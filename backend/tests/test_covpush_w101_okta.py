# -*- coding: utf-8 -*-
"""Coverage wave 101 — integrations/okta_service (OktaService).

Standalone, fully mocked (httpx.AsyncClient methods), zero network, zero LLM
spend. Follows wave-95/97 conventions.

Covers: __init__ (config + env fallbacks), _get_headers, list_users (mock
mode when creds missing, real success, error -> 500 generic), check_health
(real/mock modes), get_capabilities, health_check (healthy / unhealthy /
exception -> generic), execute_operation (list_users + all stub ops +
unsupported -> generic envelope), base-class get_operation_details contract.

Bugs fixed (TDD RED -> GREEN):
- execute_operation leaked str(e); now generic envelope.
- health_check exception branch leaked str(e); now generic.
- list_users already raised a generic 500 (no leak) — verified.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException

from integrations.okta_service import OktaService


def _svc(config=None):
    return OktaService(tenant_id="t1", config=config or {})


class TestInit:
    def test_config_passthrough(self, monkeypatch):
        monkeypatch.delenv("OKTA_ORG_URL", raising=False)
        monkeypatch.delenv("OKTA_API_TOKEN", raising=False)
        svc = _svc({"okta_org_url": "https://acme.okta.com", "okta_api_token": "tok1"})
        assert svc.org_url == "https://acme.okta.com"
        assert svc.api_token == "tok1"

    def test_env_fallbacks(self, monkeypatch):
        monkeypatch.setenv("OKTA_ORG_URL", "https://env.okta.com")
        monkeypatch.setenv("OKTA_API_TOKEN", "env-tok")
        svc = OktaService()
        assert svc.org_url == "https://env.okta.com"
        assert svc.api_token == "env-tok"


class TestHeaders:
    def test_get_headers(self):
        svc = _svc({"okta_api_token": "tok1"})
        h = svc._get_headers()
        assert h["Authorization"] == "SSWS tok1"
        assert h["Accept"] == "application/json"


class TestListUsers:
    async def test_mock_mode_without_credentials(self):
        svc = _svc()
        out = await svc.list_users()
        assert len(out) == 1
        assert out[0]["id"] == "mock_id"
        assert "MOCK" in out[0]["status"]

    async def test_real_success(self):
        svc = _svc({"okta_org_url": "https://acme.okta.com", "okta_api_token": "tok1"})
        svc.client.get = AsyncMock(return_value=httpx.Response(
            200, json=[{"id": "u1"}], request=httpx.Request("GET", "http://x")))
        out = await svc.list_users(limit=25)
        assert out == [{"id": "u1"}]
        kwargs = svc.client.get.call_args.kwargs
        assert svc.client.get.call_args.args[0] == "https://acme.okta.com/api/v1/users"
        assert kwargs["params"] == {"limit": 25}
        assert kwargs["headers"]["Authorization"] == "SSWS tok1"

    async def test_error_500_generic(self):
        svc = _svc({"okta_org_url": "https://acme.okta.com", "okta_api_token": "tok1"})
        svc.client.get = AsyncMock(side_effect=httpx.ConnectError("net-secret"))
        with pytest.raises(HTTPException) as ei:
            await svc.list_users()
        assert ei.value.status_code == 500
        assert ei.value.detail == "Internal error"
        assert "net-secret" not in ei.value.detail


class TestCheckHealth:
    async def test_real_mode_with_token(self):
        out = await _svc({"okta_api_token": "tok1"}).check_health()
        assert out["status"] == "active"
        assert out["mode"] == "real"

    async def test_mock_mode_without_token(self):
        out = await _svc().check_health()
        assert out["status"] == "partially_configured"
        assert out["mode"] == "mock"


class TestCapabilities:
    def test_operations(self):
        caps = _svc().get_capabilities()
        assert len(caps["operations"]) == 6
        assert caps["operations"][-1] == {"id": "list_users", "name": "List Users"}
        assert caps["required_params"] == ["api_token"]
        assert caps["supports_webhooks"] is True

    def test_get_operation_details_base_contract(self):
        svc = _svc()
        assert svc.get_operation_details("list_users")["name"] == "List Users"
        assert svc.get_operation_details("nope") is None


class TestHealthCheck:
    def test_healthy_with_org_url(self):
        out = _svc({"okta_org_url": "https://acme.okta.com"}).health_check()
        assert out["ok"] is True
        assert out["status"] == "healthy"
        assert out["healthy"] is True
        assert out["service"] == "okta"
        assert out["version"] == "1.0.0"

    def test_unhealthy_without_org_url(self):
        out = _svc().health_check()
        assert out["ok"] is False
        assert out["status"] == "unhealthy"

    def test_exception_branch_generic(self):
        """RED: exception branch leaked str(e); must be generic."""
        svc = _svc({"okta_org_url": "https://acme.okta.com"})
        with patch("integrations.okta_service.datetime") as dt:
            dt.now.side_effect = [RuntimeError("clock-secret"),
                                  datetime.now(timezone.utc)]
            out = svc.health_check()
        assert out["ok"] is False
        assert out["status"] == "unhealthy"
        assert "clock-secret" not in out["error"]
        assert out["error"] == "Okta health check failed"


class TestExecuteOperation:
    async def test_list_users_op(self):
        svc = _svc()
        svc.list_users = AsyncMock(return_value=[{"id": "u1"}])
        out = await svc.execute_operation("list_users", {"limit": 10})
        assert out["success"] is True
        assert out["result"] == [{"id": "u1"}]
        svc.list_users.assert_awaited_once_with(10)

    async def test_create_user_stub(self):
        out = await _svc().execute_operation("create_user", {"email": "a@b.c"})
        assert out["success"] is True
        assert out["result"] == {"id": "new_user", "email": "a@b.c"}

    async def test_get_user_stub(self):
        out = await _svc().execute_operation("get_user", {"user_id": "u9"})
        assert out["success"] is True
        assert out["result"] == {"id": "u9"}

    async def test_update_user_stub(self):
        out = await _svc().execute_operation("update_user", {"user_id": "u9"})
        assert out["success"] is True
        assert out["result"] == {"id": "u9", "updated": True}

    async def test_assign_role_stub(self):
        out = await _svc().execute_operation("assign_role", {"user_id": "u9", "role_id": "r1"})
        assert out["success"] is True
        assert out["result"] == {"user_id": "u9", "role_id": "r1"}

    async def test_get_groups_stub(self):
        out = await _svc().execute_operation("get_groups", {})
        assert out["success"] is True
        assert out["result"] == {"groups": []}

    async def test_unsupported_generic_envelope(self):
        """RED: unsupported op leaked the NotImplementedError text; now a
        generic envelope."""
        out = await _svc().execute_operation("nope", {})
        assert out["success"] is False
        assert out["error"] == "Okta operation failed"

    async def test_exception_generic_envelope(self):
        svc = _svc()
        svc.list_users = AsyncMock(side_effect=RuntimeError("secret-detail"))
        out = await svc.execute_operation("list_users", {})
        assert out["success"] is False
        assert "secret-detail" not in out["error"]
        assert out["error"] == "Okta operation failed"
