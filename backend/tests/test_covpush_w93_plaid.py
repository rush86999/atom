"""Coverage wave 93 — integrations/plaid_service.py (TDD, 0% baseline).

Pure service class — no FastAPI routes. Every HTTP interaction goes through
the module's `IntegrationHTTP` instance (patched with MagicMock) so nothing
touches the network. The DB cache-sync path is exercised with a mocked
SessionLocal.

Covers: capabilities, execute_operation (all 4 ops + cross-tenant denial +
missing token + unknown op + exception containment), close, auth-payload/
headers helpers, create_link_token, exchange_public_token, get_accounts,
get_balance, get_transactions, get_identity, remove_item (success + HTTP
error -> 400 + missing-credentials -> 401), health_check (missing creds /
healthy / unhealthy / exception), sync_to_postgres_cache (insert + update +
commit-failure rollback + inner + outer error), full_sync.

No LLM spend, no network.
"""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from integrations.plaid_service import PlaidService


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture
def svc():
    s = PlaidService(config={
        "plaid_client_id": "client-1",
        "plaid_secret": "secret-1",
        "plaid_environment": "sandbox",
    })
    s.http = MagicMock()  # replace IntegrationHTTP with a full mock
    s.http.post = AsyncMock()  # await-able post
    yield s
    run(s.close())


@pytest.fixture
def unauthed_svc():
    return PlaidService(config={})


def _http_response(payload=None):
    resp = MagicMock()
    resp.json.return_value = payload if payload is not None else {"ok": True}
    return resp


class TestInitAndCapabilities:
    def test_environment_urls(self):
        for env, url in [
            ("sandbox", "https://sandbox.plaid.com"),
            ("development", "https://development.plaid.com"),
            ("production", "https://production.plaid.com"),
        ]:
            s = PlaidService(config={
                "plaid_client_id": "c", "plaid_secret": "s",
                "plaid_environment": env})
            assert s.base_url == url
            run(s.close())

    def test_unknown_environment_falls_back_sandbox(self):
        s = PlaidService(config={
            "plaid_client_id": "c", "plaid_secret": "s",
            "plaid_environment": "weird"})
        assert s.base_url == "https://sandbox.plaid.com"
        run(s.close())

    def test_env_var_fallback(self, monkeypatch):
        monkeypatch.setenv("PLAID_CLIENT_ID", "env-c")
        monkeypatch.setenv("PLAID_SECRET", "env-s")
        monkeypatch.setenv("PLAID_ENVIRONMENT", "development")
        s = PlaidService()
        assert s.client_id == "env-c"
        assert s.secret == "env-s"
        assert s.base_url == "https://development.plaid.com"
        run(s.close())

    def test_capabilities_structure(self, svc):
        caps = svc.get_capabilities()
        assert caps["required_params"] == ["access_token"]
        ops = {o["id"] for o in caps["operations"]}
        assert ops == {"get_accounts", "get_balance", "get_transactions",
                       "get_identity"}
        assert caps["rate_limits"]["requests_per_minute"] == 100
        assert caps["supports_webhooks"] is True

    def test_headers_and_auth_payload(self, svc):
        assert svc._get_headers() == {"Content-Type": "application/json"}
        payload = svc._get_auth_payload()
        assert payload == {"client_id": "client-1", "secret": "secret-1"}


