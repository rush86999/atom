# -*- coding: utf-8 -*-
"""Coverage wave 97 — integrations/quickbooks_service (QuickBooksService).

Standalone, fully mocked (IntegrationHTTP + httpx.Response objects), zero
network, zero LLM spend. Follows the wave-95 zoom/linear conventions.

Covers: __init__ (config provided/empty + env fallbacks + sandbox toggle),
close, _get_api_url (sandbox/prod), _get_headers, get_authorization_url
(with/without state), exchange_token (success stores token, HTTPError -> 400,
MISSING client credentials -> clean 400 fail-closed — was an uncaught httpx
TypeError escaping as 500), get_company_info / get_customers / get_invoices /
get_expenses (success, no-token 401, HTTPError -> 400), health_check
(healthy/unhealthy/exception -> generic message, NO str(e) leak), execute_operation
(all 4 data ops + full_sync + unknown op + inner-exception -> generic envelope,
no str(e) leak), sync_to_postgres_cache (insert + update paths, inner rollback
-> generic, outer error -> generic), full_sync (success).

Bugs fixed (TDD RED -> GREEN):
- exchange_token: missing client_id/client_secret produced an uncaught httpx
  TypeError (auth=(None, None)) escaping as a 500. Now fail-closed 400.
- health_check exception path leaked str(e); now generic message.
- execute_operation exception path leaked str(e); now generic envelope.
- sync_to_postgres_cache inner/outer error paths leaked str(e); now generic.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from integrations.quickbooks_service import QuickBooksService


def _svc(config=None):
    svc = QuickBooksService(tenant_id="t1", config=config or {})
    return svc


def _resp(status=200, payload=None):
    return httpx.Response(status, json=payload if payload is not None else {},
                          request=httpx.Request("GET", "http://x"))


class TestInit:
    def test_config_passthrough(self):
        svc = _svc({"client_id": "cid", "client_secret": "cs",
                    "access_token": "tok", "realm_id": "r1", "use_sandbox": "true"})
        assert svc.client_id == "cid"
        assert svc.client_secret == "cs"
        assert svc.access_token == "tok"
        assert svc.realm_id == "r1"
        assert svc.use_sandbox is True
        assert svc.base_url == "https://quickbooks.api.intuit.com/v3"
        assert svc.sandbox_url == "https://sandbox-quickbooks.api.intuit.com/v3"
        assert svc.token_url == "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
        assert svc.tenant_id == "t1"

    def test_empty_config(self):
        svc = QuickBooksService()
        assert svc.client_id is None
        assert svc.access_token is None
        assert svc.use_sandbox is False

    def test_env_fallbacks(self, monkeypatch):
        monkeypatch.setenv("QUICKBOOKS_CLIENT_ID", "env-cid")
        monkeypatch.setenv("QUICKBOOKS_ACCESS_TOKEN", "env-tok")
        monkeypatch.setenv("QUICKBOOKS_REALM_ID", "env-realm")
        monkeypatch.setenv("QUICKBOOKS_USE_SANDBOX", "true")
        svc = QuickBooksService()
        assert svc.client_id == "env-cid"
        assert svc.access_token == "env-tok"
        assert svc.realm_id == "env-realm"
        assert svc.use_sandbox is True

    async def test_close(self):
        svc = _svc()
        svc.client.aclose = AsyncMock()
        await svc.close()
        svc.client.aclose.assert_awaited_once()


class TestApiUrl:
    def test_sandbox(self):
        svc = _svc({"use_sandbox": "true"})
        assert svc._get_api_url() == "https://sandbox-quickbooks.api.intuit.com/v3"

    def test_prod(self):
        svc = _svc({})
        assert svc._get_api_url() == "https://quickbooks.api.intuit.com/v3"


class TestHeaders:
    def test_get_headers(self):
        svc = _svc()
        h = svc._get_headers("abc")
        assert h["Authorization"] == "Bearer abc"
        assert h["Accept"] == "application/json"
        assert h["Content-Type"] == "application/json"


class TestCapabilities:
    def test_operations(self):
        """RED: QuickBooksService never implemented the ABC
        get_capabilities, so the class was uninstantiable (TypeError)."""
        svc = _svc()
        caps = svc.get_capabilities()
        assert set(caps["operations"]) == {
            "get_company_info", "get_customers", "get_invoices", "get_expenses", "full_sync"}
        assert caps["required_params"] == ["client_id", "client_secret", "realm_id"]
        assert caps["supports_webhooks"] is False


class TestAuthUrl:
    def test_without_state(self):
        svc = _svc()
        url = svc.get_authorization_url("http://cb")
        assert url.startswith("https://appcenter.intuit.com/connect/oauth2?")
        assert "client_id=None" in url
        assert "redirect_uri=http://cb" in url
        assert "response_type=code" in url
        assert "scope=com.intuit.quickbooks.accounting" in url
        assert "state" not in url

    def test_with_state(self):
        svc = _svc()
        url = svc.get_authorization_url("http://cb", state="s123", scope="scope-x")
        assert "state=s123" in url
        assert "scope=scope-x" in url


class TestExchangeToken:
    async def test_success(self):
        svc = _svc({"client_id": "cid", "client_secret": "cs"})
        svc.http.post = AsyncMock(return_value=_resp(200, {"access_token": "newtok", "realmId": "r9"}))
        data = await svc.exchange_token("code1", "http://cb")
        assert data["access_token"] == "newtok"
        assert svc.access_token == "newtok"
        assert svc.realm_id == "r9"
        kwargs = svc.http.post.call_args.kwargs
        assert kwargs["data"]["grant_type"] == "authorization_code"
        assert kwargs["auth"] == ("cid", "cs")
        assert kwargs["headers"]["Content-Type"] == "application/x-www-form-urlencoded"

    async def test_http_error_returns_400(self):
        svc = _svc({"client_id": "cid", "client_secret": "cs"})
        svc.http.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
        with pytest.raises(HTTPException) as ei:
            await svc.exchange_token("code1", "http://cb")
        assert ei.value.status_code == 400
        assert ei.value.detail == "Internal error"

    async def test_missing_credentials_fail_closed(self):
        """RED: missing creds produced an uncaught httpx TypeError from
        BasicAuth((None, None)) escaping as a 500; must be a clean 400."""
        svc = _svc({})
        svc.http.post = AsyncMock(side_effect=TypeError(
            "sequence item 0: expected a bytes-like object, NoneType found"))
        with pytest.raises(HTTPException) as ei:
            await svc.exchange_token("code1", "http://cb")
        assert ei.value.status_code == 400
        assert "credential" in ei.value.detail.lower()


class TestGetCompanyInfo:
    async def test_success(self):
        svc = _svc({"access_token": "tok", "realm_id": "r1"})
        svc.http.get = AsyncMock(return_value=_resp(200, {"CompanyInfo": {"Name": "ACME"}}))
        out = await svc.get_company_info()
        assert out == {"Name": "ACME"}
        url = svc.http.get.call_args.args[1]
        assert url == "https://quickbooks.api.intuit.com/v3/company/r1/companyinfo/r1"

    async def test_no_token_or_realm_401(self):
        svc = _svc({})
        with pytest.raises(HTTPException) as ei:
            await svc.get_company_info()
        assert ei.value.status_code == 401

    async def test_explicit_params_override(self):
        svc = _svc({})
        svc.http.get = AsyncMock(return_value=_resp(200, {"CompanyInfo": {}}))
        out = await svc.get_company_info(realm_id="r2", access_token="t2")
        assert out == {}

    async def test_http_error_400(self):
        svc = _svc({"access_token": "tok", "realm_id": "r1"})
        svc.http.get = AsyncMock(side_effect=httpx.TimeoutException("slow"))
        with pytest.raises(HTTPException) as ei:
            await svc.get_company_info()
        assert ei.value.status_code == 400
        assert ei.value.detail == "Internal error"


class TestGetCustomers:
    async def test_success(self):
        svc = _svc({"access_token": "tok", "realm_id": "r1"})
        svc.http.get = AsyncMock(return_value=_resp(200, {"QueryResponse": {"Customer": [{"Id": "c1"}]}}))
        out = await svc.get_customers(max_results=50)
        assert out == [{"Id": "c1"}]
        kwargs = svc.http.get.call_args.kwargs
        assert kwargs["params"]["query"] == "SELECT * FROM Customer MAXRESULTS 50"

    async def test_no_token_401(self):
        svc = _svc({})
        with pytest.raises(HTTPException) as ei:
            await svc.get_customers()
        assert ei.value.status_code == 401

    async def test_http_error_400(self):
        svc = _svc({"access_token": "tok", "realm_id": "r1"})
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.get_customers()
        assert ei.value.status_code == 400


class TestGetInvoices:
    async def test_success(self):
        svc = _svc({"access_token": "tok", "realm_id": "r1"})
        svc.http.get = AsyncMock(return_value=_resp(200, {"QueryResponse": {"Invoice": [{"Id": "i1"}]}}))
        out = await svc.get_invoices()
        assert out == [{"Id": "i1"}]
        assert svc.http.get.call_args.kwargs["params"]["query"] == "SELECT * FROM Invoice MAXRESULTS 100"

    async def test_empty_response(self):
        svc = _svc({"access_token": "tok", "realm_id": "r1"})
        svc.http.get = AsyncMock(return_value=_resp(200, {}))
        assert await svc.get_invoices() == []

    async def test_no_token_401(self):
        svc = _svc({})
        with pytest.raises(HTTPException) as ei:
            await svc.get_invoices()
        assert ei.value.status_code == 401

    async def test_http_error_400(self):
        svc = _svc({"access_token": "tok", "realm_id": "r1"})
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.get_invoices()
        assert ei.value.status_code == 400


class TestGetExpenses:
    async def test_success(self):
        svc = _svc({"access_token": "tok", "realm_id": "r1"})
        svc.http.get = AsyncMock(return_value=_resp(200, {"QueryResponse": {"Purchase": [{"Id": "p1"}]}}))
        out = await svc.get_expenses()
        assert out == [{"Id": "p1"}]
        assert "PaymentType = 'Cash'" in svc.http.get.call_args.kwargs["params"]["query"]

    async def test_no_token_401(self):
        svc = _svc({})
        with pytest.raises(HTTPException) as ei:
            await svc.get_expenses()
        assert ei.value.status_code == 401

    async def test_http_error_400(self):
        svc = _svc({"access_token": "tok", "realm_id": "r1"})
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.get_expenses()
        assert ei.value.status_code == 400


class TestHealthCheck:
    async def test_healthy(self):
        svc = _svc({"client_id": "cid"})
        out = await svc.health_check()
        assert out["ok"] is True
        assert out["status"] == "healthy"
        assert out["service"] == "quickbooks"
        assert "timestamp" in out
        assert out["version"] == "1.0.0"

    async def test_exception_path_generic(self):
        """RED: exception path leaked str(e); must be generic."""
        svc = _svc()
        with patch("integrations.quickbooks_service.datetime") as dt:
            dt.now.side_effect = RuntimeError("clock-secret-detail")
            out = await svc.health_check()
        assert out["ok"] is False
        assert out["status"] == "unhealthy"
        assert "clock-secret-detail" not in out["error"]
        assert out["error"] == "QuickBooks health check failed"


class TestExecuteOperation:
    async def test_get_company_info_op(self):
        svc = _svc()
        svc.get_company_info = AsyncMock(return_value={"Name": "ACME"})
        out = await svc.execute_operation("get_company_info", {"realm_id": "r1", "access_token": "t1"})
        assert out["success"] is True
        assert out["result"] == {"Name": "ACME"}
        svc.get_company_info.assert_awaited_once_with("r1", "t1")

    async def test_get_customers_op(self):
        svc = _svc()
        svc.get_customers = AsyncMock(return_value=[])
        out = await svc.execute_operation("get_customers", {"max_results": 25})
        assert out["success"] is True
        assert svc.get_customers.call_args.kwargs["max_results"] == 25

    async def test_get_invoices_op(self):
        svc = _svc()
        svc.get_invoices = AsyncMock(return_value=[])
        out = await svc.execute_operation("get_invoices", {})
        assert out["success"] is True

    async def test_get_expenses_op(self):
        svc = _svc()
        svc.get_expenses = AsyncMock(return_value=[])
        out = await svc.execute_operation("get_expenses", {})
        assert out["success"] is True

    async def test_full_sync_op(self):
        svc = _svc()
        svc.full_sync = AsyncMock(return_value={"success": True, "postgres_cache": {}})
        out = await svc.execute_operation("full_sync", {"user_id": "u1"})
        assert out["success"] is True
        svc.full_sync.assert_awaited_once()
        assert svc.full_sync.call_args.kwargs["user_id"] == "u1"

    async def test_unknown_operation(self):
        svc = _svc()
        out = await svc.execute_operation("nope", {})
        assert out["success"] is False
        assert "Unknown operation" in out["error"]

    async def test_inner_exception_generic_envelope(self):
        """RED: exception path leaked str(e); must be generic."""
        svc = _svc()
        svc.get_company_info = AsyncMock(side_effect=RuntimeError("secret-detail"))
        out = await svc.execute_operation("get_company_info", {})
        assert out["success"] is False
        assert "secret-detail" not in out["error"]
        assert out["error"] == "QuickBooks operation failed"


@pytest.fixture()
def db_session_factory():
    engine = create_engine("sqlite://")
    from core.models import Base
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


class TestSyncToPostgresCache:
    async def test_success_inserts_metrics(self, db_session_factory):
        svc = _svc()
        svc.get_invoices = AsyncMock(return_value=[{"Id": "i1"}, {"Id": "i2"}])
        svc.get_customers = AsyncMock(return_value=[{"Id": "c1"}])
        with patch("core.database.SessionLocal", db_session_factory):
            out = await svc.sync_to_postgres_cache("u1", "r1", "tok")
        assert out["success"] is True
        assert out["metrics_synced"] == 2
        db = db_session_factory()
        from core.models import IntegrationMetric
        rows = db.query(IntegrationMetric).all()
        assert len(rows) == 2
        keys = {r.metric_key for r in rows}
        assert keys == {"quickbooks_invoice_count", "quickbooks_customer_count"}
        by_key = {r.metric_key: r for r in rows}
        assert by_key["quickbooks_invoice_count"].value == 2.0
        assert by_key["quickbooks_customer_count"].value == 1.0
        assert all(r.workspace_id == "u1" for r in rows)
        assert all(r.integration_type == "quickbooks" for r in rows)
        db.close()

    async def test_existing_rows_updated(self, db_session_factory):
        svc = _svc()
        svc.get_invoices = AsyncMock(return_value=[{"Id": "i1"}])
        svc.get_customers = AsyncMock(return_value=[])
        with patch("core.database.SessionLocal", db_session_factory):
            await svc.sync_to_postgres_cache("u1", "r1", "tok")
            await svc.sync_to_postgres_cache("u1", "r1", "tok")
        db = db_session_factory()
        from core.models import IntegrationMetric
        rows = db.query(IntegrationMetric).all()
        assert len(rows) == 2
        inv = db.query(IntegrationMetric).filter_by(metric_key="quickbooks_invoice_count").first()
        assert inv.value == 1.0
        assert inv.last_synced_at is not None
        db.close()

    async def test_inner_error_rollback_generic(self, db_session_factory):
        """RED: inner error path leaked str(e); must be generic."""
        svc = _svc()
        svc.get_invoices = AsyncMock(return_value=[{"Id": "i1"}])
        svc.get_customers = AsyncMock(return_value=[])
        rolled_back = []

        class Boom:
            def __init__(self, *a, **k):
                pass

            def query(self, *a, **k):
                raise RuntimeError("db-explode-detail")

            def add(self, *a, **k):
                pass

            def commit(self):
                pass

            def rollback(self):
                rolled_back.append(True)

            def close(self):
                pass

        with patch("core.database.SessionLocal", Boom):
            out = await svc.sync_to_postgres_cache("u1", "r1", "tok")
        assert out["success"] is False
        assert "db-explode-detail" not in out["error"]
        assert out["error"] == "QuickBooks metrics sync failed"
        assert rolled_back

    async def test_outer_error_generic(self, db_session_factory):
        """RED: outer error path leaked str(e); must be generic."""
        svc = _svc()
        svc.get_invoices = AsyncMock(side_effect=RuntimeError("fetch-secret"))
        with patch("core.database.SessionLocal", db_session_factory):
            out = await svc.sync_to_postgres_cache("u1", "r1", "tok")
        assert out["success"] is False
        assert "fetch-secret" not in out["error"]
        assert out["error"] == "QuickBooks PostgreSQL cache sync failed"


class TestFullSync:
    async def test_success(self):
        svc = _svc()
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True, "metrics_synced": 2})
        out = await svc.full_sync("u1", "r1", "tok")
        assert out["success"] is True
        assert out["user_id"] == "u1"
        assert out["postgres_cache"]["success"] is True
        assert "timestamp" in out
