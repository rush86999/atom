import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
import httpx

logger = logging.getLogger(__name__)

class WorkdayService:
    """Workday API Service (REST/RaaS focus)"""
    
    def __init__(self):
        self.base_url = os.getenv("WORKDAY_BASE_URL", "https://wd3-impl-services1.workday.com/ccx/service/v1")
        self.tenant = os.getenv("WORKDAY_TENANT")
        self.username = os.getenv("WORKDAY_USERNAME")
        self.password = os.getenv("WORKDAY_PASSWORD")
        self.client = httpx.AsyncClient(timeout=30.0)

    def _get_auth(self) -> tuple:
        if not all([self.username, self.password]):
            return None
        return (self.username, self.password)

    async def get_worker_profile(self, worker_id: str) -> Dict[str, Any]:
        """Get worker profile by ID"""
        try:
            url = f"{self.base_url}/{self.tenant}/workers/{worker_id}"
            auth = self._get_auth()
            
            if not auth:
                # Stub data if no auth
                return {
                    "worker_id": worker_id,
                    "first_name": "John",
                    "last_name": "Doe",
                    "position": "Software Engineer",
                    "status": "Active (MOCK)"
                }
                
            response = await self.client.get(url, auth=auth)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Workday get_worker failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def check_health(self) -> Dict[str, Any]:
        """Check Workday connectivity"""
        return {
            "status": "active" if self.username else "partially_configured",
            "service": "workday",
            "mode": "real" if self.username else "mock"
        }

# Global instance
workday_service = WorkdayService()
