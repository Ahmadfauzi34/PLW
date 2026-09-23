# Historical Evidence Promotion

PLW's current repository state and historical development evidence serve different roles.

## Source-of-truth rule

Current `main` is canonical for the current PLW product, capability, runtime, and authority state.

Historical development archives are supporting evidence. They explain how a current checkpoint or boundary was derived, but they must not override a newer state already recorded on `main`.

## Why historical evidence is promoted selectively

The Development Full archive contains experiments, fixtures, audit logs, intermediate implementations, and retained checkpoint records. Copying the whole archive into the product repository would reintroduce ambiguity and unnecessary weight.

Promotion therefore retains only evidence that is still useful for reconstructing the lineage of current architecture. A promoted exact record preserves the complete historical bytes, source SHA-256, repository path, Git blob identity, and an explicit no-new-authority boundary.

## F106-F123 authority / agent lineage — exact records retained

The second bounded promotion group is retained as **19 exact historical records** under `qualification/history/`.

The retained chain covers:

```text
F106  capability lifecycle
F107  lifecycle workflow adapter
F108  workflow context-pack integration
F109  relevance trigger contract
F110  fixture fast lane
F111  relevance decision accountability
F112  delivery accountability link
F113  accountability chain query
F114  action proposal boundary
F115  layered skill router
F116  action authorization receipt
F117  authorized action gate
F118  authorized executor dry-run
F119  authority provenance / preflight hardening
F120  adaptive-agent reference machine
F120  Tool.py external-corpus audit
F121  atomic single-use action lease
F122  lease-bound executor outcome
F123  executor-adapter reconciliation bridge
```

Both F120 records are retained independently because they are distinct historical evidence artifacts despite sharing the same checkpoint number.

`qualification/history/historical_evidence_promotion_f106_f123_v1.json` is the machine-readable index for this group. It records the pinned source archive, source path, source SHA-256, repository path, repository Git blob SHA-1, and byte-match state for all 19 records.

## F128-F142 proof lineage — exact records retained

The first bounded group remains retained as **21 exact historical records**, covering scenario planning/evidence, proof obligations and witness integrity, request→authorization→lease→attempt→dispatch→runtime, result acceptance, semantic/target/evidence/capability routing, execution-backed evidence, postcondition proof, and full-stack validated-state composition.

`qualification/history/historical_evidence_promotion_ledger_v1.json` remains the machine-readable index for the F128-F142 group.

## Retained state

Across the two bounded promotion ledgers the repository now retains:

```text
F106-F123  19 exact records
F128-F142  21 exact records
---------------------------
Total      40 exact records
```

For these retained groups the Development Full ZIP is not required for normal current work. It remains useful for historical reconstruction or independent byte verification.

Historical retention does **not** grant runtime, mutation, execution, evidence-acceptance, postcondition, stable-promotion, upstream, or truth authority.

## Promotion order after F106-F123 and F128-F142

The remaining archive should be reviewed in bounded groups:

1. F124-F127 — semantic ownership, geometry/correspondence, runtime geometry, impact projection.
2. F85-F105 — simplification economics and detector-history evidence, only where still useful for current architecture.

Raw fixture corpora and transient audit output should remain outside the product repository unless a retained decision record specifically depends on them.
