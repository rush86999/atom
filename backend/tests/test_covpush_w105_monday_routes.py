"""Coverage wave 105 — integrations/monday_routes.py (TDD, 0% baseline).

Fully mocked, zero network, zero LLM spend.

BUG FOUND + FIXED (TDD RED->GREEN): POST /search had NO authentication —
anonymous callers could invoke the search surface. The anonymous-401 test
below was RED (200) before the fix; `get_current_user` is now required on
the data endpoint. (/auth/url, /callback, /status stay public, matching the
wave-98/102 dropbox/box convention.)

Covers: /auth/url (public), /callback (public success + echo code),
/status (public + user_id echo), /search (success + board results, missing
query -> 422, anon 401).
"""
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.models import User

from integrations import monday_routes as mr


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = "monday105-user"
    u.email = "monday105@x.com"
    return u


@pytest.fixture
def client(user):
    app = FastAPI()
    app.include_router(mr.router)
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(mr.router)
    return TestClient(app, raise_server_exceptions=False)


class TestAuthUrl:
    def test_success(self, anon_client):
        response = anon_client.get("/api/monday/auth/url")
        assert response.status_code == 200
        body = response.json()
        assert "url" in body and "timestamp" in body
        assert "monday.com" in body["url"]


class TestCallback:
    def test_success(self, anon_client):
        response = anon_client.get("/api/monday/callback", params={"code": "abc"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["status"] == "success"
        assert body["code"] == "abc"
        assert "timestamp" in body


class TestStatus:
    def test_success(self, anon_client):
        response = anon_client.get("/api/monday/status")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["service"] == "monday"
        assert body["status"] == "connected"
        assert body["user_id"] == "test_user"

    def test_custom_user_id(self, anon_client):
        response = anon_client.get("/api/monday/status", params={"user_id": "u1"})
        assert response.json()["user_id"] == "u1"


class TestSearch:
    def test_success(self, client):
        response = client.post("/api/monday/search", json={"query": "launch"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["query"] == "launch"
        assert body["results"][0]["title"] == "Project Board - launch"
        assert body["results"][0]["type"] == "board"
        assert "timestamp" in body

    def test_custom_user_id_default(self, client):
        response = client.post("/api/monday/search",
                               json={"query": "x", "user_id": "u9"})
        assert response.status_code == 200
        assert response.json()["query"] == "x"

    def test_missing_query_422(self, client):
        response = client.post("/api/monday/search", json={})
        assert response.status_code == 422

    def test_anonymous_401(self, anon_client):
        response = anon_client.post("/api/monday/search", json={"query": "launch"})
        assert response.status_code == 401
