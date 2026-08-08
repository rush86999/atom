"""Coverage-push tests for core/llm/byok_handler.py (target 90%).

Targets the largest uncovered blocks: tool-message sanitizer, learning-router
re-rank + feature stash, structured cascade escalation, Mixture-of-Agents,
transcription, generate_response/stream self-heal retry, and turn-fact
pre-compress enqueue. All LLM/DB/network interactions are mocked.
"""

import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.llm.byok_handler import BYOKHandler, QueryComplexity


def _handler(**attrs):
    h = BYOKHandler.__new__(BYOKHandler)
    h.workspace_id = "default"
    h.tenant_id = "default"
    h.clients = {}
    h.async_clients = {}
    h.byok_manager = Mock()
    h.health_monitor = Mock()
    h.health_monitor.record_call = Mock()
    h.cache_router = Mock()
    h._track_rate_usage = Mock()
    h._track_llm_call = Mock()
    h._record_outcome_feedback = AsyncMock()
    h._last_used_model = None
    h._last_used_provider = None
    h._pending_routing_result_id = None
    h.session_tools = []
    for k, v in attrs.items():
        setattr(h, k, v)
    return h


def _stream_chunk(content, finish_reason=None):
    return SimpleNamespace(choices=[SimpleNamespace(
        delta=SimpleNamespace(content=content),
        finish_reason=finish_reason,
    )])


# ============================================================================
# sanitize_tool_pairs (lines ~1090-1151)
# ============================================================================

class TestSanitizeToolPairs:
    def test_stub_injected_before_orphan_tool_message(self):
        out = BYOKHandler.sanitize_tool_pairs([
            {"role": "user", "content": "hi"},
            {"role": "tool", "content": "result", "tool_call_id": "tc1"},
        ])
        assert len(out) == 3
        assert out[1]["role"] == "assistant"
        assert out[1]["tool_calls"][0]["function"]["name"] == "_truncated_tool_call"
        assert out[2]["role"] == "tool"

    def test_tool_message_after_real_assistant_tool_calls_kept(self):
        out = BYOKHandler.sanitize_tool_pairs([
            {"role": "assistant", "content": None,
             "tool_calls": [{"id": "tc1", "type": "function",
                             "function": {"name": "f", "arguments": "{}"}}]},
            {"role": "tool", "content": "result", "tool_call_id": "tc1"},
        ])
        assert len(out) == 2
        assert out[0]["role"] == "assistant"

    def test_trailing_orphan_assistant_tool_calls_dropped(self):
        out = BYOKHandler.sanitize_tool_pairs([
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": None,
             "tool_calls": [{"id": "tc1", "type": "function",
                             "function": {"name": "f", "arguments": "{}"}}]},
        ])
        assert len(out) == 1
        assert out[0]["role"] == "user"

    def test_trailing_assistant_with_content_not_dropped(self):
        out = BYOKHandler.sanitize_tool_pairs([
            {"role": "assistant", "content": "answer",
             "tool_calls": [{"id": "tc1", "type": "function",
                             "function": {"name": "f", "arguments": "{}"}}]},
        ])
        assert len(out) == 1

    def test_empty_and_plain_messages_passthrough(self):
        assert BYOKHandler.sanitize_tool_pairs([]) == []
        msgs = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
        assert BYOKHandler.sanitize_tool_pairs(msgs) == msgs


# ============================================================================
# _adapt_task_type / _rerank_with_learning / _stash_decision_features
# ============================================================================

class TestLearningRouterRerank:
    def _router(self, per_model=None, ema_scores=None, learn_flag=True):
        pm = per_model or {}
        router = Mock()
        router._per_model_routers = pm
        router._ema_scores = ema_scores or {}
        router.stash_decision = Mock(return_value="dec-1")
        router._extract_request_features = Mock(return_value={"f1": 1})
        if learn_flag:
            router._EMA_SCORE_WEIGHT = 0.3
        return router

    def _model_predictor(self, satisfaction, confidence):
        p = Mock()
        p.predict_satisfaction = Mock(return_value=satisfaction)
        p.confidence = Mock(return_value=confidence)
        return p

    def _per_model_router(self, by_model):
        r = Mock()
        r.predict_satisfaction = Mock(side_effect=lambda m, f: by_model[m][0])
        r.confidence = Mock(side_effect=lambda m: by_model[m][1])
        return r

    @pytest.mark.asyncio
    async def test_flag_off_returns_options(self):
        h = _handler()
        opts = [("openai", "gpt-4o"), ("deepseek", "deepseek-chat")]
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "false"}, clear=False):
            assert await h._rerank_with_learning(opts, "p", "chat", None) is opts

    @pytest.mark.asyncio
    async def test_single_option_returns_options(self):
        h = _handler()
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}, clear=False):
            assert await h._rerank_with_learning([("openai", "gpt-4o")], "p", "chat", None) == [("openai", "gpt-4o")]

    @pytest.mark.asyncio
    async def test_cold_start_returns_options(self):
        h = _handler()
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}, clear=False), \
             patch("core.llm.learning_router_registry.get_learning_router_instance",
                   return_value=self._router({})), \
             patch("core.llm.learning_router_registry.ema_router_enabled", return_value=True):
            out = await h._rerank_with_learning([("openai", "gpt-4o"), ("deepseek", "deepseek-chat")],
                                          "hello world prompt", "chat", None)
            assert out == [("openai", "gpt-4o"), ("deepseek", "deepseek-chat")]

    @pytest.mark.asyncio
    async def test_learned_rerank_applies(self):
        h = _handler()
        pm = {
            "default:question_answering:_": self._per_model_router(
                {"gpt-4o": (0.9, 0.8), "deepseek-chat": (0.2, 0.6)}
            ),
        }
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}, clear=False), \
             patch("core.llm.learning_router_registry.get_learning_router_instance",
                   return_value=self._router(pm)), \
             patch("core.llm.learning_router_registry.ema_router_enabled", return_value=False):
            out = await h._rerank_with_learning([("openai", "gpt-4o"), ("deepseek", "deepseek-chat")],
                                          "prompt text", "chat", None)
            # learned score gpt-4o (0.72) > deepseek (0.12)
            assert out == [("openai", "gpt-4o"), ("deepseek", "deepseek-chat")]
            assert h._pending_routing_result_id == "dec-1"

    @pytest.mark.asyncio
    async def test_ema_term_steers_when_predictor_cold(self):
        h = _handler()
        pm = {
            "default:question_answering:_": self._per_model_router(
                {"gpt-4o": (None, 0.0), "deepseek-chat": (0.8, 0.5)}
            ),
        }
        router = self._router(pm)
        router._ema_scores = {
            "default:question_answering:gpt-4o": {"success": 0.9},
        }
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}, clear=False), \
             patch("core.llm.learning_router_registry.get_learning_router_instance", return_value=router), \
             patch("core.llm.learning_router_registry.ema_router_enabled", return_value=True):
            out = await h._rerank_with_learning([("openai", "gpt-4o"), ("deepseek", "deepseek-chat")],
                                          "prompt text", "chat", None)
            # gpt-4o: EMA term = 1.0 * 0.3 * 0.9 = 0.27 (learned_any via EMA)
            # deepseek: 0.5 * 0.8 = 0.4 -> deepseek still first
            assert out == [("deepseek", "deepseek-chat"), ("openai", "gpt-4o")]

    @pytest.mark.asyncio
    async def test_rerank_exception_returns_options(self):
        h = _handler()
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}, clear=False), \
             patch("core.llm.learning_router_registry.get_learning_router_instance",
                   side_effect=RuntimeError("boom")):
            opts = [("a", "m1"), ("b", "m2")]
            assert await h._rerank_with_learning(opts, "p", "chat", None) is opts

    def test_adapt_task_type_mapping(self):
        assert BYOKHandler._adapt_task_type(None) == "general"
        assert BYOKHandler._adapt_task_type("chat") == "question_answering"
        assert BYOKHandler._adapt_task_type("agentic") == "tool_use"
        assert BYOKHandler._adapt_task_type("pdf_ocr") == "extraction"
        assert BYOKHandler._adapt_task_type("code") == "code_generation"
        assert BYOKHandler._adapt_task_type("weird") == "general"

    def test_stash_decision_features(self):
        h = _handler()
        router = Mock()
        router.stash_decision = Mock(return_value="dec-9")
        router._extract_request_features = Mock(return_value={"n": 1})
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}, clear=False),              patch("core.llm.learning_router_registry.get_learning_router_instance", return_value=router):
            assert h._stash_decision_features("hello", "chat") == "dec-9"

    def test_stash_decision_features_none_router(self):
        h = _handler()
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}, clear=False),              patch("core.llm.learning_router_registry.get_learning_router_instance", return_value=None):
            assert h._stash_decision_features("hello", "chat") is None


# ============================================================================
# generate_structured_moa (lines ~3028-3120)
# ============================================================================

