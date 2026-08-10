"""Coverage wave 11e — generate_with_cognitive_tier, tracking helpers, monthly
quota, local-provider loading (TDD)."""
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm.byok_handler import BYOKHandler


def _make_handler():
    with patch("core.llm.byok_handler.OpenAI", return_value=MagicMock()), \
         patch("core.llm.byok_handler.AsyncOpenAI", return_value=MagicMock()), \
         patch("core.llm.byok_handler.get_db_session"):
        handler = BYOKHandler(workspace_id="default", tenant_id="default")
    handler.clients = {"openai": MagicMock()}
    handler.async_clients = {"openai": MagicMock()}
    handler.health_monitor = MagicMock()
    handler.health_monitor.health_scores = {}
    handler.byok_manager.is_configured = MagicMock(return_value=False)
    handler.byok_manager.get_api_key = MagicMock(return_value=None)
    return handler


class _Tier:
    def __init__(self, value):
        self.value = value


class _TierService:
    """Configurable fake tier service."""

    def __init__(self):
        self.tier = _Tier("standard")
        self.budget_ok = True
        self.cost_cents = 5
        self.model = ("openai", "gpt-4o-mini")
        self.escalations = []  # (current_tier, quality, error, rate_limited)
        self.escalate_times = 0  # how many escalations to allow

    def select_tier(self, prompt, task_type, user_tier_override):
        return self.tier

    def calculate_request_cost(self, prompt, tier, x):
        return {"cost_cents": self.cost_cents}

    def check_budget_constraint(self, cost_cents):
        return self.budget_ok

    def get_optimal_model(self, tier, tokens, requires_tools):
        return self.model

    def handle_escalation(self, current_tier, quality, error, rate_limited, request_id):
        self.escalations.append((current_tier, quality, error, rate_limited))
        if self.escalate_times > 0:
            self.escalate_times -= 1
            return True, _Tier("heavy"), _Tier("heavy")
        return False, None, None


# =========================================================================== #
# generate_with_cognitive_tier
# =========================================================================== #
class TestGenerateWithCognitiveTier:
    def _setup(self, response="good answer"):
        handler = _make_handler()
        ts = _TierService()
        handler.tier_service = ts
        handler.generate_response = AsyncMock(return_value=response)
        return handler, ts

    @pytest.mark.asyncio
    async def test_success_path(self):
        handler, ts = self._setup()
        result = await handler.generate_with_cognitive_tier("hi")
        assert result["response"] == "good answer"
        assert result["tier"] == "standard"
        assert result["provider"] == "openai"
        assert result["cost_cents"] == 5
        assert result["escalated"] is False

    @pytest.mark.asyncio
    async def test_budget_exceeded(self):
        handler, ts = self._setup()
        ts.budget_ok = False
        result = await handler.generate_with_cognitive_tier("hi")
        assert result["error"] == "Budget exceeded"

    @pytest.mark.asyncio
    async def test_no_models_for_tier(self):
        handler, ts = self._setup()
        ts.model = (None, None)
        result = await handler.generate_with_cognitive_tier("hi")
        assert "No models available" in result["error"]

    @pytest.mark.asyncio
    async def test_generation_failure_escalates_then_succeeds(self):
        handler, ts = self._setup(
            response="I'm sorry, I couldn't generate a response. Please check."
        )

        async def _responses(**kwargs):
            if ts.escalations:
                return "recovered answer"
            return "I'm sorry, I couldn't generate a response. Please check."

        handler.generate_response = AsyncMock(side_effect=_responses)
        ts.escalate_times = 1
        result = await handler.generate_with_cognitive_tier("hi")
        assert result["response"] == "recovered answer"
        assert result["escalated"] is True
        assert result["tier"] == "heavy"  # escalated tier is reported
        assert ts.escalations[0][2] == "generation_failed"

    @pytest.mark.asyncio
    async def test_quality_escalation_fires(self):
        handler, ts = self._setup()
        ts.escalate_times = 1

        async def _responses(**kwargs):
            if ts.escalations:
                return "better answer"
            return "low quality"

        handler.generate_response = AsyncMock(side_effect=_responses)
        with patch(
            "core.llm.response_quality.assess_response_quality",
            return_value=SimpleNamespace(quality_score=0.4),
        ):
            result = await handler.generate_with_cognitive_tier("hi")
        assert result["response"] == "better answer"
        assert result["escalated"] is True
        quality = ts.escalations[0][1]
        assert quality == 40.0

    @pytest.mark.asyncio
    async def test_exception_rate_limit_escalates(self):
        handler, ts = self._setup()

        async def _boom(**kwargs):
            if ts.escalations:
                return "retried ok"
            raise RuntimeError("rate limit exceeded")

        handler.generate_response = AsyncMock(side_effect=_boom)
        ts.escalate_times = 1
        result = await handler.generate_with_cognitive_tier("hi")
        assert result["response"] == "retried ok"
        assert ts.escalations[0][3] is True  # rate_limited flag

    @pytest.mark.asyncio
    async def test_max_escalations_returns_error(self):
        handler, ts = self._setup()

        async def _boom(**kwargs):
            raise RuntimeError("persistent failure")

        handler.generate_response = AsyncMock(side_effect=_boom)
        ts.escalate_times = 1
        result = await handler.generate_with_cognitive_tier("hi")
        assert "error" in result
        assert result["escalated"] is True


