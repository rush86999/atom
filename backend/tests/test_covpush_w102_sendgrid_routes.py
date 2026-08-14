"""Coverage wave 102 — integrations/sendgrid_routes.py (TDD, 0% baseline).

Fully mocked (httpx.AsyncClient patched, SENDGRID_ENABLED/api_key patched),
zero network, zero LLM spend.

Auth note: every route in this module is OAuth-flow/status metadata only
(/auth/url returns a static URL, /callback is a mock, /status and /health
return static capability flags) — none reads user data or performs an action,
so all stay public per the wave-93 dropbox convention (OAuth URL/callback and
status endpoints public; only data/action endpoints require get_current_user).
`SendGridService.send_email` is not wired to any route in this module; it is
unit-tested directly with a mocked HTTP client.

Covers: /auth/url, /callback (success + missing key -> 422), /status,
/health, SendGridService.send_email (disabled flag, unconfigured key,
mock_api_key, sent 200/202 with X-Message-Id, API error -> HTTPException),
SendGridService.__init__ (all four flag/key combinations).
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from integrations import sendgrid_routes as sr


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(sr.router)
    return TestClient(app, raise_server_exceptions=False)


class FakeSendGridResponse:
    status_code = 202
    headers = {"X-Message-Id": "msg-102"}
    text = "accepted"


class TestAuthUrl:
    def test_success(self, anon_client):
        response = anon_client.get("/api/sendgrid/auth/url")
        assert response.status_code == 200
        body = response.json()
        assert body["url"] == "https://app.sendgrid.com/settings/api_keys"
        assert "timestamp" in body


class TestCallback:
    def test_success(self, anon_client):
        response = anon_client.get("/api/sendgrid/callback",
                                   params={"key": "k1"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["status"] == "success"
        assert "timestamp" in body

    def test_missing_key_422(self, anon_client):
        response = anon_client.get("/api/sendgrid/callback")
        assert response.status_code == 422


class TestStatusHealth:
    def test_status(self, anon_client):
        response = anon_client.get("/api/sendgrid/status")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "active"
        assert body["service"] == "sendgrid"
        assert body["business_value"]["email_marketing"] is True

    def test_health(self, anon_client):
        response = anon_client.get("/api/sendgrid/health")
        assert response.status_code == 200
        assert response.json()["status"] == "active"


class TestSendGridServiceInit:
    def test_enabled_with_key(self, monkeypatch):
        monkeypatch.setattr(sr, "SENDGRID_ENABLED", True)
        monkeypatch.setenv("SENDGRID_API_KEY", "SG.real-key")
        svc = sr.SendGridService()
        assert svc.api_key == "SG.real-key"

    def test_disabled_flag(self, monkeypatch):
        monkeypatch.setattr(sr, "SENDGRID_ENABLED", False)
        svc = sr.SendGridService()
        assert svc.api_key is None

    def test_enabled_no_key(self, monkeypatch):
        monkeypatch.setattr(sr, "SENDGRID_ENABLED", True)
        monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
        svc = sr.SendGridService()
        assert svc.api_key is None

    def test_enabled_mock_key(self, monkeypatch):
        monkeypatch.setattr(sr, "SENDGRID_ENABLED", True)
        monkeypatch.setenv("SENDGRID_API_KEY", "mock_api_key")
        svc = sr.SendGridService()
        assert svc.api_key == "mock_api_key"


class TestSendEmail:
    def test_disabled(self, monkeypatch):
        monkeypatch.setattr(sr, "SENDGRID_ENABLED", False)
        result = asyncio.run(
            sr.sendgrid_service.send_email("a@b.com", "Hi", "body"))
        assert result["success"] is False
        assert result["status"] == "disabled"

    def test_unconfigured_key(self, monkeypatch):
        monkeypatch.setattr(sr, "SENDGRID_ENABLED", True)
        monkeypatch.setattr(sr.sendgrid_service, "api_key", None)
        result = asyncio.run(
            sr.sendgrid_service.send_email("a@b.com", "Hi", "body"))
        assert result["success"] is False
        assert result["status"] == "unconfigured"

    def test_mock_key(self, monkeypatch):
        monkeypatch.setattr(sr, "SENDGRID_ENABLED", True)
        monkeypatch.setattr(sr.sendgrid_service, "api_key", "mock_api_key")
        result = asyncio.run(
            sr.sendgrid_service.send_email("a@b.com", "Hi", "body"))
        assert result["status"] == "unconfigured"

    def test_sent(self, monkeypatch):
        monkeypatch.setattr(sr, "SENDGRID_ENABLED", True)
        monkeypatch.setattr(sr.sendgrid_service, "api_key", "SG.real")
        with patch("integrations.sendgrid_routes.httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=FakeSendGridResponse())
            result = asyncio.run(
                sr.sendgrid_service.send_email("a@b.com", "Hi", "body"))
        assert result["success"] is True
        assert result["status"] == "sent"
        assert result["message_id"] == "msg-102"
        call = ac.return_value.__aenter__.return_value.post
        call.assert_awaited_once()
        sent_json = call.await_args.kwargs["json"]
        assert sent_json["personalizations"][0]["to"] == [{"email": "a@b.com"}]

    def test_api_error_raises(self, monkeypatch):
        monkeypatch.setattr(sr, "SENDGRID_ENABLED", True)
        monkeypatch.setattr(sr.sendgrid_service, "api_key", "SG.real")

        class ErrorResponse:
            status_code = 401
            headers = {}
            text = "invalid key"

        with patch("integrations.sendgrid_routes.httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=ErrorResponse())
            with pytest.raises(HTTPException) as exc:
                asyncio.run(sr.sendgrid_service.send_email(
                    "a@b.com", "Hi", "body"))
        assert exc.value.status_code == 401
        assert "invalid key" in exc.value.detail
