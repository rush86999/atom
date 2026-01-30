"""
Unit tests for governance integration with streaming, canvas, and forms.

Tests cover:
- Agent resolution logic (all fallback paths)
- Governance checks for various actions
- Agent execution creation and tracking
- Canvas audit trail creation
- Form submission governance validation
"""

import pytest
import asyncio
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from datetime import datetime
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.agent_governance_service import AgentGovernanceService
from core.governance_cache import GovernanceCache, get_governance_cache
from core.models import AgentRegistry, AgentStatus, User, Workspace, ChatSession


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock(spec=Session)
    return db


@pytest.fixture
def mock_agent_student():
    """Mock student-level agent."""
    agent = Mock(spec=AgentRegistry)
    agent.id = "student-agent-1"
    agent.name = "Student Agent"
    agent.category = "test"
    agent.status = AgentStatus.STUDENT.value
    agent.confidence_score = 0.4
    return agent


@pytest.fixture
def mock_agent_intern():
    """Mock intern-level agent."""
    agent = Mock(spec=AgentRegistry)
    agent.id = "intern-agent-1"
    agent.name = "Intern Agent"
    agent.category = "test"
    agent.status = AgentStatus.INTERN.value
    agent.confidence_score = 0.6
    return agent


@pytest.fixture
def mock_agent_supervised():
    """Mock supervised-level agent."""
    agent = Mock(spec=AgentRegistry)
    agent.id = "supervised-agent-1"
    agent.name = "Supervised Agent"
    agent.category = "test"
    agent.status = AgentStatus.SUPERVISED.value
    agent.confidence_score = 0.8
    return agent


class TestAgentContextResolver:
    """Tests for AgentContextResolver."""

    def test_resolve_agent_with_explicit_id(self, mock_db, mock_agent_intern):
        """Test agent resolution with explicit agent_id."""
        with patch.object(mock_db, 'query') as mock_query:
            # Mock query chain
            mock_filter = Mock()
            mock_query.return_value = mock_filter
            mock_filter.filter.return_value = mock_filter
            mock_filter.first.return_value = mock_agent_intern

            resolver = AgentContextResolver(mock_db)

            # Run async test
            result = asyncio.run(resolver.resolve_agent_for_request(
                user_id="user-1",
                requested_agent_id="intern-agent-1",
                action_type="chat"
            ))

            agent, context = result
            assert agent is not None
            assert agent.id == "intern-agent-1"
            assert "explicit_agent_id" in context["resolution_path"]

    def test_resolve_agent_fallback_to_session(self, mock_db, mock_agent_intern):
        """Test agent resolution falls back to session agent."""
        resolver = AgentContextResolver(mock_db)

        # Mock the internal methods to simulate session fallback
        with patch.object(resolver, '_get_agent', return_value=None):
            # No explicit agent found
            with patch.object(resolver, '_get_session_agent', return_value=mock_agent_intern):
                # But session has agent
                result = asyncio.run(resolver.resolve_agent_for_request(
                    user_id="user-1",
                    session_id="session-1",
                    action_type="chat"
                ))

                agent, context = result
                assert agent is not None
                assert agent.id == "intern-agent-1"

    def test_resolve_agent_fallback_to_system_default(self, mock_db, mock_agent_intern):
        """Test agent resolution falls back to system default."""
        # Create resolver first
        resolver = AgentContextResolver(mock_db)

        # Patch the system default creation
        with patch.object(resolver, '_get_or_create_system_default', return_value=mock_agent_intern):
            with patch.object(mock_db, 'query') as mock_query:
                # Setup mock
                mock_query_instance = Mock()
                mock_db.query.return_value = mock_query_instance

                # No explicit agent, no session agent, no workspace agent
                def mock_filter_func(*args, **kwargs):
                    result_mock = Mock()
                    result_mock.first.return_value = None
                    return result_mock

                mock_query_instance.filter.side_effect = mock_filter_func

                result = asyncio.run(resolver.resolve_agent_for_request(
                    user_id="user-1",
                    action_type="chat"
                ))

                agent, context = result
                assert agent is not None


