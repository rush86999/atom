import logging
import os
from typing import Any, Dict, List, Optional
import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class WebexService:
    """Cisco Webex API Service"""
    
    def __init__(self):
        self.base_url = "https://webexapis.com/v1"
        self.access_token = os.getenv("WEBEX_ACCESS_TOKEN")
        self.client = httpx.AsyncClient(timeout=30.0)

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    async def list_rooms(self) -> List[Dict[str, Any]]:
        """List Webex rooms (now called Spaces)"""
        try:
            if not self.access_token:
                # Stub data
                return [{
                    "id": "mock_room_id",
                    "title": "Strategy Room (MOCK)",
                    "type": "group",
                    "isLocked": False
                }]

            url = f"{self.base_url}/rooms"
            response = await self.client.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.json().get("items", [])
        except Exception as e:
            logger.error(f"Webex list_rooms failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def check_health(self) -> Dict[str, Any]:
        """Check Webex connectivity"""
        return {
            "status": "active" if self.access_token else "partially_configured",
            "service": "webex",
            "mode": "real" if self.access_token else "mock"
        }

# Global instance
webex_service = WebexService()
