"""
Enhanced Microsoft Teams API Implementation
Complete Flask API handlers for Teams integration
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
    from teams_enhanced_service import teams_enhanced_service
    TEAMS_ENHANCED_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Enhanced Teams service not available: {e}")
    TEAMS_ENHANCED_AVAILABLE = False
    teams_enhanced_service = None

# Import authentication
try:
    from auth_handler_teams_complete import teams_auth_manager, get_validated_tokens
    TEAMS_AUTH_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Teams authentication not available: {e}")
    TEAMS_AUTH_AVAILABLE = False
    teams_auth_manager = None

# Configure logging
logger = logging.getLogger(__name__)

# Create Flask blueprint
teams_enhanced_bp = Blueprint("teams_enhanced_bp", __name__)

# Error handling decorator
def handle_teams_errors(func):
    """Decorator to handle Teams API errors"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Teams API error: {e}")
            return jsonify({
                "ok": False,
                "error": str(e),
                "error_type": "api_error"
            }), 500
    return wrapper

# Authentication decorator
def require_teams_auth(func):
    """Decorator to require Teams authentication"""
    def wrapper(*args, **kwargs):
        if not TEAMS_AUTH_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Teams authentication not available"
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
                    "error": "Teams authentication required"
                }), 401
            
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Teams auth error: {e}")
            return jsonify({
                "ok": False,
                "error": "Authentication failed"
            }), 500
    return wrapper

