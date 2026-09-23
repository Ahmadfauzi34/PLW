#!/usr/bin/env python3
"""Regression checks for the bounded capability postcondition issuance bridge."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

from check_js_ts_boolean_guard_bounded_capability import (
    apply_fixture,
    build_fixture,
    digest_file,
    digest_text,
    rebind_preflight_and_authorization,
    write_json,
)
from issue_js_ts_boolean_guard_bounded_capability_postconditions import (
    issue_bounded_capability_postconditions,
)
from validate_js_ts_boolean_guard_temp_worktree_postconditions import (
    _read_issuance_ledger,
    _seal_validation_receipt,
)


def _apply_capability(fixture: Dict[str, Any]) -> Path:
    receipt = apply_fixture(fixture)
    path = fixture["evidence"] / "capability_receipt.json"
    write_json(path, receipt)
    return path


def _issue(fixture: Dict[str, Any], capability_path: Path) -> Dict[str, Any]:
    return issue_bounded_capability_postconditions(
        root=fixture["target"],
        disposable_parent=fixture["base"],
        capability_contract_path=fixture["contract_path"],
        capability_receipt_path=capability_path,
        plan_path=fixture["plan_path"],
        preflight_path=fixture["preflight_path"],
        authorization_path=fixture["authorization_path"],
        validation_spec_path=fixture["spec_path"],
        primitive_materialization_path=fixture["evidence"] / "primitive.json",
        validation_receipt_path=fixture["evidence"] / "validation.json",
        issuance_ledger_path=fixture["evidence"] / "issuance.jsonl",
        timeout_seconds=30,
    )


def _positive(
    name: str,
    *,
    extension: str,
    condition: str,
    inverse: bool,
    semicolon: bool,
) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"plw_issue_{name}_") as temp:
        fixture = build_fixture(
            Path(temp),
            extension=extension,
            condition=condition,
            inverse=inverse,
            semicolon=semicolon,
        )
        capability_path = _apply_capability(fixture)
        result = _issue(fixture, capability_path)
        validation_path = fixture["evidence"] / "validation.json"
        ledger_path = fixture["evidence"] / "issuance.jsonl"
        ledger = _read_issuance_ledger(ledger_path)
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        validation_digest = digest_file(validation_path)

        replay = _seal_validation_receipt(
            ledger_path=ledger_path,
            receipt=validation,
            receipt_digest=validation_digest,
        )
        ledger_after = _read_issuance_ledger(ledger_path)

        ok = (
            result.get("status")
            == "BOUNDED_CAPABILITY_POSTCONDITION_RECEIPT_ISSUED"
            and result.get("validation_receipt_digest") == validation_digest
            and (result.get("postconditions", {}) or {}).get("validated") is True
            and (result.get("postconditions", {}) or {}).get(
                "evidence_acceptance_granted"
            )
            is False
            and len(ledger) == 1
            and ledger[0].get("validation_receipt_digest") == validation_digest
            and ledger[0].get("validation_status") == "POSTCONDITIONS_VALIDATED"
            and replay.get("status")
            == "POSTCONDITION_VALIDATION_RECEIPT_ISSUANCE_RECOVERED"
            and replay.get("appended") is False
            and len(ledger_after) == 1
            and (result.get("containment", {}) or {}).get("worktree_disposed")
            is True
            and not fixture["target"].exists()
            and (result.get("authority", {}) or {}).get("truth_commit") is False
        )
        return {
            "case": name,
            "expected": "ISSUED",
            "ok": ok,
            "status": result.get("status"),
            "issuance_status": (result.get("issuance", {}) or {}).get("status"),
            "issuance_replay_status": replay.get("status"),
            "issuance_records": len(ledger_after),
            "worktree_disposed": (result.get("containment", {}) or {}).get(
                "worktree_disposed"
            ),
        }


def _capability_tamper_rejected() -> Dict[str, Any]:
    name = "capability_receipt_tamper_no_issuance"
    with tempfile.TemporaryDirectory(prefix=f"plw_issue_{name}_") as temp:
        fixture = build_fixture(
            Path(temp),
            extension=".js",
            condition='value.kind === "ok"',
            inverse=False,
            semicolon=True,
        )
        capability_path = _apply_capability(fixture)
        payload = json.loads(capability_path.read_text(encoding="utf-8"))
        payload["capability_id"] = "other.capability"
        write_json(capability_path, payload)
        result = _issue(fixture, capability_path)
        ledger_path = fixture["evidence"] / "issuance.jsonl"
        validation_path = fixture["evidence"] / "validation.json"
        ok = (
            result.get("status") == "BOUNDED_CAPABILITY_POSTCONDITION_NOT_ISSUED"
            and not ledger_path.exists()
            and not validation_path.exists()
            and (result.get("containment", {}) or {}).get("worktree_disposed")
            is True
            and not fixture["target"].exists()
        )
        return {
            "case": name,
            "expected": "REJECT_NO_ISSUANCE",
            "ok": ok,
            "status": result.get("status"),
            "worktree_disposed": (result.get("containment", {}) or {}).get(
                "worktree_disposed"
            ),
        }


def _broken_issuance_chain_rejected() -> Dict[str, Any]:
    name = "broken_existing_issuance_chain_rejected"
    with tempfile.TemporaryDirectory(prefix=f"plw_issue_{name}_") as temp:
        fixture = build_fixture(
            Path(temp),
            extension=".js",
            condition='value.kind === "ok"',
            inverse=False,
            semicolon=True,
        )
        capability_path = _apply_capability(fixture)
        ledger_path = fixture["evidence"] / "issuance.jsonl"
        ledger_path.write_text(
            json.dumps(
                {
                    "schema_version": "plw-js-ts-v2-postcondition-validation-issuance-v1",
                    "sequence": 1,
                    "previous_record_digest": None,
                    "record_digest": "sha256:broken",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        result = _issue(fixture, capability_path)
        ok = (
            result.get("status")
            == "BOUNDED_CAPABILITY_POSTCONDITION_ISSUANCE_REJECTED"
            and (result.get("postconditions", {}) or {}).get("validated") is False
            and (result.get("postconditions", {}) or {}).get(
                "evidence_acceptance_granted"
            )
            is False
            and (result.get("containment", {}) or {}).get("worktree_disposed")
            is True
            and not fixture["target"].exists()
        )
        return {
            "case": name,
            "expected": "REJECT_BROKEN_CHAIN",
            "ok": ok,
            "status": result.get("status"),
            "reason": result.get("reason"),
        }


def _postwrite_failure_is_issued_but_not_accepted() -> Dict[str, Any]:
    name = "postwrite_failure_receipt_sealed_without_acceptance"
    with tempfile.TemporaryDirectory(prefix=f"plw_issue_{name}_") as temp:
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
        preflight = json.loads(
            fixture["preflight_path"].read_text(encoding="utf-8")
        )
        preflight["baseline_validation"] = {
            "command": command,
            "exit_code": 0,
        }
        preflight["postcondition_baseline_validation"][
            "focused_target_native_after"
        ] = {
            "command": command,
            "exit_code": 0,
            "stdout_sha256": digest_text(""),
            "stderr_sha256": digest_text(""),
        }
        write_json(fixture["preflight_path"], preflight)
        rebind_preflight_and_authorization(fixture)
        capability_path = _apply_capability(fixture)
        result = _issue(fixture, capability_path)
        ledger = _read_issuance_ledger(fixture["evidence"] / "issuance.jsonl")
        ok = (
            result.get("status")
            == "BOUNDED_CAPABILITY_POSTCONDITION_FAILURE_RECEIPT_ISSUED"
            and result.get("validation_status")
            == "MUTATION_FAILED_WORKTREE_DISCARDED"
            and len(ledger) == 1
            and ledger[0].get("validation_status")
            == "MUTATION_FAILED_WORKTREE_DISCARDED"
            and (result.get("postconditions", {}) or {}).get("validated") is False
            and (result.get("postconditions", {}) or {}).get(
                "evidence_acceptance_granted"
            )
            is False
            and (result.get("containment", {}) or {}).get("worktree_disposed")
            is True
            and not fixture["target"].exists()
        )
        return {
            "case": name,
            "expected": "FAILURE_ISSUED_NOT_ACCEPTED",
            "ok": ok,
            "status": result.get("status"),
            "validation_status": result.get("validation_status"),
        }


def _inside_target_output_rejected_and_disposed() -> Dict[str, Any]:
    name = "issuance_path_inside_target_rejected_and_disposed"
    with tempfile.TemporaryDirectory(prefix=f"plw_issue_{name}_") as temp:
        fixture = build_fixture(
            Path(temp),
            extension=".js",
            condition='value.kind === "ok"',
            inverse=False,
            semicolon=True,
        )
        capability_path = _apply_capability(fixture)
        target = fixture["target"]
        result = issue_bounded_capability_postconditions(
            root=target,
            disposable_parent=fixture["base"],
            capability_contract_path=fixture["contract_path"],
            capability_receipt_path=capability_path,
            plan_path=fixture["plan_path"],
            preflight_path=fixture["preflight_path"],
            authorization_path=fixture["authorization_path"],
            validation_spec_path=fixture["spec_path"],
            primitive_materialization_path=fixture["evidence"] / "primitive.json",
            validation_receipt_path=target / "forbidden-validation.json",
            issuance_ledger_path=fixture["evidence"] / "issuance.jsonl",
            timeout_seconds=30,
        )
        ok = (
            result.get("status")
            == "BOUNDED_CAPABILITY_POSTCONDITION_ISSUANCE_REJECTED"
            and (result.get("containment", {}) or {}).get("worktree_disposed")
            is True
            and not target.exists()
            and not (fixture["evidence"] / "issuance.jsonl").exists()
            and (result.get("postconditions", {}) or {}).get(
                "evidence_acceptance_granted"
            )
            is False
        )
        return {
            "case": name,
            "expected": "REJECT_PATH_AND_DISPOSE",
            "ok": ok,
            "status": result.get("status"),
            "reason": result.get("reason"),
            "worktree_disposed": (result.get("containment", {}) or {}).get(
                "worktree_disposed"
            ),
        }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()

    cases = [
        _positive(
            "positive_js_exact_receipt_issuance",
            extension=".js",
            condition='value.kind === "ok"',
            inverse=False,
            semicolon=True,
        ),
        _positive(
            "inverse_ts_exact_receipt_issuance",
            extension=".ts",
            condition="value.kind === 'arguments'",
            inverse=True,
            semicolon=False,
        ),
        _capability_tamper_rejected(),
        _broken_issuance_chain_rejected(),
        _postwrite_failure_is_issued_but_not_accepted(),
        _inside_target_output_rejected_and_disposed(),
    ]
    failed = [case["case"] for case in cases if not case["ok"]]
    report = {
        "schema_version": (
            "plw-js-ts-v2-bounded-capability-postcondition-issuance-regression-v1"
        ),
        "status": (
            "BOUNDED_CAPABILITY_POSTCONDITION_ISSUANCE_REGRESSION_PASSED"
            if not failed
            else "BOUNDED_CAPABILITY_POSTCONDITION_ISSUANCE_REGRESSION_FAILED"
        ),
        "case_count": len(cases),
        "passed_case_count": sum(1 for case in cases if case["ok"]),
        "failed_cases": failed,
        "cases": cases,
        "authority": {
            "deterministic_regression_only": True,
            "interactive_audit_authority": False,
            "evidence_acceptance_authority_granted": False,
            "truth_commit": False,
        },
    }

    output = Path(args.output)
    summary = Path(args.summary)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    lines = [
        "# Bounded capability postcondition issuance regression",
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
            f"{'PASS' if case['ok'] else 'FAIL'} |"
        )
    lines.extend(
        [
            "",
            "Regression only. Interactive execution remains promotion authority.",
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
            },
            sort_keys=True,
        )
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
