#!/usr/bin/env python3
"""Reference checks for read-only candidate-selection awareness in agent handoff."""
from __future__ import annotations

import json

from core.capability_selection import build_capability_selection
from core.portable_agent import list_capabilities, list_skills, read_skill
from core.semantic_affordance import describe_command


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> int:
    contract = describe_command("candidate")
    if contract.get("known") is not True:
        fail("candidate semantic contract is not registered")
    if contract.get("state_change") is not False:
        fail("candidate semantic contract unexpectedly permits state change")
    if contract.get("read_before_use") != "skills/candidate-selection-provenance-workflow.md":
        fail("candidate semantic contract points to the wrong embedded skill")
    required_limits = {
        "authorization",
        "mutation authority",
        "capability execution",
        "correctness",
        "evidence acceptance",
        "truth",
    }
    limits = set(contract.get("does_not_prove", []) or [])
    if not required_limits.issubset(limits):
        fail(f"candidate proof limits incomplete: missing {sorted(required_limits - limits)}")

    derivation = {
        "stage": "EVIDENCE_NEEDS_DERIVED",
        "selected_targets": ["src/guards.js"],
        "evidence_needed": [
            {
                "evidence_class": "semantic_scope",
                "need": "resolve the exact local simplification candidate before deciding whether more evidence is needed",
            }
        ],
    }
    selection = build_capability_selection(derivation)
    if selection.get("task_text_used_for_selection") is not False:
        fail("task text leaked into evidence-driven capability matching")
    candidates = selection.get("candidate_capabilities", []) or []
    row = next((x for x in candidates if x.get("capability") == "candidate"), None)
    if row is None:
        fail("candidate capability is not projected for semantic_scope")
    if row.get("coverage") != "CONDITIONAL_DISCOVERY":
        fail(f"candidate coverage widened unexpectedly: {row.get('coverage')}")
    if row.get("state_change") is not False:
        fail("candidate projection unexpectedly permits state change")
    if row.get("contract_known") is not True:
        fail("candidate projection lost semantic contract binding")
    if row.get("skill_path") != "skills/candidate-selection-provenance-workflow.md":
        fail("candidate projection points to the wrong skill")

    caps = list_capabilities()
    public = next((x for x in caps.get("capabilities", []) if x.get("command") == "candidate"), None)
    if public is None:
        fail("candidate is absent from public semantic capability discovery")
    if public.get("state_change") is not False or public.get("skill_embedded") is not True:
        fail("candidate public capability is not read-only with an embedded skill")
    if "js_boolean_guard.strict_equality_string.temp_worktree.v1" in json.dumps(caps, sort_keys=True):
        fail("internal bounded mutation capability leaked into public capability discovery")

    skills = list_skills()
    if skills.get("missing_referenced_skills"):
        fail(f"missing embedded skills: {skills['missing_referenced_skills']}")
    skill = read_skill("candidate")
    if skill.get("known") is not True:
        fail("candidate embedded skill is not readable by command alias")
    if skill.get("skill_path") != "skills/candidate-selection-provenance-workflow.md":
        fail("candidate embedded skill path mismatch")
    if "plw candidate select" not in str(skill.get("content") or ""):
        fail("candidate embedded skill does not explain the exact selection command")

    authority = selection.get("authority", {}) or {}
    forbidden = (
        "chooses_agent_action",
        "executes_capability",
        "grants_state_change",
        "semantic_ownership_proven",
        "behavioral_correctness_proven",
        "commit_truth",
    )
    if any(authority.get(key) for key in forbidden):
        fail(f"capability projection widened authority: {authority}")

    print(
        "CANDIDATE_SELECTION_AGENT_HANDOFF_REFERENCE: PASS "
        "candidate=read-only coverage=CONDITIONAL_DISCOVERY "
        "task_text_used=false internal_mutation_hidden=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
