"""Embedding off the event loop (event-loop stall regression).

Three linked defects stalled every concurrent request behind sync
embedding work (observed 2026-08-31: a canvas thumbs-POST queued behind a
chat turn's first FastEmbed load and blew every axios timeout):

1. EmbeddingService ran the FastEmbed model load (multi-second blocking
   ONNX init) and inference inline inside its `async` methods — first use
   froze the entire event loop, i.e. every endpoint, for the load.
2. Each EmbeddingService instance loaded its OWN model copy; startup
   warm() only reached one of the consumers.
3. LanceDBHandler.embed_text's async-context guard probed the private
   `loop._thread_id`, which uvloop's Loop (uvicorn's default) does not
   implement — the guard degraded into "Failed to embed text (sync)"
   errors instead of its intended no-op-with-warning.

Under test: the guard's thread-local get_running_loop() semantics, worker-
thread model load/inference, and the shared per-model client.
"""
import asyncio
import sys
import threading
import types

import pytest

from core.embedding_service import EmbeddingService
from core.lancedb_handler import LanceDBHandler


# ==================== embed_text sync-shim guard ====================

class _StubEmbeddingService:
    async def generate_embedding(self, text):
        return [0.1, 0.2, 0.3]


def _handler_with_stub(tmp_path):
    handler = LanceDBHandler(
        db_path=str(tmp_path / "lance"),
        embedding_provider="fastembed",
    )
    handler.embedding_service = _StubEmbeddingService()
    return handler


async def test_embed_text_noops_on_event_loop_thread(tmp_path):
    """From inside a running loop the sync shim must return None (never
    block the loop, never raise) — async callers use async_embed_text."""
    handler = _handler_with_stub(tmp_path)
    assert handler.embed_text("query") is None


def test_embed_text_works_from_sync_context(tmp_path):
    """No running loop → the shim embeds via its own loop (thread-executor
    callers, CLI scripts, background workers)."""
    handler = _handler_with_stub(tmp_path)
    assert list(handler.embed_text("query")) == [0.1, 0.2, 0.3]


# ==================== FastEmbed off-loop + shared client ====================

class _Vec:
    def __init__(self, values):
        self._values = values

    def tolist(self):
        return list(self._values)


class _RecordingEmbedder:
    """Stands in for fastembed.TextEmbedding, recording which thread each
    construction and embed() ran on."""

    constructed = []   # (model_name, thread_id)
    embed_calls = []   # (texts, thread_id)
    _vec = [0.5, 0.25, 0.125]

    def __init__(self, model_name=None):
        self.model_name = model_name
        _RecordingEmbedder.constructed.append((model_name, threading.get_ident()))

    def embed(self, texts):
        _RecordingEmbedder.embed_calls.append((list(texts), threading.get_ident()))
        return [_Vec(_RecordingEmbedder._vec) for _ in texts]


@pytest.fixture
def fake_fastembed(monkeypatch):
    """Inject a stub `fastembed` module and isolate the shared-client cache."""
    _RecordingEmbedder.constructed.clear()
    _RecordingEmbedder.embed_calls.clear()
    EmbeddingService._FASTEMBED_CLIENTS.clear()

    module = types.ModuleType("fastembed")
    module.TextEmbedding = _RecordingEmbedder
    monkeypatch.setitem(sys.modules, "fastembed", module)

    class _StubLLMService:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr("core.embedding_service.LLMService", _StubLLMService)

    yield _RecordingEmbedder

    EmbeddingService._FASTEMBED_CLIENTS.clear()


async def test_model_load_and_inference_run_off_event_loop(fake_fastembed):
    loop_thread = threading.get_ident()
    svc = EmbeddingService(provider="fastembed", model="test/model")

    vector = await svc.generate_embedding("hello")

    assert vector == _RecordingEmbedder._vec
    # Both the ONNX init and the embed call ran in worker threads — running
    # them on the loop thread stalled every concurrent request (the bug).
    assert fake_fastembed.constructed[0][1] != loop_thread
    assert fake_fastembed.embed_calls[0][1] != loop_thread


async def test_fastembed_client_shared_across_instances(fake_fastembed):
    s1 = EmbeddingService(provider="fastembed", model="test/model")
    s2 = EmbeddingService(provider="fastembed", model="test/model")

    await s1.generate_embedding("a")
    await s2.generate_embedding("b")

    # One model load total — per-instance loading paid the multi-second ONNX
    # init once per consumer and startup warm() only covered one of them.
    assert len(fake_fastembed.constructed) == 1
    assert s1._client is not None
    assert s1._client is s2._client


async def test_batch_generation_shares_loaded_client(fake_fastembed):
    svc = EmbeddingService(provider="fastembed", model="test/model")

    vectors = await svc.generate_embeddings_batch(["a", "b"])

    assert [v == _RecordingEmbedder._vec for v in vectors] == [True, True]
    assert len(fake_fastembed.constructed) == 1
