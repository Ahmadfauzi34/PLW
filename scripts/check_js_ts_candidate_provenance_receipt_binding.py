#!/usr/bin/env python3
"""Check fail-closed candidate provenance binding through postcondition issuance."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apply_js_ts_boolean_guard_bounded_capability import (
    CapabilityError,
    _canonical_digest,
    _digest_text,
    apply_bounded_capability,
)
from check_js_ts_boolean_guard_bounded_capability import (
    build_fixture,
    digest_file,
    rebind_preflight_and_authorization,
    write_json,
)
from core.candidate_provenance import (
    build_discovery_binding,
    run_candidate_provenance,
)
from core.simplification_analyzer import analyze_simplification
from issue_js_ts_boolean_guard_bounded_capability_postconditions import (
    issue_bounded_capability_postconditions,
)
from plan_js_ts_boolean_guard_rewrite import build_plan
from validate_js_ts_boolean_guard_temp_worktree_postconditions import (
    _read_issuance_ledger,
)

TASK = (
    "Select the boolean guard using strict equality, a string literal, "
    "and positive form."
)


def _prepare_fixture(base: Path) -> Dict[str, Any]:
    fixture = build_fixture(
        base,
        extension=".js",
        condition='value.kind === "ok"',
        inverse=False,
        semicolon=True,
    )
    target = fixture["target"]
    provenance = run_candidate_provenance(
        str(target), TASK, include_capability_match=True
    )
    selection = provenance["candidate_selection"]
    route = provenance["candidate_capability_match"]
    discovery = analyze_simplification(str(target))
    binding, candidates = build_discovery_binding(str(target), discovery)
    rows = [
        row
        for row in candidates
        if row.get("candidate_id") == selection.get("selected_candidate_id")
        and row.get("candidate_instance_id")
        == selection.get("selected_candidate_instance_id")
    ]
    if len(rows) != 1:
        raise AssertionError("selection did not identify one planner candidate")
    plan = build_plan(target, rows[0])
    if route.get("status") != "CAPABILITY_MATCHED":
        raise AssertionError("selected candidate did not match its internal capability")
    if plan.get("candidate", {}).get("candidate_id") != selection.get(
        "selected_candidate_id"
    ):
        raise AssertionError("planner candidate identity differs from selection")

    write_json(fixture["plan_path"], plan)
    fixture["plan"] = plan
    fixture["candidate_provenance"] = provenance
    fixture["candidate_provenance_path"] = fixture["evidence"] / "candidate-provenance.json"
    write_json(fixture["candidate_provenance_path"], provenance)

    spec = json.loads(fixture["spec_path"].read_text(encoding="utf-8"))
    spec["target"].update(
        {
            "source_path": selection["selected_source_path"],
            "candidate_id": selection["selected_candidate_id"],
        }
    )
    write_json(fixture["spec_path"], spec)

    rewrite = plan["planned_rewrite"]
    preflight = json.loads(fixture["preflight_path"].read_text(encoding="utf-8"))
    preflight["target"].update(
        {
            "source_path": selection["selected_source_path"],
            "candidate_id": selection["selected_candidate_id"],
        }
    )
    preflight["plan_binding"] = {
        "plan_digest": digest_file(fixture["plan_path"]),
        "before_source_sha256": rewrite["before_source_sha256"],
        "planned_source_sha256": rewrite["planned_source_sha256"],
        "planned_diff_digest": _digest_text(rewrite["diff"]),
    }
    write_json(fixture["preflight_path"], preflight)

    auth = json.loads(fixture["authorization_path"].read_text(encoding="utf-8"))
    auth_binding = auth["binding"]
    auth_binding.update(
        {
            "candidate_id": selection["selected_candidate_id"],
            "source_path": selection["selected_source_path"],
            "before_source_sha256": rewrite["before_source_sha256"],
            "planned_source_sha256": rewrite["planned_source_sha256"],
            "plan_digest": digest_file(fixture["plan_path"]),
        }
    )
    site = (route.get("match_facts", {}) or {}).get("source_site", {}) or {}
    summary_bindings = {
        "candidate_provenance_digest": _canonical_digest(provenance),
        "candidate_task_digest": _digest_text(TASK),
        "target_revision": binding["target_revision"]["git_head"],
        "target_tree": binding["target_revision"]["git_tree"],
        "target_revision_digest": binding["target_revision"][
            "target_revision_digest"
        ],
        "working_tree_status_digest": binding["target_revision"][
            "working_tree_status_digest"
        ],
        "shared_graph_content_signature": binding[
            "shared_graph_content_signature"
        ],
        "discovery_snapshot_digest": binding["discovery_snapshot_digest"],
        "candidate_set_digest": binding["candidate_set"]["candidate_set_digest"],
        "candidate_selection_digest": selection["candidate_selection_digest"],
        "selected_candidate_id": selection["selected_candidate_id"],
        "selected_candidate_instance_id": selection[
            "selected_candidate_instance_id"
        ],
        "selected_source_path": selection["selected_source_path"],
        "selected_symbol": selection["selected_symbol"],
        "candidate_kind": selection["candidate_kind"],
        "selection_basis_digest": _canonical_digest(
            {"selection_basis": selection["selection_basis"]}
        ),
        "selection_confidence_boundary": selection[
            "selection_confidence_boundary"
        ],
        "rejected_alternative_count": len(selection["rejected_alternatives"]),
        "rejected_alternatives_digest": _canonical_digest(
            {"rejected_alternatives": selection["rejected_alternatives"]}
        ),
        "source_site_sha256": site["matched_source_sha256"],
        "source_char_start": site["char_start"],
        "source_char_end": site["char_end"],
        "matched_capability_id": route["matched_capability_id"],
        "candidate_capability_contract_digest": route[
            "capability_contract_digest"
        ],
    }
    auth_binding.update(summary_bindings)
    write_json(fixture["authorization_path"], auth)
    rebind_preflight_and_authorization(fixture)
    fixture["candidate_provenance_summary_bindings"] = summary_bindings
    return fixture


def _apply_and_issue(fixture: Dict[str, Any]) -> Dict[str, Any]:
    capability = apply_bounded_capability(
        root=fixture["target"],
        disposable_parent=fixture["base"],
        repository="reference/synthetic-js",
        capability_contract_path=fixture["contract_path"],
        plan_path=fixture["plan_path"],
        postcondition_spec_path=fixture["spec_path"],
        preflight_path=fixture["preflight_path"],
        authorization_path=fixture["authorization_path"],
        boundary_path=fixture["boundary_path"],
        ledger_path=fixture["ledger_path"],
        timeout_seconds=30,
        allow_pending=True,
        candidate_provenance_path=fixture["candidate_provenance_path"],
    )
    capability_path = fixture["evidence"] / "capability_receipt.json"
    write_json(capability_path, capability)
    issued = issue_bounded_capability_postconditions(
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
    return {"capability": capability, "issued": issued}


def _valid_lineage_reaches_issuance() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="plw_candidate_receipt_valid_") as temp:
        fixture = _prepare_fixture(Path(temp))
        result = _apply_and_issue(fixture)
        capability = result["capability"]
        issued = result["issued"]
        validation = json.loads(
            (fixture["evidence"] / "validation.json").read_text(encoding="utf-8")
        )
        ledger = _read_issuance_ledger(fixture["evidence"] / "issuance.jsonl")
        expected = fixture["candidate_provenance_summary_bindings"]
        persisted = validation.get("bindings", {})
        expected_persisted = dict(expected)
        expected_persisted["candidate_target_revision"] = expected_persisted.pop(
            "target_revision"
        )
        for source_key, persisted_key in (
            ("target_tree", "candidate_target_tree"),
            ("target_revision_digest", "candidate_target_revision_digest"),
            (
                "working_tree_status_digest",
                "candidate_working_tree_status_digest",
            ),
            (
                "shared_graph_content_signature",
                "candidate_shared_graph_content_signature",
            ),
        ):
            expected_persisted[persisted_key] = expected_persisted.pop(source_key)
        lineage_ok = all(
            persisted.get(key) == value
            for key, value in expected_persisted.items()
        )
        lineage_ok = lineage_ok and validation.get("target", {}).get(
            "revision"
        ) == expected["target_revision"]
        lineage_ok = lineage_ok and ledger[0].get("lineage") == persisted
        provenance_receipt = capability.get("candidate_provenance", {})
        ok = (
            issued.get("status")
            == "BOUNDED_CAPABILITY_POSTCONDITION_RECEIPT_ISSUED"
            and issued.get("validation_receipt_digest")
            == digest_file(fixture["evidence"] / "validation.json")
            and issued.get("issuance", {}).get("appended") is True
            and issued.get("postconditions", {}).get("validated") is True
            and issued.get("postconditions", {}).get("evidence_acceptance_granted")
            is False
            and provenance_receipt.get("candidate_selection_digest")
            == expected["candidate_selection_digest"]
            and lineage_ok
            and len(ledger) == 1
            and (issued.get("containment", {}) or {}).get("worktree_disposed")
            is True
            and not fixture["target"].exists()
            and not (fixture["evidence"] / "accepted.jsonl").exists()
        )
        return {
            "case": "resolved_candidate_lineage_reaches_issuance",
            "ok": ok,
            "issued_status": issued.get("status"),
            "candidate_selection_digest": expected["candidate_selection_digest"],
            "selected_candidate_id": expected["selected_candidate_id"],
            "issuance_records": len(ledger),
            "evidence_acceptance_granted": issued.get("postconditions", {}).get(
                "evidence_acceptance_granted"
            ),
        }


def _tampered_selection_rejected() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="plw_candidate_receipt_tamper_") as temp:
        fixture = _prepare_fixture(Path(temp))
        source_before = fixture["source"].read_bytes()
        provenance = json.loads(
            fixture["candidate_provenance_path"].read_text(encoding="utf-8")
        )
        provenance["candidate_selection"]["selected_symbol"] = "forgedSymbol"
        write_json(fixture["candidate_provenance_path"], provenance)
        try:
            _apply_and_issue(fixture)
            rejected = False
        except CapabilityError as exc:
            rejected = "does not match current target discovery" in str(exc)
        ok = (
            rejected
            and fixture["source"].read_bytes() == source_before
            and not fixture["ledger_path"].exists()
        )
        return {
            "case": "tampered_selection_rejected_before_mutation",
            "ok": ok,
            "target_unchanged": fixture["source"].read_bytes() == source_before,
            "authorization_consumed": fixture["ledger_path"].exists(),
        }


def _authorization_selection_mismatch_rejected() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="plw_candidate_receipt_auth_") as temp:
        fixture = _prepare_fixture(Path(temp))
        source_before = fixture["source"].read_bytes()
        auth = json.loads(fixture["authorization_path"].read_text(encoding="utf-8"))
        auth["binding"]["candidate_selection_digest"] = _digest_text("wrong selection")
        write_json(fixture["authorization_path"], auth)
        try:
            _apply_and_issue(fixture)
            rejected = False
        except CapabilityError as exc:
            rejected = "candidate_selection_digest" in str(exc)
        ok = (
            rejected
            and fixture["source"].read_bytes() == source_before
            and not fixture["ledger_path"].exists()
        )
        return {
            "case": "authorization_selection_mismatch_rejected_before_mutation",
            "ok": ok,
            "target_unchanged": fixture["source"].read_bytes() == source_before,
            "authorization_consumed": fixture["ledger_path"].exists(),
        }


def main() -> int:
    results = [
        _valid_lineage_reaches_issuance(),
        _tampered_selection_rejected(),
        _authorization_selection_mismatch_rejected(),
    ]
    failed = [result for result in results if not result.get("ok")]
    print(
        json.dumps(
            {
                "schema_version": "plw-js-ts-candidate-provenance-receipt-check-v1",
                "status": "PASS" if not failed else "FAIL",
                "cases": results,
                "retained_corpus_appended": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
