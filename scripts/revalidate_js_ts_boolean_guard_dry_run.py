#!/usr/bin/env python3
"""Revalidate the boolean-guard dry-run planner against real PLW candidates.

Consumes a fresh `plw simplify --json` result for one pinned target, selects the
exact reviewed candidate, invokes the read-only planner, and proves target source
bytes remain unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict

from plan_js_ts_boolean_guard_rewrite import PlanningError, build_plan

CASES: Dict[str, Dict[str, Any]] = {
    "prettier": {
        "repository": "prettier/prettier",
        "revision": "6176846ed3c8bde9cdbdab9c1dc3294fc15d0942",
        "candidate_id": "sha256:2fb4fc47394645dd1dada20e09c329ff23ae9cf1ef499176e0ba0658b04690c4",
        "source_path": "src/language-css/utilities/index.js",
        "expected_transformation": "positive",
        "expected_after": '  return parentParentNode.type === "value-func";',
        "validated_experiment_after": '  return parentParentNode.type === "value-func";',
        "relation_to_mutation_experiment": "EXACT_PLANNED_REWRITE_MATCH",
    },
    "vite": {
        "repository": "vitejs/vite",
        "revision": "1544bb1b7ac92f775e9d0dea97954c99cc6cbd43",
        "candidate_id": "sha256:d4d1da6c55c80079b4761ae51b1593c8b051e8c3ff276fb78fd6542ab2bfdef0",
        "source_path": "packages/vite/src/node/ssr/ssrTransform.ts",
        "expected_transformation": "inverse",
        "expected_after": "  return !(id.name === 'arguments')",
        "validated_experiment_after": "  return id.name !== 'arguments'",
        "relation_to_mutation_experiment": "SEMANTICALLY_BOUNDED_PLAN_INTENTIONALLY_MORE_CONSERVATIVE",
    },
}


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=sorted(CASES), required=True)
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--simplify-result", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    spec = CASES[args.case]
    root = Path(args.target_root).resolve()
    result = load(Path(args.simplify_result))
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    matches = [
        candidate
        for candidate in (result.get("candidates", []) or [])
        if candidate.get("candidate_id") == spec["candidate_id"]
    ]
    if len(matches) != 1:
        raise SystemExit(
            f"expected exactly one candidate {spec['candidate_id']}, found {len(matches)}"
        )
    candidate = matches[0]

    if candidate.get("kind") != "js_boolean_guard_return":
        raise SystemExit(f"unexpected candidate kind: {candidate.get('kind')!r}")
    files = list(candidate.get("files", []) or [])
    if files != [spec["source_path"]]:
        raise SystemExit(f"candidate source mismatch: {files!r}")

    source = (root / spec["source_path"]).resolve()
    source.relative_to(root)
    if not source.is_file():
        raise SystemExit(f"source missing: {spec['source_path']}")

    before_sha = digest(source)
    try:
        plan = build_plan(root, candidate)
    except PlanningError as exc:
        raise SystemExit(f"planner rejected reviewed candidate: {exc}") from exc
    after_sha = digest(source)

    if before_sha != after_sha:
        raise SystemExit("target source changed during dry-run revalidation")
    if plan["match"]["transformation"] != spec["expected_transformation"]:
        raise SystemExit(
            f"unexpected transformation: {plan['match']['transformation']!r}"
        )
    if plan["planned_rewrite"]["after"] != spec["expected_after"]:
        raise SystemExit(
            "planned rewrite drift:\n"
            f"expected={spec['expected_after']!r}\n"
            f"actual={plan['planned_rewrite']['after']!r}"
        )

    relation = spec["relation_to_mutation_experiment"]
    experiment_after = spec["validated_experiment_after"]
    if relation == "EXACT_PLANNED_REWRITE_MATCH":
        if plan["planned_rewrite"]["after"] != experiment_after:
            raise SystemExit("planner should exactly match validated experiment rewrite")
    elif relation == "SEMANTICALLY_BOUNDED_PLAN_INTENTIONALLY_MORE_CONSERVATIVE":
        if plan["planned_rewrite"]["after"] == experiment_after:
            raise SystemExit("planner unexpectedly acquired operator-complement authority")
    else:
        raise SystemExit(f"unknown experiment relation: {relation}")

    candidate_path = output_dir / "candidate.json"
    plan_path = output_dir / "plan.json"
    diff_path = output_dir / "plan.patch"
    summary_path = output_dir / "summary.json"

    candidate_path.write_text(
        json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    plan_path.write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    diff_path.write_text(plan["planned_rewrite"]["diff"], encoding="utf-8")

    summary = {
        "schema_version": "plw-js-ts-v2-dry-run-cross-repo-revalidation-v1",
        "status": "DRY_RUN_CROSS_REPOSITORY_REVALIDATION_PASSED",
        "case": args.case,
        "repository": spec["repository"],
        "revision": spec["revision"],
        "candidate_id": spec["candidate_id"],
        "candidate_kind": candidate.get("kind"),
        "source_path": spec["source_path"],
        "fresh_candidate_reproduced": True,
        "planner_status": plan["status"],
        "transformation": plan["match"]["transformation"],
        "planned_after": plan["planned_rewrite"]["after"],
        "validated_experiment_after": experiment_after,
        "relation_to_mutation_experiment": relation,
        "source_sha256_before": before_sha,
        "source_sha256_after": after_sha,
        "target_source_mutated": False,
        "generic_rewrite_authority_granted": False,
        "automatic_patch_authority_granted": False,
        "upstream_mutation_authorized": False,
        "next_gate": "DRY_RUN_PLANNER_EVIDENCE_SYNTHESIS",
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
