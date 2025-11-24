"""
Dropbox Authentication Handler
OAuth 2.0 authentication handler for Dropbox integration
"""

import os
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import aiohttp
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class DropboxAuthHandler:
    """
    Handles Dropbox OAuth 2.0 authentication and token management
    """

    def __init__(self):
        self.client_id = os.getenv("DROPBOX_CLIENT_ID", "")
        self.client_secret = os.getenv("DROPBOX_CLIENT_SECRET", "")
        self.redirect_uri = os.getenv(
            "DROPBOX_REDIRECT_URI", "http://localhost:3000/api/auth/callback/dropbox"
        )
        self.authorize_url = "https://www.dropbox.com/oauth2/authorize"
        self.token_url = "https://api.dropboxapi.com/oauth2/token"
        self.api_base_url = "https://api.dropboxapi.com/2"

        # Token storage (in production, use secure storage/database)
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        self.user_info = None
        self.account_id = None

    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Generate Dropbox OAuth authorization URL

        Args:
            state: Optional state parameter for security

        Returns:
            Authorization URL
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "token_access_type": "offline",  # Request refresh token
            "state": state or "random_state_string",
        }

        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
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
                "code": code,
                "grant_type": "authorization_code",
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
                        logger.error(f"Dropbox token exchange failed: {error_text}")
                        raise HTTPException(
                            status_code=400,
                            detail=f"Token exchange failed: {error_text}",
                        )

                    token_data = await response.json()

                    # Store tokens
                    self.access_token = token_data.get("access_token")
                    self.refresh_token = token_data.get("refresh_token")
                    self.account_id = token_data.get("account_id")
                    
                    # Dropbox access tokens expire after 4 hours (14400 seconds)
                    expires_in = token_data.get("expires_in", 14400)
                    self.token_expires_at = datetime.now() + timedelta(
                        seconds=int(expires_in)
                    )

                    logger.info(
                        "Successfully exchanged Dropbox authorization code for tokens"
                    )
                    return token_data

        except Exception as e:
            logger.error(f"Error exchanging Dropbox code for token: {e}")
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
                        logger.error(f"Dropbox token refresh failed: {error_text}")
                        raise HTTPException(
                            status_code=400,
                            detail=f"Token refresh failed: {error_text}",
                        )

                    token_data = await response.json()

                    # Update tokens
                    self.access_token = token_data.get("access_token")
                    # Dropbox might not return a new refresh token
                    if token_data.get("refresh_token"):
                        self.refresh_token = token_data.get("refresh_token")
                    
                    expires_in = token_data.get("expires_in", 14400)
                    self.token_expires_at = datetime.now() + timedelta(
                        seconds=int(expires_in)
                    )

                    logger.info("Successfully refreshed Dropbox access token")
                    return token_data

        except Exception as e:
            logger.error(f"Error refreshing Dropbox token: {e}")
            raise HTTPException(
                status_code=500, detail=f"Token refresh error: {str(e)}"
            )

    async def get_user_info(self) -> Dict[str, Any]:
        """
        Get current user information from Dropbox

        Returns:
            User information
        """
        if not self.access_token:
            raise HTTPException(status_code=401, detail="No access token available")

        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }

            # Get current account info
            url = f"{self.api_base_url}/users/get_current_account"

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Failed to get Dropbox user info: {error_text}")
                        raise HTTPException(
                            status_code=400,
                            detail=f"Failed to get user info: {error_text}",
                        )

                    user_data = await response.json()
                    self.user_info = user_data
                    return user_data

        except Exception as e:
            logger.error(f"Error getting Dropbox user info: {e}")
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
                "Authorization": f"Bearer {self.access_token}",
            }

            url = "https://api.dropboxapi.com/2/auth/token/revoke"

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers) as response:
                    if response.status == 200:
                        # Clear tokens
                        self.access_token = None
                        self.refresh_token = None
                        self.token_expires_at = None
                        self.user_info = None
                        self.account_id = None

                        logger.info("Successfully revoked Dropbox token")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Dropbox token revocation failed: {error_text}")
                        return False

        except Exception as e:
            logger.error(f"Error revoking Dropbox token: {e}")
            return False

    def is_token_valid(self) -> bool:
        """
        Check if current access token is valid

        Returns:
            Token validity status
        """
        if not self.access_token or not self.token_expires_at:
            return False

        # Check if token expires in more than 5 minutes
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
            "token_expires_at": self.token_expires_at.isoformat()
            if self.token_expires_at
            else None,
            "account_id": self.account_id,
            "user_info_available": bool(self.user_info),
            "client_id_configured": bool(self.client_id),
            "client_secret_configured": bool(self.client_secret),
        }


# Global instance
dropbox_auth_handler = DropboxAuthHandler()
