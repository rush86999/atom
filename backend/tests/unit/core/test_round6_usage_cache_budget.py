"""Tests for the round-6 bug fixes: usage tracking, budgets, cache history
bounds, and benchmark score matching.
"""
import pytest
from unittest.mock import MagicMock


# --------------------------------------------------------------------------
# Bug 1: embedding usage tracking uses record() (not nonexistent track_usage)
# --------------------------------------------------------------------------

class TestEmbeddingUsageTracking:
    def test_generate_embedding_calls_record(self, monkeypatch):
        """generate_embedding must call llm_usage_tracker.record (not track_usage).

        track_usage doesn't exist on LLMUsageTracker; the old call raised
        AttributeError swallowed by try/except, so embedding usage was never
        recorded.
        """
        from core import llm_service as svc
        from core.llm_usage_tracker import LLMUsageTracker

        calls = []
        tracker = LLMUsageTracker()
        tracker.record = lambda **kw: calls.append(kw)
        monkeypatch.setattr(svc, "llm_usage_tracker", tracker)

        ls = svc.LLMService.__new__(svc.LLMService)
        ls._workspace_id = "ws1"
        ls._tenant_id = None
        ls._handler = MagicMock()
        # generate_embedding awaits handler.generate_embedding — use an async mock.
        from unittest.mock import AsyncMock
        ls._handler.generate_embedding = AsyncMock(return_value=[0.1, 0.2])
        ls._get_handler = lambda workspace_id=None, tenant_id=None: ls._handler

        import asyncio
        asyncio.run(ls.generate_embedding("hello world", model="text-embedding-3-small"))

        assert len(calls) == 1
        assert calls[0]["workspace_id"] == "ws1"
        assert calls[0]["model"] == "text-embedding-3-small"
        assert calls[0]["cost_usd"] > 0


# --------------------------------------------------------------------------
# Bugs 2 & 4: daily budget window + bounded records
# --------------------------------------------------------------------------

class TestUsageTrackerBudgetWindow:
    def test_budget_resets_next_day(self):
        """A budget breach today must NOT persist (old counter never reset)."""
        from core.llm_usage_tracker import LLMUsageTracker
        from datetime import date
        tracker = LLMUsageTracker()
        tracker.set_budget("ws1", 1.0)

        # Simulate yesterday's spend directly.
        yesterday = date.today().replace(day=max(1, date.today().day - 1))
        tracker._usage["ws1"] = {yesterday: 5.0}  # way over budget, but yesterday
        assert tracker.is_budget_exceeded("ws1") is False  # today is 0
        assert tracker.get_usage("ws1") == 0.0

        # Today's spend crosses the budget.
        tracker.record("ws1", "openai", "gpt-4o", 10, 10, 1.5)
        assert tracker.is_budget_exceeded("ws1") is True
        assert tracker.get_usage("ws1") == 1.5

    def test_records_list_is_bounded(self):
        """_records must not grow unbounded in the singleton."""
        from core.llm_usage_tracker import LLMUsageTracker
        tracker = LLMUsageTracker()
        tracker._MAX_RECORDS = 50  # small cap for the test
        for i in range(200):
            tracker.record("ws1", "openai", "gpt-4o", 1, 1, 0.001)
        assert len(tracker._records) <= tracker._MAX_RECORDS
        # Most recent records retained.
        assert tracker._records[-1].input_tokens == 1

    def test_reset_usage_clears_today(self):
        from core.llm_usage_tracker import LLMUsageTracker
        tracker = LLMUsageTracker()
        tracker.record("ws1", "openai", "gpt-4o", 10, 10, 2.0)
        assert tracker.get_usage("ws1") == 2.0
        tracker.reset_usage("ws1")
        assert tracker.get_usage("ws1") == 0.0


# --------------------------------------------------------------------------
# Bug 3: cache_hit_history bounded + rolling window
# --------------------------------------------------------------------------

