"""
Coverage-push tests for core.llm.byok_handler (tests-only; read-only source).

Uses the established fixture pattern: patch get_byok_manager, construct the
handler, then override clients/async_clients/rate_tracker/health_monitor with
mocks. Targets the untested surface: AwaitableResult seam, provider/model
heuristics, rate tracking, budget limits, context truncation, tool-pair
sanitization, complexity analysis, routing info, pricing helpers, cognitive
tier orchestration, transcription, vision coordination, embeddings, and the
learning-router hooks.
"""

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.llm.byok_handler import (
    AllProvidersFailedError,
    AwaitableResult,
    BYOKHandler,
    GatewayBlockedError,
    NoProvidersConfiguredError,
    QueryComplexity,
    _llm_request_timeout,
)
from core.llm.cognitive_tier_system import CognitiveTier


@pytest.fixture
def handler():
    with patch("core.llm.byok_handler.get_byok_manager", return_value=Mock()):
        h = BYOKHandler(workspace_id="ws-1", tenant_id="t-1")
    h.clients = {"openai": Mock(), "deepseek": Mock(), "gemini": Mock()}
    h.async_clients = {"openai": AsyncMock(), "deepseek": AsyncMock(), "gemini": AsyncMock()}
    h.rate_tracker = Mock()
    h.health_monitor = Mock()
    h.health_monitor.health_scores = {}
    return h


# ============================ AwaitableResult seam ============================


class TestAwaitableResult:
    @pytest.mark.asyncio
    async def test_await(self):
        assert await AwaitableResult(42) == 42

    def test_sequence_protocol(self):
        r = AwaitableResult([1, 2, 3])
        assert list(r) == [1, 2, 3]
        assert len(r) == 3
        assert r[1] == 2

    def test_comparison_and_math(self):
        r = AwaitableResult(10)
        assert r == 10
        assert r == AwaitableResult(10)
        assert r != 11
        assert repr(r) == "10"
        assert r + 5 == 15
        assert r + AwaitableResult(5) == 15
        assert 5 + r == 15
        assert r - 3 == 7
        assert 20 - r == 10
        assert r * 2 == 20
        assert 2 * r == 20
        assert r / 4 == 2.5
        assert 100 / r == 10
        assert r < 11 and r <= 10 and r > 9 and r >= 10
        assert float(r) == 10.0
        assert int(r) == 10


# ============================ module-level helpers ============================


class TestModuleHelpers:
    def test_llm_request_timeout_default(self, monkeypatch):
        monkeypatch.delenv("ATOM_LLM_REQUEST_TIMEOUT", raising=False)
        assert _llm_request_timeout() == 120.0

    def test_llm_request_timeout_env(self, monkeypatch):
        monkeypatch.setenv("ATOM_LLM_REQUEST_TIMEOUT", "30")
        assert _llm_request_timeout() == 30.0

    def test_llm_request_timeout_invalid(self, monkeypatch):
        monkeypatch.setenv("ATOM_LLM_REQUEST_TIMEOUT", "abc")
        assert _llm_request_timeout() == 120.0

    def test_no_providers_configured_error(self):
        err = NoProvidersConfiguredError("nope", recovery_url="/settings/ai", error_code="x")
        assert err.message == "nope"
        assert err.recovery_url == "/settings/ai"
        assert err.error_code == "x"
        assert err.to_dict()["error_code"] == "x"
        assert isinstance(err, ValueError)
        default = NoProvidersConfiguredError()
        assert default.message == "No LLM providers configured."

    def test_gateway_blocked_error(self):
        err = GatewayBlockedError("trial_expired", "blocked")
        assert err.reason == "trial_expired"
        assert err.message == "blocked"

    def test_all_providers_failed_error(self):
        assert isinstance(AllProvidersFailedError("boom"), AllProvidersFailedError)


# ============================ provider/model heuristics ============================


