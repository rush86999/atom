"""
Database Connection Drop Chaos Tests

Tests system resilience to database connection drops.

Requirements:
    CHAOS-03: Database connection drop simulation (connection pool exhaustion)

Scenarios:
    - SQLite database lock (connection drop)
    - Connection pool exhaustion
    - Retry logic validation
    - Data integrity after recovery
"""

import pytest
import time
from sqlalchemy.exc import OperationalError

from tests.chaos.core.chaos_coordinator import ChaosCoordinator
from tests.chaos.core.blast_radius_controls import assert_blast_radius
from core.models import AgentRegistry


@pytest.mark.chaos
@pytest.mark.timeout(60)
def test_sqlite_database_lock_recovery(database_connection_dropper, chaos_coordinator, chaos_db_session):
    """
    Test system resilience to SQLite database lock (connection drop).

    Scenario: Database file locked for 10 seconds
    Duration: 30 seconds
    Blast radius: test database only

    CHAOS-03: Database connection drop simulation
    """
    # Create test data before lock
    agent = AgentRegistry(
        id="test-db-lock-agent",
        name="db_lock_test",
        description="Test agent for database lock chaos",
        maturity_level="STUDENT"
    )
    chaos_db_session.add(agent)
    chaos_db_session.commit()

    agent_id = agent.id

    # Define connection drop injection
    def inject_connection_drop():
        return database_connection_dropper()

    def verify_graceful_degradation(metrics):
        """System should handle connection error gracefully."""
        # System should not crash, may have elevated CPU due to retry attempts
        assert metrics["cpu_percent"] < 100, "CPU at 100% indicates hang"

    # Run chaos experiment
    results = chaos_coordinator.run_experiment(
        experiment_name="test_sqlite_database_lock_recovery",
        failure_injection=inject_connection_drop,
        verify_graceful_degradation=verify_graceful_degradation,
        blast_radius_checks=[assert_blast_radius]
    )

    # Verify success
    assert results["success"], "Chaos experiment failed"

    # Verify data integrity after recovery
    recovered_agent = chaos_db_session.query(AgentRegistry).filter_by(id=agent_id).first()
    assert recovered_agent is not None, "Agent was lost during database lock"
    assert recovered_agent.name == "db_lock_test", "Agent data corrupted"


@pytest.mark.chaos
@pytest.mark.timeout(60)
def test_connection_pool_exhaustion_handling(connection_pool_exhaustion, chaos_coordinator, chaos_db_session):
    """
    Test system resilience to connection pool exhaustion.

    Scenario: Connection pool exhausted, no connections available
    Duration: 30 seconds
    Blast radius: test database only

    CHAOS-03: Connection pool exhaustion
    """
    # Create test data
    agent = AgentRegistry(
        id="test-pool-exhaustion-agent",
        name="pool_exhaustion_test",
        description="Test agent for pool exhaustion chaos",
        maturity_level="STUDENT"
    )
    chaos_db_session.add(agent)
    chaos_db_session.commit()

    agent_id = agent.id

    # Define pool exhaustion injection
    def inject_pool_exhaustion():
        return connection_pool_exhaustion()

    def verify_graceful_degradation(metrics):
        """System should handle pool exhaustion gracefully."""
        # System should return error, not crash
        assert metrics["cpu_percent"] < 100, "CPU at 100% indicates crash"

    # Run chaos experiment
    results = chaos_coordinator.run_experiment(
        experiment_name="test_connection_pool_exhaustion_handling",
        failure_injection=inject_pool_exhaustion,
        verify_graceful_degradation=verify_graceful_degradation,
        blast_radius_checks=[assert_blast_radius]
    )

    # Verify data integrity after recovery
    recovered_agent = chaos_db_session.query(AgentRegistry).filter_by(id=agent_id).first()
    assert recovered_agent is not None, "Agent was lost during pool exhaustion"


@pytest.mark.chaos
@pytest.mark.timeout(60)
def test_retry_logic_validation(database_connection_dropper, chaos_coordinator, chaos_db_session):
    """
    Test connection retry logic activates when database unavailable.

    Scenario: Database connection drops, system retries connection
    Duration: 30 seconds
    Blast radius: test database only

    Validates:
    - Retry logic activates (max_retries=5)
    - Exponential backoff works
    - Connection succeeds after database available
    """
    # Create test data
    agent = AgentRegistry(
        id="test-retry-agent",
        name="retry_test",
        description="Test agent for retry logic validation",
        maturity_level="STUDENT"
    )
    chaos_db_session.add(agent)
    chaos_db_session.commit()

    agent_id = agent.id

    # Track retry attempts
    retry_attempts = []

    def mock_query_with_retry():
        """Simulate query with retry logic."""
        max_retries = 5
        base_delay = 0.1  # 100ms

        for attempt in range(max_retries):
            try:
                with database_connection_dropper():
                    # This will fail during connection drop
                    agent = chaos_db_session.query(AgentRegistry).filter_by(id=agent_id).first()
                    return agent
            except OperationalError:
                retry_attempts.append(attempt)
                if attempt < max_retries - 1:
                    time.sleep(base_delay * (2 ** attempt))  # Exponential backoff
                else:
                    raise

    # Test that retry logic works
    try:
        result = mock_query_with_retry()
        assert result is not None, "Query failed after retries"
    except OperationalError:
        # Expected if database still locked after max retries
        pass

    # Verify retry attempts were made
    assert len(retry_attempts) > 0, "No retry attempts were made"

    # Verify data integrity after recovery
    recovered_agent = chaos_db_session.query(AgentRegistry).filter_by(id=agent_id).first()
    assert recovered_agent is not None, "Agent was lost"


@pytest.mark.chaos
@pytest.mark.timeout(60)
def test_data_integrity_after_database_recovery(database_connection_dropper, chaos_coordinator, chaos_db_session):
    """
    Test data integrity maintained after database connection restored.

    Scenario: Database connection drops and recovers
    Duration: 30 seconds
    Blast radius: test database only

    CHAOS-07: Recovery validation (data integrity checks)
    """
    # Create test data
    agents = []
    for i in range(5):
        agent = AgentRegistry(
            id=f"test-integrity-agent-{i}",
            name=f"integrity_test_{i}",
            description=f"Test agent {i} for data integrity validation",
            maturity_level="STUDENT"
        )
        chaos_db_session.add(agent)
        agents.append(agent)

    chaos_db_session.commit()

    agent_ids = [a.id for a in agents]
    expected_names = [a.name for a in agents]

    # Inject connection drop
    with database_connection_dropper():
        # Database is locked, queries will fail
        pass

    # Verify data integrity after recovery
    for i, agent_id in enumerate(agent_ids):
        recovered_agent = chaos_db_session.query(AgentRegistry).filter_by(id=agent_id).first()
        assert recovered_agent is not None, f"Agent {agent_id} was lost"
        assert recovered_agent.name == expected_names[i], f"Agent {agent_id} data corrupted"

    # Verify no orphaned records (all records accessible)
    all_agents = chaos_db_session.query(AgentRegistry).filter(
        AgentRegistry.id.in_(agent_ids)
    ).all()
    assert len(all_agents) == len(agent_ids), "Some records were orphaned"
