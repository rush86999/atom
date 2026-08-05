"""
TDD regression tests for WorkflowEngine.start_workflow.

start_workflow read workflow["id"] directly, so a definition carrying only the
alternate key "workflow_id" (seen across the codebase) crashed with KeyError
before any execution could start.
"""

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, "/Users/rushiparikh/projects/atom/backend")

import pytest

from core.workflow_engine import WorkflowEngine


@pytest.fixture
def engine():
    with patch("core.workflow_engine.get_state_manager", return_value=MagicMock()):
        yield WorkflowEngine()


def _node(nid):
    return {"id": nid, "title": f"Node {nid}", "type": "action",
            "config": {"service": "http", "action": "get"}}


@pytest.mark.asyncio
async def test_start_workflow_accepts_workflow_id_only(engine):
    """A workflow defined with only workflow_id must start without KeyError."""
    workflow = {"workflow_id": "wf_1", "nodes": [_node("a")]}
    engine.state_manager.create_execution = AsyncMock(return_value="exec_1")
    engine._publish_orchestration_event = MagicMock()
    fake_bt = SimpleNamespace(add_task=MagicMock())

    execution_id = await engine.start_workflow(workflow, {"k": "v"}, fake_bt)

    assert execution_id == "exec_1"
    engine.state_manager.create_execution.assert_awaited_once_with("wf_1", {"k": "v"})


@pytest.mark.asyncio
async def test_start_workflow_uses_id_key(engine):
    """The canonical id-keyed definition must still work."""
    workflow = {"id": "wf_2", "nodes": [_node("a")]}
    engine.state_manager.create_execution = AsyncMock(return_value="exec_2")
    engine._publish_orchestration_event = MagicMock()
    fake_bt = SimpleNamespace(add_task=MagicMock())

    execution_id = await engine.start_workflow(workflow, {"k": "v"}, fake_bt)

    assert execution_id == "exec_2"
    engine.state_manager.create_execution.assert_awaited_once_with("wf_2", {"k": "v"})


@pytest.mark.asyncio
async def test_start_workflow_converts_nodes_to_steps(engine):
    """A node-graph workflow gets its linear steps populated in place."""
    workflow = {"id": "wf_3", "nodes": [_node("a"), _node("b")]}
    engine.state_manager.create_execution = AsyncMock(return_value="exec_3")
    engine._publish_orchestration_event = MagicMock()
    fake_bt = SimpleNamespace(add_task=MagicMock())

    await engine.start_workflow(workflow, {}, fake_bt)

    assert "steps" in workflow
    assert {s["id"] for s in workflow["steps"]} == {"a", "b"}
