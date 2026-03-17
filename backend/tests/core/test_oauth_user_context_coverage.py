"""
Comprehensive tests for OAuth User Context

Target: 60%+ coverage for core/oauth_user_context.py (333 lines)
Focus: OAuth context management, token refresh, validation, provider-specific flows
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from core.oauth_user_context import (
    OAuthUserContext,
    OAuthUserContextManager,
    oauth_context_manager,
)


# ========================================================================
# Fixtures
# ========================================================================


@pytest.fixture
def mock_connection_service():
    """Mock ConnectionService."""
    with patch("core.oauth_user_context.ConnectionService") as mock:
        service = AsyncMock()
        mock.return_value = service
        yield service


@pytest.fixture
def mock_oauth_handler():
    """Mock OAuthHandler."""
    with patch("core.oauth_user_context.oauth_handler") as mock:
        handler = AsyncMock()
        mock.refresh_token = AsyncMock()
        mock.return_value = handler
        yield mock


@pytest.fixture
def valid_connection():
    """Valid connection data."""
    return {
        "access_token": "test_access_token_123",
        "refresh_token": "test_refresh_token_456",
        "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
        "provider": "google",
        "user_id": "user123"
    }


@pytest.fixture
def expired_connection():
    """Expired connection data."""
    return {
        "access_token": "expired_access_token",
        "refresh_token": "valid_refresh_token",
        "expires_at": (datetime.now() - timedelta(minutes=10)).isoformat(),
        "provider": "google",
        "user_id": "user123"
    }


@pytest.fixture
def connection_no_refresh():
    """Connection without refresh token."""
    return {
        "access_token": "test_access_token",
        "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
        "provider": "google",
        "user_id": "user123"
    }


# ========================================================================
# Test Class 1: OAuthUserContext - Context Management
# ========================================================================


class TestOAuthUserContext:
    """Test OAuth user context initialization and basic operations."""

    def test_context_initialization(self):
        """Test OAuthUserContext initialization."""
        context = OAuthUserContext(user_id="user123", provider="google")

        assert context.user_id == "user123"
        assert context.provider == "google"
        assert context._token_data is None

    def test_context_initialization_with_different_providers(self):
        """Test initialization with different providers."""
        providers = ["google", "microsoft", "slack", "github"]

        for provider in providers:
            context = OAuthUserContext(user_id="test_user", provider=provider)
            assert context.provider == provider
            assert context.user_id == "test_user"

    def test_is_authenticated_without_token(self):
        """Test is_authenticated returns False when no token."""
        context = OAuthUserContext(user_id="user123", provider="google")

        assert context.is_authenticated() is False

    def test_is_authenticated_with_token(self):
        """Test is_authenticated returns True when token exists."""
        context = OAuthUserContext(user_id="user123", provider="google")
        context._token_data = {"access_token": "test_token"}

        assert context.is_authenticated() is True

    def test_is_authenticated_with_empty_token(self):
        """Test is_authenticated returns False when token is empty."""
        context = OAuthUserContext(user_id="user123", provider="google")
        context._token_data = {"access_token": ""}

        assert context.is_authenticated() is False

    def test_is_authenticated_with_none_token(self):
        """Test is_authenticated returns False when token is None."""
        context = OAuthUserContext(user_id="user123", provider="google")
        context._token_data = {"access_token": None}

        assert context.is_authenticated() is False


# ========================================================================
# Test Class 2: OAuthUserContext - Token Retrieval
# ========================================================================


class TestTokenRetrieval:
    """Test token retrieval and refresh operations."""

    @pytest.mark.asyncio
    async def test_get_access_token_success(
        self, mock_connection_service, valid_connection
    ):
        """Test successful access token retrieval."""
        context = OAuthUserContext(user_id="user123", provider="google")
        mock_connection_service.get_connection.return_value = valid_connection

        token = await context.get_access_token()

        assert token == "test_access_token_123"
        assert context._token_data == valid_connection
        mock_connection_service.get_connection.assert_called_once_with(
            "user123", "google"
        )

    @pytest.mark.asyncio
    async def test_get_access_token_no_connection(self, mock_connection_service):
        """Test access token retrieval when no connection exists."""
        context = OAuthUserContext(user_id="user123", provider="google")
        mock_connection_service.get_connection.return_value = None

        token = await context.get_access_token()

        assert token is None
        assert context._token_data is None

    @pytest.mark.asyncio
    async def test_get_access_token_with_expired_token(
        self, mock_connection_service, expired_connection, mock_oauth_handler
    ):
        """Test access token retrieval with expired token (triggers refresh)."""
        context = OAuthUserContext(user_id="user123", provider="google")

        # Mock get_connection to return expired token
        mock_connection_service.get_connection.return_value = expired_connection

        # Mock refresh_token to return new token
        new_token_data = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat()
        }
        mock_oauth_handler.refresh_token.return_value = new_token_data

        token = await context.get_access_token()

        # Should have attempted refresh
        mock_oauth_handler.refresh_token.assert_called_once()
        # Token should be from new data or old if refresh failed
        assert token is not None

    @pytest.mark.asyncio
    async def test_get_access_token_exception_handling(
        self, mock_connection_service
    ):
        """Test exception handling in get_access_token."""
        context = OAuthUserContext(user_id="user123", provider="google")
        mock_connection_service.get_connection.side_effect = Exception("Connection error")

        token = await context.get_access_token()

        assert token is None


# ========================================================================
# Test Class 3: Token Validation
# ========================================================================


class TestTokenValidation:
    """Test token validation and expiry checking."""

    def test_is_token_expired_with_valid_token(self):
        """Test expiry check with valid token."""
        context = OAuthUserContext(user_id="user123", provider="google")
        connection = {
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat()
        }

        assert context._is_token_expired(connection) is False

    def test_is_token_expired_with_expired_token(self):
        """Test expiry check with expired token."""
        context = OAuthUserContext(user_id="user123", provider="google")
        connection = {
            "expires_at": (datetime.now() - timedelta(minutes=10)).isoformat()
        }

        assert context._is_token_expired(connection) is True

    def test_is_token_expired_expiring_soon(self):
        """Test expiry check with token expiring in < 5 minutes."""
        context = OAuthUserContext(user_id="user123", provider="google")
        connection = {
            "expires_at": (datetime.now() + timedelta(minutes=2)).isoformat()
        }

        assert context._is_token_expired(connection) is True

    def test_is_token_expired_with_no_expiry(self):
        """Test expiry check when no expiry field exists."""
        context = OAuthUserContext(user_id="user123", provider="google")
        connection = {"access_token": "test_token"}

        assert context._is_token_expired(connection) is False

    def test_is_token_expired_with_datetime_object(self):
        """Test expiry check with datetime object (not string)."""
        context = OAuthUserContext(user_id="user123", provider="google")
        connection = {
            "expires_at": datetime.now() + timedelta(hours=1)
        }

        assert context._is_token_expired(connection) is False

    def test_is_token_expired_with_timestamp(self):
        """Test expiry check with Unix timestamp."""
        context = OAuthUserContext(user_id="user123", provider="google")
        connection = {
            "expires_at": (datetime.now() + timedelta(hours=1)).timestamp()
        }

        assert context._is_token_expired(connection) is False

    def test_is_token_expired_exception_handling(self):
        """Test exception handling in token expiry check."""
        context = OAuthUserContext(user_id="user123", provider="google")
        connection = {"expires_at": "invalid_date_format"}

        # Should return False on error (assume valid)
        assert context._is_token_expired(connection) is False


# ========================================================================
# Test Class 4: Token Refresh
# ========================================================================


class TestTokenRefresh:
    """Test token refresh operations."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(
        self, mock_connection_service, mock_oauth_handler, expired_connection
    ):
        """Test successful token refresh."""
        context = OAuthUserContext(user_id="user123", provider="google")

        new_token_data = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat()
        }
        mock_oauth_handler.refresh_token.return_value = new_token_data

        result = await context._refresh_token(expired_connection)

        assert result["access_token"] == "new_access_token"
        mock_oauth_handler.refresh_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_token_no_refresh_token(
        self, mock_connection_service, connection_no_refresh
    ):
        """Test token refresh when no refresh token available."""
        context = OAuthUserContext(user_id="user123", provider="google")

        result = await context._refresh_token(connection_no_refresh)

        # Should return original connection unchanged
        assert result == connection_no_refresh

    @pytest.mark.asyncio
    async def test_refresh_token_provider_failure(
        self, mock_connection_service, mock_oauth_handler, expired_connection
    ):
        """Test token refresh when provider returns failure."""
        context = OAuthUserContext(user_id="user123", provider="google")

        # Mock refresh to return None or empty
        mock_oauth_handler.refresh_token.return_value = None

        result = await context._refresh_token(expired_connection)

        # Should return original connection unchanged
        assert result == expired_connection

    @pytest.mark.asyncio
    async def test_refresh_token_exception_handling(
        self, mock_connection_service, mock_oauth_handler, expired_connection
    ):
        """Test exception handling in token refresh."""
        context = OAuthUserContext(user_id="user123", provider="google")
        mock_oauth_handler.refresh_token.side_effect = Exception("Refresh failed")

        result = await context._refresh_token(expired_connection)

        # Should return original connection on error
        assert result == expired_connection


