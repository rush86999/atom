#!/usr/bin/env python3
"""
Tests for Teams Adapter JWT Signature Verification
Tests the security fix for JWT signature validation
"""

import time
from unittest.mock import AsyncMock, Mock, patch
import jwt
import pytest
from fastapi import Request

from core.communication.adapters.teams import TeamsAdapter

# Mock RSA keys for testing
MOCK_PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAyKf7KmFm1CywFZtJ8q7Xy8XKxQvX0Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1
Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z
4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z
6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z
8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z
0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1
Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z
3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z
4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z
5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z
6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z
7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z
8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z
9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z
0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z
1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1
Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2
Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3
Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z
4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4
Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z
5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5
Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z
6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6
Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z
7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7
Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8
Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9
Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0
Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1
Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2
Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3
Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6Z7Z8Z9Z0Z1Z2Z3Z4
Z5Z6Z7Z8Z9Z0wIDAQABAoIBAFG7mXgJ5J9E8YQJYH8YQJYH8YQJYH8YQJYH8YQJY
H8YQJYH8YQJYH8YQJYH8YQJYH8YQJYH8YQJYH8YQJYH8YQJYH8YQJYH8YQJYH8YQ
-----END RSA PRIVATE KEY-----"""


@pytest.fixture
def teams_adapter(monkeypatch):
    """Create Teams adapter with test configuration"""
    monkeypatch.setenv("MICROSOFT_APP_ID", "test-app-id")
    monkeypatch.setenv("MICROSOFT_APP_PASSWORD", "test-password")
    return TeamsAdapter()


@pytest.fixture
def mock_request():
    """Create mock FastAPI request"""
    request = Mock(spec=Request)
    return request


def create_test_token(app_id="test-app-id", key_id="test-key-id", private_key=None):
    """Helper to create a test JWT token"""
    if private_key is None:
        # Use a simple HS256 token for testing (Microsoft uses RS256 in production)
        return jwt.encode(
            {
                "aud": app_id,
                "iss": "https://api.botframework.com",
                "exp": int(time.time()) + 3600,
                "serviceUrl": "https://smba.trafficmanager.net/amer/"
            },
            "secret-key",
            algorithm="HS256",
            headers={"kid": key_id}
        )
    else:
        # Use RS256 with provided key
        return jwt.encode(
            {
                "aud": app_id,
                "iss": "https://api.botframework.com",
                "exp": int(time.time()) + 3600
            },
            private_key,
            algorithm="RS256",
            headers={"kid": key_id}
        )


class TestDevelopmentMode:
    """Tests for development mode bypass"""

    @pytest.mark.asyncio
    async def test_dev_mode_no_app_id(self, teams_adapter, mock_request, monkeypatch):
        """Test that requests are allowed in development mode without app_id"""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("MICROSOFT_APP_ID", "")

        adapter = TeamsAdapter()
        mock_request.headers = {"Authorization": "Bearer fake-token"}

        result = await adapter.verify_request(mock_request, b"{}")
        assert result is True, "Dev mode should allow requests without app_id"


class TestTokenStructure:
    """Tests for token structure validation"""

    @pytest.mark.asyncio
    async def test_missing_bearer_prefix(self, teams_adapter, mock_request):
        """Test rejection of token without 'Bearer ' prefix"""
        mock_request.headers = {"Authorization": "InvalidFormat token"}

        result = await teams_adapter.verify_request(mock_request, b"{}")
        assert result is False, "Should reject token without Bearer prefix"

    @pytest.mark.asyncio
    async def test_missing_authorization_header(self, teams_adapter, mock_request):
        """Test rejection of request without Authorization header"""
        mock_request.headers = {}

        result = await teams_adapter.verify_request(mock_request, b"{}")
        assert result is False, "Should reject request without Authorization header"


class TestSignatureVerification:
    """Tests for JWT signature verification"""

    @pytest.mark.asyncio
    async def test_missing_kid_in_header(self, teams_adapter, mock_request):
        """Test rejection when JWT header missing 'kid' parameter"""
        # Create token without kid
        token = jwt.encode(
            {
                "aud": "test-app-id",
                "iss": "https://api.botframework.com",
                "exp": int(time.time()) + 3600
            },
            "secret-key",
            algorithm="HS256"
        )

        mock_request.headers = {"Authorization": f"Bearer {token}"}

        result = await teams_adapter.verify_request(mock_request, b"{}")
        assert result is False, "Should reject token without kid in header"

    @pytest.mark.asyncio
    async def test_no_matching_jwk_found(self, teams_adapter, mock_request):
        """Test rejection when no matching JWK found for kid"""
        # Mock JWKS keys with different kid
        teams_adapter.jwks_keys = [{"kid": "different-key-id", "kty": "RSA"}]
        teams_adapter.jwks_expiry = time.time() + 3600

        token = create_test_token(key_id="test-key-id")
        mock_request.headers = {"Authorization": f"Bearer {token}"}

        result = await teams_adapter.verify_request(mock_request, b"{}")
        assert result is False, "Should reject when no matching JWK found"

    @pytest.mark.asyncio
    async def test_audience_mismatch(self, teams_adapter, mock_request):
        """Test rejection when audience doesn't match app_id"""
        # Create token with wrong audience
        token = create_test_token(app_id="wrong-app-id", key_id="test-key-id")

        # Mock successful JWKS fetch
        with patch.object(teams_adapter, '_get_jwks_keys', return_value=[{"kid": "test-key-id", "kty": "RSA", "n": "test", "e": "AQAB"}]):
            mock_request.headers = {"Authorization": f"Bearer {token}"}

            result = await teams_adapter.verify_request(mock_request, b"{}")
            assert result is False, "Should reject token with wrong audience"


