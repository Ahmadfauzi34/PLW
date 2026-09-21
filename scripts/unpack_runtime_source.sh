#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MANIFEST="runtime_source/CAPSULE_SHA256"
EXPECTED="$(awk '{print $1}' "$MANIFEST")"
TMP_B64="$(mktemp)"
TMP_TGZ="$(mktemp)"
trap 'rm -f "$TMP_B64" "$TMP_TGZ"' EXIT

cat runtime_source/part*.b64 > "$TMP_B64"
base64 --decode "$TMP_B64" > "$TMP_TGZ"

ACTUAL="$(sha256sum "$TMP_TGZ" | awk '{print $1}')"
if [[ "$ACTUAL" != "$EXPECTED" ]]; then
  echo "runtime source capsule digest mismatch" >&2
  echo "expected=$EXPECTED" >&2
  echo "actual=$ACTUAL" >&2
  exit 1
fi

tar -xzf "$TMP_TGZ" -C "$ROOT"

echo "RUNTIME_SOURCE_CAPSULE: PASS sha256:$ACTUAL"
