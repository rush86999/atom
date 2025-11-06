"""
ATOM Enhanced Teams API Routes
Complete API with authentication, real-time features, calls, and analytics
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
    from teams_enhanced_service import teams_enhanced_service
    from teams_workflow_engine import teams_workflow_engine, TeamsWorkflowTemplate
    from teams_analytics_engine import teams_analytics_engine, TeamsAnalyticsMetric, TeamsAnalyticsTimeRange, TeamsAnalyticsGranularity
    from teams_call_service import teams_call_service
    from atom_ingestion_pipeline import atom_ingestion_pipeline
    from atom_memory_service import AtomMemoryService
    from atom_search_service import AtomSearchService
    from atom_workflow_service import atom_workflow_service
except ImportError as e:
    logger.warning(f"Enhanced Teams services not available: {e}")
    teams_enhanced_service = None
    teams_workflow_engine = None
    teams_analytics_engine = None
    teams_call_service = None
    atom_ingestion_pipeline = None
    AtomMemoryService = None
    AtomSearchService = None
    atom_workflow_service = None

# Create enhanced Teams API blueprint
enhanced_teams_bp = Blueprint('enhanced_teams_api', __name__, url_prefix='/api/integrations/teams')

# Configuration validation
def validate_teams_config():
    """Validate Teams configuration"""
    required_vars = [
        'TEAMS_CLIENT_ID',
        'TEAMS_CLIENT_SECRET',
        'TEAMS_TENANT_ID',
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
def create_teams_response(ok: bool, data: Any = None, error: str = None, 
                        message: str = None, metadata: Dict = None) -> Dict[str, Any]:
    """Create standardized Teams API response"""
    response = {
        'ok': ok,
        'timestamp': datetime.utcnow().isoformat(),
        'api_version': '3.0.0'
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

def get_teams_request_data() -> Dict[str, Any]:
    """Get and validate Teams request data"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id') or request.headers.get('X-User-ID', 'default-user')
        data['user_id'] = user_id
        return data
    except Exception as e:
        logger.error(f"Error parsing Teams request data: {e}")
        return {}

def verify_teams_webhook(request_body: bytes, signature: str, secret: str) -> bool:
    """Verify Teams webhook signature"""
    try:
        if not signature or not secret:
            return False
        
        # Teams uses HMAC-SHA256 for webhook validation
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            request_body,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures securely
        return hmac.compare_digest(expected_signature, signature.replace('sha256=', ''))
    
    except Exception as e:
        logger.error(f"Error verifying Teams webhook: {e}")
        return False

# Health Check
@enhanced_teams_bp.route('/enhanced_health', methods=['POST'])
def teams_enhanced_health_check():
    """Enhanced health check for all Teams services"""
    try:
        if not validate_teams_config():
            return create_teams_response(False, error="Configuration validation failed")
        
        health_status = {
            'teams_enhanced_service': teams_enhanced_service is not None,
            'teams_workflow_engine': teams_workflow_engine is not None,
            'teams_analytics_engine': teams_analytics_engine is not None,
            'teams_call_service': teams_call_service is not None,
            'ingestion_pipeline': atom_ingestion_pipeline is not None,
            'memory_service': AtomMemoryService is not None,
            'search_service': AtomSearchService is not None,
            'workflow_service': atom_workflow_service is not None
        }
        
        # Check service status
        all_healthy = all(health_status.values())
        
        # Get detailed status if services are available
        service_info = {}
        if teams_enhanced_service:
            service_info['teams_service'] = await teams_enhanced_service.get_service_info()
        if teams_workflow_engine:
            service_info['workflow_engine'] = teams_workflow_engine.get_execution_stats()
        if teams_analytics_engine:
            # Add analytics stats
            pass
        if teams_call_service:
            service_info['call_service'] = await teams_call_service.get_service_status()
        
        return create_teams_response(
            all_healthy,
            data={
                'services': health_status,
                'service_info': service_info,
                'status': 'healthy' if all_healthy else 'degraded'
            },
            message="Enhanced Teams services operational" if all_healthy else "Some services unavailable"
        )
    
    except Exception as e:
        logger.error(f"Enhanced Teams health check error: {e}")
        return create_teams_response(False, error=str(e)), 500

