# -*- coding: utf-8 -*-
"""Coverage wave 97 — messaging adapters + integrations routes/services:

- integrations/adapters/line_adapter.py
- integrations/adapters/messenger_adapter.py
- integrations/adapters/signal_adapter.py
- integrations/zoom_routes.py
- integrations/zoho_projects_service.py
- integrations/asana_routes.py
- integrations/airtable_routes.py
- integrations/telegram_routes.py
- integrations/mailchimp_service.py
- integrations/xero_service.py

Standalone: each module reaches >=80% line coverage from this file alone.
No network / no LLM / no real DB: httpx boundaries mocked, FastAPI
TestClient + dependency_overrides for routes.
"""
import base64
import hmac as hmac_mod
import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def _hresp(status=200, json_data=None, content=b""):
    r = httpx.Response(status, json=json_data if json_data is not None else {},
                       request=httpx.Request("GET", "http://x"))
    if content:
        r._content = content
    return r


def _ok(json_data=None):
    return _hresp(200, json_data if json_data is not None else {})


def _db(first=None):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = first
    db.query.return_value.filter_by.return_value.first.return_value = first
    return db


# ============================================================================
# integrations/adapters/line_adapter.py
# ============================================================================

from integrations.adapters.line_adapter import LineAdapter


def _line(**cfg):
    return LineAdapter(dict(channel_access_token="tok",
                            channel_secret="sec", **cfg))


