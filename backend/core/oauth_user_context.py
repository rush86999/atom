"""
OAuth User Context Manager
Provides user-scoped OAuth token management with automatic refresh
"""

from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class OAuthUserContext:
    """
    Manages OAuth tokens in a user context with automatic refresh.

    This class provides a simplified interface for working with user-specific
    OAuth tokens, handling token validation and refresh automatically.

    Example:
        context = OAuthUserContext(user_id="user123", provider="google")
        access_token = await context.get_access_token()
        # Use access_token for API calls
    """

    def __init__(self, user_id: str, provider: str):
        """
        Initialize OAuth user context.

        Args:
            user_id: User identifier (e.g., user ID, username)
            provider: OAuth provider name (e.g., "google", "microsoft", "slack")
        """
        self.user_id = user_id
        self.provider = provider
        self._token_data: Optional[Dict[str, Any]] = None

    async def get_access_token(self) -> Optional[str]:
        """
        Get valid access token, refreshing if necessary.

        Returns:
            Access token string if available, None otherwise
        """
        try:
            from core.connection_service import ConnectionService

            conn_service = ConnectionService()
            connection = await conn_service.get_connection(self.user_id, self.provider)

            if not connection:
                logger.warning(f"No connection found for user {self.user_id}, provider {self.provider}")
                return None

            # Store token data for later use
            self._token_data = connection

            # Check if token needs refresh
            if self._is_token_expired(connection):
                logger.info(f"Token expired for {self.provider}, attempting refresh")
                connection = await self._refresh_token(connection)
                self._token_data = connection

            return connection.get("access_token")

        except Exception as e:
            logger.error(f"Error getting access token for {self.provider}: {e}")
            return None

    def _is_token_expired(self, connection: Dict[str, Any]) -> bool:
        """
        Check if token is expired or will expire soon.

        Args:
            connection: Connection data dictionary

        Returns:
            True if token is expired or will expire within 5 minutes
        """
        try:
            expires_at = connection.get("expires_at")
            if not expires_at:
                # If no expiry, assume token is valid
                return False

            # Parse expiry timestamp - handle string, datetime, or float timestamp
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            elif isinstance(expires_at, (int, float)):
                expires_at = datetime.fromtimestamp(expires_at)

            # Check if expired or will expire within 5 minutes (300 seconds)
            now = datetime.now()
            time_left = (expires_at - now).total_seconds()

            return time_left < 300  # Less than 5 minutes remaining

        except Exception as e:
            logger.error(f"Error checking token expiry: {e}")
            # Assume valid if we can't check
            return False

    async def _refresh_token(self, connection: Dict[str, Any]) -> Dict[str, Any]:
        """
        Refresh the access token using refresh token.

        Args:
            connection: Current connection data

        Returns:
            Updated connection data with new access token
        """
        try:
            from api.oauth_handler import oauth_handler

            refresh_token = connection.get("refresh_token")
            if not refresh_token:
                logger.warning(f"No refresh token available for {self.provider}")
                return connection

            # Use OAuthHandler to refresh token
            # This will vary by provider
            new_token_data = await oauth_handler.refresh_token(
                provider=self.provider,
                refresh_token=refresh_token,
                user_id=self.user_id
            )

            if new_token_data and new_token_data.get("access_token"):
                logger.info(f"Successfully refreshed {self.provider} token for user {self.user_id}")

                # Update connection with new token data
                from core.connection_service import ConnectionService
                conn_service = ConnectionService()

                await conn_service.update_connection(
                    user_id=self.user_id,
                    provider=self.provider,
                    connection_data=new_token_data
                )

                return new_token_data
            else:
                logger.error(f"Failed to refresh {self.provider} token")
                return connection

        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return connection

    async def get_connection(self) -> Optional[Dict[str, Any]]:
        """
        Get full connection data including all token information.

        Returns:
            Connection data dictionary if available, None otherwise
        """
        if not self._token_data:
            await self.get_access_token()

        return self._token_data

    def is_authenticated(self) -> bool:
        """
        Check if user is authenticated with the provider.

        Returns:
            True if authenticated, False otherwise
        """
        return self._token_data is not None and bool(self._token_data.get("access_token"))

    async def revoke_access(self) -> bool:
        """
        Revoke OAuth access and remove stored tokens.

        Returns:
            True if successfully revoked, False otherwise
        """
        try:
            from core.connection_service import ConnectionService

            conn_service = ConnectionService()
            success = await conn_service.delete_connection(self.user_id, self.provider)

            if success:
                self._token_data = None
                logger.info(f"Successfully revoked {self.provider} access for user {self.user_id}")
                return True
            else:
                logger.warning(f"Failed to revoke {self.provider} access for user {self.user_id}")
                return False

        except Exception as e:
            logger.error(f"Error revoking access: {e}")
            return False

    async def validate_access(self) -> bool:
        """
        Validate that current access token is working.

        Makes a test API call to verify token is valid.

        Returns:
            True if token is valid, False otherwise
        """
        try:
            access_token = await self.get_access_token()
            if not access_token:
                return False

            # Provider-specific validation
            if self.provider == "google":
                return await self._validate_google_token(access_token)
            elif self.provider == "microsoft":
                return await self._validate_microsoft_token(access_token)
            elif self.provider == "slack":
                return await self._validate_slack_token(access_token)
            else:
                # Default: assume valid if we have a token
                return True

        except Exception as e:
            logger.error(f"Error validating access: {e}")
            return False

    async def _validate_google_token(self, access_token: str) -> bool:
        """Validate Google OAuth token"""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://www.googleapis.com/oauth2/v3/tokeninfo",
                    params={"access_token": access_token}
                )
                return response.status_code == 200
        except:
            return False

    async def _validate_microsoft_token(self, access_token: str) -> bool:
        """Validate Microsoft OAuth token"""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/me",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                return response.status_code == 200
        except:
            return False

    async def _validate_slack_token(self, access_token: str) -> bool:
        """Validate Slack OAuth token"""
        try:
            from slack_sdk.web.async_client import AsyncWebClient
            client = AsyncWebClient(token=access_token)
            result = await client.auth_test()
            return result.get("ok", False)
        except:
            return False


