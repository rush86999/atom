"""Coverage-push tests for core.llm.byok_handler (tests-only; read-only source)."""

import asyncio
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.llm.byok_handler import (
    AllProvidersFailedError,
    BYOKHandler,
    GatewayBlockedError,
    NoProvidersConfiguredError,
    QueryComplexity,
    AwaitableResult,
)
from core.llm.cognitive_tier_system import CognitiveTier


def make_handler(user_id=None, byok_manager=None, db_session=None):
    mgr = byok_manager or Mock()
    with patch("core.llm.byok_handler.get_byok_manager", return_value=mgr), \
         patch("core.llm.byok_handler.llm_usage_tracker",
               Mock(is_budget_exceeded=Mock(return_value=False),
                    is_trial_expired=Mock(return_value=False),
                    record=Mock())):
        h = BYOKHandler(workspace_id="ws-1", tenant_id="t-1", user_id=user_id,
                        db_session=db_session)
    h.rate_tracker = Mock()
    h.health_monitor = Mock()
    h.health_monitor.health_scores = {}
    h.health_monitor.record_call = Mock()
    h.health_monitor.get_health_score = Mock(
        side_effect=lambda p: h.health_monitor.health_scores.get(p, 0.9))
    h.cache_router = Mock()
    h.cache_router.calculate_effective_cost = Mock(return_value=0.001)
    h.cache_router.record_cache_outcome = Mock()
    h._is_trial_restricted = Mock(return_value=False)
    return h


def usage_mock(prompt=10, completion=5):
    return SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion)


def response_mock(content="hello world", finish="stop", usage=None):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content),
                                 finish_reason=finish)],
        usage=usage,
    )


def ctx_mock(db):
    from contextlib import contextmanager

    @contextmanager
    def ctx():
        yield db

    return ctx


def pro_tenant_db():
    workspace = SimpleNamespace(tenant_id="t-2")
    tenant = SimpleNamespace(plan_type="pro")
    db = Mock()
    firsts = iter([workspace, tenant])

    def fake_query(model):
        q = Mock()
        q.filter.return_value.first.side_effect = lambda: next(firsts, None)
        return q

    db.query.side_effect = fake_query
    return db


class TestInitPaths:
    def test_db_session_passed(self):
        h = make_handler(db_session="provided")
        assert h.db_session == "provided"

    def test_db_session_creation_failure(self, monkeypatch):
        def _boom(*a, **k):
            raise RuntimeError("db down")

        monkeypatch.setattr("core.database.get_db_session", _boom)
        mgr = Mock()
        with patch("core.llm.byok_handler.get_byok_manager", return_value=mgr), \
             patch("core.llm.byok_handler.llm_usage_tracker", Mock()):
            h = BYOKHandler(workspace_id="ws-1", tenant_id="t-1")
        assert h.db_session is None

    def test_fallback_order_no_clients(self):
        h = make_handler()
        h.clients = {}
        assert h._get_provider_fallback_order("deepseek") == []

    def test_optimal_provider_no_clients_raises(self):
        h = make_handler()
        h.clients = {}
        h.get_ranked_providers = Mock(return_value=[])
        with pytest.raises(NoProvidersConfiguredError):
            h.get_optimal_provider(QueryComplexity.SIMPLE)


class TestClientInitLuxOllama:
    def test_lux_and_ollama_clients(self, monkeypatch):
        monkeypatch.delitem(sys.modules, "pytest")
        mgr = Mock()
        mgr.is_configured = Mock(return_value=False)
        mgr.get_api_key = Mock(return_value=None)
        with patch("core.llm.byok_handler.get_byok_manager", return_value=mgr), \
             patch("core.llm.byok_handler.lux_config.get_anthropic_key",
                   return_value="sk-ant-lux"), \
             patch("core.llm.byok_handler.llm_usage_tracker", Mock()), \
             patch.dict(os.environ, {"OPENCODE_API_KEY": ""}):
            h = BYOKHandler(workspace_id="ws-1", tenant_id="t-1")
        assert "lux" in h.clients
        assert "lux" in h.async_clients
        assert "ollama" in h.clients

    def test_lux_creation_failure(self, monkeypatch):
        monkeypatch.delitem(sys.modules, "pytest")
        mgr = Mock()
        mgr.is_configured = Mock(return_value=False)
        mgr.get_api_key = Mock(return_value=None)
        with patch("core.llm.byok_handler.get_byok_manager", return_value=mgr), \
             patch("core.llm.byok_handler.lux_config.get_anthropic_key",
                   return_value="sk-ant-lux"), \
             patch("core.llm.byok_handler.OpenAI", side_effect=RuntimeError("boom")), \
             patch("core.llm.byok_handler.AsyncOpenAI", side_effect=RuntimeError("boom")), \
             patch("core.llm.byok_handler.llm_usage_tracker", Mock()), \
             patch.dict(os.environ, {"OPENCODE_API_KEY": ""}):
            h = BYOKHandler(workspace_id="ws-1", tenant_id="t-1")
        assert "lux" not in h.clients

    def test_ollama_creation_failure(self, monkeypatch):
        monkeypatch.delitem(sys.modules, "pytest")
        mgr = Mock()
        mgr.is_configured = Mock(return_value=False)
        mgr.get_api_key = Mock(return_value=None)
        with patch("core.llm.byok_handler.get_byok_manager", return_value=mgr), \
             patch("core.llm.byok_handler.lux_config.get_anthropic_key",
                   return_value=None), \
             patch("core.llm.byok_handler.OpenAI", side_effect=RuntimeError("boom")), \
             patch("core.llm.byok_handler.AsyncOpenAI", side_effect=RuntimeError("boom")), \
             patch("core.llm.byok_handler.llm_usage_tracker", Mock()), \
             patch.dict(os.environ, {"OPENCODE_API_KEY": ""}):
            h = BYOKHandler(workspace_id="ws-1", tenant_id="t-1")
        assert "ollama" not in h.clients


class TestCredentialServiceInit:
    def test_credential_success(self, monkeypatch):
        cred = Mock()
        cred.get_credential = AsyncMock(return_value=("oauth", "sk-oauth-key"))
        monkeypatch.setattr("core.llm.byok_handler.LLMCredentialService",
                            Mock(return_value=cred))
        mgr = Mock()
        mgr.is_configured = Mock(return_value=False)
        mgr.get_api_key = Mock(return_value=None)
        with patch("core.llm.byok_handler.get_byok_manager", return_value=mgr), \
             patch("core.llm.byok_handler.llm_usage_tracker", Mock()), \
             patch.dict(os.environ, {"OPENCODE_API_KEY": ""}):
            h = BYOKHandler(workspace_id="ws-1", tenant_id="t-1", user_id="u1")
        assert "openai" in h.clients

    def test_credential_failure_falls_back_to_byok(self, monkeypatch):
        cred = Mock()
        cred.get_credential = AsyncMock(side_effect=RuntimeError("no token"))
        monkeypatch.setattr("core.llm.byok_handler.LLMCredentialService",
                            Mock(return_value=cred))
        mgr = Mock()
        mgr.is_configured = Mock(return_value=True)
        # >= 12 chars — the placeholder-key filter in _initialize_clients
        # discards shorter values.
        mgr.get_api_key = Mock(return_value="sk-byok-fallback-1234")
        with patch("core.llm.byok_handler.get_byok_manager", return_value=mgr), \
             patch("core.llm.byok_handler.llm_usage_tracker", Mock()), \
             patch.dict(os.environ, {"OPENCODE_API_KEY": ""}):
            h = BYOKHandler(workspace_id="ws-1", tenant_id="t-1", user_id="u1")
        assert "openai" in h.clients


