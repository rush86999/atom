"""
Integration Tests for LLM OAuth Routes

Tests for OAuth API endpoints including authorization flow,
callback handling, and credential management.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from core.models import LLMOAuthCredential
from main_api_app import app


class TestOAuthRoutes:
    """Test suite for OAuth API routes"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def mock_user_context(self, client):
        """Mock authenticated user context"""
        with patch.object(client.app, 'state') as mock_state:
            mock_state.user_id = "test-user-id"
            mock_state.tenant_id = "test-tenant-id"
            mock_state.workspace_id = "test-workspace-id"
            yield mock_state

    def test_list_providers(self, client):
        """Test listing supported OAuth providers"""
        response = client.get("/api/v1/llm/oauth/providers")

        assert response.status_code == 200
        providers = response.json()
        assert isinstance(providers, list)
        assert "google" in providers
        assert "openai" in providers
        assert "anthropic" in providers
        assert "huggingface" in providers

    def test_get_provider_status(self, client, mock_user_context):
        """Test getting provider credential status"""
        response = client.get("/api/v1/llm/oauth/providers/openai/status")

        assert response.status_code == 200
        status = response.json()
        assert "provider_id" in status
        assert status["provider_id"] == "openai"
        assert "has_oauth" in status
        assert "has_byok" in status
        assert "has_env" in status
        assert "active_method" in status

    def test_authorize_missing_provider(self, client, mock_user_context):
        """Test authorization fails for unknown provider"""
        response = client.post(
            "/api/v1/llm/oauth/authorize",
            json={"provider_id": "unknown_provider"}
        )

        assert response.status_code == 400

    def test_authorize_unauthorized(self, client):
        """Test authorization fails without user context"""
        # Don't set user context
        response = client.post(
            "/api/v1/llm/oauth/authorize",
            json={"provider_id": "google"}
        )

        assert response.status_code == 401

    def test_list_credentials(self, client, mock_user_context):
        """Test listing OAuth credentials"""
        with patch('core.llm_credential_service.LLMCredentialService') as mock_service:
            mock_instance = MagicMock()
            mock_service.return_value = mock_instance
            mock_instance.list_oauth_credentials.return_value = []

            response = client.get("/api/v1/llm/oauth/credentials")

            assert response.status_code == 200
            data = response.json()
            assert "credentials" in data

    def test_revoke_credential(self, client, mock_user_context):
        """Test revoking OAuth credential"""
        with patch('core.llm_credential_service.LLMCredentialService') as mock_service:
            mock_instance = MagicMock()
            mock_service.return_value = mock_instance
            mock_instance.revoke_oauth_credential.return_value = True

            response = client.delete("/api/v1/llm/oauth/credentials/test-credential-id")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_revoke_credential_not_found(self, client, mock_user_context):
        """Test revoking non-existent credential"""
        with patch('core.llm_credential_service.LLMCredentialService') as mock_service:
            mock_instance = MagicMock()
            mock_service.return_value = mock_instance
            mock_instance.revoke_oauth_credential.return_value = False

            response = client.delete("/api/v1/llm/oauth/credentials/nonexistent-id")

            assert response.status_code == 404

    def test_refresh_credential(self, client, mock_user_context):
        """Test refreshing OAuth credential"""
        with patch('core.llm_credential_service.LLMCredentialService') as mock_service:
            mock_instance = MagicMock()
            mock_service.return_value = mock_instance
            mock_instance.refresh_oauth_credential.return_value = True

            response = client.post("/api/v1/llm/oauth/credentials/test-credential-id/refresh")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


class TestCredentialServiceIntegration:
    """Test suite for credential service integration"""

    def test_get_credential_oauth_priority(self):
        """Test credential service prioritizes OAuth over BYOK"""
        from core.llm_credential_service import LLMCredentialService

        with patch('core.llm_credential_service.LLMOAuthHandler') as mock_oauth:
            with patch('core.llm_credential_service.get_byok_manager') as mock_byok:
                # Mock OAuth handler to return a token
                mock_oauth_instance = MagicMock()
                mock_oauth.return_value = mock_oauth_instance
                mock_oauth_instance.get_active_credentials.return_value = MagicMock()
                mock_oauth_instance.validate_and_refresh_if_needed.return_value = True
                mock_oauth_instance.decrypt_access_token.return_value "oauth_token_123"

                # Mock BYOK manager
                mock_byok_manager = MagicMock()
                mock_byok.return_value = mock_byok_manager
                mock_byok_manager.is_configured.return_value = True
                mock_byok_manager.get_api_key.return_value = "byok_key_456"

                import asyncio

                service = LLMCredentialService(
                    user_id="test-user",
                    tenant_id="test-tenant",
                    workspace_id="test-workspace"
                )

                # Test that OAuth is prioritized
                async def test():
                    cred_type, cred_value = await service.get_credential("openai")
                    assert cred_type == "oauth"
                    assert cred_value == "oauth_token_123"

                asyncio.run(test())

    def test_get_credential_fallback_to_byok(self):
        """Test credential service falls back to BYOK when OAuth unavailable"""
        from core.llm_credential_service import LLMCredentialService

        with patch('core.llm_credential_service.LLMOAuthHandler') as mock_oauth:
            with patch('core.llm_credential_service.get_byok_manager') as mock_byok:
                # Mock OAuth handler to return None (no OAuth configured)
                mock_oauth_instance = MagicMock()
                mock_oauth.return_value = mock_oauth_instance
                mock_oauth_instance.get_active_credentials.return_value = None

                # Mock BYOK manager
                mock_byok_manager = MagicMock()
                mock_byok.return_value = mock_byok_manager
                mock_byok_manager.is_configured.return_value = True
                mock_byok_manager.get_api_key.return_value = "byok_key_456"

                import asyncio

                service = LLMCredentialService(
                    user_id="test-user",
                    tenant_id="test-tenant",
                    workspace_id="test-workspace"
                )

                # Test fallback to BYOK
                async def test():
                    cred_type, cred_value = await service.get_credential("openai")
                    assert cred_type == "byok"
                    assert cred_value == "byok_key_456"

                asyncio.run(test())

    def test_get_credential_fallback_to_env(self):
        """Test credential service falls back to environment variable"""
        from core.llm_credential_service import LLMCredentialService
        import os

        with patch('core.llm_credential_service.LLMOAuthHandler') as mock_oauth:
            with patch('core.llm_credential_service.get_byok_manager') as mock_byok:
                with patch.dict(os.environ, {'OPENAI_API_KEY': 'env_key_789'}):
                    # Mock OAuth handler to return None
                    mock_oauth_instance = MagicMock()
                    mock_oauth.return_value = mock_oauth_instance
                    mock_oauth_instance.get_active_credentials.return_value = None

                    # Mock BYOK manager to return None
                    mock_byok_manager = MagicMock()
                    mock_byok.return_value = mock_byok_manager
                    mock_byok_manager.is_configured.return_value = False

                    import asyncio

                    service = LLMCredentialService(
                        user_id="test-user",
                        tenant_id="test-tenant",
                        workspace_id="test-workspace"
                    )

                    # Test fallback to ENV
                    async def test():
                        cred_type, cred_value = await service.get_credential("openai")
                        assert cred_type == "env"
                        assert cred_value == "env_key_789"

                    asyncio.run(test())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
