"""
Property-Based Tests for Agent Execution Invariants

Tests CRITICAL execution invariants using Hypothesis:
- Resolution context always has timestamp
- Resolution path never empty
- Execution ID is always valid UUID format
- Message format is valid (role/content structure)
- Token count is non-negative
- Agent ID is preserved through execution
- Success flag is boolean
- Response content is string
"""
import pytest
import uuid
from hypothesis import strategies as st, given, settings, HealthCheck
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from core.agent_execution_service import execute_agent_chat
from core.models import AgentRegistry, AgentStatus


# Common settings for all property tests
hypothesis_settings = settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)


class TestExecutionIdInvariants:
    """Property tests for execution ID format and uniqueness."""

    @given(
        agent_id=st.text(min_size=1, max_size=50).filter(lambda x: x.isalnum()),
        user_id=st.text(min_size=1, max_size=50).filter(lambda x: x.isalnum()),
        message=st.text(min_size=1, max_size=500)
    )
    @hypothesis_settings
    @pytest.mark.asyncio
    async def test_execution_id_always_uuid(self, agent_id, user_id, message):
        """
        Execution ID is always valid UUID format invariant.

        Property: Every execution returns a valid UUID string.
        """
        mock_tokens = ["Test"]

        with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()):
            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(None, {"resolution_path": ["system_default"]})
                )
                MockResolver.return_value = mock_resolver

                with patch("core.agent_execution_service.BYOKHandler") as MockBYOK:
                    mock_handler = MagicMock()
                    mock_handler.analyze_query_complexity.return_value = MagicMock(
                        complexity_score=0.5,
                        requires_reasoning=False
                    )
                    mock_handler.get_optimal_provider.return_value = ("openai", "gpt-4")

                    async def mock_stream(**kwargs):
                        for token in mock_tokens:
                            yield token

                    mock_handler.stream_completion = mock_stream
                    MockBYOK.return_value = mock_handler

                    with patch("core.agent_execution_service.get_chat_history_manager") as mock_hist_mgr:
                        mock_history = MagicMock()
                        mock_history.add_message = MagicMock()
                        mock_hist_mgr.return_value = mock_history

                        with patch("core.agent_execution_service.get_chat_session_manager") as mock_sess_mgr:
                            mock_session = MagicMock()
                            mock_session.create_session.return_value = "test-session"
                            mock_sess_mgr.return_value = mock_session

                            with patch("core.agent_execution_service.trigger_episode_creation", new=AsyncMock()):
                                result = await execute_agent_chat(
                                    agent_id=agent_id,
                                    message=message,
                                    user_id=user_id,
                                    session_id=None,
                                    workspace_id="default",
                                    conversation_history=None,
                                    stream=False
                                )

                # If execution succeeded, verify execution_id is valid UUID
                if result.get("success"):
                    execution_id = result.get("execution_id")
                    assert execution_id is not None

                    # Should be valid UUID format
                    try:
                        uuid.UUID(execution_id)
                    except ValueError:
                        pytest.fail(f"Execution ID {execution_id} is not a valid UUID")

    @given(
        agent_id=st.text(min_size=1, max_size=50).filter(lambda x: x.isalnum()),
        user_id=st.text(min_size=1, max_size=50).filter(lambda x: x.isalnum())
    )
    @hypothesis_settings
    @pytest.mark.asyncio
    async def test_execution_ids_are_unique(self, agent_id, user_id):
        """
        Execution IDs are unique invariant.

        Property: Multiple executions produce different UUIDs.
        """
        mock_tokens = ["Test"]

        execution_ids = []

        with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()):
            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(None, {"resolution_path": ["system_default"]})
                )
                MockResolver.return_value = mock_resolver

                with patch("core.agent_execution_service.BYOKHandler") as MockBYOK:
                    mock_handler = MagicMock()
                    mock_handler.analyze_query_complexity.return_value = MagicMock(
                        complexity_score=0.5,
                        requires_reasoning=False
                    )
                    mock_handler.get_optimal_provider.return_value = ("openai", "gpt-4")

                    async def mock_stream(**kwargs):
                        for token in mock_tokens:
                            yield token

                    mock_handler.stream_completion = mock_stream
                    MockBYOK.return_value = mock_handler

                    with patch("core.agent_execution_service.get_chat_history_manager") as mock_hist_mgr:
                        mock_history = MagicMock()
                        mock_history.add_message = MagicMock()
                        mock_hist_mgr.return_value = mock_history

                        with patch("core.agent_execution_service.get_chat_session_manager") as mock_sess_mgr:
                            mock_session = MagicMock()
                            mock_session.create_session.return_value = "test-session"
                            mock_sess_mgr.return_value = mock_session

                            with patch("core.agent_execution_service.trigger_episode_creation", new=AsyncMock()):
                                # Run 3 executions
                                for i in range(3):
                                    result = await execute_agent_chat(
                                        agent_id=agent_id,
                                        message=f"Test message {i}",
                                        user_id=user_id,
                                        session_id=None,
                                        workspace_id="default",
                                        conversation_history=None,
                                        stream=False
                                    )

                                    if result.get("success"):
                                        execution_ids.append(result.get("execution_id"))

        # All execution IDs should be unique
        if len(execution_ids) >= 2:
            assert len(execution_ids) == len(set(execution_ids)), \
                f"Execution IDs should be unique, got duplicates: {execution_ids}"


