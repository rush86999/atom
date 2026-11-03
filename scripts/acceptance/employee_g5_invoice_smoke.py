#!/usr/bin/env python3
"""Short served smoke for the invoice_reconciliation work request."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


def _scratch() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="atom-g5-invoice-"))
    os.environ.update({
        "TESTING": "1",
        "DATABASE_URL": f"sqlite:///{tmp}/atom.db",
        "ATOM_DATA_DIR": str(tmp / "data"),
        "LANCEDB_URI": str(tmp / "data" / "atom_memory"),
        "ATOM_OFFICE_DIR": str(tmp / "data" / "office"),
        "BYOK_KEYS_FILE": str(tmp / "byok_keys.json"),
        "BYOK_CONFIG_FILE": str(tmp / "byok_config.json"),
        "BYOK_ENC_KEY_FILE": str(tmp / "byok_encryption_key"),
        "ATOM_LOCAL_ONLY": "true",
        "ATOM_PRODUCT_PROFILE": "core",
        "ENABLE_SCHEDULER": "false",
        "ENABLE_INGESTION_SYNC": "false",
        "OLLAMA_CONTEXT_WINDOW": "16384",
    })
    (tmp / "data").mkdir(parents=True, exist_ok=True)
    return tmp


class RecordingLLM:
    def __init__(self, inner: Any, model: str, calls: List[Dict[str, Any]]):
        self.inner = inner
        self.model = model
        self.calls = calls

    async def generate_structured_response(self, **kwargs: Any) -> Any:
        kwargs.setdefault("provider_model", ("ollama", self.model))
        record = {
            "kind": "structured",
            "prompt": kwargs.get("prompt"),
            "system_instruction": kwargs.get("system_instruction"),
            "response_model": getattr(
                kwargs.get("response_model"), "__name__",
                str(kwargs.get("response_model"))),
            "output_mode": kwargs.get("output_mode"),
            "provider_model": list(kwargs.get("provider_model") or ()),
            "task_type": kwargs.get("task_type"),
            "attempt": len(self.calls) + 1,
        }
        started = time.time()
        try:
            result = await self.inner.generate_structured_response(**kwargs)
            record["parsed"] = (
                result.model_dump() if hasattr(result, "model_dump")
                else result)
            raw = getattr(result, "_raw_response", None)
            record["raw_available"] = raw is not None
            if raw is not None:
                record["raw"] = str(raw)[:20000]
            return result
        except Exception as exc:  # noqa: BLE001
            record["error_type"] = type(exc).__name__
            record["error"] = str(exc)[:12000]
            return None
        finally:
            record["seconds"] = round(time.time() - started, 3)
            self.calls.append(record)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11436/v1")
    parser.add_argument("--model", default="llama3.1:8b")
    parser.add_argument("--out", default="/private/tmp/atom-g5-invoice")
    parser.add_argument("--deadline", type=float, default=150.0)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    os.environ["OLLAMA_BASE_URL"] = args.ollama_url
    os.environ["OLLAMA_MODEL"] = args.model
    tmp = _scratch()

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.llm_service import LLMService
    from core.models import Base, GoalObjective, GoalRun, TaskOperationRecord
    from core.goals.goal_run_service import GoalRunService
    from core.goals.goal_service import GoalService
    from core.task_lifecycle import TaskLifecycle
    from core.assignment_executor import AssignmentExecutor, default_adapter_registry
    from core.assignment_plan import new_assignment, new_step
    from core.employee_proposal import context_from_record, propose_employee_work
    from core.employee_adaptation import propose_adaptation, adopt_adaptation
    from core.action_registry import action_registry
    import core.assignment_invoice  # noqa: F401
    import core.employee_work_compiler  # noqa: F401

    engine = create_engine(f"sqlite:///{tmp}/atom.db")
    Base.metadata.create_all(engine)
    for table in (GoalObjective.__table__, GoalRun.__table__,
                  TaskOperationRecord.__table__):
        table.create(engine, checkfirst=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    runs = GoalRunService(
        workspace_id="ws-g5", tenant_id="tenant-g5",
        session_factory=factory)
    goals = GoalService(
        workspace_id="ws-g5", tenant_id="tenant-g5",
        session_factory=factory)
    lifecycle = TaskLifecycle(runs, goals)
    executor = AssignmentExecutor(
        lifecycle, adapters=default_adapter_registry.clone())

    bill_calls: List[Dict[str, Any]] = []

    async def create_bill(arguments, context):
        bill_calls.append(dict(arguments))
        return {
            "status": "applied", "action_result": "applied",
            "provider_state": "accepted", "provider_ref": "bill-1",
            "remote_id": "bill-1",
            "verification": {"status": "verified"},
            "data": {"bill_id": "bill-1", "total": arguments.get("total")},
        }

    action_registry.register(
        "books.create_bill", create_bill,
        effects=[{"effect": "create", "object": "bill"}])

    def applied(step_id, adapter, data):
        step = new_step(
            step_id=step_id, title=step_id, operation_type="retrieve",
            adapter=adapter, inputs={}, effect="read_only")
        step.update(status="applied", operation_id=f"op-{step_id}",
                    result={
                        "data": data,
                        "resource_id": f"{step_id}-1",
                        "source_version": f"{step_id}-v1",
                        "coverage": {"complete": True, "known": True,
                                     "truncated": False},
                        "verification": {
                            "status": "verified",
                            "resource_id": f"{step_id}-1",
                            "version": f"{step_id}-v1",
                            "coverage": {"complete": True,
                                         "truncated": False}},
                    })
        return step

    steps = [
        applied("purchase-order", "document.read", {
            "po_id": "PO-7", "vendor_id": "V-9"}),
        applied("invoice", "document.read", {
            "invoice_id": "INV-7", "po_id": "PO-7", "quantity": "2",
            "unit_price": "120.00", "freight": "30.00",
            "currency": "USD"}),
        applied("receiving", "workbook.read", {
            "po_id": "PO-7", "received_quantity": "2"}),
    ]
    plan = new_assignment(
        objective=(
            "Reconcile the supplier invoice against the approved purchase "
            "order and receiving evidence and prepare only the supported bill"),
        employee_id="employee-books-1", workspace_id="ws-g5",
        tenant_id="tenant-g5", steps=steps,
        authorized_actions=["retrieve", "calculate", "outbound"],
        completion_criteria=[{"kind": "required_work_complete"}])
    record = executor.create_assignment(
        "conv-g5-invoice", plan["objective"], assignment=plan)
    run_id = record["run_id"]
    context = context_from_record(
        record,
        action_views=[{"action": "books.create_bill",
                       "effect": "external",
                       "description": "Create one reviewed bill"}])
    db = factory()
    llm = RecordingLLM(
        LLMService(db=db, workspace_id="ws-g5", tenant_id="tenant-g5"),
        args.model, calls=[])
    deadline = time.monotonic() + args.deadline
    proposal = await propose_adaptation(
        context,
        [{"observation_id": "invoice-evidence-1",
          "kind": "evidence_result", "step_id": "invoice",
          "reason": "PO, invoice and receiving evidence are accepted"}],
        assignment=record["assignment"], llm_service=llm,
        provider_model=("ollama", args.model), deadline=deadline)
    report: Dict[str, Any] = {
        "schema": "atom-g5-invoice-smoke-1",
        "provider": {"base_url": args.ollama_url, "model": args.model},
        "proposal": proposal,
        "adoption": None,
        "execution": None,
        "bill_calls": bill_calls,
        "calls": llm.calls,
    }
    if proposal.get("proposal"):
        try:
            adopted = adopt_adaptation(
                lifecycle, run_id, proposal["proposal"])
            report["adoption"] = adopted
            status = await executor.execute(run_id, max_steps=12)
            assignment = lifecycle.get_assignment(run_id)
            for step in assignment.get("steps") or []:
                if step.get("status") == "awaiting_approval":
                    executor.approve_step(
                        run_id, step["step_id"], approved_by="owner")
            status = await executor.execute(run_id, max_steps=12)
            report["execution"] = status
            report["reconcile_value"] = next((
                (step.get("result") or {}).get("value")
                for step in assignment.get("steps") or []
                if step.get("adapter") == "invoice.reconcile"), None)
            report["bill_calls"] = bill_calls
        except Exception as exc:  # noqa: BLE001
            report["adoption_error"] = f"{type(exc).__name__}: {exc}"
    (out / "report.json").write_text(json.dumps(report, indent=1, default=str))
    with (out / "calls.jsonl").open("w") as handle:
        for call in llm.calls:
            handle.write(json.dumps(call, default=str) + "\n")
    print(json.dumps({
        "source": proposal.get("source"),
        "decision": (proposal.get("proposal") or {}).get("decision"),
        "work_request": (proposal.get("proposal") or {}).get("work_request"),
        "adoption": (report.get("adoption") or {}).get("status"),
        "adoption_error": report.get("adoption_error"),
        "reconcile_value": report.get("reconcile_value"),
        "bill_calls": len(bill_calls),
        "calls": len(llm.calls),
    }, indent=1, default=str))
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
