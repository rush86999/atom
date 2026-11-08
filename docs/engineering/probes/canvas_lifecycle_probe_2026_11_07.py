"""Author-only failure-first probe for the canvas delete/undelete family.

Status: NOT RUN. This file is an author artifact for
`docs/engineering/CANVAS_LIFECYCLE_WORKORDER_2026_11_07.md`. It is expected to
be RED on current main `8ded00232` because the verified delete/undelete
contract does not exist yet. Do not run it in the inventory-authoring phase.

It uses real mounted routes, real SQLite tables, real writer/service/verifier
code, and independent fresh sessions for readback. It does not stub HTTP
responses and does not use a fake durability store. The only spies are for
WebSocket side-effect counting and one controlled scope-move seam; neither
substitutes for durable state.

Run later, only after root authorization, from the repo root:

    PYTHONPATH=backend pytest -q \
      docs/engineering/probes/canvas_lifecycle_probe_2026_11_07.py
"""
from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# ---------------------------------------------------------------------------
# Real scratch database (file-backed SQLite; fresh sessions share the file)
# ---------------------------------------------------------------------------
@pytest.fixture
def probe(tmp_path, monkeypatch):
    from core.models_registration import Base

    engine = create_engine(
        f"sqlite:///{tmp_path / 'canvas_lifecycle_probe.db'}",
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
        yield SimpleNamespace(client=client, users=users, Session=probe.Session)


# ---------------------------------------------------------------------------
# Row factories (real Tenant/Workspace/User/Canvas/CanvasAudit rows)
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
            workspace_id=None, content=None, canvas_type="generic",
            name="Probe Canvas"):
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
        name=name,
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
                    content=None):
    content = content if content is not None else {
        "to": "a@b.c", "subject": "Probe", "body": "pre-delete body"}
    owner = _user(db, user_id=owner_id, tenant_id=tenant_id,
                  workspace_id=workspace_id)
    _canvas(db, canvas_id=canvas_id, owner_id=owner.id,
            tenant_id=tenant_id, workspace_id=workspace_id,
            content=content)
    base = datetime.now(timezone.utc) - timedelta(minutes=3)
    _audit(db, canvas_id=canvas_id, action_type="create", user_id=owner.id,
           tenant_id=tenant_id, details={"content": content, "title": "Probe"},
           created_at=base)
    _audit(db, canvas_id=canvas_id, action_type="update", user_id=owner.id,
           tenant_id=tenant_id, details={"content": content, "title": "Probe"},
           created_at=base + timedelta(minutes=1))
    return owner


def _rows(db, canvas_id):
    from core.models import CanvasAudit

    return (db.query(CanvasAudit)
            .filter(CanvasAudit.canvas_id == canvas_id)
            .order_by(CanvasAudit.created_at, CanvasAudit.id)
            .all())


def _latest(db, canvas_id):
    rows = _rows(db, canvas_id)
    return rows[-1] if rows else None


def _fresh_rows(Session, canvas_id):
    with Session() as db:
        return _rows(db, canvas_id)