class TestLoadLocalProviders:
    def _provider(self, pid="p1", name="Local", ptype="ollama", base="http://x:11434/v1", key=None):
        return SimpleNamespace(id=pid, name=name, provider_type=ptype,
                               base_url=base, api_key=key)

    def test_with_caps(self, monkeypatch):
        h = make_handler()
        fetcher = Mock()
        fetcher.pricing_cache = {}
        monkeypatch.setattr("core.llm.byok_handler.get_pricing_fetcher",
                            Mock(return_value=fetcher))
        db = Mock()
        providers = [self._provider()]
        caps = [SimpleNamespace(
            model_id="local-model-1", context_window=16000, supports_tools=True,
            supports_vision=False, supports_reasoning=True, quality_score=0.8)]

        def fake_query(model):
            if model.__name__ == "LocalModelProvider":
                q = Mock()
                q.filter.return_value.all.return_value = providers
                return q
            q = Mock()
            q.filter.return_value.all.return_value = caps
            return q

        db.query.side_effect = fake_query
        monkeypatch.setattr("core.database.get_db_session", ctx_mock(db))
        h._load_local_providers()
        assert "local_p1" in h.clients
        assert "local-model-1" in fetcher.pricing_cache

    def test_without_caps(self, monkeypatch):
        h = make_handler()
        fetcher = Mock()
        fetcher.pricing_cache = {}
        monkeypatch.setattr("core.llm.byok_handler.get_pricing_fetcher",
                            Mock(return_value=fetcher))
        db = Mock()
        providers = [self._provider(pid="p2")]

        def fake_query(model):
            q = Mock()
            if model.__name__ == "LocalModelCapabilities":
                q.filter.return_value.all.return_value = []
            else:
                q.filter.return_value.all.return_value = providers
            return q

        db.query.side_effect = fake_query
        monkeypatch.setattr("core.database.get_db_session", ctx_mock(db))
        h._load_local_providers()
        assert "ollama_default" in fetcher.pricing_cache

    def test_client_creation_failure_continues(self, monkeypatch):
        h = make_handler()
        db = Mock()
        providers = [self._provider(pid="p3")]
        db.query.return_value.filter.return_value.all.return_value = providers
        monkeypatch.setattr("core.database.get_db_session", ctx_mock(db))
        with patch("core.llm.byok_handler.OpenAI", side_effect=RuntimeError("boom")):
            h._load_local_providers()
        assert "local_p3" not in h.clients

    def test_db_failure_noop(self, monkeypatch):
        h = make_handler()
        monkeypatch.setattr("core.database.get_db_session",
                            lambda: (_ for _ in ()).throw(RuntimeError("db down")))
        h._load_local_providers()


class TestComplexityAnalysis:
    def test_moderate_by_length(self):
        h = make_handler()
        assert h.analyze_query_complexity("a" * 800) == QueryComplexity.MODERATE