class TestProviderHeuristics:
    def test_provider_serves_model_empty(self, handler):
        assert handler._provider_serves_model("openai", "") is True
        assert handler._provider_serves_model("openai", None) is True

    def test_provider_serves_local(self, handler):
        for prov in ["ollama", "vllm", "lmstudio", "local", "local_abc123"]:
            assert handler._provider_serves_model(prov, "anything") is True

    def test_provider_serves_gateway(self, handler):
        for prov in ["opencode-go", "opencode", "zen", "openrouter"]:
            assert handler._provider_serves_model(prov, "deepseek-v4-flash") is True

    def test_provider_serves_family_prefixes(self, handler):
        assert handler._provider_serves_model("openai", "gpt-4o") is True
        assert handler._provider_serves_model("openai", "o3-mini") is True
        assert handler._provider_serves_model("anthropic", "claude-3-5-sonnet") is True
        assert handler._provider_serves_model("deepseek", "deepseek-chat") is True
        assert handler._provider_serves_model("gemini", "gemini-2.5-flash") is True
        assert handler._provider_serves_model("qwen", "qwen-plus") is True
        assert handler._provider_serves_model("moonshot", "kimi-k2") is True
        assert handler._provider_serves_model("minimax", "minimax-m3") is True
        assert handler._provider_serves_model("glm", "chatglm-turbo") is True
        assert handler._provider_serves_model("openai", "claude-3") is False
        assert handler._provider_serves_model("unknown-provider", "random-model") is False

    def test_provider_serves_substring_fallback(self, handler):
        assert handler._provider_serves_model("some-provider", "some-provider-x") is True

    def test_refresh_excluded_cache(self, handler):
        db = Mock()
        db.query.return_value.filter.return_value.all.return_value = [("m1",), ("m2",)]
        with patch("core.llm.byok_handler.get_db_session") as gds:
            gds.return_value.__enter__.return_value = db
            handler._refresh_excluded_cache()
        assert handler.excluded_models == {"m1", "m2"}

    def test_refresh_excluded_cache_error(self, handler):
        with patch("core.llm.byok_handler.get_db_session", side_effect=RuntimeError("db down")):
            handler._refresh_excluded_cache()
        assert handler.excluded_models == set()

    def test_load_capability_index(self, handler):
        db = Mock()
        row1 = Mock(model_id="m1", capabilities=["chat", "tools"])
        row2 = Mock(model_id="m2", capabilities=None)
        db.query.return_value.all.return_value = [row1, row2]
        with patch("core.llm.byok_handler.get_db_session") as gds:
            gds.return_value.__enter__.return_value = db
            index = handler._load_capability_index()
        assert index == {"m1": ["chat", "tools"], "m2": ["chat"]}

    def test_load_capability_index_error(self, handler):
        with patch("core.llm.byok_handler.get_db_session", side_effect=RuntimeError("down")):
            assert handler._load_capability_index() is None

    def test_filter_by_capabilities(self, handler):
        assert handler._filter_by_capabilities("m", None) is True
        assert handler._filter_by_capabilities("m", "tools", {"m": ["tools"]}) is True
        assert handler._filter_by_capabilities("m", "tools", {"m": ["chat"]}) is False
        assert handler._filter_by_capabilities("unknown", "tools", {}) is True

    def test_filter_by_capabilities_db_path(self, handler):
        db = Mock()
        model = Mock(capabilities=["tools"])
        db.query.return_value.filter_by.return_value.first.return_value = model
        with patch("core.llm.byok_handler.get_db_session") as gds:
            gds.return_value.__enter__.return_value = db
            assert handler._filter_by_capabilities("m", "tools") is True
        db.query.return_value.filter_by.return_value.first.return_value = None
        with patch("core.llm.byok_handler.get_db_session") as gds:
            gds.return_value.__enter__.return_value = db
            assert handler._filter_by_capabilities("m", "tools") is True

    def test_filter_by_capabilities_db_error(self, handler):
        with patch("core.llm.byok_handler.get_db_session", side_effect=RuntimeError("down")):
            assert handler._filter_by_capabilities("m", "tools") is True

    def test_filter_by_health(self, handler):
        assert handler._filter_by_health("unknown") is True
        handler.health_monitor.health_scores = {"openai": 0.5}
        handler.health_monitor.get_health_score = Mock(return_value=0.5)
        assert handler._filter_by_health("openai") is True
        handler.health_monitor.get_health_score = Mock(return_value=0.1)
        assert handler._filter_by_health("openai") is False

    def test_model_support_flags(self, handler):
        handler.pricing_fetcher = Mock()
        handler.pricing_fetcher.get_model_capabilities = Mock(
            return_value={"supports_tools": True, "supports_vision": False,
                          "supports_reasoning": True}
        )
        assert handler._model_supports_tools("m") is True
        assert handler._model_supports_vision("m") is False
        assert handler._model_supports_reasoning("m") is True
        handler.pricing_fetcher.get_model_capabilities = Mock(return_value={})
        assert handler._model_supports_tools("m") is False


# ============================ rate tracking / budgets ============================


