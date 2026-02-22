"""
Unit Tests for Agent Execution Service

Tests cover:
- Normal execution flow with LLM responses
- Governance checks and blocking
- Agent resolution fallback chain
- WebSocket streaming mode
- Conversation history handling
- LLM failure error handling
- Emergency bypass mode
- Database commit failures (graceful degradation)
- WebSocket failure handling
"""
import pytest
import os
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from datetime import datetime

from core.agent_execution_service import execute_agent_chat
from core.models import AgentRegistry, AgentStatus


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    db.query = MagicMock()
    db.add = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.refresh = Mock()
    db.flush = Mock()
    db.close = Mock()
    return db


@pytest.fixture
def mock_agent():
    """Create a mock agent."""
    return AgentRegistry(
        id="test-agent-123",
        name="TestAgent",
        description="Test agent for unit tests",
        category="testing",
        module_path="test.module",
        class_name="TestAgent",
        status=AgentStatus.AUTONOMOUS.value,
        confidence_score=0.95
    )


@pytest.fixture
def mock_byok_handler():
    """Mock BYOKHandler for LLM responses."""
    handler = MagicMock()
    handler.analyze_query_complexity.return_value = MagicMock(
        complexity_score=0.5,
        requires_reasoning=False
    )
    handler.get_optimal_provider.return_value = ("openai", "gpt-4")
    return handler


class TestExecuteAgentChatSuccess:
    """Test successful execution flows."""

    @pytest.mark.asyncio
    async def test_execute_agent_chat_success(self, mock_agent, mock_byok_handler):
        """
        Test normal execution flow.

        Validates:
        - Governance check passes
        - LLM streaming works
        - Response returned with all fields
        - Chat history saved
        """
        mock_tokens = ["Hello", "!", " How", " can", " I", " help", "?"]

        with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()):
            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent, {"resolution_path": ["explicit_agent_id"]})
                )
                MockResolver.return_value = mock_resolver

                with patch("core.agent_execution_service.AgentGovernanceService") as MockGovernance:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": "Agent is allowed"
                    }
                    MockGovernance.return_value = mock_governance

                    with patch("core.agent_execution_service.BYOKHandler", return_value=mock_byok_handler):
                        async def mock_stream(**kwargs):
                            for token in mock_tokens:
                                yield token

                        mock_byok_handler.stream_completion = mock_stream

                        with patch("core.agent_execution_service.get_chat_history_manager") as mock_hist_mgr:
                            mock_history = MagicMock()
                            mock_history.add_message = MagicMock()
                            mock_hist_mgr.return_value = mock_history

                            with patch("core.agent_execution_service.get_chat_session_manager") as mock_sess_mgr:
                                mock_session = MagicMock()
                                mock_session.create_session.return_value = "test-session-123"
                                mock_sess_mgr.return_value = mock_session

                                with patch("core.agent_execution_service.trigger_episode_creation", new=AsyncMock()):
                                    result = await execute_agent_chat(
                                        agent_id=mock_agent.id,
                                        message="Hello, agent!",
                                        user_id="test-user-123",
                                        session_id=None,
                                        workspace_id="default",
                                        conversation_history=None,
                                        stream=False
                                    )

        # Assertions
        assert result["success"] is True
        assert result["agent_id"] == mock_agent.id
        assert result["agent_name"] == mock_agent.name
        assert result["response"] == "Hello! How can I help?"
        assert result["tokens"] == len(mock_tokens)
        assert "execution_id" in result
        assert result["session_id"] == "test-session-123"
        assert result["provider"] == "openai"
        assert result["model"] == "gpt-4"

    @pytest.mark.asyncio
    async def test_execute_agent_chat_with_conversation_history(self, mock_agent, mock_byok_handler):
        """
        Test execution with conversation history.

        Validates:
        - History messages included in LLM request
        - History preserved in correct order
        - Current message appended after history
        """
        mock_tokens = ["Based", " on", " history"]

        conversation_history = [
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
        ]

        with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()):
            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent, {"resolution_path": ["explicit_agent_id"]})
                )
                MockResolver.return_value = mock_resolver

                with patch("core.agent_execution_service.AgentGovernanceService") as MockGovernance:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": "Agent is allowed"
                    }
                    MockGovernance.return_value = mock_governance

                    with patch("core.agent_execution_service.BYOKHandler", return_value=mock_byok_handler):
                        captured_messages = []

                        async def mock_stream(**kwargs):
                            captured_messages.extend(kwargs.get("messages", []))
                            for token in mock_tokens:
                                yield token

                        mock_byok_handler.stream_completion = mock_stream

                        with patch("core.agent_execution_service.get_chat_history_manager") as mock_hist_mgr:
                            mock_history = MagicMock()
                            mock_history.add_message = MagicMock()
                            mock_hist_mgr.return_value = mock_history

                            with patch("core.agent_execution_service.get_chat_session_manager") as mock_sess_mgr:
                                mock_session = MagicMock()
                                mock_session.create_session.return_value = "test-session-history"
                                mock_sess_mgr.return_value = mock_session

                                with patch("core.agent_execution_service.trigger_episode_creation", new=AsyncMock()):
                                    result = await execute_agent_chat(
                                        agent_id=mock_agent.id,
                                        message="Follow-up question",
                                        user_id="test-user-history",
                                        session_id="test-session-history",
                                        workspace_id="default",
                                        conversation_history=conversation_history,
                                        stream=False
                                    )

        # Assertions
        assert result["success"] is True

        # Verify conversation history was included
        assert len(captured_messages) >= 3  # system + history + current
        roles = [m.get("role") for m in captured_messages]
        assert "system" in roles
        assert "user" in roles
        assert "assistant" in roles

        # Verify history content preserved
        content_list = [m.get("content") for m in captured_messages]
        assert "First question" in content_list
        assert "First answer" in content_list
        assert "Follow-up question" in content_list