# =========================================================================== #
# Tracking helpers
# =========================================================================== #
class TestTrackingHelpers:
    def test_track_rate_usage_success(self):
        handler = _make_handler()
        handler.rate_tracker.record_usage = MagicMock()
        handler._track_rate_usage("openai", 10, 5, model_id="gpt-4o-mini")
        handler.rate_tracker.record_usage.assert_called_once_with(
            "openai", 10, 5, model_id="gpt-4o-mini"
        )

    def test_track_rate_usage_error_tolerated(self):
        handler = _make_handler()
        handler.rate_tracker.record_usage = MagicMock(
            side_effect=RuntimeError("boom")
        )
        handler._track_rate_usage("openai", 1, 1)  # must not raise

    def test_track_llm_call_success(self):
        handler = _make_handler()
        tracker = MagicMock()
        with patch("core.llm.byok_handler.get_llm_call_tracker", return_value=tracker):
            handler._track_llm_call(
                "openai", "gpt-4o-mini", True, latency_ms=12.0,
                fallback=True, fallback_provider="anthropic",
            )
        tracker.record.assert_called_once()
        kwargs = tracker.record.call_args.kwargs
        assert kwargs["provider"] == "openai"
        assert kwargs["fallback"] is True

    def test_track_llm_call_error_tolerated(self):
        handler = _make_handler()
        tracker = MagicMock()
        tracker.record.side_effect = RuntimeError("boom")
        with patch("core.llm.byok_handler.get_llm_call_tracker", return_value=tracker):
            handler._track_llm_call("openai", "m", False, error="x")  # no raise


# =========================================================================== #
# Monthly quota
# =========================================================================== #
class TestMonthlyQuota:
    def test_tpm_limit_unset(self):
        handler = _make_handler()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENCODE_MONTHLY_TPM", None)
            assert handler._monthly_tpm_limit() is None

    def test_tpm_limit_valid(self):
        handler = _make_handler()
        with patch.dict(os.environ, {"OPENCODE_MONTHLY_TPM": "500000"}):
            assert handler._monthly_tpm_limit() == 500000

    def test_tpm_limit_invalid(self):
        handler = _make_handler()
        with patch.dict(os.environ, {"OPENCODE_MONTHLY_TPM": "not-a-number"}):
            assert handler._monthly_tpm_limit() is None

    def test_budget_exhausted_true(self):
        handler = _make_handler()
        handler.rate_tracker.get_monthly_usage = MagicMock(
            return_value={"total_tokens": 600}
        )
        assert handler._monthly_budget_exhausted("openai", 500) is True

    def test_budget_not_exhausted(self):
        handler = _make_handler()
        handler.rate_tracker.get_monthly_usage = MagicMock(
            return_value={"total_tokens": 400}
        )
        assert handler._monthly_budget_exhausted("openai", 500) is False

    def test_budget_no_history_fails_open(self):
        handler = _make_handler()
        handler.rate_tracker.get_monthly_usage = MagicMock(return_value=None)
        assert handler._monthly_budget_exhausted("openai", 500) is False

    def test_budget_error_fails_open(self):
        handler = _make_handler()
        handler.rate_tracker.get_monthly_usage = MagicMock(
            side_effect=RuntimeError("db down")
        )
        assert handler._monthly_budget_exhausted("openai", 500) is False


