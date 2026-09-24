# PLW agent entrypoint

PLW is a standalone codebase reference machine for software agents.

For an unfamiliar target repository, do not begin by guessing a PLW command from task wording. Use the target-first entrypoint:

```bash
plw doctor /path/to/repo
plw agent orient /path/to/repo --task "<task>" --json
```

In doctor output, `ready` covers the portable interface and target root;
`readiness.stable_target_topology_ready` is a separate source support check.
In `plw work`, `work_status: ready` describes the reference pack only. The
`readiness.action` and `readiness.task_postcondition` fields must be read before
any action or outcome claim. `plw --version` reports the embedded build version.

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
