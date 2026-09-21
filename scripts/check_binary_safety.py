#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

RUNTIME_PATHS = [ROOT / name for name in ('core','codebase','context','bridge','memory','fullstack','ui')]
RUNTIME_FILES = [ROOT / name for name in ('agent_tool.py','hott_kernel.py','language_semantics.py','plw_cli.py')]

CHECKS = [
    ('source-byte-runtime-dependency', re.compile(r"Path\\(__file__\\).*?(?:read_bytes|with_name\\([^\\n]+\\.py)", re.S), 'runtime must not require neighboring Python source bytes'),
    ('tool-root-runtime-state', re.compile(r"_TOOL_ROOT\\s*/\\s*[\\\"']data[\\\"']\\s*/\\s*[\\\"']runtime[\\\"']"), 'runtime state must use PLW/XDG state paths, not the source tree'),
]

def iter_sources():
    for base in RUNTIME_PATHS:
        if base.exists():
            yield from base.rglob('*.py')
    for path in RUNTIME_FILES:
        if path.exists():
            yield path

def main() -> int:
    sources = list(iter_sources())
    if not sources:
        print('BINARY_SAFETY: source not imported yet; nothing to check')
        return 0
    failures = []
    for path in sources:
        text = path.read_text(encoding='utf-8')
        for name, pattern, reason in CHECKS:
            if pattern.search(text):
                failures.append((path.relative_to(ROOT).as_posix(), name, reason))
    if failures:
        print('BINARY_SAFETY: FAIL')
        for path, name, reason in failures:
            print(f'- {path}: {name}: {reason}')
        return 1
    print(f'BINARY_SAFETY: PASS ({len(sources)} runtime Python files checked)')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
