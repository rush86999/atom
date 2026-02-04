"""
Figma Service for ATOM Platform
Provides comprehensive Figma design collaboration integration functionality
"""

import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class FigmaService:
    def __init__(self):
        self.client_id = os.getenv("FIGMA_CLIENT_ID")
        self.client_secret = os.getenv("FIGMA_CLIENT_SECRET")
        self.redirect_uri = os.getenv("FIGMA_REDIRECT_URI", "http://localhost:3000/api/auth/callback/figma")
        
        # Token storage
        self.access_token = os.getenv("FIGMA_ACCESS_TOKEN")
        self.refresh_token = None
        self.token_expires_at = None
        self.user_info = None
        
        self.base_url = "https://api.figma.com/v1"
        self.auth_url = "https://www.figma.com/oauth"
        self.token_url = "https://www.figma.com/api/oauth/token"
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client connection"""
        await self.client.aclose()

    def _get_headers(self, access_token: str = None) -> Dict[str, str]:
        """Get headers for API requests"""
        token = access_token or self.access_token
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """Generate OAuth authorization URL"""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "file_read",
            "state": state or secrets.token_urlsafe(32),
            "response_type": "code",
        }
        query_string = urlencode(params)
        return f"{self.auth_url}?{query_string}"

    async def exchange_token(self, code: str, redirect_uri: str = None) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        try:
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": redirect_uri or self.redirect_uri,
                "code": code,
                "grant_type": "authorization_code"
            }
            
            response = await self.client.post(self.token_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get("access_token")
            self.refresh_token = token_data.get("refresh_token")
            
            expires_in = token_data.get("expires_in", 7776000) # 90 days
            self.token_expires_at = datetime.now() + timedelta(seconds=int(expires_in))
            
            return token_data
        except httpx.HTTPError as e:
            logger.error(f"Figma token exchange failed: {e}")
            raise HTTPException(status_code=400, detail=f"Token exchange failed: {str(e)}")

    async def refresh_access_token(self) -> Dict[str, Any]:
        """Refresh access token"""
        if not self.refresh_token:
            raise HTTPException(status_code=400, detail="No refresh token available")

        try:
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token"
            }
            
            response = await self.client.post(self.token_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get("access_token")
            if token_data.get("refresh_token"):
                self.refresh_token = token_data.get("refresh_token")
                
            expires_in = token_data.get("expires_in", 7776000)
            self.token_expires_at = datetime.now() + timedelta(seconds=int(expires_in))
            
            return token_data
        except httpx.HTTPError as e:
            logger.error(f"Figma token refresh failed: {e}")
            raise HTTPException(status_code=400, detail=f"Token refresh failed: {str(e)}")

    async def get_user_info(self) -> Dict[str, Any]:
        """Get current user info"""
        try:
            if not self.access_token:
                raise HTTPException(status_code=401, detail="Not authenticated")
                
            headers = self._get_headers()
            response = await self.client.get(f"{self.base_url}/me", headers=headers)
            response.raise_for_status()
            
            self.user_info = response.json()
            return self.user_info
        except httpx.HTTPError as e:
            logger.error(f"Failed to get user info: {e}")
            raise HTTPException(status_code=400, detail=f"Failed to get user info: {str(e)}")

    def is_token_valid(self) -> bool:
        """Check if token is valid"""
        if not self.access_token:
            return False
        if self.token_expires_at and datetime.now() > self.token_expires_at - timedelta(minutes=5):
            return False
        return True

    async def ensure_valid_token(self) -> str:
        """Ensure valid token, refresh if needed"""
        if not self.is_token_valid():
            if self.refresh_token:
                await self.refresh_access_token()
            else:
                if not self.access_token:
                    raise HTTPException(status_code=401, detail="No valid token available")
        return self.access_token

    def get_connection_status(self) -> Dict[str, Any]:
        """Get current connection status"""
        return {
            "connected": self.is_token_valid(),
            "has_access_token": bool(self.access_token),
            "has_refresh_token": bool(self.refresh_token),
            "token_expires_at": self.token_expires_at.isoformat() if self.token_expires_at else None,
            "user_info_available": bool(self.user_info),
            "client_id_configured": bool(self.client_id),
            "client_secret_configured": bool(self.client_secret),
        }

    async def get_file(self, file_key: str, access_token: str = None) -> Dict[str, Any]:
        """Get a Figma file"""
        try:
            token = access_token or await self.ensure_valid_token()
            headers = self._get_headers(token)
            
            response = await self.client.get(f"{self.base_url}/files/{file_key}", headers=headers)
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get file: {e}")
            raise HTTPException(status_code=400, detail=f"Failed to get file: {str(e)}")

    async def get_file_nodes(self, file_key: str, node_ids: List[str], access_token: str = None) -> Dict[str, Any]:
        """Get specific nodes from a file"""
        try:
            token = access_token or await self.ensure_valid_token()
            headers = self._get_headers(token)
            params = {"ids": ",".join(node_ids)}
            
            response = await self.client.get(
                f"{self.base_url}/files/{file_key}/nodes",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get file nodes: {e}")
            raise HTTPException(status_code=400, detail=f"Failed to get file nodes: {str(e)}")

    async def get_team_projects(self, team_id: str, access_token: str = None) -> List[Dict[str, Any]]:
        """Get projects from a team"""
        try:
            token = access_token or await self.ensure_valid_token()
            headers = self._get_headers(token)
            
            response = await self.client.get(f"{self.base_url}/teams/{team_id}/projects", headers=headers)
            response.raise_for_status()
            
            data = response.json()
            return data.get("projects", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get team projects: {e}")
            raise HTTPException(status_code=400, detail=f"Failed to get team projects: {str(e)}")

    async def get_project_files(self, project_id: str, access_token: str = None) -> List[Dict[str, Any]]:
        """Get files from a project"""
        try:
            token = access_token or await self.ensure_valid_token()
            headers = self._get_headers(token)
            
            response = await self.client.get(f"{self.base_url}/projects/{project_id}/files", headers=headers)
            response.raise_for_status()
            
            data = response.json()
            return data.get("files", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get project files: {e}")
            raise HTTPException(status_code=400, detail=f"Failed to get project files: {str(e)}")

    async def get_comments(self, file_key: str, access_token: str = None) -> List[Dict[str, Any]]:
        """Get comments from a file"""
        try:
            token = access_token or await self.ensure_valid_token()
            headers = self._get_headers(token)
            
            response = await self.client.get(f"{self.base_url}/files/{file_key}/comments", headers=headers)
            response.raise_for_status()
            
            data = response.json()
            return data.get("comments", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get comments: {e}")
            raise HTTPException(status_code=400, detail=f"Failed to get comments: {str(e)}")

    async def health_check(self) -> Dict[str, Any]:
        """Health check for Figma service"""
        try:
            return {
                "ok": True,
                "status": "healthy",
                "service": "figma",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
            }
        except Exception as e:
            return {
                "ok": False,
                "status": "unhealthy",
                "service": "figma",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

figma_service = FigmaService()

def get_figma_service() -> FigmaService:
    return figma_service
