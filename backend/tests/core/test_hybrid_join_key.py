"""Join-key bridge: LanceDB `documents` row id must equal the PG IngestedDocument id.

Hybrid search Step 1 (P4): without this, vector hits (timestamp ids) can never be
resolved to PG rows and are not `documents.cat`-able via the knowledge VFS, which
only resolves PG ids.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_sync_integration_stamps_join_key_into_lancedb():
    """Ingesting via sync_integration must pass the PG id as the LanceDB doc_id."""
    from core.auto_document_ingestion import AutoDocumentIngestionService

    service = AutoDocumentIngestionService()

    calls: list = []

    class FakeMemory:
        def add_document(self, **kwargs):
            calls.append(kwargs)
            return True

    service.memory_handler = FakeMemory()
    service.redactor = None
    settings = service.get_settings("google_drive")
    settings.enabled = True
    settings.file_types = ["pdf"]

    file_info = {
        "id": "ext-1",
        "name": "report.pdf",
        "size": 500,
        "modified_at": None,
        "path": "/reports/report.pdf",
        "url": "https://drive.example/report.pdf",
    }

    with (
        patch.object(service, "_list_files", new=AsyncMock(return_value=[file_info])),
        patch.object(service, "_download_file", new=AsyncMock(return_value=b"pdf-bytes")),
        patch.object(
            service.parser,
            "parse_document",
            new=AsyncMock(return_value="Quarterly revenue grew 20 percent."),
        ),
        patch.object(service, "_persist_freshness_on_ingest", new=MagicMock()),
        patch.object(service, "_maybe_supersede_older_docs", new=MagicMock()),
    ):
        result = await service.sync_integration("google_drive", force=True)

    assert result["files_ingested"] == 1
    assert calls, "add_document was not called"
    kwargs = calls[0]
    pg_doc = service.ingested_docs["ext-1"]

    # The bridge: LanceDB row id IS the PG row id (VFS-citable path).
    assert kwargs["doc_id"] == pg_doc.id, (
        "LanceDB doc_id must equal the PG IngestedDocument id so vector hits "
        "resolve to documents.cat paths"
    )
    assert kwargs["doc_id"].startswith("doc_")
    # Stamps for Step 3 filtering / audit.
    assert kwargs["metadata"].get("pg_document_id") == pg_doc.id
    assert kwargs["metadata"].get("source_type") == "ingested"


@pytest.mark.asyncio
async def test_api_ingest_document_passes_doc_id_to_lancedb():
    """API ingest must pass its uuid as doc_id so the LanceDB id matches the API id."""
    import backend.api.document_routes as doc_routes
    from uuid import uuid4

    handler_calls: list = []

    class FakeHandler:
        def add_document(self, **kwargs):
            handler_calls.append(kwargs)
            return True

    class FakeUser:
        id = "u1"
        workspaces = []

    from fastapi import HTTPException

    request = MagicMock()
    request.content = "Some knowledge content about revenue."
    request.type = "text"
    request.title = "revenue.md"
    request.metadata = None

    doc_id = str(uuid4())
    with (
        patch.object(doc_routes, "get_lancedb_handler", return_value=FakeHandler()),
        patch.object(doc_routes, "uuid4", return_value=doc_id),
    ):
        # Route is async + requires request/current_user; call the inner body via
        # a lightweight stand-in to assert the doc_id param flows through.
        from types import SimpleNamespace

        route_fn = doc_routes.ingest_document
        # The route is a FastAPI dependency-wrapped function; call with the
        # prepared objects directly.
        try:
            resp = await route_fn(request, current_user=FakeUser())
        except HTTPException as e:
            # FakeHandler returns success, so this should not raise.
            raise AssertionError(f"Unexpected HTTPException: {e.detail}") from e

    assert handler_calls, "add_document was not called"
    kwargs = handler_calls[0]
    assert kwargs["doc_id"] == doc_id, "API ingest must pass doc_id into LanceDB"
    assert kwargs["metadata"].get("doc_id") == doc_id
    assert resp.id == doc_id