def _broadcast_spy(monkeypatch):
    calls = []

    async def _record(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(
        "tools.canvas_crud_tool._broadcast_canvas_update", _record)
    return calls


# ---------------------------------------------------------------------------
# Positive: ordinary self-owner / same-scope / null-default
# ---------------------------------------------------------------------------
def test_self_owner_delete_has_verified_receipt_and_fresh_readback(
        app_client, probe):
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

    fresh = _fresh_rows(probe.Session, "probe-canvas")
    assert fresh[-1].action_type == "delete"
    assert fresh[-1].id == body["audit_id"]
    assert len(fresh) == len(before) + 1
    assert [r.id for r in fresh[:-1]] == [r.id for r in before]


def test_undelete_restores_exact_prior_content_and_source_binding(
        app_client, probe):
    with probe.Session() as db:
        owner = _seed_lifecycle(db)
        prior = _latest(db, "probe-canvas")
        prior_content = dict(prior.details_json["content"])
        app_client.users["current"] = owner

    first = app_client.client.delete("/api/canvas/probe-canvas")
    assert first.status_code == 200, first.text
    tombstone_id = first.json()["audit_id"]

    response = app_client.client.post("/api/canvas/probe-canvas/undelete")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("status") == "verified", body
    assert body.get("audit_id"), body
    assert body.get("operation_id"), body
    assert body.get("restored_from_tombstone_id") == tombstone_id, body
    assert body.get("content_sha256"), body

    fresh = _fresh_rows(probe.Session, "probe-canvas")
    assert fresh[-1].action_type == "restore"
    assert fresh[-1].id == body["audit_id"]
    assert (fresh[-1].details_json or {}).get("content") == prior_content
    assert fresh[-1].tenant_id == "default"
    assert any(r.id == tombstone_id for r in fresh)


def test_same_scope_coeditor_is_allowed_under_existing_policy(
        app_client, probe):
    with probe.Session() as db:
        owner = _seed_lifecycle(db, workspace_id="ws-shared")
        coeditor = _user(db, user_id="coeditor", tenant_id="default",
                         workspace_id="ws-shared")
        _audit(db, canvas_id="probe-canvas", action_type="update",
               user_id=coeditor.id, details={"content": "coeditor"})
        app_client.users["current"] = coeditor

    response = app_client.client.delete("/api/canvas/probe-canvas")
    assert response.status_code == 200, response.text
    assert response.json().get("status") == "verified", response.json()


def test_null_default_single_tenant_is_compatible(app_client, probe):
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


# ---------------------------------------------------------------------------
# Negative: foreign principal / foreign scope
# ---------------------------------------------------------------------------
def test_foreign_user_without_authorship_gets_404(app_client, probe):
    with probe.Session() as db:
        _seed_lifecycle(db)
        stranger = _user(db, user_id="stranger")
        before = _rows(db, "probe-canvas")
        app_client.users["current"] = stranger

    response = app_client.client.delete("/api/canvas/probe-canvas")
    assert response.status_code == 404, response.text
    fresh = _fresh_rows(probe.Session, "probe-canvas")
    assert [r.id for r in fresh] == [r.id for r in before]


def test_foreign_tenant_coeditor_is_refused_before_effect(app_client, probe):
    with probe.Session() as db:
        _seed_lifecycle(db, tenant_id="tenant-owner")
        foreign = _user(db, user_id="foreign-tenant", tenant_id="tenant-other")
        _audit(db, canvas_id="probe-canvas", action_type="update",
               user_id=foreign.id, tenant_id="tenant-other",
               details={"content": "foreign authored"})
        before = _rows(db, "probe-canvas")
        app_client.users["current"] = foreign

    response = app_client.client.delete("/api/canvas/probe-canvas")
    assert response.status_code in (403, 404), response.text
    fresh = _fresh_rows(probe.Session, "probe-canvas")
    assert [r.id for r in fresh] == [r.id for r in before]


def test_foreign_workspace_coeditor_is_refused_before_effect(
        app_client, probe):
    with probe.Session() as db:
        _seed_lifecycle(db, workspace_id="ws-owner")
        foreign = _user(db, user_id="foreign-ws", tenant_id="default",
                        workspace_id="ws-foreign")
        _audit(db, canvas_id="probe-canvas", action_type="update",
               user_id=foreign.id, details={"content": "foreign authored"})
        before = _rows(db, "probe-canvas")
        app_client.users["current"] = foreign

    response = app_client.client.delete("/api/canvas/probe-canvas")
    assert response.status_code in (403, 404), response.text
    fresh = _fresh_rows(probe.Session, "probe-canvas")
    assert [r.id for r in fresh] == [r.id for r in before]


# ---------------------------------------------------------------------------
# Replay / conflict / CAS
# ---------------------------------------------------------------------------
def test_delete_same_operation_replays_one_tombstone(app_client, probe,
                                                     monkeypatch):
    calls = _broadcast_spy(monkeypatch)
    with probe.Session() as db:
        owner = _seed_lifecycle(db)
        app_client.users["current"] = owner

    first = app_client.client.delete(
        "/api/canvas/probe-canvas",
        params={"operation_id": "op-delete-1"})
    assert first.status_code == 200, first.text
    second = app_client.client.delete(
        "/api/canvas/probe-canvas",
        params={"operation_id": "op-delete-1"})
    assert second.status_code == 200, second.text
    assert second.json().get("audit_id") == first.json().get("audit_id")
    fresh = _fresh_rows(probe.Session, "probe-canvas")
    assert [r.action_type for r in fresh].count("delete") == 1
    assert len(calls) == 1


def test_undelete_same_operation_replays_one_restore(app_client, probe,
                                                     monkeypatch):
    calls = _broadcast_spy(monkeypatch)
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
    fresh = _fresh_rows(probe.Session, "probe-canvas")
    assert [r.action_type for r in fresh].count("restore") == 1
    assert len(calls) == 2  # delete broadcast + one undelete broadcast


def test_delete_replay_with_different_operation_is_idempotent(app_client,
                                                             probe):
    with probe.Session() as db:
        owner = _seed_lifecycle(db)
        app_client.users["current"] = owner

    first = app_client.client.delete(
        "/api/canvas/probe-canvas", params={"operation_id": "op-a"})
    assert first.status_code == 200, first.text
    second = app_client.client.delete(
        "/api/canvas/probe-canvas", params={"operation_id": "op-b"})
    assert second.status_code == 200, second.text
    assert second.json().get("audit_id") == first.json().get("audit_id")
    assert second.json().get("already_applied") is True
    fresh = _fresh_rows(probe.Session, "probe-canvas")
    assert [r.action_type for r in fresh].count("delete") == 1


def test_undelete_non_deleted_canvas_is_a_conflict(app_client, probe):
    with probe.Session() as db:
        owner = _seed_lifecycle(db)
        before = _rows(db, "probe-canvas")
        app_client.users["current"] = owner

    response = app_client.client.post("/api/canvas/probe-canvas/undelete")
    assert response.status_code == 409, response.text
    fresh = _fresh_rows(probe.Session, "probe-canvas")
    assert [r.id for r in fresh] == [r.id for r in before]


def test_delete_expected_prior_mismatch_is_zero_effect(app_client, probe):
    with probe.Session() as db:
        owner = _seed_lifecycle(db)
        before = _rows(db, "probe-canvas")
        app_client.users["current"] = owner

    response = app_client.client.delete(
        "/api/canvas/probe-canvas",
        params={"expected_prior_audit_id": "not-the-latest"})
    assert response.status_code == 409, response.text
    fresh = _fresh_rows(probe.Session, "probe-canvas")
    assert [r.id for r in fresh] == [r.id for r in before]


def test_scope_move_before_effect_refuses_and_preserves_winner(
        app_client, probe, monkeypatch):
    from tools import canvas_crud_tool as crud

    original = crud.canvas_write_scope_error
    moved = {"done": False}

    def _check_then_move(*args, **kwargs):
        result = original(*args, **kwargs)
        if result is None and not moved["done"]:
            moved["done"] = True
            with probe.Session() as other:
                from core.models import Canvas
                row = other.query(Canvas).filter(
                    Canvas.id == "probe-canvas").one()
                row.workspace_id = "ws-moved"
                other.commit()
        return result

    monkeypatch.setattr(crud, "canvas_write_scope_error", _check_then_move)
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
            r.action_type == "delete" for r in _rows(db, "probe-canvas"))


# ---------------------------------------------------------------------------
# Registered-tool parallel consumer
# ---------------------------------------------------------------------------
def test_tool_path_uses_context_user_not_model_supplied_user_id(probe):
    from integrations.mcp_service import mcp_service

    with probe.Session() as db:
        _seed_lifecycle(db)
        attacker = _user(db, user_id="attacker")
        victim = _user(db, user_id="owner")
        before = _rows(db, "probe-canvas")

    result = __import__("asyncio").run(mcp_service.execute_tool(
        "local-tools",
        "delete_canvas",
        {"user_id": victim.id, "canvas_id": "probe-canvas"},
        context={"user_id": attacker.id},
    ))
    fresh = _fresh_rows(probe.Session, "probe-canvas")
    assert result.get("success") is False if isinstance(result, dict) else False
    assert [r.id for r in fresh] == [r.id for r in before]
