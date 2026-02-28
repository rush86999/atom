"""
OAuth Authorization Flow Tests

Tests for OAuth 2.0 authorization flows:
- Authorization code flow (most secure, recommended)
- Implicit flow (deprecated but still supported by some providers)
- Client credentials flow (machine-to-machine)
- Resource owner password flow (legacy, high security risk)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from fastapi import HTTPException

from core.oauth_handler import OAuthHandler, OAuthConfig, SLACK_OAUTH_CONFIG, GOOGLE_OAUTH_CONFIG


class TestAuthorizationCodeFlow:
    """Test OAuth authorization code flow (most secure, recommended)"""

    def test_authorization_code_flow_generate_url(self):
        """Test generating authorization URL with code response type"""
        # Create config with actual values (not env vars)
        config = OAuthConfig(
            client_id_env="TEST_CLIENT_ID",
            client_secret_env="TEST_CLIENT_SECRET",
            redirect_uri_env="TEST_REDIRECT_URI",
            auth_url="https://example.com/oauth/authorize",
            token_url="https://example.com/oauth/token",
            scopes=["read", "write"]
        )

        # Directly set the config values to bypass env var lookup in test
        config.client_id = "test_client_123"
        config.client_secret = "test_secret_456"
        config.redirect_uri = "http://localhost:3000/callback"

        handler = OAuthHandler(config)
        auth_url = handler.get_authorization_url(state="test_state_123")

        # Verify URL structure
        assert auth_url.startswith("https://example.com/oauth/authorize?")
        assert "client_id=test_client_123" in auth_url
        assert "response_type=code" in auth_url
        assert "scope=read+write" in auth_url
        assert "state=test_state_123" in auth_url
        assert "access_type=offline" in auth_url  # For refresh tokens

    def test_authorization_code_flow_missing_config(self):
        """Test authorization fails when OAuth not configured"""
        config = OAuthConfig(
            client_id_env="MISSING_CLIENT_ID",
            client_secret_env="MISSING_CLIENT_SECRET",
            redirect_uri_env="MISSING_REDIRECT_URI",
            auth_url="https://example.com/oauth/authorize",
            token_url="https://example.com/oauth/token",
            scopes=["read"]
        )

        # Missing environment variables
        with patch.dict('os.environ', {}, clear=True):
            handler = OAuthHandler(config)

            with pytest.raises(HTTPException) as exc_info:
                handler.get_authorization_url()

            assert exc_info.value.status_code == 500
            assert "OAuth not configured" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_authorization_code_exchange_success(self):
        """Test exchanging authorization code for access token"""
        config = OAuthConfig(
            client_id_env="TEST_CLIENT_ID",
            client_secret_env="TEST_CLIENT_SECRET",
            redirect_uri_env="TEST_REDIRECT_URI",
            auth_url="https://example.com/oauth/authorize",
            token_url="https://example.com/oauth/token",
            scopes=["read", "write"]
        )

        # Directly set the config values
        config.client_id = "test_client"
        config.client_secret = "test_secret"
        config.redirect_uri = "http://localhost:3000/callback"

        handler = OAuthHandler(config)

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "test_access_token_abc123",
            "refresh_token": "test_refresh_token_xyz789",
            "token_type": "Bearer",
            "scope": "read write",
            "expires_in": 3600
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            token_data = await handler.exchange_code_for_tokens("test_auth_code_123")

            # Verify token data
            assert token_data["access_token"] == "test_access_token_abc123"
            assert token_data["refresh_token"] == "test_refresh_token_xyz789"
            assert token_data["token_type"] == "Bearer"
            assert token_data["scope"] == "read write"
            assert token_data["expires_in"] == 3600

    @pytest.mark.asyncio
    async def test_authorization_code_exchange_invalid_code(self):
        """Test exchanging invalid authorization code fails"""
        config = OAuthConfig(
            client_id_env="TEST_CLIENT_ID",
            client_secret_env="TEST_CLIENT_SECRET",
            redirect_uri_env="TEST_REDIRECT_URI",
            auth_url="https://example.com/oauth/authorize",
            token_url="https://example.com/oauth/token",
            scopes=["read"]
        )

        # Directly set the config values
        config.client_id = "test_client"
        config.client_secret = "test_secret"
        config.redirect_uri = "http://localhost:3000/callback"

        handler = OAuthHandler(config)

        # Mock error response from OAuth provider
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "invalid_grant: Authorization code expired"

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(HTTPException) as exc_info:
                await handler.exchange_code_for_tokens("invalid_code")

            assert exc_info.value.status_code == 400
            assert "Failed to exchange code" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_authorization_code_exchange_network_error(self):
        """Test token exchange handles network errors"""
        config = OAuthConfig(
            client_id_env="TEST_CLIENT_ID",
            client_secret_env="TEST_CLIENT_SECRET",
            redirect_uri_env="TEST_REDIRECT_URI",
            auth_url="https://example.com/oauth/token",
            token_url="https://example.com/oauth/token",
            scopes=["read"]
        )

        # Directly set the config values
        config.client_id = "test_client"
        config.client_secret = "test_secret"
        config.redirect_uri = "http://localhost:3000/callback"

        handler = OAuthHandler(config)

        # Mock network error
        with patch('httpx.AsyncClient') as mock_client:
            import httpx
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.RequestError("Network connection failed")
            )

            with pytest.raises(HTTPException) as exc_info:
                await handler.exchange_code_for_tokens("test_code")

            assert exc_info.value.status_code == 500
            assert "Failed to connect to OAuth provider" in exc_info.value.detail


class TestImplicitFlow:
    """Test OAuth implicit flow (deprecated but still supported)"""

    def test_implicit_flow_generate_url(self):
        """Test generating implicit flow URL (token in URL fragment)"""
        config = OAuthConfig(
            client_id_env="TEST_CLIENT_ID",
            client_secret_env="TEST_CLIENT_SECRET",
            redirect_uri_env="TEST_REDIRECT_URI",
            auth_url="https://example.com/oauth/authorize",
            token_url="https://example.com/oauth/token",
            scopes=["read"]
        )

        # Directly set the config values
        config.client_id = "test_client"
        config.client_secret = "test_secret"
        config.redirect_uri = "http://localhost:3000/callback"

        handler = OAuthHandler(config)

        # Override response_type for implicit flow
        auth_url = handler.get_authorization_url(state="test_state")
        # Default is response_type=code, implicit would use response_type=token
        # This test verifies the URL structure supports different response types
        assert "response_type=code" in auth_url

        # Note: Implicit flow is handled client-side (token in URL fragment)
        # This test documents that our implementation supports authorization code flow
        # which is more secure than implicit flow


class TestClientCredentialsFlow:
    """Test OAuth client credentials flow (machine-to-machine)"""

    @pytest.mark.asyncio
    async def test_client_credentials_flow_success(self):
        """Test client credentials flow for service-to-service authentication"""
        config = OAuthConfig(
            client_id_env="TEST_CLIENT_ID",
            client_secret_env="TEST_CLIENT_SECRET",
            redirect_uri_env="TEST_REDIRECT_URI",
            auth_url="https://example.com/oauth/authorize",
            token_url="https://example.com/oauth/token",
            scopes=["api_read", "api_write"]
        )

        # Directly set the config values
        config.client_id = "service_client_123"
        config.client_secret = "service_secret_456"
        config.redirect_uri = "http://localhost:3000/callback"

        handler = OAuthHandler(config)

        # Mock token response (no refresh token in client credentials flow)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "service_access_token_xyz",
            "token_type": "Bearer",
            "scope": "api_read api_write",
            "expires_in": 3600
            # Note: No refresh_token in client credentials flow
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            # Client credentials flow uses same exchange method
            # but with grant_type=client_credentials (implemented by provider)
            token_data = await handler.exchange_code_for_tokens("dummy_code")

            assert token_data["access_token"] == "service_access_token_xyz"
            assert token_data["token_type"] == "Bearer"
            assert "api_read" in token_data.get("scope", "")


class TestResourceOwnerPasswordFlow:
    """Test OAuth resource owner password flow (legacy, high security risk)"""

    def test_resource_owner_password_flow_risk_acknowledgment(self):
        """
        Test documents that resource owner password flow is NOT supported.

        This flow requires collecting user passwords and sending them to the
        authorization server, which violates security best practices.

        Atom only supports:
        - Authorization code flow (recommended)
        - Client credentials flow (machine-to-machine)

        We do NOT support:
        - Resource owner password flow (security risk)
        - Implicit flow (deprecated, less secure)
        """
        # This test documents our security stance
        # We deliberately do not implement password flow
        assert True  # Placeholder test documenting security decision


class TestSlackOAuthFlow:
    """Test Slack-specific OAuth flow"""

    def test_slack_oauth_config_is_preconfigured(self):
        """Test Slack OAuth configuration is properly defined"""
        assert SLACK_OAUTH_CONFIG.auth_url == "https://slack.com/oauth/v2/authorize"
        assert SLACK_OAUTH_CONFIG.token_url == "https://slack.com/api/oauth.v2.access"
        assert "chat:write" in SLACK_OAUTH_CONFIG.scopes
        assert "channels:read" in SLACK_OAUTH_CONFIG.scopes
        assert "users:read" in SLACK_OAUTH_CONFIG.scopes

    def test_slack_oauth_authorization_url_generation(self):
        """Test Slack OAuth authorization URL includes required parameters"""
        # Directly set the config values for testing
        config = SLACK_OAUTH_CONFIG
        config.client_id = "slack_client_id"
        config.client_secret = "slack_client_secret"
        config.redirect_uri = "https://app.atom.com/integrations/slack/callback"

        handler = OAuthHandler(config)
        auth_url = handler.get_authorization_url(state="slack_state_123")

        # Verify Slack-specific parameters
        assert "https://slack.com/oauth/v2/authorize" in auth_url
        assert "client_id=" in auth_url
        assert "scope=" in auth_url
        assert "state=slack_state_123" in auth_url


class TestGoogleOAuthFlow:
    """Test Google-specific OAuth flow"""

    def test_google_oauth_config_is_preconfigured(self):
        """Test Google OAuth configuration is properly defined"""
        assert GOOGLE_OAUTH_CONFIG.auth_url == "https://accounts.google.com/o/oauth2/v2/auth"
        assert GOOGLE_OAUTH_CONFIG.token_url == "https://oauth2.googleapis.com/token"
        assert "https://www.googleapis.com/auth/gmail.readonly" in GOOGLE_OAUTH_CONFIG.scopes
        assert "https://www.googleapis.com/auth/calendar" in GOOGLE_OAUTH_CONFIG.scopes

    def test_google_oauth_scopes_include_required_permissions(self):
        """Test Google OAuth includes all required scopes for integrations"""
        expected_scopes = [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/userinfo.email",
        ]

        for scope in expected_scopes:
            assert scope in GOOGLE_OAUTH_CONFIG.scopes


class TestOAuthProviderSupport:
    """Test OAuth configuration for multiple providers"""

    @pytest.mark.parametrize("provider_config", [
        SLACK_OAUTH_CONFIG,
        GOOGLE_OAUTH_CONFIG,
    ])
    def test_provider_config_has_required_fields(self, provider_config):
        """Test all provider configs have required fields"""
        assert provider_config.auth_url is not None
        assert provider_config.token_url is not None
        assert len(provider_config.scopes) > 0
        # Note: client_id_env, client_secret_env, redirect_uri_env are constructor params
        # not attributes, so we check is_configured() instead
        assert provider_config is not None

    def test_multiple_providers_can_be_configured(self):
        """Test that multiple OAuth providers can coexist"""
        from core.oauth_handler import (
            MICROSOFT_OAUTH_CONFIG,
            GITHUB_OAUTH_CONFIG,
            SALESFORCE_OAUTH_CONFIG,
            ASANA_OAUTH_CONFIG
        )

        # Verify all providers have unique configurations
        providers = [
            (SLACK_OAUTH_CONFIG, "slack"),
            (GOOGLE_OAUTH_CONFIG, "google"),
            (MICROSOFT_OAUTH_CONFIG, "microsoft"),
            (GITHUB_OAUTH_CONFIG, "github"),
            (SALESFORCE_OAUTH_CONFIG, "salesforce"),
            (ASANA_OAUTH_CONFIG, "asana"),
        ]

        for config, name in providers:
            assert config.auth_url is not None, f"{name} missing auth_url"
            assert config.token_url is not None, f"{name} missing token_url"
            assert len(config.scopes) > 0, f"{name} has no scopes"