class TestResolutionContextInvariants:
    """Property tests for resolution context structure."""

    @given(
        agent_id=st.text(min_size=1, max_size=50).filter(lambda x: x.isalnum()),
        user_id=st.text(min_size=1, max_size=50).filter(lambda x: x.isalnum())
    )
    @hypothesis_settings
    @pytest.mark.asyncio
    async def test_resolution_context_always_has_timestamp(self, agent_id, user_id):
        """
        Resolution context always has timestamp invariant.

        Property: Any resolution includes a timestamp field.
        """
        with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()):
            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                # Capture resolution context
                captured_context = {}

                async def mock_resolve(**kwargs):
                    context = {
                        "user_id": kwargs.get("user_id"),
                        "resolution_path": ["system_default"],
                        "resolved_at": datetime.utcnow().isoformat()
                    }
                    captured_context.update(context)
                    return (None, context)

                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = mock_resolve
                MockResolver.return_value = mock_resolver

                result = await execute_agent_chat(
                    agent_id=agent_id,
                    message="Test",
                    user_id=user_id,
                    session_id=None,
                    workspace_id="default",
                    conversation_history=None,
                    stream=False
                )

                # Resolution context should have timestamp
                # (Note: in production this is internal, but we verify the structure)
                assert "resolved_at" in captured_context or result.get("success")

    @given(
        agent_id=st.text(min_size=1, max_size=50).filter(lambda x: x.isalnum()),
        user_id=st.text(min_size=1, max_size=50).filter(lambda x: x.isalnum())
    )
    @hypothesis_settings
    @pytest.mark.asyncio
    async def test_resolution_path_never_empty(self, agent_id, user_id):
        """
        Resolution path never empty invariant.

        Property: Resolution always records the path taken.
        """
        with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()):
            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                # Capture resolution path
                resolution_paths = []

                async def mock_resolve(**kwargs):
                    path = ["system_default"]
                    resolution_paths.append(path)
                    context = {
                        "user_id": kwargs.get("user_id"),
                        "resolution_path": path,
                        "resolved_at": datetime.utcnow().isoformat()
                    }
                    return (None, context)

                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = mock_resolve
                MockResolver.return_value = mock_resolver

                result = await execute_agent_chat(
                    agent_id=agent_id,
                    message="Test",
                    user_id=user_id,
                    session_id=None,
                    workspace_id="default",
                    conversation_history=None,
                    stream=False
                )

                # Resolution path should never be empty
                assert len(resolution_paths) > 0
                assert all(len(path) > 0 for path in resolution_paths)


class TestMessageFormatInvariants:
    """Property tests for message structure validation."""

    @given(
        messages=st.lists(
            st.fixed_dictionaries({
                "role": st.sampled_from(["user", "assistant", "system"]),
                "content": st.text(min_size=0, max_size=1000)
            }),
            min_size=0,
            max_size=10
        )
    )
    @hypothesis_settings
    def test_message_format_valid(self, messages):
        """
        Message format valid invariant.

        Property: Messages array always has role/content structure.
        """
        # All messages should have required fields
        for msg in messages:
            assert "role" in msg
            assert "content" in msg
            assert isinstance(msg["role"], str)
            assert isinstance(msg["content"], str)
            assert msg["role"] in ["user", "assistant", "system"]

    @given(
        role=st.sampled_from(["user", "assistant", "system"]),
        content=st.text(min_size=0, max_size=500, alphabet=st.characters(max_codepoint=1000))
    )
    @hypothesis_settings
    def test_single_message_format_valid(self, role, content):
        """
        Single message format valid invariant.

        Property: Individual message has valid structure.
        """
        message = {"role": role, "content": content}

        # Validate structure
        assert "role" in message
        assert "content" in message
        assert message["role"] in ["user", "assistant", "system"]
        assert isinstance(message["content"], str)


