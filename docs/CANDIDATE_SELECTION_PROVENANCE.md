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
