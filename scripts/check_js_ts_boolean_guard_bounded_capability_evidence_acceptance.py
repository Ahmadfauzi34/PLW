#!/usr/bin/env python3
"""Exercise the READY bounded capability through the existing evidence acceptor.

This is an integration/audit harness, not a new evidence acceptor. It composes
already-qualified boundaries:

  bounded capability -> postconditions -> exact receipt issuance -> existing
  TEMP_WORKTREE_EXPERIMENT_EVIDENCE_ACCEPTANCE_REFERENCE

All ledgers created by this checker are ephemeral fixture state. A passing run
does not append evidence to any retained/global evidence ledger and grants no
mutation, upstream, promotion, equivalence, or truth authority.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

from accept_js_ts_boolean_guard_temp_worktree_experiment_evidence import (
    AcceptanceError,
    accept_evidence,
)
from check_js_ts_boolean_guard_bounded_capability import (
    apply_fixture,
    build_fixture,
    digest_text,
    rebind_preflight_and_authorization,
    write_json,
)
from issue_js_ts_boolean_guard_bounded_capability_postconditions import (
    issue_bounded_capability_postconditions,
)


SUCCESS_ISSUANCE = "BOUNDED_CAPABILITY_POSTCONDITION_RECEIPT_ISSUED"
ACCEPTED = "EXPERIMENT_EVIDENCE_ACCEPTED"
RECOVERED = "EXPERIMENT_EVIDENCE_ACCEPTANCE_RECOVERED"


def _paths(fixture: Dict[str, Any]) -> Dict[str, Path]:
    evidence = fixture["evidence"]
    return {
        "capability": evidence / "capability_receipt.json",
        "primitive": evidence / "primitive.json",
        "validation": evidence / "validation.json",
        "issuance": evidence / "issuance.jsonl",
        "acceptance": evidence / "acceptance.jsonl",
    }


def _apply_and_issue(
    fixture: Dict[str, Any],
) -> tuple[Dict[str, Path], Dict[str, Any]]:
    paths = _paths(fixture)
    capability = apply_fixture(fixture)
    write_json(paths["capability"], capability)
    issuance = issue_bounded_capability_postconditions(
        root=fixture["target"],
        disposable_parent=fixture["base"],
        capability_contract_path=fixture["contract_path"],
        capability_receipt_path=paths["capability"],
        plan_path=fixture["plan_path"],
        preflight_path=fixture["preflight_path"],
        authorization_path=fixture["authorization_path"],
        validation_spec_path=fixture["spec_path"],
        primitive_materialization_path=paths["primitive"],
        validation_receipt_path=paths["validation"],
        issuance_ledger_path=paths["issuance"],
        timeout_seconds=30,
    )
    return paths, issuance


def _accept(fixture: Dict[str, Any], paths: Dict[str, Path]) -> Dict[str, Any]:
    return accept_evidence(
        plan_path=fixture["plan_path"],
        preflight_path=fixture["preflight_path"],
        authorization_path=fixture["authorization_path"],
        spec_path=fixture["spec_path"],
        mutation_path=paths["primitive"],
        validation_path=paths["validation"],
        issuance_ledger_path=paths["issuance"],
        acceptance_ledger_path=paths["acceptance"],
    )


def _ledger_records(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _positive(
    name: str,
    *,
    extension: str,
    condition: str,
    inverse: bool,
    semicolon: bool,
) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"plw_cap_accept_{name}_") as temp:
        fixture = build_fixture(
            Path(temp),
            extension=extension,
            condition=condition,
            inverse=inverse,
            semicolon=semicolon,
        )
        paths, issuance = _apply_and_issue(fixture)
        accepted = _accept(fixture, paths)
        replay = _accept(fixture, paths)

        authority = accepted.get("authority", {}) or {}
        ok = (
            issuance.get("status") == SUCCESS_ISSUANCE
            and accepted.get("status") == ACCEPTED
            and accepted.get("acceptance_ledger_appended") is True
            and accepted.get("reran_validation") is False
            and accepted.get("inspected_disposed_worktree") is False
            and replay.get("status") == RECOVERED
            and replay.get("acceptance_ledger_appended") is False
            and _ledger_records(paths["issuance"]) == 1
            and _ledger_records(paths["acceptance"]) == 1
            and not fixture["target"].exists()
            and authority.get("evidence_acceptance_only") is True
            and authority.get("source_mutation_allowed") is False
            and authority.get("automatic_patch_authority_granted") is False
            and authority.get("generic_mutation_authority_granted") is False
            and authority.get("upstream_mutation_authorized") is False
            and authority.get("global_behavioral_equivalence_proven") is False
            and authority.get("truth_commit") is False
        )
        return {
            "case": name,
            "expected": "ACCEPT_THEN_RECOVER",
            "ok": ok,
            "issuance_status": issuance.get("status"),
            "acceptance_status": accepted.get("status"),
            "replay_status": replay.get("status"),
            "issuance_records": _ledger_records(paths["issuance"]),
            "acceptance_records": _ledger_records(paths["acceptance"]),
            "worktree_disposed": not fixture["target"].exists(),
            "truth_commit": authority.get("truth_commit"),
        }


def _expect_acceptance_rejection(
    *,
    name: str,
    fixture: Dict[str, Any],
    paths: Dict[str, Path],
    expected_fragment: str,
) -> Dict[str, Any]:
    try:
        _accept(fixture, paths)
    except (AcceptanceError, json.JSONDecodeError) as exc:
        message = str(exc)
        ok = (
            expected_fragment in message
            and _ledger_records(paths["acceptance"]) == 0
            and not fixture["target"].exists()
        )
        return {
            "case": name,
            "expected": "REJECT_NO_ACCEPTANCE",
            "ok": ok,
            "error": message,
            "acceptance_records": _ledger_records(paths["acceptance"]),
            "worktree_disposed": not fixture["target"].exists(),
        }
    return {
        "case": name,
        "expected": "REJECT_NO_ACCEPTANCE",
        "ok": False,
        "error": "acceptor unexpectedly accepted",
        "acceptance_records": _ledger_records(paths["acceptance"]),
        "worktree_disposed": not fixture["target"].exists(),
    }


def _validation_tamper_rejected() -> Dict[str, Any]:
    name = "validation_receipt_tamper_after_issuance_rejected"
    with tempfile.TemporaryDirectory(prefix=f"plw_cap_accept_{name}_") as temp:
        fixture = build_fixture(
            Path(temp),
            extension=".js",
            condition='value.kind === "ok"',
            inverse=False,
            semicolon=True,
        )
        paths, issuance = _apply_and_issue(fixture)
        if issuance.get("status") != SUCCESS_ISSUANCE:
            return {"case": name, "expected": "REJECT_NO_ACCEPTANCE", "ok": False}
        payload = json.loads(paths["validation"].read_text(encoding="utf-8"))
        payload["validation"]["commands"][0]["stdout_sha256"] = digest_text("tampered")
        write_json(paths["validation"], payload)
        return _expect_acceptance_rejection(
            name=name,
            fixture=fixture,
            paths=paths,
            expected_fragment="exact validation receipt is not uniquely sealed",
        )


def _primitive_tamper_rejected() -> Dict[str, Any]:
    name = "primitive_receipt_tamper_after_issuance_rejected"
    with tempfile.TemporaryDirectory(prefix=f"plw_cap_accept_{name}_") as temp:
        fixture = build_fixture(
            Path(temp),
            extension=".ts",
            condition="value.kind === 'arguments'",
            inverse=True,
            semicolon=False,
        )
        paths, issuance = _apply_and_issue(fixture)
        if issuance.get("status") != SUCCESS_ISSUANCE:
            return {"case": name, "expected": "REJECT_NO_ACCEPTANCE", "ok": False}
        payload = json.loads(paths["primitive"].read_text(encoding="utf-8"))
        payload["mutation"]["actual_after_source_sha256"] = digest_text("tampered")
        write_json(paths["primitive"], payload)
        return _expect_acceptance_rejection(
            name=name,
            fixture=fixture,
            paths=paths,
            expected_fragment="validation lineage digest mismatch: mutation_receipt_digest",
        )


def _failed_postconditions_not_accepted() -> Dict[str, Any]:
    name = "failed_postconditions_sealed_but_not_accepted"
    with tempfile.TemporaryDirectory(prefix=f"plw_cap_accept_{name}_") as temp:
        fixture = build_fixture(
            Path(temp),
            extension=".js",
            condition='value.kind === "ok"',
            inverse=False,
            semicolon=True,
        )
        command = [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                "s=Path('src/example.js').read_text(); "
                "raise SystemExit(9 if 'return value.kind ===' in s else 0)"
            ),
        ]
        spec = json.loads(fixture["spec_path"].read_text(encoding="utf-8"))
        spec["commands"]["focused_target_native_after"] = command
        write_json(fixture["spec_path"], spec)
        preflight = json.loads(fixture["preflight_path"].read_text(encoding="utf-8"))
        preflight["baseline_validation"] = {"command": command, "exit_code": 0}
        preflight["postcondition_baseline_validation"]["focused_target_native_after"] = {
            "command": command,
            "exit_code": 0,
            "stdout_sha256": digest_text(""),
            "stderr_sha256": digest_text(""),
        }
        write_json(fixture["preflight_path"], preflight)
        rebind_preflight_and_authorization(fixture)

        paths, issuance = _apply_and_issue(fixture)
        if issuance.get("status") != "BOUNDED_CAPABILITY_POSTCONDITION_FAILURE_RECEIPT_ISSUED":
            return {
                "case": name,
                "expected": "FAILURE_SEALED_REJECT_ACCEPTANCE",
                "ok": False,
                "issuance_status": issuance.get("status"),
            }
        rejected = _expect_acceptance_rejection(
            name=name,
            fixture=fixture,
            paths=paths,
            expected_fragment="validation receipt is not POSTCONDITIONS_VALIDATED",
        )
        rejected["issuance_status"] = issuance.get("status")
        rejected["issuance_records"] = _ledger_records(paths["issuance"])
        return rejected


def _broken_acceptance_chain_rejected() -> Dict[str, Any]:
    name = "broken_acceptance_chain_rejected"
    with tempfile.TemporaryDirectory(prefix=f"plw_cap_accept_{name}_") as temp:
        fixture = build_fixture(
            Path(temp),
            extension=".js",
            condition='value.kind === "ok"',
            inverse=False,
            semicolon=True,
        )
        paths, issuance = _apply_and_issue(fixture)
        if issuance.get("status") != SUCCESS_ISSUANCE:
            return {"case": name, "expected": "REJECT_BROKEN_CHAIN", "ok": False}
        paths["acceptance"].write_text(
            json.dumps(
                {
                    "schema_version": "plw-js-ts-v2-experiment-evidence-acceptance-v1",
                    "sequence": 1,
                    "previous_record_digest": None,
                    "record_digest": "sha256:broken",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        try:
            _accept(fixture, paths)
        except (AcceptanceError, json.JSONDecodeError) as exc:
            message = str(exc)
            return {
                "case": name,
                "expected": "REJECT_BROKEN_CHAIN",
                "ok": (
                    "acceptance ledger record digest mismatch" in message
                    and _ledger_records(paths["acceptance"]) == 1
                    and not fixture["target"].exists()
                ),
                "error": message,
                "acceptance_records": _ledger_records(paths["acceptance"]),
                "worktree_disposed": not fixture["target"].exists(),
            }
        return {
            "case": name,
            "expected": "REJECT_BROKEN_CHAIN",
            "ok": False,
            "error": "acceptor unexpectedly accepted broken ledger",
        }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()

    cases = [
        _positive(
            "positive_js_capability_evidence_acceptance",
            extension=".js",
            condition='value.kind === "ok"',
            inverse=False,
            semicolon=True,
        ),
        _positive(
            "inverse_ts_capability_evidence_acceptance",
            extension=".ts",
            condition="value.kind === 'arguments'",
            inverse=True,
            semicolon=False,
        ),
        _validation_tamper_rejected(),
        _primitive_tamper_rejected(),
        _failed_postconditions_not_accepted(),
        _broken_acceptance_chain_rejected(),
    ]
    failed = [case["case"] for case in cases if not case.get("ok")]
    report = {
        "schema_version": "plw-js-ts-v2-bounded-capability-evidence-acceptance-integration-regression-v1",
        "status": (
            "BOUNDED_CAPABILITY_EVIDENCE_ACCEPTANCE_INTEGRATION_REGRESSION_PASSED"
            if not failed
            else "BOUNDED_CAPABILITY_EVIDENCE_ACCEPTANCE_INTEGRATION_REGRESSION_FAILED"
        ),
        "case_count": len(cases),
        "passed_case_count": sum(1 for case in cases if case.get("ok")),
        "failed_cases": failed,
        "cases": cases,
        "retained_global_evidence_ledger_modified": False,
        "authority": {
            "integration_regression_only": True,
            "interactive_audit_authority": False,
            "existing_evidence_acceptor_reused": True,
            "new_evidence_acceptor_created": False,
            "source_mutation_authority_granted": False,
            "automatic_patch_authority_granted": False,
            "generic_mutation_authority_granted": False,
            "primary_worktree_mutation_authorized": False,
            "commit_creation_authorized": False,
            "push_authorized": False,
            "pull_request_creation_authorized": False,
            "upstream_mutation_authorized": False,
            "global_behavioral_equivalence_proven": False,
            "stable_promotion_authorized": False,
            "truth_commit": False,
        },
        "next_gate_on_success": "BOUNDED_MUTATION_EVIDENCE_SYNTHESIS_REVIEW",
    }

    output = Path(args.output)
    summary = Path(args.summary)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    lines = [
        "# Bounded capability evidence-acceptance integration regression",
        "",
        f"Status: **{report['status']}**",
        "",
        f"Cases: **{report['passed_case_count']}/{report['case_count']}**",
        "",
        "| Case | Expected | Result |",
        "| --- | --- | --- |",
    ]
    for case in cases:
        lines.append(
            f"| {case['case']} | {case['expected']} | "
            f"{'PASS' if case.get('ok') else 'FAIL'} |"
        )
    lines.extend(
        [
            "",
            "The acceptance ledger is fixture-local and ephemeral; no retained/global evidence is appended.",
            "",
            "Regression only. Direct exact-head execution remains promotion authority.",
        ]
    )
    summary.write_text("\n".join(lines) + "\n")

    print(
        json.dumps(
            {
                "status": report["status"],
                "passed": report["passed_case_count"],
                "total": report["case_count"],
                "failed": failed,
                "retained_global_evidence_ledger_modified": False,
                "truth_commit": False,
            },
            sort_keys=True,
        )
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