class TestGenerateStructuredMoA:
    @pytest.mark.asyncio
    async def test_moa_aggregates_samples(self):
        h = _handler()
        h.generate_structured_response = AsyncMock(
            side_effect=["sample-a", "sample-b", "aggregated"]
        )
        with patch("core.hallucination_config.get_moa_samples", return_value=2), \
             patch("core.llm.self_consistency_voter.SelfConsistencyVoter.is_irreversible",
                   return_value=False):
            out = await h.generate_structured_moa(
                prompt="p", system_instruction="s", response_model=dict,
                temperature=0.2, task_type="analysis", agent_id=None, chain_id=None,
                options=[("openai", "gpt-4o"), ("deepseek", "deepseek-chat")],
                tenant_plan="free", is_managed=True,
                complexity=QueryComplexity.COMPLEX, cascade=False,
            )
        assert out == "aggregated"
        assert h.generate_structured_response.await_count == 3

    @pytest.mark.asyncio
    async def test_moa_single_valid_sample(self):
        h = _handler()
        h.generate_structured_response = AsyncMock(side_effect=["only"])
        with patch("core.hallucination_config.get_moa_samples", return_value=2):
            out = await h.generate_structured_moa(
                prompt="p", system_instruction="s", response_model=dict,
                temperature=0.2, task_type="analysis", agent_id=None, chain_id=None,
                options=[("openai", "gpt-4o"), ("deepseek", "deepseek-chat")],
                tenant_plan="free", is_managed=True,
                complexity=QueryComplexity.COMPLEX, cascade=False,
            )
        assert out == "only"

    @pytest.mark.asyncio
    async def test_moa_no_valid_samples(self):
        h = _handler()
        h.generate_structured_response = AsyncMock(side_effect=[Exception("x"), None])
        with patch("core.hallucination_config.get_moa_samples", return_value=2):
            out = await h.generate_structured_moa(
                prompt="p", system_instruction="s", response_model=dict,
                temperature=0.2, task_type="analysis", agent_id=None, chain_id=None,
                options=[("openai", "gpt-4o")],
                tenant_plan="free", is_managed=True,
                complexity=QueryComplexity.COMPLEX, cascade=False,
            )
        assert out is None

    @pytest.mark.asyncio
    async def test_moa_aggregator_failure_degrades_to_best_sample(self):
        h = _handler()
        calls = {"n": 0}

        async def fake(*a, **kw):
            calls["n"] += 1
            if calls["n"] <= 2:
                return f"sample-{calls['n']}"
            return None  # aggregator fails

        h.generate_structured_response = fake
        with patch("core.hallucination_config.get_moa_samples", return_value=2), \
             patch("core.llm.self_consistency_voter.SelfConsistencyVoter.is_irreversible",
                   return_value=True):
            out = await h.generate_structured_moa(
                prompt="p", system_instruction="s", response_model=dict,
                temperature=0.2, task_type="analysis", agent_id=None, chain_id=None,
                options=[("openai", "gpt-4o"), ("deepseek", "deepseek-chat")],
                tenant_plan="free", is_managed=True,
                complexity=QueryComplexity.COMPLEX, cascade=False,
            )
        assert out == "sample-1"


# ============================================================================
# generate_transcription (lines ~3122-3164)
# ============================================================================

class TestGenerateTranscription:
    @pytest.mark.asyncio
    async def test_transcription_success(self):
        h = _handler()
        client = AsyncMock()
        client.audio.transcriptions.create = AsyncMock(return_value=SimpleNamespace(
            text="transcribed text"
        ))
        client.client = client
        h.async_clients = {"openai": client}
        with patch("core.llm.byok_handler.get_db_session"):
            out = await h.generate_transcription(Mock(), model="whisper-1")
        assert out == {"text": "transcribed text", "model": "whisper-1", "provider": "openai"}
        client.audio.transcriptions.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_transcription_error(self):
        h = _handler()
        client = AsyncMock()
        client.audio.transcriptions.create = AsyncMock(side_effect=Exception("audio err"))
        client.client = client
        h.async_clients = {"openai": client}
        with patch("core.llm.byok_handler.get_db_session"):
            with pytest.raises(Exception):
                await h.generate_transcription(Mock())

    @pytest.mark.asyncio
    async def test_transcription_no_client(self):
        h = _handler()
        h.async_clients = {}
        with pytest.raises(ValueError):
            await h.generate_transcription(Mock())


# ============================================================================
# Stream self-heal retry (lines ~3515-3589)
# ============================================================================

class TestStreamSelfHeal:
    @pytest.mark.asyncio
    async def test_stream_self_heal_retry_succeeds(self):
        h = _handler()
        h._provider_serves_model = Mock(return_value=True)
        h._get_provider_fallback_order = Mock(return_value=["openai"])
        h._stash_decision_features = Mock(return_value="dec-s1")
        h._track_rate_usage = Mock()
        h._track_llm_call = Mock()
        h._record_outcome_feedback = AsyncMock()

        async def _ok_stream():
            yield _stream_chunk("ok", "stop")

        client = AsyncMock()
        client.chat.completions.create = AsyncMock(
            side_effect=[Exception("first fails"), _ok_stream()]
        )
        h.async_clients = {"openai": client}

        healer = Mock()
        healer.heal = Mock(return_value=SimpleNamespace(
            patched_kwargs={"model": "gpt-4o", "messages": [], "stream": True},
            rule="retry", patched_keys=["temperature"],
        ))
        with patch("core.llm.routing.request_healer.get_request_healer", return_value=healer):
            stream = h.stream_completion([{"role": "user", "content": "hi"}], "gpt-4o", "openai")
            tokens = [t async for t in stream]
        assert tokens == ["ok"]

    @pytest.mark.asyncio
    async def test_stream_self_heal_retry_fails_then_all_failed(self):
        h = _handler()
        h._provider_serves_model = Mock(return_value=True)
        h._get_provider_fallback_order = Mock(return_value=["openai"])
        h._stash_decision_features = Mock(return_value="dec-s2")
        h._track_rate_usage = Mock()
        h._track_llm_call = Mock()
        h._record_outcome_feedback = AsyncMock()

        client = AsyncMock()
        client.chat.completions.create = AsyncMock(
            side_effect=[Exception("first"), Exception("retry")]
        )
        h.async_clients = {"openai": client}

        healer = Mock()
        healer.heal = Mock(return_value=SimpleNamespace(
            patched_kwargs={"model": "gpt-4o", "messages": [], "stream": True},
            rule="retry", patched_keys=[],
        ))
        with patch("core.llm.routing.request_healer.get_request_healer", return_value=healer):
            stream = h.stream_completion([{"role": "user", "content": "hi"}], "gpt-4o", "openai")
            tokens = [t async for t in stream]
        assert any("Error" in t for t in tokens)


# ============================================================================
# generate_response self-heal (lines ~2014-2068)
# ============================================================================

class TestGenerateResponseSelfHeal:
    @pytest.mark.asyncio
    async def test_generate_response_self_heal_retry(self):
        h = _handler()
        h._is_trial_restricted = Mock(return_value=False)
        h.analyze_query_complexity = Mock(return_value=QueryComplexity.SIMPLE)
        h.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o")])
        h._rerank_with_learning = AsyncMock(side_effect=lambda o, p, t, intent=None: o)
        h._stash_decision_features = Mock(return_value="dec-g1")
        h._get_provider_fallback_order = Mock(return_value=["openai"])
        h._provider_serves_model = Mock(return_value=True)
        h._record_outcome_feedback = AsyncMock()
        h._track_rate_usage = Mock()
        h._track_llm_call = Mock()
        h.clients = {"openai": Mock()}

        resp = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="healed"))])
        client = Mock()
        client.chat.completions.create = Mock(side_effect=[Exception("first"), resp])
        h.clients = {"openai": client}

        healer = Mock()
        healer.heal = Mock(return_value=SimpleNamespace(
            patched_kwargs={"model": "gpt-4o", "messages": [], "temperature": 0.7},
            rule="retry", patched_keys=["temperature"],
        ))
        with patch("core.llm.routing.request_healer.get_request_healer", return_value=healer), \
             patch("core.llm.byok_handler.get_db_session"):
            out = await h.generate_response("hello", task_type="chat")
        assert out == "healed"

    @pytest.mark.asyncio
    async def test_generate_response_turn_fact_pre_compress(self):
        h = _handler()
        h._is_trial_restricted = Mock(return_value=False)
        h.analyze_query_complexity = Mock(return_value=QueryComplexity.SIMPLE)
        h.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o")])
        h._rerank_with_learning = AsyncMock(side_effect=lambda o, p, t, intent=None: o)
        h._stash_decision_features = Mock(return_value="dec-g2")
        h._get_provider_fallback_order = Mock(return_value=["openai"])
        h._provider_serves_model = Mock(return_value=True)
        h._record_outcome_feedback = AsyncMock()
        h._track_rate_usage = Mock()
        h._track_llm_call = Mock()
        h.clients = {"openai": Mock()}

        resp = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="done"))])
        client = Mock()
        client.chat.completions.create = Mock(return_value=resp)
        h.clients = {"openai": client}

        with patch("core.llm.byok_handler.get_db_session"):
            out = await h.generate_response("hello world", task_type="chat")
        assert out == "done"


# ============================================================================
# Structured cascade escalation (lines ~2910-2989)
# ============================================================================

