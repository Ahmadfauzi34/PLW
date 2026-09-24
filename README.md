# PLW — Proof Lattice Workbench

PLW is a standalone codebase reference-machine and agent tooling CLI. It is designed to analyze a target repository without copying the PLW source tree into that repository.

Current binary target: **Linux x86_64**.

## Install

Download the latest release assets:

- `plw-linux-x86_64`
- `plw-linux-x86_64.sha256`

Verify and install:

```bash
sha256sum --check plw-linux-x86_64.sha256
chmod +x plw-linux-x86_64
sudo install plw-linux-x86_64 /usr/local/bin/plw
```

Then verify that the standalone executable is ready:

```bash
plw doctor /path/to/project
```

For an agent encountering an unfamiliar repository, the official first-contact entrypoint is:

```bash
plw agent orient /path/to/project \
  --task "describe the change or investigation" \
  --json
```

The binary is self-describing. It can enumerate capability contracts and read the exact embedded skill handoff without a neighboring PLW source or skill directory:

```bash
plw capability list --json
plw capability describe topology --json
plw skill list --json
plw skill show topology --json
```

Direct expert commands remain available:

```bash
plw topology /path/to/project --json
plw impact src/example.ts /path/to/project --json
plw simplify /path/to/project --json
plw candidate select "task with a candidate symbol or structural constraints" /path/to/project --json
plw candidate capability-match "task with a candidate symbol or structural constraints" /path/to/project --json
```

Candidate selection and internal candidate-capability matching are read-only
provenance surfaces. They do not grant authorization or execution authority,
and the bounded mutation capability remains outside public capability discovery.
See [docs/CANDIDATE_SELECTION_PROVENANCE.md](docs/CANDIDATE_SELECTION_PROVENANCE.md).

Portable-agent commands are discovery/orientation surfaces only. They do not grant runtime execution, source mutation, external-repository mutation, or truth authority.

## What PLW provides

PLW currently exposes several bounded analysis surfaces:

- **Topology / impact** — codebase structure, dependencies, entrypoints, boundaries, consumers.
- **Simplification** — mechanically witnessed simplification candidates; never automatic source mutation.
- **UI mapping** — rendered geometry, overlap, clipping, viewport and ownership mapping.
- **UI bug analysis** — cross-domain diagnosis from rendered symptom to bounded structural candidates.
- **Runtime reproduction** — Chromium/CDP exact-scenario reproduction.
- **Causal isolation / bounded fix verification** — counterfactual support and post-fix recapture without equating symptom removal with global proof.

Important authority boundaries remain explicit:

```text
Candidate ≠ Patch
Topology ≠ Causality
Geometry ≠ Behavior
Runtime reproduction ≠ Root-cause proof
Fix verified in one scenario ≠ global regression proof
```

## TypeScript / JavaScript simplification

The current JS-family frontend is **`js_structural_v2`**, shared across:

```text
.ts
.tsx
.js
.jsx
```

It currently provides seven conservative rule families:

1. try/catch identical terminal return;
2. terminal literal temporary;
3. direct forwarding wrapper;
4. exact function-body duplication;
5. redundant `else` after a terminal branch;
6. boolean guard return;
7. terminal expression temporary.

Example:

```bash
plw simplify ./frontend --json
```

Expected frontend metadata:

```text
semantic_frontend = python_ast+js_structural_v2
ts_js_rule_count  = 7
```

See [docs/SIMPLIFY_JS_TS.md](docs/SIMPLIFY_JS_TS.md) for rule boundaries and deferred cases.

## Browser-backed commands

Static topology, impact, simplification, UI snapshot mapping and geometry analysis do not require an embedded browser.

Commands that execute rendered scenarios use an externally installed Chromium/Chrome executable. Chromium is intentionally **not bundled** in the PLW binary.

## Runtime state

PLW must not intentionally place mutable state in the analyzed target repository.

Runtime state/cache resolve through PLW/XDG locations such as:

```text
PLW_HOME
XDG_STATE_HOME/plw
XDG_CACHE_HOME/plw
~/.local/state/plw
~/.cache/plw
```

## Repository layout

```text
.github/workflows/      CI / binary release
docs/                   user + architecture documentation
runtime_source/         digest-pinned base runtime capsule
runtime_overlay/        digest-pinned validated runtime overlays
scripts/                build, safety and standalone smoke checks
VERSION                 next development version
```

The capsule/overlay layout is a reproducible build transport. Released users receive a single executable; target repositories do not need these files.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [BINARY_DISTRIBUTION.md](BINARY_DISTRIBUTION.md).

## CI release contract

A release binary must pass from the **built executable**, not only from Python source:

1. verified base runtime extraction;
2. verified runtime overlay application;
3. binary-safety guard;
4. source smoke;
5. one-file binary build;
6. standalone topology/impact smoke;
7. standalone portable-agent smoke;
8. standalone JS/TS/TSX/JSX simplification smoke;
9. standalone UI static analysis;
10. Chromium/CDP reproduction when available;
11. target-repository pollution checks;
12. SHA-256 verification before release publication.

Pull requests produce temporary Actions artifacts. On `main`, a final semantic version in `VERSION` publishes exactly one validated GitHub Release from the same CI run; `*-dev` versions do not publish. Tag-triggered release remains available as a fallback.

## Project policies

- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
- [Support](SUPPORT.md)
- [Changelog](CHANGELOG.md)

A repository license has not been selected by this governance change; licensing should be decided explicitly by the repository owner rather than inferred from distribution or source visibility.
