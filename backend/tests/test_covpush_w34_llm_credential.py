"""Coverage wave 34 — core/llm_credential_service.py (64% → 90%+).

Drives every remaining fallback-chain branch with a mocked oauth_handler /
byok_manager and patched env: ValueError-no-credential, invalid-token path,
oauth exception tolerance, tenant-level BYOK, gemini GOOGLE_API_KEY fallback,
env exception, credential-info/list/revoke/refresh error paths, and the full
provider-status matrix (oauth/subscription/byok/env active-method resolution).
"""
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.llm_credential_service import LLMCredentialService


def _credential(**kw):
    base = dict(
        id="cred-1", provider_id="openai", account_email="a@b.c",
        account_name="A B", is_active=True, expires_at=None,
        last_used_at=None, usage_count=3, created_at=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def svc():
    s = LLMCredentialService(user_id="u1", tenant_id="t1", workspace_id="w1")
    s.oauth_handler = Mock()
    s.byok_manager = Mock()
    s.byok_manager.get_tenant_api_key.return_value = None
    s.byok_manager.get_api_key.return_value = None
    return s


def await_coroutine(coro):
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestGetCredentialFallbackChain:
    def test_no_credential_raises_value_error(self, svc):
        svc.oauth_handler.get_active_credentials.return_value = None
        svc.byok_manager.is_configured.return_value = False
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="No credential available"):
                await_coroutine(svc.get_credential("openai"))

    def test_oauth_priority_over_subscription(self, svc):
        svc.oauth_handler.get_active_credentials.side_effect = [
            _credential(),  # oauth
            None,
        ]
        svc.oauth_handler.validate_and_refresh_if_needed = AsyncMock(return_value=True)
        svc.oauth_handler.decrypt_access_token.return_value = "oauth-tok"
        kind, token = await_coroutine(svc.get_credential("openai"))
        assert (kind, token) == ("oauth", "oauth-tok")

    def test_subscription_second_priority(self, svc):
        svc.oauth_handler.get_active_credentials.side_effect = [
            None,             # oauth
            _credential(),    # subscription
        ]
        svc.oauth_handler.validate_and_refresh_if_needed = AsyncMock(return_value=True)
        svc.oauth_handler.decrypt_access_token.return_value = "sub-tok"
        kind, token = await_coroutine(svc.get_credential("openai"))
        assert (kind, token) == ("subscription", "sub-tok")

    def test_byok_third_priority_tenant_level(self, svc):
        svc.oauth_handler.get_active_credentials.return_value = None
        svc.byok_manager.get_tenant_api_key.return_value = "tenant-key"
        kind, token = await_coroutine(svc.get_credential("openai"))
        assert (kind, token) == ("byok", "tenant-key")

    def test_byok_workspace_level(self, svc):
        svc.oauth_handler.get_active_credentials.return_value = None
        svc.byok_manager.get_tenant_api_key.return_value = None
        svc.byok_manager.is_configured.return_value = True
        svc.byok_manager.get_api_key.return_value = "ws-key"
        kind, token = await_coroutine(svc.get_credential("openai"))
        assert (kind, token) == ("byok", "ws-key")

    def test_byok_exception_returns_none(self, svc):
        svc.oauth_handler.get_active_credentials.return_value = None
        svc.byok_manager.is_configured.side_effect = RuntimeError("boom")
        assert svc._try_byok_credential("openai") is None

    def test_env_fourth_priority(self, svc):
        svc.oauth_handler.get_active_credentials.return_value = None
        svc.byok_manager.is_configured.return_value = False
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}, clear=True):
            kind, token = await_coroutine(svc.get_credential("openai"))
        assert (kind, token) == ("env", "env-key")

    def test_gemini_uses_google_api_key(self, svc):
        svc.oauth_handler.get_active_credentials.return_value = None
        svc.byok_manager.is_configured.return_value = False
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "g-key"}, clear=True):
            kind, token = await_coroutine(svc.get_credential("gemini"))
        assert (kind, token) == ("env", "g-key")

    def test_env_exception_returns_none(self, svc):
        with patch("core.llm_credential_service.os.getenv",
                   side_effect=RuntimeError("boom")):
            assert svc._try_env_credential("openai") is None


class TestResolveActiveCredential:
    def test_no_user_id_returns_none(self, svc):
        svc.user_id = None
        assert await_coroutine(svc._resolve_active_credential("openai", "oauth")) is None

    def test_no_credential_returns_none(self, svc):
        svc.oauth_handler.get_active_credentials.return_value = None
        assert await_coroutine(svc._resolve_active_credential("openai", "oauth")) is None

    def test_invalid_credential_returns_none(self, svc):
        svc.oauth_handler.get_active_credentials.return_value = _credential()
        svc.oauth_handler.validate_and_refresh_if_needed = AsyncMock(return_value=False)
        assert await_coroutine(svc._resolve_active_credential("openai", "oauth")) is None

    def test_exception_returns_none(self, svc):
        svc.oauth_handler.get_active_credentials.side_effect = RuntimeError("boom")
        assert await_coroutine(svc._resolve_active_credential("openai", "oauth")) is None


