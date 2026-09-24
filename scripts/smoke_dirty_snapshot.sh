#!/usr/bin/env bash
set -euo pipefail

BIN="$(realpath "${1:-artifacts/plw-linux-x86_64}")"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

python - "$BIN" "$TMP" <<'PY'
import json
import os
from pathlib import Path
import subprocess
import sys

binary, temp = Path(sys.argv[1]), Path(sys.argv[2])
target = temp / "target"
(target / "src").mkdir(parents=True)
(target / "src/guards.js").write_text(
    "function isOne(node) {\n  if (node.type === 'one') {\n"
    "    return true;\n  }\n  return false;\n}\n"
)
readme = target / "README.md"
readme.write_text("initial\n")
env = {**os.environ, "HOME": str(temp / "home"), "XDG_STATE_HOME": str(temp / "state"),
       "XDG_CACHE_HOME": str(temp / "cache")}

def git(*args):
    proc = subprocess.run(["git", "-C", str(target), *args], text=True,
                          capture_output=True, env=env)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()

git("init", "-q")
git("add", ".")
git("-c", "user.name=Snapshot Probe", "-c", "user.email=probe@example.invalid",
    "commit", "-qm", "baseline")

def observe():
    proc = subprocess.run(
        [str(binary), "candidate", "select", "Select isOne in src/guards.js",
         str(target), "--json"], text=True, capture_output=True, env=env, cwd=temp,
    )
    assert proc.returncode == 0 and not proc.stderr, proc.stderr
    result = json.loads(proc.stdout)
    assert result["candidate_selection"]["resolution"] == "RESOLVED", result
    return result["discovery_snapshot"]

clean = observe()
assert clean["target_revision"]["working_tree_clean"] is True
assert clean["target_revision"]["dirty_content_complete"] is True
source_hash = clean["shared_graph_content_signature"]
candidate_hash = clean["candidate_set"]["candidate_set_digest"]

readme.write_text("dirty revision A\n")
first = observe()
readme.write_text("dirty revision B\n")
second = observe()
assert first["target_revision"]["working_tree_status_digest"] == second["target_revision"]["working_tree_status_digest"]
assert first["target_revision"]["dirty_content_digest"] != second["target_revision"]["dirty_content_digest"]
assert first["discovery_snapshot_digest"] != second["discovery_snapshot_digest"]
assert first["target_revision"]["dirty_content_complete"] is True
assert first["shared_graph_content_signature"] == second["shared_graph_content_signature"] == source_hash
assert first["candidate_set"]["candidate_set_digest"] == second["candidate_set"]["candidate_set_digest"] == candidate_hash

git("checkout", "--", "README.md")
untracked = target / "notes.txt"
untracked.write_text("one\n")
third = observe()
untracked.write_text("two\n")
fourth = observe()
assert third["target_revision"]["working_tree_status_digest"] == fourth["target_revision"]["working_tree_status_digest"]
assert third["discovery_snapshot_digest"] != fourth["discovery_snapshot_digest"]
untracked.unlink()

link = target / "doc-link"
link.symlink_to("README.md")
fifth = observe()
link.unlink()
link.symlink_to("missing-file")
sixth = observe()
assert fifth["target_revision"]["working_tree_status_digest"] == sixth["target_revision"]["working_tree_status_digest"]
assert fifth["discovery_snapshot_digest"] != sixth["discovery_snapshot_digest"]
link.unlink()

restored = observe()
assert clean["discovery_snapshot_digest"] == restored["discovery_snapshot_digest"]
assert git("status", "--porcelain=v1", "--untracked-files=all") == ""
print("STANDALONE_DIRTY_SNAPSHOT: PASS tracked/untracked/symlink bytes bound; clean restored")
PY
