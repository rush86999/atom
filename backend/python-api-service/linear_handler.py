"""
Linear Handler
Complete Linear project management and issue tracking handler
"""

import os
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from loguru import logger

# Import Linear service
try:
    from linear_service_real import LinearService
    from linear_service_real import LinearIssue, LinearProject, LinearTeam, LinearUser, LinearCycle

    LINEAR_SERVICE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Linear service not available: {e}")
    LINEAR_SERVICE_AVAILABLE = False
    linear_service = None

# Import database handler
try:
    from db_oauth_linear import (
        get_tokens,
        save_tokens,
        delete_tokens,
        get_user_linear_data,
        save_linear_data,
    )

    LINEAR_DB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Linear database handler not available: {e}")
    LINEAR_DB_AVAILABLE = False

# Create blueprint
linear_bp = Blueprint("linear_bp", __name__)

# Configuration
LINEAR_API_BASE_URL = "https://api.linear.app/v1"
REQUEST_TIMEOUT = 60


async def get_user_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """Get Linear tokens for user"""
    if not LINEAR_DB_AVAILABLE:
        # Mock implementation for testing
        return {
            "access_token": os.getenv("LINEAR_ACCESS_TOKEN", "mock_linear_token"),
            "refresh_token": "mock_refresh_token",
            "expires_at": "2025-01-01T00:00:00Z"
        }
    
    try:
        return await get_tokens(user_id, 'linear')
    except Exception as e:
        logger.error(f"Error getting Linear tokens for user {user_id}: {e}")
        return None


def create_response(ok: bool, data: Any = None, error: str = None) -> Dict[str, Any]:
    """Create standardized response"""
    response = {"ok": ok}
    
    if ok and data is not None:
        if isinstance(data, list):
            response["data"] = data
            response["count"] = len(data)
        else:
            response["data"] = data
    elif error:
        response["error"] = error
    
    return response


# Health check endpoint
@linear_bp.route("/linear/health", methods=["GET"])
def health_check():
    """Linear service health check"""
    return jsonify(create_response(
        ok=LINEAR_SERVICE_AVAILABLE,
        data={
            "service": "linear",
            "status": "registered" if LINEAR_SERVICE_AVAILABLE else "not_available",
            "api_version": "v1",
            "needs_oauth": True
        }
    ))


