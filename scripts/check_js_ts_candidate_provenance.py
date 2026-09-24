#!/usr/bin/env python3
"""Fail-closed candidate selection and internal capability-match checks."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.candidate_provenance import (
    build_discovery_binding,
    match_internal_candidate_capability,
    select_candidate,
)
from core.portable_agent import list_capabilities
from core.simplification_analyzer import analyze_simplification


def run(*args: str, cwd: Path) -> str:
    proc = subprocess.run(args, cwd=str(cwd), text=True, capture_output=True, check=False, shell=False)
    if proc.returncode:
        raise AssertionError(f"command failed: {args!r}\n{proc.stdout}\n{proc.stderr}")
    return proc.stdout.strip()


def write_fixture(root: Path) -> None:
    source = root / "src" / "guards.js"
    source.parent.mkdir(parents=True)
    source.write_text(
        "function isSCSSMapItemNode(node) {\n"
        "  if (node.type === 'map-item') {\n"
        "    return true;\n"
        "  }\n"
        "  return false;\n"
        "}\n\n"
        "function isRefIdentifier(id) {\n"
        "  if (id.name === 'arguments') {\n"
        "    return false;\n"
        "  }\n"
        "  return true;\n"
        "}\n\n"
        "function isLooseMapNode(node) {\n"
        "  if (node.type !== 'map-item') {\n"
        "    return true;\n"
        "  }\n"
        "  return false;\n"
        "}\n\n"
        "function a(value) {\n"
        "  if (value) {\n"
        "    return true;\n"
        "  }\n"
        "  return false;\n"
        "}\n\n"
        "function hasNoBoundedSite(value) {\n"
        "  if (value.first) {\n"
        "    return false;\n"
        "  }\n"
        "  const second = value.second;\n"
        "  return second;\n"
        "}\n",
        encoding="utf-8",
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="plw-candidate-provenance-") as temp:
        root = Path(temp).resolve()
        write_fixture(root)
        run("git", "init", "-q", cwd=root)
        run("git", "config", "user.email", "plw-reference@example.invalid", cwd=root)
        run("git", "config", "user.name", "PLW Candidate Reference", cwd=root)
        run("git", "add", "src/guards.js", cwd=root)
        run("git", "commit", "-q", "-m", "candidate provenance fixture", cwd=root)
        before_status = run("git", "status", "--porcelain=v1", "--untracked-files=all", cwd=root)

        discovery = analyze_simplification(str(root))
        binding, candidates = build_discovery_binding(str(root), discovery)
        guards = [row for row in candidates if row.get("kind") == "js_boolean_guard_return"]
        by_symbol = {row["names"][0]: row for row in guards}

        assert len(guards) == 4, f"expected four exact guard sites, got {len(guards)}"
        assert "hasNoBoundedSite" not in by_symbol, "greedy function-wide false positive survived"
        for symbol, row in by_symbol.items():
            witness = row.get("semantic_witness", {})
            site = witness.get("source_site", {})
            member = row["members"][0]
            assert witness.get("type") == "js_boolean_guard_return_v3"
            assert member["line_start"] == site["line_start"]
            assert member["line_end"] == site["line_end"]
            assert row.get("candidate_instance_id", "").startswith("sha256:")

        positive = by_symbol["isSCSSMapItemNode"]
        inverse = by_symbol["isRefIdentifier"]
        legacy_candidate_id = "sha256:" + hashlib.sha256(
            json.dumps({
                "file": "src/guards.js",
                "kind": "js_boolean_guard_return",
                "function": "isSCSSMapItemNode",
                "inverse": False,
            }, sort_keys=True).encode("utf-8")
        ).hexdigest()
        assert positive["candidate_id"] == legacy_candidate_id

        resolved = select_candidate(
            "Explain why isSCSSMapItemNode is a bounded boolean guard candidate.",
            binding,
            candidates,
        )
        assert resolved["resolution"] == "RESOLVED"
        assert resolved["selected_candidate_id"] == positive["candidate_id"]
        assert resolved["selected_source_path"] == "src/guards.js"
        assert resolved["selected_symbol"] == "isSCSSMapItemNode"
        assert resolved["selection_basis"] == [{"kind": "EXACT_SYMBOL_MENTION", "values": ["isSCSSMapItemNode"]}]
        path_and_symbol = select_candidate(
            "Explain isSCSSMapItemNode in src/guards.js.", binding, candidates,
        )
        assert path_and_symbol["resolution"] == "RESOLVED"
        assert {row["kind"] for row in path_and_symbol["selection_basis"]} == {
            "EXACT_SYMBOL_MENTION", "EXACT_SOURCE_PATH_MENTION",
        }
        conflicting_anchors = select_candidate(
            "Select isSCSSMapItemNode in src/not-the-file.js.", binding, candidates,
        )
        assert conflicting_anchors["resolution"] == "UNRESOLVED"
        assert conflicting_anchors["reason"] == "CONFLICTING_EXACT_SYMBOL_AND_PATH_HINTS"
        wrong_case_symbol = select_candidate("ISSCSSMAPITEMNODE", binding, candidates)
        assert wrong_case_symbol["selected_candidate_id"] is None
        conflicting_constraints = select_candidate(
            "Select a boolean guard using strict equality and strict inequality.",
            binding,
            candidates,
        )
        assert conflicting_constraints["resolution"] == "UNRESOLVED"
        assert conflicting_constraints["reason"] == "CONFLICTING_TASK_STRUCTURAL_CONSTRAINTS"
        short_symbol_selection = select_candidate("Explain why `a` is a boolean guard candidate.", binding, candidates)
        assert short_symbol_selection["resolution"] == "RESOLVED"
        assert short_symbol_selection["selected_symbol"] == "a"

        routed = match_internal_candidate_capability(resolved, binding, candidates)
        assert routed["status"] == "CAPABILITY_MATCHED", routed
        assert routed["matched_capability_id"] == "js_boolean_guard.strict_equality_string.temp_worktree.v1"
        assert routed["match_facts"]["source_bytes_match_site_digest"] is True
        assert routed["match_facts"]["source_facts_match_discovery_witness"] is True
        for key in ("authorization", "execution", "mutation", "correctness", "evidence_acceptance"):
            assert routed["authority"][key] is False

        forged_facts_discovery = dict(discovery)
        forged_fact_rows = [dict(row) for row in discovery["candidates"]]
        for row in forged_fact_rows:
            if row.get("candidate_id") == positive["candidate_id"]:
                witness = dict(row["semantic_witness"])
                facts = dict(witness["condition_facts"])
                facts["operator"] = "!=="
                witness["condition_facts"] = facts
                row["semantic_witness"] = witness
        forged_facts_discovery["candidates"] = forged_fact_rows
        forged_binding, forged_candidates = build_discovery_binding(str(root), forged_facts_discovery)
        forged_facts_selection = select_candidate(
            "Explain why isSCSSMapItemNode is a bounded boolean guard candidate.",
            forged_binding,
            forged_candidates,
        )
        forged_facts_route = match_internal_candidate_capability(
            forged_facts_selection, forged_binding, forged_candidates,
        )
        assert forged_facts_route["status"] == "CAPABILITY_NOT_MATCHED"
        assert any("source_facts_match_discovery_witness" in reason for reason in forged_facts_route["rejection_reasons"])

        fixture_source = root / "src" / "guards.js"
        original_source = fixture_source.read_bytes()
        fixture_source.write_bytes(original_source.replace(b"map-item", b"map-elem", 1))
        try:
            changed_source_route = match_internal_candidate_capability(resolved, binding, candidates)
            assert changed_source_route["status"] == "CAPABILITY_NOT_MATCHED"
            assert any("source_bytes_match_site_digest" in reason for reason in changed_source_route["rejection_reasons"])
        finally:
            fixture_source.write_bytes(original_source)

        inverse_selection = select_candidate(
            "Explain why isRefIdentifier is an inverse boolean guard candidate.",
            binding,
            candidates,
        )
        assert inverse_selection["resolution"] == "RESOLVED"
        inverse_route = match_internal_candidate_capability(inverse_selection, binding, candidates)
        assert inverse_route["status"] == "CAPABILITY_MATCHED"
        assert inverse_route["match_facts"]["condition"]["transformation"] == "inverse"

        duplicated_discovery = dict(discovery)
        duplicate_rows = [dict(row) for row in discovery["candidates"]]
        duplicate_legacy_row = deepcopy(positive)
        duplicate_legacy_row.pop("candidate_instance_id", None)
        duplicate_legacy_row["members"] = [dict(duplicate_legacy_row["members"][0], line_start=99)]
        duplicate_rows.append(duplicate_legacy_row)
        duplicated_discovery["candidates"] = duplicate_rows
        duplicate_binding, duplicate_candidates = build_discovery_binding(str(root), duplicated_discovery)
        same_legacy_id = [row for row in duplicate_candidates if row.get("candidate_id") == positive["candidate_id"]]
        assert len(same_legacy_id) == 2
        assert same_legacy_id[0]["candidate_instance_id"] != same_legacy_id[1]["candidate_instance_id"]
        duplicate_selection = select_candidate(
            "Explain why isSCSSMapItemNode is a bounded boolean guard candidate.",
            duplicate_binding,
            duplicate_candidates,
        )
        assert duplicate_selection["resolution"] == "AMBIGUOUS"

        ambiguous = select_candidate(
            "Select one boolean guard with opposite boolean returns.", binding, candidates,
        )
        assert ambiguous["resolution"] == "AMBIGUOUS"
        assert len(ambiguous["ambiguous_candidates"]) == 4
        assert match_internal_candidate_capability(ambiguous, binding, candidates)["status"] == "CAPABILITY_NOT_MATCHED"

        structural_ambiguous = select_candidate(
            "Select a boolean guard using strict equality and a string literal.", binding, candidates,
        )
        assert structural_ambiguous["resolution"] == "AMBIGUOUS"
        assert len(structural_ambiguous["ambiguous_candidates"]) == 2
        structural_positive = select_candidate(
            "Select the boolean guard using strict equality, a string literal, and positive form.",
            binding,
            candidates,
        )
        assert structural_positive["resolution"] == "RESOLVED"
        assert structural_positive["selected_candidate_id"] == positive["candidate_id"]
        assert match_internal_candidate_capability(structural_positive, binding, candidates)["status"] == "CAPABILITY_MATCHED"
        structural_inverse = select_candidate(
            "Select the boolean guard using strict equality, a string literal, and inverse form.",
            binding,
            candidates,
        )
        assert structural_inverse["resolution"] == "RESOLVED"
        assert structural_inverse["selected_candidate_id"] == inverse["candidate_id"]

        unsupported_selection = select_candidate(
            "Select isLooseMapNode as a boolean guard.", binding, candidates,
        )
        assert unsupported_selection["resolution"] == "RESOLVED"
        unsupported_route = match_internal_candidate_capability(unsupported_selection, binding, candidates)
        assert unsupported_route["status"] == "CAPABILITY_NOT_MATCHED"
        assert any("operator" in reason for reason in unsupported_route["rejection_reasons"])

        tampered = [dict(row) for row in candidates]
        tampered[0]["names"] = ["forged"]
        tampered_selection = select_candidate("isSCSSMapItemNode", binding, tampered)
        assert tampered_selection["resolution"] == "UNRESOLVED"
        assert tampered_selection["reason"] == "CANDIDATE_SET_DIGEST_MISMATCH"

        edited_selection: Dict[str, Any] = dict(resolved)
        edited_selection["selected_candidate_id"] = "sha256:forged"
        assert match_internal_candidate_capability(edited_selection, binding, candidates)["status"] == "CAPABILITY_NOT_MATCHED"
        recomputed_forgery = dict(edited_selection)
        recomputed_forgery.pop("candidate_selection_digest")
        recomputed_forgery["candidate_selection_digest"] = "sha256:" + hashlib.sha256(
            json.dumps(recomputed_forgery, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        forged_route = match_internal_candidate_capability(recomputed_forgery, binding, candidates)
        assert forged_route["status"] == "CAPABILITY_NOT_MATCHED"
        assert forged_route["rejection_reasons"] == ["SELECTION_DECISION_RECOMPUTATION_MISMATCH"]

        public_registry = list_capabilities()
        public_rows = json.dumps(public_registry)
        assert "js_boolean_guard.strict_equality_string.temp_worktree.v1" not in public_rows

        cli = subprocess.run(
            [
                sys.executable, str(ROOT / "plw_cli.py"), "candidate", "capability-match",
                "Explain why isSCSSMapItemNode is a bounded boolean guard candidate.", str(root), "--json",
            ],
            cwd=str(ROOT), text=True, capture_output=True, check=False, shell=False,
        )
        assert cli.returncode == 0, f"candidate CLI failed: {cli.stderr}"
        cli_result = json.loads(cli.stdout)
        assert cli_result["candidate_selection"]["resolution"] == "RESOLVED"
        assert cli_result["candidate_capability_match"]["status"] == "CAPABILITY_MATCHED"

        after_status = run("git", "status", "--porcelain=v1", "--untracked-files=all", cwd=root)
        assert after_status == before_status == "", "read-only candidate gate changed fixture sources"

        print(
            "CANDIDATE_SELECTION_PROVENANCE: PASS "
            f"candidates={len(candidates)} guard_sites={len(guards)} "
            f"ambiguous={ambiguous['resolution']} duplicate_ids=AMBIGUOUS "
            f"positive={routed['status']} inverse={inverse_route['status']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
