#!/usr/bin/env python3
"""Review the bounded JS/TS boolean-guard reusable-rewrite proposal.

This validates proposal prerequisites against the local mutation-evidence index.
It does not implement or authorize source rewriting.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from synthesize_js_ts_local_rule_evidence import synthesize

RULE = "js_boolean_guard_return"


def load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def review(index: Dict[str, Any], proposal: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    synthesis = synthesize(index)

    if synthesis.get("status") != "LOCAL_RULE_EVIDENCE_SYNTHESIS_READY":
        errors.append("evidence synthesis is not ready")

    rule_state = (synthesis.get("rules", {}) or {}).get(RULE)
    if not rule_state:
        errors.append(f"missing evidence state for {RULE}")
        rule_state = {}

    if proposal.get("rule") != RULE:
        errors.append(f"proposal rule must be {RULE}")

    expected_stage = proposal.get("evidence_requirements", {}).get("synthesis_stage")
    if rule_state.get("stage") != expected_stage:
        errors.append(
            f"evidence stage mismatch: {rule_state.get('stage')!r} != {expected_stage!r}"
        )

    minimum_repositories = int(
        proposal.get("evidence_requirements", {}).get("minimum_repositories", 0)
    )
    minimum_candidates = int(
        proposal.get("evidence_requirements", {}).get(
            "minimum_validated_candidates", 0
        )
    )
    if int(rule_state.get("repository_count", 0)) < minimum_repositories:
        errors.append("insufficient independent repository evidence")
    if int(rule_state.get("candidate_count", 0)) < minimum_candidates:
        errors.append("insufficient validated candidate evidence")

    applicability = proposal.get("applicability", {}) or {}
    required_true = (
        "same_function",
        "return_literals_must_be_exact_booleans",
        "terminal_returns_must_be_opposite",
        "condition_evaluated_once_before_and_after",
        "condition_must_be_syntactically_boolean_proven",
    )
    for key in required_true:
        if applicability.get(key) is not True:
            errors.append(f"applicability.{key} must be true")

    if applicability.get("logical_expression_direct_return") is not False:
        errors.append("logical-expression direct return must remain excluded")
    if applicability.get("await_or_yield_in_condition") is not False:
        errors.append("await/yield conditions must remain excluded")
    if applicability.get("comments_inside_rewrite_span") != "REJECT":
        errors.append("internal-comment rewrite span must fail closed")
    if applicability.get("binding_introduction_allowed") is not False:
        errors.append("proposal must not introduce bindings")
    if applicability.get("side_effect_reordering_allowed") is not False:
        errors.append("proposal must not reorder side effects")

    allowed_binary = set(applicability.get("allowed_boolean_binary_operators", []))
    required_binary = {"===", "!==", "==", "!=", "<", ">", "<=", ">=", "in", "instanceof"}
    if allowed_binary != required_binary:
        errors.append("boolean binary operator allowlist drift")

    allowed_unary = set(applicability.get("allowed_boolean_unary_operators", []))
    if allowed_unary != {"!"}:
        errors.append("boolean unary operator allowlist drift")

    transformations = proposal.get("transformations", {}) or {}
    positive = transformations.get("positive", {}) or {}
    inverse = transformations.get("inverse", {}) or {}
    complement = transformations.get("comparison_operator_complement_folding", {}) or {}

    if positive.get("after") != "return C;":
        errors.append("positive transformation must be direct boolean return")
    if inverse.get("after") != "return !(C);":
        errors.append("inverse transformation must remain conservative negation")
    if positive.get("requires_boolean_condition_proof") is not True:
        errors.append("positive transformation requires boolean-condition proof")
    if inverse.get("requires_boolean_condition_proof") is not True:
        errors.append("inverse transformation requires boolean-condition proof")
    if complement.get("included") is not False:
        errors.append("comparison operator complement folding must stay out of v1")

    preservation = proposal.get("source_preservation", {}) or {}
    for key in (
        "preserve_semicolon_style",
        "preserve_line_ending_style",
        "preserve_outer_indentation",
        "reject_if_internal_comments_would_move_or_drop",
        "rewrite_span_must_be_exact_and_single_site",
    ):
        if preservation.get(key) is not True:
            errors.append(f"source_preservation.{key} must be true")

    validation = proposal.get("validation_contract", {}) or {}
    for key in (
        "dry_run_first",
        "parse_after_rewrite",
        "changed_path_scope_one_expected_file",
        "git_diff_check",
        "focused_target_native_test_before",
        "focused_target_native_test_after",
        "target_typecheck_or_type_tests_after",
        "candidate_specific_authorization_required_for_mutation",
    ):
        if validation.get(key) is not True:
            errors.append(f"validation_contract.{key} must be true")

    authority = proposal.get("authority", {}) or {}
    if authority.get("proposal_only") is not True:
        errors.append("proposal_only must be true")
    for key in (
        "generic_rewrite_authority_granted",
        "automatic_patch_authority_granted",
        "upstream_mutation_authorized",
        "global_behavioral_equivalence_proven",
        "truth_commit",
    ):
        if authority.get(key) is not False:
            errors.append(f"authority.{key} must be false")

    if proposal.get("next_gate") != "DRY_RUN_REWRITE_PLANNER":
        errors.append("next gate must be DRY_RUN_REWRITE_PLANNER")

    return {
        "schema_version": "plw-js-ts-v2-boolean-guard-rewrite-proposal-review-v1",
        "status": "BOOLEAN_GUARD_REWRITE_PROPOSAL_REVIEW_READY" if not errors else "INVALID",
        "rule": RULE,
        "evidence": {
            "stage": rule_state.get("stage"),
            "repository_count": rule_state.get("repository_count"),
            "repositories": rule_state.get("repositories", []),
            "candidate_count": rule_state.get("candidate_count"),
            "candidate_ids": rule_state.get("candidate_ids", []),
        },
        "proposal": {
            "stage": proposal.get("proposal_stage"),
            "next_gate": proposal.get("next_gate"),
            "positive_rewrite": positive.get("after"),
            "inverse_rewrite": inverse.get("after"),
            "comparison_operator_complement_folding": complement.get("included"),
        },
        "authority": {
            "review_ready_only": True,
            "generic_rewrite_authority_granted": False,
            "automatic_patch_authority_granted": False,
            "upstream_mutation_authorized": False,
            "truth_commit": False,
        },
        "errors": errors,
    }


def render_markdown(report: Dict[str, Any]) -> str:
    evidence = report["evidence"]
    proposal = report["proposal"]
    lines = [
        "# JS/TS boolean-guard reusable-rewrite proposal review",
        "",
        f"Status: **{report['status']}**",
        "",
        f"Rule: **{report['rule']}**",
        f"Independent repositories: **{evidence['repository_count']}**",
        f"Validated candidates: **{evidence['candidate_count']}**",
        "",
        "## Proposed bounded transformations",
        "",
        f"- positive: `{proposal['positive_rewrite']}`",
        f"- inverse: `{proposal['inverse_rewrite']}`",
        f"- comparison-operator complement folding included: **{proposal['comparison_operator_complement_folding']}**",
        "",
        "## Authority boundary",
        "",
        "proposal review ready != reusable rewriter implemented",
        "",
        "proposal review ready != generic mutation authority",
        "",
        "Next gate: DRY_RUN_REWRITE_PLANNER",
    ]
    if report["errors"]:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in report["errors"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True)
    parser.add_argument("--proposal", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()

    report = review(load(Path(args.index)), load(Path(args.proposal)))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    Path(args.summary).write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "rule": report["rule"],
                "repositories": report["evidence"]["repository_count"],
                "candidates": report["evidence"]["candidate_count"],
                "errors": report["errors"],
            },
            sort_keys=True,
        )
    )
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
