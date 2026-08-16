# -*- coding: utf-8 -*-
"""Coverage wave 89 — core.llm.byok_handler, core.generic_agent,
core.historical_sync_service.

No network, no LLM: every external boundary (OpenAI SDK, DB sessions,
credential service, learning router, pricing fetcher) is mocked.

This suite EXTENDS (does not duplicate) the established waves for these three
modules by re-collecting their strongest suites here and closing the residual
uncovered branches found via ``--cov-report=term-missing``:

* byok_handler  — credential-service / env token resolution in
  ``_initialize_clients``, ``_load_local_providers`` capability injection,
  BPC rate-headroom exhaustion skips, learning-router EMA cold-start
  re-rank, ``_stash_decision_features`` intent detection, and the
  no-running-loop path of ``_run_coroutine_sync``.
* generic_agent  — AgentRadio inbox drain inside the ReAct loop.
* historical_sync_service — re-collected (residual is <3%: pending-task
  cancellation past the 600s wait, heartbeat-thread crash handler, and
  failure-commit error paths exercised only under real DB failures).
"""
import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# ---------------------------------------------------------------------------
# Extend the established waves verbatim (collection only — no duplication).
# ---------------------------------------------------------------------------
from tests.test_covpush_w64j_byok_handler import *  # noqa: F401,F403
from tests.test_covpush_w64j_byok_handler_b import *  # noqa: F401,F403
from tests.test_covpush_generic_agent import *  # noqa: F401,F403
from tests.test_covpush_historical import *  # noqa: F401,F403

from tests.test_covpush_w64j_byok_handler import (  # noqa: F401
    _ctx,
    _db_active,
    _make_handler,
)
from tests.test_covpush_generic_agent import _agent_model, _build_agent  # noqa: F401

import core.llm.byok_handler as byok_mod
from core.llm.byok_handler import BYOKHandler, QueryComplexity
from core.react_models import ReActStep, ToolCall


# =========================================================================== #
# byok_handler — _run_coroutine_sync without a running event loop (66-68)
# =========================================================================== #

class TestW89RunCoroutineSync:
    def test_no_running_loop_drives_coroutine_directly(self):
        out = {}

        def work():
            # A non-main thread has no implicit event loop — create one so
            # get_event_loop() inside _run_coroutine_sync can find it.
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def coro():
                await asyncio.sleep(0)
                return 42

            out["v"] = byok_mod._run_coroutine_sync(coro(), timeout=5.0)
            loop.close()

        t = threading.Thread(target=work)
        t.start()
        t.join(timeout=10)
        assert out["v"] == 42


# =========================================================================== #
# byok_handler — _initialize_clients credential resolution (880-892, 924)
# =========================================================================== #

def _init_env(handler, monkeypatch, providers=None):
    """Patch everything _initialize_clients touches for a hermetic re-run."""
    providers = providers or {
        "groq": {"base_url": "https://api.groq.com/openai/v1"},
    }
    handler.providers_config = providers
    handler.byok_manager = MagicMock()
    handler.byok_manager.is_configured = MagicMock(return_value=False)
    handler.byok_manager.get_api_key = MagicMock(return_value=None)
    handler._load_local_providers = Mock()
    monkeypatch.setattr(byok_mod, "OpenAI", MagicMock())
    monkeypatch.setattr(byok_mod, "AsyncOpenAI", MagicMock())
    monkeypatch.delenv("GROQ_API_KEY", raising=False)


