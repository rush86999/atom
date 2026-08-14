# -*- coding: utf-8 -*-
"""Coverage wave 95 — integrations/zoom_service (ZoomService).

Standalone, fully mocked (IntegrationHTTP + httpx.Response objects), zero
network, zero LLM spend.

Covers: __init__ (config provided/empty + close), _get_headers,
get_authorization_url (with/without state), exchange_token (success stores
token, HTTPError -> 400, MISSING client credentials -> clean 400 fail-closed —
was an uncaught httpx TypeError -> 500), get_user / list_meetings /
create_meeting / delete_meeting / list_users / list_recordings (success with
optional params, no-token 401, HTTPError -> 400), get_capabilities,
health_check (healthy/unhealthy/exception path -> generic), execute_operation
(all 5 ops + unknown op + inner-exception -> generic envelope, no str(e) leak).
"""
import asyncio
import pytest
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException

from integrations.zoom_service import ZoomService


def _svc(config=None):
    svc = ZoomService(tenant_id="t1", config=config or {})
    svc.http = type("H", (), {})()  # replaced below by tests
    return svc


def _resp(status=200, payload=None):
    return httpx.Response(status, json=payload if payload is not None else {}, request=httpx.Request("GET", "http://x"))


class TestInit:
    def test_config_passthrough(self):
        svc = ZoomService(config={"client_id": "cid", "client_secret": "cs",
                                  "account_id": "acc", "access_token": "tok"})
        try:
            assert svc.client_id == "cid"
            assert svc.client_secret == "cs"
            assert svc.account_id == "acc"
            assert svc.access_token == "tok"
            assert svc.base_url == "https://api.zoom.us/v2"
            assert svc.token_url == "https://zoom.us/oauth/token"
            assert svc.tenant_id == "default"
        finally:
            import asyncio
            loop = asyncio.new_event_loop()
            loop.run_until_complete(svc.close())
            loop.close()

    def test_empty_config(self):
        svc = ZoomService()
        assert svc.client_id is None
        assert svc.access_token is None

    async def test_close(self):
        svc = ZoomService()
        await svc.client.aclose()
        assert svc.client.is_closed
        # calling close() again is harmless (httpx no-ops)
        await svc.close()


class TestHeaders:
    def test_get_headers(self):
        svc = _svc()
        h = svc._get_headers("abc")
        assert h["Authorization"] == "Bearer abc"
        assert h["Content-Type"] == "application/json"


class TestAuthUrl:
    def test_without_state(self):
        svc = _svc()
        url = svc.get_authorization_url("http://cb")
        assert url.startswith("https://zoom.us/oauth/authorize?")
        assert "client_id=None" in url
        assert "redirect_uri=http://cb" in url
        assert "response_type=code" in url
        assert "state" not in url

    def test_with_state(self):
        svc = _svc()
        url = svc.get_authorization_url("http://cb", state="s123")
        assert "state=s123" in url


class TestExchangeToken:
    async def _svc(self):
        svc = _svc({"client_id": "cid", "client_secret": "cs"})
        svc.http.post = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock()
        return svc

    async def test_success(self):
        svc = await self._svc()
        svc.http.post.return_value = _resp(200, {"access_token": "newtok", "refresh_token": "r"})
        data = await svc.exchange_token("code1", "http://cb")
        assert data["access_token"] == "newtok"
        assert svc.access_token == "newtok"
        kwargs = svc.http.post.call_args.kwargs
        assert kwargs["data"]["grant_type"] == "authorization_code"
        assert kwargs["auth"] == ("cid", "cs")

    async def test_http_error_returns_400(self):
        svc = await self._svc()
        svc.http.post.side_effect = httpx.ConnectError("boom")
        with pytest.raises(HTTPException) as ei:
            await svc.exchange_token("code1", "http://cb")
        assert ei.value.status_code == 400
        assert ei.value.detail == "Internal error"

    async def test_missing_credentials_fail_closed(self):
        """Missing client creds must produce a clean 400, not a raw httpx
        TypeError escaping as a 500.  RED: today the TypeError from
        BasicAuth((None, None)) is not an httpx.HTTPError so it escapes."""
        svc = _svc({})  # no client_id / client_secret
        svc.http.post = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
            side_effect=TypeError("sequence item 0: expected a bytes-like object, NoneType found"))
        with pytest.raises(HTTPException) as ei:
            await svc.exchange_token("code1", "http://cb")
        assert ei.value.status_code == 400
        assert "credential" in ei.value.detail.lower() or ei.value.detail == "Internal error"


