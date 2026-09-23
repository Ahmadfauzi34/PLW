# Historical Evidence Promotion

PLW's current repository state and historical development evidence serve different roles.

## Source-of-truth rule

Current `main` is canonical for the current PLW product, capability, runtime, and authority state.

Historical development archives are supporting evidence. They explain how a current checkpoint or boundary was derived, but they must not override a newer state already recorded on `main`.

## Why historical evidence is promoted selectively

The Development Full archive contains experiments, fixtures, audit logs, intermediate implementations, and retained checkpoint records. Copying the whole archive into the product repository would reintroduce ambiguity and unnecessary weight.

Promotion therefore retains only evidence that is still useful for reconstructing the lineage of current architecture. A promoted exact record preserves the complete historical bytes, source SHA-256, repository path, Git blob identity, and an explicit no-new-authority boundary.

## F106-F123 authority / agent lineage — exact records retained

The authority/agent lineage is retained as **19 exact historical records** under `qualification/history/`, including two independent F120 records. Its machine-readable index is:

`qualification/history/historical_evidence_promotion_f106_f123_v1.json`

This chain preserves the historical progression from capability lifecycle and advisory context through proposal, authorization, gate, dry-run, provenance/preflight, adaptive reference-machine behavior, atomic action lease, executor outcome, and reconciliation bridge.

## F124-F127 geometry / correspondence lineage — exact records retained

The geometry/correspondence lineage is retained as **4 exact historical records**:

```text
F124  Angular semantic ownership anchors
F125  GeometrySnapshot + UI↔code correspondence
F126  runtime geometry capture adapter binding
F127  targeted geometric constraint / impact projection
```

Its machine-readable index is:

`qualification/history/historical_evidence_promotion_f124_f127_v1.json`

The retained records preserve the original authority separation:

```text
SharedGraph topology authority
        !=
Angular static ownership authority
        !=
rendered GeometrySnapshot authority
        !=
UI↔code correspondence authority
        !=
runtime capture provenance
```

Retention therefore does not merge topology, geometry, or correspondence into one graph and does not manufacture runtime or behavioral truth.

## F128-F142 proof lineage — exact records retained

The proof lineage remains retained as **21 exact historical records**, covering scenario planning/evidence, proof obligations and witness integrity, request→authorization→lease→attempt→dispatch→runtime, result acceptance, semantic/target/evidence/capability routing, execution-backed evidence, postcondition proof, and full-stack validated-state composition.

Its machine-readable index remains:

`qualification/history/historical_evidence_promotion_ledger_v1.json`

## Retained state

Across the three bounded promotion ledgers the repository now retains:

```text
F106-F123  19 exact records
F124-F127   4 exact records
F128-F142  21 exact records
---------------------------
Total      44 exact records
```

For these retained groups the Development Full ZIP is not required for normal current work. It remains useful for historical reconstruction or independent byte verification.

Historical retention does **not** grant runtime, mutation, execution, evidence-acceptance, postcondition, stable-promotion, upstream, or truth authority.

## Remaining bounded historical group

The remaining archive review is:

1. F85-F105 — simplification economics and detector-history evidence, only where still useful for current architecture.

Raw fixture corpora and transient audit output should remain outside the product repository unless a retained decision record specifically depends on them.
