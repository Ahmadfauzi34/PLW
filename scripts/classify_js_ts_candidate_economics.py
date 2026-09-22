#!/usr/bin/env python3
"""Classify JS/TS simplification candidates by ownership/economic surface.

This layer does not change the structural detector and does not decide that a
candidate is a valid patch. It projects path ownership and review disposition so
high-volume test/example/generated duplicates do not dominate prioritization.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

JS_PREFIX = "js_"

ROLE_ORDER = (
    "production",
    "tooling",
    "test",
    "fixture",
    "template_scaffold",
    "example_playground",
    "generated_like",
    "docs",
    "mixed",
    "other",
)

LOCAL_RULES = {
    "js_try_catch_identical_terminal_return",
    "js_terminal_literal_temporary",
    "js_redundant_else_after_terminal",
    "js_boolean_guard_return",
    "js_terminal_expression_temporary",
}

GENERATED_MARKERS = (
    "/generated/",
    "/__generated__/",
    "/dist/",
    "/build/",
    "/coverage/",
    "/__snapshots__/",
    ".snap.",
    "mockserviceworker",
)
FIXTURE_MARKERS = (
    "/fixture/",
    "/fixtures/",
    "/__fixtures__/",
    "/__testfixtures__/",
    "/testfixtures/",
    "/test-fixtures/",
    "/testdata/",
    "/test-data/",
)
TEST_MARKERS = (
    "/tests/",
    "/test/",
    "/__tests__/",
    ".test.",
    ".spec.",
)
TEMPLATE_MARKERS = (
    "/templates/",
    "/template/",
    "/scaffolds/",
    "/scaffold/",
    "/create-vite/template-",
)
EXAMPLE_MARKERS = (
    "/examples/",
    "/example/",
    "/playground/",
    "/demo/",
    "/demos/",
    "/sandbox/",
    "/samples/",
    "/sample/",
)
DOC_MARKERS = (
    "/docs/",
    "/doc/",
    "/website/",
)
TOOLING_MARKERS = (
    "/scripts/",
    "/.github/",
    "rollup.config",
    "vite.config",
    "webpack.config",
    "eslint.config",
    "babel.config",
    "jest.config",
    "vitest.config",
    "tsup.config",
)
PRODUCTION_MARKERS = (
    "/src/",
    "/lib/",
    "/packages/",
)


def _normalize(path: str) -> str:
    text = str(path or "").replace("\\", "/").lower()
    if not text.startswith("/"):
        text = "/" + text
    return text


def classify_path(path: str) -> str:
    text = _normalize(path)
    if any(marker in text for marker in GENERATED_MARKERS):
        return "generated_like"
    if any(marker in text for marker in FIXTURE_MARKERS):
        return "fixture"
    if any(marker in text for marker in TEST_MARKERS):
        return "test"
    if any(marker in text for marker in TEMPLATE_MARKERS):
        return "template_scaffold"
    if any(marker in text for marker in EXAMPLE_MARKERS):
        return "example_playground"
    if any(marker in text for marker in DOC_MARKERS):
        return "docs"
    if any(marker in text for marker in TOOLING_MARKERS):
        return "tooling"
    if any(marker in text for marker in PRODUCTION_MARKERS):
        return "production"
    return "other"


def candidate_role(files: Sequence[str]) -> Dict[str, Any]:
    per_file = [{"file": str(path), "role": classify_path(path)} for path in files]
    roles = sorted({row["role"] for row in per_file})
    role = roles[0] if len(roles) == 1 else ("mixed" if roles else "other")
    return {"role": role, "roles": roles, "files": per_file}


def _recommendation(candidate: Mapping[str, Any]) -> str:
    return str((candidate.get("priority", {}) or {}).get("recommendation", ""))


def _risk(candidate: Mapping[str, Any]) -> str:
    return str((candidate.get("proof_surface", {}) or {}).get("risk_level", "unknown"))


def _loc(candidate: Mapping[str, Any]) -> int:
    return int(
        candidate.get(
            "estimated_removable_loc",
            candidate.get("estimated_removable_duplicate_loc", 0),
        )
        or 0
    )


def review_disposition(candidate: Mapping[str, Any], role: str) -> str:
    kind = str(candidate.get("kind", ""))
    recommendation = _recommendation(candidate)
    risk = _risk(candidate)

    if kind == "js_direct_forwarding_wrapper":
        return "API_CONTRACT_REVIEW_REQUIRED"

    if recommendation.startswith("defer") or risk == "high":
        return "DEFER_PROOF_SURFACE"

    if role == "mixed":
        return "OWNERSHIP_BOUNDARY_REVIEW"

    if role in {"test", "fixture", "template_scaffold", "example_playground", "generated_like", "docs"}:
        return "NON_PRODUCTION_CONTEXT_REVIEW"

    if role == "tooling":
        return "TOOLING_CONTEXT_REVIEW"

    if role == "production":
        if kind == "js_exact_function_body_duplication":
            return "PRODUCTION_OWNERSHIP_REVIEW_REQUIRED"
        if kind in LOCAL_RULES and recommendation.startswith("candidate"):
            return "LOCAL_PRODUCTION_REVIEW"
        return "PRODUCTION_REVIEW"

    return "UNCLASSIFIED_CONTEXT_REVIEW"


def iter_result_files(results_dir: Path) -> Iterable[Path]:
    for path in sorted(results_dir.glob("*.json")):
        if path.name in {"report.json", "economic-report.json"}:
            continue
        yield path


def build_report(results_dir: Path) -> Dict[str, Any]:
    role_counts: Counter[str] = Counter()
    role_loc: Counter[str] = Counter()
    disposition_counts: Counter[str] = Counter()
    disposition_loc: Counter[str] = Counter()
    by_rule: Dict[str, Dict[str, Counter[str]]] = defaultdict(
        lambda: {
            "roles": Counter(),
            "dispositions": Counter(),
            "recommended_roles": Counter(),
            "deferred_roles": Counter(),
            "loc_by_role": Counter(),
        }
    )
    corpora: List[Dict[str, Any]] = []
    samples: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    raw_js_candidates = 0
    classified_candidates = 0
    total_estimated_loc = 0
    recommended_total = 0
    recommended_loc = 0
    production_recommended = 0
    production_recommended_loc = 0

    for path in iter_result_files(results_dir):
        payload = json.loads(path.read_text(encoding="utf-8"))
        corpus_counts: Counter[str] = Counter()
        corpus_loc: Counter[str] = Counter()
        corpus_candidates = 0

        for candidate in payload.get("candidates", []) or []:
            kind = str(candidate.get("kind", ""))
            if not kind.startswith(JS_PREFIX):
                continue
            raw_js_candidates += 1
            corpus_candidates += 1

            ownership = candidate_role(candidate.get("files", []) or [])
            role = ownership["role"]
            disposition = review_disposition(candidate, role)
            loc = _loc(candidate)
            recommendation = _recommendation(candidate)

            classified_candidates += 1
            total_estimated_loc += loc
            role_counts[role] += 1
            role_loc[role] += loc
            disposition_counts[disposition] += 1
            disposition_loc[disposition] += loc
            corpus_counts[role] += 1
            corpus_loc[role] += loc
            by_rule[kind]["roles"][role] += 1
            by_rule[kind]["dispositions"][disposition] += 1
            by_rule[kind]["loc_by_role"][role] += loc

            if recommendation.startswith("candidate"):
                recommended_total += 1
                recommended_loc += loc
                by_rule[kind]["recommended_roles"][role] += 1
                if role == "production":
                    production_recommended += 1
                    production_recommended_loc += loc
            elif recommendation.startswith("defer"):
                by_rule[kind]["deferred_roles"][role] += 1

            if len(samples[disposition]) < 8:
                samples[disposition].append(
                    {
                        "corpus": path.stem,
                        "candidate_id": candidate.get("candidate_id"),
                        "kind": kind,
                        "role": role,
                        "files": list(candidate.get("files", []) or [])[:4],
                        "names": list(candidate.get("names", []) or [])[:4],
                        "recommendation": recommendation,
                        "risk_level": _risk(candidate),
                        "estimated_removable_loc": loc,
                    }
                )

        corpora.append(
            {
                "id": path.stem,
                "js_candidate_count": corpus_candidates,
                "roles": dict(sorted(corpus_counts.items())),
                "estimated_removable_loc_by_role": dict(sorted(corpus_loc.items())),
            }
        )

    errors: List[str] = []
    if classified_candidates != raw_js_candidates:
        errors.append(
            f"classification coverage mismatch: raw={raw_js_candidates} classified={classified_candidates}"
        )

    role_rows = {
        role: {
            "candidate_count": role_counts.get(role, 0),
            "estimated_removable_loc": role_loc.get(role, 0),
        }
        for role in ROLE_ORDER
        if role_counts.get(role, 0) or role_loc.get(role, 0)
    }

    return {
        "schema_version": "plw-js-ts-v2-economic-ownership-v1",
        "status": "ECONOMIC_OWNERSHIP_OBSERVATION_READY" if not errors else "INVALID",
        "authority": {
            "classification_is_path_heuristic": True,
            "economic_disposition_is_review_routing_only": True,
            "candidate_is_not_patch": True,
            "candidate_is_not_behavioral_equivalence": True,
            "no_numeric_truth_score": True,
            "source_mutation_allowed": False,
        },
        "coverage": {
            "raw_js_candidates": raw_js_candidates,
            "classified_candidates": classified_candidates,
            "total_estimated_removable_loc": total_estimated_loc,
        },
        "roles": role_rows,
        "dispositions": {
            name: {
                "candidate_count": count,
                "estimated_removable_loc": disposition_loc.get(name, 0),
            }
            for name, count in sorted(disposition_counts.items())
        },
        "per_rule": {
            kind: {
                "roles": dict(sorted(data["roles"].items())),
                "recommended_roles": dict(sorted(data["recommended_roles"].items())),
                "deferred_roles": dict(sorted(data["deferred_roles"].items())),
                "dispositions": dict(sorted(data["dispositions"].items())),
                "estimated_removable_loc_by_role": dict(
                    sorted(data["loc_by_role"].items())
                ),
            }
            for kind, data in sorted(by_rule.items())
        },
        "production_adjusted_yield": {
            "recommended_total": recommended_total,
            "recommended_estimated_removable_loc": recommended_loc,
            "production_recommended": production_recommended,
            "production_recommended_estimated_removable_loc": production_recommended_loc,
            "production_share_of_recommended_candidates": (
                production_recommended / recommended_total if recommended_total else 0.0
            ),
            "production_share_of_recommended_estimated_loc": (
                production_recommended_loc / recommended_loc if recommended_loc else 0.0
            ),
        },
        "corpora": corpora,
        "samples_by_disposition": dict(sorted(samples.items())),
        "errors": errors,
        "interpretation": {
            "non_production_does_not_mean_invalid": True,
            "production_does_not_mean_safe_to_patch": True,
            "exact_duplication_requires_ownership_and_binding_review": True,
            "forwarding_wrapper_requires_api_contract_review": True,
            "next_gate": "bounded production-sample review plus target-native tests/type-check",
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    coverage = report["coverage"]
    adjusted = report["production_adjusted_yield"]
    lines = [
        "# JS/TS V2 economic / ownership qualification",
        "",
        f"Status: **{report['status']}**",
        "",
        "This layer routes review effort. It does not establish patch validity or behavioral equivalence.",
        "",
        "## Ownership surface",
        "",
        "| Role | Candidates | Est. removable LOC |",
        "| --- | ---: | ---: |",
    ]
    for role, row in report["roles"].items():
        lines.append(
            f"| {role} | {row['candidate_count']} | {row['estimated_removable_loc']} |"
        )
    lines.extend(
        [
            "",
            "## Production-adjusted yield",
            "",
            f"- raw JS candidates: **{coverage['raw_js_candidates']}**",
            f"- total estimated removable LOC: **{coverage['total_estimated_removable_loc']}**",
            f"- structurally recommended candidates: **{adjusted['recommended_total']}**",
            f"- structurally recommended estimated LOC: **{adjusted['recommended_estimated_removable_loc']}**",
            f"- recommended candidates on production surfaces: **{adjusted['production_recommended']}**",
            f"- recommended estimated LOC on production surfaces: **{adjusted['production_recommended_estimated_removable_loc']}**",
            f"- production share of recommended candidates: **{adjusted['production_share_of_recommended_candidates']:.1%}**",
            f"- production share of recommended estimated LOC: **{adjusted['production_share_of_recommended_estimated_loc']:.1%}**",
            "",
            "## Review dispositions",
            "",
            "| Disposition | Candidates | Est. removable LOC |",
            "| --- | ---: | ---: |",
        ]
    )
    for name, row in report["dispositions"].items():
        lines.append(
            f"| {name} | {row['candidate_count']} | {row['estimated_removable_loc']} |"
        )
    lines.extend(
        [
            "",
            "## Authority boundary",
            "",
            "`ownership classification != proof of semantic ownership`",
            "",
            "`economic disposition != patch recommendation`",
            "",
            "Next gate: bounded production-sample review plus target-native tests/type-check.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()

    report = build_report(Path(args.results_dir))
    Path(args.output).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    Path(args.summary).write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "coverage": report["coverage"],
                "production_adjusted_yield": report["production_adjusted_yield"],
                "errors": report["errors"],
            },
            sort_keys=True,
        )
    )
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
