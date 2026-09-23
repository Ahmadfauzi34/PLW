# Historical Evidence Promotion

PLW's current repository state and historical development evidence serve different roles.

## Source-of-truth rule

Current `main` is canonical for the current PLW product, capability, runtime, and authority state.

Historical development archives are supporting evidence. They explain how a current checkpoint or boundary was derived, but they must not override a newer state already recorded on `main`.

## Why historical evidence is promoted selectively

The Development Full archive contains experiments, fixtures, audit logs, intermediate implementations, and retained checkpoint records. Copying the whole archive into the product repository would reintroduce ambiguity and unnecessary weight.

Promotion therefore retains only evidence that is still useful for reconstructing the lineage of current architecture.

A promoted exact record preserves:

- the historical checkpoint identifier and complete historical record bytes;
- the exact source-file SHA-256;
- the exact source-archive SHA-256 in the promotion ledger;
- the repository path and Git blob identity;
- an explicit boundary that historical retention grants no new runtime or authority state.

## F128-F142 proof lineage — exact records retained

The first priority group is now retained as **21 exact historical records** under `qualification/history/`.

`qualification/history/historical_evidence_promotion_ledger_v1.json` is the promotion index. It records the source path, source SHA-256, repository path, Git blob SHA-1, and byte-match result for every retained checkpoint.

The retained chain covers:

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
F138.1 semantic affordance / skill handoff
F138.2 target-codebase topology bootstrap
F138.3 target resolution
F138.4 evidence-need derivation
F138.5 evidence-driven capability selection
F139  execution-backed scenario binding
F139.1 agent-tool communication
F140  proof-obligation re-derivation
F141  postcondition proof
F142  full-stack validated state
```

All 21 records are marked `EXACT_RECORD_RETAINED`. The Development Full ZIP is therefore **not required for normal current work on this lineage**. It remains useful only for historical reconstruction or independent byte verification against the retained source hashes.

These records are historical lineage only. Retention does **not**:

- promote PLW to F143;
- grant mutation or execution authority;
- grant evidence-acceptance or postcondition authority beyond current `main`;
- promote stable state;
- commit truth.

## Promotion order after F128-F142

The remaining archive should be reviewed in bounded groups:

1. F106-F123 — capability lifecycle, agent accountability, authorization, lease/executor lineage.
2. F124-F127 — semantic ownership, geometry/correspondence, runtime geometry, impact projection.
3. F85-F105 — simplification economics and detector-history evidence, only where still useful for current architecture.

Raw fixture corpora and transient audit output should remain outside the product repository unless a current qualification record specifically depends on them.