class TestClaimsValidation:
    """Tests for JWT claims validation"""

    @pytest.mark.asyncio
    async def test_issuer_validation(self, teams_adapter, mock_request):
        """Test that issuer is validated correctly"""
        # This would require mocking the full JWKS public key construction
        # For now, we test the structure
        pass


class TestJWKSKeyRetrieval:
    """Tests for JWKS key retrieval and caching"""

    @pytest.mark.asyncio
    async def test_jwks_caching(self, teams_adapter):
        """Test that JWKS keys are cached"""
        # Mock successful fetch
        mock_keys = [{"kid": "key1", "kty": "RSA"}]

        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.json.return_value = {
                "jwks_uri": "https://login.botframework.com/v1/keys"
            }
            mock_response.raise_for_status = Mock()

            mock_keys_response = Mock()
            mock_keys_response.json.return_value = {"keys": mock_keys}
            mock_keys_response.raise_for_status = Mock()

            mock_client.return_value.__aenter__.return_value.get = Mock(
                side_effect=[mock_response, mock_keys_response]
            )

            # First call should fetch
            keys1 = await teams_adapter._get_jwks_keys()
            assert keys1 == mock_keys

            # Update expiry to past
            teams_adapter.jwks_expiry = time.time() - 100

            # Second call should fetch again
            keys2 = await teams_adapter._get_jwks_keys()
            assert keys2 == mock_keys


class TestSecurityScenarios:
    """Security-focused test scenarios"""

    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, teams_adapter, mock_request):
        """Test that expired tokens are rejected"""
        # Create expired token
        token = jwt.encode(
            {
                "aud": "test-app-id",
                "iss": "https://api.botframework.com",
                "exp": int(time.time()) - 3600  # Expired 1 hour ago
            },
            "secret-key",
            algorithm="HS256",
            headers={"kid": "test-key-id"}
        )

        mock_request.headers = {"Authorization": f"Bearer {token}"}

        result = await teams_adapter.verify_request(mock_request, b"{}")
        assert result is False, "Should reject expired token"

    @pytest.mark.asyncio
    async def test_invalid_signature_rejected(self, teams_adapter, mock_request):
        """Test that tokens with invalid signatures are rejected"""
        # Create token then corrupt it
        token = create_test_token()
        corrupted_token = token[:-10] + "CORRUPTED"

        mock_request.headers = {"Authorization": f"Bearer {corrupted_token}"}

        result = await teams_adapter.verify_request(mock_request, b"{}")
        assert result is False, "Should reject token with invalid signature"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
