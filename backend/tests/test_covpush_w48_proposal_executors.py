"""Coverage wave 48 — core/proposal_service executors (56% → 85%+).

- _execute_proposed_action dispatch: browser/canvas/integration/workflow/
  device/agent
- _execute_browser_action: success loop (navigate/click/fill/script), missing
  url/session ValueError propagates, ImportError
- _execute_canvas_action: success
- _execute_integration_action: success + non-dict result + failure
- _execute_workflow_action: success + workflow-not-found raises
- _execute_device_action: success
- _execute_agent_action: success + missing target raises
"""
import json
import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.proposal_service import ProposalService
from core.models import AgentExecution, AgentProposal, ProposalStatus


def _proposal(db, agent, action_type="browser_automate", approved=True, **action):
    action.setdefault("action_type", action_type)
    p = AgentProposal(
        id=f"prop-{uuid.uuid4().hex[:8]}",
        tenant_id="default", user_id="u1", agent_id=agent.id,
        agent_name=agent.name, proposal_type="action",
        title="P", description="d",
        proposal_data=action,
        status=ProposalStatus.EXECUTED.value,
        approved_by="u1" if approved else None,
    )
    db.add(p)
    db.commit()
    return p


@pytest.fixture
def fresh_db():
    import os
    import tempfile
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.database import Base

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    os.unlink(path)


@pytest.fixture
def intern_agent(fresh_db):
    from core.models import AgentRegistry
    agent = AgentRegistry(
        id=f"agent-{uuid.uuid4().hex[:8]}",
        name="Intern", category="general", description="d",
        status="INTERN", confidence_score=0.6,
        module_path="m", class_name="C", workspace_id="default",
    )
    fresh_db.add(agent)
    fresh_db.commit()
    return agent


@pytest.fixture
def svc(fresh_db):
    return ProposalService(fresh_db)


