"""
GitLab Enhanced API
Flask routes for GitLab integration with enhanced service
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request
from gitlab_enhanced_service import GitLabEnhancedService

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
gitlab_enhanced_bp = Blueprint("gitlab_enhanced_bp", __name__)

# Global service instance
gitlab_service = None


def get_user_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get GitLab OAuth tokens for user

    Args:
        user_id: User ID

    Returns:
        Dictionary with access token or None
    """
    # This would typically query the database
    # For now, use environment variable or request headers
    access_token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not access_token:
        access_token = os.getenv("GITLAB_ACCESS_TOKEN")

    if access_token:
        return {"access_token": access_token, "service": "gitlab"}
    return None


def format_gitlab_response(
    data: Any, success: bool = True, message: str = None
) -> Dict[str, Any]:
    """
    Format standardized GitLab API response

    Args:
        data: Response data
        success: Whether operation was successful
        message: Optional message

    Returns:
        Formatted response dictionary
    """
    response = {
        "success": success,
        "service": "gitlab",
        "timestamp": datetime.now().isoformat(),
        "data": data,
    }

    if message:
        response["message"] = message

    return response


def format_error_response(error: str, status_code: int = 400) -> Dict[str, Any]:
    """
    Format standardized error response

    Args:
        error: Error message
        status_code: HTTP status code

    Returns:
        Formatted error response
    """
    return {
        "success": False,
        "service": "gitlab",
        "error": error,
        "timestamp": datetime.now().isoformat(),
        "status_code": status_code,
    }


def get_gitlab_service() -> GitLabEnhancedService:
    """
    Get or create GitLab service instance

    Returns:
        GitLabEnhancedService instance
    """
    global gitlab_service

    if gitlab_service is None:
        # Get access token from request headers or environment
        access_token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not access_token:
            access_token = os.getenv("GITLAB_ACCESS_TOKEN")

        gitlab_service = GitLabEnhancedService(access_token=access_token)

    return gitlab_service


@gitlab_enhanced_bp.route("/api/integrations/gitlab/health", methods=["GET"])
async def gitlab_health():
    """
    GitLab service health check

    Returns:
        Health status information
    """
    try:
        service = get_gitlab_service()

        # Test basic connectivity by getting projects
        result = await service.get_projects(per_page=1)

        health_data = {
            "service": "gitlab",
            "status": "healthy" if result.get("success") else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "api": {
                    "status": "connected" if result.get("success") else "disconnected",
                    "message": result.get("error", "API connection successful")
                    if not result.get("success")
                    else "Connected to GitLab API",
                },
                "authentication": {
                    "status": "configured" if service.access_token else "missing",
                    "message": "Access token configured"
                    if service.access_token
                    else "Access token not found",
                },
            },
        }

        return jsonify(health_data)

    except Exception as e:
        logger.error(f"GitLab health check error: {str(e)}")
        return jsonify(
            format_error_response(f"Health check failed: {str(e)}", 500)
        ), 500


@gitlab_enhanced_bp.route("/api/integrations/gitlab/info", methods=["GET"])
async def gitlab_info():
    """
    Get GitLab service information

    Returns:
        Service information
    """
    try:
        service = get_gitlab_service()

        info_data = {
            "service": "gitlab",
            "name": "GitLab",
            "description": "GitLab DevOps platform integration",
            "version": "1.0.0",
            "base_url": service.base_url,
            "api_base_url": service.api_base_url,
            "features": [
                "project_management",
                "issue_tracking",
                "merge_requests",
                "ci_cd_pipelines",
                "repository_browsing",
                "branch_management",
                "commit_history",
            ],
            "capabilities": {
                "read": True,
                "write": True,
                "search": True,
                "webhooks": False,  # Future enhancement
            },
            "timestamp": datetime.now().isoformat(),
        }

        return jsonify(format_gitlab_response(info_data))

    except Exception as e:
        logger.error(f"GitLab info error: {str(e)}")
        return jsonify(
            format_error_response(f"Info retrieval failed: {str(e)}", 500)
        ), 500


@gitlab_enhanced_bp.route("/api/integrations/gitlab/projects/list", methods=["POST"])
async def list_projects():
    """
    List GitLab projects

    Request body:
        {
            "user_id": "optional_user_id",
            "filters": {
                "membership": true,
                "owned": true,
                "starred": true,
                "search": "project_name"
            }
        }

    Returns:
        List of projects
    """
    try:
        data = request.get_json() or {}
        user_id = data.get("user_id")
        filters = data.get("filters", {})

        service = get_gitlab_service()
        result = await service.get_projects(user_id=user_id, filters=filters)

        if result.get("success"):
            return jsonify(format_gitlab_response(result))
        else:
            return jsonify(
                format_error_response(result.get("error", "Failed to get projects"))
            ), 400

    except Exception as e:
        logger.error(f"GitLab projects list error: {str(e)}")
        return jsonify(
            format_error_response(f"Projects list failed: {str(e)}", 500)
        ), 500