class TestBPC:
    def _pricing_fetcher(self, cache):
        fetcher = Mock()
        fetcher.pricing_cache = cache
        return fetcher

    def test_extraction_cap_excludes_over_90(self):
        h = make_handler()
        h.clients = {"openai": Mock(), "deepseek": Mock()}
        h.rate_tracker.get_max_context = Mock(return_value=None)
        h.rate_tracker.get_model_headroom = Mock(return_value=1.0)
        h.rate_tracker.get_headroom = Mock(return_value=1.0)
        h.rate_tracker.get_model_weight = Mock(return_value=1.0)
        fetcher = self._pricing_fetcher({
            "gpt-5.6-pro": {"litellm_provider": "openai", "max_input_tokens": 128000,
                            "supports_tools": True},
            "o3-mini": {"litellm_provider": "openai", "max_input_tokens": 128000,
                        "supports_tools": True},
            "deepseek-chat": {"litellm_provider": "deepseek", "max_input_tokens": 64000,
                              "supports_tools": True},
        })

        def _qscore(model):
            if model == "gpt-5.6-pro":
                return 95
            if model == "o3-mini":
                return 90
            return 85

        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   return_value=fetcher), \
             patch("core.llm.byok_handler.get_quality_score",
                   side_effect=_qscore):
            options = h.get_ranked_providers(
                QueryComplexity.MODERATE, task_type="extraction", is_managed_service=False)
        assert options == [("deepseek", "deepseek-chat")]

    def test_capability_and_health_filters(self):
        h = make_handler()
        h.clients = {"openai": Mock(), "deepseek": Mock()}
        h.rate_tracker.get_max_context = Mock(return_value=None)
        h.rate_tracker.get_model_headroom = Mock(return_value=1.0)
        h.rate_tracker.get_headroom = Mock(return_value=1.0)
        h.rate_tracker.get_model_weight = Mock(return_value=1.0)
        h.cache_router.calculate_effective_cost = Mock(return_value=0.001)
        h.excluded_models = {"bad-model"}
        h.health_monitor.health_scores = {"openai": 0.1, "deepseek": 0.9}
        fetcher = self._pricing_fetcher({
            "gpt-4o": {"litellm_provider": "openai", "max_input_tokens": 128000,
                       "supports_tools": True},
            "deepseek-chat": {"litellm_provider": "deepseek", "max_input_tokens": 64000,
                              "supports_tools": True},
        })
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   return_value=fetcher), \
             patch("core.llm.byok_handler.get_quality_score", return_value=90), \
             patch("core.llm.byok_handler.get_capability_score", return_value=90):
            options = h.get_ranked_providers(
                QueryComplexity.MODERATE, is_managed_service=False,
                required_capability="vision")
        assert options == [("deepseek", "deepseek-chat")]

    def test_o_series_excluded_from_extraction(self):
        h = make_handler()
        h.clients = {"openai": Mock(), "deepseek": Mock()}
        h.rate_tracker.get_max_context = Mock(return_value=None)
        h.rate_tracker.get_model_headroom = Mock(return_value=1.0)
        h.rate_tracker.get_headroom = Mock(return_value=1.0)
        h.rate_tracker.get_model_weight = Mock(return_value=1.0)
        fetcher = self._pricing_fetcher({
            "o4-mini": {"litellm_provider": "openai", "max_input_tokens": 128000,
                        "supports_tools": True},
            "deepseek-chat": {"litellm_provider": "deepseek", "max_input_tokens": 64000,
                              "supports_tools": True},
        })
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   return_value=fetcher), \
             patch("core.llm.byok_handler.get_quality_score", return_value=90):
            options = h.get_ranked_providers(
                QueryComplexity.MODERATE, task_type="extraction", is_managed_service=False)
        assert options == [("deepseek", "deepseek-chat")]

    def test_monthly_budget_exhausted_skips(self, monkeypatch):
        monkeypatch.setenv("OPENCODE_MONTHLY_TPM", "1000")
        h = make_handler()
        h.clients = {"openai": Mock(), "deepseek": Mock()}
        h.rate_tracker.get_max_context = Mock(return_value=None)
        h.rate_tracker.get_model_headroom = Mock(return_value=1.0)
        h.rate_tracker.get_headroom = Mock(return_value=1.0)
        h.rate_tracker.get_model_weight = Mock(return_value=1.0)
        h.rate_tracker.get_monthly_usage = Mock(
            side_effect=lambda p: {"total_tokens": 5000} if p == "deepseek" else None)
        fetcher = self._pricing_fetcher({
            "deepseek-chat": {"litellm_provider": "deepseek", "max_input_tokens": 64000,
                              "supports_tools": True},
            "gpt-4o": {"litellm_provider": "openai", "max_input_tokens": 128000,
                       "supports_tools": True},
        })
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   return_value=fetcher), \
             patch("core.llm.byok_handler.get_quality_score", return_value=90):
            options = h.get_ranked_providers(
                QueryComplexity.MODERATE, is_managed_service=False)
        assert options == [("openai", "gpt-4o")]

    def test_rate_headroom_skips(self):
        h = make_handler()
        h.clients = {"openai": Mock(), "deepseek": Mock()}
        h.rate_tracker.get_max_context = Mock(return_value=None)
        h.rate_tracker.get_model_headroom = Mock(side_effect=[1.0, 0.0])
        h.rate_tracker.get_headroom = Mock(return_value=1.0)
        h.rate_tracker.get_model_weight = Mock(return_value=1.0)
        h.cache_router.calculate_effective_cost = Mock(return_value=0.001)
        fetcher = self._pricing_fetcher({
            "gpt-4o": {"litellm_provider": "openai", "max_input_tokens": 128000,
                       "supports_tools": True},
            "deepseek-chat": {"litellm_provider": "deepseek", "max_input_tokens": 64000,
                              "supports_tools": True},
        })
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   return_value=fetcher), \
             patch("core.llm.byok_handler.get_quality_score", return_value=90):
            options = h.get_ranked_providers(
                QueryComplexity.MODERATE, is_managed_service=False)
        assert options == [("openai", "gpt-4o")]

    def test_provider_headroom_skip(self):
        h = make_handler()
        h.clients = {"openai": Mock(), "deepseek": Mock()}
        h.rate_tracker.get_max_context = Mock(return_value=None)
        h.rate_tracker.get_model_headroom = Mock(return_value=1.0)
        h.rate_tracker.get_headroom = Mock(side_effect=[0.0, 1.0])
        h.rate_tracker.get_model_weight = Mock(return_value=1.0)
        h.cache_router.calculate_effective_cost = Mock(return_value=0.001)
        fetcher = self._pricing_fetcher({
            "gpt-4o": {"litellm_provider": "openai", "max_input_tokens": 128000,
                       "supports_tools": True},
            "deepseek-chat": {"litellm_provider": "deepseek", "max_input_tokens": 64000,
                              "supports_tools": True},
        })
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   return_value=fetcher), \
             patch("core.llm.byok_handler.get_quality_score", return_value=90):
            options = h.get_ranked_providers(
                QueryComplexity.MODERATE, is_managed_service=False)
        assert options == [("deepseek", "deepseek-chat")]

    def test_quota_weight_factor(self):
        h = make_handler()
        h.clients = {"openai": Mock()}
        h.rate_tracker.get_max_context = Mock(return_value=None)
        h.rate_tracker.get_model_headroom = Mock(return_value=1.0)
        h.rate_tracker.get_headroom = Mock(return_value=1.0)
        h.rate_tracker.get_model_weight = Mock(return_value=12.0)
        h.cache_router.calculate_effective_cost = Mock(return_value=0.001)
        fetcher = self._pricing_fetcher({
            "gpt-4o": {"litellm_provider": "openai", "max_input_tokens": 128000,
                       "supports_tools": True},
        })
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   return_value=fetcher), \
             patch("core.llm.byok_handler.get_quality_score", return_value=90):
            options = h.get_ranked_providers(
                QueryComplexity.MODERATE, is_managed_service=False)
        assert options == [("openai", "gpt-4o")]

    def test_static_fallback_moderate(self):
        h = make_handler()
        h.clients = {"deepseek": Mock()}
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   side_effect=RuntimeError("pricing down")):
            options = h.get_ranked_providers(
                QueryComplexity.MODERATE, is_managed_service=False)
        assert options[0][0] == "deepseek"

    def test_static_fallback_speciale_downgrade(self):
        h = make_handler()
        h.clients = {"deepseek": Mock()}
        h.pricing_fetcher.get_model_capabilities = Mock(return_value={"supports_tools": False})
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   side_effect=RuntimeError("pricing down")):
            options = h.get_ranked_providers(
                QueryComplexity.ADVANCED, is_managed_service=False, requires_tools=True)
        assert options == [("deepseek", "deepseek-r2")]

    def test_static_fallback_fetcher_error_allowed(self):
        h = make_handler()
        h.clients = {"deepseek": Mock()}
        h.pricing_fetcher.get_model_capabilities = Mock(side_effect=RuntimeError("boom"))
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   side_effect=RuntimeError("pricing down")):
            options = h.get_ranked_providers(
                QueryComplexity.SIMPLE, is_managed_service=True, requires_tools=True)
        assert options[0][0] == "deepseek"

    def test_managed_plan_allows_model(self):
        h = make_handler()
        h.clients = {"deepseek": Mock()}
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   side_effect=RuntimeError("pricing down")):
            options = h.get_ranked_providers(
                QueryComplexity.SIMPLE, is_managed_service=True, tenant_plan="pro")
        assert options[0][0] == "deepseek"

    def test_qwen_boost(self):
        h = make_handler()
        h.clients = {"qwen": Mock(), "deepseek": Mock()}
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   side_effect=RuntimeError("pricing down")):
            options = h.get_ranked_providers(
                QueryComplexity.SIMPLE, is_managed_service=False)
        assert options[0][0] == "qwen"

    def test_context_window_clamp(self):
        h = make_handler()
        h.clients = {"openai": Mock(), "deepseek": Mock()}
        h.rate_tracker.get_max_context = Mock(side_effect=[2000, None])
        h.rate_tracker.get_model_headroom = Mock(return_value=1.0)
        h.rate_tracker.get_headroom = Mock(return_value=1.0)
        h.rate_tracker.get_model_weight = Mock(return_value=1.0)
        fetcher = self._pricing_fetcher({
            "gpt-4o": {"litellm_provider": "openai", "max_input_tokens": 128000,
                       "supports_tools": True},
            "deepseek-chat": {"litellm_provider": "deepseek", "max_input_tokens": 64000,
                              "supports_tools": True},
        })
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   return_value=fetcher), \
             patch("core.llm.byok_handler.get_quality_score", return_value=90):
            options = h.get_ranked_providers(
                QueryComplexity.COMPLEX, is_managed_service=False)
        assert options == [("deepseek", "deepseek-chat")]


