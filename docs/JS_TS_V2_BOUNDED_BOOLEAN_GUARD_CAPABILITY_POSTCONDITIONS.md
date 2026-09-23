# Bounded boolean-guard capability → postcondition validation

## Purpose

This gate connects two already-qualified components without widening either one:

```text
BOUNDED_MUTATION_CAPABILITY_APPLIED
        ↓
capability/primitive identity handoff
        ↓
TEMP_WORKTREE_POSTCONDITION_VALIDATION_REFERENCE
        ↓
POSTCONDITIONS_VALIDATED
```

The bounded capability was promoted by PR #35. The postcondition reference was promoted by PR #18. The missing boundary is an exact handoff from the capability wrapper receipt to the primitive receipt consumed by the validator.

## Why a handoff is required

The capability receipt intentionally wraps the lower-level mutation receipt:

```text
capability receipt
  primitive.status
  primitive.canonical_receipt_digest
  primitive.receipt = TEMP_WORKTREE_APPLIED receipt
```

The existing postcondition validator intentionally consumes the lower-level `TEMP_WORKTREE_APPLIED` receipt directly. Passing the wrapper to that validator would fail schema validation; silently bypassing the wrapper would lose the capability-specific authorization binding.

The integration reference therefore proves both layers before validation:

1. capability receipt is `BOUNDED_MUTATION_CAPABILITY_APPLIED`;
2. capability ID and contract digest are exact;
3. no authority field has escalated;
4. embedded primitive is `TEMP_WORKTREE_APPLIED`;
5. embedded primitive canonical digest recomputes exactly;
6. primitive plan/preflight/authorization/spec digests still match live retained evidence;
7. authorization still binds the exact capability ID and contract digest;
8. only then is the primitive materialized outside the target and delegated to the existing validator.

## Containment

Any handoff rejection after mutation is fail-closed:

```text
binding/tamper failure
→ worktree discarded
→ postconditions.validated = false
→ evidence_acceptance_granted = false
```

The existing postcondition validator retains its own containment contract:

```text
POSTCONDITIONS_VALIDATED
or
MUTATION_FAILED_WORKTREE_DISCARDED
or
MUTATION_BOUNDARY_CONTAINMENT_FAILED
```

The authorization remains consumed after an effectful apply. A failed postcondition check never reopens or retries the mutation authorization.

## Authority boundary

Success means only:

```text
BOUNDED_MUTATION_CAPABILITY_POSTCONDITIONS_VALIDATED
```

It does **not** mean:

- experiment evidence accepted;
- global behavioral equivalence proven;
- automatic patch authority;
- generic mutation authority;
- primary-worktree mutation authority;
- commit/push/PR authority;
- upstream mutation authority;
- stable promotion;
- truth commit.

The next authority-separated gate remains:

```text
TEMP_WORKTREE_EXPERIMENT_EVIDENCE_ACCEPTANCE_REFERENCE
```

## Validation policy

The regression checker covers the mechanical boundary. It is not promotion authority.

Promotion requires direct interactive execution of the exact branch source and must include at least:

- positive JS handoff;
- inverse TS handoff;
- capability identity tamper;
- embedded primitive tamper;
- authority-escalation tamper;
- authorization capability-binding tamper;
- validation-spec substitution after apply;
- a command that passes before mutation but fails after mutation, proving postwrite failure discards the worktree.

CI may be used to produce a reproducible source/report bundle, but the merge verdict must come from interactive inspection/execution of that exact bundle.
