"""Coverage wave 98 — integrations/auth_handler_zoom.py (TDD, 0% baseline).

Fully mocked aiohttp (fake ClientSession injected at the module level), zero
network, zero LLM spend.

Covers: __init__ (env defaults/overrides), get_authorization_url (with/without
state), _get_basic_auth_header, exchange_code_for_token (success stores tokens,
non-200 -> 400 "Internal error", exception -> 500), refresh_access_token (no
refresh token -> 400, success, non-200 -> 400, exception -> 500), get_user_info
(no token -> 401, success, non-200 -> 400, exception -> 500), revoke_token
(no token -> True, 200 -> True + clears state, non-200 -> False, exception ->
False), is_token_valid (no token/expiry, expired, valid, 5-min buffer),
ensure_valid_token (valid, refreshed via refresh token, no refresh -> 401),
make_authenticated_request (success JSON, 204 -> {}, non-2xx -> HTTPException,
401 -> refresh + retry, exception -> 500), get_connection_status (all fields).
"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from integrations import auth_handler_zoom as zm
from integrations.auth_handler_zoom import ZoomAuthHandler


# ── Fake aiohttp plumbing ────────────────────────────────────────────────────
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
    """aiohttp's session.post() returns a context manager (not a coroutine);
    the real request happens in __aenter__."""

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

    def request(self, *a, **k):
        return _FakeRespCM(self._next())


def _mock_session(*responses):
    return patch.object(
        zm.aiohttp,
        "ClientSession",
        MagicMock(return_value=_FakeSession(responses)),
    )


def _valid_token_state(handler):
    handler.access_token = "tok-zoom"
    handler.refresh_token = "rt-zoom"
    handler.token_expires_at = datetime.now() + timedelta(hours=1)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("ZOOM_CLIENT_ID", "zcid")
    monkeypatch.setenv("ZOOM_CLIENT_SECRET", "zcsecret")
    monkeypatch.setenv("ZOOM_REDIRECT_URI", "https://app.example/zoom/cb")


@pytest.fixture
def handler():
    return ZoomAuthHandler()


class TestInit:
    def test_env_overrides(self):
        h = ZoomAuthHandler()
        assert h.client_id == "zcid"
        assert h.client_secret == "zcsecret"
        assert h.redirect_uri == "https://app.example/zoom/cb"
        assert h.token_url == "https://zoom.us/oauth/token"
        assert h.authorize_url == "https://zoom.us/oauth/authorize"
        assert h.api_base_url == "https://api.zoom.us/v2"
        assert h.access_token is None and h.refresh_token is None
        assert h.token_expires_at is None and h.user_info is None

    def test_env_defaults(self, monkeypatch):
        monkeypatch.delenv("ZOOM_CLIENT_ID", raising=False)
        monkeypatch.delenv("ZOOM_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("ZOOM_REDIRECT_URI", raising=False)
        h = ZoomAuthHandler()
        assert h.client_id == ""
        assert h.client_secret == ""
        assert h.redirect_uri == "http://localhost:5058/api/auth/zoom/callback"


class TestAuthorizationUrl:
    def test_with_state(self, handler):
        url = handler.get_authorization_url(state="st-1")
        assert url.startswith("https://zoom.us/oauth/authorize?")
        assert "response_type=code" in url
        assert "client_id=zcid" in url
        assert "redirect_uri=https://app.example/zoom/cb" in url
        assert "state=st-1" in url
        assert "meeting:write:admin" in url
        assert "recording:read:admin" in url

    def test_without_state(self, handler):
        url = handler.get_authorization_url()
        assert "state=" not in url

    def test_basic_auth_header(self, handler):
        import base64

        expected = base64.b64encode(b"zcid:zcsecret").decode()
        assert handler._get_basic_auth_header() == expected


class TestExchangeCode:
    async def test_success(self, handler):
        with _mock_session(_FakeResponse(
                200, {"access_token": "at1", "refresh_token": "rt1",
                      "expires_in": 7200})):
            out = await handler.exchange_code_for_token("code-1")
        assert out["access_token"] == "at1"
        assert handler.access_token == "at1"
        assert handler.refresh_token == "rt1"
        assert handler.token_expires_at > datetime.now()

    async def test_expires_in_default(self, handler):
        with _mock_session(_FakeResponse(
                200, {"access_token": "at1", "refresh_token": "rt1"})):
            out = await handler.exchange_code_for_token("code-1")
        assert out["access_token"] == "at1"
        assert handler.token_expires_at > datetime.now()

    async def test_non_200_raises_400(self, handler):
        with _mock_session(_FakeResponse(400, text="invalid_grant")):
            with pytest.raises(HTTPException) as ei:
                await handler.exchange_code_for_token("bad")
        assert ei.value.status_code == 400
        assert ei.value.detail == "Internal error"

    async def test_exception_raises_500(self, handler):
        with patch.object(
                zm.aiohttp, "ClientSession",
                side_effect=RuntimeError("net down")):
            with pytest.raises(HTTPException) as ei:
                await handler.exchange_code_for_token("code-1")
        assert ei.value.status_code == 500


class TestRefresh:
    async def test_no_refresh_token(self, handler):
        with pytest.raises(HTTPException) as ei:
            await handler.refresh_access_token()
        assert ei.value.status_code == 400
        assert ei.value.detail == "No refresh token available"

    async def test_success(self, handler):
        handler.refresh_token = "rt-old"
        with _mock_session(_FakeResponse(
                200, {"access_token": "at2", "refresh_token": "rt2",
                      "expires_in": 3600})):
            out = await handler.refresh_access_token()
        assert out["access_token"] == "at2"
        assert handler.access_token == "at2"
        assert handler.refresh_token == "rt2"

    async def test_non_200_raises_400(self, handler):
        handler.refresh_token = "rt-old"
        with _mock_session(_FakeResponse(400, text="invalid_grant")):
            with pytest.raises(HTTPException) as ei:
                await handler.refresh_access_token()
        assert ei.value.status_code == 400

    async def test_exception_raises_500(self, handler):
        handler.refresh_token = "rt-old"
        with patch.object(
                zm.aiohttp, "ClientSession",
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
                200, {"id": "u1", "display_name": "Rushi"})):
            out = await handler.get_user_info()
        assert out["display_name"] == "Rushi"
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
                zm.aiohttp, "ClientSession",
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
        handler.user_info = {"id": "u1"}
        with _mock_session(_FakeResponse(200)):
            assert await handler.revoke_token() is True
        assert handler.access_token is None
        assert handler.refresh_token is None
        assert handler.token_expires_at is None
        assert handler.user_info is None

    async def test_non_200_returns_false(self, handler):
        handler.access_token = "at1"
        with _mock_session(_FakeResponse(500, text="fail")):
            assert await handler.revoke_token() is False

    async def test_exception_returns_false(self, handler):
        handler.access_token = "at1"
        with patch.object(
                zm.aiohttp, "ClientSession",
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
        _valid_token_state(handler)
        assert await handler.ensure_valid_token() == "tok-zoom"

    async def test_invalid_with_refresh(self, handler):
        handler.access_token = "stale"
        handler.refresh_token = "rt1"
        with _mock_session(_FakeResponse(
                200, {"access_token": "fresh", "refresh_token": "rt2",
                      "expires_in": 3600})):
            assert await handler.ensure_valid_token() == "fresh"

    async def test_invalid_without_refresh(self, handler):
        handler.access_token = "stale"
        handler.refresh_token = None
        with pytest.raises(HTTPException) as ei:
            await handler.ensure_valid_token()
        assert ei.value.status_code == 401


class TestMakeAuthenticatedRequest:
    async def test_success_json(self, handler):
        _valid_token_state(handler)
        with _mock_session(_FakeResponse(200, {"ok": True})):
            out = await handler.make_authenticated_request(
                "GET", "/users/me", params={"x": 1})
        assert out == {"ok": True}

    async def test_204_returns_empty(self, handler):
        _valid_token_state(handler)
        with _mock_session(_FakeResponse(204)):
            out = await handler.make_authenticated_request(
                "DELETE", "/meetings/1")
        assert out == {}

    async def test_non_2xx_raises(self, handler):
        _valid_token_state(handler)
        with _mock_session(_FakeResponse(404, text="missing")):
            with pytest.raises(HTTPException) as ei:
                await handler.make_authenticated_request("GET", "/users/me")
        assert ei.value.status_code == 404

    async def test_401_refresh_and_retry(self, handler):
        _valid_token_state(handler)
        with _mock_session(
                _FakeResponse(401, text="expired"),
                _FakeResponse(200, {"access_token": "fresh",
                                    "refresh_token": "rt2",
                                    "expires_in": 3600}),
                _FakeResponse(200, {"retried": True})):
            out = await handler.make_authenticated_request(
                "GET", "/users/me")
        assert out == {"retried": True}
        assert handler.access_token == "fresh"

    async def test_exception_raises_500(self, handler):
        _valid_token_state(handler)
        with patch.object(
                zm.aiohttp, "ClientSession",
                side_effect=RuntimeError("boom")):
            with pytest.raises(HTTPException) as ei:
                await handler.make_authenticated_request("GET", "/users/me")
        assert ei.value.status_code == 500


class TestConnectionStatus:
    def test_empty(self, handler):
        status = handler.get_connection_status()
        assert status["connected"] is False
        assert status["has_access_token"] is False
        assert status["has_refresh_token"] is False
        assert status["token_expires_at"] is None
        assert status["user_info_available"] is False
        assert status["client_id_configured"] is True
        assert status["client_secret_configured"] is True

    def test_configured(self, handler):
        _valid_token_state(handler)
        handler.user_info = {"id": "u1"}
        status = handler.get_connection_status()
        assert status["connected"] is True
        assert status["has_access_token"] is True
        assert status["has_refresh_token"] is True
        assert status["token_expires_at"] is not None
        assert status["user_info_available"] is True
