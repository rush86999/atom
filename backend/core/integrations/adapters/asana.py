"""
Asana Integration Adapter

Provides OAuth-based integration with Asana for task and project management.
"""

import logging
import os
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class AsanaAdapter:
    """
    Adapter for Asana OAuth integration.

    Supports:
    - OAuth 2.0 authentication
    - Task and project management
    - Team and workspace access
    - Tag and section tracking
    """

    def __init__(self, db, workspace_id: str):
        self.db = db
        self.workspace_id = workspace_id
        self.service_name = "asana"
        self.base_url = "https://app.asana.com/api/1.0"

        # OAuth credentials from environment
        self.client_id = os.getenv("ASANA_CLIENT_ID")
        self.client_secret = os.getenv("ASANA_CLIENT_SECRET")
        self.redirect_uri = os.getenv("ASANA_REDIRECT_URI")

        # Token storage
        self._access_token: Optional[str] = None
        _refresh_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    async def get_oauth_url(self) -> str:
        """
        Generate Asana OAuth authorization URL.

        Returns:
            Authorization URL to redirect user to Asana OAuth consent screen
        """
        if not self.client_id:
            raise ValueError("ASANA_CLIENT_ID not configured")

        # Asana OAuth endpoint
        auth_url = "https://app.asana.com/-/oauth_authorize"

        # Build authorization URL
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": self.workspace_id,  # Use workspace_id as state
            "scope": "default"
        }

        auth_url_with_params = f"{auth_url}?{urlencode(params)}"

        logger.info(f"Generated Asana OAuth URL for workspace {self.workspace_id}")
        return auth_url_with_params

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange OAuth authorization code for access token.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Token response with access_token, refresh_token, expires_in, etc.
        """
        if not self.client_id or not self.client_secret:
            raise ValueError("Asana OAuth credentials not configured")

        token_url = f"{self.base_url}/oauth_token"

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, data=data)
                response.raise_for_status()

                token_data = response.json()

                # Store tokens
                self._access_token = token_data.get("access_token")
                _refresh_token = token_data.get("refresh_token")

                # Calculate token expiration (Asana tokens expire in 1 hour)
                if "expires_in" in token_data:
                    self._token_expires_at = datetime.now() + timedelta(
                        seconds=token_data["expires_in"]
                    )

                logger.info(f"Successfully obtained Asana access token for workspace {self.workspace_id}")
                return token_data

        except httpx.HTTPStatusError as e:
            logger.error(f"Asana token exchange failed: {e}")
            raise

    async def test_connection(self) -> bool:
        """
        Test the Asana API connection.

        Returns:
            True if connection successful, False otherwise
        """
        if not self._access_token:
            return False

        try:
            async with httpx.AsyncClient() as client:
                # Test by getting current user info
                response = await client.get(
                    f"{self.base_url}/users/me",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    }
                )
                response.raise_for_status()

                logger.info(f"Asana connection test successful for workspace {self.workspace_id}")
                return True

        except Exception as e:
            logger.error(f"Asana connection test failed: {e}")
            return False

    async def search_tasks(self, query: str, workspace: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search Asana tasks by name.

        Args:
            query: Search query string
            workspace: Workspace GID (optional)
            limit: Maximum number of results

        Returns:
            List of task objects
        """
        if not self._access_token:
            raise ValueError("Asana access token not available")

        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "query": query,
                    "resource_type": "task",
                    "limit": limit
                }
                if workspace:
                    params["workspace"] = workspace

                response = await client.get(
                    f"{self.base_url}/workspaces/search",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    },
                    params=params
                )
                response.raise_for_status()

                data = response.json()
                tasks = data.get("data", [])

                logger.info(f"Asana search returned {len(tasks)} tasks for workspace {self.workspace_id}")
                return tasks

        except Exception as e:
            logger.error(f"Asana task search failed: {e}")
            raise

    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """
        Retrieve a specific Asana task by ID.

        Args:
            task_id: Asana task GID

        Returns:
            Task details with all fields
        """
        if not self._access_token:
            raise ValueError("Asana access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/tasks/{task_id}",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    },
                    params={"opt_fields": "name,notes,completed,assignee,due_on,projects,tags"}
                )
                response.raise_for_status()

                data = response.json()
                task = data.get("data")

                logger.info(f"Retrieved Asana task {task_id} for workspace {self.workspace_id}")
                return task

        except Exception as e:
            logger.error(f"Failed to retrieve Asana task {task_id}: {e}")
            raise

    async def create_task(self, name: str, project: str = None, assignee: str = None,
                         due_on: str = None, notes: str = None, **fields) -> Dict[str, Any]:
        """
        Create a new Asana task.

        Args:
            name: Task name (required)
            project: Project GID to add task to
            assignee: User GID to assign task to
            due_on: Due date (YYYY-MM-DD format)
            notes: Task description
            **fields: Additional task fields

        Returns:
            Created task object with GID
        """
        if not self._access_token:
            raise ValueError("Asana access token not available")

        try:
            # Build task data
            task_data = {
                "name": name,
            }
            if project:
                task_data["projects"] = [project]
            if assignee:
                task_data["assignee"] = assignee
            if due_on:
                task_data["due_on"] = due_on
            if notes:
                task_data["notes"] = notes
            task_data.update(fields)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/tasks",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    },
                    json={"data": task_data}
                )
                response.raise_for_status()

                data = response.json()
                task = data.get("data")

                logger.info(f"Created Asana task {task.get('gid')} for workspace {self.workspace_id}")
                return task

        except Exception as e:
            logger.error(f"Failed to create Asana task: {e}")
            raise

    async def update_task(self, task_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an Asana task.

        Args:
            task_id: Task GID to update
            updates: Dictionary of fields to update

        Returns:
            Updated task object
        """
        if not self._access_token:
            raise ValueError("Asana access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.base_url}/tasks/{task_id}",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    },
                    json={"data": updates}
                )
                response.raise_for_status()

                data = response.json()
                task = data.get("data")

                logger.info(f"Updated Asana task {task_id} in workspace {self.workspace_id}")
                return task

        except Exception as e:
            logger.error(f"Failed to update Asana task {task_id}: {e}")
            raise

    async def get_projects(self, workspace: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Retrieve Asana projects.

        Args:
            workspace: Workspace GID (optional)
            limit: Maximum number of results

        Returns:
            List of project objects
        """
        if not self._access_token:
            raise ValueError("Asana access token not available")

        try:
            async with httpx.AsyncClient() as client:
                params = {"limit": limit}
                if workspace:
                    params["workspace"] = workspace

                response = await client.get(
                    f"{self.base_url}/projects",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    },
                    params=params
                )
                response.raise_for_status()

                data = response.json()
                projects = data.get("data", [])

                logger.info(f"Retrieved {len(projects)} Asana projects for workspace {self.workspace_id}")
                return projects

        except Exception as e:
            logger.error(f"Failed to retrieve Asana projects: {e}")
            raise

    async def add_comment(self, task_id: str, text: str) -> Dict[str, Any]:
        """
        Add a comment to an Asana task.

        Args:
            task_id: Task GID
            text: Comment text

        Returns:
            Created story (comment) object
        """
        if not self._access_token:
            raise ValueError("Asana access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/tasks/{task_id}/stories",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    },
                    json={
                        "data": {
                            "text": text
                        }
                    }
                )
                response.raise_for_status()

                data = response.json()
                story = data.get("data")

                logger.info(f"Added comment to Asana task {task_id} in workspace {self.workspace_id}")
                return story

        except Exception as e:
            logger.error(f"Failed to add comment to Asana task {task_id}: {e}")
            raise

    async def get_workspaces(self) -> List[Dict[str, Any]]:
        """
        Retrieve all Asana workspaces accessible to user.

        Returns:
            List of workspace objects
        """
        if not self._access_token:
            raise ValueError("Asana access token not available")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/workspaces",
                    headers={
                        "Authorization": f"Bearer {self._access_token}"
                    }
                )
                response.raise_for_status()

                data = response.json()
                workspaces = data.get("data", [])

                logger.info(f"Retrieved {len(workspaces)} Asana workspaces for workspace {self.workspace_id}")
                return workspaces

        except Exception as e:
            logger.error(f"Failed to retrieve Asana workspaces: {e}")
            raise
