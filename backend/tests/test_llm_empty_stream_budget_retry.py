"""A reasoning-only empty stream must retry the SAME provider with a bigger
budget before the turn is declared dead.

Live 2026-09-11 (Sales Agent canvas turn): OpenRouter streamed zero visible
content for ``z-ai/glm-5.3-flash`` with ``finish_reason=length`` on the
agent-sized prompt, while the SAME model answered fine on a direct
non-streamed call. The provider was healthy — the 6000-token budget was
consumed by hidden reasoning. Because only one real provider is configured,
the provider-fallback loop had nothing left and the turn died with
"All 2 providers failed", so the agent could not work at all.
"""
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.llm import byok_handler


class _Delta(SimpleNamespace):
    pass


def _chunk(content):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=_Delta(content=content), finish_reason=None)]
    )


def _finish_chunk(reason):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=_Delta(content=None), finish_reason=reason)]
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


class _BudgetAwareClient:
    """Empty (reasoning-only) when under-budgeted, content when retried big."""

    def __init__(self, small_budget):
        self.small_budget = small_budget
        self.budgets = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    async def _create(self, **kwargs):
        self.budgets.append(kwargs.get("max_tokens"))
        if kwargs.get("max_tokens") == self.small_budget:
            return _AsyncStream([_finish_chunk("length")])
        return _AsyncStream([_chunk("Hello"), _chunk(" world")])


def _build_handler(provider, chunks_client):
    handler = byok_handler.BYOKHandler.__new__(byok_handler.BYOKHandler)
    handler.workspace_id = "ws_test"
    handler.clients = {}
    handler.async_clients = {provider: chunks_client}
    handler.env_key_providers = {provider}
    handler.health_monitor = MagicMock()
    handler._last_reasoning = None
    return handler


async def _drain(agen):
    return [tok async for tok in agen]


@pytest.mark.asyncio
async def test_reasoning_only_empty_stream_retries_with_larger_budget(monkeypatch):
    client = _BudgetAwareClient(small_budget=1000)
    handler = _build_handler("openai", client)

    monkeypatch.setattr(
        handler, "_get_provider_fallback_order", lambda requested: ["openai"]
    )
    monkeypatch.setattr(handler, "_provider_serves_model", lambda p, m: True)
    monkeypatch.setattr(handler, "_llm_taint_check", lambda *a, **k: None)
    monkeypatch.setattr(handler, "_stash_decision_features", lambda *a, **k: None)
    monkeypatch.setattr(handler, "_track_llm_call", lambda *a, **k: None)
    monkeypatch.setattr(
        handler, "_record_outcome_feedback", AsyncMock(return_value=None)
    )

    tokens = await _drain(handler.stream_completion(
        messages=[{"role": "user", "content": "hi"}],
        model="m",
        provider_id="openai",
        max_tokens=1000,
    ))

    assert "".join(tokens) == "Hello world"
    # First attempt at the requested budget, then ONE larger retry.
    assert client.budgets[0] == 1000
    assert len(client.budgets) == 2
    assert client.budgets[1] > 1000


@pytest.mark.asyncio
async def test_non_length_empty_stream_does_not_retry_same_provider(monkeypatch):
    """Only a LENGTH stop (reasoning ate the budget) earns the bigger retry —
    a genuinely silent provider must fall through as before."""

    class _Silent:
        def __init__(self):
            self.calls = 0
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=self._create)
            )

        async def _create(self, **kwargs):
            self.calls += 1
            return _AsyncStream([])

    client = _Silent()
    handler = _build_handler("openai", client)
    monkeypatch.setattr(
        handler, "_get_provider_fallback_order", lambda requested: ["openai"]
    )
    monkeypatch.setattr(handler, "_provider_serves_model", lambda p, m: True)
    monkeypatch.setattr(handler, "_llm_taint_check", lambda *a, **k: None)
    monkeypatch.setattr(handler, "_stash_decision_features", lambda *a, **k: None)
    monkeypatch.setattr(handler, "_track_llm_call", lambda *a, **k: None)
    monkeypatch.setattr(
        handler, "_record_outcome_feedback", AsyncMock(return_value=None)
    )

    tokens = await _drain(handler.stream_completion(
        messages=[{"role": "user", "content": "hi"}],
        model="m",
        provider_id="openai",
        max_tokens=1000,
    ))

    assert client.calls == 1, "no same-provider budget retry without finish_reason=length"
    assert any("[Error:" in t for t in tokens)
