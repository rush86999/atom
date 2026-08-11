"""Coverage wave 35 — core/llm/cache_aware_router.py (17% → 90%+).

Drives the full cache-aware cost math: deterministic turn-based mode,
probabilistic mode with explicit/predicted/default probabilities and clamping,
no-pricing infinity, provider capability resolution (direct/fuzzy/default),
cache-hit history recording with rolling-window scaling + FIFO eviction,
analytics views with defensive copies, and workspace-scoped clearing.
"""
import asyncio
from unittest.mock import Mock, patch

import pytest

from core.llm.cache_aware_router import CacheAwareRouter


@pytest.fixture
def router():
    fetcher = Mock()
    return CacheAwareRouter(fetcher)


def _price(input_cost=10.0, output_cost=20.0):
    return {"input_cost_per_token": input_cost, "output_cost_per_token": output_cost}


def await_value(result):
    return asyncio.get_event_loop().run_until_complete(asyncio.ensure_future(result))


class TestCalculateEffectiveCost:
    def test_no_pricing_returns_infinity(self, router):
        router.pricing_fetcher.get_model_price.return_value = None
        assert await_value(router.calculate_effective_cost("m", "openai", 500)) == float("inf")

    def test_deterministic_turn_mode_uses_cached_ratio(self, router):
        router.pricing_fetcher.get_model_price.return_value = _price()
        cost = await_value(router.calculate_effective_cost(
            "m", "openai", 2000, turn_index=2))
        assert cost == pytest.approx((10.0 * 0.10 + 20.0) / 2)

    def test_probabilistic_explicit_probability(self, router):
        router.pricing_fetcher.get_model_price.return_value = _price()
        cost = await_value(router.calculate_effective_cost(
            "m", "openai", 2000, cache_hit_probability=0.5))
        # discounted = 0.5*0.10 + 0.5 = 0.55
        assert cost == pytest.approx((10.0 * 0.55 + 20.0) / 2)

    def test_probability_clamped_above_and_below(self, router):
        router.pricing_fetcher.get_model_price.return_value = _price()
        cost_hi = await_value(router.calculate_effective_cost(
            "m", "openai", 2000, cache_hit_probability=2.0))
        cost_lo = await_value(router.calculate_effective_cost(
            "m", "openai", 2000, cache_hit_probability=-1.0))
        assert cost_hi == pytest.approx((10.0 * 0.10 + 20.0) / 2)
        assert cost_lo == pytest.approx((10.0 * 1.0 + 20.0) / 2)

    def test_probability_predicted_from_history(self, router):
        router.pricing_fetcher.get_model_price.return_value = _price()
        router.cache_hit_history["default:abcd1234efgh5678"] = [8, 10]
        with patch.object(router, "predict_cache_hit_probability", wraps=router.predict_cache_hit_probability) as pred:
            cost = await_value(router.calculate_effective_cost(
                "m", "openai", 2000, prompt_hash="abcd1234efgh5678"))
            pred.assert_called_once()
        assert cost == pytest.approx((10.0 * (0.8 * 0.10 + 0.2) + 20.0) / 2)

    def test_probability_defaults_to_half(self, router):
        router.pricing_fetcher.get_model_price.return_value = _price()
        cost = await_value(router.calculate_effective_cost(
            "m", "openai", 2000))
        assert cost == pytest.approx((10.0 * 0.55 + 20.0) / 2)

    def test_below_min_tokens_full_price(self, router):
        router.pricing_fetcher.get_model_price.return_value = _price()
        cost = await_value(router.calculate_effective_cost(
            "m", "openai", 100, turn_index=5))
        assert cost == pytest.approx((10.0 + 20.0) / 2)

    def test_no_cache_provider_full_price(self, router):
        router.pricing_fetcher.get_model_price.return_value = _price()
        cost = await_value(router.calculate_effective_cost(
            "m", "deepseek", 5000, cache_hit_probability=0.9))
        assert cost == pytest.approx((10.0 + 20.0) / 2)


