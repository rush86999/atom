"""
Plaid Service for ATOM Platform
Provides comprehensive Plaid banking and financial data integration functionality
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class PlaidService:
    def __init__(self):
        self.client_id = os.getenv("PLAID_CLIENT_ID")
        self.secret = os.getenv("PLAID_SECRET")
        self.environment = os.getenv("PLAID_ENVIRONMENT", "sandbox")
        
        # Set base URL based on environment
        env_urls = {
            "sandbox": "https://sandbox.plaid.com",
            "development": "https://development.plaid.com",
            "production": "https://production.plaid.com"
        }
        self.base_url = env_urls.get(self.environment, env_urls["sandbox"])
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client connection"""
        await self.client.aclose()

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        return {
            "Content-Type": "application/json"
        }

    def _get_auth_payload(self) -> Dict[str, str]:
        """Get authentication payload for requests"""
        return {
            "client_id": self.client_id,
            "secret": self.secret
        }

    async def create_link_token(
        self,
        user_id: str,
        client_name: str = "ATOM Platform",
        country_codes: List[str] = None,
        language: str = "en",
        products: List[str] = None
    ) -> Dict[str, Any]:
        """Create a Link token for Plaid Link initialization"""
        try:
            if not self.client_id or not self.secret:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            
            payload = {
                **self._get_auth_payload(),
                "client_name": client_name,
                "user": {"client_user_id": user_id},
                "products": products or ["auth", "transactions"],
                "country_codes": country_codes or ["US"],
                "language": language
            }
            
            response = await self.client.post(
                f"{self.base_url}/link/token/create",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to create link token: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to create link token: {str(e)}"
            )

    async def exchange_public_token(self, public_token: str) -> Dict[str, Any]:
        """Exchange a public token for an access token"""
        try:
            if not self.client_id or not self.secret:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            payload = {
                **self._get_auth_payload(),
                "public_token": public_token
            }
            
            response = await self.client.post(
                f"{self.base_url}/item/public_token/exchange",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to exchange public token: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to exchange public token: {str(e)}"
            )

    async def get_accounts(self, access_token: str) -> List[Dict[str, Any]]:
        """Get accounts for an item"""
        try:
            if not self.client_id or not self.secret:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            payload = {
                **self._get_auth_payload(),
                "access_token": access_token
            }
            
            response = await self.client.post(
                f"{self.base_url}/accounts/get",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("accounts", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get accounts: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get accounts: {str(e)}"
            )

    async def get_balance(self, access_token: str) -> Dict[str, Any]:
        """Get real-time balance for accounts"""
        try:
            if not self.client_id or not self.secret:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            payload = {
                **self._get_auth_payload(),
                "access_token": access_token
            }
            
            response = await self.client.post(
                f"{self.base_url}/accounts/balance/get",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get balance: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get balance: {str(e)}"
            )

    async def get_transactions(
        self,
        access_token: str,
        start_date: str,
        end_date: str,
        count: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get transactions for an item"""
        try:
            if not self.client_id or not self.secret:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            payload = {
                **self._get_auth_payload(),
                "access_token": access_token,
                "start_date": start_date,
                "end_date": end_date,
                "options": {
                    "count": count,
                    "offset": offset
                }
            }
            
            response = await self.client.post(
                f"{self.base_url}/transactions/get",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get transactions: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get transactions: {str(e)}"
            )

    async def get_identity(self, access_token: str) -> Dict[str, Any]:
        """Get identity information for accounts"""
        try:
            if not self.client_id or not self.secret:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            payload = {
                **self._get_auth_payload(),
                "access_token": access_token
            }
            
            response = await self.client.post(
                f"{self.base_url}/identity/get",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get identity: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get identity: {str(e)}"
            )

    async def remove_item(self, access_token: str) -> Dict[str, Any]:
        """Remove an item (disconnect bank connection)"""
        try:
            if not self.client_id or not self.secret:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            payload = {
                **self._get_auth_payload(),
                "access_token": access_token
            }
            
            response = await self.client.post(
                f"{self.base_url}/item/remove",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to remove item: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to remove item: {str(e)}"
            )

    async def health_check(self) -> Dict[str, Any]:
        """Health check for Plaid service"""
        try:
            return {
                "ok": True,
                "status": "healthy",
                "service": "plaid",
                "environment": self.environment,
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
            }
        except Exception as e:
            return {
                "ok": False,
                "status": "unhealthy",
                "service": "plaid",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

plaid_service = PlaidService()

def get_plaid_service() -> PlaidService:
    return plaid_service
