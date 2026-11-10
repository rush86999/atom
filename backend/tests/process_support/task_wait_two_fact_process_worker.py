"""Actual-OS-process worker for the joined two-fact TASK-WAIT-01 episode.

This is test-only acceptance infrastructure. It reuses the established
controlled proposal transport and real public assignment router from
``task_wait_process_worker`` but supports two distinct missing facts in either
arrival order:

``start``
    Start one assignment with only the purchase order plus the second fact's
    source. The controlled transport asks for the first missing fact.
``source-first``
    Deliver the first authorized fact. The same job must ask for the second.
``startup-recover``
    Fresh OS process; recovery must not model-poll while the second fact is
    still missing.
``source-second``
    Fresh OS process; deliver the second fact. The same job must complete and
    publish one current artifact.
``duplicate-second``
    Re-deliver the second fact; it must be inert.
``inspect``
    Read-only snapshot.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

BASE_PATH = Path(__file__).with_name("task_wait_process_worker.py")
_spec = importlib.util.spec_from_file_location("tw_base_worker", BASE_PATH)
base = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = base
_spec.loader.exec_module(base)

PO = "PO-TWO-ORDER-1"
INVOICE = "INV-TWO-ORDER-1"
EXPECTED_TOTAL = "140.25"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True)
    parser.add_argument("--scratch", required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--report", required=True)
    parser.add_argument("--checkpoint", default="")
    parser.add_argument("--deferred-timeout", default="0")
    parser.add_argument("--order", default="")
    parser.add_argument("--first-role", default="")
    parser.add_argument("--second-role", default="")
    return parser.parse_args()


def install_two_fact_transport(calls: list, preferred_first: str = "") -> None:
    """Controlled fixture: choose the actual missing role, never a final plan."""
    import api.assignment_routes as routes
    from core.employee_adaptation import WorkAdaptationProposal
    from core.employee_work_requests import InvoiceReconciliationRequest

    async def discovery(context, **kwargs):
        return {
            "proposal": {
                "proposal_kind": "evidence_read",
                "reason": "read authorized procurement records",
                "evidence_reads": [
                    {"step_id": f"evidence-{index}",
                     "title": "Read source",
                     "source_id": source["source_id"]}
                    for index, source in enumerate(context["sources"], 1)
                ],
            },
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    async def adaptation(context, observations, **kwargs):
        roles = {
            str(item.get("business_role") or ""): item["step_id"]
            for item in context.get("evidence_results", [])
            if item.get("business_role")
        }
        capability = next(
            (item for item in context.get("available_business_operations") or []
             if str(item.get("operation") or "") == "invoice_reconciliation"),
            {})
        missing = [
            str(role) for role in capability.get("missing") or []
            if str(role).strip()]
        chosen = preferred_first if preferred_first in missing else (
            missing[0] if missing else "")
        calls.append({
            "pid": os.getpid(),
            "at": time.time(),
            "business_roles": sorted(roles),
            "missing": missing,
            "chosen": chosen,
            "observation_ids": [
                item["observation_id"] for item in observations],
        })
        common = {
            "reason": "controlled fixture selects supported work from accepted records",
            "observation_ids": [
                item["observation_id"] for item in observations],
        }
        if missing:
            role = chosen
            question = (
                f"Which authorized source contains the missing {role} "
                f"record for purchase order {PO}?")
            proposal = WorkAdaptationProposal(
                decision="clarify",
                clarification={
                    "question": question,
                    "concept": "invoice_reconciliation",
                    "unblocks": "invoice reconciliation",
                    "missing_roles": [role],
                },
                **common,
            )
        else:
            proposal = WorkAdaptationProposal(
                decision="replan",
                work_request=InvoiceReconciliationRequest(
                    operation="invoice_reconciliation",
                    invoice_step_id=roles["invoice"],
                    purchase_order_step_id=roles["purchase_order"],
                    receiving_step_id=roles["receiving"],
                ),
                **common,
            )
        return {
            "proposal": proposal.model_dump(),
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    routes.propose_employee_work = discovery
    routes.propose_adaptation = adaptation
    routes._employee_llm = lambda *args, **kwargs: object()
    routes._employee_llm_for_scope = lambda *args, **kwargs: object()


def _start(client, scratch: Path, order: str) -> dict:
    invoice = scratch / "sources" / "invoice.json"
    receiving = scratch / "sources" / "receiving.json"
    po = scratch / "sources" / "po.json"
    # Invoice-first starts with only the PO, so invoice then receiving are two
    # distinct waits. Receiving-first starts with PO+invoice, so receiving then
    # invoice are two distinct waits.
    # Both orders start with only the purchase order, so both facts are
    # genuinely missing; the controlled transport chooses the requested first
    # role, then the remaining role becomes the second wait.
    sources = [{"path": str(po)}]
    response = client.post(
        "/api/assignments/from-objective",
        json={
            "objective": (
                f"Reconcile invoice {INVOICE} for purchase order {PO}"),
            "sources": sources,
            "authorized_actions": ["retrieve", "calculate"],
            "requested_output": "document",
            "use_model": True,
        })
    if response.status_code != 200:
        raise RuntimeError(
            f"start failed: {response.status_code} {response.text}")
    return response.json()


def _add_source(client, run_id: str, scratch: Path, role: str):
    filename = "invoice.json" if role == "invoice" else "receiving.json"
    return client.post(
        f"/api/assignments/{run_id}/sources",
        json={
            "source": {"path": str(scratch / "sources" / filename)},
            "reason": f"authorized {role} record answers the {role} question",
        })


def _snapshot(lifecycle, run_id: str, calls: list) -> dict:
    snapshot = base._snapshot(lifecycle, run_id, calls)
    record = lifecycle.get_task(run_id) or {}
    assignment = record.get("assignment") or {}
    artifacts = []
    for step in assignment.get("steps") or []:
        if not str(step.get("adapter") or "").startswith("artifact."):
            continue
        if step.get("status") != "applied":
            continue
        blob = (step.get("result") or {}).get("artifact") or {}
        artifacts.append({
            "step_id": step.get("step_id"),
            "path": blob.get("path"),
            "sha256": blob.get("sha256"),
        })
    snapshot["artifacts"] = artifacts
    return snapshot


def main() -> int:
    args = _parse_args()
    scratch = Path(args.scratch).resolve()
    base._prepare_environment(scratch)

    calls: list = []
    install_two_fact_transport(calls, preferred_first=args.first_role)
    client = base.build_client()
    lifecycle = base._lifecycle()

    if args.phase == "start":
        if args.order not in ("invoice", "receiving"):
            raise RuntimeError("--order invoice|receiving required")
        started = _start(client, scratch, args.order)
        run_id = started["run_id"]
        report = _snapshot(lifecycle, run_id, calls)
        report.update({
            "phase": args.phase,
            "pid": os.getpid(),
            "order": args.order,
        })
        base._write_json(args.report, report)
        return 0

    if not args.run_id:
        raise RuntimeError("--run-id is required for this phase")

    if args.phase == "source-first":
        if not args.first_role:
            raise RuntimeError("--first-role required")
        answer = _add_source(client, args.run_id, scratch, args.first_role)
        report = _snapshot(lifecycle, args.run_id, calls)
        report.update({
            "phase": args.phase,
            "pid": os.getpid(),
            "role": args.first_role,
            "source_response_status": answer.status_code,
            "source_response": answer.json(),
        })
        base._write_json(args.report, report)
        return 0

    if args.phase == "startup-recover":
        from core.assignment_recovery import (
            recover_active_assignments_at_startup,
        )

        recovered = base.asyncio_run(
            recover_active_assignments_at_startup(
                limit=20, max_steps_per_assignment=12))
        report = _snapshot(lifecycle, args.run_id, calls)
        report.update({
            "phase": args.phase,
            "pid": os.getpid(),
            "startup_entrypoint": (
                "core.assignment_recovery."
                "recover_active_assignments_at_startup"),
            "recovery_results": recovered,
        })
        base._write_json(args.report, report)
        return 0

    if args.phase in ("source-second", "duplicate-second"):
        role = args.second_role
        if not role:
            raise RuntimeError("--second-role required")
        answer = _add_source(client, args.run_id, scratch, role)
        report = _snapshot(lifecycle, args.run_id, calls)
        report.update({
            "phase": args.phase,
            "pid": os.getpid(),
            "role": role,
            "source_response_status": answer.status_code,
            "source_response": answer.json(),
        })
        base._write_json(args.report, report)
        return 0

    if args.phase == "inspect":
        report = _snapshot(lifecycle, args.run_id, calls)
        report.update({"phase": args.phase, "pid": os.getpid()})
        base._write_json(args.report, report)
        return 0

    raise RuntimeError(f"unknown phase {args.phase!r}")


if __name__ == "__main__":
    sys.exit(main())
