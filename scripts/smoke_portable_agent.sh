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
printf 'export const value = 1;\n' > "$TMP/target/src/value.ts"
printf 'import { value } from "./value";\nconsole.log(value);\n' > "$TMP/target/src/main.ts"
cat > "$TMP/target/src/guards.js" <<'EOF'
function isSCSSMapItemNode(node) {
  if (node.type === 'map-item') {
    return true;
  }
  return false;
}

function isRefIdentifier(id) {
  if (id.name === 'arguments') {
    return false;
  }
  return true;
}
EOF

cd "$TMP/run"
export HOME="$TMP/home"
export XDG_STATE_HOME="$TMP/state"
export XDG_CACHE_HOME="$TMP/cache"

./plw doctor "$TMP/target" --json > "$TMP/doctor.json"
./plw capability list --json > "$TMP/capabilities.json"
./plw skill list --json > "$TMP/skills.json"
./plw skill show topology --json > "$TMP/skill-topology.json"
./plw skill show candidate --json > "$TMP/skill-candidate.json"
./plw agent orient "$TMP/target" --task "understand how main uses value" --json > "$TMP/orient.json"
./plw agent orient "$TMP/target" --task "Explain why isSCSSMapItemNode in src/guards.js is a bounded simplification candidate" --json > "$TMP/candidate-orient.json"
./plw candidate select "Explain why isSCSSMapItemNode is a bounded boolean guard candidate" "$TMP/target" --json > "$TMP/selection.json"
./plw candidate capability-match "Explain why isSCSSMapItemNode is a bounded boolean guard candidate" "$TMP/target" --json > "$TMP/candidate-route.json"
./plw candidate capability-match "Select one boolean guard with opposite boolean returns" "$TMP/target" --json > "$TMP/ambiguous-route.json"

python - "$TMP" "$ROOT/VERSION" <<'PY'
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
version = Path(sys.argv[2]).read_text(encoding="utf-8").strip()
doctor = json.loads((root / "doctor.json").read_text())
caps = json.loads((root / "capabilities.json").read_text())
skills = json.loads((root / "skills.json").read_text())
skill = json.loads((root / "skill-topology.json").read_text())
candidate_skill = json.loads((root / "skill-candidate.json").read_text())
orient = json.loads((root / "orient.json").read_text())
candidate_orient = json.loads((root / "candidate-orient.json").read_text())
selection = json.loads((root / "selection.json").read_text())
candidate_route = json.loads((root / "candidate-route.json").read_text())
ambiguous_route = json.loads((root / "ambiguous-route.json").read_text())
target = root / "target"

if doctor.get("ready") is not True:
    raise SystemExit(f"doctor not ready: {doctor}")
if doctor.get("version") != version:
    raise SystemExit(f"embedded version mismatch: {doctor.get('version')} != {version}")
if caps.get("capability_count", 0) < 40:
    raise SystemExit("capability registry unexpectedly small")
if skills.get("skill_count", 0) <= 0 or skills.get("embedded_count") != skills.get("skill_count"):
    raise SystemExit("embedded skill registry incomplete")
if not skill.get("content") or skill.get("skill_path") != "skills/target-codebase-topology-workflow.md":
    raise SystemExit("exact embedded topology skill unavailable")
if candidate_skill.get("known") is not True or candidate_skill.get("skill_path") != "skills/candidate-selection-provenance-workflow.md":
    raise SystemExit("exact embedded candidate-selection skill unavailable")
if "plw candidate select" not in str(candidate_skill.get("content") or ""):
    raise SystemExit("candidate-selection skill does not explain the exact command")

public_candidate = next((row for row in caps.get("capabilities", []) if row.get("command") == "candidate"), None)
if public_candidate is None:
    raise SystemExit("read-only candidate semantic capability missing from public discovery")
if public_candidate.get("state_change") is not False or public_candidate.get("skill_embedded") is not True:
    raise SystemExit("candidate semantic capability is not read-only with an embedded skill")

surface = orient.get("portable_agent_surface", {})
if surface.get("entrypoint") != "plw agent orient":
    raise SystemExit("portable agent orient contract missing")
authority = surface.get("authority", {})
if any(authority.get(key) for key in ("execute_runtime", "mutate_source", "mutate_external_repository", "commit_truth")):
    raise SystemExit("agent orient unexpectedly grants authority")

candidate_selection = candidate_orient.get("capability_selection", {}) or {}
if candidate_selection.get("task_text_used_for_selection") is not False:
    raise SystemExit("candidate handoff started routing on task keywords")
projected = next((row for row in candidate_selection.get("candidate_capabilities", []) if row.get("capability") == "candidate"), None)
if projected is None:
    raise SystemExit("agent orient did not project candidate identity discovery")
if projected.get("coverage") != "CONDITIONAL_DISCOVERY":
    raise SystemExit(f"candidate handoff coverage widened: {projected.get('coverage')}")
if projected.get("state_change") is not False:
    raise SystemExit("candidate handoff unexpectedly permits state change")
if projected.get("skill_path") != "skills/candidate-selection-provenance-workflow.md":
    raise SystemExit("candidate handoff points to the wrong embedded skill")
selection_authority = candidate_selection.get("authority", {}) or {}
if any(selection_authority.get(key) for key in ("chooses_agent_action", "executes_capability", "grants_state_change", "commit_truth")):
    raise SystemExit("candidate handoff unexpectedly grants action/execution authority")

if selection.get("candidate_selection", {}).get("resolution") != "RESOLVED":
    raise SystemExit("exact symbol task did not resolve one candidate")
if candidate_route.get("candidate_capability_match", {}).get("status") != "CAPABILITY_MATCHED":
    raise SystemExit("exact selected candidate did not match its internal capability")
route_authority = candidate_route["candidate_capability_match"].get("authority", {})
if any(route_authority.get(key) for key in ("authorization", "execution", "mutation", "correctness", "evidence_acceptance")):
    raise SystemExit("candidate capability match unexpectedly grants authority")
if ambiguous_route.get("candidate_selection", {}).get("resolution") != "AMBIGUOUS":
    raise SystemExit("underspecified candidate task did not remain ambiguous")
if ambiguous_route.get("candidate_capability_match", {}).get("status") != "CAPABILITY_NOT_MATCHED":
    raise SystemExit("ambiguous candidate selection reached internal capability match")
if "js_boolean_guard.strict_equality_string.temp_worktree.v1" in json.dumps(caps):
    raise SystemExit("internal mutation capability leaked into public capability discovery")

actual = sorted(str(p.relative_to(target)) for p in target.rglob("*") if p.is_file())
if actual != ["src/guards.js", "src/main.ts", "src/value.ts"]:
    raise SystemExit(f"target repository polluted: {actual}")

print(
    "PORTABLE_AGENT_SMOKE: PASS "
    f"version={version} capabilities={caps['capability_count']} "
    f"skills={skills['embedded_count']}/{skills['skill_count']} "
    "candidate_handoff=CONDITIONAL_DISCOVERY task_text_used=false "
    "candidate_selection=RESOLVED/AMBIGUOUS capability_match=read-only"
)
PY
