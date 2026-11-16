"""Installed-instance DATA privacy — publication is not a grant.

Root counter (real HTTP): an owner scaffolded/published/installed an app,
shared it publicly, and a FOREIGN normal user read the installer's instance
records (`GET /api/mini-apps/instances/{id}/records?series=...` → 200 with the
row). The same public shortcut covered record series/query/count/get, assets
(list/download), and update-check; the agent tool record target additionally
let the ORIGINAL APP AUTHOR read/write another installer's private instance.

These are scratch-DB integration regressions through the REAL route handlers
and the REAL ``tools.mini_app_tool`` record handlers:

* installed-instance data follows the accepted canvas policy (active
  authoritative User, owner or historical co-editor, current tenant/workspace,
  active canvas);
* publication, approval and ``MiniApp.created_by`` are NEVER instance-data
  grants;
* mutations stay STRICT instance-owner, actor/target-frozen before the effect;
* public app LISTING / definition / share / approved install keep working,
  and a legitimate installer can read/write its own copy.

Scratch only: TESTING=1 + an explicit per-test SQLite file. No servers beyond
the in-process TestClient, no models/providers, no live DB, no guests.
"""
from __future__ import annotations

import contextlib
import os
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")

from core.models import (  # noqa: E402
    Canvas,
    CanvasAudit,
    CanvasRecord,
    CanvasState,
    MiniApp,
    MiniAppAsset,
    Tenant,
    User,
    Workspace,
)
from core.models_registration import Base  # noqa: E402


