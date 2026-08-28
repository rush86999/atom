"""Coverage wave 73c — gateway_service (verify 100%), embedding/base (74% -> 100%),
embedding/providers (95% -> 100%), token_counter (verify 100%).

Standalone-certifying suite: every branch of the 4 target modules is driven here
directly (mocked deps, zero LLM spend, no network, no real DB) so this file alone
holds each module at >=95%.

Genuine coverage gaps closed vs. the pre-existing suites:
- embedding/base: abstract-method bodies (via the `__abstractmethods__ = frozenset()`
  trick) and the whole `_truncate_to_fit` truncation path were never executed.
- embedding/providers: unknown-model + API-error branches on the *batch* paths of
  every provider (OpenAI 107, Cohere 187/209/219, Voyage 312/322, Nomic 396/408/417,
  Jina 495/507/516) and the module-level `AsyncOpenAI is None` ImportError fallback
  (22-23) were never executed.
- voyageai EmbeddingsResult regression (non-subscriptable result object — the SDK
  returns `.embeddings`, not a list; fixed in an early round, locked here).
"""
import builtins
import importlib
import sys
from types import SimpleNamespace
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import HTTPException

from core.llm.byok_handler import (
    AllProvidersFailedError,
    GatewayBlockedError,
    NoProvidersConfiguredError,
)
from core.llm.cognitive_tier_system import CognitiveTier
from core.llm.embedding.base import (
    BaseEmbeddingProvider,
    EmbeddingContextLimitError,
    EmbeddingProviderError,
    EmbeddingRateLimitError,
)
from core.llm.embedding.providers import (
    CohereEmbeddingProvider,
    JinaEmbeddingProvider,
    NomicEmbeddingProvider,
    OpenAIEmbeddingProvider,
    VoyageEmbeddingProvider,
)
from core.llm.gateway.auth import GatewayIdentity
from core.llm.gateway.gateway_service import GatewayService


# ============================================================================
# embedding/base.py
# ============================================================================

class _AbstractBodyProvider(BaseEmbeddingProvider):
    """Subclass whose abstract methods are never overridden — instantiated by
    clearing ``__abstractmethods__`` so the base ``pass`` bodies execute."""


_AbstractBodyProvider.__abstractmethods__ = frozenset()


class TestBaseEmbeddingProvider:
    def test_init_stores_key_and_client(self):
        provider = _AbstractBodyProvider(api_key="secret")
        assert provider._api_key == "secret"
        assert provider._client is None
        provider2 = _AbstractBodyProvider()
        assert provider2._api_key is None

    async def test_abstract_method_bodies_execute(self):
        provider = _AbstractBodyProvider("k")
        assert await provider.generate_embedding("t", "m") is None
        assert await provider.generate_embeddings_batch(["t"], "m") is None
        assert provider.get_model_name("m") is None
        assert provider.estimate_cost("t", "m") is None
        assert provider.get_context_limit("m") is None
        assert provider.get_provider_name() is None

    def test_abstract_base_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            BaseEmbeddingProvider(api_key="k")

    def test_exception_hierarchy(self):
        rate = EmbeddingRateLimitError("rate")
        assert isinstance(rate, EmbeddingProviderError)
        ctx = EmbeddingContextLimitError("ctx")
        assert isinstance(ctx, EmbeddingProviderError)
        assert EmbeddingProviderError("plain").args == ("plain",)


class TestBaseValidationAndHelpers:
    def test_validate_text_input_non_string(self):
        provider = _AbstractBodyProvider("k")
        with pytest.raises(ValueError, match="must be a string"):
            provider._validate_text_input(None)
        with pytest.raises(ValueError, match="must be a string"):
            provider._validate_text_input(42)

    def test_validate_text_input_empty_or_whitespace(self):
        provider = _AbstractBodyProvider("k")
        with pytest.raises(ValueError, match="empty or whitespace"):
            provider._validate_text_input("")
        with pytest.raises(ValueError, match="empty or whitespace"):
            provider._validate_text_input("   ")

    def test_validate_text_input_valid(self):
        _AbstractBodyProvider("k")._validate_text_input("hello world")

    def test_estimate_tokens(self):
        provider = _AbstractBodyProvider("k")
        assert provider._estimate_tokens("") == 0
        assert provider._estimate_tokens("abcd") == 1
        assert provider._estimate_tokens("abcdefgh") == 2

    def test_truncate_to_fit_fits_returns_unchanged(self):
        provider = _AbstractBodyProvider("k")
        assert provider._truncate_to_fit("short text", 10) == "short text"

    def test_truncate_to_fit_truncates_to_token_budget(self):
        provider = _AbstractBodyProvider("k")
        text = "a" * 40  # ~10 estimated tokens
        assert provider._truncate_to_fit(text, 5) == "a" * 20


# ============================================================================
# gateway_service.py — standalone certification
# ============================================================================

def _identity():
    return GatewayIdentity(
        user_id="u-1",
        tenant_id="t-1",
        workspace_id="ws-1",
        auth_method="api_key",
        api_key_id="key-1",
    )


def _fake_handler(**overrides):
    handler = MagicMock()
    handler.analyze_query_complexity.return_value = "simple"
    handler.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")
    handler.get_ranked_providers.return_value = [("openai", "gpt-4o-mini")]
    handler._provider_serves_model.return_value = False
    handler._rerank_with_learning = AsyncMock(
        return_value=[("anthropic", "claude-3-5-sonnet")]
    )
    handler.async_clients = {"openai": object(), "anthropic": object()}
    handler.clients = {}
    handler.byok_manager = SimpleNamespace(
        providers={"openai": SimpleNamespace(model="gpt-4o-mini")}
    )
    for k, v in overrides.items():
        setattr(handler, k, v)
    return handler


def _service_harness(handler):
    with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=handler):
        return GatewayService(_identity(), MagicMock())


class TestGatewayServiceInit:
    def test_init_builds_byok_handler_with_identity(self):
        handler = _fake_handler()
        db = MagicMock()
        with patch("core.llm.gateway.gateway_service.BYOKHandler", return_value=handler) as bh:
            service = GatewayService(_identity(), db)
        bh.assert_called_once_with(
            workspace_id="ws-1", tenant_id="t-1", db_session=db, user_id="u-1"
        )
        assert service.handler is handler
        assert service.identity.user_id == "u-1"


