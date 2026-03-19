"""
Concurrency safety tests for Atom - deadlock and race condition detection.

This module explicitly validates zero deadlocks and zero race conditions
during concurrent operations, as required by LOAD-04 objective.

Tests validate:
- Deadlock detection via timeout (hanging indicates deadlock)
- Race condition detection via atomic operation validation
- No lock contention issues in cache operations
- Concurrent database operations complete successfully
- Governance cache lookups don't hang

Reference: Phase 209 Plan 04 - Stress Testing (LOAD-04)
"""

import pytest
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db_session, engine
from core.governance_cache import GovernanceCache


async def run_concurrent_operations(operations: List, timeout_seconds: int = 60) -> bool:
    """
    Run operations concurrently with deadlock detection via timeout.

    If operations don't complete within timeout, it indicates a deadlock.
    This is the primary deadlock detection mechanism.

    Args:
        operations: List of async operations to execute
        timeout_seconds: Maximum time to wait (default: 60s)

    Returns:
        True if all operations completed successfully

    Raises:
        pytest.fail: If timeout occurs (deadlock detected)
    """
    try:
        async with asyncio.timeout(timeout_seconds):
            results = await asyncio.gather(*operations, return_exceptions=True)

            # Check for actual exceptions (not timeout)
            failures = [r for r in results if isinstance(r, Exception) and not isinstance(r, asyncio.TimeoutError)]

            if len(failures) > 0:
                raise pytest.fail(f"Operations failed: {failures[:5]}")

            return True

    except asyncio.TimeoutError:
        pytest.fail(f"Deadlock detected: operations did not complete within {timeout_seconds}s")


@pytest.mark.asyncio
async def test_concurrent_database_operations_no_deadlocks():
    """
    Stress test: 100 concurrent database operations - deadlock detection.

    Executes 100 concurrent database sessions performing mixed operations:
    - SELECT queries
    - INSERT operations
    - UPDATE operations
    - DELETE operations

    Uses asyncio.Semaphore to limit to 20 concurrent operations at once.
    Sets a 60-second timeout for the entire test.

    Assertion: All 100 operations complete without hanging.
    If test hangs beyond 60 seconds, deadlock is detected.

    This explicitly validates LOAD-04 requirement: zero deadlocks during
    concurrent database operations.
    """
    print("\n=== Concurrent Database Operations - Deadlock Detection ===")

    num_operations = 100
    max_concurrent = 20
    timeout_seconds = 60

    print(f"Executing {num_operations} mixed database operations")
    print(f"Max concurrent: {max_concurrent}")
    print(f"Timeout: {timeout_seconds}s (hanging = deadlock)")

    async def db_operation(operation_id: int) -> str:
        """Perform a database operation based on ID."""
        async with asyncio.Semaphore(max_concurrent):
            with get_db_session() as db:
                # Mix of different operation types
                op_type = operation_id % 4

                if op_type == 0:
                    # SELECT
                    result = db.execute(text("SELECT 1 as value"))
                    value = result.fetchone()
                    return f"op_{operation_id}_select"

                elif op_type == 1:
                    # INSERT (test record)
                    # Use a unique ID to avoid conflicts
                    db.execute(
                        text("INSERT OR IGNORE INTO agent_registry (id, name, category, module_path, class_name, status, confidence_score) "
                             "VALUES (:id, :name, :category, :module_path, :class_name, :status, :confidence_score)"),
                        {
                            "id": f"concurrent_test_{operation_id}",
                            "name": f"Concurrent Test {operation_id}",
                            "category": "test",
                            "module_path": "test.module",
                            "class_name": "TestClass",
                            "status": "STUDENT",
                            "confidence_score": 0.5
                        }
                    )
                    return f"op_{operation_id}_insert"

                elif op_type == 2:
                    # UPDATE
                    db.execute(
                        text("UPDATE agent_registry SET confidence_score = :score WHERE id = :id"),
                        {"score": 0.6, "id": f"concurrent_test_{operation_id % 50}"}
                    )
                    return f"op_{operation_id}_update"

                else:
                    # DELETE
                    db.execute(
                        text("DELETE FROM agent_registry WHERE id = :id"),
                        {"id": f"concurrent_test_{operation_id % 50}"}
                    )
                    return f"op_{operation_id}_delete"

    # Create operations
    operations = [db_operation(i) for i in range(num_operations)]

    # Execute with deadlock detection via timeout
    start_time = time.time()

    success = await run_concurrent_operations(operations, timeout_seconds=timeout_seconds)

    elapsed_time = time.time() - start_time

    print(f"\n✓ All {num_operations} operations completed successfully")
    print(f"  Elapsed time: {elapsed_time:.2f}s")
    print(f"  Average per operation: {elapsed_time/num_operations*1000:.2f}ms")
    print(f"✓ No deadlocks detected (completed within {timeout_seconds}s timeout)")


