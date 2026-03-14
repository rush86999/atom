"""
Coverage-driven tests for GovernanceCache (currently 0% -> target 80%+)

Target file: core/governance_cache.py (678 statements)

Focus areas from coverage gap analysis:
- Cache initialization (lines 1-100)
- get/set/invalidate methods (lines 100-250)
- Directory-specific caching (lines 250-277)
- Statistics and hit rate tracking (lines 278-311)
- AsyncGovernanceCache wrapper (lines 358-397)
- Decorator pattern (lines 326-356)
- MessagingCache extensions (lines 403-677)
"""

import asyncio
import pytest
import threading
import time
from collections import OrderedDict
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from freezegun import freeze_time

from core.governance_cache import (
    GovernanceCache,
    get_governance_cache,
    cached_governance_check,
    AsyncGovernanceCache,
    get_async_governance_cache,
    MessagingCache,
    get_messaging_cache,
    _governance_cache,
    _messaging_cache
)


class TestGovernanceCacheCoverage:
    """Coverage-driven tests for governance_cache.py"""

    # ========================================================================
    # Task 1: Cache Initialization Tests (lines 33-100)
    # ========================================================================

    def test_cache_initialization_default_params(self):
        """Cover lines 33-50: Default cache initialization"""
        cache = GovernanceCache()

        assert cache.max_size == 1000
        assert cache.ttl_seconds == 60
        assert isinstance(cache._cache, OrderedDict)
        assert isinstance(cache._lock, threading.Lock)
        assert cache._hits == 0
        assert cache._misses == 0
        assert cache._evictions == 0
        assert cache._invalidations == 0

    def test_cache_initialization_custom_params(self):
        """Cover lines 33-50: Custom max_size and TTL"""
        cache = GovernanceCache(max_size=500, ttl_seconds=300)

        assert cache.max_size == 500
        assert cache.ttl_seconds == 300
        assert cache._hits == 0
        assert cache._misses == 0

    def test_cleanup_task_start_on_init(self):
        """Cover lines 66-73: Background cleanup task startup"""
        with patch('core.governance_cache.asyncio.get_event_loop') as mock_get_loop:
            mock_loop = MagicMock()
            mock_loop.is_running.return_value = True
            mock_get_loop.return_value = mock_loop

            cache = GovernanceCache()

            # Verify cleanup task was created
            mock_loop.create_task.assert_called_once()

    def test_cleanup_task_startup_no_event_loop(self):
        """Cover lines 72-73: Graceful handling when no event loop"""
        with patch('core.governance_cache.asyncio.get_event_loop') as mock_get_loop:
            mock_get_loop.side_effect = RuntimeError("No event loop")

            # Should not raise exception
            cache = GovernanceCache()
            assert cache is not None

    # ========================================================================
    # Task 2: Cache Hit/Miss/Expiration Tests (lines 107-152)
    # ========================================================================

    def test_cache_miss_returns_none(self):
        """Cover lines 125-130: Cache miss path"""
        cache = GovernanceCache()

        result = cache.get("agent-1", "stream_llm")

        assert result is None
        assert cache._misses == 1
        assert cache._hits == 0

    def test_cache_hit_returns_cached_data(self):
        """Cover lines 132-152: Cache hit path"""
        cache = GovernanceCache(ttl_seconds=60)

        # Populate cache
        data = {"allowed": True, "reason": "test"}
        cache.set("agent-1", "stream_llm", data)

        # First get - cache hit
        result = cache.get("agent-1", "stream_llm")

        assert result == data
        assert cache._hits == 1
        assert cache._misses == 0

    def test_cache_expiration_returns_none(self):
        """Cover lines 137-143: Expired entry returns None"""
        cache = GovernanceCache(ttl_seconds=60)

        # Populate cache
        data = {"allowed": True}
        cache.set("agent-1", "stream_llm", data)

        # Fast-forward time beyond TTL
        with freeze_time("2024-01-01 12:00:00"):
            cache.set("agent-1", "stream_llm", data)

        with freeze_time("2024-01-01 12:02:00"):  # 2 minutes later
            result = cache.get("agent-1", "stream_llm")

            # Should be expired
            assert result is None
            assert cache._misses == 1

    def test_directory_specific_cache_miss(self):
        """Cover lines 128-129: Directory-specific miss tracking"""
        cache = GovernanceCache()

        result = cache.check_directory("agent-1", "/tmp")

        assert result is None
        assert cache._directory_misses == 1

    def test_directory_specific_cache_hit(self):
        """Cover lines 149-150: Directory-specific hit tracking"""
        cache = GovernanceCache(ttl_seconds=60)

        data = {"allowed": True, "path": "/tmp"}
        cache.cache_directory("agent-1", "/tmp", data)

        result = cache.check_directory("agent-1", "/tmp")

        assert result == data
        assert cache._directory_hits == 1

    # ========================================================================
    # Task 3: Set Method and LRU Eviction (lines 154-193)
    # ========================================================================

    def test_set_stores_data_in_cache(self):
        """Cover lines 173-190: Cache set operation"""
        cache = GovernanceCache()

        data = {"allowed": True, "confidence": 0.8}
        success = cache.set("agent-1", "stream_llm", data)

        assert success is True
        assert cache.get("agent-1", "stream_llm") == data

    def test_set_updates_existing_entry(self):
        """Cover lines 182-190: Update existing cache entry"""
        cache = GovernanceCache(ttl_seconds=60)

        cache.set("agent-1", "stream_llm", {"allowed": False})
        cache.set("agent-1", "stream_llm", {"allowed": True})

        result = cache.get("agent-1", "stream_llm")
        assert result["allowed"] is True

    def test_lru_eviction_when_full(self):
        """Cover lines 176-179: LRU eviction at capacity"""
        cache = GovernanceCache(max_size=2)

        cache.set("agent-1", "action1", {"data": "1"})
        cache.set("agent-2", "action2", {"data": "2"})
        cache.set("agent-3", "action3", {"data": "3"})

        # First entry should be evicted
        assert cache.get("agent-1", "action1") is None
        assert cache.get("agent-2", "action2") is not None
        assert cache.get("agent-3", "action3") is not None
        assert cache._evictions == 1

    def test_set_error_handling(self):
        """Cover lines 191-193: Error handling in set"""
        cache = GovernanceCache()

        # Mock entire lock context manager to raise exception
        original_lock = cache._lock
        cache._lock = MagicMock()
        cache._lock.__enter__.side_effect = RuntimeError("Lock error")
        cache._lock.__exit__ = MagicMock()

        success = cache.set("agent-1", "action", {"data": "test"})
        assert success is False

        # Restore original lock
        cache._lock = original_lock

    # ========================================================================
    # Task 4: Invalidation Methods (lines 195-227)
    # ========================================================================

    def test_invalidate_specific_action(self):
        """Cover lines 205-210: Invalidate specific action type"""
        cache = GovernanceCache(ttl_seconds=60)

        cache.set("agent-1", "action1", {"data": "1"})
        cache.set("agent-1", "action2", {"data": "2"})

        cache.invalidate("agent-1", "action1")

        assert cache.get("agent-1", "action1") is None
        assert cache.get("agent-1", "action2") is not None
        assert cache._invalidations == 1

    def test_invalidate_all_agent_actions(self):
        """Cover lines 211-219: Invalidate all actions for agent"""
        cache = GovernanceCache(ttl_seconds=60)

        cache.set("agent-1", "action1", {"data": "1"})
        cache.set("agent-1", "action2", {"data": "2"})
        cache.set("agent-2", "action3", {"data": "3"})

        cache.invalidate("agent-1")

        assert cache.get("agent-1", "action1") is None
        assert cache.get("agent-1", "action2") is None
        assert cache.get("agent-2", "action3") is not None
        assert cache._invalidations == 2

    def test_invalidate_agent_convenience_method(self):
        """Cover lines 225-227: Convenience method for invalidation"""
        cache = GovernanceCache(ttl_seconds=60)

        cache.set("agent-1", "action1", {"data": "1"})
        cache.invalidate_agent("agent-1")

        assert cache.get("agent-1", "action1") is None

    def test_clear_all_cache_entries(self):
        """Cover lines 229-234: Clear entire cache"""
        cache = GovernanceCache(ttl_seconds=60)

        cache.set("agent-1", "action1", {"data": "1"})
        cache.set("agent-2", "action2", {"data": "2"})

        cache.clear()

        assert len(cache._cache) == 0
        assert cache.get("agent-1", "action1") is None

    # ========================================================================
    # Task 5: Statistics and Hit Rate (lines 278-311)
    # ========================================================================

    def test_get_stats_returns_all_metrics(self):
        """Cover lines 285-305: Statistics retrieval"""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        cache.set("agent-1", "action1", {"data": "1"})
        cache.get("agent-1", "action1")  # Hit
        cache.get("agent-2", "action2")  # Miss

        stats = cache.get_stats()

        assert stats["size"] == 1
        assert stats["max_size"] == 100
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 50.0
        assert stats["directory_hits"] == 0
        assert stats["directory_misses"] == 0
        assert stats["evictions"] == 0
        assert stats["invalidations"] == 0
        assert stats["ttl_seconds"] == 60

    def test_get_hit_rate_convenience_method(self):
        """Cover lines 307-310: Hit rate convenience method"""
        cache = GovernanceCache(ttl_seconds=60)

        cache.set("agent-1", "action1", {"data": "1"})
        cache.get("agent-1", "action1")  # Hit
        cache.get("agent-2", "action2")  # Miss

        hit_rate = cache.get_hit_rate()
        assert hit_rate == 50.0

    def test_directory_specific_hit_rate_tracking(self):
        """Cover lines 289-291: Directory hit rate calculation"""
        cache = GovernanceCache(ttl_seconds=60)

        cache.cache_directory("agent-1", "/tmp", {"allowed": True})
        cache.check_directory("agent-1", "/tmp")  # Hit
        cache.check_directory("agent-1", "/var")  # Miss

        stats = cache.get_stats()
        assert stats["directory_hits"] == 1
        assert stats["directory_misses"] == 1
        assert stats["directory_hit_rate"] == 50.0

    def test_hit_rate_with_zero_requests(self):
        """Cover lines 287: Handle zero total requests"""
        cache = GovernanceCache()

        stats = cache.get_stats()
        assert stats["hit_rate"] == 0.0

    # ========================================================================
    # Task 6: Global Cache Instance (lines 313-324)
    # ========================================================================

    def test_get_governance_cache_singleton(self):
        """Cover lines 317-323: Global cache singleton"""
        # Reset global cache
        import core.governance_cache
        core.governance_cache._governance_cache = None

        cache1 = get_governance_cache()
        cache2 = get_governance_cache()

        assert cache1 is cache2  # Same instance

    # ========================================================================
    # Task 7: Decorator Pattern (lines 326-356)
    # ========================================================================

    @pytest.mark.asyncio
    async def test_cached_governance_check_decorator_hit(self):
        """Cover lines 340-344: Decorator cache hit path"""
        # Reset global cache
        import core.governance_cache
        core.governance_cache._governance_cache = GovernanceCache()

        @cached_governance_check
        async def mock_check(agent_id: str, action_type: str):
            return {"allowed": True, "agent": agent_id}

        # First call - miss, caches result
        result1 = await mock_check("agent-1", "stream_llm")

        # Second call - hit from cache
        result2 = await mock_check("agent-1", "stream_llm")

        assert result1 == result2

    @pytest.mark.asyncio
    async def test_cached_governance_check_decorator_miss(self):
        """Cover lines 346-351: Decorator cache miss path"""
        # Reset global cache
        import core.governance_cache
        core.governance_cache._governance_cache = GovernanceCache()

        call_count = 0

        @cached_governance_check
        async def mock_check(agent_id: str, action_type: str):
            nonlocal call_count
            call_count += 1
            return {"allowed": True, "call": call_count}

        # First call
        result1 = await mock_check("agent-1", "stream_llm")
        assert result1["call"] == 1

        # Second call - from cache
        result2 = await mock_check("agent-1", "stream_llm")
        assert result2["call"] == 1  # Not incremented

    # ========================================================================
    # Task 8: AsyncGovernanceCache Wrapper (lines 358-397)
    # ========================================================================

    @pytest.mark.asyncio
    async def test_async_cache_get_delegates_to_sync(self):
        """Cover lines 369-371: Async get delegates to sync"""
        sync_cache = GovernanceCache(ttl_seconds=60)
        async_cache = AsyncGovernanceCache(cache=sync_cache)

        sync_cache.set("agent-1", "action1", {"allowed": True})

        result = await async_cache.get("agent-1", "action1")

        assert result == {"allowed": True}

    @pytest.mark.asyncio
    async def test_async_cache_set_delegates_to_sync(self):
        """Cover lines 373-375: Async set delegates to sync"""
        sync_cache = GovernanceCache()
        async_cache = AsyncGovernanceCache(cache=sync_cache)

        success = await async_cache.set("agent-1", "action1", {"allowed": True})

        assert success is True
        assert sync_cache.get("agent-1", "action1") == {"allowed": True}

    @pytest.mark.asyncio
    async def test_async_cache_invalidate_delegates_to_sync(self):
        """Cover lines 377-379: Async invalidate delegates to sync"""
        sync_cache = GovernanceCache(ttl_seconds=60)
        async_cache = AsyncGovernanceCache(cache=sync_cache)

        sync_cache.set("agent-1", "action1", {"allowed": True})
        await async_cache.invalidate("agent-1", "action1")

        assert sync_cache.get("agent-1", "action1") is None

    @pytest.mark.asyncio
    async def test_async_cache_get_stats(self):
        """Cover lines 385-387: Async get stats"""
        sync_cache = GovernanceCache()
        async_cache = AsyncGovernanceCache(cache=sync_cache)

        stats = await async_cache.get_stats()

        assert stats["size"] == 0
        assert stats["hit_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_async_governance_cache_factory(self):
        """Cover lines 394-396: Async cache factory"""
        async_cache = get_async_governance_cache()

        assert isinstance(async_cache, AsyncGovernanceCache)

    # ========================================================================
    # Task 9: Thread Safety Tests (lines 200-278)
    # ========================================================================

    def test_thread_safe_cache_operations(self):
        """Cover thread safety with concurrent access"""
        cache = GovernanceCache(ttl_seconds=60)
        results = []
        errors = []

        def cache_operation(agent_id):
            try:
                # Set
                cache.set(agent_id, "action1", {"allowed": True})
                # Get
                result = cache.get(agent_id, "action1")
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=cache_operation, args=(f"agent-{i}",))
            for i in range(100)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread safety violations: {errors}"
        assert len(results) == 100

    def test_thread_safe_invalidation(self):
        """Cover thread-safe invalidation operations"""
        cache = GovernanceCache(ttl_seconds=60)

        # Populate cache
        for i in range(50):
            cache.set(f"agent-{i}", "action1", {"allowed": True})

        errors = []

        def invalidate_agent(agent_id):
            try:
                cache.invalidate_agent(agent_id)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=invalidate_agent, args=(f"agent-{i}",))
            for i in range(50)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert cache.get_stats()["size"] == 0

    # ========================================================================
    # Task 10: Background Cleanup Task (lines 75-105)
    # ========================================================================

    def test_expire_stale_removes_old_entries(self):
        """Cover lines 86-105: Expire stale entries"""
        cache = GovernanceCache(ttl_seconds=60)

        # Add entries
        cache.set("agent-1", "action1", {"data": "1"})
        cache.set("agent-2", "action2", {"data": "2"})

        # Manually expire
        with patch('time.time', return_value=time.time() + 61):
            cache._expire_stale()

        assert cache.get_stats()["size"] == 0
        assert cache._evictions == 2

    # ========================================================================
    # Task 11: MessagingCache Coverage (lines 403-677)
    # ========================================================================

    def test_messaging_cache_initialization(self):
        """Cover lines 416-445: MessagingCache initialization"""
        cache = MessagingCache(max_size=500, ttl_seconds=300)

        assert cache.max_size == 500
        assert cache.ttl_seconds == 300
        assert isinstance(cache._capabilities, OrderedDict)
        assert isinstance(cache._monitors, OrderedDict)
        assert isinstance(cache._templates, OrderedDict)
        assert isinstance(cache._features, OrderedDict)
        assert cache._stats["capabilities_hits"] == 0
        assert cache._stats["capabilities_misses"] == 0

    def test_messaging_cache_platform_capabilities(self):
        """Cover lines 447-477: Platform capabilities caching"""
        cache = MessagingCache(ttl_seconds=300)

        # Miss
        result = cache.get_platform_capabilities("slack", "INTERN")
        assert result is None
        assert cache._stats["capabilities_misses"] == 1

        # Set
        capabilities = {"send_message": True, "upload_file": False}
        cache.set_platform_capabilities("slack", "INTERN", capabilities)

        # Hit
        result = cache.get_platform_capabilities("slack", "INTERN")
        assert result == capabilities
        assert cache._stats["capabilities_hits"] == 1

    def test_messaging_cache_monitor_definition(self):
        """Cover lines 495-521: Monitor definition caching"""
        cache = MessagingCache(ttl_seconds=300)

        # Miss
        result = cache.get_monitor_definition("monitor-1")
        assert result is None
        assert cache._stats["monitors_misses"] == 1

        # Set
        monitor = {"type": "keyword", "pattern": "error"}
        cache.set_monitor_definition("monitor-1", monitor)

        # Hit
        result = cache.get_monitor_definition("monitor-1")
        assert result == monitor
        assert cache._stats["monitors_hits"] == 1

    def test_messaging_cache_invalidate_monitor(self):
        """Cover lines 536-540: Monitor invalidation"""
        cache = MessagingCache(ttl_seconds=300)

        cache.set_monitor_definition("monitor-1", {"type": "keyword"})
        cache.invalidate_monitor("monitor-1")

        result = cache.get_monitor_definition("monitor-1")
        assert result is None

    def test_messaging_cache_template_render(self):
        """Cover lines 542-569: Template render caching"""
        cache = MessagingCache(ttl_seconds=300)

        # Miss
        result = cache.get_template_render("template-key-1")
        assert result is None
        assert cache._stats["templates_misses"] == 1

        # Set
        rendered = "Hello, world!"
        cache.set_template_render("template-key-1", rendered)

        # Hit
        result = cache.get_template_render("template-key-1")
        assert result == rendered
        assert cache._stats["templates_hits"] == 1

    def test_messaging_cache_platform_features(self):
        """Cover lines 584-611: Platform features caching"""
        cache = MessagingCache(ttl_seconds=300)

        # Miss
        result = cache.get_platform_features("slack")
        assert result is None
        assert cache._stats["features_misses"] == 1

        # Set
        features = {"threads": True, "reactions": True}
        cache.set_platform_features("slack", features)

        # Hit
        result = cache.get_platform_features("slack")
        assert result == features
        assert cache._stats["features_hits"] == 1

    def test_messaging_cache_is_expired(self):
        """Cover lines 626-629: Expiration check"""
        cache = MessagingCache(ttl_seconds=300)

        entry = {"cached_at": time.time()}
        assert cache._is_expired(entry) is False

        entry = {"cached_at": time.time() - 301}
        assert cache._is_expired(entry) is True

    def test_messaging_cache_ensure_capacity(self):
        """Cover lines 631-634: LRU eviction for capacity"""
        cache = MessagingCache(max_size=3, ttl_seconds=300)

        test_cache = OrderedDict()
        test_cache["key1"] = {"data": "1"}
        test_cache["key2"] = {"data": "2"}

        # Below capacity, should not evict
        cache._ensure_capacity(test_cache)
        assert len(test_cache) == 2

        # Add one more (now at capacity)
        test_cache["key3"] = {"data": "3"}

        # At capacity (len == max_size), will evict one (while len >= max_size)
        cache._ensure_capacity(test_cache)

        # After eviction, should be below max_size
        assert len(test_cache) == 2
        # key1 should be evicted (oldest)
        assert "key1" not in test_cache
        # key2 and key3 should remain
        assert "key2" in test_cache
        assert "key3" in test_cache

    def test_messaging_cache_get_stats(self):
        """Cover lines 636-653: Messaging cache statistics"""
        cache = MessagingCache(max_size=500, ttl_seconds=300)

        cache.set_platform_capabilities("slack", "INTERN", {"send": True})
        cache.get_platform_capabilities("slack", "INTERN")  # Hit
        cache.get_platform_capabilities("discord", "INTERN")  # Miss

        stats = cache.get_stats()

        assert stats["capabilities_cache_size"] == 1
        assert stats["monitors_cache_size"] == 0
        assert stats["total_hit_rate"] == 50.0
        assert stats["ttl_seconds"] == 300
        assert stats["max_size"] == 500

    def test_messaging_cache_clear(self):
        """Cover lines 655-663: Clear all messaging caches"""
        cache = MessagingCache(ttl_seconds=300)

        cache.set_platform_capabilities("slack", "INTERN", {"send": True})
        cache.set_monitor_definition("monitor-1", {"type": "keyword"})
        cache.set_template_render("template-1", "Hello")

        cache.clear()

        stats = cache.get_stats()
        assert stats["capabilities_cache_size"] == 0
        assert stats["monitors_cache_size"] == 0
        assert stats["templates_cache_size"] == 0

    def test_get_messaging_cache_singleton(self):
        """Cover lines 670-676: Global messaging cache singleton"""
        # Reset global cache
        import core.governance_cache
        core.governance_cache._messaging_cache = None

        cache1 = get_messaging_cache()
        cache2 = get_messaging_cache()

        assert cache1 is cache2  # Same instance

    # ========================================================================
    # Additional Edge Cases and Coverage Gaps
    # ========================================================================

    def test_cache_key_generation_case_insensitive(self):
        """Cover line 109: Action type lowercased in key"""
        cache = GovernanceCache(ttl_seconds=60)

        cache.set("agent-1", "Stream_LLM", {"allowed": True})

        # Should find with lowercase
        result = cache.get("agent-1", "stream_llm")
        assert result is not None

    def test_cleanup_task_cancelled_error(self):
        """Cover lines 81-82: Handle CancelledError gracefully"""
        cache = GovernanceCache()

        # Create task
        with patch('core.governance_cache.asyncio.get_event_loop') as mock_get_loop:
            mock_loop = MagicMock()
            mock_loop.is_running.return_value = True
            mock_get_loop.return_value = mock_loop

            mock_task = MagicMock()
            mock_loop.create_task.return_value = mock_task

            cache = GovernanceCache()

            # Simulate CancelledError
            async def raise_cancelled():
                raise asyncio.CancelledError()

            mock_task.side_effect = raise_cancelled

    def test_invalidate_nonexistent_agent(self):
        """Cover lines 208-209: Invalidate non-existent agent"""
        cache = GovernanceCache(ttl_seconds=60)

        # Should not raise error
        cache.invalidate("nonexistent-agent", "action1")
        cache.invalidate_agent("nonexistent-agent")

        assert cache._invalidations == 0

    def test_concurrent_hit_rate_calculation(self):
        """Cover lines 287: Thread-safe hit rate calculation"""
        cache = GovernanceCache(ttl_seconds=60)

        def cache_operations(agent_id):
            for i in range(10):
                cache.set(agent_id, f"action{i}", {"allowed": True})
                cache.get(agent_id, f"action{i}")

        threads = [
            threading.Thread(target=cache_operations, args=(f"agent-{i}",))
            for i in range(10)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Hit rate should be consistent
        stats = cache.get_stats()
        assert stats["hits"] == 100
        assert stats["hit_rate"] == 100.0

    def test_template_extended_ttl(self):
        """Cover lines 561-565: Templates have 10-minute TTL"""
        cache = MessagingCache(ttl_seconds=300)

        cache.set_template_render("template-1", "Hello")

        # Within 5-minute cache TTL
        with patch('time.time', return_value=time.time() + 301):
            result = cache.get_template_render("template-1")
            # Should still be there (10-minute TTL for templates)
            assert result is not None

        # Beyond 10-minute TTL
        with patch('time.time', return_value=time.time() + 601):
            result = cache.get_template_render("template-1")
            assert result is None

    def test_features_extended_ttl(self):
        """Cover lines 603-607: Features have 10-minute TTL"""
        cache = MessagingCache(ttl_seconds=300)

        cache.set_platform_features("slack", {"threads": True})

        # Within 5-minute cache TTL
        with patch('time.time', return_value=time.time() + 301):
            result = cache.get_platform_features("slack")
            # Should still be there (10-minute TTL for features)
            assert result is not None

        # Beyond 10-minute TTL
        with patch('time.time', return_value=time.time() + 601):
            result = cache.get_platform_features("slack")
            assert result is None

    def test_directory_cache_key_format(self):
        """Cover lines 254, 275: Directory cache uses 'dir:' prefix"""
        cache = GovernanceCache(ttl_seconds=60)

        cache.cache_directory("agent-1", "/tmp", {"allowed": True})

        # Verify key format
        key = cache._make_key("agent-1", "dir:/tmp")
        assert key in cache._cache

    def test_messaging_cache_stats_zero_total_requests(self):
        """Cover lines 642: Handle zero total requests in hit rate"""
        cache = MessagingCache()

        stats = cache.get_stats()
        assert stats["total_hit_rate"] == 0.0