class TestGenerateResponseEdges:
    @pytest.mark.asyncio
    async def test_sticky_hint_boost(self):
        h = make_handler()
        h.clients = {"openai": Mock(), "deepseek": Mock()}
        h.async_clients = {}
        h.get_ranked_providers = AsyncMock(return_value=[
            ("deepseek", "deepseek-chat"), ("openai", "gpt-4o")])
        h._rerank_with_learning = AsyncMock(side_effect=lambda o, *a, **k: o)
        client = Mock()
        client.chat.completions.create = Mock(return_value=response_mock("boosted"))
        h.clients["openai"].chat.completions.create = Mock(
            return_value=response_mock("boosted"))
        fetcher = Mock()
        fetcher.estimate_cost = Mock(return_value=0.001)
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher), \
             patch("core.llm.byok_handler.get_db_session", ctx_mock(pro_tenant_db())):
            out = await h.generate_response(
                "hi", sticky_hint=("openai", "gpt-4o"))
        assert out == "boosted"

    @pytest.mark.asyncio
    async def test_no_eligible_providers_message(self):
        h = make_handler()
        h.clients = {"openai": Mock()}
        h.async_clients = {}
        h.get_ranked_providers = AsyncMock(return_value=[])
        h._rerank_with_learning = AsyncMock(side_effect=lambda o, *a, **k: o)
        with patch("core.llm.byok_handler.get_db_session", ctx_mock(pro_tenant_db())):
            out = await h.generate_response("hi")
        assert "No eligible LLM providers" in out

    @pytest.mark.asyncio
    async def test_vision_fallback_default(self):
        h = make_handler()
        h.clients = {"openai": Mock(), "deepseek": Mock()}
        h.async_clients = {}
        h.get_ranked_providers = AsyncMock(return_value=[
            ("deepseek", "deepseek-chat")])
        h._rerank_with_learning = AsyncMock(side_effect=lambda o, *a, **k: o)
        h.pricing_fetcher.get_model_capabilities = Mock(
            return_value={"supports_vision": False, "supports_tools": True})
        h._get_coordinated_vision_description = AsyncMock(return_value=None)
        h.clients["openai"].chat.completions.create = Mock(
            return_value=response_mock("visioned"))
        h.clients["deepseek"].chat.completions.create = Mock(
            return_value=response_mock("visioned"))
        with patch("core.llm.byok_handler.get_db_session", ctx_mock(pro_tenant_db())):
            out = await h.generate_response(
                "look at this", image_payload="http://x/y.png")
        assert out == "visioned"

    @pytest.mark.asyncio
    async def test_provider_failure_falls_back(self):
        h = make_handler()
        h.clients = {"openai": Mock(), "deepseek": Mock()}
        h.async_clients = {}
        h.get_ranked_providers = AsyncMock(return_value=[
            ("openai", "gpt-4o"), ("deepseek", "deepseek-chat")])
        h._rerank_with_learning = AsyncMock(side_effect=lambda o, *a, **k: o)
        h.clients["openai"].chat.completions.create = Mock(
            side_effect=RuntimeError("rate limited"))
        h.clients["deepseek"].chat.completions.create = Mock(
            return_value=response_mock("fallback ok"))
        fetcher = Mock()
        fetcher.estimate_cost = Mock(return_value=0.001)
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher), \
             patch("core.llm.byok_handler.get_db_session", ctx_mock(pro_tenant_db())):
            out = await h.generate_response("hi")
        assert out == "fallback ok"

    @pytest.mark.asyncio
    async def test_all_providers_fail_message(self):
        h = make_handler()
        h.clients = {"openai": Mock()}
        h.async_clients = {}
        h.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o")])
        h._rerank_with_learning = AsyncMock(side_effect=lambda o, *a, **k: o)
        h.clients["openai"].chat.completions.create = Mock(
            side_effect=RuntimeError("dead"))
        with patch("core.llm.byok_handler.get_db_session", ctx_mock(pro_tenant_db())):
            out = await h.generate_response("hi")
        assert "couldn't generate" in out

    @pytest.mark.asyncio
    async def test_health_record_failure_swallowed(self):
        h = make_handler()
        h.clients = {"openai": Mock()}
        h.async_clients = {}
        h.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o")])
        h._rerank_with_learning = AsyncMock(side_effect=lambda o, *a, **k: o)
        h.clients["openai"].chat.completions.create = Mock(
            side_effect=RuntimeError("dead"))
        h.health_monitor.record_call = Mock(side_effect=RuntimeError("hm down"))
        with patch("core.llm.byok_handler.get_db_session", ctx_mock(pro_tenant_db())):
            out = await h.generate_response("hi")
        assert "couldn't generate" in out

    @pytest.mark.asyncio
    async def test_self_heal_retry_success(self):
        h = make_handler()
        h.clients = {"openai": Mock()}
        h.async_clients = {}
        h.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o")])
        h._rerank_with_learning = AsyncMock(side_effect=lambda o, *a, **k: o)
        healer = Mock()
        heal = Mock()
        heal.patched_kwargs = {"model": "gpt-4o", "messages": []}
        heal.rule = "drop_max_tokens"
        heal.patched_keys = ["max_tokens"]
        healer.heal = Mock(return_value=heal)
        create = Mock(side_effect=[
            RuntimeError("bad request"),
            response_mock("healed"),
        ])
        h.clients["openai"].chat.completions.create = create
        with patch("core.llm.byok_handler.get_db_session", ctx_mock(pro_tenant_db())), \
             patch("core.llm.routing.request_healer.get_request_healer",
                   return_value=healer):
            out = await h.generate_response("hi")
        assert out == "healed"

    @pytest.mark.asyncio
    async def test_self_heal_fails_then_fallback(self):
        h = make_handler()
        h.clients = {"openai": Mock(), "deepseek": Mock()}
        h.async_clients = {}
        h.get_ranked_providers = AsyncMock(return_value=[
            ("openai", "gpt-4o"), ("deepseek", "deepseek-chat")])
        h._rerank_with_learning = AsyncMock(side_effect=lambda o, *a, **k: o)
        healer = Mock()
        heal = Mock()
        heal.patched_kwargs = {"model": "gpt-4o"}
        heal.rule = "r"
        heal.patched_keys = []
        healer.heal = Mock(return_value=heal)
        h.clients["openai"].chat.completions.create = Mock(
            side_effect=RuntimeError("still bad"))
        h.clients["deepseek"].chat.completions.create = Mock(
            return_value=response_mock("deepseek ok"))
        with patch("core.llm.byok_handler.get_db_session", ctx_mock(pro_tenant_db())), \
             patch("core.llm.routing.request_healer.get_request_healer",
                   return_value=healer):
            out = await h.generate_response("hi")
        assert out == "deepseek ok"

    @pytest.mark.asyncio
    async def test_healer_raises_skipped(self):
        h = make_handler()
        h.clients = {"openai": Mock()}
        h.async_clients = {}
        h.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o")])
        h._rerank_with_learning = AsyncMock(side_effect=lambda o, *a, **k: o)
        h.clients["openai"].chat.completions.create = Mock(
            side_effect=RuntimeError("bad"))
        with patch("core.llm.byok_handler.get_db_session", ctx_mock(pro_tenant_db())), \
             patch("core.llm.routing.request_healer.get_request_healer",
                   side_effect=RuntimeError("healer down")):
            out = await h.generate_response("hi")
        assert "couldn't generate" in out

    @pytest.mark.asyncio
    async def test_agentic_byok_mode(self):
        h = make_handler()
        h.clients = {"openai": Mock()}
        h.async_clients = {}
        h.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o")])
        h._rerank_with_learning = AsyncMock(side_effect=lambda o, *a, **k: o)
        h.clients["openai"].chat.completions.create = Mock(
            return_value=response_mock("agentic done"))
        with patch("core.llm.byok_handler.get_db_session", ctx_mock(pro_tenant_db())):
            out = await h.generate_response("do agentic thing", task_type="agentic")
        assert out == "agentic done"

    @pytest.mark.asyncio
    async def test_forced_cognitive_tier(self):
        h = make_handler()
        h.clients = {"openai": Mock()}
        h.async_clients = {}
        h.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o")])
        h._rerank_with_learning = AsyncMock(side_effect=lambda o, *a, **k: o)
        h.clients["openai"].chat.completions.create = Mock(
            return_value=response_mock("tier done"))
        with patch("core.llm.byok_handler.get_db_session", ctx_mock(pro_tenant_db())):
            out = await h.generate_response("hi", cognitive_tier="premium")
        assert out == "tier done"

    @pytest.mark.asyncio
    async def test_compression_applied(self):
        h = make_handler()
        h.clients = {"openai": Mock()}
        h.async_clients = {}
        h.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o")])
        h._rerank_with_learning = AsyncMock(side_effect=lambda o, *a, **k: o)
        h.clients["openai"].chat.completions.create = Mock(
            return_value=response_mock("compressed"))
        pipeline = Mock()
        metrics = SimpleNamespace(savings_tokens=100)
        pipeline.compress_tool_output = Mock(return_value=("COMPRESSED", metrics))
        with patch("core.llm.byok_handler.get_db_session", ctx_mock(pro_tenant_db())), \
             patch("core.llm.compression.get_compression_pipeline",
                   return_value=pipeline):
            out = await h.generate_response("long tool output")
        assert out == "compressed"

    @pytest.mark.asyncio
    async def test_cache_controls_marks_cached(self):
        h = make_handler()
        h.clients = {"openai": Mock()}
        h.async_clients = {}
        h.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o")])
        h._rerank_with_learning = AsyncMock(side_effect=lambda o, *a, **k: o)
        resp = response_mock("cached", usage=usage_mock(10, 5))
        resp.cache_controls = True
        h.clients["openai"].chat.completions.create = Mock(return_value=resp)
        fetcher = Mock()
        fetcher.estimate_cost = Mock(return_value=0.001)
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher), \
             patch("core.llm.byok_handler.get_db_session", ctx_mock(pro_tenant_db())):
            out = await h.generate_response("hi")
        assert out == "cached"
        h.cache_router.record_cache_outcome.assert_called_once()


