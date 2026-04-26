"""
Unit Tests for LLM OAuth Handler

Tests for OAuth 2.0 authentication flow for LLM providers.
"""

import pytest
from unittest.mock import MagicMock, patch

from core.llm_oauth_handler import LLMOAuthHandler
from core.llm_oauth_config import get_oauth_config


class TestLLMOAuthHandler:
    """Test suite for LLMOAuthHandler"""

    def test_get_authorization_url_google(self):
        """Test authorization URL generation for Google"""
        handler = LLMOAuthHandler()

        with patch('core.llm_oauth_config.get_provider_client_id') as mock_client_id:
            mock_client_id.return_value = "test-client-id.apps.googleusercontent.com"

            result = handler.get_authorization_url("google")

            assert "authorization_url" in result
            assert "state" in result
            assert "accounts.google.com" in result["authorization_url"]
            assert "test-client-id.apps.googleusercontent.com" in result["authorization_url"]
            assert result["provider_id"] == "google"

    def test_get_authorization_url_openai(self):
        """Test authorization URL generation for OpenAI"""
        handler = LLMOAuthHandler()

        with patch('core.llm_oauth_config.get_provider_client_id') as mock_client_id:
            mock_client_id.return_value = "test-openai-client-id"

            result = handler.get_authorization_url("openai")

            assert "authorization_url" in result
            assert "platform.openai.com" in result["authorization_url"]
            assert result["provider_id"] == "openai"

    def test_get_authorization_url_unknown_provider(self):
        """Test authorization URL generation fails for unknown provider"""
        handler = LLMOAuthHandler()

        with pytest.raises(ValueError, match="Unknown provider"):
            handler.get_authorization_url("unknown_provider")

    def test_store_oauth_credentials(self):
        """Test storing OAuth credentials"""
        handler = LLMOAuthHandler()

        tokens = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "api:model:read api:model:write"
        }

        with patch('core.llm_oauth_handler.get_db_session') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value.__enter__.return_value = mock_session

            credential = handler.store_oauth_credentials(
                user_id="test-user-id",
                tenant_id="test-tenant-id",
                provider_id="openai",
                tokens=tokens,
                account_info={"email": "test@example.com", "name": "Test User"}
            )

            assert credential is not None
            assert credential.provider_id == "openai"
            assert credential.user_id == "test-user-id"
            assert credential.tenant_id == "test-tenant-id"

    def test_encrypt_decrypt_token(self):
        """Test token encryption and decryption"""
        handler = LLMOAuthHandler()

        original_token = "test_secret_token_12345"

        # Encrypt
        encrypted = handler._encrypt_token(original_token)
        assert encrypted is not None

        # Decrypt
        decrypted = handler._decrypt_token(encrypted)
        assert decrypted == original_token

    def test_get_active_credentials(self):
        """Test retrieving active credentials"""
        handler = LLMOAuthHandler()

        with patch('core.llm_oauth_handler.get_db_session') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value.__enter__.return_value = mock_session

            # Mock credential
            mock_credential = MagicMock()
            mock_credential.id = "test-credential-id"
            mock_credential.provider_id = "google"
            mock_credential.access_token = "encrypted_token"
            mock_credential.last_used_at = None
            mock_credential.usage_count = 0

            mock_session.query().filter().first.return_value = mock_credential

            credential = handler.get_active_credentials("test-user-id", "google")

            assert credential is not None
            assert credential.provider_id == "google"
            assert credential.usage_count == 1  # Should be incremented

    def test_revoke_credentials(self):
        """Test revoking OAuth credentials"""
        handler = LLMOAuthHandler()

        with patch('core.llm_oauth_handler.get_db_session') as mock_db:
            mock_session = MagicMock()
            mock_db.return_value.__enter__.return_value = mock_session

            mock_credential = MagicMock()
            mock_credential.id = "test-credential-id"
            mock_session.query().filter().first.return_value = mock_credential

            result = handler.revoke_credentials("test-credential-id")

            assert result is True
            assert mock_credential.is_active is False
            assert mock_credential.revoked_at is not None


class TestOAuthConfiguration:
    """Test suite for OAuth configuration"""

    def test_get_oauth_config_google(self):
        """Test Google OAuth configuration"""
        config = get_oauth_config("google")

        assert config is not None
        assert config["auth_url"] == "https://accounts.google.com/o/oauth2/v2/auth"
        assert config["token_url"] == "https://oauth2.googleapis.com/token"
        assert "cloud-platform" in str(config["scopes"])

    def test_get_oauth_config_openai(self):
        """Test OpenAI OAuth configuration"""
        config = get_oauth_config("openai")

        assert config is not None
        assert config["auth_url"] == "https://platform.openai.com/oauth/authorize"
        assert config["token_url"] == "https://api.openai.com/v1/oauth/token"

    def test_get_oauth_config_unknown_provider(self):
        """Test unknown provider returns None"""
        config = get_oauth_config("unknown_provider")
        assert config is None

    def test_all_providers_have_required_fields(self):
        """Test all providers have required OAuth fields"""
        providers = ["google", "openai", "anthropic", "huggingface"]

        for provider in providers:
            config = get_oauth_config(provider)

            assert config is not None, f"Provider {provider} has no config"
            assert "auth_url" in config
            assert "token_url" in config
            assert "client_id_env" in config
            assert "client_secret_env" in config
            assert "scopes" in config
            assert isinstance(config["scopes"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