class TestResolveRouteStandalone:
    async def test_no_overrides_uses_ranked_providers(self):
        handler = _fake_handler()
        service = _service_harness(handler)
        provider, model = await service._resolve_route(
            [{"role": "user", "content": "hi"}], None
        )
        assert (provider, model) == ("openai", "gpt-4o-mini")
        handler.get_ranked_providers.assert_called_once_with(
            "simple", "chat", prefer_cost=True
        )
        handler._rerank_with_learning.assert_not_awaited()

    async def test_forced_tier_valid_passes_cognitive_tier(self):
        handler = _fake_handler()
        service = _service_harness(handler)
        provider, model = await service._resolve_route(
            [{"role": "user", "content": "hi"}], "auto", {"x-atom-tier": "versatile"}
        )
        assert (provider, model) == ("openai", "gpt-4o-mini")
        handler.get_ranked_providers.assert_called_once_with(
            "simple", "chat", prefer_cost=True,
            cognitive_tier=CognitiveTier.VERSATILE,
        )

    async def test_forced_tier_invalid_falls_back_to_absolute(self):
        handler = _fake_handler()
        service = _service_harness(handler)
        with patch(
            "core.llm.gateway.gateway_service.parse_routing_overrides",
            return_value={"tier": "bogus"},
        ):
            provider, model = await service._resolve_route(
                [{"role": "user", "content": "hi"}], "auto"
            )
        assert (provider, model) == ("openai", "gpt-4o-mini")
        handler.get_ranked_providers.assert_not_called()

    async def test_no_providers_config_reraises(self):
        handler = _fake_handler()
        handler.get_ranked_providers.side_effect = NoProvidersConfiguredError()
        service = _service_harness(handler)
        with pytest.raises(NoProvidersConfiguredError):
            await service._resolve_route([{"role": "user", "content": "hi"}], "auto")

    async def test_generic_routing_error_logs_and_falls_back(self):
        handler = _fake_handler()
        handler.get_ranked_providers.side_effect = RuntimeError("boom")
        service = _service_harness(handler)
        with patch("core.llm.gateway.gateway_service.logger") as logger:
            provider, model = await service._resolve_route(
                [{"role": "user", "content": "hi"}], "auto"
            )
        assert (provider, model) == ("openai", "gpt-4o-mini")
        logger.warning.assert_called_once()

    async def test_empty_options_falls_back_to_absolute(self):
        handler = _fake_handler()
        handler.get_ranked_providers.return_value = []
        service = _service_harness(handler)
        provider, model = await service._resolve_route(
            [{"role": "user", "content": "hi"}], "auto"
        )
        assert (provider, model) == ("openai", "gpt-4o-mini")

    async def test_forced_intent_reranks_with_learning(self):
        handler = _fake_handler()
        service = _service_harness(handler)
        with patch(
            "core.llm.gateway.gateway_service.parse_routing_overrides",
            return_value={"intent": "code"},
        ):
            provider, model = await service._resolve_route(
                [{"role": "user", "content": "hi"}], "auto"
            )
        assert (provider, model) == ("anthropic", "claude-3-5-sonnet")
        handler._rerank_with_learning.assert_awaited_once_with(
            [("openai", "gpt-4o-mini")], "hi", "chat", intent="code"
        )

    async def test_forced_model_header_wins(self):
        handler = _fake_handler()
        service = _service_harness(handler)
        provider, model = await service._resolve_route(
            [{"role": "user", "content": "hi"}], "gpt-4o",
            {"x-atom-model": "deepseek-chat"},
        )
        assert (provider, model) == ("openai", "deepseek-chat")
        handler._provider_serves_model.assert_called()

    async def test_body_model_forced_when_not_auto(self):
        handler = _fake_handler()
        service = _service_harness(handler)
        provider, model = await service._resolve_route(
            [{"role": "user", "content": "hi"}], "gpt-4o"
        )
        assert (provider, model) == ("openai", "gpt-4o")

    async def test_body_model_auto_and_empty_are_ignored(self):
        handler = _fake_handler()
        service = _service_harness(handler)
        for bogus in ("auto", "", None):
            provider, model = await service._resolve_route(
                [{"role": "user", "content": "hi"}], bogus
            )
            assert (provider, model) == ("openai", "gpt-4o-mini")


class TestRoutingFallbacksStandalone:
    def test_optimal_success(self):
        service = _service_harness(_fake_handler())
        assert service._optimal() == ("openai", "gpt-4o-mini")

    def test_optimal_generic_error_falls_back(self):
        handler = _fake_handler()
        handler.get_optimal_provider.side_effect = RuntimeError("boom")
        service = _service_harness(handler)
        assert service._optimal() == ("openai", "gpt-4o-mini")

    def test_optimal_no_providers_reraises(self):
        handler = _fake_handler()
        handler.get_optimal_provider.side_effect = NoProvidersConfiguredError()
        service = _service_harness(handler)
        with pytest.raises(NoProvidersConfiguredError):
            service._optimal()

    def test_absolute_fallback_uses_configured_model(self):
        service = _service_harness(_fake_handler())
        assert service._absolute_fallback() == ("openai", "gpt-4o-mini")

    def test_absolute_fallback_sync_clients_when_async_empty(self):
        handler = _fake_handler()
        handler.async_clients = {}
        handler.clients = {"openai": object()}
        service = _service_harness(handler)
        assert service._absolute_fallback() == ("openai", "gpt-4o-mini")

    def test_absolute_fallback_missing_model_uses_default(self):
        handler = _fake_handler()
        handler.byok_manager = SimpleNamespace(
            providers={"openai": SimpleNamespace(model=None)}
        )
        service = _service_harness(handler)
        assert service._absolute_fallback() == ("openai", "gpt-4o-mini")

    def test_absolute_fallback_provider_lookup_error_uses_default(self):
        handler = _fake_handler()
        providers = MagicMock()
        providers.get.side_effect = RuntimeError("boom")
        handler.byok_manager = SimpleNamespace(providers=providers)
        service = _service_harness(handler)
        assert service._absolute_fallback() == ("openai", "gpt-4o-mini")

    def test_absolute_fallback_no_clients_raises(self):
        handler = _fake_handler()
        handler.async_clients = {}
        handler.clients = {}
        service = _service_harness(handler)
        with pytest.raises(NoProvidersConfiguredError):
            service._absolute_fallback()

    def test_resolve_provider_for_model_no_server(self):
        handler = _fake_handler()
        service = _service_harness(handler)
        assert service._resolve_provider_for_model("openai", "gpt-4o") == (
            "openai", "gpt-4o",
        )

    def test_resolve_provider_for_model_skips_routed_provider_then_reroutes(self):
        handler = _fake_handler()
        handler._provider_serves_model.side_effect = lambda pid, m: pid == "anthropic"
        service = _service_harness(handler)
        assert service._resolve_provider_for_model("openai", "claude-x") == (
            "anthropic", "claude-x",
        )

    def test_resolve_provider_for_model_reroutes_via_sync_client(self):
        handler = _fake_handler()
        handler.async_clients = {"openai": object()}
        handler.clients = {"anthropic": object()}
        handler._provider_serves_model.side_effect = lambda pid, m: pid == "anthropic"
        service = _service_harness(handler)
        assert service._resolve_provider_for_model("openai", "claude-x") == (
            "anthropic", "claude-x",
        )


