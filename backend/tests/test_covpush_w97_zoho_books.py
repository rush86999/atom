# -*- coding: utf-8 -*-
"""Coverage wave 97 — integrations/zoho_books_service (ZohoBooksService).

Standalone, fully mocked (httpx.AsyncClient methods + httpx.Response objects
+ patched SessionLocal), zero network, zero LLM spend. Follows the wave-95
zoom/linear conventions.

Covers: __init__ (config + env fallbacks), get_capabilities, health_check
(token present/absent), execute_operation (get_organizations / get_contacts /
unsupported / inner-exception -> generic envelope), _get_active_token (tenant
fallback, missing record, valid token, naive-tz expires_at, expired+refresh
success, expired+refresh failure -> None fail-closed, no refresh_token, DB
exception -> None), refresh_token (success/failure), _get_headers,
exchange_token (success / exception -> 400), get_organizations /
get_chart_of_accounts / get_bank_transactions / get_contacts (success +
error -> []), create_contact / create_invoice (success / error -> 500),
sync_to_postgres_cache (with + without bank account, inner rollback generic,
outer error generic), full_sync, module factory get_zoho_books_service.

Bugs fixed (TDD RED -> GREEN):
- get_zoho_books_service referenced an undefined global `tenant_id`
  (NameError on every call). Now returns ZohoBooksService(tenant_id="default",
  config=config).
- _get_active_token referenced self.session_id which does not exist on the
  base IntegrationService -> AttributeError for any tenantless call, making
  the access-token fallback branch dead code. Now getattr(self, "session_id",
  None).
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

from integrations.zoho_books_service import (
    ZohoBooksService,
    get_zoho_books_service,
    zoho_books_service,
)


def _svc(config=None):
    return ZohoBooksService(tenant_id="t1", config=config or {})


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
        self.rollbacks = 0
        self.closed = False

    def query(self, model):
        if self._fail_query:
            raise RuntimeError("db-query-secret")
        return _FakeQuery(self._record)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class TestInit:
    def test_config_passthrough(self):
        svc = _svc({"client_id": "cid", "client_secret": "cs", "access_token": "tok"})
        assert svc.client_id == "cid"
        assert svc.client_secret == "cs"
        assert svc.access_token == "tok"
        assert svc.base_url == "https://www.zohoapis.com/books/v3"
        assert svc.tenant_id == "t1"

    def test_env_fallbacks(self, monkeypatch):
        monkeypatch.setenv("ZOHO_BOOKS_CLIENT_ID", "env-cid")
        monkeypatch.setenv("ZOHO_BOOKS_CLIENT_SECRET", "env-cs")
        svc = ZohoBooksService()
        assert svc.client_id == "env-cid"
        assert svc.client_secret == "env-cs"
        assert svc.access_token is None

    def test_shared_env_fallbacks(self, monkeypatch):
        monkeypatch.delenv("ZOHO_BOOKS_CLIENT_ID", raising=False)
        monkeypatch.setenv("ZOHO_CLIENT_ID", "shared-cid")
        svc = ZohoBooksService()
        assert svc.client_id == "shared-cid"


class TestCapabilities:
    def test_operations(self):
        svc = _svc()
        caps = svc.get_capabilities()
        assert caps["operations"] == ['get_organizations', 'get_contacts', 'get_bank_transactions']
        assert caps["required_params"] == ["access_token"]
        assert caps["supports_webhooks"] is False
        assert caps["rate_limits"] == {"requests_per_minute": 100}


class TestHealthCheck:
    def test_healthy_with_token(self):
        svc = _svc({"access_token": "tok"})
        out = svc.health_check()
        assert out["healthy"] is True
        assert out["message"] == "connected"
        assert "last_check" in out
        assert out["base_url"] == "https://www.zohoapis.com/books/v3"

    def test_unhealthy_without_token(self):
        svc = _svc()
        out = svc.health_check()
        assert out["healthy"] is False
        assert "no access token" in out["message"]


class TestExecuteOperation:
    async def test_get_organizations_op(self):
        svc = _svc()
        svc.get_organizations = AsyncMock(return_value=[{"organization_id": "o1"}])
        out = await svc.execute_operation("get_organizations", {"access_token": "tok"})
        assert out["success"] is True
        assert out["result"] == [{"organization_id": "o1"}]

    async def test_get_contacts_op(self):
        svc = _svc()
        svc.get_contacts = AsyncMock(return_value=[])
        out = await svc.execute_operation("get_contacts", {"organization_id": "o1"})
        assert out["success"] is True
        assert svc.get_contacts.call_args.args[1] == "o1"

    async def test_unsupported_operation(self):
        svc = _svc()
        out = await svc.execute_operation("nope", {})
        assert out["success"] is False
        assert "Unsupported operation" in out["error"]
        assert 'get_organizations' in out["supported"]

    async def test_inner_exception_generic_envelope(self):
        """RED: exception path leaked str(exc); must be generic."""
        svc = _svc()
        svc.get_organizations = AsyncMock(side_effect=RuntimeError("secret-detail"))
        out = await svc.execute_operation("get_organizations", {})
        assert out["success"] is False
        assert "secret-detail" not in out["error"]
        assert out["error"] == "Zoho Books operation failed"


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
        monkeypatch.setenv("ZOHO_BOOKS_ACCESS_TOKEN", "env-tok")
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
        # Caller gets a usable bearer token — the ciphertext stored on the
        # row is decrypted before returning (same fix as zoho_inventory).
        assert token == "refresh-plain"
        assert db.commits == 1
        assert record.access_token == "enc-newtok"
        stamp.assert_called_once_with(record)
        svc.refresh_token.assert_awaited_once_with("refresh-plain")

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
             patch("core.privsec.token_encryption.decrypt_token", return_value="refresh-plain"):
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
        assert db.commits == 0

    async def test_no_expiry_refreshes(self):
        svc = _svc()
        record = _FakeToken(
            access_token="old",
            refresh_token="enc-refresh",
            expires_at=None,
        )
        db = _FakeDB(record=record)
        svc.refresh_token = AsyncMock(return_value={"access_token": "new"})
        with patch("core.database.SessionLocal", return_value=db), \
             patch("core.privsec.token_encryption.decrypt_token", return_value="rp"), \
             patch("core.privsec.token_encryption.encrypt_token", return_value="enc-new"), \
             patch("core.privsec.token_encryption.stamp_credential_metadata"):
            token = await svc._get_active_token("tid1")
        assert token == "rp"  # decrypted, not the stored ciphertext

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
        kwargs = svc.client.post.call_args.kwargs
        assert kwargs["data"]["grant_type"] == "refresh_token"
        assert kwargs["data"]["client_id"] == "cid"
        assert kwargs["data"]["client_secret"] == "cs"
        assert kwargs["data"]["refresh_token"] == "rt"

    async def test_failure_returns_none(self):
        svc = _svc({"client_id": "cid", "client_secret": "cs"})
        svc.client.post = AsyncMock(side_effect=httpx.ConnectError("net"))
        assert await svc.refresh_token("rt") is None


class TestHeaders:
    def test_get_headers(self):
        svc = _svc()
        h = svc._get_headers("tok", "org1")
        assert h["Authorization"] == "Zoho-oauthtoken tok"
        assert h["Accept"] == "application/json"


class TestExchangeToken:
    async def test_success(self):
        svc = _svc({"client_id": "cid", "client_secret": "cs"})
        svc.client.post = AsyncMock(return_value=_resp(200, {"access_token": "a", "refresh_token": "r"}))
        out = await svc.exchange_token("code1", "http://cb")
        assert out["access_token"] == "a"
        kwargs = svc.client.post.call_args.kwargs
        assert kwargs["data"]["grant_type"] == "authorization_code"
        assert kwargs["data"]["code"] == "code1"
        assert kwargs["data"]["redirect_uri"] == "http://cb"

    async def test_exception_400(self):
        svc = _svc({"client_id": "cid", "client_secret": "cs"})
        svc.client.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
        with pytest.raises(HTTPException) as ei:
            await svc.exchange_token("code1", "http://cb")
        assert ei.value.status_code == 400
        assert ei.value.detail == "Internal error"


class TestOrganizations:
    async def test_success(self):
        svc = _svc()
        svc.client.get = AsyncMock(return_value=_resp(200, {"organizations": [{"organization_id": "o1"}]}))
        out = await svc.get_organizations("tok")
        assert out == [{"organization_id": "o1"}]
        assert svc.client.get.call_args.kwargs["headers"] == {"Authorization": "Zoho-oauthtoken tok"}

    async def test_error_returns_empty(self):
        svc = _svc()
        svc.client.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        assert await svc.get_organizations("tok") == []


class TestChartOfAccounts:
    async def test_success(self):
        svc = _svc()
        svc.client.get = AsyncMock(return_value=_resp(200, {"chartofaccounts": [{"account_id": "a1"}]}))
        out = await svc.get_chart_of_accounts("tok", "org1")
        assert out == [{"account_id": "a1"}]
        kwargs = svc.client.get.call_args.kwargs
        assert kwargs["params"] == {"organization_id": "org1"}
        assert kwargs["headers"]["Authorization"] == "Zoho-oauthtoken tok"

    async def test_error_returns_empty(self):
        svc = _svc()
        svc.client.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        assert await svc.get_chart_of_accounts("tok", "org1") == []


class TestBankTransactions:
    async def test_success(self):
        svc = _svc()
        svc.client.get = AsyncMock(return_value=_resp(200, {"banktransactions": [{"transaction_id": "t1"}]}))
        out = await svc.get_bank_transactions("tok", "org1", "acc1")
        assert out == [{"transaction_id": "t1"}]
        assert svc.client.get.call_args.kwargs["params"] == {"organization_id": "org1", "account_id": "acc1"}

    async def test_error_returns_empty(self):
        svc = _svc()
        svc.client.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        assert await svc.get_bank_transactions("tok", "org1", "acc1") == []


class TestContacts:
    async def test_success(self):
        svc = _svc()
        svc.client.get = AsyncMock(return_value=_resp(200, {"contacts": [{"contact_id": "c1"}]}))
        out = await svc.get_contacts("tok", "org1")
        assert out == [{"contact_id": "c1"}]

    async def test_error_returns_empty(self):
        svc = _svc()
        svc.client.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        assert await svc.get_contacts("tok", "org1") == []


class TestCreateContact:
    async def test_success(self):
        svc = _svc()
        svc.client.post = AsyncMock(return_value=_resp(201, {"contact": {"contact_id": "c9"}}))
        out = await svc.create_contact("tok", "org1", {"contact_name": "ACME"})
        assert out == {"contact_id": "c9"}
        assert svc.client.post.call_args.kwargs["json"] == {"contact_name": "ACME"}

    async def test_error_500_generic(self):
        svc = _svc()
        svc.client.post = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.create_contact("tok", "org1", {})
        assert ei.value.status_code == 500
        assert ei.value.detail == "Zoho Contact creation failed"
        assert "net" not in ei.value.detail


class TestCreateInvoice:
    async def test_success(self):
        svc = _svc()
        svc.client.post = AsyncMock(return_value=_resp(201, {"invoice": {"invoice_id": "i9"}}))
        out = await svc.create_invoice("tok", "org1", {"customer_id": "c1"})
        assert out == {"invoice_id": "i9"}

    async def test_error_500_generic(self):
        svc = _svc()
        svc.client.post = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.create_invoice("tok", "org1", {})
        assert ei.value.status_code == 500
        assert ei.value.detail == "Zoho Invoice creation failed"


@pytest.fixture()
def db_session_factory():
    engine = create_engine("sqlite://")
    from core.models import Base
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


class TestSyncToPostgresCache:
    async def test_success_with_bank_account(self, db_session_factory):
        svc = _svc()
        svc.get_chart_of_accounts = AsyncMock(return_value=[
            {"account_id": "bank1", "account_type": "bank"},
            {"account_id": "acct1", "account_type": "expense"},
        ])
        svc.get_bank_transactions = AsyncMock(return_value=[{"transaction_id": "t1"}, {"transaction_id": "t2"}])
        with patch("core.database.SessionLocal", db_session_factory):
            out = await svc.sync_to_postgres_cache("u1", "tok", "org1")
        assert out["success"] is True
        assert out["metrics_synced"] == 2
        svc.get_bank_transactions.assert_awaited_once_with("tok", "org1", "bank1")
        db = db_session_factory()
        from core.models import IntegrationMetric
        rows = db.query(IntegrationMetric).all()
        assert len(rows) == 2
        by_key = {r.metric_key: r for r in rows}
        assert by_key["zoho_books_coa_count"].value == 2.0
        assert by_key["zoho_books_recent_transactions"].value == 2.0
        assert all(r.workspace_id == "u1" for r in rows)
        assert all(r.integration_type == "zoho_books" for r in rows)
        db.close()

    async def test_success_without_bank_account(self, db_session_factory):
        svc = _svc()
        svc.get_chart_of_accounts = AsyncMock(return_value=[
            {"account_id": "acct1", "account_type": "expense"},
        ])
        svc.get_bank_transactions = AsyncMock()
        with patch("core.database.SessionLocal", db_session_factory):
            out = await svc.sync_to_postgres_cache("u1", "tok", "org1")
        assert out["success"] is True
        svc.get_bank_transactions.assert_not_awaited()

    async def test_existing_rows_updated(self, db_session_factory):
        svc = _svc()
        svc.get_chart_of_accounts = AsyncMock(return_value=[])
        with patch("core.database.SessionLocal", db_session_factory):
            await svc.sync_to_postgres_cache("u1", "tok", "org1")
            await svc.sync_to_postgres_cache("u1", "tok", "org1")
        db = db_session_factory()
        from core.models import IntegrationMetric
        rows = db.query(IntegrationMetric).all()
        assert len(rows) == 2
        assert all(r.last_synced_at is not None for r in rows)
        db.close()

    async def test_inner_error_rollback_generic(self):
        """RED: inner error path leaked str(e); must be generic."""
        svc = _svc()
        svc.get_chart_of_accounts = AsyncMock(return_value=[])

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
        assert out["error"] == "Zoho Books metrics sync failed"

    async def test_outer_error_generic(self):
        """RED: outer error path leaked str(e); must be generic."""
        svc = _svc()
        svc.get_chart_of_accounts = AsyncMock(side_effect=RuntimeError("fetch-secret"))
        with patch("core.database.SessionLocal", lambda: None):
            out = await svc.sync_to_postgres_cache("u1", "tok", "org1")
        assert out["success"] is False
        assert "fetch-secret" not in out["error"]
        assert out["error"] == "Zoho Books PostgreSQL cache sync failed"


class TestFullSync:
    async def test_success(self):
        svc = _svc()
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True, "metrics_synced": 2})
        out = await svc.full_sync("u1", "tok", "org1")
        assert out["success"] is True
        assert out["user_id"] == "u1"
        assert out["postgres_cache"]["success"] is True
        assert "timestamp" in out


class TestModuleFactory:
    def test_get_zoho_books_service(self):
        """RED: referenced undefined global tenant_id -> NameError on every
        factory call."""
        svc = get_zoho_books_service({"access_token": "tok"})
        assert isinstance(svc, ZohoBooksService)
        assert svc.access_token == "tok"
        assert svc.tenant_id == "default"

    def test_module_singleton(self):
        assert isinstance(zoho_books_service, ZohoBooksService)