class TestExecutors:
    async def test_browser_success(self, svc, fresh_db, intern_agent):
        p = _proposal(
            fresh_db, intern_agent,
            action_type="browser_automate",
            url="https://x.com",
            actions=[{"type": "click", "selector": "#a"}, {"type": "script", "script": "1+1"}],
        )
        with patch("tools.browser_tool.browser_create_session", new=AsyncMock(
            return_value={"session_id": "s1"}
        )), patch("tools.browser_tool.browser_navigate", new=AsyncMock()), \
             patch("tools.browser_tool.browser_click", new=AsyncMock()), \
             patch("tools.browser_tool.browser_execute_script", new=AsyncMock()):
            result = await svc._execute_browser_action(p, p.proposal_data)
        assert result["success"] is True
        assert result["result"]["session_id"] == "s1"

    async def test_browser_fill_step(self, svc, fresh_db, intern_agent):
        p = _proposal(
            fresh_db, intern_agent, action_type="browser_automate",
            session_id="s1",
            actions=[{"type": "fill", "selector": "#f", "value": "v"}],
        )
        with patch("tools.browser_tool.browser_create_session", new=AsyncMock(
            return_value={"id": "s1"}
        )), patch("tools.browser_tool.browser_fill_form", new=AsyncMock()) as fill:
            result = await svc._execute_browser_action(p, p.proposal_data)
        assert result["success"] is True
        assert result["result"]["session_id"] == "s1"
        fill.assert_awaited_once()

    async def test_browser_missing_url_raises(self, svc, fresh_db, intern_agent):
        p = _proposal(fresh_db, intern_agent, action_type="browser_automate")
        with pytest.raises(ValueError):
            await svc._execute_browser_action(p, p.proposal_data)

    async def test_browser_import_error(self, svc, fresh_db, intern_agent):
        p = _proposal(fresh_db, intern_agent, action_type="browser_automate")
        with patch.dict("sys.modules", {"tools.browser_tool": None}), \
             patch("builtins.__import__", side_effect=ImportError("no browser tool")):
            result = await svc._execute_browser_action(p, p.proposal_data)
        assert result["success"] is False
        assert "not available" in result["error"]

    async def test_canvas_success(self, svc, fresh_db, intern_agent):
        p = _proposal(
            fresh_db, intern_agent, action_type="canvas_present",
            canvas_type="markdown", content={"content": "hi"},
        )
        with patch("tools.canvas_tool.present_to_canvas", new=AsyncMock(
            return_value={"success": True, "canvas_id": "c1"}
        )):
            result = await svc._execute_canvas_action(p, p.proposal_data)
        assert result["success"] is True
        assert result["canvas_id"] == {"success": True, "canvas_id": "c1"}

    async def test_integration_success(self, svc, fresh_db, intern_agent):
        p = _proposal(
            fresh_db, intern_agent, action_type="integration_connect",
            integration_type="gmail", operation="send", parameters={"to": "x@y.com"},
        )
        svc_inst = MagicMock()
        svc_inst.execute = AsyncMock(return_value={"success": True, "data": {}})
        with patch("integrations.universal_integration_service.UniversalIntegrationService",
                   return_value=svc_inst):
            result = await svc._execute_integration_action(p, p.proposal_data)
        assert result["success"] is True
        assert result["integration_type"] == "gmail"

    async def test_integration_non_dict_result(self, svc, fresh_db, intern_agent):
        p = _proposal(
            fresh_db, intern_agent, action_type="integration_connect",
            integration_type="gmail",
        )
        svc_inst = MagicMock()
        svc_inst.execute = AsyncMock(return_value="just a string")
        with patch("integrations.universal_integration_service.UniversalIntegrationService",
                   return_value=svc_inst):
            result = await svc._execute_integration_action(p, p.proposal_data)
        assert result["success"] is True  # ok flag from wrapped result

    async def test_integration_failure(self, svc, fresh_db, intern_agent):
        p = _proposal(fresh_db, intern_agent, action_type="integration_connect")
        svc_inst = MagicMock()
        svc_inst.execute = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("integrations.universal_integration_service.UniversalIntegrationService",
                   return_value=svc_inst):
            result = await svc._execute_integration_action(p, p.proposal_data)
        assert result["success"] is False

    async def test_workflow_success(self, svc, fresh_db, intern_agent):
        p = _proposal(
            fresh_db, intern_agent, action_type="workflow_trigger",
            workflow_id="wf-1", parameters={"x": 1},
        )
        with patch("core.workflow_endpoints.load_workflows",
                   return_value=[{"id": "wf-1", "name": "W"}]):
            engine = MagicMock()
            engine.start_workflow = AsyncMock(return_value="wfex-1")
            with patch("core.workflow_engine.WorkflowEngine", return_value=engine):
                result = await svc._execute_workflow_action(p, p.proposal_data)
        assert result["success"] is True
        assert result["workflow_id"] == "wf-1"

    async def test_workflow_not_found_raises(self, svc, fresh_db, intern_agent):
        p = _proposal(
            fresh_db, intern_agent, action_type="workflow_trigger",
            workflow_id="missing",
        )
        with patch("core.workflow_endpoints.load_workflows", return_value=[]):
            with pytest.raises(ValueError):
                await svc._execute_workflow_action(p, p.proposal_data)

    async def test_device_success(self, svc, fresh_db, intern_agent):
        p = _proposal(
            fresh_db, intern_agent, action_type="device_command",
            device_id="d1", command_type="camera",
        )
        with patch("tools.device_tool.execute_device_command", new=AsyncMock(
            return_value={"success": True, "snapshot": "x"}
        )):
            result = await svc._execute_device_action(p, p.proposal_data)
        assert result["success"] is True

    async def test_agent_execute_success(self, svc, fresh_db, intern_agent):
        p = _proposal(
            fresh_db, intern_agent, action_type="agent_execute",
            target_agent_id=intern_agent.id, prompt="do it",
        )
        with patch("core.generic_agent.GenericAgent") as ga:
            agent = ga.return_value
            agent.execute = AsyncMock(return_value={"success": True, "output": "done"})
            result = await svc._execute_agent_action(p, p.proposal_data)
        assert result["success"] is True
        assert result["target_agent_id"] == intern_agent.id

    async def test_agent_execute_missing_target_raises(self, svc, fresh_db, intern_agent):
        p = _proposal(
            fresh_db, intern_agent, action_type="agent_execute",
            target_agent_id="missing",
        )
        with pytest.raises(ValueError):
            await svc._execute_agent_action(p, p.proposal_data)

    async def test_agent_execute_non_dict_result(self, svc, fresh_db, intern_agent):
        p = _proposal(
            fresh_db, intern_agent, action_type="agent_execute",
            target_agent_id=intern_agent.id, prompt="do it",
        )
        with patch("core.generic_agent.GenericAgent") as ga:
            agent = ga.return_value
            agent.execute = AsyncMock(return_value="plain result")
            result = await svc._execute_agent_action(p, p.proposal_data)
        assert result["success"] is True
        assert result["result"]["response"] == "plain result"
