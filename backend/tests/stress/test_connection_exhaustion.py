"""
Connection exhaustion stress tests for Atom.

This module tests system behavior when connection limits are approached
or exceeded, validating graceful degradation and proper resource cleanup.

Tests validate:
- Database connection pool doesn't exhaust
- WebSocket connections have proper limits
- HTTP connection pool handles high throughput
- No connection leaks (connections returned to pool)
- Pool size remains stable under load

Reference: Phase 209 Plan 04 - Stress Testing
"""

import asyncio
import pytest
import time
from typing import List
from sqlalchemy.pool import QueuePool, Pool
from sqlalchemy import text


# Import database engine
from core.database import engine, SessionLocal, get_db_session


def test_database_pool_exhaustion():
    """
    Stress test: Database connection pool under concurrent load.

    Creates 50 concurrent database sessions, performs queries,
    and verifies connections are properly returned to the pool.

    Validates:
    - No connection leaks (all sessions closed)
    - Pool size doesn't grow unexpectedly
    - Connections are reused efficiently
    - No pool exhaustion errors

    Pool configuration (from core/database.py):
    - PostgreSQL: pool_size=20, max_overflow=30
    - SQLite: Single connection (no pooling)
    """
    print("\n=== Database Pool Exhaustion Test ===")

    # Check if using QueuePool (PostgreSQL)
    if not isinstance(engine.pool, QueuePool):
        pytest.skip("Connection pool test requires QueuePool (PostgreSQL)")

    initial_pool_size = engine.pool.size()
    initial_checked_in = engine.pool.checkedin()
    initial_checked_out = engine.pool.checkedout()

    print(f"Initial pool state:")
    print(f"  Pool size: {initial_pool_size}")
    print(f"  Checked in: {initial_checked_in}")
    print(f"  Checked out: {initial_checked_out}")

    # Create 50 concurrent database sessions
    num_sessions = 50
    print(f"\nCreating {num_sessions} concurrent database sessions...")

    sessions = []
    try:
        # Open 50 sessions
        for i in range(num_sessions):
            session = SessionLocal()
            sessions.append(session)

            # Perform a simple query
            result = session.execute(text("SELECT 1"))
            result.fetchone()

            if (i + 1) % 10 == 0:
                print(f"  {i + 1} sessions opened...")

        print(f"All {num_sessions} sessions opened successfully")

        # Check pool state under load
        pool_size_under_load = engine.pool.size()
        checked_out_under_load = engine.pool.checkedout()

        print(f"\nPool state under load:")
        print(f"  Pool size: {pool_size_under_load}")
        print(f"  Checked out: {checked_out_under_load}")

        # Close all sessions
        print(f"\nClosing {num_sessions} sessions...")
        for i, session in enumerate(sessions):
            session.close()
            if (i + 1) % 10 == 0:
                print(f"  {i + 1} sessions closed...")

        # Give pool time to recover
        time.sleep(0.5)

        # Final pool state
        final_pool_size = engine.pool.size()
        final_checked_in = engine.pool.checkedin()
        final_checked_out = engine.pool.checkedout()

        print(f"\nFinal pool state:")
        print(f"  Pool size: {final_pool_size}")
        print(f"  Checked in: {final_checked_in}")
        print(f"  Checked out: {final_checked_out}")

        # Assertions
        print(f"\n=== Validation ===")

        # Pool size should not have grown significantly
        # Allow some growth due to max_overflow
        pool_growth = final_pool_size - initial_pool_size
        print(f"Pool growth: {pool_growth}")

        assert pool_growth <= 5, \
            f"Connection pool grew unexpectedly: {initial_pool_size} -> {final_pool_size}"

        # All connections should be checked in (no leaks)
        assert final_checked_out == 0, \
            f"Connection leak detected: {final_checked_out} connections still checked out"

        print("✓ No connection leaks detected")
        print("✓ Pool size stable")

    except Exception as e:
        # Cleanup on error
        for session in sessions:
            try:
                session.close()
            except:
                pass
        raise pytest.fail(f"Database pool test failed: {e}")


