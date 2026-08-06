"""
OpenCode Go Provider Tests

Tests for the OpenCode Go (OpenCode Zen gateway) BYOK provider integration:

- Provider registration (client init via OPENCODE_API_KEY)
- Model recommendations / provider tiers
- Static fallback + BPC ranking inclusion
- Custom rates & limits (RPM/TPM/context) feeding routing decisions
- ProviderRateTracker sliding-window headroom semantics
- fetch_opencode_pricing static fallback
"""

import os
os.environ["TESTING"] = "1"

import pytest
from unittest.mock import Mock, patch

from core.llm.byok_handler import BYOKHandler, QueryComplexity, PROVIDER_TIERS, COST_EFFICIENT_MODELS
from core.llm.provider_rate_limits import (
    PROVIDER_RATE_LIMITS,
    ProviderRateTracker,
    get_provider_rate_tracker,
)
from core.dynamic_pricing_fetcher import DynamicPricingFetcher


@pytest.fixture
def mock_byok_manager():
    manager = Mock()
    manager.is_configured.return_value = False
    manager.get_api_key.return_value = None
    return manager


@pytest.fixture
def byok_handler(mock_byok_manager):
    """BYOKHandler with all real clients stubbed out."""
    with patch("core.llm.byok_handler.get_byok_manager", return_value=mock_byok_manager), \
         patch("core.llm.byok_handler.get_db_session", return_value=Mock()):
        handler = BYOKHandler()
        return handler


# ============================================================================
# Provider registration
# ============================================================================

class TestOpenCodeGoRegistration:
    def test_provider_in_tiers(self):
        assert "opencode-go" in PROVIDER_TIERS["budget"]
        assert "opencode-go" in PROVIDER_TIERS["code"]

    def test_cost_efficient_models_per_complexity(self):
        models = COST_EFFICIENT_MODELS["opencode-go"]
        assert models[QueryComplexity.SIMPLE] == "deepseek-v4-flash"
        assert models[QueryComplexity.MODERATE] == "deepseek-v4-flash"
        assert models[QueryComplexity.COMPLEX] == "deepseek-v4-pro"
        assert models[QueryComplexity.ADVANCED] == "kimi-k2.7-code"

    def test_custom_limits_registered(self):
        limits = PROVIDER_RATE_LIMITS["opencode-go"]
        assert limits["rpm"] > 0
        assert limits["tpm"] > 0
        assert limits["max_context"] > 0

    def test_client_initialized_with_env_key(self, mock_byok_manager, monkeypatch):
        monkeypatch.setenv("OPENCODE_API_KEY", "sk-opencode-test")
        monkeypatch.delenv("OPENCODE_BASE_URL", raising=False)
        with patch("core.llm.byok_handler.get_byok_manager", return_value=mock_byok_manager), \
             patch("core.llm.byok_handler.get_db_session", return_value=Mock()), \
             patch("core.llm.byok_handler.OpenAI") as mock_openai, \
             patch("core.llm.byok_handler.AsyncOpenAI") as mock_async_openai:
            handler = BYOKHandler()
            assert "opencode-go" in handler.clients
            kwargs = mock_openai.call_args.kwargs
            assert kwargs["api_key"] == "sk-opencode-test"
            assert kwargs["base_url"] == "https://opencode.ai/zen/v1"

    def test_no_client_without_key(self, mock_byok_manager, monkeypatch):
        monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
        with patch("core.llm.byok_handler.get_byok_manager", return_value=mock_byok_manager), \
             patch("core.llm.byok_handler.get_db_session", return_value=Mock()), \
             patch("core.llm.byok_handler.OpenAI") as mock_openai, \
             patch("core.llm.byok_handler.AsyncOpenAI"):
            handler = BYOKHandler()
            assert "opencode-go" not in handler.clients
            openai_calls = [c for c in mock_openai.call_args_list if c.kwargs.get("base_url") == "https://opencode.ai/zen/v1"]
            assert openai_calls == []

    def test_provider_serves_any_gateway_model(self, byok_handler):
        assert byok_handler._provider_serves_model("opencode-go", "deepseek-v4-flash")
        assert byok_handler._provider_serves_model("opencode-go", "kimi-k2.7-code")

    def test_fallback_order_includes_opencode(self, byok_handler):
        byok_handler.clients = {"opencode-go": Mock(), "deepseek": Mock(), "openai": Mock()}
        order = byok_handler._get_provider_fallback_order("opencode-go")
        assert order[0] == "opencode-go"
        assert "opencode-go" in order


