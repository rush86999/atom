"""
Coverage expansion tests for core governance services.

Tests cover critical code paths in:
- agent_governance_service.py: Agent lifecycle, permission checks, maturity enforcement
- agent_context_resolver.py: Context resolution for agent execution
- governance_cache.py: High-performance caching layer

Target: Cover critical paths (happy path + error paths) to increase coverage.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.agent_context_resolver import AgentContextResolver
from core.governance_cache import GovernanceCache, get_governance_cache
from core.models import AgentRegistry, AgentStatus, UserRole, ChatSession


class TestAgentGovernanceServiceCoverage:
    """Coverage expansion for AgentGovernanceService."""

    @pytest.fixture
    def db_session(self):
        """Get test database session."""
        from core.database import SessionLocal
        session = SessionLocal()
        yield session
        session.rollback()
        session.close()

    @pytest.fixture
    def governance_service(self, db_session):
        """Get governance service instance."""
        return AgentGovernanceService(db_session)

    # Test: can_perform_action - maturity enforcement
    def test_can_perform_action_student_blocked_high_complexity(self, governance_service, db_session):
        """Student agents blocked from HIGH complexity actions."""
        # Use register_or_update_agent which handles all required fields
        agent = governance_service.register_or_update_agent(
            name="test-student",
            category="test",
            module_path="test",
            class_name="TestStudent"
        )
        # Manually set status to STUDENT for testing
        agent.status = AgentStatus.STUDENT.value
        db_session.commit()

        result = governance_service.can_perform_action(
            agent_id=agent.id,
            action_type="delete_resource"
        )
        assert result["allowed"] == False
        assert "STUDENT" in result["reason"] or "required" in result["reason"].lower()

    def test_can_perform_action_autonomous_allowed_critical(self, governance_service, db_session):
        """AUTONOMOUS agents allowed CRITICAL actions."""
        agent = governance_service.register_or_update_agent(
            name="test-auto",
            category="test",
            module_path="test",
            class_name="TestAuto"
        )
        agent.status = AgentStatus.AUTONOMOUS.value
        db_session.commit()

        result = governance_service.can_perform_action(
            agent_id=agent.id,
            action_type="delete_resource"
        )
        assert result["allowed"] == True

    def test_can_perform_action_agent_not_found(self, governance_service):
        """Return not allowed for non-existent agent."""
        result = governance_service.can_perform_action(
            agent_id="nonexistent-agent",
            action_type="read"
        )
        assert result["allowed"] == False
        assert "not found" in result["reason"].lower()

    def test_can_perform_action_paused_agent(self, governance_service, db_session):
        """Paused agents cannot perform actions."""
        agent = governance_service.register_or_update_agent(
            name="test-paused",
            category="test",
            module_path="test",
            class_name="TestPaused"
        )
        agent.status = AgentStatus.PAUSED.value
        db_session.commit()

        result = governance_service.can_perform_action(
            agent_id=agent.id,
            action_type="read"
        )
        assert result["allowed"] == False
        assert "paused" in result["reason"].lower()

    # Test: register_or_update_agent
    def test_register_or_update_agent_new(self, governance_service, db_session):
        """Register new agent."""
        agent = governance_service.register_or_update_agent(
            name="new-agent",
            category="test",
            module_path="test.module",
            class_name="TestAgent"
        )
        assert agent.name == "new-agent"
        assert agent.status == AgentStatus.STUDENT.value
        assert agent.confidence_score == 0.5

    def test_register_or_update_agent_existing(self, governance_service, db_session):
        """Update existing agent."""
        # Create initial agent
        agent = governance_service.register_or_update_agent(
            name="update-agent",
            category="test",
            module_path="test.module",
            class_name="TestAgent"
        )
        initial_id = agent.id

        # Update agent
        updated = governance_service.register_or_update_agent(
            name="updated-agent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            description="Updated description"
        )
        assert updated.id == initial_id
        assert updated.name == "updated-agent"
        assert updated.description == "Updated description"

    # Test: enforce_action
    def test_enforce_action_blocked(self, governance_service, db_session):
        """Enforce action returns BLOCKED for insufficient maturity."""
        agent = governance_service.register_or_update_agent(
            name="test-student-block",
            category="test",
            module_path="test",
            class_name="TestStudent"
        )
        agent.status = AgentStatus.STUDENT.value
        db_session.commit()

        result = governance_service.enforce_action(
            agent_id=agent.id,
            action_type="delete_resource"
        )
        assert result["proceed"] == False
        assert result["status"] == "BLOCKED"

    def test_enforce_action_approved(self, governance_service, db_session):
        """Enforce action returns APPROVED for sufficient maturity."""
        agent = governance_service.register_or_update_agent(
            name="test-auto-approve",
            category="test",
            module_path="test",
            class_name="TestAuto"
        )
        agent.status = AgentStatus.AUTONOMOUS.value
        db_session.commit()

        result = governance_service.enforce_action(
            agent_id=agent.id,
            action_type="read"
        )
        assert result["proceed"] == True
        assert result["status"] == "APPROVED"


class TestAgentContextResolverCoverage:
    """Coverage expansion for AgentContextResolver."""

    @pytest.fixture
    def db_session(self):
        """Get test database session."""
        from core.database import SessionLocal
        session = SessionLocal()
        yield session
        session.rollback()
        session.close()

    @pytest.fixture
    def resolver(self, db_session):
        """Get context resolver instance."""
        return AgentContextResolver(db_session)

    # Test: resolve_agent_for_request - explicit agent_id
    def test_resolve_agent_explicit_agent_id(self, resolver, db_session):
        """Resolve agent via explicit agent_id."""
        agent = AgentRegistry(
            name="Test Agent",
            category="test",
            module_path="test",
            class_name="TestAgent",
            status=AgentStatus.STUDENT.value,
            workspace_id="default"
        )
        db_session.add(agent)
        db_session.commit()

        resolved, context = resolver.resolve_agent_for_request(
            user_id="test-user",
            requested_agent_id=agent.id
        )
        assert resolved is not None
        assert resolved.id == agent.id
        assert "explicit_agent_id" in context["resolution_path"]

    def test_resolve_agent_explicit_not_found(self, resolver):
        """Handle explicit agent_id that doesn't exist."""
        resolved, context = resolver.resolve_agent_for_request(
            user_id="test-user",
            requested_agent_id="nonexistent-agent"
        )
        assert resolved is None
        assert "explicit_agent_id_not_found" in context["resolution_path"]

    # Test: resolve_agent_for_request - system default
    def test_resolve_agent_system_default(self, resolver, db_session):
        """Resolve agent via system default when no explicit agent."""
        # Delete any existing Chat Assistant to test creation
        existing = db_session.query(AgentRegistry).filter(
            AgentRegistry.name == "Chat Assistant",
            AgentRegistry.category == "system"
        ).first()
        if existing:
            db_session.delete(existing)
            db_session.commit()

        resolved, context = resolver.resolve_agent_for_request(
            user_id="test-user",
            requested_agent_id=None
        )
        assert resolved is not None
        assert resolved.name == "Chat Assistant"
        assert "system_default" in context["resolution_path"]

    # Test: set_session_agent
    def test_set_session_agent(self, resolver, db_session):
        """Set agent on session."""
        # Create agent
        agent = AgentRegistry(
            name="Session Agent",
            category="test",
            module_path="test",
            class_name="SessionAgent",
            status=AgentStatus.STUDENT.value,
            workspace_id="default"
        )
        db_session.add(agent)

        # Create session
        session = ChatSession(
            id="test-session",
            user_id="test-user",
            workspace_id="default"
        )
        db_session.add(session)
        db_session.commit()

        result = resolver.set_session_agent(
            session_id="test-session",
            agent_id=agent.id
        )
        assert result == True

        # Verify agent was set
        db_session.refresh(session)
        assert session.metadata_json["agent_id"] == agent.id

    def test_set_session_agent_nonexistent_session(self, resolver):
        """Handle setting agent on non-existent session."""
        result = resolver.set_session_agent(
            session_id="nonexistent-session",
            agent_id="test-agent"
        )
        assert result == False

    def test_set_session_agent_nonexistent_agent(self, resolver, db_session):
        """Handle setting non-existent agent on session."""
        session = ChatSession(
            id="test-session",
            user_id="test-user",
            workspace_id="default"
        )
        db_session.add(session)
        db_session.commit()

        result = resolver.set_session_agent(
            session_id="test-session",
            agent_id="nonexistent-agent"
        )
        assert result == False

    # Test: validate_agent_for_action
    def test_validate_agent_for_action(self, resolver, db_session):
        """Validate agent can perform action."""
        agent = AgentRegistry(
            name="Test Agent",
            category="test",
            module_path="test",
            class_name="TestAgent",
            status=AgentStatus.AUTONOMOUS.value,
            workspace_id="default"
        )
        db_session.add(agent)
        db_session.commit()

        result = resolver.validate_agent_for_action(
            agent=agent,
            action_type="read"
        )
        assert "allowed" in result


