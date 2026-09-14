"""Regression tests for the GoalRun review bugs (2026-09-10):

1. A human checkpoint must OWN the cursor until it is resolved — creating
   the checkpoint must not advance it (approval advanced a second time and
   silently skipped the first step after the checkpoint).
2. ``SKIP`` must return its structured result — the handler block sat after
   an unconditional ``return`` and ``execute`` returned ``None``.
3. Approving a guardrail-forced hold must replay the ORIGINAL decision
   (replan budget, WAIT ceiling, failed DONE criteria) instead of no-op'ing.
4. ``/api/goal-runs/events`` is supervisor-gated (covered in
   test_goal_run_routes.py — route-level).
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")

from core.models import (Base, Canvas, CanvasAudit, GoalObjective, GoalRun,
                         HITLAction)
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_run_executors import GoalRunExecutors


@pytest.fixture()
def backend(tmp_path, monkeypatch):
    # Terminal notifications/learning are fire-and-forget in prod; silence
    # them here so no task is left pending when asyncio.run() closes.
    async def _noop_outcome(service, run, outcome):
        return None

    monkeypatch.setattr(
        "core.goals.goal_run_learning.record_run_outcome", _noop_outcome)
    monkeypatch.setattr(
        "core.goals.goal_run_notifications.schedule_notification",
        lambda coro: coro.close() if hasattr(coro, "close") else None)

    engine = create_engine(f"sqlite:///{tmp_path}/goal_run_bugfixes.db")
    for table in (GoalObjective.__table__, GoalRun.__table__,
                  Canvas.__table__, CanvasAudit.__table__, HITLAction.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    svc = GoalRunService(workspace_id="ws_test", tenant_id="t_test",
                         session_factory=factory)
    with factory() as session:
        session.add(GoalObjective(
            id="goal-1", workspace_id="ws_test", tenant_id="t_test",
            title="Prepare a quote for the Acme lead", status="active",
            criteria=[], key_results=[]))
        session.commit()

    def make(plan=None, **kw):
        rid = svc.create_run("goal-1", plan=plan or PLAN, **kw)["id"]
        svc.transition(rid, "active")
        return rid

    return svc, factory, make


PLAN = [
    {"id": "s1", "kind": "canvas_work", "title": "Research"},
    {"id": "s2", "kind": "human_checkpoint", "title": "Quote approval"},
    {"id": "s3", "kind": "canvas_work", "title": "Post-approval work"},
    {"id": "s4", "kind": "canvas_work", "title": "Send"},
]


def advance(svc, rid, decision, **kw):
    return asyncio.run(svc.advance(rid, router=_Stub(decision), **kw))


class _Stub:
    def __init__(self, decision):
        self.decision = decision

    async def decide(self, context):
        return self.decision


# --------------------------------------------------------------- bug 1

def test_checkpoint_owns_cursor_until_resolved(backend):
    svc, _, make = backend
    rid = make(plan=PLAN)
    advance(svc, rid, {"decision": "ADVANCE", "rationale": "research",
                       "confidence": 0.9})
    advance(svc, rid, {"decision": "ADVANCE", "rationale": "checkpoint",
                       "confidence": 0.9})
    run = svc.get_run(rid)
    assert run["status"] == "waiting"
    # The unresolved checkpoint owns the cursor — it must NOT have moved to s3.
    assert run["cursor"] == "s2"

    hitl_id = run["waiting_on"]["match"]["hitl_id"]
    svc.consume_wake(rid, {"event": "human_checkpoint", "hitl_id": hitl_id,
                           "approved": True})
    svc.complete_checkpoint(rid, step_id="s2")
    run = svc.get_run(rid)
    # Approval moves the cursor exactly one step: s3 must not be skipped.
    assert run["cursor"] == "s3"
    assert [s.get("done") for s in run["plan"]] == [None, True, None, None]


# --------------------------------------------------------------- bug 2

def test_skip_over_checkpoint_still_advances(backend):
    """The cursor guard is scoped to ADVANCE: a router SKIP on a checkpoint
    step must still skip it (and must not create a HITL wait)."""
    svc, _, make = backend
    rid = make(plan=PLAN)
    advance(svc, rid, {"decision": "ADVANCE", "rationale": "research",
                       "confidence": 0.9})   # s1 -> cursor s2
    out = advance(svc, rid, {"decision": "SKIP", "rationale": "approval not needed",
                             "confidence": 0.9})
    assert out["decision"] == "SKIP"
    run = svc.get_run(rid)
    assert run["status"] == "active"
    assert run["cursor"] == "s3"


def test_skip_returns_structured_result(backend):
    svc, _, make = backend
    rid = make(plan=PLAN)
    out = asyncio.run(GoalRunExecutors(svc).execute(
        svc.get_run(rid), {"decision": "SKIP", "rationale": "already exists"}))
    assert isinstance(out, dict), f"SKIP returned {out!r}"
    assert out.get("skipped") == "s1"


# --------------------------------------------------------------- bug 3

def test_approving_replan_budget_hold_replays_replan(backend):
    svc, _, make = backend
    rid = make(plan=PLAN, parameters={"replan_budget": 0})
    new_plan = [dict(s) for s in PLAN]
    out = advance(svc, rid, {"decision": "REPLAN", "rationale": "pivot now",
                             "new_plan": new_plan, "confidence": 0.9})
    assert out["held"] is True
    assert svc.get_run(rid)["pending_decision"]["decision"] == "ASK_HUMAN"

    resumed = asyncio.run(svc.resume(rid, approved=True, reviewer="sup"))
    assert resumed["resumed"] is True
    run = svc.get_run(rid)
    assert run["pending_decision"] is None
    assert run["replan_count"] == 1
    assert [s["id"] for s in run["plan"]] == [s["id"] for s in new_plan]


def test_approving_major_replan_hold_applies_replan(backend):
    svc, _, make = backend
    rid = make(plan=PLAN)
    # Drops all 3 remaining steps → over the magnitude threshold → held.
    new_plan = [{"id": "fresh-1", "kind": "canvas_work", "title": "New path"}]
    out = advance(svc, rid, {"decision": "REPLAN", "rationale": "big pivot",
                             "new_plan": new_plan, "confidence": 0.9})
    assert out["held"] is True
    assert "major replan" in (out.get("reason") or "")

    asyncio.run(svc.resume(rid, approved=True, reviewer="sup"))
    run = svc.get_run(rid)
    assert [s["id"] for s in run["plan"]] == ["fresh-1"]
    assert run["replan_count"] == 1


def test_approving_wait_ceiling_hold_sets_wait(backend):
    svc, _, make = backend
    rid = make(plan=PLAN)
    far = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    out = advance(svc, rid, {"decision": "WAIT", "rationale": "long nurture",
                             "wait_spec": {"event": "email_reply",
                                           "deadline": far},
                             "confidence": 0.95})
    assert out["held"] is True

    asyncio.run(svc.resume(rid, approved=True, reviewer="sup"))
    run = svc.get_run(rid)
    assert run["status"] == "waiting"
    assert run["waiting_on"]["event"] == "email_reply"
    assert run["waiting_on"]["deadline"] == far


def test_approving_failed_done_marks_achieved(backend):
    svc, _, make = backend
    rid = make(plan=PLAN)
    out = advance(svc, rid, {"decision": "DONE", "rationale": "looks done",
                             "confidence": 0.95})
    assert out["held"] is True
    assert "criteria" in (out.get("reason") or "")

    resumed = asyncio.run(svc.resume(rid, approved=True, reviewer="sup"))
    assert resumed["resumed"] is True
    assert svc.get_run(rid)["status"] == "achieved"
