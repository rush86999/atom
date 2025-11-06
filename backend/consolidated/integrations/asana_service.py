"""
Comprehensive Asana API Integration Service
Builds on the successful OAuth implementation to provide full Asana functionality
"""

import os
import logging
import requests
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class AsanaService:
    """Complete Asana API integration service"""

    def __init__(self):
        self.api_base_url = "https://app.asana.com/api/1.0"
        self.timeout = 30
        self.max_retries = 3

        # Load configuration from environment
        self.client_id = os.getenv("ASANA_CLIENT_ID")
        self.client_secret = os.getenv("ASANA_CLIENT_SECRET")
        self.redirect_uri = os.getenv(
            "ASANA_REDIRECT_URI", "http://localhost:8000/api/auth/asana/callback"
        )

        logger.info(f"AsanaService initialized with client_id: {self.client_id[:8]}...")

    def _make_request(
        self,
        method: str,
        endpoint: str,
        access_token: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict:
        """Make authenticated request to Asana API"""
        url = f"{self.api_base_url}/{endpoint.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        for attempt in range(self.max_retries):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                    params=params,
                    timeout=self.timeout,
                )

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    logger.warning("Asana API returned 401 - token may be expired")
                    raise PermissionError("Access token expired or invalid")
                elif response.status_code == 429:
                    logger.warning("Asana API rate limit reached")
                    if attempt < self.max_retries - 1:
                        wait_time = 2**attempt  # Exponential backoff
                        logger.info(f"Rate limited, waiting {wait_time}s before retry")
                        import time

                        time.sleep(wait_time)
                        continue
                    else:
                        raise ConnectionError("Rate limit exceeded after retries")
                else:
                    logger.error(
                        f"Asana API error {response.status_code}: {response.text}"
                    )
                    response.raise_for_status()

            except requests.exceptions.RequestException as e:
                logger.error(f"Asana API request failed (attempt {attempt + 1}): {e}")
                if attempt == self.max_retries - 1:
                    raise

        return {"data": None, "error": "Max retries exceeded"}

    async def get_user_profile(self, access_token: str) -> Dict:
        """Get current Asana user profile"""
        try:
            result = self._make_request("GET", "/users/me", access_token)
            user_data = result.get("data", {})

            return {
                "ok": True,
                "user": {
                    "gid": user_data.get("gid"),
                    "name": user_data.get("name"),
                    "email": user_data.get("email"),
                    "photo": user_data.get("photo"),
                    "workspaces": user_data.get("workspaces", []),
                },
            }
        except Exception as e:
            logger.error(f"Failed to get user profile: {e}")
            return {"ok": False, "error": str(e)}

    async def get_workspaces(self, access_token: str) -> Dict:
        """Get user's Asana workspaces"""
        try:
            result = self._make_request("GET", "/workspaces", access_token)
            workspaces = result.get("data", [])

            return {
                "ok": True,
                "workspaces": [
                    {
                        "gid": ws.get("gid"),
                        "name": ws.get("name"),
                        "is_organization": ws.get("is_organization", False),
                    }
                    for ws in workspaces
                ],
            }
        except Exception as e:
            logger.error(f"Failed to get workspaces: {e}")
            return {"ok": False, "error": str(e)}

    async def get_projects(
        self,
        access_token: str,
        workspace_gid: str = None,
        team_gid: str = None,
        limit: int = 50,
    ) -> Dict:
        """Get projects from workspace or team"""
        try:
            params = {
                "limit": limit,
                "opt_fields": "name,notes,color,created_at,modified_at",
            }

            if workspace_gid:
                params["workspace"] = workspace_gid
            elif team_gid:
                params["team"] = team_gid

            result = self._make_request("GET", "/projects", access_token, params=params)
            projects = result.get("data", [])

            return {
                "ok": True,
                "projects": [
                    {
                        "gid": project.get("gid"),
                        "name": project.get("name"),
                        "notes": project.get("notes"),
                        "color": project.get("color"),
                        "created_at": project.get("created_at"),
                        "modified_at": project.get("modified_at"),
                        "workspace_gid": project.get("workspace", {}).get("gid"),
                        "team_gid": project.get("team", {}).get("gid"),
                    }
                    for project in projects
                ],
            }
        except Exception as e:
            logger.error(f"Failed to get projects: {e}")
            return {"ok": False, "error": str(e)}

    async def get_tasks(
        self,
        access_token: str,
        project_gid: str = None,
        workspace_gid: str = None,
        assignee: str = None,
        completed_since: str = None,
        limit: int = 50,
    ) -> Dict:
        """Get tasks from project or workspace"""
        try:
            params = {
                "limit": limit,
                "opt_fields": "name,notes,completed,due_on,assignee,projects,created_at,modified_at",
            }

            if project_gid:
                params["project"] = project_gid
            elif workspace_gid:
                params["workspace"] = workspace_gid

            if assignee:
                params["assignee"] = assignee
            if completed_since:
                params["completed_since"] = completed_since

            result = self._make_request("GET", "/tasks", access_token, params=params)
            tasks = result.get("data", [])

            return {
                "ok": True,
                "tasks": [
                    {
                        "gid": task.get("gid"),
                        "name": task.get("name"),
                        "notes": task.get("notes"),
                        "completed": task.get("completed", False),
                        "due_on": task.get("due_on"),
                        "assignee": task.get("assignee", {}).get("gid")
                        if task.get("assignee")
                        else None,
                        "assignee_name": task.get("assignee", {}).get("name")
                        if task.get("assignee")
                        else None,
                        "projects": [p.get("gid") for p in task.get("projects", [])],
                        "created_at": task.get("created_at"),
                        "modified_at": task.get("modified_at"),
                    }
                    for task in tasks
                ],
            }
        except Exception as e:
            logger.error(f"Failed to get tasks: {e}")
            return {"ok": False, "error": str(e)}

    async def create_task(self, access_token: str, task_data: Dict) -> Dict:
        """Create a new task in Asana"""
        try:
            required_fields = ["name"]
            for field in required_fields:
                if not task_data.get(field):
                    return {"ok": False, "error": f"Missing required field: {field}"}

            # Prepare task creation data
            create_data = {
                "name": task_data["name"],
                "notes": task_data.get("description", ""),
                "completed": task_data.get("completed", False),
            }

            # Add optional fields
            if task_data.get("due_on"):
                create_data["due_on"] = task_data["due_on"]
            if task_data.get("assignee"):
                create_data["assignee"] = task_data["assignee"]
            if task_data.get("projects"):
                create_data["projects"] = task_data["projects"]
            if task_data.get("workspace"):
                create_data["workspace"] = task_data["workspace"]

            result = self._make_request(
                "POST", "/tasks", access_token, data={"data": create_data}
            )
            task = result.get("data", {})

            return {
                "ok": True,
                "task": {
                    "gid": task.get("gid"),
                    "name": task.get("name"),
                    "notes": task.get("notes"),
                    "completed": task.get("completed", False),
                    "due_on": task.get("due_on"),
                    "assignee": task.get("assignee", {}).get("gid")
                    if task.get("assignee")
                    else None,
                    "projects": [p.get("gid") for p in task.get("projects", [])],
                    "created_at": task.get("created_at"),
                    "modified_at": task.get("modified_at"),
                    "url": f"https://app.asana.com/0/{task.get('projects', [{}])[0].get('gid', '0')}/{task.get('gid')}",
                },
                "message": "Task created successfully",
            }
        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            return {"ok": False, "error": str(e)}

    async def update_task(
        self, access_token: str, task_gid: str, updates: Dict
    ) -> Dict:
        """Update an existing task"""
        try:
            result = self._make_request(
                "PUT", f"/tasks/{task_gid}", access_token, data={"data": updates}
            )
            task = result.get("data", {})

            return {
                "ok": True,
                "task": {
                    "gid": task.get("gid"),
                    "name": task.get("name"),
                    "notes": task.get("notes"),
                    "completed": task.get("completed", False),
                    "due_on": task.get("due_on"),
                    "assignee": task.get("assignee", {}).get("gid")
                    if task.get("assignee")
                    else None,
                    "modified_at": task.get("modified_at"),
                },
                "message": "Task updated successfully",
            }
        except Exception as e:
            logger.error(f"Failed to update task {task_gid}: {e}")
            return {"ok": False, "error": str(e)}

    async def get_teams(
        self, access_token: str, workspace_gid: str, limit: int = 50
    ) -> Dict:
        """Get teams in a workspace"""
        try:
            params = {"limit": limit, "workspace": workspace_gid}
            result = self._make_request("GET", "/teams", access_token, params=params)
            teams = result.get("data", [])

            return {
                "ok": True,
                "teams": [
                    {
                        "gid": team.get("gid"),
                        "name": team.get("name"),
                        "description": team.get("description"),
                        "organization": team.get("organization", {}).get("gid"),
                    }
                    for team in teams
                ],
            }
        except Exception as e:
            logger.error(f"Failed to get teams: {e}")
            return {"ok": False, "error": str(e)}

    async def get_users(
        self, access_token: str, workspace_gid: str, limit: int = 50
    ) -> Dict:
        """Get users in a workspace"""
        try:
            params = {"limit": limit, "workspace": workspace_gid}
            result = self._make_request("GET", "/users", access_token, params=params)
            users = result.get("data", [])

            return {
                "ok": True,
                "users": [
                    {
                        "gid": user.get("gid"),
                        "name": user.get("name"),
                        "email": user.get("email"),
                        "photo": user.get("photo"),
                    }
                    for user in users
                ],
            }
        except Exception as e:
            logger.error(f"Failed to get users: {e}")
            return {"ok": False, "error": str(e)}

    async def search_tasks(
        self, access_token: str, workspace_gid: str, query: str, limit: int = 20
    ) -> Dict:
        """Search for tasks in workspace"""
        try:
            params = {
                "workspace": workspace_gid,
                "text": query,
                "limit": limit,
                "opt_fields": "name,notes,completed,projects,assignee",
            }

            result = self._make_request(
                "GET", "/tasks/search", access_token, params=params
            )
            tasks = result.get("data", [])

            return {
                "ok": True,
                "tasks": [
                    {
                        "gid": task.get("gid"),
                        "name": task.get("name"),
                        "notes": task.get("notes"),
                        "completed": task.get("completed", False),
                        "assignee": task.get("assignee", {}).get("gid")
                        if task.get("assignee")
                        else None,
                        "projects": [p.get("gid") for p in task.get("projects", [])],
                    }
                    for task in tasks
                ],
                "query": query,
                "workspace": workspace_gid,
            }
        except Exception as e:
            logger.error(f"Failed to search tasks: {e}")
            return {"ok": False, "error": str(e)}

    async def get_task_stories(
        self, access_token: str, task_gid: str, limit: int = 20
    ) -> Dict:
        """Get stories (comments) for a task"""
        try:
            params = {"limit": limit}
            result = self._make_request(
                "GET", f"/tasks/{task_gid}/stories", access_token, params=params
            )
            stories = result.get("data", [])

            return {
                "ok": True,
                "stories": [
                    {
                        "gid": story.get("gid"),
                        "text": story.get("text"),
                        "type": story.get("type"),
                        "created_by": story.get("created_by", {}).get("gid"),
                        "created_by_name": story.get("created_by", {}).get("name"),
                        "created_at": story.get("created_at"),
                    }
                    for story in stories
                ],
            }
        except Exception as e:
            logger.error(f"Failed to get task stories: {e}")
            return {"ok": False, "error": str(e)}

    async def add_task_comment(
        self, access_token: str, task_gid: str, text: str
    ) -> Dict:
        """Add a comment to a task"""
        try:
            data = {"data": {"text": text}}
            result = self._make_request(
                "POST", f"/tasks/{task_gid}/stories", access_token, data=data
            )
            story = result.get("data", {})

            return {
                "ok": True,
                "story": {
                    "gid": story.get("gid"),
                    "text": story.get("text"),
                    "created_at": story.get("created_at"),
                },
                "message": "Comment added successfully",
            }
        except Exception as e:
            logger.error(f"Failed to add task comment: {e}")
            return {"ok": False, "error": str(e)}

    async def health_check(self, access_token: str) -> Dict:
        """Check Asana API connectivity and token validity"""
        try:
            result = self._make_request("GET", "/users/me", access_token)
            user_data = result.get("data", {})

            return {
                "ok": True,
                "service": "asana",
                "status": "connected",
                "user": {
                    "name": user_data.get("name"),
                    "email": user_data.get("email"),
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.error(f"Asana health check failed: {e}")
            return {
                "ok": False,
                "service": "asana",
                "status": "disconnected",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }


# Global instance for easy access
asana_service = AsanaService()
