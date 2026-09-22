#!/usr/bin/env python3
"""Review the JS/TS boolean-guard mutation-boundary contract.

This checker is non-effectful. It verifies that a future mutation adapter would
remain candidate-specific, explicitly authorized, disposable-worktree-only,
fail-closed, validated, and evidence-producing. It grants no source-write
authority itself.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping

RULE = "js_boolean_guard_return"
EXPECTED_SCHEMA = "plw-js-ts-v2-mutation-boundary-contract-v1"
EXPECTED_PROMOTION_STATUS = "REUSABLE_READ_ONLY_PLANNER_READY"
EXPECTED_NEXT_GATE = "TEMP_WORKTREE_MUTATION_ADAPTER_REFERENCE"

REQUIRED_STATES = [
    "READ_ONLY_PLAN_READY",
    "PREFLIGHT_VALIDATED",
    "MUTATION_AUTHORIZED",
    "TEMP_WORKTREE_APPLIED",
    "POSTCONDITIONS_VALIDATED",
    "EXPERIMENT_EVIDENCE_ACCEPTED",
]

REQUIRED_RECEIPT_BINDINGS = {
    "candidate_id",
    "target_repository",
    "target_revision",
    "source_path",
    "before_source_sha256",
    "planned_source_sha256",
    "plan_digest",
    "preflight_evidence_digest",
    "postcondition_validation_spec_digest",
}

REQUIRED_TERMINAL_STATES = {
    "success": "EXPERIMENT_EVIDENCE_ACCEPTED",
    "rejected_before_write": "MUTATION_BOUNDARY_REJECTED",
    "failed_after_write_contained": "MUTATION_FAILED_WORKTREE_DISCARDED",
    "containment_failure": "MUTATION_BOUNDARY_CONTAINMENT_FAILED",
}


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _require_true(errors: List[str], obj: Mapping[str, Any], key: str, scope: str) -> None:
    if obj.get(key) is not True:
        errors.append(f"{scope}.{key} must be true")


def _require_false(errors: List[str], obj: Mapping[str, Any], key: str, scope: str) -> None:
    if obj.get(key) is not False:
        errors.append(f"{scope}.{key} must be false")


def review_contract(contract: Mapping[str, Any], promotion: Mapping[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []

    if contract.get("schema_version") != EXPECTED_SCHEMA:
        errors.append("unexpected contract schema")
    if contract.get("rule") != RULE:
        errors.append("contract rule mismatch")
    if list(contract.get("state_machine", []) or []) != REQUIRED_STATES:
        errors.append("state machine must preserve the reviewed transition order")

    prerequisite = contract.get("prerequisite", {}) or {}
    if prerequisite.get("planner_promotion_status") != EXPECTED_PROMOTION_STATUS:
        errors.append("contract prerequisite promotion status mismatch")
    if not isinstance(prerequisite.get("planner_promotion_workflow_run_id"), int):
        errors.append("planner promotion workflow run id required")
    if not str(prerequisite.get("planner_promotion_artifact_name", "")):
        errors.append("planner promotion artifact name required")
    if not str(prerequisite.get("planner_promotion_artifact_digest", "")).startswith("sha256:"):
        errors.append("planner promotion artifact digest required")

    if promotion.get("status") != EXPECTED_PROMOTION_STATUS:
        errors.append("live promotion report is not reusable-read-only ready")
    if promotion.get("rule") != RULE:
        errors.append("live promotion report rule mismatch")
    capability = promotion.get("capability", {}) or {}
    _require_true(
        errors,
        capability,
        "reusable_read_only_planning_authority_granted",
        "promotion.capability",
    )
    _require_true(errors, capability, "diff_generation_allowed", "promotion.capability")
    _require_false(errors, capability, "target_source_write_allowed", "promotion.capability")
    promotion_authority = promotion.get("authority", {}) or {}
    for key in (
        "source_mutation_allowed",
        "generic_mutation_authority_granted",
        "automatic_patch_authority_granted",
        "upstream_mutation_authorized",
        "global_behavioral_equivalence_proven",
        "truth_commit",
    ):
        _require_false(errors, promotion_authority, key, "promotion.authority")

    plan = contract.get("plan_binding", {}) or {}
    if plan.get("required_plan_schema") != "plw-js-ts-v2-boolean-guard-dry-run-plan-v1":
        errors.append("plan binding schema mismatch")
    if plan.get("required_plan_status") != "DRY_RUN_REWRITE_PLAN_READY":
        errors.append("plan binding status mismatch")
    if plan.get("required_candidate_kind") != RULE:
        errors.append("plan binding candidate kind mismatch")
    for key in (
        "candidate_id_exact_match",
        "target_repository_exact_match",
        "target_revision_exact_match",
        "source_path_exact_match",
        "before_source_sha256_exact_match",
        "planned_source_sha256_required",
        "planned_diff_required",
        "plan_digest_required",
        "planner_source_integrity_must_show_no_mutation",
    ):
        _require_true(errors, plan, key, "plan_binding")

    preflight = contract.get("preflight", {}) or {}
    for key in (
        "clean_disposable_checkout_required",
        "pinned_revision_required",
        "upstream_push_credentials_disabled",
        "target_source_sha256_must_match_plan_before_sha256",
        "candidate_span_must_still_match_exactly_once",
        "focused_target_native_validation_before_mutation",
        "baseline_validation_must_pass",
        "preflight_evidence_digest_required",
        "postcondition_validation_spec_required_before_mutation",
        "postcondition_validation_spec_digest_required",
        "preflight_is_read_only",
    ):
        _require_true(errors, preflight, key, "preflight")

    authorization = contract.get("authorization", {}) or {}
    if authorization.get("authorization_scope") != "ONE_CANDIDATE_ONE_TARGET_ONE_PLAN":
        errors.append("authorization scope must be one candidate / one target / one plan")
    for key in (
        "explicit_literal_authorization_required",
        "authorization_receipt_required",
        "wildcard_authorization_forbidden",
        "rule_wide_authorization_forbidden",
        "authorization_reuse_forbidden",
        "authorization_does_not_imply_behavioral_equivalence",
        "authorization_issuer_must_be_external_to_planner",
        "planner_self_authorization_forbidden",
    ):
        _require_true(errors, authorization, key, "authorization")
    bindings = set(authorization.get("receipt_must_bind", []) or [])
    missing_bindings = sorted(REQUIRED_RECEIPT_BINDINGS - bindings)
    if missing_bindings:
        errors.append(f"authorization receipt bindings missing: {missing_bindings}")

    execution = contract.get("execution", {}) or {}
    if execution.get("environment") != "DISPOSABLE_TEMP_WORKTREE_ONLY":
        errors.append("execution environment must be disposable temp worktree only")
    if execution.get("source_write_scope") != "ONE_EXPECTED_FILE":
        errors.append("source write scope must be one expected file")
    for key in (
        "apply_exact_planned_replacement_only",
        "before_source_sha256_recheck_immediately_before_write",
        "candidate_span_recheck_immediately_before_write",
        "actual_after_sha256_must_equal_planned_source_sha256",
        "actual_diff_must_equal_planned_diff",
        "git_diff_check_required",
        "unexpected_changed_paths_fail_closed",
        "unexpected_untracked_target_files_fail_closed",
        "commit_creation_forbidden",
        "push_forbidden",
        "pull_request_creation_forbidden",
        "primary_worktree_forbidden",
        "evidence_output_outside_target_root",
    ):
        _require_true(errors, execution, key, "execution")

    postconditions = contract.get("postconditions", {}) or {}
    if (
        postconditions.get("validation_spec_schema")
        != "plw-js-ts-v2-postcondition-validation-spec-v1"
    ):
        errors.append("postcondition validation spec schema mismatch")
    for key in (
        "parse_after_rewrite_required",
        "same_focused_target_native_validation_after_mutation",
        "target_typecheck_or_type_tests_after_mutation",
        "changed_path_scope_must_equal_one_expected_file",
        "actual_after_sha256_must_equal_planned_source_sha256",
        "actual_diff_must_equal_planned_diff",
        "all_required_postconditions_must_pass",
        "passing_postconditions_do_not_prove_global_equivalence",
        "validation_spec_must_be_bound_before_mutation",
        "validation_spec_commands_are_argv_no_shell",
        "focused_post_command_must_equal_baseline_command",
    ):
        _require_true(errors, postconditions, key, "postconditions")

    failure = contract.get("failure_policy", {}) or {}
    for key in (
        "fail_closed",
        "no_partial_success_promotion",
        "discard_disposable_worktree_on_failure",
        "authorization_receipt_consumed_on_execution_attempt",
        "fresh_plan_and_authorization_required_for_retry",
        "upstream_repository_must_remain_untouched",
        "rollback_or_disposal_verification_required",
    ):
        _require_true(errors, failure, key, "failure_policy")
    if failure.get("rollback_strategy") != "DISCARD_DISPOSABLE_WORKTREE":
        errors.append("rollback strategy must discard the disposable worktree")

    evidence = contract.get("evidence", {}) or {}
    for key in (
        "record_target_repository_and_revision",
        "record_candidate_id",
        "record_plan_digest",
        "record_authorization_receipt_digest",
        "record_preflight_evidence_digest",
        "record_postcondition_validation_spec_digest",
        "record_before_and_after_source_sha256",
        "record_planned_and_actual_diff_digest",
        "record_validation_commands_and_results",
        "record_changed_path_scope",
        "record_worktree_disposal_status",
        "append_only_experiment_receipt",
        "evidence_output_outside_target_root",
        "record_authorization_consumption_status",
        "record_failure_or_rollback_status",
    ):
        _require_true(errors, evidence, key, "evidence")

    terminal_states = contract.get("terminal_states", {}) or {}
    if terminal_states != REQUIRED_TERMINAL_STATES:
        errors.append("terminal states do not match reviewed containment contract")

    authority = contract.get("authority", {}) or {}
    _require_true(errors, authority, "contract_review_only", "authority")
    for key in (
        "generic_mutation_adapter_implemented",
        "source_mutation_authority_granted_by_contract",
        "automatic_patch_authority_granted",
        "upstream_mutation_authorized",
        "global_behavioral_equivalence_proven",
        "truth_commit",
    ):
        _require_false(errors, authority, key, "authority")

    if contract.get("next_gate") != EXPECTED_NEXT_GATE:
        errors.append("unexpected next gate")

    status = (
        "MUTATION_BOUNDARY_CONTRACT_REVIEW_PASSED"
        if not errors
        else "MUTATION_BOUNDARY_CONTRACT_REVIEW_REJECTED"
    )
    return {
        "schema_version": "plw-js-ts-v2-mutation-boundary-contract-review-v1",
        "status": status,
        "rule": RULE,
        "prerequisite": {
            "planner_status": promotion.get("status"),
            "reusable_read_only_planning": capability.get(
                "reusable_read_only_planning_authority_granted"
            ),
            "target_source_write_allowed": capability.get("target_source_write_allowed"),
        },
        "boundary": {
            "authorization_is_external_and_candidate_specific": (
                authorization.get("authorization_issuer_must_be_external_to_planner") is True
                and authorization.get("planner_self_authorization_forbidden") is True
                and authorization.get("authorization_scope")
                == "ONE_CANDIDATE_ONE_TARGET_ONE_PLAN"
            ),
            "execution_environment": execution.get("environment"),
            "exact_plan_application_only": execution.get(
                "apply_exact_planned_replacement_only"
            ),
            "primary_worktree_forbidden": execution.get("primary_worktree_forbidden"),
            "rollback_strategy": failure.get("rollback_strategy"),
            "postconditions_required": postconditions.get(
                "all_required_postconditions_must_pass"
            ),
            "append_only_receipt_required": evidence.get(
                "append_only_experiment_receipt"
            ),
        },
        "authority": {
            "contract_review_only": True,
            "effectful_adapter_implemented": False,
            "source_mutation_authority_granted": False,
            "automatic_patch_authority_granted": False,
            "upstream_mutation_authorized": False,
            "global_behavioral_equivalence_proven": False,
            "truth_commit": False,
        },
        "errors": errors,
        "next_gate": EXPECTED_NEXT_GATE,
    }


def render_summary(report: Mapping[str, Any]) -> str:
    lines = [
        "# JS/TS boolean-guard mutation boundary contract review",
        "",
        f"Status: **{report['status']}**",
        "",
        f"Rule: **{report['rule']}**",
        "",
        "Boundary:",
        "",
        f"- external candidate-specific authorization: {report['boundary']['authorization_is_external_and_candidate_specific']}",
        f"- execution environment: {report['boundary']['execution_environment']}",
        f"- exact plan application only: {report['boundary']['exact_plan_application_only']}",
        f"- primary worktree forbidden: {report['boundary']['primary_worktree_forbidden']}",
        f"- rollback strategy: {report['boundary']['rollback_strategy']}",
        f"- postconditions required: {report['boundary']['postconditions_required']}",
        f"- append-only receipt required: {report['boundary']['append_only_receipt_required']}",
        "",
        "Authority:",
        "",
        "contract review passed != source mutation authority",
        "",
        f"Next gate: {report['next_gate']}",
    ]
    if report["errors"]:
        lines.extend(["", "Errors:", ""])
        lines.extend(f"- {error}" for error in report["errors"])
    return "\n".join(lines) + "\n"


def run_self_check(contract: Mapping[str, Any], promotion: Mapping[str, Any]) -> Dict[str, Any]:
    cases = []

    cases.append(("valid_contract", copy.deepcopy(contract), copy.deepcopy(promotion)))

    c = copy.deepcopy(contract)
    c["authorization"]["planner_self_authorization_forbidden"] = False
    cases.append(("planner_self_authorization", c, copy.deepcopy(promotion)))

    c = copy.deepcopy(contract)
    c["execution"]["primary_worktree_forbidden"] = False
    cases.append(("primary_worktree", c, copy.deepcopy(promotion)))

    c = copy.deepcopy(contract)
    c["authorization"]["receipt_must_bind"] = [
        item for item in c["authorization"]["receipt_must_bind"] if item != "plan_digest"
    ]
    cases.append(("missing_plan_digest_binding", c, copy.deepcopy(promotion)))

    c = copy.deepcopy(contract)
    c["authorization"]["receipt_must_bind"] = [
        item
        for item in c["authorization"]["receipt_must_bind"]
        if item != "postcondition_validation_spec_digest"
    ]
    cases.append(
        ("missing_postcondition_spec_binding", c, copy.deepcopy(promotion))
    )

    c = copy.deepcopy(contract)
    c["failure_policy"]["rollback_strategy"] = "KEEP_DIRTY_WORKTREE"
    cases.append(("unsafe_rollback", c, copy.deepcopy(promotion)))

    c = copy.deepcopy(contract)
    c["authority"]["upstream_mutation_authorized"] = True
    cases.append(("upstream_authority", c, copy.deepcopy(promotion)))

    p = copy.deepcopy(promotion)
    p["capability"]["target_source_write_allowed"] = True
    cases.append(("promotion_write_authority", copy.deepcopy(contract), p))

    results = []
    errors = []
    for name, case_contract, case_promotion in cases:
        result = review_contract(case_contract, case_promotion)
        expected_pass = name == "valid_contract"
        actual_pass = result["status"] == "MUTATION_BOUNDARY_CONTRACT_REVIEW_PASSED"
        ok = actual_pass == expected_pass
        results.append(
            {
                "case": name,
                "expected_pass": expected_pass,
                "actual_pass": actual_pass,
                "ok": ok,
            }
        )
        if not ok:
            errors.append(name)

    return {
        "status": "MUTATION_BOUNDARY_CONTRACT_SELF_CHECK_PASSED" if not errors else "FAILED",
        "cases": results,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True)
    parser.add_argument("--promotion-report", required=True)
    parser.add_argument("--output")
    parser.add_argument("--summary")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()

    contract = _load(Path(args.contract))
    promotion = _load(Path(args.promotion_report))

    if args.self_check:
        check = run_self_check(contract, promotion)
        print(json.dumps(check, indent=2, sort_keys=True))
        return 0 if not check["errors"] else 1

    if not args.output or not args.summary:
        parser.error("--output and --summary are required unless --self-check is used")

    report = review_contract(contract, promotion)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    Path(args.summary).write_text(render_summary(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "errors": report["errors"],
                "next_gate": report["next_gate"],
            },
            sort_keys=True,
        )
    )
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
