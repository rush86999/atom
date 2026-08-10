"""Coverage wave 11b — byok_handler completion paths, learning-router re-rank,
BPC static fallback (TDD).

Targets the remaining hot blocks: ``generate_completion`` (gateway non-stream),
``stream_completion`` (gateway stream), ``_rerank_with_learning`` (learning
router), and the BPC static fallback + provider-fallback-order helpers.
"""
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm.byok_handler import (
    AllProvidersFailedError,
    GatewayBlockedError,
    QueryComplexity,
)


def _make_handler(clients=("openai",), async_clients=("openai",)):
    from core.llm.byok_handler import BYOKHandler

    with patch("core.llm.byok_handler.OpenAI", return_value=MagicMock()), \
         patch("core.llm.byok_handler.AsyncOpenAI", return_value=MagicMock()), \
         patch("core.llm.byok_handler.get_db_session"):
        handler = BYOKHandler(workspace_id="default", tenant_id="default")
    handler.clients = {p: MagicMock() for p in clients}
    handler.async_clients = {p: MagicMock() for p in async_clients}
    handler.health_monitor = MagicMock()
    handler.health_monitor.health_scores = {}
    handler.byok_manager.is_configured = MagicMock(return_value=False)
    handler.byok_manager.get_api_key = MagicMock(return_value=None)
    return handler


def _chunk(delta_text, finish=False):
    return SimpleNamespace(
        choices=[SimpleNamespace(
            delta=SimpleNamespace(content=delta_text),
            finish_reason="stop" if finish else None,
        )]
    )


class _AsyncGenClient:
    """Async client whose create() returns an async generator of chunks."""

    def __init__(self, chunks, error=None):
        self._chunks = chunks
        self._error = error
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    async def _create(self, **kwargs):
        if self._error:
            raise self._error
        for c in self._chunks:
            yield c


# =========================================================================== #
# generate_completion (non-streaming gateway path)
# =========================================================================== #
class TestGenerateCompletion:
    async def _run(self, handler, **kw):
        return await handler.chat_completion(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4o-mini",
            provider_id="openai",
            task_type="chat",
            **kw,
        )

    @pytest.mark.asyncio
    async def test_success_shape(self):
        from core.llm.byok_handler import llm_usage_tracker

        handler, = [_make_handler()]
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            return_value=SimpleNamespace(
                choices=[SimpleNamespace(
                    message=SimpleNamespace(content="Hello back"),
                    finish_reason="stop",
                )],
                usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2),
            )
        )
        with patch.object(llm_usage_tracker, "is_budget_exceeded", return_value=False):
            out = await self._run(handler)
        assert out["choices"][0]["message"]["content"] == "Hello back"
        assert out["usage"]["total_tokens"] == 5
        assert out["model"] == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_budget_exceeded_fails_closed(self):
        from core.llm.byok_handler import llm_usage_tracker

        handler = _make_handler()
        with patch.object(llm_usage_tracker, "is_budget_exceeded", return_value=True):
            with pytest.raises(GatewayBlockedError) as exc:
                await self._run(handler)
        assert exc.value.reason == "budget_exceeded"

    @pytest.mark.asyncio
    async def test_budget_tracker_error_fails_closed(self):
        from core.llm.byok_handler import llm_usage_tracker

        handler = _make_handler()
        with patch.object(
            llm_usage_tracker, "is_budget_exceeded", side_effect=RuntimeError("db down")
        ):
            with pytest.raises(GatewayBlockedError) as exc:
                await self._run(handler)
        assert exc.value.reason == "budget_check_failed"

    @pytest.mark.asyncio
    async def test_trial_expired_blocked(self):
        from core.llm.byok_handler import llm_usage_tracker

        handler = _make_handler()
        with patch.object(llm_usage_tracker, "is_budget_exceeded", return_value=False), \
             patch.object(llm_usage_tracker, "is_trial_expired", create=True, return_value=True):
            with pytest.raises(GatewayBlockedError) as exc:
                await self._run(handler)
        assert exc.value.reason == "trial_expired"

    @pytest.mark.asyncio
    async def test_no_clients_raises(self):
        handler = _make_handler(clients=(), async_clients=())
        with pytest.raises(ValueError):
            await self._run(handler)

    @pytest.mark.asyncio
    async def test_fallback_to_second_provider(self):
        from core.llm.byok_handler import llm_usage_tracker

        handler = _make_handler(clients=("openai", "anthropic"), async_clients=("openai", "anthropic"))
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            side_effect=RuntimeError("openai down")
        )
        handler.async_clients["anthropic"].chat.completions.create = AsyncMock(
            return_value=SimpleNamespace(
                choices=[SimpleNamespace(
                    message=SimpleNamespace(content="from anthropic"),
                    finish_reason="stop",
                )],
                usage=None,
            )
        )
        handler._provider_serves_model = MagicMock(return_value=True)
        with patch.object(llm_usage_tracker, "is_budget_exceeded", return_value=False):
            out = await handler.chat_completion(
                messages=[{"role": "user", "content": "hi"}],
                model="claude-haiku", provider_id="openai", task_type="chat",
            )
        assert out["choices"][0]["message"]["content"] == "from anthropic"

    @pytest.mark.asyncio
    async def test_all_providers_fail_raises(self):
        from core.llm.byok_handler import llm_usage_tracker

        handler = _make_handler(clients=("openai", "deepseek"), async_clients=("openai", "deepseek"))
        for p in ("openai", "deepseek"):
            handler.async_clients[p].chat.completions.create = AsyncMock(
                side_effect=RuntimeError("down")
            )
        handler._provider_serves_model = MagicMock(return_value=True)
        with patch.object(llm_usage_tracker, "is_budget_exceeded", return_value=False):
            with pytest.raises(AllProvidersFailedError):
                await handler.chat_completion(
                    messages=[{"role": "user", "content": "hi"}],
                    model="m", provider_id="openai", task_type="chat",
                )


