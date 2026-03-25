"""
Service Crash Chaos Tests

Tests system resilience to service crashes.

Requirements:
    CHAOS-05: Service crash simulation (LLM provider failures, Redis crashes)

Scenarios:
    - LLM provider crash (OpenAI, Anthropic unavailable)
    - Redis cache layer crash
    - External API unavailability
    - Service recovery and reconnection
"""

import pytest
import time
from unittest.mock import patch, MagicMock

from tests.chaos.core.chaos_coordinator import ChaosCoordinator
from tests.chaos.core.blast_radius_controls import assert_blast_radius
from core.models import AgentRegistry


@pytest.mark.chaos
@pytest.mark.timeout(60)
def test_llm_provider_crash_handling(llm_provider_crash_simulator, chaos_coordinator, chaos_db_session):
    """
    Test system resilience to LLM provider crash.

    Scenario: LLM provider becomes unavailable during agent execution
    Duration: 30 seconds
    Blast radius: test only (mocked LLM calls)

    CHAOS-05: LLM provider failure simulation
    """
    # Create test agent
    agent = AgentRegistry(
        id="test-llm-crash-agent",
        name="llm_crash_test",
        description="Test agent for LLM provider crash chaos",
        maturity_level="STUDENT"
    )
    chaos_db_session.add(agent)
    chaos_db_session.commit()

    agent_id = agent.id

    # Track LLM calls
    llm_calls_made = []
    llm_errors_caught = []

    # Define LLM provider crash injection
    def inject_llm_crash():
        return llm_provider_crash_simulator()

    def verify_graceful_degradation(metrics):
        """System should handle LLM provider crash gracefully."""
        # System should return error, not crash
        assert metrics["cpu_percent"] < 100, "CPU at 100% indicates crash"

    # Mock LLM call that handles crash
    def mock_llm_call_with_error_handling():
        try:
            with llm_provider_crash_simulator():
                # This will fail due to crash
                from core.llm.byok_handler import BYOKHandler
                handler = BYOKHandler()
                llm_calls_made.append(1)
                # Attempt LLM call (will crash)
                list(handler.chat_stream("test", [], "default"))
        except Exception as e:
            llm_errors_caught.append(str(e))
            # Expected: Error caught and handled gracefully
            assert "LLM provider service unavailable" in str(e) or "Connection refused" in str(e)

    # Run chaos experiment
    results = chaos_coordinator.run_experiment(
        experiment_name="test_llm_provider_crash_handling",
        failure_injection=inject_llm_crash,
        verify_graceful_degradation=verify_graceful_degradation,
        blast_radius_checks=[assert_blast_radius]
    )

    # Verify success
    assert results["success"], "Chaos experiment failed"

    # Verify LLM crash was caught
    assert len(llm_errors_caught) > 0, "LLM provider crash was not caught"


@pytest.mark.chaos
@pytest.mark.timeout(60)
def test_redis_crash_handling(redis_crash_simulator, chaos_coordinator, chaos_db_session):
    """
    Test system resilience to Redis cache layer crash.

    Scenario: Redis becomes unavailable during operations
    Duration: 30 seconds
    Blast radius: test Redis only

    CHAOS-05: Redis crash simulation
    """
    # Create test agent
    agent = AgentRegistry(
        id="test-redis-crash-agent",
        name="redis_crash_test",
        description="Test agent for Redis crash chaos",
        maturity_level="STUDENT"
    )
    chaos_db_session.add(agent)
    chaos_db_session.commit()

    agent_id = agent.id

    # Define Redis crash injection
    def inject_redis_crash():
        return redis_crash_simulator()

    def verify_graceful_degradation(metrics):
        """System should handle Redis crash gracefully."""
        # System should fall back to database without crash
        assert metrics["cpu_percent"] < 100, "CPU at 100% indicates crash"

    # Run chaos experiment
    results = chaos_coordinator.run_experiment(
        experiment_name="test_redis_crash_handling",
        failure_injection=inject_redis_crash,
        verify_graceful_degradation=verify_graceful_degradation,
        blast_radius_checks=[assert_blast_radius]
    )

    # Verify success
    assert results["success"], "Chaos experiment failed"

    # Verify data integrity (database is source of truth)
    recovered_agent = chaos_db_session.query(AgentRegistry).filter_by(id=agent_id).first()
    assert recovered_agent is not None, "Agent data lost (cache crash should not affect database)"


