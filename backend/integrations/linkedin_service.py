"""
LinkedIn Service for ATOM Platform
Provides comprehensive LinkedIn professional networking integration functionality
"""

import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime
import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class LinkedInService:
    def __init__(self):
        self.client_id = os.getenv("LINKEDIN_CLIENT_ID")
        self.client_secret = os.getenv("LINKEDIN_CLIENT_SECRET")
        self.base_url = "https://api.linkedin.com/v2"
        self.auth_url = "https://www.linkedin.com/oauth/v2/authorization"
        self.token_url = "https://www.linkedin.com/oauth/v2/accessToken"
        self.access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client connection"""
        await self.client.aclose()

    def _get_headers(self, access_token: str) -> Dict[str, str]:
        """Get headers for API requests"""
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }

    def get_authorization_url(
        self,
        redirect_uri: str,
        state: str = None,
        scope: str = "r_liteprofile r_emailaddress w_member_social"
    ) -> str:
        """Generate OAuth authorization URL"""
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": scope
        }
        if state:
            params["state"] = state
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.auth_url}?{query_string}"

    async def exchange_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        try:
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
            
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            
            response = await self.client.post(self.token_url, data=data, headers=headers)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get("access_token")
            
            return token_data
        except httpx.HTTPError as e:
            logger.error(f"LinkedIn token exchange failed: {e}")
            raise HTTPException(
                status_code=400, 
                detail=f"Token exchange failed: {str(e)}"
            )

    async def get_profile(self, access_token: str = None) -> Dict[str, Any]:
        """Get user profile information"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            
            response = await self.client.get(
                f"{self.base_url}/me",
                headers=headers
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get profile: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get profile: {str(e)}"
            )

    async def get_email(self, access_token: str = None) -> Dict[str, Any]:
        """Get user email address"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            params = {"q": "members", "projection": "(elements*(handle~))"}
            
            response = await self.client.get(
                f"{self.base_url}/emailAddress",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get email: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get email: {str(e)}"
            )

    async def share_update(
        self,
        text: str,
        access_token: str = None,
        visibility: str = "PUBLIC"
    ) -> Dict[str, Any]:
        """Share an update/post on LinkedIn"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            
            # First get the user's URN
            profile = await self.get_profile(token)
            author_urn = profile.get("id")
            
            payload = {
                "author": f"urn:li:person:{author_urn}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": text
                        },
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": visibility
                }
            }
            
            response = await self.client.post(
                f"{self.base_url}/ugcPosts",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to share update: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to share update: {str(e)}"
            )

    async def health_check(self) -> Dict[str, Any]:
        """Health check for LinkedIn service"""
        try:
            return {
                "ok": True,
                "status": "healthy",
                "service": "linkedin",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
            }
        except Exception as e:
            return {
                "ok": False,
                "status": "unhealthy",
                "service": "linkedin",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

# Singleton instance
linkedin_service = LinkedInService()

def get_linkedin_service() -> LinkedInService:
    """Get LinkedIn service instance"""
    return linkedin_service