# ============================================================================
# Routing
# ============================================================================

class TestOpenCodeGoRouting:
    def _fetcher_with_opencode_models(self):
        fetcher = DynamicPricingFetcher()
        fetcher.pricing_cache = {
            "deepseek-v4-flash": {
                "litellm_provider": "opencode-go",
                "input_cost_per_token": 0.14 / 1e6,
                "output_cost_per_token": 0.28 / 1e6,
                "max_input_tokens": 200000,
                "supports_tools": True,
                "supports_vision": False,
                "supports_reasoning": False,
            },
        }
        return fetcher

    def test_bpc_ranks_opencode_go(self, byok_handler):
        byok_handler.clients = {"opencode-go": Mock()}
        fetcher = self._fetcher_with_opencode_models()
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync", return_value=fetcher):
            ranked = byok_handler.get_ranked_providers(
                QueryComplexity.SIMPLE, is_managed_service=False
            )
        assert ranked == [("opencode-go", "deepseek-v4-flash")]

    def test_static_fallback_uses_opencode_models(self, byok_handler):
        byok_handler.clients = {"opencode-go": Mock()}
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   side_effect=RuntimeError("no cache")):
            ranked = byok_handler.get_ranked_providers(
                QueryComplexity.COMPLEX, is_managed_service=False
            )
        assert ("opencode-go", "deepseek-v4-pro") in ranked

    def test_static_fallback_advanced_uses_code_model(self, byok_handler):
        byok_handler.clients = {"opencode-go": Mock()}
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   side_effect=RuntimeError("no cache")):
            ranked = byok_handler.get_ranked_providers(
                QueryComplexity.ADVANCED, is_managed_service=False
            )
        assert ("opencode-go", "kimi-k2.7-code") in ranked


# ============================================================================
# Custom rates & limits → routing decisions
# ============================================================================

class TestOpenCodeGoRateAwareRouting:
    def _fresh_tracker(self):
        tracker = ProviderRateTracker()
        tracker.set_rate_limits("opencode-go", rpm=60, tpm=2_000_000, max_context=200000)
        return tracker

    def _fetcher(self, context: int = 200000):
        fetcher = DynamicPricingFetcher()
        fetcher.pricing_cache = {
            "deepseek-v4-flash": {
                "litellm_provider": "opencode-go",
                "input_cost_per_token": 0.14 / 1e6,
                "output_cost_per_token": 0.28 / 1e6,
                "max_input_tokens": context,
                "supports_tools": True,
                "supports_vision": False,
                "supports_reasoning": False,
            },
            "deepseek-chat": {
                "litellm_provider": "deepseek",
                "input_cost_per_token": 0.27 / 1e6,
                "output_cost_per_token": 1.10 / 1e6,
                "max_input_tokens": 65536,
                "supports_tools": True,
                "supports_vision": False,
                "supports_reasoning": False,
            },
        }
        return fetcher

    def _handler_with_both(self, byok_handler):
        byok_handler.clients = {"opencode-go": Mock(), "deepseek": Mock()}
        byok_handler.rate_tracker = self._fresh_tracker()
        return byok_handler

    def test_context_limit_clamps_candidates(self, byok_handler):
        handler = self._handler_with_both(byok_handler)
        handler.rate_tracker.set_rate_limits("opencode-go", rpm=60, tpm=2_000_000, max_context=3000)
        fetcher = self._fetcher(context=200000)
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync", return_value=fetcher):
            ranked = handler.get_ranked_providers(QueryComplexity.SIMPLE, is_managed_service=False)
        # opencode-go model clamped below the 4k floor for SIMPLE — skipped;
        # deepseek survives.
        assert ("opencode-go", "deepseek-v4-flash") not in ranked
        assert ranked[0][0] == "deepseek"

    def test_exhausted_rate_budget_skips_provider(self, byok_handler):
        handler = self._handler_with_both(byok_handler)
        # Burn the entire RPM budget for opencode-go this window.
        for _ in range(60):
            handler.rate_tracker.record_usage("opencode-go", 100, 100)
        fetcher = self._fetcher()
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync", return_value=fetcher):
            ranked = handler.get_ranked_providers(QueryComplexity.SIMPLE, is_managed_service=False)
        assert all(p != "opencode-go" for p, _ in ranked)

    def test_headroom_penalizes_value_score(self, byok_handler):
        handler = self._handler_with_both(byok_handler)
        handler.rate_tracker.record_usage("opencode-go", 100, 100)
        fetcher = self._fetcher()
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync", return_value=fetcher):
            ranked = handler.get_ranked_providers(QueryComplexity.SIMPLE, is_managed_service=False)
        # Not exhausted — opencode-go still eligible.
        assert ("opencode-go", "deepseek-v4-flash") in ranked

    def test_rate_tracking_is_scoped_to_limited_providers(self, byok_handler):
        tracker = ProviderRateTracker()
        tracker.set_rate_limits("opencode-go", rpm=1, tpm=10, max_context=200000)
        assert tracker.get_headroom("deepseek") == 1.0  # no limits → no tracking
        tracker.record_usage("deepseek", 1000, 1000)
        assert tracker.get_headroom("deepseek") == 1.0


