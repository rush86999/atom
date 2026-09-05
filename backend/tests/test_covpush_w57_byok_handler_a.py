"""Coverage wave 57 — core/llm/byok_handler.py (60% → 90%+), section A: helpers + routing.

Unit-level tests with a lightweight handler fixture (BYOKHandler.__new__ +
manually-set deps): free-model helpers, provider serving, fallback order,
excluded/capability/health filters, model capability flags, rate/usage
tracking, monthly quota, context window + truncation, complexity analysis,
optimal-provider paths, routing info, pricing surfaces, trial gate, error
classes, AwaitableResult operators.
"""
import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

import core.llm.byok_handler as bh
from core.llm.byok_handler import (
    AllProvidersFailedError,
    AwaitableResult,
    BYOKHandler,
    GatewayBlockedError,
    NoProvidersConfiguredError,
    QueryComplexity,
    _is_insufficient_balance_error,
    _is_opencode_free_model,
    _opencode_free_paid_fallback,
    _opencode_paid_fallback_model,
    _run_coroutine_sync,
)


def make_handler(**attrs):
    h = BYOKHandler.__new__(BYOKHandler)
    h.clients = {}
    h.async_clients = {}
    h.byok_manager = Mock()
    h.credential_service = None
    h.cognitive_classifier = Mock()
    h.cache_router = Mock()
    h.pricing_fetcher = Mock()
    h.db_session = None
    h.tier_service = Mock()
    h.excluded_models = set()
    h.health_monitor = MagicMock()
    h.health_monitor.health_scores = {}
    h.rate_tracker = Mock()
    h._last_used_model = None
    h._last_used_provider = None
    h._pending_routing_result_id = None
    h._embedding_initialized = False
    h._embedding_init_lock = None
    h._clients_initialized = True
    h.workspace_id = "ws1"
    h.tenant_id = "tenant"
    h.default_provider_id = None
    for k, v in attrs.items():
        setattr(h, k, v)
    return h


class TestFreeModelHelpers:
    def test_is_opencode_free_model(self):
        assert _is_opencode_free_model("deepseek-v4-flash-free") is True
        assert _is_opencode_free_model("deepseek-v4-flash") is False

    def test_fallback_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            fallbacks = _opencode_free_paid_fallback()
        assert isinstance(fallbacks, dict)
        assert fallbacks.get("deepseek-v4-flash-free") == "deepseek-v4-flash"

    def test_fallback_env_override(self):
        with patch.dict(os.environ, {
            "OPENCODE_FREE_PAID_FALLBACK": '{"deepseek-v4-flash-free": "custom-model"}'}, clear=True):
            assert _opencode_free_paid_fallback()["deepseek-v4-flash-free"] == "custom-model"

    def test_fallback_env_invalid_json(self):
        with patch.dict(os.environ, {"OPENCODE_FREE_PAID_FALLBACK": "not json"}, clear=True):
            fallbacks = _opencode_free_paid_fallback()
        assert fallbacks.get("deepseek-v4-flash-free") == "deepseek-v4-flash"

    def test_paid_fallback_model_mapping(self):
        assert _opencode_paid_fallback_model("deepseek-v4-flash-free") == "deepseek-v4-flash"
        assert _opencode_paid_fallback_model("mimo-v2.5-free") == "minimax-m2.7"
        assert _opencode_paid_fallback_model("weird-free") == "deepseek-v4-flash"
        assert _opencode_paid_fallback_model("gpt-4o") is None

    def test_insufficient_balance_variants(self):
        assert _is_insufficient_balance_error(ValueError("Insufficient balance. Add credits"))
        assert _is_insufficient_balance_error(ValueError("CreditsError: exhausted"))
        assert _is_insufficient_balance_error(ValueError("credit limit reached"))
        assert _is_insufficient_balance_error(ValueError("billing 401"))
        assert _is_insufficient_balance_error(ValueError("rate limit")) is False


