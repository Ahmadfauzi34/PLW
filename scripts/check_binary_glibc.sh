#!/usr/bin/env bash
set -euo pipefail

BIN="${1:?binary path required}"
CEILING="${2:?GLIBC ceiling required}"

readelf -h "$BIN" | grep -Eq 'Machine:[[:space:]]+Advanced Micro Devices X86-64'
versions="$(readelf -W --version-info "$BIN" | grep -oE 'GLIBC_[0-9]+\.[0-9]+' || true)"
if [[ -z "$versions" ]]; then
  echo "ELF_GLIBC_CEILING: FAIL missing GLIBC symbols in bootloader" >&2
  exit 1
fi
highest="$(printf '%s\n' "$versions" | sed 's/^GLIBC_//' | sort -V | tail -1)"
if [[ "$(printf '%s\n' "$highest" "$CEILING" | sort -V | tail -1)" != "$CEILING" ]]; then
  echo "ELF_GLIBC_CEILING: FAIL bootloader requires $highest, ceiling $CEILING" >&2
  exit 1
fi
echo "ELF_GLIBC_CEILING: PASS bootloader=$highest ceiling=$CEILING (bundled libraries require runtime proof)"
