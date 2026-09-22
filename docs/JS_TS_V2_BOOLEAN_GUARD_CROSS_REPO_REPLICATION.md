# JS/TS boolean-guard cross-repository replication

This lane tests whether the already-reviewed `js_boolean_guard_return` rule
generalizes beyond the first successful Prettier worktree experiment.

Pinned target:

```text
repository vitejs/vite
revision   1544bb1b7ac92f775e9d0dea97954c99cc6cbd43
candidate  sha256:d4d1da6c55c80079b4761ae51b1593c8b051e8c3ff276fb78fd6542ab2bfdef0
function   isRefIdentifier
file       packages/vite/src/node/ssr/ssrTransform.ts
```

The experiment is intentionally candidate-specific and fail-closed. It requires:

1. Node 22.12.0 and pnpm 12.4.2;
2. frozen-lockfile dependency installation;
3. focused `ssrTransform.spec.ts` validation before mutation;
4. an exact one-site boolean-guard rewrite;
5. exactly one expected changed source file;
6. `git diff --check`;
7. the same focused test after mutation;
8. `pnpm --filter vite typecheck`;
9. archived rewrite hashes, patch and result evidence.

Authority boundary:

```text
same rule PASS in Prettier + Vite
!= general rewrite authority
!= global behavioral equivalence
!= global regression proof
!= upstream patch authorization
```

The purpose is evidence replication, not mutation expansion.
