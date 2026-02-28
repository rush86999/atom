"""
Boundary Condition Tests for Governance Cache

Tests exact boundary values where bugs commonly occur in the governance cache:
- Cache size boundaries (0, at capacity, over capacity)
- TTL boundaries (exact expiration, zero TTL, very large TTL)
- Agent ID boundaries (empty, very long, unicode, special chars)
- Action type boundaries (empty, very long, special patterns)
- Statistics boundaries (zero requests, 100% hit rate, 0% hit rate)

Common bugs tested:
- Off-by-one errors in capacity checks
- Integer overflow with large cache sizes
- Unicode handling errors in cache keys
- Division by zero in hit rate calculation
"""

import pytest
import time
from datetime import timedelta

from core.governance_cache import GovernanceCache


class TestGovernanceCacheSizeBoundaries:
    """Test cache size boundaries including capacity limits and LRU eviction."""

    @pytest.mark.parametrize("max_size,entries,expected_evictions", [
        (1, 0, 0),      # Empty cache
        (1, 1, 0),      # Exactly at capacity
        (1, 2, 1),      # One over capacity
        (10, 10, 0),    # At capacity
        (10, 11, 1),    # One over capacity
        (100, 100, 0),  # At capacity (larger)
        (100, 101, 1),  # One over capacity
        (100, 200, 100),  # Double capacity
        (1000, 2000, 1000),  # Double capacity (large)
    ])
    def test_cache_size_boundaries(self, max_size, entries, expected_evictions):
        """
        BOUNDARY: Test cache size limits at exact boundaries.

        Common bug: Off-by-one error causes incorrect eviction count.
        """
        cache = GovernanceCache(max_size=max_size, ttl_seconds=60)

        # Fill cache with entries
        for i in range(entries):
            cache.set(f"agent_{i}", "test_action", {"data": i})

        stats = cache.get_stats()
        assert stats["evictions"] == expected_evictions, (
            f"Expected {expected_evictions} evictions for max_size={max_size}, "
            f"entries={entries}, got {stats['evictions']}"
        )

        # Verify cache size never exceeds max
        assert stats["size"] <= max_size, (
            f"Cache size {stats['size']} exceeds max_size {max_size}"
        )

    def test_cache_empty_operations(self):
        """
        BOUNDARY: Test operations on empty cache.

        Common bug: Division by zero when calculating hit rate.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # No requests made yet
        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0.0  # Should handle 0/0 division

        # Get from empty cache
        result = cache.get("nonexistent", "action")
        assert result is None
        assert stats["misses"] == 1

    @pytest.mark.parametrize("hit_count,miss_count,expected_rate", [
        (0, 0, 0.0),      # No requests
        (10, 0, 100.0),   # All hits
        (0, 10, 0.0),     # All misses
        (5, 5, 50.0),     # 50% hits
        (1, 99, 1.0),     # 1% hit rate
        (99, 1, 99.0),    # 99% hit rate
    ])
    def test_hit_rate_boundaries(self, hit_count, miss_count, expected_rate):
        """
        BOUNDARY: Test hit rate calculation at extreme values.

        Common bug: Division by zero when hit_count + miss_count = 0.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Manually set hit/miss counts (bypassing cache operations)
        cache._hits = hit_count
        cache._misses = miss_count

        stats = cache.get_stats()
        assert stats["hit_rate"] == expected_rate

    def test_cache_size_zero(self):
        """
        BOUNDARY: Test cache with max_size=0 (should reject all entries).

        Common bug: Cache allows entries when max_size=0.
        """
        cache = GovernanceCache(max_size=0, ttl_seconds=60)

        # Try to add an entry
        success = cache.set("agent_1", "action", {"data": 1})

        # Should either fail or immediately evict
        stats = cache.get_stats()
        assert stats["size"] == 0, "Cache with max_size=0 should not hold entries"


