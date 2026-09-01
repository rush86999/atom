"""
Coverage + security bug-hunt tests for core/oauth_handler.py and
core/oauth_state_manager.py.

oauth_handler.py — OAuthConfig.is_configured, OAuthHandler authorization URL
                  generation, code-for-token exchange, refresh, Notion Basic
                  auth branch, error/token-leak handling.
oauth_state_manager.py — state generation/validation, checksum tamper
                         detection, expiry, single-use replay protection,
                         user binding, future-timestamp guard, pruning.

Security-bug tests carry a ``BUG:`` docstring (TDD).
"""
from __future__ import annotations

import os
import time
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from fastapi import HTTPException

# Set a SECRET_KEY before importing the state manager (required by __init__).
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-oauth-coverage-1234567890")

from core.oauth_handler import (
    GOOGLE_OAUTH_CONFIG,
    NOTION_OAUTH_CONFIG,
    OAuthConfig,
    OAuthHandler,
)
from core.oauth_state_manager import (
    DEFAULT_STATE_TTL,
    OAuthStateManager,
    get_oauth_state_manager,
)


# ===========================================================================
# OAuthConfig
# ===========================================================================
class TestOAuthConfig:
    def test_is_configured_true(self, monkeypatch):
        monkeypatch.setenv("OC_CLIENT_ID", "cid")
        monkeypatch.setenv("OC_SECRET", "sec")
        monkeypatch.setenv("OC_REDIRECT", "https://app/cb")
        cfg = OAuthConfig("OC_CLIENT_ID", "OC_SECRET", "OC_REDIRECT",
                          "https://auth", "https://token", ["scope1"])
        assert cfg.is_configured() is True
        assert cfg.client_id == "cid"
        assert cfg.additional_params == {}

    def test_is_configured_false_on_missing_client_id(self, monkeypatch):
        monkeypatch.delenv("OC_CLIENT_ID", raising=False)
        monkeypatch.setenv("OC_SECRET", "sec")
        monkeypatch.setenv("OC_REDIRECT", "https://app/cb")
        cfg = OAuthConfig("OC_CLIENT_ID", "OC_SECRET", "OC_REDIRECT",
                          "https://auth", "https://token", [])
        assert cfg.is_configured() is False

    def test_is_configured_false_on_missing_secret(self, monkeypatch):
        monkeypatch.setenv("OC_CLIENT_ID", "cid")
        monkeypatch.delenv("OC_SECRET", raising=False)
        monkeypatch.setenv("OC_REDIRECT", "https://app/cb")
        cfg = OAuthConfig("OC_CLIENT_ID", "OC_SECRET", "OC_REDIRECT",
                          "https://auth", "https://token", [])
        assert cfg.is_configured() is False

    def test_is_configured_false_on_missing_redirect(self, monkeypatch):
        monkeypatch.setenv("OC_CLIENT_ID", "cid")
        monkeypatch.setenv("OC_SECRET", "sec")
        monkeypatch.delenv("OC_REDIRECT", raising=False)
        cfg = OAuthConfig("OC_CLIENT_ID", "OC_SECRET", "OC_REDIRECT",
                          "https://auth", "https://token", [])
        assert cfg.is_configured() is False

    def test_additional_params_default_empty(self, monkeypatch):
        monkeypatch.setenv("OC_CLIENT_ID", "cid")
        monkeypatch.setenv("OC_SECRET", "sec")
        monkeypatch.setenv("OC_REDIRECT", "https://app/cb")
        cfg = OAuthConfig("OC_CLIENT_ID", "OC_SECRET", "OC_REDIRECT",
                          "https://auth", "https://token", [], None)
        assert cfg.additional_params == {}

    def test_preconfigured_notion_config(self):
        assert NOTION_OAUTH_CONFIG.token_url == "https://api.notion.com/v1/oauth/token"
        assert NOTION_OAUTH_CONFIG.scopes == []

    def test_preconfigured_google_config_scopes(self):
        assert "userinfo.email" in " ".join(GOOGLE_OAUTH_CONFIG.scopes)


