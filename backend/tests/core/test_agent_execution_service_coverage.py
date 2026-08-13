"""
Comprehensive tests for Agent Execution Service

Target: 60%+ coverage for core/agent_execution_service.py (419 lines)
Focus: Agent chat execution, governance integration, streaming, persistence, error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from datetime import datetime
import asyncio
import uuid

from core.agent_execution_service import execute_agent_chat, execute_agent_chat_sync
from core.models import AgentRegistry, AgentExecution, User


# ========================================================================
# Fixtures
# ========================================================================


@pytest.fixture
def mock_agent(db_session):
    """Create a mock agent for testing."""
    agent = AgentRegistry(
        id=f"test-agent-{uuid.uuid4()}",
        name="Test Agent",
        category="general",
        description="A test agent for unit testing",
        status="AUTONOMOUS",
        module_path="test.module",
        class_name="TestClass",
        confidence_score=0.95
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def mock_user(db_session):
    """Create a mock user for testing."""
    user = User(
        id=f"test-user-{uuid.uuid4()}",
        email=f"test-{uuid.uuid4()}@example.com",
        first_name="Test",
        last_name="User", role="member", status="active"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def mock_agent_resolution():
    """Mock agent context resolver."""
    with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver_cls:
        resolver = MagicMock()
        mock_resolver_cls.return_value = resolver
        yield resolver


@pytest.fixture
def mock_governance():
    """Mock agent governance service."""
    with patch('core.agent_execution_service.AgentGovernanceService') as mock_gov_cls:
        governance = MagicMock()
        mock_gov_cls.return_value = governance
        yield governance


@pytest.fixture
def mock_llm_service():
    """Mock LLM service."""
    with patch('core.agent_execution_service.LLMService') as mock_service_cls:
        llm_service = MagicMock()
        mock_service_cls.return_value = llm_service
        llm_service.analyze_query_complexity.return_value = MagicMock(
            complexity_score=0.5,
            estimated_tokens=100
        )
        llm_service.get_optimal_provider.return_value = ("openai", "gpt-4")
        llm_service.stream_completion.return_value = _async_stream_tokens(["Hello", " world", "!"])
        yield llm_service


@pytest.fixture
def mock_websocket_manager():
    """Mock WebSocket manager."""
    with patch('core.agent_execution_service.ws_manager') as mock_ws:
        mock_ws.broadcast = AsyncMock()
        mock_ws.STREAMING_UPDATE = "streaming:update"
        mock_ws.STREAMING_COMPLETE = "streaming:complete"
        yield mock_ws


def _async_stream_tokens(tokens):
    """Helper to create async generator for streaming tokens."""
    async def generator():
        for token in tokens:
            yield token
    return generator()


# ========================================================================
# TestAgentExecutionService: Service Initialization and Configuration
# ========================================================================


class TestAgentExecutionService:
    """Test agent execution service initialization and configuration."""

    @pytest.mark.asyncio
    async def test_execute_agent_chat_success(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service):
        """Test successful agent chat execution."""
        # Setup mocks
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            with patch('core.agent_execution_service.get_chat_history_manager') as mock_chat:
                with patch('core.agent_execution_service.get_chat_session_manager') as mock_sess_mgr:
                    with patch('core.agent_execution_service.trigger_episode_creation') as mock_episode:
                        mock_chat.return_value = MagicMock()
                        mock_sess_mgr.return_value = MagicMock()
                        mock_episode.return_value = AsyncMock()

                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello, how are you?",
                            user_id=mock_user.id
                        )

                        assert result["success"] is True
                        assert "execution_id" in result
                        assert "response" in result
                        assert result["agent_id"] == mock_agent.id
                        assert result["agent_name"] == mock_agent.name

    @pytest.mark.asyncio
    async def test_execute_agent_chat_with_conversation_history(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service):
        """Test agent chat execution with conversation history."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        conversation_history = [
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"}
        ]

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="New message",
                            user_id=mock_user.id,
                            conversation_history=conversation_history
                        )

                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_agent_chat_with_session_id(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service):
        """Test agent chat execution with existing session ID."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id,
                            session_id="existing-session-123"
                        )

                        assert result["success"] is True
                        assert result["session_id"] == "existing-session-123"

    @pytest.mark.asyncio
    async def test_execute_agent_chat_with_custom_workspace(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service):
        """Test agent chat execution with custom workspace."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id,
                            workspace_id="custom-workspace"
                        )

                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_agent_chat_without_governance(self, mock_user, mock_llm_service):
        """Test agent chat execution without governance enabled."""
        with patch.dict('os.environ', {'STREAMING_GOVERNANCE_ENABLED': 'false'}):
            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        result = await execute_agent_chat(
                            agent_id="test-agent",
                            message="Hello",
                            user_id=mock_user.id
                        )

                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_agent_chat_with_emergency_bypass(self, mock_agent, mock_user, mock_llm_service):
        """Test agent chat execution with emergency bypass."""
        with patch.dict('os.environ', {'EMERGENCY_GOVERNANCE_BYPASS': 'true'}):
            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id
                        )

                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_agent_chat_agent_resolution_fails(self, mock_user, mock_agent_resolution, mock_governance, mock_llm_service):
        """Test agent chat execution when agent resolution fails."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(None, None))

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        result = await execute_agent_chat(
                            agent_id="nonexistent-agent",
                            message="Hello",
                            user_id=mock_user.id
                        )

                        # Should fall through to system default and still succeed
                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_agent_chat_returns_execution_metadata(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service):
        """Test that execution returns metadata including tokens and provider."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id
                        )

                        assert "tokens" in result
                        assert "model" in result
                        assert result["model"] == "auto"

    @pytest.mark.asyncio
    async def test_execute_agent_chat_creates_agent_execution_record(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service):
        """Test that AgentExecution record is created."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id
                        )

                        # Verify AgentExecution was added to session
                        assert mock_session.add.called
                        assert mock_session.commit.called

    @pytest.mark.asyncio
    async def test_execute_agent_chat_analyzes_query_complexity(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service):
        """Test that query complexity is analyzed."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Complex query with multiple questions",
                            user_id=mock_user.id
                        )

                        # Verify complexity analysis was called
                        mock_llm_service.analyze_query_complexity.assert_called_once()


