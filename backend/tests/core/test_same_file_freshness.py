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
        assert kwargs["doc_id"].startswith("doc_")  # content-hash identity
        assert kwargs["metadata"]["source_content_hash"]
        memory.delete_documents_by_id.assert_called_once_with(
            "documents", kwargs["doc_id"]
        )

    @pytest.mark.asyncio
    async def test_same_content_same_id_across_names(self, service):
        """Content is the identity: same bytes under different names fold to
        one row; name is metadata, never an identity key."""
        svc, memory = service
        await svc.process_file_bytes(b"content one", "a.txt", source="dropbox")
        id1 = memory.add_document.call_args.kwargs["doc_id"]
        memory.add_document.reset_mock()
        memory.delete_documents_by_id.reset_mock()
        memory.get_document_by_id.return_value = None
        await svc.process_file_bytes(b"content one", "b.txt", source="onedrive")
        id2 = memory.add_document.call_args.kwargs["doc_id"]
        assert id1 == id2

    @pytest.mark.asyncio
    async def test_different_content_same_name_gets_different_key(self, service):
        """Two genuinely different files that share a filename must NOT
        collide (the old name-based key overwrote one with the other)."""
        svc, memory = service
        await svc.process_file_bytes(b"content one", "a.txt", source="dropbox")
        id1 = memory.add_document.call_args.kwargs["doc_id"]
        await svc.process_file_bytes(b"content two!!", "a.txt", source="dropbox")
        id2 = memory.add_document.call_args.kwargs["doc_id"]
        assert id1 != id2

    @pytest.mark.asyncio
    async def test_external_id_identity_preferred(self, service):
        """Connector-supplied external record id wins over the content hash."""
        svc, memory = service
        await svc.process_file_bytes(
            b"content", "a.txt", source="dropbox",
            extra_metadata={"external_id": "dbx:12345"},
        )
        doc_id = memory.add_document.call_args.kwargs["doc_id"]
        assert doc_id.startswith("ext_")

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
    def test_content_doc_key_identity(self):
        from api.document_routes import _content_doc_key

        # Same content → same id, regardless of title/filename.
        assert _content_doc_key("hello world") == _content_doc_key("hello world")
        # Different content → different id, even under the same title.
        assert _content_doc_key("hello world") != _content_doc_key("hello world!")
        assert _content_doc_key("hello world").startswith("doc_")

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


class TestSharedVectorUpsert:
    """The shared helper every integration path funnels through."""

    @pytest.mark.asyncio
    async def test_skip_unchanged_across_arbitrary_table(self):
        from core.doc_freshness_service import hash_text
        from core.vector_upsert import upsert_document

        handler = MagicMock()
        handler.get_document_by_id = MagicMock(
            return_value={"id": "r1", "text": "x", "metadata": {
                "source_content_hash": hash_text("x")}}
        )
        handler.add_document = MagicMock(return_value=True)
        result = await upsert_document(
            handler, table_name="integration_salesforce", text="x",
            doc_id="rec_salesforce:r1", source="salesforce", metadata={},
        )
        assert result == "skipped_unchanged"
        handler.add_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_written_passes_table_flags_and_hash(self):
        from core.vector_upsert import upsert_document

        handler = MagicMock()
        handler.get_document_by_id = MagicMock(return_value=None)
        handler.delete_documents_by_id = MagicMock(return_value=True)
        handler.add_document = MagicMock(return_value=True)
        result = await upsert_document(
            handler, table_name="tenant_t1_messages", text="msg body",
            doc_id="msg_slack:m1", source="slack_webhook",
            metadata={"integration_id": "slack"},
            user_id="t1", workspace_id="ws1", skip_ai_triggers=True,
        )
        assert result == "written"
        handler.delete_documents_by_id.assert_called_once_with(
            "tenant_t1_messages", "msg_slack:m1"
        )
        _, kwargs = handler.add_document.call_args
        assert kwargs["table_name"] == "tenant_t1_messages"
        assert kwargs["skip_ai_triggers"] is True
        assert kwargs["workspace_id"] == "ws1"
        assert kwargs["metadata"]["source_content_hash"]
        assert kwargs["metadata"]["integration_id"] == "slack"
