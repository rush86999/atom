"""Contract tests for verified knowledge-document deletion.

The failure-first case is the old prefix-cleanup behaviour: the base row was
deleted, chunk cleanup raised or returned ``False``, and the caller still got
a clean 200 with no operation identity. These tests drive the public delete
route against a real scratch LanceDB store and a scratch SQLite receipt
ledger, then read the effect back from a fresh handler/session.

LanceDB and SQL are separate stores. The tests therefore assert the observed
truth (base row + chunk family counts), a durable ``AuditLog`` receipt, and a
truthful partial/unknown outcome — never atomicity across the two stores.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.lancedb_handler import LanceDBHandler
from core.models import AuditLog, User


class _StubEmbed:
    """Deterministic offline embedding (no provider call)."""

    async def generate_embedding(self, text, **kwargs):
        return [0.01] * 384


@pytest.fixture
def scratch(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'document-delete-truth.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    user = User(
        id="u-doc", email="doc@example.com", hashed_password="h",
        first_name="Doc", last_name="User", role="member", status="active",
        tenant_id="t-doc", workspace_id="ws-doc")
    session.add(user)
    session.commit()
    yield session, user, engine
    session.close()
    engine.dispose()


def _handler(tmp_path, workspace_id: str = "ws-doc") -> LanceDBHandler:
    handler = LanceDBHandler(
        db_path=str(tmp_path / f"ldb-{workspace_id}"),
        workspace_id=workspace_id,
    )
    handler.embedding_service = _StubEmbed()
    handler._ensure_db()
    return handler


async def _add(
    handler: LanceDBHandler, doc_id: str, text: str,
    workspace_id: str = "ws-doc", user_id: str = "u-doc",
) -> None:
    ok = await asyncio.to_thread(
        handler.add_document,
        "documents", text, "truth-test", {"title": doc_id},
        user_id, workspace_id, doc_id, True,
    )
    assert ok, f"failed to seed {doc_id}"


async def _delete_route(
    handler, db, user, doc_id: str, operation_id: str | None = None,
    monkeypatch=None,
):
    import api.document_routes as dr

    monkeypatch.setattr(
        dr, "get_lancedb_handler", lambda ws_id=None: handler)
    return await dr.delete_document(
        doc_id=doc_id,
        request=object(),  # not a Request → governance pass-through
        operation_id=operation_id,
        db=db,
        current_user=user,
        agent_id=None,
    )


def _receipt(db, operation_id: str) -> AuditLog:
    return db.query(AuditLog).filter(AuditLog.id == operation_id).one()


def _metadata(receipt: AuditLog) -> Dict[str, Any]:
    return json.loads(receipt.metadata_json or "{}")


@pytest.mark.asyncio
async def test_base_and_chunk_family_verified_with_one_receipt(
        scratch, tmp_path, monkeypatch):
    db, user, _engine = scratch
    handler = _handler(tmp_path)
    await _add(handler, "doc-a", "unique base body")
    await _add(handler, "doc-a::c0", "chunk zero body")
    await _add(handler, "doc-a::c1", "chunk one body")

    base_calls = []
    original_delete = handler.delete_documents_by_id
    handler.delete_documents_by_id = (
        lambda *a, **k: (base_calls.append("id"), original_delete(*a, **k))[1])

    out = await _delete_route(
        handler, db, user, "doc-a", "op-a", monkeypatch)

    assert out["success"] is True
    verification = out["metadata"]["verification"]
    assert verification["status"] == "verified"
    assert verification["effect"] == "committed"
    assert out["data"]["counts"] == {
        "pre_base": 1, "pre_chunks": 2,
        "post_base": 0, "post_chunks": 0,
    }
    assert handler.count_document_rows_by_id("documents", "doc-a") == 0
    assert handler.count_document_rows_by_prefix(
        "documents", "doc-a::") == 0
    assert handler.get_document_by_id("documents", "doc-a") is None
    listed_ids = {row["id"] for row in handler.list_documents("documents")}
    assert not listed_ids & {"doc-a", "doc-a::c0", "doc-a::c1"}
    hits = await asyncio.to_thread(
        handler.search, "documents", "unique base body")
    assert hits == []

    operation_id = out["metadata"]["operation_id"]
    receipt = _receipt(db, operation_id)
    assert receipt.user_id == "u-doc"
    assert receipt.tenant_id == "t-doc"
    assert receipt.workspace_id == "ws-doc"
    assert receipt.action == "document_deleted"
    assert receipt.success is True
    meta = _metadata(receipt)
    assert meta["doc_id"] == "doc-a"
    assert meta["pre_base_rows"] == 1
    assert meta["pre_chunk_rows"] == 2
    assert meta["post_base_rows"] == 0
    assert meta["post_chunk_rows"] == 0
    assert meta["outcome"] == "verified"

    replay = await _delete_route(
        handler, db, user, "doc-a", "op-a", monkeypatch)
    assert replay["metadata"]["verification"]["status"] == "already_applied"
    assert base_calls == ["id"], "replay performed a second base deletion"
    assert db.query(AuditLog).filter(
        AuditLog.id == operation_id).count() == 1


@pytest.mark.asyncio
async def test_chunk_only_family_is_deletable_and_verified(
        scratch, tmp_path, monkeypatch):
    db, user, _engine = scratch
    handler = _handler(tmp_path)
    await _add(handler, "doc-b::c0", "orphan chunk zero")
    await _add(handler, "doc-b::c1", "orphan chunk one")

    out = await _delete_route(
        handler, db, user, "doc-b", "op-b", monkeypatch)

    assert out["metadata"]["verification"]["status"] == "verified"
    assert out["data"]["counts"] == {
        "pre_base": 0, "pre_chunks": 2,
        "post_base": 0, "post_chunks": 0,
    }
    assert handler.count_document_rows_by_prefix(
        "documents", "doc-b::") == 0
    meta = _metadata(_receipt(db, out["metadata"]["operation_id"]))
    assert meta["pre_base_rows"] == 0
    assert meta["pre_chunk_rows"] == 2


@pytest.mark.parametrize("mode", ["raise", "false"])
@pytest.mark.asyncio
async def test_prefix_cleanup_failure_is_partial_not_clean_success(
        scratch, tmp_path, monkeypatch, mode):
    db, user, _engine = scratch
    handler = _handler(tmp_path)
    await _add(handler, "doc-c", "base body for partial")
    await _add(handler, "doc-c::c0", "chunk zero for partial")
    await _add(handler, "doc-c::c1", "chunk one for partial")

    calls = []
    if mode == "raise":
        def broken_prefix(*args, **kwargs):
            calls.append("prefix")
            raise RuntimeError("lance write lock")
    else:
        def broken_prefix(*args, **kwargs):
            calls.append("prefix")
            return False
    handler.delete_documents_by_prefix = broken_prefix

    with pytest.raises(HTTPException) as exc:
        await _delete_route(
            handler, db, user, "doc-c", "op-c", monkeypatch)

    assert exc.value.status_code == 503
    detail = exc.value.detail
    assert detail["verification"]["status"] == "committed_unverified"
    assert detail["verification"]["effect"] == "partial"
    assert detail["verification"]["replay"] == "do_not_repeat"
    assert detail["operation_id"].endswith("op-c")
    assert detail["data"]["counts"] == {
        "pre_base": 1, "pre_chunks": 2,
        "post_base": 0, "post_chunks": 2,
    }
    assert handler.count_document_rows_by_id("documents", "doc-c") == 0
    assert handler.count_document_rows_by_prefix(
        "documents", "doc-c::") == 2

    receipt = _receipt(db, detail["operation_id"])
    assert receipt.success is False
    meta = _metadata(receipt)
    assert meta["outcome"] == "committed_unverified"
    assert meta["post_chunk_rows"] == 2

    with pytest.raises(HTTPException) as replay_exc:
        await _delete_route(
            handler, db, user, "doc-c", "op-c", monkeypatch)
    assert replay_exc.value.status_code == 503
    assert (replay_exc.value.detail["verification"]["status"]
            == "committed_unverified")
    assert (replay_exc.value.detail["verification"]["effect"] == "partial")
    assert calls == ["prefix"], "replay blindly repeated the failed cleanup"


@pytest.mark.asyncio
async def test_unknown_and_foreign_ids_are_404_without_effect_or_receipt(
        scratch, tmp_path, monkeypatch):
    db, user, _engine = scratch
    own = _handler(tmp_path, "ws-doc")
    foreign = _handler(tmp_path, "ws-other")
    await _add(foreign, "doc-foreign", "foreign workspace body",
               workspace_id="ws-other", user_id="u-other")

    with pytest.raises(HTTPException) as unknown:
        await _delete_route(own, db, user, "ghost", "op-unknown", monkeypatch)
    assert unknown.value.status_code == 404
    assert db.query(AuditLog).count() == 0

    with pytest.raises(HTTPException) as foreign_exc:
        await _delete_route(
            own, db, user, "doc-foreign", "op-foreign", monkeypatch)
    assert foreign_exc.value.status_code == 404
    assert foreign.count_document_rows_by_id(
        "documents", "doc-foreign") == 1
    assert db.query(AuditLog).count() == 0


@pytest.mark.asyncio
async def test_same_operation_id_for_a_different_document_conflicts(
        scratch, tmp_path, monkeypatch):
    db, user, _engine = scratch
    handler = _handler(tmp_path)
    await _add(handler, "doc-d", "first document")
    await _add(handler, "doc-e", "second document")

    await _delete_route(handler, db, user, "doc-d", "op-shared", monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _delete_route(
            handler, db, user, "doc-e", "op-shared", monkeypatch)

    assert exc.value.status_code == 409
    assert handler.count_document_rows_by_id("documents", "doc-e") == 1
    assert db.query(AuditLog).count() == 1


@pytest.mark.asyncio
async def test_same_operation_id_from_another_actor_conflicts(
        scratch, tmp_path, monkeypatch):
    db, user, _engine = scratch
    other = User(
        id="u-other", email="other@example.com", hashed_password="h",
        first_name="Other", last_name="User", role="member", status="active",
        tenant_id="t-doc", workspace_id="ws-doc")
    db.add(other)
    db.commit()
    handler = _handler(tmp_path)
    await _add(handler, "doc-f", "first document")
    await _add(handler, "doc-g", "second document")

    await _delete_route(handler, db, user, "doc-f", "op-actor", monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await _delete_route(
            handler, db, other, "doc-g", "op-actor", monkeypatch)

    assert exc.value.status_code == 409
    assert handler.count_document_rows_by_id("documents", "doc-g") == 1
    assert db.query(AuditLog).count() == 1


@pytest.mark.asyncio
async def test_second_delete_with_new_operation_is_no_change(
        scratch, tmp_path, monkeypatch):
    db, user, _engine = scratch
    handler = _handler(tmp_path)
    await _add(handler, "doc-h", "document to delete once")

    await _delete_route(handler, db, user, "doc-h", "op-first", monkeypatch)
    second = await _delete_route(
        handler, db, user, "doc-h", "op-second", monkeypatch)

    assert second["success"] is True
    assert second["metadata"]["verification"]["status"] == "no_change"
    assert second["data"]["no_change"] is True
    assert db.query(AuditLog).count() == 1, "no_change invented a new receipt"


@pytest.mark.asyncio
async def test_fresh_session_and_restarted_handler_readback_survive(
        scratch, tmp_path, monkeypatch):
    db, user, engine = scratch
    handler = _handler(tmp_path)
    await _add(handler, "doc-i", "durable deletion body")
    await _add(handler, "doc-i::c0", "durable chunk body")

    out = await _delete_route(
        handler, db, user, "doc-i", "op-restart", monkeypatch)
    operation_id = out["metadata"]["operation_id"]

    db.close()
    fresh_db = sessionmaker(bind=engine)()
    try:
        fresh_user = fresh_db.query(User).filter(User.id == "u-doc").one()
        receipt = _receipt(fresh_db, operation_id)
        assert receipt.success is True
        assert _metadata(receipt)["doc_id"] == "doc-i"

        restarted = _handler(tmp_path)
        assert restarted.count_document_rows_by_id(
            "documents", "doc-i") == 0
        assert restarted.count_document_rows_by_prefix(
            "documents", "doc-i::") == 0

        replay = await _delete_route(
            restarted, fresh_db, fresh_user, "doc-i", "op-restart",
            monkeypatch)
        assert replay["metadata"]["verification"]["status"] == (
            "already_applied")
        assert fresh_db.query(AuditLog).count() == 1
    finally:
        fresh_db.close()
