# Real Asana service implementation using Asana API v5.2.1+
# This provides real implementations for Asana API functionality using the new API structure

import os
import logging
from typing import Dict, Any, Optional, List
from asana.api import TasksApi, ProjectsApi, WorkspacesApi
from asana.api_client import ApiClient
from asana.configuration import Configuration
import db_oauth_asana, crypto_utils

from mcp_base import MCPBase

logger = logging.getLogger(__name__)


class AsanaServiceReal(MCPBase):
    def __init__(self, api_client: ApiClient):
        """Initialize real Asana client with API client"""
        self.api_client = api_client
        self.tasks_api = TasksApi(api_client)
        self.projects_api = ProjectsApi(api_client)
        self.workspaces_api = WorkspacesApi(api_client)
        self.is_mock = False

    def list_files(
        self,
        project_id: str,
        query: Optional[str] = None,
        page_size: int = 100,
        page_token: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Get tasks from an Asana project with optional search filtering"""
        try:
            # Build parameters for the API call
            params = {
                "project": project_id,
                "limit": page_size,
                "offset": page_token if page_token else "0",
            }

            if query:
                # Search for tasks containing the query text
                params["text"] = query

            # Get tasks from the project
            tasks_response = self.tasks_api.get_tasks(**params)
            tasks = tasks_response.data if hasattr(tasks_response, "data") else []

            # Convert tasks to dictionary format
            files = []
            for task in tasks:
                files.append(
                    {
                        "id": task.gid,
                        "name": task.name,
                        "notes": getattr(task, "notes", None),
                        "due_on": getattr(task, "due_on", None),
                        "completed": getattr(task, "completed", False),
                        "assignee": getattr(task.assignee, "name", None)
                        if hasattr(task, "assignee") and task.assignee
                        else None,
                        "projects": [
                            {"gid": project_id, "name": "Project"}
                        ],  # Simplified
                        "created_at": getattr(task, "created_at", None),
                        "modified_at": getattr(task, "modified_at", None),
                    }
                )

            # Calculate next page token
            next_page_token = (
                str(int(page_token or 0) + len(tasks))
                if len(tasks) == page_size
                else None
            )

            return {
                "status": "success",
                "data": {"files": files, "nextPageToken": next_page_token},
            }

        except Exception as e:
            logger.error(f"Error listing Asana tasks: {e}")
            return {"status": "error", "message": str(e)}

    def get_file_metadata(self, file_id: str, **kwargs) -> Dict[str, Any]:
        """Get metadata for a specific Asana task"""
        try:
            # Get task details
            task = self.tasks_api.get_task(file_id)

            metadata = {
                "id": task.gid,
                "name": task.name,
                "notes": getattr(task, "notes", None),
                "due_on": getattr(task, "due_on", None),
                "completed": getattr(task, "completed", False),
                "assignee": getattr(task.assignee, "name", None)
                if hasattr(task, "assignee") and task.assignee
                else None,
                "created_at": getattr(task, "created_at", None),
                "modified_at": getattr(task, "modified_at", None),
                "projects": [
                    {"gid": project.gid, "name": project.name}
                    for project in getattr(task, "projects", [])
                ],
                "tags": [
                    {"gid": tag.gid, "name": tag.name}
                    for tag in getattr(task, "tags", [])
                ],
            }

            return {"status": "success", "data": metadata}

        except Exception as e:
            logger.error(f"Error getting Asana task metadata: {e}")
            return {"status": "error", "message": str(e)}

    def download_file(self, file_id: str, **kwargs) -> Dict[str, Any]:
        """Download is not directly supported for Asana tasks"""
        return {
            "status": "error",
            "message": "Download not directly supported for Asana tasks. Use get_file_metadata to retrieve task details.",
        }

    def create_task(
        self,
        project_id: str,
        name: str,
        notes: str = "",
        due_on: Optional[str] = None,
        assignee: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Create a new Asana task"""
        try:
            # Prepare task data
            task_data = {"name": name, "projects": [project_id]}

            if notes:
                task_data["notes"] = notes
            if due_on:
                task_data["due_on"] = due_on
            if assignee:
                task_data["assignee"] = assignee

            # Create the task
            new_task = self.tasks_api.create_task(task_data)

            return {
                "status": "success",
                "data": {
                    "id": new_task.gid,
                    "name": new_task.name,
                    "url": f"https://app.asana.com/0/{project_id}/{new_task.gid}/f",
                },
            }

        except Exception as e:
            logger.error(f"Error creating Asana task: {e}")
            return {"status": "error", "message": str(e)}

    def update_task(
        self,
        task_id: str,
        name: Optional[str] = None,
        notes: Optional[str] = None,
        due_on: Optional[str] = None,
        completed: Optional[bool] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Update an existing Asana task"""
        try:
            # Prepare update data
            update_data = {}

            if name is not None:
                update_data["name"] = name
            if notes is not None:
                update_data["notes"] = notes
            if due_on is not None:
                update_data["due_on"] = due_on
            if completed is not None:
                update_data["completed"] = completed

            # Update the task
            updated_task = self.tasks_api.update_task(task_id, update_data)

            return {
                "status": "success",
                "data": {"message": "Task updated successfully"},
            }

        except Exception as e:
            logger.error(f"Error updating Asana task: {e}")
            return {"status": "error", "message": str(e)}

    def get_service_status(self) -> Dict[str, Any]:
        """Get service status information"""
        try:
            # Test connectivity by getting user info
            user_response = self.tasks_api.get_user("me")
            user_data = user_response.data if hasattr(user_response, "data") else {}

            return {
                "status": "connected",
                "message": "Asana service connected successfully",
                "available": True,
                "mock_data": False,
                "user": user_data.get("name", "Unknown User"),
            }
        except Exception as e:
            return {
                "status": "disconnected",
                "message": f"Asana service connection failed: {str(e)}",
                "available": False,
                "mock_data": False,
            }


# Function to create real Asana API client
def get_asana_api_client(access_token: str) -> ApiClient:
    """Create Asana API client with access token"""
    configuration = Configuration()
    configuration.access_token = access_token
    return ApiClient(configuration)


def get_asana_service_real(access_token: str) -> AsanaServiceReal:
    """Get real Asana service with access token"""
    api_client = get_asana_api_client(access_token)
    return AsanaServiceReal(api_client)
