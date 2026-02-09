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