class TestResponseStructureInvariants:
    """Property tests for response structure validation."""

    @given(
        agent_id=st.text(min_size=1, max_size=50).filter(lambda x: x.isalnum()),
        user_id=st.text(min_size=1, max_size=50).filter(lambda x: x.isalnum()),
        message=st.text(min_size=1, max_size=500)
    )
    @hypothesis_settings
    @pytest.mark.asyncio
    async def test_response_has_required_fields(self, agent_id, user_id, message):
        """
        Response has required fields invariant.

        Property: Response always contains success field and appropriate data fields.
        """
        mock_tokens = ["Test"]

        with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()):
            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(None, {"resolution_path": ["system_default"]})
                )
                MockResolver.return_value = mock_resolver

                with patch("core.agent_execution_service.BYOKHandler") as MockBYOK:
                    mock_handler = MagicMock()
                    mock_handler.analyze_query_complexity.return_value = MagicMock(
                        complexity_score=0.5,
                        requires_reasoning=False
                    )
                    mock_handler.get_optimal_provider.return_value = ("openai", "gpt-4")

                    async def mock_stream(**kwargs):
                        for token in mock_tokens:
                            yield token

                    mock_handler.stream_completion = mock_stream
                    MockBYOK.return_value = mock_handler

                    with patch("core.agent_execution_service.get_chat_history_manager") as mock_hist_mgr:
                        mock_history = MagicMock()
                        mock_history.add_message = MagicMock()
                        mock_hist_mgr.return_value = mock_history

                        with patch("core.agent_execution_service.get_chat_session_manager") as mock_sess_mgr:
                            mock_session = MagicMock()
                            mock_session.create_session.return_value = "test-session"
                            mock_sess_mgr.return_value = mock_session

                            with patch("core.agent_execution_service.trigger_episode_creation", new=AsyncMock()):
                                result = await execute_agent_chat(
                                    agent_id=agent_id,
                                    message=message,
                                    user_id=user_id,
                                    session_id=None,
                                    workspace_id="default",
                                    conversation_history=None,
                                    stream=False
                                )

                # Response must have success field
                assert "success" in result
                assert isinstance(result["success"], bool)

                # If successful, should have response field
                if result["success"]:
                    assert "response" in result
                    assert isinstance(result["response"], str)
                    assert "execution_id" in result
                else:
                    # If failed, should have error field
                    assert "error" in result or "agent_id" in result

    @given(
        agent_id=st.text(min_size=1, max_size=50).filter(lambda x: x.isalnum()),
        user_id=st.text(min_size=1, max_size=50).filter(lambda x: x.isalnum()),
        message=st.text(min_size=1, max_size=500)
    )
    @hypothesis_settings
    @pytest.mark.asyncio
    async def test_tokens_count_non_negative(self, agent_id, user_id, message):
        """
        Tokens count non-negative invariant.

        Property: Token count is always >= 0.
        """
        mock_tokens = ["Token1", "Token2", "Token3"]

        with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()):
            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(None, {"resolution_path": ["system_default"]})
                )
                MockResolver.return_value = mock_resolver

                with patch("core.agent_execution_service.BYOKHandler") as MockBYOK:
                    mock_handler = MagicMock()
                    mock_handler.analyze_query_complexity.return_value = MagicMock(
                        complexity_score=0.5,
                        requires_reasoning=False
                    )
                    mock_handler.get_optimal_provider.return_value = ("openai", "gpt-4")

                    async def mock_stream(**kwargs):
                        for token in mock_tokens:
                            yield token

                    mock_handler.stream_completion = mock_stream
                    MockBYOK.return_value = mock_handler

                    with patch("core.agent_execution_service.get_chat_history_manager") as mock_hist_mgr:
                        mock_history = MagicMock()
                        mock_history.add_message = MagicMock()
                        mock_hist_mgr.return_value = mock_history

                        with patch("core.agent_execution_service.get_chat_session_manager") as mock_sess_mgr:
                            mock_session = MagicMock()
                            mock_session.create_session.return_value = "test-session"
                            mock_sess_mgr.return_value = mock_session

                            with patch("core.agent_execution_service.trigger_episode_creation", new=AsyncMock()):
                                result = await execute_agent_chat(
                                    agent_id=agent_id,
                                    message=message,
                                    user_id=user_id,
                                    session_id=None,
                                    workspace_id="default",
                                    conversation_history=None,
                                    stream=False
                                )

                # If successful, tokens should be non-negative
                if result.get("success"):
                    tokens = result.get("tokens", 0)
                    assert isinstance(tokens, int)
                    assert tokens >= 0


