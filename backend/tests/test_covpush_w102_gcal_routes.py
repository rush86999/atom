"""Coverage wave 102 — integrations/google_calendar_routes.py (TDD, 0%
baseline).

Fully mocked (module-level google_oauth OAuthHandler, token_storage and
google_calendar_service patched), zero network, zero LLM spend.

Auth note: every route in this module is OAuth-flow/status metadata only
(/auth/url generates the authorization URL, /callback is the OAuth redirect
that exchanges the user's own code — public by design like the wave-93
dropbox /callback, /status and /health return static flags) — none reads
user data, so all stay public. No auth bug present.

Covers: /auth/url (success with/without state, HTTPException passthrough,
generic failure -> 500), /callback (success with/without state, user-denied
error param, exchange failure -> 400, generic failure -> 500, missing code ->
422), /status, /health.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from integrations import google_calendar_routes as gcr


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(gcr.router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _deps():
    with patch.object(gcr.google_oauth, "get_authorization_url",
                      return_value="https://accounts.google.com/o/oauth2/v2/auth"), \
            patch.object(gcr.google_oauth, "exchange_code_for_tokens",
                         new=AsyncMock(
                             return_value={"access_token": "at", "refresh_token": "rt"})), \
            patch.object(gcr.token_storage, "save_token",
                         new=MagicMock()) as save, \
            patch.object(gcr.google_calendar_service, "authenticate",
                         return_value=True):
        yield {
            "save_token": save,
            "authenticate": gcr.google_calendar_service.authenticate,
        }


class TestAuthUrl:
    def test_success(self, anon_client):
        response = anon_client.get("/api/google-calendar/auth/url")
        assert response.status_code == 200
        body = response.json()
        assert body["url"] == "https://accounts.google.com/o/oauth2/v2/auth"
        assert "timestamp" in body
        gcr.google_oauth.get_authorization_url.assert_called_once_with(
            state=None)

    def test_success_with_state(self, anon_client):
        response = anon_client.get("/api/google-calendar/auth/url",
                                   params={"state": "s1"})
        assert response.status_code == 200
        gcr.google_oauth.get_authorization_url.assert_called_once_with(
            state="s1")

    def test_http_exception_passthrough(self, anon_client):
        gcr.google_oauth.get_authorization_url.side_effect = HTTPException(
            status_code=400, detail="bad state")
        response = anon_client.get("/api/google-calendar/auth/url")
        assert response.status_code == 400
        assert response.json()["detail"] == "bad state"

    def test_generic_failure_500(self, anon_client):
        gcr.google_oauth.get_authorization_url.side_effect = \
            RuntimeError("boom")
        response = anon_client.get("/api/google-calendar/auth/url")
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal error"


class TestCallback:
    def test_success_with_state(self, anon_client, _deps):
        response = anon_client.get(
            "/api/google-calendar/callback",
            params={"code": "auth-code", "state": "user-42"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["status"] == "success"
        assert body["test_connection"] is True
        assert body["user_id"] == "user-42"
        gcr.google_oauth.exchange_code_for_tokens.assert_awaited_once_with(
            "auth-code")
        _deps["save_token"].assert_called_once()
        _deps["authenticate"].assert_called_once()

    def test_success_default_user(self, anon_client, _deps):
        response = anon_client.get("/api/google-calendar/callback",
                                   params={"code": "auth-code"})
        assert response.status_code == 200
        assert response.json()["user_id"] == "default"

    def test_denied_error_param(self, anon_client):
        response = anon_client.get(
            "/api/google-calendar/callback",
            params={"code": "x", "error": "access_denied"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is False
        assert body["status"] == "error"
        assert body["error"] == "access_denied"
        assert "denied" in body["message"]

    def test_exchange_failure_400(self, anon_client):
        gcr.google_oauth.exchange_code_for_tokens.return_value = {}
        response = anon_client.get("/api/google-calendar/callback",
                                   params={"code": "bad-code"})
        assert response.status_code == 400
        assert response.json()["detail"] == \
            "Failed to exchange authorization code for tokens"

    def test_generic_failure_500(self, anon_client):
        gcr.google_oauth.exchange_code_for_tokens.side_effect = \
            RuntimeError("network down")
        response = anon_client.get("/api/google-calendar/callback",
                                   params={"code": "x"})
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal error"

    def test_missing_code_422(self, anon_client):
        response = anon_client.get("/api/google-calendar/callback")
        assert response.status_code == 422


class TestStatusHealth:
    def test_status(self, anon_client):
        response = anon_client.get("/api/google-calendar/status")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "active"
        assert body["service"] == "google-calendar"
        assert body["business_value"]["scheduling"] is True

    def test_health(self, anon_client):
        response = anon_client.get("/api/google-calendar/health")
        assert response.status_code == 200
        assert response.json()["status"] == "active"