# =========================================================================== #
# stream_completion (real streaming generator)
# =========================================================================== #
class TestStreamCompletion:
    @pytest.mark.asyncio
    async def test_streams_tokens_and_stop_reason(self):
        from core.llm.byok_handler import llm_usage_tracker

        handler = _make_handler()
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            side_effect=_AsyncGenClient(
                [_chunk("Hel"), _chunk("lo"), _chunk(" world"), _chunk("", finish=True)]
            ).chat.completions.create
        )
        with patch.object(llm_usage_tracker, "is_budget_exceeded", return_value=False):
            tokens = [t async for t in handler.stream_completion(
                [{"role": "user", "content": "hi"}], "gpt-4o-mini", "openai"
            )]
        assert "".join(tokens) == "Hello world"

    @pytest.mark.asyncio
    async def test_fallback_stream(self):
        from core.llm.byok_handler import llm_usage_tracker

        handler = _make_handler(clients=("openai", "anthropic"), async_clients=("openai", "anthropic"))
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            side_effect=RuntimeError("openai down")
        )
        handler.async_clients["anthropic"].chat.completions.create = AsyncMock(
            side_effect=_AsyncGenClient([_chunk("ok")]).chat.completions.create
        )
        handler._provider_serves_model = MagicMock(return_value=True)
        with patch.object(llm_usage_tracker, "is_budget_exceeded", return_value=False):
            tokens = [t async for t in handler.stream_completion(
                [{"role": "user", "content": "hi"}], "claude-haiku", "openai"
            )]
        assert "".join(tokens) == "ok"

    @pytest.mark.asyncio
    async def test_error_token_surfaces_provider_error(self):
        from core.llm.byok_handler import llm_usage_tracker

        handler = _make_handler()
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        with patch.object(llm_usage_tracker, "is_budget_exceeded", return_value=False):
            tokens = [t async for t in handler.stream_completion(
                [{"role": "user", "content": "hi"}], "gpt-4o-mini", "openai"
            )]
        assert any("[Error:" in t for t in tokens)

    @pytest.mark.asyncio
    async def test_no_clients_raises(self):
        handler = _make_handler(clients=(), async_clients=())
        with pytest.raises(ValueError):
            async for _ in handler.stream_completion(
                [{"role": "user", "content": "hi"}], "m", "openai"
            ):
                pass

    @pytest.mark.asyncio
    async def test_extra_kwargs_forwarded(self):
        from core.llm.byok_handler import llm_usage_tracker

        handler = _make_handler()
        seen = {}

        async def _create(**kwargs):
            seen.update(kwargs)
            for c in [_chunk("x")]:
                yield c

        handler.async_clients["openai"].chat.completions.create = AsyncMock(side_effect=_create)
        with patch.object(llm_usage_tracker, "is_budget_exceeded", return_value=False):
            async for _ in handler.stream_completion(
                [{"role": "user", "content": "hi"}], "gpt-4o-mini", "openai",
                extra_kwargs={"stop": ["\n\n"], "top_p": 0.5},
            ):
                pass
        assert seen["stop"] == ["\n\n"]
        assert seen["top_p"] == 0.5