# ========================================================================
# Test Class 5: Connection Data
# ========================================================================


class TestConnectionData:
    """Test connection data retrieval."""

    @pytest.mark.asyncio
    async def test_get_connection_without_cached_data(
        self, mock_connection_service, valid_connection
    ):
        """Test get_connection when no cached data exists."""
        context = OAuthUserContext(user_id="user123", provider="google")
        mock_connection_service.get_connection.return_value = valid_connection

        connection = await context.get_connection()

        assert connection == valid_connection
        assert context._token_data == valid_connection

    @pytest.mark.asyncio
    async def test_get_connection_with_cached_data(self, valid_connection):
        """Test get_connection when cached data exists."""
        context = OAuthUserContext(user_id="user123", provider="google")
        context._token_data = valid_connection

        connection = await context.get_connection()

        # Should return cached data without calling service
        assert connection == valid_connection


# ========================================================================
# Test Class 6: Access Revocation
# ========================================================================


class TestAccessRevocation:
    """Test OAuth access revocation."""

    @pytest.mark.asyncio
    async def test_revoke_access_success(self, mock_connection_service):
        """Test successful access revocation."""
        context = OAuthUserContext(user_id="user123", provider="google")
        context._token_data = {"access_token": "test_token"}
        mock_connection_service.delete_connection.return_value = True

        result = await context.revoke_access()

        assert result is True
        assert context._token_data is None
        mock_connection_service.delete_connection.assert_called_once_with(
            "user123", "google"
        )

    @pytest.mark.asyncio
    async def test_revoke_access_failure(self, mock_connection_service):
        """Test access revocation when service fails."""
        context = OAuthUserContext(user_id="user123", provider="google")
        context._token_data = {"access_token": "test_token"}
        mock_connection_service.delete_connection.return_value = False

        result = await context.revoke_access()

        assert result is False
        assert context._token_data is not None  # Should not clear on failure

    @pytest.mark.asyncio
    async def test_revoke_access_exception_handling(
        self, mock_connection_service
    ):
        """Test exception handling in revoke_access."""
        context = OAuthUserContext(user_id="user123", provider="google")
        context._token_data = {"access_token": "test_token"}
        mock_connection_service.delete_connection.side_effect = Exception(
            "Delete failed"
        )

        result = await context.revoke_access()

        assert result is False


