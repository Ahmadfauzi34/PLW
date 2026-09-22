# JS/TS temp-worktree experiment evidence acceptance reference

This checkpoint accepts one already-validated, already-disposed temporary
worktree experiment as bounded evidence.

It starts from:

    POSTCONDITIONS_VALIDATED

and may produce:

    EXPERIMENT_EVIDENCE_ACCEPTED

or, for exact replay of an already accepted receipt:

    EXPERIMENT_EVIDENCE_ACCEPTANCE_RECOVERED

Acceptance does not rerun validation and does not reopen the disposed worktree.

## Interactive-first audit

The acceptance contract was audited interactively before merge.

CI is not the authority for this audit. Existing CI may only act as a
deterministic regression guard.

Six cases were exercised:

| Case | Expected | Observed |
| --- | --- | --- |
| valid sealed validation receipt | EXPERIMENT_EVIDENCE_ACCEPTED | PASS |
| exact acceptance replay | EXPERIMENT_EVIDENCE_ACCEPTANCE_RECOVERED | PASS |
| validation receipt edited after issuance | reject | PASS |
| failed-validation receipt | reject | PASS |
| lineage digest mismatch | reject | PASS |
| broken issuance hash chain | reject | PASS |

Audit artifact SHA-256:

    39a20adbd2e5079b528b022e9417f1506cda70d7af80b0b67fb6cf76f1a07d60

## Why validation receipts need issuance sealing

A validation receipt is ordinary evidence bytes outside the disposable
worktree. The worktree has already been removed by the time acceptance happens.

Without an issuance-time seal, a later consumer cannot distinguish:

- the exact receipt emitted by the validator; from
- a JSON file edited after validation.

Therefore the postcondition validator now appends the exact validation receipt
SHA-256 to a hash-chained issuance ledger.

The issuance record binds:

- validation receipt digest;
- validation status;
- rule;
- candidate ID;
- target identity;
- all validation lineage digests;
- previous issuance-record digest;
- current issuance-record digest.

Acceptance requires exactly one matching issued receipt.

## Immutable lineage

The acceptor receives these retained artifacts:

- dry-run plan;
- preflight receipt;
- authorization receipt;
- postcondition-validation spec;
- TEMP_WORKTREE_APPLIED mutation receipt;
- POSTCONDITIONS_VALIDATED validation receipt;
- issuance ledger;
- acceptance ledger.

It recomputes all retained-file digests and requires them to match the lineage
stored in the validation receipt and issuance record.

It also re-checks structural relationships:

- candidate ID and source path;
- repository and pinned revision;
- authorization scope and external issuer;
- validation-spec target;
- validation argv exactly matching the bound spec;
- focused postcondition argv equal to the preflight baseline argv;
- mutation receipt source/diff digests equal to the validation receipt;
- authorization remained consumed;
- worktree was disposed after successful validation.

No validation command is executed again.

## Acceptance ledger

A first successful acceptance appends one hash-chained record with:

    status = EXPERIMENT_EVIDENCE_ACCEPTED
    evidence_class = BOUNDED_POSTCONDITION_VALIDATION_EVIDENCE

The record binds:

- exact validation receipt digest;
- exact issuance-record digest;
- candidate and target identity;
- complete lineage digest map;
- bounded validation summary;
- explicit no-authority fields.

The acceptance ledger itself is sequence-checked and hash-chained.

## Exact replay

If the same exact validation receipt is accepted again:

    EXPERIMENT_EVIDENCE_ACCEPTANCE_RECOVERED

The previous acceptance record is validated and returned.

No second acceptance-ledger row is appended.

A replay is rejected if the existing acceptance record has changed authority,
target, candidate, lineage, evidence class, or issuance binding.

## Rejection boundary

Acceptance is rejected when any of these are observed:

- the exact validation receipt was never sealed;
- the validation receipt bytes changed after issuance;
- validation did not end in POSTCONDITIONS_VALIDATED;
- any required validation command failed or timed out;
- validation lineage files no longer match their digests;
- issuance lineage differs from validation lineage;
- issuance chain integrity is broken;
- acceptance chain integrity is broken;
- a mutation/validation/authorization receipt widens authority.

## Authority boundary

A successful acceptance means only:

    EXPERIMENT_EVIDENCE_ACCEPTED

with evidence class:

    BOUNDED_POSTCONDITION_VALIDATION_EVIDENCE

It does not mean:

    truth
    global behavioral equivalence
    source mutation authority
    automatic patch authority
    generic mutation authority
    upstream mutation authorization

The acceptor explicitly records:

    truth_commit = false

## Next gate

The next gate is:

    BOUNDED_MUTATION_EVIDENCE_SYNTHESIS_REVIEW

That review may compare multiple independently accepted experiment records.

It must not turn a single accepted experiment into general rewrite authority.
