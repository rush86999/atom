"""Joined Documents lifecycle: delete must invalidate every supported read.

Failure-first against current main: upload writes LanceDB, the SQL
``IngestedDocument``/FTS mirror, and the materialized file. The verified delete
service currently removes only LanceDB base + chunk rows, so SQL/lexical/VFS/
citability and the file survive.

Scratch SQLite + scratch LanceDB + deterministic embeddings only. No live DB,
model/provider, credential, send or spend.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from core.hybrid_search.documents_hybrid import DocumentsHybridSearch
from core.hybrid_search.fts_bootstrap import ensure_documents_fts_for_session
from core.hybrid_search.lexical_ranker import search_documents_lexical
from core.models import IngestedDocument
from tests.test_document_export import exported, _upload


def _fts_row_count(session, doc_id: str) -> int:
    row = session.execute(
        text(
            "SELECT COUNT(*) FROM ingested_documents_fts "
            "WHERE rowid = (SELECT rowid FROM ingested_documents WHERE id = :id)"
        ),
        {"id": doc_id},
    ).first()
    return int(row[0] if row else 0)


async def _legacy_action(query: str, workspace_id: str):
    from core.action_registry import _documents_search_legacy

    return await _documents_search_legacy(
        {"query": query, "limit": 10},
        {"workspace_id": workspace_id},
    )


def _prepare(ctx, monkeypatch, tmp_path, marker: str):
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
    ensure_documents_fts_for_session(ctx.session)
    user_id = ctx.user.id
    doc_id = _upload(ctx, f"{marker} unique lifecycle body\n", "joined.txt")
    ctx.session.expire_all()
    actor = ctx.session.query(type(ctx.user)).filter(
        type(ctx.user).id == user_id).one()
    return doc_id, actor


async def _delete(ctx, actor, doc_id: str, operation_id: str, monkeypatch):
    import api.document_routes as dr

    monkeypatch.setattr(
        dr, "get_lancedb_handler", lambda ws_id=None: ctx.handler)
    return await dr.delete_document(
        doc_id=doc_id,
        request=object(),
        operation_id=operation_id,
        db=ctx.session,
        current_user=actor,
        agent_id=None,
    )


@pytest.mark.asyncio
async def test_delete_must_invalidate_sql_fts_lexical_action_and_file(
    exported, monkeypatch, tmp_path
):
    ctx = exported
    marker = f"joinedlifecycle{uuid.uuid4().hex}"
    doc_id, actor = _prepare(ctx, monkeypatch, tmp_path, marker)

    row = ctx.session.get(IngestedDocument, doc_id)
    assert row is not None
    assert row.workspace_id == ctx.workspace
    stored_file = Path(row.file_path)
    assert stored_file.is_file()
    assert ctx.handler.count_document_rows_by_id("documents", doc_id) == 1
    assert search_documents_lexical(
        ctx.session, marker, workspace_id=ctx.workspace
    )
    hybrid = await DocumentsHybridSearch(
        db=ctx.session, lancedb=ctx.handler, workspace_id=ctx.workspace
    ).search(marker)
    assert any(hit.get("id") == doc_id for hit in hybrid.get("results", []))
    legacy = await _legacy_action(marker, ctx.workspace)
    assert any(hit.get("id") == doc_id for hit in legacy.get("results", []))
    assert _fts_row_count(ctx.session, doc_id) == 1

    out = await _delete(
        ctx, actor, doc_id, "joined-delete-1", monkeypatch)
    assert out["success"] is True
    assert out["metadata"]["verification"]["status"] == "verified"

    # Vector-only endpoints are clean today.
    assert ctx.handler.count_document_rows_by_id("documents", doc_id) == 0
    assert ctx.handler.count_document_rows_by_prefix(
        "documents", f"{doc_id}::") == 0

    # The retained negative: every supported SQL/FTS/lexical/hybrid/action
    # and materialized-file read must be gone after a verified delete.
    ctx.session.expire_all()
    tombstone = ctx.session.get(IngestedDocument, doc_id)
    assert tombstone is not None
    assert tombstone.freshness_status == "removed"
    assert search_documents_lexical(
        ctx.session, marker, workspace_id=ctx.workspace
    ) == []
    hybrid_after = await DocumentsHybridSearch(
        db=ctx.session, lancedb=ctx.handler, workspace_id=ctx.workspace
    ).search(marker)
    assert not any(
        hit.get("id") == doc_id for hit in hybrid_after.get("results", []))
    legacy_after = await _legacy_action(marker, ctx.workspace)
    assert not any(
        hit.get("id") == doc_id for hit in legacy_after.get("results", []))
    assert not stored_file.exists()

    replay = await _delete(
        ctx, actor, doc_id, "joined-delete-1", monkeypatch)
    assert replay["metadata"]["verification"]["status"] == "already_applied"


@pytest.mark.asyncio
async def test_sql_delete_failure_is_partial_not_clean(
    exported, monkeypatch, tmp_path
):
    import core.document_delete_service as dds
    from fastapi import HTTPException

    ctx = exported
    marker = f"joinsqlfail{uuid.uuid4().hex}"
    doc_id, actor = _prepare(ctx, monkeypatch, tmp_path, marker)
    monkeypatch.setattr(dds, "_delete_sql_target", lambda db, target: "delete_failed")

    with pytest.raises(HTTPException) as exc:
        await _delete(ctx, actor, doc_id, "joined-sql-fail", monkeypatch)
    assert exc.value.status_code == 503
    detail = exc.value.detail
    assert detail["verification"]["status"] == "committed_unverified"
    assert detail["verification"]["effect"] == "partial"
    assert detail["verification"]["replay"] == "do_not_repeat"
    ctx.session.expire_all()
    assert ctx.session.get(IngestedDocument, doc_id) is not None
    assert ctx.handler.count_document_rows_by_id("documents", doc_id) == 0


@pytest.mark.asyncio
async def test_file_unlink_failure_is_partial_not_clean(
    exported, monkeypatch, tmp_path
):
    import core.document_delete_service as dds
    from fastapi import HTTPException

    ctx = exported
    marker = f"joinfilefail{uuid.uuid4().hex}"
    doc_id, actor = _prepare(ctx, monkeypatch, tmp_path, marker)
    stored_file = Path(ctx.session.get(IngestedDocument, doc_id).file_path)
    monkeypatch.setattr(dds, "_unlink_file", lambda plan: "delete_failed")

    with pytest.raises(HTTPException) as exc:
        await _delete(ctx, actor, doc_id, "joined-file-fail", monkeypatch)
    assert exc.value.status_code == 503
    assert exc.value.detail["verification"]["effect"] == "partial"
    ctx.session.expire_all()
    tombstone = ctx.session.get(IngestedDocument, doc_id)
    assert tombstone is not None
    assert tombstone.freshness_status == "removed"
    assert stored_file.is_file()


@pytest.mark.asyncio
async def test_fts_readback_failure_is_partial_not_clean(
    exported, monkeypatch, tmp_path
):
    import core.document_delete_service as dds
    from fastapi import HTTPException

    ctx = exported
    marker = f"joinftsfail{uuid.uuid4().hex}"
    doc_id, actor = _prepare(ctx, monkeypatch, tmp_path, marker)
    monkeypatch.setattr(dds, "_fts_after", lambda db, target: "unavailable")

    with pytest.raises(HTTPException) as exc:
        await _delete(ctx, actor, doc_id, "joined-fts-fail", monkeypatch)
    assert exc.value.status_code == 503
    assert exc.value.detail["verification"]["effect"] == "partial"


@pytest.mark.asyncio
async def test_foreign_sql_scope_is_refused_without_effects(
    exported, monkeypatch, tmp_path
):
    from fastapi import HTTPException

    ctx = exported
    marker = f"joinscope{uuid.uuid4().hex}"
    doc_id, actor = _prepare(ctx, monkeypatch, tmp_path, marker)
    stored_file = Path(ctx.session.get(IngestedDocument, doc_id).file_path)
    ctx.session.query(IngestedDocument).filter(
        IngestedDocument.id == doc_id).update(
        {"workspace_id": "ws-foreign"}, synchronize_session=False)
    ctx.session.commit()

    with pytest.raises(HTTPException) as exc:
        await _delete(ctx, actor, doc_id, "joined-scope", monkeypatch)
    assert exc.value.status_code == 404
    assert ctx.handler.count_document_rows_by_id("documents", doc_id) == 1
    assert stored_file.is_file()


@pytest.mark.asyncio
async def test_stale_sql_version_refuses_before_vector_or_file_effect(
    exported, monkeypatch, tmp_path
):
    import core.document_delete_service as dds
    from fastapi import HTTPException

    ctx = exported
    marker = f"joinversion{uuid.uuid4().hex}"
    doc_id, actor = _prepare(ctx, monkeypatch, tmp_path, marker)
    real_target = dds._sql_target(
        ctx.session, doc_id=doc_id, workspace_id=ctx.workspace,
        tenant_id="t1")
    stale = dict(real_target)
    stale["version"] = "stale-version"
    monkeypatch.setattr(dds, "_sql_target", lambda *a, **k: stale)
    stored_file = Path(ctx.session.get(IngestedDocument, doc_id).file_path)

    with pytest.raises(HTTPException) as exc:
        await _delete(ctx, actor, doc_id, "joined-version", monkeypatch)
    assert exc.value.status_code == 409
    assert ctx.handler.count_document_rows_by_id("documents", doc_id) == 1
    assert stored_file.is_file()
    ctx.session.expire_all()
    assert ctx.session.get(IngestedDocument, doc_id) is not None


@pytest.mark.asyncio
async def test_stale_producer_same_version_cannot_republish(
    exported, monkeypatch, tmp_path
):
    from core.vector_upsert import upsert_document

    ctx = exported
    marker = f"joinstale{uuid.uuid4().hex}"
    doc_id, actor = _prepare(ctx, monkeypatch, tmp_path, marker)
    text = f"{marker} unique lifecycle body\n"
    await _delete(ctx, actor, doc_id, "joined-stale-delete", monkeypatch)

    result = await upsert_document(
        ctx.handler,
        table_name="documents",
        text=text,
        doc_id=doc_id,
        source="upload:joined.txt",
        metadata={"title": "joined.txt", "file_name": "joined.txt"},
        user_id=ctx.user.id,
        workspace_id=ctx.workspace,
        extra_columns={"freshness_status": "fresh"},
    )
    assert result == "skipped_revoked"
    assert ctx.handler.count_document_rows_by_id("documents", doc_id) == 0
    ctx.session.expire_all()
    assert ctx.session.get(IngestedDocument, doc_id).freshness_status == "removed"
    assert search_documents_lexical(
        ctx.session, marker, workspace_id=ctx.workspace
    ) == []


@pytest.mark.asyncio
async def test_new_version_is_allowed_and_old_receipt_cannot_delete_it(
    exported, monkeypatch, tmp_path
):
    from core.doc_freshness_service import extraction_content_hash
    from core.vector_upsert import upsert_document
    from fastapi import HTTPException

    ctx = exported
    marker = f"joinnewversion{uuid.uuid4().hex}"
    doc_id, actor = _prepare(ctx, monkeypatch, tmp_path, marker)
    text = f"{marker} unique lifecycle body\n"
    await _delete(ctx, actor, doc_id, "joined-version-delete", monkeypatch)

    new_text = text + "authorized newer revision\n"
    result = await upsert_document(
        ctx.handler,
        table_name="documents",
        text=new_text,
        doc_id=doc_id,
        source="upload:joined.txt",
        metadata={"title": "joined.txt", "file_name": "joined.txt"},
        user_id=ctx.user.id,
        workspace_id=ctx.workspace,
        extra_columns={"freshness_status": "fresh"},
    )
    assert result == "written"
    ctx.session.expire_all()
    row = ctx.session.get(IngestedDocument, doc_id)
    row.freshness_status = "fresh"
    row.source_content_hash = extraction_content_hash(new_text)
    ctx.session.commit()
    assert ctx.handler.count_document_rows_by_id("documents", doc_id) == 1

    with pytest.raises(HTTPException) as exc:
        await _delete(
            ctx, actor, doc_id, "joined-version-delete", monkeypatch)
    assert exc.value.status_code == 503
    assert exc.value.detail["verification"]["effect"] in ("partial", "unknown")
    assert ctx.handler.count_document_rows_by_id("documents", doc_id) == 1
    ctx.session.expire_all()
    assert ctx.session.get(IngestedDocument, doc_id).freshness_status == "fresh"


@pytest.mark.asyncio
async def test_upload_same_removed_version_is_refused(
    exported, monkeypatch, tmp_path
):
    ctx = exported
    text = f"joinuploadrevoked{uuid.uuid4().hex} removed body\n"
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
    ensure_documents_fts_for_session(ctx.session)
    user_id = ctx.user.id
    doc_id = _upload(ctx, text, "joined.txt")
    ctx.session.expire_all()
    actor = ctx.session.query(type(ctx.user)).filter(
        type(ctx.user).id == user_id).one()
    await _delete(ctx, actor, doc_id, "joined-upload-delete", monkeypatch)

    response = ctx.client.post(
        "/api/documents/upload",
        files={"file": ("joined.txt", text.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "DOCUMENT_REVOKED"
    assert ctx.handler.count_document_rows_by_id("documents", doc_id) == 0
    ctx.session.expire_all()
    assert ctx.session.get(IngestedDocument, doc_id).freshness_status == "removed"


@pytest.mark.asyncio
async def test_unsafe_outside_file_path_is_not_unlinked(
    exported, monkeypatch, tmp_path
):
    from fastapi import HTTPException

    ctx = exported
    marker = f"joinunsafe{uuid.uuid4().hex}"
    doc_id, actor = _prepare(ctx, monkeypatch, tmp_path, marker)
    outside = tmp_path.parent / f"outside-{doc_id}.txt"
    outside.write_text("must not be deleted\n")
    ctx.session.query(IngestedDocument).filter(
        IngestedDocument.id == doc_id).update(
        {"file_path": str(outside)}, synchronize_session=False)
    ctx.session.commit()

    with pytest.raises(HTTPException) as exc:
        await _delete(ctx, actor, doc_id, "joined-unsafe", monkeypatch)
    assert exc.value.status_code == 503
    assert exc.value.detail["verification"]["effect"] == "partial"
    assert outside.is_file()
    ctx.session.expire_all()
    assert ctx.session.get(IngestedDocument, doc_id).freshness_status == "removed"


@pytest.mark.asyncio
async def test_shared_file_is_preserved_for_peer_document(
    exported, monkeypatch, tmp_path
):
    ctx = exported
    marker = f"joinshared{uuid.uuid4().hex}"
    doc_id, actor = _prepare(ctx, monkeypatch, tmp_path, marker)
    row = ctx.session.get(IngestedDocument, doc_id)
    stored_file = Path(row.file_path)
    peer = IngestedDocument(
        id=f"peer-{uuid.uuid4().hex[:12]}",
        workspace_id=row.workspace_id,
        tenant_id=row.tenant_id,
        file_name="peer.txt",
        file_path=row.file_path,
        file_type=row.file_type,
        integration_id="manual_upload",
        external_id=f"upload_peer_{uuid.uuid4().hex[:8]}",
        content_preview="peer shares the same materialized file",
        freshness_status="fresh",
    )
    ctx.session.add(peer)
    ctx.session.commit()

    out = await _delete(ctx, actor, doc_id, "joined-shared", monkeypatch)
    assert out["metadata"]["verification"]["status"] == "verified"
    assert out["data"]["effects"]["file"] == "shared"
    assert stored_file.is_file()
    ctx.session.expire_all()
    assert ctx.session.get(IngestedDocument, doc_id).freshness_status == "removed"
    assert ctx.session.get(IngestedDocument, peer.id) is not None
