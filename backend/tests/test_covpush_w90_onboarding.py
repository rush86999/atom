"""Coverage wave 90 — api/onboarding_routes.py (57% → 95%+).

Covers the Ollama TCP probe (both socket outcomes), the probe-ollama
endpoint (env parsing: default host/port, custom host+port, scheme
defaults http→80 / https→443, unparseable env fallback), the update
endpoint (step only / completed only / both / neither), status, and
401 on every endpoint.
"""
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.onboarding_routes as or_
from core.auth import get_current_user


class FakeUser:
    id = "u-1"
    onboarding_step = "welcome"
    onboarding_completed = False


@pytest.fixture
def mock_user():
    return FakeUser()


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def client(mock_user, mock_db):
    app = FastAPI()
    app.include_router(or_.router)
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[or_.get_db] = lambda: mock_db
    yield TestClient(app)
    app.dependency_overrides = {}


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(or_.router)
    yield TestClient(app)
    app.dependency_overrides = {}


class TestAuth:
    def test_update_requires_auth(self, anon_client):
        assert anon_client.post("/api/onboarding/update", json={}).status_code == 401

    def test_status_requires_auth(self, anon_client):
        assert anon_client.get("/api/onboarding/status").status_code == 401

    def test_probe_requires_auth(self, anon_client):
        assert anon_client.get("/api/onboarding/probe-ollama").status_code == 401


class TestUpdate:
    def test_update_step(self, client, mock_user, mock_db):
        resp = client.post("/api/onboarding/update", json={"step": "models"})
        assert resp.status_code == 200
        assert mock_user.onboarding_step == "models"
        assert mock_user.onboarding_completed is False
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_user)
        data = resp.json()["data"]
        assert data["onboarding_step"] == "models"

    def test_update_completed(self, client, mock_user):
        resp = client.post("/api/onboarding/update", json={"completed": True})
        assert resp.status_code == 200
        assert mock_user.onboarding_step == "welcome"
        assert mock_user.onboarding_completed is True

    def test_update_both(self, client, mock_user):
        resp = client.post(
            "/api/onboarding/update",
            json={"step": "done", "completed": True},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["onboarding_step"] == "done"
        assert data["onboarding_completed"] is True

    def test_update_neither_is_noop_but_commits(self, client, mock_user, mock_db):
        resp = client.post("/api/onboarding/update", json={})
        assert resp.status_code == 200
        assert mock_user.onboarding_step == "welcome"
        mock_db.commit.assert_called_once()

    def test_update_invalid_body_422(self, client):
        resp = client.post("/api/onboarding/update", json={"step": 123})
        assert resp.status_code == 422


class TestStatus:
    def test_status_returns_current_progress(self, client, mock_user):
        mock_user.onboarding_step = "agents"
        resp = client.get("/api/onboarding/status")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["onboarding_step"] == "agents"
        assert data["onboarding_completed"] is False


class TestProbe:
    def test_probe_ollama_reachable_default(self, client):
        with patch.object(or_, "_probe_ollama", return_value=True) as p:
            resp = client.get("/api/onboarding/probe-ollama")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["reachable"] is True
        assert data["host"] == "localhost"
        assert data["port"] == 11434
        p.assert_called_once_with("localhost", 11434)

    def test_probe_ollama_unreachable(self, client):
        with patch.object(or_, "_probe_ollama", return_value=False):
            resp = client.get("/api/onboarding/probe-ollama")
        assert resp.json()["data"]["reachable"] is False
        assert resp.json()["message"] == "Ollama not detected"

    def test_probe_ollama_custom_env_host_port(self, client):
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://10.0.0.5:1234"}), \
             patch.object(or_, "_probe_ollama", return_value=True) as p:
            resp = client.get("/api/onboarding/probe-ollama")
        assert resp.json()["data"]["host"] == "10.0.0.5"
        assert resp.json()["data"]["port"] == 1234
        p.assert_called_once_with("10.0.0.5", 1234)

    def test_probe_ollama_http_default_port_80(self, client):
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://ollama.local"}), \
             patch.object(or_, "_probe_ollama", return_value=True) as p:
            resp = client.get("/api/onboarding/probe-ollama")
        assert resp.json()["data"]["port"] == 80
        p.assert_called_once_with("ollama.local", 80)

    def test_probe_ollama_https_default_port_443(self, client):
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "https://ollama.local"}), \
             patch.object(or_, "_probe_ollama", return_value=True) as p:
            resp = client.get("/api/onboarding/probe-ollama")
        assert resp.json()["data"]["port"] == 443
        p.assert_called_once_with("ollama.local", 443)

    def test_probe_ollama_unparseable_env_falls_back(self, client):
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "not a url://%%"}), \
             patch.object(or_, "_probe_ollama", return_value=True) as p:
            resp = client.get("/api/onboarding/probe-ollama")
        assert resp.status_code == 200
        p.assert_called_once_with("localhost", 11434)

    def test_probe_ollama_urlparse_exception_tolerated(self, client):
        """urlparse raising is caught; defaults survive (logs a warning)."""
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://evil:99"}), \
             patch("urllib.parse.urlparse", side_effect=ValueError("boom")), \
             patch.object(or_, "_probe_ollama", return_value=True) as p:
            resp = client.get("/api/onboarding/probe-ollama")
        assert resp.status_code == 200
        assert resp.json()["data"]["host"] == "localhost"
        assert resp.json()["data"]["port"] == 11434
        p.assert_called_once_with("localhost", 11434)


class TestProbeHelper:
    def test_socket_connect_success_returns_true(self):
        with patch("api.onboarding_routes.socket.create_connection") as conn:
            resp = or_._probe_ollama("localhost", 11434)
        assert resp is True
        conn.assert_called_once_with(("localhost", 11434), timeout=1.5)

    def test_socket_connect_oserror_returns_false(self):
        with patch(
            "api.onboarding_routes.socket.create_connection",
            side_effect=OSError("refused"),
        ):
            assert or_._probe_ollama("localhost", 11434) is False
