#!/usr/bin/env python3
"""Review sealed accepted mutation evidence without granting mutation authority.

Historical pre-seal experiments may be supplied as context, but they never count
toward sealed accepted evidence thresholds.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Mapping

ACCEPTANCE_SCHEMA = "plw-js-ts-v2-experiment-evidence-acceptance-v1"
HISTORICAL_SCHEMA = "plw-js-ts-v2-local-rule-evidence-index-v1"
EVIDENCE_CLASS = "BOUNDED_POSTCONDITION_VALIDATION_EVIDENCE"
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

FALSE_AUTHORITY_FIELDS = (
    "source_mutation_allowed",
    "automatic_patch_authority_granted",
    "generic_mutation_authority_granted",
    "upstream_mutation_authorized",
    "global_behavioral_equivalence_proven",
    "truth_commit",
)


class SynthesisError(ValueError):
    pass


def _digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical_record_digest(record: Mapping[str, Any]) -> str:
    payload = dict(record)
    payload.pop("record_digest", None)
    data = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return _digest_bytes(data)


def _read_acceptance_ledger(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    records: List[Dict[str, Any]] = []
    previous = None
    for expected_sequence, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        1,
    ):
        if not raw.strip():
            continue
        record = json.loads(raw)
        if record.get("schema_version") != ACCEPTANCE_SCHEMA:
            raise SynthesisError("acceptance ledger schema mismatch")
        if record.get("sequence") != expected_sequence:
            raise SynthesisError("acceptance ledger sequence mismatch")
        if record.get("previous_record_digest") != previous:
            raise SynthesisError("acceptance ledger previous digest mismatch")
        if record.get("record_digest") != _canonical_record_digest(record):
            raise SynthesisError("acceptance ledger record digest mismatch")
        previous = record["record_digest"]
        records.append(record)
    return records


def _load_historical(path: Path | None) -> Dict[str, Any]:
    if path is None or not path.exists():
        return {
            "schema_version": HISTORICAL_SCHEMA,
            "records": [],
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != HISTORICAL_SCHEMA:
        raise SynthesisError("historical evidence index schema mismatch")
    return payload


def _require_digest(value: Any, label: str) -> None:
    if not isinstance(value, str) or not DIGEST_RE.fullmatch(value):
        raise SynthesisError(f"{label} must be a sha256 digest")


def _validate_acceptance_record(record: Mapping[str, Any]) -> None:
    if record.get("status") != "EXPERIMENT_EVIDENCE_ACCEPTED":
        raise SynthesisError("acceptance record status mismatch")
    if record.get("evidence_class") != EVIDENCE_CLASS:
        raise SynthesisError("acceptance record evidence class mismatch")

    rule = record.get("rule")
    candidate_id = record.get("candidate_id")
    target = record.get("target", {}) or {}

    if not isinstance(rule, str) or not rule:
        raise SynthesisError("acceptance record rule missing")
    if not isinstance(candidate_id, str) or not candidate_id:
        raise SynthesisError("acceptance record candidate id missing")
    for key in ("repository", "revision", "source_path"):
        if not isinstance(target.get(key), str) or not target.get(key):
            raise SynthesisError(f"acceptance target missing {key}")

    _require_digest(
        record.get("validation_receipt_digest"),
        "validation receipt digest",
    )
    _require_digest(
        record.get("issuance_record_digest"),
        "issuance record digest",
    )

    lineage = record.get("lineage", {}) or {}
    required_lineage = (
        "plan_digest",
        "preflight_evidence_digest",
        "authorization_receipt_digest",
        "postcondition_validation_spec_digest",
        "mutation_receipt_digest",
    )
    for key in required_lineage:
        _require_digest(lineage.get(key), f"lineage {key}")

    summary = record.get("validation_summary", {}) or {}
    for key in (
        "all_required_postconditions_passed",
        "worktree_disposed",
        "authorization_consumed",
    ):
        if summary.get(key) is not True:
            raise SynthesisError(f"acceptance summary requires {key}=true")

    authority = record.get("authority", {}) or {}
    if authority.get("evidence_acceptance_only") is not True:
        raise SynthesisError("acceptance record must be evidence-only")
    for key in FALSE_AUTHORITY_FIELDS:
        if authority.get(key) is not False:
            raise SynthesisError(
                f"acceptance record unexpectedly grants {key}"
            )


def _stage_rule(rows: List[Mapping[str, Any]]) -> Dict[str, Any]:
    repositories = sorted(
        {str((row.get("target", {}) or {}).get("repository")) for row in rows}
    )
    candidates = sorted({str(row.get("candidate_id")) for row in rows})
    revisions = sorted(
        {str((row.get("target", {}) or {}).get("revision")) for row in rows}
    )

    if not rows:
        stage = "INSUFFICIENT_SEALED_ACCEPTED_EVIDENCE"
        reason = "NO_ACCEPTED_RECORDS"
        next_gate = "COLLECT_SEALED_ACCEPTED_EXPERIMENTS"
    elif len(repositories) < 2:
        stage = "INSUFFICIENT_SEALED_ACCEPTED_EVIDENCE"
        reason = "CROSS_REPOSITORY_ACCEPTED_EVIDENCE_REQUIRED"
        next_gate = "COLLECT_CROSS_REPOSITORY_SEALED_ACCEPTED_EXPERIMENTS"
    elif len(candidates) < 2:
        stage = "INSUFFICIENT_SEALED_ACCEPTED_EVIDENCE"
        reason = "INDEPENDENT_CANDIDATES_REQUIRED"
        next_gate = "COLLECT_INDEPENDENT_SEALED_ACCEPTED_EXPERIMENTS"
    else:
        stage = "CROSS_REPOSITORY_SEALED_ACCEPTED_EVIDENCE_READY"
        reason = None
        next_gate = "BOUNDED_MUTATION_CAPABILITY_PROMOTION_REVIEW"

    return {
        "stage": stage,
        "reason": reason,
        "accepted_record_count": len(rows),
        "repository_count": len(repositories),
        "repositories": repositories,
        "revision_count": len(revisions),
        "revisions": revisions,
        "candidate_count": len(candidates),
        "candidate_ids": candidates,
        "promotion_review_ready": (
            stage == "CROSS_REPOSITORY_SEALED_ACCEPTED_EVIDENCE_READY"
        ),
        "next_gate": next_gate,
        "authority": {
            "mutation_capability_granted": False,
            "automatic_patch_authority_granted": False,
            "generic_mutation_authority_granted": False,
            "upstream_mutation_authorized": False,
            "truth_commit": False,
        },
    }


def synthesize(
    acceptance_records: List[Dict[str, Any]],
    historical: Dict[str, Any],
) -> Dict[str, Any]:
    validation_receipts: List[str] = []
    acceptance_record_digests: List[str] = []

    by_rule: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in acceptance_records:
        _validate_acceptance_record(record)

        validation_digest = str(record["validation_receipt_digest"])
        record_digest = str(record["record_digest"])
        if validation_digest in validation_receipts:
            raise SynthesisError("duplicate validation receipt acceptance")
        if record_digest in acceptance_record_digests:
            raise SynthesisError("duplicate acceptance record digest")

        validation_receipts.append(validation_digest)
        acceptance_record_digests.append(record_digest)
        by_rule[str(record["rule"])].append(record)

    historical_rows = historical.get("records", []) or []
    historical_by_rule: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in historical_rows:
        rule = str(row.get("rule", ""))
        if rule:
            historical_by_rule[rule].append(row)

    all_rules = sorted(set(by_rule) | set(historical_by_rule))
    rules: Dict[str, Dict[str, Any]] = {}

    for rule in all_rules:
        accepted = by_rule.get(rule, [])
        historical_rule_rows = historical_by_rule.get(rule, [])
        row = _stage_rule(accepted)
        row["historical_context"] = {
            "record_count": len(historical_rule_rows),
            "repositories": sorted(
                {
                    str(item.get("repository"))
                    for item in historical_rule_rows
                    if item.get("repository")
                }
            ),
            "counts_toward_sealed_acceptance": False,
        }
        rules[rule] = row

    promotion_ready_rules = sorted(
        rule
        for rule, row in rules.items()
        if row["promotion_review_ready"]
    )

    return {
        "schema_version": (
            "plw-js-ts-v2-bounded-mutation-evidence-synthesis-review-v1"
        ),
        "status": "BOUNDED_MUTATION_EVIDENCE_SYNTHESIS_REVIEWED",
        "acceptance_ledger_record_count": len(acceptance_records),
        "acceptance_ledger_present": bool(acceptance_records),
        "historical_context_record_count": len(historical_rows),
        "historical_context_counts_toward_acceptance": False,
        "rule_count": len(rules),
        "rules": rules,
        "promotion_review_ready_rules": promotion_ready_rules,
        "authority": {
            "review_only": True,
            "historical_evidence_cannot_be_retroactively_accepted": True,
            "mutation_capability_granted": False,
            "automatic_patch_authority_granted": False,
            "generic_mutation_authority_granted": False,
            "upstream_mutation_authorized": False,
            "truth_commit": False,
        },
        "next_gate": (
            "BOUNDED_MUTATION_CAPABILITY_PROMOTION_REVIEW"
            if promotion_ready_rules
            else "COLLECT_SEALED_ACCEPTED_EXPERIMENTS"
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# JS/TS bounded mutation evidence synthesis review",
        "",
        f"Status: **{report['status']}**",
        "",
        (
            "Sealed accepted records: "
            f"**{report['acceptance_ledger_record_count']}**"
        ),
        (
            "Historical context records: "
            f"**{report['historical_context_record_count']}**"
        ),
        "",
        "Historical context never counts toward sealed acceptance thresholds.",
        "",
        "## Rule state",
        "",
        (
            "| Rule | Accepted | Repositories | Historical | Stage | "
            "Promotion review |"
        ),
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]

    for rule, row in report["rules"].items():
        lines.append(
            f"| {rule} | {row['accepted_record_count']} | "
            f"{row['repository_count']} | "
            f"{row['historical_context']['record_count']} | "
            f"{row['stage']} | "
            f"{'READY' if row['promotion_review_ready'] else 'NO'} |"
        )

    lines.extend(
        [
            "",
            "## Authority boundary",
            "",
            (
                "historical experiment PASS != sealed "
                "EXPERIMENT_EVIDENCE_ACCEPTED"
            ),
            "",
            (
                "CROSS_REPOSITORY_SEALED_ACCEPTED_EVIDENCE_READY "
                "!= mutation capability granted"
            ),
            "",
            "Next gate: " + str(report["next_gate"]),
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--acceptance-ledger", required=True)
    parser.add_argument("--historical-index")
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()

    try:
        acceptance = _read_acceptance_ledger(
            Path(args.acceptance_ledger).resolve()
        )
        historical = _load_historical(
            Path(args.historical_index).resolve()
            if args.historical_index
            else None
        )
        report = synthesize(acceptance, historical)
    except (SynthesisError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "status": "BOUNDED_MUTATION_EVIDENCE_SYNTHESIS_REJECTED",
                    "error": str(exc),
                },
                sort_keys=True,
            )
        )
        return 2

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    Path(args.summary).write_text(
        render_markdown(report),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "accepted_records": report[
                    "acceptance_ledger_record_count"
                ],
                "promotion_review_ready_rules": report[
                    "promotion_review_ready_rules"
                ],
                "next_gate": report["next_gate"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
