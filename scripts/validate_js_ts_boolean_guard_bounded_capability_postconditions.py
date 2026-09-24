#!/usr/bin/env python3
"""Bind the READY bounded boolean-guard capability to postcondition validation.

This is an internal handoff reference. It consumes a
BOUNDED_MUTATION_CAPABILITY_APPLIED receipt, proves that its embedded
TEMP_WORKTREE_APPLIED primitive is exactly the primitive authorized by the
capability contract, and delegates postcondition execution to the already
qualified reference validator.

Success stops at BOUNDED_MUTATION_CAPABILITY_POSTCONDITIONS_VALIDATED.
Evidence acceptance and truth remain separate authorities.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Mapping

from apply_js_ts_boolean_guard_bounded_capability import CAPABILITY_ID
from validate_js_ts_boolean_guard_temp_worktree_postconditions import (
    validate_postconditions,
)

CAPABILITY_RECEIPT_SCHEMA = "plw-js-ts-v2-bounded-mutation-capability-receipt-v1"
PRIMITIVE_RECEIPT_SCHEMA = "plw-js-ts-v2-temp-worktree-mutation-adapter-receipt-v1"
AUTH_SCHEMA = "plw-js-ts-v2-mutation-authorization-v1"
INTEGRATION_SCHEMA = (
    "plw-js-ts-v2-bounded-capability-postcondition-integration-receipt-v1"
)


class IntegrationError(ValueError):
    pass


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _digest_file(path: Path) -> str:
    return _digest_bytes(path.read_bytes())


def _canonical_digest(payload: Mapping[str, Any]) -> str:
    return _digest_bytes(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    )


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _require_outside_target(root: Path, path: Path, label: str) -> None:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return
    raise IntegrationError(f"{label} must be outside target root")


def _dispose(root: Path) -> bool:
    if root.exists():
        shutil.rmtree(root)
    return not root.exists()


def _assert_false(mapping: Mapping[str, Any], key: str, label: str) -> None:
    if mapping.get(key) is not False:
        raise IntegrationError(f"{label} unexpectedly grants {key}")


def _bind_capability_receipt(
    *,
    capability_contract_path: Path,
    capability_receipt_path: Path,
    plan_path: Path,
    preflight_path: Path,
    authorization_path: Path,
    validation_spec_path: Path,
) -> Dict[str, Any]:
    capability = _load(capability_receipt_path)
    authorization = _load(authorization_path)

    if capability.get("schema_version") != CAPABILITY_RECEIPT_SCHEMA:
        raise IntegrationError("unexpected bounded capability receipt schema")
    if capability.get("status") != "BOUNDED_MUTATION_CAPABILITY_APPLIED":
        raise IntegrationError("capability receipt is not applied")
    if capability.get("capability_id") != CAPABILITY_ID:
        raise IntegrationError("capability receipt id mismatch")

    contract_digest = _digest_file(capability_contract_path)
    if capability.get("capability_contract_digest") != contract_digest:
        raise IntegrationError("capability contract digest mismatch")

    cap_post = capability.get("postconditions", {}) or {}
    if cap_post.get("validated") is not False:
        raise IntegrationError("input capability receipt already claims postconditions")
    if cap_post.get("evidence_acceptance_granted") is not False:
        raise IntegrationError("input capability receipt already claims evidence acceptance")

    cap_authority = capability.get("authority", {}) or {}
    if cap_authority.get("bounded_internal_capability_applied") is not True:
        raise IntegrationError("bounded capability application marker missing")
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
        _assert_false(cap_authority, key, "capability receipt")

    if authorization.get("schema_version") != AUTH_SCHEMA:
        raise IntegrationError("unexpected authorization schema")
    if authorization.get("status") != "MUTATION_AUTHORIZED":
        raise IntegrationError("authorization receipt is not authorized")
    auth_binding = authorization.get("binding", {}) or {}
    if auth_binding.get("capability_id") != CAPABILITY_ID:
        raise IntegrationError("authorization capability id mismatch")
    if auth_binding.get("capability_contract_digest") != contract_digest:
        raise IntegrationError("authorization capability contract digest mismatch")

    candidate_provenance = capability.get("candidate_provenance")
    provenance_auth_keys = (
        "candidate_provenance_digest",
        "candidate_selection_digest",
        "discovery_snapshot_digest",
    )
    if candidate_provenance is None and any(
        key in auth_binding for key in provenance_auth_keys
    ):
        raise IntegrationError(
            "authorization binds candidate provenance but capability receipt omitted it"
        )
    if candidate_provenance is not None:
        if not isinstance(candidate_provenance, dict):
            raise IntegrationError("candidate provenance receipt must be an object")
        if candidate_provenance.get("resolution") != "RESOLVED":
            raise IntegrationError("candidate provenance is not resolved")
        if candidate_provenance.get("matched_capability_id") != CAPABILITY_ID:
            raise IntegrationError("candidate provenance capability id mismatch")
        expected_candidate_auth = {
            "candidate_provenance_digest": candidate_provenance.get(
                "candidate_provenance_digest"
            ),
            "candidate_task_digest": candidate_provenance.get(
                "candidate_task_digest"
            ),
            "target_revision": candidate_provenance.get("target_revision"),
            "target_tree": candidate_provenance.get("target_tree"),
            "target_revision_digest": candidate_provenance.get(
                "target_revision_digest"
            ),
            "working_tree_status_digest": candidate_provenance.get(
                "working_tree_status_digest"
            ),
            "shared_graph_content_signature": candidate_provenance.get(
                "shared_graph_content_signature"
            ),
            "discovery_snapshot_digest": candidate_provenance.get(
                "discovery_snapshot_digest"
            ),
            "candidate_set_digest": candidate_provenance.get(
                "candidate_set_digest"
            ),
            "candidate_selection_digest": candidate_provenance.get(
                "candidate_selection_digest"
            ),
            "selected_candidate_id": candidate_provenance.get(
                "selected_candidate_id"
            ),
            "selected_candidate_instance_id": candidate_provenance.get(
                "selected_candidate_instance_id"
            ),
            "selected_source_path": candidate_provenance.get(
                "selected_source_path"
            ),
            "selected_symbol": candidate_provenance.get("selected_symbol"),
            "candidate_kind": candidate_provenance.get("candidate_kind"),
            "selection_basis_digest": candidate_provenance.get(
                "selection_basis_digest"
            ),
            "selection_confidence_boundary": candidate_provenance.get(
                "selection_confidence_boundary"
            ),
            "rejected_alternative_count": candidate_provenance.get(
                "rejected_alternative_count"
            ),
            "rejected_alternatives_digest": candidate_provenance.get(
                "rejected_alternatives_digest"
            ),
            "source_site_sha256": candidate_provenance.get("source_site_sha256"),
            "source_char_start": candidate_provenance.get("source_char_start"),
            "source_char_end": candidate_provenance.get("source_char_end"),
            "matched_capability_id": candidate_provenance.get(
                "matched_capability_id"
            ),
            "candidate_capability_contract_digest": candidate_provenance.get(
                "capability_contract_digest"
            ),
        }
        for key, expected in expected_candidate_auth.items():
            if expected is None or auth_binding.get(key) != expected:
                raise IntegrationError(
                    f"authorization candidate-provenance binding mismatch: {key}"
                )

    primitive_wrapper = capability.get("primitive", {}) or {}
    if primitive_wrapper.get("status") != "TEMP_WORKTREE_APPLIED":
        raise IntegrationError("capability did not retain an applied primitive")
    primitive = primitive_wrapper.get("receipt")
    if not isinstance(primitive, dict):
        raise IntegrationError("embedded primitive receipt missing")
    if primitive.get("schema_version") != PRIMITIVE_RECEIPT_SCHEMA:
        raise IntegrationError("unexpected embedded primitive receipt schema")
    if primitive.get("status") != "TEMP_WORKTREE_APPLIED":
        raise IntegrationError("embedded primitive is not TEMP_WORKTREE_APPLIED")
    if candidate_provenance is not None:
        plan_candidate = (_load(plan_path).get("candidate", {}) or {})
        primitive_candidate = primitive.get("candidate", {}) or {}
        primitive_target = primitive.get("target", {}) or {}
        if primitive_candidate.get("candidate_id") != candidate_provenance.get(
            "selected_candidate_id"
        ):
            raise IntegrationError("primitive candidate id does not match provenance")
        if primitive_target.get("source_path") != candidate_provenance.get(
            "selected_source_path"
        ):
            raise IntegrationError("primitive source path does not match provenance")
        if primitive_target.get("revision") != candidate_provenance.get(
            "target_revision"
        ):
            raise IntegrationError("primitive revision does not match provenance")
        for key, expected in {
            "candidate_id": candidate_provenance.get("selected_candidate_id"),
            "candidate_instance_id": candidate_provenance.get(
                "selected_candidate_instance_id"
            ),
            "kind": candidate_provenance.get("candidate_kind"),
            "source_path": candidate_provenance.get("selected_source_path"),
            "source_site_sha256": candidate_provenance.get("source_site_sha256"),
            "source_char_start": candidate_provenance.get("source_char_start"),
            "source_char_end": candidate_provenance.get("source_char_end"),
        }.items():
            if plan_candidate.get(key) != expected:
                raise IntegrationError(
                    f"plan candidate does not match provenance: {key}"
                )
    expected_canonical = primitive_wrapper.get("canonical_receipt_digest")
    actual_canonical = _canonical_digest(primitive)
    if expected_canonical != actual_canonical:
        raise IntegrationError("embedded primitive canonical digest mismatch")

    primitive_post = primitive.get("postconditions", {}) or {}
    if primitive_post.get("validated") is not False:
        raise IntegrationError("primitive already claims postcondition validation")
    if primitive_post.get("acceptance_granted") is not False:
        raise IntegrationError("primitive already claims evidence acceptance")

    bindings = primitive.get("bindings", {}) or {}
    expected_bindings = {
        "plan_digest": _digest_file(plan_path),
        "preflight_evidence_digest": _digest_file(preflight_path),
        "authorization_receipt_digest": _digest_file(authorization_path),
        "postcondition_validation_spec_digest": _digest_file(validation_spec_path),
    }
    for key, value in expected_bindings.items():
        if bindings.get(key) != value:
            raise IntegrationError(f"embedded primitive binding mismatch: {key}")

    return {
        "capability": capability,
        "primitive": primitive,
        "contract_digest": contract_digest,
        "capability_receipt_digest": _digest_file(capability_receipt_path),
        "primitive_canonical_digest": actual_canonical,
        "candidate_provenance": candidate_provenance,
    }


def validate_bounded_capability_postconditions(
    *,
    root: Path,
    disposable_parent: Path,
    capability_contract_path: Path,
    capability_receipt_path: Path,
    plan_path: Path,
    preflight_path: Path,
    authorization_path: Path,
    validation_spec_path: Path,
    primitive_materialization_path: Path,
    timeout_seconds: int,
) -> Dict[str, Any]:
    root = root.resolve()
    paths = (
        (capability_contract_path, "capability contract"),
        (capability_receipt_path, "capability receipt"),
        (plan_path, "dry-run plan"),
        (preflight_path, "preflight evidence"),
        (authorization_path, "authorization receipt"),
        (validation_spec_path, "postcondition validation spec"),
        (primitive_materialization_path, "primitive materialization"),
    )
    for path, label in paths:
        _require_outside_target(root, path, label)

    try:
        bound = _bind_capability_receipt(
            capability_contract_path=capability_contract_path,
            capability_receipt_path=capability_receipt_path,
            plan_path=plan_path,
            preflight_path=preflight_path,
            authorization_path=authorization_path,
            validation_spec_path=validation_spec_path,
        )
        _write_json(primitive_materialization_path, bound["primitive"])

        validation = validate_postconditions(
            root=root,
            disposable_parent=disposable_parent,
            plan_path=plan_path,
            preflight_path=preflight_path,
            authorization_path=authorization_path,
            mutation_receipt_path=primitive_materialization_path,
            validation_spec_path=validation_spec_path,
            timeout_seconds=timeout_seconds,
        )
        candidate_provenance = bound.get("candidate_provenance")
        if isinstance(candidate_provenance, dict):
            validation_bindings = validation.setdefault("bindings", {})
            validation_bindings.update(
                {
                    "candidate_provenance_digest": candidate_provenance[
                        "candidate_provenance_digest"
                    ],
                    "candidate_task_digest": candidate_provenance[
                        "candidate_task_digest"
                    ],
                    "candidate_target_revision": candidate_provenance[
                        "target_revision"
                    ],
                    "candidate_target_tree": candidate_provenance[
                        "target_tree"
                    ],
                    "candidate_target_revision_digest": candidate_provenance[
                        "target_revision_digest"
                    ],
                    "candidate_working_tree_status_digest": candidate_provenance[
                        "working_tree_status_digest"
                    ],
                    "candidate_shared_graph_content_signature": candidate_provenance[
                        "shared_graph_content_signature"
                    ],
                    "discovery_snapshot_digest": candidate_provenance[
                        "discovery_snapshot_digest"
                    ],
                    "candidate_set_digest": candidate_provenance[
                        "candidate_set_digest"
                    ],
                    "candidate_selection_digest": candidate_provenance[
                        "candidate_selection_digest"
                    ],
                    "selected_candidate_id": candidate_provenance[
                        "selected_candidate_id"
                    ],
                    "selected_candidate_instance_id": candidate_provenance[
                        "selected_candidate_instance_id"
                    ],
                    "selected_source_path": candidate_provenance[
                        "selected_source_path"
                    ],
                    "selected_symbol": candidate_provenance["selected_symbol"],
                    "candidate_kind": candidate_provenance["candidate_kind"],
                    "selection_basis_digest": candidate_provenance[
                        "selection_basis_digest"
                    ],
                    "selection_confidence_boundary": candidate_provenance[
                        "selection_confidence_boundary"
                    ],
                    "rejected_alternative_count": candidate_provenance[
                        "rejected_alternative_count"
                    ],
                    "rejected_alternatives_digest": candidate_provenance[
                        "rejected_alternatives_digest"
                    ],
                    "source_site_sha256": candidate_provenance[
                        "source_site_sha256"
                    ],
                    "source_char_start": candidate_provenance[
                        "source_char_start"
                    ],
                    "source_char_end": candidate_provenance[
                        "source_char_end"
                    ],
                    "matched_capability_id": candidate_provenance[
                        "matched_capability_id"
                    ],
                    "candidate_capability_contract_digest": candidate_provenance[
                        "capability_contract_digest"
                    ],
                }
            )
        status = (
            "BOUNDED_MUTATION_CAPABILITY_POSTCONDITIONS_VALIDATED"
            if validation.get("status") == "POSTCONDITIONS_VALIDATED"
            else "BOUNDED_MUTATION_CAPABILITY_POSTCONDITION_FAILED"
        )
        return {
            "schema_version": INTEGRATION_SCHEMA,
            "status": status,
            "capability_id": CAPABILITY_ID,
            "bindings": {
                "capability_contract_digest": bound["contract_digest"],
                "capability_receipt_digest": bound["capability_receipt_digest"],
                "primitive_canonical_receipt_digest": bound[
                    "primitive_canonical_digest"
                ],
                "materialized_primitive_receipt_digest": _digest_file(
                    primitive_materialization_path
                ),
                "postcondition_validation_receipt_digest": _canonical_digest(
                    validation
                ),
            },
            "candidate_provenance": candidate_provenance,
            "postcondition_validation": validation,
            "postconditions": {
                "validated": status
                == "BOUNDED_MUTATION_CAPABILITY_POSTCONDITIONS_VALIDATED",
                "evidence_acceptance_granted": False,
            },
            "containment": validation.get("containment", {}),
            "authority": {
                "internal_handoff_reference_only": True,
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
            "next_gate": (
                "TEMP_WORKTREE_EXPERIMENT_EVIDENCE_ACCEPTANCE_REFERENCE"
                if status
                == "BOUNDED_MUTATION_CAPABILITY_POSTCONDITIONS_VALIDATED"
                else None
            ),
        }
    except (IntegrationError, json.JSONDecodeError) as exc:
        disposed = _dispose(root)
        return {
            "schema_version": INTEGRATION_SCHEMA,
            "status": (
                "BOUNDED_MUTATION_CAPABILITY_POSTCONDITION_REJECTED"
                if disposed
                else "MUTATION_BOUNDARY_CONTAINMENT_FAILED"
            ),
            "capability_id": CAPABILITY_ID,
            "error": str(exc),
            "postconditions": {
                "validated": False,
                "evidence_acceptance_granted": False,
            },
            "containment": {
                "worktree_disposed": disposed,
                "target_exists_after": root.exists(),
            },
            "authority": {
                "internal_handoff_reference_only": True,
                "evidence_acceptance_authority_granted": False,
                "truth_commit": False,
            },
            "next_gate": None,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--disposable-parent", required=True)
    parser.add_argument("--capability-contract", required=True)
    parser.add_argument("--capability-receipt", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--preflight", required=True)
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--postcondition-validation-spec", required=True)
    parser.add_argument("--primitive-materialization", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args()

    if args.timeout_seconds < 1 or args.timeout_seconds > 600:
        raise SystemExit("--timeout-seconds must be between 1 and 600")

    root = Path(args.target_root).resolve()
    output = Path(args.output).resolve()
    _require_outside_target(root, output, "integration output receipt")

    receipt = validate_bounded_capability_postconditions(
        root=root,
        disposable_parent=Path(args.disposable_parent).resolve(),
        capability_contract_path=Path(args.capability_contract).resolve(),
        capability_receipt_path=Path(args.capability_receipt).resolve(),
        plan_path=Path(args.plan).resolve(),
        preflight_path=Path(args.preflight).resolve(),
        authorization_path=Path(args.authorization).resolve(),
        validation_spec_path=Path(args.postcondition_validation_spec).resolve(),
        primitive_materialization_path=Path(args.primitive_materialization).resolve(),
        timeout_seconds=args.timeout_seconds,
    )
    _write_json(output, receipt)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "postconditions_validated": receipt["postconditions"]["validated"],
                "worktree_disposed": receipt["containment"].get(
                    "worktree_disposed"
                ),
                "evidence_acceptance_granted": receipt["postconditions"][
                    "evidence_acceptance_granted"
                ],
            },
            sort_keys=True,
        )
    )
    return (
        0
        if receipt["status"]
        == "BOUNDED_MUTATION_CAPABILITY_POSTCONDITIONS_VALIDATED"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
