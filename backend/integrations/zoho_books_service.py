from datetime import datetime
import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
import httpx

logger = logging.getLogger(__name__)

class ZohoBooksService:
    """Zoho Books API Service Implementation"""
    
    def __init__(self):
        self.base_url = "https://www.zohoapis.com/books/v3"
        self.client_id = os.getenv("ZOHO_CLIENT_ID")
        self.client_secret = os.getenv("ZOHO_CLIENT_SECRET")
        self.client = httpx.AsyncClient(timeout=30.0)

    def _get_headers(self, access_token: str, organization_id: str) -> Dict[str, str]:
        return {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    async def exchange_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access and refresh tokens"""
        try:
            url = "https://accounts.zoho.com/oauth/v2/token"
            data = {
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": redirect_uri,
                "code": code
            }
            
            response = await self.client.post(url, data=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Zoho token exchange failed: {e}")
            raise HTTPException(status_code=400, detail=f"Zoho token exchange failed: {str(e)}")

    async def get_organizations(self, access_token: str) -> List[Dict[str, Any]]:
        """Get connected Zoho organizations"""
        try:
            url = f"{self.base_url}/organizations"
            headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            return response.json().get("organizations", [])
        except Exception as e:
            logger.error(f"Failed to fetch Zoho organizations: {e}")
            return []

    async def get_chart_of_accounts(self, access_token: str, organization_id: str) -> List[Dict[str, Any]]:
        """Fetch CoA from Zoho"""
        try:
            url = f"{self.base_url}/chartofaccounts"
            headers = self._get_headers(access_token, organization_id)
            params = {"organization_id": organization_id}
            response = await self.client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json().get("chartofaccounts", [])
        except Exception as e:
            logger.error(f"Failed to fetch Zoho CoA: {e}")
            return []

    async def get_bank_transactions(self, access_token: str, organization_id: str, account_id: str) -> List[Dict[str, Any]]:
        """Fetch bank transactions from Zoho"""
        try:
            url = f"{self.base_url}/banktransactions"
            headers = self._get_headers(access_token, organization_id)
            params = {
                "organization_id": organization_id,
                "account_id": account_id
            }
            response = await self.client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json().get("banktransactions", [])
        except Exception as e:
            logger.error(f"Failed to fetch Zoho transactions: {e}")
            return []

    async def create_contact(self, access_token: str, organization_id: str, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a customer in Zoho Books"""
        try:
            url = f"{self.base_url}/contacts"
            headers = self._get_headers(access_token, organization_id)
            params = {"organization_id": organization_id}
            response = await self.client.post(url, headers=headers, params=params, json=contact_data)
            response.raise_for_status()
            return response.json().get("contact", {})
        except Exception as e:
            logger.error(f"Failed to create Zoho contact: {e}")
            raise HTTPException(status_code=500, detail="Zoho Contact creation failed")

    async def create_invoice(self, access_token: str, organization_id: str, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create an invoice in Zoho Books"""
        try:
            url = f"{self.base_url}/invoices"
            headers = self._get_headers(access_token, organization_id)
            params = {"organization_id": organization_id}
            response = await self.client.post(url, headers=headers, params=params, json=invoice_data)
            response.raise_for_status()
            return response.json().get("invoice", {})
        except Exception as e:
            logger.error(f"Failed to create Zoho invoice: {e}")
            raise HTTPException(status_code=500, detail="Zoho Invoice creation failed")
