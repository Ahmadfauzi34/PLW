#!/usr/bin/env python3
"""Require identical shared-graph digests across Python hash seeds."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="plw_graph_signature_") as temp:
        root = Path(temp)
        source = root / "src"
        source.mkdir()
        (source / "helpers.js").write_text(
            "export function alpha() {}\n"
            "export function beta() {}\n"
            "export function gamma() {}\n",
            encoding="utf-8",
        )
        (source / "main.js").write_text(
            'import { alpha, beta, gamma } from "./helpers.js";\n'
            "alpha();\n"
            "beta();\n"
            "gamma();\n",
            encoding="utf-8",
        )

        command = [
            sys.executable,
            "-c",
            (
                "import sys; from core.shared_graph import build_shared_graph, "
                "graph_content_signature; "
                "print(graph_content_signature(build_shared_graph(sys.argv[1])))"
            ),
            str(root),
        ]
        digests = []
        for hash_seed in ("1", "987654"):
            env = dict(os.environ)
            env["PYTHONHASHSEED"] = hash_seed
            proc = subprocess.run(
                command,
                text=True,
                capture_output=True,
                check=False,
                env=env,
            )
            if proc.returncode != 0:
                raise SystemExit(proc.stderr or proc.stdout)
            digests.append(proc.stdout.strip())

        if len(set(digests)) != 1:
            raise SystemExit(
                "shared-graph signature changed across hash seeds: "
                + ", ".join(digests)
            )
        print(f"SHARED_GRAPH_SIGNATURE_DETERMINISM: PASS {digests[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
