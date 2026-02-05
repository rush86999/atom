"""
Calendly Service for ATOM Platform
Provides comprehensive Calendly scheduling integration functionality
"""

from datetime import datetime
import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
import httpx

logger = logging.getLogger(__name__)

class CalendlyService:
    def __init__(self):
        self.base_url = "https://api.calendly.com"
        self.auth_url = "https://auth.calendly.com/oauth/authorize"
        self.token_url = "https://auth.calendly.com/oauth/token"
        self.client_id = os.getenv("CALENDLY_CLIENT_ID")
        self.client_secret = os.getenv("CALENDLY_CLIENT_SECRET")
        self.access_token = os.getenv("CALENDLY_ACCESS_TOKEN")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client connection"""
        await self.client.aclose()

    def _get_headers(self, access_token: str) -> Dict[str, str]:
        """Get headers for API requests"""
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

    def get_authorization_url(self, redirect_uri: str, state: str = None) -> str:
        """Generate OAuth authorization URL"""
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri
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
            
            response = await self.client.post(self.token_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get("access_token")
            
            return token_data
        except httpx.HTTPError as e:
            logger.error(f"Calendly token exchange failed: {e}")
            raise HTTPException(
                status_code=400, 
                detail=f"Token exchange failed: {str(e)}"
            )

    async def get_current_user(self, access_token: str = None) -> Dict[str, Any]:
        """Get current user information"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            response = await self.client.get(f"{self.base_url}/users/me", headers=headers)
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get current user: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get user info: {str(e)}"
            )

    async def get_event_types(
        self, 
        user_uri: str,
        access_token: str = None,
        count: int = 20
    ) -> List[Dict[str, Any]]:
        """Get event types for a user"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            params = {"user": user_uri, "count": count}
            
            response = await self.client.get(
                f"{self.base_url}/event_types",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("collection", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get event types: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get event types: {str(e)}"
            )

    async def get_scheduled_events(
        self,
        user_uri: str = None,
        access_token: str = None,
        count: int = 20,
        status: str = "active"
    ) -> List[Dict[str, Any]]:
        """Get scheduled events"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            params = {"count": count, "status": status}
            
            if user_uri:
                params["user"] = user_uri
            
            response = await self.client.get(
                f"{self.base_url}/scheduled_events",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("collection", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get scheduled events: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get scheduled events: {str(e)}"
            )

    async def health_check(self) -> Dict[str, Any]:
        """Health check for Calendly service"""
        try:
            return {
                "ok": True,
                "status": "healthy",
                "service": "calendly",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
            }
        except Exception as e:
            return {
                "ok": False,
                "status": "unhealthy",
                "service": "calendly",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

# Singleton instance
calendly_service = CalendlyService()

def get_calendly_service() -> CalendlyService:
    """Get Calendly service instance"""
    return calendly_service