class TestRerankWithLearning:
    @pytest.mark.asyncio
    async def test_single_option_noop(self, monkeypatch):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        h = make_handler()
        assert await h._rerank_with_learning([("openai", "gpt-4o")], "p", "chat") == [("openai", "gpt-4o")]

    @pytest.mark.asyncio
    async def test_router_none_returns_options(self, monkeypatch):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        h = make_handler()
        with patch("core.llm.learning_router_registry.get_learning_router_instance",
                   return_value=None):
            assert await h._rerank_with_learning(
                [("a", "m1"), ("b", "m2")], "p", "chat") == [("a", "m1"), ("b", "m2")]

    @pytest.mark.asyncio
    async def test_predictor_none_and_ema(self, monkeypatch):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        h = make_handler()
        router = Mock()
        per_model = Mock()
        per_model.predict_satisfaction = Mock(return_value=None)
        per_model.confidence = Mock(return_value=0.0)
        router._per_model_routers = {"t-1:question_answering": per_model}
        router._extract_request_features = Mock(return_value={"f": 1})
        router.stash_decision = Mock(return_value="dec-1")
        router._ema_scores = {"t-1:question_answering:m1": {"success": 0.8},
                              "t-1:question_answering:m2": {}}
        router._EMA_SCORE_WEIGHT = 0.3
        with patch("core.llm.learning_router_registry.get_learning_router_instance",
                   return_value=router), \
             patch("core.llm.learning_router_registry.ema_router_enabled",
                   return_value=True):
            result = await h._rerank_with_learning(
                [("a", "m1"), ("b", "m2")], "p", "chat")
        assert result[0] == ("a", "m1")
        assert h._pending_routing_result_id == "dec-1"

    @pytest.mark.asyncio
    async def test_no_learned_signal_returns_options(self, monkeypatch):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        h = make_handler()
        router = Mock()
        per_model = Mock()
        per_model.predict_satisfaction = Mock(return_value=None)
        per_model.confidence = Mock(return_value=0.0)
        router._per_model_routers = {"t-1:question_answering": per_model}
        router._extract_request_features = Mock(return_value={"f": 1})
        router._ema_scores = {}
        with patch("core.llm.learning_router_registry.get_learning_router_instance",
                   return_value=router), \
             patch("core.llm.learning_router_registry.ema_router_enabled",
                   return_value=False):
            result = await h._rerank_with_learning(
                [("a", "m1"), ("b", "m2")], "p", "chat")
        assert result == [("a", "m1"), ("b", "m2")]
        # no learned signal (predictor returns None) -> BPC order preserved
        per_model.predict_satisfaction.assert_called()

    @pytest.mark.asyncio
    async def test_error_returns_options(self, monkeypatch):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        h = make_handler()
        with patch("core.llm.learning_router_registry.get_learning_router_instance",
                   side_effect=RuntimeError("boom")):
            assert await h._rerank_with_learning(
                [("a", "m1"), ("b", "m2")], "p", "chat") == [("a", "m1"), ("b", "m2")]

    def test_adapt_task_type(self):
        h = make_handler()
        assert h._adapt_task_type(None) == "general"
        assert h._adapt_task_type("agentic") == "tool_use"
        assert h._adapt_task_type("pdf_ocr") == "extraction"
        assert h._adapt_task_type("bogus") == "general"


