"""Coverage wave 64i — core/llm_service.py to >=95% (TDD).

Extends the W47 baseline (87%) to >=95% by covering every remaining reachable
branch: tenant_id property, _get_handler cross-workspace construction,
_resolve_governance_model workspace-found path, generate_completion provider
fallback (no handler stash), generate_speech no-client raise, estimate_cost
fallback pricing (deepseek + default), self-consistency audit rollback failure,
embedding cohere branches + usage-tracking failure + re-raise, active
transcribe_audio delegation, and a regression lock on the ACTIVE (non-shadowed)
definitions of stream_completion / generate_embedding / generate_embeddings_batch
/ transcribe_audio (the shadowed duplicates were removed as dead code — see
source edit in this wave).

Style: mocked deps, ZERO LLM spend, no network, no real DB.
"""
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm.cognitive_tier_system import CognitiveTier
from core.llm.byok_handler import QueryComplexity
from core.llm_service import LLMProvider, LLMService, get_llm_service


def _service(db=None, handler=None, workspace_id="ws-1", tenant_id="t-1"):
    service = LLMService(db=db, workspace_id=workspace_id, tenant_id=tenant_id)
    if handler is not None:
        service._handler = handler
    return service


def _vote(**kw):
    defaults = dict(
        prompt_hash="abc123", sample_count=3, valid_count=2, winner_count=1,
        distinct_hashes=2, agreement_ratio=0.67, level="partial",
        winner_hash="hash1", temperatures=[0.2, 0.3, 0.4],
        winner=SimpleNamespace(name="Winner", value=1),
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _stream_tokens(handler, tokens):
    """Wire handler.stream_completion to be an async iterator of tokens."""
    handler.stream_completion = MagicMock(return_value=_AsyncIter(tokens))


class _AsyncIter:
    """Simple async iterator over a list (for mocking stream methods)."""

    def __init__(self, items):
        self._items = list(items)
        self._i = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._i >= len(self._items):
            raise StopAsyncIteration
        v = self._items[self._i]
        self._i += 1
        return v


class TestCoreAccessors:
    def test_tenant_id_property(self):
        service = _service(tenant_id="t-9")
        assert service.tenant_id == "t-9"

    def test_workspace_id_property(self):
        service = _service(workspace_id="ws-9")
        assert service.workspace_id == "ws-9"

    def test_handler_property_and_setter(self):
        service = _service()
        handler = MagicMock()
        service.handler = handler
        assert service.handler is handler
        assert service._handler is handler

    def test_default_ids_when_none(self):
        service = LLMService(db=None)
        assert service.workspace_id == "default"
        assert service.tenant_id == "default"

    def test_get_handler_same_workspace_returns_cached(self):
        handler = MagicMock()
        service = _service(handler=handler)
        assert service._get_handler() is handler
        assert service._get_handler(workspace_id="ws-1") is handler

    def test_get_handler_cross_workspace_builds_new(self):
        handler = MagicMock()
        service = _service(handler=handler)
        new_handler = service._get_handler(workspace_id="other-ws")
        assert new_handler is not handler
        assert new_handler.workspace_id == "other-ws"

    def test_get_llm_service_factory(self):
        svc = get_llm_service(workspace_id="w", tenant_id="t", db=None)
        assert isinstance(svc, LLMService)
        assert svc.workspace_id == "w"
        assert svc.tenant_id == "t"


class TestGetProvider:
    def test_all_providers(self):
        service = _service()
        cases = {
            "ollama/llama3": LLMProvider.OLLAMA,
            "llama3": LLMProvider.OLLAMA,
            "mixtral:8x7b": LLMProvider.OLLAMA,
            "gpt-4o-mini": LLMProvider.OPENAI,
            "claude-3-haiku": LLMProvider.ANTHROPIC,
            "deepseek-chat": LLMProvider.DEEPSEEK,
            "gemini-1.5-flash": LLMProvider.GEMINI,
            "MiniMax-M3": LLMProvider.MINIMAX,
            "mistral-large": LLMProvider.MISTRAL,
            "qwen-2.5": LLMProvider.QWEN,
            "xiaomi/mimo-v2.5-pro": LLMProvider.XIAOMI,
            "mimo-v2.5": LLMProvider.XIAOMI,
            "command-r": LLMProvider.COHERE,
            "something-new": LLMProvider.OPENAI,  # default
        }
        for model, expected in cases.items():
            assert service.get_provider(model) is expected, model

    def test_ollama_precedence_over_mistral(self):
        service = _service()
        assert service.get_provider("mistral:7b") is LLMProvider.OLLAMA


class TestResolveGovernanceModel:
    def test_no_db_returns_model(self):
        service = _service(db=None)
        assert service._resolve_governance_model("t", "gpt-4o") == "gpt-4o"

    def test_critical_bypass_flags(self):
        service = _service(db=MagicMock())
        assert service._resolve_governance_model(
            "t", "gpt-4o", is_critical_security=True) == "gpt-4o"
        assert service._resolve_governance_model(
            "t", "gpt-4o", is_system_repair=True) == "gpt-4o"

    def test_workspace_missing_returns_model(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        service = _service(db=db)
        assert service._resolve_governance_model("missing", "gpt-4o") == "gpt-4o"

    def test_workspace_no_frugal_mode_returns_model(self):
        db = MagicMock()
        ws = MagicMock()
        ws.metadata_json = None
        db.query.return_value.filter.return_value.first.return_value = ws
        service = _service(db=db)
        assert service._resolve_governance_model("t", "gpt-4o") == "gpt-4o"

    def test_frugal_mode_empty_meta_returns_model(self):
        db = MagicMock()
        ws = MagicMock()
        ws.metadata_json = {}
        db.query.return_value.filter.return_value.first.return_value = ws
        service = _service(db=db)
        assert service._resolve_governance_model("t", "gpt-4o") == "gpt-4o"

    def test_frugal_mode_deescalates_known_models(self):
        db = MagicMock()
        ws = MagicMock()
        ws.metadata_json = {"frugal_mode": True}
        db.query.return_value.filter.return_value.first.return_value = ws
        service = _service(db=db)
        assert service._resolve_governance_model("t", "gpt-4o") == "gpt-4o-mini"
        assert service._resolve_governance_model("t", "gpt-4") == "gpt-4o-mini"
        assert service._resolve_governance_model("t", "gpt-4-turbo") == "gpt-4o-mini"
        assert service._resolve_governance_model(
            "t", "claude-3-5-sonnet") == "claude-3-haiku-20240307"
        assert service._resolve_governance_model(
            "t", "claude-3-opus-20240229") == "claude-3-haiku-20240307"
        assert service._resolve_governance_model(
            "t", "claude-3-sonnet-20240229") == "claude-3-haiku-20240307"
        assert service._resolve_governance_model("t", "gemini-1.5-pro") == "gemini-1.5-flash"
        assert service._resolve_governance_model("t", "deepseek-reasoner") == "deepseek-chat"

    def test_frugal_mode_unknown_model_unchanged(self):
        db = MagicMock()
        ws = MagicMock()
        ws.metadata_json = {"frugal_mode": True}
        db.query.return_value.filter.return_value.first.return_value = ws
        service = _service(db=db)
        assert service._resolve_governance_model("t", "mystery-model") == "mystery-model"


class TestGenerate:
    async def test_generate_plain(self):
        handler = MagicMock()
        handler.generate_response = AsyncMock(return_value="answer")
        service = _service(handler=handler)
        result = await service.generate(
            "hello", model="gpt-4o-mini", turn_index=3)
        assert result == "answer"
        kwargs = handler.generate_response.await_args.kwargs
        assert kwargs["model_type"] == "gpt-4o-mini"
        assert kwargs["turn_index"] == 3

    async def test_generate_personalization_applies_temperature(self):
        handler = MagicMock()
        handler.generate_response = AsyncMock(return_value="answer")
        db = MagicMock()
        service = _service(db=db, handler=handler)
        cl = MagicMock()
        cl.get_personalized_parameters.return_value = {"temperature": 0.3}
        service.continuous_learning = cl
        await service.generate("hi", model="gpt-4o-mini", agent_id="a1", user_id="u1")
        kwargs = handler.generate_response.await_args.kwargs
        assert kwargs["temperature"] == 0.3

    async def test_generate_personalization_keeps_explicit_temperature(self):
        handler = MagicMock()
        handler.generate_response = AsyncMock(return_value="answer")
        db = MagicMock()
        service = _service(db=db, handler=handler)
        cl = MagicMock()
        cl.get_personalized_parameters.return_value = {"temperature": 0.3}
        service.continuous_learning = cl
        await service.generate(
            "hi", model="gpt-4o-mini", agent_id="a1", temperature=0.9)
        kwargs = handler.generate_response.await_args.kwargs
        assert kwargs["temperature"] == 0.9

    async def test_generate_no_continuous_learning(self):
        handler = MagicMock()
        handler.generate_response = AsyncMock(return_value="answer")
        service = _service(handler=handler)  # db=None -> continuous_learning None
        assert service.continuous_learning is None
        result = await service.generate("hi", agent_id="a1")
        assert result == "answer"


class TestGenerateCompletion:
    async def test_completion_message_mapping_with_stash(self):
        handler = MagicMock()
        handler.generate_response = AsyncMock(return_value="Hi there")
        handler._last_used_model = "deepseek-chat"
        handler._last_used_provider = "deepseek"
        service = _service(handler=handler)
        result = await service.generate_completion([
            {"role": "system", "content": "Be terse."},
            {"role": "user", "content": "Hello"},
        ])
        assert result["success"] is True
        assert result["content"] == "Hi there"
        assert result["text"] == "Hi there"
        assert result["model"] == "deepseek-chat"
        assert result["provider"] == "deepseek"
        assert result["usage"]["completion_tokens"] > 0
        kwargs = handler.generate_response.await_args.kwargs
        assert kwargs["system_instruction"] == "Be terse."
        assert kwargs["prompt"] == "Hello"

    async def test_completion_provider_fallback_via_get_provider(self):
        """No _last_used_provider stash -> provider derived via get_provider."""
        handler = SimpleNamespace(
            generate_response=AsyncMock(return_value="ok"),
            _last_used_model="deepseek-chat",
        )
        service = _service(handler=handler)
        result = await service.generate_completion([
            {"role": "user", "content": "hi"},
        ])
        assert result["provider"] == "deepseek"

    async def test_completion_empty_messages(self):
        handler = MagicMock()
        handler.generate_response = AsyncMock(return_value="x")
        service = _service(handler=handler)
        result = await service.generate_completion([])
        assert result["success"] is True
        kwargs = handler.generate_response.await_args.kwargs
        assert kwargs["prompt"] == ""
        assert kwargs["system_instruction"] == "You are a helpful assistant."


class TestGenerateStructuredResponse:
    async def test_plain(self):
        handler = MagicMock()
        handler.generate_structured_response = AsyncMock(
            return_value={"name": "x"})
        service = _service(handler=handler)
        result = await service.generate_structured_response(
            "prompt", response_model=dict, model="versatile")
        assert result == {"name": "x"}
        kwargs = handler.generate_structured_response.await_args.kwargs
        assert kwargs["task_type"] == "versatile"

    async def test_with_personalization(self):
        handler = MagicMock()
        handler.generate_structured_response = AsyncMock(
            return_value={"ok": True})
        service = _service(handler=handler)
        cl = MagicMock()
        cl.get_personalized_parameters.return_value = {"temperature": 0.7}
        service.continuous_learning = cl
        result = await service.generate_structured_response(
            "prompt", response_model=dict, agent_id="a-1")
        assert result == {"ok": True}
        kwargs = handler.generate_structured_response.await_args.kwargs
        assert kwargs["temperature"] == 0.7

    async def test_personalization_keeps_explicit_temperature(self):
        handler = MagicMock()
        handler.generate_structured_response = AsyncMock(return_value={})
        service = _service(handler=handler)
        cl = MagicMock()
        cl.get_personalized_parameters.return_value = {"temperature": 0.7}
        service.continuous_learning = cl
        await service.generate_structured_response(
            "prompt", response_model=dict, agent_id="a-1", temperature=0.5)
        kwargs = handler.generate_structured_response.await_args.kwargs
        assert kwargs["temperature"] == 0.5

    async def test_named_temperature_forwarded_without_personalization(self):
        handler = MagicMock()
        handler.generate_structured_response = AsyncMock(return_value={})
        service = _service(handler=handler)
        await service.generate_structured_response(
            "prompt", response_model=dict, temperature=0.4)
        kwargs = handler.generate_structured_response.await_args.kwargs
        assert kwargs["temperature"] == 0.4


class TestStreamCompletionActive:
    """Regression lock: the ACTIVE (final) stream_completion definition accepts
    provider_id/db and delegates to handler.stream_completion (the shadowed
    first definition was removed as dead code — it took a different signature
    and was unreachable)."""

    async def test_auto_provider_auto_model(self):
        handler = MagicMock()
        handler.analyze_query_complexity = MagicMock(return_value="complex")
        handler.get_optimal_provider = AsyncMock(
            return_value=("openai", "gpt-4o-mini"))
        service = _service(handler=handler)
        _stream_tokens(handler, ["tok1", "tok2"])
        tokens = []
        async for t in service.stream_completion(
                [{"role": "user", "content": "analyze"}], model="auto"):
            tokens.append(t)
        assert tokens == ["tok1", "tok2"]
        kwargs = handler.stream_completion.call_args.kwargs
        assert kwargs["provider_id"] == "openai"
        assert kwargs["model"] == "gpt-4o-mini"
        assert kwargs["db"] is None

    async def test_explicit_provider_and_model(self):
        handler = MagicMock()
        service = _service(handler=handler)
        _stream_tokens(handler, ["a", "b", "c"])
        tokens = []
        async for t in service.stream_completion(
                [{"role": "user", "content": "hi"}],
                model="gpt-4o-mini", provider_id="deepseek", db="db-handle"):
            tokens.append(t)
        assert tokens == ["a", "b", "c"]
        handler.analyze_query_complexity.assert_not_called()
        kwargs = handler.stream_completion.call_args.kwargs
        assert kwargs["provider_id"] == "deepseek"
        assert kwargs["model"] == "gpt-4o-mini"
        assert kwargs["db"] == "db-handle"


class TestSpeechAudio:
    async def test_generate_speech_success(self):
        handler = MagicMock()
        client = MagicMock()
        resp = MagicMock()
        resp.read.return_value = b"audio-bytes"
        client.audio.speech.create = AsyncMock(return_value=resp)
        handler.async_clients = {"openai": client}
        handler.clients = {}
        service = _service(handler=handler)
        with patch.object(service, "get_provider",
                          return_value=SimpleNamespace(value="openai")):
            result = await service.generate_speech("hello", "alloy")
        assert result == b"audio-bytes"

    async def test_generate_speech_no_client_raises(self):
        handler = MagicMock()
        handler.async_clients = {}
        handler.clients = {}
        service = _service(handler=handler)
        with patch.object(service, "get_provider",
                          return_value=SimpleNamespace(value="openai")):
            with pytest.raises(ValueError, match="No client found"):
                await service.generate_speech("hello")

    async def test_generate_speech_sync_client_fallback(self):
        handler = MagicMock()
        sync_client = MagicMock()
        resp = MagicMock()
        resp.read.return_value = b"audio"
        sync_client.audio.speech.create = AsyncMock(return_value=resp)
        handler.async_clients = {}
        handler.clients = {"openai": sync_client}
        service = _service(handler=handler)
        with patch.object(service, "get_provider",
                          return_value=SimpleNamespace(value="openai")):
            result = await service.generate_speech("hello")
        assert result == b"audio"


class TestTokenAndCost:
    def test_estimate_tokens_str(self):
        service = _service()
        service._token_counter = MagicMock()
        service._token_counter.count_tokens.return_value = 42
        assert service.estimate_tokens("hello") == 42

    def test_estimate_tokens_list(self):
        service = _service()
        service._context_validator = MagicMock()
        service._context_validator.estimate_request_tokens.return_value = 99
        assert service.estimate_tokens([{"role": "user", "content": "hi"}]) == 99

    def test_estimate_tokens_unsupported_type(self):
        service = _service()
        assert service.estimate_tokens(12345) == 0

    def test_estimate_cost_real_config(self):
        service = _service()
        with patch("core.cost_config.get_llm_cost", return_value=0.005):
            assert service.estimate_cost(100, 200, "gpt-4o") == 0.005

    def test_estimate_cost_fallback_gpt4o_mini(self):
        service = _service()
        with patch.dict(sys.modules, {"core.cost_config": None}):
            assert service.estimate_cost(1000, 1000, "gpt-4o-mini") == pytest.approx(
                (1000 * 0.15 + 1000 * 0.6) / 1e6)

    def test_estimate_cost_fallback_gpt4o(self):
        service = _service()
        with patch.dict(sys.modules, {"core.cost_config": None}):
            assert service.estimate_cost(100, 200, "gpt-4o") == pytest.approx(
                (100 * 5.0 + 200 * 15.0) / 1e6)

    def test_estimate_cost_fallback_deepseek(self):
        service = _service()
        with patch.dict(sys.modules, {"core.cost_config": None}):
            assert service.estimate_cost(1000, 1000, "deepseek-chat") == pytest.approx(
                (1000 * 0.14 + 1000 * 0.28) / 1e6)

    def test_estimate_cost_fallback_default(self):
        service = _service()
        with patch.dict(sys.modules, {"core.cost_config": None}):
            assert service.estimate_cost(1000, 1000, "unknown-model") == pytest.approx(
                (1000 * 1.0 + 1000 * 2.0) / 1e6)


class TestGenerateWithTier:
    async def test_delegates(self):
        handler = MagicMock()
        handler.generate_with_cognitive_tier = AsyncMock(
            return_value={"response": "r", "tier": "standard"})
        service = _service(handler=handler)
        result = await service.generate_with_tier(
            "prompt", task_type="chat", user_tier_override="standard",
            agent_id="a1", image_payload="data:image/png;base64,x")
        assert result["tier"] == "standard"
        kwargs = handler.generate_with_cognitive_tier.await_args.kwargs
        assert kwargs["task_type"] == "chat"
        assert kwargs["image_payload"].startswith("data:")


class TestAnalyzeProposal:
    async def test_json_response(self):
        service = _service()
        with patch.object(service, "generate",
                          AsyncMock(return_value='{"safe": true, "risk_level": "low"}')):
            result = await service.analyze_proposal("do x", context="ctx")
        assert result["safe"] is True
        assert result["risk_level"] == "low"

    async def test_fenced_json_block(self):
        service = _service()
        with patch.object(service, "generate", AsyncMock(
                return_value='```json\n{"safe": false, "risk_level": "high"}\n```')):
            result = await service.analyze_proposal("do x")
        assert result["safe"] is False

    async def test_parse_failure_fallback(self):
        service = _service()
        with patch.object(service, "generate",
                          AsyncMock(return_value="not json at all")):
            result = await service.analyze_proposal("do x")
        assert result["error"] == "Failed to parse structured audit"
        assert result["raw_response"] == "not json at all"
        assert result["safe"] is False  # "safe" not in raw response

    async def test_parse_failure_safe_keyword_detected(self):
        service = _service()
        with patch.object(service, "generate",
                          AsyncMock(return_value="This is safe to run")):
            result = await service.analyze_proposal("do x")
        assert result["safe"] is True

    async def test_proposal_without_context(self):
        service = _service()
        with patch.object(service, "generate", AsyncMock(return_value="{}")):
            result = await service.analyze_proposal("do x")
        assert result == {}


class TestAvailability:
    def test_is_available_true(self):
        handler = MagicMock()
        handler.clients = {"openai": object()}
        service = _service(handler=handler)
        assert service.is_available() is True

    def test_is_available_false(self):
        handler = MagicMock()
        handler.clients = {}
        service = _service(handler=handler)
        assert service.is_available() is False

    def test_get_available_providers(self):
        handler = MagicMock()
        handler.get_available_providers.return_value = ["openai", "deepseek"]
        service = _service(handler=handler)
        assert service.get_available_providers() == ["openai", "deepseek"]

    def test_get_context_window(self):
        handler = MagicMock()
        handler.get_context_window.return_value = 128000
        service = _service(handler=handler)
        assert service.get_context_window("gpt-4o") == 128000

    def test_truncate_to_context(self):
        handler = MagicMock()
        handler.truncate_to_context.return_value = "truncated..."
        service = _service(handler=handler)
        assert service.truncate_to_context("long text", "gpt-4o", 500) == "truncated..."

    def test_get_routing_info(self):
        handler = MagicMock()
        handler.get_routing_info.return_value = {"complexity": "moderate"}
        service = _service(handler=handler)
        assert service.get_routing_info("prompt", "chat")["complexity"] == "moderate"

    def test_classify_tier(self):
        handler = MagicMock()
        handler.classify_cognitive_tier.return_value = CognitiveTier.STANDARD
        service = _service(handler=handler)
        assert service.classify_tier("hi") is CognitiveTier.STANDARD
        handler.classify_cognitive_tier.assert_called_once_with("hi", None)

    def test_analyze_query_complexity(self):
        handler = MagicMock()
        handler.analyze_query_complexity.return_value = QueryComplexity.COMPLEX
        service = _service(handler=handler)
        assert service.analyze_query_complexity("big task", "code") is QueryComplexity.COMPLEX


class TestOptimalProvider:
    async def test_get_optimal_provider_awaitable(self):
        handler = MagicMock()
        handler.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")
        service = _service(handler=handler)
        result = service.get_optimal_provider("complex", task_type="chat")
        assert result == ("openai", "gpt-4o-mini")  # AwaitableResult __eq__
        assert await result == ("openai", "gpt-4o-mini")
        kwargs = handler.get_optimal_provider.call_args.kwargs
        assert kwargs["complexity"] is QueryComplexity.COMPLEX

    def test_get_optimal_provider_default_complexity(self):
        handler = MagicMock()
        handler.get_optimal_provider.return_value = ("deepseek", "deepseek-chat")
        service = _service(handler=handler)
        result = service.get_optimal_provider("weird-level")
        assert result == ("deepseek", "deepseek-chat")
        kwargs = handler.get_optimal_provider.call_args.kwargs
        assert kwargs["complexity"] is QueryComplexity.MODERATE

    def test_get_optimal_provider_all_levels(self):
        handler = MagicMock()
        service = _service(handler=handler)
        for level, enum in [
            ("simple", QueryComplexity.SIMPLE),
            ("moderate", QueryComplexity.MODERATE),
            ("complex", QueryComplexity.COMPLEX),
            ("advanced", QueryComplexity.ADVANCED),
        ]:
            service.get_optimal_provider(level)
            assert handler.get_optimal_provider.call_args.kwargs["complexity"] is enum

    def test_get_ranked_providers_with_cognitive_tier(self):
        handler = MagicMock()
        handler.get_ranked_providers.return_value = [("openai", "gpt-4o")]
        service = _service(handler=handler)
        result = service.get_ranked_providers("complex", cognitive_tier="heavy")
        assert result == [("openai", "gpt-4o")]
        kwargs = handler.get_ranked_providers.call_args.kwargs
        assert kwargs["cognitive_tier"] is CognitiveTier.HEAVY
        assert kwargs["workspace_id"] == "ws-1"

    def test_get_ranked_providers_invalid_tier_string(self):
        handler = MagicMock()
        handler.get_ranked_providers.return_value = []
        service = _service(handler=handler)
        service.get_ranked_providers("simple", cognitive_tier="bogus")
        assert handler.get_ranked_providers.call_args.kwargs["cognitive_tier"] is None

    def test_get_ranked_providers_no_tier(self):
        handler = MagicMock()
        handler.get_ranked_providers.return_value = []
        service = _service(handler=handler)
        service.get_ranked_providers("moderate")
        kwargs = handler.get_ranked_providers.call_args.kwargs
        assert kwargs["cognitive_tier"] is None


class TestGenerateStructured:
    async def test_unavailable_returns_none(self):
        service = _service()
        with patch.object(service, "is_available", return_value=False):
            assert await service.generate_structured("p", response_model=dict) is None

    async def test_success(self):
        handler = MagicMock()
        handler.generate_structured_response = AsyncMock(
            return_value={"name": "x", "value": 1})
        service = _service(handler=handler)
        with patch.object(service, "is_available", return_value=True), \
             patch("core.hallucination_config.is_cascade_routing_enabled",
                   return_value=True):
            result = await service.generate_structured(
                "prompt", response_model=dict, stage_decision_id="sd-1")
        assert result == {"name": "x", "value": 1}
        kwargs = handler.generate_structured_response.await_args.kwargs
        assert kwargs["cascade"] is True
        assert kwargs["stage_decision_id"] == "sd-1"

    async def test_exception_returns_none(self):
        handler = MagicMock()
        handler.generate_structured_response = AsyncMock(
            side_effect=RuntimeError("gen failed"))
        service = _service(handler=handler)
        with patch.object(service, "is_available", return_value=True), \
             patch("core.hallucination_config.is_cascade_routing_enabled",
                   return_value=False):
            assert await service.generate_structured(
                "prompt", response_model=dict) is None

    async def test_self_consistency_branch(self):
        handler = MagicMock()
        service = _service(handler=handler)
        vote = _vote()
        with patch.object(service, "is_available", return_value=True), \
             patch("core.hallucination_config.is_cascade_routing_enabled",
                   return_value=False), \
             patch("core.hallucination_config.is_self_consistency_enabled",
                   return_value=True), \
             patch("core.llm.self_consistency_voter.SelfConsistencyVoter") as cls, \
             patch.object(service, "_write_self_consistency_audit"):
            mock_voter = MagicMock()
            mock_voter.vote_with_consensus = AsyncMock(return_value=vote)
            cls.return_value = mock_voter
            winner = await service.generate_structured(
                "prompt", response_model=dict, enable_self_consistency=True)
        assert winner is vote.winner


class TestStructuredWithConsensus:
    async def test_unavailable_returns_none_none(self):
        service = _service()
        with patch.object(service, "is_available", return_value=False):
            winner, vote = await service.generate_structured_with_consensus(
                "prompt", response_model=dict)
        assert winner is None and vote is None

    async def test_flag_off_success(self):
        handler = MagicMock()
        handler.generate_structured_response = AsyncMock(return_value={"ok": 1})
        service = _service(handler=handler)
        with patch.object(service, "is_available", return_value=True), \
             patch("core.hallucination_config.is_self_consistency_enabled",
                   return_value=False), \
             patch("core.hallucination_config.is_cascade_routing_enabled",
                   return_value=False):
            winner, vote = await service.generate_structured_with_consensus(
                "prompt", response_model=dict)
        assert winner == {"ok": 1} and vote is None

    async def test_flag_off_error(self):
        handler = MagicMock()
        handler.generate_structured_response = AsyncMock(
            side_effect=RuntimeError("boom"))
        service = _service(handler=handler)
        with patch.object(service, "is_available", return_value=True), \
             patch("core.hallucination_config.is_self_consistency_enabled",
                   return_value=False):
            winner, vote = await service.generate_structured_with_consensus(
                "prompt", response_model=dict)
        assert winner is None and vote is None

    async def test_flag_on_vote_success(self):
        handler = MagicMock()
        service = _service(handler=handler)
        vote = _vote()
        with patch.object(service, "is_available", return_value=True), \
             patch("core.hallucination_config.is_self_consistency_enabled",
                   return_value=True), \
             patch("core.hallucination_config.is_cascade_routing_enabled",
                   return_value=False), \
             patch("core.llm.self_consistency_voter.SelfConsistencyVoter") as cls, \
             patch.object(service, "_write_self_consistency_audit") as audit:
            mock_voter = MagicMock()
            mock_voter.vote_with_consensus = AsyncMock(return_value=vote)
            cls.return_value = mock_voter
            winner, result = await service.generate_structured_with_consensus(
                "prompt", response_model=dict)
        assert winner is vote.winner
        assert result is vote
        audit.assert_called_once()

    async def test_vote_failure_degrades(self):
        service = _service()
        with patch.object(service, "is_available", return_value=True), \
             patch("core.hallucination_config.is_self_consistency_enabled",
                   return_value=True), \
             patch("core.llm.self_consistency_voter.SelfConsistencyVoter",
                   side_effect=RuntimeError("voter down")):
            winner, vote = await service.generate_structured_with_consensus(
                "prompt", response_model=dict)
        assert winner is None and vote is None

    async def test_audit_failure_still_returns_winner(self):
        handler = MagicMock()
        service = _service(handler=handler)
        vote = _vote()
        with patch.object(service, "is_available", return_value=True), \
             patch("core.hallucination_config.is_self_consistency_enabled",
                   return_value=True), \
             patch("core.llm.self_consistency_voter.SelfConsistencyVoter") as cls, \
             patch.object(service, "_write_self_consistency_audit",
                          side_effect=RuntimeError("audit boom")):
            mock_voter = MagicMock()
            mock_voter.vote_with_consensus = AsyncMock(return_value=vote)
            cls.return_value = mock_voter
            winner, result = await service.generate_structured_with_consensus(
                "prompt", response_model=dict)
        assert winner is vote.winner
        assert result is vote


class TestRunSelfConsistencyVote:
    async def test_success_path(self):
        handler = MagicMock()
        service = _service(handler=handler)
        vote = _vote()
        with patch("core.llm.self_consistency_voter.SelfConsistencyVoter") as cls, \
             patch.object(service, "_write_self_consistency_audit") as audit:
            mock_voter = MagicMock()
            mock_voter.vote_with_consensus = AsyncMock(return_value=vote)
            cls.return_value = mock_voter
            winner, result = await service._run_self_consistency_vote(
                "prompt", dict, "sys", 0.2, "chat", "a1", None,
                cascade=False, session_id="s1", user_id="u1")
        assert winner is vote.winner
        assert result is vote
        audit.assert_called_once()
        kwargs = mock_voter.vote_with_consensus.await_args.kwargs
        assert kwargs["cascade"] is False
        assert kwargs["agent_id"] == "a1"

    async def test_voter_exception_degrades(self):
        service = _service()
        with patch("core.llm.self_consistency_voter.SelfConsistencyVoter",
                   side_effect=RuntimeError("voter down")):
            winner, result = await service._run_self_consistency_vote(
                "p", dict, "s", 0.2, None, None, None,
                cascade=False, session_id=None, user_id=None)
        assert winner is None and result is None

    async def test_audit_exception_still_returns_winner(self):
        handler = MagicMock()
        service = _service(handler=handler)
        vote = _vote()
        with patch("core.llm.self_consistency_voter.SelfConsistencyVoter") as cls, \
             patch.object(service, "_write_self_consistency_audit",
                          side_effect=RuntimeError("audit boom")):
            mock_voter = MagicMock()
            mock_voter.vote_with_consensus = AsyncMock(return_value=vote)
            cls.return_value = mock_voter
            winner, result = await service._run_self_consistency_vote(
                "p", dict, "s", 0.2, None, None, None,
                cascade=True, session_id=None, user_id=None)
        assert winner is vote.winner
        assert result is vote


class TestAuditWrite:
    def test_audit_with_caller_db(self):
        db = MagicMock()
        service = _service(db=db)
        service._tenant_id = "t-1"
        service._workspace_id = "ws-1"
        vote = _vote()
        with patch("core.models.SelfConsistencyVote",
                   return_value=MagicMock()):
            service._write_self_consistency_audit(
                vote=vote, agent_id="a1", session_id="s1",
                user_id="u1", response_model=dict)
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_audit_caller_db_commit_error_rolls_back(self):
        db = MagicMock()
        db.commit.side_effect = RuntimeError("commit failed")
        service = _service(db=db)
        vote = _vote()
        with patch("core.models.SelfConsistencyVote",
                   return_value=MagicMock()):
            service._write_self_consistency_audit(
                vote=vote, agent_id=None, session_id=None,
                user_id=None, response_model=dict)
        db.rollback.assert_called_once()

    def test_audit_caller_db_commit_and_rollback_fail(self):
        db = MagicMock()
        db.commit.side_effect = RuntimeError("commit failed")
        db.rollback.side_effect = RuntimeError("rollback failed")
        service = _service(db=db)
        vote = _vote()
        with patch("core.models.SelfConsistencyVote",
                   return_value=MagicMock()):
            service._write_self_consistency_audit(
                vote=vote, agent_id=None, session_id=None,
                user_id=None, response_model=dict)
        db.rollback.assert_called_once()

    def test_audit_own_session(self):
        service = _service(db=None)
        vote = _vote()
        session = MagicMock()
        with patch("core.models.SelfConsistencyVote",
                   return_value=MagicMock()), \
             patch("core.database.get_db_session") as get_session:
            get_session.return_value.__enter__.return_value = session
            service._write_self_consistency_audit(
                vote=vote, agent_id="a1", session_id="s1",
                user_id="u1", response_model=dict)
        session.add.assert_called_once()
        session.commit.assert_called_once()

    def test_audit_own_session_error_swallowed(self):
        service = _service(db=None)
        vote = _vote()
        with patch("core.models.SelfConsistencyVote",
                   return_value=MagicMock()), \
             patch("core.database.get_db_session",
                   side_effect=RuntimeError("no session")):
            service._write_self_consistency_audit(
                vote=vote, agent_id=None, session_id=None,
                user_id=None, response_model=dict)

    def test_audit_model_import_failure(self):
        import types
        fake_models = types.ModuleType("core.models")
        service = _service(db=None)
        with patch.dict(sys.modules, {"core.models": fake_models}):
            service._write_self_consistency_audit(
                vote=_vote(), agent_id=None, session_id=None,
                user_id=None, response_model=dict)

    def test_audit_default_tenant_workspace_null(self):
        """'default' tenant/workspace are stored as NULL."""
        db = MagicMock()
        service = _service(db=db, workspace_id="default", tenant_id="default")
        vote = _vote()
        with patch("core.models.SelfConsistencyVote",
                   return_value=MagicMock()) as cls:
            service._write_self_consistency_audit(
                vote=vote, agent_id=None, session_id=None,
                user_id=None, response_model=dict)
        assert cls.call_args.kwargs["workspace_id"] is None
        assert cls.call_args.kwargs["tenant_id"] is None

    def test_audit_error_message_when_no_valid_samples(self):
        db = MagicMock()
        service = _service(db=db)
        vote = _vote(valid_count=0)
        with patch("core.models.SelfConsistencyVote",
                   return_value=MagicMock()) as cls:
            service._write_self_consistency_audit(
                vote=vote, agent_id=None, session_id=None,
                user_id=None, response_model=dict)
        assert cls.call_args.kwargs["error_message"] == "all samples returned None"


class TestEmbeddingActive:
    def _patch_tracker(self, record=None):
        tracker = MagicMock()
        if record is not None:
            tracker.record = record
        return patch("core.llm_service.llm_usage_tracker", tracker)

    async def test_openai_success(self):
        handler = MagicMock()
        handler.generate_embedding = AsyncMock(return_value=[0.1, 0.2])
        service = _service(handler=handler)
        with self._patch_tracker() as tracker:
            result = await service.generate_embedding("text")
        assert result == [0.1, 0.2]
        kwargs = tracker.record.call_args.kwargs
        assert kwargs["provider"] == "openai"
        assert kwargs["model"] == "text-embedding-3-small"

    async def test_openai_large_model_cost(self):
        handler = MagicMock()
        handler.generate_embedding = AsyncMock(return_value=[0.1])
        service = _service(handler=handler)
        with self._patch_tracker() as tracker:
            await service.generate_embedding("text", model="text-embedding-3-large")
        assert tracker.record.call_args.kwargs["cost_usd"] > 0

    async def test_cohere_branch(self):
        handler = MagicMock()
        handler.generate_embedding = AsyncMock(return_value=[0.3, 0.4])
        service = _service(handler=handler)
        with self._patch_tracker() as tracker:
            result = await service.generate_embedding(
                "text", model="embed-english-v3.0")
        assert result == [0.3, 0.4]
        kwargs = tracker.record.call_args.kwargs
        assert kwargs["provider"] == "cohere"
        handler.generate_embedding.assert_awaited_once_with(
            text="text", model="embed-english-v3.0", provider="cohere")

    async def test_tracking_failure_swallowed(self):
        handler = MagicMock()
        handler.generate_embedding = AsyncMock(return_value=[0.1])
        service = _service(handler=handler)
        tracker = MagicMock()
        tracker.record.side_effect = RuntimeError("tracker down")
        with patch("core.llm_service.llm_usage_tracker", tracker):
            result = await service.generate_embedding("text")
        assert result == [0.1]

    async def test_handler_failure_reraises(self):
        handler = MagicMock()
        handler.generate_embedding = AsyncMock(
            side_effect=RuntimeError("embed failed"))
        service = _service(handler=handler)
        with self._patch_tracker():
            with pytest.raises(RuntimeError, match="embed failed"):
                await service.generate_embedding("text")

    async def test_batch_openai_success(self):
        handler = MagicMock()
        handler.generate_embeddings_batch = AsyncMock(
            return_value=[[0.1], [0.2]])
        service = _service(handler=handler)
        with self._patch_tracker() as tracker:
            result = await service.generate_embeddings_batch(["a", "b"])
        assert result == [[0.1], [0.2]]
        assert tracker.record.call_args.kwargs["provider"] == "openai"

    async def test_batch_cohere_branch(self):
        handler = MagicMock()
        handler.generate_embeddings_batch = AsyncMock(
            return_value=[[0.5], [0.6]])
        service = _service(handler=handler)
        with self._patch_tracker() as tracker:
            result = await service.generate_embeddings_batch(
                ["a", "b"], model="embed-multilingual-v3.0")
        assert result == [[0.5], [0.6]]
        kwargs = tracker.record.call_args.kwargs
        assert kwargs["provider"] == "cohere"
        handler.generate_embeddings_batch.assert_awaited_once_with(
            texts=["a", "b"], model="embed-multilingual-v3.0", provider="cohere")

    async def test_batch_tracking_failure_swallowed(self):
        handler = MagicMock()
        handler.generate_embeddings_batch = AsyncMock(return_value=[[0.1]])
        service = _service(handler=handler)
        tracker = MagicMock()
        tracker.record.side_effect = RuntimeError("tracker down")
        with patch("core.llm_service.llm_usage_tracker", tracker):
            result = await service.generate_embeddings_batch(["a"])
        assert result == [[0.1]]

    async def test_batch_handler_failure_reraises(self):
        handler = MagicMock()
        handler.generate_embeddings_batch = AsyncMock(
            side_effect=RuntimeError("batch failed"))
        service = _service(handler=handler)
        with self._patch_tracker():
            with pytest.raises(RuntimeError, match="batch failed"):
                await service.generate_embeddings_batch(["a"])


class TestTranscribeActive:
    """Regression lock: the ACTIVE transcribe_audio accepts language/prompt/
    response_format and delegates to handler.generate_transcription."""

    async def test_delegates(self):
        handler = MagicMock()
        handler.generate_transcription = AsyncMock(
            return_value={"text": "hello world"})
        service = _service(handler=handler)
        result = await service.transcribe_audio(
            file="f", language="en", prompt="guide",
            response_format="verbose_json")
        assert result == {"text": "hello world"}
        handler.generate_transcription.assert_awaited_once_with(
            file="f", model="whisper-1", language="en", prompt="guide",
            response_format="verbose_json")


class TestTierDescriptions:
    def test_string_tier(self):
        service = _service()
        desc = service.get_tier_description("versatile")
        assert desc["name"] == "VERSATILE"
        assert "cost_range" in desc

    def test_invalid_string_falls_back_to_standard(self):
        service = _service()
        desc = service.get_tier_description("bogus")
        assert desc["name"] == "STANDARD"

    def test_enum_tier(self):
        service = _service()
        assert service.get_tier_description(CognitiveTier.MICRO)["name"] == "MICRO"
        assert service.get_tier_description(CognitiveTier.COMPLEX)["name"] == "COMPLEX"
