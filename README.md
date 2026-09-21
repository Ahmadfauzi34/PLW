# PLW

Proof Lattice Workbench (PLW) is a codebase reference-machine and agent tooling project.

This repository is the clean distribution/build repository for PLW. Development audits, historical fixtures, and checkpoint artifacts are intentionally kept out of the runtime distribution.

## Distribution goal

The primary release target is a standalone `plw` executable that can be placed on an agent or developer machine without copying PLW source files into the target codebase.

Planned first target:

- Linux x86_64 standalone binary
- Runtime state outside the target repository
- Optional Chromium/Chrome integration for UI reproduction
- GitHub Actions build + standalone smoke validation

The source imported here will be the clean runtime surface, not the full development/audit package.
