# -*- coding: utf-8 -*-
"""Coverage wave 115 — integrations/xero_service.py (22% → 95%+).

Tracked 2026-08-13: probe A re-run (w92/w93/w97/w98/w100/w104/w105/w109/w115
wave cluster) left integrations/xero_service.py at 22% — partially covered by
the w105 xero_routes suite (routes call exchange_token/get_tenants/get_invoices/
get_contacts). Wave 115 closes the remaining 105 lines: _get_headers (28-34),
exchange_token success + HTTPError (38-62), get_tenants/get_invoices/
get_contacts success + failure (66-112), capabilities/health_check (116, 126),
execute_operation all branches (140-175), sync_to_postgres_cache update/insert/
rollback/outer-failure (178-234), full_sync (238-243).

Zero network, zero LLM spend: the httpx client is replaced with AsyncMock
everywhere; DB (SessionLocal/IntegrationMetric) is fully mocked.
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException

from integrations.xero_service import XeroService


def _make_service(**config):
    svc = XeroService(tenant_id="tenant-1", config=config)
    svc.client = MagicMock()
    return svc


def _resp(payload=None, error=None):
    resp = MagicMock()
    if error:
        resp.raise_for_status.side_effect = error
    else:
        resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=payload if payload is not None else {})
    return resp


class TestGetHeaders:
    def test_config_none_defaults_to_empty(self):
        svc = XeroService(tenant_id="tenant-1", config=None)
        svc.client = MagicMock()
        assert svc.base_url == "https://api.xero.com/api.xro/2.0"

    def test_without_tenant(self):
        svc = _make_service()
        headers = svc._get_headers("tok-1")
        assert headers == {
            "Authorization": "Bearer tok-1",
            "Accept": "application/json",
        }

    def test_with_tenant(self):
        svc = _make_service()
        headers = svc._get_headers("tok-1", "xero-tenant-9")
        assert headers["Xero-tenant-id"] == "xero-tenant-9"


class TestExchangeToken:
    async def test_success(self):
        svc = _make_service(client_id="cid", client_secret="csec")
        svc.client.post = AsyncMock(return_value=_resp({"access_token": "at"}))
        result = await svc.exchange_token("code-1", "https://cb")
        assert result == {"access_token": "at"}
        args, kwargs = svc.client.post.await_args
        assert args[0] == "https://identity.xero.com/connect/token"
        assert kwargs["data"] == {
            "grant_type": "authorization_code",
            "code": "code-1",
            "redirect_uri": "https://cb",
        }
        assert kwargs["headers"]["Authorization"].startswith("Basic ")

    async def test_http_error_raises_400(self):
        svc = _make_service(client_id="cid", client_secret="csec")
        svc.client.post = AsyncMock(return_value=_resp(error=httpx.HTTPError("conn refused")))
        with pytest.raises(HTTPException) as exc:
            await svc.exchange_token("code-1", "https://cb")
        assert exc.value.status_code == 400


class TestGetTenants:
    async def test_success(self):
        svc = _make_service()
        svc.client.get = AsyncMock(return_value=_resp([{"tenantId": "t1"}]))
        result = await svc.get_tenants("tok-1")
        assert result == [{"tenantId": "t1"}]

    async def test_failure_raises_500(self):
        svc = _make_service()
        svc.client.get = AsyncMock(return_value=_resp(error=RuntimeError("conn refused")))
        with pytest.raises(HTTPException) as exc:
            await svc.get_tenants("tok-1")
        assert exc.value.status_code == 500


class TestGetInvoices:
    async def test_success_with_tenant_param(self):
        svc = _make_service()
        svc.client.get = AsyncMock(return_value=_resp({"Invoices": [1, 2, 3, 4, 5]}))
        result = await svc.get_invoices("tok-1", "xt-1", limit=2)
        assert result == [1, 2]
        headers = svc.client.get.await_args.kwargs["headers"]
        assert headers["Xero-tenant-id"] == "xt-1"

    async def test_success_falls_back_to_instance_tenant(self):
        svc = _make_service(xero_tenant_id="inst-tenant")
        svc.client.get = AsyncMock(return_value=_resp({"Invoices": []}))
        result = await svc.get_invoices("tok-1")
        assert result == []
        headers = svc.client.get.await_args.kwargs["headers"]
        assert headers["Xero-tenant-id"] == "inst-tenant"

    async def test_failure_raises_500(self):
        svc = _make_service()
        svc.client.get = AsyncMock(return_value=_resp(error=RuntimeError("boom")))
        with pytest.raises(HTTPException) as exc:
            await svc.get_invoices("tok-1")
        assert exc.value.status_code == 500


class TestGetContacts:
    async def test_success(self):
        svc = _make_service()
        svc.client.get = AsyncMock(return_value=_resp({"Contacts": [{"id": 1}, {"id": 2}, {"id": 3}]}))
        result = await svc.get_contacts("tok-1", "xt-1", limit=2)
        assert result == [{"id": 1}, {"id": 2}]

    async def test_failure_raises_500(self):
        svc = _make_service()
        svc.client.get = AsyncMock(return_value=_resp(error=RuntimeError("boom")))
        with pytest.raises(HTTPException) as exc:
            await svc.get_contacts("tok-1")
        assert exc.value.status_code == 500


class TestCapabilitiesAndHealth:
    def test_capabilities(self):
        svc = _make_service()
        caps = svc.get_capabilities()
        assert caps["operations"] == ["get_contacts", "get_invoices", "get_bank_transactions"]
        assert caps["rate_limits"] == {"requests_per_minute": 60}

    def test_health_incomplete(self):
        svc = _make_service()
        health = svc.health_check()
        assert health["healthy"] is False
        assert health["status"] == "incomplete_config"
        assert health["service"] == "xero"

    def test_health_operational(self):
        svc = _make_service(client_id="cid", client_secret="csec")
        health = svc.health_check()
        assert health["healthy"] is True
        assert health["status"] == "operational"
        assert "timestamp" in health


class TestExecuteOperation:
    async def test_get_tenants(self):
        svc = _make_service()
        svc.get_tenants = AsyncMock(return_value=["t1"])
        result = await svc.execute_operation("get_tenants", {"access_token": "tok"})
        assert result == {"success": True, "result": ["t1"]}

    async def test_get_invoices_with_limit(self):
        svc = _make_service()
        svc.get_invoices = AsyncMock(return_value=["inv"])
        result = await svc.execute_operation(
            "get_invoices", {"access_token": "tok", "xero_tenant_id": "xt", "limit": 5},
        )
        assert result["success"] is True
        svc.get_invoices.assert_awaited_once_with("tok", "xt", limit=5)

    async def test_get_contacts_default_limit(self):
        svc = _make_service()
        svc.get_contacts = AsyncMock(return_value=["c"])
        result = await svc.execute_operation("get_contacts", {"access_token": "tok"})
        assert result["success"] is True
        svc.get_contacts.assert_awaited_once_with("tok", None, limit=20)

    async def test_full_sync(self):
        svc = _make_service()
        svc.full_sync = AsyncMock(return_value={"success": True})
        result = await svc.execute_operation(
            "full_sync", {"access_token": "tok", "user_id": "u1", "xero_tenant_id": "xt"},
        )
        assert result["success"] is True
        svc.full_sync.assert_awaited_once_with(user_id="u1", access_token="tok", xero_tenant_id="xt")

    async def test_unknown_operation(self):
        svc = _make_service()
        result = await svc.execute_operation("get_foo", {"access_token": "tok"})
        assert result == {"success": False, "error": "Unknown operation: get_foo"}

    async def test_exception(self):
        svc = _make_service()
        svc.get_tenants = AsyncMock(side_effect=RuntimeError("boom"))
        result = await svc.execute_operation("get_tenants", {"access_token": "tok"})
        assert result == {"success": False, "error": "Xero operation failed"}


class TestSyncToPostgresCache:
    def _setup(self, svc, existing_values=None):
        db = MagicMock()
        if existing_values is None:
            existing_values = {}
        db.query.return_value.filter_by.return_value.first.side_effect = [
            existing_values.get(k) for k in ("xero_invoice_count", "xero_contact_count")
        ]
        svc.get_invoices = AsyncMock(return_value=["a", "b", "c"])
        svc.get_contacts = AsyncMock(return_value=["x", "y"])
        return db

    async def test_update_existing_metrics(self):
        svc = _make_service()
        existing_inv = MagicMock()
        existing_con = MagicMock()
        db = self._setup(svc, existing_values={
            "xero_invoice_count": existing_inv,
            "xero_contact_count": existing_con,
        })
        with patch("core.database.SessionLocal", return_value=db), \
             patch("core.models.IntegrationMetric", new=MagicMock()):
            result = await svc.sync_to_postgres_cache("u1", "tok", "xt")
        assert result == {"success": True, "metrics_synced": 2}
        assert existing_inv.value == 3.0
        assert existing_con.value == 2.0
        assert existing_inv.last_synced_at is not None
        assert db.add.call_count == 0
        db.commit.assert_called_once()
        db.close.assert_called_once()

    async def test_insert_new_metrics(self):
        svc = _make_service()
        db = self._setup(svc)  # both .first() return None -> insert path
        with patch("core.database.SessionLocal", return_value=db), \
             patch("core.models.IntegrationMetric") as IM:
            result = await svc.sync_to_postgres_cache("u1", "tok", "xt")
        assert result == {"success": True, "metrics_synced": 2}
        assert db.add.call_count == 2
        assert IM.call_count == 2
        db.commit.assert_called_once()
        db.close.assert_called_once()

    async def test_save_error_rolls_back(self):
        svc = _make_service()
        db = self._setup(svc)
        db.commit.side_effect = RuntimeError("commit failed")
        with patch("core.database.SessionLocal", return_value=db), \
             patch("core.models.IntegrationMetric", new=MagicMock()):
            result = await svc.sync_to_postgres_cache("u1", "tok", "xt")
        assert result == {"success": False, "error": "Failed to save Xero metrics"}
        db.rollback.assert_called_once()
        db.close.assert_called_once()

    async def test_outer_failure(self):
        svc = _make_service()
        svc.get_invoices = AsyncMock(side_effect=RuntimeError("api down"))
        with patch("core.database.SessionLocal") as SL:
            result = await svc.sync_to_postgres_cache("u1", "tok", "xt")
        assert result == {"success": False, "error": "Xero cache sync failed"}
        SL.assert_not_called()

    async def test_instance_tenant_fallback(self):
        svc = _make_service(xero_tenant_id="inst-tenant")
        db = self._setup(svc)
        with patch("core.database.SessionLocal", return_value=db), \
             patch("core.models.IntegrationMetric", new=MagicMock()):
            result = await svc.sync_to_postgres_cache("u1", "tok")
        assert result["success"] is True
        svc.get_invoices.assert_awaited_once_with("tok", "inst-tenant", limit=100)


class TestFullSync:
    async def test_success(self):
        svc = _make_service()
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True, "metrics_synced": 2})
        result = await svc.full_sync("u1", "tok", "xt")
        assert result["success"] is True
        assert result["user_id"] == "u1"
        assert result["postgres_cache"]["metrics_synced"] == 2
        assert isinstance(result["timestamp"], str)
        svc.sync_to_postgres_cache.assert_awaited_once_with("u1", "tok", "xt")