class TestListModelsStandalone:
    @patch("core.llm.registry.queries.get_models_for_provider")
    def test_list_models_dedupes(self, get_models):
        get_models.side_effect = (
            lambda db, pid: ["gpt-4o", "gpt-4o"] if pid == "openai" else ["claude-x"]
        )
        service = _service_harness(_fake_handler())
        body = service.list_models()
        assert body["object"] == "list"
        assert [m["id"] for m in body["data"]] == ["gpt-4o", "claude-x"]
        assert all(m["owned_by"] == "atom" for m in body["data"])

    @patch("core.llm.registry.queries.get_models_for_provider")
    def test_list_models_empty_falls_back_to_provider_ids(self, get_models):
        get_models.return_value = []
        service = _service_harness(_fake_handler())
        body = service.list_models()
        assert [m["id"] for m in body["data"]] == ["openai", "anthropic"]

    @patch("core.llm.registry.queries.get_models_for_provider")
    def test_list_models_uses_sync_clients_when_async_empty(self, get_models):
        get_models.return_value = []
        handler = _fake_handler()
        handler.async_clients = {}
        handler.clients = {"openai": object()}
        service = _service_harness(handler)
        body = service.list_models()
        assert [m["id"] for m in body["data"]] == ["openai"]

    @patch("core.llm.registry.queries.get_models_for_provider")
    def test_models_for_provider_registry_success(self, get_models):
        get_models.return_value = ["gpt-4o"]
        service = _service_harness(_fake_handler())
        assert service._models_for_provider("openai") == ["gpt-4o"]

    @patch("core.llm.registry.queries.get_models_for_provider")
    def test_models_for_provider_registry_failure_falls_back_to_config(self, get_models):
        get_models.side_effect = RuntimeError("registry down")
        service = _service_harness(_fake_handler())
        assert service._models_for_provider("openai") == ["gpt-4o-mini"]

    @patch("core.llm.registry.queries.get_models_for_provider")
    def test_models_for_provider_no_config_returns_empty(self, get_models):
        get_models.side_effect = ImportError("no registry")
        handler = _fake_handler()
        handler.byok_manager = SimpleNamespace(providers={})
        service = _service_harness(handler)
        assert service._models_for_provider("openai") == []

    @patch("core.llm.registry.queries.get_models_for_provider")
    def test_models_for_provider_config_model_none_returns_empty(self, get_models):
        get_models.side_effect = ImportError("no registry")
        handler = _fake_handler()
        handler.byok_manager = SimpleNamespace(
            providers={"openai": SimpleNamespace(model=None)}
        )
        service = _service_harness(handler)
        assert service._models_for_provider("openai") == []


class TestMapGatewayErrorStandalone:
    def _service(self):
        return _service_harness(_fake_handler())

    def test_no_providers_error(self):
        body = self._service().map_gateway_error(NoProvidersConfiguredError())
        assert body["_status"] == 503
        assert body["error"]["code"] == "no_llm_provider"
        assert body["error"]["recovery_url"] == "/settings/ai"
        assert body["error"]["type"] == "server_error"

    def test_no_providers_error_custom_recovery_url(self):
        exc = NoProvidersConfiguredError(recovery_url="/custom")
        body = self._service().map_gateway_error(exc)
        assert body["error"]["recovery_url"] == "/custom"

    def test_no_providers_error_anthropic_shape(self):
        body = self._service().map_gateway_error(
            NoProvidersConfiguredError(), anthropic=True
        )
        assert body["_status"] == 503
        assert body["type"] == "error"

    def test_gateway_blocked_error(self):
        body = self._service().map_gateway_error(
            GatewayBlockedError(reason="trial_expired", message="Trial expired")
        )
        assert body["_status"] == 429
        assert body["error"]["code"] == "trial_expired"
        assert body["error"]["message"] == "Trial expired"

    def test_all_providers_failed(self):
        body = self._service().map_gateway_error(AllProvidersFailedError("boom"))
        assert body["_status"] == 502
        assert body["error"]["code"] == "all_providers_failed"

    def test_http_exception(self):
        body = self._service().map_gateway_error(
            HTTPException(status_code=404, detail="missing")
        )
        assert body["_status"] == 404
        assert body["error"]["message"] == "missing"
        assert body["error"]["code"] == "gateway_error"

    def test_value_error(self):
        body = self._service().map_gateway_error(ValueError("bad input"))
        assert body["_status"] == 400
        assert body["error"]["code"] == "invalid_request"
        assert body["error"]["type"] == "invalid_request_error"

    def test_generic_error_logs_without_leaking_detail(self):
        service = self._service()
        with patch("core.llm.gateway.gateway_service.logger") as logger:
            body = service.map_gateway_error(RuntimeError("secret detail"))
        assert body["_status"] == 500
        assert body["error"]["code"] == "internal_error"
        assert "secret detail" not in str(body)
        logger.error.assert_called_once()

    def test_error_body_openai_without_recovery_url(self):
        body = self._service()._error_body(400, "nope", "invalid_request")
        assert body["error"] == {
            "message": "nope",
            "type": "invalid_request_error",
            "param": None,
            "code": "invalid_request",
        }
        assert "recovery_url" not in body["error"]
        assert body["_status"] == 400

    def test_error_body_anthropic_delegates(self):
        service = self._service()
        with patch(
            "core.llm.gateway.wire_formats.openai_error_to_anthropic",
            return_value={"type": "error", "error": {"type": "api_error"}},
        ) as conv:
            body = service._error_body(500, "x", "internal_error", anthropic=True)
        conv.assert_called_once_with(500, "internal_error", "x")
        assert body["_status"] == 500