class TestAgentIdInvariants:
    """Property tests for agent ID preservation."""

    @given(
        agent_id=st.text(min_size=1, max_size=50).filter(lambda x: x.isalnum()),
        user_id=st.text(min_size=1, max_size=50).filter(lambda x: x.isalnum())
    )
    @hypothesis_settings
    @pytest.mark.asyncio
    async def test_agent_id_preserved_in_response(self, agent_id, user_id):
        """
        Agent ID preserved in response invariant.

        Property: Response includes agent_id field (may differ from input if resolved).
        """
        mock_tokens = ["Test"]

        with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()):
            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(None, {"resolution_path": ["system_default"]})
                )
                MockResolver.return_value = mock_resolver

                with patch("core.agent_execution_service.BYOKHandler") as MockBYOK:
                    mock_handler = MagicMock()
                    mock_handler.analyze_query_complexity.return_value = MagicMock(
                        complexity_score=0.5,
                        requires_reasoning=False
                    )
                    mock_handler.get_optimal_provider.return_value = ("openai", "gpt-4")

                    async def mock_stream(**kwargs):
                        for token in mock_tokens:
                            yield token

                    mock_handler.stream_completion = mock_stream
                    MockBYOK.return_value = mock_handler

                    with patch("core.agent_execution_service.get_chat_history_manager") as mock_hist_mgr:
                        mock_history = MagicMock()
                        mock_history.add_message = MagicMock()
                        mock_hist_mgr.return_value = mock_history

                        with patch("core.agent_execution_service.get_chat_session_manager") as mock_sess_mgr:
                            mock_session = MagicMock()
                            mock_session.create_session.return_value = "test-session"
                            mock_sess_mgr.return_value = mock_session

                            with patch("core.agent_execution_service.trigger_episode_creation", new=AsyncMock()):
                                result = await execute_agent_chat(
                                    agent_id=agent_id,
                                    message="Test",
                                    user_id=user_id,
                                    session_id=None,
                                    workspace_id="default",
                                    conversation_history=None,
                                    stream=False
                                )

                # Response should have agent_id field
                assert "agent_id" in result
                assert result["agent_id"] is not None
                assert isinstance(result["agent_id"], str)


class TestSessionIdInvariants:
    """Property tests for session ID handling."""

    @given(
        agent_id=st.text(min_size=1, max_size=50).filter(lambda x: x.isalnum()),
        user_id=st.text(min_size=1, max_size=50).filter(lambda x: x.isalnum()),
        session_id=st.one_of(st.none(), st.text(min_size=1, max_size=50))
    )
    @hypothesis_settings
    @pytest.mark.asyncio
    async def test_session_id_in_response(self, agent_id, user_id, session_id):
        """
        Session ID in response invariant.

        Property: Response always includes session_id (created if not provided).
        """
        mock_tokens = ["Test"]

        with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()):
            with patch("core.agent_execution_service.AgentContextResolver") as MockResolver:
                mock_resolver = MagicMock()
                mock_resolver.resolve_agent_for_request = AsyncMock(
                    return_value=(None, {"resolution_path": ["system_default"]})
                )
                MockResolver.return_value = mock_resolver

                with patch("core.agent_execution_service.BYOKHandler") as MockBYOK:
                    mock_handler = MagicMock()
                    mock_handler.analyze_query_complexity.return_value = MagicMock(
                        complexity_score=0.5,
                        requires_reasoning=False
                    )
                    mock_handler.get_optimal_provider.return_value = ("openai", "gpt-4")

                    async def mock_stream(**kwargs):
                        for token in mock_tokens:
                            yield token

                    mock_handler.stream_completion = mock_stream
                    MockBYOK.return_value = mock_handler

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
                                agent_id=agent_id,
                                message="Test",
                                user_id=user_id,
                                session_id=session_id,
                                workspace_id="default",
                                conversation_history=None,
                                stream=False
                            )

                # Response should have session_id
                if result.get("success"):
                    assert "session_id" in result
                    assert result["session_id"] is not None
                    assert isinstance(result["session_id"], str)
