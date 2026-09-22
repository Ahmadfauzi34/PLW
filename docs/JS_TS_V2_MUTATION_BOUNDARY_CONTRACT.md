# JS/TS boolean-guard mutation boundary contract

This checkpoint defines the minimum boundary that must exist before the promoted
read-only boolean-guard planner can enter any effectful path.

It does not implement that path and does not grant source-write authority.

## Prerequisite

The contract is downstream of the retained planner-promotion artifact whose
status is:

    REUSABLE_READ_ONLY_PLANNER_READY

The review workflow re-downloads that exact GitHub Actions artifact and verifies
its GitHub-reported SHA-256 digest before evaluating this contract.

## State transition

The allowed success path is intentionally explicit:

    READ_ONLY_PLAN_READY
      -> PREFLIGHT_VALIDATED
      -> MUTATION_AUTHORIZED
      -> TEMP_WORKTREE_APPLIED
      -> POSTCONDITIONS_VALIDATED
      -> EXPERIMENT_EVIDENCE_ACCEPTED

No transition may be skipped.

## Plan binding

A future mutation adapter must consume exactly one existing
boolean-guard dry-run plan and bind all effectful behavior to that plan:

- candidate ID;
- target repository and pinned revision;
- source path;
- before-source SHA-256;
- planned-source SHA-256;
- exact planned diff;
- plan digest.

Fuzzy or opportunistic patch application is outside the contract.

## Preflight

Preflight remains read-only and must establish all of the following before any
write can be authorized:

- the checkout is disposable and clean;
- the target revision is pinned;
- push credentials are disabled;
- current source bytes match the plan's before hash;
- the reviewed candidate span still matches exactly once;
- the focused target-native baseline validation runs and passes;
- the preflight evidence is digested.

## Authorization separation

The planner may never authorize its own output.

Authorization must be explicit, literal, external to the planner, single-use,
and scoped to one candidate, one target and one exact plan.

The authorization receipt must bind:

- candidate ID;
- target repository and revision;
- source path;
- before/planned source hashes;
- plan digest;
- preflight evidence digest.

Wildcard and rule-wide authorization are forbidden.

## Effect boundary

Even after authorization, writes are constrained to a disposable temporary
worktree.

The future adapter must:

- reject the primary worktree;
- re-check the before-source hash immediately before writing;
- re-check the candidate span immediately before writing;
- apply only the exact planned replacement;
- change exactly one expected file;
- require the actual after hash to equal the planned after hash;
- require the actual diff to equal the planned diff;
- run git diff --check;
- reject unexpected changed or untracked target files.

Commit creation, push, and pull-request creation remain forbidden.

Evidence output must remain outside the target root.

## Postconditions

A mutation attempt cannot become successful merely because the write completed.

It must also satisfy:

- parse-after-rewrite validation;
- the same focused target-native validation used at baseline;
- target typecheck or type-tests;
- exact one-file change scope;
- planned/actual source-hash equality;
- planned/actual diff equality.

Passing these postconditions still does not prove global behavioral equivalence.

## Failure containment

Any failure after an execution attempt is fail-closed.

The authorization receipt is consumed once execution begins. Retrying requires
a fresh plan and fresh authorization.

The containment strategy is:

    DISCARD_DISPOSABLE_WORKTREE

The system must record that disposal/rollback completed and that the upstream
repository remained untouched. A containment failure is a distinct terminal
state and can never be promoted as partial success.

## Evidence closure

A future execution receipt must record at least:

- target repository and revision;
- candidate ID;
- plan digest;
- authorization-receipt digest;
- preflight-evidence digest;
- before and after source SHA-256;
- planned and actual diff digests;
- validation commands and results;
- changed-path scope;
- authorization-consumption state;
- rollback/disposal state.

The receipt is append-only and stored outside the target root.

## Authority boundary

A passing contract review means only:

    MUTATION_BOUNDARY_CONTRACT_REVIEW_PASSED

It does not mean:

    source mutation authority
    automatic patch authority
    generic mutation authority
    upstream mutation authorization
    global behavioral equivalence

The next gate is:

    TEMP_WORKTREE_MUTATION_ADAPTER_REFERENCE

That future gate may implement a reference adapter only within this contract.
It must not widen the authority defined here.