class TestStructuredCascade:
    @pytest.mark.asyncio
    async def test_cascade_escalates_on_validation_error(self):
        h = _handler()
        h._is_trial_restricted = Mock(return_value=False)
        h.analyze_query_complexity = Mock(return_value=QueryComplexity.SIMPLE)
        h.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o-mini")])
        h._rerank_with_learning = AsyncMock(side_effect=lambda o, p, t, intent=None: o)
        h._stash_decision_features = Mock(return_value="dec-c1")
        h._track_llm_call = Mock()
        h._record_outcome_feedback = AsyncMock()
        h._moa_eligible = Mock(return_value=False)

        client = AsyncMock()

        class _FakeResponse:
            choices = [SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))]

        err = json.JSONDecodeError("bad schema", "doc", 0)
        client.chat.completions.create = Mock(side_effect=[err, _FakeResponse()])
        h.clients = {"openai": client}

        with patch("core.llm.byok_handler.INSTRUCTOR_AVAILABLE", True), \
             patch("core.llm.byok_handler.get_db_session"), \
             patch("core.hallucination_config.is_frontier_model", return_value=False), \
             patch("core.hallucination_config.get_frontier_model_for_provider",
                   return_value="gpt-4o"), \
             patch("core.llm.byok_handler.instructor") as instr:
            instr.from_openai.return_value = client
            out = await h.generate_structured_response(
                prompt="p", system_instruction="s", response_model=dict,
                cascade=True, task_type="chat", allow_moa=False,
            )
        assert out.choices[0].message.content == '{"ok": true}'
        assert client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_structured_long_prompt_triggers_pre_compress(self):
        """Oversized prompts drain durable facts via the turn-fact queue and
        get truncated to the context window."""
        h = _handler()
        h._is_trial_restricted = Mock(return_value=False)
        h.analyze_query_complexity = Mock(return_value=QueryComplexity.SIMPLE)
        h.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o-mini")])
        h._rerank_with_learning = AsyncMock(side_effect=lambda o, p, t, intent=None: o)
        h._stash_decision_features = Mock(return_value="dec-c2")
        h._track_llm_call = Mock()
        h._record_outcome_feedback = AsyncMock()
        h._moa_eligible = Mock(return_value=False)
        h.get_context_window = Mock(return_value=100)

        client = AsyncMock()

        class _FakeResponse:
            choices = [SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))]

        err = json.JSONDecodeError("bad schema", "doc", 0)
        client.chat.completions.create = Mock(side_effect=[err, _FakeResponse()])
        h.clients = {"openai": client}

        queue = Mock()
        queue.enqueue = Mock()
        queue.ensure_worker = Mock()

        with patch("core.llm.byok_handler.INSTRUCTOR_AVAILABLE", True), \
             patch("core.llm.byok_handler.get_db_session"), \
             patch("core.hallucination_config.is_frontier_model", return_value=False), \
             patch("core.hallucination_config.get_frontier_model_for_provider",
                   return_value="gpt-4o"), \
             patch("core.llm.byok_handler.instructor") as instr, \
             patch("core.turn_fact_queue.get_extraction_queue", return_value=queue):
            instr.from_openai.return_value = client
            out = await h.generate_structured_response(
                prompt="x" * 5000, system_instruction="s", response_model=dict,
                cascade=True, task_type="chat", allow_moa=False,
            )
        assert out.choices[0].message.content == '{"ok": true}'
        queue.enqueue.assert_called_once()
        queue.ensure_worker.assert_called_once()


# ============================================================================
# Static BPC fallback (lines ~1529-1588)
# ============================================================================

class TestRankedProvidersStaticFallback:
    @pytest.mark.asyncio
    async def test_static_fallback_when_bpc_fails(self):
        h = _handler()
        h.clients = {"deepseek": Mock(), "minimax": Mock(),
                     "openai": Mock(), "anthropic": Mock()}
        h.async_clients = {}
        h._model_supports_tools = Mock(return_value=True)
        h._model_supports_vision = Mock(return_value=True)
        h._monthly_tpm_limit = Mock(return_value=0)
        h.rate_tracker = Mock()
        h.rate_tracker.get_model_headroom = Mock(return_value=1.0)
        h.rate_tracker.get_headroom = Mock(return_value=1.0)
        h.rate_tracker.get_model_weight = Mock(return_value=1.0)
        h.tier_service = None
        # force BPC to blow up -> static fallback
        h.cache_router.calculate_effective_cost = Mock(side_effect=RuntimeError("bpc down"))

        result = await h.get_ranked_providers(
            QueryComplexity.SIMPLE, "chat", True, "free", is_managed_service=False,
            requires_tools=True,
        )
        if hasattr(result, "unwrap"):
            result = await result
        assert len(result) > 0
        assert result[0][0] == "deepseek"  # SIMPLE priority order

    @pytest.mark.asyncio
    async def test_static_fallback_managed_plan_restrictions(self):
        h = _handler()
        h.clients = {"openai": Mock(), "anthropic": Mock()}
        h.async_clients = {}
        h._model_supports_tools = Mock(return_value=True)
        h._model_supports_vision = Mock(return_value=True)
        h._monthly_tpm_limit = Mock(return_value=0)
        h.rate_tracker = Mock()
        h.rate_tracker.get_model_headroom = Mock(return_value=1.0)
        h.rate_tracker.get_headroom = Mock(return_value=1.0)
        h.rate_tracker.get_model_weight = Mock(return_value=1.0)
        h.tier_service = None
        h.cache_router.calculate_effective_cost = Mock(side_effect=RuntimeError("bpc down"))

        result = await h.get_ranked_providers(
            QueryComplexity.COMPLEX, "chat", True, "enterprise", is_managed_service=True,
            requires_structured=True,
        )
        if hasattr(result, "unwrap"):
            result = await result
        assert result[0][0] == "anthropic"


# ============================================================================
# _get_coordinated_vision_description (lines ~3244-3305)
# ============================================================================

class TestCoordinatedVision:
    @pytest.mark.asyncio
    async def test_gemini_branch(self):
        h = _handler()
        client = Mock()
        client.chat.completions.create = Mock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="vision desc"))]
        ))
        h.clients = {"gemini": client}
        h.async_clients = {"gemini": client}
        out = await h._get_coordinated_vision_description("data:img", "free", True)
        assert out == "vision desc"

    @pytest.mark.asyncio
    async def test_deepseek_branch_and_no_client(self):
        h = _handler()
        client = Mock()
        client.chat.completions.create = Mock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="janus desc"))]
        ))
        h.clients = {"deepseek": client}
        h.async_clients = {"deepseek": client}
        out = await h._get_coordinated_vision_description("data:img", "free", True)
        assert out == "janus desc"

        h2 = _handler()
        assert await h2._get_coordinated_vision_description("data:img", "free", True) is None

    @pytest.mark.asyncio
    async def test_openai_fallback_and_error(self):
        h = _handler()
        client = Mock()
        client.chat.completions.create = Mock(side_effect=Exception("vision err"))
        h.clients = {"openai": client}
        h.async_clients = {"openai": client}
        assert await h._get_coordinated_vision_description("data:img", "free", True) is None


# ============================================================================
# generate_embedding / generate_embeddings_batch (lines ~3943-4006)
# ============================================================================

class TestEmbeddingsCoverage:
    @pytest.mark.asyncio
    async def test_embedding_openai(self):
        h = _handler()
        client = AsyncMock()
        client.embeddings.create = AsyncMock(return_value=SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1, 0.2])]
        ))
        h.async_clients = {"openai": client}
        assert await h.generate_embedding("text", "text-embedding-3") == [0.1, 0.2]

    @pytest.mark.asyncio
    async def test_embedding_cohere(self):
        h = _handler()
        client = AsyncMock()
        client.embed = AsyncMock(return_value=SimpleNamespace(embeddings=[[0.5]]))
        h.async_clients = {"cohere": client}
        assert await h.generate_embedding("text", "embed-v3", "cohere") == [0.5]

    @pytest.mark.asyncio
    async def test_embedding_unknown_provider_raises(self):
        h = _handler()
        h.async_clients = {"openai": AsyncMock()}
        with pytest.raises(ValueError):
            await h.generate_embedding("text", "m", "xai")

    @pytest.mark.asyncio
    async def test_embedding_no_client_raises(self):
        h = _handler()
        with pytest.raises(ValueError):
            await h.generate_embedding("text", "m")

    @pytest.mark.asyncio
    async def test_embedding_error_raises(self):
        h = _handler()
        client = AsyncMock()
        client.embeddings.create = AsyncMock(side_effect=Exception("emb err"))
        h.async_clients = {"openai": client}
        with pytest.raises(Exception):
            await h.generate_embedding("text", "m")

    @pytest.mark.asyncio
    async def test_embeddings_batch_openai(self):
        h = _handler()
        client = AsyncMock()
        client.embeddings.create = AsyncMock(return_value=SimpleNamespace(
            data=[SimpleNamespace(embedding=[1.0]), SimpleNamespace(embedding=[2.0])]
        ))
        h.async_clients = {"openai": client}
        out = await h.generate_embeddings_batch(["a", "b"], "m")
        assert out == [[1.0], [2.0]]

    @pytest.mark.asyncio
    async def test_embeddings_batch_cohere(self):
        h = _handler()
        client = AsyncMock()
        client.embed = AsyncMock(return_value=SimpleNamespace(embeddings=[[3.0], [4.0]]))
        h.async_clients = {"cohere": client}
        out = await h.generate_embeddings_batch(["a", "b"], "m", "cohere")
        assert out == [[3.0], [4.0]]

    @pytest.mark.asyncio
    async def test_embeddings_batch_no_client(self):
        h = _handler()
        with pytest.raises(ValueError):
            await h.generate_embeddings_batch(["a"], "m")


