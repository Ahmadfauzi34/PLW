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

apply_b64_overlay "js_ts_v2"
grep -q 'self-simplification-v14-js-structural-v2' core/simplification_analyzer.py
grep -q 'python_ast+js_structural_v2' core/simplification_analyzer.py

apply_b64_overlay "portable_agent_v1"
grep -q 'plw-portable-agent-v1' core/portable_agent.py
grep -q 'plw agent orient' plw_cli.py

apply_b64_overlay "validation_runtime_cli_v1"
grep -q 'parser.add_argument("--evidence-id", action="append"' plw_cli.py
grep -q 'F138 still requires exact identity/content agreement' skills/validation-runtime-dispatch-workflow.md
