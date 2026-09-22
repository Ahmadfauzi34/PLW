#!/usr/bin/env python3
"""Synthesize validated JS/TS local-rule evidence without granting rewrite authority."""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
PASS_KEYS = (
    "baseline_focused_test",
    "post_rewrite_focused_test",
    "typecheck_or_type_tests",
    "git_diff_check",
    "changed_path_scope",
)


def load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_record(record: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    eid = str(record.get("evidence_id", ""))
    if not eid:
        errors.append("missing evidence_id")
    if not DIGEST_RE.match(str(record.get("candidate_id", ""))):
        errors.append(f"{eid}: invalid candidate_id")
    if not DIGEST_RE.match(str(record.get("artifact_digest", ""))):
        errors.append(f"{eid}: invalid artifact_digest")
    if not re.fullmatch(r"[0-9a-f]{40}", str(record.get("revision", ""))):
        errors.append(f"{eid}: invalid revision")
    if not re.fullmatch(r"[0-9a-f]{40}", str(record.get("merged_commit", ""))):
        errors.append(f"{eid}: invalid merged_commit")

    validation = record.get("validation", {}) or {}
    for key in PASS_KEYS:
        value = validation.get(key)
        if key == "changed_path_scope":
            if value != "PASS_ONE_EXPECTED_FILE":
                errors.append(f"{eid}: {key}={value!r}")
        elif value != "PASS":
            errors.append(f"{eid}: {key}={value!r}")
    return errors


def synthesize(index: Dict[str, Any]) -> Dict[str, Any]:
    records = index.get("records", []) or []
    errors: List[str] = []

    evidence_ids = [str(r.get("evidence_id", "")) for r in records]
    candidate_ids = [str(r.get("candidate_id", "")) for r in records]
    if len(set(evidence_ids)) != len(evidence_ids):
        errors.append("duplicate evidence_id")
    if len(set(candidate_ids)) != len(candidate_ids):
        errors.append("duplicate candidate_id")

    by_rule: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in records:
        errors.extend(validate_record(record))
        by_rule[str(record.get("rule", ""))].append(record)

    rules: Dict[str, Dict[str, Any]] = {}
    proposal_review_ready = []

    for rule, rows in sorted(by_rule.items()):
        repositories = sorted({str(row["repository"]) for row in rows})
        revisions = sorted({str(row["revision"]) for row in rows})
        candidates = sorted({str(row["candidate_id"]) for row in rows})
        artifact_digests = sorted({str(row["artifact_digest"]) for row in rows})

        if len(repositories) >= 2 and len(candidates) >= 2:
            stage = "CROSS_REPOSITORY_EVIDENCE_READY"
            next_gate = "REUSABLE_REWRITE_PROPOSAL_REVIEW"
            proposal_review_ready.append(rule)
        else:
            stage = "SINGLE_REPOSITORY_EVIDENCE_READY"
            next_gate = "CROSS_REPOSITORY_REPLICATION"

        rules[rule] = {
            "stage": stage,
            "repository_count": len(repositories),
            "repositories": repositories,
            "revision_count": len(revisions),
            "candidate_count": len(candidates),
            "artifact_count": len(artifact_digests),
            "candidate_ids": candidates,
            "artifact_digests": artifact_digests,
            "next_gate": next_gate,
            "authority": {
                "reusable_rewrite_proposal_review_ready": stage == "CROSS_REPOSITORY_EVIDENCE_READY",
                "generic_rewrite_authority_granted": False,
                "automatic_patch_authority_granted": False,
                "upstream_mutation_authorized": False,
            },
        }

    return {
        "schema_version": "plw-js-ts-v2-local-rule-evidence-synthesis-v1",
        "status": "LOCAL_RULE_EVIDENCE_SYNTHESIS_READY" if not errors else "INVALID",
        "source_schema_version": index.get("schema_version"),
        "record_count": len(records),
        "rule_count": len(rules),
        "rules": rules,
        "proposal_review_ready_rules": proposal_review_ready,
        "authority": {
            "synthesis_is_evidence_routing_only": True,
            "proposal_review_ready_is_not_rewrite_authority": True,
            "generic_rewrite_authority_granted": False,
            "automatic_patch_authority_granted": False,
            "upstream_mutation_authorized": False,
            "truth_commit": False,
        },
        "errors": errors,
        "next_gate": "draft a bounded reusable-rewrite proposal only for cross-repository evidence-ready rules",
    }


def render_markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# JS/TS V2 local-rule evidence synthesis",
        "",
        f"Status: **{report['status']}**",
        "",
        f"Evidence records: **{report['record_count']}**",
        f"Rule families with mutation evidence: **{report['rule_count']}**",
        "",
        "## Rule state",
        "",
        "| Rule | Repositories | Candidates | Stage | Next gate |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for rule, row in report["rules"].items():
        lines.append(
            f"| {rule} | {row['repository_count']} | {row['candidate_count']} | "
            f"{row['stage']} | {row['next_gate']} |"
        )
    lines.extend(
        [
            "",
            "## Authority boundary",
            "",
            "cross-repository evidence ready != generic rewrite authority",
            "",
            "reusable rewrite proposal review != automatic patch authorization",
            "",
            "Only rules with independently validated candidates in at least two repositories",
            "are routed to reusable-rewrite proposal review.",
        ]
    )
    if report["errors"]:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in report["errors"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()

    report = synthesize(load(Path(args.index)))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    Path(args.summary).write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "record_count": report["record_count"],
                "rule_count": report["rule_count"],
                "proposal_review_ready_rules": report["proposal_review_ready_rules"],
                "errors": report["errors"],
            },
            sort_keys=True,
        )
    )
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
