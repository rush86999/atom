"""
Tableau Service for ATOM Platform
Provides comprehensive Tableau analytics and data visualization integration functionality
"""

import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime
import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class TableauService:
    def __init__(self):
        self.client_id = os.getenv("TABLEAU_CLIENT_ID")
        self.client_secret = os.getenv("TABLEAU_CLIENT_SECRET")
        self.server_url = os.getenv("TABLEAU_SERVER_URL", "https://10ax.online.tableau.com")
        self.site_id = os.getenv("TABLEAU_SITE_ID", "")
        self.base_url = f"{self.server_url}/api/3.19"
        self.auth_token = None
        self.site_uuid = None
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client connection"""
        await self.client.aclose()

    def _get_headers(self, auth_token: str = None) -> Dict[str, str]:
        """Get headers for API requests"""
        token = auth_token or self.auth_token
        return {
            "X-Tableau-Auth": token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    async def sign_in(self, username: str, password: str, site_content_url: str = "") -> Dict[str, Any]:
        """Sign in to Tableau Server"""
        try:
            payload = {
                "credentials": {
                    "name": username,
                    "password": password,
                    "site": {"contentUrl": site_content_url}
                }
            }
            
            response = await self.client.post(
                f"{self.base_url}/auth/signin",
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            credentials = data.get("credentials", {})
            
            self.auth_token = credentials.get("token")
            self.site_uuid = credentials.get("site", {}).get("id")
            
            return data
        except httpx.HTTPError as e:
            logger.error(f"Tableau sign in failed: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Sign in failed: {str(e)}"
            )

    async def get_workbooks(self, auth_token: str = None) -> List[Dict[str, Any]]:
        """Get workbooks from Tableau"""
        try:
            token = auth_token or self.auth_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            site_part = f"/sites/{self.site_uuid}" if self.site_uuid else ""
            
            response = await self.client.get(
                f"{self.base_url}{site_part}/workbooks",
                headers=headers
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("workbooks", {}).get("workbook", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get workbooks: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get workbooks: {str(e)}"
            )

    async def get_views(self, auth_token: str = None) -> List[Dict[str, Any]]:
        """Get views from Tableau"""
        try:
            token = auth_token or self.auth_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            site_part = f"/sites/{self.site_uuid}" if self.site_uuid else ""
            
            response = await self.client.get(
                f"{self.base_url}{site_part}/views",
                headers=headers
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("views", {}).get("view", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get views: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get views: {str(e)}"
            )

    async def get_datasources(self, auth_token: str = None) -> List[Dict[str, Any]]:
        """Get data sources from Tableau"""
        try:
            token = auth_token or self.auth_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            site_part = f"/sites/{self.site_uuid}" if self.site_uuid else ""
            
            response = await self.client.get(
                f"{self.base_url}{site_part}/datasources",
                headers=headers
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("datasources", {}).get("datasource", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get datasources: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get datasources: {str(e)}"
            )

    async def health_check(self) -> Dict[str, Any]:
        """Health check for Tableau service"""
        try:
            return {
                "ok": True,
                "status": "healthy",
                "service": "tableau",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
            }
        except Exception as e:
            return {
                "ok": False,
                "status": "unhealthy",
                "service": "tableau",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

tableau_service = TableauService()

def get_tableau_service() -> TableauService:
    return tableau_service
