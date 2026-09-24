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

apply_raw_overlay_set() {
  local overlay_name="$1"
  local overlay_dir="runtime_overlay/$overlay_name"
  local manifest="$overlay_dir/OVERLAY_SHA256"

  if [[ ! -f "$manifest" ]]; then
    echo "RUNTIME_OVERLAY_${overlay_name}: none"
    return 0
  fi

  while read -r expected filename; do
    [[ -n "${expected:-}" && -n "${filename:-}" ]] || continue
    local patch_file="$overlay_dir/$filename"
    local actual
    actual="$(sha256sum "$patch_file" | awk '{print $1}')"
    if [[ "$actual" != "$expected" ]]; then
      echo "runtime overlay digest mismatch: $overlay_name/$filename" >&2
      echo "expected=$expected" >&2
      echo "actual=$actual" >&2
      exit 1
    fi
    patch --dry-run --batch --forward -p1 < "$patch_file" >/dev/null
    patch --batch --forward -p1 < "$patch_file" >/dev/null
    echo "RUNTIME_OVERLAY_${overlay_name}: PASS $filename sha256:$actual"
  done < "$manifest"
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

apply_raw_overlay_set "candidate_selection_v1"
grep -q 'plw-candidate-selection-provenance-v1' core/candidate_selection.py
grep -q 'js_boolean_guard_return_v3_exact_span' core/simplification_analyzer.py
grep -q 'plw candidate capability-match' plw_cli.py
