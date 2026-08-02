"""Round 70 — Phase D: LLM OAuth connect flow + subscription-credential reuse.

Tests ``api/llm_oauth_routes.py``: initiate, callback (state-validated,
CSRF-bound to the authenticated user), list, revoke, and per-provider status.
Subscription intent is encoded in the OAuth ``state`` and persists the stored
credential with ``credential_type="subscription"``.
"""
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.database import get_db
from core.models import User

# States are now HMAC-signed (6-part: llm:provider:type:user:nonce:sig) to
# prevent forgery. Build them via the real helper so tests stay in sync with
# the signing scheme. The nonce is random, so states are fresh per test run.
from api.llm_oauth_routes import _build_state


def _state_oauth(user_id="u-1"):
    return _build_state("openai", "oauth", user_id)


def _state_sub(user_id="u-1"):
    return _build_state("openai", "subscription", user_id)


def _client(db=None, user_id="u-1"):
    from api.llm_oauth_routes import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db

    async def fake_current_user():
        u = MagicMock(spec=User)
        u.id = user_id
        u.tenant_id = "t-1"
        return u

    app.dependency_overrides[get_current_user] = fake_current_user
    return TestClient(app, raise_server_exceptions=False)


def _cred(credential_id="cred-1", provider_id="openai"):
    c = MagicMock()
    c.id = credential_id
    c.provider_id = provider_id
    c.credential_type = "oauth"
    c.account_email = "a@b.com"
    c.account_name = "A"
    c.is_active = True
    c.expires_at = None
    c.last_used_at = None
    c.usage_count = 0
    c.created_at = None
    return c


class TestConnect:
    def test_requires_auth(self):
        from api.llm_oauth_routes import router

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: MagicMock()
        client = TestClient(app, raise_server_exceptions=False)

        r = client.get("/api/v1/llm-oauth/openai/connect")
        assert r.status_code == 401

    def test_returns_auth_url(self):
        with patch("api.llm_oauth_routes.LLMOAuthHandler") as handler_cls:
            handler = MagicMock()
            handler.get_authorization_url.return_value = {
                "authorization_url": "https://provider/auth",
                "state": "llm:openai:oauth:u-1",
                "provider_id": "openai",
            }
            handler_cls.return_value = handler

            r = _client().get("/api/v1/llm-oauth/openai/connect")

        assert r.status_code == 200
        body = r.json()
        assert body["authorization_url"] == "https://provider/auth"
        assert body["provider_id"] == "openai"
        # state must carry the credential_type intent
        assert "llm:openai:oauth:" in body["state"]

    def test_subscription_connect_requests_subscription_state(self):
        with patch("api.llm_oauth_routes.LLMOAuthHandler") as handler_cls:
            handler = MagicMock()
            handler.get_authorization_url.return_value = {
                "authorization_url": "https://provider/auth",
                "state": "llm:openai:subscription:u-1",
                "provider_id": "openai",
            }
            handler_cls.return_value = handler

            r = _client().get(
                "/api/v1/llm-oauth/openai/connect", params={"credential_type": "subscription"}
            )

        assert r.status_code == 200
        # State is signed but must still carry the subscription intent.
        assert "subscription" in r.json()["state"]

    def test_unknown_provider_400(self):
        with patch("api.llm_oauth_routes.LLMOAuthHandler") as handler_cls:
            handler = MagicMock()
            handler.get_authorization_url.side_effect = ValueError("Unknown provider: nope")
            handler_cls.return_value = handler

            r = _client().get("/api/v1/llm-oauth/nope/connect")

        assert r.status_code == 400


