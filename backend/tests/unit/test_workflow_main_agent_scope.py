"""Regressions for the main_agent workflow readiness defect.

Observed defect: an ordinary ``_execute_step`` with ``service="main_agent"``,
a configured ``params.agent_id`` and a scoped step returned an OUTER
``status="success"`` wrapping an inner ``success=False``. The main_agent
executor dropped ``params.agent_id`` (and the step's trusted workspace/
tenant), so the agent could never resolve. A provider failure was likewise
fabricated into a successful "fallback" response.

These tests drive the real ``_execute_step`` dispatch path with the DB and
the LLM service facade mocked. Agent rows use the real AgentRegistry shape
(workspace_id/tenant_id/enabled/configuration) rather than invented ORM
model/provider attributes. No provider, MCP or network call is made.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..")))

from core.models import AgentRegistry
from core.workflow_engine import WorkflowEngine


def _bypass_retry(engine):
    """Bypass @async_retry_with_backoff (7s+ on expected failures)."""
    fn = WorkflowEngine._execute_step
    if hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    engine._execute_step = fn.__get__(engine)
    return engine


@pytest.fixture
def engine():
    with patch("core.workflow_engine.get_state_manager",
               return_value=MagicMock()):
        return _bypass_retry(WorkflowEngine())


def _db_session(agent):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = agent
    ctx = MagicMock()
    ctx.__enter__.return_value = db
    ctx.__exit__.return_value = False
    return ctx


def _agent(**overrides):
    """Transient real AgentRegistry row (no llm_provider/llm_model)."""
    values = dict(
        id="agent-1",
        workspace_id="ws-1",
        tenant_id="tenant-1",
        enabled=True,
        configuration={},
    )
    values.update(overrides)
    return AgentRegistry(**values)


def _scoped_step(**overrides):
    step = {
        "id": "s1",
        "service": "main_agent",
        "action": "analyze",
        "parameters": {"agent_id": "agent-1"},
        "workspace_id": "ws-1",
        "tenant_id": "tenant-1",
    }
    step.update(overrides)
    return step


def _llm(response=None, side_effect=None):
    service = MagicMock()
    if side_effect is not None:
        service.generate_completion = AsyncMock(side_effect=side_effect)
    else:
        service.generate_completion = AsyncMock(return_value=response)
    return service, service.generate_completion


def _success_completion(content="answer", provider="openai", model="gpt-4o"):
    return {
        "success": True,
        "content": content,
        "text": content,
        "provider": provider,
        "model": model,
        "usage": {"total_tokens": 3},
        "finish_reason": "stop",
    }


@pytest.mark.asyncio
async def test_execute_step_main_agent_success_is_not_an_outer_only_success(engine):
    """The ordinary route must resolve params.agent_id and return a real
    success whose inner payload also says success."""
    llm_service, generate = _llm(_success_completion("answer"))
    step = _scoped_step()

    with patch("core.database.get_db_session",
               return_value=_db_session(_agent())), \
         patch("core.llm_service.get_llm_service",
               return_value=llm_service) as get_llm:
        result = await engine._execute_step(step, step["parameters"])

    assert result["status"] == "success"
    inner = result["result"]
    assert inner["status"] == "success"
    payload = inner["result"]
    assert payload["success"] is True
    assert payload["agent_response"] == "answer"
    assert payload["content"] == "answer"
    assert payload["agent_id"] == "agent-1"
    assert payload["provider"] == "openai"
    assert payload["model"] == "gpt-4o"
    generate.assert_awaited_once()
    assert get_llm.call_args.kwargs["workspace_id"] == "ws-1"
    assert get_llm.call_args.kwargs["tenant_id"] == "tenant-1"
    # Exact scope is also sent to the completion facade.
    assert generate.call_args.kwargs["workspace_id"] == "ws-1"
    assert generate.call_args.kwargs["tenant_id"] == "tenant-1"
    assert generate.call_args.kwargs["agent_id"] == "agent-1"


@pytest.mark.asyncio
async def test_execute_step_main_agent_rejects_mcp_servers(engine):
    """main_agent is text-only: an explicit MCP request is refused before
    any agent lookup, MCP discovery or LLM dispatch."""
    step = _scoped_step(
        parameters={"agent_id": "agent-1", "mcp_servers": ["srv-1"]})

    with patch("core.database.get_db_session") as get_db, \
         patch("core.llm_service.get_llm_service") as get_llm:
        with pytest.raises(Exception, match="mcp_servers"):
            await engine._execute_step(step, step["parameters"])

    get_db.assert_not_called()
    get_llm.assert_not_called()


@pytest.mark.asyncio
async def test_execute_step_main_agent_foreign_agent_is_rejected(engine):
    """An agent registered in another workspace/tenant must be denied before
    the LLM service is dispatched."""
    llm_service, generate = _llm(_success_completion("must not run"))
    step = _scoped_step()

    # The real scoped query filters on the exact (id, workspace, tenant)
    # tuple, so a foreign row is simply no match.
    with patch("core.database.get_db_session",
               return_value=_db_session(None)), \
         patch("core.llm_service.get_llm_service",
               return_value=llm_service) as get_llm:
        with pytest.raises(Exception, match="not available"):
            await engine._execute_step(step, step["parameters"])

    get_llm.assert_not_called()
    generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_step_main_agent_disabled_agent_is_rejected(engine):
    llm_service, generate = _llm(_success_completion("must not run"))
    step = _scoped_step()

    # A disabled row is excluded by the admission query's enabled predicate.
    with patch("core.database.get_db_session",
               return_value=_db_session(None)), \
         patch("core.llm_service.get_llm_service",
               return_value=llm_service) as get_llm:
        with pytest.raises(Exception, match="not available"):
            await engine._execute_step(step, step["parameters"])

    get_llm.assert_not_called()
    generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_step_main_agent_missing_agent_is_rejected(engine):
    """params.agent_id is configured authority; absent means deny."""
    step = _scoped_step(parameters={})

    with patch("core.database.get_db_session") as get_db, \
         patch("core.llm_service.get_llm_service") as get_llm:
        with pytest.raises(Exception, match="agent_id"):
            await engine._execute_step(step, {})

    get_db.assert_not_called()
    get_llm.assert_not_called()


@pytest.mark.asyncio
async def test_execute_step_main_agent_unresolved_scope_is_rejected(engine):
    """A direct caller has no trusted workspace/tenant: never default it."""
    step = {
        "id": "s1",
        "service": "main_agent",
        "action": "analyze",
        "parameters": {"agent_id": "agent-1"},
    }

    with patch("core.database.get_db_session") as get_db, \
         patch("core.llm_service.get_llm_service") as get_llm:
        with pytest.raises(Exception, match="scope"):
            await engine._execute_step(step, step["parameters"])

    get_db.assert_not_called()
    get_llm.assert_not_called()


@pytest.mark.asyncio
async def test_execute_step_main_agent_provider_failure_is_not_completed(engine):
    """Provider failure must surface through the existing status:error
    envelope (so the run loop marks the step FAILED), not a fake success."""
    llm_service, generate = _llm({
        "success": False,
        "content": "",
        "text": "",
        "provider": None,
        "model": None,
        "error": "every configured provider failed",
        "failure": {"reason": "generation_failed",
                    "last_error": "provider secret"},
    })
    step = _scoped_step()

    with patch("core.database.get_db_session",
               return_value=_db_session(_agent())), \
         patch("core.llm_service.get_llm_service",
               return_value=llm_service):
        with pytest.raises(Exception) as exc_info:
            await engine._execute_step(step, step["parameters"])

    message = str(exc_info.value)
    assert "main_agent LLM execution failed" in message
    assert "provider secret" not in message


@pytest.mark.asyncio
async def test_execute_step_main_agent_provider_exception_is_not_completed(engine):
    llm_service, generate = _llm(side_effect=RuntimeError("provider secret"))
    step = _scoped_step()

    with patch("core.database.get_db_session",
               return_value=_db_session(_agent())), \
         patch("core.llm_service.get_llm_service",
               return_value=llm_service):
        with pytest.raises(Exception) as exc_info:
            await engine._execute_step(step, step["parameters"])

    message = str(exc_info.value)
    assert "main_agent LLM execution failed" in message
    assert "provider secret" not in message


@pytest.mark.asyncio
async def test_execute_step_main_agent_empty_response_is_not_completed(engine):
    llm_service, generate = _llm({
        "success": False,
        "content": "",
        "text": "",
        "provider": None,
        "model": None,
        "failure": {"reason": "empty_generation"},
    })
    step = _scoped_step()

    with patch("core.database.get_db_session",
               return_value=_db_session(_agent())), \
         patch("core.llm_service.get_llm_service",
               return_value=llm_service):
        with pytest.raises(Exception, match="no usable response"):
            await engine._execute_step(step, step["parameters"])

    generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_step_main_agent_blank_success_is_not_completed(engine):
    llm_service, generate = _llm(_success_completion("   "))
    step = _scoped_step()

    with patch("core.database.get_db_session",
               return_value=_db_session(_agent())), \
         patch("core.llm_service.get_llm_service",
               return_value=llm_service):
        with pytest.raises(Exception, match="no usable response"):
            await engine._execute_step(step, step["parameters"])

    generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_step_main_agent_fallback_path_gets_trusted_scope(engine):
    """The fallback main_agent entry path must receive the same step scope."""
    llm_service, generate = _llm(_success_completion("fallback answer"))
    step = _scoped_step(
        service="slack",
        fallback_service="main_agent",
        parameters={"agent_id": "agent-1"},
    )

    async def _primary_fails(action, params, connection_id=None, **kwargs):
        raise RuntimeError("primary down")

    with patch.object(engine, "_execute_slack_action", new=_primary_fails), \
         patch("core.database.get_db_session",
               return_value=_db_session(_agent())), \
         patch("core.llm_service.get_llm_service",
               return_value=llm_service):
        result = await engine._execute_step(step, step["parameters"])

    assert result["status"] == "success"
    assert result["fallback_used"] is True
    assert result["execution_method"] == "fallback_service"
    assert result["result"]["status"] == "success"
    assert result["result"]["result"]["success"] is True
    generate.assert_awaited_once()
    assert generate.call_args.kwargs["workspace_id"] == "ws-1"
    assert generate.call_args.kwargs["tenant_id"] == "tenant-1"


@pytest.mark.asyncio
async def test_direct_executor_without_scope_is_refused(engine):
    """The low-level executor must not invent a default scope."""
    result = await engine._execute_agent_with_mcp({
        "agent_id": "agent-1",
        "action": "analyze",
    })

    assert result["success"] is False
    assert result["failure_reason"] == "scope_unavailable"


@pytest.mark.asyncio
async def test_success_is_text_only_but_preserves_connection_metadata(engine):
    """The text-only path advertises and executes no tools even when a caller
    supplies tool definitions; connection metadata stays attached to the
    legitimate response without claiming any tool ran."""
    llm_service, generate = _llm(_success_completion("tool answer"))
    connection_metadata = {
        "srv-1": {
            "connected_at": "now",
            "tools": [{"name": "lookup"}],
        }
    }

    with patch("core.database.get_db_session",
               return_value=_db_session(_agent())), \
         patch("core.llm_service.get_llm_service",
               return_value=llm_service):
        result = await engine._execute_agent_with_mcp({
            "agent_id": "agent-1",
            "workspace_id": "ws-1",
            "tenant_id": "tenant-1",
            "action": "analyze",
            "input_data": {"q": 1},
            "available_tools": [{
                "server_id": "srv-1",
                "tool": {
                    "name": "lookup",
                    "description": "Look something up",
                    "input_schema": {"type": "object"},
                },
            }],
            "mcp_connections": connection_metadata,
        })

    assert result["success"] is True
    assert result["content"] == "tool answer"
    assert result["agent_response"] == "tool answer"
    assert result["tool_definitions"] == []
    assert result["tools_available"] == 0
    assert result["tool_calls"] == []
    assert result["mcp_connections"] == 1
    assert result["mcp_connection_metadata"] == connection_metadata
    # Tool definitions are not admitted into the text-only prompt.
    prompt = generate.call_args.kwargs["messages"][0]["content"]
    assert "analyze" in prompt
    assert "lookup" not in prompt
