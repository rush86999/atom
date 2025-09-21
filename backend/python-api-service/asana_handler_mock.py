import logging
from flask import Blueprint, request, jsonify
from typing import Dict, Any, Optional
import datetime

logger = logging.getLogger(__name__)

asana_bp = Blueprint('asana_bp', __name__)

class MockAsanaService:
    """Mock Asana Service for development"""

    def __init__(self):
        logger.warning("Using mock Asana service - real Asana integration disabled")

    def list_tasks(
        self,
        project_id: Optional[str] = None,
        assignee: Optional[str] = None,
        completed: Optional[bool] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Mock list tasks implementation"""

        # Generate mock tasks
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

        # Apply filters
        if project_id:
            tasks = [task for task in tasks if any(p["gid"] == project_id for p in task.get("projects", []))]

        if assignee:
            tasks = [task for task in tasks if task.get("assignee", {}).get("gid") == assignee]

        if completed is not None:
            tasks = [task for task in tasks if task.get("completed") == completed]

        return {
            "data": tasks,
            "next_page": None,
            "is_mock": True
        }

    def list_projects(self) -> Dict[str, Any]:
        """Mock list projects implementation"""

        projects = [
            {
                "gid": "project_001",
                "name": "Website Redesign",
                "color": "blue",
                "current_status": {"text": "On track"}
            },
            {
                "gid": "project_002",
                "name": "API Development",
                "color": "green",
                "current_status": {"text": "Behind schedule"}
            },
            {
                "gid": "project_003",
                "name": "Marketing Campaign",
                "color": "purple",
                "current_status": {"text": "Not started"}
            }
        ]

        return {
            "data": projects,
            "is_mock": True
        }

    def get_service_status(self) -> Dict[str, Any]:
        """Get mock service status"""
        return {
            "status": "mock_mode",
            "message": "Asana service running in mock mode for development",
            "available": False,
            "mock_data": True
        }

# Create mock service instance
mock_service = MockAsanaService()

@asana_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """List tasks from Asana"""
    try:
        project_id = request.args.get('project_id')
        assignee = request.args.get('assignee')
        completed = request.args.get('completed')

        if completed is not None:
            completed = completed.lower() == 'true'

        result = mock_service.list_tasks(
            project_id=project_id,
            assignee=assignee,
            completed=completed
        )

        return jsonify({
            "success": True,
            "data": result,
            "is_mock": True
        })

    except Exception as e:
        logger.error(f"Error listing Asana tasks: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "is_mock": True
        }), 500

@asana_bp.route('/projects', methods=['GET'])
def list_projects():
    """List projects from Asana"""
    try:
        result = mock_service.list_projects()

        return jsonify({
            "success": True,
            "data": result,
            "is_mock": True
        })

    except Exception as e:
        logger.error(f"Error listing Asana projects: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "is_mock": True
        }), 500

@asana_bp.route('/status', methods=['GET'])
def get_status():
    """Get Asana service status"""
    try:
        status = mock_service.get_service_status()

        return jsonify({
            "success": True,
            "status": status,
            "is_mock": True
        })

    except Exception as e:
        logger.error(f"Error getting Asana status: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "is_mock": True
        }), 500

@asana_bp.route('/health', methods=['GET'])
def health_check():
    """Asana service health check"""
    return jsonify({
        "status": "healthy",
        "service": "asana",
        "mode": "mock",
        "available": True
    })

# Mock OAuth endpoints for development
@asana_bp.route('/auth/url', methods=['GET'])
def get_auth_url():
    """Get mock OAuth URL"""
    return jsonify({
        "auth_url": "https://mock-asana.com/oauth/authorize?client_id=mock_client_id&response_type=code",
        "is_mock": True
    })

@asana_bp.route('/auth/callback', methods=['GET'])
def oauth_callback():
    """Mock OAuth callback"""
    return jsonify({
        "success": True,
        "access_token": "mock_asana_access_token_123",
        "refresh_token": "mock_asana_refresh_token_456",
        "expires_in": 3600,
        "is_mock": True
    })

logger.info("Asana mock handler initialized successfully")
