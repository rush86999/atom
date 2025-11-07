"""
Zoom Authentication Handler
OAuth 2.0 authentication handler for Zoom integration
"""

import os
import json
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import aiohttp
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class ZoomAuthHandler:
    """
    Handles Zoom OAuth 2.0 authentication and token management
    """

    def __init__(self):
        self.client_id = os.getenv("ZOOM_CLIENT_ID", "")
        self.client_secret = os.getenv("ZOOM_CLIENT_SECRET", "")
        self.redirect_uri = os.getenv(
            "ZOOM_REDIRECT_URI", "http://localhost:5058/api/auth/zoom/callback"
        )
        self.token_url = "https://zoom.us/oauth/token"
        self.authorize_url = "https://zoom.us/oauth/authorize"
        self.api_base_url = "https://api.zoom.us/v2"

        # Token storage (in production, use secure storage)
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        self.user_info = None

    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Generate Zoom OAuth authorization URL

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

        # Zoom requires specific scopes
        scopes = [
            "meeting:write:admin",
            "meeting:read:admin",
            "user:read:admin",
            "recording:read:admin",
            "webhook:write:admin",
        ]
        params["scope"] = " ".join(scopes)

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
                "Authorization": f"Basic {self._get_basic_auth_header()}",
            }

            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.token_url, headers=headers, data=data
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Zoom token exchange failed: {error_text}")
                        raise HTTPException(
                            status_code=400,
                            detail=f"Token exchange failed: {error_text}",
                        )

                    token_data = await response.json()

                    # Store tokens
                    self.access_token = token_data.get("access_token")
                    self.refresh_token = token_data.get("refresh_token")
                    expires_in = token_data.get("expires_in", 3600)
                    self.token_expires_at = datetime.now() + timedelta(
                        seconds=expires_in
                    )

                    logger.info(
                        "Successfully exchanged Zoom authorization code for tokens"
                    )
                    return token_data

        except Exception as e:
            logger.error(f"Error exchanging Zoom code for token: {e}")
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
                "Authorization": f"Basic {self._get_basic_auth_header()}",
            }

            data = {"grant_type": "refresh_token", "refresh_token": self.refresh_token}

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.token_url, headers=headers, data=data
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Zoom token refresh failed: {error_text}")
                        raise HTTPException(
                            status_code=400,
                            detail=f"Token refresh failed: {error_text}",
                        )

                    token_data = await response.json()

                    # Update tokens
                    self.access_token = token_data.get("access_token")
                    self.refresh_token = token_data.get("refresh_token")
                    expires_in = token_data.get("expires_in", 3600)
                    self.token_expires_at = datetime.now() + timedelta(
                        seconds=expires_in
                    )

                    logger.info("Successfully refreshed Zoom access token")
                    return token_data

        except Exception as e:
            logger.error(f"Error refreshing Zoom token: {e}")
            raise HTTPException(
                status_code=500, detail=f"Token refresh error: {str(e)}"
            )

    async def get_user_info(self) -> Dict[str, Any]:
        """
        Get current user information from Zoom

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

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}/users/me", headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Failed to get Zoom user info: {error_text}")
                        raise HTTPException(
                            status_code=400,
                            detail=f"Failed to get user info: {error_text}",
                        )

                    user_data = await response.json()
                    self.user_info = user_data
                    return user_data

        except Exception as e:
            logger.error(f"Error getting Zoom user info: {e}")
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
                "Authorization": f"Basic {self._get_basic_auth_header()}",
            }

            data = {"token": self.access_token, "token_type_hint": "access_token"}

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://zoom.us/oauth/revoke", headers=headers, data=data
                ) as response:
                    if response.status == 200:
                        # Clear tokens
                        self.access_token = None
                        self.refresh_token = None
                        self.token_expires_at = None
                        self.user_info = None

                        logger.info("Successfully revoked Zoom token")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Zoom token revocation failed: {error_text}")
                        return False

        except Exception as e:
            logger.error(f"Error revoking Zoom token: {e}")
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

    async def make_authenticated_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Make authenticated request to Zoom API

        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request parameters

        Returns:
            API response
        """
        access_token = await self.ensure_valid_token()

        headers = kwargs.get("headers", {})
        headers.update(
            {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
        )
        kwargs["headers"] = headers

        url = f"{self.api_base_url}{endpoint}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, **kwargs) as response:
                    if response.status == 401:
                        # Token might be expired, try to refresh
                        await self.refresh_access_token()
                        return await self.make_authenticated_request(
                            method, endpoint, **kwargs
                        )

                    if response.status not in [200, 201, 204]:
                        error_text = await response.text()
                        logger.error(f"Zoom API request failed: {error_text}")
                        raise HTTPException(
                            status_code=response.status,
                            detail=f"Zoom API error: {error_text}",
                        )

                    if response.status == 204:
                        return {}

                    return await response.json()

        except Exception as e:
            logger.error(f"Error making Zoom API request: {e}")
            raise HTTPException(
                status_code=500, detail=f"Zoom API request error: {str(e)}"
            )

    def _get_basic_auth_header(self) -> str:
        """
        Generate Basic Auth header for Zoom OAuth

        Returns:
            Base64 encoded auth header
        """
        import base64

        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        return encoded_credentials

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
zoom_auth_handler = ZoomAuthHandler()
