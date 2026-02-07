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
from hypothesis import given, settings
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
    @settings(max_examples=200)
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
    @settings(max_examples=100)
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
    @settings(max_examples=100)
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
    @settings(max_examples=50)
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
