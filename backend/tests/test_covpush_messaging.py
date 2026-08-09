"""
Coverage-push + bug-hunt tests for the WhatsApp, Discord, and HubSpot
integration modules.

TDD targets (RED first):
1. whatsapp webhook POST is fail-open: no HMAC verification, forged events
   are stored + bridged even when no app secret is configured (R45 class).
2. whatsapp webhook GET verification is fail-open when webhook_verify_token
   is unset (None == None passes the subscribe handshake).
3. whatsapp route/service handlers leak str(e) to clients.
4. discord unified_search discards its search results (always returns []).
5. discord communication_channels accumulates duplicates across calls.
"""

import asyncio
import base64
import contextlib
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import integrations.atom_discord_integration as discord_mod
import integrations.hubspot_routes as hubspot_mod
import integrations.whatsapp_business_integration as whatsapp_mod

# --------------------------------------------------------------------------
# Shared fakes
# --------------------------------------------------------------------------


class FakeCursor:
    def __init__(self):
        self.executed = []
        self.rows = []
        self.one = [1]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        self.executed.append(query)

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.one


class FakeDb:
    def __init__(self, rows=None, one=None):
        self.cursor_obj = FakeCursor()
        if rows is not None:
            self.cursor_obj.rows = rows
        if one is not None:
            self.cursor_obj.one = one
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data
        self.text = text

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=httpx.Request("GET", "http://x"), response=httpx.Response(self.status_code)
            )


class FakeFlaskRequest:
    def __init__(self, json_body=None, args=None, headers=None, raw=b"", method="GET"):
        self._json = json_body
        self.args = args or {}
        self.headers = headers or {}
        self._raw = raw
        self.method = method

    def get_json(self):
        return self._json

    def get_data(self):
        return self._raw