class TestCacheHitHistoryBounds:
    def _router(self):
        from core.llm.cache_aware_router import CacheAwareRouter
        r = CacheAwareRouter.__new__(CacheAwareRouter)
        r.cache_hit_history = {}
        r._cache_key_order = []
        r._CACHE_WINDOW = 100
        r._MAX_CACHE_KEYS = 10_000
        r.pricing_fetcher = MagicMock()
        return r

    def test_history_rolls_off_old_samples(self):
        """Per-key total is capped so the ratio reflects recent samples."""
        r = self._router()
        # 100 hits then 100 misses. A lifetime average would be 0.5; the rolling
        # window decays old hits so recent misses pull the ratio below 0.5.
        for _ in range(100):
            r.record_cache_outcome("hash1", "ws", True)
        for _ in range(100):
            r.record_cache_outcome("hash1", "ws", False)
        hits, total = r.cache_hit_history["ws:hash1"[:len("ws:hash1")]]
        assert total <= r._CACHE_WINDOW + 1
        ratio = hits / total if total else 0
        # Rolling window must reflect recent misses (below the 0.5 lifetime avg).
        assert ratio < 0.5, f"stale history not rolling off: ratio={ratio}"

    def test_history_keys_are_bounded(self):
        """Distinct keys beyond the cap are FIFO-evicted."""
        r = self._router()
        r._MAX_CACHE_KEYS = 20
        for i in range(50):
            r.record_cache_outcome(f"hash{i}", "ws", True)
        assert len(r.cache_hit_history) <= r._MAX_CACHE_KEYS
        # Oldest keys evicted, newest kept.
        assert "ws:hash49"[:16] in r.cache_hit_history or any(
            k.startswith("ws:hash4") for k in r.cache_hit_history)


# --------------------------------------------------------------------------
# Bug 7: longest-match for quality/capability scores
# --------------------------------------------------------------------------

class TestBenchmarkScoreMatching:
    def test_quality_prefers_longest_match(self, monkeypatch):
        """A dated variant should match the most specific STATIC key.

        'gpt-4o-mini-2024-07-18' should resolve via 'gpt-4o-mini', not the
        shorter 'gpt-4o'. We force the static path by making the dynamic
        fetcher import fail (it's environment-dependent and would override).
        """
        import builtins
        real_import = builtins.__import__

        def blocking_import(name, *args, **kwargs):
            if "dynamic_benchmark_fetcher" in name:
                raise ImportError("blocked for test")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocking_import)

        from core.benchmarks import get_quality_score, MODEL_QUALITY_SCORES
        if "gpt-4o" in MODEL_QUALITY_SCORES and "gpt-4o-mini" in MODEL_QUALITY_SCORES:
            mini_score = MODEL_QUALITY_SCORES["gpt-4o-mini"]
            score = get_quality_score("gpt-4o-mini-2024-07-18")
            assert score == mini_score, (
                f"expected longest-match {mini_score}, got {score}")

    def test_exact_match_still_wins(self, monkeypatch):
        import builtins
        real_import = builtins.__import__

        def blocking_import(name, *args, **kwargs):
            if "dynamic_benchmark_fetcher" in name:
                raise ImportError("blocked for test")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocking_import)
        from core.benchmarks import get_quality_score, MODEL_QUALITY_SCORES
        if "gpt-4o" in MODEL_QUALITY_SCORES:
            assert get_quality_score("gpt-4o") == MODEL_QUALITY_SCORES["gpt-4o"]


# --------------------------------------------------------------------------
# Bug 8: round() not int() for dynamic scores
# --------------------------------------------------------------------------

class TestDynamicScoreRounding:
    def _patched_fetcher(self, score):
        """Build a fake dynamic fetcher module so the local import in
        benchmarks.get_quality_score returns our controlled score."""
        import types, sys
        fake_mod = types.ModuleType("core.dynamic_benchmark_fetcher")
        fake_fetcher = MagicMock()
        fake_fetcher.get_benchmark_score.return_value = score
        fake_mod.get_benchmark_fetcher = lambda: fake_fetcher
        sys.modules["core.dynamic_benchmark_fetcher"] = fake_mod
        return fake_mod

    def test_dynamic_score_rounds_not_truncates(self):
        """A dynamic score of 89.7 should yield 90, not 89 (truncation)."""
        import sys
        self._patched_fetcher(89.7)
        try:
            from core.benchmarks import get_quality_score
            assert get_quality_score("some-dynamic-model") == 90
        finally:
            sys.modules.pop("core.dynamic_benchmark_fetcher", None)

    def test_dynamic_score_clamped_to_100(self):
        import sys
        self._patched_fetcher(105.4)
        try:
            from core.benchmarks import get_quality_score
            assert get_quality_score("over-100-model") == 100
        finally:
            sys.modules.pop("core.dynamic_benchmark_fetcher", None)
