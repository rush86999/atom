"""Coverage wave 105 — integrations/jira_routes.py (TDD, 0% baseline).

Fully mocked, zero network, zero LLM spend.

BUG FOUND + FIXED (TDD RED->GREEN): POST /search and GET /items had NO
authentication — anonymous callers could invoke the search surface. The
anonymous-401 tests below were RED (200) before the fix; `get_current_user`
is now required on both data endpoints. (/auth/url, /callback, /status stay
public, matching the wave-98/102 dropbox/box convention.)

Covers: /auth/url (public), /callback (public success + echo code),
/status (public + user_id echo), /search (success + results content,
missing query -> 422, anon 401), /items (success + 5 items, anon 401).
"""
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.models import User

from integrations import jira_routes as jr


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = "jira105-user"
    u.email = "jira105@x.com"
    return u


@pytest.fixture
def client(user):
    app = FastAPI()
    app.include_router(jr.router)
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(jr.router)
    return TestClient(app, raise_server_exceptions=False)


class TestAuthUrl:
    def test_success(self, anon_client):
        response = anon_client.get("/api/jira/auth/url")
        assert response.status_code == 200
        body = response.json()
        assert "url" in body and "timestamp" in body
        assert "atlassian.com" in body["url"]


class TestCallback:
    def test_success(self, anon_client):
        response = anon_client.get("/api/jira/callback", params={"code": "abc"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["status"] == "success"
        assert body["code"] == "abc"
        assert "timestamp" in body


class TestStatus:
    def test_success(self, anon_client):
        response = anon_client.get("/api/jira/status")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["service"] == "jira"
        assert body["status"] == "connected"
        assert body["user_id"] == "test_user"

    def test_custom_user_id(self, anon_client):
        response = anon_client.get("/api/jira/status", params={"user_id": "u1"})
        assert response.json()["user_id"] == "u1"


class TestSearch:
    def test_success(self, client):
        response = client.post("/api/jira/search", json={"query": "ticket"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["query"] == "ticket"
        assert body["results"][0]["title"] == "Sample Jira Result - ticket"
        assert "timestamp" in body

    def test_custom_user_id_default(self, client):
        response = client.post("/api/jira/search",
                               json={"query": "x", "user_id": "u9"})
        assert response.status_code == 200
        assert response.json()["query"] == "x"

    def test_missing_query_422(self, client):
        response = client.post("/api/jira/search", json={})
        assert response.status_code == 422

    def test_anonymous_401(self, anon_client):
        response = anon_client.post("/api/jira/search", json={"query": "ticket"})
        assert response.status_code == 401


class TestItems:
    def test_success(self, client):
        response = client.get("/api/jira/items")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert len(body["items"]) == 5
        assert body["items"][0]["id"] == "item_1"
        assert "timestamp" in body

    def test_custom_user_id(self, client):
        response = client.get("/api/jira/items", params={"user_id": "u2"})
        assert response.status_code == 200

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/api/jira/items")
        assert response.status_code == 401
