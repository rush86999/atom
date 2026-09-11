"""P2 hardening tests: canvas-context elision and error-class fallbacks.

  * canvas context must keep the END of a long draft (the alternative-machine
    row sat past a 4000-char head cut, so the agent told the operator the draft
    had no alternative — live 2026-09-11);
  * a context-window (or content-policy) error fails on EVERY provider of the
    model, so the turn must jump straight to the model-level fallback instead of
    re-trying the same model on the next provider.
"""
import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.llm import byok_handler
from integrations.chat_orchestrator import _elide_middle


# ── canvas-context elision ───────────────────────────────────────────────

def test_short_canvas_text_is_unchanged():
    assert _elide_middle("hello", 100) == "hello"
    assert _elide_middle("", 100) == ""


def test_long_canvas_text_keeps_head_and_tail():
    body = "HEAD-" + ("x" * 20000) + "-TAIL-$7,519.00"
    out = _elide_middle(body, 1000)
    assert out.startswith("HEAD-")
    assert "$7,519.00" in out, "the draft's tail was cut off again"
    assert "elided" in out
    assert len(out) <= 1000 + 60  # marker slack


# ── context-window error → model-level fallback ──────────────────────────

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


class _ContextErrorClient:
    """Raises a context-window error for the primary model, serves the fallback."""

    def __init__(self, primary_model):
        self.primary_model = primary_model
        self.calls = 0
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    async def _create(self, **kwargs):
        self.calls += 1
        if kwargs.get("model") == self.primary_model:
            raise RuntimeError(
                "This model's maximum context length is 8192 tokens, however "
                "you requested 9900 tokens")
        return _AsyncStream([_chunk("served-by-fallback-model")])


class _NeverClient:
    def __init__(self):
        self.calls = 0
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    async def _create(self, **kwargs):
        self.calls += 1
        return _AsyncStream([_chunk("should-not-be-used")])


def _handler(clients):
    handler = byok_handler.BYOKHandler.__new__(byok_handler.BYOKHandler)
    handler.workspace_id = "ws_test"
    handler.clients = {}
    handler.async_clients = dict(clients)
    handler.env_key_providers = set(clients)
    handler.health_monitor = MagicMock()
    handler._last_reasoning = None
    handler._model_supports_reasoning = lambda m: False
    handler._get_provider_fallback_order = lambda requested: list(clients)
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
async def test_context_error_skips_same_model_providers_for_model_fallback(monkeypatch):
    monkeypatch.setenv("ATOM_STREAM_IDLE_TIMEOUT_SECONDS", "0")
    p1 = _ContextErrorClient(primary_model="m1")
    p2 = _NeverClient()
    handler = _handler({"p1": p1, "p2": p2})

    tokens = await _drain(handler.stream_completion(
        messages=[{"role": "user", "content": "hi"}],
        model="m1",
        provider_id="p1",
        max_tokens=1000,
        fallback_models=["m2"],
    ))

    assert "".join(tokens) == "served-by-fallback-model"
    assert p2.calls == 0, (
        "a context-window error must not re-try the same model on the next "
        "provider — it fails on all of them"
    )
