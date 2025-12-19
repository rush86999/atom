"""
Zoom Service for ATOM Platform
Provides comprehensive Zoom video conferencing integration functionality
"""

import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime
import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class ZoomService:
    def __init__(self):
        self.client_id = os.getenv("ZOOM_CLIENT_ID")
        self.client_secret = os.getenv("ZOOM_CLIENT_SECRET")
        self.account_id = os.getenv("ZOOM_ACCOUNT_ID")
        self.base_url = "https://api.zoom.us/v2"
        self.auth_url = "https://zoom.us/oauth/authorize"
        self.token_url = "https://zoom.us/oauth/token"
        self.access_token = None
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

    def get_authorization_url(
        self,
        redirect_uri: str,
        state: str = None
    ) -> str:
        """Generate OAuth authorization URL"""
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri
        }
        if state:
            params["state"] = state
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.auth_url}?{query_string}"

    async def exchange_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        try:
            auth = (self.client_id, self.client_secret)
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri
            }
            
            response = await self.client.post(
                self.token_url,
                data=data,
                auth=auth
            )
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get("access_token")
            
            return token_data
        except httpx.HTTPError as e:
            logger.error(f"Zoom token exchange failed: {e}")
            raise HTTPException(
                status_code=400, 
                detail=f"Token exchange failed: {str(e)}"
            )

    async def get_user(self, user_id: str = "me", access_token: str = None) -> Dict[str, Any]:
        """Get user information"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            
            response = await self.client.get(
                f"{self.base_url}/users/{user_id}",
                headers=headers
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get user: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get user: {str(e)}"
            )

    async def list_meetings(
        self,
        user_id: str = "me",
        type: str = "scheduled",
        access_token: str = None,
        page_size: int = 30
    ) -> Dict[str, Any]:
        """List user's meetings"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            params = {
                "type": type,
                "page_size": page_size
            }
            
            response = await self.client.get(
                f"{self.base_url}/users/{user_id}/meetings",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to list meetings: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to list meetings: {str(e)}"
            )

    async def create_meeting(
        self,
        topic: str,
        user_id: str = "me",
        access_token: str = None,
        start_time: str = None,
        duration: int = 60,
        timezone: str = "UTC",
        agenda: str = None
    ) -> Dict[str, Any]:
        """Create a meeting"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            
            payload = {
                "topic": topic,
                "type": 2,  # Scheduled meeting
                "duration": duration,
                "timezone": timezone
            }
            
            if start_time:
                payload["start_time"] = start_time
            if agenda:
                payload["agenda"] = agenda
            
            response = await self.client.post(
                f"{self.base_url}/users/{user_id}/meetings",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to create meeting: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to create meeting: {str(e)}"
            )

    async def delete_meeting(
        self,
        meeting_id: str,
        access_token: str = None
    ) -> Dict[str, Any]:
        """Delete a meeting"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            
            response = await self.client.delete(
                f"{self.base_url}/meetings/{meeting_id}",
                headers=headers
            )
            response.raise_for_status()
            
            return {"ok": True, "message": "Meeting deleted"}
        except httpx.HTTPError as e:
            logger.error(f"Failed to delete meeting: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to delete meeting: {str(e)}"
            )

    async def health_check(self) -> Dict[str, Any]:
        """Health check for Zoom service"""
        try:
            return {
                "ok": True,
                "status": "healthy",
                "service": "zoom",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
            }
        except Exception as e:
            return {
                "ok": False,
                "status": "unhealthy",
                "service": "zoom",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    async def list_users(
        self,
        status: str = "active",
        page_size: int = 30,
        page_number: int = 1,
        access_token: str = None
    ) -> Dict[str, Any]:
        """List users on the account"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            params = {
                "status": status,
                "page_size": page_size,
                "page_number": page_number
            }
            
            response = await self.client.get(
                f"{self.base_url}/users",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to list users: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to list users: {str(e)}"
            )

    async def list_recordings(
        self,
        user_id: str = "me",
        from_date: str = None,
        to_date: str = None,
        page_size: int = 30,
        access_token: str = None
    ) -> Dict[str, Any]:
        """List cloud recordings for a user"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            params = {
                "page_size": page_size
            }
            if from_date:
                params["from"] = from_date
            if to_date:
                params["to"] = to_date
            
            response = await self.client.get(
                f"{self.base_url}/users/{user_id}/recordings",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to list recordings: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to list recordings: {str(e)}"
            )

zoom_service = ZoomService()

def get_zoom_service() -> ZoomService:
    return zoom_service
