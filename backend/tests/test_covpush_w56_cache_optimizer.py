"""Coverage wave 56 — core/llm/routing/cache_optimizer.py (69% → 90%+).

CacheStatistics update, AccessPatternAnalyzer (pattern cache hit, short
history, temporal/sequential/random detection, frequency window, next-access
probability), CacheWarmer (should_warm probability/frequency paths, warm
candidates filtering+sorting), CacheOptimizer (record_access, recommendations
hit-rate low/high + dynamic sizing min/max, optimal cache size incl. empty
and target-reaching), factories.
"""
from collections import deque
from datetime import datetime, timedelta

import pytest

from core.llm.routing.cache_optimizer import (
    AccessPattern,
    AccessPatternAnalyzer,
    CacheOptimizer,
    CacheStatistics,
    CacheWarmer,
    get_cache_optimizer,
    get_cache_warmer,
    get_pattern_analyzer,
)


class TestStatistics:
    def test_update_hits_and_misses(self):
        stats = CacheStatistics()
        stats.update(True, 10)
        stats.update(False, 50)
        stats.update(True, 20)
        assert stats.total_accesses == 3
        assert stats.hit_rate == pytest.approx(2 / 3)
        assert stats.avg_latency_ms == pytest.approx((10 + 50 + 20) / 3)


class TestPatternAnalyzer:
    def _ts(self, minutes_ago):
        return datetime.now() - timedelta(minutes=minutes_ago)

    def test_short_history_random(self):
        a = AccessPatternAnalyzer()
        a.record_access("h", self._ts(10))
        a.record_access("h", self._ts(9))
        assert a.detect_pattern("h") == AccessPattern.RANDOM

    def test_pattern_cache_hit(self):
        a = AccessPatternAnalyzer()
        a.pattern_cache["h"] = AccessPattern.TEMPORAL
        assert a.detect_pattern("h") == AccessPattern.TEMPORAL

    def test_temporal_regular_gaps(self):
        a = AccessPatternAnalyzer()
        for i in range(5):
            a.record_access("h", self._ts(i * 5))  # 5-min gaps, low variance
        assert a.detect_pattern("h") == AccessPattern.TEMPORAL

    def test_sequential_fast_accesses(self):
        a = AccessPatternAnalyzer()
        for i in range(5):
            a.record_access("h", self._ts(i))  # 1-min gaps
        # gap variance 0 < 60 -> TEMPORAL wins; force sequential path
        a2 = AccessPatternAnalyzer()
        a2.access_history["h"] = deque([
            self._ts(0), self._ts(1), self._ts(2), self._ts(3), self._ts(4),
        ])
        assert a2._is_sequential(list(a2.access_history["h"])) is True

    def test_frequency_window(self):
        a = AccessPatternAnalyzer()
        a.record_access("h", self._ts(5))
        a.record_access("h", self._ts(59))
        freq = a.get_access_frequency("h", window_minutes=60)
        assert freq == pytest.approx(2 / 60)

    def test_next_access_probability_boost(self):
        a = AccessPatternAnalyzer()
        for i in range(5):
            a.record_access("h", self._ts(i * 5))
        prob = a.get_next_access_probability("h")
        assert 0 <= prob <= 1.0


class TestCacheWarmer:
    def test_should_warm_high_probability(self):
        w = CacheWarmer()
        assert w.should_warm("h", 0.9) is True
        assert w.should_warm("h", 0.5) is False

    def test_should_warm_frequency_path(self):
        w = CacheWarmer()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(w.analyzer, "get_access_frequency", lambda h, wm: 2.0)
            assert w.should_warm("h", 0.1) is True

    def test_warm_candidates_filter_and_sort(self):
        from core.llm.routing.cache_optimizer import WarmedCacheEntry
        w = CacheWarmer()
        w.warmed_entries["low"] = WarmedCacheEntry(
            prompt_hash="low", access_probability=0.1)
        w.warmed_entries["high"] = WarmedCacheEntry(
            prompt_hash="high", access_probability=0.9)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(w.analyzer, "get_next_access_probability",
                       lambda h: 0.9 if h == "high" else 0.1)
            candidates = w.get_warm_candidates("ws1")
        assert [c.prompt_hash for c in candidates] == ["high"]
        assert candidates[0].access_probability == 0.9


class TestCacheOptimizer:
    def test_record_access_tracks_all(self):
        co = CacheOptimizer()
        co.record_access("h1", True, 10, "m1", "p1")
        co.record_access("h1", False, 40, "m1", "p1")
        assert co.statistics.total_accesses == 2
        assert len(co.accesses) == 2

    def test_recommendations_low_hit_rate(self):
        co = CacheOptimizer()
        for _ in range(5):
            co.record_access("h", False, 20)
        recs = co.get_cache_recommendations("ws1", 10.0)
        assert any(r["type"] == "hit_rate" and r["severity"] == "warning"
                   for r in recs["recommendations"])

    def test_recommendations_high_hit_rate(self):
        co = CacheOptimizer()
        for _ in range(50):
            co.record_access("h", True, 5)
        recs = co.get_cache_recommendations("ws1", 10.0)
        assert any(r["type"] == "hit_rate" and r["severity"] == "info"
                   for r in recs["recommendations"])

    def test_recommendations_size_below_min(self):
        co = CacheOptimizer()
        co.record_access("h", True, 5)
        recs = co.get_cache_recommendations("ws1", 0.5)
        assert any(r["type"] == "cache_size" and "below minimum" in r["message"]
                   for r in recs["recommendations"])

    def test_recommendations_size_above_max(self):
        co = CacheOptimizer()
        co.record_access("h", True, 5)
        recs = co.get_cache_recommendations("ws1", 9999.0)
        assert any(r["type"] == "cache_size" and "exceeds maximum" in r["message"]
                   for r in recs["recommendations"])

    def test_recommendations_dynamic_sizing_disabled(self):
        co = CacheOptimizer()
        co.config.enable_dynamic_sizing = False
        co.record_access("h", True, 5)
        recs = co.get_cache_recommendations("ws1", 0.5)
        assert not any(r["type"] == "cache_size" for r in recs["recommendations"])

    def test_optimal_cache_size_empty(self):
        co = CacheOptimizer()
        assert co.get_optimal_cache_size() == co.config.min_cache_size_mb

    def test_optimal_cache_size_target_reached(self):
        co = CacheOptimizer()
        for _ in range(80):
            co.record_access("hot", True)
        for _ in range(20):
            co.record_access("cold", True)
        size = co.get_optimal_cache_size(target_hit_rate=0.95)
        assert size >= co.config.min_cache_size_mb

    def test_factories(self):
        assert isinstance(get_cache_optimizer(), CacheOptimizer)
        assert isinstance(get_cache_warmer(), CacheWarmer)
        assert isinstance(get_pattern_analyzer(), AccessPatternAnalyzer)
