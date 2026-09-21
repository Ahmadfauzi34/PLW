# Repository maintenance

This repository has two audiences:

1. users who download a standalone PLW binary;
2. maintainers who reproduce and validate that binary.

## Current build-source layout

```text
runtime_source/
    verified base capsule

runtime_overlay/
    small verified runtime deltas

scripts/
    extraction, overlay, build and standalone validation

.github/workflows/
    CI and tagged release publication
```

The base capsule is intentionally immutable for a given baseline. Runtime overlays are deterministic deltas and are verified before application.

## Why overlays are chunked

The current GitHub bootstrap path may transport a runtime overlay as ordered Base64 chunks. CI reconstructs the patch, verifies its SHA-256, performs a patch dry-run, and only then applies it to the verified base source.

Chunking is a repository transport detail; it is not part of PLW runtime behavior.

## Long-term cleanup

A future maintenance-only milestone should normalize the validated runtime into ordinary source files tracked directly by Git while preserving:

- the same CLI behavior;
- the same binary-safety invariants;
- the same standalone smoke tests;
- reproducible release assets.

That normalization should be reviewed separately from analyzer feature changes.
