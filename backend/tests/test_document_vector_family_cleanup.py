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


# ─── DELETE /api/documents/{doc_id}: the THIRD family-aware site ─────────────
#
# The d94a5e6df fix (id delete + `<doc_id>::` prefix delete) landed at only
# 2 of 3 sites (auto_document_ingestion.py:1665/:2474) — the HTTP delete
# route orphaned chunk families exactly the same way, and its 404 guard
# made an id that exists ONLY as chunks permanently undeletable.


from fastapi import HTTPException


class RouteRecordingHandler:
    """Stateful LanceDB handler stand-in for the delete route."""

    def __init__(self, base_row=None, family_ids=None):
        self.base_row = dict(base_row) if base_row else None
        self.family_ids = list(family_ids or [])
        self.deleted_by_id: List[Tuple[str, str]] = []
        self.deleted_by_prefix: List[Tuple[str, str]] = []

    def get_document_by_id(self, table_name, doc_id):
        return self.base_row

    def get_document_ids_by_prefix(self, table_name, prefix):
        assert prefix.endswith("::"), prefix
        return list(self.family_ids)

    def count_document_rows_by_id(self, table_name, doc_id):
        return 1 if self.base_row else 0

    def count_document_rows_by_prefix(self, table_name, prefix):
        return len(self.family_ids)

    def delete_documents_by_id(self, table_name, doc_id):
        self.deleted_by_id.append((table_name, doc_id))
        self.base_row = None
        return True

    def delete_documents_by_prefix(self, table_name, prefix):
        self.deleted_by_prefix.append((table_name, prefix))
        self.family_ids = []
        return True


@pytest.fixture
def delete_db(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.database import Base
    from core.models import User

    engine = create_engine(
        f"sqlite:///{tmp_path / 'route-delete.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    user = User(
        id="u-route", email="route@example.com", hashed_password="h",
        first_name="R", last_name="T", role="member", status="active",
        tenant_id="t-route", workspace_id="ws-1")
    session.add(user)
    session.commit()
    yield session, user
    session.close()
    engine.dispose()


async def _run_delete(handler, doc_id, monkeypatch, db, user,
                      operation_id=None):
    import api.document_routes as dr

    monkeypatch.setattr(dr, "get_lancedb_handler", lambda ws_id=None: handler)
    return await dr.delete_document(
        doc_id=doc_id,
        request=object(),  # not a starlette Request → governance pass-through
        operation_id=operation_id,
        db=db,
        current_user=user,
        agent_id=None,
    )


@pytest.mark.asyncio
async def test_delete_route_removes_chunk_family(monkeypatch, delete_db):
    db, user = delete_db
    handler = RouteRecordingHandler(
        base_row={"id": "doc_abc", "text": "x", "metadata": {}},
        family_ids=["doc_abc::c0", "doc_abc::c1"],
    )
    out = await _run_delete(handler, "doc_abc", monkeypatch, db, user)

    assert ("documents", "doc_abc") in handler.deleted_by_id
    assert ("documents", "doc_abc::") in handler.deleted_by_prefix, (
        "route deleted the base row but orphaned the chunk family"
    )
    assert out["success"] is True
    assert out["metadata"]["verification"]["status"] == "verified"


@pytest.mark.asyncio
async def test_delete_route_accepts_chunk_only_id(monkeypatch, delete_db):
    """An id with no exact row but a live chunk family is DELETABLE — the
    old 404 guard made such ids permanently undeletable."""
    db, user = delete_db
    handler = RouteRecordingHandler(
        base_row=None, family_ids=["doc_abc::c0", "doc_abc::c1"]
    )
    out = await _run_delete(handler, "doc_abc", monkeypatch, db, user)

    assert ("documents", "doc_abc::") in handler.deleted_by_prefix
    assert out["success"] is True
    assert out["metadata"]["verification"]["status"] == "verified"


@pytest.mark.asyncio
async def test_delete_route_404_when_neither_row_nor_family(
        monkeypatch, delete_db):
    db, user = delete_db
    handler = RouteRecordingHandler(base_row=None, family_ids=[])
    with pytest.raises(HTTPException) as exc:
        await _run_delete(handler, "ghost", monkeypatch, db, user)
    assert exc.value.status_code == 404
    assert handler.deleted_by_id == []
    assert handler.deleted_by_prefix == []


@pytest.mark.asyncio
async def test_delete_route_family_cleanup_failure_is_not_success(
        monkeypatch, delete_db):
    """A raising prefix delete leaves a known base-row deletion and a live
    chunk family. That is a partial, non-success outcome with the original
    operation identity — never a clean 200 success."""
    db, user = delete_db
    handler = RouteRecordingHandler(
        base_row={"id": "doc_abc", "text": "x", "metadata": {}},
        family_ids=["doc_abc::c0", "doc_abc::c1"],
    )

    def boom(table_name, prefix):
        raise RuntimeError("lance write lock")

    handler.delete_documents_by_prefix = boom
    with pytest.raises(HTTPException) as exc:
        await _run_delete(
            handler, "doc_abc", monkeypatch, db, user,
            operation_id="client-partial-1")

    assert exc.value.status_code == 503
    detail = exc.value.detail
    assert detail["verification"]["status"] == "committed_unverified"
    assert detail["verification"]["effect"] == "partial"
    assert detail["verification"]["replay"] == "do_not_repeat"
    assert detail["operation_id"].endswith("client-partial-1")
    assert detail["data"]["counts"]["post_base"] == 0
    assert detail["data"]["counts"]["post_chunks"] == 2
    assert ("documents", "doc_abc") in handler.deleted_by_id
    assert handler.count_document_rows_by_prefix("documents", "doc_abc::") == 2