class TestAwaitableResultOperators:
    def test_arithmetic_and_comparison(self):
        r = AwaitableResult(10)
        assert r + 5 == 15
        assert 5 + r == 15
        assert r - 3 == 7
        assert 20 - r == 10
        assert r * 2 == 20
        assert 2 * r == 20
        assert r / 2 == 5.0
        assert 100 / r == 10.0
        assert r < 11 and r <= 10 and r > 9 and r >= 10
        assert float(r) == 10.0
        assert int(r) == 10
        assert len(AwaitableResult([1, 2])) == 2
        assert AwaitableResult([1, 2])[0] == 1
        assert list(AwaitableResult([1])) == [1]
        assert repr(r) is not None

    def test_eq_and_await(self):
        assert AwaitableResult(1) == AwaitableResult(1)
        assert AwaitableResult(1) != AwaitableResult(2)

        async def consume():
            return await AwaitableResult(7)

        # asyncio.get_event_loop() raises when no loop is set (Python 3.14+
        # always; earlier versions after another test closed the loop) —
        # drive the coroutine on a fresh loop instead.
        loop = asyncio.new_event_loop()
        try:
            assert loop.run_until_complete(consume()) == 7
        finally:
            loop.close()


class TestErrorClasses:
    def test_no_providers_error(self):
        exc = NoProvidersConfiguredError("no providers")
        d = exc.to_dict()
        assert "no_llm_provider" in str(d)
        assert exc.recovery_url == "/settings/ai"

    def test_gateway_blocked(self):
        exc = GatewayBlockedError("budget", "Blocked for spend")
        assert exc.reason == "budget"
        assert exc.message == "Blocked for spend"

    def test_all_providers_failed(self):
        exc = AllProvidersFailedError()
        assert exc is not None


class TestProviderServing:
    def test_empty_model_true(self):
        h = make_handler()
        assert h._provider_serves_model("openai", "") is True

    def test_local_providers_always_serve(self):
        h = make_handler()
        for pid in ("ollama", "vllm", "lmstudio", "local", "local_abc"):
            assert h._provider_serves_model(pid, "anything") is True

    def test_gateway_providers_serve(self):
        h = make_handler()
        for pid in ("opencode-go", "opencode", "zen", "openrouter"):
            assert h._provider_serves_model(pid, "any-model") is True

    def test_family_prefixes(self):
        h = make_handler()
        assert h._provider_serves_model("deepseek", "deepseek-chat") is True
        assert h._provider_serves_model("anthropic", "claude-3-5-sonnet") is True
        assert h._provider_serves_model("openai", "gpt-4o") is True
        assert h._provider_serves_model("openai", "claude-x") is False
        assert h._provider_serves_model("moonshot", "kimi-k2") is True
        assert h._provider_serves_model("unknown_provider", "model-x") is False
        assert h._provider_serves_model("qwen", "qwen-plus") is True


class TestFallbackOrder:
    def test_order_with_primary(self):
        h = make_handler(clients={"deepseek": 1, "openai": 2, "ollama": 3, "custom": 4})
        # The order path drops a local runtime that isn't answering (live
        # localhost:11434 probe). Dev machines run ollama, CI runners don't —
        # pin the probe so the ordering assertion is environment-independent.
        with patch.object(bh.BYOKHandler, "_ollama_runtime_state",
                          return_value=("up", set())):
            order = h._get_provider_fallback_order("openai")
        assert order[0] == "openai"
        assert order.index("deepseek") < order.index("ollama")
        assert "custom" in order  # remaining providers appended

    def test_order_excludes_ollama_when_runtime_down(self):
        """CI reality: nothing listens on localhost:11434. A non-answering
        local runtime must stay out of the fallback chain — mid-request
        fallback to a dead ollama only adds its connection timeout."""
        h = make_handler(clients={"deepseek": 1, "openai": 2, "ollama": 3})
        with patch.object(bh.BYOKHandler, "_ollama_runtime_state",
                          return_value=("down", None)):
            order = h._get_provider_fallback_order("deepseek")
        assert "ollama" not in order
        assert order[0] == "deepseek"

    def test_empty_clients(self):
        h = make_handler(clients={})
        assert h._get_provider_fallback_order("deepseek") == []

    def test_primary_not_available(self):
        h = make_handler(clients={"deepseek": 1})
        order = h._get_provider_fallback_order("ghost")
        assert order == ["deepseek"]


