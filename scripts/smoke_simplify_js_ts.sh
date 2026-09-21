#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="${1:-$ROOT/artifacts/plw-linux-x86_64}"

if [[ ! -x "$BIN" ]]; then
  echo "binary not executable: $BIN" >&2
  exit 2
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/home" "$TMP/run" "$TMP/project"
cp "$BIN" "$TMP/run/plw"
chmod +x "$TMP/run/plw"

cat > "$TMP/project/a.ts" <<'EOF'
function target(x: number) { return x; }
class A {
  private wrap(x: number) { return target(x); }
}
EOF

cat > "$TMP/project/b.tsx" <<'EOF'
function flag(x: boolean) {
  if (x) { return true; }
  return false;
}
EOF

cat > "$TMP/project/c.js" <<'EOF'
function choose(x) {
  if (x) { return 1; }
  else { return 2; }
}
EOF

cat > "$TMP/project/d.jsx" <<'EOF'
function compute(x) { return x + 1; }
function value(x) {
  const result = compute(x);
  return result;
}
EOF

cd "$TMP/run"
export HOME="$TMP/home"
export XDG_STATE_HOME="$TMP/home/state"
export XDG_CACHE_HOME="$TMP/home/cache"

./plw simplify "$TMP/project" --json > "$TMP/simplify.json"

python - "$TMP/simplify.json" "$TMP/project" <<'PY'
import json
from pathlib import Path
import sys

payload = json.loads(Path(sys.argv[1]).read_text())
project = Path(sys.argv[2])

bridge = payload.get("canonical_anatomy_bridge", {})
scope = bridge.get("semantic_frontend_scope", {})
inventory = bridge.get("language_inventory", {})
counts = inventory.get("reference_source_counts", {})

if bridge.get("semantic_frontend") != "python_ast+js_structural_v2":
    raise SystemExit(f"unexpected frontend: {bridge.get('semantic_frontend')}")
if scope.get("ts_js_rule_count") != 7:
    raise SystemExit(f"unexpected TS/JS rule count: {scope.get('ts_js_rule_count')}")

for ext in (".ts", ".tsx", ".js", ".jsx"):
    if counts.get(ext) != 1:
        raise SystemExit(f"expected exactly one {ext} fixture, got {counts.get(ext)}")
    if inventory.get("semantic_rule_frontends", {}).get(ext) != "js_structural_v2":
        raise SystemExit(f"{ext} not bound to js_structural_v2")

kinds = {row.get("kind") for row in payload.get("candidates", [])}
required = {
    "js_direct_forwarding_wrapper",
    "js_boolean_guard_return",
    "js_redundant_else_after_terminal",
    "js_terminal_expression_temporary",
}
missing = required - kinds
if missing:
    raise SystemExit(f"missing expected JS/TS v2 candidate kinds: {sorted(missing)}")

if payload.get("invariants", {}).get("js_structural_frontend_v2_is_not_a_full_js_ts_parser") is not True:
    raise SystemExit("JS/TS v2 parser boundary invariant missing")

for forbidden in ("data/runtime", "data/codebase/cache"):
    if (project / forbidden).exists():
        raise SystemExit(f"target repository polluted by PLW runtime state: {forbidden}")

print("STANDALONE_SIMPLIFY_JS_TS_V2: PASS")
PY