def _hub_sig(secret: str, raw: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


# --------------------------------------------------------------------------
# WhatsApp Business Integration
# --------------------------------------------------------------------------


class TestWhatsAppService:
    def _svc(self, config=None):
        svc = whatsapp_mod.WhatsAppBusinessIntegration(config=config or {})
        return svc

    def test_initialize_demo_mode_db_failure(self):
        svc = self._svc()
        with patch.object(whatsapp_mod.psycopg2, "connect", side_effect=RuntimeError("no db")):
            assert svc.initialize({"is_demo": True}) is True
        assert svc.db_connection is None

    def test_initialize_non_demo_db_failure(self):
        svc = self._svc()
        with patch.object(whatsapp_mod.psycopg2, "connect", side_effect=RuntimeError("no db")):
            assert svc.initialize({"is_demo": False}) is False

    def test_initialize_success(self):
        svc = self._svc()
        db = FakeDb()
        with patch.object(whatsapp_mod.psycopg2, "connect", return_value=db):
            assert svc.initialize({"access_token": "tok", "phone_number_id": "pn"}) is True
        assert svc.access_token == "tok"
        assert svc.webhook_verify_token is None
        assert len(db.cursor_obj.executed) == 4
        assert db.commits == 1

    def test_initialize_sets_webhook_secrets(self):
        svc = self._svc()
        with patch.object(whatsapp_mod.psycopg2, "connect", side_effect=RuntimeError("no db")):
            svc.initialize({"is_demo": True, "webhook_verify_token": "vt", "webhook_app_secret": "as"})
        assert svc.webhook_verify_token == "vt"
        assert svc.webhook_app_secret == "as"

    def test_initialize_exception(self):
        svc = self._svc()
        with patch.object(whatsapp_mod.psycopg2, "connect", side_effect=RuntimeError("no db")):
            config = MagicMock()
            config.get.side_effect = RuntimeError("boom")
            assert svc.initialize(config) is False

    def test_get_capabilities(self):
        caps = self._svc().get_capabilities()
        assert {o["id"] for o in caps["operations"]} == {
            "send_message", "get_conversations", "get_messages",
            "create_template", "get_analytics",
        }
        assert caps["supports_webhooks"] is True

    def test_health_check(self):
        svc = self._svc({"access_token": "t"})
        assert svc.health_check()["healthy"] is True
        svc2 = self._svc({})
        assert svc2.health_check()["healthy"] is False

    def test_execute_operation_send_message(self):
        svc = self._svc({"access_token": "t", "phone_number_id": "pn"})
        db = FakeDb()
        svc.db_connection = db
        with patch.object(whatsapp_mod.requests, "post", return_value=FakeResponse(200, {"messages": [{"id": "w1"}]})) as post:
            result = asyncio.run(svc.execute_operation("send_message", {"to": "123", "type": "text", "content": {"body": "hi"}}, {"user_id": "u1"}))
        assert result["success"] is True
        payload = post.call_args.kwargs["json"]
        assert payload["to"] == "123" and payload["type"] == "text"

    def test_execute_operation_unsupported(self):
        svc = self._svc()
        with pytest.raises(NotImplementedError):
            asyncio.run(svc.execute_operation("nope", {}, {}))

    def test_get_credentials_from_config(self):
        svc = self._svc({"access_token": "t", "phone_number_id": "p"})
        creds = asyncio.run(svc._get_credentials("u1"))
        assert creds == {"access_token": "t", "phone_number_id": "p"}

    def test_get_credentials_no_user_id(self):
        svc = self._svc({})
        with pytest.raises(whatsapp_mod.AuthenticationError):
            asyncio.run(svc._get_credentials())

    def test_get_credentials_no_connections(self):
        svc = self._svc({})
        with patch.object(whatsapp_mod.connection_service, "get_connections", return_value=[]):
            with pytest.raises(whatsapp_mod.AuthenticationError):
                asyncio.run(svc._get_credentials("u1"))

    def test_get_credentials_missing_token(self):
        svc = self._svc({})
        with patch.object(whatsapp_mod.connection_service, "get_connections", return_value=[{"id": "c1"}]):
            with patch.object(whatsapp_mod.connection_service, "get_connection_credentials", new=AsyncMock(return_value=None)):
                with pytest.raises(whatsapp_mod.AuthenticationError):
                    asyncio.run(svc._get_credentials("u1"))

    def _send(self, svc, *args, **kwargs):
        return asyncio.run(svc.send_message(*args, **kwargs))

    def test_send_message_text_success(self):
        svc = self._svc({"access_token": "t", "phone_number_id": "pn"})
        db = FakeDb()
        svc.db_connection = db
        with patch.object(whatsapp_mod.requests, "post", return_value=FakeResponse(200, {"messages": [{"id": "w1"}]})) as post:
            result = self._send(svc, "123", "text", {"body": "hello"})
        assert result == {"success": True, "message_id": "w1", "status": "sent"}
        assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer t"
        assert db.commits >= 1

    def test_send_message_uses_connection_phone_id(self):
        svc = self._svc({"access_token": "t"})
        db = FakeDb()
        svc.db_connection = db
        creds = {"access_token": "ct", "phone_number_id": "pn2"}
        with patch.object(whatsapp_mod.connection_service, "get_connections", return_value=[{"id": "c1"}]):
            with patch.object(whatsapp_mod.connection_service, "get_connection_credentials", new=AsyncMock(return_value=creds)):
                with patch.object(whatsapp_mod.requests, "post", return_value=FakeResponse(200, {"messages": [{"id": "w2"}]})) as post:
                    result = self._send(svc, "123", "text", {"body": "hello"}, user_id="u1")
        assert result["success"] is True
        assert post.call_args.args[0] == f"{svc.base_url}/pn2/messages"

    def test_send_message_missing_phone_number_id(self):
        svc = self._svc({"access_token": "t"})
        svc.db_connection = None
        with patch.object(whatsapp_mod.connection_service, "get_connections", return_value=[]):
            result = self._send(svc, "123", "text", {"body": "x"}, user_id=None)
        assert result["success"] is False
        assert "exception" not in str(result["error"]).lower()

    def test_send_message_template_and_media_and_interactive(self):
        svc = self._svc({"access_token": "t", "phone_number_id": "pn"})
        db = FakeDb()
        svc.db_connection = db
        for mtype, content, expected in [
            ("template", {"name": "tpl", "language": {"code": "en"}}, "template"),
            ("media", {"media_type": "image", "id": "mid"}, "image"),
            ("interactive", {"type": "button"}, "interactive"),
        ]:
            with patch.object(whatsapp_mod.requests, "post", return_value=FakeResponse(200, {"messages": [{"id": "w"}]})) as post:
                result = self._send(svc, "123", mtype, content)
            assert result["success"] is True, mtype
            assert post.call_args.kwargs["json"]["type"] == expected

    def test_send_message_unsupported_type(self):
        svc = self._svc({"access_token": "t", "phone_number_id": "pn"})
        svc.db_connection = None
        result = self._send(svc, "123", "carrier_pigeon", {})
        assert result["success"] is False

    def test_send_message_api_error(self):
        svc = self._svc({"access_token": "t", "phone_number_id": "pn"})
        svc.db_connection = None
        with patch.object(whatsapp_mod.requests, "post", return_value=FakeResponse(500, {"error": {"message": "rate limited"}})):
            result = self._send(svc, "123", "text", {"body": "x"})
        assert result["success"] is False
        assert result["error"] == {"error": {"message": "rate limited"}}

    def test_send_message_exception_does_not_leak_detail(self):
        svc = self._svc({"access_token": "t", "phone_number_id": "pn"})
        svc.db_connection = None
        with patch.object(whatsapp_mod.requests, "post", side_effect=RuntimeError("secret-detail-xyz")):
            result = self._send(svc, "123", "text", {"body": "x"})
        assert result["success"] is False
        assert "secret-detail-xyz" not in str(result["error"])

    def test_get_conversations_success(self):
        svc = self._svc()
        svc.db_connection = FakeDb(rows=[{"id": 1, "name": "A"}, {"id": 2, "name": "B"}])
        convs = svc.get_conversations(limit=5, offset=10)
        assert len(convs) == 2
        assert "LIMIT %s OFFSET %s" in svc.db_connection.cursor_obj.executed[0]

    def test_get_conversations_error(self):
        svc = self._svc()
        svc.db_connection = None
        assert svc.get_conversations() == []

    def test_get_messages_success_and_error(self):
        svc = self._svc()
        svc.db_connection = FakeDb(rows=[{"id": 1}])
        assert len(svc.get_messages("wa", 10)) == 1
        svc.db_connection = None
        assert svc.get_messages("wa") == []

    def test_create_template_success_and_error(self):
        svc = self._svc()
        db = FakeDb()
        svc.db_connection = db
        result = svc.create_template("t1", "UTILITY", "en", [{"type": "BODY"}])
        assert result["success"] is True and result["template_name"] == "t1"
        assert db.commits == 1
        db2 = FakeDb()
        db2.cursor_obj.one = None
        svc.db_connection = db2
        result2 = svc.create_template("t2", "UTILITY", "en", [])
        assert result2["success"] is False
        assert db2.rollbacks == 1

    def test_get_analytics_success_and_error(self):
        svc = self._svc()
        svc.db_connection = FakeDb(
            rows=[{"direction": "inbound", "message_type": "text", "status": "received", "count": 3}],
            one={"total_conversations": 5, "active_conversations": 2},
        )
        start, end = datetime.now() - timedelta(days=30), datetime.now()
        result = svc.get_analytics(start, end)
        assert result["message_statistics"][0]["count"] == 3
        assert result["conversation_statistics"]["total_conversations"] == 5
        svc.db_connection = None
        assert svc.get_analytics(start, end) == {}

    def test_store_message_success_and_error(self):
        svc = self._svc()
        db = FakeDb()
        svc.db_connection = db
        svc._store_message("m1", "wa1", "text", {"body": "hi"}, "inbound", "received")
        assert db.commits == 1
        assert len(db.cursor_obj.executed) == 3
        db2 = FakeDb()
        db2.cursor_obj.execute = MagicMock(side_effect=RuntimeError("boom"))
        svc.db_connection = db2
        svc._store_message("m2", "wa1", "text", {}, "inbound", "received")
        assert db2.rollbacks == 1

    def test_process_incoming_message_types(self):
        stored = []
        whatsapp_mod.whatsapp_integration._store_message = MagicMock(side_effect=lambda **kw: stored.append(kw))
        cases = [
            ({"from": "wa", "id": "m1", "type": "text", "text": {"body": "hi"}}, {"body": "hi"}),
            ({"from": "wa", "id": "m2", "type": "image", "image": {"id": "i1", "caption": "cap"}}, {"media_id": "i1", "caption": "cap"}),
            ({"from": "wa", "id": "m3", "type": "audio", "audio": {"id": "a1"}}, {"media_id": "a1"}),
            ({"from": "wa", "id": "m4", "type": "document", "document": {"id": "d1", "filename": "f.pdf"}}, {"media_id": "d1", "filename": "f.pdf"}),
            ({"from": "wa", "id": "m5", "type": "sticker"}, {}),
        ]
        for message, expected_content in cases:
            with patch.object(whatsapp_mod.asyncio, "get_event_loop", side_effect=RuntimeError("no loop")), \
                 patch("integrations.universal_webhook_bridge.universal_webhook_bridge") as bridge:
                bridge.process_incoming_message = AsyncMock()
                whatsapp_mod._process_incoming_message(message)
            assert stored[-1]["content"] == expected_content
            assert stored[-1]["direction"] == "inbound"
            assert bridge.process_incoming_message.called

    def test_process_incoming_message_running_loop_schedules_task(self):
        whatsapp_mod.whatsapp_integration._store_message = MagicMock()
        loop = MagicMock()
        loop.is_running.return_value = True
        with patch.object(whatsapp_mod.asyncio, "get_event_loop", return_value=loop):
            whatsapp_mod._process_incoming_message({"from": "wa", "id": "m9", "type": "text", "text": {"body": "x"}})
        assert loop.create_task.called

    def test_process_incoming_message_store_failure_swallowed(self):
        whatsapp_mod.whatsapp_integration._store_message = MagicMock(side_effect=RuntimeError("boom"))
        with patch.object(whatsapp_mod.asyncio, "get_event_loop", side_effect=RuntimeError("no loop")), \
             patch("integrations.universal_webhook_bridge.universal_webhook_bridge"):
            whatsapp_mod._process_incoming_message({"from": "wa", "id": "m1", "type": "text", "text": {"body": "x"}})

    def test_initialize_whatsapp_integration_success_with_bp(self):
        app = MagicMock()
        bp = MagicMock()
        with patch.object(whatsapp_mod, "whatsapp_bp", bp), \
             patch.object(whatsapp_mod.whatsapp_integration, "initialize", return_value=True):
            whatsapp_mod.initialize_whatsapp_integration(app, {"access_token": "t"})
        app.register_blueprint.assert_called_once_with(bp)

    def test_initialize_whatsapp_integration_flask_unavailable(self):
        app = MagicMock()
        with patch.object(whatsapp_mod, "whatsapp_bp", None), \
             patch.object(whatsapp_mod.whatsapp_integration, "initialize", return_value=True):
            whatsapp_mod.initialize_whatsapp_integration(app, {})
        app.register_blueprint.assert_not_called()

    def test_initialize_whatsapp_integration_failure(self):
        app = MagicMock()
        with patch.object(whatsapp_mod.whatsapp_integration, "initialize", return_value=False):
            whatsapp_mod.initialize_whatsapp_integration(app, {})
        app.register_blueprint.assert_not_called()


class TestWhatsAppWebhookFailClosed:
    @contextlib.contextmanager
    def _route_ctx(self, json_body=None, args=None, headers=None, raw=b"", method="POST"):
        jf = MagicMock()
        jf.return_value = ("jsonified",)
        req = FakeFlaskRequest(json_body=json_body, args=args, headers=headers, raw=raw, method=method)
        with patch.object(whatsapp_mod, "request", req), patch.object(whatsapp_mod, "jsonify", jf):
            yield jf

    def test_webhook_get_verification_success(self):
        whatsapp_mod.whatsapp_integration.webhook_verify_token = "vt"
        with self._route_ctx(args={"hub.mode": "subscribe", "hub.verify_token": "vt", "hub.challenge": "ch1"}, method="GET"):
            result = whatsapp_mod.webhook()
        assert result == ("ch1", 200)

    def test_webhook_get_wrong_token_rejected(self):
        whatsapp_mod.whatsapp_integration.webhook_verify_token = "vt"
        with self._route_ctx(args={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "ch1"}, method="GET"):
            result = whatsapp_mod.webhook()
        assert result == ("Verification failed", 403)

    def test_webhook_get_fails_closed_when_token_unconfigured(self):
        whatsapp_mod.whatsapp_integration.webhook_verify_token = None
        with self._route_ctx(args={"hub.mode": "subscribe", "hub.challenge": "ch1"}, method="GET"):
            result = whatsapp_mod.webhook()
        assert result[1] == 403

    def test_webhook_post_fails_closed_when_unconfigured(self):
        whatsapp_mod.whatsapp_integration.webhook_app_secret = None
        stored = []
        whatsapp_mod.whatsapp_integration._store_message = MagicMock(side_effect=lambda **kw: stored.append(kw))
        with self._route_ctx(json_body={"entry": [{"changes": [{"value": {"messages": [{"from": "wa", "id": "m1", "type": "text"}]}}]}]}):
            result = whatsapp_mod.webhook()
        assert result == ("Webhook not configured", 503)
        assert not stored

    def test_webhook_post_missing_signature_rejected(self):
        whatsapp_mod.whatsapp_integration.webhook_app_secret = "as"
        with self._route_ctx(json_body={"entry": []}, headers={}):
            result = whatsapp_mod.webhook()
        assert result[1] == 401

    def test_webhook_post_bad_signature_rejected(self):
        whatsapp_mod.whatsapp_integration.webhook_app_secret = "as"
        raw = json.dumps({"entry": []}).encode()
        with self._route_ctx(json_body={"entry": []}, headers={"X-Hub-Signature-256": "sha256=deadbeef"}, raw=raw):
            result = whatsapp_mod.webhook()
        assert result[1] == 401

    def test_webhook_post_valid_signature_processed(self):
        whatsapp_mod.whatsapp_integration.webhook_app_secret = "as"
        stored = []
        whatsapp_mod.whatsapp_integration._store_message = MagicMock(side_effect=lambda **kw: stored.append(kw))
        body = {"entry": [{"changes": [{"value": {"messages": [{"from": "wa1", "id": "m1", "type": "text", "text": {"body": "hi"}}]}}]}]}
        raw = json.dumps(body).encode()
        headers = {"X-Hub-Signature-256": _hub_sig("as", raw)}
        with self._route_ctx(json_body=body, headers=headers, raw=raw), \
             patch.object(whatsapp_mod.asyncio, "get_event_loop", side_effect=RuntimeError("no loop")), \
             patch("integrations.universal_webhook_bridge.universal_webhook_bridge") as bridge:
            bridge.process_incoming_message = AsyncMock()
            result = whatsapp_mod.webhook()
        assert result == ("ok", 200)
        assert stored and stored[0]["whatsapp_id"] == "wa1"
        assert bridge.process_incoming_message.called

    def test_webhook_post_signature_encoding_flexible(self):
        whatsapp_mod.whatsapp_integration.webhook_app_secret = "as"
        raw = json.dumps({"entry": []}).encode()
        digest = hmac.new(b"as", raw, hashlib.sha256).digest()
        b64 = "sha256=" + __import__("base64").b64encode(digest).decode()
        with self._route_ctx(json_body={"entry": []}, headers={"X-Hub-Signature-256": b64}, raw=raw):
            result = whatsapp_mod.webhook()
        assert result == ("ok", 200)

    def test_webhook_exception_returns_500(self):
        with patch.object(whatsapp_mod, "request", FakeFlaskRequest(args={}, method="GET")), \
             patch.object(whatsapp_mod, "jsonify", MagicMock()):
            whatsapp_mod.request.args = MagicMock()
            whatsapp_mod.request.args.get.side_effect = RuntimeError("boom")
            result = whatsapp_mod.webhook()
        assert result == ("error", 500)


class TestWhatsAppRoutes:
    @contextlib.contextmanager
    def _ctx(self, json_body=None, args=None, headers=None, raw=b""):
        jf = MagicMock()
        jf.return_value = ("jsonified",)
        req = FakeFlaskRequest(json_body=json_body, args=args, headers=headers, raw=raw)
        with patch.object(whatsapp_mod, "request", req), patch.object(whatsapp_mod, "jsonify", jf):
            yield jf

    def test_health_route_healthy(self):
        whatsapp_mod.whatsapp_integration.access_token = "t"
        with self._ctx() as jf:
            result = whatsapp_mod.health_check()
        assert result == ("jsonified",)
        assert jf.call_args.args[0]["status"] == "healthy"

    def test_health_route_not_configured(self):
        whatsapp_mod.whatsapp_integration.access_token = None
        with self._ctx():
            result = whatsapp_mod.health_check()
        assert result[1] == 503

    def test_send_route_missing_fields(self):
        with self._ctx(json_body={"to": "123"}):
            result = asyncio.run(whatsapp_mod.send_message_route())
        assert result[1] == 400

    def test_send_route_success(self):
        payload = {"to": "123", "type": "text", "content": {"body": "hi"}}
        with self._ctx(json_body=payload) as jf, \
             patch.object(whatsapp_mod.whatsapp_integration, "send_message", new=AsyncMock(return_value={"success": True, "message_id": "w1"})) as send:
            result = asyncio.run(whatsapp_mod.send_message_route())
        send.assert_awaited_once()
        assert result == ("jsonified",)
        assert jf.call_args.args[0]["success"] is True

    def test_send_route_exception_generic(self):
        with self._ctx(json_body={"to": "123", "type": "text", "content": {}}) as jf, \
             patch.object(whatsapp_mod.whatsapp_integration, "send_message", new=AsyncMock(side_effect=RuntimeError("secret-detail"))):
            result = asyncio.run(whatsapp_mod.send_message_route())
        assert result[1] == 500
        assert "secret-detail" not in str(jf.call_args.args[0])

    def test_conversations_route_success_and_error(self):
        with self._ctx(args={"limit": "10", "offset": "5"}) as jf, \
             patch.object(whatsapp_mod.whatsapp_integration, "get_conversations", return_value=[]):
            result = whatsapp_mod.get_conversations()
        assert result == ("jsonified",)
        assert jf.call_args.args[0]["total"] == 0
        with self._ctx(args={}) as jf2, patch.object(whatsapp_mod.whatsapp_integration, "get_conversations", side_effect=RuntimeError("secret-detail")):
            result = whatsapp_mod.get_conversations()
        assert result[1] == 500
        assert "secret-detail" not in str(jf2.call_args.args[0])

    def test_messages_route_success_and_error(self):
        with self._ctx(args={"limit": "10"}) as jf:
            result = whatsapp_mod.get_messages("wa1")
        assert jf.call_args.args[0]["total"] == 0
        with self._ctx(args={}) as jf2, patch.object(whatsapp_mod.whatsapp_integration, "get_messages", side_effect=RuntimeError("secret-detail")):
            result = whatsapp_mod.get_messages("wa1")
        assert result[1] == 500
        assert "secret-detail" not in str(jf2.call_args.args[0])

    def test_create_template_route_missing_fields(self):
        with self._ctx(json_body={"template_name": "t"}):
            result = whatsapp_mod.create_template()
        assert result[1] == 400

    def test_create_template_route_success_and_error(self):
        body = {"template_name": "t1", "category": "UTILITY", "language_code": "en", "components": []}
        with self._ctx(json_body=body) as jf, \
             patch.object(whatsapp_mod.whatsapp_integration, "create_template", return_value={"success": True, "template_id": 1}):
            result = whatsapp_mod.create_template()
        assert jf.call_args.args[0]["success"] is True
        with self._ctx(json_body=body) as jf2, patch.object(whatsapp_mod.whatsapp_integration, "create_template", side_effect=RuntimeError("secret-detail")):
            result = whatsapp_mod.create_template()
        assert result[1] == 500
        assert "secret-detail" not in str(jf2.call_args.args[0])

    def test_analytics_route_with_and_without_dates(self):
        with self._ctx(args={}) as jf:
            result = whatsapp_mod.get_analytics()
        assert jf.call_args.args[0]["success"] is True
        with self._ctx(args={"start_date": "2026-01-01T00:00:00", "end_date": "2026-01-02T00:00:00"}) as jf2:
            result = whatsapp_mod.get_analytics()
        assert jf2.call_args.args[0]["period"]["start_date"].startswith("2026-01-01")
        with self._ctx(args={"start_date": "not-a-date"}) as jf3:
            result = whatsapp_mod.get_analytics()
        assert result[1] == 500
        assert "not-a-date" not in str(jf3.call_args.args[0])


# --------------------------------------------------------------------------
# ATOM Discord Integration
# --------------------------------------------------------------------------


class FakeType:
    def __init__(self, value):
        self.value = value


class FakeGuild:
    def __init__(self, guild_id, name="Discord Server", owner_id="owner_id", owner_name="Server Owner"):
        self.guild_id = guild_id
        self.name = name
        self.owner_id = owner_id
        self.owner_name = owner_name
        self.is_connected = True
        self.member_count = 100
        self.channel_count = 7
        self.icon_url = "https://cdn/icons/1.png"
        self.description = "A server"
        self.region = "us-east"
        self.features = ["NEWS", "VANITY_URL"]
        self.premium_tier = 2
        self.verification_level = 1
        self.roles_count = 12
        self.emojis_count = 30
        self.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)


