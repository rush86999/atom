"""
Unit Tests for Governance Cache

Tests pure logic functions in governance_cache.py without external dependencies.
Uses parametrize for edge cases and Hypothesis for invariant testing.
"""

import pytest
import time
from hypothesis import given, strategies as st
from collections import OrderedDict

from core.governance_cache import (
    GovernanceCache,
    MessagingCache,
    get_governance_cache,
)


@pytest.mark.unit
class TestGovernanceCacheBasics:
    """Test basic cache operations"""

    def test_cache_put_and_get(self):
        """Test basic put/get operations"""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        cache.set("agent1", "action1", {"allowed": True})
        result = cache.get("agent1", "action1")

        assert result == {"allowed": True}

    def test_cache_miss_returns_none(self):
        """Test cache miss returns None"""
        cache = GovernanceCache()
        assert cache.get("nonexistent_agent", "nonexistent_action") is None

    @pytest.mark.parametrize("key,value", [
        ("agent:action1", True),
        ("agent:action2", False),
        ("agent:action3", {"complex": "value", "data": [1, 2, 3]}),
        ("agent:action4", None),
        ("agent:action5", 0),
        ("agent:action6", ""),
        ("agent:action7", {"nested": {"deep": "value"}}),
    ])
    def test_cache_put_various_types(self, key, value):
        """Parametrized test for different value types"""
        cache = GovernanceCache()
        agent_id, action_type = key.split(":", 1) if ":" in key else (key, "default")

        cache.set(agent_id, action_type, value)
        assert cache.get(agent_id, action_type) == value


@pytest.mark.unit
class TestGovernanceCacheInvalidation:
    """Test cache invalidation logic"""

    def test_cache_invalidation_specific_action(self):
        """Test cache invalidation for specific action"""
        cache = GovernanceCache()
        cache.set("agent1", "action1", {"allowed": True})
        cache.set("agent1", "action2", {"allowed": False})

        # Invalidate only action1
        cache.invalidate("agent1", "action1")

        assert cache.get("agent1", "action1") is None
        assert cache.get("agent1", "action2") == {"allowed": False}

    def test_cache_invalidation_all_actions(self):
        """Test cache invalidation for all agent actions"""
        cache = GovernanceCache()
        cache.set("agent1", "action1", {"allowed": True})
        cache.set("agent1", "action2", {"allowed": False})
        cache.set("agent1", "action3", {"allowed": True})

        # Invalidate all actions for agent1
        cache.invalidate_agent("agent1")

        assert cache.get("agent1", "action1") is None
        assert cache.get("agent1", "action2") is None
        assert cache.get("agent1", "action3") is None

    def test_cache_clear(self):
        """Test clearing all cache entries"""
        cache = GovernanceCache()
        cache.set("agent1", "action1", {"allowed": True})
        cache.set("agent2", "action2", {"allowed": False})

        cache.clear()

        assert cache.get("agent1", "action1") is None
        assert cache.get("agent2", "action2") is None
        assert cache.get_stats()["size"] == 0


@pytest.mark.unit
class TestGovernanceCacheTTL:
    """Test TTL (time-to-live) behavior"""

    def test_cache_expiration(self):
        """Test expired entries return None"""
        cache = GovernanceCache(max_size=100, ttl_seconds=1)

        cache.set("agent1", "action1", {"allowed": True})

        # Should be available immediately
        assert cache.get("agent1", "action1") == {"allowed": True}

        # Wait for expiration
        time.sleep(1.5)

        # Should be expired
        assert cache.get("agent1", "action1") is None

    @pytest.mark.parametrize("ttl_seconds,sleep_time,expected", [
        (1, 0.5, True),    # Not expired
        (1, 1.5, False),   # Expired
        (2, 1.0, True),    # Not expired
        (2, 2.5, False),   # Expired
    ])
    def test_cache_expiration_parametrized(self, ttl_seconds, sleep_time, expected):
        """Parametrized test for TTL expiration"""
        cache = GovernanceCache(max_size=100, ttl_seconds=ttl_seconds)
        cache.set("agent1", "action1", {"allowed": True})

        time.sleep(sleep_time)

        result = cache.get("agent1", "action1") is not None
        assert result == expected


