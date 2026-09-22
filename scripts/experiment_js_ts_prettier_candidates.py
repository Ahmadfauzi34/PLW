#!/usr/bin/env python3
"""Apply one strict, pinned Prettier local-candidate experiment rewrite.

This is not a general rewriter. Each case binds one reviewed candidate ID to one
pinned repository revision and exact source shape, then fails closed on drift.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPOSITORY = "prettier/prettier"
REVISION = "6176846ed3c8bde9cdbdab9c1dc3294fc15d0942"

CASES = {
    "scss-boolean-guard": {
        "candidate_id": "sha256:2fb4fc47394645dd1dada20e09c329ff23ae9cf1ef499176e0ba0658b04690c4",
        "kind": "js_boolean_guard_return",
        "source_path": "src/language-css/utilities/index.js",
        "old": """  if (parentParentNode.type === "value-func") {
    return true;
  }

  return false;
""",
        "new": """  return parentParentNode.type === "value-func";
""",
        "focused_validation": [
            "tests/format/scss/map/format.test.js",
            "tests/format/scss/trailing-comma/format.test.js",
        ],
    },
    "cache-terminal-expression": {
        "candidate_id": "sha256:31288793325b8227864f6b0254307a27991c7823dcade80e6235efad7b9c4798",
        "kind": "js_terminal_expression_temporary",
        "source_path": "src/cli/find-cache-file.js",
        "old": """  const cacheFilePath = path.join(cacheDir, ".prettier-cache");
  return cacheFilePath;
""",
        "new": """  return path.join(cacheDir, ".prettier-cache");
""",
        "focused_validation": [
            "tests/integration/__tests__/cache.js",
        ],
    },
}


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=sorted(CASES), required=True)
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    spec = CASES[args.case]
    root = Path(args.target_root).resolve()
    source = (root / spec["source_path"]).resolve()
    source.relative_to(root)
    if not source.is_file():
        raise SystemExit(f"source file missing: {spec['source_path']}")

    before_bytes = source.read_bytes()
    before = before_bytes.decode("utf-8")
    matches = before.count(spec["old"])
    if matches != 1:
        raise SystemExit(
            f"strict candidate shape drift: expected 1 rewrite site, found {matches}"
        )

    after = before.replace(spec["old"], spec["new"], 1)
    if after == before:
        raise SystemExit("rewrite produced no change")
    source.write_text(after, encoding="utf-8", newline="")

    result = {
        "schema_version": "plw-js-ts-rule-diversity-worktree-rewrite-v1",
        "status": "STRICT_REWRITE_APPLIED",
        "case": args.case,
        "candidate": {
            "candidate_id": spec["candidate_id"],
            "kind": spec["kind"],
            "source_path": spec["source_path"],
            "corpus_repository": REPOSITORY,
            "corpus_revision": REVISION,
            "focused_validation": spec["focused_validation"],
        },
        "rewrite": {
            "strict_match_count": matches,
            "before_sha256": digest(before_bytes),
            "after_sha256": digest(source.read_bytes()),
            "old_shape": spec["old"],
            "new_shape": spec["new"],
        },
        "authority": {
            "temporary_checkout_only": True,
            "reviewed_candidate_only": True,
            "upstream_source_mutation": False,
            "patch_is_not_behavioral_equivalence": True,
            "focused_test_pass_is_not_global_correctness": True,
            "truth_commit": False,
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "case": args.case}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
