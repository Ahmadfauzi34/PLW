#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import multiprocessing as mp
import tempfile
from pathlib import Path
from typing import Any

from core.operation_invocation_admission import admit_operation_invocation, canonical_digest
from core.operation_plan import resolve_operation_plan
from core.semantic_affordance import describe_command


def make_fixture(base: Path) -> dict[str, Any]:
    cwd = (base / "cwd").resolve()
    cwd.mkdir(parents=True)
    target = (cwd / "target").resolve()
    target.mkdir()
    evidence = (base / "evidence").resolve()
    evidence.mkdir()
    plan = {
        "schema_version": "plw-operation-plan-v1",
        "capability": "candidate",
        "operation_id": "candidate.select.v1",
        "inputs": {"task": "Select isOne in src/guards.js", "root": "target"},
    }
    resolution = resolve_operation_plan(plan)
    assert resolution["status"] == "RESOLVED"
    auth = {
        "schema_version": "plw-operation-invocation-authorization-v1",
        "status": "INVOCATION_AUTHORIZED",
        "authorized": True,
        "authorization_scope": "ONE_RESOLVED_PLAN_ONE_OPERATION_ONE_ARGV",
        "single_use": True,
        "issuer": {
            "kind": "REFERENCE_HARNESS",
            "external_to_planner": True,
            "planner_self_authorized": False,
        },
        "binding": {
            "operation_plan_digest": resolution["plan_digest"],
            "operation_resolution_digest": canonical_digest(resolution),
            "operation_id": resolution["resolved_operation_id"],
            "operation_contract_digest": resolution["operation_contract_digest"],
            "compiled_argv_digest": canonical_digest(resolution["compiled_argv"]),
            "invocation_cwd": str(cwd),
            "invocation_cwd_digest": canonical_digest({"invocation_cwd": str(cwd)}),
        },
        "authority": {
            "invocation_only": True,
            "mutation_authorized": False,
            "correctness_proven": False,
            "evidence_acceptance_granted": False,
            "truth_committed": False,
        },
    }
    return {
        "cwd": cwd,
        "target": target,
        "evidence": evidence,
        "plan": plan,
        "resolution": resolution,
        "authorization": auth,
    }


def call(
    fx: dict[str, Any],
    ledger: Path,
    *,
    plan=None,
    resolution=None,
    authorization=None,
):
    return admit_operation_invocation(
        plan if plan is not None else fx["plan"],
        resolution if resolution is not None else fx["resolution"],
        authorization if authorization is not None else fx["authorization"],
        invocation_cwd=fx["cwd"],
        consumption_ledger=ledger,
    )


def worker(plan, resolution, auth, cwd: str, ledger: str, queue) -> None:
    result = admit_operation_invocation(
        plan,
        resolution,
        auth,
        invocation_cwd=Path(cwd),
        consumption_ledger=Path(ledger),
    )
    queue.put((result.get("status"), result.get("reason")))