class TestGatewayHelpersStandalone:
    def test_parse_tier_valid(self):
        import core.llm.gateway.gateway_service as gs

        assert gs._parse_tier("micro") is CognitiveTier.MICRO
        assert gs._parse_tier("COMPLEX") is CognitiveTier.COMPLEX

    def test_parse_tier_invalid_logs_and_returns_none(self):
        import core.llm.gateway.gateway_service as gs

        with patch("core.llm.gateway.gateway_service.logger") as logger:
            assert gs._parse_tier("quantum") is None
        logger.warning.assert_called_once()

    def test_get_gateway_enabled(self):
        import core.llm.gateway.gateway_service as gs

        assert gs.get_gateway_enabled() == gs.GATEWAY_ENABLED

    def test_require_gateway_enabled_when_on(self):
        import core.llm.gateway.gateway_service as gs

        gs.require_gateway_enabled()

    def test_require_gateway_enabled_when_off(self):
        import core.llm.gateway.gateway_service as gs

        # require_gateway_enabled() consults the LIVE gateway_enabled()
        # (env > runtime_settings DB row) — the GATEWAY_ENABLED module
        # constant is an import-time snapshot no code path reads.
        with patch("core.llm.gateway.gateway_service.gateway_enabled", return_value=False):
            with pytest.raises(HTTPException) as ei:
                gs.require_gateway_enabled()
        assert ei.value.status_code == 404
        assert "Gateway disabled" in ei.value.detail

    def test_get_user_or_none(self):
        import core.llm.gateway.gateway_service as gs

        user = MagicMock()
        identity = GatewayIdentity(
            user_id="u-1", tenant_id="t-1", workspace_id="w",
            auth_method="api_key", user=user,
        )
        assert gs.get_user_or_none(identity) is user
        assert gs.get_user_or_none(_identity()) is None


# ============================================================================
# token_counter.py — standalone certification
# ============================================================================

from core.llm.context.token_counter import (  # noqa: E402
    ContextValidator,
    ModelFamily,
    TokenCounter,
)

_REAL_IMPORT = builtins.__import__


def _block_tiktoken(name, *args, **kwargs):
    if name == "tiktoken":
        raise ImportError("No module named 'tiktoken'")
    return _REAL_IMPORT(name, *args, **kwargs)


class TestTokenCounterModuleFallback:
    def test_module_import_without_tiktoken_falls_back(self):
        import core.llm.context.token_counter as tc_mod

        with mock.patch.dict(sys.modules, {"tiktoken": None}):
            with mock.patch.object(builtins, "__import__", _block_tiktoken):
                reloaded = importlib.reload(tc_mod)
        try:
            assert reloaded.HAS_TIKTOKEN is False
            counter = reloaded.TokenCounter()
            assert counter.count_tokens("hello world", "gpt-4o") == 2
            assert counter.count_tokens_by_family(
                "hello world", reloaded.ModelFamily.OPENAI
            ) == 2
            assert counter.count_tokens_by_family(
                "hello world", reloaded.ModelFamily.ANTHROPIC
            ) == 2
        finally:
            importlib.reload(tc_mod)
            globals()["TokenCounter"] = tc_mod.TokenCounter
            globals()["ContextValidator"] = tc_mod.ContextValidator
            globals()["ModelFamily"] = tc_mod.ModelFamily


class TestTokenCounterStandalone:
    def test_count_tokens_empty_text_returns_zero(self):
        assert TokenCounter().count_tokens("", "gpt-4o") == 0

    def test_count_tokens_tiktoken_path(self):
        counter = TokenCounter()
        assert counter.count_tokens("hello world", "gpt-4o") == 2

    def test_count_tokens_fallback_model_uses_estimate(self):
        counter = TokenCounter()
        text = "some unknown model text"
        assert counter.count_tokens(text, "unknown-model") == len(text) // 4

    def test_count_tokens_by_family_empty(self):
        assert TokenCounter().count_tokens_by_family("", ModelFamily.OPENAI) == 0

    def test_count_tokens_by_family_tiktoken(self):
        assert TokenCounter().count_tokens_by_family(
            "hello world", ModelFamily.OPENAI
        ) == 2

    def test_count_tokens_by_family_estimate_for_non_tiktoken_family(self):
        text = "cohere family text"
        assert TokenCounter().count_tokens_by_family(
            text, ModelFamily.COHERE
        ) == len(text) // 4

    def test_tiktoken_encoding_failure_falls_back_to_approximation(self, monkeypatch):
        counter = TokenCounter()

        def boom(family):
            raise RuntimeError("encoding unavailable")

        monkeypatch.setattr(counter, "_get_encoding", boom)
        text = "hello world this is a test"
        assert counter.count_tokens(text, "gpt-4o") == len(text) // 4

    def test_estimate_tokens(self):
        assert TokenCounter().estimate_tokens("") == 0
        assert TokenCounter().estimate_tokens("abcdefgh") == 2

    def test_get_model_family_detection(self):
        counter = TokenCounter()
        assert counter.get_model_family("gpt-4o") is ModelFamily.OPENAI
        assert counter.get_model_family("o1-preview") is ModelFamily.OPENAI
        assert counter.get_model_family("o3-mini") is ModelFamily.OPENAI
        assert counter.get_model_family("text-embedding-3-small") is ModelFamily.OPENAI
        assert counter.get_model_family("claude-3-5-sonnet") is ModelFamily.ANTHROPIC
        assert counter.get_model_family("Claude-3-Opus") is ModelFamily.ANTHROPIC
        assert counter.get_model_family("command-r") is ModelFamily.COHERE
        assert counter.get_model_family("embed-english-v3.0") is ModelFamily.COHERE
        assert counter.get_model_family("gemini-1.5-pro") is ModelFamily.GOOGLE
        assert counter.get_model_family("some-unknown-model") is ModelFamily.FALLBACK

    def test_get_encoding_openai_caches(self):
        TokenCounter._encoding_cache.pop(ModelFamily.OPENAI, None)
        try:
            counter = TokenCounter()
            enc = counter._get_encoding(ModelFamily.OPENAI)
            assert enc is TokenCounter._encoding_cache[ModelFamily.OPENAI]
            assert counter._get_encoding(ModelFamily.OPENAI) is enc
        finally:
            TokenCounter._encoding_cache.pop(ModelFamily.OPENAI, None)

    def test_get_encoding_anthropic_branch_caches(self):
        TokenCounter._encoding_cache.pop(ModelFamily.ANTHROPIC, None)
        try:
            counter = TokenCounter()
            enc = counter._get_encoding(ModelFamily.ANTHROPIC)
            assert enc is TokenCounter._encoding_cache[ModelFamily.ANTHROPIC]
        finally:
            TokenCounter._encoding_cache.pop(ModelFamily.ANTHROPIC, None)

    def test_get_encoding_unsupported_family_raises(self):
        TokenCounter._encoding_cache.pop(ModelFamily.COHERE, None)
        with pytest.raises(ValueError, match="No tiktoken encoding"):
            TokenCounter()._get_encoding(ModelFamily.COHERE)