class TestRateTracking:
    def test_track_rate_usage(self, handler):
        handler._track_rate_usage("opencode-go", 100, 200, model_id="m1")
        handler.rate_tracker.record_usage.assert_called_once_with(
            "opencode-go", 100, 200, model_id="m1"
        )

    def test_track_rate_usage_error_swallowed(self, handler):
        handler.rate_tracker.record_usage.side_effect = RuntimeError("boom")
        handler._track_rate_usage("x")  # no raise

    def test_track_llm_call(self, handler):
        with patch("core.llm.byok_handler.get_llm_call_tracker") as tracker:
            handler._track_llm_call("openai", "gpt-4o", True, latency_ms=12, input_tokens=10,
                                    output_tokens=5, fallback=True, fallback_provider="deepseek")
            tracker.return_value.record.assert_called_once()

    def test_track_llm_call_error_swallowed(self, handler):
        with patch("core.llm.byok_handler.get_llm_call_tracker", side_effect=RuntimeError("boom")):
            handler._track_llm_call("openai", "gpt-4o", True)  # no raise

    def test_monthly_tpm_limit(self, monkeypatch):
        monkeypatch.delenv("OPENCODE_MONTHLY_TPM", raising=False)
        assert BYOKHandler._monthly_tpm_limit(handler) is None
        monkeypatch.setenv("OPENCODE_MONTHLY_TPM", "5000000")
        assert BYOKHandler._monthly_tpm_limit(handler) == 5000000
        monkeypatch.setenv("OPENCODE_MONTHLY_TPM", "-5")
        assert BYOKHandler._monthly_tpm_limit(handler) is None
        monkeypatch.setenv("OPENCODE_MONTHLY_TPM", "not-a-number")
        assert BYOKHandler._monthly_tpm_limit(handler) is None

    def test_monthly_budget_exhausted(self, handler):
        handler.rate_tracker.get_monthly_usage.return_value = None
        assert handler._monthly_budget_exhausted("opencode-go", 1000) is False
        handler.rate_tracker.get_monthly_usage.return_value = {"total_tokens": 1500}
        assert handler._monthly_budget_exhausted("opencode-go", 1000) is True
        handler.rate_tracker.get_monthly_usage.return_value = {"total_tokens": 500}
        assert handler._monthly_budget_exhausted("opencode-go", 1000) is False
        handler.rate_tracker.get_monthly_usage.side_effect = RuntimeError("down")
        assert handler._monthly_budget_exhausted("opencode-go", 1000) is False


# ============================ context window / truncation ============================


class TestContext:
    def test_get_context_window(self, handler):
        fetcher = Mock()
        fetcher.get_model_price = Mock(return_value={"max_input_tokens": 64000})
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            assert handler.get_context_window("any-model") == 64000
        fetcher.get_model_price = Mock(return_value={"max_tokens": 32000})
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            assert handler.get_context_window("any-model") == 32000
        fetcher.get_model_price = Mock(return_value={})
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            assert handler.get_context_window("deepseek-chat") == 32768
        fetcher.get_model_price = Mock(return_value=None)
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            assert handler.get_context_window("unknown-xyz") == 4096

    def test_get_context_window_error(self, handler):
        fetcher = Mock()
        fetcher.get_model_price = Mock(side_effect=RuntimeError("boom"))
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            assert handler.get_context_window("gpt-4o") == 128000

    def test_truncate_no_truncation(self, handler):
        text = "short"
        assert handler.truncate_to_context(text, "gpt-4o", reserve_tokens=1000) == text

    def test_truncate_drops_middle(self, handler):
        handler.get_context_window = Mock(return_value=128000)
        text = "A" * 1000000
        out = handler.truncate_to_context(text, "gpt-4o", reserve_tokens=1000)
        assert len(out) < len(text)
        assert "Content truncated" in out
        assert out.endswith("A" * 100)
        assert out.startswith("A" * 100)

    def test_truncate_reserve_tokens(self, handler):
        handler.get_context_window = Mock(return_value=2000)
        text = "B" * 10000
        out = handler.truncate_to_context(text, "m", reserve_tokens=1500)
        assert "Content truncated" in out


# ============================ sanitize_tool_pairs ============================


