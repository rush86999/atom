"""Coverage wave 98 — integrations/auth_handler_salesforce.py (TDD, 0%
baseline).

Fully mocked (fake aiohttp session + fake secret manager), zero network, zero
LLM spend.

BUG FOUND + FIXED (TDD RED->GREEN): the non-200 branches of
exchange_code_for_token / refresh_access_token / get_user_info raise
HTTPException(400) INSIDE the method try-block, but the trailing
`except Exception` caught it and re-raised HTTPException(500) — the 400
error mapping was dead code and every OAuth/API failure surfaced as a 500
(and the 400 raise lines were unreachable for coverage). `except HTTPException:
raise` added; tests asserting 400 on non-200 were RED before the fix.

Covers: __init__ (env override/defaults, secret-manager token loading ->
token_expires_at forced to now, no token -> None), get_authorization_url
(explicit state / auto-generated 32-char state), exchange_code_for_token
(success persists tokens+instance_url to secret manager, expires_in int
mapping incl. 0 -> 7200 default, non-200 -> 400, exception -> 500),
refresh_access_token (no refresh token -> 400, success with new refresh
token, success keeping old refresh token, non-200 -> 400, exception -> 500),
get_user_info (no token/instance_url -> 401, success, non-200 -> 400,
exception -> 500), revoke_token (no token -> True, 200 clears state + secret
manager, non-200 -> False, exception -> False), is_token_valid, 
ensure_valid_token (valid/refresh/401), get_connection_status (all fields).
"""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from integrations import auth_handler_salesforce as sf
from integrations.auth_handler_salesforce import SalesforceAuthHandler


class _FakeResponse:
    def __init__(self, status=200, payload=None, text="err"):
        self.status = status
        self._payload = payload
        self._text = text

    async def text(self):
        return self._text

    async def json(self):
        return self._payload or {}


class _FakeRespCM:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *a):
        return False


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def _next(self):
        if len(self._responses) == 1:
            return self._responses[0]
        return self._responses.pop(0)

    def post(self, *a, **k):
        return _FakeRespCM(self._next())

    def get(self, *a, **k):
        return _FakeRespCM(self._next())


def _mock_session(*responses):
    return patch.object(
        sf.aiohttp,
        "ClientSession",
        MagicMock(return_value=_FakeSession(responses)),
    )


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SALESFORCE_CLIENT_ID", "sfcid")
    monkeypatch.setenv("SALESFORCE_CLIENT_SECRET", "sfcsecret")
    monkeypatch.setenv("SALESFORCE_REDIRECT_URI",
                       "https://app.example/sf/cb")
    monkeypatch.setenv("SALESFORCE_AUTH_URL", "https://test.salesforce.com")


@pytest.fixture
def secret_manager():
    sm = MagicMock()
    sm.get_secret.return_value = None
    return sm


@pytest.fixture
def handler(secret_manager):
    with patch.object(sf, "get_secret_manager",
                      return_value=secret_manager):
        yield SalesforceAuthHandler()


