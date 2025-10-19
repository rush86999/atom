"""
Authentication Service for Atom Personal Assistant

This service provides unified authentication and OAuth management across multiple platforms:
- OAuth token management and refresh
- Secure credential storage
- Integration authentication flows
- Token lifecycle management
"""

import os
import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class AuthProvider(Enum):
    """Authentication provider enumeration"""

    GOOGLE = "google"
    OUTLOOK = "outlook"
    SLACK = "slack"
    MICROSOFT_TEAMS = "microsoft_teams"
    DISCORD = "discord"
    NOTION = "notion"
    TRELLO = "trello"
    ASANA = "asana"
    JIRA = "jira"
    GITHUB = "github"
    SALESFORCE = "salesforce"
    HUBSPOT = "hubspot"
    ZOHO = "zoho"
    SHOPIFY = "shopify"
    DROPBOX = "dropbox"
    BOX = "box"
    ONEDRIVE = "onedrive"
    GOOGLE_DRIVE = "google_drive"
    PLATFORM = "platform"  # For platform-specific auth


class AuthStatus(Enum):
    """Authentication status enumeration"""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING = "pending"
    FAILED = "failed"


class AuthService:
    """Service for authentication and OAuth management operations"""

    def __init__(self, db_pool=None):
        self.db_pool = db_pool
        self.provider_configs = self._load_provider_configs()

    async def get_auth_url(
        self,
        user_id: str,
        provider: str,
        scopes: List[str] = None,
        redirect_uri: str = None,
    ) -> Dict[str, Any]:
        """Generate OAuth authorization URL for a provider"""
        try:
            provider_config = self.provider_configs.get(provider)
            if not provider_config:
                raise ValueError(f"Provider {provider} not configured")

            # Generate state parameter for security
            state = self._generate_state_parameter(user_id, provider)

            # Build authorization URL
            auth_url = self._build_auth_url(
                provider_config, scopes, redirect_uri, state
            )

            # Store state for validation later
            await self._store_auth_state(user_id, provider, state, scopes, redirect_uri)

            return {
                "success": True,
                "auth_url": auth_url,
                "state": state,
                "provider": provider,
                "expires_in": 600,  # 10 minutes
            }

        except Exception as e:
            logger.error(f"Failed to generate auth URL for {provider}: {e}")
            return {"success": False, "error": str(e), "provider": provider}

    async def handle_oauth_callback(
        self,
        user_id: str,
        provider: str,
        code: str,
        state: str,
        redirect_uri: str = None,
    ) -> Dict[str, Any]:
        """Handle OAuth callback and exchange code for tokens"""
        try:
            # Validate state parameter
            if not await self._validate_auth_state(user_id, provider, state):
                raise ValueError("Invalid state parameter")

            provider_config = self.provider_configs.get(provider)
            if not provider_config:
                raise ValueError(f"Provider {provider} not configured")

            # Exchange code for tokens
            tokens = await self._exchange_code_for_tokens(
                provider_config, code, redirect_uri
            )

            # Store tokens securely
            token_data = await self._store_tokens(user_id, provider, tokens)

            # Clean up state
            await self._cleanup_auth_state(user_id, provider, state)

            return {
                "success": True,
                "provider": provider,
                "status": AuthStatus.ACTIVE.value,
                "scopes": tokens.get("scope", "").split(),
                "expires_at": token_data.get("expires_at"),
                "user_info": await self._get_user_info(provider, tokens),
            }

        except Exception as e:
            logger.error(f"Failed to handle OAuth callback for {provider}: {e}")
            return {"success": False, "error": str(e), "provider": provider}

    async def get_user_tokens(
        self, user_id: str, provider: str
    ) -> Optional[Dict[str, Any]]:
        """Get user's tokens for a specific provider"""
        try:
            tokens = await self._get_stored_tokens(user_id, provider)
            if not tokens:
                return None

            # Check if token needs refresh
            if await self._is_token_expired(tokens):
                refreshed_tokens = await self._refresh_tokens(user_id, provider, tokens)
                if refreshed_tokens:
                    tokens = refreshed_tokens

            return {
                "access_token": tokens.get("access_token"),
                "refresh_token": tokens.get("refresh_token"),
                "expires_at": tokens.get("expires_at"),
                "scope": tokens.get("scope"),
                "provider": provider,
                "status": AuthStatus.ACTIVE.value,
            }

        except Exception as e:
            logger.error(f"Failed to get tokens for {provider}: {e}")
            return None

    async def revoke_tokens(self, user_id: str, provider: str) -> bool:
        """Revoke and delete user's tokens for a provider"""
        try:
            tokens = await self._get_stored_tokens(user_id, provider)
            if tokens and tokens.get("access_token"):
                # Attempt to revoke token with provider
                await self._revoke_with_provider(provider, tokens.get("access_token"))

            # Delete tokens from storage
            await self._delete_tokens(user_id, provider)

            logger.info(f"Revoked tokens for {provider} for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to revoke tokens for {provider}: {e}")
            return False

    async def get_connected_services(self, user_id: str) -> List[Dict[str, Any]]:
        """Get list of all connected services for a user"""
        try:
            connected_services = []

            for provider in AuthProvider:
                tokens = await self._get_stored_tokens(user_id, provider.value)
                if tokens:
                    status = AuthStatus.ACTIVE.value
                    if await self._is_token_expired(tokens):
                        status = AuthStatus.EXPIRED.value

                    connected_services.append(
                        {
                            "provider": provider.value,
                            "status": status,
                            "connected_at": tokens.get("created_at"),
                            "scopes": tokens.get("scope", "").split(),
                            "expires_at": tokens.get("expires_at"),
                        }
                    )

            return connected_services

        except Exception as e:
            logger.error(f"Failed to get connected services: {e}")
            return []

    async def validate_token(self, user_id: str, provider: str) -> Dict[str, Any]:
        """Validate and refresh token if necessary"""
        try:
            tokens = await self._get_stored_tokens(user_id, provider)
            if not tokens:
                return {"valid": False, "status": "not_connected", "provider": provider}

            if await self._is_token_expired(tokens):
                refreshed = await self._refresh_tokens(user_id, provider, tokens)
                if refreshed:
                    return {
                        "valid": True,
                        "status": "refreshed",
                        "provider": provider,
                        "expires_at": refreshed.get("expires_at"),
                    }
                else:
                    return {
                        "valid": False,
                        "status": "refresh_failed",
                        "provider": provider,
                    }

            # Token is valid
            return {
                "valid": True,
                "status": "active",
                "provider": provider,
                "expires_at": tokens.get("expires_at"),
            }

        except Exception as e:
            logger.error(f"Failed to validate token for {provider}: {e}")
            return {
                "valid": False,
                "status": "validation_error",
                "error": str(e),
                "provider": provider,
            }

    def _load_provider_configs(self) -> Dict[str, Any]:
        """Load OAuth provider configurations"""
        # In production, these would come from environment variables or config files
        configs = {}

        # Google configuration
        configs[AuthProvider.GOOGLE.value] = {
            "auth_url": "https://accounts.google.com/o/oauth2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "scopes": [
                "https://www.googleapis.com/auth/calendar",
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/drive.readonly",
            ],
        }

        # Microsoft configuration
        configs[AuthProvider.OUTLOOK.value] = {
            "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            "client_id": os.getenv("MICROSOFT_CLIENT_ID"),
            "client_secret": os.getenv("MICROSOFT_CLIENT_SECRET"),
            "scopes": ["Calendars.Read", "Mail.Read", "User.Read"],
        }

        # Slack configuration
        configs[AuthProvider.SLACK.value] = {
            "auth_url": "https://slack.com/oauth/v2/authorize",
            "token_url": "https://slack.com/api/oauth.v2.access",
            "client_id": os.getenv("SLACK_CLIENT_ID"),
            "client_secret": os.getenv("SLACK_CLIENT_SECRET"),
            "scopes": ["channels:read", "channels:history", "chat:write"],
        }

        # Add more providers as needed...

        return configs

    def _generate_state_parameter(self, user_id: str, provider: str) -> str:
        """Generate secure state parameter for OAuth flow"""
        import secrets
        import hashlib

        random_bytes = secrets.token_bytes(32)
        state_data = f"{user_id}:{provider}:{random_bytes.hex()}"
        return hashlib.sha256(state_data.encode()).hexdigest()

    def _build_auth_url(
        self,
        provider_config: Dict[str, Any],
        scopes: List[str],
        redirect_uri: str,
        state: str,
    ) -> str:
        """Build OAuth authorization URL"""
        from urllib.parse import urlencode

        params = {
            "client_id": provider_config["client_id"],
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes or provider_config["scopes"]),
            "state": state,
            "access_type": "offline",  # For refresh tokens
            "prompt": "consent",  # Force consent screen for refresh token
        }

        return f"{provider_config['auth_url']}?{urlencode(params)}"

    async def _exchange_code_for_tokens(
        self, provider_config: Dict[str, Any], code: str, redirect_uri: str
    ) -> Dict[str, Any]:
        """Exchange authorization code for access tokens"""
        import requests

        data = {
            "client_id": provider_config["client_id"],
            "client_secret": provider_config["client_secret"],
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }

        response = requests.post(provider_config["token_url"], data=data)
        response.raise_for_status()

        return response.json()

    async def _refresh_tokens(
        self, user_id: str, provider: str, tokens: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Refresh expired access tokens"""
        try:
            provider_config = self.provider_configs.get(provider)
            if not provider_config:
                return None

            refresh_token = tokens.get("refresh_token")
            if not refresh_token:
                return None

            import requests

            data = {
                "client_id": provider_config["client_id"],
                "client_secret": provider_config["client_secret"],
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }

            response = requests.post(provider_config["token_url"], data=data)
            response.raise_for_status()

            new_tokens = response.json()

            # Update tokens in storage
            updated_tokens = await self._update_tokens(user_id, provider, new_tokens)

            return updated_tokens

        except Exception as e:
            logger.error(f"Failed to refresh tokens for {provider}: {e}")
            return None

    async def _get_user_info(
        self, provider: str, tokens: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get user information from provider"""
        try:
            access_token = tokens.get("access_token")
            if not access_token:
                return {}

            import requests

            # Provider-specific user info endpoints
            user_info_endpoints = {
                AuthProvider.GOOGLE.value: "https://www.googleapis.com/oauth2/v3/userinfo",
                AuthProvider.OUTLOOK.value: "https://graph.microsoft.com/v1.0/me",
                AuthProvider.SLACK.value: "https://slack.com/api/users.identity",
            }

            endpoint = user_info_endpoints.get(provider)
            if not endpoint:
                return {}

            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(endpoint, headers=headers)
            response.raise_for_status()

            return response.json()

        except Exception as e:
            logger.error(f"Failed to get user info from {provider}: {e}")
            return {}

    async def _revoke_with_provider(self, provider: str, access_token: str) -> bool:
        """Revoke token with provider"""
        try:
            import requests

            revoke_endpoints = {
                AuthProvider.GOOGLE.value: "https://oauth2.googleapis.com/revoke",
                AuthProvider.OUTLOOK.value: "https://graph.microsoft.com/v1.0/me/revokeSignInSessions",
            }

            endpoint = revoke_endpoints.get(provider)
            if not endpoint:
                return True  # No revocation endpoint, consider it successful

            data = {"token": access_token}
            response = requests.post(endpoint, data=data)

            # Some providers return 200, others might have different success codes
            return response.status_code in [200, 204]

        except Exception as e:
            logger.error(f"Failed to revoke token with {provider}: {e}")
            return False

    def _is_token_expired(self, tokens: Dict[str, Any]) -> bool:
        """Check if token is expired or about to expire"""
        expires_at = tokens.get("expires_at")
        if not expires_at:
            return True

        try:
            expiry_time = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            # Consider token expired if it expires in less than 5 minutes
            return expiry_time < (datetime.now() + timedelta(minutes=5))
        except Exception:
            return True

    # Database operations (to be implemented based on actual database schema)

    async def _store_auth_state(
        self,
        user_id: str,
        provider: str,
        state: str,
        scopes: List[str],
        redirect_uri: str,
    ):
        """Store OAuth state for validation"""
        # Implementation depends on database schema
        pass

    async def _validate_auth_state(
        self, user_id: str, provider: str, state: str
    ) -> bool:
        """Validate OAuth state parameter"""
        # Implementation depends on database schema
        return True

    async def _cleanup_auth_state(self, user_id: str, provider: str, state: str):
        """Clean up OAuth state after use"""
        # Implementation depends on database schema
        pass

    async def _store_tokens(
        self, user_id: str, provider: str, tokens: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Store OAuth tokens securely"""
        # Implementation depends on database schema and encryption
        expires_in = tokens.get("expires_in", 3600)
        expires_at = (datetime.now() + timedelta(seconds=expires_in)).isoformat()

        token_data = {
            "user_id": user_id,
            "provider": provider,
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "scope": tokens.get("scope"),
            "expires_at": expires_at,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        return token_data

    async def _get_stored_tokens(
        self, user_id: str, provider: str
    ) -> Optional[Dict[str, Any]]:
        """Get stored OAuth tokens"""
        # Implementation depends on database schema
        return None

    async def _update_tokens(
        self, user_id: str, provider: str, tokens: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update stored OAuth tokens"""
        # Implementation depends on database schema
        return await self._store_tokens(user_id, provider, tokens)

    async def _delete_tokens(self, user_id: str, provider: str):
        """Delete stored OAuth tokens"""
        # Implementation depends on database schema
        pass
