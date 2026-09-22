#!/usr/bin/env python3
"""Reference checks for the disposable temp-worktree boolean-guard adapter."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, Mapping

from plan_js_ts_boolean_guard_rewrite import build_plan

RULE = "js_boolean_guard_return"
REPOSITORY = "reference/synthetic-js"
SOURCE_PATH = "src/example.js"
ADAPTER = Path(__file__).with_name(
    "apply_js_ts_boolean_guard_temp_worktree_reference.py"
)


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def digest_text(text: str) -> str:
    return digest_bytes(text.encode("utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git(root: Path, *args: str) -> str:
    proc = run(["git", "-C", str(root), *args])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return proc.stdout.strip()


def build_fixture(base: Path) -> Dict[str, Any]:
    target = (base / "target").resolve()
    evidence = (base / "evidence").resolve()
    target.mkdir(parents=True)
    evidence.mkdir(parents=True)
    source = target / SOURCE_PATH
    source.parent.mkdir(parents=True)
    source.write_text(
        """function isSame(left, right) {
  if (left === right) {
    return true;
  }

  return false;
}
""",
        encoding="utf-8",
    )

    if run(["git", "init", "-q"], cwd=target).returncode != 0:
        raise RuntimeError("git init failed")
    git(target, "config", "user.email", "reference@example.invalid")
    git(target, "config", "user.name", "PLW Reference")
    git(target, "add", SOURCE_PATH)
    git(target, "commit", "-q", "-m", "reference baseline")
    revision = git(target, "rev-parse", "HEAD")

    candidate = {
        "candidate_id": digest_text("reference:boolean-guard:isSame"),
        "kind": RULE,
        "files": [SOURCE_PATH],
        "members": [
            {
                "file": SOURCE_PATH,
                "name": "isSame",
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
            "inverse": False,
        },
    }
    candidate_path = evidence / "candidate.json"
    write_json(candidate_path, candidate)

    plan = build_plan(target, candidate)
    plan_path = evidence / "plan.json"
    write_json(plan_path, plan)
    plan_digest = digest_file(plan_path)

    baseline = run(["node", "--check", SOURCE_PATH], cwd=target)
    if baseline.returncode != 0:
        raise RuntimeError("reference baseline node --check failed")

    rewrite = plan["planned_rewrite"]
    postcondition_spec = {
        "schema_version": "plw-js-ts-v2-postcondition-validation-spec-v1",
        "status": "POSTCONDITION_VALIDATION_SPEC_READY",
        "target": {
            "repository": REPOSITORY,
            "revision": revision,
            "source_path": SOURCE_PATH,
            "candidate_id": candidate["candidate_id"],
        },
        "commands": {
            "parse_after_rewrite": ["node", "--check", SOURCE_PATH],
            "focused_target_native_after": ["node", "--check", SOURCE_PATH],
            "target_typecheck_or_type_tests_after": ["node", "--check", SOURCE_PATH],
        },
        "policy": {
            "cwd": "TARGET_ROOT",
            "shell": False,
            "stop_on_first_failure": True,
        },
    }
    postcondition_spec_path = evidence / "postcondition-validation-spec.json"
    write_json(postcondition_spec_path, postcondition_spec)
    postcondition_spec_digest = digest_file(postcondition_spec_path)

    preflight = {
        "schema_version": "plw-js-ts-v2-mutation-preflight-v1",
        "status": "PREFLIGHT_VALIDATED",
        "postcondition_validation_spec_digest": postcondition_spec_digest,
        "target": {
            "repository": REPOSITORY,
            "revision": revision,
            "source_path": SOURCE_PATH,
            "candidate_id": candidate["candidate_id"],
            "target_root_realpath_sha256": digest_text(str(target)),
        },
        "plan_binding": {
            "plan_digest": plan_digest,
            "before_source_sha256": rewrite["before_source_sha256"],
            "planned_source_sha256": rewrite["planned_source_sha256"],
            "planned_diff_digest": digest_text(rewrite["diff"]),
        },
        "checks": {
            "clean_checkout": git(target, "status", "--porcelain", "--untracked-files=all") == "",
            "disposable_checkout": True,
            "primary_worktree": False,
            "upstream_push_credentials_disabled": True,
            "source_hash_matches_plan": digest_file(source)
            == rewrite["before_source_sha256"],
            "candidate_span_match_count_one": True,
            "baseline_validation_passed": True,
        },
        "baseline_validation": {
            "command": ["node", "--check", SOURCE_PATH],
            "exit_code": baseline.returncode,
        },
        "authority": {
            "read_only": True,
            "source_mutation_allowed": False,
        },
    }
    preflight_path = evidence / "preflight.json"
    write_json(preflight_path, preflight)
    preflight_digest = digest_file(preflight_path)

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

    authorization = {
        "schema_version": "plw-js-ts-v2-mutation-authorization-v1",
        "status": "MUTATION_AUTHORIZED",
        "authorized": True,
        "authorization_scope": "ONE_CANDIDATE_ONE_TARGET_ONE_PLAN",
        "single_use": True,
        "issuer": {
            "kind": "REFERENCE_TEST_HARNESS",
            "external_to_planner": True,
            "planner_self_authorized": False,
        },
        "binding": {
            "candidate_id": candidate["candidate_id"],
            "target_repository": REPOSITORY,
            "target_revision": revision,
            "source_path": SOURCE_PATH,
            "before_source_sha256": rewrite["before_source_sha256"],
            "planned_source_sha256": rewrite["planned_source_sha256"],
            "plan_digest": plan_digest,
            "preflight_evidence_digest": preflight_digest,
            "postcondition_validation_spec_digest": postcondition_spec_digest,
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

    return {
        "base": base,
        "target": target,
        "evidence": evidence,
        "source": source,
        "revision": revision,
        "candidate": candidate,
        "plan": plan,
        "plan_path": plan_path,
        "postcondition_spec_path": postcondition_spec_path,
        "preflight_path": preflight_path,
        "authorization_path": authorization_path,
        "boundary_path": boundary_path,
        "ledger_path": evidence / "consumption.jsonl",
        "receipt_path": evidence / "receipt.json",
    }


def adapter_command(fixture: Mapping[str, Any], *, allow: bool = True, disposable_parent: Path | None = None) -> list[str]:
    command = [
        sys.executable,
        str(ADAPTER),
        "--target-root",
        str(fixture["target"]),
        "--disposable-parent",
        str(disposable_parent or fixture["base"]),
        "--target-repository",
        REPOSITORY,
        "--plan",
        str(fixture["plan_path"]),
        "--postcondition-validation-spec",
        str(fixture["postcondition_spec_path"]),
        "--preflight",
        str(fixture["preflight_path"]),
        "--authorization",
        str(fixture["authorization_path"]),
        "--disposable-boundary",
        str(fixture["boundary_path"]),
        "--consumption-ledger",
        str(fixture["ledger_path"]),
        "--output",
        str(fixture["receipt_path"]),
    ]
    if allow:
        command.append("--allow-reference-mutation")
    return command


def run_case(
    name: str,
    *,
    mutate_fixture: Callable[[Dict[str, Any]], None] | None = None,
    allow: bool = True,
    expected_pass: bool,
    alternate_parent: bool = False,
) -> Dict[str, Any]:
    temp_path = None
    result: Dict[str, Any]
    with tempfile.TemporaryDirectory(prefix=f"plw_{name}_") as temp:
        temp_path = Path(temp)
        fixture = build_fixture(temp_path)
        if mutate_fixture:
            mutate_fixture(fixture)

        before_call = fixture["source"].read_bytes()
        parent = (temp_path / "wrong-parent") if alternate_parent else None
        if parent is not None:
            parent.mkdir()
        proc = run(adapter_command(fixture, allow=allow, disposable_parent=parent))
        actual_pass = proc.returncode == 0
        after_call = fixture["source"].read_bytes()

        checks = {
            "expected_pass": expected_pass,
            "actual_pass": actual_pass,
            "adapter_exit_code": proc.returncode,
            "negative_source_unchanged": True if expected_pass else before_call == after_call,
            "receipt_exists": fixture["receipt_path"].is_file(),
            "ledger_exists": fixture["ledger_path"].is_file(),
        }

        if expected_pass:
            if not actual_pass:
                checks["error"] = proc.stderr.strip() or proc.stdout.strip()
            else:
                receipt = json.loads(fixture["receipt_path"].read_text())
                checks.update(
                    {
                        "receipt_status": receipt.get("status"),
                        "changed_paths": receipt.get("mutation", {}).get("changed_paths"),
                        "authorization_consumed": receipt.get("mutation", {}).get(
                            "authorization_consumed"
                        ),
                        "postconditions_validated": receipt.get("postconditions", {}).get(
                            "validated"
                        ),
                        "after_hash_matches_plan": digest_file(fixture["source"])
                        == fixture["plan"]["planned_rewrite"]["planned_source_sha256"],
                        "node_parse_after_apply": run(
                            ["node", "--check", SOURCE_PATH], cwd=fixture["target"]
                        ).returncode
                        == 0,
                    }
                )
        else:
            checks["rejection_output"] = (proc.stdout.strip() or proc.stderr.strip())[-500:]

        ok = actual_pass == expected_pass
        if expected_pass:
            ok = ok and checks.get("receipt_status") == "TEMP_WORKTREE_APPLIED"
            ok = ok and checks.get("changed_paths") == [SOURCE_PATH]
            ok = ok and checks.get("authorization_consumed") is True
            ok = ok and checks.get("postconditions_validated") is False
            ok = ok and checks.get("after_hash_matches_plan") is True
            ok = ok and checks.get("node_parse_after_apply") is True
        else:
            ok = ok and checks["negative_source_unchanged"] is True

        result = {
            "case": name,
            "ok": ok,
            "checks": checks,
        }

    result["temporary_root_disposed"] = bool(temp_path is not None and not temp_path.exists())
    result["ok"] = result["ok"] and result["temporary_root_disposed"]
    return result


def mutate_self_authorization(fixture: Dict[str, Any]) -> None:
    payload = json.loads(fixture["authorization_path"].read_text())
    payload["issuer"]["external_to_planner"] = False
    payload["issuer"]["planner_self_authorized"] = True
    write_json(fixture["authorization_path"], payload)


def _rebind_validation_spec(fixture: Dict[str, Any]) -> None:
    spec_digest = digest_file(fixture["postcondition_spec_path"])
    preflight = json.loads(fixture["preflight_path"].read_text())
    preflight["postcondition_validation_spec_digest"] = spec_digest
    write_json(fixture["preflight_path"], preflight)

    authorization = json.loads(fixture["authorization_path"].read_text())
    authorization["binding"]["postcondition_validation_spec_digest"] = spec_digest
    authorization["binding"]["preflight_evidence_digest"] = digest_file(
        fixture["preflight_path"]
    )
    write_json(fixture["authorization_path"], authorization)


def mutate_wrong_validation_spec_digest(fixture: Dict[str, Any]) -> None:
    authorization = json.loads(fixture["authorization_path"].read_text())
    authorization["binding"]["postcondition_validation_spec_digest"] = digest_text(
        "wrong-validation-spec"
    )
    write_json(fixture["authorization_path"], authorization)


def mutate_focused_command_substitution(fixture: Dict[str, Any]) -> None:
    spec = json.loads(fixture["postcondition_spec_path"].read_text())
    spec["commands"]["focused_target_native_after"] = [
        "node",
        "--check",
        "package.json",
    ]
    write_json(fixture["postcondition_spec_path"], spec)
    _rebind_validation_spec(fixture)


def mutate_shell_validation_spec(fixture: Dict[str, Any]) -> None:
    spec = json.loads(fixture["postcondition_spec_path"].read_text())
    spec["policy"]["shell"] = True
    write_json(fixture["postcondition_spec_path"], spec)
    _rebind_validation_spec(fixture)


def mutate_wrong_plan_digest(fixture: Dict[str, Any]) -> None:
    payload = json.loads(fixture["authorization_path"].read_text())
    payload["binding"]["plan_digest"] = digest_text("wrong-plan")
    write_json(fixture["authorization_path"], payload)


def mutate_wrong_preflight_digest(fixture: Dict[str, Any]) -> None:
    payload = json.loads(fixture["authorization_path"].read_text())
    payload["binding"]["preflight_evidence_digest"] = digest_text("wrong-preflight")
    write_json(fixture["authorization_path"], payload)


def mutate_dirty_checkout(fixture: Dict[str, Any]) -> None:
    (fixture["target"] / "unexpected.tmp").write_text("unexpected", encoding="utf-8")


def mutate_stale_source_hidden_from_status(fixture: Dict[str, Any]) -> None:
    git(fixture["target"], "update-index", "--assume-unchanged", SOURCE_PATH)
    fixture["source"].write_text(
        fixture["source"].read_text(encoding="utf-8").replace(
            "left === right", "left !== right"
        ),
        encoding="utf-8",
    )


def mutate_boundary_mismatch(fixture: Dict[str, Any]) -> None:
    payload = json.loads(fixture["boundary_path"].read_text())
    payload["target_root_realpath"] = str(fixture["target"]) + "-other"
    write_json(fixture["boundary_path"], payload)


def mutate_wildcard_authorization(fixture: Dict[str, Any]) -> None:
    payload = json.loads(fixture["authorization_path"].read_text())
    payload["authorization_scope"] = "RULE_WIDE"
    write_json(fixture["authorization_path"], payload)


def mutate_tampered_planned_diff(fixture: Dict[str, Any]) -> None:
    plan = json.loads(fixture["plan_path"].read_text())
    plan["planned_rewrite"]["diff"] = plan["planned_rewrite"]["diff"] + "\n"
    write_json(fixture["plan_path"], plan)

    preflight = json.loads(fixture["preflight_path"].read_text())
    preflight["plan_binding"]["plan_digest"] = digest_file(fixture["plan_path"])
    preflight["plan_binding"]["planned_diff_digest"] = digest_text(
        plan["planned_rewrite"]["diff"]
    )
    write_json(fixture["preflight_path"], preflight)

    auth = json.loads(fixture["authorization_path"].read_text())
    auth["binding"]["plan_digest"] = digest_file(fixture["plan_path"])
    auth["binding"]["preflight_evidence_digest"] = digest_file(
        fixture["preflight_path"]
    )
    write_json(fixture["authorization_path"], auth)


def run_reuse_case() -> Dict[str, Any]:
    temp_path = None
    result: Dict[str, Any]
    with tempfile.TemporaryDirectory(prefix="plw_authorization_reuse_") as temp:
        temp_path = Path(temp)
        fixture = build_fixture(temp_path)
        first = run(adapter_command(fixture, allow=True))
        if first.returncode != 0:
            result = {
                "case": "authorization_reuse",
                "ok": False,
                "checks": {"first_apply_failed": first.stderr or first.stdout},
            }
        else:
            git(fixture["target"], "reset", "--hard", "HEAD")
            git(fixture["target"], "clean", "-fd")
            before_second = fixture["source"].read_bytes()
            second = run(adapter_command(fixture, allow=True))
            after_second = fixture["source"].read_bytes()
            result = {
                "case": "authorization_reuse",
                "ok": (
                    second.returncode != 0
                    and before_second == after_second
                    and fixture["ledger_path"].read_text().count(
                        "CONSUMED_FOR_EXECUTION_ATTEMPT"
                    )
                    == 1
                ),
                "checks": {
                    "first_apply_exit_code": first.returncode,
                    "second_apply_exit_code": second.returncode,
                    "second_source_unchanged": before_second == after_second,
                    "ledger_consumption_count": fixture["ledger_path"].read_text().count(
                        "CONSUMED_FOR_EXECUTION_ATTEMPT"
                    ),
                    "second_rejection_output": (
                        second.stdout.strip() or second.stderr.strip()
                    )[-500:],
                },
            }

    result["temporary_root_disposed"] = bool(temp_path is not None and not temp_path.exists())
    result["ok"] = result["ok"] and result["temporary_root_disposed"]
    return result


def build_report(index: Mapping[str, Any], contract_report: Mapping[str, Any]) -> Dict[str, Any]:
    errors = []
    if index.get("schema_version") != "plw-js-ts-v2-temp-worktree-mutation-adapter-reference-v1":
        errors.append("unexpected reference index schema")
    if index.get("rule") != RULE:
        errors.append("reference index rule mismatch")
    if contract_report.get("status") != "MUTATION_BOUNDARY_CONTRACT_REVIEW_PASSED":
        errors.append("mutation boundary contract prerequisite not passed")
    if contract_report.get("next_gate") != "TEMP_WORKTREE_MUTATION_ADAPTER_REFERENCE":
        errors.append("contract prerequisite next gate mismatch")
    authority = contract_report.get("authority", {}) or {}
    if authority.get("source_mutation_authority_granted") is not False:
        errors.append("contract prerequisite unexpectedly grants source mutation")

    cases = [
        run_case("positive_apply", expected_pass=True),
        run_case("missing_literal_allow", allow=False, expected_pass=False),
        run_case(
            "planner_self_authorization",
            mutate_fixture=mutate_self_authorization,
            expected_pass=False,
        ),
        run_case(
            "wrong_plan_digest",
            mutate_fixture=mutate_wrong_plan_digest,
            expected_pass=False,
        ),
        run_case(
            "wrong_preflight_digest",
            mutate_fixture=mutate_wrong_preflight_digest,
            expected_pass=False,
        ),
        run_case(
            "wrong_validation_spec_digest",
            mutate_fixture=mutate_wrong_validation_spec_digest,
            expected_pass=False,
        ),
        run_case(
            "focused_command_substitution",
            mutate_fixture=mutate_focused_command_substitution,
            expected_pass=False,
        ),
        run_case(
            "shell_validation_spec",
            mutate_fixture=mutate_shell_validation_spec,
            expected_pass=False,
        ),
        run_case(
            "disposable_boundary_mismatch",
            mutate_fixture=mutate_boundary_mismatch,
            expected_pass=False,
        ),
        run_case(
            "disposable_parent_mismatch",
            expected_pass=False,
            alternate_parent=True,
        ),
        run_case(
            "dirty_checkout",
            mutate_fixture=mutate_dirty_checkout,
            expected_pass=False,
        ),
        run_case(
            "stale_source",
            mutate_fixture=mutate_stale_source_hidden_from_status,
            expected_pass=False,
        ),
        run_case(
            "wildcard_authorization",
            mutate_fixture=mutate_wildcard_authorization,
            expected_pass=False,
        ),
        run_case(
            "tampered_planned_diff",
            mutate_fixture=mutate_tampered_planned_diff,
            expected_pass=False,
        ),
        run_reuse_case(),
    ]

    failed_cases = [case["case"] for case in cases if not case["ok"]]
    errors.extend(f"reference case failed: {name}" for name in failed_cases)

    status = (
        "TEMP_WORKTREE_MUTATION_ADAPTER_REFERENCE_PASSED"
        if not errors
        else "TEMP_WORKTREE_MUTATION_ADAPTER_REFERENCE_FAILED"
    )
    return {
        "schema_version": "plw-js-ts-v2-temp-worktree-mutation-adapter-reference-report-v1",
        "status": status,
        "rule": RULE,
        "prerequisite": {
            "contract_review": contract_report.get("status"),
            "contract_authority_remains_read_only": authority.get(
                "source_mutation_authority_granted"
            )
            is False,
        },
        "cases": cases,
        "case_count": len(cases),
        "passed_case_count": sum(1 for case in cases if case["ok"]),
        "adapter_state_reached": "TEMP_WORKTREE_APPLIED" if not errors else None,
        "postcondition_acceptance_performed": False,
        "authority": {
            "reference_adapter_only": True,
            "product_mutation_surface_exposed": False,
            "generic_mutation_authority_granted": False,
            "automatic_patch_authority_granted": False,
            "upstream_mutation_authorized": False,
            "postcondition_acceptance_authority_granted": False,
            "global_behavioral_equivalence_proven": False,
            "truth_commit": False,
        },
        "errors": errors,
        "next_gate": "TEMP_WORKTREE_POSTCONDITION_VALIDATION_REFERENCE",
    }


def render_summary(report: Mapping[str, Any]) -> str:
    lines = [
        "# JS/TS temp-worktree mutation adapter reference",
        "",
        f"Status: **{report['status']}**",
        "",
        f"Cases: **{report['passed_case_count']}/{report['case_count']} passed**",
        "",
        "The positive case reaches TEMP_WORKTREE_APPLIED only.",
        "Postcondition acceptance is deliberately not performed by this adapter.",
        "",
        "## Cases",
        "",
        "| Case | Result |",
        "| --- | --- |",
    ]
    for case in report["cases"]:
        lines.append(f"| {case['case']} | {'PASS' if case['ok'] else 'FAIL'} |")
    lines.extend(
        [
            "",
            "## Authority boundary",
            "",
            "reference adapter PASS != product mutation surface",
            "",
            "TEMP_WORKTREE_APPLIED != postcondition acceptance",
            "",
            f"Next gate: {report['next_gate']}",
        ]
    )
    if report["errors"]:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in report["errors"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True)
    parser.add_argument("--contract-report", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()

    index = json.loads(Path(args.index).read_text(encoding="utf-8"))
    contract_report = json.loads(
        Path(args.contract_report).read_text(encoding="utf-8")
    )
    report = build_report(index, contract_report)

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
                "passed": report["passed_case_count"],
                "total": report["case_count"],
                "errors": report["errors"],
            },
            sort_keys=True,
        )
    )
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
