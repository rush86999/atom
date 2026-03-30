"""
ClickUp Integration Adapter

Provides a unified interface for ClickUp services within the IntegrationFactory.
"""

import logging
import os
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class ClickUpAdapter:
    """
    Adapter for ClickUp OAuth integration.
    """

    def __init__(self, db=None, workspace_id: str = None):
        self.db = db
        self.workspace_id = workspace_id
        self.service_name = "clickup"
        self.base_url = "https://api.clickup.com/api/v2"
        
        # OAuth credentials from environment
        self.client_id = os.getenv("CLICKUP_CLIENT_ID")
        self.client_secret = os.getenv("CLICKUP_CLIENT_SECRET")
        
        # In a real scenario, this would be fetched from UserConnection
        self._access_token: Optional[str] = os.getenv("CLICKUP_ACCESS_TOKEN")

    async def test_connection(self) -> bool:
        """Test the ClickUp API connection"""
        if not self._access_token:
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/user",
                    headers={"Authorization": self._access_token}
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"ClickUp connection test failed: {e}")
            return False

    async def get_data(self, data_type: str, query: str = None, **kwargs) -> Dict[str, Any]:
        """
        Generic method to fetch data from ClickUp.
        
        Supported data_types:
        - teams: Get workspaces
        - spaces: Get spaces in a team (requires team_id)
        - tasks: Get tasks in a list (requires list_id)
        - user: Get authorized user info
        """
        if not self._access_token:
            raise ValueError("ClickUp access token not configured")

        async with httpx.AsyncClient() as client:
            headers = {"Authorization": self._access_token}
            
            if data_type == "teams":
                response = await client.get(f"{self.base_url}/team", headers=headers)
                response.raise_for_status()
                return {"ok": True, "data": response.json().get("teams", [])}
            
            elif data_type == "spaces":
                team_id = query or kwargs.get("team_id")
                if not team_id:
                    raise ValueError("team_id is required for spaces")
                response = await client.get(f"{self.base_url}/team/{team_id}/space", headers=headers)
                response.raise_for_status()
                return {"ok": True, "data": response.json().get("spaces", [])}
            
            elif data_type == "tasks":
                list_id = query or kwargs.get("list_id")
                if not list_id:
                    raise ValueError("list_id is required for tasks")
                response = await client.get(f"{self.base_url}/list/{list_id}/task", headers=headers)
                response.raise_for_status()
                return {"ok": True, "data": response.json().get("tasks", [])}
            
            elif data_type == "user":
                response = await client.get(f"{self.base_url}/user", headers=headers)
                response.raise_for_status()
                return {"ok": True, "data": response.json().get("user")}
            
            else:
                raise ValueError(f"Unsupported data type for ClickUp: {data_type}")
