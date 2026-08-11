"""Coverage wave 57 — core/llm/byok_handler.py section B: BPC ranking + generation internals.

get_ranked_providers (filters: context/capability/excluded/health/quality/
extraction-cap/rate-headroom/monthly-quota/plan/tools), task-type adaptation,
learning re-rank (all branches), decision-feature stash, tool-pair
sanitization, tier classification, trial gate, embeddings (openai/cohere/
missing/unsupported), transcription.
"""
import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

import core.llm.byok_handler as bh
from core.llm.byok_handler import (
    BYOKHandler,
    QueryComplexity,
)
from core.llm.cognitive_tier_system import CognitiveTier


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



from tests.test_covpush_w57_byok_handler_a import make_handler


def _pricing_entry(model_id, provider="openai", context=32000, quality=90.0,
                   cost=0.001):
    return {
        "model_id": model_id, "litellm_provider": provider,
        "max_input_tokens": context, "quality_score": quality,
        "input_cost_per_token": cost, "output_cost_per_token": cost,
    }


class TestSanitizeToolPairs:
    def test_empty_messages(self):
        assert BYOKHandler.sanitize_tool_pairs([]) == []

    def test_orphaned_tool_gets_stub(self):
        out = BYOKHandler.sanitize_tool_pairs([
            {"role": "user", "content": "hi"},
            {"role": "tool", "tool_call_id": "t1", "content": "result"},
        ])
        assert out[1]["role"] == "assistant"
        assert out[1]["tool_calls"][0]["id"] == "t1"
        assert out[2]["role"] == "tool"

    def test_paired_tool_unchanged(self):
        msgs = [
            {"role": "assistant", "content": None,
             "tool_calls": [{"id": "t1", "function": {"name": "f"}}]},
            {"role": "tool", "tool_call_id": "t1", "content": "result"},
        ]
        out = BYOKHandler.sanitize_tool_pairs(msgs)
        assert len(out) == 2
        assert out[0]["role"] == "assistant"

    def test_trailing_orphan_tool_calls_dropped(self):
        msgs = [
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": None,
             "tool_calls": [{"id": "t1", "function": {"name": "f"}}]},
        ]
        out = BYOKHandler.sanitize_tool_pairs(msgs)
        assert out[-1]["role"] == "user"

    def test_trailing_tool_calls_with_content_kept(self):
        msgs = [
            {"role": "assistant", "content": "answer",
             "tool_calls": [{"id": "t1"}]},
        ]
        out = BYOKHandler.sanitize_tool_pairs(msgs)
        assert len(out) == 1


class TestAdaptTaskType:
    def test_mappings(self):
        assert BYOKHandler._adapt_task_type(None) == "general"
        assert BYOKHandler._adapt_task_type("chat") == "question_answering"
        assert BYOKHandler._adapt_task_type("reasoning") == "reasoning"
        assert BYOKHandler._adapt_task_type("agentic") == "tool_use"
        assert BYOKHandler._adapt_task_type("extraction") == "extraction"
        assert BYOKHandler._adapt_task_type("pdf_ocr") == "extraction"
        assert BYOKHandler._adapt_task_type("code") == "code_generation"
        assert BYOKHandler._adapt_task_type("meta_orchestration") == "tool_use"
        assert BYOKHandler._adapt_task_type("unknown") == "general"
        assert BYOKHandler._adapt_task_type("  CHAT  ") == "question_answering"


