#!/usr/bin/env python3
"""Issue the exact postcondition receipt produced by the bounded capability chain.

This bridge closes the provenance gap between the READY capability->postcondition
integration and the existing sealed evidence acceptor. It runs the already
qualified integration, materializes the nested lower-level validation receipt,
and immediately seals those exact bytes in the existing postcondition issuance
hash chain.

It does not accept experiment evidence and grants no new mutation/truth
authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Mapping

from validate_js_ts_boolean_guard_bounded_capability_postconditions import (
    validate_bounded_capability_postconditions,
)
from validate_js_ts_boolean_guard_temp_worktree_postconditions import (
    ValidationError,
    _seal_validation_receipt,
)

ISSUANCE_BRIDGE_SCHEMA = (
    "plw-js-ts-v2-bounded-capability-postcondition-issuance-bridge-v1"
)
EXPECTED_INTEGRATION_STATUS = (
    "BOUNDED_MUTATION_CAPABILITY_POSTCONDITIONS_VALIDATED"
)
EXPECTED_VALIDATION_STATUS = "POSTCONDITIONS_VALIDATED"


class IssuanceBridgeError(ValueError):
    pass


def _digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _write_receipt(path: Path, payload: Mapping[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.write_bytes(data)
    return _digest_bytes(data)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _require_outside_target(root: Path, path: Path, label: str) -> None:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return
    raise IssuanceBridgeError(f"{label} must be outside target root")


def _dispose(root: Path) -> bool:
    if root.exists():
        shutil.rmtree(root)
    return not root.exists()


def _rejection(
    *,
    status: str,
    reason: str,
    root: Path,
    integration_status: Any = None,
    validation_receipt_digest: str | None = None,
) -> Dict[str, Any]:
    disposed = _dispose(root)
    result: Dict[str, Any] = {
        "schema_version": ISSUANCE_BRIDGE_SCHEMA,
        "status": status if disposed else "MUTATION_BOUNDARY_CONTAINMENT_FAILED",
        "integration_status": integration_status,
        "reason": reason,
        "postconditions": {
            "validated": False,
            "evidence_acceptance_granted": False,
        },
        "containment": {
            "worktree_disposed": disposed,
            "target_exists_after": root.exists(),
        },
        "authority": {
            "postcondition_receipt_issuance_only": True,
            "evidence_acceptance_authority_granted": False,
            "truth_commit": False,
        },
        "next_gate": None,
    }
    if validation_receipt_digest is not None:
        result["validation_receipt_digest"] = validation_receipt_digest
    return result


def issue_bounded_capability_postconditions(
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
    validation_receipt_path: Path,
    issuance_ledger_path: Path,
    timeout_seconds: int,
) -> Dict[str, Any]:
    root = root.resolve()
    try:
        for path, label in (
            (primitive_materialization_path, "primitive materialization"),
            (validation_receipt_path, "validation receipt"),
            (issuance_ledger_path, "issuance ledger"),
        ):
            _require_outside_target(root, path, label)
    except IssuanceBridgeError as exc:
        return _rejection(
            status="BOUNDED_CAPABILITY_POSTCONDITION_ISSUANCE_REJECTED",
            reason=str(exc),
            root=root,
        )

    integration = validate_bounded_capability_postconditions(
        root=root,
        disposable_parent=disposable_parent,
        capability_contract_path=capability_contract_path,
        capability_receipt_path=capability_receipt_path,
        plan_path=plan_path,
        preflight_path=preflight_path,
        authorization_path=authorization_path,
        validation_spec_path=validation_spec_path,
        primitive_materialization_path=primitive_materialization_path,
        timeout_seconds=timeout_seconds,
    )

    validation = integration.get("postcondition_validation")
    if not isinstance(validation, dict):
        return {
            "schema_version": ISSUANCE_BRIDGE_SCHEMA,
            "status": "BOUNDED_CAPABILITY_POSTCONDITION_NOT_ISSUED",
            "integration_status": integration.get("status"),
            "reason": "NO_VALIDATION_RECEIPT_PRODUCED",
            "postconditions": {
                "validated": False,
                "evidence_acceptance_granted": False,
            },
            "containment": integration.get("containment", {}),
            "authority": {
                "postcondition_receipt_issuance_only": True,
                "evidence_acceptance_authority_granted": False,
                "truth_commit": False,
            },
            "next_gate": None,
        }

    validation_digest = _write_receipt(validation_receipt_path, validation)

    try:
        issuance = _seal_validation_receipt(
            ledger_path=issuance_ledger_path,
            receipt=validation,
            receipt_digest=validation_digest,
        )
    except (ValidationError, json.JSONDecodeError) as exc:
        containment = integration.get("containment", {}) or {}
        if containment.get("worktree_disposed") is not True:
            return _rejection(
                status="BOUNDED_CAPABILITY_POSTCONDITION_ISSUANCE_REJECTED",
                reason=str(exc),
                root=root,
                integration_status=integration.get("status"),
                validation_receipt_digest=validation_digest,
            )
        return {
            "schema_version": ISSUANCE_BRIDGE_SCHEMA,
            "status": "BOUNDED_CAPABILITY_POSTCONDITION_ISSUANCE_REJECTED",
            "integration_status": integration.get("status"),
            "validation_receipt_digest": validation_digest,
            "reason": str(exc),
            "postconditions": {
                "validated": False,
                "evidence_acceptance_granted": False,
            },
            "containment": containment,
            "authority": {
                "postcondition_receipt_issuance_only": True,
                "evidence_acceptance_authority_granted": False,
                "truth_commit": False,
            },
            "next_gate": None,
        }

    issuance_record = issuance.get("record", {}) or {}
    successful = (
        integration.get("status") == EXPECTED_INTEGRATION_STATUS
        and validation.get("status") == EXPECTED_VALIDATION_STATUS
        and (validation.get("postconditions", {}) or {}).get("validated") is True
        and issuance_record.get("validation_receipt_digest") == validation_digest
        and issuance_record.get("validation_status") == EXPECTED_VALIDATION_STATUS
        and issuance_record.get("target") == validation.get("target")
        and issuance_record.get("lineage") == validation.get("bindings")
    )

    return {
        "schema_version": ISSUANCE_BRIDGE_SCHEMA,
        "status": (
            "BOUNDED_CAPABILITY_POSTCONDITION_RECEIPT_ISSUED"
            if successful
            else "BOUNDED_CAPABILITY_POSTCONDITION_FAILURE_RECEIPT_ISSUED"
        ),
        "integration_status": integration.get("status"),
        "validation_status": validation.get("status"),
        "validation_receipt_digest": validation_digest,
        "issuance": {
            "status": issuance.get("status"),
            "record_digest": issuance_record.get("record_digest"),
            "sequence": issuance_record.get("sequence"),
            "appended": issuance.get("appended"),
        },
        "integration_receipt": integration,
        "postconditions": {
            "validated": successful,
            "evidence_acceptance_granted": False,
        },
        "containment": integration.get("containment", {}),
        "authority": {
            "postcondition_receipt_issuance_only": True,
            "public_product_surface_exposed": False,
            "automatic_patch_authority_granted": False,
            "generic_mutation_authority_granted": False,
            "primary_worktree_mutation_authorized": False,
            "commit_creation_authorized": False,
            "push_authorized": False,
            "pull_request_creation_authorized": False,
            "upstream_mutation_authorized": False,
            "evidence_acceptance_authority_granted": False,
            "global_behavioral_equivalence_proven": False,
            "truth_commit": False,
        },
        "next_gate": (
            "TEMP_WORKTREE_EXPERIMENT_EVIDENCE_ACCEPTANCE_REFERENCE"
            if successful
            else None
        ),
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
    parser.add_argument("--validation-receipt", required=True)
    parser.add_argument("--issuance-ledger", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args()

    if args.timeout_seconds < 1 or args.timeout_seconds > 600:
        raise SystemExit("--timeout-seconds must be between 1 and 600")

    root = Path(args.target_root).resolve()
    output = Path(args.output).resolve()
    try:
        _require_outside_target(root, output, "issuance bridge output")
    except IssuanceBridgeError as exc:
        result = _rejection(
            status="BOUNDED_CAPABILITY_POSTCONDITION_ISSUANCE_REJECTED",
            reason=str(exc),
            root=root,
        )
        print(json.dumps(result, sort_keys=True))
        return 2

    result = issue_bounded_capability_postconditions(
        root=root,
        disposable_parent=Path(args.disposable_parent).resolve(),
        capability_contract_path=Path(args.capability_contract).resolve(),
        capability_receipt_path=Path(args.capability_receipt).resolve(),
        plan_path=Path(args.plan).resolve(),
        preflight_path=Path(args.preflight).resolve(),
        authorization_path=Path(args.authorization).resolve(),
        validation_spec_path=Path(args.postcondition_validation_spec).resolve(),
        primitive_materialization_path=Path(args.primitive_materialization).resolve(),
        validation_receipt_path=Path(args.validation_receipt).resolve(),
        issuance_ledger_path=Path(args.issuance_ledger).resolve(),
        timeout_seconds=args.timeout_seconds,
    )
    _write_json(output, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "validation_receipt_digest": result.get(
                    "validation_receipt_digest"
                ),
                "issuance_status": (result.get("issuance", {}) or {}).get(
                    "status"
                ),
                "evidence_acceptance_granted": result["postconditions"][
                    "evidence_acceptance_granted"
                ],
            },
            sort_keys=True,
        )
    )
    return (
        0
        if result["status"]
        == "BOUNDED_CAPABILITY_POSTCONDITION_RECEIPT_ISSUED"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
