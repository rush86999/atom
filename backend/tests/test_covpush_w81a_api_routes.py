"""Coverage wave 81a — api/oauth_routes.py (79% -> 100%) + tail lines of
api/social_media_routes.py (98% -> 100%).

Prior waves covered the oauth_routes auth matrix (round71) and the signed
state CSRF round-trip (bughunt 2026-08-09). This wave finishes the remaining
lines:

oauth_routes missing at baseline:
  51-52  _state_hmac_key branches (SECRET_KEY set / fallback)
  65-71  _build_state body (direct unit coverage; prior suite only via HTTP)
  76-93  _validate_state (None / wrong part count / wrong prefix / provider
         mismatch / user mismatch / expired / non-numeric expiry / tampered)
  106    oauth_rate_limit 429 raise
  167-178 _handle_callback_logic new-token branch (create OAuthToken)
  183-185 _handle_callback_logic generic exception -> 500
  249    callback unsupported-provider 400
  282-289 list_oauth_tokens body (empty / provider filter)
  312-323 revoke_oauth_token body (found -> inactive, not-found -> 404)
  328-342 oauth_config_status body

social_media_routes missing at baseline:
  600-604 platform without a poster function (not-yet-implemented branch)
  749, 785 `except HTTPException: raise` re-raise paths

No network, no LLM spend, no real DB — FastAPI TestClient + MagicMock deps.
"""
import hashlib
import os
import time as _time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api import oauth_routes
from api import social_media_routes
from api.social_media_routes import PlatformConfig
from core.database import get_db
from core.oauth_handler import OAuthHandler


FAKE_USER = SimpleNamespace(id="user-1", tenant_id="t1")

# ============================================================================
# api/oauth_routes.py
# ============================================================================


class _OAuthApp:
    """Helpers shared by the oauth tests."""

    @staticmethod
    def client(monkeypatch, db=None, user=FAKE_USER, override_auth=True,
               patch_body_user=True):
        """Build a TestClient over the oauth router.

        ``override_auth`` controls the endpoint Depends(get_current_user);
        ``patch_body_user`` controls the module-global ``get_current_user``
        awaited inside handler bodies (``_handle_callback_logic``,
        ``list_oauth_tokens``, ``revoke_oauth_token``).
        """
        app = FastAPI()
        app.include_router(oauth_routes.router)
        app.dependency_overrides[get_db] = (
            lambda: db if db is not None else MagicMock()
        )
        if override_auth:
            app.dependency_overrides[oauth_routes.get_current_user] = (
                lambda: user
            )
        if patch_body_user:
            monkeypatch.setattr(
                oauth_routes, "get_current_user", AsyncMock(return_value=user)
            )
        return TestClient(app, raise_server_exceptions=False)

    @staticmethod
    def fresh_limiter(monkeypatch, allowed=True, remaining=1000):
        limiter = MagicMock()
        limiter.check.return_value = (allowed, remaining)
        monkeypatch.setattr(oauth_routes, "_oauth_limiter", limiter)
        return limiter

    @staticmethod
    def patch_exchange(monkeypatch, token_data=None, side_effect=None):
        td = token_data if token_data is not None else {
            "access_token": "at-1",
            "refresh_token": "rt-1",
            "token_type": "Bearer",
            "scope": "read",
            "expires_in": 3600,
        }
        mock = AsyncMock(return_value=td, side_effect=side_effect)
        monkeypatch.setattr(OAuthHandler, "exchange_code_for_tokens", mock)
        return mock

    @staticmethod
    def patch_auth_url(monkeypatch):
        captured = {}

        def _fake_auth_url(self, state=None, **kwargs):
            captured["state"] = state
            return f"https://provider.test/auth?state={state}"

        monkeypatch.setattr(OAuthHandler, "get_authorization_url", _fake_auth_url)
        return captured


