# JS/TS V2 external corpus qualification

This qualification lane measures how the released **PLW v0.2.0** JS/TS
simplification frontend behaves on pinned, real-world repositories.

It is intentionally observational:

```text
candidate != patch
candidate != behavioral equivalence
estimated removable LOC != realized savings
```

The workflow downloads the exact published v0.2.0 binary and verifies its
release SHA-256 before scanning the corpora listed in
`qualification/js_ts_v2_external_corpus.json`.

For each corpus and each of the seven JS/TS rule families the ledger records:

- source/file coverage;
- structural candidate count;
- mechanically recommended vs deferred candidates;
- proof-surface risk;
- estimated removable LOC;
- bounded candidate samples.

It deliberately leaves `false_positive_count = null` and
`behavioral_validation = NOT_RUN`. Those fields require a later review lane
using target-native tests/type-checks and, when necessary, domain-specific
behavioral evidence.

Pinned corpora make runs reproducible. Updating a corpus revision is an explicit
qualification change rather than an implicit change caused by a moving branch.
