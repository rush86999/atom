#!/usr/bin/env python3
"""
🚀 Salesforce OAuth 2.0 Authentication Handler
Enterprise-grade Salesforce integration with comprehensive OAuth flow
"""

import os
import json
import urllib.parse
import hashlib
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass

import requests
import asyncpg
from flask import Blueprint, request, jsonify, session, redirect

logger = logging.getLogger(__name__)

# Salesforce OAuth Configuration
SALESFORCE_AUTH_URL = "https://login.salesforce.com/services/oauth2/authorize"
SALESFORCE_TOKEN_URL = "https://login.salesforce.com/services/oauth2/token"
SALESFORCE_REVOKE_URL = "https://login.salesforce.com/services/oauth2/revoke"

# Required Salesforce API Scopes
SALESFORCE_SCOPES = [
    "api",  # Full API access
    "refresh_token",  # Token refresh capability
    "offline_access",  # Offline access
]

SALESFORCE_REQUIRED_FIELDS = [
    "id",
    "email",
    "name",
    "username",
    "organization_id",
    "profile_id",
]


@dataclass
class SalesforceOAuthConfig:
    """Salesforce OAuth configuration"""

    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: list
    environment: str = "production"  # production or sandbox
    auth_url: str = SALESFORCE_AUTH_URL
    token_url: str = SALESFORCE_TOKEN_URL


@dataclass
class SalesforceTokenInfo:
    """Salesforce OAuth token information"""

    access_token: str
    refresh_token: str
    instance_url: str
    user_id: str
    organization_id: str
    issued_at: datetime
    expires_at: datetime
    token_type: str = "Bearer"
    scope: str = ""
    profile_id: str = ""
    username: str = ""


