"""P1.4/P1.5 — bench an unusable (provider, model) pair and teach the router.

A model can be HTTP-healthy yet unusable (empty / reasoning-starved / silent
output). Provider-level health cannot see that, so BPC keeps re-picking it.
Contract: after empty/inactive output survives the budget retry, the pair is
benched for a cooldown AND the empty outcome is recorded as a FAILURE for the
learning router (previously only the success path recorded feedback, so empty
streams never taught the predictors).
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


class _AlwaysEmptyClient:
    def __init__(self):
        self.calls = 0
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    async def _create(self, **kwargs):
        self.calls += 1
        return _AsyncStream([_empty_length_chunk()])


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
async def test_empty_output_benches_pair_and_records_failure(monkeypatch):
    monkeypatch.setenv("ATOM_STREAM_IDLE_TIMEOUT_SECONDS", "0")
    client = _AlwaysEmptyClient()
    handler = _handler(client)
    feedback = handler._record_outcome_feedback

    tokens = await _drain(handler.stream_completion(
        messages=[{"role": "user", "content": "hi"}],
        model="z-ai/glm-5.3-flash",
        provider_id="openrouter",
        max_tokens=1000,
    ))

    # Initial attempt + the reasoning-budget retry, then it gives up.
    assert client.calls == 2
    assert any("[Error:" in t for t in tokens)

    # P1.5: the empty outcome is recorded as a FAILURE (not a silent success).
    failure_calls = [
        c for c in feedback.call_args_list if c.kwargs.get("success") is False
    ]
    assert failure_calls, "empty stream did not record a failure outcome"

    # P1.4: the pair is benched…
    assert handler._model_cooldown_active(
        "openrouter", "z-ai/glm-5.3-flash") is True

    # …and a subsequent call skips it before touching the provider.
    calls_before = client.calls
    tokens2 = await _drain(handler.stream_completion(
        messages=[{"role": "user", "content": "hi again"}],
        model="z-ai/glm-5.3-flash",
        provider_id="openrouter",
        max_tokens=1000,
    ))
    assert client.calls == calls_before, "benched pair was tried again"
    assert any("[Error:" in t for t in tokens2)
