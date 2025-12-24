import logging
import os
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

class ZohoInventoryService:
    def __init__(self):
        self.base_url = "https://inventory.zoho.com/api/v1"
        self.access_token = os.getenv("ZOHO_INVENTORY_ACCESS_TOKEN")
        self.organization_id = os.getenv("ZOHO_ORG_ID")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_items(self) -> List[Dict[str, Any]]:
        """Fetch items list for pricing and availability checks"""
        try:
            params = {"organization_id": self.organization_id}
            headers = {"Authorization": f"Zoho-oauthtoken {self.access_token}"}
            response = await self.client.get(f"{self.base_url}/items", headers=headers, params=params)
            response.raise_for_status()
            return response.json().get("items", [])
        except Exception as e:
            logger.error(f"Failed to fetch Zoho Inventory items: {e}")
            return []

    async def check_stock(self, item_id: str) -> Dict[str, Any]:
        """Check current stock levels for an item"""
        try:
            params = {"organization_id": self.organization_id}
            headers = {"Authorization": f"Zoho-oauthtoken {self.access_token}"}
            response = await self.client.get(f"{self.base_url}/items/{item_id}", headers=headers, params=params)
            response.raise_for_status()
            item = response.json().get("item", {})
            return {
                "item_id": item_id,
                "name": item.get("name"),
                "stock_on_hand": item.get("stock_on_hand", 0),
                "available_stock": item.get("available_stock", 0)
            }
        except Exception as e:
            logger.error(f"Failed to check stock for {item_id}: {e}")
            return {"error": str(e)}
