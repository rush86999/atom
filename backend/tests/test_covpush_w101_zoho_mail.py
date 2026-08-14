# -*- coding: utf-8 -*-
"""Coverage wave 101 — integrations/zoho_mail_service (ZohoMailService).

Standalone, fully mocked (httpx.AsyncClient methods + httpx.Response objects
+ patched SessionLocal), zero network, zero LLM spend. Follows wave-97 zoho
books conventions.

Covers: __init__ (config + env fallbacks), get_capabilities, health_check,
execute_operation (get_accounts / get_recent_inbox / unsupported /
inner-exception -> generic envelope), get_accounts / get_messages (success +
error -> []), get_recent_inbox (success / no accounts -> [] / exception),
sync_to_postgres_cache (success rows, no-accounts fail-closed, existing row
update, inner rollback generic, outer error generic), full_sync.

Bugs fixed (TDD RED -> GREEN):
- execute_operation leaked str(exc); now generic envelope.
- sync_to_postgres_cache inner/outer error paths leaked str(e); now generic.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

import httpx

from integrations.zoho_mail_service import ZohoMailService


def _svc(config=None):
    return ZohoMailService(tenant_id="t1", config=config or {})


def _resp(status=200, payload=None):
    return httpx.Response(status, json=payload if payload is not None else {},
                          request=httpx.Request("GET", "http://x"))


@pytest.fixture()
def db_session_factory():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine("sqlite://")
    from core.models import Base
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


class TestInit:
    def test_config_passthrough(self, monkeypatch):
        monkeypatch.delenv("ZOHO_CLIENT_ID", raising=False)
        monkeypatch.delenv("ZOHO_CLIENT_SECRET", raising=False)
        svc = _svc({"client_id": "cid", "client_secret": "cs"})
        assert svc.client_id == "cid"
        assert svc.client_secret == "cs"
        assert svc.base_url == "https://mail.zoho.com/api/v1"
        assert svc.tenant_id == "t1"

    def test_env_fallbacks(self, monkeypatch):
        monkeypatch.setenv("ZOHO_CLIENT_ID", "env-cid")
        monkeypatch.setenv("ZOHO_CLIENT_SECRET", "env-cs")
        svc = ZohoMailService()
        assert svc.client_id == "env-cid"
        assert svc.client_secret == "env-cs"


class TestCapabilities:
    def test_operations(self):
        caps = _svc().get_capabilities()
        assert caps["operations"] == ['get_accounts', 'get_messages', 'get_recent_inbox']
        assert caps["required_params"] == ["access_token"]
        assert caps["supports_webhooks"] is False


class TestHealthCheck:
    def test_healthy_with_token(self):
        out = _svc({"access_token": "tok"}).health_check()
        assert out["healthy"] is True
        assert out["message"] == "connected"
        assert out["base_url"] == "https://mail.zoho.com/api/v1"

    def test_unhealthy_without_token(self):
        out = _svc().health_check()
        assert out["healthy"] is False
        assert "no access token" in out["message"]


class TestExecuteOperation:
    async def test_get_accounts_op(self):
        svc = _svc()
        svc.get_accounts = AsyncMock(return_value=[{"accountId": "a1"}])
        out = await svc.execute_operation("get_accounts", {"access_token": "tok"})
        assert out["success"] is True
        svc.get_accounts.assert_awaited_once_with("tok")

    async def test_get_accounts_op_falls_back_to_self_token(self):
        svc = _svc({"access_token": "self-tok"})
        svc.get_accounts = AsyncMock(return_value=[])
        out = await svc.execute_operation("get_accounts", {})
        assert out["success"] is True
        svc.get_accounts.assert_awaited_once_with("self-tok")

    async def test_get_recent_inbox_op(self):
        svc = _svc()
        svc.get_recent_inbox = AsyncMock(return_value=[{"id": "m1"}])
        out = await svc.execute_operation("get_recent_inbox", {"access_token": "tok"})
        assert out["success"] is True
        assert out["result"] == [{"id": "m1"}]
        svc.get_recent_inbox.assert_awaited_once_with("tok")

    async def test_unsupported_operation(self):
        out = await _svc().execute_operation("nope", {})
        assert out["success"] is False
        assert "Unsupported operation" in out["error"]
        assert 'get_recent_inbox' in out["supported"]

    async def test_inner_exception_generic_envelope(self):
        """RED: exception path leaked str(exc); must be generic."""
        svc = _svc()
        svc.get_accounts = AsyncMock(side_effect=RuntimeError("secret-detail"))
        out = await svc.execute_operation("get_accounts", {"access_token": "tok"})
        assert out["success"] is False
        assert "secret-detail" not in out["error"]
        assert out["error"] == "Zoho Mail operation failed"


class TestGetAccounts:
    async def test_success(self):
        svc = _svc()
        svc.client.get = AsyncMock(return_value=_resp(200, {"data": [{"accountId": "a1"}]}))
        out = await svc.get_accounts("tok")
        assert out == [{"accountId": "a1"}]
        kwargs = svc.client.get.call_args.kwargs
        assert kwargs["headers"] == {"Authorization": "Zoho-oauthtoken tok"}
        assert svc.client.get.call_args.args[0] == "https://mail.zoho.com/api/v1/accounts"

    async def test_error_returns_empty(self):
        svc = _svc()
        svc.client.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        assert await svc.get_accounts("tok") == []

    async def test_http_500_returns_empty(self):
        svc = _svc()
        svc.client.get = AsyncMock(return_value=_resp(500, {}))
        assert await svc.get_accounts("tok") == []


class TestGetMessages:
    async def test_success(self):
        svc = _svc()
        svc.client.get = AsyncMock(return_value=_resp(200, {"data": [{"messageId": "m1"}]}))
        out = await svc.get_messages("tok", "a1", limit=5)
        assert out == [{"messageId": "m1"}]
        kwargs = svc.client.get.call_args.kwargs
        assert kwargs["params"] == {"limit": 5}
        assert svc.client.get.call_args.args[0].endswith("/accounts/a1/messages/view")

    async def test_default_limit(self):
        svc = _svc()
        svc.client.get = AsyncMock(return_value=_resp(200, {"data": []}))
        await svc.get_messages("tok", "a1")
        assert svc.client.get.call_args.kwargs["params"] == {"limit": 20}

    async def test_error_returns_empty(self):
        svc = _svc()
        svc.client.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        assert await svc.get_messages("tok", "a1") == []


class TestGetRecentInbox:
    async def test_success_uses_first_account(self):
        svc = _svc()
        svc.get_accounts = AsyncMock(return_value=[{"accountId": "a1"}, {"accountId": "a2"}])
        svc.get_messages = AsyncMock(return_value=[{"id": "m1"}])
        out = await svc.get_recent_inbox("tok", limit=7)
        assert out == [{"id": "m1"}]
        svc.get_messages.assert_awaited_once_with("tok", "a1", limit=7)

    async def test_no_accounts_returns_empty(self):
        svc = _svc()
        svc.get_accounts = AsyncMock(return_value=[])
        svc.get_messages = AsyncMock()
        assert await svc.get_recent_inbox("tok") == []
        svc.get_messages.assert_not_awaited()

    async def test_exception_returns_empty(self):
        svc = _svc()
        svc.get_accounts = AsyncMock(side_effect=httpx.ConnectError("net"))
        assert await svc.get_recent_inbox("tok") == []


class TestSyncToPostgresCache:
    async def test_success(self, db_session_factory):
        svc = _svc()
        svc.get_accounts = AsyncMock(return_value=[
            {"accountId": "a1"}, {"accountId": "a2"},
        ])
        svc.get_messages = AsyncMock(return_value=[{"id": "m1"}] * 3)
        with patch("core.database.SessionLocal", db_session_factory):
            out = await svc.sync_to_postgres_cache("u1", "tok")
        assert out["success"] is True
        assert out["metrics_synced"] == 2
        svc.get_messages.assert_awaited_once_with("tok", "a1", limit=100)
        db = db_session_factory()
        from core.models import IntegrationMetric
        rows = db.query(IntegrationMetric).all()
        assert len(rows) == 2
        by_key = {r.metric_key: r for r in rows}
        assert by_key["zoho_mail_account_count"].value == 2.0
        assert by_key["zoho_mail_recent_messages"].value == 3.0
        assert all(r.workspace_id == "u1" for r in rows)
        assert all(r.integration_type == "zoho_mail" for r in rows)
        db.close()

    async def test_no_accounts_fail_closed(self, db_session_factory):
        svc = _svc()
        svc.get_accounts = AsyncMock(return_value=[])
        with patch("core.database.SessionLocal", db_session_factory):
            out = await svc.sync_to_postgres_cache("u1", "tok")
        assert out["success"] is False
        assert out["error"] == "No accounts found"

    async def test_existing_rows_updated(self, db_session_factory):
        svc = _svc()
        svc.get_accounts = AsyncMock(return_value=[{"accountId": "a1"}])
        svc.get_messages = AsyncMock(return_value=[])
        with patch("core.database.SessionLocal", db_session_factory):
            await svc.sync_to_postgres_cache("u1", "tok")
            await svc.sync_to_postgres_cache("u1", "tok")
        db = db_session_factory()
        from core.models import IntegrationMetric
        rows = db.query(IntegrationMetric).all()
        assert len(rows) == 2
        assert all(r.last_synced_at is not None for r in rows)
        db.close()

    async def test_inner_error_rollback_generic(self):
        """RED: inner error path leaked str(e); must be generic."""
        svc = _svc()
        svc.get_accounts = AsyncMock(return_value=[{"accountId": "a1"}])
        svc.get_messages = AsyncMock(return_value=[])

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
            out = await svc.sync_to_postgres_cache("u1", "tok")
        assert out["success"] is False
        assert "db-explode-detail" not in out["error"]
        assert out["error"] == "Zoho Mail metrics sync failed"

    async def test_outer_error_generic(self):
        """RED: outer error path leaked str(e); must be generic."""
        svc = _svc()
        svc.get_accounts = AsyncMock(side_effect=RuntimeError("fetch-secret"))
        with patch("core.database.SessionLocal", lambda: None):
            out = await svc.sync_to_postgres_cache("u1", "tok")
        assert out["success"] is False
        assert "fetch-secret" not in out["error"]
        assert out["error"] == "Zoho Mail PostgreSQL cache sync failed"


class TestFullSync:
    async def test_success(self):
        svc = _svc()
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True, "metrics_synced": 2})
        out = await svc.full_sync("u1", "tok")
        assert out["success"] is True
        assert out["user_id"] == "u1"
        assert out["postgres_cache"]["success"] is True
        assert "timestamp" in out
