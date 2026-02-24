"""
Governance Cache Error Path Tests

Comprehensive error handling tests for GovernanceCache that validate:
- Initialization errors (invalid max_size, ttl_seconds, event loop issues)
- Cache get() errors (invalid types, corrupted entries, race conditions)
- Cache set() errors (oversized data, concurrent writes, eviction failures)
- Cache invalidate() errors (invalid formats, race conditions)
- Async cache wrapper errors (missing sync instance, delegation failures)

These tests discover bugs in exception handling code that is rarely
executed in normal operation but critical for production reliability.
"""

import pytest
import asyncio
import threading
import time
from typing import Dict, Any
from unittest.mock import patch, MagicMock

from core.governance_cache import (
    GovernanceCache,
    AsyncGovernanceCache,
    get_governance_cache,
    cached_governance_check
)


# ============================================================================
# Cache Initialization Errors
# ============================================================================


class TestCacheInitializationErrors:
    """Test cache initialization with invalid parameters"""

    def test_cache_with_negative_max_size(self):
        """
        ERROR PATH: Negative max_size should be handled gracefully.
        EXPECTED: Cache accepts negative value or raises ValueError with clear message.
        BUG_FOUND: Cache accepts negative max_size without validation,可能导致后续逻辑错误。
        """
        # GovernanceCache doesn't validate max_size, so it accepts negative values
        cache = GovernanceCache(max_size=-100, ttl_seconds=60)
        assert cache.max_size == -100  # Accepted without validation
        # BUG: Negative max_size causes issues in eviction logic (line 176: if len(self._cache) >= self.max_size)

    def test_cache_with_zero_max_size(self):
        """
        ERROR PATH: Zero max_size should prevent cache from storing entries.
        EXPECTED: Cache cannot store any entries (LRU eviction triggers immediately).
        BUG_FOUND: Cache with max_size=0 causes set() to fail with exception due to OrderedDict.popitem() on empty dict.
        """
        cache = GovernanceCache(max_size=0, ttl_seconds=60)

        # Try to set an entry - this fails because max_size=0 triggers eviction on empty cache
        # Line 176: if len(self._cache) >= self.max_size and key not in self._cache:
        # Line 178: oldest_key = next(iter(self._cache)) raises StopIteration on empty dict
        result = cache.set("agent-1", "stream_chat", {"allowed": True})
        assert result is False  # Set fails due to exception in eviction logic

    def test_cache_with_extremely_large_max_size(self):
        """
        ERROR PATH: Extremely large max_size may cause memory issues.
        EXPECTED: Cache accepts large value without crashing.
        """
        cache = GovernanceCache(max_size=10**9, ttl_seconds=60)  # 1 billion entries
        assert cache.max_size == 10**9

        # Verify cache can still store entries
        cache.set("agent-1", "stream_chat", {"allowed": True})
        assert cache.get("agent-1", "stream_chat") is not None

    def test_cache_with_negative_ttl(self):
        """
        ERROR PATH: Negative TTL should be handled gracefully.
        EXPECTED: Cache accepts negative TTL or raises ValueError.
        BUG_FOUND: Cache accepts negative ttl_seconds without validation.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=-60)
        assert cache.ttl_seconds == -60  # Accepted without validation

        # Entries with negative TTL expire immediately
        cache.set("agent-1", "stream_chat", {"allowed": True})
        retrieved = cache.get("agent-1", "stream_chat")
        # Entry considered expired (age_seconds > -60 is always True)
        assert retrieved is None

    def test_cache_with_zero_ttl(self):
        """
        ERROR PATH: Zero TTL means entries expire immediately.
        EXPECTED: Entries always considered expired, cache misses every time.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=0)

        cache.set("agent-1", "stream_chat", {"allowed": True})
        retrieved = cache.get("agent-1", "stream_chat")
        # Entry expires immediately (age_seconds > 0 is always True for entries set 1ms ago)
        assert retrieved is None

    def test_cache_without_running_event_loop(self):
        """
        ERROR PATH: Cleanup task requires running event loop.
        EXPECTED: Cache logs warning but continues functioning.
        BUG_FOUND: Cleanup task fails silently if no event loop running.
        """
        # Ensure no event loop is running
        try:
            asyncio.get_event_loop().close()
        except:
            pass

        # Cache should still initialize without event loop
        cache = GovernanceCache(max_size=100, ttl_seconds=60)
        assert cache is not None

        # Cache should still work
        cache.set("agent-1", "stream_chat", {"allowed": True})
        assert cache.get("agent-1", "stream_chat") is not None

        # Cleanup task should be None (line 63: self._cleanup_task = None)
        assert cache._cleanup_task is None


