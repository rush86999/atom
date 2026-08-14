"""Coverage wave 98 — integrations/auth_handler_dropbox.py (TDD, 0%
baseline).

Fully mocked (fake aiohttp session), zero network, zero LLM spend.

BUG FOUND + FIXED (TDD RED->GREEN): same HTTPException-swallowing defect as
the zoom/salesforce handlers — the non-200 branches of
exchange_code_for_token / refresh_access_token / get_user_info raise
HTTPException(400) inside the try-block but the trailing `except Exception`
re-raised them as HTTPException(500), so every OAuth/API error surfaced as a
500 and the 400 raise sites were dead code. `except HTTPException: raise`
added; the 400 tests were RED before the fix.

Covers: __init__ (env override/defaults), get_authorization_url (explicit
state / auto 43-char state, token_access_type=offline), exchange_code_for_token
(success stores tokens + account_id + expires_at, expires_in int mapping,
non-200 -> 400, exception -> 500), refresh_access_token (no refresh token ->
400, success with new refresh token, success keeping old refresh token,
non-200 -> 400, exception -> 500), get_user_info (no token -> 401, success via
POST users/get_current_account, non-200 -> 400, exception -> 500),
revoke_token (no token -> True, 200 clears state incl. account_id, non-200 ->
False, exception -> False), is_token_valid (all branches), ensure_valid_token
(valid/refresh/401), get_connection_status (all fields).
"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from integrations import auth_handler_dropbox as dbx
from integrations.auth_handler_dropbox import DropboxAuthHandler


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


def _mock_session(*responses):
    return patch.object(
        dbx.aiohttp,
        "ClientSession",
        MagicMock(return_value=_FakeSession(responses)),
    )


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("DROPBOX_CLIENT_ID", "dbcid")
    monkeypatch.setenv("DROPBOX_CLIENT_SECRET", "dbcsecret")
    monkeypatch.setenv("DROPBOX_REDIRECT_URI", "https://app.example/db/cb")


@pytest.fixture
def handler():
    return DropboxAuthHandler()


class TestInit:
    def test_env_overrides(self):
        h = DropboxAuthHandler()
        assert h.client_id == "dbcid"
        assert h.client_secret == "dbcsecret"
        assert h.redirect_uri == "https://app.example/db/cb"
        assert h.authorize_url == "https://www.dropbox.com/oauth2/authorize"
        assert h.token_url == "https://api.dropboxapi.com/oauth2/token"
        assert h.api_base_url == "https://api.dropboxapi.com/2"
        assert h.access_token is None and h.account_id is None

    def test_env_defaults(self, monkeypatch):
        monkeypatch.delenv("DROPBOX_CLIENT_ID", raising=False)
        monkeypatch.delenv("DROPBOX_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("DROPBOX_REDIRECT_URI", raising=False)
        h = DropboxAuthHandler()
        assert h.client_id == ""
        assert h.client_secret == ""
        assert h.redirect_uri == \
            "http://localhost:3000/api/auth/callback/dropbox"


class TestAuthorizationUrl:
    def test_explicit_state(self, handler):
        url = handler.get_authorization_url(state="s1")
        assert url.startswith(
            "https://www.dropbox.com/oauth2/authorize?")
        assert "client_id=dbcid" in url
        assert "response_type=code" in url
        assert "token_access_type=offline" in url
        assert "state=s1" in url

    def test_auto_state(self, handler):
        url = handler.get_authorization_url()
        assert "state=" in url
        assert len(url.split("state=")[1].split("&")[0]) == 43


class TestExchangeCode:
    async def test_success(self, handler):
        with _mock_session(_FakeResponse(
                200, {"access_token": "at1", "refresh_token": "rt1",
                      "account_id": "dbid:1", "expires_in": 14400})):
            out = await handler.exchange_code_for_token("code-1")
        assert out["access_token"] == "at1"
        assert handler.access_token == "at1"
        assert handler.refresh_token == "rt1"
        assert handler.account_id == "dbid:1"
        assert handler.token_expires_at > datetime.now()

    async def test_expires_in_default(self, handler):
        with _mock_session(_FakeResponse(
                200, {"access_token": "at1", "refresh_token": "rt1"})):
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
                dbx.aiohttp, "ClientSession",
                side_effect=RuntimeError("net down")):
            with pytest.raises(HTTPException) as ei:
                await handler.exchange_code_for_token("code-1")
        assert ei.value.status_code == 500


class TestRefresh:
    async def test_no_refresh_token(self, handler):
        with pytest.raises(HTTPException) as ei:
            await handler.refresh_access_token()
        assert ei.value.status_code == 400

    async def test_success_new_refresh_token(self, handler):
        handler.refresh_token = "rt-old"
        with _mock_session(_FakeResponse(
                200, {"access_token": "at2", "refresh_token": "rt2",
                      "expires_in": 14400})):
            out = await handler.refresh_access_token()
        assert out["access_token"] == "at2"
        assert handler.refresh_token == "rt2"

    async def test_success_keeps_old_refresh_token(self, handler):
        handler.refresh_token = "rt-old"
        with _mock_session(_FakeResponse(
                200, {"access_token": "at2", "expires_in": 14400})):
            out = await handler.refresh_access_token()
        assert handler.refresh_token == "rt-old"

    async def test_non_200_raises_400(self, handler):
        handler.refresh_token = "rt-old"
        with _mock_session(_FakeResponse(400, text="bad")):
            with pytest.raises(HTTPException) as ei:
                await handler.refresh_access_token()
        assert ei.value.status_code == 400

    async def test_exception_raises_500(self, handler):
        handler.refresh_token = "rt-old"
        with patch.object(
                dbx.aiohttp, "ClientSession",
                side_effect=RuntimeError("boom")):
            with pytest.raises(HTTPException) as ei:
                await handler.refresh_access_token()
        assert ei.value.status_code == 500


class TestGetUserInfo:
    async def test_no_token(self, handler):
        with pytest.raises(HTTPException) as ei:
            await handler.get_user_info()
        assert ei.value.status_code == 401

    async def test_success(self, handler):
        handler.access_token = "at1"
        with _mock_session(_FakeResponse(
                200, {"account_id": "dbid:1", "email": "a@b.c"})):
            out = await handler.get_user_info()
        assert out["email"] == "a@b.c"
        assert handler.user_info == out

    async def test_non_200_raises_400(self, handler):
        handler.access_token = "at1"
        with _mock_session(_FakeResponse(401, text="unauthorized")):
            with pytest.raises(HTTPException) as ei:
                await handler.get_user_info()
        assert ei.value.status_code == 400

    async def test_exception_raises_500(self, handler):
        handler.access_token = "at1"
        with patch.object(
                dbx.aiohttp, "ClientSession",
                side_effect=RuntimeError("boom")):
            with pytest.raises(HTTPException) as ei:
                await handler.get_user_info()
        assert ei.value.status_code == 500


class TestRevoke:
    async def test_no_token_returns_true(self, handler):
        assert await handler.revoke_token() is True

    async def test_success_clears_state(self, handler):
        handler.access_token = "at1"
        handler.refresh_token = "rt1"
        handler.token_expires_at = datetime.now()
        handler.user_info = {"account_id": "dbid:1"}
        handler.account_id = "dbid:1"
        with _mock_session(_FakeResponse(200)):
            assert await handler.revoke_token() is True
        assert handler.access_token is None
        assert handler.refresh_token is None
        assert handler.token_expires_at is None
        assert handler.user_info is None
        assert handler.account_id is None

    async def test_non_200_returns_false(self, handler):
        handler.access_token = "at1"
        with _mock_session(_FakeResponse(500, text="fail")):
            assert await handler.revoke_token() is False

    async def test_exception_returns_false(self, handler):
        handler.access_token = "at1"
        with patch.object(
                dbx.aiohttp, "ClientSession",
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
                200, {"access_token": "fresh", "expires_in": 14400})):
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
        assert status["account_id"] is None
        assert status["token_expires_at"] is None
        assert status["user_info_available"] is False
        assert status["client_id_configured"] is True
        assert status["client_secret_configured"] is True

    def test_configured(self, handler):
        handler.access_token = "at1"
        handler.account_id = "dbid:1"
        handler.token_expires_at = datetime.now() + timedelta(minutes=10)
        handler.user_info = {"account_id": "dbid:1"}
        status = handler.get_connection_status()
        assert status["connected"] is True
        assert status["has_access_token"] is True
        assert status["account_id"] == "dbid:1"
        assert status["token_expires_at"] is not None
        assert status["user_info_available"] is True
