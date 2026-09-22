#!/usr/bin/env python3
"""Build a deterministic bounded review pack for JS/TS V2 candidates.

This consumes structural + economic qualification evidence and target source
snapshots. It extracts bounded source context and discovers target-native
validation surfaces. It does not edit source, execute target tests, or decide
that a candidate is a valid patch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from classify_js_ts_candidate_economics import candidate_role, review_disposition

LOCAL_DISPOSITION = "LOCAL_PRODUCTION_REVIEW"
OWNERSHIP_DISPOSITION = "PRODUCTION_OWNERSHIP_REVIEW_REQUIRED"
API_DISPOSITION = "API_CONTRACT_REVIEW_REQUIRED"
LOCAL_SAMPLE_PER_RULE = 2
OWNERSHIP_SAMPLE_LIMIT = 3
API_SAMPLE_LIMIT = 2
CONTEXT_LINES = 8

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "unknown": 3}
VALIDATION_SCRIPT_RE = re.compile(
    r"(?:^|[:_-])(test|type|typecheck|check|lint|build|verify|validate)(?:$|[:_-])",
    re.IGNORECASE,
)


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _candidate_records(results_dir: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for path in sorted(results_dir.glob("*.json")):
        if path.name in {
            "report.json",
            "economic-report.json",
            "review-pack.json",
        }:
            continue
        payload = _load(path)
        corpus = path.stem
        for candidate in payload.get("candidates", []) or []:
            kind = str(candidate.get("kind", ""))
            if not kind.startswith("js_"):
                continue
            ownership = candidate_role(candidate.get("files", []) or [])
            disposition = review_disposition(candidate, ownership["role"])
            records.append(
                {
                    "corpus": corpus,
                    "candidate": candidate,
                    "role": ownership["role"],
                    "disposition": disposition,
                }
            )
    return records


def _loc(candidate: Mapping[str, Any]) -> int:
    return int(
        candidate.get(
            "estimated_removable_loc",
            candidate.get("estimated_removable_duplicate_loc", 0),
        )
        or 0
    )


def _risk(candidate: Mapping[str, Any]) -> str:
    return str((candidate.get("proof_surface", {}) or {}).get("risk_level", "unknown"))


def _candidate_key(record: Mapping[str, Any]) -> tuple:
    candidate = record["candidate"]
    members = candidate.get("members", []) or []
    first = members[0] if members else {}
    return (
        RISK_ORDER.get(_risk(candidate), 9),
        _loc(candidate),
        str(record["corpus"]),
        str(first.get("file", "")),
        int(first.get("line_start", 0) or 0),
        str(candidate.get("candidate_id", "")),
    )


def _select_diverse(
    records: Sequence[Dict[str, Any]],
    limit: int,
    *,
    high_gain_first: bool,
) -> List[Dict[str, Any]]:
    if high_gain_first:
        ordered = sorted(
            records,
            key=lambda r: (
                -_loc(r["candidate"]),
                RISK_ORDER.get(_risk(r["candidate"]), 9),
                str(r["corpus"]),
                str(r["candidate"].get("candidate_id", "")),
            ),
        )
    else:
        ordered = sorted(records, key=_candidate_key)

    selected: List[Dict[str, Any]] = []
    used_corpora = set()
    for record in ordered:
        if record["corpus"] in used_corpora:
            continue
        selected.append(record)
        used_corpora.add(record["corpus"])
        if len(selected) >= limit:
            return selected
    for record in ordered:
        if record in selected:
            continue
        selected.append(record)
        if len(selected) >= limit:
            break
    return selected


def select_review_records(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []

    local_by_kind: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    ownership: List[Dict[str, Any]] = []
    api: List[Dict[str, Any]] = []

    for record in records:
        if record["role"] != "production":
            continue
        kind = str(record["candidate"].get("kind", ""))
        if record["disposition"] == LOCAL_DISPOSITION:
            local_by_kind[kind].append(record)
        elif record["disposition"] == OWNERSHIP_DISPOSITION:
            ownership.append(record)
        elif record["disposition"] == API_DISPOSITION:
            api.append(record)

    for kind in sorted(local_by_kind):
        selected.extend(
            sorted(local_by_kind[kind], key=_candidate_key)[:LOCAL_SAMPLE_PER_RULE]
        )

    selected.extend(
        _select_diverse(
            ownership,
            OWNERSHIP_SAMPLE_LIMIT,
            high_gain_first=True,
        )
    )
    selected.extend(
        _select_diverse(
            api,
            API_SAMPLE_LIMIT,
            high_gain_first=False,
        )
    )

    # Preserve deterministic category ordering while deduplicating IDs.
    unique: List[Dict[str, Any]] = []
    seen = set()
    for record in selected:
        cid = str(record["candidate"].get("candidate_id", ""))
        if cid in seen:
            continue
        seen.add(cid)
        unique.append(record)
    return unique


def _safe_target(root: Path, rel: str) -> Path:
    candidate = (root / rel).resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"path escapes corpus root: {rel}") from exc
    return candidate


def _extract_member_context(corpus_root: Path, member: Mapping[str, Any]) -> Dict[str, Any]:
    rel = str(member.get("file", ""))
    path = _safe_target(corpus_root, rel)
    if not path.is_file():
        return {
            "file": rel,
            "error": "source_file_missing",
            "line_start": member.get("line_start"),
            "line_end": member.get("line_end"),
        }

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(1, int(member.get("line_start", 1) or 1))
    end = max(start, int(member.get("line_end", start) or start))
    context_start = max(1, start - CONTEXT_LINES)
    context_end = min(len(lines), end + CONTEXT_LINES)
    excerpt = [
        {"line": lineno, "text": lines[lineno - 1]}
        for lineno in range(context_start, context_end + 1)
    ]
    return {
        "file": rel,
        "name": member.get("name"),
        "line_start": start,
        "line_end": end,
        "context_start": context_start,
        "context_end": context_end,
        "source_sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
        "excerpt": excerpt,
    }


def _nearest_package_json(corpus_root: Path, rel_file: str) -> Path | None:
    source = _safe_target(corpus_root, rel_file)
    current = source.parent
    root = corpus_root.resolve()
    while True:
        package = current / "package.json"
        if package.is_file():
            return package
        if current == root:
            return None
        if root not in current.parents:
            return None
        current = current.parent


def _read_package_surface(package: Path, corpus_root: Path) -> Dict[str, Any]:
    try:
        payload = _load(package)
    except Exception as exc:
        return {
            "package_json": package.relative_to(corpus_root).as_posix(),
            "error": f"{type(exc).__name__}: {exc}",
        }
    scripts = payload.get("scripts", {}) or {}
    relevant = {
        str(name): str(command)
        for name, command in sorted(scripts.items())
        if VALIDATION_SCRIPT_RE.search(str(name))
    }
    return {
        "package_json": package.relative_to(corpus_root).as_posix(),
        "package_name": payload.get("name"),
        "package_type": payload.get("type"),
        "validation_scripts": relevant,
    }


def _validation_surface(corpus_root: Path, files: Sequence[str]) -> Dict[str, Any]:
    packages: Dict[str, Dict[str, Any]] = {}
    for rel in files:
        package = _nearest_package_json(corpus_root, rel)
        if package is None:
            continue
        key = package.relative_to(corpus_root).as_posix()
        packages[key] = _read_package_surface(package, corpus_root)

    root_package = corpus_root / "package.json"
    root_surface = (
        _read_package_surface(root_package, corpus_root)
        if root_package.is_file()
        else None
    )

    package_manager = "unknown"
    for marker, manager in (
        ("pnpm-lock.yaml", "pnpm"),
        ("yarn.lock", "yarn"),
        ("package-lock.json", "npm"),
        ("bun.lock", "bun"),
        ("bun.lockb", "bun"),
    ):
        if (corpus_root / marker).exists():
            package_manager = manager
            break

    config_candidates = []
    for name in (
        "pnpm-workspace.yaml",
        "tsconfig.json",
        "eslint.config.js",
        "eslint.config.mjs",
        "vitest.config.ts",
        "vitest.config.js",
        "jest.config.js",
        "jest.config.ts",
    ):
        if (corpus_root / name).exists():
            config_candidates.append(name)

    return {
        "package_manager": package_manager,
        "root_package": root_surface,
        "nearest_packages": [packages[key] for key in sorted(packages)],
        "root_validation_configs": config_candidates,
        "execution_performed": False,
        "authority": "validation_surface_discovery_only",
    }


def _proof_questions(disposition: str, kind: str) -> List[str]:
    common = [
        "What target-native validation command covers the affected file/package?",
        "Does the source context contain comments, naming, or API intent that the structural witness cannot represent?",
    ]
    if disposition == LOCAL_DISPOSITION:
        return common + [
            "Can the local rewrite preserve evaluation count, lexical scope, and control-flow exactly?",
            "Would the rewrite alter debugging/stack readability or an intentional intermediate name?",
        ]
    if disposition == OWNERSHIP_DISPOSITION:
        return common + [
            "Do duplicate bodies resolve every referenced binding to equivalent semantics?",
            "Is there a neutral abstraction owner that does not introduce a dependency cycle or ownership inversion?",
            "Would deduplication preserve module initialization, tree-shaking, and every public callable surface?",
        ]
    if disposition == API_DISPOSITION:
        return common + [
            "Is the wrapper exported, overridden, instrumented, or relied on as a compatibility boundary?",
            "Would removing the wrapper alter method binding, stack traces, mocking, subclass behavior, or API identity?",
        ]
    return common


def build_review_pack(results_dir: Path, corpora_root: Path) -> Dict[str, Any]:
    records = _candidate_records(results_dir)
    selected = select_review_records(records)
    samples = []
    errors: List[str] = []

    for index, record in enumerate(selected, 1):
        candidate = record["candidate"]
        corpus = str(record["corpus"])
        corpus_root = (corpora_root / corpus).resolve()
        if not corpus_root.is_dir():
            errors.append(f"{corpus}: corpus checkout missing")
            continue

        members = candidate.get("members", []) or []
        contexts = [_extract_member_context(corpus_root, member) for member in members]
        files = list(candidate.get("files", []) or [])
        samples.append(
            {
                "sample_index": index,
                "corpus": corpus,
                "candidate_id": candidate.get("candidate_id"),
                "kind": candidate.get("kind"),
                "role": record["role"],
                "disposition": record["disposition"],
                "estimated_removable_loc": _loc(candidate),
                "risk_level": _risk(candidate),
                "names": list(candidate.get("names", []) or []),
                "files": files,
                "members": contexts,
                "semantic_witness": candidate.get("semantic_witness"),
                "proof_obligation": candidate.get("proof_obligation"),
                "proof_surface": candidate.get("proof_surface"),
                "priority": candidate.get("priority"),
                "validation_surface": _validation_surface(corpus_root, files),
                "proof_questions": _proof_questions(
                    record["disposition"],
                    str(candidate.get("kind", "")),
                ),
                "review_outcome": "UNREVIEWED",
                "patch_experiment_authorized": False,
            }
        )

    by_disposition: Dict[str, int] = defaultdict(int)
    by_kind: Dict[str, int] = defaultdict(int)
    for sample in samples:
        by_disposition[sample["disposition"]] += 1
        by_kind[sample["kind"]] += 1

    return {
        "schema_version": "plw-js-ts-v2-bounded-production-review-v1",
        "status": "BOUNDED_REVIEW_PACK_READY" if not errors else "INVALID",
        "selection_policy": {
            "local_production_per_rule": LOCAL_SAMPLE_PER_RULE,
            "ownership_sample_limit": OWNERSHIP_SAMPLE_LIMIT,
            "api_sample_limit": API_SAMPLE_LIMIT,
            "deterministic": True,
            "local_prefers_low_risk_small_surface": True,
            "ownership_prefers_high_gain_with_corpus_diversity": True,
            "api_prefers_corpus_diversity": True,
        },
        "authority": {
            "review_pack_is_not_patch": True,
            "review_pack_is_not_behavioral_equivalence": True,
            "validation_commands_are_discovered_not_executed": True,
            "source_mutation_allowed": False,
            "patch_experiment_authorized": False,
        },
        "sample_count": len(samples),
        "samples_by_disposition": dict(sorted(by_disposition.items())),
        "samples_by_kind": dict(sorted(by_kind.items())),
        "samples": samples,
        "errors": errors,
        "next_gate": "agent/source review followed by explicitly bounded target-worktree validation experiments",
    }


def render_markdown(pack: Mapping[str, Any]) -> str:
    lines = [
        "# JS/TS V2 bounded production review pack",
        "",
        f"Status: **{pack['status']}**",
        "",
        "This pack extracts source and validation context. It does not authorize a patch.",
        "",
        f"Selected samples: **{pack['sample_count']}**",
        "",
        "## Sample inventory",
        "",
        "| # | Corpus | Kind | Disposition | LOC | File |",
        "| ---: | --- | --- | --- | ---: | --- |",
    ]
    for sample in pack["samples"]:
        first_file = sample["files"][0] if sample["files"] else ""
        lines.append(
            f"| {sample['sample_index']} | {sample['corpus']} | "
            f"{sample['kind']} | {sample['disposition']} | "
            f"{sample['estimated_removable_loc']} | `{first_file}` |"
        )
    lines.extend(
        [
            "",
            "## Authority boundary",
            "",
            "`review pack != patch != behavioral equivalence`",
            "",
            "Target-native validation commands are discovered only; none are executed by this gate.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--corpora-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()

    pack = build_review_pack(Path(args.results_dir), Path(args.corpora_root))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(pack, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    Path(args.summary).write_text(render_markdown(pack), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": pack["status"],
                "sample_count": pack["sample_count"],
                "samples_by_disposition": pack["samples_by_disposition"],
                "samples_by_kind": pack["samples_by_kind"],
                "errors": pack["errors"],
            },
            sort_keys=True,
        )
    )
    return 0 if not pack["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