# =========================================================================== #
# Model capability helpers
# =========================================================================== #
class TestModelCapabilities2:
    def test_model_supports_reasoning(self):
        handler = _make_handler()
        handler.pricing_fetcher = MagicMock()
        handler.pricing_fetcher.get_model_capabilities.return_value = {
            "supports_reasoning": True
        }
        assert handler._model_supports_reasoning("o3") is True
        handler.pricing_fetcher.get_model_capabilities.return_value = {
            "supports_reasoning": False
        }
        assert handler._model_supports_reasoning("o3") is False


# =========================================================================== #
# Local provider loading
# =========================================================================== #
class TestLocalProviderLoading:
    def test_loads_local_providers(self):
        handler = _make_handler()

        provider = SimpleNamespace(
            id="p1", name="ollama-local", provider_type="ollama",
            api_key=None, base_url="http://localhost:11434/v1",
            workspace_id="default",
        )
        cap = SimpleNamespace(
            provider_id="p1", model_id="llama3:8b", context_window=8192,
            supports_tools=True, supports_vision=False, supports_reasoning=False,
            quality_score=0.6,
        )

        def _query(model):
            q = MagicMock()
            if model.__name__ == "LocalModelProvider":
                q.filter.return_value.all.return_value = [provider]
            else:
                q.filter.return_value.all.return_value = [cap]
            return q

        session = MagicMock()
        session.query.side_effect = _query
        ctx = MagicMock()
        ctx.__enter__.return_value = session
        ctx.__exit__.return_value = False

        fetcher = MagicMock()
        fetcher.pricing_cache = {}

        mock_openai = MagicMock()
        mock_async = MagicMock()
        with patch("core.database.get_db_session", return_value=ctx), \
             patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher), \
             patch("core.llm.byok_handler.OpenAI", return_value=mock_openai), \
             patch("core.llm.byok_handler.AsyncOpenAI", return_value=mock_async):
            handler._load_local_providers()

        assert "local_p1" in handler.clients
        assert "local_p1" in handler.async_clients
        assert "llama3:8b" in fetcher.pricing_cache
        assert fetcher.pricing_cache["llama3:8b"]["supports_tools"] is True

    def test_no_providers_is_noop(self):
        handler = _make_handler()

        def _query(model):
            q = MagicMock()
            q.filter.return_value.all.return_value = []
            return q

        session = MagicMock()
        session.query.side_effect = _query
        ctx = MagicMock()
        ctx.__enter__.return_value = session
        ctx.__exit__.return_value = False

        with patch("core.database.get_db_session", return_value=ctx), \
             patch("core.llm.byok_handler.get_pricing_fetcher", return_value=MagicMock()):
            handler._load_local_providers()
        assert "local_p1" not in handler.clients

    def test_provider_without_caps_gets_generic_entry(self):
        handler = _make_handler()

        provider = SimpleNamespace(
            id="p2", name="lm-studio", provider_type="openai",
            api_key=None, base_url="http://localhost:1234/v1",
            workspace_id="default",
        )

        def _query(model):
            q = MagicMock()
            if model.__name__ == "LocalModelProvider":
                q.filter.return_value.all.return_value = [provider]
            else:
                q.filter.return_value.all.return_value = []
            return q

        session = MagicMock()
        session.query.side_effect = _query
        ctx = MagicMock()
        ctx.__enter__.return_value = session
        ctx.__exit__.return_value = False

        fetcher = MagicMock()
        fetcher.pricing_cache = {}

        with patch("core.database.get_db_session", return_value=ctx), \
             patch("core.llm.byok_handler.get_pricing_fetcher", return_value=fetcher), \
             patch("core.llm.byok_handler.OpenAI", return_value=MagicMock()), \
             patch("core.llm.byok_handler.AsyncOpenAI", return_value=MagicMock()):
            handler._load_local_providers()

        assert "openai_default" in fetcher.pricing_cache
        assert fetcher.pricing_cache["openai_default"]["supports_vision"] is False

    def test_db_error_is_noop(self):
        handler = _make_handler()
        with patch(
            "core.database.get_db_session",
            side_effect=RuntimeError("db down"),
        ):
            handler._load_local_providers()  # must not raise
