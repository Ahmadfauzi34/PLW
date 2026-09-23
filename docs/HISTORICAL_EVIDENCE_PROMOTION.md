# Historical Evidence Promotion

PLW's current repository state and historical development evidence serve different roles.

## Source-of-truth rule

Current `main` is canonical for the current PLW product, capability, runtime, and authority state.

Historical development archives are supporting evidence. They explain how a current checkpoint or boundary was derived, but they must not override a newer state already recorded on `main`.

## Why historical evidence is promoted selectively

The Development Full archive contains experiments, fixtures, audit logs, intermediate implementations, and retained checkpoint records. Copying the whole archive into the product repository would reintroduce ambiguity and unnecessary weight.

Promotion therefore retains only evidence that is still useful for reconstructing the lineage of current architecture. A promoted exact record preserves the complete historical bytes, source SHA-256, repository path, Git blob identity, and an explicit no-new-authority boundary.

## F85-F105 simplification / economics lineage — exact records retained

The foundational simplification lineage is retained as **21 exact checkpoint records** from F85 through F105.

Its machine-readable index is:

`qualification/history/historical_evidence_promotion_f85_f105_v1.json`

This group preserves the lineage from selective stable promotion and reference-machine economics through frontend reuse/compression, freeze/reopen governance, and the Rule3 dossier → shadow prototype → economics → retirement sequence.

Five direct supporting witnesses are retained byte-exact because they are decision-relevant to F104/F105:

```text
4  pinned F104 Rule3 probe excerpts
1  F105 compression-trial patch
```

The two large F105 analyzer snapshots remain archive-only. Their exact SHA-256 identities and decision role are preserved in the F105 checkpoint record, while the retained compression patch preserves the implementation delta. They are not required for normal current development; the pinned Development Full archive remains available for independent historical reconstruction.

Large external probe/corpus snapshots from F94/F98/F99 remain outside the clean repository because their decision records already retain the relevant historical conclusions and identities; raw corpora are not current product authority.

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

Across the bounded promotion ledgers the repository now retains:

```text
F85-F105   21 exact decision records
F106-F123  19 exact records
F124-F127   4 exact records
F128-F142  21 exact records
---------------------------
Total      65 exact decision/history records

F104/F105   5 exact supporting witnesses
             2 archive-only analyzer snapshots
```

For the F85-F142 architectural lineage, the Development Full ZIP is no longer required for normal current development reasoning. It remains archival material for independent byte verification and broader historical archaeology.

Historical retention does **not** grant runtime, mutation, execution, evidence-acceptance, postcondition, stable-promotion, upstream, or truth authority.

## Promotion frontier closed

The bounded historical promotion plan F85-F142 is complete.

Raw fixture corpora and transient audit output remain outside the product repository unless a future retained decision record specifically requires them.