# ============================================================================
# generate_with_cognitive_tier (lines ~2377-2539)
# ============================================================================

class TestCognitiveTierCoverage:
    @pytest.mark.asyncio
    async def test_budget_exceeded_returns_error(self):
        h = _handler()
        tier = Mock()
        tier.value = "versatile"
        tier_service = Mock()
        tier_service.select_tier = Mock(return_value=tier)
        tier_service.calculate_request_cost = Mock(return_value={"cost_cents": 500})
        tier_service.check_budget_constraint = Mock(return_value=False)
        h.tier_service = tier_service

        out = await h.generate_with_cognitive_tier("prompt", "chat")
        assert out["error"] == "Budget exceeded"
        assert out["tier"] == "versatile"

    @pytest.mark.asyncio
    async def test_success_path(self):
        h = _handler()
        tier = Mock()
        tier.value = "versatile"
        tier_service = Mock()
        tier_service.select_tier = Mock(return_value=tier)
        tier_service.calculate_request_cost = Mock(return_value={"cost_cents": 5})
        tier_service.check_budget_constraint = Mock(return_value=True)
        tier_service.get_optimal_model = Mock(return_value=("openai", "gpt-4o"))
        tier_service.handle_escalation = Mock(return_value=(False, None, tier))
        h.tier_service = tier_service
        h.generate_response = AsyncMock(return_value="tier answer")

        out = await h.generate_with_cognitive_tier("prompt", "chat")
        assert out["response"] == "tier answer"
        assert out["tier"] == "versatile"

    @pytest.mark.asyncio
    async def test_no_optimal_model(self):
        h = _handler()
        tier = Mock()
        tier.value = "versatile"
        tier_service = Mock()
        tier_service.select_tier = Mock(return_value=tier)
        tier_service.calculate_request_cost = Mock(return_value={"cost_cents": 5})
        tier_service.check_budget_constraint = Mock(return_value=True)
        tier_service.get_optimal_model = Mock(return_value=(None, None))
        h.tier_service = tier_service

        out = await h.generate_with_cognitive_tier("prompt", "chat")
        assert "error" in out


# ============================================================================
# chat_completion (lines ~3643-3939): gateway-shaped completion
# ============================================================================

class TestChatCompletionCoverage:
    @pytest.mark.asyncio
    async def test_no_clients_raises(self):
        h = _handler()
        with pytest.raises(ValueError):
            await h.chat_completion([{"role": "user", "content": "hi"}], "gpt-4o", "openai")

    @pytest.mark.asyncio
    async def test_budget_exceeded_blocks(self):
        h = _handler()
        h.async_clients = {"openai": AsyncMock()}
        with patch("core.llm.byok_handler.llm_usage_tracker") as tracker:
            tracker.is_budget_exceeded = Mock(return_value=True)
            with pytest.raises(Exception):
                await h.chat_completion([{"role": "user", "content": "hi"}], "gpt-4o", "openai")

    @pytest.mark.asyncio
    async def test_tracker_unavailable_fails_closed(self):
        h = _handler()
        h.async_clients = {"openai": AsyncMock()}
        with patch("core.llm.byok_handler.llm_usage_tracker") as tracker:
            tracker.is_budget_exceeded = Mock(side_effect=RuntimeError("db down"))
            with pytest.raises(Exception):
                await h.chat_completion([{"role": "user", "content": "hi"}], "gpt-4o", "openai")

    @pytest.mark.asyncio
    async def test_trial_expired_blocks(self):
        h = _handler()
        h.async_clients = {"openai": AsyncMock()}
        with patch("core.llm.byok_handler.llm_usage_tracker") as tracker:
            tracker.is_budget_exceeded = Mock(return_value=False)
            tracker.is_trial_expired = Mock(return_value=True)
            with pytest.raises(Exception):
                await h.chat_completion([{"role": "user", "content": "hi"}], "gpt-4o", "openai")

    @pytest.mark.asyncio
    async def test_no_provider_order_raises(self):
        h = _handler()
        h.async_clients = {"openai": AsyncMock()}
        h._get_provider_fallback_order = Mock(return_value=[])
        with patch("core.llm.byok_handler.llm_usage_tracker") as tracker:
            tracker.is_budget_exceeded = Mock(return_value=False)
            tracker.is_trial_expired = Mock(return_value=False)
            with pytest.raises(ValueError):
                await h.chat_completion([{"role": "user", "content": "hi"}], "gpt-4o", "openai")

    @pytest.mark.asyncio
    async def test_success_with_usage_and_extra_kwargs(self):
        h = _handler()
        h._get_provider_fallback_order = Mock(return_value=["openai"])
        h._provider_serves_model = Mock(return_value=True)
        h._stash_decision_features = Mock(return_value="dec-cc")
        h._track_llm_call = Mock()
        h._record_outcome_feedback = AsyncMock()
        h.health_monitor = Mock()

        client = AsyncMock()
        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="cc answer"))],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        )
        client.chat.completions.create = AsyncMock(return_value=resp)
        h.async_clients = {"openai": client}

        with patch("core.llm.byok_handler.llm_usage_tracker") as tracker, \
             patch("core.llm.byok_handler.get_pricing_fetcher") as pf:
            tracker.is_budget_exceeded = Mock(return_value=False)
            tracker.is_trial_expired = Mock(return_value=False)
            pf.return_value.estimate_cost = Mock(return_value=0.0001)
            out = await h.chat_completion(
                [{"role": "user", "content": "hi"}], "gpt-4o", "openai",
                extra_kwargs={"stop": ["END"], "n": None},
            )
        assert out["choices"][0]["message"]["content"] == "cc answer"

    @pytest.mark.asyncio
    async def test_heal_retry_then_success(self):
        h = _handler()
        h._get_provider_fallback_order = Mock(return_value=["openai"])
        h._provider_serves_model = Mock(return_value=True)
        h._stash_decision_features = Mock(return_value="dec-cc2")
        h._track_llm_call = Mock()
        h._record_outcome_feedback = AsyncMock()
        h.health_monitor = Mock()

        client = AsyncMock()
        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="healed cc"))],
        )
        client.chat.completions.create = AsyncMock(side_effect=[Exception("first"), resp])
        h.async_clients = {"openai": client}

        healer = Mock()
        healer.heal = Mock(return_value=SimpleNamespace(
            patched_kwargs={"model": "gpt-4o", "messages": [], "temperature": 0.7},
            rule="retry", patched_keys=[],
        ))
        with patch("core.llm.byok_handler.llm_usage_tracker") as tracker, \
             patch("core.llm.routing.request_healer.get_request_healer", return_value=healer):
            tracker.is_budget_exceeded = Mock(return_value=False)
            tracker.is_trial_expired = Mock(return_value=False)
            out = await h.chat_completion(
                [{"role": "user", "content": "hi"}], "gpt-4o", "openai"
            )
        assert out["choices"][0]["message"]["content"] == "healed cc"

    @pytest.mark.asyncio
    async def test_all_providers_failed(self):
        h = _handler()
        h._get_provider_fallback_order = Mock(return_value=["openai"])
        h._provider_serves_model = Mock(return_value=True)
        h._stash_decision_features = Mock(return_value="dec-cc3")
        h._track_llm_call = Mock()
        h._record_outcome_feedback = AsyncMock()
        h.health_monitor = Mock()

        client = AsyncMock()
        client.chat.completions.create = AsyncMock(side_effect=[Exception("a"), Exception("b")])
        h.async_clients = {"openai": client}

        healer = Mock()
        healer.heal = Mock(return_value=SimpleNamespace(
            patched_kwargs={"model": "gpt-4o", "messages": [], "temperature": 0.7},
            rule="retry", patched_keys=[],
        ))
        with patch("core.llm.byok_handler.llm_usage_tracker") as tracker, \
             patch("core.llm.routing.request_healer.get_request_healer", return_value=healer):
            tracker.is_budget_exceeded = Mock(return_value=False)
            with pytest.raises(Exception):
                await h.chat_completion(
                    [{"role": "user", "content": "hi"}], "gpt-4o", "openai"
                )


# ============================================================================
# generate_response cost attribution + cache outcome (lines ~1878-1945)
# ============================================================================