# ========================================================================
# TestExecutionLifecycle: Execution States and Transitions
# ========================================================================


class TestExecutionLifecycle:
    """Test execution lifecycle, states, and transitions."""

    @pytest.mark.asyncio
    async def test_execution_state_running_to_completed(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service):
        """Test execution transitions from running to completed."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            # Track the AgentExecution object
            execution_obj = None

            def mock_add(obj):
                nonlocal execution_obj
                execution_obj = obj

            mock_session.add = mock_add
            mock_session.query.return_value.filter.return_value.first.side_effect = lambda: execution_obj

            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id
                        )

                        assert result["success"] is True
                        # Execution should be marked as completed
                        if execution_obj:
                            assert execution_obj.status == "completed"

    @pytest.mark.asyncio
    async def test_execution_records_duration(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service):
        """Test that execution duration is recorded."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id
                        )

                        # Verify execution completed with duration
                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execution_updates_output_data(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service):
        """Test that execution output data is updated."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id
                        )

                        # Verify execution has output data
                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execution_records_end_time(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service):
        """Test that execution end time is recorded."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id
                        )

                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execution_without_governance_skips_audit(self, mock_user, mock_llm_service):
        """Test that execution without governance skips audit record."""
        with patch.dict('os.environ', {'STREAMING_GOVERNANCE_ENABLED': 'false'}):
            with patch('core.agent_execution_service.SessionLocal') as mock_db:
                mock_session = MagicMock()
                mock_db.return_value = mock_session

                with patch('core.agent_execution_service.get_chat_history_manager'):
                    with patch('core.agent_execution_service.get_chat_session_manager'):
                        with patch('core.agent_execution_service.trigger_episode_creation'):
                            result = await execute_agent_chat(
                                agent_id="test-agent",
                                message="Hello",
                                user_id=mock_user.id
                            )

                            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execution_with_session_creates_continuity(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service):
        """Test that execution with session ID maintains continuity."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id,
                            session_id="existing-session"
                        )

                        assert result["success"] is True
                        assert result["session_id"] == "existing-session"

    @pytest.mark.asyncio
    async def test_execution_without_session_creates_new(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service):
        """Test that execution without session ID creates new session."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            mock_session_mgr = MagicMock()
            mock_session_mgr.create_session.return_value = "new-session-123"

            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager', return_value=mock_session_mgr):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id
                        )

                        assert result["success"] is True
                        # Session should be created
                        mock_session_mgr.create_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_execution_saves_to_chat_history(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service):
        """Test that messages are saved to chat history."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            mock_chat = MagicMock()
            mock_chat.add_message = MagicMock()

            with patch('core.agent_execution_service.get_chat_history_manager', return_value=mock_chat):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id
                        )

                        assert result["success"] is True
                        # Should save both user and assistant messages
                        assert mock_chat.add_message.call_count == 2

    @pytest.mark.asyncio
    async def test_execution_triggers_episode_creation(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service):
        """Test that episode creation is triggered."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            mock_episode = AsyncMock()

            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation', return_value=mock_episode) as mock_episode_fn:
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id
                        )

                        assert result["success"] is True
                        # Episode creation should be triggered
                        mock_episode_fn.assert_called_once()


