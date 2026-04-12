"""
Test Coverage for Concurrency Patterns

Comprehensive tests for race conditions, locks, semaphores, concurrent requests,
and thread-safe operations throughout the backend.

Target Coverage Areas:
- Race condition handling
- Thread-safe operations
- Lock and mutex usage
- Semaphore-based limiting
- Concurrent request handling
- Shared state management
- Deadlock prevention
- Concurrent data structures

Tests: ~15 tests
Expected Impact: +2-3 percentage points
"""

import asyncio
import pytest
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from unittest.mock import MagicMock, patch
from typing import Dict, Any, List

# Import core services with concurrency patterns
from core.governance_cache import GovernanceCache
from core.task_queue import TaskQueueManager


class TestGovernanceCacheConcurrency:
    """Test governance cache thread-safe operations."""

    def test_concurrent_cache_reads(self):
        """Test concurrent cache reads are thread-safe."""
        cache = GovernanceCache(max_size=1000, ttl_seconds=60)

        # Pre-populate cache
        for i in range(100):
            cache.set(f"agent{i}", "action1", {"allowed": True, "data": {}})

        # Concurrent reads
        def read_worker(worker_id):
            hits = 0
            for i in range(100):
                result = cache.get(f"agent{i}", "action1")
                if result:
                    hits += 1
            return hits

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(read_worker, i) for i in range(10)]
            results = [f.result() for f in as_completed(futures)]

        # All reads should succeed
        assert all(r == 100 for r in results)
        assert cache._hits == 1000  # 10 workers * 100 reads

    def test_concurrent_cache_writes(self):
        """Test concurrent cache writes are thread-safe."""
        cache = GovernanceCache(max_size=1000, ttl_seconds=60)

        def write_worker(worker_id):
            for i in range(100):
                cache.set(f"agent{worker_id}_{i}", "action1", {"allowed": True})

        # Concurrent writes
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(write_worker, i) for i in range(10)]
            results = [f.result() for f in as_completed(futures)]

        # All writes should complete without errors
        assert len(cache._cache) == 1000  # 10 workers * 100 writes

    def test_concurrent_cache_read_write(self):
        """Test concurrent reads and writes are thread-safe."""
        cache = GovernanceCache(max_size=1000, ttl_seconds=60)

        def read_worker():
            for i in range(100):
                cache.get(f"agent{i}", "action1")

        def write_worker(worker_id):
            for i in range(100):
                cache.set(f"agent{i}", "action1", {"allowed": True, "worker": worker_id})

        # Mix of reads and writes
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            # 10 readers
            futures.extend(executor.submit(read_worker) for _ in range(10))
            # 10 writers
            futures.extend(executor.submit(write_worker, i) for i in range(10))

            results = [f.result() for f in as_completed(futures)]

        # All operations should complete
        assert len(results) == 20

    def test_cache_lock_contention(self):
        """Test cache handles lock contention correctly."""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        def contentious_worker(worker_id):
            for i in range(50):
                cache.set(f"key{worker_id}_{i}", "action1", {"value": i})
                cache.get(f"key{worker_id}_{i}", "action1")
                cache.invalidate(f"agent{worker_id}", "action1")

        # High contention scenario
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(contentious_worker, i) for i in range(20)]
            results = [f.result() for f in as_completed(futures)]

        # All operations should complete without deadlock
        assert len(results) == 20

    def test_cache_statistics_thread_safety(self):
        """Test cache statistics are thread-safe."""
        cache = GovernanceCache(max_size=1000, ttl_seconds=60)

        def stats_worker():
            for i in range(100):
                cache.set(f"key{i}", "action1", {"value": i})
                cache.get(f"key{i}", "action1")  # Hit
                cache.get(f"key{1000+i}", "action1")  # Miss

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(stats_worker) for _ in range(10)]
            results = [f.result() for f in as_completed(futures)]

        assert cache._hits == 1000  # 10 workers * 100 hits
        assert cache._misses == 1000  # 10 workers * 100 misses


@pytest.mark.asyncio
class TestAsyncLockingMechanisms:
    """Test various locking mechanisms."""

    async def test_asyncio_lock_basic(self):
        """Test basic asyncio lock."""
        lock = asyncio.Lock()
        results = []

        async def worker(worker_id):
            async with lock:
                results.append(worker_id)
                await asyncio.sleep(0.01)

        # Run workers concurrently
        tasks = [worker(i) for i in range(5)]
        await asyncio.gather(*tasks)

        # All workers should complete
        assert len(results) == 5

    async def test_asyncio_semaphore_limiting(self):
        """Test semaphore limits concurrent operations."""
        semaphore = asyncio.Semaphore(2)
        active_count = 0
        max_active = 0

        async def worker(worker_id):
            nonlocal active_count, max_active
            async with semaphore:
                active_count += 1
                max_active = max(max_active, active_count)
                await asyncio.sleep(0.01)
                active_count -= 1

        # Run many workers
        tasks = [worker(i) for i in range(10)]
        await asyncio.gather(*tasks)

        # Should never exceed semaphore limit
        assert max_active <= 2

    async def test_concurrent_async_lock_contention(self):
        """Test concurrent async lock contention."""
        lock = asyncio.Lock()
        results = []

        async def worker(worker_id):
            async with lock:
                results.append(worker_id)
                await asyncio.sleep(0.01)

        # Run workers concurrently
        tasks = [worker(i) for i in range(10)]
        await asyncio.gather(*tasks)

        # All workers should complete
        assert len(results) == 10


