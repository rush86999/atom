"""Coverage wave 11c — Mixture-of-Agents, cascade escalation, transcription
(TDD). All tests drive the REAL byok_handler methods with mocked provider
clients / inner calls.
"""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm.byok_handler import BYOKHandler, QueryComplexity


def _make_handler():
    with patch("core.llm.byok_handler.OpenAI", return_value=MagicMock()), \
         patch("core.llm.byok_handler.AsyncOpenAI", return_value=MagicMock()), \
         patch("core.llm.byok_handler.get_db_session"):
        handler = BYOKHandler(workspace_id="default", tenant_id="default")
    handler.clients = {"openai": MagicMock(), "anthropic": MagicMock()}
    handler.async_clients = {"openai": MagicMock(), "anthropic": MagicMock()}
    handler.health_monitor = MagicMock()
    handler.health_monitor.health_scores = {}
    handler.byok_manager.is_configured = MagicMock(return_value=False)
    handler.byok_manager.get_api_key = MagicMock(return_value=None)
    return handler


class _Sample:
    """Hashable structured sample (pydantic-like)."""

    def __init__(self, value):
        self.value = value

    def model_dump(self, mode="python"):
        return {"value": self.value}

    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other):
        return isinstance(other, _Sample) and other.value == self.value


# =========================================================================== #
# generate_structured_moa
# =========================================================================== #
class TestGenerateStructuredMoa:
    async def _run(self, handler, options=None, **kw):
        return await handler.generate_structured_moa(
            prompt="Hard task",
            system_instruction="sys",
            response_model=SimpleNamespace,
            temperature=0.2,
            task_type="reasoning",
            agent_id=None,
            chain_id=None,
            options=options or [("openai", "gpt-4o"), ("anthropic", "claude-sonnet")],
            tenant_plan="pro",
            is_managed=True,
            complexity=QueryComplexity.COMPLEX,
            cascade=False,
            **kw,
        )

    @pytest.mark.asyncio
    async def test_single_valid_sample_returns_directly(self):
        handler = _make_handler()
        sample = _Sample("a")
        handler.generate_structured_response = AsyncMock(
            side_effect=[sample, sample, sample]
        )
        result = await self._run(handler)
        assert result is sample
        assert handler.generate_structured_response.await_count == 3

    @pytest.mark.asyncio
    async def test_aggregator_reconciles_samples(self):
        handler = _make_handler()
        sample_a, sample_b, agg = _Sample("a"), _Sample("b"), _Sample("agg")
        handler.generate_structured_response = AsyncMock(
            side_effect=[sample_a, sample_b, agg]
        )
        result = await self._run(handler)
        assert result is agg
        assert handler.generate_structured_response.await_count == 3
        # samples pinned + no recursion
        for call in handler.generate_structured_response.await_args_list:
            assert call.kwargs["allow_moa"] is False
            assert call.kwargs["provider_model"] is not None

    @pytest.mark.asyncio
    async def test_all_samples_fail_returns_none(self):
        handler = _make_handler()
        handler.generate_structured_response = AsyncMock(return_value=None)
        result = await self._run(handler)
        assert result is None

    @pytest.mark.asyncio
    async def test_aggregator_failure_falls_back_to_best_sample(self):
        handler = _make_handler()
        sample_a, sample_b = _Sample("a"), _Sample("b")
        handler.generate_structured_response = AsyncMock(
            side_effect=[sample_a, sample_b, None]
        )
        result = await self._run(handler)
        assert result is sample_a  # best-ranked valid sample

    @pytest.mark.asyncio
    async def test_consensus_agreement_high(self):
        handler = _make_handler()
        sample = _Sample("same")
        handler.generate_structured_response = AsyncMock(
            side_effect=[sample, sample, _Sample("harmonized")]
        )
        await self._run(handler)
        agg_prompt = handler.generate_structured_response.await_args_list[2].kwargs["prompt"]
        assert "[CONSENSUS]" in agg_prompt
        assert "agree strongly" in agg_prompt
        assert "[CANDIDATE ANSWER 1]" in agg_prompt

    @pytest.mark.asyncio
    async def test_consensus_agreement_low(self):
        handler = _make_handler()
        handler.generate_structured_response = AsyncMock(
            side_effect=[_Sample("x"), _Sample("y"), _Sample("z"), _Sample("agg")]
        )
        await self._run(
            handler,
            options=[("openai", "gpt-4o"), ("anthropic", "c1"), ("deepseek", "d1")],
        )
        agg_prompt = handler.generate_structured_response.await_args_list[3].kwargs["prompt"]
        assert "disagree substantially" in agg_prompt

    @pytest.mark.asyncio
    async def test_sample_exception_tolerated(self):
        handler = _make_handler()
        b = _Sample("b")
        handler.generate_structured_response = AsyncMock(
            side_effect=[RuntimeError("sample boom"), b, b]
        )
        result = await self._run(handler)
        assert result is b  # one failed sample; the valid one degrades gracefully

    def test_moa_eligible(self):
        handler = _make_handler()
        assert handler._moa_eligible(QueryComplexity.COMPLEX, None) is True
        assert handler._moa_eligible(QueryComplexity.ADVANCED, None) is True
        assert handler._moa_eligible(QueryComplexity.SIMPLE, "code") is True
        assert handler._moa_eligible(QueryComplexity.SIMPLE, "analysis") is True
        assert handler._moa_eligible(QueryComplexity.SIMPLE, "chat") is False

    def test_render_sample_variants(self):
        assert BYOKHandler._render_sample(_Sample("v")) == json.dumps({"value": "v"})

        class _DictSample:
            def dict(self):
                return {"k": 1}

        assert BYOKHandler._render_sample(_DictSample()) == '{"k": 1}'
        assert BYOKHandler._render_sample("plain") == "plain"
        assert BYOKHandler._render_sample(42) == "42"

        class _Broken:
            def model_dump(self):
                raise RuntimeError("boom")

        assert BYOKHandler._render_sample(_Broken()).startswith("<")

    def test_build_aggregator_prompt_branches(self):
        p = BYOKHandler._build_moa_aggregator_prompt("q", [_Sample("a")])
        assert "[MIXTURE-OF-AGENTS]" in p and "q" in p
        p75 = BYOKHandler._build_moa_aggregator_prompt("q", [_Sample("a")], agreement=0.8)
        assert "agree strongly" in p75
        p50 = BYOKHandler._build_moa_aggregator_prompt("q", [_Sample("a")], agreement=0.6)
        assert "partially agree" in p50
        p25 = BYOKHandler._build_moa_aggregator_prompt("q", [_Sample("a")], agreement=0.4)
        assert "disagree substantially" in p25

    @pytest.mark.asyncio
    async def test_single_option_path(self):
        handler = _make_handler()
        sample = _Sample("only")
        handler.generate_structured_response = AsyncMock(return_value=sample)
        result = await handler.generate_structured_moa(
            prompt="p", system_instruction="s", response_model=SimpleNamespace,
            temperature=0.2, task_type="chat", agent_id=None, chain_id=None,
            options=[("openai", "gpt-4o")], tenant_plan="pro", is_managed=True,
            complexity=QueryComplexity.COMPLEX, cascade=False,
        )
        assert result is sample


