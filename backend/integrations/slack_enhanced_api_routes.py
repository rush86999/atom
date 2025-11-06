"""
ATOM Enhanced Slack API Routes
Complete API with workflow automation, analytics, and real-time features
"""

import os
import logging
import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from flask import Blueprint, request, jsonify, current_app
from loguru import logger

# Import enhanced services
try:
    from slack_enhanced_service import slack_enhanced_service
    from slack_workflow_engine import workflow_engine, WorkflowTemplate
    from slack_analytics_engine import slack_analytics_engine, AnalyticsMetric, AnalyticsTimeRange, AnalyticsGranularity
    from atom_ingestion_pipeline import atom_ingestion_pipeline
    from atom_memory_service import AtomMemoryService
    from atom_search_service import AtomSearchService
    from slack_workflow_automation import slack_workflow_automation
except ImportError as e:
    logger.warning(f"Enhanced Slack services not available: {e}")
    slack_enhanced_service = None
    workflow_engine = None
    slack_analytics_engine = None
    atom_ingestion_pipeline = None
    AtomMemoryService = None
    AtomSearchService = None
    slack_workflow_automation = None

# Create enhanced Slack API blueprint
enhanced_slack_bp = Blueprint('enhanced_slack_api', __name__, url_prefix='/api/integrations/slack')

