"""Same-file freshness: re-ingesting a file must UPDATE it, not duplicate it.

Covers the three ingestion surfaces made content-aware upserts:
- AutoDocumentIngestionService.process_file_bytes (connector/upload shared path)
- api/document_routes._upsert_document + _stable_doc_key (documents API)
- sync_integration's superseded-row cleanup (exercised via the w34 suites;
  asserted here at the unit level through process_file_bytes semantics)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.auto_document_ingestion import AutoDocumentIngestionService


@pytest.fixture
def service():
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("ATOM_INGESTION_PERSIST_STATE", "false")
        memory = MagicMock()
        memory.add_document = MagicMock(return_value=True)
        memory.get_document_by_id = MagicMock(return_value=None)
        memory.delete_documents_by_id = MagicMock(return_value=True)
        redactor = MagicMock()
        redactor.redact.return_value = MagicMock(has_secrets=False, redacted_text=None)
        mp.setattr(
            "core.lancedb_handler.get_lancedb_handler", lambda *a, **k: memory
        )
        svc = AutoDocumentIngestionService()
        svc.memory_handler = memory
        svc.redactor = redactor
        svc._ws_handlers = {}
        yield svc, memory


class TestProcessFileBytesUpsert:
    @pytest.mark.asyncio
    async def test_first_ingest_writes_with_stable_key(self, service):
        svc, memory = service
        result = await svc.process_file_bytes(
            b"# Hello\nWorld content", "notes.md", source="dropbox"
        )
        assert result["status"] == "ingested"
        _, kwargs = memory.add_document.call_args
        # Stable id: same file → same id on every ingest.
        assert kwargs["doc_id"].startswith("file_")
        assert kwargs["metadata"]["source_content_hash"]
        memory.delete_documents_by_id.assert_called_once_with(
            "documents", kwargs["doc_id"]
        )

    @pytest.mark.asyncio
    async def test_same_id_for_same_source_and_name(self, service):
        svc, memory = service
        await svc.process_file_bytes(b"content one", "a.txt", source="dropbox")
        id1 = memory.add_document.call_args.kwargs["doc_id"]
        memory.add_document.reset_mock()
        await svc.process_file_bytes(b"content two!!", "a.txt", source="dropbox")
        id2 = memory.add_document.call_args.kwargs["doc_id"]
        assert id1 == id2

    @pytest.mark.asyncio
    async def test_different_name_gets_different_key(self, service):
        svc, memory = service
        await svc.process_file_bytes(b"content", "a.txt", source="dropbox")
        id1 = memory.add_document.call_args.kwargs["doc_id"]
        await svc.process_file_bytes(b"content", "b.txt", source="dropbox")
        id2 = memory.add_document.call_args.kwargs["doc_id"]
        assert id1 != id2

    @pytest.mark.asyncio
    async def test_unchanged_content_skips_write(self, service):
        svc, memory = service
        # Stored copy exists with the same content hash the new run will
        # compute → skip entirely.
        from core.doc_freshness_service import hash_text

        memory.get_document_by_id = MagicMock(
            return_value={
                "id": "file_x",
                "text": "same text",
                "metadata": {"source_content_hash": hash_text("same text")},
            }
        )
        result = await svc.process_file_bytes(b"same text", "a.txt", source="dropbox")
        assert result["status"] == "skipped"
        assert result["reason"] == "unchanged"
        memory.add_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_changed_content_replaces_prior_row(self, service):
        svc, memory = service
        from core.doc_freshness_service import hash_text

        memory.get_document_by_id = MagicMock(
            return_value={
                "id": "file_x",
                "text": "old text",
                "metadata": {"source_content_hash": hash_text("old text")},
            }
        )
        result = await svc.process_file_bytes(b"brand new text", "a.txt", source="dropbox")
        assert result["status"] == "ingested"
        memory.delete_documents_by_id.assert_called()
        memory.add_document.assert_called_once()


class TestDocumentsApiUpsertHelpers:
    def test_stable_doc_key_deterministic(self):
        from api.document_routes import _stable_doc_key

        assert _stable_doc_key("upload", "a:b.txt") == _stable_doc_key("upload", "a:b.txt")
        assert _stable_doc_key("upload", "a.txt") != _stable_doc_key("upload", "b.txt")
        assert _stable_doc_key("api", "x") != _stable_doc_key("upload", "x")

    @pytest.mark.asyncio
    async def test_upsert_skips_unchanged(self):
        from api.document_routes import _upsert_document
        from core.doc_freshness_service import hash_text

        handler = MagicMock()
        handler.get_document_by_id = MagicMock(
            return_value={"id": "k", "text": "t", "metadata": {
                "source_content_hash": hash_text("t")}}
        )
        handler.add_document = MagicMock(return_value=True)
        result = await _upsert_document(
            handler, text="t", doc_key="k", source="s", metadata={}, user_id="u"
        )
        assert result == "skipped_unchanged"
        handler.add_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_upsert_replaces_changed(self):
        from api.document_routes import _upsert_document

        handler = MagicMock()
        handler.get_document_by_id = MagicMock(
            return_value={"id": "k", "text": "old", "metadata": {
                "source_content_hash": "different"}}
        )
        handler.delete_documents_by_id = MagicMock(return_value=True)
        handler.add_document = MagicMock(return_value=True)
        result = await _upsert_document(
            handler, text="new text", doc_key="k", source="s",
            metadata={}, user_id="u", workspace_id="ws1",
        )
        assert result == "written"
        handler.delete_documents_by_id.assert_called_once_with("documents", "k")
        _, kwargs = handler.add_document.call_args
        assert kwargs["doc_id"] == "k"
        assert kwargs["workspace_id"] == "ws1"
        assert kwargs["metadata"]["source_content_hash"]