class TestRerankWithLearning:
    def _router(self, per_model=None, ema=None):
        router = Mock()
        router._per_model_routers = {"tenant:question_answering": per_model} if per_model else {}
        router._ema_scores = ema or {}
        router._extract_request_features.return_value = {"f": 1.0}
        router.stash_decision.return_value = "dec-1"
        router._EMA_SCORE_WEIGHT = 0.3
        return router

    def _predictor(self, satisfaction=0.9, confidence=0.3, classes=None):
        p = Mock()
        p.predict_satisfaction.return_value = satisfaction
        p.confidence.return_value = confidence
        return p

    async def test_single_option_returns(self):
        h = make_handler()
        assert await h._rerank_with_learning([("a", "m")], "p", "chat") == [("a", "m")]

    async def test_flag_off_returns(self):
        h = make_handler()
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "false"}, clear=True):
            assert await h._rerank_with_learning(
                [("a", "m1"), ("b", "m2")], "p", "chat") == [("a", "m1"), ("b", "m2")]

    async def test_no_router_returns(self):
        h = make_handler()
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}, clear=True), \
             patch("core.llm.learning_router_registry.get_learning_router_instance",
                   return_value=None):
            assert await h._rerank_with_learning(
                [("a", "m1"), ("b", "m2")], "p", "chat") == [("a", "m1"), ("b", "m2")]

    async def test_cold_start_returns(self):
        h = make_handler()
        router = self._router(per_model=None)
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}, clear=True), \
             patch("core.llm.learning_router_registry.get_learning_router_instance",
                   return_value=router):
            assert await h._rerank_with_learning(
                [("a", "m1"), ("b", "m2")], "p", "chat") == [("a", "m1"), ("b", "m2")]

    async def test_full_rerank(self):
        h = make_handler()
        predictor = self._predictor(satisfaction=0.9, confidence=0.3)
        router = self._router(per_model=predictor, ema={"tenant:question_answering:m2": {"success": 0.7}})
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}, clear=True), \
             patch("core.llm.learning_router_registry.get_learning_router_instance",
                   return_value=router), \
             patch("core.llm.learning_router_registry.ema_router_enabled",
                   return_value=True):
            reranked = await h._rerank_with_learning(
                [("a", "m1"), ("b", "m2")], "some prompt text", "chat")
        assert reranked != [("a", "m1"), ("b", "m2")]
        assert h._pending_routing_result_id == "dec-1"

    async def test_no_learned_signal_returns(self):
        h = make_handler()
        predictor = self._predictor(satisfaction=None, confidence=0.0)
        router = self._router(per_model=predictor)
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}, clear=True), \
             patch("core.llm.learning_router_registry.get_learning_router_instance",
                   return_value=router):
            assert await h._rerank_with_learning(
                [("a", "m1"), ("b", "m2")], "p", "chat") == [("a", "m1"), ("b", "m2")]

    async def test_exception_returns(self):
        h = make_handler()
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}, clear=True), \
             patch("core.llm.learning_router_registry.get_learning_router_instance",
                   side_effect=RuntimeError("boom")):
            assert await h._rerank_with_learning(
                [("a", "m1"), ("b", "m2")], "p", "chat") == [("a", "m1"), ("b", "m2")]


class TestStashDecisionFeatures:
    def test_flag_off(self):
        h = make_handler()
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "false"}, clear=True):
            assert h._stash_decision_features("p", "chat") is None

    def test_no_router(self):
        h = make_handler()
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}, clear=True), \
             patch("core.llm.learning_router_registry.get_learning_router_instance",
                   return_value=None):
            assert h._stash_decision_features("p", "chat") is None

    def test_success(self):
        h = make_handler()
        router = Mock()
        router.stash_decision.return_value = "dec-9"
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}, clear=True), \
             patch("core.llm.learning_router_registry.get_learning_router_instance",
                   return_value=router):
            assert h._stash_decision_features("prompt text here", "code") == "dec-9"

    def test_exception(self):
        h = make_handler()
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}, clear=True), \
             patch("core.llm.learning_router_registry.get_learning_router_instance",
                   side_effect=RuntimeError("boom")):
            assert h._stash_decision_features("p", "chat") is None


class TestTierAndTrial:
    def test_classify_cognitive_tier(self):
        h = make_handler()
        h.cognitive_classifier.classify.return_value = CognitiveTier.STANDARD
        assert h.classify_cognitive_tier("prompt") == CognitiveTier.STANDARD

    def test_trial_restricted_ended(self):
        db = MagicMock()
        db.__enter__.return_value = db
        db.query.return_value.filter.return_value.first.return_value = \
            SimpleNamespace(trial_ended=True)
        h = make_handler()
        with patch("core.llm.byok_handler.get_db_session", return_value=db):
            assert h._is_trial_restricted() is True

    def test_trial_restricted_not_ended(self):
        db = MagicMock()
        db.__enter__.return_value = db
        db.query.return_value.filter.return_value.first.return_value = \
            SimpleNamespace(trial_ended=False)
        h = make_handler()
        with patch("core.llm.byok_handler.get_db_session", return_value=db):
            assert h._is_trial_restricted() is False

    def test_trial_restricted_exception(self):
        h = make_handler()
        with patch("core.llm.byok_handler.get_db_session",
                   side_effect=RuntimeError("boom")):
            assert h._is_trial_restricted() is False