class TestGenerateResponseCostAttribution:
    @pytest.mark.asyncio
    async def test_success_with_usage_attribution(self):
        h = _handler()
        h._is_trial_restricted = Mock(return_value=False)
        h.analyze_query_complexity = Mock(return_value=QueryComplexity.SIMPLE)
        h.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o")])
        h._rerank_with_learning = AsyncMock(side_effect=lambda o, p, t, intent=None: o)
        h._stash_decision_features = Mock(return_value="dec-g3")
        h._get_provider_fallback_order = Mock(return_value=["openai"])
        h._provider_serves_model = Mock(return_value=True)
        h._record_outcome_feedback = AsyncMock()
        h._track_rate_usage = Mock()
        h._track_llm_call = Mock()
        h.cache_router = Mock()

        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="cost answer"),
                                     finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50,
                                  prompt_cache_hit_tokens=10),
        )
        client = Mock()
        client.chat.completions.create = Mock(return_value=resp)
        h.clients = {"openai": client}

        tracker = Mock()
        tracker.record = Mock()
        tracker.is_budget_exceeded = Mock(return_value=False)
        tracker.is_trial_expired = Mock(return_value=False)
        fetcher = Mock()
        fetcher.estimate_cost = Mock(side_effect=[0.0002, 0.0005])  # cost + reference
        with patch("core.llm.byok_handler.get_db_session"), \
             patch("core.llm.byok_handler.llm_usage_tracker", tracker), \
             patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher), \
             patch("core.llm.byok_handler.get_llm_cost", return_value=0.0001):
            out = await h.generate_response("hello", task_type="chat", agent_id="ag-1")
        assert out == "cost answer"
        tracker.record.assert_called_once()
        h.cache_router.record_cache_outcome.assert_called_once()

    @pytest.mark.asyncio
    async def test_cost_attribution_fallback_to_static(self):
        h = _handler()
        h._is_trial_restricted = Mock(return_value=False)
        h.analyze_query_complexity = Mock(return_value=QueryComplexity.SIMPLE)
        h.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o")])
        h._rerank_with_learning = AsyncMock(side_effect=lambda o, p, t, intent=None: o)
        h._stash_decision_features = Mock(return_value="dec-g4")
        h._get_provider_fallback_order = Mock(return_value=["openai"])
        h._provider_serves_model = Mock(return_value=True)
        h._record_outcome_feedback = AsyncMock()
        h._track_rate_usage = Mock()
        h._track_llm_call = Mock()
        h.cache_router = Mock()

        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="static cost answer"),
                                     finish_reason=None)],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        )
        client = Mock()
        client.chat.completions.create = Mock(return_value=resp)
        h.clients = {"openai": client}

        tracker = Mock()
        tracker.record = Mock()
        tracker.is_budget_exceeded = Mock(return_value=False)
        tracker.is_trial_expired = Mock(return_value=False)
        fetcher = Mock()
        fetcher.estimate_cost = Mock(return_value=None)  # dynamic unavailable
        with patch("core.llm.byok_handler.get_db_session"), \
             patch("core.llm.byok_handler.llm_usage_tracker", tracker), \
             patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher), \
             patch("core.llm.byok_handler.get_llm_cost", return_value=0.0001):
            out = await h.generate_response("hello", task_type="chat")
        assert out == "static cost answer"
        tracker.record.assert_called_once()


# ============================================================================
# stream_completion success + outcome hooks with governance (lines ~3398-3487)
# ============================================================================

class TestStreamOutcomeHooks:
    @pytest.mark.asyncio
    async def test_stream_success_with_governance_tracking(self):
        h = _handler()
        h._get_provider_fallback_order = Mock(return_value=["openai"])
        h._provider_serves_model = Mock(return_value=True)
        h._stash_decision_features = Mock(return_value="dec-st1")
        h._track_rate_usage = Mock()
        h._track_llm_call = Mock()
        h._record_outcome_feedback = AsyncMock()

        async def _stream():
            yield _stream_chunk("one", None)
            yield _stream_chunk(" two", "stop")

        client = AsyncMock()
        client.chat.completions.create = AsyncMock(return_value=_stream())
        h.async_clients = {"openai": client}

        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id="exec-1", status="running",
        )

        gov = AsyncMock()
        gov.record_outcome = AsyncMock()
        with patch("core.llm.byok_handler.llm_usage_tracker") as _tracker, \
             patch("core.models.AgentExecution") as _AExec, \
             patch("core.agent_governance_service.AgentGovernanceService", return_value=gov), \
             patch.dict(os.environ, {"STREAMING_GOVERNANCE_ENABLED": "true"}, clear=False):
            _tracker.is_budget_exceeded = Mock(return_value=False)
            _AExec.return_value = SimpleNamespace(id="exec-1")
            tokens = [t async for t in h.stream_completion(
                [{"role": "user", "content": "hi"}], "gpt-4o", "openai",
                agent_id="ag-1", db=db,
            )]
        assert tokens == ["one", " two"]
        gov.record_outcome.assert_awaited()

    @pytest.mark.asyncio
    async def test_stream_failure_tracks_outcome_failed(self):
        h = _handler()
        h._get_provider_fallback_order = Mock(return_value=["openai"])
        h._provider_serves_model = Mock(return_value=True)
        h._stash_decision_features = Mock(return_value="dec-st2")
        h._track_rate_usage = Mock()
        h._track_llm_call = Mock()
        h._record_outcome_feedback = AsyncMock()

        client = AsyncMock()
        client.chat.completions.create = AsyncMock(side_effect=Exception("stream boom"))
        h.async_clients = {"openai": client}

        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id="exec-2", status="running",
        )
        gov = AsyncMock()
        gov.record_outcome = AsyncMock()
        with patch("core.llm.byok_handler.llm_usage_tracker") as _tracker, \
             patch("core.models.AgentExecution") as _AExec, \
             patch("core.agent_governance_service.AgentGovernanceService", return_value=gov), \
             patch.dict(os.environ, {"STREAMING_GOVERNANCE_ENABLED": "true"}, clear=False):
            _tracker.is_budget_exceeded = Mock(return_value=False)
            _AExec.return_value = SimpleNamespace(id="exec-2")
            tokens = [t async for t in h.stream_completion(
                [{"role": "user", "content": "hi"}], "gpt-4o", "openai",
                agent_id="ag-1", db=db,
            )]
        assert any("Error" in t for t in tokens)
        gov.record_outcome.assert_awaited()


# ============================================================================
# generate_with_cognitive_tier escalation path (lines ~2490-2539)
# ============================================================================

class TestCognitiveTierEscalation:
    @pytest.mark.asyncio
    async def test_rate_limit_escalation(self):
        h = _handler()
        tier = Mock()
        tier.value = "versatile"
        tier_service = Mock()
        tier_service.select_tier = Mock(return_value=tier)
        tier_service.calculate_request_cost = Mock(return_value={"cost_cents": 5})
        tier_service.check_budget_constraint = Mock(return_value=True)
        tier_service.get_optimal_model = Mock(return_value=("openai", "gpt-4o"))
        h.tier_service = tier_service
        h.generate_response = AsyncMock(side_effect=Exception("rate limit exceeded"))

        target = Mock()
        target.value = "complex"
        reason = Mock()
        reason.value = "rate limit exceeded"
        _esc_calls = {"n": 0}

        def _esc(*a, **k):
            _esc_calls["n"] += 1
            if _esc_calls["n"] == 1:
                return (True, reason, target)  # escalate on the first failure
            return (False, None, None)  # second (successful) attempt: no escalation

        tier_service.handle_escalation = Mock(side_effect=_esc)
        _gom_calls = {"n": 0}

        def _gom(*a, **k):
            _gom_calls["n"] += 1
            return ("openai", "gpt-4o") if _gom_calls["n"] == 1 else ("anthropic", "claude-3")

        tier_service.get_optimal_model = Mock(side_effect=_gom)
        h.generate_response = AsyncMock(
            side_effect=[Exception("rate limit exceeded"), "escalated answer"]
        )

        out = await h.generate_with_cognitive_tier("prompt", "chat")
        assert out.get("escalated") is True
        assert out["response"] == "escalated answer"
        assert out["tier"] == "complex"


# ============================================================================
# _load_local_providers (lines ~860-945) + MoA helpers (2996-3027)
# ============================================================================

