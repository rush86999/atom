"""
GoToMeeting Integration Adapter

Provides a unified interface for GoToMeeting services within the IntegrationFactory.
"""

import logging
import os
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class GotoMeetingAdapter:
    """
    Adapter for GoToMeeting OAuth integration.
    """

    def __init__(self, db=None, workspace_id: str = None):
        self.db = db
        self.workspace_id = workspace_id
        self.service_name = "gotomeeting"
        self.base_url = "https://api.getgo.com/G2M/rest/v1"
        
        # In a real scenario, this would be fetched from UserConnection
        self._access_token: Optional[str] = os.getenv("GOTOMEETING_ACCESS_TOKEN")

    async def test_connection(self) -> bool:
        """Test the GoToMeeting API connection"""
        if not self._access_token:
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/meetings",
                    headers={"Authorization": f"Bearer {self._access_token}"}
                )
                return response.status_code in [200, 204]
        except Exception as e:
            logger.error(f"GoToMeeting connection test failed: {e}")
            return False

    async def get_data(self, data_type: str, query: str = None, **kwargs) -> Dict[str, Any]:
        """
        Generic method to fetch data from GoToMeeting.
        
        Supported data_types:
        - meetings: Get all meetings
        - upcoming: Get upcoming meetings
        - recordings: Get recordings
        """
        if not self._access_token:
            raise ValueError("GoToMeeting access token not configured")

        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json"
            }
            
            if data_type == "meetings":
                response = await client.get(f"{self.base_url}/meetings", headers=headers)
                response.raise_for_status()
                return {"ok": True, "data": response.json() if response.status_code != 204 else []}
            
            elif data_type == "upcoming":
                response = await client.get(f"{self.base_url}/upcomingMeetings", headers=headers)
                response.raise_for_status()
                return {"ok": True, "data": response.json() if response.status_code != 204 else []}
            
            elif data_type == "recordings":
                response = await client.get(f"{self.base_url}/recordings", headers=headers)
                response.raise_for_status()
                return {"ok": True, "data": response.json() if response.status_code != 204 else []}
            
            else:
                raise ValueError(f"Unsupported data type for GoToMeeting: {data_type}")