class TestStateHelpers:
    """_state_hmac_key / _build_state direct unit coverage."""

    def test_hmac_key_uses_secret_key(self):
        with patch.dict(os.environ, {"SECRET_KEY": "super-secret"}):
            key = oauth_routes._state_hmac_key()
        assert key == hashlib.sha256(b"super-secret").digest()

    def test_hmac_key_falls_back(self, monkeypatch):
        monkeypatch.delenv("SECRET_KEY", raising=False)
        key = oauth_routes._state_hmac_key()
        assert key == hashlib.sha256(b"atom-oauth-state-fallback").digest()

    def test_build_state_format(self):
        state = oauth_routes._build_state("google", "user-1")
        parts = state.split(":")
        assert len(parts) == 6
        assert parts[0] == "oauth_v1"
        assert parts[1] == "google"
        assert parts[2] == "user-1"
        assert parts[3]  # nonce
        assert int(parts[4]) == int(_time.time()) + 600
        assert len(parts[5]) == 64  # sha256 hexdigest

    def test_build_state_unique_nonce_per_call(self):
        s1 = oauth_routes._build_state("google", "user-1")
        s2 = oauth_routes._build_state("google", "user-1")
        assert s1 != s2

    def test_build_state_binds_user_and_provider(self):
        a = oauth_routes._build_state("google", "user-1")
        b = oauth_routes._build_state("linkedin", "user-1")
        c = oauth_routes._build_state("google", "user-2")
        assert a != b != c


class TestValidateState:
    def test_none_rejected(self):
        assert oauth_routes._validate_state(None, "google", "user-1") is False

    def test_empty_rejected(self):
        assert oauth_routes._validate_state("", "google", "user-1") is False

    def test_wrong_part_count_rejected(self):
        assert oauth_routes._validate_state("a:b:c", "google", "user-1") is False

    def test_wrong_prefix_rejected(self):
        state = "oauth_v2:google:user-1:nonce:1234567890:sig"
        assert oauth_routes._validate_state(state, "google", "user-1") is False

    def test_provider_mismatch_rejected(self):
        state = oauth_routes._build_state("google", "user-1")
        assert oauth_routes._validate_state(state, "linkedin", "user-1") is False

    def test_user_mismatch_rejected(self):
        state = oauth_routes._build_state("google", "user-1")
        assert oauth_routes._validate_state(state, "google", "user-2") is False

    def test_expired_rejected(self):
        with patch("time.time", return_value=1_700_000_000):
            state = oauth_routes._build_state("google", "user-1")
        assert oauth_routes._validate_state(state, "google", "user-1") is False

    def test_non_numeric_expiry_rejected(self):
        state = "oauth_v1:google:user-1:nonce:not-a-number:sig"
        assert oauth_routes._validate_state(state, "google", "user-1") is False

    def test_tampered_signature_rejected(self):
        state = oauth_routes._build_state("google", "user-1")
        parts = state.split(":")
        parts[5] = "0" * 64
        assert oauth_routes._validate_state(":".join(parts), "google", "user-1") is False

    def test_valid_state_accepted(self):
        state = oauth_routes._build_state("google", "user-1")
        assert oauth_routes._validate_state(state, "google", "user-1") is True


class TestOauthRateLimit:
    def test_rate_limit_allows(self):
        limiter = MagicMock()
        limiter.check.return_value = (True, 19)
        with patch.object(oauth_routes, "_oauth_limiter", limiter):
            oauth_routes.oauth_rate_limit(MagicMock())  # must not raise

    def test_rate_limit_blocked_raises_429(self):
        limiter = MagicMock()
        limiter.check.return_value = (False, 0)
        with patch.object(oauth_routes, "_oauth_limiter", limiter):
            with pytest.raises(HTTPException) as exc:
                oauth_routes.oauth_rate_limit(MagicMock())
        assert exc.value.status_code == 429