# ============================================================================
# ProviderRateTracker unit tests
# ============================================================================

class TestProviderRateTracker:
    def test_headroom_full_when_idle(self):
        tracker = ProviderRateTracker()
        tracker.set_rate_limits("opencode-go", rpm=60, tpm=2_000_000, max_context=200000)
        assert tracker.get_headroom("opencode-go") == 1.0

    def test_headroom_shrinks_with_requests(self):
        tracker = ProviderRateTracker()
        tracker.set_rate_limits("opencode-go", rpm=10, tpm=100000, max_context=200000)
        for _ in range(5):
            tracker.record_usage("opencode-go", 100, 100)
        assert tracker.get_headroom("opencode-go") == pytest.approx(0.5, abs=0.01)

    def test_headroom_floor_at_exhaustion(self):
        tracker = ProviderRateTracker()
        tracker.set_rate_limits("opencode-go", rpm=2, tpm=100000, max_context=200000)
        for _ in range(5):
            tracker.record_usage("opencode-go", 100, 100)
        assert tracker.get_headroom("opencode-go") == 0.0

    def test_window_trims_old_usage(self):
        tracker = ProviderRateTracker(window_seconds=60)
        tracker.set_rate_limits("opencode-go", rpm=10, tpm=100000, max_context=200000)
        for _ in range(9):
            tracker.record_usage("opencode-go", 10, 10)
        assert tracker.get_headroom("opencode-go") == pytest.approx(0.1, abs=0.01)
        # Expire the window: force entries before the cutoff, then trim.
        from datetime import datetime, timezone, timedelta
        import collections
        expired = collections.deque(
            (datetime.now(timezone.utc) - timedelta(seconds=120), 10, 10) for _ in range(9)
        )
        with tracker._lock:
            tracker._usage["opencode-go"] = expired
        assert tracker.get_headroom("opencode-go") == 1.0

    def test_usage_summary(self):
        tracker = ProviderRateTracker()
        tracker.set_rate_limits("opencode-go", rpm=10, tpm=100000, max_context=200000)
        tracker.record_usage("opencode-go", 250, 50)
        summary = tracker.usage_summary("opencode-go")
        assert summary["requests_in_window"] == 1
        assert summary["tokens_in_window"] == 300
        assert summary["limits"]["rpm"] == 10


# ============================================================================
# Pricing fetcher
# ============================================================================

class TestOpenCodePricing:
    def test_static_fallback_tags_provider(self):
        fetcher = DynamicPricingFetcher()
        pricing = fetcher._opencode_static_fallback()
        assert pricing["deepseek-v4-flash"]["litellm_provider"] == "opencode-go"
        assert pricing["deepseek-v4-flash"]["input_cost_per_token"] == pytest.approx(0.14 / 1e6)
        assert pricing["kimi-k2.7-code"]["litellm_provider"] == "opencode-go"
        assert len(pricing) >= 5

    def test_fetch_opencode_falls_back_offline(self):
        import asyncio
        fetcher = DynamicPricingFetcher()
        with patch("httpx.AsyncClient.get", side_effect=Exception("offline")):
            pricing = asyncio.run(fetcher.fetch_opencode_pricing())
        assert pricing["deepseek-v4-flash"]["source"] == "opencode-zen"
