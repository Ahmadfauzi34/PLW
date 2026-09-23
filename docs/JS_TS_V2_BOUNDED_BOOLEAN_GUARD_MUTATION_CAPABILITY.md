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

## Interactive implementation validation

CI and the deterministic regression suite are regression/build signals only.
They are not the enablement authority.

The exact PR #26 implementation source was packaged from workflow run
`35874207271` and audited directly outside CI:

    source head       ab8415379b8771d5b80b4ddeef5646123d2723a6
    source artifact   10755986435
    artifact sha256   sha256:122d441cd90c80e34dfe6bafba178f71c825378f49212fcdd149a8bfb73e59ce
    regression        16 / 16 PASS
    interactive       11 / 11 PASS
    READY transition   2 / 2 PASS

The interactive walk verified:

- literal bounded-mutation opt-in remains mandatory;
- JS positive and TS inverse transforms stay inside the approved syntax scope;
- inverse rewriting remains `return !(C)` rather than operator-complement folding;
- TSX and out-of-scope forms fail closed before authorization consumption;
- pre-existing dirty checkout, baseline failure, shell execution, and validation
  commands that dirty the checkout fail closed before authorization consumption;
- exact replay of a consumed authorization is rejected after the disposable
  target is reset clean;
- successful application stops before postcondition validation and evidence
  acceptance.

The implementation status is therefore:

    BOUNDED_MUTATION_CAPABILITY_READY

This READY state means only that the approved internal bounded effectful
capability passed its implementation-validation gate. It does not expose a
public mutation command or grant broader mutation authority.

## Authority

READY does not imply:

    public PLW mutation command
    automatic patch authority
    generic mutation authority
    primary-worktree mutation
    commit / push / PR authority
    upstream mutation authority
    postcondition acceptance authority
    evidence acceptance authority
    global behavioral equivalence
    truth

The next proof gate remains:

    TEMP_WORKTREE_POSTCONDITION_VALIDATION_REFERENCE
