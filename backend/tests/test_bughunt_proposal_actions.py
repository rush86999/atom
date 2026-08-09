"""TDD bug-hunt: proposal action execution wiring (R92 follow-up).

Four of six proposal action types could never execute — they imported
phantom functions:
- agent_execute: `core.generic_agent.execute_agent` (real: GenericAgent(agent_model).execute)
- workflow_trigger: `core.workflow_engine.trigger_workflow` (real: load_workflows() + WorkflowEngine().start_workflow)
- integration_connect: `core.integrations.get_integration_service` (real: UniversalIntegrationService().execute)
- browser_automate: `tools.browser_tool.execute_browser_automation` (real: browser_create_session/navigate/click/close)
Every such execution swallowed an ImportError into an error dict.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _service():
    from core.proposal_service import ProposalService

    return ProposalService(db=MagicMock())


def _proposal(agent_id="agent-1", approver="user-1", pid="prop-1"):
    return SimpleNamespace(id=pid, agent_id=agent_id, approved_by=approver)


@pytest.mark.asyncio
async def test_agent_execute_wired_to_generic_agent():
    from core.models import AgentRegistry  # noqa: F401 (patch target anchor)

    service = _service()
    registry_row = SimpleNamespace(id="target-1")
    service.db.query.return_value.filter.return_value.first.return_value = registry_row

    agent = MagicMock()
    agent.execute = AsyncMock(return_value={"success": True, "response": "done"})
    with patch("core.generic_agent.GenericAgent", return_value=agent):
        result = await service._execute_agent_action(
            _proposal(),
            {"action_type": "agent_execute", "target_agent_id": "target-1", "prompt": "do it"},
        )

    assert result["success"] is True
    agent.execute.assert_awaited_once()
    assert agent.execute.await_args.kwargs["task_input"] == "do it"


@pytest.mark.asyncio
async def test_agent_execute_missing_target_agent_fails_cleanly():
    service = _service()
    service.db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(ValueError, match="not found"):
        await service._execute_agent_action(
            _proposal(), {"action_type": "agent_execute", "target_agent_id": "nope", "prompt": "x"}
        )


@pytest.mark.asyncio
async def test_workflow_trigger_wired_to_engine():
    with patch(
        "core.workflow_endpoints.load_workflows",
        return_value=[{"id": "wf-1", "name": "W", "steps": []}],
    ), patch("core.workflow_engine.WorkflowEngine") as we_cls:
        engine = MagicMock()
        engine.start_workflow = AsyncMock(return_value="exec-9")
        we_cls.return_value = engine

        service = _service()
        result = await service._execute_workflow_action(
            _proposal(),
            {"action_type": "workflow_trigger", "workflow_id": "wf-1", "parameters": {"p": 1}},
        )

    assert result["success"] is True
    assert result["result"]["execution_id"] == "exec-9"
    engine.start_workflow.assert_awaited_once()
    assert engine.start_workflow.await_args.kwargs["input_data"] == {"p": 1}


@pytest.mark.asyncio
async def test_workflow_trigger_missing_workflow_fails_cleanly():
    with patch("core.workflow_endpoints.load_workflows", return_value=[]):
        service = _service()
        with pytest.raises(ValueError, match="not found"):
            await service._execute_workflow_action(
                _proposal(), {"action_type": "workflow_trigger", "workflow_id": "wf-x"}
            )


@pytest.mark.asyncio
async def test_integration_connect_wired_to_universal():
    with patch(
        "integrations.universal_integration_service.UniversalIntegrationService"
    ) as ui_cls:
        inst = MagicMock()
        inst.execute = AsyncMock(return_value={"ok": True, "data": {"x": 1}})
        ui_cls.return_value = inst

        service = _service()
        result = await service._execute_integration_action(
            _proposal(),
            {
                "action_type": "integration_connect",
                "integration_type": "slack",
                "operation": "send",
                "parameters": {"msg": "hi"},
            },
        )

    assert result["success"] is True
    inst.execute.assert_awaited_once()
    assert inst.execute.await_args.kwargs["service"] == "slack"
    assert inst.execute.await_args.kwargs["action"] == "send"


@pytest.mark.asyncio
async def test_browser_automate_wired_to_tool_functions():
    nav = AsyncMock()
    click = AsyncMock()
    close = AsyncMock()
    with patch(
        "tools.browser_tool.browser_create_session",
        new=AsyncMock(return_value={"session_id": "s-1"}),
    ), patch("tools.browser_tool.browser_navigate", new=nav), patch(
        "tools.browser_tool.browser_click", new=click
    ), patch("tools.browser_tool.browser_close_session", new=close):
        service = _service()
        result = await service._execute_browser_action(
            _proposal(),
            {
                "action_type": "browser_automate",
                "url": "https://example.com",
                "actions": [{"type": "click", "selector": "#b"}],
            },
        )

    assert result["success"] is True
    nav.assert_awaited_once()
    click.assert_awaited_once()
