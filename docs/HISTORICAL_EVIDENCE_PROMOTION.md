# Historical Evidence Promotion

PLW's current repository state and historical development evidence serve different roles.

## Source-of-truth rule

Current `main` is canonical for the current PLW product, capability, runtime, and authority state.

Historical development archives are supporting evidence. They explain how a current checkpoint or boundary was derived, but they must not override a newer state already recorded on `main`.

## Why historical evidence is promoted selectively

The Development Full archive contains experiments, fixtures, audit logs, intermediate implementations, and retained checkpoint records. Copying the whole archive into the product repository would reintroduce ambiguity and unnecessary weight.

Promotion therefore retains only evidence that is still useful for reconstructing the lineage of current architecture.

The promoted record must preserve:

- the historical checkpoint identifier;
- historical status and complete record content;
- the exact source-file SHA-256;
- the exact source-archive SHA-256;
- an explicit statement that promotion does not grant new runtime or authority state.

## First promoted lineage: F128-F142

`qualification/history/f128_f142_proof_lineage_v1.json` retains the historical proof chain covering:

```text
F128  scenario-set validation planning
F129  scenario-bound validation evidence
F130  proof-obligation coverage
F131  witness-integrity hardening
F132  validation execution request
F133  authorization binding
F134  single-use execution lease
F135  attempt registration
F136  dispatch intent
F137  runtime dispatch/reconciliation
F138  validation-result evidence acceptance
F138.1-F138.5 agent/target/evidence routing checkpoints
F139  execution-backed scenario binding
F139.1 agent-tool communication
F140  proof-obligation re-derivation
F141  postcondition proof
F142  full-stack validated state
```

These records are historical lineage, not a promotion to F143 and not a truth commit.

## Promotion order after F128-F142

The remaining archive should be reviewed in bounded groups:

1. F106-F123 — capability lifecycle, agent accountability, authorization, lease/executor lineage.
2. F124-F127 — semantic ownership, geometry/correspondence, runtime geometry, impact projection.
3. F85-F105 — simplification economics and detector-history evidence, only where still useful for current architecture.

Raw fixture corpora and transient audit output should remain outside the product repository unless a current qualification record specifically depends on them.
