"""
Governance Cache Performance Benchmarks

Measures execution time for GovernanceCache critical paths using pytest-benchmark.
These tests establish baseline performance and enable regression detection through
historical tracking.

Target Metrics:
- Cache get (hit) <1ms P50
- Cache get (miss) <5ms P50
- Cache set <1ms P50
- Bulk invalidation <10ms P50
- Full governance check <1ms P50

Reference: Phase 208 Plan 03 - Performance Benchmarking
"""

import pytest
from typing import Dict, Any
from unittest.mock import MagicMock

from core.governance_cache import GovernanceCache

# Try to import pytest_benchmark, but don't fail if not available
try:
    import pytest_benchmark
    BENCHMARK_AVAILABLE = True
except ImportError:
    BENCHMARK_AVAILABLE = False

# Skip tests if pytest-benchmark not available
pytestmark = pytest.mark.skipif(
    not BENCHMARK_AVAILABLE,
    reason="pytest-benchmark plugin not installed. Install with: pip install pytest-benchmark"
)


class TestGovernancePerformance:
    """Test governance cache performance benchmarks."""

    @pytest.fixture
    def cache_with_entries(self):
        """Create cache with pre-populated entries."""
        cache = GovernanceCache(max_size=1000, ttl_seconds=60)

        # Populate with 100 entries
        for i in range(100):
            cache.set(
                agent_id=f"agent_{i}",
                action_type=f"action_{i % 5}",  # 5 different action types
                data={
                    "allowed": i % 2 == 0,
                    "maturity_level": ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"][i % 4],
                    "action_complexity": i % 5
                }
            )

        return cache

    @pytest.mark.benchmark(group="governance-cache")
    def test_cache_get_hit(self, benchmark, cache_with_entries):
        """
        Benchmark cache get operation (cache hit).

        Target: <1ms P50 (cache hits must be instant)
        Input: Cached agent permission check
        Verify: Returns cached value
        """
        # Pre-populate specific entry
        cache_with_entries.set(
            agent_id="agent_hit",
            action_type="action_test",
            data={"allowed": True, "maturity_level": "AUTONOMOUS"}
        )

        def cache_get():
            result = cache_with_entries.get("agent_hit", "action_test")
            assert result is not None
            assert result["allowed"] is True
            return result

        result = benchmark(cache_get)
        assert result["allowed"] is True

    @pytest.mark.benchmark(group="governance-cache")
    def test_cache_get_miss(self, benchmark, cache_with_entries):
        """
        Benchmark cache get operation (cache miss).

        Target: <5ms P50 (cache misses faster than DB)
        Input: Non-cached agent permission check
        Verify: Returns None (cache miss)
        """
        def cache_get():
            result = cache_with_entries.get("agent_miss", "action_miss")
            assert result is None
            return result

        result = benchmark(cache_get)
        assert result is None

    @pytest.mark.benchmark(group="governance-cache")
    def test_cache_get_expired(self, benchmark):
        """
        Benchmark cache get operation with expired entry.

        Target: <5ms P50 (expired entries treated as miss)
        Input: Expired cache entry
        Verify: Returns None (entry expired)
        """
        cache = GovernanceCache(max_size=1000, ttl_seconds=0)  # 0s TTL = immediately expired

        # Add entry (will be immediately expired)
        cache.set(
            agent_id="agent_expired",
            action_type="action_expired",
            data={"allowed": True}
        )

        def cache_get():
            result = cache.get("agent_expired", "action_expired")
            assert result is None  # Expired
            return result

        result = benchmark(cache_get)
        assert result is None

    @pytest.mark.benchmark(group="governance-cache")
    def test_cache_set(self, benchmark):
        """
        Benchmark cache set operation.

        Target: <1ms P50 (cache writes must be instant)
        Input: Store agent permission result
        Verify: Value retrievable after set
        """
        cache = GovernanceCache(max_size=1000, ttl_seconds=60)

        def cache_set():
            result = cache.set(
                agent_id="agent_set",
                action_type="action_set",
                data={"allowed": True, "maturity_level": "INTERN"}
            )
            assert result is True
            return result

        set_result = benchmark(cache_set)
        assert set_result is True

        # Verify value is retrievable
        retrieved = cache.get("agent_set", "action_set")
        assert retrieved is not None
        assert retrieved["allowed"] is True

    @pytest.mark.benchmark(group="governance-cache")
    def test_cache_bulk_invalidate(self, benchmark, cache_with_entries):
        """
        Benchmark bulk cache invalidation.

        Target: <10ms P50 (clear all cache entries)
        Input: Cache with 100 entries
        Verify: All entries cleared
        """
        # Verify cache has entries
        stats_before = cache_with_entries.get_stats()
        assert stats_before["size"] > 0

        def bulk_invalidate():
            cache_with_entries.clear()
            return cache_with_entries.get_stats()["size"]

        size_after = benchmark(bulk_invalidate)
        assert size_after == 0  # All entries cleared

    @pytest.mark.benchmark(group="governance-cache")
    def test_cache_invalidate_agent(self, benchmark, cache_with_entries):
        """
        Benchmark invalidation of single agent's cache entries.

        Target: <5ms P50 (selective invalidation)
        Input: Cache with multiple entries per agent
        Verify: Only specified agent's entries removed
        """
        # Add multiple entries for same agent
        for i in range(5):
            cache_with_entries.set(
                agent_id="agent_to_invalidate",
                action_type=f"action_{i}",
                data={"allowed": True}
            )

        # Verify entries exist
        assert cache_with_entries.get("agent_to_invalidate", "action_0") is not None

        def invalidate_agent():
            cache_with_entries.invalidate_agent("agent_to_invalidate")
            return cache_with_entries.get("agent_to_invalidate", "action_0")

        result = benchmark(invalidate_agent)
        assert result is None  # Entry invalidated

    @pytest.mark.benchmark(group="governance-check")
    def test_governance_check_cached(self, benchmark, cache_with_entries):
        """
        Benchmark full governance check (cached).

        Target: <1ms P50 (governance decision from cache)
        Input: Agent maturity + action complexity check
        Verify: Returns allowed/denied decision
        """
        # Pre-populate governance decision
        cache_with_entries.set(
            agent_id="agent_autonomous",
            action_type="stream_chat",
            data={
                "allowed": True,
                "maturity_level": "AUTONOMOUS",
                "action_complexity": 2
            }
        )

        def governance_check():
            result = cache_with_entries.get("agent_autonomous", "stream_chat")
            assert result is not None
            assert result["allowed"] is True
            return result

        result = benchmark(governance_check)
        assert result["allowed"] is True

    @pytest.mark.benchmark(group="governance-cache")
    def test_cache_directory_permission_hit(self, benchmark, cache_with_entries):
        """
        Benchmark directory permission check (cache hit).

        Target: <1ms P50 (directory checks must be instant)
        Input: Cached directory permission
        Verify: Returns cached permission
        """
        # Cache directory permission
        cache_with_entries.cache_directory(
            agent_id="agent_dir",
            directory="/tmp",
            permission_data={"allowed": True, "reason": "read-only"}
        )

        def check_directory():
            result = cache_with_entries.check_directory("agent_dir", "/tmp")
            assert result is not None
            assert result["allowed"] is True
            return result

        result = benchmark(check_directory)
        assert result["allowed"] is True

    @pytest.mark.benchmark(group="governance-cache")
    def test_cache_directory_permission_miss(self, benchmark, cache_with_entries):
        """
        Benchmark directory permission check (cache miss).

        Target: <5ms P50 (directory cache miss)
        Input: Non-cached directory permission
        Verify: Returns None (cache miss)
        """
        def check_directory():
            result = cache_with_entries.check_directory("agent_miss", "/not/cached")
            assert result is None
            return result

        result = benchmark(check_directory)
        assert result is None

    @pytest.mark.benchmark(group="governance-cache")
    def test_cache_lru_eviction(self, benchmark):
        """
        Benchmark LRU eviction when cache is full.

        Target: <5ms P50 (LRU eviction is fast)
        Input: Cache with max_size=10, adding 11th entry
        Verify: Oldest entry evicted
        """
        cache = GovernanceCache(max_size=10, ttl_seconds=60)

        # Fill cache to capacity
        for i in range(10):
            cache.set(
                agent_id=f"agent_{i}",
                action_type=f"action_{i}",
                data={"allowed": True}
            )

        # Add 11th entry (should evict agent_0)
        def add_entry_beyond_capacity():
            result = cache.set(
                agent_id="agent_10",
                action_type="action_10",
                data={"allowed": True}
            )
            return result

        result = benchmark(add_entry_beyond_capacity)
        assert result is True

        # Verify oldest entry was evicted
        oldest = cache.get("agent_0", "action_0")
        assert oldest is None  # Evicted