class TestCredentialInfoAndManagement:
    def test_get_oauth_info_no_user(self, svc):
        svc.user_id = None
        assert await_coroutine(svc.get_oauth_credential_info("openai")) is None

    def test_get_oauth_info_no_credential(self, svc):
        svc.oauth_handler.get_active_credentials.return_value = None
        assert await_coroutine(svc.get_oauth_credential_info("openai")) is None

    def test_get_oauth_info_full(self, svc):
        from datetime import datetime, timezone
        cred = _credential(
            expires_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            last_used_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        svc.oauth_handler.get_active_credentials.return_value = cred
        info = await_coroutine(svc.get_oauth_credential_info("openai"))
        assert info["credential_id"] == "cred-1"
        assert info["expires_at"] == "2026-09-01T00:00:00+00:00"
        assert info["usage_count"] == 3

    def test_get_oauth_info_exception(self, svc):
        svc.oauth_handler.get_active_credentials.side_effect = RuntimeError("boom")
        assert await_coroutine(svc.get_oauth_credential_info("openai")) is None

    def test_list_credentials_no_user(self, svc):
        svc.user_id = None
        assert svc.list_oauth_credentials() == []

    def test_list_credentials_full(self, svc):
        svc.oauth_handler.list_credentials.return_value = [
            _credential(), _credential(id="cred-2")]
        creds = svc.list_oauth_credentials()
        assert [c["credential_id"] for c in creds] == ["cred-1", "cred-2"]

    def test_list_credentials_exception(self, svc):
        svc.oauth_handler.list_credentials.side_effect = RuntimeError("boom")
        assert svc.list_oauth_credentials() == []

    def test_revoke_success_and_exception(self, svc):
        svc.oauth_handler.revoke_credentials.return_value = True
        assert svc.revoke_oauth_credential("cred-1") is True
        svc.oauth_handler.revoke_credentials.side_effect = RuntimeError("boom")
        assert svc.revoke_oauth_credential("cred-1") is False

    def test_refresh_success_and_exception(self, svc):
        svc.oauth_handler.refresh_access_token = AsyncMock(return_value=True)
        assert await_coroutine(svc.refresh_oauth_credential("cred-1")) is True
        svc.oauth_handler.refresh_access_token = AsyncMock(side_effect=RuntimeError("boom"))
        assert await_coroutine(svc.refresh_oauth_credential("cred-1")) is False


class TestProviderStatus:
    def test_all_present_active_method_oauth(self, svc):
        svc.oauth_handler.get_active_credentials.return_value = _credential()
        svc.byok_manager.is_configured.return_value = True
        with patch.dict(os.environ, {"OPENAI_API_KEY": "k"}, clear=True):
            status = svc.get_provider_status("openai")
        assert status["has_oauth"] and status["has_byok"] and status["has_env"]
        assert status["active_method"] == "oauth"
        assert status["oauth_info"]["account_email"] == "a@b.c"

    def test_subscription_only(self, svc):
        svc.oauth_handler.get_active_credentials.side_effect = [None, _credential()]
        svc.byok_manager.is_configured.return_value = False
        with patch.dict(os.environ, {}, clear=True):
            status = svc.get_provider_status("openai")
        assert status["has_subscription"] and not status["has_oauth"]
        assert status["active_method"] == "subscription"
        assert status["subscription_info"]["account_email"] == "a@b.c"

    def test_byok_only_active_method(self, svc):
        svc.oauth_handler.get_active_credentials.return_value = None
        svc.byok_manager.is_configured.return_value = True
        with patch.dict(os.environ, {}, clear=True):
            status = svc.get_provider_status("openai")
        assert status["has_byok"] and status["active_method"] == "byok"

    def test_env_only_active_method(self, svc):
        svc.oauth_handler.get_active_credentials.return_value = None
        svc.byok_manager.is_configured.return_value = False
        with patch.dict(os.environ, {"OPENAI_API_KEY": "k"}, clear=True):
            status = svc.get_provider_status("openai")
        assert status["has_env"] and status["active_method"] == "env"

    def test_nothing_configured(self, svc):
        svc.oauth_handler.get_active_credentials.return_value = None
        svc.byok_manager.is_configured.return_value = False
        with patch.dict(os.environ, {}, clear=True):
            status = svc.get_provider_status("openai")
        assert status["active_method"] is None
        assert not any(status[k] for k in ("has_oauth", "has_subscription", "has_byok", "has_env"))

    def test_oauth_check_exception_tolerated(self, svc):
        svc.oauth_handler.get_active_credentials.side_effect = RuntimeError("boom")
        svc.byok_manager.is_configured.return_value = False
        with patch.dict(os.environ, {}, clear=True):
            status = svc.get_provider_status("openai")
        assert status["has_oauth"] is False

    def test_byok_check_exception_tolerated(self, svc):
        svc.oauth_handler.get_active_credentials.return_value = None
        svc.byok_manager.is_configured.side_effect = RuntimeError("boom")
        with patch.dict(os.environ, {}, clear=True):
            status = svc.get_provider_status("openai")
        assert status["has_byok"] is False
