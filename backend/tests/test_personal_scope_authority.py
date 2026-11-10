"""Personal NULL/default scope authority controls (scratch SQLite only)."""
from __future__ import annotations

import os

os.environ.setdefault("TESTING", "1")
os.environ.setdefault(
    "DATABASE_URL", "sqlite:////private/tmp/atom-personal-scope-scratch.db")

import uuid
from contextlib import contextmanager

import pytest
from docx import Document
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker

from api.canvas_routes import router
from core.auth import create_access_token, get_current_user
from core.canvas_authority import CanvasAuthorityError, require_active_actor
from core.database import Base, get_db
from core.deployment_audience import require_pilot_user
from core.models import Canvas, CanvasAudit, Tenant, User, Workspace
from tools.canvas_crud_tool import claim_canvas_actor


class World:
    def __init__(self, tmp_path, *, default_tenant=True, foreign=True):
        self.engine = create_engine(
            f"sqlite:///{tmp_path}/scope.db",
            connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        s = uuid.uuid4().hex[:8]
        self.default_tenant = "default"
        self.default_ws = "default"
        self.foreign_tenant = f"tenant-f-{s}"
        self.foreign_ws = f"ws-f-{s}"
        with self.Session() as db:
            if default_tenant:
                db.add(Tenant(id="default", name="Default",
                              subdomain=f"d-{s}", edition="personal",
                              is_active=True))
                db.add(Workspace(id="default", name="Default",
                                 tenant_id="default"))
            if foreign:
                db.add(Tenant(id=self.foreign_tenant, name="F",
                              subdomain=f"f-{s}", edition="personal",
                              is_active=True))
                db.add(Workspace(id=self.foreign_ws, name="FW",
                                 tenant_id=self.foreign_tenant))
            db.commit()
        self.admin = f"admin-{s}"
        self.opaque = f"opaque-{s}"
        self.inactive = f"inactive-{s}"
        with self.Session() as db:
            db.add(User(
                id=self.admin, tenant_id=None, workspace_id=None,
                email="admin@example.com", hashed_password="x",
                first_name="Bootstrap", last_name="Admin", role="workspace_admin",
                status="active", is_active=True))
            if foreign:
                db.add(User(
                    id=self.opaque, tenant_id=self.foreign_tenant,
                    workspace_id=self.foreign_ws,
                    email=f"{self.opaque}@example.invalid",
                    hashed_password="x", first_name="O", last_name="User",
                    role="member", status="active", is_active=True))
            db.add(User(
                id=self.inactive, tenant_id=None, workspace_id=None,
                email=f"{self.inactive}@example.invalid", hashed_password="x",
                first_name="I", last_name="User", role="member",
                status="active", is_active=False))
            db.commit()

    def token(self, uid):
        with self.Session() as db:
            user = db.query(User).filter(User.id == uid).one()
            return create_access_token({"sub": user.id}, user=user)

    def canvas(self, *, tenant="default", workspace="default", content=None,
               owner=None):
        owner = owner or self.admin
        cid = f"canvas-{uuid.uuid4().hex[:10]}"
        aid = f"audit-{uuid.uuid4().hex[:10]}"
        with self.Session() as db:
            db.add(Canvas(
                id=cid, tenant_id=tenant, workspace_id=workspace,
                created_by=owner, name="Scope doc",
                canvas_type="docs",
                content={"title": "Scope doc", "content": content or (
                    "# Heading\n\nIntro text.\n\n- One\n- Two\n\n"
                    "| A | B |\n|---|---|\n| 1 | 2 |\n")},
                status="active"))
            db.add(CanvasAudit(
                id=aid, canvas_id=cid, tenant_id=tenant, user_id=owner,
                canvas_type="docs", action_type="update",
                details_json={
                    "title": "Scope doc",
                    "content": content or (
                        "# Heading\n\nIntro text.\n\n- One\n- Two\n\n"
                        "| A | B |\n|---|---|\n| 1 | 2 |\n"),
                    "review_status": "accepted",
                }))
            db.commit()
        return cid, aid


def client(world, user_id):
    app = FastAPI()
    app.include_router(router)

    def override_db():
        db = world.Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_pilot_user] = lambda: None
    c = TestClient(app)
    c.headers["Authorization"] = f"Bearer {world.token(user_id)}"
    return c