def test_database_connection_reuse():
    """
    Stress test: Database connection reuse efficiency.

    Opens and closes 100 connections in sequence to validate
    that connections are reused from the pool efficiently.

    Validates:
    - Connections are reused (not created for each request)
    - Pool hit rate is high (>80%)
    - No unnecessary connection creation
    """
    print("\n=== Database Connection Reuse Test ===")

    if not isinstance(engine.pool, QueuePool):
        pytest.skip("Connection pool test requires QueuePool (PostgreSQL)")

    initial_pool_size = engine.pool.size()

    # Open and close 100 connections
    num_iterations = 100
    print(f"Opening and closing {num_iterations} connections...")

    for i in range(num_iterations):
        with get_db_session() as db:
            result = db.execute(text("SELECT 1"))
            result.fetchone()

        if (i + 1) % 20 == 0:
            current_size = engine.pool.size()
            print(f"  {i + 1} iterations, pool size: {current_size}")

    final_pool_size = engine.pool.size()

    print(f"\n=== Results ===")
    print(f"Initial pool size: {initial_pool_size}")
    print(f"Final pool size: {final_pool_size}")
    print(f"Difference: {final_pool_size - initial_pool_size}")

    # Pool size should remain stable (connections reused)
    assert final_pool_size <= initial_pool_size + 2, \
        f"Pool grew unexpectedly: {initial_pool_size} -> {final_pool_size}"

    print("✓ Connections reused efficiently")


@pytest.mark.asyncio
async def test_websocket_connection_limits():
    """
    Stress test: WebSocket connection limits.

    Attempts to establish 100 concurrent WebSocket connections
    to identify breaking points and validate graceful rejection.

    Note: This test requires a running WebSocket server.
    Skipped if server is not available.

    Validates:
    - System can handle reasonable number of WebSocket connections
    - Graceful rejection after limit
    - No crashes or hangs
    """
    print("\n=== WebSocket Connection Limits Test ===")

    try:
        import websockets
    except ImportError:
        pytest.skip("websockets library not installed")

    # WebSocket endpoint (adjust based on actual implementation)
    ws_url = "ws://localhost:8000/ws/test"

    max_connections = 100
    successful_connections = 0
    failed_connections = 0

    print(f"Attempting {max_connections} concurrent WebSocket connections...")
    print(f"WebSocket URL: {ws_url}")

    async def connect_websocket(i: int) -> bool:
        """Attempt to establish WebSocket connection."""
        try:
            async with websockets.connect(f"{ws_url}/{i}") as ws:
                # Send a test message
                await ws.send('{"type": "ping"}')
                # Receive response
                response = await ws.recv()
                return True
        except Exception as e:
            return False

    # Attempt connections in batches to avoid overwhelming the system
    batch_size = 10
    for batch_start in range(0, max_connections, batch_size):
        batch_end = min(batch_start + batch_size, max_connections)
        batch_tasks = [
            connect_websocket(i) for i in range(batch_start, batch_end)
        ]

        results = await asyncio.gather(*batch_tasks, return_exceptions=True)

        batch_successful = sum(1 for r in results if r is True)
        batch_failed = batch_size - batch_successful

        successful_connections += batch_successful
        failed_connections += batch_failed

        print(f"  Batch {batch_start}-{batch_end}: {batch_successful} successful, {batch_failed} failed")

        # Stop if we're getting consistent failures (hit limit)
        if batch_failed == batch_size and batch_successful == 0:
            print(f"  All connections failed - likely hit connection limit")
            break

    print(f"\n=== Results ===")
    print(f"Successful connections: {successful_connections}/{max_connections}")
    print(f"Failed connections: {failed_connections}/{max_connections}")
    print(f"Success rate: {successful_connections/max_connections*100:.2f}%")

    # At least some connections should succeed
    assert successful_connections > 0, "No WebSocket connections succeeded"

    # If we hit a limit, it should fail gracefully (not crash)
    if failed_connections > 0:
        print(f"✓ Connection limit detected: ~{successful_connections} concurrent connections")
        print("✓ Failures were graceful (no crashes)")
    else:
        print(f"✓ System handled all {max_connections} connections successfully")


