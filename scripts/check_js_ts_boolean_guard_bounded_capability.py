#!/usr/bin/env python3
"""Deterministic regression checks for the bounded boolean-guard capability.

These checks exercise implementation mechanics only. Promotion/enablement
adjudication remains interactive.
"""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping

from apply_js_ts_boolean_guard_bounded_capability import (
    CAPABILITY_ID,
    CapabilityError,
    apply_bounded_capability,
)
from plan_js_ts_boolean_guard_rewrite import build_plan

REPOSITORY = "reference/synthetic-js"


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def digest_text(text: str) -> str:
    return digest_bytes(text.encode("utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def run(argv: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        shell=False,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git(root: Path, *args: str) -> str:
    proc = run(["git", "-C", str(root), *args], cwd=root)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return proc.stdout.strip()


def noop_command() -> list[str]:
    return [sys.executable, "-c", "raise SystemExit(0)"]


def failing_command() -> list[str]:
    return [sys.executable, "-c", "raise SystemExit(7)"]


def dirty_command() -> list[str]:
    return [
        sys.executable,
        "-c",
        "from pathlib import Path; Path('unexpected.tmp').write_text('dirty')",
    ]


def build_fixture(
    base: Path,
    *,
    extension: str = ".js",
    condition: str = 'value.kind === "ok"',
    inverse: bool = False,
    semicolon: bool = True,
) -> Dict[str, Any]:
    target = (base / "target").resolve()
    evidence = (base / "evidence").resolve()
    target.mkdir(parents=True)
    evidence.mkdir(parents=True)

    source_rel = f"src/example{extension}"
    source = target / source_rel
    source.parent.mkdir(parents=True)

    semi = ";" if semicolon else ""
    if inverse:
        source_text = (
            "function check(value) {\n"
            f"  if ({condition}) {{\n"
            f"    return false{semi}\n"
            "  }\n\n"
            f"  return true{semi}\n"
            "}\n"
        )
    else:
        source_text = (
            "function check(value) {\n"
            f"  if ({condition}) {{\n"
            f"    return true{semi}\n"
            "  }\n\n"
            f"  return false{semi}\n"
            "}\n"
        )
    source.write_text(source_text, encoding="utf-8")

    if run(["git", "init", "-q"], cwd=target).returncode != 0:
        raise RuntimeError("git init failed")
    git(target, "config", "user.email", "reference@example.invalid")
    git(target, "config", "user.name", "PLW Reference")
    git(target, "add", source_rel)
    git(target, "commit", "-q", "-m", "baseline")
    revision = git(target, "rev-parse", "HEAD")

    candidate = {
        "candidate_id": digest_text(
            f"capability:{extension}:{condition}:{inverse}:{semicolon}"
        ),
        "kind": "js_boolean_guard_return",
        "files": [source_rel],
        "members": [
            {
                "file": source_rel,
                "name": "check",
                "line_start": 1,
                "line_end": 7,
            }
        ],
        "semantic_witness": {
            "type": "js_boolean_guard_return_v2",
            "same_function": True,
            "condition_evaluated_once_before_and_after": True,
            "true_false_terminals_opposite": True,
            "await_and_yield_condition_excluded": True,
            "inverse": inverse,
        },
    }
    plan = build_plan(target, candidate)
    plan_path = evidence / "plan.json"
    write_json(plan_path, plan)

    command = noop_command()
    spec = {
        "schema_version": "plw-js-ts-v2-postcondition-validation-spec-v1",
        "status": "POSTCONDITION_VALIDATION_SPEC_READY",
        "target": {
            "repository": REPOSITORY,
            "revision": revision,
            "source_path": source_rel,
            "candidate_id": candidate["candidate_id"],
        },
        "commands": {
            "parse_after_rewrite": command,
            "focused_target_native_after": command,
            "target_typecheck_or_type_tests_after": command,
        },
        "policy": {
            "cwd": "TARGET_ROOT",
            "shell": False,
            "stop_on_first_failure": True,
        },
    }
    spec_path = evidence / "spec.json"
    write_json(spec_path, spec)
    spec_digest = digest_file(spec_path)

    rewrite = plan["planned_rewrite"]
    baseline_records = {
        name: {
            "command": command,
            "exit_code": 0,
            "stdout_sha256": digest_text(""),
            "stderr_sha256": digest_text(""),
        }
        for name in (
            "parse_after_rewrite",
            "focused_target_native_after",
            "target_typecheck_or_type_tests_after",
        )
    }
    preflight = {
        "schema_version": "plw-js-ts-v2-mutation-preflight-v1",
        "status": "PREFLIGHT_VALIDATED",
        "postcondition_validation_spec_digest": spec_digest,
        "target": {
            "repository": REPOSITORY,
            "revision": revision,
            "source_path": source_rel,
            "candidate_id": candidate["candidate_id"],
            "target_root_realpath_sha256": digest_text(str(target)),
        },
        "plan_binding": {
            "plan_digest": digest_file(plan_path),
            "before_source_sha256": rewrite["before_source_sha256"],
            "planned_source_sha256": rewrite["planned_source_sha256"],
            "planned_diff_digest": digest_text(rewrite["diff"]),
        },
        "checks": {
            "clean_checkout": True,
            "disposable_checkout": True,
            "primary_worktree": False,
            "upstream_push_credentials_disabled": True,
            "source_hash_matches_plan": True,
            "candidate_span_match_count_one": True,
            "baseline_validation_passed": True,
        },
        "baseline_validation": {
            "command": command,
            "exit_code": 0,
        },
        "postcondition_baseline_validation": baseline_records,
        "authority": {
            "read_only": True,
            "source_mutation_allowed": False,
        },
    }
    preflight_path = evidence / "preflight.json"
    write_json(preflight_path, preflight)

    capability_contract_path = Path(
        "qualification/js_ts_v2_bounded_boolean_guard_mutation_capability.json"
    ).resolve()
    contract_digest = digest_file(capability_contract_path)

    authorization = {
        "schema_version": "plw-js-ts-v2-mutation-authorization-v1",
        "status": "MUTATION_AUTHORIZED",
        "authorized": True,
        "authorization_scope": "ONE_CANDIDATE_ONE_TARGET_ONE_PLAN",
        "single_use": True,
        "issuer": {
            "kind": "REGRESSION_HARNESS",
            "external_to_planner": True,
            "planner_self_authorized": False,
        },
        "binding": {
            "candidate_id": candidate["candidate_id"],
            "target_repository": REPOSITORY,
            "target_revision": revision,
            "source_path": source_rel,
            "before_source_sha256": rewrite["before_source_sha256"],
            "planned_source_sha256": rewrite["planned_source_sha256"],
            "plan_digest": digest_file(plan_path),
            "preflight_evidence_digest": digest_file(preflight_path),
            "postcondition_validation_spec_digest": spec_digest,
            "capability_id": CAPABILITY_ID,
            "capability_contract_digest": contract_digest,
        },
        "authority": {
            "generic_mutation_authority_granted": False,
            "automatic_patch_authority_granted": False,
            "upstream_mutation_authorized": False,
            "global_behavioral_equivalence_proven": False,
        },
    }
    authorization_path = evidence / "authorization.json"
    write_json(authorization_path, authorization)

    boundary = {
        "schema_version": "plw-js-ts-v2-disposable-boundary-v1",
        "status": "DISPOSABLE_BOUNDARY_READY",
        "reference_only": True,
        "primary_worktree": False,
        "target_root_realpath": str(target),
        "target_root_realpath_sha256": digest_text(str(target)),
    }
    boundary_path = evidence / "boundary.json"
    write_json(boundary_path, boundary)

    return {
        "base": base,
        "target": target,
        "source": source,
        "source_rel": source_rel,
        "evidence": evidence,
        "candidate": candidate,
        "plan": plan,
        "plan_path": plan_path,
        "spec_path": spec_path,
        "preflight_path": preflight_path,
        "authorization_path": authorization_path,
        "boundary_path": boundary_path,
        "ledger_path": evidence / "consumption.jsonl",
        "contract_path": capability_contract_path,
        "revision": revision,
    }


def rebind_preflight_and_authorization(fixture: Dict[str, Any]) -> None:
    spec_digest = digest_file(fixture["spec_path"])
    plan_digest = digest_file(fixture["plan_path"])
    preflight = json.loads(fixture["preflight_path"].read_text())
    preflight["postcondition_validation_spec_digest"] = spec_digest
    preflight["plan_binding"]["plan_digest"] = plan_digest
    write_json(fixture["preflight_path"], preflight)

    auth = json.loads(fixture["authorization_path"].read_text())
    auth["binding"]["plan_digest"] = plan_digest
    auth["binding"]["preflight_evidence_digest"] = digest_file(
        fixture["preflight_path"]
    )
    auth["binding"]["postcondition_validation_spec_digest"] = spec_digest
    write_json(fixture["authorization_path"], auth)


def apply_fixture(fixture: Dict[str, Any]) -> Dict[str, Any]:
    return apply_bounded_capability(
        root=fixture["target"],
        disposable_parent=fixture["base"],
        repository=REPOSITORY,
        capability_contract_path=fixture["contract_path"],
        plan_path=fixture["plan_path"],
        postcondition_spec_path=fixture["spec_path"],
        preflight_path=fixture["preflight_path"],
        authorization_path=fixture["authorization_path"],
        boundary_path=fixture["boundary_path"],
        ledger_path=fixture["ledger_path"],
        timeout_seconds=30,
        allow_pending=True,
    )


def run_positive(
    name: str,
    *,
    extension: str,
    condition: str,
    inverse: bool,
    semicolon: bool,
) -> Dict[str, Any]:
    temp_path = None
    result: Dict[str, Any]
    with tempfile.TemporaryDirectory(prefix=f"plw_cap_{name}_") as temp:
        temp_path = Path(temp)
        fixture = build_fixture(
            temp_path,
            extension=extension,
            condition=condition,
            inverse=inverse,
            semicolon=semicolon,
        )
        before = fixture["source"].read_bytes()
        try:
            receipt = apply_fixture(fixture)
            error = None
        except Exception as exc:  # deterministic report, not recovery path
            receipt = {}
            error = str(exc)
        after = fixture["source"].read_bytes()

        result = {
            "case": name,
            "expected": "PASS",
            "ok": (
                error is None
                and receipt.get("status")
                == "BOUNDED_MUTATION_CAPABILITY_APPLIED"
                and receipt.get("capability_id") == CAPABILITY_ID
                and (receipt.get("primitive", {}) or {}).get("status")
                == "TEMP_WORKTREE_APPLIED"
                and (receipt.get("postconditions", {}) or {}).get("validated")
                is False
                and before != after
                and fixture["ledger_path"].is_file()
            ),
            "error": error,
            "scope_proof": receipt.get("scope_proof"),
            "receipt_status": receipt.get("status"),
        }
    result["temporary_root_disposed"] = bool(
        temp_path is not None and not temp_path.exists()
    )
    result["ok"] = result["ok"] and result["temporary_root_disposed"]
    return result


def run_negative(
    name: str,
    fixture_builder: Dict[str, Any],
    mutate,
) -> Dict[str, Any]:
    temp_path = None
    result: Dict[str, Any]
    with tempfile.TemporaryDirectory(prefix=f"plw_cap_{name}_") as temp:
        temp_path = Path(temp)
        fixture = build_fixture(Path(temp), **fixture_builder)
        mutate(fixture)
        before = fixture["source"].read_bytes()
        try:
            apply_fixture(fixture)
            rejected = False
            error = None
        except CapabilityError as exc:
            rejected = True
            error = str(exc)
        after = fixture["source"].read_bytes()
        result = {
            "case": name,
            "expected": "REJECT",
            "ok": (
                rejected
                and before == after
                and not fixture["ledger_path"].exists()
            ),
            "error": error,
            "source_unchanged": before == after,
            "authorization_consumed": fixture["ledger_path"].exists(),
        }
    result["temporary_root_disposed"] = bool(
        temp_path is not None and not temp_path.exists()
    )
    result["ok"] = result["ok"] and result["temporary_root_disposed"]
    return result


def mutate_noop(_fixture: Dict[str, Any]) -> None:
    pass


def mutate_fold_inverse(fixture: Dict[str, Any]) -> None:
    plan = json.loads(fixture["plan_path"].read_text())
    condition = plan["match"]["condition"]
    indent = "  "
    plan["planned_rewrite"]["after"] = (
        indent + "return value.kind !== \"ok\"" + (
            ";" if plan["match"]["semicolon_style"] == "semicolon" else ""
        )
    )
    write_json(fixture["plan_path"], plan)
    rebind_preflight_and_authorization(fixture)


def mutate_missing_baseline(fixture: Dict[str, Any]) -> None:
    preflight = json.loads(fixture["preflight_path"].read_text())
    preflight["postcondition_baseline_validation"].pop(
        "target_typecheck_or_type_tests_after"
    )
    write_json(fixture["preflight_path"], preflight)
    auth = json.loads(fixture["authorization_path"].read_text())
    auth["binding"]["preflight_evidence_digest"] = digest_file(
        fixture["preflight_path"]
    )
    write_json(fixture["authorization_path"], auth)


def mutate_wrong_capability_id(fixture: Dict[str, Any]) -> None:
    auth = json.loads(fixture["authorization_path"].read_text())
    auth["binding"]["capability_id"] = "other.capability"
    write_json(fixture["authorization_path"], auth)


def mutate_actual_baseline_failure(fixture: Dict[str, Any]) -> None:
    spec = json.loads(fixture["spec_path"].read_text())
    spec["commands"]["parse_after_rewrite"] = failing_command()
    write_json(fixture["spec_path"], spec)
    preflight = json.loads(fixture["preflight_path"].read_text())
    preflight["postcondition_baseline_validation"]["parse_after_rewrite"] = {
        "command": failing_command(),
        "exit_code": 0,
    }
    write_json(fixture["preflight_path"], preflight)
    rebind_preflight_and_authorization(fixture)


def mutate_dirty_baseline_command(fixture: Dict[str, Any]) -> None:
    spec = json.loads(fixture["spec_path"].read_text())
    spec["commands"]["parse_after_rewrite"] = dirty_command()
    write_json(fixture["spec_path"], spec)
    preflight = json.loads(fixture["preflight_path"].read_text())
    preflight["postcondition_baseline_validation"]["parse_after_rewrite"] = {
        "command": dirty_command(),
        "exit_code": 0,
    }
    write_json(fixture["preflight_path"], preflight)
    rebind_preflight_and_authorization(fixture)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()

    cases = [
        run_positive(
            "positive_js_strict_equality_string",
            extension=".js",
            condition='value.kind === "ok"',
            inverse=False,
            semicolon=True,
        ),
        run_positive(
            "inverse_ts_strict_equality_string",
            extension=".ts",
            condition="value.kind === 'arguments'",
            inverse=True,
            semicolon=False,
        ),
        run_negative(
            "strict_inequality_rejected",
            {
                "extension": ".js",
                "condition": 'value.kind !== "ok"',
                "inverse": False,
                "semicolon": True,
            },
            mutate_noop,
        ),
        run_negative(
            "relational_operator_rejected",
            {
                "extension": ".js",
                "condition": "value.count < 3",
                "inverse": False,
                "semicolon": True,
            },
            mutate_noop,
        ),
        run_negative(
            "tsx_rejected",
            {
                "extension": ".tsx",
                "condition": 'value.kind === "ok"',
                "inverse": False,
                "semicolon": True,
            },
            mutate_noop,
        ),
        run_negative(
            "number_rhs_rejected",
            {
                "extension": ".js",
                "condition": "value.count === 3",
                "inverse": False,
                "semicolon": True,
            },
            mutate_noop,
        ),
        run_negative(
            "reversed_operands_rejected",
            {
                "extension": ".js",
                "condition": '"ok" === value.kind',
                "inverse": False,
                "semicolon": True,
            },
            mutate_noop,
        ),
        run_negative(
            "optional_chain_rejected",
            {
                "extension": ".js",
                "condition": 'value?.kind === "ok"',
                "inverse": False,
                "semicolon": True,
            },
            mutate_noop,
        ),
        run_negative(
            "operator_complement_folding_rejected",
            {
                "extension": ".js",
                "condition": 'value.kind === "ok"',
                "inverse": True,
                "semicolon": True,
            },
            mutate_fold_inverse,
        ),
        run_negative(
            "missing_baseline_record_rejected",
            {
                "extension": ".js",
                "condition": 'value.kind === "ok"',
                "inverse": False,
                "semicolon": True,
            },
            mutate_missing_baseline,
        ),
        run_negative(
            "wrong_capability_binding_rejected",
            {
                "extension": ".js",
                "condition": 'value.kind === "ok"',
                "inverse": False,
                "semicolon": True,
            },
            mutate_wrong_capability_id,
        ),
        run_negative(
            "actual_baseline_failure_rejected",
            {
                "extension": ".js",
                "condition": 'value.kind === "ok"',
                "inverse": False,
                "semicolon": True,
            },
            mutate_actual_baseline_failure,
        ),
        run_negative(
            "baseline_command_mutates_checkout_rejected",
            {
                "extension": ".js",
                "condition": 'value.kind === "ok"',
                "inverse": False,
                "semicolon": True,
            },
            mutate_dirty_baseline_command,
        ),
    ]

    failed = [case["case"] for case in cases if not case["ok"]]
    report = {
        "schema_version": (
            "plw-js-ts-v2-bounded-boolean-guard-capability-regression-v1"
        ),
        "status": (
            "BOUNDED_BOOLEAN_GUARD_CAPABILITY_REGRESSION_PASSED"
            if not failed
            else "BOUNDED_BOOLEAN_GUARD_CAPABILITY_REGRESSION_FAILED"
        ),
        "case_count": len(cases),
        "passed_case_count": sum(1 for case in cases if case["ok"]),
        "cases": cases,
        "failed_cases": failed,
        "authority": {
            "deterministic_regression_only": True,
            "interactive_audit_authority": False,
            "public_product_surface_exposed": False,
            "truth_commit": False,
        },
    }

    out = Path(args.output)
    summary = Path(args.summary)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    lines = [
        "# Bounded boolean-guard capability regression",
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
            "This is deterministic regression evidence only.",
            "Interactive review remains the authority for capability enablement.",
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
    import argparse

    raise SystemExit(main())
