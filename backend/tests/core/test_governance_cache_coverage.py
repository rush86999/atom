"""
Coverage tests for core/governance_cache.py.

Existing unit tests (tests/unit/agent/test_governance_cache.py,
tests/unit/governance/test_governance_cache_performance.py) cover the sync
GovernanceCache API. This file covers the parts they miss:
- GovernanceCache async API (get_async/set_async/invalidate_async/clear_async/
  check_directory_async/cache_directory_async/get_stats_async/get_hit_rate_async)
- _expire_stale / _cleanup_expired / _start_cleanup_task
- Module-level singletons + cached_governance_check decorator
- AsyncGovernanceCache wrapper
- MessagingCache (all 4 cache types, TTLs, LRU, stats, clear)
"""
import asyncio
import time
from unittest.mock import patch

import pytest

import core.governance_cache as gc
from core.governance_cache import (
    AsyncGovernanceCache,
    GovernanceCache,
    MessagingCache,
    cached_governance_check,
    get_async_governance_cache,
    get_governance_cache,
    get_messaging_cache,
)


# ============================================================================
# GovernanceCache - SYNC API edge cases not covered elsewhere
# ============================================================================
class TestGovernanceCacheSyncEdgeCases:
    def test_get_miss_increments_misses(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        assert c.get("a", "x") is None
        assert c.get_stats()["misses"] == 1

    def test_get_hit_returns_data_and_increments_hits(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        c.set("a", "x", {"allowed": True})
        result = c.get("a", "x")
        assert result == {"allowed": True}
        stats = c.get_stats()
        assert stats["hits"] == 1

    def test_get_expired_returns_none_and_evicts(self):
        c = GovernanceCache(max_size=10, ttl_seconds=0.05)
        c.set("a", "x", {"v": 1})
        time.sleep(0.06)
        assert c.get("a", "x") is None
        # expired entry removed
        assert "a:x" not in c._cache
        assert c.get_stats()["misses"] == 1

    def test_action_type_is_lowercased_in_key(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        c.set("a", "STREAM_Chat", {"v": 1})
        # key uses lowercased action
        assert "a:stream_chat" in c._cache
        assert c.get("a", "stream_chat") == {"v": 1}

    def test_lru_eviction_removes_oldest(self):
        c = GovernanceCache(max_size=2, ttl_seconds=60)
        c.set("a", "x", {"1": 1})
        c.set("b", "x", {"2": 2})
        # access 'a' to make it most-recently-used
        c.get("a", "x")
        # adding 'c' should evict 'b' (least recently used)
        c.set("c", "x", {"3": 3})
        assert "a:x" in c._cache
        assert "b:x" not in c._cache
        assert c.get_stats()["evictions"] == 1

    def test_set_overwrite_existing_does_not_evict(self):
        c = GovernanceCache(max_size=2, ttl_seconds=60)
        c.set("a", "x", {"1": 1})
        c.set("b", "x", {"2": 2})
        # overwrite 'a' at capacity - should NOT evict
        c.set("a", "x", {"1": 10})
        assert len(c._cache) == 2
        assert c.get("a", "x") == {"1": 10}

    def test_invalidate_specific_action(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        c.set("a", "x", {"1": 1})
        c.set("a", "y", {"2": 2})
        c.invalidate("a", "x")
        assert c.get("a", "x") is None
        assert c.get("a", "y") == {"2": 2}
        assert c.get_stats()["invalidations"] == 1

    def test_invalidate_specific_action_not_present(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        # should not raise, invalidations stays 0
        c.invalidate("a", "missing")
        assert c.get_stats()["invalidations"] == 0

    def test_invalidate_agent_all_actions(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        c.set("a", "x", {"1": 1})
        c.set("a", "y", {"2": 2})
        c.set("b", "x", {"3": 3})
        c.invalidate_agent("a")
        assert c.get("a", "x") is None
        assert c.get("a", "y") is None
        assert c.get("b", "x") == {"3": 3}
        assert c.get_stats()["invalidations"] == 2

    def test_invalidate_agent_with_no_entries(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        c.invalidate_agent("ghost")  # no-op

    def test_clear(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        c.set("a", "x", {"1": 1})
        c.clear()
        assert len(c._cache) == 0

    def test_get_hit_rate_helper(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        c.set("a", "x", {"1": 1})
        c.get("a", "x")  # hit
        c.get("a", "y")  # miss
        rate = c.get_hit_rate()
        assert rate == 50.0

    def test_directory_helpers_sync(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        c.cache_directory("a", "/tmp", {"allowed": True})
        result = c.check_directory("a", "/tmp")
        assert result == {"allowed": True}
        # directory stats tracked
        stats = c.get_stats()
        assert stats["directory_hits"] == 1

    def test_directory_miss_sync(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        assert c.check_directory("a", "/tmp") is None
        stats = c.get_stats()
        assert stats["directory_misses"] == 1

    def test_stats_zero_requests(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        stats = c.get_stats()
        assert stats["hit_rate"] == 0
        assert stats["directory_hit_rate"] == 0
        assert stats["size"] == 0

    def test_make_key(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        # Only the action_type is lowercased; agent_id is preserved as-is.
        assert c._make_key("A1", "Action") == "A1:action"


# ============================================================================
# GovernanceCache - ASYNC API
# ============================================================================
class TestGovernanceCacheAsync:
    @pytest.mark.asyncio
    async def test_get_async_miss(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        assert await c.get_async("a", "x") is None
        assert c.get_stats()["misses"] == 1

    @pytest.mark.asyncio
    async def test_get_async_hit(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        await c.set_async("a", "x", {"v": 1})
        assert await c.get_async("a", "x") == {"v": 1}
        assert c.get_stats()["hits"] == 1

    @pytest.mark.asyncio
    async def test_get_async_expired(self):
        c = GovernanceCache(max_size=10, ttl_seconds=0.05)
        await c.set_async("a", "x", {"v": 1})
        await asyncio.sleep(0.06)
        assert await c.get_async("a", "x") is None

    @pytest.mark.asyncio
    async def test_get_async_directory_hit(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        await c.set_async("a", "dir:/tmp", {"allowed": True})
        result = await c.get_async("a", "dir:/tmp")
        assert result == {"allowed": True}
        assert c.get_stats()["directory_hits"] == 1

    @pytest.mark.asyncio
    async def test_set_async_returns_true(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        assert await c.set_async("a", "x", {"v": 1}) is True

    @pytest.mark.asyncio
    async def test_set_async_lru_eviction(self):
        c = GovernanceCache(max_size=2, ttl_seconds=60)
        await c.set_async("a", "x", {"1": 1})
        await c.set_async("b", "x", {"2": 2})
        await c.set_async("c", "x", {"3": 3})
        # 'a' was oldest, evicted
        assert await c.get_async("a", "x") is None
        assert await c.get_async("c", "x") == {"3": 3}

    @pytest.mark.asyncio
    async def test_invalidate_async_specific(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        await c.set_async("a", "x", {"1": 1})
        await c.invalidate_async("a", "x")
        assert await c.get_async("a", "x") is None
        assert c.get_stats()["invalidations"] == 1

    @pytest.mark.asyncio
    async def test_invalidate_async_all_for_agent(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        await c.set_async("a", "x", {"1": 1})
        await c.set_async("a", "y", {"2": 2})
        await c.invalidate_async("a")
        assert await c.get_async("a", "x") is None
        assert await c.get_async("a", "y") is None

    @pytest.mark.asyncio
    async def test_invalidate_agent_async(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        await c.set_async("a", "x", {"1": 1})
        await c.invalidate_agent_async("a")
        assert await c.get_async("a", "x") is None

    @pytest.mark.asyncio
    async def test_clear_async(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        await c.set_async("a", "x", {"1": 1})
        await c.clear_async()
        assert len(c._cache) == 0

    @pytest.mark.asyncio
    async def test_check_directory_async(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        await c.cache_directory_async("a", "/tmp", {"allowed": True})
        result = await c.check_directory_async("a", "/tmp")
        assert result == {"allowed": True}

    @pytest.mark.asyncio
    async def test_cache_directory_async_returns_true(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        assert await c.cache_directory_async("a", "/tmp", {"allowed": True}) is True

    @pytest.mark.asyncio
    async def test_get_stats_async(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        await c.set_async("a", "x", {"1": 1})
        await c.get_async("a", "x")
        stats = await c.get_stats_async()
        assert stats["hits"] == 1
        assert stats["size"] == 1

    @pytest.mark.asyncio
    async def test_get_hit_rate_async(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        await c.set_async("a", "x", {"1": 1})
        await c.get_async("a", "x")
        assert await c.get_hit_rate_async() == 100.0


# ============================================================================
# _expire_stale / _cleanup_expired / _start_cleanup_task
# ============================================================================
class TestBackgroundCleanup:
    @pytest.mark.asyncio
    async def test_expire_stale_removes_expired(self):
        c = GovernanceCache(max_size=10, ttl_seconds=0.05)
        c.set("a", "x", {"1": 1})
        c.set("b", "x", {"2": 2})
        await asyncio.sleep(0.06)
        await c._expire_stale()
        assert len(c._cache) == 0
        assert c.get_stats()["evictions"] == 2

    @pytest.mark.asyncio
    async def test_expire_stale_keeps_fresh(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        c.set("a", "x", {"1": 1})
        await c._expire_stale()
        assert len(c._cache) == 1

    @pytest.mark.asyncio
    async def test_expire_stale_empty_cache_no_error(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        await c._expire_stale()  # no entries, no error

    def test_start_cleanup_task_no_running_loop(self):
        """_start_cleanup_task when no event loop is running should log + skip."""
        # Construct in a context with no running loop is tricky; just verify
        # the method exists and does not crash when called outside a loop.
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        # Should not raise even though loop may not be running
        c._start_cleanup_task()


# ============================================================================
# Module-level singletons + decorator
# ============================================================================
class TestSingletonsAndDecorator:
    def test_get_governance_cache_singleton(self):
        c1 = get_governance_cache()
        c2 = get_governance_cache()
        assert c1 is c2

    @pytest.mark.asyncio
    async def test_cached_governance_check_decorator_cache_hit(self):
        # Use a fresh global cache to control state
        global_cache = get_governance_cache()
        global_cache.clear()
        call_count = 0

        @cached_governance_check
        async def check(agent_id, action_type):
            nonlocal call_count
            call_count += 1
            return {"allowed": True, "call": call_count}

        r1 = await check("a", "x")
        r2 = await check("a", "x")
        assert r1 == {"allowed": True, "call": 1}
        assert r2 == {"allowed": True, "call": 1}  # served from cache
        assert call_count == 1
        global_cache.clear()

    @pytest.mark.asyncio
    async def test_cached_governance_check_decorator_cache_miss_calls_func(self):
        global_cache = get_governance_cache()
        global_cache.clear()

        @cached_governance_check
        async def check(agent_id, action_type, extra=None):
            return {"allowed": True, "extra": extra}

        result = await check("a", "y", extra="payload")
        assert result == {"allowed": True, "extra": "payload"}
        global_cache.clear()


# ============================================================================
# AsyncGovernanceCache wrapper
# ============================================================================
class TestAsyncGovernanceCacheWrapper:
    @pytest.mark.asyncio
    async def test_get_set(self):
        wrapper = AsyncGovernanceCache(GovernanceCache(max_size=10, ttl_seconds=60))
        await wrapper.set("a", "x", {"v": 1})
        assert await wrapper.get("a", "x") == {"v": 1}

    @pytest.mark.asyncio
    async def test_invalidate(self):
        wrapper = AsyncGovernanceCache(GovernanceCache(max_size=10, ttl_seconds=60))
        await wrapper.set("a", "x", {"v": 1})
        await wrapper.invalidate("a", "x")
        assert await wrapper.get("a", "x") is None

    @pytest.mark.asyncio
    async def test_invalidate_agent(self):
        wrapper = AsyncGovernanceCache(GovernanceCache(max_size=10, ttl_seconds=60))
        await wrapper.set("a", "x", {"v": 1})
        await wrapper.invalidate_agent("a")
        assert await wrapper.get("a", "x") is None

    @pytest.mark.asyncio
    async def test_get_stats_and_hit_rate(self):
        wrapper = AsyncGovernanceCache(GovernanceCache(max_size=10, ttl_seconds=60))
        await wrapper.set("a", "x", {"v": 1})
        await wrapper.get("a", "x")
        stats = await wrapper.get_stats()
        assert stats["hits"] == 1
        assert await wrapper.get_hit_rate() == 100.0

    def test_get_async_governance_cache(self):
        w = get_async_governance_cache()
        assert isinstance(w, AsyncGovernanceCache)


# ============================================================================
# MessagingCache
# ============================================================================
class TestMessagingCache:
    def test_capabilities_get_set(self):
        mc = MessagingCache(max_size=10, ttl_seconds=60)
        assert mc.get_platform_capabilities("slack", "intern") is None
        mc.set_platform_capabilities("slack", "intern", {"send": True})
        result = mc.get_platform_capabilities("slack", "intern")
        assert result == {"send": True}

    def test_capabilities_expired(self):
        mc = MessagingCache(max_size=10, ttl_seconds=0.05)
        mc.set_platform_capabilities("slack", "intern", {"send": True})
        time.sleep(0.06)
        assert mc.get_platform_capabilities("slack", "intern") is None

    def test_monitor_get_set_invalidate(self):
        mc = MessagingCache(max_size=10, ttl_seconds=60)
        assert mc.get_monitor_definition("m1") is None
        mc.set_monitor_definition("m1", {"name": "monitor1"})
        assert mc.get_monitor_definition("m1") == {"name": "monitor1"}
        mc.invalidate_monitor("m1")
        assert mc.get_monitor_definition("m1") is None

    def test_monitor_expired(self):
        mc = MessagingCache(max_size=10, ttl_seconds=0.05)
        mc.set_monitor_definition("m1", {"name": "monitor1"})
        time.sleep(0.06)
        assert mc.get_monitor_definition("m1") is None

    def test_template_get_set_with_longer_ttl(self):
        mc = MessagingCache(max_size=10, ttl_seconds=60)
        assert mc.get_template_render("t1") is None
        mc.set_template_render("t1", "rendered text")
        assert mc.get_template_render("t1") == "rendered text"

    def test_template_expired_after_600s_window(self):
        """Templates use a hard-coded 600s TTL independent of ttl_seconds."""
        mc = MessagingCache(max_size=10, ttl_seconds=60)
        mc.set_template_render("t1", "rendered text")
        # Manually backdate the entry to simulate >600s age
        mc._templates["t1"]["cached_at"] = time.time() - 601
        assert mc.get_template_render("t1") is None

    def test_features_get_set_with_longer_ttl(self):
        mc = MessagingCache(max_size=10, ttl_seconds=60)
        assert mc.get_platform_features("slack") is None
        mc.set_platform_features("slack", {"reactions": True})
        assert mc.get_platform_features("slack") == {"reactions": True}

    def test_features_expired_after_600s_window(self):
        mc = MessagingCache(max_size=10, ttl_seconds=60)
        mc.set_platform_features("slack", {"reactions": True})
        mc._features["slack"]["cached_at"] = time.time() - 601
        assert mc.get_platform_features("slack") is None

    def test_lru_eviction_capabilities(self):
        mc = MessagingCache(max_size=2, ttl_seconds=60)
        mc.set_platform_capabilities("slack", "a", {"1": 1})
        mc.set_platform_capabilities("slack", "b", {"2": 2})
        mc.set_platform_capabilities("slack", "c", {"3": 3})  # evicts 'a'
        assert mc.get_platform_capabilities("slack", "a") is None
        assert mc.get_platform_capabilities("slack", "c") == {"3": 3}

    def test_stats(self):
        mc = MessagingCache(max_size=10, ttl_seconds=60)
        mc.set_platform_capabilities("slack", "a", {"1": 1})
        mc.get_platform_capabilities("slack", "a")  # hit
        mc.get_platform_capabilities("slack", "z")  # miss
        stats = mc.get_stats()
        assert stats["capabilities_cache_size"] == 1
        assert stats["stats"]["capabilities_hits"] == 1
        assert stats["stats"]["capabilities_misses"] == 1
        # total hit rate: 1 hit / 2 requests = 50%
        assert stats["total_hit_rate"] == 50.0

    def test_stats_zero_requests(self):
        mc = MessagingCache(max_size=10, ttl_seconds=60)
        stats = mc.get_stats()
        assert stats["total_hit_rate"] == 0

    def test_clear(self):
        mc = MessagingCache(max_size=10, ttl_seconds=60)
        mc.set_platform_capabilities("slack", "a", {"1": 1})
        mc.set_monitor_definition("m", {"x": 1})
        mc.set_template_render("t", "r")
        mc.set_platform_features("slack", {"f": 1})
        mc.clear()
        stats = mc.get_stats()
        assert stats["capabilities_cache_size"] == 0
        assert stats["monitors_cache_size"] == 0
        assert stats["templates_cache_size"] == 0
        assert stats["features_cache_size"] == 0

    def test_get_messaging_cache_singleton(self):
        m1 = get_messaging_cache()
        m2 = get_messaging_cache()
        assert m1 is m2

    def test_invalidate_monitor_not_present(self):
        """invalidate_monitor on missing id is a no-op."""
        mc = MessagingCache(max_size=10, ttl_seconds=60)
        mc.invalidate_monitor("ghost")  # no error


# ============================================================================
# Exception-swallow branches (force errors inside locked sections)
# ============================================================================
class TestExceptionBranches:
    def test_set_handles_internal_exception(self):
        """set() returns False when an exception occurs inside the locked block."""
        c = GovernanceCache(max_size=10, ttl_seconds=60)

        original_cache = c._cache

        class BoomDict:
            def __setitem__(self, key, value):
                raise RuntimeError("setitem boom")

            def __len__(self):
                return 0

            def __contains__(self, key):
                return False

        c._cache = BoomDict()
        # The internal assignment to c._cache[key] raises -> caught -> returns False
        assert c.set("a", "x", {"v": 1}) is False
        c._cache = original_cache

    def test_invalidate_handles_internal_exception(self):
        """invalidate() must not raise when an internal error occurs."""
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        c.set("a", "x", {"v": 1})

        class BoomList:
            def __iter__(self):
                raise RuntimeError("iter boom")

        # Force keys() to raise
        original_keys = c._cache.keys
        c._cache.keys = lambda: (_ for _ in BoomList())
        # must not raise
        c.invalidate("a")
        c._cache.keys = original_keys

    @pytest.mark.asyncio
    async def test_set_async_handles_internal_exception(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)

        class BoomDict:
            def __setitem__(self, key, value):
                raise RuntimeError("async setitem boom")

            def __len__(self):
                return 0

            def __contains__(self, key):
                return False

        c._cache = BoomDict()
        assert await c.set_async("a", "x", {"v": 1}) is False

    @pytest.mark.asyncio
    async def test_invalidate_async_handles_internal_exception(self):
        c = GovernanceCache(max_size=10, ttl_seconds=60)

        class BoomDict:
            def __contains__(self, key):
                raise RuntimeError("async contains boom")

            def __len__(self):
                return 0

        c._cache = BoomDict()
        # must not raise
        await c.invalidate_async("a")

    @pytest.mark.asyncio
    async def test_check_directory_async_miss(self):
        """Cover directory miss branch in get_async via check_directory_async."""
        c = GovernanceCache(max_size=10, ttl_seconds=60)
        result = await c.check_directory_async("a", "/tmp")
        assert result is None
        assert c.get_stats()["directory_misses"] == 1

    def test_sync_get_directory_expired_increments_dir_miss(self):
        """Cover directory-miss branch when an expired dir entry is evicted."""
        c = GovernanceCache(max_size=10, ttl_seconds=0.05)
        c.cache_directory("a", "/tmp", {"allowed": True})
        time.sleep(0.06)
        assert c.check_directory("a", "/tmp") is None
        assert c.get_stats()["directory_misses"] == 1
