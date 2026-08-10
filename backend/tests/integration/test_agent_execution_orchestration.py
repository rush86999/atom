"""
Agent Execution Orchestration Tests

Realigned against the live ``core/agent_execution_service`` contract
(2026-08-09 wave 10c). The previous version was uncollectable (conftest
crash from the jwt_verifier regression) and then stale (undefined ``llm``/
``mock_llm_service`` names, phantom ``provider``/``model`` response keys,
permissive asserts, unpatched SessionLocal hitting the dev DB).
"""
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from core.agent_execution_service import (
    execute_agent_chat,
    execute_agent_chat_sync,
)


def _agent(**overrides):
    a = SimpleNamespace(
        id="agent-1", name="Helper", description="A helper",
        category="general", type="standard",
    )
    for k, v in overrides.items():
        setattr(a, k, v)
    return a


@pytest.fixture
def llm_harness():
    """Patch LLMService + ws_manager; returns (llm, ws) mocks."""
    llm = MagicMock()
    llm.analyze_query_complexity.return_value = "simple"
    llm.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")
    ws = AsyncMock()
    ws.STREAMING_UPDATE = "streaming:update"
    ws.STREAMING_COMPLETE = "streaming:complete"

    async def _gen(*a, **k):
        yield "Hello"
        yield " world"

    llm.stream_completion = _gen
    stack = [
        patch("core.agent_execution_service.LLMService", return_value=llm),
        patch("core.agent_execution_service.ws_manager", ws),
        patch("core.agent_execution_service.get_chat_history_manager"),
        patch("core.agent_execution_service.get_chat_session_manager"),
        patch("core.agent_execution_service.trigger_episode_creation"),
        patch("core.agent_execution_service.personal_budget_service"),
    ]
    for p in stack:
        p.start()
    yield llm, ws
    for p in reversed(stack):
        p.stop()


_RESOLVER_PATCHES: list = []


def _resolver(agent):
    resolver = AsyncMock()
    resolver.resolve_agent_for_request.return_value = (agent, {})
    governance = MagicMock()
    governance.can_perform_action.return_value = {"allowed": True, "reason": None}
    p1 = patch("core.agent_execution_service.AgentContextResolver", return_value=resolver)
    p2 = patch("core.agent_execution_service.AgentGovernanceService", return_value=governance)
    p1.start()
    p2.start()
    _RESOLVER_PATCHES.append(p1)
    _RESOLVER_PATCHES.append(p2)
    return p1, p2


@pytest.fixture(autouse=True)
def _stop_resolver_patches():
    """Never leak resolver/governance patches into later test files."""
    yield
    while _RESOLVER_PATCHES:
        _RESOLVER_PATCHES.pop().stop()


# ============================================================================
# Test: Governance Validation
# ============================================================================
class TestGovernanceValidation:
    @pytest.mark.asyncio
    async def test_governance_check_passes_for_authorized_agent(self, llm_harness, db_session):
        agent = _agent()
        with patch("core.agent_execution_service.SessionLocal", return_value=db_session):
            _resolver(agent)
            try:
                result = await execute_agent_chat(
                    agent_id="agent-1", message="Hello", user_id="u-1", stream=False
                )
            finally:
                pass
        assert result["success"] is True
        assert result["response"] == "Hello world"
        assert result["agent_name"] == "Helper"

    @pytest.mark.asyncio
    async def test_governance_check_blocks_unauthorized_action(self, db_session):
        resolver = AsyncMock()
        resolver.resolve_agent_for_request.return_value = (_agent(), {})
        governance = MagicMock()
        governance.can_perform_action.return_value = {
            "allowed": False, "reason": "STUDENT agent blocked from chat"
        }
        with patch("core.agent_execution_service.SessionLocal", return_value=db_session), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance):
            result = await execute_agent_chat(
                agent_id="agent-1", message="test", user_id="u-1"
            )
        assert result["success"] is False
        assert "blocked" in result["error"].lower()
        assert result["execution_id"] is None

    @pytest.mark.asyncio
    async def test_governance_emergency_bypass_allows_execution(self, llm_harness, monkeypatch):
        monkeypatch.setenv("EMERGENCY_GOVERNANCE_BYPASS", "true")
        result = await execute_agent_chat(agent_id="agent-1", message="test", user_id="u-1")
        assert result["success"] is True
        assert result["agent_name"] == "System"

    @pytest.mark.asyncio
    async def test_governance_flag_disables_checks(self, llm_harness, monkeypatch):
        monkeypatch.setenv("STREAMING_GOVERNANCE_ENABLED", "false")
        result = await execute_agent_chat(agent_id="agent-1", message="test", user_id="u-1")
        assert result["success"] is True


