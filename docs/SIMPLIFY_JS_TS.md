# TypeScript / JavaScript simplification

PLW's current JS-family simplification frontend is `js_structural_v2`.

It is shared across:

- `.ts`
- `.tsx`
- `.js`
- `.jsx`

The frontend is intentionally conservative. It produces mechanically witnessed simplification candidates; it does not claim behavioral equivalence and it does not patch source automatically.

## Active rule families

| Rule | Candidate kind | Purpose |
| --- | --- | --- |
| Try/catch terminal return | `js_try_catch_identical_terminal_return` | Detect identical safe terminal returns that can potentially be hoisted |
| Terminal literal temporary | `js_terminal_literal_temporary` | Detect adjacent literal assignment + return |
| Direct forwarding wrapper | `js_direct_forwarding_wrapper` | Detect exact parameter forwarding to a direct identifier callee |
| Exact function-body duplication | `js_exact_function_body_duplication` | Detect conservative exact structural body duplication |
| Redundant else after terminal | `js_redundant_else_after_terminal` | Detect a braced `else` following a directly terminal branch |
| Boolean guard return | `js_boolean_guard_return` | Detect simple opposite boolean return pairs |
| Terminal expression temporary | `js_terminal_expression_temporary` | Detect adjacent terminal const temporaries for bounded non-literal expressions |

## Safety boundaries

The frontend deliberately defers or rejects cases where its structural witness is insufficient. Important examples include:

- exported/public forwarding wrappers without compatibility proof;
- async forwarding wrappers;
- destructured/default parameter forwarding;
- inferred-name-sensitive function/class/arrow temporaries;
- explicit TypeScript type-annotation temporaries;
- self-referential/TDZ temporary initializers;
- regex/division-heavy duplicate bodies;
- JSX body token equivalence;
- `else if` rewriting;
- boolean conditions containing `await` or `yield`.

A candidate means **"worth validating"**, not **"safe to edit"**.

## CLI

JSON output:

```bash
plw simplify /path/to/project --json
```

Useful fields:

```text
canonical_anatomy_bridge.semantic_frontend
canonical_anatomy_bridge.semantic_frontend_scope.ts_js_rule_count
canonical_anatomy_bridge.language_inventory
candidates[]
frontier
invariants
```

For V2, the expected frontend marker is:

```text
python_ast+js_structural_v2
```

and the TS/JS rule count is:

```text
7
```

## Authority boundary

`plw simplify` is a candidate generator.

It does not:

- mutate source;
- prove complete behavioral equivalence;
- prove an exported API can be removed;
- replace project tests/type-checks;
- treat zero candidates as universal code cleanliness.

Apply a candidate only after target-specific validation.
