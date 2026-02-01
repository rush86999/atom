"""
Tests for Asana Token Refresh Implementation
Tests the automatic token refresh functionality when access tokens expire.
"""

import pytest
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from httpx import Response

# Set environment variables before importing
os.environ["ASANA_CLIENT_ID"] = "test_client_id"
os.environ["ASANA_CLIENT_SECRET"] = "test_client_secret"


@pytest.fixture
def mock_token_storage():
    """Mock TokenStorage for testing"""
    with patch('consolidated.integrations.asana_routes.TokenStorage') as mock:
        storage_instance = Mock()
        storage_instance.get_token = Mock()
        storage_instance.is_token_expired = Mock()
        storage_instance.save_token = Mock()
        mock.return_value = storage_instance
        yield storage_instance


@pytest.fixture
def valid_token_data():
    """Valid token data that hasn't expired"""
    return {
        "access_token": "valid_access_token_123",
        "refresh_token": "valid_refresh_token_456",
        "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
        "updated_at": datetime.now().isoformat()
    }


@pytest.fixture
def expired_token_data():
    """Expired token data that needs refresh"""
    return {
        "access_token": "expired_access_token_789",
        "refresh_token": "valid_refresh_token_456",
        "expires_at": (datetime.now() - timedelta(hours=1)).isoformat(),
        "updated_at": (datetime.now() - timedelta(hours=2)).isoformat()
    }


class TestAsanaTokenRefresh:
    """Test suite for Asana token refresh functionality"""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self):
        """Test successful token refresh"""
        from consolidated.integrations.asana_routes import _refresh_asana_token

        # Mock httpx.AsyncClient
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token_abc",
            "refresh_token": "new_refresh_token_def",
            "expires_in": 3600
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            result = await _refresh_asana_token("valid_refresh_token_456")

            assert result is not None
            assert result["access_token"] == "new_access_token_abc"
            assert result["refresh_token"] == "new_refresh_token_def"
            assert result["expires_in"] == 3600

    @pytest.mark.asyncio
    async def test_refresh_token_without_new_refresh_token(self):
        """Test token refresh when API doesn't return new refresh token"""
        from consolidated.integrations.asana_routes import _refresh_asana_token

        # Mock response without new refresh_token (some OAuth providers don't return it)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token_abc",
            "expires_in": 7200
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            result = await _refresh_asana_token("old_refresh_token_xyz")

            assert result is not None
            assert result["access_token"] == "new_access_token_abc"
            # Should fall back to old refresh token
            assert result["refresh_token"] == "old_refresh_token_xyz"
            assert result["expires_in"] == 7200

    @pytest.mark.asyncio
    async def test_refresh_token_api_error(self):
        """Test token refresh when API returns error"""
        from consolidated.integrations.asana_routes import _refresh_asana_token

        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Invalid refresh token"

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            result = await _refresh_asana_token("invalid_refresh_token")

            assert result is None

    @pytest.mark.asyncio
    async def test_refresh_token_network_error(self):
        """Test token refresh when network error occurs"""
        from consolidated.integrations.asana_routes import _refresh_asana_token

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(side_effect=Exception("Network error"))

            result = await _refresh_asana_token("refresh_token")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_access_token_valid_not_expired(self, mock_token_storage, valid_token_data):
        """Test get_access_token with valid non-expired token"""
        from consolidated.integrations.asana_routes import get_access_token
        from fastapi import Query

        mock_token_storage.get_token.return_value = valid_token_data
        mock_token_storage.is_token_expired.return_value = False

        access_token = await get_access_token(user_id="test_user")

        assert access_token == "valid_access_token_123"
        mock_token_storage.get_token.assert_called_once_with("asana_test_user")
        mock_token_storage.is_token_expired.assert_called_once_with("asana_test_user")
        # Should not call save_token for valid non-expired token
        mock_token_storage.save_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_access_token_expired_with_refresh(self, mock_token_storage, expired_token_data):
        """Test get_access_token with expired token that has refresh token"""
        from consolidated.integrations.asana_routes import get_access_token

        mock_token_storage.get_token.return_value = expired_token_data
        mock_token_storage.is_token_expired.return_value = True

        # Mock successful refresh
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "refreshed_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            access_token = await get_access_token(user_id="test_user")

            assert access_token == "refreshed_access_token"
            # Should save the refreshed token
            mock_token_storage.save_token.assert_called_once()
            saved_token = mock_token_storage.save_token.call_args[0][1]
            assert saved_token["access_token"] == "refreshed_access_token"
            assert saved_token["refresh_token"] == "new_refresh_token"

    @pytest.mark.asyncio
    async def test_get_access_token_expired_refresh_fails(self, mock_token_storage, expired_token_data):
        """Test get_access_token when token refresh fails"""
        from consolidated.integrations.asana_routes import get_access_token
        from fastapi import HTTPException

        mock_token_storage.get_token.return_value = expired_token_data
        mock_token_storage.is_token_expired.return_value = True

        # Mock failed refresh
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Invalid refresh token"

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            with pytest.raises(HTTPException) as exc_info:
                await get_access_token(user_id="test_user")

            assert exc_info.value.status_code == 401
            assert "refresh failed" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_get_access_token_no_token_found(self, mock_token_storage):
        """Test get_access_token when no token is found"""
        from consolidated.integrations.asana_routes import get_access_token
        from fastapi import HTTPException

        mock_token_storage.get_token.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await get_access_token(user_id="new_user")

        assert exc_info.value.status_code == 401
        assert "No Asana token found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_access_token_expired_no_refresh_token(self, mock_token_storage):
        """Test get_access_token when token expired but no refresh token available"""
        from consolidated.integrations.asana_routes import get_access_token
        from fastapi import HTTPException

        expired_no_refresh = {
            "access_token": "expired_token",
            "expires_at": (datetime.now() - timedelta(hours=1)).isoformat()
        }

        mock_token_storage.get_token.return_value = expired_no_refresh
        mock_token_storage.is_token_expired.return_value = True

        with pytest.raises(HTTPException) as exc_info:
            await get_access_token(user_id="test_user")

        assert exc_info.value.status_code == 401
        assert "no refresh token available" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_refresh_token_missing_credentials(self):
        """Test token refresh when client credentials are not configured"""
        from consolidated.integrations.asana_routes import _refresh_asana_token

        # Temporarily remove environment variables
        old_client_id = os.environ.get("ASANA_CLIENT_ID")
        old_client_secret = os.environ.get("ASANA_CLIENT_SECRET")

        os.environ["ASANA_CLIENT_ID"] = ""
        os.environ["ASANA_CLIENT_SECRET"] = ""

        result = await _refresh_asana_token("refresh_token")

        # Restore environment variables
        if old_client_id:
            os.environ["ASANA_CLIENT_ID"] = old_client_id
        if old_client_secret:
            os.environ["ASANA_CLIENT_SECRET"] = old_client_secret

        assert result is None


