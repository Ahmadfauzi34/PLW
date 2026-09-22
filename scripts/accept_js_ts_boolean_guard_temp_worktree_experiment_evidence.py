#!/usr/bin/env python3
"""Accept one sealed JS/TS temp-worktree experiment result as bounded evidence.

This command does not rerun validation and does not inspect a disposed worktree.
It verifies the immutable evidence lineage, requires an issuance seal for the
exact POSTCONDITIONS_VALIDATED receipt, and appends one hash-chained acceptance
record.

Accepted evidence is not truth and grants no mutation authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Mapping

RULE = "js_boolean_guard_return"
PLAN_SCHEMA = "plw-js-ts-v2-boolean-guard-dry-run-plan-v1"
PREFLIGHT_SCHEMA = "plw-js-ts-v2-mutation-preflight-v1"
AUTH_SCHEMA = "plw-js-ts-v2-mutation-authorization-v1"
SPEC_SCHEMA = "plw-js-ts-v2-postcondition-validation-spec-v1"
MUTATION_SCHEMA = "plw-js-ts-v2-temp-worktree-mutation-adapter-receipt-v1"
VALIDATION_SCHEMA = "plw-js-ts-v2-postcondition-validation-receipt-v1"
ISSUANCE_SCHEMA = "plw-js-ts-v2-postcondition-validation-issuance-v1"
ACCEPTANCE_SCHEMA = "plw-js-ts-v2-experiment-evidence-acceptance-v1"

EXPECTED_COMMAND_NAMES = [
    "parse_after_rewrite",
    "focused_target_native_after",
    "target_typecheck_or_type_tests_after",
]

FALSE_AUTHORITY_FIELDS = (
    "product_mutation_surface_exposed",
    "automatic_patch_authority_granted",
    "generic_mutation_authority_granted",
    "upstream_mutation_authorized",
    "global_behavioral_equivalence_proven",
    "truth_commit",
)


class AcceptanceError(ValueError):
    pass


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _digest_file(path: Path) -> str:
    return _digest_bytes(path.read_bytes())


def _canonical_record_digest(record: Mapping[str, Any]) -> str:
    payload = dict(record)
    payload.pop("record_digest", None)
    data = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return _digest_bytes(data)


def _read_hash_chain(
    path: Path,
    *,
    schema: str,
    label: str,
) -> list[Dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    previous = None
    for expected_sequence, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        1,
    ):
        if not raw.strip():
            continue
        record = json.loads(raw)
        if record.get("schema_version") != schema:
            raise AcceptanceError(f"{label} schema mismatch")
        if record.get("sequence") != expected_sequence:
            raise AcceptanceError(f"{label} sequence mismatch")
        if record.get("previous_record_digest") != previous:
            raise AcceptanceError(f"{label} previous digest mismatch")
        if record.get("record_digest") != _canonical_record_digest(record):
            raise AcceptanceError(f"{label} record digest mismatch")
        previous = record["record_digest"]
        records.append(record)
    return records


def _assert_false_authority(
    authority: Mapping[str, Any],
    *,
    label: str,
    include_acceptance: bool = False,
) -> None:
    for key in FALSE_AUTHORITY_FIELDS:
        if authority.get(key) is not False:
            raise AcceptanceError(f"{label} unexpectedly grants {key}")
    if include_acceptance and (
        authority.get("experiment_evidence_acceptance_authority_granted")
        is not False
    ):
        raise AcceptanceError(
            f"{label} unexpectedly grants experiment evidence acceptance authority"
        )


def _assert_sha(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise AcceptanceError(f"{label} must be a sha256 digest")


def _verify_validation_receipt(validation: Mapping[str, Any]) -> None:
    if validation.get("schema_version") != VALIDATION_SCHEMA:
        raise AcceptanceError("unexpected validation receipt schema")
    if validation.get("status") != "POSTCONDITIONS_VALIDATED":
        raise AcceptanceError("validation receipt is not POSTCONDITIONS_VALIDATED")
    if validation.get("rule") != RULE:
        raise AcceptanceError("validation receipt rule mismatch")
    if validation.get("next_gate") != (
        "TEMP_WORKTREE_EXPERIMENT_EVIDENCE_ACCEPTANCE_REFERENCE"
    ):
        raise AcceptanceError("validation receipt next gate mismatch")

    postconditions = validation.get("postconditions", {}) or {}
    if postconditions.get("validated") is not True:
        raise AcceptanceError("validation receipt does not prove validated postconditions")
    if postconditions.get("evidence_acceptance_granted") is not False:
        raise AcceptanceError("validation receipt already claims evidence acceptance")

    result = validation.get("validation", {}) or {}
    if result.get("all_required_postconditions_passed") is not True:
        raise AcceptanceError("not all required postconditions passed")
    if result.get("failure") is not None:
        raise AcceptanceError("validation receipt contains a failure")
    if result.get("same_focused_command_as_baseline") is not True:
        raise AcceptanceError("focused postcondition command was not baseline-identical")

    commands = result.get("commands", []) or []
    if [item.get("name") for item in commands] != EXPECTED_COMMAND_NAMES:
        raise AcceptanceError("validation command sequence mismatch")
    for item in commands:
        if item.get("exit_code") != 0:
            raise AcceptanceError(
                f"validation command failed: {item.get('name')}"
            )
        if item.get("timed_out") is not False:
            raise AcceptanceError(
                f"validation command timed out: {item.get('name')}"
            )
        _assert_sha(item.get("stdout_sha256"), "validation stdout digest")
        _assert_sha(item.get("stderr_sha256"), "validation stderr digest")

    _assert_sha(
        result.get("source_sha256_before_disposal"),
        "validated source digest",
    )
    _assert_sha(
        result.get("diff_digest_before_disposal"),
        "validated diff digest",
    )

    containment = validation.get("containment", {}) or {}
    if containment.get("authorization_consumed") is not True:
        raise AcceptanceError("authorization was not consumed")
    if containment.get("worktree_disposition") != "DISPOSED_AFTER_VALIDATION":
        raise AcceptanceError("unexpected successful worktree disposition")
    if containment.get("worktree_disposed") is not True:
        raise AcceptanceError("validated worktree was not disposed")
    if containment.get("target_exists_after") is not False:
        raise AcceptanceError("disposed target still exists")

    authority = validation.get("authority", {}) or {}
    _assert_false_authority(
        authority,
        label="validation receipt",
        include_acceptance=True,
    )


def _verify_lineage(
    *,
    plan: Mapping[str, Any],
    preflight: Mapping[str, Any],
    authorization: Mapping[str, Any],
    spec: Mapping[str, Any],
    mutation: Mapping[str, Any],
    validation: Mapping[str, Any],
    digests: Mapping[str, str],
) -> None:
    if plan.get("schema_version") != PLAN_SCHEMA:
        raise AcceptanceError("unexpected plan schema")
    if plan.get("status") != "DRY_RUN_REWRITE_PLAN_READY":
        raise AcceptanceError("plan is not ready")

    plan_candidate = plan.get("candidate", {}) or {}
    if plan_candidate.get("kind") != RULE:
        raise AcceptanceError("plan candidate kind mismatch")

    if preflight.get("schema_version") != PREFLIGHT_SCHEMA:
        raise AcceptanceError("unexpected preflight schema")
    if preflight.get("status") != "PREFLIGHT_VALIDATED":
        raise AcceptanceError("preflight is not validated")

    if authorization.get("schema_version") != AUTH_SCHEMA:
        raise AcceptanceError("unexpected authorization schema")
    if authorization.get("status") != "MUTATION_AUTHORIZED":
        raise AcceptanceError("authorization receipt is not authorized")

    if spec.get("schema_version") != SPEC_SCHEMA:
        raise AcceptanceError("unexpected validation spec schema")
    if spec.get("status") != "POSTCONDITION_VALIDATION_SPEC_READY":
        raise AcceptanceError("validation spec is not ready")

    if mutation.get("schema_version") != MUTATION_SCHEMA:
        raise AcceptanceError("unexpected mutation receipt schema")
    if mutation.get("status") != "TEMP_WORKTREE_APPLIED":
        raise AcceptanceError("mutation receipt is not TEMP_WORKTREE_APPLIED")
    if mutation.get("rule") != RULE:
        raise AcceptanceError("mutation receipt rule mismatch")

    mutation_post = mutation.get("postconditions", {}) or {}
    if mutation_post.get("validated") is not False:
        raise AcceptanceError("mutation receipt already claims validation")
    if mutation_post.get("acceptance_granted") is not False:
        raise AcceptanceError("mutation receipt already claims acceptance")

    mutation_authority = mutation.get("authority", {}) or {}
    _assert_false_authority(
        mutation_authority,
        label="mutation receipt",
        include_acceptance=False,
    )
    if (
        mutation_authority.get("postcondition_acceptance_authority_granted")
        is not False
    ):
        raise AcceptanceError(
            "mutation receipt unexpectedly grants postcondition acceptance authority"
        )

    validation_bindings = validation.get("bindings", {}) or {}
    for key, value in digests.items():
        if validation_bindings.get(key) != value:
            raise AcceptanceError(f"validation lineage digest mismatch: {key}")

    target = validation.get("target", {}) or {}
    candidate = validation.get("candidate", {}) or {}
    candidate_id = candidate.get("candidate_id")
    source_path = target.get("source_path")
    repository = target.get("repository")
    revision = target.get("revision")

    if plan_candidate.get("candidate_id") != candidate_id:
        raise AcceptanceError("plan candidate id mismatch")
    if plan_candidate.get("source_path") != source_path:
        raise AcceptanceError("plan source path mismatch")

    preflight_target = preflight.get("target", {}) or {}
    expected_target = {
        "repository": repository,
        "revision": revision,
        "source_path": source_path,
        "candidate_id": candidate_id,
    }
    for key, value in expected_target.items():
        if preflight_target.get(key) != value:
            raise AcceptanceError(f"preflight target mismatch: {key}")

    if (
        preflight.get("postcondition_validation_spec_digest")
        != digests["postcondition_validation_spec_digest"]
    ):
        raise AcceptanceError("preflight validation-spec digest mismatch")

    auth_binding = authorization.get("binding", {}) or {}
    expected_auth = {
        "candidate_id": candidate_id,
        "target_repository": repository,
        "target_revision": revision,
        "source_path": source_path,
        "plan_digest": digests["plan_digest"],
        "preflight_evidence_digest": digests["preflight_evidence_digest"],
        "postcondition_validation_spec_digest": digests[
            "postcondition_validation_spec_digest"
        ],
    }
    for key, value in expected_auth.items():
        if auth_binding.get(key) != value:
            raise AcceptanceError(f"authorization binding mismatch: {key}")

    spec_target = spec.get("target", {}) or {}
    for key, value in expected_target.items():
        if spec_target.get(key) != value:
            raise AcceptanceError(f"validation spec target mismatch: {key}")

    mutation_target = mutation.get("target", {}) or {}
    for key in ("repository", "revision", "source_path"):
        if mutation_target.get(key) != expected_target[key]:
            raise AcceptanceError(f"mutation target mismatch: {key}")
    if (mutation.get("candidate", {}) or {}).get("candidate_id") != candidate_id:
        raise AcceptanceError("mutation candidate mismatch")

    mutation_bindings = mutation.get("bindings", {}) or {}
    for key in (
        "plan_digest",
        "preflight_evidence_digest",
        "authorization_receipt_digest",
        "postcondition_validation_spec_digest",
    ):
        if mutation_bindings.get(key) != digests[key]:
            raise AcceptanceError(f"mutation lineage digest mismatch: {key}")

    mutation_state = mutation.get("mutation", {}) or {}
    if mutation_state.get("authorization_consumed") is not True:
        raise AcceptanceError("mutation receipt does not show consumed authorization")
    if (
        mutation_state.get("actual_after_source_sha256")
        != (validation.get("validation", {}) or {}).get(
            "source_sha256_before_disposal"
        )
    ):
        raise AcceptanceError("validated source digest does not match mutation receipt")
    if (
        mutation_state.get("actual_diff_digest")
        != (validation.get("validation", {}) or {}).get(
            "diff_digest_before_disposal"
        )
    ):
        raise AcceptanceError("validated diff digest does not match mutation receipt")


def _find_issuance(
    *,
    ledger: list[Dict[str, Any]],
    validation_receipt_digest: str,
    validation: Mapping[str, Any],
) -> Dict[str, Any]:
    matches = [
        record
        for record in ledger
        if record.get("validation_receipt_digest") == validation_receipt_digest
    ]
    if len(matches) != 1:
        raise AcceptanceError(
            "exact validation receipt is not uniquely sealed in issuance ledger"
        )
    record = matches[0]
    if record.get("status") != "POSTCONDITION_VALIDATION_RECEIPT_ISSUED":
        raise AcceptanceError("issuance record is not an issued receipt")
    if record.get("validation_status") != "POSTCONDITIONS_VALIDATED":
        raise AcceptanceError("issued receipt is not POSTCONDITIONS_VALIDATED")
    if record.get("rule") != RULE:
        raise AcceptanceError("issuance rule mismatch")
    if record.get("candidate_id") != (
        validation.get("candidate", {}) or {}
    ).get("candidate_id"):
        raise AcceptanceError("issuance candidate mismatch")
    if record.get("target") != validation.get("target"):
        raise AcceptanceError("issuance target mismatch")
    if record.get("lineage") != validation.get("bindings"):
        raise AcceptanceError("issuance lineage does not match validation receipt")
    return record


def _append_or_recover_acceptance(
    *,
    ledger_path: Path,
    existing: list[Dict[str, Any]],
    validation: Mapping[str, Any],
    validation_receipt_digest: str,
    issuance_record: Mapping[str, Any],
) -> Dict[str, Any]:
    matches = [
        record
        for record in existing
        if record.get("validation_receipt_digest") == validation_receipt_digest
    ]
    if len(matches) > 1:
        raise AcceptanceError("duplicate acceptance records detected")
    if matches:
        return {
            "status": "EXPERIMENT_EVIDENCE_ACCEPTANCE_RECOVERED",
            "acceptance_record": matches[0],
            "appended": False,
        }

    record = {
        "schema_version": ACCEPTANCE_SCHEMA,
        "status": "EXPERIMENT_EVIDENCE_ACCEPTED",
        "evidence_class": "BOUNDED_POSTCONDITION_VALIDATION_EVIDENCE",
        "validation_receipt_digest": validation_receipt_digest,
        "issuance_record_digest": issuance_record.get("record_digest"),
        "rule": RULE,
        "candidate_id": (validation.get("candidate", {}) or {}).get(
            "candidate_id"
        ),
        "target": validation.get("target"),
        "lineage": validation.get("bindings"),
        "validation_summary": {
            "all_required_postconditions_passed": True,
            "worktree_disposed": True,
            "authorization_consumed": True,
        },
        "authority": {
            "evidence_acceptance_only": True,
            "source_mutation_allowed": False,
            "automatic_patch_authority_granted": False,
            "generic_mutation_authority_granted": False,
            "upstream_mutation_authorized": False,
            "global_behavioral_equivalence_proven": False,
            "truth_commit": False,
        },
        "sequence": len(existing) + 1,
        "previous_record_digest": (
            existing[-1]["record_digest"] if existing else None
        ),
    }
    record["record_digest"] = _canonical_record_digest(record)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return {
        "status": "EXPERIMENT_EVIDENCE_ACCEPTED",
        "acceptance_record": record,
        "appended": True,
    }


def accept_evidence(
    *,
    plan_path: Path,
    preflight_path: Path,
    authorization_path: Path,
    spec_path: Path,
    mutation_path: Path,
    validation_path: Path,
    issuance_ledger_path: Path,
    acceptance_ledger_path: Path,
) -> Dict[str, Any]:
    plan = _load(plan_path)
    preflight = _load(preflight_path)
    authorization = _load(authorization_path)
    spec = _load(spec_path)
    mutation = _load(mutation_path)
    validation = _load(validation_path)

    _verify_validation_receipt(validation)

    digests = {
        "plan_digest": _digest_file(plan_path),
        "preflight_evidence_digest": _digest_file(preflight_path),
        "authorization_receipt_digest": _digest_file(authorization_path),
        "postcondition_validation_spec_digest": _digest_file(spec_path),
        "mutation_receipt_digest": _digest_file(mutation_path),
    }
    _verify_lineage(
        plan=plan,
        preflight=preflight,
        authorization=authorization,
        spec=spec,
        mutation=mutation,
        validation=validation,
        digests=digests,
    )

    validation_receipt_digest = _digest_file(validation_path)
    issuance = _read_hash_chain(
        issuance_ledger_path,
        schema=ISSUANCE_SCHEMA,
        label="issuance ledger",
    )
    issuance_record = _find_issuance(
        ledger=issuance,
        validation_receipt_digest=validation_receipt_digest,
        validation=validation,
    )

    acceptance = _read_hash_chain(
        acceptance_ledger_path,
        schema=ACCEPTANCE_SCHEMA,
        label="acceptance ledger",
    )
    result = _append_or_recover_acceptance(
        ledger_path=acceptance_ledger_path,
        existing=acceptance,
        validation=validation,
        validation_receipt_digest=validation_receipt_digest,
        issuance_record=issuance_record,
    )

    return {
        "schema_version": "plw-js-ts-v2-experiment-evidence-acceptance-result-v1",
        "status": result["status"],
        "rule": RULE,
        "evidence_class": "BOUNDED_POSTCONDITION_VALIDATION_EVIDENCE",
        "validation_receipt_digest": validation_receipt_digest,
        "issuance_record_digest": issuance_record["record_digest"],
        "acceptance_record": result["acceptance_record"],
        "acceptance_ledger_appended": result["appended"],
        "reran_validation": False,
        "inspected_disposed_worktree": False,
        "authority": {
            "evidence_acceptance_only": True,
            "source_mutation_allowed": False,
            "automatic_patch_authority_granted": False,
            "generic_mutation_authority_granted": False,
            "upstream_mutation_authorized": False,
            "global_behavioral_equivalence_proven": False,
            "truth_commit": False,
        },
        "next_gate": "BOUNDED_MUTATION_EVIDENCE_SYNTHESIS_REVIEW",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--preflight", required=True)
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--postcondition-validation-spec", required=True)
    parser.add_argument("--mutation-receipt", required=True)
    parser.add_argument("--validation-receipt", required=True)
    parser.add_argument("--issuance-ledger", required=True)
    parser.add_argument("--acceptance-ledger", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    try:
        result = accept_evidence(
            plan_path=Path(args.plan).resolve(),
            preflight_path=Path(args.preflight).resolve(),
            authorization_path=Path(args.authorization).resolve(),
            spec_path=Path(args.postcondition_validation_spec).resolve(),
            mutation_path=Path(args.mutation_receipt).resolve(),
            validation_path=Path(args.validation_receipt).resolve(),
            issuance_ledger_path=Path(args.issuance_ledger).resolve(),
            acceptance_ledger_path=Path(args.acceptance_ledger).resolve(),
        )
    except (AcceptanceError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "status": "EXPERIMENT_EVIDENCE_ACCEPTANCE_REJECTED",
                    "error": str(exc),
                },
                sort_keys=True,
            )
        )
        return 2

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "acceptance_ledger_appended": result[
                    "acceptance_ledger_appended"
                ],
                "reran_validation": result["reran_validation"],
                "truth_commit": result["authority"]["truth_commit"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