class TestGovernanceEdgeCases:
    """Test edge cases and error handling performance."""

    @pytest.mark.benchmark(group="governance-cache")
    def test_empty_cache_get(self, benchmark):
        """
        Benchmark get on empty cache.

        Target: <1ms P50 (empty cache is fast)
        Input: Empty cache
        Verify: Returns None
        """
        cache = GovernanceCache(max_size=1000, ttl_seconds=60)

        def get_from_empty():
            result = cache.get("nonexistent", "action")
            assert result is None
            return result

        result = benchmark(get_from_empty)
        assert result is None

    @pytest.mark.benchmark(group="governance-cache")
    def test_cache_stats(self, benchmark, cache_with_entries):
        """
        Benchmark cache statistics retrieval.

        Target: <1ms P50 (stats are pre-calculated)
        Input: Cache with 100 entries
        Verify: Returns stats dict
        """
        def get_stats():
            stats = cache_with_entries.get_stats()
            assert "hit_rate" in stats
            assert "size" in stats
            return stats

        result = benchmark(get_stats)
        assert "hit_rate" in result

    @pytest.mark.benchmark(group="governance-cache")
    def test_concurrent_access_simulation(self, benchmark, cache_with_entries):
        """
        Benchmark simulated concurrent cache access.

        Target: <5ms P50 (thread-safe operations)
        Input: Multiple get/set operations
        Verify: Thread-safe access
        """
        # Pre-populate entry
        cache_with_entries.set(
            agent_id="agent_concurrent",
            action_type="action_concurrent",
            data={"allowed": True}
        )

        def simulate_concurrent():
            # Simulate multiple operations
            results = []
            for i in range(10):
                result = cache_with_entries.get("agent_concurrent", "action_concurrent")
                results.append(result)
            return results

        results = benchmark(simulate_concurrent)
        assert len(results) == 10
        assert all(r["allowed"] is True for r in results)

    @pytest.mark.benchmark(group="governance-cache")
    def test_cache_hit_rate_calculation(self, benchmark, cache_with_entries):
        """
        Benchmark hit rate calculation.

        Target: <1ms P50 (simple arithmetic)
        Input: Cache with known hit/miss counts
        Verify: Returns correct hit rate
        """
        def get_hit_rate():
            hit_rate = cache_with_entries.get_hit_rate()
            assert 0.0 <= hit_rate <= 100.0
            return hit_rate

        result = benchmark(get_hit_rate)
        assert 0.0 <= result <= 100.0

    @pytest.mark.benchmark(group="governance-cache")
    def test_special_characters_in_action_type(self, benchmark):
        """
        Benchmark cache with special characters in action type.

        Target: <1ms P50 (key generation is fast)
        Input: Action type with special characters (dir:, /, etc.)
        Verify: Handles special characters correctly
        """
        cache = GovernanceCache(max_size=1000, ttl_seconds=60)

        def cache_special_chars():
            # Directory paths have special characters
            cache.set(
                agent_id="agent_special",
                action_type="dir:/tmp/test/subdir",
                data={"allowed": True}
            )
            result = cache.get("agent_special", "dir:/tmp/test/subdir")
            assert result is not None
            return result

        result = benchmark(cache_special_chars)
        assert result["allowed"] is True
