"""Coverage wave 64j-b — byok_handler structured/MoA/streaming/chat edges (TDD).

Extends test_covpush_w64j_byok_handler.py. Targets: generate_structured_response
(stage-carrier exception, BYOK tenant paths, provider_model pin, vision
coordination + panic fallback, empty options, MoA dispatch, pre-compress
enqueue, vision payload messages, raw finish_reason, result.usage, cost
tracking, outer error), generate_structured_moa (diversity overlays, agreement
computation + error, irreversibility audit + error, aggregator degrade),
_moa_eligible/_render_sample/_build_moa_aggregator_prompt full branches,
_get_coordinated_vision_description (gemini/deepseek/openai/no-client/error),
get_routing_info/refresh_pricing/get_provider_comparison/get_cheapest_models,
stream_completion (no-order, sync-client, ghost-client, fallback-serve skip,
governance completion + tracking error, health-failure, self-heal stream,
free->paid stream retry, all-failed execution record, CancelledError cleanup),
chat_completion (trial-check error, no-order, fallback-serve skip, cost error,
tracking error, self-heal success), generate_embedding(s) batch providers.
"""
import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm.byok_handler import BYOKHandler, QueryComplexity
from core.llm.cognitive_tier_system import CognitiveTier

from tests.test_covpush_w64j_byok_handler import (
    _budget,
    _chunk,
    _ctx,
    _db_active,
    _make_handler,
    _ok_response,
    _stream,
    _usage_response,
)


def _instructor_result(**kw):
    """Structured result with optional _raw_response / usage / .usage."""
    return SimpleNamespace(**kw) if kw else SimpleNamespace()


