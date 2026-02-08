"""
Asana Real API Integration Service
Connects unified task endpoints to real Asana workspace
"""

from datetime import datetime
import logging
import os
from typing import Any, Dict, List, Optional
import aiohttp

logger = logging.getLogger(__name__)

class AsanaRealService:
    """Service for real Asana API interactions"""
    
    BASE_URL = "https://app.asana.com/api/1.0"
    
    def __init__(self, access_token: str = None, workspace_gid: str = None):
        # Get from environment or parameter
        self.access_token = access_token or os.getenv("ASANA_ACCESS_TOKEN", "2/1211551477617044/1211959900544452:04904fb3621a011e810dc1c21ef41890")
        self.workspace_gid = workspace_gid or "1211551477617056"  # Default workspace
        
    async def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Make authenticated request to Asana API"""
        url = f"{self.BASE_URL}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                if method == "GET":
                    async with session.get(url, headers=headers) as response:
                        result = await response.json()
                        return result
                elif method == "POST":
                    async with session.post(url, headers=headers, json=data) as response:
                        result = await response.json()
                        return result
                elif method == "PUT":
                    async with session.put(url, headers=headers, json=data) as response:
                        result = await response.json()
                        return result
                elif method == "DELETE":
                    async with session.delete(url, headers=headers) as response:
                        return {"success": True}
            except Exception as e:
                logger.error(f"Asana API request failed: {e}")
                return {"errors": [{"message": str(e)}]}
    
    async def get_tasks(self, limit: int = 100, project_gid: str = None) -> List[Dict]:
        """Get tasks from Asana workspace"""
        if project_gid:
            endpoint = f"projects/{project_gid}/tasks?limit={limit}&opt_fields=name,notes,completed,due_on,assignee,tags,created_at,modified_at"
        else:
            endpoint = f"workspaces/{self.workspace_gid}/tasks/search?limit={limit}&opt_fields=name,notes,completed,due_on,assignee,tags,created_at,modified_at"
        
        result = await self._make_request("GET", endpoint)
        
        if "data" in result:
            # Convert Asana tasks to unified format
            return [self._convert_asana_to_unified(task) for task in result["data"]]
        return []
    
    async def create_task(self, task_data: Dict) -> Dict:
        """Create task in Asana"""
        asana_data = {
            "data": {
                "name": task_data.get("title"),
                "notes": task_data.get("description", ""),
                "workspace": self.workspace_gid,
            }
        }
        
        # Add optional fields
        if task_data.get("dueDate"):
            asana_data["data"]["due_on"] = task_data["dueDate"].split("T")[0]
        
        if task_data.get("project"):
            asana_data["data"]["projects"] = [task_data["project"]]
        
        result = await self._make_request("POST", "tasks", asana_data)
        
        if "data" in result:
            return self._convert_asana_to_unified(result["data"])
        return None
    
    async def update_task(self, task_id: str, updates: Dict) -> Dict:
        """Update task in Asana"""
        asana_updates = {"data": {}}
        
        if "title" in updates:
            asana_updates["data"]["name"] = updates["title"]
        if "description" in updates:
            asana_updates["data"]["notes"] = updates["description"]
        if "status" in updates:
            asana_updates["data"]["completed"] = updates["status"] == "completed"
        if "dueDate" in updates:
            asana_updates["data"]["due_on"] = updates["dueDate"].split("T")[0]
        
        result = await self._make_request("PUT", f"tasks/{task_id}", asana_updates)
        
        if "data" in result:
            return self._convert_asana_to_unified(result["data"])
        return None
    
    async def delete_task(self, task_id: str) -> bool:
        """Delete task from Asana"""
        result = await self._make_request("DELETE", f"tasks/{task_id}")
        return result.get("success", False)
    
    async def get_projects(self, limit: int = 100) -> List[Dict]:
        """Get projects from Asana workspace"""
        endpoint = f"workspaces/{self.workspace_gid}/projects?limit={limit}&opt_fields=name,notes,color,created_at,modified_at"
        
        result = await self._make_request("GET", endpoint)
        
        if "data" in result:
            return [self._convert_asana_project_to_unified(proj) for proj in result["data"]]
        return []
    
    async def create_project(self, project_data: Dict) -> Dict:
        """Create project in Asana"""
        asana_data = {
            "data": {
                "name": project_data.get("name"),
                "notes": project_data.get("description", ""),
                "workspace": self.workspace_gid,
                "color": project_data.get("color", "blue"),
            }
        }
        
        result = await self._make_request("POST", "projects", asana_data)
        
        if "data" in result:
            return self._convert_asana_project_to_unified(result["data"])
        return None
    
    def _convert_asana_to_unified(self, asana_task: Dict) -> Dict:
        """Convert Asana task format to unified format"""
        status = "completed" if asana_task.get("completed") else "todo"
        
        return {
            "id": asana_task.get("gid"),
            "title": asana_task.get("name"),
            "description": asana_task.get("notes", ""),
            "dueDate": asana_task.get("due_on", datetime.now().isoformat()) + "T00:00:00Z" if asana_task.get("due_on") else datetime.now().isoformat(),
            "priority": "medium",  # Asana doesn't have priority by default
            "status": status,
            "platform": "asana",
            "tags": [tag.get("name") for tag in asana_task.get("tags", [])],
            "assignee": asana_task.get("assignee", {}).get("name") if asana_task.get("assignee") else None,
            "createdAt": asana_task.get("created_at", datetime.now().isoformat()),
            "updatedAt": asana_task.get("modified_at", datetime.now().isoformat()),
            "color": "#3182CE",
        }
    
    def _convert_asana_project_to_unified(self, asana_project: Dict) -> Dict:
        """Convert Asana project format to unified format"""
        color_map = {
            "dark-pink": "#D53F8C",
            "dark-green": "#38A169",
            "dark-blue": "#3182CE",
            "dark-red": "#E53E3E",
            "dark-teal": "#319795",
            "dark-brown": "#8B4513",
            "dark-orange": "#DD6B20",
            "dark-purple": "#805AD5",
            "dark-warm-gray": "#718096",
        }
        
        asana_color = asana_project.get("color", "dark-blue")
        unified_color = color_map.get(asana_color, "#3182CE")
        
        return {
            "id": asana_project.get("gid"),
            "name": asana_project.get("name"),
            "description": asana_project.get("notes", ""),
            "color": unified_color,
            "tasks": [],  # Will be populated separately
            "progress": 0,  # Will be calculated from tasks
        }

# Singleton instance
asana_real_service = AsanaRealService()
