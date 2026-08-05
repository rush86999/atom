"""
TDD tests for WorkflowEngine._convert_nodes_to_steps (graph → linear steps).

Covers ordering (linear/diamond/disconnected), cycle detection, trigger node
mapping, unknown-node references, and malformed-connection robustness — a
missing 'target' key must not crash the whole conversion (which would also
break the R67 security gate that resolves nodes → steps).
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


def _wf(nodes, connections=None):
    return {"id": "wf", "nodes": nodes, "connections": connections or []}


def _node(nid, service="http", action="get", node_type="action"):
    return {
        "id": nid,
        "title": f"Node {nid}",
        "type": node_type,
        "config": {"service": service, "action": action, "parameters": {"url": nid}},
    }


def test_linear_chain_preserves_order(engine):
    wf = _wf([_node("a"), _node("b"), _node("c")], [
        {"source": "a", "target": "b"},
        {"source": "b", "target": "c"},
    ])
    steps = engine._convert_nodes_to_steps(wf)
    assert [s["id"] for s in steps] == ["a", "b", "c"]


def test_diamond_ordering(engine):
    wf = _wf([_node("a"), _node("b"), _node("c"), _node("d")], [
        {"source": "a", "target": "b"},
        {"source": "a", "target": "c"},
        {"source": "b", "target": "d"},
        {"source": "c", "target": "d"},
    ])
    steps = engine._convert_nodes_to_steps(wf)
    ids = [s["id"] for s in steps]
    assert ids[0] == "a"
    assert ids[-1] == "d"
    assert set(ids) == {"a", "b", "c", "d"}


def test_disconnected_nodes_all_present(engine):
    wf = _wf([_node("a"), _node("b")])
    steps = engine._convert_nodes_to_steps(wf)
    assert {s["id"] for s in steps} == {"a", "b"}


def test_cycle_detection_raises(engine):
    wf = _wf([_node("a"), _node("b")], [
        {"source": "a", "target": "b"},
        {"source": "b", "target": "a"},
    ])
    with pytest.raises(ValueError, match="circular"):
        engine._convert_nodes_to_steps(wf)


def test_connection_to_unknown_node_ignored(engine):
    wf = _wf([_node("a"), _node("b")], [
        {"source": "a", "target": "ghost"},
    ])
    steps = engine._convert_nodes_to_steps(wf)
    assert {s["id"] for s in steps} == {"a", "b"}


def test_trigger_node_maps_default_action(engine):
    # Trigger node whose config carries no action → manual_trigger default.
    node = {
        "id": "t1",
        "title": "Trigger",
        "type": "trigger",
        "config": {"service": "trigger"},
    }
    steps = engine._convert_nodes_to_steps(_wf([node]))
    assert steps[0]["type"] == "trigger"
    assert steps[0]["action"] == "manual_trigger"


def test_step_fields_populated_from_config(engine):
    wf = _wf([_node("a", service="slack", action="send_message")])
    steps = engine._convert_nodes_to_steps(wf)
    step = steps[0]
    assert step["service"] == "slack"
    assert step["action"] == "send_message"
    assert step["parameters"] == {"url": "a"}
    assert step["sequence_order"] == 1


def test_malformed_connection_missing_target_does_not_crash(engine):
    """A connection dict without 'target' must not raise KeyError and kill
    the whole conversion (and thus the security gate / execution)."""
    wf = _wf([_node("a"), _node("b")], [
        {"source": "a"},  # missing 'target'
    ])
    steps = engine._convert_nodes_to_steps(wf)
    assert {s["id"] for s in steps} == {"a", "b"}
