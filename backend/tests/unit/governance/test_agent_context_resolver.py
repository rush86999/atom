"""
Unit tests for AgentContextResolver.

Tests fallback chain resolution, cache integration, error handling,
performance, and context enrichment.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.models import (
    AgentRegistry,
    AgentStatus,
    ChatSession,
)
from core.agent_context_resolver import AgentContextResolver
from tests.factories import (
    AgentFactory,
    StudentAgentFactory,
)


# Test database session fixture
@pytest.fixture
def db_session():
    """Create a fresh database session for each test."""
    db = SessionLocal()
    try:
        yield db
        db.rollback()
    finally:
        db.close()


# Context resolver fixture
@pytest.fixture
def context_resolver(db_session):
    """Create context resolver instance."""
    return AgentContextResolver(db_session)


# ========================================================================
# Task 3.1: Fallback Chain Resolution
# ========================================================================

class TestFallbackChainResolution:
    """Test fallback chain for agent resolution."""

    @pytest.mark.asyncio
    async def test_explicit_agent_id_lookup(self, context_resolver, db_session):
        """Test direct agent ID lookup (Level 1 of fallback chain)."""
        agent = AgentFactory(_session=db_session)
        db_session.commit()

        resolved_agent, context = await context_resolver.resolve_agent_for_request(
            user_id="test_user",
            requested_agent_id=agent.id
        )

        assert resolved_agent is not None
        assert resolved_agent.id == agent.id
        assert "explicit_agent_id" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_session_based_resolution(self, context_resolver, db_session):
        """Test session-based agent resolution (Level 2 of fallback chain)."""
        # Create agent
        agent = AgentFactory(_session=db_session)

        # Create session with agent_id in metadata
        session = ChatSession(
            id="test_session_id",
            user_id="test_user",
            workspace_id="default",
            metadata_json={"agent_id": agent.id}
        )
        db_session.add(session)
        db_session.commit()

        # Resolve without explicit agent_id (should use session)
        resolved_agent, context = await context_resolver.resolve_agent_for_request(
            user_id="test_user",
            session_id="test_session_id"
        )

        assert resolved_agent is not None
        assert resolved_agent.id == agent.id
        assert "session_agent" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_system_default_resolution(self, context_resolver, db_session):
        """Test system default agent resolution (Level 3 of fallback chain)."""
        # No agent ID provided, no session with agent
        resolved_agent, context = await context_resolver.resolve_agent_for_request(
            user_id="test_user"
        )

        # Should create/return system default "Chat Assistant"
        assert resolved_agent is not None
        assert resolved_agent.name == "Chat Assistant"
        assert resolved_agent.category == "system"
        assert "system_default" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_missing_explicit_agent_falls_back_to_session(self, context_resolver, db_session):
        """Test that missing explicit agent ID falls back to session agent."""
        # Create session with agent
        agent = AgentFactory(_session=db_session)
        session = ChatSession(
            id="test_session_id",
            user_id="test_user",
            workspace_id="default",
            metadata_json={"agent_id": agent.id}
        )
        db_session.add(session)
        db_session.commit()

        # Request non-existent agent, should fallback to session
        resolved_agent, context = await context_resolver.resolve_agent_for_request(
            user_id="test_user",
            session_id="test_session_id",
            requested_agent_id="nonexistent_agent_id"
        )

        assert resolved_agent is not None
        assert resolved_agent.id == agent.id
        assert "explicit_agent_id_not_found" in context["resolution_path"]
        assert "session_agent" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_resolution_failed_when_all_fallbacks_exhausted(self, context_resolver, db_session):
        """Test resolution failure when all fallbacks exhausted."""
        # Mock _get_or_create_system_default to return None
        with patch.object(
            context_resolver, '_get_or_create_system_default',
            return_value=None
        ):
            resolved_agent, context = await context_resolver.resolve_agent_for_request(
                user_id="test_user"
            )

        assert resolved_agent is None
        assert "resolution_failed" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_session_without_agent_falls_back_to_default(self, context_resolver, db_session):
        """Test session without agent_id falls back to system default."""
        # Create session without agent_id in metadata
        session = ChatSession(
            id="test_session_id",
            user_id="test_user",
            workspace_id="default",
            metadata_json={}
        )
        db_session.add(session)
        db_session.commit()

        resolved_agent, context = await context_resolver.resolve_agent_for_request(
            user_id="test_user",
            session_id="test_session_id"
        )

        assert resolved_agent is not None
        assert resolved_agent.name == "Chat Assistant"
        assert "no_session_agent" in context["resolution_path"]


# ========================================================================
# Task 3.2: Cache Integration
# ========================================================================

class TestCacheIntegration:
    """Test cache integration for agent lookups."""

    @pytest.mark.asyncio
    async def test_governance_service_used_for_validation(self, context_resolver):
        """Test that governance service is available for validation."""
        # Governance service should be initialized
        assert context_resolver.governance is not None

    @pytest.mark.asyncio
    async def test_validate_agent_for_action(self, context_resolver, db_session):
        """Test validating agent can perform specific action."""
        agent = StudentAgentFactory(_session=db_session)
        db_session.commit()

        # Validate agent for low-complexity action
        result = context_resolver.validate_agent_for_action(
            agent=agent,
            action_type="present_chart"
        )

        # Should return governance result
        assert "permitted" in result or "allowed" in result or "success" in result


# ========================================================================
# Task 3.3: Error Handling
# ========================================================================

class TestErrorHandling:
    """Test error handling and graceful degradation."""

    @pytest.mark.asyncio
    async def test_get_agent_handles_not_found(self, context_resolver):
        """Test _get_agent handles non-existent agent gracefully."""
        agent = context_resolver._get_agent("nonexistent_agent_id")
        assert agent is None

    @pytest.mark.asyncio
    async def test_get_session_agent_handles_nonexistent_session(self, context_resolver):
        """Test _get_session_agent handles non-existent session."""
        agent = context_resolver._get_session_agent("nonexistent_session_id")
        assert agent is None

    @pytest.mark.asyncio
    async def test_get_session_agent_handles_session_without_agent_id(self, context_resolver, db_session):
        """Test _get_session_agent handles session without agent_id."""
        session = ChatSession(
            id="test_session_id",
            user_id="test_user",
            workspace_id="default",
            metadata_json={}
        )
        db_session.add(session)
        db_session.commit()

        agent = context_resolver._get_session_agent("test_session_id")
        assert agent is None

    @pytest.mark.asyncio
    async def test_resolution_context_includes_error_info(self, context_resolver):
        """Test resolution context includes detailed information."""
        agent, context = await context_resolver.resolve_agent_for_request(
            user_id="test_user",
            requested_agent_id="nonexistent_agent"
        )

        # Should have resolution details even when agent not found
        assert "user_id" in context
        assert "requested_agent_id" in context
        assert "resolution_path" in context
        assert "resolved_at" in context


# ========================================================================
# Task 3.4: Performance
# ========================================================================

class TestPerformance:
    """Test context resolver performance."""

    @pytest.mark.asyncio
    async def test_direct_agent_lookup_performance(self, context_resolver, db_session):
        """Test direct agent lookup is fast."""
        import time

        agent = AgentFactory(_session=db_session)
        db_session.commit()

        start_time = time.time()

        for _ in range(100):
            resolved_agent, _ = await context_resolver.resolve_agent_for_request(
                user_id="test_user",
                requested_agent_id=agent.id
            )

        duration_ms = (time.time() - start_time) * 1000

        # Should average <50ms per lookup (including 100 iterations)
        avg_ms = duration_ms / 100
        assert avg_ms < 50, f"Average lookup time: {avg_ms}ms"

    @pytest.mark.asyncio
    async def test_system_default_creation_performance(self, context_resolver, db_session):
        """Test system default creation is reasonably fast."""
        import time

        # Clear any existing Chat Assistant
        db_session.query(AgentRegistry).filter(
            AgentRegistry.name == "Chat Assistant",
            AgentRegistry.category == "system"
        ).delete()
        db_session.commit()

        start_time = time.time()

        agent, context = await context_resolver.resolve_agent_for_request(
            user_id="test_user"
        )

        duration_ms = (time.time() - start_time) * 1000

        # Should complete quickly (including DB write)
        assert duration_ms < 500, f"System default creation took {duration_ms}ms"


# ========================================================================
# Task 3.5: Context Enrichment
# ========================================================================

class TestContextEnrichment:
    """Test context enrichment and metadata attachment."""

    @pytest.mark.asyncio
    async def test_resolution_context_includes_metadata(self, context_resolver, db_session):
        """Test resolution context includes all metadata."""
        agent = AgentFactory(_session=db_session)
        db_session.commit()

        resolved_agent, context = await context_resolver.resolve_agent_for_request(
            user_id="test_user",
            session_id="test_session",
            requested_agent_id=agent.id,
            action_type="chat"
        )

        # Verify context has all expected fields
        assert context["user_id"] == "test_user"
        assert context["session_id"] == "test_session"
        assert context["requested_agent_id"] == agent.id
        assert context["action_type"] == "chat"
        assert "resolution_path" in context
        assert "resolved_at" in context

    @pytest.mark.asyncio
    async def test_resolution_path_tracks_fallback_chain(self, context_resolver, db_session):
        """Test resolution_path tracks which fallbacks were tried."""
        agent = AgentFactory(_session=db_session)
        db_session.commit()

        resolved_agent, context = await context_resolver.resolve_agent_for_request(
            user_id="test_user",
            requested_agent_id=agent.id
        )

        # Should have path entries
        assert len(context["resolution_path"]) > 0
        assert "explicit_agent_id" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_resolved_at_timestamp_is_valid(self, context_resolver):
        """Test resolved_at timestamp is a valid ISO format string."""
        agent, context = await context_resolver.resolve_agent_for_request(
            user_id="test_user"
        )

        # Should be parseable as ISO datetime
        assert "resolved_at" in context
        try:
            datetime.fromisoformat(context["resolved_at"])
        except ValueError:
            pytest.fail("resolved_at is not a valid ISO datetime")


# ========================================================================
# Task 3.6: Session Management
# ========================================================================

class TestSessionManagement:
    """Test session agent association and retrieval."""

    @pytest.mark.asyncio
    async def test_set_session_agent(self, context_resolver, db_session):
        """Test setting agent on a session."""
        agent = AgentFactory(_session=db_session)

        # Create session
        session = ChatSession(
            id="test_session_id",
            user_id="test_user",
            workspace_id="default",
            metadata_json={}
        )
        db_session.add(session)
        db_session.commit()

        # Set agent on session
        success = context_resolver.set_session_agent(
            session_id="test_session_id",
            agent_id=agent.id
        )

        assert success is True

        # Verify agent was set
        db_session.refresh(session)
        assert session.metadata_json["agent_id"] == agent.id

    @pytest.mark.asyncio
    async def test_set_session_agent_on_nonexistent_session(self, context_resolver):
        """Test setting agent on non-existent session returns False."""
        success = context_resolver.set_session_agent(
            session_id="nonexistent_session",
            agent_id="some_agent_id"
        )

        assert success is False

    @pytest.mark.asyncio
    async def test_set_nonexistent_agent_on_session(self, context_resolver, db_session):
        """Test setting non-existent agent on session returns False."""
        session = ChatSession(
            id="test_session_id",
            user_id="test_user",
            workspace_id="default",
            metadata_json={}
        )
        db_session.add(session)
        db_session.commit()

        success = context_resolver.set_session_agent(
            session_id="test_session_id",
            agent_id="nonexistent_agent_id"
        )

        assert success is False

    @pytest.mark.asyncio
    async def test_set_session_agent_preserves_existing_metadata(self, context_resolver, db_session):
        """Test setting agent preserves other session metadata."""
        agent = AgentFactory(_session=db_session)

        session = ChatSession(
            id="test_session_id",
            user_id="test_user",
            workspace_id="default",
            metadata_json={"existing_key": "existing_value"}
        )
        db_session.add(session)
        db_session.commit()

        context_resolver.set_session_agent(
            session_id="test_session_id",
            agent_id=agent.id
        )

        db_session.refresh(session)
        assert session.metadata_json["existing_key"] == "existing_value"
        assert session.metadata_json["agent_id"] == agent.id


# ========================================================================
# Task 3.7: System Default Agent
# ========================================================================

class TestSystemDefaultAgent:
    """Test system default Chat Assistant agent."""

    @pytest.mark.asyncio
    async def test_system_default_agent_created_once(self, context_resolver, db_session):
        """Test system default agent is created only once."""
        # Clear any existing Chat Assistant
        db_session.query(AgentRegistry).filter(
            AgentRegistry.name == "Chat Assistant",
            AgentRegistry.category == "system"
        ).delete()
        db_session.commit()

        # First resolution creates agent
        agent1, _ = await context_resolver.resolve_agent_for_request(
            user_id="test_user"
        )
        agent1_id = agent1.id

        # Second resolution should return same agent
        agent2, _ = await context_resolver.resolve_agent_for_request(
            user_id="test_user"
        )

        assert agent2.id == agent1_id

    @pytest.mark.asyncio
    async def test_system_default_agent_attributes(self, context_resolver):
        """Test system default agent has correct attributes."""
        agent, _ = await context_resolver.resolve_agent_for_request(
            user_id="test_user"
        )

        assert agent.name == "Chat Assistant"
        assert agent.category == "system"
        assert agent.module_path == "system"
        assert agent.class_name == "ChatAssistant"
        assert agent.status == AgentStatus.STUDENT.value
        assert agent.confidence_score == 0.5
        assert "system_prompt" in agent.configuration
        assert "capabilities" in agent.configuration

    @pytest.mark.asyncio
    async def test_system_default_configuration(self, context_resolver):
        """Test system default agent has proper configuration."""
        agent, _ = await context_resolver.resolve_agent_for_request(
            user_id="test_user"
        )

        config = agent.configuration

        # Should have system prompt
        assert "system_prompt" in config
        assert len(config["system_prompt"]) > 0

        # Should have capabilities list
        assert "capabilities" in config
        assert isinstance(config["capabilities"], list)
        assert len(config["capabilities"]) > 0


# ========================================================================
# Task 3.8: Edge Cases
# ========================================================================

class TestEdgeCases:
    """Test edge cases and unusual scenarios."""

    @pytest.mark.asyncio
    async def test_resolution_with_none_session_id(self, context_resolver, db_session):
        """Test resolution handles None session_id gracefully."""
        agent = AgentFactory(_session=db_session)
        db_session.commit()

        resolved_agent, context = await context_resolver.resolve_agent_for_request(
            user_id="test_user",
            session_id=None,
            requested_agent_id=agent.id
        )

        assert resolved_agent is not None
        assert resolved_agent.id == agent.id

    @pytest.mark.asyncio
    async def test_resolution_with_empty_session_id(self, context_resolver, db_session):
        """Test resolution handles empty string session_id."""
        agent = AgentFactory(_session=db_session)
        db_session.commit()

        resolved_agent, context = await context_resolver.resolve_agent_for_request(
            user_id="test_user",
            session_id="",
            requested_agent_id=agent.id
        )

        assert resolved_agent is not None
        assert resolved_agent.id == agent.id

    @pytest.mark.asyncio
    async def test_multiple_resolution_paths_tracked(self, context_resolver, db_session):
        """Test that multiple fallback attempts are all tracked in path."""
        # Request non-existent agent with no session
        # Should try: explicit_agent_id_not_found -> no_session -> system_default
        resolved_agent, context = await context_resolver.resolve_agent_for_request(
            user_id="test_user",
            requested_agent_id="nonexistent_agent"
        )

        # Should have multiple path entries
        assert len(context["resolution_path"]) >= 2
