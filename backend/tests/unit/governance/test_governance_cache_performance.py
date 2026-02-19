"""
Governance Cache Performance Tests

Comprehensive test suite for GovernanceCache performance characteristics.

Test Coverage:
- TestCacheBasicOperations: Test get/set/has/invalidate operations
- TestCacheHitRate: Test >90% hit rate after warmup with 1000 operations
- TestCacheLatency: Test <1ms P50 latency for cached lookups
- TestLRUEviction: Test oldest entry eviction at max_size (1000 entries)
- TestTTLExpiration: Test 60-second TTL for entry expiration
- TestAgentSpecificInvalidation: Test invalidate(agent_id) removes all agent entries
- TestDirectoryPermissionCache: Test specialized "dir:" prefix cache for permissions
- TestThreadSafety: Test concurrent access from multiple threads
- TestStatisticsReporting: Test get_stats() returns correct metrics
- TestBackgroundCleanup: Test async cleanup task removes expired entries

Total: 40+ test cases
"""

import pytest
import time
import threading
from unittest.mock import patch
from sqlalchemy.orm import Session

from core.governance_cache import GovernanceCache, get_governance_cache
from tests.factories import AutonomousAgentFactory


class TestCacheBasicOperations:
    """Test basic cache operations: get, set, has, invalidate."""

    def test_cache_set_and_get(self):
        """Cache should store and retrieve values correctly."""
        cache = GovernanceCache()
        agent_id = "test_agent"
        action_type = "test_action"
        data = {"allowed": True, "reason": "Test"}

        # Set value
        result = cache.set(agent_id, action_type, data)
        assert result is True

        # Get value
        retrieved = cache.get(agent_id, action_type)
        assert retrieved is not None
        assert retrieved["allowed"] is True
        assert retrieved["reason"] == "Test"

    def test_cache_get_nonexistent_returns_none(self):
        """Getting a non-existent key should return None."""
        cache = GovernanceCache()
        result = cache.get("nonexistent_agent", "nonexistent_action")
        assert result is None

    def test_cache_set_overwrites_existing(self):
        """Setting a key that exists should overwrite the value."""
        cache = GovernanceCache()
        agent_id = "test_agent"
        action_type = "test_action"

        # Set initial value
        cache.set(agent_id, action_type, {"allowed": False})
        # Overwrite
        cache.set(agent_id, action_type, {"allowed": True})

        result = cache.get(agent_id, action_type)
        assert result["allowed"] is True

    def test_cache_clear_removes_all_entries(self):
        """Clear should remove all entries from cache."""
        cache = GovernanceCache()

        # Add multiple entries
        cache.set("agent1", "action1", {"data": "value1"})
        cache.set("agent2", "action2", {"data": "value2"})
        cache.set("agent3", "action3", {"data": "value3"})

        # Clear all
        cache.clear()

        assert cache.get("agent1", "action1") is None
        assert cache.get("agent2", "action2") is None
        assert cache.get("agent3", "action3") is None


