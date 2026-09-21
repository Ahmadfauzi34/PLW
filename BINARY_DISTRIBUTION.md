# PLW Binary Distribution V1

## Goal

Ship PLW as a standalone executable so an agent or target repository does not need a copy of the PLW source tree.

The first supported release target is Linux x86_64 as a one-file `plw` executable. Chromium/Chrome remains an external optional runtime dependency for browser-backed UI commands.

## Separation

The release binary must not carry development-only material such as historical audit bundles, experimental checkpoint manifests, fixture corpora, reference-check scripts, transient SQLite databases, or graph/retrieval caches.

## Binary-safety invariants

PLW must not write mutable state next to the executable or into the target codebase by default. Runtime state should use `PLW_HOME`, XDG state/cache locations, or user-home fallbacks.

Runtime logic must not require neighboring Python source files. Build identity/signatures should come from embedded build metadata rather than hashing `.py` files at runtime.

Operational skill resources may be embedded in the executable; an external `skills/` directory must not be required.

Browser absence must degrade browser-backed UI capabilities explicitly and must not break topology, impact, static UI-map analysis, or other non-browser functions.

## Release proof

A release is accepted only if CI builds the binary, copies only that executable into a fresh directory, analyzes a fixture repository without PLW source present, confirms the target repository is not polluted with PLW state/cache, and publishes the binary plus SHA-256.

Source tests alone are not sufficient evidence that the standalone binary works.
