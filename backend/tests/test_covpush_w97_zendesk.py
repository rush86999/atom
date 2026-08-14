# -*- coding: utf-8 -*-
"""Coverage wave 97 — integrations/zendesk_service (ZendeskService).

Standalone, fully mocked (IntegrationHTTP + httpx.Response objects), zero
network, zero LLM spend. Follows the wave-95 zoom/linear conventions.

Covers: __init__ (config + env fallback for subdomain/access_token),
close, _get_headers, get_authorization_url (with/without state),
exchange_token (success stores token, HTTPError -> 400), get_tickets /
get_ticket / create_ticket (with/without requester) / search_tickets /
get_users (success, no-token 401, HTTPError -> 400), health_check
(healthy/unhealthy/exception -> generic message, NO str(e) leak),
execute_operation (all 5 ops + unknown op + inner-exception -> generic
envelope, no str(e) leak).

Bugs fixed (TDD RED -> GREEN):
- ZendeskService never implemented the IntegrationService ABC
  get_capabilities, so the class could not be instantiated at all
  (TypeError). Added get_capabilities().
- health_check exception path leaked str(e); now generic message.
- execute_operation exception path leaked str(e); now generic envelope.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException

from integrations.zendesk_service import ZendeskService


def _svc(config=None):
    return ZendeskService(tenant_id="t1", config=config or {})


def _resp(status=200, payload=None):
    return httpx.Response(status, json=payload if payload is not None else {},
                          request=httpx.Request("GET", "http://x"))


class TestInit:
    def test_config_passthrough(self):
        svc = _svc({"client_id": "cid", "client_secret": "cs",
                    "subdomain": "acme", "access_token": "tok"})
        assert svc.client_id == "cid"
        assert svc.client_secret == "cs"
        assert svc.subdomain == "acme"
        assert svc.access_token == "tok"
        assert svc.base_url == "https://acme.zendesk.com/api/v2"
        assert svc.oauth_url == "https://acme.zendesk.com/oauth"

    def test_env_fallbacks(self, monkeypatch):
        monkeypatch.setenv("ZENDESK_SUBDOMAIN", "envco")
        monkeypatch.setenv("ZENDESK_ACCESS_TOKEN", "env-tok")
        svc = ZendeskService()
        assert svc.subdomain == "envco"
        assert svc.access_token == "env-tok"
        assert svc.base_url == "https://envco.zendesk.com/api/v2"

    async def test_close(self):
        svc = _svc()
        svc.client.aclose = AsyncMock()
        await svc.close()
        svc.client.aclose.assert_awaited_once()


class TestCapabilities:
    def test_operations(self):
        """RED: ZendeskService never implemented the ABC get_capabilities,
        so the class was uninstantiable (TypeError)."""
        svc = _svc()
        caps = svc.get_capabilities()
        assert set(caps["operations"]) == {
            "get_tickets", "get_ticket", "create_ticket", "search_tickets", "get_users"}
        assert "subdomain" in caps["required_params"]
        assert "access_token" in caps["required_params"]


class TestHeaders:
    def test_get_headers(self):
        svc = _svc()
        h = svc._get_headers("abc")
        assert h["Authorization"] == "Bearer abc"
        assert h["Content-Type"] == "application/json"


class TestAuthUrl:
    def test_without_state(self):
        svc = _svc({"subdomain": "acme"})
        url = svc.get_authorization_url("http://cb")
        assert url.startswith("https://acme.zendesk.com/oauth/authorizations/new?")
        assert "response_type=code" in url
        assert "redirect_uri=http://cb" in url
        assert "scope=read write" in url
        assert "state" not in url

    def test_with_state(self):
        svc = _svc({"subdomain": "acme"})
        url = svc.get_authorization_url("http://cb", state="s1")
        assert "state=s1" in url


class TestExchangeToken:
    async def test_success(self):
        svc = _svc({"client_id": "cid", "client_secret": "cs", "subdomain": "acme"})
        svc.http.post = AsyncMock(return_value=_resp(200, {"access_token": "newtok"}))
        data = await svc.exchange_token("code1", "http://cb")
        assert data["access_token"] == "newtok"
        assert svc.access_token == "newtok"
        body = svc.http.post.call_args.kwargs["data"]
        assert body["grant_type"] == "authorization_code"
        assert body["client_id"] == "cid"
        assert body["client_secret"] == "cs"
        assert body["redirect_uri"] == "http://cb"
        assert body["scope"] == "read write"

    async def test_http_error_returns_400(self):
        svc = _svc({"client_id": "cid", "client_secret": "cs", "subdomain": "acme"})
        svc.http.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
        with pytest.raises(HTTPException) as ei:
            await svc.exchange_token("code1", "http://cb")
        assert ei.value.status_code == 400
        assert ei.value.detail == "Internal error"


class TestGetTickets:
    async def test_success(self):
        svc = _svc({"access_token": "tok", "subdomain": "acme"})
        svc.http.get = AsyncMock(return_value=_resp(200, {"tickets": [{"id": 1}]}))
        out = await svc.get_tickets(per_page=50, sort_by="updated_at", sort_order="asc")
        assert out == [{"id": 1}]
        kwargs = svc.http.get.call_args.kwargs
        assert kwargs["params"] == {"per_page": 50, "sort_by": "updated_at", "sort_order": "asc"}
        assert kwargs["headers"]["Authorization"] == "Bearer tok"
        assert svc.http.get.call_args.args[1] == "https://acme.zendesk.com/api/v2/tickets.json"

    async def test_empty_response(self):
        svc = _svc({"access_token": "tok", "subdomain": "acme"})
        svc.http.get = AsyncMock(return_value=_resp(200, {}))
        assert await svc.get_tickets() == []

    async def test_no_token_401(self):
        svc = _svc({"subdomain": "acme"})
        with pytest.raises(HTTPException) as ei:
            await svc.get_tickets()
        assert ei.value.status_code == 401
        assert ei.value.detail == "Not authenticated"

    async def test_http_error_400(self):
        svc = _svc({"access_token": "tok", "subdomain": "acme"})
        svc.http.get = AsyncMock(side_effect=httpx.TimeoutException("slow"))
        with pytest.raises(HTTPException) as ei:
            await svc.get_tickets()
        assert ei.value.status_code == 400
        assert ei.value.detail == "Internal error"


class TestGetTicket:
    async def test_success(self):
        svc = _svc({"access_token": "tok", "subdomain": "acme"})
        svc.http.get = AsyncMock(return_value=_resp(200, {"ticket": {"id": 42}}))
        out = await svc.get_ticket(42)
        assert out == {"id": 42}
        assert svc.http.get.call_args.args[1].endswith("/tickets/42.json")

    async def test_no_token_401(self):
        svc = _svc({"subdomain": "acme"})
        with pytest.raises(HTTPException) as ei:
            await svc.get_ticket(1)
        assert ei.value.status_code == 401

    async def test_http_error_400(self):
        svc = _svc({"access_token": "tok", "subdomain": "acme"})
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.get_ticket(1)
        assert ei.value.status_code == 400


class TestCreateTicket:
    async def test_full_payload_with_requester(self):
        svc = _svc({"access_token": "tok", "subdomain": "acme"})
        svc.http.post = AsyncMock(return_value=_resp(201, {"ticket": {"id": 7}}))
        out = await svc.create_ticket("Help", "body", priority="urgent",
                                      requester_name="Alice", requester_email="a@x.com")
        assert out == {"id": 7}
        payload = svc.http.post.call_args.kwargs["json"]["ticket"]
        assert payload["subject"] == "Help"
        assert payload["comment"] == {"body": "body"}
        assert payload["priority"] == "urgent"
        assert payload["requester"] == {"name": "Alice", "email": "a@x.com"}

    async def test_minimal_payload(self):
        svc = _svc({"access_token": "tok", "subdomain": "acme"})
        svc.http.post = AsyncMock(return_value=_resp(201, {}))
        await svc.create_ticket("Help", "body")
        payload = svc.http.post.call_args.kwargs["json"]["ticket"]
        assert payload["priority"] == "normal"
        assert "requester" not in payload

    async def test_requester_name_only(self):
        svc = _svc({"access_token": "tok", "subdomain": "acme"})
        svc.http.post = AsyncMock(return_value=_resp(201, {}))
        await svc.create_ticket("Help", "body", requester_name="Bob")
        payload = svc.http.post.call_args.kwargs["json"]["ticket"]
        assert payload["requester"] == {"name": "Bob"}

    async def test_no_token_401(self):
        svc = _svc({"subdomain": "acme"})
        with pytest.raises(HTTPException) as ei:
            await svc.create_ticket("Help", "body")
        assert ei.value.status_code == 401

    async def test_http_error_400(self):
        svc = _svc({"access_token": "tok", "subdomain": "acme"})
        svc.http.post = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.create_ticket("Help", "body")
        assert ei.value.status_code == 400


class TestSearchTickets:
    async def test_success(self):
        svc = _svc({"access_token": "tok", "subdomain": "acme"})
        svc.http.get = AsyncMock(return_value=_resp(200, {"results": [{"id": 1}]}))
        out = await svc.search_tickets("bug", per_page=25)
        assert out == [{"id": 1}]
        params = svc.http.get.call_args.kwargs["params"]
        assert params["query"] == "type:ticket bug"
        assert params["per_page"] == 25

    async def test_no_token_401(self):
        svc = _svc({"subdomain": "acme"})
        with pytest.raises(HTTPException) as ei:
            await svc.search_tickets("x")
        assert ei.value.status_code == 401

    async def test_http_error_400(self):
        svc = _svc({"access_token": "tok", "subdomain": "acme"})
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.search_tickets("x")
        assert ei.value.status_code == 400


class TestGetUsers:
    async def test_success(self):
        svc = _svc({"access_token": "tok", "subdomain": "acme"})
        svc.http.get = AsyncMock(return_value=_resp(200, {"users": [{"id": 1}]}))
        out = await svc.get_users(per_page=10)
        assert out == [{"id": 1}]
        assert svc.http.get.call_args.kwargs["params"] == {"per_page": 10}

    async def test_no_token_401(self):
        svc = _svc({"subdomain": "acme"})
        with pytest.raises(HTTPException) as ei:
            await svc.get_users()
        assert ei.value.status_code == 401

    async def test_http_error_400(self):
        svc = _svc({"access_token": "tok", "subdomain": "acme"})
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.get_users()
        assert ei.value.status_code == 400


class TestHealthCheck:
    async def test_healthy(self):
        svc = _svc({"subdomain": "acme"})
        out = await svc.health_check()
        assert out["ok"] is True
        assert out["status"] == "healthy"
        assert out["service"] == "zendesk"
        assert out["version"] == "1.0.0"
        assert "timestamp" in out

    async def test_exception_path_generic(self):
        """RED: exception path leaked str(e); must be generic."""
        svc = _svc()
        with patch("integrations.zendesk_service.datetime") as dt:
            dt.now.side_effect = RuntimeError("clock-secret-detail")
            out = await svc.health_check()
        assert out["ok"] is False
        assert out["status"] == "unhealthy"
        assert "clock-secret-detail" not in out["error"]
        assert out["error"] == "Zendesk health check failed"


class TestExecuteOperation:
    async def test_get_tickets_op(self):
        svc = _svc({"access_token": "tok"})
        svc.get_tickets = AsyncMock(return_value=[])
        out = await svc.execute_operation("get_tickets", {"per_page": 5, "sort_by": "id"})
        assert out["success"] is True
        assert svc.get_tickets.call_args.kwargs["per_page"] == 5
        assert svc.get_tickets.call_args.kwargs["sort_by"] == "id"

    async def test_get_ticket_op(self):
        svc = _svc({"access_token": "tok"})
        svc.get_ticket = AsyncMock(return_value={"id": 1})
        out = await svc.execute_operation("get_ticket", {"ticket_id": 1})
        assert out["success"] is True
        assert out["result"] == {"id": 1}

    async def test_create_ticket_op(self):
        svc = _svc({"access_token": "tok"})
        svc.create_ticket = AsyncMock(return_value={"id": 1})
        out = await svc.execute_operation("create_ticket", {"subject": "S", "comment_body": "B"})
        assert out["success"] is True
        kwargs = svc.create_ticket.call_args.kwargs
        assert kwargs["subject"] == "S"
        assert kwargs["comment_body"] == "B"

    async def test_search_tickets_op(self):
        svc = _svc({"access_token": "tok"})
        svc.search_tickets = AsyncMock(return_value=[])
        out = await svc.execute_operation("search_tickets", {"query": "bug"})
        assert out["success"] is True

    async def test_get_users_op(self):
        svc = _svc({"access_token": "tok"})
        svc.get_users = AsyncMock(return_value=[])
        out = await svc.execute_operation("get_users", {})
        assert out["success"] is True

    async def test_unknown_operation(self):
        svc = _svc()
        out = await svc.execute_operation("nope", {})
        assert out["success"] is False
        assert "Unknown operation" in out["error"]

    async def test_inner_exception_generic_envelope(self):
        """RED: exception path leaked str(e); must be generic."""
        svc = _svc({"access_token": "tok"})
        svc.get_tickets = AsyncMock(side_effect=RuntimeError("secret-detail"))
        out = await svc.execute_operation("get_tickets", {})
        assert out["success"] is False
        assert "secret-detail" not in out["error"]
        assert out["error"] == "Zendesk operation failed"
