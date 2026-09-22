# JS/TS V2 economic / ownership qualification

The structural simplifier answers a mechanical question:

> where does a conservative JS/TS simplification pattern appear?

That is intentionally different from:

> which candidate is economically worth changing?

The ownership/economic qualification layer keeps those authorities separate. It
classifies candidate paths into bounded review surfaces:

- production;
- tooling;
- test;
- fixture;
- example/playground;
- generated-like;
- docs;
- mixed;
- other.

It then derives a **review disposition**, not a truth score. Examples:

- local low/medium-risk production rules → `LOCAL_PRODUCTION_REVIEW`;
- exact-body duplication in production → `PRODUCTION_OWNERSHIP_REVIEW_REQUIRED`;
- public forwarding wrappers → `API_CONTRACT_REVIEW_REQUIRED`;
- mixed surfaces → `OWNERSHIP_BOUNDARY_REVIEW`;
- tests/examples/generated-like surfaces → `NON_PRODUCTION_CONTEXT_REVIEW`.

The classification is path-heuristic evidence only:

```text
production != safe to patch
test/example != invalid
ownership classification != semantic ownership proof
economic disposition != patch recommendation
```

The next proof gate remains bounded sample review followed by the target
repository's own tests, type-checks, and any required behavioral evidence.