# ===========================================================================
# OAuthHandler.get_authorization_url
# ===========================================================================
class TestGetAuthorizationUrl:
    def _configured(self, monkeypatch, token_url="https://token.example"):
        monkeypatch.setenv("OC_CLIENT_ID", "client-123")
        monkeypatch.setenv("OC_SECRET", "secret-456")
        monkeypatch.setenv("OC_REDIRECT", "https://app.example/callback")
        return OAuthConfig("OC_CLIENT_ID", "OC_SECRET", "OC_REDIRECT",
                           "https://auth.example", token_url, ["a", "b"])

    def test_url_contains_required_params(self, monkeypatch):
        cfg = self._configured(monkeypatch)
        url = OAuthHandler(cfg).get_authorization_url()
        assert url.startswith("https://auth.example?")
        assert "client_id=client-123" in url
        assert "redirect_uri=https://app.example/callback" in url
        assert "scope=a" in url and "scope" in url  # space-joined
        assert "response_type=code" in url
        assert "access_type=offline" in url

    def test_state_param_included_when_provided(self, monkeypatch):
        cfg = self._configured(monkeypatch)
        url = OAuthHandler(cfg).get_authorization_url(state="xyzSTATE123")
        assert "state=xyzSTATE123" in url

    def test_no_state_param_when_absent(self, monkeypatch):
        cfg = self._configured(monkeypatch)
        url = OAuthHandler(cfg).get_authorization_url()
        assert "state=" not in url

    def test_additional_params_merged(self, monkeypatch):
        monkeypatch.setenv("OC_CLIENT_ID", "cid")
        monkeypatch.setenv("OC_SECRET", "sec")
        monkeypatch.setenv("OC_REDIRECT", "https://app/cb")
        cfg = OAuthConfig("OC_CLIENT_ID", "OC_SECRET", "OC_REDIRECT",
                          "https://auth", "https://token", [],
                          additional_params={"expiration": "never", "name": "Atom"})
        url = OAuthHandler(cfg).get_authorization_url()
        assert "expiration=never" in url
        assert "name=Atom" in url

    def test_raises_when_not_configured(self, monkeypatch):
        monkeypatch.delenv("OC_CLIENT_ID", raising=False)
        monkeypatch.delenv("OC_SECRET", raising=False)
        monkeypatch.delenv("OC_REDIRECT", raising=False)
        cfg = OAuthConfig("OC_CLIENT_ID", "OC_SECRET", "OC_REDIRECT",
                          "https://auth", "https://token", [])
        with pytest.raises(HTTPException) as exc:
            OAuthHandler(cfg).get_authorization_url()
        assert exc.value.status_code == 500
        assert "CLIENT_ID" in exc.value.detail

    def test_no_prompt_by_default(self, monkeypatch):
        """Switch-Account support: without prompt the URL must stay unchanged
        so providers that don't understand the param are never sent it."""
        cfg = self._configured(monkeypatch)
        url = OAuthHandler(cfg).get_authorization_url(state="s1")
        assert "prompt=" not in url

    def test_prompt_select_account_added(self, monkeypatch):
        """prompt=select_account forces the provider's account picker instead
        of silently reusing the signed-in session (Microsoft/Google remember
        the last account — the "Switch Account" flow needs this)."""
        cfg = self._configured(monkeypatch)
        url = OAuthHandler(cfg).get_authorization_url(state="s1", prompt="select_account")
        assert "prompt=select_account" in url
        assert "state=s1" in url
        assert "client_id=client-123" in url