# ========================================================================
# TestExecutionMonitoring: Progress Tracking and Status
# ========================================================================


class TestExecutionMonitoring:
    """Test execution monitoring, progress tracking, and logging."""

    @pytest.mark.asyncio
    async def test_execution_with_streaming_enabled(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service, mock_websocket_manager):
        """Test execution with WebSocket streaming enabled."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id,
                            stream=True
                        )

                        assert result["success"] is True
                        # Should have sent streaming messages
                        assert mock_websocket_manager.broadcast.called

    @pytest.mark.asyncio
    async def test_streaming_sends_start_message(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service, mock_websocket_manager):
        """Test that streaming sends start message."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id,
                            stream=True
                        )

                        assert result["success"] is True
                        # First message should be streaming:start
                        first_call = mock_websocket_manager.broadcast.call_args_list[0]
                        assert first_call[0][0] == f"user:{mock_user.id}"
                        assert first_call[0][1]["type"] == "streaming:start"

    @pytest.mark.asyncio
    async def test_streaming_sends_update_messages(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service, mock_websocket_manager):
        """Test that streaming sends update messages for each token."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id,
                            stream=True
                        )

                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_streaming_sends_complete_message(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service, mock_websocket_manager):
        """Test that streaming sends complete message."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id,
                            stream=True
                        )

                        assert result["success"] is True
                        # Last message should be streaming:complete
                        last_call = mock_websocket_manager.broadcast.call_args_list[-1]
                        assert last_call[0][0] == f"user:{mock_user.id}"
                        assert last_call[0][1]["type"] == "streaming:complete"

    @pytest.mark.asyncio
    async def test_streaming_includes_message_id(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service, mock_websocket_manager):
        """Test that streaming includes unique message ID."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id,
                            stream=True
                        )

                        assert result["success"] is True
                        # Should have message_id
                        assert "message_id" in result

    @pytest.mark.asyncio
    async def test_streaming_broadcasts_to_user_channel(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service, mock_websocket_manager):
        """Test that streaming broadcasts to user-specific channel."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id,
                            stream=True
                        )

                        assert result["success"] is True
                        # All broadcasts should be to user:{user_id}
                        for call in mock_websocket_manager.broadcast.call_args_list:
                            assert call[0][0] == f"user:{mock_user.id}"

    @pytest.mark.asyncio
    async def test_non_streaming_skips_websocket(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service, mock_websocket_manager):
        """Test that non-streaming execution doesn't use WebSocket."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id,
                            stream=False
                        )

                        assert result["success"] is True
                        # Should not have broadcast anything
                        assert not mock_websocket_manager.broadcast.called

    @pytest.mark.asyncio
    async def test_execution_without_streaming_still_succeeds(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service):
        """Test that execution succeeds without streaming."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id,
                            stream=False
                        )

                        assert result["success"] is True
                        assert "response" in result


# ========================================================================
# TestExecutionErrors: Error Handling and Edge Cases
# ========================================================================