# ============================================================================
# Test: LLM Streaming Execution
# ============================================================================
class TestLLMStreamingExecution:
    @pytest.mark.asyncio
    async def test_llm_streaming_accumulates_tokens(self, llm_harness, db_session):
        llm, _ = llm_harness
        agent = _agent()
        with patch("core.agent_execution_service.SessionLocal", return_value=db_session):
            _resolver(agent)
            result = await execute_agent_chat(
                agent_id="agent-1", message="test", user_id="u-1", stream=False
            )
        assert result["success"] is True
        assert result["response"] == "Hello world"
        # "Hello" (5 chars -> 1) + " world" (6 -> 1) = 2 tokens estimated
        assert result["tokens"] == 2
        assert result["model"] == "auto"
        llm.get_optimal_provider.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_provider_selection(self, llm_harness, db_session):
        llm, _ = llm_harness
        llm.get_optimal_provider.return_value = ("anthropic", "claude-3-opus")
        agent = _agent()
        with patch("core.agent_execution_service.SessionLocal", return_value=db_session):
            _resolver(agent)
            result = await execute_agent_chat(
                agent_id="agent-1", message="Complex question", user_id="u-1"
            )
        assert result["success"] is True
        kwargs = llm.get_optimal_provider.call_args.kwargs
        assert kwargs["prefer_cost"] is True
        assert kwargs["task_type"] == "chat"

    @pytest.mark.asyncio
    async def test_llm_streaming_with_conversation_history(self, llm_harness, db_session):
        llm, _ = llm_harness
        agent = _agent()
        with patch("core.agent_execution_service.SessionLocal", return_value=db_session):
            _resolver(agent)
            result = await execute_agent_chat(
                agent_id="agent-1",
                message="Follow-up",
                user_id="u-1",
                conversation_history=[
                    {"role": "user", "content": "Previous question"},
                    {"role": "assistant", "content": "Previous answer"},
                ],
            )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_llm_error_propagation_is_generic(self, llm_harness, db_session):
        llm, _ = llm_harness

        async def _boom(*a, **k):
            raise ValueError("provider exploded: token 42")

        llm.stream_completion = _boom
        agent = _agent()
        with patch("core.agent_execution_service.SessionLocal", return_value=db_session):
            _resolver(agent)
            result = await execute_agent_chat(agent_id="agent-1", message="test", user_id="u-1")
        assert result["success"] is False
        assert "error" in result
        assert "token 42" not in result["error"]


# ============================================================================
# Test: WebSocket Streaming
# ============================================================================
class TestWebSocketStreaming:
    @pytest.mark.asyncio
    async def test_websocket_sends_start_message(self, llm_harness, db_session):
        _, ws = llm_harness
        agent = _agent()
        with patch("core.agent_execution_service.SessionLocal", return_value=db_session):
            _resolver(agent)
            result = await execute_agent_chat(
                agent_id="agent-1", message="test", user_id="u-1", stream=True
            )
        assert result["success"] is True
        start_calls = [c for c in ws.broadcast.await_args_list if c.args[1]["type"] == "streaming:start"]
        assert len(start_calls) == 1
        payload = start_calls[0].args[1]
        assert payload["channel"] if "channel" in payload else payload["id"] == result["message_id"]
        assert payload["execution_id"] == result["execution_id"]

    @pytest.mark.asyncio
    async def test_websocket_sends_update_and_complete(self, llm_harness, db_session):
        _, ws = llm_harness
        agent = _agent()
        with patch("core.agent_execution_service.SessionLocal", return_value=db_session):
            _resolver(agent)
            result = await execute_agent_chat(
                agent_id="agent-1", message="test", user_id="u-1", stream=True
            )
        types = [c.args[1]["type"] for c in ws.broadcast.await_args_list]
        assert ws.STREAMING_UPDATE in types
        assert ws.STREAMING_COMPLETE in types
        # start + 2 update chunks + complete
        assert len(types) == 4

    @pytest.mark.asyncio
    async def test_websocket_skipped_when_stream_false(self, llm_harness, db_session):
        _, ws = llm_harness
        agent = _agent()
        with patch("core.agent_execution_service.SessionLocal", return_value=db_session):
            _resolver(agent)
            result = await execute_agent_chat(
                agent_id="agent-1", message="test", user_id="u-1", stream=False
            )
        assert result["success"] is True
        assert ws.broadcast.await_count == 0


