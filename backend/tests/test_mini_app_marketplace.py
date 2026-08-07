"""Mini-app marketplace gaps A–G — install authz, cross-tenant, share/approve, browse.

Covers the seven marketplace gaps: install authorization (A), installer-tenant
ownership (B), is_public/share_token activation + by-token install (C),
is_approved review gate (D), browse metadata (E), update-check signal (F),
dead-stub removal (G).
"""
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.models import Canvas, MiniApp, MiniAppInstallation


def _seed_app(db, owner_id="u1", app_id=None, **kw):
    app_id = app_id or f"app-{uuid.uuid4().hex[:10]}"
    # Build a fresh default manifest each call (avoid mutable-default sharing).
    default_manifest = kw.get("manifest") or {
        "declared_scopes": ["*"], "dependencies": ["pandas==2.2"],
        "integrations": [{"service": "notion", "action": "search", "params": {}}],
        "blueprint": {"content": {}, "style": {}, "logic_source": "state = state",
                      "logic_language": "python", "component_installations": []},
        "initial_state": {},
    }
    db.add(MiniApp(
        id=app_id, tenant_id=kw.get("tenant_id", "t_author"), created_by=owner_id,
        name=kw.get("name", "t"), description=kw.get("description", "a test app"),
        version=kw.get("version", "1.0.0"),
        manifest=default_manifest,
        status=kw.get("status", "published"),
        is_public=kw.get("is_public", False),
        is_approved=kw.get("is_approved", False),
    ))
    db.commit()
    return app_id


def _client(db_session, user_id="u1", is_admin=False):
    from api.mini_app_routes import router
    from core.auth import get_current_user
    from core.database import get_db

    stub = type("U", (), {"id": user_id, "is_authenticated": True, "is_active": True,
                          "is_admin": is_admin, "is_staff": is_admin,
                          "tenant_id": "t_installer", "workspace_id": "w_installer"})()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: stub
    app.dependency_overrides[get_db] = lambda: (yield db_session)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Gap A — install authz
# ---------------------------------------------------------------------------
class TestInstallAuthz:
    def test_owner_can_install_own_app(self, db_session):
        aid = _seed_app(db_session, owner_id="u1")
        c = _client(db_session, "u1")
        r = c.post(f"/api/mini-apps/{aid}/install")
        assert r.status_code == 200, r.text

    def test_non_owner_private_app_forbidden(self, db_session):
        aid = _seed_app(db_session, owner_id="author", is_public=False)
        c = _client(db_session, "intruder")
        r = c.post(f"/api/mini-apps/{aid}/install")
        assert r.status_code == 403

    def test_non_owner_public_unapproved_pending_review(self, db_session):
        aid = _seed_app(db_session, owner_id="author", is_public=True, is_approved=False)
        c = _client(db_session, "installer")
        r = c.post(f"/api/mini-apps/{aid}/install")
        assert r.status_code == 403
        assert "review" in r.json()["detail"].lower()

    def test_non_owner_public_approved_allowed(self, db_session):
        aid = _seed_app(db_session, owner_id="author", is_public=True, is_approved=True)
        c = _client(db_session, "installer")
        r = c.post(f"/api/mini-apps/{aid}/install")
        assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Gap B — installer-tenant ownership
# ---------------------------------------------------------------------------
class TestInstallerTenant:
    def test_instance_lands_in_installer_tenant(self, db_session):
        aid = _seed_app(db_session, owner_id="author", tenant_id="t_author",
                        is_public=True, is_approved=True)
        c = _client(db_session, "installer")  # tenant_id="t_installer"
        r = c.post(f"/api/mini-apps/{aid}/install")
        assert r.status_code == 200
        cid = r.json()["canvas_id"]
        canvas = db_session.query(Canvas).filter(Canvas.id == cid).first()
        # Gap B: instance is in the INSTALLER's tenant, not the author's
        assert canvas.tenant_id == "t_installer"
        assert canvas.created_by == "installer"