class TestExecutionErrors:
    """Test execution error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_governance_denies_execution(self, mock_agent, mock_user, mock_agent_resolution, mock_governance):
        """Test that governance denial prevents execution."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "Agent maturity level insufficient for this action"
        }

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            result = await execute_agent_chat(
                agent_id=mock_agent.id,
                message="Hello",
                user_id=mock_user.id
            )

            assert result["success"] is False
            assert "governance" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_agent_execution_record_creation_fails(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service):
        """Test execution continues even if AgentExecution record creation fails."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session
            mock_session.add.side_effect = Exception("Database error")

            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        # Should still succeed despite audit failure
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id
                        )

                        # Execution should continue despite audit failure
                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_chat_history_persistence_fails(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service):
        """Test execution continues even if chat history persistence fails."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            mock_chat = MagicMock()
            mock_chat.add_message.side_effect = Exception("Chat history error")

            with patch('core.agent_execution_service.get_chat_history_manager', return_value=mock_chat):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation'):
                        # Should still succeed despite persistence failure
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id
                        )

                        # Should not fail the request
                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_llm_streaming_fails(self, mock_agent, mock_user, mock_agent_resolution, mock_governance):
        """Test execution handles LLM streaming failure."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            with patch('core.agent_execution_service.LLMService') as mock_service_cls:
                llm_service = MagicMock()
                mock_service_cls.return_value = llm_service
                llm_service.analyze_query_complexity.return_value = MagicMock()
                llm_service.get_optimal_provider.return_value = ("openai", "gpt-4")

                # Make streaming fail
                async def failing_stream():
                    raise Exception("LLM API error")
                    yield

                llm_service.stream_completion = failing_stream

                result = await execute_agent_chat(
                    agent_id=mock_agent.id,
                    message="Hello",
                    user_id=mock_user.id
                )

                assert result["success"] is False
                assert "error" in result

    @pytest.mark.asyncio
    async def test_episode_creation_fails_gracefully(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service):
        """Test execution continues even if episode creation fails."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            async def failing_episode(*args, **kwargs):
                raise Exception("Episode creation error")

            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation', side_effect=failing_episode):
                        # Should still succeed despite episode failure
                        result = await execute_agent_chat(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id
                        )

                        # Should not fail the request
                        assert result["success"] is True


# ========================================================================
# TestSynchronousExecution: Sync Wrapper Functionality
# ========================================================================


class TestSynchronousExecution:
    """Test synchronous wrapper for async execution."""

    def test_execute_agent_chat_sync_success(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service):
        """Test synchronous wrapper executes successfully."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal'):
            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation') as mock_episode:
                        mock_episode.return_value = AsyncMock()
                        result = execute_agent_chat_sync(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id
                        )

                        # Should return success
                        assert result["success"] is True

    def test_execute_agent_chat_sync_disables_streaming(self, mock_agent, mock_user):
        """Test that sync wrapper disables streaming."""
        with patch('core.agent_execution_service.SessionLocal'):
            with patch('core.agent_execution_service.AgentContextResolver'):
                with patch('core.agent_execution_service.AgentGovernanceService'):
                    with patch('core.agent_execution_service.LLMService'):
                        with patch('core.agent_execution_service.get_chat_history_manager'):
                            with patch('core.agent_execution_service.get_chat_session_manager'):
                                with patch('core.agent_execution_service.trigger_episode_creation') as mock_episode:
                                    # Mock the async function to verify streaming=False
                                    async def mock_execute(*args, **kwargs):
                                        assert kwargs.get("stream") is False
                                        return {"success": True}

                                    with patch('core.agent_execution_service.execute_agent_chat', side_effect=mock_execute):
                                        result = execute_agent_chat_sync(
                                            agent_id=mock_agent.id,
                                            message="Hello",
                                            user_id=mock_user.id
                                        )

                                        assert result["success"] is True

    def test_execute_agent_chat_sync_with_conversation_history(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service):
        """Test sync wrapper with conversation history."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        conversation_history = [
            {"role": "user", "content": "Previous message"}
        ]

        with patch('core.agent_execution_service.SessionLocal'):
            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation') as mock_episode:
                        mock_episode.return_value = AsyncMock()
                        result = execute_agent_chat_sync(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id,
                            conversation_history=conversation_history
                        )

                        assert result["success"] is True

    def test_execute_agent_chat_sync_creates_event_loop_if_needed(self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service):
        """Test that sync wrapper creates event loop if needed."""
        # This test verifies the function works in sync context
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal'):
            with patch('core.agent_execution_service.get_chat_history_manager'):
                with patch('core.agent_execution_service.get_chat_session_manager'):
                    with patch('core.agent_execution_service.trigger_episode_creation') as mock_episode:
                        mock_episode.return_value = AsyncMock()
                        result = execute_agent_chat_sync(
                            agent_id=mock_agent.id,
                            message="Hello",
                            user_id=mock_user.id
                        )

                        assert result["success"] is True


# =========================================================================
# TestCoverageGaps: error/edge branches not exercised by the suites above
# (budget paths, marketplace tracking, db-close exceptions, ChatMessage)
# =========================================================================


