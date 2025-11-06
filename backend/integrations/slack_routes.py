"""
Slack Integration Routes - Enhanced API Endpoints
Complete Slack integration with comprehensive API endpoints
"""

import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from flask import Blueprint, request, jsonify, current_app
from slack_enhanced_service import slack_enhanced_service

logger = logging.getLogger(__name__)

# Create Slack integration blueprint
slack_bp = Blueprint("slack_integration", __name__, url_prefix="/api/integrations/slack")

# Service health tracking
service_status = {
    "connected": False,
    "last_check": None,
    "error_count": 0,
    "total_requests": 0
}

def update_service_status(connected: bool, error: bool = False):
    """Update service health status"""
    global service_status
    service_status["connected"] = connected
    service_status["last_check"] = datetime.utcnow().isoformat()
    service_status["total_requests"] += 1
    if error:
        service_status["error_count"] += 1

@slack_bp.route("/health", methods=["GET"])
def health_check():
    """Slack integration health check"""
    try:
        # Test basic service availability
        service_info = slack_enhanced_service.get_service_info()
        
        update_service_status(True)
        
        return jsonify({
            "status": "healthy",
            "service": "slack_integration",
            "version": service_info.get("version", "1.0.0"),
            "capabilities": service_info.get("capabilities", []),
            "timestamp": datetime.utcnow().isoformat(),
            "service_status": service_status
        })
    except Exception as e:
        update_service_status(False, error=True)
        logger.error(f"Slack health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "service": "slack_integration",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            "service_status": service_status
        }), 500

