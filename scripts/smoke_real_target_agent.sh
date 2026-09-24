#!/usr/bin/env bash
set -euo pipefail

BIN="$(realpath "${1:-artifacts/plw-linux-x86_64}")"
TARGET="$(realpath "${2:?pass a pinned vite checkout as the second argument}")"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/run" "$TMP/home" "$TMP/state" "$TMP/cache"
cp "$BIN" "$TMP/run/plw"

python - "$TMP/run/plw" "$TARGET" "$TMP" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

binary, target, temp = map(Path, sys.argv[1:])
revision = "1544bb1b7ac92f775e9d0dea97954c99cc6cbd43"
source_path = "packages/vite/src/node/ssr/ssrTransform.ts"
candidate_id = "sha256:d4d1da6c55c80079b4761ae51b1593c8b051e8c3ff276fb78fd6542ab2bfdef0"
task = f"Select isRefIdentifier in {source_path}"
env = {**os.environ, "HOME": str(temp / "home"), "XDG_STATE_HOME": str(temp / "state"),
       "XDG_CACHE_HOME": str(temp / "cache")}

def git(*args):
    proc = subprocess.run(["git", "-C", str(target), *args], text=True, capture_output=True, env=env)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()

assert git("rev-parse", "HEAD") == revision, "external target revision drift"
assert git("status", "--porcelain=v1", "--untracked-files=all") == "", "external target dirty before audit"
source_before = hashlib.sha256((target / source_path).read_bytes()).hexdigest()

def call(*args, input_text=None):
    proc = subprocess.run([str(binary), *map(str, args)], cwd=temp / "run", env=env,
                          input=input_text, text=True, capture_output=True, timeout=180)
    assert proc.returncode == 0 and not proc.stderr, (args, proc.returncode, proc.stderr[-600:])
    return json.loads(proc.stdout)

doctor = call("doctor", target, "--json")
assert doctor["ready"] is True and doctor["target_support"]["topology_ready"] is True
orient = call("agent", "orient", target, "--task", task, "--json")
assert orient["target_resolution"]["resolution"]["state"] == "RESOLVED"
assert source_path in orient["target_resolution"]["resolution"]["selected_targets"]
projection = next(x for x in orient["capability_selection"]["candidate_capabilities"]
                  if x["capability"] == "candidate")
assert projection["operation_contract_available"] is True and projection["operation_contract_count"] == 2

contract = call("capability", "describe", "candidate", "--json")
assert [x["operation_id"] for x in contract["operation_contracts"]] == [
    "candidate.select.v1", "candidate.capability-match.v1"]
skill = call("skill", "show", "candidate", "--json")
assert "plw candidate select" in skill["content"]

plan = call("operation-plan", "resolve", "-", "--json", input_text=json.dumps({
    "schema_version": "plw-operation-plan-v1",
    "capability": "candidate",
    "operation_id": "candidate.select.v1",
    "inputs": {"task": task, "root": str(target)},
}))
assert plan["status"] == "RESOLVED" and plan["resolved_operation_id"] == "candidate.select.v1"
assert plan["authority"]["invocation_authorized"] is False and plan["executes_operation"] is False
assert plan["compiled_argv"][0] == "plw"
selected = call(*plan["compiled_argv"][1:])
selection = selected["candidate_selection"]
assert selection["resolution"] == "RESOLVED" and selection["selected_candidate_id"] == candidate_id
assert selection["selected_source_path"] == source_path
assert selected["discovery_snapshot"]["target_revision"]["git_head"] == revision

matched = call("candidate", "capability-match", task, target, "--json")
route = matched["candidate_capability_match"]
assert matched["candidate_selection"]["selected_candidate_instance_id"] == selection["selected_candidate_instance_id"]
assert matched["discovery_snapshot"]["discovery_snapshot_digest"] == selected["discovery_snapshot"]["discovery_snapshot_digest"]
assert route["status"] == "CAPABILITY_MATCHED"
assert route["matched_capability_id"] == "js_boolean_guard.strict_equality_string.temp_worktree.v1"
assert all(route["authority"][key] is False for key in
           ("authorization", "execution", "mutation", "correctness", "evidence_acceptance"))
assert git("status", "--porcelain=v1", "--untracked-files=all") == "", "external target polluted"
assert hashlib.sha256((target / source_path).read_bytes()).hexdigest() == source_before

print("STANDALONE_REAL_TARGET_AGENT: PASS "
      f"repo=vitejs/vite commit={revision[:12]} candidate={candidate_id[:19]} "
      "doctor/orient/contract/skill/plan/invocation/match=same_snapshot target_clean=true")
PY