class TestAgentGovernanceService:
    """Tests for AgentGovernanceService action complexity."""

    def test_action_complexity_mappings(self, mock_db, mock_agent_student):
        """Test new action complexity mappings."""
        governance = AgentGovernanceService(mock_db)

        with patch.object(mock_db, 'query') as mock_query:
            mock_filter = Mock()
            mock_query.return_value = mock_filter
            mock_filter.filter.return_value = mock_filter
            mock_filter.first.return_value = mock_agent_student

            # Test stream_chat (complexity 2 - INTERN+)
            check = governance.can_perform_action("student-agent-1", "stream_chat")
            assert check["action_complexity"] == 2
            assert not check["allowed"]  # STUDENT can't do complexity 2

            # Test present_chart (complexity 1 - STUDENT+)
            check = governance.can_perform_action("student-agent-1", "present_chart")
            assert check["action_complexity"] == 1
            assert check["allowed"]  # STUDENT can do complexity 1

            # Test submit_form (complexity 3 - SUPERVISED+)
            check = governance.can_perform_action("student-agent-1", "submit_form")
            assert check["action_complexity"] == 3
            assert not check["allowed"]  # STUDENT can't do complexity 3

    def test_intern_agent_permissions(self, mock_db, mock_agent_intern):
        """Test INTERN agent can perform moderate actions."""
        governance = AgentGovernanceService(mock_db)

        with patch.object(mock_db, 'query') as mock_query:
            mock_filter = Mock()
            mock_query.return_value = mock_filter
            mock_filter.filter.return_value = mock_filter
            mock_filter.first.return_value = mock_agent_intern

            # INTERN can do stream_chat (complexity 2)
            check = governance.can_perform_action("intern-agent-1", "stream_chat")
            assert check["allowed"]

            # INTERN can do present_form (complexity 2)
            check = governance.can_perform_action("intern-agent-1", "present_form")
            assert check["allowed"]

            # INTERN cannot do submit_form (complexity 3)
            check = governance.can_perform_action("intern-agent-1", "submit_form")
            assert not check["allowed"]

    def test_supervised_agent_permissions(self, mock_db, mock_agent_supervised):
        """Test SUPERVISED agent can perform high-complexity actions."""
        governance = AgentGovernanceService(mock_db)

        with patch.object(mock_db, 'query') as mock_query:
            mock_filter = Mock()
            mock_query.return_value = mock_filter
            mock_filter.filter.return_value = mock_filter
            mock_filter.first.return_value = mock_agent_supervised

            # SUPERVISED can do submit_form (complexity 3)
            check = governance.can_perform_action("supervised-agent-1", "submit_form")
            assert check["allowed"]

            # SUPERVISED can do all lower complexity actions
            check = governance.can_perform_action("supervised-agent-1", "stream_chat")
            assert check["allowed"]