class TestCachesAndFilters:
    def test_refresh_excluded_cache(self):
        db = MagicMock()
        db.__enter__.return_value = db
        db.query.return_value.filter.return_value.all.return_value = [("m1",), ("m2",)]
        h = make_handler()
        with patch("core.llm.byok_handler.get_db_session", return_value=db):
            h._refresh_excluded_cache()
        assert h.excluded_models == {"m1", "m2"}

    def test_refresh_excluded_cache_error(self):
        h = make_handler()
        with patch("core.llm.byok_handler.get_db_session",
                   side_effect=RuntimeError("db down")):
            h._refresh_excluded_cache()
        assert h.excluded_models == set()

    def test_load_capability_index(self):
        db = MagicMock()
        db.__enter__.return_value = db
        db.query.return_value.all.return_value = [
            SimpleNamespace(model_id="m1", capabilities=["tools", "vision"]),
            SimpleNamespace(model_id="m2", capabilities=None),
        ]
        h = make_handler()
        with patch("core.llm.byok_handler.get_db_session", return_value=db):
            index = h._load_capability_index()
        assert index["m1"] == ["tools", "vision"]
        assert index["m2"] == ["chat"]  # None -> default

    def test_load_capability_index_error(self):
        h = make_handler()
        with patch("core.llm.byok_handler.get_db_session",
                   side_effect=RuntimeError("boom")):
            assert h._load_capability_index() is None

    def test_filter_by_capabilities_index_path(self):
        h = make_handler()
        index = {"m1": ["tools"], "m2": ["chat"]}
        assert h._filter_by_capabilities("m1", "tools", index) is True
        assert h._filter_by_capabilities("m2", "tools", index) is False
        assert h._filter_by_capabilities("unknown", "tools", index) is True
        assert h._filter_by_capabilities("m1", None, index) is True

    def test_filter_by_capabilities_db_path(self):
        db = MagicMock()
        db.__enter__.return_value = db
        h = make_handler()
        db.query.return_value.filter_by.return_value.first.return_value = \
            SimpleNamespace(capabilities=["vision"])
        with patch("core.llm.byok_handler.get_db_session", return_value=db):
            assert h._filter_by_capabilities("m1", "vision") is True
            assert h._filter_by_capabilities("m1", "tools") is False
            db.query.return_value.filter_by.return_value.first.return_value = None
            assert h._filter_by_capabilities("m1", "tools") is True

    def test_filter_by_capabilities_db_error(self):
        h = make_handler()
        with patch("core.llm.byok_handler.get_db_session",
                   side_effect=RuntimeError("boom")):
            assert h._filter_by_capabilities("m1", "tools") is True

    def test_filter_by_health(self):
        h = make_handler()
        h.health_monitor.health_scores = {"dead": 0.1}
        h.health_monitor.get_health_score.return_value = 0.1
        assert h._filter_by_health("dead") is False
        assert h._filter_by_health("unknown") is True
        h.health_monitor.get_health_score.return_value = 0.9
        assert h._filter_by_health("dead") is True

    def test_model_capability_flags(self):
        h = make_handler()
        h.pricing_fetcher.get_model_capabilities.return_value = {
            "supports_tools": True, "supports_vision": True, "supports_reasoning": False}
        assert h._model_supports_tools("m") is True
        assert h._model_supports_vision("m") is True
        assert h._model_supports_reasoning("m") is False
        h.pricing_fetcher.get_model_capabilities.return_value = {}
        assert h._model_supports_tools("m") is False


