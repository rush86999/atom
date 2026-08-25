"""Tests for the ingest→search bridge: file-ingested docs get a PG
IngestedDocument row (so hybrid search no longer drops them as unbridged),
and the chat search handler surfaces document hits."""
from unittest.mock import AsyncMock, MagicMock, patch

from core.auto_document_ingestion import AutoDocumentIngestionService
from integrations.chat_orchestrator import ChatIntent, ChatOrchestrator, FeatureType


async def test_bridge_creates_ingested_document_row():
    svc = AutoDocumentIngestionService()
    captured = {}

    class _FakeSession:
        def add(self, row):
            captured["row"] = row

        def commit(self):
            pass

        def close(self):
            pass

    with patch("core.database.SessionLocal", return_value=_FakeSession()):
        svc._bridge_document_to_db(
            doc_id="file_123.456",
            file_name="visa payment 1-17-25.pdf",
            file_ext="pdf",
            content=b"pdf-bytes",
            text="VISA payment statement content",
            source="zoho_workdrive",
            ws_id="default",
        )

    row = captured["row"]
    assert row.id == "file_123.456"
    assert row.file_name == "visa payment 1-17-25.pdf"
    assert row.integration_id == "zoho_workdrive"
    assert row.workspace_id == "default"
    assert row.content_preview == "VISA payment statement content"
    assert row.external_id == "file_123.456"


async def test_process_file_bytes_bridges_row_on_success():
    svc = AutoDocumentIngestionService()
    svc.memory_handler = MagicMock()
    svc.memory_handler.add_document = MagicMock(return_value=True)
    svc.redactor = None
    svc.parser = MagicMock()
    svc.parser.parse_document = AsyncMock(return_value="Some real text content here")
    svc._bridge_document_to_db = MagicMock()

    result = await svc.process_file_bytes(
        b"content", file_name="note.md", source="zoho_workdrive", user_id="u1"
    )

    assert result["status"] == "ingested"
    svc._bridge_document_to_db.assert_called_once()
    assert svc._bridge_document_to_db.call_args.kwargs["file_name"] == "note.md"


async def test_chat_search_includes_document_results():
    orch = ChatOrchestrator.__new__(ChatOrchestrator)
    orch.ai_engines = {}

    with patch("core.hybrid_search.documents_hybrid.DocumentsHybridSearch") as cls:
        svc = cls.return_value
        svc.search = AsyncMock(
            return_value={"results": [{"id": "file_1", "title": "visa payment 1-17-25.pdf"}]}
        )
        resp = await orch._handle_search_request("what is inside the visa pdf", {}, {}, None)

    assert resp["success"] is True
    assert len(resp["data"]["document_results"]) == 1
    assert resp["data"]["document_results"][0]["title"] == "visa payment 1-17-25.pdf"


async def test_chat_search_document_leg_failure_is_isolated():
    orch = ChatOrchestrator.__new__(ChatOrchestrator)
    orch.ai_engines = {}

    with patch("core.hybrid_search.documents_hybrid.DocumentsHybridSearch") as cls:
        svc = cls.return_value
        svc.search = AsyncMock(side_effect=RuntimeError("boom"))
        resp = await orch._handle_search_request("query", {}, {}, None)

    assert resp["success"] is True
    assert resp["data"]["document_results"] == []


def test_search_message_counts_documents():
    orch = ChatOrchestrator.__new__(ChatOrchestrator)
    feature_responses = {
        FeatureType.SEARCH: {
            "data": {"results": [{"id": "e1"}], "document_results": [{"id": "d1"}, {"id": "d2"}]}
        }
    }
    msg = orch._generate_main_message(
        "query", {"primary_intent": ChatIntent.SEARCH_REQUEST}, feature_responses
    )
    assert msg == "I found 3 results for your search."
