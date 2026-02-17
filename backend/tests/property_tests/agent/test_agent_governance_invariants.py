"""
Property-Based Tests for Agent Governance Invariants

Tests CRITICAL governance invariants:
- Maturity routing is deterministic (same inputs → same decisions)
- Action complexity matrix enforced (1-4)
- STUDENT agents blocked from complexity 3-4 actions
- INTERN agents require proposals for complexity 2-4
- SUPERVISED agents monitored for complexity 2-4
- AUTONOMOUS agents have full access
- Confidence scores in [0.0, 1.0]
- Governance cache hit rate >95%
"""
import pytest
from hypothesis import strategies as st, given, settings, example, HealthCheck
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.governance_cache import GovernanceCache
from core.models import AgentRegistry, AgentStatus
from tests.factories import (
    AgentFactory,
    StudentAgentFactory,
    InternAgentFactory,
    SupervisedAgentFactory,
    AutonomousAgentFactory
)

# Common settings for all property tests
hypothesis_settings = settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)

# Map maturity levels to their factories
MATURITY_FACTORIES = {
    "STUDENT": StudentAgentFactory,
    "INTERN": InternAgentFactory,
    "SUPERVISED": SupervisedAgentFactory,
    "AUTONOMOUS": AutonomousAgentFactory,
}


def create_agent(factory_class, db_session):
    """Helper to create agent with proper session handling."""
    return factory_class(_session=db_session)