class TestSanitizeToolPairs:
    def test_empty(self):
        assert BYOKHandler.sanitize_tool_pairs([]) == []

    def test_orphaned_tool_injects_stub(self):
        messages = [{"role": "tool", "tool_call_id": "t1", "content": "result"}]
        out = BYOKHandler.sanitize_tool_pairs(messages)
        assert out[0]["role"] == "assistant"
        assert out[0]["tool_calls"][0]["function"]["name"] == "_truncated_tool_call"
        assert out[1] == messages[0]

    def test_paired_tool_untouched(self):
        messages = [
            {"role": "assistant", "content": None, "tool_calls": [{"id": "t1"}]},
            {"role": "tool", "tool_call_id": "t1", "content": "result"},
        ]
        out = BYOKHandler.sanitize_tool_pairs(messages)
        assert len(out) == 2

    def test_trailing_tool_call_without_result_dropped(self):
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "t1"}]},
        ]
        out = BYOKHandler.sanitize_tool_pairs(messages)
        assert len(out) == 1
        assert out[0]["role"] == "user"

    def test_trailing_tool_call_with_content_kept(self):
        messages = [
            {"role": "assistant", "content": "text", "tool_calls": [{"id": "t1"}]},
        ]
        out = BYOKHandler.sanitize_tool_pairs(messages)
        assert len(out) == 1


# ============================ complexity / optimal provider ============================


class TestComplexity:
    def test_simple(self, handler):
        assert handler.analyze_query_complexity("hello how are you") == QueryComplexity.SIMPLE

    def test_moderate(self, handler):
        assert handler.analyze_query_complexity(
            "analyze and compare these two options in detail please"
        ) == QueryComplexity.MODERATE

    def test_complex_via_length(self, handler):
        assert handler.analyze_query_complexity("x" * 2000) == QueryComplexity.COMPLEX

    def test_advanced_via_length(self, handler):
        assert handler.analyze_query_complexity("```" + "x" * 9000) == QueryComplexity.ADVANCED

    def test_code_block_and_task_type(self, handler):
        assert handler.analyze_query_complexity("```\ncode\n```", task_type="code") in (
            QueryComplexity.COMPLEX, QueryComplexity.ADVANCED)
        assert handler.analyze_query_complexity("hi", task_type="chat") == QueryComplexity.SIMPLE
        assert handler.analyze_query_complexity("hi", task_type="general") == QueryComplexity.SIMPLE

    def test_optimal_provider_first_option(self, handler):
        handler.get_ranked_providers = Mock(return_value=[("deepseek", "deepseek-chat")])
        result = handler.get_optimal_provider(QueryComplexity.SIMPLE)
        assert result[0] == "deepseek"

    def test_optimal_provider_fallback(self, handler):
        handler.get_ranked_providers = Mock(return_value=[])
        result = handler.get_optimal_provider(QueryComplexity.SIMPLE)
        assert result == ("openai", "gpt-4o-mini")

    def test_optimal_provider_no_clients_raises(self, handler):
        handler.get_ranked_providers = Mock(return_value=[])
        handler.clients = {}
        with pytest.raises(NoProvidersConfiguredError):
            handler.get_optimal_provider(QueryComplexity.SIMPLE)

    def test_get_routing_info(self, handler):
        handler.get_optimal_provider = Mock(return_value=("deepseek", "deepseek-chat"))
        fetcher = Mock()
        fetcher.get_model_price = Mock(return_value={"input": 0.1})
        fetcher.estimate_cost = Mock(return_value=0.002)
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            info = handler.get_routing_info("hello")
        assert info["complexity"] == "simple"
        assert info["selected_provider"] == "deepseek"
        assert info["cost_tier"] == "budget"
        assert info["estimated_cost_usd"] == 0.002

    def test_get_routing_info_value_error(self, handler):
        handler.get_optimal_provider = Mock(side_effect=ValueError("no providers"))
        info = handler.get_routing_info("hello")
        assert "error" in info
        assert info["available_providers"] == []


# ============================ pricing helpers ============================


class TestPricing:
    async def test_refresh_pricing_success(self, handler):
        with patch("core.llm.byok_handler.refresh_pricing_cache", new=AsyncMock(return_value=[1, 2])):
            result = await handler.refresh_pricing()
        assert result == {"status": "success", "model_count": 2}

    async def test_refresh_pricing_error(self, handler):
        with patch("core.llm.byok_handler.refresh_pricing_cache", new=AsyncMock(
            side_effect=RuntimeError("boom"))):
            result = await handler.refresh_pricing()
        assert result["status"] == "error"

    def test_get_provider_comparison(self, handler):
        fetcher = Mock()
        fetcher.compare_providers = Mock(return_value={"deepseek": 1})
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            assert handler.get_provider_comparison() == {"deepseek": 1}

    def test_get_provider_comparison_fallback(self, handler):
        fetcher = Mock()
        fetcher.compare_providers = Mock(side_effect=RuntimeError("boom"))
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            result = handler.get_provider_comparison()
        assert result["deepseek"]["tier"] == "budget"

    def test_get_cheapest_models(self, handler):
        fetcher = Mock()
        fetcher.get_cheapest_models = Mock(return_value=[{"model_id": "m"}])
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            assert handler.get_cheapest_models() == [{"model_id": "m"}]

    def test_get_cheapest_models_error(self, handler):
        fetcher = Mock()
        fetcher.get_cheapest_models = Mock(side_effect=RuntimeError("boom"))
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            assert handler.get_cheapest_models() == []