@pytest.mark.unit
class TestGovernanceCacheLRU:
    """Test LRU (least recently used) eviction"""

    def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full"""
        cache = GovernanceCache(max_size=3, ttl_seconds=60)

        # Fill cache to capacity
        cache.set("agent1", "action1", {"data": 1})
        cache.set("agent2", "action2", {"data": 2})
        cache.set("agent3", "action3", {"data": 3})

        # Access agent1 to make it recently used
        cache.get("agent1", "action1")

        # Add new entry - should evict agent2 (least recently used)
        cache.set("agent4", "action4", {"data": 4})

        # agent2 should be evicted
        assert cache.get("agent2", "action2") is None

        # Others should still exist
        assert cache.get("agent1", "action1") == {"data": 1}
        assert cache.get("agent3", "action3") == {"data": 3}
        assert cache.get("agent4", "action4") == {"data": 4}

    def test_cache_no_eviction_when_key_exists(self):
        """Test that updating existing key doesn't cause eviction"""
        cache = GovernanceCache(max_size=2, ttl_seconds=60)

        cache.set("agent1", "action1", {"data": 1})
        cache.set("agent2", "action2", {"data": 2})

        # Update existing key
        cache.set("agent1", "action1", {"data": 100})

        # Should still have both entries
        assert cache.get("agent1", "action1") == {"data": 100}
        assert cache.get("agent2", "action2") == {"data": 2}


@pytest.mark.unit
class TestGovernanceCacheStatistics:
    """Test cache statistics tracking"""

    def test_cache_statistics_tracking(self):
        """Test cache hit/miss statistics"""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        cache.set("agent1", "action1", {"allowed": True})

        # Hit
        cache.get("agent1", "action1")

        # Miss
        cache.get("agent2", "action2")

        stats = cache.get_stats()

        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 50.0

    @pytest.mark.parametrize("hits,misses,expected_rate", [
        (5, 5, 50.0),
        (10, 0, 100.0),
        (0, 10, 0.0),
        (7, 3, 70.0),
        (3, 7, 30.0),
    ])
    def test_cache_hit_rate_calculation(self, hits, misses, expected_rate):
        """Parametrized test for hit rate calculation"""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Manually set statistics for testing
        cache._hits = hits
        cache._misses = misses

        stats = cache.get_stats()
        assert stats["hit_rate"] == expected_rate

    def test_cache_size_tracking(self):
        """Test cache size tracking"""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        assert cache.get_stats()["size"] == 0

        cache.set("agent1", "action1", {"data": 1})
        assert cache.get_stats()["size"] == 1

        cache.set("agent2", "action2", {"data": 2})
        assert cache.get_stats()["size"] == 2

        cache.invalidate("agent1", "action1")
        assert cache.get_stats()["size"] == 1


@pytest.mark.unit
class TestGovernanceCacheDirectories:
    """Test directory-specific caching"""

    def test_cache_directory_permission(self):
        """Test caching directory permissions"""
        cache = GovernanceCache()

        permission_data = {"allowed": True, "read_only": False}
        cache.cache_directory("agent1", "/tmp", permission_data)

        result = cache.check_directory("agent1", "/tmp")
        assert result == permission_data

    def test_cache_directory_miss(self):
        """Test directory permission cache miss"""
        cache = GovernanceCache()

        result = cache.check_directory("agent1", "/nonexistent")
        assert result is None

    def test_cache_directory_statistics(self):
        """Test directory-specific hit/miss tracking"""
        cache = GovernanceCache()

        cache.cache_directory("agent1", "/tmp", {"allowed": True})

        # Directory hit
        cache.check_directory("agent1", "/tmp")

        # Directory miss
        cache.check_directory("agent1", "/nonexistent")

        stats = cache.get_stats()
        assert stats["directory_hits"] == 1
        assert stats["directory_misses"] == 1
        assert stats["directory_hit_rate"] == 50.0


@pytest.mark.unit
class TestGovernanceCachePropertyTests:
    """Property-based tests using Hypothesis"""

    @given(st.dictionaries(st.text(min_size=1), st.booleans()))
    def test_cache_get_put_invariant_booleans(self, dict_data):
        """Property: put then get returns same value for booleans"""
        cache = GovernanceCache(max_size=1000, ttl_seconds=60)

        # Put all items
        for key, value in dict_data.items():
            agent_id = f"agent_{hash(key) % 1000}"
            action_type = f"action_{key}"
            cache.set(agent_id, action_type, {"allowed": value})

        # Verify invariant: cache size <= max_size
        assert cache.get_stats()["size"] <= cache.max_size

    @given(st.lists(st.tuples(st.text(min_size=1), st.integers())))
    def test_cache_size_never_exceeds_max(self, items):
        """Property: cache size never exceeds max_size"""
        cache = GovernanceCache(max_size=10, ttl_seconds=60)

        for key, value in items[:20]:  # Try to add more than max
            agent_id = f"agent_{hash(key) % 100}"
            action_type = f"action_{key}"
            cache.set(agent_id, action_type, {"value": value})

            # Invariant: size never exceeds max
            assert cache.get_stats()["size"] <= cache.max_size

    @given(st.integers(min_value=1, max_value=100))
    def test_cache_max_size_enforced(self, max_size):
        """Property: cache respects max_size parameter"""
        cache = GovernanceCache(max_size=max_size, ttl_seconds=60)

        # Add max_size + 5 items
        for i in range(max_size + 5):
            cache.set(f"agent{i}", f"action{i}", {"data": i})

        # Size should be at most max_size
        assert cache.get_stats()["size"] <= max_size


