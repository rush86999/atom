"""Coverage wave W64 — integrations/whatsapp_fastapi_routes.py (TDD, 0% baseline).

Router prefix /api/whatsapp. WHATSAPP_AVAILABLE=True in this env (optional deps
installed); the ImportError-fallback block is exercised via a sys.modules=None
reload test; 503/500 branch variants are exercised by patching the module flag.

Endpoints: health, service/{health,metrics,initialize}, send, messages,
send/batch, conversations, conversations/search, messages/{id}, messages,
templates, analytics, analytics/export, configuration/business-profile
(GET/PUT), webhook (GET verify + POST handler), plus register_whatsapp_routes
(websocket/status + websocket/notify) and initialize_whatsapp_service.

Bug found + fixed in module (regression test below):
- send_batch_messages with an EMPTY recipients list divided by zero
  (success_rate = success_count / len(recipients)) -> ZeroDivisionError -> 500
  on an otherwise valid request. Now guards the division — empty batch returns
  200 with success_rate 0.0 — test_send_batch_empty_recipients.
"""
import importlib
import sys
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from integrations import whatsapp_fastapi_routes as wa
from core.models import User

MSGS = ["+15550001", "+15550002"]


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = f"wa-{uuid.uuid4().hex[:8]}"
    u.email = "wa@x.com"
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
def svc():
    """Patched whatsapp_integration + whatsapp_service_manager module globals."""
    integration = MagicMock()
    integration.send_message.return_value = {"success": True, "message_id": "wamid-1"}
    integration.get_conversations.return_value = [
        {"whatsapp_id": "w1", "name": "Alice", "phone_number": "+15550001",
         "status": "open", "last_message": "hi", "last_message_at": "2026-08-01T10:00:00"}]
    integration.get_messages.return_value = [{"id": "m1", "text": "hi"}]
    integration.create_template.return_value = {"success": True, "template_id": "tpl-1"}
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


def _c(client, method, path, **kw):
    return getattr(client, method)(path, **kw)