# ========================================================================
# Test Class 7: Access Validation
# ========================================================================


class TestAccessValidation:
    """Test access token validation."""

    @pytest.mark.asyncio
    async def test_validate_access_google_success(
        self, mock_connection_service, valid_connection
    ):
        """Test Google token validation success."""
        context = OAuthUserContext(user_id="user123", provider="google")
        mock_connection_service.get_connection.return_value = valid_connection

        with patch("core.oauth_user_context.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            result = await context.validate_access()

            assert result is True

    @pytest.mark.asyncio
    async def test_validate_access_google_failure(
        self, mock_connection_service, valid_connection
    ):
        """Test Google token validation failure."""
        context = OAuthUserContext(user_id="user123", provider="google")
        mock_connection_service.get_connection.return_value = valid_connection

        with patch("core.oauth_user_context.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            result = await context.validate_access()

            assert result is False

    @pytest.mark.asyncio
    async def test_validate_access_no_token(self, mock_connection_service):
        """Test validation when no token available."""
        context = OAuthUserContext(user_id="user123", provider="google")
        mock_connection_service.get_connection.return_value = None

        result = await context.validate_access()

        assert result is False

    @pytest.mark.asyncio
    async def test_validate_access_microsoft_success(
        self, mock_connection_service, valid_connection
    ):
        """Test Microsoft token validation success."""
        context = OAuthUserContext(user_id="user123", provider="microsoft")
        valid_connection["provider"] = "microsoft"
        mock_connection_service.get_connection.return_value = valid_connection

        with patch("core.oauth_user_context.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            result = await context.validate_access()

            assert result is True

    @pytest.mark.asyncio
    async def test_validate_access_microsoft_failure(
        self, mock_connection_service, valid_connection
    ):
        """Test Microsoft token validation failure."""
        context = OAuthUserContext(user_id="user123", provider="microsoft")
        valid_connection["provider"] = "microsoft"
        mock_connection_service.get_connection.return_value = valid_connection

        with patch("core.oauth_user_context.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            result = await context.validate_access()

            assert result is False

    @pytest.mark.asyncio
    async def test_validate_access_slack_success(
        self, mock_connection_service, valid_connection
    ):
        """Test Slack token validation success."""
        context = OAuthUserContext(user_id="user123", provider="slack")
        valid_connection["provider"] = "slack"
        mock_connection_service.get_connection.return_value = valid_connection

        with patch("core.oauth_user_context.AsyncWebClient") as mock_web_client:
            mock_client = MagicMock()
            mock_client.auth_test.return_value = {"ok": True}
            mock_web_client.return_value = mock_client

            result = await context.validate_access()

            assert result is True

    @pytest.mark.asyncio
    async def test_validate_access_slack_failure(
        self, mock_connection_service, valid_connection
    ):
        """Test Slack token validation failure."""
        context = OAuthUserContext(user_id="user123", provider="slack")
        valid_connection["provider"] = "slack"
        mock_connection_service.get_connection.return_value = valid_connection

        with patch("core.oauth_user_context.AsyncWebClient") as mock_web_client:
            mock_client = MagicMock()
            mock_client.auth_test.return_value = {"ok": False}
            mock_web_client.return_value = mock_client

            result = await context.validate_access()

            assert result is False

    @pytest.mark.asyncio
    async def test_validate_access_unknown_provider(
        self, mock_connection_service, valid_connection
    ):
        """Test validation with unknown provider (defaults to True)."""
        context = OAuthUserContext(user_id="user123", provider="unknown")
        valid_connection["provider"] = "unknown"
        mock_connection_service.get_connection.return_value = valid_connection

        result = await context.validate_access()

        # Unknown providers default to True
        assert result is True


# ========================================================================
# Test Class 8: OAuthUserContextManager
# ========================================================================


class TestOAuthUserContextManager:
    """Test OAuth user context manager."""

    def test_manager_initialization(self):
        """Test manager initialization."""
        manager = OAuthUserContextManager()

        assert manager._contexts == {}

    def test_get_context_creates_new(self):
        """Test get_context creates new context if not exists."""
        manager = OAuthUserContextManager()

        context = manager.get_context("user123", "google")

        assert isinstance(context, OAuthUserContext)
        assert context.user_id == "user123"
        assert context.provider == "google"
        assert "user123:google" in manager._contexts

    def test_get_context_returns_cached(self):
        """Test get_context returns cached context."""
        manager = OAuthUserContextManager()

        context1 = manager.get_context("user123", "google")
        context2 = manager.get_context("user123", "google")

        # Should return same instance
        assert context1 is context2

    def test_get_context_different_keys(self):
        """Test get_context with different user/provider combinations."""
        manager = OAuthUserContextManager()

        context1 = manager.get_context("user1", "google")
        context2 = manager.get_context("user1", "microsoft")
        context3 = manager.get_context("user2", "google")

        # Should be different instances
        assert context1 is not context2
        assert context1 is not context3
        assert context2 is not context3

    @pytest.mark.asyncio
    async def test_get_valid_token(self, mock_connection_service, valid_connection):
        """Test get_valid_token convenience method."""
        manager = OAuthUserContextManager()
        mock_connection_service.get_connection.return_value = valid_connection

        token = await manager.get_valid_token("user123", "google")

        assert token == "test_access_token_123"

    @pytest.mark.asyncio
    async def test_revoke_all_for_user(
        self, mock_connection_service, valid_connection
    ):
        """Test revoking access for multiple providers."""
        manager = OAuthUserContextManager()
        mock_connection_service.delete_connection.return_value = True

        results = await manager.revoke_all_for_user(
            "user123", ["google", "microsoft", "slack"]
        )

        assert results["google"] is True
        assert results["microsoft"] is True
        assert results["slack"] is True

    def test_clear_cache(self):
        """Test clearing manager cache."""
        manager = OAuthUserContextManager()
        manager.get_context("user123", "google")
        manager.get_context("user456", "microsoft")

        assert len(manager._contexts) == 2

        manager.clear_cache()

        assert len(manager._contexts) == 0


# ========================================================================
# Test Class 9: Global Instance
# ========================================================================


class TestGlobalInstance:
    """Test global oauth_context_manager instance."""

    def test_global_manager_exists(self):
        """Test global manager instance exists."""
        from core.oauth_user_context import oauth_context_manager

        assert isinstance(oauth_context_manager, OAuthUserContextManager)

    def test_global_manager_is_singleton(self):
        """Test global manager is same instance across imports."""
        from core.oauth_user_context import oauth_context_manager as manager1
        from core.oauth_user_context import oauth_context_manager as manager2

        assert manager1 is manager2


# ========================================================================
# Test Class 10: Edge Cases
# ========================================================================


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_context_with_empty_user_id(self):
        """Test context with empty user ID."""
        context = OAuthUserContext(user_id="", provider="google")

        assert context.user_id == ""
        assert context.provider == "google"

    @pytest.mark.asyncio
    async def test_context_with_special_characters_in_user_id(self):
        """Test context with special characters in user ID."""
        context = OAuthUserContext(
            user_id="user@example.com", provider="google"
        )

        assert context.user_id == "user@example.com"

    def test_multiple_token_refresh_attempts(self):
        """Test multiple token expiry checks work correctly."""
        context = OAuthUserContext(user_id="user123", provider="google")
        connection = {
            "expires_at": (datetime.now() + timedelta(minutes=6)).isoformat()
        }

        # First check - should not be expired
        assert context._is_token_expired(connection) is False

        # Modify to expiring soon
        connection["expires_at"] = (
            datetime.now() + timedelta(minutes=4)
        ).isoformat()

        # Second check - should be expired
        assert context._is_token_expired(connection) is True

    @pytest.mark.asyncio
    async def test_token_data_persistence_across_operations(
        self, mock_connection_service, valid_connection
    ):
        """Test that token data persists across operations."""
        context = OAuthUserContext(user_id="user123", provider="google")
        mock_connection_service.get_connection.return_value = valid_connection

        # Get token first time
        await context.get_access_token()
        assert context._token_data is not None

        # Get connection should return cached data
        connection = await context.get_connection()
        assert connection == valid_connection
