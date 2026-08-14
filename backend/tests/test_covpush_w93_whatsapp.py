"""Coverage wave 93 — integrations/whatsapp_fastapi_routes.py (security audit).

W64 covered this module to 99%; the wave-93 audit found REAL fail-open
webhook bugs (the R45 class already fixed in whatsapp_business_integration):

1. GET /webhook verification accepted ANY hub.verify_token when
   hub.mode=subscribe ("For development, accept any token") — an attacker
   can complete the Meta handshake, and the endpoint never validated the
   token at all. Now: 403 unless the token matches the configured
   WHATSAPP_VERIFY_TOKEN (env) or whatsapp_integration.webhook_verify_token;
   unconfigured token => fail closed 403.

2. POST /webhook had NO signature verification — any unauthenticated POST
   was queued to universal_webhook_bridge (forged-events vector). Now:
   missing app secret => 503; missing/malformed X-Hub-Signature-256 => 401;
   HMAC mismatch => 401. Verified requests process as before.

3. Data-exposing endpoints (conversations, messages, analytics, exports,
   business-profile GET, service/initialize) were unauthenticated.
   get_current_user is now required on all of them.

Also closes the W64 gap (send_batch outer except, lines 221-223) and adds
401-anonymous checks on every auth-gated endpoint.

Every integration dependency is mocked; no network, no LLM spend.
"""
import base64
import hashlib
import hmac
import sys
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from integrations import whatsapp_fastapi_routes as wa
from core.models import User

APP_SECRET = "0123456789abcdef0123456789abcdef"
VERIFY_TOKEN = "meta-verify-93"


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = f"wa93-{uuid.uuid4().hex[:8]}"
    u.email = "wa93@x.com"
    u.tenant_id = "t-1"
    return u