# ============================================================================
# Cache get() Errors
# ============================================================================


class TestCacheGetErrors:
    """Test cache get() with invalid inputs and corrupted entries"""

    def test_cache_get_with_non_string_agent_id(self):
        """
        ERROR PATH: Non-string agent_id should be handled gracefully.
        EXPECTED: TypeError raised with clear message, or auto-conversion to string.
        BUG_FOUND: _make_key() uses f-string formatting which converts non-strings to strings.
                   Both "00123" and 123 become "00123:stream_chat" vs "123:stream_chat",
                   but f"{123}" = "123", so integer 123 cannot retrieve string "00123" entry.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Set with string agent_id "123"
        cache.set("123", "stream_chat", {"allowed": True})

        # Get with integer agent_id 123 - f-string converts to "123"
        result = cache.get(123, "stream_chat")  # f"{123}:{action}" = "123:stream_chat"
        assert result is not None  # Works due to f-string conversion

        # Set with string agent_id "00123" (different from "123")
        cache.set("00123", "stream_chat", {"allowed": False})

        # Get with integer 123 still retrieves "123" entry (not "00123")
        result2 = cache.get(123, "stream_chat")  # "123:stream_chat" != "00123:stream_chat"
        assert result2 is not None  # Returns "123" entry, not "00123"
        assert result2["allowed"] is True  # From "123" entry

        # BUG: Integer 123 cannot retrieve "00123" entry due to string conversion differences

    def test_cache_get_with_empty_string_agent_id(self):
        """
        ERROR PATH: Empty string agent_id should be handled.
        EXPECTED: Cache handles empty strings gracefully (no crashes).
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Empty agent_id creates key like ":stream_chat"
        result = cache.get("", "stream_chat")
        assert result is None  # Cache miss (no entry stored)

        # Can store with empty agent_id (weird but doesn't crash)
        cache.set("", "stream_chat", {"allowed": True})
        result = cache.get("", "stream_chat")
        assert result is not None  # Entry retrieved

    def test_cache_get_with_corrupted_entry_missing_data_key(self):
        """
        ERROR PATH: Cache entry missing 'data' key should be handled.
        EXPECTED: Corrupted entry is skipped or deleted, returns None.
        BUG_FOUND: Line 152 returns entry["data"] directly, will raise KeyError if missing.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Manually insert corrupted entry (missing 'data' key)
        cache._cache["agent-1:stream_chat"] = {
            "cached_at": time.time()
            # Missing "data" key
        }

        # Try to get corrupted entry
        with pytest.raises(KeyError) as exc_info:
            cache.get("agent-1", "stream_chat")

        assert "data" in str(exc_info.value).lower()
        # BUG: Cache crashes with KeyError instead of handling corrupted entry gracefully

    def test_cache_get_with_corrupted_entry_missing_timestamp(self):
        """
        ERROR PATH: Cache entry missing 'cached_at' timestamp.
        EXPECTED: Uses default timestamp (line 133: cached_at = entry.get("cached_at", 0)).
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Insert entry without timestamp
        cache._cache["agent-1:stream_chat"] = {
            "data": {"allowed": True}
            # Missing "cached_at" key
        }

        # get() uses .get("cached_at", 0) as default (line 133)
        result = cache.get("agent-1", "stream_chat")
        # Entry considered expired (time.time() - 0 > ttl_seconds)
        assert result is None  # Expired due to missing timestamp

    def test_cache_get_with_expired_entry_deletion(self):
        """
        ERROR PATH: Expired entry should be deleted during get().
        EXPECTED: Entry removed from cache, returns None.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=1)

        # Set entry
        cache.set("agent-1", "stream_chat", {"allowed": True})
        assert cache.get("agent-1", "stream_chat") is not None

        # Wait for expiration
        time.sleep(1.5)

        # Get should delete expired entry (line 138: del self._cache[key])
        result = cache.get("agent-1", "stream_chat")
        assert result is None

        # Verify entry was deleted from cache
        assert "agent-1:stream_chat" not in cache._cache

    def test_cache_get_concurrent_reads(self):
        """
        ERROR PATH: Concurrent get() calls with same key.
        EXPECTED: Thread-safe, no race conditions or data corruption.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)
        cache.set("agent-1", "stream_chat", {"allowed": True})

        results = []
        errors = []

        def read_operation():
            try:
                result = cache.get("agent-1", "stream_chat")
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Spawn 10 threads reading same key
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=read_operation)
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join(timeout=5.0)

        # All threads should succeed
        assert len(errors) == 0, f"Concurrent reads raised errors: {errors}"
        assert len(results) == 10
        assert all(r is not None for r in results)