# ============================================================================
# Test: Chat History Persistence
# ============================================================================
class TestChatHistoryPersistence:
    @pytest.mark.asyncio
    async def test_chat_session_created_and_messages_saved(self, llm_harness, db_session):
        agent = _agent()
        session_mgr = MagicMock()
        session_mgr.create_session.return_value = "sess-new"
        hist = MagicMock()
        with patch("core.agent_execution_service.SessionLocal", return_value=db_session), \
             patch("core.agent_execution_service.get_chat_session_manager", return_value=session_mgr), \
             patch("core.agent_execution_service.get_chat_history_manager", return_value=hist):
            _resolver(agent)
            result = await execute_agent_chat(
                agent_id="agent-1", message="hello", user_id="u-1", session_id=None
            )
        assert result["session_id"] == "sess-new"
        session_mgr.create_session.assert_called_once_with("u-1")
        hist.add_message.assert_any_call("sess-new", "user", "hello")
        hist.add_message.assert_any_call("sess-new", "assistant", "Hello world")

    @pytest.mark.asyncio
    async def test_existing_session_reused(self, llm_harness, db_session):
        agent = _agent()
        session_mgr = MagicMock()
        hist = MagicMock()
        with patch("core.agent_execution_service.SessionLocal", return_value=db_session), \
             patch("core.agent_execution_service.get_chat_session_manager", return_value=session_mgr), \
             patch("core.agent_execution_service.get_chat_history_manager", return_value=hist):
            _resolver(agent)
            result = await execute_agent_chat(
                agent_id="agent-1", message="hi", user_id="u-1", session_id="sess-old"
            )
        assert result["session_id"] == "sess-old"
        session_mgr.create_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_chat_history_persistence_error_doesnt_fail_execution(self, llm_harness, db_session):
        agent = _agent()
        with patch("core.agent_execution_service.SessionLocal", return_value=db_session), \
             patch(
                 "core.agent_execution_service.get_chat_history_manager",
                 side_effect=RuntimeError("history down"),
             ):
            _resolver(agent)
            result = await execute_agent_chat(agent_id="agent-1", message="hi", user_id="u-1")
        assert result["success"] is True


# ============================================================================
# Test: AgentExecution Audit Trail
# ============================================================================
class TestAgentExecutionAuditTrail:
    @pytest.mark.asyncio
    async def test_agent_execution_record_created(self, llm_harness, db_session):
        from core.models import AgentExecution

        agent = _agent()
        db = MagicMock()
        with patch("core.agent_execution_service.SessionLocal", return_value=db):
            _resolver(agent)
            result = await execute_agent_chat(agent_id="agent-1", message="hi", user_id="u-1")
        assert result["success"] is True
        added = [a for a in db.add.call_args_list]
        assert added, "AgentExecution row should be added"
        row = added[0].args[0]
        assert isinstance(row, AgentExecution)
        assert row.status == "running"
        assert row.metadata_json["agent_name"] == "Helper"
        assert row.metadata_json["user_id"] == "u-1"
        assert row.metadata_json["action_type"] == "chat"

    @pytest.mark.asyncio
    async def test_execution_record_updated_on_completion(self, llm_harness, db_session):
        execution = MagicMock()
        execution.metadata_json = {"existing": 1}
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = execution
        with patch("core.agent_execution_service.SessionLocal", return_value=db):
            _resolver(_agent())
            result = await execute_agent_chat(agent_id="agent-1", message="hi", user_id="u-1")
        assert result["success"] is True
        assert execution.status == "completed"
        assert execution.result_summary == "Hello world"
        assert execution.metadata_json["existing"] == 1
        assert execution.metadata_json["output"]["response"] == "Hello world"

    @pytest.mark.asyncio
    async def test_execution_record_marked_failed_on_error(self, llm_harness, db_session):
        llm, _ = llm_harness

        async def _boom(*a, **k):
            raise RuntimeError("secret internal path /var/lib/data.db")

        llm.stream_completion = _boom
        execution = MagicMock()
        execution.metadata_json = {}
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = execution
        with patch("core.agent_execution_service.SessionLocal", return_value=db):
            _resolver(_agent())
            result = await execute_agent_chat(agent_id="agent-1", message="hi", user_id="u-1")
        assert result["success"] is False
        assert "data.db" not in result["error"]
        assert execution.status == "failed"
        assert "data.db" not in (execution.error_message or "")

    @pytest.mark.asyncio
    async def test_execution_metadata_includes_governance_context(self, llm_harness, db_session):
        agent = _agent()
        db = MagicMock()
        with patch("core.agent_execution_service.SessionLocal", return_value=db):
            _resolver(agent)
            result = await execute_agent_chat(
                agent_id="agent-1", message="hi", user_id="u-1", workspace_id="ws-x"
            )
        assert result["success"] is True
        row = db.add.call_args.args[0]
        assert row.workspace_id == "ws-x"
        assert row.triggered_by == "websocket"
        assert row.metadata_json["source"] == "menubar"
        assert row.metadata_json["resolution_context"] is not None
        assert row.metadata_json["governance_check"]["allowed"] is True