@pytest.fixture
def client(user):
    app = FastAPI()
    app.include_router(wa.router)
    from core.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(wa.router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def svc():
    integration = MagicMock()
    integration.send_message.return_value = {"success": True,
                                             "message_id": "wamid-93"}
    integration.get_conversations.return_value = [
        {"whatsapp_id": "w1", "name": "Alice", "phone_number": "+15550001",
         "status": "open", "last_message": "hi",
         "last_message_at": "2026-08-01T10:00:00"}]
    integration.get_messages.return_value = [{"id": "m1", "text": "hi"}]
    integration.create_template.return_value = {"success": True,
                                                "template_id": "tpl-1"}
    integration.get_analytics.return_value = {"message_statistics": []}

    manager = MagicMock()
    manager.config = {"business_profile": {"name": "ACME"}}
    manager.health_check.return_value = {"status": "healthy", "uptime": 99}
    manager.get_service_metrics.return_value = {"messages_sent": 10}
    manager.initialize_service.return_value = {"success": True}

    with patch.object(wa, "whatsapp_integration", integration), \
            patch.object(wa, "whatsapp_service_manager", manager), \
            patch.object(wa, "WHATSAPP_AVAILABLE", True):
        yield integration, manager


def _signed_headers(body: bytes) -> dict:
    digest = hmac.new(APP_SECRET.encode(), body, hashlib.sha256).digest()
    return {
        "X-Hub-Signature-256": "sha256=" + digest.hex(),
        "Content-Type": "application/json",
    }


def _signed_json(payload: dict) -> tuple:
    body = __import__("json").dumps(payload).encode()
    return body, _signed_headers(body)


class TestWebhookVerificationFailClosed:
    """Wave-93 regression: GET /webhook must validate hub.verify_token."""

    def test_subscribe_matching_token_200(self, anon_client, monkeypatch):
        monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", VERIFY_TOKEN)
        response = anon_client.get(
            "/api/whatsapp/webhook?hub.mode=subscribe"
            f"&hub.verify_token={VERIFY_TOKEN}&hub.challenge=CH93")
        assert response.status_code == 200
        assert response.json() == "CH93"

    def test_subscribe_wrong_token_403(self, anon_client, monkeypatch):
        monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", VERIFY_TOKEN)
        response = anon_client.get(
            "/api/whatsapp/webhook?hub.mode=subscribe"
            "&hub.verify_token=attacker-token&hub.challenge=CH93")
        assert response.status_code == 403

    def test_subscribe_missing_token_fail_closed_403(self, anon_client):
        """No verify token configured => never satisfy the handshake."""
        with patch.dict("os.environ", {}, clear=False):
            pass
        monkeypatch_del = None
        import os as _os
        saved = _os.environ.pop("WHATSAPP_VERIFY_TOKEN", None)
        try:
            response = anon_client.get(
                "/api/whatsapp/webhook?hub.mode=subscribe"
                "&hub.verify_token=anything&hub.challenge=CH93")
        finally:
            if saved is not None:
                _os.environ["WHATSAPP_VERIFY_TOKEN"] = saved
        assert response.status_code == 403

    def test_mode_not_subscribe_403(self, anon_client, monkeypatch):
        monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", VERIFY_TOKEN)
        response = anon_client.get(
            "/api/whatsapp/webhook?hub.mode=unsubscribe"
            f"&hub.verify_token={VERIFY_TOKEN}&hub.challenge=CH93")
        assert response.status_code == 403

    def test_verify_token_lookup_error_403(self, anon_client):
        with patch.object(wa, "_get_webhook_verify_token",
                          side_effect=RuntimeError("env broken")):
            response = anon_client.get(
                "/api/whatsapp/webhook?hub.mode=subscribe"
                "&hub.verify_token=x&hub.challenge=CH93")
        assert response.status_code == 403

    def test_token_from_integration_config(self, anon_client):
        """Falls back to whatsapp_integration.webhook_verify_token."""
        integration = MagicMock()
        integration.webhook_verify_token = VERIFY_TOKEN
        with patch.object(wa, "whatsapp_integration", integration), \
                patch.dict("os.environ", {}, clear=True):
            response = anon_client.get(
                "/api/whatsapp/webhook?hub.mode=subscribe"
                f"&hub.verify_token={VERIFY_TOKEN}&hub.challenge=CH93")
        assert response.status_code == 200
        assert response.json() == "CH93"


class TestWebhookSignatureFailClosed:
    """Wave-93 regression: POST /webhook requires a valid HMAC signature."""

    def test_no_secret_503(self, anon_client):
        with patch.object(wa, "whatsapp_integration",
                          MagicMock(webhook_app_secret=None)), \
                patch.dict("os.environ", {}, clear=True):
            response = anon_client.post(
                "/api/whatsapp/webhook", json={"entry": [{"id": "p1"}]})
        assert response.status_code == 503

    def test_missing_signature_401(self, anon_client, monkeypatch):
        monkeypatch.setenv("WHATSAPP_APP_SECRET", APP_SECRET)
        response = anon_client.post(
            "/api/whatsapp/webhook",
            json={"entry": [{"id": "p1"}]},
            headers={"Content-Type": "application/json"})
        assert response.status_code == 401

    def test_bad_signature_401(self, anon_client, monkeypatch):
        monkeypatch.setenv("WHATSAPP_APP_SECRET", APP_SECRET)
        response = anon_client.post(
            "/api/whatsapp/webhook",
            json={"entry": [{"id": "p1"}]},
            headers={"X-Hub-Signature-256": "sha256=deadbeef",
                     "Content-Type": "application/json"})
        assert response.status_code == 401

    def test_malformed_signature_header_401(self, anon_client, monkeypatch):
        monkeypatch.setenv("WHATSAPP_APP_SECRET", APP_SECRET)
        response = anon_client.post(
            "/api/whatsapp/webhook",
            json={"entry": [{"id": "p1"}]},
            headers={"X-Hub-Signature-256": "hmac:abc",
                     "Content-Type": "application/json"})
        assert response.status_code == 401

    def test_valid_signature_processed_200(self, anon_client, monkeypatch):
        monkeypatch.setenv("WHATSAPP_APP_SECRET", APP_SECRET)
        from integrations import universal_webhook_bridge
        with patch.object(
                universal_webhook_bridge.universal_webhook_bridge,
                "process_incoming_message",
                new=AsyncMock(return_value=True)) as process:
            body, headers = _signed_json({"entry": [{"id": "p1"}]})
            response = anon_client.post("/api/whatsapp/webhook",
                                        content=body, headers=headers)
        assert response.status_code == 200
        assert response.json() == {"status": "received"}
        process.assert_called_once()
        assert process.call_args[0][0] == "whatsapp"

    def test_valid_signature_from_integration_secret(self, anon_client):
        integration = MagicMock()
        integration.webhook_app_secret = APP_SECRET
        from integrations import universal_webhook_bridge
        with patch.object(wa, "whatsapp_integration", integration), \
                patch.dict("os.environ", {}, clear=True), \
                patch.object(
                    universal_webhook_bridge.universal_webhook_bridge,
                    "process_incoming_message",
                    new=AsyncMock(return_value=True)):
            body, headers = _signed_json({"entry": [{"id": "p1"}]})
            response = anon_client.post("/api/whatsapp/webhook",
                                        content=body, headers=headers)
        assert response.status_code == 200

    def test_valid_signature_bridge_error_500(self, anon_client, monkeypatch):
        """Import failure inside the handler surfaces as 500 (fire-and-forget
        task errors are intentionally invisible to the HTTP response)."""
        monkeypatch.setenv("WHATSAPP_APP_SECRET", APP_SECRET)
        saved = sys.modules.get("integrations.universal_webhook_bridge")
        sys.modules["integrations.universal_webhook_bridge"] = None
        try:
            body, headers = _signed_json({"entry": [{"id": "p1"}]})
            response = anon_client.post("/api/whatsapp/webhook",
                                        content=body, headers=headers)
        finally:
            if saved is not None:
                sys.modules["integrations.universal_webhook_bridge"] = saved
        assert response.status_code == 500


class TestAuthGates:
    """Wave-93 regression: data/state endpoints require authentication."""

    @pytest.mark.parametrize("method,path", [
        ("get", "/api/whatsapp/conversations"),
        ("get", "/api/whatsapp/conversations/search?query=x"),
        ("get", "/api/whatsapp/messages/w1"),
        ("get", "/api/whatsapp/messages"),
        ("get", "/api/whatsapp/analytics"),
        ("get", "/api/whatsapp/analytics/export?format=json"),
        ("get", "/api/whatsapp/configuration/business-profile"),
        ("post", "/api/whatsapp/service/initialize"),
    ])
    def test_anonymous_401(self, anon_client, method, path):
        response = getattr(anon_client, method)(path)
        assert response.status_code == 401

    @pytest.mark.parametrize("method,path", [
        ("post", "/api/whatsapp/send"),
        ("post", "/api/whatsapp/messages"),
        ("post", "/api/whatsapp/send/batch"),
        ("post", "/api/whatsapp/templates"),
        ("put", "/api/whatsapp/configuration/business-profile"),
    ])
    def test_anonymous_401_existing_auth(self, anon_client, method, path):
        response = getattr(anon_client, method)(path, json={})
        assert response.status_code == 401


class TestHealthAndService:
    def test_health_ok(self, client, svc):
        _, manager = svc
        manager.config = {"business_profile": {}}
        response = client.get("/api/whatsapp/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_health_not_configured_503(self, client, svc):
        _, manager = svc
        manager.config = {}
        response = client.get("/api/whatsapp/health")
        assert response.status_code == 503

    def test_service_health_200(self, client, svc):
        response = client.get("/api/whatsapp/service/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_service_metrics_200(self, client, svc):
        response = client.get("/api/whatsapp/service/metrics")
        assert response.status_code == 200
        assert response.json()["messages_sent"] == 10

    def test_initialize_authed_200(self, client, svc):
        response = client.post("/api/whatsapp/service/initialize")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_initialize_error_500(self, client, svc):
        _, manager = svc
        manager.initialize_service.side_effect = RuntimeError("boom")
        response = client.post("/api/whatsapp/service/initialize")
        assert response.status_code == 500


class TestMessages:
    def test_send_success(self, client, svc):
        response = client.post("/api/whatsapp/send", json={
            "to": "+15550001", "type": "text",
            "content": {"text": "hello"}})
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_messages_alias_text(self, client, svc):
        response = client.post("/api/whatsapp/messages",
                               json={"to": "+15550001", "message": "hi"})
        assert response.status_code == 200

    def test_messages_alias_other_type(self, client, svc):
        integration, _ = svc
        response = client.post("/api/whatsapp/messages", json={
            "to": "+15550001", "message": "hi", "type": "media"})
        assert response.status_code == 200
        assert integration.send_message.call_args[1]["content"] == {
            "body": "hi"}

    def test_send_batch_mixed(self, client, svc):
        integration, _ = svc
        integration.send_message.side_effect = [
            {"success": True, "message_id": "m1"},
            {"success": False, "error": "rate limited"},
        ]
        response = client.post("/api/whatsapp/send/batch", json={
            "recipients": ["+15550001", "+15550002"],
            "message": {"text": "hi"}, "type": "text",
            "delay_between_messages": 0})
        assert response.status_code == 200
        body = response.json()
        assert body["success_count"] == 1
        assert body["failure_count"] == 1
        assert body["success_rate"] == 50.0

    def test_send_batch_recipient_exception(self, client, svc):
        integration, _ = svc
        integration.send_message.side_effect = RuntimeError("boom")
        response = client.post("/api/whatsapp/send/batch", json={
            "recipients": ["+15550001"],
            "message": {"text": "hi"}, "type": "text",
            "delay_between_messages": 0})
        assert response.status_code == 200
        body = response.json()
        assert body["success_count"] == 0
        assert body["failure_count"] == 1
        assert body["results"][0]["success"] is False

    def test_send_batch_outer_except_500(self, client, svc):
        """Wave-93 gap: outer try in send_batch (non-recipient failure -> 500)."""
        from datetime import datetime as _dt

        class _BrokenClock(_dt):
            @classmethod
            def now(cls, *a, **k):
                raise RuntimeError("clock broken")

        integration, _ = svc
        integration.send_message.return_value = {"success": True}
        with patch.object(wa, "datetime", _BrokenClock):
            response = client.post("/api/whatsapp/send/batch", json={
                "recipients": ["+15550001"],
                "message": {"text": "hi"}, "type": "text",
                "delay_between_messages": 0})
        assert response.status_code == 500

    def test_send_batch_empty_recipients_ok(self, client, svc):
        response = client.post("/api/whatsapp/send/batch", json={
            "recipients": [], "message": {"text": "hi"}, "type": "text"})
        assert response.status_code == 200
        assert response.json()["success_rate"] == 0.0


class TestReadEndpoints:
    def test_conversations_pagination(self, client, svc):
        integration, _ = svc
        integration.get_conversations.return_value = [
            {"whatsapp_id": f"w{i}"} for i in range(2)]
        response = client.get("/api/whatsapp/conversations?limit=2")
        assert response.status_code == 200
        assert response.json()["total"] == 2
        assert response.json()["pagination"]["has_more"] is True

    def test_search_conversations_no_filters_400(self, client, svc):
        response = client.get("/api/whatsapp/conversations/search")
        assert response.status_code == 400

    def test_search_conversations_text_filter(self, client, svc):
        integration, _ = svc
        integration.get_conversations.return_value = [
            {"whatsapp_id": "w1", "name": "Alice", "phone_number": "+1555",
             "status": "open", "last_message_at": "2026-08-01T10:00:00"},
            {"whatsapp_id": "w2", "name": "Bob", "phone_number": "+1999",
             "status": "closed", "last_message_at": "2026-08-02T10:00:00"},
        ]
        response = client.get(
            "/api/whatsapp/conversations/search?query=alice&status=open")
        assert response.status_code == 200
        assert len(response.json()["conversations"]) == 1

    def test_search_conversations_date_filter_bad_date_skipped(
            self, client, svc):
        integration, _ = svc
        integration.get_conversations.return_value = [
            {"whatsapp_id": "w1", "name": "A", "phone_number": "+1",
             "status": "open", "last_message_at": "not-a-date"},
        ]
        response = client.get(
            "/api/whatsapp/conversations/search?date_from=2026-08-01")
        assert response.status_code == 200
        assert response.json()["conversations"] == []

    def test_get_messages_contact(self, client, svc):
        response = client.get("/api/whatsapp/messages/w1?limit=5")
        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_get_all_messages(self, client, svc):
        integration, _ = svc
        integration.get_conversations.return_value = [
            {"whatsapp_id": "w1", "phone_number": "+1555",
             "last_message": "hi", "last_message_at": "2026-08-01T10:00:00"},
            {"whatsapp_id": "w2", "phone_number": "+1999",
             "last_message": None, "last_message_at": None},
        ]
        response = client.get("/api/whatsapp/messages?limit=10")
        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["messages"][0]["id"] == "msg_w1"

    def test_create_template(self, client, svc):
        response = client.post("/api/whatsapp/templates", json={
            "template_name": "welcome", "category": "UTILITY",
            "language_code": "en", "components": [{"type": "BODY"}]})
        assert response.status_code == 200
        assert response.json()["template_id"] == "tpl-1"

    def test_analytics_default_range(self, client, svc):
        response = client.get("/api/whatsapp/analytics")
        assert response.status_code == 200
        assert "period" in response.json()

    def test_analytics_with_dates(self, client, svc):
        response = client.get(
            "/api/whatsapp/analytics?start_date=2026-08-01"
            "&end_date=2026-08-10")
        assert response.status_code == 200
        period = response.json()["period"]
        assert period["start_date"].startswith("2026-08-01")

    def test_export_json(self, client, svc):
        response = client.get(
            "/api/whatsapp/analytics/export?format=json")
        assert response.status_code == 200
        assert response.json()["format"] == "json"

    def test_export_csv(self, client, svc):
        integration, _ = svc
        integration.get_analytics.return_value = {
            "message_statistics": [
                {"message_type": "text", "direction": "outbound",
                 "status": "sent", "count": 3}]}
        response = client.get(
            "/api/whatsapp/analytics/export?format=csv")
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        assert "Type,Direction,Status,Count" in response.text
        assert "outbound" in response.text
        assert "3" in response.text

    def test_export_bad_format_422(self, client, svc):
        response = client.get(
            "/api/whatsapp/analytics/export?format=xml")
        assert response.status_code == 422

    def test_business_profile_get(self, client, svc):
        response = client.get("/api/whatsapp/configuration/business-profile")
        assert response.status_code == 200
        assert response.json()["business_profile"]["name"] == "ACME"

    def test_business_profile_update_missing_fields_400(self, client, svc):
        response = client.put(
            "/api/whatsapp/configuration/business-profile",
            json={"business_profile": {"name": "X"}})
        assert response.status_code == 400

    def test_business_profile_update_success(self, client, svc):
        response = client.put(
            "/api/whatsapp/configuration/business-profile",
            json={"business_profile": {"name": "ACME 2",
                                       "description": "d",
                                       "email": "a@b.c"}})
        assert response.status_code == 200
        assert response.json()["updated_fields"] == ["name",
                                                     "description", "email"]


class TestErrorPaths:
    def test_health_unavailable_503(self, client, svc):
        with patch.object(wa, "WHATSAPP_AVAILABLE", False):
            response = client.get("/api/whatsapp/health")
        assert response.status_code == 503

    def test_send_error_500(self, client, svc):
        integration, _ = svc
        integration.send_message.side_effect = RuntimeError("boom")
        response = client.post("/api/whatsapp/send", json={
            "to": "+15550001", "type": "text", "content": {"text": "hi"}})
        assert response.status_code == 500

    def test_conversations_error_500(self, client, svc):
        integration, _ = svc
        integration.get_conversations.side_effect = RuntimeError("boom")
        response = client.get("/api/whatsapp/conversations")
        assert response.status_code == 500

    def test_templates_error_500(self, client, svc):
        integration, _ = svc
        integration.create_template.side_effect = RuntimeError("boom")
        response = client.post("/api/whatsapp/templates", json={
            "template_name": "w", "category": "UTILITY",
            "language_code": "en", "components": []})
        assert response.status_code == 500

    def test_export_error_500(self, client, svc):
        integration, _ = svc
        integration.get_analytics.side_effect = RuntimeError("boom")
        response = client.get("/api/whatsapp/analytics/export?format=json")
        assert response.status_code == 500


class TestHelpers:
    def test_register_whatsapp_routes_true(self):
        app = FastAPI()
        assert wa.register_whatsapp_routes(app) is True

    def test_register_whatsapp_routes_false(self):
        app = FastAPI()
        with patch.object(wa, "WHATSAPP_AVAILABLE", False):
            assert wa.register_whatsapp_routes(app) is False

    def test_initialize_whatsapp_service_true(self):
        manager = MagicMock()
        manager.initialize_service.return_value = {"success": True}
        with patch.object(wa, "whatsapp_service_manager", manager):
            assert wa.initialize_whatsapp_service() is True

    def test_initialize_whatsapp_service_false(self):
        manager = MagicMock()
        manager.initialize_service.return_value = {"success": False}
        with patch.object(wa, "whatsapp_service_manager", manager):
            assert wa.initialize_whatsapp_service() is False

    def test_initialize_whatsapp_service_error_false(self):
        manager = MagicMock()
        manager.initialize_service.side_effect = RuntimeError("boom")
        with patch.object(wa, "whatsapp_service_manager", manager):
            assert wa.initialize_whatsapp_service() is False

    def test_initialize_whatsapp_service_unavailable_false(self):
        with patch.object(wa, "WHATSAPP_AVAILABLE", False):
            assert wa.initialize_whatsapp_service() is False