class TestInit:
    def test_env_overrides(self, secret_manager):
        with patch.object(sf, "get_secret_manager",
                          return_value=secret_manager):
            h = SalesforceAuthHandler()
        assert h.client_id == "sfcid"
        assert h.client_secret == "sfcsecret"
        assert h.redirect_uri == "https://app.example/sf/cb"
        assert h.base_url == "https://test.salesforce.com"
        assert h.token_url == \
            "https://test.salesforce.com/services/oauth2/token"
        assert h.authorize_url == \
            "https://test.salesforce.com/services/oauth2/authorize"
        assert h.revoke_url == \
            "https://test.salesforce.com/services/oauth2/revoke"
        assert h.access_token is None
        assert h.token_expires_at is None

    def test_env_defaults(self, monkeypatch, secret_manager):
        monkeypatch.delenv("SALESFORCE_CLIENT_ID", raising=False)
        monkeypatch.delenv("SALESFORCE_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("SALESFORCE_REDIRECT_URI", raising=False)
        monkeypatch.delenv("SALESFORCE_AUTH_URL", raising=False)
        with patch.object(sf, "get_secret_manager",
                          return_value=secret_manager):
            h = SalesforceAuthHandler()
        assert h.client_id == ""
        assert h.client_secret == ""
        assert h.base_url == "https://login.salesforce.com"

    def test_stored_access_token_forces_refresh_check(self, secret_manager):
        secret_manager.get_secret.return_value = "stored-at"
        with patch.object(sf, "get_secret_manager",
                          return_value=secret_manager):
            h = SalesforceAuthHandler()
        assert h.access_token == "stored-at"
        assert h.token_expires_at is not None
        assert h.is_token_valid() is False


class TestAuthorizationUrl:
    def test_explicit_state(self, handler):
        url = handler.get_authorization_url(state="s1")
        assert url.startswith(
            "https://test.salesforce.com/services/oauth2/authorize?")
        assert "response_type=code" in url
        assert "client_id=sfcid" in url
        assert "state=s1" in url
        assert "offline_access" in url

    def test_auto_state(self, handler):
        url = handler.get_authorization_url()
        assert "state=" in url
        assert len(url.split("state=")[1].split("&")[0]) == 43


class TestExchangeCode:
    async def test_success_persists_secrets(self, handler, secret_manager):
        with _mock_session(_FakeResponse(
                200, {"access_token": "at1", "refresh_token": "rt1",
                      "instance_url": "https://x.salesforce.com",
                      "expires_in": 7200})):
            out = await handler.exchange_code_for_token("code-1")
        assert out["access_token"] == "at1"
        assert handler.access_token == "at1"
        assert handler.instance_url == "https://x.salesforce.com"
        assert handler.token_expires_at > datetime.now()
        secret_manager.set_secret.assert_any_call(
            "SALESFORCE_ACCESS_TOKEN", "at1")
        secret_manager.set_secret.assert_any_call(
            "SALESFORCE_REFRESH_TOKEN", "rt1")
        secret_manager.set_secret.assert_any_call(
            "SALESFORCE_INSTANCE_URL", "https://x.salesforce.com")

    async def test_expires_in_zero_uses_default(self, handler,
                                                secret_manager):
        with _mock_session(_FakeResponse(
                200, {"access_token": "at1", "refresh_token": "rt1",
                      "expires_in": 0})):
            await handler.exchange_code_for_token("code-1")
        assert handler.token_expires_at > datetime.now()

    async def test_non_200_raises_400(self, handler):
        with _mock_session(_FakeResponse(400, text="invalid_grant")):
            with pytest.raises(HTTPException) as ei:
                await handler.exchange_code_for_token("bad")
        assert ei.value.status_code == 400
        assert ei.value.detail == "Internal error"

    async def test_exception_raises_500(self, handler):
        with patch.object(
                sf.aiohttp, "ClientSession",
                side_effect=RuntimeError("net down")):
            with pytest.raises(HTTPException) as ei:
                await handler.exchange_code_for_token("code-1")
        assert ei.value.status_code == 500


class TestRefresh:
    async def test_no_refresh_token(self, handler):
        with pytest.raises(HTTPException) as ei:
            await handler.refresh_access_token()
        assert ei.value.status_code == 400

    async def test_success_new_refresh_token(self, handler,
                                             secret_manager):
        handler.refresh_token = "rt-old"
        with _mock_session(_FakeResponse(
                200, {"access_token": "at2", "refresh_token": "rt2",
                      "instance_url": "https://y.salesforce.com",
                      "expires_in": 7200})):
            out = await handler.refresh_access_token()
        assert out["access_token"] == "at2"
        assert handler.refresh_token == "rt2"
        assert handler.instance_url == "https://y.salesforce.com"
        secret_manager.set_secret.assert_any_call(
            "SALESFORCE_REFRESH_TOKEN", "rt2")

    async def test_success_keeps_old_refresh_token(self, handler):
        handler.refresh_token = "rt-old"
        with _mock_session(_FakeResponse(
                200, {"access_token": "at2", "expires_in": 7200})):
            out = await handler.refresh_access_token()
        assert handler.refresh_token == "rt-old"
        assert handler.instance_url is None

    async def test_non_200_raises_400(self, handler):
        handler.refresh_token = "rt-old"
        with _mock_session(_FakeResponse(401, text="bad")):
            with pytest.raises(HTTPException) as ei:
                await handler.refresh_access_token()
        assert ei.value.status_code == 400

    async def test_exception_raises_500(self, handler):
        handler.refresh_token = "rt-old"
        with patch.object(
                sf.aiohttp, "ClientSession",
                side_effect=RuntimeError("boom")):
            with pytest.raises(HTTPException) as ei:
                await handler.refresh_access_token()
        assert ei.value.status_code == 500


class TestGetUserInfo:
    async def test_no_token_or_instance(self, handler):
        with pytest.raises(HTTPException) as ei:
            await handler.get_user_info()
        assert ei.value.status_code == 401

    async def test_no_instance_url(self, handler):
        handler.access_token = "at1"
        handler.instance_url = None
        with pytest.raises(HTTPException) as ei:
            await handler.get_user_info()
        assert ei.value.status_code == 401

    async def test_success(self, handler):
        handler.access_token = "at1"
        handler.instance_url = "https://x.salesforce.com"
        with _mock_session(_FakeResponse(
                200, {"sub": "u1", "name": "Rushi"})):
            out = await handler.get_user_info()
        assert out["name"] == "Rushi"
        assert handler.user_info == out

    async def test_non_200_raises_400(self, handler):
        handler.access_token = "at1"
        handler.instance_url = "https://x.salesforce.com"
        with _mock_session(_FakeResponse(403, text="nope")):
            with pytest.raises(HTTPException) as ei:
                await handler.get_user_info()
        assert ei.value.status_code == 400

    async def test_exception_raises_500(self, handler):
        handler.access_token = "at1"
        handler.instance_url = "https://x.salesforce.com"
        with patch.object(
                sf.aiohttp, "ClientSession",
                side_effect=RuntimeError("boom")):
            with pytest.raises(HTTPException) as ei:
                await handler.get_user_info()
        assert ei.value.status_code == 500


class TestRevoke:
    async def test_no_token_returns_true(self, handler):
        assert await handler.revoke_token() is True

    async def test_success_clears_state(self, handler, secret_manager):
        handler.access_token = "at1"
        handler.refresh_token = "rt1"
        handler.token_expires_at = datetime.now()
        handler.user_info = {"sub": "u1"}
        handler.instance_url = "https://x.salesforce.com"
        with _mock_session(_FakeResponse(200)):
            assert await handler.revoke_token() is True
        assert handler.access_token is None
        assert handler.refresh_token is None
        assert handler.token_expires_at is None
        assert handler.user_info is None
        assert handler.instance_url is None
        secret_manager.set_secret.assert_any_call(
            "SALESFORCE_ACCESS_TOKEN", "")
        secret_manager.set_secret.assert_any_call(
            "SALESFORCE_REFRESH_TOKEN", "")

    async def test_non_200_returns_false(self, handler):
        handler.access_token = "at1"
        with _mock_session(_FakeResponse(500, text="fail")):
            assert await handler.revoke_token() is False

    async def test_exception_returns_false(self, handler):
        handler.access_token = "at1"
        with patch.object(
                sf.aiohttp, "ClientSession",
                side_effect=RuntimeError("boom")):
            assert await handler.revoke_token() is False


class TestTokenValidity:
    def test_no_token(self, handler):
        assert handler.is_token_valid() is False

    def test_no_expiry(self, handler):
        handler.access_token = "at1"
        assert handler.is_token_valid() is False

    def test_expired(self, handler):
        handler.access_token = "at1"
        handler.token_expires_at = datetime.now() - timedelta(minutes=1)
        assert handler.is_token_valid() is False

    def test_within_buffer(self, handler):
        handler.access_token = "at1"
        handler.token_expires_at = datetime.now() + timedelta(minutes=4)
        assert handler.is_token_valid() is False

    def test_valid(self, handler):
        handler.access_token = "at1"
        handler.token_expires_at = datetime.now() + timedelta(minutes=10)
        assert handler.is_token_valid() is True


class TestEnsureValidToken:
    async def test_valid_returns_token(self, handler):
        handler.access_token = "at1"
        handler.token_expires_at = datetime.now() + timedelta(minutes=10)
        assert await handler.ensure_valid_token() == "at1"

    async def test_invalid_with_refresh(self, handler):
        handler.access_token = "stale"
        handler.refresh_token = "rt1"
        with _mock_session(_FakeResponse(
                200, {"access_token": "fresh", "expires_in": 7200})):
            assert await handler.ensure_valid_token() == "fresh"

    async def test_invalid_without_refresh(self, handler):
        handler.access_token = "stale"
        handler.refresh_token = None
        with pytest.raises(HTTPException) as ei:
            await handler.ensure_valid_token()
        assert ei.value.status_code == 401


class TestConnectionStatus:
    def test_empty(self, handler):
        status = handler.get_connection_status()
        assert status["connected"] is False
        assert status["has_access_token"] is False
        assert status["instance_url"] is None
        assert status["token_expires_at"] is None
        assert status["user_info_available"] is False
        assert status["client_id_configured"] is True

    def test_configured(self, handler):
        handler.access_token = "at1"
        handler.token_expires_at = datetime.now() + timedelta(minutes=10)
        handler.user_info = {"sub": "u1"}
        status = handler.get_connection_status()
        assert status["connected"] is True
        assert status["token_expires_at"] is not None