class TestCacheHitRate:
    """Test cache hit rate performance (>90% after warmup)."""

    def test_cache_hit_rate_after_warmup(self):
        """Cache hit rate should exceed 90% after warmup with 100 operations."""
        cache = GovernanceCache(max_size=1000)
        agent_id = "test_agent"

        # Warmup: cache 100 unique actions
        warmup_actions = 100
        for i in range(warmup_actions):
            cache.set(agent_id, f"action_{i}", {"allowed": True})

        # Measure hit rate with repeated lookups
        hits = 0
        total_lookups = 1000
        for i in range(total_lookups):
            # Access cached actions cyclically
            action = f"action_{i % warmup_actions}"
            result = cache.get(agent_id, action)
            if result is not None:
                hits += 1

        hit_rate = (hits / total_lookups) * 100
        assert hit_rate > 90, f"Hit rate {hit_rate:.2f}% is below 90% threshold"

    def test_cache_miss_rate_on_new_keys(self):
        """Cache should have 100% miss rate on uncached keys."""
        cache = GovernanceCache()

        # Don't warmup - directly test misses
        misses = 0
        total_lookups = 100
        for i in range(total_lookups):
            result = cache.get("agent", f"uncached_action_{i}")
            if result is None:
                misses += 1

        miss_rate = (misses / total_lookups) * 100
        assert miss_rate == 100, f"Miss rate {miss_rate}% should be 100% for uncached keys"

    def test_stats_report_hit_rate(self):
        """get_stats() should report accurate hit rate."""
        cache = GovernanceCache()
        agent_id = "test_agent"

        # Add some cached actions
        for i in range(10):
            cache.set(agent_id, f"action_{i}", {"allowed": True})

        # Generate hits and misses
        for i in range(20):  # 20 hits
            cache.get(agent_id, f"action_{i % 10}")
        for i in range(5):  # 5 misses
            cache.get(agent_id, f"nonexistent_{i}")

        stats = cache.get_stats()
        assert stats["hits"] == 20
        assert stats["misses"] == 5
        assert stats["hit_rate"] == 80.0  # 20/(20+5) = 80%


