"""Embedding physical-attempt admission/settlement.

Failure-first: embedding dispatches previously hit the provider SDK with the
SDK's default retries and only an in-memory chars/4 estimate — no durable
pre-dispatch admission and no exact settlement on the TokenUsage ledger.

These controls double the underlying transport only. Each real chargeable
embedding dispatch (single and batch) must have a unique server-owned attempt
id, a conservative authorized bound before dispatch, and a durable
actual/unknown settlement after it, on the EXISTING ledger.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from tests.test_goal9_physical_attempts import (
    _attempt_rows,
    _make_handler,
    _pricing,
    _seed,
    host,
)

pytest_plugins = ("tests.test_goal9_physical_attempts",)


class _EmbeddingClient:
    """Doubled embeddings transport; records each physical call."""

    def __init__(self, script, calls):
        self._script = list(script)
        self._calls = calls
        self.embeddings = SimpleNamespace(create=self._create)

    async def _create(self, **kwargs):
        self._calls.append(kwargs)
        action = self._script.pop(0)
        if isinstance(action, Exception):
            raise action
        return action


def _embedding_response(dim=4, prompt_tokens=None):
    response = SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.1] * dim)])
    if prompt_tokens is not None:
        response.usage = SimpleNamespace(
            prompt_tokens=prompt_tokens,
            total_tokens=prompt_tokens,
        )
    return response


def _handler(monkeypatch, tmp_path, script, calls):
    return _make_handler(
        monkeypatch, tmp_path, {"openai": ["text-embedding-3-small"]},
        async_={"openai": _EmbeddingClient(script, calls)})


def test_embedding_dispatch_admits_and_settles_exact_attempt(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _pricing(monkeypatch, lambda model, i, o: float(i) * 0.000001)
    calls = []
    handler = _handler(
        monkeypatch, tmp_path,
        [_embedding_response(prompt_tokens=7)], calls)
    vector = asyncio.run(handler.generate_embedding(
        "hello", "text-embedding-3-small", provider="openai"))
    assert vector == [0.1] * 4
    assert len(calls) == 1
    rows = _attempt_rows(host)
    assert len(rows) == 1, [r.attempt_id for r in rows]
    row = rows[0]
    assert row.attempt_id and row.request_id
    assert row.provider_id == "openai"
    assert row.model_name == "text-embedding-3-small"
    assert row.workspace_id == "ws-goal9-physical"
    assert row.tenant_id == "tenant-goal9-physical"
    assert row.prompt_tokens == 7 and row.completion_tokens == 0
    assert row.billed is True
    assert row.cost_usd == pytest.approx(7 * 0.000001)
    assert row.pricing_status == "priced"
    assert row.reservation_status == "settled"


def test_embedding_without_usage_keeps_unknown_liability(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _pricing(monkeypatch, lambda model, i, o: float(i) * 0.000001)
    calls = []
    handler = _handler(monkeypatch, tmp_path, [_embedding_response()], calls)
    asyncio.run(handler.generate_embedding(
        "hello", "text-embedding-3-small", provider="openai"))
    row = _attempt_rows(host)[0]
    assert row.billed is True
    assert row.prompt_tokens == 0 and row.completion_tokens == 0
    assert row.cost_usd is None and row.pricing_status == "unknown"
    assert row.reservation_status == "uncertain"
    assert float(row.reserved_cost_usd) > 0


def test_embedding_missing_price_refuses_before_dispatch(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)  # hard_stop with a positive cap
    _pricing(monkeypatch, lambda *a, **k: None)
    calls = []
    handler = _handler(monkeypatch, tmp_path, [_embedding_response(7)], calls)
    with pytest.raises(Exception):
        asyncio.run(handler.generate_embedding(
            "hello", "controlled-unpriced-embedding", provider="openai"))
    assert calls == []
    assert _attempt_rows(host) == []


def test_embedding_batch_is_one_physical_attempt(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _pricing(monkeypatch, lambda model, i, o: float(i) * 0.000001)
    calls = []
    handler = _handler(
        monkeypatch, tmp_path, [_embedding_response(prompt_tokens=20)], calls)
    vectors = asyncio.run(handler.generate_embeddings_batch(
        ["one", "two"], "text-embedding-3-small", provider="openai"))
    assert len(vectors) == 1
    assert len(calls) == 1
    assert calls[0]["input"] == ["one", "two"]
    rows = _attempt_rows(host)
    assert len(rows) == 1
    assert rows[0].prompt_tokens == 20
    assert rows[0].reservation_status == "settled"


class _CohereEmbedClient:
    def __init__(self, response, calls):
        self._response = response
        self._calls = calls

    async def embed(self, **kwargs):
        self._calls.append(kwargs)
        return self._response


def _cohere_response(billed_tokens=None):
    response = SimpleNamespace(embeddings=[[0.2] * 3])
    if billed_tokens is not None:
        response.meta = SimpleNamespace(
            billed_units=SimpleNamespace(input_tokens=billed_tokens))
    return response


def test_cohere_embedding_settles_billed_units(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _pricing(monkeypatch, lambda model, i, o: float(i) * 0.000001)
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path, {"cohere": ["embed-english-v3.0"]},
        async_={"cohere": _CohereEmbedClient(
            _cohere_response(12), calls)})
    vector = asyncio.run(handler.generate_embedding(
        "hello", "embed-english-v3.0", provider="cohere"))
    assert vector == [0.2] * 3
    assert len(calls) == 1
    row = _attempt_rows(host)[0]
    assert row.provider_id == "cohere"
    assert row.prompt_tokens == 12
    assert row.cost_usd == pytest.approx(12 * 0.000001)
    assert row.reservation_status == "settled"


def test_cohere_embedding_without_billed_units_stays_unknown(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _pricing(monkeypatch, lambda model, i, o: float(i) * 0.000001)
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path, {"cohere": ["embed-english-v3.0"]},
        async_={"cohere": _CohereEmbedClient(
            _cohere_response(None), calls)})
    asyncio.run(handler.generate_embedding(
        "hello", "embed-english-v3.0", provider="cohere"))
    row = _attempt_rows(host)[0]
    assert row.cost_usd is None and row.pricing_status == "unknown"
    assert row.reservation_status == "uncertain"


def test_vendor_embedding_classes_disable_sdk_retries(monkeypatch):
    import core.llm.embedding.providers as providers

    seen = {"cohere": [], "voyageai": [], "nomic": []}

    class _CohereRecorder:
        def __init__(self, **kwargs):
            seen["cohere"].append(kwargs)

    class _VoyageRecorder:
        def __init__(self, **kwargs):
            seen["voyageai"].append(kwargs)

    class _NomicRecorder:
        def __init__(self, **kwargs):
            seen["nomic"].append(kwargs)

    monkeypatch.setattr(providers, "cohere", SimpleNamespace(
        AsyncClient=_CohereRecorder))
    monkeypatch.setattr(providers, "voyageai", SimpleNamespace(
        Client=_VoyageRecorder))
    monkeypatch.setattr(providers, "nomic", SimpleNamespace(
        Embedding=_NomicRecorder))

    providers.CohereEmbeddingProvider(api_key="scratch-key")
    providers.VoyageEmbeddingProvider(api_key="scratch-key")
    providers.NomicEmbeddingProvider(api_key="scratch-key")

    assert seen["cohere"][0].get("max_retries") == 0
    assert seen["voyageai"][0].get("max_retries") == 0
    # Nomic's SDK is requests-based and exposes no retry knob; no invented
    # parameter is passed (inventory note).
    assert "max_retries" not in seen["nomic"][0]


def test_embedding_provider_classes_disable_sdk_retries(monkeypatch):
    import core.llm.embedding.providers as providers

    seen = []

    class _Recorder:
        def __init__(self, **kwargs):
            seen.append(kwargs)

    monkeypatch.setattr(providers, "AsyncOpenAI", _Recorder)
    providers.OpenAIEmbeddingProvider(api_key="scratch-key")
    providers.JinaEmbeddingProvider(api_key="scratch-key")
    assert len(seen) == 2
    assert all(kwargs.get("max_retries") == 0 for kwargs in seen), seen