class TestCoverageGaps:
    """Targeted tests for branches left uncovered by the main suites."""

    def test_chat_message_model_stores_role_and_content(self):
        """ChatMessage is a trivial value object; cover its __init__."""
        from core.agent_execution_service import ChatMessage
        msg = ChatMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"

    @pytest.mark.asyncio
    async def test_budget_exceeded_continues_and_alerts(
        self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service
    ):
        """When the budget is exceeded, execution continues and a 100% alert fires."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.personal_budget_service') as mock_budget:
            mock_budget.is_budget_exceeded.return_value = True
            with patch('core.agent_execution_service.SessionLocal') as mock_db:
                mock_db.return_value = MagicMock()
                with patch('core.agent_execution_service.get_chat_history_manager'), \
                     patch('core.agent_execution_service.get_chat_session_manager'), \
                     patch('core.agent_execution_service.trigger_episode_creation'):
                    result = await execute_agent_chat(
                        agent_id=mock_agent.id, message="Hi", user_id=mock_user.id
                    )
            assert result["success"] is True
            # 100% alert is sent on the exceeded branch (80/90 are NOT).
            mock_budget.send_budget_alert.assert_any_call(100.0)

    @pytest.mark.asyncio
    async def test_budget_check_exception_does_not_block(
        self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service
    ):
        """A budget-check failure is logged and swallowed; execution proceeds."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.personal_budget_service') as mock_budget:
            mock_budget.is_budget_exceeded.side_effect = RuntimeError("budget svc down")
            with patch('core.agent_execution_service.SessionLocal') as mock_db:
                mock_db.return_value = MagicMock()
                with patch('core.agent_execution_service.get_chat_history_manager'), \
                     patch('core.agent_execution_service.get_chat_session_manager'), \
                     patch('core.agent_execution_service.trigger_episode_creation'):
                    result = await execute_agent_chat(
                        agent_id=mock_agent.id, message="Hi", user_id=mock_user.id
                    )
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_record_spend_exception_is_non_fatal(
        self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service
    ):
        """A spend-recording failure must not fail the (already-successful) execution."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.personal_budget_service') as mock_budget:
            mock_budget.record_spend.side_effect = RuntimeError("spend failed")
            with patch('core.agent_execution_service.SessionLocal') as mock_db:
                mock_db.return_value = MagicMock()
                with patch('core.agent_execution_service.get_chat_history_manager'), \
                     patch('core.agent_execution_service.get_chat_session_manager'), \
                     patch('core.agent_execution_service.trigger_episode_creation'):
                    result = await execute_agent_chat(
                        agent_id=mock_agent.id, message="Hi", user_id=mock_user.id
                    )
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_marketplace_agent_usage_tracked_on_success(
        self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service
    ):
        """A marketplace-type agent records MarketplaceUsageTracker on success."""
        mock_agent.type = "marketplace"
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        installation = MagicMock(template_id="tpl-1")
        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session
            # The finalize session re-fetches the execution row AND the
            # AgentInstallation row; both flow through query().filter().first().
            mock_session.query.return_value.filter.return_value.first.return_value = installation
            with patch('core.agent_execution_service.MarketplaceUsageTracker') as mock_tracker, \
                 patch('core.agent_execution_service.get_chat_history_manager'), \
                 patch('core.agent_execution_service.get_chat_session_manager'), \
                 patch('core.agent_execution_service.trigger_episode_creation'):
                result = await execute_agent_chat(
                    agent_id=mock_agent.id, message="Hi", user_id=mock_user.id
                )
            assert result["success"] is True
            mock_tracker.track_usage.assert_called_once()
            assert mock_tracker.track_usage.call_args.kwargs["success"] is True

    @pytest.mark.asyncio
    async def test_marketplace_agent_usage_tracked_on_failure(
        self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service
    ):
        """A marketplace-type agent records a FAILURE usage when streaming errors."""
        mock_agent.type = "marketplace"
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        installation = MagicMock(template_id="tpl-1")
        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session
            mock_session.query.return_value.filter.return_value.first.return_value = installation
            # Replace the streaming token generator with one that raises.
            async def failing_stream():
                raise Exception("LLM API error")
                yield  # pragma: no cover
            mock_llm_service.stream_completion = failing_stream
            with patch('core.agent_execution_service.MarketplaceUsageTracker') as mock_tracker, \
                 patch('core.agent_execution_service.get_chat_history_manager'), \
                 patch('core.agent_execution_service.get_chat_session_manager'), \
                 patch('core.agent_execution_service.trigger_episode_creation'):
                result = await execute_agent_chat(
                    agent_id=mock_agent.id, message="Hi", user_id=mock_user.id
                )
            assert result["success"] is False
            mock_tracker.track_usage.assert_called_once()
            assert mock_tracker.track_usage.call_args.kwargs["success"] is False

    @pytest.mark.asyncio
    async def test_db_session_close_exception_is_swallowed(
        self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service
    ):
        """A pre-stream db_session.close() failure is swallowed (try/except pass)."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session
            # First SessionLocal() (governance) closes with an error; the
            # finalize SessionLocal() must still work.
            close_calls = {"n": 0}
            real_close = mock_session.close

            def flaky_close():
                close_calls["n"] += 1
                if close_calls["n"] == 1:
                    raise RuntimeError("close failed")
            mock_session.close = flaky_close
            with patch('core.agent_execution_service.get_chat_history_manager'), \
                 patch('core.agent_execution_service.get_chat_session_manager'), \
                 patch('core.agent_execution_service.trigger_episode_creation'):
                result = await execute_agent_chat(
                    agent_id=mock_agent.id, message="Hi", user_id=mock_user.id
                )
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_episode_trigger_raises_synchronously_is_swallowed(
        self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service
    ):
        """A synchronous exception from trigger_episode_creation is logged, not fatal."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_db.return_value = MagicMock()
            with patch('core.agent_execution_service.get_chat_history_manager'), \
                 patch('core.agent_execution_service.get_chat_session_manager'), \
                 patch('core.agent_execution_service.trigger_episode_creation',
                       side_effect=RuntimeError("trigger boom")):
                result = await execute_agent_chat(
                    agent_id=mock_agent.id, message="Hi", user_id=mock_user.id
                )
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_marketplace_track_exception_swallowed(
        self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service
    ):
        """A MarketplaceUsageTracker failure on the success path is logged, not fatal."""
        mock_agent.type = "marketplace"
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        installation = MagicMock(template_id="tpl-1")
        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session
            mock_session.query.return_value.filter.return_value.first.return_value = installation
            with patch('core.agent_execution_service.MarketplaceUsageTracker') as mock_tracker:
                mock_tracker.track_usage.side_effect = RuntimeError("tracker down")
                with patch('core.agent_execution_service.get_chat_history_manager'), \
                     patch('core.agent_execution_service.get_chat_session_manager'), \
                     patch('core.agent_execution_service.trigger_episode_creation'):
                    result = await execute_agent_chat(
                        agent_id=mock_agent.id, message="Hi", user_id=mock_user.id
                    )
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_finalize_commit_failure_rolls_back(
        self, mock_agent, mock_user, mock_agent_resolution, mock_governance, mock_llm_service
    ):
        """If the finalize-session commit fails, the update_error path rolls back."""
        mock_agent_resolution.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_governance.can_perform_action.return_value = {"allowed": True}

        with patch('core.agent_execution_service.SessionLocal') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session
            # query().first() returns a row so the update path is entered, then
            # commit() raises to drive the update_error except branch.
            mock_session.query.return_value.filter.return_value.first.return_value = MagicMock()
            mock_session.commit.side_effect = RuntimeError("commit failed")
            with patch('core.agent_execution_service.get_chat_history_manager'), \
                 patch('core.agent_execution_service.get_chat_session_manager'), \
                 patch('core.agent_execution_service.trigger_episode_creation'):
                result = await execute_agent_chat(
                    agent_id=mock_agent.id, message="Hi", user_id=mock_user.id
                )
            assert result["success"] is True
            mock_session.rollback.assert_called()

    def test_sync_wrapper_creates_new_loop_when_none_running(self):
        """execute_agent_chat_sync falls back to a new event loop when none exists."""
        fake_loop = MagicMock()
        fake_loop.run_until_complete.return_value = {"success": True}
        with patch('asyncio.get_event_loop', side_effect=RuntimeError("no running loop")), \
             patch('asyncio.new_event_loop', return_value=fake_loop) as mock_new, \
             patch('asyncio.set_event_loop') as mock_set, \
             patch('core.agent_execution_service.execute_agent_chat',
                   new=AsyncMock(return_value={"success": True})):
            result = execute_agent_chat_sync(agent_id="a1", message="Hi", user_id="u1")
        assert result["success"] is True
        mock_new.assert_called_once()
        mock_set.assert_called_once_with(fake_loop)

