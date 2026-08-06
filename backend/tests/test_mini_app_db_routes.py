# -*- coding: utf-8 -*-
"""
Mini-app DB store — instance record API routes (host-mediated CRUD surface).

Standalone FastAPI app with ``get_db`` (in-memory SQLite, StaticPool) and
``get_current_user`` overridden. Covers the authz matrix: 401/403/404, owner-
only mutations, kill switch (db_disabled), and no str(e) in error bodies.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.models import Canvas, CanvasLogic, CanvasRecord, CanvasState, MiniApp, MiniAppAsset


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
    Base.metadata.create_all(
        bind=engine,
        tables=[
            MiniApp.__table__, Canvas.__table__, CanvasLogic.__table__,
            MiniAppAsset.__table__, CanvasState.__table__, CanvasRecord.__table__,
        ],
    )
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture()
def client(db_session):
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


@pytest.fixture()
def canvas_fixture(db_session):
    """A published mini-app with an installed instance canvas (owner user-1)."""
    app_id = "app-1"
    canvas_id = "inst-1"
    db_session.add(MiniApp(
        id=app_id, tenant_id="t1", workspace_id="w1", created_by="user-1",
        name="chart", version="1.0.0", status="published",
        manifest={
            "declared_scopes": ["*"], "mcp_servers": [], "dependencies": [],
            "base_image": "python:3.11-slim", "assets": [],
            "db": {"enabled": True, "max_records_per_series": 100, "max_record_bytes": 10240},
            "initial_state": {}, "blueprint": {},
        },
        blueprint_canvas_id="src-1",
    ))
    db_session.add(Canvas(
        id=canvas_id, tenant_id="t1", created_by="user-1", name="chart",
        canvas_type="mini_app", content={}, style={}, status="active",
        mini_app_id=app_id,
    ))
    db_session.add(CanvasState(canvas_id=canvas_id, tenant_id="t1", state={}, version=1))
    db_session.commit()
    return app_id, canvas_id


def _public_canvas(db_session):
    """A public app instance owned by someone else (read-visible, not mutable)."""
    db_session.add(MiniApp(
        id="app-public", tenant_id="t1", created_by="other-user",
        name="pub", version="1.0.0", status="published",
        manifest={"declared_scopes": ["*"], "mcp_servers": [], "dependencies": [],
                  "base_image": "python:3.11-slim", "assets": [],
                  "initial_state": {}, "blueprint": {}},
        blueprint_canvas_id="src-pub", is_public=True,
    ))
    db_session.add(Canvas(
        id="inst-public", tenant_id="t1", created_by="other-user", name="pub",
        canvas_type="mini_app", content={}, style={}, status="active",
        mini_app_id="app-public",
    ))
    db_session.commit()
    return "inst-public"


class TestRecordsRoutes:
    def test_append_query_roundtrip(self, client, db_session, canvas_fixture):
        _, canvas_id = canvas_fixture
        r = client.post(f"/api/mini-apps/instances/{canvas_id}/records",
                        json={"series": "chart_data", "data": {"label": "Jan", "value": 12}})
        assert r.status_code == 200 and r.json()["success"]
        rid = r.json()["record"]["id"]
        assert r.json()["record"]["seq"] == 1

        q = client.get(f"/api/mini-apps/instances/{canvas_id}/records",
                       params={"series": "chart_data"})
        assert q.status_code == 200
        assert q.json()["count"] == 1
        assert q.json()["records"][0]["data"]["label"] == "Jan"

        g = client.get(f"/api/mini-apps/instances/{canvas_id}/records/{rid}",
                       params={"series": "chart_data"})
        assert g.status_code == 200 and g.json()["record"]["id"] == rid

        u = client.put(f"/api/mini-apps/instances/{canvas_id}/records/{rid}",
                       json={"series": "chart_data", "data": {"value": 99}})
        assert u.status_code == 200 and u.json()["record"]["data"]["value"] == 99

        d = client.delete(f"/api/mini-apps/instances/{canvas_id}/records/{rid}",
                          params={"series": "chart_data"})
        assert d.status_code == 200 and d.json()["deleted"] is True

        q2 = client.post(f"/api/mini-apps/instances/{canvas_id}/records/query",
                         json={"series": "chart_data"})
        assert q2.status_code == 200 and q2.json()["count"] == 0

    def test_count_and_series_list(self, client, canvas_fixture):
        _, canvas_id = canvas_fixture
        client.post(f"/api/mini-apps/instances/{canvas_id}/records",
                    json={"series": "a", "data": {"k": 1}})
        client.post(f"/api/mini-apps/instances/{canvas_id}/records",
                    json={"series": "b", "data": {"k": 1}})
        c = client.post(f"/api/mini-apps/instances/{canvas_id}/records/count",
                        json={"series": "a"})
        assert c.json()["count"] == 1
        s = client.get(f"/api/mini-apps/instances/{canvas_id}/records/series")
        names = {x["series"] for x in s.json()["series"]}
        assert names == {"a", "b"}

    def test_filtered_query_and_delete_series(self, client, canvas_fixture):
        _, canvas_id = canvas_fixture
        client.post(f"/api/mini-apps/instances/{canvas_id}/records",
                    json={"series": "todos", "data": {"team": "a"}})
        client.post(f"/api/mini-apps/instances/{canvas_id}/records",
                    json={"series": "todos", "data": {"team": "b"}})
        q = client.post(f"/api/mini-apps/instances/{canvas_id}/records/query",
                        json={"series": "todos", "filter": {"team": "a"}})
        assert q.json()["count"] == 1
        d = client.delete(f"/api/mini-apps/instances/{canvas_id}/records",
                          params={"series": "todos"})
        assert d.status_code == 200 and d.json()["deleted"] == 2
        q2 = client.post(f"/api/mini-apps/instances/{canvas_id}/records/count",
                         json={"series": "todos"})
        assert q2.json()["count"] == 0

    def test_validation_errors(self, client, canvas_fixture):
        _, canvas_id = canvas_fixture
        r = client.post(f"/api/mini-apps/instances/{canvas_id}/records",
                        json={"series": "Bad Series!", "data": {"x": 1}})
        assert r.status_code == 400
        r2 = client.post(f"/api/mini-apps/instances/{canvas_id}/records",
                         json={"series": "s", "data": {"big": "x" * 50000}})
        assert r2.status_code == 400
        q = client.get(f"/api/mini-apps/instances/{canvas_id}/records",
                       params={"series": "s", "limit": 0})
        assert q.status_code == 422  # FastAPI Query constraint

    def test_404_non_instance_canvas(self, client, db_session):
        db_session.add(Canvas(
            id="plain", tenant_id="t1", created_by="user-1", name="plain",
            canvas_type="whiteboard", content={}, style={}, status="active",
        ))
        db_session.commit()
        r = client.get("/api/mini-apps/instances/plain/records", params={"series": "s"})
        assert r.status_code == 404
        r2 = client.get("/api/mini-apps/instances/nope/records", params={"series": "s"})
        assert r2.status_code == 404

    def test_public_read_allowed_mutation_denied(self, client, db_session, canvas_fixture):
        public_id = _public_canvas(db_session)
        q = client.get(f"/api/mini-apps/instances/{public_id}/records", params={"series": "s"})
        assert q.status_code == 200
        r = client.post(f"/api/mini-apps/instances/{public_id}/records",
                        json={"series": "s", "data": {"x": 1}})
        assert r.status_code == 403

    def test_owner_only_mutation(self, client, db_session, canvas_fixture):
        public_id = _public_canvas(db_session)
        r = client.delete(f"/api/mini-apps/instances/{public_id}/records", params={"series": "s"})
        assert r.status_code == 403

    def test_kill_switch_503(self, client, canvas_fixture, monkeypatch):
        monkeypatch.setenv("ATOM_MINIAPP_DB_ENABLED", "false")
        import core.mini_app_db_service as dbsvc
        monkeypatch.setattr(dbsvc, "db_store_enabled", lambda: False)
        _, canvas_id = canvas_fixture
        r = client.get(f"/api/mini-apps/instances/{canvas_id}/records", params={"series": "s"})
        assert r.status_code == 503 and r.json()["detail"] == "db_disabled"
        r2 = client.post(f"/api/mini-apps/instances/{canvas_id}/records",
                         json={"series": "s", "data": {"x": 1}})
        assert r2.status_code == 503

    def test_error_bodies_have_no_traceback(self, client, canvas_fixture):
        _, canvas_id = canvas_fixture
        r = client.post(f"/api/mini-apps/instances/{canvas_id}/records",
                        json={"series": "Bad!", "data": {}})
        body = r.text
        assert "Traceback" not in body
        assert " at 0x" not in body