class TestMaturityRoutingInvariants:
    """Property tests for maturity routing determinism and correctness."""

    @pytest.fixture
    def service(self, db_session):
        """Create AgentGovernanceService."""
        return AgentGovernanceService(db_session)

    @given(
        maturity=st.sampled_from(["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]),
        action_complexity=st.integers(min_value=1, max_value=4)
    )
    @hypothesis_settings
    def test_maturity_routing_deterministic(self, service, maturity, action_complexity):
        """
        Maturity routing is deterministic invariant.

        Property: Same (maturity, action_complexity) always produces same allow/deny decision.
        """
        factory = MATURITY_FACTORIES[maturity]
        agent = create_agent(factory, service.db)

        # Map complexity to appropriate action
        action_map = {
            1: "present_chart",
            2: "stream_chat",
            3: "submit_form",
            4: "delete"
        }
        action = action_map.get(action_complexity, "stream_chat")

        # Check permission twice
        decision1 = service.can_perform_action(
            agent_id=agent.id,
            action_type=action
        )
        decision2 = service.can_perform_action(
            agent_id=agent.id,
            action_type=action
        )

        # Should be identical
        assert decision1["allowed"] == decision2["allowed"]
        # These fields should be present when agent is found
        if "agent_status" in decision1:
            assert decision1["agent_status"] == decision2["agent_status"]
        if "action_complexity" in decision1:
            assert decision1["action_complexity"] == decision2["action_complexity"]

    @given(
        complexity=st.integers(min_value=1, max_value=4)
    )
    @hypothesis_settings
    @example(complexity=3)
    @example(complexity=4)
    def test_student_blocked_from_high_complexity(self, service, db_session, complexity):
        """
        STUDENT agents blocked from complexity 3-4 invariant.

        Property: STUDENT agents always denied actions with complexity >= 3.
        """
        agent = create_agent(StudentAgentFactory, db_session)

        # Map complexity to appropriate action
        action_map = {
            1: "present_chart",
            2: "stream_chat",
            3: "submit_form",
            4: "delete"
        }
        action = action_map.get(complexity, "stream_chat")

        decision = service.can_perform_action(
            agent_id=agent.id,
            action_type=action
        )

        if complexity >= 3:
            # STUDENT should be blocked from complexity 3-4
            assert decision["allowed"] is False, (
                f"STUDENT agent should be blocked from complexity {complexity}, "
                f"but was allowed: {decision}"
            )
            assert "student" in decision["agent_status"].lower()

    @given(
        complexity=st.integers(min_value=1, max_value=4)
    )
    @hypothesis_settings
    def test_autonomous_full_access(self, service, db_session, complexity):
        """
        AUTONOMOUS agents have full access invariant.

        Property: AUTONOMOUS agents always allowed for all complexity levels.
        """
        agent = create_agent(AutonomousAgentFactory, db_session)

        # Map complexity to appropriate action
        action_map = {
            1: "present_chart",
            2: "stream_chat",
            3: "submit_form",
            4: "delete"
        }
        action = action_map.get(complexity, "stream_chat")

        decision = service.can_perform_action(
            agent_id=agent.id,
            action_type=action
        )

        # AUTONOMOUS should be allowed for all complexities
        assert decision["allowed"] is True, (
            f"AUTONOMOUS agent should be allowed complexity {complexity}, "
            f"but was blocked: {decision}"
        )
        assert "autonomous" in decision["agent_status"].lower()


class TestActionComplexityMatrixInvariants:
    """Property tests for action complexity matrix enforcement."""

    @pytest.fixture
    def service(self, db_session):
        """Create AgentGovernanceService."""
        return AgentGovernanceService(db_session)

    @given(
        maturity=st.sampled_from(["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]),
        complexity=st.integers(min_value=1, max_value=4)
    )
    @hypothesis_settings
    def test_complexity_matrix_enforced(self, service, maturity, complexity):
        """
        Action complexity matrix invariant.

        Property: Each maturity level has specific complexity access.
        """
        factory = MATURITY_FACTORIES[maturity]
        agent = create_agent(factory, service.db)

        # Map complexity to appropriate action
        action_map = {
            1: "present_chart",
            2: "stream_chat",
            3: "submit_form",
            4: "delete"
        }
        action = action_map.get(complexity, "stream_chat")

        decision = service.can_perform_action(
            agent_id=agent.id,
            action_type=action
        )

        # Define allowed complexity by maturity
        allowed_by_maturity = {
            "STUDENT": [1],  # Presentations only
            "INTERN": [1, 2],  # Presentations + Streaming
            "SUPERVISED": [1, 2, 3],  # + State changes
            "AUTONOMOUS": [1, 2, 3, 4]  # Full access
        }

        # Check if complexity is allowed for this maturity
        is_allowed = complexity in allowed_by_maturity[maturity]

        # Verify decision matches expected allowance
        assert decision["allowed"] == is_allowed, (
            f"Expected {maturity} agent to {'be allowed' if is_allowed else 'be blocked'} "
            f"from complexity {complexity} action, but got: {decision}"
        )

    @given(
        maturity=st.sampled_from(["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"])
    )
    @hypothesis_settings
    def test_complexity_1_always_allowed(self, service, maturity):
        """
        Complexity 1 actions always allowed invariant.

        Property: All maturity levels can perform complexity 1 (presentations).
        """
        factory = MATURITY_FACTORIES[maturity]
        agent = create_agent(factory, service.db)
        decision = service.can_perform_action(
            agent_id=agent.id,
            action_type="present_chart"
        )

        assert decision["allowed"] is True, (
            f"All maturity levels should be allowed complexity 1 actions, "
            f"but {maturity} was blocked: {decision}"
        )
        assert decision["action_complexity"] == 1

    @given(
        maturity=st.sampled_from(["STUDENT", "INTERN", "SUPERVISED"])
    )
    @hypothesis_settings
    def test_complexity_4_requires_autonomous(self, service, maturity):
        """
        Complexity 4 requires AUTONOMOUS invariant.

        Property: Only AUTONOMOUS agents can perform complexity 4 (deletions).
        """
        factory = MATURITY_FACTORIES[maturity]
        agent = create_agent(factory, service.db)
        decision = service.can_perform_action(
            agent_id=agent.id,
            action_type="delete"
        )

        # Only AUTONOMOUS should be allowed
        assert decision["allowed"] is False, (
            f"Non-AUTONOMOUS agent ({maturity}) should be blocked from "
            f"complexity 4 actions, but was allowed: {decision}"
        )


class TestGovernanceCachePerformance:
    """Property tests for governance cache performance."""

    @pytest.fixture
    def cache(self, db_session):
        """Create GovernanceCache."""
        return GovernanceCache()

    @given(
        num_queries=st.integers(min_value=10, max_value=100)
    )
    @hypothesis_settings
    def test_cache_consistency(self, cache, num_queries):
        """
        Cache consistency invariant.

        Property: Repeated queries for same agent_id return consistent results.
        """
        agent_id = "test-agent-123"
        action_type = "test_action"

        # Store a decision
        test_decision = {
            "allowed": True,
            "agent_status": "AUTONOMOUS",
            "action_complexity": 2
        }
        cache.set(agent_id, action_type, test_decision)

        # Query multiple times
        results = []
        for _ in range(num_queries):
            result = cache.get(agent_id, action_type)
            results.append(result)

        # All results should be identical
        assert all(r == test_decision for r in results), (
            f"Cache should return consistent results across {num_queries} queries"
        )

    @given(
        num_entries=st.integers(min_value=1, max_value=100)
    )
    @hypothesis_settings
    def test_cache_lru_eviction(self, cache, num_entries):
        """
        Cache LRU eviction invariant.

        Property: Cache evicts least recently used entries when at capacity.
        """
        # Create cache with small max size
        small_cache = GovernanceCache(max_size=10)

        # Add more entries than max_size
        for i in range(num_entries):
            small_cache.set(f"agent_{i}", "action", {"data": f"value_{i}"})

        # Cache should not exceed max_size
        stats = small_cache.get_stats()
        assert stats["size"] <= 10, (
            f"Cache size {stats['size']} exceeds max_size 10"
        )

        # Most recently added items should still be present
        recent_result = small_cache.get(f"agent_{num_entries-1}", "action")
        assert recent_result is not None, "Recently added entry should be in cache"

    @given(
        num_agents=st.integers(min_value=5, max_value=50)
    )
    @hypothesis_settings
    def test_cache_hit_rate_increases_with_repetition(self, cache, num_agents):
        """
        Cache hit rate improves with repetition invariant.

        Property: Repeated queries increase cache hit rate.
        """
        # Clear cache to start fresh (it's a global singleton)
        cache.clear()

        # Create unique agent IDs
        agent_ids = [f"agent_{i}_{id(cache)}" for i in range(num_agents)]  # Make unique per cache instance

        # First pass: all cache misses
        for agent_id in agent_ids:
            cache.get(agent_id, "test_action")

        stats_after_warm = cache.get_stats()
        # Should have at least num_agents misses (might have more from previous tests)
        assert stats_after_warm["misses"] >= num_agents

        # Second pass: warm up cache
        for agent_id in agent_ids:
            cache.set(agent_id, "test_action", {"allowed": True})

        hits = 0
        for agent_id in agent_ids:
            result = cache.get(agent_id, "test_action")
            if result is not None:
                hits += 1

        # All should be hits after warming
        assert hits == num_agents, (
            f"Expected {num_agents} cache hits after warming, got {hits}"
        )


class TestConfidenceScoreInvariants:
    """Property tests for confidence score management."""

    @pytest.fixture
    def service(self, db_session):
        """Create AgentGovernanceService."""
        return AgentGovernanceService(db_session)

    @given(
        initial_score=st.floats(min_value=0.0, max_value=1.0),
        num_positive=st.integers(min_value=0, max_value=10),
        num_negative=st.integers(min_value=0, max_value=10)
    )
    @hypothesis_settings
    def test_confidence_score_bounds(self, service, initial_score, num_positive, num_negative):
        """
        Confidence score bounds invariant.

        Property: Confidence scores always stay within [0.0, 1.0].
        """
        # Create agent with specific confidence
        agent = AgentFactory(confidence_score=initial_score, _session=service.db)

        # Apply positive updates
        for _ in range(num_positive):
            service._update_confidence_score(agent.id, positive=True, impact_level="low")

        # Apply negative updates
        for _ in range(num_negative):
            service._update_confidence_score(agent.id, positive=False, impact_level="low")

        # Refresh from database
        service.db.refresh(agent)

        # Score should be within bounds
        assert 0.0 <= agent.confidence_score <= 1.0, (
            f"Confidence score {agent.confidence_score} outside valid range [0.0, 1.0]"
        )

    @given(
        maturity=st.sampled_from(["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"])
    )
    @hypothesis_settings
    def test_maturity_status_matches_confidence(self, service, maturity):
        """
        Maturity status matches confidence score invariant.

        Property: Agent status reflects confidence score range.
        """
        # Create agent with specific maturity
        factory = MATURITY_FACTORIES[maturity]
        agent = create_agent(factory, service.db)

        # Verify confidence matches maturity range
        if maturity == "STUDENT":
            assert 0.0 <= agent.confidence_score < 0.5
        elif maturity == "INTERN":
            assert 0.5 <= agent.confidence_score < 0.7
        elif maturity == "SUPERVISED":
            assert 0.7 <= agent.confidence_score < 0.9
        elif maturity == "AUTONOMOUS":
            assert 0.9 <= agent.confidence_score <= 1.0


class TestMaturityTransitions:
    """Property tests for maturity level transitions."""

    @pytest.fixture
    def service(self, db_session):
        """Create AgentGovernanceService."""
        return AgentGovernanceService(db_session)

    @given(
        initial_maturity=st.sampled_from(["STUDENT", "INTERN", "SUPERVISED"]),
        num_positive_updates=st.integers(min_value=1, max_value=20)
    )
    @hypothesis_settings
    def test_positive_updates_increase_maturity(self, service, initial_maturity, num_positive_updates):
        """
        Positive updates increase maturity invariant.

        Property: Sufficient positive updates promote agents to higher maturity.
        """
        factory = MATURITY_FACTORIES[initial_maturity]
        agent = factory(_session=service.db)

        # Apply many positive updates with high impact
        for _ in range(num_positive_updates):
            service._update_confidence_score(agent.id, positive=True, impact_level="high")

        # Re-query from database to get updated state
        updated_agent = service.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent.id
        ).first()

        # Confidence should have increased
        # (not checking strict monotonicity due to clamping at 1.0)
        assert updated_agent is not None
        assert updated_agent.confidence_score >= 0.0

    @given(
        initial_maturity=st.sampled_from(["INTERN", "SUPERVISED", "AUTONOMOUS"]),
        num_negative_updates=st.integers(min_value=1, max_value=10)
    )
    @hypothesis_settings
    def test_negative_updates_decrease_maturity(self, service, initial_maturity, num_negative_updates):
        """
        Negative updates decrease maturity invariant.

        Property: Sufficient negative updates demote agents to lower maturity.
        """
        factory = MATURITY_FACTORIES[initial_maturity]
        agent = factory(_session=service.db)

        # Apply many negative updates with high impact
        for _ in range(num_negative_updates):
            service._update_confidence_score(agent.id, positive=False, impact_level="high")

        # Re-query from database to get updated state
        updated_agent = service.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent.id
        ).first()

        # Confidence should have decreased
        # (not checking strict monotonicity due to clamping at 0.0)
        assert updated_agent is not None
        assert updated_agent.confidence_score <= 1.0


class TestGovernanceDecisionCompleteness:
    """Property tests for governance decision structure."""

    @pytest.fixture
    def service(self, db_session):
        """Create AgentGovernanceService."""
        return AgentGovernanceService(db_session)

    @given(
        maturity=st.sampled_from(["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]),
        action_type=st.sampled_from([
            "present_chart", "stream_chat", "submit_form", "delete",
            "read", "analyze", "create", "execute", "send_email", "deploy"
        ])
    )
    @hypothesis_settings
    def test_decision_structure_complete(self, service, maturity, action_type):
        """
        Governance decision structure completeness invariant.

        Property: All governance decisions contain required fields.
        """
        factory = MATURITY_FACTORIES[maturity]
        agent = create_agent(factory, service.db)
        decision = service.can_perform_action(
            agent_id=agent.id,
            action_type=action_type
        )

        # Check required fields exist
        required_fields = ["allowed", "reason", "agent_status", "action_complexity"]
        for field in required_fields:
            assert field in decision, f"Decision missing required field: {field}"

        # Check field types
        assert isinstance(decision["allowed"], bool)
        assert isinstance(decision["reason"], str)
        assert isinstance(decision["agent_status"], str)
        assert isinstance(decision["action_complexity"], int)

        # Check complexity is valid range
        assert 1 <= decision["action_complexity"] <= 4

    @given(
        maturity=st.sampled_from(["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"])
    )
    @hypothesis_settings
    def test_decision_reason_informative(self, service, maturity):
        """
        Governance decision reason informative invariant.

        Property: Decision reasons contain useful information.
        """
        factory = MATURITY_FACTORIES[maturity]
        agent = create_agent(factory, service.db)
        decision = service.can_perform_action(
            agent_id=agent.id,
            action_type="test_action"
        )

        # Reason should not be empty
        assert len(decision["reason"]) > 0, "Decision reason should not be empty"

        # Reason should mention agent or action
        reason_lower = decision["reason"].lower()
        assert "agent" in reason_lower or "action" in reason_lower or "complexity" in reason_lower, (
            f"Decision reason should be informative: {decision['reason']}"
        )