# ===========================================================================
# OAuthHandler.exchange_code_for_tokens
# ===========================================================================
class TestExchangeCodeForTokens:
    def _cfg(self, monkeypatch, token_url="https://token.example"):
        monkeypatch.setenv("OC_CLIENT_ID", "cid")
        monkeypatch.setenv("OC_SECRET", "sec")
        monkeypatch.setenv("OC_REDIRECT", "https://app/cb")
        return OAuthConfig("OC_CLIENT_ID", "OC_SECRET", "OC_REDIRECT",
                           "https://auth", token_url, [])

    @pytest.mark.asyncio
    async def test_success_returns_tokens(self, monkeypatch):
        cfg = self._cfg(monkeypatch)
        handler = OAuthHandler(cfg)
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "AT", "refresh_token": "RT"}
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            tokens = await handler.exchange_code_for_tokens("auth-code-123")
        assert tokens["access_token"] == "AT"
        assert tokens["refresh_token"] == "RT"

    @pytest.mark.asyncio
    async def test_not_configured_raises(self, monkeypatch):
        monkeypatch.delenv("OC_CLIENT_ID", raising=False)
        cfg = OAuthConfig("OC_CLIENT_ID", "OC_SECRET", "OC_REDIRECT",
                          "https://auth", "https://token", [])
        with pytest.raises(HTTPException) as exc:
            await OAuthHandler(cfg).exchange_code_for_tokens("code")
        assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_non_200_does_not_leak_response_body(self, monkeypatch):
        """BUG (exchange path): a non-200 token response must NOT echo the
        upstream body back to the client -- it may contain access tokens or
        internal provider details. Only the HTTP status is safe to expose."""
        cfg = self._cfg(monkeypatch)
        mock_resp = Mock()
        mock_resp.status_code = 400
        mock_resp.text = '{"error":"invalid_grant","access_token":"LEAKED_TOKEN"}'
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            with pytest.raises(HTTPException) as exc:
                await OAuthHandler(cfg).exchange_code_for_tokens("bad-code")
        assert exc.value.status_code == 400
        # The leaked token must NOT appear in the client-facing detail.
        assert "LEAKED_TOKEN" not in exc.value.detail
        assert "400" in exc.value.detail

    @pytest.mark.asyncio
    async def test_request_error_returns_500(self, monkeypatch):
        cfg = self._cfg(monkeypatch)
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock,
                   side_effect=httpx.ConnectError("dns fail")):
            with pytest.raises(HTTPException) as exc:
                await OAuthHandler(cfg).exchange_code_for_tokens("code")
        assert exc.value.status_code == 500
        assert exc.value.detail == "Internal error"

    @pytest.mark.asyncio
    async def test_notion_uses_basic_auth(self, monkeypatch):
        """Notion requires HTTP Basic auth header instead of body credentials."""
        cfg = self._cfg(monkeypatch, token_url="https://api.notion.com/v1/oauth/token")
        handler = OAuthHandler(cfg)
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "nt_abc"}
        captured = {}

        async def fake_post(self, url, data=None, headers=None, **kwargs):
            captured["headers"] = headers
            captured["data"] = data
            return mock_resp

        with patch("httpx.AsyncClient.post", new=fake_post):
            await handler.exchange_code_for_tokens("notion-code")
        # Basic auth header present, and client_secret NOT in the body.
        assert "Authorization" in captured["headers"]
        assert captured["headers"]["Authorization"].startswith("Basic ")
        assert "client_secret" not in captured["data"]

    @pytest.mark.asyncio
    async def test_non_notion_puts_credentials_in_body(self, monkeypatch):
        cfg = self._cfg(monkeypatch, token_url="https://github.com/login/oauth/access_token")
        handler = OAuthHandler(cfg)
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "gho_abc"}
        captured = {}

        async def fake_post(self, url, data=None, headers=None, **kwargs):
            captured["data"] = data
            captured["headers"] = headers
            return mock_resp

        with patch("httpx.AsyncClient.post", new=fake_post):
            await handler.exchange_code_for_tokens("gh-code")
        assert captured["data"]["client_id"] == "cid"
        assert captured["data"]["client_secret"] == "sec"
        assert "Authorization" not in captured["headers"]