class TestCallback:
    def test_requires_auth(self):
        from api.llm_oauth_routes import router

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: MagicMock()
        client = TestClient(app, raise_server_exceptions=False)

        r = client.get("/api/v1/llm-oauth/openai/callback", params={"code": "x", "state": _state_oauth()})
        assert r.status_code == 401

    def test_rejects_missing_state(self):
        r = _client().get("/api/v1/llm-oauth/openai/callback", params={"code": "x"})
        assert r.status_code == 400

    def test_rejects_wrong_provider_in_state(self):
        # Build a validly-signed state for anthropic, then send it to the
        # openai callback — provider mismatch must be rejected.
        wrong_state = _build_state("anthropic", "oauth", "u-1")
        r = _client().get(
            "/api/v1/llm-oauth/openai/callback",
            params={"code": "x", "state": wrong_state},
        )
        assert r.status_code == 400

    def test_rejects_state_bound_to_another_user(self):
        # Build a validly-signed state bound to a different user — must 403.
        attacker_state = _build_state("openai", "oauth", "attacker-id")
        r = _client(user_id="u-1").get(
            "/api/v1/llm-oauth/openai/callback",
            params={"code": "x", "state": attacker_state},
        )
        assert r.status_code == 403

    def test_rejects_forged_state(self):
        # An unsigned/forged state (old format without HMAC) must be rejected.
        r = _client().get(
            "/api/v1/llm-oauth/openai/callback",
            params={"code": "x", "state": "llm:openai:oauth:u-1"},
        )
        assert r.status_code == 400

    def test_stores_oauth_credential(self):
        with patch("api.llm_oauth_routes.LLMOAuthHandler") as handler_cls:
            handler = MagicMock()
            handler.exchange_code_for_tokens = AsyncMock(return_value={"access_token": "at"})
            cred = _cred()
            handler.store_oauth_credentials.return_value = cred
            handler_cls.return_value = handler

            r = _client().get(
                "/api/v1/llm-oauth/openai/callback",
                params={"code": "code123", "state": _state_oauth()},
            )

        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["credential_id"] == "cred-1"
        _, kwargs = handler.store_oauth_credentials.call_args
        assert kwargs["provider_id"] == "openai"
        assert kwargs["credential_type"] == "oauth"

    def test_subscription_callback_stores_subscription_type(self):
        with patch("api.llm_oauth_routes.LLMOAuthHandler") as handler_cls:
            handler = MagicMock()
            handler.exchange_code_for_tokens = AsyncMock(return_value={"access_token": "at"})
            cred = _cred()
            handler.store_oauth_credentials.return_value = cred
            handler_cls.return_value = handler

            r = _client().get(
                "/api/v1/llm-oauth/openai/callback",
                params={"code": "code123", "state": _state_sub()},
            )

        assert r.status_code == 200
        _, kwargs = handler.store_oauth_credentials.call_args
        assert kwargs["credential_type"] == "subscription"

    def test_exchange_failure_500(self):
        with patch("api.llm_oauth_routes.LLMOAuthHandler") as handler_cls:
            handler = MagicMock()
            handler.exchange_code_for_tokens = AsyncMock(
                side_effect=RuntimeError("provider down")
            )
            handler_cls.return_value = handler

            r = _client().get(
                "/api/v1/llm-oauth/openai/callback",
                params={"code": "x", "state": _state_oauth()},
            )

        assert r.status_code == 500


class TestManagement:
    def test_list_credentials(self):
        with patch("api.llm_oauth_routes.LLMCredentialService") as svc_cls:
            svc = MagicMock()
            svc.list_oauth_credentials.return_value = [
                {
                    "credential_id": "cred-1",
                    "provider_id": "openai",
                    "credential_type": "subscription",
                }
            ]
            svc_cls.return_value = svc

            r = _client().get("/api/v1/llm-oauth/credentials")

        assert r.status_code == 200
        assert r.json()["data"][0]["provider_id"] == "openai"

    def test_revoke_credential_owner_scoped(self):
        with patch("api.llm_oauth_routes.LLMCredentialService") as svc_cls:
            svc = MagicMock()
            svc.revoke_oauth_credential.return_value = True
            svc_cls.return_value = svc

            r = _client().delete("/api/v1/llm-oauth/credentials/cred-1")

        assert r.status_code == 200
        svc.revoke_oauth_credential.assert_called_once_with("cred-1")

    def test_status_reports_subscription(self):
        with patch("api.llm_oauth_routes.LLMCredentialService") as svc_cls:
            svc = MagicMock()
            svc.get_provider_status.return_value = {
                "provider_id": "openai",
                "has_oauth": False,
                "has_subscription": True,
                "has_byok": False,
                "has_env": False,
                "active_method": "subscription",
            }
            svc_cls.return_value = svc

            r = _client().get("/api/v1/llm-oauth/status")

        assert r.status_code == 200
        statuses = r.json()["statuses"]
        assert statuses["openai"]["active_method"] == "subscription"