class FakeChannel:
    def __init__(self, channel_id="c1", name="general", ctype=None):
        self.channel_id = channel_id
        self.name = name
        self.type = ctype or FakeType("GUILD_TEXT")
        self.topic = "talk here"
        self.is_archived = False
        self.member_count = 50
        self.message_count = 200
        self.last_modified_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
        self.is_private = False
        self.is_text = ctype is None or ctype.value == "GUILD_TEXT"
        self.is_voice = ctype is not None and ctype.value == "GUILD_VOICE"
        self.is_stage = False
        self.is_news = ctype is not None and ctype.value == "GUILD_NEWS"
        self.is_thread = False
        self.position = 1
        self.parent_id = None
        self.permissions = "0"
        self.rate_limit_per_user = 5
        self.guild_id = "g1"
        self.nsfw = False
        self.bitrate = 64000
        self.user_limit = 0
        self.default_auto_archive_duration = 1440
        self.flags = 0
        self.permission_overwrites = []
        self.last_pin_timestamp = None
        self.rtc_region = None


class FakeMessage:
    def __init__(self, message_id="m1", timestamp="2026-01-03T00:00:00Z"):
        self.message_id = message_id
        self.content = "hello world"
        self.user_id = "u1"
        self.user_name = "bob"
        self.user_display_name = "bob"
        self.user_discriminator = "0001"
        self.user_avatar = "aa"
        self.timestamp = timestamp
        self.thread_id = None
        self.reply_to_id = None
        self.type = 19
        self.is_edited = False
        self.edited_timestamp = None
        self.is_pinned = False
        self.is_crossposted = False
        self.is_command = False
        self.is_bot = False
        self.is_webhook = False
        self.is_system = False
        self.reactions = []
        self.attachments = []
        self.mentions = []
        self.embeds = []
        self.components = []
        self.stickers = []
        self.mention_roles = []
        self.mention_channels = []
        self.mention_everyone = False
        self.tts = False
        self.pinned = False
        self.flags = 0
        self.member = None
        self.referenced_message = None
        self.interaction = None
        self.application_id = None
        self.webhook_id = None
        self.position = 0
        self.message_snapshots = []


