
import logging
import os
import base64
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class XeroService:
    """Xero API Service Implementation"""
    
    def __init__(self):
        self.base_url = "https://api.xero.com/api.xro/2.0"
        self.client_id = os.getenv("XERO_CLIENT_ID")
        self.client_secret = os.getenv("XERO_CLIENT_SECRET")
        self.client = httpx.AsyncClient(timeout=30.0)

    def _get_headers(self, access_token: str, tenant_id: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        if tenant_id:
            headers["Xero-tenant-id"] = tenant_id
        return headers

    async def exchange_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        try:
            url = "https://identity.xero.com/connect/token"
            
            # Xero requires Basic Auth with client_id:client_secret for token exchange
            auth_str = f"{self.client_id}:{self.client_secret}"
            b64_auth = base64.b64encode(auth_str.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {b64_auth}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri
            }
            
            response = await self.client.post(url, headers=headers, data=data)
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Xero token exchange failed: {e}")
            raise HTTPException(status_code=400, detail=f"Token exchange failed: {str(e)}")

    async def get_tenants(self, access_token: str) -> List[Dict[str, Any]]:
        """Get connected tenants (organizations)"""
        try:
            url = "https://api.xero.com/connections"
            headers = self._get_headers(access_token)
            
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get tenants: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch tenants: {str(e)}")

    async def get_invoices(self, access_token: str, tenant_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get list of invoices"""
        try:
            url = f"{self.base_url}/Invoices"
            headers = self._get_headers(access_token, tenant_id)
            # Xero doesn't support 'limit' param directly in same way, but we can filter or just take top N
            # For simplicity, we'll just fetch and slice
            
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            invoices = data.get("Invoices", [])
            return invoices[:limit]
        except Exception as e:
            logger.error(f"Failed to get invoices: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch invoices: {str(e)}")

    async def get_contacts(self, access_token: str, tenant_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get list of contacts"""
        try:
            url = f"{self.base_url}/Contacts"
            headers = self._get_headers(access_token, tenant_id)
            
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            contacts = data.get("Contacts", [])
            return contacts[:limit]
        except Exception as e:
            logger.error(f"Failed to get contacts: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch contacts: {str(e)}")