# =========================================================================== #
# Cascade escalation (schema error -> frontier retry)
# =========================================================================== #
class TestCascadeEscalation:
    @pytest.mark.asyncio
    async def test_schema_error_escalates_to_frontier(self):
        import instructor

        handler = _make_handler()
        from pydantic import ValidationError

        from core.hallucination_config import get_frontier_model_for_provider

        fake_instructor = MagicMock()
        fake_instructor.chat.completions.create.side_effect = [
            ValidationError.from_exception_data("x", []),  # schema failure
            SimpleNamespace(parsed="recovered"),
        ]
        session = MagicMock()
        workspace = SimpleNamespace(tenant_id="t-1")
        tenant = SimpleNamespace(plan_type=SimpleNamespace(value="pro"))

        def _query(model):
            q = MagicMock()
            if model is SimpleNamespace:  # placeholder
                pass
            return q

        from core.models import Tenant as _Tenant, Workspace as _Workspace

        def _query2(model):
            q = MagicMock()
            if model is _Workspace:
                q.filter.return_value.first.return_value = workspace
            elif model is _Tenant:
                q.filter.return_value.first.return_value = tenant
            else:
                q.filter.return_value.first.return_value = None
                q.all.return_value = []
            return q

        session.query.side_effect = _query2
        ctx = MagicMock()
        ctx.__enter__.return_value = session
        ctx.__exit__.return_value = False

        handler.clients = {"openai": MagicMock()}
        handler.get_ranked_providers = AsyncMock(
            return_value=[("openai", "gpt-4o-mini")]
        )
        handler.get_optimal_provider = AsyncMock(return_value=("openai", "gpt-4o-mini"))
        handler.byok_manager.get_tenant_api_key = MagicMock(return_value=None)
        handler._db_patch = patch("core.database.get_db_session", return_value=ctx)

        with patch.object(instructor, "from_openai", return_value=fake_instructor), \
             handler._db_patch:
            result = await handler.generate_structured_response(
                "Extract", "sys", SimpleNamespace, task_type="chat",
                cascade=True, allow_moa=False,
            )
        assert result is not None
        # frontier model was attempted after the schema failure
        frontier = get_frontier_model_for_provider("openai")
        models_tried = [c.kwargs.get("model") for c in fake_instructor.chat.completions.create.call_args_list]
        if frontier and frontier != "gpt-4o-mini":
            assert frontier in models_tried

    @pytest.mark.asyncio
    async def test_transient_error_no_cascade(self):
        import instructor

        handler = _make_handler()
        fake_instructor = MagicMock()
        fake_instructor.chat.completions.create.side_effect = RuntimeError("network")
        session = MagicMock()
        workspace = SimpleNamespace(tenant_id="t-1")
        tenant = SimpleNamespace(plan_type=SimpleNamespace(value="pro"))
        from core.models import Tenant as _Tenant, Workspace as _Workspace

        def _query2(model):
            q = MagicMock()
            if model is _Workspace:
                q.filter.return_value.first.return_value = workspace
            elif model is _Tenant:
                q.filter.return_value.first.return_value = tenant
            else:
                q.filter.return_value.first.return_value = None
                q.all.return_value = []
            return q

        session.query.side_effect = _query2
        ctx = MagicMock()
        ctx.__enter__.return_value = session
        ctx.__exit__.return_value = False

        handler.clients = {"openai": MagicMock()}
        handler.get_ranked_providers = AsyncMock(
            return_value=[("openai", "gpt-4o-mini")]
        )
        handler.get_optimal_provider = AsyncMock(return_value=("openai", "gpt-4o-mini"))
        handler.byok_manager.get_tenant_api_key = MagicMock(return_value=None)
        handler._db_patch = patch("core.database.get_db_session", return_value=ctx)

        with patch.object(instructor, "from_openai", return_value=fake_instructor), \
             handler._db_patch:
            result = await handler.generate_structured_response(
                "Extract", "sys", SimpleNamespace, task_type="chat",
                cascade=True, allow_moa=False,
            )
        assert result is None
        # transient errors must NOT trigger frontier escalation
        assert fake_instructor.chat.completions.create.call_count == 1


