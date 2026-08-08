"""TDD bug-hunt + coverage tests for core/workflow_engine.py.

Focuses on UNcovered regions (where undetected bugs hide):
- _execute_workflow_action sub-workflow timeout/status handling
- _execute_step fallback + error-status propagation
- _convert_nodes_to_steps malformed-connection + cycle handling
- _build_execution_graph / _has_conditional_connections
- _check_dependencies / _path_exists (None-value) edge cases
"""

import sys
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, "/Users/rushiparikh/projects/atom/backend")

import pytest

from core.workflow_engine import (
    MissingInputError,
    SchemaValidationError,
    WorkflowEngine,
)


@pytest.fixture
def engine():
    with patch("core.workflow_engine.get_state_manager", return_value=MagicMock()):
        yield WorkflowEngine()


# ---------------------------------------------------------------------------
# BUG 1 (PRIMARY): sub-workflow "timeout" status is silently treated as SUCCESS
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_execute_step_treats_subworkflow_timeout_as_failure(engine):
    """BUG: _execute_workflow_action returns {"status": "timeout", ...} when a
    sub-workflow times out, but _execute_step only fails steps whose result has
    status == "error". A timed-out sub-workflow was therefore wrapped as
    {"status": "success"} and the parent step marked COMPLETED — masking the
    failure and continuing the workflow as if nothing went wrong."""

    async def fake_workflow_action(action, params, connection_id=None):
        return {
            "action": action,
            "workflow_id": "wf-child",
            "execution_id": "exec-child",
            "status": "timeout",
            "error": "Sub-workflow execution timed out after 1 seconds",
        }

    # Register the fake executor directly into the service registry.
    engine._execute_workflow_action = fake_workflow_action

    step = {
        "id": "sub-wf-step",
        "service": "workflow",
        "action": "run_workflow",
        "parameters": {},
    }

    with pytest.raises(Exception, match="timed out|timeout|failed"):
        await engine._execute_step(step, {})


# ---------------------------------------------------------------------------
# BUG 2: error-status returned from a primary executor must surface as failure
# (regression guard for the status=="error" handling in _execute_step).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_execute_step_error_status_surfaces_as_exception(engine):
    """BUG (regression guard): an executor returning {"status": "error", ...}
    must raise, not be wrapped as a successful result. This guards the fix at
    workflow_engine.py:1222-1225 (primary) and 1255-1259 (fallback)."""

    async def failing_executor(action, params, connection_id=None):
        return {"status": "error", "error": "boom"}

    engine._execute_ai_action = failing_executor

    step = {"id": "ai-step", "service": "ai", "action": "summarize", "parameters": {}}
    with pytest.raises(Exception, match="boom"):
        await engine._execute_step(step, {})


# ---------------------------------------------------------------------------
# BUG 3: unknown service WITHOUT fallback must raise (not return success).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_execute_step_unknown_service_no_fallback_raises(engine):
    """An unknown service with no fallback_service must raise a clear error
    rather than silently succeeding or returning an error dict that the run
    loop would treat as a completed step."""

    # Force the generic catalog path to fail so we reach the "no fallback" arm.
    async def boom_generic(service, action, params, connection_id=None):
        raise RuntimeError("not in catalog")

    with patch.object(engine, "_execute_generic_action", side_effect=boom_generic):
        step = {
            "id": "weird-step",
            "service": "totally_unknown_svc",
            "action": "do",
            "parameters": {},
        }
        with pytest.raises(Exception):
            await engine._execute_step(step, {})


# ---------------------------------------------------------------------------
# BUG 4: unknown service WITH a fallback that succeeds must use the fallback.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_execute_step_falls_back_to_fallback_service(engine):
    """When the primary service is unknown, a valid fallback_service must be
    attempted and its result returned (with fallback_used=True). Previously the
    generic-execution failure aborted before trying the fallback."""

    async def good_fallback(action, params, connection_id=None):
        return {"ok": True}

    engine._execute_ai_action = good_fallback

    async def boom_generic(service, action, params, connection_id=None):
        raise RuntimeError("not in catalog")

    with patch.object(engine, "_execute_generic_action", side_effect=boom_generic):
        step = {
            "id": "fallback-step",
            "service": "totally_unknown_svc",
            "action": "do",
            "parameters": {},
            "fallback_service": "ai",
        }
        result = await engine._execute_step(step, {})
    assert result["status"] == "success"
    assert result.get("fallback_used") is True
    assert result["execution_method"] == "fallback_service"