class TestHandleCallbackLogic:
    """Direct async coverage of _handle_callback_logic branches."""

    async def _run(self, monkeypatch, db, token_data=None, side_effect=None,
                   user=None):
        _OAuthApp.patch_exchange(monkeypatch, token_data, side_effect)
        monkeypatch.setattr(
            oauth_routes, "get_current_user",
            AsyncMock(return_value=user if user is not None else FAKE_USER),
        )
        return await oauth_routes._handle_callback_logic(
            "google", "code-1", MagicMock(), MagicMock(), db
        )

    def _existing(self, **kw):
        base = dict(
            access_token_hash="old-hash",
            refresh_token_hash="old-rt",
            scope="old",
            access_token_expires_at=None,
            is_active=False,
        )
        base.update(kw)
        return SimpleNamespace(**base)

    async def test_existing_token_updated(self, monkeypatch):
        db = MagicMock()
        existing = self._existing()
        db.query.return_value.filter.return_value.first.return_value = existing
        result = await self._run(
            monkeypatch,
            db,
            token_data={
                "access_token": "at-new",
                "refresh_token": "rt-new",
                "scope": "read,write",
                "expires_in": 60,
            },
        )
        assert result["access_token"] == "at-new"
        assert existing.access_token_hash == hashlib.sha256(b"at-new").hexdigest()
        assert existing.refresh_token_hash == hashlib.sha256(b"rt-new").hexdigest()
        assert existing.scope == "read write"
        assert existing.access_token_expires_at is not None
        assert existing.is_active is True
        db.commit.assert_called_once()

    async def test_existing_token_without_refresh_keeps_hash(self, monkeypatch):
        db = MagicMock()
        existing = self._existing()
        db.query.return_value.filter.return_value.first.return_value = existing
        await self._run(
            monkeypatch,
            db,
            token_data={"access_token": "at-2", "scope": "read"},
        )
        assert existing.refresh_token_hash == "old-rt"
        assert existing.scope == "read"

    async def test_new_token_created(self, monkeypatch):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        await self._run(
            monkeypatch,
            db,
            token_data={
                "access_token": "at-3",
                "refresh_token": "rt-3",
                "scope": "a,b",
                "expires_in": 120,
            },
        )
        db.commit.assert_called_once()
        added = db.add.call_args[0][0]
        from core.models import OAuthToken

        assert isinstance(added, OAuthToken)
        assert added.client_id == "google_client"
        assert added.tenant_id == "t1"
        assert added.user_id == "user-1"
        assert added.access_token_hash == hashlib.sha256(b"at-3").hexdigest()
        assert added.refresh_token_hash == hashlib.sha256(b"rt-3").hexdigest()
        assert added.scope == "a b"
        assert added.access_token_expires_at is not None
        assert added.is_active is True

    async def test_new_token_tenant_falls_back_to_default(self, monkeypatch):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        await self._run(
            monkeypatch,
            db,
            token_data={"access_token": "at-4"},
            user=SimpleNamespace(id="u2", tenant_id=None),
        )
        added = db.add.call_args[0][0]
        assert added.tenant_id == "default"

    async def test_new_token_no_expiry(self, monkeypatch):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        await self._run(
            monkeypatch, db, token_data={"access_token": "at-5", "scope": "r"}
        )
        added = db.add.call_args[0][0]
        assert added.access_token_expires_at is None

    async def test_list_scope_ignored(self, monkeypatch):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        await self._run(
            monkeypatch,
            db,
            token_data={"access_token": "at-6", "scope": ["a", "b"]},
        )
        added = db.add.call_args[0][0]
        assert added.scope == ""

    async def test_exchange_failure_maps_to_500(self, monkeypatch):
        db = MagicMock()
        with pytest.raises(HTTPException) as exc:
            await self._run(
                monkeypatch, db, side_effect=RuntimeError("provider boom")
            )
        assert exc.value.status_code == 500
        assert "google" in exc.value.detail


class TestOauthInitiate:
    def test_initiate_redirects_with_signed_state(self, monkeypatch):
        captured = _OAuthApp.patch_auth_url(monkeypatch)
        client = _OAuthApp.client(monkeypatch)
        resp = client.get(
            "/api/v1/auth/oauth/google/initiate", follow_redirects=False
        )
        assert resp.status_code in (302, 307)
        state = captured["state"]
        assert oauth_routes._validate_state(state, "google", "user-1") is True
        assert "google" in resp.headers["location"]

    def test_initiate_requires_auth(self, monkeypatch):
        client = _OAuthApp.client(monkeypatch, override_auth=False, patch_body_user=False)
        resp = client.get("/api/v1/auth/oauth/google/initiate", follow_redirects=False)
        assert resp.status_code == 401

    def test_initiate_unknown_provider_400(self, monkeypatch):
        client = _OAuthApp.client(monkeypatch)
        resp = client.get("/api/v1/auth/oauth/bogus/initiate", follow_redirects=False)
        assert resp.status_code == 400


