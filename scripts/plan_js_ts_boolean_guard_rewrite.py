#!/usr/bin/env python3
"""Build a fail-closed dry-run plan for one JS/TS boolean-guard candidate.

The planner reads target source and writes evidence outside the target root. It
never mutates target source and grants no patch authority.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Tuple

RULE = "js_boolean_guard_return"
WITNESS_TYPE = "js_boolean_guard_return_v2"

IDENT = r"[A-Za-z_$][A-Za-z0-9_$]*(?:\??\.[A-Za-z_$][A-Za-z0-9_$]*)*"
STRING = r"(?:'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\")"
NUMBER = r"(?:-?(?:\d+(?:\.\d*)?|\.\d+))"
ATOM = rf"(?:{IDENT}|{STRING}|{NUMBER}|true|false|null|undefined)"
BINARY_BOOL_RE = re.compile(
    rf"^\s*{ATOM}\s*(?:===|!==|==|!=|<=|>=|<|>|\bin\b|\binstanceof\b)\s*{ATOM}\s*$"
)
UNARY_BOOL_RE = re.compile(rf"^\s*!\s*{ATOM}\s*$")

TERMINAL_PAIR_RE = re.compile(
    r"(?m)"
    r"^(?P<indent>[ \t]*)if[ \t]*\((?P<cond>[^\r\n()]*)\)[ \t]*\{[ \t]*(?P<nl>\r?\n)"
    r"(?P<bodyindent>[ \t]+)return[ \t]+(?P<first>true|false)(?P<semi1>;?)[ \t]*(?P=nl)"
    r"(?P=indent)\}[ \t]*(?P=nl)"
    r"(?:[ \t]*(?:\r?\n))*"
    r"(?P=indent)return[ \t]+(?P<second>true|false)(?P<semi2>;?)[ \t]*(?=(?:\r?\n|$))"
)


class PlanningError(ValueError):
    pass


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _safe_file(root: Path, rel: str) -> Path:
    path = (root / rel).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise PlanningError(f"source path escapes target root: {rel}") from exc
    if not path.is_file():
        raise PlanningError(f"source file missing: {rel}")
    return path


def _require_evidence_output_outside_target(root: Path, path: Path) -> None:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return
    raise PlanningError("planner evidence output must be outside target root")


def _validate_candidate(candidate: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    if candidate.get("kind") != RULE:
        raise PlanningError(f"candidate kind must be {RULE}")

    members = candidate.get("members", []) or []
    files = candidate.get("files", []) or []
    if len(members) != 1:
        raise PlanningError("planner requires exactly one candidate member")
    if len(files) != 1:
        raise PlanningError("planner requires exactly one candidate file")
    member = members[0]
    if str(member.get("file", "")) != str(files[0]):
        raise PlanningError("candidate member/file mismatch")

    witness = candidate.get("semantic_witness", {}) or {}
    if witness.get("type") != WITNESS_TYPE:
        raise PlanningError("unexpected semantic witness type")
    required_true = (
        "same_function",
        "condition_evaluated_once_before_and_after",
        "true_false_terminals_opposite",
        "await_and_yield_condition_excluded",
    )
    for key in required_true:
        if witness.get(key) is not True:
            raise PlanningError(f"semantic witness {key} must be true")
    if not isinstance(witness.get("inverse"), bool):
        raise PlanningError("semantic witness inverse must be boolean")

    line_start = int(member.get("line_start", 0) or 0)
    line_end = int(member.get("line_end", 0) or 0)
    if line_start < 1 or line_end < line_start:
        raise PlanningError("invalid candidate member line span")

    return member, bool(witness["inverse"])


def _boolean_condition_proven(condition: str) -> bool:
    if re.search(r"\b(?:await|yield)\b", condition):
        return False
    if any(token in condition for token in ("&&", "||", "??", "/*", "//")):
        return False
    return bool(BINARY_BOOL_RE.fullmatch(condition) or UNARY_BOOL_RE.fullmatch(condition))


def _segment_for_member(source: str, member: Dict[str, Any]) -> Tuple[str, int]:
    lines = source.splitlines(keepends=True)
    start = int(member["line_start"]) - 1
    end = int(member["line_end"])
    if end > len(lines):
        raise PlanningError("candidate member line span exceeds source length")
    prefix = "".join(lines[:start])
    segment = "".join(lines[start:end])
    return segment, len(prefix)


def build_plan(target_root: Path, candidate: Dict[str, Any]) -> Dict[str, Any]:
    root = target_root.resolve()
    member, witness_inverse = _validate_candidate(candidate)
    rel = str(member["file"])
    source_path = _safe_file(root, rel)

    before_bytes = source_path.read_bytes()
    try:
        source = before_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PlanningError("source must be valid UTF-8") from exc

    segment, segment_offset = _segment_for_member(source, member)
    matches = list(TERMINAL_PAIR_RE.finditer(segment))
    if len(matches) != 1:
        raise PlanningError(
            f"expected exactly one bounded boolean terminal pair in member span, found {len(matches)}"
        )

    match = matches[0]
    matched_text = match.group(0)
    if "/*" in matched_text or "//" in matched_text:
        raise PlanningError("comments inside rewrite span are not allowed")

    condition = match.group("cond").strip()
    if not _boolean_condition_proven(condition):
        raise PlanningError("condition is not proven boolean by the bounded syntax allowlist")

    first = match.group("first")
    second = match.group("second")
    if first == second:
        raise PlanningError("terminal boolean returns must be opposite")

    detected_inverse = first == "false" and second == "true"
    detected_positive = first == "true" and second == "false"
    if not (detected_inverse or detected_positive):
        raise PlanningError("unsupported boolean terminal polarity")
    if detected_inverse != witness_inverse:
        raise PlanningError("semantic witness polarity does not match source")

    semi1 = match.group("semi1")
    semi2 = match.group("semi2")
    if semi1 != semi2:
        raise PlanningError("mixed semicolon style inside rewrite span is rejected")
    semicolon = semi1
    indent = match.group("indent")

    if detected_inverse:
        replacement = f"{indent}return !({condition}){semicolon}"
        transformation = "inverse"
    else:
        replacement = f"{indent}return {condition}{semicolon}"
        transformation = "positive"

    absolute_start = segment_offset + match.start()
    absolute_end = segment_offset + match.end()
    planned_source = source[:absolute_start] + replacement + source[absolute_end:]
    planned_bytes = planned_source.encode("utf-8")

    diff_text = "".join(
        difflib.unified_diff(
            source.splitlines(keepends=True),
            planned_source.splitlines(keepends=True),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
        )
    )
    if not diff_text.strip():
        raise PlanningError("dry-run plan produced no diff")

    after_read = source_path.read_bytes()
    if after_read != before_bytes:
        raise PlanningError("target source changed during dry-run planning")

    return {
        "schema_version": "plw-js-ts-v2-boolean-guard-dry-run-plan-v1",
        "status": "DRY_RUN_REWRITE_PLAN_READY",
        "candidate": {
            "candidate_id": candidate.get("candidate_id"),
            "kind": candidate.get("kind"),
            "source_path": rel,
            "member_line_start": int(member["line_start"]),
            "member_line_end": int(member["line_end"]),
        },
        "match": {
            "transformation": transformation,
            "condition": condition,
            "condition_boolean_proof": "BOUNDED_SYNTAX_ALLOWLIST",
            "first_terminal": first,
            "second_terminal": second,
            "semicolon_style": "semicolon" if semicolon else "no_semicolon",
            "match_count_in_member_span": len(matches),
            "source_char_start": absolute_start,
            "source_char_end": absolute_end,
        },
        "planned_rewrite": {
            "before": matched_text,
            "after": replacement,
            "before_source_sha256": digest(before_bytes),
            "planned_source_sha256": digest(planned_bytes),
            "diff": diff_text,
        },
        "source_integrity": {
            "target_source_mutated": False,
            "source_unchanged_verified": True,
            "source_sha256_after_planning": digest(after_read),
        },
        "validation_required_before_any_mutation": {
            "parse_after_rewrite": True,
            "focused_target_native_test_before": True,
            "focused_target_native_test_after": True,
            "target_typecheck_or_type_tests_after": True,
            "git_diff_check": True,
            "one_expected_changed_file": True,
            "candidate_specific_authorization": True,
        },
        "authority": {
            "dry_run_only": True,
            "source_mutation_allowed": False,
            "generic_rewrite_authority_granted": False,
            "automatic_patch_authority_granted": False,
            "upstream_mutation_authorized": False,
            "global_behavioral_equivalence_proven": False,
            "truth_commit": False,
        },
        "next_gate": "DRY_RUN_PLANNER_CROSS_REPOSITORY_REVALIDATION",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--diff", required=True)
    args = parser.parse_args()

    root = Path(args.target_root).resolve()
    output = Path(args.output).resolve()
    diff_path = Path(args.diff).resolve()
    _require_evidence_output_outside_target(root, output)
    _require_evidence_output_outside_target(root, diff_path)

    candidate = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
    try:
        plan = build_plan(root, candidate)
    except PlanningError as exc:
        rejection = {
            "schema_version": "plw-js-ts-v2-boolean-guard-dry-run-plan-v1",
            "status": "DRY_RUN_REWRITE_REJECTED",
            "error": str(exc),
            "authority": {
                "dry_run_only": True,
                "source_mutation_allowed": False,
                "truth_commit": False,
            },
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(rejection, indent=2, sort_keys=True) + "\n")
        print(json.dumps(rejection, sort_keys=True))
        return 2

    output.parent.mkdir(parents=True, exist_ok=True)
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    diff_path.write_text(plan["planned_rewrite"]["diff"], encoding="utf-8")
    print(
        json.dumps(
            {
                "status": plan["status"],
                "candidate_id": plan["candidate"]["candidate_id"],
                "transformation": plan["match"]["transformation"],
                "source_mutated": plan["source_integrity"]["target_source_mutated"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
