# -*- coding: utf-8 -*-
"""Coverage wave 101 — integrations/openclaw_service (OpenClawService).

Standalone, fully mocked (httpx.AsyncClient methods + requests.post), zero
network, zero LLM spend. Follows wave-95/97 conventions.

Covers: __init__ (config passthrough, env-independent), get_capabilities,
execute_operation (tenant mismatch, missing params, send_message success,
send_message error/skipped status, unsupported op, exception -> generic),
close, _get_headers (with/without api_key), send_message (no webhook_url ->
skipped fail-closed, success payload + thread_ts, HTTPError -> generic
message), health_check (not configured, reachable, error status,
exception -> generic error).

Bugs fixed (TDD RED -> GREEN):
- execute_operation leaked str(e); now generic envelope.
- send_message returned the raw httpx exception text in the result payload
  (which execute_operation then surfaced as the operation error); now a
  generic message with the detail kept server-side in the log.
- health_check exception branch leaked str(e) into the response; now generic.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from integrations.openclaw_service import OpenClawService


def _svc(config=None):
    return OpenClawService(tenant_id="t1", config=config or {})


class TestInit:
    def test_config_passthrough(self):
        svc = _svc({"openclaw_webhook_url": "https://claw.example/hook",
                    "openclaw_api_key": "k123"})
        assert svc.webhook_url == "https://claw.example/hook"
        assert svc.api_key == "k123"
        assert svc.tenant_id == "t1"

    def test_missing_config(self):
        svc = _svc()
        assert svc.webhook_url is None
        assert svc.api_key is None

    def test_explicit_none_config(self):
        svc = OpenClawService(tenant_id="t1", config=None)
        assert svc.webhook_url is None


class TestCapabilities:
    def test_operations(self):
        caps = _svc().get_capabilities()
        assert caps["operations"] == [{"id": "send_message", "name": "Send Message"}]
        assert caps["required_params"] == ["webhook_url"]
        assert caps["rate_limits"] == {"requests_per_minute": 60}
        assert caps["supports_webhooks"] is True


class TestExecuteOperation:
    async def test_tenant_mismatch_fails_closed(self):
        svc = _svc()
        out = await svc.execute_operation("send_message",
                                          {"recipient_id": "r", "content": "c"},
                                          context={"tenant_id": "other"})
        assert out["success"] is False
        assert out["error"] == "Tenant mismatch validation failed"

    async def test_tenant_match_proceeds(self):
        svc = _svc()
        svc.send_message = AsyncMock(return_value={"status": "sent", "message": "ok"})
        out = await svc.execute_operation("send_message",
                                          {"recipient_id": "r", "content": "c"},
                                          context={"tenant_id": "t1"})
        assert out["success"] is True

    async def test_missing_params(self):
        out = await _svc().execute_operation("send_message", {})
        assert out["success"] is False
        assert out["error"] == "Missing recipient_id or content"

    async def test_send_message_success(self):
        svc = _svc()
        svc.send_message = AsyncMock(return_value={"status": "sent", "message": "ok"})
        out = await svc.execute_operation("send_message",
                                          {"recipient_id": "r", "content": "c", "thread_ts": "t0"})
        assert out["success"] is True
        assert out["result"] == {"status": "sent", "message": "ok"}
        svc.send_message.assert_awaited_once_with("r", "c", "t0")

    async def test_send_message_error_status(self):
        svc = _svc()
        svc.send_message = AsyncMock(return_value={"status": "error", "message": "boom"})
        out = await svc.execute_operation("send_message", {"recipient_id": "r", "content": "c"})
        assert out["success"] is False
        assert out["error"] == "boom"

    async def test_send_message_skipped_status(self):
        svc = _svc()
        svc.send_message = AsyncMock(return_value={"status": "skipped", "reason": "config_missing"})
        out = await svc.execute_operation("send_message", {"recipient_id": "r", "content": "c"})
        assert out["success"] is False

    async def test_unsupported_operation_generic(self):
        out = await _svc().execute_operation("nope", {})
        assert out["success"] is False
        assert out["error"] == "OpenClaw operation failed"

    async def test_exception_generic_envelope(self):
        """RED: exception path leaked str(e); must be generic."""
        svc = _svc()
        svc.send_message = AsyncMock(side_effect=RuntimeError("secret-detail"))
        out = await svc.execute_operation("send_message", {"recipient_id": "r", "content": "c"})
        assert out["success"] is False
        assert "secret-detail" not in out["error"]
        assert out["error"] == "OpenClaw operation failed"


class TestClose:
    async def test_closes_client(self):
        svc = _svc()
        svc.client = AsyncMock()
        await svc.close()
        svc.client.aclose.assert_awaited_once()


class TestHeaders:
    def test_with_api_key(self):
        svc = _svc({"openclaw_api_key": "k1"})
        h = svc._get_headers()
        assert h["Authorization"] == "Bearer k1"
        assert h["Content-Type"] == "application/json"

    def test_without_api_key(self):
        h = _svc()._get_headers()
        assert "Authorization" not in h


class TestSendMessage:
    async def test_no_webhook_url_skips(self):
        svc = _svc()
        out = await svc.send_message("r", "c")
        assert out == {"status": "skipped", "reason": "configuration_missing"}

    async def test_success_payload(self):
        svc = _svc({"openclaw_webhook_url": "https://claw/hook", "openclaw_api_key": "k1"})
        svc.client.post = AsyncMock(return_value=httpx.Response(
            200, json={"status": "sent"},
            request=httpx.Request("POST", "https://claw/hook")))
        out = await svc.send_message("r", "c")
        assert out == {"status": "sent"}
        payload = svc.client.post.call_args.kwargs["json"]
        assert payload["type"] == "message"
        assert payload["recipient_id"] == "r"
        assert payload["content"] == "c"
        assert "timestamp" in payload
        assert svc.client.post.call_args.kwargs["headers"]["Authorization"] == "Bearer k1"

    async def test_success_with_thread_ts(self):
        svc = _svc({"openclaw_webhook_url": "https://claw/hook"})
        svc.client.post = AsyncMock(return_value=httpx.Response(
            200, json={}, request=httpx.Request("POST", "https://claw/hook")))
        await svc.send_message("r", "c", thread_ts="t0")
        assert svc.client.post.call_args.kwargs["json"]["thread_ts"] == "t0"

    async def test_http_error_generic_message(self):
        """RED: returned raw httpx error text as the public message; must be
        generic (detail stays in server-side log)."""
        svc = _svc({"openclaw_webhook_url": "https://claw/hook"})
        svc.client.post = AsyncMock(side_effect=httpx.ConnectError("net-secret"))
        out = await svc.send_message("r", "c")
        assert out["status"] == "error"
        assert "net-secret" not in out["message"]
        assert out["message"] == "Failed to send message to OpenClaw"

    async def test_http_500_error_generic_message(self):
        svc = _svc({"openclaw_webhook_url": "https://claw/hook"})
        svc.client.post = AsyncMock(return_value=httpx.Response(
            500, request=httpx.Request("POST", "https://claw/hook")))
        out = await svc.send_message("r", "c")
        assert out["status"] == "error"
        assert "Failed to send message to OpenClaw" in out["message"]


class TestHealthCheck:
    def test_not_configured(self):
        out = _svc().health_check()
        assert out["healthy"] is False
        assert out["status"] == "not_configured"
        assert out["service"] == "openclaw"

    def test_reachable(self):
        svc = _svc({"openclaw_webhook_url": "https://claw/hook"})
        with patch("requests.post") as post:
            post.return_value = MagicMock(status_code=200)
            out = svc.health_check()
        assert out["healthy"] is True
        assert out["status"] == "reachable"
        assert out["status_code"] == 200
        assert post.call_args.kwargs["json"] == {"type": "ping"}
        assert post.call_args.kwargs["timeout"] == 10.0

    def test_unreachable_status_code(self):
        svc = _svc({"openclaw_webhook_url": "https://claw/hook"})
        with patch("requests.post") as post:
            post.return_value = MagicMock(status_code=503)
            out = svc.health_check()
        assert out["healthy"] is False
        assert out["status"] == "error"
        assert out["status_code"] == 503

    def test_exception_generic_error(self):
        """RED: exception branch leaked str(e); must be generic."""
        svc = _svc({"openclaw_webhook_url": "https://claw/hook"})
        with patch("requests.post", side_effect=RuntimeError("reach-secret")):
            out = svc.health_check()
        assert out["healthy"] is False
        assert out["status"] == "unreachable"
        assert "reach-secret" not in out["error"]
        assert out["error"] == "OpenClaw health check failed"