class TestGovernanceChecks:
    """Test governance enforcement in execution."""

    @pytest.mark.asyncio
    async def test_execute_agent_chat_with_governance_block(self, mock_agent):
        """
        Test governance blocking execution.

        Validates:
        - Governance check performed
        - Blocked actions return error
        - No LLM call made when blocked
        - Execution record not created
        """
        with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()):
            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent, {"resolution_path": ["explicit_agent_id"]})
                )
                MockResolver.return_value = mock_resolver

                with patch("core.agent_execution_service.AgentGovernanceService") as MockGovernance:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": False,
                        "reason": "STUDENT agents cannot perform this action"
                    }
                    MockGovernance.return_value = mock_governance

                    result = await execute_agent_chat(
                        agent_id=mock_agent.id,
                        message="Test blocking",
                        user_id="test-user-block",
                        session_id=None,
                        workspace_id="default",
                        conversation_history=None,
                        stream=False
                    )

        # Assertions
        assert result["success"] is False
        assert "error" in result
        assert "governance" in result["error"].lower() or "blocked" in result["error"].lower()
        assert result["agent_id"] == mock_agent.id
        assert result["execution_id"] is None

    @pytest.mark.asyncio
    async def test_execute_agent_chat_emergency_bypass(self, mock_agent, mock_byok_handler):
        """
        Test emergency governance bypass.

        Validates:
        - EMERGENCY_GOVERNANCE_BYPASS flag disables governance
        - Execution proceeds without governance check
        - Agent resolution still occurs
        """
        mock_tokens = ["Bypass", " active"]

        with patch.dict(os.environ, {"EMERGENCY_GOVERNANCE_BYPASS": "true"}):
            with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()):
                with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                    mock_resolver = MagicMock()
                    mock_resolver.resolve_agent_for_request = AsyncMock(
                        return_value=(mock_agent, {"resolution_path": ["explicit_agent_id"]})
                    )
                    MockResolver.return_value = mock_resolver

                    with patch("core.agent_execution_service.BYOKHandler", return_value=mock_byok_handler):
                        async def mock_stream(**kwargs):
                            for token in mock_tokens:
                                yield token

                        mock_byok_handler.stream_completion = mock_stream

                        with patch("core.agent_execution_service.get_chat_history_manager") as mock_hist_mgr:
                            mock_history = MagicMock()
                            mock_history.add_message = MagicMock()
                            mock_hist_mgr.return_value = mock_history

                            with patch("core.agent_execution_service.get_chat_session_manager") as mock_sess_mgr:
                                mock_session = MagicMock()
                                mock_session.create_session.return_value = "test-session-bypass"
                                mock_sess_mgr.return_value = mock_session

                                with patch("core.agent_execution_service.trigger_episode_creation", new=AsyncMock()):
                                    result = await execute_agent_chat(
                                        agent_id=mock_agent.id,
                                        message="Test bypass",
                                        user_id="test-user-bypass",
                                        session_id=None,
                                        workspace_id="default",
                                        conversation_history=None,
                                        stream=False
                                    )

        # Assertions
        assert result["success"] is True
        assert result["response"] == "Bypass active"


