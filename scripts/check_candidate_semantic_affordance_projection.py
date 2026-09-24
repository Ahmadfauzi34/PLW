#!/usr/bin/env python3
"""Reference check for bounded semantic affordance projection in agent orient."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="plw-candidate-affordance-") as td:
        tmp = Path(td)
        target = tmp / "target"
        (target / "src").mkdir(parents=True)
        (target / "src" / "guards.js").write_text(
            "function isReady(node) {\n"
            "  if (node.type === 'ready') {\n"
            "    return true;\n"
            "  }\n"
            "  return false;\n"
            "}\n",
            encoding="utf-8",
        )
        env = dict(__import__("os").environ)
        env.update({
            "HOME": str(tmp / "home"),
            "XDG_STATE_HOME": str(tmp / "state"),
            "XDG_CACHE_HOME": str(tmp / "cache"),
        })
        proc = subprocess.run(
            [sys.executable, str(ROOT / "plw_cli.py"), "agent", "orient", str(target), "--task", "Explain the exact simplification candidate in src/guards.js", "--json"],
            cwd=str(ROOT),
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            fail(f"agent orient failed: rc={proc.returncode} stderr={proc.stderr[:1200]}")
        payload = json.loads(proc.stdout)

    selection = payload.get("capability_selection", {}) or {}
    if selection.get("task_text_used_for_selection") is not False:
        fail("task text leaked into evidence-driven capability routing")
    rows = [x for x in selection.get("candidate_capabilities", []) or [] if isinstance(x, dict)]
    if not rows:
        fail("compact capability projection is empty")
    for row in rows:
        for field in ("canonical_concepts", "expected_information_gain", "does_not_prove"):
            value = row.get(field)
            if not isinstance(value, list):
                fail(f"{row.get('capability')} missing bounded {field}")
            if len(value) > 2:
                fail(f"{row.get('capability')} exceeds compact {field} budget: {len(value)}")
        if not isinstance(row.get("information_role"), str) or not row.get("information_role"):
            fail(f"{row.get('capability')} missing information_role")

    candidate = next((x for x in rows if x.get("capability") == "candidate"), None)
    if candidate is None:
        fail("candidate affordance is not projected")
    if candidate.get("coverage") != "CONDITIONAL_DISCOVERY":
        fail("candidate coverage changed")
    if candidate.get("state_change") is not False:
        fail("candidate affordance unexpectedly permits state change")
    if "candidate identity" not in candidate.get("canonical_concepts", []):
        fail(f"candidate canonical concepts lost technical identity: {candidate.get('canonical_concepts')}")
    if not candidate.get("expected_information_gain"):
        fail("candidate expected information gain is absent")
    if not candidate.get("does_not_prove"):
        fail("candidate proof limits are absent")

    frame = payload.get("agent_decision_frame", {}) or {}
    frame_rows = (((frame.get("capability_projection") or {}).get("candidates")) or [])
    frame_candidate = next((x for x in frame_rows if isinstance(x, dict) and x.get("capability") == "candidate"), None)
    if frame_candidate is None or not frame_candidate.get("information_role"):
        fail("agent decision frame does not carry candidate information role")
    if (frame.get("capability_projection") or {}).get("action_priority_computed") is not False:
        fail("semantic affordance projection computed action priority")
    if (frame.get("capability_projection") or {}).get("ranking_is_not_recommendation") is not True:
        fail("semantic affordance projection lost non-recommendation boundary")

    authority = selection.get("authority", {}) or {}
    forbidden = ("chooses_agent_action", "executes_capability", "grants_state_change", "commit_truth")
    if any(authority.get(k) for k in forbidden):
        fail(f"semantic affordance projection widened authority: {authority}")

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > 45000:
        fail(f"compact agent orient exceeded bounded context budget: {len(encoded.encode('utf-8'))}")

    print(
        "CANDIDATE_SEMANTIC_AFFORDANCE_PROJECTION: PASS "
        f"rows={len(rows)} candidate_concepts={len(candidate['canonical_concepts'])} "
        f"candidate_gain={len(candidate['expected_information_gain'])} bytes={len(encoded.encode('utf-8'))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
