#!/usr/bin/env python3
"""Reference checks for machine-readable candidate operation contracts."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.capability_selection import build_capability_selection
from core.semantic_affordance import describe_command


def fail(message: str) -> None:
    raise SystemExit(message)


def by_id(rows: list[dict], operation_id: str) -> dict:
    for row in rows:
        if row.get("operation_id") == operation_id:
            return row
    fail(f"operation contract missing: {operation_id}")


def run_candidate(operation: str, task: str, root: Path) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "plw_cli.py"), "candidate", operation, task, str(root), "--json"],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.stderr.strip():
        fail(f"unexpected candidate stderr for {operation}: {proc.stderr.strip()}")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        fail(f"candidate {operation} did not return JSON: {exc}")
    return proc.returncode, payload


contract = describe_command("candidate")
operations = contract.get("operation_contracts", []) or []
if len(operations) != 2:
    fail(f"expected two candidate operation contracts, got {len(operations)}")
select = by_id(operations, "candidate.select.v1")
match = by_id(operations, "candidate.capability-match.v1")
for row in (select, match):
    if row.get("schema_version") != "plw-operation-contract-v1":
        fail("operation contract schema drifted")
    authority = row.get("authority", {}) or {}
    if any(authority.values()):
        fail(f"operation contract unexpectedly grants authority: {authority}")
    inputs = (row.get("invocation", {}) or {}).get("inputs", []) or []
    roles = {item.get("name"): item.get("role") for item in inputs}
    if roles != {"task": "task_evidence", "root": "target_root"}:
        fail(f"operation input roles drifted: {roles}")
    root_input = next(item for item in inputs if item.get("name") == "root")
    if root_input.get("required") is not False or root_input.get("default") != ".":
        fail("candidate root input no longer reflects CLI default")
    if root_input.get("path_existence_required_by_cli") is not False:
        fail("operation contract incorrectly claims root existence prevalidation")
    failure_model = row.get("failure_model", {}) or {}
    if failure_model.get("domain_outcomes_are_not_process_failures") is not True:
        fail("domain outcomes were conflated with process failures")

select_output = select.get("output", {}) or {}
if select_output.get("domain_state_path") != "candidate_selection.resolution":
    fail("select state path drifted")
if select_output.get("domain_states") != ["RESOLVED", "AMBIGUOUS", "UNRESOLVED"]:
    fail("select domain states drifted")
if select_output.get("domain_outcomes_exit_code") != 0:
    fail("select domain exit-code contract drifted")
if (select.get("capacity", {}) or {}).get("ambiguity_policy") != "preserve_ambiguity_do_not_guess":
    fail("select ambiguity capacity boundary drifted")

match_output = match.get("output", {}) or {}
if match_output.get("match_state_path") != "candidate_capability_match.status":
    fail("capability-match state path drifted")
if match_output.get("match_states") != ["CAPABILITY_MATCHED", "CAPABILITY_NOT_MATCHED"]:
    fail("capability-match states drifted")

selection = build_capability_selection({
    "stage": "EVIDENCE_NEEDS_DERIVED",
    "selected_targets": ["src/guards.js"],
    "evidence_needed": [{
        "evidence_class": "semantic_scope",
        "need": "semantic implementation scope evidence",
        "reason": "fixture",
    }],
})
projected = next(
    (row for row in selection.get("candidate_capabilities", []) if row.get("capability") == "candidate"),
    None,
)
if projected is None:
    fail("candidate capability not projected")
if projected.get("operation_contract_available") is not True or projected.get("operation_contract_count") != 2:
    fail("agent handoff cannot discover candidate operation contracts")

with tempfile.TemporaryDirectory(prefix="plw-operation-contract-") as tmp:
    target = Path(tmp) / "target"
    target.mkdir()
    (target / "guards.js").write_text(
        "function isOne(node) {\n"
        "  if (node.type === 'one') {\n"
        "    return true;\n"
        "  }\n"
        "  return false;\n"
        "}\n\n"
        "function isTwo(node) {\n"
        "  if (node.type === 'two') {\n"
        "    return true;\n"
        "  }\n"
        "  return false;\n"
        "}\n",
        encoding="utf-8",
    )

    rc, resolved = run_candidate("select", "Select isOne in guards.js", target)
    if rc != 0 or resolved.get("candidate_selection", {}).get("resolution") != "RESOLVED":
        fail("observed RESOLVED outcome disagrees with operation contract")

    rc, ambiguous = run_candidate("select", "Select one boolean guard with opposite boolean returns", target)
    if rc != 0 or ambiguous.get("candidate_selection", {}).get("resolution") != "AMBIGUOUS":
        fail("observed AMBIGUOUS outcome disagrees with operation contract")

    rc, empty_task = run_candidate("select", "", target)
    if rc != 0 or empty_task.get("candidate_selection", {}).get("resolution") != "UNRESOLVED":
        fail("empty task is no longer a zero-exit domain UNRESOLVED outcome")

    rc, missing_root = run_candidate("select", "Select isOne", Path(tmp) / "missing")
    if rc != 0 or missing_root.get("candidate_selection", {}).get("resolution") != "UNRESOLVED":
        fail("missing root behavior no longer matches operation failure model")

    rc, matched = run_candidate("capability-match", "Select isOne in guards.js", target)
    if rc != 0 or matched.get("candidate_capability_match", {}).get("status") != "CAPABILITY_MATCHED":
        fail("observed CAPABILITY_MATCHED outcome disagrees with operation contract")

    rc, not_matched = run_candidate("capability-match", "Select one boolean guard with opposite boolean returns", target)
    if rc != 0 or not_matched.get("candidate_capability_match", {}).get("status") != "CAPABILITY_NOT_MATCHED":
        fail("ambiguous selection no longer yields CAPABILITY_NOT_MATCHED")

print(
    "CANDIDATE_OPERATION_CONTRACT_REFERENCE: PASS "
    "operations=2 inputs=task/root domain_states=RESOLVED/AMBIGUOUS/UNRESOLVED "
    "match_states=CAPABILITY_MATCHED/CAPABILITY_NOT_MATCHED missing_root=domain_UNRESOLVED"
)
