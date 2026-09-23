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

cd "$TMP/run"
export HOME="$TMP/home"
export XDG_STATE_HOME="$TMP/state"
export XDG_CACHE_HOME="$TMP/cache"

./plw doctor "$TMP/target" --json > "$TMP/doctor.json"
./plw capability list --json > "$TMP/capabilities.json"
./plw skill list --json > "$TMP/skills.json"
./plw skill show topology --json > "$TMP/skill-topology.json"
./plw agent orient "$TMP/target" --task "understand how main uses value" --json > "$TMP/orient.json"

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
orient = json.loads((root / "orient.json").read_text())
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
surface = orient.get("portable_agent_surface", {})
if surface.get("entrypoint") != "plw agent orient":
    raise SystemExit("portable agent orient contract missing")
authority = surface.get("authority", {})
if any(authority.get(key) for key in ("execute_runtime", "mutate_source", "mutate_external_repository", "commit_truth")):
    raise SystemExit("agent orient unexpectedly grants authority")

actual = sorted(str(p.relative_to(target)) for p in target.rglob("*") if p.is_file())
if actual != ["src/main.ts", "src/value.ts"]:
    raise SystemExit(f"target repository polluted: {actual}")

print(
    "PORTABLE_AGENT_BINARY_SMOKE: PASS "
    f"version={version} capabilities={caps['capability_count']} "
    f"skills={skills['embedded_count']}/{skills['skill_count']}"
)
PY