class TestContextValidatorStandalone:
    def test_validate_request_fits(self):
        validator = ContextValidator()
        assert validator.validate_request_fits(
            "hello world", "gpt-4o", max_tokens=100
        ) is True
        assert validator.validate_request_fits(
            "hello world", "gpt-4o", max_tokens=200000
        ) is False
        assert validator.validate_request_fits("x" * 600_000, "unknown-model") is False

    def test_get_model_context_limit(self):
        validator = ContextValidator()
        assert validator.get_model_context_limit("gpt-4o") == 128000
        assert validator.get_model_context_limit("GPT-4") == 8192
        assert validator.get_model_context_limit("claude-3-5-sonnet-20241022") == 200000
        assert validator.get_model_context_limit("text-embedding-3-large") == 8191
        assert (
            validator.get_model_context_limit("unknown-frontier-model")
            == ContextValidator.DEFAULT_CONTEXT_LIMIT
        )

    def test_truncate_to_fit_returns_text_when_fits(self):
        validator = ContextValidator()
        text = "hello world, this fits easily"
        assert validator.truncate_to_fit(text, "gpt-4o") == text

    def test_truncate_to_fit_max_tokens_clamp(self):
        validator = ContextValidator()
        text = "hello world"
        assert validator.truncate_to_fit(text, "gpt-4o", max_tokens=100) == text

    def test_truncate_to_fit_truncates_long_text(self):
        validator = ContextValidator()
        text = "sentence one. " + "filler words here " * 500
        truncated = validator.truncate_to_fit(text, "gpt-4", reserve_for_output=7500)
        assert len(truncated) < len(text)
        assert text.startswith(truncated)

    def test_estimate_request_tokens(self):
        validator = ContextValidator()
        messages = [
            {"role": "user", "content": "hello world"},
            {"role": "assistant", "content": ""},
            {"role": "system"},
        ]
        total = validator.estimate_request_tokens(messages, "gpt-4o")
        assert total == (2 + 10) + (0 + 10) + (0 + 10)


class TestTruncateAtBoundaryStandalone:
    def _validator(self):
        return ContextValidator()

    def test_empty_returns_unchanged(self):
        assert self._validator()._truncate_at_boundary("") == ""

    def test_newline_boundary(self):
        text = "a" * 90 + "\nremaining text"
        assert self._validator()._truncate_at_boundary(text) == "a" * 90 + "\n"

    def test_question_mark_boundary(self):
        text = "b" * 80 + "? more text"
        assert self._validator()._truncate_at_boundary(text) == "b" * 80 + "? "

    def test_exclamation_boundary(self):
        text = "a" * 85 + "! more text"
        assert self._validator()._truncate_at_boundary(text) == "a" * 85 + "! "

    def test_period_boundary(self):
        text = "x" * 90 + ". more text after"
        assert self._validator()._truncate_at_boundary(text) == "x" * 90 + ". "

    def test_word_boundary(self):
        text = "y" * 95 + " final"
        assert self._validator()._truncate_at_boundary(text) == "y" * 95

    def test_no_boundary_returns_unchanged(self):
        text = "m" * 50 + ". " + "n" * 50
        assert self._validator()._truncate_at_boundary(text) == text


# ============================================================================
# embedding/providers.py — standalone certification
# ============================================================================

def _openai_response(vectors):
    return SimpleNamespace(data=[SimpleNamespace(embedding=v) for v in vectors])


