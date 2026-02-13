"""
Unit tests for Agent Context Resolver

Tests cover:
- Explicit agent_id resolution path
- Session-based agent resolution
- System default agent creation
- Session agent setting
- Resolution context metadata
- Error handling for missing entities
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.models import AgentRegistry, AgentStatus, ChatSession


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock(spec=Session)
    db.query = MagicMock()
    db.add = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.refresh = Mock()
    db.flush = Mock()
    return db


@pytest.fixture
def resolver(mock_db):
    """Create agent context resolver instance."""
    return AgentContextResolver(mock_db)


@pytest.fixture
def sample_agent():
    """Create sample agent."""
    return AgentRegistry(
        id="agent_123",
        name="Test Agent",
        category="testing",
        module_path="test.module",
        class_name="TestAgent",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.5
    )


@pytest.fixture
def sample_session():
    """Create sample chat session."""
    session = MagicMock(spec=ChatSession)
    session.id = "session_123"
    session.metadata_json = {"agent_id": "agent_123"}
    return session


@pytest.fixture
def system_default_agent():
    """Create system default agent."""
    return AgentRegistry(
        id="system_default",
        name="Chat Assistant",
        category="system",
        module_path="system",
        class_name="ChatAssistant",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.5
    )


# ============================================================================
# Explicit Agent Resolution Tests
# ============================================================================

class TestExplicitAgentResolution:
    """Tests for explicit agent_id resolution path."""

    @pytest.mark.asyncio
    async def test_resolve_with_explicit_agent_id(self, resolver, mock_db, sample_agent):
        """Test resolution via explicit agent_id."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            requested_agent_id="agent_123"
        )

        assert agent is not None
        assert agent.id == "agent_123"
        assert "explicit_agent_id" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_explicit_agent_found(self, resolver, mock_db, sample_agent):
        """Test explicit agent is found."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            requested_agent_id="agent_123"
        )

        assert agent.id == "agent_123"
        assert agent.name == "Test Agent"

    @pytest.mark.asyncio
    async def test_explicit_agent_not_found_continues_fallback(self, resolver, mock_db):
        """Test that non-existent explicit agent triggers fallback."""
        call_count = [0]

        def mock_filter_side_effect(*args, **kwargs):
            m = MagicMock()
            if call_count[0] < 2:
                m.first.return_value = None
            else:
                m.first.return_value = AgentRegistry(
                    id="system_default",
                    name="Chat Assistant",
                    category="system"
                )
            call_count[0] += 1
            return m

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            requested_agent_id="nonexistent_agent"
        )

        assert agent is not None
        assert "explicit_agent_id_not_found" in context["resolution_path"]


# ============================================================================
# Session Agent Resolution Tests
# ============================================================================

class TestSessionAgentResolution:
    """Tests for session-based agent resolution."""

    @pytest.mark.asyncio
    async def test_resolve_via_session_agent(self, resolver, mock_db, sample_session, sample_agent):
        """Test resolution via session agent."""
        call_count = [0]

        def mock_filter_side_effect(*args, **kwargs):
            m = MagicMock()
            if call_count[0] == 0:
                m.first.return_value = None
            elif call_count[0] == 1:
                m.first.return_value = sample_session
            else:
                m.first.return_value = sample_agent
            call_count[0] += 1
            return m

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            session_id="session_123"
        )

        assert agent is not None
        assert "session_agent" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_session_agent_found(self, resolver, mock_db, sample_session, sample_agent):
        """Test session agent is found."""
        call_count = [0]

        def mock_filter_side_effect(*args, **kwargs):
            m = MagicMock()
            if call_count[0] == 0:
                m.first.return_value = None
            elif call_count[0] == 1:
                m.first.return_value = sample_session
            else:
                m.first.return_value = sample_agent
            call_count[0] += 1
            return m

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            session_id="session_123"
        )

        assert agent is not None
        assert agent.id == "agent_123"

    @pytest.mark.asyncio
    async def test_session_without_agent_falls_back(self, resolver, mock_db):
        """Test session without agent_id falls back to system default."""
        session_no_agent = MagicMock(spec=ChatSession)
        session_no_agent.id = "session_123"
        session_no_agent.metadata_json = {}

        call_count = [0]

        def mock_filter_side_effect(*args, **kwargs):
            m = MagicMock()
            if call_count[0] == 0:
                m.first.return_value = None
            elif call_count[0] == 1:
                m.first.return_value = session_no_agent
            else:
                m.first.return_value = AgentRegistry(
                    id="system_default",
                    name="Chat Assistant",
                    category="system"
                )
            call_count[0] += 1
            return m

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            session_id="session_123"
        )

        assert agent is not None
        assert "no_session_agent" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_nonexistent_session_falls_back(self, resolver, mock_db, system_default_agent):
        """Test nonexistent session falls back to system default."""
        call_count = [0]

        def mock_filter_side_effect(*args, **kwargs):
            m = MagicMock()
            if call_count[0] < 2:
                m.first.return_value = None
            else:
                m.first.return_value = system_default_agent
            call_count[0] += 1
            return m

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            session_id="nonexistent_session"
        )

        assert agent is not None
        assert "system_default" in context["resolution_path"]


# ============================================================================
# System Default Resolution Tests
# ============================================================================

class TestSystemDefaultResolution:
    """Tests for system default agent resolution."""

    @pytest.mark.asyncio
    async def test_system_default_created_if_not_exists(self, resolver, mock_db):
        """Test system default agent is created if not exists."""
        call_count = [0]
        created_agent = None

        def mock_filter_side_effect(*args, **kwargs):
            nonlocal created_agent
            m = MagicMock()

            if call_count[0] < 2:
                m.first.return_value = None
            else:
                m.first.return_value = created_agent
            call_count[0] += 1
            return m

        def mock_add_side_effect(agent):
            nonlocal created_agent
            created_agent = agent

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect
        mock_db.add.side_effect = mock_add_side_effect

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123"
        )

        assert agent is not None
        assert agent.name == "Chat Assistant"
        assert agent.category == "system"
        assert "system_default" in context["resolution_path"]
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_existing_system_default_reused(self, resolver, mock_db):
        """Test existing system default agent is reused."""
        existing_default = AgentRegistry(
            id="existing_default",
            name="Chat Assistant",
            category="system"
        )

        call_count = [0]

        def mock_filter_side_effect(*args, **kwargs):
            m = MagicMock()
            if call_count[0] < 2:
                m.first.return_value = None
            else:
                m.first.return_value = existing_default
            call_count[0] += 1
            return m

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123"
        )

        assert agent.id == "existing_default"
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_system_default_has_configuration(self, resolver, mock_db):
        """Test system default agent has proper configuration."""
        call_count = [0]
        created_agent = None

        def mock_filter_side_effect(*args, **kwargs):
            nonlocal created_agent
            m = MagicMock()

            if call_count[0] < 2:
                m.first.return_value = None
            else:
                m.first.return_value = created_agent
            call_count[0] += 1
            return m

        def mock_add_side_effect(agent):
            nonlocal created_agent
            created_agent = agent

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect
        mock_db.add.side_effect = mock_add_side_effect

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123"
        )

        assert agent.module_path == "system"
        assert agent.class_name == "ChatAssistant"
        assert agent.status == AgentStatus.STUDENT.value
        assert agent.confidence_score == 0.5


# ============================================================================
# Resolution Failure Tests
# ============================================================================

class TestResolutionFailure:
    """Tests for resolution failure scenarios."""

    @pytest.mark.asyncio
    async def test_resolution_failed_when_all_paths_fail(self, resolver, mock_db):
        """Test resolution failure when all paths fail."""
        call_count = [0]

        def mock_filter_side_effect(*args, **kwargs):
            m = MagicMock()
            m.first.return_value = None
            call_count[0] += 1
            return m

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123"
        )

        assert agent is None
        assert "resolution_failed" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_resolution_failed_includes_error_context(self, resolver, mock_db):
        """Test resolution failure includes error context."""
        call_count = [0]

        def mock_filter_side_effect(*args, **kwargs):
            m = MagicMock()
            m.first.return_value = None
            call_count[0] += 1
            return m

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123"
        )

        assert context["user_id"] == "user_123"
        assert "resolution_failed" in context["resolution_path"]
        assert context["resolved_at"] is not None


# ============================================================================
# Set Session Agent Tests
# ============================================================================

class TestSetSessionAgent:
    """Tests for setting session agent."""

    def test_set_session_agent_success(self, resolver, mock_db, sample_session, sample_agent):
        """Test successfully setting agent on session."""
        call_count = [0]

        def mock_filter_side_effect(*args, **kwargs):
            m = MagicMock()
            if call_count[0] == 0:
                m.first.return_value = sample_session
            else:
                m.first.return_value = sample_agent
            call_count[0] += 1
            return m

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        result = resolver.set_session_agent("session_123", "agent_123")

        assert result is True
        assert sample_session.metadata_json["agent_id"] == "agent_123"
        mock_db.commit.assert_called()

    def test_set_agent_on_nonexistent_session(self, resolver, mock_db):
        """Test setting agent on non-existent session fails."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        result = resolver.set_session_agent("nonexistent_session", "agent_123")

        assert result is False

    def test_set_agent_with_nonexistent_agent_fails(self, resolver, mock_db, sample_session):
        """Test setting non-existent agent on session fails."""
        call_count = [0]

        def mock_filter_side_effect(*args, **kwargs):
            m = MagicMock()
            m.first.return_value = sample_session if call_count[0] == 0 else None
            call_count[0] += 1
            return m

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        result = resolver.set_session_agent("session_123", "nonexistent_agent")

        assert result is False

    def test_set_session_agent_updates_metadata(self, resolver, mock_db, sample_session):
        """Test setting session agent updates metadata."""
        original_metadata = {"previous_key": "previous_value"}
        sample_session.metadata_json = original_metadata.copy()

        call_count = [0]

        def mock_filter_side_effect(*args, **kwargs):
            m = MagicMock()
            m.first.return_value = sample_session
            call_count[0] += 1
            return m

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        resolver.set_session_agent("session_123", "agent_123")

        assert sample_session.metadata_json["agent_id"] == "agent_123"
        assert sample_session.metadata_json["previous_key"] == "previous_value"


