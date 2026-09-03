"""
Security bug-hunt 2026-08-09 (wave-3): OAuth + admin + webhook surfaces.

Covers:
1. teams_enhanced_service.py:512 — MS access token decoded with
   verify_signature=False (JWKS verification fix).
2. api/oauth_routes.py — static predictable OAuth state (forgery → token
   binding attack); signed per-user state fix.
3. api/routes/webhooks/ingestion_webhooks.py — Gmail Pub/Sub push webhook
   processed with NO verification at all (fail-closed token gate fix).
4. api/admin/* + api/admin_routes.py — member-role → 403 matrix on every
   admin endpoint (verification; expected green).
5. api/llm_oauth_routes.py — verify-only: signed state, provider allowlist.
"""
from __future__ import annotations

import base64
import json
import os
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import oauth_routes
from api.routes.webhooks import ingestion_webhooks as iw
from core.auth import get_current_user
from core.database import get_db
from core.oauth_handler import OAuthHandler


# ============================================================================
# Shared helpers
# ============================================================================

def _b64url_int(n: int) -> str:
    return base64.urlsafe_b64encode(
        n.to_bytes((n.bit_length() + 7) // 8, "big")
    ).rstrip(b"=").decode()


def _rsa_jwk(kid: str):
    """Generate an RSA key pair + a JWKS-style JWK dict for it."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nums = key.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "kid": kid,
        "use": "sig",
        "alg": "RS256",
        "n": _b64url_int(nums.n),
        "e": _b64url_int(nums.e),
    }
    return key, jwk


def _ms_token(key, kid: str, **overrides) -> str:
    """Mint a Microsoft-style RS256 access token."""
    payload = {
        "tid": "tenant-1",
        "oid": "obj-1",
        "name": "Test Team",
        "upn": "t@example.com",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    payload.update(overrides)
    return pyjwt.encode(payload, key, algorithm="RS256", headers={"kid": kid})


def _fake_user(user_id="user-1", role="member"):
    return SimpleNamespace(
        id=user_id, role=role, tenant_id="t1", workspace_id="default"
    )


def _make_app(router, user=None, db=None):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db if db is not None else MagicMock()
    app.dependency_overrides[get_current_user] = (
        lambda: user if user is not None else _fake_user()
    )
    return app


# ============================================================================
# 1. teams_enhanced_service — MS access token signature verification
# ============================================================================

class TestTeamsJwksVerification:
    """teams_enhanced_service.exchange_code_for_tokens decodes the MS token
    with verify_signature=False; a forged token must be rejected via JWKS."""

    def _svc(self, monkeypatch):
        from integrations.teams_enhanced_service import TeamsEnhancedService

        svc = TeamsEnhancedService(tenant_id="t", config={"client_id": "cid"})
        svc.msal_app = MagicMock()
        svc._save_workspace = MagicMock(return_value=True)
        return svc

    async def test_forged_token_with_unknown_kid_rejected(self, monkeypatch):
        key, real_jwk = _rsa_jwk("real-kid")
        forged_key, _ = _rsa_jwk("forged-kid")
        svc = self._svc(monkeypatch)
        monkeypatch.setattr(svc, "_get_jwks_keys", lambda tenant: [real_jwk])
        svc.msal_app.acquire_token_by_authorization_code.return_value = {
            "access_token": _ms_token(forged_key, "forged-kid"),
            "refresh_token": "rt",
        }
        result = await svc.exchange_code_for_tokens("code", "state")
        assert result["ok"] is False

    async def test_forged_token_same_kid_wrong_signature_rejected(self, monkeypatch):
        jwks_key, jwk = _rsa_jwk("kid-1")
        attacker_key, _ = _rsa_jwk("kid-1")
        svc = self._svc(monkeypatch)
        monkeypatch.setattr(svc, "_get_jwks_keys", lambda tenant: [jwk])
        svc.msal_app.acquire_token_by_authorization_code.return_value = {
            "access_token": _ms_token(attacker_key, "kid-1"),
            "refresh_token": "rt",
        }
        result = await svc.exchange_code_for_tokens("code", "state")
        assert result["ok"] is False

    async def test_expired_token_rejected(self, monkeypatch):
        key, jwk = _rsa_jwk("kid-1")
        svc = self._svc(monkeypatch)
        monkeypatch.setattr(svc, "_get_jwks_keys", lambda tenant: [jwk])
        svc.msal_app.acquire_token_by_authorization_code.return_value = {
            "access_token": _ms_token(
                key, "kid-1", exp=int(time.time()) - 3600, iat=int(time.time()) - 7200
            ),
            "refresh_token": "rt",
        }
        result = await svc.exchange_code_for_tokens("code", "state")
        assert result["ok"] is False

    async def test_validly_signed_token_accepted(self, monkeypatch):
        key, jwk = _rsa_jwk("kid-1")
        svc = self._svc(monkeypatch)
        monkeypatch.setattr(svc, "_get_jwks_keys", lambda tenant: [jwk])
        svc.msal_app.acquire_token_by_authorization_code.return_value = {
            "access_token": _ms_token(key, "kid-1"),
            "refresh_token": "rt",
        }
        result = await svc.exchange_code_for_tokens("code", "state")
        assert result["ok"] is True
        workspace = svc._save_workspace.call_args[0][0]
        assert workspace.team_id == "tenant-1"
        assert workspace.name == "Test Team"

    async def test_jwks_fetch_failure_fails_closed(self, monkeypatch):
        key, jwk = _rsa_jwk("kid-1")
        svc = self._svc(monkeypatch)
        monkeypatch.setattr(svc, "_get_jwks_keys", lambda tenant: None)
        svc.msal_app.acquire_token_by_authorization_code.return_value = {
            "access_token": _ms_token(key, "kid-1"),
            "refresh_token": "rt",
        }
        result = await svc.exchange_code_for_tokens("code", "state")
        assert result["ok"] is False


# ============================================================================
# 2. api/oauth_routes.py — state CSRF
# ============================================================================

class TestOauthRoutesStateCsrf:
    """The callback previously accepted the static, predictable state value
    ``{provider}_oauth`` — an attacker who completes their own OAuth flow can
    forge the state and bind THEIR provider tokens to the victim's account
    (OAuth CSRF / token-binding). State must be signed + per-user."""

    _TOKENS = {
        "access_token": "at-1",
        "refresh_token": "rt-1",
        "token_type": "Bearer",
        "scope": "read",
        "expires_in": 3600,
    }

    def _client(self, monkeypatch, user=None):
        app = FastAPI()
        app.include_router(oauth_routes.router)
        app.dependency_overrides[get_db] = lambda: MagicMock()
        app.dependency_overrides[oauth_routes.get_current_user] = (
            lambda: user if user is not None else _fake_user()
        )
        monkeypatch.setattr(
            oauth_routes, "get_current_user", AsyncMock(return_value=_fake_user())
        )
        monkeypatch.setattr(
            OAuthHandler, "exchange_code_for_tokens",
            AsyncMock(return_value=dict(self._TOKENS)),
        )
        return TestClient(app, raise_server_exceptions=False)

    def test_static_predictable_state_rejected(self, monkeypatch):
        """Attacker submits the well-known static state for a victim's callback.

        Expects 401 (invalid state signature) since the signed-state redesign
        rejects any non-``oauth_v1`` state via ``_get_user_id_from_state``."""
        client = self._client(monkeypatch)
        resp = client.get(
            "/api/v1/auth/oauth/google/callback?code=attacker_code&state=google_oauth",
            follow_redirects=False,
        )
        assert resp.status_code in (400, 401)

    def test_tampered_state_signature_rejected(self, monkeypatch):
        """State with a forged/truncated signature is rejected (401), not
        accepted — the HMAC binding must never pass on tampered input."""
        client = self._client(monkeypatch)
        resp = client.get(
            "/api/v1/auth/oauth/google/callback?code=c&state=google_oauth%3Auser-1%3Anonce%3Asig%3Aextra",
            follow_redirects=False,
        )
        assert resp.status_code in (400, 401)

    def test_signed_state_round_trip_accepted(self, monkeypatch):
        """Initiate mints a signed state; the same state on callback is accepted."""
        client = self._client(monkeypatch)

        def _fake_auth_url(state=None, **kwargs):
            return f"https://provider.test/auth?state={state}"

        # R88: initiate resolves the user via a LOCAL `from core.auth import
        # get_current_user` — patching the source module is the only hook.
        with patch("core.auth.get_current_user", new=AsyncMock(return_value=_fake_user())), \
             patch.object(
            OAuthHandler, "get_authorization_url", side_effect=_fake_auth_url
        ):
            resp = client.get(
                "/api/v1/auth/oauth/google/initiate", follow_redirects=False
            )
        assert resp.status_code in (302, 307)
        state = parse_qs(urlparse(resp.headers["location"]).query)["state"][0]
        assert state != "google_oauth"

        resp = client.get(
            f"/api/v1/auth/oauth/google/callback?code=real_code&state={state}",
            follow_redirects=False,
        )
        assert resp.status_code in (302, 307)
        assert "oauth/success" in resp.headers["location"]

    def test_state_bound_to_other_user_rejected(self, monkeypatch):
        """A state minted for user A must not validate for user B (CSRF)."""
        original_get_current_user = oauth_routes.get_current_user
        app = FastAPI()
        app.include_router(oauth_routes.router)
        app.dependency_overrides[get_db] = lambda: MagicMock()
        app.dependency_overrides[original_get_current_user] = lambda: _fake_user("user-a")
        monkeypatch.setattr(
            oauth_routes, "get_current_user", AsyncMock(return_value=_fake_user("user-a"))
        )
        state = oauth_routes._build_state("google", "user-a")
        app.dependency_overrides[original_get_current_user] = lambda: _fake_user("user-b")
        monkeypatch.setattr(
            oauth_routes, "get_current_user", AsyncMock(return_value=_fake_user("user-b"))
        )
        monkeypatch.setattr(
            OAuthHandler, "exchange_code_for_tokens",
            AsyncMock(return_value=dict(self._TOKENS)),
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            f"/api/v1/auth/oauth/google/callback?code=c&state={state}",
            follow_redirects=False,
        )
        assert resp.status_code in (400, 403)

    def test_no_open_redirect_via_redirect_uri_param(self, monkeypatch):
        """Client-supplied redirect_uri must never influence the callback target."""
        client = self._client(monkeypatch)
        state = oauth_routes._build_state("google", "user-1")
        resp = client.get(
            f"/api/v1/auth/oauth/google/callback?code=c&state={state}"
            f"&redirect_uri=https://evil.example/steal",
            follow_redirects=False,
        )
        assert resp.status_code in (302, 307)
        assert "evil.example" not in resp.headers["location"]

    def test_unknown_provider_rejected(self, monkeypatch):
        client = self._client(monkeypatch)
        # R88 fail-closed identity: auth resolves (patched here) BEFORE the
        # provider allowlist, so an unknown provider is a 400, not a 401.
        with patch("core.auth.get_current_user", new=AsyncMock(return_value=_fake_user())):
            resp = client.get(
                "/api/v1/auth/oauth/bogus/initiate", follow_redirects=False
            )
        assert resp.status_code == 400


# ============================================================================
# 3. Gmail Pub/Sub push webhook — fail-closed verification token
# ============================================================================

class TestGmailWebhookFailClosed:
    """/webhooks/gmail/events processed payloads with no verification at all.
    Google Pub/Sub push subscriptions carry a `token` query param — it must
    be checked (fail closed when unset / on mismatch)."""

    def _client(self, db=None):
        app = FastAPI()
        app.include_router(iw.router)
        app.dependency_overrides[get_db] = lambda: db if db is not None else MagicMock()
        return TestClient(app, raise_server_exceptions=False)

    def _discovery(self, tenant_id="tenant-1"):
        service = MagicMock()
        service.get_tenant_id_by_external_id = AsyncMock(return_value=tenant_id)
        return patch.object(iw, "TenantDiscoveryService", return_value=service)

    def _queue(self):
        queue = MagicMock()
        queue.enqueue_ingestion_job = AsyncMock(return_value="job-1")
        return patch.object(iw, "webhook_queue", queue)

    def _payload(self):
        return {"historyId": "h1", "emailAddress": "a@b.c"}

    def test_unconfigured_secret_fails_closed(self, monkeypatch):
        monkeypatch.delenv("GMAIL_WEBHOOK_VERIFY_TOKEN", raising=False)
        with self._discovery(), self._queue():
            resp = self._client().post(
                "/webhooks/gmail/events", json=self._payload()
            )
        assert resp.status_code == 503

    def test_wrong_verification_token_rejected(self, monkeypatch):
        monkeypatch.setenv("GMAIL_WEBHOOK_VERIFY_TOKEN", "real-secret")
        with self._discovery(), self._queue():
            resp = self._client().post(
                "/webhooks/gmail/events?token=attacker-token", json=self._payload()
            )
        assert resp.status_code == 401

    def test_correct_verification_token_enqueues(self, monkeypatch):
        monkeypatch.setenv("GMAIL_WEBHOOK_VERIFY_TOKEN", "real-secret")
        conn = MagicMock()
        conn.id = "conn-1"
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = conn
        with self._discovery(), self._queue() as queue:
            resp = self._client(db).post(
                "/webhooks/gmail/events?token=real-secret", json=self._payload()
            )
        assert resp.status_code == 200
        assert resp.json()["job_id"] == "job-1"
        queue.enqueue_ingestion_job.assert_awaited_once()


# ============================================================================
# 4. Admin surfaces — member → 403 matrix (verification, expected green)
# ============================================================================

class TestAdminMemberForbidden:
    """No admin-only endpoint may be readable by a member-role user."""

    def _run(self, router, path, method="get"):
        app = _make_app(router, user=_fake_user("member-1", role="member"))
        client = TestClient(app, raise_server_exceptions=False)
        resp = getattr(client, method)(path)
        assert resp.status_code == 403, f"{method.upper()} {path} -> {resp.status_code}"

    def test_business_facts_all_endpoints(self):
        from api.admin.business_facts_routes import router

        for method, path in [
            ("get", "/api/admin/governance/facts"),
            ("get", "/api/admin/governance/facts/fact-1"),
            ("post", "/api/admin/governance/facts"),
            ("put", "/api/admin/governance/facts/fact-1"),
            ("delete", "/api/admin/governance/facts/fact-1"),
            ("post", "/api/admin/governance/facts/fact-1/verify-citation"),
            ("post", "/api/admin/governance/facts/upload"),
        ]:
            self._run(router, path, method)

    def test_cache_routes_all_endpoints(self):
        from api.admin.cache_routes import router

        for method, path in [
            ("post", "/api/v1/admin/cache/preseed"),
            ("get", "/api/v1/admin/cache/stats"),
            ("get", "/api/v1/admin/cache/health"),
        ]:
            self._run(router, path, method)

    def test_skill_routes_member_forbidden(self):
        from api.admin.skill_routes import router

        self._run(router, "/api/admin/skills/", "post")

    def test_system_health_member_forbidden(self):
        from api.admin.system_health_routes import router

        self._run(router, "/api/admin/health/api/admin/health")

    def test_admin_routes_all_endpoints(self):
        from api.admin_routes import router

        for method, path in [
            ("get", "/api/admin/users"),
            ("get", "/api/admin/users/admin-1"),
            ("post", "/api/admin/users"),
            ("patch", "/api/admin/users/admin-1"),
            ("delete", "/api/admin/users/admin-1"),
            ("patch", "/api/admin/users/admin-1/last-login"),
            ("get", "/api/admin/roles"),
            ("get", "/api/admin/roles/role-1"),
            ("post", "/api/admin/roles"),
            ("patch", "/api/admin/roles/role-1"),
            ("delete", "/api/admin/roles/role-1"),
            ("get", "/api/admin/websocket/status"),
            ("post", "/api/admin/websocket/reconnect"),
            ("post", "/api/admin/websocket/disable"),
            ("post", "/api/admin/websocket/enable"),
            ("post", "/api/admin/sync/ratings"),
            ("get", "/api/admin/ratings/failed-uploads"),
            ("post", "/api/admin/ratings/failed-uploads/f-1/retry"),
            ("get", "/api/admin/conflicts"),
            ("get", "/api/admin/conflicts/c-1"),
            ("post", "/api/admin/conflicts/c-1/resolve"),
            ("post", "/api/admin/conflicts/bulk-resolve"),
        ]:
            self._run(router, path, method)


# ============================================================================
# 5. llm_oauth_routes — verify-only (signed state, allowlist)
# ============================================================================

class TestLlmOauthVerifyOnly:
    """Verification tests — expected green at HEAD (R70 shipped these)."""

    def _client(self):
        from api.llm_oauth_routes import router

        return TestClient(
            _make_app(router, user=_fake_user("user-1")),
            raise_server_exceptions=False,
        )

    def test_tampered_state_rejected(self):
        client = self._client()
        resp = client.get(
            "/api/v1/llm-oauth/openai/callback?code=c&state=llm:openai:oauth:user-1:nonce:forged"
        )
        assert resp.status_code == 400

    def test_user_mismatch_state_rejected(self):
        from api.llm_oauth_routes import _build_state

        state = _build_state("openai", "oauth", "user-other")
        client = self._client()
        resp = client.get(
            f"/api/v1/llm-oauth/openai/callback?code=c&state={state}"
        )
        assert resp.status_code in (400, 403)

    def test_unknown_provider_connect_rejected(self):
        client = self._client()
        resp = client.get("/api/v1/llm-oauth/bogus/connect")
        assert resp.status_code == 400