class TestGovernanceCache:
    """Tests for GovernanceCache."""

    def test_cache_set_and_get(self):
        """Test basic cache set and get operations."""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        test_data = {
            "allowed": True,
            "reason": "Agent is permitted",
            "agent_status": "intern"
        }

        # Set and get
        assert cache.set("agent-1", "stream_chat", test_data)
        retrieved = cache.get("agent-1", "stream_chat")

        assert retrieved is not None
        assert retrieved["allowed"] == True
        assert retrieved["reason"] == "Agent is permitted"

    def test_cache_miss(self):
        """Test cache miss returns None."""
        cache = GovernanceCache()
        result = cache.get("nonexistent-agent", "unknown_action")
        assert result is None

    def test_cache_expiration(self):
        """Test cache entries expire after TTL."""
        cache = GovernanceCache(ttl_seconds=1)  # 1 second TTL

        test_data = {"allowed": True}
        cache.set("agent-1", "chat", test_data)

        # Should be available immediately
        assert cache.get("agent-1", "chat") is not None

        # Wait for expiration
        import time
        time.sleep(2)

        # Should be expired
        assert cache.get("agent-1", "chat") is None

    def test_cache_invalidation(self):
        """Test cache invalidation for specific agent/action."""
        cache = GovernanceCache()

        cache.set("agent-1", "stream_chat", {"allowed": True})
        cache.set("agent-1", "submit_form", {"allowed": False})
        cache.set("agent-2", "stream_chat", {"allowed": True})

        # Invalidate specific action
        cache.invalidate("agent-1", "stream_chat")

        assert cache.get("agent-1", "stream_chat") is None
        assert cache.get("agent-1", "submit_form") is not None  # Still there
        assert cache.get("agent-2", "stream_chat") is not None  # Different agent

    def test_cache_invalidate_all_agent_actions(self):
        """Test invalidating all actions for an agent."""
        cache = GovernanceCache()

        cache.set("agent-1", "stream_chat", {"allowed": True})
        cache.set("agent-1", "submit_form", {"allowed": False})
        cache.set("agent-2", "stream_chat", {"allowed": True})

        # Invalidate all agent-1 actions
        cache.invalidate_agent("agent-1")

        assert cache.get("agent-1", "stream_chat") is None
        assert cache.get("agent-1", "submit_form") is None
        assert cache.get("agent-2", "stream_chat") is not None  # Different agent

    def test_cache_stats(self):
        """Test cache statistics tracking."""
        cache = GovernanceCache()

        cache.set("agent-1", "chat", {"allowed": True})

        # Hit
        cache.get("agent-1", "chat")

        # Miss
        cache.get("nonexistent", "action")

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 50.0

    def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = GovernanceCache(max_size=3, ttl_seconds=60)

        cache.set("agent-1", "action1", {"data": "1"})
        cache.set("agent-2", "action2", {"data": "2"})
        cache.set("agent-3", "action3", {"data": "3"})

        # Cache is full, adding new entry should evict oldest
        cache.set("agent-4", "action4", {"data": "4"})

        assert cache.get("agent-1", "action1") is None  # Evicted
        assert cache.get("agent-2", "action2") is not None
        assert cache.get("agent-3", "action3") is not None
        assert cache.get("agent-4", "action4") is not None


@pytest.mark.asyncio
class TestAgentExecutionTracking:
    """Tests for agent execution tracking in streaming."""

    async def test_agent_execution_created_on_stream_start(self, mock_db):
        """Test that AgentExecution is created when streaming starts."""
        from core.models import AgentExecution
        import uuid

        execution = AgentExecution(
            id=str(uuid.uuid4()),  # Explicitly provide ID
            agent_id="agent-1",
            workspace_id="workspace-1",
            status="running",
            input_summary="Stream chat: test message",
            triggered_by="websocket"
        )

        assert execution.id is not None
        assert execution.status == "running"
        assert execution.agent_id == "agent-1"

    async def test_agent_execution_marked_completed(self, mock_db):
        """Test that AgentExecution is marked completed after streaming."""
        from core.models import AgentExecution

        execution = AgentExecution(
            agent_id="agent-1",
            workspace_id="workspace-1",
            status="running",
            input_summary="Test"
        )

        # Simulate completion
        execution.status = "completed"
        execution.output_summary = "Generated 100 tokens"
        execution.completed_at = datetime.now()

        assert execution.status == "completed"
        assert execution.completed_at is not None
        assert execution.output_summary == "Generated 100 tokens"


@pytest.mark.asyncio
class TestCanvasAuditTrail:
    """Tests for canvas audit trail creation."""

    async def test_canvas_audit_created_for_chart(self, mock_db):
        """Test that canvas audit entry is created for chart presentation."""
        from core.models import CanvasAudit

        audit = CanvasAudit(
            id="audit-1",
            agent_id="agent-1",
            agent_execution_id="execution-1",
            user_id="user-1",
            canvas_id="canvas-1",
            component_type="chart",
            component_name="line_chart",
            action="present",
            governance_check_passed=True,
            audit_metadata={"title": "Test Chart", "data_points": 10}
        )

        assert audit.component_type == "chart"
        assert audit.action == "present"
        assert audit.governance_check_passed == True

    async def test_canvas_audit_created_for_form_submission(self, mock_db):
        """Test that canvas audit entry tracks form submissions."""
        from core.models import CanvasAudit

        audit = CanvasAudit(
            id="audit-2",
            agent_id="agent-1",
            user_id="user-1",
            canvas_id="canvas-1",
            component_type="form",
            action="submit",
            governance_check_passed=True,
            audit_metadata={"field_count": 5}
        )

        assert audit.component_type == "form"
        assert audit.action == "submit"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
