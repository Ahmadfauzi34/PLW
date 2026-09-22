#!/usr/bin/env python3
"""Apply one strict, pinned JS/TS local-candidate experiment rewrite.

This helper is intentionally not a general source rewriter. It recognizes one
candidate ID at one pinned repository revision and fails closed on any byte-shape
drift. The target checkout is expected to be disposable CI state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

CANDIDATE_ID = "sha256:c27d04409b63ff0100535ec7b9129b4c01133235e6a4f0b22b3d3fb6ba7fc6f6"
CORPUS_REPOSITORY = "reduxjs/redux-toolkit"
CORPUS_REVISION = "c9dac937d77adc3bf04842a43955e81d0e7a46da"
SOURCE_PATH = "packages/toolkit/src/immutableStateInvariantMiddleware.ts"
RULE = "js_redundant_else_after_terminal"

OLD = """  if (process.env.NODE_ENV === 'production') {
    return () => (next) => (action) => next(action)
  } else {
"""
NEW = """  if (process.env.NODE_ENV === 'production') {
    return () => (next) => (action) => next(action)
  }
  {
"""


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    root = Path(args.target_root).resolve()
    source = (root / SOURCE_PATH).resolve()
    source.relative_to(root)
    if not source.is_file():
        raise SystemExit(f"source file missing: {SOURCE_PATH}")

    before_bytes = source.read_bytes()
    before = before_bytes.decode("utf-8")
    matches = before.count(OLD)
    if matches != 1:
        raise SystemExit(
            f"strict candidate shape drift: expected 1 rewrite site, found {matches}"
        )

    after = before.replace(OLD, NEW, 1)
    if after == before:
        raise SystemExit("rewrite produced no change")

    source.write_text(after, encoding="utf-8", newline="")

    result = {
        "schema_version": "plw-js-ts-local-worktree-experiment-v1",
        "status": "STRICT_REWRITE_APPLIED",
        "candidate": {
            "candidate_id": CANDIDATE_ID,
            "kind": RULE,
            "source_path": SOURCE_PATH,
            "corpus_repository": CORPUS_REPOSITORY,
            "corpus_revision": CORPUS_REVISION,
        },
        "rewrite": {
            "strict_match_count": matches,
            "before_sha256": digest(before_bytes),
            "after_sha256": digest(source.read_bytes()),
            "old_shape": OLD,
            "new_shape": NEW,
        },
        "authority": {
            "temporary_checkout_only": True,
            "upstream_source_mutation": False,
            "patch_is_not_behavioral_equivalence": True,
            "test_pass_is_not_global_correctness": True,
            "truth_commit": False,
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "candidate": CANDIDATE_ID}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
