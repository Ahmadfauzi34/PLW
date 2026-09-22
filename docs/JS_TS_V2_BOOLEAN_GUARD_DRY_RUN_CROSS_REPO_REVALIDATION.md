# JS/TS boolean-guard dry-run cross-repository revalidation

This gate runs the merged read-only boolean-guard planner against the same real
repositories that established the mutation evidence: Prettier and Vite.

The planner does not receive hand-authored candidates. Each job first downloads
the exact PLW v0.2.0 release binary, verifies its published SHA-256, and runs a
fresh `plw simplify --json` scan on the pinned target revision. The reviewed
candidate must be reproduced with the same candidate ID before planning.

Pinned targets:

```text
prettier/prettier
6176846ed3c8bde9cdbdab9c1dc3294fc15d0942

vitejs/vite
1544bb1b7ac92f775e9d0dea97954c99cc6cbd43
```

For each repository the gate proves:

1. the target checkout is clean before PLW observation;
2. PLW v0.2.0 reproduces the exact reviewed candidate;
3. the dry-run planner accepts that real candidate witness;
4. the expected bounded transformation is generated;
5. source SHA-256 before and after planning is identical;
6. `git status --porcelain --untracked-files=all` stays empty;
7. no generic rewrite, automatic patch, or upstream mutation authority is
   granted.

The relation to the earlier mutation experiments is intentionally different for
the two repositories:

- **Prettier:** the bounded planner produces the exact rewrite that was already
  validated in the temporary worktree.
- **Vite:** the planner deliberately produces
  `return !(id.name === 'arguments')`, while the earlier experiment used
  `return id.name !== 'arguments'`. The difference is expected because
  comparison-operator complement folding remains outside planner V1 authority.

Thus a successful gate proves reusable *planning* generalization, not reusable
mutation authority.

```text
DRY_RUN_PLANNER_CROSS_REPOSITORY_REVALIDATED
!= generic source rewriter
!= automatic patch
!= upstream mutation authorization
```

Next gate: `DRY_RUN_PLANNER_EVIDENCE_SYNTHESIS`.
