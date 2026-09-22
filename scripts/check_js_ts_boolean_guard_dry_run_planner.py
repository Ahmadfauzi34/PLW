#!/usr/bin/env python3
"""Reference checks for the JS/TS boolean-guard dry-run planner."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from plan_js_ts_boolean_guard_rewrite import PlanningError, build_plan


def candidate(rel: str, line_end: int, *, inverse: bool, suffix: str) -> dict:
    return {
        "candidate_id": "sha256:" + suffix * 64,
        "kind": "js_boolean_guard_return",
        "files": [rel],
        "members": [
            {
                "file": rel,
                "name": "demo",
                "line_start": 1,
                "line_end": line_end,
            }
        ],
        "semantic_witness": {
            "type": "js_boolean_guard_return_v2",
            "same_function": True,
            "condition_evaluated_once_before_and_after": True,
            "true_false_terminals_opposite": True,
            "await_and_yield_condition_excluded": True,
            "inverse": inverse,
            "authority": "bounded_js_structural_boolean_return_witness_only",
        },
    }


def write_case(root: Path, rel: str, source: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8", newline="")
    return path


def expect_rejected(root: Path, rel: str, source: str, cand: dict, label: str) -> None:
    write_case(root, rel, source)
    try:
        build_plan(root, cand)
    except PlanningError:
        return
    raise AssertionError(f"{label}: expected PlanningError")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True)
    args = parser.parse_args()
    evidence_dir = Path(args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="plw-bool-plan-") as tmp:
        base = Path(tmp)
        root = base / "target"
        root.mkdir()

        prettier_rel = "prettier-style.js"
        prettier_source = """function demo(node) {
  if (node.type === "value-func") {
    return true;
  }

  return false;
}
"""
        prettier_path = write_case(root, prettier_rel, prettier_source)
        prettier_before = prettier_path.read_bytes()
        prettier_plan = build_plan(
            root,
            candidate(prettier_rel, 7, inverse=False, suffix="a"),
        )
        assert prettier_plan["status"] == "DRY_RUN_REWRITE_PLAN_READY"
        assert prettier_plan["match"]["transformation"] == "positive"
        assert prettier_plan["planned_rewrite"]["after"] == '  return node.type === "value-func";'
        assert prettier_plan["source_integrity"]["target_source_mutated"] is False
        assert prettier_plan["source_integrity"]["source_unchanged_verified"] is True
        assert prettier_path.read_bytes() == prettier_before

        (evidence_dir / "positive-plan.json").write_text(
            json.dumps(prettier_plan, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (evidence_dir / "positive.patch").write_text(
            prettier_plan["planned_rewrite"]["diff"],
            encoding="utf-8",
        )

        vite_rel = "vite-style.ts"
        vite_source = """function demo(id) {
  if (id.name === 'arguments') {
    return false
  }

  return true
}
"""
        vite_path = write_case(root, vite_rel, vite_source)
        vite_before = vite_path.read_bytes()
        vite_plan = build_plan(
            root,
            candidate(vite_rel, 7, inverse=True, suffix="b"),
        )
        assert vite_plan["status"] == "DRY_RUN_REWRITE_PLAN_READY"
        assert vite_plan["match"]["transformation"] == "inverse"
        assert vite_plan["planned_rewrite"]["after"] == "  return !(id.name === 'arguments')"
        assert vite_plan["match"]["semicolon_style"] == "no_semicolon"
        assert vite_path.read_bytes() == vite_before

        (evidence_dir / "inverse-plan.json").write_text(
            json.dumps(vite_plan, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (evidence_dir / "inverse.patch").write_text(
            vite_plan["planned_rewrite"]["diff"],
            encoding="utf-8",
        )

        logical = """function demo(left, right) {
  if (left && right) {
    return true;
  }

  return false;
}
"""
        expect_rejected(
            root,
            "logical.js",
            logical,
            candidate("logical.js", 7, inverse=False, suffix="c"),
            "logical-expression",
        )

        non_boolean = """function demo(value) {
  if (value) {
    return true;
  }

  return false;
}
"""
        expect_rejected(
            root,
            "non-boolean.js",
            non_boolean,
            candidate("non-boolean.js", 7, inverse=False, suffix="d"),
            "non-boolean-condition",
        )

        commented = """function demo(node) {
  if (node.type === "x") {
    // preserve this comment
    return true;
  }

  return false;
}
"""
        expect_rejected(
            root,
            "commented.js",
            commented,
            candidate("commented.js", 8, inverse=False, suffix="e"),
            "internal-comment",
        )

        awaited = """async function demo(ready) {
  if (await ready === true) {
    return true;
  }

  return false;
}
"""
        expect_rejected(
            root,
            "awaited.js",
            awaited,
            candidate("awaited.js", 7, inverse=False, suffix="f"),
            "await-condition",
        )

        mixed_semicolon = """function demo(node) {
  if (node.type === "x") {
    return true;
  }

  return false
}
"""
        expect_rejected(
            root,
            "mixed.js",
            mixed_semicolon,
            candidate("mixed.js", 7, inverse=False, suffix="1"),
            "mixed-semicolon",
        )

        polarity = write_case(
            root,
            "polarity.js",
            prettier_source,
        )
        del polarity
        try:
            build_plan(
                root,
                candidate("polarity.js", 7, inverse=True, suffix="2"),
            )
        except PlanningError:
            pass
        else:
            raise AssertionError("polarity-mismatch: expected PlanningError")

        multiple = """function demo(a, b, c, d) {
  if (a === b) {
    return true;
  }
  return false;

  if (c === d) {
    return true;
  }
  return false;
}
"""
        expect_rejected(
            root,
            "multiple.js",
            multiple,
            candidate("multiple.js", 10, inverse=False, suffix="3"),
            "multiple-matches",
        )

    summary = {
        "status": "BOOLEAN_GUARD_DRY_RUN_PLANNER_REFERENCE_PASSED",
        "positive_style": "PASS",
        "inverse_style": "PASS",
        "negative_cases": 7,
        "source_mutation": False,
        "generic_rewrite_authority_granted": False,
    }
    (evidence_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
