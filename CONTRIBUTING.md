# Contributing to PLW

PLW changes should preserve conservative authority boundaries and standalone distribution behavior.

## Development expectations

Before proposing a runtime change:

1. keep target repositories read-only unless a command explicitly declares mutation authority;
2. add focused positive and negative tests for new analyzers;
3. preserve fail-closed behavior for ambiguous syntax/evidence;
4. run the relevant source reference checks;
5. ensure the standalone binary can run without the PLW source tree beside it;
6. do not write PLW cache/state into the analyzed target.

## Simplification rules

A new simplification rule should provide:

- a mechanical witness;
- explicit exclusions for known ambiguous constructs;
- a bounded recommendation/adjudication path;
- positive fixtures;
- negative fixtures;
- a statement of what the rule does **not** prove.

A candidate is not permission to edit source automatically.

## Runtime overlays

While the repository uses the capsule/overlay bootstrap:

- overlays must be digest-pinned;
- patch application must dry-run successfully;
- overlays must apply to the verified base capsule only;
- every runtime overlay must have binary-level smoke coverage.

## Pull requests

Keep PRs scoped. Include:

- the behavior being added or changed;
- authority/boundary implications;
- tests run;
- standalone binary impact;
- known unsupported cases.