class World:
    """One scratch SQLite file; every actor/app/canvas is a real row."""

    def __init__(self, tmp_path):
        self.tmp_path = tmp_path
        self.engine = create_engine(
            f"sqlite:///{tmp_path}/instance_privacy.db",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        suffix = uuid.uuid4().hex[:8]
        with self.Session() as db:
            db.add_all([
                Tenant(id="tenant-1", name="T1", subdomain=f"t1-{suffix}",
                       edition="personal", is_active=True),
                Tenant(id="tenant-2", name="T2", subdomain=f"t2-{suffix}",
                       edition="personal", is_active=True),
            ])
            db.add_all([
                Workspace(id="ws-1", name="W1", tenant_id="tenant-1"),
                Workspace(id="ws-1b", name="W1b", tenant_id="tenant-1"),
                Workspace(id="ws-2", name="W2", tenant_id="tenant-2"),
            ])
            db.commit()
        self.owner = self.actor("u-owner")
        self.stranger = self.actor("u-stranger")
        self.author = self.actor("u-author")
        self.collab = self.actor("u-collab")
        self.frozen = self.actor("u-frozen", active=False)
        self.outsider = self.actor("u-outsider", tenant_id="tenant-2",
                                   workspace_id="ws-2")

    def actor(self, user_id, *, tenant_id="tenant-1", workspace_id="ws-1",
              active=True):
        with self.Session() as db:
            db.add(User(
                id=user_id, tenant_id=tenant_id, workspace_id=workspace_id,
                email=f"{user_id}@privacy.test", hashed_password="x",
                first_name="P", last_name="R", role="member",
                status="active", is_active=active,
            ))
            db.commit()
        return user_id

    def app(self, *, author="u-author", public=True, approved=True,
            status="published"):
        app_id = f"app-{uuid.uuid4().hex[:10]}"
        with self.Session() as db:
            db.add(MiniApp(
                id=app_id, tenant_id="tenant-1", workspace_id="ws-1",
                created_by=author, name="Tracker", description="d",
                version="1.0.0", status=status,
                manifest={
                    "declared_scopes": ["*"], "skills": [], "mcp_servers": [],
                    "integrations": [], "dependencies": [],
                    "base_image": "python:3.11-slim", "assets": [],
                    "storage": {"enabled": True, "backend": "local"},
                    "db": {"enabled": True},
                    "initial_state": {},
                    "blueprint": {"content": {}, "style": {},
                                  "logic_source": "", "logic_language": "python",
                                  "component_installations": []},
                },
                blueprint_canvas_id=f"src-{uuid.uuid4().hex[:10]}",
                is_public=public,
                is_approved=approved,
                share_token="tok-" + uuid.uuid4().hex[:8] if public else None,
            ))
            db.commit()
        return app_id

    def canvas(self, canvas_id):
        with self.Session() as db:
            return db.query(Canvas).filter(Canvas.id == canvas_id).first()

    def move_canvas(self, canvas_id, *, tenant_id, workspace_id):
        with self.Session() as db:
            row = db.query(Canvas).filter(Canvas.id == canvas_id).one()
            row.tenant_id = tenant_id
            row.workspace_id = workspace_id
            db.commit()

    def add_collaborator(self, canvas_id, user_id):
        with self.Session() as db:
            db.add(CanvasAudit(
                id=str(uuid.uuid4()), canvas_id=canvas_id, tenant_id="tenant-1",
                user_id=user_id, canvas_type="mini_app",
                action_type="update", details_json={"title": "collab"},
            ))
            db.commit()

    def tombstone(self, canvas_id):
        from datetime import datetime, timedelta, timezone

        with self.Session() as db:
            tenant = db.query(Canvas).filter(Canvas.id == canvas_id).one().tenant_id
            db.add(CanvasAudit(
                id=str(uuid.uuid4()), canvas_id=canvas_id, tenant_id=tenant,
                user_id="u-owner", canvas_type="mini_app", action_type="delete",
                details_json={"canvas_id": canvas_id},
                created_at=datetime.now(timezone.utc) + timedelta(seconds=30),
            ))
            db.commit()

    def counts(self, canvas_id):
        with self.Session() as db:
            return {
                "records": db.query(CanvasRecord).filter(
                    CanvasRecord.canvas_id == canvas_id).count(),
                "assets": db.query(MiniAppAsset).filter(
                    MiniAppAsset.canvas_id == canvas_id).count(),
                "audits": db.query(CanvasAudit).filter(
                    CanvasAudit.canvas_id == canvas_id).count(),
            }

    def record_ids(self, canvas_id):
        with self.Session() as db:
            return [r.id for r in db.query(CanvasRecord).filter(
                CanvasRecord.canvas_id == canvas_id).all()]


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


@pytest.fixture
def api(world, monkeypatch):
    """Real mini_app_routes handlers over the scratch DB with a real actor."""
    from api.mini_app_routes import router
    from core.auth import get_current_user
    from core.database import get_db

    holder = {"user": None}

    def override_db():
        db = world.Session()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: holder["user"]
    client = TestClient(app)
    client.holder = holder

    @contextlib.contextmanager
    def _tool_db():
        db = world.Session()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr("core.database.get_db_session", _tool_db)
    return client


def _as(client, user_id):
    from types import SimpleNamespace

    client.holder["user"] = SimpleNamespace(
        id=user_id, is_active=True, is_authenticated=True, role="member")
    return client


@pytest.fixture
def installed(world, api):
    """Public+approved app installed by ``owner`` through the real route."""
    app_id = world.app()
    _as(api, world.owner)
    r = api.post(f"/api/mini-apps/{app_id}/install")
    assert r.status_code == 200, r.text
    return app_id, r.json()["canvas_id"]


def _append_as(client, user_id, canvas_id, series="s", data=None):
    return _as(client, user_id).post(
        f"/api/mini-apps/instances/{canvas_id}/records",
        json={"series": series, "data": data or {"v": 1}})


async def _tool_query(user_id, canvas_id, **extra):
    from tools.mini_app_tool import mini_app_db_query

    return await mini_app_db_query(
        {"canvas_id": canvas_id, "op": "query", "series": "s", **extra},
        {"user_id": user_id, "tier": "supervised"})


async def _tool_write(user_id, canvas_id, data=None):
    from tools.mini_app_tool import mini_app_db_write

    return await mini_app_db_write(
        {"canvas_id": canvas_id, "op": "append", "series": "s",
         "data": data or {"v": 99}},
        {"user_id": user_id, "tier": "supervised"})


# ---------------------------------------------------------------------------
# Public instances: publication/approval never grants installed data
# ---------------------------------------------------------------------------
class TestPublicInstanceDataIsPrivate:
    def test_stranger_cannot_read_public_instance_records(self, world, api, installed):
        _, cid = installed
        assert _append_as(api, world.owner, cid, data={"secret": 1}).status_code == 200
        before = world.counts(cid)

        _as(api, world.stranger)
        reads = [
            api.get(f"/api/mini-apps/instances/{cid}/records", params={"series": "s"}),
            api.get(f"/api/mini-apps/instances/{cid}/records/series"),
            api.post(f"/api/mini-apps/instances/{cid}/records/query",
                     json={"series": "s"}),
            api.post(f"/api/mini-apps/instances/{cid}/records/count",
                     json={"series": "s"}),
        ]
        rid = world.record_ids(cid)[0]
        reads.append(api.get(
            f"/api/mini-apps/instances/{cid}/records/{rid}", params={"series": "s"}))
        for resp in reads:
            assert resp.status_code == 404, resp.text
            assert "records" not in resp.json() and "count" not in resp.json()
        assert world.counts(cid) == before

    def test_stranger_cannot_read_public_instance_assets_or_update(
            self, world, api, installed):
        _, cid = installed
        _as(api, world.owner)
        up = api.post(f"/api/mini-apps/instances/{cid}/assets",
                      data={"key": "report.txt"},
                      files={"file": ("report.txt", b"payload", "text/plain")})
        assert up.status_code == 200, up.text
        before = world.counts(cid)

        _as(api, world.stranger)
        assert api.get(f"/api/mini-apps/instances/{cid}/assets").status_code == 404
        dl = api.get(f"/api/mini-apps/instances/{cid}/assets/report.txt")
        assert dl.status_code == 404 and b"payload" not in dl.content
        assert api.get(f"/api/mini-apps/instances/{cid}/update-check").status_code == 404
        assert world.counts(cid) == before

    def test_unapproved_public_instance_also_private(self, world, api):
        """Approval state is irrelevant to instance-data authorization."""
        app_id = world.app(public=True, approved=False)
        _as(api, world.owner)
        # unpublished/unapproved install is refused, so install it while
        # approved then revoke approval (same canvas, same data).
        approved_app = world.app(public=True, approved=True)
        inst = api.post(f"/api/mini-apps/{approved_app}/install")
        assert inst.status_code == 200
        cid = inst.json()["canvas_id"]
        assert _append_as(api, world.owner, cid, data={"x": 1}).status_code == 200
        _as(api, world.stranger)
        # pending-review app definition/install is separate; instance data is
        # private regardless of the app row's approval flag.
        assert api.get(f"/api/mini-apps/instances/{cid}/records",
                       params={"series": "s"}).status_code == 404
        assert app_id  # unapproved app never becomes an instance here

    def test_public_definition_still_visible(self, world, api, installed):
        app_id, cid = installed
        _as(api, world.stranger)
        listing = api.get("/api/mini-apps")
        assert listing.status_code == 200
        assert app_id in {a["id"] for a in listing.json()["apps"]}
        definition = api.get(f"/api/mini-apps/{app_id}")
        assert definition.status_code == 200
        assert definition.json()["app"]["id"] == app_id
        # ... but never the installed-instance data.
        assert api.get(f"/api/mini-apps/instances/{cid}/records",
                       params={"series": "s"}).status_code == 404


# ---------------------------------------------------------------------------
# Private instances
# ---------------------------------------------------------------------------
class TestPrivateInstance:
    def test_stranger_denied_on_private_instance(self, world, api, installed):
        app_id2 = world.app(public=False, approved=False, author=world.owner)
        _as(api, world.owner)
        # Owner installs its own private app.
        inst = api.post(f"/api/mini-apps/{app_id2}/install")
        assert inst.status_code == 200, inst.text
        cid = inst.json()["canvas_id"]
        assert _append_as(api, world.owner, cid).status_code == 200

        _as(api, world.stranger)
        assert api.get(f"/api/mini-apps/instances/{cid}/records",
                       params={"series": "s"}).status_code == 404
        assert api.get(f"/api/mini-apps/instances/{cid}/assets").status_code == 404


# ---------------------------------------------------------------------------
# Original app author: no instance-data shortcut
# ---------------------------------------------------------------------------
class TestAppAuthorNoShortcut:
    @pytest.mark.asyncio
    async def test_author_tool_read_denied(self, world, api, installed):
        _, cid = installed
        assert _append_as(api, world.owner, cid).status_code == 200
        before = world.counts(cid)

        result = await _tool_query(world.author, cid)

        assert result["success"] is False
        assert result["error_code"] == "CANVAS_NOT_AUTHORIZED"
        assert "records" not in result
        assert world.counts(cid) == before

    @pytest.mark.asyncio
    async def test_author_tool_write_denied_without_effect(self, world, api, installed):
        _, cid = installed
        assert _append_as(api, world.owner, cid).status_code == 200
        before = world.counts(cid)
        before_ids = world.record_ids(cid)

        result = await _tool_write(world.author, cid)

        assert result["success"] is False
        assert result["error_code"] == "CANVAS_NOT_AUTHORIZED"
        assert "audit_id" not in result
        after = world.counts(cid)
        assert after["records"] == before["records"]
        assert after["audits"] == before["audits"]  # no write receipt
        assert world.record_ids(cid) == before_ids

    def test_author_api_read_denied(self, world, api, installed):
        _, cid = installed
        assert _append_as(api, world.owner, cid).status_code == 200
        _as(api, world.author)
        assert api.get(f"/api/mini-apps/instances/{cid}/records",
                       params={"series": "s"}).status_code == 404
        assert api.get(f"/api/mini-apps/instances/{cid}/records/series").status_code == 404


# ---------------------------------------------------------------------------
# Wrong scope / inactive / deleted targets
# ---------------------------------------------------------------------------
class TestScopeAndLifecycle:
    @pytest.mark.asyncio
    async def test_wrong_tenant_owner_id_denied(self, world, api, installed):
        _, cid = installed
        world.move_canvas(cid, tenant_id="tenant-2", workspace_id="ws-2")
        # The actor is an authoritative user in tenant-2; the canvas moved to
        # tenant-2 too, but `u-owner` still lives in tenant-1.
        result = await _tool_query(world.owner, cid)
        assert result["success"] is False
        assert result["http_status"] == 403
        assert "tenant" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_wrong_workspace_denied(self, world, api, installed):
        _, cid = installed
        world.move_canvas(cid, tenant_id="tenant-1", workspace_id="ws-1b")
        result = await _tool_query(world.owner, cid)
        assert result["success"] is False
        assert result["http_status"] == 403
        assert "workspace" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_inactive_actor_denied(self, world, api, installed):
        _, cid = installed
        result = await _tool_query(world.frozen, cid)
        assert result["success"] is False
        assert result["error_code"] in {
            "CANVAS_ACTOR_REFUSED", "CANVAS_NOT_AUTHORIZED"}
        assert "records" not in result

    def test_deleted_canvas_denied(self, world, api, installed):
        _, cid = installed
        assert _append_as(api, world.owner, cid).status_code == 200
        world.tombstone(cid)
        before = world.counts(cid)
        _as(api, world.owner)
        assert api.get(f"/api/mini-apps/instances/{cid}/records",
                       params={"series": "s"}).status_code == 404
        assert api.get(f"/api/mini-apps/instances/{cid}/assets").status_code == 404
        assert world.counts(cid) == before

    @pytest.mark.asyncio
    async def test_outsider_tenant_denied(self, world, api, installed):
        _, cid = installed
        result = await _tool_query(world.outsider, cid)
        assert result["success"] is False
        assert result["error_code"] == "CANVAS_NOT_AUTHORIZED"


# ---------------------------------------------------------------------------
# Legitimate access preserved
# ---------------------------------------------------------------------------
class TestLegitimateAccess:
    def test_public_approved_install_and_owner_read_write(self, world, api):
        app_id = world.app(public=True, approved=True)
        _as(api, world.stranger)  # a normal marketplace installer
        r = api.post(f"/api/mini-apps/{app_id}/install")
        assert r.status_code == 200, r.text
        cid = r.json()["canvas_id"]

        appended = _append_as(api, world.stranger, cid, data={"mine": 1})
        assert appended.status_code == 200, appended.text
        q = api.get(f"/api/mini-apps/instances/{cid}/records",
                    params={"series": "s"})
        assert q.status_code == 200 and q.json()["count"] == 1
        assert q.json()["records"][0]["data"] == {"mine": 1}
        up = api.post(f"/api/mini-apps/instances/{cid}/assets",
                      data={"key": "k.txt"},
                      files={"file": ("k.txt", b"ok", "text/plain")})
        assert up.status_code == 200
        assert api.get(f"/api/mini-apps/instances/{cid}/update-check").status_code == 200

    @pytest.mark.asyncio
    async def test_owner_tool_read_write(self, world, api, installed):
        _, cid = installed
        written = await _tool_write(world.owner, cid, data={"tool": 1})
        assert written["success"] is True
        assert written.get("audit_id")
        read = await _tool_query(world.owner, cid)
        assert read["success"] is True and read["count"] == 1
        assert read["records"][0]["data"] == {"tool": 1}

    def test_pending_and_private_install_contract_unchanged(self, world, api):
        pending = world.app(public=True, approved=False)
        private = world.app(public=False, approved=False)
        _as(api, world.stranger)
        assert api.post(f"/api/mini-apps/{pending}/install").status_code == 403
        assert api.post(f"/api/mini-apps/{private}/install").status_code == 403

    @pytest.mark.asyncio
    async def test_collaborator_reads_but_never_writes(self, world, api, installed):
        _, cid = installed
        assert _append_as(api, world.owner, cid, data={"v": 1}).status_code == 200
        world.add_collaborator(cid, world.collab)
        before = world.counts(cid)

        _as(api, world.collab)
        read = api.get(f"/api/mini-apps/instances/{cid}/records",
                       params={"series": "s"})
        assert read.status_code == 200 and read.json()["count"] == 1
        assert api.get(f"/api/mini-apps/instances/{cid}/assets").status_code == 200
        assert api.get(f"/api/mini-apps/instances/{cid}/update-check").status_code == 200

        # Mutation stays strict instance-owner.
        write = _append_as(api, world.collab, cid, data={"v": 2})
        assert write.status_code == 403
        assert write.json()["detail"] == "Not the instance owner"

        tool_write = await _tool_write(world.collab, cid)
        assert tool_write["success"] is False
        assert tool_write["error_code"] == "CANVAS_NOT_INSTANCE_OWNER"
        assert world.counts(cid) == before

        tool_read = await _tool_query(world.collab, cid)
        assert tool_read["success"] is True and tool_read["count"] == 1
