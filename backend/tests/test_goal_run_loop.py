"""Slice 2+3 tests — router decision loop, guardrails, executors, criteria
(docs/architecture/GOAL_RUN_ORCHESTRATION.md §3.2-§3.5, §7 slices 2-3).

The router is stubbed (deterministic scripts); no LLM is contacted.
Scratch-file sqlite via injected session_factory — never the live dev DB.
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
)
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_run_executors import GoalRunExecutors


@pytest.fixture()
def backend(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/goal_run_loop_test.db")
    for table in (GoalObjective.__table__, GoalRun.__table__,
                  Canvas.__table__, CanvasAudit.__table__, HITLAction.__table__):
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

    def make_run(plan=None, **kwargs):
        return svc.create_run("goal-1", plan=plan or PLAN, **kwargs)

    return svc, factory, make_run


PLAN = [
    {"id": "step-research", "kind": "canvas_work", "title": "Research the lead",
     "canvas_type": "document"},
    {"id": "step-quote", "kind": "canvas_work", "title": "Draft the quote",
     "canvas_type": "spreadsheet"},
    {"id": "step-approval", "kind": "human_checkpoint", "title": "Quote approval"},
    {"id": "step-send", "kind": "integration_action", "title": "send_email",
     "arguments": {"to": "acme@x.com"}},
]


class StubRouter:
    """Scripted decisions — one per advance() call, in order."""

    def __init__(self, decisions):
        self.decisions = list(decisions)
        self.calls = []

    async def decide(self, context):
        self.calls.append(context)
        if self.decisions:
            return self.decisions.pop(0)
        return {"decision": "ASK_HUMAN", "rationale": "script exhausted",
                "confidence": 0.9}


class RecordingExecutors(GoalRunExecutors):
    """Real executors with the agent-delegation path short-circuited."""

    async def _delegate_agent_work(self, run, step_id, directive, canvas_id):
        return False


def advance(svc, rid, router=None, **kwargs):
    return asyncio.run(svc.advance(rid, router=router, **kwargs))


# ---------------------------------------------------------------- slice 2

class TestDecisionLoop:
    def test_advance_persists_decision_and_executes_canvas_step(self, backend):
        svc, factory, make_run = backend
        rid = make_run(supervision_mode="shadow")["id"]
        svc.transition(rid, "active")
        out = advance(svc, rid, router=StubRouter([
            {"decision": "ADVANCE", "rationale": "research first",
             "confidence": 0.9}]),
            executors=RecordingExecutors(svc))
        assert out["advanced"] is True and out["decision"] == "ADVANCE"
        canvas_id = out["result"]["canvas_id"]
        log = svc.get_decisions(rid)
        entry = next(e for e in log if e.get("kind") == "decision")
        assert entry["decision"] == "ADVANCE"
        assert entry["rationale"] == "research first"
        with factory() as session:
            canvas = session.query(Canvas).filter(Canvas.id == canvas_id).one()
            assert canvas.goal_run_id == rid
            assert canvas.goal_run_step_id == "step-research"
            assert canvas.canvas_type == "document"
            audit = session.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id).one()
            assert audit.action_type == "goal_run_canvas_create"
        run = svc.get_run(rid)
        assert run["steps_executed"] == 1
        assert run["cursor"] == "step-quote"       # cursor advanced

    def test_parameter_updates_applied_and_logged(self, backend):
        svc, _, make_run = backend
        rid = make_run()["id"]
        svc.transition(rid, "active")
        advance(svc, rid, router=StubRouter([
            {"decision": "ADVANCE", "rationale": "ok",
             "parameter_updates": {"objection": "price", "lead": {"stage": "quoted"}},
             "confidence": 0.8}]),
            executors=RecordingExecutors(svc))
        run = svc.get_run(rid)
        assert run["parameters"]["objection"] == "price"
        assert run["parameters"]["lead"]["stage"] == "quoted"
        entry = next(e for e in svc.get_decisions(rid)
                     if e.get("kind") == "decision")
        assert entry["parameter_diff"]["objection"] == "price"

    def test_wait_decision_suspends_run(self, backend):
        svc, _, make_run = backend
        rid = make_run()["id"]
        svc.transition(rid, "active")
        advance(svc, rid, router=StubRouter([
            {"decision": "WAIT", "rationale": "wait for the lead's reply",
             "wait_spec": {"event": "email_reply", "match": {"from": "acme@x.com"},
                           "deadline": "2026-09-12T00:00:00Z"},
             "confidence": 0.9}]))
        run = svc.get_run(rid)
        assert run["status"] == "waiting"
        assert run["waiting_on"]["event"] == "email_reply"
        # a wake re-enters the loop with the event in context
        wake = svc.consume_wake(rid, {"event": "email_reply",
                                      "from": "acme@x.com",
                                      "subject": "Re: quote"})
        assert wake["consumed"] is True
        out = advance(svc, rid, router=StubRouter([
            {"decision": "ADVANCE", "rationale": "reply received — proceed",
             "confidence": 0.85}]),
            executors=RecordingExecutors(svc), event={"event": "email_reply"})
        assert out["decision"] == "ADVANCE"

    def test_done_requires_criteria_verification(self, backend):
        svc, _, make_run = backend
        rid = make_run()["id"]
        svc.transition(rid, "active")
        # goal has zero criteria → DONE claim must NOT be trusted
        out = advance(svc, rid, router=StubRouter([
            {"decision": "DONE", "rationale": "trust me", "confidence": 0.99}]))
        assert out["decision"] == "ASK_HUMAN"
        assert out["held"] is True
        assert "not" in out["reason"] or "criteria" in out["reason"]
        assert svc.get_run(rid)["status"] == "paused_hitl"

    def test_training_mode_holds_every_decision(self, backend):
        svc, _, make_run = backend
        rid = make_run(supervision_mode="training")["id"]
        svc.transition(rid, "active")
        out = advance(svc, rid, router=StubRouter([
            {"decision": "ADVANCE", "rationale": "next", "confidence": 0.95}]))
        assert out["held"] is True
        assert svc.get_run(rid)["status"] == "paused_hitl"
        assert svc.get_run(rid)["pending_decision"]["decision"] == "ADVANCE"
        # resume executes the exact held decision
        executed = asyncio.run(svc.resume(rid, approved=True, reviewer="sup"))
        assert executed["decision"] == "ADVANCE"

    def test_training_mode_checkpoint_passes_through_human_checkpoints(self, backend):
        """ASK_HUMAN in training mode → still a single checkpoint (not two)."""
        svc, _, make_run = backend
        rid = make_run(supervision_mode="training")["id"]
        svc.transition(rid, "active")
        out = advance(svc, rid, router=StubRouter([
            {"decision": "ASK_HUMAN", "rationale": "need pricing approval",
             "confidence": 0.9}]))
        assert out["held"] is True
        log = svc.get_decisions(rid)
        assert sum(1 for e in log if e.get("kind") == "held_for_approval") == 1


# ------------------------------------------------------------- guardrails

class TestGuardrails:
    def test_replan_budget_forces_ask_human(self, backend):
        svc, _, make_run = backend
        rid = make_run(parameters={"replan_budget": 1})["id"]
        svc.transition(rid, "active")
        # Minor first replan (keeps 2 of 3 remaining steps) — budget 1 → applies.
        advance(svc, rid, router=StubRouter([
            {"decision": "REPLAN", "rationale": "tighten the plan",
             "new_plan": [PLAN[0], PLAN[1], PLAN[3]],
             "confidence": 0.9}]))
        assert svc.get_run(rid)["replan_count"] == 1
        out = advance(svc, rid, router=StubRouter([
            {"decision": "REPLAN", "rationale": "pivot again",
             "new_plan": [{"id": "step-quote", "kind": "canvas_work",
                           "title": "Quote"}],
             "confidence": 0.9}]))
        assert out["decision"] == "ASK_HUMAN"
        assert "budget" in (out.get("reason") or "")

    def test_replan_magnitude_gate_holds_major_replans(self, backend):
        svc, _, make_run = backend
        rid = make_run()["id"]
        svc.transition(rid, "active")
        # Replaces all 4 planned steps → major → HITL hold, plan NOT applied
        out = advance(svc, rid, router=StubRouter([
            {"decision": "REPLAN", "rationale": "different strategy",
             "new_plan": [{"id": "step-x", "kind": "canvas_work",
                           "title": "Something else entirely"}],
             "confidence": 0.95}]))
        assert out["decision"] == "ASK_HUMAN" and out["held"] is True
        assert svc.get_run(rid)["plan"][0]["id"] == "step-research"

    def test_minor_replan_applies(self, backend):
        svc, _, make_run = backend
        rid = make_run()["id"]
        svc.transition(rid, "active")
        out = advance(svc, rid, router=StubRouter([
            {"decision": "REPLAN", "rationale": "drop one step",
             "new_plan": PLAN[:3] + [{"id": "step-send",
                                      "kind": "integration_action",
                                      "title": "send_email"}],
             "confidence": 0.9}]))
        assert out["decision"] == "REPLAN"
        assert svc.get_run(rid)["replan_count"] == 1

    def test_stuck_detector_pauses_after_identical_decisions(self, backend):
        svc, _, make_run = backend
        rid = make_run(plan=[{"id": "s1", "kind": "canvas_work",
                              "title": "only step"}])["id"]
        svc.transition(rid, "active")
        pivot = {"decision": "REVISE_CURRENT", "rationale": "not good enough",
                 "confidence": 0.9}
        advance(svc, rid, router=StubRouter([dict(pivot)]),
                executors=RecordingExecutors(svc))
        advance(svc, rid, router=StubRouter([dict(pivot)]),
                executors=RecordingExecutors(svc))
        third = advance(svc, rid, router=StubRouter([dict(pivot)]),
                        executors=RecordingExecutors(svc))
        assert third["decision"] == "ASK_HUMAN"
        assert "stuck" in (third.get("reason") or "").lower()


# ---------------------------------------------------------------- slice 3

class TestExecutors:
    def test_human_checkpoint_step_creates_hitl_and_waits(self, backend):
        svc, factory, make_run = backend
        rid = make_run(plan=[PLAN[2]])["id"]  # the approval step
        svc.transition(rid, "active")
        ex = RecordingExecutors(svc)
        out = asyncio.run(ex.execute(svc.get_run(rid),
                                     {"decision": "ADVANCE",
                                      "rationale": "quote ready"}))
        assert out["checkpoint"]
        run = svc.get_run(rid)
        assert run["status"] == "waiting"
        assert run["waiting_on"]["match"]["hitl_id"] == out["checkpoint"]
        with factory() as session:
            hitl = session.query(HITLAction).filter(
                HITLAction.id == out["checkpoint"]).one()
            assert hitl.action_type == "goal_run_checkpoint"

    def test_integration_action_via_action_registry(self, backend):
        from core.action_registry import register_action
        seen = {}

        @register_action("test_goalrun.send")
        async def _fake_send(args, context):
            seen["args"] = args
            seen["context_goal_run"] = context.get("goal_run_id")
            return {"sent": True}

        svc, _, make_run = backend
        step = {"id": "step-send", "kind": "integration_action",
                "title": "Send the quote", "action": "test_goalrun.send",
                "arguments": {"to": "acme@x.com"}}
        rid = make_run(plan=[step])["id"]
        svc.transition(rid, "active")
        ex = RecordingExecutors(svc)
        out = asyncio.run(ex.execute(svc.get_run(rid),
                                     {"decision": "ADVANCE",
                                      "rationale": "send it"}))
        assert out["result"]["sent"] is True
        assert seen["context_goal_run"] == rid

    def test_unknown_action_is_reported_not_raised(self, backend):
        svc, _, make_run = backend
        rid = make_run(plan=[{"id": "s", "kind": "integration_action",
                              "title": "no.such.action"}])["id"]
        svc.transition(rid, "active")
        ex = RecordingExecutors(svc)
        out = asyncio.run(ex.execute(svc.get_run(rid),
                                     {"decision": "ADVANCE"}))
        assert "error" in out

    def test_branch_new_canvas_creates_linked_canvas(self, backend):
        svc, factory, make_run = backend
        rid = make_run()["id"]
        svc.transition(rid, "active")
        ex = RecordingExecutors(svc)
        out = asyncio.run(ex.execute(
            svc.get_run(rid),
            {"decision": "BRANCH_NEW_CANVAS", "rationale": "needs a demo sheet",
             "target_step": "step-demo",
             "new_canvas": {"canvas_type": "spreadsheet",
                            "title": "Demo comparison"}}))
        assert out["branched"] is True and out["canvas_id"]
        with factory() as session:
            canvas = session.query(Canvas).filter(
                Canvas.id == out["canvas_id"]).one()
            assert canvas.goal_run_id == rid
            assert canvas.canvas_type == "spreadsheet"

    def test_skip_advances_cursor(self, backend):
        svc, _, make_run = backend
        rid = make_run()["id"]
        svc.transition(rid, "active")
        advance(svc, rid, router=StubRouter([
            {"decision": "SKIP", "rationale": "research already exists",
             "confidence": 0.9}]),
            executors=RecordingExecutors(svc))
        assert svc.get_run(rid)["cursor"] == "step-quote"


# ------------------------------------------------------------- criteria

class TestCanvasCriteria:
    def test_canvas_state_criterion(self, backend):
        from core.goals.criterion_evaluator import CriterionEvaluator
        svc, factory, _ = backend
        rid = svc.create_run("goal-1", plan=PLAN)["id"]
        with factory() as session:
            session.add(Canvas(id="cv-quote", tenant_id="t_test",
                               workspace_id="ws_test", created_by="u",
                               name="Quote", canvas_type="spreadsheet",
                               goal_run_id=rid))
            session.commit()
        engine = create_engine("sqlite:///:memory:")  # evaluator takes factory
        del engine
        ev = CriterionEvaluator(workspace_id="ws_test",
                                session_factory=factory)
        ok = ev.evaluate([{"type": "canvas_state", "goal_run_id": rid,
                           "canvas_type": "spreadsheet",
                           "expected": {"name_contains": "quote"}}])
        assert ok[0].satisfied is True
        miss = ev.evaluate([{"type": "canvas_state", "goal_run_id": rid,
                             "canvas_type": "document",
                             "expected": {"name_contains": "invoice"}}])
        assert miss[0].satisfied is False

    def test_action_dispatched_criterion(self, backend):
        from core.goals.criterion_evaluator import CriterionEvaluator
        svc, factory, _ = backend
        rid = svc.create_run("goal-1", plan=PLAN)["id"]
        svc.append_decision(rid, {"kind": "decision", "decision": "ADVANCE",
                                  "canvas_id": "cv-quote"})
        with factory() as session:
            session.add(CanvasAudit(canvas_id="cv-quote", tenant_id="t_test",
                                    action_type="goal_run_action_dispatched",
                                    details_json={"goal_run_id": rid}))
            session.commit()
        ev = CriterionEvaluator(workspace_id="ws_test", session_factory=factory)
        ok = ev.evaluate([{"type": "action_dispatched", "goal_run_id": rid}])
        assert ok[0].satisfied is True
