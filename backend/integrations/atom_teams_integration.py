"""
ATOM Teams Integration Module
Integrates Microsoft Teams seamlessly into ATOM's Communication ecosystem
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum

# Import existing ATOM services
try:
    from atom_memory_service import AtomMemoryService
    from atom_search_service import AtomSearchService
    from atom_workflow_service import AtomWorkflowService
    from atom_ingestion_pipeline import AtomIngestionPipeline
    from teams_enhanced_service import teams_enhanced_service, TeamsWorkspace, TeamsChannel, TeamsMessage, TeamsFile
    from teams_analytics_engine import teams_analytics_engine
except ImportError as e:
    logging.warning(f"Teams integration services not available: {e}")

logger = logging.getLogger(__name__)

class AtomTeamsIntegration:
    """Main integration class for Microsoft Teams within ATOM ecosystem"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.atom_memory = config.get('atom_memory_service')
        self.atom_search = config.get('atom_search_service')
        self.atom_workflow = config.get('atom_workflow_service')
        self.atom_ingestion = config.get('atom_ingestion_pipeline')
        
        # Teams services
        self.teams_service = teams_enhanced_service
        self.teams_analytics = teams_analytics_engine
        
        # Integration state
        self.is_initialized = False
        self.active_workspaces: List[TeamsWorkspace] = []
        self.communication_channels: List[Dict[str, Any]] = []
        self.unified_messages: List[Dict[str, Any]] = []
        
        logger.info("ATOM Teams Integration initialized")
    
    async def initialize(self) -> bool:
        """Initialize Teams integration with ATOM services"""
        try:
            if not all([self.teams_service, self.atom_memory, self.atom_search]):
                logger.error("Required services not available for Teams integration")
                return False
            
            # Start integration workers
            await self._start_integration_workers()
            
            # Initialize unified data structures
            await self._initialize_unified_data()
            
            # Setup event handlers for cross-platform communication
            await self._setup_cross_platform_handlers()
            
            self.is_initialized = True
            logger.info("Teams integration with ATOM ecosystem initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing Teams integration: {e}")
            return False
    
    async def get_unified_workspaces(self, user_id: str) -> List[Dict[str, Any]]:
        """Get unified workspaces across all platforms including Teams"""
        try:
            # Get Teams workspaces
            teams_workspaces = await self.teams_service.get_workspaces(user_id)
            
            # Transform to unified format
            unified_workspaces = []
            
            for workspace in teams_workspaces:
                unified_workspace = {
                    'id': f"teams_{workspace.team_id}",
                    'name': workspace.display_name,
                    'type': 'microsoft_teams',
                    'platform': 'Microsoft Teams',
                    'status': 'connected' if workspace.is_active else 'disconnected',
                    'member_count': workspace.member_count,
                    'channel_count': workspace.channel_count,
                    'icon_url': 'https://static.squarespace.com/static/55f4f1e6e4b0c5255b878c8/t/5c96395219aefae371f52257/1552750239451/Teams_logo.png',
                    'integration_data': {
                        'team_id': workspace.team_id,
                        'tenant_id': workspace.tenant_id,
                        'visibility': workspace.visibility,
                        'web_url': workspace.web_url,
                        'last_sync': workspace.last_sync.isoformat() if workspace.last_sync else None
                    },
                    'capabilities': {
                        'messaging': True,
                        'voice_calls': True,
                        'video_calls': True,
                        'screen_sharing': True,
                        'file_sharing': True,
                        'meetings': True,
                        'workflows': True,
                        'analytics': True
                    }
                }
                unified_workspaces.append(unified_workspace)
            
            # Store in active workspaces
            self.active_workspaces = teams_workspaces
            
            return unified_workspaces
            
        except Exception as e:
            logger.error(f"Error getting unified Teams workspaces: {e}")
            return []
    
    async def get_unified_channels(self, workspace_id: str, user_id: str = None) -> List[Dict[str, Any]]:
        """Get unified channels across platforms for given workspace"""
        try:
            # Extract Teams workspace ID from unified workspace ID
            if workspace_id.startswith('teams_'):
                teams_workspace_id = workspace_id[6:]  # Remove 'teams_' prefix
            else:
                return []
            
            # Get Teams channels
            teams_channels = await self.teams_service.get_channels(
                teams_workspace_id,
                user_id,
                include_private=True,
                include_archived=False
            )
            
            # Transform to unified format
            unified_channels = []
            
            for channel in teams_channels:
                unified_channel = {
                    'id': f"teams_{channel.channel_id}",
                    'name': channel.display_name,
                    'display_name': channel.display_name,
                    'description': channel.description,
                    'type': channel.channel_type,
                    'platform': 'Microsoft Teams',
                    'workspace_id': workspace_id,
                    'workspace_name': channel.workspaceName,
                    'status': 'active' if not channel.is_archived else 'archived',
                    'member_count': channel.member_count,
                    'message_count': channel.message_count,
                    'unread_count': channel.unreadCount or 0,
                    'last_activity': channel.lastActivityAt.isoformat() if channel.lastActivityAt else None,
                    'is_private': channel.channelType == 'private',
                    'is_muted': channel.isMuted or False,
                    'integration_data': {
                        'channel_id': channel.channel_id,
                        'membership_type': channel.membership_type,
                        'email': channel.email,
                        'web_url': channel.webUrl,
                        'allow_cross_team_posts': channel.allowCrossTeamPosts
                    },
                    'capabilities': {
                        'messaging': True,
                        'file_sharing': True,
                        'voice_calls': True,
                        'video_calls': True,
                        'meetings': True,
                        'workflows': True
                    }
                }
                unified_channels.append(unified_channel)
            
            # Store in communication channels
            self.communication_channels.extend(unified_channels)
            
            return unified_channels
            
        except Exception as e:
            logger.error(f"Error getting unified Teams channels: {e}")
            return []
    
    async def send_unified_message(self, workspace_id: str, channel_id: str, 
                                 content: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send unified message across platforms including Teams"""
        try:
            options = options or {}
            
            # Check if this is a Teams channel
            if channel_id.startswith('teams_'):
                teams_channel_id = channel_id[6:]  # Remove 'teams_' prefix
                teams_workspace_id = workspace_id[6:] if workspace_id.startswith('teams_') else None
                
                if not teams_workspace_id:
                    raise ValueError("Invalid workspace ID for Teams")
                
                # Send Teams message with enhanced options
                teams_result = await self.teams_service.send_message(
                    teams_workspace_id,
                    teams_channel_id,
                    content,
                    thread_id=options.get('thread_id'),
                    importance=options.get('importance', 'normal'),
                    subject=options.get('subject'),
                    attachments=options.get('attachments', [])
                )
                
                if teams_result.get('ok'):
                    # Store in unified memory
                    await self._store_message_in_memory(teams_result, 'teams', options)
                    
                    # Index in unified search
                    await self._index_message_in_search(teams_result, 'teams', options)
                    
                    # Trigger workflows if needed
                    await self._trigger_workflows(teams_result, 'teams_message_sent', options)
                    
                    return {
                        'ok': True,
                        'message_id': teams_result.get('message_id'),
                        'platform': 'Microsoft Teams',
                        'timestamp': datetime.utcnow().isoformat(),
                        'channel_id': channel_id,
                        'workspace_id': workspace_id
                    }
                else:
                    return teams_result
            
            # For non-Teams channels, would handle other platforms here
            else:
                return {'ok': False, 'error': 'Unsupported platform'}
            
        except Exception as e:
            logger.error(f"Error sending unified Teams message: {e}")
            return {'ok': False, 'error': str(e)}
    
    async def get_unified_messages(self, workspace_id: str, channel_id: str,
                                limit: int = 100, options: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get unified messages across platforms including Teams"""
        try:
            options = options or {}
            unified_messages = []
            
            # Check if this is a Teams channel
            if channel_id.startswith('teams_'):
                teams_channel_id = channel_id[6:]  # Remove 'teams_' prefix
                teams_workspace_id = workspace_id[6:] if workspace_id.startswith('teams_') else None
                
                if not teams_workspace_id:
                    return []
                
                # Get Teams messages
                teams_messages = await self.teams_service.get_channel_messages(
                    teams_workspace_id,
                    teams_channel_id,
                    limit=limit,
                    latest=options.get('latest'),
                    oldest=options.get('oldest')
                )
                
                # Transform to unified format
                for message in teams_messages:
                    unified_message = {
                        'id': f"teams_{message.message_id}",
                        'content': message.text,
                        'html_content': message.html,
                        'platform': 'Microsoft Teams',
                        'workspace_id': workspace_id,
                        'channel_id': channel_id,
                        'user_id': f"teams_{message.userId}",
                        'user_name': message.userName,
                        'user_email': message.userEmail,
                        'user_avatar': f"https://ui-avatars.com/api/?name={message.userName}&background=random",
                        'timestamp': message.timestamp,
                        'thread_id': f"teams_{message.threadId}" if message.threadId else None,
                        'reply_to_id': f"teams_{message.replyToId}" if message.replyToId else None,
                        'message_type': message.messageType,
                        'importance': message.importance,
                        'subject': message.subject,
                        'is_edited': message.isEdited,
                        'edit_timestamp': message.editTimestamp,
                        'reactions': message.reactions,
                        'attachments': message.attachments,
                        'mentions': [
                            {
                                'id': mention.get('id'),
                                'name': mention.get('displayName') or mention.get('userPrincipalName'),
                                'type': 'user',
                                'platform': 'Microsoft Teams'
                            }
                            for mention in message.mentions
                        ],
                        'files': [
                            {
                                'id': file.get('id'),
                                'name': file.get('name'),
                                'type': 'teams_file',
                                'platform': 'Microsoft Teams',
                                'url': file.get('webUrl'),
                                'size': file.get('size', 0)
                            }
                            for file in message.files
                        ],
                        'integration_data': {
                            'message_id': message.message_id,
                            'user_id': message.userId,
                            'tenant_id': message.tenantId,
                            'etag': message.etag,
                            'channel_identity': message.channelIdentity,
                            'participant_count': message.participantCount
                        },
                        'metadata': {
                            'has_thread': bool(message.threadId),
                            'reply_count': len([msg for msg in teams_messages if msg.replyToId == message.message_id]),
                            'has_attachments': bool(message.attachments),
                            'has_mentions': bool(message.mentions),
                            'importance_level': {
                                'low': 1,
                                'normal': 2,
                                'high': 3,
                                'urgent': 4
                            }.get(message.importance, 2)
                        }
                    }
                    unified_messages.append(unified_message)
            
            # Store in unified messages
            self.unified_messages.extend(unified_messages)
            
            # Sort by timestamp (newest first)
            unified_messages.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return unified_messages[:limit]
            
        except Exception as e:
            logger.error(f"Error getting unified Teams messages: {e}")
            return []
    
    async def unified_search(self, query: str, workspace_id: str = None,
                          channel_id: str = None, options: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Perform unified search across platforms including Teams"""
        try:
            options = options or {}
            unified_results = []
            
            # Teams search
            if channel_id and channel_id.startswith('teams_'):
                teams_channel_id = channel_id[6:]
                teams_workspace_id = workspace_id[6:] if workspace_id and workspace_id.startswith('teams_') else None
                
                if teams_workspace_id:
                    teams_results = await self.teams_service.search_messages(
                        teams_workspace_id,
                        query,
                        channel_id=teams_channel_id,
                        user_id=options.get('user_id'),
                        limit=options.get('limit', 50)
                    )
                    
                    if teams_results.get('ok'):
                        for message in teams_results.get('messages', []):
                            unified_result = {
                                'id': f"teams_{message.message_id}",
                                'title': message.subject or f"Message from {message.userName}",
                                'content': message.text,
                                'platform': 'Microsoft Teams',
                                'workspace_id': workspace_id or f"teams_{message.tenantId}",
                                'channel_id': channel_id,
                                'user_id': f"teams_{message.userId}",
                                'user_name': message.userName,
                                'timestamp': message.timestamp,
                                'type': 'message',
                                'url': f"https://teams.microsoft.com/l/message/{message.message_id}/thread/{message.threadId}" if message.threadId else f"https://teams.microsoft.com/l/message/{message.message_id}",
                                'relevance_score': message.metadata.get('search_score', 1.0) if hasattr(message, 'metadata') else 1.0,
                                'highlights': self._generate_search_highlights(message.text, query),
                                'integration_data': {
                                    'message_id': message.message_id,
                                    'channel_name': message.channelIdentity.get('displayName') if hasattr(message, 'channelIdentity') else None,
                                    'importance': message.importance
                                }
                            }
                            unified_results.append(unified_result)
            
            # Add results from other platforms here...
            
            # Sort by relevance score
            unified_results.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            return unified_results[:options.get('limit', 50)]
            
        except Exception as e:
            logger.error(f"Error in unified Teams search: {e}")
            return []
    
    async def create_unified_workflow(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create unified workflow that can operate across platforms including Teams"""
        try:
            # Check if workflow involves Teams
            teams_involved = False
            for trigger in workflow_data.get('triggers', []):
                if trigger.get('platform') == 'microsoft_teams' or 'teams' in trigger.get('event', '').lower():
                    teams_involved = True
                    break
            
            for action in workflow_data.get('actions', []):
                if action.get('platform') == 'microsoft_teams' or 'teams' in action.get('action', '').lower():
                    teams_involved = True
                    break
            
            if not teams_involved:
                # Workflow doesn't involve Teams, handle through standard workflow service
                if self.atom_workflow:
                    return await self.atom_workflow.create_workflow(workflow_data)
                else:
                    return {'ok': False, 'error': 'Workflow service not available'}
            
            # Create Teams-specific workflow
            if teams_workflow_engine:  # Would import from teams_workflow_engine
                teams_workflow = TeamsWorkflow(
                    id=f"teams_workflow_{int(datetime.utcnow().timestamp())}",
                    name=workflow_data['name'],
                    description=workflow_data.get('description', ''),
                    triggers=[
                        TeamsWorkflowTrigger(**trigger_data)
                        for trigger_data in workflow_data.get('triggers', [])
                        if trigger_data.get('platform') == 'microsoft_teams'
                    ],
                    actions=[
                        TeamsWorkflowAction(**action_data)
                        for action_data in workflow_data.get('actions', [])
                        if action_data.get('platform') == 'microsoft_teams'
                    ],
                    created_by=workflow_data.get('created_by', 'system'),
                    created_at=datetime.utcnow(),
                    category=workflow_data.get('category', 'teams'),
                    tags=workflow_data.get('tags', [])
                )
                
                # Register workflow
                success = teams_workflow_engine.register_workflow(teams_workflow)
                
                if success:
                    return {
                        'ok': True,
                        'workflow_id': teams_workflow.id,
                        'platform': 'microsoft_teams',
                        'message': 'Teams workflow created successfully'
                    }
                else:
                    return {'ok': False, 'error': 'Failed to create Teams workflow'}
            else:
                return {'ok': False, 'error': 'Teams workflow engine not available'}
            
        except Exception as e:
            logger.error(f"Error creating unified Teams workflow: {e}")
            return {'ok': False, 'error': str(e)}
    
    async def get_unified_analytics(self, metric: str, time_range: str,
                                 workspace_id: str = None, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get unified analytics across platforms including Teams"""
        try:
            options = options or {}
            
            # Get Teams analytics
            teams_analytics = await self.teams_analytics.get_analytics(
                metric=metric,
                time_range=time_range,
                workspace_id=workspace_id[6:] if workspace_id and workspace_id.startswith('teams_') else None,
                filters=options.get('filters', {})
            )
            
            # Transform to unified format
            unified_analytics = {
                'platform': 'Microsoft Teams',
                'metric': metric,
                'time_range': time_range,
                'workspace_id': workspace_id,
                'data_points': [
                    {
                        'timestamp': point.timestamp.isoformat(),
                        'value': point.value,
                        'dimensions': point.dimensions,
                        'metadata': point.metadata
                    }
                    for point in teams_analytics
                ],
                'total_points': len(teams_analytics)
            }
            
            # Add analytics from other platforms here...
            
            return unified_analytics
            
        except Exception as e:
            logger.error(f"Error getting unified Teams analytics: {e}")
            return {'ok': False, 'error': str(e)}
    
    # Private helper methods
    async def _start_integration_workers(self):
        """Start background integration workers"""
        # Start Teams message ingestion worker
        asyncio.create_task(self._teams_message_ingestion_worker())
        
        # Start Teams event processing worker
        asyncio.create_task(self._teams_event_processing_worker())
        
        # Start unified search indexing worker
        asyncio.create_task(self._unified_search_indexing_worker())
    
    async def _initialize_unified_data(self):
        """Initialize unified data structures"""
        # Load existing data from memory service
        if self.atom_memory:
            try:
                # Load unified workspaces
                workspaces_data = await self.atom_memory.query({
                    'type': 'unified_workspace',
                    'platform': 'microsoft_teams'
                })
                
                # Load unified channels
                channels_data = await self.atom_memory.query({
                    'type': 'unified_channel',
                    'platform': 'microsoft_teams'
                })
                
                # Load unified messages
                messages_data = await self.atom_memory.query({
                    'type': 'unified_message',
                    'platform': 'microsoft_teams'
                })
                
                logger.info(f"Loaded unified Teams data: {len(workspaces_data)} workspaces, {len(channels_data)} channels, {len(messages_data)} messages")
                
            except Exception as e:
                logger.error(f"Error loading unified Teams data: {e}")
    
    async def _setup_cross_platform_handlers(self):
        """Setup cross-platform event handlers"""
        # Setup Teams event handlers that integrate with other platforms
        
        # Example: When a Teams message is sent, also notify in Slack if configured
        if self.teams_service:
            self.teams_service.event_handlers[TeamsEventType.MESSAGE].append(
                self._handle_teams_message_cross_platform
            )
            
            self.teams_service.event_handlers[TeamsEventType.FILE_UPLOAD].append(
                self._handle_teams_file_cross_platform
            )
            
            self.teams_service.event_handlers[TeamsEventType.USER_JOIN].append(
                self._handle_teams_user_event_cross_platform
            )
    
    async def _handle_teams_message_cross_platform(self, event_data: Dict[str, Any]):
        """Handle Teams message cross-platform integration"""
        try:
            # Store in unified memory
            await self._store_message_in_memory(event_data, 'teams')
            
            # Index in unified search
            await self._index_message_in_search(event_data, 'teams')
            
            # Trigger cross-platform workflows
            await self._trigger_workflows(event_data, 'teams_message_cross_platform')
            
        except Exception as e:
            logger.error(f"Error handling Teams message cross-platform: {e}")
    
    async def _handle_teams_file_cross_platform(self, event_data: Dict[str, Any]):
        """Handle Teams file cross-platform integration"""
        try:
            # Index file in unified search
            await self._index_file_in_search(event_data, 'teams')
            
            # Store file metadata in unified memory
            await self._store_file_in_memory(event_data, 'teams')
            
            # Trigger file workflows
            await self._trigger_workflows(event_data, 'teams_file_cross_platform')
            
        except Exception as e:
            logger.error(f"Error handling Teams file cross-platform: {e}")
    
    async def _handle_teams_user_event_cross_platform(self, event_data: Dict[str, Any]):
        """Handle Teams user event cross-platform integration"""
        try:
            # Update unified user profile
            await self._update_user_profile_cross_platform(event_data, 'teams')
            
            # Trigger user event workflows
            await self._trigger_workflows(event_data, 'teams_user_event_cross_platform')
            
        except Exception as e:
            logger.error(f"Error handling Teams user event cross-platform: {e}")
    
    async def _store_message_in_memory(self, message_data: Dict[str, Any], platform: str, options: Dict[str, Any] = None):
        """Store message in unified ATOM memory"""
        try:
            if not self.atom_memory:
                return
            
            memory_data = {
                'type': 'unified_message',
                'platform': platform,
                'message_id': message_data.get('message_id'),
                'content': message_data.get('text') or message_data.get('content', ''),
                'html_content': message_data.get('html'),
                'user_id': message_data.get('user_id'),
                'user_name': message_data.get('user_name'),
                'user_email': message_data.get('user_email'),
                'channel_id': message_data.get('channel_id'),
                'workspace_id': message_data.get('workspace_id'),
                'timestamp': message_data.get('timestamp') or datetime.utcnow().isoformat(),
                'importance': message_data.get('importance', 'normal'),
                'subject': message_data.get('subject'),
                'thread_id': message_data.get('thread_id'),
                'reactions': message_data.get('reactions', []),
                'attachments': message_data.get('attachments', []),
                'mentions': message_data.get('mentions', []),
                'files': message_data.get('files', []),
                'integration_data': message_data,
                'options': options or {},
                'indexed': False,
                'synced': True
            }
            
            await self.atom_memory.store(memory_data)
            
        except Exception as e:
            logger.error(f"Error storing Teams message in unified memory: {e}")
    
    async def _index_message_in_search(self, message_data: Dict[str, Any], platform: str, options: Dict[str, Any] = None):
        """Index message in unified ATOM search"""
        try:
            if not self.atom_search:
                return
            
            search_data = {
                'type': 'unified_message',
                'platform': platform,
                'id': f"{platform}_{message_data.get('message_id')}",
                'title': message_data.get('subject') or f"Message from {message_data.get('user_name', 'Unknown')}",
                'content': message_data.get('text') or message_data.get('content', ''),
                'metadata': {
                    'user_id': message_data.get('user_id'),
                    'user_name': message_data.get('user_name'),
                    'user_email': message_data.get('user_email'),
                    'channel_id': message_data.get('channel_id'),
                    'workspace_id': message_data.get('workspace_id'),
                    'timestamp': message_data.get('timestamp') or datetime.utcnow().isoformat(),
                    'importance': message_data.get('importance', 'normal'),
                    'platform': platform,
                    'has_thread': bool(message_data.get('thread_id')),
                    'has_attachments': bool(message_data.get('attachments')),
                    'has_mentions': bool(message_data.get('mentions')),
                    'integration_data': message_data
                }
            }
            
            await self.atom_search.index(search_data)
            
        except Exception as e:
            logger.error(f"Error indexing Teams message in unified search: {e}")
    
    async def _trigger_workflows(self, event_data: Dict[str, Any], event_type: str, options: Dict[str, Any] = None):
        """Trigger workflows for cross-platform events"""
        try:
            if not self.atom_workflow:
                return
            
            workflow_trigger = {
                'event_type': event_type,
                'platform': 'microsoft_teams',
                'data': event_data,
                'timestamp': datetime.utcnow().isoformat(),
                'options': options or {}
            }
            
            await self.atom_workflow.trigger_workflows(workflow_trigger)
            
        except Exception as e:
            logger.error(f"Error triggering workflows for Teams event: {e}")
    
    def _generate_search_highlights(self, content: str, query: str) -> List[str]:
        """Generate search highlights for Teams message content"""
        try:
            import re
            highlights = []
            
            # Simple highlight generation (would use more sophisticated algorithm in production)
            query_words = query.lower().split()
            words = content.split()
            
            for i, word in enumerate(words):
                if any(qword in word.lower() for qword in query_words):
                    # Get context around the match
                    start = max(0, i - 3)
                    end = min(len(words), i + 4)
                    context = ' '.join(words[start:end])
                    highlights.append(context)
            
            return list(set(highlights))[:3]  # Limit to 3 unique highlights
            
        except Exception:
            return []
    
    # Background workers
    async def _teams_message_ingestion_worker(self):
        """Background worker for Teams message ingestion"""
        while True:
            try:
                # Process Teams message queue
                # This would integrate with the ingestion pipeline
                await asyncio.sleep(30)  # Process every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in Teams message ingestion worker: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    async def _teams_event_processing_worker(self):
        """Background worker for Teams event processing"""
        while True:
            try:
                # Process Teams event queue
                # This would handle real-time Teams events
                await asyncio.sleep(10)  # Process every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in Teams event processing worker: {e}")
                await asyncio.sleep(30)  # Wait before retrying
    
    async def _unified_search_indexing_worker(self):
        """Background worker for unified search indexing"""
        while True:
            try:
                # Index unindexed Teams messages in unified search
                if self.atom_search and self.atom_memory:
                    unindexed_messages = await self.atom_memory.query({
                        'type': 'unified_message',
                        'platform': 'microsoft_teams',
                        'indexed': False
                    })
                    
                    for message in unindexed_messages:
                        await self._index_message_in_search(message, 'teams')
                        await self.atom_memory.update(message['id'], {'indexed': True})
                
                await asyncio.sleep(60)  # Process every minute
                
            except Exception as e:
                logger.error(f"Error in unified search indexing worker: {e}")
                await asyncio.sleep(120)  # Wait before retrying

# Global Teams integration instance
atom_teams_integration = AtomTeamsIntegration({
    'atom_memory_service': None,  # Would be actual instance
    'atom_search_service': None,  # Would be actual instance
    'atom_workflow_service': None,  # Would be actual instance
    'atom_ingestion_pipeline': None  # Would be actual instance
})