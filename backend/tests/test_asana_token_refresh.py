"""
Tests for Asana Token Refresh Logic
Tests automatic OAuth token refresh for Asana integration.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch
import pytest

from core.token_storage import TokenStorage


@pytest.fixture
def mock_token_storage():
    """Create a mock TokenStorage"""
    storage = Mock(spec=TokenStorage)

    # Mock get_token to return token data
    storage.get_token = Mock(return_value={
        "access_token": "old_access_token",
        "refresh_token": "test_refresh_token",
        "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()  # Expired
    })

    # Mock is_token_expired
    storage.is_token_expired = Mock(return_value=True)

    # Mock save_token
    storage.save_token = Mock()

    return storage


@pytest.fixture
def valid_token_storage():
    """Create a mock TokenStorage with valid token"""
    storage = Mock(spec=TokenStorage)

    storage.get_token = Mock(return_value={
        "access_token": "valid_access_token",
        "refresh_token": "test_refresh_token",
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()  # Valid
    })

    storage.is_token_expired = Mock(return_value=False)

    return storage


@pytest.fixture
def no_refresh_token_storage():
    """Create a mock TokenStorage without refresh token"""
    storage = Mock(spec=TokenStorage)

    storage.get_token = Mock(return_value={
        "access_token": "old_access_token",
        "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()  # Expired
    })

    storage.is_token_expired = Mock(return_value=True)

    return storage


class TestAsanaTokenRefresh:
    """Test Asana token refresh functionality"""

    @pytest.mark.asyncio
    async def test_refresh_expired_token_success(self, mock_token_storage):
        """Test successful token refresh with expired token"""
        from consolidated.integrations.asana_routes import _refresh_asana_token

        # Mock environment variables
        with patch.dict('os.environ', {
            'ASANA_CLIENT_ID': 'test_client_id',
            'ASANA_CLIENT_SECRET': 'test_client_secret'
        }):
            # Mock httpx.AsyncClient to return successful response
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json = Mock(return_value={
                    "access_token": "new_access_token",
                    "refresh_token": "new_refresh_token",
                    "expires_in": 3600
                })

                mock_client.post = AsyncMock(return_value=mock_response)

                # Call refresh function
                result = await _refresh_asana_token("test_refresh_token")

                # Verify result
                assert result is not None
                assert result["access_token"] == "new_access_token"
                assert result["refresh_token"] == "new_refresh_token"
                assert result["expires_in"] == 3600

                # Verify API was called correctly
                mock_client.post.assert_called_once()
                call_args = mock_client.post.call_args
                assert "https://app.asana.com/-/oauth_token" in str(call_args)

    @pytest.mark.asyncio
    async def test_refresh_token_missing_credentials(self):
        """Test token refresh fails without client credentials"""
        from consolidated.integrations.asana_routes import _refresh_asana_token

        # Mock environment without credentials
        with patch.dict('os.environ', {}, clear=True):
            result = await _refresh_asana_token("test_refresh_token")

            # Should return None on failure
            assert result is None

    @pytest.mark.asyncio
    async def test_refresh_token_api_error(self):
        """Test token refresh handles API errors gracefully"""
        from consolidated.integrations.asana_routes import _refresh_asana_token

        with patch.dict('os.environ', {
            'ASANA_CLIENT_ID': 'test_client_id',
            'ASANA_CLIENT_SECRET': 'test_client_secret'
        }):
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                # Mock error response
                mock_response = Mock()
                mock_response.status_code = 400
                mock_response.text = "Invalid refresh token"

                mock_client.post = AsyncMock(return_value=mock_response)

                result = await _refresh_asana_token("invalid_refresh_token")

                # Should return None on error
                assert result is None

    @pytest.mark.asyncio
    async def test_get_access_token_auto_refresh(self, mock_token_storage):
        """Test that get_access_token automatically refreshes expired tokens"""
        # Import the module after setting up mocks
        import sys
        sys.modules['consolidated.integrations.asana_routes'] = None

        from consolidated.integrations import asana_routes

        with patch('core.token_storage.TokenStorage', return_value=mock_token_storage):
            with patch.object(asana_routes, '_refresh_asana_token') as mock_refresh:
                # Mock successful refresh
                mock_refresh.return_value = {
                    "access_token": "new_access_token",
                    "refresh_token": "new_refresh_token",
                    "expires_in": 3600
                }

                # Import get_access_token after patches are in place
                from consolidated.integrations.asana_routes import get_access_token

                # Call get_access_token
                token = await get_access_token(user_id="test_user")

                # Verify refresh was called
                mock_refresh.assert_called_once_with("test_refresh_token")

                # Verify new token was saved
                mock_token_storage.save_token.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
