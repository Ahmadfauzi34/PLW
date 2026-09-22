#!/usr/bin/env python3
"""Apply one strict Vite boolean-guard replication rewrite.

This is a candidate-specific experiment helper, not a general rewriter.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

CANDIDATE_ID = "sha256:d4d1da6c55c80079b4761ae51b1593c8b051e8c3ff276fb78fd6542ab2bfdef0"
REPOSITORY = "vitejs/vite"
REVISION = "1544bb1b7ac92f775e9d0dea97954c99cc6cbd43"
SOURCE_PATH = "packages/vite/src/node/ssr/ssrTransform.ts"
RULE = "js_boolean_guard_return"

OLD = """  // is a special keyword but parsed as identifier
  if (id.name === 'arguments') {
    return false
  }

  return true
}
"""
NEW = """  // is a special keyword but parsed as identifier
  return id.name !== 'arguments'
}
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
        "schema_version": "plw-js-ts-vite-boolean-replication-rewrite-v1",
        "status": "STRICT_REWRITE_APPLIED",
        "candidate": {
            "candidate_id": CANDIDATE_ID,
            "kind": RULE,
            "source_path": SOURCE_PATH,
            "corpus_repository": REPOSITORY,
            "corpus_revision": REVISION,
            "name": "isRefIdentifier",
            "focused_validation": [
                "packages/vite/src/node/ssr/__tests__/ssrTransform.spec.ts"
            ],
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
            "reviewed_candidate_only": True,
            "cross_repository_replication": True,
            "upstream_source_mutation": False,
            "patch_is_not_behavioral_equivalence": True,
            "focused_test_pass_is_not_global_correctness": True,
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