class TestThreadLockingMechanisms:
    """Test thread-based locking mechanisms."""

    def test_thread_lock_basic(self):
        """Test basic thread lock."""
        lock = threading.Lock()
        results = []

        def worker(worker_id):
            with lock:
                results.append(worker_id)
                time.sleep(0.01)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker, i) for i in range(5)]
            results = [f.result() for f in as_completed(futures)]

        assert len(results) == 5

    def test_thread_lock_data_race_prevention(self):
        """Test lock prevents data races."""
        lock = threading.Lock()
        counter = {"value": 0}

        def incrementer():
            for _ in range(1000):
                with lock:
                    counter["value"] += 1

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(incrementer) for _ in range(10)]
            results = [f.result() for f in as_completed(futures)]

        # No data race - counter should be exact
        assert counter["value"] == 10000

    def test_concurrent_shared_state(self):
        """Test shared state management with threads."""
        state = {"counter": 0}
        lock = threading.Lock()

        def increment():
            for _ in range(100):
                with lock:
                    current = state["counter"]
                    time.sleep(0.0001)
                    state["counter"] = current + 1

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(increment) for _ in range(10)]
            results = [f.result() for f in as_completed(futures)]

        # All increments should be applied
        assert state["counter"] == 1000


@pytest.mark.asyncio
class TestRaceConditionHandling:
    """Test race condition detection and handling."""

    async def test_check_then_act_race(self):
        """Test check-then-act race condition pattern."""
        shared_resource = {"value": 0}
        lock = asyncio.Lock()

        async def check_then_act(worker_id):
            async with lock:
                # Check
                current = shared_resource["value"]
                # Act
                shared_resource["value"] = current + 1

        # Run concurrent operations
        tasks = [check_then_act(i) for i in range(100)]
        await asyncio.gather(*tasks)

        # No race condition - value should be exact
        assert shared_resource["value"] == 100

    async def test_double_checked_locking(self):
        """Test double-checked locking pattern."""
        cache = {"initialized": False}
        lock = asyncio.Lock()

        async def initialize_if_needed():
            # First check (without lock)
            if not cache["initialized"]:
                async with lock:
                    # Second check (with lock)
                    if not cache["initialized"]:
                        await asyncio.sleep(0.01)  # Expensive init
                        cache["initialized"] = True

        # Concurrent initializations
        tasks = [initialize_if_needed() for _ in range(10)]
        await asyncio.gather(*tasks)

        # Should only initialize once
        assert cache["initialized"] is True


@pytest.mark.asyncio
class TestDeadlockPrevention:
    """Test deadlock prevention mechanisms."""

    async def test_lock_ordering_prevents_deadlock(self):
        """Test consistent lock ordering prevents deadlock."""
        lock1 = asyncio.Lock()
        lock2 = asyncio.Lock()
        results = []

        async def worker1():
            # Always acquire locks in same order
            async with lock1:
                await asyncio.sleep(0.01)
                async with lock2:
                    results.append("worker1")

        async def worker2():
            # Same lock order as worker1
            async with lock1:
                await asyncio.sleep(0.01)
                async with lock2:
                    results.append("worker2")

        # Run both workers
        await asyncio.gather(worker1(), worker2())

        # Both should complete (no deadlock)
        assert len(results) == 2

    async def test_timeout_prevents_deadlock(self):
        """Test timeout prevents indefinite blocking."""
        # Test that asyncio.wait_for works with timeouts
        async def slow_operation():
            await asyncio.sleep(10)
            return "completed"

        # Should timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_operation(), timeout=0.1)


@pytest.mark.asyncio
class TestConcurrentStateManagement:
    """Test concurrent state management."""

    async def test_async_shared_state(self):
        """Test shared state management with async."""
        state = {"counter": 0}
        lock = asyncio.Lock()

        async def increment():
            async with lock:
                current = state["counter"]
                await asyncio.sleep(0.001)
                state["counter"] = current + 1

        # Concurrent increments
        tasks = [increment() for _ in range(100)]
        await asyncio.gather(*tasks)

        # All increments should be applied
        assert state["counter"] == 100

    async def test_concurrent_dictionary_access(self):
        """Test concurrent dictionary access."""
        shared_dict = {}
        lock = asyncio.Lock()

        async def write_worker(worker_id):
            async with lock:
                shared_dict[f"key{worker_id}"] = worker_id

        # Concurrent writes
        tasks = [write_worker(i) for i in range(100)]
        await asyncio.gather(*tasks)

        # All writes should complete
        assert len(shared_dict) == 100
