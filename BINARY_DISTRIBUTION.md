# PLW Binary Distribution

## Goal

Ship PLW as a standalone executable so an agent or target repository does not need a copy of the PLW Python source tree.

Current supported release target:

- Linux x86_64
- glibc-based runtime
- one-file PyInstaller executable
- external Chromium/Chrome only for browser-backed UI execution

## Build source model

The repository currently builds runtime source in two verified stages:

```text
digest-pinned base runtime capsule
    ↓
digest-pinned runtime overlays
    ↓
current runtime source
    ↓
source/binary safety gates
    ↓
one-file executable
```

This transport model keeps updates reproducible while the runtime source is being normalized into a cleaner long-term Git layout.

The released executable does not require the capsule or overlay files.

## Binary-safety invariants

PLW must not write mutable state next to the executable or into the target codebase by default.

Runtime state should use:

- `PLW_HOME` when explicitly configured;
- `XDG_STATE_HOME/plw`;
- `XDG_CACHE_HOME/plw`;
- user-home fallbacks such as `~/.local/state/plw` and `~/.cache/plw`.

Runtime logic must not require neighboring Python source files. Build identity/signatures should come from embedded/runtime metadata rather than reading source bytes beside the executable.

Operational resources may be embedded in the executable. An external PLW source/skills directory must not be required beside the binary.

## Browser boundary

Chromium/Chrome is not bundled.

Browser-backed commands must:

- discover an external Chromium/Chrome executable;
- fail closed if browser execution cannot be established;
- keep non-browser capabilities usable when Chromium is absent.

## Release proof

A release is accepted only when CI proves the built executable can operate from a fresh directory without the PLW source tree beside it.

Required gates include:

- verified capsule digest;
- verified overlay digest and dry-run;
- binary-safety source guard;
- standalone topology/impact;
- standalone `plw simplify` on TS/TSX/JS/JSX;
- standalone UI static analysis;
- Chromium/CDP reproduction when available;
- target repository cleanliness;
- executable SHA-256 verification.

Source tests alone are not sufficient release evidence.

## Target repository separation

A target should remain conceptually:

```text
target-project/
├─ src/
├─ project config
└─ application files
```

PLW runtime source, build fixtures, audit bundles and caches must not be copied into the target.
