"""Slice 1 tests — GoalRun model + service skeleton
(docs/architecture/GOAL_RUN_ORCHESTRATION.md §3.1, §7 slice 1).

Scratch-file sqlite via injected session_factory — never the live dev DB
(AGENTS.md: ad-hoc DB contact only through TESTING / scratch engines).
"""

import asyncio
import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")

from core.models import (
    Base,
    Canvas,
    CanvasAudit,
    GoalObjective,
    GoalRun,
    HITLAction,
    HITLActionStatus,
)
from core.goals.goal_run_service import (
    GOAL_RUN_TRANSITIONS,
    GoalRunService,
    GoalRunTransitionError,
)


@pytest.fixture()
def backend(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/goal_run_test.db")
    for table in (GoalObjective.__table__, GoalRun.__table__,
                  Canvas.__table__, CanvasAudit.__table__,
                  HITLAction.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    svc = GoalRunService(workspace_id="ws_test", tenant_id="t_test",
                         session_factory=factory)
    with factory() as session:
        session.add(GoalObjective(
            id="goal-1", workspace_id="ws_test", tenant_id="t_test",
            title="Prepare a quote for the Acme lead",
            status="active", criteria=[], key_results=[]))
        session.commit()

    def make_goal(goal_id):
        with factory() as session:
            session.add(GoalObjective(
                id=goal_id, workspace_id="ws_test", tenant_id="t_test",
                title=f"goal {goal_id}", status="active"))
            session.commit()

    return svc, factory, make_goal


PLAN = [
    {"id": "step-research", "kind": "canvas_work", "title": "Research the lead",
     "canvas_type": "document"},
    {"id": "step-quote", "kind": "canvas_work", "title": "Draft the quote",
     "canvas_type": "spreadsheet"},
    {"id": "step-send", "kind": "integration_action", "title": "Send the quote"},
]


class TestCreateRun:
    def test_creates_planning_run_with_cursor(self, backend):
        svc, _, _ = backend
        run = svc.create_run("goal-1", agent_id="agent-1", role="sales",
                             supervision_mode="training", plan=PLAN)
        assert run["status"] == "planning"
        assert run["supervision_mode"] == "training"
        assert run["role"] == "sales"
        assert run["cursor"] == "step-research"
        assert run["decision_log"] == []

    def test_rejects_unknown_supervision_mode(self, backend):
        svc, _, _ = backend
        with pytest.raises(ValueError, match="supervision_mode"):
            svc.create_run("goal-1", supervision_mode="yolo")

    def test_rejects_unknown_goal(self, backend):
        svc, _, _ = backend
        with pytest.raises(ValueError, match="not found"):
            svc.create_run("goal-missing")


class TestStateMachine:
    def test_full_lifecycle(self, backend):
        svc, _, _ = backend
        run = svc.create_run("goal-1", plan=PLAN)
        rid = run["id"]
        svc.transition(rid, "active")
        svc.set_wait(rid, {"event": "email_reply", "match": {"from": "acme@x.com"},
                           "deadline": "2026-09-12T00:00:00Z"})
        assert svc.get_run(rid)["status"] == "waiting"
        wake = svc.consume_wake(rid, {"event": "email_reply",
                                      "from": "acme@x.com", "subject": "Re: quote"})
        assert wake["consumed"] is True
        assert svc.get_run(rid)["status"] == "active"
        assert svc.get_run(rid)["waiting_on"] is None
        svc.transition(rid, "achieved")
        assert svc.get_run(rid)["status"] == "achieved"

    def test_illegal_transitions_rejected(self, backend):
        svc, _, _ = backend
        run = svc.create_run("goal-1", plan=PLAN)
        rid = run["id"]
        with pytest.raises(GoalRunTransitionError):
            svc.transition(rid, "achieved")       # planning → achieved
        with pytest.raises(GoalRunTransitionError):
            svc.transition(rid, "waiting")        # planning → waiting
        svc.transition(rid, "active")
        svc.transition(rid, "achieved")
        with pytest.raises(GoalRunTransitionError):
            svc.transition(rid, "active")         # terminal is terminal

    def test_terminal_states_have_no_exits(self, backend):
        for state in ("achieved", "failed", "cancelled"):
            assert GOAL_RUN_TRANSITIONS[state] == set()

    def test_pause_hitl_round_trip(self, backend):
        svc, _, _ = backend
        rid = svc.create_run("goal-1", plan=PLAN)["id"]
        svc.transition(rid, "active")
        svc.transition(rid, "paused_hitl")
        svc.transition(rid, "active")
        assert svc.get_run(rid)["status"] == "active"


class TestPersistence:
    def test_run_survives_fresh_service(self, backend, tmp_path):
        """Restart simulation: a NEW service instance on a fresh engine must
        see the same durable run (§3 constraint: durable state, not memory)."""
        svc, factory, _ = backend
        rid = svc.create_run("goal-1", agent_id="agent-1", role="sales",
                             plan=PLAN, parameters={"budget": 5000})["id"]
        svc.append_decision(rid, {"kind": "decision", "decision": "ADVANCE",
                                  "rationale": "research done"})

        engine = create_engine(f"sqlite:///{tmp_path}/goal_run_test.db")
        fresh = GoalRunService(workspace_id="ws_test", tenant_id="t_test",
                               session_factory=sessionmaker(bind=engine))
        run = fresh.get_run(rid)
        assert run is not None
        assert run["parameters"]["budget"] == 5000
        assert run["decision_log"][-1]["decision"] == "ADVANCE"

    def test_decision_log_append_only(self, backend):
        svc, _, _ = backend
        rid = svc.create_run("goal-1", plan=PLAN)["id"]
        svc.append_decision(rid, {"kind": "decision", "decision": "ADVANCE"})
        svc.append_decision(rid, {"kind": "wake", "event": "email_reply"})
        log = svc.get_decisions(rid)
        assert [e["kind"] for e in log] == ["decision", "wake"]
        assert all("ts" in e for e in log)


class TestWaits:
    def test_set_wait_requires_active(self, backend):
        svc, _, _ = backend
        rid = svc.create_run("goal-1", plan=PLAN)["id"]
        with pytest.raises(GoalRunTransitionError):
            svc.set_wait(rid, {"event": "timer"})

    def test_set_wait_requires_event_key(self, backend):
        svc, _, _ = backend
        rid = svc.create_run("goal-1", plan=PLAN)["id"]
        svc.transition(rid, "active")
        with pytest.raises(ValueError, match="event"):
            svc.set_wait(rid, {"match": {"from": "x"}})

    def test_wake_consumed_once(self, backend):
        svc, _, _ = backend
        rid = svc.create_run("goal-1", plan=PLAN)["id"]
        svc.transition(rid, "active")
        svc.set_wait(rid, {"event": "email_reply", "match": {"from": "acme@x.com"}})
        miss = svc.consume_wake(rid, {"event": "email_reply",
                                      "from": "someoneelse@y.com"})
        assert miss["consumed"] is False
        assert svc.get_run(rid)["status"] == "waiting"
        hit = svc.consume_wake(rid, {"event": "email_reply",
                                     "from": "acme@x.com"})
        assert hit["consumed"] is True
        again = svc.consume_wake(rid, {"event": "email_reply",
                                       "from": "acme@x.com"})
        assert again["consumed"] is False   # spec consumed — run is active

    def test_timer_wake_without_constraints(self, backend):
        svc, _, _ = backend
        rid = svc.create_run("goal-1", plan=PLAN)["id"]
        svc.transition(rid, "active")
        svc.set_wait(rid, {"event": "timer",
                           "deadline": "2026-09-12T00:00:00Z"})
        wake = svc.consume_wake(rid, {"event": "timer", "source": "followup"})
        assert wake["consumed"] is True


class TestParameters:
    def test_patch_merges_top_level_and_nested(self, backend):
        svc, _, _ = backend
        rid = svc.create_run("goal-1", plan=PLAN,
                             parameters={"budget": 5000,
                                         "lead": {"name": "Acme"}})["id"]
        run = svc.patch_parameters(rid, {"objection": "price",
                                         "lead": {"stage": "quoted"}})
        assert run["parameters"]["budget"] == 5000
        assert run["parameters"]["objection"] == "price"
        assert run["parameters"]["lead"] == {"name": "Acme", "stage": "quoted"}


class TestCanvasBackLinks:
    def test_canvas_goal_run_link_persists(self, backend):
        svc, factory, _ = backend
        rid = svc.create_run("goal-1", plan=PLAN)["id"]
        with factory() as session:
            canvas = Canvas(
                id=f"cv-{uuid.uuid4().hex[:8]}",
                tenant_id="t_test", workspace_id="ws_test",
                created_by="user-1", name="Lead research",
                canvas_type="document",
                goal_run_id=rid, goal_run_step_id="step-research")
            session.add(canvas)
            session.commit()
        with factory() as session:
            row = session.query(Canvas).filter(
                Canvas.goal_run_id == rid).one()
            assert row.goal_run_step_id == "step-research"


class TestHITLHold:
    def test_hold_creates_hitl_row_and_resume_executes(self, backend):
        svc, factory, _ = backend

        class EchoExecutors:
            def __init__(self, service):
                self.service = service

            async def execute(self, run, decision):
                return {"executed": decision["decision"]}

        rid = svc.create_run("goal-1", plan=PLAN,
                             supervision_mode="training")["id"]
        svc.transition(rid, "active")
        out = svc.execute_decision  # sanity: method exists
        held = svc._hold_for_approval(
            rid, {"decision": "ADVANCE", "rationale": "next step"},
            reason="training mode checkpoint")
        assert held["held"] is True
        assert held["hitl_id"]
        run = svc.get_run(rid)
        assert run["status"] == "paused_hitl"
        assert run["pending_decision"]["decision"] == "ADVANCE"
        with factory() as session:
            hitl = session.query(HITLAction).filter(
                HITLAction.id == held["hitl_id"]).one()
            assert hitl.status == HITLActionStatus.PENDING.value
            assert hitl.params["run_id"] == rid

        resumed = asyncio.run(svc.resume(rid, approved=True, reviewer="sup-1"))
        assert resumed["resumed"] is True
        assert resumed["decision"] == "ADVANCE"
        assert resumed["result"]["canvas_id"]
        assert svc.get_run(rid)["pending_decision"] is None

    def test_reject_override_recorded(self, backend):
        svc, _, _ = backend
        rid = svc.create_run("goal-1", plan=PLAN)["id"]
        svc.transition(rid, "active")
        svc._hold_for_approval(rid, {"decision": "REPLAN",
                                     "rationale": "pivot"},
                               reason="ask human")
        out = asyncio.run(svc.resume(rid, approved=False, reviewer="sup-1",
                                     guidance="stay on plan, revise the quote instead"))
        assert out["resumed"] is True and out["approved"] is False
        log = svc.get_decisions(rid)
        assert log[-1]["kind"] == "override"
        assert "revise the quote" in log[-1]["rationale"]

    def test_resume_without_pending_is_noop(self, backend):
        svc, _, _ = backend
        rid = svc.create_run("goal-1", plan=PLAN)["id"]
        out = asyncio.run(svc.resume(rid, approved=True))
        assert out["resumed"] is False
