"""
Unit Tests for Governance Cache Performance

Tests cover:
- Cache hit rate (>95% target)
- Cache latency (<1ms target)
- Cache invalidation
- Cache warming
"""
import pytest
import time
from sqlalchemy.orm import Session

from core.governance_cache import GovernanceCache
from tests.factories import AgentFactory


class TestGovernanceCachePerformance:
    """Test governance cache performance."""

    @pytest.fixture
    def cache(self, db_session):
        """Create cache."""
        # Clear cache to start fresh
        cache = GovernanceCache()
        cache.clear()
        return cache

    def test_cache_hit_rate_gt_95_percent(self, cache, db_session):
        """Cache hit rate should exceed 95%."""
        # Create 100 agents
        agents = [AgentFactory(_session=db_session) for _ in range(100)]
        db_session.commit()

        # Warm cache
        for agent in agents:
            cache.set(agent.id, "test_action", {"allowed": True})

        # Measure hit rate
        hits = 0
        queries = 1000
        for i in range(queries):
            agent_id = agents[i % len(agents)].id
            result = cache.get(agent_id, "test_action")
            if result is not None:
                hits += 1

        hit_rate = hits / queries
        assert hit_rate > 0.95, f"Hit rate {hit_rate:.1%} should exceed 95%"

    def test_cache_latency_lt_1ms(self, cache, db_session):
        """Cache lookup should be <1ms (P99)."""
        agent = AgentFactory(_session=db_session)
        db_session.commit()

        # Warm cache
        cache.set(agent.id, "test_action", {"allowed": True})

        # Measure P99 latency
        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            cache.get(agent.id, "test_action")
            end = time.perf_counter()
            latencies.append((end - start) * 1000)  # Convert to ms

        # Sort and get P99
        latencies.sort()
        p99_latency = latencies[int(0.99 * len(latencies))]

        assert p99_latency < 1.0, f"P99 latency {p99_latency:.3f}ms should be <1ms"

    def test_cache_invalidation_removes_entry(self, cache):
        """Cache invalidation removes cached entries."""
        agent_id = "test-agent-123"

        # Set cache entry
        cache.set(agent_id, "test_action", {"allowed": True})
        assert cache.get(agent_id, "test_action") is not None

        # Invalidate
        cache.invalidate(agent_id, "test_action")
        assert cache.get(agent_id, "test_action") is None

    def test_cache_invalidation_agent_level(self, cache):
        """Cache invalidation at agent level removes all actions."""
        agent_id = "test-agent-456"

        # Set multiple actions for same agent
        cache.set(agent_id, "action1", {"allowed": True})
        cache.set(agent_id, "action2", {"allowed": True})
        cache.set(agent_id, "action3", {"allowed": True})

        # Invalidate all actions for agent
        cache.invalidate_agent(agent_id)

        # All should be gone
        assert cache.get(agent_id, "action1") is None
        assert cache.get(agent_id, "action2") is None
        assert cache.get(agent_id, "action3") is None

    def test_cache_warming_strategy(self, cache, db_session):
        """Cache warming improves hit rate."""
        # Create agents
        agents = [AgentFactory(_session=db_session) for _ in range(20)]

        # Measure misses before warming
        misses_before = cache.get_stats()["misses"]
        for agent in agents:
            cache.get(agent.id, "test_action")
        misses_after_cold = cache.get_stats()["misses"] - misses_before

        # Warm cache
        for agent in agents:
            cache.set(agent.id, "test_action", {"allowed": True})

        # Measure hits after warming
        hits = 0
        for agent in agents:
            result = cache.get(agent.id, "test_action")
            if result is not None:
                hits += 1

        # All should be hits
        assert hits == len(agents), f"Cache warming failed: {hits}/{len(agents)} hits"

    def test_cache_lru_eviction_policy(self, cache):
        """Cache evicts least recently used entries when at capacity."""
        small_cache = GovernanceCache(max_size=10)

        # Add 15 entries (more than max_size)
        for i in range(15):
            small_cache.set(f"agent_{i}", "action", {"data": f"value_{i}"})

        # Cache should not exceed max_size
        stats = small_cache.get_stats()
        assert stats["size"] <= 10, f"Cache size {stats['size']} exceeds max_size 10"

        # Most recently added items should be present
        assert small_cache.get("agent_14", "action") is not None
        assert small_cache.get("agent_13", "action") is not None

        # Oldest items might be evicted
        # (LRU eviction means agent_0, agent_1 likely evicted)

    def test_cache_ttl_expiration(self, cache):
        """Cache entries expire after TTL."""
        import time

        # Create cache with short TTL for testing
        short_ttl_cache = GovernanceCache(ttl_seconds=1)

        agent_id = "test-agent-ttl"

        # Set entry
        short_ttl_cache.set(agent_id, "action", {"data": "value"})
        assert short_ttl_cache.get(agent_id, "action") is not None

        # Wait for TTL to expire
        time.sleep(1.1)

        # Entry should be expired
        result = short_ttl_cache.get(agent_id, "action")
        assert result is None, "Cache entry should expire after TTL"

    def test_cache_stats_tracking(self, cache):
        """Cache statistics are tracked accurately."""
        # Perform some operations
        cache.set("agent1", "action1", {"data": "value1"})
        cache.get("agent1", "action1")  # Hit
        cache.get("agent2", "action2")  # Miss
        cache.get("agent3", "action3")  # Miss
        cache.set("agent2", "action2", {"data": "value2"})
        cache.get("agent2", "action2")  # Hit

        stats = cache.get_stats()

        # Verify stats
        assert stats["hits"] == 2
        assert stats["misses"] == 2
        assert stats["size"] == 2

        hit_rate = stats["hit_rate"]
        expected_rate = 2 / 4 * 100  # 2 hits out of 4 total
        assert abs(hit_rate - expected_rate) < 1.0  # Allow small rounding error

    def test_cache_clear_removes_all_entries(self, cache):
        """Cache clear removes all entries."""
        # Add some entries
        for i in range(10):
            cache.set(f"agent_{i}", "action", {"data": f"value_{i}"})

        assert cache.get_stats()["size"] == 10

        # Clear all
        cache.clear()

        assert cache.get_stats()["size"] == 0
        assert cache.get("agent_0", "action") is None

    def test_cache_concurrent_access_thread_safe(self, cache):
        """Cache is thread-safe for concurrent access."""
        import threading

        results = {"errors": 0}
        num_threads = 10
        operations_per_thread = 100

        def worker(thread_id):
            try:
                for i in range(operations_per_thread):
                    # Mix of reads and writes
                    agent_id = f"agent_{thread_id}_{i % 10}"
                    if i % 2 == 0:
                        cache.set(agent_id, "action", {"data": f"value_{i}"})
                    else:
                        cache.get(agent_id, "action")
            except Exception as e:
                results["errors"] += 1

        # Create and start threads
        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join()

        # Should have no errors
        assert results["errors"] == 0, f"Thread safety test failed with {results['errors']} errors"

    def test_cache_directory_operations(self, cache):
        """Cache supports directory-specific operations."""
        agent_id = "test-agent-dir"

        # Cache directory permission
        cache.cache_directory(
            agent_id=agent_id,
            directory="/tmp/test",
            permission_data={"allowed": True, "read_only": True}
        )

        # Check directory permission
        result = cache.check_directory(agent_id, "/tmp/test")
        assert result is not None
        assert result["allowed"] is True
        assert result["read_only"] is True

        # Different directory should miss
        result = cache.check_directory(agent_id, "/var/test")
        assert result is None

    def test_cache_miss_returns_none(self, cache):
        """Cache miss returns None for non-existent entries."""
        result = cache.get("nonexistent-agent", "nonexistent-action")
        assert result is None

    def test_cache_set_overwrites_existing(self, cache):
        """Cache set overwrites existing entry."""
        agent_id = "test-agent-overwrite"

        # Set initial value
        cache.set(agent_id, "action", {"data": "initial"})
        result1 = cache.get(agent_id, "action")
        assert result1["data"] == "initial"

        # Overwrite with new value
        cache.set(agent_id, "action", {"data": "updated"})
        result2 = cache.get(agent_id, "action")
        assert result2["data"] == "updated"

        # Size should still be 1 (not 2)
        stats = cache.get_stats()
        assert stats["size"] == 1

    def test_cache_get_hit_rate_helper(self, cache):
        """get_hit_rate helper returns correct percentage."""
        # Empty cache
        assert cache.get_hit_rate() == 0.0

        # Add some operations
        cache.set("agent1", "action1", {"data": "value1"})
        cache.get("agent1", "action1")  # Hit
        cache.get("agent2", "action2")  # Miss

        hit_rate = cache.get_hit_rate()
        expected = 1 / 2 * 100  # 1 hit out of 2
        assert abs(hit_rate - expected) < 1.0

    def test_cache_performance_under_load(self, cache, db_session):
        """Cache maintains performance under high load."""
        # Create 1000 agents
        agents = [AgentFactory(_session=db_session) for _ in range(1000)]

        # Warm up cache
        for agent in agents:
            cache.set(agent.id, "action", {"allowed": True})

        # Measure latency under load
        start = time.perf_counter()
        for agent in agents:
            cache.get(agent.id, "action")
        end = time.perf_counter()

        total_time_ms = (end - start) * 1000
        avg_latency_ms = total_time_ms / len(agents)

        # Average should be very fast (<0.1ms)
        assert avg_latency_ms < 0.1, f"Average latency {avg_latency_ms:.3f}ms too high under load"

    def test_cache_memory_efficiency(self, cache):
        """Cache doesn't grow unbounded (LRU eviction works)."""
        large_cache = GovernanceCache(max_size=100)

        # Add 1000 entries (10x max_size)
        for i in range(1000):
            large_cache.set(f"agent_{i}", "action", {"data": f"value_{i}"})

        # Size should be bounded by max_size
        stats = large_cache.get_stats()
        assert stats["size"] <= 100, f"Cache size {stats['size']} exceeded max_size"
        assert stats["evictions"] > 0, "Cache should have evicted entries"