# ---------------------------------------------------------------------------
# Gap C — share token + by-token install
# ---------------------------------------------------------------------------
class TestShareToken:
    def test_share_mints_token(self, db_session):
        aid = _seed_app(db_session, owner_id="u1", status="draft")
        c = _client(db_session, "u1")
        r = c.post(f"/api/mini-apps/{aid}/share?public=true")
        assert r.status_code == 200
        body = r.json()
        assert body["is_public"] is True
        assert body["share_token"]

    def test_install_by_token_approved(self, db_session):
        aid = _seed_app(db_session, owner_id="author", is_public=True, is_approved=True)
        app = db_session.query(MiniApp).filter(MiniApp.id == aid).first()
        import secrets
        app.share_token = secrets.token_urlsafe(32)
        db_session.commit()
        c = _client(db_session, "installer")
        r = c.post(f"/api/mini-apps/by-token/{app.share_token}/install")
        assert r.status_code == 200, r.text

    def test_install_by_token_unapproved_403(self, db_session):
        aid = _seed_app(db_session, owner_id="author", is_public=True, is_approved=False)
        app = db_session.query(MiniApp).filter(MiniApp.id == aid).first()
        import secrets
        app.share_token = secrets.token_urlsafe(32)
        db_session.commit()
        c = _client(db_session, "installer")
        r = c.post(f"/api/mini-apps/by-token/{app.share_token}/install")
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Gap D — admin approve
# ---------------------------------------------------------------------------
class TestApprove:
    def test_non_admin_forbidden(self, db_session):
        aid = _seed_app(db_session, owner_id="u1")
        c = _client(db_session, "u1", is_admin=False)
        r = c.post(f"/api/mini-apps/{aid}/approve")
        assert r.status_code == 403

    def test_admin_approves(self, db_session):
        aid = _seed_app(db_session, owner_id="u1")
        c = _client(db_session, "admin", is_admin=True)
        r = c.post(f"/api/mini-apps/{aid}/approve")
        assert r.status_code == 200
        app = db_session.query(MiniApp).filter(MiniApp.id == aid).first()
        assert app.is_approved is True


# ---------------------------------------------------------------------------
# Gap E — browse metadata + search
# ---------------------------------------------------------------------------
class TestBrowseMetadata:
    def test_list_includes_marketplace_fields(self, db_session):
        _seed_app(db_session, owner_id="u1", name="Revenue Tracker")
        c = _client(db_session, "u1")
        r = c.get("/api/mini-apps")
        assert r.status_code == 200
        apps = r.json()["apps"]
        # Find THIS test's app (the shared DB session may have apps from prior tests).
        a = next((x for x in apps if x["name"] == "Revenue Tracker"), apps[0])
        assert "declared_scopes" in a and "dependencies" in a
        assert "integrations_count" in a and a["integrations_count"] == 1
        assert "description" in a and "is_approved" in a

    def test_search_by_name(self, db_session):
        _seed_app(db_session, owner_id="u1", name="Revenue Tracker")
        _seed_app(db_session, owner_id="u1", app_id="app2", name="Todo List")
        c = _client(db_session, "u1")
        r = c.get("/api/mini-apps?q=Revenue")
        names = [a["name"] for a in r.json()["apps"]]
        assert "Revenue Tracker" in names and "Todo List" not in names


# ---------------------------------------------------------------------------
# Gap F — update-check signal
# ---------------------------------------------------------------------------
class TestUpdateCheck:
    def test_update_available_when_version_bumps(self, db_session):
        aid = _seed_app(db_session, owner_id="u1", version="1.0.0")
        c = _client(db_session, "u1")
        cid = c.post(f"/api/mini-apps/{aid}/install").json()["canvas_id"]
        # simulate the app being upgraded after install
        app = db_session.query(MiniApp).filter(MiniApp.id == aid).first()
        app.version = "2.0.0"
        db_session.commit()
        r = c.get(f"/api/mini-apps/instances/{cid}/update-check")
        body = r.json()
        assert body["update_available"] is True
        assert body["latest_version"] == "2.0.0"

    def test_no_update_when_versions_match(self, db_session):
        aid = _seed_app(db_session, owner_id="u1", version="1.0.0")
        c = _client(db_session, "u1")
        cid = c.post(f"/api/mini-apps/{aid}/install").json()["canvas_id"]
        r = c.get(f"/api/mini-apps/instances/{cid}/update-check")
        assert r.json()["update_available"] is False


# ---------------------------------------------------------------------------
# Gap G — dead stubs removed (import-level)
# ---------------------------------------------------------------------------
class TestDeadStubsRemoved:
    def test_main_app_imports_clean(self):
        import main_api_app  # noqa: F401
        src = open("main_api_app.py").read()
        assert "public_marketplace_routes" not in src
        assert "Public Marketplace v1 API" not in src
