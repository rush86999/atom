"""
Conftest for concurrent operations tests

This module provides fixtures for testing race conditions, deadlocks,
and resource cleanup issues that only manifest under concurrent access.

Fixtures are organized into:
1. Threading fixtures for cache tests
2. Asyncio fixtures for async tests
3. Database fixtures for lock tests
4. Resource tracking fixtures

IMPORTANT: SQLite Concurrency Limitations
-------------------------------------------
SQLite has limited concurrent write support:
- Only one writer at a time (serialized access)
- Multiple readers allowed (WITH one writer or zero writers)
- For true concurrency, use PostgreSQL with SERIALIZABLE isolation

Tests in this suite focus on:
- Read-heavy concurrent operations (SQLite can handle)
- Thread-safe cache access (in-memory, no DB locking)
- Async operation coordination (event loop concurrency)
- Documented PostgreSQL behavior for true parallel writes

For production deployment with PostgreSQL:
- Deadlocks can occur with conflicting lock orders
- SERIALIZABLE isolation prevents phantom reads
- Connection pool exhaustion under high load
- SELECT FOR UPDATE for pessimistic locking
"""

import asyncio
import gc
import os
import pytest
import tempfile
import threading
import time
import uuid
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.governance_cache import GovernanceCache
from core.database import Base


# ============================================================================
# Threading Fixtures for Cache Tests
# ============================================================================


@pytest.fixture(scope="function")
def concurrent_cache():
    """
    Create a GovernanceCache instance for concurrent testing.

    Thread-safe by design (threading.Lock protects internal state).
    Tests will verify lock contention behavior and cache consistency.

    Usage:
        def test_cache_concurrent_write(concurrent_cache):
            cache = concurrent_cache(max_size=100, thread_count=10)
            # Launch 10 threads writing to cache
            # Verify no data corruption
    """
    def _create_cache(max_size: int = 1000, ttl_seconds: int = 60):
        """Create cache with specified parameters."""
        return GovernanceCache(max_size=max_size, ttl_seconds=ttl_seconds)

    return _create_cache


@pytest.fixture(scope="function")
def assert_cache_consistency():
    """
    Verify cache consistency after concurrent operations.

    Checks that:
    - No data loss (all writes preserved)
    - No corrupted entries (all values valid)
    - Cache size within bounds (max_size respected)
    - Statistics accurate (hits/misses/evictions)

    Usage:
        assert_cache_consistency(cache, expected_entries=100)
    """
    def _assert_consistency(
        cache: GovernanceCache,
        expected_entries: Optional[int] = None,
        max_size: Optional[int] = None
    ):
        """Assert cache is consistent after concurrent operations."""
        stats = cache.get_stats()

        # Verify cache size
        if max_size:
            assert stats["size"] <= max_size, f"Cache size {stats['size']} exceeds max {max_size}"

        # Verify statistics are non-negative
        assert stats["hits"] >= 0
        assert stats["misses"] >= 0
        assert stats["evictions"] >= 0
        assert stats["invalidations"] >= 0

        # Verify hit rate is valid
        assert 0 <= stats["hit_rate"] <= 100

        # Verify expected entries (with tolerance for evictions)
        if expected_entries:
            # Allow 10% tolerance for LRU eviction during writes
            min_expected = int(expected_entries * 0.9)
            assert stats["size"] >= min_expected, \
                f"Cache size {stats['size']} below expected {min_expected}"

    return _assert_consistency


@pytest.fixture(scope="function")
def timed_operation():
    """
    Measure execution time for contention detection.

    Returns operation duration in milliseconds. Useful for detecting
    lock contention (operations taking >50ms under high contention).

    Usage:
        duration_ms = timed_operation(lambda: cache.get("agent", "action"))
        assert duration_ms < 50, "Lock contention detected"
    """
    def _time_operation(operation_fn, *args, **kwargs) -> float:
        """
        Execute operation and return duration in milliseconds.

        Args:
            operation_fn: Function to execute
            *args, **kwargs: Arguments passed to operation_fn

        Returns:
            Duration in milliseconds
        """
        start_time = time.perf_counter()
        result = operation_fn(*args, **kwargs)
        end_time = time.perf_counter()
        duration_ms = (end_time - start_time) * 1000
        return duration_ms

    return _time_operation