@teams_enhanced_bp.route("/api/teams/enhanced/health", methods=["GET"])
@handle_teams_errors
def health():
    """Health check for enhanced Teams service"""
    try:
        service_info = teams_enhanced_service.get_service_info() if teams_enhanced_service else {}
        
        return jsonify({
            "ok": True,
            "status": "healthy",
            "service": "enhanced-teams-api",
            "version": "2.0.0",
            "features": {
                "service_available": TEAMS_ENHANCED_AVAILABLE,
                "auth_available": TEAMS_AUTH_AVAILABLE,
                "mock_mode": service_info.get("mock_mode", False)
            },
            "service_info": service_info
        })
    except Exception as e:
        logger.error(f"Teams health check error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Channel operations
@teams_enhanced_bp.route("/api/teams/enhanced/channels", methods=["POST"])
@handle_teams_errors
@require_teams_auth
def list_channels():
    """List channels accessible to user"""
    try:
        if not TEAMS_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Teams service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        membership_filter = data.get('membership_filter', 'user')
        limit = data.get('limit', 50)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        channels = loop.run_until_complete(
            teams_enhanced_service.list_channels(
                user_id=user_id,
                membership_filter=membership_filter,
                limit=limit
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "channels": [channel.to_dict() for channel in channels],
            "count": len(channels),
            "filters": {
                "membership_filter": membership_filter,
                "limit": limit
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing Teams channels: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@teams_enhanced_bp.route("/api/teams/enhanced/channels/info", methods=["POST"])
@handle_teams_errors
@require_teams_auth
def get_channel_info():
    """Get information about a specific channel"""
    try:
        if not TEAMS_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Teams service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        channel_id = data.get('channel_id')
        
        # Validate required fields
        if not channel_id:
            return jsonify({
                "ok": False,
                "error": "Channel ID is required"
            }), 400
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        channel = loop.run_until_complete(
            teams_enhanced_service.get_channel_info(
                user_id=user_id,
                channel_id=channel_id
            )
        )
        loop.close()
        
        if not channel:
            return jsonify({
                "ok": False,
                "error": "Channel not found"
            }), 404
        
        return jsonify({
            "ok": True,
            "channel": channel.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error getting Teams channel info: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Message operations
@teams_enhanced_bp.route("/api/teams/enhanced/messages/send", methods=["POST"])
@handle_teams_errors
@require_teams_auth
def send_message():
    """Send a message to a Teams channel"""
    try:
        if not TEAMS_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Teams service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        channel_id = data.get('channel_id')
        content = data.get('content')
        subject = data.get('subject', '')
        importance = data.get('importance', 'normal')
        thread_id = data.get('thread_id')
        
        # Validate required fields
        if not channel_id or not content:
            return jsonify({
                "ok": False,
                "error": "Channel ID and content are required"
            }), 400
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        message = loop.run_until_complete(
            teams_enhanced_service.send_message(
                user_id=user_id,
                channel_id=channel_id,
                content=content,
                subject=subject,
                importance=importance,
                thread_id=thread_id
            )
        )
        loop.close()
        
        if not message:
            return jsonify({
                "ok": False,
                "error": "Failed to send message"
            }), 500
        
        return jsonify({
            "ok": True,
            "message": {
                "id": message.id,
                "subject": message.subject,
                "body": message.body,
                "importance": message.importance,
                "conversationId": message.conversation_id,
                "threadId": message.thread_id,
                "createdDateTime": message.created_at
            },
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Error sending Teams message: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@teams_enhanced_bp.route("/api/teams/enhanced/messages", methods=["POST"])
@handle_teams_errors
@require_teams_auth
def list_messages():
    """List messages from a Teams channel"""
    try:
        if not TEAMS_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Teams service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        channel_id = data.get('channel_id')
        limit = data.get('limit', 50)
        before = data.get('before')
        after = data.get('after')
        
        # Validate required fields
        if not channel_id:
            return jsonify({
                "ok": False,
                "error": "Channel ID is required"
            }), 400
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        messages = loop.run_until_complete(
            teams_enhanced_service.list_messages(
                user_id=user_id,
                channel_id=channel_id,
                limit=limit,
                before=before,
                after=after
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "messages": [message.to_dict() for message in messages],
            "count": len(messages),
            "channel": channel_id,
            "filters": {
                "limit": limit,
                "before": before,
                "after": after
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing Teams messages: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# User operations
@teams_enhanced_bp.route("/api/teams/enhanced/users", methods=["POST"])
@handle_teams_errors
@require_teams_auth
def list_users():
    """List users in Teams organization"""
    try:
        if not TEAMS_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Teams service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        limit = data.get('limit', 100)
        search_query = data.get('search_query')
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        users = loop.run_until_complete(
            teams_enhanced_service.list_users(
                user_id=user_id,
                limit=limit,
                search_query=search_query
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "users": [user.to_dict() for user in users],
            "count": len(users),
            "filters": {
                "limit": limit,
                "search_query": search_query
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing Teams users: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@teams_enhanced_bp.route("/api/teams/enhanced/users/info", methods=["POST"])
@handle_teams_errors
@require_teams_auth
def get_user_info():
    """Get information about a specific user"""
    try:
        if not TEAMS_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Teams service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        target_user_id = data.get('target_user_id')
        
        # Validate required fields
        if not target_user_id:
            return jsonify({
                "ok": False,
                "error": "Target user ID is required"
            }), 400
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        user = loop.run_until_complete(
            teams_enhanced_service.get_user_info(
                user_id=user_id,
                target_user_id=target_user_id
            )
        )
        loop.close()
        
        if not user:
            return jsonify({
                "ok": False,
                "error": "User not found"
            }), 404
        
        return jsonify({
            "ok": True,
            "user": user.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error getting Teams user info: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Meeting operations
@teams_enhanced_bp.route("/api/teams/enhanced/meetings", methods=["POST"])
@handle_teams_errors
@require_teams_auth
def list_meetings():
    """List meetings for user"""
    try:
        if not TEAMS_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Teams service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        limit = data.get('limit', 50)
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        meetings = loop.run_until_complete(
            teams_enhanced_service.list_meetings(
                user_id=user_id,
                limit=limit,
                start_date=start_date,
                end_date=end_date
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "meetings": [meeting.to_dict() for meeting in meetings],
            "count": len(meetings),
            "filters": {
                "limit": limit,
                "start_date": start_date,
                "end_date": end_date
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing Teams meetings: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@teams_enhanced_bp.route("/api/teams/enhanced/meetings/create", methods=["POST"])
@handle_teams_errors
@require_teams_auth
def create_meeting():
    """Create a Teams meeting"""
    try:
        if not TEAMS_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Teams service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        subject = data.get('subject')
        content = data.get('content')
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        attendees = data.get('attendees', [])
        location = data.get('location')
        importance = data.get('importance', 'normal')
        
        # Validate required fields
        if not subject or not start_time or not end_time:
            return jsonify({
                "ok": False,
                "error": "Subject, start time, and end time are required"
            }), 400
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        meeting = loop.run_until_complete(
            teams_enhanced_service.create_meeting(
                user_id=user_id,
                subject=subject,
                content=content,
                start_time=start_time,
                end_time=end_time,
                attendees=attendees,
                location=location,
                importance=importance
            )
        )
        loop.close()
        
        if not meeting:
            return jsonify({
                "ok": False,
                "error": "Failed to create meeting"
            }), 500
        
        return jsonify({
            "ok": True,
            "meeting": meeting.to_dict(),
            "message": "Meeting created successfully"
        })
        
    except Exception as e:
        logger.error(f"Error creating Teams meeting: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# File operations
@teams_enhanced_bp.route("/api/teams/enhanced/files", methods=["POST"])
@handle_teams_errors
@require_teams_auth
def list_files():
    """List files from user's OneDrive"""
    try:
        if not TEAMS_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Teams service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        limit = data.get('limit', 50)
        folder_path = data.get('folder_path')
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        files = loop.run_until_complete(
            teams_enhanced_service.list_files(
                user_id=user_id,
                limit=limit,
                folder_path=folder_path
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "files": [file.to_dict() for file in files],
            "count": len(files),
            "filters": {
                "limit": limit,
                "folder_path": folder_path
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing Teams files: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@teams_enhanced_bp.route("/api/teams/enhanced/files/upload", methods=["POST"])
@handle_teams_errors
@require_teams_auth
def upload_file():
    """Upload a file to user's OneDrive"""
    try:
        if not TEAMS_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Teams service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        file_path = data.get('file_path')
        filename = data.get('filename')
        folder_path = data.get('folder_path')
        
        # Validate required fields
        if not file_path:
            return jsonify({
                "ok": False,
                "error": "File path is required"
            }), 400
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        file = loop.run_until_complete(
            teams_enhanced_service.upload_file(
                user_id=user_id,
                file_path=file_path,
                filename=filename,
                folder_path=folder_path
            )
        )
        loop.close()
        
        if not file:
            return jsonify({
                "ok": False,
                "error": "Failed to upload file"
            }), 500
        
        return jsonify({
            "ok": True,
            "file": file.to_dict(),
            "message": "File uploaded successfully"
        })
        
    except Exception as e:
        logger.error(f"Error uploading Teams file: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Webhook operations
@teams_enhanced_bp.route("/api/teams/enhanced/webhooks", methods=["POST"])
@handle_teams_errors
def handle_webhook():
    """Handle Microsoft Teams webhooks"""
    try:
        data = request.get_json()
        
        # Get webhook type
        value = data.get('value', [])
        
        if not value:
            logger.info("Teams webhook validation received")
            return jsonify({"validationResponse": "Teams webhook active"})
        
        # Handle different event types
        for event in value:
            event_type = event.get('changeType')
            resource = event.get('resource', '')
            await handle_teams_event(event, event_type, resource)
        
        return jsonify({
            "ok": True,
            "message": "Webhook processed successfully"
        })
        
    except Exception as e:
        logger.error(f"Error handling Teams webhook: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

async def handle_teams_event(event_data: Dict[str, Any], event_type: str, resource: str):
    """Handle Teams event"""
    try:
        logger.info(f"Teams event received: {event_type} for resource: {resource}")
        
        # Process different event types
        if event_type == 'created':
            await handle_event_created(event_data, resource)
        elif event_type == 'updated':
            await handle_event_updated(event_data, resource)
        elif event_type == 'deleted':
            await handle_event_deleted(event_data, resource)
        
    except Exception as e:
        logger.error(f"Error processing Teams event: {e}")

async def handle_event_created(event_data: Dict[str, Any], resource: str):
    """Handle Teams event created"""
    try:
        logger.info(f"Teams resource created: {resource}")
        
    except Exception as e:
        logger.error(f"Error handling Teams created event: {e}")

async def handle_event_updated(event_data: Dict[str, Any], resource: str):
    """Handle Teams event updated"""
    try:
        logger.info(f"Teams resource updated: {resource}")
        
    except Exception as e:
        logger.error(f"Error handling Teams updated event: {e}")

async def handle_event_deleted(event_data: Dict[str, Any], resource: str):
    """Handle Teams event deleted"""
    try:
        logger.info(f"Teams resource deleted: {resource}")
        
    except Exception as e:
        logger.error(f"Error handling Teams deleted event: {e}")

# Utility endpoints
@teams_enhanced_bp.route("/api/teams/enhanced/sync", methods=["POST"])
@handle_teams_errors
@require_teams_auth
def sync_data():
    """Sync Teams data for user"""
    try:
        if not TEAMS_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Teams service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        sync_types = data.get('sync_types', ['channels', 'users', 'meetings'])
        
        results = {}
        
        # Sync channels
        if 'channels' in sync_types:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            channels = loop.run_until_complete(
                teams_enhanced_service.list_channels(user_id=user_id, limit=1000)
            )
            loop.close()
            results['channels'] = {
                'count': len(channels),
                'synced': True
            }
        
        # Sync users
        if 'users' in sync_types:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            users = loop.run_until_complete(
                teams_enhanced_service.list_users(user_id=user_id, limit=1000)
            )
            loop.close()
            results['users'] = {
                'count': len(users),
                'synced': True
            }
        
        # Sync meetings
        if 'meetings' in sync_types:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            meetings = loop.run_until_complete(
                teams_enhanced_service.list_meetings(user_id=user_id, limit=1000)
            )
            loop.close()
            results['meetings'] = {
                'count': len(meetings),
                'synced': True
            }
        
        return jsonify({
            "ok": True,
            "sync_results": results,
            "synced_at": datetime.utcnow().isoformat(),
            "user_id": user_id
        })
        
    except Exception as e:
        logger.error(f"Error syncing Teams data: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@teams_enhanced_bp.route("/api/teams/enhanced/status", methods=["POST"])
@handle_teams_errors
def get_status():
    """Get enhanced Teams service status"""
    try:
        data = request.get_json() if request.is_json else {}
        user_id = data.get('user_id')
        
        service_info = teams_enhanced_service.get_service_info() if teams_enhanced_service else {}
        
        status_data = {
            "ok": True,
            "service": "enhanced-teams-api",
            "status": "available",
            "version": "2.0.0",
            "capabilities": {
                "service_available": TEAMS_ENHANCED_AVAILABLE,
                "auth_available": TEAMS_AUTH_AVAILABLE,
                "mock_mode": service_info.get("mock_mode", False),
                "encryption_available": bool(os.getenv('ATOM_OAUTH_ENCRYPTION_KEY'))
            },
            "service_info": service_info,
            "api_endpoints": [
                "/api/teams/enhanced/health",
                "/api/teams/enhanced/channels",
                "/api/teams/enhanced/channels/info",
                "/api/teams/enhanced/messages/send",
                "/api/teams/enhanced/messages",
                "/api/teams/enhanced/users",
                "/api/teams/enhanced/users/info",
                "/api/teams/enhanced/meetings",
                "/api/teams/enhanced/meetings/create",
                "/api/teams/enhanced/files",
                "/api/teams/enhanced/files/upload",
                "/api/teams/enhanced/webhooks",
                "/api/teams/enhanced/sync",
                "/api/teams/enhanced/status"
            ]
        }
        
        if user_id:
            # Add user-specific status
            try:
                if TEAMS_AUTH_AVAILABLE:
                    tokens = asyncio.run(get_validated_tokens(user_id))
                    status_data["user_authenticated"] = tokens is not None
                else:
                    status_data["user_authenticated"] = False
            except:
                status_data["user_authenticated"] = False
        
        return jsonify(status_data)
        
    except Exception as e:
        logger.error(f"Error getting Teams service status: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Register blueprint with Flask app
def register_teams_enhanced_bp(app: Flask):
    """Register enhanced Teams blueprint with Flask app"""
    app.register_blueprint(teams_enhanced_bp)
    logger.info("Enhanced Teams API blueprint registered")

# Export components
__all__ = [
    'teams_enhanced_bp',
    'register_teams_enhanced_bp'
]