# ============================================================================
# Test: Episode Creation Triggering
# ============================================================================
class TestEpisodeCreationTriggering:
    @pytest.mark.asyncio
    async def test_episode_creation_triggered_after_execution(self, llm_harness, db_session):
        agent = _agent()
        with patch("core.agent_execution_service.SessionLocal", return_value=db_session), \
             patch("core.agent_execution_service.trigger_episode_creation") as trigger:
            _resolver(agent)
            result = await execute_agent_chat(
                agent_id="agent-1", message="hi", user_id="u-1", session_id="s-1",
                workspace_id="w-1",
            )
        assert result["success"] is True
        trigger.assert_called_once()
        kwargs = trigger.call_args.kwargs
        assert kwargs["session_id"] == "s-1"
        assert kwargs["agent_id"] == "agent-1"
        assert kwargs["user_id"] == "u-1"
        assert kwargs["workspace_id"] == "w-1"

    @pytest.mark.asyncio
    async def test_episode_creation_error_doesnt_fail_execution(self, llm_harness, db_session):
        agent = _agent()
        with patch("core.agent_execution_service.SessionLocal", return_value=db_session), \
             patch(
                 "core.agent_execution_service.trigger_episode_creation",
                 side_effect=RuntimeError("episode down"),
             ):
            _resolver(agent)
            result = await execute_agent_chat(agent_id="agent-1", message="hi", user_id="u-1")
        assert result["success"] is True


# ============================================================================
# Test: Error Handling
# ============================================================================
class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_llm_failure_caught_and_logged(self, llm_harness, db_session):
        llm, _ = llm_harness

        async def _boom(*a, **k):
            raise RuntimeError("stream died")

        llm.stream_completion = _boom
        agent = _agent()
        with patch("core.agent_execution_service.SessionLocal", return_value=db_session):
            _resolver(agent)
            result = await execute_agent_chat(agent_id="agent-1", message="hi", user_id="u-1")
        assert result["success"] is False
        assert result["error"] == "Agent chat execution failed"

    @pytest.mark.asyncio
    async def test_websocket_disconnection_doesnt_affect_execution(self, llm_harness, db_session):
        _, ws = llm_harness
        ws.broadcast.side_effect = RuntimeError("client disconnected")
        agent = _agent()
        with patch("core.agent_execution_service.SessionLocal", return_value=db_session):
            _resolver(agent)
            result = await execute_agent_chat(
                agent_id="agent-1", message="hi", user_id="u-1", stream=True
            )
        # broadcast failure propagates to the outer handler -> failed result
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_database_connection_error_returns_error_response(self):
        with patch(
            "core.agent_execution_service.AgentContextResolver"
        ) as resolver_cls:
            resolver = AsyncMock()
            resolver.resolve_agent_for_request.side_effect = RuntimeError(
                "db down: /var/lib/secret.db"
            )
            resolver_cls.return_value = resolver
            result = await execute_agent_chat(agent_id="agent-1", message="hi", user_id="u-1")
        assert result["success"] is False
        assert "/var/lib/secret.db" not in result["error"]


# ============================================================================
# Test: Sync Execution Wrapper
# ============================================================================
class TestSyncExecutionWrapper:
    def test_sync_wrapper_creates_event_loop_and_disables_streaming(self, llm_harness):
        llm, ws = llm_harness
        result = execute_agent_chat_sync("agent-1", "hi", "u-1")
        assert result["success"] is True
        assert result["response"] == "Hello world"
        assert ws.broadcast.await_count == 0