# =========================================================================== #
# _rerank_with_learning
# =========================================================================== #
class TestRerankWithLearning:
    def _options(self):
        return [("openai", "gpt-4o-mini"), ("anthropic", "claude-haiku")]

    @pytest.mark.asyncio
    async def test_returns_single_option_unchanged(self):
        handler = _make_handler()
        opts = [("openai", "gpt-4o-mini")]
        assert await handler._rerank_with_learning(opts, "hi", "chat") is opts

    @pytest.mark.asyncio
    async def test_flag_off_returns_unchanged(self):
        handler = _make_handler()
        opts = self._options()
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "false"}):
            assert await handler._rerank_with_learning(opts, "hi", "chat") is opts

    @pytest.mark.asyncio
    async def test_router_unavailable_returns_unchanged(self):
        handler = _make_handler()
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}), \
             patch(
                 "core.llm.learning_router_registry.get_learning_router_instance",
                 return_value=None,
             ):
            assert await handler._rerank_with_learning(
                self._options(), "hi", "chat"
            ) == self._options()

    @pytest.mark.asyncio
    async def test_cold_start_returns_unchanged(self):
        handler = _make_handler()
        router = MagicMock()
        router._per_model_routers = {}
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}), \
             patch(
                 "core.llm.learning_router_registry.get_learning_router_instance",
                 return_value=router,
             ):
            assert await handler._rerank_with_learning(
                self._options(), "hi", "chat"
            ) == self._options()

    @pytest.mark.asyncio
    async def test_full_rerank_reorders(self):
        handler = _make_handler()
        router = MagicMock()
        per_model = MagicMock()
        per_model.predict_satisfaction.side_effect = lambda model, feats: {
            "gpt-4o-mini": 0.5, "claude-haiku": 0.9,
        }[model]
        per_model.confidence.side_effect = lambda model: {
            "gpt-4o-mini": 0.4, "claude-haiku": 0.8,
        }[model]
        router._per_model_routers = {"default:question_answering": per_model}
        router._extract_request_features = MagicMock(return_value={"tokens": 5})
        router.stash_decision = MagicMock(return_value="dec-123")
        router._ema_scores = {}

        from core.llm.learning_router_registry import ema_router_enabled

        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}), \
             patch(
                 "core.llm.learning_router_registry.get_learning_router_instance",
                 return_value=router,
             ), \
             patch(
                 "core.llm.byok_handler.os.getenv",
                 side_effect=lambda k, d=None: "true" if k == "ATOM_LEARNING_ROUTER" else os.environ.get(k, d),
             ):
            # NOTE: the learning-router flag is read via os.getenv in the
            # method; patch the registry import used by the method itself.
            pass
        # The method imports get_learning_router_instance lazily — patch the
        # byok_handler module's import target instead.
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}), \
             patch(
                 "core.llm.learning_router_registry.get_learning_router_instance",
                 return_value=router,
             ):
            out = await handler._rerank_with_learning(
                self._options(), "hi", "chat"
            )
        assert out[0] == ("anthropic", "claude-haiku")  # higher learned score
        assert handler._pending_routing_result_id == "dec-123"

    @pytest.mark.asyncio
    async def test_no_learned_signal_returns_unchanged(self):
        handler = _make_handler()
        router = MagicMock()
        per_model = MagicMock()
        per_model.predict_satisfaction.return_value = None
        per_model.confidence.return_value = 0.0
        router._per_model_routers = {"default:question_answering": per_model}
        router._extract_request_features = MagicMock(return_value={})
        router._ema_scores = {}
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}), \
             patch(
                 "core.llm.learning_router_registry.get_learning_router_instance",
                 return_value=router,
             ):
            assert await handler._rerank_with_learning(
                self._options(), "hi", "chat"
            ) == self._options()

    @pytest.mark.asyncio
    async def test_rerank_exception_returns_unchanged(self):
        handler = _make_handler()
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}), \
             patch(
                 "core.llm.learning_router_registry.get_learning_router_instance",
                 side_effect=RuntimeError("boom"),
             ):
            assert await handler._rerank_with_learning(
                self._options(), "hi", "chat"
            ) == self._options()

    def test_adapt_task_type(self):
        from core.llm.byok_handler import BYOKHandler

        assert BYOKHandler._adapt_task_type(None) == "general"
        assert BYOKHandler._adapt_task_type("chat") == "question_answering"
        assert BYOKHandler._adapt_task_type("code") == "code_generation"
        assert BYOKHandler._adapt_task_type("extraction") == "extraction"
        assert BYOKHandler._adapt_task_type("pdf_ocr") == "extraction"
        assert BYOKHandler._adapt_task_type("agentic") == "tool_use"
        assert BYOKHandler._adapt_task_type("bogus") == "general"