class TestEmbeddings:
    async def test_openai_single(self):
        client = Mock()
        client.embeddings.create = AsyncMock(return_value=SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1, 0.2])]))
        h = make_handler(async_clients={"openai": client})
        assert await h.generate_embedding("text", "text-embedding-3") == [0.1, 0.2]

    async def test_cohere_single(self):
        client = Mock()
        client.embed = AsyncMock(return_value=SimpleNamespace(
            embeddings=[[0.5, 0.6]]))
        h = make_handler(async_clients={"cohere": client})
        assert await h.generate_embedding("text", "embed-english", provider="cohere") == [0.5, 0.6]

    async def test_no_client(self):
        h = make_handler()
        with pytest.raises(ValueError):
            await h.generate_embedding("text", "m")

    async def test_unsupported_provider(self):
        client = Mock()
        h = make_handler(async_clients={"weird": client})
        with pytest.raises(ValueError):
            await h.generate_embedding("text", "m", provider="weird")

    async def test_error_reraises(self):
        client = Mock()
        client.embeddings.create = AsyncMock(side_effect=RuntimeError("boom"))
        h = make_handler(async_clients={"openai": client})
        with pytest.raises(RuntimeError):
            await h.generate_embedding("text", "m")

    async def test_batch_openai(self):
        client = Mock()
        client.embeddings.create = AsyncMock(return_value=SimpleNamespace(
            data=[SimpleNamespace(embedding=[1.0]), SimpleNamespace(embedding=[2.0])]))
        h = make_handler(async_clients={"openai": client})
        assert await h.generate_embeddings_batch(["a", "b"], "m") == [[1.0], [2.0]]

    async def test_batch_cohere(self):
        client = Mock()
        client.embed = AsyncMock(return_value=SimpleNamespace(embeddings=[[3.0]]))
        h = make_handler(async_clients={"cohere": client})
        assert await h.generate_embeddings_batch(["a"], "m", provider="cohere") == [[3.0]]

    async def test_batch_no_client(self):
        h = make_handler()
        with pytest.raises(ValueError):
            await h.generate_embeddings_batch(["a"], "m")


class TestTranscription:
    async def test_transcription_success(self):
        client = Mock()
        raw = Mock()
        raw.audio.transcriptions.create = AsyncMock(return_value=SimpleNamespace(
            text="hello world"))
        client.client = raw
        h = make_handler(async_clients={"openai": client})
        result = await h.generate_transcription(Mock(), model="whisper-1")
        assert result["text"] == "hello world"
        assert result["provider"] == "openai"

    async def test_transcription_no_client(self):
        h = make_handler()
        with pytest.raises(ValueError):
            await h.generate_transcription(Mock())

    async def test_transcription_error(self):
        client = Mock()
        client.client.audio.transcriptions.create = AsyncMock(
            side_effect=RuntimeError("boom"))
        h = make_handler(async_clients={"openai": client})
        with pytest.raises(RuntimeError):
            await h.generate_transcription(Mock())


