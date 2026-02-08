"""
Zendesk Service for ATOM Platform
Provides comprehensive Zendesk customer support integration functionality
"""

from datetime import datetime
import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
import httpx

logger = logging.getLogger(__name__)

class ZendeskService:
    def __init__(self):
        self.client_id = os.getenv("ZENDESK_CLIENT_ID")
        self.client_secret = os.getenv("ZENDESK_CLIENT_SECRET")
        self.subdomain = os.getenv("ZENDESK_SUBDOMAIN", "")
        self.base_url = f"https://{self.subdomain}.zendesk.com/api/v2"
        self.oauth_url = f"https://{self.subdomain}.zendesk.com/oauth"
        self.access_token = os.getenv("ZENDESK_ACCESS_TOKEN")
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

    def get_authorization_url(self, redirect_uri: str, state: str = None, scope: str = "read write") -> str:
        """Generate OAuth authorization URL"""
        params = {
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "client_id": self.client_id,
            "scope": scope
        }
        if state:
            params["state"] = state
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.oauth_url}/authorizations/new?{query_string}"

    async def exchange_token(self, code: str, redirect_uri: str, scope: str = "read write") -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        try:
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": redirect_uri,
                "scope": scope
            }
            
            response = await self.client.post(f"{self.oauth_url}/tokens", data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get("access_token")
            
            return token_data
        except httpx.HTTPError as e:
            logger.error(f"Zendesk token exchange failed: {e}")
            raise HTTPException(
                status_code=400, 
                detail=f"Token exchange failed: {str(e)}"
            )

    async def get_tickets(
        self, 
        access_token: str = None,
        per_page: int = 100,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> List[Dict[str, Any]]:
        """Get tickets from Zendesk"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            params = {
                "per_page": per_page,
                "sort_by": sort_by,
                "sort_order": sort_order
            }
            
            response = await self.client.get(
                f"{self.base_url}/tickets.json",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("tickets", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get tickets: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get tickets: {str(e)}"
            )

    async def get_ticket(self, ticket_id: int, access_token: str = None) -> Dict[str, Any]:
        """Get a specific ticket"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            
            response = await self.client.get(
                f"{self.base_url}/tickets/{ticket_id}.json",
                headers=headers
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("ticket", {})
        except httpx.HTTPError as e:
            logger.error(f"Failed to get ticket: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get ticket: {str(e)}"
            )

    async def create_ticket(
        self,
        subject: str,
        comment_body: str,
        access_token: str = None,
        priority: str = "normal",
        requester_name: str = None,
        requester_email: str = None
    ) -> Dict[str, Any]:
        """Create a new ticket"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            
            ticket_data = {
                "subject": subject,
                "comment": {"body": comment_body},
                "priority": priority
            }
            
            if requester_name or requester_email:
                ticket_data["requester"] = {}
                if requester_name:
                    ticket_data["requester"]["name"] = requester_name
                if requester_email:
                    ticket_data["requester"]["email"] = requester_email
            
            payload = {"ticket": ticket_data}
            
            response = await self.client.post(
                f"{self.base_url}/tickets.json",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("ticket", {})
        except httpx.HTTPError as e:
            logger.error(f"Failed to create ticket: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to create ticket: {str(e)}"
            )

    async def search_tickets(
        self,
        query: str,
        access_token: str = None,
        per_page: int = 100
    ) -> List[Dict[str, Any]]:
        """Search Zendesk tickets"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            params = {
                "query": f"type:ticket {query}",
                "per_page": per_page
            }
            
            response = await self.client.get(
                f"{self.base_url}/search.json",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("results", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to search tickets: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to search tickets: {str(e)}"
            )

    async def get_users(
        self,
        access_token: str = None,
        per_page: int = 100
    ) -> List[Dict[str, Any]]:
        """Get users from Zendesk"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            params = {"per_page": per_page}
            
            response = await self.client.get(
                f"{self.base_url}/users.json",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("users", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get users: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get users: {str(e)}"
            )

    async def health_check(self) -> Dict[str, Any]:
        """Health check for Zendesk service"""
        try:
            return {
                "ok": True,
                "status": "healthy",
                "service": "zendesk",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
            }
        except Exception as e:
            return {
                "ok": False,
                "status": "unhealthy",
                "service": "zendesk",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

# Singleton instance
zendesk_service = ZendeskService()

def get_zendesk_service() -> ZendeskService:
    """Get Zendesk service instance"""
    return zendesk_service
