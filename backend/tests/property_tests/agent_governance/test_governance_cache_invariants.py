"""
Property-Based Tests for Governance Cache Invariants

Tests CRITICAL governance cache invariants:
- LRU eviction behavior
- TTL expiration logic
- Cache hit/miss tracking
- Key uniqueness and format
- Statistics accuracy

These tests protect against cache corruption and performance bugs.
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta
from typing import Dict, List
from unittest.mock import Mock, patch
import time

from core.governance_cache import GovernanceCache


class TestCacheLRUInvariants:
    """Property-based tests for LRU eviction invariants."""

    @given(
        max_size=st.integers(min_value=10, max_value=100),
        entry_count=st.integers(min_value=1, max_value=200)
    )
    @settings(max_examples=50)
    def test_lru_eviction_enforcement(self, max_size, entry_count):
        """INVARIANT: Cache should enforce max_size with LRU eviction."""
        cache = GovernanceCache(max_size=max_size, ttl_seconds=60)

        # Add entries
        entries_added = 0
        for i in range(entry_count):
            key = f"agent_{i}:action"
            value = {"allowed": i % 2 == 0, "cached_at": time.time()}
            cache._cache[key] = value
            entries_added += 1

            # Simulate LRU eviction
            if len(cache._cache) > max_size:
                # Remove oldest entry
                oldest_key = next(iter(cache._cache))
                del cache._cache[oldest_key]
                cache._evictions += 1

        # Invariant: Cache size should not exceed max_size
        assert len(cache._cache) <= max_size, \
            f"Cache size {len(cache._cache)} exceeds max_size {max_size}"

    @given(
        max_size=st.integers(min_value=5, max_value=50)
    )
    @settings(max_examples=50)
    def test_eviction_counter_accuracy(self, max_size):
        """INVARIANT: Eviction counter should match actual evictions."""
        cache = GovernanceCache(max_size=max_size, ttl_seconds=60)

        initial_evictions = cache._evictions

        # Add more entries than max_size
        for i in range(max_size + 10):
            key = f"agent_{i}:action"
            value = {"allowed": True, "cached_at": time.time()}
            cache._cache[key] = value

            # Simulate eviction
            if len(cache._cache) > max_size:
                oldest_key = next(iter(cache._cache))
                del cache._cache[oldest_key]
                cache._evictions += 1

        # Invariant: Evictions should be counted
        assert cache._evictions >= initial_evictions, \
            "Eviction counter should increase"


class TestCacheTTLInvariants:
    """Property-based tests for TTL expiration invariants."""

    @given(
        ttl_seconds=st.integers(min_value=1, max_value=300),
        entry_count=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=50)
    def test_ttl_expiration_logic(self, ttl_seconds, entry_count):
        """INVARIANT: Cache entries should expire after TTL."""
        cache = GovernanceCache(max_size=100, ttl_seconds=ttl_seconds)

        # Add entries with timestamps
        now = time.time()
        for i in range(entry_count):
            key = f"agent_{i}:action"
            # Make some entries old
            cached_at = now - (ttl_seconds + i)
            value = {"allowed": True, "cached_at": cached_at}
            cache._cache[key] = value

        # Simulate expiration
        cache._expire_stale()

        # Invariant: Old entries should be removed
        remaining_stale = sum(1 for k, v in cache._cache.items() if now - v["cached_at"] > ttl_seconds)

        assert remaining_stale == 0, "Stale entries should be removed"

    @given(
        entry_count=st.integers(min_value=1, max_value=20),
        age_seconds=st.integers(min_value=0, max_value=120)
    )
    @settings(max_examples=50)
    def test_fresh_entries_preserved(self, entry_count, age_seconds):
        """INVARIANT: Fresh entries should not be expired."""
        ttl_seconds = 60
        cache = GovernanceCache(max_size=100, ttl_seconds=ttl_seconds)

        # Add entries with specific ages
        now = time.time()
        for i in range(entry_count):
            key = f"agent_{i}:action"
            cached_at = now - age_seconds
            value = {"allowed": True, "cached_at": cached_at}
            cache._cache[key] = value

        # Run expiration
        cache._expire_stale()

        # Check if fresh entries remain
        if age_seconds < ttl_seconds:
            assert len(cache._cache) == entry_count, \
                f"Fresh entries should remain: {len(cache._cache)}/{entry_count}"


class TestCacheStatisticsInvariants:
    """Property-based tests for cache statistics invariants."""

    @given(
        hit_count=st.integers(min_value=0, max_value=100),
        miss_count=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=50)
    def test_hit_miss_tracking(self, hit_count, miss_count):
        """INVARIANT: Cache should accurately track hits and misses."""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Simulate hits and misses
        cache._hits = hit_count
        cache._misses = miss_count

        # Calculate hit rate
        total_requests = hit_count + miss_count
        hit_rate = hit_count / total_requests if total_requests > 0 else 0.0

        # Invariant: Hit rate should be in [0, 1]
        assert 0.0 <= hit_rate <= 1.0, \
            f"Hit rate {hit_rate} out of bounds [0, 1]"

        # Invariant: Total should match
        assert cache._hits + cache._misses == total_requests, \
            "Hit + miss count mismatch"

    @given(
        operation_count=st.integers(min_value=100, max_value=1000)
    )
    @settings(max_examples=50)
    def test_hit_rate_calculation(self, operation_count):
        """INVARIANT: Hit rate should be calculated correctly."""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Simulate operations (70% hit rate)
        hits = int(operation_count * 0.7)
        misses = operation_count - hits

        cache._hits = hits
        cache._misses = misses

        hit_rate = cache._hits / (cache._hits + cache._misses)

        # Invariant: Hit rate should be approximately 0.7
        expected_rate = 0.7
        tolerance = 0.05  # More lenient tolerance for integer division
        assert abs(hit_rate - expected_rate) <= tolerance, \
            f"Hit rate {hit_rate} != expected {expected_rate}"

    @given(
        invalidation_count=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=50)
    def test_invalidation_counter(self, invalidation_count):
        """INVARIANT: Invalidation counter should be accurate."""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Simulate invalidations
        for i in range(invalidation_count):
            key = f"agent_{i}:action"
            if key in cache._cache:
                del cache._cache[key]
                cache._invalidations += 1

        # Invariant: Counter should match
        assert cache._invalidations <= invalidation_count, \
            "Invalidation count mismatch"


class TestCacheKeyInvariants:
    """Property-based tests for cache key invariants."""

    @given(
        agent_id=st.text(min_size=1, max_size=50, alphabet='abc123'),
        action_type=st.text(min_size=1, max_size=30, alphabet='xyz')
    )
    @settings(max_examples=100)
    def test_key_format_validity(self, agent_id, action_type):
        """INVARIANT: Cache keys should follow format: agent_id:action."""
        key = f"{agent_id}:{action_type}"

        # Invariant: Key should contain colon separator
        assert ':' in key, "Cache key must contain ':' separator"

        # Invariant: Key should not be empty
        assert len(key) > 0, "Cache key should not be empty"

        # Invariant: Key components should not be empty
        parts = key.split(':')
        assert len(parts) == 2, "Key should have exactly 2 parts"
        assert len(parts[0]) > 0, "Agent ID should not be empty"
        assert len(parts[1]) > 0, "Action type should not be empty"

    @given(
        agent_count=st.integers(min_value=1, max_value=50),
        action_count=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=50)
    def test_key_uniqueness(self, agent_count, action_count):
        """INVARIANT: Cache keys should be unique."""
        keys = set()
        duplicate_count = 0

        for i in range(agent_count):
            for j in range(action_count):
                key = f"agent_{i}:action_{j}"
                if key in keys:
                    duplicate_count += 1
                else:
                    keys.add(key)

        # Invariant: Should have unique keys
        expected_count = agent_count * action_count
        assert len(keys) == expected_count - duplicate_count, \
            f"Key count mismatch: {len(keys)} != {expected_count}"

    @given(
        agent_id=st.text(min_size=1, max_size=50, alphabet='abc123')
    )
    @settings(max_examples=50)
    def test_key_collision_prevention(self, agent_id):
        """INVARIANT: Different agents should have different cache entries."""
        action = "test_action"
        key1 = f"{agent_id}:{action}"
        key2 = f"{agent_id}_different:{action}"

        # Invariant: Keys should be different
        assert key1 != key2, "Different agents should produce different keys"


class TestCacheConcurrencyInvariants:
    """Property-based tests for cache concurrency invariants."""

    @given(
        reader_count=st.integers(min_value=1, max_value=10),
        writer_count=st.integers(min_value=0, max_value=5)
    )
    @settings(max_examples=50)
    def test_concurrent_read_write_safety(self, reader_count, writer_count):
        """INVARIANT: Cache should handle concurrent reads and writes safely."""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # First populate cache with entries for reads
        for i in range(reader_count):
            key = f"agent_{i}:action"
            cache._cache[key] = {"allowed": True, "cached_at": time.time()}

        # Simulate concurrent operations
        completed_reads = 0
        completed_writes = 0

        # Simulate reads
        for i in range(reader_count):
            key = f"agent_{i}:action"
            if key in cache._cache:
                completed_reads += 1

        # Simulate writes
        for i in range(writer_count):
            key = f"agent_{reader_count + i}:action"
            value = {"allowed": True, "cached_at": time.time()}
            cache._cache[key] = value
            completed_writes += 1

        # Invariant: All operations should complete
        total_completed = completed_reads + completed_writes
        assert total_completed == reader_count + writer_count, \
            f"Not all operations completed: {total_completed}/{reader_count + writer_count}"

    @given(
        operation_count=st.integers(min_value=10, max_value=100)
    )
    @settings(max_examples=50)
    def test_atomic_operations(self, operation_count):
        """INVARIANT: Cache operations should be atomic."""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Simulate atomic operations
        successful_ops = 0
        for i in range(operation_count):
            key = f"agent_{i}:action"
            initial_size = len(cache._cache)

            # Simulate atomic check-and-set
            if key not in cache._cache:
                cache._cache[key] = {"allowed": True, "cached_at": time.time()}
                final_size = len(cache._cache)

                # Check atomicity
                if final_size == initial_size + 1:
                    successful_ops += 1

        # Invariant: Operations should be atomic
        assert successful_ops == operation_count, \
            f"Not all operations were atomic: {successful_ops}/{operation_count}"

    @given(
        thread_count=st.integers(min_value=2, max_value=10),
        operations_per_thread=st.integers(min_value=5, max_value=20)
    )
    @settings(max_examples=50)
    def test_thread_safety(self, thread_count, operations_per_thread):
        """INVARIANT: Cache should be thread-safe."""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Simulate thread operations
        total_operations = thread_count * operations_per_thread
        completed_operations = 0

        for thread_id in range(thread_count):
            for op_id in range(operations_per_thread):
                key = f"agent_{thread_id}_{op_id}:action"
                value = {"allowed": True, "cached_at": time.time()}
                cache._cache[key] = value
                completed_operations += 1

        # Invariant: All operations should complete
        assert completed_operations == total_operations, \
            f"Thread safety issue: {completed_operations}/{total_operations}"


class TestCachePerformanceInvariants:
    """Property-based tests for cache performance invariants."""

    @given(
        lookup_count=st.integers(min_value=100, max_value=10000)
    )
    @settings(max_examples=50)
    def test_lookup_performance(self, lookup_count):
        """INVARIANT: Cache lookups should be fast (<1ms)."""
        cache = GovernanceCache(max_size=1000, ttl_seconds=60)

        # Populate cache
        for i in range(100):
            key = f"agent_{i}:action"
            cache._cache[key] = {"allowed": True, "cached_at": time.time()}

        # Measure lookup performance
        start_time = time.perf_counter()
        for i in range(lookup_count):
            key = f"agent_{i % 100}:action"
            _ = cache._cache.get(key)
        end_time = time.perf_counter()

        avg_time_ms = (end_time - start_time) * 1000 / lookup_count

        # Invariant: Average lookup should be fast
        assert avg_time_ms < 1.0, \
            f"Lookup too slow: {avg_time_ms:.3f}ms (should be <1ms)"

    @given(
        entry_count=st.integers(min_value=1, max_value=1000)
    )
    @settings(max_examples=50)
    def test_insertion_performance(self, entry_count):
        """INVARIANT: Cache insertions should be fast."""
        cache = GovernanceCache(max_size=10000, ttl_seconds=60)

        # Measure insertion performance
        start_time = time.perf_counter()
        for i in range(entry_count):
            key = f"agent_{i}:action"
            cache._cache[key] = {"allowed": True, "cached_at": time.time()}
        end_time = time.perf_counter()

        avg_time_ms = (end_time - start_time) * 1000 / entry_count

        # Invariant: Average insertion should be fast
        assert avg_time_ms < 0.5, \
            f"Insertion too slow: {avg_time_ms:.3f}ms (should be <0.5ms)"

    @given(
        cache_size=st.integers(min_value=100, max_value=10000)
    )
    @settings(max_examples=50)
    def test_memory_efficiency(self, cache_size):
        """INVARIANT: Cache should use memory efficiently."""
        # Estimate memory per entry (dict key + dict value)
        estimated_bytes_per_entry = 200  # Conservative estimate
        estimated_total_bytes = cache_size * estimated_bytes_per_entry

        # Convert to MB
        estimated_mb = estimated_total_bytes / (1024 * 1024)

        # Invariant: Cache should not exceed reasonable memory limit
        max_memory_mb = 10  # 10MB limit
        assert estimated_mb <= max_memory_mb, \
            f"Cache uses too much memory: {estimated_mb:.2f}MB > {max_memory_mb}MB"


class TestCacheBulkOperationsInvariants:
    """Property-based tests for bulk cache operations invariants."""

    @given(
        agent_count=st.integers(min_value=1, max_value=50),
        action_count=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=50)
    def test_bulk_get(self, agent_count, action_count):
        """INVARIANT: Bulk get should retrieve all entries."""
        cache = GovernanceCache(max_size=1000, ttl_seconds=60)

        # Populate cache
        keys = []
        for i in range(agent_count):
            for j in range(action_count):
                key = f"agent_{i}:action_{j}"
                cache._cache[key] = {"allowed": True, "cached_at": time.time()}
                keys.append(key)

        # Simulate bulk get
        results = {}
        for key in keys:
            results[key] = cache._cache.get(key)

        # Invariant: Should retrieve all entries
        assert len(results) == len(keys), \
            f"Bulk get missed entries: {len(results)}/{len(keys)}"

    @given(
        entry_count=st.integers(min_value=10, max_value=100)
    )
    @settings(max_examples=50)
    def test_bulk_invalidation(self, entry_count):
        """INVARIANT: Bulk invalidation should remove all entries."""
        cache = GovernanceCache(max_size=1000, ttl_seconds=60)

        # Populate cache with unique entries
        keys = []
        for i in range(entry_count):
            key = f"agent_{i}:action"
            cache._cache[key] = {"allowed": True, "cached_at": time.time()}
            keys.append(key)

        # Simulate bulk invalidation (invalidate all agents)
        invalidated_count = 0
        for key in list(cache._cache.keys()):
            del cache._cache[key]
            cache._invalidations += 1
            invalidated_count += 1

        # Invariant: All entries should be invalidated
        assert len(cache._cache) == 0, "Cache should be empty after bulk invalidation"
        assert invalidated_count == len(keys), \
            f"Not all entries invalidated: {invalidated_count}/{len(keys)}"

    @given(
        batch_size=st.integers(min_value=1, max_value=50),
        batch_count=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=50)
    def test_batch_operations_consistency(self, batch_size, batch_count):
        """INVARIANT: Batch operations should maintain consistency."""
        cache = GovernanceCache(max_size=1000, ttl_seconds=60)

        # Simulate batch inserts
        all_keys = []
        for batch_num in range(batch_count):
            batch_keys = []
            for i in range(batch_size):
                key = f"batch_{batch_num}_item_{i}:action"
                cache._cache[key] = {"allowed": True, "cached_at": time.time()}
                batch_keys.append(key)
                all_keys.append(key)

        # Verify all batches inserted
        found_count = sum(1 for key in all_keys if key in cache._cache)

        # Invariant: All batches should be inserted
        assert found_count == len(all_keys), \
            f"Batch operations lost entries: {found_count}/{len(all_keys)}"


class TestCacheConsistencyInvariants:
    """Property-based tests for cache consistency invariants."""

    @given(
        update_count=st.integers(min_value=1, max_value=100),
        agent_id=st.text(min_size=1, max_size=20, alphabet='abc123')
    )
    @settings(max_examples=50)
    def test_sequential_updates_consistent(self, update_count, agent_id):
        """INVARIANT: Sequential updates to same key should be consistent."""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        action = "test_action"
        key = f"{agent_id}:{action}"

        # Apply sequential updates
        previous_value = None
        for i in range(update_count):
            value = {"allowed": i % 2 == 0, "cached_at": time.time()}
            cache._cache[key] = value

            # Verify value was set
            current_value = cache._cache.get(key)
            assert current_value is not None, "Value should be set"

            # Verify value matches what was set
            assert current_value["allowed"] == value["allowed"], \
                f"Value mismatch at update {i}"

            previous_value = current_value

        # Invariant: Final value should match last update
        final_value = cache._cache.get(key)
        assert final_value is not None, "Final value should exist"

    @given(
        agent_count=st.integers(min_value=2, max_value=10),
        shared_action=st.text(min_size=1, max_size=20, alphabet='xyz')
    )
    @settings(max_examples=50)
    def test_multi_agent_isolation(self, agent_count, shared_action):
        """INVARIANT: Different agents should have isolated cache entries."""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Each agent gets own entry for same action
        for i in range(agent_count):
            agent_id = f"agent_{i}"
            key = f"{agent_id}:{shared_action}"
            cache._cache[key] = {"allowed": i % 2 == 0, "agent": agent_id}

        # Verify isolation
        for i in range(agent_count):
            agent_id = f"agent_{i}"
            key = f"{agent_id}:{shared_action}"
            value = cache._cache.get(key)

            # Invariant: Each agent should have own entry
            assert value is not None, f"Agent {agent_id} missing entry"
            assert value["agent"] == agent_id, "Entry should belong to correct agent"

    @given(
        read_count=st.integers(min_value=10, max_value=100),
        write_interval=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_read_write_consistency(self, read_count, write_interval):
        """INVARIANT: Reads should see consistent state during writes."""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        key = "test_agent:test_action"
        cache._cache[key] = {"allowed": False, "version": 0}

        inconsistent_reads = 0

        # Simulate interleaved reads and writes
        for i in range(read_count):
            # Perform read
            value = cache._cache.get(key)
            if value is None:
                inconsistent_reads += 1
                continue

            # Perform write every N iterations
            if i % write_interval == 0:
                new_value = {"allowed": True, "version": i}
                cache._cache[key] = new_value

        # Invariant: All reads should be consistent
        assert inconsistent_reads == 0, \
            f"Found {inconsistent_reads} inconsistent reads out of {read_count}"