# =========================================================================== #
# generate_structured_response — edge branches
# =========================================================================== #
class TestStructuredEdges:
    def _instructor_patch(self, result=None, error=None, side_effect=None):
        import instructor

        fake = MagicMock()
        if side_effect is not None:
            fake.chat.completions.create.side_effect = side_effect
        elif error is not None:
            fake.chat.completions.create.side_effect = error
        else:
            fake.chat.completions.create.return_value = result
        return patch.object(instructor, "from_openai", return_value=fake), fake

    @pytest.mark.asyncio
    async def test_stage_carrier_exception_tolerated(self):
        handler, _ = _make_handler()
        handler._is_trial_restricted = lambda: True
        with patch(
            "core.llm.stage_router.set_stage_decision_carrier",
            side_effect=RuntimeError("carrier down"),
        ):
            result = await handler.generate_structured_response(
                "x", "sys", response_model=SimpleNamespace
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_tenant_key_forces_byok(self):
        handler, _ = _make_handler()
        handler.byok_manager.get_tenant_api_key = MagicMock(return_value="sk-x")
        fake_result = SimpleNamespace(parsed="ok")
        with self._instructor_patch(result=fake_result)[0], _db_active(handler):
            result = await handler.generate_structured_response(
                "Extract", "sys", response_model=SimpleNamespace,
                task_type="chat", allow_moa=False,
            )
        assert result is fake_result

    @pytest.mark.asyncio
    async def test_byok_plan_forces_byok(self):
        handler, _ = _make_handler(workspace_plan="pro")
        handler.byok_manager.get_tenant_api_key = MagicMock(return_value=None)
        fake_result = SimpleNamespace(parsed="ok")
        with self._instructor_patch(result=fake_result)[0], _db_active(handler):
            result = await handler.generate_structured_response(
                "Extract", "sys", response_model=SimpleNamespace,
                task_type="chat", allow_moa=False,
            )
        assert result is fake_result

    @pytest.mark.asyncio
    async def test_provider_model_pin(self):
        handler, _ = _make_handler()
        fake_result = SimpleNamespace(parsed="ok")
        ipatch, fake = self._instructor_patch(result=fake_result)
        with ipatch, _db_active(handler):
            result = await handler.generate_structured_response(
                "Extract", "sys", response_model=SimpleNamespace,
                task_type="chat", provider_model=("openai", "gpt-4o-mini"),
            )
        assert result is fake_result
        assert fake.chat.completions.create.call_args.kwargs["model"] == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_vision_coordination_and_panic_fallback(self):
        handler, _ = _make_handler()
        handler.get_ranked_providers = AsyncMock(return_value=[("deepseek", "deepseek-chat")])
        handler._model_supports_vision = MagicMock(return_value=False)
        handler._get_coordinated_vision_description = AsyncMock(return_value="visual desc")
        fake_result = SimpleNamespace(parsed="ok")
        ipatch, fake = self._instructor_patch(result=fake_result)
        with ipatch, _db_active(handler):
            result = await handler.generate_structured_response(
                "click the button", "sys", response_model=SimpleNamespace,
                task_type="chat", image_payload="b64==",
            )
        assert result is fake_result
        kwargs = fake.chat.completions.create.call_args.kwargs
        assert kwargs["model"] == "gpt-4o"  # panic fallback
        assert "[VISUAL CONTEXT ANALYSIS]" in kwargs["messages"][1]["content"]

    @pytest.mark.asyncio
    async def test_empty_options_returns_none(self):
        handler, _ = _make_handler()
        handler.get_ranked_providers = AsyncMock(return_value=[])
        with _db_active(handler):
            result = await handler.generate_structured_response(
                "x", "sys", response_model=SimpleNamespace, task_type="chat"
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_moa_dispatch(self):
        handler, _ = _make_handler()
        handler.get_ranked_providers = AsyncMock(
            return_value=[("openai", "gpt-4o-mini"), ("deepseek", "deepseek-chat")]
        )
        handler.generate_structured_moa = AsyncMock(return_value="moa-result")
        with _db_active(handler):
            result = await handler.generate_structured_response(
                "write code", "sys", response_model=SimpleNamespace,
                task_type="code",
            )
        assert result == "moa-result"
        assert handler.generate_structured_moa.called

    @pytest.mark.asyncio
    async def test_pre_compress_enqueue_before_truncation(self):
        handler, _ = _make_handler()
        handler.get_context_window = MagicMock(return_value=4096)
        fake_result = SimpleNamespace(parsed="ok")
        queue = MagicMock()
        with self._instructor_patch(result=fake_result)[0], \
             patch("core.turn_fact_queue.get_extraction_queue", return_value=queue), \
             _db_active(handler):
            result = await handler.generate_structured_response(
                "x" * 20000, "sys", response_model=SimpleNamespace,
                task_type="chat", allow_moa=False,
            )
        assert result is fake_result
        assert queue.enqueue.called
        assert queue.ensure_worker.called

    @pytest.mark.asyncio
    async def test_pre_compress_queue_error_tolerated(self):
        handler, _ = _make_handler()
        handler.get_context_window = MagicMock(return_value=4096)
        fake_result = SimpleNamespace(parsed="ok")
        with self._instructor_patch(result=fake_result)[0], \
             patch(
                 "core.turn_fact_queue.get_extraction_queue",
                 side_effect=RuntimeError("queue down"),
             ), _db_active(handler):
            result = await handler.generate_structured_response(
                "x" * 20000, "sys", response_model=SimpleNamespace,
                task_type="chat", allow_moa=False,
            )
        assert result is fake_result

    @pytest.mark.asyncio
    async def test_vision_payload_messages(self):
        handler, _ = _make_handler()
        handler._model_supports_vision = MagicMock(return_value=True)
        fake_result = SimpleNamespace(parsed="ok")
        ipatch, fake = self._instructor_patch(result=fake_result)
        with ipatch, _db_active(handler):
            result = await handler.generate_structured_response(
                "what is this", "sys", response_model=SimpleNamespace,
                task_type="chat", image_payload="b64==",
            )
        assert result is fake_result
        content = fake.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        assert content[1]["type"] == "image_url"
        assert "data:image/jpeg;base64," in content[1]["image_url"]["url"]

    @pytest.mark.asyncio
    async def test_raw_finish_reason_and_result_usage(self):
        handler, _ = _make_handler()
        fake_result = SimpleNamespace(
            _raw_response=SimpleNamespace(finish_reason="length"),
            usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2),
        )
        fetcher = MagicMock()
        fetcher.estimate_cost.return_value = 0.001
        fetcher.get_model_price.return_value = None
        handler.rate_tracker = MagicMock()
        with self._instructor_patch(result=fake_result)[0], \
             patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher), \
             _db_active(handler):
            result = await handler.generate_structured_response(
                "Extract", "sys", response_model=SimpleNamespace,
                task_type="chat", allow_moa=False,
            )
        assert result is fake_result
        assert handler.rate_tracker.record_usage.called

    @pytest.mark.asyncio
    async def test_raw_finish_reason_extraction_error_tolerated(self):
        class _RaisingRaw:
            @property
            def finish_reason(self):
                raise RuntimeError("boom")

        handler, _ = _make_handler()
        fake_result = SimpleNamespace(_raw_response=_RaisingRaw())
        with self._instructor_patch(result=fake_result)[0], _db_active(handler):
            result = await handler.generate_structured_response(
                "Extract", "sys", response_model=SimpleNamespace,
                task_type="chat", allow_moa=False,
            )
        assert result is fake_result

    @pytest.mark.asyncio
    async def test_structured_cost_tracking_error(self):
        handler, _ = _make_handler()
        fake_result = SimpleNamespace(
            _raw_response=SimpleNamespace(
                usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2)
            ),
        )
        fetcher = MagicMock()
        fetcher.estimate_cost.side_effect = RuntimeError("no pricing")
        fetcher.get_model_price.return_value = None
        handler.rate_tracker = MagicMock()
        with self._instructor_patch(result=fake_result)[0], \
             patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher), \
             _db_active(handler):
            result = await handler.generate_structured_response(
                "Extract", "sys", response_model=SimpleNamespace,
                task_type="chat", allow_moa=False,
            )
        assert result is fake_result

    @pytest.mark.asyncio
    async def test_cascade_schema_error_escalates(self):
        handler, _ = _make_handler()
        fake_result = SimpleNamespace(parsed="recovered")
        first_err = RuntimeError("validation failed on output")
        with self._instructor_patch(
            side_effect=[first_err, fake_result],
        )[0], _db_active(handler), \
             patch("core.hallucination_config.is_frontier_model", return_value=False), \
             patch("core.hallucination_config.get_frontier_model_for_provider",
                   return_value="gpt-5"):
            result = await handler.generate_structured_response(
                "Extract", "sys", response_model=SimpleNamespace,
                task_type="chat", cascade=True, allow_moa=False,
            )
        assert result is fake_result

    @pytest.mark.asyncio
    async def test_instructor_unavailable_returns_none(self):
        handler, _ = _make_handler()
        with patch("core.llm.byok_handler.INSTRUCTOR_AVAILABLE", False), _db_active(handler):
            result = await handler.generate_structured_response(
                "x", "sys", response_model=SimpleNamespace, task_type="chat"
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_outer_structured_error_returns_none(self):
        handler, _ = _make_handler()
        with patch(
            "core.llm.byok_handler.get_db_session",
            side_effect=RuntimeError("db down"),
        ):
            result = await handler.generate_structured_response(
                "x", "sys", response_model=SimpleNamespace, task_type="chat"
            )
        assert result is None


# =========================================================================== #
# MoA helpers + generate_structured_moa
# =========================================================================== #
class TestMoaEdges:
    def test_moa_eligible_matrix(self):
        handler, _ = _make_handler()
        assert handler._moa_eligible(QueryComplexity.COMPLEX, None) is True
        assert handler._moa_eligible(QueryComplexity.ADVANCED, "chat") is True
        assert handler._moa_eligible(QueryComplexity.SIMPLE, "code") is True
        assert handler._moa_eligible(QueryComplexity.SIMPLE, "chat") is False
        assert handler._moa_eligible(QueryComplexity.MODERATE, None) is False

    def test_render_sample_variants(self):
        class _Pd:
            def model_dump(self):
                return {"a": 1}

        class _Dc:
            def dict(self):
                return {"b": 2}

        assert json.loads(BYOKHandler._render_sample(_Pd())) == {"a": 1}
        assert json.loads(BYOKHandler._render_sample(_Dc())) == {"b": 2}
        assert BYOKHandler._render_sample("plain") == "plain"

        class _Broken:
            def model_dump(self):
                raise RuntimeError("boom")

        broken = _Broken()
        assert BYOKHandler._render_sample(broken) == str(broken)

    def test_build_aggregator_prompt_agreement_branches(self):
        prompt = BYOKHandler._build_moa_aggregator_prompt("ask", ["s1"], agreement=0.8)
        assert "Harmonize" in prompt
        prompt = BYOKHandler._build_moa_aggregator_prompt("ask", ["s1"], agreement=0.3)
        assert "contradictions" in prompt
        prompt = BYOKHandler._build_moa_aggregator_prompt("ask", ["s1"], agreement=0.6)
        assert "partially agree" in prompt
        prompt = BYOKHandler._build_moa_aggregator_prompt("ask", ["s1"])
        assert "[CONSENSUS]" not in prompt

    @pytest.mark.asyncio
    async def test_moa_single_valid_sample_wins(self):
        handler, _ = _make_handler()
        handler.generate_structured_response = AsyncMock(side_effect=[None, "sample2"])
        result = await handler.generate_structured_moa(
            prompt="p", system_instruction="sys", response_model=SimpleNamespace,
            temperature=0.2, task_type="code", agent_id=None, chain_id=None,
            options=[("openai", "gpt-4o-mini"), ("deepseek", "deepseek-chat")],
            tenant_plan="pro", is_managed=False,
            complexity=QueryComplexity.COMPLEX, cascade=False,
        )
        assert result == "sample2"

    @pytest.mark.asyncio
    async def test_moa_all_samples_fail(self):
        handler, _ = _make_handler()
        handler.generate_structured_response = AsyncMock(return_value=None)
        result = await handler.generate_structured_moa(
            prompt="p", system_instruction="sys", response_model=SimpleNamespace,
            temperature=0.2, task_type="code", agent_id=None, chain_id=None,
            options=[("openai", "gpt-4o-mini"), ("deepseek", "deepseek-chat")],
            tenant_plan="pro", is_managed=False,
            complexity=QueryComplexity.COMPLEX, cascade=False,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_moa_sample_exception_tolerated(self):
        handler, _ = _make_handler()
        handler.generate_structured_response = AsyncMock(
            side_effect=[RuntimeError("sample exploded"), "sample2"]
        )
        result = await handler.generate_structured_moa(
            prompt="p", system_instruction="sys", response_model=SimpleNamespace,
            temperature=0.2, task_type="code", agent_id=None, chain_id=None,
            options=[("openai", "gpt-4o-mini"), ("deepseek", "deepseek-chat")],
            tenant_plan="pro", is_managed=False,
            complexity=QueryComplexity.COMPLEX, cascade=False,
        )
        assert result == "sample2"

    @pytest.mark.asyncio
    async def test_moa_agreement_computation(self):
        handler, _ = _make_handler()
        handler.generate_structured_response = AsyncMock(
            side_effect=[SimpleNamespace(parsed="a"), SimpleNamespace(parsed="a"), "agg"]
        )
        result = await handler.generate_structured_moa(
            prompt="p", system_instruction="sys", response_model=SimpleNamespace,
            temperature=0.2, task_type="code", agent_id=None, chain_id=None,
            options=[("openai", "gpt-4o-mini"), ("deepseek", "deepseek-chat")],
            tenant_plan="pro", is_managed=False,
            complexity=QueryComplexity.COMPLEX, cascade=False,
        )
        assert result == "agg"

    @pytest.mark.asyncio
    async def test_moa_agreement_error_tolerated(self):
        handler, _ = _make_handler()
        handler.generate_structured_response = AsyncMock(
            side_effect=[SimpleNamespace(parsed="a"), SimpleNamespace(parsed="b"), "agg"]
        )
        with patch(
            "core.llm.self_consistency_voter.SelfConsistencyVoter._hash_sample",
            side_effect=RuntimeError("hash broke"),
        ):
            result = await handler.generate_structured_moa(
                prompt="p", system_instruction="sys", response_model=SimpleNamespace,
                temperature=0.2, task_type="code", agent_id=None, chain_id=None,
                options=[("openai", "gpt-4o-mini"), ("deepseek", "deepseek-chat")],
                tenant_plan="pro", is_managed=False,
                complexity=QueryComplexity.COMPLEX, cascade=False,
            )
        assert result == "agg"

    @pytest.mark.asyncio
    async def test_moa_irreversibility_audit_hit(self):
        handler, _ = _make_handler()
        handler.generate_structured_response = AsyncMock(
            side_effect=[SimpleNamespace(parsed="a"), SimpleNamespace(parsed="b"), "agg"]
        )
        with patch(
            "core.llm.self_consistency_voter.SelfConsistencyVoter.is_irreversible",
            return_value=True,
        ):
            result = await handler.generate_structured_moa(
                prompt="p", system_instruction="sys", response_model=SimpleNamespace,
                temperature=0.2, task_type="code", agent_id=None, chain_id=None,
                options=[("openai", "gpt-4o-mini"), ("deepseek", "deepseek-chat")],
                tenant_plan="pro", is_managed=False,
                complexity=QueryComplexity.COMPLEX, cascade=False,
            )
        assert result == "agg"

    @pytest.mark.asyncio
    async def test_moa_irreversibility_audit_error(self):
        handler, _ = _make_handler()
        handler.generate_structured_response = AsyncMock(
            side_effect=[SimpleNamespace(parsed="a"), SimpleNamespace(parsed="b"), "agg"]
        )
        with patch(
            "core.llm.self_consistency_voter.SelfConsistencyVoter.is_irreversible",
            side_effect=RuntimeError("audit broke"),
        ):
            result = await handler.generate_structured_moa(
                prompt="p", system_instruction="sys", response_model=SimpleNamespace,
                temperature=0.2, task_type="code", agent_id=None, chain_id=None,
                options=[("openai", "gpt-4o-mini"), ("deepseek", "deepseek-chat")],
                tenant_plan="pro", is_managed=False,
                complexity=QueryComplexity.COMPLEX, cascade=False,
            )
        assert result == "agg"

    @pytest.mark.asyncio
    async def test_moa_aggregator_failure_degrades_to_best_sample(self):
        handler, _ = _make_handler()
        handler.generate_structured_response = AsyncMock(
            side_effect=[SimpleNamespace(parsed="a"), SimpleNamespace(parsed="b"), None]
        )
        result = await handler.generate_structured_moa(
            prompt="p", system_instruction="sys", response_model=SimpleNamespace,
            temperature=0.2, task_type="code", agent_id=None, chain_id=None,
            options=[("openai", "gpt-4o-mini"), ("deepseek", "deepseek-chat")],
            tenant_plan="pro", is_managed=False,
            complexity=QueryComplexity.COMPLEX, cascade=False,
        )
        assert result.parsed == "a"

    @pytest.mark.asyncio
    async def test_moa_diversity_overlays_applied(self):
        handler, _ = _make_handler()
        handler.generate_structured_response = AsyncMock(
            side_effect=[SimpleNamespace(parsed="a"), SimpleNamespace(parsed="b"), "agg"]
        )
        with patch.dict(os.environ, {"ATOM_MOA_DIVERSITY_ENABLED": "true"}), \
             patch(
                 "core.llm.self_consistency_voter.SelfConsistencyVoter.diversity_overlays",
                 return_value=["perspective A", "perspective B"],
             ):
            result = await handler.generate_structured_moa(
                prompt="p", system_instruction="sys", response_model=SimpleNamespace,
                temperature=0.2, task_type="code", agent_id=None, chain_id=None,
                options=[("openai", "gpt-4o-mini"), ("deepseek", "deepseek-chat")],
                tenant_plan="pro", is_managed=False,
                complexity=QueryComplexity.COMPLEX, cascade=False,
            )
        assert result == "agg"
        calls = handler.generate_structured_response.call_args_list
        assert "perspective A" in calls[0].kwargs["system_instruction"]


# =========================================================================== #
# _get_coordinated_vision_description
# =========================================================================== #
class TestVisionCoordination:
    @pytest.mark.asyncio
    async def test_gemini_provider(self):
        handler, _ = _make_handler(clients=("gemini",))
        handler.clients["gemini"].chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="desc-gemini"))]
        )
        desc = await handler._get_coordinated_vision_description("b64==", "pro", False)
        assert desc == "desc-gemini"
        model = handler.clients["gemini"].chat.completions.create.call_args.kwargs["model"]
        assert model == "gemini-2.0-flash-exp"

    @pytest.mark.asyncio
    async def test_deepseek_janus_provider(self):
        handler, _ = _make_handler(clients=("deepseek",))
        handler.clients["deepseek"].chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="desc-janus"))]
        )
        desc = await handler._get_coordinated_vision_description("b64==", "pro", False)
        assert desc == "desc-janus"
        model = handler.clients["deepseek"].chat.completions.create.call_args.kwargs["model"]
        assert model == "janus-pro-7b"

    @pytest.mark.asyncio
    async def test_openai_fallback_provider(self):
        handler, _ = _make_handler(clients=("openai",))
        handler.clients["openai"].chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="desc-gpt"))]
        )
        desc = await handler._get_coordinated_vision_description("b64==", "pro", False)
        assert desc == "desc-gpt"
        model = handler.clients["openai"].chat.completions.create.call_args.kwargs["model"]
        assert model == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_no_client_returns_none(self):
        handler, _ = _make_handler(clients=("openai",))
        handler.clients = {}
        desc = await handler._get_coordinated_vision_description("b64==", "pro", False)
        assert desc is None

    @pytest.mark.asyncio
    async def test_http_url_payload(self):
        handler, _ = _make_handler(clients=("gemini",))
        handler.clients["gemini"].chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="desc"))]
        )
        await handler._get_coordinated_vision_description("https://example.com/i.png", "pro", False)
        url = handler.clients["gemini"].chat.completions.create.call_args.kwargs[
            "messages"][1]["content"][1]["image_url"]["url"]
        assert url == "https://example.com/i.png"

    @pytest.mark.asyncio
    async def test_error_returns_none(self):
        handler, _ = _make_handler(clients=("gemini",))
        handler.clients["gemini"].chat.completions.create.side_effect = RuntimeError("vision down")
        desc = await handler._get_coordinated_vision_description("b64==", "pro", False)
        assert desc is None


