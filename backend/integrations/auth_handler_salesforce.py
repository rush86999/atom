"""
Salesforce Authentication Handler
OAuth 2.0 authentication handler for Salesforce integration
"""

import os
import json
import logging
import secrets
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from urllib.parse import urlencode
import aiohttp
from fastapi import HTTPException
from core.secret_manager import get_secret_manager

logger = logging.getLogger(__name__)


class SalesforceAuthHandler:
    """
    Handles Salesforce OAuth 2.0 authentication and token management
    """

    def __init__(self):
        self.client_id = os.getenv("SALESFORCE_CLIENT_ID", "")
        self.client_secret = os.getenv("SALESFORCE_CLIENT_SECRET", "")
        self.redirect_uri = os.getenv(
            "SALESFORCE_REDIRECT_URI", "http://localhost:3000/api/auth/callback/salesforce"
        )
        # Default to production, can be overridden or made dynamic for sandbox
        self.base_url = os.getenv("SALESFORCE_AUTH_URL", "https://login.salesforce.com")
        self.token_url = f"{self.base_url}/services/oauth2/token"
        self.authorize_url = f"{self.base_url}/services/oauth2/authorize"
        self.revoke_url = f"{self.base_url}/services/oauth2/revoke"

        # Initialize Secret Manager
        self.secret_manager = get_secret_manager()

        # Token storage (Load from Secret Manager if available)
        self.access_token = self.secret_manager.get_secret("SALESFORCE_ACCESS_TOKEN")
        self.refresh_token = self.secret_manager.get_secret("SALESFORCE_REFRESH_TOKEN")
        self.instance_url = self.secret_manager.get_secret("SALESFORCE_INSTANCE_URL")
        
        # Expiry is tricky to persist exactly without timezone issues, but we can rely on refresh if needed
        # Or store timestamp as string. For now, we assume if we load from disk, we might need a refresh.
        self.token_expires_at = None
        if self.access_token:
             # Assume expired/close to expiry to force check/refresh on startup if real robustness needed
             # Or just let is_token_valid fail and trigger refresh
             self.token_expires_at = datetime.now() # Temporarily invalid to force refresh check
        
        self.user_info = None

    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Generate Salesforce OAuth authorization URL

        Args:
            state: Optional state parameter for security

        Returns:
            Authorization URL
        """
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
        }

        if state:
            params["state"] = state
        else:
            params["state"] = secrets.token_urlsafe(32)

        # Standard Salesforce scopes
        scopes = [
            "api",
            "refresh_token",
            "offline_access",
            "web"
        ]
        params["scope"] = " ".join(scopes)

        query_string = urlencode(params)
        return f"{self.authorize_url}?{query_string}"

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Token response
        """
        try:
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
            }

            data = {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.token_url, headers=headers, data=data
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Salesforce token exchange failed: {error_text}")
                        raise HTTPException(
                            status_code=400,
                            detail=f"Token exchange failed: {error_text}",
                        )

                    token_data = await response.json()

                    # Store tokens
                    self.access_token = token_data.get("access_token")
                    self.refresh_token = token_data.get("refresh_token")
                    self.instance_url = token_data.get("instance_url")
                    
                    # Persist to Secret Manager
                    if self.access_token:
                        self.secret_manager.set_secret("SALESFORCE_ACCESS_TOKEN", self.access_token)
                    if self.refresh_token:
                        self.secret_manager.set_secret("SALESFORCE_REFRESH_TOKEN", self.refresh_token)
                    if self.instance_url:
                        self.secret_manager.set_secret("SALESFORCE_INSTANCE_URL", self.instance_url)
                    
                    # Salesforce doesn't always return expires_in, default to 2 hours if missing
                    # Session timeout is configured in Salesforce org
                    expires_in = token_data.get("expires_in", 7200) 
                    self.token_expires_at = datetime.now() + timedelta(
                        seconds=int(expires_in) if expires_in else 7200
                    )

                    logger.info(
                        "Successfully exchanged Salesforce authorization code for tokens"
                    )
                    return token_data

        except Exception as e:
            logger.error(f"Error exchanging Salesforce code for token: {e}")
            raise HTTPException(
                status_code=500, detail=f"Token exchange error: {str(e)}"
            )

    async def refresh_access_token(self) -> Dict[str, Any]:
        """
        Refresh access token using refresh token

        Returns:
            New token data
        """
        if not self.refresh_token:
            raise HTTPException(status_code=400, detail="No refresh token available")

        try:
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
            }

            data = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.token_url, headers=headers, data=data
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Salesforce token refresh failed: {error_text}")
                        raise HTTPException(
                            status_code=400,
                            detail=f"Token refresh failed: {error_text}",
                        )

                    token_data = await response.json()

                    # Update tokens
                    self.access_token = token_data.get("access_token")
                    # Salesforce might not return a new refresh token, keep old one if not provided
                    if token_data.get("refresh_token"):
                        self.refresh_token = token_data.get("refresh_token")
                    
                    self.instance_url = token_data.get("instance_url", self.instance_url)
                    
                    # Persist updates
                    if self.access_token:
                        self.secret_manager.set_secret("SALESFORCE_ACCESS_TOKEN", self.access_token)
                    if self.refresh_token:
                        self.secret_manager.set_secret("SALESFORCE_REFRESH_TOKEN", self.refresh_token)
                    if self.instance_url:
                        self.secret_manager.set_secret("SALESFORCE_INSTANCE_URL", self.instance_url)
                    
                    expires_in = token_data.get("expires_in", 7200)
                    self.token_expires_at = datetime.now() + timedelta(
                        seconds=int(expires_in) if expires_in else 7200
                    )

                    logger.info("Successfully refreshed Salesforce access token")
                    return token_data

        except Exception as e:
            logger.error(f"Error refreshing Salesforce token: {e}")
            raise HTTPException(
                status_code=500, detail=f"Token refresh error: {str(e)}"
            )

    async def get_user_info(self) -> Dict[str, Any]:
        """
        Get current user information from Salesforce

        Returns:
            User information
        """
        if not self.access_token or not self.instance_url:
            raise HTTPException(status_code=401, detail="No access token or instance URL available")

        try:
            # Salesforce Identity URL is usually provided in token response as 'id'
            # But we can also query the User object directly or use the UserInfo endpoint
            
            # Using UserInfo endpoint (OpenID Connect)
            userinfo_url = f"{self.base_url}/services/oauth2/userinfo"
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    userinfo_url, headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Failed to get Salesforce user info: {error_text}")
                        raise HTTPException(
                            status_code=400,
                            detail=f"Failed to get user info: {error_text}",
                        )

                    user_data = await response.json()
                    self.user_info = user_data
                    return user_data

        except Exception as e:
            logger.error(f"Error getting Salesforce user info: {e}")
            raise HTTPException(status_code=500, detail=f"User info error: {str(e)}")

    async def revoke_token(self) -> bool:
        """
        Revoke access token

        Returns:
            Success status
        """
        if not self.access_token:
            return True

        try:
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
            }

            data = {"token": self.access_token}

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.revoke_url, headers=headers, data=data
                ) as response:
                    if response.status == 200:
                        # Clear tokens
                        # Clear tokens
                        self.access_token = None
                        self.refresh_token = None
                        self.token_expires_at = None
                        self.user_info = None
                        self.instance_url = None
                        
                        # Clear from Secret Manager (by setting to empty or handling delete)
                        # SecretManagerBase doesn't have delete, so we set to empty string or handle logic
                        # For now, let's just overwrite with empty
                        self.secret_manager.set_secret("SALESFORCE_ACCESS_TOKEN", "")
                        self.secret_manager.set_secret("SALESFORCE_REFRESH_TOKEN", "")

                        logger.info("Successfully revoked Salesforce token")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Salesforce token revocation failed: {error_text}")
                        return False

        except Exception as e:
            logger.error(f"Error revoking Salesforce token: {e}")
            return False

    def is_token_valid(self) -> bool:
        """
        Check if current access token is valid

        Returns:
            Token validity status
        """
        if not self.access_token or not self.token_expires_at:
            return False

        return datetime.now() < self.token_expires_at - timedelta(minutes=5)

    async def ensure_valid_token(self) -> str:
        """
        Ensure we have a valid access token, refreshing if necessary

        Returns:
            Valid access token
        """
        if not self.is_token_valid():
            if self.refresh_token:
                await self.refresh_access_token()
            else:
                raise HTTPException(status_code=401, detail="No valid token available")

        return self.access_token

    def get_connection_status(self) -> Dict[str, Any]:
        """
        Get current connection status

        Returns:
            Connection status information
        """
        return {
            "connected": self.is_token_valid(),
            "has_access_token": bool(self.access_token),
            "has_refresh_token": bool(self.refresh_token),
            "instance_url": self.instance_url,
            "token_expires_at": self.token_expires_at.isoformat()
            if self.token_expires_at
            else None,
            "user_info_available": bool(self.user_info),
            "client_id_configured": bool(self.client_id),
            "client_secret_configured": bool(self.client_secret),
        }


# Global instance
salesforce_auth_handler = SalesforceAuthHandler()
