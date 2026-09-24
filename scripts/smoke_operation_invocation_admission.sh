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
mkdir -p "$TMP/cwd/target" "$TMP/evidence"
printf 'sentinel\n' > "$TMP/cwd/target/UNCHANGED.txt"

cat > "$TMP/plan.json" <<'EOF'
{
  "schema_version": "plw-operation-plan-v1",
  "capability": "candidate",
  "operation_id": "candidate.select.v1",
  "inputs": {
    "task": "Select isOne in src/guards.js",
    "root": "target"
  }
}
EOF

cat > "$TMP/ambiguous-plan.json" <<'EOF'
{
  "schema_version": "plw-operation-plan-v1",
  "capability": "candidate",
  "inputs": {
    "task": "Select isOne in src/guards.js",
    "root": "target"
  }
}
EOF

HOME="$TMP/home" XDG_STATE_HOME="$TMP/state" XDG_CACHE_HOME="$TMP/cache" \
  "$BIN" operation-plan resolve "$TMP/plan.json" --json > "$TMP/resolution.json"
HOME="$TMP/home" XDG_STATE_HOME="$TMP/state" XDG_CACHE_HOME="$TMP/cache" \
  "$BIN" operation-plan resolve "$TMP/ambiguous-plan.json" --json > "$TMP/ambiguous-resolution.json"

python - "$TMP" <<'PY'
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
cwd = (root / "cwd").resolve()
resolution = json.loads((root / "resolution.json").read_text())
assert resolution["status"] == "RESOLVED", resolution


def digest(value):
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


authorization = {
    "schema_version": "plw-operation-invocation-authorization-v1",
    "status": "INVOCATION_AUTHORIZED",
    "authorized": True,
    "authorization_scope": "ONE_RESOLVED_PLAN_ONE_OPERATION_ONE_ARGV",
    "single_use": True,
    "issuer": {
        "kind": "STANDALONE_BINARY_SMOKE",
        "external_to_planner": True,
        "planner_self_authorized": False,
    },
    "binding": {
        "operation_plan_digest": resolution["plan_digest"],
        "operation_resolution_digest": digest(resolution),
        "operation_id": resolution["resolved_operation_id"],
        "operation_contract_digest": resolution["operation_contract_digest"],
        "compiled_argv_digest": digest(resolution["compiled_argv"]),
        "invocation_cwd": str(cwd),
        "invocation_cwd_digest": digest({"invocation_cwd": str(cwd)}),
    },
    "authority": {
        "invocation_only": True,
        "mutation_authorized": False,
        "correctness_proven": False,
        "evidence_acceptance_granted": False,
        "truth_committed": False,
    },
}
(root / "authorization.json").write_text(
    json.dumps(authorization, indent=2, sort_keys=True) + "\n"
)

tampered = dict(resolution)
tampered["compiled_argv"] = ["plw", "doctor"]
(root / "tampered-resolution.json").write_text(
    json.dumps(tampered, indent=2, sort_keys=True) + "\n"
)
PY

if HOME="$TMP/home" XDG_STATE_HOME="$TMP/state" XDG_CACHE_HOME="$TMP/cache" \
  "$BIN" operation-invocation admit \
    "$TMP/plan.json" "$TMP/resolution.json" "$TMP/authorization.json" \
    --cwd "$TMP/cwd" \
    --consumption-ledger "$TMP/evidence/no-ack.jsonl" \
    --json > "$TMP/no-ack.json"; then
  echo "operation invocation admission unexpectedly accepted missing state-change acknowledgement" >&2
  exit 1
fi
[[ ! -e "$TMP/evidence/no-ack.jsonl" ]]

HOME="$TMP/home" XDG_STATE_HOME="$TMP/state" XDG_CACHE_HOME="$TMP/cache" \
  "$BIN" operation-invocation admit \
    "$TMP/plan.json" "$TMP/resolution.json" "$TMP/authorization.json" \
    --cwd "$TMP/cwd" \
    --consumption-ledger "$TMP/evidence/consume.jsonl" \
    --allow-state-change --json > "$TMP/admitted.json"

HOME="$TMP/home" XDG_STATE_HOME="$TMP/state" XDG_CACHE_HOME="$TMP/cache" \
  "$BIN" operation-invocation admit \
    "$TMP/plan.json" "$TMP/resolution.json" "$TMP/authorization.json" \
    --cwd "$TMP/cwd" \
    --consumption-ledger "$TMP/evidence/consume.jsonl" \
    --allow-state-change --json > "$TMP/replay.json"