# ============================================================================
# Resolution Context Tests
# ============================================================================

class TestResolutionContext:
    """Tests for resolution context metadata."""

    @pytest.mark.asyncio
    async def test_resolution_context_contains_all_fields(self, resolver, mock_db, sample_agent):
        """Test resolution context contains required fields."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            session_id="session_456",
            requested_agent_id="agent_123",
            action_type="chat"
        )

        assert context["user_id"] == "user_123"
        assert context["session_id"] == "session_456"
        assert context["requested_agent_id"] == "agent_123"
        assert context["action_type"] == "chat"
        assert "resolution_path" in context
        assert "resolved_at" in context

    @pytest.mark.asyncio
    async def test_resolution_path_tracks_fallback(self, resolver, mock_db):
        """Test resolution_path tracks all attempted fallbacks."""
        call_count = [0]

        def mock_filter_side_effect(*args, **kwargs):
            m = MagicMock()
            if call_count[0] < 2:
                m.first.return_value = None
            else:
                m.first.return_value = AgentRegistry(
                    id="system_default",
                    name="Chat Assistant",
                    category="system"
                )
            call_count[0] += 1
            return m

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            requested_agent_id="nonexistent"
        )

        assert len(context["resolution_path"]) > 0

    @pytest.mark.asyncio
    async def test_resolution_context_with_default_action_type(self, resolver, mock_db, sample_agent):
        """Test resolution context uses default action type."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123"
        )

        assert context["action_type"] == "chat"

    @pytest.mark.asyncio
    async def test_resolution_context_has_timestamp(self, resolver, mock_db, sample_agent):
        """Test resolution context includes timestamp."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123"
        )

        assert "resolved_at" in context
        assert context["resolved_at"] is not None


# ============================================================================
# Validate Agent for Action Tests
# ============================================================================

class TestValidateAgentForAction:
    """Tests for validating agents for specific actions."""

    @pytest.mark.asyncio
    async def test_validate_agent_for_action_delegates_to_governance(self, resolver, sample_agent):
        """Test validation delegates to governance service."""
        with patch.object(resolver.governance, 'can_perform_action', return_value={"allowed": True}):
            result = resolver.validate_agent_for_action(
                agent=sample_agent,
                action_type="search",
                require_approval=False
            )

            assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_validate_agent_passes_require_approval(self, resolver, sample_agent):
        """Test validation passes require_approval through."""
        with patch.object(resolver.governance, 'can_perform_action', return_value={"allowed": False, "requires_human_approval": True}):
            result = resolver.validate_agent_for_action(
                agent=sample_agent,
                action_type="delete",
                require_approval=True
            )

            assert result["requires_human_approval"] is True


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_get_agent_handles_exceptions(self, resolver, mock_db):
        """Test _get_agent handles database exceptions."""
        mock_query = MagicMock()
        mock_query.filter.side_effect = Exception("Database error")
        mock_db.query.return_value = mock_query

        result = resolver._get_agent("agent_123")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_session_agent_handles_exceptions(self, resolver, mock_db):
        """Test _get_session_agent handles exceptions."""
        mock_query = MagicMock()
        mock_query.filter.side_effect = Exception("Database error")
        mock_db.query.return_value = mock_query

        result = resolver._get_session_agent("session_123")

        assert result is None

    def test_set_session_agent_handles_exceptions(self, resolver, mock_db, sample_session):
        """Test set_session_agent handles exceptions."""
        mock_query = MagicMock()
        mock_query.filter.side_effect = Exception("Database error")
        mock_db.query.return_value = mock_query

        result = resolver.set_session_agent("session_123", "agent_123")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_or_create_system_default_handles_exceptions(self, resolver, mock_db):
        """Test _get_or_create_system_default handles exceptions."""
        mock_query = MagicMock()
        mock_query.filter.side_effect = Exception("Database error")
        mock_db.query.return_value = mock_query

        result = await resolver._get_or_create_system_default()

        assert result is None
