"""Coverage wave 64l — integrations/salesforce_core_service.py (TDD, mocked
requests/session, zero network, zero LLM spend).

The module had ZERO test references and was unimportable in this env (top-level
``import asyncpg`` while asyncpg is not a declared dependency) — fixed with a
guarded import + regression tests. Covers: enums, dataclasses, APIError,
session setup, get_credentials (no-tokens / expired / valid / exception /
phantom-module ImportError), _make_api_request (200/204/error-json/error-non-json
timeout/network/generic, endpoint prefixing, data-None), API usage logging
(sync + async + swallow), list_accounts / create_account / list_contacts /
list_opportunities (auth-fail, success, SOQL building with escaping,
pipeline stats, APIError, unexpected), get_user_info (production/sandbox,
non-200, exception), singleton, and the optional-asyncpg import guard.
"""
import importlib
import json
import sys
import types
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import requests

import integrations.salesforce_core_service as sf_mod
from integrations.salesforce_core_service import (
    SalesforceAPIError,
    SalesforceCoreService,
    SalesforceCredentials,
    SalesforceEnvironment,
    SalesforceObject,
    SalesforceQueryResult,
    get_salesforce_core_service,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_credentials(**overrides):
    creds = dict(
        access_token="tok-1",
        instance_url="https://acme.my.salesforce.com",
        refresh_token="ref-1",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        user_id="u-1",
        organization_id="org-1",
        username="alice",
    )
    creds.update(overrides)
    return SalesforceCredentials(**creds)


def make_response(status=200, payload=None, text="", content=None):
    r = Mock()
    r.status_code = status
    if content is None:
        content = json.dumps(payload).encode() if payload is not None else b""
    r.content = content
    r.text = text
    r.json.side_effect = lambda: json.loads(r.content) if r.content else {}
    return r


@pytest.fixture
def svc():
    s = SalesforceCoreService(db_pool=MagicMock())
    s.session = Mock()
    return s


@pytest.fixture
def svc_nopool():
    s = SalesforceCoreService(db_pool=None)
    s.session = Mock()
    return s


# ===========================================================================
# Enums, dataclasses, error type
# ===========================================================================


class TestEnums:
    def test_environment_values(self):
        assert SalesforceEnvironment.PRODUCTION.value == "production"
        assert SalesforceEnvironment.SANDBOX.value == "sandbox"

    def test_object_values(self):
        assert SalesforceObject.ACCOUNT.value == "Account"
        assert SalesforceObject.CONTACT.value == "Contact"
        assert SalesforceObject.LEAD.value == "Lead"
        assert SalesforceObject.OPPORTUNITY.value == "Opportunity"
        assert SalesforceObject.CASE.value == "Case"
        assert SalesforceObject.CAMPAIGN.value == "Campaign"
        assert SalesforceObject.TASK.value == "Task"
        assert SalesforceObject.EVENT.value == "Event"
        assert SalesforceObject.NOTE.value == "Note"
        assert SalesforceObject.ATTACHMENT.value == "Attachment"


class TestDataclasses:
    def test_query_result_fields(self):
        r = SalesforceQueryResult(
            total_size=2, done=True, next_records_url="/next", records=[{"Id": "x"}]
        )
        assert r.total_size == 2
        assert r.done is True
        assert r.next_records_url == "/next"
        assert r.records == [{"Id": "x"}]

    def test_query_result_optional_fields(self):
        r = SalesforceQueryResult(total_size=0, done=False, next_records_url=None, records=[])
        assert r.next_records_url is None
        assert r.records == []

    def test_credentials_roundtrip(self):
        creds = make_credentials()
        d = creds.__dict__
        assert d["access_token"] == "tok-1"
        assert d["organization_id"] == "org-1"
        assert d["username"] == "alice"

    def test_credentials_fields_via_asdict(self):
        from dataclasses import asdict

        creds = make_credentials()
        out = asdict(creds)
        assert out["instance_url"] == "https://acme.my.salesforce.com"
        assert isinstance(out["expires_at"], datetime)


class TestAPIError:
    def test_defaults_none(self):
        err = SalesforceAPIError("boom")
        assert err.status_code is None
        assert err.error_code is None

    def test_with_values(self):
        err = SalesforceAPIError("boom", status_code=400, error_code="BAD")
        assert str(err) == "boom"
        assert err.status_code == 400
        assert err.error_code == "BAD"


# ===========================================================================
# Construction / session setup
# ===========================================================================


class TestInit:
    def test_session_configured(self):
        s = SalesforceCoreService(db_pool=None)
        try:
            assert s.db_pool is None
            assert s.session.timeout == 30
            assert s.session.headers["User-Agent"] == "ATOM-Enterprise/1.0"
            assert s.session.headers["Accept"] == "application/json"
            assert s.session.headers["Content-Type"] == "application/json"
        finally:
            s.session.close()

    def test_db_pool_kept(self, svc):
        assert svc.db_pool is not None


# ===========================================================================
# get_credentials
# ===========================================================================


@pytest.fixture
def db_oauth_installed():
    fake = types.ModuleType("db_oauth_salesforce")
    fake.get_user_salesforce_tokens = AsyncMock()
    fake.log_api_usage = AsyncMock()
    sys.modules["db_oauth_salesforce"] = fake
    yield fake
    sys.modules.pop("db_oauth_salesforce", None)


class TestGetCredentials:
    def test_no_tokens_returns_none(self, svc, db_oauth_installed):
        db_oauth_installed.get_user_salesforce_tokens.return_value = None
        result = _await(svc.get_credentials("u-1"))
        assert result is None

    def test_expired_token_returns_none(self, svc, db_oauth_installed):
        expired = datetime.now(timezone.utc) - timedelta(minutes=5)
        db_oauth_installed.get_user_salesforce_tokens.return_value = {
            "access_token": "t",
            "instance_url": "https://x",
            "refresh_token": "r",
            "expires_at": expired.isoformat().replace("+00:00", "Z"),
            "user_id": "u-1",
            "organization_id": "o",
            "username": "alice",
        }
        result = _await(svc.get_credentials("u-1"))
        assert result is None

    def test_valid_tokens_build_credentials(self, svc, db_oauth_installed):
        future = datetime.now(timezone.utc) + timedelta(hours=2)
        db_oauth_installed.get_user_salesforce_tokens.return_value = {
            "access_token": "tok-1",
            "instance_url": "https://acme.my.salesforce.com",
            "refresh_token": "ref-1",
            "expires_at": future.isoformat(),
            "user_id": "u-1",
            "organization_id": "org-1",
            "username": "alice",
        }
        creds = _await(svc.get_credentials("u-1", username="alice"))
        assert isinstance(creds, SalesforceCredentials)
        assert creds.access_token == "tok-1"
        assert creds.user_id == "u-1"
        assert creds.organization_id == "org-1"
        assert creds.username == "alice"

    def test_token_lookup_exception_returns_none(self, svc, db_oauth_installed):
        db_oauth_installed.get_user_salesforce_tokens.side_effect = RuntimeError("db down")
        result = _await(svc.get_credentials("u-1"))
        assert result is None

    def test_phantom_module_import_error_returns_none(self, svc):
        sys.modules.pop("db_oauth_salesforce", None)
        try:
            result = _await(svc.get_credentials("u-1"))
        finally:
            fake = types.ModuleType("db_oauth_salesforce")
            fake.get_user_salesforce_tokens = AsyncMock()
            fake.log_api_usage = AsyncMock()
            sys.modules["db_oauth_salesforce"] = fake
        assert result is None


# ===========================================================================
# _make_api_request
# ===========================================================================


class TestMakeApiRequest:
    def _req(self, svc, response, **kwargs):
        svc.session.request.return_value = response
        svc._log_api_usage = Mock()
        return svc._make_api_request(
            make_credentials(), "GET", "query/?q=SELECT+Id+FROM+Account", **kwargs
        )

    def test_200_with_content_returns_json(self, svc):
        out = self._req(svc, make_response(200, {"totalSize": 1, "records": [{"Id": "x"}]}))
        assert out == {"totalSize": 1, "records": [{"Id": "x"}]}

    def test_200_with_empty_content_returns_empty_dict(self, svc):
        out = self._req(svc, make_response(200, None))
        assert out == {}

    def test_204_returns_empty_dict(self, svc):
        out = self._req(svc, make_response(204, {"ignored": True}))
        assert out == {}

    def test_endpoint_without_slash_is_prefixed(self, svc):
        svc.session.request.return_value = make_response(200, {})
        svc._log_api_usage = Mock()
        svc._make_api_request(make_credentials(), "GET", "query/?q=x")
        url = svc.session.request.call_args[1]["url"]
        assert url == "https://acme.my.salesforce.com/services/data/v56.0/query/?q=x"

    def test_endpoint_with_slash_uses_urljoin(self, svc):
        svc.session.request.return_value = make_response(200, {})
        svc._log_api_usage = Mock()
        svc._make_api_request(make_credentials(), "GET", "/services/data/v58.0/query/?q=x")
        url = svc.session.request.call_args[1]["url"]
        assert url == "https://acme.my.salesforce.com/services/data/v58.0/query/?q=x"

    def test_headers_and_json_body(self, svc):
        svc.session.request.return_value = make_response(200, {})
        svc._log_api_usage = Mock()
        svc._make_api_request(
            make_credentials(), "POST", "sobjects/Account/", data={"Name": "Acme"}
        )
        call = svc.session.request.call_args
        assert call[1]["headers"]["Authorization"] == "Bearer tok-1"
        assert call[1]["json"] == {"Name": "Acme"}
        assert call[1]["params"] is None

    def test_data_none_passes_json_none(self, svc):
        svc.session.request.return_value = make_response(200, {})
        svc._log_api_usage = Mock()
        svc._make_api_request(make_credentials(), "GET", "x", data=None)
        assert svc.session.request.call_args[1]["json"] is None

    def test_error_json_with_description(self, svc):
        payload = {"error_description": "Invalid grant", "error_code": "INVALID_GRANT"}
        with pytest.raises(SalesforceAPIError) as exc:
            self._req(svc, make_response(401, payload))
        assert str(exc.value) == "Invalid grant"
        assert exc.value.status_code == 401
        assert exc.value.error_code == "INVALID_GRANT"

    def test_error_json_with_error_key(self, svc):
        payload = {"error": "Bad session", "error_code": "INVALID_SESSION_ID"}
        with pytest.raises(SalesforceAPIError) as exc:
            self._req(svc, make_response(400, payload))
        assert str(exc.value) == "Bad session"
        assert exc.value.error_code == "INVALID_SESSION_ID"

    def test_error_json_without_message_keys(self, svc):
        with pytest.raises(SalesforceAPIError) as exc:
            self._req(svc, make_response(500, {"foo": "bar"}))
        assert str(exc.value) == "Unknown error"
        assert exc.value.error_code == "UNKNOWN_ERROR"

    def test_error_non_json_falls_back_to_text(self, svc):
        raw = b"<html>502 Bad Gateway</html>"
        with pytest.raises(SalesforceAPIError) as exc:
            self._req(svc, make_response(502, None, text="bad gateway", content=raw))
        assert str(exc.value) == "bad gateway"
        assert exc.value.error_code == "HTTP_ERROR"
        assert exc.value.status_code == 502

    def test_timeout_maps_to_408(self, svc):
        svc.session.request.side_effect = requests.exceptions.Timeout()
        svc._log_api_usage = Mock()
        with pytest.raises(SalesforceAPIError) as exc:
            svc._make_api_request(make_credentials(), "GET", "x")
        assert exc.value.status_code == 408
        assert exc.value.error_code == "TIMEOUT_ERROR"

    def test_request_exception_maps_to_network_error(self, svc):
        svc.session.request.side_effect = requests.exceptions.ConnectionError("conn refused")
        svc._log_api_usage = Mock()
        with pytest.raises(SalesforceAPIError) as exc:
            svc._make_api_request(make_credentials(), "GET", "x")
        assert exc.value.error_code == "NETWORK_ERROR"
        assert "Network error" in str(exc.value)

    def test_generic_exception_maps_to_unknown(self, svc):
        svc.session.request.side_effect = ValueError("weird")
        svc._log_api_usage = Mock()
        with pytest.raises(SalesforceAPIError) as exc:
            svc._make_api_request(make_credentials(), "GET", "x")
        assert exc.value.error_code == "UNKNOWN_ERROR"
        assert "Unexpected error" in str(exc.value)

    def test_log_usage_called_with_success_flag(self, svc):
        svc.session.request.return_value = make_response(200, {})
        svc._log_api_usage = Mock()
        svc._make_api_request(make_credentials(), "GET", "query/?q=x")
        args = svc._log_api_usage.call_args[0]
        assert args[0] == "u-1"
        assert args[1] == "alice"
        assert args[2] == "GET /services/data/v56.0/query/?q=x"
        assert args[4] is True

    def test_log_usage_called_with_failure(self, svc):
        svc.session.request.return_value = make_response(400, {"error": "x"}, text="err text")
        svc._log_api_usage = Mock()
        with pytest.raises(SalesforceAPIError):
            svc._make_api_request(make_credentials(), "GET", "query/?q=x")
        args = svc._log_api_usage.call_args[0]
        assert args[4] is False
        assert args[5] == "err text"


# ===========================================================================
# API usage logging
# ===========================================================================


class TestLogApiUsage:
    def test_no_db_pool_is_noop(self, svc_nopool):
        with patch("asyncio.create_task") as create_task:
            svc_nopool._log_api_usage("u", "a", "GET /x", 10, True, None)
        create_task.assert_not_called()

    def test_db_pool_schedules_async_task(self, svc):
        with patch("asyncio.create_task") as create_task:
            svc._log_api_usage("u", "a", "GET /x", 10, True, None)
        assert create_task.call_count == 1
        coro = create_task.call_args[0][0]
        assert coro.cr_code.co_name == "_log_api_usage_async"

    def test_create_task_exception_swallowed(self, svc):
        with patch("asyncio.create_task", side_effect=RuntimeError("no loop")):
            svc._log_api_usage("u", "a", "GET /x", 10, True, None)  # must not raise

    def test_async_logging_success(self, svc, db_oauth_installed):
        _await(svc._log_api_usage_async("u", "a", "GET /x", 10, True, None))
        db_oauth_installed.log_api_usage.assert_awaited_once_with(
            svc.db_pool, "u", "a", "GET /x", 10, True, None
        )

    def test_async_logging_exception_swallowed(self, svc, db_oauth_installed):
        db_oauth_installed.log_api_usage.side_effect = RuntimeError("db down")
        _await(svc._log_api_usage_async("u", "a", "GET /x", 10, True, None))  # no raise


# ===========================================================================
# list_accounts
# ===========================================================================


class TestListAccounts:
    async def test_auth_failed(self, svc):
        with patch.object(svc, "get_credentials", new=AsyncMock(return_value=None)):
            out = await svc.list_accounts("u-1")
        assert out["ok"] is False
        assert out["error"] == "authentication_failed"

    async def test_success_default_fields(self, svc):
        creds = make_credentials()
        with patch.object(svc, "get_credentials", new=AsyncMock(return_value=creds)), \
             patch.object(svc, "_make_api_request",
                          new=Mock(return_value={"records": [{"Id": "a1"}], "totalSize": 1,
                                                "done": True})):
            out = await svc.list_accounts("u-1")
        assert out["ok"] is True
        assert out["accounts"] == [{"Id": "a1"}]
        assert out["total_size"] == 1
        assert out["limit"] == 25
        assert out["offset"] == 0
        assert "FROM Account" in out["query"]
        assert "Name" in out["query"]

    async def test_custom_query_fields_limit_offset(self, svc):
        creds = make_credentials()
        with patch.object(svc, "get_credentials", new=AsyncMock(return_value=creds)), \
             patch.object(svc, "_make_api_request",
                          new=Mock(return_value={"records": [], "done": False})):
            out = await svc.list_accounts("u-1", query="Industry = 'Tech'",
                                          fields=["Id", "Name"], limit=5, offset=10)
        soql = out["query"]
        assert "WHERE Industry = 'Tech'" in soql
        assert "LIMIT 5 OFFSET 10" in soql
        assert "AnnualRevenue" not in soql
        assert out["total_size"] == 0

    async def test_api_error(self, svc):
        creds = make_credentials()
        err = SalesforceAPIError("bad query", status_code=400, error_code="MALFORMED_QUERY")
        with patch.object(svc, "get_credentials", new=AsyncMock(return_value=creds)), \
             patch.object(svc, "_make_api_request", new=Mock(side_effect=err)):
            out = await svc.list_accounts("u-1")
        assert out["ok"] is False
        assert out["error"] == "api_error"
        assert out["status_code"] == 400
        assert out["error_code"] == "MALFORMED_QUERY"

    async def test_unexpected_error(self, svc):
        creds = make_credentials()
        with patch.object(svc, "get_credentials", new=AsyncMock(return_value=creds)), \
             patch.object(svc, "_make_api_request", new=Mock(side_effect=ValueError("boom"))):
            out = await svc.list_accounts("u-1")
        assert out["ok"] is False
        assert out["error"] == "unexpected_error"
        assert "Unexpected" in out["message"]


# ===========================================================================
# create_account
# ===========================================================================


class TestCreateAccount:
    async def test_auth_failed(self, svc):
        with patch.object(svc, "get_credentials", new=AsyncMock(return_value=None)):
            out = await svc.create_account("u-1", account_data={"Name": "Acme"})
        assert out["error"] == "authentication_failed"

    async def test_missing_data_validation_error(self, svc):
        with patch.object(svc, "get_credentials",
                          new=AsyncMock(return_value=make_credentials())), \
             patch.object(svc, "_make_api_request", new=Mock()) as req:
            out = await svc.create_account("u-1")
        assert out["error"] == "validation_error"
        req.assert_not_called()

    async def test_success(self, svc):
        with patch.object(svc, "get_credentials",
                          new=AsyncMock(return_value=make_credentials())), \
             patch.object(svc, "_make_api_request",
                          new=Mock(return_value={"id": "001xx", "success": True})) as req:
            out = await svc.create_account("u-1", account_data={"Name": "Acme"})
        assert out["ok"] is True
        assert out["account"] == {"id": "001xx", "success": True}
        assert req.call_args[1]["endpoint"] == "sobjects/Account/"
        assert req.call_args[1]["method"] == "POST"
        assert req.call_args[1]["data"] == {"Name": "Acme"}

    async def test_api_error(self, svc):
        err = SalesforceAPIError("duplicate", status_code=409, error_code="DUPLICATE")
        with patch.object(svc, "get_credentials",
                          new=AsyncMock(return_value=make_credentials())), \
             patch.object(svc, "_make_api_request", new=Mock(side_effect=err)):
            out = await svc.create_account("u-1", account_data={"Name": "Acme"})
        assert out["error"] == "api_error"
        assert out["status_code"] == 409

    async def test_unexpected_error(self, svc):
        with patch.object(svc, "get_credentials",
                          new=AsyncMock(return_value=make_credentials())), \
             patch.object(svc, "_make_api_request",
                          new=Mock(side_effect=RuntimeError("boom"))):
            out = await svc.create_account("u-1", account_data={"Name": "Acme"})
        assert out["error"] == "unexpected_error"


# ===========================================================================
# list_contacts
# ===========================================================================


class TestListContacts:
    async def test_auth_failed(self, svc):
        with patch.object(svc, "get_credentials", new=AsyncMock(return_value=None)):
            out = await svc.list_contacts("u-1")
        assert out["error"] == "authentication_failed"

    async def test_success_with_account_and_query_filters(self, svc):
        with patch.object(svc, "get_credentials",
                          new=AsyncMock(return_value=make_credentials())), \
             patch.object(svc, "_make_api_request",
                          new=Mock(return_value={"records": [{"Id": "c1"}], "totalSize": 1,
                                                "done": True})) as req:
            out = await svc.list_contacts("u-1", account_id="001'x",
                                          query="Email LIKE '%@acme.com'")
        soql = out["query"]
        assert "FROM Contact" in soql
        assert "AccountId = '001''x'" in soql
        assert "Email LIKE '%@acme.com'" in soql
        assert out["ok"] is True
        assert out["contacts"] == [{"Id": "c1"}]
        assert req.call_args[1]["method"] == "GET"

    async def test_no_conditions_no_where(self, svc):
        with patch.object(svc, "get_credentials",
                          new=AsyncMock(return_value=make_credentials())), \
             patch.object(svc, "_make_api_request",
                          new=Mock(return_value={"records": [], "done": True})):
            out = await svc.list_contacts("u-1", fields=["Id", "Email"])
        assert "WHERE" not in out["query"]
        assert "Email" in out["query"]

    async def test_api_error(self, svc):
        err = SalesforceAPIError("x", status_code=403, error_code="FORBIDDEN")
        with patch.object(svc, "get_credentials",
                          new=AsyncMock(return_value=make_credentials())), \
             patch.object(svc, "_make_api_request", new=Mock(side_effect=err)):
            out = await svc.list_contacts("u-1")
        assert out["error"] == "api_error"
        assert out["error_code"] == "FORBIDDEN"

    async def test_unexpected_error(self, svc):
        with patch.object(svc, "get_credentials",
                          new=AsyncMock(return_value=make_credentials())), \
             patch.object(svc, "_make_api_request",
                          new=Mock(side_effect=KeyError("k"))):
            out = await svc.list_contacts("u-1")
        assert out["error"] == "unexpected_error"


# ===========================================================================
# list_opportunities
# ===========================================================================


class TestListOpportunities:
    async def test_auth_failed(self, svc):
        with patch.object(svc, "get_credentials", new=AsyncMock(return_value=None)):
            out = await svc.list_opportunities("u-1")
        assert out["error"] == "authentication_failed"

    async def test_success_with_filters_and_pipeline_stats(self, svc):
        records = [
            {"Id": "o1", "Amount": 1000, "Probability": 50},
            {"Id": "o2", "Amount": 2000, "Probability": 100},
        ]
        with patch.object(svc, "get_credentials",
                          new=AsyncMock(return_value=make_credentials())), \
             patch.object(svc, "_make_api_request",
                          new=Mock(return_value={"records": records, "totalSize": 2,
                                                "done": True})):
            out = await svc.list_opportunities("u-1", account_id="001x",
                                               stage="Prospecting", query="Amount > 0")
        soql = out["query"]
        assert "FROM Opportunity" in soql
        assert "AccountId = '001x'" in soql
        assert "StageName = 'Prospecting'" in soql
        assert "Amount > 0" in soql
        assert "ORDER BY CloseDate ASC" in soql
        assert out["pipeline_statistics"]["total_pipeline_value"] == 3000
        assert out["pipeline_statistics"]["weighted_pipeline_value"] == 2500
        assert out["pipeline_statistics"]["opportunity_count"] == 2

    async def test_success_missing_amount_and_probability_default_zero(self, svc):
        with patch.object(svc, "get_credentials",
                          new=AsyncMock(return_value=make_credentials())), \
             patch.object(svc, "_make_api_request",
                          new=Mock(return_value={"records": [{"Id": "o1"}], "done": True})):
            out = await svc.list_opportunities("u-1")
        assert out["pipeline_statistics"]["total_pipeline_value"] == 0
        assert out["pipeline_statistics"]["weighted_pipeline_value"] == 0

    async def test_api_error(self, svc):
        err = SalesforceAPIError("x", status_code=400, error_code="BAD")
        with patch.object(svc, "get_credentials",
                          new=AsyncMock(return_value=make_credentials())), \
             patch.object(svc, "_make_api_request", new=Mock(side_effect=err)):
            out = await svc.list_opportunities("u-1")
        assert out["error"] == "api_error"

    async def test_unexpected_error(self, svc):
        with patch.object(svc, "get_credentials",
                          new=AsyncMock(return_value=make_credentials())), \
             patch.object(svc, "_make_api_request",
                          new=Mock(side_effect=ZeroDivisionError)):
            out = await svc.list_opportunities("u-1")
        assert out["error"] == "unexpected_error"


# ===========================================================================
# get_user_info
# ===========================================================================


class TestGetUserInfo:
    async def test_auth_failed(self, svc):
        with patch.object(svc, "get_credentials", new=AsyncMock(return_value=None)):
            out = await svc.get_user_info("u-1")
        assert out["error"] == "authentication_failed"

    async def test_success_production(self, svc):
        creds = make_credentials(instance_url="https://login.salesforce.com")
        with patch.object(svc, "get_credentials", new=AsyncMock(return_value=creds)), \
             patch("integrations.salesforce_core_service.requests.get",
                   new=Mock(return_value=make_response(200, {
                       "user_id": "005x", "organization_id": "org-1", "username": "alice",
                       "email": "alice@acme.com", "display_name": "Alice",
                       "profile_id": "p1", "timezone": "UTC", "locale": "en_US",
                       "active": True,
                   }))) as get_mock:
            out = await svc.get_user_info("u-1")
        assert out["ok"] is True
        assert out["user_info"]["environment"] == "production"
        assert out["user_info"]["email"] == "alice@acme.com"
        assert out["user_info"]["active"] is True
        url = get_mock.call_args[0][0]
        assert url.endswith("/services/oauth2/userinfo")

    async def test_success_sandbox(self, svc):
        creds = make_credentials(instance_url="https://acme--dev.sandbox.my.salesforce.com")
        with patch.object(svc, "get_credentials", new=AsyncMock(return_value=creds)), \
             patch("integrations.salesforce_core_service.requests.get",
                   new=Mock(return_value=make_response(200, {"username": "bob"}))):
            out = await svc.get_user_info("u-1")
        assert out["ok"] is True
        assert out["user_info"]["environment"] == "sandbox"
        assert out["user_info"]["active"] is True  # default

    async def test_non_200(self, svc):
        with patch.object(svc, "get_credentials",
                          new=AsyncMock(return_value=make_credentials())), \
             patch("integrations.salesforce_core_service.requests.get",
                   new=Mock(return_value=make_response(401))):
            out = await svc.get_user_info("u-1")
        assert out["ok"] is False
        assert out["error"] == "user_info_failed"
        assert out["status_code"] == 401

    async def test_exception(self, svc):
        with patch.object(svc, "get_credentials",
                          new=AsyncMock(return_value=make_credentials())), \
             patch("integrations.salesforce_core_service.requests.get",
                   new=Mock(side_effect=requests.exceptions.ConnectionError("down"))):
            out = await svc.get_user_info("u-1")
        assert out["ok"] is False
        assert out["error"] == "unexpected_error"


# ===========================================================================
# Singleton
# ===========================================================================


class TestSingleton:
    def test_returns_same_instance(self, monkeypatch):
        monkeypatch.setattr(sf_mod, "salesforce_core_service", None)
        a = get_salesforce_core_service()
        b = get_salesforce_core_service(db_pool=MagicMock())
        assert a is b
        assert isinstance(a, SalesforceCoreService)

    def test_creates_new_when_none(self, monkeypatch):
        monkeypatch.setattr(sf_mod, "salesforce_core_service", None)
        s = get_salesforce_core_service()
        assert s.db_pool is None


# ===========================================================================
# Optional-dependency guard (asyncpg)
# ===========================================================================


class TestAsyncpgGuard:
    def test_module_usable_without_asyncpg(self):
        assert sf_mod.asyncpg is None
        assert sf_mod.SalesforceCoreService is not None

    def test_module_imports_when_asyncpg_available(self):
        fake = types.ModuleType("asyncpg")
        fake.Pool = type("Pool", (), {})
        original = sys.modules.get("asyncpg")
        sys.modules["asyncpg"] = fake
        try:
            importlib.reload(sf_mod)
            assert sf_mod.asyncpg is fake
            assert sf_mod.SalesforceCoreService is not None
            assert sf_mod.get_salesforce_core_service() is not None
        finally:
            if original is not None:
                sys.modules["asyncpg"] = original
            else:
                sys.modules.pop("asyncpg", None)


def _await(coro):
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
