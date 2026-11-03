#!/usr/bin/env python3
"""One served G5 adaptive-choice probe through the production consumers.

This is a bounded qualification probe, not a campaign. It starts from an
objective/source context, records the actual model proposal, then gives the
model the observed evidence rows and records whether it proposes supported
calculation work. Invalid/unsafe proposals are preserved, not relabelled.

Usage:
  python scripts/acceptance/employee_g5_served_probe.py \
    --ollama-url http://127.0.0.1:11436/v1 --model llama3.1:8b \
    --out /private/tmp/atom-g5-served
"""
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
    tmp = Path(tempfile.mkdtemp(prefix="atom-g5-served-"))
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
            "temperature": kwargs.get("temperature"),
            "output_mode": kwargs.get("output_mode"),
            "provider_model": list(kwargs.get("provider_model") or ()),
            "task_type": kwargs.get("task_type"),
        }
        started = time.time()
        try:
            result = await self.inner.generate_structured_response(**kwargs)
            record["parsed"] = (
                result.model_dump() if hasattr(result, "model_dump")
                else result)
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
    parser.add_argument("--out", default="/private/tmp/atom-g5-served")
    parser.add_argument("--deadline", type=float, default=90.0)
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
    import core.quote_rows  # noqa: F401  (registers quote.lines_from_rows)
    from core.employee_proposal import (
        build_employee_context, context_from_record, propose_employee_work,
    )
    from core.employee_adaptation import propose_adaptation, adopt_adaptation

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

    source_view = {
        "resource_id": "heldout:price-book.xlsx",
        "kind": "workbook", "representation": "xlsx",
        "file_name": "price-book.xlsx", "sheet": "Prices",
        "columns": ["Item", "Qty", "Price", "Currency"],
        "numeric_columns": ["Qty", "Price"],
        "source_version": "heldout-v1",
        "coverage": {"known": True, "truncated": False},
    }
    initial_context = build_employee_context(
        objective="Quote the held-out customer request using approved prices",
        employee_id="employee-1", workspace_id="ws-g5",
        tenant_id="tenant-g5", sources=[source_view],
        authorized_actions=["retrieve", "calculate"],
        budget={"max_steps": 20},
    )
    db = factory()
    llm = RecordingLLM(
        LLMService(db=db, workspace_id="ws-g5", tenant_id="tenant-g5"),
        args.model, calls=[])
    try:
        initial = await asyncio.wait_for(propose_employee_work(
            initial_context, llm_service=llm,
            provider_model=("ollama", args.model)), timeout=args.deadline)
    except asyncio.TimeoutError:
        initial = {
            "proposal": None, "source": "timeout",
            "technical_fallback": False,
            "errors": ["deadline_exceeded: initial proposal"],
        }

    read = new_step(
        step_id="read", title="Read the held-out price book",
        operation_type="retrieve", adapter="workbook.read",
        inputs={}, effect="read_only")
    read["status"] = "applied"
    read["operation_id"] = "op-g5-read"
    read["result"] = {
        "rows": [
            {"Item": "A", "Qty": 2, "Price": 100, "Currency": "USD"},
            {"Item": "B", "Qty": 3, "Price": 50, "Currency": "USD"},
        ],
        "schema": [{"column": "Item"}, {"column": "Qty"},
                   {"column": "Price"}, {"column": "Currency"}],
        "coverage": {"complete": True, "known": True, "truncated": False},
        "source_version": "heldout-v1",
    }
    plan = new_assignment(
        objective="Quote the held-out customer request using approved prices",
        employee_id="employee-1", workspace_id="ws-g5",
        tenant_id="tenant-g5", steps=[read],
        authorized_actions=["retrieve", "calculate"],
        completion_criteria=[{"kind": "required_work_complete"}])
    created = executor.create_assignment(
        "conv-g5-heldout", plan["objective"], assignment=plan)
    run_id = created["run_id"]
    record = lifecycle.get_task(run_id)
    context = context_from_record(
        record,
        adapter_views=[
            {
                "adapter": "quote.lines_from_rows", "effect": "local",
                "operation_type": "calculate",
                "required_actions": ["calculate"],
                "input_schema": {
                    "rows": "rows from the completed read",
                    "columns": {"item_id": "column", "quantity": "column",
                                "unit_price": "column",
                                "currency": "column"},
                    "defaults": {"currency": "USD"},
                },
            },
            {
                "adapter": "quote.calculate", "effect": "local",
                "operation_type": "calculate",
                "required_actions": ["calculate"],
                "input_schema": {
                    "line_items": "reference lines.line_items",
                    "currency": "USD", "freight": "decimal string",
                    "tax": {"basis": "none"},
                },
            },
        ])
    observation = {
        "observation_id": "heldout-read-1",
        "kind": "evidence_result",
        "step_id": "read",
        "reason": "the authorized price rows were read",
    }
    try:
        proposal = await asyncio.wait_for(propose_adaptation(
            context, [observation], assignment=record["assignment"],
            llm_service=llm, provider_model=("ollama", args.model)),
            timeout=args.deadline)
    except asyncio.TimeoutError:
        proposal = {
            "proposal": None, "source": "timeout",
            "technical_fallback": False,
            "errors": ["deadline_exceeded: evidence adaptation"],
        }
    report: Dict[str, Any] = {
        "schema": "atom-g5-served-probe-1",
        "provider": {
            "base_url": args.ollama_url,
            "model": args.model,
            "pin": f"ollama:{args.model}",
        },
        "initial_proposal": initial,
        "evidence_proposal": proposal,
        "calls": llm.calls,
        "adoption": None,
        "execution": None,
    }
    rounds = []
    current = proposal
    for round_index in range(4):
        if current.get("source") not in ("model", "model_repaired"):
            break
        if not current.get("proposal"):
            break
        item = {
            "round": round_index,
            "proposal": current.get("proposal"),
            "source": current.get("source"),
        }
        try:
            adopted = adopt_adaptation(
                lifecycle, run_id, current["proposal"],
                rationale="served G5 evidence adaptation")
            status = await executor.execute(run_id, max_steps=12)
            item["adoption"] = {
                "status": adopted.get("status"),
                "affected": adopted.get("affected_steps"),
                "updated": adopted.get("updated_steps"),
            }
            item["execution_status"] = (
                (status.get("assignment") or {}).get("status"))
            assignment = lifecycle.get_assignment(run_id)
            item["calculated_value"] = next((
                (step.get("result") or {}).get("value")
                for step in assignment.get("steps") or []
                if step.get("adapter") == "quote.calculate"), None)
        except Exception as exc:  # noqa: BLE001
            item["adoption_error"] = f"{type(exc).__name__}: {exc}"
            rounds.append(item)
            break
        rounds.append(item)
        record = lifecycle.get_task(run_id)
        assignment = record.get("assignment") or {}
        if assignment.get("status") in ("completed", "failed", "cancelled"):
            break
        from core.task_lifecycle import open_unresolved_questions
        if open_unresolved_questions(record):
            break
        context = context_from_record(
            record,
            adapter_views=[
                {"adapter": "quote.lines_from_rows", "effect": "local",
                 "operation_type": "calculate",
                 "required_actions": ["calculate"],
                 "input_schema": {
                     "rows": "array of source row objects; use ${read.rows}",
                     "columns": "mapping item_id/quantity/unit_price/currency "
                                "to source column names",
                     "defaults": "object, e.g. {currency: USD}"}},
                {"adapter": "quote.calculate", "effect": "local",
                 "operation_type": "calculate",
                 "required_actions": ["calculate"],
                 "input_schema": {
                     "line_items": "array; reference the mapping step's "
                                   "line_items result with ${step_id.line_items}",
                     "currency": "explicit ISO currency",
                     "freight": "explicit decimal",
                     "tax": "explicit descriptor, e.g. {basis: none}"}},
            ])
        try:
            current = await asyncio.wait_for(propose_adaptation(
                context,
                [{"observation_id": f"round-{round_index + 1}",
                  "kind": "evidence_result",
                  "reason": "the newly adopted steps completed"}],
                assignment=assignment, llm_service=llm,
                provider_model=("ollama", args.model)),
                timeout=args.deadline)
        except asyncio.TimeoutError:
            rounds.append({
                "round": round_index + 1,
                "source": "timeout",
                "proposal": None,
                "error": "deadline_exceeded: next adaptation",
            })
            break
    report["rounds"] = rounds
    if rounds:
        last = rounds[-1]
        report["adoption"] = last.get("adoption")
        report["adoption_error"] = last.get("adoption_error")
        report["calculated_value"] = last.get("calculated_value")
    (out / "report.json").write_text(json.dumps(report, indent=1) + "\n")
    with (out / "calls.jsonl").open("w") as handle:
        for call in llm.calls:
            handle.write(json.dumps(call, default=str) + "\n")
    print(json.dumps({
        "initial_source": initial.get("source"),
        "initial_kind": (initial.get("proposal") or {}).get("proposal_kind"),
        "evidence_source": proposal.get("source"),
        "evidence_decision": (proposal.get("proposal") or {}).get("decision"),
        "adoption_error": report.get("adoption_error"),
        "calculated_value": report.get("calculated_value"),
        "calls": len(llm.calls),
    }, indent=1))
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