# ============================ learning router hooks ============================


class TestLearningRouter:
    def test_adapt_task_type(self):
        assert BYOKHandler._adapt_task_type(None) == "general"
        assert BYOKHandler._adapt_task_type("chat") == "question_answering"
        assert BYOKHandler._adapt_task_type("reasoning") == "reasoning"
        assert BYOKHandler._adapt_task_type("agentic") == "tool_use"
        assert BYOKHandler._adapt_task_type("extraction") == "extraction"
        assert BYOKHandler._adapt_task_type("pdf_ocr") == "extraction"
        assert BYOKHandler._adapt_task_type("code") == "code_generation"
        assert BYOKHandler._adapt_task_type("meta_orchestration") == "tool_use"
        assert BYOKHandler._adapt_task_type("weird") == "general"
        assert BYOKHandler._adapt_task_type("  CODE ") == "code_generation"

    async def test_record_outcome_feedback_disabled(self, handler, monkeypatch):
        monkeypatch.delenv("ATOM_LEARNING_ROUTER", raising=False)
        await handler._record_outcome_feedback("m", "p", "chat", "content", "stop", True, 0.1, 10)
        # no raise, no router touched

    async def test_record_outcome_feedback_router_none(self, handler, monkeypatch):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        try:
            with patch("core.llm.learning_router_registry.get_learning_router_instance", return_value=None):
                await handler._record_outcome_feedback("m", "p", None, "c", "stop", True, None, 5)
        finally:
            monkeypatch.delenv("ATOM_LEARNING_ROUTER", raising=False)

    async def test_record_outcome_feedback_full(self, handler, monkeypatch):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        router = Mock()
        router.record_feedback = AsyncMock()
        try:
            with patch("core.llm.learning_router_registry.get_learning_router_instance", return_value=router), \
                 patch("core.llm.response_quality.assess_response_quality") as assess, \
                 patch("core.learning_llm_router.LearningBasedRouter.build_feedback",
                       return_value={"feedback": True}) as build:
                assess.return_value = SimpleNamespace(quality_score=0.8)
                await handler._record_outcome_feedback(
                    "m", "p", "code", "content", "stop", True, 0.1, 10,
                    routing_result_id="rid-1",
                )
            build.assert_called_once()
            router.record_feedback.assert_awaited_once()
        finally:
            monkeypatch.delenv("ATOM_LEARNING_ROUTER", raising=False)

    async def test_record_outcome_feedback_exception(self, handler, monkeypatch):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        try:
            with patch("core.llm.learning_router_registry.get_learning_router_instance",
                       side_effect=RuntimeError("boom")):
                await handler._record_outcome_feedback("m", "p", None, "c", None, False, None, 1)
        finally:
            monkeypatch.delenv("ATOM_LEARNING_ROUTER", raising=False)

    def test_stash_decision_features_disabled(self, handler, monkeypatch):
        monkeypatch.delenv("ATOM_LEARNING_ROUTER", raising=False)
        assert handler._stash_decision_features("prompt", "chat") is None

    def test_stash_decision_features_router_none(self, handler, monkeypatch):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        try:
            with patch("core.llm.learning_router_registry.get_learning_router_instance", return_value=None):
                assert handler._stash_decision_features("p", "chat") is None
        finally:
            monkeypatch.delenv("ATOM_LEARNING_ROUTER", raising=False)

    def test_stash_decision_features_full(self, handler, monkeypatch):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        router = Mock()
        router.stash_decision = Mock(return_value="decision-1")
        try:
            with patch("core.llm.learning_router_registry.get_learning_router_instance", return_value=router):
                assert handler._stash_decision_features("prompt here", "chat") == "decision-1"
        finally:
            monkeypatch.delenv("ATOM_LEARNING_ROUTER", raising=False)

    def test_stash_decision_features_error(self, handler, monkeypatch):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        try:
            with patch("core.llm.learning_router_registry.get_learning_router_instance",
                       side_effect=RuntimeError("boom")):
                assert handler._stash_decision_features("p", None) is None
        finally:
            monkeypatch.delenv("ATOM_LEARNING_ROUTER", raising=False)

    async def test_rerank_single_option(self, handler, monkeypatch):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        try:
            assert await handler._rerank_with_learning([("a", "m1")], "p", "chat") == [("a", "m1")]
        finally:
            monkeypatch.delenv("ATOM_LEARNING_ROUTER", raising=False)

    async def test_rerank_disabled(self, handler, monkeypatch):
        monkeypatch.delenv("ATOM_LEARNING_ROUTER", raising=False)
        options = [("a", "m1"), ("b", "m2")]
        assert await handler._rerank_with_learning(options, "p", "chat") == options

    async def test_rerank_cold_start(self, handler, monkeypatch):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        router = Mock()
        router._per_model_routers = {}
        try:
            with patch("core.llm.learning_router_registry.get_learning_router_instance", return_value=router):
                options = [("a", "m1"), ("b", "m2")]
                assert await handler._rerank_with_learning(options, "p", "chat") == options
        finally:
            monkeypatch.delenv("ATOM_LEARNING_ROUTER", raising=False)

    async def test_rerank_reorders(self, handler, monkeypatch):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        per_model = Mock()
        per_model.predict_satisfaction = Mock(return_value=1.0)
        per_model.confidence = Mock(return_value=1.0)
        router = Mock()
        router._per_model_routers = {"t-1:question_answering:_": per_model}
        router._extract_request_features = Mock(return_value={"features": True})
        try:
            with patch("core.llm.learning_router_registry.get_learning_router_instance", return_value=router), \
                 patch("core.llm.learning_router_registry.ema_router_enabled", return_value=False):
                out = await handler._rerank_with_learning(
                    [("a", "m1"), ("b", "m2")], "prompt", "chat"
                )
            assert len(out) == 2
            assert out[0] == ("a", "m1")
        finally:
            monkeypatch.delenv("ATOM_LEARNING_ROUTER", raising=False)

    async def test_rerank_error_returns_original(self, handler, monkeypatch):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        try:
            with patch("core.llm.learning_router_registry.get_learning_router_instance",
                       side_effect=RuntimeError("boom")):
                options = [("a", "m1"), ("b", "m2")]
                assert await handler._rerank_with_learning(options, "p", "chat") == options
        finally:
            monkeypatch.delenv("ATOM_LEARNING_ROUTER", raising=False)


