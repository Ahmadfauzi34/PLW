#!/usr/bin/env python3
"""Reference postcondition validator for one applied JS/TS boolean-guard mutation.

This validator consumes a TEMP_WORKTREE_APPLIED receipt and the exact evidence
bound before mutation. It runs the pre-bound validation commands without a
shell, records command results, and always disposes the temporary worktree after
capturing evidence.

Success stops at POSTCONDITIONS_VALIDATED. Experiment evidence acceptance is a
separate authority.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

RULE = "js_boolean_guard_return"
PLAN_SCHEMA = "plw-js-ts-v2-boolean-guard-dry-run-plan-v1"
PREFLIGHT_SCHEMA = "plw-js-ts-v2-mutation-preflight-v1"
AUTH_SCHEMA = "plw-js-ts-v2-mutation-authorization-v1"
MUTATION_RECEIPT_SCHEMA = "plw-js-ts-v2-temp-worktree-mutation-adapter-receipt-v1"
VALIDATION_SPEC_SCHEMA = "plw-js-ts-v2-postcondition-validation-spec-v1"

FORBIDDEN_SHELL_EXECUTABLES = {
    "sh",
    "bash",
    "dash",
    "zsh",
    "fish",
    "cmd",
    "cmd.exe",
    "powershell",
    "powershell.exe",
    "pwsh",
    "pwsh.exe",
}


class ValidationError(ValueError):
    pass


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _digest_file(path: Path) -> str:
    return _digest_bytes(path.read_bytes())


def _digest_text(text: str) -> str:
    return _digest_bytes(text.encode("utf-8"))


def _require_outside_target(root: Path, path: Path, label: str) -> None:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return
    raise ValidationError(f"{label} must be outside target root")


def _assert_system_temp_target(root: Path, disposable_parent: Path) -> None:
    system_temp = Path(tempfile.gettempdir()).resolve()
    parent = disposable_parent.resolve()
    try:
        parent.relative_to(system_temp)
    except ValueError as exc:
        raise ValidationError(
            "disposable parent must be under the system temp directory"
        ) from exc
    try:
        root.relative_to(parent)
    except ValueError as exc:
        raise ValidationError(
            "target root must be inside the declared disposable parent"
        ) from exc
    if root == parent:
        raise ValidationError(
            "target root must be a strict child of disposable parent"
        )


def _run(
    argv: Sequence[str],
    *,
    cwd: Path,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        cwd=str(cwd),
        shell=False,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
    )


def _git(root: Path, *args: str) -> str:
    proc = _run(
        ["git", "-C", str(root), *args],
        cwd=root,
        timeout_seconds=30,
    )
    if proc.returncode != 0:
        raise ValidationError(
            f"git {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout.strip()


def _git_show_bytes(root: Path, rel: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(root), "show", f"HEAD:{rel}"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise ValidationError(
            "git show failed: "
            + proc.stderr.decode("utf-8", errors="replace").strip()
        )
    return proc.stdout


def _safe_target_file(root: Path, rel: str) -> Path:
    path = (root / rel).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValidationError(f"source path escapes target root: {rel}") from exc
    if not path.is_file():
        raise ValidationError(f"source file missing: {rel}")
    return path


def _assert_argv(name: str, argv: Any) -> list[str]:
    if not isinstance(argv, list) or not argv:
        raise ValidationError(f"validation command must be non-empty argv list: {name}")
    if not all(isinstance(item, str) and item for item in argv):
        raise ValidationError(f"validation argv contains invalid item: {name}")
    executable = Path(argv[0]).name.lower()
    if executable in FORBIDDEN_SHELL_EXECUTABLES:
        raise ValidationError(f"shell executable is forbidden in validation spec: {name}")
    return list(argv)


def _load_and_bind_inputs(
    *,
    root: Path,
    plan_path: Path,
    preflight_path: Path,
    authorization_path: Path,
    mutation_receipt_path: Path,
    validation_spec_path: Path,
) -> Dict[str, Any]:
    plan = _load(plan_path)
    preflight = _load(preflight_path)
    authorization = _load(authorization_path)
    mutation = _load(mutation_receipt_path)
    spec = _load(validation_spec_path)

    if plan.get("schema_version") != PLAN_SCHEMA:
        raise ValidationError("unexpected plan schema")
    if plan.get("status") != "DRY_RUN_REWRITE_PLAN_READY":
        raise ValidationError("plan is not ready")

    if preflight.get("schema_version") != PREFLIGHT_SCHEMA:
        raise ValidationError("unexpected preflight schema")
    if preflight.get("status") != "PREFLIGHT_VALIDATED":
        raise ValidationError("preflight is not validated")

    if authorization.get("schema_version") != AUTH_SCHEMA:
        raise ValidationError("unexpected authorization schema")
    if authorization.get("status") != "MUTATION_AUTHORIZED":
        raise ValidationError("authorization receipt is not authorized")

    if mutation.get("schema_version") != MUTATION_RECEIPT_SCHEMA:
        raise ValidationError("unexpected mutation receipt schema")
    if mutation.get("status") != "TEMP_WORKTREE_APPLIED":
        raise ValidationError("mutation receipt is not TEMP_WORKTREE_APPLIED")
    if mutation.get("rule") != RULE:
        raise ValidationError("mutation receipt rule mismatch")
    if (mutation.get("postconditions", {}) or {}).get("validated") is not False:
        raise ValidationError("input mutation receipt already claims postcondition validation")
    if (mutation.get("postconditions", {}) or {}).get("acceptance_granted") is not False:
        raise ValidationError("input mutation receipt already claims evidence acceptance")

    if spec.get("schema_version") != VALIDATION_SPEC_SCHEMA:
        raise ValidationError("unexpected postcondition validation spec schema")
    if spec.get("status") != "POSTCONDITION_VALIDATION_SPEC_READY":
        raise ValidationError("postcondition validation spec is not ready")

    digests = {
        "plan_digest": _digest_file(plan_path),
        "preflight_evidence_digest": _digest_file(preflight_path),
        "authorization_receipt_digest": _digest_file(authorization_path),
        "postcondition_validation_spec_digest": _digest_file(validation_spec_path),
    }
    receipt_bindings = mutation.get("bindings", {}) or {}
    for key, value in digests.items():
        if receipt_bindings.get(key) != value:
            raise ValidationError(f"mutation receipt binding mismatch: {key}")

    spec_digest = digests["postcondition_validation_spec_digest"]
    if preflight.get("postcondition_validation_spec_digest") != spec_digest:
        raise ValidationError("preflight validation-spec digest mismatch")
    auth_binding = authorization.get("binding", {}) or {}
    if auth_binding.get("postcondition_validation_spec_digest") != spec_digest:
        raise ValidationError("authorization validation-spec digest mismatch")
    if (
        auth_binding.get("preflight_evidence_digest")
        != digests["preflight_evidence_digest"]
    ):
        raise ValidationError("authorization preflight digest mismatch")

    target = mutation.get("target", {}) or {}
    candidate = mutation.get("candidate", {}) or {}
    plan_candidate = plan.get("candidate", {}) or {}
    spec_target = spec.get("target", {}) or {}
    expected_target = {
        "repository": target.get("repository"),
        "revision": target.get("revision"),
        "source_path": target.get("source_path"),
        "candidate_id": candidate.get("candidate_id"),
    }
    if plan_candidate.get("kind") != RULE:
        raise ValidationError("plan candidate kind mismatch")
    if plan_candidate.get("candidate_id") != expected_target["candidate_id"]:
        raise ValidationError("plan candidate id mismatch")
    if plan_candidate.get("source_path") != expected_target["source_path"]:
        raise ValidationError("plan source path mismatch")
    for key, value in expected_target.items():
        if spec_target.get(key) != value:
            raise ValidationError(f"validation spec target mismatch: {key}")

    policy = spec.get("policy", {}) or {}
    if policy.get("cwd") != "TARGET_ROOT":
        raise ValidationError("validation spec cwd must be TARGET_ROOT")
    if policy.get("shell") is not False:
        raise ValidationError("validation spec shell must be false")

    commands = spec.get("commands", {}) or {}
    command_map = {
        "parse_after_rewrite": _assert_argv(
            "parse_after_rewrite", commands.get("parse_after_rewrite")
        ),
        "focused_target_native_after": _assert_argv(
            "focused_target_native_after",
            commands.get("focused_target_native_after"),
        ),
        "target_typecheck_or_type_tests_after": _assert_argv(
            "target_typecheck_or_type_tests_after",
            commands.get("target_typecheck_or_type_tests_after"),
        ),
    }
    baseline_command = (preflight.get("baseline_validation", {}) or {}).get("command")
    if command_map["focused_target_native_after"] != baseline_command:
        raise ValidationError(
            "focused postcondition command does not equal preflight baseline command"
        )

    revision = _git(root, "rev-parse", "HEAD")
    if revision != expected_target["revision"]:
        raise ValidationError("target revision changed after mutation")

    root_digest = _digest_text(str(root))
    if target.get("target_root_realpath_sha256") != root_digest:
        raise ValidationError("target-root digest mismatch")

    return {
        "plan": plan,
        "preflight": preflight,
        "authorization": authorization,
        "mutation": mutation,
        "spec": spec,
        "digests": digests,
        "commands": command_map,
    }


def _assert_live_mutation_state(
    *,
    root: Path,
    plan: Mapping[str, Any],
    mutation: Mapping[str, Any],
) -> Dict[str, Any]:
    target = mutation.get("target", {}) or {}
    source_rel = str(target.get("source_path", ""))
    source_path = _safe_target_file(root, source_rel)

    rewrite = plan.get("planned_rewrite", {}) or {}
    mutation_state = mutation.get("mutation", {}) or {}

    before_bytes = _git_show_bytes(root, source_rel)
    before_hash = _digest_bytes(before_bytes)
    if before_hash != rewrite.get("before_source_sha256"):
        raise ValidationError("HEAD source hash does not match the dry-run plan")
    if before_hash != mutation_state.get("before_source_sha256"):
        raise ValidationError("HEAD source hash does not match mutation receipt")

    current_bytes = source_path.read_bytes()
    current_hash = _digest_bytes(current_bytes)
    planned_after_hash = rewrite.get("planned_source_sha256")

    if current_hash != planned_after_hash:
        raise ValidationError("live source hash does not match planned after hash")
    if current_hash != mutation_state.get("actual_after_source_sha256"):
        raise ValidationError("live source hash does not match mutation receipt")

    changed = [
        line.strip()
        for line in _git(root, "diff", "--name-only").splitlines()
        if line.strip()
    ]
    if changed != [source_rel]:
        raise ValidationError(f"unexpected changed path scope: {changed}")

    untracked = [
        line.strip()
        for line in _git(root, "ls-files", "--others", "--exclude-standard").splitlines()
        if line.strip()
    ]
    if untracked:
        raise ValidationError(f"unexpected untracked target files: {untracked}")

    _git(root, "diff", "--check")

    try:
        before_source = before_bytes.decode("utf-8")
        after_source = current_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError("reference validation requires UTF-8 source") from exc
    actual_diff = "".join(
        difflib.unified_diff(
            before_source.splitlines(keepends=True),
            after_source.splitlines(keepends=True),
            fromfile=f"a/{source_rel}",
            tofile=f"b/{source_rel}",
        )
    )
    planned_diff = str(rewrite.get("diff", ""))
    if actual_diff != planned_diff:
        raise ValidationError("live diff does not match the dry-run plan")

    actual_diff_digest = _digest_text(actual_diff)
    if actual_diff_digest != mutation_state.get("actual_diff_digest"):
        raise ValidationError("live diff digest does not match mutation receipt")
    if actual_diff_digest != mutation_state.get("planned_diff_digest"):
        raise ValidationError("live diff digest does not match planned diff digest")

    if mutation_state.get("authorization_consumed") is not True:
        raise ValidationError("authorization must remain consumed")

    return {
        "source_path": source_rel,
        "source_sha256": current_hash,
        "changed_paths": changed,
        "untracked_paths": untracked,
        "diff_digest": actual_diff_digest,
    }


def _assert_validation_did_not_mutate_target(
    *,
    root: Path,
    expected: Mapping[str, Any],
) -> None:
    source_path = _safe_target_file(root, str(expected["source_path"]))
    if _digest_file(source_path) != expected["source_sha256"]:
        raise ValidationError("validation command changed the target source")
    changed = [
        line.strip()
        for line in _git(root, "diff", "--name-only").splitlines()
        if line.strip()
    ]
    if changed != expected["changed_paths"]:
        raise ValidationError("validation command changed path scope")
    untracked = [
        line.strip()
        for line in _git(root, "ls-files", "--others", "--exclude-standard").splitlines()
        if line.strip()
    ]
    if untracked:
        raise ValidationError(
            f"validation command produced untracked target files: {untracked}"
        )
    _git(root, "diff", "--check")


def _dispose_worktree(root: Path) -> bool:
    if root.exists():
        shutil.rmtree(root)
    return not root.exists()


def validate_postconditions(
    *,
    root: Path,
    disposable_parent: Path,
    plan_path: Path,
    preflight_path: Path,
    authorization_path: Path,
    mutation_receipt_path: Path,
    validation_spec_path: Path,
    timeout_seconds: int,
) -> Dict[str, Any]:
    _assert_system_temp_target(root, disposable_parent)

    inputs = _load_and_bind_inputs(
        root=root,
        plan_path=plan_path,
        preflight_path=preflight_path,
        authorization_path=authorization_path,
        mutation_receipt_path=mutation_receipt_path,
        validation_spec_path=validation_spec_path,
    )
    live = _assert_live_mutation_state(
        root=root,
        plan=inputs["plan"],
        mutation=inputs["mutation"],
    )

    results = []
    failure: str | None = None
    for name in (
        "parse_after_rewrite",
        "focused_target_native_after",
        "target_typecheck_or_type_tests_after",
    ):
        argv = inputs["commands"][name]
        try:
            proc = _run(argv, cwd=root, timeout_seconds=timeout_seconds)
        except subprocess.TimeoutExpired:
            failure = f"{name}_timed_out"
            results.append(
                {
                    "name": name,
                    "argv": argv,
                    "exit_code": None,
                    "timed_out": True,
                }
            )
            break

        result = {
            "name": name,
            "argv": argv,
            "exit_code": proc.returncode,
            "timed_out": False,
            "stdout_sha256": _digest_text(proc.stdout),
            "stderr_sha256": _digest_text(proc.stderr),
        }
        results.append(result)

        try:
            _assert_validation_did_not_mutate_target(root=root, expected=live)
        except ValidationError as exc:
            failure = str(exc)
            break

        if proc.returncode != 0:
            failure = f"{name}_failed"
            break

    if failure is None:
        status = "POSTCONDITIONS_VALIDATED"
        disposition = "DISPOSED_AFTER_VALIDATION"
    else:
        status = "MUTATION_FAILED_WORKTREE_DISCARDED"
        disposition = "DISCARDED_AFTER_FAILURE"

    disposed = _dispose_worktree(root)
    if not disposed:
        status = "MUTATION_BOUNDARY_CONTAINMENT_FAILED"
        disposition = "DISPOSAL_FAILED"

    return {
        "schema_version": "plw-js-ts-v2-postcondition-validation-receipt-v1",
        "status": status,
        "rule": RULE,
        "target": {
            "repository": inputs["mutation"]["target"]["repository"],
            "revision": inputs["mutation"]["target"]["revision"],
            "source_path": live["source_path"],
            "target_root_realpath_sha256": _digest_text(str(root)),
        },
        "candidate": {
            "candidate_id": inputs["mutation"]["candidate"]["candidate_id"],
        },
        "bindings": {
            **inputs["digests"],
            "mutation_receipt_digest": _digest_file(mutation_receipt_path),
        },
        "validation": {
            "commands": results,
            "all_required_postconditions_passed": failure is None,
            "failure": failure,
            "same_focused_command_as_baseline": True,
            "source_sha256_before_disposal": live["source_sha256"],
            "diff_digest_before_disposal": live["diff_digest"],
        },
        "containment": {
            "authorization_consumed": True,
            "worktree_disposition": disposition,
            "worktree_disposed": disposed,
            "target_exists_after": root.exists(),
        },
        "postconditions": {
            "validated": status == "POSTCONDITIONS_VALIDATED",
            "evidence_acceptance_granted": False,
        },
        "authority": {
            "reference_validation_only": True,
            "product_mutation_surface_exposed": False,
            "automatic_patch_authority_granted": False,
            "generic_mutation_authority_granted": False,
            "upstream_mutation_authorized": False,
            "experiment_evidence_acceptance_authority_granted": False,
            "global_behavioral_equivalence_proven": False,
            "truth_commit": False,
        },
        "next_gate": (
            "TEMP_WORKTREE_EXPERIMENT_EVIDENCE_ACCEPTANCE_REFERENCE"
            if status == "POSTCONDITIONS_VALIDATED"
            else None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--disposable-parent", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--preflight", required=True)
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--mutation-receipt", required=True)
    parser.add_argument("--postcondition-validation-spec", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args()

    root = Path(args.target_root).resolve()
    output = Path(args.output).resolve()
    if args.timeout_seconds < 1 or args.timeout_seconds > 600:
        raise SystemExit("--timeout-seconds must be between 1 and 600")

    for path, label in (
        (Path(args.plan).resolve(), "dry-run plan"),
        (Path(args.preflight).resolve(), "preflight evidence"),
        (Path(args.authorization).resolve(), "authorization receipt"),
        (Path(args.mutation_receipt).resolve(), "mutation receipt"),
        (
            Path(args.postcondition_validation_spec).resolve(),
            "postcondition validation spec",
        ),
        (output, "postcondition validation receipt"),
    ):
        _require_outside_target(root, path, label)

    try:
        receipt = validate_postconditions(
            root=root,
            disposable_parent=Path(args.disposable_parent).resolve(),
            plan_path=Path(args.plan).resolve(),
            preflight_path=Path(args.preflight).resolve(),
            authorization_path=Path(args.authorization).resolve(),
            mutation_receipt_path=Path(args.mutation_receipt).resolve(),
            validation_spec_path=Path(args.postcondition_validation_spec).resolve(),
            timeout_seconds=args.timeout_seconds,
        )
    except (ValidationError, json.JSONDecodeError) as exc:
        failure = str(exc)
        disposed = _dispose_worktree(root)
        receipt = {
            "schema_version": "plw-js-ts-v2-postcondition-validation-receipt-v1",
            "status": (
                "MUTATION_FAILED_WORKTREE_DISCARDED"
                if disposed
                else "MUTATION_BOUNDARY_CONTAINMENT_FAILED"
            ),
            "rule": RULE,
            "validation": {
                "commands": [],
                "all_required_postconditions_passed": False,
                "failure": failure,
            },
            "containment": {
                "authorization_consumed": True,
                "worktree_disposition": (
                    "DISCARDED_AFTER_FAILURE" if disposed else "DISPOSAL_FAILED"
                ),
                "worktree_disposed": disposed,
                "target_exists_after": root.exists(),
            },
            "postconditions": {
                "validated": False,
                "evidence_acceptance_granted": False,
            },
            "authority": {
                "reference_validation_only": True,
                "experiment_evidence_acceptance_authority_granted": False,
                "truth_commit": False,
            },
            "next_gate": None,
        }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")

    print(
        json.dumps(
            {
                "status": receipt["status"],
                "postconditions_validated": receipt["postconditions"]["validated"],
                "worktree_disposed": receipt["containment"]["worktree_disposed"],
                "evidence_acceptance_granted": receipt["postconditions"][
                    "evidence_acceptance_granted"
                ],
            },
            sort_keys=True,
        )
    )
    return 0 if receipt["status"] == "POSTCONDITIONS_VALIDATED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