# OAuth and Authentication
@enhanced_teams_bp.route('/oauth_url', methods=['POST'])
def get_teams_oauth_url():
    """Generate OAuth authorization URL for Teams"""
    try:
        data = get_teams_request_data()
        user_id = data.get('user_id')
        
        if not teams_enhanced_service:
            return create_teams_response(False, error="Teams service not available"), 503
        
        # Generate secure state token
        state_token = f"teams_auth_{user_id}_{int(datetime.utcnow().timestamp())}"
        
        # Generate OAuth URL
        oauth_url = teams_enhanced_service.generate_oauth_url(
            state=state_token,
            user_id=user_id
        )
        
        return create_teams_response(
            True,
            data={
                'oauth_url': oauth_url,
                'state': state_token,
                'scopes': teams_enhanced_service.required_scopes,
                'expires_in': 600  # 10 minutes
            },
            message="Teams OAuth URL generated successfully"
        )
    
    except Exception as e:
        logger.error(f"Teams OAuth URL generation error: {e}")
        return create_teams_response(False, error=str(e)), 500

@enhanced_teams_bp.route('/oauth_callback', methods=['POST'])
def handle_teams_oauth_callback():
    """Handle Teams OAuth callback"""
    try:
        data = get_teams_request_data()
        code = data.get('code')
        state = data.get('state')
        
        if not code or not state:
            return create_teams_response(False, error="Missing code or state parameter")
        
        if not teams_enhanced_service:
            return create_teams_response(False, error="Teams service not available"), 503
        
        # Exchange code for tokens
        result = await teams_enhanced_service.exchange_code_for_tokens(code, state)
        
        if result.get('ok'):
            # Store in memory service
            if AtomMemoryService:
                memory_data = {
                    'type': 'teams_oauth_success',
                    'workspace_id': result.get('workspace', {}).get('team_id'),
                    'user_id': data.get('user_id'),
                    'timestamp': datetime.utcnow().isoformat()
                }
                await AtomMemoryService.store(memory_data)
            
            return create_teams_response(
                True,
                data=result.get('workspace'),
                message="Teams workspace connected successfully"
            )
        else:
            return create_teams_response(False, error=result.get('error')), 400
    
    except Exception as e:
        logger.error(f"Teams OAuth callback error: {e}")
        return create_teams_response(False, error=str(e)), 500

# Enhanced Workspace Management
@enhanced_teams_bp.route('/workspaces/enhanced', methods=['POST'])
def get_enhanced_teams_workspaces():
    """Get Teams workspaces with enhanced metadata"""
    try:
        data = get_teams_request_data()
        user_id = data.get('user_id')
        
        if not teams_enhanced_service:
            return create_teams_response(False, error="Teams service not available"), 503
        
        # Get workspaces
        workspaces = await teams_enhanced_service.get_workspaces(user_id)
        
        # Test connections
        workspace_data = []
        for workspace in workspaces:
            # Test connection status
            connection_test = await teams_enhanced_service.test_connection(workspace.team_id)
            
            workspace_info = {
                'id': workspace.team_id,
                'name': workspace.name,
                'displayName': workspace.display_name,
                'description': workspace.description,
                'visibility': workspace.visibility,
                'mailNickname': workspace.mail_nickname,
                'tenantId': workspace.tenant_id,
                'internalId': workspace.internal_id,
                'classification': workspace.classification,
                'specialization': workspace.specialization,
                'webUrl': workspace.web_url,
                'connectionStatus': connection_test.get('status', 'unknown'),
                'lastSync': workspace.last_sync.isoformat() if workspace.last_sync else None,
                'memberCount': workspace.member_count,
                'channelCount': workspace.channel_count,
                'isActive': workspace.is_active
            }
            
            workspace_data.append(workspace_info)
        
        return create_teams_response(
            True,
            data={
                'workspaces': workspace_data,
                'total_count': len(workspace_data),
                'connected_count': len([w for w in workspace_data if w['connectionStatus'] == 'connected'])
            },
            message="Enhanced Teams workspaces retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Enhanced Teams workspaces error: {e}")
        return create_teams_response(False, error=str(e)), 500