# ============================ cognitive tier generation ============================


class TestCognitiveTierGeneration:
    def make_tier_service(self, **overrides):
        svc = Mock()
        svc.select_tier = Mock(return_value=CognitiveTier.STANDARD)
        svc.calculate_request_cost = Mock(return_value={"cost_cents": 5})
        svc.check_budget_constraint = Mock(return_value=True)
        svc.get_optimal_model = Mock(return_value=("deepseek", "deepseek-chat"))
        svc.handle_escalation = Mock(return_value=(False, None, None))
        for k, v in overrides.items():
            setattr(svc, k, v)
        return svc

    @pytest.mark.asyncio
    async def test_budget_exceeded(self, handler):
        handler.tier_service = self.make_tier_service(check_budget_constraint=Mock(return_value=False))
        result = await handler.generate_with_cognitive_tier("hello")
        assert result["error"] == "Budget exceeded"
        assert result["tier"] == CognitiveTier.STANDARD.value

    @pytest.mark.asyncio
    async def test_no_models(self, handler):
        handler.tier_service = self.make_tier_service(get_optimal_model=Mock(return_value=(None, None)))
        result = await handler.generate_with_cognitive_tier("hello")
        assert "No models" in result["error"]

    @pytest.mark.asyncio
    async def test_success(self, handler):
        handler.tier_service = self.make_tier_service()
        handler.generate_response = AsyncMock(return_value="good answer")
        with patch("core.llm.response_quality.assess_response_quality") as assess:
            assess.return_value = SimpleNamespace(quality_score=0.9)
            result = await handler.generate_with_cognitive_tier("hello", task_type="chat")
        assert result["response"] == "good answer"
        assert result["escalated"] is False
        assert result["model"] == "deepseek-chat"

    @pytest.mark.asyncio
    async def test_gen_failure_escalates(self, handler):
        svc = self.make_tier_service()
        svc.handle_escalation = Mock(side_effect=[
            (True, SimpleNamespace(value="quality"), CognitiveTier.VERSATILE),
            (False, SimpleNamespace(value="ok"), CognitiveTier.STANDARD),
        ])
        handler.tier_service = svc
        handler.generate_response = AsyncMock(side_effect=[
            "I'm sorry, I couldn't generate a response", "recovered answer"])
        result = await handler.generate_with_cognitive_tier("hello")
        assert result["escalated"] is True
        assert result["response"] == "recovered answer"

    @pytest.mark.asyncio
    async def test_quality_escalation_loop_success(self, handler):
        svc = self.make_tier_service()
        calls = {"n": 0}
        orig_handle = svc.handle_escalation

        def handle(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return True, SimpleNamespace(value="quality"), CognitiveTier.VERSATILE
            return False, SimpleNamespace(value="ok"), CognitiveTier.STANDARD

        svc.handle_escalation = Mock(side_effect=handle)
        handler.tier_service = svc
        handler.generate_response = AsyncMock(return_value="answer")
        with patch("core.llm.response_quality.assess_response_quality") as assess:
            assess.return_value = SimpleNamespace(quality_score=0.2)
            result = await handler.generate_with_cognitive_tier("hello")
        assert result["escalated"] is True
        assert result["response"] == "answer"

    @pytest.mark.asyncio
    async def test_exception_rate_limit_escalation(self, handler):
        svc = self.make_tier_service()
        svc.handle_escalation = Mock(return_value=(
            True, SimpleNamespace(value="rate_limit"), CognitiveTier.COMPLEX))
        handler.tier_service = svc
        handler.generate_response = AsyncMock(side_effect=RuntimeError("rate limit exceeded"))
        result = await handler.generate_with_cognitive_tier("hello")
        assert result["error"] == "rate limit exceeded"

    @pytest.mark.asyncio
    async def test_exception_no_escalation(self, handler):
        svc = self.make_tier_service()
        svc.handle_escalation = Mock(return_value=(False, None, None))
        handler.tier_service = svc
        handler.generate_response = AsyncMock(side_effect=RuntimeError("boom"))
        result = await handler.generate_with_cognitive_tier("hello")
        assert "boom" in result["error"]

    @pytest.mark.asyncio
    async def test_escalated_tier_no_models(self, handler):
        svc = self.make_tier_service()
        svc.handle_escalation = Mock(return_value=(
            True, SimpleNamespace(value="quality"), CognitiveTier.VERSATILE))
        svc.get_optimal_model = Mock(side_effect=[("deepseek", "deepseek-chat"), (None, None)])
        handler.tier_service = svc
        handler.generate_response = AsyncMock(return_value="answer")
        result = await handler.generate_with_cognitive_tier("hello")
        assert result["response"] == "answer"
        assert result["escalated"] is True

    @pytest.mark.asyncio
    async def test_exception_escalate_no_fallback(self, handler):
        svc = self.make_tier_service()
        svc.handle_escalation = Mock(return_value=(
            True, SimpleNamespace(value="rate_limit"), CognitiveTier.COMPLEX))
        svc.get_optimal_model = Mock(side_effect=[("deepseek", "m"), (None, None)])
        handler.tier_service = svc
        handler.generate_response = AsyncMock(side_effect=RuntimeError("rate limit"))
        result = await handler.generate_with_cognitive_tier("hello")
        assert "rate limit" in result["error"]


# ============================ transcription / vision ============================


class TestTranscription:
    @pytest.mark.asyncio
    async def test_no_client(self, handler):
        handler.async_clients = {}
        handler.clients = {}
        with pytest.raises(ValueError, match="not configured"):
            await handler.generate_transcription("file")

    @pytest.mark.asyncio
    async def test_success(self, handler):
        client = AsyncMock()
        client.client = client  # patched-by-instructor shape
        client.audio.transcriptions.create = AsyncMock(return_value=SimpleNamespace(text="hello"))
        handler.async_clients = {"openai": client}
        result = await handler.generate_transcription("file", language="en", prompt="p")
        assert result["text"] == "hello"
        assert result["provider"] == "openai"
        client.audio.transcriptions.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_failure_reraises(self, handler):
        client = AsyncMock()
        client.client = client
        client.audio.transcriptions.create = AsyncMock(side_effect=RuntimeError("whisper down"))
        handler.async_clients = {"openai": client}
        with pytest.raises(RuntimeError):
            await handler.generate_transcription("file")


class TestVision:
    @pytest.mark.asyncio
    async def test_gemini_selected(self, handler):
        client = Mock()
        client.chat.completions.create = Mock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="desc"))]))
        handler.clients = {"gemini": client}
        result = await handler._get_coordinated_vision_description("data", "free", True)
        assert result == "desc"

    @pytest.mark.asyncio
    async def test_deepseek_selected(self, handler):
        client = Mock()
        client.chat.completions.create = Mock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="d"))]))
        handler.clients = {"gemini": None, "deepseek": client}
        handler.clients.pop("gemini")
        result = await handler._get_coordinated_vision_description("http://img", "free", True)
        assert result == "d"

    @pytest.mark.asyncio
    async def test_openai_fallback_and_no_client(self, handler):
        client = Mock()
        client.chat.completions.create = Mock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="d"))]))
        handler.clients = {"openai": client}
        result = await handler._get_coordinated_vision_description("b64", "free", True)
        assert result == "d"
        handler.clients = {}
        assert await handler._get_coordinated_vision_description("b64", "free", True) is None

    @pytest.mark.asyncio
    async def test_error_returns_none(self, handler):
        client = Mock()
        client.chat.completions.create = Mock(side_effect=RuntimeError("vision down"))
        handler.clients = {"gemini": client}
        assert await handler._get_coordinated_vision_description("b64", "free", True) is None


