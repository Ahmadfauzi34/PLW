# JS/TS temp-worktree postcondition validation reference

This checkpoint validates an already-applied boolean-guard mutation inside a
disposable worktree.

It starts from:

    TEMP_WORKTREE_APPLIED

and may produce only one of these terminal outcomes:

    POSTCONDITIONS_VALIDATED
    MUTATION_FAILED_WORKTREE_DISCARDED
    MUTATION_BOUNDARY_CONTAINMENT_FAILED

A successful validation does not accept experiment evidence and does not grant
upstream mutation authority.

## Interactive-first audit policy

This checkpoint was audited interactively before CI integration.

The audit was run directly against real temporary Git repositories and exercised
both success and failure-after-write behavior.

CI is not the audit authority for this checkpoint.

CI may later be used only as a deterministic regression guard for:

- syntax;
- build compatibility;
- fixture regression;
- invariant drift.

The architectural decision and failure interpretation remain interactive.

## Frozen validation spec

The postcondition-validation commands must be selected and digested before the
source mutation is authorized.

The spec schema is:

    plw-js-ts-v2-postcondition-validation-spec-v1

The same digest must be carried by:

    preflight
      -> authorization
      -> mutation receipt
      -> postcondition validator

This prevents command substitution after the source has already changed.

The focused post-mutation command must exactly equal the focused baseline argv
recorded by preflight.

Validation commands are argv arrays and run with shell=false.

Explicit shell executables are rejected by the reference validator.

## Validation order

The reference validator executes:

1. parse-after-rewrite validation;
2. the exact focused target-native baseline command again;
3. target typecheck or target type-tests.

Before running commands it revalidates:

- pinned Git revision;
- exact candidate/source binding;
- exact plan/preflight/authorization/spec digests;
- exact post-mutation source SHA-256;
- exact dry-run diff;
- exactly one expected changed file;
- no untracked target files;
- git diff --check.

After each validation command it rechecks that the validation process itself did
not mutate the target source, widen changed-path scope, or create untracked target
files.

## Success path

If all postconditions pass:

    TEMP_WORKTREE_APPLIED
      -> POSTCONDITIONS_VALIDATED

The receipt records:

- exact validation argv;
- exit codes;
- stdout/stderr SHA-256;
- source SHA-256 before disposal;
- diff SHA-256 before disposal;
- authorization-consumed state;
- worktree-disposal state.

The disposable worktree is then removed.

The validator explicitly records:

    evidence_acceptance_granted = false

The next authority boundary is:

    TEMP_WORKTREE_EXPERIMENT_EVIDENCE_ACCEPTANCE_REFERENCE

## Failure after write

A failed source write is handled by the adapter boundary.

This checkpoint covers failures after a successful write.

Examples include:

- focused validation failure;
- typecheck/type-test failure;
- validation-spec tampering;
- focused-command substitution;
- validation command mutating the checkout.

Any such failure must become:

    MUTATION_FAILED_WORKTREE_DISCARDED

There is no partial-success state.

Authorization remains consumed because an execution attempt already occurred.
Retry therefore requires a fresh plan, fresh preflight, and fresh authorization.

The disposable worktree must be absent after containment.

If the worktree cannot be removed, the terminal state is:

    MUTATION_BOUNDARY_CONTAINMENT_FAILED

That state can never be promoted to success.

## Interactive audit result

The initial interactive audit used Node 22.16.0, TypeScript 5.8.3, Git 2.47.3
and Python 3.13.5.

Five cases were exercised:

| Case | Expected | Observed |
| --- | --- | --- |
| valid mutation + validations | POSTCONDITIONS_VALIDATED | PASS |
| focused validation fails | MUTATION_FAILED_WORKTREE_DISCARDED | PASS |
| typecheck fails | MUTATION_FAILED_WORKTREE_DISCARDED | PASS |
| validation spec is tampered | MUTATION_FAILED_WORKTREE_DISCARDED | PASS |
| focused command is substituted | MUTATION_FAILED_WORKTREE_DISCARDED | PASS |

For every case:

- authorization remained consumed;
- the disposable worktree was removed;
- the synthetic bare upstream remained unchanged.

Audit artifact SHA-256:

    4014a5a06b2d94b3000a25c8ad77f2e2ffb16bd335a194fd38a889625d43e4b2

## Authority boundary

A successful reference validation means only:

    POSTCONDITIONS_VALIDATED

It does not mean:

    experiment evidence accepted
    global behavioral equivalence proven
    product mutation API enabled
    automatic patch authority granted
    generic mutation authority granted
    upstream mutation authorized
    truth committed
