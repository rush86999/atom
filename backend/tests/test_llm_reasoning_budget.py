"""Chat replies must pin a bounded reasoning budget on gateway models.

Live 2026-09-11: `z-ai/glm-5.3-flash` spent the whole 6000-token completion cap
on hidden reasoning and streamed zero visible content (`finish_reason=length`);
the turn died. OpenRouter's documented contract is that `max_tokens` must be
strictly greater than the reasoning budget, and its unified `reasoning` object
lets a caller bound it.

Planning already disables reasoning (`_REASONING_MANDATORY` / `disable_reasoning`);
this pins the CHAT path: a bounded budget for reasoning models on gateway
providers, no reasoning field for non-reasoning models or non-gateway providers.
"""
import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.llm import byok_handler


class _Delta(SimpleNamespace):
    pass


def _chunk(content):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=_Delta(content=content), finish_reason=None)]
    )


class _AsyncStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __aiter__(self):
        self._it = iter(self._chunks)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class _CapturingClient:
    def __init__(self):
        self.kwargs = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    async def _create(self, **kwargs):
        self.kwargs.append(kwargs)
        return _AsyncStream([_chunk("ok")])


def _build_handler(provider="openrouter", supports_reasoning=True):
    handler = byok_handler.BYOKHandler.__new__(byok_handler.BYOKHandler)
    handler.workspace_id = "ws_test"
    handler.clients = {}
    client = _CapturingClient()
    handler.async_clients = {provider: client}
    handler.env_key_providers = {provider}
    handler.health_monitor = MagicMock()
    handler._last_reasoning = None
    handler._model_supports_reasoning = lambda m: supports_reasoning
    return handler, client


def _wire(handler, provider):
    handler._get_provider_fallback_order = lambda requested: [provider]
    handler._provider_serves_model = lambda p, m: True
    handler._llm_taint_check = lambda *a, **k: None
    handler._stash_decision_features = lambda *a, **k: None
    handler._track_llm_call = lambda *a, **k: None
    handler._record_outcome_feedback = AsyncMock(return_value=None)
    handler._is_provider_available = lambda p: True


async def _drain(agen):
    return [tok async for tok in agen]


@pytest.mark.asyncio
async def test_reasoning_model_gets_bounded_budget_with_headroom():
    handler, client = _build_handler(provider="openrouter", supports_reasoning=True)
    _wire(handler, "openrouter")

    await _drain(handler.stream_completion(
        messages=[{"role": "user", "content": "hi"}],
        model="z-ai/glm-5.3-flash",
        provider_id="openrouter",
        max_tokens=6000,
    ))

    sent = client.kwargs[0]
    extra = sent.get("extra_body") or {}
    assert "reasoning" in extra, "reasoning model got no bounded reasoning budget"
    budget = extra["reasoning"]["max_tokens"]
    assert 0 < budget < sent["max_tokens"], (
        f"OpenRouter requires max_tokens > reasoning budget "
        f"(max_tokens={sent['max_tokens']}, budget={budget})"
    )


@pytest.mark.asyncio
async def test_non_reasoning_model_gets_no_reasoning_field():
    handler, client = _build_handler(provider="openrouter", supports_reasoning=False)
    _wire(handler, "openrouter")

    await _drain(handler.stream_completion(
        messages=[{"role": "user", "content": "hi"}],
        model="some/plain-model",
        provider_id="openrouter",
        max_tokens=6000,
    ))

    assert "reasoning" not in (client.kwargs[0].get("extra_body") or {})


@pytest.mark.asyncio
async def test_non_gateway_provider_gets_no_reasoning_field():
    handler, client = _build_handler(provider="openai", supports_reasoning=True)
    _wire(handler, "openai")

    await _drain(handler.stream_completion(
        messages=[{"role": "user", "content": "hi"}],
        model="gpt-x",
        provider_id="openai",
        max_tokens=6000,
    ))

    assert "reasoning" not in (client.kwargs[0].get("extra_body") or {})