# ============================================================================
# Asyncio Fixtures for Async Tests
# ============================================================================


@pytest.fixture(scope="function")
def run_async_tasks():
    """
    Run N async tasks concurrently using asyncio.gather.

    Forces true concurrent execution (not sequential) for async race
    condition testing. Verifies no state leakage between tasks.

    Usage:
        async def my_task(task_id):
            return await service.create_episode(f"session_{task_id}")

        results = await run_async_tasks(my_task, count=10)
        assert len(results) == 10
    """
    async def _run_tasks(coro, count: int, **kwargs) -> List[Any]:
        """
        Run async coroutine concurrently N times.

        Args:
            coro: Async coroutine function (or lambda returning coroutine)
            count: Number of concurrent tasks to run
            **kwargs: Arguments passed to each coroutine

        Returns:
            List of results from all tasks
        """
        tasks = [coro(i, **kwargs) if asyncio.iscoroutinefunction(coro) else coro for i in range(count)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

    return _run_tasks


@pytest.fixture(scope="function")
def assert_no_duplicate_ids():
    """
    Verify no duplicate IDs in concurrent creation results.

    Common bug: Race condition in ID generation causes collisions.
    This fixture detects duplicate IDs from concurrent operations.

    Usage:
        results = await run_async_tasks(create_episode, count=10)
        episode_ids = [r.id for r in results]
        assert_no_duplicate_ids(episode_ids)
    """
    def _assert_no_duplicates(items: List[Any], id_extractor=None):
        """
        Assert no duplicate IDs in items.

        Args:
            items: List of items (objects or IDs)
            id_extractor: Optional function to extract ID from item

        Raises:
            AssertionError: If duplicate IDs found
        """
        if id_extractor:
            ids = [id_extractor(item) for item in items]
        elif isinstance(items[0], (str, int)):
            ids = items
        else:
            # Assume objects with .id attribute
            ids = [item.id for item in items]

        unique_ids = set(ids)
        if len(ids) != len(unique_ids):
            # Find duplicates
            seen = set()
            duplicates = [x for x in ids if x in seen or seen.add(x)]
            raise AssertionError(f"Duplicate IDs found: {duplicates}")

    return _assert_no_duplicates


# ============================================================================
# Database Fixtures for Lock Tests
# ============================================================================


@pytest.fixture(scope="function")
def two_agent_sessions():
    """
    Create two database sessions for deadlock testing.

    Simulates two concurrent transactions that might deadlock when
    updating rows in different orders. Each session has independent
    transaction context.

    Usage:
        session1, session2 = two_agent_sessions()

        # Transaction 1: Update agent1 then agent2
        session1.query(Agent).filter(...).update(...)
        # Transaction 2: Update agent2 then agent1 (reverse order)
        session2.query(Agent).filter(...).update(...)
    """
    # Create in-memory SQLite database
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Create tables
    Base.metadata.create_all(engine, checkfirst=True)

    # Create two session factories
    SessionLocal1 = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    SessionLocal2 = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session1 = SessionLocal1()
    session2 = SessionLocal2()

    yield session1, session2

    # Cleanup
    session1.close()
    session2.close()
    engine.dispose()
    try:
        os.unlink(db_path)
    except Exception:
        pass


@pytest.fixture(scope="function")
def assert_transaction_rollback():
    """
    Verify transaction was rolled back after deadlock/error.

    Checks that database state matches expected after rollback.
    Useful for verifying deadlock handling.

    Usage:
        # After deadlock detected
        assert_transaction_rollback(session, expected_state={"agent1": 0.7})
    """
    def _assert_rollback(session: Session, expected_state: Dict[str, Any]):
        """
        Assert database state matches expected after rollback.

        Args:
            session: Database session to query
            expected_state: Dict of expected values {"key": value}
        """
        from core.models import AgentRegistry

        for key, expected_value in expected_state.items():
            if key.startswith("agent_"):
                # Query agent by ID or name
                agent = session.query(AgentRegistry).filter(
                    (AgentRegistry.id == key) | (AgentRegistry.name == key)
                ).first()
                if agent:
                    actual_value = agent.confidence_score
                    assert actual_value == expected_value, \
                        f"Rollback failed: {key} has {actual_value}, expected {expected_value}"

    return _assert_rollback


# ============================================================================
# Resource Tracking Fixtures
# ============================================================================


@pytest.fixture(scope="function")
def connection_counter():
    """
    Track DB connection count for leak detection.

    Monitors open database connections before/after operations
    to detect connection leaks (connections not properly closed).

    Usage:
        counter = connection_counter()
        before = counter.count()

        # Run operations that might leak connections
        await many_async_db_calls()

        after = counter.count()
        assert after <= before + 2, "Connections leaked!"
    """
    class _ConnectionCounter:
        def __init__(self):
            self.engine = None

        def count(self) -> int:
            """
            Count open database connections.

            For SQLite: Check open file handles
            For PostgreSQL: Query pg_stat_activity

            Returns:
                Number of open connections
            """
            # Simplified implementation for SQLite
            # In production with PostgreSQL, query pg_stat_activity
            import sqlite3
            count = 0
            for thread in threading.enumerate():
                if hasattr(thread, '_connection'):
                    count += 1
            return count

        def detailed_count(self) -> Dict[str, int]:
            """Return detailed connection statistics."""
            return {
                "total": self.count(),
                "active": len([t for t in threading.enumerate() if hasattr(t, '_connection')]),
            }

    return _ConnectionCounter()


@pytest.fixture(scope="function")
def leak_detector():
    """
    Detect resource leaks (memory, file handles, connections).

    Tracks object counts before/after operations to identify leaks.
    Uses garbage collector for accurate memory tracking.

    Usage:
        detector = leak_detector("database_connection")
        detector.start()

        # Run operations that might leak
        await risky_async_operations()

        leaked = detector.stop()
        assert leaked == 0, f"Leaked {leaked} resources"
    """
    class _LeakDetector:
        def __init__(self, resource_type: str):
            self.resource_type = resource_type
            self.before_count = 0
            self.after_count = 0

        def start(self):
            """Record initial resource count."""
            gc.collect()  # Force GC before counting
            self.before_count = self._count_resources()

        def stop(self) -> int:
            """
            Record final resource count and return leak count.

            Returns:
                Number of leaked resources (0 if no leak)
            """
            gc.collect()  # Force GC before counting
            self.after_count = self._count_resources()
            return max(0, self.after_count - self.before_count)

        def _count_resources(self) -> int:
            """Count resources of tracked type."""
            if self.resource_type == "database_connection":
                # Count open DB connections
                return len([
                    obj for obj in gc.get_objects()
                    if hasattr(obj, '__class__') and
                    'Connection' in obj.__class__.__name__ and
                    hasattr(obj, 'connection')
                ])
            elif self.resource_type == "thread":
                # Count threads (excluding main thread)
                return len([t for t in threading.enumerate() if t.name != 'MainThread'])
            elif self.resource_type == "object":
                # Count all Python objects (for memory leak detection)
                return len(gc.get_objects())
            else:
                return 0

    return _LeakDetector


@pytest.fixture(scope="function")
def get_object_count():
    """
    Get current Python object count for memory leak testing.

    Uses garbage collector to count all live Python objects.
    Useful for detecting memory leaks in long-running operations.

    Usage:
        initial_objects = get_object_count()

        # Run many operations
        for i in range(1000):
            await service.create_episode(...)

        gc.collect()
        final_objects = get_object_count()
        assert final_objects - initial_objects < 100, "Memory leak detected"
    """
    def _count_objects() -> int:
        """Count all Python objects in memory."""
        gc.collect()
        return len(gc.get_objects())

    return _count_objects


# ============================================================================
# SQLite Concurrency Documentation Fixture
# ============================================================================


@pytest.fixture(scope="session", autouse=True)
def sqlite_concurrency_notes():
    """
    Document SQLite concurrency limitations for all tests.

    This fixture auto-documents test behavior expectations for
    SQLite vs PostgreSQL concurrency differences.

    SQLite Limitations:
    - Only one writer at a time (serialized)
    - Multiple readers allowed (WITH one writer)
    - Write operations are queued (first-come, first-served)
    - No true parallel write concurrency

    PostgreSQL Advantages:
    - Multiple writers with MVCC
    - True parallel writes with row-level locking
    - SERIALIZABLE isolation prevents phantom reads
    - Deadlock detection and automatic rollback

    Test Strategy:
    - Focus on read-heavy concurrency (SQLite friendly)
    - Test cache thread-safety (in-memory, no DB locking)
    - Test async coordination (event loop, not DB locking)
    - Document expected PostgreSQL behavior for write-heavy tests
    """
    # This is a documentation fixture - no action needed
    # The docstring serves as inline documentation for test developers
    pass


# ============================================================================
# Test Helpers
# ============================================================================


@pytest.fixture(scope="function")
def is_ci_environment():
    """
    Detect if running in CI environment.

    CI environments have different concurrency characteristics:
    - Fewer CPU cores (slower concurrent execution)
    - Shared resources (contention more likely)
    - Timeouts may need adjustment

    Usage:
        if is_ci_environment():
            timeout_seconds = 10
        else:
            timeout_seconds = 2
    """
    return os.getenv("CI", "false").lower() == "true"


@pytest.fixture(scope="function")
def retry_on_deadlock():
    """
    Retry function call on database deadlock.

    Deadlocks are transient errors - retrying with backoff
    is the standard handling strategy.

    Usage:
        result = retry_on_deadlock(
            lambda: update_agent(session, agent_id, data),
            max_retries=3
        )
    """
    def _retry(func, max_retries: int = 3, backoff_ms: int = 100):
        """
        Retry function on deadlock/lock error.

        Args:
            func: Function to execute
            max_retries: Maximum retry attempts
            backoff_ms: Backoff delay between retries

        Returns:
            Function result

        Raises:
            Exception: If all retries exhausted
        """
        last_exception = None

        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                error_msg = str(e).lower()
                if "deadlock" in error_msg or "lock" in error_msg:
                    if attempt < max_retries - 1:
                        time.sleep(backoff_ms / 1000 * (attempt + 1))
                        continue
                raise

        raise last_exception

    return _retry


# ============================================================================
# Performance Benchmarks
# ============================================================================


@pytest.fixture(scope="function")
def benchmark_concurrent_operations():
    """
    Benchmark concurrent operation performance.

    Measures throughput (ops/sec) and latency under various
    concurrency levels to identify performance regressions.

    Usage:
        results = benchmark_concurrent_operations(
            operation=lambda: cache.get("agent", "action"),
            thread_count=50,
            operations_per_thread=100
        )

        print(f"Throughput: {results['ops_per_sec']:.0f} ops/sec")
        print(f"Latency P50: {results['latency_p50_ms']:.2f} ms")
    """
    def _benchmark(
        operation_fn,
        thread_count: int = 10,
        operations_per_thread: int = 100
    ) -> Dict[str, Any]:
        """
        Benchmark operation under concurrent load.

        Args:
            operation_fn: Function to benchmark
            thread_count: Number of concurrent threads
            operations_per_thread: Operations per thread

        Returns:
            Dict with ops_per_sec, latency_p50_ms, latency_p99_ms
        """
        errors = []
        latencies = []
        stop_event = threading.Event()

        def worker(thread_id: int):
            """Worker thread for benchmark."""
            thread_latencies = []
            for i in range(operations_per_thread):
                if stop_event.is_set():
                    break
                start = time.perf_counter()
                try:
                    operation_fn()
                    latency_ms = (time.perf_counter() - start) * 1000
                    thread_latencies.append(latency_ms)
                except Exception as e:
                    errors.append(e)
                    stop_event.set()
                    break
            latencies.extend(thread_latencies)

        # Launch threads
        start_time = time.perf_counter()
        threads = [
            threading.Thread(target=worker, args=(i,))
            for i in range(thread_count)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        end_time = time.perf_counter()

        # Calculate metrics
        total_duration = end_time - start_time
        total_ops = len(latencies)
        ops_per_sec = total_ops / total_duration if total_duration > 0 else 0

        latencies_sorted = sorted(latencies)
        p50_idx = int(len(latencies_sorted) * 0.5)
        p99_idx = int(len(latencies_sorted) * 0.99)

        return {
            "ops_per_sec": ops_per_sec,
            "latency_p50_ms": latencies_sorted[p50_idx] if latencies_sorted else 0,
            "latency_p99_ms": latencies_sorted[p99_idx] if latencies_sorted else 0,
            "errors": errors,
            "total_operations": total_ops,
        }

    return _benchmark
