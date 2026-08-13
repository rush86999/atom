# -*- coding: utf-8 -*-
"""Coverage wave 91 — core/user_preference_routes (API router).

TestClient + in-memory SQLite; get_current_user / get_db dependency overrides.
Zero LLM spend, no network.

- GET /api/v1/preferences: empty, populated, per-user isolation.
- GET /api/v1/preferences/{key}: found / missing (default None).
- POST /api/v1/preferences: set + upsert; client-supplied body user_id is
  NEVER trusted (R77 IDOR regression guard — identity is always the token
  user); service failure → 500 "Internal error" (no str(e) leak).
- Auth: unauthenticated request → 401.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core import user_preference_routes
from core.database import Base
from core.models import User
from core.user_preference_service import UserPreference

PREFIX = "/api/v1/preferences"


def _user(uid="user-1"):
    return User(
        id=uid,
        email=f"{uid}@example.com",
        first_name="Test",
        last_name="User",
        role="admin",
        status="active",
    )


@pytest.fixture()
def db_session():
    # StaticPool: TestClient runs requests on a worker thread, so the in-memory
    # SQLite database must live on a single shared connection.
    engine = create_engine(
        "sqlite://",
        poolclass=__import__("sqlalchemy.pool", fromlist=["StaticPool"]).StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db_session, monkeypatch):
    app = FastAPI()
    app.include_router(user_preference_routes.router, prefix=PREFIX)
    app.dependency_overrides[user_preference_routes.get_current_user] = lambda: _user()
    app.dependency_overrides[user_preference_routes.get_db] = lambda: db_session
    return TestClient(app)


def _seed(db_session, user_id, workspace_id, key, value):
    pref = UserPreference(user_id=user_id, workspace_id=workspace_id, key=key,
                          value=__import__("json").dumps(value))
    db_session.add(pref)
    db_session.commit()
    return pref


# ============================================================================
# GET all
# ============================================================================

def test_get_all_empty(client):
    resp = client.get(PREFIX, params={"workspace_id": "ws-1"})
    assert resp.status_code == 200
    assert resp.json() == {}


def test_get_all_populated(db_session, client):
    _seed(db_session, "user-1", "ws-1", "theme", "dark")
    _seed(db_session, "user-1", "ws-1", "revenue_goal", 1000)
    resp = client.get(PREFIX, params={"workspace_id": "ws-1"})
    assert resp.status_code == 200
    assert resp.json() == {"theme": "dark", "revenue_goal": 1000}


def test_get_all_isolated_per_user_and_workspace(db_session, client):
    _seed(db_session, "user-2", "ws-1", "theme", "light")
    _seed(db_session, "user-1", "ws-2", "theme", "light")
    resp = client.get(PREFIX, params={"workspace_id": "ws-1"})
    assert resp.status_code == 200
    assert resp.json() == {}  # user-1 has nothing in ws-1


# ============================================================================
# GET {key}
# ============================================================================

def test_get_preference_found(db_session, client):
    _seed(db_session, "user-1", "ws-1", "theme", "dark")
    resp = client.get(f"{PREFIX}/theme", params={"workspace_id": "ws-1"})
    assert resp.status_code == 200
    assert resp.json() == {"key": "theme", "value": "dark"}


def test_get_preference_missing(client):
    resp = client.get(f"{PREFIX}/nope", params={"workspace_id": "ws-1"})
    assert resp.status_code == 200
    assert resp.json() == {"key": "nope", "value": None}


# ============================================================================
# POST set (upsert)
# ============================================================================

def test_set_preference_create(client):
    resp = client.post(PREFIX, json={
        "workspace_id": "ws-1", "key": "theme", "value": "dark",
    })
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "key": "theme", "value": "dark"}


def test_set_preference_upsert(client):
    client.post(PREFIX, json={"workspace_id": "ws-1", "key": "theme", "value": "dark"})
    resp = client.post(PREFIX, json={"workspace_id": "ws-1", "key": "theme", "value": "light"})
    assert resp.status_code == 200
    assert resp.json()["value"] == "light"
    get_resp = client.get(f"{PREFIX}/theme", params={"workspace_id": "ws-1"})
    assert get_resp.json()["value"] == "light"


def test_set_preference_ignores_client_user_id(client):
    """R77 IDOR regression: a client-supplied user_id must never win."""
    resp = client.post(PREFIX, json={
        "user_id": "attacker-id",  # spoof attempt — must be ignored
        "workspace_id": "ws-1", "key": "theme", "value": "dark",
    })
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    # Value must be stored under the TOKEN user (user-1), not attacker-id.
    all_resp = client.get(PREFIX, params={"workspace_id": "ws-1"})
    assert all_resp.json() == {"theme": "dark"}


def test_set_preference_validation_error(client):
    resp = client.post(PREFIX, json={"workspace_id": "ws-1", "key": "theme"})
    assert resp.status_code == 422  # value required


def test_set_preference_service_failure_returns_generic_500(db_session, monkeypatch):
    app = FastAPI()
    app.include_router(user_preference_routes.router, prefix=PREFIX)
    app.dependency_overrides[user_preference_routes.get_current_user] = lambda: _user()
    app.dependency_overrides[user_preference_routes.get_db] = lambda: db_session

    class _BrokenService:
        def __init__(self, db):
            self.db = db

        def set_preference(self, **kwargs):
            raise RuntimeError("secret-db-detail")

    monkeypatch.setattr(user_preference_routes, "UserPreferenceService", _BrokenService)
    client = TestClient(app)
    resp = client.post(PREFIX, json={"workspace_id": "ws-1", "key": "k", "value": 1})
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal error"}  # no str(e) leak
    assert "secret-db-detail" not in resp.text


# ============================================================================
# Auth
# ============================================================================

def test_routes_require_auth():
    app = FastAPI()
    app.include_router(user_preference_routes.router, prefix=PREFIX)
    client = TestClient(app)  # no dependency overrides — real get_current_user
    resp = client.get(PREFIX, params={"workspace_id": "ws-1"})
    assert resp.status_code == 401
