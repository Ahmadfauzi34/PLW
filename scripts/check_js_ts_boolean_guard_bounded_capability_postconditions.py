#!/usr/bin/env python3
"""Deterministic checks for bounded capability -> postcondition handoff.

These cases are regression evidence only. Promotion authority comes from a
separate interactive execution of the exact checked source bundle.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping

from check_js_ts_boolean_guard_bounded_capability import (
    apply_fixture,
    build_fixture,
    digest_file,
    digest_text,
    rebind_preflight_and_authorization,
    write_json,
)
from validate_js_ts_boolean_guard_bounded_capability_postconditions import (
    validate_bounded_capability_postconditions,
)


def _write_capability_receipt(fixture: Dict[str, Any]) -> Path:
    receipt = apply_fixture(fixture)
    path = fixture["evidence"] / "capability_receipt.json"
    write_json(path, receipt)
    return path


def _integrate(fixture: Dict[str, Any], capability_receipt_path: Path) -> Dict[str, Any]:
    return validate_bounded_capability_postconditions(
        root=fixture["target"],
        disposable_parent=fixture["base"],
        capability_contract_path=fixture["contract_path"],
        capability_receipt_path=capability_receipt_path,
        plan_path=fixture["plan_path"],
        preflight_path=fixture["preflight_path"],
        authorization_path=fixture["authorization_path"],
        validation_spec_path=fixture["spec_path"],
        primitive_materialization_path=fixture["evidence"] / "primitive.json",
        timeout_seconds=30,
    )


def _positive_case(
    name: str,
    *,
    extension: str,
    condition: str,
    inverse: bool,
    semicolon: bool,
) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"plw_cap_post_{name}_") as temp:
        base = Path(temp)
        fixture = build_fixture(
            base,
            extension=extension,
            condition=condition,
            inverse=inverse,
            semicolon=semicolon,
        )
        capability_path = _write_capability_receipt(fixture)
        receipt = _integrate(fixture, capability_path)
        ok = (
            receipt.get("status")
            == "BOUNDED_MUTATION_CAPABILITY_POSTCONDITIONS_VALIDATED"
            and (receipt.get("postconditions", {}) or {}).get("validated") is True
            and (receipt.get("postconditions", {}) or {}).get(
                "evidence_acceptance_granted"
            )
            is False
            and (receipt.get("containment", {}) or {}).get("worktree_disposed")
            is True
            and not fixture["target"].exists()
            and (receipt.get("authority", {}) or {}).get("truth_commit") is False
        )
        return {
            "case": name,
            "expected": "VALIDATED",
            "ok": ok,
            "status": receipt.get("status"),
            "next_gate": receipt.get("next_gate"),
            "worktree_disposed": (receipt.get("containment", {}) or {}).get(
                "worktree_disposed"
            ),
        }


def _tamper_after_apply_case(name: str, tamper) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"plw_cap_post_{name}_") as temp:
        base = Path(temp)
        fixture = build_fixture(
            base,
            extension=".js",
            condition='value.kind === "ok"',
            inverse=False,
            semicolon=True,
        )
        capability_path = _write_capability_receipt(fixture)
        tamper(fixture, capability_path)
        receipt = _integrate(fixture, capability_path)
        ok = (
            receipt.get("status")
            in {
                "BOUNDED_MUTATION_CAPABILITY_POSTCONDITION_REJECTED",
                "BOUNDED_MUTATION_CAPABILITY_POSTCONDITION_FAILED",
            }
            and (receipt.get("postconditions", {}) or {}).get("validated") is False
            and (receipt.get("postconditions", {}) or {}).get(
                "evidence_acceptance_granted"
            )
            is False
            and (receipt.get("containment", {}) or {}).get("worktree_disposed")
            is True
            and not fixture["target"].exists()
        )
        return {
            "case": name,
            "expected": "REJECT_OR_FAIL_CLOSED",
            "ok": ok,
            "status": receipt.get("status"),
            "error": receipt.get("error"),
            "worktree_disposed": (receipt.get("containment", {}) or {}).get(
                "worktree_disposed"
            ),
        }


def _postwrite_failure_case() -> Dict[str, Any]:
    name = "postwrite_focused_validation_failure_discards_worktree"
    with tempfile.TemporaryDirectory(prefix=f"plw_cap_post_{name}_") as temp:
        base = Path(temp)
        fixture = build_fixture(
            base,
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

        capability_path = _write_capability_receipt(fixture)
        receipt = _integrate(fixture, capability_path)
        validation = receipt.get("postcondition_validation", {}) or {}
        ok = (
            receipt.get("status")
            == "BOUNDED_MUTATION_CAPABILITY_POSTCONDITION_FAILED"
            and validation.get("status") == "MUTATION_FAILED_WORKTREE_DISCARDED"
            and (receipt.get("postconditions", {}) or {}).get("validated") is False
            and (receipt.get("containment", {}) or {}).get("worktree_disposed")
            is True
            and not fixture["target"].exists()
        )
        return {
            "case": name,
            "expected": "FAIL_CLOSED_AFTER_WRITE",
            "ok": ok,
            "status": receipt.get("status"),
            "validator_status": validation.get("status"),
            "worktree_disposed": (receipt.get("containment", {}) or {}).get(
                "worktree_disposed"
            ),
        }


def _tamper_capability_id(_fixture: Dict[str, Any], path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["capability_id"] = "other.capability"
    write_json(path, payload)


def _tamper_primitive(_fixture: Dict[str, Any], path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["primitive"]["receipt"]["mutation"]["actual_after_source_sha256"] = (
        digest_text("tampered")
    )
    write_json(path, payload)


def _tamper_capability_authority(_fixture: Dict[str, Any], path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["authority"]["evidence_acceptance_authority_granted"] = True
    write_json(path, payload)


def _tamper_authorization(fixture: Dict[str, Any], _path: Path) -> None:
    auth = json.loads(fixture["authorization_path"].read_text(encoding="utf-8"))
    auth["binding"]["capability_id"] = "other.capability"
    write_json(fixture["authorization_path"], auth)


def _tamper_spec_after_apply(fixture: Dict[str, Any], _path: Path) -> None:
    spec = json.loads(fixture["spec_path"].read_text(encoding="utf-8"))
    spec["commands"]["parse_after_rewrite"] = [sys.executable, "-c", "pass"]
    write_json(fixture["spec_path"], spec)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()

    cases = [
        _positive_case(
            "positive_js_capability_to_postconditions",
            extension=".js",
            condition='value.kind === "ok"',
            inverse=False,
            semicolon=True,
        ),
        _positive_case(
            "inverse_ts_capability_to_postconditions",
            extension=".ts",
            condition="value.kind === 'arguments'",
            inverse=True,
            semicolon=False,
        ),
        _tamper_after_apply_case(
            "capability_id_tamper_rejected",
            _tamper_capability_id,
        ),
        _tamper_after_apply_case(
            "embedded_primitive_tamper_rejected",
            _tamper_primitive,
        ),
        _tamper_after_apply_case(
            "capability_authority_escalation_rejected",
            _tamper_capability_authority,
        ),
        _tamper_after_apply_case(
            "authorization_capability_binding_tamper_rejected",
            _tamper_authorization,
        ),
        _tamper_after_apply_case(
            "validation_spec_substitution_after_apply_rejected",
            _tamper_spec_after_apply,
        ),
        _postwrite_failure_case(),
    ]
    failed = [case["case"] for case in cases if not case["ok"]]
    report = {
        "schema_version": (
            "plw-js-ts-v2-bounded-capability-postcondition-integration-regression-v1"
        ),
        "status": (
            "BOUNDED_CAPABILITY_POSTCONDITION_INTEGRATION_REGRESSION_PASSED"
            if not failed
            else "BOUNDED_CAPABILITY_POSTCONDITION_INTEGRATION_REGRESSION_FAILED"
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
        "# Bounded capability postcondition integration regression",
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