class TestLineAdapter:
    def test_init_variants(self, monkeypatch):
        monkeypatch.delenv("LINE_CHANNEL_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("LINE_CHANNEL_SECRET", raising=False)
        a = LineAdapter()
        assert a.is_enabled is False
        a = _line()
        assert a.is_enabled is True
        assert a.api_url.endswith("/v2/bot")

    async def test_get_client_and_close(self):
        a = _line()
        c1 = await a._get_client()
        assert c1 is await a._get_client()
        await a.close()
        assert a.client is None
        a2 = _line()
        mock_client = MagicMock()
        a2.client = mock_client
        mock_client.aclose = AsyncMock()
        await a2.close()
        mock_client.aclose.assert_awaited()

    def test_verify_signature(self):
        a = _line()
        body = b"payload"
        sig = base64.b64encode(
            hmac_mod.new(b"sec", body, hashlib.sha256).digest()).decode()
        assert a.verify_signature(body, sig) is True
        assert a.verify_signature(body, "bm90LXZhbGlkAAAA") is False
        assert a.verify_signature(body, "!!!not-base64!!!") is False
        # no secret configured -> skipped
        a2 = LineAdapter({"channel_access_token": "t"})
        assert a2.verify_signature(body, "x") is True

    async def test_send_message_paths(self):
        a = _line()
        a.client = MagicMock()
        a.client.post = AsyncMock(return_value=_ok())
        assert (await a.send_message("u1", "hi"))["ok"] is True
        assert (await a.send_message("u1", "hi", reply_token="rt"))["ok"] is True
        url = a.client.post.call_args[0][0]
        assert "reply" in url
        # error branch
        a.client.post = AsyncMock(side_effect=RuntimeError("net"))
        assert (await a.send_message("u1", "hi"))["ok"] is False
        # no client
        a2 = LineAdapter()
        r = await a2.send_message("u1", "hi")
        assert r["ok"] is False
        # HTTP error status
        a3 = _line()
        a3.client = MagicMock()
        resp = _hresp(500, {})
        a3.client.post = AsyncMock(return_value=resp)
        with patch.object(httpx.Response, "raise_for_status",
                          side_effect=httpx.HTTPError("x")):
            assert (await a3.send_message("u1", "hi"))["ok"] is False

    async def test_send_messages_quick_reply_template(self):
        a = _line()
        a.client = MagicMock()
        a.client.post = AsyncMock(return_value=_ok())
        msgs = [{"type": "text", "text": "a"}]
        r = await a.send_messages("u1", msgs)
        assert r["ok"] is True and r["count"] == 1
        r = await a.send_messages("u1", msgs, reply_token="rt")
        assert r["ok"] is True
        r = await a.send_quick_reply("u1", "hi", [{"label": "y"}])
        assert r["ok"] is True
        payload = a.client.post.call_args[1]["json"]
        assert payload["messages"][0]["quickReply"]["items"][0]["label"] == "y"
        r = await a.send_template_message("u1", "alt", {"type": "buttons"})
        assert r["ok"] is True
        # failures
        a.client.post = AsyncMock(side_effect=RuntimeError("net"))
        assert (await a.send_messages("u", msgs))["ok"] is False
        assert (await a.send_quick_reply("u", "t", []))["ok"] is False
        assert (await a.send_template_message("u", "a", {}))["ok"] is False
        a2 = LineAdapter()
        assert (await a2.send_messages("u", msgs))["ok"] is False

    async def test_get_user_profile(self):
        a = _line()
        a.client = MagicMock()
        a.client.get = AsyncMock(return_value=_ok(
            {"userId": "u", "displayName": "D", "pictureUrl": "p",
             "statusMessage": "s"}))
        r = await a.get_user_profile("u")
        assert r["ok"] is True and r["display_name"] == "D"
        a.client.get = AsyncMock(side_effect=RuntimeError("net"))
        assert (await a.get_user_profile("u"))["ok"] is False
        a2 = LineAdapter()
        assert (await a2.get_user_profile("u"))["ok"] is False

    async def test_handle_webhook_event(self):
        a = _line()
        assert (await a.handle_webhook_event({}))["ok"] is False
        base = {"source": {"type": "user", "userId": "u1"},
                "replyToken": "rt", "timestamp": 1}
        text_ev = await a.handle_webhook_event(
            {"events": [dict(base, type="message",
                             message={"type": "text", "text": "hi", "id": "m"})]})
        assert text_ev["text"] == "hi" and text_ev["ok"] is True
        img_ev = await a.handle_webhook_event(
            {"events": [dict(base, type="message",
                             message={"type": "image", "id": "m",
                                      "contentProvider": {"x": 1}})]})
        assert img_ev["message_type"] == "image"
        for et in ("follow", "unfollow", "join", "leave"):
            r = await a.handle_webhook_event({"events": [dict(base, type=et)]})
            assert r["ok"] is True and r["event_type"] == et
        r = await a.handle_webhook_event(
            {"events": [dict(base, type="postback",
                             postback={"data": "d", "params": {}})]})
        assert r["data"] == "d" and r["params"] == {}
        r = await a.handle_webhook_event(
            {"events": [dict(base, type="beacon",
                             beacon={"hwid": "h", "type": "enter"})]})
        assert r["hwid"] == "h"
        r = await a.handle_webhook_event({"events": [dict(base, type="weird")]})
        assert r["event_type"] == "weird"
        # exception branch: source raises (non-dict)
        r = await a.handle_webhook_event(
            {"events": [dict(base, type="message", message={"type": "text"},
                             source="notadict")]})
        assert r["ok"] is False

    async def test_capabilities_and_status(self):
        a = _line()
        caps = await a.get_capabilities()
        assert caps["platform"] == "LINE"
        assert (await a.get_service_status())["status"] == "active"
        assert (await LineAdapter().get_service_status())["status"] == "inactive"


# ============================================================================
# integrations/adapters/messenger_adapter.py
# ============================================================================

from integrations.adapters.messenger_adapter import MessengerAdapter


def _msgr(**cfg):
    return MessengerAdapter(dict(page_access_token="tok",
                                 app_secret="sec", **cfg))


class TestMessengerAdapter:
    def test_init(self, monkeypatch):
        monkeypatch.delenv("FACEBOOK_PAGE_ACCESS_TOKEN", raising=False)
        assert MessengerAdapter().is_enabled is False
        assert _msgr().is_enabled is True
        assert _msgr(verify_token="vt").verify_token == "vt"

    async def test_get_client_close(self):
        m = _msgr()
        c = await m._get_client()
        assert c is not None
        await m.close()
        assert m.client is None

    def test_verify_webhook(self):
        m = _msgr()
        assert m.verify_webhook("subscribe", "atom_verify_token",
                                "ch")["ok"] is True
        assert m.verify_webhook("subscribe", "wrong",
                                "ch")["ok"] is False
        assert m.verify_webhook("badmode", "atom_verify_token",
                                "ch")["ok"] is False

    def test_verify_signature(self):
        m = _msgr()
        payload = b"body"
        sig = hmac_mod.new(b"sec", payload, hashlib.sha1).hexdigest()
        assert m.verify_signature(payload, f"sha1={sig}") is True
        assert m.verify_signature(payload, "deadbeef") is False
        m2 = MessengerAdapter({"page_access_token": "t"})
        assert m2.verify_signature(payload, "x") is True

    async def test_send_message(self):
        m = _msgr()
        m.client = MagicMock()
        m.client.post = AsyncMock(return_value=_ok({"message_id": "m1"}))
        r = await m.send_message("psid", "hi", quick_replies=[{"a": 1}])
        assert r["ok"] is True and r["message_id"] == "m1"
        assert m.client.post.call_args[1]["json"]["message"][
            "quick_replies"] == [{"a": 1}]
        m.client.post = AsyncMock(side_effect=RuntimeError("net"))
        assert (await m.send_message("p", "x"))["ok"] is False
        assert (await MessengerAdapter().send_message("p", "x"))["ok"] is False

    async def test_send_attachment(self):
        m = _msgr()
        m.client = MagicMock()
        m.client.post = AsyncMock(return_value=_ok({"attachment_id": "a1"}))
        r = await m.send_attachment("p", "image", "http://img")
        assert r["ok"] is True and r["attachment_id"] == "a1"
        m.client.post = AsyncMock(side_effect=RuntimeError("net"))
        assert (await m.send_attachment("p", "image", "u"))["ok"] is False
        assert (await MessengerAdapter().send_attachment(
            "p", "image", "u"))["ok"] is False

    async def test_get_user_info(self):
        m = _msgr()
        m.client = MagicMock()
        m.client.get = AsyncMock(return_value=_ok(
            {"first_name": "F", "last_name": "L", "profile_pic": "pic"}))
        r = await m.get_user_info("u")
        assert r["ok"] is True and r["first_name"] == "F"
        m.client.get = AsyncMock(side_effect=RuntimeError("net"))
        assert (await m.get_user_info("u"))["ok"] is False
        assert (await MessengerAdapter().get_user_info("u"))["ok"] is False

    async def test_handle_webhook_event(self):
        m = _msgr()
        assert (await m.handle_webhook_event({}))["ok"] is False
        assert (await m.handle_webhook_event({"entry": [
            {"messaging": []}]}))["event_type"] == "unknown"
        mk = lambda ev: {"entry": [{"messaging": [ev]}]}
        ev = {"sender": {"id": "s"}, "recipient": {"id": "r"},
              "message": {"text": "t", "attachments": [1], "mid": "m1"}}
        r = await m.handle_webhook_event(mk(ev))
        assert r["event_type"] == "message" and r["text"] == "t"
        r = await m.handle_webhook_event(mk({"sender": {"id": "s"},
                                             "delivery": {"watermark": 5,
                                                          "mids": ["m"]}}))
        assert r["event_type"] == "delivery" and r["watermark"] == 5
        r = await m.handle_webhook_event(mk({"sender": {"id": "s"},
                                             "read": {"watermark": 9}}))
        assert r["event_type"] == "read"
        r = await m.handle_webhook_event(mk({"sender": {"id": "s"},
                                             "postback": {"payload": "pp"}}))
        assert r["event_type"] == "postback" and r["payload"] == "pp"
        r = await m.handle_webhook_event(mk({"sender": {"id": "s"},
                                             "other": 1}))
        assert r["event_type"] == "unknown"
        # exception branch
        with patch.object(m, "_get_client", side_effect=RuntimeError("x")):
            pass
        r = await m.handle_webhook_event({"entry": "notalist"})
        assert r["ok"] is False

    async def test_capabilities_and_status(self):
        m = _msgr()
        assert (await m.get_capabilities())["platform"] == "Facebook Messenger"
        assert (await m.get_service_status())["status"] == "active"
        assert (await MessengerAdapter().get_service_status())[
            "status"] == "inactive"


# ============================================================================
# integrations/adapters/signal_adapter.py
# ============================================================================

from integrations.adapters.signal_adapter import SignalAdapter


def _sig(**cfg):
    return SignalAdapter(dict(signal_phone_number="+15551234567",
                              signal_api_url="http://sig:8080", **cfg))


class TestSignalAdapter:
    def test_init(self, monkeypatch):
        monkeypatch.delenv("SIGNAL_PHONE_NUMBER", raising=False)
        assert SignalAdapter().is_enabled is False
        a = _sig()
        assert a.is_enabled is True
        assert a.api_url == "http://sig:8080"

    async def test_client_and_close(self):
        s = _sig()
        c = await s._get_client()
        assert c is not None
        await s.close()
        assert s.client is None
        s2 = _sig()
        mock_client = MagicMock()
        s2.client = mock_client
        mock_client.aclose = AsyncMock()
        await s2.close()
        mock_client.aclose.assert_awaited()

    async def test_send_message(self):
        s = _sig()
        s.client = MagicMock()
        s.client.post = AsyncMock(return_value=_ok({"timestamp": "123"}))
        r = await s.send_message("+1", "hi", attachments=[{"filename": "f"}])
        assert r["ok"] is True and r["message_id"] == "123"
        assert s.client.post.call_args[1]["json"]["attachments"] == [
            {"filename": "f"}]
        s.client.post = AsyncMock(side_effect=RuntimeError("net"))
        assert (await s.send_message("+1", "x"))["ok"] is False
        assert (await SignalAdapter().send_message("+1", "x"))["ok"] is False

    async def test_send_receipt(self):
        s = _sig()
        s.client = MagicMock()
        s.client.post = AsyncMock(return_value=_ok())
        r = await s.send_receipt("+1", "ts")
        assert r["ok"] is True and r["type"] == "read"
        s.client.post = AsyncMock(side_effect=RuntimeError("net"))
        assert (await s.send_receipt("+1", "ts"))["ok"] is False
        assert (await SignalAdapter().send_receipt("+1", "t"))["ok"] is False

    async def test_get_account_info(self):
        s = _sig()
        s.client = MagicMock()
        s.client.get = AsyncMock(return_value=_ok({"version": "v"}))
        r = await s.get_account_info()
        assert r["ok"] is True and r["data"] == {"version": "v"}
        s.client.get = AsyncMock(side_effect=RuntimeError("net"))
        assert (await s.get_account_info())["ok"] is False
        assert (await SignalAdapter().get_account_info())["ok"] is False

    async def test_verify_webhook(self):
        s = _sig()
        r = await s.verify_webhook("ch")
        assert r["ok"] is True and r["challenge"] == "ch"

    async def test_handle_webhook_event(self):
        s = _sig()
        msg = {"type": "message", "envelope": {
            "timestamp": 1, "data": {
                "source": {"number": "+1"},
                "message": {"body": "hello"}}}}
        r = await s.handle_webhook_event(msg)
        assert r["event_type"] == "message" and r["message"] == "hello"
        rcpt = {"type": "receipt", "envelope": {
            "data": {"receipt": {"type": "read", "timestamp": 2}}}}
        r = await s.handle_webhook_event(rcpt)
        assert r["event_type"] == "receipt" and r["type"] == "read"
        r = await s.handle_webhook_event({"type": "other"})
        assert r["event_type"] == "other"
        r = await s.handle_webhook_event({})
        assert r["event_type"] == "unknown"
        # exception branch
        r = await s.handle_webhook_event({"type": "message",
                                          "envelope": None})
        assert r["ok"] is False

    async def test_capabilities_and_status(self):
        s = _sig()
        assert (await s.get_capabilities())["platform"] == "Signal"
        s.get_account_info = AsyncMock(return_value={"ok": True, "data": {}})
        st = await s.get_service_status()
        assert st["status"] == "active" and st["account_info"] is not None
        s2 = _sig()
        s2.get_account_info = AsyncMock(return_value={"ok": False})
        st = await s2.get_service_status()
        assert st["account_info"] is None
        s3 = _sig()
        s3.get_account_info = AsyncMock(side_effect=RuntimeError("x"))
        assert (await s3.get_service_status())["status"] == "error"


# ============================================================================
# integrations/zoom_routes.py
# ============================================================================

from core.auth import get_current_user
from core.database import get_db
from integrations import zoom_routes as zr


@pytest.fixture
def zoom_client():
    app = FastAPI()
    app.include_router(zr.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="u1")
    return TestClient(app)


class TestZoomRoutes:
    def test_auth_url(self, zoom_client):
        with patch.object(zr, "zoom_auth_handler") as h:
            h.get_authorization_url = MagicMock(return_value="http://z")
            r = zoom_client.get("/api/zoom/v1/auth/url", params={"state": "s"})
            assert r.status_code == 200 and r.json()["url"] == "http://z"
            h.get_authorization_url = MagicMock(side_effect=RuntimeError("x"))
            assert zoom_client.get(
                "/api/zoom/v1/auth/url").status_code == 500

    def test_callback(self, zoom_client):
        with patch.object(zr, "zoom_auth_handler") as h:
            h.exchange_code_for_token = AsyncMock(return_value={
                "access_token": "at", "refresh_token": "rt",
                "expires_in": 3600})
            r = zoom_client.get("/api/zoom/v1/callback",
                                params={"code": "c"})
            assert r.json()["ok"] is True and r.json()["access_token"] == "at"
            h.exchange_code_for_token = AsyncMock(
                side_effect=RuntimeError("x"))
            assert zoom_client.get(
                "/api/zoom/v1/callback", params={"code": "c"}).status_code \
                == 400

    def test_status(self, zoom_client):
        with patch.object(zr, "zoom_auth_handler") as h:
            h.get_connection_status = MagicMock(
                return_value={"connected": True})
            r = zoom_client.get("/api/zoom/v1/status")
            assert r.json()["status"] == "connected"
            h.get_connection_status = MagicMock(
                return_value={"connected": False})
            assert zoom_client.get("/api/zoom/v1/status").json()[
                "status"] == "disconnected"
            h.get_connection_status = MagicMock(side_effect=RuntimeError("x"))
            assert zoom_client.get("/api/zoom/v1/status").status_code == 500

    def test_health(self, zoom_client):
        with patch.object(zr, "get_mock_mode_manager") as gmm:
            gmm.return_value.is_mock_mode = MagicMock(return_value=True)
            r = zoom_client.get("/api/zoom/v1/health")
            assert r.json()["is_mock"] is True
            gmm.return_value.is_mock_mode = MagicMock(return_value=False)
            with patch.object(zr, "zoom_service") as svc, \
                    patch.object(zr, "zoom_auth_handler") as h:
                svc.health_check = AsyncMock(return_value={"ok": True,
                                                           "status": "ok"})
                h.get_connection_status = MagicMock(
                    return_value={"connected": True, "has_access_token": True})
                r = zoom_client.get("/api/zoom/v1/health")
                assert r.json()["ok"] is True and r.json()["is_mock"] is False
                svc.health_check = AsyncMock(side_effect=RuntimeError("x"))
                r = zoom_client.get("/api/zoom/v1/health")
                assert r.json()["status"] == "unhealthy"

    def test_create_meeting(self, zoom_client):
        body = {"topic": "T", "user_id": "me", "duration": 30,
                "timezone": "UTC"}
        with patch.object(zr, "zoom_auth_handler") as h, \
                patch.object(zr, "zoom_service") as svc:
            h.ensure_valid_token = AsyncMock(return_value="at")
            svc.create_meeting = AsyncMock(return_value={
                "id": 1, "topic": "T", "join_url": "j", "start_time": "s",
                "duration": 30})
            r = zoom_client.post("/api/zoom/v1/meetings", json=body)
            assert r.json()["ok"] is True and r.json()["meeting_id"] == 1
            # HTTPException passthrough
            svc.create_meeting = AsyncMock(
                side_effect=HTTPException(401, "nope"))
            assert zoom_client.post("/api/zoom/v1/meetings",
                                    json=body).status_code == 401
            svc.create_meeting = AsyncMock(side_effect=RuntimeError("x"))
            assert zoom_client.post("/api/zoom/v1/meetings",
                                    json=body).status_code == 500

    def test_list_meetings(self, zoom_client):
        with patch.object(zr, "zoom_auth_handler") as h, \
                patch.object(zr, "zoom_service") as svc:
            h.ensure_valid_token = AsyncMock(return_value="at")
            svc.list_meetings = AsyncMock(return_value={
                "meetings": [{"id": 1}], "total_records": 1, "page_size": 30})
            r = zoom_client.get("/api/zoom/v1/meetings")
            assert r.json()["total"] == 1
            h.ensure_valid_token = AsyncMock(return_value=None)
            assert zoom_client.get(
                "/api/zoom/v1/meetings").status_code == 401
            h.ensure_valid_token = AsyncMock(return_value="at")
            svc.list_meetings = AsyncMock(side_effect=RuntimeError("x"))
            assert zoom_client.get(
                "/api/zoom/v1/meetings").status_code == 500

    def test_list_users(self, zoom_client):
        with patch.object(zr, "zoom_auth_handler") as h, \
                patch.object(zr, "zoom_service") as svc:
            h.ensure_valid_token = AsyncMock(return_value="at")
            svc.list_users = AsyncMock(return_value={
                "users": [{"id": "u"}], "total_records": 1})
            r = zoom_client.get("/api/zoom/v1/users")
            assert r.json()["total_records"] == 1
            h.ensure_valid_token = AsyncMock(return_value=None)
            assert zoom_client.get("/api/zoom/v1/users").status_code == 401
            h.ensure_valid_token = AsyncMock(return_value="at")
            svc.list_users = AsyncMock(side_effect=RuntimeError("x"))
            assert zoom_client.get(
                "/api/zoom/v1/users").status_code == 500

    def test_list_recordings(self, zoom_client):
        with patch.object(zr, "zoom_auth_handler") as h, \
                patch.object(zr, "zoom_service") as svc:
            h.ensure_valid_token = AsyncMock(return_value="at")
            svc.list_recordings = AsyncMock(return_value={
                "meetings": [{"id": 1}], "total_records": 1})
            r = zoom_client.get("/api/zoom/v1/recordings",
                                params={"from_date": "2026-01-01",
                                        "to_date": "2026-02-01"})
            assert r.json()["recordings"][0]["id"] == 1
            h.ensure_valid_token = AsyncMock(return_value=None)
            assert zoom_client.get(
                "/api/zoom/v1/recordings").status_code == 401
            h.ensure_valid_token = AsyncMock(return_value="at")
            svc.list_recordings = AsyncMock(side_effect=RuntimeError("x"))
            assert zoom_client.get(
                "/api/zoom/v1/recordings").status_code == 500


# ============================================================================
# integrations/zoho_projects_service.py
# ============================================================================

from integrations.zoho_projects_service import ZohoProjectsService


def _zp():
    return ZohoProjectsService(tenant_id="t1",
                               config={"access_token": "at"})


class TestZohoProjectsService:
    def test_static(self):
        s = _zp()
        assert s.get_capabilities()["supports_webhooks"] is False
        h = s.health_check()
        assert h["healthy"] is True
        h2 = ZohoProjectsService(tenant_id="t", config={}).health_check()
        assert h2["healthy"] is False

    async def test_getters(self):
        s = _zp()
        s.client = MagicMock()
        s.client.get = AsyncMock(return_value=_ok({"portals": [{"id": "p"}]}))
        assert await s.get_portals("at") == [{"id": "p"}]
        s.client.get = AsyncMock(return_value=_ok(
            {"projects": [{"id_string": "pr1", "name": "P"}]}))
        assert await s.get_projects("at", "portal") == [
            {"id_string": "pr1", "name": "P"}]
        s.client.get = AsyncMock(return_value=_ok({"tasks": [{"id": "t"}]}))
        assert await s.get_tasks("at", "portal", "pr1") == [{"id": "t"}]
        for meth, args in (("get_portals", ("at",)),
                           ("get_projects", ("at", "p")),
                           ("get_tasks", ("at", "p", "pr"))):
            s.client.get = AsyncMock(side_effect=RuntimeError("net"))
            assert await getattr(s, meth)(*args) == []

    async def test_get_all_active_tasks(self):
        s = _zp()
        s.get_projects = AsyncMock(return_value=[
            {"id_string": "p1", "name": "P1"},
            {"id_string": "p2", "name": "P2"}])
        s.get_tasks = AsyncMock(side_effect=[[{"id": 1}, {"id": 2}],
                                             [{"id": 3}]])
        r = await s.get_all_active_tasks("at", "portal", limit=3)
        assert len(r) == 3 and r[0]["project_name"] == "P1"
        # limit reached mid-project
        s.get_tasks = AsyncMock(return_value=[{"id": 1}, {"id": 2}])
        r = await s.get_all_active_tasks("at", "portal", limit=1)
        assert r == [{"id": 1, "project_name": "P1"}]
        s.get_projects = AsyncMock(side_effect=RuntimeError("x"))
        assert await s.get_all_active_tasks("at", "p") == []

    async def test_create_task(self):
        s = _zp()
        s.client = MagicMock()
        s.client.post = AsyncMock(return_value=_ok(
            {"tasks": [{"id": "t1", "name": "n"}]}))
        assert (await s.create_task("at", "p", "pr", {"name": "n"}))["id"] \
            == "t1"
        s.client.post = AsyncMock(side_effect=RuntimeError("net"))
        with pytest.raises(HTTPException):
            await s.create_task("at", "p", "pr", {})

    async def test_execute_operation(self):
        s = _zp()
        s.get_portals = AsyncMock(return_value=[{"id": "p"}])
        r = await s.execute_operation("get_portals", {})
        assert r["success"] is True
        r = await s.execute_operation("nope", {})
        assert r["success"] is False
        s.get_portals = AsyncMock(side_effect=RuntimeError("x"))
        r = await s.execute_operation("get_portals", {})
        assert r["success"] is False

    async def test_sync_and_full_sync(self, monkeypatch):
        s = _zp()
        db = _db(first=None)
        monkeypatch.setattr("core.database.SessionLocal",
                            MagicMock(return_value=db))
        # with portal_id (get_projects success + failure)
        s.get_projects = AsyncMock(return_value=[{"id": 1}])
        assert (await s.sync_to_postgres_cache("ws", "at", "portal")) == \
            {"success": True, "metrics_synced": 1}
        # verify filter keyed on workspace_id (no tenant_id bug present)
        kwargs = db.query.return_value.filter_by.call_args[1]
        assert "workspace_id" in kwargs and "tenant_id" not in kwargs
        s.get_projects = AsyncMock(side_effect=RuntimeError("net"))
        assert (await s.sync_to_postgres_cache("ws", "at", "portal"))[
            "success"] is True
        # existing metric update branch
        db.query.return_value.filter_by.return_value.first.return_value = \
            MagicMock()
        assert (await s.sync_to_postgres_cache("ws", "at"))[
            "metrics_synced"] == 1
        # commit failure
        db.commit = MagicMock(side_effect=RuntimeError("x"))
        assert (await s.sync_to_postgres_cache("ws", "at"))["success"] is False
        assert db.rollback.called
        # SessionLocal failure
        monkeypatch.setattr("core.database.SessionLocal",
                            MagicMock(side_effect=RuntimeError("db")))
        assert (await s.sync_to_postgres_cache("ws", "at"))["success"] is False
        s.sync_to_postgres_cache = AsyncMock(return_value={"success": True})
        r = await s.full_sync("ws", "at", "portal")
        assert r["success"] and r["workspace_id"] == "ws"


# ============================================================================
# integrations/asana_routes.py
# ============================================================================

from integrations import asana_routes as ar


@pytest.fixture
def asana_client():
    app = FastAPI()
    app.include_router(ar.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="u1")
    app.dependency_overrides[ar.get_access_token] = lambda: "tok"
    app.dependency_overrides[ar.get_super_admin] = lambda: SimpleNamespace(
        id="adm", email="a@b.c")
    return TestClient(app)


@pytest.fixture
def asvc():
    svc = MagicMock()
    svc.health_check = AsyncMock(return_value={"ok": True, "user": {}})
    svc.get_user_profile = AsyncMock(return_value={"ok": True, "data": {}})
    svc.get_workspaces = AsyncMock(return_value={"ok": True,
                                                 "workspaces": [{"id": "w"}]})
    svc.get_projects = AsyncMock(return_value={"ok": True, "data": []})
    svc.get_tasks = AsyncMock(return_value={"ok": True, "data": []})
    svc.create_task = AsyncMock(return_value={"ok": True, "data": {}})
    svc.create_project = AsyncMock(return_value={"ok": True, "data": {}})
    svc.update_task = AsyncMock(return_value={"ok": True, "data": {}})
    svc.get_teams = AsyncMock(return_value={"ok": True, "data": []})
    svc.get_users = AsyncMock(return_value={"ok": True, "data": []})
    svc.search_tasks = AsyncMock(return_value={"ok": True, "data": []})
    svc.get_task_stories = AsyncMock(return_value={"ok": True, "data": []})
    svc.add_task_comment = AsyncMock(return_value={"ok": True, "data": {}})
    with patch.object(ar, "asana_service", svc):
        yield svc


class TestAsanaRoutes:
    def test_auth_token_endpoint(self, asana_client):
        with patch.object(ar, "token_storage") as ts:
            r = asana_client.post("/api/asana/auth/token",
                                  json={"token": "tk"})
            assert r.json()["status"] == "success"
            ts.save_token.assert_called()
            # empty token body fails validation (422)
            assert asana_client.post("/api/asana/auth/token",
                                     json={"token": ""}).status_code == 422

    def test_health(self, asana_client, asvc):
        r = asana_client.get("/api/asana/health")
        assert r.json()["success"] is True
        asvc.health_check = AsyncMock(return_value={"ok": False,
                                                    "error": "down"})
        assert asana_client.get("/api/asana/health").status_code == 503
        asvc.health_check = AsyncMock(side_effect=RuntimeError("x"))
        assert asana_client.get("/api/asana/health").status_code == 503

    def test_crud_endpoints(self, asana_client, asvc):
        assert asana_client.get("/api/asana/user/profile").json()["ok"]
        assert asana_client.get("/api/asana/workspaces").json()["ok"]
        r = asana_client.get("/api/asana/projects",
                             params={"workspace_gid": "w"})
        assert r.json()["ok"]
        assert asana_client.get("/api/asana/tasks").json()["ok"]
        r = asana_client.post("/api/asana/tasks",
                              json={"name": "T", "projects": ["p"]})
        assert r.json()["ok"]
        r = asana_client.post("/api/asana/projects",
                              json={"name": "P", "workspace": "w"})
        assert r.json()["ok"]
        r = asana_client.put("/api/asana/tasks/t1",
                             json={"name": "T2", "completed": True})
        assert r.json()["ok"]
        assert asana_client.get("/api/asana/teams",
                                params={"workspace_gid": "w"}).json()["ok"]
        assert asana_client.get("/api/asana/users",
                                params={"workspace_gid": "w"}).json()["ok"]
        r = asana_client.post("/api/asana/search",
                              json={"query": "q", "workspace_gid": "w"})
        assert r.json()["ok"]
        assert asana_client.get("/api/asana/tasks/t1/stories").json()["ok"]
        r = asana_client.post("/api/asana/tasks/t1/comments",
                              json={"text": "c"})
        assert r.json()["ok"]

    def test_error_branches(self, asana_client, asvc):
        bad = {"ok": False, "error": "bad"}
        for setter in ("get_user_profile", "get_workspaces", "get_projects",
                       "get_tasks", "create_task", "create_project",
                       "update_task", "get_teams", "get_users",
                       "search_tasks", "get_task_stories",
                       "add_task_comment"):
            setattr(asvc, setter, AsyncMock(return_value=bad))
        assert asana_client.get("/api/asana/user/profile").status_code == 400
        assert asana_client.get("/api/asana/workspaces").status_code == 400
        assert asana_client.get("/api/asana/projects").status_code == 400
        assert asana_client.get("/api/asana/tasks").status_code == 400
        assert asana_client.post("/api/asana/tasks",
                                 json={"name": "T"}).status_code == 400
        assert asana_client.post("/api/asana/projects",
                                 json={"name": "P",
                                       "workspace": "w"}).status_code == 400
        assert asana_client.put("/api/asana/tasks/t1",
                                json={"name": "x"}).status_code == 400
        assert asana_client.get("/api/asana/teams",
                                params={"workspace_gid": "w"}
                                ).status_code == 400
        assert asana_client.get("/api/asana/users",
                                params={"workspace_gid": "w"}
                                ).status_code == 400
        assert asana_client.post("/api/asana/search", json={
            "query": "q", "workspace_gid": "w"}).status_code == 400
        assert asana_client.get("/api/asana/tasks/t1/stories"
                                ).status_code == 400
        assert asana_client.post("/api/asana/tasks/t1/comments",
                                 json={"text": "c"}).status_code == 400

    def test_status(self, asana_client, asvc):
        r = asana_client.get("/api/asana/status")
        assert r.json()["connected"] is True
        asvc.health_check = AsyncMock(return_value={"ok": False,
                                                    "error": "x"})
        r = asana_client.get("/api/asana/status")
        assert r.json()["connected"] is False
        asvc.health_check = AsyncMock(return_value={"ok": True})
        asvc.get_workspaces = AsyncMock(return_value={"ok": False})
        r = asana_client.get("/api/asana/status")
        assert r.json()["workspaces"] == []
        asvc.health_check = AsyncMock(side_effect=RuntimeError("x"))
        r = asana_client.get("/api/asana/status")
        assert r.json()["ok"] is False

    def test_misc_endpoints(self, asana_client):
        assert asana_client.get("/api/asana/error-test").status_code == 400
        assert asana_client.post("/api/asana/webhooks").status_code == 200
        r = asana_client.delete("/api/asana/webhooks/wg1")
        assert "wg1" in r.json()["message"]

    async def test_get_access_token_dependency(self, monkeypatch):
        monkeypatch.delenv("ASANA_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        with patch.object(ar, "token_storage") as ts:
            # no token anywhere -> 401 (dev message)
            ts.get_token.return_value = None
            with pytest.raises(HTTPException) as ei:
                await ar.get_access_token(None)
            assert ei.value.status_code == 401
            # production variant
            monkeypatch.setenv("ENVIRONMENT", "production")
            with pytest.raises(HTTPException) as ei:
                await ar.get_access_token(None)
            assert "production" not in ei.value.detail  # generic message
            monkeypatch.delenv("ENVIRONMENT", raising=False)
            # env var fallback
            monkeypatch.setenv("ASANA_ACCESS_TOKEN", "envtok")
            assert await ar.get_access_token(None) == "envtok"
            # valid stored token
            ts.get_token.return_value = {"access_token": "stored"}
            ts.is_token_expired.return_value = False
            assert await ar.get_access_token(None) == "stored"
            # expired with refresh_token success
            ts.is_token_expired.return_value = True
            ts.get_token.return_value = {"access_token": "old",
                                         "refresh_token": "rt",
                                         "extra": "keep"}
            with patch.object(ar, "OAuthHandler") as oh:
                oh.return_value.refresh_access_token = AsyncMock(
                    return_value={"access_token": "new"})
                assert await ar.get_access_token(None) == "new"
                saved = ts.save_token.call_args[0][1]
                assert saved["extra"] == "keep"
            # expired, refresh fails -> falls back to stored token
            with patch.object(ar, "OAuthHandler") as oh:
                oh.return_value.refresh_access_token = AsyncMock(
                    side_effect=RuntimeError("x"))
                assert await ar.get_access_token(None) == "old"
            # expired, no refresh token
            ts.get_token.return_value = {"access_token": "old2"}
            assert await ar.get_access_token(None) == "old2"


# ============================================================================
# integrations/airtable_routes.py
# ============================================================================

from integrations import airtable_routes as air


@pytest.fixture
def airtable_client():
    app = FastAPI()
    app.include_router(air.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="u1")
    return TestClient(app)


class TestAirtableRoutes:
    def test_status(self, airtable_client):
        with patch.object(air, "airtable_service") as svc:
            svc.api_key = "key"
            svc.health_check = AsyncMock(return_value={"ok": True})
            r = airtable_client.get("/api/airtable/status")
            assert r.json()["status"] == "connected"
            svc.api_key = None
            svc.health_check = AsyncMock(return_value={"ok": False})
            r = airtable_client.get("/api/airtable/status")
            assert r.json()["status"] == "not_configured"

    def test_health(self, airtable_client):
        with patch.object(air, "airtable_service") as svc:
            svc.api_key = "key"
            svc.health_check = AsyncMock(return_value={"ok": True})
            r = airtable_client.get("/api/airtable/health")
            assert r.json()["status"] == "healthy"
            svc.api_key = None
            svc.health_check = AsyncMock(return_value={"ok": False})
            r = airtable_client.get("/api/airtable/health")
            assert r.json()["status"] == "unhealthy"

    def test_record_crud(self, airtable_client):
        with patch.object(air, "airtable_service") as svc:
            svc.list_records = AsyncMock(return_value=[{"id": "r1"}])
            r = airtable_client.get("/api/airtable/records/b1/t1",
                                    params={"max_records": 5, "view": "v",
                                            "filter_formula": "F"})
            assert r.json()["count"] == 1
            svc.get_record = AsyncMock(return_value={"id": "r1"})
            r = airtable_client.get("/api/airtable/records/b1/t1/r1")
            assert r.json()["ok"] is True
            svc.create_record = AsyncMock(return_value={"id": "r2"})
            r = airtable_client.post("/api/airtable/records", json={
                "base_id": "b", "table_name": "t", "fields": {"a": 1}})
            assert r.json()["ok"] is True
            svc.update_record = AsyncMock(return_value={"id": "r3"})
            r = airtable_client.patch("/api/airtable/records", json={
                "base_id": "b", "table_name": "t", "record_id": "r",
                "fields": {"a": 2}})
            assert r.json()["ok"] is True
            svc.delete_record = AsyncMock(return_value=True)
            r = airtable_client.delete("/api/airtable/records/b/t/r")
            assert r.json()["deleted"] is True

    def test_record_errors(self, airtable_client):
        with patch.object(air, "airtable_service") as svc:
            svc.list_records = AsyncMock(side_effect=RuntimeError("x"))
            assert airtable_client.get(
                "/api/airtable/records/b/t").status_code == 500
            # HTTPException passthrough
            svc.list_records = AsyncMock(side_effect=HTTPException(401))
            assert airtable_client.get(
                "/api/airtable/records/b/t").status_code == 401
            svc.get_record = AsyncMock(side_effect=RuntimeError("x"))
            assert airtable_client.get(
                "/api/airtable/records/b/t/r").status_code == 500
            svc.create_record = AsyncMock(side_effect=RuntimeError("x"))
            assert airtable_client.post("/api/airtable/records", json={
                "base_id": "b", "table_name": "t",
                "fields": {}}).status_code == 500
            svc.update_record = AsyncMock(side_effect=RuntimeError("x"))
            assert airtable_client.patch("/api/airtable/records", json={
                "base_id": "b", "table_name": "t", "record_id": "r",
                "fields": {}}).status_code == 500
            svc.delete_record = AsyncMock(side_effect=RuntimeError("x"))
            assert airtable_client.delete(
                "/api/airtable/records/b/t/r").status_code == 500

    def test_search(self, airtable_client):
        with patch.object(air, "airtable_service") as svc:
            svc.list_records = AsyncMock(return_value=[{"id": "r"}])
            r = airtable_client.post("/api/airtable/search", json={
                "query": "q", "base_id": "b", "table_name": "t"})
            assert r.json()["ok"] is True and len(r.json()["results"]) == 1
            svc.list_records = AsyncMock(side_effect=RuntimeError("x"))
            r = airtable_client.post("/api/airtable/search", json={
                "query": "q", "base_id": "b", "table_name": "t"})
            assert r.json()["ok"] is False
            r = airtable_client.post("/api/airtable/search",
                                     json={"query": "q"})
            assert r.json()["ok"] is True and r.json()["results"] == []


# ============================================================================
# integrations/telegram_routes.py
# ============================================================================

from integrations import telegram_routes as tgr


@pytest.fixture
def telegram_client(monkeypatch):
    monkeypatch.setenv("ATOM_TELEGRAM_WEBHOOK_SECRET", "sekrit")
    app = FastAPI()
    app.include_router(tgr.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="u1")
    app.dependency_overrides[get_db] = lambda: _db()
    return TestClient(app)


@pytest.fixture
def tg_integration():
    with patch.object(tgr, "atom_telegram_integration") as it:
        it.get_service_status = AsyncMock(return_value={"status": "active"})
        it.get_intelligent_workspaces = AsyncMock(return_value=[{"id": 1}])
        it.send_message_with_keyboard = AsyncMock(
            return_value={"success": True})
        it.edit_message_keyboard = AsyncMock(return_value={"success": True})
        it.answer_callback_query = AsyncMock(return_value={"success": True})
        it.answer_inline_query = AsyncMock(return_value={"success": True})
        it.send_chat_action = AsyncMock(return_value={"success": True})
        it.send_intelligent_message = AsyncMock(
            return_value={"success": True})
        it.send_photo = AsyncMock(return_value={"success": True})
        it.send_poll = AsyncMock(return_value={"success": True})
        it.get_chat_info = AsyncMock(return_value={"success": True})
        it.handle_callback_query = AsyncMock()
        it.handle_inline_query = AsyncMock()
        yield it


SECRET_HDR = {"X-Telegram-Bot-Api-Secret-Token": "sekrit"}


class TestTelegramRoutes:
    def test_webhook_auth_failures(self, telegram_client):
        c = telegram_client
        assert c.post("/api/telegram/webhook", json={}).status_code == 401
        assert c.post("/api/telegram/webhook", json={},
                      headers=SECRET_HDR).status_code in (200, 400)

    def test_webhook_no_secret(self, monkeypatch):
        monkeypatch.delenv("ATOM_TELEGRAM_WEBHOOK_SECRET", raising=False)
        monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET_TOKEN", raising=False)
        app = FastAPI()
        app.include_router(tgr.router)
        c = TestClient(app)
        assert c.post("/api/telegram/webhook", json={}).status_code == 401

    def test_webhook_callback_inline_and_plain(self, telegram_client,
                                               tg_integration):
        c = telegram_client
        r = c.post("/api/telegram/webhook", json={
            "callback_query": {"id": "cb1"}},
            headers={**SECRET_HDR, "Content-Type": "application/json"})
        assert r.json().get("callback_query_id") == "cb1"
        r = c.post("/api/telegram/webhook",
                   json={"inline_query": {"id": "iq1"}}, headers=SECRET_HDR)
        assert r.json().get("inline_query_id") == "iq1"
        r = c.post("/api/telegram/webhook", json={"update_id": 1},
                   headers=SECRET_HDR)
        assert r.json()["status"] == "ok"

    def test_webhook_invalid_json(self, telegram_client):
        r = telegram_client.post(
            "/api/telegram/webhook", content=b"not-json",
            headers={**SECRET_HDR, "Content-Type": "application/json"})
        assert r.status_code == 400

    def test_webhook_message_flow(self, telegram_client):
        gov = MagicMock()
        gov.verify_and_rate_limit = AsyncMock(
            return_value={"sender_id": "s1"})
        gov.check_permissions = AsyncMock()
        gov.log_to_audit_trail = AsyncMock()
        bridge = MagicMock()
        bridge.process_incoming_message = AsyncMock()
        with patch.object(tgr, "IMGovernanceService", return_value=gov), \
                patch.object(tgr, "universal_webhook_bridge", bridge):
            r = telegram_client.post("/api/telegram/webhook", json={
                "message": {"chat": {"id": 1}, "text": "hi"}},
                headers=SECRET_HDR)
            assert r.json()["status"] == "ok"
            # verify raises HTTPException -> re-raised
            gov.verify_and_rate_limit = AsyncMock(
                side_effect=HTTPException(429, "rate"))
            assert telegram_client.post(
                "/api/telegram/webhook",
                json={"message": {"text": "hi"}},
                headers=SECRET_HDR).status_code == 429
            # permission failure -> audit + re-raise
            gov.verify_and_rate_limit = AsyncMock(
                return_value={"sender_id": "s1"})
            gov.check_permissions = AsyncMock(
                side_effect=HTTPException(403, "no"))
            assert telegram_client.post(
                "/api/telegram/webhook",
                json={"message": {"text": "hi"}},
                headers=SECRET_HDR).status_code == 403
            # bridge failure -> audit + 500
            gov.check_permissions = AsyncMock()
            bridge.process_incoming_message = AsyncMock(
                side_effect=RuntimeError("x"))
            assert telegram_client.post(
                "/api/telegram/webhook",
                json={"message": {"text": "hi"}},
                headers=SECRET_HDR).status_code == 500

    def test_health_status_workspaces(self, telegram_client, tg_integration):
        c = telegram_client
        assert c.get("/api/telegram/health").json()["status"] == "healthy"
        tg_integration.get_service_status = AsyncMock(
            return_value={"status": "inactive"})
        assert c.get("/api/telegram/health").json()["status"] == "inactive"
        tg_integration.get_service_status = AsyncMock(
            side_effect=RuntimeError("x"))
        assert c.get("/api/telegram/health").json()["status"] == "unhealthy"
        tg_integration.get_service_status = AsyncMock(
            return_value={"status": "active"})
        assert c.get("/api/telegram/status").json()["status"] == "active"
        assert c.get("/api/telegram/workspaces/1").json() == [{"id": 1}]

    async def test_keyboard_endpoints(self, telegram_client, tg_integration):
        c = telegram_client
        r = c.post("/api/telegram/send-keyboard", json={
            "chat_id": 1, "text": "t",
            "keyboard": [[{"text": "b", "callback_data": "d"}]]})
        assert r.json()["success"] is True
        tg_integration.send_message_with_keyboard = AsyncMock(
            return_value={"success": False, "error": "e"})
        assert c.post("/api/telegram/send-keyboard", json={
            "chat_id": 1, "text": "t",
            "keyboard": []}).status_code == 500
        # edit-keyboard: invoke the async endpoint directly (nested query
        # list does not round-trip via TestClient params cleanly)
        res = await tgr.edit_message_keyboard(
            chat_id=1, message_id=2, keyboard=[[{"text": "b"}]],
            current_user=SimpleNamespace(id="u1"))
        assert res["success"] is True
        tg_integration.edit_message_keyboard = AsyncMock(
            return_value={"success": False, "error": "e"})
        with pytest.raises(HTTPException):
            await tgr.edit_message_keyboard(
                chat_id=1, message_id=2, keyboard=[],
                current_user=SimpleNamespace(id="u1"))
        tg_integration.edit_message_keyboard = AsyncMock(
            return_value={"success": True})
        r = c.post("/api/telegram/answer-callback", params={
            "callback_query_id": "cb", "text": "t", "show_alert": True})
        assert r.json()["success"] is True
        tg_integration.answer_callback_query = AsyncMock(
            return_value={"success": False, "error": "e"})
        assert c.post("/api/telegram/answer-callback", params={
            "callback_query_id": "cb"}).status_code == 500

    def test_inline_and_chataction(self, telegram_client, tg_integration):
        c = telegram_client
        r = c.post("/api/telegram/answer-inline", json={
            "inline_query_id": "q", "results": [{"type": "article"}]})
        assert r.json()["success"] is True
        tg_integration.answer_inline_query = AsyncMock(
            return_value={"success": False, "error": "e"})
        assert c.post("/api/telegram/answer-inline", json={
            "inline_query_id": "q",
            "results": []}).status_code == 500
        r = c.post("/api/telegram/send-chat-action", json={
            "chat_id": 1, "action": "typing", "progress": 10})
        assert r.json()["success"] is True
        tg_integration.send_chat_action = AsyncMock(
            return_value={"success": False, "error": "e"})
        assert c.post("/api/telegram/send-chat-action", json={
            "chat_id": 1, "action": "typing"}).status_code == 500

    def test_message_endpoints(self, telegram_client, tg_integration):
        c = telegram_client
        r = c.post("/api/telegram/send", json={
            "channel_id": 1, "message": "m", "parse_mode": "Markdown"})
        assert r.json()["success"] is True
        tg_integration.send_intelligent_message = AsyncMock(
            return_value={"success": False, "error": "e"})
        assert c.post("/api/telegram/send", json={
            "channel_id": 1, "message": "m"}).status_code == 500
        r = c.post("/api/telegram/send-photo", json={
            "chat_id": 1, "photo": "http://p", "caption": "c"})
        assert r.json()["success"] is True
        tg_integration.send_photo = AsyncMock(
            return_value={"success": False, "error": "e"})
        assert c.post("/api/telegram/send-photo", json={
            "chat_id": 1, "photo": "p"}).status_code == 500
        r = c.post("/api/telegram/send-poll", json={
            "chat_id": 1, "question": "q", "options": ["a", "b"]})
        assert r.json()["success"] is True
        tg_integration.send_poll = AsyncMock(
            return_value={"success": False, "error": "e"})
        assert c.post("/api/telegram/send-poll", json={
            "chat_id": 1, "question": "q",
            "options": ["a"]}).status_code == 500
        r = c.post("/api/telegram/get-chat-info/1")
        assert r.json()["success"] is True
        tg_integration.get_chat_info = AsyncMock(
            return_value={"success": False, "error": "e"})
        assert c.post("/api/telegram/get-chat-info/1").status_code == 500

    def test_capabilities(self, telegram_client):
        r = telegram_client.get("/api/telegram/capabilities")
        assert r.json()["platform"] == "Telegram"


# ============================================================================
# integrations/mailchimp_service.py
# ============================================================================

from integrations.mailchimp_service import MailchimpService


def _mc():
    return MailchimpService(tenant_id="t1", config={"client_id": "ci",
                                                    "client_secret": "cs"})


class TestMailchimpService:
    def test_static(self):
        s = _mc()
        assert s.get_capabilities()["supports_webhooks"] is True
        assert s.health_check()["healthy"] is True
        assert s._get_base_url("us1").startswith("https://us1.")
        assert s._get_headers("tk")["Authorization"] == "Bearer tk"

    async def test_close(self):
        s = _mc()
        s.client.aclose = AsyncMock()
        await s.close()
        s.client.aclose.assert_awaited()

    async def test_http_methods(self):
        s = _mc()
        s.http.post = AsyncMock(return_value=_ok({"access_token": "at"}))
        assert (await s.exchange_token("c", "http://cb"))["access_token"] \
            == "at"
        s.http.get = AsyncMock(return_value=_ok({"dc": "us1"}))
        assert (await s.get_metadata("tk"))["dc"] == "us1"
        s.http.get = AsyncMock(return_value=_ok({"lists": [{"id": "l"}]}))
        assert await s.get_audiences("tk", "us1") == [{"id": "l"}]
        s.http.get = AsyncMock(return_value=_ok({"campaigns": [{"id": "c"}]}))
        assert await s.get_campaigns("tk", "us1", status="sent") == [
            {"id": "c"}]
        s.http.get = AsyncMock(return_value=_ok({"account_name": "A"}))
        assert (await s.get_account_info("tk", "us1"))["account_name"] == "A"
        # http errors propagate
        s.http.get = AsyncMock(return_value=_hresp(500, {}))
        with patch.object(httpx.Response, "raise_for_status",
                          side_effect=httpx.HTTPError("x")):
            with pytest.raises(Exception):
                await s.get_audiences("tk", "us1")

    async def test_execute_operation(self):
        s = _mc()
        s.get_audiences = AsyncMock(return_value=[1])
        s.get_campaigns = AsyncMock(return_value=[2])
        s.get_account_info = AsyncMock(return_value={"a": 1})
        assert (await s.execute_operation(
            "get_audiences",
            {"access_token": "t", "server_prefix": "us1"}))["success"]
        assert (await s.execute_operation(
            "get_campaigns",
            {"access_token": "t", "server_prefix": "us1",
             "status": "sent"}))["success"]
        assert (await s.execute_operation(
            "get_account_info",
            {"access_token": "t", "server_prefix": "us1"}))["success"]
        r = await s.execute_operation("nope", {})
        assert r["success"] is False
        s.get_audiences = AsyncMock(side_effect=RuntimeError("x"))
        r = await s.execute_operation("get_audiences", {})
        assert r["success"] is False

    async def test_sync_and_full_sync(self, monkeypatch):
        s = _mc()
        db = _db(first=None)
        monkeypatch.setattr("core.database.SessionLocal",
                            MagicMock(return_value=db))
        # no credentials -> counts stay 0
        assert (await s.sync_to_postgres_cache("ws")) == \
            {"success": True, "metrics_synced": 2}
        kwargs = db.query.return_value.filter_by.call_args[1]
        assert "workspace_id" in kwargs and "tenant_id" not in kwargs
        # with credentials
        s.get_audiences = AsyncMock(return_value=[{"id": 1}])
        s.get_campaigns = AsyncMock(return_value=[{"id": 1},
                                                  {"id": 2}])
        assert (await s.sync_to_postgres_cache("ws", "tk", "us1"))[
            "metrics_synced"] == 2
        # credential fetch failure swallowed
        s.get_audiences = AsyncMock(side_effect=RuntimeError("x"))
        s.get_campaigns = AsyncMock(side_effect=RuntimeError("x"))
        assert (await s.sync_to_postgres_cache("ws", "tk", "us1"))[
            "success"] is True
        # existing metrics updated
        db.query.return_value.filter_by.return_value.first.return_value = \
            MagicMock()
        assert (await s.sync_to_postgres_cache("ws"))["metrics_synced"] == 2
        # commit failure
        db.commit = MagicMock(side_effect=RuntimeError("x"))
        assert (await s.sync_to_postgres_cache("ws"))["success"] is False
        assert db.rollback.called
        monkeypatch.setattr("core.database.SessionLocal",
                            MagicMock(side_effect=RuntimeError("db")))
        assert (await s.sync_to_postgres_cache("ws"))["success"] is False
        s.sync_to_postgres_cache = AsyncMock(return_value={"success": True})
        r = await s.full_sync("ws", "tk", "us1")
        assert r["success"] and r["workspace_id"] == "ws"


# ============================================================================
# integrations/xero_service.py
# ============================================================================

from integrations.xero_service import XeroService


def _xero():
    return XeroService(tenant_id="t1",
                       config={"client_id": "ci", "client_secret": "cs",
                               "access_token": "at", "xero_tenant_id": "xt"})


class TestXeroService:
    def test_headers_and_static(self):
        s = _xero()
        h = s._get_headers("tk")
        assert h["Authorization"] == "Bearer tk"
        assert "Xero-tenant-id" not in h
        assert s._get_headers("tk", "xt")["Xero-tenant-id"] == "xt"
        assert s.get_capabilities()["supports_webhooks"] is False
        assert s.health_check()["healthy"] is True
        assert XeroService(tenant_id="t",
                           config={}).health_check()["healthy"] is False

    async def test_exchange_token(self):
        s = _xero()
        s.client.post = AsyncMock(return_value=_ok({"access_token": "at"}))
        assert (await s.exchange_token("c", "http://cb"))["access_token"] \
            == "at"
        s.client.post = AsyncMock(return_value=_hresp(500, {}))
        with patch.object(httpx.Response, "raise_for_status",
                          side_effect=httpx.HTTPError("x")):
            with pytest.raises(HTTPException) as ei:
                await s.exchange_token("c", "http://cb")
            assert ei.value.status_code == 400

    async def test_get_tenants(self):
        s = _xero()
        s.client.get = AsyncMock(return_value=_ok([{"tenantId": "t"}]))
        assert await s.get_tenants("tk") == [{"tenantId": "t"}]
        s.client.get = AsyncMock(side_effect=RuntimeError("net"))
        with pytest.raises(HTTPException):
            await s.get_tenants("tk")

    async def test_get_invoices_contacts(self):
        s = _xero()
        s.client.get = AsyncMock(return_value=_ok(
            {"Invoices": [{"id": i} for i in range(30)]}))
        r = await s.get_invoices("tk", limit=5)
        assert len(r) == 5
        # default tenant id from config
        s.client.get = AsyncMock(return_value=_ok({"Invoices": []}))
        await s.get_invoices("tk")
        hdrs = s.client.get.call_args[1]["headers"]
        assert hdrs["Xero-tenant-id"] == "xt"
        s.client.get = AsyncMock(return_value=_ok(
            {"Contacts": [{"id": i} for i in range(30)]}))
        assert len(await s.get_contacts("tk", limit=3)) == 3
        s.client.get = AsyncMock(side_effect=RuntimeError("net"))
        with pytest.raises(HTTPException):
            await s.get_invoices("tk")
        with pytest.raises(HTTPException):
            await s.get_contacts("tk")

    async def test_execute_operation(self):
        s = _xero()
        s.get_tenants = AsyncMock(return_value=[1])
        s.get_invoices = AsyncMock(return_value=[1])
        s.get_contacts = AsyncMock(return_value=[1])
        s.full_sync = AsyncMock(return_value={"success": True})
        assert (await s.execute_operation("get_tenants", {}))["success"]
        assert (await s.execute_operation(
            "get_invoices", {"access_token": "a",
                             "xero_tenant_id": "x"}))["success"]
        assert (await s.execute_operation("get_contacts", {}))["success"]
        assert (await s.execute_operation(
            "full_sync", {"user_id": "u"}))["success"]
        r = await s.execute_operation("nope", {})
        assert r["success"] is False
        s.get_tenants = AsyncMock(side_effect=RuntimeError("x"))
        assert (await s.execute_operation("get_tenants", {}))[
            "success"] is False

    async def test_sync_and_full_sync(self, monkeypatch):
        s = _xero()
        s.get_invoices = AsyncMock(return_value=[{"id": 1}])
        s.get_contacts = AsyncMock(return_value=[{"id": 1}, {"id": 2}])
        db = _db(first=None)
        monkeypatch.setattr("core.database.SessionLocal",
                            MagicMock(return_value=db))
        assert (await s.sync_to_postgres_cache("ws", "tk")) == \
            {"success": True, "metrics_synced": 2}
        kwargs = db.query.return_value.filter_by.call_args[1]
        assert "workspace_id" in kwargs and "tenant_id" not in kwargs
        db.query.return_value.filter_by.return_value.first.return_value = \
            MagicMock()
        assert (await s.sync_to_postgres_cache("ws", "tk"))[
            "metrics_synced"] == 2
        db.commit = MagicMock(side_effect=RuntimeError("x"))
        assert (await s.sync_to_postgres_cache("ws", "tk"))[
            "success"] is False
        assert db.rollback.called
        # fetch failure (get_invoices raises HTTPException) -> outer catch
        s.get_invoices = AsyncMock(side_effect=HTTPException(500, "x"))
        assert (await s.sync_to_postgres_cache("ws", "tk"))[
            "success"] is False
        s.sync_to_postgres_cache = AsyncMock(return_value={"success": True})
        r = await s.full_sync("ws", "tk")
        assert r["success"] and r["user_id"] == "ws"