class TestOauthCallback:
    def _valid_state(self):
        return oauth_routes._build_state("google", "user-1")

    def test_callback_missing_state_400(self, monkeypatch):
        _OAuthApp.patch_exchange(monkeypatch)
        client = _OAuthApp.client(monkeypatch)
        resp = client.get(
            "/api/v1/auth/oauth/google/callback?code=code-1", follow_redirects=False
        )
        assert resp.status_code == 400

    def test_callback_unsupported_provider_400(self, monkeypatch):
        _OAuthApp.patch_exchange(monkeypatch)
        client = _OAuthApp.client(monkeypatch)
        resp = client.get(
            "/api/v1/auth/oauth/zoom/callback?code=c&state=s", follow_redirects=False
        )
        assert resp.status_code == 400

    def test_callback_success_uses_frontend_url_env(self, monkeypatch):
        _OAuthApp.patch_exchange(monkeypatch)
        client = _OAuthApp.client(monkeypatch)
        with patch.dict(os.environ, {"FRONTEND_URL": "https://app.test"}):
            resp = client.get(
                f"/api/v1/auth/oauth/google/callback?code=c&state={self._valid_state()}",
                follow_redirects=False,
            )
        assert resp.status_code in (302, 307)
        assert resp.headers["location"] == "https://app.test/oauth/success?provider=google"

    def test_callback_success_default_frontend_url(self, monkeypatch):
        _OAuthApp.patch_exchange(monkeypatch)
        client = _OAuthApp.client(monkeypatch)
        resp = client.get(
            f"/api/v1/auth/oauth/google/callback?code=c&state={self._valid_state()}",
            follow_redirects=False,
        )
        assert resp.status_code in (302, 307)
        assert resp.headers["location"] == "http://localhost:3000/oauth/success?provider=google"

    def test_callback_handler_failure_500(self, monkeypatch):
        _OAuthApp.patch_exchange(monkeypatch, side_effect=RuntimeError("boom"))
        client = _OAuthApp.client(monkeypatch)
        resp = client.get(
            f"/api/v1/auth/oauth/google/callback?code=c&state={self._valid_state()}",
            follow_redirects=False,
        )
        assert resp.status_code == 500

    def test_callback_rate_limited_429(self, monkeypatch):
        _OAuthApp.patch_exchange(monkeypatch)
        _OAuthApp.fresh_limiter(monkeypatch, allowed=False)
        client = _OAuthApp.client(monkeypatch)
        resp = client.get(
            f"/api/v1/auth/oauth/google/callback?code=c&state={self._valid_state()}",
            follow_redirects=False,
        )
        assert resp.status_code == 429

    def test_callback_requires_auth(self, monkeypatch):
        _OAuthApp.patch_exchange(monkeypatch)
        client = _OAuthApp.client(monkeypatch, override_auth=False, patch_body_user=False)
        resp = client.get(
            "/api/v1/auth/oauth/google/callback?code=c&state=s", follow_redirects=False
        )
        assert resp.status_code == 401


