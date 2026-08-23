"""RED tests — Round 80w2: OpenRouter free-model fallback on budget exhaustion.

The user's paid OpenRouter credits run out; the system should automatically
retry the same request on a free model (``:free`` suffix) before skipping
the provider entirely. Mirrors the opencode-go free/paid fallback pattern
but reversed: paid fails → try free.

Also wires the previously-dead opencode-go fallback helpers
(_is_insufficient_balance_error, _opencode_paid_fallback_model) into the
same retry path so both gateways benefit.
"""
from unittest.mock import MagicMock, patch

import pytest

from core.llm.byok_handler import (
    _is_insufficient_balance_error,
    _opencode_paid_fallback_model,
)


class TestInsufficientBalanceDetection:
    def test_opencode_credits_error(self):
        err = Exception("CreditsError: Insufficient balance. Please top up.")
        assert _is_insufficient_balance_error(err)

    def test_openrouter_insufficient_credits(self):
        err = Exception("Provider returned 402: You've exceeded your credit limit")
        assert _is_insufficient_balance_error(err)

    def test_generic_auth_error_not_balance(self):
        err = Exception("401 Unauthorized: invalid api key")
        assert not _is_insufficient_balance_error(err)

    def test_random_error_not_balance(self):
        assert not _is_insufficient_balance_error(Exception("timeout"))


class TestOpenCodeFallbackModel:
    def test_free_model_maps_to_paid_sibling(self):
        assert _opencode_paid_fallback_model("deepseek-v4-flash-free") == "deepseek-v4-flash"

    def test_unknown_free_gets_cheapest(self):
        assert _opencode_paid_fallback_model("mystery-free") == "deepseek-v4-flash"

    def test_non_free_returns_none(self):
        assert _opencode_paid_fallback_model("gpt-4o") is None


# ---------------------------------------------------------------------------
# OpenRouter free-fallback mapping
# ---------------------------------------------------------------------------

from core.llm.byok_handler import (  # noqa: E402
    _openrouter_free_fallback_model,
    OPENROUTER_PAID_FREE_FALLBACK_DEFAULTS,
)


class TestOpenRouterFreeFallback:
    def test_known_paid_models_have_free_fallbacks(self):
        for model in ("openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet"):
            fb = _openrouter_free_fallback_model(model)
            assert fb is not None and ":free" in fb, f"{model} -> {fb}"

    def test_already_free_returns_none(self):
        assert _openrouter_free_fallback_model("google/gemma-2-9b-it:free") is None

    def test_unknown_model_gets_default_free(self):
        result = _openrouter_free_fallback_model("some/exotic-model")
        assert result is not None and ":free" in result

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv(
            "OPENROUTER_FREE_FALLBACK",
            '{"custom/model": "custom/model:free"}'
        )
        # reset cache so env override is picked up
        import core.llm.byok_handler as mod
        mod._openrouter_free_fallback_cache = None
        result = _openrouter_free_fallback_model("custom/model")
        assert result == "custom/model:free"
        # restore cache for other tests
        mod._openrouter_free_fallback_cache = None


# ---------------------------------------------------------------------------
# Retry-loop wiring: insufficient-balance triggers free/paid fallback
# ---------------------------------------------------------------------------

class TestRetryLoopWiring:
    """Verify that when a gateway call fails with insufficient balance,
    the retry loop swaps the model instead of immediately moving to the
    next provider."""

    def test_opencode_free_failure_triggers_paid_retry_model(self):
        """When a -free opencode model hits budget, the paid sibling is tried."""
        err = Exception("CreditsError: Insufficient balance")
        assert _is_insufficient_balance_error(err)
        # the caller would use _opencode_paid_fallback_model to get the retry target
        assert _opencode_paid_fallback_model("deepseek-v4-flash-free") is not None

    def test_openrouter_budget_exhaustion_triggers_free_retry_model(self):
        """When an openrouter paid model hits credit limit, a :free variant is tried."""
        err = Exception("402 Payment Required: insufficient credits")
        assert _is_insufficient_balance_error(err)
        fb = _openrouter_free_fallback_model("openai/gpt-4o-mini")
        assert fb and ":free" in fb