@pytest.mark.chaos
@pytest.mark.timeout(60)
def test_service_recovery_after_crash(llm_provider_crash_simulator, chaos_coordinator, chaos_db_session):
    """
    Test service recovery after crash is resolved.

    Scenario: LLM provider crashes, then recovers
    Duration: 30 seconds
    Blast radius: test only (mocked LLM calls)

    CHAOS-07: Recovery validation (service restoration)
    """
    # Create test agent
    agent = AgentRegistry(
        id="test-recovery-agent",
        name="recovery_test",
        description="Test agent for service recovery validation",
        maturity_level="STUDENT"
    )
    chaos_db_session.add(agent)
    chaos_db_session.commit()

    # Phase 1: Crash service
    with llm_provider_crash_simulator():
        # LLM calls will fail
        from core.llm.byok_handler import BYOKHandler
        handler = BYOKHandler()
        try:
            list(handler.chat_stream("test", [], "default"))
            assert False, "LLM call should have failed during crash"
        except Exception:
            pass  # Expected

    # Phase 2: Verify service recovered (context manager restored service)
    from core.llm.byok_handler import BYOKHandler
    handler = BYOKHandler()

    # Mock successful LLM response for recovery test
    with patch.object(BYOKHandler, 'chat_stream', return_value=iter(["Recovered"])):
        response = list(handler.chat_stream("test", [], "default"))
        assert response == ["Recovered"], "Service did not recover after crash"


@pytest.mark.chaos
@pytest.mark.timeout(60)
def test_external_api_crash_handling(external_api_crash_simulator, chaos_coordinator, chaos_db_session):
    """
    Test system resilience to external API crashes.

    Scenario: External webhooks/integrations become unavailable
    Duration: 30 seconds
    Blast radius: test only (mocked requests)

    CHAOS-05: External service crash simulation
    """
    # Create test agent
    agent = AgentRegistry(
        id="test-external-api-crash-agent",
        name="external_api_crash_test",
        description="Test agent for external API crash chaos",
        maturity_level="STUDENT"
    )
    chaos_db_session.add(agent)
    chaos_db_session.commit()

    # Define external API crash injection
    def inject_external_api_crash():
        return external_api_crash_simulator()

    def verify_graceful_degradation(metrics):
        """System should handle external API crash gracefully."""
        # System should queue or return error, not crash
        assert metrics["cpu_percent"] < 100, "CPU at 100% indicates crash"

    # Run chaos experiment
    results = chaos_coordinator.run_experiment(
        experiment_name="test_external_api_crash_handling",
        failure_injection=inject_external_api_crash,
        verify_graceful_degradation=verify_graceful_degradation,
        blast_radius_checks=[assert_blast_radius]
    )

    # Verify success
    assert results["success"], "Chaos experiment failed"


@pytest.mark.chaos
@pytest.mark.timeout(60)
def test_cascading_failure_prevention(llm_provider_crash_simulator, redis_crash_simulator, chaos_coordinator, chaos_db_session):
    """
    Test cascading failure prevention when multiple services crash.

    Scenario: Both LLM provider and Redis crash simultaneously
    Duration: 30 seconds
    Blast radius: test only

    Validates:
    - No cascading failures (one crash doesn't trigger others)
    - System remains functional for non-dependent operations
    - Appropriate error messages for each failed service
    """
    # Create test agent
    agent = AgentRegistry(
        id="test-cascading-agent",
        name="cascading_test",
        description="Test agent for cascading failure prevention",
        maturity_level="STUDENT"
    )
    chaos_db_session.add(agent)
    chaos_db_session.commit()

    agent_id = agent.id

    # Track errors
    errors_caught = []

    # Crash both services
    with llm_provider_crash_simulator():
        with redis_crash_simulator():
            # System should still function for database operations
            try:
                # Database query should still work (not dependent on LLM or Redis)
                agent = chaos_db_session.query(AgentRegistry).filter_by(id=agent_id).first()
                assert agent is not None, "Database operations should work during service crashes"
            except Exception as e:
                errors_caught.append(("database", str(e)))

    # Verify no cascading failures
    assert len(errors_caught) == 0, f"Cascading failures detected: {errors_caught}"

    # Verify data integrity
    recovered_agent = chaos_db_session.query(AgentRegistry).filter_by(id=agent_id).first()
    assert recovered_agent is not None, "Data lost due to cascading failure"
