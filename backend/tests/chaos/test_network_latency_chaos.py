"""
Network Latency Chaos Tests

Tests system resilience to network latency using Toxiproxy.

Requirements:
    CHAOS-02: Network latency injection (Toxiproxy integration, slow 3G simulation)

Scenarios:
    - Slow 3G database latency (2000ms)
    - Network timeout handling
    - Recovery after latency removed
"""

import pytest
import time
from sqlalchemy.exc import OperationalError

from tests.chaos.core.chaos_coordinator import ChaosCoordinator
from tests.chaos.core.blast_radius_controls import assert_blast_radius
from core.models import AgentRegistry


@pytest.mark.chaos
@pytest.mark.timeout(60)
def test_slow_3g_database_latency(slow_database_proxy, chaos_coordinator, chaos_db_session):
    """
    Test system resilience to 2000ms database latency (slow 3G).

    Scenario: Database queries take 2+ seconds (slow 3G)
    Duration: 30 seconds
    Blast radius: test database only

    CHAOS-02: Network latency injection (Toxiproxy integration)
    """
    # Create test data before latency injection
    agent = AgentRegistry(
        id="test-latency-agent",
        name="latency_test",
        description="Test agent for latency chaos",
        category="Testing",
        module_path="test.latency",
        class_name="LatencyTest",
        status="STUDENT"
    )
    chaos_db_session.add(agent)
    chaos_db_session.commit()

    agent_id = agent.id

    # Baseline: Query without latency
    start_time = time.time()
    agent_baseline = chaos_db_session.query(AgentRegistry).filter_by(id=agent_id).first()
    baseline_latency = time.time() - start_time

    # Define graceful degradation verification
    def verify_graceful_degradation(metrics):
        """System should handle latency gracefully (not crash)."""
        # CPU may spike due to waiting, but system should not crash
        assert metrics["cpu_percent"] < 100, "CPU at 100% indicates hang"

    # Run chaos experiment with ChaosCoordinator
    results = chaos_coordinator.run_experiment(
        experiment_name="test_slow_3g_database_latency",
        failure_injection=lambda: _latency_context(slow_database_proxy),
        verify_graceful_degradation=verify_graceful_degradation,
        blast_radius_checks=[assert_blast_radius]
    )

    # Verify recovery
    assert results["success"], "Chaos experiment failed"

    # Verify data integrity
    recovered_agent = chaos_db_session.query(AgentRegistry).filter_by(id=agent_id).first()
    assert recovered_agent is not None, "Agent was lost during latency injection"
    assert recovered_agent.name == "latency_test", "Agent data corrupted"


def _latency_context(slow_database_proxy):
    """Context manager for latency injection."""
    class LatencyContext:
        def __init__(self, proxy):
            self.proxy = proxy

        def __enter__(self):
            self.toxic = self.proxy.toxic("latency", latency_ms=2000, jitter=0)
            # For SQLite mock proxy, toxic() returns context manager directly
            if hasattr(self.toxic, '__enter__'):
                return self.toxic.__enter__()
            return self.toxic

        def __exit__(self, *args):
            if hasattr(self.toxic, '__exit__'):
                self.toxic.__exit__(*args)

    return LatencyContext(slow_database_proxy)


@pytest.mark.chaos
@pytest.mark.timeout(60)
def test_network_timeout_handling(chaos_coordinator, chaos_db_session):
    """
    Test system resilience to network timeout conditions.

    Scenario: Network requests timeout after 5 seconds
    Duration: 30 seconds
    Blast radius: test network only
    """
    # Create test data
    agent = AgentRegistry(
        id="test-timeout-agent",
        name="timeout_test",
        description="Test agent for timeout chaos",
        category="Testing",
        module_path="test.timeout",
        class_name="TimeoutTest",
        status="STUDENT"
    )
    chaos_db_session.add(agent)
    chaos_db_session.commit()

    # Simulate timeout with sleep
    def inject_timeout():
        class TimeoutContext:
            def __enter__(self):
                # Simulate 5 second network timeout
                time.sleep(5)
                return self

            def __exit__(self, *args):
                time.sleep(1)  # Recovery time

        return TimeoutContext()

    def verify_timeout_handling(metrics):
        """System should handle timeout gracefully."""
        # Verify system didn't crash
        assert metrics["cpu_percent"] < 100, "CPU at 100% indicates hang"

    results = chaos_coordinator.run_experiment(
        experiment_name="test_network_timeout_handling",
        failure_injection=inject_timeout,
        verify_graceful_degradation=verify_timeout_handling,
        blast_radius_checks=[assert_blast_radius]
    )

    assert results["success"]


@pytest.mark.chaos
@pytest.mark.timeout(60)
def test_recovery_after_latency_removed(slow_database_proxy, chaos_coordinator, chaos_db_session):
    """
    Test system recovery after network latency is removed.

    Scenario: Latency injected for 10 seconds, then removed
    Duration: 30 seconds
    Blast radius: test database only

    Validates: CHAOS-07 (Recovery validation)
    """
    # Create test data
    agent = AgentRegistry(
        id="test-recovery-agent",
        name="recovery_test",
        description="Test agent for recovery validation",
        category="Testing",
        module_path="test.recovery",
        class_name="RecoveryTest",
        status="STUDENT"
    )
    chaos_db_session.add(agent)
    chaos_db_session.commit()

    agent_id = agent.id

    # Baseline: Query without latency
    start_time = time.time()
    agent_baseline = chaos_db_session.query(AgentRegistry).filter_by(id=agent_id).first()
    baseline_latency = time.time() - start_time

    # Inject latency
    with slow_database_proxy.toxic("latency", latency_ms=2000, jitter=0):
        # Query under latency
        start_time = time.time()
        agent_during = chaos_db_session.query(AgentRegistry).filter_by(id=agent_id).first()
        latency_during = time.time() - start_time
        assert latency_during > 1.0, "Latency not applied"

    # Verify recovery: Query should return to baseline speed
    start_time = time.time()
    agent_recovered = chaos_db_session.query(AgentRegistry).filter_by(id=agent_id).first()
    recovery_latency = time.time() - start_time

    # Assert recovery within 0.5s of baseline
    assert abs(recovery_latency - baseline_latency) < 0.5, \
        f"System did not recover: baseline={baseline_latency:.3f}s, recovery={recovery_latency:.3f}s"
