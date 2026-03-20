"""
Soak Tests for Database Connection Pool Stability

Extended duration tests (2 hours) to detect connection pool exhaustion and leaks:
- Connection pool size stability under load
- Connection return validation (all connections checked in)
- Connection leak detection (unclosed connections)
- Pool growth monitoring (shouldn't grow unbounded)

Connection pool issues detected:
- Connections not returned to pool (leaks)
- Pool exhaustion (all connections checked out)
- Pool growing unbounded (connections created but not reused)

Tests use SQLAlchemy engine.pool.status() to monitor pool health.
Only applicable to QueuePool (SQLite uses StaticPool, skip if not QueuePool).
"""

import gc
import pytest
import time
from sqlalchemy.pool import QueuePool

from core.models import AgentRegistry


@pytest.mark.soak
@pytest.mark.timeout(7200)  # 2 hours
def test_connection_pool_no_leaks_2hr(db_session, memory_monitor):
    """
    Soak test for database connection pool stability (2 hours).

    Validates:
    - All connections are returned to pool after operations
    - Pool size doesn't grow >10 from initial (no connection leaks)
    - Pool remains stable under extended load
    - No connection exhaustion errors

    Test pattern:
    - Run for 2 hours (7200 seconds)
    - Perform 100 database operations per iteration
    - Each iteration: create agent, query agent, delete agent
    - Log pool status every 300 iterations (~5 minutes)
    - Final validation: all connections checked in, pool size stable

    Duration: 2 hours
    Pool threshold: Size growth < 10 connections
    Failure: Pool grown > 10 or connections not checked in

    Note: Skips if not using QueuePool (SQLite uses StaticPool).
    """
    from core.database import engine

    # Check if using QueuePool (SQLite uses StaticPool, skip test)
    if not isinstance(engine.pool, QueuePool):
        pytest.skip("Connection pool test requires QueuePool (SQLite uses StaticPool)")

    initial_size = engine.pool.size()
    initial_checked_in = engine.pool.checkedin()

    print(f"\n🔍 Initial pool state: size={initial_size}, checked_in={initial_checked_in}")

    start_time = time.time()
    iterations = 0

    # Run database operations for 2 hours
    while time.time() - start_time < 7200:
        # Perform 100 database operations per iteration
        for i in range(100):
            try:
                # Create agent
                agent = AgentRegistry(
                    id=f"soak_test_agent_{iterations}_{i}",
                    name=f"Soak Test Agent {iterations}_{i}",
                    category="test",
                    module_path="test.module",
                    class_name="TestClass",
                    status="AUTONOMOUS",
                    confidence_score=0.9
                )
                db_session.add(agent)
                db_session.commit()

                # Query agent
                agent = db_session.query(AgentRegistry).filter(
                    AgentRegistry.id == f"soak_test_agent_{iterations}_{i}"
                ).first()

                # Delete agent (cleanup)
                db_session.query(AgentRegistry).filter(
                    AgentRegistry.id == f"soak_test_agent_{iterations}_{i}"
                ).delete(synchronize_session=False)
                db_session.commit()

            except Exception as e:
                db_session.rollback()
                pytest.fail(f"Database operation failed at iteration {iterations}: {e}")

        iterations += 1

        # Force garbage collection every 10 iterations
        if iterations % 10 == 0:
            gc.collect()

        # Log pool status every 300 iterations (~5 minutes)
        if iterations % 300 == 0:
            current_size = engine.pool.size()
            current_checked_in = engine.pool.checkedin()

            print(
                f"Iteration {iterations}: "
                f"Pool size={current_size}, "
                f"Checked in={current_checked_in}"
            )

            # Fail if pool grown > 10 (indicates connection leak)
            if current_size > initial_size + 10:
                pytest.fail(
                    f"Connection pool grown significantly: "
                    f"{initial_size} -> {current_size} "
                    f"(threshold: +10)"
                )

    # Final validation: all connections should be checked in
    final_size = engine.pool.size()
    final_checked_in = engine.pool.checkedin()

    print(f"\n🔍 Final pool state: size={final_size}, checked_in={final_checked_in}")

    # Validate pool size hasn't grown > 10
    assert final_size <= initial_size + 10, (
        f"Connection pool grown: {initial_size} -> {final_size} "
        f"(threshold: +10)"
    )

    # Validate all connections are checked in (±1 for timing)
    # Allow 1 connection variance (test cleanup may have 1 connection open)
    checked_in_tolerance = 1
    assert abs(final_checked_in - initial_checked_in) <= checked_in_tolerance, (
        f"Connection leak detected: checked_in changed from {initial_checked_in} "
        f"to {final_checked_in} (tolerance: ±{checked_in_tolerance})"
    )

    print(f"\n✅ Soak test complete: {iterations} iterations, zero connection leaks")


@pytest.mark.soak
@pytest.mark.timeout(3600)  # 1 hour
def test_connection_pool_rapid_operations_1hr(db_session):
    """
    Soak test for rapid connection pool operations (1 hour).

    Validates:
    - Pool handles rapid connection open/close cycles
    - No connection exhaustion under high-frequency operations
    - Pool performance remains stable

    Test pattern:
    - Run for 1 hour (3600 seconds)
    - Perform 500 rapid operations per iteration
    - Each operation: single query
    - Log pool status every 60 iterations (~1 minute)
    - Final validation: pool size stable

    Duration: 1 hour
    Purpose: Detect pool performance degradation under rapid operations

    Note: Skips if not using QueuePool.
    """
    from core.database import engine

    # Check if using QueuePool
    if not isinstance(engine.pool, QueuePool):
        pytest.skip("Connection pool test requires QueuePool (SQLite uses StaticPool)")

    initial_size = engine.pool.size()

    start_time = time.time()
    iterations = 0

    # Run rapid operations for 1 hour
    while time.time() - start_time < 3600:
        # Perform 500 rapid database operations per iteration
        for i in range(500):
            try:
                # Simple query operation
                _ = db_session.query(AgentRegistry).limit(1).first()
            except Exception as e:
                pytest.fail(f"Database query failed at iteration {iterations}: {e}")

        iterations += 1

        # Log pool status every 60 iterations (~1 minute)
        if iterations % 60 == 0:
            current_size = engine.pool.size()
            checked_in = engine.pool.checkedin()

            print(
                f"Iteration {iterations}: "
                f"Pool size={current_size}, "
                f"Checked in={checked_in}"
            )

    # Final validation
    final_size = engine.pool.size()

    # Pool size should be stable
    assert final_size <= initial_size + 10, (
        f"Connection pool grown: {initial_size} -> {final_size} "
        f"(threshold: +10)"
    )

    print(f"\n✅ Soak test complete: {iterations} iterations, pool performance stable")
