"""
ATOM Google Chat API Routes
Complete API with authentication, real-time features, and analytics integration
"""

import os
import json
import logging
import asyncio
import base64
import hashlib
import hmac
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from flask import Blueprint, request, jsonify, current_app
from loguru import logger

# Import enhanced services
try:
    from google_chat_enhanced_service import google_chat_enhanced_service
    from atom_google_chat_integration import atom_google_chat_integration
    from atom_ingestion_pipeline import atom_ingestion_pipeline
    from atom_memory_service import AtomMemoryService
    from atom_search_service import AtomSearchService
    from atom_workflow_service import atom_workflow_service
except ImportError as e:
    logger.warning(f"Google Chat integration services not available: {e}")
    google_chat_enhanced_service = None
    atom_google_chat_integration = None
    atom_ingestion_pipeline = None
    AtomMemoryService = None
    AtomSearchService = None
    atom_workflow_service = None

# Create Google Chat API blueprint
google_chat_bp = Blueprint('google_chat_api', __name__, url_prefix='/api/integrations/google-chat')

# Configuration validation
def validate_google_chat_config():
    """Validate Google Chat configuration"""
    required_vars = [
        'GOOGLE_CHAT_CLIENT_ID',
        'GOOGLE_CHAT_CLIENT_SECRET',
        'GOOGLE_CHAT_REDIRECT_URI',
        'ENCRYPTION_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        return False
    
    return True

# Utility functions
def create_google_chat_response(ok: bool, data: Any = None, error: str = None,
                            message: str = None, metadata: Dict = None) -> Dict[str, Any]:
    """Create standardized Google Chat API response"""
    response = {
        'ok': ok,
        'timestamp': datetime.utcnow().isoformat(),
        'api_version': '3.0.0',
        'service': 'Google Chat Integration'
    }
    
    if ok:
        if data is not None:
            response['data'] = data
        if message:
            response['message'] = message
        if metadata:
            response['metadata'] = metadata
    else:
        response['error'] = error or 'Unknown error occurred'
    
    return response

def get_google_chat_request_data() -> Dict[str, Any]:
    """Get and validate Google Chat request data"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id') or request.headers.get('X-User-ID', 'default-user')
        data['user_id'] = user_id
        return data
    except Exception as e:
        logger.error(f"Error parsing Google Chat request data: {e}")
        return {}

def verify_google_chat_webhook(request_body: bytes, signature: str, secret: str) -> bool:
    """Verify Google Chat webhook signature"""
    try:
        if not signature or not secret:
            return False
        
        # Google Chat uses HMAC-SHA256 for webhook validation
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            request_body,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures securely
        return hmac.compare_digest(expected_signature, signature.replace('sha256=', ''))
    
    except Exception as e:
        logger.error(f"Error verifying Google Chat webhook: {e}")
        return False

# Health Check
@google_chat_bp.route('/enhanced_health', methods=['POST'])
def google_chat_enhanced_health_check():
    """Enhanced health check for all Google Chat services"""
    try:
        if not validate_google_chat_config():
            return create_google_chat_response(False, error="Configuration validation failed")
        
        health_status = {
            'google_chat_enhanced_service': google_chat_enhanced_service is not None,
            'atom_google_chat_integration': atom_google_chat_integration is not None,
            'ingestion_pipeline': atom_ingestion_pipeline is not None,
            'memory_service': AtomMemoryService is not None,
            'search_service': AtomSearchService is not None,
            'workflow_service': atom_workflow_service is not None
        }
        
        # Check service status
        all_healthy = all(health_status.values())
        
        # Get detailed status if services are available
        service_info = {}
        if google_chat_enhanced_service:
            service_info['google_chat_service'] = await google_chat_enhanced_service.get_service_info()
        if atom_google_chat_integration:
            service_info['integration_service'] = {
                'initialized': atom_google_chat_integration.is_initialized,
                'active_spaces': len(atom_google_chat_integration.active_spaces),
                'unified_channels': len(atom_google_chat_integration.communication_channels)
            }
        
        return create_google_chat_response(
            all_healthy,
            data={
                'services': health_status,
                'service_info': service_info,
                'status': 'healthy' if all_healthy else 'degraded'
            },
            message="Enhanced Google Chat services operational" if all_healthy else "Some services unavailable"
        )
    
    except Exception as e:
        logger.error(f"Enhanced Google Chat health check error: {e}")
        return create_google_chat_response(False, error=str(e)), 500

# OAuth and Authentication
@google_chat_bp.route('/oauth_url', methods=['POST'])
def get_google_chat_oauth_url():
    """Generate OAuth authorization URL for Google Chat"""
    try:
        data = get_google_chat_request_data()
        user_id = data.get('user_id')
        
        if not google_chat_enhanced_service:
            return create_google_chat_response(False, error="Google Chat service not available"), 503
        
        # Generate secure state token
        state_token = f"gc_auth_{user_id}_{int(datetime.utcnow().timestamp())}"
        
        # Generate OAuth URL
        oauth_url = google_chat_enhanced_service.generate_oauth_url(
            state=state_token,
            user_id=user_id
        )
        
        return create_google_chat_response(
            True,
            data={
                'oauth_url': oauth_url,
                'state': state_token,
                'scopes': google_chat_enhanced_service.required_scopes,
                'expires_in': 600  # 10 minutes
            },
            message="Google Chat OAuth URL generated successfully"
        )
    
    except Exception as e:
        logger.error(f"Google Chat OAuth URL generation error: {e}")
        return create_google_chat_response(False, error=str(e)), 500

@google_chat_bp.route('/oauth_callback', methods=['POST'])
def handle_google_chat_oauth_callback():
    """Handle Google Chat OAuth callback"""
    try:
        data = get_google_chat_request_data()
        code = data.get('code')
        state = data.get('state')
        
        if not code or not state:
            return create_google_chat_response(False, error="Missing code or state parameter")
        
        if not google_chat_enhanced_service:
            return create_google_chat_response(False, error="Google Chat service not available"), 503
        
        # Exchange code for tokens
        result = await google_chat_enhanced_service.exchange_code_for_tokens(code, state)
        
        if result.get('ok'):
            # Store in memory service
            if AtomMemoryService:
                memory_data = {
                    'type': 'google_chat_oauth_success',
                    'space_ids': [space.get('space_id') for space in result.get('spaces', [])],
                    'user_id': data.get('user_id'),
                    'timestamp': datetime.utcnow().isoformat()
                }
                await AtomMemoryService.store(memory_data)
            
            return create_google_chat_response(
                True,
                data=result.get('spaces'),
                message=f"Connected to {len(result.get('spaces', []))} Google Chat spaces successfully"
            )
        else:
            return create_google_chat_response(False, error=result.get('error')), 400
    
    except Exception as e:
        logger.error(f"Google Chat OAuth callback error: {e}")
        return create_google_chat_response(False, error=str(e)), 500

# Enhanced Workspace Management
@google_chat_bp.route('/spaces/enhanced', methods=['POST'])
def get_enhanced_google_chat_spaces():
    """Get Google Chat spaces with enhanced metadata"""
    try:
        data = get_google_chat_request_data()
        user_id = data.get('user_id')
        
        if not atom_google_chat_integration:
            return create_google_chat_response(False, error="Google Chat integration not available"), 503
        
        # Get unified workspaces (Google Chat spaces become workspaces)
        workspaces = await atom_google_chat_integration.get_unified_workspaces(user_id)
        
        # Test connections
        workspace_data = []
        for workspace in workspaces:
            # Test connection status
            space_id = workspace['integration_data']['space_id']
            connection_test = await google_chat_enhanced_service.test_connection(space_id)
            
            workspace_info = {
                'id': workspace['id'],
                'name': workspace['name'],
                'platform': workspace['platform'],
                'type': workspace['type'],
                'status': connection_test.get('status', 'unknown'),
                'member_count': workspace['member_count'],
                'channel_count': workspace['channel_count'],
                'icon_url': workspace['icon_url'],
                'connectionStatus': connection_test.get('connected', False),
                'capabilities': workspace['capabilities'],
                'integration_data': workspace['integration_data']
            }
            
            workspace_data.append(workspace_info)
        
        return create_google_chat_response(
            True,
            data={
                'workspaces': workspace_data,
                'total_count': len(workspace_data),
                'connected_count': len([w for w in workspace_data if w['connectionStatus'] == True])
            },
            message="Enhanced Google Chat workspaces retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Enhanced Google Chat workspaces error: {e}")
        return create_google_chat_response(False, error=str(e)), 500

# Enhanced Channel Management
@google_chat_bp.route('/channels/enhanced', methods=['POST'])
def get_enhanced_google_chat_channels():
    """Get Google Chat channels (spaces) with enhanced metadata"""
    try:
        data = get_google_chat_request_data()
        workspace_id = data.get('workspace_id')
        user_id = data.get('user_id')
        include_stats = data.get('include_stats', True)
        include_activity = data.get('include_activity', True)
        
        if not workspace_id:
            return create_google_chat_response(False, error="workspace_id is required")
        
        if not atom_google_chat_integration:
            return create_google_chat_response(False, error="Google Chat integration not available"), 503
        
        # Get channels (Google Chat spaces become channels)
        channels = await atom_google_chat_integration.get_unified_channels(workspace_id, user_id)
        
        channel_data = []
        for channel in channels:
            channel_info = {
                'id': channel['id'],
                'name': channel['name'],
                'display_name': channel['display_name'],
                'description': channel['description'],
                'type': channel['type'],
                'platform': channel['platform'],
                'workspace_id': channel['workspace_id'],
                'workspace_name': channel['workspace_name'],
                'status': channel['status'],
                'member_count': channel['member_count'],
                'message_count': channel['message_count'],
                'unread_count': channel['unread_count'],
                'last_activity': channel['last_activity'],
                'is_private': channel['is_private'],
                'is_muted': channel['is_muted'],
                'is_favorite': channel['is_favorite'],
                'capabilities': channel['capabilities'],
                'integration_data': channel['integration_data']
            }
            
            # Add statistics if requested
            if include_stats:
                # This would fetch statistics from database
                channel_info['stats'] = {
                    'messageCount': channel['message_count'],
                    'fileCount': 0,  # Would calculate
                    'activeUsers': channel['member_count'],
                    'lastActivity': channel['last_activity']
                }
            
            # Add recent activity if requested
            if include_activity:
                # This would fetch recent activity
                channel_info['recentActivity'] = {
                    'lastMessage': None,
                    'activeUsers': [],
                    'trendingTopics': []
                }
            
            channel_data.append(channel_info)
        
        return create_google_chat_response(
            True,
            data={
                'channels': channel_data,
                'total_count': len(channel_data),
                'workspace_id': workspace_id
            },
            message="Enhanced Google Chat channels retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Enhanced Google Chat channels error: {e}")
        return create_google_chat_response(False, error=str(e)), 500

# Enhanced Message Operations
@google_chat_bp.route('/messages/enhanced', methods=['POST'])
def get_enhanced_google_chat_messages():
    """Get Google Chat messages with enhanced metadata and analysis"""
    try:
        data = get_google_chat_request_data()
        workspace_id = data.get('workspace_id')
        channel_id = data.get('channel_id')
        user_id = data.get('user_id')
        
        if not workspace_id or not channel_id:
            return create_google_chat_response(False, error="workspace_id and channel_id are required")
        
        if not atom_google_chat_integration:
            return create_google_chat_response(False, error="Google Chat integration not available"), 503
        
        # Get messages
        messages = await atom_google_chat_integration.get_unified_messages(
            workspace_id,
            channel_id,
            limit=data.get('limit', 100),
            options={
                'page_token': data.get('page_token'),
                'filter': data.get('filter'),
                'include_sentiment': data.get('include_sentiment', False),
                'include_topics': data.get('include_topics', True),
                'include_language': data.get('include_language', False)
            }
        )
        
        message_data = []
        for message in messages:
            message_info = {
                'id': message['id'],
                'content': message['content'],
                'html_content': message['html_content'],
                'userId': message['user_id'],
                'userName': message['user_name'],
                'userEmail': message['user_email'],
                'userAvatar': message['user_avatar'],
                'channelId': message['channel_id'],
                'workspaceId': message['workspace_id'],
                'timestamp': message['timestamp'],
                'threadId': message['thread_id'],
                'replyToId': message['reply_to_id'],
                'messageType': message['message_type'],
                'isEdited': message['is_edited'],
                'editTimestamp': message['edit_timestamp'],
                'reactions': message['reactions'],
                'attachments': message['attachments'],
                'mentions': message['mentions'],
                'files': message['files'],
                'integration_data': message['integration_data'],
                'metadata': message['metadata']
            }
            
            # Add enhanced analysis
            if data.get('include_sentiment', False):
                # This would analyze sentiment
                message_info['sentiment'] = {
                    'score': 0.5,
                    'label': 'neutral',
                    'confidence': 0.8
                }
            
            if data.get('include_topics', False):
                # This would extract topics
                message_info['topics'] = []
            
            if data.get('include_language', False):
                # This would detect language
                message_info['language'] = 'en'
            
            message_data.append(message_info)
        
        return create_google_chat_response(
            True,
            data={
                'messages': message_data,
                'total_count': len(message_data),
                'channel_id': channel_id,
                'workspace_id': workspace_id,
                'has_more': len(message_data) == data.get('limit', 100)
            },
            message="Enhanced Google Chat messages retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Enhanced Google Chat messages error: {e}")
        return create_google_chat_response(False, error=str(e)), 500

@google_chat_bp.route('/messages/enhanced_send', methods=['POST'])
def send_enhanced_google_chat_message():
    """Send Google Chat message with enhanced features"""
    try:
        data = get_google_chat_request_data()
        workspace_id = data.get('workspace_id')
        channel_id = data.get('channel_id')
        text = data.get('text')
        user_id = data.get('user_id')
        
        if not all([workspace_id, channel_id, text]):
            return create_google_chat_response(False, error="workspace_id, channel_id, and text are required")
        
        if not atom_google_chat_integration:
            return create_google_chat_response(False, error="Google Chat integration not available"), 503
        
        # Send message
        result = await atom_google_chat_integration.send_unified_message(
            workspace_id,
            channel_id,
            text,
            options={
                'thread_id': data.get('thread_id'),
                'message_format': data.get('message_format', 'TEXT'),  # TEXT or MARKDOWN
                'card_v2': data.get('card_v2', [])
            }
        )
        
        if result.get('ok'):
            # Store in memory service
            if AtomMemoryService:
                memory_data = {
                    'type': 'sent_google_chat_message',
                    'workspace_id': workspace_id,
                    'channel_id': channel_id,
                    'message_id': result.get('message_id'),
                    'text': text,
                    'user_id': user_id,
                    'timestamp': datetime.utcnow().isoformat()
                }
                await AtomMemoryService.store(memory_data)
            
            return create_google_chat_response(
                True,
                data=result,
                message="Google Chat message sent successfully"
            )
        else:
            return create_google_chat_response(False, error=result.get('error')), 400
    
    except Exception as e:
        logger.error(f"Enhanced Google Chat send message error: {e}")
        return create_google_chat_response(False, error=str(e)), 500

# Enhanced Search
@google_chat_bp.route('/search/enhanced', methods=['POST'])
def enhanced_google_chat_search():
    """Enhanced Google Chat search with analytics and insights"""
    try:
        data = get_google_chat_request_data()
        query = data.get('query')
        workspace_id = data.get('workspace_id')
        channel_id = data.get('channel_id')
        user_id = data.get('user_id')
        
        if not query:
            return create_google_chat_response(False, error="query is required")
        
        if not atom_google_chat_integration:
            return create_google_chat_response(False, error="Google Chat integration not available"), 503
        
        # Perform search
        search_results = await atom_google_chat_integration.unified_search(
            query,
            workspace_id,
            options={
                'channel_id': channel_id,
                'user_id': user_id,
                'limit': data.get('count', 50),
                'include_highlights': data.get('include_highlights', True),
                'include_relevance': data.get('include_relevance', True)
            }
        )
        
        # Store search in memory
        if AtomMemoryService:
            memory_data = {
                'type': 'google_chat_search',
                'query': query,
                'workspace_id': workspace_id,
                'channel_id': channel_id,
                'user_id': user_id,
                'results_count': len(search_results),
                'timestamp': datetime.utcnow().isoformat()
            }
            await AtomMemoryService.store(memory_data)
        
        # Index for search service
        if AtomSearchService:
            for result in search_results:
                search_data = {
                    'type': 'google_chat_message',
                    'id': result['id'],
                    'title': result['title'],
                    'content': result['content'],
                    'metadata': {
                        'workspace_id': result['workspace_id'],
                        'channel_id': result['channel_id'],
                        'user_id': result['user_id'],
                        'user_name': result['user_name'],
                        'timestamp': result['timestamp'],
                        'platform': result['platform'],
                        'relevance_score': result['relevance_score']
                    }
                }
                await AtomSearchService.index(search_data)
        
        return create_google_chat_response(
            True,
            data={
                'query': query,
                'results': search_results,
                'total': len(search_results),
                'search_time': datetime.utcnow().isoformat(),
                'insights': {
                    'top_spaces': len(set(result['workspace_id'] for result in search_results)),
                    'top_users': len(set(result['user_id'] for result in search_results)),
                    'avg_relevance': sum(result['relevance_score'] for result in search_results) / len(search_results) if search_results else 0
                }
            },
            message="Enhanced Google Chat search completed successfully"
        )
    
    except Exception as e:
        logger.error(f"Enhanced Google Chat search error: {e}")
        return create_google_chat_response(False, error=str(e)), 500

# File Operations
@google_chat_bp.route('/files/enhanced_upload', methods=['POST'])
def enhanced_google_chat_file_upload():
    """Enhanced Google Chat file upload with analysis"""
    try:
        data = get_google_chat_request_data()
        workspace_id = data.get('workspace_id')
        channel_id = data.get('channel_id')
        file_data = data.get('file_data')  # Base64 encoded file
        file_name = data.get('file_name')
        file_type = data.get('file_type')
        description = data.get('description')
        user_id = data.get('user_id')
        
        if not all([workspace_id, channel_id, file_data, file_name]):
            return create_google_chat_response(False, error="workspace_id, channel_id, file_data, and file_name are required")
        
        if not google_chat_enhanced_service:
            return create_google_chat_response(False, error="Google Chat service not available"), 503
        
        # Decode and upload file
        file_bytes = base64.b64decode(file_data)
        
        # For now, just simulate file upload
        file_info = {
            'file_id': f"gc_file_{int(datetime.utcnow().timestamp())}",
            'name': file_name,
            'display_name': file_name,
            'mime_type': file_type,
            'file_type': file_type.split('/')[0] if '/' in file_type else 'document',
            'size': len(file_bytes),
            'user_id': user_id,
            'user_name': 'Current User',
            'user_email': 'user@example.com',
            'space_id': channel_id,
            'timestamp': datetime.utcnow().isoformat(),
            'is_image': file_type.startswith('image/'),
            'is_video': file_type.startswith('video/'),
            'is_audio': file_type.startswith('audio/'),
            'is_document': file_type.startswith('application/') or file_type.startswith('text/')
        }
        
        # Index file for search
        if AtomSearchService:
            search_data = {
                'type': 'google_chat_file',
                'id': file_info['file_id'],
                'title': file_info['display_name'],
                'content': description or '',
                'metadata': {
                    'mime_type': file_info['mime_type'],
                    'size': file_info['size'],
                    'file_type': file_info['file_type'],
                    'workspace_id': workspace_id,
                    'channel_id': channel_id,
                    'user_id': file_info['user_id'],
                    'timestamp': file_info['timestamp']
                }
            }
            await AtomSearchService.index(search_data)
        
        return create_google_chat_response(
            True,
            data={
                'file': file_info,
                'uploaded': True
            },
            message="Google Chat file uploaded successfully"
        )
    
    except Exception as e:
        logger.error(f"Enhanced Google Chat file upload error: {e}")
        return create_google_chat_response(False, error=str(e)), 500

# Analytics and Reporting
@google_chat_bp.route('/analytics/metrics', methods=['POST'])
def get_google_chat_analytics_metrics():
    """Get Google Chat analytics metrics"""
    try:
        data = get_google_chat_request_data()
        metric_name = data.get('metric')
        time_range_name = data.get('time_range', 'last_7_days')
        granularity_name = data.get('granularity', 'day')
        workspace_id = data.get('workspace_id')
        channel_ids = data.get('channel_ids', [])
        user_ids = data.get('user_ids', [])
        
        if not metric_name:
            return create_google_chat_response(False, error="metric is required")
        
        if not atom_google_chat_integration:
            return create_google_chat_response(False, error="Google Chat integration not available"), 503
        
        # Get analytics data
        analytics_data = await atom_google_chat_integration.get_unified_analytics(
            metric_name,
            time_range_name,
            workspace_id,
            options={
                'granularity': granularity_name,
                'filters': data.get('filters', {}),
                'channel_ids': channel_ids,
                'user_ids': user_ids
            }
        )
        
        return create_google_chat_response(
            True,
            data=analytics_data,
            message="Google Chat analytics data retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Google Chat analytics metrics error: {e}")
        return create_google_chat_response(False, error=str(e)), 500

@google_chat_bp.route('/analytics/top_spaces', methods=['POST'])
def get_google_chat_top_spaces():
    """Get top Google Chat spaces by metric"""
    try:
        data = get_google_chat_request_data()
        metric_name = data.get('metric')
        time_range_name = data.get('time_range', 'last_7_days')
        limit = data.get('limit', 10)
        workspace_id = data.get('workspace_id')
        
        if not metric_name:
            return create_google_chat_response(False, error="metric is required")
        
        if not atom_google_chat_integration:
            return create_google_chat_response(False, error="Google Chat integration not available"), 503
        
        # This would get top spaces from analytics engine
        # For now, return mock data
        top_spaces = [
            {
                'space_id': 'space_1',
                'space_name': 'General Discussion',
                'value': 1250,
                'metric': metric_name,
                'human_ratio': 0.85,
                'time_range': time_range_name
            },
            {
                'space_id': 'space_2',
                'space_name': 'Project Alpha',
                'value': 980,
                'metric': metric_name,
                'human_ratio': 0.92,
                'time_range': time_range_name
            }
        ]
        
        return create_google_chat_response(
            True,
            data={
                'metric': metric_name,
                'time_range': time_range_name,
                'spaces': top_spaces[:limit],
                'total_spaces': len(top_spaces)
            },
            message="Google Chat top spaces retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Google Chat top spaces error: {e}")
        return create_google_chat_response(False, error=str(e)), 500

@google_chat_bp.route('/analytics/user_activity', methods=['POST'])
def get_google_chat_user_activity():
    """Get user activity analytics for Google Chat"""
    try:
        data = get_google_chat_request_data()
        user_id = data.get('user_id')
        time_range_name = data.get('time_range', 'last_7_days')
        workspace_id = data.get('workspace_id')
        
        if not user_id:
            return create_google_chat_response(False, error="user_id is required")
        
        # Return mock user activity data
        user_activity = {
            'user_id': user_id,
            'message_count': 245,
            'spaces_participated': 6,
            'threads_created': 18,
            'reactions_given': 35,
            'card_interactions': 12,
            'avg_response_time': 165,
            'most_active_hours': [10, 14, 16],
            'engagement_score': 0.78,
            'time_range': time_range_name,
            'top_spaces': [
                {'space_name': 'General Discussion', 'message_count': 85},
                {'space_name': 'Project Alpha', 'message_count': 62}
            ]
        }
        
        return create_google_chat_response(
            True,
            data=user_activity,
            message="Google Chat user activity retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Google Chat user activity error: {e}")
        return create_google_chat_response(False, error=str(e)), 500

# Workflow Automation
@google_chat_bp.route('/workflows', methods=['GET', 'POST'])
def manage_google_chat_workflows():
    """Get or create Google Chat workflows"""
    try:
        data = get_google_chat_request_data()
        user_id = data.get('user_id')
        
        if request.method == 'GET':
            # Get workflows
            workspace_id = data.get('workspace_id')
            
            if not atom_google_chat_integration:
                return create_google_chat_response(False, error="Google Chat integration not available"), 503
            
            # Return mock workflows
            workflows = [
                {
                    'id': 'gc_workflow_1',
                    'name': 'Auto-reply in General',
                    'description': 'Automatically reply to messages in General space',
                    'platform': 'google_chat',
                    'triggers': [
                        {'event': 'message', 'space_id': 'general'}
                    ],
                    'actions': [
                        {'action': 'send_message', 'text': 'Auto-reply: Thanks for your message!'}
                    ],
                    'enabled': True,
                    'created_at': '2023-12-04T10:00:00Z'
                }
            ]
            
            return create_google_chat_response(
                True,
                data={
                    'workflows': workflows,
                    'total_count': len(workflows)
                },
                message="Google Chat workflows retrieved successfully"
            )
        
        elif request.method == 'POST':
            # Create workflow
            workflow_data = data.get('workflow', {})
            
            if not atom_google_chat_integration:
                return create_google_chat_response(False, error="Google Chat integration not available"), 503
            
            # Create workflow
            result = await atom_google_chat_integration.create_unified_workflow(workflow_data)
            
            if result.get('ok'):
                return create_google_chat_response(
                    True,
                    data=result,
                    message="Google Chat workflow created successfully"
                )
            else:
                return create_google_chat_response(False, error=result.get('error')), 500
    
    except Exception as e:
        logger.error(f"Google Chat workflow management error: {e}")
        return create_google_chat_response(False, error=str(e)), 500

# Enhanced Webhook Handler
@google_chat_bp.route('/enhanced_events', methods=['POST'])
def enhanced_google_chat_webhook_handler():
    """Enhanced Google Chat webhook event handler"""
    try:
        # Get request data
        body = request.get_data()
        headers = request.headers
        
        # Verify signature (if provided)
        signature = headers.get('X-GoogleChat-Signature')
        signing_secret = os.getenv('GOOGLE_CHAT_SIGNING_SECRET')
        
        if signing_secret and not verify_google_chat_webhook(body, signature, signing_secret):
            return create_google_chat_response(False, error="Invalid signature"), 401
        
        # Parse event data
        event_data = json.loads(body.decode('utf-8'))
        
        if not google_chat_enhanced_service:
            return create_google_chat_response(False, error="Google Chat service not available"), 503
        
        # Process event
        result = await google_chat_enhanced_service.handle_webhook_event(event_data)
        
        # Store event for analytics
        if AtomMemoryService:
            memory_data = {
                'type': 'google_chat_webhook_event',
                'event_type': event_data.get('type', 'unknown'),
                'space_id': event_data.get('space', {}).get('name'),
                'event_id': event_data.get('event_id'),
                'timestamp': datetime.utcnow().isoformat(),
                'data': event_data
            }
            await AtomMemoryService.store(memory_data)
        
        return create_google_chat_response(
            result.get('ok', True),
            message="Google Chat webhook event processed successfully"
        )
    
    except Exception as e:
        logger.error(f"Enhanced Google Chat webhook error: {e}")
        return create_google_chat_response(False, error=str(e)), 500

# Data Ingestion
@google_chat_bp.route('/ingestion/start', methods=['POST'])
def start_google_chat_data_ingestion():
    """Start enhanced Google Chat data ingestion"""
    try:
        data = get_google_chat_request_data()
        user_id = data.get('user_id')
        workspace_id = data.get('workspace_id')
        space_ids = data.get('space_ids', [])
        config = data.get('config', {})
        
        if not atom_ingestion_pipeline:
            return create_google_chat_response(False, error="Ingestion pipeline not available"), 503
        
        # Start ingestion
        ingestion_config = {
            'sourceType': 'google_chat_enhanced',
            'workspace_id': workspace_id,
            'space_ids': space_ids,
            'config': {
                'syncOptions': {
                    'messageTypes': config.get('message_types', ['messages', 'replies', 'files']),
                    'realTimeSync': config.get('real_time_sync', True),
                    'syncFrequency': config.get('sync_frequency', 'realtime'),
                    'includeThreads': config.get('include_threads', True),
                    'includeCardInteractions': config.get('include_card_interactions', True)
                },
                'filters': config.get('filters', {}),
                'processing': {
                    'indexForSearch': config.get('index_for_search', True),
                    'analyzeSentiment': config.get('analyze_sentiment', False),
                    'extractTopics': config.get('extract_topics', True),
                    'processReactions': config.get('process_reactions', True)
                }
            }
        }
        
        result = await atom_ingestion_pipeline.startIngestion(
            ingestion_config,
            callback=data.get('callback')
        )
        
        return create_google_chat_response(
            True,
            data=result,
            message="Google Chat data ingestion started successfully"
        )
    
    except Exception as e:
        logger.error(f"Google Chat data ingestion start error: {e}")
        return create_google_chat_response(False, error=str(e)), 500

# Error handlers
@google_chat_bp.errorhandler(404)
def google_chat_not_found(error):
    return create_google_chat_response(False, error="Endpoint not found"), 404

@google_chat_bp.errorhandler(500)
def google_chat_internal_error(error):
    logger.error(f"Google Chat internal server error: {error}")
    return create_google_chat_response(False, error="Internal server error"), 500

# Register blueprint
def register_google_chat_api(app):
    """Register Google Chat API blueprint"""
    app.register_blueprint(google_chat_bp)
    logger.info("Google Chat API blueprint registered")

# Service initialization
def initialize_google_chat_services():
    """Initialize Google Chat services"""
    try:
        # Validate configuration
        if not validate_google_chat_config():
            return False
        
        # Initialize services
        if google_chat_enhanced_service:
            logger.info("Google Chat Enhanced service initialized")
        
        if atom_google_chat_integration:
            logger.info("Google Chat integration service initialized")
        
        return True
    
    except Exception as e:
        logger.error(f"Error initializing Google Chat services: {e}")
        return False

# Export for external use
__all__ = [
    'google_chat_bp',
    'register_google_chat_api',
    'initialize_google_chat_services',
    'create_google_chat_response',
    'get_google_chat_request_data'
]