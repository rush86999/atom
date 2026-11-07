"""Actual-OS-process worker for the TASK-WAIT-01 recovery acceptance.

This script is intentionally a *separate process* from the pytest parent. It
builds the real public assignment router, the real compiler/executor and a
scratch SQLite store, then performs exactly one phase of the restart scenario:

``start``
    Start the employee objective and stop at the genuine missing-invoice wait.
``source-complete``
    Deliver the authorized invoice through the public ``/sources`` route; the
    route's existing continuation must finish the same task.
``source-interrupt``
    Deliver the authorized invoice, let the route durably accept/read it and
    settle the obligation, then hard-exit (``os._exit(17)``) *inside* the
    adaptation consumer before any business plan is compiled. The checkpoint
    written just before exit is the proof of the committed boundary.
``startup-recover``
    Relaunch against the same scratch database and run the existing
    assignment recovery owner only. No source POST, no ``/advance``, no new
    objective, no injected plan/result.
``duplicate-source``
    Re-deliver the same accepted source after recovery; it must be inert.

Proposal transport is controlled (the repository's existing fixture pattern)
and authentication is the existing dependency override. No provider, model,
network, account, send or deployment action is used.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True)
    parser.add_argument("--scratch", required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--report", required=True)
    parser.add_argument("--checkpoint", default="")
    return parser.parse_args()


def _prepare_environment(scratch: Path) -> None:
    backend = Path(__file__).resolve().parents[2]
    os.environ["TESTING"] = "1"
    os.environ["ENVIRONMENT"] = "test"
    # `core.database.get_database_url` honors an explicit non-dev DATABASE_URL
    # for a pytest-importing process and otherwise forces the shared
    # backend/test_integration.db. This child is a real process but must use
    # the verifier's private scratch store, so declare the pytest marker
    # explicitly (no test module is imported; this only selects the DB path).
    os.environ["PYTEST_CURRENT_TEST"] = "task_wait_process_worker"
    os.environ["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY", "task-wait-process-recovery-test")
    os.environ["DATABASE_URL"] = f"sqlite:///{scratch / 'routes.db'}"
    os.environ["ATOM_DATA_DIR"] = str(scratch / "data")
    os.environ["ATOM_LANCEDB_PATH"] = str(scratch / "lancedb")
    os.environ["ATOM_ASSIGNMENT_OUTBOX"] = str(scratch / "outbox.jsonl")
    os.environ["ATOM_OFFICE_DIR"] = str(scratch)
    os.environ["ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS"] = "1"
    os.environ["ATOM_ASSIGNMENT_INTERNAL_FIXTURE_ROOT"] = str(
        scratch / "sources")
    os.environ["ATOM_EMPLOYEE_ADVANCE_DEADLINE_SECONDS"] = "30"
    os.environ["ENABLE_SCHEDULER"] = "false"
    os.environ["ATOM_EXECUTION_RECOVERY_ENABLED"] = "false"
    (scratch / "data").mkdir(parents=True, exist_ok=True)
    (scratch / "lancedb").mkdir(parents=True, exist_ok=True)
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))


def _write_json(path: str, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str, sort_keys=True))
    tmp.replace(target)


def _database():
    from core.database import SessionLocal, engine
    from core.models import Base, User

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        user = db.get(User, "lead-1")
        if user is None:
            user = User(
                id="lead-1", email="lead@example.com", hashed_password="x",
                first_name="L", last_name="One", role="team_lead",
                status="active", workspace_id="ws-1", tenant_id="tenant-1",
                is_active=True)
            db.add(user)
            db.commit()
        return user


def _lifecycle():
    from core.goals.goal_run_service import GoalRunService
    from core.goals.goal_service import GoalService
    from core.task_lifecycle import TaskLifecycle

    return TaskLifecycle(
        GoalRunService(workspace_id="ws-1", tenant_id="tenant-1"),
        GoalService(workspace_id="ws-1", tenant_id="tenant-1"))


def install_controlled_transport(calls: list) -> None:
    """The same controlled proposal fixture the in-process tests use."""
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
                    for index, source in enumerate(
                        context["sources"], 1)
                ],
            },
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    async def adaptation(context, observations, **kwargs):
        calls.append({
            "pid": os.getpid(),
            "at": time.time(),
            "observation_ids": [
                item["observation_id"] for item in observations],
            "business_roles": sorted(
                str(item.get("business_role") or "")
                for item in context.get("evidence_results", [])
                if item.get("business_role")),
        })
        roles = {
            str(item.get("business_role") or ""): item["step_id"]
            for item in context.get("evidence_results", [])
            if item.get("business_role")
        }
        common = {
            "reason": "select supported work from accepted records",
            "observation_ids": [
                item["observation_id"] for item in observations],
        }
        if all(roles.get(key) for key in (
                "invoice", "purchase_order", "receiving")):
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
        else:
            proposal = WorkAdaptationProposal(
                decision="clarify",
                clarification={
                    "question": (
                        "Which authorized source contains invoice "
                        "INV-TRIGGER-91 for purchase order PO-TRIGGER-63?"),
                    "concept": "invoice_reconciliation",
                    "unblocks": "invoice reconciliation",
                },
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


def build_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.assignment_routes import router
    from core.auth import get_current_user

    user = _database()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def _snapshot(lifecycle, run_id: str, calls: list) -> dict:
    from core.employee_job_runner import evidence_observations
    from core.task_lifecycle import open_unresolved_questions

    record = lifecycle.get_task(run_id) or {}
    assignment = record.get("assignment") or {}
    steps = []
    for step in assignment.get("steps") or []:
        result = step.get("result") if isinstance(
            step.get("result"), dict) else {}
        data = result.get("data") if isinstance(
            result.get("data"), dict) else {}
        steps.append({
            "step_id": step.get("step_id"),
            "adapter": step.get("adapter"),
            "status": step.get("status"),
            "operation_id": step.get("operation_id"),
            "source_version": (
                result.get("source_version") or result.get("version")),
            "result_value": result.get("value"),
            "result_data": data,
            "prior_results": len(step.get("prior_results") or []),
        })
    reconciliations = [
        step for step in steps
        if step["adapter"] == "invoice.reconcile"
        and step["status"] == "applied"
    ]
    source_steps = [
        step for step in steps
        if str(step["step_id"] or "").startswith("source-")
        and step["status"] == "applied"
    ]
    return {
        "run_id": run_id,
        "objective": assignment.get("objective"),
        "assignment_id": assignment.get("assignment_id"),
        "status": assignment.get("status"),
        "plan_revision": assignment.get("plan_revision"),
        "steps": steps,
        "source_steps": source_steps,
        "reconciliations": reconciliations,
        "open_questions": [
            {"question_id": item.get("question_id"),
             "kind": item.get("kind"),
             "operation": item.get("operation") or item.get("concept")}
            for item in open_unresolved_questions(record)
        ],
        "unresolved": (record.get("task_revision") or {}).get(
            "unresolved") or [],
        "evidence_observations": [
            {"observation_id": item.get("observation_id"),
             "step_id": item.get("step_id"),
             "shape": item.get("shape")}
            for item in evidence_observations(record)
        ],
        "provenance": assignment.get("provenance") or {},
        "recovery_marker": assignment.get("evidence_recovery") or {},
        "adaptation_calls": len(calls),
        "adaptation_call_log": calls,
    }


def _start(client, scratch: Path) -> dict:
    response = client.post(
        "/api/assignments/from-objective",
        json={
            "objective": (
                "Reconcile invoice INV-TRIGGER-91 for PO-TRIGGER-63"),
            "sources": [
                {"path": str(scratch / "sources" / "po.json")},
                {"path": str(scratch / "sources" / "receiving.json")},
            ],
            "authorized_actions": ["retrieve", "calculate"],
            "use_model": True,
        })
    if response.status_code != 200:
        raise RuntimeError(f"start failed: {response.status_code} {response.text}")
    return response.json()


def _add_invoice(client, run_id: str, scratch: Path):
    return client.post(
        f"/api/assignments/{run_id}/sources",
        json={
            "source": {"path": str(scratch / "sources" / "invoice.json")},
            "reason": "authorized source answers the invoice question",
        })


def main() -> int:
    args = _parse_args()
    scratch = Path(args.scratch).resolve()
    _prepare_environment(scratch)

    calls: list = []
    install_controlled_transport(calls)
    client = build_client()
    lifecycle = _lifecycle()

    if args.phase == "start":
        started = _start(client, scratch)
        run_id = started["run_id"]
        report = _snapshot(lifecycle, run_id, calls)
        report.update({"phase": args.phase, "pid": os.getpid()})
        _write_json(args.report, report)
        return 0

    if not args.run_id:
        raise RuntimeError("--run-id is required for this phase")

    if args.phase == "source-complete":
        answer = _add_invoice(client, args.run_id, scratch)
        report = _snapshot(lifecycle, args.run_id, calls)
        report.update({
            "phase": args.phase,
            "pid": os.getpid(),
            "source_response_status": answer.status_code,
            "source_response": (
                answer.json() if answer.headers.get(
                    "content-type", "").startswith("application/json")
                else answer.text),
        })
        _write_json(args.report, report)
        return 0

    if args.phase == "source-interrupt":
        import api.assignment_routes as routes

        async def interrupt_before_adaptation(executor, run_id, *a, **k):
            committed = _snapshot(executor.lifecycle, run_id, calls)
            committed.update({
                "phase": args.phase,
                "pid": os.getpid(),
                "interrupted_stage": "before_business_adaptation",
            })
            _write_json(args.checkpoint or args.report, committed)
            os._exit(17)

        routes._advance_employee_work = interrupt_before_adaptation
        _add_invoice(client, args.run_id, scratch)
        # The hard exit above is the expected path.
        _write_json(args.report, {
            "phase": args.phase, "pid": os.getpid(),
            "unexpected": "adaptation consumer was not reached"})
        return 19

    if args.phase == "startup-recover":
        from core.assignment_executor import AssignmentExecutor

        executor = AssignmentExecutor(lifecycle)
        entrypoint = "AssignmentExecutor.recover_ready_assignments"
        try:
            from core.assignment_recovery import (
                recover_active_assignments_at_startup,
            )
        except ImportError:
            recovered = asyncio_run(executor.recover_ready_assignments(
                limit=20, max_steps_per_assignment=12))
        else:
            entrypoint = (
                "core.assignment_recovery."
                "recover_active_assignments_at_startup")
            recovered = asyncio_run(
                recover_active_assignments_at_startup(
                    limit=20, max_steps_per_assignment=12))
        report = _snapshot(lifecycle, args.run_id, calls)
        report.update({
            "phase": args.phase,
            "pid": os.getpid(),
            "startup_entrypoint": entrypoint,
            "recovery_results": recovered,
        })
        _write_json(args.report, report)
        return 0

    if args.phase == "duplicate-source":
        answer = _add_invoice(client, args.run_id, scratch)
        report = _snapshot(lifecycle, args.run_id, calls)
        report.update({
            "phase": args.phase,
            "pid": os.getpid(),
            "source_response_status": answer.status_code,
            "source_response": (
                answer.json() if answer.headers.get(
                    "content-type", "").startswith("application/json")
                else answer.text),
        })
        _write_json(args.report, report)
        return 0

    if args.phase == "inspect":
        report = _snapshot(lifecycle, args.run_id, calls)
        report.update({"phase": args.phase, "pid": os.getpid()})
        _write_json(args.report, report)
        return 0

    raise RuntimeError(f"unknown phase {args.phase!r}")


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)


if __name__ == "__main__":
    sys.exit(main())
