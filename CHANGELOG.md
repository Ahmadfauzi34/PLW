# Changelog

This file records user-facing changes in published PLW releases. Development work may exist on `main` before it appears here as a release.

## Unreleased

## 0.2.3 — 2026-09-24

### Changed

- declarative operation plans now compile positional argv after `--`, reject
  NUL/invalid-Unicode inputs, and prove CLI round trips for flag-looking tasks
  on the binary;
- candidate revision snapshots bind Git-visible dirty file and symlink bytes
  with an explicit completeness marker;
- rootless source extraction no longer attempts to restore archive ownership;
- release gating now requires Chromium/CDP reproduction and a pinned Vite
  target-first agent workflow against the built artifact;
- Linux x86_64 binary builds use a digest-pinned manylinux2014 container with
  GLIBC 2.17; CI executes the same artifact on GLIBC 2.17 and 2.31 before release.
- repository governance and support documentation are being formalized for the post-0.2.1 development line.
- boolean-guard candidates now bind to one exact source site instead of a whole-function greedy witness;
- duplicate legacy candidate IDs receive distinct candidate-instance bindings and remain ambiguous when task evidence cannot distinguish them.
- shared-graph semantic-usage ordering is canonical across Python hash seeds, keeping discovery snapshots reproducible across processes.
- exact-site v3 candidate witnesses can feed the bounded rewrite planner while preserving candidate-instance and source-span bindings;
- selection, discovery, and internal capability digests can be verified through single-use authorization and postcondition receipt issuance.
- portable-agent evidence-driven capability projection can now advertise read-only `candidate` identity discovery for `semantic_scope`, with explicit proof limits and an embedded skill handoff; task text remains excluded from capability routing.
- compact agent capability projection now carries bounded technical concepts, information role, expected information gain, and proof limits so an agent can judge why a call may be useful before invoking it without reopening the prior context-bloat failure mode.
- candidate discovery now exposes machine-readable operation contracts that separate invocation inputs, domain result states, capacity boundaries, process-failure classes, and authority; normal `RESOLVED`, `AMBIGUOUS`, `UNRESOLVED`, and capability-match states remain domain outcomes rather than process failures.

### Added

- `plw candidate select` with revision, shared-graph, candidate-set, and selection digests;
- `plw candidate capability-match` for read-only internal contract matching after resolved selection;
- fail-closed ambiguity, exact source-symbol/path rationale, and standalone regression coverage.
- a public read-only `candidate` semantic capability and `skills/candidate-selection-provenance-workflow.md`, so agents can discover why/when candidate identity evidence may be useful without exposing the internal mutation capability.
- generic `plw-operation-contract-v1` reference records for `candidate.select.v1` and `candidate.capability-match.v1`, recoverable through `plw capability describe candidate --json`; compact agent orientation advertises only contract availability/count to keep planning metadata bounded.

### Release validation

- standalone executable, operation-plan and dirty snapshot smoke tests;
- ELF bootloader GLIBC ceiling plus actual topology execution on CentOS 7
  (GLIBC 2.17) and Ubuntu 20.04 (GLIBC 2.31);
- required Chrome/CDP UI test and pinned Vite agent workflow;
- target cleanliness and artifact SHA-256 checks.

### Authority

Candidate selection and internal capability matching grant no authorization, execution, mutation, correctness, or evidence-acceptance authority. The public `candidate` semantic handoff is descriptive/read-only and does not automatically run selection. Semantic affordance projection is information-only, bounded for context, and remains non-recommendatory. Operation contracts describe how an operation can be invoked and interpreted but do not authorize or automatically execute it. The bounded mutation capability remains outside public capability discovery.

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
