# -*- coding: utf-8 -*-
"""Coverage wave 80 — core/microsoft365_learner.py to >=95% (standalone;
onedrive_service / httpx / doc_learner / GraphRAGEngine fully mocked —
zero network, zero LLM spend).

Covers:
- _build_entities: sender+email+order+shipment+amounts, no-sender form,
  missing message_id, keyword matching.
- _process_outlook_message: no keyword match → False; match → persist True/
  False; malformed body (str); exception → False.
- _persist_to_graph: success + exception → False.
- scan_outlook_for_lifecycle: 200 with mixed messages, non-200, exception.
- scan_onedrive_for_lifecycle: envelope handling (success dict / dict with
  value / list), dedupe by id, download 200 → learn + tempfile cleanup,
  download non-200, exception in processing.
"""
import os
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.microsoft365_learner import Microsoft365LifecycleLearner


@pytest.fixture()
def learner():
    with patch("core.document_learner.DocumentLifecycleLearner"):
        l = Microsoft365LifecycleLearner(ai_service=None, db_session=None)
    l.doc_learner = MagicMock()
    l.doc_learner.learn_from_file = AsyncMock()
    return l


# ============================================================================
# _build_entities
# ============================================================================

def test_build_entities_full():
    learner = Microsoft365LifecycleLearner.__new__(Microsoft365LifecycleLearner)
    entities, relationships = learner._build_entities(
        subject="Invoice #INV-1234 for order PO-5678",
        from_email="vendor@acme.com",
        from_name="Acme Billing",
        received="2026-08-01T10:00:00Z",
        matched_keywords=["invoice", "order"],
        order_ids=["INV-1234", "PO-5678"],
        tracking_ids=["1Z9999999999999999"],
        amounts=["1,234.50"],
        body_preview="preview text",
        message_id="msg-1",
    )
    types = {e["type"] for e in entities}
    assert types == {"contact", "email", "order", "shipment"}
    email_ent = next(e for e in entities if e["type"] == "email")
    assert email_ent["properties"]["amounts"] == ["1,234.50"]
    assert email_ent["properties"]["keywords"] == ["invoice", "order"]
    contact = next(e for e in entities if e["type"] == "contact")
    assert contact["properties"]["email"] == "vendor@acme.com"
    rel_types = {r["type"] for r in relationships}
    assert rel_types == {"sent", "references"}
    assert any(r["from"] == "Acme Billing"
               and r["type"] == "sent" for r in relationships)


def test_build_entities_no_sender_and_no_ids():
    learner = Microsoft365LifecycleLearner.__new__(Microsoft365LifecycleLearner)
    entities, relationships = learner._build_entities(
        subject="", from_email="", from_name="", received="",
        matched_keywords=["quote"], order_ids=[], tracking_ids=[],
        amounts=[], body_preview="", message_id=None,
    )
    assert [e["type"] for e in entities] == ["email"]
    assert entities[0]["name"] == "(no subject)"
    assert entities[0]["properties"]["keywords"] == ["quote"]
    assert relationships == []


def test_build_entities_limits_ids_and_no_amounts():
    learner = Microsoft365LifecycleLearner.__new__(Microsoft365LifecycleLearner)
    order_ids = [f"ORD-{i}" for i in range(8)]
    entities, relationships = learner._build_entities(
        subject="PO-1", from_email="x@y.z", from_name="X",
        received="2026-08-01", matched_keywords=["purchase order"],
        order_ids=order_ids, tracking_ids=[], amounts=[],
        body_preview="", message_id="m1",
    )
    order_ents = [e for e in entities if e["type"] == "order"]
    assert len(order_ents) == 5  # capped at 5


# ============================================================================
# _process_outlook_message
# ============================================================================

@pytest.mark.asyncio
async def test_process_message_no_keyword_match(learner):
    msg = {"subject": "Team lunch", "body": {"content": "pizza"},
           "from": {"emailAddress": {"address": "a@b.c"}}}
    result = await learner._process_outlook_message(msg, "u1", "ws1")
    assert result is False