class TestGovernanceCacheCoverage:
    """Coverage expansion for GovernanceCache."""

    @pytest.fixture
    def cache(self):
        """Get governance cache instance."""
        return GovernanceCache()

    # Test: get/set - cache operations
    def test_cache_get_miss(self, cache):
        """Return None for cache miss."""
        result = cache.get("nonexistent-agent", "read")
        assert result is None

    def test_cache_set_and_get(self, cache):
        """Set and get values from cache."""
        data = {"allowed": True, "reason": "Test"}
        success = cache.set("test-agent", "read", data)
        assert success == True

        result = cache.get("test-agent", "read")
        assert result == data

    def test_cache_hit_increments_counter(self, cache):
        """Cache hit increments hit counter."""
        data = {"allowed": True}
        cache.set("test-agent", "read", data)

        # Miss then hit
        cache.get("test-agent", "read")
        stats = cache.get_stats()
        assert stats["hits"] == 1

    def test_cache_miss_increments_counter(self, cache):
        """Cache miss increments miss counter."""
        cache.get("test-agent", "read")
        stats = cache.get_stats()
        assert stats["misses"] == 1

    # Test: invalidate - cache invalidation
    def test_cache_invalidate_specific_action(self, cache):
        """Invalidate cached value for specific action."""
        cache.set("test-agent", "read", {"allowed": True})
        cache.set("test-agent", "write", {"allowed": False})

        cache.invalidate("test-agent", "read")

        assert cache.get("test-agent", "read") is None
        assert cache.get("test-agent", "write") is not None

    def test_cache_invalidate_all_actions(self, cache):
        """Invalidate all cached values for agent."""
        cache.set("test-agent", "read", {"allowed": True})
        cache.set("test-agent", "write", {"allowed": False})
        cache.set("test-agent", "delete", {"allowed": False})

        cache.invalidate_agent("test-agent")

        assert cache.get("test-agent", "read") is None
        assert cache.get("test-agent", "write") is None
        assert cache.get("test-agent", "delete") is None

    def test_cache_clear_all(self, cache):
        """Clear all cache entries."""
        cache.set("agent1", "read", {"data": 1})
        cache.set("agent2", "write", {"data": 2})
        cache.clear()

        assert cache.get("agent1", "read") is None
        assert cache.get("agent2", "write") is None

    # Test: cache statistics
    def test_cache_hit_rate(self, cache):
        """Calculate cache hit rate."""
        cache.set("test-agent", "read", {"allowed": True})

        # 1 hit, 1 miss
        cache.get("test-agent", "read")
        cache.get("test-agent", "write")

        stats = cache.get_stats()
        expected_rate = 50.0  # 1 hit / 2 requests = 50%
        assert stats["hit_rate"] == expected_rate

    def test_cache_stats_structure(self, cache):
        """Cache stats returns expected structure."""
        stats = cache.get_stats()
        assert "size" in stats
        assert "max_size" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats
        assert "evictions" in stats
        assert "invalidations" in stats

    # Test: directory-specific caching
    def test_cache_directory_permission(self, cache):
        """Cache directory permission result."""
        data = {"allowed": True, "directory": "/tmp"}
        success = cache.cache_directory("test-agent", "/tmp", data)
        assert success == True

        result = cache.check_directory("test-agent", "/tmp")
        assert result == data

    def test_cache_directory_miss(self, cache):
        """Return None for directory cache miss."""
        result = cache.check_directory("test-agent", "/nonexistent")
        assert result is None

    # Test: TTL expiration
    def test_cache_expiration(self, cache):
        """Cache entries expire after TTL."""
        import time

        # Create cache with short TTL
        short_cache = GovernanceCache(ttl_seconds=1)
        short_cache.set("test-agent", "read", {"allowed": True})

        # Should be cached immediately
        assert short_cache.get("test-agent", "read") is not None

        # Wait for expiration
        time.sleep(2)

        # Should be expired
        assert short_cache.get("test-agent", "read") is None

    # Test: LRU eviction
    def test_cache_lru_eviction(self, cache):
        """Cache evicts oldest entry when at capacity."""
        # Create small cache
        small_cache = GovernanceCache(max_size=3)

        small_cache.set("agent1", "read", {"data": 1})
        small_cache.set("agent2", "read", {"data": 2})
        small_cache.set("agent3", "read", {"data": 3})

        # Access agent1 to make it recently used
        small_cache.get("agent1", "read")

        # Add one more - should evict agent2 (oldest)
        small_cache.set("agent4", "read", {"data": 4})

        assert small_cache.get("agent1", "read") is not None
        assert small_cache.get("agent2", "read") is None  # Evicted
        assert small_cache.get("agent3", "read") is not None
        assert small_cache.get("agent4", "read") is not None
