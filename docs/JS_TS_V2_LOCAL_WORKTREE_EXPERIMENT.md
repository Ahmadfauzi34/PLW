# JS/TS local candidate temporary-worktree experiment

This lane is the first mutation-bearing gate after bounded review. The mutation
authority is deliberately restricted to a disposable CI checkout of a pinned
external repository revision.

V1 exercises one reviewed Redux Toolkit candidate:

```text
candidate  sha256:c27d04409b63ff0100535ec7b9129b4c01133235e6a4f0b22b3d3fb6ba7fc6f6
rule       js_redundant_else_after_terminal
file       packages/toolkit/src/immutableStateInvariantMiddleware.ts
revision   c9dac937d77adc3bf04842a43955e81d0e7a46da
```

The workflow requires:

1. exact pinned target checkout;
2. target package-manager activation;
3. bounded dependency install;
4. focused target-native test **before** the rewrite;
5. strict byte-shape rewrite at exactly one expected site;
6. exactly one changed source path;
7. `git diff --check`;
8. the same focused target-native test after the rewrite;
9. package-native `type-tests`;
10. archived diff + hashes + validation evidence.

The experiment does **not** push to Redux Toolkit and does not create an
upstream pull request.

```text
experiment PASS
!= global behavioral equivalence
!= global regression proof
!= upstream patch authorization
```

Only local candidates with an explicit bounded review should ever enter this
lane. Ownership-sensitive deduplication and public/API wrappers remain outside
V1 mutation authority.
