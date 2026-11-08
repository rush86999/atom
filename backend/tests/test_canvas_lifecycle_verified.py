"""Verified canvas delete/undelete lifecycle — real scratch SQLite + routes.

The accepted update/restore slice already runs the shared postcondition oracle.
Delete/undelete bypassed it: no current-scope authorization, no server-owned
operation identity, no exact tombstone/source binding and no independent
readback. These tests exercise the repaired shared consumer end to end:

* real mounted FastAPI routes and real ``Canvas``/``CanvasAudit`` rows;
* a fresh SQLite file shared by fresh sessions (not a mocked durability store);
* the real writer, service and postcondition verifier;
* WebSocket side effects counted through the real broadcast seam.

They preserve the two existing supported policies: single-tenant Personal
``NULL``/``default`` scope and owner OR historical co-editor authorship.
"""
from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import core.models  # noqa: F401 — register the real tables BEFORE create_all
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models_registration import Base


# ---------------------------------------------------------------------------
# Scratch database and mounted app
# ---------------------------------------------------------------------------
@pytest.fixture
def probe(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'canvas_lifecycle.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextlib.contextmanager
    def _get_db_session():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr("core.database.get_db_session", _get_db_session)
    monkeypatch.setattr("core.database.SessionLocal", Session)
    yield SimpleNamespace(Session=Session, engine=engine)
    engine.dispose()


@pytest.fixture
def app_client(probe):
    from api.canvas_routes import router
    from core.auth import get_current_user
    from core.database import get_db

    users: dict = {}
    app = FastAPI()
    app.include_router(router)

    def _override_db():
        session = probe.Session()
        try:
            yield session
        finally:
            session.close()

    def _override_user():
        return users["current"]

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    with TestClient(app) as client:
        yield SimpleNamespace(
            client=client, users=users, Session=probe.Session)


@pytest.fixture
def broadcast_spy(monkeypatch):
    calls = []

    async def record(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr("core.websockets.manager.broadcast", record)
    monkeypatch.setattr(
        "tools.canvas_crud_tool._broadcast_canvas_update", record)
    return calls


# ---------------------------------------------------------------------------
# Row factories
# ---------------------------------------------------------------------------
def _tenant(db, tenant_id="default"):
    from core.models import Tenant

    row = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if row is None:
        row = Tenant(id=tenant_id, name=tenant_id,
                     subdomain=f"sub-{tenant_id}")
        db.add(row)
        db.commit()
    return row


def _workspace(db, workspace_id, tenant_id="default"):
    from core.models import Workspace

    row = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if row is None:
        row = Workspace(id=workspace_id, name=workspace_id,
                        tenant_id=tenant_id)
        db.add(row)
        db.commit()
    return row


def _user(db, *, user_id, tenant_id="default", workspace_id=None):
    from core.models import User, UserStatus

    if tenant_id:
        _tenant(db, tenant_id)
    if workspace_id:
        _workspace(db, workspace_id, tenant_id or "default")
    row = User(
        id=user_id,
        email=f"{user_id}@probe.local",
        hashed_password="x",
        first_name="Probe",
        last_name=user_id,
        role="member",
        status=UserStatus.ACTIVE,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _canvas(db, *, canvas_id, owner_id, tenant_id="default",
            workspace_id=None, content=None, canvas_type="generic"):
    from core.models import Canvas

    if tenant_id:
        _tenant(db, tenant_id)
    if workspace_id:
        _workspace(db, workspace_id, tenant_id or "default")
    row = Canvas(
        id=canvas_id,
        tenant_id=tenant_id or "default",
        workspace_id=workspace_id,
        created_by=owner_id,
        name="Probe Canvas",
        canvas_type=canvas_type,
        content=content,
        status="active",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _audit(db, *, canvas_id, action_type, user_id, tenant_id="default",
           canvas_type="generic", details=None, created_at=None):
    from core.models import CanvasAudit

    row = CanvasAudit(
        canvas_id=canvas_id,
        tenant_id=tenant_id,
        action_type=action_type,
        user_id=user_id,
        canvas_type=canvas_type,
        details_json=details or {},
        created_at=created_at or datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _seed_lifecycle(db, *, canvas_id="probe-canvas", owner_id="owner",
                    tenant_id="default", workspace_id=None,
                    content=None, canvas_type="generic"):
    content = content if content is not None else {
        "to": "a@b.c", "subject": "Probe", "body": "pre-delete body"}
    owner = _user(db, user_id=owner_id, tenant_id=tenant_id,
                  workspace_id=workspace_id)
    _canvas(db, canvas_id=canvas_id, owner_id=owner.id,
            tenant_id=tenant_id, workspace_id=workspace_id,
            content=content, canvas_type=canvas_type)
    base = datetime.now(timezone.utc) - timedelta(minutes=3)
    _audit(db, canvas_id=canvas_id, action_type="create", user_id=owner.id,
           tenant_id=tenant_id, canvas_type=canvas_type,
           details={"content": content, "title": "Probe"},
           created_at=base)
    _audit(db, canvas_id=canvas_id, action_type="update", user_id=owner.id,
           tenant_id=tenant_id, canvas_type=canvas_type,
           details={"content": content, "title": "Probe"},
           created_at=base + timedelta(minutes=1))
    return owner


def _rows(db, canvas_id):
    from core.models import CanvasAudit

    return (db.query(CanvasAudit)
            .filter(CanvasAudit.canvas_id == canvas_id)
            .order_by(CanvasAudit.created_at, CanvasAudit.id)
            .all())


def _fresh_rows(Session, canvas_id):
    with Session() as db:
        return _rows(db, canvas_id)


def _row_ids(rows):
    return [str(row.id) for row in rows]


def _row_snapshot(Session, canvas_id):
    """All stored columns for every audit row (history immutability check)."""
    with Session() as db:
        return [
            {column.name: getattr(row, column.name)
             for column in row.__table__.columns}
            for row in _rows(db, canvas_id)
        ]


# ---------------------------------------------------------------------------
# Positive: owner, co-editor, Personal NULL/default, audit-only
# ---------------------------------------------------------------------------
def test_owner_delete_has_verified_receipt_and_fresh_readback(
        app_client, probe, broadcast_spy):
    with probe.Session() as db:
        owner = _seed_lifecycle(db)
        before = _rows(db, "probe-canvas")
        app_client.users["current"] = owner

    response = app_client.client.delete("/api/canvas/probe-canvas")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("success") is True, body
    assert body.get("status") == "verified", body
    assert body.get("verification", {}).get("status") == "verified", body
    assert body.get("audit_id"), body
    assert body.get("operation_id"), body
    assert body.get("prior_audit_id"), body
    assert body.get("source_audit_id"), body
    assert body.get("content_sha256"), body

    fresh = _fresh_rows(probe.Session, "probe-canvas")
    assert fresh[-1].action_type == "delete"
    assert str(fresh[-1].id) == body["audit_id"]
    assert len(fresh) == len(before) + 1
    assert _row_ids(fresh[:-1]) == _row_ids(before)
    assert (fresh[-1].details_json or {})["prior_audit_id"] == (
        body["prior_audit_id"])
    assert len(broadcast_spy) == 1


def test_undelete_binds_exact_tombstone_source_and_content(
        app_client, probe, broadcast_spy):
    with probe.Session() as db:
        owner = _seed_lifecycle(db)
        prior = _rows(db, "probe-canvas")[-1]
        prior_content = dict(prior.details_json["content"])
        app_client.users["current"] = owner

    deleted = app_client.client.delete("/api/canvas/probe-canvas")
    assert deleted.status_code == 200, deleted.text
    tombstone_id = deleted.json()["audit_id"]

    response = app_client.client.post("/api/canvas/probe-canvas/undelete")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("status") == "verified", body
    assert body.get("verification", {}).get("status") == "verified", body
    assert body.get("audit_id"), body
    assert body.get("operation_id"), body
    assert body.get("restored_from_tombstone_id") == tombstone_id, body
    assert body.get("source_audit_id"), body
    assert body.get("content_sha256"), body

    fresh = _fresh_rows(probe.Session, "probe-canvas")
    assert fresh[-1].action_type == "restore"
    assert str(fresh[-1].id) == body["audit_id"]
    assert (fresh[-1].details_json or {}).get("content") == prior_content
    assert fresh[-1].tenant_id == "default"
    assert any(str(row.id) == tombstone_id for row in fresh)
    assert len(broadcast_spy) == 2  # one delete close + one restore update


def test_same_scope_coeditor_still_allowed(app_client, probe):
    with probe.Session() as db:
        _seed_lifecycle(db, workspace_id="ws-shared")
        coeditor = _user(db, user_id="coeditor", tenant_id="default",
                        workspace_id="ws-shared")
        _audit(db, canvas_id="probe-canvas", action_type="update",
               user_id=coeditor.id, details={"content": "coeditor edit"})
        app_client.users["current"] = coeditor

    response = app_client.client.delete("/api/canvas/probe-canvas")
    assert response.status_code == 200, response.text
    assert response.json().get("status") == "verified", response.json()


def test_null_default_single_tenant_compatible(app_client, probe):
    with probe.Session() as db:
        owner = _user(db, user_id="admin-null", tenant_id=None,
                      workspace_id=None)
        _canvas(db, canvas_id="probe-legacy", owner_id=owner.id,
                tenant_id="default", workspace_id=None,
                content={"body": "legacy"})
        _audit(db, canvas_id="probe-legacy", action_type="create",
               user_id=owner.id, tenant_id="default",
               details={"content": {"body": "legacy"}})
        app_client.users["current"] = owner

    response = app_client.client.delete("/api/canvas/probe-legacy")
    assert response.status_code == 200, response.text
    assert response.json().get("status") == "verified", response.json()


def test_audit_only_canvas_uses_latest_audit_tenant(app_client, probe):
    with probe.Session() as db:
        owner = _user(db, user_id="audit-only-owner", tenant_id="default",
                      workspace_id=None)
        _audit(db, canvas_id="probe-audit-only", action_type="create",
               user_id=owner.id, tenant_id="default",
               details={"content": {"body": "no mirror"}})
        app_client.users["current"] = owner

    response = app_client.client.delete("/api/canvas/probe-audit-only")
    assert response.status_code == 200, response.text
    assert response.json().get("status") == "verified", response.json()
    fresh = _fresh_rows(probe.Session, "probe-audit-only")
    assert fresh[-1].action_type == "delete"
    assert fresh[-1].tenant_id == "default"


def test_audit_only_canvas_undelete_binds_source_without_mirror(
        app_client, probe):
    with probe.Session() as db:
        owner = _user(db, user_id="audit-only-owner", tenant_id="default",
                      workspace_id=None)
        _audit(db, canvas_id="probe-audit-only", action_type="create",
               user_id=owner.id, tenant_id="default",
               details={"content": {"body": "no mirror"}})
        app_client.users["current"] = owner

    deleted = app_client.client.delete("/api/canvas/probe-audit-only")
    assert deleted.status_code == 200, deleted.text
    tombstone_id = deleted.json()["audit_id"]

    response = app_client.client.post(
        "/api/canvas/probe-audit-only/undelete")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("status") == "verified", body
    assert body.get("restored_from_tombstone_id") == tombstone_id, body
    fresh = _fresh_rows(probe.Session, "probe-audit-only")
    assert fresh[-1].action_type == "restore"
    assert fresh[-1].tenant_id == "default"
    assert (fresh[-1].details_json or {}).get("content") == {
        "body": "no mirror"}


# ---------------------------------------------------------------------------
# Negative: stranger / current foreign tenant / current foreign workspace
# ---------------------------------------------------------------------------
def test_stranger_gets_404_and_zero_rows(app_client, probe):
    with probe.Session() as db:
        _seed_lifecycle(db)
        stranger = _user(db, user_id="stranger")
        before = _rows(db, "probe-canvas")
        app_client.users["current"] = stranger

    response = app_client.client.delete("/api/canvas/probe-canvas")
    assert response.status_code == 404, response.text
    assert _row_ids(_fresh_rows(probe.Session, "probe-canvas")) == (
        _row_ids(before))


def test_stranger_cannot_replay_another_users_operation(
        app_client, probe):
    with probe.Session() as db:
        owner = _seed_lifecycle(db)
        stranger = _user(db, user_id="stranger")
        app_client.users["current"] = owner

    deleted = app_client.client.delete(
        "/api/canvas/probe-canvas", params={"operation_id": "op-owner"})
    assert deleted.status_code == 200, deleted.text
    before = _row_ids(_fresh_rows(probe.Session, "probe-canvas"))

    with probe.Session() as db:
        from core.models import User

        app_client.users["current"] = db.get(User, "stranger")

    response = app_client.client.delete(
        "/api/canvas/probe-canvas", params={"operation_id": "op-owner"})
    assert response.status_code == 404, response.text
    assert "audit_id" not in response.json(), response.json()
    assert _row_ids(_fresh_rows(probe.Session, "probe-canvas")) == before


@pytest.mark.parametrize("operation", ["delete", "undelete"])
def test_current_foreign_tenant_coeditor_refuses_before_effect(
        app_client, probe, operation):
    with probe.Session() as db:
        owner = _seed_lifecycle(db, tenant_id="tenant-owner")
        actor = _user(db, user_id="tenant-coeditor",
                      tenant_id="tenant-owner")
        _audit(db, canvas_id="probe-canvas", action_type="update",
               user_id=actor.id, tenant_id="tenant-owner",
               details={"content": {"body": "historical edit"}})
        app_client.users["current"] = owner

    if operation == "undelete":
        initial = app_client.client.delete("/api/canvas/probe-canvas")
        assert initial.status_code == 200, initial.text

    with probe.Session() as db:
        from core.models import User

        moved = db.get(User, "tenant-coeditor")
        _tenant(db, "tenant-other")
        _workspace(db, "ws-other", "tenant-other")
        moved.tenant_id = "tenant-other"
        moved.workspace_id = "ws-other"
        db.commit()
        db.refresh(moved)
        app_client.users["current"] = moved
        before = _row_ids(_rows(db, "probe-canvas"))

    response = (
        app_client.client.delete("/api/canvas/probe-canvas")
        if operation == "delete"
        else app_client.client.post("/api/canvas/probe-canvas/undelete"))
    assert response.status_code in (403, 404), response.text
    assert _row_ids(_fresh_rows(probe.Session, "probe-canvas")) == before


@pytest.mark.parametrize("operation", ["delete", "undelete"])
def test_current_foreign_workspace_coeditor_refuses_before_effect(
        app_client, probe, operation):
    with probe.Session() as db:
        owner = _seed_lifecycle(db, workspace_id="ws-owner")
        actor = _user(db, user_id="ws-coeditor", tenant_id="default",
                      workspace_id="ws-owner")
        _audit(db, canvas_id="probe-canvas", action_type="update",
               user_id=actor.id, details={"content": {"body": "historical edit"}})
        app_client.users["current"] = owner

    if operation == "undelete":
        initial = app_client.client.delete("/api/canvas/probe-canvas")
        assert initial.status_code == 200, initial.text

    with probe.Session() as db:
        from core.models import User

        moved = db.get(User, "ws-coeditor")
        _workspace(db, "ws-other", "default")
        moved.workspace_id = "ws-other"
        db.commit()
        db.refresh(moved)
        app_client.users["current"] = moved
        before = _row_ids(_rows(db, "probe-canvas"))

    response = (
        app_client.client.delete("/api/canvas/probe-canvas")
        if operation == "delete"
        else app_client.client.post("/api/canvas/probe-canvas/undelete"))
    assert response.status_code in (403, 404), response.text
    assert _row_ids(_fresh_rows(probe.Session, "probe-canvas")) == before


# ---------------------------------------------------------------------------
# Replay / idempotency / conflict / CAS
# ---------------------------------------------------------------------------
def test_delete_same_operation_replays_one_tombstone_no_second_broadcast(
        app_client, probe, broadcast_spy):
    with probe.Session() as db:
        owner = _seed_lifecycle(db)
        app_client.users["current"] = owner

    first = app_client.client.delete(
        "/api/canvas/probe-canvas", params={"operation_id": "op-delete-1"})
    assert first.status_code == 200, first.text
    second = app_client.client.delete(
        "/api/canvas/probe-canvas", params={"operation_id": "op-delete-1"})
    assert second.status_code == 200, second.text
    assert second.json().get("audit_id") == first.json().get("audit_id")
    assert second.json().get("status") == "no_change", second.json()
    fresh = _fresh_rows(probe.Session, "probe-canvas")
    assert [row.action_type for row in fresh].count("delete") == 1
    assert len(broadcast_spy) == 1


def test_delete_different_operation_is_idempotent_with_original_tombstone(
        app_client, probe, broadcast_spy):
    with probe.Session() as db:
        owner = _seed_lifecycle(db)
        app_client.users["current"] = owner

    first = app_client.client.delete(
        "/api/canvas/probe-canvas", params={"operation_id": "op-a"})
    assert first.status_code == 200, first.text
    second = app_client.client.delete(
        "/api/canvas/probe-canvas", params={"operation_id": "op-b"})
    assert second.status_code == 200, second.text
    body = second.json()
    assert body.get("audit_id") == first.json().get("audit_id")
    assert body.get("already_applied") is True
    assert body.get("status") == "no_change", body
    fresh = _fresh_rows(probe.Session, "probe-canvas")
    assert [row.action_type for row in fresh].count("delete") == 1
    assert len(broadcast_spy) == 1


def test_undelete_same_operation_replays_one_restore(
        app_client, probe, broadcast_spy):
    with probe.Session() as db:
        owner = _seed_lifecycle(db)
        app_client.users["current"] = owner

    deleted = app_client.client.delete("/api/canvas/probe-canvas")
    assert deleted.status_code == 200, deleted.text
    first = app_client.client.post(
        "/api/canvas/probe-canvas/undelete",
        json={"operation_id": "op-undelete-1"})
    assert first.status_code == 200, first.text
    second = app_client.client.post(
        "/api/canvas/probe-canvas/undelete",
        json={"operation_id": "op-undelete-1"})
    assert second.status_code == 200, second.text
    assert second.json().get("audit_id") == first.json().get("audit_id")
    assert second.json().get("status") == "no_change", second.json()
    fresh = _fresh_rows(probe.Session, "probe-canvas")
    assert [row.action_type for row in fresh].count("restore") == 1
    assert len(broadcast_spy) == 2  # delete + one undelete


def test_undelete_non_deleted_canvas_is_a_conflict(app_client, probe):
    with probe.Session() as db:
        owner = _seed_lifecycle(db)
        before = _row_ids(_rows(db, "probe-canvas"))
        app_client.users["current"] = owner

    response = app_client.client.post("/api/canvas/probe-canvas/undelete")
    assert response.status_code == 409, response.text
    assert _row_ids(_fresh_rows(probe.Session, "probe-canvas")) == before


def test_undelete_without_content_source_is_a_conflict(app_client, probe):
    with probe.Session() as db:
        owner = _user(db, user_id="empty-owner")
        _audit(db, canvas_id="probe-empty", action_type="create",
               user_id=owner.id, details={"title": "no body"})
        _audit(db, canvas_id="probe-empty", action_type="delete",
               user_id=owner.id, details={"deleted": True})
        before = _row_ids(_rows(db, "probe-empty"))
        app_client.users["current"] = owner

    response = app_client.client.post("/api/canvas/probe-empty/undelete")
    assert response.status_code == 409, response.text
    assert _row_ids(_fresh_rows(probe.Session, "probe-empty")) == before


def test_delete_expected_prior_mismatch_is_zero_effect(app_client, probe):
    with probe.Session() as db:
        owner = _seed_lifecycle(db)
        before = _row_ids(_rows(db, "probe-canvas"))
        app_client.users["current"] = owner

    response = app_client.client.delete(
        "/api/canvas/probe-canvas",
        params={"expected_prior_audit_id": "not-the-latest"})
    assert response.status_code == 409, response.text
    assert _row_ids(_fresh_rows(probe.Session, "probe-canvas")) == before


def test_same_operation_different_material_is_a_conflict(app_client, probe):
    with probe.Session() as db:
        owner = _seed_lifecycle(db)
        app_client.users["current"] = owner

    first = app_client.client.delete(
        "/api/canvas/probe-canvas", params={"operation_id": "op-reused"})
    assert first.status_code == 200, first.text
    restored = app_client.client.post("/api/canvas/probe-canvas/undelete")
    assert restored.status_code == 200, restored.text
    before = _row_ids(_fresh_rows(probe.Session, "probe-canvas"))

    # Same operation id, but the target state is now a different (live)
    # canvas, so this is not a replay of the original delete.
    response = app_client.client.delete(
        "/api/canvas/probe-canvas", params={"operation_id": "op-reused"})
    assert response.status_code == 409, response.text
    assert _row_ids(_fresh_rows(probe.Session, "probe-canvas")) == before


def test_ambiguous_operation_identity_fails_closed(app_client, probe):
    with probe.Session() as db:
        owner = _seed_lifecycle(db)
        _audit(db, canvas_id="probe-canvas", action_type="delete",
               user_id=owner.id,
               details={"deleted": True, "operation_id": "op-duplicate"})
        _audit(db, canvas_id="probe-canvas", action_type="delete",
               user_id=owner.id,
               details={"deleted": True, "operation_id": "op-duplicate"})
        before = _row_ids(_rows(db, "probe-canvas"))
        app_client.users["current"] = owner

    response = app_client.client.delete(
        "/api/canvas/probe-canvas", params={"operation_id": "op-duplicate"})
    assert response.status_code == 409, response.text
    assert _row_ids(_fresh_rows(probe.Session, "probe-canvas")) == before


def test_scope_move_before_effect_refuses_and_preserves_winner(
        app_client, probe, monkeypatch):
    from tools import canvas_crud_tool as crud

    original = crud.canvas_lifecycle_scope_error
    calls = {"n": 0}

    def _check_then_move(*args, **kwargs):
        calls["n"] += 1
        result = original(*args, **kwargs)
        if calls["n"] == 2 and result is None:
            with probe.Session() as other:
                from core.models import Canvas

                row = other.query(Canvas).filter(
                    Canvas.id == "probe-canvas").one()
                row.workspace_id = "ws-moved"
                other.commit()
        return result

    monkeypatch.setattr(crud, "canvas_lifecycle_scope_error", _check_then_move)
    with probe.Session() as db:
        owner = _seed_lifecycle(db, workspace_id="ws-original")
        app_client.users["current"] = owner

    response = app_client.client.delete("/api/canvas/probe-canvas")
    assert response.status_code == 409, response.text
    with probe.Session() as db:
        from core.models import Canvas

        assert db.query(Canvas).filter(
            Canvas.id == "probe-canvas").one().workspace_id == "ws-moved"
        assert not any(
            row.action_type == "delete"
            for row in _rows(db, "probe-canvas"))


def test_scope_move_after_commit_is_committed_unverified(
        app_client, probe, monkeypatch):
    from core import canvas_write_service as service

    original = service.delete_canvas

    async def _move_after_commit(*args, **kwargs):
        result = await original(*args, **kwargs)
        with probe.Session() as other:
            from core.models import Canvas

            row = other.query(Canvas).filter(
                Canvas.id == "probe-canvas").one()
            row.workspace_id = "ws-moved"
            other.commit()
        return result

    monkeypatch.setattr(service, "delete_canvas", _move_after_commit)
    with probe.Session() as db:
        owner = _seed_lifecycle(db, workspace_id="ws-original")
        app_client.users["current"] = owner

    response = app_client.client.delete("/api/canvas/probe-canvas")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("status") == "committed_unverified", body
    assert body.get("audit_id"), body
    assert body.get("operation_id"), body
    assert body.get("verification", {}).get("replay") == "do_not_repeat", body
    fresh = _fresh_rows(probe.Session, "probe-canvas")
    assert [row.action_type for row in fresh].count("delete") == 1


# ---------------------------------------------------------------------------
# Current-actor authority interleavings (successor blocker)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("operation", ["delete", "undelete"])
@pytest.mark.parametrize("change", ["workspace", "inactive"])
def test_actor_change_after_preflight_refuses_effect(
        app_client, probe, monkeypatch, broadcast_spy, operation, change):
    """A real preflight snapshot must not authorize a stale User.

    The current User is changed in a separate committed session after the
    lifecycle preflight returns. The writer must re-resolve and atomically
    claim the active User in its append transaction, so the stale request
    context cannot commit delete/undelete.
    """
    from core.models import User
    from core import canvas_write_service as service

    with probe.Session() as db:
        owner = _seed_lifecycle(db, workspace_id="ws-owner")
        _workspace(db, "ws-moved", "default")
        app_client.users["current"] = owner

    if operation == "undelete":
        initial = app_client.client.delete("/api/canvas/probe-canvas")
        assert initial.status_code == 200, initial.text

    calls_before = len(broadcast_spy)
    before = _row_snapshot(probe.Session, "probe-canvas")
    original = service._lifecycle_preflight
    interleaved = []

    def _interleave(*args, **kwargs):
        frozen = original(*args, **kwargs)
        if not interleaved:
            with probe.Session() as db:
                current = db.get(User, owner.id)
                if change == "workspace":
                    current.workspace_id = "ws-moved"
                else:
                    current.is_active = False
                db.commit()
            interleaved.append(True)
        return frozen

    monkeypatch.setattr(service, "_lifecycle_preflight", _interleave)
    response = (
        app_client.client.delete("/api/canvas/probe-canvas")
        if operation == "delete"
        else app_client.client.post("/api/canvas/probe-canvas/undelete"))
    assert interleaved
    assert response.status_code in (403, 404, 409), response.text
    assert _row_snapshot(probe.Session, "probe-canvas") == before
    assert len(broadcast_spy) == calls_before
    with probe.Session() as db:
        current = db.get(User, owner.id)
        if change == "workspace":
            assert current.workspace_id == "ws-moved"
        else:
            assert current.is_active is False


@pytest.mark.parametrize("operation", ["delete", "undelete"])
def test_unchanged_active_actor_valid_twin(
        app_client, probe, broadcast_spy, operation):
    """The unchanged active User still produces exactly one lifecycle effect."""
    from core.models import User

    with probe.Session() as db:
        owner = _seed_lifecycle(db, workspace_id="ws-owner")
        app_client.users["current"] = owner

    if operation == "undelete":
        initial = app_client.client.delete("/api/canvas/probe-canvas")
        assert initial.status_code == 200, initial.text

    calls_before = len(broadcast_spy)
    before = _row_snapshot(probe.Session, "probe-canvas")
    response = (
        app_client.client.delete("/api/canvas/probe-canvas")
        if operation == "delete"
        else app_client.client.post("/api/canvas/probe-canvas/undelete"))
    assert response.status_code == 200, response.text
    assert response.json().get("success") is True, response.json()
    after = _row_snapshot(probe.Session, "probe-canvas")
    assert len(after) == len(before) + 1
    assert after[:-1] == before
    assert after[-1]["action_type"] == (
        "delete" if operation == "delete" else "restore")
    assert len(broadcast_spy) == calls_before + 1
    with probe.Session() as db:
        current = db.get(User, owner.id)
        assert current.is_active is True
        assert current.workspace_id == "ws-owner"


# ---------------------------------------------------------------------------
# Registered-tool / MCP consumer
# ---------------------------------------------------------------------------
def test_tool_path_ignores_model_user_id_and_uses_context_actor(probe):
    from integrations.mcp_service import mcp_service

    with probe.Session() as db:
        _seed_lifecycle(db)
        victim = _user(db, user_id="victim")
        attacker = _user(db, user_id="attacker")

    result = asyncio.run(mcp_service.execute_tool(
        "local-tools",
        "delete_canvas",
        {"user_id": victim.id, "canvas_id": "probe-canvas"},
        context={"user_id": attacker.id},
    ))
    assert isinstance(result, dict) and result.get("success") is False, result
    fresh = _fresh_rows(probe.Session, "probe-canvas")
    assert [row.action_type for row in fresh].count("delete") == 0


def test_tool_path_context_actor_wins_over_model_supplied_victim(probe):
    from integrations.mcp_service import mcp_service

    with probe.Session() as db:
        owner = _seed_lifecycle(db)
        victim = _user(db, user_id="victim")

    result = asyncio.run(mcp_service.execute_tool(
        "local-tools",
        "delete_canvas",
        {"user_id": victim.id, "canvas_id": "probe-canvas"},
        context={"user_id": owner.id, "tenant_id": "default"},
    ))
    assert isinstance(result, dict) and result.get("success") is True, result
    assert result.get("status") == "verified", result
    fresh = _fresh_rows(probe.Session, "probe-canvas")
    assert fresh[-1].action_type == "delete"
    assert fresh[-1].user_id == owner.id


def test_standard_call_tool_entry_resolves_the_verified_lifecycle(probe):
    from integrations.mcp_service import mcp_service

    with probe.Session() as db:
        owner = _seed_lifecycle(db)
        victim = _user(db, user_id="victim")

    result = asyncio.run(mcp_service.call_tool(
        "delete_canvas",
        {"user_id": victim.id, "canvas_id": "probe-canvas"},
        context={"user_id": owner.id, "tenant_id": "default"},
    ))
    assert isinstance(result, dict) and result.get("success") is True, result
    assert result.get("status") == "verified", result
    fresh = _fresh_rows(probe.Session, "probe-canvas")
    assert fresh[-1].action_type == "delete"
    assert fresh[-1].user_id == owner.id


def test_tool_path_without_trusted_context_actor_refuses(probe):
    from integrations.mcp_service import mcp_service

    with probe.Session() as db:
        _seed_lifecycle(db)

    result = asyncio.run(mcp_service.execute_tool(
        "local-tools",
        "delete_canvas",
        {"user_id": "owner", "canvas_id": "probe-canvas"},
        context={},
    ))
    assert isinstance(result, dict) and result.get("success") is False, result
    fresh = _fresh_rows(probe.Session, "probe-canvas")
    assert [row.action_type for row in fresh].count("delete") == 0


# ---------------------------------------------------------------------------
# Readback / uncertainty / no second effect
# ---------------------------------------------------------------------------
def test_missing_audit_readback_is_committed_unverified_and_no_second_effect(
        app_client, probe, monkeypatch):
    from core import canvas_write_service as service

    async def _fake_delete(*args, **kwargs):
        return {
            "success": True,
            "write_outcome": "committed",
            "canvas_id": "probe-canvas",
            "audit_id": "missing-audit-id",
            "operation_id": kwargs.get("operation_id"),
            "action_type": "delete",
            "prior_audit_id": None,
            "source_audit_id": None,
            "content_sha256": "",
        }

    monkeypatch.setattr(service, "delete_canvas", _fake_delete)
    with probe.Session() as db:
        owner = _seed_lifecycle(db)
        before = _row_ids(_rows(db, "probe-canvas"))
        app_client.users["current"] = owner

    response = app_client.client.delete("/api/canvas/probe-canvas")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("status") == "committed_unverified", body
    assert body.get("audit_id") == "missing-audit-id", body
    assert body.get("verification", {}).get("replay") == "do_not_repeat", body
    assert _row_ids(_fresh_rows(probe.Session, "probe-canvas")) == before


def test_unknown_commit_outcome_keeps_identity_and_never_claims_no_change(
        app_client, probe, monkeypatch):
    from core import canvas_write_service as service

    async def _unknown_delete(*args, **kwargs):
        return {
            "success": False,
            "write_outcome": "unknown",
            "canvas_id": "probe-canvas",
            "audit_id": "possibly-committed",
            "operation_id": kwargs.get("operation_id"),
            "action_type": "delete",
            "error": "connection lost after send",
        }

    monkeypatch.setattr(service, "delete_canvas", _unknown_delete)
    with probe.Session() as db:
        owner = _seed_lifecycle(db)
        before = _row_ids(_rows(db, "probe-canvas"))
        app_client.users["current"] = owner

    response = app_client.client.delete("/api/canvas/probe-canvas")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("status") == "effect_unknown", body
    assert body.get("audit_id") == "possibly-committed", body
    assert body.get("operation_id"), body
    assert body.get("verification", {}).get("status") == "unavailable", body
    assert body.get("verification", {}).get("replay") == "do_not_repeat", body
    assert _row_ids(_fresh_rows(probe.Session, "probe-canvas")) == before


# ---------------------------------------------------------------------------
# Verifier refutations (independent readback)
# ---------------------------------------------------------------------------
def _lifecycle_ctx(rows, *, actor, op, prior, source, digest,
                   tenant="default", workspace="", action="canvas.delete",
                   audit_id=None):
    return {
        "audit_id": audit_id or str(rows[-1].id),
        "write_outcome": "committed",
        "already_applied": False,
        "_oracle_action": action,
        "_oracle_expected_canvas_id": "probe-canvas",
        "_oracle_expected_operation_id": op,
        "_oracle_expected_prior_audit_id": prior,
        "_oracle_expected_source_audit_id": source,
        "_oracle_expected_canvas_content_sha256": digest,
        "_oracle_expected_tenant_id": tenant,
        "_oracle_expected_workspace_id": workspace,
        "_oracle_expected_actor_id": actor,
        "_oracle_require_scope_match": True,
    }


@pytest.mark.asyncio
async def test_verifier_refutes_wrong_actor_scope_operation_and_digest(
        app_client, probe):
    from core.oracle import validate

    with probe.Session() as db:
        owner = _seed_lifecycle(db, workspace_id="ws-owner")
        app_client.users["current"] = owner

    deleted = app_client.client.delete("/api/canvas/probe-canvas")
    assert deleted.status_code == 200, deleted.text
    receipt = deleted.json()
    rows = _fresh_rows(probe.Session, "probe-canvas")

    good = _lifecycle_ctx(
        rows, actor=owner.id, op=receipt["operation_id"],
        prior=receipt["prior_audit_id"], source=receipt["source_audit_id"],
        digest=receipt["content_sha256"], workspace="ws-owner")
    assert (await validate("canvas.delete", good)).verified is True

    for field, value in (
        ("_oracle_expected_actor_id", "somebody-else"),
        ("_oracle_expected_workspace_id", "ws-foreign"),
        ("_oracle_expected_operation_id", "not-the-operation"),
        ("_oracle_expected_canvas_content_sha256", "0" * 64),
    ):
        bad = dict(good)
        bad[field] = value
        verdict = await validate("canvas.delete", bad)
        assert verdict.verified is False, (field, verdict)


@pytest.mark.asyncio
async def test_verifier_refutes_a_later_lifecycle_row(app_client, probe):
    from core.oracle import validate

    with probe.Session() as db:
        owner = _seed_lifecycle(db)
        app_client.users["current"] = owner

    deleted = app_client.client.delete("/api/canvas/probe-canvas")
    assert deleted.status_code == 200, deleted.text
    receipt = deleted.json()

    with probe.Session() as db:
        _audit(db, canvas_id="probe-canvas", action_type="update",
               user_id=owner.id,
               details={"content": {"body": "later edit"}},
               created_at=datetime.now(timezone.utc) + timedelta(minutes=5))
        rows = _rows(db, "probe-canvas")

    ctx = _lifecycle_ctx(
        rows, actor=owner.id, op=receipt["operation_id"],
        prior=receipt["prior_audit_id"], source=receipt["source_audit_id"],
        digest=receipt["content_sha256"], audit_id=receipt["audit_id"])
    verdict = await validate("canvas.delete", ctx)
    assert verdict.verified is False
    assert "not the current lifecycle row" in verdict.evidence


@pytest.mark.asyncio
async def test_verifier_refutes_missing_audit(app_client, probe):
    from core.oracle import validate

    ctx = {
        "audit_id": "does-not-exist",
        "write_outcome": "committed",
        "_oracle_action": "canvas.delete",
        "_oracle_expected_canvas_id": "probe-canvas",
        "_oracle_expected_operation_id": "op",
        "_oracle_expected_actor_id": "owner",
        "_oracle_require_scope_match": True,
    }
    verdict = await validate("canvas.delete", ctx)
    assert verdict.verified is False
