"""Coverage wave 100 — integrations/teams_routes.py (TDD, 0% baseline).

Fully mocked (MessagingActionDispatcher, rate limiter, HMAC secret),
zero network, zero LLM spend.

BUG FOUND + FIXED (TDD RED->GREEN):
1. Adaptive-card webhook dispatch crashed: teams_routes.py:158 called
   `teams_dispatcher.dispatch(...)` but MessagingActionDispatcher has NO
   `dispatch` method (it exposes async `dispatch_action(platform,
   tenant_id, user_id, action_id, payload)`). Any signed adaptive-card
   action with an action_id raised AttributeError -> 500. The test below
   was RED (500) before the fix; the route now awaits the real
   `dispatch_action` with proper arguments and degrades gracefully
   (logs + returns the empty Teams reply) if dispatch fails.
2. The /search data route had NO authentication — anyone could use the
   platform's Teams search. The anonymous-401 test was RED (200) before
   the fix; `get_current_user` is now required. OAuth flow (/auth/url,
   /callback), /status and the HMAC-protected /webhook stay public.

Covers: _RateLimiter unit (allow/deny at limit, window expiry),
verify_teams_signature (missing secret, bad prefix, valid, tampered,
bad base64), /auth/url, /callback, /status, /search (success + 422 +
anon 401), /webhook (429, no/valid/tampered HMAC, invalid JSON, plain
payload, adaptive card with/without action_id, dispatch failure
degradation).
"""
import base64
import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.models import User

from integrations import teams_routes as tr


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = "teams100-user"
    u.email = "teams100@x.com"
    return u