# ===========================================================================
# OAuthHandler.refresh_access_token
# ===========================================================================
class TestRefreshAccessToken:
    def _cfg(self, monkeypatch):
        monkeypatch.setenv("OC_CLIENT_ID", "cid")
        monkeypatch.setenv("OC_SECRET", "sec")
        monkeypatch.setenv("OC_REDIRECT", "https://app/cb")
        return OAuthConfig("OC_CLIENT_ID", "OC_SECRET", "OC_REDIRECT",
                           "https://auth", "https://token.example", [])

    @pytest.mark.asyncio
    async def test_success_returns_new_tokens(self, monkeypatch):
        cfg = self._cfg(monkeypatch)
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "new-AT", "expires_in": 3600}
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            tokens = await OAuthHandler(cfg).refresh_access_token("rt-old")
        assert tokens["access_token"] == "new-AT"

    @pytest.mark.asyncio
    async def test_not_configured_raises(self, monkeypatch):
        monkeypatch.delenv("OC_CLIENT_ID", raising=False)
        cfg = OAuthConfig("OC_CLIENT_ID", "OC_SECRET", "OC_REDIRECT",
                          "https://auth", "https://token", [])
        with pytest.raises(HTTPException) as exc:
            await OAuthHandler(cfg).refresh_access_token("rt")
        assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_non_200_does_not_leak_response_body(self, monkeypatch):
        """BUG (refresh path): the refresh failure response body must NOT be
        forwarded to the client. Previously refresh_access_token set
        detail=f"Failed to refresh token: {response.text}", leaking the token
        endpoint response (which can include access tokens / provider internals).
        The exchange path was already fixed for this; refresh was missed.
        """
        cfg = self._cfg(monkeypatch)
        mock_resp = Mock()
        mock_resp.status_code = 401
        mock_resp.text = '{"error":"invalid_grant","access_token":"SHOULD_NOT_LEAK"}'
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            with pytest.raises(HTTPException) as exc:
                await OAuthHandler(cfg).refresh_access_token("expired-rt")
        assert exc.value.status_code == 400
        assert "SHOULD_NOT_LEAK" not in exc.value.detail
        assert "401" in exc.value.detail

    @pytest.mark.asyncio
    async def test_request_error_returns_500(self, monkeypatch):
        cfg = self._cfg(monkeypatch)
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock,
                   side_effect=httpx.ReadTimeout("slow")):
            with pytest.raises(HTTPException) as exc:
                await OAuthHandler(cfg).refresh_access_token("rt")
        assert exc.value.status_code == 500


# ===========================================================================
# OAuthStateManager — generation / validation / CSRF
# ===========================================================================
@pytest.fixture
def mgr():
    return OAuthStateManager(secret_key="unit-test-secret-key")


class TestOAuthStateManagerInit:
    def test_requires_secret_key(self, monkeypatch):
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("OAUTH_STATE_SECRET", raising=False)
        with pytest.raises(ValueError, match="SECRET_KEY"):
            OAuthStateManager()

    def test_uses_explicit_secret(self):
        m = OAuthStateManager(secret_key="explicit")
        assert m.secret_key == "explicit"

    def test_get_secret_key_from_env(self, monkeypatch):
        import core.oauth_state_manager as mod
        monkeypatch.setenv("SECRET_KEY", "envsecret")
        assert mod.OAuthStateManager._get_secret_key() == "envsecret"

    def test_falls_back_to_oauth_state_secret(self, monkeypatch):
        import core.oauth_state_manager as mod
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.setenv("OAUTH_STATE_SECRET", "oauthsecret")
        assert mod.OAuthStateManager._get_secret_key() == "oauthsecret"

    def test_consumed_tokens_starts_empty(self, mgr):
        assert mgr._consumed_tokens == {}


