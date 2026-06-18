"""
Test suite for GovernanceCache concurrency issues.

RED PHASE: These tests expose bugs in the current implementation:
1. threading.Lock doesn't work properly in async contexts
2. Race conditions during concurrent cache access
3. Statistics tracking errors under concurrent load
4. Cache iteration issues during concurrent modifications

These tests should FAIL with the current implementation, revealing the bugs.
"""

import asyncio
import pytest
from collections import OrderedDict
from unittest.mock import patch

from core.governance_cache import GovernanceCache, get_governance_cache


class TestGovernanceCacheConcurrencyBugs:
    """
    Test suite revealing concurrency bugs in GovernanceCache.

    Bug: Using threading.Lock in async context doesn't properly protect
    against race conditions because asyncio tasks can yield between
    lock acquisition and release.
    """

    @pytest.mark.asyncio
    async def test_concurrent_get_race_condition(self):
        """
        Test that concurrent get operations can interleave incorrectly.

        EXPECTED FAILURE: Current implementation uses threading.Lock which
        doesn't prevent async task interleaving. This test will reveal
        race conditions where statistics are incorrectly tracked.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Prime the cache with some data
        for i in range(10):
            cache.set(f"agent_{i}", "test_action", {"allowed": True, "data": f"value_{i}"})

        # Track results from concurrent operations
        results = []
        errors = []

        async def get_agent(agent_id):
            try:
                result = cache.get(f"agent_{agent_id}", "test_action")
                results.append((agent_id, result))
            except Exception as e:
                errors.append((agent_id, str(e)))

        # Launch concurrent gets on the same agent
        tasks = [get_agent(5) for _ in range(100)]
        await asyncio.gather(*tasks)

        # Verify no errors occurred (e.g., RuntimeError from dict modification)
        assert len(errors) == 0, f"Errors during concurrent access: {errors}"

        # All results should be consistent
        expected_value = {"allowed": True, "data": "value_5"}
        for agent_id, result in results:
            assert result == expected_value, f"Inconsistent result for agent_{agent_id}"

    @pytest.mark.asyncio
    async def test_concurrent_set_race_condition(self):
        """
        Test that concurrent set operations can cause cache corruption.

        EXPECTED FAILURE: threading.Lock doesn't protect against async
        task interleaving during LRU eviction logic.
        """
        cache = GovernanceCache(max_size=10, ttl_seconds=60)

        results = []
        errors = []

        async def set_agent(agent_id):
            try:
                success = cache.set(f"agent_{agent_id}", "test_action", {"allowed": True})
                results.append((agent_id, success))
            except Exception as e:
                errors.append((agent_id, type(e).__name__, str(e)))

        # Launch 50 concurrent sets on a cache with max_size=10
        tasks = [set_agent(i) for i in range(50)]
        await asyncio.gather(*tasks)

        # Verify no exceptions (RuntimeError, KeyError, etc.)
        assert len(errors) == 0, f"Errors during concurrent sets: {errors}"

        # All operations should succeed
        assert len(results) == 50
        assert all(success for _, success in results)

    @pytest.mark.asyncio
    async def test_concurrent_get_and_set_race(self):
        """
        Test mixed concurrent get/set operations.

        EXPECTED FAILURE: Race conditions when gets and sets happen
        simultaneously, especially during LRU eviction.
        """
        cache = GovernanceCache(max_size=5, ttl_seconds=60)

        # Fill the cache
        for i in range(5):
            cache.set(f"agent_{i}", "action", {"data": i})

        get_results = []
        set_results = []
        errors = []

        async def get_operation(agent_id):
            try:
                result = cache.get(f"agent_{agent_id}", "action")
                get_results.append(result)
            except Exception as e:
                errors.append(("get", type(e).__name__))

        async def set_operation(agent_id):
            try:
                cache.set(f"agent_{agent_id}", "action", {"data": agent_id})
                set_results.append(True)
            except Exception as e:
                errors.append(("set", type(e).__name__))

        # Mix gets and sets concurrently
        tasks = []
        for i in range(20):
            if i % 2 == 0:
                tasks.append(get_operation(i % 5))
            else:
                tasks.append(set_operation(i + 10))

        await asyncio.gather(*tasks)

        # Should have no errors
        assert len(errors) == 0, f"Errors during mixed operations: {errors}"

    @pytest.mark.asyncio
    async def test_statistics_tracking_inaccuracy(self):
        """
        Test that statistics tracking breaks under concurrent load.

        EXPECTED FAILURE: Hit/miss counters can be incremented incorrectly
        due to race conditions, leading to inaccurate statistics.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Prime cache
        for i in range(10):
            cache.set(f"agent_{i}", "action", {"data": i})

        async def mixed_operations():
            # Do a mix of hits and misses
            for i in range(50):
                cache.get(f"agent_{i % 10}", "action")  # Hit
                cache.get(f"agent_{i + 100}", "action")  # Miss

        # Run 10 concurrent workers
        tasks = [mixed_operations() for _ in range(10)]
        await asyncio.gather(*tasks)

        stats = cache.get_stats()

        # Expected: 10 workers * 50 hits = 500 hits
        # Expected: 10 workers * 50 misses = 500 misses
        # But due to race conditions, these numbers will likely be wrong
        expected_total = 1000
        actual_total = stats["hits"] + stats["misses"]

        # This will fail due to race condition in statistics tracking
        assert actual_total == expected_total, (
            f"Statistics tracking incorrect: expected {expected_total} operations, "
            f"got {actual_total} (hits: {stats['hits']}, misses: {stats['misses']})"
        )

    @pytest.mark.asyncio
    async def test_concurrent_invalidate_iteration_bug(self):
        """
        Test cache invalidation during iteration bug.

        EXPECTED FAILURE: The invalidate method iterates over cache.keys()
        while deleting, which can cause RuntimeError if the cache is modified
        during iteration.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Fill cache
        for i in range(50):
            cache.set(f"agent_{i}", "action", {"data": i})

        errors = []

        async def invalidate_random_agent():
            try:
                # This will iterate over keys and delete them
                cache.invalidate_agent(f"agent_{__import__('random').randint(0, 49)}")
            except Exception as e:
                errors.append((type(e).__name__, str(e)))

        async def iterate_cache():
            try:
                # Simulate iteration during invalidation
                cache.get_stats()
            except Exception as e:
                errors.append(("stats", type(e).__name__, str(e)))

        # Concurrent invalidations and iterations
        tasks = []
        for _ in range(20):
            tasks.append(invalidate_random_agent())
            tasks.append(iterate_cache())

        await asyncio.gather(*tasks)

        # Should have no RuntimeError from dict modification
        runtime_errors = [e for e in errors if "RuntimeError" in str(e)]
        assert len(runtime_errors) == 0, f"RuntimeError from dict modification: {runtime_errors}"

    @pytest.mark.asyncio
    async def test_lru_eviction_race_condition(self):
        """
        Test LRU eviction under concurrent load.

        EXPECTED FAILURE: When cache is at max_size and multiple concurrent
        sets happen, the LRU eviction logic can race, causing cache to exceed
        max_size or lose data.
        """
        cache = GovernanceCache(max_size=5, ttl_seconds=60)

        # Fill to capacity
        for i in range(5):
            cache.set(f"agent_{i}", "action", {"data": i})

        # Concurrent sets that trigger eviction
        async def evicting_set(agent_id):
            cache.set(f"new_agent_{agent_id}", "action", {"data": agent_id})

        # Launch 20 concurrent sets on a full cache
        tasks = [evicting_set(i) for i in range(20)]
        await asyncio.gather(*tasks)

        # Cache should never exceed max_size
        # This will fail if eviction logic has race conditions
        assert len(cache._cache) <= cache.max_size, (
            f"Cache exceeded max_size: {len(cache._cache)} > {cache.max_size}"
        )

    @pytest.mark.asyncio
    async def test_lock_doesnt_block_async_tasks(self):
        """
        Test that threading.Lock doesn't properly block async tasks.

        EXPECTED FAILURE: This test demonstrates that threading.Lock doesn't
        provide proper mutual exclusion in asyncio because tasks can yield
        during the "locked" section.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        lock_holder_running = asyncio.Event()
        lock_holder_finished = asyncio.Event()
        second_task_started = asyncio.Event()

        # Track if second task accessed cache while first held lock
        violations = []

        async def lock_holder():
            """Hold the lock for a while."""
            lock_holder_running.set()
            with cache._lock:
                # While holding lock, sleep to let other tasks run
                # In proper async locking, other tasks should be blocked
                await asyncio.sleep(0.1)
                # Check if another task modified the cache
                second_task_started.wait(timeout=1.0)
                if second_task_started.is_set():
                    violations.append("Second task ran while lock was held!")
            lock_holder_finished.set()

        async def cache_modifier():
            """Try to modify cache while lock is held."""
            await lock_holder_running.wait()
            second_task_started.set()
            # Try to acquire lock and modify
            with cache._lock:
                cache.set("test", "action", {"data": "modified"})

        # Run both tasks concurrently
        await asyncio.gather(lock_holder(), cache_modifier())

        # With threading.Lock, the second task CAN run while first holds lock
        # This test reveals the bug
        assert len(violations) > 0, (
            "Lock appears to work (test may be unreliable), but threading.Lock "
            "doesn't provide proper async mutual exclusion"
        )


