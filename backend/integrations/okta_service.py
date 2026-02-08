import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
import httpx

logger = logging.getLogger(__name__)

class OktaService:
    """Okta Identity API Service"""
    
    def __init__(self):
        self.org_url = os.getenv("OKTA_ORG_URL")
        self.api_token = os.getenv("OKTA_API_TOKEN")
        self.client = httpx.AsyncClient(timeout=30.0)

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"SSWS {self.api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    async def list_users(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List users from Okta"""
        try:
            if not self.api_token or not self.org_url:
                # Stub data
                return [{
                    "id": "mock_id",
                    "profile": {"firstName": "Admin", "lastName": "User", "email": "admin@example.com"},
                    "status": "ACTIVE (MOCK)"
                }]

            url = f"{self.org_url}/api/v1/users"
            params = {"limit": limit}
            response = await self.client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Okta list_users failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def check_health(self) -> Dict[str, Any]:
        """Check Okta connectivity"""
        return {
            "status": "active" if self.api_token else "partially_configured",
            "service": "okta",
            "mode": "real" if self.api_token else "mock"
        }

# Global instance
okta_service = OktaService()