@pytest.mark.asyncio
async def test_process_message_persist_true(learner):
    msg = {
        "id": "m1",
        "subject": "Invoice #INV-99",
        "from": {"emailAddress": {"address": "b@c.d", "name": "B"}},
        "receivedDateTime": "2026-08-01T00:00:00Z",
        "body": {"content": "Please pay USD 1,234.56 within 30 days. Tracking 1Z9999999999999999"},
    }
    learner._persist_to_graph = AsyncMock(return_value=True)
    result = await learner._process_outlook_message(msg, "u1", "ws1")
    assert result is True
    learner._persist_to_graph.assert_awaited_once()
    entities, relationships = learner._persist_to_graph.await_args.args[1:]
    assert any(e["type"] == "order" for e in entities)
    assert any(e["type"] == "shipment" for e in entities)


@pytest.mark.asyncio
async def test_process_message_persist_false(learner):
    msg = {"subject": "Tracking 1Z9999999999999999", "body": {},
           "from": {"emailAddress": {"address": "c@d.e"}}}
    learner._persist_to_graph = AsyncMock(return_value=False)
    result = await learner._process_outlook_message(msg, "u1", "ws1")
    assert result is False


@pytest.mark.asyncio
async def test_process_message_body_as_string(learner):
    msg = {"subject": "quote attached", "body": "plain string body"}
    learner._persist_to_graph = AsyncMock(return_value=True)
    result = await learner._process_outlook_message(msg, "u1", "ws1")
    assert result is True


@pytest.mark.asyncio
async def test_process_message_exception_swallowed(learner):
    msg = {"subject": "payment due", "body": {"content": "pay"},
           "from": None}
    learner._persist_to_graph = AsyncMock(side_effect=RuntimeError("boom"))
    result = await learner._process_outlook_message(msg, "u1", "ws1")
    assert result is False


@pytest.mark.asyncio
async def test_process_message_no_entities_built(learner):
    """Defensive guard: keyword matched but _build_entities returned nothing
    → False without persisting."""
    msg = {"subject": "invoice attached", "body": {"content": "x"},
           "from": {"emailAddress": {"address": "a@b.c"}}}
    learner._build_entities = MagicMock(return_value=([], []))
    learner._persist_to_graph = AsyncMock(return_value=True)
    result = await learner._process_outlook_message(msg, "u1", "ws1")
    assert result is False
    learner._persist_to_graph.assert_not_called()


# ============================================================================
# _persist_to_graph
# ============================================================================

@pytest.mark.asyncio
async def test_persist_to_graph_success(learner):
    with patch("core.graphrag_engine.GraphRAGEngine") as engine_cls:
        engine = MagicMock()
        engine_cls.return_value = engine
        ok = await learner._persist_to_graph(
            "ws1", [{"id": "e1"}], [{"from": "e1", "to": "e2"}])
    engine.ingest_structured_data.assert_called_once_with(
        workspace_id="ws1", tenant_id="ws1", entities=[{"id": "e1"}],
        relationships=[{"from": "e1", "to": "e2"}])
    assert ok is True


@pytest.mark.asyncio
async def test_persist_to_graph_exception(learner):
    with patch("core.graphrag_engine.GraphRAGEngine") as engine_cls:
        engine = MagicMock()
        engine.ingest_structured_data.side_effect = RuntimeError("graph down")
        engine_cls.return_value = engine
        ok = await learner._persist_to_graph("ws1", [], [])
    assert ok is False


# ============================================================================
# scan_outlook_for_lifecycle
# ============================================================================

@pytest.mark.asyncio
async def test_scan_outlook_success(learner):
    messages = [
        {"id": "m1", "subject": "Invoice #INV-1",
         "from": {"emailAddress": {"address": "a@b.c"}},
         "receivedDateTime": "2026-08-01T00:00:00Z",
         "body": {"content": "USD 100.00 due"}},
        {"id": "m2", "subject": "hello", "body": {"content": "hi"},
         "from": {"emailAddress": {"address": "x@y.z"}}},
    ]
    client = MagicMock()
    client.__aenter__.return_value = client
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"value": messages}
    client.get = AsyncMock(return_value=resp)
    learner._process_outlook_message = AsyncMock(side_effect=[True, False])
    with patch("httpx.AsyncClient",
               return_value=client) as client_cls:
        await learner.scan_outlook_for_lifecycle("u1", "tok", "ws1")
    client_cls.assert_called_once()
    assert client.get.await_count == 1
    assert learner._process_outlook_message.await_count == 2


