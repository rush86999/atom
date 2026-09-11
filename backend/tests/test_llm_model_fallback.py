"""Model-level fallback: when every provider for the chosen MODEL fails, the
next ranked MODEL must serve the turn.

Live 2026-09-11: BPC picked `z-ai/glm-5.3-flash`; its only provider streamed
empty, the fallback provider list was exhausted, and the turn died. Mature
gateways fall back across a *model group* (LiteLLM `fallbacks=[{model: [..]}]`,
OpenRouter `models: [...]`), not just across providers of one model.
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


def _empty_length_chunk():
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=_Delta(content=None), finish_reason="length")]
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


class _PerModelClient:
    def __init__(self):
        self.models = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    async def _create(self, **kwargs):
        self.models.append(kwargs.get("model"))
        if kwargs.get("model") == "primary/bad":
            return _AsyncStream([_empty_length_chunk()])
        return _AsyncStream([_chunk("fallback"), _chunk(" answer")])


def _handler(client):
    handler = byok_handler.BYOKHandler.__new__(byok_handler.BYOKHandler)
    handler.workspace_id = "ws_test"
    handler.clients = {}
    handler.async_clients = {"openrouter": client}
    handler.env_key_providers = {"openrouter"}
    handler.health_monitor = MagicMock()
    handler._last_reasoning = None
    handler._model_supports_reasoning = lambda m: False
    handler._get_provider_fallback_order = lambda requested: ["openrouter"]
    handler._provider_serves_model = lambda p, m: True
    handler._llm_taint_check = lambda *a, **k: None
    handler._stash_decision_features = lambda *a, **k: None
    handler._track_llm_call = lambda *a, **k: None
    handler._record_outcome_feedback = AsyncMock(return_value=None)
    handler._is_provider_available = lambda p: True
    return handler


async def _drain(agen):
    return [tok async for tok in agen]


@pytest.mark.asyncio
async def test_next_ranked_model_serves_when_primary_model_exhausts(monkeypatch):
    monkeypatch.setenv("ATOM_STREAM_IDLE_TIMEOUT_SECONDS", "0")  # disabled here
    client = _PerModelClient()
    handler = _handler(client)

    tokens = await _drain(handler.stream_completion(
        messages=[{"role": "user", "content": "hi"}],
        model="primary/bad",
        provider_id="openrouter",
        max_tokens=1000,
        fallback_models=["secondary/good"],
    ))

    assert "".join(tokens) == "fallback answer"
    assert "secondary/good" in client.models, (
        f"fallback model was never tried (tried: {client.models})"
    )


@pytest.mark.asyncio
async def test_no_model_fallback_without_the_list(monkeypatch):
    monkeypatch.setenv("ATOM_STREAM_IDLE_TIMEOUT_SECONDS", "0")
    client = _PerModelClient()
    handler = _handler(client)

    tokens = await _drain(handler.stream_completion(
        messages=[{"role": "user", "content": "hi"}],
        model="primary/bad",
        provider_id="openrouter",
        max_tokens=1000,
    ))

    assert any("[Error:" in t for t in tokens)
    assert "secondary/good" not in client.models