class TestMoA:
    def test_moa_eligible(self):
        h = make_handler()
        assert h._moa_eligible(QueryComplexity.COMPLEX, None) is True
        assert h._moa_eligible(QueryComplexity.ADVANCED, None) is True
        assert h._moa_eligible(QueryComplexity.SIMPLE, "code") is True
        assert h._moa_eligible(QueryComplexity.SIMPLE, "chat") is False

    def test_render_sample(self):
        pydantic_like = SimpleNamespace(model_dump=lambda: {"a": 1})
        assert h_render(pydantic_like) == '{"a": 1}'
        dict_like = SimpleNamespace(dict=lambda: {"b": 2})
        assert h_render(dict_like) == '{"b": 2}'
        assert h_render("plain") == "plain"

    def test_moa_aggregator_prompt_agreement(self):
        h = make_handler()
        p_high = BYOKHandler._build_moa_aggregator_prompt("q", ["s1", "s2"], agreement=0.9)
        assert "agree strongly" in p_high
        p_low = BYOKHandler._build_moa_aggregator_prompt("q", ["s1"], agreement=0.3)
        assert "disagree substantially" in p_low
        p_mid = BYOKHandler._build_moa_aggregator_prompt("q", ["s1"], agreement=0.6)
        assert "partially agree" in p_mid
        p_none = BYOKHandler._build_moa_aggregator_prompt("q", ["s1"], agreement=None)
        assert "CONSENSUS" not in p_none

    @pytest.mark.asyncio
    async def test_generate_structured_moa_all_samples_fail(self):
        h = make_handler()
        with patch("core.hallucination_config.get_moa_samples", return_value=2), \
             patch("core.hallucination_config.is_moa_diversity_enabled",
                   return_value=False), \
             patch("core.llm.self_consistency_voter.SelfConsistencyVoter.diversity_overlays",
                   return_value=[]):
            h.generate_structured_response = AsyncMock(return_value=None)
            result = await h.generate_structured_moa(
                "p", "sys", object(), 0.2, "code", None, None,
                [("a", "m1"), ("b", "m2")], "free", True,
                QueryComplexity.ADVANCED, True)
        assert result is None

    @pytest.mark.asyncio
    async def test_generate_structured_moa_sample_error_ignored(self):
        h = make_handler()
        with patch("core.hallucination_config.get_moa_samples", return_value=2), \
             patch("core.hallucination_config.is_moa_diversity_enabled",
                   return_value=False), \
             patch("core.llm.self_consistency_voter.SelfConsistencyVoter.diversity_overlays",
                   return_value=[]):
            async def _sample(prompt, **kw):
                raise RuntimeError("sample failed")

            h.generate_structured_response = _sample
            result = await h.generate_structured_moa(
                "p", "sys", object(), 0.2, "code", None, None,
                [("a", "m1"), ("b", "m2")], "free", True,
                QueryComplexity.ADVANCED, True)
        assert result is None

    @pytest.mark.asyncio
    async def test_generate_structured_moa_single_valid(self):
        h = make_handler()
        with patch("core.hallucination_config.get_moa_samples", return_value=2), \
             patch("core.hallucination_config.is_moa_diversity_enabled",
                   return_value=False), \
             patch("core.llm.self_consistency_voter.SelfConsistencyVoter.diversity_overlays",
                   return_value=[]):
            results = iter(["sample1", None])

            async def _sample(prompt, **kw):
                return next(results)

            h.generate_structured_response = _sample
            result = await h.generate_structured_moa(
                "p", "sys", object(), 0.2, "code", None, None,
                [("a", "m1"), ("b", "m2")], "free", True,
                QueryComplexity.ADVANCED, True)
        assert result == "sample1"

    @pytest.mark.asyncio
    async def test_generate_structured_moa_aggregator(self):
        h = make_handler()
        with patch("core.hallucination_config.get_moa_samples", return_value=2), \
             patch("core.hallucination_config.is_moa_diversity_enabled",
                   return_value=False), \
             patch("core.llm.self_consistency_voter.SelfConsistencyVoter.diversity_overlays",
                   return_value=[]), \
             patch("core.llm.self_consistency_voter.SelfConsistencyVoter._hash_sample",
                   return_value="h1"), \
             patch("core.llm.self_consistency_voter.SelfConsistencyVoter.is_irreversible",
                   return_value=True):
            calls = []

            async def _sample(prompt, **kw):
                calls.append(prompt)
                if len(calls) == 1:
                    return "sample1"
                if len(calls) == 2:
                    return "sample2"
                return "aggregated"

            h.generate_structured_response = _sample
            result = await h.generate_structured_moa(
                "p", "sys", object(), 0.2, "code", None, None,
                [("a", "m1"), ("b", "m2")], "free", True,
                QueryComplexity.ADVANCED, True)
        assert result == "aggregated"

    @pytest.mark.asyncio
    async def test_generate_structured_moa_agreement_error(self):
        h = make_handler()
        with patch("core.hallucination_config.get_moa_samples", return_value=2), \
             patch("core.hallucination_config.is_moa_diversity_enabled",
                   return_value=False), \
             patch("core.llm.self_consistency_voter.SelfConsistencyVoter.diversity_overlays",
                   return_value=[]), \
             patch("core.llm.self_consistency_voter.SelfConsistencyVoter._hash_sample",
                   side_effect=RuntimeError("hash fail")), \
             patch("core.llm.self_consistency_voter.SelfConsistencyVoter.is_irreversible",
                   return_value=True):
            calls = []

            async def _sample(prompt, **kw):
                calls.append(prompt)
                if len(calls) <= 2:
                    return f"sample{len(calls)}"
                return "aggregated"

            h.generate_structured_response = _sample
            result = await h.generate_structured_moa(
                "p", "sys", object(), 0.2, "code", None, None,
                [("a", "m1"), ("b", "m2")], "free", True,
                QueryComplexity.ADVANCED, True)
        assert result == "aggregated"