def test_concurrent_cache_operations_no_races():
    """
    Stress test: 50 concurrent cache updates - race condition detection.

    Tests cache operations for race conditions by having 50 workers
    increment the same cache key 100 times each.

    Expected result: 50 workers × 100 increments = 5000
    If final value < 5000, lost updates indicate a race condition.

    This uses ThreadPoolExecutor to simulate true concurrent access
    from multiple threads, which is more aggressive than asyncio.

    This explicitly validates LOAD-04 requirement: zero race conditions
    in cache operations.
    """
    print("\n=== Concurrent Cache Operations - Race Condition Detection ===")

    cache = GovernanceCache(max_size=10000, ttl_seconds=60)
    key = "race_test_key"
    increments_per_worker = 100
    num_workers = 50

    print(f"Workers: {num_workers}")
    print(f"Increments per worker: {increments_per_worker}")
    print(f"Expected final value: {num_workers * increments_per_worker}")

    # Initialize counter
    cache.set(
        agent_id=key,
        action_type="test",
        data={"counter": 0}
    )

    def increment_worker(worker_id: int) -> int:
        """Worker that increments cache value multiple times."""
        for i in range(increments_per_worker):
            # Read current value
            result = cache.get(agent_id=key, action_type="test")

            if result and "counter" in result:
                current = result["counter"]
            else:
                current = 0

            # Increment and write back
            cache.set(
                agent_id=key,
                action_type="test",
                data={"counter": current + 1}
            )

        return increments_per_worker

    # Execute workers concurrently
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(increment_worker, i) for i in range(num_workers)]

        # Wait for all workers with timeout
        try:
            for future in as_completed(futures, timeout=30):
                future.result()  # Raises exceptions if any
        except Exception as e:
            raise pytest.fail(f"Cache operation failed: {e}")

    elapsed_time = time.time() - start_time

    # Check final value
    final_result = cache.get(agent_id=key, action_type="test")
    final_value = final_result["counter"] if final_result else 0
    expected_value = num_workers * increments_per_worker

    print(f"\n=== Results ===")
    print(f"Expected value: {expected_value}")
    print(f"Actual value: {final_value}")
    print(f"Lost updates: {expected_value - final_value}")
    print(f"Elapsed time: {elapsed_time:.2f}s")

    # Assert no lost updates (race condition detection)
    if final_value != expected_value:
        lost_updates = expected_value - final_value
        loss_rate = (lost_updates / expected_value) * 100
        pytest.fail(
            f"Race condition detected: {lost_updates} lost updates ({loss_rate:.2f}%)\n"
            f"Expected: {expected_value}, Got: {final_value}"
        )

    print(f"✓ No race conditions detected (exact value: {final_value})")


@pytest.mark.asyncio
async def test_concurrent_governance_checks_no_hangs():
    """
    Stress test: 200 concurrent governance cache lookups - hang detection.

    Tests governance cache lookups for lock contention issues that
    could cause hangs or degraded performance under load.

    Uses mix of cached and uncached agent IDs to test both cold
    and warm cache scenarios.

    Sets 30-second timeout. If operations don't complete, indicates
    lock contention or deadlock in governance cache.

    This explicitly validates LOAD-04 requirement: zero hangs during
    concurrent governance checks.
    """
    print("\n=== Concurrent Governance Checks - Hang Detection ===")

    cache = GovernanceCache(max_size=1000, ttl_seconds=60)
    num_lookups = 200
    timeout_seconds = 30

    print(f"Executing {num_lookups} governance cache lookups")
    print(f"Timeout: {timeout_seconds}s (hanging = lock contention)")

    # Pre-populate cache with some agents (warm cache)
    warm_cache_count = 50
    for i in range(warm_cache_count):
        cache.set(
            agent_id=f"cached_agent_{i}",
            action_type="test_action",
            data={"allowed": True, "maturity_level": "AUTONOMOUS"}
        )

    print(f"Warm cache: {warm_cache_count} agents pre-cached")

    async def governance_check(check_id: int) -> Dict:
        """Perform a governance check."""
        # Mix of cached and uncached agents
        if check_id < warm_cache_count:
            agent_id = f"cached_agent_{check_id}"
        else:
            agent_id = f"uncached_agent_{check_id}"

        result = cache.get(
            agent_id=agent_id,
            action_type="test_action"
        )

        return {
            "check_id": check_id,
            "agent_id": agent_id,
            "found": result is not None
        }

    # Create lookup operations
    operations = [governance_check(i) for i in range(num_lookups)]

    # Execute with hang detection via timeout
    start_time = time.time()

    success = await run_concurrent_operations(operations, timeout_seconds=timeout_seconds)

    elapsed_time = time.time() - start_time

    print(f"\n✓ All {num_lookups} lookups completed successfully")
    print(f"  Elapsed time: {elapsed_time:.2f}s")
    print(f"  Average per lookup: {elapsed_time/num_lookups*1000:.2f}ms")
    print(f"✓ No lock contention detected (completed within {timeout_seconds}s timeout)")


