#!/usr/bin/env python3
"""Apply the promoted bounded JS/TS boolean-guard mutation capability.

This is an internal capability implementation, not a public PLW command.
It narrows the reusable read-only planner to the sealed-evidence-supported
mutation subset and composes the existing fail-closed reference executor.

The capability stops after BOUNDED_MUTATION_CAPABILITY_APPLIED.
Postcondition validation and evidence acceptance remain separate transitions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from apply_js_ts_boolean_guard_temp_worktree_reference import (
    AdapterError,
    apply_reference_mutation,
)
from plan_js_ts_boolean_guard_rewrite import IDENT, STRING

CAPABILITY_SCHEMA = "plw-js-ts-v2-bounded-boolean-guard-mutation-capability-v1"
CAPABILITY_ID = "js_boolean_guard.strict_equality_string.temp_worktree.v1"
RULE = "js_boolean_guard_return"
READY_STATUSES = {
    "IMPLEMENTED_PENDING_INTERACTIVE_VALIDATION",
    "BOUNDED_MUTATION_CAPABILITY_READY",
}
STRICT_EQUAL_STRING_RE = re.compile(
    rf"^\s*{IDENT}\s*===\s*{STRING}\s*$"
)
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
BASELINE_COMMAND_KEYS = (
    "parse_after_rewrite",
    "focused_target_native_after",
    "target_typecheck_or_type_tests_after",
)


class CapabilityError(ValueError):
    pass


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _digest_file(path: Path) -> str:
    return _digest_bytes(path.read_bytes())


def _digest_text(text: str) -> str:
    return _digest_bytes(text.encode("utf-8"))


def _canonical_digest(payload: Mapping[str, Any]) -> str:
    return _digest_bytes(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    )


def _require_outside_target(root: Path, path: Path, label: str) -> None:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return
    raise CapabilityError(f"{label} must be outside target root")


def _assert_system_temp_target(root: Path, disposable_parent: Path) -> None:
    system_temp = Path(tempfile.gettempdir()).resolve()
    parent = disposable_parent.resolve()
    try:
        parent.relative_to(system_temp)
    except ValueError as exc:
        raise CapabilityError(
            "disposable parent must be under the system temp directory"
        ) from exc
    try:
        root.relative_to(parent)
    except ValueError as exc:
        raise CapabilityError(
            "target root must be inside the disposable parent"
        ) from exc
    if root == parent:
        raise CapabilityError(
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


def _git_status(root: Path) -> str:
    proc = _run(
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
        cwd=root,
        timeout_seconds=30,
    )
    if proc.returncode != 0:
        raise CapabilityError(
            "git status failed: " + (proc.stderr.strip() or proc.stdout.strip())
        )
    return proc.stdout.strip()


def _assert_contract(
    contract: Mapping[str, Any],
    *,
    allow_pending: bool,
) -> None:
    if contract.get("schema_version") != CAPABILITY_SCHEMA:
        raise CapabilityError("unexpected capability contract schema")
    if contract.get("capability_id") != CAPABILITY_ID:
        raise CapabilityError("capability id mismatch")
    if contract.get("rule") != RULE:
        raise CapabilityError("capability rule mismatch")

    status = contract.get("implementation_status")
    if status not in READY_STATUSES:
        raise CapabilityError("capability implementation status is not usable")
    if (
        status == "IMPLEMENTED_PENDING_INTERACTIVE_VALIDATION"
        and not allow_pending
    ):
        raise CapabilityError(
            "pending implementation requires --allow-pending-implementation"
        )

    scope = contract.get("scope", {}) or {}
    if scope.get("source_extensions") != [".js", ".ts"]:
        raise CapabilityError("capability source-extension scope drifted")
    condition = scope.get("condition", {}) or {}
    if condition.get("operator") != "===":
        raise CapabilityError("capability operator scope drifted")
    if condition.get("right_operand") != "STRING_LITERAL":
        raise CapabilityError("capability right-operand scope drifted")
    if scope.get("transformations") != ["positive", "inverse"]:
        raise CapabilityError("capability transformation scope drifted")
    if scope.get("comparison_operator_complement_folding") is not False:
        raise CapabilityError("operator-complement folding must remain disabled")

    authority = contract.get("authority", {}) or {}
    if authority.get("internal_capability_implemented") is not True:
        raise CapabilityError("capability implementation authority missing")
    for key in (
        "public_product_surface_exposed",
        "automatic_patch_authority_granted",
        "generic_mutation_authority_granted",
        "primary_worktree_mutation_authorized",
        "commit_creation_authorized",
        "push_authorized",
        "pull_request_creation_authorized",
        "upstream_mutation_authorized",
        "postcondition_acceptance_authority_granted",
        "evidence_acceptance_authority_granted",
        "global_behavioral_equivalence_proven",
        "truth_commit",
    ):
        if authority.get(key) is not False:
            raise CapabilityError(f"capability contract unexpectedly grants {key}")


def _assert_plan_scope(plan: Mapping[str, Any]) -> Dict[str, Any]:
    if plan.get("schema_version") != "plw-js-ts-v2-boolean-guard-dry-run-plan-v1":
        raise CapabilityError("unexpected planner schema")
    if plan.get("status") != "DRY_RUN_REWRITE_PLAN_READY":
        raise CapabilityError("planner result is not ready")

    candidate = plan.get("candidate", {}) or {}
    if candidate.get("kind") != RULE:
        raise CapabilityError("plan rule is outside promoted capability")

    source_path = str(candidate.get("source_path", ""))
    suffix = Path(source_path).suffix.lower()
    if suffix not in {".js", ".ts"}:
        raise CapabilityError(
            f"source extension is outside promoted scope: {suffix or '<none>'}"
        )

    match = plan.get("match", {}) or {}
    condition = str(match.get("condition", ""))
    if "?." in condition:
        raise CapabilityError(
            "optional chaining is outside the promoted evidence subset"
        )
    if not STRICT_EQUAL_STRING_RE.fullmatch(condition):
        raise CapabilityError(
            "condition is outside IDENT === STRING promoted subset"
        )
    if match.get("condition_boolean_proof") != "BOUNDED_SYNTAX_ALLOWLIST":
        raise CapabilityError("bounded boolean proof is required")

    transformation = match.get("transformation")
    if transformation not in {"positive", "inverse"}:
        raise CapabilityError("unsupported transformation")

    semicolon_style = match.get("semicolon_style")
    if semicolon_style not in {"semicolon", "no_semicolon"}:
        raise CapabilityError("unsupported semicolon style")

    rewrite = plan.get("planned_rewrite", {}) or {}
    before = str(rewrite.get("before", ""))
    after = str(rewrite.get("after", ""))
    indent_match = re.match(r"^([ \t]*)", before)
    indent = indent_match.group(1) if indent_match else ""
    semi = ";" if semicolon_style == "semicolon" else ""
    if transformation == "positive":
        expected_after = f"{indent}return {condition}{semi}"
    else:
        expected_after = f"{indent}return !({condition}){semi}"
    if after != expected_after:
        raise CapabilityError(
            "planner output is not the exact promoted conservative rewrite"
        )

    authority = plan.get("authority", {}) or {}
    if authority.get("source_mutation_allowed") is not False:
        raise CapabilityError("input planner must remain read-only")
    if authority.get("automatic_patch_authority_granted") is not False:
        raise CapabilityError("input planner unexpectedly grants auto-patch authority")
    if authority.get("upstream_mutation_authorized") is not False:
        raise CapabilityError("input planner unexpectedly grants upstream mutation")

    return {
        "source_extension": suffix,
        "condition_family": "IDENT_STRICT_EQUAL_STRING",
        "transformation": transformation,
        "semicolon_style": semicolon_style,
        "condition": condition,
    }


def _assert_capability_authorization(
    authorization: Mapping[str, Any],
    *,
    contract_digest: str,
) -> None:
    binding = authorization.get("binding", {}) or {}
    if binding.get("capability_id") != CAPABILITY_ID:
        raise CapabilityError("authorization does not bind promoted capability id")
    if binding.get("capability_contract_digest") != contract_digest:
        raise CapabilityError("authorization capability contract digest mismatch")


def _verify_candidate_provenance(
    *,
    root: Path,
    provenance_path: Path,
    plan: Mapping[str, Any],
    authorization: Mapping[str, Any],
) -> Dict[str, Any]:
    from core.candidate_provenance import run_candidate_provenance

    supplied = _load(provenance_path)
    selection = supplied.get("candidate_selection", {}) or {}
    route = supplied.get("candidate_capability_match", {}) or {}
    snapshot = supplied.get("discovery_snapshot", {}) or {}
    task = selection.get("task")
    if not isinstance(task, str) or not task.strip():
        raise CapabilityError("candidate provenance task is missing")

    try:
        current = run_candidate_provenance(
            str(root), task, include_capability_match=True
        )
    except (OSError, TypeError, ValueError) as exc:
        raise CapabilityError(f"candidate provenance revalidation failed: {exc}") from exc
    if _canonical_digest(current) != _canonical_digest(supplied):
        raise CapabilityError("candidate provenance does not match current target discovery")
    if selection.get("resolution") != "RESOLVED":
        raise CapabilityError("candidate selection is not resolved")
    if route.get("status") != "CAPABILITY_MATCHED":
        raise CapabilityError("selected candidate has no exact internal capability match")
    if route.get("matched_capability_id") != CAPABILITY_ID:
        raise CapabilityError("candidate route selected a different capability")

    selected_id = selection.get("selected_candidate_id")
    selected_instance = selection.get("selected_candidate_instance_id")
    selected_path = selection.get("selected_source_path")
    candidate = (plan.get("candidate", {}) or {})
    site = (route.get("match_facts", {}) or {}).get("source_site", {}) or {}
    plan_bindings = {
        "candidate_id": selected_id,
        "candidate_instance_id": selected_instance,
        "kind": selection.get("candidate_kind"),
        "source_path": selected_path,
        "source_site_sha256": site.get("matched_source_sha256"),
        "source_char_start": site.get("char_start"),
        "source_char_end": site.get("char_end"),
    }
    for key, expected in plan_bindings.items():
        if candidate.get(key) != expected:
            raise CapabilityError(f"dry-run plan is not bound to selected candidate: {key}")

    discovery_digest = snapshot.get("discovery_snapshot_digest")
    target_revision_info = snapshot.get("target_revision", {}) or {}
    target_revision = target_revision_info.get("git_head")
    target_tree = target_revision_info.get("git_tree")
    if (
        target_revision_info.get("working_tree_clean") is not True
        or target_revision_info.get("working_tree_status_observed") is not True
    ):
        raise CapabilityError("candidate provenance target was not observed clean")
    candidate_set_digest = (snapshot.get("candidate_set", {}) or {}).get(
        "candidate_set_digest"
    )
    selection_digest = selection.get("candidate_selection_digest")
    contract_digest = route.get("capability_contract_digest")
    if (
        not isinstance(target_revision, str)
        or not target_revision
        or route.get("discovery_snapshot_digest") != discovery_digest
        or route.get("candidate_set_digest") != candidate_set_digest
        or route.get("selected_candidate_id") != selected_id
        or route.get("selected_candidate_instance_id") != selected_instance
        or selection.get("discovery_snapshot_digest") != discovery_digest
        or selection.get("candidate_set_digest") != candidate_set_digest
    ):
        raise CapabilityError("candidate provenance lineage fields disagree")

    summary = {
        "candidate_provenance_digest": _canonical_digest(supplied),
        "candidate_task_digest": _digest_text(task),
        "resolution": selection.get("resolution"),
        "target_revision": target_revision,
        "target_tree": target_tree,
        "target_revision_digest": target_revision_info.get("target_revision_digest"),
        "working_tree_status_digest": target_revision_info.get(
            "working_tree_status_digest"
        ),
        "shared_graph_content_signature": snapshot.get(
            "shared_graph_content_signature"
        ),
        "discovery_snapshot_digest": discovery_digest,
        "candidate_set_digest": candidate_set_digest,
        "candidate_selection_digest": selection_digest,
        "selected_candidate_id": selected_id,
        "selected_candidate_instance_id": selected_instance,
        "selected_source_path": selected_path,
        "selected_symbol": selection.get("selected_symbol"),
        "candidate_kind": selection.get("candidate_kind"),
        "selection_basis": selection.get("selection_basis", []),
        "selection_basis_digest": _canonical_digest(
            {"selection_basis": selection.get("selection_basis", [])}
        ),
        "selection_confidence_boundary": selection.get(
            "selection_confidence_boundary"
        ),
        "rejected_alternative_count": len(
            selection.get("rejected_alternatives", []) or []
        ),
        "rejected_alternatives_digest": _canonical_digest(
            {"rejected_alternatives": selection.get("rejected_alternatives", []) or []}
        ),
        "matched_capability_id": route.get("matched_capability_id"),
        "capability_contract_digest": contract_digest,
        "source_site_sha256": site.get("matched_source_sha256"),
        "source_char_start": site.get("char_start"),
        "source_char_end": site.get("char_end"),
    }
    expected_authorization = {
        "candidate_provenance_digest": summary["candidate_provenance_digest"],
        "candidate_task_digest": summary["candidate_task_digest"],
        "target_revision": target_revision,
        "target_tree": target_tree,
        "target_revision_digest": summary["target_revision_digest"],
        "working_tree_status_digest": summary[
            "working_tree_status_digest"
        ],
        "shared_graph_content_signature": summary[
            "shared_graph_content_signature"
        ],
        "discovery_snapshot_digest": discovery_digest,
        "candidate_set_digest": candidate_set_digest,
        "candidate_selection_digest": selection_digest,
        "selected_candidate_id": selected_id,
        "selected_candidate_instance_id": selected_instance,
        "selected_source_path": selected_path,
        "selected_symbol": summary["selected_symbol"],
        "candidate_kind": summary["candidate_kind"],
        "selection_basis_digest": summary["selection_basis_digest"],
        "selection_confidence_boundary": summary[
            "selection_confidence_boundary"
        ],
        "rejected_alternative_count": summary["rejected_alternative_count"],
        "rejected_alternatives_digest": summary[
            "rejected_alternatives_digest"
        ],
        "source_site_sha256": summary["source_site_sha256"],
        "source_char_start": summary["source_char_start"],
        "source_char_end": summary["source_char_end"],
        "matched_capability_id": summary["matched_capability_id"],
        "candidate_capability_contract_digest": contract_digest,
    }
    auth_binding = authorization.get("binding", {}) or {}
    for key, expected in expected_authorization.items():
        if auth_binding.get(key) != expected:
            raise CapabilityError(
                f"authorization does not bind selected candidate provenance: {key}"
            )
    return summary


def _assert_argv(name: str, argv: Any) -> list[str]:
    if not isinstance(argv, list) or not argv:
        raise CapabilityError(f"validation command must be argv: {name}")
    if not all(isinstance(item, str) and item for item in argv):
        raise CapabilityError(f"invalid validation argv item: {name}")
    if Path(argv[0]).name.lower() in FORBIDDEN_SHELL_EXECUTABLES:
        raise CapabilityError(f"shell executable is forbidden: {name}")
    return list(argv)


def _revalidate_baseline_before_write(
    *,
    root: Path,
    spec: Mapping[str, Any],
    preflight: Mapping[str, Any],
    timeout_seconds: int,
) -> list[Dict[str, Any]]:
    policy = spec.get("policy", {}) or {}
    if policy.get("cwd") != "TARGET_ROOT":
        raise CapabilityError("validation spec cwd must be TARGET_ROOT")
    if policy.get("shell") is not False:
        raise CapabilityError("validation spec shell must be false")

    commands = spec.get("commands", {}) or {}
    recorded = preflight.get("postcondition_baseline_validation", {}) or {}
    results: list[Dict[str, Any]] = []

    if _git_status(root):
        raise CapabilityError(
            "target must be clean before capability baseline revalidation"
        )

    for name in BASELINE_COMMAND_KEYS:
        argv = _assert_argv(name, commands.get(name))
        record = recorded.get(name, {}) or {}
        if record.get("command") != argv:
            raise CapabilityError(
                f"preflight baseline command does not match spec: {name}"
            )
        if record.get("exit_code") != 0:
            raise CapabilityError(
                f"preflight baseline did not pass before authorization: {name}"
            )

        try:
            proc = _run(argv, cwd=root, timeout_seconds=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            raise CapabilityError(
                f"prewrite baseline command timed out: {name}"
            ) from exc

        result = {
            "name": name,
            "argv": argv,
            "exit_code": proc.returncode,
            "stdout_sha256": _digest_text(proc.stdout),
            "stderr_sha256": _digest_text(proc.stderr),
        }
        results.append(result)
        if proc.returncode != 0:
            raise CapabilityError(
                f"prewrite baseline command failed: {name}"
            )
        dirty = _git_status(root)
        if dirty:
            raise CapabilityError(
                f"prewrite baseline command changed target checkout: {name}"
            )

    focused = (preflight.get("baseline_validation", {}) or {}).get("command")
    if focused != commands.get("focused_target_native_after"):
        raise CapabilityError(
            "focused preflight baseline command does not match validation spec"
        )
    return results


def apply_bounded_capability(
    *,
    root: Path,
    disposable_parent: Path,
    repository: str,
    capability_contract_path: Path,
    plan_path: Path,
    postcondition_spec_path: Path,
    preflight_path: Path,
    authorization_path: Path,
    boundary_path: Path,
    ledger_path: Path,
    timeout_seconds: int,
    allow_pending: bool,
    candidate_provenance_path: Path | None = None,
) -> Dict[str, Any]:
    root = root.resolve()
    _assert_system_temp_target(root, disposable_parent)

    for path, label in (
        (capability_contract_path, "capability contract"),
        (plan_path, "dry-run plan"),
        (postcondition_spec_path, "postcondition validation spec"),
        (preflight_path, "preflight evidence"),
        (authorization_path, "authorization receipt"),
        (boundary_path, "disposable boundary"),
        (ledger_path, "authorization consumption ledger"),
    ):
        _require_outside_target(root, path, label)
    if candidate_provenance_path is not None:
        _require_outside_target(root, candidate_provenance_path, "candidate provenance")

    contract = _load(capability_contract_path)
    plan = _load(plan_path)
    spec = _load(postcondition_spec_path)
    preflight = _load(preflight_path)
    authorization = _load(authorization_path)

    _assert_contract(contract, allow_pending=allow_pending)
    scope = _assert_plan_scope(plan)

    contract_digest = _digest_file(capability_contract_path)
    _assert_capability_authorization(
        authorization,
        contract_digest=contract_digest,
    )
    if candidate_provenance_path is not None:
        candidate_provenance = _verify_candidate_provenance(
            root=root,
            provenance_path=candidate_provenance_path,
            plan=plan,
            authorization=authorization,
        )
    else:
        auth_binding = authorization.get("binding", {}) or {}
        if any(
            key in auth_binding
            for key in (
                "candidate_provenance_digest",
                "candidate_selection_digest",
                "discovery_snapshot_digest",
            )
        ):
            raise CapabilityError(
                "authorization binds candidate provenance but no provenance artifact was supplied"
            )
        candidate_provenance = None

    baseline_results = _revalidate_baseline_before_write(
        root=root,
        spec=spec,
        preflight=preflight,
        timeout_seconds=timeout_seconds,
    )

    try:
        primitive = apply_reference_mutation(
            root=root,
            disposable_parent=disposable_parent,
            repository=repository,
            plan_path=plan_path,
            postcondition_spec_path=postcondition_spec_path,
            preflight_path=preflight_path,
            authorization_path=authorization_path,
            boundary_path=boundary_path,
            ledger_path=ledger_path,
        )
    except AdapterError as exc:
        raise CapabilityError(str(exc)) from exc

    if primitive.get("status") != "TEMP_WORKTREE_APPLIED":
        raise CapabilityError("trusted reference primitive did not reach expected state")
    if (primitive.get("postconditions", {}) or {}).get("validated") is not False:
        raise CapabilityError("mutation primitive must stop before postconditions")

    receipt = {
        "schema_version": "plw-js-ts-v2-bounded-mutation-capability-receipt-v1",
        "status": "BOUNDED_MUTATION_CAPABILITY_APPLIED",
        "capability_id": CAPABILITY_ID,
        "rule": RULE,
        "capability_contract_digest": contract_digest,
        "scope_proof": scope,
        "prewrite_baseline_revalidation": {
            "status": "PASS",
            "commands": baseline_results,
            "checkout_clean_after_all_commands": True,
        },
        "primitive": {
            "schema_version": primitive.get("schema_version"),
            "status": primitive.get("status"),
            "canonical_receipt_digest": _canonical_digest(primitive),
            "receipt": primitive,
        },
        "postconditions": {
            "validated": False,
            "evidence_acceptance_granted": False,
        },
        "authority": {
            "bounded_internal_capability_applied": True,
            "public_product_surface_exposed": False,
            "automatic_patch_authority_granted": False,
            "generic_mutation_authority_granted": False,
            "primary_worktree_mutation_authorized": False,
            "commit_creation_authorized": False,
            "push_authorized": False,
            "pull_request_creation_authorized": False,
            "upstream_mutation_authorized": False,
            "postcondition_acceptance_authority_granted": False,
            "evidence_acceptance_authority_granted": False,
            "global_behavioral_equivalence_proven": False,
            "truth_commit": False,
        },
        "next_gate": "TEMP_WORKTREE_POSTCONDITION_VALIDATION_REFERENCE",
    }
    if candidate_provenance is not None:
        receipt["candidate_provenance"] = candidate_provenance
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--disposable-parent", required=True)
    parser.add_argument("--target-repository", required=True)
    parser.add_argument("--capability-contract", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--postcondition-validation-spec", required=True)
    parser.add_argument("--preflight", required=True)
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--disposable-boundary", required=True)
    parser.add_argument("--consumption-ledger", required=True)
    parser.add_argument("--candidate-provenance")
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--allow-bounded-mutation", action="store_true")
    parser.add_argument("--allow-pending-implementation", action="store_true")
    args = parser.parse_args()

    if not args.allow_bounded_mutation:
        raise SystemExit("literal --allow-bounded-mutation is required")
    if args.timeout_seconds < 1 or args.timeout_seconds > 1200:
        raise SystemExit("--timeout-seconds must be between 1 and 1200")

    root = Path(args.target_root).resolve()
    output = Path(args.output).resolve()
    _require_outside_target(root, output, "capability output receipt")

    try:
        receipt = apply_bounded_capability(
            root=root,
            disposable_parent=Path(args.disposable_parent).resolve(),
            repository=args.target_repository,
            capability_contract_path=Path(args.capability_contract).resolve(),
            plan_path=Path(args.plan).resolve(),
            postcondition_spec_path=Path(
                args.postcondition_validation_spec
            ).resolve(),
            preflight_path=Path(args.preflight).resolve(),
            authorization_path=Path(args.authorization).resolve(),
            boundary_path=Path(args.disposable_boundary).resolve(),
            ledger_path=Path(args.consumption_ledger).resolve(),
            timeout_seconds=args.timeout_seconds,
            allow_pending=args.allow_pending_implementation,
            candidate_provenance_path=(
                Path(args.candidate_provenance).resolve()
                if args.candidate_provenance
                else None
            ),
        )
    except (CapabilityError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "status": "BOUNDED_MUTATION_CAPABILITY_REJECTED",
                    "error": str(exc),
                },
                sort_keys=True,
            )
        )
        return 2

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "capability_id": receipt["capability_id"],
                "transformation": receipt["scope_proof"]["transformation"],
                "source_extension": receipt["scope_proof"]["source_extension"],
                "postconditions_validated": receipt["postconditions"]["validated"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
