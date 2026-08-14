# -*- coding: utf-8 -*-
"""Coverage wave 97 — integrations/mailchimp_service (MailchimpService).

Standalone, fully mocked (IntegrationHTTP + httpx.Response objects + patched
SessionLocal), zero network, zero LLM spend. Follows the wave-95
zoom/linear conventions.

Covers: __init__ (config provided/empty), close, get_capabilities,
health_check (healthy/exception -> generic message, NO str(e) leak),
execute_operation (get_audiences / get_campaigns / get_account_info /
unknown op / inner-exception -> generic envelope, no str(e) leak),
_get_base_url, _get_headers, exchange_token (success stores nothing, error
propagates as httpx error), get_metadata (success, error propagates),
get_audiences (success with params, error propagates), get_campaigns
(with/without status, error propagates), get_account_info (success, error
propagates), sync_to_postgres_cache (with creds -> counts from mocked
get_audiences/get_campaigns, without creds -> zero counts, audience/campaign
API failure tolerated, inner rollback generic, outer error generic),
full_sync (success).

Bugs fixed (TDD RED -> GREEN):
- sync_to_postgres_cache used the phantom IntegrationMetric.tenant_id column
  (filter_by + constructor) -> InvalidRequestError on every sync; now uses the
  real workspace_id column (same bug class as wave-95 Linear).
- health_check exception path leaked str(e); now generic message.
- execute_operation exception path leaked str(e); now generic envelope.
- sync_to_postgres_cache inner/outer error paths leaked str(e); now generic.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from integrations.mailchimp_service import MailchimpService


def _svc(config=None):
    return MailchimpService(tenant_id="t1", config=config or {})


def _resp(status=200, payload=None):
    return httpx.Response(status, json=payload if payload is not None else {},
                          request=httpx.Request("GET", "http://x"))


class TestInit:
    def test_config_passthrough(self):
        svc = _svc({"client_id": "cid", "client_secret": "cs"})
        assert svc.client_id == "cid"
        assert svc.client_secret == "cs"
        assert svc.tenant_id == "t1"

    def test_empty_config(self):
        svc = MailchimpService()
        assert svc.client_id is None
        assert svc.client_secret is None

    async def test_close(self):
        svc = _svc()
        svc.client.aclose = AsyncMock()
        await svc.close()
        svc.client.aclose.assert_awaited_once()


class TestCapabilities:
    def test_operations(self):
        svc = _svc()
        caps = svc.get_capabilities()
        ops = {o["id"] for o in caps["operations"]}
        assert ops == {"get_audiences", "get_campaigns", "get_account_info", "sync_metrics"}
        assert caps["required_params"] == ["access_token", "server_prefix"]
        assert caps["supports_webhooks"] is True


class TestHealthCheck:
    def test_healthy(self):
        svc = _svc()
        out = svc.health_check()
        assert out["healthy"] is True
        assert "operational" in out["message"]
        assert "last_check" in out

    def test_exception_path_generic(self):
        """RED: exception path leaked str(e); must be generic."""
        svc = _svc()
        with patch("integrations.mailchimp_service.datetime") as dt:
            dt.now.side_effect = RuntimeError("clock-secret-detail")
            out = svc.health_check()
        assert out["healthy"] is False
        assert "clock-secret-detail" not in out["message"]
        assert out["message"] == "Mailchimp service health check failed"


class TestExecuteOperation:
    async def test_get_audiences_op(self):
        svc = _svc()
        svc.get_audiences = AsyncMock(return_value=[{"id": "a1"}])
        out = await svc.execute_operation("get_audiences",
                                          {"access_token": "tok", "server_prefix": "us5", "limit": 5})
        assert out["success"] is True
        assert out["result"] == [{"id": "a1"}]
        assert out["details"] == {}
        assert svc.get_audiences.call_args.args[2] == 5

    async def test_get_campaigns_op(self):
        svc = _svc()
        svc.get_campaigns = AsyncMock(return_value=[])
        out = await svc.execute_operation("get_campaigns",
                                          {"access_token": "tok", "server_prefix": "us5",
                                           "limit": 10, "status": "sent"})
        assert out["success"] is True
        assert svc.get_campaigns.call_args.args[3] == "sent"

    async def test_get_account_info_op(self):
        svc = _svc()
        svc.get_account_info = AsyncMock(return_value={"account_id": "x"})
        out = await svc.execute_operation("get_account_info",
                                          {"access_token": "tok", "server_prefix": "us5"})
        assert out["success"] is True
        assert out["result"] == {"account_id": "x"}

    async def test_unknown_operation(self):
        svc = _svc()
        out = await svc.execute_operation("nope", {})
        assert out["success"] is False
        assert "Unknown operation" in out["error"]

    async def test_inner_exception_generic_envelope(self):
        """RED: exception path leaked str(e); must be generic."""
        svc = _svc()
        svc.get_audiences = AsyncMock(side_effect=RuntimeError("secret-detail"))
        out = await svc.execute_operation("get_audiences", {})
        assert out["success"] is False
        assert "secret-detail" not in out["error"]
        assert out["error"] == "Mailchimp operation failed"


class TestBaseUrlAndHeaders:
    def test_get_base_url(self):
        svc = _svc()
        assert svc._get_base_url("us5") == "https://us5.api.mailchimp.com/3.0"

    def test_get_headers(self):
        svc = _svc()
        h = svc._get_headers("tok")
        assert h["Authorization"] == "Bearer tok"
        assert h["Accept"] == "application/json"
        assert "Content-Type" not in h


class TestExchangeToken:
    async def test_success(self):
        svc = _svc({"client_id": "cid", "client_secret": "cs"})
        svc.http.post = AsyncMock(return_value=_resp(200, {"access_token": "newtok"}))
        out = await svc.exchange_token("code1", "http://cb")
        assert out["access_token"] == "newtok"
        data = svc.http.post.call_args.kwargs["data"]
        assert data["grant_type"] == "authorization_code"
        assert data["client_id"] == "cid"
        assert data["client_secret"] == "cs"
        assert data["redirect_uri"] == "http://cb"
        assert data["code"] == "code1"

    async def test_error_propagates(self):
        svc = _svc({"client_id": "cid", "client_secret": "cs"})
        svc.http.post = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(httpx.ConnectError):
            await svc.exchange_token("code1", "http://cb")


class TestGetMetadata:
    async def test_success(self):
        svc = _svc()
        svc.http.get = AsyncMock(return_value=_resp(200, {"dc": "us5"}))
        out = await svc.get_metadata("tok")
        assert out == {"dc": "us5"}
        assert svc.http.get.call_args.kwargs["headers"] == {"Authorization": "OAuth tok"}

    async def test_error_propagates(self):
        svc = _svc()
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(httpx.ConnectError):
            await svc.get_metadata("tok")


class TestGetAudiences:
    async def test_success(self):
        svc = _svc()
        svc.http.get = AsyncMock(return_value=_resp(200, {"lists": [{"id": "l1"}]}))
        out = await svc.get_audiences("tok", "us5", limit=7)
        assert out == [{"id": "l1"}]
        kwargs = svc.http.get.call_args.kwargs
        assert kwargs["params"] == {"count": 7}
        assert kwargs["headers"]["Authorization"] == "Bearer tok"
        assert svc.http.get.call_args.args[1] == "https://us5.api.mailchimp.com/3.0/lists"

    async def test_error_propagates(self):
        svc = _svc()
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(httpx.ConnectError):
            await svc.get_audiences("tok", "us5")


class TestGetCampaigns:
    async def test_with_status(self):
        svc = _svc()
        svc.http.get = AsyncMock(return_value=_resp(200, {"campaigns": [{"id": "c1"}]}))
        out = await svc.get_campaigns("tok", "us5", limit=3, status="sent")
        assert out == [{"id": "c1"}]
        assert svc.http.get.call_args.kwargs["params"] == {"count": 3, "status": "sent"}

    async def test_without_status(self):
        svc = _svc()
        svc.http.get = AsyncMock(return_value=_resp(200, {"campaigns": []}))
        await svc.get_campaigns("tok", "us5")
        assert svc.http.get.call_args.kwargs["params"] == {"count": 20}

    async def test_error_propagates(self):
        svc = _svc()
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(httpx.ConnectError):
            await svc.get_campaigns("tok", "us5")


class TestGetAccountInfo:
    async def test_success(self):
        svc = _svc()
        svc.http.get = AsyncMock(return_value=_resp(200, {"account_id": "x"}))
        out = await svc.get_account_info("tok", "us5")
        assert out == {"account_id": "x"}
        assert svc.http.get.call_args.args[1] == "https://us5.api.mailchimp.com/3.0/"

    async def test_error_propagates(self):
        svc = _svc()
        svc.http.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(httpx.ConnectError):
            await svc.get_account_info("tok", "us5")


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
        svc.get_audiences = AsyncMock(return_value=[{"id": "a1"}, {"id": "a2"}])
        svc.get_campaigns = AsyncMock(return_value=[{"id": "c1"}])
        with patch("core.database.SessionLocal", db_session_factory):
            out = await svc.sync_to_postgres_cache("ws1", "tok", "us5")
        assert out["success"] is True
        assert out["metrics_synced"] == 2
        svc.get_audiences.assert_awaited_once_with("tok", "us5")
        db = db_session_factory()
        from core.models import IntegrationMetric
        rows = db.query(IntegrationMetric).all()
        assert len(rows) == 2
        by_key = {r.metric_key: r for r in rows}
        assert by_key["mailchimp_audience_count"].value == 2.0
        assert by_key["mailchimp_campaign_count"].value == 1.0
        assert all(r.workspace_id == "ws1" for r in rows)
        assert all(r.integration_type == "mailchimp" for r in rows)
        db.close()

    async def test_without_creds_zero_counts(self, db_session_factory):
        svc = _svc()
        with patch("core.database.SessionLocal", db_session_factory):
            out = await svc.sync_to_postgres_cache("ws1")
        assert out["success"] is True
        db = db_session_factory()
        from core.models import IntegrationMetric
        rows = db.query(IntegrationMetric).all()
        assert len(rows) == 2
        assert all(r.value == 0.0 for r in rows)
        db.close()

    async def test_api_failures_tolerated(self, db_session_factory):
        svc = _svc()
        svc.get_audiences = AsyncMock(side_effect=httpx.ConnectError("net"))
        svc.get_campaigns = AsyncMock(side_effect=httpx.ConnectError("net"))
        with patch("core.database.SessionLocal", db_session_factory):
            out = await svc.sync_to_postgres_cache("ws1", "tok", "us5")
        assert out["success"] is True
        assert out["metrics_synced"] == 2

    async def test_existing_rows_updated(self, db_session_factory):
        svc = _svc()
        svc.get_audiences = AsyncMock(return_value=[])
        svc.get_campaigns = AsyncMock(return_value=[])
        with patch("core.database.SessionLocal", db_session_factory):
            await svc.sync_to_postgres_cache("ws1", "tok", "us5")
            await svc.sync_to_postgres_cache("ws1", "tok", "us5")
        db = db_session_factory()
        from core.models import IntegrationMetric
        rows = db.query(IntegrationMetric).all()
        assert len(rows) == 2
        assert all(r.last_synced_at is not None for r in rows)
        db.close()

    async def test_inner_error_rollback_generic(self):
        """RED: inner error path leaked str(e); must be generic."""
        svc = _svc()
        svc.get_audiences = AsyncMock(return_value=[])
        svc.get_campaigns = AsyncMock(return_value=[])

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
            out = await svc.sync_to_postgres_cache("ws1", "tok", "us5")
        assert out["success"] is False
        assert "db-explode-detail" not in out["error"]
        assert out["error"] == "Mailchimp metrics sync failed"

    async def test_outer_error_generic(self):
        """RED: outer error path leaked str(e); must be generic."""
        svc = _svc()
        svc.get_audiences = AsyncMock(side_effect=RuntimeError("fetch-secret"))
        svc.get_campaigns = AsyncMock(side_effect=RuntimeError("fetch-secret"))
        with patch("core.database.SessionLocal", lambda: None):
            out = await svc.sync_to_postgres_cache("ws1", "tok", "us5")
        assert out["success"] is False
        assert "fetch-secret" not in out["error"]
        assert out["error"] == "Mailchimp PostgreSQL cache sync failed"


class TestFullSync:
    async def test_success(self):
        svc = _svc()
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True, "metrics_synced": 2})
        out = await svc.full_sync("ws1", "tok", "us5")
        assert out["success"] is True
        assert out["workspace_id"] == "ws1"
        assert out["postgres_cache"]["success"] is True
        assert "timestamp" in out
