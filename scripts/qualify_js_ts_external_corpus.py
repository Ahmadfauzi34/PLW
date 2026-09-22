#!/usr/bin/env python3
"""Aggregate pinned external-corpus observations from PLW simplify.

This script is deliberately observational. It never edits a corpus and never
converts a structural candidate into a correctness or behavioral-equivalence
claim.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

RULE_KIND_TO_FAMILY = {
    "js_try_catch_identical_terminal_return": "try_catch_terminal_return",
    "js_terminal_literal_temporary": "terminal_literal_temporary",
    "js_direct_forwarding_wrapper": "direct_forwarding_wrapper",
    "js_exact_function_body_duplication": "exact_function_body_duplication",
    "js_redundant_else_after_terminal": "redundant_else_after_terminal",
    "js_boolean_guard_return": "boolean_guard_return",
    "js_terminal_expression_temporary": "terminal_expression_temporary",
}
JS_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx")


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sum_js_counts(payload: Dict[str, Any]) -> Dict[str, int]:
    inv = (
        payload.get("canonical_anatomy_bridge", {})
        .get("language_inventory", {})
        .get("reference_source_counts", {})
    )
    return {ext: int(inv.get(ext, 0) or 0) for ext in JS_EXTENSIONS}


def _sample(candidate: Dict[str, Any]) -> Dict[str, Any]:
    priority = candidate.get("priority", {}) or {}
    surface = candidate.get("proof_surface", {}) or {}
    return {
        "candidate_id": candidate.get("candidate_id"),
        "kind": candidate.get("kind"),
        "files": list(candidate.get("files", []) or [])[:4],
        "names": list(candidate.get("names", []) or [])[:4],
        "recommendation": priority.get("recommendation"),
        "risk_level": surface.get("risk_level"),
        "estimated_removable_loc": int(
            candidate.get(
                "estimated_removable_loc",
                candidate.get("estimated_removable_duplicate_loc", 0),
            )
            or 0
        ),
    }


def _classify_recommendation(value: str) -> str:
    if value.startswith("candidate"):
        return "candidate"
    if value.startswith("defer"):
        return "defer"
    return "other"


def aggregate(manifest: Dict[str, Any], results_dir: Path) -> Dict[str, Any]:
    baseline = manifest["baseline"]
    errors: List[str] = []
    corpus_rows: List[Dict[str, Any]] = []
    aggregate_rules: Dict[str, Dict[str, Any]] = {
        family: {
            "candidate_count": 0,
            "recommended_count": 0,
            "deferred_count": 0,
            "other_count": 0,
            "estimated_removable_loc": 0,
            "risk": Counter(),
            "samples": [],
        }
        for family in RULE_KIND_TO_FAMILY.values()
    }

    for corpus in manifest["corpora"]:
        corpus_id = corpus["id"]
        result_path = results_dir / f"{corpus_id}.json"
        if not result_path.is_file():
            errors.append(f"{corpus_id}: result missing")
            continue
        payload = _load(result_path)
        bridge = payload.get("canonical_anatomy_bridge", {}) or {}
        scope = bridge.get("semantic_frontend_scope", {}) or {}
        frontend = bridge.get("semantic_frontend")
        if frontend != baseline["semantic_frontend"]:
            errors.append(f"{corpus_id}: frontend={frontend!r}")
        if int(scope.get("ts_js_rule_count", -1)) != int(baseline["ts_js_rule_count"]):
            errors.append(
                f"{corpus_id}: rule_count={scope.get('ts_js_rule_count')!r}"
            )

        source_counts = _sum_js_counts(payload)
        if sum(source_counts.values()) <= 0:
            errors.append(f"{corpus_id}: no JS/TS source files observed")

        rule_rows: Dict[str, Dict[str, Any]] = {
            family: {
                "candidate_count": 0,
                "recommended_count": 0,
                "deferred_count": 0,
                "other_count": 0,
                "estimated_removable_loc": 0,
                "risk": Counter(),
                "samples": [],
            }
            for family in RULE_KIND_TO_FAMILY.values()
        }
        unknown_js_kinds = set()
        js_candidates = []
        for candidate in payload.get("candidates", []) or []:
            kind = str(candidate.get("kind", ""))
            if not kind.startswith("js_"):
                continue
            js_candidates.append(candidate)
            family = RULE_KIND_TO_FAMILY.get(kind)
            if family is None:
                unknown_js_kinds.add(kind)
                continue
            priority = candidate.get("priority", {}) or {}
            surface = candidate.get("proof_surface", {}) or {}
            recommendation = str(priority.get("recommendation", ""))
            bucket = _classify_recommendation(recommendation)
            loc = int(
                candidate.get(
                    "estimated_removable_loc",
                    candidate.get("estimated_removable_duplicate_loc", 0),
                )
                or 0
            )
            for target in (rule_rows[family], aggregate_rules[family]):
                target["candidate_count"] += 1
                target[f"{bucket}_count"] += 1
                target["estimated_removable_loc"] += loc
                target["risk"][str(surface.get("risk_level", "unknown"))] += 1
                if len(target["samples"]) < 5:
                    target["samples"].append(_sample(candidate))

        if unknown_js_kinds:
            errors.append(
                f"{corpus_id}: unknown JS candidate kinds={sorted(unknown_js_kinds)}"
            )

        metrics = payload.get("metrics", {}) or {}
        corpus_rows.append(
            {
                "id": corpus_id,
                "repository": corpus["repository"],
                "revision": corpus["revision"],
                "source_counts": source_counts,
                "js_files_scanned": int(metrics.get("js_semantic_files_scanned", 0) or 0),
                "js_source_loc": int(metrics.get("js_semantic_source_loc", 0) or 0),
                "js_candidate_count": len(js_candidates),
                "frontier_status": (payload.get("frontier", {}) or {}).get("status"),
                "rules": {
                    family: {
                        **{k: v for k, v in row.items() if k not in {"risk"}},
                        "risk": dict(sorted(row["risk"].items())),
                    }
                    for family, row in rule_rows.items()
                },
                "behavioral_validation": "NOT_RUN",
                "false_positive_count": None,
                "authority": "STRUCTURAL_CORPUS_OBSERVATION_ONLY",
            }
        )

    aggregate = {
        family: {
            **{k: v for k, v in row.items() if k not in {"risk"}},
            "risk": dict(sorted(row["risk"].items())),
        }
        for family, row in aggregate_rules.items()
    }
    return {
        "schema_version": manifest["schema_version"],
        "qualification_status": (
            "STRUCTURAL_CORPUS_OBSERVATION_READY" if not errors else "INVALID"
        ),
        "baseline": baseline,
        "authority": manifest["authority"],
        "corpora": corpus_rows,
        "aggregate_rules": aggregate,
        "errors": errors,
        "interpretation": {
            "zero_hit_is_evidence": True,
            "candidate_count_is_not_valid_patch_count": True,
            "estimated_removable_loc_is_not_realized_savings": True,
            "false_positive_rate_not_claimed_without_review": True,
            "next_gate": "sample review and target-native behavioral/type-check validation",
        },
    }


def render_markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# JS/TS V2 external corpus qualification",
        "",
        f"Status: **{report['qualification_status']}**",
        "",
        "This report is structural observation only. Candidate counts are not patch counts,",
        "and no false-positive rate is claimed without review/behavioral proof.",
        "",
        "## Corpus",
        "",
        "| Corpus | JS/TS files | JS/TS LOC | Candidates |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in report["corpora"]:
        lines.append(
            f"| {row['repository']} @ `{row['revision'][:12]}` | "
            f"{row['js_files_scanned']} | {row['js_source_loc']} | "
            f"{row['js_candidate_count']} |"
        )
    lines.extend(
        [
            "",
            "## Rule yield",
            "",
            "| Rule | Observed | Candidate | Defer | Est. removable LOC |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for family, row in report["aggregate_rules"].items():
        lines.append(
            f"| {family} | {row['candidate_count']} | "
            f"{row['recommended_count']} | {row['deferred_count']} | "
            f"{row['estimated_removable_loc']} |"
        )
    if report["errors"]:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in report["errors"])
    lines.extend(
        [
            "",
            "## Authority boundary",
            "",
            "`candidate != patch != behavioral equivalence`",
            "",
            "Next gate: bounded sample review plus target-native tests/type-check for any patch candidate.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()

    manifest = _load(Path(args.manifest))
    report = aggregate(manifest, Path(args.results_dir))
    Path(args.output).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    Path(args.summary).write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({
        "qualification_status": report["qualification_status"],
        "corpora": len(report["corpora"]),
        "errors": report["errors"],
    }, sort_keys=True))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
