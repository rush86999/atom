"""
Discord LanceDB Ingestion Service
Complete Discord message ingestion for ATOM memory with user controls
"""

import os
import logging
import json
import asyncio
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
import httpx

# Import LanceDB and vector operations
try:
    import lancedb
    import pyarrow as pa
    LANCEDB_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"LanceDB not available: {e}")
    LANCEDB_AVAILABLE = False

# Import enhanced Discord service
try:
    from discord_enhanced_service import discord_enhanced_service
    DISCORD_SERVICE_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Discord service not available: {e}")
    DISCORD_SERVICE_AVAILABLE = False

# Import encryption utilities
try:
    from atom_encryption import encrypt_data, decrypt_data
    ENCRYPTION_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Encryption not available: {e}")
    ENCRYPTION_AVAILABLE = False

# Import database operations
try:
    from db_oauth_discord_complete import get_discord_tokens
    DISCORD_DB_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Discord database not available: {e}")
    DISCORD_DB_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

# Discord memory configuration
DISCORD_MEMORY_TABLE_NAME = "discord_memory"
DISCORD_USER_SETTINGS_TABLE_NAME = "discord_user_settings"
DISCORD_INGESTION_STATS_TABLE_NAME = "discord_ingestion_stats"

@dataclass
class DiscordMemorySettings:
    """User-controlled Discord memory settings"""
    user_id: str
    ingestion_enabled: bool = True
    sync_frequency: str = "hourly"  # real-time, hourly, daily, weekly, manual
    data_retention_days: int = 365
    include_guilds: List[str] = None
    exclude_guilds: List[str] = None
    include_channels: List[str] = None
    exclude_channels: List[str] = None
    include_dm_channels: bool = True
    include_private_channels: bool = False
    max_messages_per_channel: int = 10000
    semantic_search_enabled: bool = True
    metadata_extraction_enabled: bool = True
    last_sync_timestamp: str = None
    next_sync_timestamp: str = None
    sync_in_progress: bool = False
    error_message: str = None
    created_at: str = None
    updated_at: str = None

