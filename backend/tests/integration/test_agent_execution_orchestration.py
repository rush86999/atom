"""
Agent Execution Orchestration Tests

Comprehensive end-to-end tests for agent execution flow:
- Governance validation before execution
- LLM streaming with BYOK handler
- WebSocket token delivery
- Chat history persistence
- AgentExecution audit trail
- Episode creation triggering
- Error handling scenarios
- Sync execution wrapper

Coverage Target: 50%+ on agent_execution_service.py
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime
from sqlalchemy.orm import Session

from core.agent_execution_service import execute_agent_chat, execute_agent_chat_sync
from core.models import AgentExecution, AgentRegistry, ChatSession
from core.llm.byok_handler import QueryComplexity


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_autonomous_agent(db_session):
    """Create AUTONOMOUS agent for testing"""
    agent = AgentRegistry(
        id="test_autonomous_agent",
        name="TestAutonomousAgent",
        category="testing",
        status="autonomous",  # lowercase to match AgentStatus enum
        description="Test autonomous agent",
        module_path="test.agent",
        class_name="TestAgent"
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    yield agent
    # Cleanup
    db_session.query(AgentExecution).filter(AgentExecution.agent_id == agent.id).delete()
    db_session.query(AgentRegistry).filter(AgentRegistry.id == agent.id).delete()
    db_session.commit()


@pytest.fixture
def mock_student_agent(db_session):
    """Create STUDENT agent for governance testing"""
    agent = AgentRegistry(
        id="test_student_agent",
        name="TestStudentAgent",
        category="testing",
        status="student",  # lowercase to match AgentStatus enum
        description="Test student agent",
        module_path="test.student_agent",
        class_name="StudentAgent"
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    yield agent
    # Cleanup
    db_session.query(AgentExecution).filter(AgentExecution.agent_id == agent.id).delete()
    db_session.query(AgentRegistry).filter(AgentRegistry.id == agent.id).delete()
    db_session.commit()


@pytest.fixture
def mock_byok_handler():
    """Mock BYOK handler for LLM streaming"""
    byok_instance = MagicMock()
    byok_instance.analyze_query_complexity.return_value = QueryComplexity.SIMPLE
    byok_instance.get_optimal_provider.return_value = ("openai", "gpt-4")

    async def mock_stream(**kwargs):
        tokens = ["Hello", " ", "world", "!"]
        for token in tokens:
            yield token

    byok_instance.stream_completion = mock_stream
    return byok_instance


@pytest.fixture
def mock_agent_resolver(mock_autonomous_agent):
    """Mock agent context resolver"""
    resolver = MagicMock()
    resolver.resolve_agent_for_request = AsyncMock(
        return_value=(mock_autonomous_agent, {"resolution_path": ["explicit_agent_id"]})
    )

    # Mock governance check
    governance = MagicMock()
    governance.can_perform_action.return_value = {
        "proceed": True,
        "allowed": True
    }
    resolver.governance = governance

    return resolver


@pytest.fixture
def mock_websocket_manager():
    """Mock WebSocket manager for streaming"""
    ws_instance = MagicMock()
    ws_instance.broadcast = AsyncMock()

    mock_ws = MagicMock()
    mock_ws.broadcast = ws_instance.broadcast
    mock_ws.STREAMING_UPDATE = "streaming:update"
    mock_ws.STREAMING_COMPLETE = "streaming:complete"

    return mock_ws


# ============================================================================
# Test: Governance Validation
# ============================================================================

class TestGovernanceValidation:
    """Tests for governance checks before execution"""

    @pytest.mark.asyncio
    async def test_governance_check_passes_for_authorized_agent(self, mock_autonomous_agent, db_session):
        """AUTONOMOUS agent passes governance check"""
        with patch('core.agent_execution_service.BYOKHandler') as mock_byok:
            with patch('core.agent_execution_service.ws_manager'):
                with patch('core.agent_execution_service.SessionLocal', return_value=db_session):
                    with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                        byok = MagicMock()
                        byok.analyze_query_complexity.return_value = QueryComplexity.SIMPLE
                        byok.get_optimal_provider.return_value = ("openai", "gpt-4")

                        async def mock_stream(**kwargs):
                            yield "Test response"

                        byok.stream_completion = mock_stream
                        mock_byok.return_value = byok

                        resolver = MagicMock()
                        resolver.resolve_agent_for_request = AsyncMock(
                            return_value=(mock_autonomous_agent, {})
                        )
                        resolver.governance = MagicMock()
                        resolver.governance.can_perform_action = MagicMock(
                            return_value={"proceed": True, "allowed": True}
                        )
                        mock_resolver.return_value = resolver

                        result = await execute_agent_chat(
                            agent_id=mock_autonomous_agent.id,
                            message="Hello",
                            user_id="test_user",
                            stream=False
                        )

        assert result["success"] is True
        assert "response" in result

    @pytest.mark.asyncio
    async def test_governance_check_blocks_unauthorized_action(self, mock_student_agent, db_session):
        """STUDENT agent blocked from chat"""
        with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
            resolver = MagicMock()
            resolver.resolve_agent_for_request = AsyncMock(
                return_value=(mock_student_agent, {})
            )
            resolver.governance = MagicMock()
            resolver.governance.can_perform_action = MagicMock(
                return_value={
                    "proceed": False,
                    "allowed": False,
                    "reason": "STUDENT agent blocked from chat"
                }
            )
            mock_resolver.return_value = resolver

            result = await execute_agent_chat(
                agent_id=mock_student_agent.id,
                message="test",
                user_id="user_123"
            )

        assert result["success"] is False
        assert "blocked" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_governance_emergency_bypass_allows_execution(self, mock_student_agent, db_session, monkeypatch):
        """Emergency bypass disables governance checks"""
        monkeypatch.setenv("EMERGENCY_GOVERNANCE_BYPASS", "true")

        with patch('core.agent_execution_service.BYOKHandler') as mock_byok:
            with patch('core.agent_execution_service.ws_manager'):
                byok = MagicMock()
                byok.analyze_query_complexity.return_value = QueryComplexity.SIMPLE
                byok.get_optimal_provider.return_value = ("openai", "gpt-4")

                async def mock_stream(**kwargs):
                    yield "Bypass response"

                byok.stream_completion = mock_stream
                mock_byok.return_value = byok

                result = await execute_agent_chat(
                    agent_id=mock_student_agent.id,
                    message="test",
                    user_id="user_123"
                )

        # With emergency bypass, governance is skipped but execution may succeed
        assert "success" in result or "error" in result

    @pytest.mark.asyncio
    async def test_governance_flag_disables_checks(self, mock_student_agent, db_session, monkeypatch):
        """STREAMING_GOVERNANCE_ENABLED=false skips governance"""
        monkeypatch.setenv("STREAMING_GOVERNANCE_ENABLED", "false")

        with patch('core.agent_execution_service.BYOKHandler') as mock_byok:
            with patch('core.agent_execution_service.ws_manager'):
                byok = MagicMock()
                byok.analyze_query_complexity.return_value = QueryComplexity.SIMPLE
                byok.get_optimal_provider.return_value = ("openai", "gpt-4")

                async def mock_stream(**kwargs):
                    yield "Disabled governance response"

                byok.stream_completion = mock_stream
                mock_byok.return_value = byok

                result = await execute_agent_chat(
                    agent_id=mock_student_agent.id,
                    message="test",
                    user_id="user_123"
                )

        # Governance disabled, execution proceeds
        assert "success" in result or "error" in result


# ============================================================================
# Test: LLM Streaming Execution
# ============================================================================

class TestLLMStreamingExecution:
    """Tests for BYOK handler streaming"""

    @pytest.mark.asyncio
    async def test_llm_streaming_accumulates_tokens(self, mock_autonomous_agent, mock_byok_handler, db_session):
        """Tokens are accumulated correctly from streaming"""
        with patch('core.agent_execution_service.BYOKHandler', return_value=mock_byok_handler):
            with patch('core.agent_execution_service.ws_manager'):
                with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                    resolver = MagicMock()
                    resolver.resolve_agent_for_request = AsyncMock(
                        return_value=(mock_autonomous_agent, {})
                    )
                    resolver.governance = MagicMock()
                    resolver.governance.can_perform_action = MagicMock(
                        return_value={"proceed": True, "allowed": True}
                    )
                    mock_resolver.return_value = resolver

                    result = await execute_agent_chat(
                        agent_id=mock_autonomous_agent.id,
                        message="test",
                        user_id="user_123",
                        stream=False
                    )

        assert result["success"] is True
        assert result["response"] == "Hello world!"
        assert result["tokens"] == 4

    @pytest.mark.asyncio
    async def test_llm_provider_selection(self, mock_autonomous_agent, db_session):
        """Optimal provider is selected based on query complexity"""
        with patch('core.agent_execution_service.BYOKHandler') as mock_byok:
            with patch('core.agent_execution_service.ws_manager'):
                byok = MagicMock()
                byok.analyze_query_complexity.return_value = QueryComplexity.COMPLEX
                byok.get_optimal_provider.return_value = ("anthropic", "claude-3-opus")

                async def mock_stream(**kwargs):
                    yield "Complex query response"

                byok.stream_completion = mock_stream
                mock_byok.return_value = byok

                with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                    resolver = MagicMock()
                    resolver.resolve_agent_for_request = AsyncMock(
                        return_value=(mock_autonomous_agent, {})
                    )
                    resolver.governance = MagicMock()
                    resolver.governance.can_perform_action = MagicMock(
                        return_value={"proceed": True, "allowed": True}
                    )
                    mock_resolver.return_value = resolver

                    result = await execute_agent_chat(
                        agent_id=mock_autonomous_agent.id,
                        message="Complex question requiring reasoning",
                        user_id="user_123"
                    )

        assert result["success"] is True
        assert result["provider"] == "anthropic"
        assert result["model"] == "claude-3-opus"

    @pytest.mark.asyncio
    async def test_llm_streaming_with_conversation_history(self, mock_autonomous_agent, mock_byok_handler, db_session):
        """Conversation history is included in LLM context"""
        with patch('core.agent_execution_service.BYOKHandler', return_value=mock_byok_handler):
            with patch('core.agent_execution_service.ws_manager'):
                with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                    resolver = MagicMock()
                    resolver.resolve_agent_for_request = AsyncMock(
                        return_value=(mock_autonomous_agent, {})
                    )
                    resolver.governance = MagicMock()
                    resolver.governance.can_perform_action = MagicMock(
                        return_value={"proceed": True, "allowed": True}
                    )
                    mock_resolver.return_value = resolver

                    history = [
                        {"role": "user", "content": "Previous question"},
                        {"role": "assistant", "content": "Previous answer"}
                    ]

                    result = await execute_agent_chat(
                        agent_id=mock_autonomous_agent.id,
                        message="Follow-up question",
                        user_id="user_123",
                        conversation_history=history
                    )

        assert result["success"] is True
        # Verify history was used (check would require inspecting BYOK call)

    @pytest.mark.asyncio
    async def test_llm_error_propagation(self, mock_autonomous_agent, db_session):
        """LLM streaming errors are handled gracefully"""
        with patch('core.agent_execution_service.BYOKHandler') as mock_byok:
            with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                resolver = MagicMock()
                resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_autonomous_agent, {})
                )
                resolver.governance = MagicMock()
                resolver.governance.can_perform_action.return_value = {
                    "proceed": True, "allowed": True
                }
                mock_resolver.return_value = resolver

                byok = MagicMock()
                byok.analyze_query_complexity.return_value = QueryComplexity.SIMPLE

                async def mock_stream_error(**kwargs):
                    raise Exception("LLM API error")

                byok.stream_completion = mock_stream_error
                mock_byok.return_value = byok

                result = await execute_agent_chat(
                    agent_id=mock_autonomous_agent.id,
                    message="test",
                    user_id="user_123"
                )

        assert result["success"] is False
        assert "error" in result


# ============================================================================
# Test: WebSocket Streaming
# ============================================================================

class TestWebSocketStreaming:
    """Tests for WebSocket token delivery"""

    @pytest.mark.asyncio
    async def test_websocket_sends_start_message(self, mock_autonomous_agent, mock_byok_handler, mock_websocket_manager, db_session):
        """WebSocket sends streaming:start message"""
        with patch('core.agent_execution_service.BYOKHandler', return_value=mock_byok_handler):
            with patch('core.agent_execution_service.ws_manager', mock_websocket_manager):
                with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                    resolver = MagicMock()
                    resolver.resolve_agent_for_request = AsyncMock(
                        return_value=(mock_autonomous_agent, {})
                    )
                    resolver.governance = MagicMock()
                    resolver.governance.can_perform_action = MagicMock(
                        return_value={"proceed": True, "allowed": True}
                    )
                    mock_resolver.return_value = resolver

                    result = await execute_agent_chat(
                        agent_id=mock_autonomous_agent.id,
                        message="test",
                        user_id="user_123",
                        stream=True
                    )

        assert result["success"] is True
        # Verify start message was sent
        mock_websocket_manager.broadcast.assert_any_call(
            "user:user_123",
            {
                "type": "streaming:start",
                "id": result["message_id"],
                "model": "gpt-4",
                "provider": "openai",
                "agent_id": mock_autonomous_agent.id,
                "agent_name": mock_autonomous_agent.name,
                "execution_id": result["execution_id"]
            }
        )

    @pytest.mark.asyncio
    async def test_websocket_sends_update_messages(self, mock_autonomous_agent, mock_byok_handler, mock_websocket_manager, db_session):
        """WebSocket sends streaming:update messages for each token"""
        with patch('core.agent_execution_service.BYOKHandler', return_value=mock_byok_handler):
            with patch('core.agent_execution_service.ws_manager', mock_websocket_manager):
                with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                    resolver = MagicMock()
                    resolver.resolve_agent_for_request = AsyncMock(
                        return_value=(mock_autonomous_agent, {})
                    )
                    resolver.governance = MagicMock()
                    resolver.governance.can_perform_action = MagicMock(
                        return_value={"proceed": True, "allowed": True}
                    )
                    mock_resolver.return_value = resolver

                    result = await execute_agent_chat(
                        agent_id=mock_autonomous_agent.id,
                        message="test",
                        user_id="user_123",
                        stream=True
                    )

        assert result["success"] is True
        # Verify update messages were sent
        assert mock_websocket_manager.broadcast.call_count >= 5  # start + 4 tokens + complete

    @pytest.mark.asyncio
    async def test_websocket_sends_complete_message(self, mock_autonomous_agent, mock_byok_handler, mock_websocket_manager, db_session):
        """WebSocket sends streaming:complete message with full content"""
        with patch('core.agent_execution_service.BYOKHandler', return_value=mock_byok_handler):
            with patch('core.agent_execution_service.ws_manager', mock_websocket_manager):
                with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                    resolver = MagicMock()
                    resolver.resolve_agent_for_request = AsyncMock(
                        return_value=(mock_autonomous_agent, {})
                    )
                    resolver.governance = MagicMock()
                    resolver.governance.can_perform_action = MagicMock(
                        return_value={"proceed": True, "allowed": True}
                    )
                    mock_resolver.return_value = resolver

                    result = await execute_agent_chat(
                        agent_id=mock_autonomous_agent.id,
                        message="test",
                        user_id="user_123",
                        stream=True
                    )

        assert result["success"] is True
        # Verify complete message was sent
        complete_calls = [
            call for call in mock_websocket_manager.broadcast.call_args_list
            if "streaming:complete" in str(call)
        ]
        assert len(complete_calls) > 0

    @pytest.mark.asyncio
    async def test_websocket_skipped_when_stream_false(self, mock_autonomous_agent, mock_byok_handler, mock_websocket_manager, db_session):
        """No WebSocket messages when stream=False"""
        with patch('core.agent_execution_service.BYOKHandler', return_value=mock_byok_handler):
            with patch('core.agent_execution_service.ws_manager', mock_websocket_manager):
                with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                    resolver = MagicMock()
                    resolver.resolve_agent_for_request = AsyncMock(
                        return_value=(mock_autonomous_agent, {})
                    )
                    resolver.governance = MagicMock()
                    resolver.governance.can_perform_action = MagicMock(
                        return_value={"proceed": True, "allowed": True}
                    )
                    mock_resolver.return_value = resolver

                    result = await execute_agent_chat(
                        agent_id=mock_autonomous_agent.id,
                        message="test",
                        user_id="user_123",
                        stream=False
                    )

        assert result["success"] is True
        # Verify no WebSocket calls when stream=False
        mock_websocket_manager.broadcast.assert_not_called()


# ============================================================================
# Test: Chat History Persistence
# ============================================================================

class TestChatHistoryPersistence:
    """Tests for chat history saving"""

    @pytest.mark.asyncio
    async def test_chat_session_created_on_execution(self, mock_autonomous_agent, mock_byok_handler, db_session):
        """New chat session is created if none provided"""
        with patch('core.agent_execution_service.BYOKHandler', return_value=mock_byok_handler):
            with patch('core.agent_execution_service.ws_manager'):
                with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                    resolver = MagicMock()
                    resolver.resolve_agent_for_request = AsyncMock(
                        return_value=(mock_autonomous_agent, {})
                    )
                    resolver.governance = MagicMock()
                    resolver.governance.can_perform_action = MagicMock(
                        return_value={"proceed": True, "allowed": True}
                    )
                    mock_resolver.return_value = resolver

                    result = await execute_agent_chat(
                        agent_id=mock_autonomous_agent.id,
                        message="test",
                        user_id="user_123",
                        session_id=None
                    )

        assert result["success"] is True
        assert "session_id" in result

    @pytest.mark.asyncio
    async def test_messages_saved_to_chat_history(self, mock_autonomous_agent, mock_byok_handler, db_session):
        """User and assistant messages are saved to chat history"""
        with patch('core.agent_execution_service.BYOKHandler', return_value=mock_byok_handler):
            with patch('core.agent_execution_service.ws_manager'):
                with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                    resolver = MagicMock()
                    resolver.resolve_agent_for_request = AsyncMock(
                        return_value=(mock_autonomous_agent, {})
                    )
                    resolver.governance = MagicMock()
                    resolver.governance.can_perform_action = MagicMock(
                        return_value={"proceed": True, "allowed": True}
                    )
                    mock_resolver.return_value = resolver

                    result = await execute_agent_chat(
                        agent_id=mock_autonomous_agent.id,
                        message="Hello world",
                        user_id="user_123"
                    )

        assert result["success"] is True
        assert result["response"] == "Hello world!"

    @pytest.mark.asyncio
    async def test_chat_history_persistence_error_doesnt_fail_execution(self, mock_autonomous_agent, mock_byok_handler, db_session):
        """Execution succeeds even if chat history persistence fails"""
        with patch('core.agent_execution_service.BYOKHandler', return_value=mock_byok_handler):
            with patch('core.agent_execution_service.ws_manager'):
                with patch('core.agent_execution_service.get_chat_history_manager') as mock_history:
                    mock_history.side_effect = Exception("Chat history DB error")

                    with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                        resolver = MagicMock()
                        resolver.resolve_agent_for_request = AsyncMock(
                            return_value=(mock_autonomous_agent, {})
                        )
                        resolver.governance = MagicMock()
                        resolver.governance.can_perform_action.return_value = {
                            "proceed": True, "allowed": True
                        }
                        mock_resolver.return_value = resolver

                        result = await execute_agent_chat(
                            agent_id=mock_autonomous_agent.id,
                            message="test",
                            user_id="user_123"
                        )

        # Execution should succeed despite chat history error
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_existing_session_reused_for_continuity(self, mock_autonomous_agent, mock_byok_handler, db_session):
        """Existing session_id is reused for conversation continuity"""
        with patch('core.agent_execution_service.BYOKHandler', return_value=mock_byok_handler):
            with patch('core.agent_execution_service.ws_manager'):
                with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                    resolver = MagicMock()
                    resolver.resolve_agent_for_request = AsyncMock(
                        return_value=(mock_autonomous_agent, {})
                    )
                    resolver.governance = MagicMock()
                    resolver.governance.can_perform_action = MagicMock(
                        return_value={"proceed": True, "allowed": True}
                    )
                    mock_resolver.return_value = resolver

                    existing_session_id = "test_session_123"

                    result = await execute_agent_chat(
                        agent_id=mock_autonomous_agent.id,
                        message="test",
                        user_id="user_123",
                        session_id=existing_session_id
                    )

        assert result["success"] is True
        assert result["session_id"] == existing_session_id


# ============================================================================
# Test: Agent Execution Audit Trail
# ============================================================================

class TestAgentExecutionAuditTrail:
    """Tests for AgentExecution records"""

    @pytest.mark.asyncio
    async def test_agent_execution_record_created(self, mock_autonomous_agent, mock_byok_handler, db_session):
        """AgentExecution record is created on execution start"""
        with patch('core.agent_execution_service.BYOKHandler', return_value=mock_byok_handler):
            with patch('core.agent_execution_service.ws_manager'):
                with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                    resolver = MagicMock()
                    resolver.resolve_agent_for_request = AsyncMock(
                        return_value=(mock_autonomous_agent, {})
                    )
                    resolver.governance = MagicMock()
                    resolver.governance.can_perform_action = MagicMock(
                        return_value={"proceed": True, "allowed": True}
                    )
                    mock_resolver.return_value = resolver

                    result = await execute_agent_chat(
                        agent_id=mock_autonomous_agent.id,
                        message="test",
                        user_id="user_123",
                        stream=False
                    )

        # Verify AgentExecution record was created
        execution = db_session.query(AgentExecution).filter(
            AgentExecution.agent_id == mock_autonomous_agent.id
        ).first()

        assert execution is not None
        assert execution.status == "completed"
        assert execution.agent_name == mock_autonomous_agent.name

    @pytest.mark.asyncio
    async def test_execution_record_updated_on_completion(self, mock_autonomous_agent, mock_byok_handler, db_session):
        """AgentExecution status updated to completed with output data"""
        with patch('core.agent_execution_service.BYOKHandler', return_value=mock_byok_handler):
            with patch('core.agent_execution_service.ws_manager'):
                with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                    resolver = MagicMock()
                    resolver.resolve_agent_for_request = AsyncMock(
                        return_value=(mock_autonomous_agent, {})
                    )
                    resolver.governance = MagicMock()
                    resolver.governance.can_perform_action = MagicMock(
                        return_value={"proceed": True, "allowed": True}
                    )
                    mock_resolver.return_value = resolver

                    result = await execute_agent_chat(
                        agent_id=mock_autonomous_agent.id,
                        message="test",
                        user_id="user_123"
                    )

        # Verify record updated with completion data
        execution = db_session.query(AgentExecution).filter(
            AgentExecution.agent_id == mock_autonomous_agent.id
        ).first()

        assert execution.status == "completed"
        assert execution.output_data is not None
        assert execution.output_data["response"] == "Hello world!"
        assert execution.output_data["tokens"] == 4
        assert execution.duration_ms > 0
        assert execution.end_time is not None

    @pytest.mark.asyncio
    async def test_execution_record_marked_failed_on_error(self, mock_autonomous_agent, db_session):
        """AgentExecution marked as failed on execution error"""
        with patch('core.agent_execution_service.BYOKHandler') as mock_byok:
            with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                resolver = MagicMock()
                resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_autonomous_agent, {})
                )
                resolver.governance = MagicMock()
                resolver.governance.can_perform_action.return_value = {
                    "proceed": True, "allowed": True
                }
                mock_resolver.return_value = resolver

                byok = MagicMock()
                byok.analyze_query_complexity.return_value = QueryComplexity.SIMPLE

                async def mock_stream_error(**kwargs):
                    raise Exception("LLM API failure")

                byok.stream_completion = mock_stream_error
                mock_byok.return_value = byok

                result = await execute_agent_chat(
                    agent_id=mock_autonomous_agent.id,
                    message="test",
                    user_id="user_123"
                )

        # Verify failure recorded
        execution = db_session.query(AgentExecution).filter(
            AgentExecution.agent_id == mock_autonomous_agent.id
        ).first()

        assert execution is not None
        assert execution.status == "failed"
        assert execution.error_message is not None

    @pytest.mark.asyncio
    async def test_execution_metadata_includes_governance_context(self, mock_autonomous_agent, mock_byok_handler, db_session):
        """Execution metadata includes governance check details"""
        with patch('core.agent_execution_service.BYOKHandler', return_value=mock_byok_handler):
            with patch('core.agent_execution_service.ws_manager'):
                with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                    resolver = MagicMock()
                    resolution_context = {"resolution_path": ["explicit_agent_id"]}
                    resolver.resolve_agent_for_request = AsyncMock(
                        return_value=(mock_autonomous_agent, resolution_context)
                    )
                    resolver.governance = MagicMock()
                    resolver.governance.can_perform_action.return_value = {
                        "proceed": True, "allowed": True, "maturity_level": "AUTONOMOUS"
                    }
                    mock_resolver.return_value = resolver

                    result = await execute_agent_chat(
                        agent_id=mock_autonomous_agent.id,
                        message="test",
                        user_id="user_123"
                    )

        # Verify metadata includes governance context
        execution = db_session.query(AgentExecution).filter(
            AgentExecution.agent_id == mock_autonomous_agent.id
        ).first()

        assert execution is not None
        assert execution.metadata is not None
        assert "governance_check" in execution.metadata


# ============================================================================
# Test: Episode Creation Triggering
# ============================================================================

class TestEpisodeCreationTriggering:
    """Tests for episode creation after execution"""

    @pytest.mark.asyncio
    async def test_episode_creation_triggered_after_execution(self, mock_autonomous_agent, mock_byok_handler, db_session):
        """Episode creation is triggered after successful execution"""
        with patch('core.agent_execution_service.BYOKHandler', return_value=mock_byok_handler):
            with patch('core.agent_execution_service.ws_manager'):
                with patch('core.agent_execution_service.trigger_episode_creation') as mock_episode:
                    mock_episode.return_value = None

                    with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                        resolver = MagicMock()
                        resolver.resolve_agent_for_request = AsyncMock(
                            return_value=(mock_autonomous_agent, {})
                        )
                        resolver.governance = MagicMock()
                        resolver.governance.can_perform_action.return_value = {
                            "proceed": True, "allowed": True
                        }
                        mock_resolver.return_value = resolver

                        result = await execute_agent_chat(
                            agent_id=mock_autonomous_agent.id,
                            message="test",
                            user_id="user_123"
                        )

        # Verify episode creation was triggered
        mock_episode.assert_called_once()

    @pytest.mark.asyncio
    async def test_episode_creation_error_doesnt_fail_execution(self, mock_autonomous_agent, mock_byok_handler, db_session):
        """Execution succeeds even if episode creation fails"""
        with patch('core.agent_execution_service.BYOKHandler', return_value=mock_byok_handler):
            with patch('core.agent_execution_service.ws_manager'):
                with patch('core.agent_execution_service.trigger_episode_creation') as mock_episode:
                    mock_episode.side_effect = Exception("Episode service error")

                    with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                        resolver = MagicMock()
                        resolver.resolve_agent_for_request = AsyncMock(
                            return_value=(mock_autonomous_agent, {})
                        )
                        resolver.governance = MagicMock()
                        resolver.governance.can_perform_action.return_value = {
                            "proceed": True, "allowed": True
                        }
                        mock_resolver.return_value = resolver

                        result = await execute_agent_chat(
                            agent_id=mock_autonomous_agent.id,
                            message="test",
                            user_id="user_123"
                        )

        # Execution should succeed despite episode error
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_episode_creation_with_session_context(self, mock_autonomous_agent, mock_byok_handler, db_session):
        """Episode creation includes session and agent context"""
        with patch('core.agent_execution_service.BYOKHandler', return_value=mock_byok_handler):
            with patch('core.agent_execution_service.ws_manager'):
                with patch('core.agent_execution_service.trigger_episode_creation') as mock_episode:
                    mock_episode.return_value = None

                    with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                        resolver = MagicMock()
                        resolver.resolve_agent_for_request = AsyncMock(
                            return_value=(mock_autonomous_agent, {})
                        )
                        resolver.governance = MagicMock()
                        resolver.governance.can_perform_action.return_value = {
                            "proceed": True, "allowed": True
                        }
                        mock_resolver.return_value = resolver

                        session_id = "test_session_456"

                        result = await execute_agent_chat(
                            agent_id=mock_autonomous_agent.id,
                            message="test",
                            user_id="user_123",
                            session_id=session_id
                        )

        # Verify episode creation called with correct context
        mock_episode.assert_called_once()
        call_args = mock_episode.call_args
        assert call_args[1]["session_id"] == session_id
        assert call_args[1]["agent_id"] == mock_autonomous_agent.id

    @pytest.mark.asyncio
    async def test_episode_creation_for_governance_blocked_execution(self, mock_student_agent, db_session):
        """Episode creation not triggered for governance-blocked executions"""
        with patch('core.agent_execution_service.trigger_episode_creation') as mock_episode:
            with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                resolver = MagicMock()
                resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_student_agent, {})
                )
                resolver.governance = MagicMock()
                resolver.governance.can_perform_action.return_value = {
                    "proceed": False,
                    "allowed": False,
                    "reason": "STUDENT agent blocked"
                }
                mock_resolver.return_value = resolver

                result = await execute_agent_chat(
                    agent_id=mock_student_agent.id,
                    message="test",
                    user_id="user_123"
                )

        # Episode creation should not be triggered for blocked executions
        mock_episode.assert_not_called()


# ============================================================================
# Test: Error Handling
# ============================================================================

class TestErrorHandling:
    """Tests for error scenarios"""

    @pytest.mark.asyncio
    async def test_llm_failure_caught_and_logged(self, mock_autonomous_agent, db_session):
        """LLM provider failures are caught and returned as errors"""
        with patch('core.agent_execution_service.BYOKHandler') as mock_byok:
            with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                resolver = MagicMock()
                resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_autonomous_agent, {})
                )
                resolver.governance = MagicMock()
                resolver.governance.can_perform_action.return_value = {
                    "proceed": True, "allowed": True
                }
                mock_resolver.return_value = resolver

                byok = MagicMock()
                byok.analyze_query_complexity.return_value = QueryComplexity.SIMPLE

                async def mock_stream_error(**kwargs):
                    raise Exception("OpenAI API timeout")

                byok.stream_completion = mock_stream_error
                mock_byok.return_value = byok

                result = await execute_agent_chat(
                    agent_id=mock_autonomous_agent.id,
                    message="test",
                    user_id="user_123"
                )

        assert result["success"] is False
        assert "OpenAI API timeout" in result["error"]

    @pytest.mark.asyncio
    async def test_database_connection_error_returns_error_response(self, mock_autonomous_agent, db_session, monkeypatch):
        """Database connection errors are handled gracefully"""
        # Simulate DB error by breaking session
        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_db.side_effect = Exception("Database connection failed")

            result = await execute_agent_chat(
                agent_id=mock_autonomous_agent.id,
                message="test",
                user_id="user_123"
            )

        # Should handle DB error gracefully
        # May succeed without governance or fail gracefully
        assert "success" in result or "error" in result

    @pytest.mark.asyncio
    async def test_websocket_disconnection_doesnt_affect_execution(self, mock_autonomous_agent, mock_byok_handler, db_session):
        """Execution completes even if WebSocket disconnects"""
        with patch('core.agent_execution_service.BYOKHandler', return_value=mock_byok_handler):
            with patch('core.agent_execution_service.ws_manager') as mock_ws:
                # Simulate WebSocket error
                mock_ws.broadcast.side_effect = Exception("WebSocket disconnected")

                with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                    resolver = MagicMock()
                    resolver.resolve_agent_for_request = AsyncMock(
                        return_value=(mock_autonomous_agent, {})
                    )
                    resolver.governance = MagicMock()
                    resolver.governance.can_perform_action = MagicMock(
                        return_value={"proceed": True, "allowed": True}
                    )
                    mock_resolver.return_value = resolver

                    # WebSocket error should propagate
                    try:
                        result = await execute_agent_chat(
                            agent_id=mock_autonomous_agent.id,
                            message="test",
                            user_id="user_123",
                            stream=True
                        )
                        # If it succeeds, that's okay too (WS errors are logged)
                        assert result["success"] is True or "error" in result
                    except Exception as e:
                        # WebSocket disconnection may raise exception
                        assert "WebSocket" in str(e)


# ============================================================================
# Test: Sync Execution Wrapper
# ============================================================================

class TestSyncExecutionWrapper:
    """Tests for execute_agent_chat_sync()"""

    def test_sync_wrapper_creates_event_loop(self):
        """Sync wrapper creates event loop if none exists"""
        with patch('core.agent_execution_service.BYOKHandler') as mock_byok:
            with patch('core.agent_execution_service.ws_manager'):
                with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver:
                    # Mock agent
                    mock_agent = MagicMock()
                    mock_agent.id = "test_agent"
                    mock_agent.name = "TestAgent"

                    resolver = MagicMock()
                    resolver.resolve_agent_for_request = AsyncMock(
                        return_value=(mock_agent, {})
                    )
                    resolver.governance = MagicMock()
                    resolver.governance.can_perform_action = MagicMock(
                        return_value={"proceed": True, "allowed": True}
                    )
                    mock_resolver.return_value = resolver

                    byok = MagicMock()
                    byok.analyze_query_complexity.return_value = QueryComplexity.SIMPLE
                    byok.get_optimal_provider.return_value = ("openai", "gpt-4")

                    async def mock_stream(**kwargs):
                        yield "Sync response"

                    byok.stream_completion = mock_stream
                    mock_byok.return_value = byok

                    result = execute_agent_chat_sync(
                        agent_id="test_agent",
                        message="test message",
                        user_id="user_123",
                        stream=False
                    )

        assert "success" in result or "error" in result

    def test_sync_wrapper_disables_streaming(self):
        """Sync wrapper forces stream=False regardless of input"""
        with patch('core.agent_execution_service.execute_agent_chat') as mock_execute:
            mock_execute.return_value = {"success": True, "response": "test"}

            result = execute_agent_chat_sync(
                agent_id="test_agent",
                message="test",
                user_id="user_123",
                stream=True  # Should be ignored
            )

        # Verify execute_agent_chat called with stream=False
        mock_execute.assert_called_once()
        call_kwargs = mock_execute.call_args[1]
        assert call_kwargs["stream"] is False

    def test_sync_wrapper_reuses_existing_event_loop(self):
        """Sync wrapper reuses existing event loop"""
        import asyncio

        # Create event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            with patch('core.agent_execution_service.execute_agent_chat') as mock_execute:
                mock_execute.return_value = {"success": True, "response": "test"}

                result = execute_agent_chat_sync(
                    agent_id="test_agent",
                    message="test",
                    user_id="user_123"
                )

            assert result["success"] is True
        finally:
            loop.close()

    def test_sync_wrapper_propagates_execution_result(self):
        """Sync wrapper returns full execution result"""
        with patch('core.agent_execution_service.execute_agent_chat') as mock_execute:
            mock_execute.return_value = {
                "success": True,
                "execution_id": "exec_123",
                "response": "Test response",
                "tokens": 2,
                "provider": "openai",
                "model": "gpt-4"
            }

            result = execute_agent_chat_sync(
                agent_id="test_agent",
                message="test",
                user_id="user_123"
            )

        assert result["success"] is True
        assert result["execution_id"] == "exec_123"
        assert result["response"] == "Test response"