class TestOpenAIProviderStandalone:
    def _make(self, client):
        with patch("core.llm.embedding.providers.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = client
            return OpenAIEmbeddingProvider(api_key="test_key")

    def test_init_success_and_names(self):
        provider = self._make(AsyncMock())
        assert provider.get_provider_name() == "OpenAI"
        assert provider.get_model_name("text-embedding-3-small") == (
            "OpenAI text-embedding-3-small"
        )
        assert provider.get_model_name("unknown-model") == "unknown-model"

    def test_init_without_package(self):
        with patch("core.llm.embedding.providers.AsyncOpenAI", None):
            with pytest.raises(EmbeddingProviderError, match="pip install openai"):
                OpenAIEmbeddingProvider(api_key="k")

    async def test_generate_embedding_success(self):
        client = AsyncMock()
        client.embeddings.create = AsyncMock(
            return_value=_openai_response([[0.1, 0.2, 0.3]])
        )
        provider = self._make(client)
        assert await provider.generate_embedding("hello", "text-embedding-3-small") == [
            0.1, 0.2, 0.3,
        ]

    async def test_generate_embedding_rate_limit(self):
        client = AsyncMock()
        client.embeddings.create = AsyncMock(
            side_effect=Exception("rate limit exceeded")
        )
        provider = self._make(client)
        with pytest.raises(EmbeddingRateLimitError, match="OpenAI rate limit"):
            await provider.generate_embedding("hello", "text-embedding-3-small")

    async def test_generate_embedding_api_error(self):
        client = AsyncMock()
        client.embeddings.create = AsyncMock(side_effect=Exception("connection failed"))
        provider = self._make(client)
        with pytest.raises(EmbeddingProviderError, match="OpenAI API error"):
            await provider.generate_embedding("hello", "text-embedding-3-small")

    async def test_generate_embedding_unknown_model(self):
        provider = self._make(AsyncMock())
        with pytest.raises(ValueError, match="Unknown model"):
            await provider.generate_embedding("hello", "nope")

    async def test_generate_embedding_invalid_text(self):
        provider = self._make(AsyncMock())
        with pytest.raises(ValueError):
            await provider.generate_embedding("", "text-embedding-3-small")
        with pytest.raises(ValueError):
            await provider.generate_embedding(42, "text-embedding-3-small")

    async def test_generate_embeddings_batch_success(self):
        client = AsyncMock()
        client.embeddings.create = AsyncMock(
            return_value=_openai_response([[0.1], [0.2], [0.3]])
        )
        provider = self._make(client)
        assert await provider.generate_embeddings_batch(
            ["a", "b", "c"], "text-embedding-3-small"
        ) == [[0.1], [0.2], [0.3]]
        client.embeddings.create.assert_awaited_once_with(
            input=["a", "b", "c"], model="text-embedding-3-small",
            encoding_format="float",
        )

    async def test_generate_embeddings_batch_empty(self):
        client = AsyncMock()
        provider = self._make(client)
        assert await provider.generate_embeddings_batch([], "text-embedding-3-small") == []
        client.embeddings.create.assert_not_called()

    async def test_generate_embeddings_batch_rate_limit(self):
        client = AsyncMock()
        client.embeddings.create = AsyncMock(side_effect=Exception("rate"))
        provider = self._make(client)
        with pytest.raises(EmbeddingRateLimitError):
            await provider.generate_embeddings_batch(
                ["a"], "text-embedding-3-small"
            )

    async def test_generate_embeddings_batch_api_error(self):
        client = AsyncMock()
        client.embeddings.create = AsyncMock(side_effect=Exception("boom"))
        provider = self._make(client)
        with pytest.raises(EmbeddingProviderError):
            await provider.generate_embeddings_batch(
                ["a"], "text-embedding-3-small"
            )

    async def test_generate_embeddings_batch_unknown_model(self):
        provider = self._make(AsyncMock())
        with pytest.raises(ValueError, match="Unknown model"):
            await provider.generate_embeddings_batch(["a"], "nope")

    async def test_generate_embeddings_batch_invalid_text_in_list(self):
        provider = self._make(AsyncMock())
        with pytest.raises(ValueError):
            await provider.generate_embeddings_batch(
                ["ok", ""], "text-embedding-3-small"
            )

    def test_estimate_cost_and_context_limit(self):
        provider = self._make(AsyncMock())
        assert provider.estimate_cost("hello", "text-embedding-3-small") == pytest.approx(
            1 / 1e6 * 0.02
        )
        assert provider.get_context_limit("text-embedding-3-large") == 8191
        with pytest.raises(ValueError):
            provider.estimate_cost("hello", "nope")
        with pytest.raises(ValueError):
            provider.get_context_limit("nope")


class TestCohereProviderStandalone:
    def _make(self, client):
        with patch(
            "core.llm.embedding.providers.cohere",
            SimpleNamespace(AsyncClient=lambda **kw: client),
        ):
            return CohereEmbeddingProvider(api_key="test_key")

    def test_init_success_and_names(self):
        provider = self._make(AsyncMock())
        assert provider.get_provider_name() == "Cohere"
        assert provider.get_model_name("embed-english-v3.0") == (
            "Cohere embed-english-v3.0"
        )
        assert provider.get_model_name("unknown") == "unknown"

    def test_init_without_package(self):
        with patch("core.llm.embedding.providers.cohere", None):
            with pytest.raises(EmbeddingProviderError, match="pip install cohere"):
                CohereEmbeddingProvider(api_key="k")

    async def test_generate_embedding_success(self):
        client = AsyncMock()
        client.embed = AsyncMock(return_value=SimpleNamespace(embeddings=[[0.1, 0.2]]))
        provider = self._make(client)
        assert await provider.generate_embedding("hello", "embed-english-v3.0") == [
            0.1, 0.2,
        ]
        client.embed.assert_awaited_once_with(
            texts=["hello"], model="embed-english-v3.0", input_type="search_document"
        )

    async def test_generate_embedding_rate_limit_429(self):
        client = AsyncMock()
        client.embed = AsyncMock(side_effect=Exception("429 Too Many Requests"))
        provider = self._make(client)
        with pytest.raises(EmbeddingRateLimitError, match="Cohere rate limit"):
            await provider.generate_embedding("hello", "embed-english-v3.0")

    async def test_generate_embedding_api_error(self):
        client = AsyncMock()
        client.embed = AsyncMock(side_effect=Exception("down"))
        provider = self._make(client)
        with pytest.raises(EmbeddingProviderError, match="Cohere API error"):
            await provider.generate_embedding("hello", "embed-english-v3.0")

    async def test_generate_embedding_unknown_model(self):
        provider = self._make(AsyncMock())
        with pytest.raises(ValueError, match="Unknown model"):
            await provider.generate_embedding("hello", "nope")

    async def test_generate_embedding_invalid_text(self):
        provider = self._make(AsyncMock())
        with pytest.raises(ValueError):
            await provider.generate_embedding("", "embed-english-v3.0")

    async def test_generate_embeddings_batch_success(self):
        client = AsyncMock()
        client.embed = AsyncMock(return_value=SimpleNamespace(embeddings=[[0.1], [0.2]]))
        provider = self._make(client)
        assert await provider.generate_embeddings_batch(
            ["a", "b"], "embed-english-v3.0"
        ) == [[0.1], [0.2]]

    async def test_generate_embeddings_batch_empty(self):
        client = AsyncMock()
        provider = self._make(client)
        assert await provider.generate_embeddings_batch([], "embed-english-v3.0") == []
        client.embed.assert_not_called()

    async def test_generate_embeddings_batch_rate_limit(self):
        client = AsyncMock()
        client.embed = AsyncMock(side_effect=Exception("rate"))
        provider = self._make(client)
        with pytest.raises(EmbeddingRateLimitError):
            await provider.generate_embeddings_batch(["a"], "embed-english-v3.0")

    async def test_generate_embeddings_batch_api_error(self):
        client = AsyncMock()
        client.embed = AsyncMock(side_effect=Exception("boom"))
        provider = self._make(client)
        with pytest.raises(EmbeddingProviderError, match="Cohere API error"):
            await provider.generate_embeddings_batch(["a"], "embed-english-v3.0")

    async def test_generate_embeddings_batch_unknown_model(self):
        provider = self._make(AsyncMock())
        with pytest.raises(ValueError, match="Unknown model"):
            await provider.generate_embeddings_batch(["a"], "nope")

    async def test_generate_embeddings_batch_invalid_text_in_list(self):
        provider = self._make(AsyncMock())
        with pytest.raises(ValueError):
            await provider.generate_embeddings_batch(["ok", "  "], "embed-english-v3.0")

    def test_estimate_cost_and_context_limit(self):
        provider = self._make(AsyncMock())
        assert provider.estimate_cost("hello", "embed-multilingual-v3.0") == pytest.approx(
            1 / 1e6 * 0.15
        )
        assert provider.get_context_limit("embed-english-light-v3.0") == 512
        with pytest.raises(ValueError):
            provider.estimate_cost("hello", "nope")
        with pytest.raises(ValueError):
            provider.get_context_limit("nope")


class TestVoyageProviderStandalone:
    def _make(self, client):
        mock_voyage = MagicMock()
        mock_voyage.Client.return_value = client
        with patch("core.llm.embedding.providers.voyageai", mock_voyage):
            return VoyageEmbeddingProvider(api_key="k")

    def test_init_success_and_names(self):
        provider = self._make(Mock())
        assert provider.get_provider_name() == "Voyage"
        assert provider.get_model_name("voyage-large-2") == "Voyage voyage-large-2"
        assert provider.get_model_name("nope") == "nope"

    def test_init_without_package(self):
        with patch("core.llm.embedding.providers.voyageai", None):
            with pytest.raises(EmbeddingProviderError, match="pip install voyageai"):
                VoyageEmbeddingProvider(api_key="k")

    async def test_generate_embedding_embeddings_result_regression(self):
        """Regression: voyageai SDK returns EmbeddingsResult (attribute access
        only, NOT subscriptable) — provider must read ``result.embeddings[0]``
        instead of ``result[0]`` (TypeError on every real call, fixed in an
        early round)."""
        result = SimpleNamespace(embeddings=[0.5, 0.6])
        with pytest.raises(TypeError):
            result[0]
        client = Mock()
        client.embed = Mock(return_value=result)
        provider = self._make(client)
        vector = await provider.generate_embedding("hello", "voyage-2")
        assert vector == 0.5
        client.embed.assert_called_once_with(
            "hello", model="voyage-2", input_type="document"
        )

    async def test_generate_embeddings_batch_success(self):
        client = Mock()
        client.embed = Mock(return_value=SimpleNamespace(embeddings=[[0.1], [0.2]]))
        provider = self._make(client)
        assert await provider.generate_embeddings_batch(["a", "b"], "voyage-2") == [
            [0.1], [0.2],
        ]
        client.embed.assert_called_once_with(
            ["a", "b"], model="voyage-2", input_type="document"
        )

    async def test_generate_embeddings_batch_empty(self):
        client = Mock()
        provider = self._make(client)
        assert await provider.generate_embeddings_batch([], "voyage-2") == []
        client.embed.assert_not_called()

    async def test_generate_embedding_rate_limit(self):
        client = Mock()
        client.embed = Mock(side_effect=Exception("rate"))
        provider = self._make(client)
        with pytest.raises(EmbeddingRateLimitError, match="Voyage rate limit"):
            await provider.generate_embedding("hello", "voyage-2")

    async def test_generate_embedding_api_error(self):
        client = Mock()
        client.embed = Mock(side_effect=Exception("down"))
        provider = self._make(client)
        with pytest.raises(EmbeddingProviderError, match="Voyage API error"):
            await provider.generate_embedding("hello", "voyage-2")

    async def test_generate_embedding_unknown_model(self):
        provider = self._make(Mock())
        with pytest.raises(ValueError, match="Unknown model"):
            await provider.generate_embedding("hello", "nope")

    async def test_generate_embeddings_batch_rate_limit(self):
        client = Mock()
        client.embed = Mock(side_effect=Exception("429"))
        provider = self._make(client)
        with pytest.raises(EmbeddingRateLimitError):
            await provider.generate_embeddings_batch(["a"], "voyage-2")

    async def test_generate_embeddings_batch_api_error(self):
        client = Mock()
        client.embed = Mock(side_effect=Exception("boom"))
        provider = self._make(client)
        with pytest.raises(EmbeddingProviderError, match="Voyage API error"):
            await provider.generate_embeddings_batch(["a"], "voyage-2")

    async def test_generate_embeddings_batch_unknown_model(self):
        provider = self._make(Mock())
        with pytest.raises(ValueError, match="Unknown model"):
            await provider.generate_embeddings_batch(["a"], "nope")

    def test_estimate_cost_and_context_limit(self):
        provider = self._make(Mock())
        assert provider.estimate_cost("hello", "voyage-code-2") == pytest.approx(
            1 / 1e6 * 0.15
        )
        assert provider.get_context_limit("voyage-2") == 128
        with pytest.raises(ValueError):
            provider.estimate_cost("hello", "nope")
        with pytest.raises(ValueError):
            provider.get_context_limit("nope")


class TestNomicProviderStandalone:
    def _make(self, embedder):
        mock_nomic = MagicMock()
        mock_nomic.Embedding.return_value = embedder
        with patch("core.llm.embedding.providers.nomic", mock_nomic):
            return NomicEmbeddingProvider(api_key="k")

    def test_init_success_and_names(self):
        provider = self._make(Mock())
        assert provider.get_provider_name() == "Nomic"
        assert provider.get_model_name("nomic-embed-text-v1") == "Nomic nomic-embed-text-v1"
        assert provider.get_model_name("nope") == "nope"

    def test_init_without_package(self):
        with patch("core.llm.embedding.providers.nomic", None):
            with pytest.raises(EmbeddingProviderError, match="pip install nomic"):
                NomicEmbeddingProvider(api_key="k")

    async def test_generate_embedding_success(self):
        embedder = Mock()
        embedder.embed = Mock(return_value={"embeddings": [[0.1, 0.2]]})
        provider = self._make(embedder)
        assert await provider.generate_embedding(
            "hello", "nomic-embed-text-v1.5"
        ) == [0.1, 0.2]
        embedder.embed.assert_called_once_with(
            texts=["hello"], model="nomic-embed-text-v1.5",
            task_type="search_document",
        )

    async def test_generate_embeddings_batch_success(self):
        embedder = Mock()
        embedder.embed = Mock(return_value={"embeddings": [[0.1], [0.2]]})
        provider = self._make(embedder)
        assert await provider.generate_embeddings_batch(
            ["a", "b"], "nomic-embed-text-v1.5"
        ) == [[0.1], [0.2]]

    async def test_generate_embeddings_batch_empty(self):
        embedder = Mock()
        provider = self._make(embedder)
        assert await provider.generate_embeddings_batch(
            [], "nomic-embed-text-v1.5"
        ) == []
        embedder.embed.assert_not_called()

    async def test_generate_embedding_rate_limit(self):
        embedder = Mock()
        embedder.embed = Mock(side_effect=Exception("rate"))
        provider = self._make(embedder)
        with pytest.raises(EmbeddingRateLimitError, match="Nomic rate limit"):
            await provider.generate_embedding("hello", "nomic-embed-text-v1.5")

    async def test_generate_embedding_api_error(self):
        embedder = Mock()
        embedder.embed = Mock(side_effect=Exception("down"))
        provider = self._make(embedder)
        with pytest.raises(EmbeddingProviderError, match="Nomic API error"):
            await provider.generate_embedding("hello", "nomic-embed-text-v1.5")

    async def test_generate_embedding_unknown_model(self):
        provider = self._make(Mock())
        with pytest.raises(ValueError, match="Unknown model"):
            await provider.generate_embedding("hello", "nope")

    async def test_generate_embeddings_batch_rate_limit(self):
        embedder = Mock()
        embedder.embed = Mock(side_effect=Exception("429"))
        provider = self._make(embedder)
        with pytest.raises(EmbeddingRateLimitError):
            await provider.generate_embeddings_batch(["a"], "nomic-embed-text-v1.5")

    async def test_generate_embeddings_batch_api_error(self):
        embedder = Mock()
        embedder.embed = Mock(side_effect=Exception("boom"))
        provider = self._make(embedder)
        with pytest.raises(EmbeddingProviderError, match="Nomic API error"):
            await provider.generate_embeddings_batch(["a"], "nomic-embed-text-v1.5")

    async def test_generate_embeddings_batch_unknown_model(self):
        provider = self._make(Mock())
        with pytest.raises(ValueError, match="Unknown model"):
            await provider.generate_embeddings_batch(["a"], "nope")

    def test_estimate_cost_and_context_limit(self):
        provider = self._make(Mock())
        assert provider.estimate_cost("hello", "nomic-embed-text-v1.5") == pytest.approx(
            1 / 1e6 * 0.08
        )
        assert provider.get_context_limit("nomic-embed-text-v1") == 8192
        with pytest.raises(ValueError):
            provider.estimate_cost("hello", "nope")
        with pytest.raises(ValueError):
            provider.get_context_limit("nope")


class TestJinaProviderStandalone:
    def _make(self, client):
        with patch("core.llm.embedding.providers.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = client
            return JinaEmbeddingProvider(api_key="test_key")

    def test_init_success_and_names(self):
        client = AsyncMock()
        with patch("core.llm.embedding.providers.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = client
            provider = JinaEmbeddingProvider(api_key="test_key")
        mock_openai.assert_called_once_with(
            api_key="test_key", base_url="https://api.jina.ai/v1"
        )
        assert provider.get_provider_name() == "Jina"
        assert provider.get_model_name("jina-embeddings-v3") == "Jina jina-embeddings-v3"
        assert provider.get_model_name("nope") == "nope"

    def test_init_without_package(self):
        with patch("core.llm.embedding.providers.AsyncOpenAI", None):
            with pytest.raises(EmbeddingProviderError, match="pip install openai"):
                JinaEmbeddingProvider(api_key="k")

    async def test_generate_embedding_success(self):
        client = AsyncMock()
        client.embeddings.create = AsyncMock(
            return_value=_openai_response([[0.1, 0.2]])
        )
        provider = self._make(client)
        assert await provider.generate_embedding("hello", "jina-embeddings-v2") == [
            0.1, 0.2,
        ]
        client.embeddings.create.assert_awaited_once_with(
            input="hello", model="jina-embeddings-v2"
        )

    async def test_generate_embedding_rate_limit(self):
        client = AsyncMock()
        client.embeddings.create = AsyncMock(side_effect=Exception("rate"))
        provider = self._make(client)
        with pytest.raises(EmbeddingRateLimitError, match="Jina rate limit"):
            await provider.generate_embedding("hello", "jina-embeddings-v2")

    async def test_generate_embedding_api_error(self):
        client = AsyncMock()
        client.embeddings.create = AsyncMock(side_effect=Exception("down"))
        provider = self._make(client)
        with pytest.raises(EmbeddingProviderError, match="Jina API error"):
            await provider.generate_embedding("hello", "jina-embeddings-v2")

    async def test_generate_embedding_unknown_model(self):
        provider = self._make(AsyncMock())
        with pytest.raises(ValueError, match="Unknown model"):
            await provider.generate_embedding("hello", "nope")

    async def test_generate_embeddings_batch_success(self):
        client = AsyncMock()
        client.embeddings.create = AsyncMock(
            return_value=_openai_response([[0.1], [0.2]])
        )
        provider = self._make(client)
        assert await provider.generate_embeddings_batch(
            ["a", "b"], "jina-embeddings-v2"
        ) == [[0.1], [0.2]]

    async def test_generate_embeddings_batch_empty(self):
        client = AsyncMock()
        provider = self._make(client)
        assert await provider.generate_embeddings_batch([], "jina-embeddings-v2") == []
        client.embeddings.create.assert_not_called()

    async def test_generate_embeddings_batch_rate_limit(self):
        client = AsyncMock()
        client.embeddings.create = AsyncMock(side_effect=Exception("429"))
        provider = self._make(client)
        with pytest.raises(EmbeddingRateLimitError):
            await provider.generate_embeddings_batch(["a"], "jina-embeddings-v2")

    async def test_generate_embeddings_batch_api_error(self):
        client = AsyncMock()
        client.embeddings.create = AsyncMock(side_effect=Exception("boom"))
        provider = self._make(client)
        with pytest.raises(EmbeddingProviderError, match="Jina API error"):
            await provider.generate_embeddings_batch(["a"], "jina-embeddings-v2")

    async def test_generate_embeddings_batch_unknown_model(self):
        provider = self._make(AsyncMock())
        with pytest.raises(ValueError, match="Unknown model"):
            await provider.generate_embeddings_batch(["a"], "nope")

    def test_estimate_cost_and_context_limit(self):
        provider = self._make(AsyncMock())
        assert provider.estimate_cost("hello", "jina-embeddings-v3") == pytest.approx(
            1 / 1e6 * 0.03
        )
        assert provider.get_context_limit("jina-embeddings-v2") == 8192
        with pytest.raises(ValueError):
            provider.estimate_cost("hello", "nope")
        with pytest.raises(ValueError):
            provider.get_context_limit("nope")


class TestProvidersModuleImportFallback:
    def test_module_import_without_openai_sentinel_falls_back(self):
        """Cover the module-level ``except ImportError: AsyncOpenAI = None``
        branch (openai is installed here so it never fires on normal import)."""
        import core.llm.embedding.providers as prov_mod

        with mock.patch.dict(sys.modules, {"openai": None}):
            with mock.patch.object(builtins, "__import__", _block_openai):
                reloaded = importlib.reload(prov_mod)
        try:
            assert reloaded.AsyncOpenAI is None
            with pytest.raises(EmbeddingProviderError, match="pip install openai"):
                reloaded.OpenAIEmbeddingProvider(api_key="k")
            with pytest.raises(EmbeddingProviderError, match="pip install openai"):
                reloaded.JinaEmbeddingProvider(api_key="k")
        finally:
            importlib.reload(prov_mod)
            globals()["OpenAIEmbeddingProvider"] = prov_mod.OpenAIEmbeddingProvider
            globals()["CohereEmbeddingProvider"] = prov_mod.CohereEmbeddingProvider
            globals()["VoyageEmbeddingProvider"] = prov_mod.VoyageEmbeddingProvider
            globals()["NomicEmbeddingProvider"] = prov_mod.NomicEmbeddingProvider
            globals()["JinaEmbeddingProvider"] = prov_mod.JinaEmbeddingProvider


def _block_openai(name, *args, **kwargs):
    if name == "openai":
        raise ImportError("No module named 'openai'")
    return _REAL_IMPORT(name, *args, **kwargs)