# ============================ embeddings ============================


class TestEmbeddings:
    @pytest.mark.asyncio
    async def test_embedding_no_client(self, handler):
        handler.async_clients = {}
        handler.clients = {}
        with pytest.raises(ValueError, match="No client available"):
            await handler.generate_embedding("text", "m")

    @pytest.mark.asyncio
    async def test_embedding_openai(self, handler):
        client = AsyncMock()
        client.embeddings.create = AsyncMock(return_value=SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1, 0.2])]))
        handler.async_clients = {"openai": client}
        assert await handler.generate_embedding("text", "m") == [0.1, 0.2]

    @pytest.mark.asyncio
    async def test_embedding_cohere(self, handler):
        client = AsyncMock()
        client.embed = AsyncMock(return_value=SimpleNamespace(embeddings=[[0.5]]))
        handler.async_clients = {"cohere": client}
        assert await handler.generate_embedding("text", "m", provider="cohere") == [0.5]

    @pytest.mark.asyncio
    async def test_embedding_unsupported_provider(self, handler):
        client = AsyncMock()
        handler.async_clients = {"x": client}
        with pytest.raises(ValueError, match="does not support"):
            await handler.generate_embedding("text", "m", provider="x")

    @pytest.mark.asyncio
    async def test_embedding_error_reraises(self, handler):
        client = AsyncMock()
        client.embeddings.create = AsyncMock(side_effect=RuntimeError("emb down"))
        handler.async_clients = {"openai": client}
        with pytest.raises(RuntimeError):
            await handler.generate_embedding("text", "m")

    @pytest.mark.asyncio
    async def test_batch_no_client(self, handler):
        handler.async_clients = {}
        handler.clients = {}
        with pytest.raises(ValueError, match="No client available"):
            await handler.generate_embeddings_batch(["a"], "m")

    @pytest.mark.asyncio
    async def test_batch_openai(self, handler):
        client = AsyncMock()
        client.embeddings.create = AsyncMock(return_value=SimpleNamespace(
            data=[SimpleNamespace(embedding=[1.0]), SimpleNamespace(embedding=[2.0])]))
        handler.async_clients = {"openai": client}
        assert await handler.generate_embeddings_batch(["a", "b"], "m") == [[1.0], [2.0]]

    @pytest.mark.asyncio
    async def test_batch_cohere(self, handler):
        client = AsyncMock()
        client.embed = AsyncMock(return_value=SimpleNamespace(embeddings=[[1.0]]))
        handler.async_clients = {"cohere": client}
        assert await handler.generate_embeddings_batch(["a"], "m", provider="cohere") == [[1.0]]

    @pytest.mark.asyncio
    async def test_batch_unsupported(self, handler):
        client = AsyncMock()
        handler.async_clients = {"x": client}
        with pytest.raises(ValueError, match="does not support"):
            await handler.generate_embeddings_batch(["a"], "m", provider="x")


# ============================ misc ============================


class TestMisc:
    def test_classify_cognitive_tier(self, handler):
        handler.cognitive_classifier = Mock()
        handler.cognitive_classifier.classify = Mock(return_value=CognitiveTier.VERSATILE)
        assert handler.classify_cognitive_tier("prompt", "code") == CognitiveTier.VERSATILE
        handler.cognitive_classifier.classify.assert_called_once_with("prompt", "code")

    def test_is_trial_restricted(self, handler):
        db = Mock()
        workspace = Mock(trial_ended=True)
        db.query.return_value.filter.return_value.first.return_value = workspace
        with patch("core.llm.byok_handler.get_db_session") as gds:
            gds.return_value.__enter__.return_value = db
            assert handler._is_trial_restricted() is True
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.llm.byok_handler.get_db_session") as gds:
            gds.return_value.__enter__.return_value = db
            assert handler._is_trial_restricted() is False

    def test_is_trial_restricted_error(self, handler):
        with patch("core.llm.byok_handler.get_db_session", side_effect=RuntimeError("down")):
            assert handler._is_trial_restricted() is False
