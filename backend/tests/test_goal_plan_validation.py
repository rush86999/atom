"""One semantic plan validator shared by router, service and executor."""
from __future__ import annotations

import math

import pytest

from core.goals.goal_plan_validation import (
    confidence_is_valid,
    validate_goal_plan,
    validate_replan_decision,
)
from core.goals.goal_run_router import GoalRunRouter
from core.goals.goal_run_service import GoalRunService


def _step(step_id="step-1", **overrides):
    step = {"id": step_id, "kind": "canvas_work", "title": "Research"}
    step.update(overrides)
    return step


def test_valid_plan_and_dependency_order_pass():
    plan = [
        _step("step-1"),
        _step("step-2", depends_on=["step-1"]),
    ]
    assert validate_goal_plan(plan) == []


@pytest.mark.parametrize("plan", [
    [],
    {"id": "not-a-list"},
    [_step("")],
    [_step("same"), _step("same")],
    [_step("step-1", kind="unknown_kind")],
    [_step("step-1", depends_on=["missing"])],
    [_step("step-1", depends_on=["step-1"])],
    [_step("step-1", depends_on=["step-2"]), _step("step-2")],
    [_step("step-1", authorized_actions=["send"])],
])
def test_invalid_plans_are_rejected(plan):
    assert validate_goal_plan(plan), plan


def test_integration_action_requires_a_registered_action():
    from core.action_registry import action_registry

    class Registry:
        @staticmethod
        def get_action(name):
            return action_registry.get_action(name)

    unknown = [_step("step-1", kind="integration_action",
                     action="does.not.exist")]
    assert validate_goal_plan(unknown, action_registry=Registry())
    known = [_step("step-1", kind="integration_action",
                   action="canvas.present_markdown", arguments={"content": "x"})]
    assert validate_goal_plan(known, action_registry=Registry()) == []


def test_replan_decision_uses_the_same_validator():
    assert validate_replan_decision(
        {"decision": "REPLAN", "new_plan": None})
    assert validate_replan_decision(
        {"decision": "REPLAN", "new_plan": [_step()]}) == []
    assert validate_replan_decision(
        {"decision": "ADVANCE", "new_plan": []})


def test_confidence_must_be_finite_and_in_range():
    assert confidence_is_valid(0.5)
    assert not confidence_is_valid(float("nan"))
    assert not confidence_is_valid(float("inf"))
    assert not confidence_is_valid(-0.1)
    assert not confidence_is_valid(1.1)
    assert not confidence_is_valid("not-a-number")


def test_router_coerce_rejects_semantically_invalid_replans():
    assert GoalRunRouter._coerce(
        None, {"decision": "REPLAN", "new_plan": []}) is None
    valid = GoalRunRouter._coerce(
        None, {"decision": "REPLAN", "new_plan": [_step()]})
    assert valid is not None and valid["decision"] == "REPLAN"


def test_set_plan_refuses_invalid_plans_before_any_db_session():
    svc = object.__new__(GoalRunService)
    with pytest.raises(ValueError, match="invalid goal plan"):
        svc.set_plan("run-1", [_step("dup"), _step("dup")])
    with pytest.raises(ValueError, match="invalid goal plan"):
        svc.set_plan("run-1", [])