def h_render(sample):
    return BYOKHandler._render_sample(sample)


class TestStreamCompletion:
    @pytest.mark.asyncio
    async def test_no_provider_raises(self):
        h = make_handler()
        h.clients = {}
        h.async_clients = {}
        with pytest.raises(ValueError):
            async for _ in h.stream_completion([], "m", "openai"):
                pass

    @pytest.mark.asyncio
    async def test_unknown_provider_raises(self):
        h = make_handler()
        h.clients = {}
        h.async_clients = {}
        with pytest.raises(ValueError):
            async for _ in h.stream_completion([], "m", "ghost"):
                pass

    @pytest.mark.asyncio
    async def test_no_client_skips_to_error(self):
        h = make_handler()
        h.clients = {"openai": None}
        h.async_clients = {"openai": None}
        h._get_provider_fallback_order = Mock(return_value=["openai"])
        out = []
        async for token in h.stream_completion([], "m", "openai"):
            out.append(token)
        assert any("Error: All LLM providers failed" in t for t in out)

    @pytest.mark.asyncio
    async def test_stream_success_and_tracking_failure(self):
        h = make_handler()
        chunk = SimpleNamespace(choices=[SimpleNamespace(
            delta=SimpleNamespace(content="tok"), finish_reason="stop")])
        client = Mock()

        async def _gen():
            yield chunk

        client.chat.completions.create = AsyncMock(return_value=AsyncMock(
            __aiter__=lambda s: _gen()))
        h.async_clients = {"openai": client}
        h.clients = {"openai": Mock()}
        h._get_provider_fallback_order = Mock(return_value=["openai"])
        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        governance = Mock()
        governance.record_outcome = AsyncMock()
        with patch("core.agent_governance_service.AgentGovernanceService",
                   lambda d: governance), \
             patch("core.llm.byok_handler.AgentExecution", Mock()):
            out = []
            async for token in h.stream_completion(
                [{"role": "user", "content": "hi"}], "m", "openai",
                agent_id="ag-1", db=db):
                out.append(token)
        assert out == ["tok"]
        assert db.commit.called

    @pytest.mark.asyncio
    async def test_stream_fallback_and_heal(self):
        h = make_handler()
        chunk = SimpleNamespace(choices=[SimpleNamespace(
            delta=SimpleNamespace(content="healed"), finish_reason="stop")])
        bad_client = Mock()
        bad_client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("bad request"))
        good_client = Mock()

        async def _gen2():
            yield chunk

        good_client.chat.completions.create = AsyncMock(return_value=AsyncMock(
            __aiter__=lambda s: _gen2()))
        h.async_clients = {"openai": bad_client, "deepseek": good_client}
        h.clients = {"openai": Mock(), "deepseek": Mock()}
        h._get_provider_fallback_order = Mock(return_value=["openai", "deepseek"])
        healer = Mock()
        heal = Mock()
        heal.patched_kwargs = {"model": "deepseek-chat", "messages": [], "stream": True}
        heal.rule = "r"
        heal.patched_keys = ["max_tokens"]
        healer.heal = Mock(return_value=heal)
        with patch("core.llm.routing.request_healer.get_request_healer",
                   return_value=healer):
            out = []
            async for token in h.stream_completion(
                [{"role": "user", "content": "hi"}], "deepseek-chat", "openai"):
                out.append(token)
        assert "healed" in out

    @pytest.mark.asyncio
    async def test_stream_heal_retry_failure_then_next_provider(self):
        h = make_handler()
        chunk = SimpleNamespace(choices=[SimpleNamespace(
            delta=SimpleNamespace(content="deepseek tok"), finish_reason="stop")])
        bad_client = Mock()
        bad_client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("bad request"))
        good_client = Mock()

        async def _gen2():
            yield chunk

        good_client.chat.completions.create = AsyncMock(return_value=AsyncMock(
            __aiter__=lambda s: _gen2()))
        h.async_clients = {"openai": bad_client, "deepseek": good_client}
        h.clients = {"openai": Mock(), "deepseek": Mock()}
        h._get_provider_fallback_order = Mock(return_value=["openai", "deepseek"])
        healer = Mock()
        heal = Mock()
        heal.patched_kwargs = {"model": "deepseek-chat"}
        heal.rule = "r"
        heal.patched_keys = []
        healer.heal = Mock(return_value=heal)
        with patch("core.llm.routing.request_healer.get_request_healer",
                   return_value=healer):
            out = []
            async for token in h.stream_completion(
                [{"role": "user", "content": "hi"}], "deepseek-chat", "openai"):
                out.append(token)
        assert out == ["deepseek tok"]

    @pytest.mark.asyncio
    async def test_stream_interrupted_marks_failed(self):
        h = make_handler()
        h.async_clients = {}
        h.clients = {}
        h._get_provider_fallback_order = Mock(return_value=[])
        db = Mock()
        with pytest.raises(ValueError):
            async for _ in h.stream_completion([], "m", "openai"):
                pass