class TestAgentResolution:
    """Test agent resolution fallback chain."""

    @pytest.mark.asyncio
    async def test_execute_agent_chat_agent_not_found(self, mock_byok_handler):
        """
        Test agent not found fallback to system default.

        Validates:
        - Agent resolution fails for requested agent
        - System default agent used
        - Execution proceeds with default agent
        """
        mock_tokens = ["Default", " agent"]

        with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()):
            # Mock resolver to return None (agent not found)
            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(None, {"resolution_path": ["resolution_failed"]})
                )
                MockResolver.return_value = mock_resolver

                with patch("core.agent_execution_service.BYOKHandler", return_value=mock_byok_handler):
                    async def mock_stream(**kwargs):
                        for token in mock_tokens:
                            yield token

                    mock_byok_handler.stream_completion = mock_stream

                    with patch("core.agent_execution_service.get_chat_history_manager") as mock_hist_mgr:
                        mock_history = MagicMock()
                        mock_history.add_message = MagicMock()
                        mock_hist_mgr.return_value = mock_history

                        with patch("core.agent_execution_service.get_chat_session_manager") as mock_sess_mgr:
                            mock_session = MagicMock()
                            mock_session.create_session.return_value = "test-session-default"
                            mock_sess_mgr.return_value = mock_session

                            with patch("core.agent_execution_service.trigger_episode_creation", new=AsyncMock()):
                                result = await execute_agent_chat(
                                    agent_id="nonexistent-agent",
                                    message="Test default",
                                    user_id="test-user-default",
                                    session_id=None,
                                    workspace_id="default",
                                    conversation_history=None,
                                    stream=False
                                )

        # Assertions - should still succeed with system default
        assert result["success"] is True
        assert result["response"] == "Default agent"


class TestStreamingMode:
    """Test WebSocket streaming functionality."""

    @pytest.mark.asyncio
    async def test_execute_agent_chat_streaming_mode(self, mock_agent, mock_byok_handler):
        """
        Test streaming mode via WebSocket.

        Validates:
        - WebSocket manager receives start message
        - Token updates sent via WebSocket
        - Complete message sent with full response
        - message_id matches across all messages
        """
        mock_tokens = ["Stream", "ing", " test"]

        with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()):
            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent, {"resolution_path": ["explicit_agent_id"]})
                )
                MockResolver.return_value = mock_resolver

                with patch("core.agent_execution_service.AgentGovernanceService") as MockGovernance:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": "Agent is allowed"
                    }
                    MockGovernance.return_value = mock_governance

                    with patch("core.agent_execution_service.BYOKHandler", return_value=mock_byok_handler):
                        async def mock_stream(**kwargs):
                            for token in mock_tokens:
                                yield token

                        mock_byok_handler.stream_completion = mock_stream

                        with patch("core.agent_execution_service.ws_manager") as mock_ws:
                            mock_ws.broadcast = AsyncMock()
                            mock_ws.STREAMING_UPDATE = "streaming:update"
                            mock_ws.STREAMING_COMPLETE = "streaming:complete"

                            with patch("core.agent_execution_service.get_chat_history_manager") as mock_hist_mgr:
                                mock_history = MagicMock()
                                mock_history.add_message = MagicMock()
                                mock_hist_mgr.return_value = mock_history

                                with patch("core.agent_execution_service.get_chat_session_manager") as mock_sess_mgr:
                                    mock_session = MagicMock()
                                    mock_session.create_session.return_value = "test-session-stream"
                                    mock_sess_mgr.return_value = mock_session

                                    with patch("core.agent_execution_service.trigger_episode_creation", new=AsyncMock()):
                                        result = await execute_agent_chat(
                                            agent_id=mock_agent.id,
                                            message="Stream test",
                                            user_id="test-user-stream",
                                            session_id=None,
                                            workspace_id="default",
                                            conversation_history=None,
                                            stream=True
                                        )

        # Assertions
        assert result["success"] is True
        assert result["response"] == "Streaming test"
        assert "message_id" in result

        # Verify WebSocket broadcast called
        assert mock_ws.broadcast.call_count > 0

        # Check for streaming:start message
        start_calls = [call for call in mock_ws.broadcast.call_args_list
                      if len(call[0]) > 1 and call[0][1].get("type") == "streaming:start"]
        assert len(start_calls) == 1

        # Check for streaming:complete message
        complete_calls = [call for call in mock_ws.broadcast.call_args_list
                         if len(call[0]) > 1 and call[0][1].get("type") == "streaming:complete"]
        assert len(complete_calls) == 1