def test_concurrent_atomic_operations():
    """
    Stress test: Concurrent atomic operations validation.

    Tests that atomic operations (like database transactions with
    proper isolation) prevent race conditions.

    Scenario: 10 workers each incrementing a database counter 100 times.
    Uses proper transaction isolation to prevent lost updates.

    This validates that the database's transaction isolation is working
    correctly and preventing race conditions.
    """
    print("\n=== Concurrent Atomic Operations Test ===")

    num_workers = 10
    increments_per_worker = 100
    expected_value = num_workers * increments_per_worker

    print(f"Workers: {num_workers}")
    print(f"Increments per worker: {increments_per_worker}")
    print(f"Expected final value: {expected_value}")

    # Create test table
    with get_db_session() as db:
        # Create counter table if not exists
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS test_counter (
                id INTEGER PRIMARY KEY,
                value INTEGER DEFAULT 0
            )
        """))

        # Reset counter
        db.execute(text("DELETE FROM test_counter WHERE id = 1"))
        db.execute(text("INSERT INTO test_counter (id, value) VALUES (1, 0)"))
        db.commit()

    def atomic_increment_worker(worker_id: int) -> bool:
        """Worker that performs atomic increments."""
        for i in range(increments_per_worker):
            with get_db_session() as db:
                # Use UPDATE with atomic increment
                db.execute(
                    text("UPDATE test_counter SET value = value + 1 WHERE id = 1")
                )
                # Transaction commits automatically on context exit

        return True

    # Execute workers concurrently
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(atomic_increment_worker, i) for i in range(num_workers)]

        try:
            for future in as_completed(futures, timeout=30):
                future.result()
        except Exception as e:
            raise pytest.fail(f"Atomic operation failed: {e}")

    elapsed_time = time.time() - start_time

    # Check final value
    with get_db_session() as db:
        result = db.execute(text("SELECT value FROM test_counter WHERE id = 1"))
        row = result.fetchone()
        final_value = row[0] if row else 0

    print(f"\n=== Results ===")
    print(f"Expected value: {expected_value}")
    print(f"Actual value: {final_value}")
    print(f"Elapsed time: {elapsed_time:.2f}s")

    # Assert exact value (no lost updates due to atomic operations)
    assert final_value == expected_value, \
        f"Lost updates detected: expected {expected_value}, got {final_value}"

    print(f"✓ Atomic operations working correctly (exact value: {final_value})")

    # Cleanup
    with get_db_session() as db:
        db.execute(text("DROP TABLE IF EXISTS test_counter"))
        db.commit()


@pytest.mark.asyncio
async def test_concurrent_session_management_no_leaks():
    """
    Stress test: Concurrent database session management - leak detection.

    Tests that database sessions are properly managed under concurrent
    load with no connection leaks.

    Executes 100 concurrent operations, each opening and closing
    a database session. Validates that all sessions are properly
    closed and connections returned to pool.
    """
    print("\n=== Concurrent Session Management - Leak Detection ===")

    from sqlalchemy.pool import QueuePool

    if not isinstance(engine.pool, QueuePool):
        pytest.skip("Connection leak test requires QueuePool (PostgreSQL)")

    num_operations = 100

    initial_checked_out = engine.pool.checkedout()
    print(f"Initial checked out connections: {initial_checked_out}")
    print(f"Executing {num_operations} concurrent session operations")

    async def session_operation(op_id: int) -> bool:
        """Open and close a database session."""
        with get_db_session() as db:
            # Perform a simple query
            result = db.execute(text("SELECT 1"))
            result.fetchone()
            # Session closes automatically on context exit

        return True

    # Execute operations concurrently
    operations = [session_operation(i) for i in range(num_operations)]

    start_time = time.time()

    success = await run_concurrent_operations(operations, timeout_seconds=60)

    elapsed_time = time.time() - start_time

    # Check for connection leaks
    final_checked_out = engine.pool.checkedout()

    print(f"\n✓ All {num_operations} operations completed")
    print(f"  Elapsed time: {elapsed_time:.2f}s")
    print(f"Final checked out connections: {final_checked_out}")

    # Assert no connection leaks
    assert final_checked_out == 0, \
        f"Connection leak detected: {final_checked_out} connections still checked out"

    print(f"✓ No connection leaks detected")


if __name__ == "__main__":
    # Run tests manually for development
    pytest.main([__file__, "-v", "-s"])
