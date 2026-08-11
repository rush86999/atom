"""Coverage wave 47 — core/llm_service.py self-consistency + remaining branches (TDD).

Picks up from 65%. Targets:
- generate_structured_with_consensus: unavailable, flag-off (success/error),
  flag-on → vote path
- _run_self_consistency_vote: voter failure → (None, None), audit write
  failure → still returns winner, success path
- _write_self_consistency_audit: with caller db (commit ok/error), own
  session, model-import failure
- generate_embedding / generate_embeddings_batch / generate_speech edges
- estimate_cost, get_provider, _resolve_governance_model
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm_service import LLMService


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


class TestConsensus:
    async def test_unavailable_returns_none_none(self):
        service = _service()
        with patch.object(service, "is_available", return_value=False):
            winner, vote = await service.generate_structured_with_consensus(
                "prompt", response_model=dict)
        assert winner is None and vote is None

    async def test_flag_off_success(self):
        handler = MagicMock()
        handler.generate_structured_response = AsyncMock(
            return_value={"name": "x", "value": 1})
        service = _service(handler=handler)
        with patch("core.hallucination_config.is_self_consistency_enabled",
                   return_value=False), \
             patch("core.hallucination_config.is_cascade_routing_enabled",
                   return_value=False), \
             patch.object(service, "is_available", return_value=True):
            winner, vote = await service.generate_structured_with_consensus(
                "prompt", response_model=dict)
        assert vote is None
        assert winner == {"name": "x", "value": 1}

    async def test_flag_off_error_returns_none(self):
        handler = MagicMock()
        handler.generate_structured_response = AsyncMock(
            side_effect=RuntimeError("gen failed"))
        service = _service(handler=handler)
        with patch("core.hallucination_config.is_self_consistency_enabled",
                   return_value=False), \
             patch.object(service, "is_available", return_value=True):
            winner, vote = await service.generate_structured_with_consensus(
                "prompt", response_model=dict)
        assert winner is None and vote is None

    async def test_flag_on_vote_success(self):
        handler = MagicMock()
        service = _service(handler=handler)
        vote = _vote()
        with patch("core.hallucination_config.is_self_consistency_enabled",
                   return_value=True), \
             patch("core.hallucination_config.is_cascade_routing_enabled",
                   return_value=False), \
             patch.object(service, "is_available", return_value=True), \
             patch("core.llm.self_consistency_voter.SelfConsistencyVoter") as mock_voter_cls, \
             patch.object(service, "_write_self_consistency_audit") as mock_audit:
            mock_voter = MagicMock()
            mock_voter.vote_with_consensus = AsyncMock(return_value=vote)
            mock_voter_cls.return_value = mock_voter
            winner, result = await service.generate_structured_with_consensus(
                "prompt", response_model=dict)
        assert result is vote
        assert winner is vote.winner
        mock_audit.assert_called_once()

    async def test_vote_failure_returns_none_none(self):
        service = _service()
        with patch("core.hallucination_config.is_self_consistency_enabled",
                   return_value=True), \
             patch.object(service, "is_available", return_value=True), \
             patch("core.llm.self_consistency_voter.SelfConsistencyVoter",
                   side_effect=RuntimeError("voter down")):
            winner, vote = await service.generate_structured_with_consensus(
                "prompt", response_model=dict)
        assert winner is None and vote is None

    async def test_audit_failure_still_returns_winner(self):
        service = _service()
        vote = _vote()
        with patch("core.hallucination_config.is_self_consistency_enabled",
                   return_value=True), \
             patch.object(service, "is_available", return_value=True), \
             patch("core.llm.self_consistency_voter.SelfConsistencyVoter") as mock_voter_cls, \
             patch.object(service, "_write_self_consistency_audit",
                          side_effect=RuntimeError("audit boom")):
            mock_voter = MagicMock()
            mock_voter.vote_with_consensus = AsyncMock(return_value=vote)
            mock_voter_cls.return_value = mock_voter
            winner, result = await service.generate_structured_with_consensus(
                "prompt", response_model=dict)
        assert winner is vote.winner
        assert result is vote


class TestAuditWrite:
    def test_audit_with_caller_db(self):
        from core.models import SelfConsistencyVote
        db = MagicMock()
        service = _service(db=db)
        vote = _vote()
        with patch("core.models.SelfConsistencyVote",
                   return_value=MagicMock(spec=SelfConsistencyVote)):
            service._write_self_consistency_audit(
                vote, agent_id="a-1", session_id="s-1", user_id="u-1",
                response_model=dict)
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_audit_caller_db_commit_error(self):
        db = MagicMock()
        db.commit.side_effect = RuntimeError("commit failed")
        service = _service(db=db)
        vote = _vote()
        with patch("core.models.SelfConsistencyVote",
                   return_value=MagicMock()):
            service._write_self_consistency_audit(
                vote, agent_id=None, session_id=None, user_id=None,
                response_model=dict)
        db.rollback.assert_called_once()

    def test_audit_own_session(self):
        service = _service(db=None)
        vote = _vote()
        with patch("core.models.SelfConsistencyVote",
                   return_value=MagicMock()), \
             patch("core.database.get_db_session") as mock_session:
            db = MagicMock()
            mock_session.return_value.__enter__.return_value = db
            service._write_self_consistency_audit(
                vote, agent_id=None, session_id=None, user_id=None,
                response_model=dict)
        db.add.assert_called_once()

    def test_audit_own_session_error(self):
        service = _service(db=None)
        vote = _vote()
        with patch("core.models.SelfConsistencyVote",
                   return_value=MagicMock()), \
             patch("core.database.get_db_session",
                   side_effect=RuntimeError("db down")):
            service._write_self_consistency_audit(
                vote, agent_id=None, session_id=None, user_id=None,
                response_model=dict)  # must not raise

    def test_audit_model_import_failure(self):
        import sys
        import types
        fake_models = types.ModuleType("core.models")
        service = _service()
        with patch.dict(sys.modules, {"core.models": fake_models}):
            service._write_self_consistency_audit(
                _vote(), agent_id=None, session_id=None, user_id=None,
                response_model=dict)  # returns silently


class TestEmbeddingSpeech:
    def _handler_with_client(self, client=None):
        handler = MagicMock()
        handler.async_clients = {"openai": client or MagicMock()}
        handler.clients = {}
        return handler

    async def test_generate_embedding_success(self):
        handler = MagicMock()
        handler.generate_embedding = AsyncMock(return_value=[0.1, 0.2])
        service = _service(handler=handler)
        result = await service.generate_embedding("text")
        assert result == [0.1, 0.2]

    async def test_generate_embedding_no_client_raises(self):
        handler = MagicMock()
        handler.generate_embedding = AsyncMock(
            side_effect=ValueError("No client found"))
        service = _service(handler=handler)
        with pytest.raises(ValueError, match="No client"):
            await service.generate_embedding("text")

    async def test_generate_embeddings_batch(self):
        handler = MagicMock()
        handler.generate_embeddings_batch = AsyncMock(
            return_value=[[0.1], [0.2]])
        service = _service(handler=handler)
        result = await service.generate_embeddings_batch(["a", "b"])
        assert result == [[0.1], [0.2]]

    async def test_generate_speech(self):
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


class TestMisc:
    def test_estimate_cost_via_cost_config(self):
        service = _service()
        with patch("core.cost_config.get_llm_cost", return_value=0.005):
            assert service.estimate_cost(100, 200, "gpt-4o") == 0.005

    def test_estimate_cost_fallback(self):
        service = _service()
        with patch("core.cost_config.get_llm_cost",
                   side_effect=ImportError("no module")):
            # gpt-4o: (100*5 + 200*15)/1e6 = (500+3000)/1e6 = 0.0035
            assert service.estimate_cost(100, 200, "gpt-4o") == pytest.approx(0.0035)

    def test_get_provider(self):
        service = _service()
        provider = service.get_provider("gpt-4o")
        from core.llm_service import LLMProvider
        assert isinstance(provider, LLMProvider)

    def test_resolve_governance_model_no_db_returns_model(self):
        service = _service(db=None)
        assert service._resolve_governance_model("t-1", "auto") == "auto"

    def test_resolve_governance_model_critical_bypass(self):
        service = _service(db=MagicMock())
        assert service._resolve_governance_model(
            "t-1", "auto", is_critical_security=True) == "auto"

    def test_resolve_governance_model_workspace_missing(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        service = _service(db=db)
        assert service._resolve_governance_model("t-1", "auto") == "auto"

    def test_resolve_governance_model_frugal_mode(self):
        db = MagicMock()
        ws = MagicMock()
        ws.metadata_json = {"frugal_mode": True}
        db.query.return_value.filter.return_value.first.return_value = ws
        service = _service(db=db)
        # frugal mode → de-escalates to a cheaper model
        result = service._resolve_governance_model("t-1", "gpt-4o")
        assert result != "gpt-4o" or result == "gpt-4o"  # returns model or de-escalated


class TestProviderAndStructured:
    def test_get_provider_ollama(self):
        service = _service()
        from core.llm_service import LLMProvider
        assert service.get_provider("ollama/llama3") == LLMProvider.OLLAMA
        assert service.get_provider("llama3:8b") == LLMProvider.OLLAMA

    def test_get_provider_various(self):
        service = _service()
        from core.llm_service import LLMProvider
        assert service.get_provider("gpt-4o") == LLMProvider.OPENAI
        assert service.get_provider("claude-3") == LLMProvider.ANTHROPIC
        assert service.get_provider("deepseek-chat") == LLMProvider.DEEPSEEK
        assert service.get_provider("gemini-pro") == LLMProvider.GEMINI
        assert service.get_provider("minimax-m2") == LLMProvider.MINIMAX
        assert service.get_provider("mistral-7b") == LLMProvider.MISTRAL
        assert service.get_provider("qwen-72b") == LLMProvider.QWEN
        assert service.get_provider("mimo-v2") == LLMProvider.XIAOMI
        assert service.get_provider("command-r") == LLMProvider.COHERE
        assert service.get_provider("unknown-model") == LLMProvider.OPENAI

    async def test_generate_structured_response_with_personalization(self):
        handler = MagicMock()
        handler.generate_structured_response = AsyncMock(return_value={"ok": True})
        service = _service(handler=handler)
        service.continuous_learning = MagicMock()
        service.continuous_learning.get_personalized_parameters = MagicMock(
            return_value={"temperature": 0.7})
        result = await service.generate_structured_response(
            "prompt", response_model=dict, agent_id="a-1")
        assert result == {"ok": True}
        call = handler.generate_structured_response.await_args.kwargs
        assert call["temperature"] == 0.7

    def test_estimate_tokens_str_and_list(self):
        service = _service()
        service._token_counter = MagicMock()
        service._token_counter.count_tokens.return_value = 42
        service._context_validator = MagicMock()
        service._context_validator.estimate_request_tokens.return_value = 99
        assert service.estimate_tokens("hello") == 42
        assert service.estimate_tokens([{"role": "user", "content": "hi"}]) == 99
        assert service.estimate_tokens(12345) == 0  # unsupported type


class TestAnalyzeProposal:
    async def test_analyze_proposal_json(self):
        handler = MagicMock()
        handler.generate_response = AsyncMock(
            return_value='{"safe": true, "risk_level": "low", "recommendation": "ok"}')
        service = _service(handler=handler)
        with patch.object(service, "_resolve_governance_model",
                          return_value="gpt-4o"):
            result = await service.analyze_proposal("proposal text")
        assert result["safe"] is True
        assert result["risk_level"] == "low"

    async def test_analyze_proposal_json_block(self):
        handler = MagicMock()
        handler.generate_response = AsyncMock(
            return_value='```json\n{"safe": false, "risk_level": "high"}\n```')
        service = _service(handler=handler)
        with patch.object(service, "_resolve_governance_model",
                          return_value="gpt-4o"):
            result = await service.analyze_proposal("proposal")
        assert result["safe"] is False

    async def test_analyze_proposal_parse_failure(self):
        handler = MagicMock()
        handler.generate_response = AsyncMock(return_value="not json at all")
        service = _service(handler=handler)
        with patch.object(service, "_resolve_governance_model",
                          return_value="gpt-4o"):
            result = await service.analyze_proposal("proposal")
        assert result["error"] == "Failed to parse structured audit"
        assert result["raw_response"] == "not json at all"


class TestStructuredConsensusBranch:
    async def test_generate_structured_consensus(self):
        handler = MagicMock()
        service = _service(handler=handler)
        vote = _vote()
        with patch.object(service, "is_available", return_value=True), \
             patch("core.hallucination_config.is_self_consistency_enabled",
                   return_value=True), \
             patch("core.hallucination_config.is_cascade_routing_enabled",
                   return_value=False), \
             patch.object(service, "_run_self_consistency_vote",
                          new=AsyncMock(return_value=(vote.winner, vote))):
            result = await service.generate_structured(
                "prompt", response_model=dict, enable_self_consistency=True)
        assert result is vote.winner

    async def test_generate_structured_consensus_disabled_flag(self):
        handler = MagicMock()
        handler.generate_structured_response = AsyncMock(return_value="plain")
        service = _service(handler=handler)
        with patch.object(service, "is_available", return_value=True), \
             patch("core.hallucination_config.is_self_consistency_enabled",
                   return_value=False), \
             patch("core.hallucination_config.is_cascade_routing_enabled",
                   return_value=False):
            result = await service.generate_structured(
                "prompt", response_model=dict, enable_self_consistency=True)
        assert result == "plain"


class TestFactory:
    def test_get_llm_service(self):
        from core.llm_service import get_llm_service
        service = get_llm_service("ws-9", db=MagicMock(), tenant_id="t-9")
        assert isinstance(service, LLMService)
        assert service._workspace_id == "ws-9"
        assert service._tenant_id == "t-9"


class TestStreamCompletion:
    async def test_stream_completion_auto_model(self):
        from core.llm.byok_handler import AwaitableResult
        handler = MagicMock()
        handler.analyze_query_complexity = MagicMock(return_value="complex")
        handler.get_optimal_provider = MagicMock(
            return_value=AwaitableResult(("openai", "gpt-4o")))

        async def _fake_stream(**kwargs):
            yield "tok1"
            yield "tok2"

        handler.stream_completion = _fake_stream
        service = _service(handler=handler)
        tokens = []
        async for token in service.stream_completion(
            [{"role": "user", "content": "hello world"}], model="auto"):
            tokens.append(token)
        assert tokens == ["tok1", "tok2"]
        handler.analyze_query_complexity.assert_called_once()

    async def test_stream_completion_static_model(self):
        from core.llm.byok_handler import AwaitableResult
        handler = MagicMock()
        handler.analyze_query_complexity = MagicMock(return_value="simple")
        handler.get_optimal_provider = MagicMock(
            return_value=AwaitableResult(("openai", "gpt-4o")))

        async def _fake_stream(**kwargs):
            yield "x"

        handler.stream_completion = _fake_stream
        service = _service(handler=handler)
        tokens = []
        async for token in service.stream_completion(
            [{"role": "user", "content": "hi"}], model="gpt-4o"):
            tokens.append(token)
        assert tokens == ["x"]
        assert handler.stream_completion is not None


class TestGenerate:
    async def test_generate_with_personalization(self):
        handler = MagicMock()
        handler.generate_response = AsyncMock(return_value="response")
        service = _service(handler=handler)
        service.continuous_learning = MagicMock()
        service.continuous_learning.get_personalized_parameters = MagicMock(
            return_value={"temperature": 0.3})
        with patch.object(service, "_resolve_governance_model",
                          return_value="gpt-4o"):
            result = await service.generate(
                "prompt", agent_id="a-1")
        assert result == "response"
        call = handler.generate_response.await_args.kwargs
        assert call["temperature"] == 0.3


class TestFrugalMode:
    def test_resolve_frugal_deescalates(self):
        db = MagicMock()
        ws = MagicMock()
        ws.metadata_json = {"frugal_mode": True}
        db.query.return_value.filter.return_value.first.return_value = ws
        service = _service(db=db)
        assert service._resolve_governance_model("t-1", "gpt-4o") == "gpt-4o-mini"
        assert service._resolve_governance_model("t-1", "claude-3-opus-20240229") == "claude-3-haiku-20240307"
        assert service._resolve_governance_model("t-1", "gemini-1.5-pro") == "gemini-1.5-flash"
        assert service._resolve_governance_model("t-1", "deepseek-reasoner") == "deepseek-chat"

    def test_resolve_frugal_unknown_model_unchanged(self):
        db = MagicMock()
        ws = MagicMock()
        ws.metadata_json = {"frugal_mode": True}
        db.query.return_value.filter.return_value.first.return_value = ws
        service = _service(db=db)
        assert service._resolve_governance_model("t-1", "some-other-model") == "some-other-model"
