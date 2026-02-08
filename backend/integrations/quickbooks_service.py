"""
QuickBooks Service for ATOM Platform
Provides comprehensive QuickBooks accounting integration functionality
"""

from datetime import datetime
import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
import httpx

logger = logging.getLogger(__name__)

class QuickBooksService:
    def __init__(self):
        self.client_id = os.getenv("QUICKBOOKS_CLIENT_ID")
        self.client_secret = os.getenv("QUICKBOOKS_CLIENT_SECRET")
        self.base_url = "https://quickbooks.api.intuit.com/v3"
        self.sandbox_url = "https://sandbox-quickbooks.api.intuit.com/v3"
        self.auth_url = "https://appcenter.intuit.com/connect/oauth2"
        self.token_url = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
        self.access_token = os.getenv("QUICKBOOKS_ACCESS_TOKEN")
        self.realm_id = os.getenv("QUICKBOOKS_REALM_ID")
        self.use_sandbox = os.getenv("QUICKBOOKS_USE_SANDBOX", "false").lower() == "true"
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client connection"""
        await self.client.aclose()

    def _get_api_url(self) -> str:
        """Get the appropriate API URL based on environment"""
        return self.sandbox_url if self.use_sandbox else self.base_url

    def _get_headers(self, access_token: str) -> Dict[str, str]:
        """Get headers for API requests"""
        return {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def get_authorization_url(self, redirect_uri: str, state: str = None, scope: str = "com.intuit.quickbooks.accounting") -> str:
        """Generate OAuth authorization URL"""
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
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
                "redirect_uri": redirect_uri
            }
            
            auth = (self.client_id, self.client_secret)
            headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
            
            response = await self.client.post(
                self.token_url,
                data=data,
                auth=auth,
                headers=headers
            )
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get("access_token")
            self.realm_id = token_data.get("realmId")
            
            return token_data
        except httpx.HTTPError as e:
            logger.error(f"QuickBooks token exchange failed: {e}")
            raise HTTPException(
                status_code=400, 
                detail=f"Token exchange failed: {str(e)}"
            )

    async def get_company_info(self, realm_id: str = None, access_token: str = None) -> Dict[str, Any]:
        """Get company information"""
        try:
            token = access_token or self.access_token
            realm = realm_id or self.realm_id
            
            if not token or not realm:
                raise HTTPException(status_code=401, detail="Not authenticated or missing realm ID")
            
            headers = self._get_headers(token)
            url = f"{self._get_api_url()}/company/{realm}/companyinfo/{realm}"
            
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            return data.get("CompanyInfo", {})
        except httpx.HTTPError as e:
            logger.error(f"Failed to get company info: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get company info: {str(e)}"
            )

    async def get_customers(
        self,
        realm_id: str = None,
        access_token: str = None,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Get customers"""
        try:
            token = access_token or self.access_token
            realm = realm_id or self.realm_id
            
            if not token or not realm:
                raise HTTPException(status_code=401, detail="Not authenticated or missing realm ID")
            
            headers = self._get_headers(token)
            query = f"SELECT * FROM Customer MAXRESULTS {max_results}"
            params = {"query": query}
            
            url = f"{self._get_api_url()}/company/{realm}/query"
            
            response = await self.client.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            return data.get("QueryResponse", {}).get("Customer", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get customers: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get customers: {str(e)}"
            )

    async def get_invoices(
        self,
        realm_id: str = None,
        access_token: str = None,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Get invoices"""
        try:
            token = access_token or self.access_token
            realm = realm_id or self.realm_id
            
            if not token or not realm:
                raise HTTPException(status_code=401, detail="Not authenticated or missing realm ID")
            
            headers = self._get_headers(token)
            query = f"SELECT * FROM Invoice MAXRESULTS {max_results}"
            params = {"query": query}
            
            url = f"{self._get_api_url()}/company/{realm}/query"
            
            response = await self.client.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            return data.get("QueryResponse", {}).get("Invoice", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get invoices: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get invoices: {str(e)}"
            )

    async def get_expenses(
        self,
        realm_id: str = None,
        access_token: str = None,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Get expenses"""
        try:
            token = access_token or self.access_token
            realm = realm_id or self.realm_id
            
            if not token or not realm:
                raise HTTPException(status_code=401, detail="Not authenticated or missing realm ID")
            
            headers = self._get_headers(token)
            query = f"SELECT * FROM Purchase WHERE PaymentType = 'Cash' MAXRESULTS {max_results}"
            params = {"query": query}
            
            url = f"{self._get_api_url()}/company/{realm}/query"
            
            response = await self.client.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            return data.get("QueryResponse", {}).get("Purchase", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get expenses: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get expenses: {str(e)}"
            )

    async def health_check(self) -> Dict[str, Any]:
        """Health check for QuickBooks service"""
        try:
            return {
                "ok": True,
                "status": "healthy",
                "service": "quickbooks",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
            }
        except Exception as e:
            return {
                "ok": False,
                "status": "unhealthy",
                "service": "quickbooks",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

# Singleton instance
quickbooks_service = QuickBooksService()

def get_quickbooks_service() -> QuickBooksService:
    """Get QuickBooks service instance"""
    return quickbooks_service
