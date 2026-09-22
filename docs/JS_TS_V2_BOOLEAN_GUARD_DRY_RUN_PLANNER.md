# JS/TS boolean-guard dry-run rewrite planner

This checkpoint implements the first reusable planning surface for the reviewed
`js_boolean_guard_return` proposal. The planner is deliberately read-only.

Input:

- a target root;
- one PLW boolean-guard candidate with its semantic witness;
- one exact candidate member/file span.

Output:

- the exact bounded source match;
- the proposed replacement;
- before/planned SHA-256 values;
- a unified diff;
- validation obligations for any future mutation-bearing gate.

The planner re-reads the target file after planning and requires the source hash
to remain unchanged.

## Bounded syntax

V1 only plans candidates whose condition is already proven boolean by a narrow
source grammar:

- equality/comparison binary expressions;
- `in` and `instanceof`;
- unary `!`.

It fails closed on:

- logical `&&`, `||`, or `??` direct-return conditions;
- conditions containing `await` or `yield`;
- non-boolean conditions such as `if (value)`;
- comments inside the rewrite span;
- mixed semicolon style across terminal returns;
- semantic-witness/source polarity mismatch;
- multiple candidate-shaped matches inside one member span;
- missing or escaping source paths.

## Planned transformations

Positive:

```text
if (C) {
  return true;
}

return false;

→ dry-run plan →

return C;
```

Inverse:

```text
if (C) {
  return false
}

return true

→ dry-run plan →

return !(C)
```

Comparison-operator complement folding remains outside V1. The planner does not
turn `!(a === b)` into `a !== b`.

## Authority

```text
DRY_RUN_REWRITE_PLAN_READY
!= source mutation
!= reusable mutation authority
!= automatic patch
!= upstream authorization
```

The next gate is
`DRY_RUN_PLANNER_CROSS_REPOSITORY_REVALIDATION`: run the planner against the
same pinned Prettier and Vite candidates that established the proposal evidence,
while proving both target checkouts remain byte-for-byte unmodified.
