"""Unit tests for BYOKHandler.chat_completion (Phase A2).

Uses a fake async client so no network/provider keys are needed.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm.byok_handler import (
    AllProvidersFailedError,
    BYOKHandler,
    GatewayBlockedError,
)


def make_handler(async_clients):
    """Build a BYOKHandler without running __init__ (heavy I/O)."""
    handler = object.__new__(BYOKHandler)
    handler.async_clients = async_clients
    handler.clients = {}
    handler.workspace_id = "ws-1"
    handler.tenant_id = "t-1"
    handler.user_id = "u-1"
    handler.health_monitor = MagicMock()
    handler.health_monitor.record_call = MagicMock()
    handler.cache_router = MagicMock()
    handler._last_used_model = None
    handler._last_used_provider = None
    handler._pending_routing_result_id = None
    handler._stash_decision_features = MagicMock(return_value="test-id")
    handler._record_outcome_feedback = AsyncMock()
    handler.byok_manager = MagicMock()
    # Provider heuristic: treat everything as serving everything.
    handler._provider_serves_model = lambda pid, model: True
    return handler


class FakeChoices:
    def __init__(self, content, finish_reason="stop"):
        self.message = MagicMock(content=content)
        self.finish_reason = finish_reason


class FakeUsage:
    prompt_tokens = 5
    completion_tokens = 3
    total_tokens = 8


class FakeResponse:
    def __init__(self, content="hi", finish_reason="stop"):
        self.choices = [FakeChoices(content, finish_reason)]
        self.usage = FakeUsage()


class FakeClient:
    """Mimics an OpenAI async client: ``chat.completions.create``."""

    def __init__(self, responses=None, excs=None):
        self._responses = list(responses or [])
        self._excs = list(excs or [])
        create = AsyncMock(side_effect=self._next)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

    def _next(self, **kwargs):
        if self._excs:
            raise self._excs.pop(0)
        if self._responses:
            return self._responses.pop(0)
        return FakeResponse()


def patch_fallback(order):
    return patch.object(
        BYOKHandler, "_get_provider_fallback_order", lambda self, p: order
    )


@pytest.mark.asyncio
async def test_full_history_preserved():
    client = FakeClient([FakeResponse("hi")])
    handler = make_handler({"openai": client})
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "first"},
        {"role": "user", "content": "second"},
    ]
    with patch_fallback(["openai"]):
        result = await handler.chat_completion(messages, "gpt-4o", "openai")
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["messages"] == messages  # full history, no flattening
    assert result["object"] == "chat.completion"
    assert result["choices"][0]["message"]["content"] == "hi"
    assert result["usage"]["total_tokens"] == 8
    assert handler._last_used_provider == "openai"
    handler.health_monitor.record_call.assert_called_once()
    handler._record_outcome_feedback.assert_awaited_once()


@pytest.mark.asyncio
async def test_fallback_across_providers():
    fail_client = FakeClient(excs=[Exception("boom")])
    ok_client = FakeClient([FakeResponse("ok")])
    handler = make_handler({"openai": fail_client, "anthropic": ok_client})
    with patch_fallback(["openai", "anthropic"]):
        result = await handler.chat_completion(
            [{"role": "user", "content": "x"}], "claude-3", "openai"
        )
    assert result["choices"][0]["message"]["content"] == "ok"
    assert handler._last_used_provider == "anthropic"


@pytest.mark.asyncio
async def test_healer_retry_on_repairable_4xx():
    client = FakeClient()
    exc = ValueError("400 schema mismatch")
    client.chat.completions.create = AsyncMock(side_effect=[exc, FakeResponse("healed")])
    handler = make_handler({"openai": client})
    heal = MagicMock()
    heal.patched_kwargs = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "x"}],
        "temperature": 0.7,
        "max_tokens": 100,
    }
    heal.rule = "test-rule"
    heal.patched_keys = ["model"]
    with patch_fallback(["openai"]), patch(
        "core.llm.routing.request_healer.get_request_healer",
        return_value=MagicMock(heal=MagicMock(return_value=heal)),
    ):
        result = await handler.chat_completion(
            [{"role": "user", "content": "x"}], "gpt-4o", "openai"
        )
    assert result["choices"][0]["message"]["content"] == "healed"
    assert client.chat.completions.create.call_count == 2


@pytest.mark.asyncio
async def test_all_failed_raises():
    client = FakeClient(excs=[Exception("boom")])
    handler = make_handler({"openai": client})
    with patch_fallback(["openai"]):
        with pytest.raises(AllProvidersFailedError):
            await handler.chat_completion(
                [{"role": "user", "content": "x"}], "gpt-4o", "openai"
            )


@pytest.mark.asyncio
async def test_budget_guard():
    handler = make_handler({"openai": FakeClient([FakeResponse("hi")])})
    with patch("core.llm.byok_handler.llm_usage_tracker") as tracker:
        tracker.is_budget_exceeded = lambda ws: True
        tracker.is_trial_expired = lambda ws: False
        with patch_fallback(["openai"]):
            with pytest.raises(GatewayBlockedError) as exc_info:
                await handler.chat_completion(
                    [{"role": "user", "content": "x"}], "gpt-4o", "openai"
                )
        assert exc_info.value.reason == "budget_exceeded"


@pytest.mark.asyncio
async def test_usage_and_health_recorded():
    client = FakeClient([FakeResponse("hi")])
    handler = make_handler({"openai": client})
    with patch("core.llm.byok_handler.llm_usage_tracker") as tracker:
        tracker.is_budget_exceeded = lambda ws: False
        tracker.is_trial_expired = lambda ws: False
        tracker.record = MagicMock()
        with patch("core.llm.byok_handler.get_pricing_fetcher") as pricing:
            pricing.return_value.estimate_cost = lambda m, i, o: 0.001
            with patch_fallback(["openai"]):
                await handler.chat_completion(
                    [{"role": "user", "content": "x"}], "gpt-4o", "openai"
                )
    tracker.record.assert_called_once()
    handler.health_monitor.record_call.assert_called_once()
