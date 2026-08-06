# -*- coding: utf-8 -*-
"""
Round 79 — gap coverage: core/debug_cache.py (thread-safe LRU+TTL insight cache;
zero test references before this file).

TDD targets (RED first):
- ``clear()`` claims to count invalidations but reads ``len(self._cache)``
  AFTER clearing — the counter is always 0 (stats lie about invalidations).
- Query caches are keyed by ``query:{hash(...)}`` — ``invalidate_component``
  prefix-matches ``query:{component_type}`` which can never match a hash key,
  so component invalidation silently never evicts query results.
- Baseline: get/set/TTL/LRU/stats/singleton behaviour.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from core.debug_cache import (
    DEBUG_CACHE_MAX_SIZE,
    DEBUG_CACHE_TTL_SECONDS,
    DebugInsightCache,
    get_debug_cache,
    init_debug_cache,
)


@pytest.fixture()
def cache():
    with patch.object(DebugInsightCache, "_start_cleanup_task"):
        c = DebugInsightCache(max_size=3, ttl_seconds=300)
        yield c


class TestBasics:
    def test_miss_returns_none(self, cache):
        assert cache.get("nope") is None

    def test_set_get_roundtrip(self, cache):
        cache.set("k", {"a": 1})
        assert cache.get("k") == {"a": 1}

    def test_get_updates_mru(self, cache):
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.get("a")  # 'a' becomes MRU
        cache.set("d", 4)  # evicts 'b' (LRU)
        assert cache.get("a") == 1
        assert cache.get("b") is None

    def test_lru_eviction(self, cache):
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)
        assert cache.get("a") is None
        assert cache.get_stats()["size"] == 3

    def test_delete_existing_and_missing(self, cache):
        cache.set("k", 1)
        assert cache.delete("k") is True
        assert cache.delete("k") is False

    def test_ttl_expiry_on_read(self, cache):
        cache.set("k", 1)
        with patch("core.debug_cache.time.time") as fake_time:
            fake_time.return_value = 1000.0
            cache.set("k", 1)
            fake_time.return_value = 1000.0 + cache.ttl_seconds + 1
            assert cache.get("k") is None

    def test_expire_stale_removes_old_entries(self, cache):
        with patch("core.debug_cache.time.time") as fake_time:
            fake_time.return_value = 1000.0
            cache.set("old", 1)
            fake_time.return_value = 2000.0
            cache.set("fresh", 2)
            cache._expire_stale()
            assert cache.get("old") is None
            assert cache.get("fresh") == 2

    def test_clear_empties_cache(self, cache):
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None
        assert cache.get_stats()["size"] == 0


class TestStats:
    def test_hit_and_miss_rates(self, cache):
        cache.set("k", 1)
        cache.get("k")
        cache.get("missing")
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    def test_lru_eviction_counts(self, cache):
        for i in range(4):
            cache.set(f"k{i}", i)
        assert cache.get_stats()["evictions"] == 1

    def test_invalidations_tracked_by_delete(self, cache):
        cache.set("k", 1)
        cache.delete("k")
        assert cache.get_stats()["invalidations"] == 1

    def test_clear_counts_invalidations(self, cache):
        """RED: clear() read len(self._cache) after clearing -> always 0."""
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get_stats()["invalidations"] == 2


class TestConvenience:
    def test_insight_roundtrip(self, cache):
        cache.set_insight("ins-1", {"title": "t"})
        assert cache.get_insight("ins-1") == {"title": "t"}

    def test_component_state_roundtrip_and_invalidate(self, cache):
        cache.set_component_state("agent", "agent-1", {"state": "idle"})
        assert cache.get_component_state("agent", "agent-1") == {"state": "idle"}
        cache.invalidate_component("agent", "agent-1")
        assert cache.get_component_state("agent", "agent-1") is None

    def test_query_roundtrip(self, cache):
        cache.set_insights_by_query([{"id": "i1"}], component_type="agent", component_id="agent-1")
        result = cache.get_insights_by_query(component_type="agent", component_id="agent-1")
        assert result == [{"id": "i1"}]

    def test_invalidate_component_clears_query_cache(self, cache):
        """RED: hash-keyed query entries could not be prefix-matched."""
        cache.set_insights_by_query(
            [{"id": "i1"}], component_type="agent", component_id="agent-1", severity="error"
        )
        assert cache.get_insights_by_query(
            component_type="agent", component_id="agent-1", severity="error"
        ) == [{"id": "i1"}]
        cache.invalidate_component("agent", "agent-1")
        assert cache.get_insights_by_query(
            component_type="agent", component_id="agent-1", severity="error"
        ) is None

    def test_invalidate_component_preserves_other_components(self, cache):
        cache.set_insights_by_query([{"id": "i1"}], component_type="agent", component_id="agent-1")
        cache.set_insights_by_query([{"id": "i2"}], component_type="browser", component_id="page-1")
        cache.invalidate_component("agent", "agent-1")
        assert cache.get_insights_by_query(component_type="browser", component_id="page-1") == [
            {"id": "i2"}
        ]


class TestSingleton:
    def test_get_debug_cache_singleton(self):
        assert get_debug_cache() is get_debug_cache()
        assert isinstance(get_debug_cache(), DebugInsightCache)

    def test_init_debug_cache_configures_singleton(self):
        assert init_debug_cache(max_size=5, ttl_seconds=60) is get_debug_cache()

    def test_defaults_from_env(self):
        assert isinstance(DEBUG_CACHE_MAX_SIZE, int)
        assert isinstance(DEBUG_CACHE_TTL_SECONDS, int)
        assert DEBUG_CACHE_TTL_SECONDS > 0
