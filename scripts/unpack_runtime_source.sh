#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CAPSULE="runtime_source/plw-runtime-src.tar.gz"
MANIFEST="runtime_source/CAPSULE_SHA256"

if [[ ! -f "$CAPSULE" ]]; then
  echo "runtime source capsule is missing: $CAPSULE" >&2
  exit 2
fi

EXPECTED="$(awk '{print $1}' "$MANIFEST")"
ACTUAL="$(sha256sum "$CAPSULE" | awk '{print $1}')"

if [[ "$ACTUAL" != "$EXPECTED" ]]; then
  echo "runtime source capsule digest mismatch" >&2
  echo "expected=$EXPECTED" >&2
  echo "actual=$ACTUAL" >&2
  exit 1
fi

tar -xzf "$CAPSULE" -C "$ROOT"

echo "RUNTIME_SOURCE_CAPSULE: PASS sha256:$ACTUAL"

bash scripts/apply_runtime_overlays.sh