class TestGetUser:
    async def test_success(self):
        svc = _svc({"access_token": "tok"})
        svc.http.get = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
            return_value=_resp(200, {"id": "me"}))
        out = await svc.get_user()
        assert out == {"id": "me"}
        assert svc.http.get.call_args.args[0] == "zoom"

    async def test_no_token_401(self):
        svc = _svc({})
        with pytest.raises(HTTPException) as ei:
            await svc.get_user()
        assert ei.value.status_code == 401

    async def test_token_param_overrides(self):
        svc = _svc({})
        svc.http.get = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
            return_value=_resp(200, {"id": "me"}))
        out = await svc.get_user(access_token="explicit")
        assert out == {"id": "me"}

    async def test_http_error_400(self):
        svc = _svc({"access_token": "tok"})
        svc.http.get = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
            side_effect=httpx.HTTPStatusError("429", request=httpx.Request("GET", "u"),
                                              response=httpx.Response(429)))
        with pytest.raises(HTTPException) as ei:
            await svc.get_user()
        assert ei.value.status_code == 400
        assert ei.value.detail == "Internal error"


class TestListMeetings:
    async def test_success(self):
        svc = _svc({"access_token": "tok"})
        svc.http.get = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
            return_value=_resp(200, {"meetings": []}))
        out = await svc.list_meetings(type="upcoming", page_size=10)
        assert out == {"meetings": []}
        kwargs = svc.http.get.call_args.kwargs
        assert kwargs["params"] == {"type": "upcoming", "page_size": 10}

    async def test_no_token_401(self):
        svc = _svc({})
        with pytest.raises(HTTPException) as ei:
            await svc.list_meetings()
        assert ei.value.status_code == 401

    async def test_http_error_400(self):
        svc = _svc({"access_token": "tok"})
        svc.http.get = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
            side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.list_meetings()
        assert ei.value.status_code == 400


class TestCreateMeeting:
    async def test_full_payload(self):
        svc = _svc({"access_token": "tok"})
        svc.http.post = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
            return_value=_resp(201, {"id": "m1"}))
        out = await svc.create_meeting("Standup", start_time="2026-01-01T10:00:00Z",
                                       duration=30, timezone="US/Pacific", agenda="sync")
        assert out == {"id": "m1"}
        payload = svc.http.post.call_args.kwargs["json"]
        assert payload["topic"] == "Standup"
        assert payload["type"] == 2
        assert payload["duration"] == 30
        assert payload["timezone"] == "US/Pacific"
        assert payload["start_time"] == "2026-01-01T10:00:00Z"
        assert payload["agenda"] == "sync"

    async def test_minimal_payload(self):
        svc = _svc({"access_token": "tok"})
        svc.http.post = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
            return_value=_resp(201, {}))
        await svc.create_meeting("Standup")
        payload = svc.http.post.call_args.kwargs["json"]
        assert "start_time" not in payload
        assert "agenda" not in payload
        assert payload["timezone"] == "UTC"

    async def test_no_token_401(self):
        svc = _svc({})
        with pytest.raises(HTTPException) as ei:
            await svc.create_meeting("x")
        assert ei.value.status_code == 401

    async def test_http_error_400(self):
        svc = _svc({"access_token": "tok"})
        svc.http.post = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
            side_effect=httpx.TimeoutException("slow"))
        with pytest.raises(HTTPException) as ei:
            await svc.create_meeting("x")
        assert ei.value.status_code == 400


class TestDeleteMeeting:
    async def test_success(self):
        svc = _svc({"access_token": "tok"})
        svc.http.delete = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
            return_value=_resp(204))
        out = await svc.delete_meeting("mid1")
        assert out == {"ok": True, "message": "Meeting deleted"}
        assert svc.http.delete.call_args.args[1] == "https://api.zoom.us/v2/meetings/mid1"

    async def test_no_token_401(self):
        svc = _svc({})
        with pytest.raises(HTTPException) as ei:
            await svc.delete_meeting("mid1")
        assert ei.value.status_code == 401

    async def test_http_error_400(self):
        svc = _svc({"access_token": "tok"})
        svc.http.delete = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
            side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.delete_meeting("mid1")
        assert ei.value.status_code == 400


class TestCapabilities:
    def test_operations(self):
        svc = _svc()
        caps = svc.get_capabilities()
        ops = {o["id"] for o in caps["operations"]}
        assert ops == {"create_meeting", "list_meetings", "delete_meeting",
                       "list_users", "list_recordings"}
        assert caps["required_params"] == ["client_id", "client_secret", "account_id"]
        assert caps["supports_webhooks"] is True


