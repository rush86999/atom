"""
Mock Asana Service for Development

This module provides a mock implementation of Asana service for development
and testing when the real asana package is not available or has compatibility issues.
"""

import logging
from typing import Dict, Any, Optional, List
import datetime

logger = logging.getLogger(__name__)

class MockAsanaClient:
    """Mock Asana Client class"""
    def __init__(self, access_token: str = "mock_asana_access_token"):
        self.access_token = access_token
        logger.warning("Using mock Asana client - real Asana integration disabled")

    def tasks(self):
        """Mock tasks method"""
        return MockTasks()

    def projects(self):
        """Mock projects method"""
        return MockProjects()

    def users(self):
        """Mock users method"""
        return MockUsers()

class MockTasks:
    """Mock Tasks collection"""
    def find_all(self, project: str = None, **kwargs):
        """Mock find_all method"""
        # Return mock tasks
        tasks = [
            {
                "gid": "task_001",
                "name": "Complete project documentation",
                "due_on": "2025-09-20",
                "completed": False,
                "assignee": {"gid": "user_001", "name": "John Doe"},
                "projects": [{"gid": "project_001", "name": "Website Redesign"}]
            },
            {
                "gid": "task_002",
                "name": "Review design mockups",
                "due_on": "2025-09-18",
                "completed": True,
                "assignee": {"gid": "user_002", "name": "Jane Smith"},
                "projects": [{"gid": "project_001", "name": "Website Redesign"}]
            },
            {
                "gid": "task_003",
                "name": "Set up development environment",
                "due_on": "2025-09-15",
                "completed": True,
                "assignee": {"gid": "user_001", "name": "John Doe"},
                "projects": [{"gid": "project_002", "name": "API Development"}]
            }
        ]

        # Filter by project if specified
        if project:
            tasks = [task for task in tasks if any(p["gid"] == project for p in task.get("projects", []))]

        return tasks

    def find_by_id(self, task_id: str):
        """Mock find_by_id method"""
        tasks = self.find_all()
        for task in tasks:
            if task["gid"] == task_id:
                return task
        return None

class MockProjects:
    """Mock Projects collection"""
    def find_all(self, **kwargs):
        """Mock find_all method"""
        return [
            {
                "gid": "project_001",
                "name": "Website Redesign",
                "color": "blue",
                "current_status": {"text": "On track"},
                "members": [{"gid": "user_001"}, {"gid": "user_002"}]
            },
            {
                "gid": "project_002",
                "name": "API Development",
                "color": "green",
                "current_status": {"text": "Behind schedule"},
                "members": [{"gid": "user_001"}, {"gid": "user_003"}]
            },
            {
                "gid": "project_003",
                "name": "Marketing Campaign",
                "color": "purple",
                "current_status": {"text": "Not started"},
                "members": [{"gid": "user_004"}]
            }
        ]

    def find_by_id(self, project_id: str):
        """Mock find_by_id method"""
        projects = self.find_all()
        for project in projects:
            if project["gid"] == project_id:
                return project
        return None

class MockUsers:
    """Mock Users collection"""
    def find_all(self, **kwargs):
        """Mock find_all method"""
        return [
            {
                "gid": "user_001",
                "name": "John Doe",
                "email": "john@example.com"
            },
            {
                "gid": "user_002",
                "name": "Jane Smith",
                "email": "jane@example.com"
            },
            {
                "gid": "user_003",
                "name": "Bob Johnson",
                "email": "bob@example.com"
            }
        ]

    def find_by_id(self, user_id: str):
        """Mock find_by_id method"""
        users = self.find_all()
        for user in users:
            if user["gid"] == user_id:
                return user
        return None

class AsanaService:
    """Asana Service with mock implementation"""

    def __init__(self, client: MockAsanaClient):
        self.client = client
        self.is_mock = True

    def list_tasks(
        self,
        project_id: Optional[str] = None,
        assignee: Optional[str] = None,
        completed: Optional[bool] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """List tasks from Asana"""

        tasks = self.client.tasks().find_all(project=project_id)

        # Apply additional filters
        if assignee:
            tasks = [task for task in tasks if task.get("assignee", {}).get("gid") == assignee]

        if completed is not None:
            tasks = [task for task in tasks if task.get("completed") == completed]

        return {
            "data": tasks,
            "next_page": None,
            "is_mock": self.is_mock
        }

    def get_task(self, task_id: str) -> Dict[str, Any]:
        """Get a specific task"""
        task = self.client.tasks().find_by_id(task_id)
        if task:
            return {
                "data": task,
                "is_mock": self.is_mock
            }
        return {
            "data": None,
            "error": f"Task {task_id} not found",
            "is_mock": self.is_mock
        }

    def list_projects(self) -> Dict[str, Any]:
        """List projects from Asana"""
        projects = self.client.projects().find_all()
        return {
            "data": projects,
            "is_mock": self.is_mock
        }

    def get_project(self, project_id: str) -> Dict[str, Any]:
        """Get a specific project"""
        project = self.client.projects().find_by_id(project_id)
        if project:
            return {
                "data": project,
                "is_mock": self.is_mock
            }
        return {
            "data": None,
            "error": f"Project {project_id} not found",
            "is_mock": self.is_mock
        }

    def list_users(self) -> Dict[str, Any]:
        """List users from Asana"""
        users = self.client.users().find_all()
        return {
            "data": users,
            "is_mock": self.is_mock
        }

    def get_service_status(self) -> Dict[str, Any]:
        """Get Asana service status"""
        return {
            "status": "mock_mode",
            "message": "Asana service running in mock mode for development",
            "available": False,
            "mock_data": True
        }

# Create mock client instance for easy import
mock_client = MockAsanaClient()
mock_service = AsanaService(mock_client)

logger.info("Asana mock service initialized successfully")
