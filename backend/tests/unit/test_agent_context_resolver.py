"""
Unit Tests for Agent Context Resolver

Tests agent resolution logic:
- resolve_agent_for_request: Agent selection with fallback
- Resolution context generation
- Agent preference handling

Target Coverage: 85%
Target Branch Coverage: 60%+
Pass Rate Target: 95%+
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from core.agent_context_resolver import AgentContextResolver
from core.models import AgentRegistry


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_db():
    """Create mock database session."""
    return Mock()


@pytest.fixture
def resolver(mock_db):
    """Create AgentContextResolver instance."""
    return AgentContextResolver(mock_db)


# =============================================================================
# Test Class: Resolve Agent for Request
# =============================================================================

class TestResolveAgentForRequest:
    """Tests for resolve_agent_for_request method."""

    @pytest.mark.asyncio
    async def test_resolve_with_requested_agent(self, resolver):
        """RED: Test resolving with explicitly requested agent."""
        with patch.object(resolver, 'governance') as mock_governance:
            mock_agent = Mock()
            mock_agent.id = "agent-123"
            mock_governance.get_agent.return_value = mock_agent

            agent, context = await resolver.resolve_agent_for_request(
                user_id="user-123",
                requested_agent_id="agent-123"
            )

            assert context is not None
            assert isinstance(context, dict)

    @pytest.mark.asyncio
    async def test_resolve_without_requested_agent(self, resolver):
        """RED: Test resolving without explicit agent request."""
        agent, context = await resolver.resolve_agent_for_request(
            user_id="user-123",
            action_type="chat"
        )

        assert isinstance(context, dict)

    @pytest.mark.asyncio
    async def test_resolve_with_session_id(self, resolver):
        """RED: Test resolving with session ID."""
        agent, context = await resolver.resolve_agent_for_request(
            user_id="user-123",
            session_id="session-456",
            action_type="workflow"
        )

        assert isinstance(context, dict)

    @pytest.mark.asyncio
    async def test_resolve_for_different_action_types(self, resolver):
        """RED: Test resolving for different action types."""
        for action_type in ["chat", "workflow", "task"]:
            agent, context = await resolver.resolve_agent_for_request(
                user_id="user-123",
                action_type=action_type
            )
            assert isinstance(context, dict)


# =============================================================================
# Test Class: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_resolve_with_empty_user_id(self, resolver):
        """RED: Test resolving with empty user ID."""
        agent, context = await resolver.resolve_agent_for_request(
            user_id=""
        )

        assert isinstance(context, dict)

    @pytest.mark.asyncio
    async def test_resolve_with_nonexistent_agent(self, resolver):
        """RED: Test resolving non-existent requested agent."""
        with patch.object(resolver, 'governance') as mock_governance:
            mock_governance.get_agent.return_value = None

            agent, context = await resolver.resolve_agent_for_request(
                user_id="user-123",
                requested_agent_id="nonexistent"
            )

            assert isinstance(context, dict)

    @pytest.mark.asyncio
    async def test_resolve_with_all_optional_params(self, resolver):
        """RED: Test resolving with all optional parameters."""
        agent, context = await resolver.resolve_agent_for_request(
            user_id="user-123",
            session_id="session-456",
            requested_agent_id="agent-789",
            action_type="task"
        )

        assert isinstance(context, dict)


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