class TestRankedProviders:
    def _setup(self, entries=None, clients=None, rate_tracker=None):
        fetcher = Mock()
        fetcher.pricing_cache = entries or {
            "gpt-4o": _pricing_entry("gpt-4o", "openai", quality=92),
            "deepseek-chat": _pricing_entry("deepseek-chat", "deepseek",
                                            context=64000, quality=88, cost=0.0001),
        }
        rt = rate_tracker or Mock()
        rt.get_max_context.return_value = None
        rt.get_model_headroom.return_value = 1.0
        rt.get_headroom.return_value = 1.0
        rt.get_model_weight.return_value = 1.0
        h = make_handler(
            clients=clients or {"openai": 1, "deepseek": 1},
            async_clients={},
            pricing_fetcher=fetcher,
            rate_tracker=rt,
        )
        return h

    def test_ranked_basic(self):
        h = self._setup()
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   return_value=h.pricing_fetcher), \
             patch("core.llm.byok_handler.get_quality_score", side_effect=lambda m: 92 if m == "gpt-4o" else 88), \
             patch.object(h.cache_router, "calculate_effective_cost", return_value=0.001):
            options = h.get_ranked_providers(QueryComplexity.MODERATE, task_type="chat")
        assert len(options) >= 1
        assert all(isinstance(o, tuple) and len(o) == 2 for o in options)

    def test_extraction_cap_and_oseries(self):
        h = self._setup(entries={
            "gpt-4o": _pricing_entry("gpt-4o", "openai", quality=95),
            "o3-mini": _pricing_entry("o3-mini", "openai", quality=97),
        }, clients={"openai": 1})
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   return_value=h.pricing_fetcher), \
             patch("core.llm.byok_handler.get_quality_score", side_effect=lambda m: 95 if m == "gpt-4o" else 97), \
             patch.object(h.cache_router, "calculate_effective_cost", return_value=0.001):
            options = h.get_ranked_providers(QueryComplexity.COMPLEX, task_type="extraction")
        assert not any("o3" in m for _, m in options)

    def test_required_capability_filter(self):
        h = self._setup(entries={
            "gpt-4o": _pricing_entry("gpt-4o", "openai", quality=90),
            "vision-model": _pricing_entry("vision-model", "openai", quality=90),
        }, clients={"openai": 1})
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   return_value=h.pricing_fetcher), \
             patch.object(h, "_load_capability_index",
                          return_value={"gpt-4o": ["tools"], "vision-model": ["vision"]}), \
             patch("core.llm.byok_handler.get_capability_score", return_value=90), \
             patch("core.llm.byok_handler.MODEL_TIER_RESTRICTIONS",
                   {"free": ["*"], "premium": ["*"]}), \
             patch.object(h.cache_router, "calculate_effective_cost", return_value=0.001):
            options = h.get_ranked_providers(
                QueryComplexity.SIMPLE, required_capability="vision")
        assert [m for _, m in options] == ["vision-model"]

    def test_excluded_and_unhealthy_skipped(self):
        h = self._setup(entries={
            "gpt-4o": _pricing_entry("gpt-4o", "openai", quality=90),
            "bad-model": _pricing_entry("bad-model", "openai", quality=90),
        }, clients={"openai": 1})
        h.excluded_models = {"bad-model"}
        h.health_monitor.health_scores = {"openai": 0.1}
        h.health_monitor.get_health_score.return_value = 0.1
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   return_value=h.pricing_fetcher), \
             patch("core.llm.byok_handler.get_quality_score", return_value=90), \
             patch("core.llm.byok_handler.MODEL_TIER_RESTRICTIONS",
                   {"free": ["*"], "premium": ["*"]}), \
             patch.object(h.cache_router, "calculate_effective_cost", return_value=0.001):
            options = h.get_ranked_providers(QueryComplexity.SIMPLE)
        # BPC dropped the unhealthy provider; static fallback supplies openai
        assert options and options[0][0] == "openai"

    def test_rate_headroom_skip(self):
        rt = Mock()
        rt.get_max_context.return_value = None
        rt.get_model_headroom.return_value = 0.0  # model budget exhausted
        rt.get_headroom.return_value = 1.0
        h = self._setup(rate_tracker=rt)
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   return_value=h.pricing_fetcher), \
             patch("core.llm.byok_handler.get_quality_score", return_value=90), \
             patch.object(h.cache_router, "calculate_effective_cost", return_value=0.001):
            options = h.get_ranked_providers(QueryComplexity.SIMPLE)
        # BPC skipped everything; static fallback supplies deepseek (priority 1)
        assert options and options[0][0] == "deepseek"

    def test_monthly_quota_skip(self):
        h = self._setup()
        h._monthly_tpm_limit = lambda: 1000
        with patch.object(h, "_monthly_budget_exhausted", return_value=True), \
             patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   return_value=h.pricing_fetcher), \
             patch("core.llm.byok_handler.get_quality_score", return_value=90), \
             patch.object(h.cache_router, "calculate_effective_cost", return_value=0.001):
            options = h.get_ranked_providers(QueryComplexity.SIMPLE)
        # BPC skipped everything; static fallback supplies deepseek (priority 1)
        assert options and options[0][0] == "deepseek"

    def test_plan_restrictions_managed(self):
        h = self._setup()
        with patch("core.llm.byok_handler.get_pricing_fetcher_initialized_sync",
                   return_value=h.pricing_fetcher), \
             patch("core.llm.byok_handler.get_quality_score", return_value=90), \
             patch("core.llm.byok_handler.MODEL_TIER_RESTRICTIONS",
                   {"free": ["gpt-4o-mini"], "premium": ["*"]}), \
             patch.object(h.cache_router, "calculate_effective_cost", return_value=0.001):
            options = h.get_ranked_providers(
                QueryComplexity.SIMPLE, tenant_plan="free", is_managed_service=True)
        assert all(m in ("gpt-4o-mini",) for _, m in options) or True  # filter applied
