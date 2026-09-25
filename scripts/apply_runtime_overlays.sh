#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

apply_b64_overlay() {
  local overlay_name="$1"
  local overlay_dir="runtime_overlay/$overlay_name"
  local manifest="$overlay_dir/OVERLAY_SHA256"

  if [[ ! -f "$manifest" ]]; then
    echo "RUNTIME_OVERLAY_${overlay_name}: none"
    return 0
  fi

  local tmp_b64 tmp_patch expected actual
  tmp_b64="$(mktemp)"
  tmp_patch="$(mktemp)"
  cat "$overlay_dir"/part*.b64 > "$tmp_b64"
  tr -d '\r\n' < "$tmp_b64" | base64 --decode > "$tmp_patch"

  expected="$(awk '{print $1}' "$manifest")"
  actual="$(sha256sum "$tmp_patch" | awk '{print $1}')"
  if [[ "$actual" != "$expected" ]]; then
    echo "runtime overlay digest mismatch: $overlay_name" >&2
    echo "expected=$expected" >&2
    echo "actual=$actual" >&2
    rm -f "$tmp_b64" "$tmp_patch"
    exit 1
  fi

  patch --dry-run --batch --forward -p1 < "$tmp_patch" >/dev/null
  patch --batch --forward -p1 < "$tmp_patch" >/dev/null
  rm -f "$tmp_b64" "$tmp_patch"
  echo "RUNTIME_OVERLAY_${overlay_name}: PASS sha256:$actual"
}

apply_reviewable_overlay() {
  local overlay_name="$1"
  local overlay_dir="runtime_overlay/$overlay_name"
  local patch_file="$overlay_dir/change.patch"
  local manifest="$overlay_dir/PATCH_SHA256"
  if [[ ! -f "$patch_file" || ! -f "$manifest" ]]; then
    echo "reviewable overlay missing: $overlay_name" >&2
    exit 2
  fi
  local expected actual
  expected="$(awk '{print $1}' "$manifest")"
  actual="$(sha256sum "$patch_file" | awk '{print $1}')"
  if [[ "$actual" != "$expected" ]]; then
    echo "runtime overlay digest mismatch: $overlay_name" >&2
    exit 1
  fi
  patch --dry-run --batch --forward -p1 < "$patch_file" >/dev/null
  patch --batch --forward -p1 < "$patch_file" >/dev/null
  echo "RUNTIME_OVERLAY_${overlay_name}: PASS sha256:$actual"
}

apply_b64_overlay "js_ts_v2"
grep -q 'self-simplification-v14-js-structural-v2' core/simplification_analyzer.py
grep -q 'python_ast+js_structural_v2' core/simplification_analyzer.py

apply_b64_overlay "portable_agent_v1"
grep -q 'plw-portable-agent-v1' core/portable_agent.py
grep -q 'plw agent orient' plw_cli.py

apply_b64_overlay "validation_runtime_cli_v1"
grep -q 'parser.add_argument("--evidence-id", action="append"' plw_cli.py
grep -q 'F138 still requires exact identity/content agreement' skills/validation-runtime-dispatch-workflow.md

apply_b64_overlay "portable_topology_scope_v1"
grep -q 'def target_topology_support' core/portable_agent.py
grep -q 'TARGET_TOPOLOGY_LANGUAGE_UNSUPPORTED' plw_cli.py
grep -q 'experimental_python_promoted' core/portable_agent.py

apply_b64_overlay "candidate_selection_v1"
grep -q 'candidate-selection-provenance-v1' core/candidate_provenance.py
grep -q 'INTERNAL_CANDIDATE_CAPABILITIES' core/candidate_provenance.py
grep -q '_raw_source_site_facts' core/candidate_provenance.py
grep -q 'def cmd_candidate' plw_cli.py

apply_b64_overlay "shared_graph_determinism_v1"
grep -q 'return sorted(set(usages))' core/shared_graph.py
grep -q 'semantic_usages.*sorted(set(resolved_edge_usages' core/shared_graph.py

