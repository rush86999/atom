"""
TDD bug-hunt tests for the BYOK/rate/pricing/cognitive-tier territory.

Bugs covered:
1. cognitive_tier_service passes the learned cache-hit probability as the
   POSITIONAL ``turn_index`` argument of ``CacheAwareRouter.calculate_effective_cost``
   (4th param) instead of the ``cache_hit_probability`` keyword (5th), so
   learned cache rates are ignored and every cache-capable model is scored at
   the full deterministic discount.
2. ``get_ranked_providers``' ``is_model_approved`` early-returns True when the
   plan allowed-list is ``"*"`` (BYOK / enterprise), skipping the
   ``requires_tools`` / ``requires_structured`` filter — agentic requests can
   route to tool-incapable models on the BPC primary path.
3. The static fallback path calls ``fetcher._model_supports_tools(model)`` — a
   method that does not exist on ``DynamicPricingFetcher`` — and the
   AttributeError is swallowed by ``except Exception: pass``, so the managed
   static fallback admits tool-less models.
4. The forced-tier (x-atom-tier) path passes the STRING ``"complex"`` as
   ``complexity``; the BPC success log does ``complexity.value``, raising
   AttributeError and discarding the successful tier-filtered BPC results in
   favor of the tier-ignorant static fallback.
5. ``stream_completion`` yields ``str(last_error)`` to the client in its error
   chunk — leaking provider error details (secrets can appear in auth errors).
"""
import hashlib
import logging
import os
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.llm.byok_handler import BYOKHandler, QueryComplexity
from core.llm.cache_aware_router import CacheAwareRouter
from core.llm.cognitive_tier_service import CognitiveTierService
from core.llm.cognitive_tier_system import CognitiveTier
from core.llm.provider_rate_limits import ProviderRateTracker


class FakePricingFetcher:
    """In-memory pricing fetcher standing in for DynamicPricingFetcher."""

    def __init__(self, cache):
        self.pricing_cache = cache

    def get_model_price(self, name):
        if name in self.pricing_cache:
            return self.pricing_cache[name]
        for cached, pricing in self.pricing_cache.items():
            if cached.lower() == name.lower():
                return pricing
        return None

    def get_model_capabilities(self, name):
        entry = self.pricing_cache.get(name, {})
        return {
            "supports_tools": entry.get("supports_tools", False),
            "supports_vision": entry.get("supports_vision", False),
            "supports_reasoning": entry.get("supports_reasoning", False),
        }


def _entry(provider, window=131072, cost=1e-7, tools=True):
    return {
        "model_id": "x",
        "litellm_provider": provider,
        "input_cost_per_token": cost,
        "output_cost_per_token": cost,
        "max_input_tokens": window,
        "max_tokens": window,
        "supports_tools": tools,
    }


@pytest.fixture
def handler():
    """BYOKHandler with all external dependencies mocked.

    Patchers are STARTED (not context-managed) so they stay active for the
    duration of the TEST, not just construction: get_quality_score consults
    the dynamic benchmark fetcher at call time, and the fetcher substring-
    matches model names across GENERATIONS (a cached deepseek-chat-v3-0324
    entry scores the current deepseek-chat 15 instead of the table's 80).
    Without this, ranking tests depend on the ambient local benchmark cache.
    """
    patchers = [
        patch("core.dynamic_benchmark_fetcher.get_benchmark_fetcher"),
        patch("core.llm.byok_handler.get_byok_manager"),
        patch("core.llm.byok_handler.CognitiveTierService"),
        patch("core.provider_health_monitor.get_provider_health_monitor"),
    ]
    bench_mock, manager_mock, _tier_mock, health_mock = (p.start() for p in patchers)
    bench_mock.return_value = Mock(get_benchmark_score=Mock(return_value=None))
    manager_mock.return_value = Mock()
    monitor = Mock()
    monitor.health_scores = {}
    monitor.get_health_score = Mock(return_value=1.0)
    monitor.record_call = Mock()
    health_mock.return_value = monitor
    try:
        h = BYOKHandler(
            workspace_id="test-ws",
            tenant_id="test-t",
            provider_id="auto",
        )
        h.rate_tracker = ProviderRateTracker()
        h.excluded_models = set()
        yield h
    finally:
        for p in patchers:
            p.stop()


# ============================================================================
# Bug 1: cache-hit probability passed as positional turn_index
# ============================================================================

