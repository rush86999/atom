"""
Enhanced Jira API Implementation
Complete Flask API handlers for Jira integration
"""

import os
import logging
import json
import asyncio
from datetime import datetime, timezone
from flask import Flask, request, jsonify, Blueprint
from typing import Dict, Any, Optional, List

# Import enhanced services
try:
    from jira_enhanced_service import jira_enhanced_service
    JIRA_ENHANCED_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Enhanced Jira service not available: {e}")
    JIRA_ENHANCED_AVAILABLE = False
    jira_enhanced_service = None

# Import authentication
try:
    from auth_handler_jira import jira_auth_manager, get_validated_tokens
    JIRA_AUTH_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Jira authentication not available: {e}")
    JIRA_AUTH_AVAILABLE = False
    jira_auth_manager = None

# Configure logging
logger = logging.getLogger(__name__)

# Create Flask blueprint
jira_enhanced_bp = Blueprint("jira_enhanced_bp", __name__)

# Error handling decorator
def handle_jira_errors(func):
    """Decorator to handle Jira API errors"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Jira API error: {e}")
            return jsonify({
                "ok": False,
                "error": str(e),
                "error_type": "api_error"
            }), 500
    return wrapper

# Authentication decorator
def require_jira_auth(func):
    """Decorator to require Jira authentication"""
    def wrapper(*args, **kwargs):
        if not JIRA_AUTH_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Jira authentication not available"
            }), 503
        
        try:
            # Get user_id from request
            data = request.get_json() if request.is_json else {}
            user_id = data.get('user_id') or request.headers.get('X-User-ID')
            
            if not user_id:
                return jsonify({
                    "ok": False,
                    "error": "User ID is required"
                }), 400
            
            # Validate tokens (synchronous wrapper)
            tokens = asyncio.run(get_validated_tokens(user_id))
            if not tokens:
                return jsonify({
                    "ok": False,
                    "error": "Jira authentication required"
                }), 401
            
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Jira auth error: {e}")
            return jsonify({
                "ok": False,
                "error": "Authentication failed"
            }), 500
    return wrapper

@jira_enhanced_bp.route("/api/jira/enhanced/health", methods=["GET"])
@handle_jira_errors
def health():
    """Health check for enhanced Jira service"""
    try:
        service_info = jira_enhanced_service.get_service_info() if jira_enhanced_service else {}
        
        return jsonify({
            "ok": True,
            "status": "healthy",
            "service": "enhanced-jira-api",
            "version": "2.0.0",
            "features": {
                "service_available": JIRA_ENHANCED_AVAILABLE,
                "auth_available": JIRA_AUTH_AVAILABLE,
                "mock_mode": service_info.get("mock_mode", False)
            },
            "service_info": service_info
        })
    except Exception as e:
        logger.error(f"Jira health check error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Issue operations
@jira_enhanced_bp.route("/api/jira/enhanced/issues/create", methods=["POST"])
@handle_jira_errors
@require_jira_auth
def create_issue():
    """Create a new Jira issue"""
    try:
        if not JIRA_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Jira service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        project_key = data.get('project_key')
        summary = data.get('summary')
        issue_type = data.get('issue_type')
        description = data.get('description', '')
        priority = data.get('priority', 'Medium')
        assignee = data.get('assignee')
        labels = data.get('labels', [])
        components = data.get('components', [])
        
        # Validate required fields
        if not all([project_key, summary, issue_type]):
            return jsonify({
                "ok": False,
                "error": "Project key, summary, and issue type are required"
            }), 400
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        issue = loop.run_until_complete(
            jira_enhanced_service.create_issue(
                user_id=user_id,
                project_key=project_key,
                summary=summary,
                issue_type=issue_type,
                description=description,
                priority=priority,
                assignee=assignee,
                labels=labels,
                components=components
            )
        )
        loop.close()
        
        if not issue:
            return jsonify({
                "ok": False,
                "error": "Failed to create issue"
            }), 500
        
        return jsonify({
            "ok": True,
            "issue": issue.to_dict(),
            "message": "Issue created successfully"
        })
        
    except Exception as e:
        logger.error(f"Error creating Jira issue: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@jira_enhanced_bp.route("/api/jira/enhanced/issues/get", methods=["POST"])
@handle_jira_errors
@require_jira_auth
def get_issue():
    """Get detailed information about a Jira issue"""
    try:
        if not JIRA_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Jira service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        issue_key = data.get('issue_key')
        
        # Validate required fields
        if not issue_key:
            return jsonify({
                "ok": False,
                "error": "Issue key is required"
            }), 400
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        issue = loop.run_until_complete(
            jira_enhanced_service.get_issue(
                user_id=user_id,
                issue_key=issue_key
            )
        )
        loop.close()
        
        if not issue:
            return jsonify({
                "ok": False,
                "error": "Issue not found"
            }), 404
        
        return jsonify({
            "ok": True,
            "issue": issue.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error getting Jira issue: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@jira_enhanced_bp.route("/api/jira/enhanced/issues/search", methods=["POST"])
@handle_jira_errors
@require_jira_auth
def search_issues():
    """Search for Jira issues using JQL"""
    try:
        if not JIRA_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Jira service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        jql = data.get('jql')
        limit = data.get('limit', 50)
        start_at = data.get('start_at', 0)
        fields = data.get('fields', [])
        
        # Validate required fields
        if not jql:
            return jsonify({
                "ok": False,
                "error": "JQL query is required"
            }), 400
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        issues = loop.run_until_complete(
            jira_enhanced_service.search_issues(
                user_id=user_id,
                jql=jql,
                limit=limit,
                start_at=start_at,
                fields=fields
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "issues": [issue.to_dict() for issue in issues],
            "count": len(issues),
            "search_params": {
                "jql": jql,
                "limit": limit,
                "start_at": start_at,
                "fields": fields
            }
        })
        
    except Exception as e:
        logger.error(f"Error searching Jira issues: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@jira_enhanced_bp.route("/api/jira/enhanced/issues/update", methods=["POST"])
@handle_jira_errors
@require_jira_auth
def update_issue():
    """Update a Jira issue"""
    try:
        if not JIRA_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Jira service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        issue_key = data.get('issue_key')
        fields = data.get('fields', {})
        
        # Validate required fields
        if not issue_key or not fields:
            return jsonify({
                "ok": False,
                "error": "Issue key and fields are required"
            }), 400
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        issue = loop.run_until_complete(
            jira_enhanced_service.update_issue(
                user_id=user_id,
                issue_key=issue_key,
                fields=fields
            )
        )
        loop.close()
        
        if not issue:
            return jsonify({
                "ok": False,
                "error": "Failed to update issue"
            }), 500
        
        return jsonify({
            "ok": True,
            "issue": issue.to_dict(),
            "message": "Issue updated successfully"
        })
        
    except Exception as e:
        logger.error(f"Error updating Jira issue: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Project operations
@jira_enhanced_bp.route("/api/jira/enhanced/projects", methods=["POST"])
@handle_jira_errors
@require_jira_auth
def list_projects():
    """List Jira projects accessible to user"""
    try:
        if not JIRA_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Jira service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        limit = data.get('limit', 50)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        projects = loop.run_until_complete(
            jira_enhanced_service.list_projects(
                user_id=user_id,
                limit=limit
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "projects": [project.to_dict() for project in projects],
            "count": len(projects),
            "filters": {
                "limit": limit
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing Jira projects: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Board operations
@jira_enhanced_bp.route("/api/jira/enhanced/boards", methods=["POST"])
@handle_jira_errors
@require_jira_auth
def list_boards():
    """List Jira boards"""
    try:
        if not JIRA_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Jira service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        project_key = data.get('project_key')
        limit = data.get('limit', 50)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        boards = loop.run_until_complete(
            jira_enhanced_service.list_boards(
                user_id=user_id,
                project_key=project_key,
                limit=limit
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "boards": [board.to_dict() for board in boards],
            "count": len(boards),
            "filters": {
                "project_key": project_key,
                "limit": limit
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing Jira boards: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Sprint operations
@jira_enhanced_bp.route("/api/jira/enhanced/sprints", methods=["POST"])
@handle_jira_errors
@require_jira_auth
def list_sprints():
    """List Jira sprints for a board"""
    try:
        if not JIRA_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Jira service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        board_id = data.get('board_id')
        state = data.get('state')  # active, closed, future
        
        # Validate required fields
        if not board_id:
            return jsonify({
                "ok": False,
                "error": "Board ID is required"
            }), 400
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        sprints = loop.run_until_complete(
            jira_enhanced_service.list_sprints(
                user_id=user_id,
                board_id=board_id,
                state=state
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "sprints": [sprint.to_dict() for sprint in sprints],
            "count": len(sprints),
            "filters": {
                "board_id": board_id,
                "state": state
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing Jira sprints: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# User operations
@jira_enhanced_bp.route("/api/jira/enhanced/users/search", methods=["POST"])
@handle_jira_errors
@require_jira_auth
def search_users():
    """Search for Jira users"""
    try:
        if not JIRA_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Jira service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        query = data.get('query')
        limit = data.get('limit', 50)
        
        # Validate required fields
        if not query:
            return jsonify({
                "ok": False,
                "error": "Search query is required"
            }), 400
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        users = loop.run_until_complete(
            jira_enhanced_service.search_users(
                user_id=user_id,
                query=query,
                limit=limit
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "users": [user.to_dict() for user in users],
            "count": len(users),
            "filters": {
                "query": query,
                "limit": limit
            }
        })
        
    except Exception as e:
        logger.error(f"Error searching Jira users: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Utility endpoints
@jira_enhanced_bp.route("/api/jira/enhanced/sync", methods=["POST"])
@handle_jira_errors
@require_jira_auth
def sync_data():
    """Sync Jira data for user"""
    try:
        if not JIRA_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Jira service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        sync_types = data.get('sync_types', ['projects', 'issues', 'boards'])
        
        results = {}
        
        # Sync projects
        if 'projects' in sync_types:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            projects = loop.run_until_complete(
                jira_enhanced_service.list_projects(user_id=user_id, limit=1000)
            )
            loop.close()
            results['projects'] = {
                'count': len(projects),
                'synced': True
            }
        
        # Sync recent issues
        if 'issues' in sync_types:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            issues = loop.run_until_complete(
                jira_enhanced_service.search_issues(user_id=user_id, jql='order by created DESC', limit=1000)
            )
            loop.close()
            results['issues'] = {
                'count': len(issues),
                'synced': True
            }
        
        # Sync boards
        if 'boards' in sync_types:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            boards = loop.run_until_complete(
                jira_enhanced_service.list_boards(user_id=user_id, limit=1000)
            )
            loop.close()
            results['boards'] = {
                'count': len(boards),
                'synced': True
            }
        
        return jsonify({
            "ok": True,
            "sync_results": results,
            "synced_at": datetime.utcnow().isoformat(),
            "user_id": user_id
        })
        
    except Exception as e:
        logger.error(f"Error syncing Jira data: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@jira_enhanced_bp.route("/api/jira/enhanced/status", methods=["POST"])
@handle_jira_errors
def get_status():
    """Get enhanced Jira service status"""
    try:
        data = request.get_json() if request.is_json else {}
        user_id = data.get('user_id')
        
        service_info = jira_enhanced_service.get_service_info() if jira_enhanced_service else {}
        
        status_data = {
            "ok": True,
            "service": "enhanced-jira-api",
            "status": "available",
            "version": "2.0.0",
            "capabilities": {
                "service_available": JIRA_ENHANCED_AVAILABLE,
                "auth_available": JIRA_AUTH_AVAILABLE,
                "mock_mode": service_info.get("mock_mode", False),
                "encryption_available": bool(os.getenv('ATOM_OAUTH_ENCRYPTION_KEY'))
            },
            "service_info": service_info,
            "api_endpoints": [
                "/api/jira/enhanced/health",
                "/api/jira/enhanced/issues/create",
                "/api/jira/enhanced/issues/get",
                "/api/jira/enhanced/issues/search",
                "/api/jira/enhanced/issues/update",
                "/api/jira/enhanced/projects",
                "/api/jira/enhanced/boards",
                "/api/jira/enhanced/sprints",
                "/api/jira/enhanced/users/search",
                "/api/jira/enhanced/sync",
                "/api/jira/enhanced/status"
            ]
        }
        
        if user_id:
            # Add user-specific status
            try:
                if JIRA_AUTH_AVAILABLE:
                    tokens = asyncio.run(get_validated_tokens(user_id))
                    status_data["user_authenticated"] = tokens is not None
                else:
                    status_data["user_authenticated"] = False
            except:
                status_data["user_authenticated"] = False
        
        return jsonify(status_data)
        
    except Exception as e:
        logger.error(f"Error getting Jira service status: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Webhook operations
@jira_enhanced_bp.route("/api/jira/enhanced/webhooks", methods=["POST"])
@handle_jira_errors
def handle_webhook():
    """Handle Jira webhooks"""
    try:
        data = request.get_json()
        
        # Get webhook type
        webhook_event = data.get("webhookEvent")
        
        if webhook_event:
            logger.info(f"Jira webhook event received: {webhook_event}")
            await handle_jira_event(data, webhook_event)
        else:
            logger.info("Jira webhook validation received")
            return jsonify({"validationResponse": "Jira webhook active"})
        
        return jsonify({
            "ok": True,
            "message": "Webhook processed successfully"
        })
        
    except Exception as e:
        logger.error(f"Error handling Jira webhook: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

async def handle_jira_event(event_data: Dict[str, Any], event_type: str):
    """Handle Jira event"""
    try:
        logger.info(f"Jira event received: {event_type}")
        
        # Process different event types
        if event_type == 'jira:issue_created':
            await handle_issue_created_event(event_data)
        elif event_type == 'jira:issue_updated':
            await handle_issue_updated_event(event_data)
        elif event_type == 'jira:issue_deleted':
            await handle_issue_deleted_event(event_data)
        elif event_type == 'jira:sprint_started':
            await handle_sprint_started_event(event_data)
        elif event_type == 'jira:sprint_closed':
            await handle_sprint_closed_event(event_data)
        
    except Exception as e:
        logger.error(f"Error processing Jira event: {e}")

async def handle_issue_created_event(event_data: Dict[str, Any]):
    """Handle Jira issue created event"""
    try:
        issue = event_data.get("issue", {})
        logger.info(f"Jira issue created: {issue.get('key', 'unknown')}")
        
    except Exception as e:
        logger.error(f"Error handling Jira issue created event: {e}")

async def handle_issue_updated_event(event_data: Dict[str, Any]):
    """Handle Jira issue updated event"""
    try:
        issue = event_data.get("issue", {})
        logger.info(f"Jira issue updated: {issue.get('key', 'unknown')}")
        
    except Exception as e:
        logger.error(f"Error handling Jira issue updated event: {e}")

async def handle_issue_deleted_event(event_data: Dict[str, Any]):
    """Handle Jira issue deleted event"""
    try:
        issue = event_data.get("issue", {})
        logger.info(f"Jira issue deleted: {issue.get('key', 'unknown')}")
        
    except Exception as e:
        logger.error(f"Error handling Jira issue deleted event: {e}")

async def handle_sprint_started_event(event_data: Dict[str, Any]):
    """Handle Jira sprint started event"""
    try:
        sprint = event_data.get("sprint", {})
        logger.info(f"Jira sprint started: {sprint.get('name', 'unknown')}")
        
    except Exception as e:
        logger.error(f"Error handling Jira sprint started event: {e}")

async def handle_sprint_closed_event(event_data: Dict[str, Any]):
    """Handle Jira sprint closed event"""
    try:
        sprint = event_data.get("sprint", {})
        logger.info(f"Jira sprint closed: {sprint.get('name', 'unknown')}")
        
    except Exception as e:
        logger.error(f"Error handling Jira sprint closed event: {e}")

# Register blueprint with Flask app
def register_jira_enhanced_bp(app: Flask):
    """Register enhanced Jira blueprint with Flask app"""
    app.register_blueprint(jira_enhanced_bp)
    logger.info("Enhanced Jira API blueprint registered")

# Export components
__all__ = [
    'jira_enhanced_bp',
    'register_jira_enhanced_bp'
]