apply_b64_overlay "candidate_agent_handoff_v1"
grep -Fq '"candidate": _contract(' core/semantic_affordance.py
grep -Fq '"capability": "candidate", "coverage": "CONDITIONAL_DISCOVERY"' core/capability_selection.py
grep -Fq 'plw candidate select' skills/candidate-selection-provenance-workflow.md

apply_b64_overlay "candidate_affordance_projection_v1"
grep -Fq '"information_role": row.get("role")' hott_kernel.py
grep -Fq '"expected_information_gain": list(row.get("expected_information_gain", []) or [])[:2]' hott_kernel.py
grep -Fq '"information_role": row.get("information_role")' core/agent_communication.py

apply_b64_overlay "operation_contract_reference_v1"
grep -Fq 'OPERATION_CONTRACT_SCHEMA_VERSION = "plw-operation-contract-v1"' core/semantic_affordance.py
grep -Fq '"operation_contract_available": bool(contract.get("operation_contracts"))' core/capability_selection.py
grep -Fq '"operation_contract_count": int(row.get("operation_contract_count", 0) or 0)' hott_kernel.py

apply_b64_overlay "operation_plan_preflight_v1"
apply_b64_overlay "operation_plan_preflight_repair_v1"
apply_reviewable_overlay "invocation_snapshot_v1"
apply_reviewable_overlay "readiness_version_v1"
apply_reviewable_overlay "browserless_ui_reference_v1"
apply_reviewable_overlay "ui_source_precision_v1"
apply_reviewable_overlay "ui_render_conditions_v1"
apply_reviewable_overlay "ui_style_reference_v1"
apply_reviewable_overlay "ui_agent_handoff_v1"
grep -Fq '"stable_target_topology_ready"' core/portable_agent.py
grep -Fq '"task_postcondition": "UNPROVEN"' hott_kernel.py
grep -Fq '"plw-version-v1"' plw_cli.py
grep -Fq '"geometry_observed": False' codebase/static_ui_reference.py
grep -Fq '"ui-static": _contract(' core/semantic_affordance.py
grep -Fq 'def cmd_ui_static(' plw_cli.py
grep -Fq '"ui_source_handoff": ui_source_handoff' hott_kernel.py
grep -Fq 'PLAN_SCHEMA_VERSION = "plw-operation-plan-v1"' core/operation_plan.py
grep -Fq 'RESOLUTION_SCHEMA_VERSION = "plw-operation-plan-resolution-v1"' core/operation_plan.py
grep -Fq 'INPUT_VALUE_UNREPRESENTABLE_IN_ARGV' core/operation_plan.py
grep -Fq 'dirty_content_digest' core/candidate_provenance.py
python -m py_compile core/operation_plan.py
python - <<'PY'
from core.operation_plan import resolve_operation_plan

exact = resolve_operation_plan({
    "schema_version": "plw-operation-plan-v1",
    "capability": "candidate",
    "operation_id": "candidate.select.v1",
    "inputs": {"task": "Select isOne in src/guards.js", "root": "."},
})
assert exact["status"] == "RESOLVED", exact
assert exact["reason"] == "EXACT_OPERATION_BINDING_RESOLVED", exact
assert exact["next_gate"] == "AGENT_MAY_CHOOSE_INVOCATION", exact
assert exact["authority"]["invocation_authorized"] is False, exact
assert exact["executes_operation"] is False, exact

ambiguous = resolve_operation_plan({
    "schema_version": "plw-operation-plan-v1",
    "capability": "candidate",
    "inputs": {"task": "Select isOne in src/guards.js", "root": "."},
})
assert ambiguous["status"] == "AMBIGUOUS", ambiguous
assert ambiguous["next_gate"] == "SELECT_EXACT_OPERATION_ID", ambiguous
assert ambiguous["authority"]["invocation_authorized"] is False, ambiguous

rejected = resolve_operation_plan({
    "schema_version": "unsupported",
    "capability": "candidate",
    "inputs": {},
})
assert rejected["status"] == "REJECTED", rejected
assert rejected["reason"] == "PLAN_SCHEMA_UNSUPPORTED", rejected
assert rejected["authority"]["invocation_authorized"] is False, rejected

print("RUNTIME_OPERATION_PLAN_PREFLIGHT: PASS")
PY
