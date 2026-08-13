# -*- coding: utf-8 -*-
"""Coverage wave 82 — core/oauth_user_context (OAuthUserContext +
OAuthUserContextManager).

ConnectionService / oauth_handler / httpx / slack_sdk are all mocked — no
network, no real credentials. Patch targets are the SOURCE modules
(core.connection_service / core.oauth_handler) because the functions do
function-local `from core.connection_service import ConnectionService`.

Coverage targets:
- get_access_token: no connection, valid token (no refresh), expired float
  timestamp → refresh, expired naive ISO → refresh, BUG W82-2 (expired AWARE
  ISO must refresh, not fail open), connection exception → None.
- _is_token_expired: no expiry (assume valid), str naive / aware / float /
  int / datetime input, >= 300s left → not expired, unparseable → valid.
- _refresh_token: no refresh token, success (updates connection), refresh
  returns no access_token, refresh exception → original connection.
- get_connection: cached / lazy load.
- is_authenticated: with/without access_token.
- revoke_access: success (clears cache), failure, exception.
- validate_access: no token, google/microsoft/slack (ok + error paths),
  unknown provider assume-valid, exception.
- OAuthUserContextManager: get_context create+cache, get_valid_token,
  revoke_all_for_user, clear_cache.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _ConnServiceStub:
    """Stands in for core.connection_service.ConnectionService."""

    def __init__(self, connection=None, delete_result=True, update_result=None):
        self._connection = connection
        self.delete_result = delete_result
        self.update_result = update_result
        self.get_calls = []
        self.delete_calls = []
        self.update_calls = []

    async def get_connection(self, user_id, provider):
        self.get_calls.append((user_id, provider))
        return self._connection

    async def delete_connection(self, user_id, provider):
        self.delete_calls.append((user_id, provider))
        return self.delete_result

    async def update_connection(self, user_id, provider, connection_data):
        self.update_calls.append((user_id, provider, connection_data))
        return self.update_result


def _conn(access_token="tok-1", refresh_token="rt-1", expires_at=None):
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
    }


def _patch_conn(connection=None, delete_result=True, update_result=None):
    """Patch core.connection_service.ConnectionService to a class whose
    instances are _ConnServiceStub; returns (cm, stub)."""
    stub = _ConnServiceStub(
        connection=connection, delete_result=delete_result, update_result=update_result
    )
    conn_cls = MagicMock(return_value=stub)
    return patch("core.connection_service.ConnectionService", conn_cls), stub


def _ctx():
    from core.oauth_user_context import OAuthUserContext

    return OAuthUserContext("u-1", "google")


def _patch_refresh(new_token_data=None, side_effect=None, configs=None):
    """Patch core.oauth_handler.OAuthHandler (class) + PROVIDER_CONFIGS so
    `_refresh_token` resolves the real import names."""
    handler_cls = MagicMock()
    method = AsyncMock()
    if side_effect is not None:
        method.side_effect = side_effect
    else:
        method.return_value = new_token_data
    handler_cls.return_value.refresh_access_token = method
    cfg = configs if configs is not None else {"google": object()}
    return (
        patch("core.oauth_handler.OAuthHandler", handler_cls),
        patch("core.oauth_handler.PROVIDER_CONFIGS", cfg),
        handler_cls,
    )


class TestGetAccessToken:
    @pytest.mark.asyncio
    async def test_no_connection(self):
        from core.oauth_user_context import OAuthUserContext

        ctx = OAuthUserContext("u-1", "google")
        cm, _ = _patch_conn(connection=None)
        with cm:
            assert await ctx.get_access_token() is None
        assert ctx._token_data is None

    @pytest.mark.asyncio
    async def test_valid_token_no_refresh(self):
        from core.oauth_user_context import OAuthUserContext

        conn = _conn(expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        ctx = OAuthUserContext("u-1", "google")
        cm, _ = _patch_conn(connection=conn)
        cm2, cm3, handler_cls = _patch_refresh(new_token_data=None)
        with cm, cm2, cm3:
            token = await ctx.get_access_token()
        assert token == "tok-1"
        handler_cls.return_value.refresh_access_token.assert_not_called()
        assert ctx._token_data == conn

    @pytest.mark.asyncio
    async def test_expired_float_timestamp_refreshes(self):
        from core.oauth_user_context import OAuthUserContext

        old = _conn(expires_at=datetime.now().timestamp() - 1000)
        new = _conn(access_token="tok-2", refresh_token="rt-1",
                    expires_at=datetime.now().timestamp() + 3600)
        cm, stub = _patch_conn(connection=old)
        cm2, cm3, handler_cls = _patch_refresh(new_token_data=new)
        with cm, cm2, cm3:
            ctx = OAuthUserContext("u-1", "google")
            token = await ctx.get_access_token()
        assert token == "tok-2"
        handler_cls.return_value.refresh_access_token.assert_awaited_once_with("rt-1")
        assert stub.update_calls == [("u-1", "google", new)]

    @pytest.mark.asyncio
    async def test_expired_naive_iso_refreshes(self):
        from core.oauth_user_context import OAuthUserContext

        old = _conn(expires_at=(datetime.now() - timedelta(hours=2)).isoformat())
        new = _conn(access_token="tok-3", refresh_token="rt-1")
        cm, _ = _patch_conn(connection=old)
        cm2, cm3, _ = _patch_refresh(new_token_data=new)
        with cm, cm2, cm3:
            ctx = OAuthUserContext("u-1", "google")
            token = await ctx.get_access_token()
        assert token == "tok-3"

    @pytest.mark.asyncio
    async def test_expired_aware_iso_refreshes(self):
        """BUG W82-2: an AWARE ISO expiry string ('2026-01-01T00:00:00+00:00')
        was compared against a naive datetime.now(), raising TypeError. The
        except branch assumed the token was VALID (fail-open) — an expired
        token was returned without refresh."""
        from core.oauth_user_context import OAuthUserContext

        old = _conn(expires_at=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat())
        new = _conn(access_token="tok-fresh", refresh_token="rt-1")
        cm, _ = _patch_conn(connection=old)
        cm2, cm3, handler_cls = _patch_refresh(new_token_data=new)
        with cm, cm2, cm3:
            ctx = OAuthUserContext("u-1", "google")
            token = await ctx.get_access_token()
        assert token == "tok-fresh"
        handler_cls.return_value.refresh_access_token.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_expired_aware_datetime_object_refreshes(self):
        from core.oauth_user_context import OAuthUserContext

        old = _conn(expires_at=datetime.now(timezone.utc) - timedelta(hours=2))
        new = _conn(access_token="tok-fresh2", refresh_token="rt-1")
        cm, _ = _patch_conn(connection=old)
        cm2, cm3, _ = _patch_refresh(new_token_data=new)
        with cm, cm2, cm3:
            ctx = OAuthUserContext("u-1", "google")
            token = await ctx.get_access_token()
        assert token == "tok-fresh2"

    @pytest.mark.asyncio
    async def test_connection_exception_returns_none(self):
        from core.oauth_user_context import OAuthUserContext

        class BoomConn:
            async def get_connection(self, user_id, provider):
                raise RuntimeError("conn service down")

        conn_cls = MagicMock(return_value=BoomConn())
        ctx = OAuthUserContext("u-1", "google")
        with patch("core.connection_service.ConnectionService", conn_cls):
            assert await ctx.get_access_token() is None


class TestIsTokenExpired:
    def test_no_expiry_assumed_valid(self):
        assert _ctx()._is_token_expired({}) is False

    def test_string_naive_expired(self):
        assert _ctx()._is_token_expired(_conn(expires_at="2020-01-01T00:00:00")) is True

    def test_aware_iso_past(self):
        expires_at = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        assert _ctx()._is_token_expired(_conn(expires_at=expires_at)) is True

    def test_float_future_but_within_5min(self):
        assert _ctx()._is_token_expired(_conn(expires_at=datetime.now().timestamp() + 120)) is True

    def test_int_far_future(self):
        assert _ctx()._is_token_expired(_conn(expires_at=int(datetime.now().timestamp()) + 3600)) is False

    def test_aware_future(self):
        expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
        assert _ctx()._is_token_expired(_conn(expires_at=expires_at)) is False

    def test_unparseable_assumed_valid(self):
        assert _ctx()._is_token_expired(_conn(expires_at="not-a-date")) is False


class TestRefreshToken:
    @pytest.mark.asyncio
    async def test_no_refresh_token(self):
        ctx = _ctx()
        conn = _conn(refresh_token=None)
        cm, cm2, handler_cls = _patch_refresh(new_token_data=None)
        with cm, cm2:
            result = await ctx._refresh_token(conn)
        assert result == conn
        handler_cls.return_value.refresh_access_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_success_updates_connection(self):
        ctx = _ctx()
        old = _conn()
        new = {"access_token": "new-tok", "refresh_token": "rt-2"}
        cm, stub = _patch_conn()
        cm2, cm3, handler_cls = _patch_refresh(new_token_data=new)
        with cm, cm2, cm3:
            result = await ctx._refresh_token(old)
        assert result == new
        handler_cls.return_value.refresh_access_token.assert_awaited_once_with("rt-1")
        assert stub.update_calls == [("u-1", "google", new)]

    @pytest.mark.asyncio
    async def test_refresh_returns_no_access_token(self):
        ctx = _ctx()
        old = _conn()
        cm, stub = _patch_conn()
        cm2, cm3, _ = _patch_refresh(new_token_data={})
        with cm, cm2, cm3:
            result = await ctx._refresh_token(old)
        assert result == old
        assert stub.update_calls == []

    @pytest.mark.asyncio
    async def test_refresh_exception_returns_original(self):
        ctx = _ctx()
        old = _conn()
        cm, cm2, _ = _patch_refresh(side_effect=RuntimeError("refresh failed"))
        with cm, cm2:
            result = await ctx._refresh_token(old)
        assert result == old

    @pytest.mark.asyncio
    async def test_unknown_provider_no_config_returns_original(self):
        """BUG W82-2b: the old code imported a nonexistent `oauth_handler`
        global (ImportError) — refresh silently never ran. A provider with no
        registered config must degrade gracefully, not crash."""
        from core.oauth_user_context import OAuthUserContext

        ctx = OAuthUserContext("u-1", "notion-ish")
        old = _conn()
        cm, cm2, handler_cls = _patch_refresh(new_token_data=None, configs={})
        with cm, cm2:
            result = await ctx._refresh_token(old)
        assert result == old
        handler_cls.assert_not_called()


class TestConnectionHelpers:
    @pytest.mark.asyncio
    async def test_get_connection_cached(self):
        ctx = _ctx()
        ctx._token_data = {"access_token": "cached"}
        assert await ctx.get_connection() == {"access_token": "cached"}

    @pytest.mark.asyncio
    async def test_get_connection_lazy_loads(self):
        ctx = _ctx()
        conn = _conn(expires_at=datetime.now().timestamp() + 3600)
        cm, _ = _patch_conn(connection=conn)
        with cm:
            result = await ctx.get_connection()
        assert result == conn

    def test_is_authenticated_with_token(self):
        ctx = _ctx()
        ctx._token_data = {"access_token": "abc"}
        assert ctx.is_authenticated() is True

    def test_is_authenticated_no_token(self):
        ctx = _ctx()
        assert ctx.is_authenticated() is False
        ctx._token_data = {}
        assert ctx.is_authenticated() is False


class TestRevokeAccess:
    @pytest.mark.asyncio
    async def test_success(self):
        ctx = _ctx()
        ctx._token_data = {"access_token": "abc"}
        cm, stub = _patch_conn(delete_result=True)
        with cm:
            assert await ctx.revoke_access() is True
        assert ctx._token_data is None
        assert stub.delete_calls == [("u-1", "google")]

    @pytest.mark.asyncio
    async def test_failure(self):
        ctx = _ctx()
        cm, _ = _patch_conn(delete_result=False)
        with cm:
            assert await ctx.revoke_access() is False

    @pytest.mark.asyncio
    async def test_exception(self):
        class BoomConn:
            async def delete_connection(self, user_id, provider):
                raise RuntimeError("down")

        conn_cls = MagicMock(return_value=BoomConn())
        ctx = _ctx()
        with patch("core.connection_service.ConnectionService", conn_cls):
            assert await ctx.revoke_access() is False


class TestValidateAccess:
    @pytest.mark.asyncio
    async def test_no_token(self):
        ctx = _ctx()
        cm, _ = _patch_conn(connection=None)
        with cm:
            assert await ctx.validate_access() is False

    @pytest.mark.asyncio
    async def test_google_valid(self):
        ctx = _ctx()
        conn = _conn(expires_at=datetime.now().timestamp() + 3600)
        cm, _ = _patch_conn(connection=conn)
        with cm, patch("httpx.AsyncClient") as client_cls:
            client_cls.return_value.__aenter__.return_value.get.return_value = MagicMock(status_code=200)
            assert await ctx.validate_access() is True

    @pytest.mark.asyncio
    async def test_google_invalid(self):
        ctx = _ctx()
        conn = _conn(expires_at=datetime.now().timestamp() + 3600)
        cm, _ = _patch_conn(connection=conn)
        with cm, patch("httpx.AsyncClient") as client_cls:
            client_cls.return_value.__aenter__.return_value.get.return_value = MagicMock(status_code=401)
            assert await ctx.validate_access() is False

    @pytest.mark.asyncio
    async def test_microsoft_valid(self):
        from core.oauth_user_context import OAuthUserContext

        ctx = OAuthUserContext("u-1", "microsoft")
        conn = _conn(expires_at=datetime.now().timestamp() + 3600)
        cm, _ = _patch_conn(connection=conn)
        with cm, patch("httpx.AsyncClient") as client_cls:
            client_cls.return_value.__aenter__.return_value.get.return_value = MagicMock(status_code=200)
            assert await ctx.validate_access() is True

    @pytest.mark.asyncio
    async def test_microsoft_invalid(self):
        from core.oauth_user_context import OAuthUserContext

        ctx = OAuthUserContext("u-1", "microsoft")
        conn = _conn(expires_at=datetime.now().timestamp() + 3600)
        cm, _ = _patch_conn(connection=conn)
        with cm, patch("httpx.AsyncClient") as client_cls:
            client_cls.return_value.__aenter__.return_value.get.return_value = MagicMock(status_code=403)
            assert await ctx.validate_access() is False

    @pytest.mark.asyncio
    async def test_microsoft_exception(self):
        from core.oauth_user_context import OAuthUserContext

        ctx = OAuthUserContext("u-1", "microsoft")
        conn = _conn(expires_at=datetime.now().timestamp() + 3600)
        cm, _ = _patch_conn(connection=conn)
        with cm, patch("httpx.AsyncClient") as client_cls:
            client_cls.side_effect = RuntimeError("graph down")
            assert await ctx.validate_access() is False

    @pytest.mark.asyncio
    async def test_slack_valid(self):
        from core.oauth_user_context import OAuthUserContext

        ctx = OAuthUserContext("u-1", "slack")
        conn = _conn(expires_at=datetime.now().timestamp() + 3600)
        cm, _ = _patch_conn(connection=conn)
        client = MagicMock()
        client.auth_test = AsyncMock(return_value={"ok": True})
        with cm, patch("slack_sdk.web.async_client.AsyncWebClient", return_value=client):
            assert await ctx.validate_access() is True

    @pytest.mark.asyncio
    async def test_slack_invalid(self):
        from core.oauth_user_context import OAuthUserContext

        ctx = OAuthUserContext("u-1", "slack")
        conn = _conn(expires_at=datetime.now().timestamp() + 3600)
        cm, _ = _patch_conn(connection=conn)
        client = MagicMock()
        client.auth_test = AsyncMock(return_value={"ok": False})
        with cm, patch("slack_sdk.web.async_client.AsyncWebClient", return_value=client):
            assert await ctx.validate_access() is False

    @pytest.mark.asyncio
    async def test_slack_exception(self):
        from core.oauth_user_context import OAuthUserContext

        ctx = OAuthUserContext("u-1", "slack")
        conn = _conn(expires_at=datetime.now().timestamp() + 3600)
        cm, _ = _patch_conn(connection=conn)
        client = MagicMock()
        client.auth_test = AsyncMock(side_effect=RuntimeError("api down"))
        with cm, patch("slack_sdk.web.async_client.AsyncWebClient", return_value=client):
            assert await ctx.validate_access() is False

    @pytest.mark.asyncio
    async def test_unknown_provider_assumed_valid(self):
        from core.oauth_user_context import OAuthUserContext

        ctx = OAuthUserContext("u-1", "github")
        conn = _conn(expires_at=datetime.now().timestamp() + 3600)
        cm, _ = _patch_conn(connection=conn)
        with cm:
            assert await ctx.validate_access() is True
    @pytest.mark.asyncio
    async def test_validation_exception(self):
        ctx = _ctx()

        class BoomConn:
            async def get_connection(self, user_id, provider):
                raise RuntimeError("down")

        conn_cls = MagicMock(return_value=BoomConn())
        with patch("core.connection_service.ConnectionService", conn_cls):
            assert await ctx.validate_access() is False

    @pytest.mark.asyncio
    async def test_outer_except_via_validator_raise(self):
        """validate_access's outer except: a provider validator raising
        propagates out of the dispatch and is caught at the top level."""
        from unittest.mock import AsyncMock

        ctx = _ctx()
        conn = _conn(expires_at=datetime.now().timestamp() + 3600)
        cm, _ = _patch_conn(connection=conn)
        with cm:
            ctx._validate_google_token = AsyncMock(side_effect=RuntimeError("boom"))
            assert await ctx.validate_access() is False

    @pytest.mark.asyncio
    async def test_google_network_error(self):
        ctx = _ctx()
        conn = _conn(expires_at=datetime.now().timestamp() + 3600)
        cm, _ = _patch_conn(connection=conn)
        with cm, patch("httpx.AsyncClient") as client_cls:
            client_cls.side_effect = RuntimeError("network down")
            assert await ctx.validate_access() is False


class TestOAuthUserContextManager:
    @pytest.mark.asyncio
    async def test_get_context_caches(self):
        from core.oauth_user_context import OAuthUserContextManager

        mgr = OAuthUserContextManager()
        c1 = mgr.get_context("u-1", "google")
        c2 = mgr.get_context("u-1", "google")
        c3 = mgr.get_context("u-1", "microsoft")
        assert c1 is c2
        assert c3 is not c1

    @pytest.mark.asyncio
    async def test_get_valid_token(self):
        from core.oauth_user_context import OAuthUserContextManager

        mgr = OAuthUserContextManager()
        conn = _conn(expires_at=datetime.now().timestamp() + 3600)
        cm, _ = _patch_conn(connection=conn)
        with cm:
            assert await mgr.get_valid_token("u-1", "google") == "tok-1"

    @pytest.mark.asyncio
    async def test_revoke_all_for_user(self):
        from core.oauth_user_context import OAuthUserContextManager

        mgr = OAuthUserContextManager()
        cm, _ = _patch_conn(delete_result=True)
        with cm:
            results = await mgr.revoke_all_for_user("u-1", ["google", "microsoft"])
        assert results == {"google": True, "microsoft": True}

    def test_clear_cache(self):
        from core.oauth_user_context import OAuthUserContextManager

        mgr = OAuthUserContextManager()
        c1 = mgr.get_context("u-1", "google")
        mgr.clear_cache()
        assert mgr.get_context("u-1", "google") is not c1
