# JS/TS V2 bounded production-sample review

The economic/ownership layer narrows structural candidates, but it still does
not provide enough evidence to authorize a rewrite. This gate builds a bounded,
deterministic review pack before any patch experiment.

The pack selects three distinct review classes:

1. **Local production candidates** — up to two per observed local rule, preferring
   low-risk/small proof surfaces.
2. **Production ownership candidates** — a small, corpus-diverse set of exact-body
   duplicates where semantic ownership, binding equivalence, and neutral-owner
   placement must be reviewed.
3. **API wrapper candidates** — a small corpus-diverse control set where public
   compatibility boundaries must remain explicit.

For every selected candidate the workflow records:

- exact candidate ID and rule;
- source file/member line spans;
- bounded source excerpts with SHA-256;
- structural witness and proof surface;
- nearest and root `package.json` validation scripts;
- package-manager/config discovery;
- review questions specific to the proof surface.

Authority remains intentionally narrow:

```text
review pack != patch
discovered validation command != executed validation
source similarity != binding equivalence
production path != safe rewrite
```

The next gate is an explicit target-worktree experiment for individually reviewed
candidates, using the target repository's own tests/type-check/build surface.
