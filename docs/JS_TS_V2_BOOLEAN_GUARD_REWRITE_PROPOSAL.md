# JS/TS boolean-guard reusable-rewrite proposal

This checkpoint turns the cross-repository evidence for
`js_boolean_guard_return` into a bounded rewrite proposal. It does not implement
or authorize a generic source rewriter.

Evidence basis:

```text
prettier/prettier
  js_boolean_guard_return
  bounded worktree validation PASS

vitejs/vite
  js_boolean_guard_return
  cross-repository replication PASS
```

The proposal is intentionally narrower than the structural detector.

## Admissible shape

Only terminal boolean-return pairs are in scope:

```text
if (C) return true;
return false;
```

or:

```text
if (C) return false;
return true;
```

The condition `C` must be syntactically proven to yield a boolean. V1 allows
comparison/equality operators and unary `!`; logical expressions are not
treated as directly boolean because JavaScript logical operators can return
non-boolean operands.

## Bounded transformations

Positive:

```text
if (C) return true;
return false;

→

return C;
```

Inverse:

```text
if (C) return false;
return true;

→

return !(C);
```

V1 deliberately does not fold comparison operators such as `=== → !==`.
That algebraic transformation is a separate authority even though the Vite
candidate experiment used such a stronger simplification.

## Fail-closed source conditions

The proposal rejects a candidate when:

- comments inside the rewrite span could move or disappear;
- the condition contains `await` or `yield`;
- the condition cannot be proven boolean by the bounded syntax allowlist;
- the terminal returns are not exact opposite boolean literals;
- the rewrite would introduce a binding;
- the rewrite would reorder side effects;
- the candidate span is not exact and unique.

Source style such as semicolons, line endings, and outer indentation must be
preserved.

## Validation contract

A future implementation must begin as a dry-run planner. Any mutation-bearing
experiment still requires candidate-specific authorization plus:

1. exact rewrite span;
2. parse success after rewrite;
3. exactly one expected changed file;
4. `git diff --check`;
5. focused target-native validation before mutation;
6. the same focused validation after mutation;
7. target typecheck or type-tests after mutation.

Authority remains:

```text
proposal review ready
!= reusable rewriter implemented
!= generic rewrite authority
!= automatic patch authority
!= upstream mutation authorization
```

Next gate: `DRY_RUN_REWRITE_PLANNER`.