class TestCacheProbabilityKwarg:

    def _make_service(self, ws="test-ws", prompt="short prompt"):
        cache = {
            "gpt-4o-mini": _entry("openai", cost=5e-7),
            "deepseek-chat": _entry("deepseek", cost=1e-7),
        }
        fetcher = FakePricingFetcher(cache)
        router = CacheAwareRouter(fetcher)
        model = "gpt-4o-mini"
        hash16 = hashlib.sha256(f"{ws}:{model}".encode()).hexdigest()[:16]
        router.cache_hit_history[f"{ws}:{hash16}"] = [2, 10]  # 20% hit rate
        prompt_hash16 = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        router.cache_hit_history[f"{ws}:{prompt_hash16}"] = [2, 10]
        service = CognitiveTierService(workspace_id=ws, db_session=None)
        service._cache_router = router
        return service, router, model

    def test_optimal_model_passes_cache_probability_as_keyword(self):
        service, router, model = self._make_service()
        calls = []

        def spy(*args, **kwargs):
            calls.append((args, kwargs))
            return original(*args, **kwargs)

        original = router.calculate_effective_cost
        router.calculate_effective_cost = spy

        service.get_optimal_model(CognitiveTier.MICRO, estimated_tokens=1500)

        gpt_calls = [c for c in calls if c[0] and c[0][0] == model]
        assert gpt_calls, "gpt-4o-mini should have been scored"
        args, kwargs = gpt_calls[0]
        # Learned 20% hit rate must reach cache_hit_probability, not turn_index.
        assert kwargs.get("cache_hit_probability") == 0.2
        assert len(args) == 3, "cache probability must not be passed as turn_index"

    def test_request_cost_uses_learned_cache_probability_and_full_price_base(self):
        service, router, model = self._make_service()
        calls = []

        def spy(*args, **kwargs):
            calls.append((args, kwargs))
            return original(*args, **kwargs)

        original = router.calculate_effective_cost
        router.calculate_effective_cost = spy

        service.calculate_request_cost("short prompt", CognitiveTier.MICRO, model=model)

        assert len(calls) == 2
        effective_kwargs = calls[0][1]
        full_kwargs = calls[1][1]
        assert effective_kwargs.get("cache_hit_probability") == 0.2
        # "full cost" baseline must be the 0% cached price, not the 50% default.
        assert full_kwargs.get("cache_hit_probability") == 0.0


# ============================================================================
# Bug 2: "*" allowed-list bypasses the tools filter in the BPC path
# ============================================================================

class TestWildcardPlanToolBypass:

    def test_byok_wildcard_plan_still_filters_tool_incapable_models(self, handler):
        cache = {
            "gpt-4o-mini": _entry("openai", cost=5e-7, tools=False),
            "deepseek-chat": _entry("deepseek", cost=1e-7, tools=True),
        }
        fetcher = FakePricingFetcher(cache)
        handler.clients = {"openai": object(), "deepseek": object()}
        handler.cache_router = CacheAwareRouter(fetcher)
        handler.pricing_fetcher = fetcher

        with patch.object(
            __import__("core.llm.byok_handler", fromlist=["x"]),
            "get_pricing_fetcher_initialized_sync",
            return_value=fetcher,
        ):
            options = list(handler.get_ranked_providers(
                QueryComplexity.MODERATE,
                task_type="agentic",
                prefer_cost=True,
                tenant_plan="free",
                is_managed_service=False,
                requires_tools=True,
                requires_structured=False,
                turn_index=0,
            ))

        assert options, "BPC should still return the tool-capable candidate"
        for provider, model in options:
            if model in cache:
                assert cache[model]["supports_tools"], (
                    f"tool-incapable model {model} leaked into ranked options"
                )
        assert ("openai", "gpt-4o-mini") not in options


# ============================================================================
# Bug 3: static fallback calls a method that doesn't exist on the fetcher
# ============================================================================

class TestStaticFallbackToolCheck:

    def test_managed_static_fallback_excludes_tool_less_models(self, handler):
        # Empty pricing cache forces BPC to fail and the static fallback to run.
        fetcher = FakePricingFetcher({})
        handler.clients = {"gemini": object(), "deepseek": object()}
        handler.cache_router = CacheAwareRouter(fetcher)
        handler.pricing_fetcher = fetcher

        with patch.object(
            __import__("core.llm.byok_handler", fromlist=["x"]),
            "get_pricing_fetcher_initialized_sync",
            return_value=fetcher,
        ):
            options = list(handler.get_ranked_providers(
                QueryComplexity.COMPLEX,
                task_type="agentic",
                prefer_cost=True,
                tenant_plan="free",
                is_managed_service=True,
                requires_tools=True,
                requires_structured=False,
                turn_index=0,
            ))

        for provider, model in options:
            if not handler._model_supports_tools(model):
                raise AssertionError(
                    f"static fallback returned tool-incapable model {provider}/{model}"
                )
        assert ("gemini", "gemini-3.5-flash") not in options


# ============================================================================
# Bug 4: forced-tier string complexity discards successful BPC results
# ============================================================================

