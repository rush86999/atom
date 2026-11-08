"""Independent root scope twins for mounted Canvas delete/undelete routes.

Real scratch SQLite with FK enforcement, real route/writer/service/readback;
current-user dependency is injected (not a normal login/browser qualification).
No future receipt shape is invented here. Assert the existing owner/coeditor
policy and zero durable changes for current foreign scope, with immutable old
history. Root source-bound negative executions live in the retained packets.
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
    import core.models  # register actual tables before create_all
    from core.models_registration import Base

    engine = create_engine(
        f"sqlite:///{tmp_path / 'canvas_lifecycle_probe.db'}",
        connect_args={"check_same_thread": False},
    )
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def _foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")
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



@pytest.fixture(autouse=True)
def local_broadcast_only(monkeypatch):
    calls = []
    async def record(*args, **kwargs):
        calls.append((args, kwargs))
    monkeypatch.setattr("core.websockets.manager.broadcast", record)
    return calls


def _snapshot(Session, canvas_id):
    with Session() as db:
        rows = _rows(db, canvas_id)
        return [{c.name: getattr(row, c.name) for c in row.__table__.columns}
                for row in rows]


def _invoke(client, operation):
    if operation == "delete":
        return client.delete("/api/canvas/probe-canvas")
    return client.post("/api/canvas/probe-canvas/undelete")


def _prepare_operation(app_client, probe, operation, coeditor=False):
    with probe.Session() as db:
        owner = _seed_lifecycle(db, tenant_id="tenant-owner", workspace_id="ws-owner")
        actor = owner
        if coeditor:
            actor = _user(db, user_id="coeditor", tenant_id="tenant-owner", workspace_id="ws-owner")
            _audit(db, canvas_id="probe-canvas", action_type="update", user_id=actor.id,
                   tenant_id="tenant-owner", details={"content": {"body": "legitimate historical edit"}})
        app_client.users["current"] = owner
    if operation == "undelete":
        initial = _invoke(app_client.client, "delete")
        assert initial.status_code == 200 and initial.json().get("success") is True, initial.text
    app_client.users["current"] = actor
    return actor


@pytest.mark.parametrize("scope", ["tenant", "workspace"])
@pytest.mark.parametrize("operation", ["delete", "undelete"])
def test_former_coeditor_current_foreign_scope_has_zero_effect(app_client, probe, scope, operation):
    from core.models import User
    actor = _prepare_operation(app_client, probe, operation, coeditor=True)
    with probe.Session() as db:
        actor = db.get(User, actor.id)
        tenant = "tenant-other" if scope == "tenant" else "tenant-owner"
        _tenant(db, tenant)
        _workspace(db, "ws-other", tenant)
        actor.tenant_id = tenant
        actor.workspace_id = "ws-other"
        db.commit(); db.refresh(actor)
        app_client.users["current"] = actor
    before = _snapshot(probe.Session, "probe-canvas")
    response = _invoke(app_client.client, operation)
    after = _snapshot(probe.Session, "probe-canvas")
    observed = {"scope": scope, "operation": operation, "http": response.status_code,
                "body": response.json(), "before_count": len(before), "after_count": len(after),
                "latest_action": after[-1]["action_type"]}
    assert response.status_code in (403, 404), observed
    assert after == before, observed


@pytest.mark.parametrize("coeditor", [False, True])
@pytest.mark.parametrize("operation", ["delete", "undelete"])
def test_supported_owner_and_same_scope_coeditor_still_work(app_client, probe, coeditor, operation):
    _prepare_operation(app_client, probe, operation, coeditor=coeditor)
    before = _snapshot(probe.Session, "probe-canvas")
    response = _invoke(app_client.client, operation)
    after = _snapshot(probe.Session, "probe-canvas")
    assert response.status_code == 200 and response.json().get("success") is True, response.text
    assert len(after) == len(before) + 1
    assert after[:-1] == before
    assert after[-1]["action_type"] == ("delete" if operation == "delete" else "restore")
    assert after[-1]["tenant_id"] == "tenant-owner"


def test_stranger_without_authorship_is_still_refused(app_client, probe):
    _prepare_operation(app_client, probe, "delete")
    with probe.Session() as db:
        actor = _user(db, user_id="stranger", tenant_id="tenant-owner", workspace_id="ws-owner")
        app_client.users["current"] = actor
    before = _snapshot(probe.Session, "probe-canvas")
    response = _invoke(app_client.client, "delete")
    assert response.status_code == 404, response.text
    assert _snapshot(probe.Session, "probe-canvas") == before


# Root forced actor-CAS interleavings, promoted from the executed independent probe.
@pytest.mark.parametrize('operation',['delete','undelete'])
@pytest.mark.parametrize('change',['tenant','workspace','status','inactive'])
def test_actor_change_during_guard_has_no_effect(app_client,probe,monkeypatch,operation,change,local_broadcast_only):
    from core.models import User
    import tools.canvas_crud_tool as tool
    actor=_prepare_operation(app_client,probe,operation)
    with probe.Session() as db:
        _tenant(db,'tenant-new')
        _workspace(db,'ws-new','tenant-new')
        _workspace(db,'ws-moved','tenant-owner')
    before=_snapshot(probe.Session,'probe-canvas');calls_before=len(local_broadcast_only)
    original=tool._claim_canvas_actor;done=[]
    def interleave(db,*args,**kwargs):
        if not done:
            with probe.Session() as peer:
                current=peer.get(User,actor.id)
                if change=='tenant':
                    current.tenant_id='tenant-new';current.workspace_id='ws-new'
                elif change=='workspace':current.workspace_id='ws-moved'
                elif change=='status':current.status='suspended'
                else:current.is_active=False
                peer.commit()
            done.append(True)
        return original(db,*args,**kwargs)
    monkeypatch.setattr(tool,'_claim_canvas_actor',interleave)
    response=_invoke(app_client.client,operation)
    assert done
    assert response.status_code in (403,404,409),(response.status_code,response.json())
    assert _snapshot(probe.Session,'probe-canvas')==before
    assert len(local_broadcast_only)==calls_before
    with probe.Session() as peer:
        current=peer.get(User,actor.id)
        if change=='tenant':assert current.tenant_id=='tenant-new' and current.workspace_id=='ws-new'
        elif change=='workspace':assert current.workspace_id=='ws-moved'
        elif change=='status':assert current.status=='suspended'
        else:assert current.is_active is False
