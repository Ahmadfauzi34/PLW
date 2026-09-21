# PLW

Proof Lattice Workbench (PLW) is a codebase reference-machine and agent tooling project.

This repository is the clean build/distribution surface for PLW. Development audits, historical checkpoint fixtures, and transient runtime databases are intentionally excluded from the runtime distribution.

## Primary distribution

The primary release target is a single Linux x86_64 executable:

```text
plw-linux-x86_64
```

A target repository does **not** need a copy of the PLW Python source tree.

Example installation:

```bash
chmod +x plw-linux-x86_64
sudo install plw-linux-x86_64 /usr/local/bin/plw
```

Then PLW can analyze an unrelated codebase directly:

```bash
plw topology /path/to/project --json
plw impact src/example.ts /path/to/project --json
```

UI workflows remain available from the same executable:

```bash
plw ui map snapshot.json /path/to/project --json
plw ui diagnose candidate.json --baseline baseline.json --root /path/to/project --json
```

## Runtime state

PLW does not intentionally place mutable runtime state in the target codebase.

Runtime state/cache resolve through:

- `PLW_HOME` / explicit PLW state overrides when configured;
- `XDG_STATE_HOME/plw`;
- `XDG_CACHE_HOME/plw`;
- Linux user-home fallbacks such as `~/.local/state/plw` and `~/.cache/plw`.

## Browser-backed UI commands

Static topology, impact, UI mapping, diffing, and bug analysis do not require an embedded browser.

Commands that execute a rendered UI scenario—such as targeted reproduction, causal isolation, and post-fix verification—use an externally installed Chromium/Chrome executable. Chromium is intentionally **not** bundled into the PLW binary.

## Supported binary target

Binary Distribution V1 currently targets:

- Linux x86_64
- glibc-based runtime
- one-file PyInstaller executable

Additional OS/architecture targets can be added after the Linux release contract is stable.

## CI release contract

Every binary build must pass, from the built executable rather than just source:

1. verified runtime-source capsule extraction;
2. binary-safety guard;
3. source smoke;
4. one-file executable build;
5. standalone topology/impact smoke from a fresh directory;
6. standalone UI mapping/diagnosis smoke;
7. browser-backed UI reproduction when Chromium is available on the runner;
8. target-repository pollution check.

Pull requests publish a GitHub Actions artifact. A version tag matching `v*` publishes the already-validated executable and its SHA-256 file to GitHub Releases.

See [BINARY_DISTRIBUTION.md](BINARY_DISTRIBUTION.md) for the distribution invariants.