# ---------------------------------------------------------------------------
# Coverage: _has_conditional_connections
# ---------------------------------------------------------------------------
def test_has_conditional_connections_true(engine):
    wf = {"connections": [{"source": "a", "target": "b", "condition": "${x} > 1"}]}
    assert engine._has_conditional_connections(wf) is True


def test_has_conditional_connections_false_empty(engine):
    assert engine._has_conditional_connections({}) is False


def test_has_conditional_connections_false_no_truthy(engine):
    wf = {"connections": [{"source": "a", "target": "b", "condition": ""}]}
    assert engine._has_conditional_connections(wf) is False


# ---------------------------------------------------------------------------
# Coverage: _convert_nodes_to_steps skips malformed connections + detects cycles
# ---------------------------------------------------------------------------
def test_convert_nodes_skips_malformed_connection(engine):
    """A connection missing source/target must be skipped, not crash."""
    wf = {
        "nodes": [
            {"id": "a"},
            {"id": "b"},
        ],
        "connections": [
            {"source": "a", "target": "b"},
            {"source": None, "target": "b"},  # malformed
            {"source": "a", "target": None},  # malformed
        ],
    }
    steps = engine._convert_nodes_to_steps(wf)
    ids = [s["id"] for s in steps]
    assert ids == ["a", "b"]


def test_convert_nodes_detects_cycle(engine):
    """A cycle in the graph must raise ValueError, not silently truncate."""
    wf = {
        "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
        "connections": [
            {"source": "a", "target": "b"},
            {"source": "b", "target": "c"},
            {"source": "c", "target": "a"},  # cycle a->b->c->a
        ],
    }
    with pytest.raises(ValueError, match="circular|cycle"):
        engine._convert_nodes_to_steps(wf)


def test_convert_nodes_assigns_sequence_order(engine):
    wf = {
        "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
        "connections": [
            {"source": "a", "target": "b"},
            {"source": "b", "target": "c"},
        ],
    }
    steps = engine._convert_nodes_to_steps(wf)
    assert [s["sequence_order"] for s in steps] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Coverage: _build_execution_graph ignores connections to unknown nodes
# ---------------------------------------------------------------------------
def test_build_execution_graph_ignores_unknown_nodes(engine):
    wf = {
        "nodes": [{"id": "a"}, {"id": "b"}],
        "connections": [
            {"source": "a", "target": "b"},
            {"source": "a", "target": "ghost"},  # target not in nodes
            {"source": "ghost2", "target": "b"},  # source not in nodes
        ],
    }
    graph = engine._build_execution_graph(wf)
    assert graph["adjacency"]["a"] == [{"source": "a", "target": "b"}]
    # b has one incoming (from a only)
    assert len(graph["reverse_adjacency"]["b"]) == 1


# ---------------------------------------------------------------------------
# Coverage: _check_dependencies
# ---------------------------------------------------------------------------
def test_check_dependencies_completed(engine):
    step = {"depends_on": ["x", "y"]}
    state = {"steps": {"x": {"status": "COMPLETED"}, "y": {"status": "COMPLETED"}}}
    assert engine._check_dependencies(step, state) is True


def test_check_dependencies_one_pending(engine):
    step = {"depends_on": ["x", "y"]}
    state = {"steps": {"x": {"status": "COMPLETED"}, "y": {"status": "PENDING"}}}
    assert engine._check_dependencies(step, state) is False


def test_check_dependencies_missing_dep(engine):
    """A dependency id not present in state must count as unmet."""
    step = {"depends_on": ["x", "ghost"]}
    state = {"steps": {"x": {"status": "COMPLETED"}}}
    assert engine._check_dependencies(step, state) is False


def test_check_dependencies_empty(engine):
    assert engine._check_dependencies({}, {"steps": {}}) is True


# ---------------------------------------------------------------------------
# Coverage: _path_exists (None output value vs missing variable)
# ---------------------------------------------------------------------------
def test_path_exists_input_present(engine):
    state = {"input_data": {"topic": "x"}}
    assert engine._path_exists("input.topic", state) is True