class SalesforceOAuthHandler:
    """Enterprise-grade Salesforce OAuth handler"""

    def __init__(self, db_pool: asyncpg.Pool = None):
        self.db_pool = db_pool
        self.config = self._load_config()
        self._validate_config()

    def _load_config(self) -> SalesforceOAuthConfig:
        """Load Salesforce OAuth configuration"""
        try:
            # Environment check for sandbox
            environment = os.getenv("SALESFORCE_ENVIRONMENT", "production")
            if environment == "sandbox":
                auth_url = "https://test.salesforce.com/services/oauth2/authorize"
                token_url = "https://test.salesforce.com/services/oauth2/token"
            else:
                auth_url = SALESFORCE_AUTH_URL
                token_url = SALESFORCE_TOKEN_URL

            config = SalesforceOAuthConfig(
                client_id=os.getenv("SALESFORCE_CLIENT_ID", ""),
                client_secret=os.getenv("SALESFORCE_CLIENT_SECRET", ""),
                redirect_uri=os.getenv(
                    "SALESFORCE_REDIRECT_URI",
                    "http://localhost:3000/oauth/salesforce/callback",
                ),
                scopes=SALESFORCE_SCOPES,
                environment=environment,
                auth_url=auth_url,
                token_url=token_url,
            )

            return config

        except Exception as e:
            logger.error(f"Failed to load Salesforce OAuth config: {e}")
            raise ValueError(f"Salesforce OAuth configuration error: {e}")

    def _validate_config(self) -> None:
        """Validate Salesforce OAuth configuration"""
        if not self.config.client_id or self.config.client_id.startswith(
            ("YOUR_", "mock_")
        ):
            raise ValueError("SALESFORCE_CLIENT_ID is required and must be valid")

        if not self.config.client_secret or self.config.client_secret.startswith(
            ("YOUR_", "mock_")
        ):
            raise ValueError("SALESFORCE_CLIENT_SECRET is required and must be valid")

        if not self.config.redirect_uri:
            raise ValueError("SALESFORCE_REDIRECT_URI is required")

    def get_oauth_url(
        self, user_id: Optional[str] = None, state: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate Salesforce OAuth authorization URL

        Args:
            user_id: Optional user identifier
            state: Optional state parameter for security

        Returns:
            Dictionary with authorization URL and metadata
        """
        try:
            # Generate secure state if not provided
            if not state:
                state = self._generate_state()
                if self.db_pool and user_id:
                    self._store_state(user_id, state)

            # Build OAuth parameters
            params = {
                "response_type": "code",
                "client_id": self.config.client_id,
                "redirect_uri": self.config.redirect_uri,
                "scope": " ".join(self.config.scopes),
                "state": state,
                "prompt": "consent",  # Force consent for comprehensive access
            }

            # Generate authorization URL
            auth_url = f"{SALESFORCE_AUTH_URL}?{urllib.parse.urlencode(params)}"

            logger.info(f"Generated Salesforce OAuth URL for user: {user_id}")

            return {
                "ok": True,
                "authorization_url": auth_url,
                "state": state,
                "provider": "salesforce",
                "environment": self.config.environment,
                "client_id": self.config.client_id[:10]
                + "...",  # Partial ID for security
                "redirect_uri": self.config.redirect_uri,
                "expires_in": 600,  # URL expires in 10 minutes
            }

        except Exception as e:
            logger.error(f"Failed to generate Salesforce OAuth URL: {e}")
            return {
                "ok": False,
                "error": "oauth_url_generation_failed",
                "message": f"Failed to generate authorization URL: {str(e)}",
                "provider": "salesforce",
            }

    def exchange_code_for_token(self, code: str, state: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token

        Args:
            code: Authorization code from Salesforce
            state: State parameter for security validation

        Returns:
            Dictionary with token information
        """
        try:
            # Validate state if database is available
            if self.db_pool:
                state_validation = self._validate_state(state)
                if not state_validation["valid"]:
                    return {
                        "ok": False,
                        "error": "invalid_state",
                        "message": "Invalid or expired state parameter",
                        "provider": "salesforce",
                    }

            # Prepare token request
            token_data = {
                "grant_type": "authorization_code",
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "redirect_uri": self.config.redirect_uri,
                "code": code,
            }

            # Request token from Salesforce
            response = requests.post(
                SALESFORCE_TOKEN_URL,
                data=token_data,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=30,
            )

            if response.status_code != 200:
                error_data = (
                    response.json()
                    if response.headers.get("content-type", "").startswith(
                        "application/json"
                    )
                    else {}
                )
                error_message = error_data.get(
                    "error_description", error_data.get("error", "Unknown error")
                )

                logger.error(
                    f"Salesforce token exchange failed: {response.status_code} - {error_message}"
                )

                return {
                    "ok": False,
                    "error": "token_exchange_failed",
                    "message": f"Token exchange failed: {error_message}",
                    "status_code": response.status_code,
                    "provider": "salesforce",
                }

            token_response = response.json()

            # Calculate expiration time
            issued_at = datetime.now(timezone.utc)
            expires_in = token_response.get("expires_in", 3600)
            expires_at = issued_at + timedelta(seconds=expires_in)

            # Parse issued_at timestamp from Salesforce (milliseconds since epoch)
            sf_issued_at = token_response.get("issued_at", 0)
            if sf_issued_at:
                sf_issued_time = datetime.fromtimestamp(
                    sf_issued_at / 1000, tz=timezone.utc
                )
                # Use the later of our issued_at and Salesforce's issued_at
                issued_at = max(issued_at, sf_issued_time)

            # Create token info object
            token_info = SalesforceTokenInfo(
                access_token=token_response["access_token"],
                refresh_token=token_response.get("refresh_token", ""),
                instance_url=token_response["instance_url"],
                user_id=token_response["id"],
                organization_id=token_response.get("organization_id", ""),
                issued_at=issued_at,
                expires_at=expires_at,
                token_type=token_response.get("token_type", "Bearer"),
                scope=token_response.get("scope", ""),
                profile_id=token_response.get("profile_id", ""),
                username=token_response.get("username", ""),
            )

            # Get user information
            user_info = self._get_user_info(token_info)

            logger.info(
                f"Successfully exchanged Salesforce OAuth code for user: {token_info.user_id}"
            )

            return {
                "ok": True,
                "tokens": {
                    "access_token": token_info.access_token,
                    "refresh_token": token_info.refresh_token,
                    "instance_url": token_info.instance_url,
                    "token_type": token_info.token_type,
                    "scope": token_info.scope,
                    "expires_in": expires_in,
                    "issued_at": issued_at.isoformat(),
                    "expires_at": expires_at.isoformat(),
                },
                "user_info": {
                    "id": token_info.user_id,
                    "username": token_info.username,
                    "organization_id": token_info.organization_id,
                    "profile_id": token_info.profile_id,
                    "instance_url": token_info.instance_url,
                    "environment": self.config.environment,
                },
                "additional_info": user_info,
                "provider": "salesforce",
                "stored": False,  # Will be updated when stored in database
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Salesforce token request failed: {e}")
            return {
                "ok": False,
                "error": "network_error",
                "message": f"Network error during token exchange: {str(e)}",
                "provider": "salesforce",
            }
        except Exception as e:
            logger.error(f"Unexpected error in Salesforce token exchange: {e}")
            return {
                "ok": False,
                "error": "token_exchange_error",
                "message": f"Unexpected error during token exchange: {str(e)}",
                "provider": "salesforce",
            }

    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh access token using refresh token

        Args:
            refresh_token: Valid refresh token

        Returns:
            Dictionary with new token information
        """
        try:
            token_data = {
                "grant_type": "refresh_token",
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "refresh_token": refresh_token,
            }

            response = requests.post(
                SALESFORCE_TOKEN_URL,
                data=token_data,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=30,
            )

            if response.status_code != 200:
                error_data = (
                    response.json()
                    if response.headers.get("content-type", "").startswith(
                        "application/json"
                    )
                    else {}
                )
                error_message = error_data.get(
                    "error_description", error_data.get("error", "Unknown error")
                )

                logger.error(
                    f"Salesforce token refresh failed: {response.status_code} - {error_message}"
                )

                return {
                    "ok": False,
                    "error": "token_refresh_failed",
                    "message": f"Token refresh failed: {error_message}",
                    "provider": "salesforce",
                }

            token_response = response.json()

            # Calculate new expiration
            issued_at = datetime.now(timezone.utc)
            expires_in = token_response.get("expires_in", 3600)
            expires_at = issued_at + timedelta(seconds=expires_in)

            logger.info(f"Successfully refreshed Salesforce token")

            return {
                "ok": True,
                "tokens": {
                    "access_token": token_response["access_token"],
                    "refresh_token": token_response.get(
                        "refresh_token", refresh_token
                    ),  # Use new or existing
                    "instance_url": token_response.get("instance_url", ""),
                    "token_type": token_response.get("token_type", "Bearer"),
                    "scope": token_response.get("scope", ""),
                    "expires_in": expires_in,
                    "issued_at": issued_at.isoformat(),
                    "expires_at": expires_at.isoformat(),
                },
                "provider": "salesforce",
            }

        except Exception as e:
            logger.error(f"Salesforce token refresh error: {e}")
            return {
                "ok": False,
                "error": "token_refresh_error",
                "message": f"Error during token refresh: {str(e)}",
                "provider": "salesforce",
            }

    def revoke_token(self, access_token: str) -> Dict[str, Any]:
        """
        Revoke Salesforce access token

        Args:
            access_token: Access token to revoke

        Returns:
            Dictionary with revocation result
        """
        try:
            token_data = {"token": access_token}

            response = requests.post(
                SALESFORCE_REVOKE_URL,
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )

            # Salesforce returns 200 on successful revocation
            success = response.status_code == 200

            if success:
                logger.info("Successfully revoked Salesforce token")
            else:
                logger.warning(
                    f"Salesforce token revocation failed: {response.status_code}"
                )

            return {
                "ok": success,
                "message": "Token revoked successfully"
                if success
                else "Token revocation failed",
                "status_code": response.status_code,
                "provider": "salesforce",
            }

        except Exception as e:
            logger.error(f"Salesforce token revocation error: {e}")
            return {
                "ok": False,
                "error": "token_revocation_error",
                "message": f"Error during token revocation: {str(e)}",
                "provider": "salesforce",
            }

    def _get_user_info(self, token_info: SalesforceTokenInfo) -> Dict[str, Any]:
        """
        Get additional user information from Salesforce

        Args:
            token_info: Valid token information

        Returns:
            Dictionary with user information
        """
        try:
            # Use Salesforce Identity service to get user info
            identity_url = f"{token_info.instance_url}/services/oauth2/userinfo"

            headers = {
                "Authorization": f"Bearer {token_info.access_token}",
                "Accept": "application/json",
            }

            response = requests.get(identity_url, headers=headers, timeout=30)

            if response.status_code == 200:
                user_data = response.json()
                return {
                    "ok": True,
                    "user_data": {
                        "user_id": user_data.get("user_id"),
                        "organization_id": user_data.get("organization_id"),
                        "username": user_data.get("username"),
                        "email": user_data.get("email"),
                        "name": user_data.get("display_name"),
                        "profile_id": user_data.get("profile_id"),
                        "timezone": user_data.get("timezone"),
                        "locale": user_data.get("locale"),
                        "active": user_data.get("active", True),
                    },
                }
            else:
                logger.warning(
                    f"Failed to get Salesforce user info: {response.status_code}"
                )
                return {"ok": False, "error": "user_info_failed"}

        except Exception as e:
            logger.error(f"Error getting Salesforce user info: {e}")
            return {"ok": False, "error": "user_info_error"}

    def _generate_state(self) -> str:
        """Generate secure state parameter"""
        return secrets.token_urlsafe(32)

    async def _store_state(self, user_id: str, state: str) -> None:
        """Store state parameter for validation"""
        try:
            if not self.db_pool:
                return

            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO oauth_states (user_id, provider, state, expires_at, created_at)
                    VALUES ($1, 'salesforce', $2, $3, $4)
                    ON CONFLICT (user_id, provider)
                    DO UPDATE SET
                        state = EXCLUDED.state,
                        expires_at = EXCLUDED.expires_at,
                        created_at = EXCLUDED.created_at
                    """,
                    user_id,
                    state,
                    datetime.now(timezone.utc)
                    + timedelta(minutes=10),  # 10 minute expiration
                    datetime.now(timezone.utc),
                )

        except Exception as e:
            logger.error(f"Failed to store Salesforce OAuth state: {e}")

    async def _validate_state(self, state: str) -> Dict[str, Any]:
        """Validate state parameter"""
        try:
            if not self.db_pool:
                return {"valid": True}  # Skip validation if no database

            async with self.db_pool.acquire() as conn:
                result = await conn.fetchrow(
                    """
                    SELECT user_id, expires_at FROM oauth_states
                    WHERE provider = 'salesforce' AND state = $1
                    """,
                    state,
                )

                if not result:
                    return {"valid": False, "error": "state_not_found"}

                if result["expires_at"] < datetime.now(timezone.utc):
                    return {"valid": False, "error": "state_expired"}

                # Clean up used state
                await conn.execute(
                    """
                    DELETE FROM oauth_states
                    WHERE provider = 'salesforce' AND state = $1
                    """,
                    state,
                )

                return {"valid": True, "user_id": result["user_id"]}

        except Exception as e:
            logger.error(f"Failed to validate Salesforce OAuth state: {e}")
            return {"valid": False, "error": "state_validation_error"}


# Flask Blueprint for Salesforce OAuth
salesforce_auth_bp = Blueprint("salesforce_auth", __name__)

# Global OAuth handler (will be initialized with database pool)
salesforce_oauth_handler = None


def init_salesforce_oauth_handler(db_pool: asyncpg.Pool):
    """Initialize Salesforce OAuth handler with database pool"""
    global salesforce_oauth_handler
    salesforce_oauth_handler = SalesforceOAuthHandler(db_pool)


@salesforce_auth_bp.route("/salesforce/authorize", methods=["GET"])
def salesforce_authorize():
    """Initiate Salesforce OAuth flow"""
    user_id = request.args.get("user_id")
    state = request.args.get("state")

    if not salesforce_oauth_handler:
        return jsonify(
            {
                "ok": False,
                "error": "service_not_initialized",
                "message": "Salesforce OAuth handler not initialized",
            }
        ), 503

    result = salesforce_oauth_handler.get_oauth_url(user_id, state)

    if result.get("ok"):
        return jsonify(result)
    else:
        return jsonify(result), 400


@salesforce_auth_bp.route("/salesforce/callback", methods=["POST"])
def salesforce_callback():
    """Handle Salesforce OAuth callback"""
    data = request.get_json()
    code = data.get("code")
    state = data.get("state")

    if not code:
        return jsonify(
            {
                "ok": False,
                "error": "authorization_code_required",
                "message": "Authorization code is required",
                "provider": "salesforce",
            }
        ), 400

    if not salesforce_oauth_handler:
        return jsonify(
            {
                "ok": False,
                "error": "service_not_initialized",
                "message": "Salesforce OAuth handler not initialized",
            }
        ), 503

    result = salesforce_oauth_handler.exchange_code_for_token(code, state)

    if result.get("ok"):
        # Store tokens in database (implementation in db_oauth_salesforce.py)
        try:
            from db_oauth_salesforce import store_salesforce_tokens

            if salesforce_oauth_handler.db_pool:
                user_info = result.get("user_info", {})
                tokens = result.get("tokens", {})

                user_id = user_info.get("id")
                if user_id:
                    from datetime import datetime, timezone, timedelta

                    expires_in = tokens.get("expires_in", 3600)
                    expires_at = datetime.now(timezone.utc) + timedelta(
                        seconds=expires_in
                    )

                    store_result = asyncio.run(
                        store_salesforce_tokens(
                            salesforce_oauth_handler.db_pool,
                            user_id,
                            tokens.get("access_token"),
                            tokens.get("refresh_token"),
                            expires_at,
                            tokens.get("scope"),
                            user_info.get("organization_id"),
                            user_info.get("profile_id"),
                            user_info.get("instance_url"),
                            user_info.get("username"),
                            user_info.get("environment"),
                        )
                    )

                    if store_result.get("success"):
                        result["stored"] = True
                    else:
                        logger.error(
                            f"Failed to store Salesforce tokens: {store_result.get('error')}"
                        )
                        result["stored"] = False
        except Exception as e:
            logger.error(f"Error storing Salesforce tokens: {e}")
            result["stored"] = False

    return jsonify(result)


@salesforce_auth_bp.route("/salesforce/refresh", methods=["POST"])
def salesforce_refresh():
    """Refresh Salesforce access token"""
    data = request.get_json()
    refresh_token = data.get("refresh_token")

    if not refresh_token:
        return jsonify(
            {
                "ok": False,
                "error": "refresh_token_required",
                "message": "Refresh token is required",
                "provider": "salesforce",
            }
        ), 400

    if not salesforce_oauth_handler:
        return jsonify(
            {
                "ok": False,
                "error": "service_not_initialized",
                "message": "Salesforce OAuth handler not initialized",
            }
        ), 503

    result = salesforce_oauth_handler.refresh_token(refresh_token)

    return jsonify(result)


@salesforce_auth_bp.route("/salesforce/revoke", methods=["POST"])
def salesforce_revoke():
    """Revoke Salesforce access token"""
    data = request.get_json()
    access_token = data.get("access_token")

    if not access_token:
        return jsonify(
            {
                "ok": False,
                "error": "access_token_required",
                "message": "Access token is required",
                "provider": "salesforce",
            }
        ), 400

    if not salesforce_oauth_handler:
        return jsonify(
            {
                "ok": False,
                "error": "service_not_initialized",
                "message": "Salesforce OAuth handler not initialized",
            }
        ), 503

    result = salesforce_oauth_handler.revoke_token(access_token)

    return jsonify(result)


@salesforce_auth_bp.route("/salesforce/health", methods=["GET"])
def salesforce_health():
    """Health check for Salesforce OAuth service"""
    if not salesforce_oauth_handler:
        return jsonify(
            {"ok": False, "error": "service_not_initialized", "provider": "salesforce"}
        ), 503

    try:
        # Test basic configuration
        config_ok = bool(
            salesforce_oauth_handler.config.client_id
            and salesforce_oauth_handler.config.client_secret
            and salesforce_oauth_handler.config.redirect_uri
        )

        return jsonify(
            {
                "ok": True,
                "provider": "salesforce",
                "environment": salesforce_oauth_handler.config.environment,
                "configuration": "valid" if config_ok else "invalid",
                "database": "connected"
                if salesforce_oauth_handler.db_pool
                else "disconnected",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    except Exception as e:
        return jsonify(
            {
                "ok": False,
                "error": "health_check_failed",
                "message": str(e),
                "provider": "salesforce",
            }
        ), 500