@dataclass
class DiscordMessageMemory:
    """Discord message data for LanceDB storage"""
    id: str
    user_id: str
    guild_id: str
    guild_name: str
    channel_id: str
    channel_name: str
    channel_type: str
    message_id: str
    author_id: str
    author_username: str
    author_display_name: str
    author_bot: bool
    content: str
    content_clean: str
    timestamp: str
    edited_timestamp: str
    message_type: int
    tts: bool
    mention_everyone: bool
    mentions: List[str]
    mention_roles: List[str]
    attachments: List[str]
    embeds: List[str]
    reactions: List[str]
    reply_to_message_id: str
    reply_to_author: str
    reply_to_content: str
    thread_id: str
    webhook_id: str
    pinned: bool
    content_hash: str
    processed_at: str
    batch_id: str
    metadata: Dict[str, Any]
    
    def to_lancedb_schema(self) -> Dict[str, Any]:
        """Convert to LanceDB schema"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'guild_id': self.guild_id,
            'guild_name': self.guild_name,
            'channel_id': self.channel_id,
            'channel_name': self.channel_name,
            'channel_type': self.channel_type,
            'message_id': self.message_id,
            'author_id': self.author_id,
            'author_username': self.author_username,
            'author_display_name': self.author_display_name,
            'author_bot': self.author_bot,
            'content': self.content,
            'content_clean': self.content_clean,
            'timestamp': self.timestamp,
            'edited_timestamp': self.edited_timestamp,
            'message_type': self.message_type,
            'tts': self.tts,
            'mention_everyone': self.mention_everyone,
            'mentions': self.mentions,
            'mention_roles': self.mention_roles,
            'attachments': self.attachments,
            'embeds': self.embeds,
            'reactions': self.reactions,
            'reply_to_message_id': self.reply_to_message_id,
            'reply_to_author': self.reply_to_author,
            'reply_to_content': self.reply_to_content,
            'thread_id': self.thread_id,
            'webhook_id': self.webhook_id,
            'pinned': self.pinned,
            'content_hash': self.content_hash,
            'processed_at': self.processed_at,
            'batch_id': self.batch_id,
            'metadata': json.dumps(self.metadata)
        }

@dataclass
class DiscordIngestionStats:
    """Discord ingestion statistics"""
    user_id: str
    total_messages_ingested: int = 0
    last_ingestion_timestamp: str = None
    total_guilds_synced: int = 0
    total_channels_synced: int = 0
    failed_ingestions: int = 0
    last_error_message: str = None
    avg_messages_per_minute: float = 0.0
    storage_size_mb: float = 0.0
    created_at: str = None
    updated_at: str = None

class DiscordLanceDBIngestionService:
    """Discord LanceDB ingestion service with user controls"""
    
    def __init__(self, lancedb_uri: str = None):
        self.lancedb_uri = lancedb_uri or os.getenv('LANCEDB_URI', 'lancedb/discord_memory')
        self.db = None
        self.memory_table = None
        self.settings_table = None
        self.stats_table = None
        self._init_lancedb()
        
        # Ingestion state
        self.ingestion_workers = {}
        self.ingestion_locks = {}
    
    def _init_lancedb(self):
        """Initialize LanceDB connection"""
        try:
            if LANCEDB_AVAILABLE:
                self.db = lancedb.connect(self.lancedb_uri)
                self._create_tables()
                logger.info(f"Discord LanceDB service initialized: {self.lancedb_uri}")
            else:
                logger.warning("LanceDB not available - using mock database")
                self._init_mock_database()
        except Exception as e:
            logger.error(f"Failed to initialize Discord LanceDB: {e}")
            self._init_mock_database()
    
    def _init_mock_database(self):
        """Initialize mock database for testing"""
        self.db = type('MockDB', (), {})()
        self.memory_table = type('MockTable', (), {})()
        self.settings_table = type('MockTable', (), {})()
        self.stats_table = type('MockTable', (), {})()
        self.memory_table.data = []
        self.settings_table.data = []
        self.stats_table.data = []
    
    def _create_tables(self):
        """Create LanceDB tables"""
        if not LANCEDB_AVAILABLE or not self.db:
            return
        
        try:
            # Discord memory table schema
            memory_schema = pa.schema([
                pa.field('id', pa.string()),
                pa.field('user_id', pa.string()),
                pa.field('guild_id', pa.string()),
                pa.field('guild_name', pa.string()),
                pa.field('channel_id', pa.string()),
                pa.field('channel_name', pa.string()),
                pa.field('channel_type', pa.string()),
                pa.field('message_id', pa.string()),
                pa.field('author_id', pa.string()),
                pa.field('author_username', pa.string()),
                pa.field('author_display_name', pa.string()),
                pa.field('author_bot', pa.bool_()),
                pa.field('content', pa.string()),
                pa.field('content_clean', pa.string()),
                pa.field('timestamp', pa.timestamp('us')),
                pa.field('edited_timestamp', pa.timestamp('us')),
                pa.field('message_type', pa.int64()),
                pa.field('tts', pa.bool_()),
                pa.field('mention_everyone', pa.bool_()),
                pa.field('mentions', pa.list_(pa.string())),
                pa.field('mention_roles', pa.list_(pa.string())),
                pa.field('attachments', pa.list_(pa.string())),
                pa.field('embeds', pa.list_(pa.string())),
                pa.field('reactions', pa.list_(pa.string())),
                pa.field('reply_to_message_id', pa.string()),
                pa.field('reply_to_author', pa.string()),
                pa.field('reply_to_content', pa.string()),
                pa.field('thread_id', pa.string()),
                pa.field('webhook_id', pa.string()),
                pa.field('pinned', pa.bool_()),
                pa.field('content_hash', pa.string()),
                pa.field('processed_at', pa.timestamp('us')),
                pa.field('batch_id', pa.string()),
                pa.field('metadata', pa.string())
            ])
            
            # Create or open tables
            self.memory_table = self.db.create_table(
                DISCORD_MEMORY_TABLE_NAME,
                schema=memory_schema,
                mode="overwrite"
            )
            
            # Settings table
            settings_schema = pa.schema([
                pa.field('user_id', pa.string()),
                pa.field('ingestion_enabled', pa.bool_()),
                pa.field('sync_frequency', pa.string()),
                pa.field('data_retention_days', pa.int64()),
                pa.field('include_guilds', pa.list_(pa.string())),
                pa.field('exclude_guilds', pa.list_(pa.string())),
                pa.field('include_channels', pa.list_(pa.string())),
                pa.field('exclude_channels', pa.list_(pa.string())),
                pa.field('include_dm_channels', pa.bool_()),
                pa.field('include_private_channels', pa.bool_()),
                pa.field('max_messages_per_channel', pa.int64()),
                pa.field('semantic_search_enabled', pa.bool_()),
                pa.field('metadata_extraction_enabled', pa.bool_()),
                pa.field('last_sync_timestamp', pa.timestamp('us')),
                pa.field('next_sync_timestamp', pa.timestamp('us')),
                pa.field('sync_in_progress', pa.bool_()),
                pa.field('error_message', pa.string()),
                pa.field('created_at', pa.timestamp('us')),
                pa.field('updated_at', pa.timestamp('us'))
            ])
            
            self.settings_table = self.db.create_table(
                DISCORD_USER_SETTINGS_TABLE_NAME,
                schema=settings_schema,
                mode="overwrite"
            )
            
            # Stats table
            stats_schema = pa.schema([
                pa.field('user_id', pa.string()),
                pa.field('total_messages_ingested', pa.int64()),
                pa.field('last_ingestion_timestamp', pa.timestamp('us')),
                pa.field('total_guilds_synced', pa.int64()),
                pa.field('total_channels_synced', pa.int64()),
                pa.field('failed_ingestions', pa.int64()),
                pa.field('last_error_message', pa.string()),
                pa.field('avg_messages_per_minute', pa.float64()),
                pa.field('storage_size_mb', pa.float64()),
                pa.field('created_at', pa.timestamp('us')),
                pa.field('updated_at', pa.timestamp('us'))
            ])
            
            self.stats_table = self.db.create_table(
                DISCORD_INGESTION_STATS_TABLE_NAME,
                schema=stats_schema,
                mode="overwrite"
            )
            
            logger.info("Discord LanceDB tables created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create Discord LanceDB tables: {e}")
            raise
    
    def _clean_content(self, content: str) -> str:
        """Clean message content for storage"""
        if not content:
            return ""
        
        # Remove Discord mention formatting
        cleaned = content
        
        # Replace user mentions with readable format
        import re
        cleaned = re.sub(r'<@!?(\d+)>', r'@user', cleaned)
        
        # Replace role mentions
        cleaned = re.sub(r'<@&(\d+)>', r'@role', cleaned)
        
        # Replace channel mentions
        cleaned = re.sub(r'<#(\d+)>', r'#channel', cleaned)
        
        # Remove emoji code blocks
        cleaned = re.sub(r'<:(\w+):\d+>', r':\1:', cleaned)
        cleaned = re.sub(r'<a:(\w+):\d+>', r':\1:', cleaned)
        
        # Clean up extra whitespace
        cleaned = ' '.join(cleaned.split())
        
        return cleaned
    
    def _generate_content_hash(self, content: str) -> str:
        """Generate hash for content deduplication"""
        if not content:
            return ""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    
    def _generate_message_id(self, user_id: str, message_id: str) -> str:
        """Generate unique message ID"""
        return f"{user_id}:{message_id}"
    
    async def get_user_settings(self, user_id: str) -> DiscordMemorySettings:
        """Get user Discord memory settings"""
        try:
            if LANCEDB_AVAILABLE and self.settings_table:
                # Query from LanceDB
                results = self.settings_table.search().where(f"user_id = '{user_id}'").to_list()
                if results:
                    settings_data = results[0]
                    return DiscordMemorySettings(**settings_data)
            
            # Mock database or no results
            default_settings = DiscordMemorySettings(
                user_id=user_id,
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat()
            )
            
            return default_settings
            
        except Exception as e:
            logger.error(f"Error getting Discord user settings: {e}")
            return DiscordMemorySettings(user_id=user_id)
    
    async def save_user_settings(self, settings: DiscordMemorySettings) -> bool:
        """Save user Discord memory settings"""
        try:
            settings.updated_at = datetime.utcnow().isoformat()
            
            if not settings.created_at:
                settings.created_at = settings.updated_at
            
            if LANCEDB_AVAILABLE and self.settings_table:
                # Convert to dict and save
                settings_dict = asdict(settings)
                
                # Remove existing settings
                self.settings_table.delete(f"user_id = '{settings.user_id}'")
                
                # Add new settings
                self.settings_table.add([settings_dict])
                
                logger.info(f"Discord user settings saved for {settings.user_id}")
                return True
            else:
                # Mock database
                existing_index = None
                for i, existing_settings in enumerate(self.settings_table.data):
                    if existing_settings.get('user_id') == settings.user_id:
                        existing_index = i
                        break
                
                settings_dict = asdict(settings)
                if existing_index is not None:
                    self.settings_table.data[existing_index] = settings_dict
                else:
                    self.settings_table.data.append(settings_dict)
                
                return True
                
        except Exception as e:
            logger.error(f"Error saving Discord user settings: {e}")
            return False
    
    async def get_ingestion_stats(self, user_id: str) -> DiscordIngestionStats:
        """Get Discord ingestion statistics"""
        try:
            if LANCEDB_AVAILABLE and self.stats_table:
                # Query from LanceDB
                results = self.stats_table.search().where(f"user_id = '{user_id}'").to_list()
                if results:
                    stats_data = results[0]
                    return DiscordIngestionStats(**stats_data)
            
            # Mock database or no results
            default_stats = DiscordIngestionStats(
                user_id=user_id,
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat()
            )
            
            return default_stats
            
        except Exception as e:
            logger.error(f"Error getting Discord ingestion stats: {e}")
            return DiscordIngestionStats(user_id=user_id)
    
    async def update_ingestion_stats(self, user_id: str, messages_count: int = 0, 
                                  guilds_count: int = 0, channels_count: int = 0,
                                  error_message: str = None) -> bool:
        """Update Discord ingestion statistics"""
        try:
            # Get existing stats
            stats = await self.get_ingestion_stats(user_id)
            
            # Update stats
            stats.total_messages_ingested += messages_count
            stats.total_guilds_synced = max(stats.total_guilds_synced, guilds_count)
            stats.total_channels_synced = max(stats.total_channels_synced, channels_count)
            stats.last_ingestion_timestamp = datetime.utcnow().isoformat()
            stats.updated_at = datetime.utcnow().isoformat()
            
            if error_message:
                stats.failed_ingestions += 1
                stats.last_error_message = error_message
            
            # Save stats
            stats_dict = asdict(stats)
            
            if LANCEDB_AVAILABLE and self.stats_table:
                # Remove existing stats
                self.stats_table.delete(f"user_id = '{user_id}'")
                
                # Add new stats
                self.stats_table.add([stats_dict])
            else:
                # Mock database
                existing_index = None
                for i, existing_stats in enumerate(self.stats_table.data):
                    if existing_stats.get('user_id') == user_id:
                        existing_index = i
                        break
                
                if existing_index is not None:
                    self.stats_table.data[existing_index] = stats_dict
                else:
                    self.stats_table.data.append(stats_dict)
            
            logger.info(f"Discord ingestion stats updated for {user_id}: +{messages_count} messages")
            return True
            
        except Exception as e:
            logger.error(f"Error updating Discord ingestion stats: {e}")
            return False
    
    async def should_sync_user(self, user_id: str) -> bool:
        """Check if user should be synced based on settings"""
        try:
            settings = await self.get_user_settings(user_id)
            
            if not settings.ingestion_enabled:
                return False
            
            if settings.sync_in_progress:
                return False
            
            now = datetime.utcnow()
            
            if not settings.last_sync_timestamp:
                return True
            
            last_sync = datetime.fromisoformat(settings.last_sync_timestamp.replace('Z', '+00:00'))
            
            # Check sync frequency
            if settings.sync_frequency == "real-time":
                return True
            elif settings.sync_frequency == "hourly":
                return now - last_sync > timedelta(hours=1)
            elif settings.sync_frequency == "daily":
                return now - last_sync > timedelta(days=1)
            elif settings.sync_frequency == "weekly":
                return now - last_sync > timedelta(weeks=1)
            elif settings.sync_frequency == "manual":
                return False
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking Discord sync requirements: {e}")
            return False
    
    def _should_include_guild(self, guild_id: str, settings: DiscordMemorySettings) -> bool:
        """Check if guild should be included in sync"""
        if settings.exclude_guilds and guild_id in settings.exclude_guilds:
            return False
        
        if settings.include_guilds and guild_id not in settings.include_guilds:
            return False
        
        return True
    
    def _should_include_channel(self, channel_id: str, channel_type: str, 
                             settings: DiscordMemorySettings) -> bool:
        """Check if channel should be included in sync"""
        if settings.exclude_channels and channel_id in settings.exclude_channels:
            return False
        
        if settings.include_channels and channel_id not in settings.include_channels:
            return False
        
        # Check channel types
        if not settings.include_dm_channels and channel_type in ['1', '3']:  # DM, Group DM
            return False
        
        if not settings.include_private_channels and channel_type not in ['0']:  # Public text
            return False
        
        return True
    
    async def ingest_discord_messages(self, user_id: str, force_sync: bool = False) -> Dict[str, Any]:
        """Ingest Discord messages for user"""
        try:
            if not DISCORD_SERVICE_AVAILABLE or not DISCORD_DB_AVAILABLE:
                return {
                    'success': False,
                    'error': 'Discord service or database not available',
                    'error_type': 'service_unavailable'
                }
            
            # Check if sync is needed
            if not force_sync and not await self.should_sync_user(user_id):
                return {
                    'success': False,
                    'error': 'Sync not required or already in progress',
                    'error_type': 'sync_not_required'
                }
            
            # Get user settings
            settings = await self.get_user_settings(user_id)
            settings.sync_in_progress = True
            settings.error_message = None
            await self.save_user_settings(settings)
            
            # Get user tokens
            tokens = await get_discord_tokens(None, user_id)
            if not tokens:
                return {
                    'success': False,
                    'error': 'Discord authentication required',
                    'error_type': 'auth_required'
                }
            
            # Initialize Discord service
            discord_service = discord_enhanced_service
            
            # Get user guilds
            guilds = await discord_service.get_user_guilds(user_id, limit=200)
            
            # Filter guilds based on settings
            guilds_to_sync = []
            for guild in guilds:
                if self._should_include_guild(guild.id, settings):
                    guilds_to_sync.append(guild)
            
            total_messages = 0
            total_guilds = len(guilds_to_sync)
            total_channels = 0
            batch_id = f"{user_id}:{datetime.utcnow().isoformat()}"
            
            # Sync each guild
            for guild in guilds_to_sync:
                try:
                    # Get guild channels
                    channels = await discord_service.get_guild_channels(user_id, guild.id)
                    
                    # Filter channels based on settings
                    channels_to_sync = []
                    for channel in channels:
                        if self._should_include_channel(channel.id, str(channel.type), settings):
                            channels_to_sync.append(channel)
                    
                    total_channels += len(channels_to_sync)
                    
                    # Sync messages from each channel
                    for channel in channels_to_sync:
                        try:
                            # Get messages from channel
                            messages = await discord_service.get_channel_messages(
                                user_id=user_id,
                                channel_id=channel.id,
                                limit=settings.max_messages_per_channel
                            )
                            
                            # Process and store messages
                            batch_messages = []
                            
                            for message in messages:
                                # Create memory record
                                memory_record = DiscordMessageMemory(
                                    id=self._generate_message_id(user_id, message.id),
                                    user_id=user_id,
                                    guild_id=guild.id,
                                    guild_name=guild.name,
                                    channel_id=channel.id,
                                    channel_name=channel.name,
                                    channel_type=str(channel.type),
                                    message_id=message.id,
                                    author_id=message.author.get('id', ''),
                                    author_username=message.author.get('username', ''),
                                    author_display_name=message.author.get('display_name', '') or 
                                                    message.author.get('username', ''),
                                    author_bot=message.author.get('bot', False),
                                    content=message.content or '',
                                    content_clean=self._clean_content(message.content or ''),
                                    timestamp=message.timestamp,
                                    edited_timestamp=message.edited_timestamp or '',
                                    message_type=message.type,
                                    tts=message.tts,
                                    mention_everyone=message.mention_everyone,
                                    mentions=[mention.get('id', '') for mention in message.mentions],
                                    mention_roles=message.mention_roles,
                                    attachments=json.dumps([att.get('url', '') for att in message.attachments]),
                                    embeds=json.dumps([emb.get('title', '') for emb in message.embeds]),
                                    reactions=json.dumps([react.get('emoji', {}).get('name', '') for react in message.reactions]),
                                    reply_to_message_id=message.message_reference.get('message_id') if message.message_reference else '',
                                    reply_to_author='',
                                    reply_to_content='',
                                    thread_id='',
                                    webhook_id=message.webhook_id or '',
                                    pinned=message.pinned,
                                    content_hash=self._generate_content_hash(message.content or ''),
                                    processed_at=datetime.utcnow().isoformat(),
                                    batch_id=batch_id,
                                    metadata={
                                        'source': 'discord',
                                        'ingested_at': datetime.utcnow().isoformat(),
                                        'settings_version': '1.0'
                                    }
                                )
                                
                                batch_messages.append(memory_record)
                                
                                # Handle reply information
                                if message.message_reference and message.message_reference.get('message_id'):
                                    reply_message_id = message.message_reference.get('message_id')
                                    # In real implementation, you'd fetch the reply message
                                    pass
                            
                            # Store batch in LanceDB
                            if batch_messages:
                                await self._store_messages_batch(batch_messages)
                                total_messages += len(batch_messages)
                            
                        except Exception as e:
                            logger.error(f"Error processing Discord channel {channel.id}: {e}")
                            continue
                
                except Exception as e:
                    logger.error(f"Error processing Discord guild {guild.id}: {e}")
                    continue
            
            # Update settings and stats
            settings.last_sync_timestamp = datetime.utcnow().isoformat()
            settings.sync_in_progress = False
            
            # Set next sync timestamp
            now = datetime.utcnow()
            if settings.sync_frequency == "hourly":
                settings.next_sync_timestamp = (now + timedelta(hours=1)).isoformat()
            elif settings.sync_frequency == "daily":
                settings.next_sync_timestamp = (now + timedelta(days=1)).isoformat()
            elif settings.sync_frequency == "weekly":
                settings.next_sync_timestamp = (now + timedelta(weeks=1)).isoformat()
            
            await self.save_user_settings(settings)
            
            # Update ingestion stats
            await self.update_ingestion_stats(
                user_id=user_id,
                messages_count=total_messages,
                guilds_count=total_guilds,
                channels_count=total_channels
            )
            
            logger.info(f"Discord ingestion completed for {user_id}: {total_messages} messages from {total_guilds} guilds")
            
            return {
                'success': True,
                'messages_ingested': total_messages,
                'guilds_synced': total_guilds,
                'channels_synced': total_channels,
                'batch_id': batch_id,
                'next_sync': settings.next_sync_timestamp,
                'sync_frequency': settings.sync_frequency
            }
            
        except Exception as e:
            logger.error(f"Error in Discord ingestion: {e}")
            
            # Update settings with error
            try:
                settings = await self.get_user_settings(user_id)
                settings.sync_in_progress = False
                settings.error_message = str(e)
                await self.save_user_settings(settings)
                
                await self.update_ingestion_stats(user_id, error_message=str(e))
            except:
                pass
            
            return {
                'success': False,
                'error': str(e),
                'error_type': 'ingestion_error'
            }
    
    async def _store_messages_batch(self, messages: List[DiscordMessageMemory]) -> bool:
        """Store batch of messages in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.memory_table:
                # Convert to LanceDB format
                batch_data = [msg.to_lancedb_schema() for msg in messages]
                
                # Add batch to table
                self.memory_table.add(batch_data)
                
                logger.info(f"Stored {len(messages)} Discord messages in LanceDB")
                return True
            else:
                # Mock database
                batch_data = [asdict(msg) for msg in messages]
                self.memory_table.data.extend(batch_data)
                
                logger.info(f"Stored {len(messages)} Discord messages in mock DB")
                return True
                
        except Exception as e:
            logger.error(f"Error storing Discord messages batch: {e}")
            return False
    
    async def search_discord_messages(self, user_id: str, query: str, 
                                    limit: int = 50, guild_id: str = None,
                                    channel_id: str = None, date_from: str = None,
                                    date_to: str = None) -> List[Dict[str, Any]]:
        """Search Discord messages in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.memory_table:
                # Build query
                where_clauses = [f"user_id = '{user_id}'"]
                
                if guild_id:
                    where_clauses.append(f"guild_id = '{guild_id}'")
                
                if channel_id:
                    where_clauses.append(f"channel_id = '{channel_id}'")
                
                if date_from:
                    where_clauses.append(f"timestamp >= '{date_from}'")
                
                if date_to:
                    where_clauses.append(f"timestamp <= '{date_to}'")
                
                where_clause = " AND ".join(where_clauses)
                
                # Perform search
                if query:
                    # Text search
                    results = (self.memory_table
                             .search(query)
                             .where(where_clause)
                             .limit(limit)
                             .to_list())
                else:
                    # Filter only
                    results = (self.memory_table
                             .search()
                             .where(where_clause)
                             .limit(limit)
                             .to_list())
                
                return results
            else:
                # Mock database search
                all_messages = self.memory_table.data
                
                # Filter by user
                filtered_messages = [msg for msg in all_messages if msg.get('user_id') == user_id]
                
                # Apply additional filters
                if guild_id:
                    filtered_messages = [msg for msg in filtered_messages if msg.get('guild_id') == guild_id]
                
                if channel_id:
                    filtered_messages = [msg for msg in filtered_messages if msg.get('channel_id') == channel_id]
                
                if query:
                    filtered_messages = [msg for msg in filtered_messages 
                                      if query.lower() in msg.get('content', '').lower() or 
                                         query.lower() in msg.get('content_clean', '').lower()]
                
                # Sort by timestamp and limit
                filtered_messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                
                return filtered_messages[:limit]
                
        except Exception as e:
            logger.error(f"Error searching Discord messages: {e}")
            return []
    
    async def get_sync_status(self, user_id: str) -> Dict[str, Any]:
        """Get current sync status for user"""
        try:
            settings = await self.get_user_settings(user_id)
            stats = await self.get_ingestion_stats(user_id)
            
            # Calculate next sync time
            next_sync_time = None
            if settings.next_sync_timestamp:
                try:
                    next_sync_time = datetime.fromisoformat(settings.next_sync_timestamp.replace('Z', '+00:00'))
                except:
                    pass
            
            # Check if should sync
            should_sync = await self.should_sync_user(user_id)
            
            return {
                'user_id': user_id,
                'ingestion_enabled': settings.ingestion_enabled,
                'sync_frequency': settings.sync_frequency,
                'sync_in_progress': settings.sync_in_progress,
                'last_sync_timestamp': settings.last_sync_timestamp,
                'next_sync_timestamp': settings.next_sync_timestamp,
                'should_sync_now': should_sync,
                'error_message': settings.error_message,
                'stats': {
                    'total_messages_ingested': stats.total_messages_ingested,
                    'total_guilds_synced': stats.total_guilds_synced,
                    'total_channels_synced': stats.total_channels_synced,
                    'failed_ingestions': stats.failed_ingestions,
                    'last_ingestion_timestamp': stats.last_ingestion_timestamp,
                    'avg_messages_per_minute': stats.avg_messages_per_minute,
                    'storage_size_mb': stats.storage_size_mb
                },
                'settings': {
                    'include_guilds': settings.include_guilds or [],
                    'exclude_guilds': settings.exclude_guilds or [],
                    'include_channels': settings.include_channels or [],
                    'exclude_channels': settings.exclude_channels or [],
                    'include_dm_channels': settings.include_dm_channels,
                    'include_private_channels': settings.include_private_channels,
                    'max_messages_per_channel': settings.max_messages_per_channel,
                    'semantic_search_enabled': settings.semantic_search_enabled,
                    'metadata_extraction_enabled': settings.metadata_extraction_enabled
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting Discord sync status: {e}")
            return {
                'user_id': user_id,
                'error': str(e),
                'error_type': 'status_error'
            }
    
    async def delete_user_data(self, user_id: str) -> bool:
        """Delete all Discord data for user"""
        try:
            # Delete from memory table
            if LANCEDB_AVAILABLE and self.memory_table:
                self.memory_table.delete(f"user_id = '{user_id}'")
            else:
                # Mock database
                self.memory_table.data = [msg for msg in self.memory_table.data 
                                       if msg.get('user_id') != user_id]
            
            # Delete settings
            if LANCEDB_AVAILABLE and self.settings_table:
                self.settings_table.delete(f"user_id = '{user_id}'")
            else:
                # Mock database
                self.settings_table.data = [settings for settings in self.settings_table.data 
                                          if settings.get('user_id') != user_id]
            
            # Delete stats
            if LANCEDB_AVAILABLE and self.stats_table:
                self.stats_table.delete(f"user_id = '{user_id}'")
            else:
                # Mock database
                self.stats_table.data = [stats for stats in self.stats_table.data 
                                       if stats.get('user_id') != user_id]
            
            logger.info(f"All Discord data deleted for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting Discord user data: {e}")
            return False

# Create singleton instance
discord_lancedb_service = DiscordLanceDBIngestionService()