class TestForcedTierComplexityCrash:

    def test_string_complexity_keeps_bpc_results(self, handler, caplog):
        cache = {
            "deepseek-chat": _entry("deepseek", cost=1e-7, tools=True),
            "deepseek-v3.2-speciale": _entry("deepseek", cost=3e-7, tools=False),
            "gpt-4o-mini": _entry("openai", cost=5e-7, tools=True),
        }
        fetcher = FakePricingFetcher(cache)
        handler.clients = {"openai": object(), "deepseek": object()}
        handler.cache_router = CacheAwareRouter(fetcher)
        handler.pricing_fetcher = fetcher

        with caplog.at_level(logging.INFO, logger="core.llm.byok_handler"):
            with patch.object(
                __import__("core.llm.byok_handler", fromlist=["x"]),
                "get_pricing_fetcher_initialized_sync",
                return_value=fetcher,
            ):
                options = list(handler.get_ranked_providers(
                    "complex",  # string, as set by the forced x-atom-tier path
                    task_type=None,
                    prefer_cost=True,
                    tenant_plan="free",
                    is_managed_service=False,
                    requires_tools=False,
                    cognitive_tier=CognitiveTier.STANDARD,
                    turn_index=0,
                ))

        # The BPC success path must be reached instead of crashing into the
        # tier-ignorant static fallback (which would return gpt-5.6-sol).
        assert "BPC Ranking Successful" in caplog.text
        assert ("openai", "gpt-5.6-sol") not in options
        assert ("deepseek", "deepseek-chat") in options


# ============================================================================
# Bug 5: stream_completion leaks error detail to the client
# ============================================================================

class TestStreamErrorLeak:

    async def test_stream_error_chunk_does_not_leak_error_detail(self, handler):
        secret = "sk-live-secret-12345"
        handler.clients = {"openai": object()}
        handler.async_clients = {"openai": Mock()}
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            side_effect=RuntimeError(f"401 Invalid API key: {secret}")
        )

        chunks = []
        async for chunk in handler.stream_completion(
            [{"role": "user", "content": "hello"}],
            model="gpt-4o-mini",
            provider_id="openai",
        ):
            chunks.append(chunk)

        error_chunks = [c for c in chunks if "[Error" in c]
        assert error_chunks, "expected an error chunk after all providers failed"
        assert secret not in "".join(chunks)
        assert "Please check your API key" in error_chunks[0]


# ============================================================================
# Availability: a cold/empty pricing cache must not zero out routing
# ============================================================================

class TestColdCacheFailOpen:
    def test_structured_request_survives_empty_pricing_cache(self, handler):
        """The 2026-08-28 live outage: ReAct requests are structured, the
        pricing cache had no capability data (fetch failed), and the
        conservative tools filter eliminated every candidate — 'No eligible
        LLM providers found for your current plan'. Capability filtering is
        best-effort; it must fail open when it would return zero options."""

        fetcher = MagicMock()
        fetcher.pricing_cache = {}
        fetcher.get_model_capabilities.return_value = {}
        handler.clients = {"openrouter": object()}
        handler.cache_router = MagicMock()
        handler.cache_router.calculate_effective_cost.return_value = 1e-7
        handler.rate_tracker.get_max_context = MagicMock(return_value=None)
        handler.rate_tracker.get_model_weight = MagicMock(return_value=1.0)

        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                        return_value=fetcher), \
             patch("core.llm.byok_handler.get_pricing_fetcher",
                        return_value=fetcher):
            options = list(handler.get_ranked_providers(
                "moderate", prefer_cost=True, tenant_plan="free",
                is_managed_service=True, requires_tools=False,
                requires_structured=True, turn_index=0,
            ))

        assert options, "cold cache + structured request must fail open, not empty"
        assert options[0][0] == "openrouter"

    def test_warm_cache_tools_filter_still_applies(self, handler):
        """Fail-open only rescues the zero-option case: with a populated cache
        the conservative per-model filter still removes non-tool models."""
        fetcher = MagicMock()
        fetcher.pricing_cache = {
            "deepseek-chat": _entry("deepseek", cost=1e-7, tools=True),
        }
        handler.clients = {"deepseek": object()}
        handler.cache_router = MagicMock()
        handler.cache_router.calculate_effective_cost.return_value = 1e-7
        handler.rate_tracker.get_max_context = MagicMock(return_value=None)
        handler.rate_tracker.get_model_weight = MagicMock(return_value=1.0)

        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                        return_value=fetcher), \
             patch("core.llm.byok_handler.get_pricing_fetcher",
                        return_value=fetcher):
            options = list(handler.get_ranked_providers(
                QueryComplexity.MODERATE, prefer_cost=True, tenant_plan="pro",
                is_managed_service=True, requires_tools=True, turn_index=0,
            ))

        assert options, "tool-capable model should rank normally"
        assert all(handler._model_supports_tools(m) for _, m in options)
