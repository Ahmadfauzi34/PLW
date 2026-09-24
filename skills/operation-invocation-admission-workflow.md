# Operation Invocation Admission Workflow

**Load when:** an operation plan has already resolved one exact public PLW operation and the agent needs to decide whether that exact invocation may cross from read-only planning into an authority-bearing execution path.

## Semantic anchor

Local concept: **Operation Invocation Admission**.

Nearest established abstractions:
- admission control;
- single-use capability / capability token;
- compare-and-consume authorization;
- content-addressed provenance binding;
- replay protection / idempotency-key consumption.

This is similar to a capability-token admission gate, but the PLW delta is strict: the gate binds one recomputed operation-plan resolution, one operation contract, one compiled argv, and one invocation working directory. It consumes an external authorization exactly once. It still does **not** execute the operation.

It is different from:
- operation execution;
- runtime/binary identity attestation;
- mutation authorization;
- postcondition validation;
- result evidence acceptance;
- truth commit.

## Why this gate exists

`operation-plan resolve` can establish that exactly one public operation contract accepts the declared inputs. A `RESOLVED` plan is still only preflight knowledge. Treating resolution as invocation authority would collapse proposal/planning into authorization.

Use this gate when the epistemic gap is:

```text
exact operation plan RESOLVED
+
compiled argv known
+
invocation cwd known
+
external authorization exists
-
no proof yet that the authorization exactly binds this plan/resolution/contract/argv/cwd
```

## Required authorization

The authorization must be external to the planner and single-use:

```json
{
  "schema_version": "plw-operation-invocation-authorization-v1",
  "status": "INVOCATION_AUTHORIZED",
  "authorized": true,
  "authorization_scope": "ONE_RESOLVED_PLAN_ONE_OPERATION_ONE_ARGV",
  "single_use": true,
  "issuer": {
    "kind": "EXTERNAL_REVIEWER_OR_POLICY",
    "external_to_planner": true,
    "planner_self_authorized": false
  },
  "binding": {
    "operation_plan_digest": "sha256:...",
    "operation_resolution_digest": "sha256:...",
    "operation_id": "candidate.select.v1",
    "operation_contract_digest": "sha256:...",
    "compiled_argv_digest": "sha256:...",
    "invocation_cwd": "/absolute/path",
    "invocation_cwd_digest": "sha256:..."
  },
  "authority": {
    "invocation_only": true,
    "mutation_authorized": false,
    "correctness_proven": false,
    "evidence_acceptance_granted": false,
    "truth_committed": false
  }
}
```

The planner must not mint this authorization for itself. `authorized` must be literal JSON `true`; truthy substitutes such as `1` are rejected.

## Command

```bash
plw operation-invocation admit \
  plan.json \
  resolution.json \
  authorization.json \
  --cwd /absolute/invocation/cwd \
  --consumption-ledger /outside/target/invocation-consumption.jsonl \
  --allow-state-change \
  --json
```

`--allow-state-change` is required because successful admission atomically consumes the single-use authorization in the ledger. The ledger must be outside the target root when the plan has a target `root` input.

## Outcomes

### `ADMITTED`

The supplied resolution exactly matches a fresh recomputation of the original plan, the external authorization binds the exact plan/resolution/operation-contract/argv/cwd, and that authorization was atomically consumed once.

Authority gained:
- `invocation_authorized=true` for the exact admitted invocation.

Authority **not** gained:
- `executes_operation=false`;
- `mutation_authorized=false`;
- `correctness_proven=false`;
- `evidence_acceptance_granted=false`;
- `truth_committed=false`.

The receipt also states `runtime_identity_required=true` because an argv beginning with a logical command such as `plw` does not prove which runtime/binary will execute it.

Next gate:

```text
BIND_RUNTIME_AND_EXECUTE_EXACT_ADMITTED_INVOCATION
```

### `UNRESOLVED`

The original plan no longer resolves exactly, for example because it is now ambiguous. No authorization is consumed. Return to operation selection/preflight; do not guess through ambiguity.

### `REJECTED`

The supplied resolution, external authorization, cwd, ledger boundary, or single-use constraint is invalid. No invocation authority is created. A replay of an already-consumed authorization is rejected.

## Information gained

A successful admission proves only:
- exact plan/resolution recomputation binding;
- exact operation-contract binding;
- exact argv identity;
- exact invocation-cwd identity;
- one external authorization was consumed atomically for that binding;
- replay of the same authorization cannot create a second admission through the same ledger.

It does not prove runtime identity, execution, mutation permission, domain success, correctness, evidence acceptance, or truth.
