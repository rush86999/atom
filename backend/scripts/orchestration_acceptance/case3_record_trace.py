#!/usr/bin/env python3
"""Case-3 record-pipeline trace (owner directive 2026-10-06, items 1-2).

Reproduces the failed trial's EXACT planner queries in an isolated
in-memory fixture seeded with the REAL teaching (verbatim lesson
1451b758 from the dev agent 9837ec71), then traces one operation
through: selected tool -> executor branch -> engine invocation ->
structured-record publication -> job attachment/write -> block content.

Every transition is OBSERVED (wrapped), never inferred from absence.
Run:
  venv314/bin/python scripts/orchestration_acceptance/case3_record_trace.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))
os.environ["ATOM_TASK_LIFECYCLE_ENABLED"] = "1"
os.environ["TESTING"] = "1"

# Scratch in-memory DB ONLY (never the live dev DB).
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models import Base, AgentRegistry

engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                       poolclass=StaticPool)
Base.metadata.create_all(engine)
_factory = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def _scratch_db():
    s = _factory()
    try:
        yield s
        s.commit()
    finally:
        s.close()


import core.database as _dbmod
_dbmod.get_db_session = _scratch_db

# The REAL teaching, verbatim from the dev world (agent 9837ec71,
# configuration.learning.log entry 1451b758...): the failed trial's
# correct figures came from THIS lesson's formula + default rate.
LESSON = {
    "id": "1451b758f7964e1a9d1878704b7ce054",
    "source": "teacher", "teacher_agent_id": "human_supervisor",
    "topic": "service estimates",
    "lesson": ("Service estimate: estimate = ROUNDUP(hours * rate + "
               "materials, 0). Our service rate is 150 per hour."),
    "learned_at": "2026-10-06T13:22:44.344495+00:00", "scope": "global",
}

USER = f"u-trace-{uuid.uuid4().hex[:8]}"
WS = "default"
CONV = f"c3-trace-{uuid.uuid4().hex[:8]}"

# The planner-shaped queries from the failed trial (dev server log):
Q_T1 = "Estimate this service job using our taught rates."
Q_T2 = ("Estimate this service job using our taught rates "
        "with hours=17.5 materials=0")
Q_T3 = ("Estimate this service job using our taught rates "
        "with hours=12 materials=0")

TRACE: list = []


def _seed() -> None:
    with _scratch_db() as db:
        db.add(AgentRegistry(
            id="trace-agent-9837ec71", name="trace Brennan agent",
            status="active", category="trainee",
            module_path="agents.trace_fixture", class_name="TraceAgent",
            configuration={"learning": {"log": [LESSON]}}))


def _instrument() -> None:
    """Wrap every transition point; record entry/exit, never infer."""
    import core.pricing_calculation as P

    def wrap_async(mod_name, name):
        orig = getattr(P, name)

        async def wrapper(*a, **kw):
            TRACE.append({"t": "enter", "fn": name,
                          "args": [str(x)[:60] for x in a[:1]]})
            out = await orig(*a, **kw)
            TRACE.append({"t": "exit", "fn": name,
                          "ret": (out[:160] if isinstance(out, str)
                                  else repr(out)[:80])})
            return out
        setattr(P, name, wrapper)
        return orig

    for name in ("calculate_workbook_from_query",
                 "calculate_expression_from_query",
                 "calculate_natural_from_query",
                 "calculate_from_query"):
        if hasattr(P, name):
            wrap_async(P, name)

    # record publication + job write are sync module-level functions.
    # (Bind orig/name through default args: a plain closure over the
    # loop variable made BOTH wrappers call the LAST function —
    # _publish_calc_record invoked _record_on_job and raised a bogus
    # "multiple values for conversation_id" TypeError, a trace artifact
    # that masqueraded as a product bug.)
    for name in ("_publish_calc_record", "_record_on_job"):
        orig = getattr(P, name)

        def wrapper(*a, _orig=orig, _name=name, **kw):
            TRACE.append({"t": "enter", "fn": _name,
                          "conv": str(kw.get("conversation_id")
                                      or (a[0] if a else ""))[:40]})
            out = _orig(*a, **kw)
            TRACE.append({"t": "exit", "fn": _name, "ret": repr(out)[:60]})
            return out
        setattr(P, name, wrapper)

    # engine invocation
    import core.formula_engine as FE
    _orig_eval = FE.evaluate_expression

    def eval_wrapper(expr, inputs):
        TRACE.append({"t": "engine", "fn": "evaluate_expression",
                      "expr": expr, "inputs": dict(inputs)})
        out = _orig_eval(expr, inputs)
        TRACE.append({"t": "engine-out", "status": out.status,
                      "value": str(out.value)})
        return out
    FE.evaluate_expression = eval_wrapper
    # pricing_calculation imports evaluate_expression inside functions
    # (fresh import at call time), so patching the engine module is
    # enough.


def _inspect_job() -> dict:
    from core.task_lifecycle import TaskLifecycle
    from core.goals.goal_run_service import GoalRunService
    from core.goals.goal_service import GoalService
    tl = TaskLifecycle(GoalRunService(workspace_id=WS, tenant_id="default",
                                      session_factory=_scratch_db),
                       GoalService(workspace_id=WS, tenant_id="default",
                                   session_factory=_scratch_db))
    task = tl.find_active_task(CONV)
    if not task:
        return {"task": None}
    ops = [{"type": o.get("operation_type"), "status": o.get("status")}
           for o in (task.get("operations") or [])]
    return {"task": task.get("run_id"), "ops": ops}


async def main() -> int:
    _seed()
    _instrument()
    from core.chat_tool_planner import ToolPlan, execute_tool_plan

    for label, q in (("T1-missing-input", Q_T1),
                     ("T2-answered-inputs", Q_T2),
                     ("T3-changed-input", Q_T3)):
        TRACE.append({"t": "turn", "label": label, "query": q})
        plan = ToolPlan(use_tool=True, service="datasets.calculate",
                        intent="calculate", query=q)
        block = await execute_tool_plan(
            plan, USER, tenant_id="default",
            context={"conversation_id": CONV, "workspace_id": WS})
        TRACE.append({"t": "block", "label": label,
                      "head": (block or "")[:220]})
    print(json.dumps(TRACE, indent=1, default=str))
    print("JOB:", json.dumps(_inspect_job(), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
