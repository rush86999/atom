"""Coverage wave 36 — core/agent_objective (71% → 100%)."""
import os
from unittest.mock import patch

import pytest

from core.agent_objective import (
    Objective,
    _env_bool,
    objective_from_context,
    objective_loop_enabled,
)


class TestEnvBool:
    def test_missing_returns_default(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _env_bool("NOPE", True) is True
            assert _env_bool("NOPE2", False) is False

    @pytest.mark.parametrize("value,expected", [
        ("1", True), ("true", True), ("yes", True), ("on", True),
        ("0", False), ("false", False), ("no", False), ("off", False),
        ("  True  ", True),
    ])
    def test_values(self, value, expected):
        with patch.dict(os.environ, {"FLAG": value}):
            assert _env_bool("FLAG", False) is expected


class TestObjectiveLoopFlag:
    def test_default_on(self):
        with patch.dict(os.environ, {}, clear=True):
            assert objective_loop_enabled() is True

    def test_off(self):
        with patch.dict(os.environ, {"ATOM_OBJECTIVE_LOOP_ENABLED": "false"}):
            assert objective_loop_enabled() is False


class TestObjective:
    def test_is_satisfied_none_predicate(self):
        o = Objective(goal="g")
        assert o.is_satisfied({}) is False

    def test_is_satisfied_true_and_false(self):
        o = Objective(goal="g", definition_of_done=lambda s: s.get("done") is True)
        assert o.is_satisfied({"done": True}) is True
        assert o.is_satisfied({"done": False}) is False

    def test_is_satisfied_exception_tolerated(self):
        def boom(state):
            raise RuntimeError("bad predicate")
        o = Objective(goal="g", definition_of_done=boom)
        assert o.is_satisfied({}) is False

    def test_constraints_and_criteria_defaults(self):
        o = Objective(goal="g")
        assert o.constraints == {}
        assert o.success_criteria == []


class TestObjectiveFromContext:
    def test_flag_off_returns_none(self):
        with patch("core.agent_objective.objective_loop_enabled", return_value=False):
            assert objective_from_context({"objective_goal": "g"}) is None

    def test_objective_instance(self):
        o = Objective(goal="g")
        assert objective_from_context({"objective": o}) is o

    def test_goal_and_predicate(self):
        done = lambda s: True  # noqa: E731
        obj = objective_from_context({
            "objective_goal": "finish",
            "objective_done": done,
            "objective_criteria": ["a"],
        })
        assert obj is not None
        assert obj.goal == "finish"
        assert obj.success_criteria == ["a"]

    def test_incomplete_returns_none(self):
        assert objective_from_context({"objective_goal": "g"}) is None
        assert objective_from_context({"objective_done": lambda s: True}) is None
        assert objective_from_context({}) is None
