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
- for dirty Git-visible tracked/untracked paths, a digest of regular-file bytes
  or symlink targets, with `dirty_content_complete` and `dirty_path_count`;
- the shared-graph content signature;
- a digest over the complete canonical candidate set;
- a discovery snapshot digest over those values.

The status digest alone cannot distinguish two contents of the same dirty
README path. `dirty_content_digest` closes that gap for readable regular files
and symlinks without following symlinks outside the target. Deleted paths are
represented as missing. Unsupported/unreadable paths mark
`dirty_content_complete=false`; callers must preserve that uncertainty.
Ignored files are outside Git-visible dirty path coverage. Effectful candidate
execution still requires a clean target and independent authorization.

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

## Machine-readable operation contracts

`plw capability describe candidate --json` exposes operation contracts using
the generic schema `plw-operation-contract-v1`. Candidate selection is the
first reference implementation; the schema is not candidate-specific.

Two operations are currently described:

- `candidate.select.v1` for `plw candidate select <task> [root] --json`;
- `candidate.capability-match.v1` for
  `plw candidate capability-match <task> [root] --json`.

Each record binds, in one machine-readable object:

- command prefix and positional input order;
- input type, semantic role, required/optional status, and defaults;
- output schema and exact result-state paths;
- bounded cardinality/front-end/ambiguity constraints;
- domain-result behavior versus process-failure classes;
- an explicit all-false authority block.

The `task` input has role `task_evidence`. The optional `root` input has role
`target_root`, defaults to `.`, and reflects the current CLI behavior that root
existence is not prevalidated by argparse.

For `candidate.select.v1`, `RESOLVED`, `AMBIGUOUS`, and `UNRESOLVED` are domain
states and normally return process exit code 0. In the current implementation,
an empty task, zero-candidate target, or even a nonexistent root may therefore
produce domain `UNRESOLVED`; callers must not misclassify that normal result as
a transport/process failure.

`plw operation-plan resolve` emits a reference argv with `--json` before the
end-of-options delimiter `--`, followed by positional input values. Tasks such
as `-h` or `--json` therefore reach the candidate operation as task data. NUL
and invalid Unicode in positional input are rejected as unrepresentable in
process argv. A plan
being `RESOLVED` remains separate from selection's own domain result and
does not authorize invocation.

For `candidate.capability-match.v1`, a resolved exact contract match yields
`CAPABILITY_MATCHED`; ambiguous, unresolved, or otherwise unmatched selection
can yield `CAPABILITY_NOT_MATCHED`. These are also domain outcomes, not grants
of execution authority.

`plw agent orient` does **not** inline the full operation records. Its compact
candidate-capability row only advertises
`operation_contract_available=true` and `operation_contract_count=2`. An agent
can therefore know that an exact invocation contract is recoverable, then fetch
it only when planning a call. This keeps normal orientation bounded rather than
repeating input/output/failure metadata for every projected capability.

Operation contracts are descriptive reference-machine state. They do not
authorize invocation, automatically execute a command, mutate source, establish
correctness, accept evidence, or commit truth.

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
