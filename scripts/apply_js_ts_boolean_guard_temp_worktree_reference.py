#!/usr/bin/env python3
"""Reference-only boolean-guard mutation adapter for disposable temp worktrees.

This adapter is intentionally not a product mutation surface. It consumes an
already-reviewed dry-run plan, a read-only preflight receipt, an explicit
single-use authorization receipt, and a disposable-boundary receipt. It may
apply exactly one planned replacement inside a system temporary directory.

It stops at TEMP_WORKTREE_APPLIED. Postcondition acceptance is a separate gate.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping

RULE = "js_boolean_guard_return"
PLAN_SCHEMA = "plw-js-ts-v2-boolean-guard-dry-run-plan-v1"
PREFLIGHT_SCHEMA = "plw-js-ts-v2-mutation-preflight-v1"
AUTH_SCHEMA = "plw-js-ts-v2-mutation-authorization-v1"
BOUNDARY_SCHEMA = "plw-js-ts-v2-disposable-boundary-v1"
POSTCONDITION_SPEC_SCHEMA = "plw-js-ts-v2-postcondition-validation-spec-v1"


class AdapterError(ValueError):
    pass


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _digest_file(path: Path) -> str:
    return _digest_bytes(path.read_bytes())


def _digest_text(text: str) -> str:
    return _digest_bytes(text.encode("utf-8"))


def _safe_target_file(root: Path, rel: str) -> Path:
    path = (root / rel).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise AdapterError(f"source path escapes target root: {rel}") from exc
    if not path.is_file():
        raise AdapterError(f"source file missing: {rel}")
    return path


def _require_outside_target(root: Path, path: Path, label: str) -> None:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return
    raise AdapterError(f"{label} must be outside target root")


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise AdapterError(
            f"git {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout.strip()


def _assert_system_temp_target(root: Path, disposable_parent: Path) -> None:
    system_temp = Path(tempfile.gettempdir()).resolve()
    parent = disposable_parent.resolve()
    try:
        parent.relative_to(system_temp)
    except ValueError as exc:
        raise AdapterError("disposable parent must be under the system temp directory") from exc
    try:
        root.relative_to(parent)
    except ValueError as exc:
        raise AdapterError("target root must be inside the declared disposable parent") from exc
    if root == parent:
        raise AdapterError("target root must be a strict child of disposable parent")


def _assert_boundary(boundary: Mapping[str, Any], root: Path) -> None:
    if boundary.get("schema_version") != BOUNDARY_SCHEMA:
        raise AdapterError("unexpected disposable-boundary schema")
    if boundary.get("status") != "DISPOSABLE_BOUNDARY_READY":
        raise AdapterError("disposable boundary is not ready")
    if boundary.get("reference_only") is not True:
        raise AdapterError("disposable boundary must be reference-only")
    if boundary.get("primary_worktree") is not False:
        raise AdapterError("primary worktree is forbidden")
    if boundary.get("target_root_realpath") != str(root):
        raise AdapterError("disposable boundary target root mismatch")
    if boundary.get("target_root_realpath_sha256") != _digest_text(str(root)):
        raise AdapterError("disposable boundary root digest mismatch")


def _assert_plan(plan: Mapping[str, Any]) -> None:
    if plan.get("schema_version") != PLAN_SCHEMA:
        raise AdapterError("unexpected plan schema")
    if plan.get("status") != "DRY_RUN_REWRITE_PLAN_READY":
        raise AdapterError("plan is not ready")
    candidate = plan.get("candidate", {}) or {}
    if candidate.get("kind") != RULE:
        raise AdapterError("plan candidate kind mismatch")
    source_integrity = plan.get("source_integrity", {}) or {}
    if source_integrity.get("target_source_mutated") is not False:
        raise AdapterError("planner source-integrity boundary not satisfied")
    if source_integrity.get("source_unchanged_verified") is not True:
        raise AdapterError("planner did not verify unchanged source")
    authority = plan.get("authority", {}) or {}
    if authority.get("source_mutation_allowed") is not False:
        raise AdapterError("input plan unexpectedly grants mutation authority")


def _assert_postcondition_spec(
    spec: Mapping[str, Any],
    *,
    repository: str,
    revision: str,
    plan: Mapping[str, Any],
    preflight: Mapping[str, Any],
) -> None:
    if spec.get("schema_version") != POSTCONDITION_SPEC_SCHEMA:
        raise AdapterError("unexpected postcondition validation spec schema")
    if spec.get("status") != "POSTCONDITION_VALIDATION_SPEC_READY":
        raise AdapterError("postcondition validation spec is not ready")

    candidate = plan.get("candidate", {}) or {}
    target = spec.get("target", {}) or {}
    expected = {
        "repository": repository,
        "revision": revision,
        "source_path": candidate.get("source_path"),
        "candidate_id": candidate.get("candidate_id"),
    }
    for key, value in expected.items():
        if target.get(key) != value:
            raise AdapterError(f"postcondition validation spec target mismatch: {key}")

    policy = spec.get("policy", {}) or {}
    if policy.get("cwd") != "TARGET_ROOT":
        raise AdapterError("postcondition validation spec cwd must be TARGET_ROOT")
    if policy.get("shell") is not False:
        raise AdapterError("postcondition validation spec shell must be false")

    commands = spec.get("commands", {}) or {}
    required = (
        "parse_after_rewrite",
        "focused_target_native_after",
        "target_typecheck_or_type_tests_after",
    )
    for name in required:
        argv = commands.get(name)
        if not isinstance(argv, list) or not argv or not all(
            isinstance(item, str) and item for item in argv
        ):
            raise AdapterError(
                f"postcondition validation command must be non-empty argv list: {name}"
            )

    baseline = (preflight.get("baseline_validation", {}) or {}).get("command")
    if commands.get("focused_target_native_after") != baseline:
        raise AdapterError(
            "focused postcondition command must equal preflight baseline command"
        )


def _assert_preflight(
    preflight: Mapping[str, Any],
    *,
    root: Path,
    repository: str,
    revision: str,
    plan: Mapping[str, Any],
    plan_digest: str,
    postcondition_spec_digest: str,
) -> None:
    if preflight.get("schema_version") != PREFLIGHT_SCHEMA:
        raise AdapterError("unexpected preflight schema")
    if preflight.get("status") != "PREFLIGHT_VALIDATED":
        raise AdapterError("preflight is not validated")
    if (
        preflight.get("postcondition_validation_spec_digest")
        != postcondition_spec_digest
    ):
        raise AdapterError(
            "preflight postcondition validation spec digest mismatch"
        )

    target = preflight.get("target", {}) or {}
    candidate = plan.get("candidate", {}) or {}
    rewrite = plan.get("planned_rewrite", {}) or {}
    expected = {
        "repository": repository,
        "revision": revision,
        "source_path": candidate.get("source_path"),
        "candidate_id": candidate.get("candidate_id"),
        "target_root_realpath_sha256": _digest_text(str(root)),
    }
    for key, value in expected.items():
        if target.get(key) != value:
            raise AdapterError(f"preflight target binding mismatch: {key}")

    binding = preflight.get("plan_binding", {}) or {}
    checks = {
        "plan_digest": plan_digest,
        "before_source_sha256": rewrite.get("before_source_sha256"),
        "planned_source_sha256": rewrite.get("planned_source_sha256"),
        "planned_diff_digest": _digest_text(str(rewrite.get("diff", ""))),
    }
    for key, value in checks.items():
        if binding.get(key) != value:
            raise AdapterError(f"preflight plan binding mismatch: {key}")

    preflight_checks = preflight.get("checks", {}) or {}
    required_true = (
        "clean_checkout",
        "disposable_checkout",
        "upstream_push_credentials_disabled",
        "source_hash_matches_plan",
        "candidate_span_match_count_one",
        "baseline_validation_passed",
    )
    for key in required_true:
        if preflight_checks.get(key) is not True:
            raise AdapterError(f"preflight check must be true: {key}")
    if preflight_checks.get("primary_worktree") is not False:
        raise AdapterError("preflight must prove primary_worktree=false")


def _assert_authorization(
    authorization: Mapping[str, Any],
    *,
    repository: str,
    revision: str,
    plan: Mapping[str, Any],
    plan_digest: str,
    preflight_digest: str,
    postcondition_spec_digest: str,
) -> None:
    if authorization.get("schema_version") != AUTH_SCHEMA:
        raise AdapterError("unexpected authorization schema")
    if authorization.get("status") != "MUTATION_AUTHORIZED":
        raise AdapterError("mutation is not authorized")
    if authorization.get("authorized") is not True:
        raise AdapterError("authorization requires literal true")
    if authorization.get("authorization_scope") != "ONE_CANDIDATE_ONE_TARGET_ONE_PLAN":
        raise AdapterError("authorization scope mismatch")
    if authorization.get("single_use") is not True:
        raise AdapterError("authorization must be single-use")

    issuer = authorization.get("issuer", {}) or {}
    if issuer.get("external_to_planner") is not True:
        raise AdapterError("authorization issuer must be external to planner")
    if issuer.get("planner_self_authorized") is not False:
        raise AdapterError("planner self-authorization is forbidden")

    candidate = plan.get("candidate", {}) or {}
    rewrite = plan.get("planned_rewrite", {}) or {}
    expected = {
        "candidate_id": candidate.get("candidate_id"),
        "target_repository": repository,
        "target_revision": revision,
        "source_path": candidate.get("source_path"),
        "before_source_sha256": rewrite.get("before_source_sha256"),
        "planned_source_sha256": rewrite.get("planned_source_sha256"),
        "plan_digest": plan_digest,
        "preflight_evidence_digest": preflight_digest,
        "postcondition_validation_spec_digest": postcondition_spec_digest,
    }
    binding = authorization.get("binding", {}) or {}
    for key, value in expected.items():
        if binding.get(key) != value:
            raise AdapterError(f"authorization binding mismatch: {key}")

    authority = authorization.get("authority", {}) or {}
    for key in (
        "generic_mutation_authority_granted",
        "automatic_patch_authority_granted",
        "upstream_mutation_authorized",
        "global_behavioral_equivalence_proven",
    ):
        if authority.get(key) is not False:
            raise AdapterError(f"authorization may not grant {key}")


def _authorization_consumed(ledger: Path, authorization_digest: str) -> bool:
    if not ledger.exists():
        return False
    for raw in ledger.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        row = json.loads(raw)
        if row.get("authorization_digest") == authorization_digest:
            return True
    return False


def _consume_authorization(
    ledger: Path,
    *,
    authorization_digest: str,
    plan_digest: str,
    candidate_id: str,
) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema_version": "plw-js-ts-v2-authorization-consumption-v1",
        "status": "CONSUMED_FOR_EXECUTION_ATTEMPT",
        "authorization_digest": authorization_digest,
        "plan_digest": plan_digest,
        "candidate_id": candidate_id,
    }
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _member_segment(source: str, line_start: int, line_end: int) -> str:
    lines = source.splitlines(keepends=True)
    start = line_start - 1
    end = line_end
    if start < 0 or end > len(lines) or end <= start:
        raise AdapterError("candidate member line span is invalid")
    return "".join(lines[start:end])


def apply_reference_mutation(
    *,
    root: Path,
    disposable_parent: Path,
    repository: str,
    plan_path: Path,
    postcondition_spec_path: Path,
    preflight_path: Path,
    authorization_path: Path,
    boundary_path: Path,
    ledger_path: Path,
) -> Dict[str, Any]:
    root = root.resolve()
    _assert_system_temp_target(root, disposable_parent)

    for path, label in (
        (plan_path, "dry-run plan"),
        (postcondition_spec_path, "postcondition validation spec"),
        (preflight_path, "preflight evidence"),
        (authorization_path, "authorization receipt"),
        (boundary_path, "disposable-boundary receipt"),
        (ledger_path, "authorization consumption ledger"),
    ):
        _require_outside_target(root, path, label)

    plan = _load(plan_path)
    postcondition_spec = _load(postcondition_spec_path)
    preflight = _load(preflight_path)
    authorization = _load(authorization_path)
    boundary = _load(boundary_path)

    _assert_plan(plan)
    _assert_boundary(boundary, root)

    plan_digest = _digest_file(plan_path)
    postcondition_spec_digest = _digest_file(postcondition_spec_path)
    preflight_digest = _digest_file(preflight_path)
    authorization_digest = _digest_file(authorization_path)

    revision = _git(root, "rev-parse", "HEAD")
    _assert_postcondition_spec(
        postcondition_spec,
        repository=repository,
        revision=revision,
        plan=plan,
        preflight=preflight,
    )
    _assert_preflight(
        preflight,
        root=root,
        repository=repository,
        revision=revision,
        plan=plan,
        plan_digest=plan_digest,
        postcondition_spec_digest=postcondition_spec_digest,
    )
    _assert_authorization(
        authorization,
        repository=repository,
        revision=revision,
        plan=plan,
        plan_digest=plan_digest,
        preflight_digest=preflight_digest,
        postcondition_spec_digest=postcondition_spec_digest,
    )

    if _authorization_consumed(ledger_path, authorization_digest):
        raise AdapterError("authorization receipt has already been consumed")

    if _git(root, "status", "--porcelain", "--untracked-files=all"):
        raise AdapterError("target checkout must be clean immediately before execution")

    candidate = plan["candidate"]
    match = plan.get("match", {}) or {}
    rewrite = plan["planned_rewrite"]
    rel = str(candidate["source_path"])
    source_path = _safe_target_file(root, rel)

    before_bytes = source_path.read_bytes()
    if _digest_bytes(before_bytes) != rewrite.get("before_source_sha256"):
        raise AdapterError("source hash no longer matches plan")

    source = before_bytes.decode("utf-8")
    before_text = str(rewrite.get("before", ""))
    after_text = str(rewrite.get("after", ""))
    start = int(match.get("source_char_start", -1))
    end = int(match.get("source_char_end", -1))
    if start < 0 or end <= start or source[start:end] != before_text:
        raise AdapterError("exact planned source span no longer matches")

    member_segment = _member_segment(
        source,
        int(candidate.get("member_line_start", 0) or 0),
        int(candidate.get("member_line_end", 0) or 0),
    )
    if member_segment.count(before_text) != 1:
        raise AdapterError("candidate span must match exactly once inside member")

    planned = source[:start] + after_text + source[end:]
    planned_bytes = planned.encode("utf-8")
    if _digest_bytes(planned_bytes) != rewrite.get("planned_source_sha256"):
        raise AdapterError("locally reconstructed planned hash mismatches plan")

    actual_planned_diff = "".join(
        difflib.unified_diff(
            source.splitlines(keepends=True),
            planned.splitlines(keepends=True),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
        )
    )
    if actual_planned_diff != rewrite.get("diff"):
        raise AdapterError("locally reconstructed diff mismatches plan")

    _consume_authorization(
        ledger_path,
        authorization_digest=authorization_digest,
        plan_digest=plan_digest,
        candidate_id=str(candidate.get("candidate_id")),
    )

    source_path.write_bytes(planned_bytes)

    after_bytes = source_path.read_bytes()
    if _digest_bytes(after_bytes) != rewrite.get("planned_source_sha256"):
        raise AdapterError("actual after-source hash mismatches plan")

    actual_diff = "".join(
        difflib.unified_diff(
            source.splitlines(keepends=True),
            after_bytes.decode("utf-8").splitlines(keepends=True),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
        )
    )
    if actual_diff != rewrite.get("diff"):
        raise AdapterError("actual diff mismatches planned diff")

    changed = [
        line.strip()
        for line in _git(root, "diff", "--name-only").splitlines()
        if line.strip()
    ]
    untracked = [
        line.strip()
        for line in _git(root, "ls-files", "--others", "--exclude-standard").splitlines()
        if line.strip()
    ]
    if changed != [rel]:
        raise AdapterError(f"unexpected changed path scope: {changed}")
    if untracked:
        raise AdapterError(f"unexpected untracked target files: {untracked}")

    _git(root, "diff", "--check")

    return {
        "schema_version": "plw-js-ts-v2-temp-worktree-mutation-adapter-receipt-v1",
        "status": "TEMP_WORKTREE_APPLIED",
        "rule": RULE,
        "target": {
            "repository": repository,
            "revision": revision,
            "source_path": rel,
            "disposable_parent": str(disposable_parent.resolve()),
            "target_root_realpath_sha256": _digest_text(str(root)),
        },
        "candidate": {
            "candidate_id": candidate.get("candidate_id"),
            "member_line_start": candidate.get("member_line_start"),
            "member_line_end": candidate.get("member_line_end"),
        },
        "bindings": {
            "plan_digest": plan_digest,
            "preflight_evidence_digest": preflight_digest,
            "authorization_receipt_digest": authorization_digest,
            "disposable_boundary_digest": _digest_file(boundary_path),
            "postcondition_validation_spec_digest": postcondition_spec_digest,
        },
        "mutation": {
            "before_source_sha256": rewrite.get("before_source_sha256"),
            "planned_source_sha256": rewrite.get("planned_source_sha256"),
            "actual_after_source_sha256": _digest_bytes(after_bytes),
            "planned_diff_digest": _digest_text(str(rewrite.get("diff", ""))),
            "actual_diff_digest": _digest_text(actual_diff),
            "changed_paths": changed,
            "untracked_target_paths": untracked,
            "git_diff_check": "PASS",
            "authorization_consumed": True,
        },
        "postconditions": {
            "validated": False,
            "acceptance_granted": False,
        },
        "authority": {
            "reference_adapter_only": True,
            "product_mutation_surface_exposed": False,
            "automatic_patch_authority_granted": False,
            "generic_mutation_authority_granted": False,
            "upstream_mutation_authorized": False,
            "postcondition_acceptance_authority_granted": False,
            "global_behavioral_equivalence_proven": False,
            "truth_commit": False,
        },
        "next_gate": "TEMP_WORKTREE_POSTCONDITION_VALIDATION_REFERENCE",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--disposable-parent", required=True)
    parser.add_argument("--target-repository", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--postcondition-validation-spec", required=True)
    parser.add_argument("--preflight", required=True)
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--disposable-boundary", required=True)
    parser.add_argument("--consumption-ledger", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-reference-mutation", action="store_true")
    args = parser.parse_args()

    if not args.allow_reference_mutation:
        raise SystemExit("literal --allow-reference-mutation is required")

    root = Path(args.target_root).resolve()
    output = Path(args.output).resolve()
    ledger = Path(args.consumption_ledger).resolve()
    _require_outside_target(root, output, "adapter receipt")
    _require_outside_target(root, ledger, "authorization consumption ledger")

    try:
        receipt = apply_reference_mutation(
            root=root,
            disposable_parent=Path(args.disposable_parent),
            repository=args.target_repository,
            plan_path=Path(args.plan).resolve(),
            postcondition_spec_path=Path(
                args.postcondition_validation_spec
            ).resolve(),
            preflight_path=Path(args.preflight).resolve(),
            authorization_path=Path(args.authorization).resolve(),
            boundary_path=Path(args.disposable_boundary).resolve(),
            ledger_path=ledger,
        )
    except AdapterError as exc:
        print(json.dumps({"status": "MUTATION_BOUNDARY_REJECTED", "error": str(exc)}))
        return 2

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "candidate_id": receipt["candidate"]["candidate_id"],
                "changed_paths": receipt["mutation"]["changed_paths"],
                "postconditions_validated": receipt["postconditions"]["validated"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
