# Bounded capability postcondition issuance bridge

## Purpose

The bounded mutation capability and postcondition integration are already READY. The generic evidence acceptor is also already qualified. The remaining provenance gap is receipt issuance:

```text
BOUNDED_MUTATION_CAPABILITY_POSTCONDITIONS_VALIDATED
        ↓
materialize exact lower-level validation receipt
        ↓
postcondition issuance hash chain
        ↓
BOUNDED_CAPABILITY_POSTCONDITION_RECEIPT_ISSUED
        ↓
existing TEMP_WORKTREE_EXPERIMENT_EVIDENCE_ACCEPTANCE_REFERENCE
```

This bridge does not create a new evidence acceptor. It reuses the issuance mechanism introduced with the existing evidence-acceptance reference.

## Why issuance must remain separate

The postcondition integration returns a wrapper containing the exact lower-level validation result. Evidence acceptance, however, is intentionally allowed to consume only a separately materialized and sealed `POSTCONDITIONS_VALIDATED` receipt.

That separation prevents a later reconstructed JSON object from silently becoming evidence. The bridge therefore:

1. executes the already-qualified capability→postcondition integration;
2. obtains its lower-level validation receipt in the same process;
3. writes deterministic receipt bytes outside the target;
4. hashes those exact bytes;
5. appends/recover-binds that digest through the existing issuance hash chain;
6. leaves experiment evidence acceptance false.

The disposed worktree is never reopened by issuance.

## Failure semantics

The bridge is fail-closed.

```text
invalid path after effectful capability apply
→ discard worktree
→ no issuance

tampered capability receipt
→ integration rejects + disposes
→ no validation receipt
→ no issuance

broken existing issuance chain
→ validated worktree already disposed
→ issuance rejected
→ evidence acceptance remains false

postcondition failure
→ failure receipt may be sealed for auditability
→ evidence acceptance remains false
```

A sealed failure receipt is not accepted evidence. The existing evidence acceptor independently requires `POSTCONDITIONS_VALIDATED`.

## Replay

Exact issuance replay is idempotent:

```text
same validation receipt digest
→ POSTCONDITION_VALIDATION_RECEIPT_ISSUANCE_RECOVERED
→ no second ledger append
```

A broken issuance chain rejects rather than being repaired implicitly.

## Authority boundary

Successful issuance grants only provenance retention for the exact postcondition receipt. It does not grant:

- experiment evidence acceptance;
- source mutation;
- automatic patching;
- generic mutation;
- primary-worktree mutation;
- commit/push/PR authority;
- upstream mutation;
- global behavioral equivalence;
- stable promotion;
- truth commit.

The next gate remains the already-qualified:

```text
TEMP_WORKTREE_EXPERIMENT_EVIDENCE_ACCEPTANCE_REFERENCE
```

## Promotion rule

Regression/CI is not promotion authority. Promotion requires direct execution of an exact PR-head source bundle and verification of at least:

- positive JS issuance;
- inverse TS issuance;
- exact issuance replay without append;
- capability receipt tamper → no issuance;
- broken issuance chain rejection;
- failed postcondition receipt sealed but not accepted;
- invalid issuance/output path after effectful apply → worktree disposed.

## Interactive audit result

The exact PR-head source bundle was downloaded and executed outside CI:

```text
source head       be243d87b023586dba38505ff4b4427d0291200f
workflow run      35911149108
artifact id       10773286429
artifact sha256   48cc54b4bfc5001208e24d92254fa40e4e2406e1bcba7956d6e0b5ee1a184a85
bundle HEAD_SHA   exact match
SHA256SUMS        all sources PASS
direct execution  6 / 6 PASS
```

Direct report SHA-256:

```text
20b42301467afbfcce7be3c54824b82a03e8623f0e5875d353bbf28c18fac301
```

Observed boundaries:

```text
positive JS issuance                 PASS
inverse TS issuance                  PASS
exact issuance replay                recovered, 1 record only
capability receipt tamper            no issuance + disposed
broken existing issuance chain       rejected
postwrite validation failure         failure receipt sealed, not accepted
validation receipt path inside target rejected + disposed
```

The retained authority record is:

`qualification/interactive_js_ts_v2_bounded_capability_postcondition_issuance_audit.json`

The gate is therefore:

```text
BOUNDED_CAPABILITY_POSTCONDITION_ISSUANCE_READY
```

READY still grants no experiment-evidence acceptance. The next checkpoint remains the existing evidence-acceptance reference.
