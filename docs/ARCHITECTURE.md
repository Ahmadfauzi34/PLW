# PLW architecture

PLW separates codebase discovery, structural reasoning, runtime evidence, and distribution.

## Runtime layers

```text
target codebase
    ↓
SharedGraph / source inventory
    ↓
domain analyzers
    ├─ topology / impact
    ├─ simplify
    ├─ UI geometry/correspondence
    └─ runtime reproduction
    ↓
bounded evidence / candidate output
```

The analyzers do not gain authority merely because they share a graph.

Examples:

```text
Topology ≠ Geometry
Geometry ≠ Correspondence
Correspondence ≠ Behavior
Candidate ≠ Patch
Runtime reproduction ≠ Root-cause proof
```

## Distribution repository

This repository currently uses a verified base runtime capsule plus verified runtime overlays.

```text
runtime_source/plw-runtime-src.tar.gz
    ↓ SHA-256 verification
base runtime source
    ↓
runtime_overlay/*
    ↓ overlay SHA-256 + patch dry-run
current runtime source
    ↓
binary-safety checks
    ↓
PyInstaller one-file build
    ↓
standalone binary smoke tests
```

The released executable does not need the capsule or overlay files at runtime.

## Runtime state

Mutable state and cache must remain outside the analyzed target by default:

```text
PLW_HOME
XDG_STATE_HOME/plw
XDG_CACHE_HOME/plw
~/.local/state/plw
~/.cache/plw
```

## Browser-backed commands

Chromium/Chrome is an external optional runtime dependency. Browser-backed commands must fail closed when execution cannot be established. Chromium is not bundled into the PLW executable.

## Source normalization

The capsule/overlay layout is a reproducible bootstrap transport. A future repository-maintenance milestone may normalize the runtime into ordinary browsable Git source files, but that change must preserve the same binary and validation contracts.