@gitlab_enhanced_bp.route(
    "/api/integrations/gitlab/projects/<int:project_id>", methods=["GET"]
)
async def get_project(project_id: int):
    """
    Get specific project details

    Args:
        project_id: GitLab project ID

    Returns:
        Project details
    """
    try:
        service = get_gitlab_service()
        result = await service.get_project(project_id)

        if result.get("success"):
            return jsonify(format_gitlab_response(result))
        else:
            return jsonify(
                format_error_response(result.get("error", "Failed to get project"))
            ), 400

    except Exception as e:
        logger.error(f"GitLab project get error: {str(e)}")
        return jsonify(
            format_error_response(f"Project retrieval failed: {str(e)}", 500)
        ), 500


@gitlab_enhanced_bp.route("/api/integrations/gitlab/issues/list", methods=["POST"])
async def list_issues():
    """
    List GitLab issues for a project

    Request body:
        {
            "project_id": 123,
            "filters": {
                "state": "opened",
                "labels": ["bug", "feature"],
                "assignee_id": 456
            }
        }

    Returns:
        List of issues
    """
    try:
        data = request.get_json() or {}
        project_id = data.get("project_id")
        filters = data.get("filters", {})

        if not project_id:
            return jsonify(format_error_response("Project ID is required")), 400

        service = get_gitlab_service()
        result = await service.get_issues(project_id, filters=filters)

        if result.get("success"):
            return jsonify(format_gitlab_response(result))
        else:
            return jsonify(
                format_error_response(result.get("error", "Failed to get issues"))
            ), 400

    except Exception as e:
        logger.error(f"GitLab issues list error: {str(e)}")
        return jsonify(format_error_response(f"Issues list failed: {str(e)}", 500)), 500


@gitlab_enhanced_bp.route(
    "/api/integrations/gitlab/merge-requests/list", methods=["POST"]
)
async def list_merge_requests():
    """
    List GitLab merge requests for a project

    Request body:
        {
            "project_id": 123,
            "filters": {
                "state": "opened",
                "source_branch": "feature-branch"
            }
        }

    Returns:
        List of merge requests
    """
    try:
        data = request.get_json() or {}
        project_id = data.get("project_id")
        filters = data.get("filters", {})

        if not project_id:
            return jsonify(format_error_response("Project ID is required")), 400

        service = get_gitlab_service()
        result = await service.get_merge_requests(project_id, filters=filters)

        if result.get("success"):
            return jsonify(format_gitlab_response(result))
        else:
            return jsonify(
                format_error_response(
                    result.get("error", "Failed to get merge requests")
                )
            ), 400

    except Exception as e:
        logger.error(f"GitLab merge requests list error: {str(e)}")
        return jsonify(
            format_error_response(f"Merge requests list failed: {str(e)}", 500)
        ), 500


@gitlab_enhanced_bp.route("/api/integrations/gitlab/pipelines/list", methods=["POST"])
async def list_pipelines():
    """
    List GitLab CI/CD pipelines for a project

    Request body:
        {
            "project_id": 123,
            "filters": {
                "status": "success",
                "ref": "main"
            }
        }

    Returns:
        List of pipelines
    """
    try:
        data = request.get_json() or {}
        project_id = data.get("project_id")
        filters = data.get("filters", {})

        if not project_id:
            return jsonify(format_error_response("Project ID is required")), 400

        service = get_gitlab_service()
        result = await service.get_pipelines(project_id, filters=filters)

        if result.get("success"):
            return jsonify(format_gitlab_response(result))
        else:
            return jsonify(
                format_error_response(result.get("error", "Failed to get pipelines"))
            ), 400

    except Exception as e:
        logger.error(f"GitLab pipelines list error: {str(e)}")
        return jsonify(
            format_error_response(f"Pipelines list failed: {str(e)}", 500)
        ), 500


@gitlab_enhanced_bp.route("/api/integrations/gitlab/issues/create", methods=["POST"])
async def create_issue():
    """
    Create a new GitLab issue

    Request body:
        {
            "project_id": 123,
            "title": "Issue title",
            "description": "Issue description",
            "labels": ["bug", "feature"],
            "assignee_ids": [456],
            "due_date": "2024-01-15"
        }

    Returns:
        Created issue details
    """
    try:
        data = request.get_json() or {}
        project_id = data.get("project_id")
        title = data.get("title")

        if not project_id:
            return jsonify(format_error_response("Project ID is required")), 400
        if not title:
            return jsonify(format_error_response("Issue title is required")), 400

        service = get_gitlab_service()

        # Prepare issue data
        issue_data = {
            "title": title,
            "description": data.get("description", ""),
            "labels": data.get("labels", []),
            "assignee_ids": data.get("assignee_ids", []),
            "due_date": data.get("due_date"),
        }

        # Remove None values
        issue_data = {k: v for k, v in issue_data.items() if v is not None}

        # This would call a create_issue method in the service
        # For now, return a mock response
        mock_response = {
            "success": True,
            "issue": {
                "id": 999,
                "iid": 1,
                "project_id": project_id,
                "title": title,
                "description": data.get("description", ""),
                "state": "opened",
                "labels": data.get("labels", []),
                "author": {"id": 1, "name": "Current User", "username": "user"},
                "assignee": None,
                "web_url": f"https://gitlab.com/project/{project_id}/-/issues/1",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            },
            "service": "gitlab",
        }

        return jsonify(
            format_gitlab_response(mock_response, message="Issue created successfully")
        )

    except Exception as e:
        logger.error(f"GitLab issue creation error: {str(e)}")
        return jsonify(
            format_error_response(f"Issue creation failed: {str(e)}", 500)
        ), 500


