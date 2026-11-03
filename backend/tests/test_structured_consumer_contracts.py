"""Shared structured-consumer contracts: typed no-tool and REPLAN repair.

- A successful planner decline is ToolPlan(use_tool=False), not transport None.
- A transport/parse None stays None (no fabricated decline).
- Invalid REPLAN gets one bounded corrective pass; still invalid -> ASK_HUMAN.
- execute_decision never applies or executes an invalid REPLAN.
"""
from __future__ import annotations

import asyncio

import pytest

from core.chat_tool_planner import ToolPlan, plan_tool_use
from core.goals.goal_run_router import GoalRunRouter, RouterDecisionModel
from core.goals.goal_run_service import GoalRunService


def _goal_context():
    return {
        "run": {
            "id": "run-1", "goal_id": "goal-1", "role": "operations",
            "status": "active", "parameters": {"lead": "Acme"},
            "plan": [{"id": "step-1", "kind": "canvas_work",
                      "title": "Research", "canvas_type": "document"}],
            "cursor": "step-1", "decision_log": [],
        },
        "goal": {"status": "active", "satisfied": 0, "total": 0},
        "step_digest": {}, "event": {},
        "maturity_tier": "autonomous", "agent_name": "Model Employee",
    }


class _FakeLLM:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    async def generate_structured_response(self, **kwargs):
        self.calls.append(kwargs.get("prompt") or "")
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return output


def test_invalid_replan_gets_one_repair_and_returns_the_plan():
    fake = _FakeLLM([
        RouterDecisionModel(
            decision="REPLAN", rationale="need a new plan", new_plan=None),
        RouterDecisionModel(
            decision="REPLAN", rationale="repaired",
            new_plan=[{"id": "step-2", "kind": "canvas_work",
                       "title": "Draft"}]),
    ])
    router = GoalRunRouter(llm_service=fake)
    decision = asyncio.run(router.decide(_goal_context()))
    assert decision["decision"] == "REPLAN"
    assert decision["new_plan"] == [{"id": "step-2", "kind": "canvas_work",
                                     "title": "Draft"}]
    assert decision["repair"]["attempted"] is True
    assert decision["repair"]["recovered"] is True
    assert len(fake.calls) == 2
    assert "REPAIR REQUIRED" in fake.calls[1]


def test_unrepaired_invalid_replan_falls_back_to_human():
    fake = _FakeLLM([
        RouterDecisionModel(
            decision="REPLAN", rationale="bad", new_plan=None),
        RouterDecisionModel(
            decision="REPLAN", rationale="still bad", new_plan=[]),
    ])
    router = GoalRunRouter(llm_service=fake)
    decision = asyncio.run(router.decide(_goal_context()))
    assert decision["decision"] == "ASK_HUMAN"
    assert decision["new_plan"] is None
    assert decision["repair"]["attempted"] is True
    assert decision["repair"]["recovered"] is False
    assert len(fake.calls) == 2


def test_transport_none_is_not_repaired_as_replan():
    fake = _FakeLLM([None])
    router = GoalRunRouter(llm_service=fake)
    decision = asyncio.run(router.decide(_goal_context()))
    assert decision["decision"] == "ASK_HUMAN"
    assert "repair" not in decision
    assert len(fake.calls) == 1


def test_execute_decision_never_applies_an_invalid_replan():
    svc = object.__new__(GoalRunService)
    svc.get_run = lambda _run_id: {
        "id": "run-1", "plan": [{"id": "step-1"}], "cursor": "step-1",
        "parameters": {}, "decision_log": [],
    }
    held = {}

    def hold(run_id, decision, reason=None, **_kwargs):
        held.update({"run_id": run_id, "decision": decision,
                     "reason": reason})
        return {"advanced": False, "decision": "ASK_HUMAN", "held": True}

    svc._hold_for_approval = hold
    calls = {"execute": 0}

    class Executors:
        async def execute(self, *_args, **_kwargs):
            calls["execute"] += 1
            return {}

    result = asyncio.run(svc.execute_decision(
        "run-1", {"decision": "REPLAN", "rationale": "bad",
                  "new_plan": None},
        executors=Executors()))
    assert result["held"] is True
    assert held["decision"]["decision"] == "ASK_HUMAN"
    assert held["decision"]["invalid_decision"]["decision"] == "REPLAN"
    assert calls["execute"] == 0


def test_planner_typed_no_tool_is_not_transport_none(monkeypatch):
    async def typed_decline(*_args, **_kwargs):
        return ToolPlan(use_tool=False, reason="conversational turn")

    monkeypatch.setattr(
        "core.chat_tool_planner._structured_with_fallback", typed_decline)
    plan = asyncio.run(plan_tool_use(
        "hello there", [], "user-1", object()))
    assert plan is not None
    assert plan.use_tool is False

    async def transport_failure(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "core.chat_tool_planner._structured_with_fallback",
        transport_failure)
    failed = asyncio.run(plan_tool_use(
        "hello there", [], "user-1", object()))
    assert failed is None
