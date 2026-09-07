"""Coverage wave 27 — OpenCode Go free-usage → paid-model retry (TDD).

Per opencode.ai/docs/zen, free-usage models carry a "-free" suffix in their
gateway ID (deepseek-v4-flash-free, mimo-v2.5-free, ...) and their free
allowance can return CreditsError / "Insufficient balance" even with an
ACTIVE subscription — the paid models would complete fine. This suite drives
the retry that re-issues the SAME request on the subscription-paid fallback
model when a free-usage attempt fails with an insufficient-balance error.

- generate_response: free model fails w/ balance error → same request retried
  on paid fallback (deepseek-v4-flash-free → deepseek-v4-flash), success
- generate_response: paid retry also fails → falls through to next provider
- free-model failure with a NON-balance error → no paid retry (normal fallback)
- paid model (no "-free" suffix) failing w/ balance error → no self-retry
- paid fallback used for the same messages/temperature
"""
import asyncio
from unittest.mock import MagicMock, patch

import pytest

from core.llm.byok_handler import BYOKHandler, AwaitableResult


@pytest.fixture
def mock_byok_manager():
    """Mock BYOKManager for provider key management."""
    manager = MagicMock()
    manager.is_configured = MagicMock(return_value=True)
    manager.get_api_key = MagicMock(
        side_effect=lambda provider_id, key_name="default": {
            "opencode-go": "sk-opencode-test",
            "openai": "sk-test-openai-key-12345",
            "anthropic": "sk-ant-test-key-67890",
            "deepseek": "sk-deepseek-test-key",
        }.get(provider_id)
    )
    manager.get_tenant_api_key = manager.get_api_key
    return manager

CREDITS_ERROR = (
    "Error code: 401 - {'type': 'error', 'error': {'type': 'CreditsError', "
    "'message': 'Insufficient balance. Manage your billing at opencode.ai'}}"
)


@pytest.fixture
def handler(mock_byok_manager):
    with patch("core.llm.byok_handler.get_byok_manager", return_value=mock_byok_manager):
        h = BYOKHandler()
        h.clients = {"opencode-go": MagicMock()}
        h.get_ranked_providers = lambda *a, **k: AwaitableResult(
            [("opencode-go", "deepseek-v4-flash-free")]
        )
        yield h


def _response(content):
    r = MagicMock()
    r.choices = [MagicMock()]
    r.choices[0].message.content = content
    r.choices[0].finish_reason = "stop"
    r.usage = MagicMock()
    r.usage.prompt_tokens = 10
    r.usage.completion_tokens = 5
    return r


