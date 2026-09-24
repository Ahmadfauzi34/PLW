#!/usr/bin/env bash
set -euo pipefail

BIN="${1:-artifacts/plw-linux-x86_64}"
BIN="$(realpath "$BIN")"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
TARGET="$TMP/target"
mkdir -p "$TARGET/src" "$TMP/home" "$TMP/state" "$TMP/cache"

cat > "$TARGET/src/a.js" <<'JS'
export function positiveGuard(kind) {
  const keep = 1;
  if (kind === "map") {
    return true;
  }
  return false;
}
JS

cat > "$TARGET/src/b.ts" <<'TS'
export function inverseGuard(name) {
  if (name === "arguments") {
    return false;
  }
  return true;
}
TS

git -C "$TARGET" init -q
git -C "$TARGET" config user.email smoke@example.invalid
git -C "$TARGET" config user.name "PLW Smoke"
git -C "$TARGET" add .
git -C "$TARGET" commit -qm init

run_plw() {
  HOME="$TMP/home" XDG_STATE_HOME="$TMP/state" XDG_CACHE_HOME="$TMP/cache" "$BIN" "$@"
}

POS_TASK='Find a boolean guard using === with string literal in positive form'
INV_TASK='Find a boolean guard using === with string literal in inverse form'
GENERIC_TASK='Review boolean guard candidates'
CONFLICT_TASK='Review symbol positiveGuard in src/b.ts'
MISSING_TASK='Review boolean guard using === in src/missing.js'

run_plw candidate select "$POS_TASK" "$TARGET" --json > "$TMP/positive-select.json"
run_plw candidate capability-match "$POS_TASK" "$TARGET" --json > "$TMP/positive-match.json"
run_plw candidate select "$INV_TASK" "$TARGET" --json > "$TMP/inverse-select.json"
run_plw candidate capability-match "$INV_TASK" "$TARGET" --json > "$TMP/inverse-match.json"
run_plw candidate select "$GENERIC_TASK" "$TARGET" --json > "$TMP/generic.json"
run_plw candidate select "$CONFLICT_TASK" "$TARGET" --json > "$TMP/conflict.json"
run_plw candidate select "$MISSING_TASK" "$TARGET" --json > "$TMP/missing.json"

python - "$TMP" <<'PY'
import json
from pathlib import Path
import sys
p = Path(sys.argv[1])
def load(name):
    return json.loads((p / name).read_text())

pos = load("positive-select.json")
posm = load("positive-match.json")
inv = load("inverse-select.json")
invm = load("inverse-match.json")
generic = load("generic.json")
conflict = load("conflict.json")
missing = load("missing.json")

assert pos["status"] == "RESOLVED", pos
assert pos["selected_candidate"]["symbol"] == "positiveGuard", pos
assert pos["selected_candidate"]["source_path"] == "src/a.js", pos
assert pos["selected_candidate"]["semantic_witness"]["polarity"] == "positive", pos
assert posm["status"] == "CAPABILITY_MATCHED", posm
assert posm["selection"]["selection_digest"] == pos["selection_digest"], (posm, pos)
assert posm["authority"]["authorization_granted"] is False, posm
assert posm["authority"]["mutation_granted"] is False, posm

assert inv["status"] == "RESOLVED", inv
assert inv["selected_candidate"]["symbol"] == "inverseGuard", inv
assert inv["selected_candidate"]["source_path"] == "src/b.ts", inv
assert inv["selected_candidate"]["semantic_witness"]["polarity"] == "inverse", inv
assert invm["status"] == "CAPABILITY_MATCHED", invm

assert generic["status"] == "AMBIGUOUS", generic
assert conflict["status"] == "UNRESOLVED", conflict
assert missing["status"] == "UNRESOLVED", missing

for result in (pos, inv, generic, conflict, missing):
    auth = result["authority"]
    assert auth["authorization_granted"] is False
    assert auth["execution_granted"] is False
    assert auth["mutation_granted"] is False
    assert auth["evidence_acceptance_granted"] is False
    assert auth["truth_commit"] is False

print("CANDIDATE_SELECTION_SMOKE: PASS")
PY

if [[ -n "$(git -C "$TARGET" status --porcelain --untracked-files=all)" ]]; then
  echo "candidate selection polluted target" >&2
  git -C "$TARGET" status --porcelain --untracked-files=all >&2
  exit 1
fi