class TestW89InitializeClientsCredentials:
    def test_credential_service_oauth_path(self, monkeypatch):
        handler, _ = _make_handler()
        _init_env(handler, monkeypatch)
        cs = MagicMock()
        cs.get_credential = AsyncMock(return_value=("oauth", "key-oauth"))
        handler.credential_service = cs
        handler._initialize_clients()
        assert handler.clients["groq"] is not None
        assert cs.get_credential.await_count >= 1

    def test_credential_service_error_falls_to_env(self, monkeypatch):
        handler, _ = _make_handler()
        _init_env(handler, monkeypatch)
        monkeypatch.setenv("GROQ_API_KEY", "env-key")
        cs = MagicMock()
        cs.get_credential = AsyncMock(side_effect=RuntimeError("svc down"))
        handler.credential_service = cs
        handler._initialize_clients()
        # env fallback resolved a key and initialized the client
        assert "groq" in handler.clients
        ctor = byok_mod.OpenAI
        assert ctor.called

    def test_credential_service_error_no_key_skips(self, monkeypatch):
        handler, _ = _make_handler()
        _init_env(handler, monkeypatch)
        cs = MagicMock()
        cs.get_credential = AsyncMock(side_effect=RuntimeError("svc down"))
        handler.credential_service = cs
        handler._initialize_clients()
        assert "groq" not in handler.clients


# =========================================================================== #
# byok_handler — _load_local_providers (986-1013)
# =========================================================================== #

class TestW89LoadLocalProviders:
    def _run(self, handler, monkeypatch, providers, caps):
        from core.models import LocalModelCapabilities, LocalModelProvider

        def _query(model):
            q = MagicMock()
            if model is LocalModelProvider:
                q.filter.return_value.all.return_value = providers
            elif model is LocalModelCapabilities:
                q.filter.return_value.all.return_value = caps
            return q

        session = MagicMock()
        session.query.side_effect = _query
        ctx = _ctx(session)
        fetcher = SimpleNamespace(pricing_cache={})

        with patch("core.database.get_db_session", return_value=ctx), \
             patch.object(byok_mod, "get_pricing_fetcher", return_value=fetcher), \
             patch.object(byok_mod, "OpenAI", MagicMock()), \
             patch.object(byok_mod, "AsyncOpenAI", MagicMock()):
            handler._load_local_providers()
        return fetcher

    def test_local_provider_with_caps(self, monkeypatch):
        handler, _ = _make_handler()
        prov = SimpleNamespace(
            id="abcd1234ef", api_key=None, base_url="http://localhost:11434/v1/",
            name="MyOllama", provider_type="ollama")
        caps = [SimpleNamespace(model_id="llama3", context_window=8192,
                                supports_tools=True, supports_vision=False,
                                supports_reasoning=False, quality_score=0.5)]
        fetcher = self._run(handler, monkeypatch, [prov], caps)
        assert "local_abcd1234" in handler.clients
        assert fetcher.pricing_cache["llama3"]["quality_score"] == 0.5
        assert fetcher.pricing_cache["llama3"]["input_cost"] == 0.0

    def test_local_provider_without_caps_registers_generic_entry(self, monkeypatch):
        handler, _ = _make_handler()
        prov = SimpleNamespace(
            id="ffff1234ef", api_key=None, base_url="http://x/v1/",
            name="LM", provider_type="lmstudio")
        fetcher = self._run(handler, monkeypatch, [prov], [])
        assert "lmstudio_default" in fetcher.pricing_cache
        assert fetcher.pricing_cache["lmstudio_default"]["max_input_tokens"] == 8192

    def test_no_providers_registered_is_noop(self, monkeypatch):
        handler, _ = _make_handler()
        before = dict(handler.clients)
        self._run(handler, monkeypatch, [], [])
        assert handler.clients == before


# =========================================================================== #
# byok_handler — BPC rate-headroom exhaustion skips (1548-1564)
# =========================================================================== #

def _pricing(pricing_cache):
    return SimpleNamespace(pricing_cache=pricing_cache)


