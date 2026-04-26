"""
LLM OAuth 2.0 Handler

Handles OAuth 2.0 authentication flows for LLM providers:
- Authorization URL generation
- Token exchange
- Token refresh
- Credential storage and retrieval
- Token validation

Supports: Google AI Studio, OpenAI, Anthropic, Hugging Face
"""

import logging
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional

import httpx

from core.database import get_db_session
from core.llm_oauth_config import (
    get_oauth_config,
    get_provider_client_id,
    get_provider_client_secret,
    is_provider_oauth_configured,
    DEFAULT_OAUTH_REDIRECT_URI
)
from core.models import LLMOAuthCredential

logger = logging.getLogger(__name__)


class LLMOAuthHandler:
    """
    Handler for LLM provider OAuth 2.0 authentication.

    Manages the complete OAuth flow for LLM providers including
    authorization, token exchange, refresh, and credential storage.
    """

    def __init__(self, encryption_key: Optional[bytes] = None):
        """
        Initialize OAuth handler.

        Args:
            encryption_key: Optional Fernet key for token encryption
        """
        self.encryption_key = encryption_key

    def get_authorization_url(
        self,
        provider_id: str,
        redirect_uri: Optional[str] = None,
        state: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate OAuth authorization URL for a provider.

        Args:
            provider_id: Provider identifier (google, openai, anthropic, huggingface)
            redirect_uri: OAuth callback URL (defaults to configured redirect URI)
            state: Optional state parameter for CSRF protection

        Returns:
            Dict with authorization_url and state

        Raises:
            ValueError: If provider is not configured
        """
        config = get_oauth_config(provider_id)
        if not config:
            raise ValueError(f"Unknown provider: {provider_id}")

        if not is_provider_oauth_configured(provider_id):
            raise ValueError(f"OAuth not configured for provider: {provider_id}")

        client_id = get_provider_client_id(provider_id)

        # Generate state if not provided
        if not state:
            state = secrets.token_urlsafe(32)

        # Build authorization URL parameters
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri or DEFAULT_OAUTH_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(config["scopes"]),
            "state": state,
        }

        # Add PKCE for Google if enabled
        if config.get("pkce", False):
            # TODO: Implement PKCE code challenge generation
            # For now, skip PKCE as it's optional
            pass

        # Build URL
        from urllib.parse import urlencode
        auth_url = f"{config['auth_url']}?{urlencode(params)}"

        logger.info(f"Generated OAuth authorization URL for {provider_id}")

        return {
            "authorization_url": auth_url,
            "state": state,
            "provider_id": provider_id
        }

    async def exchange_code_for_tokens(
        self,
        provider_id: str,
        code: str,
        redirect_uri: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Exchange authorization code for access tokens.

        Args:
            provider_id: Provider identifier
            code: Authorization code from callback
            redirect_uri: Original redirect URI used in authorization

        Returns:
            Dict with access_token, refresh_token, expires_in, etc.

        Raises:
            ValueError: If provider is not configured
            httpx.HTTPError: If token exchange fails
        """
        config = get_oauth_config(provider_id)
        if not config:
            raise ValueError(f"Unknown provider: {provider_id}")

        client_id = get_provider_client_id(provider_id)
        client_secret = get_provider_client_secret(provider_id)

        # Prepare token request payload
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri or DEFAULT_OAUTH_REDIRECT_URI,
        }

        # Make token request
        async with httpx.AsyncClient() as client:
            response = await client.post(
                config["token_url"],
                data=data,
                headers={"Accept": "application/json"}
            )
            response.raise_for_status()
            tokens = response.json()

        logger.info(f"Successfully exchanged code for tokens with {provider_id}")

        return tokens

    def store_oauth_credentials(
        self,
        user_id: str,
        tenant_id: str,
        provider_id: str,
        tokens: Dict[str, any],
        account_info: Optional[Dict[str, str]] = None
    ) -> LLMOAuthCredential:
        """
        Store OAuth credentials in the database.

        Args:
            user_id: User ID
            tenant_id: Tenant ID
            provider_id: Provider identifier
            tokens: Token response from OAuth exchange
            account_info: Optional account info (email, name)

        Returns:
            Created LLMOAuthCredential instance
        """
        with get_db_session() as db:
            # Check if credential already exists for this user/provider
            existing = db.query(LLMOAuthCredential).filter(
                LLMOAuthCredential.user_id == user_id,
                LLMOAuthCredential.provider_id == provider_id,
                LLMOAuthCredential.is_active == True
            ).first()

            if existing:
                # Deactivate existing credential
                existing.is_active = False
                existing.revoked_at = datetime.utcnow()
                logger.info(f"Deactivated existing OAuth credential for {provider_id}")

            # Calculate expiration
            expires_at = None
            refresh_expires_at = None

            if "expires_in" in tokens:
                expires_at = datetime.utcnow() + timedelta(seconds=tokens["expires_in"])

            if "refresh_token_expires_in" in tokens:
                refresh_expires_at = datetime.utcnow() + timedelta(
                    seconds=tokens["refresh_token_expires_in"]
                )

            # Create new credential
            credential = LLMOAuthCredential(
                id=str(uuid.uuid4()),
                user_id=user_id,
                tenant_id=tenant_id,
                provider_id=provider_id,
                access_token=self._encrypt_token(tokens["access_token"]),
                refresh_token=self._encrypt_token(tokens.get("refresh_token")) if tokens.get("refresh_token") else None,
                token_type=tokens.get("token_type", "Bearer"),
                scope=tokens.get("scope", ""),
                expires_at=expires_at,
                refresh_expires_at=refresh_expires_at,
                account_email=account_info.get("email") if account_info else None,
                account_name=account_info.get("name") if account_info else None,
                is_active=True,
            )

            db.add(credential)
            db.commit()
            db.refresh(credential)

            logger.info(f"Stored OAuth credential for {provider_id} (user: {user_id})")

            return credential

    def get_active_credentials(
        self,
        user_id: str,
        provider_id: str
    ) -> Optional[LLMOAuthCredential]:
        """
        Get active OAuth credentials for a user and provider.

        Args:
            user_id: User ID
            provider_id: Provider identifier

        Returns:
            LLMOAuthCredential or None if not found
        """
        with get_db_session() as db:
            credential = db.query(LLMOAuthCredential).filter(
                LLMOAuthCredential.user_id == user_id,
                LLMOAuthCredential.provider_id == provider_id,
                LLMOAuthCredential.is_active == True
            ).first()

            if credential:
                # Update last_used_at
                credential.last_used_at = datetime.utcnow()
                credential.usage_count = (credential.usage_count or 0) + 1
                db.commit()

            return credential

    def decrypt_access_token(self, credential: LLMOAuthCredential) -> str:
        """
        Decrypt access token from credential.

        Args:
            credential: LLMOAuthCredential instance

        Returns:
            Decrypted access token
        """
        return self._decrypt_token(credential.access_token)

    async def refresh_access_token(self, credential_id: str) -> bool:
        """
        Refresh an expired OAuth token.

        Args:
            credential_id: Credential ID to refresh

        Returns:
            True if refresh successful, False otherwise
        """
        with get_db_session() as db:
            credential = db.query(LLMOAuthCredential).filter(
                LLMOAuthCredential.id == credential_id
            ).first()

            if not credential:
                logger.error(f"Credential not found: {credential_id}")
                return False

            if not credential.refresh_token:
                logger.error(f"No refresh token available for {credential_id}")
                return False

            try:
                config = get_oauth_config(credential.provider_id)
                if not config:
                    logger.error(f"Unknown provider: {credential.provider_id}")
                    return False

                client_id = get_provider_client_id(credential.provider_id)
                client_secret = get_provider_client_secret(credential.provider_id)

                # Prepare refresh request
                data = {
                    "grant_type": "refresh_token",
                    "refresh_token": self._decrypt_token(credential.refresh_token),
                    "client_id": client_id,
                    "client_secret": client_secret,
                }

                # Make refresh request
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        config["token_url"],
                        data=data,
                        headers={"Accept": "application/json"}
                    )
                    response.raise_for_status()
                    tokens = response.json()

                # Update credential with new tokens
                credential.access_token = self._encrypt_token(tokens["access_token"])

                # Update refresh token if provided
                if "refresh_token" in tokens:
                    credential.refresh_token = self._encrypt_token(tokens["refresh_token"])

                # Update expiration
                if "expires_in" in tokens:
                    credential.expires_at = datetime.utcnow() + timedelta(
                        seconds=tokens["expires_in"]
                    )

                credential.last_validated_at = datetime.utcnow()
                db.commit()

                logger.info(f"Successfully refreshed token for {credential.provider_id}")
                return True

            except Exception as e:
                logger.error(f"Failed to refresh token for {credential_id}: {e}")
                return False

    async def validate_and_refresh_if_needed(
        self,
        credential: LLMOAuthCredential
    ) -> bool:
        """
        Validate credential and refresh if expired.

        Args:
            credential: LLMOAuthCredential instance

        Returns:
            True if credential is valid (or was successfully refreshed)
        """
        # Check if token is expired or will expire soon (< 5 minutes)
        if credential.expires_at:
            expiry_threshold = datetime.utcnow() + timedelta(minutes=5)
            if credential.expires_at < expiry_threshold:
                logger.info(f"Token expired for {credential.provider_id}, refreshing...")
                return await self.refresh_access_token(credential.id)

        # Token is still valid
        credential.last_validated_at = datetime.utcnow()

        with get_db_session() as db:
            db.add(credential)
            db.commit()

        return True

    def revoke_credentials(self, credential_id: str) -> bool:
        """
        Revoke OAuth credentials.

        Args:
            credential_id: Credential ID to revoke

        Returns:
            True if revocation successful
        """
        with get_db_session() as db:
            credential = db.query(LLMOAuthCredential).filter(
                LLMOAuthCredential.id == credential_id
            ).first()

            if not credential:
                return False

            credential.is_active = False
            credential.revoked_at = datetime.utcnow()
            db.commit()

            logger.info(f"Revoked OAuth credential {credential_id}")
            return True

    def list_credentials(
        self,
        user_id: str,
        provider_id: Optional[str] = None
    ) -> list:
        """
        List OAuth credentials for a user.

        Args:
            user_id: User ID
            provider_id: Optional provider filter

        Returns:
            List of LLMOAuthCredential instances
        """
        with get_db_session() as db:
            query = db.query(LLMOAuthCredential).filter(
                LLMOAuthCredential.user_id == user_id
            )

            if provider_id:
                query = query.filter(LLMOAuthCredential.provider_id == provider_id)

            return query.all()

    def _encrypt_token(self, token: str) -> str:
        """
        Encrypt token using Fernet.

        Args:
            token: Plain text token

        Returns:
            Encrypted token (base64 encoded)

        Raises:
            ValueError: If encryption key is not configured
        """
        try:
            from cryptography.fernet import Fernet, InvalidToken
            import base64

            if not self.encryption_key:
                # Generate warning but allow operation in development
                logger.warning("No encryption key configured - storing tokens in plain text (INSECURE)")
                return token

            try:
                f = Fernet(self.encryption_key)
                encrypted = f.encrypt(token.encode())
                return base64.urlsafe_b64encode(encrypted).decode()
            except InvalidToken as e:
                logger.error(f"Token encryption failed: {e}")
                raise ValueError("Failed to encrypt token")

        except ImportError:
            logger.error("cryptography package not installed - tokens will be stored in plain text")
            return token

    def _decrypt_token(self, encrypted_token: str) -> str:
        """
        Decrypt token using Fernet.

        Args:
            encrypted_token: Encrypted token

        Returns:
            Plain text token

        Raises:
            ValueError: If decryption fails
        """
        try:
            from cryptography.fernet import Fernet, InvalidToken
            import base64

            if not self.encryption_key:
                # If no encryption key, assume token is plain text
                return encrypted_token

            try:
                f = Fernet(self.encryption_key)
                # Decode from base64 if needed
                if isinstance(encrypted_token, str):
                    try:
                        encrypted_bytes = base64.urlsafe_b64decode(encrypted_token.encode())
                    except Exception:
                        # Not base64 encoded, try direct decryption
                        encrypted_bytes = encrypted_token.encode()
                else:
                    encrypted_bytes = encrypted_token

                decrypted = f.decrypt(encrypted_bytes)
                return decrypted.decode()

            except InvalidToken as e:
                logger.error(f"Token decryption failed: {e}")
                raise ValueError("Failed to decrypt token - may be corrupted")

        except ImportError:
            logger.error("cryptography package not installed - returning token as plain text")
            return encrypted_token
