# -*- coding: utf-8 -*-
"""Coverage wave 97 — integrations/zoho_inventory_service (ZohoInventoryService).

Standalone, fully mocked (httpx.AsyncClient methods + httpx.Response objects
+ patched SessionLocal), zero network, zero LLM spend. Follows the wave-95
zoom/linear conventions.

Covers: __init__ (config + env fallbacks), get_capabilities, health_check
(token present/absent), execute_operation (get_items / get_inventory_levels /
unsupported / inner-exception -> generic envelope), _get_active_token (tenant
fallback, missing record, valid token, naive-tz expires_at, expired+refresh
success, expired+refresh failure -> None fail-closed, no refresh_token, DB
exception -> None), refresh_token (success/failure), get_items (success,
no-token 401, no-org 400, error -> []), check_stock (success, no-token 401,
no-org 400, error -> generic, NO str(e) leak), get_inventory_levels (success
mapping, error -> []), sync_to_postgres_cache (insert + update paths, inner
rollback generic, outer error generic), full_sync, module factory.

Bugs fixed (TDD RED -> GREEN):
- get_zoho_inventory_service referenced an undefined global `tenant_id`
  (NameError on every call). Now returns ZohoInventoryService(tenant_id="default",
  config=config).
- _get_active_token referenced self.session_id which does not exist on the
  base IntegrationService -> AttributeError for any tenantless call. Now
  getattr(self, "session_id", None).
- check_stock error path leaked str(e) to callers; now a generic message.
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

from integrations.zoho_inventory_service import (
    ZohoInventoryService,
    get_zoho_inventory_service,
    zoho_inventory_service,
)


def _svc(config=None):
    return ZohoInventoryService(tenant_id="t1", config=config or {})


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
        svc = _svc({"client_id": "cid", "client_secret": "cs",
                    "access_token": "tok", "organization_id": "org1"})
        assert svc.client_id == "cid"
        assert svc.client_secret == "cs"
        assert svc.access_token == "tok"
        assert svc.organization_id == "org1"
        assert svc.base_url == "https://inventory.zoho.com/api/v1"
        assert svc.tenant_id == "t1"

    def test_env_fallbacks(self, monkeypatch):
        monkeypatch.setenv("ZOHO_INVENTORY_CLIENT_ID", "env-cid")
        monkeypatch.setenv("ZOHO_INVENTORY_CLIENT_SECRET", "env-cs")
        monkeypatch.setenv("ZOHO_ORG_ID", "env-org")
        svc = ZohoInventoryService()
        assert svc.client_id == "env-cid"
        assert svc.client_secret == "env-cs"
        assert svc.organization_id == "env-org"

    def test_shared_env_fallbacks(self, monkeypatch):
        monkeypatch.delenv("ZOHO_INVENTORY_CLIENT_ID", raising=False)
        monkeypatch.setenv("ZOHO_CLIENT_ID", "shared-cid")
        svc = ZohoInventoryService()
        assert svc.client_id == "shared-cid"


class TestCapabilities:
    def test_operations(self):
        svc = _svc()
        caps = svc.get_capabilities()
        # search_items added 2026-09-03: the live stock-search leg (see
        # tests/test_zoho_inventory_search.py for the root-cause story).
        assert caps["operations"] == ['get_items', 'search_items', 'get_inventory_levels', 'check_stock']
        assert caps["required_params"] == ["access_token"]
        assert caps["supports_webhooks"] is False


class TestHealthCheck:
    def test_healthy_with_token(self):
        svc = _svc({"access_token": "tok"})
        out = svc.health_check()
        assert out["healthy"] is True
        assert out["message"] == "connected"
        assert out["base_url"] == "https://inventory.zoho.com/api/v1"

    def test_unhealthy_without_token(self):
        svc = _svc()
        out = svc.health_check()
        assert out["healthy"] is False
        assert "no access token" in out["message"]


class TestExecuteOperation:
    async def test_get_items_op(self):
        svc = _svc()
        svc.get_items = AsyncMock(return_value=[])
        out = await svc.execute_operation("get_items", {})
        assert out["success"] is True
        assert out["result"] == []

    async def test_get_inventory_levels_op(self):
        svc = _svc()
        svc.get_inventory_levels = AsyncMock(return_value=[])
        out = await svc.execute_operation("get_inventory_levels", {})
        assert out["success"] is True

    async def test_unsupported_operation(self):
        svc = _svc()
        out = await svc.execute_operation("nope", {})
        assert out["success"] is False
        assert "Unsupported operation" in out["error"]
        assert 'get_items' in out["supported"]

    async def test_inner_exception_generic_envelope(self):
        """RED: exception path leaked str(exc); must be generic."""
        svc = _svc()
        svc.get_items = AsyncMock(side_effect=RuntimeError("secret-detail"))
        out = await svc.execute_operation("get_items", {})
        assert out["success"] is False
        assert "secret-detail" not in out["error"]
        assert out["error"] == "Zoho Inventory operation failed"


class TestGetActiveToken:
    async def test_tenantless_falls_back_to_access_token(self):
        """RED: referenced missing self.session_id -> AttributeError before
        the fallback could ever run (session_id is never set by the base
        IntegrationService)."""
        svc = _svc({"access_token": "cfg-tok"})
        svc.tenant_id = None
        token = await svc._get_active_token()
        assert token == "cfg-tok"

    async def test_env_fallback_when_no_attrs(self, monkeypatch):
        monkeypatch.setenv("ZOHO_INVENTORY_ACCESS_TOKEN", "env-tok")
        svc = _svc()
        svc.tenant_id = None
        token = await svc._get_active_token()
        assert token == "env-tok"

    async def test_no_token_record_returns_none(self):
        svc = _svc()
        db = _FakeDB(record=None)
        with patch("core.database.SessionLocal", return_value=db):
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
        with patch("core.database.SessionLocal", return_value=db):
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
        with patch("core.database.SessionLocal", return_value=db):
            token = await svc._get_active_token("tid1")
        assert token == "plain-access"

    async def test_expired_refresh_success_commits(self):
        svc = _svc({"client_id": "cid", "client_secret": "cs"})
        record = _FakeToken(
            access_token="old-enc",
            refresh_token="enc-refresh",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        db = _FakeDB(record=record)
        svc.refresh_token = AsyncMock(return_value={"access_token": "newtok", "expires_in": 3600})
        with patch("core.database.SessionLocal", return_value=db), \
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
        with patch("core.database.SessionLocal", return_value=db), \
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
        with patch("core.database.SessionLocal", return_value=db):
            token = await svc._get_active_token("tid1")
        assert token is None

    async def test_db_exception_returns_none(self):
        svc = _svc()
        db = _FakeDB(record=None, fail_query=True)
        with patch("core.database.SessionLocal", return_value=db):
            token = await svc._get_active_token("tid1")
        assert token is None
        assert db.closed


class TestRefreshToken:
    async def test_success(self):
        svc = _svc({"client_id": "cid", "client_secret": "cs"})
        svc.client.post = AsyncMock(return_value=_resp(200, {"access_token": "new"}))
        out = await svc.refresh_token("rt")
        assert out == {"access_token": "new"}
        data = svc.client.post.call_args.kwargs["data"]
        assert data["grant_type"] == "refresh_token"
        assert data["client_id"] == "cid"
        assert data["client_secret"] == "cs"
        assert data["refresh_token"] == "rt"

    async def test_failure_returns_none(self):
        svc = _svc({"client_id": "cid", "client_secret": "cs"})
        svc.client.post = AsyncMock(side_effect=httpx.ConnectError("net"))
        assert await svc.refresh_token("rt") is None


class TestGetItems:
    async def test_success(self):
        svc = _svc()
        svc.client.get = AsyncMock(return_value=_resp(200, {"items": [{"item_id": "i1"}]}))
        out = await svc.get_items("tok", "org1")
        assert out == [{"item_id": "i1"}]
        kwargs = svc.client.get.call_args.kwargs
        assert kwargs["params"] == {"organization_id": "org1"}
        assert kwargs["headers"]["Authorization"] == "Zoho-oauthtoken tok"

    async def test_config_defaults(self):
        svc = _svc({"access_token": "tok", "organization_id": "org9"})
        svc.client.get = AsyncMock(return_value=_resp(200, {"items": []}))
        assert await svc.get_items() == []
        assert svc.client.get.call_args.kwargs["params"] == {"organization_id": "org9"}

    async def test_no_token_401(self):
        svc = _svc({"organization_id": "org1"})
        svc.client.get = AsyncMock()
        with pytest.raises(HTTPException) as ei:
            await svc.get_items()
        assert ei.value.status_code == 401

    async def test_no_org_400(self):
        svc = _svc({"access_token": "tok"})
        svc.client.get = AsyncMock()
        with pytest.raises(HTTPException) as ei:
            await svc.get_items()
        assert ei.value.status_code == 400
        assert "Organization ID required" in ei.value.detail

    async def test_error_returns_empty(self):
        svc = _svc({"access_token": "tok", "organization_id": "org1"})
        svc.client.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        assert await svc.get_items() == []


class TestCheckStock:
    async def test_success(self):
        svc = _svc()
        svc.client.get = AsyncMock(return_value=_resp(200, {
            "item": {"name": "Widget", "stock_on_hand": 5, "available_stock": 3}}))
        out = await svc.check_stock("i1", "tok", "org1")
        assert out == {"item_id": "i1", "name": "Widget", "stock_on_hand": 5, "available_stock": 3}
        assert svc.client.get.call_args.args[0].endswith("/items/i1")

    async def test_missing_item_fields_default_zero(self):
        svc = _svc()
        svc.client.get = AsyncMock(return_value=_resp(200, {"item": {"name": "X"}}))
        out = await svc.check_stock("i1", "tok", "org1")
        assert out["stock_on_hand"] == 0
        assert out["available_stock"] == 0

    async def test_no_token_401(self):
        svc = _svc({"organization_id": "org1"})
        with pytest.raises(HTTPException) as ei:
            await svc.check_stock("i1")
        assert ei.value.status_code == 401

    async def test_no_org_400(self):
        svc = _svc({"access_token": "tok"})
        with pytest.raises(HTTPException) as ei:
            await svc.check_stock("i1")
        assert ei.value.status_code == 400

    async def test_error_generic_no_leak(self):
        """RED: error path leaked str(e) to the caller; must be generic."""
        svc = _svc({"access_token": "tok", "organization_id": "org1"})
        svc.client.get = AsyncMock(side_effect=httpx.ConnectError("internal-secret"))
        out = await svc.check_stock("i1")
        assert "internal-secret" not in out.get("error", "")


class TestGetInventoryLevels:
    async def test_success_mapping(self):
        svc = _svc()
        svc.get_items = AsyncMock(return_value=[
            {"sku": "A1", "name": "Alpha", "stock_on_hand": 4},
            {"sku": "B2", "name": "Beta"},
        ])
        out = await svc.get_inventory_levels("tok", "org1")
        assert out == [
            {"sku": "A1", "name": "Alpha", "available": 4, "platform": "zoho"},
            {"sku": "B2", "name": "Beta", "available": 0, "platform": "zoho"},
        ]

    async def test_error_returns_empty(self):
        svc = _svc()
        svc.get_items = AsyncMock(side_effect=RuntimeError("boom"))
        assert await svc.get_inventory_levels() == []


@pytest.fixture()
def db_session_factory():
    engine = create_engine("sqlite://")
    from core.models import Base
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


class TestSyncToPostgresCache:
    async def test_success_inserts_metrics(self, db_session_factory):
        svc = _svc()
        svc.get_items = AsyncMock(return_value=[{"item_id": "i1"}, {"item_id": "i2"}])
        with patch("core.database.SessionLocal", db_session_factory):
            out = await svc.sync_to_postgres_cache("u1", "tok", "org1")
        assert out["success"] is True
        assert out["metrics_synced"] == 1
        db = db_session_factory()
        from core.models import IntegrationMetric
        rows = db.query(IntegrationMetric).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.metric_key == "zoho_inventory_item_count"
        assert row.value == 2.0
        assert row.workspace_id == "u1"
        assert row.integration_type == "zoho_inventory"
        db.close()

    async def test_existing_rows_updated(self, db_session_factory):
        svc = _svc()
        svc.get_items = AsyncMock(return_value=[])
        with patch("core.database.SessionLocal", db_session_factory):
            await svc.sync_to_postgres_cache("u1", "tok", "org1")
            await svc.sync_to_postgres_cache("u1", "tok", "org1")
        db = db_session_factory()
        from core.models import IntegrationMetric
        rows = db.query(IntegrationMetric).all()
        assert len(rows) == 1
        assert rows[0].last_synced_at is not None
        db.close()

    async def test_inner_error_rollback_generic(self):
        """RED: inner error path leaked str(e); must be generic."""
        svc = _svc()
        svc.get_items = AsyncMock(return_value=[])

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
            out = await svc.sync_to_postgres_cache("u1", "tok", "org1")
        assert out["success"] is False
        assert "db-explode-detail" not in out["error"]
        assert out["error"] == "Zoho Inventory metrics sync failed"

    async def test_outer_error_generic(self):
        """RED: outer error path leaked str(e); must be generic."""
        svc = _svc()
        svc.get_items = AsyncMock(side_effect=RuntimeError("fetch-secret"))
        with patch("core.database.SessionLocal", lambda: None):
            out = await svc.sync_to_postgres_cache("u1", "tok", "org1")
        assert out["success"] is False
        assert "fetch-secret" not in out["error"]
        assert out["error"] == "Zoho Inventory PostgreSQL cache sync failed"


class TestFullSync:
    async def test_success(self):
        svc = _svc()
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True, "metrics_synced": 1})
        out = await svc.full_sync("u1", "tok", "org1")
        assert out["success"] is True
        assert out["user_id"] == "u1"
        assert out["postgres_cache"]["success"] is True
        assert "timestamp" in out


class TestModuleFactory:
    def test_get_zoho_inventory_service(self):
        """RED: referenced undefined global tenant_id -> NameError on every
        factory call."""
        svc = get_zoho_inventory_service({"access_token": "tok"})
        assert isinstance(svc, ZohoInventoryService)
        assert svc.access_token == "tok"
        assert svc.tenant_id == "default"

    def test_module_singleton(self):
        assert isinstance(zoho_inventory_service, ZohoInventoryService)
