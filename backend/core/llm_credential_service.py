"""
LLM Credential Resolution Service

Unified interface for resolving LLM provider credentials with fallback priority:
1. OAuth Token (active and not expired)
2. Refresh OAuth Token (if expired but has refresh token)
3. BYOK API Key
4. Environment Variable

This service provides a single point of credential resolution for the BYOKHandler
and other LLM consumers.
"""

import logging
import os
from typing import Optional, Tuple

from core.byok_endpoints import get_byok_manager
from core.database import get_db_session
from core.llm_oauth_handler import LLMOAuthHandler
from core.models import LLMOAuthCredential

logger = logging.getLogger(__name__)


class LLMCredentialService:
    """
    Unified credential resolution service for LLM providers.

    Implements the fallback priority:
    1. OAuth Token (with auto-refresh)
    2. BYOK API Key
    3. Environment Variable
    """

    def __init__(
        self,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        encryption_key: Optional[bytes] = None
    ):
        """
        Initialize credential service.

        Args:
            user_id: User ID for OAuth credentials
            tenant_id: Tenant ID for OAuth credentials and BYOK
            workspace_id: Workspace ID for BYOK credentials
            encryption_key: Optional encryption key for OAuth tokens
        """
        self.user_id = user_id or "default"
        self.tenant_id = tenant_id or "default"
        self.workspace_id = workspace_id or "default"

        self.oauth_handler = LLMOAuthHandler(encryption_key=encryption_key)
        self.byok_manager = get_byok_manager()

    async def get_credential(
        self,
        provider_id: str
    ) -> Tuple[str, str]:
        """
        Get credential for a provider using fallback priority.

        Priority:
        1. Active OAuth token (with auto-refresh if expired)
        2. BYOK API key
        3. Environment variable

        Args:
            provider_id: Provider identifier (google, openai, anthropic, huggingface)

        Returns:
            Tuple of (credential_type, credential_value)
            credential_type is one of: "oauth", "byok", "env"

        Raises:
            ValueError: If no credential is available
        """
        # Try OAuth first
        oauth_token = await self._try_oauth_credential(provider_id)
        if oauth_token:
            logger.debug(f"Using OAuth credential for {provider_id}")
            return ("oauth", oauth_token)

        # Try BYOK
        byok_key = self._try_byok_credential(provider_id)
        if byok_key:
            logger.debug(f"Using BYOK credential for {provider_id}")
            return ("byok", byok_key)

        # Try environment variable
        env_key = self._try_env_credential(provider_id)
        if env_key:
            logger.debug(f"Using ENV credential for {provider_id}")
            return ("env", env_key)

        raise ValueError(
            f"No credential available for provider '{provider_id}'. "
            f"Please configure OAuth, BYOK, or environment variable."
        )

    async def _try_oauth_credential(self, provider_id: str) -> Optional[str]:
        """
        Try to get active OAuth credential for provider.

        Args:
            provider_id: Provider identifier

        Returns:
            Access token if available and valid, None otherwise
        """
        if not self.user_id:
            return None

        try:
            # Get active credential
            credential = self.oauth_handler.get_active_credentials(
                self.user_id, provider_id
            )

            if not credential:
                logger.debug(f"No OAuth credential found for {provider_id}")
                return None

            # Validate and refresh if needed
            is_valid = await self.oauth_handler.validate_and_refresh_if_needed(credential)

            if not is_valid:
                logger.warning(f"OAuth credential invalid for {provider_id}")
                return None

            # Decrypt and return access token
            access_token = self.oauth_handler.decrypt_access_token(credential)
            logger.info(f"Using OAuth credential for {provider_id} (user: {self.user_id})")

            return access_token

        except Exception as e:
            logger.error(f"Error getting OAuth credential for {provider_id}: {e}")
            return None

    def _try_byok_credential(self, provider_id: str) -> Optional[str]:
        """
        Try to get BYOK API key for provider.

        Args:
            provider_id: Provider identifier

        Returns:
            API key if available, None otherwise
        """
        try:
            # Try tenant-level BYOK first
            if self.tenant_id and self.tenant_id != "default":
                tenant_key = self.byok_manager.get_tenant_api_key(
                    self.tenant_id, provider_id
                )
                if tenant_key:
                    logger.debug(f"Using tenant BYOK key for {provider_id}")
                    return tenant_key

            # Try workspace-level BYOK
            if self.byok_manager.is_configured(self.workspace_id, provider_id):
                api_key = self.byok_manager.get_api_key(provider_id)
                if api_key:
                    logger.debug(f"Using workspace BYOK key for {provider_id}")
                    return api_key

            return None

        except Exception as e:
            logger.error(f"Error getting BYOK credential for {provider_id}: {e}")
            return None

    def _try_env_credential(self, provider_id: str) -> Optional[str]:
        """
        Try to get API key from environment variables.

        Args:
            provider_id: Provider identifier

        Returns:
            API key if available, None otherwise
        """
        try:
            # Standard env var pattern: {PROVIDER}_API_KEY
            env_var = f"{provider_id.upper()}_API_KEY"
            api_key = os.getenv(env_var)

            # Special case: Gemini can use GOOGLE_API_KEY
            if not api_key and provider_id == "gemini":
                api_key = os.getenv("GOOGLE_API_KEY")

            if api_key:
                logger.debug(f"Using ENV var {env_var} for {provider_id}")
                return api_key

            return None

        except Exception as e:
            logger.error(f"Error getting ENV credential for {provider_id}: {e}")
            return None

    async def get_oauth_credential_info(
        self,
        provider_id: str
    ) -> Optional[dict]:
        """
        Get OAuth credential information without exposing tokens.

        Args:
            provider_id: Provider identifier

        Returns:
            Dict with credential info or None if not found
        """
        if not self.user_id:
            return None

        try:
            credential = self.oauth_handler.get_active_credentials(
                self.user_id, provider_id
            )

            if not credential:
                return None

            return {
                "credential_id": credential.id,
                "provider_id": credential.provider_id,
                "account_email": credential.account_email,
                "account_name": credential.account_name,
                "is_active": credential.is_active,
                "expires_at": credential.expires_at.isoformat() if credential.expires_at else None,
                "last_used_at": credential.last_used_at.isoformat() if credential.last_used_at else None,
                "usage_count": credential.usage_count,
                "created_at": credential.created_at.isoformat() if credential.created_at else None,
            }

        except Exception as e:
            logger.error(f"Error getting OAuth credential info: {e}")
            return None

    def list_oauth_credentials(self) -> list:
        """
        List all OAuth credentials for the user.

        Returns:
            List of credential info dicts
        """
        if not self.user_id:
            return []

        try:
            credentials = self.oauth_handler.list_credentials(self.user_id)

            return [
                {
                    "credential_id": c.id,
                    "provider_id": c.provider_id,
                    "account_email": c.account_email,
                    "account_name": c.account_name,
                    "is_active": c.is_active,
                    "expires_at": c.expires_at.isoformat() if c.expires_at else None,
                    "last_used_at": c.last_used_at.isoformat() if c.last_used_at else None,
                    "usage_count": c.usage_count,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in credentials
            ]

        except Exception as e:
            logger.error(f"Error listing OAuth credentials: {e}")
            return []

    def revoke_oauth_credential(self, credential_id: str) -> bool:
        """
        Revoke an OAuth credential.

        Args:
            credential_id: Credential ID to revoke

        Returns:
            True if revocation successful
        """
        try:
            return self.oauth_handler.revoke_credentials(credential_id)
        except Exception as e:
            logger.error(f"Error revoking OAuth credential: {e}")
            return False

    async def refresh_oauth_credential(self, credential_id: str) -> bool:
        """
        Refresh an OAuth credential.

        Args:
            credential_id: Credential ID to refresh

        Returns:
            True if refresh successful
        """
        try:
            return await self.oauth_handler.refresh_access_token(credential_id)
        except Exception as e:
            logger.error(f"Error refreshing OAuth credential: {e}")
            return False

    def get_provider_status(self, provider_id: str) -> dict:
        """
        Get credential status for a provider.

        Args:
            provider_id: Provider identifier

        Returns:
            Dict with status information
        """
        status = {
            "provider_id": provider_id,
            "has_oauth": False,
            "has_byok": False,
            "has_env": False,
            "active_method": None,
        }

        # Check OAuth
        if self.user_id:
            try:
                credential = self.oauth_handler.get_active_credentials(
                    self.user_id, provider_id
                )
                if credential:
                    status["has_oauth"] = True
                    status["oauth_info"] = {
                        "account_email": credential.account_email,
                        "expires_at": credential.expires_at.isoformat() if credential.expires_at else None,
                    }
            except Exception as e:
                logger.debug(f"Error checking OAuth status: {e}")

        # Check BYOK
        try:
            if self.byok_manager.is_configured(self.workspace_id, provider_id):
                status["has_byok"] = True
        except Exception as e:
            logger.debug(f"Error checking BYOK status: {e}")

        # Check ENV
        env_var = f"{provider_id.upper()}_API_KEY"
        if os.getenv(env_var):
            status["has_env"] = True

        # Determine active method
        if status["has_oauth"]:
            status["active_method"] = "oauth"
        elif status["has_byok"]:
            status["active_method"] = "byok"
        elif status["has_env"]:
            status["active_method"] = "env"

        return status
