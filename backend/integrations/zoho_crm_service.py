import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime
import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class ZohoCRMService:
    def __init__(self):
        self.base_url = "https://www.zohoapis.com/crm/v2"
        self.access_token = os.getenv("ZOHO_CRM_ACCESS_TOKEN")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_leads(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Fetch leads from Zoho CRM"""
        try:
            headers = {"Authorization": f"Zoho-oauthtoken {self.access_token}"}
            response = await self.client.get(f"{self.base_url}/Leads", headers=headers)
            response.raise_for_status()
            return response.json().get("data", [])
        except Exception as e:
            logger.error(f"Failed to fetch Zoho CRM leads: {e}")
            return []

    async def create_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new lead in Zoho CRM"""
        try:
            headers = {"Authorization": f"Zoho-oauthtoken {self.access_token}"}
            payload = {"data": [lead_data]}
            response = await self.client.post(f"{self.base_url}/Leads", headers=headers, json=payload)
            response.raise_for_status()
            return response.json().get("data", [{}])[0]
        except Exception as e:
            logger.error(f"Failed to create Zoho CRM lead: {e}")
            raise HTTPException(status_code=500, detail="Zoho CRM Lead creation failed")

    async def get_deals(self) -> List[Dict[str, Any]]:
        """Fetch deals (Opportunities) from Zoho CRM"""
        try:
            headers = {"Authorization": f"Zoho-oauthtoken {self.access_token}"}
            response = await self.client.get(f"{self.base_url}/Deals", headers=headers)
            response.raise_for_status()
            return response.json().get("data", [])
        except Exception as e:
            logger.error(f"Failed to fetch Zoho CRM deals: {e}")
            return []