def test_path_exists_input_missing_key(engine):
    state = {"input_data": {}}
    assert engine._path_exists("input.topic", state) is False


def test_path_exists_step_output_present(engine):
    state = {"outputs": {"step1": {"k": "v"}}}
    assert engine._path_exists("step1.k", state) is True


def test_path_exists_step_missing_root(engine):
    state = {"outputs": {}}
    assert engine._path_exists("ghost.k", state) is False


def test_resolve_value_none_output_does_not_raise(engine):
    """A legitimately-None output value must NOT raise MissingInputError —
    it should resolve to None (distinguishes missing var from null value)."""
    state = {"outputs": {"step1": {"k": None}}}
    # Path exists (key present), value is None -> resolve to None, no raise.
    assert engine._resolve_parameter_value("${step1.k}", state) is None


# ---------------------------------------------------------------------------
# Coverage: _get_value_from_path walks non-dict safely
# ---------------------------------------------------------------------------
def test_get_value_from_path_walks_past_dict(engine):
    state = {"outputs": {"step1": {"nested": {"deep": 42}}}}
    assert engine._get_value_from_path("step1.nested.deep", state) == 42


def test_get_value_from_path_non_dict_returns_none(engine):
    """If an intermediate value is not a dict, sub-paths must yield None."""
    state = {"outputs": {"step1": "a-string"}}
    assert engine._get_value_from_path("step1.nested", state) is None


def test_get_value_from_path_no_outputs_key(engine):
    assert engine._get_value_from_path("step1.x", {}) is None


# ---------------------------------------------------------------------------
# Coverage: _evaluate_condition edge cases
# ---------------------------------------------------------------------------
def test_evaluate_condition_empty_is_true(engine):
    assert engine._evaluate_condition("", {}) is True


def test_evaluate_condition_none_is_true(engine):
    assert engine._evaluate_condition(None, {}) is True


def test_evaluate_condition_numeric_comparison(engine):
    state = {"outputs": {"step1": {"output": {"count": 10}}}}
    assert engine._evaluate_condition("${step1.output.count} > 5", state) is True
    assert engine._evaluate_condition("${step1.output.count} > 50", state) is False


# ---------------------------------------------------------------------------
# Coverage: _validate_input_schema / _validate_output_schema
# ---------------------------------------------------------------------------
def test_validate_input_schema_passes(engine):
    step = {"id": "s1", "input_schema": {"type": "object", "required": ["x"]}}
    engine._validate_input_schema(step, {"x": 1})  # no raise


def test_validate_input_schema_fails(engine):
    step = {"id": "s1", "input_schema": {"type": "object", "required": ["x"]}}
    with pytest.raises(SchemaValidationError):
        engine._validate_input_schema(step, {})


def test_validate_input_schema_no_schema(engine):
    engine._validate_input_schema({"id": "s1"}, {})  # no raise


def test_validate_output_schema_fails(engine):
    step = {"id": "s1", "output_schema": {"type": "object", "required": ["y"]}}
    with pytest.raises(SchemaValidationError):
        engine._validate_output_schema(step, {})


# ---------------------------------------------------------------------------
# Coverage: _resolve_parameter_value recurses into nested dict/list
# ---------------------------------------------------------------------------
def test_resolve_parameter_value_nested_dict(engine):
    params = {"cfg": {"url": "${input.host}", "port": 80}}
    state = {"input_data": {"host": "example.com"}}
    out = engine._resolve_parameters(params, state)
    assert out["cfg"]["url"] == "example.com"
    assert out["cfg"]["port"] == 80


def test_resolve_parameter_value_list(engine):
    params = {"items": ["${input.a}", "${input.b}"]}
    state = {"input_data": {"a": "x", "b": "y"}}
    out = engine._resolve_parameters(params, state)
    assert out["items"] == ["x", "y"]


def test_resolve_parameter_value_non_string_passthrough(engine):
    assert engine._resolve_parameter_value(42, {}) == 42
    assert engine._resolve_parameter_value(True, {}) is True
    assert engine._resolve_parameter_value(None, {}) is None