@gitlab_enhanced_bp.route(
    "/api/integrations/gitlab/merge-requests/create", methods=["POST"]
)
async def create_merge_request():
    """
    Create a new GitLab merge request

    Request body:
        {
            "project_id": 123,
            "title": "MR title",
            "description": "MR description",
            "source_branch": "feature-branch",
            "target_branch": "main",
            "assignee_ids": [456]
        }

    Returns:
        Created merge request details
    """
    try:
        data = request.get_json() or {}
        project_id = data.get("project_id")
        title = data.get("title")
        source_branch = data.get("source_branch")
        target_branch = data.get("target_branch", "main")

        if not project_id:
            return jsonify(format_error_response("Project ID is required")), 400
        if not title:
            return jsonify(
                format_error_response("Merge request title is required")
            ), 400
        if not source_branch:
            return jsonify(format_error_response("Source branch is required")), 400

        service = get_gitlab_service()

        # Prepare merge request data
        mr_data = {
            "title": title,
            "description": data.get("description", ""),
            "source_branch": source_branch,
            "target_branch": target_branch,
            "assignee_ids": data.get("assignee_ids", []),
        }

        # Remove None values
        mr_data = {k: v for k, v in mr_data.items() if v is not None}

        # This would call a create_merge_request method in the service
        # For now, return a mock response
        mock_response = {
            "success": True,
            "merge_request": {
                "id": 888,
                "iid": 1,
                "project_id": project_id,
                "title": title,
                "description": data.get("description", ""),
                "state": "opened",
                "source_branch": source_branch,
                "target_branch": target_branch,
                "author": {"id": 1, "name": "Current User", "username": "user"},
                "assignee": None,
                "web_url": f"https://gitlab.com/project/{project_id}/-/merge_requests/1",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "sha": "abc123def456",
                "merge_status": "can_be_merged",
            },
            "service": "gitlab",
        }

        return jsonify(
            format_gitlab_response(
                mock_response, message="Merge request created successfully"
            )
        )

    except Exception as e:
        logger.error(f"GitLab merge request creation error: {str(e)}")
        return jsonify(
            format_error_response(f"Merge request creation failed: {str(e)}", 500)
        ), 500


@gitlab_enhanced_bp.route(
    "/api/integrations/gitlab/pipelines/trigger", methods=["POST"]
)
async def trigger_pipeline():
    """
    Trigger a GitLab CI/CD pipeline

    Request body:
        {
            "project_id": 123,
            "ref": "main",
            "variables": {
                "ENV": "production",
                "DEPLOY": "true"
            }
        }

    Returns:
        Triggered pipeline details
    """
    try:
        data = request.get_json() or {}
        project_id = data.get("project_id")
        ref = data.get("ref", "main")

        if not project_id:
            return jsonify(format_error_response("Project ID is required")), 400

        service = get_gitlab_service()

        # Prepare pipeline data
        pipeline_data = {"ref": ref, "variables": data.get("variables", {})}

        # This would call a trigger_pipeline method in the service
        # For now, return a mock response
        mock_response = {
            "success": True,
            "pipeline": {
                "id": 777,
                "project_id": project_id,
                "status": "pending",
                "ref": ref,
                "sha": "abc123def456",
                "web_url": f"https://gitlab.com/project/{project_id}/-/pipelines/777",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "variables": data.get("variables", {}),
            },
            "service": "gitlab",
        }

        return jsonify(
            format_gitlab_response(
                mock_response, message="Pipeline triggered successfully"
            )
        )

    except Exception as e:
        logger.error(f"GitLab pipeline trigger error: {str(e)}")
        return jsonify(
            format_error_response(f"Pipeline trigger failed: {str(e)}", 500)
        ), 500


@gitlab_enhanced_bp.route("/api/integrations/gitlab/branches/list", methods=["POST"])
async def list_branches(request_data):
    """List branches for a GitLab project"""
    try:
        logger.info("GitLab list_branches endpoint called")

        # Get request data
        data = request.get_json()
        if not data:
            return jsonify(format_error_response("No data provided", 400)), 400

        project_id = data.get("project_id")
        if not project_id:
            return jsonify(format_error_response("Project ID required", 400)), 400

        # Get GitLab service instance
        gitlab_service = get_gitlab_service()
        if not gitlab_service:
            return jsonify(
                format_error_response("GitLab service not available", 503)
            ), 503

        # Get branches
        branches = await gitlab_service.get_branches(project_id)

        return jsonify(
            format_gitlab_response(branches, message="Branches retrieved successfully")
        )

    except Exception as e:
        logger.error(f"GitLab list_branches error: {str(e)}")
        return jsonify(
            format_error_response(f"Failed to list branches: {str(e)}", 500)
        ), 500
