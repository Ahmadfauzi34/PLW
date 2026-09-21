#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OVERLAY_DIR="runtime_overlay/js_ts_v2"
MANIFEST="$OVERLAY_DIR/OVERLAY_SHA256"

if [[ ! -f "$MANIFEST" ]]; then
  echo "RUNTIME_OVERLAY: none"
  exit 0
fi

TMP_B64="$(mktemp)"
TMP_PATCH="$(mktemp)"
trap 'rm -f "$TMP_B64" "$TMP_PATCH"' EXIT

cat "$OVERLAY_DIR"/part*.b64 > "$TMP_B64"
tr -d '\r\n' < "$TMP_B64" | base64 --decode > "$TMP_PATCH"

EXPECTED="$(awk '{print $1}' "$MANIFEST")"
ACTUAL="$(sha256sum "$TMP_PATCH" | awk '{print $1}')"

if [[ "$ACTUAL" != "$EXPECTED" ]]; then
  echo "runtime overlay digest mismatch" >&2
  echo "expected=$EXPECTED" >&2
  echo "actual=$ACTUAL" >&2
  exit 1
fi

patch --dry-run --batch --forward -p1 < "$TMP_PATCH" >/dev/null
patch --batch --forward -p1 < "$TMP_PATCH" >/dev/null

grep -q 'self-simplification-v14-js-structural-v2' core/simplification_analyzer.py
grep -q 'python_ast+js_structural_v2' core/simplification_analyzer.py

echo "RUNTIME_OVERLAY_JS_TS_V2: PASS sha256:$ACTUAL"
