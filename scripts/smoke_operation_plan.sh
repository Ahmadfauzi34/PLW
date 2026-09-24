#!/usr/bin/env bash
set -euo pipefail

BIN="${1:-artifacts/plw-linux-x86_64}"
if [[ ! -x "$BIN" ]]; then
  echo "binary not executable: $BIN" >&2
  exit 2
fi
BIN="$(cd "$(dirname "$BIN")" && pwd)/$(basename "$BIN")"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/project"
printf 'sentinel\n' > "$TMP/project/UNCHANGED.txt"

cat > "$TMP/exact.json" <<EOF
{
  "schema_version": "plw-operation-plan-v1",
  "capability": "candidate",
  "operation_id": "candidate.select.v1",
  "inputs": {
    "task": "Select isOne in src/guards.js",
    "root": "$TMP/project"
  }
}
EOF

cat > "$TMP/ambiguous.json" <<EOF
{
  "schema_version": "plw-operation-plan-v1",
  "capability": "candidate",
  "inputs": {
    "task": "Select isOne in src/guards.js",
    "root": "$TMP/project"
  }
}
EOF

cat > "$TMP/rejected.json" <<'EOF'
{
  "schema_version": "unsupported",
  "capability": "candidate",
  "inputs": {}
}
EOF

HOME="$TMP/home" XDG_STATE_HOME="$TMP/state" XDG_CACHE_HOME="$TMP/cache" \
  "$BIN" operation-plan resolve "$TMP/exact.json" --json > "$TMP/exact.out.json"
HOME="$TMP/home" XDG_STATE_HOME="$TMP/state" XDG_CACHE_HOME="$TMP/cache" \
  "$BIN" operation-plan resolve "$TMP/ambiguous.json" --json > "$TMP/ambiguous.out.json"
HOME="$TMP/home" XDG_STATE_HOME="$TMP/state" XDG_CACHE_HOME="$TMP/cache" \
  "$BIN" operation-plan resolve "$TMP/rejected.json" --json > "$TMP/rejected.out.json"

python - "$TMP" <<'PY'
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
exact = json.loads((root / "exact.out.json").read_text())
ambiguous = json.loads((root / "ambiguous.out.json").read_text())
rejected = json.loads((root / "rejected.out.json").read_text())

assert exact["schema_version"] == "plw-operation-plan-resolution-v1", exact
assert exact["status"] == "RESOLVED", exact
assert exact["reason"] == "EXACT_OPERATION_BINDING_RESOLVED", exact
assert exact["resolved_operation_id"] == "candidate.select.v1", exact
assert exact["next_gate"] == "AGENT_MAY_CHOOSE_INVOCATION", exact
assert exact["executes_operation"] is False, exact
assert exact["authority"]["invocation_authorized"] is False, exact
assert exact["authority"]["mutates_source"] is False, exact
assert exact["authority"]["commits_truth"] is False, exact
assert isinstance(exact.get("compiled_argv"), list) and exact["compiled_argv"], exact

assert ambiguous["status"] == "AMBIGUOUS", ambiguous
assert ambiguous["reason"] == "MULTIPLE_OPERATION_BINDINGS_ACCEPT_INPUTS", ambiguous
assert ambiguous["next_gate"] == "SELECT_EXACT_OPERATION_ID", ambiguous
assert ambiguous["compiled_argv"] is None, ambiguous
assert ambiguous["authority"]["invocation_authorized"] is False, ambiguous

assert rejected["status"] == "REJECTED", rejected
assert rejected["reason"] == "PLAN_SCHEMA_UNSUPPORTED", rejected
assert rejected["authority"]["invocation_authorized"] is False, rejected
assert rejected["executes_operation"] is False, rejected

sentinel = (root / "project" / "UNCHANGED.txt").read_text()
assert sentinel == "sentinel\n", sentinel
for forbidden in ("data/runtime", "data/codebase/cache"):
    assert not (root / "project" / forbidden).exists(), forbidden

print(
    "STANDALONE_OPERATION_PLAN_SMOKE: PASS "
    "states=RESOLVED/AMBIGUOUS/REJECTED authority=false target_unchanged=true"
)
PY
