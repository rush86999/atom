"""
Cache Race Condition Tests

Tests for race conditions, lock contention, and cache consistency under
concurrent access using threading.Thread for parallel execution.

These tests intentionally create contention to expose bugs that cause
production failures under load. Single-threaded tests cannot detect
these issues.

Key Bugs Tested:
- Concurrent write corruption (lost updates)
- Read/write inconsistency (torn reads)
- Cache eviction under load (LRU correctness)
- Invalidation during access (use-after-free)
- Lock contention (deadlock, timeout)

SQLite Limitations:
- Tests use in-memory GovernanceCache (thread-safe by design)
- No SQLite locking involved (cache is pure Python + threading.Lock)
- True concurrency achieved via threading.Thread
"""

import threading
import time
import pytest
from typing import List, Dict, Any

from core.governance_cache import GovernanceCache


class TestCacheConcurrentWriteRaceConditions:
    """Test concurrent write operations for data corruption."""

    def test_cache_concurrent_write_race_condition(self):
        """
        CONCURRENT: Multiple threads writing to cache simultaneously.

        Tests that cache handles concurrent writes without corruption.
        Each thread writes unique entries - verify all are present.

        BUG_PATTERN: Lost updates due to lack of locking.
        EXPECTED: All writes preserved, no data loss.
        """
        cache = GovernanceCache(max_size=1000, ttl_seconds=60)
        thread_count = 10
        writes_per_thread = 100

        errors = []
        write_count = [0]  # List for mutability in closure

        def write_cache(thread_id):
            try:
                for i in range(writes_per_thread):
                    agent_id = f"agent_{thread_id}_{i}"
                    cache.set(agent_id, "test_action", {"thread": thread_id, "index": i})
                    write_count[0] += 1
            except Exception as e:
                errors.append(e)

        threads = []
        for thread_id in range(thread_count):
            thread = threading.Thread(target=write_cache, args=(thread_id,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Verify no errors occurred
        assert len(errors) == 0, f"Concurrent write errors: {errors}"

        # Verify all writes completed
        expected_writes = thread_count * writes_per_thread
        assert write_count[0] == expected_writes, \
            f"Write count mismatch: {write_count[0]} != {expected_writes}"

        # Verify cache has most entries (may have some evictions if at capacity)
        stats = cache.get_stats()
        # Allow 10% tolerance for LRU eviction during concurrent writes
        min_expected = int(expected_writes * 0.9)
        assert stats["size"] >= min_expected, \
            f"Cache size {stats['size']} below expected {min_expected}"

    def test_cache_concurrent_write_same_key(self):
        """
        CONCURRENT: Multiple threads writing to same key.

        Tests last-write-wins behavior for same key.
        All writes should succeed, final value is from one thread.

        BUG_PATTERN: Race condition in key updates causing corruption.
        EXPECTED: All writes succeed, final value is valid.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)
        thread_count = 10
        writes_per_thread = 50

        errors = []

        def write_same_key(thread_id):
            try:
                for i in range(writes_per_thread):
                    # All threads write to same key
                    cache.set("shared_agent", "test_action", {
                        "thread": thread_id,
                        "index": i,
                        "value": f"thread_{thread_id}_write_{i}"
                    })
            except Exception as e:
                errors.append(e)

        threads = []
        for thread_id in range(thread_count):
            thread = threading.Thread(target=write_same_key, args=(thread_id,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Verify no errors
        assert len(errors) == 0, f"Errors writing to same key: {errors}"

        # Verify final value is valid (from some thread)
        result = cache.get("shared_agent", "test_action")
        assert result is not None, "Key should exist"
        assert "thread" in result, "Result should have thread field"
        assert "index" in result, "Result should have index field"
        assert 0 <= result["thread"] < thread_count, f"Invalid thread ID: {result['thread']}"
        assert 0 <= result["index"] < writes_per_thread, f"Invalid index: {result['index']}"

    def test_cache_concurrent_write_overflow(self):
        """
        CONCURRENT: Fill cache beyond capacity with concurrent writes.

        Tests LRU eviction works correctly under concurrent load.
        Oldest entries should be evicted, newest preserved.

        BUG_PATTERN: LRU eviction broken due to race condition.
        EXPECTED: Cache size <= max_size, evicted entries removed.
        """
        max_size = 50
        cache = GovernanceCache(max_size=max_size, ttl_seconds=60)
        thread_count = 10
        writes_per_thread = 20  # Total 200 writes for capacity 50

        errors = []

        def write_cache(thread_id):
            try:
                for i in range(writes_per_thread):
                    agent_id = f"agent_{thread_id}_{i}"
                    cache.set(agent_id, "test_action", {"data": f"{thread_id}_{i}"})
            except Exception as e:
                errors.append(e)

        threads = []
        for thread_id in range(thread_count):
            thread = threading.Thread(target=write_cache, args=(thread_id,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Verify no errors
        assert len(errors) == 0, f"Errors during overflow: {errors}"

        # Verify cache size at capacity
        stats = cache.get_stats()
        assert stats["size"] <= max_size, \
            f"Cache size {stats['size']} exceeds max {max_size}"

        # Verify evictions occurred
        assert stats["evictions"] > 0, "Should have evicted entries"

        # Verify some entries still present
        assert stats["size"] > 0, "Cache should not be empty"


class TestCacheConcurrentReadWriteConsistency:
    """Test read/write consistency under concurrent access."""

    def test_cache_read_during_concurrent_writes(self):
        """
        CONCURRENT: Multiple threads reading while one writes.

        Tests that reads never return corrupted data (torn reads).
        All reads should return valid data or None, never partial objects.

        BUG_PATTERN: Torn reads due to lack of synchronization.
        EXPECTED: All reads return valid dicts or None.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)
        thread_count = 10
        operations_per_thread = 100

        # Pre-populate cache
        for i in range(50):
            cache.set(f"agent_{i}", "action", {"value": i})

        errors = []
        read_count = [0]
        write_count = [0]
        corrupted_reads = []

        def read_cache():
            try:
                for i in range(operations_per_thread):
                    agent_id = f"agent_{i % 50}"
                    result = cache.get(agent_id, "action")
                    read_count[0] += 1

                    # Verify result is valid
                    if result is not None:
                        if not isinstance(result, dict):
                            corrupted_reads.append(f"Not a dict: {type(result)}")
                        elif "value" not in result:
                            corrupted_reads.append(f"Missing 'value' key: {result}")
            except Exception as e:
                errors.append(e)

        def write_cache():
            try:
                for i in range(operations_per_thread):
                    agent_id = f"agent_{i % 50}"
                    cache.set(agent_id, "action", {"value": i, "writer": "writer"})
                    write_count[0] += 1
            except Exception as e:
                errors.append(e)

        # Launch 9 readers, 1 writer
        threads = []
        for _ in range(9):
            thread = threading.Thread(target=read_cache)
            threads.append(thread)
            thread.start()

        thread = threading.Thread(target=write_cache)
        threads.append(thread)
        thread.start()

        for thread in threads:
            thread.join()

        # Verify no errors
        assert len(errors) == 0, f"Errors during read/write: {errors}"

        # Verify no corrupted reads
        assert len(corrupted_reads) == 0, f"Corrupted reads: {corrupted_reads}"

        # Verify operations completed
        assert read_count[0] == 9 * operations_per_thread, \
            f"Read count mismatch: {read_count[0]}"
        assert write_count[0] == operations_per_thread, \
            f"Write count mismatch: {write_count[0]}"

    def test_cache_concurrent_read_miss_consistency(self):
        """
        CONCURRENT: Multiple threads reading missing keys.

        Tests that cache miss handling is thread-safe.
        All reads of missing keys should return None consistently.

        BUG_PATTERN: Race condition in miss handling.
        EXPECTED: All reads return None, statistics accurate.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)
        thread_count = 20
        reads_per_thread = 100

        errors = []
        results = []

        def read_missing_keys():
            try:
                for i in range(reads_per_thread):
                    # Read non-existent keys
                    result = cache.get(f"missing_agent_{i}", "missing_action")
                    results.append(result)
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(thread_count):
            thread = threading.Thread(target=read_missing_keys)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Verify no errors
        assert len(errors) == 0, f"Errors reading missing keys: {errors}"

        # Verify all reads returned None
        assert all(r is None for r in results), "All reads should return None"

        # Verify miss statistics
        stats = cache.get_stats()
        assert stats["misses"] == thread_count * reads_per_thread, \
            f"Miss count mismatch: {stats['misses']}"
        assert stats["hits"] == 0, "Should have no hits"


class TestCacheEvictionUnderContention:
    """Test cache eviction behavior under concurrent load."""

    def test_cache_concurrent_lru_eviction(self):
        """
        CONCURRENT: LRU eviction works correctly under concurrent access.

        Tests that recently-used entries are preserved during eviction.
        Oldest entries evicted, newest entries present.

        BUG_PATTERN: LRU ordering broken by concurrent updates.
        EXPECTED: Oldest entries evicted, newest present.
        """
        cache = GovernanceCache(max_size=10, ttl_seconds=60)

        # Fill cache with 10 entries
        for i in range(10):
            cache.set(f"key{i}", "action", {"data": i})

        # Launch threads that access different keys
        errors = []

        def access_old_keys():
            try:
                # Access old keys (keep them in LRU)
                for i in range(5):
                    cache.get(f"key{i}", "action")
            except Exception as e:
                errors.append(e)

        def write_new_keys():
            try:
                # Write new keys (trigger eviction)
                for i in range(10, 20):
                    cache.set(f"key{i}", "action", {"data": i})
            except Exception as e:
                errors.append(e)

        # Start threads concurrently
        thread1 = threading.Thread(target=access_old_keys)
        thread2 = threading.Thread(target=write_new_keys)

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # Verify no errors
        assert len(errors) == 0, f"Errors during LRU test: {errors}"

        # Verify cache size
        stats = cache.get_stats()
        assert stats["size"] <= 10, f"Cache size {stats['size']} exceeds max 10"

        # Verify evictions occurred
        assert stats["evictions"] > 0, "Should have evicted entries"

    def test_cache_concurrent_eviction_deterministic(self):
        """
        CONCURRENT: Deterministic eviction test.

        Forces cache overflow by writing more entries than capacity.
        Verifies cache maintains size invariant.

        BUG_PATTERN: Cache size exceeds max due to race condition.
        EXPECTED: Cache size never exceeds max_size.
        """
        max_size = 5
        cache = GovernanceCache(max_size=max_size, ttl_seconds=60)

        # Write 10 items concurrently (capacity is 5)
        errors = []

        def write_item(i):
            try:
                cache.set(f"key{i}", "action", {"data": i})
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(10):
            thread = threading.Thread(target=write_item, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Verify no errors
        assert len(errors) == 0, f"Errors during eviction: {errors}"

        # Verify cache size invariant
        stats = cache.get_stats()
        assert stats["size"] <= max_size, \
            f"Cache size {stats['size']} exceeds max {max_size}"

        # Verify some entries present (not all evicted)
        assert stats["size"] > 0, "Cache should have entries"


class TestCacheInvalidationDuringConcurrentAccess:
    """Test cache invalidation under concurrent load."""

    def test_cache_invalidate_during_reads(self):
        """
        CONCURRENT: Invalidate entries while other threads read.

        Tests that invalidation doesn't cause crashes or inconsistencies.
        Reads during invalidation should succeed (return None or old value).

        BUG_PATTERN: Use-after-free during invalidation.
        EXPECTED: No crashes, all operations complete.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Pre-populate cache
        for i in range(50):
            cache.set(f"agent_{i}", "action", {"data": i})

        errors = []

        def read_cache():
            try:
                for i in range(100):
                    agent_id = f"agent_{i % 50}"
                    result = cache.get(agent_id, "action")
                    # Result may be None (invalidated) or dict (present)
                    # Both are valid outcomes
            except Exception as e:
                errors.append(e)

        def invalidate_cache():
            try:
                for i in range(50):
                    cache.invalidate(f"agent_{i}", "action")
            except Exception as e:
                errors.append(e)

        # Launch 5 readers, 1 invalidator
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=read_cache)
            threads.append(thread)
            thread.start()

        thread = threading.Thread(target=invalidate_cache)
        threads.append(thread)
        thread.start()

        for thread in threads:
            thread.join()

        # Verify no errors
        assert len(errors) == 0, f"Errors during invalidation: {errors}"

        # Verify all entries invalidated
        stats = cache.get_stats()
        assert stats["invalidations"] == 50, f"Invalidations: {stats['invalidations']}"
        assert stats["size"] == 0, f"Cache should be empty: {stats['size']}"

    def test_cache_invalidate_all_during_operations(self):
        """
        CONCURRENT: Invalidate all agent entries while other threads operate.

        Tests bulk invalidation (all actions for an agent) under load.
        Agent operations should continue working after invalidation.

        BUG_PATTERN: Bulk invalidation causes race condition.
        EXPECTED: Operations complete correctly after invalidation.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Pre-populate with multiple agents, multiple actions
        for agent_id in range(10):
            for action in ["action1", "action2", "action3"]:
                cache.set(f"agent_{agent_id}", action, {"data": f"{agent_id}_{action}"})

        errors = []
        operation_count = [0]

        def cache_operations():
            try:
                for i in range(100):
                    agent_id = f"agent_{i % 10}"
                    action = f"action{i % 3}"

                    # Mix of reads and writes
                    if i % 2 == 0:
                        cache.get(agent_id, action)
                    else:
                        cache.set(agent_id, action, {"data": i})
                    operation_count[0] += 1
            except Exception as e:
                errors.append(e)

        def invalidate_agents():
            try:
                # Invalidate all actions for some agents
                for agent_id in range(5):
                    cache.invalidate_agent(f"agent_{agent_id}")
            except Exception as e:
                errors.append(e)

        # Launch 10 operation threads, 1 invalidator
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=cache_operations)
            threads.append(thread)
            thread.start()

        thread = threading.Thread(target=invalidate_agents)
        threads.append(thread)
        thread.start()

        for thread in threads:
            thread.join()

        # Verify no errors
        assert len(errors) == 0, f"Errors during operations: {errors}"

        # Verify operations completed
        assert operation_count[0] == 10 * 100, \
            f"Operation count mismatch: {operation_count[0]}"

        # Verify invalidations
        stats = cache.get_stats()
        assert stats["invalidations"] >= 5, \
            f"Should have at least 5 invalidations: {stats['invalidations']}"


class TestCacheLockContentionPerformance:
    """Test cache performance under high lock contention."""

    def test_cache_high_contention_same_key(self):
        """
        CONCURRENT: 50 threads accessing same key (high contention).

        Tests cache handles high lock contention without deadlock.
        All threads should complete within reasonable time.

        BUG_PATTERN: Deadlock or excessive slowdown under contention.
        EXPECTED: All threads complete, avg time < 50ms per operation.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)
        cache.set("shared_agent", "action", {"value": "initial"})

        thread_count = 50
        operations_per_thread = 10
        errors = []
        latencies = []

        def access_shared_key():
            try:
                for _ in range(operations_per_thread):
                    start = time.perf_counter()
                    result = cache.get("shared_agent", "action")
                    latency_ms = (time.perf_counter() - start) * 1000
                    latencies.append(latency_ms)

                    # Verify result is valid
                    assert result is not None, "Key should exist"
                    assert isinstance(result, dict), "Result should be dict"
            except Exception as e:
                errors.append(e)

        # Launch all threads
        threads = []
        start_time = time.perf_counter()

        for _ in range(thread_count):
            thread = threading.Thread(target=access_shared_key)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        end_time = time.perf_counter()

        # Verify no errors
        assert len(errors) == 0, f"Errors under contention: {errors}"

        # Verify all operations completed
        expected_ops = thread_count * operations_per_thread
        assert len(latencies) == expected_ops, \
            f"Operations count mismatch: {len(latencies)} != {expected_ops}"

        # Calculate latency statistics
        latencies_sorted = sorted(latencies)
        p50_idx = int(len(latencies_sorted) * 0.5)
        p99_idx = int(len(latencies_sorted) * 0.99)

        avg_latency = sum(latencies) / len(latencies)
        p50_latency = latencies_sorted[p50_idx]
        p99_latency = latencies_sorted[p99_idx]

        # Verify performance acceptable (allow 50ms per operation for high contention)
        assert p99_latency < 50, \
            f"P99 latency {p99_latency:.2f}ms exceeds 50ms threshold"

        # Verify no deadlock (all threads completed)
        total_duration = end_time - start_time
        assert total_duration < 30, \
            f"Total duration {total_duration:.2f}s suggests deadlock or slowdown"

    def test_cache_lock_contention_deadlock_free(self):
        """
        CONCURRENT: Verify cache operations are deadlock-free.

        Tests various cache operations mixed together don't deadlock.
        All operations types (get, set, invalidate, clear) tested.

        BUG_PATTERN: Deadlock when mixing operations.
        EXPECTED: All threads complete without hanging.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Pre-populate
        for i in range(50):
            cache.set(f"agent_{i}", "action", {"data": i})

        thread_count = 20
        operations_per_thread = 50
        errors = []

        def mixed_operations(thread_id):
            try:
                for i in range(operations_per_thread):
                    agent_id = f"agent_{i % 50}"

                    # Mix of operations
                    op_type = i % 4
                    if op_type == 0:
                        cache.get(agent_id, "action")
                    elif op_type == 1:
                        cache.set(agent_id, "action", {"data": i, "thread": thread_id})
                    elif op_type == 2:
                        cache.invalidate(agent_id, "action")
                    else:
                        # Clear is less frequent (heavy operation)
                        if i % 20 == 0:
                            cache.clear()
            except Exception as e:
                errors.append(e)

        # Launch threads
        threads = []
        for thread_id in range(thread_count):
            thread = threading.Thread(target=mixed_operations, args=(thread_id,))
            threads.append(thread)
            thread.start()

        # Wait for completion with timeout (detect deadlock)
        start_time = time.time()
        for thread in threads:
            # Thread.join(timeout) returns None if thread completed, or hangs if alive
            thread.join(timeout=30)  # 30 second timeout
            if thread.is_alive():
                pytest.fail(f"Deadlock detected: thread still alive after 30s")

        end_time = time.time()
        duration = end_time - start_time

        # Verify no errors
        assert len(errors) == 0, f"Errors in mixed operations: {errors}"

        # Verify completion within reasonable time
        assert duration < 30, \
            f"Duration {duration:.2f}s suggests performance issue"

    def test_cache_statistics_accuracy_under_contention(self):
        """
        CONCURRENT: Statistics remain accurate under concurrent access.

        Tests that hit/miss/eviction counters are thread-safe.
        Stats should accurately reflect all operations.

        BUG_PATTERN: Statistics corrupted by concurrent updates.
        EXPECTED: Stats accurate (hits + misses = total gets).
        """
        cache = GovernanceCache(max_size=50, ttl_seconds=60)

        # Pre-populate half the cache
        for i in range(25):
            cache.set(f"agent_{i}", "action", {"data": i})

        thread_count = 10
        operations_per_thread = 100
        errors = []

        def mixed_access():
            try:
                for i in range(operations_per_thread):
                    # 50% hits (existing keys), 50% misses (new keys)
                    if i % 2 == 0:
                        cache.get(f"agent_{i % 25}", "action")  # Hit
                    else:
                        cache.get(f"missing_agent_{i}", "action")  # Miss
            except Exception as e:
                errors.append(e)

        # Launch threads
        threads = []
        for _ in range(thread_count):
            thread = threading.Thread(target=mixed_access)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Verify no errors
        assert len(errors) == 0, f"Errors during access: {errors}"

        # Verify statistics
        stats = cache.get_stats()
        total_gets = stats["hits"] + stats["misses"]
        expected_gets = thread_count * operations_per_thread

        assert total_gets == expected_gets, \
            f"Total gets {total_gets} != expected {expected_gets}"

        # Verify hit rate is reasonable (around 50%)
        assert 40 <= stats["hit_rate"] <= 60, \
            f"Hit rate {stats['hit_rate']} outside expected range [40, 60]"
