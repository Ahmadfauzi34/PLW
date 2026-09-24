# Candidate Selection Provenance

Candidate selection is separate from target-file resolution. It consumes one
full `plw simplify --json` observation and binds any decision to that exact
candidate set, graph content snapshot, and target revision.

```bash
plw candidate select "Explain why isSCSSMapItemNode is a bounded boolean guard candidate" /path/to/repo --json
plw candidate capability-match "Explain why isSCSSMapItemNode is a bounded boolean guard candidate" /path/to/repo --json
```

## Discovery binding

The command records:

- Git HEAD and tree identities when available;
- clean/dirty working-tree state and a digest of the status output;
- the shared-graph content signature;
- a digest over the complete canonical candidate set;
- a discovery snapshot digest over those values.

Boolean-guard candidates bind to one exact `if`/boolean-return source span.
The candidate member line span now names that local site, while the enclosing
function lines remain available as owner context. Each candidate row also has
a candidate instance ID. Boolean-guard instances bind to the exact source-span
digest and offsets; legacy rows without an instance identity get a digest over
their complete candidate record. Duplicate legacy IDs therefore remain
distinct instances and cannot resolve by ID alone. For a function with one
valid site, the existing function candidate ID stays stable. If a function
contains multiple sites, each candidate ID includes a site-specific
disambiguator.

## Selection states

Selection resolves only when task evidence identifies one candidate through:

- one exact candidate symbol mention;
- one exact source path that contains one candidate; or
- at least two explicit structural task constraints that uniquely match one
  candidate.

The decision carries `selected_candidate_id`, `selected_candidate_instance_id`,
source path, symbol, kind, local site lines, discovery and candidate-set
digests, selection basis, and rejected alternatives. An under-specified task
stays `AMBIGUOUS`; a task with no matching candidate evidence is
`UNRESOLVED`.

When a task names both a symbol and a path, both anchors must identify the same
candidate instance. A missing or conflicting explicit path remains
`UNRESOLVED`; the symbol does not override it. Symbol and path matching are
case-sensitive.

## Agent handoff

The portable-agent surface registers `candidate` as a **read-only semantic
capability**. This public capability means candidate identity/provenance is an
available information source; it is not the internal mutation capability.

Evidence-driven capability selection may project `candidate` for the
machine-readable `semantic_scope` evidence class with coverage
`CONDITIONAL_DISCOVERY`. Task text is still excluded from capability routing.
The projection tells the agent what information `plw candidate select` can add,
what it does not prove, whether it changes state, and which exact embedded skill
to read before deciding whether to call it.

```text
candidate projected
!= candidate selected
!= internal capability matched
!= authorization
!= execution
!= mutation
```

The agent may therefore discover the candidate-selection surface during normal
`plw agent orient` reasoning without PLW automatically running candidate
selection or choosing an action for the agent. `AMBIGUOUS` and `UNRESOLVED`
remain valid outcomes and must not be guessed away.

The internal bounded mutation contract ID
`js_boolean_guard.strict_equality_string.temp_worktree.v1` remains absent from
public `plw capability list` / `plw capability describe` discovery.

## Internal capability match

`plw candidate capability-match` performs discovery, selection, then candidate
fact matching in one process and one snapshot. It checks the exact site binding,
`.js`/`.ts` extension, strict `===`, a non-optional identifier/member-chain
left operand, a string-literal right operand, and positive/inverse polarity.
It re-reads the selected source span and verifies that the discovered site and
condition facts still match the target bytes. It also recomputes the selection
from the task and same candidate snapshot before routing.
The internal contract ID is not registered in `plw capability list` or
`plw capability describe`.

The result `CAPABILITY_MATCHED` is only a match classification. Selection and
matching grant no authorization, execution, mutation, correctness, or evidence
acceptance. The contract digest and snapshot digests provide content integrity
bindings; they are not signatures or proof that an external caller is trusted.

The source-span parser remains a conservative JS/TS structural frontend, not a
full language parser. Candidates outside its bounded pattern remain unmatched
or ambiguous and require a separately justified path.

The shared-graph signature sorts set-derived semantic-usage lists before
hashing. Revalidation therefore compares stable content across independent
Python processes instead of depending on each process's hash iteration order.

## Selection-bound execution receipts

The internal bounded-capability runner accepts a `--candidate-provenance`
artifact. Before consuming the single-use authorization it recomputes full
discovery, selection, and capability matching against the same clean target
revision. It rejects a stale or edited artifact, an ambiguous selection, a
different plan candidate/site, or authorization that does not bind the exact
provenance digests.

The JS/TS planner accepts the current exact-site `js_boolean_guard_return_v3`
witness only when its candidate-instance ID, source-span digest, offsets, line
span, polarity, and condition digest still match the target bytes. Legacy v2
planner fixtures remain supported.

For a bound execution, the capability receipt carries the full provenance
digest and a compact selection summary. Postcondition validation carries the
discovery snapshot, candidate-set, selection, selected candidate/instance,
internal capability-contract, source-site, and rationale digests through the
sealed validation receipt and issuance record. Selection remains separate from
authorization, execution, correctness, and evidence acceptance. The
revalidation path does not append to the retained evidence corpus.