# =========================================================================== #
# generate_transcription (Whisper)
# =========================================================================== #
class TestTranscription:
    @pytest.mark.asyncio
    async def test_success(self):
        handler = _make_handler()
        handler.async_clients["openai"] = SimpleNamespace(
            client=SimpleNamespace(
                audio=SimpleNamespace(
                    transcriptions=SimpleNamespace(
                        create=AsyncMock(return_value=SimpleNamespace(text="hello world"))
                    )
                )
            )
        )
        out = await handler.generate_transcription(file=b"audio", model="whisper-1")
        assert out["text"] == "hello world"
        assert out["provider"] == "openai"

    @pytest.mark.asyncio
    async def test_no_openai_client_raises(self):
        handler = _make_handler(clients=(), async_clients=()) if False else _make_handler()
        handler.async_clients = {}
        handler.clients = {}
        with pytest.raises(ValueError):
            await handler.generate_transcription(file=b"audio")

    @pytest.mark.asyncio
    async def test_provider_error_propagates(self):
        handler = _make_handler()
        handler.async_clients["openai"] = SimpleNamespace(
            client=SimpleNamespace(
                audio=SimpleNamespace(
                    transcriptions=SimpleNamespace(
                        create=AsyncMock(side_effect=RuntimeError("whisper down"))
                    )
                )
            )
        )
        with pytest.raises(RuntimeError):
            await handler.generate_transcription(file=b"audio")
