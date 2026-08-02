"""Round 70 — Phase D: subscription-credential reuse.

Tests the extended credential-resolution priority
(oauth -> subscription -> byok -> env) and the ``credential_type`` column on
``LLMOAuthCredential``. See docs/security/LLM_GATEWAY_SUBSCRIPTION_REUSE.md.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm_credential_service import LLMCredentialService
from core.llm_oauth_handler import LLMOAuthHandler
from core.models import LLMOAuthCredential


def _make_service(**kwargs):
    svc = LLMCredentialService(
        user_id=kwargs.get("user_id", "u-1"),
        tenant_id=kwargs.get("tenant_id", "t-1"),
        workspace_id=kwargs.get("workspace_id", "ws-1"),
    )
    svc.oauth_handler = MagicMock()
    svc.byok_manager = MagicMock()
    # Real BYOKManager returns None when no tenant-level key is set.
    svc.byok_manager.get_tenant_api_key.return_value = None
    svc.byok_manager.get_api_key.return_value = None
    return svc


def _cred(access="tok"):
    c = MagicMock(spec=LLMOAuthCredential)
    c.access_token = access
    return c


def _handler_side_effect(oauth=None, subscription=None):
    """Return a get_active_credentials side effect that dispatches on type."""

    def _side(user_id, provider_id, credential_type=None):
        if credential_type == "oauth":
            return oauth
        if credential_type == "subscription":
            return subscription
        return oauth or subscription

    return _side


class TestGetCredentialPriority:
    @pytest.mark.asyncio
    async def test_oauth_wins_over_subscription(self):
        svc = _make_service()
        svc.oauth_handler.get_active_credentials.side_effect = _handler_side_effect(
            oauth=_cred(), subscription=_cred()
        )
        svc.oauth_handler.validate_and_refresh_if_needed = AsyncMock(return_value=True)
        svc.oauth_handler.decrypt_access_token.return_value = "oauth-token"

        ctype, token = await svc.get_credential("openai")

        assert ctype == "oauth"
        assert token == "oauth-token"

    @pytest.mark.asyncio
    async def test_subscription_used_when_no_oauth(self):
        svc = _make_service()
        svc.oauth_handler.get_active_credentials.side_effect = _handler_side_effect(
            oauth=None, subscription=_cred()
        )
        svc.oauth_handler.validate_and_refresh_if_needed = AsyncMock(return_value=True)
        svc.oauth_handler.decrypt_access_token.return_value = "sub-token"

        ctype, token = await svc.get_credential("openai")

        assert ctype == "subscription"
        assert token == "sub-token"

    @pytest.mark.asyncio
    async def test_subscription_wins_over_byok_and_env(self):
        svc = _make_service()
        svc.oauth_handler.get_active_credentials.side_effect = _handler_side_effect(
            oauth=None, subscription=_cred()
        )
        svc.oauth_handler.validate_and_refresh_if_needed = AsyncMock(return_value=True)
        svc.oauth_handler.decrypt_access_token.return_value = "sub-token"
        svc.byok_manager.is_configured.return_value = True
        svc.byok_manager.get_api_key.return_value = "byok-key"

        with patch.dict("os.environ", {"OPENAI_API_KEY": "env-key"}):
            ctype, token = await svc.get_credential("openai")

        assert ctype == "subscription"
        assert token == "sub-token"

    @pytest.mark.asyncio
    async def test_byok_used_when_no_oauth_or_subscription(self):
        svc = _make_service()
        svc.oauth_handler.get_active_credentials.return_value = None
        svc.byok_manager.is_configured.return_value = True
        svc.byok_manager.get_api_key.return_value = "byok-key"

        ctype, token = await svc.get_credential("openai")

        assert ctype == "byok"
        assert token == "byok-key"

    @pytest.mark.asyncio
    async def test_env_used_as_last_resort(self):
        svc = _make_service()
        svc.oauth_handler.get_active_credentials.return_value = None
        svc.byok_manager.is_configured.return_value = False

        with patch.dict("os.environ", {"OPENAI_API_KEY": "env-key"}):
            ctype, token = await svc.get_credential("openai")

        assert ctype == "env"
        assert token == "env-key"

    @pytest.mark.asyncio
    async def test_service_requests_oauth_then_subscription_types(self):
        """The service must pass credential_type filters to the handler."""
        svc = _make_service()
        svc.oauth_handler.get_active_credentials.return_value = None
        svc.byok_manager.is_configured.return_value = False

        with patch.dict("os.environ", {"OPENAI_API_KEY": "env-key"}):
            await svc.get_credential("openai")

        types = [
            c.kwargs.get("credential_type")
            for c in svc.oauth_handler.get_active_credentials.call_args_list
        ]
        assert types == ["oauth", "subscription"]


class TestProviderStatus:
    def test_reports_subscription(self):
        svc = _make_service()
        svc.oauth_handler.get_active_credentials.side_effect = _handler_side_effect(
            oauth=None, subscription=_cred()
        )
        svc.byok_manager.is_configured.return_value = False

        status = svc.get_provider_status("openai")

        assert status["has_subscription"] is True
        assert status["has_oauth"] is False
        assert status["active_method"] == "subscription"

    def test_oauth_still_preferred_in_status(self):
        svc = _make_service()
        svc.oauth_handler.get_active_credentials.side_effect = _handler_side_effect(
            oauth=_cred(), subscription=_cred()
        )
        status = svc.get_provider_status("openai")

        assert status["has_oauth"] is True
        assert status["has_subscription"] is True
        assert status["active_method"] == "oauth"


class TestStoreCredentialType:
    def test_store_defaults_to_oauth(self):
        with patch("core.llm_oauth_handler.get_db_session") as mock_db_ctx:
            db = MagicMock()
            mock_db_ctx.return_value.__enter__.return_value = db
            db.query.return_value.filter.return_value.first.return_value = None

            handler = LLMOAuthHandler()
            cred = handler.store_oauth_credentials(
                user_id="u-1",
                tenant_id="t-1",
                provider_id="openai",
                tokens={"access_token": "at", "token_type": "Bearer"},
            )

            stored = db.add.call_args[0][0]
            assert isinstance(stored, LLMOAuthCredential)
            assert stored.credential_type == "oauth"

    def test_store_subscription_type(self):
        with patch("core.llm_oauth_handler.get_db_session") as mock_db_ctx:
            db = MagicMock()
            mock_db_ctx.return_value.__enter__.return_value = db
            db.query.return_value.filter.return_value.first.return_value = None

            handler = LLMOAuthHandler()
            handler.store_oauth_credentials(
                user_id="u-1",
                tenant_id="t-1",
                provider_id="openai",
                tokens={"access_token": "at", "token_type": "Bearer"},
                credential_type="subscription",
            )

            stored = db.add.call_args[0][0]
            assert stored.credential_type == "subscription"
