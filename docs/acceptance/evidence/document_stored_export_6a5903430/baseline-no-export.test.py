"""Read-only failure-first proof for NEXT03 stored-document export.

Mounted real api.document_routes router; no live DB/world/browser/model.
Shows current-main read works while export/download is absent, and the enabled
Documents detail component has no export control.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.document_routes as dr

REPO = Path("/private/tmp/atom-task-wait-01-reconciliation-20261107")


class _Handler:
    def get_document_by_id(self, table, doc_id):
        assert table == "documents"
        return {
            "id": doc_id,
            "text": "stored extracted text for NEXT03",
            "created_at": "2026-11-07T00:00:00Z",
            "metadata": {
                "title": "next03.txt",
                "file_type": "txt",
                "source": "upload",
                "source_content_hash": "ev4:abc",
            },
        }


def _app():
    app = FastAPI()
    app.include_router(dr.router)
    app.dependency_overrides[dr.get_current_user] = lambda: SimpleNamespace(
        id="member-1", workspace_id="ws1", tenant_id="t1")
    return app


def test_mounted_document_router_reads_but_has_no_export(monkeypatch):
    monkeypatch.setattr(dr, "get_lancedb_handler", lambda ws: _Handler())
    client = TestClient(_app())

    read = client.get("/api/documents/doc-1")
    assert read.status_code == 200, read.text
    assert read.json()["data"]["content"] == "stored extracted text for NEXT03"

    for path in (
        "/api/documents/doc-1/export",
        "/api/documents/doc-1/download",
        "/api/documents/doc-1/export?format=text",
    ):
        response = client.get(path)
        assert response.status_code in (404, 405), (path, response.status_code)

    route_paths = {getattr(route, "path", "") for route in dr.router.routes}
    assert not any(
        "export" in path or "download" in path for path in route_paths
    ), route_paths


def test_enabled_documents_detail_has_no_export_control():
    detail = (REPO / "frontend-nextjs/pages/documents/[docId].tsx").read_text()
    listing = (REPO / "frontend-nextjs/pages/documents.tsx").read_text()
    for label, source in (("detail", detail), ("listing", listing)):
        lowered = source.lower()
        assert "download" not in lowered, label
        assert "/export" not in lowered, label
        assert "export document" not in lowered, label
        assert "exportdocument" not in lowered, label
        assert ">export<" not in lowered, label
    assert "/api/documents/" in detail
    assert "router.push(`/documents/${doc.id}`)" in listing
