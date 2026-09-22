# JS/TS V2 local-rule evidence synthesis

This checkpoint combines the mutation-bearing evidence already produced for
reviewed local simplification candidates. It is an evidence-routing layer only;
it does not change the detector and does not create a reusable rewriter.

Current evidence index:

- Redux Toolkit — `js_redundant_else_after_terminal`
- Prettier — `js_boolean_guard_return`
- Prettier — `js_terminal_expression_temporary`
- Vite — `js_boolean_guard_return`

The synthesis requires every indexed record to have:

- a pinned candidate and target revision;
- a recorded workflow artifact digest;
- baseline focused target-native validation PASS;
- post-rewrite focused target-native validation PASS;
- typecheck/type-tests PASS;
- `git diff --check` PASS;
- exactly one expected changed source file.

Rule routing:

```text
one repository with validated mutation evidence
→ SINGLE_REPOSITORY_EVIDENCE_READY
→ next: cross-repository replication

two or more independent repositories with validated candidates
→ CROSS_REPOSITORY_EVIDENCE_READY
→ next: REUSABLE_REWRITE_PROPOSAL_REVIEW
```

At the current checkpoint only `js_boolean_guard_return` satisfies the
cross-repository condition (Prettier + Vite).

Authority remains explicit:

```text
CROSS_REPOSITORY_EVIDENCE_READY
!= generic rewrite authority
!= automatic patch authority
!= global behavioral equivalence
!= upstream mutation authorization
```

The next gate for the boolean-guard rule is a bounded reusable-rewrite proposal:
a specification and proof contract, not an automatic source transformer.