# =========================================================================== #
# Routing info / pricing surfaces
# =========================================================================== #
class TestRoutingSurfaces:
    def test_get_available_providers(self):
        handler, _ = _make_handler()
        assert handler.get_available_providers() == ["openai", "deepseek"]

    def test_get_routing_info_success(self):
        handler, _ = _make_handler()
        handler.get_optimal_provider = MagicMock(return_value=("openai", "gpt-4o-mini"))
        fetcher = MagicMock()
        fetcher.get_model_price.return_value = {"price": 1}
        fetcher.estimate_cost.return_value = 0.0042
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            info = handler.get_routing_info("hello", "chat")
        assert info["selected_provider"] == "openai"
        assert info["cost_tier"] == "premium"
        assert info["estimated_cost_usd"] == 0.0042

    def test_get_routing_info_cost_error(self):
        handler, _ = _make_handler()
        handler.get_optimal_provider = MagicMock(return_value=("openai", "gpt-4o-mini"))
        fetcher = MagicMock()
        fetcher.get_model_price.side_effect = RuntimeError("no pricing")
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            info = handler.get_routing_info("hello", "chat")
        assert info["estimated_cost_usd"] is None

    def test_get_routing_info_no_providers(self):
        handler, _ = _make_handler()
        handler.get_optimal_provider = MagicMock(side_effect=ValueError("no providers"))
        info = handler.get_routing_info("hello", "chat")
        assert "error" in info
        assert info["available_providers"] == []

    @pytest.mark.asyncio
    async def test_refresh_pricing_success(self):
        handler, _ = _make_handler()
        with patch("core.llm.byok_handler.refresh_pricing_cache", return_value={"a": 1, "b": 2}):
            result = await handler.refresh_pricing(force=True)
        assert result == {"status": "success", "model_count": 2}

    @pytest.mark.asyncio
    async def test_refresh_pricing_error(self):
        handler, _ = _make_handler()
        with patch(
            "core.llm.byok_handler.refresh_pricing_cache",
            side_effect=RuntimeError("fetch failed"),
        ):
            result = await handler.refresh_pricing()
        assert result["status"] == "error"

    def test_provider_comparison_dynamic(self):
        handler, _ = _make_handler()
        fetcher = MagicMock()
        fetcher.compare_providers.return_value = {"deepseek": {"avg_cost_per_token": 1e-6}}
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            result = handler.get_provider_comparison()
        assert result == {"deepseek": {"avg_cost_per_token": 1e-6}}

    def test_provider_comparison_empty_falls_to_static(self):
        handler, _ = _make_handler()
        fetcher = MagicMock()
        fetcher.compare_providers.return_value = {}
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            result = handler.get_provider_comparison()
        assert result["openai"]["tier"] == "premium"

    def test_provider_comparison_error_falls_to_static(self):
        handler, _ = _make_handler()
        with patch(
            "core.llm.byok_handler.get_pricing_fetcher",
            side_effect=RuntimeError("pricing down"),
        ):
            result = handler.get_provider_comparison()
        assert result["deepseek"]["tier"] == "budget"

    def test_get_cheapest_models(self):
        handler, _ = _make_handler()
        fetcher = MagicMock()
        fetcher.get_cheapest_models.return_value = [{"model_id": "m1"}]
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            assert handler.get_cheapest_models(limit=3) == [{"model_id": "m1"}]

    def test_get_cheapest_models_error(self):
        handler, _ = _make_handler()
        with patch(
            "core.llm.byok_handler.get_pricing_fetcher",
            side_effect=RuntimeError("down"),
        ):
            assert handler.get_cheapest_models() == []

    def test_classify_cognitive_tier(self):
        handler, _ = _make_handler()
        handler.cognitive_classifier = MagicMock(return_value=None)
        handler.cognitive_classifier.classify.return_value = CognitiveTier.STANDARD
        assert handler.classify_cognitive_tier("hello") == CognitiveTier.STANDARD