class TestGovernanceCacheTTLBoundaries:
    """Test TTL (time-to-live) boundaries including exact expiration. """

    @pytest.mark.parametrize("ttl_seconds,wait_seconds,should_exist", [
        (0, 0.01, False),     # Zero TTL: expires immediately
        (1, 0.5, True),       # 1s TTL, check at 0.5s: should exist
        (1, 1.5, False),      # 1s TTL, check at 1.5s: should expire
        (10, 9, True),        # 10s TTL, check at 9s: should exist
        (10, 11, False),      # 10s TTL, check at 11s: should expire
        (60, 59, True),       # 60s TTL, check at 59s: should exist
        (60, 61, False),      # 60s TTL, check at 61s: should expire
    ])
    def test_ttl_boundaries(self, ttl_seconds, wait_seconds, should_exist):
        """
        BOUNDARY: Test TTL expiration at exact boundaries.

        Common bug: Using >= instead of > for TTL check causes premature expiration.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=ttl_seconds)

        # Add entry
        cache.set("agent_1", "action", {"data": "test"})

        # Wait specified time
        time.sleep(wait_seconds)

        # Check if entry exists
        result = cache.get("agent_1", "action")

        if should_exist:
            assert result is not None, (
                f"Entry should exist after {wait_seconds}s with TTL={ttl_seconds}s"
            )
        else:
            assert result is None, (
                f"Entry should expire after {wait_seconds}s with TTL={ttl_seconds}s"
            )

    def test_very_large_ttl(self):
        """
        BOUNDARY: Test cache with very large TTL (24 hours).

        Common bug: Integer overflow in TTL calculation.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=86400)  # 24 hours

        cache.set("agent_1", "action", {"data": "test"})

        # Should exist immediately
        result = cache.get("agent_1", "action")
        assert result is not None

    def test_negative_ttl(self):
        """
        BOUNDARY: Test cache with negative TTL.

        Common bug: Negative TTL causes unexpected behavior.
        """
        # GovernanceCache accepts negative TTL (entries expire immediately)
        cache = GovernanceCache(max_size=100, ttl_seconds=-1)

        cache.set("agent_1", "action", {"data": "test"})

        # Entry should be expired immediately
        result = cache.get("agent_1", "action")
        assert result is None, "Entry with negative TTL should expire immediately"


class TestGovernanceCacheAgentIDBoundaries:
    """Test agent ID boundary conditions. """

    @pytest.mark.parametrize("agent_id,description", [
        ("", "empty string"),
        ("   ", "whitespace only"),
        ("a", "single character"),
        ("a" * 1000, "very long ID (1000 chars)"),
        ("正常文本", "Chinese characters"),
        ("עברית", "Hebrew (RTL)"),
        ("🚀", "emoji only"),
        ("agent🚀123", "mixed ASCII + emoji"),
        ("agent; DROP TABLE agents; --", "SQL injection attempt"),
        ("<script>alert('xss')</script>", "XSS attempt"),
        ("../../etc/passwd", "path traversal"),
        ("agent\x00name", "null byte"),
    ])
    def test_agent_id_boundaries(self, agent_id, description):
        """
        BOUNDARY: Test various agent ID formats.

        Common bug: Unicode encoding errors or SQL injection vulnerabilities.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Should handle all agent_id formats gracefully
        cache.set(agent_id, "action", {"data": "test"})

        # Retrieve should work
        result = cache.get(agent_id, "action")
        assert result is not None, f"Failed for agent_id: {description}"

        # Stats should include this entry
        stats = cache.get_stats()
        assert stats["size"] > 0

    def test_unicode_agent_id_case_sensitivity(self):
        """
        BOUNDARY: Test case sensitivity with unicode agent IDs.

        Common bug: Unicode case folding causes incorrect cache hits.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # These should be different keys
        cache.set("Agent测试", "action", {"data": 1})
        cache.set("agent测试", "action", {"data": 2})

        result1 = cache.get("Agent测试", "action")
        result2 = cache.get("agent测试", "action")

        # Should be different entries
        assert result1["data"] == 1
        assert result2["data"] == 2


