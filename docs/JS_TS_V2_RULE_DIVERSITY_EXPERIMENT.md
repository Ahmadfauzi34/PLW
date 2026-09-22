# JS/TS local rule-diversity worktree experiment

This lane extends the first Redux Toolkit worktree experiment across two other
local JS/TS simplification rules without widening mutation authority.

Pinned target:

```text
repository prettier/prettier
revision   6176846ed3c8bde9cdbdab9c1dc3294fc15d0942
```

Reviewed cases:

1. `js_boolean_guard_return` in
   `src/language-css/utilities/index.js`, validated by the SCSS map and
   trailing-comma format tests.
2. `js_terminal_expression_temporary` in
   `src/cli/find-cache-file.js`, validated by the CLI cache integration test.

Each matrix job uses its own disposable checkout and requires:

1. pinned Yarn 4.18.0 on Node 22;
2. immutable dependency install;
3. focused target-native test before mutation;
4. exact one-site source-shape match;
5. exactly one expected changed file;
6. `git diff --check`;
7. the same focused test after mutation;
8. repository typecheck;
9. archived hashes, patch, and result evidence.

Authority remains bounded:

```text
experiment PASS
!= reusable rewrite authority
!= global behavioral equivalence
!= global regression proof
!= upstream patch authorization
```

Exact-body duplication and forwarding wrappers remain outside this mutation lane.
