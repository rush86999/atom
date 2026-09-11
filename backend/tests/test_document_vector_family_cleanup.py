"""Vector cleanup must remove a document's CHUNK family, not just its base row.

Regression context (2026-09-11): the LanceDB `documents` table held 38,983 rows.
2,676 of them carried a `metadata.pg_document_id` pointing at a parent that no
longer existed in Postgres — orphaned chunks. Root cause: both cleanup sites in
`auto_document_ingestion.py` called only `delete_documents_by_id("documents",
doc.id)`, which matches `id = '<doc_id>'` exactly. A chunked ingest stores its
chunks as `<doc_id>::c0..cN`, so every chunk survived the parent's deletion:
still retrievable, still stamped with a departed parent, and still able to
compete with the fresh copy in search results.

`LanceDBHandler.delete_documents_by_prefix` already existed for exactly this
(`{doc}::c0..c3400` per its own docstring) but was never called from these two
sites. These tests lock the family-aware cleanup in place.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import pytest

from core.auto_document_ingestion import AutoDocumentIngestionService, IngestedDocument


class RecordingHandler:
    """Minimal memory_handler stand-in that records every deletion call."""

    def __init__(self) -> None:
        self.deleted_by_id: List[Tuple[str, str]] = []
        self.deleted_by_prefix: List[Tuple[str, str]] = []

    def delete_documents_by_id(self, table_name: str, doc_id: str) -> bool:
        self.deleted_by_id.append((table_name, doc_id))
        return True

    def delete_documents_by_prefix(self, table_name: str, prefix: str) -> bool:
        self.deleted_by_prefix.append((table_name, prefix))
        return True


def _doc(doc_id: str, integration_id: str = "google_drive") -> IngestedDocument:
    return IngestedDocument(
        id=doc_id,
        file_name="price_list.xlsx",
        file_path="/drive/price_list.xlsx",
        file_type="xlsx",
        integration_id=integration_id,
        workspace_id="default",
        file_size_bytes=123,
        content_preview="Consolidated price list",
        ingested_at=datetime.now(timezone.utc),
        external_id="ext-1",
    )


@pytest.mark.asyncio
async def test_remove_integration_deletes_chunk_family():
    """Deleting an integration's docs must take the `<doc_id>::` chunks with it."""
    svc = AutoDocumentIngestionService(workspace_id="default")
    handler = RecordingHandler()
    svc.memory_handler = handler
    svc.ingested_docs = {"ext-1": _doc("doc_abc")}

    await svc.remove_integration_documents("google_drive")

    assert ("documents", "doc_abc") in handler.deleted_by_id, "base row not deleted"
    assert ("documents", "doc_abc::") in handler.deleted_by_prefix, (
        "chunk family was NOT deleted — chunks would be orphaned in LanceDB"
    )


@pytest.mark.asyncio
async def test_remove_integration_leaves_other_integrations_alone():
    """Scoping must not regress: only the requested integration's docs go."""
    svc = AutoDocumentIngestionService(workspace_id="default")
    handler = RecordingHandler()
    svc.memory_handler = handler
    svc.ingested_docs = {
        "ext-1": _doc("doc_abc", integration_id="google_drive"),
        "ext-2": _doc("doc_xyz", integration_id="onedrive"),
    }

    await svc.remove_integration_documents("google_drive")

    deleted = {d for _t, d in handler.deleted_by_id}
    assert "doc_abc" in deleted
    assert "doc_xyz" not in deleted, "another integration's document was deleted"


@pytest.mark.asyncio
async def test_cleanup_failure_is_not_fatal():
    """A raising handler must not break the removal loop (best-effort contract)."""

    class ExplodingHandler(RecordingHandler):
        def delete_documents_by_id(self, table_name: str, doc_id: str) -> bool:
            raise RuntimeError("lancedb down")

        def delete_documents_by_prefix(self, table_name: str, prefix: str) -> bool:
            raise RuntimeError("lancedb down")

    svc = AutoDocumentIngestionService(workspace_id="default")
    svc.memory_handler = ExplodingHandler()
    svc.ingested_docs = {"ext-1": _doc("doc_abc")}

    result: Dict[str, Any] = await svc.remove_integration_documents("google_drive")

    assert result is not None  # returned instead of propagating the error