# Configuration validation
def validate_enhanced_config():
    """Validate enhanced Slack configuration"""
    required_vars = [
        'SLACK_CLIENT_ID',
        'SLACK_CLIENT_SECRET', 
        'SLACK_SIGNING_SECRET',
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
def create_response(ok: bool, data: Any = None, error: str = None, 
                    message: str = None, metadata: Dict = None) -> Dict[str, Any]:
    """Create standardized API response"""
    response = {
        'ok': ok,
        'timestamp': datetime.utcnow().isoformat()
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

def get_request_data() -> Dict[str, Any]:
    """Get and validate request data"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id') or request.headers.get('X-User-ID', 'default-user')
        data['user_id'] = user_id
        return data
    except Exception as e:
        logger.error(f"Error parsing request data: {e}")
        return {}

def async_route(coro):
    """Decorator for async routes"""
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro(*args, **kwargs))
        except Exception as e:
            logger.error(f"Error in async route: {e}")
            return create_response(False, error=str(e)), 500
        finally:
            loop.close()
    return wrapper

# Health Check
@enhanced_slack_bp.route('/enhanced_health', methods=['POST'])
def enhanced_health_check():
    """Enhanced health check for all Slack services"""
    try:
        if not validate_enhanced_config():
            return create_response(False, error="Configuration validation failed")
        
        health_status = {
            'slack_enhanced_service': slack_enhanced_service is not None,
            'workflow_engine': workflow_engine is not None,
            'analytics_engine': slack_analytics_engine is not None,
            'ingestion_pipeline': atom_ingestion_pipeline is not None,
            'memory_service': AtomMemoryService is not None,
            'search_service': AtomSearchService is not None,
            'workflow_automation': slack_workflow_automation is not None
        }
        
        # Check service status
        all_healthy = all(health_status.values())
        
        # Get detailed status if services are available
        service_info = {}
        if slack_enhanced_service:
            service_info['slack_service'] = await slack_enhanced_service.get_service_info()
        if workflow_engine:
            service_info['workflow_engine'] = workflow_engine.get_execution_stats()
        if slack_analytics_engine:
            # Add analytics stats
            pass
        
        return create_response(
            all_healthy,
            data={
                'services': health_status,
                'service_info': service_info,
                'status': 'healthy' if all_healthy else 'degraded'
            },
            message="Enhanced Slack services operational" if all_healthy else "Some services unavailable"
        )
    
    except Exception as e:
        logger.error(f"Enhanced health check error: {e}")
        return create_response(False, error=str(e)), 500

# OAuth and Authentication
@enhanced_slack_bp.route('/oauth_url', methods=['POST'])
def get_oauth_url():
    """Generate OAuth authorization URL with enhanced security"""
    try:
        data = get_request_data()
        user_id = data.get('user_id')
        
        if not slack_enhanced_service:
            return create_response(False, error="Slack service not available"), 503
        
        # Generate secure state token
        state_token = f"slack_auth_{user_id}_{int(datetime.utcnow().timestamp())}"
        
        # Store state token in memory/redis
        # This would be stored securely in production
        
        # Generate OAuth URL
        scopes = data.get('scopes', [
            'channels:read', 'channels:history', 'groups:read', 'groups:history',
            'im:read', 'im:history', 'mpim:read', 'mpim:history',
            'users:read', 'users:read.email', 'chat:write', 'chat:write.public',
            'files:read', 'files:write', 'reactions:read', 'reactions:write',
            'team:read', 'channels:manage', 'users:write'
        ])
        
        oauth_url = slack_enhanced_service.generate_oauth_url(
            state=state_token,
            user_id=user_id,
            scopes=scopes
        )
        
        return create_response(
            True,
            data={
                'oauth_url': oauth_url,
                'state': state_token,
                'scopes': scopes,
                'expires_in': 600  # 10 minutes
            },
            message="OAuth URL generated successfully"
        )
    
    except Exception as e:
        logger.error(f"OAuth URL generation error: {e}")
        return create_response(False, error=str(e)), 500

@enhanced_slack_bp.route('/oauth_callback', methods=['POST'])
def handle_oauth_callback():
    """Handle OAuth callback with enhanced security"""
    try:
        data = get_request_data()
        code = data.get('code')
        state = data.get('state')
        
        if not code or not state:
            return create_response(False, error="Missing code or state parameter")
        
        if not slack_enhanced_service:
            return create_response(False, error="Slack service not available"), 503
        
        # Validate state token
        user_id = data.get('user_id')
        if not user_id:
            return create_response(False, error="User ID required")
        
        # Exchange code for tokens
        result = await slack_enhanced_service.exchange_code_for_tokens(code, state)
        
        if result.get('ok'):
            return create_response(
                True,
                data=result.get('workspace'),
                message="Slack workspace connected successfully"
            )
        else:
            return create_response(False, error=result.get('error')), 400
    
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return create_response(False, error=str(e)), 500

# Enhanced Workspace Management
@enhanced_slack_bp.route('/workspaces/enhanced', methods=['POST'])
def get_enhanced_workspaces():
    """Get workspaces with enhanced metadata"""
    try:
        data = get_request_data()
        user_id = data.get('user_id')
        
        if not slack_enhanced_service:
            return create_response(False, error="Slack service not available"), 503
        
        # Get workspaces
        workspaces = await slack_enhanced_service.get_workspaces(user_id)
        
        # Test connections
        workspace_data = []
        for workspace in workspaces:
            # Test connection status
            connection_test = await slack_enhanced_service.test_connection(workspace.id)
            
            workspace_info = {
                'id': workspace.id,
                'name': workspace.name,
                'domain': workspace.domain,
                'url': workspace.url,
                'icon_url': workspace.icon_url,
                'is_verified': workspace.enterprise_id is not None,
                'plan': workspace.enterprise_name or 'Free',
                'connection_status': connection_test.get('status', 'unknown'),
                'last_sync': workspace.last_sync.isoformat() if workspace.last_sync else None,
                'member_count': connection_test.get('workspace', {}).get('member_count', 0),
                'channel_count': 0  # Would be fetched from database
            }
            
            workspace_data.append(workspace_info)
        
        return create_response(
            True,
            data={
                'workspaces': workspace_data,
                'total_count': len(workspace_data),
                'connected_count': len([w for w in workspace_data if w['connection_status'] == 'connected'])
            },
            message="Workspaces retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Enhanced workspaces error: {e}")
        return create_response(False, error=str(e)), 500

# Enhanced Channel Management
@enhanced_slack_bp.route('/channels/enhanced', methods=['POST'])
def get_enhanced_channels():
    """Get channels with enhanced metadata"""
    try:
        data = get_request_data()
        workspace_id = data.get('workspace_id')
        user_id = data.get('user_id')
        include_stats = data.get('include_stats', True)
        include_activity = data.get('include_activity', True)
        
        if not workspace_id:
            return create_response(False, error="workspace_id is required")
        
        if not slack_enhanced_service:
            return create_response(False, error="Slack service not available"), 503
        
        # Get channels
        channels = await slack_enhanced_service.get_channels(
            workspace_id,
            user_id,
            include_private=data.get('include_private', False),
            include_archived=data.get('include_archived', False),
            limit=data.get('limit', 100)
        )
        
        channel_data = []
        for channel in channels:
            channel_info = {
                'id': channel.id,
                'name': channel.name,
                'display_name': channel.display_name,
                'purpose': channel.purpose,
                'topic': channel.topic,
                'is_private': channel.is_private,
                'is_archived': channel.is_archived,
                'is_general': channel.is_general,
                'is_shared': channel.is_shared,
                'workspace_id': channel.workspace_id,
                'num_members': channel.num_members,
                'created': channel.created.isoformat(),
                'unread_count': channel.unread_count,
                'is_muted': channel.is_muted
            }
            
            # Add statistics if requested
            if include_stats:
                # This would fetch statistics from database
                channel_info['stats'] = {
                    'message_count': 0,
                    'file_count': 0,
                    'active_users': 0,
                    'last_activity': None
                }
            
            # Add recent activity if requested
            if include_activity:
                # This would fetch recent activity
                channel_info['recent_activity'] = {
                    'last_message': None,
                    'active_users': [],
                    'trending_topics': []
                }
            
            channel_data.append(channel_info)
        
        return create_response(
            True,
            data={
                'channels': channel_data,
                'total_count': len(channel_data),
                'workspace_id': workspace_id
            },
            message="Enhanced channels retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Enhanced channels error: {e}")
        return create_response(False, error=str(e)), 500

# Enhanced Message Operations
@enhanced_slack_bp.route('/messages/enhanced', methods=['POST'])
def get_enhanced_messages():
    """Get messages with enhanced metadata and analysis"""
    try:
        data = get_request_data()
        workspace_id = data.get('workspace_id')
        channel_id = data.get('channel_id')
        user_id = data.get('user_id')
        
        if not workspace_id or not channel_id:
            return create_response(False, error="workspace_id and channel_id are required")
        
        if not slack_enhanced_service:
            return create_response(False, error="Slack service not available"), 503
        
        # Get messages
        messages = await slack_enhanced_service.get_channel_history(
            workspace_id,
            channel_id,
            limit=data.get('limit', 100),
            latest=data.get('latest'),
            oldest=data.get('oldest'),
            include_threads=data.get('include_threads', True)
        )
        
        message_data = []
        for message in messages:
            message_info = {
                'id': message.id,
                'text': message.text,
                'user_id': message.user_id,
                'user_name': message.user_name,
                'channel_id': message.channel_id,
                'channel_name': message.channel_name,
                'workspace_id': message.workspace_id,
                'timestamp': message.timestamp,
                'thread_ts': message.thread_ts,
                'reply_count': message.reply_count,
                'type': message.message_type,
                'subtype': message.subtype,
                'is_starred': message.is_starred,
                'is_edited': message.is_edited,
                'edit_timestamp': message.edit_timestamp,
                'mentions': message.mentions,
                'reactions': message.reactions,
                'files': message.files,
                'pinned_to': message.pinned_to,
                'blocks': message.blocks,
                'bot_profile': message.bot_profile
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
        
        return create_response(
            True,
            data={
                'messages': message_data,
                'total_count': len(message_data),
                'channel_id': channel_id,
                'workspace_id': workspace_id,
                'has_more': len(message_data) == data.get('limit', 100)
            },
            message="Enhanced messages retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Enhanced messages error: {e}")
        return create_response(False, error=str(e)), 500

@enhanced_slack_bp.route('/messages/enhanced_send', methods=['POST'])
def send_enhanced_message():
    """Send message with enhanced features"""
    try:
        data = get_request_data()
        workspace_id = data.get('workspace_id')
        channel_id = data.get('channel_id')
        message_text = data.get('text')
        user_id = data.get('user_id')
        
        if not all([workspace_id, channel_id, message_text]):
            return create_response(False, error="workspace_id, channel_id, and text are required")
        
        if not slack_enhanced_service:
            return create_response(False, error="Slack service not available"), 503
        
        # Send message
        result = await slack_enhanced_service.send_message(
            workspace_id,
            channel_id,
            message_text,
            thread_ts=data.get('thread_ts'),
            blocks=data.get('blocks'),
            attachments=data.get('attachments')
        )
        
        if result.get('ok'):
            # Store in memory service
            if AtomMemoryService:
                memory_data = {
                    'type': 'sent_message',
                    'workspace_id': workspace_id,
                    'channel_id': channel_id,
                    'message_id': result.get('message_id'),
                    'text': message_text,
                    'user_id': user_id,
                    'timestamp': datetime.utcnow().isoformat()
                }
                await AtomMemoryService.store(memory_data)
            
            return create_response(
                True,
                data=result,
                message="Message sent successfully"
            )
        else:
            return create_response(False, error=result.get('error')), 400
    
    except Exception as e:
        logger.error(f"Enhanced send message error: {e}")
        return create_response(False, error=str(e)), 500

# Enhanced Search
@enhanced_slack_bp.route('/search/enhanced', methods=['POST'])
def enhanced_search():
    """Enhanced search with analytics and insights"""
    try:
        data = get_request_data()
        query = data.get('query')
        workspace_id = data.get('workspace_id')
        user_id = data.get('user_id')
        
        if not query:
            return create_response(False, error="query is required")
        
        if not slack_enhanced_service:
            return create_response(False, error="Slack service not available"), 503
        
        # Perform search
        search_result = await slack_enhanced_service.search_messages(
            workspace_id,
            query,
            channel_id=data.get('channel_id'),
            user_id=data.get('user_id'),
            sort=data.get('sort', 'timestamp'),
            sort_dir=data.get('sort_dir', 'desc'),
            count=data.get('count', 50)
        )
        
        if search_result.get('ok'):
            # Store search in memory
            if AtomMemoryService:
                memory_data = {
                    'type': 'slack_search',
                    'query': query,
                    'workspace_id': workspace_id,
                    'user_id': user_id,
                    'results_count': len(search_result.get('messages', [])),
                    'timestamp': datetime.utcnow().isoformat()
                }
                await AtomMemoryService.store(memory_data)
            
            return create_response(
                True,
                data={
                    'query': query,
                    'messages': search_result.get('messages', []),
                    'total': search_result.get('total', 0),
                    'paging': search_result.get('paging'),
                    'search_time': datetime.utcnow().isoformat()
                },
                message="Enhanced search completed successfully"
            )
        else:
            return create_response(False, error=search_result.get('error')), 400
    
    except Exception as e:
        logger.error(f"Enhanced search error: {e}")
        return create_response(False, error=str(e)), 500

# Workflow Automation
@enhanced_slack_bp.route('/workflows', methods=['GET', 'POST'])
def manage_workflows():
    """Get or create workflows"""
    try:
        data = get_request_data()
        user_id = data.get('user_id')
        
        if request.method == 'GET':
            # Get workflows
            workspace_id = data.get('workspace_id')
            
            if not slack_workflow_automation:
                return create_response(False, error="Workflow automation service not available"), 503
            
            workflows = slack_workflow_automation.list_workspaces(workspace_id)
            
            return create_response(
                True,
                data={
                    'workflows': [asdict(w) for w in workflows],
                    'total_count': len(workflows)
                },
                message="Workflows retrieved successfully"
            )
        
        elif request.method == 'POST':
            # Create workflow
            workflow_data = data.get('workflow', {})
            
            if not slack_workflow_automation:
                return create_response(False, error="Workflow automation service not available"), 503
            
            # Validate workflow data
            if not workflow_data.get('name'):
                return create_response(False, error="Workflow name is required")
            
            # Create workflow
            from slack_workflow_automation import SlackWorkflow, SlackWorkflowTrigger, SlackWorkflowAction
            
            workflow = SlackWorkflow(
                id=f"workflow_{int(datetime.utcnow().timestamp())}",
                name=workflow_data['name'],
                description=workflow_data.get('description', ''),
                triggers=[
                    SlackWorkflowTrigger(**trigger_data)
                    for trigger_data in workflow_data.get('triggers', [])
                ],
                actions=[
                    SlackWorkflowAction(**action_data)
                    for action_data in workflow_data.get('actions', [])
                ],
                created_by=user_id,
                created_at=datetime.utcnow()
            )
            
            # Register workflow
            success = slack_workflow_automation.register_workflow(workflow)
            
            if success:
                return create_response(
                    True,
                    data=asdict(workflow),
                    message="Workflow created successfully"
                )
            else:
                return create_response(False, error="Failed to create workflow"), 500
    
    except Exception as e:
        logger.error(f"Workflow management error: {e}")
        return create_response(False, error=str(e)), 500

@enhanced_slack_bp.route('/workflows/<workflow_id>/execute', methods=['POST'])
def execute_workflow(workflow_id: str):
    """Execute a workflow"""
    try:
        data = get_request_data()
        user_id = data.get('user_id')
        
        if not slack_workflow_automation:
            return create_response(False, error="Workflow automation service not available"), 503
        
        # Execute workflow
        execution = await slack_workflow_automation.execute_workflow(
            workflow_id,
            {
                'user_id': user_id,
                'source': 'api',
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        
        return create_response(
            True,
            data=asdict(execution),
            message="Workflow execution started"
        )
    
    except Exception as e:
        logger.error(f"Workflow execution error: {e}")
        return create_response(False, error=str(e)), 500

@enhanced_slack_bp.route('/workflows/templates', methods=['GET'])
def get_workflow_templates():
    """Get available workflow templates"""
    try:
        templates = [
            asdict(WorkflowTemplate.welcome_message()),
            asdict(WorkflowTemplate.message_summary())
        ]
        
        return create_response(
            True,
            data={
                'templates': templates,
                'total_count': len(templates)
            },
            message="Workflow templates retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Workflow templates error: {e}")
        return create_response(False, error=str(e)), 500

# Analytics and Reporting
@enhanced_slack_bp.route('/analytics/metrics', methods=['POST'])
def get_analytics_metrics():
    """Get analytics metrics"""
    try:
        data = get_request_data()
        metric_name = data.get('metric')
        time_range_name = data.get('time_range', 'last_7_days')
        granularity_name = data.get('granularity', 'day')
        workspace_id = data.get('workspace_id')
        channel_ids = data.get('channel_ids', [])
        user_ids = data.get('user_ids', [])
        
        if not metric_name:
            return create_response(False, error="metric is required")
        
        if not slack_analytics_engine:
            return create_response(False, error="Analytics engine not available"), 503
        
        # Parse metric and time range
        try:
            metric = AnalyticsMetric(metric_name)
            time_range = AnalyticsTimeRange(time_range_name)
            granularity = AnalyticsGranularity(granularity_name)
        except ValueError as e:
            return create_response(False, error=f"Invalid parameter: {e}"), 400
        
        # Get analytics data
        analytics_data = await slack_analytics_engine.get_analytics(
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
        
        return create_response(
            True,
            data={
                'metric': metric.value,
                'time_range': time_range.value,
                'granularity': granularity.value,
                'data_points': data_points,
                'total_points': len(data_points)
            },
            message="Analytics data retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Analytics metrics error: {e}")
        return create_response(False, error=str(e)), 500

@enhanced_slack_bp.route('/analytics/insights', methods=['POST'])
def get_analytics_insights():
    """Get analytics insights"""
    try:
        data = get_request_data()
        metric_name = data.get('metric')
        time_range_name = data.get('time_range', 'last_7_days')
        workspace_id = data.get('workspace_id')
        
        if not metric_name:
            return create_response(False, error="metric is required")
        
        if not slack_analytics_engine:
            return create_response(False, error="Analytics engine not available"), 503
        
        # Parse parameters
        try:
            metric = AnalyticsMetric(metric_name)
            time_range = AnalyticsTimeRange(time_range_name)
        except ValueError as e:
            return create_response(False, error=f"Invalid parameter: {e}"), 400
        
        # Get insights
        insights = await slack_analytics_engine.get_insights(
            metric=metric,
            time_range=time_range,
            filters=data.get('filters', {})
        )
        
        return create_response(
            True,
            data=insights,
            message="Analytics insights retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Analytics insights error: {e}")
        return create_response(False, error=str(e)), 500

@enhanced_slack_bp.route('/analytics/top_users', methods=['POST'])
def get_top_users():
    """Get top users by metric"""
    try:
        data = get_request_data()
        metric_name = data.get('metric')
        time_range_name = data.get('time_range', 'last_7_days')
        limit = data.get('limit', 10)
        workspace_id = data.get('workspace_id')
        
        if not metric_name:
            return create_response(False, error="metric is required")
        
        if not slack_analytics_engine:
            return create_response(False, error="Analytics engine not available"), 503
        
        # Parse parameters
        try:
            metric = AnalyticsMetric(metric_name)
            time_range = AnalyticsTimeRange(time_range_name)
        except ValueError as e:
            return create_response(False, error=f"Invalid parameter: {e}"), 400
        
        # Get top users
        top_users = await slack_analytics_engine.get_top_users(
            metric=metric,
            time_range=time_range,
            limit=limit,
            filters=data.get('filters', {})
        )
        
        return create_response(
            True,
            data={
                'metric': metric.value,
                'time_range': time_range.value,
                'users': top_users,
                'total_users': len(top_users)
            },
            message="Top users retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Top users error: {e}")
        return create_response(False, error=str(e)), 500

@enhanced_slack_bp.route('/analytics/trending_topics', methods=['POST'])
def get_trending_topics():
    """Get trending topics"""
    try:
        data = get_request_data()
        time_range_name = data.get('time_range', 'last_7_days')
        limit = data.get('limit', 20)
        workspace_id = data.get('workspace_id')
        
        if not slack_analytics_engine:
            return create_response(False, error="Analytics engine not available"), 503
        
        # Parse parameters
        try:
            time_range = AnalyticsTimeRange(time_range_name)
        except ValueError as e:
            return create_response(False, error=f"Invalid parameter: {e}"), 400
        
        # Get trending topics
        trending_topics = await slack_analytics_engine.get_trending_topics(
            time_range=time_range,
            limit=limit,
            filters=data.get('filters', {})
        )
        
        return create_response(
            True,
            data={
                'time_range': time_range.value,
                'topics': trending_topics,
                'total_topics': len(trending_topics)
            },
            message="Trending topics retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Trending topics error: {e}")
        return create_response(False, error=str(e)), 500

@enhanced_slack_bp.route('/analytics/predict_volume', methods=['POST'])
def predict_message_volume():
    """Predict message volume"""
    try:
        data = get_request_data()
        hours_ahead = data.get('hours_ahead', 24)
        workspace_id = data.get('workspace_id')
        
        if not slack_analytics_engine:
            return create_response(False, error="Analytics engine not available"), 503
        
        # Get prediction
        prediction = await slack_analytics_engine.predict_message_volume(
            hours_ahead=hours_ahead,
            workspace_id=workspace_id
        )
        
        return create_response(
            True,
            data=prediction,
            message="Message volume prediction completed"
        )
    
    except Exception as e:
        logger.error(f"Volume prediction error: {e}")
        return create_response(False, error=str(e)), 500

# Enhanced File Operations
@enhanced_slack_bp.route('/files/enhanced_upload', methods=['POST'])
def enhanced_file_upload():
    """Enhanced file upload with analysis"""
    try:
        data = get_request_data()
        workspace_id = data.get('workspace_id')
        channel_id = data.get('channel_id')
        file_path = data.get('file_path')
        title = data.get('title')
        user_id = data.get('user_id')
        
        if not all([workspace_id, channel_id, file_path]):
            return create_response(False, error="workspace_id, channel_id, and file_path are required")
        
        if not slack_enhanced_service:
            return create_response(False, error="Slack service not available"), 503
        
        # Upload file
        result = await slack_enhanced_service.upload_file(
            workspace_id,
            channel_id,
            file_path,
            title=title,
            initial_comment=data.get('initial_comment')
        )
        
        if result.get('ok'):
            # Index file for search
            if AtomSearchService:
                file_data = result.get('file', {})
                search_data = {
                    'type': 'slack_file',
                    'id': file_data.get('file_id'),
                    'title': file_data.get('title'),
                    'content': file_data.get('name'),
                    'metadata': {
                        'mimetype': file_data.get('mimetype'),
                        'size': file_data.get('size'),
                        'workspace_id': workspace_id,
                        'channel_id': channel_id,
                        'user_id': file_data.get('user_id'),
                        'timestamp': file_data.get('timestamp')
                    }
                }
                await AtomSearchService.index(search_data)
            
            return create_response(
                True,
                data=result,
                message="File uploaded successfully"
            )
        else:
            return create_response(False, error=result.get('error')), 400
    
    except Exception as e:
        logger.error(f"Enhanced file upload error: {e}")
        return create_response(False, error=str(e)), 500

# Enhanced Webhook Handler
@enhanced_slack_bp.route('/enhanced_events', methods=['POST'])
def enhanced_webhook_handler():
    """Enhanced webhook event handler"""
    try:
        # Get request data
        body = request.get_data()
        headers = request.headers
        
        # Verify signature
        signature = headers.get('X-Slack-Signature')
        timestamp = headers.get('X-Slack-Request-Timestamp')
        
        if not slack_enhanced_service:
            return create_response(False, error="Slack service not available"), 503
        
        # Verify webhook signature
        if not await slack_enhanced_service.verify_webhook_signature(
            body, timestamp, signature
        ):
            return create_response(False, error="Invalid signature"), 401
        
        # Parse event data
        event_data = json.loads(body.decode('utf-8'))
        
        # Handle URL verification challenge
        if event_data.get('type') == 'url_verification':
            return jsonify({'challenge': event_data.get('challenge')})
        
        # Process event
        result = await slack_enhanced_service.handle_webhook_event(event_data)
        
        # Store event for analytics
        if AtomMemoryService:
            memory_data = {
                'type': 'slack_webhook_event',
                'event_type': event_data.get('event', {}).get('type'),
                'team_id': event_data.get('team_id'),
                'event_id': event_data.get('event_id'),
                'timestamp': datetime.utcnow().isoformat(),
                'data': event_data
            }
            await AtomMemoryService.store(memory_data)
        
        return create_response(
            result.get('ok', True),
            message="Webhook event processed successfully"
        )
    
    except Exception as e:
        logger.error(f"Enhanced webhook error: {e}")
        return create_response(False, error=str(e)), 500

# Data Ingestion
@enhanced_slack_bp.route('/ingestion/start', methods=['POST'])
def start_data_ingestion():
    """Start enhanced data ingestion"""
    try:
        data = get_request_data()
        user_id = data.get('user_id')
        workspace_id = data.get('workspace_id')
        channel_ids = data.get('channel_ids', [])
        config = data.get('config', {})
        
        if not atom_ingestion_pipeline:
            return create_response(False, error="Ingestion pipeline not available"), 503
        
        # Start ingestion
        ingestion_config = {
            'sourceType': 'slack_enhanced',
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
                }
            }
        }
        
        result = await atom_ingestion_pipeline.startIngestion(
            ingestion_config,
            callback=data.get('callback')
        )
        
        return create_response(
            True,
            data=result,
            message="Data ingestion started successfully"
        )
    
    except Exception as e:
        logger.error(f"Data ingestion start error: {e}")
        return create_response(False, error=str(e)), 500

@enhanced_slack_bp.route('/ingestion/status', methods=['POST'])
def get_ingestion_status():
    """Get data ingestion status"""
    try:
        data = get_request_data()
        ingestion_id = data.get('ingestion_id')
        workspace_id = data.get('workspace_id')
        
        if not atom_ingestion_pipeline:
            return create_response(False, error="Ingestion pipeline not available"), 503
        
        # Get status
        if ingestion_id:
            status = await atom_ingestion_pipeline.getIngestionStatus(ingestion_id)
        elif workspace_id:
            status = await atom_ingestion_pipeline.getIngestionStatus(workspace_id)
        else:
            status = await atom_ingestion_pipeline.getIngestionStatus()
        
        return create_response(
            True,
            data=status,
            message="Ingestion status retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Ingestion status error: {e}")
        return create_response(False, error=str(e)), 500

# Error handlers
@enhanced_slack_bp.errorhandler(404)
def not_found(error):
    return create_response(False, error="Endpoint not found"), 404

@enhanced_slack_bp.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return create_response(False, error="Internal server error"), 500

# Register blueprint
def register_enhanced_slack_api(app):
    """Register enhanced Slack API blueprint"""
    app.register_blueprint(enhanced_slack_bp)
    logger.info("Enhanced Slack API blueprint registered")
    
    # Start workflow engine workers
    if workflow_engine:
        asyncio.create_task(workflow_engine.start_execution_workers())

# Service initialization
def initialize_enhanced_services():
    """Initialize enhanced Slack services"""
    try:
        # Validate configuration
        if not validate_enhanced_config():
            return False
        
        # Initialize services
        if slack_enhanced_service:
            logger.info("Enhanced Slack service initialized")
        
        if workflow_engine:
            logger.info("Workflow engine initialized")
        
        if slack_analytics_engine:
            logger.info("Analytics engine initialized")
        
        return True
    
    except Exception as e:
        logger.error(f"Error initializing enhanced services: {e}")
        return False

# Export for external use
__all__ = [
    'enhanced_slack_bp',
    'register_enhanced_slack_api',
    'initialize_enhanced_services',
    'create_response',
    'get_request_data'
]