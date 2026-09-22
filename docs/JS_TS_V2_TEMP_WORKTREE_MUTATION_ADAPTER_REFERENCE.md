# JS/TS temp-worktree mutation adapter reference

This checkpoint implements a reference-only effectful transition for the
promoted boolean-guard planner.

It is not a product mutation API.

The adapter consumes:

- one reviewed dry-run plan;
- one read-only preflight receipt;
- one explicit single-use authorization receipt;
- one disposable-boundary receipt;
- one append-only authorization-consumption ledger.

The adapter may reach exactly one effectful state:

    TEMP_WORKTREE_APPLIED

It deliberately stops before postcondition acceptance.

## Why the adapter is separate from validation

The architecture keeps these authorities distinct:

    plan
      -> preflight
      -> authorization
      -> apply exact mutation
      -> postcondition validation
      -> evidence acceptance

A successful write is not proof that the change is correct.

Therefore the adapter does not convert a successful write into
EXPERIMENT_EVIDENCE_ACCEPTED.

## Disposable boundary

The reference adapter only accepts targets that are strict children of a
declared disposable parent under the operating system temporary directory.

For this reference implementation that means a target under the system temp
root such as /tmp on Linux.

The disposable-boundary receipt binds the resolved target path and its SHA-256.
The primary worktree flag must be false.

The following control/evidence files must remain outside the target root:

- dry-run plan;
- preflight receipt;
- authorization receipt;
- disposable-boundary receipt;
- authorization-consumption ledger;
- adapter output receipt.

## Preflight

Preflight is read-only and must already be validated.

It binds:

- repository identity;
- exact Git revision;
- source path;
- candidate ID;
- resolved target-root digest;
- plan digest;
- before/planned source hashes;
- planned diff digest.

It also records that:

- the checkout was clean;
- the checkout is disposable;
- upstream push credentials are disabled;
- source bytes matched the plan;
- the candidate span matched once;
- focused baseline validation passed.

The adapter re-checks the critical mutable facts immediately before writing.

## Authorization

Authorization must use the exact scope:

    ONE_CANDIDATE_ONE_TARGET_ONE_PLAN

The receipt must be literal authorized=true, single-use, and issued by an
authority external to the planner.

It binds:

- candidate ID;
- target repository and revision;
- source path;
- before/planned source SHA-256;
- plan digest;
- preflight-evidence digest.

Planner self-authorization is rejected.

Before the source write begins, the authorization digest is appended to the
consumption ledger as:

    CONSUMED_FOR_EXECUTION_ATTEMPT

A consumed authorization cannot be replayed, even if the disposable checkout is
reset to its original bytes.

## Exact application

Immediately before the write the adapter requires:

- clean Git status;
- exact pinned revision;
- exact before-source hash;
- exact candidate source span;
- exactly one match inside the reviewed member span;
- locally reconstructed planned source hash equal to the planner hash;
- locally reconstructed diff equal to the planner diff.

After the write it requires:

- actual after-source hash equals the planned source hash;
- actual diff equals the planned diff;
- exactly one expected changed file;
- no untracked target files;
- git diff --check passes.

No fuzzy patching is used.

## Reference suite

The reference checker creates real temporary Git repositories and exercises one
positive application plus fail-closed negative cases.

The negative suite covers:

- missing literal mutation flag;
- planner self-authorization;
- wrong plan digest;
- wrong preflight digest;
- disposable-boundary mismatch;
- disposable-parent mismatch;
- dirty checkout;
- source drift hidden from ordinary Git status;
- wildcard/rule-wide authorization;
- tampered planned diff;
- authorization replay.

Every negative case requires the adapter to leave source bytes unchanged.

The temporary roots are disposed after each case.

## Authority boundary

A passing reference suite means:

    TEMP_WORKTREE_MUTATION_ADAPTER_REFERENCE_PASSED

and the positive case may reach:

    TEMP_WORKTREE_APPLIED

It does not mean:

    postconditions validated
    experiment evidence accepted
    product mutation surface exposed
    automatic patch authority
    generic mutation authority
    upstream mutation authorization
    global behavioral equivalence

The next gate is:

    TEMP_WORKTREE_POSTCONDITION_VALIDATION_REFERENCE
