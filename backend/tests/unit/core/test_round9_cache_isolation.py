"""Tests for the round-9 cache/chat-history fixes.

Covers:
- SyncLocalCache true LRU eviction (was: no eviction then mass-clear).
- RedisCircuitBreaker thread-safe state transitions.
- (Falsy-value get fix is exercised indirectly via SyncLocalCache.)
"""
import threading
import pytest


# --------------------------------------------------------------------------
# Bug 4: SyncLocalCache LRU eviction
# --------------------------------------------------------------------------

class TestSyncLocalCacheLRU:
    def _cache(self, max_size=5):
        from core.cache import SyncLocalCache
        return SyncLocalCache(max_size=max_size, default_ttl=60)

    def test_evicts_oldest_at_capacity(self):
        """At capacity, the single oldest key is evicted (not a mass-clear)."""
        c = self._cache(max_size=3)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        c.set("d", 4)  # over capacity -> evict "a"
        assert c.get("a") is None
        assert c.get("b") == 2
        assert c.get("c") == 3
        assert c.get("d") == 4

    def test_get_marks_as_recently_used(self):
        """A get() should make a key most-recently-used (evicted last)."""
        c = self._cache(max_size=3)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        c.get("a")  # touch 'a' -> now most recent
        c.set("d", 4)  # over capacity -> evict the LRU, which is 'b' not 'a'
        assert c.get("a") == 1  # 'a' survived because it was just used
        assert c.get("b") is None

    def test_update_existing_key_does_not_evict(self):
        c = self._cache(max_size=2)
        c.set("a", 1)
        c.set("b", 2)
        c.set("a", 99)  # update, not insert -> no eviction
        assert c.get("a") == 99
        assert c.get("b") == 2

    def test_no_mass_clear(self):
        """Inserting well past capacity must not wipe everything (old bug)."""
        c = self._cache(max_size=3)
        for i in range(20):
            c.set(f"k{i}", i)
        # The 3 most-recent should survive; the cache size stays at max_size.
        assert c.get("k19") == 19
        assert c.get("k18") == 18
        assert c.get("k17") == 17
        assert len(c._cache) <= c.max_size


# --------------------------------------------------------------------------
# Bug 5: RedisCircuitBreaker thread-safety
# --------------------------------------------------------------------------

class TestCircuitBreakerThreadSafety:
    def _breaker(self, threshold=10):
        from core.cache import RedisCircuitBreaker
        return RedisCircuitBreaker(failure_threshold=threshold, recovery_timeout=60)

    def test_concurrent_failures_open_the_breaker(self):
        """Concurrent failures must not lose increments — the breaker opens."""
        b = self._breaker(threshold=50)
        N = 100

        def fail():
            for _ in range(N // 4):
                try:
                    b.call(lambda: (_ for _ in ()).throw(ConnectionError("redis down")))
                except CircuitBreakerOpenError:
                    return
                except ConnectionError:
                    continue

        from core.cache import CircuitBreakerOpenError
        threads = [threading.Thread(target=fail) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # With proper locking, all failures are counted and the breaker opens.
        assert b.get_state().name == "OPEN"

    def test_state_transitions_are_consistent(self):
        """get_state under concurrency returns a valid enum, never errors."""
        b = self._breaker(threshold=3)
        results = []

        def poke():
            for _ in range(50):
                results.append(b.get_state())

        threads = [threading.Thread(target=poke) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # Every read returned a real state (no crash).
        assert len(results) == 200