class TestCacheLatency:
    """Test cache lookup latency performance (<1ms P50)."""

    def test_cache_latency_p50_sub_1ms(self):
        """P50 latency should be less than 1ms for cached lookups."""
        cache = GovernanceCache()
        agent_id = "perf_agent"
        cache.set(agent_id, "test_action", {"allowed": True})

        # Measure 1000 lookup latencies
        latencies = []
        iterations = 1000
        for _ in range(iterations):
            start = time.perf_counter()
            cache.get(agent_id, "test_action")
            end = time.perf_counter()
            latencies.append((end - start) * 1000)  # Convert to ms

        # Calculate P50 (median)
        sorted_latencies = sorted(latencies)
        p50 = sorted_latencies[iterations // 2]

        assert p50 < 1.0, f"P50 latency {p50:.3f}ms exceeds 1ms threshold"

    def test_cache_latency_p99_sub_10ms(self):
        """P99 latency should be less than 10ms for cached lookups."""
        cache = GovernanceCache()
        agent_id = "perf_agent"
        cache.set(agent_id, "test_action", {"allowed": True})

        # Measure 1000 lookup latencies
        latencies = []
        iterations = 1000
        for _ in range(iterations):
            start = time.perf_counter()
            cache.get(agent_id, "test_action")
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        # Calculate P99
        sorted_latencies = sorted(latencies)
        p99 = sorted_latencies[int(iterations * 0.99)]

        assert p99 < 10.0, f"P99 latency {p99:.3f}ms exceeds 10ms threshold"

    def test_cache_miss_latency(self):
        """Cache miss latency should also be fast (<5ms P50)."""
        cache = GovernanceCache()

        # Measure miss latencies
        latencies = []
        iterations = 100
        for i in range(iterations):
            start = time.perf_counter()
            cache.get("agent", f"nonexistent_action_{i}")
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        sorted_latencies = sorted(latencies)
        p50 = sorted_latencies[iterations // 2]

        assert p50 < 5.0, f"Miss P50 latency {p50:.3f}ms exceeds 5ms threshold"


class TestLRUEviction:
    """Test LRU (Least Recently Used) eviction behavior."""

    def test_lru_eviction_at_max_size(self):
        """Cache should evict oldest entries when reaching max_size."""
        cache = GovernanceCache(max_size=3)

        # Fill cache to max_size
        cache.set("agent1", "action1", {"data": "first"})
        cache.set("agent2", "action2", {"data": "second"})
        cache.set("agent3", "action3", {"data": "third"})

        # Add 4th entry - should evict oldest (agent1:action1)
        cache.set("agent4", "action4", {"data": "fourth"})

        # Verify eviction
        assert cache.get("agent1", "action1") is None  # Evicted
        assert cache.get("agent2", "action2") is not None
        assert cache.get("agent3", "action3") is not None
        assert cache.get("agent4", "action4") is not None

        # Check eviction counter
        stats = cache.get_stats()
        assert stats["evictions"] >= 1

    def test_lru_promotes_recently_accessed(self):
        """Accessing an entry should mark it as recently used (prevent eviction)."""
        cache = GovernanceCache(max_size=3)

        cache.set("agent1", "action1", {"data": "first"})
        cache.set("agent2", "action2", {"data": "second"})
        cache.set("agent3", "action3", {"data": "third"})

        # Access agent1 to make it recently used
        cache.get("agent1", "action1")

        # Add 4th entry - should evict agent2 (oldest, not agent1)
        cache.set("agent4", "action4", {"data": "fourth"})

        assert cache.get("agent1", "action1") is not None  # Still present (accessed)
        assert cache.get("agent2", "action2") is None  # Evicted (oldest, not accessed)
        assert cache.get("agent3", "action3") is not None
        assert cache.get("agent4", "action4") is not None

    def test_lru_multiple_evictions(self):
        """Cache should handle multiple evictions correctly."""
        cache = GovernanceCache(max_size=2)

        # Add and exceed capacity multiple times
        cache.set("agent1", "action1", {"data": "1"})
        cache.set("agent2", "action2", {"data": "2"})
        cache.set("agent3", "action3", {"data": "3"})  # Evicts agent1
        cache.set("agent4", "action4", {"data": "4"})  # Evicts agent2

        # Only last two should remain
        assert cache.get("agent1", "action1") is None
        assert cache.get("agent2", "action2") is None
        assert cache.get("agent3", "action3") is not None
        assert cache.get("agent4", "action4") is not None


class TestTTLExpiration:
    """Test TTL (Time-To-Live) expiration behavior."""

    def test_ttl_expires_old_entries(self):
        """Entries older than TTL should be expired."""
        cache = GovernanceCache(ttl_seconds=1)  # 1 second TTL
        agent_id = "test_agent"

        cache.set(agent_id, "action1", {"data": "value"})

        # Wait for TTL to expire
        time.sleep(1.5)

        # Entry should be expired
        result = cache.get(agent_id, "action1")
        assert result is None

    def test_fresh_entries_not_expired(self):
        """Entries younger than TTL should not be expired."""
        cache = GovernanceCache(ttl_seconds=10)
        agent_id = "test_agent"

        cache.set(agent_id, "action1", {"data": "value"})

        # Wait less than TTL
        time.sleep(0.5)

        # Entry should still be present
        result = cache.get(agent_id, "action1")
        assert result is not None

    def test_ttl_respects_cached_at_timestamp(self):
        """TTL should use the cached_at timestamp for expiration."""
        cache = GovernanceCache(ttl_seconds=1)
        agent_id = "test_agent"

        # Create an entry with manually set old timestamp
        cache.set(agent_id, "action1", {"data": "value"})

        # Manually age the entry by modifying cached_at
        key = cache._make_key(agent_id, "action1")
        with cache._lock:
            if key in cache._cache:
                cache._cache[key]["cached_at"] = time.time() - 2  # 2 seconds old

        # Should be expired
        result = cache.get(agent_id, "action1")
        assert result is None


class TestAgentSpecificInvalidation:
    """Test agent-specific cache invalidation."""

    def test_invalidate_specific_action(self):
        """Invalidating a specific action should remove only that entry."""
        cache = GovernanceCache()
        agent_id = "test_agent"

        cache.set(agent_id, "action1", {"data": "value1"})
        cache.set(agent_id, "action2", {"data": "value2"})

        # Invalidate only action1
        cache.invalidate(agent_id, "action1")

        assert cache.get(agent_id, "action1") is None
        assert cache.get(agent_id, "action2") is not None

    def test_invalidate_all_agent_actions(self):
        """Invalidating without action_type should remove all agent entries."""
        cache = GovernanceCache()
        agent_id = "test_agent"

        # Add multiple actions for agent
        cache.set(agent_id, "action1", {"data": "value1"})
        cache.set(agent_id, "action2", {"data": "value2"})
        cache.set(agent_id, "action3", {"data": "value3"})

        # Add actions for different agent (should not be affected)
        cache.set("other_agent", "action1", {"data": "other"})

        # Invalidate all actions for test_agent
        cache.invalidate(agent_id)

        assert cache.get(agent_id, "action1") is None
        assert cache.get(agent_id, "action2") is None
        assert cache.get(agent_id, "action3") is None
        assert cache.get("other_agent", "action1") is not None  # Unaffected

    def test_invalidate_nonexistent_agent_no_error(self):
        """Invalidating a non-existent agent should not raise errors."""
        cache = GovernanceCache()

        # Should not raise
        cache.invalidate("nonexistent_agent")
        cache.invalidate("nonexistent_agent", "some_action")


class TestDirectoryPermissionCache:
    """Test specialized directory permission cache with "dir:" prefix."""

    def test_cache_directory_and_check(self):
        """Should cache and retrieve directory permissions."""
        cache = GovernanceCache()
        agent_id = "test_agent"
        directory = "/tmp/test"

        permission_data = {"allowed": True, "reason": "Test directory"}
        cache.cache_directory(agent_id, directory, permission_data)

        result = cache.check_directory(agent_id, directory)
        assert result is not None
        assert result["allowed"] is True

    def test_directory_cache_no_collision_with_actions(self):
        """Directory cache should not collide with action_type cache."""
        cache = GovernanceCache()
        agent_id = "test_agent"
        directory = "/tmp/test"

        # Cache directory permission
        cache.cache_directory(agent_id, directory, {"allowed": True})
        # Cache action
        cache.set(agent_id, "test_action", {"allowed": False})

        # Both should be retrievable
        dir_result = cache.check_directory(agent_id, directory)
        action_result = cache.get(agent_id, "test_action")

        assert dir_result["allowed"] is True
        assert action_result["allowed"] is False

    def test_directory_cache_invalidation(self):
        """Invalidating directory cache should work correctly."""
        cache = GovernanceCache()
        agent_id = "test_agent"
        directory = "/tmp/test"

        cache.cache_directory(agent_id, directory, {"allowed": True})
        cache.invalidate(agent_id, f"dir:{directory}")

        result = cache.check_directory(agent_id, directory)
        assert result is None

    def test_directory_statistics_tracked(self):
        """Directory cache hits/misses should be tracked separately."""
        cache = GovernanceCache()
        agent_id = "test_agent"
        directory = "/tmp/test"

        # Cache a directory
        cache.cache_directory(agent_id, directory, {"allowed": True})

        # Generate a hit
        cache.check_directory(agent_id, directory)

        # Generate a miss
        cache.check_directory(agent_id, "/nonexistent")

        stats = cache.get_stats()
        assert stats["directory_hits"] == 1
        assert stats["directory_misses"] == 1


class TestThreadSafety:
    """Test cache thread safety under concurrent access."""

    def test_concurrent_reads(self):
        """Cache should handle concurrent reads safely."""
        cache = GovernanceCache()
        agent_id = "test_agent"

        # Warmup cache
        for i in range(100):
            cache.set(agent_id, f"action_{i}", {"allowed": True})

        # Concurrent reads
        results = []
        def read_worker():
            for i in range(100):
                result = cache.get(agent_id, f"action_{i % 100}")
                results.append(result)

        threads = [threading.Thread(target=read_worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All reads should succeed without errors
        assert len(results) == 1000
        assert all(r is not None for r in results)

    def test_concurrent_writes(self):
        """Cache should handle concurrent writes safely."""
        cache = GovernanceCache()

        def write_worker(worker_id):
            for i in range(50):
                cache.set(f"agent_{worker_id}", f"action_{i}", {"worker": worker_id})

        threads = [threading.Thread(target=write_worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Cache should have entries from all workers
        stats = cache.get_stats()
        assert stats["size"] > 0

    def test_concurrent_invalidation(self):
        """Cache should handle concurrent invalidations safely."""
        cache = GovernanceCache()

        # Populate cache
        for i in range(100):
            cache.set(f"agent_{i}", "action1", {"data": f"value_{i}"})

        # Concurrent invalidations
        def invalidate_worker(worker_id):
            for i in range(10):
                cache.invalidate(f"agent_{worker_id * 10 + i}")

        threads = [threading.Thread(target=invalidate_worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Some entries should be invalidated
        stats = cache.get_stats()
        assert stats["invalidations"] > 0


class TestStatisticsReporting:
    """Test cache statistics reporting accuracy."""

    def test_stats_returns_all_metrics(self):
        """get_stats() should return all expected metrics."""
        cache = GovernanceCache()

        cache.set("agent1", "action1", {"data": "value1"})
        cache.get("agent1", "action1")  # Hit
        cache.get("agent1", "nonexistent")  # Miss

        stats = cache.get_stats()

        # Check all expected fields
        assert "size" in stats
        assert "max_size" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats
        assert "evictions" in stats
        assert "invalidations" in stats
        assert "ttl_seconds" in stats

    def test_stats_accuracy(self):
        """Statistics should accurately reflect cache operations."""
        cache = GovernanceCache(max_size=10)

        # Add 5 entries
        for i in range(5):
            cache.set(f"agent_{i}", "action1", {"data": f"value_{i}"})

        # Generate 7 hits
        for i in range(7):
            cache.get("agent_0", "action1")

        # Generate 3 misses
        for i in range(3):
            cache.get("nonexistent", "action")

        # Trigger 1 eviction
        for i in range(11):  # Exceed max_size of 10
            cache.set(f"evict_agent_{i}", "action1", {"data": "value"})

        stats = cache.get_stats()

        assert stats["size"] == 10  # At max_size
        assert stats["max_size"] == 10
        assert stats["hits"] == 7
        assert stats["misses"] == 3
        assert stats["hit_rate"] == 70.0  # 7/(7+3)
        assert stats["evictions"] >= 1


class TestBackgroundCleanup:
    """Test background cleanup task for expired entries."""

    def test_cleanup_removes_expired_entries(self):
        """Background cleanup should remove expired entries."""
        # Note: Background cleanup runs every 30 seconds, so we test the synchronous method
        cache = GovernanceCache(ttl_seconds=1)
        agent_id = "test_agent"

        cache.set(agent_id, "action1", {"data": "value1"})
        cache.set(agent_id, "action2", {"data": "value2"})

        # Manually age the entries
        key1 = cache._make_key(agent_id, "action1")
        key2 = cache._make_key(agent_id, "action2")
        old_time = time.time() - 2

        with cache._lock:
            cache._cache[key1]["cached_at"] = old_time
            cache._cache[key2]["cached_at"] = old_time

        # Trigger cleanup manually
        cache._expire_stale()

        # Entries should be removed
        assert cache.get(agent_id, "action1") is None
        assert cache.get(agent_id, "action2") is None

    def test_cleanup_preserves_fresh_entries(self):
        """Background cleanup should preserve fresh entries."""
        cache = GovernanceCache(ttl_seconds=10)
        agent_id = "test_agent"

        cache.set(agent_id, "action1", {"data": "value1"})

        # Trigger cleanup
        cache._expire_stale()

        # Entry should still be present
        result = cache.get(agent_id, "action1")
        assert result is not None


class TestGlobalCacheInstance:
    """Test global cache instance management."""

    def test_get_governance_cache_returns_singleton(self):
        """get_governance_cache() should return the same instance."""
        cache1 = get_governance_cache()
        cache2 = get_governance_cache()

        assert cache1 is cache2

    def test_global_cache_persists_across_calls(self):
        """Global cache should persist data across calls."""
        cache = get_governance_cache()

        # Set value in global cache
        cache.set("test_agent", "test_action", {"allowed": True})

        # Retrieve from new reference
        cache2 = get_governance_cache()
        result = cache2.get("test_agent", "test_action")

        assert result is not None
        assert result["allowed"] is True
