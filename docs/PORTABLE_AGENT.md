# Portable Agent Surface

PLW's official distribution target is a single standalone executable.

After release download and checksum verification:

```bash
chmod +x plw-linux-x86_64
./plw-linux-x86_64 doctor /path/to/repo
./plw-linux-x86_64 agent orient /path/to/repo --task "<task>" --json
```

No Python environment, PLW source checkout, runtime capsule, overlay directory, or neighboring skill directory is required by the released executable.

## Embedded contract

The binary carries:

- the PLW runtime/reference machine;
- the semantic capability registry;
- exact version-aligned skill modules;
- the portable-agent readiness doctor;
- the target-first agent orientation entrypoint;
- build/version metadata.

`plw doctor` treats Chromium as optional: static capabilities remain ready when no browser is installed. Browser-backed commands still fail closed when their runtime dependency is unavailable.

## Acceptance gate

A binary is portable-agent ready only if CI proves, from a fresh HOME and a copied standalone executable:

1. `plw doctor` reports `ready=true`;
2. embedded version matches repository `VERSION`;
3. capability registry is available;
4. every referenced skill handoff is embedded;
5. `plw skill show topology` works without external files;
6. `plw agent orient` returns the portable orientation contract;
7. no portable-agent command grants execution/mutation/truth authority;
8. the target fixture remains file-clean.

The existing topology, impact, simplification, UI and browser smokes remain independent release gates.