class OAuthUserContextManager:
    """
    Manager class for handling multiple OAuth user contexts.

    Provides caching and bulk operations for managing user contexts.
    """

    def __init__(self):
        self._contexts: Dict[str, OAuthUserContext] = {}

    def get_context(self, user_id: str, provider: str) -> OAuthUserContext:
        """
        Get or create OAuth user context.

        Args:
            user_id: User identifier
            provider: OAuth provider name

        Returns:
            OAuthUserContext instance
        """
        key = f"{user_id}:{provider}"

        if key not in self._contexts:
            self._contexts[key] = OAuthUserContext(user_id, provider)

        return self._contexts[key]

    async def get_valid_token(self, user_id: str, provider: str) -> Optional[str]:
        """
        Get valid access token for a user and provider.

        Args:
            user_id: User identifier
            provider: OAuth provider name

        Returns:
            Access token if available, None otherwise
        """
        context = self.get_context(user_id, provider)
        return await context.get_access_token()

    async def revoke_all_for_user(self, user_id: str, providers: list[str]) -> Dict[str, bool]:
        """
        Revoke access for multiple providers.

        Args:
            user_id: User identifier
            providers: List of provider names

        Returns:
            Dictionary mapping provider name to success status
        """
        results = {}

        for provider in providers:
            context = self.get_context(user_id, provider)
            results[provider] = await context.revoke_access()

        return results

    def clear_cache(self):
        """Clear cached contexts"""
        self._contexts.clear()


# Global instance
oauth_context_manager = OAuthUserContextManager()