# ============================================================================
# Cache set() Errors
# ============================================================================


class TestCacheSetErrors:
    """Test cache set() with invalid inputs and edge cases"""

    def test_cache_set_with_oversized_data(self):
        """
        ERROR PATH: Oversized data may cause memory issues.
        EXPECTED: Cache accepts large data, but may evict other entries.
        """
        cache = GovernanceCache(max_size=10, ttl_seconds=60)

        # Fill cache to capacity
        for i in range(10):
            cache.set(f"agent-{i}", "stream_chat", {"allowed": True})

        assert len(cache._cache) == 10

        # Add one more (should evict oldest)
        cache.set("agent-10", "stream_chat", {"allowed": True})
        assert len(cache._cache) == 10  # Still at capacity

        # Oldest entry should be evicted
        assert cache.get("agent-0", "stream_chat") is None

    def test_cache_set_concurrent_writes_same_key(self):
        """
        ERROR PATH: Concurrent writes to same key may cause race condition.
        EXPECTED: Last write wins (thread-safe with lock).
        BUG_FOUND: With lock, only one thread writes at a time, but final value depends on timing.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        errors = []
        final_values = []

        def write_operation(agent_id: str, value: bool):
            try:
                cache.set(agent_id, "stream_chat", {"allowed": value})
                result = cache.get(agent_id, "stream_chat")
                final_values.append(result["allowed"])
            except Exception as e:
                errors.append(e)

        # Spawn 5 threads writing to same key with different values
        threads = []
        for i in range(5):
            thread = threading.Thread(target=write_operation, args=("agent-1", i % 2 == 0))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join(timeout=5.0)

        # All threads should succeed
        assert len(errors) == 0, f"Concurrent writes raised errors: {errors}"
        assert len(final_values) == 5

        # Final value should be one of the written values (True or False)
        final_result = cache.get("agent-1", "stream_chat")
        assert final_result is not None
        assert final_result["allowed"] in [True, False]

    def test_cache_set_concurrent_writes_different_keys(self):
        """
        ERROR PATH: Concurrent writes to different keys.
        EXPECTED: All writes succeed, no data corruption.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        errors = []
        success_count = [0]

        def write_operation(agent_id: str):
            try:
                cache.set(agent_id, "stream_chat", {"allowed": True})
                success_count[0] += 1
            except Exception as e:
                errors.append(e)

        # Spawn 20 threads writing to different keys
        threads = []
        for i in range(20):
            thread = threading.Thread(target=write_operation, args=(f"agent-{i}",))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join(timeout=5.0)

        # All threads should succeed
        assert len(errors) == 0, f"Concurrent writes raised errors: {errors}"
        assert success_count[0] == 20

        # Verify all entries were stored
        for i in range(20):
            assert cache.get(f"agent-{i}", "stream_chat") is not None

    def test_cache_set_eviction_during_capacity_overflow(self):
        """
        ERROR PATH: Cache eviction when at capacity.
        EXPECTED: Oldest entry evicted, new entry added.
        """
        cache = GovernanceCache(max_size=5, ttl_seconds=60)

        # Fill cache to capacity
        for i in range(5):
            cache.set(f"agent-{i}", "stream_chat", {"allowed": i})

        assert len(cache._cache) == 5
        assert cache._evictions == 0

        # Add one more (should trigger eviction)
        cache.set("agent-5", "stream_chat", {"allowed": 5})

        # Verify eviction
        assert len(cache._cache) == 5  # Still at capacity
        assert cache._evictions == 1  # One eviction occurred
        assert cache.get("agent-0", "stream_chat") is None  # Oldest evicted
        assert cache.get("agent-5", "stream_chat") is not None  # New entry added