class TestHealthCheck:
    def test_healthy(self):
        svc = _svc({"client_id": "cid", "client_secret": "cs"})
        out = asyncio.run(svc.health_check())
        assert out["healthy"] is True
        assert "operational" in out["message"]
        assert "last_check" in out

    def test_unhealthy_missing_client_id(self):
        svc = _svc({"client_secret": "cs"})
        out = asyncio.run(svc.health_check())
        assert out["healthy"] is False
        assert "not configured" in out["message"]

    def test_exception_path_generic(self):
        svc = _svc()
        with __import__("unittest.mock", fromlist=["patch"]).patch(
                "integrations.zoom_service.datetime") as dt:
            dt.now.side_effect = RuntimeError("clock broke")
            out = asyncio.run(svc.health_check())
        assert out["healthy"] is False
        assert out["message"] == "Zoom health check failed"


class TestExecuteOperation:
    async def test_create_meeting_op(self):
        svc = _svc({"access_token": "tok"})
        svc.create_meeting = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
            return_value={"id": "m"})
        out = await svc.execute_operation("create_meeting", {"topic": "t"})
        assert out["success"] is True
        assert out["result"] == {"id": "m"}
        assert out["details"]["tenant_id"] == "t1"

    async def test_list_meetings_op(self):
        svc = _svc({"access_token": "tok"})
        svc.list_meetings = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
            return_value={"meetings": []})
        out = await svc.execute_operation("list_meetings", {})
        assert out["success"] is True

    async def test_delete_meeting_op(self):
        svc = _svc({"access_token": "tok"})
        svc.delete_meeting = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
            return_value={"ok": True})
        out = await svc.execute_operation("delete_meeting", {"meeting_id": "m"})
        assert out["success"] is True

    async def test_list_users_op(self):
        svc = _svc({"access_token": "tok"})
        svc.list_users = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
            return_value={"users": []})
        out = await svc.execute_operation("list_users", {})
        assert out["success"] is True

    async def test_list_recordings_op(self):
        svc = _svc({"access_token": "tok"})
        svc.list_recordings = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
            return_value={"recording_files": []})
        out = await svc.execute_operation("list_recordings", {})
        assert out["success"] is True

    async def test_unknown_operation(self):
        svc = _svc()
        out = await svc.execute_operation("nope", {})
        assert out["success"] is False
        assert "Unknown operation" in out["error"]

    async def test_inner_exception_generic_envelope(self):
        svc = _svc({"access_token": "tok"})
        svc.create_meeting = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
            side_effect=RuntimeError("secret-detail"))
        out = await svc.execute_operation("create_meeting", {})
        assert out["success"] is False
        assert "secret-detail" not in out["error"]
        assert out["error"] == "Zoom operation failed"


class TestListUsers:
    async def test_success(self):
        svc = _svc({"access_token": "tok"})
        svc.http.get = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
            return_value=_resp(200, {"users": [{"id": "u1"}]}))
        out = await svc.list_users(status="pending", page_size=5, page_number=2)
        assert out == {"users": [{"id": "u1"}]}
        assert svc.http.get.call_args.kwargs["params"] == {
            "status": "pending", "page_size": 5, "page_number": 2}

    async def test_no_token_401(self):
        svc = _svc({})
        with pytest.raises(HTTPException) as ei:
            await svc.list_users()
        assert ei.value.status_code == 401

    async def test_http_error_400(self):
        svc = _svc({"access_token": "tok"})
        svc.http.get = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
            side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.list_users()
        assert ei.value.status_code == 400


class TestListRecordings:
    async def test_with_dates(self):
        svc = _svc({"access_token": "tok"})
        svc.http.get = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
            return_value=_resp(200, {"recording_files": []}))
        out = await svc.list_recordings(from_date="2026-01-01", to_date="2026-01-31")
        assert out == {"recording_files": []}
        params = svc.http.get.call_args.kwargs["params"]
        assert params["from"] == "2026-01-01"
        assert params["to"] == "2026-01-31"
        assert params["page_size"] == 30

    async def test_without_dates(self):
        svc = _svc({"access_token": "tok"})
        svc.http.get = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
            return_value=_resp(200, {}))
        await svc.list_recordings()
        assert svc.http.get.call_args.kwargs["params"] == {"page_size": 30}

    async def test_no_token_401(self):
        svc = _svc({})
        with pytest.raises(HTTPException) as ei:
            await svc.list_recordings()
        assert ei.value.status_code == 401

    async def test_http_error_400(self):
        svc = _svc({"access_token": "tok"})
        svc.http.get = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
            side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.list_recordings()
        assert ei.value.status_code == 400
