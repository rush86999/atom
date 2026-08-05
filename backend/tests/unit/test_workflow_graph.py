"""
TDD tests for WorkflowEngine graph helpers: _build_execution_graph,
_has_conditional_connections, and _evaluate_condition edge cases.
"""

import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, "/Users/rushiparikh/projects/atom/backend")

import pytest

from core.workflow_engine import WorkflowEngine


@pytest.fixture
def engine():
    with patch("core.workflow_engine.get_state_manager", return_value=MagicMock()):
        yield WorkflowEngine()


def _node(nid):
    return {"id": nid, "title": f"N {nid}", "config": {"service": "http"}}


def test_build_execution_graph_adjacency(engine):
    wf = {"id": "wf", "nodes": [_node("a"), _node("b"), _node("c")], "connections": [
        {"source": "a", "target": "b"},
        {"source": "a", "target": "c"},
    ]}
    graph = engine._build_execution_graph(wf)
    assert set(graph["nodes"]) == {"a", "b", "c"}
    assert {c["target"] for c in graph["adjacency"]["a"]} == {"b", "c"}
    assert graph["reverse_adjacency"]["b"][0]["source"] == "a"


def test_build_execution_graph_ignores_bad_connections(engine):
    wf = {"id": "wf", "nodes": [_node("a"), _node("b")], "connections": [
        {"source": "a", "target": "ghost"},
        {"source": None, "target": "b"},
        {"source": "a"},  # missing target
    ]}
    graph = engine._build_execution_graph(wf)
    assert graph["adjacency"]["a"] == []
    assert graph["reverse_adjacency"]["b"] == []


def test_has_conditional_connections(engine):
    assert engine._has_conditional_connections({"connections": [{"source": "a", "target": "b"}]}) is False
    assert engine._has_conditional_connections({"connections": [{"condition": "x > 1"}]}) is True
    assert engine._has_conditional_connections({}) is False


def test_evaluate_condition_truthy_non_boolean(engine):
    assert engine._evaluate_condition("5", {}) is True
    assert engine._evaluate_condition("0", {}) is False


def test_evaluate_condition_injection_blocked_returns_false(engine):
    assert engine._evaluate_condition("__import__('os').system('id')", {}) is False
    assert engine._evaluate_condition("", {}) is True  # empty = always run