class FakeAnalyticsPoint:
    def __init__(self, value=1.0):
        self.timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.value = value
        self.dimensions = {"channel": "c1"}
        self.metadata = {"m": 1}


class FakeEventType:
    MESSAGE_CREATE = "MESSAGE_CREATE"
    GUILD_CREATE = "GUILD_CREATE"
    VOICE_STATE_UPDATE = "VOICE_STATE_UPDATE"


class FakeWorkspace:
    def __init__(self, wid="w1", voice_states=None, metadata=None):
        self.id = wid
        self.discord_guild_id = "g1"
        self.voice_states = voice_states if voice_states is not None else {}
        self.metadata = metadata if metadata is not None else {}
        self.updated_at = None


class FakeDbSession:
    def __init__(self, workspace=None):
        self._ws = workspace
        self.commits = 0

    def query(self, model):
        return self

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._ws

    def commit(self):
        self.commits += 1


@pytest.fixture
def disc():
    service = MagicMock()
    service.event_handlers = {
        FakeEventType.MESSAGE_CREATE: [],
        FakeEventType.GUILD_CREATE: [],
        FakeEventType.VOICE_STATE_UPDATE: [],
    }
    memory = MagicMock()
    memory.query = AsyncMock(return_value=[])
    memory.store = AsyncMock()
    memory.update = AsyncMock()
    search = MagicMock()
    search.index = AsyncMock()
    workflow = MagicMock()
    workflow.trigger_workflows = AsyncMock()
    workflow.create_workflow = AsyncMock()
    with patch.object(discord_mod, "discord_enhanced_service", service), \
         patch.object(discord_mod, "discord_analytics_engine", MagicMock()), \
         patch.object(discord_mod, "DiscordGuild", FakeGuild), \
         patch.object(discord_mod, "DiscordEventType", FakeEventType):
        svc = discord_mod.AtomDiscordIntegration({
            "atom_memory_service": memory,
            "atom_search_service": search,
            "atom_workflow_service": workflow,
        })
        yield svc


def _run(coro):
    return asyncio.run(coro)