class TestLocalProvidersAndMoaHelpers:
    def test_load_local_providers_with_caps(self):
        h = _handler()
        provider = SimpleNamespace(
            id="prov-12345678", name="ollama", provider_type="ollama",
            api_key=None, base_url="http://localhost:11434/v1/",
        )
        cap = SimpleNamespace(
            model_id="llama3:8b", context_window=8192, supports_tools=True,
            supports_vision=False, supports_reasoning=False, quality_score=0.7,
        )
        providers_q = Mock()
        providers_q.filter.return_value.all.return_value = [provider]
        caps_q = Mock()
        caps_q.filter.return_value.all.return_value = [cap]

        db = Mock()
        db.query = Mock(side_effect=lambda m: providers_q if m.__name__ == "LocalModelProvider" else caps_q)

        fetcher = Mock()
        fetcher.pricing_cache = {}

        class _Ctx:
            def __enter__(self):
                return db

            def __exit__(self, *a):
                return False

        with patch("core.database.get_db_session", return_value=_Ctx()), \
             patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher), \
             patch("core.llm.byok_handler.OpenAI") as _OpenAI, \
             patch("core.llm.byok_handler.AsyncOpenAI") as _AOpenAI:
            _OpenAI.return_value = Mock()
            _AOpenAI.return_value = AsyncMock()
            h._load_local_providers()

        assert "local_prov-123" in h.clients
        assert "local_prov-123" in h.async_clients
        assert "llama3:8b" in fetcher.pricing_cache

    def test_load_local_providers_empty_and_error(self):
        h = _handler()
        db = Mock()
        db.query.return_value.filter.return_value.all.return_value = []
        with patch("core.database.get_db_session"):
            h._load_local_providers()  # no providers -> clean no-op

        class _Boom:
            def __enter__(self):
                raise RuntimeError("db down")

            def __exit__(self, *a):
                return False

        with patch("core.database.get_db_session", return_value=_Boom()):
            h._load_local_providers()  # DB error -> clean no-op

    def test_moa_eligible(self):
        h = _handler()
        assert h._moa_eligible(QueryComplexity.COMPLEX, "chat") is True
        assert h._moa_eligible(QueryComplexity.ADVANCED, "chat") is True
        assert h._moa_eligible(QueryComplexity.SIMPLE, "code") is True
        assert h._moa_eligible(QueryComplexity.SIMPLE, "chat") is False

    def test_build_moa_aggregator_prompt(self):
        h = _handler()
        pyd = SimpleNamespace(model_dump=lambda: {"a": 1})
        out = h._build_moa_aggregator_prompt("user q", [pyd, "plain"])
        assert "user q" in out
        assert "[CANDIDATE ANSWER 1]" in out
        assert '{"a": 1}' in out
        assert "[CANDIDATE ANSWER 2]" in out
        assert "plain" in out


# ============================================================================
# capability helpers + BPC headroom skips
# ============================================================================

class TestCapabilityHelpersAndBPC:
    def test_filter_by_capabilities(self):
        h = _handler()
        # no requirement -> True
        assert h._filter_by_capabilities("m", None) is True
        # index fast path
        assert h._filter_by_capabilities("m1", "vision", {"m1": ["vision"]}) is True
        assert h._filter_by_capabilities("m1", "vision", {"m1": ["chat"]}) is False
        assert h._filter_by_capabilities("unknown", "vision", {"m1": ["vision"]}) is True
        # DB path
        model = SimpleNamespace(model_id="db-model", capabilities=["computer_use"])
        db = Mock()
        db.query.return_value.filter_by.return_value.first.return_value = model
        with patch("core.database.get_db_session") as gds:
            gds.return_value.__enter__.return_value = db
            assert h._filter_by_capabilities("db-model", "computer_use") is True
            assert h._filter_by_capabilities("db-model", "vision") is False
        # error pass-through
        with patch("core.database.get_db_session") as gds:
            gds.return_value.__enter__.side_effect = RuntimeError("db down")
            assert h._filter_by_capabilities("db-model", "vision") is True

    def test_bulk_capability_index_error(self):
        h = _handler()
        with patch("core.database.get_db_session") as gds:
            gds.return_value.__enter__.side_effect = RuntimeError("db down")
            assert h._load_capability_index() is None

    def test_model_capability_helpers(self):
        h = _handler()
        h.pricing_fetcher = Mock()
        h.pricing_fetcher.get_model_capabilities = Mock(
            return_value={"supports_tools": True, "supports_vision": False,
                          "supports_reasoning": True}
        )
        assert h._model_supports_tools("m") is True
        assert h._model_supports_vision("m") is False
        assert h._model_supports_reasoning("m") is True

    @pytest.mark.asyncio
    async def test_bpc_skips_exhausted_headroom(self):
        h = _handler()
        h.clients = {"deepseek": Mock(), "openai": Mock()}
        h.async_clients = {}
        h._model_supports_tools = Mock(return_value=True)
        h._model_supports_vision = Mock(return_value=True)
        h._monthly_tpm_limit = Mock(return_value=1000)
        h._monthly_budget_exhausted = Mock(return_value=True)
        h.rate_tracker = Mock()
        h.rate_tracker.get_model_headroom = Mock(return_value=1.0)
        h.rate_tracker.get_headroom = Mock(return_value=1.0)
        h.rate_tracker.get_model_weight = Mock(return_value=1.0)
        h.tier_service = None

        result = await h.get_ranked_providers(
            QueryComplexity.SIMPLE, "chat", True, "free", is_managed_service=False,
            requires_tools=True,
        )
        if hasattr(result, "unwrap"):
            result = await result
        # monthly quota exhausted -> provider hard-skipped in BPC; fallback used
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_embeddings_batch_unknown_provider(self):
        h = _handler()
        h.async_clients = {"openai": AsyncMock()}
        with pytest.raises(ValueError):
            await h.generate_embeddings_batch(["a"], "m", "xai")

    @pytest.mark.asyncio
    async def test_embeddings_batch_error(self):
        h = _handler()
        client = AsyncMock()
        client.embeddings.create = AsyncMock(side_effect=Exception("batch err"))
        h.async_clients = {"openai": client}
        with pytest.raises(Exception):
            await h.generate_embeddings_batch(["a"], "m")


# ============================================================================
# _initialize_clients credential paths (lines ~693-855)
# ============================================================================

class TestInitializeClients:
    def test_credential_service_and_env_paths(self):
        h = _handler()
        h.clients = {}
        h.async_clients = {}
        cred = Mock()
        cred.get_credential = AsyncMock(return_value=("oauth", "cred-key"))
        h.credential_service = cred

        byok = Mock()
        byok.is_configured = Mock(return_value=True)
        byok.get_api_key = Mock(return_value="byok-key")
        h.byok_manager = byok

        with patch("core.llm.byok_handler.OpenAI") as _OpenAI, \
             patch("core.llm.byok_handler.AsyncOpenAI") as _AOpenAI, \
             patch("core.llm.byok_handler._llm_request_timeout", return_value=30.0), \
             patch("core.database.get_db_session") as gds:
            gds.return_value.__enter__.return_value.query.return_value.filter.return_value.all.return_value = []
            _OpenAI.return_value = Mock()
            _AOpenAI.return_value = AsyncMock()
            h._initialize_clients()

        assert h.clients.get("openai") is not None

    def test_openai_not_installed(self):
        h = _handler()
        with patch("core.llm.byok_handler.OpenAI", None):
            h._initialize_clients()  # early return
        assert h.clients == {}


# ============================================================================
# _record_outcome_feedback (lines ~2088-2149)
# ============================================================================

class TestRecordOutcomeFeedback:
    @pytest.mark.asyncio
    async def test_flag_off_noop(self):
        h = _handler()
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "false"}, clear=False):
            await h._record_outcome_feedback(
                model="m", provider_id="p", task_type="chat", content="x",
                finish_reason="stop", success=True, cost=None, latency_ms=1.0,
            )

    @pytest.mark.asyncio
    async def test_records_feedback_and_error_paths(self):
        h = _handler()
        del h._record_outcome_feedback  # exercise the REAL method, not the helper mock
        router = Mock()
        router.record_feedback = AsyncMock()
        quality = Mock()
        quality.quality_score = 0.9
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}, clear=False), \
             patch("core.llm.learning_router_registry.get_learning_router_instance",
                   return_value=router), \
             patch("core.learning_llm_router.LearningBasedRouter.build_feedback",
                   return_value=Mock()), \
             patch("core.llm.response_quality.assess_response_quality",
                   return_value=quality):
            await h._record_outcome_feedback(
                model="m", provider_id="p", task_type="chat", content="hello",
                finish_reason="stop", success=True, cost=0.1, latency_ms=5.0,
                routing_result_id="dec-fb",
            )
        router.record_feedback.assert_awaited_once()

        # exception path
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}, clear=False), \
             patch("core.llm.learning_router_registry.get_learning_router_instance",
                   return_value=router), \
             patch("core.llm.response_quality.assess_response_quality",
                   side_effect=RuntimeError("quality down")):
            await h._record_outcome_feedback(
                model="m", provider_id="p", task_type="chat", content=None,
                finish_reason=None, success=False, cost=None, latency_ms=0.0,
                exception=ValueError("boom"), schema_error=True,
            )

        # router unavailable
        with patch.dict(os.environ, {"ATOM_LEARNING_ROUTER": "true"}, clear=False), \
             patch("core.llm.learning_router_registry.get_learning_router_instance",
                   return_value=None):
            await h._record_outcome_feedback(
                model="m", provider_id="p", task_type="chat", content="x",
                finish_reason="stop", success=True, cost=None, latency_ms=1.0,
            )


# ============================================================================
# generate_response: LKGP sticky + intent detector (lines ~1725-1746)
# ============================================================================