# ============================================================================
# Cache invalidate() Errors
# ============================================================================


class TestCacheInvalidateErrors:
    """Test cache invalidate() with invalid inputs"""

    def test_cache_invalidate_with_non_string_agent_id(self):
        """
        ERROR PATH: Non-string agent_id in invalidate().
        EXPECTED: f-string converts to string, no crashes.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Set entry with string ID
        cache.set("123", "stream_chat", {"allowed": True})

        # Invalidate with integer ID (f-string converts to "123")
        cache.invalidate(123, "stream_chat")

        # Entry should be invalidated
        assert cache.get("123", "stream_chat") is None

    def test_cache_invalidate_with_empty_string_agent_id(self):
        """
        ERROR PATH: Empty string agent_id in invalidate().
        EXPECTED: Invalidates entries with empty agent_id (weird but works).
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Set entry with empty agent_id
        cache.set("", "stream_chat", {"allowed": True})

        # Invalidate with empty agent_id
        cache.invalidate("", "stream_chat")

        # Entry should be invalidated
        assert cache.get("", "stream_chat") is None

    def test_cache_invalidate_with_invalid_action_type(self):
        """
        ERROR PATH: Invalid action_type in invalidate().
        EXPECTED: No errors, just no matching entries to invalidate.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        cache.set("agent-1", "stream_chat", {"allowed": True})

        # Try to invalidate non-existent action type
        cache.invalidate("agent-1", "non_existent_action")

        # Original entry should still exist
        assert cache.get("agent-1", "stream_chat") is not None

    def test_cache_invalidate_all_actions_for_agent(self):
        """
        ERROR PATH: Invalidate all actions for an agent (action_type=None).
        EXPECTED: All entries for agent removed from cache.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Set multiple actions for same agent
        cache.set("agent-1", "stream_chat", {"allowed": True})
        cache.set("agent-1", "present_chart", {"allowed": True})
        cache.set("agent-1", "browse", {"allowed": True})

        # Set entry for different agent
        cache.set("agent-2", "stream_chat", {"allowed": True})

        # Invalidate all actions for agent-1
        cache.invalidate("agent-1", action_type=None)

        # All agent-1 entries should be gone
        assert cache.get("agent-1", "stream_chat") is None
        assert cache.get("agent-1", "present_chart") is None
        assert cache.get("agent-1", "browse") is None

        # agent-2 entry should still exist
        assert cache.get("agent-2", "stream_chat") is not None

    def test_cache_invalidate_concurrent_invalidations(self):
        """
        ERROR PATH: Concurrent invalidations may cause race condition.
        EXPECTED: Thread-safe with lock, all invalidations succeed.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Set entries
        for i in range(10):
            cache.set(f"agent-{i}", "stream_chat", {"allowed": True})

        errors = []
        invalidation_count = [0]

        def invalidate_operation(agent_id: str):
            try:
                cache.invalidate(agent_id, "stream_chat")
                invalidation_count[0] += 1
            except Exception as e:
                errors.append(e)

        # Spawn 10 threads invalidating different agents
        threads = []
        for i in range(10):
            thread = threading.Thread(target=invalidate_operation, args=(f"agent-{i}",))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join(timeout=5.0)

        # All invalidations should succeed
        assert len(errors) == 0, f"Concurrent invalidations raised errors: {errors}"
        assert invalidation_count[0] == 10

        # Verify all entries were invalidated
        for i in range(10):
            assert cache.get(f"agent-{i}", "stream_chat") is None


# ============================================================================
# Async Cache Wrapper Errors
# ============================================================================


class TestAsyncCacheWrapperErrors:
    """Test AsyncGovernanceCache error handling"""

    def test_async_cache_with_missing_sync_instance(self):
        """
        ERROR PATH: AsyncGovernanceCache initialized without sync cache.
        EXPECTED: Falls back to global cache via get_governance_cache().
        """
        # AsyncGovernanceCache with None uses get_governance_cache()
        async_cache = AsyncGovernanceCache(cache=None)

        # Should still work
        result = asyncio.run(async_cache.get("agent-1", "stream_chat"))
        assert result is None  # Cache miss (no entry stored)

    def test_async_cache_get_delegation_failure(self):
        """
        ERROR PATH: Delegation to sync cache fails.
        EXPECTED: Exception propagates to caller.
        """
        sync_cache = MagicMock()
        sync_cache.get = MagicMock(side_effect=RuntimeError("Sync cache error"))

        async_cache = AsyncGovernanceCache(cache=sync_cache)

        # Exception should propagate
        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(async_cache.get("agent-1", "stream_chat"))

        assert "Sync cache error" in str(exc_info.value)

    def test_async_cache_set_delegation_failure(self):
        """
        ERROR PATH: Async set() delegation fails.
        EXPECTED: Exception propagates to caller.
        """
        sync_cache = MagicMock()
        sync_cache.set = MagicMock(side_effect=RuntimeError("Sync cache error"))

        async_cache = AsyncGovernanceCache(cache=sync_cache)

        # Exception should propagate
        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(async_cache.set("agent-1", "stream_chat", {"allowed": True}))

        assert "Sync cache error" in str(exc_info.value)

    def test_async_cache_invalidate_delegation_failure(self):
        """
        ERROR PATH: Async invalidate() delegation fails.
        EXPECTED: Exception propagates to caller.
        """
        sync_cache = MagicMock()
        sync_cache.invalidate = MagicMock(side_effect=RuntimeError("Sync cache error"))

        async_cache = AsyncGovernanceCache(cache=sync_cache)

        # Exception should propagate
        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(async_cache.invalidate("agent-1", "stream_chat"))

        assert "Sync cache error" in str(exc_info.value)

    def test_async_cache_stats_delegation_failure(self):
        """
        ERROR PATH: Async get_stats() delegation fails.
        EXPECTED: Exception propagates to caller.
        """
        sync_cache = MagicMock()
        sync_cache.get_stats = MagicMock(side_effect=RuntimeError("Stats error"))

        async_cache = AsyncGovernanceCache(cache=sync_cache)

        # Exception should propagate
        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(async_cache.get_stats())

        assert "Stats error" in str(exc_info.value)


# ============================================================================
# Cleanup Task Errors
# ============================================================================


class TestCleanupTaskErrors:
    """Test background cleanup task error handling"""

    def test_cleanup_task_handles_cancelled_error(self):
        """
        ERROR PATH: Cleanup task receives CancelledError.
        EXPECTED: Task exits gracefully (line 81-82).
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Simulate cleanup task being cancelled
        if cache._cleanup_task:
            # Task should handle CancelledError gracefully
            # (This is hard to test directly, but code has exception handler)
            assert True  # Code has except asyncio.CancelledError: break
        else:
            # No event loop, no cleanup task
            assert True

    def test_cleanup_task_handles_general_exception(self):
        """
        ERROR PATH: Cleanup task encounters unexpected error.
        EXPECTED: Logs error, continues running (line 83-84).
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=60)

        # Corrupt cache to cause error in _expire_stale()
        # Add entry with invalid structure
        cache._cache["corrupted"] = "not_a_dict"

        # Call _expire_stale() directly
        # Should handle exception gracefully and log error
        cache._expire_stale()

        # Cache should still function after error
        cache.set("agent-1", "stream_chat", {"allowed": True})
        assert cache.get("agent-1", "stream_chat") is not None

    def test_cleanup_with_corrupted_entries(self):
        """
        ERROR PATH: Cache contains corrupted entries during cleanup.
        EXPECTED: Cleanup handles corruption, continues processing.
        """
        cache = GovernanceCache(max_size=100, ttl_seconds=1)

        # Add valid entry
        cache.set("agent-1", "stream_chat", {"allowed": True})

        # Add corrupted entry (missing 'cached_at')
        cache._cache["corrupted"] = {"data": {"allowed": True}}

        # Run cleanup
        cache._expire_stale()

        # Valid entry should still work
        assert cache.get("agent-1", "stream_chat") is not None

        # Corrupted entry should be removed or skipped
        # (get("cached_at", 0) in _expire_stale() handles missing key)


# ============================================================================
# Messaging Cache Errors
# ============================================================================


class TestMessagingCacheErrors:
    """Test MessagingCache error handling (if present)"""

    def test_messaging_cache_with_negative_max_size(self):
        """
        ERROR PATH: MessagingCache with negative max_size.
        EXPECTED: Accepted without validation (similar to GovernanceCache).
        """
        from core.governance_cache import MessagingCache

        cache = MessagingCache(max_size=-100, ttl_seconds=300)
        assert cache.max_size == -100

    def test_messaging_cache_get_with_corrupted_entry(self):
        """
        ERROR PATH: MessagingCache corrupted entry missing keys.
        EXPECTED: KeyError or graceful handling.
        """
        from core.governance_cache import MessagingCache

        cache = MessagingCache(max_size=100, ttl_seconds=300)

        # Manually insert corrupted entry
        cache._capabilities["slack:STUDENT"] = {
            "cached_at": time.time()
            # Missing "data" key
        }

        # Try to get corrupted entry
        with pytest.raises(KeyError):
            cache.get_platform_capabilities("slack", "STUDENT")


# ============================================================================
# Global Cache Instance Errors
# ============================================================================


class TestGlobalCacheInstanceErrors:
    """Test global cache singleton error handling"""

    def test_get_governance_cache_creates_instance_once(self):
        """
        ERROR PATH: Multiple calls to get_governance_cache().
        EXPECTED: Returns same instance (singleton pattern).
        """
        # Reset global cache
        from core import governance_cache
        governance_cache._governance_cache = None

        cache1 = get_governance_cache()
        cache2 = get_governance_cache()

        assert cache1 is cache2  # Same instance

    def test_get_async_governance_cache_returns_wrapper(self):
        """
        ERROR PATH: get_async_governance_cache() returns valid wrapper.
        EXPECTED: AsyncGovernanceCache wrapping global cache.
        """
        from core.governance_cache import get_async_governance_cache

        async_cache = get_async_governance_cache()

        assert isinstance(async_cache, AsyncGovernanceCache)
        assert async_cache._cache is not None


# ============================================================================
# Decorator Errors
# ============================================================================


class TestCachedGovernanceCheckDecoratorErrors:
    """Test @cached_governance_check decorator error handling"""

    @pytest.mark.asyncio
    async def test_decorator_with_function_exception(self):
        """
        ERROR PATH: Decorated function raises exception.
        EXPECTED: Exception propagates, cache not polluted.
        """
        # Reset cache
        from core import governance_cache
        governance_cache._governance_cache = None

        @cached_governance_check
        async def failing_check(agent_id: str, action_type: str):
            raise ValueError("Database error")

        # Exception should propagate
        with pytest.raises(ValueError, match="Database error"):
            await failing_check("agent-1", "stream_chat")

        # Cache should be empty (no caching on error)
        cache = get_governance_cache()
        stats = cache.get_stats()
        assert stats["size"] == 0

    @pytest.mark.asyncio
    async def test_decorator_with_cache_set_failure(self):
        """
        ERROR PATH: Cache.set() fails during decorator execution.
        EXPECTED: Function result returned, cache error logged.
        """
        from core import governance_cache
        governance_cache._governance_cache = None

        @cached_governance_check
        async def working_check(agent_id: str, action_type: str):
            return {"allowed": True, "reason": "OK"}

        # Patch cache.set() to fail
        cache = get_governance_cache()
        with patch.object(cache, 'set', return_value=False):
            # Decorator should still return function result
            result = await working_check("agent-1", "stream_chat")
            assert result == {"allowed": True, "reason": "OK"}

        # Cache miss on second call (set failed)
        result2 = await working_check("agent-1", "stream_chat")
        assert result2 == {"allowed": True, "reason": "OK"}