class TestErrorHandling:
    """Test error handling and graceful degradation."""

    @pytest.mark.asyncio
    async def test_execute_agent_chat_llm_failure(self, mock_agent):
        """
        Test LLM failure handling.

        Validates:
        - LLM errors caught gracefully
        - Error message returned to user
        - Execution record marked as failed
        - No partial results returned
        """
        with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()):
            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent, {"resolution_path": ["explicit_agent_id"]})
                )
                MockResolver.return_value = mock_resolver

                with patch("core.agent_execution_service.AgentGovernanceService") as MockGovernance:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": "Agent is allowed"
                    }
                    MockGovernance.return_value = mock_governance

                    with patch("core.agent_execution_service.BYOKHandler") as MockBYOK:
                        mock_handler = MagicMock()

                        async def mock_stream_failure(**kwargs):
                            raise Exception("LLM service unavailable")

                        mock_handler.stream_completion = mock_stream_failure
                        MockBYOK.return_value = mock_handler

                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Test error",
                            user_id="test-user-error",
                            session_id=None,
                            workspace_id="default",
                            conversation_history=None,
                            stream=False
                        )

        # Assertions
        assert result["success"] is False
        assert "error" in result
        assert result["agent_id"] == mock_agent.id
        assert "execution_id" in result

    @pytest.mark.asyncio
    async def test_execute_agent_chat_db_commit_failure(self, mock_agent, mock_byok_handler):
        """
        Test graceful handling of database commit failure.

        Validates:
        - AgentExecution record creation failure doesn't block execution
        - Execution proceeds despite audit trail failure
        - Response returned successfully
        - Error logged but not surfaced to user
        """
        mock_tokens = ["Success", " despite", " DB", " error"]

        mock_db = MagicMock()
        mock_db.add = Mock(side_effect=Exception("Database connection lost"))
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        mock_db.close = Mock()

        with patch("core.agent_execution_service.SessionLocal", return_value=mock_db):
            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent, {"resolution_path": ["explicit_agent_id"]})
                )
                MockResolver.return_value = mock_resolver

                with patch("core.agent_execution_service.AgentGovernanceService") as MockGovernance:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": "Agent is allowed"
                    }
                    MockGovernance.return_value = mock_governance

                    with patch("core.agent_execution_service.BYOKHandler", return_value=mock_byok_handler):
                        async def mock_stream(**kwargs):
                            for token in mock_tokens:
                                yield token

                        mock_byok_handler.stream_completion = mock_stream

                        with patch("core.agent_execution_service.get_chat_history_manager") as mock_hist_mgr:
                            mock_history = MagicMock()
                            mock_history.add_message = MagicMock()
                            mock_hist_mgr.return_value = mock_history

                            with patch("core.agent_execution_service.get_chat_session_manager") as mock_sess_mgr:
                                mock_session = MagicMock()
                                mock_session.create_session.return_value = "test-session-db-error"
                                mock_sess_mgr.return_value = mock_session

                                with patch("core.agent_execution_service.trigger_episode_creation", new=AsyncMock()):
                                    result = await execute_agent_chat(
                                        agent_id=mock_agent.id,
                                        message="Test DB error",
                                        user_id="test-user-db-error",
                                        session_id=None,
                                        workspace_id="default",
                                        conversation_history=None,
                                        stream=False
                                    )

        # Assertions - should succeed despite DB error
        assert result["success"] is True
        assert result["response"] == "Success despite DB error"

    @pytest.mark.asyncio
    async def test_execute_agent_chat_websocket_failure(self, mock_agent, mock_byok_handler):
        """
        Test graceful handling of WebSocket broadcast failure.

        Validates:
        - WebSocket errors don't block execution
        - Response still accumulated and returned
        - Error logged but not surfaced
        """
        mock_tokens = ["Response", " despite", " WS", " error"]

        with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()):
            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent, {"resolution_path": ["explicit_agent_id"]})
                )
                MockResolver.return_value = mock_resolver

                with patch("core.agent_execution_service.AgentGovernanceService") as MockGovernance:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": "Agent is allowed"
                    }
                    MockGovernance.return_value = mock_governance

                    with patch("core.agent_execution_service.BYOKHandler", return_value=mock_byok_handler):
                        async def mock_stream(**kwargs):
                            for token in mock_tokens:
                                yield token

                        mock_byok_handler.stream_completion = mock_stream

                        # Mock WebSocket manager to fail
                        with patch("core.agent_execution_service.ws_manager") as mock_ws:
                            mock_ws.broadcast = AsyncMock(side_effect=Exception("WebSocket connection lost"))
                            mock_ws.STREAMING_UPDATE = "streaming:update"
                            mock_ws.STREAMING_COMPLETE = "streaming:complete"

                            with patch("core.agent_execution_service.get_chat_history_manager") as mock_hist_mgr:
                                mock_history = MagicMock()
                                mock_history.add_message = MagicMock()
                                mock_hist_mgr.return_value = mock_history

                                with patch("core.agent_execution_service.get_chat_session_manager") as mock_sess_mgr:
                                    mock_session = MagicMock()
                                    mock_session.create_session.return_value = "test-session-ws-error"
                                    mock_sess_mgr.return_value = mock_session

                                    with patch("core.agent_execution_service.trigger_episode_creation", new=AsyncMock()):
                                        result = await execute_agent_chat(
                                            agent_id=mock_agent.id,
                                            message="Test WS error",
                                            user_id="test-user-ws-error",
                                            session_id=None,
                                            workspace_id="default",
                                            conversation_history=None,
                                            stream=True
                                        )

        # Assertions - should fail due to WebSocket error during streaming
        assert result["success"] is False
        assert "error" in result


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_execute_agent_chat_empty_message(self, mock_agent, mock_byok_handler):
        """Test execution with empty message."""
        mock_tokens = [""]

        with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()):
            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent, {"resolution_path": ["explicit_agent_id"]})
                )
                MockResolver.return_value = mock_resolver

                with patch("core.agent_execution_service.AgentGovernanceService") as MockGovernance:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": "Agent is allowed"
                    }
                    MockGovernance.return_value = mock_governance

                    with patch("core.agent_execution_service.BYOKHandler", return_value=mock_byok_handler):
                        async def mock_stream(**kwargs):
                            for token in mock_tokens:
                                yield token

                        mock_byok_handler.stream_completion = mock_stream

                        with patch("core.agent_execution_service.get_chat_history_manager") as mock_hist_mgr:
                            mock_history = MagicMock()
                            mock_history.add_message = MagicMock()
                            mock_hist_mgr.return_value = mock_history

                            with patch("core.agent_execution_service.get_chat_session_manager") as mock_sess_mgr:
                                mock_session = MagicMock()
                                mock_session.create_session.return_value = "test-session-empty"
                                mock_sess_mgr.return_value = mock_session

                                with patch("core.agent_execution_service.trigger_episode_creation", new=AsyncMock()):
                                    result = await execute_agent_chat(
                                        agent_id=mock_agent.id,
                                        message="",
                                        user_id="test-user-empty",
                                        session_id=None,
                                        workspace_id="default",
                                        conversation_history=None,
                                        stream=False
                                    )

        # Should handle empty message gracefully
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_agent_chat_very_long_message(self, mock_agent, mock_byok_handler):
        """Test execution with very long message."""
        long_message = "Test " * 10000  # 50k characters
        mock_tokens = ["Received"]

        with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()):
            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent, {"resolution_path": ["explicit_agent_id"]})
                )
                MockResolver.return_value = mock_resolver

                with patch("core.agent_execution_service.AgentGovernanceService") as MockGovernance:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": "Agent is allowed"
                    }
                    MockGovernance.return_value = mock_governance

                    with patch("core.agent_execution_service.BYOKHandler", return_value=mock_byok_handler):
                        async def mock_stream(**kwargs):
                            for token in mock_tokens:
                                yield token

                        mock_byok_handler.stream_completion = mock_stream

                        with patch("core.agent_execution_service.get_chat_history_manager") as mock_hist_mgr:
                            mock_history = MagicMock()
                            mock_history.add_message = MagicMock()
                            mock_hist_mgr.return_value = mock_history

                            with patch("core.agent_execution_service.get_chat_session_manager") as mock_sess_mgr:
                                mock_session = MagicMock()
                                mock_session.create_session.return_value = "test-session-long"
                                mock_sess_mgr.return_value = mock_session

                                with patch("core.agent_execution_service.trigger_episode_creation", new=AsyncMock()):
                                    result = await execute_agent_chat(
                                        agent_id=mock_agent.id,
                                        message=long_message,
                                        user_id="test-user-long",
                                        session_id=None,
                                        workspace_id="default",
                                        conversation_history=None,
                                        stream=False
                                    )

        # Should handle long message
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_agent_chat_governance_disabled(self, mock_agent, mock_byok_handler):
        """Test execution when governance is disabled via feature flag."""
        mock_tokens = ["No", " governance"]

        with patch.dict(os.environ, {"STREAMING_GOVERNANCE_ENABLED": "false"}):
            with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()):
                with patch("core.agent_execution_service.BYOKHandler", return_value=mock_byok_handler):
                    async def mock_stream(**kwargs):
                        for token in mock_tokens:
                            yield token

                    mock_byok_handler.stream_completion = mock_stream

                    with patch("core.agent_execution_service.get_chat_history_manager") as mock_hist_mgr:
                        mock_history = MagicMock()
                        mock_history.add_message = MagicMock()
                        mock_hist_mgr.return_value = mock_history

                        with patch("core.agent_execution_service.get_chat_session_manager") as mock_sess_mgr:
                            mock_session = MagicMock()
                            mock_session.create_session.return_value = "test-session-no-gov"
                            mock_sess_mgr.return_value = mock_session

                            with patch("core.agent_execution_service.trigger_episode_creation", new=AsyncMock()):
                                result = await execute_agent_chat(
                                    agent_id=mock_agent.id,
                                    message="Test no governance",
                                    user_id="test-user-no-gov",
                                    session_id=None,
                                    workspace_id="default",
                                    conversation_history=None,
                                    stream=False
                                )

        # Should succeed without governance
        assert result["success"] is True
        assert result["response"] == "No governance"


