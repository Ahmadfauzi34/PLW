## Goal

Describe the bounded behavior or repository change this PR introduces.

## Authority boundary

What does this change prove, and what does it explicitly **not** prove?

Check every authority-bearing surface this PR changes:

- [ ] read-only observation
- [ ] local runtime execution
- [ ] temporary/disposable mutation for validation
- [ ] source mutation proposal
- [ ] external repository mutation
- [ ] stable promotion / release behavior
- [ ] no authority change

## Evidence / validation

List the exact checks run. Include standalone-binary evidence when runtime behavior changes.

- [ ] focused source/reference tests
- [ ] binary-safety guard
- [ ] standalone topology / impact smoke
- [ ] standalone portable-agent smoke
- [ ] standalone JS/TS simplification smoke where relevant
- [ ] browser-backed validation where relevant
- [ ] target repository remains unpolluted

```text
<commands / CI runs / reference checks>
```

## Simplification changes

If this PR adds or modifies a simplification rule:

- [ ] mechanical witness documented
- [ ] positive fixture covered
- [ ] negative/ambiguous fixture covered
- [ ] public/API compatibility boundary considered
- [ ] economic/ownership surface considered where relevant
- [ ] candidate remains non-mutating by default

## Standalone distribution impact

- [ ] standalone binary behavior is unchanged
- [ ] standalone binary behavior changed and has binary-level smoke coverage
- [ ] not applicable (documentation/governance only)

If changed, describe fresh-HOME / source-tree-independent validation.

## Release impact

- [ ] ordinary development (`VERSION` remains `*-dev`)
- [ ] release candidate / version finalization
- [ ] no release impact

State whether this changes runtime source, binary output, documentation only, or release workflow.

## Unsupported / deferred cases

List known boundaries, ambiguous cases, or follow-up work that this PR intentionally does not solve.
