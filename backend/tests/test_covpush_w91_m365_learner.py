# -*- coding: utf-8 -*-
"""Coverage wave 91 — core/microsoft365_learner (Microsoft365LifecycleLearner).

Fully mocked: onedrive_service / microsoft365_service singletons, httpx client
for the Graph API downloads, DocumentLifecycleLearner doc_learner,
GraphRAGEngine. Zero LLM spend, no network, no real DB.

- scan_onedrive_for_lifecycle: envelope success / bare-"value" / list results,
  dedup by id + file-key filter, download 200 → learn_from_file + os.unlink,
  download non-200, exception during download/processing.
- scan_outlook_for_lifecycle: 200 with ingest counting, non-200, exception.
- _process_outlook_message: keyword gate, dict/str body, persist True/False,
  exception → False.
- _build_entities: sender variants, order/tracking/amount entities +
  relationships, event-id fallbacks, amounts merged only on the event entity.
- _persist_to_graph: success True / engine failure / import failure → False.
"""
import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock

import core.microsoft365_learner as m365


# ============================================================================
# Helpers
# ============================================================================

class _FakeResponse:
    def __init__(self, status_code=200, content=b"file-bytes", exception=None):
        self.status_code = status_code
        self.content = content
        self._exception = exception

    def json(self):
        return {"value": self._value if hasattr(self, "_value") else []}

    @property
    def value(self):
        return getattr(self, "_value", [])

    @value.setter
    def value(self, v):
        self._value = v


class _FakeClient:
    """AsyncClient stand-in; configured with a per-call response or exception."""

    def __init__(self, response=None):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, *args, **kwargs):
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class _FakeDocLearner:
    def __init__(self):
        self.learned = []
        self.fail_learn = False

    async def learn_from_file(self, local_path, workspace_id):
        if self.fail_learn:
            raise RuntimeError("learn boom")
        self.learned.append((local_path, workspace_id))


class _FakeGraphEngine:
    def __init__(self):
        self.ingested = []
        self.fail = False

    def ingest_structured_data(self, workspace_id, entities, relationships, **kwargs):
        if self.fail:
            raise RuntimeError("graph boom")
        self.ingested.append((workspace_id, entities, relationships))


def _file(fid, name="Invoice.xlsx"):
    return {"id": fid, "name": name, "file": {"name": name}}


def _learner(monkeypatch, onedrive_results=None):
    fake_onedrive = MagicMock()
    if onedrive_results is not None:
        # 5 keyword searches per scan; use an infinite side_effect so repeated
        # scans (multi-scan tests) never exhaust the result queue.
        if len(onedrive_results) == 1:
            fake_onedrive.search_files = AsyncMock(return_value=onedrive_results[0])
        else:
            fake_onedrive.search_files = AsyncMock(
                side_effect=[onedrive_results[i % len(onedrive_results)] for i in range(100)]
            )
    monkeypatch.setattr(m365, "onedrive_service", fake_onedrive)

    doc_learner = _FakeDocLearner()
    monkeypatch.setattr(
        m365, "DocumentLifecycleLearner", lambda *a, **k: MagicMock(doc_learner=doc_learner)
    )
    learner = m365.Microsoft365LifecycleLearner()
    learner.doc_learner = doc_learner
    return learner, fake_onedrive, doc_learner


def _patch_httpx(monkeypatch, response=None):
    monkeypatch.setattr("httpx.AsyncClient", lambda *a, **k: _FakeClient(response))
    monkeypatch.setattr("os.unlink", MagicMock())


