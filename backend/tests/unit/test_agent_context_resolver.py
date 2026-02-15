"""
Unit tests for Agent Context Resolver

Tests cover:
- Explicit agent_id resolution path
- Session-based agent resolution
- System default agent creation
- Session agent setting
- Resolution context metadata
- Error handling for missing entities

Total: 30 tests
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call
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
# Explicit Agent Resolution Tests (4 tests)
# ============================================================================

class TestExplicitAgentResolution:
    """Tests for explicit agent_id resolution path."""

    @pytest.mark.asyncio
    async def test_resolve_with_explicit_agent_id(self, resolver, mock_db, sample_agent):
        """Test resolution via explicit agent_id."""
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_first = MagicMock()
        mock_first.return_value = sample_agent
        mock_filter.first = mock_first
        mock_query.filter = mock_filter
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
        mock_filter = MagicMock()
        mock_first = MagicMock()
        mock_first.return_value = sample_agent
        mock_filter.first = mock_first
        mock_query.filter = mock_filter
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
        system_agent = AgentRegistry(
            id="system_default",
            name="Chat Assistant",
            category="system"
        )

        mock_query_1 = MagicMock()
        mock_filter1 = MagicMock()
        mock_first_1 = MagicMock()
        mock_first1.return_value = None
        mock_filter1.first = mock_first1
        mock_query1.filter = mock_filter1
        mock_db.query.return_value = mock_query1

        mock_query_2 = MagicMock()
        mock_filter2 = MagicMock()
        mock_first2 = MagicMock()
        mock_first2.return_value = system_agent
        mock_filter2.first = mock_first2
        mock_query2.filter = mock_filter2
        mock_db.query.return_value = mock_query2

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            requested_agent_id="nonexistent_agent"
        )

        assert agent is not None
        assert "explicit_agent_id_not_found" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_explicit_agent_skips_session_lookup(self, resolver, mock_db, sample_agent):
        """Test explicit agent bypasses session agent lookup."""
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_first = MagicMock()
        mock_first.return_value = sample_agent
        mock_filter.first = mock_first
        mock_query.filter = mock_filter
        mock_db.query.return_value = mock_query

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            session_id="session_123",
            requested_agent_id="agent_123"
        )

        assert agent.id == "agent_123"
        assert "explicit_agent_id" in context["resolution_path"]
        assert "session_agent" not in context["resolution_path"]


# ============================================================================
# Session Agent Resolution Tests (5 tests)
# ============================================================================

class TestSessionAgentResolution:
    """Tests for session-based agent resolution."""

    @pytest.mark.asyncio
    async def test_resolve_via_session_agent(self, resolver, mock_db, sample_agent, sample_session):
        """Test resolution via session agent."""
        mock_query1 = MagicMock()
        mock_filter1 = MagicMock()
        mock_first1 = MagicMock()
        mock_first1.return_value = None
        mock_filter1.first = mock_first1
        mock_query1.filter = mock_filter1
        mock_db.query.return_value = mock_query1

        mock_query2 = MagicMock()
        mock_filter2 = MagicMock()
        mock_first2 = MagicMock()
        mock_first2.return_value = sample_session
        mock_filter2.first = mock_first2
        mock_query2.filter = mock_filter2
        mock_db.query.return_value = mock_query2

        mock_query3 = MagicMock()
        mock_filter3 = MagicMock()
        mock_first3 = MagicMock()
        mock_first3.return_value = sample_agent
        mock_filter3.first = mock_first3
        mock_query3.filter = mock_filter3
        mock_db.query.return_value = mock_query3

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            session_id="session_123"
        )

        assert agent is not None
        assert "session_agent" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_session_agent_found(self, resolver, mock_db, sample_agent, sample_session):
        """Test session agent is found."""
        mock_query1 = MagicMock()
        mock_filter1 = MagicMock()
        mock_first1 = MagicMock()
        mock_first1.return_value = None
        mock_filter1.first = mock_first1
        mock_query1.filter = mock_filter1
        mock_db.query.return_value = mock_query1

        mock_query2 = MagicMock()
        mock_filter2 = MagicMock()
        mock_first2 = MagicMock()
        mock_first2.return_value = sample_session
        mock_filter2.first = mock_first2
        mock_query2.filter = mock_filter2
        mock_db.query.return_value = mock_query2

        mock_query3 = MagicMock()
        mock_filter3 = MagicMock()
        mock_first3 = MagicMock()
        mock_first3.return_value = sample_agent
        mock_filter3.first = mock_first3
        mock_query3.filter = mock_filter3
        mock_db.query.return_value = mock_query3

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

        system_agent = AgentRegistry(
            id="system_default",
            name="Chat Assistant",
            category="system"
        )

        mock_query1 = MagicMock()
        mock_filter1 = MagicMock()
        mock_first1 = MagicMock()
        mock_first1.return_value = None
        mock_filter1.first = mock_first1
        mock_query1.filter = mock_filter1
        mock_db.query.return_value = mock_query1

        mock_query2 = MagicMock()
        mock_filter2 = MagicMock()
        mock_first2 = MagicMock()
        mock_first2.return_value = session_no_agent
        mock_filter2.first = mock_first2
        mock_query2.filter = mock_filter2
        mock_db.query.return_value = mock_query2

        mock_query3 = MagicMock()
        mock_filter3 = MagicMock()
        mock_first3 = MagicMock()
        mock_first3.return_value = system_agent
        mock_filter3.first = mock_first3
        mock_query3.filter = mock_filter3
        mock_db.query.return_value = mock_query3

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            session_id="session_123"
        )

        assert agent is not None
        assert "no_session_agent" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_nonexistent_session_falls_back(self, resolver, mock_db, system_default_agent):
        """Test nonexistent session falls back to system default."""
        mock_query1 = MagicMock()
        mock_filter1 = MagicMock()
        mock_first1 = MagicMock()
        mock_first1.return_value = None
        mock_filter1.first = mock_first1
        mock_query1.filter = mock_filter1
        mock_db.query.return_value = mock_query1

        mock_query2 = MagicMock()
        mock_filter2 = MagicMock()
        mock_first2 = MagicMock()
        mock_first2.return_value = None
        mock_filter2.first = mock_first2
        mock_query2.filter = mock_filter2
        mock_db.query.return_value = mock_query2

        mock_query3 = MagicMock()
        mock_filter3 = MagicMock()
        mock_first3 = MagicMock()
        mock_first3.return_value = system_default_agent
        mock_filter3.first = mock_first3
        mock_query3.filter = mock_filter3
        mock_db.query.return_value = mock_query3

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            session_id="nonexistent_session"
        )

        assert agent is not None
        assert "system_default" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_session_metadata_none_falls_back(self, resolver, mock_db):
        """Test session with None metadata_json falls back to system default."""
        session_none_metadata = MagicMock(spec=ChatSession)
        session_none_metadata.id = "session_123"
        session_none_metadata.metadata_json = None

        system_agent = AgentRegistry(
            id="system_default",
            name="Chat Assistant",
            category="system"
        )

        mock_query1 = MagicMock()
        mock_filter1 = MagicMock()
        mock_first1 = MagicMock()
        mock_first1.return_value = None
        mock_filter1.first = mock_first1
        mock_query1.filter = mock_filter1
        mock_db.query.return_value = mock_query1

        mock_query2 = MagicMock()
        mock_filter2 = MagicMock()
        mock_first2 = MagicMock()
        mock_first2.return_value = session_none_metadata
        mock_filter2.first = mock_first2
        mock_query2.filter = mock_filter2
        mock_db.query.return_value = mock_query2

        mock_query3 = MagicMock()
        mock_filter3 = MagicMock()
        mock_first3 = MagicMock()
        mock_first3.return_value = system_agent
        mock_filter3.first = mock_first3
        mock_query3.filter = mock_filter3
        mock_db.query.return_value = mock_query3

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            session_id="session_123"
        )

        assert agent is not None
        assert "system_default" in context["resolution_path"]


# ============================================================================
# System Default Resolution Tests (4 tests)
# ============================================================================

class TestSystemDefaultResolution:
    """Tests for system default agent resolution."""

    @pytest.mark.asyncio
    async def test_system_default_created_if_not_exists(self, resolver, mock_db):
        """Test system default agent is created if not exists."""
        created_agent = [None]

        def mock_add_func(agent):
            created_agent[0] = agent

        mock_query1 = MagicMock()
        mock_filter1 = MagicMock()
        mock_first1 = MagicMock()

        def mock_first_side_effect():
            nonlocal created_agent
            if created_agent[0]:
                return created_agent[0]
            else:
                return None

        mock_first1.side_effect = mock_first_side_effect

        mock_filter1.first = mock_first1
        mock_query1.filter = mock_filter1
        mock_db.query.return_value = mock_query1

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123"
        )

        assert agent is not None
        assert agent.name == "Chat Assistant"
        assert agent.category == "system"
        assert "system_default" in context["resolution_path"]
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_existing_system_default_reused(self, resolver, mock_db):
        """Test existing system default agent is reused."""
        existing_default = AgentRegistry(
            id="existing_default",
            name="Chat Assistant",
            category="system"
        )

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_first = MagicMock()
        mock_first.return_value = existing_default
        mock_filter.first = mock_first
        mock_query.filter = mock_filter
        mock_db.query.return_value = mock_query

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123"
        )

        assert agent.id == "existing_default"
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_system_default_has_configuration(self, resolver, mock_db):
        """Test system default agent has proper configuration."""
        created_agent = [None]

        def mock_add_func(agent):
            created_agent[0] = agent

        mock_query1 = MagicMock()
        mock_filter1 = MagicMock()
        mock_first1 = MagicMock()

        def mock_first_side_effect():
            nonlocal created_agent
            if created_agent[0]:
                return created_agent[0]
            else:
                return None

        mock_first1.side_effect = mock_first_side_effect

        mock_filter1.first = mock_first1
        mock_query1.filter = mock_filter1
        mock_db.query.return_value = mock_query1

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123"
        )

        assert agent.module_path == "system"
        assert agent.class_name == "ChatAssistant"
        assert agent.status == AgentStatus.STUDENT.value
        assert agent.confidence_score == 0.5

    @pytest.mark.asyncio
    async def test_system_default_has_capabilities(self, resolver, mock_db):
        """Test system default agent has capabilities configured."""
        created_agent = [None]

        def mock_add_func(agent):
            created_agent[0] = agent

        mock_query1 = MagicMock()
        mock_filter1 = MagicMock()
        mock_first1 = MagicMock()

        def mock_first_side_effect():
            nonlocal created_agent
            if created_agent[0]:
                return created_agent[0]
            else:
                return None

        mock_first1.side_effect = mock_first_side_effect

        mock_filter1.first = mock_first1
        mock_query1.filter = mock_filter1
        mock_db.query.return_value = mock_query1

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123"
        )

        assert "configuration" in agent.__dict__
        assert agent.configuration is not None
        assert "system_prompt" in agent.configuration
        assert "capabilities" in agent.configuration


# ============================================================================
# Resolution Failure Tests (3 tests)
# ============================================================================

class TestResolutionFailure:
    """Tests for resolution failure scenarios."""

    @pytest.mark.asyncio
    async def test_resolution_failed_when_create_fails(self, resolver, mock_db):
        """Test resolution failure when system default creation fails."""
        mock_query1 = MagicMock()
        mock_filter1 = MagicMock()
        mock_first1 = MagicMock()

        def mock_first_side_effect():
            return None

        mock_first1.side_effect = mock_first_side_effect

        mock_filter1.first = mock_first1
        mock_query1.filter = mock_filter1
        mock_db.query.return_value = mock_query1

        mock_db.commit.side_effect = Exception("Commit failed")

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123"
        )

        assert agent is None
        assert "resolution_failed" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_resolution_failed_includes_error_context(self, resolver, mock_db):
        """Test resolution failure includes error context."""
        mock_query1 = MagicMock()
        mock_filter1 = MagicMock()
        mock_first1 = MagicMock()

        def mock_first_side_effect():
            return None

        mock_first1.side_effect = mock_first_side_effect

        mock_filter1.first = mock_first1
        mock_query1.filter = mock_filter1
        mock_db.query.return_value = mock_query1

        mock_db.commit.side_effect = Exception("Commit failed")

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123"
        )

        assert context["user_id"] == "user_123"
        assert "resolution_failed" in context["resolution_path"]
        assert context["resolved_at"] is not None

    @pytest.mark.asyncio
    async def test_resolution_failure_with_session_falls_back_to_default(self, resolver, mock_db):
        """Test resolution with nonexistent session falls back to system default."""
        system_agent = AgentRegistry(
            id="system_default",
            name="Chat Assistant",
            category="system"
        )

        mock_query1 = MagicMock()
        mock_filter1 = MagicMock()
        mock_first1 = MagicMock()

        call_count = 0

        def mock_first_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return None
            else:
                return system_agent

        mock_first1 = MagicMock(side_effect=mock_first_side_effect)

        mock_filter1.first = mock_first1
        mock_query1.filter = mock_filter1
        mock_db.query.return_value = mock_query1

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            session_id="nonexistent_session"
        )

        assert agent is not None
        assert "system_default" in context["resolution_path"]


# ============================================================================
# Set Session Agent Tests (5 tests)
# ============================================================================

class TestSetSessionAgent:
    """Tests for setting session agent."""

    def test_set_session_agent_success(self, resolver, mock_db, sample_session, sample_agent):
        """Test successfully setting agent on session."""
        mock_query1 = MagicMock()
        mock_filter1 = MagicMock()
        mock_first1 = MagicMock()
        mock_first1.return_value = sample_session
        mock_filter1.first = mock_first1
        mock_query1.filter = mock_filter1
        mock_db.query.return_value = mock_query1

        mock_query2 = MagicMock()
        mock_filter2 = MagicMock()
        mock_first2 = MagicMock()
        mock_first2.return_value = sample_agent
        mock_filter2.first = mock_first2
        mock_query2.filter = mock_filter2
        mock_db.query.return_value = mock_query2

        result = resolver.set_session_agent("session_123", "agent_123")

        assert result is True
        assert sample_session.metadata_json["agent_id"] == "agent_123"
        mock_db.commit.assert_called_once()

    def test_set_agent_on_nonexistent_session(self, resolver, mock_db):
        """Test setting agent on non-existent session fails."""
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_first = MagicMock()
        mock_first.return_value = None
        mock_filter.first = mock_first
        mock_query.filter = mock_filter
        mock_db.query.return_value = mock_query

        result = resolver.set_session_agent("nonexistent_session", "agent_123")

        assert result is False

    def test_set_agent_with_nonexistent_agent_fails(self, resolver, mock_db, sample_session):
        """Test setting non-existent agent on session fails."""
        mock_query1 = MagicMock()
        mock_filter1 = MagicMock()
        mock_first1 = MagicMock()
        mock_first1.return_value = sample_session
        mock_filter1.first = mock_first1
        mock_query1.filter = mock_filter1
        mock_db.query.return_value = mock_query1

        mock_query2 = MagicMock()
        mock_filter2 = MagicMock()
        mock_first2 = MagicMock()
        mock_first2.return_value = None
        mock_filter2.first = mock_first2
        mock_query2.filter = mock_filter2
        mock_db.query.return_value = mock_query2

        result = resolver.set_session_agent("session_123", "nonexistent_agent")

        assert result is False

    def test_set_session_agent_updates_metadata(self, resolver, mock_db, sample_session):
        """Test setting session agent updates metadata."""
        original_metadata = {"previous_key": "previous_value"}
        sample_session.metadata_json = original_metadata.copy()

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_first = MagicMock()
        mock_first.return_value = sample_session
        mock_filter.first = mock_first
        mock_query.filter = mock_filter
        mock_db.query.return_value = mock_query

        resolver.set_session_agent("session_123", "agent_123")

        assert sample_session.metadata_json["agent_id"] == "agent_123"
        assert sample_session.metadata_json["previous_key"] == "previous_value"

    def test_set_session_agent_creates_metadata_if_none(self, resolver, mock_db):
        """Test setting session agent creates metadata if None."""
        session_no_metadata = MagicMock(spec=ChatSession)
        session_no_metadata.id = "session_123"
        session_no_metadata.metadata_json = None

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_first = MagicMock()
        mock_first.return_value = session_no_metadata
        mock_filter.first = mock_first
        mock_query.filter = mock_filter
        mock_db.query.return_value = mock_query

        resolver.set_session_agent("session_123", "agent_123")

        assert session_no_metadata.metadata_json is not None
        assert session_no_metadata.metadata_json["agent_id"] == "agent_123"


# ============================================================================
# Resolution Context Tests (6 tests)
# ============================================================================

class TestResolutionContext:
    """Tests for resolution context metadata."""

    @pytest.mark.asyncio
    async def test_resolution_context_contains_all_fields(self, resolver, mock_db, sample_agent):
        """Test resolution context contains required fields."""
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_first = MagicMock()
        mock_first.return_value = sample_agent
        mock_filter.first = mock_first
        mock_query.filter = mock_filter
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
        system_agent = AgentRegistry(
            id="system_default",
            name="Chat Assistant",
            category="system"
        )

        mock_query1 = MagicMock()
        mock_filter1 = MagicMock()
        mock_first1 = MagicMock()
        mock_first1.return_value = None
        mock_filter1.first = mock_first1
        mock_query1.filter = mock_filter1
        mock_db.query.return_value = mock_query1

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            requested_agent_id="nonexistent"
        )

        assert len(context["resolution_path"]) > 0

    @pytest.mark.asyncio
    async def test_resolution_context_with_default_action_type(self, resolver, mock_db, sample_agent):
        """Test resolution context uses default action type."""
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_first = MagicMock()
        mock_first.return_value = sample_agent
        mock_filter.first = mock_first
        mock_query.filter = mock_filter
        mock_db.query.return_value = mock_query

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123"
        )

        assert context["action_type"] == "chat"

    @pytest.mark.asyncio
    async def test_resolution_context_has_timestamp(self, resolver, mock_db, sample_agent):
        """Test resolution context includes timestamp."""
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_first = MagicMock()
        mock_first.return_value = sample_agent
        mock_filter.first = mock_first
        mock_query.filter = mock_filter
        mock_db.query.return_value = mock_query

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123"
        )

        assert "resolved_at" in context
        assert context["resolved_at"] is not None

    @pytest.mark.asyncio
    async def test_resolution_context_includes_null_session_id(self, resolver, mock_db, sample_agent):
        """Test resolution context handles null session_id."""
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter = MagicMock()
        mock_first.return_value = sample_agent
        mock_filter.first = mock_first
        mock_query.filter = mock_filter
        mock_db.query.return_value = mock_query

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            session_id=None
        )

        assert context["session_id"] is None

    @pytest.mark.asyncio
    async def test_resolution_context_timestamp_format(self, resolver, mock_db, sample_agent):
        """Test resolution context timestamp is ISO format."""
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_first = MagicMock()
        mock_first.return_value = sample_agent
        mock_filter.first = mock_first
        mock_query.filter = mock_filter
        mock_db.query.return_value = mock_query

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123"
        )

        assert "resolved_at" in context
        # Should be ISO format with 'T' separator
        assert "T" in context["resolved_at"]


# ============================================================================
# Validate Agent for Action Tests (3 tests)
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

    @pytest.mark.asyncio
    async def test_validate_agent_passes_agent_id(self, resolver, sample_agent):
        """Test validation passes agent_id to governance."""
        with patch.object(resolver.governance, 'can_perform_action', return_value={"allowed": True}) as mock_gov:
            resolver.validate_agent_for_action(
                agent=sample_agent,
                action_type="search",
                require_approval=False
            )

            mock_gov.assert_called_once_with(
                agent_id=sample_agent.id,
                action_type="search",
                require_approval=False
            )


# ============================================================================
# Error Handling Tests (5 tests)
# ============================================================================

class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_get_agent_handles_exceptions(self, resolver, mock_db):
        """Test _get_agent handles database exceptions."""
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.side_effect = Exception("Database error")
        mock_query.filter = mock_filter
        mock_db.query.return_value = mock_query

        result = resolver._get_agent("agent_123")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_session_agent_handles_exceptions(self, resolver, mock_db):
        """Test _get_session_agent handles exceptions."""
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.side_effect = Exception("Database error")
        mock_query.filter = mock_filter
        mock_db.query.return_value = mock_query

        result = resolver._get_session_agent("session_123")

        assert result is None

    def test_set_session_agent_handles_exceptions(self, resolver, mock_db):
        """Test set_session_agent handles exceptions."""
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.filter.side_effect = Exception("Database error")
        mock_query.filter = mock_filter
        mock_db.query.return_value = mock_query

        result = resolver.set_session_agent("session_123", "agent_123")

        assert result is False

    def test_get_or_create_system_default_handles_exceptions(self, resolver, mock_db):
        """Test _get_or_create_system_default handles exceptions."""
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.side_effect = Exception("Database error")
        mock_query.filter = mock_filter
        mock_db.query.return_value = mock_query

        result = resolver._get_or_create_system_default()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_session_agent_with_invalid_agent_id(self, resolver, mock_db):
        """Test _get_session_agent with session pointing to invalid agent."""
        session_with_invalid_agent = MagicMock(spec=ChatSession)
        session_with_invalid_agent.id = "session_123"
        session_with_invalid_agent.metadata_json = {"agent_id": "invalid_agent"}

        mock_query1 = MagicMock()
        mock_filter1 = MagicMock()
        mock_first1 = MagicMock()
        mock_first1.return_value = session_with_invalid_agent
        mock_filter1.first = mock_first1
        mock_query1.filter = mock_filter1
        mock_db.query.return_value = mock_query1

        mock_query2 = MagicMock()
        mock_filter2 = MagicMock()
        mock_first2 = MagicMock()
        mock_first2.return_value = None
        mock_filter2.first = mock_first2
        mock_query2.filter = mock_filter2
        mock_db.query.return_value = mock_query2

        result = resolver._get_session_agent("session_123")

        assert result is None


# ============================================================================
# Edge Cases Tests (2 tests)
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio
    async def test_multiple_resolution_attempts(self, resolver, mock_db, sample_agent):
        """Test multiple resolution calls work correctly."""
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_first = MagicMock()
        mock_first.return_value = sample_agent
        mock_filter.first = mock_first
        mock_query.filter = mock_filter
        mock_db.query.return_value = mock_query

        agent1, ctx1 = await resolver.resolve_agent_for_request(
            user_id="user_123",
            requested_agent_id="agent_123"
        )

        agent2, ctx2 = await resolver.resolve_agent_for_request(
            user_id="user_123",
            requested_agent_id="agent_123"
        )

        assert agent1.id == agent2.id
        assert ctx1["resolution_path"] == ctx2["resolution_path"]

    @pytest.mark.asyncio
    async def test_resolution_with_empty_strings(self, resolver, mock_db):
        """Test resolution handles empty string parameters."""
        system_agent = AgentRegistry(
            id="system_default",
            name="Chat Assistant",
            category="system"
        )

        mock_query1 = MagicMock()
        mock_filter1 = MagicMock()
        mock_first1 = MagicMock()

        def mock_first_side_effect():
            nonlocal call_count
            if call_count < 2:
                return None
            else:
                return system_agent

        mock_first1.side_effect = mock_first_side_effect

        mock_filter1.first = mock_first1
        mock_query1.filter = mock_filter1
        mock_db.query.return_value = mock_query1

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            session_id="",
            requested_agent_id=""
        )

        assert agent is not None
