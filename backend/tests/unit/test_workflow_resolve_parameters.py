"""
TDD regression tests for WorkflowEngine._resolve_parameters and
_evaluate_condition.

The resolver replaced the WHOLE parameter string with just the first matched
variable — "Hello ${user.name}!" became "Alice" instead of "Hello Alice!" —
silently corrupting text and dropping later variables. _get_value_from_path
also crashed with KeyError when state had no 'outputs' key.
"""

import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, "/Users/rushiparikh/projects/atom/backend")

import pytest

from core.workflow_engine import MissingInputError, WorkflowEngine


@pytest.fixture
def engine():
    with patch("core.workflow_engine.get_state_manager", return_value=MagicMock()):
        yield WorkflowEngine()


def test_string_with_prefix_and_variable_preserves_text(engine):
    params = {"message": "Hello ${user.name}!"}
    state = {"outputs": {"user": {"name": "Alice"}}}
    resolved = engine._resolve_parameters(params, state)
    assert resolved["message"] == "Hello Alice!", (
        "prefix/suffix around a variable was dropped"
    )


def test_multiple_variables_in_one_string(engine):
    params = {"message": "${first} ${last}"}
    state = {"outputs": {"first": "Ada", "last": "Lovelace"}}
    resolved = engine._resolve_parameters(params, state)
    assert resolved["message"] == "Ada Lovelace", (
        "only the first variable was resolved"
    )


def test_plain_string_untouched(engine):
    params = {"message": "no variables"}
    resolved = engine._resolve_parameters(params, {})
    assert resolved["message"] == "no variables"


def test_input_variable_resolved(engine):
    params = {"topic": "${input.topic}"}
    state = {"input_data": {"topic": "sales"}}
    resolved = engine._resolve_parameters(params, state)
    assert resolved["topic"] == "sales"


def test_missing_variable_raises(engine):
    params = {"message": "${ghost}"}
    with pytest.raises(MissingInputError):
        engine._resolve_parameters(params, {"outputs": {}})


def test_get_value_from_path_no_outputs_key(engine):
    """A state without 'outputs' must yield None, not crash with KeyError."""
    assert engine._get_value_from_path("step1.x", {"input_data": {}}) is None


def test_condition_single_variable(engine):
    state = {"outputs": {"step1": {"output": {"success": True}}}}
    assert engine._evaluate_condition("${step1.output.success} == true", state) is True


def test_condition_missing_variable_is_false(engine):
    state = {"outputs": {"step1": {"output": {}}}}
    assert engine._evaluate_condition("${step1.output.missing} == true", state) is False
