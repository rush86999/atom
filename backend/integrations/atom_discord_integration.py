"""
ATOM Discord Integration Module
Integrates Discord seamlessly into ATOM's unified communication ecosystem
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
    from discord_enhanced_service import discord_enhanced_service, DiscordGuild, DiscordChannel, DiscordMessage, DiscordUser
    from discord_analytics_engine import discord_analytics_engine
except ImportError as e:
    logging.warning(f"Discord integration services not available: {e}")

logger = logging.getLogger(__name__)

class AtomDiscordIntegration:
    """Main integration class for Discord within ATOM ecosystem"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.atom_memory = config.get('atom_memory_service')
        self.atom_search = config.get('atom_search_service')
        self.atom_workflow = config.get('atom_workflow_service')
        self.atom_ingestion = config.get('atom_ingestion_pipeline')
        
        # Discord services
        self.discord_service = discord_enhanced_service
        self.discord_analytics = discord_analytics_engine
        
        # Integration state
        self.is_initialized = False
        self.active_guilds: List[DiscordGuild] = []
        self.communication_channels: List[Dict[str, Any]] = []
        self.unified_messages: List[Dict[str, Any]] = []
        
        logger.info("ATOM Discord Integration initialized")
    
    async def initialize(self) -> bool:
        """Initialize Discord integration with ATOM services"""
        try:
            if not all([self.discord_service, self.atom_memory, self.atom_search]):
                logger.error("Required services not available for Discord integration")
                return False
            
            # Start integration workers
            await self._start_integration_workers()
            
            # Initialize unified data structures
            await self._initialize_unified_data()
            
            # Setup event handlers for cross-platform communication
            await self._setup_cross_platform_handlers()
            
            self.is_initialized = True
            logger.info("Discord integration with ATOM ecosystem initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing Discord integration: {e}")
            return False
    
    async def get_unified_workspaces(self, user_id: str) -> List[Dict[str, Any]]:
        """Get unified workspaces across all platforms including Discord"""
        try:
            # Get Discord guilds
            discord_guilds = await self.discord_service.get_guilds(user_id)
            
            # Transform to unified format
            unified_workspaces = []
            
            for guild in discord_guilds:
                unified_workspace = {
                    'id': f"discord_{guild.guild_id}",
                    'name': guild.name,
                    'type': 'discord',
                    'platform': 'Discord',
                    'status': 'connected' if guild.is_connected else 'disconnected',
                    'member_count': guild.member_count,
                    'channel_count': guild.channel_count,
                    'icon_url': guild.icon_url,
                    'description': guild.description,
                    'integration_data': {
                        'guild_id': guild.guild_id,
                        'owner_id': guild.owner_id,
                        'owner_name': guild.owner_name,
                        'region': guild.region,
                        'features': guild.features,
                        'premium_tier': guild.premium_tier,
                        'verification_level': guild.verification_level,
                        'roles_count': guild.roles_count,
                        'emojis_count': guild.emojis_count,
                        'created_at': guild.created_at.isoformat() if guild.created_at else None
                    },
                    'capabilities': {
                        'messaging': True,
                        'voice_calls': True,
                        'video_calls': True,
                        'screen_sharing': True,
                        'file_sharing': True,
                        'live_streaming': True,
                        'workflows': True,
                        'analytics': True,
                        'gaming_features': True,
                        'role_management': True,
                        'bot_automation': True,
                        'server_boosting': True
                    }
                }
                unified_workspaces.append(unified_workspace)
            
            # Store in active guilds
            self.active_guilds = discord_guilds
            
            return unified_workspaces
            
        except Exception as e:
            logger.error(f"Error getting unified Discord workspaces: {e}")
            return []
    
    async def get_unified_channels(self, workspace_id: str, user_id: str = None) -> List[Dict[str, Any]]:
        """Get unified channels across platforms for given workspace"""
        try:
            # Extract Discord workspace ID from unified workspace ID
            if workspace_id.startswith('discord_'):
                discord_workspace_id = workspace_id[8:]  # Remove 'discord_' prefix
            else:
                return []
            
            # Get Discord channels for guild
            guild = self._get_guild_by_id(discord_workspace_id)
            if not guild:
                return []
            
            # Get channels from Discord API
            channels = await self.discord_service.get_guild_channels(discord_workspace_id)
            
            # Transform to unified format
            unified_channels = []
            
            for channel in channels:
                unified_channel = {
                    'id': f"discord_{channel.channel_id}",
                    'name': channel.name,
                    'display_name': channel.name,
                    'description': channel.topic,
                    'type': channel.type.value.lower().replace('_', '-'),
                    'platform': 'Discord',
                    'workspace_id': workspace_id,
                    'workspace_name': guild.name,
                    'status': 'active' if not channel.is_archived else 'archived',
                    'member_count': channel.member_count,
                    'message_count': channel.message_count,
                    'unread_count': 0,  # Would calculate from database
                    'last_activity': channel.last_modified_at,
                    'is_private': channel.is_private,
                    'is_muted': False,  # Would check user preferences
                    'is_favorite': False,  # Would check user preferences
                    'is_text': channel.is_text,
                    'is_voice': channel.is_voice,
                    'is_stage': channel.is_stage,
                    'is_news': channel.is_news,
                    'is_thread': channel.is_thread,
                    'is_archived': channel.is_archived,
                    'position': channel.position,
                    'parent_id': channel.parent_id,
                    'permissions': channel.permissions,
                    'rate_limit': channel.rate_limit_per_user,
                    'integration_data': {
                        'channel_id': channel.channel_id,
                        'channel_type': channel.type.value,
                        'guild_id': channel.guild_id,
                        'nsfw': channel.nsfw,
                        'bitrate': channel.bitrate,
                        'user_limit': channel.user_limit,
                        'default_auto_archive_duration': channel.default_auto_archive_duration,
                        'flags': channel.flags,
                        'permission_overwrites': channel.permission_overwrites,
                        'last_pin_timestamp': channel.last_pin_timestamp,
                        'rtc_region': channel.rtc_region
                    },
                    'capabilities': {
                        'messaging': channel.is_text,
                        'file_sharing': channel.is_text,
                        'voice_calls': channel.is_voice,
                        'video_calls': channel.is_voice or channel.is_stage,
                        'screen_sharing': channel.is_voice or channel.is_stage,
                        'voice_chat': channel.is_voice,
                        'streaming': channel.is_voice,
                        'announcements': channel.is_news,
                        'threads': channel.is_text,
                        'reactions': channel.is_text
                    }
                }
                unified_channels.append(unified_channel)
            
            # Store in communication channels
            self.communication_channels.extend(unified_channels)
            
            return unified_channels
            
        except Exception as e:
            logger.error(f"Error getting unified Discord channels: {e}")
            return []
    
    async def send_unified_message(self, workspace_id: str, channel_id: str,
                                 content: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send unified message across platforms including Discord"""
        try:
            options = options or {}
            
            # Check if this is a Discord channel
            if channel_id.startswith('discord_'):
                discord_channel_id = channel_id[8:]  # Remove 'discord_' prefix
                
                # Send Discord message with enhanced options
                discord_result = await self.discord_service.send_message(
                    guild_id=options.get('guild_id'),
                    channel_id=discord_channel_id,
                    content=content,
                    embed=options.get('embed'),
                    components=options.get('components'),
                    tts=options.get('tts', False)
                )
                
                if discord_result.get('ok'):
                    # Store in unified memory
                    await self._store_message_in_memory(discord_result, 'discord', options)
                    
                    # Index in unified search
                    await self._index_message_in_search(discord_result, 'discord', options)
                    
                    # Trigger workflows if needed
                    await self._trigger_workflows(discord_result, 'discord_message_sent', options)
                    
                    return {
                        'ok': True,
                        'message_id': discord_result.get('message_id'),
                        'platform': 'Discord',
                        'timestamp': datetime.utcnow().isoformat(),
                        'channel_id': channel_id,
                        'workspace_id': workspace_id
                    }
                else:
                    return discord_result
            
            # For non-Discord channels, would handle other platforms here
            else:
                return {'ok': False, 'error': 'Unsupported platform'}
        
        except Exception as e:
            logger.error(f"Error sending unified Discord message: {e}")
            return {'ok': False, 'error': str(e)}
    
    async def get_unified_messages(self, workspace_id: str, channel_id: str,
                                limit: int = 100, options: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get unified messages across platforms including Discord"""
        try:
            options = options or {}
            unified_messages = []
            
            # Check if this is a Discord channel
            if channel_id.startswith('discord_'):
                discord_channel_id = channel_id[8:]  # Remove 'discord_' prefix
                discord_workspace_id = workspace_id[8:]  # Remove 'discord_' prefix
                
                # Get Discord messages
                discord_messages = await self.discord_service.get_channel_messages(
                    guild_id=discord_workspace_id,
                    channel_id=discord_channel_id,
                    limit=limit,
                    before=options.get('before'),
                    after=options.get('after'),
                    around=options.get('around')
                )
                
                # Transform to unified format
                for message in discord_messages:
                    unified_message = {
                        'id': f"discord_{message.message_id}",
                        'content': message.content,
                        'html_content': message.content,  # Discord doesn't have HTML content
                        'platform': 'Discord',
                        'workspace_id': workspace_id,
                        'channel_id': channel_id,
                        'user_id': f"discord_{message.user_id}",
                        'user_name': message.user_name,
                        'user_display_name': message.user_display_name,
                        'user_discriminator': message.user_discriminator,
                        'user_avatar': message.user_avatar,
                        'timestamp': message.timestamp,
                        'thread_id': f"discord_{message.thread_id}" if message.thread_id else None,
                        'reply_to_id': message.reply_to_id,
                        'message_type': self._convert_discord_message_type(message.type),
                        'subject': None,  # Discord doesn't have subjects
                        'is_edited': message.is_edited,
                        'edit_timestamp': message.edited_timestamp,
                        'is_pinned': message.is_pinned,
                        'is_crossposted': message.is_crossposted,
                        'is_command': message.is_command,
                        'is_bot': message.is_bot,
                        'is_webhook': message.is_webhook,
                        'is_system': message.is_system,
                        'reactions': self._convert_discord_reactions(message.reactions),
                        'attachments': self._convert_discord_attachments(message.attachments),
                        'mentions': self._convert_discord_mentions(message.mentions),
                        'files': self._convert_discord_attachments(message.attachments),
                        'embeds': self._convert_discord_embeds(message.embeds),
                        'components': message.components,
                        'stickers': message.stickers,
                        'role_mentions': message.mention_roles,
                        'channel_mentions': message.mention_channels,
                        'mention_everyone': message.mention_everyone,
                        'tts': message.tts,
                        'pinned': message.pinned,
                        'integration_data': {
                            'message_id': message.message_id,
                            'user_id': message.user_id,
                            'user_discriminator': message.user_discriminator,
                            'message_type': message.type,
                            'flags': message.flags,
                            'member': message.member,
                            'referenced_message': message.referenced_message,
                            'interaction': message.interaction,
                            'application_id': message.application_id,
                            'webhook_id': message.webhook_id,
                            'position': message.position,
                            'message_snapshots': message.message_snapshots
                        },
                        'metadata': {
                            'has_thread': bool(message.thread_id),
                            'has_reactions': bool(message.reactions),
                            'has_attachments': bool(message.attachments),
                            'has_embeds': bool(message.embeds),
                            'has_components': bool(message.components),
                            'has_stickers': bool(message.stickers),
                            'is_tts': message.tts,
                            'mentions_everyone': message.mention_everyone
                        }
                    }
                    unified_messages.append(unified_message)
            
            # Store in unified messages
            self.unified_messages.extend(unified_messages)
            
            # Sort by timestamp (newest first)
            unified_messages.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return unified_messages[:limit]
            
        except Exception as e:
            logger.error(f"Error getting unified Discord messages: {e}")
            return []
    
    async def unified_search(self, query: str, workspace_id: str = None,
                          channel_id: str = None, options: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Perform unified search across platforms including Discord"""
        try:
            options = options or {}
            unified_results = []
            
            # Discord search
            if channel_id and channel_id.startswith('discord_'):
                discord_channel_id = channel_id[8:]  # Remove 'discord_' prefix
                discord_workspace_id = workspace_id[8:] if workspace_id and workspace_id.startswith('discord_') else None
                
                discord_results = await self.discord_service.search_messages(
                    guild_id=discord_workspace_id,
                    channel_id=discord_channel_id,
                    query=query,
                    limit=options.get('limit', 50),
                    before=options.get('before'),
                    after=options.get('after')
                )
                
                if discord_results.get('ok'):
                    # Would convert to unified format
                    # For now, add placeholder results
                    pass
            
            # Add results from other platforms here...
            
            # Sort by relevance score
            unified_results.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            return unified_results[:options.get('limit', 50)]
            
        except Exception as e:
            logger.error(f"Error in unified Discord search: {e}")
            return []
    
    async def create_unified_workflow(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create unified workflow that can operate across platforms including Discord"""
        try:
            # Check if workflow involves Discord
            discord_involved = False
            for trigger in workflow_data.get('triggers', []):
                if trigger.get('platform') == 'discord' or 'discord' in trigger.get('event', '').lower():
                    discord_involved = True
                    break
            
            for action in workflow_data.get('actions', []):
                if action.get('platform') == 'discord' or 'discord' in action.get('action', '').lower():
                    discord_involved = True
                    break
            
            if not discord_involved:
                # Workflow doesn't involve Discord, handle through standard workflow service
                if self.atom_workflow:
                    return await self.atom_workflow.create_workflow(workflow_data)
                else:
                    return {'ok': False, 'error': 'Workflow service not available'}
            
            # Create Discord-specific workflow
            # This would integrate with discord_workflow_engine
            
            return {
                'ok': True,
                'workflow_id': f"discord_workflow_{int(datetime.utcnow().timestamp())}",
                'platform': 'discord',
                'message': 'Discord workflow created successfully'
            }
        
        except Exception as e:
            logger.error(f"Error creating unified Discord workflow: {e}")
            return {'ok': False, 'error': str(e)}
    
    async def get_unified_analytics(self, metric: str, time_range: str,
                                 workspace_id: str = None, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get unified analytics across platforms including Discord"""
        try:
            options = options or {}
            
            # Get Discord analytics
            if self.discord_analytics:
                discord_analytics = await self.discord_analytics.get_analytics(
                    metric=metric,
                    time_range=time_range,
                    workspace_id=workspace_id[8:] if workspace_id and workspace_id.startswith('discord_') else None,
                    filters=options.get('filters', {})
                )
            else:
                discord_analytics = []
            
            # Transform to unified format
            unified_analytics = {
                'platform': 'Discord',
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
                    for point in discord_analytics
                ],
                'total_points': len(discord_analytics)
            }
            
            # Add analytics from other platforms here...
            
            return unified_analytics
            
        except Exception as e:
            logger.error(f"Error getting unified Discord analytics: {e}")
            return {'ok': False, 'error': str(e)}
    
    # Private helper methods
    async def _start_integration_workers(self):
        """Start background integration workers"""
        # Start Discord message ingestion worker
        asyncio.create_task(self._discord_message_ingestion_worker())
        
        # Start Discord event processing worker
        asyncio.create_task(self._discord_event_processing_worker())
        
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
                    'platform': 'discord'
                })
                
                # Load unified channels
                channels_data = await self.atom_memory.query({
                    'type': 'unified_channel',
                    'platform': 'discord'
                })
                
                # Load unified messages
                messages_data = await self.atom_memory.query({
                    'type': 'unified_message',
                    'platform': 'discord'
                })
                
                logger.info(f"Loaded unified Discord data: {len(workspaces_data)} workspaces, {len(channels_data)} channels, {len(messages_data)} messages")
                
            except Exception as e:
                logger.error(f"Error loading unified Discord data: {e}")
    
    async def _setup_cross_platform_handlers(self):
        """Setup cross-platform event handlers"""
        # Setup Discord event handlers that integrate with other platforms
        
        # Example: When a Discord message is sent, also notify in Slack if configured
        if self.discord_service:
            self.discord_service.event_handlers[DiscordEventType.MESSAGE_CREATE].append(
                self._handle_discord_message_cross_platform
            )
            
            self.discord_service.event_handlers[DiscordEventType.GUILD_CREATE].append(
                self._handle_discord_guild_event_cross_platform
            )
            
            self.discord_service.event_handlers[DiscordEventType.VOICE_STATE_UPDATE].append(
                self._handle_discord_voice_event_cross_platform
            )
    
    async def _handle_discord_message_cross_platform(self, event_data: Dict[str, Any]):
        """Handle Discord message cross-platform integration"""
        try:
            # Store in unified memory
            await self._store_message_in_memory(event_data, 'discord')
            
            # Index in unified search
            await self._index_message_in_search(event_data, 'discord')
            
            # Trigger cross-platform workflows
            await self._trigger_workflows(event_data, 'discord_message_cross_platform')
            
        except Exception as e:
            logger.error(f"Error handling Discord message cross-platform: {e}")
    
    async def _handle_discord_guild_event_cross_platform(self, event_data: Dict[str, Any]):
        """Handle Discord guild event cross-platform integration"""
        try:
            # Update unified workspace information
            await self._update_workspace_cross_platform(event_data, 'discord')
            
            # Trigger workspace event workflows
            await self._trigger_workflows(event_data, 'discord_guild_event_cross_platform')
            
        except Exception as e:
            logger.error(f"Error handling Discord guild event cross-platform: {e}")
    
    async def _handle_discord_voice_event_cross_platform(self, event_data: Dict[str, Any]):
        """Handle Discord voice event cross-platform integration"""
        try:
            # Update voice state in unified workspace
            await self._update_voice_state_cross_platform(event_data, 'discord')
            
            # Trigger voice event workflows
            await self._trigger_workflows(event_data, 'discord_voice_event_cross_platform')
            
        except Exception as e:
            logger.error(f"Error handling Discord voice event cross-platform: {e}")
    
    def _get_guild_by_id(self, guild_id: str) -> Optional[DiscordGuild]:
        """Get Discord guild by ID"""
        try:
            # This would get from database or cache
            # For now, return placeholder
            return DiscordGuild(
                guild_id=guild_id,
                name='Discord Server',
                owner_id='owner_id',
                owner_name='Server Owner'
            )
        except Exception as e:
            logger.error(f"Error getting Discord guild by ID: {e}")
            return None
    
    def _convert_discord_message_type(self, message_type: int) -> str:
        """Convert Discord message type to unified format"""
        type_mapping = {
            0: 'default',
            1: 'recipient_add',
            2: 'recipient_remove',
            3: 'call',
            4: 'channel_name_change',
            5: 'channel_icon_change',
            6: 'channel_pinned_message',
            7: 'guild_member_join',
            8: 'guild_boost',
            9: 'guild_boost_tier_1',
            10: 'guild_boost_tier_2',
            11: 'guild_boost_tier_3',
            12: 'channel_follow_add',
            14: 'guild_discovery_disqualified',
            15: 'guild_discovery_requalified',
            16: 'guild_discovery_grace_period_initial_warning',
            17: 'guild_discovery_grace_period_final_warning',
            18: 'thread_created',
            19: 'reply',
            20: 'chat_input_command',
            21: 'thread_starter_message',
            22: 'guild_invite_reminder',
            23: 'context_menu_command',
            24: 'auto_moderation_action'
        }
        return type_mapping.get(message_type, 'unknown')
    
    def _convert_discord_reactions(self, reactions: List[Dict]) -> List[Dict]:
        """Convert Discord reactions to unified format"""
        unified_reactions = []
        for reaction in reactions:
            unified_reactions.append({
                'emoji': reaction.get('emoji', {}).get('name', '❓'),
                'id': reaction.get('emoji', {}).get('id'),
                'animated': reaction.get('emoji', {}).get('animated', False),
                'count': reaction.get('count', 1),
                'me': reaction.get('me', False)
            })
        return unified_reactions
    
    def _convert_discord_attachments(self, attachments: List[Dict]) -> List[Dict]:
        """Convert Discord attachments to unified format"""
        unified_attachments = []
        for attachment in attachments:
            unified_attachments.append({
                'id': attachment.get('id'),
                'title': attachment.get('filename'),
                'content_type': attachment.get('content_type'),
                'download_url': attachment.get('url'),
                'proxy_url': attachment.get('proxy_url'),
                'size': attachment.get('size', 0),
                'width': attachment.get('width'),
                'height': attachment.get('height'),
                'type': 'discord_attachment'
            })
        return unified_attachments
    
    def _convert_discord_mentions(self, mentions: List[Dict]) -> List[Dict]:
        """Convert Discord mentions to unified format"""
        unified_mentions = []
        for mention in mentions:
            unified_mentions.append({
                'id': mention.get('id'),
                'username': mention.get('username'),
                'discriminator': mention.get('discriminator'),
                'display_name': mention.get('display_name'),
                'avatar': mention.get('avatar'),
                'type': 'user',
                'platform': 'Discord'
            })
        return unified_mentions
    
    def _convert_discord_embeds(self, embeds: List[Dict]) -> List[Dict]:
        """Convert Discord embeds to unified format"""
        unified_embeds = []
        for embed in embeds:
            unified_embeds.append({
                'title': embed.get('title'),
                'description': embed.get('description'),
                'url': embed.get('url'),
                'type': embed.get('type'),
                'color': embed.get('color'),
                'timestamp': embed.get('timestamp'),
                'footer': embed.get('footer'),
                'image': embed.get('image'),
                'thumbnail': embed.get('thumbnail'),
                'video': embed.get('video'),
                'author': embed.get('author'),
                'fields': embed.get('fields', [])
            })
        return unified_embeds
    
    async def _store_message_in_memory(self, message_data: Dict[str, Any], platform: str, options: Dict[str, Any] = None):
        """Store message in unified ATOM memory"""
        try:
            if not self.atom_memory:
                return
            
            memory_data = {
                'type': 'unified_message',
                'platform': platform,
                'message_id': message_data.get('message_id'),
                'content': message_data.get('content'),
                'user_id': message_data.get('user_id'),
                'user_name': message_data.get('user_name'),
                'user_discriminator': message_data.get('user_discriminator'),
                'channel_id': message_data.get('channel_id'),
                'workspace_id': message_data.get('workspace_id'),
                'timestamp': message_data.get('timestamp') or datetime.utcnow().isoformat(),
                'edited_timestamp': message_data.get('edited_timestamp'),
                'reactions': message_data.get('reactions', []),
                'attachments': message_data.get('attachments', []),
                'embeds': message_data.get('embeds', []),
                'mentions': message_data.get('mentions', []),
                'integration_data': message_data,
                'options': options or {},
                'indexed': False,
                'synced': True
            }
            
            await self.atom_memory.store(memory_data)
            
        except Exception as e:
            logger.error(f"Error storing Discord message in unified memory: {e}")
    
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
                'content': message_data.get('content'),
                'metadata': {
                    'user_id': message_data.get('user_id'),
                    'user_name': message_data.get('user_name'),
                    'user_discriminator': message_data.get('user_discriminator'),
                    'channel_id': message_data.get('channel_id'),
                    'workspace_id': message_data.get('workspace_id'),
                    'timestamp': message_data.get('timestamp') or datetime.utcnow().isoformat(),
                    'platform': platform,
                    'has_attachments': bool(message_data.get('attachments')),
                    'has_embeds': bool(message_data.get('embeds')),
                    'has_reactions': bool(message_data.get('reactions')),
                    'is_bot': message_data.get('is_bot', False),
                    'is_webhook': message_data.get('is_webhook', False),
                    'is_system': message_data.get('is_system', False),
                    'integration_data': message_data
                }
            }
            
            await self.atom_search.index(search_data)
            
        except Exception as e:
            logger.error(f"Error indexing Discord message in unified search: {e}")
    
    async def _trigger_workflows(self, event_data: Dict[str, Any], event_type: str, options: Dict[str, Any] = None):
        """Trigger workflows for cross-platform events"""
        try:
            if not self.atom_workflow:
                return
            
            workflow_trigger = {
                'event_type': event_type,
                'platform': 'discord',
                'data': event_data,
                'timestamp': datetime.utcnow().isoformat(),
                'options': options or {}
            }
            
            await self.atom_workflow.trigger_workflows(workflow_trigger)
            
        except Exception as e:
            logger.error(f"Error triggering workflows for Discord event: {e}")
    
    async def _update_workspace_cross_platform(self, event_data: Dict[str, Any], platform: str):
        """Update workspace information across platforms"""
        try:
            # This would update unified workspace information
            pass
        except Exception as e:
            logger.error(f"Error updating workspace cross-platform: {e}")
    
    async def _update_voice_state_cross_platform(self, event_data: Dict[str, Any], platform: str):
        """Update voice state information across platforms"""
        try:
            # This would update voice state in unified workspace
            pass
        except Exception as e:
            logger.error(f"Error updating voice state cross-platform: {e}")
    
    # Background workers
    async def _discord_message_ingestion_worker(self):
        """Background worker for Discord message ingestion"""
        while True:
            try:
                # Process Discord message queue
                # This would integrate with ingestion pipeline
                await asyncio.sleep(30)  # Process every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in Discord message ingestion worker: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    async def _discord_event_processing_worker(self):
        """Background worker for Discord event processing"""
        while True:
            try:
                # Process Discord event queue
                # This would handle real-time Discord events
                await asyncio.sleep(10)  # Process every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in Discord event processing worker: {e}")
                await asyncio.sleep(30)  # Wait before retrying
    
    async def _unified_search_indexing_worker(self):
        """Background worker for unified search indexing"""
        while True:
            try:
                # Index unindexed Discord messages in unified search
                if self.atom_search and self.atom_memory:
                    unindexed_messages = await self.atom_memory.query({
                        'type': 'unified_message',
                        'platform': 'discord',
                        'indexed': False
                    })
                    
                    for message in unindexed_messages:
                        await self._index_message_in_search(message, 'discord')
                        await self.atom_memory.update(message['id'], {'indexed': True})
                
                await asyncio.sleep(60)  # Process every minute
                
            except Exception as e:
                logger.error(f"Error in unified search indexing worker: {e}")
                await asyncio.sleep(120)  # Wait before retrying

# Global Discord integration instance
atom_discord_integration = AtomDiscordIntegration({
    'atom_memory_service': None,  # Would be actual instance
    'atom_search_service': None,  # Would be actual instance
    'atom_workflow_service': None,  # Would be actual instance
    'atom_ingestion_pipeline': None  # Would be actual instance
})