class TestTrackingAndQuota:
    def test_track_rate_usage(self):
        h = make_handler()
        h._track_rate_usage("p", 10, 20, "m")
        h.rate_tracker.record_usage.assert_called_once_with("p", 10, 20, model_id="m")

    def test_track_rate_usage_error(self):
        h = make_handler()
        h.rate_tracker.record_usage.side_effect = RuntimeError("boom")
        h._track_rate_usage("p", 1, 1)  # must not raise

    def test_track_llm_call(self):
        h = make_handler()
        with patch("core.llm.byok_handler.get_llm_call_tracker") as glt:
            h._track_llm_call("p", "m", True, latency_ms=5.0, fallback=True)
            glt.return_value.record.assert_called_once()

    def test_track_llm_call_error(self):
        h = make_handler()
        with patch("core.llm.byok_handler.get_llm_call_tracker",
                   side_effect=RuntimeError("boom")):
            h._track_llm_call("p", "m", True)  # must not raise

    def test_monthly_tpm_limit(self):
        h = make_handler()
        with patch.dict(os.environ, {"OPENCODE_MONTHLY_TPM": "5000"}, clear=True):
            assert h._monthly_tpm_limit() == 5000
        with patch.dict(os.environ, {}, clear=True):
            assert h._monthly_tpm_limit() is None
        with patch.dict(os.environ, {"OPENCODE_MONTHLY_TPM": "-5"}, clear=True):
            assert h._monthly_tpm_limit() is None
        with patch.dict(os.environ, {"OPENCODE_MONTHLY_TPM": "abc"}, clear=True):
            assert h._monthly_tpm_limit() is None

    def test_monthly_budget_exhausted(self):
        h = make_handler()
        h.rate_tracker.get_monthly_usage.return_value = {"total_tokens": 100}
        assert h._monthly_budget_exhausted("p", 50) is True
        assert h._monthly_budget_exhausted("p", 200) is False
        h.rate_tracker.get_monthly_usage.return_value = None
        assert h._monthly_budget_exhausted("p", 50) is False
        h.rate_tracker.get_monthly_usage.side_effect = RuntimeError("boom")
        assert h._monthly_budget_exhausted("p", 50) is False


class TestContextAndTruncation:
    def test_get_context_window_pricing(self):
        h = make_handler()
        fetcher = Mock()
        fetcher.get_model_price.return_value = {"max_input_tokens": 64000}
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            assert h.get_context_window("gpt-4o") == 64000
            fetcher.get_model_price.return_value = {"max_tokens": 32000}
            assert h.get_context_window("gpt-4o") == 32000

    def test_get_context_window_defaults(self):
        h = make_handler()
        fetcher = Mock()
        fetcher.get_model_price.return_value = None
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            assert h.get_context_window("gpt-4o") == 128000
            assert h.get_context_window("deepseek-chat") == 32768
            assert h.get_context_window("claude-3-sonnet") == 200000
            assert h.get_context_window("unknown-model") == 4096

    def test_get_context_window_error(self):
        h = make_handler()
        with patch("core.llm.byok_handler.get_pricing_fetcher",
                   side_effect=RuntimeError("boom")):
            assert h.get_context_window("unknown-model") == 4096

    def test_truncate_to_context_short(self):
        h = make_handler()
        text = "x" * 100
        assert h.truncate_to_context(text, "gpt-4o") == text

    def test_truncate_to_context_long(self):
        h = make_handler()
        with patch.object(h, "get_context_window", return_value=2000):
            result = h.truncate_to_context("x" * 5000, "gpt-4o")
        assert "truncated" in result