class TestStateGeneration:
    def test_generates_unique_states(self, mgr):
        states = {mgr.generate_state(user_id="u") for _ in range(50)}
        assert len(states) == 50

    def test_state_format_has_five_parts(self, mgr):
        state = mgr.generate_state(user_id="u1")
        assert len(state.split(":")) == 5

    def test_state_includes_user_id(self, mgr):
        state = mgr.generate_state(user_id="user-42")
        assert "user-42" in state

    def test_state_without_user_has_empty_segment(self, mgr):
        state = mgr.generate_state(user_id=None)
        parts = state.split(":")
        assert parts[2] == ""

    def test_default_ttl_is_600(self):
        assert DEFAULT_STATE_TTL == 600

    def test_custom_ttl_embedded_in_state(self, mgr):
        state = mgr.generate_state(user_id="u", ttl=120)
        # expires_at is the 4th field
        ts = int(state.split(":")[1])
        exp = int(state.split(":")[3])
        assert exp - ts == 120


class TestStateValidation:
    def test_valid_state_passes(self, mgr):
        state = mgr.generate_state(user_id="u1")
        result = mgr.validate_state(state, user_id="u1", require_user_match=True)
        assert result["valid"] is True
        assert result["user_id"] == "u1"
        assert result["expired"] is False
        assert result["tampered"] is False

    def test_anonymous_state_validates(self, mgr):
        state = mgr.generate_state(user_id=None)
        result = mgr.validate_state(state)
        assert result["valid"] is True
        assert result["user_id"] is None

    def test_missing_state_rejected(self, mgr):
        with pytest.raises(ValueError, match="missing"):
            mgr.validate_state("")

    def test_wrong_part_count_rejected(self, mgr):
        for malformed in ["a", "a:b", "a:b:c", "a:b:c:d", "a:b:c:d:e:f"]:
            with pytest.raises(ValueError, match="Invalid state format|State validation failed"):
                mgr.validate_state(malformed)

    def test_tampered_checksum_rejected(self, mgr):
        state = mgr.generate_state(user_id="u")
        parts = state.split(":")
        parts[-1] = "deadbeef" * 8  # wrong checksum
        with pytest.raises(ValueError, match="tampered"):
            mgr.validate_state(":".join(parts))

    def test_cross_secret_rejected(self, mgr):
        other = OAuthStateManager(secret_key="different-secret")
        state = mgr.generate_state(user_id="u")
        with pytest.raises(ValueError, match="tampered"):
            other.validate_state(state)

    def test_expired_state_rejected(self, mgr, monkeypatch):
        """A state whose embedded expires_at is in the past is rejected."""
        state = mgr.generate_state(user_id="u", ttl=1)
        # Force time forward past expiry.
        import core.oauth_state_manager as mod
        real_time = time.time
        monkeypatch.setattr(mod.time, "time", lambda: real_time() + 100)
        with pytest.raises(ValueError, match="expired"):
            mgr.validate_state(state)

    def test_future_timestamp_rejected(self, mgr):
        """A state with a creation timestamp >60s in the future (clock-skew /
        forgery guard) is rejected even if expires_at is far out."""
        import secrets
        tok = secrets.token_urlsafe(32)
        future_ts = int(time.time()) + 3600
        far_exp = future_ts + 9999
        chk = mgr._compute_checksum(tok, future_ts, None)
        state = f"{tok}:{future_ts}::{far_exp}:{chk}"
        with pytest.raises(ValueError, match="invalid timestamp"):
            mgr.validate_state(state)


class TestStateUserBinding:
    def test_require_user_match_mismatch_rejected(self, mgr):
        state = mgr.generate_state(user_id="alice")
        with pytest.raises(ValueError, match="different user"):
            mgr.validate_state(state, user_id="bob", require_user_match=True)

    def test_require_user_match_with_anonymous_state_passes(self, mgr):
        """If the state has no bound user, require_user_match does not fail."""
        state = mgr.generate_state(user_id=None)
        result = mgr.validate_state(state, user_id="anyone", require_user_match=True)
        assert result["valid"] is True

    def test_no_require_user_match_allows_any_caller(self, mgr):
        state = mgr.generate_state(user_id="alice")
        # Without require_user_match, the caller's user_id is ignored.
        result = mgr.validate_state(state, user_id="bob")
        assert result["valid"] is True
        assert result["user_id"] == "alice"


