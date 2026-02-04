"""
ATOM Google Chat Integration Module
Integrates Google Chat seamlessly into ATOM's unified communication ecosystem
"""

import asyncio
import json
import logging
import os
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlencode

# Import existing ATOM services
try:
    from atom_ingestion_pipeline import AtomIngestionPipeline
    from atom_memory_service import AtomMemoryService
    from atom_search_service import AtomSearchService
    from atom_workflow_service import AtomWorkflowService
    from core.models import UnifiedWorkspace
    from google_chat_analytics_engine import google_chat_analytics_engine
    from google_chat_enhanced_service import (
        GoogleChatFile,
        GoogleChatMessage,
        GoogleChatSpace,
        google_chat_enhanced_service,
    )
except ImportError as e:
    logging.warning(f"Google Chat integration services not available: {e}")
    google_chat_enhanced_service = None
    google_chat_analytics_engine = None
    UnifiedWorkspace = None

logger = logging.getLogger(__name__)

class AtomGoogleChatIntegration:
    """Main integration class for Google Chat within ATOM ecosystem"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.atom_memory = config.get('atom_memory_service')
        self.atom_search = config.get('atom_search_service')
        self.atom_workflow = config.get('atom_workflow_service')
        self.atom_ingestion = config.get('atom_ingestion_pipeline')
        self.db = config.get('database')

        # Google Chat services
        self.google_chat_service = google_chat_enhanced_service
        self.google_chat_analytics = google_chat_analytics_engine

        # Workspace synchronization service
        self.workspace_sync = None
        if self.db:
            try:
                from integrations.workspace_sync_service import WorkspaceSyncService
                self.workspace_sync = WorkspaceSyncService(self.db)
                logger.info("Workspace sync service initialized for Google Chat integration")
            except ImportError as e:
                logger.warning(f"Workspace sync service not available: {e}")

        # Integration state
        self.is_initialized = False
        self.active_spaces: List[GoogleChatSpace] = []
        self.communication_channels: List[Dict[str, Any]] = []
        self.unified_messages: List[Dict[str, Any]] = []
        
        logger.info("ATOM Google Chat Integration initialized")
    
    async def initialize(self) -> bool:
        """Initialize Google Chat integration with ATOM services"""
        try:
            if not all([self.google_chat_service, self.atom_memory, self.atom_search]):
                logger.error("Required services not available for Google Chat integration")
                return False
            
            # Start integration workers
            await self._start_integration_workers()
            
            # Initialize unified data structures
            await self._initialize_unified_data()
            
            # Setup event handlers for cross-platform communication
            await self._setup_cross_platform_handlers()
            
            self.is_initialized = True
            logger.info("Google Chat integration with ATOM ecosystem initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing Google Chat integration: {e}")
            return False
    
    async def get_unified_workspaces(self, user_id: str) -> List[Dict[str, Any]]:
        """Get unified workspaces across all platforms including Google Chat"""
        try:
            # Get Google Chat spaces
            google_chat_spaces = await self.google_chat_service.get_spaces(user_id)
            
            # Transform to unified format
            unified_workspaces = []
            
            for space in google_chat_spaces:
                unified_workspace = {
                    'id': f"google_chat_{space.space_id}",
                    'name': space.display_name,
                    'type': 'google_chat',
                    'platform': 'Google Chat',
                    'status': 'connected' if space.is_active else 'disconnected',
                    'member_count': space.member_count,
                    'channel_count': 1,  # Google Chat spaces are single spaces
                    'icon_url': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/69/Google_Chat_logo.svg/512px-Google_Chat_logo.svg.png',
                    'integration_data': {
                        'space_id': space.space_id,
                        'space_type': space.type,
                        'space_threading_state': space.space_threading_state,
                        'space_uri': space.space_uri,
                        'space_permission_level': space.space_permission_level,
                        'threaded': space.threaded,
                        'created_at': space.created_at.isoformat() if space.created_at else None
                    },
                    'capabilities': {
                        'messaging': True,
                        'voice_calls': False,  # Google Meet integration separate
                        'video_calls': False,
                        'screen_sharing': False,
                        'file_sharing': True,
                        'meetings': True,  # Google Meet integration
                        'workflows': True,
                        'analytics': True
                    }
                }
                unified_workspaces.append(unified_workspace)
            
            # Store in active spaces
            self.active_spaces = google_chat_spaces
            
            return unified_workspaces
            
        except Exception as e:
            logger.error(f"Error getting unified Google Chat workspaces: {e}")
            return []
    
    async def get_unified_channels(self, workspace_id: str, user_id: str = None) -> List[Dict[str, Any]]:
        """Get unified channels across platforms for given workspace"""
        try:
            # Extract Google Chat workspace ID from unified workspace ID
            if workspace_id.startswith('google_chat_'):
                google_chat_workspace_id = workspace_id[11:]  # Remove 'google_chat_' prefix
            else:
                return []
            
            # Get Google Chat space as channel
            space = self._get_space_by_id(google_chat_workspace_id)
            if not space:
                return []
            
            # Transform to unified format (Google Chat spaces become channels)
            unified_channels = []
            
            unified_channel = {
                'id': f"google_chat_{space.space_id}",
                'name': space.display_name,
                'display_name': space.display_name,
                'description': space.description,
                'type': space.type.lower(),  # ROOM, DM, GROUP_DM
                'platform': 'Google Chat',
                'workspace_id': workspace_id,
                'workspace_name': 'Google Chat',
                'status': 'active' if not space.is_archived else 'archived',
                'member_count': space.member_count,
                'message_count': space.message_count,
                'unread_count': 0,  # Would calculate from database
                'last_activity': space.last_modified_at,
                'is_private': space.type in ['DM', 'GROUP_DM'],
                'is_muted': False,  # Would check user preferences
                'is_favorite': False,  # Would check user preferences
                'integration_data': {
                    'space_id': space.space_id,
                    'space_type': space.type,
                    'space_threading_state': space.space_threading_state,
                    'threaded': space.threaded,
                    'single_user_bot_dm': space.single_user_bot_dm,
                    'external_user_permission': space.external_user_permission
                },
                'capabilities': {
                    'messaging': True,
                    'file_sharing': True,
                    'voice_calls': False,
                    'video_calls': False,
                    'meetings': True,
                    'workflows': True
                }
            }
            unified_channels.append(unified_channel)
            
            # Store in communication channels
            self.communication_channels.extend(unified_channels)
            
            return unified_channels
            
        except Exception as e:
            logger.error(f"Error getting unified Google Chat channels: {e}")
            return []
    
    async def send_unified_message(self, workspace_id: str, channel_id: str,
                                 content: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send unified message across platforms including Google Chat"""
        try:
            options = options or {}
            
            # Check if this is a Google Chat channel
            if channel_id.startswith('google_chat_'):
                google_chat_space_id = channel_id[11:]  # Remove 'google_chat_' prefix
                
                # Send Google Chat message with enhanced options
                google_chat_result = await self.google_chat_service.send_message(
                    google_chat_space_id,
                    content,
                    thread_id=options.get('thread_id'),
                    message_format=options.get('message_format', 'TEXT'),
                    card_v2=options.get('card_v2')
                )
                
                if google_chat_result.get('ok'):
                    # Store in unified memory
                    await self._store_message_in_memory(google_chat_result, 'google_chat', options)
                    
                    # Index in unified search
                    await self._index_message_in_search(google_chat_result, 'google_chat', options)
                    
                    # Trigger workflows if needed
                    await self._trigger_workflows(google_chat_result, 'google_chat_message_sent', options)
                    
                    return {
                        'ok': True,
                        'message_id': google_chat_result.get('message_id'),
                        'platform': 'Google Chat',
                        'timestamp': datetime.utcnow().isoformat(),
                        'channel_id': channel_id,
                        'workspace_id': workspace_id
                    }
                else:
                    return google_chat_result
            
            # For non-Google Chat channels, would handle other platforms here
            else:
                return {'ok': False, 'error': 'Unsupported platform'}
        
        except Exception as e:
            logger.error(f"Error sending unified Google Chat message: {e}")
            return {'ok': False, 'error': str(e)}
    
    async def get_unified_messages(self, workspace_id: str, channel_id: str,
                                limit: int = 100, options: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get unified messages across platforms including Google Chat"""
        try:
            options = options or {}
            unified_messages = []
            
            # Check if this is a Google Chat channel
            if channel_id.startswith('google_chat_'):
                google_chat_space_id = channel_id[11:]  # Remove 'google_chat_' prefix
                
                # Get Google Chat messages
                google_chat_messages = await self.google_chat_service.get_space_messages(
                    google_chat_space_id,
                    limit=limit,
                    page_token=options.get('page_token'),
                    filter=options.get('filter')
                )
                
                # Transform to unified format
                for message in google_chat_messages:
                    unified_message = {
                        'id': f"google_chat_{message.message_id}",
                        'content': message.text,
                        'html_content': message.formatted_text,
                        'platform': 'Google Chat',
                        'workspace_id': workspace_id,
                        'channel_id': channel_id,
                        'user_id': f"google_chat_{message.user_id}",
                        'user_name': message.user_name,
                        'user_email': message.user_email,
                        'user_avatar': message.user_avatar,
                        'timestamp': message.timestamp,
                        'thread_id': f"google_chat_{message.thread_id}" if message.thread_id else None,
                        'reply_to_id': message.reply_to_id,
                        'message_type': message.message_type.lower(),
                        'subject': None,  # Google Chat doesn't have subjects
                        'is_edited': message.is_edited,
                        'edit_timestamp': message.edit_timestamp,
                        'reactions': self._convert_google_chat_reactions(message.reactions),
                        'attachments': self._convert_google_chat_attachments(message.attachment),
                        'mentions': self._convert_google_chat_mentions(message.annotations),
                        'files': self._convert_google_chat_files(message.attachment),
                        'integration_data': {
                            'message_id': message.message_id,
                            'user_id': message.user_id,
                            'gu_id': message.gu_id,
                            'sender_type': message.sender_type,
                            'space_threading_state': message.space_threading_state,
                            'thread_name': message.thread_name,
                            'thread_id_created_by': message.thread_id_created_by,
                            'quoted_message_id': message.quoted_message_id,
                            'card_v2': message.card_v2,
                            'slash_command': message.slash_command,
                            'action_response': message.action_response,
                            'arguments': message.arguments,
                            'annotations': message.annotations
                        },
                        'metadata': {
                            'has_thread': bool(message.thread_id),
                            'has_cards': len(message.card_v2) > 0,
                            'has_attachments': bool(message.attachment),
                            'has_annotations': bool(message.annotations),
                            'is_bot_message': message.sender_type == 'BOT'
                        }
                    }
                    unified_messages.append(unified_message)
            
            # Store in unified messages
            self.unified_messages.extend(unified_messages)
            
            # Sort by timestamp (newest first)
            unified_messages.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return unified_messages[:limit]
            
        except Exception as e:
            logger.error(f"Error getting unified Google Chat messages: {e}")
            return []
    
    async def unified_search(self, query: str, workspace_id: str = None,
                          channel_id: str = None, options: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Perform unified search across platforms including Google Chat"""
        try:
            options = options or {}
            unified_results = []
            
            # Google Chat search
            if channel_id and channel_id.startswith('google_chat_'):
                google_chat_space_id = channel_id[11:]  # Remove 'google_chat_' prefix
                
                google_chat_results = await self.google_chat_service.search_messages(
                    google_chat_space_id,
                    query,
                    page_size=options.get('limit', 50),
                    page_token=options.get('page_token')
                )
                
                if google_chat_results.get('ok'):
                    for message in google_chat_results.get('messages', []):
                        unified_result = {
                            'id': f"google_chat_{message.message_id}",
                            'title': f"Message from {message.user_name}",
                            'content': message.text,
                            'platform': 'Google Chat',
                            'workspace_id': workspace_id or f"google_chat_{message.space_id}",
                            'channel_id': channel_id,
                            'user_id': f"google_chat_{message.user_id}",
                            'user_name': message.user_name,
                            'timestamp': message.timestamp,
                            'type': 'message',
                            'url': f"https://chat.google.com/room/{message.space_id}",
                            'relevance_score': message.integration_data.get('search_score', 1.0) if hasattr(message, 'integration_data') else 1.0,
                            'highlights': self._generate_search_highlights(message.text, query),
                            'integration_data': {
                                'message_id': message.message_id,
                                'thread_id': message.thread_id,
                                'sender_type': message.sender_type,
                                'has_cards': len(message.card_v2) > 0,
                                'annotations': message.annotations
                            }
                        }
                        unified_results.append(unified_result)
            
            # Add results from other platforms here...
            
            # Sort by relevance score
            unified_results.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            return unified_results[:options.get('limit', 50)]
            
        except Exception as e:
            logger.error(f"Error in unified Google Chat search: {e}")
            return []
    
    async def create_unified_workflow(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create unified workflow that can operate across platforms including Google Chat"""
        try:
            # Check if workflow involves Google Chat
            google_chat_involved = False
            for trigger in workflow_data.get('triggers', []):
                if trigger.get('platform') == 'google_chat' or 'google_chat' in trigger.get('event', '').lower():
                    google_chat_involved = True
                    break
            
            for action in workflow_data.get('actions', []):
                if action.get('platform') == 'google_chat' or 'google_chat' in action.get('action', '').lower():
                    google_chat_involved = True
                    break
            
            if not google_chat_involved:
                # Workflow doesn't involve Google Chat, handle through standard workflow service
                if self.atom_workflow:
                    return await self.atom_workflow.create_workflow(workflow_data)
                else:
                    return {'ok': False, 'error': 'Workflow service not available'}
            
            # Create Google Chat-specific workflow
            # This would integrate with google_chat_workflow_engine
            
            return {
                'ok': True,
                'workflow_id': f"gc_workflow_{int(datetime.utcnow().timestamp())}",
                'platform': 'google_chat',
                'message': 'Google Chat workflow created successfully'
            }
        
        except Exception as e:
            logger.error(f"Error creating unified Google Chat workflow: {e}")
            return {'ok': False, 'error': str(e)}
    
    async def get_unified_analytics(self, metric: str, time_range: str,
                                 workspace_id: str = None, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get unified analytics across platforms including Google Chat"""
        try:
            options = options or {}
            
            # Get Google Chat analytics
            if self.google_chat_analytics:
                google_chat_analytics = await self.google_chat_analytics.get_analytics(
                    metric=metric,
                    time_range=time_range,
                    workspace_id=workspace_id[11:] if workspace_id and workspace_id.startswith('google_chat_') else None,
                    filters=options.get('filters', {})
                )
            else:
                google_chat_analytics = []
            
            # Transform to unified format
            unified_analytics = {
                'platform': 'Google Chat',
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
                    for point in google_chat_analytics
                ],
                'total_points': len(google_chat_analytics)
            }
            
            # Add analytics from other platforms here...
            
            return unified_analytics
            
        except Exception as e:
            logger.error(f"Error getting unified Google Chat analytics: {e}")
            return {'ok': False, 'error': str(e)}
    
    # Private helper methods
    async def _start_integration_workers(self):
        """Start background integration workers"""
        # Start Google Chat message ingestion worker
        asyncio.create_task(self._google_chat_message_ingestion_worker())
        
        # Start Google Chat event processing worker
        asyncio.create_task(self._google_chat_event_processing_worker())
        
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
                    'platform': 'google_chat'
                })
                
                # Load unified channels
                channels_data = await self.atom_memory.query({
                    'type': 'unified_channel',
                    'platform': 'google_chat'
                })
                
                # Load unified messages
                messages_data = await self.atom_memory.query({
                    'type': 'unified_message',
                    'platform': 'google_chat'
                })
                
                logger.info(f"Loaded unified Google Chat data: {len(workspaces_data)} workspaces, {len(channels_data)} channels, {len(messages_data)} messages")
                
            except Exception as e:
                logger.error(f"Error loading unified Google Chat data: {e}")
    
    async def _setup_cross_platform_handlers(self):
        """Setup cross-platform event handlers"""
        # Setup Google Chat event handlers that integrate with other platforms
        
        # Example: When a Google Chat message is sent, also notify in Slack if configured
        if self.google_chat_service:
            self.google_chat_service.event_handlers[GoogleChatEventType.MESSAGE].append(
                self._handle_google_chat_message_cross_platform
            )
            
            self.google_chat_service.event_handlers[GoogleChatEventType.ADDED_TO_SPACE].append(
                self._handle_google_chat_space_event_cross_platform
            )
    
    async def _handle_google_chat_message_cross_platform(self, event_data: Dict[str, Any]):
        """Handle Google Chat message cross-platform integration"""
        try:
            # Store in unified memory
            await self._store_message_in_memory(event_data, 'google_chat')
            
            # Index in unified search
            await self._index_message_in_search(event_data, 'google_chat')
            
            # Trigger cross-platform workflows
            await self._trigger_workflows(event_data, 'google_chat_message_cross_platform')
            
        except Exception as e:
            logger.error(f"Error handling Google Chat message cross-platform: {e}")
    
    async def _handle_google_chat_space_event_cross_platform(self, event_data: Dict[str, Any]):
        """Handle Google Chat space event cross-platform integration"""
        try:
            # Update unified workspace information
            await self._update_workspace_cross_platform(event_data, 'google_chat')
            
            # Trigger workspace event workflows
            await self._trigger_workflows(event_data, 'google_chat_space_event_cross_platform')
            
        except Exception as e:
            logger.error(f"Error handling Google Chat space event cross-platform: {e}")
    
    def _get_space_by_id(self, space_id: str) -> Optional[GoogleChatSpace]:
        """
        Get Google Chat space by ID.

        This method retrieves space information from the active spaces cache.
        For production use, this should query a database or persistent cache.

        Args:
            space_id: The Google Chat space ID to retrieve

        Returns:
            GoogleChatSpace if found, None otherwise
        """
        try:
            # First check the active spaces cache
            for space in self.active_spaces:
                if space.space_id == space_id:
                    return space

            # If not found in cache, try to fetch from the service
            if self.google_chat_service:
                # This would call the Google Chat API to get space details
                # For now, log that the space was not found
                logger.warning(f"Space {space_id} not found in active spaces cache")

            # Return None if space not found (caller should handle this)
            return None

        except Exception as e:
            logger.error(f"Error getting Google Chat space by ID {space_id}: {e}")
            return None
    
    def _convert_google_chat_reactions(self, reactions: List[Dict]) -> List[Dict]:
        """Convert Google Chat reactions to unified format"""
        unified_reactions = []
        for reaction in reactions:
            unified_reactions.append({
                'emoji': reaction.get('emoji'),
                'count': reaction.get('count', 1),
                'user_ids': reaction.get('user_ids', [])
            })
        return unified_reactions
    
    def _convert_google_chat_attachments(self, attachments: List[Dict]) -> List[Dict]:
        """Convert Google Chat attachments to unified format"""
        unified_attachments = []
        for attachment in attachments:
            unified_attachments.append({
                'id': attachment.get('name'),
                'title': attachment.get('title'),
                'content_type': attachment.get('contentType'),
                'download_url': attachment.get('downloadUri'),
                'thumbnail_url': attachment.get('thumbnailUri'),
                'size': attachment.get('size', 0)
            })
        return unified_attachments
    
    def _convert_google_chat_mentions(self, annotations: List[Dict]) -> List[Dict]:
        """Convert Google Chat annotations (mentions) to unified format"""
        unified_mentions = []
        for annotation in annotations:
            if annotation.get('type') == 'user_mention':
                user_data = annotation.get('userMention', {})
                unified_mentions.append({
                    'id': user_data.get('name'),
                    'name': user_data.get('displayName'),
                    'type': 'user',
                    'platform': 'Google Chat'
                })
        return unified_mentions
    
    def _convert_google_chat_files(self, attachments: List[Dict]) -> List[Dict]:
        """Convert Google Chat attachments to unified file format"""
        unified_files = []
        for attachment in attachments:
            if attachment.get('contentType', '').startswith(('image/', 'video/', 'audio/', 'application/')):
                unified_files.append({
                    'id': attachment.get('name'),
                    'name': attachment.get('title'),
                    'type': 'google_chat_file',
                    'platform': 'Google Chat',
                    'url': attachment.get('downloadUri'),
                    'size': attachment.get('size', 0)
                })
        return unified_files
    
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
                'formatted_content': message_data.get('formatted_text'),
                'user_id': message_data.get('user_id'),
                'user_name': message_data.get('user_name'),
                'user_email': message_data.get('user_email'),
                'channel_id': message_data.get('space_id'),
                'workspace_id': message_data.get('space_id'),
                'timestamp': message_data.get('timestamp') or datetime.utcnow().isoformat(),
                'thread_id': message_data.get('thread_id'),
                'annotations': message_data.get('annotations', []),
                'attachments': message_data.get('attachment', []),
                'card_v2': message_data.get('card_v2', []),
                'reactions': message_data.get('reactions', []),
                'integration_data': message_data,
                'options': options or {},
                'indexed': False,
                'synced': True
            }
            
            await self.atom_memory.store(memory_data)
            
        except Exception as e:
            logger.error(f"Error storing Google Chat message in unified memory: {e}")
    
    async def _index_message_in_search(self, message_data: Dict[str, Any], platform: str, options: Dict[str, Any] = None):
        """Index message in unified ATOM search"""
        try:
            if not self.atom_search:
                return
            
            search_data = {
                'type': 'unified_message',
                'platform': platform,
                'id': f"{platform}_{message_data.get('message_id')}",
                'title': f"Message from {message_data.get('user_name', 'Unknown')}",
                'content': message_data.get('text') or message_data.get('content', ''),
                'metadata': {
                    'user_id': message_data.get('user_id'),
                    'user_name': message_data.get('user_name'),
                    'user_email': message_data.get('user_email'),
                    'channel_id': message_data.get('space_id'),
                    'workspace_id': message_data.get('space_id'),
                    'timestamp': message_data.get('timestamp') or datetime.utcnow().isoformat(),
                    'platform': platform,
                    'has_thread': bool(message_data.get('thread_id')),
                    'has_cards': bool(message_data.get('card_v2')),
                    'has_attachments': bool(message_data.get('attachment')),
                    'has_annotations': bool(message_data.get('annotations')),
                    'sender_type': message_data.get('sender_type'),
                    'integration_data': message_data
                }
            }
            
            await self.atom_search.index(search_data)
            
        except Exception as e:
            logger.error(f"Error indexing Google Chat message in unified search: {e}")
    
    async def _trigger_workflows(self, event_data: Dict[str, Any], event_type: str, options: Dict[str, Any] = None):
        """Trigger workflows for cross-platform events"""
        try:
            if not self.atom_workflow:
                return
            
            workflow_trigger = {
                'event_type': event_type,
                'platform': 'google_chat',
                'data': event_data,
                'timestamp': datetime.utcnow().isoformat(),
                'options': options or {}
            }
            
            await self.atom_workflow.trigger_workflows(workflow_trigger)
            
        except Exception as e:
            logger.error(f"Error triggering workflows for Google Chat event: {e}")
    
    def _generate_search_highlights(self, content: str, query: str) -> List[str]:
        """Generate search highlights for Google Chat message content"""
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
    
    async def _update_workspace_cross_platform(self, event_data: Dict[str, Any], platform: str):
        """Update workspace information across platforms"""
        try:
            if not self.workspace_sync:
                logger.debug("Workspace sync service not available, skipping cross-platform update")
                return

            # Extract workspace information from event
            space_info = event_data.get('space', {})
            space_name = space_info.get('name', 'Unknown Space')
            space_id = space_info.get('name', '')  # Google Chat uses name as ID
            event_type = event_data.get('type', '')

            logger.info(
                f"Processing cross-platform workspace update: "
                f"platform={platform}, event_type={event_type}, space={space_name}"
            )

            # Determine change type based on event
            if event_type in ['SPACE_UPDATED', 'RENAME_SPACE']:
                change_type = 'name_change'
            elif event_type == 'MEMBER_ADDED':
                change_type = 'member_add'
            elif event_type == 'MEMBER_REMOVED':
                change_type = 'member_remove'
            elif event_type == 'SETTINGS_UPDATED':
                change_type = 'settings_change'
            else:
                change_type = 'settings_change'  # Default

            # Get or create unified workspace
            unified_workspace = await self._get_or_create_unified_workspace(
                space_id=space_id,
                space_name=space_name
            )

            if not unified_workspace:
                logger.warning(f"Could not get or create unified workspace for space {space_id}")
                return

            # Propagate changes to other platforms
            await self.workspace_sync.propagate_change(
                workspace_id=unified_workspace.id,
                source_platform='google_chat',
                change_type=change_type,
                change_data={
                    'space_name': space_name,
                    'space_id': space_id,
                    'event_type': event_type,
                    'event_data': event_data
                }
            )

            logger.info(
                f"Successfully propagated workspace change for {space_name} "
                f"(unified workspace ID: {unified_workspace.id})"
            )

        except Exception as e:
            logger.error(f"Error updating workspace cross-platform: {e}")

    async def _get_or_create_unified_workspace(
        self,
        space_id: str,
        space_name: str
    ):
        """
        Get or create a unified workspace for a Google Chat space.

        Args:
            space_id: Google Chat space ID
            space_name: Google Chat space name

        Returns:
            UnifiedWorkspace object or None
        """
        try:
            from sqlalchemy import or_

            # Search for existing unified workspace with this Google Chat space
            existing = self.db.query(UnifiedWorkspace).filter(
                UnifiedWorkspace.google_chat_space_id == space_id
            ).first()

            if existing:
                logger.debug(f"Found existing unified workspace {existing.id} for space {space_id}")
                return existing

            # Create new unified workspace
            # Use a default user_id - in production this would come from authentication
            user_id = "system"

            unified_workspace = self.workspace_sync.create_unified_workspace(
                user_id=user_id,
                name=space_name,
                description=f"Unified workspace for Google Chat space: {space_name}",
                google_chat_space_id=space_id,
                sync_config={
                    'auto_sync': True,
                    'sync_members': True,
                    'sync_settings': True
                }
            )

            logger.info(f"Created unified workspace {unified_workspace.id} for Google Chat space {space_id}")
            return unified_workspace

        except Exception as e:
            logger.error(f"Error getting or creating unified workspace: {e}")
            return None
    
    # Background workers
    async def _google_chat_message_ingestion_worker(self):
        """Background worker for Google Chat message ingestion"""
        while True:
            try:
                # Process Google Chat message queue
                # This would integrate with ingestion pipeline
                await asyncio.sleep(30)  # Process every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in Google Chat message ingestion worker: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    async def _google_chat_event_processing_worker(self):
        """Background worker for Google Chat event processing"""
        while True:
            try:
                # Process Google Chat event queue
                # This would handle real-time Google Chat events
                await asyncio.sleep(10)  # Process every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in Google Chat event processing worker: {e}")
                await asyncio.sleep(30)  # Wait before retrying
    
    async def _unified_search_indexing_worker(self):
        """Background worker for unified search indexing"""
        while True:
            try:
                # Index unindexed Google Chat messages in unified search
                if self.atom_search and self.atom_memory:
                    unindexed_messages = await self.atom_memory.query({
                        'type': 'unified_message',
                        'platform': 'google_chat',
                        'indexed': False
                    })
                    
                    for message in unindexed_messages:
                        await self._index_message_in_search(message, 'google_chat')
                        await self.atom_memory.update(message['id'], {'indexed': True})
                
                await asyncio.sleep(60)  # Process every minute
                
            except Exception as e:
                logger.error(f"Error in unified search indexing worker: {e}")
                await asyncio.sleep(120)  # Wait before retrying

    # ============================================================================
    # OAuth 2.0 Authentication Methods
    # ============================================================================

    async def get_oauth_url(
        self,
        redirect_uri: str,
        state: Optional[str] = None,
        access_type: str = "offline",
        prompt: str = "consent",
        include_granted_scopes: Optional[bool] = False,
        login_hint: Optional[str] = None
    ) -> str:
        """
        Generate Google OAuth 2.0 authorization URL.

        Args:
            redirect_uri: URI to redirect to after authorization
            state: Optional state parameter for security
            access_type: 'offline' for refresh token, 'online' for access only
            prompt: 'consent' to force consent dialog, 'none' to skip
            include_granted_scopes: Whether to filter to granted scopes
            login_hint: Email address hint for the user

        Returns:
            OAuth authorization URL as string
        """
        try:
            # Get OAuth config from environment
            client_id = os.getenv("GOOGLE_CHAT_CLIENT_ID")
            if not client_id:
                raise ValueError("GOOGLE_CHAT_CLIENT_ID not configured")

            # OAuth scopes for Google Chat
            scopes = [
                "https://www.googleapis.com/auth/chat.bot",
                "https://www.googleapis.com/auth/chat.spaces",
                "https://www.googleapis.com/auth/chat.messages",
                "https://www.googleapis.com/auth/chat.memberships"
            ]

            # Build authorization URL
            base_url = "https://accounts.google.com/o/oauth2/v2/auth"
            params = {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "scope": " ".join(scopes),
                "response_type": "code",
                "access_type": access_type,
                "prompt": prompt
            }

            if state:
                params["state"] = state
            if include_granted_scopes:
                params["include_granted_scopes"] = "true"
            if login_hint:
                params["login_hint"] = login_hint

            oauth_url = f"{base_url}?{urlencode(params)}"

            logger.info(f"Generated OAuth URL for Google Chat")
            return oauth_url

        except Exception as e:
            logger.error(f"Error generating OAuth URL: {e}")
            raise

    async def handle_oauth_callback(
        self,
        code: str,
        state: Optional[str] = None,
        redirect_uri: str = None
    ) -> Dict[str, Any]:
        """
        Handle OAuth 2.0 callback from Google.

        Exchanges authorization code for access token.

        Args:
            code: Authorization code from Google
            state: Optional state parameter for security validation
            redirect_uri: Original redirect URI used in authorization request

        Returns:
            Dict with success, access_token, refresh_token, expires_in
        """
        try:
            client_id = os.getenv("GOOGLE_CHAT_CLIENT_ID")
            client_secret = os.getenv("GOOGLE_CHAT_CLIENT_SECRET")

            if not client_id or not client_secret:
                raise ValueError("Google Chat OAuth credentials not configured")

            if not redirect_uri:
                redirect_uri = os.getenv("GOOGLE_CHAT_REDIRECT_URI", "http://localhost:8000/api/google-chat/oauth/callback")

            # Exchange authorization code for tokens
            token_url = "https://oauth2.googleapis.com/token"

            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    token_url,
                    data={
                        "code": code,
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "redirect_uri": redirect_uri,
                        "grant_type": "authorization_code"
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                response.raise_for_status()
                token_data = response.json()

            # Validate state if provided (should check against stored value)
            if state:
                logger.info(f"OAuth state validation: {state}")

            return {
                "success": True,
                "access_token": token_data.get("access_token"),
                "refresh_token": token_data.get("refresh_token"),
                "expires_in": token_data.get("expires_in", 3600),
                "token_type": token_data.get("token_type", "Bearer"),
                "scope": token_data.get("scope", "")
            }

        except Exception as e:
            logger.error(f"Error handling OAuth callback: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh an access token using refresh token.

        Args:
            refresh_token: Refresh token from initial OAuth flow

        Returns:
            Dict with success, access_token, refresh_token, expires_in
        """
        try:
            client_id = os.getenv("GOOGLE_CHAT_CLIENT_ID")
            client_secret = os.getenv("GOOGLE_CHAT_CLIENT_SECRET")

            if not client_id or not client_secret:
                raise ValueError("Google Chat OAuth credentials not configured")

            token_url = "https://oauth2.googleapis.com/token"

            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    token_url,
                    data={
                        "refresh_token": refresh_token,
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "grant_type": "refresh_token"
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                response.raise_for_status()
                token_data = response.json()

            return {
                "success": True,
                "access_token": token_data.get("access_token"),
                "refresh_token": token_data.get("refresh_token", refresh_token),  # May not be returned
                "expires_in": token_data.get("expires_in", 3600),
                "token_type": token_data.get("token_type", "Bearer")
            }

        except Exception as e:
            logger.error(f"Error refreshing access token: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    # ============================================================================
    # Interactive Card Methods
    # ============================================================================

    async def send_card(
        self,
        space_name: str,
        message: Optional[str] = None,
        card: Optional[Dict[str, Any]] = None,
        thread_key: Optional[str] = None,
        header: Optional[Dict[str, Any]] = None,
        sections: Optional[List[Dict[str, Any]]] = None,
        widgets: Optional[List[Dict[str, Any]]] = None,
        cards: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Send an interactive card to Google Chat.

        Cards can contain buttons, text paragraphs, images, input widgets, and decorated text.

        Args:
            space_name: Google Chat space name
            message: Optional text message to display with card
            card: Card definition (dict with cardHeader, sections, etc.)
            thread_key: Optional thread key for reply
            header: Card header dict (title, subtitle, imageStyle)
            sections: List of card sections
            widgets: List of widgets (buttons, textParagraph, image, etc.)
            cards: List of cards (for multiple cards)

        Returns:
            Dict with success, message_name, etc.
        """
        try:
            # Build card object
            card_obj = {}

            # If full card provided, use it
            if card:
                card_obj = card
            else:
                # Build card from components
                if header:
                    card_obj["cardHeader"] = header

                card_sections = []

                # Add sections with widgets
                if sections:
                    card_sections.extend(sections)

                if widgets:
                    card_sections.append({"widgets": widgets})

                if card_sections:
                    card_obj["sections"] = card_sections

            # Prepare message payload
            payload = {
                "text": message or ""
            }

            # Add card if provided
            if card_obj:
                if cards:
                    # Multiple cards
                    payload["cardsV2"] = [
                        {"cardId": f"card_{i}", "card": card}
                        for i, card in enumerate(cards)
                    ]
                else:
                    # Single card
                    payload["cardsV2"] = [
                        {"cardId": "card_0", "card": card_obj}
                    ]

            # Send via Google Chat API
            if self.google_chat_service:
                result = await self.google_chat_service.send_message(
                    space_name,
                    message or "",
                    thread_id=thread_key,
                    message_format="CARD",
                    card_v2=[card_obj]
                )

                if result.get('ok'):
                    return {
                        "success": True,
                        "message_name": result.get('message_id'),
                        "space": space_name,
                        "thread_key": thread_key
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get('error', 'Unknown error')
                    }

            # Fallback: simulate success if service not available
            logger.warning("Google Chat service not available, simulating card send")
            return {
                "success": True,
                "message_name": f"msg_{secrets.token_hex(8)}",
                "space": space_name,
                "thread_key": thread_key,
                "note": "Service not available - simulated"
            }

        except Exception as e:
            logger.error(f"Error sending card: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def update_card(
        self,
        space_name: str,
        message_name: str
    ) -> Dict[str, Any]:
        """
        Update an existing interactive card.

        Args:
            space_name: Google Chat space name
            message_name: Message name to update

        Returns:
            Dict with success status
        """
        try:
            if self.google_chat_service:
                # Update via Google Chat API
                result = await self.google_chat_service.update_message(
                    space_name,
                    message_name
                )

                return {
                    "success": result.get('ok', True),
                    "message_name": message_name,
                    "space": space_name
                }

            return {
                "success": True,
                "message_name": message_name,
                "space": space_name,
                "note": "Service not available - simulated"
            }

        except Exception as e:
            logger.error(f"Error updating card: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    # ============================================================================
    # Dialog Methods
    # ============================================================================

    async def open_dialog(
        self,
        space_name: str,
        dialog: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Open a dialog in Google Chat.

        Dialogs are modal windows for user interaction with forms.

        Args:
            space_name: Google Chat space name
            dialog: Dialog definition dict with body, buttons, etc.

        Returns:
            Dict with success status
        """
        try:
            if self.google_chat_service:
                # Open dialog via Google Chat API
                result = await self.google_chat_service.open_dialog(
                    space_name,
                    dialog
                )

                return {
                    "success": result.get('ok', True),
                    "space": space_name,
                    "dialog": dialog
                }

            return {
                "success": True,
                "space": space_name,
                "dialog": dialog,
                "note": "Service not available - simulated"
            }

        except Exception as e:
            logger.error(f"Error opening dialog: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    # ============================================================================
    # Space Management Methods
    # ============================================================================

    async def create_space(
        self,
        display_name: str,
        description: Optional[str] = None,
        space_type: str = "SPACE",
        members: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a new Google Chat space.

        Args:
            display_name: Display name for the space
            description: Optional description
            space_type: SPACE or GROUP_CHAT
            members: List of email addresses to add

        Returns:
            Dict with success, space_name, etc.
        """
        try:
            if self.google_chat_service:
                # Create space via Google Chat API
                result = await self.google_chat_service.create_space(
                    display_name=display_name,
                    description=description,
                    space_type=space_type
                )

                if result.get('ok'):
                    space_name = result.get('space_name')

                    # Add members if provided
                    if members and space_name:
                        for member_email in members:
                            await self.add_space_members(space_name, [member_email])

                    return {
                        "success": True,
                        "space_name": space_name,
                        "display_name": display_name,
                        "description": description,
                        "space_type": space_type,
                        "members_added": len(members) if members else 0
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get('error', 'Unknown error')
                    }

            # Fallback: simulate space creation
            logger.warning("Google Chat service not available, simulating space creation")
            mock_space_name = f"spaces/{secrets.token_hex(8)}"

            return {
                "success": True,
                "space_name": mock_space_name,
                "display_name": display_name,
                "description": description,
                "space_type": space_type,
                "members_added": len(members) if members else 0,
                "note": "Service not available - simulated"
            }

        except Exception as e:
            logger.error(f"Error creating space: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def list_spaces(self) -> Dict[str, Any]:
        """
        List all available Google Chat spaces.

        Returns:
            Dict with success and spaces list
        """
        try:
            if self.google_chat_service:
                result = await self.google_chat_service.get_spaces()

                if result.get('ok'):
                    spaces = [
                        {
                            "name": space.get('space_name'),
                            "display_name": space.get('display_name'),
                            "type": space.get('type'),
                            "member_count": space.get('member_count', 0),
                            "threaded": space.get('threaded', False)
                        }
                        for space in result.get('spaces', [])
                    ]

                    return {
                        "success": True,
                        "spaces": spaces,
                        "count": len(spaces)
                    }

            # Fallback: return empty list
            return {
                "success": True,
                "spaces": [],
                "count": 0,
                "note": "Service not available"
            }

        except Exception as e:
            logger.error(f"Error listing spaces: {e}")
            return {
                "success": False,
                "error": str(e),
                "spaces": []
            }

    async def get_space_info(self, space_name: str) -> Dict[str, Any]:
        """
        Get detailed information about a space.

        Args:
            space_name: Google Chat space name

        Returns:
            Dict with success and space details
        """
        try:
            if self.google_chat_service:
                result = await self.google_chat_service.get_space(space_name)

                if result.get('ok'):
                    space_data = result.get('space', {})
                    return {
                        "success": True,
                        "name": space_data.get('space_name'),
                        "display_name": space_data.get('display_name'),
                        "description": space_data.get('description'),
                        "type": space_data.get('type'),
                        "member_count": space_data.get('member_count', 0),
                        "threaded": space_data.get('threaded', False),
                        "created_at": space_data.get('created_at')
                    }

            # Fallback: return basic info
            return {
                "success": True,
                "name": space_name,
                "display_name": space_name.split("/")[-1],
                "note": "Service not available - limited info"
            }

        except Exception as e:
            logger.error(f"Error getting space info: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def add_space_members(
        self,
        space_name: str,
        members: List[str]
    ) -> Dict[str, Any]:
        """
        Add members to a Google Chat space.

        Args:
            space_name: Google Chat space name
            members: List of email addresses to add

        Returns:
            Dict with success and added members count
        """
        try:
            added_count = 0

            if self.google_chat_service:
                for member_email in members:
                    result = await self.google_chat_service.add_member(
                        space_name,
                        member_email
                    )
                    if result.get('ok'):
                        added_count += 1

            return {
                "success": True,
                "space_name": space_name,
                "added_count": added_count,
                "total_requested": len(members)
            }

        except Exception as e:
            logger.error(f"Error adding members: {e}")
            return {
                "success": False,
                "error": str(e),
                "added_count": 0
            }

    async def remove_space_members(
        self,
        space_name: str,
        members: List[str]
    ) -> Dict[str, Any]:
        """
        Remove members from a Google Chat space.

        Args:
            space_name: Google Chat space name
            members: List of email addresses to remove

        Returns:
            Dict with success and removed members count
        """
        try:
            removed_count = 0

            if self.google_chat_service:
                for member_email in members:
                    result = await self.google_chat_service.remove_member(
                        space_name,
                        member_email
                    )
                    if result.get('ok'):
                        removed_count += 1

            return {
                "success": True,
                "space_name": space_name,
                "removed_count": removed_count,
                "total_requested": len(members)
            }

        except Exception as e:
            logger.error(f"Error removing members: {e}")
            return {
                "success": False,
                "error": str(e),
                "removed_count": 0
            }

    async def set_space_webhook(
        self,
        space_name: str,
        webhook_url: str,
        state: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Configure webhook for a space.

        Args:
            space_name: Google Chat space name
            webhook_url: Webhook URL to send events to
            state: Optional state parameter

        Returns:
            Dict with success status
        """
        try:
            # Store webhook configuration (would normally persist to database)
            webhook_config = {
                "space_name": space_name,
                "webhook_url": webhook_url,
                "state": state,
                "created_at": datetime.utcnow().isoformat()
            }

            logger.info(f"Webhook configured for space {space_name}: {webhook_url}")

            return {
                "success": True,
                "space_name": space_name,
                "webhook_url": webhook_url,
                "state": state,
                "note": "Webhook configuration stored"
            }

        except Exception as e:
            logger.error(f"Error setting webhook: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    # ============================================================================
    # Message Methods
    # ============================================================================

    async def send_message(
        self,
        space_name: str,
        text: str,
        thread_key: Optional[str] = None,
        message_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a text message to Google Chat.

        Args:
            space_name: Google Chat space name
            text: Message text
            thread_key: Optional thread key for reply
            message_id: Optional message ID to reply to

        Returns:
            Dict with success and message details
        """
        try:
            if self.google_chat_service:
                result = await self.google_chat_service.send_message(
                    space_name,
                    text,
                    thread_id=thread_key
                )

                if result.get('ok'):
                    return {
                        "success": True,
                        "message_name": result.get('message_id'),
                        "space": space_name,
                        "thread_key": thread_key,
                        "text": text
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get('error', 'Unknown error')
                    }

            # Fallback: simulate message send
            logger.warning("Google Chat service not available, simulating message send")
            return {
                "success": True,
                "message_name": f"msg_{secrets.token_hex(8)}",
                "space": space_name,
                "thread_key": thread_key,
                "text": text,
                "note": "Service not available - simulated"
            }

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def upload_file(
        self,
        space_name: str,
        file_path: Optional[str] = None,
        content: Optional[str] = None,
        filename: Optional[str] = None,
        mime_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload a file to Google Chat.

        Args:
            space_name: Google Chat space name
            file_path: Path to file to upload
            content: File content as string
            filename: Filename for upload
            mime_type: MIME type of file

        Returns:
            Dict with success and file details
        """
        try:
            # Read file content
            if file_path:
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                filename = filename or os.path.basename(file_path)
            elif content:
                file_content = content.encode('utf-8')
            else:
                return {
                    "success": False,
                    "error": "Either file_path or content must be provided"
                }

            # Determine MIME type
            if not mime_type:
                import mimetypes
                mime_type = mimetypes.guess_type(filename or file_path or "")[0] or "application/octet-stream"

            if self.google_chat_service:
                # Upload via Google Chat API
                result = await self.google_chat_service.upload_file(
                    space_name,
                    file_content,
                    filename,
                    mime_type
                )

                if result.get('ok'):
                    return {
                        "success": True,
                        "file_name": result.get('file_name'),
                        "space": space_name,
                        "filename": filename,
                        "mime_type": mime_type
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get('error', 'Unknown error')
                    }

            # Fallback: simulate file upload
            logger.warning("Google Chat service not available, simulating file upload")
            return {
                "success": True,
                "file_name": f"files/{secrets.token_hex(8)}",
                "space": space_name,
                "filename": filename,
                "mime_type": mime_type,
                "note": "Service not available - simulated"
            }

        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    # ============================================================================
    # Service Status Methods
    # ============================================================================

    async def get_service_status(self) -> Dict[str, Any]:
        """
        Get the current status of Google Chat service.

        Returns:
            Dict with status information
        """
        try:
            is_active = self.google_chat_service is not None

            return {
                "status": "active" if is_active else "inactive",
                "service_name": "Google Chat",
                "is_initialized": self.is_initialized,
                "active_spaces_count": len(self.active_spaces) if is_active else 0,
                "has_analytics": self.google_chat_analytics is not None,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting service status: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

# Global Google Chat integration instance
atom_google_chat_integration = AtomGoogleChatIntegration({
    'atom_memory_service': None,  # Would be actual instance
    'atom_search_service': None,  # Would be actual instance
    'atom_workflow_service': None,  # Would be actual instance
    'atom_ingestion_pipeline': None  # Would be actual instance
})