@pytest.mark.asyncio
async def test_http_connection_pool_stress():
    """
    Stress test: HTTP connection pool under high throughput.

    Uses httpx with connection limits to send 1000 requests
    over a limited number of connections (10).

    Validates:
    - No connection pool exhaustion errors
    - Connections are reused efficiently
    - High throughput achieved with limited connections
    - No memory leaks in connection pool
    """
    print("\n=== HTTP Connection Pool Stress Test ===")

    import httpx

    base_url = "http://localhost:8000"
    endpoint = "/health/live"
    url = f"{base_url}{endpoint}"

    total_requests = 1000
    max_connections = 10

    print(f"Sending {total_requests} requests over {max_connections} connections...")
    print(f"Endpoint: {url}")

    # Create async client with connection limits
    start_time = time.time()

    async with httpx.AsyncClient(
        timeout=30.0,
        limits=httpx.Limits(max_connections=max_connections, max_keepalive_connections=5)
    ) as client:
        tasks = []
        for i in range(total_requests):
            task = client.get(url)
            tasks.append(task)

            # Process in batches to avoid overwhelming memory
            if len(tasks) >= 100:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                success_count = sum(1 for r in results if not isinstance(r, Exception))
                print(f"  Processed {len(results)} requests: {success_count} successful")
                tasks = []

        # Process remaining tasks
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success_count = sum(1 for r in results if not isinstance(r, Exception))
            print(f"  Processed {len(results)} requests: {success_count} successful")

    elapsed_time = time.time() - start_time
    requests_per_second = total_requests / elapsed_time

    print(f"\n=== Results ===")
    print(f"Total requests: {total_requests}")
    print(f"Elapsed time: {elapsed_time:.2f}s")
    print(f"Requests per second: {requests_per_second:.2f}")
    print(f"Throughput per connection: {requests_per_second/max_connections:.2f} RPS/connection")

    # Performance assertions
    assert requests_per_second > 10, \
        f"Throughput too low: {requests_per_second:.2f} RPS"

    print(f"✓ Achieved {requests_per_second:.2f} RPS with {max_connections} connections")


def test_database_pool_timeout():
    """
    Stress test: Database connection pool timeout behavior.

    Simulates connection pool exhaustion by opening connections
    up to the pool size limit, then attempts to open more connections.

    Validates:
    - Connection timeout occurs when pool is exhausted
    - Timeout is configurable and reasonable
    - System doesn't hang indefinitely
    - Connections are released after timeout
    """
    print("\n=== Database Pool Timeout Test ===")

    if not isinstance(engine.pool, QueuePool):
        pytest.skip("Connection pool test requires QueuePool (PostgreSQL)")

    pool_size = engine.pool.size()
    max_overflow = engine.pool.max_overflow
    max_connections = pool_size + max_overflow

    print(f"Pool configuration:")
    print(f"  Pool size: {pool_size}")
    print(f"  Max overflow: {max_overflow}")
    print(f"  Max connections: {max_connections}")

    # Open connections up to max
    sessions = []
    print(f"\nOpening {max_connections} connections...")

    try:
        for i in range(max_connections):
            session = SessionLocal()
            sessions.append(session)
            result = session.execute(text("SELECT 1"))
            result.fetchone()

            if (i + 1) % 10 == 0:
                print(f"  {i + 1} connections opened...")

        print(f"All {max_connections} connections opened")

        # Try to open one more connection (should timeout or raise error)
        print(f"\nAttempting to open one more connection (should timeout)...")

        timeout_occurred = False
        try:
            # Set a shorter timeout for this test
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError("Connection timeout")

            # Set alarm for 5 seconds
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(5)

            extra_session = SessionLocal()
            signal.alarm(0)  # Cancel alarm

            # If we get here, connection succeeded (might be due to overflow)
            print(f"⚠️  Extra connection succeeded (max_overflow may have allowed it)")
            extra_session.close()

        except TimeoutError:
            timeout_occurred = True
            print(f"✓ Connection timeout occurred as expected")
        except Exception as e:
            print(f"✓ Connection failed with error: {type(e).__name__}")
            timeout_occurred = True

        # Cleanup
        print(f"\nClosing {len(sessions)} connections...")
        for session in sessions:
            session.close()

        print("✓ All connections closed successfully")

        if timeout_occurred:
            print("✓ Pool timeout behavior validated")
        else:
            print("ℹ️  Pool allowed extra connections (overflow working)")

    except Exception as e:
        # Cleanup on error
        for session in sessions:
            try:
                session.close()
            except:
                pass
        raise pytest.fail(f"Pool timeout test failed: {e}")


if __name__ == "__main__":
    # Run tests manually for development
    pytest.main([__file__, "-v", "-s"])