class TestExecuteOperation:
    def test_get_accounts_success(self, svc):
        with patch.object(svc, "get_accounts",
                          new=AsyncMock(return_value=[{"id": "a1"}])):
            result = run(svc.execute_operation(
                "get_accounts", {"access_token": "tok"}))
        assert result["success"] is True
        assert result["result"] == [{"id": "a1"}]
        assert result["details"]["tenant_id"] == "default"

    def test_get_balance_success(self, svc):
        with patch.object(svc, "get_balance",
                          new=AsyncMock(return_value={"balances": []})):
            result = run(svc.execute_operation(
                "get_balance", {"access_token": "tok"}))
        assert result["success"] is True

    def test_get_transactions_success(self, svc):
        with patch.object(svc, "get_transactions",
                          new=AsyncMock(return_value={"transactions": []})) as gt:
            result = run(svc.execute_operation(
                "get_transactions", {"access_token": "tok"}))
        assert result["success"] is True
        gt.assert_awaited_once_with("tok", "2000-01-01", "2099-01-01")

    def test_get_transactions_custom_dates(self, svc):
        with patch.object(svc, "get_transactions",
                          new=AsyncMock(return_value={})) as gt:
            run(svc.execute_operation("get_transactions", {
                "access_token": "tok",
                "start_date": "2026-01-01", "end_date": "2026-02-01"}))
        gt.assert_awaited_once_with("tok", "2026-01-01", "2026-02-01")

    def test_get_identity_success(self, svc):
        with patch.object(svc, "get_identity",
                          new=AsyncMock(return_value={"identity": []})):
            result = run(svc.execute_operation(
                "get_identity", {"access_token": "tok"}))
        assert result["success"] is True

    def test_cross_tenant_denied(self):
        s = PlaidService(config={"plaid_client_id": "c", "plaid_secret": "s",
                                 "plaid_environment": "sandbox",
                                 "tenant_id": "tenant-a"})
        try:
            result = run(s.execute_operation(
                "get_accounts", {"access_token": "tok"},
                context={"tenant_id": "tenant-b"}))
        finally:
            run(s.close())
        assert result["success"] is False
        assert "cross_tenant_access_prevented" in result["details"]["reason"]

    def test_same_tenant_allowed(self, svc):
        with patch.object(svc, "get_accounts",
                          new=AsyncMock(return_value=[])):
            result = run(svc.execute_operation(
                "get_accounts", {"access_token": "tok"},
                context={"tenant_id": "default"}))
        assert result["success"] is True

    def test_missing_token(self, svc):
        result = run(svc.execute_operation("get_accounts", {}))
        assert result["success"] is False
        assert result["error"] == "Missing Plaid access token"

    def test_unknown_operation(self, svc):
        result = run(svc.execute_operation("delete_everything",
                                           {"access_token": "tok"}))
        assert result["success"] is False
        assert result["error"] == "Plaid operation failed"

    def test_operation_exception_contained_no_leak(self, svc):
        """Failure is generic; internal exception detail stays server-side."""
        with patch.object(svc, "get_accounts",
                          new=AsyncMock(side_effect=ValueError("secret-1"))):
            result = run(svc.execute_operation(
                "get_accounts", {"access_token": "tok"}))
        assert result["success"] is False
        assert result["error"] == "Plaid operation failed"
        assert "secret-1" not in str(result)


class TestLinkAndExchange:
    def test_create_link_token_success(self, svc):
        resp = _http_response({"link_token": "lt-1"})
        svc.http.post.return_value = resp
        result = run(svc.create_link_token(
            "user-1", client_name="ACME", country_codes=["US"],
            language="en", products=["auth"]))
        assert result == {"link_token": "lt-1"}
        url = svc.http.post.call_args[0][1]
        assert url.endswith("/link/token/create")
        payload = svc.http.post.call_args[1]["json"]
        assert payload["user"] == {"client_user_id": "user-1"}
        assert payload["client_name"] == "ACME"
        assert payload["products"] == ["auth"]

    def test_create_link_token_defaults(self, svc):
        svc.http.post.return_value = _http_response({})
        run(svc.create_link_token("u1"))
        payload = svc.http.post.call_args[1]["json"]
        assert payload["products"] == ["auth", "transactions"]
        assert payload["country_codes"] == ["US"]

    def test_create_link_token_http_error_400(self, svc):
        svc.http.post.return_value = _http_response()
        svc.http.post.return_value.raise_for_status.side_effect = \
            httpx.ConnectError("connection refused")
        with pytest.raises(Exception) as exc:
            run(svc.create_link_token("u1"))
        assert exc.value.status_code == 400

    def test_create_link_token_missing_creds_401(self, unauthed_svc):
        with pytest.raises(Exception) as exc:
            run(unauthed_svc.create_link_token("u1"))
        assert exc.value.status_code == 401

    def test_exchange_public_token_success(self, svc):
        resp = _http_response({"access_token": "at-1"})
        svc.http.post.return_value = resp
        result = run(svc.exchange_public_token("pub-1"))
        assert result == {"access_token": "at-1"}
        assert svc.http.post.call_args[0][1].endswith(
            "/item/public_token/exchange")
        assert svc.http.post.call_args[1]["json"]["public_token"] == "pub-1"

    def test_exchange_public_token_http_error_400(self, svc):
        svc.http.post.return_value = _http_response()
        svc.http.post.return_value.raise_for_status.side_effect = \
            httpx.ConnectError("down")
        with pytest.raises(Exception) as exc:
            run(svc.exchange_public_token("pub-1"))
        assert exc.value.status_code == 400

    def test_exchange_public_token_missing_creds_401(self, unauthed_svc):
        with pytest.raises(Exception) as exc:
            run(unauthed_svc.exchange_public_token("pub-1"))
        assert exc.value.status_code == 401