HOME="$TMP/home" XDG_STATE_HOME="$TMP/state" XDG_CACHE_HOME="$TMP/cache" \
  "$BIN" operation-invocation admit \
    "$TMP/plan.json" "$TMP/tampered-resolution.json" "$TMP/authorization.json" \
    --cwd "$TMP/cwd" \
    --consumption-ledger "$TMP/evidence/tamper.jsonl" \
    --allow-state-change --json > "$TMP/tamper.json"

HOME="$TMP/home" XDG_STATE_HOME="$TMP/state" XDG_CACHE_HOME="$TMP/cache" \
  "$BIN" operation-invocation admit \
    "$TMP/ambiguous-plan.json" "$TMP/ambiguous-resolution.json" "$TMP/authorization.json" \
    --cwd "$TMP/cwd" \
    --consumption-ledger "$TMP/evidence/ambiguous.jsonl" \
    --allow-state-change --json > "$TMP/ambiguous.json"

HOME="$TMP/home" XDG_STATE_HOME="$TMP/state" XDG_CACHE_HOME="$TMP/cache" \
  "$BIN" operation-invocation admit \
    "$TMP/plan.json" "$TMP/resolution.json" "$TMP/authorization.json" \
    --cwd "$TMP/cwd" \
    --consumption-ledger "$TMP/cwd/target/inside.jsonl" \
    --allow-state-change --json > "$TMP/inside.json"

python - "$TMP" <<'PY'
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
admitted = json.loads((root / "admitted.json").read_text())
replay = json.loads((root / "replay.json").read_text())
tamper = json.loads((root / "tamper.json").read_text())
ambiguous = json.loads((root / "ambiguous.json").read_text())
inside = json.loads((root / "inside.json").read_text())
no_ack = json.loads((root / "no-ack.json").read_text())

assert no_ack["error"] == "STATE_CHANGE_ACKNOWLEDGEMENT_REQUIRED", no_ack
assert admitted["status"] == "ADMITTED", admitted
assert admitted["reason"] == "EXACT_RESOLVED_OPERATION_INVOCATION_ADMITTED", admitted
assert admitted["operation_id"] == "candidate.select.v1", admitted
assert admitted["runtime_identity_required"] is True, admitted
assert admitted["next_gate"] == "BIND_RUNTIME_AND_EXECUTE_EXACT_ADMITTED_INVOCATION", admitted
authority = admitted["authority"]
assert authority["invocation_authorized"] is True, authority
assert authority["executes_operation"] is False, authority
assert authority["mutation_authorized"] is False, authority
assert authority["correctness_proven"] is False, authority
assert authority["evidence_acceptance_granted"] is False, authority
assert authority["truth_committed"] is False, authority

assert replay["status"] == "REJECTED", replay
assert replay["reason"] == "INVOCATION_AUTHORIZATION_ALREADY_CONSUMED", replay
assert tamper["status"] == "REJECTED", tamper
assert tamper["reason"] == "SUPPLIED_RESOLUTION_RECOMPUTATION_MISMATCH", tamper
assert ambiguous["status"] == "UNRESOLVED", ambiguous
assert ambiguous["reason"] == "OPERATION_PLAN_NOT_RESOLVED", ambiguous
assert ambiguous["plan_status"] == "AMBIGUOUS", ambiguous
assert inside["status"] == "REJECTED", inside
assert inside["reason"] == "CONSUMPTION_LEDGER_MUST_BE_OUTSIDE_TARGET_ROOT", inside

ledger_rows = [
    json.loads(line)
    for line in (root / "evidence" / "consume.jsonl").read_text().splitlines()
    if line.strip()
]
assert len(ledger_rows) == 1, ledger_rows
assert ledger_rows[0]["status"] == "CONSUMED_FOR_INVOCATION_ADMISSION", ledger_rows
assert not (root / "evidence" / "tamper.jsonl").exists()
assert not (root / "evidence" / "ambiguous.jsonl").exists()
assert not (root / "cwd" / "target" / "inside.jsonl").exists()
assert (root / "cwd" / "target" / "UNCHANGED.txt").read_text() == "sentinel\n"
assert sorted(path.name for path in (root / "cwd" / "target").iterdir()) == ["UNCHANGED.txt"]
for forbidden in ("data/runtime", "data/codebase/cache"):
    assert not (root / "cwd" / "target" / forbidden).exists(), forbidden

print(
    "STANDALONE_OPERATION_INVOCATION_ADMISSION_SMOKE: PASS "
    "admitted_once=true replay_rejected=true executes=false mutation_authority=false "
    "runtime_identity_required=true target_unchanged=true"
)
PY
