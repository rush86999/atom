"""
Unit Tests for Agent Context Resolver

Tests cover:
- Context resolution fallback chain (explicit -> session -> default)
- Governance cache integration
- Session context creation
- Default context fallback
"""
import pytest
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.models import AgentRegistry, ChatSession, User
from tests.factories import AgentFactory


class TestAgentContextResolver:
    """Test agent context resolver."""

    @pytest.fixture
    def resolver(self, db_session):
        """Create resolver."""
        return AgentContextResolver(db_session)

    @pytest.mark.asyncio
    async def test_context_resolution_fallback_chain(self, resolver, db_session):
        """Context resolution should fallback: explicit -> session -> default."""
        agent = AgentFactory(_session=db_session)

        # Try explicit context (doesn't exist) - should fallback to default
        resolved_agent, context = await resolver.resolve_agent_for_request(
            user_id="test-user",
            session_id=None,
            requested_agent_id="nonexistent-agent",
            action_type="chat"
        )

        # Should fallback to system default
        assert resolved_agent is not None
        assert "system_default" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_explicit_context_priority(self, resolver, db_session):
        """Explicit context should take priority over session/default."""
        # Create an agent
        agent = AgentFactory(_session=db_session, name="Explicit Agent")

        # Resolve with explicit agent_id
        resolved_agent, context = await resolver.resolve_agent_for_request(
            user_id="test-user",
            session_id=None,
            requested_agent_id=agent.id,
            action_type="chat"
        )

        assert resolved_agent is not None
        assert resolved_agent.id == agent.id
        assert "explicit_agent_id" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_session_context_resolution(self, resolver, db_session):
        """Session context should be used if available."""
        # Create agent and session
        agent = AgentFactory(_session=db_session, name="Session Agent")
        user = User(id="test-user", email="test@example.com")
        db_session.add(user)

        session = ChatSession(
            id="test-session",
            user_id="test-user",
            metadata_json={"agent_id": agent.id}
        )
        db_session.add(session)
        db_session.commit()

        # Resolve with session_id
        resolved_agent, context = await resolver.resolve_agent_for_request(
            user_id="test-user",
            session_id="test-session",
            requested_agent_id=None,
            action_type="chat"
        )

        assert resolved_agent is not None
        assert resolved_agent.id == agent.id
        assert "session_agent" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_system_default_creation(self, resolver, db_session):
        """System default agent should be created if not exists."""
        # Resolve without any context (should create default)
        resolved_agent, context = await resolver.resolve_agent_for_request(
            user_id="test-user",
            session_id=None,
            requested_agent_id=None,
            action_type="chat"
        )

        assert resolved_agent is not None
        assert resolved_agent.name == "Chat Assistant"
        assert resolved_agent.category == "system"
        assert "system_default" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_system_default_reuse(self, resolver, db_session):
        """System default agent should be reused on subsequent calls."""
        # First call creates default
        resolved_agent1, context1 = await resolver.resolve_agent_for_request(
            user_id="test-user",
            session_id=None,
            requested_agent_id=None,
            action_type="chat"
        )

        # Second call should reuse same agent
        resolved_agent2, context2 = await resolver.resolve_agent_for_request(
            user_id="test-user",
            session_id=None,
            requested_agent_id=None,
            action_type="chat"
        )

        assert resolved_agent1.id == resolved_agent2.id
        assert resolved_agent1.name == "Chat Assistant"

    @pytest.mark.asyncio
    async def test_resolution_context_contains_metadata(self, resolver, db_session):
        """Resolution context should contain all metadata."""
        agent = AgentFactory(_session=db_session)

        resolved_agent, context = await resolver.resolve_agent_for_request(
            user_id="test-user",
            session_id="test-session",
            requested_agent_id=agent.id,
            action_type="stream_chat"
        )

        assert "user_id" in context
        assert "session_id" in context
        assert "requested_agent_id" in context
        assert "action_type" in context
        assert "resolution_path" in context
        assert "resolved_at" in context
        assert context["user_id"] == "test-user"
        assert context["action_type"] == "stream_chat"

    @pytest.mark.asyncio
    async def test_set_session_agent(self, resolver, db_session):
        """Should be able to set agent on session."""
        agent = AgentFactory(_session=db_session)
        user = User(id="test-user", email="test@example.com")
        db_session.add(user)

        session = ChatSession(
            id="test-session",
            user_id="test-user",
            metadata_json={}
        )
        db_session.add(session)
        db_session.commit()

        # Set agent on session
        result = resolver.set_session_agent(
            session_id="test-session",
            agent_id=agent.id
        )

        assert result is True

        # Verify agent was set
        db_session.refresh(session)
        assert session.metadata_json["agent_id"] == agent.id

    @pytest.mark.asyncio
    async def test_set_session_agent_nonexistent_session(self, resolver, db_session):
        """Setting agent on non-existent session should return False."""
        agent = AgentFactory(_session=db_session)

        result = resolver.set_session_agent(
            session_id="nonexistent-session",
            agent_id=agent.id
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_set_session_agent_nonexistent_agent(self, resolver, db_session):
        """Setting non-existent agent on session should return False."""
        user = User(id="test-user", email="test@example.com")
        db_session.add(user)

        session = ChatSession(
            id="test-session",
            user_id="test-user",
            metadata_json={}
        )
        db_session.add(session)
        db_session.commit()

        result = resolver.set_session_agent(
            session_id="test-session",
            agent_id="nonexistent-agent"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_validate_agent_for_action(self, resolver, db_session):
        """Should validate agent can perform action."""
        agent = AgentFactory(_session=db_session, status="AUTONOMOUS")

        # AUTONOMOUS agents can present (complexity 1)
        result = resolver.validate_agent_for_action(
            agent=agent,
            action_type="present_chart",
            require_approval=False
        )

        # AUTONOMOUS agent should be allowed for presentations
        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_resolution_path_logging(self, resolver, db_session):
        """Resolution path should be tracked in context."""
        # Try explicit agent that doesn't exist (should go through fallback)
        resolved_agent, context = await resolver.resolve_agent_for_request(
            user_id="test-user",
            session_id=None,
            requested_agent_id="nonexistent-agent",
            action_type="chat"
        )

        # Should have tried explicit_agent_id_not_found then system_default
        assert len(context["resolution_path"]) >= 1
        assert "system_default" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_multiple_resolution_attempts(self, resolver, db_session):
        """Multiple resolution attempts should work correctly."""
        agent = AgentFactory(_session=db_session)

        # First resolution
        resolved_agent1, context1 = await resolver.resolve_agent_for_request(
            user_id="test-user",
            requested_agent_id=agent.id,
            action_type="chat"
        )

        # Second resolution
        resolved_agent2, context2 = await resolver.resolve_agent_for_request(
            user_id="test-user",
            requested_agent_id=agent.id,
            action_type="stream_chat"
        )

        assert resolved_agent1.id == resolved_agent2.id
        assert context1["resolution_path"] == context2["resolution_path"]

    @pytest.mark.asyncio
    async def test_session_without_agent_falls_back_to_default(self, resolver, db_session):
        """Session without agent_id should fallback to default."""
        user = User(id="test-user", email="test@example.com")
        db_session.add(user)

        session = ChatSession(
            id="test-session",
            user_id="test-user",
            metadata_json={}  # No agent_id
        )
        db_session.add(session)
        db_session.commit()

        # Resolve with session that has no agent
        resolved_agent, context = await resolver.resolve_agent_for_request(
            user_id="test-user",
            session_id="test-session",
            requested_agent_id=None,
            action_type="chat"
        )

        # Should fallback to system default
        assert resolved_agent is not None
        assert "system_default" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_get_session_agent_with_invalid_metadata(self, resolver, db_session):
        """Should handle sessions with invalid metadata gracefully."""
        user = User(id="test-user", email="test@example.com")
        db_session.add(user)

        # Create session with string metadata (invalid)
        session = ChatSession(
            id="test-session",
            user_id="test-user",
            metadata_json="invalid"  # Should be dict
        )
        db_session.add(session)
        db_session.commit()

        # Should not crash, should fallback to default
        resolved_agent, context = await resolver.resolve_agent_for_request(
            user_id="test-user",
            session_id="test-session",
            requested_agent_id=None,
            action_type="chat"
        )

        # Should fallback to system default
        assert resolved_agent is not None

    @pytest.mark.asyncio
    async def test_agent_for_request_with_all_contexts(self, resolver, db_session):
        """Should prioritize explicit > session > default."""
        # Create agents
        explicit_agent = AgentFactory(_session=db_session, name="Explicit Agent")
        session_agent = AgentFactory(_session=db_session, name="Session Agent")
        user = User(id="test-user", email="test@example.com")
        db_session.add(user)

        # Create session with agent
        session = ChatSession(
            id="test-session",
            user_id="test-user",
            metadata_json={"agent_id": session_agent.id}
        )
        db_session.add(session)
        db_session.commit()

        # Explicit agent should take priority
        resolved_agent, context = await resolver.resolve_agent_for_request(
            user_id="test-user",
            session_id="test-session",
            requested_agent_id=explicit_agent.id,
            action_type="chat"
        )

        assert resolved_agent.id == explicit_agent.id
        assert "explicit_agent_id" in context["resolution_path"]
