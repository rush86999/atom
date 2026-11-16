# -*- coding: utf-8 -*-
"""
Round 79 — gap coverage: api/mini_app_routes.py (mini-app authoring/install/
asset REST surface; zero test references before this file).

Standalone FastAPI app with ``get_db`` (in-memory SQLite, StaticPool for the
TestClient worker thread) and ``get_current_user`` overridden. Heavy service
calls (scaffold/dev-run/publish/install) are mocked at the service layer.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.models import Canvas, CanvasLogic, MiniApp, MiniAppAsset


@pytest.fixture()
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from core.database import Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from core.models import CanvasAudit, Tenant, User, Workspace

    Base.metadata.create_all(
        bind=engine,
        tables=[
            MiniApp.__table__, Canvas.__table__, CanvasLogic.__table__,
            MiniAppAsset.__table__, Tenant.__table__, Workspace.__table__,
            User.__table__, CanvasAudit.__table__,
        ],
    )
    session = sessionmaker(bind=engine)()
    # Instance data follows the canvas policy: the requester and every canvas
    # owner are authoritative users, and a real install writes an audit row.
    from tests.mini_app_authority_fixtures import ensure_actor

    ensure_actor(session, "user-1", "t1", None)
    yield session
    session.close()


@pytest.fixture()
def client(db_session, monkeypatch):
    from core.auth import get_current_user
    from core.database import get_db
    from api.mini_app_routes import router

    app = FastAPI()
    app.include_router(router)

    def override_db():
        yield db_session

    def override_user():
        return SimpleNamespace(id="user-1", role="super_admin", tenant_id="t1", workspace_id=None)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    with TestClient(app) as c:
        yield c


def _create_app(client, name="my-app", manifest=None):
    return client.post(
        "/api/mini-apps",
        json={
            "name": name,
            "manifest": manifest or {"name": name, "version": "1.0.0", "declared_scopes": ["canvas.read"], "dependencies": []},
        },
    )


def _make_app_row(db, app_id="app-1", owner="user-1", status="draft", manifest=None,
                  blueprint_canvas_id=None, runtime_image=None, is_public=False):
    app = MiniApp(
        id=app_id,
        tenant_id="t1",
        created_by=owner,
        name="my-app",
        version="1.0.0",
        status=status,
        manifest=manifest or {"name": "my-app", "version": "1.0.0", "declared_scopes": ["canvas.read"], "dependencies": []},
        blueprint_canvas_id=blueprint_canvas_id,
        runtime_image=runtime_image,
        is_public=is_public,
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


def _make_canvas_row(db, canvas_id="canvas-1", owner="user-1", mini_app_id="app-1"):
    canvas = Canvas(
        id=canvas_id,
        tenant_id="t1",
        created_by=owner,
        name=f"instance {canvas_id}",
        mini_app_id=mini_app_id,
        canvas_type="mini_app",
    )
    from tests.mini_app_authority_fixtures import ensure_actor, ensure_canvas_audit

    ensure_actor(db, owner, "t1", None)
    db.add(canvas)
    ensure_canvas_audit(db, canvas_id, user_id=owner, tenant_id="t1",
                        action_type="mini_app_install")
    db.commit()
    db.refresh(canvas)
    return canvas


class TestCreate:
    def test_create_mini_app(self, client):
        r = _create_app(client)
        assert r.status_code == 200
        assert r.json()["success"] is True
        assert r.json()["app"]["status"] == "draft"

    def test_create_invalid_manifest_400(self, client):
        r = _create_app(client, manifest={"name": "n", "declared_scopes": ["bogus_scope"]})
        assert r.status_code == 400

    def test_create_with_source_canvas(self, client, db_session):
        _make_canvas_row(db_session, mini_app_id=None)
        r = client.post(
            "/api/mini-apps",
            json={
                "name": "n",
                "source_canvas_id": "canvas-1",
                "manifest": {"name": "n", "version": "1.0.0", "declared_scopes": ["canvas.read"]},
            },
        )
        assert r.status_code == 200


class TestListAndGet:
    def test_list_returns_owned_apps(self, client, db_session):
        _make_app_row(db_session, app_id="a1")
        r = client.get("/api/mini-apps")
        assert r.status_code == 200
        assert [a["id"] for a in r.json()["apps"]] == ["a1"]

    def test_list_includes_public_apps(self, client, db_session):
        _make_app_row(db_session, app_id="a1", owner="other-user", is_public=True)
        r = client.get("/api/mini-apps")
        assert r.json()["apps"][0]["id"] == "a1"

    def test_list_excludes_private_foreign_apps(self, client, db_session):
        _make_app_row(db_session, app_id="a1", owner="other-user", is_public=False)
        r = client.get("/api/mini-apps")
        assert r.json()["apps"] == []

    def test_get_app_strips_credentials_from_manifest(self, client, db_session):
        _make_app_row(
            db_session,
            app_id="a1",
            manifest={"name": "n", "api_key": "sk-live-abc", "declared_scopes": ["canvas.read"]},
        )
        r = client.get("/api/mini-apps/a1")
        assert r.status_code == 200
        assert "api_key" not in str(r.json()["app"]["manifest"])
        assert "sk-live-abc" not in str(r.json()["app"]["manifest"])

    def test_get_missing_app_404(self, client):
        assert client.get("/api/mini-apps/nope").status_code == 404


class TestUpdate:
    def test_owner_can_update_name_and_version(self, client, db_session):
        _make_app_row(db_session, app_id="a1")
        r = client.put("/api/mini-apps/a1", json={"name": "renamed", "version": "2.0.0"})
        assert r.status_code == 200
        app = db_session.query(MiniApp).filter(MiniApp.id == "a1").first()
        assert app.name == "renamed"
        assert app.version == "2.0.0"

    def test_non_owner_forbidden(self, client, db_session):
        _make_app_row(db_session, app_id="a1", owner="someone-else")
        r = client.put("/api/mini-apps/a1", json={"name": "x"})
        assert r.status_code == 403

    def test_dependency_change_clears_runtime_image(self, client, db_session):
        _make_app_row(
            db_session, app_id="a1",
            runtime_image="repo/img:latest",
            manifest={"name": "n", "declared_scopes": ["canvas.read"], "dependencies": ["requests"]},
        )
        r = client.put(
            "/api/mini-apps/a1",
            json={"manifest": {"name": "n", "declared_scopes": ["canvas.read"], "dependencies": ["requests", "pandas"]}},
        )
        assert r.status_code == 200
        app = db_session.query(MiniApp).filter(MiniApp.id == "a1").first()
        assert app.runtime_image is None

    def test_manifest_change_without_dep_change_keeps_image(self, client, db_session):
        _make_app_row(
            db_session, app_id="a1",
            runtime_image="repo/img:latest",
            manifest={"name": "n", "declared_scopes": ["canvas.read"], "dependencies": ["requests"]},
        )
        r = client.put(
            "/api/mini-apps/a1",
            json={"manifest": {"name": "renamed", "declared_scopes": ["canvas.read"], "dependencies": ["requests"]}},
        )
        assert r.status_code == 200
        app = db_session.query(MiniApp).filter(MiniApp.id == "a1").first()
        assert app.runtime_image == "repo/img:latest"

    def test_invalid_manifest_update_400(self, client, db_session):
        _make_app_row(db_session, app_id="a1")
        r = client.put("/api/mini-apps/a1", json={"manifest": {"name": "n", "declared_scopes": []}})
        assert r.status_code == 400


class TestLogic:
    def test_save_logic_valid_source(self, client, db_session):
        _make_app_row(db_session, app_id="a1", blueprint_canvas_id="canvas-1")
        r = client.post(
            "/api/mini-apps/a1/logic", json={"source": "def run(state):\n    return state\n"}
        )
        assert r.status_code == 200
        logic = db_session.query(CanvasLogic).filter(CanvasLogic.canvas_id == "canvas-1").first()
        assert logic is not None

    def test_save_logic_syntax_error_400(self, client, db_session):
        _make_app_row(db_session, app_id="a1", blueprint_canvas_id="canvas-1")
        r = client.post("/api/mini-apps/a1/logic", json={"source": "def broken(:\n"})
        assert r.status_code == 400
        assert "SyntaxError" in r.json()["detail"]

    def test_save_logic_non_owner_forbidden(self, client, db_session):
        _make_app_row(db_session, app_id="a1", owner="other", blueprint_canvas_id="canvas-1")
        r = client.post("/api/mini-apps/a1/logic", json={"source": "x = 1\n"})
        assert r.status_code == 403

    def test_save_logic_missing_blueprint_400(self, client, db_session):
        _make_app_row(db_session, app_id="a1")
        r = client.post("/api/mini-apps/a1/logic", json={"source": "x = 1\n"})
        assert r.status_code == 400


class TestDevRunPublishInstall:
    def test_dev_run_success(self, client, db_session):
        _make_app_row(db_session, app_id="a1", blueprint_canvas_id="canvas-1")
        with patch("core.mini_app_service.prepare_runtime") as prepare, patch(
            "core.mini_app_service.run_stateful", new=AsyncMock(return_value={"success": True, "state": {"n": 1}})
        ) as run:
            r = client.post("/api/mini-apps/a1/dev-run", json={"inputs": {}})
        assert r.status_code == 200
        prepare.assert_called_once()
        assert r.json()["state"] == {"n": 1}

    def test_dev_run_failure_maps_to_500(self, client, db_session):
        _make_app_row(db_session, app_id="a1", blueprint_canvas_id="canvas-1")
        with patch("core.mini_app_service.prepare_runtime"), patch(
            "core.mini_app_service.run_stateful",
            new=AsyncMock(return_value={"success": False, "error": "rootfs missing"}),
        ):
            r = client.post("/api/mini-apps/a1/dev-run", json={})
        assert r.status_code == 500

    def test_publish_success(self, client, db_session):
        _make_app_row(db_session, app_id="a1")
        with patch("core.mini_app_service.publish", return_value={"version": "1.0.0"}):
            r = client.post("/api/mini-apps/a1/publish")
        assert r.status_code == 200
        assert r.json()["version"] == "1.0.0"

    def test_publish_runtime_error_500(self, client, db_session):
        _make_app_row(db_session, app_id="a1")
        with patch("core.mini_app_service.publish", side_effect=RuntimeError("rootfs missing")):
            r = client.post("/api/mini-apps/a1/publish")
        assert r.status_code == 500

    def test_publish_value_error_400(self, client, db_session):
        _make_app_row(db_session, app_id="a1")
        with patch("core.mini_app_service.publish", side_effect=ValueError("no blueprint")):
            r = client.post("/api/mini-apps/a1/publish")
        assert r.status_code == 400

    def test_publish_non_owner_forbidden(self, client, db_session):
        _make_app_row(db_session, app_id="a1", owner="other")
        r = client.post("/api/mini-apps/a1/publish")
        assert r.status_code == 403

    def test_install_success(self, client, db_session):
        _make_app_row(db_session, app_id="a1", status="published")
        with patch("core.mini_app_service.install", return_value="canvas-99"):
            r = client.post("/api/mini-apps/a1/install")
        assert r.status_code == 200
        assert r.json()["canvas_id"] == "canvas-99"

    def test_install_value_error_400(self, client, db_session):
        _make_app_row(db_session, app_id="a1")
        with patch("core.mini_app_service.install", side_effect=ValueError("not published")):
            r = client.post("/api/mini-apps/a1/install")
        assert r.status_code == 400


class TestAssets:
    @pytest.fixture()
    def storage(self):
        return MagicMock(store=MagicMock(return_value="mem://canvas-1/key"),
                         retrieve=MagicMock(return_value=b"data"),
                         delete=MagicMock(return_value=True))

    def test_upload_asset(self, client, db_session, storage):
        _make_app_row(db_session, app_id="app-1")
        _make_canvas_row(db_session, mini_app_id="app-1")
        with patch("api.mini_app_routes.get_mini_app_storage", return_value=storage):
            r = client.post(
                "/api/mini-apps/instances/canvas-1/assets",
                data={"key": "logo.png"},
                files={"file": ("logo.png", b"png-bytes", "image/png")},
            )
        assert r.status_code == 200
        assert r.json()["key"] == "logo.png"

    def test_upload_asset_non_instance_canvas_404(self, client, db_session):
        _make_canvas_row(db_session, mini_app_id=None)
        r = client.post(
            "/api/mini-apps/instances/canvas-1/assets",
            data={"key": "logo.png"},
            files={"file": ("logo.png", b"x", "image/png")},
        )
        assert r.status_code == 404

    def test_upload_asset_public_app_foreign_user_denied(self, client, db_session, storage):
        _make_app_row(db_session, app_id="app-1", owner="owner-2", is_public=True)
        _make_canvas_row(db_session, mini_app_id="app-1", owner="owner-2")
        with patch("api.mini_app_routes.get_mini_app_storage", return_value=storage):
            r = client.post(
                "/api/mini-apps/instances/canvas-1/assets",
                data={"key": "k"},
                files={"file": ("k", b"x", "text/plain")},
            )
        # Publication is not a grant to instance data: a stranger gets the
        # canvas-policy refusal ("not found"), not an ownership oracle.
        assert r.status_code == 404
        assert db_session.query(MiniAppAsset).count() == 0

    def test_upload_asset_private_foreign_denied(self, client, db_session):
        _make_app_row(db_session, app_id="app-1", owner="owner-2", is_public=False)
        _make_canvas_row(db_session, mini_app_id="app-1", owner="owner-2")
        r = client.post(
            "/api/mini-apps/instances/canvas-1/assets",
            data={"key": "k"},
            files={"file": ("k", b"x", "text/plain")},
        )
        assert r.status_code == 404

    def test_upload_invalid_key_400(self, client, db_session, storage):
        _make_app_row(db_session, app_id="app-1")
        _make_canvas_row(db_session, mini_app_id="app-1")
        with patch("api.mini_app_routes.get_mini_app_storage", return_value=storage):
            r = client.post(
                "/api/mini-apps/instances/canvas-1/assets",
                data={"key": "../evil"},
                files={"file": ("evil", b"x", "text/plain")},
            )
        assert r.status_code == 400

    def test_list_assets(self, client, db_session, storage):
        _make_app_row(db_session, app_id="app-1")
        _make_canvas_row(db_session, mini_app_id="app-1")
        db_session.add(MiniAppAsset(canvas_id="canvas-1", tenant_id="t1", key="k",
                                    uri="mem://k", content_type="text/plain", size=1,
                                    created_by="user-1"))
        db_session.commit()
        with patch("api.mini_app_routes.get_mini_app_storage", return_value=storage):
            r = client.get("/api/mini-apps/instances/canvas-1/assets")
        assert r.status_code == 200
        assert r.json()["assets"][0]["key"] == "k"

    def test_download_asset(self, client, db_session, storage):
        _make_app_row(db_session, app_id="app-1")
        _make_canvas_row(db_session, mini_app_id="app-1")
        db_session.add(MiniAppAsset(canvas_id="canvas-1", tenant_id="t1", key="k",
                                    uri="mem://k", content_type="image/png", size=4,
                                    created_by="user-1"))
        db_session.commit()
        with patch("api.mini_app_routes.get_mini_app_storage", return_value=storage):
            r = client.get("/api/mini-apps/instances/canvas-1/assets/k")
        assert r.status_code == 200
        assert r.content == b"data"

    def test_download_missing_asset_404(self, client, db_session, storage):
        _make_app_row(db_session, app_id="app-1")
        _make_canvas_row(db_session, mini_app_id="app-1")
        storage.retrieve.return_value = None
        with patch("api.mini_app_routes.get_mini_app_storage", return_value=storage):
            r = client.get("/api/mini-apps/instances/canvas-1/assets/missing")
        assert r.status_code == 404

    def test_delete_asset_owner_only(self, client, db_session, storage):
        _make_app_row(db_session, app_id="app-1")
        _make_canvas_row(db_session, mini_app_id="app-1")
        with patch("api.mini_app_routes.get_mini_app_storage", return_value=storage):
            r = client.delete("/api/mini-apps/instances/canvas-1/assets/k")
        assert r.status_code == 200
        assert r.json()["deleted"] is True

    def test_delete_asset_foreign_owner_denied(self, client, db_session):
        _make_app_row(db_session, app_id="app-1")
        _make_canvas_row(db_session, mini_app_id="app-1", owner="owner-2")
        r = client.delete("/api/mini-apps/instances/canvas-1/assets/k")
        assert r.status_code == 404

    def test_delete_asset_collaborator_stays_owner_only(self, client, db_session):
        """Accepted read collaboration must not widen instance mutations."""
        from core.models import CanvasAudit

        _make_app_row(db_session, app_id="app-1")
        _make_canvas_row(db_session, mini_app_id="app-1", owner="owner-2")
        db_session.add(CanvasAudit(
            id="collab-a", canvas_id="canvas-1", tenant_id="t1",
            user_id="user-1", canvas_type="mini_app", action_type="update",
            details_json={"title": "x"},
        ))
        db_session.commit()
        r = client.delete("/api/mini-apps/instances/canvas-1/assets/k")
        assert r.status_code == 403
        assert r.json()["detail"] == "Not the instance owner"