class TestOauthTokens:
    def test_list_tokens_empty(self, monkeypatch):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        client = _OAuthApp.client(monkeypatch, db=db)
        resp = client.get("/api/v1/auth/oauth/tokens")
        assert resp.status_code == 200
        assert resp.json() == {"integrations": []}

    def test_list_tokens_serialization(self, monkeypatch):
        from datetime import datetime, timezone

        db = MagicMock()
        rows = [
            SimpleNamespace(
                client_id="google_client",
                is_active=True,
                access_token_expires_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                last_used_at=None,
                scope="https://graph.microsoft.com/Mail.Send offline_access",
            ),
            SimpleNamespace(
                client_id="custom-store",
                is_active=False,
                access_token_expires_at=None,
                last_used_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
                scope="",
            ),
        ]
        db.query.return_value.filter.return_value.all.return_value = rows
        client = _OAuthApp.client(monkeypatch, db=db)
        resp = client.get("/api/v1/auth/oauth/tokens")
        assert resp.status_code == 200
        integrations = resp.json()["integrations"]
        assert integrations[0]["provider"] == "google"
        assert integrations[0]["status"] == "active"
        assert integrations[0]["expires_at"] == "2026-01-01T00:00:00+00:00"
        assert integrations[0]["last_used"] is None
        assert integrations[0]["scope"] == "https://graph.microsoft.com/Mail.Send offline_access"
        assert integrations[1]["provider"] == "custom-store"
        assert integrations[1]["status"] == "revoked"
        assert integrations[1]["expires_at"] is None
        assert integrations[1]["last_used"] == "2026-02-01T00:00:00+00:00"

    def test_list_tokens_provider_filter(self, monkeypatch):
        db = MagicMock()
        inner = db.query.return_value.filter.return_value
        inner.filter.return_value.all.return_value = []
        client = _OAuthApp.client(monkeypatch, db=db)
        resp = client.get("/api/v1/auth/oauth/tokens?provider=google")
        assert resp.status_code == 200
        assert inner.filter.call_count == 1  # provider branch added a filter

    def test_revoke_token_success(self, monkeypatch):
        db = MagicMock()
        token = SimpleNamespace(is_active=True)
        db.query.return_value.filter.return_value.first.return_value = token
        client = _OAuthApp.client(monkeypatch, db=db)
        resp = client.delete("/api/v1/auth/oauth/tokens/google")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert token.is_active is False
        db.commit.assert_called_once()

    def test_revoke_token_not_found_404(self, monkeypatch):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        client = _OAuthApp.client(monkeypatch, db=db)
        resp = client.delete("/api/v1/auth/oauth/tokens/unknown")
        assert resp.status_code == 404

    def test_tokens_require_auth(self, monkeypatch):
        client = _OAuthApp.client(monkeypatch, override_auth=False, patch_body_user=False)
        resp = client.get("/api/v1/auth/oauth/tokens")
        assert resp.status_code == 401


class TestOauthConfigStatus:
    def test_config_status_reports_all_providers(self, monkeypatch):
        with patch.object(
            oauth_routes.GOOGLE_OAUTH_CONFIG, "is_configured", return_value=True
        ):
            client = _OAuthApp.client(monkeypatch)
            resp = client.get("/api/v1/auth/oauth/config-status")
        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) == {
            "google", "linkedin", "microsoft", "salesforce", "slack",
            "github", "asana", "notion", "trello", "dropbox", "whatsapp",
        }
        assert data["google"] is True
        assert all(isinstance(v, bool) for v in data.values())


# ============================================================================
# api/social_media_routes.py — tail lines (98% -> 100%)
# ============================================================================


class TestSocialMediaTail:
    """Covers the remaining uncovered lines: unimplemented-platform branch
    (600-604) and the HTTPException re-raise paths (749, 785)."""

    @staticmethod
    def _client(db=None):
        from core.security_dependencies import get_current_user as social_user

        app = FastAPI()
        app.include_router(social_media_routes.router)
        app.dependency_overrides[get_db] = lambda: db if db is not None else MagicMock()
        app.dependency_overrides[social_user] = lambda: SimpleNamespace(id="user-1")
        return TestClient(app, raise_server_exceptions=False)

    def _post_db(self, token=None):
        db = MagicMock()
        q = db.query.return_value
        q.filter.return_value.count.return_value = 0
        q.filter.return_value.first.return_value = token if token is not None else MagicMock()
        return db

    def test_post_to_unimplemented_platform(self):
        with patch.dict(
            PlatformConfig.PLATFORMS,
            {
                "instagram": {
                    "name": "Instagram",
                    "max_length": 5000,
                    "supports_media": True,
                    "supports_links": True,
                    "oauth_provider": "instagram",
                },
            },
        ):
            client = self._client(self._post_db())
            resp = client.post(
                "/api/v1/social/post",
                json={"text": "hello world", "platforms": ["instagram"]},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        result = data["platform_results"]["instagram"]
        assert result["success"] is False
        assert "not yet implemented" in result["error"]

    def test_connected_accounts_http_exception_reraised(self):
        db = MagicMock()
        db.query.side_effect = HTTPException(status_code=401, detail="session expired")
        client = self._client(db)
        resp = client.get("/api/v1/social/connected-accounts")
        assert resp.status_code == 401

    def test_rate_limit_status_http_exception_reraised(self):
        db = MagicMock()
        db.query.side_effect = HTTPException(status_code=403, detail="denied")
        client = self._client(db)
        resp = client.get("/api/v1/social/rate-limit")
        assert resp.status_code == 403