class TestW89BpcHeadroomSkips:
    def _handler(self):
        handler, _ = _make_handler()
        # cerebras is absent from the static fallback priority list, so any
        # candidate ranked for it can only come from the dynamic BPC path —
        # that makes presence/absence assertions unambiguous.
        handler.clients = {"cerebras": MagicMock()}
        handler.async_clients = {"cerebras": MagicMock()}
        handler.cache_router = MagicMock()
        handler.cache_router.calculate_effective_cost = MagicMock(return_value=1e-6)
        handler._filter_by_capabilities = MagicMock(return_value=True)
        handler._filter_by_health = MagicMock(return_value=True)
        return handler

    def _cache(self):
        return _pricing({
            "cerebras/llama-3.3-70b": {
                "litellm_provider": "cerebras", "max_input_tokens": 128000,
            },
        })

    async def _rank(self, handler, monkeypatch):
        # _make_handler stubs get_ranked_providers with an AsyncMock — invoke
        # the real implementation on the instance.
        with patch.object(byok_mod, "get_pricing_fetcher_initialized_sync",
                          return_value=self._cache()), \
             patch.object(byok_mod, "get_quality_score", return_value=50.0):
            return await BYOKHandler.get_ranked_providers(
                handler, QueryComplexity.SIMPLE, is_managed_service=False)

    _CAND = ("cerebras", "cerebras/llama-3.3-70b")

    async def test_per_model_headroom_exhausted_skips(self, monkeypatch):
        handler = self._handler()
        handler.rate_tracker = MagicMock()
        handler.rate_tracker.get_max_context = MagicMock(return_value=None)
        handler.rate_tracker.get_model_headroom = MagicMock(return_value=0.0)
        out = await self._rank(handler, monkeypatch)
        # model hard-skipped -> falls through to static tier fallback
        assert self._CAND not in out

    async def test_provider_headroom_exhausted_skips(self, monkeypatch):
        handler = self._handler()
        handler.rate_tracker = MagicMock()
        handler.rate_tracker.get_max_context = MagicMock(return_value=None)
        handler.rate_tracker.get_model_headroom = MagicMock(return_value=1.0)
        handler.rate_tracker.get_headroom = MagicMock(return_value=0.0)
        out = await self._rank(handler, monkeypatch)
        assert self._CAND not in out

    async def test_healthy_headroom_ranks_candidate(self, monkeypatch):
        handler = self._handler()
        rt = MagicMock()
        rt.get_max_context = MagicMock(return_value=None)
        rt.get_model_headroom = MagicMock(return_value=1.0)
        rt.get_headroom = MagicMock(return_value=0.9)
        rt.get_model_weight = MagicMock(return_value=1.0)
        handler.rate_tracker = rt
        out = await self._rank(handler, monkeypatch)
        assert self._CAND in out

    async def test_monthly_subscription_quota_exhausted_skips(self, monkeypatch):
        handler = self._handler()
        rt = MagicMock()
        rt.get_max_context = MagicMock(return_value=None)
        rt.get_model_headroom = MagicMock(return_value=1.0)
        rt.get_headroom = MagicMock(return_value=0.9)
        rt.get_model_weight = MagicMock(return_value=1.0)
        rt.get_monthly_usage = MagicMock(return_value={"total_tokens": 5_000_000})
        handler.rate_tracker = rt
        monkeypatch.setenv("OPENCODE_MONTHLY_TPM", "1000000")
        out = await self._rank(handler, monkeypatch)
        assert self._CAND not in out
        # not-exhausted branch: monthly usage below the allowance
        rt.get_monthly_usage = MagicMock(return_value={"total_tokens": 10})
        out2 = await self._rank(handler, monkeypatch)
        assert self._CAND in out2


# =========================================================================== #
# byok_handler — learning-router EMA cold-start re-rank (2454-2455)
# and _stash_decision_features intent detection (2545-2547)
# =========================================================================== #

def _fake_learning_router(ema_scores=None, per_model_routers=None):
    lr = MagicMock()
    lr._ema_scores = ema_scores or {}
    lr._per_model_routers = per_model_routers or {}
    lr._extract_request_features = MagicMock(return_value=[0.0] * 16)
    lr.stash_decision = MagicMock(return_value="decision-id-1")
    lr._EMA_SCORE_WEIGHT = 0.3
    return lr