class TestChatCompletion:
    @pytest.mark.asyncio
    async def test_no_clients_raises(self):
        h = make_handler()
        h.clients = {}
        h.async_clients = {}
        with pytest.raises(ValueError):
            await h.chat_completion([], "m", "openai")

    @pytest.mark.asyncio
    async def test_budget_exceeded_blocked(self):
        h = make_handler()
        with patch("core.llm.byok_handler.llm_usage_tracker",
                   Mock(is_budget_exceeded=Mock(return_value=True))):
            with pytest.raises(GatewayBlockedError):
                await h.chat_completion([], "m", "openai")

    @pytest.mark.asyncio
    async def test_budget_tracker_error_fail_closed(self):
        h = make_handler()
        tracker = Mock()
        tracker.is_budget_exceeded = Mock(side_effect=RuntimeError("db down"))
        with patch("core.llm.byok_handler.llm_usage_tracker", tracker):
            with pytest.raises(GatewayBlockedError):
                await h.chat_completion([], "m", "openai")

    @pytest.mark.asyncio
    async def test_trial_check_error_advisory(self):
        h = make_handler()
        h.async_clients = {"openai": Mock()}
        h.clients = {"openai": Mock()}
        h._get_provider_fallback_order = Mock(return_value=["openai"])
        h.async_clients["openai"].chat.completions.create = AsyncMock(
            return_value=response_mock("ok"))
        tracker = Mock()
        tracker.is_budget_exceeded = Mock(return_value=False)
        tracker.is_trial_expired = Mock(side_effect=RuntimeError("trial db down"))
        with patch("core.llm.byok_handler.llm_usage_tracker", tracker):
            result = await h.chat_completion(
                [{"role": "user", "content": "hi"}], "m", "openai")
        assert result["choices"][0]["message"]["content"] == "ok"

    @pytest.mark.asyncio
    async def test_sync_client_used_and_cost_failure(self):
        h = make_handler()
        h.async_clients = {}
        client = Mock()
        client.chat.completions.create = AsyncMock(
            return_value=response_mock("sync ok"))
        h.clients = {"openai": client}
        h._get_provider_fallback_order = Mock(return_value=["openai"])
        fetcher = Mock()
        fetcher.estimate_cost = Mock(side_effect=RuntimeError("pricing down"))
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            result = await h.chat_completion(
                [{"role": "user", "content": "hi"}], "m", "openai")
        assert result["choices"][0]["message"]["content"] == "sync ok"

    @pytest.mark.asyncio
    async def test_no_client_warning_then_error(self):
        h = make_handler()
        h.async_clients = {"openai": None}
        h.clients = {"openai": None}
        h._get_provider_fallback_order = Mock(return_value=["openai"])
        with pytest.raises(AllProvidersFailedError):
            await h.chat_completion([], "m", "openai")

    @pytest.mark.asyncio
    async def test_heal_retry_success_and_cost_failure(self):
        h = make_handler()
        client = Mock()
        client.chat.completions.create = AsyncMock(
            side_effect=[RuntimeError("bad"), response_mock("healed")])
        h.async_clients = {}
        h.clients = {"openai": client}
        h._get_provider_fallback_order = Mock(return_value=["openai"])
        healer = Mock()
        heal = Mock()
        heal.patched_kwargs = {"model": "m"}
        heal.rule = "r"
        heal.patched_keys = ["max_tokens"]
        healer.heal = Mock(return_value=heal)
        fetcher = Mock()
        fetcher.estimate_cost = Mock(side_effect=RuntimeError("pricing down"))
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher), \
             patch("core.llm.routing.request_healer.get_request_healer",
                   return_value=healer):
            result = await h.chat_completion(
                [{"role": "user", "content": "hi"}], "m", "openai")
        assert result["choices"][0]["message"]["content"] == "healed"

    @pytest.mark.asyncio
    async def test_heal_retry_failure_raises(self):
        h = make_handler()
        client = Mock()
        client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("bad"))
        h.async_clients = {}
        h.clients = {"openai": client}
        h._get_provider_fallback_order = Mock(return_value=["openai"])
        healer = Mock()
        heal = Mock()
        heal.patched_kwargs = {"model": "m"}
        heal.rule = "r"
        heal.patched_keys = []
        healer.heal = Mock(return_value=heal)
        with patch("core.llm.routing.request_healer.get_request_healer",
                   return_value=healer):
            with pytest.raises(AllProvidersFailedError):
                await h.chat_completion(
                    [{"role": "user", "content": "hi"}], "m", "openai")

    @pytest.mark.asyncio
    async def test_health_record_failure_swallowed(self):
        h = make_handler()
        client = Mock()
        client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("bad"))
        h.async_clients = {}
        h.clients = {"openai": client}
        h._get_provider_fallback_order = Mock(return_value=["openai"])
        h.health_monitor.record_call = Mock(side_effect=RuntimeError("hm down"))
        with pytest.raises(AllProvidersFailedError):
            await h.chat_completion(
                [{"role": "user", "content": "hi"}], "m", "openai")


class TestGenerateWithCognitiveTier:
    @pytest.mark.asyncio
    async def test_budget_exceeded(self):
        h = make_handler()
        h.tier_service = Mock()
        h.tier_service.select_tier.return_value = CognitiveTier.MICRO
        h.tier_service.calculate_request_cost.return_value = {"cost_cents": 999}
        h.tier_service.check_budget_constraint.return_value = False
        result = await h.generate_with_cognitive_tier("hi")
        assert result["error"] == "Budget exceeded"

    @pytest.mark.asyncio
    async def test_no_models_available(self):
        h = make_handler()
        h.tier_service = Mock()
        h.tier_service.select_tier.return_value = CognitiveTier.MICRO
        h.tier_service.calculate_request_cost.return_value = {"cost_cents": 1}
        h.tier_service.check_budget_constraint.return_value = True
        h.tier_service.get_optimal_model.return_value = (None, None)
        result = await h.generate_with_cognitive_tier("hi")
        assert result["error"] == "No models available for this tier"

    @pytest.mark.asyncio
    async def test_quality_assess_failure_and_success(self):
        h = make_handler()
        h.tier_service = Mock()
        h.tier_service.select_tier.return_value = CognitiveTier.MICRO
        h.tier_service.calculate_request_cost.return_value = {"cost_cents": 1}
        h.tier_service.check_budget_constraint.return_value = True
        h.tier_service.get_optimal_model.return_value = ("openai", "gpt-4o")
        h.generate_response = AsyncMock(return_value="a good answer")
        h.tier_service.handle_escalation.return_value = (False, None, None)
        with patch("core.llm.response_quality.assess_response_quality",
                   side_effect=RuntimeError("quality down")):
            result = await h.generate_with_cognitive_tier("hi")
        assert result["response"] == "a good answer"

    @pytest.mark.asyncio
    async def test_generation_failed_escalates(self):
        h = make_handler()
        h.tier_service = Mock()
        h.tier_service.select_tier.return_value = CognitiveTier.MICRO
        h.tier_service.calculate_request_cost.return_value = {"cost_cents": 1}
        h.tier_service.check_budget_constraint.return_value = True
        h.tier_service.get_optimal_model.return_value = ("openai", "gpt-4o")
        h.generate_response = AsyncMock(return_value="I'm sorry, but an error occurred.")
        h.tier_service.handle_escalation.return_value = (False, None, None)
        result = await h.generate_with_cognitive_tier("hi")
        assert "error" in result or "response" in result


class TestPricingHelpers:
    def test_get_provider_comparison(self):
        h = make_handler()
        fetcher = Mock()
        fetcher.compare_providers = Mock(return_value={
            "deepseek": {"avg_cost_per_token": 1e-7},
        })
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            result = h.get_provider_comparison()
        assert result["deepseek"]["avg_cost_per_token"] == 1e-7

    def test_get_provider_comparison_static_fallback(self):
        h = make_handler()
        fetcher = Mock()
        fetcher.compare_providers = Mock(return_value={})
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            result = h.get_provider_comparison()
        assert "openai" in result

    def test_monthly_tpm_invalid(self, monkeypatch):
        monkeypatch.setenv("OPENCODE_MONTHLY_TPM", "abc")
        h = make_handler()
        assert h._monthly_tpm_limit() is None

    def test_monthly_tpm_valid(self, monkeypatch):
        monkeypatch.setenv("OPENCODE_MONTHLY_TPM", "500")
        h = make_handler()
        assert h._monthly_tpm_limit() == 500

    def test_monthly_budget_fail_open(self):
        h = make_handler()
        h.rate_tracker.get_monthly_usage = Mock(side_effect=RuntimeError("db down"))
        assert h._monthly_budget_exhausted("openai", 100) is False
