"""
🚀 Enhanced Zoom API Routes
Comprehensive REST API endpoints for Zoom integration
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from flask import Blueprint, request, jsonify

from zoom_api_manager import ZoomAPIManager
from zoom_data_synchronizer import ZoomDataSynchronizer

logger = logging.getLogger(__name__)

# Create blueprint
zoom_enhanced_bp = Blueprint("zoom_enhanced", __name__)

# Global API manager
api_manager: Optional[ZoomAPIManager] = None
synchronizer: Optional[ZoomDataSynchronizer] = None

def init_zoom_enhanced_service(db_pool):
    """Initialize enhanced Zoom service"""
    global api_manager, synchronizer
    
    try:
        api_manager = ZoomAPIManager(db_pool)
        synchronizer = api_manager.data_synchronizer
        
        # Initialize API manager
        asyncio.create_task(api_manager.initialize())
        
        # Start synchronization
        asyncio.create_task(synchronizer.start_sync())
        
        logger.info("Enhanced Zoom service initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize enhanced Zoom service: {e}")
        return False

def format_response(data: Any, endpoint: str, status: str = 'success') -> Dict[str, Any]:
    """Format API response"""
    return {
        'ok': status == 'success',
        'data': data,
        'endpoint': endpoint,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'source': 'zoom_enhanced_api'
    }

def format_error_response(error: str, endpoint: str, status_code: int = 500) -> tuple:
    """Format error response"""
    error_response = {
        'ok': False,
        'error': {
            'code': 'API_ERROR',
            'message': error,
            'endpoint': endpoint
        },
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'source': 'zoom_enhanced_api'
    }
    return jsonify(error_response), status_code

def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> tuple:
    """Validate required fields in request data"""
    missing_fields = [field for field in required_fields if field not in data or not data[field]]
    
    if missing_fields:
        error_msg = f"Missing required fields: {', '.join(missing_fields)}"
        return False, error_msg
    
    return True, None

def validate_user_id(request_data: Dict[str, Any]) -> tuple:
    """Validate user_id in request"""
    user_id = request_data.get('user_id')
    
    if not user_id:
        return False, "user_id is required"
    
    return True, user_id

# === HEALTH AND INFO ENDPOINTS ===

@zoom_enhanced_bp.route("/api/integrations/zoom/health", methods=["GET"])
async def health_check():
    """Enhanced Zoom API health check"""
    try:
        # Check API manager status
        if not api_manager:
            return jsonify({
                'status': 'error',
                'message': 'API manager not initialized',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }), 503
        
        # Check token availability
        active_tokens = await api_manager.token_manager.get_all_active_tokens()
        
        # Check synchronization status
        sync_stats = synchronizer.get_sync_stats()
        
        health_data = {
            'status': 'healthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'components': {
                'api_manager': {'status': 'available'},
                'token_manager': {'status': 'available'},
                'data_synchronizer': {
                    'status': 'active' if sync_stats['sync_active'] else 'inactive',
                    'last_sync': sync_stats['last_sync_time']
                },
                'database': {
                    'status': 'connected' if active_tokens else 'connected',
                    'active_tokens': len(active_tokens)
                }
            },
            'metrics': {
                'active_users': len(active_tokens),
                'sync_stats': sync_stats['stats'],
                'sync_duration_ms': sync_stats['stats'].get('last_sync_duration', 0) * 1000
            },
            'version': '2.0.0',
            'service': 'zoom_enhanced',
            'capabilities': [
                'meetings',
                'webinars',
                'recordings',
                'users',
                'chats',
                'reports',
                'oauth',
                'synchronization',
                'analytics'
            ]
        }
        
        return jsonify(health_data)
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 500

@zoom_enhanced_bp.route("/api/integrations/zoom/info", methods=["GET"])
async def service_info():
    """Get enhanced Zoom service information"""
    try:
        info_data = {
            'service': 'zoom_enhanced',
            'version': '2.0.0',
            'status': 'active',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'features': [
                'Enterprise-grade OAuth 2.0',
                'Real-time data synchronization',
                'Comprehensive meeting management',
                'Advanced recording capabilities',
                'Webinar support',
                'User management',
                'Chat integration',
                'Analytics and reporting',
                'Secure token storage',
                'Rate limiting and retry logic'
            ],
            'api_endpoints': [
                '/meetings/list',
                '/meetings/create',
                '/meetings/update',
                '/meetings/delete',
                '/meetings/info',
                '/recordings/list',
                '/recordings/delete',
                '/webinars/list',
                '/webinars/create',
                '/users/profile',
                '/users/list',
                '/chats/list',
                '/chats/messages',
                '/reports/generate',
                '/analytics/dashboard',
                '/oauth/authorize',
                '/oauth/callback'
            ],
            'authentication': 'OAuth 2.0',
            'rate_limiting': {
                'requests_per_second': 10,
                'burst_requests': 30,
                'retry_strategy': 'exponential_backoff'
            },
            'data_synchronization': {
                'interval_seconds': 300,
                'batch_size': 100,
                'max_retries': 3,
                'background_sync': True
            }
        }
        
        return format_response(info_data, '/info')
        
    except Exception as e:
        return format_error_response(str(e), '/info', 500)

# === OAUTH ENDPOINTS ===

@zoom_enhanced_bp.route("/api/integrations/zoom/oauth/authorize", methods=["POST"])
async def oauth_authorize():
    """Initiate OAuth flow"""
    try:
        request_data = request.get_json()
        is_valid, error = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(error, '/oauth/authorize', 400)
        
        user_id = request_data['user_id']
        
        # Generate OAuth URL
        oauth_url = await api_manager.generate_oauth_url(user_id)
        
        response_data = {
            'oauth_url': oauth_url,
            'user_id': user_id,
            'scopes': [
                'user:read:admin',
                'meeting:write:admin',
                'meeting:read:admin',
                'recording:write:admin',
                'recording:read:admin',
                'webinar:write:admin',
                'webinar:read:admin',
                'user:write:admin',
                'report:read:admin',
                'dashboard:read:admin'
            ]
        }
        
        return format_response(response_data, '/oauth/authorize')
        
    except Exception as e:
        return format_error_response(str(e), '/oauth/authorize', 500)

@zoom_enhanced_bp.route("/api/integrations/zoom/oauth/callback", methods=["POST"])
async def oauth_callback():
    """Handle OAuth callback"""
    try:
        request_data = request.get_json()
        
        is_valid, error = validate_required_fields(request_data, ['code', 'user_id'])
        if not is_valid:
            return format_error_response(error, '/oauth/callback', 400)
        
        code = request_data['code']
        user_id = request_data['user_id']
        
        # Exchange code for token
        token_result = await api_manager.exchange_code_for_token(code, user_id)
        
        return format_response(token_result, '/oauth/callback')
        
    except Exception as e:
        return format_error_response(str(e), '/oauth/callback', 500)

@zoom_enhanced_bp.route("/api/integrations/zoom/oauth/revoke", methods=["POST"])
async def oauth_revoke():
    """Revoke OAuth token"""
    try:
        request_data = request.get_json()
        is_valid, error = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(error, '/oauth/revoke', 400)
        
        user_id = request_data['user_id']
        
        # Revoke token
        success = await api_manager.revoke_token(user_id)
        
        response_data = {
            'success': success,
            'user_id': user_id,
            'message': 'Token revoked successfully' if success else 'Failed to revoke token'
        }
        
        return format_response(response_data, '/oauth/revoke')
        
    except Exception as e:
        return format_error_response(str(e), '/oauth/revoke', 500)

# === MEETINGS ENDPOINTS ===

@zoom_enhanced_bp.route("/api/integrations/zoom/meetings/list", methods=["POST"])
async def list_meetings():
    """List user meetings"""
    try:
        request_data = request.get_json()
        is_valid, user_id = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(user_id, '/meetings/list', 400)
        
        # Extract parameters
        meeting_type = request_data.get('type', 'scheduled')
        from_date = request_data.get('from_date')
        to_date = request_data.get('to_date')
        page_size = request_data.get('page_size', 100)
        
        # List meetings
        meetings = await api_manager.list_meetings(
            user_id, 
            meeting_type=meeting_type,
            from_date=from_date,
            to_date=to_date,
            page_size=page_size
        )
        
        response_data = {
            'meetings': meetings,
            'count': len(meetings),
            'filters': {
                'type': meeting_type,
                'from_date': from_date,
                'to_date': to_date,
                'page_size': page_size
            }
        }
        
        return format_response(response_data, '/meetings/list')
        
    except Exception as e:
        return format_error_response(str(e), '/meetings/list', 500)

@zoom_enhanced_bp.route("/api/integrations/zoom/meetings/create", methods=["POST"])
async def create_meeting():
    """Create a new meeting"""
    try:
        request_data = request.get_json()
        is_valid, user_id = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(user_id, '/meetings/create', 400)
        
        # Validate meeting data
        required_fields = ['topic', 'start_time']
        is_valid, error = validate_required_fields(request_data, required_fields)
        
        if not is_valid:
            return format_error_response(error, '/meetings/create', 400)
        
        meeting_data = request_data.get('meeting', {})
        
        # Create meeting request
        from zoom_api_manager import ZoomMeetingRequest
        
        meeting_request = ZoomMeetingRequest(
            topic=meeting_data['topic'],
            start_time=meeting_data['start_time'],
            duration=meeting_data.get('duration', 60),
            timezone=meeting_data.get('timezone', 'UTC'),
            agenda=meeting_data.get('agenda'),
            password=meeting_data.get('password'),
            settings=meeting_data.get('settings')
        )
        
        # Create meeting
        meeting = await api_manager.create_meeting(user_id, meeting_request)
        
        if meeting:
            response_data = {
                'meeting': meeting,
                'meeting_url': meeting.join_url,
                'meeting_id': meeting.id
            }
            
            return format_response(response_data, '/meetings/create')
        else:
            return format_error_response('Failed to create meeting', '/meetings/create', 500)
        
    except Exception as e:
        return format_error_response(str(e), '/meetings/create', 500)

@zoom_enhanced_bp.route("/api/integrations/zoom/meetings/update", methods=["POST"])
async def update_meeting():
    """Update existing meeting"""
    try:
        request_data = request.get_json()
        is_valid, user_id = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(user_id, '/meetings/update', 400)
        
        # Validate required fields
        required_fields = ['meeting_id']
        is_valid, error = validate_required_fields(request_data, required_fields)
        
        if not is_valid:
            return format_error_response(error, '/meetings/update', 400)
        
        meeting_id = request_data['meeting_id']
        meeting_updates = request_data.get('updates', {})
        
        # Update meeting
        from zoom_api_manager import ZoomMeetingUpdate
        
        update_request = ZoomMeetingUpdate(**meeting_updates)
        result = await api_manager.update_meeting(user_id, meeting_id, update_request)
        
        if result:
            response_data = {
                'meeting_id': meeting_id,
                'updates_applied': meeting_updates,
                'updated_meeting': result
            }
            
            return format_response(response_data, '/meetings/update')
        else:
            return format_error_response('Failed to update meeting', '/meetings/update', 500)
        
    except Exception as e:
        return format_error_response(str(e), '/meetings/update', 500)

@zoom_enhanced_bp.route("/api/integrations/zoom/meetings/delete", methods=["POST"])
async def delete_meeting():
    """Delete a meeting"""
    try:
        request_data = request.get_json()
        is_valid, user_id = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(user_id, '/meetings/delete', 400)
        
        # Validate required fields
        required_fields = ['meeting_id']
        is_valid, error = validate_required_fields(request_data, required_fields)
        
        if not is_valid:
            return format_error_response(error, '/meetings/delete', 400)
        
        meeting_id = request_data['meeting_id']
        
        # Delete meeting
        success = await api_manager.delete_meeting(user_id, meeting_id)
        
        response_data = {
            'meeting_id': meeting_id,
            'deleted': success,
            'message': 'Meeting deleted successfully' if success else 'Failed to delete meeting'
        }
        
        return format_response(response_data, '/meetings/delete')
        
    except Exception as e:
        return format_error_response(str(e), '/meetings/delete', 500)

@zoom_enhanced_bp.route("/api/integrations/zoom/meetings/info", methods=["POST"])
async def get_meeting_info():
    """Get meeting information"""
    try:
        request_data = request.get_json()
        is_valid, user_id = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(user_id, '/meetings/info', 400)
        
        # Validate required fields
        required_fields = ['meeting_id']
        is_valid, error = validate_required_fields(request_data, required_fields)
        
        if not is_valid:
            return format_error_response(error, '/meetings/info', 400)
        
        meeting_id = request_data['meeting_id']
        
        # Get meeting info
        meeting_info = await api_manager.get_meeting(user_id, meeting_id)
        
        if meeting_info:
            response_data = {
                'meeting': meeting_info,
                'meeting_id': meeting_id
            }
            
            return format_response(response_data, '/meetings/info')
        else:
            return format_error_response('Meeting not found', '/meetings/info', 404)
        
    except Exception as e:
        return format_error_response(str(e), '/meetings/info', 500)

@zoom_enhanced_bp.route("/api/integrations/zoom/meetings/participants", methods=["POST"])
async def get_meeting_participants():
    """Get meeting participants"""
    try:
        request_data = request.get_json()
        is_valid, user_id = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(user_id, '/meetings/participants', 400)
        
        # Validate required fields
        required_fields = ['meeting_id']
        is_valid, error = validate_required_fields(request_data, required_fields)
        
        if not is_valid:
            return format_error_response(error, '/meetings/participants', 400)
        
        meeting_id = request_data['meeting_id']
        
        # Get participants
        participants = await api_manager.get_meeting_participants(user_id, meeting_id)
        
        response_data = {
            'meeting_id': meeting_id,
            'participants': participants,
            'count': len(participants)
        }
        
        return format_response(response_data, '/meetings/participants')
        
    except Exception as e:
        return format_error_response(str(e), '/meetings/participants', 500)

# === RECORDINGS ENDPOINTS ===

@zoom_enhanced_bp.route("/api/integrations/zoom/recordings/list", methods=["POST"])
async def list_recordings():
    """List user recordings"""
    try:
        request_data = request.get_json()
        is_valid, user_id = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(user_id, '/recordings/list', 400)
        
        # Extract parameters
        from_date = request_data.get('from_date')
        to_date = request_data.get('to_date')
        meeting_id = request_data.get('meeting_id')
        page_size = request_data.get('page_size', 100)
        
        # Get recordings
        recordings = await api_manager.get_recordings(
            user_id,
            from_date=from_date,
            to_date=to_date,
            meeting_id=meeting_id,
            page_size=page_size
        )
        
        response_data = {
            'recordings': recordings,
            'count': len(recordings),
            'filters': {
                'from_date': from_date,
                'to_date': to_date,
                'meeting_id': meeting_id,
                'page_size': page_size
            }
        }
        
        return format_response(response_data, '/recordings/list')
        
    except Exception as e:
        return format_error_response(str(e), '/recordings/list', 500)

@zoom_enhanced_bp.route("/api/integrations/zoom/recordings/delete", methods=["POST"])
async def delete_recording():
    """Delete a recording"""
    try:
        request_data = request.get_json()
        is_valid, user_id = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(user_id, '/recordings/delete', 400)
        
        # Validate required fields
        required_fields = ['meeting_id', 'recording_id']
        is_valid, error = validate_required_fields(request_data, required_fields)
        
        if not is_valid:
            return format_error_response(error, '/recordings/delete', 400)
        
        meeting_id = request_data['meeting_id']
        recording_id = request_data['recording_id']
        
        # Delete recording
        success = await api_manager.delete_recording(user_id, meeting_id, recording_id)
        
        response_data = {
            'meeting_id': meeting_id,
            'recording_id': recording_id,
            'deleted': success,
            'message': 'Recording deleted successfully' if success else 'Failed to delete recording'
        }
        
        return format_response(response_data, '/recordings/delete')
        
    except Exception as e:
        return format_error_response(str(e), '/recordings/delete', 500)

# === USERS ENDPOINTS ===

@zoom_enhanced_bp.route("/api/integrations/zoom/users/profile", methods=["POST"])
async def get_user_profile():
    """Get user profile"""
    try:
        request_data = request.get_json()
        is_valid, user_id = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(user_id, '/users/profile', 400)
        
        target_user_id = request_data.get('target_user_id')
        
        # Get user info
        user_info = await api_manager.get_user_info(user_id, target_user_id)
        
        if user_info:
            response_data = {
                'user': user_info,
                'user_id': target_user_id or user_id
            }
            
            return format_response(response_data, '/users/profile')
        else:
            return format_error_response('User not found', '/users/profile', 404)
        
    except Exception as e:
        return format_error_response(str(e), '/users/profile', 500)

@zoom_enhanced_bp.route("/api/integrations/zoom/users/list", methods=["POST"])
async def list_users():
    """List users (requires admin permissions)"""
    try:
        request_data = request.get_json()
        is_valid, user_id = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(user_id, '/users/list', 400)
        
        # Extract parameters
        page_size = request_data.get('page_size', 100)
        status = request_data.get('status')
        role_id = request_data.get('role_id')
        
        # List users
        users = await api_manager.list_users(
            user_id,
            page_size=page_size,
            status=status,
            role_id=role_id
        )
        
        response_data = {
            'users': users,
            'count': len(users),
            'filters': {
                'page_size': page_size,
                'status': status,
                'role_id': role_id
            }
        }
        
        return format_response(response_data, '/users/list')
        
    except Exception as e:
        return format_error_response(str(e), '/users/list', 500)

@zoom_enhanced_bp.route("/api/integrations/zoom/users/update", methods=["POST"])
async def update_user_profile():
    """Update user profile"""
    try:
        request_data = request.get_json()
        is_valid, user_id = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(user_id, '/users/update', 400)
        
        updates = request_data.get('updates', {})
        
        if not updates:
            return format_error_response('No updates provided', '/users/update', 400)
        
        # Update user info
        result = await api_manager.update_user_info(user_id, updates)
        
        if result:
            response_data = {
                'user_id': user_id,
                'updates_applied': updates,
                'updated_user': result
            }
            
            return format_response(response_data, '/users/update')
        else:
            return format_error_response('Failed to update user', '/users/update', 500)
        
    except Exception as e:
        return format_error_response(str(e), '/users/update', 500)

# === WEBINARS ENDPOINTS ===

@zoom_enhanced_bp.route("/api/integrations/zoom/webinars/list", methods=["POST"])
async def list_webinars():
    """List user webinars"""
    try:
        request_data = request.get_json()
        is_valid, user_id = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(user_id, '/webinars/list', 400)
        
        # Extract parameters
        webinar_type = request_data.get('type', 'scheduled')
        from_date = request_data.get('from_date')
        to_date = request_data.get('to_date')
        page_size = request_data.get('page_size', 100)
        
        # List webinars
        webinars = await api_manager.list_webinars(
            user_id,
            webinar_type=webinar_type,
            from_date=from_date,
            to_date=to_date,
            page_size=page_size
        )
        
        response_data = {
            'webinars': webinars,
            'count': len(webinars),
            'filters': {
                'type': webinar_type,
                'from_date': from_date,
                'to_date': to_date,
                'page_size': page_size
            }
        }
        
        return format_response(response_data, '/webinars/list')
        
    except Exception as e:
        return format_error_response(str(e), '/webinars/list', 500)

@zoom_enhanced_bp.route("/api/integrations/zoom/webinars/create", methods=["POST"])
async def create_webinar():
    """Create a new webinar"""
    try:
        request_data = request.get_json()
        is_valid, user_id = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(user_id, '/webinars/create', 400)
        
        # Validate webinar data
        required_fields = ['topic', 'start_time']
        is_valid, error = validate_required_fields(request_data, required_fields)
        
        if not is_valid:
            return format_error_response(error, '/webinars/create', 400)
        
        webinar_data = request_data.get('webinar', {})
        
        # Create webinar request
        from zoom_api_manager import ZoomWebinarRequest
        
        webinar_request = ZoomWebinarRequest(
            topic=webinar_data['topic'],
            start_time=webinar_data['start_time'],
            duration=webinar_data.get('duration', 60),
            timezone=webinar_data.get('timezone', 'UTC'),
            agenda=webinar_data.get('agenda'),
            password=webinar_data.get('password'),
            settings=webinar_data.get('settings')
        )
        
        # Create webinar
        webinar = await api_manager.create_webinar(user_id, webinar_request)
        
        if webinar:
            response_data = {
                'webinar': webinar,
                'webinar_url': webinar.get('join_url'),
                'webinar_id': webinar.get('id')
            }
            
            return format_response(response_data, '/webinars/create')
        else:
            return format_error_response('Failed to create webinar', '/webinars/create', 500)
        
    except Exception as e:
        return format_error_response(str(e), '/webinars/create', 500)

# === CHAT ENDPOINTS ===

@zoom_enhanced_bp.route("/api/integrations/zoom/chats/list", methods=["POST"])
async def list_chat_channels():
    """List chat channels"""
    try:
        request_data = request.get_json()
        is_valid, user_id = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(user_id, '/chats/list', 400)
        
        page_size = request_data.get('page_size', 100)
        
        # Get chat channels
        channels = await api_manager.get_chat_channels(user_id, page_size)
        
        response_data = {
            'channels': channels,
            'count': len(channels),
            'page_size': page_size
        }
        
        return format_response(response_data, '/chats/list')
        
    except Exception as e:
        return format_error_response(str(e), '/chats/list', 500)

@zoom_enhanced_bp.route("/api/integrations/zoom/chats/messages", methods=["POST"])
async def get_chat_messages():
    """Get chat messages"""
    try:
        request_data = request.get_json()
        is_valid, user_id = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(user_id, '/chats/messages', 400)
        
        # Validate required fields
        required_fields = ['channel_id']
        is_valid, error = validate_required_fields(request_data, required_fields)
        
        if not is_valid:
            return format_error_response(error, '/chats/messages', 400)
        
        channel_id = request_data['channel_id']
        from_date = request_data.get('from_date')
        to_date = request_data.get('to_date')
        page_size = request_data.get('page_size', 100)
        
        # Get messages
        messages = await api_manager.get_chat_messages(
            user_id,
            channel_id,
            from_date=from_date,
            to_date=to_date,
            page_size=page_size
        )
        
        response_data = {
            'channel_id': channel_id,
            'messages': messages,
            'count': len(messages),
            'filters': {
                'from_date': from_date,
                'to_date': to_date,
                'page_size': page_size
            }
        }
        
        return format_response(response_data, '/chats/messages')
        
    except Exception as e:
        return format_error_response(str(e), '/chats/messages', 500)

# === REPORTS ENDPOINTS ===

@zoom_enhanced_bp.route("/api/integrations/zoom/reports/meetings", methods=["POST"])
async def get_meeting_reports():
    """Get meeting reports"""
    try:
        request_data = request.get_json()
        is_valid, user_id = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(user_id, '/reports/meetings', 400)
        
        # Validate required fields
        required_fields = ['meeting_id']
        is_valid, error = validate_required_fields(request_data, required_fields)
        
        if not is_valid:
            return format_error_response(error, '/reports/meetings', 400)
        
        meeting_id = request_data['meeting_id']
        report_type = request_data.get('type', 'participants')
        
        # Get meeting report
        report = await api_manager.get_meeting_report(user_id, meeting_id, report_type)
        
        if report:
            response_data = {
                'meeting_id': meeting_id,
                'report_type': report_type,
                'report': report
            }
            
            return format_response(response_data, '/reports/meetings')
        else:
            return format_error_response('Report not found', '/reports/meetings', 404)
        
    except Exception as e:
        return format_error_response(str(e), '/reports/meetings', 500)

@zoom_enhanced_bp.route("/api/integrations/zoom/reports/generate", methods=["POST"])
async def generate_report():
    """Generate custom report"""
    try:
        request_data = request.get_json()
        is_valid, user_id = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(user_id, '/reports/generate', 400)
        
        # Validate required fields
        required_fields = ['report_type', 'from_date', 'to_date']
        is_valid, error = validate_required_fields(request_data, required_fields)
        
        if not is_valid:
            return format_error_response(error, '/reports/generate', 400)
        
        from zoom_api_manager import ZoomReportRequest
        
        report_request = ZoomReportRequest(
            report_type=request_data['report_type'],
            from_date=request_data['from_date'],
            to_date=request_data['to_date'],
            user_ids=request_data.get('user_ids'),
            meeting_ids=request_data.get('meeting_ids'),
            settings=request_data.get('settings')
        )
        
        # Generate report
        report = await api_manager.get_user_report(user_id, report_request)
        
        if report:
            response_data = {
                'report_type': report_request.report_type,
                'date_range': {
                    'from': report_request.from_date,
                    'to': report_request.to_date
                },
                'report': report
            }
            
            return format_response(response_data, '/reports/generate')
        else:
            return format_error_response('Failed to generate report', '/reports/generate', 500)
        
    except Exception as e:
        return format_error_response(str(e), '/reports/generate', 500)

# === ANALYTICS ENDPOINTS ===

@zoom_enhanced_bp.route("/api/integrations/zoom/analytics/dashboard", methods=["POST"])
async def get_analytics_dashboard():
    """Get analytics dashboard data"""
    try:
        request_data = request.get_json()
        is_valid, user_id = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(user_id, '/analytics/dashboard', 400)
        
        # Get dashboard data
        dashboard = await api_manager.get_user_dashboard(user_id)
        
        if dashboard:
            response_data = {
                'dashboard': dashboard,
                'user_id': user_id
            }
            
            return format_response(response_data, '/analytics/dashboard')
        else:
            return format_error_response('Dashboard not available', '/analytics/dashboard', 404)
        
    except Exception as e:
        return format_error_response(str(e), '/analytics/dashboard', 500)

@zoom_enhanced_bp.route("/api/integrations/zoom/analytics/meeting", methods=["POST"])
async def get_meeting_analytics():
    """Get meeting analytics"""
    try:
        request_data = request.get_json()
        is_valid, user_id = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(user_id, '/analytics/meeting', 400)
        
        # Validate required fields
        required_fields = ['meeting_id']
        is_valid, error = validate_required_fields(request_data, required_fields)
        
        if not is_valid:
            return format_error_response(error, '/analytics/meeting', 400)
        
        meeting_id = request_data['meeting_id']
        
        # Get meeting analytics
        analytics = await api_manager.get_meeting_analytics(user_id, meeting_id)
        
        if analytics:
            response_data = {
                'meeting_id': meeting_id,
                'analytics': analytics
            }
            
            return format_response(response_data, '/analytics/meeting')
        else:
            return format_error_response('Analytics not available', '/analytics/meeting', 404)
        
    except Exception as e:
        return format_error_response(str(e), '/analytics/meeting', 500)

# === SYNCHRONIZATION ENDPOINTS ===

@zoom_enhanced_bp.route("/api/integrations/zoom/sync/status", methods=["POST"])
async def get_sync_status():
    """Get synchronization status"""
    try:
        request_data = request.get_json()
        is_valid, user_id = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(user_id, '/sync/status', 400)
        
        # Get sync status
        sync_stats = synchronizer.get_sync_stats()
        
        response_data = {
            'sync_status': sync_stats,
            'user_id': user_id
        }
        
        return format_response(response_data, '/sync/status')
        
    except Exception as e:
        return format_error_response(str(e), '/sync/status', 500)

@zoom_enhanced_bp.route("/api/integrations/zoom/sync/force", methods=["POST"])
async def force_sync():
    """Force immediate synchronization"""
    try:
        request_data = request.get_json()
        is_valid, user_id = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(user_id, '/sync/force', 400)
        
        sync_all = request_data.get('sync_all', False)
        
        # Force sync
        if sync_all:
            await synchronizer.force_sync()
        else:
            await synchronizer.force_sync(user_id)
        
        response_data = {
            'sync_initiated': True,
            'sync_all': sync_all,
            'user_id': user_id if not sync_all else 'all_users',
            'message': 'Synchronization started successfully'
        }
        
        return format_response(response_data, '/sync/force')
        
    except Exception as e:
        return format_error_response(str(e), '/sync/force', 500)

@zoom_enhanced_bp.route("/api/integrations/zoom/sync/start", methods=["POST"])
async def start_sync():
    """Start background synchronization"""
    try:
        await synchronizer.start_sync()
        
        response_data = {
            'sync_started': True,
            'message': 'Background synchronization started'
        }
        
        return format_response(response_data, '/sync/start')
        
    except Exception as e:
        return format_error_response(str(e), '/sync/start', 500)

@zoom_enhanced_bp.route("/api/integrations/zoom/sync/stop", methods=["POST"])
async def stop_sync():
    """Stop background synchronization"""
    try:
        await synchronizer.stop_sync()
        
        response_data = {
            'sync_stopped': True,
            'message': 'Background synchronization stopped'
        }
        
        return format_response(response_data, '/sync/stop')
        
    except Exception as e:
        return format_error_response(str(e), '/sync/stop', 500)

# === UTILITY ENDPOINTS ===

@zoom_enhanced_bp.route("/api/integrations/zoom/usage", methods=["POST"])
async def get_api_usage():
    """Get API usage statistics"""
    try:
        request_data = request.get_json()
        is_valid, user_id = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(user_id, '/usage', 400)
        
        # Get API usage
        usage = await api_manager.get_api_usage(user_id)
        
        if usage:
            response_data = {
                'usage': usage,
                'user_id': user_id
            }
            
            return format_response(response_data, '/usage')
        else:
            return format_error_response('Usage data not available', '/usage', 404)
        
    except Exception as e:
        return format_error_response(str(e), '/usage', 500)

@zoom_enhanced_bp.route("/api/integrations/zoom/validate", methods=["POST"])
async def validate_token():
    """Validate access token"""
    try:
        request_data = request.get_json()
        is_valid, user_id = validate_user_id(request_data)
        
        if not is_valid:
            return format_error_response(user_id, '/validate', 400)
        
        # Validate token
        is_valid_token = await api_manager.validate_access_token(user_id)
        
        response_data = {
            'token_valid': is_valid_token,
            'user_id': user_id,
            'message': 'Token is valid' if is_valid_token else 'Token is invalid or expired'
        }
        
        return format_response(response_data, '/validate')
        
    except Exception as e:
        return format_error_response(str(e), '/validate', 500)

# === ERROR HANDLING ===

@zoom_enhanced_bp.errorhandler(400)
def bad_request(error):
    """Handle 400 Bad Request"""
    return format_error_response('Bad Request', 'global', 400)

@zoom_enhanced_bp.errorhandler(401)
def unauthorized(error):
    """Handle 401 Unauthorized"""
    return format_error_response('Unauthorized', 'global', 401)

@zoom_enhanced_bp.errorhandler(403)
def forbidden(error):
    """Handle 403 Forbidden"""
    return format_error_response('Forbidden', 'global', 403)

@zoom_enhanced_bp.errorhandler(404)
def not_found(error):
    """Handle 404 Not Found"""
    return format_error_response('Not Found', 'global', 404)

@zoom_enhanced_bp.errorhandler(429)
def rate_limited(error):
    """Handle 429 Too Many Requests"""
    return format_error_response('Rate Limit Exceeded', 'global', 429)

@zoom_enhanced_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 Internal Server Error"""
    logger.error(f"Internal server error: {error}")
    return format_error_response('Internal Server Error', 'global', 500)

# === BLUEPRINT CLEANUP ===

async def cleanup_zoom_enhanced():
    """Cleanup Zoom enhanced service"""
    global api_manager, synchronizer
    
    try:
        if api_manager:
            await api_manager.close()
        
        logger.info("Enhanced Zoom service cleaned up successfully")
        
    except Exception as e:
        logger.error(f"Failed to cleanup enhanced Zoom service: {e}")

# Register cleanup function
import atexit
atexit.register(lambda: asyncio.create_task(cleanup_zoom_enhanced()))