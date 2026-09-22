#!/usr/bin/env python3
"""Synthesize retained evidence for boolean-guard read-only planner promotion."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
RULE = "js_boolean_guard_return"
PRETTIER_ID = "sha256:2fb4fc47394645dd1dada20e09c329ff23ae9cf1ef499176e0ba0658b04690c4"
VITE_ID = "sha256:d4d1da6c55c80079b4761ae51b1593c8b051e8c3ff276fb78fd6542ab2bfdef0"


def load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def synthesize(
    index: Dict[str, Any],
    proposal: Dict[str, Any],
    reference: Dict[str, Any],
    prettier: Dict[str, Any],
    vite: Dict[str, Any],
    aggregate: Dict[str, Any],
) -> Dict[str, Any]:
    errors: List[str] = []

    artifacts = index.get("artifacts", []) or []
    if len(artifacts) != 5:
        errors.append(f"expected 5 indexed artifacts, found {len(artifacts)}")
    names = [str(row.get("evidence_id", "")) for row in artifacts]
    if len(set(names)) != len(names):
        errors.append("duplicate evidence_id")
    for row in artifacts:
        if not DIGEST_RE.fullmatch(str(row.get("artifact_digest", ""))):
            errors.append(f"invalid artifact digest for {row.get('evidence_id')}")
        if int(row.get("workflow_run_id", 0) or 0) <= 0:
            errors.append(f"invalid workflow_run_id for {row.get('evidence_id')}")

    if proposal.get("status") != "BOOLEAN_GUARD_REWRITE_PROPOSAL_REVIEW_READY":
        errors.append("proposal review is not ready")
    evidence = proposal.get("evidence", {}) or {}
    if evidence.get("repository_count") != 2 or evidence.get("candidate_count") != 2:
        errors.append("proposal review evidence cardinality drift")
    proposal_authority = proposal.get("authority", {}) or {}
    for key in (
        "generic_rewrite_authority_granted",
        "automatic_patch_authority_granted",
        "upstream_mutation_authorized",
        "truth_commit",
    ):
        if proposal_authority.get(key) is not False:
            errors.append(f"proposal authority drift: {key}")

    if reference.get("status") != "BOOLEAN_GUARD_DRY_RUN_PLANNER_REFERENCE_PASSED":
        errors.append("planner reference suite is not ready")
    if reference.get("positive_style") != "PASS" or reference.get("inverse_style") != "PASS":
        errors.append("planner positive/inverse reference coverage missing")
    if int(reference.get("negative_cases", 0) or 0) < 7:
        errors.append("planner fail-closed reference coverage too small")
    if reference.get("source_mutation") is not False:
        errors.append("planner reference mutated source")
    if reference.get("generic_rewrite_authority_granted") is not False:
        errors.append("planner reference leaked generic rewrite authority")

    real_rows = [prettier, vite]
    expected = {
        "prettier": ("prettier/prettier", PRETTIER_ID),
        "vite": ("vitejs/vite", VITE_ID),
    }
    for row in real_rows:
        case = str(row.get("case", ""))
        if case not in expected:
            errors.append(f"unexpected real-candidate case: {case!r}")
            continue
        repository, candidate_id = expected[case]
        if row.get("status") != "DRY_RUN_CROSS_REPOSITORY_REVALIDATION_PASSED":
            errors.append(f"{case}: revalidation not passed")
        if row.get("repository") != repository:
            errors.append(f"{case}: repository mismatch")
        if row.get("candidate_id") != candidate_id:
            errors.append(f"{case}: candidate mismatch")
        if row.get("candidate_kind") != RULE:
            errors.append(f"{case}: rule mismatch")
        if row.get("fresh_candidate_reproduced") is not True:
            errors.append(f"{case}: candidate was not freshly reproduced")
        if row.get("planner_status") != "DRY_RUN_REWRITE_PLAN_READY":
            errors.append(f"{case}: planner did not produce a ready plan")
        if row.get("source_sha256_before") != row.get("source_sha256_after"):
            errors.append(f"{case}: source hash changed")
        if row.get("target_source_mutated") is not False:
            errors.append(f"{case}: target mutation observed")
        for key in (
            "generic_rewrite_authority_granted",
            "automatic_patch_authority_granted",
            "upstream_mutation_authorized",
        ):
            if row.get(key) is not False:
                errors.append(f"{case}: authority drift {key}")

    if prettier.get("relation_to_mutation_experiment") != "EXACT_PLANNED_REWRITE_MATCH":
        errors.append("Prettier planner/experiment relation drift")
    if (
        vite.get("relation_to_mutation_experiment")
        != "SEMANTICALLY_BOUNDED_PLAN_INTENTIONALLY_MORE_CONSERVATIVE"
    ):
        errors.append("Vite planner should remain conservatively narrower than experiment")

    if aggregate.get("status") != "DRY_RUN_PLANNER_CROSS_REPOSITORY_REVALIDATED":
        errors.append("cross-repository aggregate is not validated")
    if set(aggregate.get("repositories", []) or []) != {"prettier/prettier", "vitejs/vite"}:
        errors.append("aggregate repository set drift")
    if aggregate.get("candidate_count") != 2:
        errors.append("aggregate candidate count drift")
    if aggregate.get("fresh_candidate_reproduction") is not True:
        errors.append("aggregate fresh-candidate proof missing")
    if aggregate.get("target_source_mutation") is not False:
        errors.append("aggregate target mutation must be false")
    for key in (
        "generic_rewrite_authority_granted",
        "automatic_patch_authority_granted",
        "upstream_mutation_authorized",
    ):
        if aggregate.get(key) is not False:
            errors.append(f"aggregate authority drift: {key}")

    ready = not errors
    return {
        "schema_version": "plw-js-ts-v2-boolean-guard-planner-promotion-v1",
        "status": "REUSABLE_READ_ONLY_PLANNER_READY" if ready else "INVALID",
        "rule": RULE,
        "evidence": {
            "indexed_artifact_count": len(artifacts),
            "proposal_review": proposal.get("status"),
            "reference_planner": reference.get("status"),
            "real_repository_count": 2 if ready else None,
            "real_candidate_count": 2 if ready else None,
            "repositories": ["prettier/prettier", "vitejs/vite"] if ready else [],
            "fresh_candidate_reproduction": bool(
                prettier.get("fresh_candidate_reproduced")
                and vite.get("fresh_candidate_reproduced")
            ),
        },
        "capability": {
            "reusable_read_only_planning_authority_granted": ready,
            "candidate_source_requirement": "PLW_ANALYZER_BOOLEAN_GUARD_WITNESS",
            "applicability_contract": "js_ts_v2_boolean_guard_rewrite_proposal_v1",
            "exact_plan_or_fail_closed": True,
            "diff_generation_allowed": ready,
            "target_source_write_allowed": False,
        },
        "authority": {
            "source_mutation_allowed": False,
            "generic_mutation_authority_granted": False,
            "automatic_patch_authority_granted": False,
            "upstream_mutation_authorized": False,
            "global_behavioral_equivalence_proven": False,
            "truth_commit": False,
        },
        "errors": errors,
        "next_gate": "MUTATION_BOUNDARY_CONTRACT_REVIEW" if ready else "REPAIR_EVIDENCE_CHAIN",
    }


def render_markdown(report: Dict[str, Any]) -> str:
    cap = report["capability"]
    lines = [
        "# JS/TS boolean-guard planner evidence synthesis",
        "",
        f"Status: **{report['status']}**",
        "",
        f"Rule: **{report['rule']}**",
        f"Reusable read-only planning: **{cap['reusable_read_only_planning_authority_granted']}**",
        f"Target source write allowed: **{cap['target_source_write_allowed']}**",
        "",
        "Evidence chain:",
        "",
        f"- proposal review: {report['evidence']['proposal_review']}",
        f"- planner reference: {report['evidence']['reference_planner']}",
        f"- real repositories: {report['evidence']['real_repository_count']}",
        f"- real candidates: {report['evidence']['real_candidate_count']}",
        f"- fresh candidate reproduction: {report['evidence']['fresh_candidate_reproduction']}",
        "",
        "Authority boundary:",
        "",
        "reusable read-only planner != generic mutation authority",
        "",
        "diff generation != source write",
        "",
        f"Next gate: {report['next_gate']}",
    ]
    if report["errors"]:
        lines.extend(["", "Errors:", ""])
        lines.extend(f"- {error}" for error in report["errors"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True)
    parser.add_argument("--proposal-report", required=True)
    parser.add_argument("--reference-summary", required=True)
    parser.add_argument("--prettier-summary", required=True)
    parser.add_argument("--vite-summary", required=True)
    parser.add_argument("--aggregate-report", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()

    report = synthesize(
        load(Path(args.index)),
        load(Path(args.proposal_report)),
        load(Path(args.reference_summary)),
        load(Path(args.prettier_summary)),
        load(Path(args.vite_summary)),
        load(Path(args.aggregate_report)),
    )
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    Path(args.summary).write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "read_only_planning": report["capability"]["reusable_read_only_planning_authority_granted"],
        "source_write": report["capability"]["target_source_write_allowed"],
        "errors": report["errors"],
    }, sort_keys=True))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