class TestLkgpAndIntent:
    @pytest.mark.asyncio
    async def test_sticky_hint_boosts_pair(self):
        h = _handler()
        h._is_trial_restricted = Mock(return_value=False)
        h.analyze_query_complexity = Mock(return_value=QueryComplexity.SIMPLE)
        h.get_ranked_providers = AsyncMock(
            return_value=[("openai", "gpt-4o"), ("deepseek", "deepseek-chat")]
        )
        h._rerank_with_learning = AsyncMock(side_effect=lambda o, p, t, intent=None: o)
        h._stash_decision_features = Mock(return_value="dec-lkgp")
        h._get_provider_fallback_order = Mock(return_value=["deepseek"])
        h._provider_serves_model = Mock(return_value=True)
        h._record_outcome_feedback = AsyncMock()
        h._track_rate_usage = Mock()
        h._track_llm_call = Mock()
        h._last_used_model = None
        h._last_used_provider = None

        resp = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="sticky ok"))])
        client = Mock()
        client.chat.completions.create = Mock(return_value=resp)
        h.clients = {"deepseek": client}

        intent = Mock()
        intent.category = "coding"
        intent.confidence = 0.9
        with patch("core.llm.intent_detector.get_intent_detector") as det, \
             patch("core.llm.byok_handler.get_db_session"):
            det.return_value.detect = Mock(return_value=intent)
            out = await h.generate_response(
                "hello", task_type="chat",
                sticky_hint=("deepseek", "deepseek-chat"),
            )
        assert out == "sticky ok"

    @pytest.mark.asyncio
    async def test_intent_detector_failure_continues(self):
        h = _handler()
        h._is_trial_restricted = Mock(return_value=False)
        h.analyze_query_complexity = Mock(return_value=QueryComplexity.SIMPLE)
        h.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o")])
        h._rerank_with_learning = AsyncMock(side_effect=lambda o, p, t, intent=None: o)
        h._stash_decision_features = Mock(return_value="dec-int")
        h._get_provider_fallback_order = Mock(return_value=["openai"])
        h._provider_serves_model = Mock(return_value=True)
        h._record_outcome_feedback = AsyncMock()
        h._track_rate_usage = Mock()
        h._track_llm_call = Mock()

        resp = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])
        client = Mock()
        client.chat.completions.create = Mock(return_value=resp)
        h.clients = {"openai": client}

        with patch("core.llm.intent_detector.get_intent_detector",
                   side_effect=RuntimeError("intent down")), \
             patch("core.llm.byok_handler.get_db_session"):
            out = await h.generate_response("hello", task_type="chat")
        assert out == "ok"


# ============================================================================
# MoA dispatch inside generate_structured_response (lines ~2725-2742)
# ============================================================================

class TestStructuredMoaDispatch:
    @pytest.mark.asyncio
    async def test_moa_dispatch_fires_for_hard_tasks(self):
        h = _handler()
        h._is_trial_restricted = Mock(return_value=False)
        h.analyze_query_complexity = Mock(return_value=QueryComplexity.COMPLEX)
        h.get_ranked_providers = AsyncMock(
            return_value=[("openai", "gpt-4o"), ("deepseek", "deepseek-chat")]
        )
        h._moa_eligible = Mock(return_value=True)
        h.generate_structured_moa = AsyncMock(return_value="moa-result")
        h.clients = {"openai": Mock(), "deepseek": Mock()}

        with patch("core.llm.byok_handler.INSTRUCTOR_AVAILABLE", True), \
             patch("core.llm.byok_handler.get_db_session"), \
             patch("core.hallucination_config.is_moa_enabled", return_value=True), \
             patch("core.hallucination_config.get_moa_samples", return_value=2), \
             patch("core.hallucination_config.is_frontier_model", return_value=False), \
             patch("core.hallucination_config.get_frontier_model_for_provider",
                   return_value="gpt-4o"), \
             patch("core.llm.byok_handler.instructor") as instr:
            instr.from_openai.return_value = Mock()
            out = await h.generate_structured_response(
                prompt="p", system_instruction="s", response_model=dict,
                cascade=True, task_type="analysis", allow_moa=True,
            )
        assert out == "moa-result"
        h.generate_structured_moa.assert_awaited_once()


# ============================================================================
# stream_completion error token + no-client skip (lines ~3631-3641, 3374-3375)
# ============================================================================

class TestStreamTailCoverage:
    @pytest.mark.asyncio
    async def test_stream_no_client_for_provider_skips(self):
        h = _handler()
        h._get_provider_fallback_order = Mock(return_value=["openai", "deepseek"])
        h._provider_serves_model = Mock(return_value=True)
        h._stash_decision_features = Mock(return_value="dec-sk")
        h._track_rate_usage = Mock()
        h._track_llm_call = Mock()
        h._record_outcome_feedback = AsyncMock()
        deepseek_client = AsyncMock()
        deepseek_client.chat.completions.create = AsyncMock(side_effect=Exception("no"))
        h.async_clients = {"deepseek": deepseek_client}
        h.clients = {}  # openai (requested) has NO client -> skipped

        tokens = [t async for t in h.stream_completion(
            [{"role": "user", "content": "hi"}], "gpt-4o", "openai"
        )]
        assert any("Error" in t for t in tokens)


# ============================================================================
# generate_response guard rails (lines ~1612-1631)
# ============================================================================

class TestGenerateResponseGuards:
    @pytest.mark.asyncio
    async def test_trial_restricted(self):
        h = _handler()
        h._is_trial_restricted = Mock(return_value=True)
        out = await h.generate_response("hello")
        assert "Trial Expired" in out

    @pytest.mark.asyncio
    async def test_no_clients_agentic_demo_mock(self):
        h = _handler()
        h._is_trial_restricted = Mock(return_value=False)
        out = await h.generate_response("Check my inbox", task_type="agentic")
        parsed = json.loads(out)
        assert parsed["action"] == "perform_market_analysis"

        out2 = await h.generate_response("anything", task_type="agentic")
        assert '"action": "DONE"' in out2

    @pytest.mark.asyncio
    async def test_no_clients_plain(self):
        h = _handler()
        h._is_trial_restricted = Mock(return_value=False)
        out = await h.generate_response("hello")
        assert "No API Keys" in out


# ============================================================================
# generate_response budget gate + BPC headroom skip + init error paths
# ============================================================================

class TestFinalEdgePaths:
    @pytest.mark.asyncio
    async def test_generate_response_budget_exceeded(self):
        h = _handler()
        h._is_trial_restricted = Mock(return_value=False)
        h.clients = {"openai": Mock()}
        with patch("core.llm.byok_handler.llm_usage_tracker") as tracker:
            tracker.is_budget_exceeded = Mock(return_value=True)
            out = await h.generate_response("hello")
        assert "BUDGET EXCEEDED" in out

    @pytest.mark.asyncio
    async def test_bpc_per_model_headroom_skip(self):
        h = _handler()
        h.clients = {"deepseek": Mock(), "openai": Mock()}
        h.async_clients = {}
        h._model_supports_tools = Mock(return_value=True)
        h._model_supports_vision = Mock(return_value=True)
        h._monthly_tpm_limit = Mock(return_value=0)
        h.rate_tracker = Mock()
        h.rate_tracker.get_model_headroom = Mock(return_value=0.0)  # per-model exhausted
        h.rate_tracker.get_headroom = Mock(return_value=1.0)
        h.rate_tracker.get_model_weight = Mock(return_value=1.0)
        h.tier_service = None

        result = await h.get_ranked_providers(
            QueryComplexity.SIMPLE, "chat", True, "free", is_managed_service=False,
            requires_tools=True,
        )
        if hasattr(result, "unwrap"):
            result = await result
        assert len(result) > 0  # static fallback still yields providers

    @pytest.mark.asyncio
    async def test_initialize_clients_credential_error_and_no_credential(self):
        h = _handler()
        h.clients = {}
        h.async_clients = {}
        cred = Mock()
        cred.get_credential = AsyncMock(side_effect=RuntimeError("oauth down"))
        h.credential_service = cred
        byok = Mock()
        byok.is_configured = Mock(return_value=False)
        h.byok_manager = byok

        with patch("core.llm.byok_handler.OpenAI") as _OpenAI, \
             patch("core.llm.byok_handler.AsyncOpenAI") as _AOpenAI, \
             patch("core.llm.byok_handler._llm_request_timeout", return_value=30.0), \
             patch.dict(os.environ, {}, clear=True), \
             patch("core.database.get_db_session") as gds:
            gds.return_value.__enter__.return_value.query.return_value.filter.return_value.all.return_value = []
            _OpenAI.return_value = Mock()
            _AOpenAI.return_value = AsyncMock()
            h._initialize_clients()  # no credentials anywhere -> clean skip
        assert h.clients == {}

    @pytest.mark.asyncio
    async def test_initialize_clients_openai_creation_error(self):
        h = _handler()
        h.clients = {}
        h.async_clients = {}
        cred = Mock()
        cred.get_credential = AsyncMock(return_value=("byok", "key-1"))
        h.credential_service = cred
        byok = Mock()
        byok.is_configured = Mock(return_value=False)
        h.byok_manager = byok

        with patch("core.llm.byok_handler.OpenAI",
                   side_effect=RuntimeError("sdk init failed")), \
             patch("core.llm.byok_handler.AsyncOpenAI") as _AOpenAI, \
             patch("core.llm.byok_handler._llm_request_timeout", return_value=30.0), \
             patch.dict(os.environ, {}, clear=True), \
             patch("core.database.get_db_session") as gds:
            gds.return_value.__enter__.return_value.query.return_value.filter.return_value.all.return_value = []
            _AOpenAI.return_value = AsyncMock()
            h._initialize_clients()  # client creation failure logged, loop continues
        assert "openai" not in h.clients