class TestDataOps:
    def test_get_accounts_success(self, svc):
        svc.http.post.return_value = _http_response(
            {"accounts": [{"account_id": "a1"}]})
        result = run(svc.get_accounts("tok"))
        assert result == [{"account_id": "a1"}]
        assert svc.http.post.call_args[0][1].endswith("/accounts/get")
        assert svc.http.post.call_args[1]["json"]["access_token"] == "tok"

    def test_get_accounts_http_error_400(self, svc):
        svc.http.post.return_value = _http_response()
        svc.http.post.return_value.raise_for_status.side_effect = \
            httpx.ConnectError("down")
        with pytest.raises(Exception) as exc:
            run(svc.get_accounts("tok"))
        assert exc.value.status_code == 400

    def test_get_accounts_missing_creds_401(self, unauthed_svc):
        with pytest.raises(Exception) as exc:
            run(unauthed_svc.get_accounts("tok"))
        assert exc.value.status_code == 401

    def test_get_balance_success(self, svc):
        svc.http.post.return_value = _http_response({"balances": []})
        result = run(svc.get_balance("tok"))
        assert result == {"balances": []}
        assert svc.http.post.call_args[0][1].endswith("/accounts/balance/get")

    def test_get_balance_http_error_400(self, svc):
        svc.http.post.return_value = _http_response()
        svc.http.post.return_value.raise_for_status.side_effect = \
            httpx.ConnectError("down")
        with pytest.raises(Exception) as exc:
            run(svc.get_balance("tok"))
        assert exc.value.status_code == 400

    def test_get_balance_missing_creds_401(self, unauthed_svc):
        with pytest.raises(Exception) as exc:
            run(unauthed_svc.get_balance("tok"))
        assert exc.value.status_code == 401

    def test_get_transactions_success(self, svc):
        svc.http.post.return_value = _http_response(
            {"transactions": [{"id": "t1"}]})
        result = run(svc.get_transactions("tok", "2026-01-01", "2026-02-01"))
        assert result == {"transactions": [{"id": "t1"}]}
        payload = svc.http.post.call_args[1]["json"]
        assert payload["start_date"] == "2026-01-01"
        assert payload["options"] == {"count": 100, "offset": 0}

    def test_get_transactions_custom_count(self, svc):
        svc.http.post.return_value = _http_response({})
        run(svc.get_transactions("tok", "2026-01-01", "2026-02-01",
                                 count=50, offset=10))
        assert svc.http.post.call_args[1]["json"]["options"] == {
            "count": 50, "offset": 10}

    def test_get_transactions_http_error_400(self, svc):
        svc.http.post.return_value = _http_response()
        svc.http.post.return_value.raise_for_status.side_effect = \
            httpx.ConnectError("down")
        with pytest.raises(Exception) as exc:
            run(svc.get_transactions("tok", "2026-01-01", "2026-02-01"))
        assert exc.value.status_code == 400

    def test_get_transactions_missing_creds_401(self, unauthed_svc):
        with pytest.raises(Exception) as exc:
            run(unauthed_svc.get_transactions("tok", "2026-01-01",
                                              "2026-02-01"))
        assert exc.value.status_code == 401

    def test_get_identity_success(self, svc):
        svc.http.post.return_value = _http_response({"identity": []})
        result = run(svc.get_identity("tok"))
        assert result == {"identity": []}
        assert svc.http.post.call_args[0][1].endswith("/identity/get")

    def test_get_identity_http_error_400(self, svc):
        svc.http.post.return_value = _http_response()
        svc.http.post.return_value.raise_for_status.side_effect = \
            httpx.ConnectError("down")
        with pytest.raises(Exception) as exc:
            run(svc.get_identity("tok"))
        assert exc.value.status_code == 400

    def test_get_identity_missing_creds_401(self, unauthed_svc):
        with pytest.raises(Exception) as exc:
            run(unauthed_svc.get_identity("tok"))
        assert exc.value.status_code == 401

    def test_remove_item_success(self, svc):
        svc.http.post.return_value = _http_response({"removed": True})
        result = run(svc.remove_item("tok"))
        assert result == {"removed": True}
        assert svc.http.post.call_args[0][1].endswith("/item/remove")

    def test_remove_item_http_error_400(self, svc):
        svc.http.post.return_value = _http_response()
        svc.http.post.return_value.raise_for_status.side_effect = \
            httpx.ConnectError("down")
        with pytest.raises(Exception) as exc:
            run(svc.remove_item("tok"))
        assert exc.value.status_code == 400

    def test_remove_item_missing_creds_401(self, unauthed_svc):
        with pytest.raises(Exception) as exc:
            run(unauthed_svc.remove_item("tok"))
        assert exc.value.status_code == 401