@pytest.fixture
def client(user):
    app = FastAPI()
    app.include_router(tr.router)
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(tr.router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def webhook_secret(monkeypatch):
    secret = base64.b64encode(b"teams-secret-w100").decode()
    monkeypatch.setattr(tr, "TEAMS_WEBHOOK_SECRET", secret)
    return secret


def _sign(secret, raw_body: bytes) -> str:
    mac = hmac.new(base64.b64decode(secret), raw_body,
                   hashlib.sha256).digest()
    return "HMAC " + base64.b64encode(mac).decode()


class TestRateLimiter:
    def test_allows_until_limit(self):
        limiter = tr._RateLimiter(limit=3, window=60)
        assert limiter.check("ip-1") is True
        assert limiter.check("ip-1") is True
        assert limiter.check("ip-1") is True
        assert limiter.check("ip-1") is False

    def test_keys_isolated(self):
        limiter = tr._RateLimiter(limit=2, window=60)
        assert limiter.check("ip-a") is True
        assert limiter.check("ip-b") is True
        assert limiter.check("ip-a") is True
        assert limiter.check("ip-a") is False
        assert limiter.check("ip-b") is True

    def test_window_expiry(self):
        limiter = tr._RateLimiter(limit=2, window=60)
        clock = [1_000_000.0]
        with patch("time.time", side_effect=lambda: clock[0]):
            assert limiter.check("ip-x") is True
            assert limiter.check("ip-x") is True
            assert limiter.check("ip-x") is False
        clock[0] += 61
        assert limiter.check("ip-x") is True

    def test_default_constructor(self):
        limiter = tr._RateLimiter()
        assert limiter.limit == 30
        assert limiter.window == 60


class TestSignatureVerification:
    def test_missing_secret_fails_closed(self, webhook_secret, monkeypatch):
        monkeypatch.setattr(tr, "TEAMS_WEBHOOK_SECRET", "")
        assert tr.verify_teams_signature(b"{}",
                                         "HMAC whatever") is False

    def test_bad_prefix_fails(self, webhook_secret):
        assert tr.verify_teams_signature(b"{}", "Bearer abc") is False

    def test_valid_signature(self, webhook_secret):
        raw = b'{"type": "message"}'
        assert tr.verify_teams_signature(raw,
                                         _sign(webhook_secret, raw)) is True

    def test_tampered_body(self, webhook_secret):
        raw = b'{"type": "message"}'
        auth = _sign(webhook_secret, raw)
        assert tr.verify_teams_signature(b'{"type": "other"}', auth) is False

    def test_tampered_signature(self, webhook_secret):
        raw = b'{"type": "message"}'
        assert tr.verify_teams_signature(raw, "HMAC " + "A" * 16) is False

    def test_invalid_base64_secret(self, monkeypatch):
        monkeypatch.setattr(tr, "TEAMS_WEBHOOK_SECRET", "not-base64!!")
        assert tr.verify_teams_signature(b"{}", "HMAC xyz") is False


class TestOAuthFlowEndpoints:
    def test_auth_url(self, anon_client):
        response = anon_client.get("/api/teams/auth/url")
        assert response.status_code == 200
        body = response.json()
        assert body["url"].startswith(
            "https://login.microsoftonline.com/common/oauth2/v2.0/authorize")
        assert "timestamp" in body

    def test_callback(self, anon_client):
        response = anon_client.get("/api/teams/callback",
                                   params={"code": "code-1"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["code"] == "code-1"

    def test_status(self, anon_client):
        response = anon_client.get("/api/teams/status")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "connected"
        assert body["service"] == "teams"
        assert body["user_id"] == "test_user"


class TestSearch:
    def test_success(self, client):
        response = client.post("/api/teams/search",
                               json={"query": "quarterly report"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["query"] == "quarterly report"
        assert body["results"][0]["title"] == \
            "Teams Result - quarterly report"
        assert "timestamp" in body

    def test_custom_user_id(self, client):
        response = client.post("/api/teams/search",
                               json={"query": "x", "user_id": "u9"})
        assert response.status_code == 200
        assert response.json()["results"][0]["snippet"] == \
            "Result for query: x"

    def test_missing_query_422(self, client):
        response = client.post("/api/teams/search", json={})
        assert response.status_code == 422

    def test_anonymous_401(self, anon_client):
        response = anon_client.post("/api/teams/search",
                                    json={"query": "q"})
        assert response.status_code == 401


class TestWebhook:
    def test_rate_limited_429(self, webhook_secret, anon_client):
        with patch.object(tr.teams_rate_limiter, "check",
                          return_value=False):
            response = anon_client.post("/api/teams/webhook",
                                        content=b"{}",
                                        headers={"Authorization":
                                                 "HMAC x"})
        assert response.status_code == 429

    def test_missing_signature_401(self, webhook_secret, anon_client):
        response = anon_client.post("/api/teams/webhook", content=b"{}")
        assert response.status_code == 401
        assert response.json()["detail"] == "invalid webhook signature"

    def test_invalid_signature_401(self, webhook_secret, anon_client):
        response = anon_client.post(
            "/api/teams/webhook", content=b"{}",
            headers={"Authorization": "HMAC " + "B" * 20})
        assert response.status_code == 401

    def test_invalid_json_400(self, webhook_secret, anon_client):
        response = anon_client.post(
            "/api/teams/webhook", content=b"{not json}",
            headers={"Authorization": _sign(webhook_secret,
                                            b"{not json}")})
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid JSON"

    def test_plain_payload_ok(self, webhook_secret, anon_client):
        raw = json.dumps({"type": "message", "text": "hello"}).encode()
        response = anon_client.post(
            "/api/teams/webhook", content=raw,
            headers={"Authorization": _sign(webhook_secret, raw)})
        assert response.status_code == 200
        assert response.json() == {"type": "message", "text": ""}

    def test_value_not_dict_ok(self, webhook_secret, anon_client):
        raw = json.dumps({"value": "not-a-dict"}).encode()
        response = anon_client.post(
            "/api/teams/webhook", content=raw,
            headers={"Authorization": _sign(webhook_secret, raw)})
        assert response.status_code == 200

    def test_action_without_action_id_no_dispatch(
            self, webhook_secret, anon_client):
        with patch.object(tr, "teams_dispatcher") as dispatcher:
            raw = json.dumps({"value": {"foo": "bar"}}).encode()
            response = anon_client.post(
                "/api/teams/webhook", content=raw,
                headers={"Authorization": _sign(webhook_secret, raw)})
        assert response.status_code == 200
        dispatcher.dispatch_action.assert_not_called()

    def test_adaptive_card_dispatches(self, webhook_secret, anon_client):
        """RED before bug fix #1: AttributeError -> 500."""
        dispatcher = MagicMock()
        dispatcher.dispatch_action = AsyncMock(return_value={
            "success": True})
        payload = {
            "type": "message",
            "from": {"id": "user-9"},
            "value": {"action_id": "approve:123"},
        }
        raw = json.dumps(payload).encode()
        with patch.object(tr, "teams_dispatcher", dispatcher):
            response = anon_client.post(
                "/api/teams/webhook", content=raw,
                headers={"Authorization": _sign(webhook_secret, raw)})
        assert response.status_code == 200
        dispatcher.dispatch_action.assert_awaited_once_with(
            platform="teams", tenant_id="default",
            user_id="user-9", action_id="approve:123", payload=payload)

    def test_dispatch_failure_degrades(self, webhook_secret, anon_client):
        """Webhook stays responsive even if the dispatcher crashes."""
        dispatcher = MagicMock()
        dispatcher.dispatch_action = AsyncMock(
            side_effect=RuntimeError("dispatch boom"))
        payload = {"from": {"id": "u1"},
                   "value": {"action_id": "reject:9"}}
        raw = json.dumps(payload).encode()
        with patch.object(tr, "teams_dispatcher", dispatcher):
            response = anon_client.post(
                "/api/teams/webhook", content=raw,
                headers={"Authorization": _sign(webhook_secret, raw)})
        assert response.status_code == 200
        assert response.json() == {"type": "message", "text": ""}
