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
mkdir -p "$TMP/home" "$TMP/state" "$TMP/cache" "$TMP/target/src"
cat > "$TMP/target/src/guards.js" <<'EOF'
function isReady(node) {
  if (node.type === 'ready') {
    return true;
  }
  return false;
}
EOF

HOME="$TMP/home" XDG_STATE_HOME="$TMP/state" XDG_CACHE_HOME="$TMP/cache" \
  "$BIN" agent orient "$TMP/target" \
    --task "Explain the exact simplification candidate in src/guards.js" \
    --json > "$TMP/orient.json"

python - "$TMP/orient.json" <<'PY'
import json
from pathlib import Path
import sys

path = Path(sys.argv[1])
payload = json.loads(path.read_text())
raw_bytes = len(path.read_bytes())
selection = payload.get("capability_selection", {}) or {}
if selection.get("task_text_used_for_selection") is not False:
    raise SystemExit("task text leaked into capability projection")
rows = [x for x in selection.get("candidate_capabilities", []) or [] if isinstance(x, dict)]
if not rows:
    raise SystemExit("compact capability projection empty")
for row in rows:
    if not row.get("information_role"):
        raise SystemExit(f"missing information_role for {row.get('capability')}")
    for field in ("canonical_concepts", "expected_information_gain", "does_not_prove"):
        value = row.get(field)
        if not isinstance(value, list) or len(value) > 2:
            raise SystemExit(f"unbounded/missing {field} for {row.get('capability')}: {value}")

candidate = next((x for x in rows if x.get("capability") == "candidate"), None)
if candidate is None:
    raise SystemExit("candidate semantic affordance absent")
if candidate.get("coverage") != "CONDITIONAL_DISCOVERY" or candidate.get("state_change") is not False:
    raise SystemExit("candidate affordance authority/coverage widened")
if "candidate identity" not in candidate.get("canonical_concepts", []):
    raise SystemExit(f"candidate technical concept absent: {candidate.get('canonical_concepts')}")
if not candidate.get("expected_information_gain") or not candidate.get("does_not_prove"):
    raise SystemExit("candidate semantic gain/proof limits absent")

frame = payload.get("agent_decision_frame", {}) or {}
projection = frame.get("capability_projection", {}) or {}
frame_candidate = next((x for x in projection.get("candidates", []) or [] if isinstance(x, dict) and x.get("capability") == "candidate"), None)
if frame_candidate is None or not frame_candidate.get("information_role"):
    raise SystemExit("decision frame candidate information role absent")
if projection.get("action_priority_computed") is not False or projection.get("ranking_is_not_recommendation") is not True:
    raise SystemExit("decision frame widened semantic ranking into action recommendation")
if raw_bytes > 45000:
    raise SystemExit(f"compact orient context budget exceeded: {raw_bytes}")

print(
    "CANDIDATE_SEMANTIC_AFFORDANCE_BINARY: PASS "
    f"rows={len(rows)} bytes={raw_bytes} "
    f"candidate_concepts={len(candidate['canonical_concepts'])} "
    f"candidate_gain={len(candidate['expected_information_gain'])}"
)
PY