class TestW89RerankWithLearning:
    async def test_ema_cold_start_reranks_without_predictor(self, monkeypatch):
        handler, _ = _make_handler()
        lr = _fake_learning_router(
            ema_scores={"default:general:model-b": {"success": 0.9}})
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        monkeypatch.setenv("ATOM_EMA_ROUTER_ENABLED", "true")
        # _make_handler stubs this method out — invoke the real implementation.
        with patch("core.llm.learning_router_registry"
                   ".get_learning_router_instance", return_value=lr):
            out = await BYOKHandler._rerank_with_learning(
                handler,
                [("openai", "model-a"), ("deepseek", "model-b")],
                "do the thing", "general")
        # model-b has EMA history -> sorted first
        assert out[0] == ("deepseek", "model-b")
        assert len(out) == 2
        assert handler._pending_routing_result_id == "decision-id-1"

    async def test_no_learned_signal_returns_original_order(self, monkeypatch):
        handler, _ = _make_handler()
        lr = _fake_learning_router()
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        monkeypatch.setenv("ATOM_EMA_ROUTER_ENABLED", "true")
        with patch("core.llm.learning_router_registry"
                   ".get_learning_router_instance", return_value=lr):
            out = await BYOKHandler._rerank_with_learning(
                handler,
                [("openai", "model-a"), ("deepseek", "model-b")],
                "prompt", "general")
        assert out == [("openai", "model-a"), ("deepseek", "model-b")]


class TestW89StashDecisionFeatures:
    def _env(self, monkeypatch, router):
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        return patch("core.llm.learning_router_registry"
                     ".get_learning_router_instance", return_value=router)

    def test_intent_detected_and_stashed(self, monkeypatch):
        handler, _ = _make_handler()
        lr = _fake_learning_router()
        ir = MagicMock()
        ir.detect = MagicMock(return_value=SimpleNamespace(
            category="analysis", confidence=0.9))
        with self._env(monkeypatch, lr), \
             patch("core.llm.intent_detector.get_intent_detector",
                   return_value=ir):
            out = handler._stash_decision_features("analyze this", "general")
        assert out == "decision-id-1"
        # intent one-hot entered the stashed feature vector
        feats = lr._extract_request_features.call_args[0][0]
        assert getattr(feats, "intent", None) == "analysis"

    def test_intent_detection_failure_tolerated(self, monkeypatch):
        handler, _ = _make_handler()
        lr = _fake_learning_router()
        with self._env(monkeypatch, lr), \
             patch("core.llm.intent_detector.get_intent_detector",
                   side_effect=RuntimeError("intent down")):
            out = handler._stash_decision_features("analyze this", "general")
        assert out == "decision-id-1"

    def test_disabled_returns_none(self, monkeypatch):
        handler, _ = _make_handler()
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "false")
        assert handler._stash_decision_features("p", "general") is None


# =========================================================================== #
# generic_agent — AgentRadio inbox drain in the ReAct loop (206-216)
# =========================================================================== #

class TestW89RadioInboxDrain:
    @pytest.mark.asyncio
    async def test_radio_mentions_absorbed_into_history(self):
        agent = _build_agent(_agent_model())
        agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
        agent.world_model.recall_experiences = AsyncMock(return_value={})
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
        agent._record_execution = AsyncMock()
        agent._step_act = AsyncMock(return_value="ok")
        agent._react_step = AsyncMock(side_effect=[
            ReActStep(thought="t", action=ToolCall(tool="t1", params={}),
                      final_answer=None),
            ReActStep(thought="t2", final_answer="done"),
        ])
        drained = []

        def fake_drain(agent_id, thread_id):
            drained.append((agent_id, thread_id))
            return "@you: heads up"

        with patch("core.agent_radio.radio_service.inbox_drain_text",
                   side_effect=fake_drain):
            result = await agent.execute("do it", context={"radio_thread_id": "th-1"})
        assert result["status"] == "success"
        # the drain fires before each plan step
        assert ("agent-123", "th-1") in drained

    @pytest.mark.asyncio
    async def test_radio_drain_failure_never_breaks_loop(self):
        agent = _build_agent(_agent_model())
        agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
        agent.world_model.recall_experiences = AsyncMock(return_value={})
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
        agent._record_execution = AsyncMock()
        agent._react_step = AsyncMock(side_effect=[
            ReActStep(thought="t", final_answer="done"),
        ])
        with patch("core.agent_radio.radio_service.inbox_drain_text",
                   side_effect=RuntimeError("radio down")):
            result = await agent.execute("do it", context={"radio_thread_id": "th-2"})
        assert result["status"] == "success"