# Profile endpoint
@linear_bp.route("/linear/profile", methods=["GET"])
def get_profile():
    """Get Linear user profile"""
    user_id = request.headers.get("user-id")
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    try:
        if not LINEAR_SERVICE_AVAILABLE:
            return jsonify(create_response(False, error="Linear service not available")), 503
        
        service = LinearService()
        profile = await service.get_user_profile(user_id)
        
        if profile:
            return jsonify(create_response(True, profile))
        else:
            return jsonify(create_response(False, error="Failed to get Linear profile")), 500
            
    except Exception as e:
        logger.error(f"Error getting Linear profile for user {user_id}: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Teams endpoint
@linear_bp.route("/linear/teams", methods=["GET"])
def get_teams():
    """Get Linear teams"""
    user_id = request.headers.get("user-id")
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    try:
        if not LINEAR_SERVICE_AVAILABLE:
            return jsonify(create_response(False, error="Linear service not available")), 503
        
        service = LinearService()
        teams = await service.get_user_teams(user_id)
        
        return jsonify(create_response(True, teams))
            
    except Exception as e:
        logger.error(f"Error getting Linear teams for user {user_id}: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Projects endpoint
@linear_bp.route("/linear/projects", methods=["GET"])
def get_projects():
    """Get Linear projects"""
    user_id = request.headers.get("user-id")
    team_id = request.args.get("team_id")
    
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    try:
        if not LINEAR_SERVICE_AVAILABLE:
            return jsonify(create_response(False, error="Linear service not available")), 503
        
        service = LinearService()
        projects = await service.get_team_projects(user_id, team_id)
        
        return jsonify(create_response(True, projects))
            
    except Exception as e:
        logger.error(f"Error getting Linear projects for user {user_id}: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Issues endpoint
@linear_bp.route("/linear/issues", methods=["GET"])
def get_issues():
    """Get Linear issues"""
    user_id = request.headers.get("user-id")
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    # Get query parameters
    team_id = request.args.get("team_id")
    project_id = request.args.get("project_id")
    status = request.args.get("status", "open")
    limit = int(request.args.get("limit", 50))
    
    try:
        if not LINEAR_SERVICE_AVAILABLE:
            return jsonify(create_response(False, error="Linear service not available")), 503
        
        service = LinearService()
        issues = await service.get_user_issues(
            user_id=user_id,
            team_id=team_id,
            project_id=project_id,
            include_completed=status in ["done", "completed"],
            include_canceled=status == "canceled",
            include_backlog=status == "backlog",
            limit=limit
        )
        
        return jsonify(create_response(True, issues))
            
    except Exception as e:
        logger.error(f"Error getting Linear issues for user {user_id}: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Create issue endpoint
@linear_bp.route("/linear/issues", methods=["POST"])
def create_issue():
    """Create Linear issue"""
    user_id = request.headers.get("user-id")
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    data = request.get_json()
    if not data or 'title' not in data:
        return jsonify(create_response(False, error="issue title is required")), 400
    
    try:
        if not LINEAR_SERVICE_AVAILABLE:
            return jsonify(create_response(False, error="Linear service not available")), 503
        
        service = LinearService()
        issue = await service.create_issue(
            user_id=user_id,
            title=data['title'],
            description=data.get('description', ''),
            team_id=data.get('team_id'),
            project_id=data.get('project_id'),
            assignee_id=data.get('assignee_id'),
            priority=data.get('priority'),
            label_ids=data.get('label_ids', [])
        )
        
        if issue:
            return jsonify(create_response(True, issue)), 201
        else:
            return jsonify(create_response(False, error="Failed to create Linear issue")), 500
            
    except Exception as e:
        logger.error(f"Error creating Linear issue for user {user_id}: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Cycles endpoint
@linear_bp.route("/linear/cycles", methods=["GET"])
def get_cycles():
    """Get Linear cycles"""
    user_id = request.headers.get("user-id")
    team_id = request.args.get("team_id")
    
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    try:
        if not LINEAR_SERVICE_AVAILABLE:
            return jsonify(create_response(False, error="Linear service not available")), 503
        
        service = LinearService()
        cycles = await service.get_team_cycles(user_id, team_id)
        
        return jsonify(create_response(True, cycles))
            
    except Exception as e:
        logger.error(f"Error getting Linear cycles for user {user_id}: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Search endpoint
@linear_bp.route("/linear/search", methods=["GET"])
def search_linear():
    """Search Linear issues, projects, or teams"""
    user_id = request.headers.get("user-id")
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    query = request.args.get("q")
    if not query:
        return jsonify(create_response(False, error="search query is required")), 400
    
    search_type = request.args.get("type", "issues")
    team_id = request.args.get("team_id")
    limit = int(request.args.get("limit", 20))
    
    try:
        if not LINEAR_SERVICE_AVAILABLE:
            return jsonify(create_response(False, error="Linear service not available")), 503
        
        service = LinearService()
        results = await service.search_linear(
            user_id=user_id,
            query=query,
            search_type=search_type,
            team_id=team_id,
            limit=limit
        )
        
        return jsonify(create_response(True, results))
            
    except Exception as e:
        logger.error(f"Error searching Linear for user {user_id}: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Update issue endpoint
@linear_bp.route("/linear/issues/<issue_id>", methods=["PUT"])
def update_issue(issue_id):
    """Update Linear issue"""
    user_id = request.headers.get("user-id")
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    data = request.get_json()
    if not data:
        return jsonify(create_response(False, error="update data is required")), 400
    
    try:
        if not LINEAR_SERVICE_AVAILABLE:
            return jsonify(create_response(False, error="Linear service not available")), 503
        
        service = LinearService()
        issue = await service.update_issue(
            user_id=user_id,
            issue_id=issue_id,
            title=data.get('title'),
            description=data.get('description'),
            status_id=data.get('status_id'),
            assignee_id=data.get('assignee_id'),
            priority=data.get('priority'),
            label_ids=data.get('label_ids')
        )
        
        if issue:
            return jsonify(create_response(True, issue))
        else:
            return jsonify(create_response(False, error="Failed to update Linear issue")), 500
            
    except Exception as e:
        logger.error(f"Error updating Linear issue {issue_id} for user {user_id}: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Create comment endpoint
@linear_bp.route("/linear/issues/<issue_id>/comments", methods=["POST"])
def create_comment(issue_id):
    """Create comment on Linear issue"""
    user_id = request.headers.get("user-id")
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    data = request.get_json()
    if not data or 'body' not in data:
        return jsonify(create_response(False, error="comment body is required")), 400
    
    try:
        if not LINEAR_SERVICE_AVAILABLE:
            return jsonify(create_response(False, error="Linear service not available")), 503
        
        service = LinearService()
        comment = await service.create_comment(
            user_id=user_id,
            issue_id=issue_id,
            body=data['body']
        )
        
        if comment:
            return jsonify(create_response(True, comment)), 201
        else:
            return jsonify(create_response(False, error="Failed to create Linear comment")), 500
            
    except Exception as e:
        logger.error(f"Error creating Linear comment for issue {issue_id} for user {user_id}: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Get issue comments endpoint
@linear_bp.route("/linear/issues/<issue_id>/comments", methods=["GET"])
def get_comments(issue_id):
    """Get comments for Linear issue"""
    user_id = request.headers.get("user-id")
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    try:
        if not LINEAR_SERVICE_AVAILABLE:
            return jsonify(create_response(False, error="Linear service not available")), 503
        
        service = LinearService()
        comments = await service.get_issue_comments(user_id, issue_id)
        
        return jsonify(create_response(True, comments))
            
    except Exception as e:
        logger.error(f"Error getting Linear comments for issue {issue_id} for user {user_id}: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Service info endpoint
@linear_bp.route("/linear/service-info", methods=["GET"])
def get_service_info():
    """Get Linear service information"""
    try:
        if not LINEAR_SERVICE_AVAILABLE:
            return jsonify(create_response(False, error="Linear service not available")), 503
        
        service = LinearService()
        info = await service.get_service_info()
        
        return jsonify(create_response(True, info))
            
    except Exception as e:
        logger.error(f"Error getting Linear service info: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Error handlers
@linear_bp.errorhandler(404)
def not_found(error):
    return jsonify(create_response(False, error="Endpoint not found")), 404

@linear_bp.errorhandler(500)
def internal_error(error):
    return jsonify(create_response(False, error="Internal server error")), 500

@linear_bp.errorhandler(403)
def forbidden(error):
    return jsonify(create_response(False, error="Access forbidden")), 403

@linear_bp.errorhandler(401)
def unauthorized(error):
    return jsonify(create_response(False, error="Unauthorized")), 401