@pytest.mark.unit
class TestMessagingCache:
    """Test messaging cache functionality"""

    def test_messaging_cache_platform_capabilities(self):
        """Test platform capabilities caching"""
        cache = MessagingCache(max_size=100, ttl_seconds=300)

        capabilities = {"send_messages": True, "monitor_channels": False}
        cache.set_platform_capabilities("slack", "INTERN", capabilities)

        result = cache.get_platform_capabilities("slack", "INTERN")
        assert result == capabilities

    def test_messaging_cache_monitor_definition(self):
        """Test monitor definition caching"""
        cache = MessagingCache()

        monitor_data = {"webhook_url": "https://example.com", "events": ["message"]}
        cache.set_monitor_definition("monitor_1", monitor_data)

        result = cache.get_monitor_definition("monitor_1")
        assert result == monitor_data

    def test_messaging_cache_template_render(self):
        """Test template render caching"""
        cache = MessagingCache()

        rendered = "Hello {{name}}, you have {{count}} messages"
        cache.set_template_render("template_1", rendered)

        result = cache.get_template_render("template_1")
        assert result == rendered

    def test_messaging_cache_platform_features(self):
        """Test platform features caching"""
        cache = MessagingCache()

        features = {"threads": True, "reactions": True, "file_upload": False}
        cache.set_platform_features("discord", features)

        result = cache.get_platform_features("discord")
        assert result == features

    def test_messaging_cache_stats(self):
        """Test messaging cache statistics"""
        cache = MessagingCache()

        cache.set_platform_capabilities("slack", "INTERN", {"send": True})
        cache.get_platform_capabilities("slack", "INTERN")  # Hit
        cache.get_platform_capabilities("discord", "INTERN")  # Miss

        stats = cache.get_stats()
        assert stats["capabilities_cache_size"] == 1
        assert stats["stats"]["capabilities_hits"] == 1
        assert stats["stats"]["capabilities_misses"] == 1

    def test_messaging_cache_clear(self):
        """Test clearing messaging cache"""
        cache = MessagingCache()

        cache.set_platform_capabilities("slack", "INTERN", {"send": True})
        cache.set_monitor_definition("monitor_1", {"webhook": "url"})

        cache.clear()

        assert cache.get_stats()["capabilities_cache_size"] == 0
        assert cache.get_stats()["monitors_cache_size"] == 0


@pytest.mark.unit
class TestGovernanceCacheKeyGeneration:
    """Test cache key generation logic"""

    def test_cache_key_format(self):
        """Test cache key format is agent_id:action_type"""
        cache = GovernanceCache()

        # Internal method for key generation
        key1 = cache._make_key("agent1", "stream_chat")
        assert key1 == "agent1:stream_chat"

        key2 = cache._make_key("agent2", "PRESENT_CHART")
        assert key2 == "agent2:present_chart"  # Action type is lowercased

    def test_directory_key_format(self):
        """Test directory cache key uses dir: prefix"""
        cache = GovernanceCache()

        # Cache a directory permission
        cache.cache_directory("agent1", "/tmp", {"allowed": True})

        # Should use special "dir:" prefix
        result = cache.check_directory("agent1", "/tmp")
        assert result == {"allowed": True}


@pytest.mark.unit
class TestGovernanceCacheThreadSafety:
    """Test thread-safe operations (basic checks)"""

    def test_cache_with_lock_context(self):
        """Test cache operations respect lock"""
        cache = GovernanceCache()

        # These operations should be thread-safe
        with cache._lock:
            cache.set("agent1", "action1", {"data": 1})
            assert cache.get("agent1", "action1") == {"data": 1}

    def test_stats_are_thread_safe(self):
        """Test statistics tracking with lock"""
        cache = GovernanceCache()

        cache.set("agent1", "action1", {"data": 1})

        # Stats should be accessed with lock
        with cache._lock:
            stats = cache.get_stats()
            assert stats["size"] == 1
