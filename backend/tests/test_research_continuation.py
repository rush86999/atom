# -*- coding: utf-8 -*-
"""Durable research continuation (round 52): the recurring worker that
finishes authorized read jobs after the interactive turn ends."""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models import GoalObjective, GoalRun, TaskOperationRecord
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_service import GoalService
from core.task_lifecycle import TaskLifecycle


@pytest.fixture
def lifecycle(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/rc_test.db")
    for table in (GoalObjective.__table__, GoalRun.__table__,
                  TaskOperationRecord.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return TaskLifecycle(
        GoalRunService(workspace_id="ws", tenant_id="t",
                       session_factory=factory),
        GoalService(workspace_id="ws", tenant_id="t",
                    session_factory=factory))


@pytest.mark.asyncio
async def test_cycle_executes_queued_read_and_retires(lifecycle,
                                                      monkeypatch):
    """A job with an eligible pending read gets it executed by ONE cycle,
    the question retires, and a second cycle does not duplicate (the
    completed action is no longer selected)."""
    from core.task_lifecycle import (
        begin_retrieval_turn, next_unfinished_work, record_read_outcome)
    from core import research_continuation as rc

    run_id, op = begin_retrieval_turn(
        lifecycle, {"id": "s1"}, "conv-rc", "verify pricing", "e1")
    record_read_outcome(
        lifecycle, run_id, op, structured_result=None, freshness=None,
        execution=None, extra_questions=[{
            "item": "Manual Flanger", "kind": "verification",
            "question": "Manual Flanger is carried by X — not yet read",
            "evidence": "value_trace coverage",
            "next_action": "read X.xlsx for Manual Flanger"}])

    executed = {"n": 0}

    async def fake_exec(plan, user_id, tenant_id="default", context=None,
                        llm_service=None):
        executed["n"] += 1
        assert plan.service == "datasets" and plan.intent == "read"
        plan._result_meta = {"storage_read": {"file_name": "X.xlsx"}}
        return "LIVE TOOL RESULTS — the workbook cells"

    # The REAL _execute_one_read runs (settling on the job's run); only
    # the executor is faked at its module boundary.
    monkeypatch.setattr(rc, "_lifecycle_for_default_tenant",
                        lambda: lifecycle)
    monkeypatch.setattr(
        "core.chat_tool_planner.execute_tool_plan", fake_exec)

    class StubMgr:
        def get_session(self, sid):
            return {"user_id": "u1", "workspace_id": "ws",
                    "agent_id": "a1", "history": []}

        def update_session_activity(self, sid, history=None,
                                    last_message=None):
            pass

    monkeypatch.setattr(
        "core.chat_session_manager.chat_session_manager", StubMgr())

    out = await rc.research_continuation_cycle()
    assert executed["n"] == 1, "one grouped read executed"
    assert out["reads"] == 1 and out["completed_items"] == 1

    # The read question retired via the settle — the action must no
    # longer be selected; a second cycle executes nothing.
    out2 = await rc.research_continuation_cycle()
    assert out2["reads"] == 0, "no duplicate execution of completed work"


@pytest.mark.asyncio
async def test_cycle_respects_missing_identity(lifecycle, monkeypatch):
    """No session identity -> the job is left durable and listed; nothing
    executes (authorization + identity discipline)."""
    from core.task_lifecycle import (
        begin_retrieval_turn, record_read_outcome)
    from core import research_continuation as rc

    run_id, op = begin_retrieval_turn(
        lifecycle, {"id": "s1"}, "conv-rc2", "verify", "e1")
    record_read_outcome(
        lifecycle, run_id, op, structured_result=None, freshness=None,
        execution=None, extra_questions=[{
            "item": "X", "kind": "verification",
            "question": "X is carried by Y — not yet read",
            "evidence": "vt", "next_action": "read Y.xlsx for X"}])

    monkeypatch.setattr(rc, "_lifecycle_for_default_tenant",
                        lambda: lifecycle)

    class NoSessionMgr:
        def get_session(self, sid):
            return None

    monkeypatch.setattr(
        "core.chat_session_manager.chat_session_manager", NoSessionMgr())
    out = await rc.research_continuation_cycle()
    assert out["reads"] == 0


@pytest.mark.asyncio
async def test_worker_start_is_idempotent():
    from core import research_continuation as rc

    async def scenario():
        first = rc.start_research_continuation()
        second = rc.start_research_continuation()
        await rc.stop_research_continuation()
        return first, second

    first, second = await asyncio.wait_for(scenario(), timeout=10)
    assert first is True and second is False, "idempotent start"
