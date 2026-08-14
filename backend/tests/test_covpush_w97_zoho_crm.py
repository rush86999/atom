# -*- coding: utf-8 -*-
"""Coverage wave 97 — integrations/zoho_crm_service (ZohoCRMService).

Standalone, fully mocked (httpx.AsyncClient methods + httpx.Response objects
+ patched SessionLocal), zero network, zero LLM spend. Follows the wave-95
zoom/linear conventions.

Covers: __init__ (config + env fallback), get_capabilities, health_check
(token present/absent), execute_operation (get_leads / get_deals /
get_modules / create_lead / create_record / unsupported / inner-exception ->
generic envelope), _get_active_token (tenant fallback, missing record, valid
token, naive-tz expires_at, expired+refresh success, expired+refresh failure
-> None fail-closed, no refresh_token, DB exception -> None), refresh_token
(missing env creds -> None fail-closed, success, failure), get_leads /
get_deals (success, no-token 401, error -> []), get_modules / get_fields
(success, no-token -> [], error -> []), create_lead / create_record (success,
no-token 401, error -> 500 generic), sync_to_postgres_cache (insert + update
paths, inner rollback generic, outer error generic), full_sync (success).

Bugs fixed (TDD RED -> GREEN):
- sync_to_postgres_cache used the phantom IntegrationMetric.tenant_id column
  (filter_by + constructor) -> InvalidRequestError on every sync; now uses the
  real workspace_id column (same bug class as wave-95 Linear).
- execute_operation leaked str(exc); now generic envelope.
- sync_to_postgres_cache inner/outer error paths leaked str(e); now generic.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from integrations.zoho_crm_service import ZohoCRMService


def _svc(config=None):
    return ZohoCRMService(tenant_id="t1", config=config or {})


def _resp(status=200, payload=None):
    return httpx.Response(status, json=payload if payload is not None else {},
                          request=httpx.Request("GET", "http://x"))


class _FakeToken:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._result


class _FakeDB:
    def __init__(self, record=None, fail_query=False):
        self._record = record
        self._fail_query = fail_query
        self.commits = 0
        self.closed = False

    def query(self, model):
        if self._fail_query:
            raise RuntimeError("db-query-secret")
        return _FakeQuery(self._record)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        self.closed = True


class TestInit:
    def test_config_passthrough(self):
        svc = _svc({"access_token": "tok"})
        assert svc.access_token == "tok"
        assert svc.base_url == "https://www.zohoapis.com/crm/v2"
        assert svc.tenant_id == "t1"

    def test_env_fallback(self, monkeypatch):
        monkeypatch.setenv("ZOHO_CRM_ACCESS_TOKEN", "env-tok")
        svc = ZohoCRMService()
        assert svc.access_token == "env-tok"


class TestCapabilities:
    def test_operations(self):
        svc = _svc()
        caps = svc.get_capabilities()
        assert set(caps["operations"]) == {'get_leads', 'get_deals', 'get_modules',
                                           'create_lead', 'create_record'}
        assert caps["required_params"] == ["access_token"]
        assert caps["supports_webhooks"] is False


class TestHealthCheck:
    def test_healthy_with_token(self):
        svc = _svc({"access_token": "tok"})
        out = svc.health_check()
        assert out["healthy"] is True
        assert out["message"] == "connected"
        assert out["base_url"] == "https://www.zohoapis.com/crm/v2"

    def test_unhealthy_without_token(self):
        svc = _svc()
        out = svc.health_check()
        assert out["healthy"] is False
        assert "no access token" in out["message"]


class TestExecuteOperation:
    async def test_get_leads_op(self):
        svc = _svc()
        svc.get_leads = AsyncMock(return_value=[{"Id": "1"}])
        out = await svc.execute_operation("get_leads", {})
        assert out["success"] is True
        assert out["result"] == [{"Id": "1"}]

    async def test_get_deals_op(self):
        svc = _svc()
        svc.get_deals = AsyncMock(return_value=[])
        out = await svc.execute_operation("get_deals", {})
        assert out["success"] is True

    async def test_get_modules_op(self):
        svc = _svc()
        svc.get_modules = AsyncMock(return_value=[])
        out = await svc.execute_operation("get_modules", {})
        assert out["success"] is True

    async def test_create_lead_op(self):
        svc = _svc()
        svc.create_lead = AsyncMock(return_value={"Id": "1"})
        out = await svc.execute_operation("create_lead", {"Last_Name": "X"})
        assert out["success"] is True
        assert svc.create_lead.call_args.args[0] == {"Last_Name": "X"}

    async def test_create_record_op(self):
        svc = _svc()
        svc.create_record = AsyncMock(return_value={"Id": "1"})
        out = await svc.execute_operation("create_record", {"module": "Leads", "data": {}})
        assert out["success"] is True

    async def test_unsupported_operation(self):
        svc = _svc()
        out = await svc.execute_operation("nope", {})
        assert out["success"] is False
        assert "Unsupported operation" in out["error"]
        assert 'create_record' in out["supported"]

    async def test_inner_exception_generic_envelope(self):
        """RED: exception path leaked str(exc); must be generic."""
        svc = _svc()
        svc.get_leads = AsyncMock(side_effect=RuntimeError("secret-detail"))
        out = await svc.execute_operation("get_leads", {})
        assert out["success"] is False
        assert "secret-detail" not in out["error"]
        assert out["error"] == "Zoho CRM operation failed"


class TestGetActiveToken:
    async def test_tenantless_falls_back_to_access_token(self):
        svc = _svc({"access_token": "cfg-tok"})
        svc.tenant_id = None
        assert await svc._get_active_token() == "cfg-tok"

    async def test_env_fallback(self, monkeypatch):
        monkeypatch.setenv("ZOHO_CRM_ACCESS_TOKEN", "env-tok")
        svc = _svc()
        svc.tenant_id = None
        assert await svc._get_active_token() == "env-tok"

    async def test_no_token_record_returns_none(self):
        svc = _svc()
        db = _FakeDB(record=None)
        with patch("integrations.zoho_crm_service.SessionLocal", return_value=db):
            assert await svc._get_active_token("tid1") is None
        assert db.closed

    async def test_valid_token_returns_plaintext(self):
        svc = _svc()
        record = _FakeToken(
            access_token="plain-access",
            refresh_token=None,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db = _FakeDB(record=record)
        with patch("integrations.zoho_crm_service.SessionLocal", return_value=db):
            token = await svc._get_active_token("tid1")
        assert token == "plain-access"

    async def test_naive_expires_at_normalized(self):
        svc = _svc()
        record = _FakeToken(
            access_token="plain-access",
            refresh_token=None,
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1),
        )
        db = _FakeDB(record=record)
        with patch("integrations.zoho_crm_service.SessionLocal", return_value=db):
            token = await svc._get_active_token("tid1")
        assert token == "plain-access"

    async def test_expired_refresh_success_commits(self):
        svc = _svc()
        record = _FakeToken(
            access_token="old-enc",
            refresh_token="enc-refresh",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        db = _FakeDB(record=record)
        svc.refresh_token = AsyncMock(return_value={"access_token": "newtok", "expires_in": 3600})
        with patch("integrations.zoho_crm_service.SessionLocal", return_value=db), \
             patch("core.privsec.token_encryption.decrypt_token", return_value="refresh-plain"), \
             patch("core.privsec.token_encryption.encrypt_token", return_value="enc-newtok"), \
             patch("core.privsec.token_encryption.stamp_credential_metadata") as stamp:
            token = await svc._get_active_token("tid1")
        assert token == "enc-newtok"
        assert db.commits == 1
        assert record.access_token == "enc-newtok"
        stamp.assert_called_once_with(record)

    async def test_expired_refresh_failure_fail_closed(self):
        svc = _svc()
        record = _FakeToken(
            access_token="old",
            refresh_token="enc-refresh",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        db = _FakeDB(record=record)
        svc.refresh_token = AsyncMock(return_value=None)
        with patch("integrations.zoho_crm_service.SessionLocal", return_value=db), \
             patch("core.privsec.token_encryption.decrypt_token", return_value="rp"):
            token = await svc._get_active_token("tid1")
        assert token is None
        assert db.commits == 0

    async def test_expired_no_refresh_token_fail_closed(self):
        svc = _svc()
        record = _FakeToken(
            access_token="old",
            refresh_token=None,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        db = _FakeDB(record=record)
        with patch("integrations.zoho_crm_service.SessionLocal", return_value=db):
            token = await svc._get_active_token("tid1")
        assert token is None

    async def test_db_exception_returns_none(self):
        svc = _svc()
        db = _FakeDB(record=None, fail_query=True)
        with patch("integrations.zoho_crm_service.SessionLocal", return_value=db):
            token = await svc._get_active_token("tid1")
        assert token is None
        assert db.closed


class TestRefreshToken:
    async def test_missing_env_creds_fail_closed(self, monkeypatch):
        monkeypatch.delenv("ZOHO_CRM_CLIENT_ID", raising=False)
        monkeypatch.delenv("ZOHO_CRM_CLIENT_SECRET", raising=False)
        svc = _svc()
        svc.client.post = AsyncMock()
        assert await svc.refresh_token("rt") is None
        svc.client.post.assert_not_awaited()

    async def test_success(self, monkeypatch):
        monkeypatch.setenv("ZOHO_CRM_CLIENT_ID", "cid")
        monkeypatch.setenv("ZOHO_CRM_CLIENT_SECRET", "cs")
        svc = _svc()
        svc.client.post = AsyncMock(return_value=_resp(200, {"access_token": "new"}))
        out = await svc.refresh_token("rt")
        assert out == {"access_token": "new"}
        data = svc.client.post.call_args.kwargs["data"]
        assert data["grant_type"] == "refresh_token"
        assert data["client_id"] == "cid"
        assert data["client_secret"] == "cs"

    async def test_failure_returns_none(self, monkeypatch):
        monkeypatch.setenv("ZOHO_CRM_CLIENT_ID", "cid")
        monkeypatch.setenv("ZOHO_CRM_CLIENT_SECRET", "cs")
        svc = _svc()
        svc.client.post = AsyncMock(side_effect=httpx.ConnectError("net"))
        assert await svc.refresh_token("rt") is None


class TestGetLeads:
    async def test_success(self):
        svc = _svc()
        svc._get_active_token = AsyncMock(return_value="tok")
        svc.client.get = AsyncMock(return_value=_resp(200, {"data": [{"Id": "1"}]}))
        out = await svc.get_leads()
        assert out == [{"Id": "1"}]
        assert svc.client.get.call_args.args[0] == "https://www.zohoapis.com/crm/v2/Leads"

    async def test_no_token_401(self):
        svc = _svc()
        svc._get_active_token = AsyncMock(return_value=None)
        with pytest.raises(HTTPException) as ei:
            await svc.get_leads()
        assert ei.value.status_code == 401

    async def test_error_returns_empty(self):
        svc = _svc()
        svc._get_active_token = AsyncMock(return_value="tok")
        svc.client.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        assert await svc.get_leads() == []


class TestCreateLead:
    async def test_success(self):
        svc = _svc()
        svc._get_active_token = AsyncMock(return_value="tok")
        svc.client.post = AsyncMock(return_value=_resp(201, {"data": [{"Id": "9"}]}))
        out = await svc.create_lead({"Last_Name": "X"})
        assert out == {"Id": "9"}
        assert svc.client.post.call_args.kwargs["json"] == {"data": [{"Last_Name": "X"}]}

    async def test_no_token_401(self):
        svc = _svc()
        svc._get_active_token = AsyncMock(return_value=None)
        with pytest.raises(HTTPException) as ei:
            await svc.create_lead({})
        assert ei.value.status_code == 401

    async def test_error_500_generic(self):
        svc = _svc()
        svc._get_active_token = AsyncMock(return_value="tok")
        svc.client.post = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.create_lead({})
        assert ei.value.status_code == 500
        assert ei.value.detail == "Zoho CRM Lead creation failed"
        assert "net" not in ei.value.detail


class TestGetDeals:
    async def test_success(self):
        svc = _svc()
        svc._get_active_token = AsyncMock(return_value="tok")
        svc.client.get = AsyncMock(return_value=_resp(200, {"data": [{"Amount": "100"}]}))
        out = await svc.get_deals()
        assert out == [{"Amount": "100"}]

    async def test_no_token_401(self):
        svc = _svc()
        svc._get_active_token = AsyncMock(return_value=None)
        with pytest.raises(HTTPException) as ei:
            await svc.get_deals()
        assert ei.value.status_code == 401

    async def test_error_returns_empty(self):
        svc = _svc()
        svc._get_active_token = AsyncMock(return_value="tok")
        svc.client.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        assert await svc.get_deals() == []


class TestGetModules:
    async def test_success(self):
        svc = _svc()
        svc._get_active_token = AsyncMock(return_value="tok")
        svc.client.get = AsyncMock(return_value=_resp(200, {"modules": [{"api_name": "Leads"}]}))
        out = await svc.get_modules()
        assert out == [{"api_name": "Leads"}]

    async def test_no_token_returns_empty(self):
        svc = _svc()
        svc._get_active_token = AsyncMock(return_value=None)
        assert await svc.get_modules() == []

    async def test_error_returns_empty(self):
        svc = _svc()
        svc._get_active_token = AsyncMock(return_value="tok")
        svc.client.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        assert await svc.get_modules() == []


class TestGetFields:
    async def test_success(self):
        svc = _svc()
        svc._get_active_token = AsyncMock(return_value="tok")
        svc.client.get = AsyncMock(return_value=_resp(200, {"fields": [{"api_name": "Last_Name"}]}))
        out = await svc.get_fields("Leads")
        assert out == [{"api_name": "Last_Name"}]
        assert "module=Leads" in svc.client.get.call_args.args[0]

    async def test_no_token_returns_empty(self):
        svc = _svc()
        svc._get_active_token = AsyncMock(return_value=None)
        assert await svc.get_fields("Leads") == []

    async def test_error_returns_empty(self):
        svc = _svc()
        svc._get_active_token = AsyncMock(return_value="tok")
        svc.client.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        assert await svc.get_fields("Leads") == []


class TestCreateRecord:
    async def test_success(self):
        svc = _svc()
        svc._get_active_token = AsyncMock(return_value="tok")
        svc.client.post = AsyncMock(return_value=_resp(201, {"data": [{"Id": "7"}]}))
        out = await svc.create_record("Contacts", {"Last_Name": "Y"})
        assert out == {"Id": "7"}
        assert svc.client.post.call_args.args[0].endswith("/Contacts")

    async def test_no_token_401(self):
        svc = _svc()
        svc._get_active_token = AsyncMock(return_value=None)
        with pytest.raises(HTTPException) as ei:
            await svc.create_record("Contacts", {})
        assert ei.value.status_code == 401

    async def test_error_500_generic(self):
        svc = _svc()
        svc._get_active_token = AsyncMock(return_value="tok")
        svc.client.post = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.create_record("Contacts", {})
        assert ei.value.status_code == 500
        assert ei.value.detail == "Zoho CRM Contacts creation failed"


@pytest.fixture()
def db_session_factory():
    engine = create_engine("sqlite://")
    from core.models import Base
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


class TestSyncToPostgresCache:
    async def test_success_inserts_metrics(self, db_session_factory):
        """RED: used phantom IntegrationMetric.tenant_id column -> every
        sync raised InvalidRequestError."""
        svc = _svc()
        svc.get_leads = AsyncMock(return_value=[{"Id": "1"}, {"Id": "2"}])
        svc.get_deals = AsyncMock(return_value=[{"Amount": "100"}, {"Amount": "50"}])
        with patch("core.database.SessionLocal", db_session_factory):
            out = await svc.sync_to_postgres_cache("ws1")
        assert out["success"] is True
        assert out["metrics_synced"] == 3
        db = db_session_factory()
        from core.models import IntegrationMetric
        rows = db.query(IntegrationMetric).all()
        assert len(rows) == 3
        by_key = {r.metric_key: r for r in rows}
        assert by_key["zoho_crm_lead_count"].value == 2.0
        assert by_key["zoho_crm_deal_count"].value == 2.0
        assert by_key["zoho_crm_total_revenue"].value == 150.0
        assert all(r.workspace_id == "ws1" for r in rows)
        assert all(r.integration_type == "zoho_crm" for r in rows)
        db.close()

    async def test_existing_rows_updated(self, db_session_factory):
        svc = _svc()
        svc.get_leads = AsyncMock(return_value=[])
        svc.get_deals = AsyncMock(return_value=[])
        with patch("core.database.SessionLocal", db_session_factory):
            await svc.sync_to_postgres_cache("ws1")
            await svc.sync_to_postgres_cache("ws1")
        db = db_session_factory()
        from core.models import IntegrationMetric
        rows = db.query(IntegrationMetric).all()
        assert len(rows) == 3
        assert all(r.last_synced_at is not None for r in rows)
        db.close()

    async def test_inner_error_rollback_generic(self):
        """RED: inner error path leaked str(e); must be generic."""
        svc = _svc()
        svc.get_leads = AsyncMock(return_value=[])
        svc.get_deals = AsyncMock(return_value=[])

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
                pass

            def close(self):
                pass

        with patch("core.database.SessionLocal", Boom):
            out = await svc.sync_to_postgres_cache("ws1")
        assert out["success"] is False
        assert "db-explode-detail" not in out["error"]
        assert out["error"] == "Zoho CRM metrics sync failed"

    async def test_outer_error_generic(self):
        """RED: outer error path leaked str(e); must be generic."""
        svc = _svc()
        svc.get_leads = AsyncMock(side_effect=RuntimeError("fetch-secret"))
        with patch("core.database.SessionLocal", lambda: None):
            out = await svc.sync_to_postgres_cache("ws1")
        assert out["success"] is False
        assert "fetch-secret" not in out["error"]
        assert out["error"] == "Zoho CRM PostgreSQL cache sync failed"


class TestFullSync:
    async def test_success(self):
        svc = _svc()
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True, "metrics_synced": 3})
        out = await svc.full_sync("ws1")
        assert out["success"] is True
        assert out["workspace_id"] == "ws1"
        assert out["postgres_cache"]["success"] is True
        assert "timestamp" in out
