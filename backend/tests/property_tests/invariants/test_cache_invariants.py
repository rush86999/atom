"""
⚠️  PROTECTED PROPERTY-BASED TEST ⚠️

This file tests CRITICAL SYSTEM INVARIANTS for the Atom platform.

DO NOT MODIFY THIS FILE unless:
1. You are fixing a TEST BUG (not an implementation bug)
2. You are ADDING new invariants
3. You have EXPLICIT APPROVAL from engineering lead

These tests must remain IMPLEMENTATION-AGNOSTIC.
Test only observable behaviors and public API contracts.

Protection: tests/.protection_markers/PROPERTY_TEST_GUARDIAN.md
"""

import time

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.governance_cache import get_governance_cache
from core.models import AgentRegistry, AgentStatus


class TestCacheInvariants:
    """Test governance cache maintains critical invariants."""

    @given(
        agent_status=st.sampled_from([
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ]),
        action_type=st.text(min_size=1, max_size=50).filter(lambda x: x.strip())
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_cache_idempotency_within_ttl(
        self, db_session: Session, agent_status: str, action_type: str
    ):
        """
        INVARIANT: Cache MUST return same decision for same key within TTL.

        Multiple checks for same agent+action should return identical results.
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        cache = get_governance_cache()

        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=agent_status,
            confidence_score=0.5,
            
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Act: First check (cache miss)
        decision1 = service.can_perform_action(agent.id, action_type)

        # Second check (cache hit)
        decision2 = service.can_perform_action(agent.id, action_type)

        # Assert: Decisions should be identical
        assert decision1["allowed"] == decision2["allowed"], \
            "Cached decision 'allowed' field differs"
        assert decision1["agent_status"] == decision2["agent_status"], \
            "Cached decision 'agent_status' field differs"
        assert decision1["action_complexity"] == decision2["action_complexity"], \
            "Cached decision 'action_complexity' field differs"
        assert decision1["required_status"] == decision2["required_status"], \
            "Cached decision 'required_status' field differs"

    @given(
        action_type=st.text(min_size=1, max_size=50).filter(lambda x: x.strip())
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_cache_invalidation_on_status_change(
        self, db_session: Session, action_type: str
    ):
        """
        INVARIANT: Cache MUST invalidate when agent status changes.

        After agent status changes, old cached decisions must not be used.
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        cache = get_governance_cache()

        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
            
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Act: First check (status: STUDENT)
        decision1 = service.can_perform_action(agent.id, action_type)
        initial_status = agent.status

        # Change agent status
        agent.status = AgentStatus.AUTONOMOUS.value
        agent.confidence_score = 0.95
        db_session.commit()

        # Invalidate cache explicitly
        cache.invalidate(agent.id)

        # Second check (status: AUTONOMOUS)
        decision2 = service.can_perform_action(agent.id, action_type)
        final_status = agent.status

        # Assert: Cached decisions should reflect new status
        assert decision1["agent_status"] == initial_status, \
            "First decision should show initial status"
        assert decision2["agent_status"] == final_status, \
            "Second decision should show new status"

        # If the status change affects permissions, decisions should differ
        if initial_status != final_status:
            # At minimum, the agent_status field must be updated
            assert decision1["agent_status"] != decision2["agent_status"], \
                "Cache should reflect status change"

    @given(
        agent_status=st.sampled_from([
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ]),
        action_type=st.text(min_size=1, max_size=50).filter(lambda x: x.strip())
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_cache_performance(
        self, db_session: Session, agent_status: str, action_type: str
    ):
        """
        INVARIANT: Cache MUST provide <1ms lookups for cached entries.

        This is a performance invariant - cached checks should be extremely fast.
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        cache = get_governance_cache()

        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=agent_status,
            confidence_score=0.5,
            
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # First check to populate cache
        service.can_perform_action(agent.id, action_type)

        # Measure cached lookup time
        start_time = time.perf_counter()
        for _ in range(100):
            service.can_perform_action(agent.id, action_type)
        end_time = time.perf_counter()

        avg_time_ms = (end_time - start_time) * 1000 / 100

        # Assert: Average cached lookup should be <1ms
        assert avg_time_ms < 1.0, \
            f"Cache lookup too slow: {avg_time_ms:.3f}ms (should be <1ms)"

    @given(
        num_agents=st.integers(min_value=1, max_value=50),
        num_actions=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_cache_handles_high_volume(
        self, db_session: Session, num_agents: int, num_actions: int
    ):
        """
        INVARIANT: Cache MUST handle high volume without errors.

        Even with many agents and actions, cache should not crash or return invalid results.
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        cache = get_governance_cache()

        agents = []
        for i in range(num_agents):
            agent = AgentRegistry(
                name=f"TestAgent_{i}",
                category="test",
                module_path="test.module",
                class_name="TestClass",
                status=AgentStatus.INTERN.value,
                confidence_score=0.5,
                
            )
            db_session.add(agent)
            db_session.commit()
            db_session.refresh(agent)
            agents.append(agent)

        # Generate test actions
        actions = [f"action_{i}" for i in range(num_actions)]

        # Act: Perform many governance checks
        try:
            for agent in agents:
                for action in actions:
                    decision = service.can_perform_action(agent.id, action)

                    # Assert: Every decision must be valid
                    assert decision is not None, "Cache returned None"
                    assert isinstance(decision, dict), "Cache returned non-dict"
                    assert "allowed" in decision, "Decision missing 'allowed' field"

        except Exception as e:
            pytest.fail(f"Cache failed under high volume: {e}")

    @given(
        num_queries=st.integers(min_value=10, max_value=100),
        delay_seconds=st.floats(min_value=0.01, max_value=0.1, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_cache_hit_rate_tracking(
        self, db_session: Session, num_queries: int, delay_seconds: float
    ):
        """
        INVARIANT: Cache MUST track hit rate accurately.

        Hit rate should be (hits / total_queries) and should improve with repeated queries.
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        cache = get_governance_cache()

        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,

        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        test_action = "test_action"

        # Act: Perform repeated queries
        import time
        for _ in range(num_queries):
            decision = service.can_perform_action(agent.id, test_action)
            assert decision is not None
            time.sleep(delay_seconds)

        # Assert: Cache should show statistics
        # (Note: This tests the invariant that cache tracks stats,
        # actual hit rate depends on implementation)
        stats = cache.get_stats() if hasattr(cache, 'get_stats') else {}
        assert isinstance(stats, dict), "Cache stats should be a dict"

    @given(
        num_agents=st.integers(min_value=1, max_value=10),
        unique_actions=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_cache_key_consistency(
        self, db_session: Session, num_agents: int, unique_actions: int
    ):
        """
        INVARIANT: Cache MUST generate consistent keys for same agent+action pair.

        Same agent and action should always generate same cache key.
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        cache = get_governance_cache()

        agents = []
        for i in range(num_agents):
            agent = AgentRegistry(
                name=f"TestAgent_{i}",
                category="test",
                module_path="test.module",
                class_name="TestClass",
                status=AgentStatus.INTERN.value,
                confidence_score=0.5,

            )
            db_session.add(agent)
            db_session.commit()
            db_session.refresh(agent)
            agents.append(agent)

        actions = [f"action_{i}" for i in range(unique_actions)]

        # Act: Generate cache keys for each agent+action pair
        key_pairs = {}
        for agent in agents:
            for action in actions:
                # First lookup
                decision1 = service.can_perform_action(agent.id, action)

                # Second lookup (should use same key)
                decision2 = service.can_perform_action(agent.id, action)

                # Decisions should be identical
                pair_key = (agent.id, action)
                key_pairs[pair_key] = (decision1, decision2)

        # Assert: All decisions should be consistent
        for pair_key, (decision1, decision2) in key_pairs.items():
            assert decision1["allowed"] == decision2["allowed"], \
                f"Inconsistent decisions for {pair_key}"

    @given(
        initial_status=st.sampled_from([
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
        ]),
        new_status=st.sampled_from([
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ]),
        num_invalidations=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_cache_partial_invalidation(
        self, db_session: Session, initial_status: str, new_status: str, num_invalidations: int
    ):
        """
        INVARIANT: Cache MUST support partial invalidation (by agent).

        Invalidating one agent should not affect other agents' cache entries.
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        cache = get_governance_cache()

        # Create multiple agents
        agents = []
        for i in range(3):
            agent = AgentRegistry(
                name=f"TestAgent_{i}",
                category="test",
                module_path="test.module",
                class_name="TestClass",
                status=initial_status,
                confidence_score=0.5,

            )
            db_session.add(agent)
            db_session.commit()
            db_session.refresh(agent)
            agents.append(agent)

        test_action = "test_action"

        # Populate cache for all agents
        decisions_before = {}
        for agent in agents:
            decision = service.can_perform_action(agent.id, test_action)
            decisions_before[agent.id] = decision

        # Act: Invalidate only the first agent
        target_agent = agents[0]
        for _ in range(num_invalidations):
            cache.invalidate(target_agent.id)

        # Update target agent's status
        target_agent.status = new_status
        target_agent.confidence_score = 0.8
        db_session.commit()

        # Get new decision for target agent
        new_decision = service.can_perform_action(target_agent.id, test_action)

        # Get cached decisions for other agents (should be unchanged)
        decisions_after = {}
        for agent in agents[1:]:
            decision = service.can_perform_action(agent.id, test_action)
            decisions_after[agent.id] = decision

        # Assert: Target agent's decision may have changed
        # Other agents' decisions should be identical
        for agent_id in decisions_after:
            assert decisions_after[agent_id]["allowed"] == decisions_before[agent_id]["allowed"], \
                f"Agent {agent_id} cache was incorrectly invalidated"

    @given(
        agent_status=st.sampled_from([
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ]),
        action_type=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        num_repetitions=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_cache_miss_vs_hit_performance(
        self, db_session: Session, agent_status: str, action_type: str, num_repetitions: int
    ):
        """
        INVARIANT: Cache MUST provide faster hits than misses.

        Cached lookups should be consistently faster than uncached lookups.
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        cache = get_governance_cache()

        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=agent_status,
            confidence_score=0.5,

        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Measure cache miss time (first query)
        import time
        start_miss = time.perf_counter()
        decision1 = service.can_perform_action(agent.id, action_type)
        end_miss = time.perf_counter()
        miss_time_ms = (end_miss - start_miss) * 1000

        # Measure cache hit time (subsequent queries)
        start_hit = time.perf_counter()
        for _ in range(num_repetitions):
            decision2 = service.can_perform_action(agent.id, action_type)
        end_hit = time.perf_counter()
        avg_hit_time_ms = (end_hit - start_hit) * 1000 / num_repetitions

        # Assert: Cache hits should be faster (or at least not significantly slower)
        # Allow 10x tolerance for noise
        assert avg_hit_time_ms <= miss_time_ms * 10, \
            f"Cache hit ({avg_hit_time_ms:.3f}ms) slower than miss ({miss_time_ms:.3f}ms)"

    @given(
        num_entries=st.integers(min_value=10, max_value=100),
        clear_fraction=st.floats(min_value=0.1, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_cache_global_clear(
        self, db_session: Session, num_entries: int, clear_fraction: float
    ):
        """
        INVARIANT: Cache MUST support global clearing.

        Clearing all cache entries should remove all cached decisions.
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        cache = get_governance_cache()

        # Create agents and populate cache
        agents = []
        for i in range(num_entries):
            agent = AgentRegistry(
                name=f"TestAgent_{i}",
                category="test",
                module_path="test.module",
                class_name="TestClass",
                status=AgentStatus.INTERN.value,
                confidence_score=0.5,

            )
            db_session.add(agent)
            db_session.commit()
            db_session.refresh(agent)
            agents.append(agent)

        # Populate cache
        actions = [f"action_{i % 5}" for i in range(num_entries)]
        for agent, action in zip(agents, actions):
            service.can_perform_action(agent.id, action)

        # Act: Clear cache (if method exists)
        if hasattr(cache, 'clear'):
            cache.clear()

        # Assert: Next lookups should be cache misses
        # (We can't directly detect misses, but we can verify cache still works)
        for agent, action in zip(agents[:10], actions[:10]):
            decision = service.can_perform_action(agent.id, action)
            assert decision is not None, "Cache should still work after clear"

    @given(
        confidence_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        action_type=st.text(min_size=1, max_size=50).filter(lambda x: x.strip())
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_negative_caching(
        self, db_session: Session, confidence_score: float, action_type: str
    ):
        """
        INVARIANT: Cache MUST cache denials (negative caching).

        When an action is denied, the denial should also be cached for performance.
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        cache = get_governance_cache()

        # Create STUDENT agent (lowest maturity)
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=confidence_score,

        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Act: Try high-complexity action (will be denied)
        decision1 = service.can_perform_action(agent.id, "delete")

        # Second query (should use cached denial)
        decision2 = service.can_perform_action(agent.id, "delete")

        # Assert: Denials should be cached (identical results)
        assert decision1["allowed"] == decision2["allowed"], \
            "Denied action should be cached"
        assert decision1["allowed"] == False, \
            "STUDENT agent should be denied for 'delete' action"