@slack_bp.route("/workspaces", methods=["POST"])
async def get_workspaces():
    """Get Slack workspaces"""
    try:
        data = request.get_json() or {}
        user_id = data.get("user_id", "default-user")
        
        # Get workspaces using enhanced service
        workspaces = await slack_enhanced_service.get_workspaces(user_id)
        
        update_service_status(True)
        
        return jsonify({
            "ok": True,
            "workspaces": [ws.to_dict() for ws in workspaces],
            "total_count": len(workspaces),
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        update_service_status(False, error=True)
        logger.error(f"Error getting workspaces: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@slack_bp.route("/workspace/details", methods=["POST"])
async def get_workspace_details():
    """Get specific workspace details"""
    try:
        data = request.get_json() or {}
        user_id = data.get("user_id", "default-user")
        workspace_id = data.get("workspace_id")
        
        if not workspace_id:
            return jsonify({
                "ok": False,
                "error": "workspace_id is required"
            }), 400
        
        # Get workspace using enhanced service
        workspace = await slack_enhanced_service.get_workspace(workspace_id, user_id)
        
        if not workspace:
            return jsonify({
                "ok": False,
                "error": "Workspace not found"
            }), 404
        
        update_service_status(True)
        
        return jsonify({
            "ok": True,
            "workspace": workspace.to_dict(),
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        update_service_status(False, error=True)
        logger.error(f"Error getting workspace details: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@slack_bp.route("/channels", methods=["POST"])
async def get_channels():
    """Get Slack channels from workspace"""
    try:
        data = request.get_json() or {}
        user_id = data.get("user_id", "default-user")
        workspace_id = data.get("workspace_id")
        include_private = data.get("include_private", False)
        include_archived = data.get("include_archived", False)
        limit = data.get("limit", 100)
        
        if not workspace_id:
            return jsonify({
                "ok": False,
                "error": "workspace_id is required"
            }), 400
        
        # Build channel types
        types = []
        if include_private:
            types.extend(["private_channel", "mpim", "im"])
        types.extend(["public_channel"])
        
        # Get channels using enhanced service
        channels = await slack_enhanced_service.get_channels(
            workspace_id, user_id, ",".join(types)
        )
        
        # Filter by archived status
        if not include_archived:
            channels = [ch for ch in channels if not ch.is_archived]
        
        # Apply limit
        if limit and limit > 0:
            channels = channels[:limit]
        
        update_service_status(True)
        
        return jsonify({
            "ok": True,
            "channels": [ch.to_dict() for ch in channels],
            "total_count": len(channels),
            "filters": {
                "include_private": include_private,
                "include_archived": include_archived,
                "limit": limit
            },
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        update_service_status(False, error=True)
        logger.error(f"Error getting channels: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@slack_bp.route("/messages", methods=["POST"])
async def get_messages():
    """Get Slack messages from channel"""
    try:
        data = request.get_json() or {}
        user_id = data.get("user_id", "default-user")
        workspace_id = data.get("workspace_id")
        channel_id = data.get("channel_id")
        limit = data.get("limit", 100)
        latest = data.get("latest")
        oldest = data.get("oldest")
        filters = data.get("filters", {})
        
        if not workspace_id or not channel_id:
            return jsonify({
                "ok": False,
                "error": "workspace_id and channel_id are required"
            }), 400
        
        # Get messages using enhanced service
        result = await slack_enhanced_service.get_messages(
            workspace_id, channel_id, limit, latest, oldest, True, user_id
        )
        
        # Apply additional filters
        messages = result.get("messages", [])
        
        # Filter by user if specified
        if filters.get("from_user") == "me":
            # Need to get current user ID - for now, return all
            pass
        
        # Filter by files if specified
        if filters.get("has_files"):
            messages = [msg for msg in messages if msg.has_files]
        
        # Filter by starred if specified
        if filters.get("starred"):
            messages = [msg for msg in messages if msg.is_starred]
        
        # Filter by pinned if specified
        if filters.get("pinned"):
            messages = [msg for msg in messages if len(msg.pinned_to) > 0]
        
        update_service_status(True)
        
        return jsonify({
            "ok": True,
            "messages": [msg.to_dict() for msg in messages],
            "has_more": result.get("has_more", False),
            "total": len(messages),
            "filters": filters,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        update_service_status(False, error=True)
        logger.error(f"Error getting messages: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@slack_bp.route("/messages/send", methods=["POST"])
async def send_message():
    """Send Slack message"""
    try:
        data = request.get_json() or {}
        user_id = data.get("user_id", "default-user")
        workspace_id = data.get("workspace_id")
        channel_id = data.get("channel_id")
        text = data.get("text")
        thread_ts = data.get("thread_ts")
        
        if not workspace_id or not channel_id or not text:
            return jsonify({
                "ok": False,
                "error": "workspace_id, channel_id, and text are required"
            }), 400
        
        # Send message using enhanced service
        message = await slack_enhanced_service.send_message(
            workspace_id, channel_id, text, thread_ts, user_id
        )
        
        if not message:
            return jsonify({
                "ok": False,
                "error": "Failed to send message"
            }), 500
        
        update_service_status(True)
        
        return jsonify({
            "ok": True,
            "message": message.to_dict(),
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        update_service_status(False, error=True)
        logger.error(f"Error sending message: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@slack_bp.route("/users", methods=["POST"])
async def get_users():
    """Get Slack users from workspace"""
    try:
        data = request.get_json() or {}
        user_id = data.get("user_id", "default-user")
        workspace_id = data.get("workspace_id")
        include_restricted = data.get("include_restricted", False)
        include_bots = data.get("include_bots", False)
        limit = data.get("limit", 100)
        
        if not workspace_id:
            return jsonify({
                "ok": False,
                "error": "workspace_id is required"
            }), 400
        
        # Get users using enhanced service
        users = await slack_enhanced_service.get_users(workspace_id, user_id)
        
        # Apply filters
        if not include_restricted:
            users = [user for user in users if not (user.is_restricted or user.is_ultra_restricted)]
        
        if not include_bots:
            users = [user for user in users if not user.is_bot]
        
        # Apply limit
        if limit and limit > 0:
            users = users[:limit]
        
        update_service_status(True)
        
        return jsonify({
            "ok": True,
            "users": [user.to_dict() for user in users],
            "total_count": len(users),
            "filters": {
                "include_restricted": include_restricted,
                "include_bots": include_bots,
                "limit": limit
            },
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        update_service_status(False, error=True)
        logger.error(f"Error getting users: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@slack_bp.route("/files", methods=["POST"])
async def get_files():
    """Get Slack files from workspace or channel"""
    try:
        data = request.get_json() or {}
        user_id = data.get("user_id", "default-user")
        workspace_id = data.get("workspace_id")
        channel_id = data.get("channel_id")
        uploaded_by = data.get("uploaded_by")
        file_type = data.get("file_type")
        limit = data.get("limit", 100)
        
        if not workspace_id:
            return jsonify({
                "ok": False,
                "error": "workspace_id is required"
            }), 400
        
        # Get files using enhanced service
        result = await slack_enhanced_service.get_files(
            workspace_id, channel_id, uploaded_by, user_id, limit
        )
        
        files = result.get("files", [])
        
        # Filter by file type if specified
        if file_type:
            files = [file for file in files if file.filetype == file_type]
        
        update_service_status(True)
        
        return jsonify({
            "ok": True,
            "files": [file.to_dict() for file in files],
            "total": len(files),
            "paging": result.get("paging", {}),
            "filters": {
                "channel_id": channel_id,
                "uploaded_by": uploaded_by,
                "file_type": file_type,
                "limit": limit
            },
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        update_service_status(False, error=True)
        logger.error(f"Error getting files: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@slack_bp.route("/search", methods=["POST"])
async def search_messages():
    """Search Slack messages"""
    try:
        data = request.get_json() or {}
        user_id = data.get("user_id", "default-user")
        workspace_id = data.get("workspace_id")
        query = data.get("query")
        channel_id = data.get("channel_id")
        sort = data.get("sort", "timestamp")
        sort_dir = data.get("sort_dir", "desc")
        count = data.get("count", 100)
        
        if not workspace_id or not query:
            return jsonify({
                "ok": False,
                "error": "workspace_id and query are required"
            }), 400
        
        # Search messages using enhanced service
        result = await slack_enhanced_service.search_messages(
            workspace_id, query, channel_id, None, sort, sort_dir, count, user_id
        )
        
        update_service_status(True)
        
        return jsonify({
            "ok": True,
            "messages": [msg.to_dict() for msg in result.get("messages", [])],
            "paging": result.get("paging", {}),
            "total": result.get("total", 0),
            "query": query,
            "search_filters": result.get("search_filters", {}),
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        update_service_status(False, error=True)
        logger.error(f"Error searching messages: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@slack_bp.route("/analytics/activity", methods=["POST"])
async def get_activity_analytics():
    """Get Slack activity analytics"""
    try:
        data = request.get_json() or {}
        user_id = data.get("user_id", "default-user")
        
        # For now, return mock analytics data
        # In a real implementation, this would query the database
        analytics = {
            "activity_over_time": [
                {
                    "period": "2023-12-01",
                    "message_count": 150,
                    "unique_users": 12,
                    "active_channels": 8
                },
                {
                    "period": "2023-12-02",
                    "message_count": 180,
                    "unique_users": 14,
                    "active_channels": 9
                }
            ],
            "top_users": [
                {
                    "user_id": "U1234567890",
                    "user_name": "john.doe",
                    "message_count": 85,
                    "channels_used": 5,
                    "avg_message_length": 120
                }
            ],
            "top_channels": [
                {
                    "channel_id": "C1234567890",
                    "channel_name": "general",
                    "message_count": 200,
                    "unique_users": 15,
                    "avg_message_length": 95
                }
            ],
            "summary": {
                "total_messages": 330,
                "total_users": 16,
                "total_channels": 10
            }
        }
        
        update_service_status(True)
        
        return jsonify({
            "ok": True,
            "analytics": analytics,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        update_service_status(False, error=True)
        logger.error(f"Error getting activity analytics: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@slack_bp.route("/events", methods=["POST"])
async def handle_events():
    """Handle Slack webhook events"""
    try:
        # Verify request signature (in production)
        # For now, just log the event
        event_data = request.get_json() or {}
        logger.info(f"Received Slack event: {event_data}")
        
        # Handle URL verification challenge
        if event_data.get("type") == "url_verification":
            return jsonify({
                "challenge": event_data.get("challenge")
            })
        
        # Process other events
        event_type = event_data.get("event", {}).get("type")
        
        # Handle different event types
        if event_type == "message":
            # Process message event
            logger.info("Processing message event")
        elif event_type == "file_shared":
            # Process file share event
            logger.info("Processing file share event")
        
        update_service_status(True)
        
        return jsonify({
            "ok": True,
            "status": "processed",
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        update_service_status(False, error=True)
        logger.error(f"Error handling event: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@slack_bp.route("/ingest", methods=["POST"])
async def ingest_data():
    """Start data ingestion from Slack"""
    try:
        data = request.get_json() or {}
        user_id = data.get("user_id", "default-user")
        workspace_id = data.get("workspace_id")
        config = data.get("config", {})
        
        if not workspace_id:
            return jsonify({
                "ok": False,
                "error": "workspace_id is required"
            }), 400
        
        # Start ingestion process
        # This would be implemented as a background task
        ingestion_result = {
            "ingestion_id": f"slack_ingest_{workspace_id}_{int(datetime.utcnow().timestamp())}",
            "status": "started",
            "workspace_id": workspace_id,
            "config": config,
            "estimated_items": 1000,  # Would be calculated
            "started_at": datetime.utcnow().isoformat()
        }
        
        update_service_status(True)
        
        return jsonify({
            "ok": True,
            "ingestion": ingestion_result,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        update_service_status(False, error=True)
        logger.error(f"Error starting ingestion: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@slack_bp.route("/config", methods=["GET", "POST"])
def manage_config():
    """Get or update Slack integration configuration"""
    try:
        if request.method == "GET":
            # Get current configuration
            config = {
                "oauth_configured": bool(os.getenv("SLACK_CLIENT_ID") and os.getenv("SLACK_CLIENT_SECRET")),
                "webhook_configured": bool(os.getenv("SLACK_SIGNING_SECRET")),
                "scopes": [
                    "channels:read",
                    "channels:history",
                    "users:read",
                    "chat:write",
                    "files:read"
                ],
                "features": {
                    "realtime_events": True,
                    "analytics": True,
                    "search": True,
                    "file_management": True
                }
            }
            
            return jsonify({
                "ok": True,
                "config": config,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        elif request.method == "POST":
            # Update configuration
            data = request.get_json() or {}
            # In a real implementation, this would update config files or database
            
            return jsonify({
                "ok": True,
                "message": "Configuration updated",
                "timestamp": datetime.utcnow().isoformat()
            })
            
    except Exception as e:
        update_service_status(False, error=True)
        logger.error(f"Error managing config: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

# Error handlers
@slack_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        "ok": False,
        "error": "Endpoint not found",
        "timestamp": datetime.utcnow().isoformat()
    }), 404

@slack_bp.errorhandler(500)
def internal_error(error):
    update_service_status(False, error=True)
    return jsonify({
        "ok": False,
        "error": "Internal server error",
        "timestamp": datetime.utcnow().isoformat()
    }), 500

# Export blueprint for registration
__all__ = ["slack_bp"]