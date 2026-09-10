"""Issue-fix regression tests — the loop-semantics bugs found in review:

1. Re-wait: waiting → waiting is legal (wake arrives, router waits again).
2. Stale hold: a wake must not execute around an unresolved held decision.
3. REVISE_CURRENT reworks the step's EXISTING canvas (no sibling canvases).
4. Checkpoint rejection rewinds the cursor to the guarded work step.
5. Tier WAIT ceilings (§8.6): over-ceiling deadlines require human sign-off.
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")

from core.models import Base, Canvas, CanvasAudit, GoalObjective, GoalRun, HITLAction
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_run_executors import GoalRunExecutors


@pytest.fixture()
def backend(tmp_path, monkeypatch):
    async def noop_outcome(service, run, outcome):
        return None

    monkeypatch.setattr(
        "core.goals.goal_run_learning.record_run_outcome", noop_outcome)
    engine = create_engine(f"sqlite:///{tmp_path}/goal_run_fixes_test.db")
    for table in (GoalObjective.__table__, GoalRun.__table__,
                  Canvas.__table__, CanvasAudit.__table__, HITLAction.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    svc = GoalRunService(workspace_id="ws_test", tenant_id="t_test",
                         session_factory=factory)
    with factory() as session:
        session.add(GoalObjective(id="goal-1", workspace_id="ws_test",
                                  tenant_id="t_test",
                                  title="Prepare a quote for the Acme lead",
                                  status="active"))
        session.commit()

    def make(plan=None, **kw):
        rid = svc.create_run("goal-1", plan=plan or PLAN, **kw)["id"]
        svc.transition(rid, "active")
        return rid

    return svc, factory, make


PLAN = [
    {"id": "step-research", "kind": "canvas_work", "title": "Research",
     "canvas_type": "document"},
    {"id": "step-quote", "kind": "canvas_work", "title": "Quote",
     "canvas_type": "spreadsheet"},
]


class Stub:
    def __init__(self, decision):
        self.decision = decision

    async def decide(self, context):
        return self.decision


def advance(svc, rid, decision, **kw):
    return asyncio.run(svc.advance(rid, router=Stub(decision), **kw))


def test_rewait_from_waiting_is_legal(backend):
    """A wake arrives, the router wants to wait again → replaces the spec
    instead of raising."""
    svc, _, make = backend
    rid = make()
    svc.set_wait(rid, {"event": "email_reply", "match": {"from": "a@x.com"}})
    svc.consume_wake(rid, {"event": "email_reply", "from": "a@x.com"})
    # consume flipped to active; wait again without a wake (direct set_wait
    # from waiting must also work — e.g. events-layer double waits)
    svc.set_wait(rid, {"event": "email_reply", "match": {"from": "b@x.com"}})
    run = svc.get_run(rid)
    assert run["status"] == "waiting"
    assert run["waiting_on"]["match"]["from"] == "b@x.com"


def test_wake_does_not_execute_around_unresolved_hold(backend):
    svc, _, make = backend
    rid = make(supervision_mode="training")
    svc._hold_for_approval(rid, {"decision": "ADVANCE",
                                 "rationale": "next"},
                           reason="training checkpoint")
    wake = svc.consume_wake(rid, {"event": "email_reply",
                                  "from": "acme@x.com"})
    if wake["consumed"]:   # hold cleared waiting_on only if it was waiting
        pass
    # Simulate the risky interleaving: active + pending decision + wake.
    svc.set_wait(rid, {"event": "email_reply"})
    svc.consume_wake(rid, {"event": "email_reply"})
    out = advance(svc, rid, {"decision": "ADVANCE", "rationale": "go"})
    assert out["advanced"] is False
    assert "awaiting approval" in out["reason"]
    assert svc.get_run(rid)["pending_decision"] is not None


def test_revise_current_reuses_step_canvas(backend):
    svc, factory, make = backend
    rid = make()
    ex = GoalRunExecutors(svc)
    # Step produces a canvas…
    first = asyncio.run(ex.execute(
        svc.get_run(rid), {"decision": "ADVANCE", "rationale": "draft"}))
    # …REVISE_CURRENT must return the SAME canvas, and not create another.
    second = asyncio.run(ex.execute(
        svc.get_run(rid), {"decision": "REVISE_CURRENT",
                           "rationale": "tighten the numbers"}))
    assert second["canvas_id"] == first["canvas_id"]
    assert second["revised"] is True
    with factory() as session:
        count = session.query(Canvas).filter(
            Canvas.goal_run_id == rid).count()
    assert count == 1


def test_checkpoint_rejection_rewinds_to_work(backend):
    svc, _, make = backend
    rid = make(plan=PLAN + [{"id": "step-approval",
                             "kind": "human_checkpoint",
                             "title": "Quote approval"}])
    # Full loop advances (service persists decisions + moves the cursor):
    # research → quote → the checkpoint step itself executes and waits.
    advance(svc, rid, {"decision": "ADVANCE", "rationale": "work",
                       "confidence": 0.9})
    advance(svc, rid, {"decision": "ADVANCE", "rationale": "more work",
                       "confidence": 0.9})
    advance(svc, rid, {"decision": "ADVANCE", "rationale": "checkpoint",
                       "confidence": 0.9})
    run = svc.get_run(rid)
    assert run["cursor"] == "step-approval"
    assert run["status"] == "waiting"
    # Supervisor REJECTS: cursor rewinds to the nearest work step.
    svc.rewind_to_work_before(rid, "step-approval")
    assert svc.get_run(rid)["cursor"] == "step-quote"


def test_wait_ceiling_forces_human_signoff(backend):
    svc, _, make = backend
    rid = make()  # shadow → default 14-day ceiling
    far = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    out = advance(svc, rid, {
        "decision": "WAIT", "rationale": "long game",
        "wait_spec": {"event": "email_reply", "deadline": far},
        "confidence": 0.95})
    assert out["decision"] == "ASK_HUMAN"
    assert "ceiling" in (out.get("reason") or "")
    assert svc.get_run(rid)["status"] == "paused_hitl"


def test_wait_within_ceiling_and_override(backend):
    svc, _, make = backend
    rid = make()  # shadow: 14d ceiling
    near = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    far = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    out = advance(svc, rid, {
        "decision": "WAIT", "rationale": "give the lead a week",
        "wait_spec": {"event": "email_reply", "deadline": near},
        "confidence": 0.95})
    assert out["decision"] == "WAIT"
    assert svc.get_run(rid)["status"] == "waiting"
    # Supervisor grants a longer ceiling per run via parameters.
    rid2 = make(parameters={"wait_ceiling_days": 60})
    out2 = advance(svc, rid2, {
        "decision": "WAIT", "rationale": "long nurture",
        "wait_spec": {"event": "email_reply", "deadline": far},
        "confidence": 0.95})
    assert out2["decision"] == "WAIT"
