"""Tests for the observability tracing seam (core.observability.tracing).

Covers: span record/retrieve, bounded buffer enforcement, name_prefix
filtering, aggregation, Langfuse export skipped without keys, and export
attempted (once, failures tolerated) with keys configured.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.observability import tracing
from core.observability.tracing import (
    aggregate_spans,
    get_recent_spans,
    record_span,
)


@pytest.fixture(autouse=True)
def _clean_buffer(monkeypatch):
    tracing.clear_spans()
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    yield
    tracing.clear_spans()


def _mk_span(name, started=1.0, ended=2.0, **attributes):
    return record_span(
        trace_id=f"t-{name}",
        name=name,
        kind="test",
        attributes=attributes,
        started_at=started,
        ended_at=ended,
        status="ok",
    )


def test_record_and_retrieve_span():
    span = _mk_span("llm.gateway.request", model="gpt-4o", provider="openai")
    assert span["latency_ms"] == pytest.approx(1000.0)
    spans = get_recent_spans(limit=10)
    assert len(spans) == 1
    assert spans[0]["name"] == "llm.gateway.request"
    assert spans[0]["attributes"] == {"model": "gpt-4o", "provider": "openai"}
    assert spans[0]["status"] == "ok"


def test_get_recent_spans_newest_first_and_limit():
    for i in range(5):
        _mk_span(f"span.{i}", started=float(i), ended=float(i) + 1)
    spans = get_recent_spans(limit=3)
    assert [s["name"] for s in spans] == ["span.4", "span.3", "span.2"]


def test_bounded_buffer_enforced(monkeypatch):
    monkeypatch.setattr(tracing, "MAX_SPANS", 5)
    monkeypatch.setattr(
        tracing, "_spans", __import__("collections").deque(maxlen=5)
    )
    for i in range(10):
        _mk_span(f"span.{i}")
    spans = get_recent_spans(limit=100)
    assert len(spans) == 5
    # oldest evicted: newest 5 survive (span.9 newest-first)
    assert spans[0]["name"] == "span.9"
    assert spans[-1]["name"] == "span.5"


def test_name_prefix_filter():
    _mk_span("llm.gateway.request")
    _mk_span("oracle.verify")
    _mk_span("llm.gateway.request")
    spans = get_recent_spans(limit=10, name_prefix="llm.gateway")
    assert len(spans) == 2
    assert all(s["name"] == "llm.gateway.request" for s in spans)


def test_aggregate_counts_and_avg_latency():
    _mk_span("oracle.verify", started=0.0, ended=1.0)   # 1000 ms
    _mk_span("oracle.verify", started=0.0, ended=3.0)   # 3000 ms
    _mk_span("llm.gateway.request", started=0.0, ended=0.5)  # 500 ms
    agg = aggregate_spans(get_recent_spans(limit=100))
    assert agg["oracle.verify"]["count"] == 2
    assert agg["oracle.verify"]["avg_latency_ms"] == pytest.approx(2000.0)
    assert agg["llm.gateway.request"]["count"] == 1
    assert agg["llm.gateway.request"]["avg_latency_ms"] == pytest.approx(500.0)


def test_export_skipped_without_keys(monkeypatch):
    post = AsyncMock()
    client_ctx = MagicMock()
    client_ctx.__aenter__ = AsyncMock(return_value=MagicMock(post=post))
    monkeypatch.setattr(
        __import__("httpx", fromlist=["AsyncClient"]), "AsyncClient", MagicMock(return_value=client_ctx)
    )
    # Run in an event loop so the export path would be exercised if configured
    async def run():
        _mk_span("llm.gateway.request")

    asyncio.run(run())
    # Give any (incorrectly) scheduled task a chance to run
    asyncio.run(asyncio.sleep(0))
    assert not post.called


def test_export_attempted_once_with_keys(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    post = AsyncMock()
    client = MagicMock(post=post)
    client_ctx = MagicMock()
    client_ctx.__aenter__ = AsyncMock(return_value=client)
    client_ctx.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(
        __import__("httpx", fromlist=["AsyncClient"]), "AsyncClient", MagicMock(return_value=client_ctx)
    )

    async def run():
        _mk_span("oracle.verify")
        # Let the scheduled fire-and-forget export task run to completion.
        await asyncio.sleep(0.05)

    asyncio.run(run())
    assert post.await_count == 1
    args, kwargs = post.call_args
    url = args[0] if args else kwargs.get("url")
    assert url == "https://cloud.langfuse.com/api/public/ingestion"
    body = kwargs.get("json") or args[1]
    assert len(body["batch"]) == 2
    assert body["batch"][1]["body"]["name"] == "oracle.verify"
    assert body["batch"][1]["body"]["traceId"]


def test_export_failure_tolerated(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    # AsyncClient constructor itself raises — export must swallow it.
    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(
        __import__("httpx", fromlist=["AsyncClient"]), "AsyncClient", boom
    )
    events = tracing._langfuse_events("t", "n", "k", {}, 1.0, 2.0, "ok")
    # Should not raise
    asyncio.run(tracing._export_to_langfuse(events))
    # And recording spans still works with a broken exporter in a live loop
    async def run():
        _mk_span("oracle.verify")

    asyncio.run(run())
    assert len(get_recent_spans()) == 1


def test_custom_langfuse_host(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setenv("LANGFUSE_HOST", "https://lf.example.com/")
    post = AsyncMock()
    client = MagicMock(post=post)
    client_ctx = MagicMock()
    client_ctx.__aenter__ = AsyncMock(return_value=client)
    monkeypatch.setattr(
        __import__("httpx", fromlist=["AsyncClient"]), "AsyncClient", MagicMock(return_value=client_ctx)
    )
    asyncio.run(tracing._export_to_langfuse([{"type": "trace-create"}]))
    url = post.call_args[0][0] if post.call_args[0] else post.call_args[1].get("url")
    assert url == "https://lf.example.com/api/public/ingestion"
