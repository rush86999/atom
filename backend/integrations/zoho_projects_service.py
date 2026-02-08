from datetime import datetime
import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
import httpx

logger = logging.getLogger(__name__)

class ZohoProjectsService:
    """Zoho Projects API Service Implementation"""
    
    def __init__(self):
        self.base_url = "https://projectsapi.zoho.com/restapi/v1"
        self.client_id = os.getenv("ZOHO_CLIENT_ID")
        self.client_secret = os.getenv("ZOHO_CLIENT_SECRET")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_portals(self, access_token: str) -> List[Dict[str, Any]]:
        """Get connected Zoho Projects portals"""
        try:
            url = f"{self.base_url}/portals/"
            headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            return response.json().get("portals", [])
        except Exception as e:
            logger.error(f"Failed to fetch Zoho Projects portals: {e}")
            return []

    async def get_projects(self, access_token: str, portal_id: str) -> List[Dict[str, Any]]:
        """Fetch projects within a portal"""
        try:
            url = f"{self.base_url}/portal/{portal_id}/projects/"
            headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            return response.json().get("projects", [])
        except Exception as e:
            logger.error(f"Failed to fetch Zoho projects: {e}")
            return []

    async def get_tasks(self, access_token: str, portal_id: str, project_id: str) -> List[Dict[str, Any]]:
        """Fetch tasks for a specific project"""
        try:
            url = f"{self.base_url}/portal/{portal_id}/projects/{project_id}/tasks/"
            headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            return response.json().get("tasks", [])
        except Exception as e:
            logger.error(f"Failed to fetch Zoho tasks: {e}")
            return []

    async def get_all_active_tasks(self, access_token: str, portal_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch all tasks across all projects in a portal"""
        try:
            # First get projects
            projects = await self.get_projects(access_token, portal_id)
            all_tasks = []
            
            # Fetch tasks from each project until limit is reached
            for project in projects:
                if len(all_tasks) >= limit:
                    break
                project_id = project.get("id_string")
                tasks = await self.get_tasks(access_token, portal_id, project_id)
                
                # Add project name to each task for UI
                for task in tasks:
                    task["project_name"] = project.get("name")
                    all_tasks.append(task)
            
            return all_tasks[:limit]
        except Exception as e:
            logger.error(f"Failed to fetch all Zoho tasks: {e}")
            return []