# =========================================================================== #
# stream_completion
# =========================================================================== #
class TestStreamCompletion:
    @pytest.mark.asyncio
    async def test_no_provider_order_raises(self):
        handler, _ = _make_handler()
        handler.clients = {}
        with pytest.raises(ValueError, match="No available providers for streaming"):
            async for _tok in handler.stream_completion([{"role": "user", "content": "hi"}], "m", "openai"):
                pass

    @pytest.mark.asyncio
    async def test_sync_client_fallback(self):
        handler, _ = _make_handler()
        handler.async_clients = {}
        handler.clients["openai"].chat.completions.create = AsyncMock(
            return_value=_stream(_chunk("Hi", None), _chunk(None, "stop"))
        )
        tokens = []
        async for tok in handler.stream_completion([{"role": "user", "content": "hi"}], "m", "openai"):
            tokens.append(tok)
        assert tokens == ["Hi"]

    @pytest.mark.asyncio
    async def test_ghost_provider_skipped(self):
        handler, _ = _make_handler()
        handler._get_provider_fallback_order = MagicMock(return_value=["ghost"])
        tokens = []
        async for tok in handler.stream_completion([{"role": "user", "content": "hi"}], "m", "openai"):
            tokens.append(tok)
        assert "[Error: All LLM providers failed" in tokens[0]

    @pytest.mark.asyncio
    async def test_fallback_provider_does_not_serve_model(self):
        handler, _ = _make_handler(clients=("openai", "anthropic"))
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            side_effect=RuntimeError("openai down")
        )
        handler.async_clients["anthropic"].chat.completions.create = AsyncMock()
        healer = MagicMock()
        healer.heal.return_value = SimpleNamespace(patched_kwargs=None, rule=None, patched_keys=[])
        with patch("core.llm.routing.request_healer.get_request_healer", return_value=healer):
            tokens = []
            async for tok in handler.stream_completion(
                [{"role": "user", "content": "hi"}], "gpt-4o", "openai"
            ):
                tokens.append(tok)
        # anthropic skipped (doesn't serve gpt-4o) -> all failed
        assert "[Error: All LLM providers failed" in tokens[0]
        assert not handler.async_clients["anthropic"].chat.completions.create.called

    @pytest.mark.asyncio
    async def test_governance_completion_tracking(self):
        handler, _ = _make_handler(clients=("openai",))
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            return_value=_stream(_chunk("Hi", None), _chunk(None, "stop"))
        )
        with patch(
            "core.agent_governance_service.AgentGovernanceService.record_outcome",
            new=AsyncMock(return_value=None),
        ):
            tokens = []
            async for tok in handler.stream_completion(
                [{"role": "user", "content": "hi"}], "m", "openai",
                agent_id="a-1", db=MagicMock(),
            ):
                tokens.append(tok)
        assert tokens == ["Hi"]

    @pytest.mark.asyncio
    async def test_governance_tracking_error_tolerated(self):
        handler, _ = _make_handler(clients=("openai",))
        db = MagicMock()
        db.commit.side_effect = [None, RuntimeError("db broken")]
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            return_value=_stream(_chunk("Hi", None), _chunk(None, "stop"))
        )
        with patch(
            "core.agent_governance_service.AgentGovernanceService.record_outcome",
            new=AsyncMock(return_value=None),
        ):
            tokens = []
            async for tok in handler.stream_completion(
                [{"role": "user", "content": "hi"}], "m", "openai",
                agent_id="a-1", db=db,
            ):
                tokens.append(tok)
        assert tokens == ["Hi"]

    @pytest.mark.asyncio
    async def test_failure_health_tracking_error(self):
        handler, _ = _make_handler(clients=("openai",))
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            side_effect=RuntimeError("stream died")
        )
        handler.health_monitor.record_call = MagicMock(side_effect=RuntimeError("monitor down"))
        healer = MagicMock()
        healer.heal.return_value = SimpleNamespace(patched_kwargs=None, rule=None, patched_keys=[])
        with patch("core.llm.routing.request_healer.get_request_healer", return_value=healer):
            tokens = []
            async for tok in handler.stream_completion(
                [{"role": "user", "content": "hi"}], "m", "openai"
            ):
                tokens.append(tok)
        assert "[Error: All LLM providers failed" in tokens[0]

    @pytest.mark.asyncio
    async def test_stream_self_heal_success(self):
        handler, _ = _make_handler(clients=("openai",))
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            side_effect=[
                RuntimeError("400 context overflow"),
                _stream(_chunk("Healed", None), _chunk(None, "stop")),
            ]
        )
        healer = MagicMock()
        healer.heal.return_value = SimpleNamespace(
            patched_kwargs={"model": "m", "max_tokens": 100},
            rule="context_overflow", patched_keys=["max_tokens"],
        )
        handler.health_monitor.record_call = MagicMock(
            side_effect=[None, RuntimeError("monitor flaky")]
        )
        with patch("core.llm.routing.request_healer.get_request_healer", return_value=healer):
            tokens = []
            async for tok in handler.stream_completion(
                [{"role": "user", "content": "hi"}], "m", "openai"
            ):
                tokens.append(tok)
        assert tokens == ["Healed"]

    @pytest.mark.asyncio
    async def test_stream_self_heal_retry_fails(self):
        handler, _ = _make_handler(clients=("openai",))
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            side_effect=[RuntimeError("400 context overflow"), RuntimeError("still 400")]
        )
        healer = MagicMock()
        healer.heal.return_value = SimpleNamespace(
            patched_kwargs={"model": "m", "max_tokens": 100},
            rule="context_overflow", patched_keys=["max_tokens"],
        )
        with patch("core.llm.routing.request_healer.get_request_healer", return_value=healer):
            tokens = []
            async for tok in handler.stream_completion(
                [{"role": "user", "content": "hi"}], "m", "openai"
            ):
                tokens.append(tok)
        assert "[Error: All LLM providers failed" in tokens[0]

    @pytest.mark.asyncio
    async def test_stream_healer_raise_tolerated(self):
        handler, _ = _make_handler(clients=("openai",))
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        with patch(
            "core.llm.routing.request_healer.get_request_healer",
            side_effect=RuntimeError("healer down"),
        ):
            tokens = []
            async for tok in handler.stream_completion(
                [{"role": "user", "content": "hi"}], "m", "openai"
            ):
                tokens.append(tok)
        assert "[Error: All LLM providers failed" in tokens[0]

    @pytest.mark.asyncio
    async def test_stream_free_to_paid_retry(self):
        handler, _ = _make_handler(clients=("opencode-go",))
        handler.async_clients["opencode-go"].chat.completions.create = AsyncMock(
            side_effect=[
                RuntimeError("Insufficient balance. Please add credits."),
                _stream(_chunk("Paid", None), _chunk(None, "stop")),
            ]
        )
        healer = MagicMock()
        healer.heal.return_value = SimpleNamespace(patched_kwargs=None, rule=None, patched_keys=[])
        handler.health_monitor.record_call = MagicMock(
            side_effect=[None, RuntimeError("monitor flaky")]
        )
        with patch("core.llm.routing.request_healer.get_request_healer", return_value=healer):
            tokens = []
            async for tok in handler.stream_completion(
                [{"role": "user", "content": "hi"}], "deepseek-v4-flash-free", "opencode-go",
                extra_kwargs={"stop": ["END"]},
            ):
                tokens.append(tok)
        assert tokens == ["Paid"]
        retry_kwargs = handler.async_clients["opencode-go"].chat.completions.create.call_args_list[1].kwargs
        assert retry_kwargs["model"] == "deepseek-v4-flash"
        assert retry_kwargs["stop"] == ["END"]

    @pytest.mark.asyncio
    async def test_stream_free_to_paid_retry_fails(self):
        handler, _ = _make_handler(clients=("opencode-go",))
        handler.async_clients["opencode-go"].chat.completions.create = AsyncMock(
            side_effect=[
                RuntimeError("Insufficient balance. Please add credits."),
                RuntimeError("CreditsError: still broke"),
            ]
        )
        healer = MagicMock()
        healer.heal.return_value = SimpleNamespace(patched_kwargs=None, rule=None, patched_keys=[])
        with patch("core.llm.routing.request_healer.get_request_healer", return_value=healer):
            tokens = []
            async for tok in handler.stream_completion(
                [{"role": "user", "content": "hi"}], "deepseek-v4-flash-free", "opencode-go"
            ):
                tokens.append(tok)
        assert "[Error: All LLM providers failed" in tokens[0]

    @pytest.mark.asyncio
    async def test_all_failed_marks_execution_failed(self):
        handler, _ = _make_handler(clients=("openai",))
        db = MagicMock()
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        healer = MagicMock()
        healer.heal.return_value = SimpleNamespace(patched_kwargs=None, rule=None, patched_keys=[])
        with patch("core.llm.routing.request_healer.get_request_healer", return_value=healer), \
             patch(
                 "core.agent_governance_service.AgentGovernanceService.record_outcome",
                 new=AsyncMock(return_value=None),
             ):
            tokens = []
            async for tok in handler.stream_completion(
                [{"role": "user", "content": "hi"}], "m", "openai",
                agent_id="a-1", db=db,
            ):
                tokens.append(tok)
        assert "[Error: All LLM providers failed" in tokens[0]
        exec_record = db.add.call_args.args[0]
        assert exec_record.status == "failed"

    @pytest.mark.asyncio
    async def test_all_failed_outcome_tracking_error(self):
        handler, _ = _make_handler(clients=("openai",))
        db = MagicMock()
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        healer = MagicMock()
        healer.heal.return_value = SimpleNamespace(patched_kwargs=None, rule=None, patched_keys=[])
        with patch("core.llm.routing.request_healer.get_request_healer", return_value=healer), \
             patch(
                 "core.agent_governance_service.AgentGovernanceService.record_outcome",
                 new=AsyncMock(side_effect=RuntimeError("gov broke")),
             ):
            tokens = []
            async for tok in handler.stream_completion(
                [{"role": "user", "content": "hi"}], "m", "openai",
                agent_id="a-1", db=db,
            ):
                tokens.append(tok)
        assert "[Error: All LLM providers failed" in tokens[0]

    @pytest.mark.asyncio
    async def test_cancelled_error_marks_execution_failed(self):
        handler, _ = _make_handler(clients=("openai",))
        db = MagicMock()
        db.commit.side_effect = RuntimeError("commit broken")
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        healer = MagicMock()
        healer.heal.return_value = SimpleNamespace(patched_kwargs=None, rule=None, patched_keys=[])
        with patch("core.llm.routing.request_healer.get_request_healer", return_value=healer), \
             patch(
                 "core.agent_governance_service.AgentGovernanceService.record_outcome",
                 new=AsyncMock(return_value=None),
             ), \
             patch("core.llm.byok_handler.logger.error", side_effect=asyncio.CancelledError()):
            with pytest.raises(asyncio.CancelledError):
                async for _tok in handler.stream_completion(
                    [{"role": "user", "content": "hi"}], "m", "openai",
                    agent_id="a-1", db=db,
                ):
                    pass


