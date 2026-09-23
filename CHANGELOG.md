# Changelog

This file records user-facing changes in published PLW releases. Development work may exist on `main` before it appears here as a release.

## Unreleased

### Changed

- repository governance and support documentation are being formalized for the post-0.2.1 development line.

## 0.2.1 — 2026-09-23

### Added

- official standalone portable-agent surface;
- `plw doctor <target>` readiness checks;
- `plw agent orient <target> --task "..." --json` target-first orientation;
- embedded capability discovery from the binary;
- embedded skill discovery and exact skill lookup from the binary;
- root `AGENTS.md` and `SKILL.md` first-contact contracts;
- fresh-HOME standalone portable-agent smoke with target-cleanliness proof.

### Release validation

- standalone binary build and binary-safety checks;
- topology/impact smoke;
- portable-agent doctor/orient/embedded-skill smoke;
- JS/TS/TSX/JSX simplification smoke;
- UI static and Chromium/CDP runtime smoke;
- SHA-256 verification before publication.

### Authority

Portable-agent discovery/orientation remains advisory and read-only with respect to target source. This release does not grant generic mutation, automatic patching, external-repository mutation, stable-promotion, or truth authority.

## 0.2.0 — 2026-09-23

### Added

- standalone Linux x86_64 binary release path;
- JS/TS Structural Simplification V2 frontend for `.ts`, `.tsx`, `.js`, and `.jsx`;
- seven conservative JS/TS simplification rule families;
- binary/runtime safety cleanup and standalone smoke coverage;
- published release binary plus SHA-256 checksum.

### Notes

Simplification output is candidate evidence, not automatic patch authority or behavioral-equivalence proof.
