"""
Test suite for Governance Cache

Tests governance cache including:
- Cache initialization and configuration
- Cache get/set operations
- Cache invalidation and clearing
- Directory permission caching
- AsyncGovernanceCache wrapper
- MessagingCache extensions
- Cache statistics and metrics
- Thread safety and LRU eviction
"""

import pytest
import time
import threading
from collections import OrderedDict
from unittest.mock import AsyncMock, Mock, patch

from core.governance_cache import (
    GovernanceCache,
    AsyncGovernanceCache,
    MessagingCache,
    get_governance_cache,
    get_async_governance_cache,
    get_messaging_cache,
    cached_governance_check
)


class TestGovernanceCacheInit:
    """Test GovernanceCache initialization and configuration"""

    def test_cache_initialization_default_params(self):
        """GovernanceCache initializes with default parameters."""
        cache = GovernanceCache()
        assert cache.max_size == 1000
        assert cache.ttl_seconds == 60
        assert len(cache._cache) == 0
        assert cache._hits == 0
        assert cache._misses == 0

    def test_cache_initialization_custom_params(self):
        """GovernanceCache initializes with custom parameters."""
        cache = GovernanceCache(max_size=500, ttl_seconds=300)
        assert cache.max_size == 500
        assert cache.ttl_seconds == 300

    def test_cache_initialization_stats(self):
        """GovernanceCache initializes statistics counters."""
        cache = GovernanceCache()
        stats = cache.get_stats()
        assert stats["size"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["evictions"] == 0
        assert stats["invalidations"] == 0


class TestCacheOperations:
    """Test cache get/set/delete operations"""

    @pytest.fixture
    def cache(self):
        """Create governance cache instance."""
        return GovernanceCache(max_size=100, ttl_seconds=60)

    def test_cache_set_and_get_success(self, cache):
        """Cache set and get operations work correctly."""
        data = {"allowed": True, "reason": "Agent has permission"}
        success = cache.set("agent-001", "stream_chat", data)
        assert success is True

        retrieved = cache.get("agent-001", "stream_chat")
        assert retrieved is not None
        assert retrieved["allowed"] is True
        assert retrieved["reason"] == "Agent has permission"

    def test_cache_get_miss(self, cache):
        """Cache get returns None for non-existent key."""
        result = cache.get("agent-999", "nonexistent_action")
        assert result is None

    def test_cache_set_updates_existing(self, cache):
        """Cache set updates existing entry."""
        cache.set("agent-001", "stream_chat", {"allowed": False})
        cache.set("agent-001", "stream_chat", {"allowed": True})

        result = cache.get("agent-001", "stream_chat")
        assert result["allowed"] is True

    def test_cache_key_format(self, cache):
        """Cache key combines agent_id and action_type correctly."""
        cache.set("agent-001", "Stream_Chat", {"test": True})
        result = cache.get("agent-001", "Stream_Chat")
        assert result is not None

        # Case insensitive for action_type
        result_lower = cache.get("agent-001", "stream_chat")
        # Should be same key (action_type.lower() in _make_key)
        assert result_lower is not None

    def test_cache_multiple_entries(self, cache):
        """Cache handles multiple entries for same agent."""
        cache.set("agent-001", "action1", {"data": 1})
        cache.set("agent-001", "action2", {"data": 2})
        cache.set("agent-001", "action3", {"data": 3})

        assert cache.get("agent-001", "action1")["data"] == 1
        assert cache.get("agent-001", "action2")["data"] == 2
        assert cache.get("agent-001", "action3")["data"] == 3

    def test_cache_data_isolation(self, cache):
        """Cache isolates data between different agents."""
        cache.set("agent-001", "action", {"agent": "agent-001"})
        cache.set("agent-002", "action", {"agent": "agent-002"})

        result1 = cache.get("agent-001", "action")
        result2 = cache.get("agent-002", "action")

        assert result1["agent"] == "agent-001"
        assert result2["agent"] == "agent-002"


class TestCacheExpiration:
    """Test cache TTL and expiration logic"""

    @pytest.fixture
    def cache(self):
        """Create cache with short TTL for testing."""
        return GovernanceCache(max_size=100, ttl_seconds=1)

    def test_cache_expiration_after_ttl(self, cache):
        """Cache entry expires after TTL."""
        cache.set("agent-001", "action", {"data": "test"})

        # Should be accessible immediately
        result = cache.get("agent-001", "action")
        assert result is not None

        # Wait for expiration
        time.sleep(1.5)

        # Should be expired
        result = cache.get("agent-001", "action")
        assert result is None

    def test_cache_expiration_increments_misses(self, cache):
        """Cache expiration increments miss counter."""
        cache.set("agent-001", "action", {"data": "test"})
        time.sleep(1.5)

        initial_misses = cache._misses
        cache.get("agent-001", "action")
        assert cache._misses == initial_misses + 1


class TestCacheInvalidation:
    """Test cache invalidation operations"""

    @pytest.fixture
    def cache(self):
        """Create cache instance."""
        return GovernanceCache(max_size=100, ttl_seconds=60)

    def test_invalidate_specific_action(self, cache):
        """Cache invalidation removes specific action for agent."""
        cache.set("agent-001", "action1", {"data": 1})
        cache.set("agent-001", "action2", {"data": 2})

        cache.invalidate("agent-001", "action1")

        assert cache.get("agent-001", "action1") is None
        assert cache.get("agent-001", "action2") is not None

    def test_invalidate_all_agent_actions(self, cache):
        """Cache invalidation removes all actions for agent."""
        cache.set("agent-001", "action1", {"data": 1})
        cache.set("agent-001", "action2", {"data": 2})
        cache.set("agent-001", "action3", {"data": 3})

        cache.invalidate("agent-001")

        assert cache.get("agent-001", "action1") is None
        assert cache.get("agent-001", "action2") is None
        assert cache.get("agent-001", "action3") is None

    def test_invalidate_agent_convenience_method(self, cache):
        """invalidate_agent convenience method works correctly."""
        cache.set("agent-001", "action", {"data": "test"})

        cache.invalidate_agent("agent-001")

        assert cache.get("agent-001", "action") is None

    def test_invalidate_increments_counter(self, cache):
        """Cache invalidation increments invalidation counter."""
        cache.set("agent-001", "action", {"data": "test"})

        initial_invalidations = cache._invalidations
        cache.invalidate("agent-001")
        assert cache._invalidations == initial_invalidations + 1

    def test_clear_all_cache_entries(self, cache):
        """Cache clear removes all entries."""
        cache.set("agent-001", "action1", {"data": 1})
        cache.set("agent-002", "action2", {"data": 2})
        cache.set("agent-003", "action3", {"data": 3})

        cache.clear()

        assert len(cache._cache) == 0
        assert cache.get("agent-001", "action1") is None
        assert cache.get("agent-002", "action2") is None


class TestCacheStatistics:
    """Test cache statistics and metrics"""

    @pytest.fixture
    def cache(self):
        """Create cache instance."""
        return GovernanceCache(max_size=100, ttl_seconds=60)

    def test_cache_hit_rate_calculation(self, cache):
        """Cache hit rate calculated correctly."""
        cache.set("agent-001", "action", {"data": "test"})

        # Hit
        cache.get("agent-001", "action")
        # Miss
        cache.get("agent-999", "nonexistent")

        stats = cache.get_stats()
        expected_hit_rate = (1 / 2) * 100  # 1 hit out of 2 requests
        assert stats["hit_rate"] == expected_hit_rate

    def test_cache_stats_all_fields(self, cache):
        """Cache stats include all required fields."""
        cache.set("agent-001", "action", {"data": "test"})

        stats = cache.get_stats()
        assert "size" in stats
        assert "max_size" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats
        assert "evictions" in stats
        assert "invalidations" in stats
        assert "ttl_seconds" in stats

    def test_get_hit_rate_convenience_method(self, cache):
        """get_hit_rate returns current hit rate percentage."""
        cache.set("agent-001", "action", {"data": "test"})

        cache.get("agent-001", "action")  # Hit
        cache.get("agent-999", "action")  # Miss

        hit_rate = cache.get_hit_rate()
        assert hit_rate == 50.0


class TestDirectoryCaching:
    """Test directory permission caching"""

    @pytest.fixture
    def cache(self):
        """Create cache instance."""
        return GovernanceCache(max_size=100, ttl_seconds=60)

    def test_cache_directory_permission(self, cache):
        """Directory permission cached with special key format."""
        permission_data = {"allowed": True, "directory": "/tmp"}
        success = cache.cache_directory("agent-001", "/tmp", permission_data)
        assert success is True

        result = cache.check_directory("agent-001", "/tmp")
        assert result is not None
        assert result["allowed"] is True

    def test_check_directory_miss(self, cache):
        """check_directory returns None for non-existent directory."""
        result = cache.check_directory("agent-001", "/nonexistent")
        assert result is None

    def test_directory_and_action_separate_keys(self, cache):
        """Directory and action permissions use separate cache keys."""
        cache.set("agent-001", "action", {"type": "action"})
        cache.cache_directory("agent-001", "/tmp", {"type": "directory"})

        action_result = cache.get("agent-001", "action")
        dir_result = cache.check_directory("agent-001", "/tmp")

        assert action_result["type"] == "action"
        assert dir_result["type"] == "directory"


class TestLRUEviction:
    """Test LRU eviction when cache is full"""

    @pytest.fixture
    def small_cache(self):
        """Create small cache for LRU testing."""
        return GovernanceCache(max_size=3, ttl_seconds=60)

    def test_lru_eviction_when_full(self, small_cache):
        """Cache evicts least recently used entry when full."""
        # Fill cache to capacity
        small_cache.set("agent-001", "action", {"data": 1})
        small_cache.set("agent-002", "action", {"data": 2})
        small_cache.set("agent-003", "action", {"data": 3})

        # Access agent-001 to make it recently used
        small_cache.get("agent-001", "action")

        # Add new entry (should evict agent-002 as least recently used)
        small_cache.set("agent-004", "action", {"data": 4})

        assert small_cache.get("agent-001", "action") is not None  # Recently accessed
        assert small_cache.get("agent-002", "action") is None  # Evicted
        assert small_cache.get("agent-003", "action") is not None
        assert small_cache.get("agent-004", "action") is not None  # New entry

    def test_lru_eviction_increments_counter(self, small_cache):
        """LRU eviction increments eviction counter."""
        small_cache.set("agent-001", "action", {"data": 1})
        small_cache.set("agent-002", "action", {"data": 2})
        small_cache.set("agent-003", "action", {"data": 3})

        initial_evictions = small_cache._evictions
        small_cache.set("agent-004", "action", {"data": 4})
        assert small_cache._evictions == initial_evictions + 1


class TestAsyncGovernanceCache:
    """Test AsyncGovernanceCache wrapper"""

    @pytest.fixture
    def async_cache(self):
        """Create async cache instance."""
        return AsyncGovernanceCache()

    @pytest.mark.asyncio
    async def test_async_cache_get(self, async_cache):
        """Async cache get delegates to sync cache."""
        async_cache._cache.set("agent-001", "action", {"test": True})

        result = await async_cache.get("agent-001", "action")
        assert result is not None
        assert result["test"] is True

    @pytest.mark.asyncio
    async def test_async_cache_set(self, async_cache):
        """Async cache set delegates to sync cache."""
        success = await async_cache.set("agent-001", "action", {"data": "test"})
        assert success is True

        result = await async_cache.get("agent-001", "action")
        assert result is not None

    @pytest.mark.asyncio
    async def test_async_cache_invalidate(self, async_cache):
        """Async cache invalidate delegates to sync cache."""
        await async_cache.set("agent-001", "action", {"data": "test"})
        await async_cache.invalidate("agent-001")

        result = await async_cache.get("agent-001", "action")
        assert result is None

    @pytest.mark.asyncio
    async def test_async_cache_get_stats(self, async_cache):
        """Async cache get_stats delegates to sync cache."""
        stats = await async_cache.get_stats()
        assert "size" in stats
        assert "hits" in stats
        assert "misses" in stats


class TestMessagingCache:
    """Test MessagingCache specialized cache"""

    @pytest.fixture
    def messaging_cache(self):
        """Create messaging cache instance."""
        return MessagingCache(max_size=100, ttl_seconds=300)

    def test_messaging_cache_initialization(self, messaging_cache):
        """MessagingCache initializes with separate caches."""
        assert messaging_cache._capabilities is not None
        assert messaging_cache._monitors is not None
        assert messaging_cache._templates is not None
        assert messaging_cache._features is not None

    def test_cache_platform_capabilities(self, messaging_cache):
        """Platform capabilities cached and retrieved."""
        capabilities = {"can_send": True, "can_monitor": False}
        messaging_cache.set_platform_capabilities("slack", "INTERN", capabilities)

        result = messaging_cache.get_platform_capabilities("slack", "INTERN")
        assert result is not None
        assert result["can_send"] is True

    def test_cache_monitor_definition(self, messaging_cache):
        """Monitor definition cached and retrieved."""
        monitor = {"metric": "error_rate", "threshold": 10.0}
        messaging_cache.set_monitor_definition("monitor-001", monitor)

        result = messaging_cache.get_monitor_definition("monitor-001")
        assert result is not None
        assert result["metric"] == "error_rate"

    def test_cache_template_render(self, messaging_cache):
        """Template render cached and retrieved."""
        rendered = "Hello {{name}}, welcome to Slack!"
        messaging_cache.set_template_render("template-001", rendered)

        result = messaging_cache.get_template_render("template-001")
        assert result == rendered

    def test_cache_platform_features(self, messaging_cache):
        """Platform features cached and retrieved."""
        features = {"threads": True, "reactions": True}
        messaging_cache.set_platform_features("slack", features)

        result = messaging_cache.get_platform_features("slack")
        assert result is not None
        assert result["threads"] is True

    def test_messaging_cache_stats(self, messaging_cache):
        """Messaging cache stats include all cache types."""
        messaging_cache.set_platform_capabilities("slack", "INTERN", {})
        messaging_cache.set_monitor_definition("monitor-001", {})

        stats = messaging_cache.get_stats()
        assert "capabilities_cache_size" in stats
        assert "monitors_cache_size" in stats
        assert "templates_cache_size" in stats
        assert "features_cache_size" in stats
        assert "total_hit_rate" in stats

    def test_invalidate_monitor(self, messaging_cache):
        """Monitor invalidation removes specific monitor."""
        messaging_cache.set_monitor_definition("monitor-001", {"data": 1})
        messaging_cache.invalidate_monitor("monitor-001")

        result = messaging_cache.get_monitor_definition("monitor-001")
        assert result is None


class TestGlobalCacheInstances:
    """Test global cache singleton instances"""

    def test_get_governance_cache_singleton(self):
        """get_governance_cache returns singleton instance."""
        cache1 = get_governance_cache()
        cache2 = get_governance_cache()
        assert cache1 is cache2

    def test_get_async_governance_cache_singleton(self):
        """get_async_governance_cache returns singleton instance."""
        cache1 = get_async_governance_cache()
        cache2 = get_async_governance_cache()
        assert cache1 is cache2

    def test_get_messaging_cache_singleton(self):
        """get_messaging_cache returns singleton instance."""
        cache1 = get_messaging_cache()
        cache2 = get_messaging_cache()
        assert cache1 is cache2


class TestCachedGovernanceCheckDecorator:
    """Test cached_governance_check decorator"""

    @pytest.mark.asyncio
    async def test_decorator_caches_results(self):
        """Decorator caches function results."""
        call_count = 0

        @cached_governance_check
        async def mock_check(agent_id: str, action_type: str):
            nonlocal call_count
            call_count += 1
            return {"allowed": True, "agent_id": agent_id}

        # First call - executes function
        result1 = await mock_check("agent-001", "action")
        assert call_count == 1
        assert result1["allowed"] is True

        # Second call - uses cache
        result2 = await mock_check("agent-001", "action")
        assert call_count == 1  # Not incremented
        assert result2["allowed"] is True

    @pytest.mark.asyncio
    async def test_decorator_different_params(self):
        """Decorator treats different parameters as separate cache entries."""
        call_count = 0

        @cached_governance_check
        async def mock_check(agent_id: str, action_type: str):
            nonlocal call_count
            call_count += 1
            return {"agent_id": agent_id}

        await mock_check("agent-001", "action1")
        await mock_check("agent-001", "action2")
        await mock_check("agent-002", "action1")

        assert call_count == 3  # Each unique combo


class TestThreadSafety:
    """Test cache thread safety"""

    def test_concurrent_cache_operations(self):
        """Cache handles concurrent operations safely."""
        cache = GovernanceCache(max_size=1000, ttl_seconds=60)
        errors = []

        def worker(worker_id):
            try:
                for i in range(100):
                    cache.set(f"agent-{worker_id}", f"action-{i}", {"data": i})
                    cache.get(f"agent-{worker_id}", f"action-{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"
