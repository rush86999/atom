"""Coverage wave 57 — core/llm/byok_handler.py section E: cognitive-tier + structured generation.

generate_with_cognitive_tier: budget gate, no-model gate, success (quality
assessment + no escalation), generation-failure escalation, rate-limit
escalation retry, escalation-no-fallback, max-escalations error.
generate_structured_response: trial/no-clients/no-instructor/free-tier gates,
success path, cascade on schema error.
"""
import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.llm.byok_handler import (
    AwaitableResult,
    BYOKHandler,
)


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


class _Tier:
    def __init__(self, value):
        self.value = value


class TestCognitiveTier:
    def _tier_service(self, **kw):
        ts = Mock()
        ts.select_tier.return_value = _Tier("standard")
        ts.calculate_request_cost.return_value = {"cost_cents": 50}
        ts.check_budget_constraint.return_value = True
        ts.get_optimal_model.return_value = ("deepseek", "deepseek-chat")
        ts.handle_escalation.return_value = (False, None, None)
        for k, v in kw.items():
            setattr(ts, k, v)
        return ts

    async def test_budget_exceeded(self):
        ts = self._tier_service(check_budget_constraint=lambda c: False)
        h = make_handler(tier_service=ts)
        result = await h.generate_with_cognitive_tier("prompt text here")
        assert result["error"] == "Budget exceeded"
        assert result["tier"] == "standard"

    async def test_no_models(self):
        ts = self._tier_service(get_optimal_model=lambda t, e, r: (None, None))
        h = make_handler(tier_service=ts)
        result = await h.generate_with_cognitive_tier("prompt")
        assert "No models available" in result["error"]

    async def test_success_no_escalation(self):
        ts = self._tier_service()
        h = make_handler(tier_service=ts, clients={"deepseek": 1})
        with patch.object(h, "generate_response",
                          new=AsyncMock(return_value="good answer")), \
             patch("core.llm.response_quality.assess_response_quality") as arq:
            arq.return_value = SimpleNamespace(quality_score=0.95)
            result = await h.generate_with_cognitive_tier("prompt")
        assert result["response"] == "good answer"
        assert result["tier"] == "standard"
        assert result["provider"] == "deepseek"
        assert result["escalated"] is False
        assert result["cost_cents"] == 50

    async def test_gen_failure_marker_escalates(self):
        ts = self._tier_service()
        # escalate once (with the fallback model), then accept on retry
        ts.handle_escalation.side_effect = [
            (True, SimpleNamespace(value="quality"), _Tier("versatile")),
            (False, None, None),
        ]
        h = make_handler(tier_service=ts, clients={"deepseek": 1})
        with patch.object(h, "generate_response",
                          new=AsyncMock(return_value="I'm sorry, but an error occurred")), \
             patch("core.llm.response_quality.assess_response_quality") as arq:
            arq.return_value = SimpleNamespace(quality_score=0.3)
            result = await h.generate_with_cognitive_tier("prompt")
        # escalation with no fallback model returns previous response
        assert result["response"] == "I'm sorry, but an error occurred"
        assert result["escalated"] is True

    async def test_rate_limit_exception_escalates_then_retries(self):
        ts = self._tier_service()
        # escalation True only on the exception; accept the retried response
        ts.handle_escalation.side_effect = [
            (True, SimpleNamespace(value="rate_limit"), _Tier("versatile")),
            (False, None, None),
        ]
        calls = {"n": 0}

        async def gen(**kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("rate limit exceeded")
            return "recovered answer"

        h = make_handler(tier_service=ts, clients={"deepseek": 1})
        with patch.object(h, "generate_response", new=gen):
            result = await h.generate_with_cognitive_tier("prompt")
        assert result["response"] == "recovered answer"
        assert result["escalated"] is True
        assert calls["n"] == 2

    async def test_escalation_no_fallback_error(self):
        ts = self._tier_service()
        ts.handle_escalation.return_value = (True, SimpleNamespace(value="error"), _Tier("complex"))
        ts.get_optimal_model.side_effect = [("deepseek", "deepseek-chat"), (None, None)]
        h = make_handler(tier_service=ts, clients={"deepseek": 1})
        with patch.object(h, "generate_response",
                          new=AsyncMock(side_effect=RuntimeError("rate limit hit"))):
            result = await h.generate_with_cognitive_tier("prompt")
        assert "error" in result
        assert result["escalated"] is True

    async def test_max_escalations_error(self):
        ts = self._tier_service()
        ts.handle_escalation.return_value = (True, SimpleNamespace(value="error"), _Tier("complex"))
        h = make_handler(tier_service=ts, clients={"deepseek": 1})
        with patch.object(h, "generate_response",
                          new=AsyncMock(side_effect=RuntimeError("persistent failure"))):
            result = await h.generate_with_cognitive_tier("prompt")
        assert "persistent failure" in result.get("error", "")
        assert result["escalated"] is True


class TestStructuredGates:
    async def test_trial_restricted(self):
        h = make_handler(clients={"openai": 1})
        with patch.object(h, "_is_trial_restricted", return_value=True):
            assert await h.generate_structured_response("p", "s", Mock()) is None

    async def test_no_clients(self):
        h = make_handler()
        with patch.object(h, "_is_trial_restricted", return_value=False):
            assert await h.generate_structured_response("p", "s", Mock()) is None

    async def test_no_instructor(self):
        h = make_handler(clients={"openai": 1})
        with patch.object(h, "_is_trial_restricted", return_value=False), \
             patch("core.llm.byok_handler.INSTRUCTOR_AVAILABLE", False), \
             patch("core.llm.byok_handler.get_db_session") as gds:
            db = MagicMock()
            db.__enter__.return_value = db
            db.query.return_value.filter.return_value.first.return_value = None
            gds.return_value = db
            assert await h.generate_structured_response("p", "s", Mock()) is None

    async def test_free_tier_blocked(self):
        h = make_handler(clients={"openai": 1})
        with patch.object(h, "_is_trial_restricted", return_value=False), \
             patch("core.llm.byok_handler.get_db_session") as gds:
            db = MagicMock()
            db.__enter__.return_value = db
            db.query.return_value.filter.return_value.first.return_value = None
            gds.return_value = db
            assert await h.generate_structured_response("p", "s", Mock()) is None


class TestStructuredSuccess:
    async def test_success_with_instructor(self):
        from pydantic import BaseModel

        class Model(BaseModel):
            answer: str

        h = make_handler(clients={"openai": 1, "deepseek": 1})
        client = Mock()
        h.clients["openai"] = client

        # Free-tier gate: make the DB lookups return nothing so is_managed
        # stays True and tenant_plan "free" -> blocked? No — patched below.
        with patch.object(h, "_is_trial_restricted", return_value=False), \
             patch("core.llm.byok_handler.get_db_session") as gds, \
             patch.object(h, "get_ranked_providers",
                          return_value=AwaitableResult([("openai", "gpt-4o")])), \
             patch("core.llm.byok_handler.INSTRUCTOR_AVAILABLE", True), \
             patch("core.llm.byok_handler.instructor") as instructor_mod:
            db = MagicMock()
            db.__enter__.return_value = db
            workspace = SimpleNamespace(tenant_id="t1")
            tenant = SimpleNamespace(plan_type=SimpleNamespace(value="premium"))
            db.query.return_value.filter.return_value.first.side_effect = [workspace, tenant]
            gds.return_value = db
            h.byok_manager.get_tenant_api_key.return_value = None

            instructor_client = Mock()
            instructor_client.chat.completions.create = Mock(
                return_value=Model(answer="ok"))
            instructor_mod.from_openai.return_value = instructor_client

            result = await h.generate_structured_response(
                "prompt", "system", Model)
        assert result == Model(answer="ok")


    async def test_moa_eligibility_matrix(self):
        h = make_handler()
        from core.llm.byok_handler import QueryComplexity
        assert h._moa_eligible(QueryComplexity.COMPLEX, "chat") is True
        assert h._moa_eligible(QueryComplexity.SIMPLE, "code") is True
        assert h._moa_eligible(QueryComplexity.SIMPLE, "chat") is False
        assert h._moa_eligible(QueryComplexity.ADVANCED, "chat") is True

    async def test_render_sample_variants(self):
        assert BYOKHandler._render_sample({"a": 1}) == "{'a': 1}"
        assert BYOKHandler._render_sample("plain text") == "plain text"
        assert BYOKHandler._render_sample(SimpleNamespace(model_dump=lambda: {"x": 2})) == '{"x": 2}' 

    async def test_build_moa_aggregator_prompt(self):
        prompt = BYOKHandler._build_moa_aggregator_prompt(
            "original", ["sample1", "sample2"])
        assert "sample1" in prompt
        assert "sample2" in prompt
        hi = BYOKHandler._build_moa_aggregator_prompt(
            "q", ["a"], agreement=0.9)
        assert "CONSENSUS" in hi and "Harmonize" in hi
        lo = BYOKHandler._build_moa_aggregator_prompt(
            "q", ["a"], agreement=0.3)
        assert "disagree substantially" in lo
        mid = BYOKHandler._build_moa_aggregator_prompt(
            "q", ["a"], agreement=0.6)
        assert "partially agree" in mid