# =========================================================================== #
# BPC static fallback + provider ordering helpers
# =========================================================================== #
class TestBpcStaticFallback:
    def _handler(self):
        handler = _make_handler(clients=("openai", "deepseek", "qwen", "anthropic"))
        handler.health_monitor.health_scores = {}
        handler.health_monitor.get_health_score = MagicMock(
            side_effect=lambda p: 1.0
        )
        handler._refresh_excluded_cache = MagicMock()
        handler.excluded_models = set()
        return handler

    def _empty_fetcher(self):
        fetcher = MagicMock()
        fetcher.pricing_cache = {}
        return fetcher

    def test_static_fallback_simple_order(self):
        from core.llm.byok_handler import COST_EFFICIENT_MODELS

        handler = _make_handler(clients=("openai", "deepseek", "anthropic"))
        handler.health_monitor = MagicMock()
        handler.health_monitor.health_scores = {}
        handler.health_monitor.get_health_score = MagicMock(side_effect=lambda p: 1.0)
        handler._refresh_excluded_cache = MagicMock()
        handler.excluded_models = set()
        with patch(
            "core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
            return_value=self._empty_fetcher(),
        ):
            result = handler.get_ranked_providers(
                QueryComplexity.SIMPLE, is_managed_service=False
            )
        providers = [p for p, _ in result]
        # deepseek is first in the SIMPLE priority list and has a client.
        assert providers[0] == "deepseek"
        assert "openai" in providers

    def test_static_fallback_managed_plan_filters(self):
        handler = self._handler()
        with patch(
            "core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
            return_value=self._empty_fetcher(),
        ):
            result = handler.get_ranked_providers(
                QueryComplexity.MODERATE, tenant_plan="free", is_managed_service=True
            )
        providers = [p for p, _ in result]
        assert providers  # free plan still gets providers
        assert "deepseek" in providers

    def test_static_fallback_byok_tools_skip(self):
        handler = self._handler()
        handler._model_supports_tools = MagicMock(return_value=False)
        with patch(
            "core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
            return_value=self._empty_fetcher(),
        ):
            result = handler.get_ranked_providers(
                QueryComplexity.MODERATE, is_managed_service=False, requires_tools=True
            )
        # deepseek's "deepseek-v3.2-speciale" downgrades to deepseek-r2 when
        # tools unsupported; openai's model gets skipped entirely.
        providers = [p for p, _ in result]
        assert "openai" not in providers

    def test_qwen_boost(self):
        handler = self._handler()
        with patch(
            "core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
            return_value=self._empty_fetcher(),
        ):
            result = handler.get_ranked_providers(
                QueryComplexity.COMPLEX, is_managed_service=False
            )
        providers = [p for p, _ in result]
        if "qwen" in providers:
            assert providers[0] == "qwen"

    def test_provider_fallback_order(self):
        handler = self._handler()
        order = handler._get_provider_fallback_order("openai")
        assert order[0] == "openai"  # requested provider first
        assert "deepseek" in order
        assert "qwen" in order

    def test_provider_fallback_order_unknown(self):
        handler = self._handler()
        order = handler._get_provider_fallback_order("ghost")
        assert order == [] or "ghost" not in order

    def test_health_exclude_threshold_boundary(self):
        handler = self._handler()
        handler.health_monitor.health_scores = {"openai": 0.19}
        handler.health_monitor.get_health_score = MagicMock(
            side_effect=lambda p: handler.health_monitor.health_scores.get(p, 1.0)
        )
        assert handler._filter_by_health("openai") is False
        handler.health_monitor.health_scores = {"openai": 0.2}
        assert handler._filter_by_health("openai") is True
        assert handler._filter_by_health("unknown") is True  # optimistic