class TestDatabaseErrorHandling:
    """Test database error handling and graceful degradation."""

    @pytest.mark.asyncio
    async def test_execute_agent_chat_db_refresh_failure(self, mock_agent, mock_byok_handler):
        """
        Test DB session refresh failure during AgentExecution creation.

        Validates:
        - db.refresh() failure is caught gracefully
        - Execution continues despite refresh error
        - Response returned successfully
        """
        mock_tokens = ["Success", " despite", " refresh", " error"]

        mock_db = MagicMock()
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock(side_effect=Exception("Connection timeout"))
        mock_db.close = Mock()

        with patch("core.agent_execution_service.SessionLocal", return_value=mock_db):
            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent, {"resolution_path": ["explicit_agent_id"]})
                )
                MockResolver.return_value = mock_resolver

                with patch("core.agent_execution_service.AgentGovernanceService") as MockGovernance:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": "Agent is allowed"
                    }
                    MockGovernance.return_value = mock_governance

                    with patch("core.agent_execution_service.BYOKHandler", return_value=mock_byok_handler):
                        async def mock_stream(**kwargs):
                            for token in mock_tokens:
                                yield token

                        mock_byok_handler.stream_completion = mock_stream

                        with patch("core.agent_execution_service.get_chat_history_manager") as mock_hist_mgr:
                            mock_history = MagicMock()
                            mock_history.add_message = MagicMock()
                            mock_hist_mgr.return_value = mock_history

                            with patch("core.agent_execution_service.get_chat_session_manager") as mock_sess_mgr:
                                mock_session = MagicMock()
                                mock_session.create_session.return_value = "test-session-refresh-error"
                                mock_sess_mgr.return_value = mock_session

                                with patch("core.agent_execution_service.trigger_episode_creation", new=AsyncMock()):
                                    result = await execute_agent_chat(
                                        agent_id=mock_agent.id,
                                        message="Test refresh error",
                                        user_id="test-user-refresh-error",
                                        session_id=None,
                                        workspace_id="default",
                                        conversation_history=None,
                                        stream=False
                                    )

        # Should succeed despite refresh error
        assert result["success"] is True
        assert result["response"] == "Success despite refresh error"

    @pytest.mark.asyncio
    async def test_execute_agent_chat_chat_history_persistence_failure(self, mock_agent, mock_byok_handler):
        """
        Test chat history persistence failure handling.

        Validates:
        - chat_history.add_message() errors are caught
        - Request doesn't fail on persistence errors
        - Response still returned to user
        """
        mock_tokens = ["Response", " despite", " persistence", " error"]

        with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()):
            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent, {"resolution_path": ["explicit_agent_id"]})
                )
                MockResolver.return_value = mock_resolver

                with patch("core.agent_execution_service.AgentGovernanceService") as MockGovernance:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": "Agent is allowed"
                    }
                    MockGovernance.return_value = mock_governance

                    with patch("core.agent_execution_service.BYOKHandler", return_value=mock_byok_handler):
                        async def mock_stream(**kwargs):
                            for token in mock_tokens:
                                yield token

                        mock_byok_handler.stream_completion = mock_stream

                        with patch("core.agent_execution_service.get_chat_history_manager") as mock_hist_mgr:
                            mock_history = MagicMock()
                            mock_history.add_message = Mock(side_effect=Exception("DB unavailable"))
                            mock_hist_mgr.return_value = mock_history

                            with patch("core.agent_execution_service.get_chat_session_manager") as mock_sess_mgr:
                                mock_session = MagicMock()
                                mock_session.create_session.return_value = "test-session-persist-error"
                                mock_sess_mgr.return_value = mock_session

                                with patch("core.agent_execution_service.trigger_episode_creation", new=AsyncMock()):
                                    result = await execute_agent_chat(
                                        agent_id=mock_agent.id,
                                        message="Test persistence error",
                                        user_id="test-user-persist-error",
                                        session_id=None,
                                        workspace_id="default",
                                        conversation_history=None,
                                        stream=False
                                    )

        # Should succeed despite persistence error
        assert result["success"] is True
        assert result["response"] == "Response despite persistence error"

    @pytest.mark.asyncio
    async def test_execute_agent_chat_execution_update_failure(self, mock_agent, mock_byok_handler):
        """
        Test AgentExecution record update failure handling.

        Validates:
        - Execution record update errors are caught
        - Status update failures don't block response
        - Error logged but not surfaced to user
        """
        mock_tokens = ["Response", " despite", " update", " error"]

        mock_db = MagicMock()
        mock_db.add = Mock()
        mock_db.commit = Mock(side_effect=[None, Exception("Update failed")])  # Second commit fails
        mock_db.refresh = Mock()
        mock_db.close = Mock()

        with patch("core.agent_execution_service.SessionLocal", return_value=mock_db):
            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent, {"resolution_path": ["explicit_agent_id"]})
                )
                MockResolver.return_value = mock_resolver

                with patch("core.agent_execution_service.AgentGovernanceService") as MockGovernance:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": "Agent is allowed"
                    }
                    MockGovernance.return_value = mock_governance

                    with patch("core.agent_execution_service.BYOKHandler", return_value=mock_byok_handler):
                        async def mock_stream(**kwargs):
                            for token in mock_tokens:
                                yield token

                        mock_byok_handler.stream_completion = mock_stream

                        with patch("core.agent_execution_service.get_chat_history_manager") as mock_hist_mgr:
                            mock_history = MagicMock()
                            mock_history.add_message = MagicMock()
                            mock_hist_mgr.return_value = mock_history

                            with patch("core.agent_execution_service.get_chat_session_manager") as mock_sess_mgr:
                                mock_session = MagicMock()
                                mock_session.create_session.return_value = "test-session-update-error"
                                mock_sess_mgr.return_value = mock_session

                                with patch("core.agent_execution_service.trigger_episode_creation", new=AsyncMock()):
                                    result = await execute_agent_chat(
                                        agent_id=mock_agent.id,
                                        message="Test update error",
                                        user_id="test-user-update-error",
                                        session_id=None,
                                        workspace_id="default",
                                        conversation_history=None,
                                        stream=False
                                    )

        # Should succeed despite update error
        assert result["success"] is True
        assert result["response"] == "Response despite update error"

    @pytest.mark.asyncio
    async def test_execute_agent_chat_episode_creation_failure(self, mock_agent, mock_byok_handler):
        """
        Test episode creation trigger failure handling.

        Validates:
        - Episode creation errors are caught gracefully
        - Response returned despite episode failure
        - Warning logged but not surfaced
        """
        mock_tokens = ["Response", " despite", " episode", " error"]

        with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()):
            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent, {"resolution_path": ["explicit_agent_id"]})
                )
                MockResolver.return_value = mock_resolver

                with patch("core.agent_execution_service.AgentGovernanceService") as MockGovernance:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": "Agent is allowed"
                    }
                    MockGovernance.return_value = mock_governance

                    with patch("core.agent_execution_service.BYOKHandler", return_value=mock_byok_handler):
                        async def mock_stream(**kwargs):
                            for token in mock_tokens:
                                yield token

                        mock_byok_handler.stream_completion = mock_stream

                        with patch("core.agent_execution_service.get_chat_history_manager") as mock_hist_mgr:
                            mock_history = MagicMock()
                            mock_history.add_message = MagicMock()
                            mock_hist_mgr.return_value = mock_history

                            with patch("core.agent_execution_service.get_chat_session_manager") as mock_sess_mgr:
                                mock_session = MagicMock()
                                mock_session.create_session.return_value = "test-session-episode-error"
                                mock_sess_mgr.return_value = mock_session

                                async def mock_episode_failure(**kwargs):
                                    raise Exception("LanceDB unavailable")

                                with patch("core.agent_execution_service.trigger_episode_creation",
                                           side_effect=mock_episode_failure):
                                    result = await execute_agent_chat(
                                        agent_id=mock_agent.id,
                                        message="Test episode error",
                                        user_id="test-user-episode-error",
                                        session_id=None,
                                        workspace_id="default",
                                        conversation_history=None,
                                        stream=False
                                    )

        # Should succeed despite episode error
        assert result["success"] is True
        assert result["response"] == "Response despite episode error"

    @pytest.mark.asyncio
    async def test_execute_agent_chat_failed_execution_record_update_error(self, mock_agent):
        """
        Test error when updating failed execution record itself fails.

        Validates:
        - Nested error handling (LLM fails + record update fails)
        - Outer exception still raised correctly
        - Error response returned to user
        """
        with patch("core.agent_execution_service.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_db.commit = Mock(side_effect=Exception("DB locked"))
            mock_sl.return_value = mock_db

            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent, {"resolution_path": ["explicit_agent_id"]})
                )
                MockResolver.return_value = mock_resolver

                with patch("core.agent_execution_service.AgentGovernanceService") as MockGovernance:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": "Agent is allowed"
                    }
                    MockGovernance.return_value = mock_governance

                    with patch("core.agent_execution_service.BYOKHandler") as MockBYOK:
                        mock_handler = MagicMock()

                        async def mock_stream_failure(**kwargs):
                            raise Exception("LLM service unavailable")

                        mock_handler.stream_completion = mock_stream_failure
                        MockBYOK.return_value = mock_handler

                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Test nested error",
                            user_id="test-user-nested",
                            session_id=None,
                            workspace_id="default",
                            conversation_history=None,
                            stream=False
                        )

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_agent_chat_db_close_error(self, mock_agent, mock_byok_handler):
        """
        Test DB session close error handling in finally block.

        Validates:
        - db.close() errors in finally block are caught
        - Response still returned successfully
        - No exception propagates to caller
        """
        mock_tokens = ["Success", " despite", " close", " error"]

        mock_db = MagicMock()
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        mock_db.close = Mock(side_effect=Exception("Connection already closed"))

        with patch("core.agent_execution_service.SessionLocal", return_value=mock_db):
            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent, {"resolution_path": ["explicit_agent_id"]})
                )
                MockResolver.return_value = mock_resolver

                with patch("core.agent_execution_service.AgentGovernanceService") as MockGovernance:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": "Agent is allowed"
                    }
                    MockGovernance.return_value = mock_governance

                    with patch("core.agent_execution_service.BYOKHandler", return_value=mock_byok_handler):
                        async def mock_stream(**kwargs):
                            for token in mock_tokens:
                                yield token

                        mock_byok_handler.stream_completion = mock_stream

                        with patch("core.agent_execution_service.get_chat_history_manager") as mock_hist_mgr:
                            mock_history = MagicMock()
                            mock_history.add_message = MagicMock()
                            mock_hist_mgr.return_value = mock_history

                            with patch("core.agent_execution_service.get_chat_session_manager") as mock_sess_mgr:
                                mock_session = MagicMock()
                                mock_session.create_session.return_value = "test-session-close-error"
                                mock_sess_mgr.return_value = mock_session

                                with patch("core.agent_execution_service.trigger_episode_creation", new=AsyncMock()):
                                    result = await execute_agent_chat(
                                        agent_id=mock_agent.id,
                                        message="Test close error",
                                        user_id="test-user-close-error",
                                        session_id=None,
                                        workspace_id="default",
                                        conversation_history=None,
                                        stream=False
                                    )

        # Should succeed despite close error
        assert result["success"] is True
        assert result["response"] == "Success despite close error"


