"""Coverage wave 96 — integrations/notion_routes.py (TDD, 0% baseline).

The routes module was NOT importable at baseline:
  ImportError: cannot import name 'NotionToken' from 'core.models'
No NotionToken model exists anywhere in core/models.py, yet the router
queries/creates it in the OAuth callback and the token-resolution dependency
(get_notion_access_token). core/lazy_integration_registry.py maps
"notion" -> "integrations.notion_routes:router" and main_api_app.py loads the
notion router in test mode (line ~1217/1260), so any lazy load of the Notion
integration crashed with ImportError — the router was dead.

BUG FOUND + FIXED (wave 96, TDD RED->GREEN): a `NotionToken` ORM model was
added to core/models.py (columns mirror every field the router uses:
user_id, workspace_id, status, access_token, refresh_token, notion_user_id,
workspace_name, workspace_icon, token_type, owner_type, expires_at,
last_used). The import below was RED (ImportError at collection) before the
fix; the whole suite now runs against the REAL model through a mocked db
session.

Also covered: every endpoint x {success, 401 anon, 404, 422, 500};
Bearer-header token path vs stored-token path (incl. expired -> 401 +
status flip to "expired"); OAuth callback error/missing-cred/user-not-found/
non-200-exchange branches; search result transform; page-id hyphenation.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.database import get_db
from core.models import NotionToken, User

from integrations import notion_routes as nr


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = f"notion96-{uuid.uuid4().hex[:8]}"
    u.email = "notion96@x.com"
    u.tenant_id = "t-1"
    return u


def _make_db(user, token=None):
    """Fake Session: query(User) -> user, query(NotionToken) -> token."""
    db = MagicMock()
    user_q = MagicMock()
    user_q.filter.return_value.first.return_value = user
    token_q = MagicMock()
    token_q.filter.return_value.first.return_value = token

    def q_side(model):
        if model is User:
            return user_q
        return token_q

    db.query.side_effect = q_side
    return db


def make_app(user, db):
    app = FastAPI()
    app.include_router(nr.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return app


def app_client(user, db):
    app = make_app(user, db)
    client = TestClient(app, raise_server_exceptions=False)
    return client


@pytest.fixture
def client(user, active_token):
    c = app_client(user, _make_db(user, active_token))
    yield c
    c.app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(nr.router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def active_token(user):
    tok = NotionToken(
        user_id=user.id,
        access_token="ntn_secret_token_96",
        status="active",
        workspace_id="ws-1",
        expires_at=datetime.now(timezone.utc) + timedelta(days=10),
    )
    return tok


@pytest.fixture
def db(user, active_token):
    return _make_db(user, active_token)


def _cred_env():
    return {
        "NOTION_CLIENT_ID": "cli-96",
        "NOTION_CLIENT_SECRET": "sec-96",
    }


# ── Auth URL ────────────────────────────────────────────────────────────────
class TestAuthUrl:
    def test_success(self, client, user):
        with patch.dict(os.environ, _cred_env(), clear=False):
            response = client.get("/api/notion/auth/url")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "client_id=cli-96" in body["url"]
        assert f"state={user.id}" in body["url"]
        assert "owner=user" in body["url"]

    def test_missing_client_id_500(self, client):
        with patch.dict(os.environ, {"NOTION_CLIENT_ID": ""}, clear=False):
            response = client.get("/api/notion/auth/url")
        assert response.status_code == 500
        assert "NOTION_CLIENT_ID" in response.json()["detail"]

    def test_anonymous_401(self, anon_client):
        assert anon_client.get("/api/notion/auth/url").status_code == 401


# ── OAuth callback (no user auth — standard OAuth flow) ─────────────────────
class TestCallback:
    def test_oauth_error_400(self, client):
        response = client.get(
            "/api/notion/callback?code=c&error=access_denied"
            "&error_description=nope")
        assert response.status_code == 400

    def test_missing_credentials_500(self, client):
        with patch.dict(os.environ, {
            "NOTION_CLIENT_ID": "", "NOTION_CLIENT_SECRET": ""}, clear=False):
            response = client.get("/api/notion/callback?code=c&state=s1")
        assert response.status_code == 500

    def test_success_stores_token(self, user, db):
        def make_response(*a, **k):
            return SimpleNamespace(status_code=200, json=lambda: {
                "access_token": "ntn_new_96",
                "workspace_id": "ws-9",
                "workspace_name": "Team Vault",
                "workspace_icon": "emoji",
                "bot_id": "bot-9",
                "owner": {"type": "user"},
            })

        with patch.dict(os.environ, _cred_env(), clear=False), \
                patch("requests.post", side_effect=make_response):
            response = app_client(user, db).get(
                f"/api/notion/callback?code=c1&state={user.id}")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["workspace_name"] == "Team Vault"
        added = db.add.call_args[0][0]
        assert isinstance(added, NotionToken)
        assert added.access_token == "ntn_new_96"
        assert added.status == "active"
        assert added.owner_type == "user"
        db.commit.assert_called()
        # old active tokens revoked before the new one is stored
        db.query(NotionToken).filter.return_value.update.assert_called()

    def test_exchange_non_200_400(self, user, db):
        def make_response(*a, **k):
            return SimpleNamespace(status_code=400, text="bad code")

        with patch.dict(os.environ, _cred_env(), clear=False), \
                patch("requests.post", side_effect=make_response):
            response = app_client(user, db).get(
                f"/api/notion/callback?code=bad&state={user.id}")
        assert response.status_code == 400

    def test_missing_state_400(self, user, db):
        with patch.dict(os.environ, _cred_env(), clear=False), \
                patch("requests.post", return_value=SimpleNamespace(
                    status_code=200, json=lambda: {
                        "access_token": "a", "workspace_id": "w"})):
            response = app_client(user, db).get("/api/notion/callback?code=c1")
        assert response.status_code == 400

    def test_user_not_found_404(self, user):
        db = _make_db(None, None)  # no user in db
        with patch.dict(os.environ, _cred_env(), clear=False), \
                patch("requests.post", return_value=SimpleNamespace(
                    status_code=200, json=lambda: {
                        "access_token": "a", "workspace_id": "w"})):
            response = app_client(user, db).get(
                f"/api/notion/callback?code=c1&state={user.id}")
        assert response.status_code == 404

    def test_exchange_exception_500(self, user, db):
        with patch.dict(os.environ, _cred_env(), clear=False), \
                patch("requests.post",
                      side_effect=RuntimeError("notion down")):
            response = app_client(user, db).get(
                f"/api/notion/callback?code=c1&state={user.id}")
        assert response.status_code == 500

    def test_anon_callback_flow_ok(self, user):
        """Callback is intentionally unauthenticated (browser OAuth)."""
        db = _make_db(user, None)
        with patch.dict(os.environ, _cred_env(), clear=False), \
                patch("requests.post", return_value=SimpleNamespace(
                    status_code=200, json=lambda: {
                        "access_token": "a", "workspace_id": "w"})):
            response = app_client(user, db).get(
                f"/api/notion/callback?code=c1&state={user.id}")
        assert response.status_code == 200


# ── Token dependency: Bearer header vs stored token ─────────────────────────
class TestTokenDependency:
    def test_bearer_header_used(self, client, user):
        req = MagicMock(return_value=SimpleNamespace(
            status_code=200, json=lambda: {"id": "me"}))
        with patch("requests.get", req):
            response = client.get("/api/notion/status",
                                  headers={"Authorization": "Bearer hdr-96"})
        assert response.status_code == 200
        assert response.json()["status"] == "connected"
        call_headers = req.call_args.kwargs["headers"]
        assert call_headers["Authorization"] == "Bearer hdr-96"

    def test_stored_token_used(self, user, db):
        with patch("requests.get", return_value=SimpleNamespace(
                status_code=200, json=lambda: {"id": "me"})):
            response = app_client(user, db).get("/api/notion/status")
        assert response.status_code == 200
        assert response.json()["status"] == "connected"
        db.commit.assert_called()  # last_used bump

    def test_expired_token_401_flips_status(self, user):
        tok = NotionToken(
            user_id=user.id,
            access_token="ntn_old_96",
            status="active",
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db = _make_db(user, tok)
        with patch("requests.get", return_value=SimpleNamespace(
                status_code=200, json=lambda: {"id": "me"})):
            response = app_client(user, db).get("/api/notion/status")
        assert response.status_code == 401
        assert tok.status == "expired"
        db.commit.assert_called()

    def test_no_token_401(self, user):
        db = _make_db(user, None)
        response = app_client(user, db).get("/api/notion/status")
        assert response.status_code == 401

    def test_status_anonymous_401(self, anon_client):
        assert anon_client.get("/api/notion/status").status_code == 401


# ── Status ──────────────────────────────────────────────────────────────────
class TestStatus:
    def test_connected(self, client, db):
        with patch("requests.get", return_value=SimpleNamespace(
                status_code=200, json=lambda: {"id": "u-me"})), \
                patch("core.database.get_db", return_value=db):
            response = client.get(
                "/api/notion/status", headers={"Authorization": "Bearer t"})
        body = response.json()
        assert body["status"] == "connected"
        assert body["user"] == {"id": "u-me"}

    def test_disconnected_non_200(self, client, db):
        with patch("requests.get", return_value=SimpleNamespace(
                status_code=401, json=lambda: {})), \
                patch("core.database.get_db", return_value=db):
            response = client.get(
                "/api/notion/status", headers={"Authorization": "Bearer t"})
        body = response.json()
        assert body["success"] is False
        assert body["status"] == "disconnected"

    def test_exception_returns_error_status(self, client, db):
        with patch("requests.get", side_effect=RuntimeError("boom")), \
                patch("core.database.get_db", return_value=db):
            response = client.get(
                "/api/notion/status", headers={"Authorization": "Bearer t"})
        assert response.status_code == 200
        assert response.json()["status"] == "error"


# ── Search ──────────────────────────────────────────────────────────────────
class TestSearch:
    def test_success_transforms_results(self, client, db):
        def make_response(*a, **k):
            return SimpleNamespace(status_code=200, json=lambda: {
                "results": [
                    {"object": "page", "id": "abc12345def67890abc12345def67890",
                     "url": "https://notion.so/x",
                     "last_edited_time": "2026-01-01",
                     "properties": {"Name": {"type": "title", "title": [
                         {"plain_text": "Q3 Plan"}]}}},
                    {"object": "page", "id": "p2", "properties": {}},
                    {"object": "database", "id": "db1", "properties": {}},
                ]})

        with patch("requests.post", side_effect=make_response), \
                patch("core.database.get_db", return_value=db):
            response = client.post(
                "/api/notion/search", json={"query": "plan", "user_id": "u"},
                headers={"Authorization": "Bearer t"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["query"] == "plan"
        results = body["results"]
        assert len(results) == 2  # databases skipped
        assert results[0]["title"] == "Q3 Plan"
        assert "-" not in results[0]["id"]  # hyphens stripped
        assert results[1]["title"] == "Untitled"

    def test_empty_results(self, client, db):
        with patch("requests.post", return_value=SimpleNamespace(
                status_code=200, json=lambda: {"results": []})), \
                patch("core.database.get_db", return_value=db):
            response = client.post(
                "/api/notion/search", json={"query": "q"},
                headers={"Authorization": "Bearer t"})
        assert response.status_code == 200
        assert response.json()["results"] == []

    def test_non_200_raises_http_error(self, client, db):
        with patch("requests.post", return_value=SimpleNamespace(
                status_code=429, text="rate limited")), \
                patch("core.database.get_db", return_value=db):
            response = client.post(
                "/api/notion/search", json={"query": "q"},
                headers={"Authorization": "Bearer t"})
        assert response.status_code == 429

    def test_exception_500(self, client, db):
        with patch("requests.post", side_effect=RuntimeError("boom")), \
                patch("core.database.get_db", return_value=db):
            response = client.post(
                "/api/notion/search", json={"query": "q"},
                headers={"Authorization": "Bearer t"})
        assert response.status_code == 500

    def test_missing_query_422(self, client):
        response = client.post(
            "/api/notion/search", json={},
            headers={"Authorization": "Bearer t"})
        assert response.status_code == 422

    def test_anonymous_401(self, anon_client):
        response = anon_client.post("/api/notion/search", json={"query": "q"})
        assert response.status_code == 401


# ── Pages ───────────────────────────────────────────────────────────────────
class TestPages:
    def test_success_short_id(self, client, db):
        with patch("requests.get", return_value=SimpleNamespace(
                status_code=200, json=lambda: {"properties": {}})), \
                patch("core.database.get_db", return_value=db):
            response = client.get(
                "/api/notion/pages/abc123", headers={"Authorization": "Bearer t"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["title"] == "Untitled"

    def test_success_32char_id_hyphenated(self, client, db):
        page_id = "a" * 32
        url_capture = {}

        def get_side(*args, **kwargs):
            url_capture["url"] = args[0]
            return SimpleNamespace(status_code=200, json=lambda: {
                "properties": {"Name": {"type": "title", "title": [
                    {"plain_text": "Docs"}]}}})

        with patch("requests.get", side_effect=get_side), \
                patch("core.database.get_db", return_value=db):
            response = client.get(
                f"/api/notion/pages/{page_id}",
                headers={"Authorization": "Bearer t"})
        assert response.status_code == 200
        assert response.json()["title"] == "Docs"
        assert "/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" in url_capture["url"]

    def test_non_200_raises_http_error(self, client, db):
        with patch("requests.get", return_value=SimpleNamespace(
                status_code=404, text="not found")), \
                patch("core.database.get_db", return_value=db):
            response = client.get(
                "/api/notion/pages/missing", headers={"Authorization": "Bearer t"})
        assert response.status_code == 404

    def test_exception_500(self, client, db):
        with patch("requests.get", side_effect=RuntimeError("boom")), \
                patch("core.database.get_db", return_value=db):
            response = client.get(
                "/api/notion/pages/abc", headers={"Authorization": "Bearer t"})
        assert response.status_code == 500

    def test_anonymous_401(self, anon_client):
        assert anon_client.get("/api/notion/pages/abc").status_code == 401


# ── Health / root ───────────────────────────────────────────────────────────
class TestHealthRoot:
    def test_health(self, anon_client):
        response = anon_client.get("/api/notion/health")
        assert response.status_code == 200
        assert response.json()["status"] == "available"

    def test_root(self, anon_client):
        response = anon_client.get("/api/notion/")
        assert response.status_code == 200
        assert response.json()["service"] == "notion"