class TestGovernanceCacheActionTypeBoundaries:
    """Test action type boundary conditions. """

    @pytest.mark.parametrize("action_type,description", [
        ("", "empty string"),
        ("a", "single character"),
        ("a" * 500, "very long action type"),
        ("stream_chat", "normal action"),
        ("dir:/tmp", "directory action"),
        ("dir:/../../etc/passwd", "directory traversal attempt"),
        ("action; DROP TABLE cache; --", "SQL injection"),
        ("action<script>alert('xss')</script>", "XSS attempt"),
        ("正常", "Chinese action type"),
        ("🚀", "emoji action type"),
    ])
    def test_action_type_boundaries(self, action_type, description):
        """
        BOUNDARY: Test various action type formats.

        Common bug: Special characters in action types cause cache key collisions.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Should handle all action_type formats
        cache.set("agent_1", action_type, {"data": "test"})

        result = cache.get("agent_1", action_type)
        assert result is not None, f"Failed for action_type: {description}"

    def test_action_type_case_insensitive(self):
        """
        BOUNDARY: Test that action types are lowercased (as per _make_key).

        This verifies the documented behavior that action_type is converted
        to lowercase for cache key generation.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # These should be the same key (action_type is lowercased)
        cache.set("agent_1", "Stream_Chat", {"data": 1})
        result = cache.get("agent_1", "stream_chat")  # Lowercase lookup

        assert result is not None, "action_type should be case-insensitive"
        assert result["data"] == 1


class TestGovernanceCacheStatisticsBoundaries:
    """Test statistics calculation at boundary conditions. """

    def test_all_cache_hits(self):
        """
        BOUNDARY: Test 100% cache hit rate.

        Common bug: Hit rate calculation error at 100%.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Add entry
        cache.set("agent_1", "action", {"data": "test"})

        # Hit cache 100 times
        for _ in range(100):
            cache.get("agent_1", "action")

        stats = cache.get_stats()
        assert stats["hits"] == 100
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 100.0

    def test_all_cache_misses(self):
        """
        BOUNDARY: Test 0% cache hit rate.

        Common bug: Hit rate calculation error at 0%.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Miss cache 100 times
        for i in range(100):
            cache.get(f"agent_{i}", "action")

        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 100
        assert stats["hit_rate"] == 0.0

    def test_directory_hit_rate_boundaries(self):
        """
        BOUNDARY: Test directory-specific hit rate calculation.

        Common bug: Directory hit rate not tracked separately.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Add directory entries
        cache.cache_directory("agent_1", "/tmp", {"allowed": True})
        cache.cache_directory("agent_2", "/home", {"allowed": False})

        # Hit directory cache 10 times
        for _ in range(10):
            cache.check_directory("agent_1", "/tmp")

        # Miss directory cache 5 times
        for _ in range(5):
            cache.check_directory("agent_2", "/nonexistent")

        stats = cache.get_stats()
        assert stats["directory_hits"] == 10
        assert stats["directory_misses"] == 5
        # (10 / 15) * 100 = 66.67%
        assert stats["directory_hit_rate"] == 66.67


class TestGovernanceCacheInvalidationBoundaries:
    """Test cache invalidation at boundaries. """

    @pytest.mark.parametrize("entries_count", [
        0,      # Empty cache
        1,      # Single entry
        10,     # Multiple entries
        100,    # Many entries
    ])
    def test_invalidate_agent_boundaries(self, entries_count):
        """
        BOUNDARY: Test agent invalidation with varying cache sizes.

        Common bug: Invalidation fails when cache is empty or very large.
        """
        cache = GovernanceCache(max_size=1000, ttl_seconds=60)

        # Add entries for agent_1
        for i in range(entries_count):
            cache.set("agent_1", f"action_{i}", {"data": i})

        # Add entries for agent_2 (should not be affected)
        cache.set("agent_2", "action", {"data": "preserved"})

        # Invalidate all agent_1 entries
        cache.invalidate_agent("agent_1")

        # agent_1 entries should be gone
        result = cache.get("agent_1", "action_0")
        assert result is None

        # agent_2 entry should still exist
        result = cache.get("agent_2", "action")
        assert result is not None
        assert result["data"] == "preserved"

    def test_invalidate_nonexistent_agent(self):
        """
        BOUNDARY: Test invalidating agent that doesn't exist.

        Common bug: Crash when invalidating nonexistent agent.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Should not crash
        cache.invalidate_agent("nonexistent_agent")

        # Should not crash for specific action either
        cache.invalidate("nonexistent_agent", "nonexistent_action")

        stats = cache.get_stats()
        assert stats["size"] == 0

    def test_clear_empty_cache(self):
        """
        BOUNDARY: Test clearing an empty cache.

        Common bug: Crash when clearing empty cache.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Clear empty cache - should not crash
        cache.clear()

        stats = cache.get_stats()
        assert stats["size"] == 0