class TestHealthCheck:
    def test_missing_credentials_unhealthy(self, unauthed_svc):
        result = asyncio.run(unauthed_svc.health_check())
        assert result["ok"] is False
        assert result["status"] == "unhealthy"
        assert "Missing credentials" in result["message"]

    def test_healthy(self, svc):
        with patch("requests.post") as post:
            post.return_value = MagicMock(status_code=200)
            result = asyncio.run(svc.health_check())
        assert result["ok"] is True
        assert result["status"] == "healthy"
        assert result["version"] == "1.0.0"
        assert post.call_args[0][0].endswith("/categories/get")

    def test_unhealthy_status(self, svc):
        with patch("requests.post") as post:
            post.return_value = MagicMock(status_code=500)
            result = asyncio.run(svc.health_check())
        assert result["ok"] is False
        assert result["status"] == "unhealthy"

    def test_exception_unhealthy(self, svc):
        with patch("requests.post",
                   side_effect=RuntimeError("network down")):
            result = asyncio.run(svc.health_check())
        assert result["ok"] is False
        assert result["error"] == "Plaid health check failed"


class TestPostgresCacheSync:
    def _accounts(self):
        return [
            {"balances": {"current": 100.0, "available": 90.0}},
            {"balances": {"current": 50.0, "available": 40.0}},
        ]

    def _fake_db(self, existing=False):
        db = MagicMock()
        query = db.query.return_value
        query.filter_by.return_value.first.return_value = \
            MagicMock(value=1.0) if existing else None
        return db

    def test_sync_inserts_new_metrics(self, svc):
        with patch.object(svc, "get_accounts",
                          new=AsyncMock(return_value=self._accounts())), \
                patch("core.database.SessionLocal") as session_local, \
                patch("core.models.IntegrationMetric", create=True):
            db = self._fake_db(existing=False)
            session_local.return_value = db
            result = run(svc.sync_to_postgres_cache("ws-1", "tok"))
        assert result["success"] is True
        assert result["metrics_synced"] == 3
        assert db.add.call_count == 3
        db.commit.assert_called_once()
        db.close.assert_called_once()

    def test_sync_updates_existing_metrics(self, svc):
        with patch.object(svc, "get_accounts",
                          new=AsyncMock(return_value=self._accounts())), \
                patch("core.database.SessionLocal") as session_local, \
                patch("core.models.IntegrationMetric", create=True):
            db = self._fake_db(existing=True)
            session_local.return_value = db
            result = run(svc.sync_to_postgres_cache("ws-1", "tok"))
        assert result["success"] is True
        assert db.add.call_count == 0
        assert db.commit.call_count == 1

    def test_sync_commit_failure_rolls_back(self, svc):
        with patch.object(svc, "get_accounts",
                          new=AsyncMock(return_value=self._accounts())), \
                patch("core.database.SessionLocal") as session_local, \
                patch("core.models.IntegrationMetric", create=True):
            db = self._fake_db(existing=False)
            db.commit.side_effect = RuntimeError("db down")
            session_local.return_value = db
            result = run(svc.sync_to_postgres_cache("ws-1", "tok"))
        assert result["success"] is False
        assert result["error"] == "Failed to save Plaid metrics"
        db.rollback.assert_called_once()

    def test_sync_get_accounts_failure_outer_error(self, svc):
        with patch.object(svc, "get_accounts",
                          new=AsyncMock(side_effect=ValueError("boom"))), \
                patch("core.database.SessionLocal") as session_local, \
                patch("core.models.IntegrationMetric", create=True):
            result = run(svc.sync_to_postgres_cache("ws-1", "tok"))
        assert result["success"] is False
        assert result["error"] == "Plaid cache sync failed"

    def test_sync_empty_accounts(self, svc):
        with patch.object(svc, "get_accounts",
                          new=AsyncMock(return_value=[])), \
                patch("core.database.SessionLocal") as session_local, \
                patch("core.models.IntegrationMetric", create=True):
            db = self._fake_db(existing=False)
            session_local.return_value = db
            result = run(svc.sync_to_postgres_cache("ws-1", "tok"))
        assert result["success"] is True
        assert result["metrics_synced"] == 3

    def test_full_sync(self, svc):
        with patch.object(
                svc, "sync_to_postgres_cache",
                new=AsyncMock(return_value={"success": True,
                                            "metrics_synced": 3})) as sync:
            result = run(svc.full_sync("ws-1", "tok"))
        assert result["success"] is True
        assert result["workspace_id"] == "ws-1"
        assert result["postgres_cache"]["metrics_synced"] == 3
        sync.assert_awaited_once_with("ws-1", "tok")
