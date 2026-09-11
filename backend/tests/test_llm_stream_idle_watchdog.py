"""A 200-then-silent stream must be bounded, and a partial answer never replayed.

Live pattern (Qwen Code incident, and Atom's own empty-stream class): the SDK's
request-level timeout covers connect + getting the response object, but once a
stream is open, inter-chunk silence is unbounded. Atom's only bound was the 95s
turn budget.

Contract pinned here:
  * silence before the FIRST chunk → the attempt fails so the next provider/model
    can serve the turn (never a silent success);
  * silence AFTER at least one chunk → the partial answer is kept and the stream
    ends; the request is NOT re-issued (that would duplicate visible content).
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


class _HangingStream:
    """Yields any prefetched chunks, then hangs forever on the next read."""

    def __init__(self, chunks=()):
        self._chunks = list(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._chunks:
            return self._chunks.pop(0)
        await asyncio.sleep(3600)
        raise StopAsyncIteration


class _HangingClient:
    def __init__(self, chunks=()):
        self._chunks = list(chunks)
        self.create_calls = 0
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    async def _create(self, **kwargs):
        self.create_calls += 1
        return _HangingStream(self._chunks)


def _build_handler(client):
    handler = byok_handler.BYOKHandler.__new__(byok_handler.BYOKHandler)
    handler.workspace_id = "ws_test"
    handler.clients = {}
    handler.async_clients = {"openai": client}
    handler.env_key_providers = {"openai"}
    handler.health_monitor = MagicMock()
    handler._last_reasoning = None
    handler._model_supports_reasoning = lambda m: False
    handler._get_provider_fallback_order = lambda requested: ["openai"]
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
async def test_silent_first_chunk_fails_fast(monkeypatch):
    monkeypatch.setenv("ATOM_STREAM_IDLE_TIMEOUT_SECONDS", "0.05")
    client = _HangingClient(chunks=[])
    handler = _build_handler(client)

    t0 = asyncio.get_event_loop().time()
    tokens = await asyncio.wait_for(_drain(handler.stream_completion(
        messages=[{"role": "user", "content": "hi"}],
        model="m",
        provider_id="openai",
        max_tokens=1000,
    )), timeout=5)
    elapsed = asyncio.get_event_loop().time() - t0

    assert elapsed < 4, "silent stream was not bounded by the idle watchdog"
    assert any("[Error:" in t for t in tokens), (
        f"silent stream must not look like a success: {tokens!r}"
    )


@pytest.mark.asyncio
async def test_mid_stream_silence_keeps_partial_and_never_replays(monkeypatch):
    monkeypatch.setenv("ATOM_STREAM_IDLE_TIMEOUT_SECONDS", "0.05")
    client = _HangingClient(chunks=[_chunk("Hello")])
    handler = _build_handler(client)

    tokens = await asyncio.wait_for(_drain(handler.stream_completion(
        messages=[{"role": "user", "content": "hi"}],
        model="m",
        provider_id="openai",
        max_tokens=1000,
    )), timeout=5)

    assert tokens == ["Hello"], f"partial answer was altered/duplicated: {tokens!r}"
    assert client.create_calls == 1, "a mid-stream stall must not re-issue the request"
