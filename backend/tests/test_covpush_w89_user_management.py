# -*- coding: utf-8 -*-
"""Coverage wave 89 — api/user_management_routes.py.

Real in-memory SQLite. Covers all 4 endpoints x {success, 401 unauth,
404 missing, ownership/IDOR guard, current-session flags, cookie token
fallback}.

Security regression surface checked this wave:
  * every endpoint rejects anonymous callers with 401,
  * revoke_session enforces ownership — another user's session id is a
    404, never revocable (no cross-user session revocation),
  * revoke_all_sessions keeps the current session alive (token-matched)
    and revokes everything else,
  * the session-token extraction prefers the Authorization header and
    falls back to the NextAuth cookies.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.user_management_routes import router as user_mgmt_router
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import User, UserSession

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_user(db, user_id="user-1"):
    existing = db.query(User).filter(User.id == user_id).first()
    if existing:
        return existing
    user = User(
        id=user_id,
        email=f"{user_id}@example.com",
        first_name="Jane",
        last_name="Doe",
        role="admin",
        status="active",
        tenant_id="t1",
        last_login=datetime(2026, 8, 1, 12, 0, 0),
    )
    db.add(user)
    db.commit()
    return user


def _make_session(db, session_id, user_id="user-1", *, session_token=None,
                  is_active=True, expires_days=7, last_active_days=1,
                  device_type="mobile", browser="Safari", os="iOS"):
    session = UserSession(
        id=session_id,
        user_id=user_id,
        session_token=session_token or f"tok-{session_id}",
        is_active=is_active,
        device_type=device_type,
        browser=browser,
        os=os,
        ip_address="127.0.0.1",
        created_at=datetime.now(timezone.utc) - timedelta(days=30),
        last_active_at=datetime.now(timezone.utc) - timedelta(days=last_active_days),
        expires_at=datetime.now(timezone.utc) + timedelta(days=expires_days),
    )
    db.add(session)
    db.commit()
    return session


@pytest.fixture()
def client(db):
    app = FastAPI()
    app.include_router(user_mgmt_router)
    user = _make_user(db)

    def _override_db():
        yield db

    def _override_user():
        return user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def anon_client(db):
    app = FastAPI()
    app.include_router(user_mgmt_router)

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    return TestClient(app)


class TestAuthEnforcement:
    @pytest.mark.parametrize("method,path", [
        ("get", "/api/users/me"),
        ("get", "/api/users/sessions"),
        ("delete", "/api/users/sessions/s-1"),
        ("delete", "/api/users/sessions"),
    ])
    def test_anonymous_requests_rejected(self, anon_client, method, path):
        resp = getattr(anon_client, method)(path)
        assert resp.status_code == 401


class TestGetMe:
    def test_me_success(self, client):
        resp = client.get("/api/users/me", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "user-1"
        assert body["email"] == "user-1@example.com"
        assert body["name"] == "Jane Doe"
        assert body["first_name"] == "Jane"
        assert body["last_name"] == "Doe"
        assert body["role"] == "admin"
        assert body["status"] == "active"
        assert body["tenant_id"] == "t1"
        assert body["email_verified"] is None
        assert body["last_login"] is not None

    def test_me_name_falls_back_to_email(self, client, db):
        user = _make_user(db, "nameless")
        user.first_name = ""
        user.last_name = ""
        db.commit()
        resp = client.get("/api/users/me", headers=AUTH_HEADERS)
        # fixture user-1 still has names; use a dedicated client instead
        app = FastAPI()
        app.include_router(user_mgmt_router)
        app.dependency_overrides[get_db] = lambda: (yield db)
        app.dependency_overrides[get_current_user] = lambda: user
        resp = TestClient(app).get("/api/users/me")
        assert resp.json()["name"] == "nameless@example.com"


class TestListSessions:
    def test_list_sessions_with_current_token(self, client, db):
        _make_session(db, "s-1", session_token="test-token")
        _make_session(db, "s-2", session_token="tok-other")
        resp = client.get("/api/users/sessions", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        sessions = resp.json()
        assert len(sessions) == 2
        current = next(s for s in sessions if s["id"] == "s-1")
        other = next(s for s in sessions if s["id"] == "s-2")
        assert current["is_current"] is True
        assert other["is_current"] is False
        assert current["device_type"] == "mobile"
        assert current["browser"] == "Safari"
        assert current["is_active"] is True

    def test_list_sessions_cookie_token_fallback(self, client, db):
        _make_session(db, "s-1", session_token="cookie-tok")
        resp = client.get(
            "/api/users/sessions",
            headers={"Cookie": "next-auth.session-token=cookie-tok"})
        assert resp.status_code == 200
        sessions = resp.json()
        assert sessions[0]["is_current"] is True

    def test_list_sessions_secure_cookie_fallback(self, client, db):
        _make_session(db, "s-1", session_token="secure-cookie-tok")
        resp = client.get(
            "/api/users/sessions",
            headers={"Cookie": "__Secure-next-auth.session-token=secure-cookie-tok"})
        assert resp.json()[0]["is_current"] is True

    def test_list_sessions_no_token_no_current(self, client, db):
        _make_session(db, "s-1")
        resp = client.get("/api/users/sessions")
        assert resp.status_code == 200
        assert resp.json()[0]["is_current"] is False

    def test_list_sessions_filters_inactive_and_expired(self, client, db):
        _make_session(db, "s-active")
        _make_session(db, "s-inactive", is_active=False)
        _make_session(db, "s-expired", expires_days=-2)
        resp = client.get("/api/users/sessions")
        sessions = resp.json()
        assert len(sessions) == 1
        assert sessions[0]["id"] == "s-active"

    def test_list_sessions_empty(self, client):
        resp = client.get("/api/users/sessions")
        assert resp.json() == []

    def test_list_sessions_other_users_sessions_excluded(self, client, db):
        _make_session(db, "s-mine")
        _make_session(db, "s-other", user_id="other-user")
        resp = client.get("/api/users/sessions")
        assert len(resp.json()) == 1
        assert resp.json()[0]["id"] == "s-mine"


class TestRevokeSession:
    def test_revoke_session_success(self, client, db):
        _make_session(db, "s-1")
        resp = client.delete("/api/users/sessions/s-1", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["message"] == "Session revoked successfully"
        session = db.query(UserSession).filter(UserSession.id == "s-1").first()
        assert session.is_active is False

    def test_revoke_session_missing_404(self, client):
        resp = client.delete("/api/users/sessions/nope", headers=AUTH_HEADERS)
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"]["code"] == "NOT_FOUND"

    def test_revoke_session_other_users_session_404_idor(self, client, db):
        """IDOR guard: a session owned by another user must 404 — the query
        is scoped to current_user.id so it can never be revoked."""
        _make_session(db, "s-other", user_id="someone-else")
        resp = client.delete("/api/users/sessions/s-other", headers=AUTH_HEADERS)
        assert resp.status_code == 404
        session = db.query(UserSession).filter(UserSession.id == "s-other").first()
        assert session.is_active is True


class TestRevokeAllSessions:
    def test_revoke_all_except_current(self, client, db):
        _make_session(db, "s-current", session_token="test-token")
        _make_session(db, "s-1", session_token="tok-1")
        _make_session(db, "s-2", session_token="tok-2")
        resp = client.delete("/api/users/sessions", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["message"] == "All sessions revoked successfully"
        sessions = db.query(UserSession).filter(UserSession.user_id == "user-1").all()
        by_id = {s.id: s.is_active for s in sessions}
        assert by_id["s-current"] is True
        assert by_id["s-1"] is False
        assert by_id["s-2"] is False

    def test_revoke_all_without_token_revokes_everything(self, client, db):
        _make_session(db, "s-1", session_token="tok-1")
        _make_session(db, "s-2", session_token="tok-2")
        resp = client.delete("/api/users/sessions")
        assert resp.status_code == 200
        active = db.query(UserSession).filter(
            UserSession.is_active == True).count()  # noqa: E712
        assert active == 0

    def test_revoke_all_empty(self, client):
        resp = client.delete("/api/users/sessions", headers=AUTH_HEADERS)
        assert resp.status_code == 200