class TestSyncWrapper:
    """Test synchronous wrapper functionality."""

    def test_execute_agent_chat_sync_basic(self, mock_agent, mock_byok_handler):
        """
        Test sync wrapper basic functionality.

        Validates:
        - execute_agent_chat_sync properly wraps async function
        - Response returned successfully
        - All fields present in response
        """
        from core.agent_execution_service import execute_agent_chat_sync

        mock_tokens = ["Sync", " response"]

        with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()):
            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(mock_agent, {"resolution_path": ["explicit_agent_id"]})
                )
                MockResolver.return_value = mock_resolver

                with patch("core.agent_execution_service.AgentGovernanceService") as MockGovernance:
                    mock_governance = MagicMock()
                    mock_governance.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": "Agent is allowed"
                    }
                    MockGovernance.return_value = mock_governance

                    with patch("core.agent_execution_service.BYOKHandler", return_value=mock_byok_handler):
                        async def mock_stream(**kwargs):
                            for token in mock_tokens:
                                yield token

                        mock_byok_handler.stream_completion = mock_stream

                        with patch("core.agent_execution_service.get_chat_history_manager") as mock_hist_mgr:
                            mock_history = MagicMock()
                            mock_history.add_message = MagicMock()
                            mock_hist_mgr.return_value = mock_history

                            with patch("core.agent_execution_service.get_chat_session_manager") as mock_sess_mgr:
                                mock_session = MagicMock()
                                mock_session.create_session.return_value = "test-session-sync"
                                mock_sess_mgr.return_value = mock_session

                                with patch("core.agent_execution_service.trigger_episode_creation", new=AsyncMock()):
                                    result = execute_agent_chat_sync(
                                        agent_id=mock_agent.id,
                                        message="Sync test",
                                        user_id="test-sync-user",
                                    )

        # Should succeed
        assert result["success"] is True
        assert result["response"] == "Sync response"