class TestHealth:
    def test_health_ok(self, client, svc):
        _, manager = svc
        manager.config = {"business_profile": {}}
        response = _c(client, "get", "/api/whatsapp/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_health_not_configured_503(self, client, svc):
        _, manager = svc
        manager.config = {}
        response = _c(client, "get", "/api/whatsapp/health")
        assert response.status_code == 503

    def test_health_config_access_error_500(self, client, svc):
        class Boom:
            @property
            def config(self):
                raise RuntimeError("boom")

        with patch.object(wa, "whatsapp_service_manager", Boom()):
            response = _c(client, "get", "/api/whatsapp/health")
        assert response.status_code == 500

    def test_health_unavailable_503(self, client, svc):
        with patch.object(wa, "WHATSAPP_AVAILABLE", False):
            response = _c(client, "get", "/api/whatsapp/health")
        assert response.status_code == 503
        assert "missing optional dependency" in response.json()["detail"]


class TestServiceEndpoints:
    def test_service_health_healthy_200(self, client, svc):
        response = _c(client, "get", "/api/whatsapp/service/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_service_health_degraded_503(self, client, svc):
        _, manager = svc
        manager.health_check.return_value = {"status": "degraded"}
        response = _c(client, "get", "/api/whatsapp/service/health")
        assert response.status_code == 503

    def test_service_health_error_500(self, client, svc):
        _, manager = svc
        manager.health_check.side_effect = RuntimeError("boom")
        response = _c(client, "get", "/api/whatsapp/service/health")
        assert response.status_code == 500

    def test_service_health_unavailable_503(self, client, svc):
        _, manager = svc
        manager.health_check.side_effect = RuntimeError("boom")
        with patch.object(wa, "WHATSAPP_AVAILABLE", False):
            response = _c(client, "get", "/api/whatsapp/service/health")
        assert response.status_code == 503

    def test_service_metrics_200(self, client, svc):
        response = _c(client, "get", "/api/whatsapp/service/metrics")
        assert response.status_code == 200
        assert response.json()["messages_sent"] == 10

    def test_service_metrics_error_500(self, client, svc):
        _, manager = svc
        manager.get_service_metrics.side_effect = RuntimeError("boom")
        response = _c(client, "get", "/api/whatsapp/service/metrics")
        assert response.status_code == 500

    def test_initialize_service_200(self, client, svc):
        response = _c(client, "post", "/api/whatsapp/service/initialize")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_initialize_service_error_500(self, client, svc):
        _, manager = svc
        manager.initialize_service.side_effect = RuntimeError("boom")
        response = _c(client, "post", "/api/whatsapp/service/initialize")
        assert response.status_code == 500


class TestSendMessage:
    def test_send_success(self, client, svc):
        integration, _ = svc
        response = _c(client, "post", "/api/whatsapp/send", json={
            "to": "+15550001", "type": "text", "content": {"text": "Hello"}})
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert integration.send_message.call_args.kwargs["to"] == "+15550001"
        assert integration.send_message.call_args.kwargs["message_type"] == "text"

    def test_send_error_500(self, client, svc):
        integration, _ = svc
        integration.send_message.side_effect = RuntimeError("boom")
        response = _c(client, "post", "/api/whatsapp/send", json={
            "to": "+15550001", "type": "text", "content": {"text": "Hello"}})
        assert response.status_code == 500

    def test_send_validation_422(self, client, svc):
        response = _c(client, "post", "/api/whatsapp/send", json={"to": "+1"})
        assert response.status_code == 422

    def test_messages_alias_text(self, client, svc):
        integration, _ = svc
        response = _c(client, "post", "/api/whatsapp/messages", json={
            "to": "+15550001", "message": "Hello", "type": "text"})
        assert response.status_code == 200
        assert integration.send_message.call_args.kwargs["content"] == {"text": "Hello"}

    def test_messages_alias_non_text(self, client, svc):
        integration, _ = svc
        _c(client, "post", "/api/whatsapp/messages", json={
            "to": "+15550001", "message": "Hello", "type": "template"})
        assert integration.send_message.call_args.kwargs["content"] == {"body": "Hello"}

    def test_messages_alias_error_500(self, client, svc):
        integration, _ = svc
        integration.send_message.side_effect = RuntimeError("boom")
        response = _c(client, "post", "/api/whatsapp/messages", json={
            "to": "+15550001", "message": "Hello"})
        assert response.status_code == 500


class TestSendBatch:
    def test_send_batch_mixed_results(self, client, svc):
        integration, _ = svc
        integration.send_message.side_effect = [
            {"success": True, "message_id": "m1"},
            {"success": False, "message_id": None, "error": "template not approved"},
        ]
        response = _c(client, "post", "/api/whatsapp/send/batch", json={
            "recipients": MSGS, "message": {"text": "Hi"}, "type": "text",
            "delay_between_messages": 0})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["success_count"] == 1
        assert body["failure_count"] == 1
        assert body["success_rate"] == 50.0
        assert len(body["results"]) == 2

    def test_send_batch_all_fail(self, client, svc):
        integration, _ = svc
        integration.send_message.return_value = {"success": False, "error": "no"}
        response = _c(client, "post", "/api/whatsapp/send/batch", json={
            "recipients": MSGS, "message": {"text": "Hi"}})
        assert response.json()["success"] is False
        assert response.json()["failure_count"] == 2

    def test_send_batch_per_recipient_exception(self, client, svc):
        integration, _ = svc
        integration.send_message.side_effect = [
            {"success": True, "message_id": "m1"},
            RuntimeError("line busy"),
        ]
        response = _c(client, "post", "/api/whatsapp/send/batch", json={
            "recipients": MSGS, "message": {"text": "Hi"}})
        body = response.json()
        assert body["success"] is True
        assert body["failure_count"] == 1
        assert body["results"][1]["success"] is False
        assert "line busy" in body["results"][1]["error"]

    def test_send_batch_with_delay_sleeps(self, client, svc):
        integration, _ = svc
        with patch("time.sleep") as sleep:
            response = _c(client, "post", "/api/whatsapp/send/batch", json={
                "recipients": MSGS, "message": {"text": "Hi"},
                "delay_between_messages": 2})
        assert response.status_code == 200
        assert sleep.call_count == 1
        sleep.assert_called_once_with(2)

    # Regression: empty recipients previously -> ZeroDivisionError -> 500.
    def test_send_batch_empty_recipients(self, client, svc):
        response = _c(client, "post", "/api/whatsapp/send/batch", json={
            "recipients": [], "message": {"text": "Hi"}})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert body["success_rate"] == 0.0
        assert body["total_recipients"] == 0

    def test_send_batch_validation_422(self, client, svc):
        response = _c(client, "post", "/api/whatsapp/send/batch", json={
            "recipients": MSGS, "message": {"text": "Hi"}, "delay_between_messages": 999})
        assert response.status_code == 422


class TestConversations:
    def test_get_conversations_success(self, client, svc):
        integration, _ = svc
        integration.get_conversations.return_value = [{"whatsapp_id": "w1"}, {"whatsapp_id": "w2"}]
        response = _c(client, "get", "/api/whatsapp/conversations?limit=2")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert body["pagination"]["has_more"] is True

    def test_get_conversations_no_more(self, client, svc):
        integration, _ = svc
        integration.get_conversations.return_value = [{"whatsapp_id": "w1"}]
        response = _c(client, "get", "/api/whatsapp/conversations?limit=50")
        assert response.json()["pagination"]["has_more"] is False

    def test_get_conversations_error_500(self, client, svc):
        integration, _ = svc
        integration.get_conversations.side_effect = RuntimeError("boom")
        response = _c(client, "get", "/api/whatsapp/conversations")
        assert response.status_code == 500

    def test_search_no_filters_400(self, client, svc):
        response = _c(client, "get", "/api/whatsapp/conversations/search")
        assert response.status_code == 400

    def test_search_query_match_and_skip(self, client, svc):
        integration, _ = svc
        integration.get_conversations.return_value = [
            {"name": "Alice", "phone_number": "+15550001"},
            {"name": "Bob", "phone_number": "+15550002"},
        ]
        response = _c(client, "get", "/api/whatsapp/conversations/search?query=ali")
        assert response.status_code == 200
        assert len(response.json()["conversations"]) == 1
        assert response.json()["conversations"][0]["name"] == "Alice"

    def test_search_phone_match(self, client, svc):
        integration, _ = svc
        integration.get_conversations.return_value = [
            {"name": "Alice", "phone_number": "+15550001"},
        ]
        response = _c(client, "get", "/api/whatsapp/conversations/search?query=550001")
        assert len(response.json()["conversations"]) == 1

    def test_search_status_filter(self, client, svc):
        integration, _ = svc
        integration.get_conversations.return_value = [
            {"status": "open"}, {"status": "closed"}]
        response = _c(client, "get", "/api/whatsapp/conversations/search?status=closed")
        assert len(response.json()["conversations"]) == 1

    def test_search_date_range(self, client, svc):
        integration, _ = svc
        integration.get_conversations.return_value = [
            {"last_message_at": "2026-07-01T10:00:00"},  # before date_from -> skip
            {"last_message_at": "2026-08-01T10:00:00"},  # within range -> keep
            {"last_message_at": "2026-09-15T10:00:00"},  # after date_to -> skip
        ]
        response = _c(client, "get",
                      "/api/whatsapp/conversations/search?date_from=2026-08-01&date_to=2026-08-31")
        assert response.status_code == 200
        assert len(response.json()["conversations"]) == 1

    def test_search_date_invalid_value_skips(self, client, svc):
        integration, _ = svc
        integration.get_conversations.return_value = [
            {"last_message_at": "2026-08-01T10:00:00Z"},
            {"last_message_at": ""},
        ]
        response = _c(client, "get",
                      "/api/whatsapp/conversations/search?date_from=notadate")
        assert response.status_code == 200
        assert response.json()["conversations"] == []

    def test_search_pagination_has_more(self, client, svc):
        integration, _ = svc
        integration.get_conversations.return_value = [
            {"name": f"c{i}"} for i in range(5)]
        response = _c(client, "get", "/api/whatsapp/conversations/search?query=c&limit=2")
        body = response.json()
        assert len(body["conversations"]) == 2
        assert body["pagination"]["has_more"] is True

    def test_search_pagination_no_more(self, client, svc):
        integration, _ = svc
        integration.get_conversations.return_value = [{"name": "c1"}]
        response = _c(client, "get", "/api/whatsapp/conversations/search?query=c&offset=5")
        body = response.json()
        assert body["conversations"] == []
        assert body["pagination"]["has_more"] is False

    def test_search_error_500(self, client, svc):
        integration, _ = svc
        integration.get_conversations.side_effect = RuntimeError("boom")
        response = _c(client, "get", "/api/whatsapp/conversations/search?query=x")
        assert response.status_code == 500


class TestMessages:
    def test_get_messages_for_contact(self, client, svc):
        integration, _ = svc
        integration.get_messages.return_value = [{"id": "m1"}, {"id": "m2"}]
        response = _c(client, "get", "/api/whatsapp/messages/w1")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert body["whatsapp_id"] == "w1"

    def test_get_messages_for_contact_error_500(self, client, svc):
        integration, _ = svc
        integration.get_messages.side_effect = RuntimeError("boom")
        response = _c(client, "get", "/api/whatsapp/messages/w1")
        assert response.status_code == 500

    def test_get_all_messages(self, client, svc):
        integration, _ = svc
        integration.get_conversations.return_value = [
            {"last_message": "hi", "whatsapp_id": "w1", "phone_number": "+1",
             "last_message_at": "t1"},
            {"whatsapp_id": "w2", "last_message": None},
        ]
        response = _c(client, "get", "/api/whatsapp/messages")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["messages"][0]["id"] == "msg_w1"

    def test_get_all_messages_limit_slice(self, client, svc):
        integration, _ = svc
        integration.get_conversations.return_value = [
            {"last_message": "a", "whatsapp_id": "w1"},
            {"last_message": "b", "whatsapp_id": "w2"},
        ]
        response = _c(client, "get", "/api/whatsapp/messages?limit=1")
        assert len(response.json()["messages"]) == 1

    def test_get_all_messages_error_500(self, client, svc):
        integration, _ = svc
        integration.get_conversations.side_effect = RuntimeError("boom")
        response = _c(client, "get", "/api/whatsapp/messages")
        assert response.status_code == 500


class TestTemplates:
    def test_create_template_success(self, client, svc):
        integration, _ = svc
        response = _c(client, "post", "/api/whatsapp/templates", json={
            "template_name": "welcome", "category": "UTILITY",
            "language_code": "en", "components": [{"type": "BODY", "text": "Hi"}]})
        assert response.status_code == 200
        assert integration.create_template.call_args.kwargs["template_name"] == "welcome"
        assert integration.create_template.call_args.kwargs["components"] == [
            {"type": "BODY", "text": "Hi"}]

    def test_create_template_error_500(self, client, svc):
        integration, _ = svc
        integration.create_template.side_effect = RuntimeError("boom")
        response = _c(client, "post", "/api/whatsapp/templates", json={
            "template_name": "welcome", "category": "UTILITY",
            "language_code": "en", "components": []})
        assert response.status_code == 500

    def test_create_template_validation_422(self, client, svc):
        response = _c(client, "post", "/api/whatsapp/templates", json={})
        assert response.status_code == 422


class TestAnalytics:
    def test_get_analytics_with_dates(self, client, svc):
        integration, _ = svc
        response = _c(client, "get",
                      "/api/whatsapp/analytics?start_date=2026-07-01&end_date=2026-07-31")
        assert response.status_code == 200
        body = response.json()
        assert body["period"]["start_date"].startswith("2026-07-01")
        assert body["period"]["end_date"].startswith("2026-07-31")
        assert integration.get_analytics.called

    def test_get_analytics_default_window(self, client, svc):
        integration, _ = svc
        response = _c(client, "get", "/api/whatsapp/analytics")
        assert response.status_code == 200
        body = response.json()
        start = datetime.fromisoformat(body["period"]["start_date"])
        assert datetime.now() - timedelta(days=30) - start < timedelta(days=1)

    def test_get_analytics_error_500(self, client, svc):
        integration, _ = svc
        integration.get_analytics.side_effect = RuntimeError("boom")
        response = _c(client, "get", "/api/whatsapp/analytics")
        assert response.status_code == 500

    def test_export_json(self, client, svc):
        response = _c(client, "get", "/api/whatsapp/analytics/export?format=json")
        assert response.status_code == 200
        assert response.json()["format"] == "json"

    def test_export_json_with_dates(self, client, svc):
        response = _c(client, "get", "/api/whatsapp/analytics/export?format=json"
                      "&start_date=2026-07-01&end_date=2026-07-31")
        assert response.status_code == 200
        body = response.json()
        assert body["date_range"]["start_date"] == "2026-07-01"
        assert body["date_range"]["end_date"] == "2026-07-31"

    def test_export_csv_with_stats(self, client, svc):
        integration, _ = svc
        integration.get_analytics.return_value = {"message_statistics": [
            {"message_type": "text", "direction": "outbound",
             "status": "delivered", "count": 3}]}
        response = _c(client, "get", "/api/whatsapp/analytics/export?format=csv")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "delivered" in response.text

    def test_export_csv_empty_stats(self, client, svc):
        response = _c(client, "get", "/api/whatsapp/analytics/export?format=csv")
        assert response.status_code == 200
        assert "Type,Direction,Status,Count" in response.text

    def test_export_invalid_format_422(self, client, svc):
        response = _c(client, "get", "/api/whatsapp/analytics/export?format=xml")
        assert response.status_code == 422

    def test_export_error_500(self, client, svc):
        integration, _ = svc
        integration.get_analytics.side_effect = RuntimeError("boom")
        response = _c(client, "get", "/api/whatsapp/analytics/export")
        assert response.status_code == 500


class TestBusinessProfile:
    def test_get_business_profile(self, client, svc):
        response = _c(client, "get", "/api/whatsapp/configuration/business-profile")
        assert response.status_code == 200
        assert response.json()["business_profile"] == {"name": "ACME"}

    def test_get_business_profile_error_500(self, client, svc):
        _, manager = svc
        manager.config = None
        response = _c(client, "get", "/api/whatsapp/configuration/business-profile")
        assert response.status_code == 500

    def test_update_business_profile_missing_fields_400(self, client, svc):
        response = _c(client, "put", "/api/whatsapp/configuration/business-profile", json={
            "business_profile": {"name": "ACME"}})
        assert response.status_code == 400
        assert "Missing required fields" in response.json()["detail"]

    def test_update_business_profile_success(self, client, svc):
        _, manager = svc
        response = _c(client, "put", "/api/whatsapp/configuration/business-profile", json={
            "business_profile": {"name": "ACME 2", "description": "d", "email": "a@b.c"}})
        assert response.status_code == 200
        body = response.json()
        assert body["business_profile"]["name"] == "ACME 2"
        assert body["updated_fields"] == ["name", "description", "email"]
        assert manager.config["business_profile"]["email"] == "a@b.c"

    def test_update_business_profile_error_500(self, client, svc):
        _, manager = svc
        manager.config = None
        response = _c(client, "put", "/api/whatsapp/configuration/business-profile", json={
            "business_profile": {"name": "X", "description": "d", "email": "a@b.c"}})
        assert response.status_code == 500


class TestWebhook:
    def test_verification_subscribe(self, client, monkeypatch):
        # Wave 93 (fail-closed): handshake requires the configured verify token
        monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "tok")
        response = _c(client, "get",
                      "/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=tok&hub.challenge=CH")
        assert response.status_code == 200
        assert response.json() == "CH"

    def test_verification_wrong_token_403(self, client):
        # Wave 93 (fail-closed): token mismatch is rejected even with the
        # correct subscribe mode
        response = _c(client, "get",
                      "/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=CH")
        assert response.status_code == 403

    def test_verification_rejected(self, client):
        response = _c(client, "get",
                      "/api/whatsapp/webhook?hub.mode=unsubscribe&hub.verify_token=tok&hub.challenge=CH")
        assert response.status_code == 403

    def test_webhook_handler_success(self, client, monkeypatch):
        # Wave 93 (fail-closed): a valid X-Hub-Signature-256 is required
        monkeypatch.setenv("WHATSAPP_APP_SECRET", "0123456789abcdef0123456789abcdef")
        from integrations import universal_webhook_bridge
        import hmac
        import hashlib
        body = ('{"entry": [{"id": "p1"}]}').encode()
        digest = hmac.new(
            "0123456789abcdef0123456789abcdef".encode(), body,
            hashlib.sha256).digest()
        with patch.object(universal_webhook_bridge.universal_webhook_bridge,
                          "process_incoming_message", new=AsyncMock(return_value=True)):
            response = _c(client, "post", "/api/whatsapp/webhook",
                          content=body,
                          headers={"X-Hub-Signature-256": "sha256=" + digest.hex()})
        assert response.status_code == 200
        assert response.json() == {"status": "received"}

    def test_webhook_handler_error_500(self, client, monkeypatch):
        # Wave 93 (fail-closed): signature required before the handler body
        monkeypatch.setenv("WHATSAPP_APP_SECRET", "0123456789abcdef0123456789abcdef")
        saved = sys.modules.get("integrations.universal_webhook_bridge")
        sys.modules["integrations.universal_webhook_bridge"] = None
        try:
            import hmac
            import hashlib
            body = b'{"entry": []}'
            digest = hmac.new(
                "0123456789abcdef0123456789abcdef".encode(), body,
                hashlib.sha256).digest()
            response = _c(client, "post", "/api/whatsapp/webhook",
                          content=body,
                          headers={"X-Hub-Signature-256": "sha256=" + digest.hex()})
        finally:
            if saved is not None:
                sys.modules["integrations.universal_webhook_bridge"] = saved
        assert response.status_code == 500


class TestRegisterRoutes:
    def test_register_available(self):
        app = FastAPI()
        assert wa.register_whatsapp_routes(app) is True

        def _health():
            return {}

        c = TestClient(app)
        response = c.get("/api/whatsapp/websocket/status")
        assert response.status_code == 200
        assert response.json()["status"] == "available"

        response = c.post("/api/whatsapp/websocket/notify", json={"type": "test"})
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "test" in response.json()["message"]

    def test_register_unavailable(self):
        app = FastAPI()
        with patch.object(wa, "WHATSAPP_AVAILABLE", False):
            assert wa.register_whatsapp_routes(app) is False
        c = TestClient(app)
        assert c.get("/api/whatsapp/websocket/status").status_code == 404


class TestInitializeService:
    def test_initialize_success_true(self):
        manager = MagicMock()
        manager.initialize_service.return_value = {"success": True}
        with patch.object(wa, "whatsapp_service_manager", manager):
            assert wa.initialize_whatsapp_service() is True

    def test_initialize_result_false(self):
        manager = MagicMock()
        manager.initialize_service.return_value = {"success": False}
        with patch.object(wa, "whatsapp_service_manager", manager):
            assert wa.initialize_whatsapp_service() is False

    def test_initialize_exception_false(self):
        manager = MagicMock()
        manager.initialize_service.side_effect = RuntimeError("boom")
        with patch.object(wa, "whatsapp_service_manager", manager):
            assert wa.initialize_whatsapp_service() is False

    def test_initialize_unavailable_false(self):
        with patch.object(wa, "WHATSAPP_AVAILABLE", False):
            assert wa.initialize_whatsapp_service() is False


class TestImportFallbackBlock:
    """Exercise the optional-dependency ImportError guard (lines 22-30)."""

    def test_import_guard_when_deps_missing(self):
        names = [
            "integrations.universal_webhook_bridge",
            "integrations.whatsapp_business_integration",
            "integrations.whatsapp_service_manager",
        ]
        saved = {n: sys.modules.get(n) for n in names}
        for n in names:
            sys.modules[n] = None  # makes `from X import Y` raise ImportError
        try:
            reloaded = importlib.reload(wa)
            assert reloaded.WHATSAPP_AVAILABLE is False
            assert reloaded.whatsapp_integration is None
            assert reloaded.whatsapp_service_manager is None
            assert reloaded.universal_webhook_bridge is None
        finally:
            for n in names:
                if saved[n] is not None:
                    sys.modules[n] = saved[n]
                else:
                    sys.modules.pop(n, None)
            importlib.reload(wa)
            assert wa.WHATSAPP_AVAILABLE is True
