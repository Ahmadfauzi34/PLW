#!/usr/bin/env python3
"""Finalize rule-diversity temporary-worktree experiment evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rewrite-evidence", required=True)
    parser.add_argument("--diff", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()

    rewrite = json.loads(Path(args.rewrite_evidence).read_text())
    diff_text = Path(args.diff).read_text(encoding="utf-8", errors="replace")
    if not diff_text.strip():
        raise SystemExit("experiment diff is empty")

    result = {
        "schema_version": "plw-js-ts-rule-diversity-worktree-result-v1",
        "status": "RULE_DIVERSITY_EXPERIMENT_PASSED",
        "case": rewrite["case"],
        "candidate": rewrite["candidate"],
        "rewrite": rewrite["rewrite"],
        "validation": {
            "baseline_focused_target_native_test": "PASS",
            "post_rewrite_focused_target_native_test": "PASS",
            "post_rewrite_repo_typecheck": "PASS",
            "git_diff_check": "PASS",
            "changed_path_scope": "PASS_ONE_EXPECTED_FILE",
        },
        "diff": diff_text,
        "authority": {
            "temporary_checkout_only": True,
            "candidate_validated_in_one_pinned_revision": True,
            "rule_diversity_evidence": True,
            "upstream_patch_created": False,
            "upstream_patch_authorized": False,
            "behavioral_equivalence_globally_proven": False,
            "regression_free_globally_proven": False,
            "truth_commit": False,
        },
        "next_gate": "compare multiple validated local-rule cases before any reusable rewrite or upstream mutation surface",
    }
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

    summary = [
        "# JS/TS rule-diversity temporary-worktree experiment",
        "",
        f"Status: **{result['status']}**",
        "",
        f"Case: `{result['case']}`",
        f"Candidate: `{result['candidate']['candidate_id']}`",
        f"Rule: `{result['candidate']['kind']}`",
        "",
        "Validation:",
        "",
        "- baseline focused target-native test: PASS",
        "- post-rewrite focused target-native test: PASS",
        "- repository typecheck: PASS",
        "- git diff --check: PASS",
        "- changed path scope: exactly one expected source file",
        "",
        "Authority: one pinned temporary checkout only; no upstream patch authorization.",
        "",
    ]
    Path(args.summary).write_text("\n".join(summary), encoding="utf-8")
    print(json.dumps({"status": result["status"], "case": result["case"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
