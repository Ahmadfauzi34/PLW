#!/usr/bin/env bash
set -euo pipefail

BIN="${1:-artifacts/plw-linux-x86_64}"
BIN="$(realpath "$BIN")"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/js" "$TMP/python" "$TMP/run"
printf 'export const value = 1;\n' > "$TMP/js/main.ts"
printf 'print(1)\n' > "$TMP/python/main.py"

export HOME="$TMP/home" XDG_STATE_HOME="$TMP/state" XDG_CACHE_HOME="$TMP/cache"
cd "$TMP/run"

"$BIN" --version > "$TMP/version.txt"
"$BIN" version --json > "$TMP/version.json"
"$BIN" doctor "$TMP/js" --json > "$TMP/doctor-js.json"
"$BIN" doctor "$TMP/python" --json > "$TMP/doctor-py.json"
"$BIN" work 'Find value export' "$TMP/js" --json > "$TMP/work.json"

python - "$TMP" "$ROOT/VERSION" "$BIN" <<'PY'
import json
import os
from pathlib import Path
import subprocess
import sys

root, version_path, binary = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
version = version_path.read_text().strip()
read = lambda name: json.loads((root / name).read_text())
assert (root / "version.txt").read_text().strip() == f"plw {version}"
assert read("version.json") == {"schema_version": "plw-version-v1", "version": version}
bad = subprocess.run([binary, "version", "--not-a-flag"], text=True,
                     capture_output=True, env=os.environ, cwd=root / "run")
assert bad.returncode == 2 and "accepts only --json" in bad.stderr, bad

js = read("doctor-js.json")
py = read("doctor-py.json")
for doctor in (js, py):
    assert doctor["version"] == version and doctor["ready"] is True, doctor
    assert doctor["readiness"]["portable_surface_ready"] is True, doctor
    assert doctor["readiness"]["action_readiness"] == "NOT_ASSESSED", doctor
assert js["readiness"]["stable_target_topology_ready"] is True, js
assert py["readiness"]["stable_target_topology_ready"] is False, py
assert py["readiness"]["stable_target_topology_reason"] == "NO_STABLE_TOPOLOGY_SOURCE_FILES", py
assert py["target_support"]["authority"]["experimental_python_promoted"] is False, py

work = read("work.json")
assert work["work_status"] == "ready", work
assert work["work_status_scope"] == "reference_pack_status_only", work
assert work["readiness"]["reference_pack"] == "READY", work
assert work["readiness"]["action"] == work["agent_decision_frame"]["action_readiness"], work
assert work["readiness"]["action"] == "NOT_READY", work
assert work["readiness"]["task_postcondition"] == "UNPROVEN", work
assert work["authority"]["mutate_source"] is False, work
assert sorted(p.name for p in (root / "js").iterdir()) == ["main.ts"]
assert sorted(p.name for p in (root / "python").iterdir()) == ["main.py"]
print("READINESS_VERSION_SMOKE: PASS version=embedded doctor=scope-separated work=not-action-ready target=clean")
PY
