"""Tool-plan → calculate-lane boundary regressions (release case 3).

The failed trial (2026-10-06, manifest BRENNAN_RELEASE_MANIFEST) proved a
planner-shaped datasets.calculate plan could bypass the local lanes and the
whole calculation-record pipeline: the dotted service name fell through to
the generic external-integration branch, whose failure block let the model
self-compute the figure in narration — correct-looking reply, no engine
run, no structured record, no job operation.

These tests pin the SHARED boundary (owner directive 3-4): every
planner-shaped datasets.* plan reaches the same local lanes the derivation
path uses; one request = one recorded calculation operation with its own
inputs; narration alone never satisfies the gate.
"""
from __future__ import annotations

import asyncio
import os
from contextlib import contextmanager

os.environ.setdefault("ATOM_TASK_LIFECYCLE_ENABLED", "1")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models import AgentRegistry, Base, User

LESSON_RATE_150 = {
    "id": "1451b758f7964e1a9d1878704b7ce054",
    "source": "teacher", "teacher_agent_id": "human_supervisor",
    "topic": "service estimates",
    "lesson": ("Service estimate: estimate = ROUNDUP(hours * rate + "
               "materials, 0). Our service rate is 150 per hour."),
    "learned_at": "2026-10-06T13:22:44.344495+00:00", "scope": "global",
}
LESSON_RATE_200 = {
    **LESSON_RATE_150, "id": "rate200-lesson-0001",
    "lesson": ("Service estimate: estimate = ROUNDUP(hours * rate + "
               "materials, 0). Our service rate is 200 per hour."),
}

Q_MISSING = "Estimate this service job using our taught rates."
Q_175 = ("Estimate this service job using our taught rates "
         "with hours=17.5 materials=0")
Q_12 = ("Estimate this service job using our taught rates "
        "with hours=12 materials=0")

_STATE = {}


@pytest.fixture()
def world():
    """Scratch in-memory DB + one trained agent carrying the REAL
    teaching (verbatim lesson from the dev agent). Never the live DB."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def scratch():
        s = factory()
        try:
            yield s
            s.commit()
        finally:
            s.close()

    import core.database as dbmod
    old = dbmod.get_db_session
    dbmod.get_db_session = scratch
    with scratch() as db:
        db.add(User(id="u-boundary", email="boundary@example.com",
                    first_name="Boundary", last_name="Test", role="user",
                    status="active"))
        db.add(AgentRegistry(
            id="boundary-agent", name="boundary agent", status="active",
            category="trainee", module_path="agents.boundary",
            class_name="BoundaryAgent",
            configuration={"learning": {"log": [LESSON_RATE_150]}}))
    _STATE["factory"] = factory
    yield {"user": "u-boundary", "ws": "default"}
    dbmod.get_db_session = old
    engine.dispose()


def _plan(query, service="datasets.calculate"):
    from core.chat_tool_planner import ToolPlan
    return ToolPlan(use_tool=True, service=service, query=query)


def _run(plan, conv, user="u-boundary"):
    from core.chat_tool_planner import execute_tool_plan
    return asyncio.run(execute_tool_plan(
        plan, user, tenant_id="default",
        context={"conversation_id": conv, "workspace_id": "default"}))


def _job_ops(conv):
    from core.goals.goal_run_service import GoalRunService
    from core.goals.goal_service import GoalService
    from core.task_lifecycle import TaskLifecycle
    factory = _STATE["factory"]
    tl = TaskLifecycle(
        GoalRunService(workspace_id="default", tenant_id="default",
                       session_factory=factory),
        GoalService(workspace_id="default", tenant_id="default",
                    session_factory=factory))
    task = tl.find_active_task(conv)
    if not task:
        return []
    out = []
    for o in (task.get("operations") or []):
        # attach_operation_field merges keys FLAT onto the operation
        # record (op["calculation"]), not under an "extra" envelope
        calc = o.get("calculation") or {}
        proposed = calc.get("proposed")
        if isinstance(proposed, dict):
            value = proposed.get("amount")
        else:
            value = getattr(proposed, "amount", proposed)
        # to_record() serializes inputs_snapshot as "inputs", whose own
        # "inputs" key carries the name→value bindings
        snap = calc.get("inputs") or {}
        bindings = snap.get("inputs") or snap
        out.append({"type": o.get("operation_type"),
                    "status": o.get("status"),
                    "value": value,
                    "inputs": bindings})
    return out


def test_dotted_service_reaches_local_lanes(world):
    """The trial-1 failure shape: service='datasets.calculate' must run
    the LOCAL calculate lanes (grounded engine block), never the generic
    external branch's 'nothing usable' failure block."""
    block = _run(_plan(Q_175), "c-boundary-1")
    assert block and "LIVE TOOL RESULTS" in block
    assert "datasets.calculate" in block
    # the external branch's failure shape must be absent
    assert "returned nothing usable" not in block
    assert "not supported" not in block
    # the engine — not the model — produced the value
    assert "the model did not compute this" in block


def test_missing_input_asks_and_records_nothing(world):
    block = _run(_plan(Q_MISSING), "c-boundary-2")
    assert block and "INPUT NEEDED" in block
    assert "hours" in block and "materials" in block
    assert _job_ops("c-boundary-2") == []


def test_answered_inputs_compute_and_record_one_operation(world):
    block = _run(_plan(Q_175), "c-boundary-3")
    assert block and ("2625" in block or "2,625" in block)
    ops = _job_ops("c-boundary-3")
    calc = [o for o in ops if o["type"] == "calculate"]
    assert len(calc) == 1
    assert calc[0]["status"] == "applied"
    assert str(calc[0]["value"]).startswith("2625")
    assert calc[0]["inputs"].get("hours") == "17.5"
    assert calc[0]["inputs"].get("materials") == "0"


def test_changed_input_recalc_is_its_own_operation(world):
    _run(_plan(Q_175), "c-boundary-4")
    _run(_plan(Q_12), "c-boundary-4")
    calc = [o for o in _job_ops("c-boundary-4") if o["type"] == "calculate"]
    assert len(calc) == 2
    values = sorted(str(c["value"]) for c in calc)
    assert values == ["1800", "2625"]
    # each op carries ITS OWN inputs
    ins = {c["inputs"].get("hours") for c in calc}
    assert ins == {"12", "17.5"}


def test_duplicate_dispatch_does_not_duplicate_operations(world):
    _run(_plan(Q_175), "c-boundary-5")
    _run(_plan(Q_175), "c-boundary-5")
    calc = [o for o in _job_ops("c-boundary-5") if o["type"] == "calculate"]
    assert len(calc) == 1


def test_two_conversations_use_their_own_teaching(world):
    """Two conversations, different taught rates: each computes and
    records from ITS OWN lesson — no cross-conversation record reuse."""
    import core.database as dbmod
    with dbmod.get_db_session() as db:
        db.query(AgentRegistry).filter(
            AgentRegistry.id == "boundary-agent").update(
            {"configuration": {"learning": {"log": [LESSON_RATE_200]}}})
    block = _run(_plan(Q_175), "c-boundary-6")
    assert block and "3500" in block
    ops6 = [o for o in _job_ops("c-boundary-6") if o["type"] == "calculate"]
    assert len(ops6) == 1
    assert str(ops6[0]["value"]).startswith("3500")