def main() -> int:
    cases: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str = "") -> None:
        cases.append((name, ok, detail))

    contract = describe_command("operation-invocation")
    record(
        "semantic_contract",
        bool(contract.get("known"))
        and contract.get("state_change") is True
        and "single-use capability" in (contract.get("canonical_concepts") or [])
        and set(contract.get("possible_outcomes") or [])
        == {"ADMITTED", "UNRESOLVED", "REJECTED"},
        json.dumps(contract, sort_keys=True),
    )

    with tempfile.TemporaryDirectory(prefix="plw_inv_adm_") as td:
        fx = make_fixture(Path(td))
        ledger = fx["evidence"] / "consume.jsonl"
        first = call(fx, ledger)
        record(
            "admit_exact",
            first.get("status") == "ADMITTED"
            and first.get("operation_id") == "candidate.select.v1"
            and first.get("compiled_argv") == fx["resolution"]["compiled_argv"]
            and first.get("invocation_cwd") == str(fx["cwd"])
            and first.get("runtime_identity_required") is True
            and first.get("next_gate")
            == "BIND_RUNTIME_AND_EXECUTE_EXACT_ADMITTED_INVOCATION"
            and (first.get("authority") or {}).get("invocation_authorized") is True
            and (first.get("authority") or {}).get("executes_operation") is False
            and (first.get("authority") or {}).get("mutation_authorized") is False
            and (first.get("authority") or {}).get("correctness_proven") is False
            and (first.get("authority") or {}).get("evidence_acceptance_granted") is False
            and (first.get("authority") or {}).get("truth_committed") is False,
            json.dumps(first, sort_keys=True),
        )
        replay = call(fx, ledger)
        record(
            "replay_rejected",
            replay.get("status") == "REJECTED"
            and replay.get("reason") == "INVOCATION_AUTHORIZATION_ALREADY_CONSUMED",
            str(replay),
        )
        rows = [
            json.loads(line)
            for line in ledger.read_text().splitlines()
            if line.strip()
        ]
        record(
            "one_consumption_record",
            len(rows) == 1
            and rows[0].get("status") == "CONSUMED_FOR_INVOCATION_ADMISSION",
            str(rows),
        )
        record(
            "target_unchanged",
            not any(fx["target"].iterdir()),
            str(list(fx["target"].iterdir())),
        )

    for name, mutate, expected in [
        (
            "resolution_tamper",
            lambda fx: fx["resolution"].__setitem__(
                "compiled_argv", ["plw", "doctor"]
            ),
            "SUPPLIED_RESOLUTION_RECOMPUTATION_MISMATCH",
        ),
        (
            "auth_contract_tamper",
            lambda fx: fx["authorization"]["binding"].__setitem__(
                "operation_contract_digest", "sha256:" + "0" * 64
            ),
            "INVOCATION_AUTHORIZATION_BINDING_MISMATCH:operation_contract_digest",
        ),
        (
            "auth_argv_tamper",
            lambda fx: fx["authorization"]["binding"].__setitem__(
                "compiled_argv_digest", "sha256:" + "1" * 64
            ),
            "INVOCATION_AUTHORIZATION_BINDING_MISMATCH:compiled_argv_digest",
        ),
        (
            "auth_cwd_tamper",
            lambda fx: fx["authorization"]["binding"].__setitem__(
                "invocation_cwd", "/tmp/other"
            ),
            "INVOCATION_AUTHORIZATION_BINDING_MISMATCH:invocation_cwd",
        ),
        (
            "planner_self_auth",
            lambda fx: fx["authorization"]["issuer"].__setitem__(
                "planner_self_authorized", True
            ),
            "PLANNER_SELF_AUTHORIZATION_FORBIDDEN",
        ),
        (
            "truthy_not_literal_true",
            lambda fx: fx["authorization"].__setitem__("authorized", 1),
            "INVOCATION_AUTHORIZATION_LITERAL_TRUE_REQUIRED",
        ),
    ]:
        with tempfile.TemporaryDirectory(prefix=f"plw_inv_{name}_") as td:
            fx = make_fixture(Path(td))
            mutate(fx)
            ledger = fx["evidence"] / "consume.jsonl"
            out = call(fx, ledger)
            record(
                name,
                out.get("status") == "REJECTED"
                and out.get("reason") == expected
                and not ledger.exists(),
                str(out),
            )

    with tempfile.TemporaryDirectory(prefix="plw_inv_amb_") as td:
        fx = make_fixture(Path(td))
        plan = copy.deepcopy(fx["plan"])
        plan.pop("operation_id")
        resolution = resolve_operation_plan(plan)
        ledger = fx["evidence"] / "consume.jsonl"
        out = call(fx, ledger, plan=plan, resolution=resolution)
        record(
            "ambiguous_unresolved",
            out.get("status") == "UNRESOLVED"
            and out.get("plan_status") == "AMBIGUOUS"
            and not ledger.exists(),
            str(out),
        )

    with tempfile.TemporaryDirectory(prefix="plw_inv_inside_") as td:
        fx = make_fixture(Path(td))
        ledger = fx["target"] / "consume.jsonl"
        out = call(fx, ledger)
        record(
            "ledger_outside_target",
            out.get("status") == "REJECTED"
            and out.get("reason") == "CONSUMPTION_LEDGER_MUST_BE_OUTSIDE_TARGET_ROOT"
            and not ledger.exists(),
            str(out),
        )

    with tempfile.TemporaryDirectory(prefix="plw_inv_malformed_") as td:
        fx = make_fixture(Path(td))
        ledger = fx["evidence"] / "consume.jsonl"
        ledger.write_text("not-json\n")
        out = call(fx, ledger)
        record(
            "malformed_ledger_fail_closed",
            out.get("status") == "REJECTED"
            and out.get("reason") == "AUTHORIZATION_CONSUMPTION_LEDGER_INVALID",
            str(out),
        )

    with tempfile.TemporaryDirectory(prefix="plw_inv_concurrent_") as td:
        fx = make_fixture(Path(td))
        ledger = fx["evidence"] / "consume.jsonl"
        ctx = mp.get_context("fork")
        queue = ctx.Queue()
        processes = [
            ctx.Process(
                target=worker,
                args=(
                    fx["plan"],
                    fx["resolution"],
                    fx["authorization"],
                    str(fx["cwd"]),
                    str(ledger),
                    queue,
                ),
            )
            for _ in range(8)
        ]
        for process in processes:
            process.start()
        results = [queue.get(timeout=20) for _ in processes]
        for process in processes:
            process.join(20)
        admitted = sum(1 for status, _ in results if status == "ADMITTED")
        replay = sum(
            1
            for status, reason in results
            if status == "REJECTED"
            and reason == "INVOCATION_AUTHORIZATION_ALREADY_CONSUMED"
        )
        rows = [
            json.loads(line)
            for line in ledger.read_text().splitlines()
            if line.strip()
        ]
        record(
            "atomic_concurrency_8way",
            admitted == 1
            and replay == 7
            and len(rows) == 1
            and all(process.exitcode == 0 for process in processes),
            str(results),
        )

    failed = [row for row in cases if not row[1]]
    for name, ok, detail in cases:
        print(f"{'PASS' if ok else 'FAIL'} {name}" + ("" if ok else f": {detail}"))
    print(
        f"OPERATION_INVOCATION_ADMISSION_REFERENCE: "
        f"{len(cases) - len(failed)}/{len(cases)} PASS"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
