# JS/TS bounded boolean-guard mutation capability implementation

This checkpoint implements the promotion-approved mutation subset without
widening the trusted reference executor.

The internal capability ID is:

    js_boolean_guard.strict_equality_string.temp_worktree.v1

The implementation is not registered as a public PLW command.

## Composition

The implementation deliberately composes the already-audited effect primitive:

    promotion scope gate
      -> prewrite baseline revalidation
      -> existing reference mutation primitive
      -> BOUNDED_MUTATION_CAPABILITY_APPLIED

The existing reference primitive remains unchanged in authority. It still
reaches only:

    TEMP_WORKTREE_APPLIED

The outer capability receipt records the primitive receipt and its canonical
digest.

## Promotion scope

The effectful capability accepts only:

    rule        js_boolean_guard_return
    source      .js or .ts
    condition   IDENT_OR_MEMBER_CHAIN === STRING_LITERAL
    transform   positive or inverse

Optional chaining is excluded until separate evidence exists.

The implementation rejects:

- JSX and TSX;
- strict inequality;
- loose equality/inequality;
- relational conditions;
- in / instanceof;
- numeric right-hand operands;
- reversed string/identifier operands;
- comparison-operator complement folding.

For inverse transformations the exact planner output must remain:

    return !(C)

The capability may not independently normalize that expression to an inverted
comparison operator.

## Prewrite baseline revalidation

The outer capability does not trust a boolean field such as
baseline_validation_passed by itself.

Before the reference primitive is allowed to consume authorization or write
source, the capability re-runs the frozen validation-spec commands:

1. parse-after-rewrite command;
2. focused target-native command;
3. typecheck or type-tests command.

Each command:

- is an argv list;
- runs with shell=false;
- may not invoke an explicit shell executable;
- must have an existing successful baseline record in preflight;
- must exit successfully again;
- must leave the checkout clean.

If any command fails or dirties the checkout, the mutation primitive is never
entered and authorization is not consumed.

## Capability authorization binding

The existing candidate-specific authorization receipt gains two outer bindings:

    capability_id
    capability_contract_digest

The inner reference executor continues to validate the original bindings:

    candidate
    repository
    revision
    source path
    source hashes
    plan digest
    preflight digest
    validation-spec digest

This preserves the existing one-candidate / one-target / one-plan authority
boundary.

## Execution boundary

The capability remains:

- disposable-system-temp-worktree only;
- exact planner output only;
- one expected changed file only;
- no untracked target files;
- no commit;
- no push;
- no upstream pull request;
- no primary-worktree mutation.

The capability stops at:

    BOUNDED_MUTATION_CAPABILITY_APPLIED

Postcondition validation remains separate:

    TEMP_WORKTREE_POSTCONDITION_VALIDATION_REFERENCE

Evidence acceptance also remains a separate transition.

## Regression versus audit

The deterministic regression suite exists only to catch implementation drift.

It is not the authority for capability enablement.

The suite covers positive JS/TS paths plus rejected scope and prewrite failure
cases. The implementation status remains:

    IMPLEMENTED_PENDING_INTERACTIVE_VALIDATION

until the regression output is inspected and adjudicated interactively.

## Authority

Implementation does not imply:

    public PLW mutation command
    automatic patch authority
    generic mutation authority
    primary-worktree mutation
    commit / push / PR authority
    upstream mutation authority
    global behavioral equivalence
    truth

The next checkpoint after interactive implementation validation determines
whether the internal capability may move from pending to ready.
