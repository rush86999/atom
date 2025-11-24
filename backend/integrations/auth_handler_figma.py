"""
Figma Authentication Handler
OAuth 2.0 authentication handler for Figma integration
"""

import os
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import aiohttp
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class FigmaAuthHandler:
    """
    Handles Figma OAuth 2.0 authentication and token management
    """

    def __init__(self):
        self.client_id = os.getenv("FIGMA_CLIENT_ID", "")
        self.client_secret = os.getenv("FIGMA_CLIENT_SECRET", "")
        self.redirect_uri = os.getenv(
            "FIGMA_REDIRECT_URI", "http://localhost:3000/api/auth/callback/figma"
        )
        self.authorize_url = "https://www.figma.com/oauth"
        self.token_url = "https://www.figma.com/api/oauth/token"
        self.api_base_url = "https://api.figma.com/v1"

        # Token storage (in production, use secure storage/database)
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        self.user_info = None

    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Generate Figma OAuth authorization URL

        Args:
            state: Optional state parameter for security

        Returns:
            Authorization URL
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "file_read",  # Default scope, can be extended with file_write, webhooks, etc.
            "state": state or "random_state_string",
            "response_type": "code",
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
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "code": code,
                "grant_type": "authorization_code",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.token_url, headers=headers, data=data
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Figma token exchange failed: {error_text}")
                        raise HTTPException(
                            status_code=400,
                            detail=f"Token exchange failed: {error_text}",
                        )

                    token_data = await response.json()

                    # Store tokens
                    self.access_token = token_data.get("access_token")
                    self.refresh_token = token_data.get("refresh_token")
                    
                    # Figma tokens typically expire in 90 days
                    expires_in = token_data.get("expires_in", 7776000)  # 90 days default
                    self.token_expires_at = datetime.now() + timedelta(
                        seconds=int(expires_in)
                    )

                    logger.info(
                        "Successfully exchanged Figma authorization code for tokens"
                    )
                    return token_data

        except Exception as e:
            logger.error(f"Error exchanging Figma code for token: {e}")
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
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.token_url, headers=headers, data=data
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Figma token refresh failed: {error_text}")
                        raise HTTPException(
                            status_code=400,
                            detail=f"Token refresh failed: {error_text}",
                        )

                    token_data = await response.json()

                    # Update tokens
                    self.access_token = token_data.get("access_token")
                    if token_data.get("refresh_token"):
                        self.refresh_token = token_data.get("refresh_token")
                    
                    expires_in = token_data.get("expires_in", 7776000)
                    self.token_expires_at = datetime.now() + timedelta(
                        seconds=int(expires_in)
                    )

                    logger.info("Successfully refreshed Figma access token")
                    return token_data

        except Exception as e:
            logger.error(f"Error refreshing Figma token: {e}")
            raise HTTPException(
                status_code=500, detail=f"Token refresh error: {str(e)}"
            )

    async def get_user_info(self) -> Dict[str, Any]:
        """
        Get current user information from Figma

        Returns:
            User information
        """
        if not self.access_token:
            raise HTTPException(status_code=401, detail="No access token available")

        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
            }

            # Get user information
            url = f"{self.api_base_url}/me"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Failed to get Figma user info: {error_text}")
                        raise HTTPException(
                            status_code=400,
                            detail=f"Failed to get user info: {error_text}",
                        )

                    user_data = await response.json()
                    self.user_info = user_data
                    return user_data

        except Exception as e:
            logger.error(f"Error getting Figma user info: {e}")
            raise HTTPException(status_code=500, detail=f"User info error: {str(e)}")

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
            "user_info_available": bool(self.user_info),
            "client_id_configured": bool(self.client_id),
            "client_secret_configured": bool(self.client_secret),
        }


# Global instance
figma_auth_handler = FigmaAuthHandler()