class TestFreeToPaidRetry:
    def test_free_model_balance_error_retries_paid(self, handler):
        client = handler.clients["opencode-go"]
        client.chat.completions.create.side_effect = [
            Exception(CREDITS_ERROR),
            _response("Paid model response"),
        ]
        result = asyncio.run(handler.generate_response(
            prompt="What is 2+2?",
            system_instruction="You are helpful",
            temperature=0.7,
        ))
        assert result == "Paid model response"
        calls = client.chat.completions.create.call_args_list
        assert len(calls) == 2
        assert calls[0].kwargs["model"] == "deepseek-v4-flash-free"
        assert calls[1].kwargs["model"] == "deepseek-v4-flash"
        assert calls[1].kwargs["messages"] == calls[0].kwargs["messages"]
        assert calls[1].kwargs["temperature"] == calls[0].kwargs["temperature"]

    def test_unlisted_free_model_falls_back_to_cheapest_paid(self, handler):
        handler.get_ranked_providers = lambda *a, **k: AwaitableResult(
            [("opencode-go", "mimo-v2.5-free")]
        )
        client = handler.clients["opencode-go"]
        client.chat.completions.create.side_effect = [
            Exception(CREDITS_ERROR),
            _response("cheapest paid"),
        ]
        result = asyncio.run(handler.generate_response(
            prompt="test",
            system_instruction="You are helpful",
        ))
        assert result == "cheapest paid"
        calls = client.chat.completions.create.call_args_list
        assert calls[0].kwargs["model"] == "mimo-v2.5-free"
        assert calls[1].kwargs["model"] == "minimax-m2.7"

    def test_free_model_balance_error_paid_also_fails(self, handler):
        """Free model hits the balance error, the paid fallback fails too, and
        the R83 free-tier walk exhausts — the handler gives up with the
        standard couldn't-generate text.

        The side_effect is a scripted FUNCTION, not a finite list: an
        exhausted MagicMock side_effect list raises StopIteration inside the
        to_thread worker, which crashes asyncio's future-chaining callback
        (set_exception forbids StopIteration) and hangs the awaiting coroutine
        forever — the 6h CI backend-tests timeout on 2026-09-05. This chain
        makes MORE calls than a two-entry list once the free-tier walk exists.
        """
        client = handler.clients["opencode-go"]
        script = [Exception(CREDITS_ERROR), Exception("paid model 500")]
        state = {"n": 0}

        def _fail_scripted(*a, **kw):
            n = state["n"]
            state["n"] += 1
            if n < len(script):
                raise script[n]
            raise Exception(f"free-tier fallback attempt {n} also failed")

        client.chat.completions.create.side_effect = _fail_scripted
        result = asyncio.run(handler.generate_response(
            prompt="test",
            system_instruction="You are helpful",
        ))
        assert "couldn't generate" in result.lower()
        models = [
            c.kwargs.get("model")
            for c in client.chat.completions.create.call_args_list
        ]
        # Balance error on the free model → one paid retry (same request),
        # then the R83 free-tier walk — never a self-retry of the paid model.
        assert models[0] == "deepseek-v4-flash-free"
        assert models[1] == "deepseek-v4-flash"
        assert len(models) > 2
        assert all(m != "deepseek-v4-flash" for m in models[2:])

    def test_free_model_non_balance_error_no_paid_retry(self, handler):
        client = handler.clients["opencode-go"]
        client.chat.completions.create.side_effect = [
            Exception("rate limit exceeded 429"),
            _response("should not happen"),
        ]
        result = asyncio.run(handler.generate_response(
            prompt="test",
            system_instruction="You are helpful",
        ))
        assert "couldn't generate" in result.lower()
        assert client.chat.completions.create.call_count == 1

    def test_paid_model_balance_error_retries_free_tier_no_self_retry(self, handler):
        """R83: an exhausted paid balance now retries the verified free tier —
        but must never re-try the SAME paid model."""
        handler.get_ranked_providers = lambda *a, **k: AwaitableResult(
            [("opencode-go", "deepseek-v4-flash")]
        )
        client = handler.clients["opencode-go"]

        def _always_credits(*a, **kw):
            raise Exception(CREDITS_ERROR)

        client.chat.completions.create.side_effect = _always_credits
        result = asyncio.run(handler.generate_response(
            prompt="test",
            system_instruction="You are helpful",
        ))
        assert "couldn't generate" in result.lower()
        calls = client.chat.completions.create.call_args_list
        models_tried = [c.kwargs.get("model") for c in calls]
        assert models_tried[0] == "deepseek-v4-flash"
        # Retries happen only on free-tier models — never a self-retry.
        assert all(m != "deepseek-v4-flash" for m in models_tried[1:])
        assert len(models_tried) > 1

    def test_paid_model_balance_error_free_tier_succeeds(self, handler):
        """Paid balance exhausted → the free tier answers the request."""
        handler.get_ranked_providers = lambda *a, **k: AwaitableResult(
            [("opencode-go", "deepseek-v4-flash")]
        )
        client = handler.clients["opencode-go"]
        client.chat.completions.create.side_effect = [
            Exception(CREDITS_ERROR),
            _response("free tier answer"),
        ]
        result = asyncio.run(handler.generate_response(
            prompt="test",
            system_instruction="You are helpful",
        ))
        assert result == "free tier answer"
        calls = client.chat.completions.create.call_args_list
        assert calls[1].kwargs["model"].endswith("-free")


class TestToThreadSafe:
    """The 2026-09-05 CI hang guard: StopIteration escaping into the executor
    future must surface as a normal error, never freeze the awaiting caller."""

    def test_stop_iteration_becomes_runtime_error(self):
        from core.llm.byok_handler import _to_thread_safe

        def _exhausted():
            raise StopIteration

        async def _run():
            return await _to_thread_safe(_exhausted)

        with pytest.raises(RuntimeError, match="StopIteration"):
            asyncio.run(_run())

    def test_passthrough_result_and_exception(self):
        from core.llm.byok_handler import _to_thread_safe

        assert asyncio.run(_to_thread_safe(lambda: "ok")) == "ok"

        def _boom():
            raise ValueError("real error")

        with pytest.raises(ValueError, match="real error"):
            asyncio.run(_to_thread_safe(_boom))
