"""
Zoom Service for ATOM Platform
Provides comprehensive Zoom video conferencing integration functionality
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import httpx
from fastapi import HTTPException

from core.integration_service import IntegrationService

logger = logging.getLogger(__name__)

class ZoomService(IntegrationService):
    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        """
        Initialize Zoom service for a specific tenant.

        Args:
            tenant_id: Tenant UUID for multi-tenancy
            config: Tenant-specific configuration with client_id, client_secret, account_id, access_token
        """
        super().__init__(tenant_id=tenant_id, config=config)
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        self.account_id = config.get("account_id")
        self.base_url = "https://api.zoom.us/v2"
        self.auth_url = "https://zoom.us/oauth/authorize"
        self.token_url = "https://zoom.us/oauth/token"
        self.access_token = config.get("access_token")
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

    def get_capabilities(self) -> Dict[str, Any]:
        """Return Zoom integration capabilities"""
        return {
            "operations": [
                {
                    "id": "create_meeting",
                    "name": "Create Meeting",
                    "description": "Create a Zoom meeting",
                    "complexity": 3
                },
                {
                    "id": "list_meetings",
                    "name": "List Meetings",
                    "description": "List user's meetings",
                    "complexity": 2
                },
                {
                    "id": "delete_meeting",
                    "name": "Delete Meeting",
                    "description": "Delete a meeting",
                    "complexity": 3
                },
                {
                    "id": "list_users",
                    "name": "List Users",
                    "description": "List users on the account",
                    "complexity": 2
                },
                {
                    "id": "list_recordings",
                    "name": "List Recordings",
                    "description": "List cloud recordings for a user",
                    "complexity": 2
                }
            ],
            "required_params": ["client_id", "client_secret", "account_id"],
            "optional_params": ["access_token"],
            "rate_limits": {"requests_per_minute": 100},
            "supports_webhooks": True
        }

    def health_check(self) -> Dict[str, Any]:
        """Health check for Zoom service"""
        try:
            return {
                "healthy": bool(self.client_id and self.client_secret),
                "message": "Zoom service is operational" if self.client_id else "Zoom credentials not configured",
                "last_check": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            return {
                "healthy": False,
                "message": str(e),
                "last_check": datetime.now(timezone.utc).isoformat()
            }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a Zoom operation with tenant context.

        Args:
            operation: Operation name (e.g., "create_meeting", "list_meetings")
            parameters: Operation parameters
            context: Tenant context dict

        Returns:
            Dict with success, result, error, details
        """
        try:
            if operation == "create_meeting":
                result = await self.create_meeting(**parameters)
                return {
                    "success": True,
                    "result": result,
                    "details": {"operation": "create_meeting", "tenant_id": self.tenant_id}
                }
            elif operation == "list_meetings":
                result = await self.list_meetings(**parameters)
                return {
                    "success": True,
                    "result": result,
                    "details": {"operation": "list_meetings", "tenant_id": self.tenant_id}
                }
            elif operation == "delete_meeting":
                result = await self.delete_meeting(**parameters)
                return {
                    "success": True,
                    "result": result,
                    "details": {"operation": "delete_meeting", "tenant_id": self.tenant_id}
                }
            elif operation == "list_users":
                result = await self.list_users(**parameters)
                return {
                    "success": True,
                    "result": result,
                    "details": {"operation": "list_users", "tenant_id": self.tenant_id}
                }
            elif operation == "list_recordings":
                result = await self.list_recordings(**parameters)
                return {
                    "success": True,
                    "result": result,
                    "details": {"operation": "list_recordings", "tenant_id": self.tenant_id}
                }
            else:
                return {
                    "success": False,
                    "error": f"Unknown operation: {operation}",
                    "details": {"operation": operation}
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": {"operation": operation, "tenant_id": self.tenant_id}
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
