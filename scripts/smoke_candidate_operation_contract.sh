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
mkdir -p "$TMP/run" "$TMP/home" "$TMP/state" "$TMP/cache" "$TMP/target/src"
cp "$BIN" "$TMP/run/plw"
cat > "$TMP/target/src/guards.js" <<'EOF'
function isOne(node) {
  if (node.type === 'one') { return true; }
  return false;
}

function isTwo(node) {
  if (node.type === 'two') { return true; }
  return false;
}
EOF

find "$TMP/target" -type f -print0 | sort -z | xargs -0 sha256sum > "$TMP/before.sha256"
cd "$TMP/run"
export HOME="$TMP/home"
export XDG_STATE_HOME="$TMP/state"
export XDG_CACHE_HOME="$TMP/cache"

./plw capability describe candidate --json > "$TMP/contract.json"
./plw agent orient "$TMP/target" --task "Select isOne in src/guards.js" --json > "$TMP/orient.json"
./plw candidate select "Select isOne in src/guards.js" "$TMP/target" --json > "$TMP/resolved.json"
./plw candidate select "Select one boolean guard with opposite boolean returns" "$TMP/target" --json > "$TMP/ambiguous.json"
./plw candidate capability-match "Select isOne in src/guards.js" "$TMP/target" --json > "$TMP/matched.json"

find "$TMP/target" -type f -print0 | sort -z | xargs -0 sha256sum > "$TMP/after.sha256"
cmp "$TMP/before.sha256" "$TMP/after.sha256"

python - "$TMP" <<'PY'
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
contract = json.loads((root / "contract.json").read_text())
orient = json.loads((root / "orient.json").read_text())
resolved = json.loads((root / "resolved.json").read_text())
ambiguous = json.loads((root / "ambiguous.json").read_text())
matched = json.loads((root / "matched.json").read_text())

ops = contract.get("operation_contracts", []) or []
ids = [row.get("operation_id") for row in ops]
if ids != ["candidate.select.v1", "candidate.capability-match.v1"]:
    raise SystemExit(f"standalone operation contract IDs drifted: {ids}")
for row in ops:
    if row.get("schema_version") != "plw-operation-contract-v1":
        raise SystemExit("standalone operation schema missing")
    if any((row.get("authority", {}) or {}).values()):
        raise SystemExit("standalone operation contract grants authority")

selection = orient.get("capability_selection", {}) or {}
candidate = next((row for row in selection.get("candidate_capabilities", []) if row.get("capability") == "candidate"), None)
if candidate is None:
    raise SystemExit("candidate missing from standalone orient")
if candidate.get("operation_contract_available") is not True or candidate.get("operation_contract_count") != 2:
    raise SystemExit("orient does not advertise recoverable operation contract")
if "operation_contracts" in candidate:
    raise SystemExit("full operation contracts leaked into compact orient")
if selection.get("task_text_used_for_selection") is not False:
    raise SystemExit("operation contract changed evidence-class routing")
if resolved.get("candidate_selection", {}).get("resolution") != "RESOLVED":
    raise SystemExit("standalone resolved outcome drifted")
if ambiguous.get("candidate_selection", {}).get("resolution") != "AMBIGUOUS":
    raise SystemExit("standalone ambiguous outcome drifted")
if matched.get("candidate_capability_match", {}).get("status") != "CAPABILITY_MATCHED":
    raise SystemExit("standalone capability-match outcome drifted")

print(
    "CANDIDATE_OPERATION_CONTRACT_BINARY: PASS "
    f"operations={len(ops)} orient_marker={candidate['operation_contract_count']} "
    "domain_outcomes=zero-exit target_unchanged=true"
)
PY