class TestStateSingleUse:
    """Replay protection: a consumed state cannot validate again."""

    def test_state_rejected_on_replay(self, mgr):
        state = mgr.generate_state(user_id="u")
        first = mgr.validate_state(state)
        assert first["valid"] is True
        with pytest.raises(ValueError, match="already been used"):
            mgr.validate_state(state)

    def test_distinct_states_each_valid_once(self, mgr):
        s1 = mgr.generate_state(user_id="u")
        s2 = mgr.generate_state(user_id="u")
        assert mgr.validate_state(s1)["valid"] is True
        assert mgr.validate_state(s2)["valid"] is True

    def test_consumed_recorded_with_expiry(self, mgr):
        state = mgr.generate_state(user_id="u", ttl=300)
        mgr.validate_state(state)
        tok = state.split(":")[0]
        assert tok in mgr._consumed_tokens
        assert mgr._consumed_tokens[tok] > int(time.time())


class TestStatePruning:
    def test_prune_drops_expired_consumed_tokens(self, mgr):
        state = mgr.generate_state(user_id="u", ttl=1)
        mgr.validate_state(state)  # consume
        tok = state.split(":")[0]
        assert tok in mgr._consumed_tokens
        # Advance time past expiry and trigger prune via another validation.
        import core.oauth_state_manager as mod
        real_time = time.time
        with patch.object(mod.time, "time", return_value=real_time() + 9999):
            # A fresh, non-expired state validated under the moved clock:
            # generate now (real time) then validate under moved clock would
            # expire; instead just call _prune_consumed directly.
            mgr._prune_consumed(int(real_time()) + 9999)
        assert tok not in mgr._consumed_tokens

    def test_prune_noop_on_empty(self, mgr):
        # No consumed tokens -> prune is a no-op (early return branch).
        mgr._prune_consumed(int(time.time()))
        assert mgr._consumed_tokens == {}


class TestChecksum:
    def test_checksum_deterministic(self, mgr):
        a = mgr._compute_checksum("t", 100, "u")
        b = mgr._compute_checksum("t", 100, "u")
        assert a == b

    def test_checksum_differs_per_input(self, mgr):
        base = mgr._compute_checksum("t", 100, "u")
        assert base != mgr._compute_checksum("t2", 100, "u")
        assert base != mgr._compute_checksum("t", 101, "u")
        assert base != mgr._compute_checksum("t", 100, "u2")
        assert base != mgr._compute_checksum("t", 100, None)

    def test_checksum_is_hex(self, mgr):
        chk = mgr._compute_checksum("t", 100, "u")
        assert all(c in "0123456789abcdef" for c in chk)


class TestExtractUserId:
    def test_extracts_user_from_valid_state(self, mgr):
        state = mgr.generate_state(user_id="user-99")
        assert mgr.extract_user_id(state) == "user-99"

    def test_returns_none_for_anonymous_state(self, mgr):
        state = mgr.generate_state(user_id=None)
        assert mgr.extract_user_id(state) is None

    def test_returns_none_for_malformed(self, mgr):
        assert mgr.extract_user_id("garbage") is None

    def test_returns_none_for_empty(self, mgr):
        assert mgr.extract_user_id("") is None

    def test_returns_none_when_split_raises(self, mgr):
        """extract_user_id swallows unexpected errors and returns None
        (defensive branch for non-string input)."""
        assert mgr.extract_user_id(None) is None  # type: ignore[arg-type]


class TestGetOAuthStateManagerSingleton:
    def setup_method(self):
        import core.oauth_state_manager as mod
        mod._oauth_state_manager = None

    def teardown_method(self):
        import core.oauth_state_manager as mod
        mod._oauth_state_manager = None

    def test_singleton_returns_same_instance(self):
        a = get_oauth_state_manager()
        b = get_oauth_state_manager()
        assert a is b