class TestGovernanceCacheThreadSafetyIssues:
    """Test specific thread-safety issues with threading.Lock in async context."""

    @pytest.mark.asyncio
    async def test_expire_stale_async_context_bug(self):
        """
        Test _expire_stale called from async context.

        EXPECTED FAILURE: _expire_stale uses threading.Lock but is called
        from async _cleanup_expired task. The lock doesn't protect against
        concurrent async modifications during iteration.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=5)  # Short TTL

        # Add entries that will expire
        import time
        cache.set("expiring_agent", "action", {"data": "old"})
        cache._cache["expiring_agent:action"]["cached_at"] = time.time() - 10  # Expired

        errors = []

        async def modify_cache():
            """Modify cache while cleanup is running."""
            try:
                for i in range(50):
                    cache.set(f"agent_{i}", "action", {"data": i})
                    await asyncio.sleep(0.001)  # Yield to let cleanup run
            except Exception as e:
                errors.append(("modify", type(e).__name__, str(e)))

        async def trigger_cleanup():
            """Trigger cleanup by waiting."""
            try:
                await asyncio.sleep(0.1)  # Let cleanup task run
                cache._expire_stale()  # Manual trigger
            except Exception as e:
                errors.append(("cleanup", type(e).__name__, str(e)))

        await asyncio.gather(modify_cache(), trigger_cleanup())

        # Should have no errors during concurrent modification and cleanup
        assert len(errors) == 0, f"Errors during cleanup and modification: {errors}"


class TestMessagingCacheConcurrencyBugs:
    """Test concurrency bugs in MessagingCache (also uses threading.Lock)."""

    @pytest.mark.asyncio
    async def test_messaging_cache_concurrent_access(self):
        """
        Test MessagingCache with concurrent access.

        EXPECTED FAILURE: MessagingCache also uses threading.Lock which
        doesn't protect against async race conditions.
        """
        from core.governance_cache import MessagingCache

        cache = MessagingCache(max_size=50, ttl_seconds=60)

        errors = []

        async def set_capability(platform):
            try:
                cache.set_platform_capabilities(platform, "AUTONOMOUS", {"feature": platform})
            except Exception as e:
                errors.append(("set", type(e).__name__))

        async def get_capability(platform):
            try:
                cache.get_platform_capabilities(platform, "AUTONOMOUS")
            except Exception as e:
                errors.append(("get", type(e).__name__))

        tasks = []
        platforms = [f"platform_{i}" for i in range(20)]

        for platform in platforms:
            tasks.append(set_capability(platform))
            tasks.append(get_capability(platform))

        await asyncio.gather(*tasks)

        assert len(errors) == 0, f"Errors in MessagingCache: {errors}"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