class TestDiscordIntegration:
    def test_initialize_success(self, disc):
        disc.discord_service.get_guilds = AsyncMock(return_value=[])
        with patch.object(disc, "_start_integration_workers", new=AsyncMock()):
            assert _run(disc.initialize()) is True
        assert disc.is_initialized is True

    def test_initialize_missing_services(self, disc):
        disc.discord_service = None
        assert _run(disc.initialize()) is False

    def test_initialize_exception(self, disc):
        with patch.object(disc, "_start_integration_workers", new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert _run(disc.initialize()) is False

    def test_get_unified_workspaces_success(self, disc):
        disc.discord_service.get_guilds = AsyncMock(return_value=[FakeGuild("g1", name="Guild A")])
        workspaces = _run(disc.get_unified_workspaces("u1"))
        assert len(workspaces) == 1
        assert workspaces[0]["id"] == "discord_g1"
        assert workspaces[0]["type"] == "discord"
        assert workspaces[0]["status"] == "connected"
        assert workspaces[0]["integration_data"]["premium_tier"] == 2
        assert disc.active_guilds[0].guild_id == "g1"

    def test_get_unified_workspaces_error(self, disc):
        disc.discord_service.get_guilds = AsyncMock(side_effect=RuntimeError("boom"))
        assert _run(disc.get_unified_workspaces("u1")) == []

    def test_get_unified_channels_success(self, disc):
        disc.discord_service.get_guild_channels = AsyncMock(return_value=[
            FakeChannel("c1", "general"),
            FakeChannel("c2", "voice", FakeType("GUILD_VOICE")),
        ])
        channels = _run(disc.get_unified_channels("discord_g1", "u1"))
        assert len(channels) == 2
        assert channels[0]["id"] == "discord_c1"
        assert channels[0]["type"] == "guild-text"
        assert channels[0]["is_text"] is True and channels[0]["is_voice"] is False
        assert channels[1]["is_voice"] is True
        assert len(disc.communication_channels) == 2

    def test_get_unified_channels_non_discord_workspace(self, disc):
        assert _run(disc.get_unified_channels("slack_s1", "u1")) == []

    def test_get_unified_channels_no_guild(self, disc):
        with patch.object(discord_mod, "DiscordGuild", side_effect=TypeError("cannot instantiate")):
            assert _run(disc.get_unified_channels("discord_unknown", "u1")) == []

    def test_get_unified_channels_accumulates_without_duplicates(self, disc):
        disc.discord_service.get_guild_channels = AsyncMock(return_value=[FakeChannel("c1", "general")])
        _run(disc.get_unified_channels("discord_g1", "u1"))
        _run(disc.get_unified_channels("discord_g1", "u1"))
        assert len(disc.communication_channels) == 1

    def test_send_unified_message_success(self, disc):
        disc.discord_service.send_message = AsyncMock(return_value={"ok": True, "message_id": "dm1"})
        result = _run(disc.send_unified_message("discord_g1", "discord_c1", "hi", {"tts": True, "guild_id": "g1"}))
        assert result["ok"] is True
        assert result["platform"] == "Discord"
        disc.atom_memory.store.assert_awaited_once()
        disc.atom_search.index.assert_awaited_once()
        disc.atom_workflow.trigger_workflows.assert_awaited_once()
        disc.discord_service.send_message.assert_awaited_with(guild_id="g1", channel_id="c1", content="hi", embed=None, components=None, tts=True)

    def test_send_unified_message_discord_failure(self, disc):
        disc.discord_service.send_message = AsyncMock(return_value={"ok": False, "error": "rate limited"})
        result = _run(disc.send_unified_message("discord_g1", "discord_c1", "hi"))
        assert result == {"ok": False, "error": "rate limited"}

    def test_send_unified_message_unsupported_platform(self, disc):
        result = _run(disc.send_unified_message("slack_s1", "slack_c1", "hi"))
        assert result == {"ok": False, "error": "Unsupported platform"}

    def test_send_unified_message_exception(self, disc):
        disc.discord_service.send_message = AsyncMock(side_effect=RuntimeError("boom"))
        result = _run(disc.send_unified_message("discord_g1", "discord_c1", "hi"))
        assert result["ok"] is False

    def test_get_unified_messages_success(self, disc):
        disc.discord_service.get_channel_messages = AsyncMock(return_value=[
            FakeMessage("m1", "2026-01-03T00:00:00Z"),
            FakeMessage("m2", "2026-01-04T00:00:00Z"),
        ])
        messages = _run(disc.get_unified_messages("discord_g1", "discord_c1", limit=10, options={"before": "x"}))
        assert len(messages) == 2
        assert messages[0]["id"] == "discord_m2"
        assert messages[0]["message_type"] == "reply"
        assert messages[0]["platform"] == "Discord"
        assert messages[1]["metadata"]["has_thread"] is False
        assert len(disc.unified_messages) == 2

    def test_get_unified_messages_error(self, disc):
        disc.discord_service.get_channel_messages = AsyncMock(side_effect=RuntimeError("boom"))
        assert _run(disc.get_unified_messages("discord_g1", "discord_c1")) == []

    def test_unified_search_returns_results(self, disc):
        disc.discord_service.search_messages = AsyncMock(return_value={
            "ok": True,
            "messages": [{"results": [{"id": "m1", "content": "needle", "timestamp": "2026-01-03T00:00:00Z", "author": {"id": "u9", "username": "alice"}}]}],
            "total": 1,
        })
        results = _run(disc.unified_search("needle", "discord_g1", "discord_c1", {"limit": 10}))
        assert len(results) == 1
        assert results[0]["content"] == "needle"
        assert results[0]["id"] == "discord_m1"
        assert results[0]["user_name"] == "alice"

    def test_unified_search_error(self, disc):
        disc.discord_service.search_messages = AsyncMock(side_effect=RuntimeError("boom"))
        assert _run(disc.unified_search("q", "discord_g1", "discord_c1")) == []

    def test_create_unified_workflow_discord_trigger(self, disc):
        result = _run(disc.create_unified_workflow({"triggers": [{"platform": "discord", "event": "message"}], "actions": []}))
        assert result["ok"] is True
        assert result["platform"] == "discord"

    def test_create_unified_workflow_discord_action(self, disc):
        result = _run(disc.create_unified_workflow({"triggers": [], "actions": [{"action": "send_discord_message"}]}))
        assert result["ok"] is True

    def test_create_unified_workflow_non_discord_with_service(self, disc):
        disc.atom_workflow.create_workflow = AsyncMock(return_value={"ok": True, "workflow_id": "wf1"})
        result = _run(disc.create_unified_workflow({"triggers": [{"platform": "slack"}], "actions": []}))
        assert result["workflow_id"] == "wf1"

    def test_create_unified_workflow_non_discord_no_service(self, disc):
        disc.atom_workflow = None
        result = _run(disc.create_unified_workflow({"triggers": [], "actions": []}))
        assert result == {"ok": False, "error": "Workflow service not available"}

    def test_get_unified_analytics_with_engine(self, disc):
        disc.discord_analytics.get_analytics = AsyncMock(return_value=[FakeAnalyticsPoint(5.0)])
        result = _run(disc.get_unified_analytics("messages", "7d", "discord_g1", {"filters": {}}))
        assert result["metric"] == "messages"
        assert result["total_points"] == 1
        assert result["data_points"][0]["value"] == 5.0
        assert result["data_points"][0]["dimensions"] == {"channel": "c1"}

    def test_get_unified_analytics_without_engine(self, disc):
        disc.discord_analytics = None
        result = _run(disc.get_unified_analytics("messages", "7d"))
        assert result["total_points"] == 0

    def test_get_unified_analytics_exception(self, disc):
        disc.discord_analytics.get_analytics = AsyncMock(side_effect=RuntimeError("boom"))
        result = _run(disc.get_unified_analytics("messages", "7d"))
        assert result["ok"] is False

    def test_get_guild_by_id_success_and_failure(self, disc):
        guild = disc._get_guild_by_id("g1")
        assert guild.guild_id == "g1"
        with patch.object(discord_mod, "DiscordGuild", side_effect=TypeError("boom")):
            assert disc._get_guild_by_id("g1") is None

    def test_convert_message_type(self, disc):
        assert disc._convert_discord_message_type(0) == "default"
        assert disc._convert_discord_message_type(19) == "reply"
        assert disc._convert_discord_message_type(24) == "auto_moderation_action"
        assert disc._convert_discord_message_type(99) == "unknown"

    def test_convert_reactions_attachments_mentions_embeds(self, disc):
        reactions = [{"emoji": {"name": "🔥", "id": "e1", "animated": True}, "count": 3, "me": True}]
        assert disc._convert_discord_reactions(reactions) == [{
            "emoji": "🔥", "id": "e1", "animated": True, "count": 3, "me": True,
        }]
        assert disc._convert_discord_reactions([]) == []
        attachments = [{"id": "a1", "filename": "f.png", "content_type": "image/png", "url": "https://x/f.png", "proxy_url": "https://p/f.png", "size": 10, "width": 100, "height": 50}]
        converted = disc._convert_discord_attachments(attachments)
        assert converted[0]["download_url"] == "https://x/f.png"
        assert converted[0]["type"] == "discord_attachment"
        mentions = [{"id": "m", "username": "bob", "discriminator": "0001", "display_name": "Bobby", "avatar": "aa"}]
        assert disc._convert_discord_mentions(mentions)[0]["platform"] == "Discord"
        embeds = [{"title": "T", "description": "D", "url": "u", "type": "rich", "color": 1, "timestamp": "t", "footer": {}, "image": {}, "thumbnail": {}, "video": {}, "author": {}, "fields": []}]
        assert disc._convert_discord_embeds(embeds)[0]["title"] == "T"

    def test_store_message_in_memory(self, disc):
        disc.atom_memory.store = AsyncMock()
        _run(disc._store_message_in_memory({"message_id": "m1", "content": "x"}, "discord", {"k": "v"}))
        disc.atom_memory.store.assert_awaited_once()
        stored = disc.atom_memory.store.call_args.args[0]
        assert stored["type"] == "unified_message"
        assert stored["synced"] is True
        disc.atom_memory = None
        _run(disc._store_message_in_memory({}, "discord"))

    def test_index_message_in_search(self, disc):
        disc.atom_search.index = AsyncMock()
        _run(disc._index_message_in_search({"message_id": "m1", "user_name": "bob"}, "discord"))
        disc.atom_search.index.assert_awaited_once()
        disc.atom_search = None
        _run(disc._index_message_in_search({}, "discord"))

    def test_trigger_workflows(self, disc):
        disc.atom_workflow.trigger_workflows = AsyncMock()
        _run(disc._trigger_workflows({"guild_id": "g1"}, "discord_message_sent", {"o": 1}))
        disc.atom_workflow.trigger_workflows.assert_awaited_once()
        disc.atom_workflow = None
        _run(disc._trigger_workflows({}, "x"))

    def test_update_workspace_cross_platform_no_sync(self, disc):
        disc.workspace_sync = None
        _run(disc._update_workspace_cross_platform({"guild_id": "g1"}, "discord"))

    def test_update_workspace_cross_platform_propagates(self, disc):
        disc.db = FakeDbSession(workspace=None)
        sync = MagicMock()
        sync.propagate_change = AsyncMock()
        sync.create_unified_workspace = MagicMock(return_value=FakeWorkspace("w9"))
        disc.workspace_sync = sync
        for event_type, expected in [
            ("GUILD_UPDATE", "name_change"),
            ("GUILD_NAME_UPDATE", "name_change"),
            ("GUILD_MEMBER_ADD", "member_add"),
            ("GUILD_MEMBER_REMOVE", "member_remove"),
            ("GUILD_ROLE_UPDATE", "member_role_change"),
            ("GUILD_CHANNEL_CREATE", "channel_add"),
            ("GUILD_CHANNEL_DELETE", "channel_remove"),
            ("SOMETHING_ELSE", "settings_change"),
        ]:
            _run(disc._update_workspace_cross_platform({"guild_id": "g1", "guild_name": "G", "type": event_type}, "discord"))
            assert sync.propagate_change.await_args.kwargs["change_type"] == expected
            sync.propagate_change.reset_mock()

    def test_get_or_create_unified_workspace_existing(self, disc):
        disc.db = FakeDbSession(workspace=FakeWorkspace("w1"))
        ws = _run(disc._get_or_create_unified_workspace("g1", "Guild"))
        assert ws.id == "w1"

    def test_get_or_create_unified_workspace_creates(self, disc):
        disc.db = FakeDbSession(workspace=None)
        sync = MagicMock()
        sync.create_unified_workspace = MagicMock(return_value=FakeWorkspace("w2"))
        disc.workspace_sync = sync
        ws = _run(disc._get_or_create_unified_workspace("g1", "Guild"))
        assert ws.id == "w2"
        assert sync.create_unified_workspace.call_args.kwargs["discord_guild_id"] == "g1"

    def test_get_or_create_unified_workspace_error(self, disc):
        disc.db = FakeDbSession(workspace=None)
        disc.db.query = MagicMock(side_effect=RuntimeError("boom"))
        assert _run(disc._get_or_create_unified_workspace("g1", "G")) is None

    def test_update_voice_state_cross_platform_success(self, disc):
        ws = FakeWorkspace("w1")
        disc.db = FakeDbSession(workspace=ws)
        sync = MagicMock()
        sync.propagate_change = AsyncMock()
        disc.workspace_sync = sync
        _run(disc._update_voice_state_cross_platform({"user_id": "u1", "guild_id": "g1", "channel_id": "c1", "state": "joined"}, "discord"))
        assert "u1_discord" in ws.voice_states
        assert disc.db.commits == 1

    def test_update_voice_state_cross_platform_no_workspace(self, disc):
        disc.db = FakeDbSession(workspace=None)
        disc.workspace_sync = MagicMock()
        _run(disc._update_voice_state_cross_platform({"guild_id": "g1"}, "discord"))
        assert disc.db.commits == 0

    def test_update_voice_state_cross_platform_no_sync(self, disc):
        disc.workspace_sync = None
        _run(disc._update_voice_state_cross_platform({"guild_id": "g1"}, "discord"))

    def test_update_voice_state_cross_platform_exception(self, disc):
        disc.db = FakeDbSession(workspace=FakeWorkspace("w1"))
        disc.db.commit = MagicMock(side_effect=RuntimeError("boom"))
        disc.workspace_sync = MagicMock()
        _run(disc._update_voice_state_cross_platform({"guild_id": "g1", "user_id": "u1", "state": "joined"}, "discord"))

    def test_check_voice_state_conflicts_detected(self, disc):
        ws = FakeWorkspace("w1", voice_states={
            "u1_discord": {"platform": "discord", "channel_id": "c1", "state": "joined", "timestamp": "t1"},
            "u1_slack": {"platform": "slack", "channel_id": "s1", "state": "joined", "timestamp": "t2"},
        })
        _run(disc._check_voice_state_conflicts(ws, "u1", "discord", "joined"))
        assert len(ws.metadata["voice_conflicts"]) == 1
        assert ws.metadata["voice_conflicts"][0]["platforms"] == ["discord", "slack"]

    def test_check_voice_state_conflicts_none(self, disc):
        ws = FakeWorkspace("w1", voice_states={
            "u1_discord": {"platform": "discord", "channel_id": "c1", "state": "joined", "timestamp": "t1"},
            "u1_slack": {"platform": "slack", "channel_id": "s1", "state": "left", "timestamp": "t2"},
        })
        _run(disc._check_voice_state_conflicts(ws, "u1", "discord", "joined"))
        assert "voice_conflicts" not in ws.metadata
        _run(disc._check_voice_state_conflicts(ws, "u1", "discord", "left"))
        assert "voice_conflicts" not in ws.metadata

    def test_ingestion_worker_iteration(self, disc):
        calls = []
        async def fake_sleep(seconds):
            calls.append(seconds)
            if len(calls) == 1:
                raise RuntimeError("transient")
            raise asyncio.CancelledError()
        with patch.object(discord_mod.asyncio, "sleep", side_effect=fake_sleep):
            with pytest.raises(asyncio.CancelledError):
                _run(disc._discord_message_ingestion_worker())
        assert calls == [30, 60]

    def test_event_processing_worker_iteration(self, disc):
        with patch.object(discord_mod.asyncio, "sleep", side_effect=[asyncio.CancelledError()]):
            with pytest.raises(asyncio.CancelledError):
                _run(disc._discord_event_processing_worker())

    def test_search_indexing_worker_iteration(self, disc):
        disc.atom_memory.query = AsyncMock(return_value=[{"id": "m1", "content": "x"}])
        disc.atom_memory.update = AsyncMock()
        disc.atom_search.index = AsyncMock()
        with patch.object(discord_mod.asyncio, "sleep", side_effect=[asyncio.CancelledError()]):
            with pytest.raises(asyncio.CancelledError):
                _run(disc._unified_search_indexing_worker())
        disc.atom_search.index.assert_awaited_once()
        disc.atom_memory.update.assert_awaited_once()

    def test_search_indexing_worker_no_services(self, disc):
        disc.atom_search = None
        with patch.object(discord_mod.asyncio, "sleep", side_effect=[asyncio.CancelledError()]):
            with pytest.raises(asyncio.CancelledError):
                _run(disc._unified_search_indexing_worker())


# --------------------------------------------------------------------------
# HubSpot Routes
# --------------------------------------------------------------------------


def _make_hubspot_service(access_token="tok"):
    svc = hubspot_mod.HubSpotService()
    svc.access_token = access_token
    svc.advanced_service = None
    return svc


class TestHubSpotService:
    def test_authenticate_success(self):
        svc = _make_hubspot_service(None)
        svc.client.post = AsyncMock(return_value=FakeResponse(200, {"access_token": "at", "refresh_token": "rt", "expires_in": 3600}))
        svc.client.get = AsyncMock(return_value=FakeResponse(200, {"portalId": 123}))
        result = asyncio.run(svc.authenticate(hubspot_mod.HubSpotAuthRequest(client_id="c", client_secret="s", redirect_uri="http://x", code="code")))
        assert result["access_token"] == "at"
        assert result["hub_id"] == 123

    def test_authenticate_httpx_error(self):
        svc = _make_hubspot_service(None)
        svc.client.post = AsyncMock(side_effect=httpx.ConnectError("no route"))
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.authenticate(hubspot_mod.HubSpotAuthRequest(client_id="c", client_secret="s", redirect_uri="http://x", code="code")))
        assert exc.value.status_code == 400

    def test_authenticate_unexpected_error(self):
        svc = _make_hubspot_service(None)
        svc.client.post = AsyncMock(side_effect=RuntimeError("boom"))
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.authenticate(hubspot_mod.HubSpotAuthRequest(client_id="c", client_secret="s", redirect_uri="http://x", code="code")))
        assert exc.value.status_code == 500

    def test_get_hub_id_success_and_failure(self):
        svc = _make_hubspot_service()
        svc.client.get = AsyncMock(return_value=FakeResponse(200, {"portalId": 42}))
        asyncio.run(svc._get_hub_id())
        assert svc.hub_id == 42
        svc.client.get = AsyncMock(side_effect=httpx.ConnectError("x"))
        asyncio.run(svc._get_hub_id())
        assert svc.hub_id is None

    def test_get_contacts_success(self):
        svc = _make_hubspot_service()
        svc.client.get = AsyncMock(return_value=FakeResponse(200, {"results": [{
            "id": "1",
            "properties": {
                "email": "a@b.com", "firstname": "A", "lastname": "B", "company": "C",
                "phone": "555", "createdate": "1700000000000", "lastmodifieddate": "1700000001000",
                "lifecyclestage": "lead", "hs_lead_status": "open",
            },
        }]}))
        contacts = asyncio.run(svc.get_contacts(limit=5, offset=3))
        assert len(contacts) == 1
        assert contacts[0].email == "a@b.com"
        assert contacts[0].first_name == "A"
        assert svc.client.get.call_args.kwargs["params"]["after"] == 3

    def test_get_contacts_unauthenticated(self):
        svc = _make_hubspot_service(None)
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.get_contacts())
        assert exc.value.status_code == 401

    def test_get_contacts_httpx_error(self):
        svc = _make_hubspot_service()
        svc.client.get = AsyncMock(side_effect=httpx.ConnectError("x"))
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.get_contacts())
        assert exc.value.status_code == 400

    def test_get_contacts_unexpected_error(self):
        svc = _make_hubspot_service()
        svc.client.get = AsyncMock(return_value=FakeResponse(200, {"results": [{"id": "1", "properties": {"createdate": "not-a-number"}}]}))
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.get_contacts())
        assert exc.value.status_code == 500

    def test_get_contacts_wrapper_unauthenticated(self):
        svc = _make_hubspot_service(None)
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.get_contacts_wrapper())
        assert exc.value.status_code == 401
        assert "credentials" in exc.value.detail.lower()

    def test_get_companies_success(self):
        svc = _make_hubspot_service()
        svc.client.get = AsyncMock(return_value=FakeResponse(200, {"results": [{
            "id": "c1",
            "properties": {"name": "N", "domain": "d.com", "industry": "tech", "city": "NYC",
                           "state": "NY", "country": "US", "createdate": "1700000000000",
                           "lastmodifieddate": "1700000001000"},
        }]}))
        companies = asyncio.run(svc.get_companies(limit=100, offset=0))
        assert companies[0].name == "N"
        assert companies[0].industry == "tech"

    def test_get_companies_unauthenticated(self):
        svc = _make_hubspot_service(None)
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.get_companies())
        assert exc.value.status_code == 401

    def test_get_deals_success(self):
        svc = _make_hubspot_service()
        svc.client.get = AsyncMock(return_value=FakeResponse(200, {"results": [{
            "id": "d1",
            "properties": {"dealname": "Big Deal", "amount": "50000", "dealstage": "qualifiedtobuy",
                           "pipeline": "default", "closedate": "1700000000000",
                           "createdate": "1700000000000", "lastmodifieddate": "1700000001000",
                           "hubspot_owner_id": "o1"},
        }]}))
        deals = asyncio.run(svc.get_deals())
        assert deals[0].deal_name == "Big Deal"
        assert deals[0].amount == 50000.0
        assert deals[0].owner_id == "o1"

    def test_get_deals_wrapper_unauthenticated(self):
        svc = _make_hubspot_service(None)
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.get_deals_wrapper())
        assert exc.value.status_code == 401

    def test_get_campaigns_success(self):
        svc = _make_hubspot_service()
        svc.client.get = AsyncMock(return_value=FakeResponse(200, {"campaigns": [{
            "id": "m1", "name": "Q4", "type": "email", "status": "sent",
            "createdAt": "1700000000000", "updatedAt": "1700000001000",
            "numIncluded": 100, "numResponded": 5,
        }]}))
        campaigns = asyncio.run(svc.get_campaigns())
        assert campaigns[0].name == "Q4"
        assert campaigns[0].num_included == 100

    def test_get_lists_success(self):
        svc = _make_hubspot_service()
        svc.client.get = AsyncMock(return_value=FakeResponse(200, {"lists": [{
            "listId": "7", "name": "Leads", "listType": "STATIC", "createdAt": "1700000000000",
            "lastProcessingFinishedAt": "1700000001000", "metaData": {"size": 25},
        }]}))
        lists = asyncio.run(svc.get_lists())
        assert lists[0].id == "7"
        assert lists[0].member_count == 25

    def test_get_lists_unauthenticated(self):
        svc = _make_hubspot_service(None)
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.get_lists())
        assert exc.value.status_code == 401

    def test_search_content_success(self):
        svc = _make_hubspot_service()
        svc.client.post = AsyncMock(return_value=FakeResponse(200, {"results": [{"id": "1"}], "total": 1}))
        result = asyncio.run(svc.search_content(hubspot_mod.HubSpotSearchRequest(query="a@b.com", object_type="contact")))
        assert result.total == 1
        assert len(result.results) == 1

    def test_search_content_unauthenticated(self):
        svc = _make_hubspot_service(None)
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.search_content(hubspot_mod.HubSpotSearchRequest(query="q")))
        assert exc.value.status_code == 401

    def test_create_contact_success(self):
        svc = _make_hubspot_service()
        svc.client.post = AsyncMock(return_value=FakeResponse(201, {"id": "c9"}))
        result = asyncio.run(svc.create_contact(hubspot_mod.HubSpotContactCreate(email="a@b.com", first_name="A", last_name=None)))
        assert result["id"] == "c9"
        payload = svc.client.post.call_args.kwargs["json"]["properties"]
        assert payload == {"email": "a@b.com", "firstname": "A"}

    def test_create_contact_httpx_error(self):
        svc = _make_hubspot_service()
        svc.client.post = AsyncMock(side_effect=httpx.ConnectError("x"))
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.create_contact(hubspot_mod.HubSpotContactCreate(email="a@b.com")))
        assert exc.value.status_code == 400

    def test_create_deal_success(self):
        svc = _make_hubspot_service()
        svc.client.post = AsyncMock(return_value=FakeResponse(201, {"id": "d9"}))
        result = asyncio.run(svc.create_deal(hubspot_mod.HubSpotDealCreate(
            deal_name="Deal", amount=1000.0, stage="qualifiedtobuy", pipeline="default",
            close_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )))
        assert result["id"] == "d9"
        props = svc.client.post.call_args.kwargs["json"]["properties"]
        assert props["amount"] == "1000.0"
        assert props["closedate"] is not None

    def test_create_deal_unauthenticated(self):
        svc = _make_hubspot_service(None)
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.create_deal(hubspot_mod.HubSpotDealCreate(deal_name="D", stage="s", pipeline="p")))
        assert exc.value.status_code == 401

    def test_get_stats_advanced(self):
        svc = _make_hubspot_service()
        advanced = MagicMock()
        advanced.analytics_metrics = {"total_contacts": 10, "total_companies": 2, "total_deals": 3,
                                      "total_campaigns": 1, "active_deals": 2, "won_deals": 1,
                                      "lost_deals": 0, "total_revenue": 5000.0}
        svc.advanced_service = advanced
        stats = asyncio.run(svc.get_stats())
        assert stats.total_contacts == 10
        assert stats.total_revenue == 5000.0

    def test_get_stats_fallback(self):
        svc = _make_hubspot_service()
        stats = asyncio.run(svc.get_stats())
        assert stats.total_contacts == 1500

    def test_get_stats_unauthenticated(self):
        svc = _make_hubspot_service(None)
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.get_stats())
        assert exc.value.status_code == 401

    def test_get_stats_exception(self):
        svc = _make_hubspot_service()
        advanced = MagicMock()
        advanced.analytics_metrics = None
        svc.advanced_service = advanced
        with pytest.raises(HTTPException) as exc:
            asyncio.run(svc.get_stats())
        assert exc.value.status_code == 500

    def test_health_check_and_wrapper(self):
        svc = _make_hubspot_service()
        result = asyncio.run(svc.health_check())
        assert result["ok"] is True
        manager = MagicMock()
        manager.is_mock_mode.return_value = True
        with patch.object(hubspot_mod, "get_mock_mode_manager", return_value=manager):
            result2 = asyncio.run(svc.health_check_wrapper())
        assert result2["is_mock"] is True
        manager.is_mock_mode.return_value = False
        with patch.object(hubspot_mod, "get_mock_mode_manager", return_value=manager):
            result3 = asyncio.run(svc.health_check_wrapper())
        assert result3["ok"] is True
        assert "is_mock" not in result3


