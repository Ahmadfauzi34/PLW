#!/usr/bin/env python3
"""Prepare one sealed Vite boolean-guard experiment before mutation.

Candidate-specific, reference-only preparation. Runs the exact focused baseline
validation, freezes the postcondition-validation spec, and emits preflight,
authorization, and disposable-boundary receipts. It never mutates target source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Sequence

REPOSITORY = "vitejs/vite"
REVISION = "1544bb1b7ac92f775e9d0dea97954c99cc6cbd43"
RULE = "js_boolean_guard_return"
CANDIDATE_ID = (
    "sha256:d4d1da6c55c80079b4761ae51b1593c8b051e8c3ff276fb78fd6542ab2bfdef0"
)
SOURCE_PATH = "packages/vite/src/node/ssr/ssrTransform.ts"

FOCUSED_COMMAND = [
    "pnpm",
    "exec",
    "vitest",
    "run",
    "packages/vite/src/node/ssr/__tests__/ssrTransform.spec.ts",
]
PARSE_COMMAND = [
    "pnpm",
    "exec",
    "esbuild",
    SOURCE_PATH,
    "--format=esm",
    "--platform=node",
    "--log-level=error",
    "--outfile=/dev/null",
]
TYPECHECK_COMMAND = ["pnpm", "--filter", "vite", "typecheck"]


class PreparationError(ValueError):
    pass


def _digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _digest_file(path: Path) -> str:
    return _digest_bytes(path.read_bytes())


def _digest_text(text: str) -> str:
    return _digest_bytes(text.encode("utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _run(
    argv: Sequence[str],
    *,
    cwd: Path,
    timeout_seconds: int = 1200,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        cwd=str(cwd),
        shell=False,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
    )


def _git(root: Path, *args: str) -> str:
    proc = _run(["git", "-C", str(root), *args], cwd=root, timeout_seconds=60)
    if proc.returncode != 0:
        raise PreparationError(
            f"git {' '.join(args)} failed: "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout.strip()


def _git_optional(root: Path, *args: str) -> str:
    proc = _run(["git", "-C", str(root), *args], cwd=root, timeout_seconds=60)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _require_outside_target(root: Path, path: Path, label: str) -> None:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return
    raise PreparationError(f"{label} must be outside target root")


def _validate_plan_and_candidate(
    *,
    root: Path,
    plan: Dict[str, Any],
    candidate: Dict[str, Any],
) -> Dict[str, Any]:
    if plan.get("schema_version") != "plw-js-ts-v2-boolean-guard-dry-run-plan-v1":
        raise PreparationError("unexpected dry-run plan schema")
    if plan.get("status") != "DRY_RUN_REWRITE_PLAN_READY":
        raise PreparationError("dry-run plan is not ready")

    plan_candidate = plan.get("candidate", {}) or {}
    if plan_candidate.get("kind") != RULE:
        raise PreparationError("plan candidate kind mismatch")
    if plan_candidate.get("candidate_id") != CANDIDATE_ID:
        raise PreparationError("plan candidate id mismatch")
    if plan_candidate.get("source_path") != SOURCE_PATH:
        raise PreparationError("plan source path mismatch")

    if candidate.get("candidate_id") != CANDIDATE_ID:
        raise PreparationError("fresh candidate id mismatch")
    if candidate.get("kind") != RULE:
        raise PreparationError("fresh candidate kind mismatch")
    if list(candidate.get("files", []) or []) != [SOURCE_PATH]:
        raise PreparationError("fresh candidate source mismatch")

    source_path = (root / SOURCE_PATH).resolve()
    source_path.relative_to(root)
    if not source_path.is_file():
        raise PreparationError("target source is missing")

    source_bytes = source_path.read_bytes()
    rewrite = plan.get("planned_rewrite", {}) or {}
    if _digest_bytes(source_bytes) != rewrite.get("before_source_sha256"):
        raise PreparationError("source bytes do not match plan before hash")

    source_integrity = plan.get("source_integrity", {}) or {}
    if source_integrity.get("target_source_mutated") is not False:
        raise PreparationError("dry-run planner unexpectedly mutated target")
    if source_integrity.get("source_unchanged_verified") is not True:
        raise PreparationError("dry-run planner did not prove unchanged source")

    if (plan.get("match", {}) or {}).get("transformation") != "inverse":
        raise PreparationError("Vite planner must preserve inverse transformation")
    if rewrite.get("after") != "  return !(id.name === 'arguments')":
        raise PreparationError("Vite conservative planner output drifted")

    before = str(rewrite.get("before", ""))
    line_start = int(plan_candidate.get("member_line_start", 0) or 0)
    line_end = int(plan_candidate.get("member_line_end", 0) or 0)
    lines = source_bytes.decode("utf-8").splitlines(keepends=True)
    if line_start < 1 or line_end < line_start or line_end > len(lines):
        raise PreparationError("plan member line span is invalid")
    member = "".join(lines[line_start - 1 : line_end])
    match_count = member.count(before)
    if match_count != 1:
        raise PreparationError(
            f"expected one planned source span inside member, found {match_count}"
        )

    return {
        "source_path": source_path,
        "member_match_count": match_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--disposable-parent", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    root = Path(args.target_root).resolve()
    disposable_parent = Path(args.disposable_parent).resolve()
    candidate_path = Path(args.candidate).resolve()
    plan_path = Path(args.plan).resolve()
    out = Path(args.output_dir).resolve()

    for path, label in (
        (candidate_path, "candidate evidence"),
        (plan_path, "dry-run plan"),
        (out, "experiment evidence directory"),
    ):
        _require_outside_target(root, path, label)

    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan_info = _validate_plan_and_candidate(
        root=root,
        plan=plan,
        candidate=candidate,
    )

    revision = _git(root, "rev-parse", "HEAD")
    if revision != REVISION:
        raise PreparationError(
            f"target revision mismatch: expected {REVISION}, got {revision}"
        )

    status_before = _git(root, "status", "--porcelain", "--untracked-files=all")
    if status_before:
        raise PreparationError(
            "target must be clean before baseline validation: "
            + status_before.replace("\n", " | ")
        )

    origin = _git(root, "remote", "get-url", "origin")
    extraheader = _git_optional(
        root,
        "config",
        "--get-all",
        "http.https://github.com/.extraheader",
    )
    if extraheader:
        raise PreparationError("GitHub extraheader credentials are still configured")
    if "@" in origin.split("://", 1)[-1].split("/", 1)[0]:
        raise PreparationError("origin URL appears to contain embedded credentials")

    baseline = _run(FOCUSED_COMMAND, cwd=root, timeout_seconds=1200)
    baseline_record = {
        "command": FOCUSED_COMMAND,
        "exit_code": baseline.returncode,
        "stdout_sha256": _digest_text(baseline.stdout),
        "stderr_sha256": _digest_text(baseline.stderr),
        "stdout_tail": baseline.stdout[-4000:],
        "stderr_tail": baseline.stderr[-4000:],
    }
    if baseline.returncode != 0:
        _write_json(out / "baseline-failure.json", baseline_record)
        raise PreparationError("focused baseline validation failed")

    status_after = _git(root, "status", "--porcelain", "--untracked-files=all")
    if status_after:
        raise PreparationError(
            "baseline validation changed target checkout: "
            + status_after.replace("\n", " | ")
        )

    spec = {
        "schema_version": "plw-js-ts-v2-postcondition-validation-spec-v1",
        "status": "POSTCONDITION_VALIDATION_SPEC_READY",
        "target": {
            "repository": REPOSITORY,
            "revision": revision,
            "source_path": SOURCE_PATH,
            "candidate_id": CANDIDATE_ID,
        },
        "commands": {
            "parse_after_rewrite": PARSE_COMMAND,
            "focused_target_native_after": FOCUSED_COMMAND,
            "target_typecheck_or_type_tests_after": TYPECHECK_COMMAND,
        },
        "policy": {
            "cwd": "TARGET_ROOT",
            "shell": False,
            "stop_on_first_failure": True,
        },
        "authority": {
            "spec_only": True,
            "source_mutation_allowed": False,
            "truth_commit": False,
        },
    }
    spec_path = out / "postcondition-validation-spec.json"
    _write_json(spec_path, spec)
    spec_digest = _digest_file(spec_path)

    rewrite = plan.get("planned_rewrite", {}) or {}
    plan_digest = _digest_file(plan_path)
    preflight = {
        "schema_version": "plw-js-ts-v2-mutation-preflight-v1",
        "status": "PREFLIGHT_VALIDATED",
        "postcondition_validation_spec_digest": spec_digest,
        "target": {
            "repository": REPOSITORY,
            "revision": revision,
            "source_path": SOURCE_PATH,
            "candidate_id": CANDIDATE_ID,
            "target_root_realpath_sha256": _digest_text(str(root)),
        },
        "plan_binding": {
            "plan_digest": plan_digest,
            "before_source_sha256": rewrite.get("before_source_sha256"),
            "planned_source_sha256": rewrite.get("planned_source_sha256"),
            "planned_diff_digest": _digest_text(str(rewrite.get("diff", ""))),
        },
        "checks": {
            "clean_checkout": True,
            "disposable_checkout": True,
            "primary_worktree": False,
            "upstream_push_credentials_disabled": True,
            "source_hash_matches_plan": (
                _digest_file(plan_info["source_path"])
                == rewrite.get("before_source_sha256")
            ),
            "candidate_span_match_count_one": (
                plan_info["member_match_count"] == 1
            ),
            "baseline_validation_passed": True,
        },
        "baseline_validation": baseline_record,
        "authority": {
            "read_only": True,
            "source_mutation_allowed": False,
            "truth_commit": False,
        },
    }
    preflight_path = out / "preflight.json"
    _write_json(preflight_path, preflight)
    preflight_digest = _digest_file(preflight_path)

    authorization = {
        "schema_version": "plw-js-ts-v2-mutation-authorization-v1",
        "status": "MUTATION_AUTHORIZED",
        "authorized": True,
        "authorization_scope": "ONE_CANDIDATE_ONE_TARGET_ONE_PLAN",
        "single_use": True,
        "issuer": {
            "kind": "INTERACTIVE_EXPERIMENT_HARNESS",
            "external_to_planner": True,
            "planner_self_authorized": False,
            "scope_note": "User-authorized disposable Vite evidence collection only",
        },
        "binding": {
            "candidate_id": CANDIDATE_ID,
            "target_repository": REPOSITORY,
            "target_revision": revision,
            "source_path": SOURCE_PATH,
            "before_source_sha256": rewrite.get("before_source_sha256"),
            "planned_source_sha256": rewrite.get("planned_source_sha256"),
            "plan_digest": plan_digest,
            "preflight_evidence_digest": preflight_digest,
            "postcondition_validation_spec_digest": spec_digest,
        },
        "authority": {
            "generic_mutation_authority_granted": False,
            "automatic_patch_authority_granted": False,
            "upstream_mutation_authorized": False,
            "global_behavioral_equivalence_proven": False,
            "truth_commit": False,
        },
    }
    authorization_path = out / "authorization.json"
    _write_json(authorization_path, authorization)

    boundary = {
        "schema_version": "plw-js-ts-v2-disposable-boundary-v1",
        "status": "DISPOSABLE_BOUNDARY_READY",
        "reference_only": True,
        "primary_worktree": False,
        "disposable_parent_realpath": str(disposable_parent),
        "target_root_realpath": str(root),
        "target_root_realpath_sha256": _digest_text(str(root)),
    }
    _write_json(out / "disposable-boundary.json", boundary)

    summary = {
        "schema_version": "plw-js-ts-v2-vite-sealed-preparation-v1",
        "status": "SEALED_VITE_EXPERIMENT_PREPARED",
        "repository": REPOSITORY,
        "revision": revision,
        "candidate_id": CANDIDATE_ID,
        "source_path": SOURCE_PATH,
        "plan_digest": plan_digest,
        "postcondition_validation_spec_digest": spec_digest,
        "preflight_evidence_digest": preflight_digest,
        "baseline_validation": {
            "command": FOCUSED_COMMAND,
            "exit_code": baseline.returncode,
            "stdout_sha256": baseline_record["stdout_sha256"],
            "stderr_sha256": baseline_record["stderr_sha256"],
        },
        "planner_transformation": "inverse",
        "planner_after": rewrite.get("after"),
        "clean_before_baseline": status_before == "",
        "clean_after_baseline": status_after == "",
        "upstream_push_credentials_disabled": True,
        "primary_worktree": False,
        "authority": {
            "preparation_only": True,
            "source_mutation_allowed": False,
            "automatic_patch_authority_granted": False,
            "upstream_mutation_authorized": False,
            "truth_commit": False,
        },
        "next_gate": "TEMP_WORKTREE_APPLIED",
    }
    _write_json(out / "preparation-summary.json", summary)

    print(
        json.dumps(
            {
                "status": summary["status"],
                "candidate_id": CANDIDATE_ID,
                "baseline_exit_code": baseline.returncode,
                "clean_after_baseline": status_after == "",
                "planner_transformation": "inverse",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