@pytest.mark.asyncio
async def test_scan_outlook_non_200(learner):
    learner._process_outlook_message = AsyncMock()
    client = MagicMock()
    client.__aenter__.return_value = client
    resp = MagicMock()
    resp.status_code = 500
    client.get = AsyncMock(return_value=resp)
    with patch("httpx.AsyncClient", return_value=client):
        await learner.scan_outlook_for_lifecycle("u1", "tok", "ws1")
    learner._process_outlook_message.assert_not_called()


@pytest.mark.asyncio
async def test_scan_outlook_exception(learner):
    client = MagicMock()
    client.__aenter__.return_value = client
    client.get = AsyncMock(side_effect=RuntimeError("network"))
    with patch("httpx.AsyncClient",
               return_value=client):
        await learner.scan_outlook_for_lifecycle("u1", "tok", "ws1")


# ============================================================================
# scan_onedrive_for_lifecycle
# ============================================================================

@pytest.mark.asyncio
async def test_scan_onedrive_envelopes_and_dedup(learner):
    results = [
        {"status": "success", "data": {"value": [
            {"id": "f1", "name": "a.pdf", "file": {"mimeType": "application/pdf"}},
        ]}},
        {"value": [
            {"id": "f1", "name": "a.pdf", "file": {"mimeType": "application/pdf"}},  # duplicate
            {"id": "f2", "name": "b.xlsx", "file": {"mimeType": "spreadsheet"}},
            {"id": "f3", "name": "c.txt"},  # no file key → dropped
        ]},
        [{"id": "f4", "name": "d.docx", "file": {"mimeType": "document"}}],
        "not-a-dict",
        {"value": []},
    ]
    onedrive = MagicMock()
    onedrive.search_files = AsyncMock(side_effect=results)
    download = MagicMock()
    download.__aenter__.return_value = download
    resp = MagicMock()
    resp.status_code = 200
    resp.content = b"pdf-bytes"
    download.get = AsyncMock(return_value=resp)
    with patch("core.microsoft365_learner.onedrive_service", onedrive), \
         patch("httpx.AsyncClient",
               return_value=download) as client_cls, \
         patch("tempfile.NamedTemporaryFile") as tmp_cls:
        tmp = MagicMock()
        tmp.name = "/tmp/learned_file"
        tmp_cls.return_value.__enter__.return_value = tmp
        with patch("os.unlink") as unlink:
            await learner.scan_onedrive_for_lifecycle("u1", "tok", "ws1")
    assert onedrive.search_files.await_count == 5
    assert client_cls.call_count == 3  # unique files: f1, f2, f4 (f3 no file)
    assert learner.doc_learner.learn_from_file.await_count == 3
    assert unlink.call_count == 3


@pytest.mark.asyncio
async def test_scan_onedrive_download_failure(learner):
    onedrive = MagicMock()
    onedrive.search_files = AsyncMock(return_value={"status": "success",
                                                    "data": {"value": [
                                                        {"id": "f1",
                                                         "name": "a.pdf",
                                                         "file": {"mimeType": "application/pdf"}}]}})
    download = MagicMock()
    download.__aenter__.return_value = download
    resp = MagicMock()
    resp.status_code = 403
    download.get = AsyncMock(return_value=resp)
    with patch("core.microsoft365_learner.onedrive_service", onedrive), \
         patch("httpx.AsyncClient",
               return_value=download):
        await learner.scan_onedrive_for_lifecycle("u1", "tok", "ws1")
    learner.doc_learner.learn_from_file.assert_not_called()


@pytest.mark.asyncio
async def test_scan_onedrive_processing_exception(learner):
    onedrive = MagicMock()
    onedrive.search_files = AsyncMock(return_value={
        "status": "success",
        "data": {"value": [{"id": "f1", "name": "a.pdf", "file": {"mimeType": "application/pdf"}}]},
    })
    download = MagicMock()
    download.__aenter__.return_value = download
    download.get = AsyncMock(side_effect=RuntimeError("graph down"))
    with patch("core.microsoft365_learner.onedrive_service", onedrive), \
         patch("httpx.AsyncClient",
               return_value=download):
        await learner.scan_onedrive_for_lifecycle("u1", "tok", "ws1")
    learner.doc_learner.learn_from_file.assert_not_called()