class TestAsanaTokenRefreshIntegration:
    """Integration tests for token refresh with storage"""

    @pytest.mark.asyncio
    async def test_full_refresh_flow(self):
        """Test complete flow: check expiry -> refresh -> save -> return new token"""
        from consolidated.integrations.asana_routes import get_access_token
        from core.token_storage import TokenStorage

        # Create real token storage instance for integration test
        token_storage = TokenStorage()
        user_id = "integration_test_user"
        provider_key = f"asana_{user_id}"

        # Setup: Save an expired token
        expired_token = {
            "access_token": "old_expired_token",
            "refresh_token": "integration_refresh_token",
            "expires_at": (datetime.now() - timedelta(hours=1)).isoformat()
        }
        token_storage.save_token(provider_key, expired_token)

        # Mock the refresh API call
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "integration_new_token",
            "refresh_token": "integration_new_refresh",
            "expires_in": 3600
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            # Mock TokenStorage to use our instance
            with patch('consolidated.integrations.asana_routes.TokenStorage', return_value=token_storage):
                access_token = await get_access_token(user_id=user_id)

                # Verify we got the new token
                assert access_token == "integration_new_token"

                # Verify the token was saved with new data
                updated_token = token_storage.get_token(provider_key)
                assert updated_token["access_token"] == "integration_new_token"
                assert updated_token["refresh_token"] == "integration_new_refresh"

        # Cleanup
        token_storage.delete_token(provider_key)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