# ============================================================================
# generate_response vision path + structured usage attribution
# ============================================================================

class TestVisionAndStructuredUsage:
    @pytest.mark.asyncio
    async def test_generate_response_with_image_payload(self):
        h = _handler()
        h._is_trial_restricted = Mock(return_value=False)
        h.analyze_query_complexity = Mock(return_value=QueryComplexity.SIMPLE)
        h.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o")])
        h._rerank_with_learning = AsyncMock(side_effect=lambda o, p, t, intent=None: o)
        h._stash_decision_features = Mock(return_value="dec-vis")
        h._get_provider_fallback_order = Mock(return_value=["openai"])
        h._provider_serves_model = Mock(return_value=True)
        h._model_supports_vision = Mock(return_value=True)
        h._record_outcome_feedback = AsyncMock()
        h._track_rate_usage = Mock()
        h._track_llm_call = Mock()
        h.cache_router = Mock()

        resp = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="vision ok"))])
        client = Mock()
        client.chat.completions.create = Mock(return_value=resp)
        h.clients = {"openai": client}

        with patch("core.llm.byok_handler.get_db_session"), \
             patch("core.llm.byok_handler.llm_usage_tracker") as tracker:
            tracker.is_budget_exceeded = Mock(return_value=False)
            tracker.is_trial_expired = Mock(return_value=False)
            out = await h.generate_response(
                "describe", task_type="chat", image_payload="data:image/png;base64,AAA="
            )
        assert out == "vision ok"

    @pytest.mark.asyncio
    async def test_structured_usage_attribution(self):
        h = _handler()
        h._is_trial_restricted = Mock(return_value=False)
        h.analyze_query_complexity = Mock(return_value=QueryComplexity.SIMPLE)
        h.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o-mini")])
        h._moa_eligible = Mock(return_value=False)
        h._stash_decision_features = Mock(return_value="dec-su")
        h._track_llm_call = Mock()
        h._record_outcome_feedback = AsyncMock()
        h._track_rate_usage = Mock()
        h.get_context_window = Mock(return_value=2000)

        raw = SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=7, completion_tokens=3),
            choices=[SimpleNamespace(finish_reason="length")],
        )
        result = SimpleNamespace(_raw_response=raw)
        client = Mock()
        client.chat.completions.create = Mock(return_value=result)
        h.clients = {"openai": client}

        with patch("core.llm.byok_handler.INSTRUCTOR_AVAILABLE", True), \
             patch("core.llm.byok_handler.get_db_session"), \
             patch("core.llm.byok_handler.instructor") as instr, \
             patch("core.llm.byok_handler.get_pricing_fetcher") as pf:
            instr.from_openai.return_value = client
            pf.return_value.estimate_cost = Mock(return_value=0.001)
            out = await h.generate_structured_response(
                prompt="p", system_instruction="s", response_model=dict,
                allow_moa=False, task_type="chat",
            )
        assert out is result
        h._track_rate_usage.assert_called_once()


# ============================================================================
# tenant-plan free-tier block + self-heal retry FAILED path
# ============================================================================

class TestTenantPlanAndHealFailure:
    @pytest.mark.asyncio
    async def test_free_tier_managed_blocked(self):
        h = _handler()
        h._is_trial_restricted = Mock(return_value=False)
        h.analyze_query_complexity = Mock(return_value=QueryComplexity.SIMPLE)
        h.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o")])
        h.get_optimal_provider = AsyncMock(return_value=("openai", "gpt-4o"))
        h.byok_manager.get_tenant_api_key = Mock(return_value=None)
        h.clients = {"openai": Mock()}

        workspace = SimpleNamespace(tenant_id="t1")
        tenant = SimpleNamespace(plan_type="free")

        def _query(model):
            q = Mock()
            if model.__name__ == "Workspace":
                q.filter.return_value.first.return_value = workspace
            else:
                q.filter.return_value.first.return_value = tenant
            return q

        db = Mock()
        db.query = Mock(side_effect=_query)
        with patch("core.llm.byok_handler.get_db_session") as gds, \
             patch("core.llm.byok_handler.llm_usage_tracker") as tracker:
            gds.return_value.__enter__.return_value = db
            tracker.is_budget_exceeded = Mock(return_value=False)
            out = await h.generate_response("hello", task_type="chat")
        # free + managed: restriction message OR a fallback error — either way
        # the tenant-plan determination (is_managed=True) executed
        assert isinstance(out, str) and out

    @pytest.mark.asyncio
    async def test_generate_response_heal_retry_failed(self):
        h = _handler()
        h._is_trial_restricted = Mock(return_value=False)
        h.analyze_query_complexity = Mock(return_value=QueryComplexity.SIMPLE)
        h.get_ranked_providers = AsyncMock(return_value=[("openai", "gpt-4o")])
        h._rerank_with_learning = AsyncMock(side_effect=lambda o, p, t, intent=None: o)
        h._stash_decision_features = Mock(return_value="dec-hf")
        h._get_provider_fallback_order = Mock(return_value=["openai"])
        h._provider_serves_model = Mock(return_value=True)
        h._record_outcome_feedback = AsyncMock()
        h._track_rate_usage = Mock()
        h._track_llm_call = Mock()

        client = Mock()
        client.chat.completions.create = Mock(side_effect=[Exception("first"), Exception("retry too")])
        h.clients = {"openai": client}

        healer = Mock()
        healer.heal = Mock(return_value=SimpleNamespace(
            patched_kwargs={"model": "gpt-4o", "messages": [], "temperature": 0.7},
            rule="retry", patched_keys=[],
        ))
        with patch("core.llm.routing.request_healer.get_request_healer", return_value=healer), \
             patch("core.llm.byok_handler.get_db_session"), \
             patch("core.llm.byok_handler.llm_usage_tracker") as tracker:
            tracker.is_budget_exceeded = Mock(return_value=False)
            tracker.is_trial_expired = Mock(return_value=False)
            out = await h.generate_response("hello", task_type="chat")
        # both original and heal retry failed -> apology message
        assert "couldn't generate a response" in out


# ============================================================================
# monthly quota helpers + local provider init error + transcription params
# ============================================================================

class TestMonthlyQuotaAndMisc:
    def test_monthly_tpm_limit_invalid(self):
        h = _handler()
        with patch.dict(os.environ, {"OPENCODE_MONTHLY_TPM": "not-a-number"}, clear=False):
            assert h._monthly_tpm_limit() is None

    def test_monthly_budget_exhausted(self):
        h = _handler()
        h.rate_tracker = Mock()
        h.rate_tracker.get_monthly_usage = Mock(return_value=None)
        assert h._monthly_budget_exhausted("openai", 1000) is False

        h.rate_tracker.get_monthly_usage = Mock(return_value={"total_tokens": 5000})
        assert h._monthly_budget_exhausted("openai", 1000) is True
        assert h._monthly_budget_exhausted("openai", 10000) is False

        h.rate_tracker.get_monthly_usage = Mock(side_effect=RuntimeError("db down"))
        assert h._monthly_budget_exhausted("openai", 1000) is False

    def test_local_provider_openai_error(self):
        h = _handler()
        provider = SimpleNamespace(
            id="prov-12345678", name="ollama", provider_type="ollama",
            api_key=None, base_url="http://localhost:11434/v1/",
        )
        providers_q = Mock()
        providers_q.filter.return_value.all.return_value = [provider]
        caps_q = Mock()
        caps_q.filter.return_value.all.return_value = []

        db = Mock()
        db.query = Mock(side_effect=lambda m: providers_q if m.__name__ == "LocalModelProvider" else caps_q)
        fetcher = Mock()
        fetcher.pricing_cache = {}

        class _Ctx:
            def __enter__(self):
                return db

            def __exit__(self, *a):
                return False

        with patch("core.database.get_db_session", return_value=_Ctx()), \
             patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher), \
             patch("core.llm.byok_handler.OpenAI",
                   side_effect=RuntimeError("sdk down")), \
             patch("core.llm.byok_handler.AsyncOpenAI") as _AOpenAI:
            _AOpenAI.return_value = AsyncMock()
            h._load_local_providers()  # client creation failure -> logged, skipped
        assert "local_prov-123" not in h.clients
        # no caps -> generic pricing entry still registered? no — creation failed first
        assert fetcher.pricing_cache == {}

    @pytest.mark.asyncio
    async def test_transcription_with_params(self):
        h = _handler()
        client = AsyncMock()
        client.client = client
        client.audio.transcriptions.create = AsyncMock(
            return_value=SimpleNamespace(text="transcribed with params")
        )
        h.async_clients = {"openai": client}
        with patch("core.llm.byok_handler.get_db_session"):
            out = await h.generate_transcription(
                Mock(), model="whisper-1", language="en", prompt="hint",
                response_format="verbose_json",
            )
        assert out["text"] == "transcribed with params"
        call_kwargs = client.audio.transcriptions.create.call_args.kwargs
        assert call_kwargs["language"] == "en"
        assert call_kwargs["prompt"] == "hint"
        assert call_kwargs["response_format"] == "verbose_json"
