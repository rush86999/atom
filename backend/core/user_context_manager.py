"""
User Context Manager

Centralized token management and user context for integrations.
Provides a clean interface for retrieving and managing user tokens across different platforms.
"""

import logging
import os
from typing import Dict, Optional, Any
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class UserContextManager:
    """
    Manages user context and authentication tokens for external integrations.

    Provides a unified interface for retrieving tokens from multiple sources:
    1. Database token storage (user-specific tokens)
    2. Environment variables (bot/service account tokens)
    3. Configuration files
    """

    def __init__(self, db: Optional[Session] = None):
        """
        Initialize the user context manager.

        Args:
            db: Optional database session for user token lookup
        """
        self.db = db
        self._token_storage = None

    @property
    def token_storage(self):
        """Lazy load token storage"""
        if self._token_storage is None:
            try:
                from core.token_storage import token_storage
                self._token_storage = token_storage
            except ImportError:
                logger.warning("token_storage module not available")
                self._token_storage = None
        return self._token_storage

    def get_token(
        self,
        provider: str,
        user_id: Optional[str] = None,
        token_type: str = "access_token"
    ) -> Optional[str]:
        """
        Get authentication token for a provider.

        Retrieval strategy:
        1. If user_id provided, try database token storage for user-specific token
        2. Fallback to environment variable for bot/service account token
        3. Return None if no token found

        Args:
            provider: Provider name (e.g., "slack", "gmail", "outlook")
            user_id: Optional user ID for user-specific token lookup
            token_type: Type of token to retrieve (default: "access_token")

        Returns:
            Token string or None if not found
        """
        # Try user-specific token from database
        if user_id and self.token_storage:
            try:
                tokens = self.token_storage.get_token(provider, user_id)
                if tokens and token_type in tokens:
                    token = tokens[token_type]
                    logger.debug(f"Retrieved {token_type} for {provider} user {user_id}")
                    return token
            except Exception as e:
                logger.debug(f"Could not retrieve user token from storage: {e}")

        # Fallback to environment variable (bot mode)
        env_var_names = [
            f"{provider.upper()}_BOT_TOKEN",
            f"{provider.upper()}_ACCESS_TOKEN",
            f"{provider.upper()}_TOKEN"
        ]

        for env_var in env_var_names:
            token = os.getenv(env_var)
            if token:
                logger.debug(f"Retrieved {provider} token from env var {env_var}")
                return token

        logger.warning(f"No token found for provider {provider}")
        return None

    def get_token_with_context(
        self,
        provider: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get token with additional context information.

        Returns a dictionary with:
        - token: The authentication token
        - source: Where the token came from ("user" or "bot")
        - user_id: User ID if applicable
        - provider: Provider name

        Args:
            provider: Provider name
            user_id: Optional user ID

        Returns:
            Dictionary with token and context, or empty dict if no token
        """
        token = self.get_token(provider, user_id)

        if not token:
            return {}

        # Determine source
        if user_id and self.token_storage:
            try:
                tokens = self.token_storage.get_token(provider, user_id)
                if tokens and "access_token" in tokens:
                    source = "user"
                else:
                    source = "bot"
            except:
                source = "bot"
        else:
            source = "bot"

        return {
            "token": token,
            "source": source,
            "user_id": user_id if source == "user" else None,
            "provider": provider
        }

    def store_token(
        self,
        provider: str,
        token: str,
        user_id: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Store a token in the token storage.

        Args:
            provider: Provider name
            token: Token string to store
            user_id: Optional user ID (required for user tokens)
            additional_data: Optional additional data (refresh_token, expires_at, etc.)

        Returns:
            True if stored successfully, False otherwise
        """
        if not self.token_storage:
            logger.error("Cannot store token: token_storage not available")
            return False

        if not user_id:
            logger.warning("Cannot store token without user_id")
            return False

        try:
            token_data = {"access_token": token}
            if additional_data:
                token_data.update(additional_data)

            self.token_storage.set_token(provider, user_id, token_data)
            logger.info(f"Stored token for {provider} user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to store token for {provider}: {e}")
            return False

    def invalidate_token(
        self,
        provider: str,
        user_id: str
    ) -> bool:
        """
        Invalidate/remove a token from storage.

        Args:
            provider: Provider name
            user_id: User ID

        Returns:
            True if invalidated successfully, False otherwise
        """
        if not self.token_storage:
            return False

        try:
            # Implementation depends on token_storage interface
            # Assuming there's a delete_token method or similar
            if hasattr(self.token_storage, 'delete_token'):
                self.token_storage.delete_token(provider, user_id)
            elif hasattr(self.token_storage, 'set_token'):
                self.token_storage.set_token(provider, user_id, {})

            logger.info(f"Invalidated token for {provider} user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to invalidate token for {provider}: {e}")
            return False

    def get_available_providers(self) -> list[str]:
        """
        Get list of providers with available tokens.

        Checks both environment variables and token storage.

        Returns:
            List of provider names that have tokens available
        """
        providers = set()

        # Check environment variables
        env_providers = ["SLACK", "GMAIL", "OUTLOOK", "MICROSOFT_365", "ZOHO"]
        for provider in env_providers:
            if os.getenv(f"{provider}_BOT_TOKEN") or os.getenv(f"{provider}_ACCESS_TOKEN"):
                providers.add(provider.lower())

        # Check token storage if available
        if self.token_storage and hasattr(self.token_storage, 'get_all_providers'):
            try:
                storage_providers = self.token_storage.get_all_providers()
                providers.update(storage_providers)
            except Exception as e:
                logger.debug(f"Could not get providers from token_storage: {e}")

        return list(providers)


# Global instance for convenience
_global_context_manager = None


def get_user_context_manager(db: Optional[Session] = None) -> UserContextManager:
    """
    Get the global user context manager instance.

    Args:
        db: Optional database session

    Returns:
        UserContextManager instance
    """
    global _global_context_manager

    if _global_context_manager is None:
        _global_context_manager = UserContextManager(db)
    elif db is not None:
        _global_context_manager.db = db

    return _global_context_manager
