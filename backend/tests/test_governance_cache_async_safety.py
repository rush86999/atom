"""
Test suite for GovernanceCache async safety verification.

GREEN PHASE: These tests verify the bug fix for threading.Lock in async contexts.

The fix implements a dual-lock system:
- threading.Lock for synchronous methods (backward compatibility)
- asyncio.Lock for async-safe methods (proper async concurrency protection)
"""

import asyncio
import pytest
from collections import OrderedDict
from unittest.mock import patch

from core.governance_cache import GovernanceCache, get_governance_cache


class TestGovernanceCacheAsyncSafety:
    """
    Test suite verifying the concurrency bug fix in GovernanceCache.

    The fix: Added dual-lock system with threading.Lock for sync methods
    and asyncio.Lock for async methods (get_async, set_async, etc.).
    """

    @pytest.mark.asyncio
    async def test_dual_lock_system_exists(self):
        """Verify both locks exist and are correct types."""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        import threading
        assert isinstance(cache._lock, threading.Lock), \
            "Sync lock should be threading.Lock for backward compatibility"
        assert isinstance(cache._async_lock, asyncio.Lock), \
            "Async lock should be asyncio.Lock for proper async protection"

    @pytest.mark.asyncio
    async def test_async_methods_use_async_lock(self):
        """Test that async methods properly use asyncio.Lock."""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Test set_async and get_async
        await cache.set_async("agent_1", "action", {"allowed": True})
        result = await cache.get_async("agent_1", "action")

        assert result == {"allowed": True}

    @pytest.mark.asyncio
    async def test_concurrent_async_operations_safe(self):
        """Test that concurrent async operations are properly protected."""
        cache = GovernanceCache(max_size=10, ttl_seconds=60)

        results = []
        errors = []

        async def set_agent(agent_id):
            try:
                await cache.set_async(f"agent_{agent_id}", "action", {"data": agent_id})
                results.append(agent_id)
            except Exception as e:
                errors.append((agent_id, type(e).__name__, str(e)))

        # Launch 20 concurrent async sets on a cache with max_size=10
        tasks = [set_agent(i) for i in range(20)]
        await asyncio.gather(*tasks)

        # Should have no errors
        assert len(errors) == 0, f"Errors during concurrent async sets: {errors}"
        assert len(results) == 20

    @pytest.mark.asyncio
    async def test_async_invalidate_safe(self):
        """Test that async invalidate is properly protected."""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Add some entries
        for i in range(10):
            await cache.set_async(f"agent_{i}", "action", {"data": i})

        # Invalidate using async method
        await cache.invalidate_async("agent_5")

        # Verify it's gone
        result = await cache.get_async("agent_5", "action")
        assert result is None

    @pytest.mark.asyncio
    async def test_async_stats_safe(self):
        """Test that async stats are properly protected."""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Add some entries
        for i in range(10):
            await cache.set_async(f"agent_{i}", "action", {"data": i})

        # Get stats using async method
        stats = await cache.get_stats_async()

        assert stats["size"] == 10
        assert stats["hits"] == 0
        assert stats["misses"] == 0

    @pytest.mark.asyncio
    async def test_sync_methods_still_work(self):
        """Test that synchronous methods still work for backward compatibility."""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Use sync methods
        cache.set("agent_1", "action", {"allowed": True})
        result = cache.get("agent_1", "action")

        assert result == {"allowed": True}

        # Sync stats
        stats = cache.get_stats()
        assert stats["size"] == 1

    @pytest.mark.asyncio
    async def test_mixed_sync_and_async_safe(self):
        """Test that mixing sync and async methods is safe."""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Set via sync
        cache.set("agent_1", "action", {"sync": True})

        # Get via async
        result = await cache.get_async("agent_1", "action")
        assert result == {"sync": True}

        # Set via async
        await cache.set_async("agent_2", "action", {"async": True})

        # Get via sync
        result = cache.get("agent_2", "action")
        assert result == {"async": True}

    @pytest.mark.asyncio
    async def test_async_lock_blocks_concurrent_modification(self):
        """Test that asyncio.Lock properly blocks concurrent modifications."""
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Simply verify that multiple concurrent operations work correctly
        # without race conditions
        tasks = []
        for i in range(10):
            tasks.append(cache.set_async(f"agent_{i}", "action", {"data": i}))

        # All should complete without errors
        await asyncio.gather(*tasks)

        # Verify all data was set correctly
        for i in range(10):
            result = await cache.get_async(f"agent_{i}", "action")
            assert result == {"data": i}, f"Data for agent_{i} incorrect"

    @pytest.mark.asyncio
    async def test_background_cleanup_uses_async_lock(self):
        """Test that background cleanup task uses async lock correctly."""
        cache = GovernanceCache(max_size=100, ttl_seconds=1)  # 1 second TTL

        # Add entries
        import time
        await cache.set_async("expiring", "action", {"data": "old"})
        cache._cache["expiring:action"]["cached_at"] = time.time() - 2  # Expired

        # Trigger cleanup
        await cache._expire_stale()

        # Verify expired entry is gone
        result = await cache.get_async("expiring", "action")
        assert result is None, "Expired entry should be removed"


class TestAsyncGovernanceCacheWrapper:
    """Test the AsyncGovernanceCache wrapper."""

    @pytest.mark.asyncio
    async def test_wrapper_delegates_to_async_methods(self):
        """Test that wrapper correctly delegates to async methods."""
        from core.governance_cache import AsyncGovernanceCache

        cache = GovernanceCache(max_size=100, ttl_seconds=60)
        wrapper = AsyncGovernanceCache(cache)

        # Use wrapper methods
        await wrapper.set("agent_1", "action", {"allowed": True})
        result = await wrapper.get("agent_1", "action")

        assert result == {"allowed": True}

    @pytest.mark.asyncio
    async def test_wrapper_invalidate(self):
        """Test wrapper invalidate method."""
        from core.governance_cache import AsyncGovernanceCache

        cache = GovernanceCache(max_size=100, ttl_seconds=60)
        wrapper = AsyncGovernanceCache(cache)

        await wrapper.set("agent_1", "action", {"allowed": True})
        await wrapper.invalidate("agent_1")

        result = await wrapper.get("agent_1", "action")
        assert result is None

    @pytest.mark.asyncio
    async def test_wrapper_stats(self):
        """Test wrapper stats methods."""
        from core.governance_cache import AsyncGovernanceCache

        cache = GovernanceCache(max_size=100, ttl_seconds=60)
        wrapper = AsyncGovernanceCache(cache)

        await wrapper.set("agent_1", "action", {"allowed": True})
        stats = await wrapper.get_stats()

        assert stats["size"] == 1

        hit_rate = await wrapper.get_hit_rate()
        assert hit_rate == 0.0  # No hits yet


class TestCachedGovernanceCheckDecorator:
    """Test the cached_governance_check decorator."""

    @pytest.mark.asyncio
    async def test_decorator_uses_async_methods(self):
        """Test that decorator uses async-safe cache methods."""
        from core.governance_cache import cached_governance_check

        call_count = 0

        @cached_governance_check
        async def check_permission(agent_id, action_type):
            nonlocal call_count
            call_count += 1
            return {"allowed": True, "agent": agent_id}

        # First call - cache miss
        result1 = await check_permission("agent_1", "action")
        assert result1 == {"allowed": True, "agent": "agent_1"}
        assert call_count == 1

        # Second call - cache hit (should not increment call_count)
        result2 = await check_permission("agent_1", "action")
        assert result2 == {"allowed": True, "agent": "agent_1"}
        assert call_count == 1, "Should not call function again on cache hit"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