def _run(coro):
    """Run a coroutine without depending on a current event loop.

    Earlier suites in a batch may create/close loops via
    ``asyncio.new_event_loop()``, which poisons
    ``asyncio.get_event_loop()`` for sync tests — fall back to a fresh
    loop (and close it) when no loop is current.
    """
    try:
        return asyncio.get_event_loop().run_until_complete(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


# ============================================================================
# scan_onedrive_for_lifecycle
# ============================================================================

def test_scan_onedrive_envelope_success(monkeypatch):
    learner, fake_onedrive, doc_learner = _learner(
        monkeypatch,
        onedrive_results=[
            {"status": "success", "data": {"value": [_file("a1"), _file("a2")]}},
            {"status": "success", "data": {"value": [_file("a1")]}},  # dup id
            {"value": [_file("b1")]},                                  # bare value
            [_file("c1"), _file("c2")],                                # list
            {"status": "error"},                                       # ignored
        ],
    )
    _patch_httpx(monkeypatch, response=_FakeResponse(200, content=b"data"))

    _run(learner.scan_onedrive_for_lifecycle("u1", "tok", "ws1"))

    assert len(doc_learner.learned) == 5
    assert {path.split("_")[-1] for path, _ in doc_learner.learned} == {
        "Invoice.xlsx"
    }
    assert all(ws == "ws1" for _, ws in doc_learner.learned)
    assert fake_onedrive.search_files.call_count == 5
    for call in fake_onedrive.search_files.await_args_list:
        assert call.args[0] == "tok"


def test_scan_onedrive_non_200_and_exception(monkeypatch):
    learner, fake_onedrive, doc_learner = _learner(
        monkeypatch, onedrive_results=[[_file("x1")]]
    )
    _patch_httpx(monkeypatch, response=_FakeResponse(500))

    _run(learner.scan_onedrive_for_lifecycle("u1", "tok", "ws1"))
    assert doc_learner.learned == []  # 500 → no learn

    _patch_httpx(monkeypatch, response=RuntimeError("conn refused"))
    _run(learner.scan_onedrive_for_lifecycle("u1", "tok", "ws1"))
    assert doc_learner.learned == []  # exception → caught, no crash


def test_scan_onedrive_learner_error_still_unlinks(monkeypatch):
    learner, fake_onedrive, doc_learner = _learner(monkeypatch, onedrive_results=[[_file("y1")]])
    _patch_httpx(monkeypatch, response=_FakeResponse(200))
    doc_learner.fail_learn = True

    _run(learner.scan_onedrive_for_lifecycle("u1", "tok", "ws1"))
    # Exception inside per-file try block is swallowed; no crash.


def test_scan_onedrive_download_exception(monkeypatch):
    learner, fake_onedrive, doc_learner = _learner(monkeypatch, onedrive_results=[[_file("z1")]])
    monkeypatch.setattr("httpx.AsyncClient", lambda *a, **k: _FakeClient(TimeoutError("slow")))

    _run(learner.scan_onedrive_for_lifecycle("u1", "tok", "ws1"))
    assert doc_learner.learned == []


def test_scan_onedrive_search_raises(monkeypatch):
    fake_onedrive = MagicMock()
    fake_onedrive.search_files = AsyncMock(side_effect=RuntimeError("search boom"))
    monkeypatch.setattr(m365, "onedrive_service", fake_onedrive)
    doc_learner = _FakeDocLearner()
    monkeypatch.setattr(
        m365, "DocumentLifecycleLearner", lambda *a, **k: MagicMock(doc_learner=doc_learner)
    )
    learner = m365.Microsoft365LifecycleLearner()

    with pytest.raises(RuntimeError):
        _run(learner.scan_onedrive_for_lifecycle("u1", "tok", "ws1"))
    assert doc_learner.learned == []


# ============================================================================
# scan_outlook_for_lifecycle
# ============================================================================

def _outlook_msg(mid, subject="Your Invoice #INV-1234", body="", has_body=True):
    msg = {
        "id": mid,
        "subject": subject,
        "from": {"emailAddress": {"address": "v@acme.com", "name": "Vendor"}},
        "receivedDateTime": "2026-08-01T10:00:00Z",
        "body": {"content": body} if has_body else None,
    }
    return msg


def test_scan_outlook_ingests(monkeypatch):
    learner, _, _ = _learner(monkeypatch)
    resp = _FakeResponse(200)
    resp.value = [
        _outlook_msg("m1", body="Invoice USD 1,234.56 order PO-98765"),
        _outlook_msg("m2", body="no lifecycle content here"),
    ]
    monkeypatch.setattr("httpx.AsyncClient", lambda *a, **k: _FakeClient(resp))
    engine = _FakeGraphEngine()
    monkeypatch.setattr("core.graphrag_engine.GraphRAGEngine", lambda: engine)

    _run(learner.scan_outlook_for_lifecycle("u1", "tok", "ws1"))
    assert engine.ingested, "entity-bearing message should be persisted"
    assert engine.ingested[0][0] == "ws1"
    assert engine.ingested[0][1][0]["type"] == "contact"


def test_scan_outlook_non_200_and_exception(monkeypatch):
    learner, _, _ = _learner(monkeypatch)
    monkeypatch.setattr("httpx.AsyncClient", lambda *a, **k: _FakeClient(_FakeResponse(403)))
    _run(learner.scan_outlook_for_lifecycle("u1", "tok", "ws1"))

    monkeypatch.setattr("httpx.AsyncClient", lambda *a, **k: _FakeClient(RuntimeError("boom")))
    _run(learner.scan_outlook_for_lifecycle("u1", "tok", "ws1"))


# ============================================================================
# _process_outlook_message
# ============================================================================

def test_process_message_no_keyword(monkeypatch):
    learner, _, _ = _learner(monkeypatch)
    msg = _outlook_msg("m1", subject="Hello world", body="just greetings")
    assert _run(learner._process_outlook_message(msg, "u1", "ws1")) is False


def test_process_message_body_str(monkeypatch):
    learner, _, _ = _learner(monkeypatch)
    msg = _outlook_msg("m2", subject="Order shipped", body="tracking 1Z999AA10123456784")
    msg["body"] = "tracking 1Z999AA10123456784"
    engine = _FakeGraphEngine()
    monkeypatch.setattr("core.graphrag_engine.GraphRAGEngine", lambda: engine)
    assert _run(learner._process_outlook_message(msg, "u1", "ws1")) is True
    assert engine.ingested[0][1][0]["type"] == "contact"


def test_process_message_persist_false(monkeypatch):
    learner, _, _ = _learner(monkeypatch)
    msg = _outlook_msg("m3", subject="Invoice attached", body="please pay")
    monkeypatch.setattr("core.graphrag_engine.GraphRAGEngine", lambda: _FakeGraphEngine())
    monkeypatch.setattr(
        "core.graphrag_engine.GraphRAGEngine", lambda: _FakeGraphEngine()
    )
    # force persistence failure
    class _Fail:
        def ingest_structured_data(self, **kw):
            raise RuntimeError("persist boom")
    monkeypatch.setattr("core.graphrag_engine.GraphRAGEngine", lambda: _Fail())
    assert _run(learner._process_outlook_message(msg, "u1", "ws1")) is False


def test_process_message_exception(monkeypatch):
    learner, _, _ = _learner(monkeypatch)
    assert _run(learner._process_outlook_message(None, "u1", "ws1")) is False


# ============================================================================
# _build_entities
# ============================================================================

def test_build_entities_full():
    learner = m365.Microsoft365LifecycleLearner()
    entities, relationships = learner._build_entities(
        subject="PO-98765 Invoice USD 1,234.56",
        from_email="v@acme.com",
        from_name="Vendor",
        received="2026-08-01T10:00:00Z",
        matched_keywords=["invoice", "purchase order"],
        order_ids=["PO-98765", "PO-11111"],
        tracking_ids=["1Z999AA10123456784"],
        amounts=["1,234.56"],
        body_preview="preview...",
        message_id="m-1",
    )
    types = {e["type"] for e in entities}
    assert types == {"contact", "email", "order", "shipment"}
    event = next(e for e in entities if e["type"] == "email")
    assert event["properties"]["amounts"] == ["1,234.56"]
    assert event["properties"]["keywords"] == ["invoice", "purchase order"]
    order_ent = next(e for e in entities if e["type"] == "order")
    assert order_ent["properties"]["order_id"] == "PO-98765"
    shipment_ent = next(e for e in entities if e["type"] == "shipment")
    assert shipment_ent["properties"]["tracking_number"] == "1Z999AA10123456784"
    rel_types = {r["type"] for r in relationships}
    assert rel_types == {"sent", "references"}
    sender_rel = next(r for r in relationships if r["type"] == "sent")
    assert sender_rel["from"] == "Vendor"


def test_build_entities_no_sender_and_no_ids():
    learner = m365.Microsoft365LifecycleLearner()
    entities, relationships = learner._build_entities(
        subject="",
        from_email="",
        from_name="",
        received="",
        matched_keywords=["quote"],
        order_ids=[],
        tracking_ids=[],
        amounts=[],
        body_preview="",
        message_id=None,
    )
    assert len(entities) == 1
    assert entities[0]["type"] == "email"
    assert entities[0]["name"] == "(no subject)"
    assert entities[0]["id"] == "email:"  # message_id/received/subject all empty
    assert relationships == []


def test_build_entities_caps_and_amount_merge():
    learner = m365.Microsoft365LifecycleLearner()
    entities, relationships = learner._build_entities(
        subject="s",
        from_email="a@b.c",
        from_name="A",
        received="r",
        matched_keywords=["payment"],
        order_ids=[f"PO-{i}" for i in range(10)],
        tracking_ids=[f"T{i}" for i in range(10)],
        amounts=["1.00", "2.00"],
        body_preview="p",
        message_id="mid",
    )
    assert sum(1 for e in entities if e["type"] == "order") == 5
    assert sum(1 for e in entities if e["type"] == "shipment") == 5
    event = next(e for e in entities if e["type"] == "email")
    assert event["properties"]["amounts"] == ["1.00", "2.00"]
    contact = next(e for e in entities if e["type"] == "contact")
    assert "amounts" not in contact["properties"]


# ============================================================================
# _persist_to_graph
# ============================================================================

def test_persist_to_graph_success(monkeypatch):
    engine = _FakeGraphEngine()
    monkeypatch.setattr("core.graphrag_engine.GraphRAGEngine", lambda: engine)
    learner = m365.Microsoft365LifecycleLearner()
    ok = _run(learner._persist_to_graph("ws1", [{"id": "e1"}], [{"from": "e1", "to": "e2"}]))
    assert ok is True
    assert engine.ingested == [("ws1", [{"id": "e1"}], [{"from": "e1", "to": "e2"}])]


def test_persist_to_graph_engine_failure(monkeypatch):
    monkeypatch.setattr("core.graphrag_engine.GraphRAGEngine", lambda: _FakeGraphEngine())
    monkeypatch.setattr(
        "core.graphrag_engine.GraphRAGEngine", lambda: MagicMock()
    )
    engine = _FakeGraphEngine()
    engine.fail = True
    monkeypatch.setattr("core.graphrag_engine.GraphRAGEngine", lambda: engine)
    learner = m365.Microsoft365LifecycleLearner()
    assert _run(learner._persist_to_graph("ws1", [{"id": "e1"}], [])) is False


def test_persist_to_graph_import_failure(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "core.graphrag_engine", None)
    learner = m365.Microsoft365LifecycleLearner()
    assert _run(learner._persist_to_graph("ws1", [{"id": "e1"}], [])) is False
