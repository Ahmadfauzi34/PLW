# JS/TS boolean-guard planner evidence synthesis

This checkpoint decides whether the reviewed boolean-guard planner can be
promoted from experiment/revalidation state into a reusable **read-only**
planning capability.

The workflow verifies the actual retained GitHub Actions evidence chain:

1. bounded rewrite proposal review;
2. synthetic dry-run planner reference suite;
3. real Prettier dry-run revalidation;
4. real Vite dry-run revalidation;
5. cross-repository aggregate revalidation.

Every artifact is bound by workflow run ID, artifact name, and the SHA-256 digest
reported by GitHub. The synthesis job downloads those artifacts again and
requires the live artifact digest to match the committed evidence index before
reading their reports.

Promotion requires:

- proposal review ready with two validated repositories/candidates;
- positive and inverse planner reference coverage;
- at least seven fail-closed negative planner cases;
- fresh PLW candidate reproduction on Prettier and Vite;
- ready dry-run plans on both repositories;
- identical target source hashes before and after planning;
- zero target source mutation;
- preserved authority boundaries on every evidence layer.

A successful synthesis may grant exactly one new capability state:

```text
REUSABLE_READ_ONLY_PLANNER_READY
```

Within that state PLW may generate a bounded plan and diff for
`js_boolean_guard_return` candidates satisfying the reviewed applicability
contract.

It still may not write source:

```text
reusable read-only planning authority
!= source mutation authority
!= automatic patch authority
!= upstream mutation authorization
!= global behavioral equivalence
```

The next gate is `MUTATION_BOUNDARY_CONTRACT_REVIEW`: specify the authorization,
temporary-worktree, validation, rollback, and evidence requirements that would
be necessary before any reusable planner output could enter an effectful path.
