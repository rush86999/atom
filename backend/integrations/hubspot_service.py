"""
HubSpot Service for ATOM Platform
Provides comprehensive HubSpot integration functionality
"""

import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime
import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class HubSpotService:
    def __init__(self):
        self.base_url = "https://api.hubapi.com"
        self.access_token = os.getenv("HUBSPOT_ACCESS_TOKEN")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def authenticate(self, client_id: str, client_secret: str, redirect_uri: str, code: str) -> dict:
        """Authenticate with HubSpot OAuth"""
        try:
            token_url = "https://api.hubapi.com/oauth/v1/token"
            data = {
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            }

            response = await self.client.post(token_url, data=data)
            response.raise_for_status()

            token_data = response.json()
            self.access_token = token_data.get("access_token")
            
            return token_data

        except httpx.HTTPError as e:
            logger.error(f"HubSpot authentication failed: {e}")
            raise HTTPException(
                status_code=400, detail=f"Authentication failed: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error during HubSpot authentication: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    async def get_contacts(self, limit: int = 100, offset: int = 0, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get HubSpot contacts"""
        try:
            # Use provided token or fall back to instance token or env
            active_token = token or self.access_token or os.getenv("HUBSPOT_ACCESS_TOKEN")
            
            if not active_token:
                 raise HTTPException(status_code=401, detail="Not authenticated")

            headers = {"Authorization": f"Bearer {active_token}"}
            params = {
                "limit": limit,
                "properties": "email,firstname,lastname,company,phone,createdate,lastmodifieddate,lifecyclestage,hs_lead_status",
            }

            if offset > 0:
                params["after"] = offset

            response = await self.client.get(
                f"{self.base_url}/crm/v3/objects/contacts",
                headers=headers,
                params=params,
            )
            response.raise_for_status()

            data = response.json()
            return data.get("results", [])

        except httpx.HTTPError as e:
            logger.error(f"Failed to get HubSpot contacts: {e}")
            raise HTTPException(
                status_code=400, detail=f"Failed to get contacts: {str(e)}"
            )

    async def get_companies(self, limit: int = 100, offset: int = 0, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get HubSpot companies"""
        try:
            active_token = token or self.access_token or os.getenv("HUBSPOT_ACCESS_TOKEN")
            if not active_token:
                raise HTTPException(status_code=401, detail="Not authenticated")

            headers = {"Authorization": f"Bearer {active_token}"}
            params = {
                "limit": limit,
                "properties": "name,domain,industry,city,state,country,createdate,lastmodifieddate",
            }

            if offset > 0:
                params["after"] = offset

            response = await self.client.get(
                f"{self.base_url}/crm/v3/objects/companies",
                headers=headers,
                params=params,
            )
            response.raise_for_status()

            data = response.json()
            return data.get("results", [])

        except httpx.HTTPError as e:
            logger.error(f"Failed to get HubSpot companies: {e}")
            raise HTTPException(
                status_code=400, detail=f"Failed to get companies: {str(e)}"
            )

    async def get_deals(self, limit: int = 100, offset: int = 0, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get HubSpot deals"""
        try:
            active_token = token or self.access_token or os.getenv("HUBSPOT_ACCESS_TOKEN")
            if not active_token:
                raise HTTPException(status_code=401, detail="Not authenticated")

            headers = {"Authorization": f"Bearer {active_token}"}
            params = {
                "limit": limit,
                "properties": "dealname,amount,dealstage,pipeline,closedate,createdate,lastmodifieddate,hubspot_owner_id",
            }

            if offset > 0:
                params["after"] = offset

            response = await self.client.get(
                f"{self.base_url}/crm/v3/objects/deals", headers=headers, params=params
            )
            response.raise_for_status()

            data = response.json()
            return data.get("results", [])

        except httpx.HTTPError as e:
            logger.error(f"Failed to get HubSpot deals: {e}")
            raise HTTPException(
                status_code=400, detail=f"Failed to get deals: {str(e)}"
            )

    async def get_campaigns(self, limit: int = 100, offset: int = 0, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get HubSpot campaigns"""
        try:
            active_token = token or self.access_token or os.getenv("HUBSPOT_ACCESS_TOKEN")
            if not active_token:
                raise HTTPException(status_code=401, detail="Not authenticated")

            headers = {"Authorization": f"Bearer {active_token}"}
            params = {"limit": limit}

            if offset > 0:
                params["offset"] = offset

            response = await self.client.get(
                f"{self.base_url}/marketing/v3/campaigns",
                headers=headers,
                params=params,
            )
            response.raise_for_status()

            data = response.json()
            return data.get("campaigns", [])

        except httpx.HTTPError as e:
            logger.error(f"Failed to get HubSpot campaigns: {e}")
            raise HTTPException(
                status_code=400, detail=f"Failed to get campaigns: {str(e)}"
            )

    async def search_content(self, query: str, object_type: str = "contact") -> Dict[str, Any]:
        """Search HubSpot content"""
        try:
            if not self.access_token:
                self.access_token = os.getenv("HUBSPOT_ACCESS_TOKEN")
                if not self.access_token:
                    raise HTTPException(status_code=401, detail="Not authenticated")

            headers = {"Authorization": f"Bearer {self.access_token}"}

            search_url = (
                f"{self.base_url}/crm/v3/objects/{object_type}/search"
            )
            payload = {
                "query": query,
                "limit": 50,
                "properties": ["email", "firstname", "lastname", "company", "phone"],
            }

            response = await self.client.post(search_url, headers=headers, json=payload)
            response.raise_for_status()

            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"HubSpot search failed: {e}")
            raise HTTPException(status_code=400, detail=f"Search failed: {str(e)}")

    async def create_contact(self, email: str, first_name: Optional[str] = None, last_name: Optional[str] = None, company: Optional[str] = None, phone: Optional[str] = None, token: Optional[str] = None) -> Dict[str, Any]:
        """Create a new HubSpot contact"""
        try:
            active_token = token or self.access_token or os.getenv("HUBSPOT_ACCESS_TOKEN")
            if not active_token:
                raise HTTPException(status_code=401, detail="Not authenticated")

            headers = {
                "Authorization": f"Bearer {active_token}",
                "Content-Type": "application/json",
            }

            properties = {
                "email": email,
                "firstname": first_name,
                "lastname": last_name,
                "company": company,
                "phone": phone,
            }

            payload = {
                "properties": {k: v for k, v in properties.items() if v is not None}
            }

            response = await self.client.post(
                f"{self.base_url}/crm/v3/objects/contacts",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Failed to create HubSpot contact: {e}")
            raise HTTPException(
                status_code=400, detail=f"Failed to create contact: {str(e)}"
            )

    async def create_company(self, name: str, domain: Optional[str] = None, token: Optional[str] = None) -> Dict[str, Any]:
        """Create a new HubSpot company"""
        try:
            active_token = token or self.access_token or os.getenv("HUBSPOT_ACCESS_TOKEN")
            if not active_token:
                raise HTTPException(status_code=401, detail="Not authenticated")

            headers = {
                "Authorization": f"Bearer {active_token}",
                "Content-Type": "application/json",
            }

            properties = {
                "name": name,
                "domain": domain,
            }

            payload = {
                "properties": {k: v for k, v in properties.items() if v is not None}
            }

            response = await self.client.post(
                f"{self.base_url}/crm/v3/objects/companies",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Failed to create HubSpot company: {e}")
            raise HTTPException(
                status_code=400, detail=f"Failed to create company: {str(e)}"
            )

    async def create_deal(self, name: str, amount: float, company_id: Optional[str] = None, token: Optional[str] = None) -> Dict[str, Any]:
        """Create a new HubSpot deal"""
        try:
            active_token = token or self.access_token or os.getenv("HUBSPOT_ACCESS_TOKEN")
            if not active_token:
                raise HTTPException(status_code=401, detail="Not authenticated")

            headers = {
                "Authorization": f"Bearer {active_token}",
                "Content-Type": "application/json",
            }

            properties = {
                "dealname": name,
                "amount": str(amount),
                "dealstage": "appointmentscheduled", # Default stage
                "pipeline": "default"
            }

            payload = {
                "properties": properties
            }

            if company_id:
                payload["associations"] = [
                    {
                        "to": {"id": company_id},
                        "types": [
                            {
                                "associationCategory": "HUBSPOT_DEFINED",
                                "associationTypeId": 5 # deal_to_company
                            }
                        ]
                    }
                ]

            response = await self.client.post(
                f"{self.base_url}/crm/v3/objects/deals",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Failed to create HubSpot deal: {e}")
            raise HTTPException(
                status_code=400, detail=f"Failed to create deal: {str(e)}"
            )

    async def health_check(self) -> dict:
        """Health check for HubSpot service"""
        try:
            # Basic health check - verify service can be initialized
            return {
                "ok": True,
                "status": "healthy",
                "service": "hubspot",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
            }
        except Exception as e:
            return {
                "ok": False,
                "status": "unhealthy",
                "service": "hubspot",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

# Singleton instance for global access
hubspot_service = HubSpotService()

def get_hubspot_service() -> HubSpotService:
    """Get HubSpot service instance"""
    return hubspot_service