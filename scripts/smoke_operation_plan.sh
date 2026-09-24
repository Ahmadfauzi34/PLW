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
mkdir -p "$TMP/project/src"
cat > "$TMP/project/src/guards.js" <<'EOF'
function isOne(node) {
  if (node.type === 'one') {
    return true;
  }
  return false;
}
EOF

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

python - "$TMP" "$BIN" <<'PY'
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1])
binary = Path(sys.argv[2])
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

plan_document = json.loads((root / "exact.json").read_text())
env = {**os.environ, "HOME": str(root / "home"), "XDG_STATE_HOME": str(root / "state"),
       "XDG_CACHE_HOME": str(root / "cache")}
target = root / "project"
before = {str(p.relative_to(target)): p.read_bytes() for p in target.rglob("*") if p.is_file()}

def resolve(plan):
    proc = subprocess.run([str(binary), "operation-plan", "resolve", "-", "--json"],
                          input=json.dumps(plan), text=True, capture_output=True, env=env, cwd=root)
    assert proc.returncode == 0 and not proc.stderr, proc.stderr
    return json.loads(proc.stdout)

def invoke(binding, task):
    argv = binding["compiled_argv"]
    assert argv and argv[0] == "plw", binding
    proc = subprocess.run([str(binary), *argv[1:]], text=True, capture_output=True,
                          env=env, cwd=root)
    assert proc.returncode == 0 and not proc.stderr, (argv, proc.stderr)
    result = json.loads(proc.stdout)
    assert result["candidate_selection"]["task"] == task, result
    assert result["candidate_selection"]["resolution"] in {"RESOLVED", "AMBIGUOUS", "UNRESOLVED"}
    return result

assert invoke(exact, plan_document["inputs"]["task"])["candidate_selection"]["resolution"] == "RESOLVED"
assert resolve(plan_document)["plan_digest"] == exact["plan_digest"], "stdin and file diverged"
for task in ("-h", "--json", "task with spaces"):
    altered = json.loads(json.dumps(plan_document))
    altered["inputs"]["task"] = task
    binding = resolve(altered)
    assert binding["status"] == "RESOLVED", binding
    assert binding["authority"]["invocation_authorized"] is False
    invoke(binding, task)

for invalid_task in ("\x00", "\ud800"):
    invalid_plan = json.loads(json.dumps(plan_document))
    invalid_plan["inputs"]["task"] = invalid_task
    invalid_binding = resolve(invalid_plan)
    assert invalid_binding["status"] == "REJECTED" and invalid_binding.get("compiled_argv") is None
    assert any(err.get("code") == "INPUT_VALUE_UNREPRESENTABLE_IN_ARGV"
               for row in invalid_binding["candidate_bindings"] for err in row["binding_errors"]), invalid_binding

space_root = root / "project with spaces"
(space_root / "src").mkdir(parents=True)
(space_root / "src/guards.js").write_text((target / "src/guards.js").read_text())
space_plan = json.loads(json.dumps(plan_document))
space_plan["inputs"]["root"] = str(space_root)
assert invoke(resolve(space_plan), space_plan["inputs"]["task"])["candidate_selection"]["resolution"] == "RESOLVED"

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
after = {str(p.relative_to(target)): p.read_bytes() for p in target.rglob("*") if p.is_file()}
assert before == after, "plan/invocation modified target"

print(
    "STANDALONE_OPERATION_PLAN_SMOKE: PASS "
    "states=RESOLVED/AMBIGUOUS/REJECTED argv_round_trip=true authority=false target_unchanged=true"
)
PY
