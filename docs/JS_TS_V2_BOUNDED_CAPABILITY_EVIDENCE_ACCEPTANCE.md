# Bounded capability evidence-acceptance integration

## Purpose

The bounded boolean-guard capability is already READY, its postcondition handoff is READY, and its exact validation-receipt issuance bridge is READY. The generic experiment-evidence acceptor is also already qualified.

This gate proves that those existing authorities compose without inventing a second acceptor:

```text
BOUNDED_MUTATION_CAPABILITY_APPLIED
        ↓
BOUNDED_MUTATION_CAPABILITY_POSTCONDITIONS_VALIDATED
        ↓
BOUNDED_CAPABILITY_POSTCONDITION_RECEIPT_ISSUED
        ↓
existing TEMP_WORKTREE_EXPERIMENT_EVIDENCE_ACCEPTANCE_REFERENCE
        ↓
EXPERIMENT_EVIDENCE_ACCEPTED
```

The integration checker is an audit harness only. It does not add a product mutation command and does not add a new evidence-acceptance implementation.

## Why this is a separate gate

Receipt issuance proves provenance, not evidence acceptance. PR #42 intentionally stops at an exact sealed `POSTCONDITIONS_VALIDATED` receipt. PR #19 independently defines the acceptance contract.

This integration therefore asks a narrow question:

> Can evidence produced by the current bounded capability traverse the already-qualified acceptance boundary without authority widening or lineage reconstruction?

A positive answer means only that the existing boundaries compose correctly.

## Ephemeral evidence only

The checker creates its acceptance ledger inside a temporary fixture evidence directory. That ledger is destroyed with the fixture.

```text
fixture acceptance ledger != retained/global experiment evidence ledger
```

A passing integration audit therefore does **not** create a new retained experiment, change the evidence corpus used by synthesis review, or authorize promotion.

## Required direct cases

The exact PR-head source bundle must be executed outside CI and must demonstrate at least:

- positive JS capability evidence → `EXPERIMENT_EVIDENCE_ACCEPTED`;
- inverse TS capability evidence → `EXPERIMENT_EVIDENCE_ACCEPTED`;
- exact replay → `EXPERIMENT_EVIDENCE_ACCEPTANCE_RECOVERED` with one acceptance record only;
- validation receipt tamper after issuance → rejected;
- primitive mutation receipt tamper after issuance → rejected;
- failed postcondition receipt may be sealed but must be rejected by the acceptor;
- broken acceptance hash chain → rejected.

Every positive path must leave the disposable worktree absent before acceptance. Acceptance must not rerun validation or inspect/reopen the disposed worktree.

## Authority boundary

A successful integration audit does not grant:

- a second evidence acceptor;
- public mutation surface;
- source mutation authority;
- automatic patch authority;
- generic mutation authority;
- primary-worktree mutation authority;
- commit/push/PR authority;
- upstream mutation authority;
- global behavioral equivalence;
- stable promotion;
- truth commit.

The existing acceptor may issue the bounded evidence state `EXPERIMENT_EVIDENCE_ACCEPTED` inside the isolated fixture. That accepted evidence is still not truth.

## Next gate

If direct exact-head audit succeeds, the integration state may become:

```text
BOUNDED_CAPABILITY_EVIDENCE_ACCEPTANCE_INTEGRATION_READY
```

The next semantic checkpoint is the already-existing:

```text
BOUNDED_MUTATION_EVIDENCE_SYNTHESIS_REVIEW
```

That next checkpoint must independently decide what accepted evidence is sufficient. This integration does not pre-authorize its conclusion.

## Promotion rule

CI/regression is a reproducibility guard only. Promotion requires direct execution of the exact source bundle packaged from the PR head, verification of bundle `HEAD_SHA.txt` and `SHA256SUMS.txt`, and retained audit evidence identifying the exact audited source bytes.

## Interactive audit result

The exact PR #43 source bundle was downloaded and executed outside CI:

```text
source head       46f3d9e1e74a2303e4b9d8258b25df971b59b801
workflow run      35912070931
artifact id       10773363061
artifact sha256   46be96d6d476da3b4e0c63bb1f071f20f6d3777ba76d2f450b1c4a146b543324
bundle HEAD_SHA   exact match
SHA256SUMS        all bundled sources PASS
direct execution  6 / 6 PASS
```

Direct report SHA-256:

```text
d83bc799c5287374820ac567912dc00fbf79f20afbbb9bbb257fa2214a24f3c8
```

Observed boundaries:

```text
positive JS acceptance                 ACCEPTED; replay RECOVERED; 1 record
inverse TS acceptance                  ACCEPTED; replay RECOVERED; 1 record
validation receipt tamper              rejected; 0 acceptance records
primitive receipt tamper               rejected; 0 acceptance records
failed postconditions                  failure receipt sealed; acceptance rejected
broken acceptance hash chain           rejected
worktree before acceptance             disposed on all audited paths
retained/global evidence ledger        unchanged
truth commit                           false
```

The retained audit record is:

`qualification/interactive_js_ts_v2_bounded_capability_evidence_acceptance_audit.json`

The gate is therefore:

```text
BOUNDED_CAPABILITY_EVIDENCE_ACCEPTANCE_INTEGRATION_READY
```

READY means composition of the existing boundaries is proven for the audited bounded scope. It does not create retained experiment evidence and does not pre-authorize synthesis review, promotion, upstream mutation, equivalence, or truth.
