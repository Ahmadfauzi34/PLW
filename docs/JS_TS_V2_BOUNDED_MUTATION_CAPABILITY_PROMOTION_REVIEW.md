# JS/TS boolean-guard bounded mutation capability promotion review

This checkpoint reviews whether the sealed accepted mutation evidence is strong
enough to authorize implementation of a reusable effectful capability.

It does not itself enable that capability.

## Interactive-first review

The promotion scope was reviewed interactively after the retained sealed ledger
reached:

    accepted records = 2
    repositories = 2
    candidates = 2

The two accepted experiments cover:

    Prettier
      .js
      positive transform
      semicolon style
      condition family: IDENT === STRING

    Vite
      .ts
      inverse transform
      no-semicolon style
      condition family: IDENT === STRING

Both use:

    BOUNDED_POSTCONDITION_VALIDATION_EVIDENCE

and both retain:

    truth_commit = false

CI is not the authority for this promotion review.

## Why the full planner allowlist is not promoted

The read-only planner can prove a wider bounded syntax allowlist, including
operators such as:

    !==
    ==
    !=
    <
    >
    <=
    >=
    in
    instanceof

That does not mean the mutation capability has equivalent sealed mutation
evidence for those forms.

The sealed accepted experiments currently share:

    operator = ===
    left operand = identifier/member chain
    right operand = string literal

Therefore promotion of the full planner allowlist would be an evidence-class
jump.

The mutation capability must be narrower than the read-only planner until more
sealed evidence exists.

## Approved implementation scope

The promotion review approves implementation of:

    js_boolean_guard.strict_equality_string.temp_worktree.v1

Bounded applicability:

    rule              js_boolean_guard_return
    source extension  .js or .ts
    left operand      identifier or member chain
    operator          ===
    right operand     string literal
    transformation    positive or inverse

Positive form:

    if (C) return true
    return false

may become:

    return C

Inverse form:

    if (C) return false
    return true

may become:

    return !(C)

The capability must preserve the planner-produced text exactly.

Comparison-operator complement folding remains excluded. For example:

    return !(x === "value")

must not independently become:

    return x !== "value"

without a separate authority/evidence review.

## Mandatory execution boundary

Any future implementation must retain the existing separation:

    read-only plan
      -> preflight
      -> explicit candidate-specific authorization
      -> disposable worktree apply
      -> postcondition validation
      -> evidence acceptance

Required invariants:

- system-temp disposable worktree only;
- primary worktree forbidden;
- exact one-site planner output only;
- plan digest bound;
- preflight digest bound;
- validation-spec digest bound;
- external single-use authorization;
- no planner self-authorization;
- all postcondition commands proven runnable on baseline before write;
- exact after-source hash;
- exact planned diff;
- one expected changed file;
- no untracked target files;
- failure-after-write disposes the worktree;
- postcondition validation remains a separate transition;
- evidence acceptance remains a separate transition.

## Explicitly rejected scopes

This review does not approve:

    all seven JS/TS simplification rules
    full boolean-guard operator allowlist
    JSX mutation
    TSX mutation
    != / !== / relational / in / instanceof mutation authority
    comparison-operator complement folding
    primary-worktree mutation
    unattended automatic patching
    commit creation
    push
    upstream pull-request creation
    generic mutation authority

## Interactive scope audit

Ten promotion-scope cases were checked:

| Case | Result |
| --- | --- |
| Prettier positive JS strict equality | PASS |
| Vite inverse TS strict equality | PASS |
| new JS strict-equality/string candidate | implementation scope only |
| strict inequality | rejected |
| relational operator | rejected |
| TSX source | rejected |
| primary worktree | rejected |
| automatic/upstream patch | rejected |
| operator complement folding | rejected |
| missing baseline qualification | rejected |

Result:

    INTERACTIVE_BOUNDED_MUTATION_CAPABILITY_PROMOTION_AUDIT_PASSED
    10 / 10

## Promotion result

The review result is:

    BOUNDED_MUTATION_CAPABILITY_PROMOTION_APPROVED_FOR_IMPLEMENTATION

This means:

    implementation_authorized_for_approved_scope = true

It does not mean:

    runtime_mutation_capability_enabled = true
    automatic_patch_authority_granted = true
    generic_mutation_authority_granted = true
    upstream_mutation_authorized = true
    global behavioral equivalence proven = true
    truth committed = true

The next gate is:

    BOUNDED_BOOLEAN_GUARD_MUTATION_CAPABILITY_IMPLEMENTATION
