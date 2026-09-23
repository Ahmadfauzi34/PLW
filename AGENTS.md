# PLW agent entrypoint

PLW is a standalone codebase reference machine for software agents.

For an unfamiliar target repository, do not begin by guessing a PLW command from task wording. Use the target-first entrypoint:

```bash
plw doctor /path/to/repo
plw agent orient /path/to/repo --task "<task>" --json
```

The orientation order is:

```text
target topology
→ target resolution
→ evidence-need derivation
→ capability candidates
→ exact skill handoff
```

When a capability is justified, inspect its contract and embedded skill directly from the binary:

```bash
plw capability describe <command> --json
plw skill show <command> --json
```

Authority boundaries are strict:

```text
candidate ≠ patch
topology ≠ causality
geometry ≠ behavior
runtime reproduction ≠ root-cause proof
orientation ≠ execution authority
```

Portable-agent discovery commands are read-only with respect to target source. Any effectful validation or mutation path has its own explicit authorization and proof boundaries.