def _export(world, user_id, canvas_id, audit_id):
    return client(world, user_id).get(
        f"/api/canvas/{canvas_id}/export/office",
        params={"format": "docx", "expected_audit_id": audit_id})


def test_bootstrap_null_raw_scope_exports_default_canvas(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_DEPLOYMENT_AUDIENCE", "development")
    w = World(tmp_path)
    cid, aid = w.canvas(tenant="default", workspace="default")
    r = _export(w, w.admin, cid, aid)
    assert r.status_code == 200, r.text
    Document(__import__("io").BytesIO(r.content))
    with w.Session() as db:
        actor = db.query(User).filter(User.id == w.admin).one()
        assert actor.tenant_id is None and actor.workspace_id is None


def test_null_actor_foreign_real_tenant_workspace_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_DEPLOYMENT_AUDIENCE", "development")
    w = World(tmp_path)
    cid, aid = w.canvas(tenant=w.foreign_tenant, workspace=w.foreign_ws)
    r = _export(w, w.admin, cid, aid)
    assert r.status_code == 403, r.text
    assert "content-disposition" not in r.headers


def test_inactive_unknown_and_missing_default_tenant_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_DEPLOYMENT_AUDIENCE", "development")
    w = World(tmp_path)
    cid, aid = w.canvas()
    assert _export(w, w.inactive, cid, aid).status_code == 403
    with w.Session() as db:
        with pytest.raises(CanvasAuthorityError) as exc:
            require_active_actor(db, "user-does-not-exist")
        assert exc.value.code == "CANVAS_ACTOR_REFUSED"

    missing = tmp_path / "missing"
    missing.mkdir(parents=True, exist_ok=True)
    w2 = World(missing, default_tenant=False)
    with w2.Session() as db:
        with pytest.raises(CanvasAuthorityError) as exc:
            require_active_actor(db, w2.admin)
        assert exc.value.code == "CANVAS_ACTOR_SCOPE_MISSING"


@pytest.mark.parametrize("moved", ["default", ""])
def test_null_raw_scope_transition_cas_refuses(tmp_path, moved):
    w = World(tmp_path)
    with w.Session() as db:
        actor = require_active_actor(db, w.admin)
        assert actor["tenant_id"] is None
        with w.Session() as peer:
            peer.query(User).filter(User.id == w.admin).update(
                {"tenant_id": moved, "workspace_id": moved},
                synchronize_session=False)
            peer.commit()
        assert claim_canvas_actor(db, actor) is False


def test_real_opaque_scope_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_DEPLOYMENT_AUDIENCE", "development")
    w = World(tmp_path)
    with w.Session() as db:
        actor = require_active_actor(db, w.opaque)
        assert actor["tenant_id"] == w.foreign_tenant
        assert actor["workspace_id"] == w.foreign_ws
        assert actor["effective_tenant_id"] == w.foreign_tenant
        assert actor["effective_workspace_id"] == w.foreign_ws
        assert claim_canvas_actor(db, actor) is True
    cid, aid = w.canvas(
        tenant=w.foreign_tenant, workspace=w.foreign_ws, owner=w.opaque)
    r = _export(w, w.opaque, cid, aid)
    assert r.status_code == 200, r.text


def test_coding_and_sheets_create_use_effective_default_scope(tmp_path):
    w = World(tmp_path)
    from core.canvas_coding_service import CodingCanvasService
    from core.canvas_sheets_service import SpreadsheetCanvasService
    with w.Session() as db:
        coding = CodingCanvasService(db).create_coding_canvas(
            user_id=w.admin, repo="example/repo", branch="main")
        sheet = SpreadsheetCanvasService(db).create_spreadsheet_canvas(
            user_id=w.admin, title="Scope sheet", data={"A1": "x"})
    assert coding.get("success") is True, coding
    assert sheet.get("success") is True, sheet
    with w.Session() as db:
        for cid in (coding["canvas_id"], sheet["canvas_id"]):
            row = db.query(Canvas).filter(Canvas.id == cid).one()
            assert row.tenant_id == "default"
            assert row.workspace_id == "default"
            audit = db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == cid,
                CanvasAudit.action_type == "create").one()
            assert audit.tenant_id == "default"