# Enhanced Channel Management
@enhanced_teams_bp.route('/channels/enhanced', methods=['POST'])
def get_enhanced_teams_channels():
    """Get Teams channels with enhanced metadata"""
    try:
        data = get_teams_request_data()
        workspace_id = data.get('workspace_id')
        user_id = data.get('user_id')
        include_stats = data.get('include_stats', True)
        include_activity = data.get('include_activity', True)
        
        if not workspace_id:
            return create_teams_response(False, error="workspace_id is required")
        
        if not teams_enhanced_service:
            return create_teams_response(False, error="Teams service not available"), 503
        
        # Get channels
        channels = await teams_enhanced_service.get_channels(
            workspace_id,
            user_id,
            include_private=data.get('include_private', False),
            include_archived=data.get('include_archived', False),
            limit=data.get('limit', 100)
        )
        
        channel_data = []
        for channel in channels:
            channel_info = {
                'id': channel.channel_id,
                'name': channel.name,
                'displayName': channel.display_name,
                'description': channel.description,
                'workspaceId': channel.workspace_id,
                'channelType': channel.channel_type,
                'email': channel.email,
                'webUrl': channel.web_url,
                'isFavoriteByDefault': channel.is_favorite_by_default,
                'membershipType': channel.membership_type,
                'createdAt': channel.created_at.isoformat(),
                'lastActivityAt': channel.last_activity_at.isoformat() if channel.last_activity_at else None,
                'memberCount': channel.member_count,
                'messageCount': channel.message_count,
                'filesCount': channel.files_count,
                'isArchived': channel.is_archived,
                'isWelcomeMessageEnabled': channel.is_welcome_message_enabled,
                'allowCrossTeamPosts': channel.allow_cross_team_posts,
                'allowGiphy': channel.allow_giphy,
                'giphyContentRating': channel.giphy_content_rating,
                'allowMemes': channel.allow_memes,
                'allowCustomMemes': channel.allow_custom_memes,
                'allowStickersAndGifs': channel.allow_stickers_and_gifs,
                'allowUserEditMessages': channel.allow_user_edit_messages,
                'allowOwnerDeleteMessages': channel.allow_owner_delete_messages,
                'allowTeamMentions': channel.allow_team_mentions,
                'allowChannelMentions': channel.allow_channel_mentions
            }
            
            # Add statistics if requested
            if include_stats:
                # This would fetch statistics from database
                channel_info['stats'] = {
                    'messageCount': 0,
                    'fileCount': 0,
                    'activeUsers': 0,
                    'lastActivity': None
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
        
        return create_teams_response(
            True,
            data={
                'channels': channel_data,
                'total_count': len(channel_data),
                'workspace_id': workspace_id
            },
            message="Enhanced Teams channels retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Enhanced Teams channels error: {e}")
        return create_teams_response(False, error=str(e)), 500

# Enhanced Message Operations
@enhanced_teams_bp.route('/messages/enhanced', methods=['POST'])
def get_enhanced_teams_messages():
    """Get Teams messages with enhanced metadata and analysis"""
    try:
        data = get_teams_request_data()
        workspace_id = data.get('workspace_id')
        channel_id = data.get('channel_id')
        user_id = data.get('user_id')
        
        if not workspace_id or not channel_id:
            return create_teams_response(False, error="workspace_id and channel_id are required")
        
        if not teams_enhanced_service:
            return create_teams_response(False, error="Teams service not available"), 503
        
        # Get messages
        messages = await teams_enhanced_service.get_channel_messages(
            workspace_id,
            channel_id,
            limit=data.get('limit', 100),
            latest=data.get('latest'),
            oldest=data.get('oldest')
        )
        
        message_data = []
        for message in messages:
            message_info = {
                'id': message.message_id,
                'text': message.text,
                'html': message.html,
                'userId': message.user_id,
                'userName': message.user_name,
                'userEmail': message.user_email,
                'channelId': message.channel_id,
                'workspaceId': message.workspace_id,
                'tenantId': message.tenant_id,
                'timestamp': message.timestamp,
                'threadId': message.thread_id,
                'replyToId': message.reply_to_id,
                'messageType': message.message_type,
                'importance': message.importance,
                'subject': message.subject,
                'summary': message.summary,
                'policyViolations': message.policy_violations,
                'attachments': message.attachments,
                'mentions': message.mentions,
                'reactions': message.reactions,
                'files': message.files,
                'localized': message.localized,
                'etag': message.etag,
                'lastModifiedAt': message.last_modified_at,
                'isEdited': message.is_edited,
                'editTimestamp': message.edit_timestamp,
                'isDeleted': message.is_deleted,
                'deleteTimestamp': message.delete_timestamp,
                'channelIdentity': message.channel_identity,
                'participantCount': message.participant_count
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
        
        return create_teams_response(
            True,
            data={
                'messages': message_data,
                'total_count': len(message_data),
                'channel_id': channel_id,
                'workspace_id': workspace_id,
                'has_more': len(message_data) == data.get('limit', 100)
            },
            message="Enhanced Teams messages retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Enhanced Teams messages error: {e}")
        return create_teams_response(False, error=str(e)), 500

@enhanced_teams_bp.route('/messages/enhanced_send', methods=['POST'])
def send_enhanced_teams_message():
    """Send Teams message with enhanced features"""
    try:
        data = get_teams_request_data()
        workspace_id = data.get('workspace_id')
        channel_id = data.get('channel_id')
        text = data.get('text')
        user_id = data.get('user_id')
        
        if not all([workspace_id, channel_id, text]):
            return create_teams_response(False, error="workspace_id, channel_id, and text are required")
        
        if not teams_enhanced_service:
            return create_teams_response(False, error="Teams service not available"), 503
        
        # Send message
        result = await teams_enhanced_service.send_message(
            workspace_id,
            channel_id,
            text,
            thread_id=data.get('thread_id'),
            importance=data.get('importance', 'normal'),
            subject=data.get('subject'),
            attachments=data.get('attachments')
        )
        
        if result.get('ok'):
            # Store in memory service
            if AtomMemoryService:
                memory_data = {
                    'type': 'sent_teams_message',
                    'workspace_id': workspace_id,
                    'channel_id': channel_id,
                    'message_id': result.get('message_id'),
                    'text': text,
                    'user_id': user_id,
                    'timestamp': datetime.utcnow().isoformat()
                }
                await AtomMemoryService.store(memory_data)
            
            return create_teams_response(
                True,
                data=result,
                message="Teams message sent successfully"
            )
        else:
            return create_teams_response(False, error=result.get('error')), 400
    
    except Exception as e:
        logger.error(f"Enhanced Teams send message error: {e}")
        return create_teams_response(False, error=str(e)), 500

# Enhanced Search
@enhanced_teams_bp.route('/search/enhanced', methods=['POST'])
def enhanced_teams_search():
    """Enhanced Teams search with analytics and insights"""
    try:
        data = get_teams_request_data()
        query = data.get('query')
        workspace_id = data.get('workspace_id')
        user_id = data.get('user_id')
        
        if not query:
            return create_teams_response(False, error="query is required")
        
        if not teams_enhanced_service:
            return create_teams_response(False, error="Teams service not available"), 503
        
        # Perform search
        search_result = await teams_enhanced_service.search_messages(
            workspace_id,
            query,
            channel_id=data.get('channel_id'),
            user_id=data.get('user_id'),
            limit=data.get('count', 50)
        )
        
        if search_result.get('ok'):
            # Store search in memory
            if AtomMemoryService:
                memory_data = {
                    'type': 'teams_search',
                    'query': query,
                    'workspace_id': workspace_id,
                    'user_id': user_id,
                    'results_count': len(search_result.get('messages', [])),
                    'timestamp': datetime.utcnow().isoformat()
                }
                await AtomMemoryService.store(memory_data)
            
            # Index for search service
            if AtomSearchService and search_result.get('messages'):
                for message in search_result.get('messages', []):
                    search_data = {
                        'type': 'teams_message',
                        'id': message.get('message_id'),
                        'title': message.get('subject', 'Teams Message'),
                        'content': message.get('text', ''),
                        'metadata': {
                            'workspace_id': workspace_id,
                            'channel_id': message.get('channel_id'),
                            'user_id': message.get('user_id'),
                            'user_name': message.get('user_name'),
                            'timestamp': message.get('timestamp'),
                            'importance': message.get('importance', 'normal')
                        }
                    }
                    await AtomSearchService.index(search_data)
            
            return create_teams_response(
                True,
                data={
                    'query': query,
                    'messages': search_result.get('messages', []),
                    'total': search_result.get('total', 0),
                    'search_time': datetime.utcnow().isoformat()
                },
                message="Enhanced Teams search completed successfully"
            )
        else:
            return create_teams_response(False, error=search_result.get('error')), 400
    
    except Exception as e:
        logger.error(f"Enhanced Teams search error: {e}")
        return create_teams_response(False, error=str(e)), 500

# File Operations
@enhanced_teams_bp.route('/files/enhanced_upload', methods=['POST'])
def enhanced_teams_file_upload():
    """Enhanced Teams file upload with analysis"""
    try:
        data = get_teams_request_data()
        workspace_id = data.get('workspace_id')
        channel_id = data.get('channel_id')
        file_path = data.get('file_path')
        title = data.get('title')
        description = data.get('description')
        user_id = data.get('user_id')
        
        if not all([workspace_id, channel_id, file_path]):
            return create_teams_response(False, error="workspace_id, channel_id, and file_path are required")
        
        if not teams_enhanced_service:
            return create_teams_response(False, error="Teams service not available"), 503
        
        # Upload file
        result = await teams_enhanced_service.upload_file(
            workspace_id,
            channel_id,
            file_path,
            title=title,
            description=description
        )
        
        if result.get('ok'):
            # Index file for search
            if AtomSearchService:
                file_data = result.get('file', {})
                search_data = {
                    'type': 'teams_file',
                    'id': file_data.get('file_id'),
                    'title': file_data.get('display_name'),
                    'content': file_data.get('description', ''),
                    'metadata': {
                        'mimetype': file_data.get('mime_type'),
                        'size': file_data.get('size'),
                        'file_type': file_data.get('file_type'),
                        'workspace_id': workspace_id,
                        'channel_id': channel_id,
                        'user_id': file_data.get('user_id'),
                        'user_name': file_data.get('user_name'),
                        'timestamp': file_data.get('timestamp'),
                        'url': file_data.get('url'),
                        'download_url': file_data.get('download_url')
                    }
                }
                await AtomSearchService.index(search_data)
            
            return create_teams_response(
                True,
                data=result,
                message="Teams file uploaded successfully"
            )
        else:
            return create_teams_response(False, error=result.get('error')), 400
    
    except Exception as e:
        logger.error(f"Enhanced Teams file upload error: {e}")
        return create_teams_response(False, error=str(e)), 500

# Call Operations
@enhanced_teams_bp.route('/calls/start', methods=['POST'])
def start_teams_call():
    """Start Teams call with enhanced features"""
    try:
        data = get_teams_request_data()
        channel_id = data.get('channel_id')
        call_type = data.get('type', 'video')  # audio or video
        user_id = data.get('user_id')
        
        if not channel_id:
            return create_teams_response(False, error="channel_id is required")
        
        if not teams_call_service:
            return create_teams_response(False, error="Teams call service not available"), 503
        
        # Start call
        call_result = await teams_call_service.start_call(
            channel_id=channel_id,
            call_type=call_type,
            user_id=user_id,
            options=data.get('options', {})
        )
        
        if call_result.get('ok'):
            # Store call in memory
            if AtomMemoryService:
                memory_data = {
                    'type': 'teams_call_started',
                    'call_id': call_result.get('call_id'),
                    'channel_id': channel_id,
                    'call_type': call_type,
                    'user_id': user_id,
                    'timestamp': datetime.utcnow().isoformat()
                }
                await AtomMemoryService.store(memory_data)
            
            return create_teams_response(
                True,
                data=call_result,
                message=f"Teams {call_type} call started successfully"
            )
        else:
            return create_teams_response(False, error=call_result.get('error')), 400
    
    except Exception as e:
        logger.error(f"Teams call start error: {e}")
        return create_teams_response(False, error=str(e)), 500

@enhanced_teams_bp.route('/calls/enhanced_info', methods=['POST'])
def get_enhanced_call_info():
    """Get enhanced Teams call information"""
    try:
        data = get_teams_request_data()
        call_id = data.get('call_id')
        user_id = data.get('user_id')
        
        if not call_id:
            return create_teams_response(False, error="call_id is required")
        
        if not teams_call_service:
            return create_teams_response(False, error="Teams call service not available"), 503
        
        # Get call info
        call_info = await teams_call_service.get_call_info(call_id, user_id)
        
        return create_teams_response(
            True,
            data=call_info,
            message="Teams call information retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Teams call info error: {e}")
        return create_teams_response(False, error=str(e)), 500

# Workflow Automation
@enhanced_teams_bp.route('/workflows', methods=['GET', 'POST'])
def manage_teams_workflows():
    """Get or create Teams workflows"""
    try:
        data = get_teams_request_data()
        user_id = data.get('user_id')
        
        if request.method == 'GET':
            # Get workflows
            workspace_id = data.get('workspace_id')
            
            if not teams_workflow_engine:
                return create_teams_response(False, error="Teams workflow engine not available"), 503
            
            workflows = teams_workflow_engine.list_workflows(workspace_id)
            
            return create_teams_response(
                True,
                data={
                    'workflows': [asdict(w) for w in workflows],
                    'total_count': len(workflows)
                },
                message="Teams workflows retrieved successfully"
            )
        
        elif request.method == 'POST':
            # Create workflow
            workflow_data = data.get('workflow', {})
            
            if not teams_workflow_engine:
                return create_teams_response(False, error="Teams workflow engine not available"), 503
            
            # Create workflow
            from teams_workflow_engine import TeamsWorkflow, TeamsWorkflowTrigger, TeamsWorkflowAction
            
            workflow = TeamsWorkflow(
                id=f"workflow_{int(datetime.utcnow().timestamp())}",
                name=workflow_data['name'],
                description=workflow_data.get('description', ''),
                triggers=[
                    TeamsWorkflowTrigger(**trigger_data)
                    for trigger_data in workflow_data.get('triggers', [])
                ],
                actions=[
                    TeamsWorkflowAction(**action_data)
                    for action_data in workflow_data.get('actions', [])
                ],
                created_by=user_id,
                created_at=datetime.utcnow()
            )
            
            # Register workflow
            success = teams_workflow_engine.register_workflow(workflow)
            
            if success:
                return create_teams_response(
                    True,
                    data=asdict(workflow),
                    message="Teams workflow created successfully"
                )
            else:
                return create_teams_response(False, error="Failed to create Teams workflow"), 500
    
    except Exception as e:
        logger.error(f"Teams workflow management error: {e}")
        return create_teams_response(False, error=str(e)), 500

@enhanced_teams_bp.route('/workflows/<workflow_id>/execute', methods=['POST'])
def execute_teams_workflow(workflow_id: str):
    """Execute Teams workflow"""
    try:
        data = get_teams_request_data()
        user_id = data.get('user_id')
        
        if not teams_workflow_engine:
            return create_teams_response(False, error="Teams workflow engine not available"), 503
        
        # Execute workflow
        execution = await teams_workflow_engine.execute_workflow(
            workflow_id,
            {
                'user_id': user_id,
                'source': 'api',
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        
        return create_teams_response(
            True,
            data=asdict(execution),
            message="Teams workflow execution started"
        )
    
    except Exception as e:
        logger.error(f"Teams workflow execution error: {e}")
        return create_teams_response(False, error=str(e)), 500

# Analytics and Reporting
@enhanced_teams_bp.route('/analytics/metrics', methods=['POST'])
def get_teams_analytics_metrics():
    """Get Teams analytics metrics"""
    try:
        data = get_teams_request_data()
        metric_name = data.get('metric')
        time_range_name = data.get('time_range', 'last_7_days')
        granularity_name = data.get('granularity', 'day')
        workspace_id = data.get('workspace_id')
        channel_ids = data.get('channel_ids', [])
        user_ids = data.get('user_ids', [])
        
        if not metric_name:
            return create_teams_response(False, error="metric is required")
        
        if not teams_analytics_engine:
            return create_teams_response(False, error="Teams analytics engine not available"), 503
        
        # Parse metric and time range
        try:
            metric = TeamsAnalyticsMetric(metric_name)
            time_range = TeamsAnalyticsTimeRange(time_range_name)
            granularity = TeamsAnalyticsGranularity(granularity_name)
        except ValueError as e:
            return create_teams_response(False, error=f"Invalid parameter: {e}"), 400
        
        # Get analytics data
        analytics_data = await teams_analytics_engine.get_analytics(
            metric=metric,
            time_range=time_range,
            granularity=granularity,
            filters=data.get('filters', {}),
            workspace_id=workspace_id,
            channel_ids=channel_ids,
            user_ids=user_ids
        )
        
        # Convert to serializable format
        data_points = []
        for point in analytics_data:
            data_points.append({
                'timestamp': point.timestamp.isoformat(),
                'metric': point.metric.value,
                'value': point.value,
                'dimensions': point.dimensions,
                'metadata': point.metadata
            })
        
        return create_teams_response(
            True,
            data={
                'metric': metric.value,
                'time_range': time_range.value,
                'granularity': granularity.value,
                'data_points': data_points,
                'total_points': len(data_points)
            },
            message="Teams analytics data retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Teams analytics metrics error: {e}")
        return create_teams_response(False, error=str(e)), 500

@enhanced_teams_bp.route('/analytics/call_metrics', methods=['POST'])
def get_teams_call_analytics():
    """Get Teams call analytics"""
    try:
        data = get_teams_request_data()
        time_range_name = data.get('time_range', 'last_7_days')
        workspace_id = data.get('workspace_id')
        
        if not teams_analytics_engine:
            return create_teams_response(False, error="Teams analytics engine not available"), 503
        
        # Parse time range
        try:
            time_range = TeamsAnalyticsTimeRange(time_range_name)
        except ValueError as e:
            return create_teams_response(False, error=f"Invalid parameter: {e}"), 400
        
        # Get call analytics
        call_analytics = await teams_analytics_engine.get_call_analytics(
            time_range=time_range,
            workspace_id=workspace_id,
            filters=data.get('filters', {})
        )
        
        return create_teams_response(
            True,
            data=call_analytics,
            message="Teams call analytics retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Teams call analytics error: {e}")
        return create_teams_response(False, error=str(e)), 500

@enhanced_teams_bp.route('/analytics/top_users', methods=['POST'])
def get_teams_top_users():
    """Get top Teams users by metric"""
    try:
        data = get_teams_request_data()
        metric_name = data.get('metric')
        time_range_name = data.get('time_range', 'last_7_days')
        limit = data.get('limit', 10)
        workspace_id = data.get('workspace_id')
        
        if not metric_name:
            return create_teams_response(False, error="metric is required")
        
        if not teams_analytics_engine:
            return create_teams_response(False, error="Teams analytics engine not available"), 503
        
        # Parse parameters
        try:
            metric = TeamsAnalyticsMetric(metric_name)
            time_range = TeamsAnalyticsTimeRange(time_range_name)
        except ValueError as e:
            return create_teams_response(False, error=f"Invalid parameter: {e}"), 400
        
        # Get top users
        top_users = await teams_analytics_engine.get_top_users(
            metric=metric,
            time_range=time_range,
            limit=limit,
            filters=data.get('filters', {}),
            workspace_id=workspace_id
        )
        
        return create_teams_response(
            True,
            data={
                'metric': metric.value,
                'time_range': time_range.value,
                'users': top_users,
                'total_users': len(top_users)
            },
            message="Teams top users retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Teams top users error: {e}")
        return create_teams_response(False, error=str(e)), 500

# Enhanced Webhook Handler
@enhanced_teams_bp.route('/enhanced_events', methods=['POST'])
def enhanced_teams_webhook_handler():
    """Enhanced Teams webhook event handler"""
    try:
        # Get request data
        body = request.get_data()
        headers = request.headers
        
        # Verify signature (if provided)
        signature = headers.get('X-Teams-Signature')
        signing_secret = os.getenv('TEAMS_SIGNING_SECRET')
        
        if signing_secret and not verify_teams_webhook(body, signature, signing_secret):
            return create_teams_response(False, error="Invalid signature"), 401
        
        # Parse event data
        event_data = json.loads(body.decode('utf-8'))
        
        if not teams_enhanced_service:
            return create_teams_response(False, error="Teams service not available"), 503
        
        # Process event
        result = await teams_enhanced_service.handle_webhook_event(event_data)
        
        # Store event for analytics
        if AtomMemoryService:
            memory_data = {
                'type': 'teams_webhook_event',
                'event_type': event_data.get('event', {}).get('type'),
                'team_id': event_data.get('team_id'),
                'event_id': event_data.get('event_id'),
                'timestamp': datetime.utcnow().isoformat(),
                'data': event_data
            }
            await AtomMemoryService.store(memory_data)
        
        return create_teams_response(
            result.get('ok', True),
            message="Teams webhook event processed successfully"
        )
    
    except Exception as e:
        logger.error(f"Enhanced Teams webhook error: {e}")
        return create_teams_response(False, error=str(e)), 500

# Data Ingestion
@enhanced_teams_bp.route('/ingestion/start', methods=['POST'])
def start_teams_data_ingestion():
    """Start enhanced Teams data ingestion"""
    try:
        data = get_teams_request_data()
        user_id = data.get('user_id')
        workspace_id = data.get('workspace_id')
        channel_ids = data.get('channel_ids', [])
        config = data.get('config', {})
        
        if not atom_ingestion_pipeline:
            return create_teams_response(False, error="Ingestion pipeline not available"), 503
        
        # Start ingestion
        ingestion_config = {
            'sourceType': 'teams_enhanced',
            'workspace_id': workspace_id,
            'channel_ids': channel_ids,
            'config': {
                'syncOptions': {
                    'messageTypes': config.get('message_types', ['messages', 'replies', 'files']),
                    'realTimeSync': config.get('real_time_sync', True),
                    'syncFrequency': config.get('sync_frequency', 'realtime'),
                    'includeArchived': config.get('include_archived', False),
                    'includePrivate': config.get('include_private', True),
                    'excludeBots': config.get('exclude_bots', False)
                },
                'filters': config.get('filters', {}),
                'processing': {
                    'indexForSearch': config.get('index_for_search', True),
                    'analyzeSentiment': config.get('analyze_sentiment', False),
                    'extractTopics': config.get('extract_topics', True)
                },
                'callProcessing': {
                    'indexCalls': config.get('index_calls', True),
                    'recordMeetings': config.get('record_meetings', False),
                    'analyzeCallData': config.get('analyze_call_data', True)
                }
            }
        }
        
        result = await atom_ingestion_pipeline.startIngestion(
            ingestion_config,
            callback=data.get('callback')
        )
        
        return create_teams_response(
            True,
            data=result,
            message="Teams data ingestion started successfully"
        )
    
    except Exception as e:
        logger.error(f"Teams data ingestion start error: {e}")
        return create_teams_response(False, error=str(e)), 500

# Error handlers
@enhanced_teams_bp.errorhandler(404)
def teams_not_found(error):
    return create_teams_response(False, error="Endpoint not found"), 404

@enhanced_teams_bp.errorhandler(500)
def teams_internal_error(error):
    logger.error(f"Teams internal server error: {error}")
    return create_teams_response(False, error="Internal server error"), 500

# Register blueprint
def register_enhanced_teams_api(app):
    """Register enhanced Teams API blueprint"""
    app.register_blueprint(enhanced_teams_bp)
    logger.info("Enhanced Teams API blueprint registered")

# Service initialization
def initialize_enhanced_teams_services():
    """Initialize enhanced Teams services"""
    try:
        # Validate configuration
        if not validate_teams_config():
            return False
        
        # Initialize services
        if teams_enhanced_service:
            logger.info("Enhanced Teams service initialized")
        
        if teams_workflow_engine:
            logger.info("Teams workflow engine initialized")
        
        if teams_analytics_engine:
            logger.info("Teams analytics engine initialized")
        
        if teams_call_service:
            logger.info("Teams call service initialized")
        
        return True
    
    except Exception as e:
        logger.error(f"Error initializing enhanced Teams services: {e}")
        return False

# Export for external use
__all__ = [
    'enhanced_teams_bp',
    'register_enhanced_teams_api',
    'initialize_enhanced_teams_services',
    'create_teams_response',
    'get_teams_request_data'
]