# =========================================================================== #
# chat_completion
# =========================================================================== #
class TestChatCompletion:
    def _completion_response(self, content="Hi", usage_tokens=(3, 2)):
        usage = SimpleNamespace(prompt_tokens=usage_tokens[0], completion_tokens=usage_tokens[1])
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content=content),
                finish_reason="stop",
            )],
            usage=usage,
        )

    @pytest.mark.asyncio
    async def test_trial_check_error_allows(self):
        from core.llm.byok_handler import llm_usage_tracker

        handler, _ = _make_handler(clients=("openai",))
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            return_value=self._completion_response()
        )
        with patch.object(
            llm_usage_tracker,
            "is_trial_expired",
            side_effect=RuntimeError("trial check broke"), create=True,
        ):
            result = await handler.chat_completion(
                [{"role": "user", "content": "hi"}], "m", "openai"
            )
        assert result["choices"][0]["message"]["content"] == "Hi"

    @pytest.mark.asyncio
    async def test_no_provider_order_raises(self):
        handler, _ = _make_handler(clients=("openai",))
        handler.clients = {}
        with pytest.raises(ValueError, match="No available providers for completion"):
            await handler.chat_completion([{"role": "user", "content": "hi"}], "m", "openai")

    @pytest.mark.asyncio
    async def test_fallback_provider_does_not_serve_model(self):
        handler, _ = _make_handler(clients=("openai", "anthropic"))
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            side_effect=RuntimeError("openai down")
        )
        handler.async_clients["anthropic"].chat.completions.create = AsyncMock()
        healer = MagicMock()
        healer.heal.return_value = SimpleNamespace(patched_kwargs=None, rule=None, patched_keys=[])
        with patch("core.llm.routing.request_healer.get_request_healer", return_value=healer):
            with pytest.raises(Exception, match="All 2 providers failed"):
                await handler.chat_completion(
                    [{"role": "user", "content": "hi"}], "gpt-4o", "openai"
                )
        assert not handler.async_clients["anthropic"].chat.completions.create.called

    @pytest.mark.asyncio
    async def test_cost_attribution_error_tolerated(self):
        handler, _ = _make_handler(clients=("openai",))
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            return_value=self._completion_response()
        )
        fetcher = MagicMock()
        fetcher.estimate_cost.side_effect = RuntimeError("no pricing")
        with patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            result = await handler.chat_completion(
                [{"role": "user", "content": "hi"}], "m", "openai"
            )
        assert result["usage"]["total_tokens"] == 5

    @pytest.mark.asyncio
    async def test_failure_tracking_error_tolerated(self):
        handler, _ = _make_handler(clients=("openai",))
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        handler.health_monitor.record_call = MagicMock(side_effect=RuntimeError("monitor down"))
        healer = MagicMock()
        healer.heal.return_value = SimpleNamespace(patched_kwargs=None, rule=None, patched_keys=[])
        with patch("core.llm.routing.request_healer.get_request_healer", return_value=healer):
            with pytest.raises(Exception, match="All 1 providers failed"):
                await handler.chat_completion(
                    [{"role": "user", "content": "hi"}], "m", "openai"
                )

    @pytest.mark.asyncio
    async def test_self_heal_success(self):
        handler, _ = _make_handler(clients=("openai",))
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            side_effect=[
                RuntimeError("400 context overflow"),
                self._completion_response(content="Healed", usage_tokens=(5, 4)),
            ]
        )
        healer = MagicMock()
        healer.heal.return_value = SimpleNamespace(
            patched_kwargs={"model": "m", "max_tokens": 100},
            rule="context_overflow", patched_keys=["max_tokens"],
        )
        fetcher = MagicMock()
        fetcher.estimate_cost.side_effect = RuntimeError("no pricing")
        with patch("core.llm.routing.request_healer.get_request_healer", return_value=healer), \
             patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher):
            result = await handler.chat_completion(
                [{"role": "user", "content": "hi"}], "m", "openai"
            )
        assert result["choices"][0]["message"]["content"] == "Healed"
        assert result["usage"]["total_tokens"] == 9

    @pytest.mark.asyncio
    async def test_self_heal_retry_fails(self):
        handler, _ = _make_handler(clients=("openai",))
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            side_effect=[RuntimeError("400 context overflow"), RuntimeError("still 400")]
        )
        healer = MagicMock()
        healer.heal.return_value = SimpleNamespace(
            patched_kwargs={"model": "m", "max_tokens": 100},
            rule="context_overflow", patched_keys=["max_tokens"],
        )
        with patch("core.llm.routing.request_healer.get_request_healer", return_value=healer):
            with pytest.raises(Exception, match="All 1 providers failed"):
                await handler.chat_completion(
                    [{"role": "user", "content": "hi"}], "m", "openai"
                )

    @pytest.mark.asyncio
    async def test_healer_raise_tolerated(self):
        handler, _ = _make_handler(clients=("openai",))
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        with patch(
            "core.llm.routing.request_healer.get_request_healer",
            side_effect=RuntimeError("healer down"),
        ):
            with pytest.raises(Exception, match="All 1 providers failed"):
                await handler.chat_completion(
                    [{"role": "user", "content": "hi"}], "m", "openai"
                )

    @pytest.mark.asyncio
    async def test_extra_kwargs_forwarded(self):
        handler, _ = _make_handler(clients=("openai",))
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            return_value=self._completion_response()
        )
        await handler.chat_completion(
            [{"role": "user", "content": "hi"}], "m", "openai",
            extra_kwargs={"stop": ["END"], "top_p": None},
        )
        kwargs = handler.async_clients["openai"].chat.completions.create.call_args.kwargs
        assert kwargs["stop"] == ["END"]
        assert "top_p" not in kwargs