class TestHubSpotRoutes:
    @pytest.fixture
    def client(self):
        app = FastAPI()
        app.include_router(hubspot_mod.router)
        app.dependency_overrides[hubspot_mod.get_current_user] = lambda: {"user_id": "u1"}
        return TestClient(app, raise_server_exceptions=False)

    def _patch_service(self, service):
        return patch.object(hubspot_mod, "HubSpotService", lambda: service)

    def test_start_oauth_unconfigured(self, client):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("HUBSPOT_CLIENT_ID", None)
            resp = client.get("/api/hubspot/auth/start")
        assert resp.status_code == 200
        assert resp.json()["ok"] is False

    def test_start_oauth_configured(self, client):
        with patch.dict(os.environ, {"HUBSPOT_CLIENT_ID": "cid", "HUBSPOT_REDIRECT_URI": "http://cb"}):
            resp = client.get("/api/hubspot/auth/start")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "app.hubspot.com/oauth/authorize" in data["auth_url"]
        assert "client_id=cid" in data["auth_url"]

    def test_callback_route(self, client):
        svc = _make_hubspot_service(None)
        svc.authenticate = AsyncMock(return_value={"access_token": "at", "hub_id": 1})
        with self._patch_service(svc):
            resp = client.post("/api/hubspot/callback", json={
                "client_id": "c", "client_secret": "s", "redirect_uri": "http://cb", "code": "code",
            })
        assert resp.status_code == 200
        assert resp.json()["hub_id"] == 1

    def test_contacts_route(self, client):
        svc = _make_hubspot_service()
        svc.get_contacts_wrapper = AsyncMock(return_value=[hubspot_mod.HubSpotContact(
            id="1", email="a@b.com", created_at=datetime.now(), last_modified=datetime.now(),
        )])
        with self._patch_service(svc):
            resp = client.get("/api/hubspot/contacts")
        assert resp.status_code == 200
        assert resp.json()[0]["email"] == "a@b.com"

    def test_companies_route(self, client):
        svc = _make_hubspot_service()
        svc.get_companies = AsyncMock(return_value=[])
        with self._patch_service(svc):
            resp = client.get("/api/hubspot/companies")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_deals_route(self, client):
        svc = _make_hubspot_service()
        svc.get_deals_wrapper = AsyncMock(return_value=[])
        with self._patch_service(svc):
            resp = client.get("/api/hubspot/deals")
        assert resp.status_code == 200

    def test_campaigns_route(self, client):
        svc = _make_hubspot_service()
        svc.get_campaigns = AsyncMock(return_value=[])
        with self._patch_service(svc):
            resp = client.get("/api/hubspot/campaigns")
        assert resp.status_code == 200

    def test_lists_route(self, client):
        svc = _make_hubspot_service()
        svc.get_lists = AsyncMock(return_value=[])
        with self._patch_service(svc):
            resp = client.get("/api/hubspot/lists")
        assert resp.status_code == 200

    def test_search_route(self, client):
        svc = _make_hubspot_service()
        svc.search_content = AsyncMock(return_value=hubspot_mod.HubSpotSearchResponse(results=[], total=0))
        with self._patch_service(svc):
            resp = client.post("/api/hubspot/search", json={"query": "q", "object_type": "contact"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_create_contact_route(self, client):
        svc = _make_hubspot_service()
        svc.create_contact = AsyncMock(return_value={"id": "c1"})
        with self._patch_service(svc):
            resp = client.post("/api/hubspot/contacts/create", json={"email": "a@b.com"})
        assert resp.status_code == 200
        assert resp.json()["id"] == "c1"

    def test_create_deal_route(self, client):
        svc = _make_hubspot_service()
        svc.create_deal = AsyncMock(return_value={"id": "d1"})
        with self._patch_service(svc):
            resp = client.post("/api/hubspot/deals/create", json={"deal_name": "D", "stage": "s", "pipeline": "p"})
        assert resp.status_code == 200

    def test_stats_route(self, client):
        svc = _make_hubspot_service()
        svc.get_stats = AsyncMock(return_value=hubspot_mod.HubSpotStats(
            total_contacts=1, total_companies=0, total_deals=0, total_campaigns=0,
            active_deals=0, won_deals=0, lost_deals=0, total_revenue=0.0,
        ))
        with self._patch_service(svc):
            resp = client.get("/api/hubspot/stats")
        assert resp.status_code == 200
        assert resp.json()["total_contacts"] == 1

    def test_health_route(self, client):
        svc = _make_hubspot_service()
        svc.health_check_wrapper = AsyncMock(return_value={"ok": True, "status": "healthy", "service": "hubspot"})
        with self._patch_service(svc):
            resp = client.get("/api/hubspot/health")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_root_route(self, client):
        resp = client.get("/api/hubspot/")
        assert resp.status_code == 200
        assert resp.json()["service"] == "hubspot"

    def test_analytics_route_default(self, client):
        svc = _make_hubspot_service()
        svc.advanced_service = None
        with self._patch_service(svc):
            resp = client.get("/api/hubspot/analytics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["totalContacts"] == 1547
        assert len(data["topPerformingCampaigns"]) == 3

    def test_analytics_route_advanced(self, client):
        svc = _make_hubspot_service()
        advanced = MagicMock()
        advanced.analytics_metrics = {
            "total_contacts": 10, "total_companies": 3, "total_deals": 5,
            "total_revenue": "9000", "win_rate": "75.5", "monthly_revenue": "1000",
            "top_campaigns": [{"name": "C1", "performance": "50", "roi": "100", "budget": "10"}],
            "recent_activities": [{"type": "Deal", "description": "d", "timestamp": "t", "contact": "x"}],
            "pipeline_stages": [{"stage": "s", "count": "1", "value": "2", "probability": "3"}],
        }
        svc.advanced_service = advanced
        with self._patch_service(svc):
            resp = client.get("/api/hubspot/analytics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["totalContacts"] == 10
        assert data["totalDealValue"] == 9000.0
        assert data["topPerformingCampaigns"][0]["name"] == "C1"

    def test_ai_predictions_route(self, client):
        resp = client.get("/api/hubspot/ai/predictions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["models"]) == 3
        assert data["models"][0]["performance"]["auc"] == 0.91
        assert data["forecast"][3]["actual"] is None

    def test_analyze_lead_route_advanced(self, client):
        svc = _make_hubspot_service()
        advanced = MagicMock()
        advanced._score_lead = AsyncMock(return_value=85.0)
        svc.advanced_service = advanced
        with self._patch_service(svc):
            resp = client.post("/api/hubspot/ai/analyze-lead", json={"contact_id": "c1"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["leadScore"] == 85.0
        assert data["timeframe"] == "2-4 weeks"
        assert data["recommendations"][0]["priority"] == "high"

    def test_analyze_lead_route_fallback(self, client):
        svc = _make_hubspot_service()
        svc.advanced_service = None
        with self._patch_service(svc):
            resp = client.post("/api/hubspot/ai/analyze-lead", json={"contact_id": "c1"})
        assert resp.status_code == 200
        data = resp.json()
        assert 60 <= data["leadScore"] <= 95
        assert data["keyFactors"][0]["factor"] == "Email Engagement"

    def test_analyze_lead_route_advanced_failure_falls_back(self, client):
        svc = _make_hubspot_service()
        advanced = MagicMock()
        advanced._score_lead = AsyncMock(side_effect=RuntimeError("boom"))
        svc.advanced_service = advanced
        with self._patch_service(svc):
            resp = client.post("/api/hubspot/ai/analyze-lead", json={"contact_id": "c1"})
        assert resp.status_code == 200
        assert 60 <= resp.json()["leadScore"] <= 95