class TestPredictAndRecord:
    def test_predict_no_history_returns_default(self, router):
        assert router.predict_cache_hit_probability("abc", "default") == 0.5

    def test_predict_uses_history(self, router):
        router.cache_hit_history["default:abcd1234efgh5678"] = [7, 10]
        assert router.predict_cache_hit_probability("abcd1234efgh5678", "default") == 0.7

    def test_predict_zero_total_returns_default(self, router):
        router.cache_hit_history["default:abcd1234efgh5678"] = [0, 0]
        assert router.predict_cache_hit_probability("abcd1234efgh5678", "default") == 0.5

    def test_predict_key_truncated_to_16_chars(self, router):
        router.cache_hit_history["default:abcd1234efgh5678"] = [1, 2]
        # different suffix, same first 16 chars → same bucket
        assert router.predict_cache_hit_probability("abcd1234efgh5678ZZZZ", "default") == 0.5

    def test_record_new_key(self, router):
        router.record_cache_outcome("abc123", "default", True)
        assert router.cache_hit_history["default:abc123"] == [1, 1]

    def test_record_miss_new_key(self, router):
        router.record_cache_outcome("abc123", "default", False)
        assert router.cache_hit_history["default:abc123"] == [0, 1]

    def test_record_accumulates(self, router):
        router.record_cache_outcome("abc123", "default", True)
        router.record_cache_outcome("abc123", "default", False)
        assert router.cache_hit_history["default:abc123"] == [1, 2]

    def test_record_rolling_window_scales(self, router):
        router._CACHE_WINDOW = 100
        for _ in range(150):
            router.record_cache_outcome("abc123", "default", True)
        hits, total = router.cache_hit_history["default:abc123"]
        assert total == 100  # capped at window
        assert 0 < hits <= 100
        # ratio still ~1.0 for all-hit stream
        assert hits / total > 0.95

    def test_record_fifo_eviction(self, router):
        router._MAX_CACHE_KEYS = 5
        for i in range(7):
            router.record_cache_outcome(f"prompt{i}", "w", True)
        assert len(router.cache_hit_history) == 5
        assert "w:prompt0" not in router.cache_hit_history
        assert "w:prompt1" not in router.cache_hit_history
        assert "w:prompt2" in router.cache_hit_history
        assert "w:prompt6" in router.cache_hit_history
        assert len(router._cache_key_order) == 5


class TestProviderCapability:
    def test_direct_match(self, router):
        assert router.get_provider_cache_capability("anthropic")["min_tokens"] == 2048

    def test_case_insensitive(self, router):
        assert router.get_provider_cache_capability("OpenAI")["supports_cache"] is True

    def test_google_fuzzy_matches_gemini(self, router):
        caps = router.get_provider_cache_capability("google")
        assert caps["supports_cache"] is True
        assert caps["min_tokens"] == 1024

    def test_gemini_name_matches(self, router):
        assert router.get_provider_cache_capability("gemini")["supports_cache"] is True

    def test_unknown_provider_defaults_no_cache(self, router):
        caps = router.get_provider_cache_capability("unknown-xyz")
        assert caps == {
            "supports_cache": False,
            "cached_cost_ratio": 1.0,
            "min_tokens": 0,
        }


class TestHistoryViewsAndClear:
    def test_history_filtered_by_workspace(self, router):
        router.cache_hit_history["w1:aaa"] = [1, 1]
        router.cache_hit_history["w2:bbb"] = [2, 2]
        assert set(router.get_cache_hit_history("w1")) == {"w1:aaa"}

    def test_history_all_when_no_workspace(self, router):
        router.cache_hit_history["w1:aaa"] = [1, 1]
        router.cache_hit_history["w2:bbb"] = [2, 2]
        assert len(router.get_cache_hit_history()) == 2

    def test_history_defensive_copy(self, router):
        router.cache_hit_history["w1:aaa"] = [1, 1]
        view = router.get_cache_hit_history("w1")
        view["w1:aaa"][0] = 999
        assert router.cache_hit_history["w1:aaa"] == [1, 1]

    def test_clear_workspace_scoped(self, router):
        router.cache_hit_history["w1:aaa"] = [1, 1]
        router.cache_hit_history["w1:bbb"] = [1, 1]
        router.cache_hit_history["w2:ccc"] = [1, 1]
        router._cache_key_order = ["w1:aaa", "w1:bbb", "w2:ccc"]
        router.clear_cache_history("w1")
        assert router.cache_hit_history == {"w2:ccc": [1, 1]}
        assert router._cache_key_order == ["w2:ccc"]

    def test_clear_all(self, router):
        router.cache_hit_history["w1:aaa"] = [1, 1]
        router._cache_key_order = ["w1:aaa"]
        router.clear_cache_history()
        assert router.cache_hit_history == {}
        assert router._cache_key_order == []