class TestComplexity:
    def test_simple(self):
        h = make_handler()
        assert h.analyze_query_complexity("hello, thanks for your help") == QueryComplexity.SIMPLE

    def test_moderate(self):
        h = make_handler()
        assert h.analyze_query_complexity("analyze the concept") == QueryComplexity.MODERATE

    def test_complex_code(self):
        h = make_handler()
        prompt = "write a function to debug this script and refactor the import"
        assert h.analyze_query_complexity(prompt) == QueryComplexity.COMPLEX

    def test_advanced(self):
        h = make_handler()
        prompt = "architect a distributed system with concurrency, cryptography and load balance"
        assert h.analyze_query_complexity(prompt) == QueryComplexity.ADVANCED

    def test_long_prompt(self):
        h = make_handler()
        long_prompt = "this is a long prompt " * 300  # > 2000 tokens est
        assert h.analyze_query_complexity(long_prompt) == QueryComplexity.COMPLEX


class TestOptimalProvider:
    def test_returns_first_option(self):
        h = make_handler()
        with patch.object(h, "get_ranked_providers", return_value=[("p", "m")]):
            result = h.get_optimal_provider(QueryComplexity.SIMPLE)
        assert result[0] == "p"

    def test_absolute_fallback(self):
        h = make_handler(clients={"deepseek": 1})
        with patch.object(h, "get_ranked_providers", return_value=[]):
            result = h.get_optimal_provider(QueryComplexity.SIMPLE)
        assert result[1] == "gpt-4o-mini"

    def test_no_clients_raises(self):
        h = make_handler(clients={})
        with patch.object(h, "get_ranked_providers", return_value=[]):
            with pytest.raises(NoProvidersConfiguredError):
                h.get_optimal_provider(QueryComplexity.SIMPLE)


class TestRoutingInfoAndPricing:
    def test_routing_info_success(self):
        h = make_handler(clients={"deepseek": 1})
        with patch.object(h, "get_optimal_provider", return_value=("deepseek", "deepseek-chat")), \
             patch("core.llm.byok_handler.get_pricing_fetcher") as gpf:
            fetcher = gpf.return_value
            fetcher.get_model_price.return_value = {"input_cost_per_token": 1e-6}
            fetcher.estimate_cost.return_value = 0.01
            info = h.get_routing_info("hello world")
        assert info["complexity"] == "simple"
        assert info["selected_provider"] == "deepseek"
        assert info["cost_tier"] == "budget"
        assert info["estimated_cost_usd"] == 0.01

    def test_routing_info_error(self):
        h = make_handler(clients={})
        with patch.object(h, "get_optimal_provider",
                          side_effect=ValueError("no providers")):
            info = h.get_routing_info("hello")
        assert "error" in info
        assert info["available_providers"] == []

    def test_refresh_pricing_success_and_error(self):
        h = make_handler()
        with patch("core.llm.byok_handler.refresh_pricing_cache",
                   new=AsyncMock(return_value={"m1": {}})):
            result = await_h(h.refresh_pricing())
        assert result["status"] == "success"
        with patch("core.llm.byok_handler.refresh_pricing_cache",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await_h(h.refresh_pricing())
        assert result["status"] == "error"

    def test_provider_comparison_dynamic_and_static(self):
        h = make_handler()
        fetcher = Mock()
        fetcher.compare_providers.return_value = {"openai": {}}
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            assert h.get_provider_comparison() == {"openai": {}}
            fetcher.compare_providers.return_value = {}
            comparison = h.get_provider_comparison()
        assert "deepseek" in comparison  # static fallback

    def test_provider_comparison_error(self):
        h = make_handler()
        with patch("core.llm.byok_handler.get_pricing_fetcher",
                   side_effect=RuntimeError("boom")):
            comparison = h.get_provider_comparison()
        assert "deepseek" in comparison

    def test_cheapest_models(self):
        h = make_handler()
        fetcher = Mock()
        fetcher.get_cheapest_models.return_value = [{"id": "m1"}]
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            assert h.get_cheapest_models(3) == [{"id": "m1"}]
            fetcher.get_cheapest_models.side_effect = RuntimeError("boom")
            assert h.get_cheapest_models(3) == []

    def test_get_available_providers(self):
        h = make_handler(clients={"a": 1, "b": 2})
        assert h.get_available_providers() == ["a", "b"]


def await_h(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
