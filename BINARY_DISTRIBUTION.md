# PLW Binary Distribution

## Goal

Ship PLW as a standalone executable so an agent or target repository does not need a copy of the PLW Python source tree.

Current supported release target:

- Linux x86_64
- glibc-based runtime
- baseline GLIBC 2.17 on Linux x86_64, subject to the required runtime compatibility gate
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
- portable capsule extraction without archive-owner `chown`;
- binary-safety source guard;
- standalone topology/impact;
- standalone `plw simplify` on TS/TSX/JS/JSX;
- standalone UI static analysis;
- reference argv round-trip and dirty Git-visible content binding from the
  built executable;
- required Chromium/CDP proof and a pinned Vite target-first agent workflow in
  separate jobs consuming the exact built artifact;
- target repository cleanliness;
- executable SHA-256 verification.
- ELF bootloader GLIBC symbol ceiling at 2.17, plus actual execution of the
  same artifact on GLIBC 2.17 (CentOS 7) and GLIBC 2.31 (Ubuntu 20.04).

The CI build runs PyInstaller with shared CPython 3.13 in a `manylinux2014`
container. The host runner only executes tests and uploads artifacts. The
ELF symbol check covers the one-file bootloader; actual older-GLIBC execution
also checks the extracted Python and bundled libraries. This is a Linux
x86_64 glibc baseline, not a promise for musl/Alpine, other CPU architectures,
or arbitrary external Chromium/Chrome builds.

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


## Version publication

`VERSION` is the canonical release intent:

- values ending in `-dev` are development builds and never publish from a main push;
- a final semantic version such as `0.2.0` may publish `v0.2.0` only after the main standalone binary job succeeds;
- if that release already exists, CI refuses to replace its published assets.

This keeps release assets tied to one validated main commit while retaining tag-triggered publication as a fallback.
