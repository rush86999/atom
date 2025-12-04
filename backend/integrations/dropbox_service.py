"""
Dropbox Service for ATOM Platform
Provides comprehensive Dropbox file storage integration functionality
"""

import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime
import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class DropboxService:
    def __init__(self):
        self.client_id = os.getenv("DROPBOX_CLIENT_ID")
        self.client_secret = os.getenv("DROPBOX_CLIENT_SECRET")
        self.base_url = "https://api.dropboxapi.com/2"
        self.content_url = "https://content.dropboxapi.com/2"
        self.auth_url = "https://www.dropbox.com/oauth2/authorize"
        self.token_url = "https://api.dropboxapi.com/oauth2/token"
        self.access_token = os.getenv("DROPBOX_ACCESS_TOKEN")
        self.client = httpx.AsyncClient(timeout=60.0)

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
            "redirect_uri": redirect_uri,
            "token_access_type": "offline"
        }
        if state:
            params["state"] = state
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.auth_url}?{query_string}"

    async def exchange_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        try:
            data = {
                "code": code,
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": redirect_uri
            }
            
            response = await self.client.post(self.token_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get("access_token")
            
            return token_data
        except httpx.HTTPError as e:
            logger.error(f"Dropbox token exchange failed: {e}")
            raise HTTPException(
                status_code=400, 
                detail=f"Token exchange failed: {str(e)}"
            )

    async def list_folder(
        self,
        path: str = "",
        access_token: str = None,
        recursive: bool = False,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List files and folders"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            payload = {
                "path": path,
                "recursive": recursive,
                "limit": limit
            }
            
            response = await self.client.post(
                f"{self.base_url}/files/list_folder",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("entries", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to list folder: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to list folder: {str(e)}"
            )

    async def search(
        self,
        query: str,
        access_token: str = None,
        path: str = "",
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Search for files and folders"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            payload = {
                "query": query,
                "options": {
                    "path": path,
                    "max_results": max_results
                }
            }
            
            response = await self.client.post(
                f"{self.base_url}/files/search_v2",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            matches = data.get("matches", [])
            return [match.get("metadata", {}).get("metadata", {}) for match in matches]
        except httpx.HTTPError as e:
            logger.error(f"Failed to search: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to search: {str(e)}"
            )

    async def get_metadata(
        self,
        path: str,
        access_token: str = None
    ) -> Dict[str, Any]:
        """Get metadata for a file or folder"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            payload = {"path": path}
            
            response = await self.client.post(
                f"{self.base_url}/files/get_metadata",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get metadata: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get metadata: {str(e)}"
            )

    async def create_folder(
        self,
        path: str,
        access_token: str = None
    ) -> Dict[str, Any]:
        """Create a new folder"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            payload = {"path": path}
            
            response = await self.client.post(
                f"{self.base_url}/files/create_folder_v2",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to create folder: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to create folder: {str(e)}"
            )

    async def get_account_info(self, access_token: str = None) -> Dict[str, Any]:
        """Get current account information"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            
            response = await self.client.post(
                f"{self.base_url}/users/get_current_account",
                headers=headers
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get account info: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get account info: {str(e)}"
            )

    async def get_space_usage(self, access_token: str = None) -> Dict[str, Any]:
        """Get account space usage"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            
            response = await self.client.post(
                f"{self.base_url}/users/get_space_usage",
                headers=headers
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get space usage: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get space usage: {str(e)}"
            )

    async def health_check(self) -> Dict[str, Any]:
        """Health check for Dropbox service"""
        try:
            return {
                "ok": True,
                "status": "healthy",
                "service": "dropbox",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
            }
        except Exception as e:
            return {
                "ok": False,
                "status": "unhealthy",
                "service": "dropbox",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

# Singleton instance
dropbox_service = DropboxService()

def get_dropbox_service() -> DropboxService:
    """Get Dropbox service instance"""
    return dropbox_service