# =========================================================================== #
# embeddings
# =========================================================================== #
class TestEmbeddings:
    @pytest.mark.asyncio
    async def test_single_no_client(self):
        handler, _ = _make_handler(clients=("openai",))
        handler.async_clients = {}
        handler.clients = {}
        with pytest.raises(ValueError, match="No client available"):
            await handler.generate_embedding("text", "m", "openai")

    @pytest.mark.asyncio
    async def test_single_unsupported_provider(self):
        handler, _ = _make_handler(clients=("openai",))
        handler.async_clients["mistral"] = MagicMock()
        with pytest.raises(ValueError, match="does not support embeddings"):
            await handler.generate_embedding("text", "m", "mistral")

    @pytest.mark.asyncio
    async def test_batch_openai(self):
        handler, _ = _make_handler(clients=("openai",))
        resp = SimpleNamespace(data=[
            SimpleNamespace(embedding=[0.1, 0.2]),
            SimpleNamespace(embedding=[0.3]),
        ])
        handler.async_clients["openai"].embeddings.create = AsyncMock(return_value=resp)
        out = await handler.generate_embeddings_batch(["a", "b"], "m", "openai")
        assert out == [[0.1, 0.2], [0.3]]

    @pytest.mark.asyncio
    async def test_batch_cohere(self):
        handler, _ = _make_handler(clients=("openai",))
        resp = SimpleNamespace(embeddings=[[0.5], [0.6]])
        handler.async_clients["cohere"] = MagicMock()
        handler.async_clients["cohere"].embed = AsyncMock(return_value=resp)
        out = await handler.generate_embeddings_batch(["a", "b"], "m", "cohere")
        assert out == [[0.5], [0.6]]

    @pytest.mark.asyncio
    async def test_batch_unsupported_provider(self):
        handler, _ = _make_handler(clients=("openai",))
        handler.async_clients["mistral"] = MagicMock()
        with pytest.raises(ValueError, match="does not support batch embeddings"):
            await handler.generate_embeddings_batch(["a"], "m", "mistral")

    @pytest.mark.asyncio
    async def test_batch_no_client(self):
        handler, _ = _make_handler(clients=("openai",))
        handler.async_clients = {}
        handler.clients = {}
        with pytest.raises(ValueError, match="No client available"):
            await handler.generate_embeddings_batch(["a"], "m", "openai")
