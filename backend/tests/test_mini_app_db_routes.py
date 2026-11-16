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
    from core.models import CanvasAudit, Tenant, User, Workspace

    Base.metadata.create_all(
        bind=engine,
        tables=[
            MiniApp.__table__, Canvas.__table__, CanvasLogic.__table__,
            MiniAppAsset.__table__, CanvasState.__table__, CanvasRecord.__table__,
            Tenant.__table__, Workspace.__table__, User.__table__,
            CanvasAudit.__table__,
        ],
    )
    session = sessionmaker(bind=engine)()
    # Honest actors: instance data follows the canvas policy, so the
    # requesting users must exist and every real install writes an audit row.
    from tests.mini_app_authority_fixtures import ensure_actor

    ensure_actor(session, "user-1", "t1", None)
    ensure_actor(session, "user-2", "t1", None)
    ensure_actor(session, "other-user", "t1", None)
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
    from tests.mini_app_authority_fixtures import ensure_canvas_audit

    ensure_canvas_audit(db_session, canvas_id, user_id="user-1", tenant_id="t1",
                        action_type="mini_app_install")
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
    from tests.mini_app_authority_fixtures import ensure_canvas_audit

    ensure_canvas_audit(db_session, "inst-public", user_id="other-user",
                        tenant_id="t1", action_type="mini_app_install")
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

    def test_public_instance_data_not_readable_by_stranger(self, client, db_session, canvas_fixture):
        """Publication is an install signal, never a grant to instance data."""
        public_id = _public_canvas(db_session)
        q = client.get(f"/api/mini-apps/instances/{public_id}/records", params={"series": "s"})
        assert q.status_code == 404  # non-owner gets the canvas-policy refusal
        assert "records" not in q.json()
        r = client.get(f"/api/mini-apps/instances/{public_id}/records/series")
        assert r.status_code == 404
        count = client.post(f"/api/mini-apps/instances/{public_id}/records/count",
                            json={"series": "s"})
        assert count.status_code == 404
        assert "count" not in count.json()
        w = client.post(f"/api/mini-apps/instances/{public_id}/records",
                        json={"series": "s", "data": {"x": 1}})
        assert w.status_code == 404

    def test_collaborator_reads_but_mutation_stays_owner_only(self, client, db_session):
        """Accepted canvas collaboration: read yes, write no (unchanged contract)."""
        from core.models import CanvasAudit

        public_id = _public_canvas(db_session)
        db_session.add(CanvasAudit(
            id="collab-audit", canvas_id=public_id, tenant_id="t1",
            user_id="user-1", canvas_type="mini_app", action_type="update",
            details_json={"title": "pub"},
        ))
        db_session.commit()
        q = client.get(f"/api/mini-apps/instances/{public_id}/records", params={"series": "s"})
        assert q.status_code == 200 and q.json()["records"] == []
        w = client.post(f"/api/mini-apps/instances/{public_id}/records",
                        json={"series": "s", "data": {"x": 1}})
        assert w.status_code == 403
        assert w.json()["detail"] == "Not the instance owner"

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
