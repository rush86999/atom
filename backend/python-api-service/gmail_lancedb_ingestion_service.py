"""
Gmail LanceDB Ingestion Service
Complete Gmail email workflow memory ingestion with user controls
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

# Import enhanced Gmail service
try:
    from gmail_enhanced_service import gmail_enhanced_service
    GMAIL_SERVICE_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Gmail service not available: {e}")
    GMAIL_SERVICE_AVAILABLE = False

# Import encryption utilities
try:
    from atom_encryption import encrypt_data, decrypt_data
    ENCRYPTION_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Encryption not available: {e}")
    ENCRYPTION_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

# Gmail memory configuration
GMAIL_MEMORY_TABLE_NAME = "gmail_memory"
GMAIL_USER_SETTINGS_TABLE_NAME = "gmail_user_settings"
GMAIL_INGESTION_STATS_TABLE_NAME = "gmail_ingestion_stats"

@dataclass
class GmailMemorySettings:
    """User-controlled Gmail memory settings"""
    user_id: str
    ingestion_enabled: bool = True
    sync_frequency: str = "hourly"  # real-time, hourly, daily, weekly, manual
    data_retention_days: int = 365
    include_labels: List[str] = None
    exclude_labels: List[str] = None
    include_threads: bool = True
    include_drafts: bool = False
    include_sent: bool = True
    include_received: bool = True
    max_messages_per_sync: int = 1000
    max_attachment_size_mb: int = 25
    include_attachments: bool = True
    index_attachments: bool = False
    search_enabled: bool = True
    semantic_search_enabled: bool = True
    metadata_extraction_enabled: bool = True
    thread_tracking_enabled: bool = True
    contact_analysis_enabled: bool = True
    last_sync_timestamp: str = None
    next_sync_timestamp: str = None
    sync_in_progress: bool = False
    error_message: str = None
    created_at: str = None
    updated_at: str = None

@dataclass
class GmailMessageMemory:
    """Gmail message data for LanceDB storage"""
    id: str
    user_id: str
    thread_id: str
    message_id: str
    subject: str
    from_email: str
    from_name: str
    to_emails: List[str]
    cc_emails: List[str]
    bcc_emails: List[str]
    date: str
    body_text: str
    body_html: str
    snippet: str
    labels: List[str]
    is_read: bool
    is_starred: bool
    is_draft: bool
    is_sent: bool
    is_inbox: bool
    is_important: bool
    attachment_count: int
    attachment_size_total: int
    size: int
    history_id: str
    gmail_thread_id: str
    processed_at: str
    batch_id: str
    
    def to_lancedb_schema(self) -> Dict[str, Any]:
        """Convert to LanceDB schema"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'thread_id': self.thread_id,
            'message_id': self.message_id,
            'subject': self.subject,
            'from_email': self.from_email,
            'from_name': self.from_name,
            'to_emails': json.dumps(self.to_emails),
            'cc_emails': json.dumps(self.cc_emails),
            'bcc_emails': json.dumps(self.bcc_emails),
            'date': self.date,
            'body_text': self.body_text,
            'body_html': self.body_html,
            'snippet': self.snippet,
            'labels': json.dumps(self.labels),
            'is_read': self.is_read,
            'is_starred': self.is_starred,
            'is_draft': self.is_draft,
            'is_sent': self.is_sent,
            'is_inbox': self.is_inbox,
            'is_important': self.is_important,
            'attachment_count': self.attachment_count,
            'attachment_size_total': self.attachment_size_total,
            'size': self.size,
            'history_id': self.history_id,
            'gmail_thread_id': self.gmail_thread_id,
            'processed_at': self.processed_at,
            'batch_id': self.batch_id
        }

@dataclass
class GmailThreadMemory:
    """Gmail thread data for LanceDB storage"""
    id: str
    user_id: str
    thread_id: str
    subject: str
    message_count: int
    participant_emails: List[str]
    first_message_date: str
    last_message_date: str
    is_unread: bool
    labels: List[str]
    total_size: int
    total_attachments: int
    last_message_snippet: str
    processed_at: str
    batch_id: str
    
    def to_lancedb_schema(self) -> Dict[str, Any]:
        """Convert to LanceDB schema"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'thread_id': self.thread_id,
            'subject': self.subject,
            'message_count': self.message_count,
            'participant_emails': json.dumps(self.participant_emails),
            'first_message_date': self.first_message_date,
            'last_message_date': self.last_message_date,
            'is_unread': self.is_unread,
            'labels': json.dumps(self.labels),
            'total_size': self.total_size,
            'total_attachments': self.total_attachments,
            'last_message_snippet': self.last_message_snippet,
            'processed_at': self.processed_at,
            'batch_id': self.batch_id
        }

@dataclass
class GmailAttachmentMemory:
    """Gmail attachment data for LanceDB storage"""
    id: str
    user_id: str
    message_id: str
    thread_id: str
    filename: str
    mime_type: str
    size: int
    attachment_id: str
    content_hash: str
    is_indexed: bool
    indexed_at: str
    metadata: Dict[str, Any]
    processed_at: str
    batch_id: str
    
    def to_lancedb_schema(self) -> Dict[str, Any]:
        """Convert to LanceDB schema"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'message_id': self.message_id,
            'thread_id': self.thread_id,
            'filename': self.filename,
            'mime_type': self.mime_type,
            'size': self.size,
            'attachment_id': self.attachment_id,
            'content_hash': self.content_hash,
            'is_indexed': self.is_indexed,
            'indexed_at': self.indexed_at,
            'metadata': json.dumps(self.metadata),
            'processed_at': self.processed_at,
            'batch_id': self.batch_id
        }

@dataclass
class GmailContactMemory:
    """Gmail contact data for LanceDB storage"""
    id: str
    user_id: str
    email: str
    name: str
    avatar_url: str
    interaction_count: int
    first_interaction: str
    last_interaction: str
    sent_count: int
    received_count: int
    common_subjects: List[str]
    common_labels: List[str]
    metadata: Dict[str, Any]
    processed_at: str
    batch_id: str
    
    def to_lancedb_schema(self) -> Dict[str, Any]:
        """Convert to LanceDB schema"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'email': self.email,
            'name': self.name,
            'avatar_url': self.avatar_url,
            'interaction_count': self.interaction_count,
            'first_interaction': self.first_interaction,
            'last_interaction': self.last_interaction,
            'sent_count': self.sent_count,
            'received_count': self.received_count,
            'common_subjects': json.dumps(self.common_subjects),
            'common_labels': json.dumps(self.common_labels),
            'metadata': json.dumps(self.metadata),
            'processed_at': self.processed_at,
            'batch_id': self.batch_id
        }

@dataclass
class GmailIngestionStats:
    """Gmail ingestion statistics"""
    user_id: str
    total_messages_ingested: int = 0
    total_threads_ingested: int = 0
    total_attachments_ingested: int = 0
    total_contacts_processed: int = 0
    last_ingestion_timestamp: str = None
    total_size_mb: float = 0.0
    failed_ingestions: int = 0
    last_error_message: str = None
    avg_messages_per_sync: float = 0.0
    avg_processing_time_ms: float = 0.0
    created_at: str = None
    updated_at: str = None

class GmailLanceDBIngestionService:
    """Gmail LanceDB ingestion service with user controls"""
    
    def __init__(self, lancedb_uri: str = None):
        self.lancedb_uri = lancedb_uri or os.getenv('LANCEDB_URI', 'lancedb/gmail_memory')
        self.db = None
        self.messages_table = None
        self.threads_table = None
        self.attachments_table = None
        self.contacts_table = None
        self.settings_table = None
        self.stats_table = None
        self._init_lancedb()
        
        # Ingestion state
        self.ingestion_workers = {}
        self.ingestion_locks = {}
        
        # MIME type handling
        self.indexable_mime_types = {
            'text/plain', 'text/html', 'text/csv', 'text/xml',
            'application/json', 'application/xml',
            'application/pdf',  # Can be indexed with OCR
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'image/jpeg', 'image/png', 'image/gif', 'image/webp'  # Can be indexed with OCR
        }
    
    def _init_lancedb(self):
        """Initialize LanceDB connection"""
        try:
            if LANCEDB_AVAILABLE:
                self.db = lancedb.connect(self.lancedb_uri)
                self._create_tables()
                logger.info(f"Gmail LanceDB service initialized: {self.lancedb_uri}")
            else:
                logger.warning("LanceDB not available - using mock database")
                self._init_mock_database()
        except Exception as e:
            logger.error(f"Failed to initialize Gmail LanceDB: {e}")
            self._init_mock_database()
    
    def _init_mock_database(self):
        """Initialize mock database for testing"""
        self.db = type('MockDB', (), {})()
        self.messages_table = type('MockTable', (), {})()
        self.threads_table = type('MockTable', (), {})()
        self.attachments_table = type('MockTable', (), {})()
        self.contacts_table = type('MockTable', (), {})()
        self.settings_table = type('MockTable', (), {})()
        self.stats_table = type('MockTable', (), {})()
        self.messages_table.data = []
        self.threads_table.data = []
        self.attachments_table.data = []
        self.contacts_table.data = []
        self.settings_table.data = []
        self.stats_table.data = []
    
    def _create_tables(self):
        """Create LanceDB tables"""
        if not LANCEDB_AVAILABLE or not self.db:
            return
        
        try:
            # Gmail messages table schema
            messages_schema = pa.schema([
                pa.field('id', pa.string()),
                pa.field('user_id', pa.string()),
                pa.field('thread_id', pa.string()),
                pa.field('message_id', pa.string()),
                pa.field('subject', pa.string()),
                pa.field('from_email', pa.string()),
                pa.field('from_name', pa.string()),
                pa.field('to_emails', pa.list_(pa.string())),
                pa.field('cc_emails', pa.list_(pa.string())),
                pa.field('bcc_emails', pa.list_(pa.string())),
                pa.field('date', pa.timestamp('us')),
                pa.field('body_text', pa.string()),
                pa.field('body_html', pa.string()),
                pa.field('snippet', pa.string()),
                pa.field('labels', pa.list_(pa.string())),
                pa.field('is_read', pa.bool_()),
                pa.field('is_starred', pa.bool_()),
                pa.field('is_draft', pa.bool_()),
                pa.field('is_sent', pa.bool_()),
                pa.field('is_inbox', pa.bool_()),
                pa.field('is_important', pa.bool_()),
                pa.field('attachment_count', pa.int64()),
                pa.field('attachment_size_total', pa.int64()),
                pa.field('size', pa.int64()),
                pa.field('history_id', pa.string()),
                pa.field('gmail_thread_id', pa.string()),
                pa.field('processed_at', pa.timestamp('us')),
                pa.field('batch_id', pa.string())
            ])
            
            # Gmail threads table schema
            threads_schema = pa.schema([
                pa.field('id', pa.string()),
                pa.field('user_id', pa.string()),
                pa.field('thread_id', pa.string()),
                pa.field('subject', pa.string()),
                pa.field('message_count', pa.int64()),
                pa.field('participant_emails', pa.list_(pa.string())),
                pa.field('first_message_date', pa.timestamp('us')),
                pa.field('last_message_date', pa.timestamp('us')),
                pa.field('is_unread', pa.bool_()),
                pa.field('labels', pa.list_(pa.string())),
                pa.field('total_size', pa.int64()),
                pa.field('total_attachments', pa.int64()),
                pa.field('last_message_snippet', pa.string()),
                pa.field('processed_at', pa.timestamp('us')),
                pa.field('batch_id', pa.string())
            ])
            
            # Gmail attachments table schema
            attachments_schema = pa.schema([
                pa.field('id', pa.string()),
                pa.field('user_id', pa.string()),
                pa.field('message_id', pa.string()),
                pa.field('thread_id', pa.string()),
                pa.field('filename', pa.string()),
                pa.field('mime_type', pa.string()),
                pa.field('size', pa.int64()),
                pa.field('attachment_id', pa.string()),
                pa.field('content_hash', pa.string()),
                pa.field('is_indexed', pa.bool_()),
                pa.field('indexed_at', pa.timestamp('us')),
                pa.field('metadata', pa.string()),
                pa.field('processed_at', pa.timestamp('us')),
                pa.field('batch_id', pa.string())
            ])
            
            # Gmail contacts table schema
            contacts_schema = pa.schema([
                pa.field('id', pa.string()),
                pa.field('user_id', pa.string()),
                pa.field('email', pa.string()),
                pa.field('name', pa.string()),
                pa.field('avatar_url', pa.string()),
                pa.field('interaction_count', pa.int64()),
                pa.field('first_interaction', pa.timestamp('us')),
                pa.field('last_interaction', pa.timestamp('us')),
                pa.field('sent_count', pa.int64()),
                pa.field('received_count', pa.int64()),
                pa.field('common_subjects', pa.list_(pa.string())),
                pa.field('common_labels', pa.list_(pa.string())),
                pa.field('metadata', pa.string()),
                pa.field('processed_at', pa.timestamp('us')),
                pa.field('batch_id', pa.string())
            ])
            
            # Settings table schema
            settings_schema = pa.schema([
                pa.field('user_id', pa.string()),
                pa.field('ingestion_enabled', pa.bool_()),
                pa.field('sync_frequency', pa.string()),
                pa.field('data_retention_days', pa.int64()),
                pa.field('include_labels', pa.list_(pa.string())),
                pa.field('exclude_labels', pa.list_(pa.string())),
                pa.field('include_threads', pa.bool_()),
                pa.field('include_drafts', pa.bool_()),
                pa.field('include_sent', pa.bool_()),
                pa.field('include_received', pa.bool_()),
                pa.field('max_messages_per_sync', pa.int64()),
                pa.field('max_attachment_size_mb', pa.int64()),
                pa.field('include_attachments', pa.bool_()),
                pa.field('index_attachments', pa.bool_()),
                pa.field('search_enabled', pa.bool_()),
                pa.field('semantic_search_enabled', pa.bool_()),
                pa.field('metadata_extraction_enabled', pa.bool_()),
                pa.field('thread_tracking_enabled', pa.bool_()),
                pa.field('contact_analysis_enabled', pa.bool_()),
                pa.field('last_sync_timestamp', pa.timestamp('us')),
                pa.field('next_sync_timestamp', pa.timestamp('us')),
                pa.field('sync_in_progress', pa.bool_()),
                pa.field('error_message', pa.string()),
                pa.field('created_at', pa.timestamp('us')),
                pa.field('updated_at', pa.timestamp('us'))
            ])
            
            # Stats table schema
            stats_schema = pa.schema([
                pa.field('user_id', pa.string()),
                pa.field('total_messages_ingested', pa.int64()),
                pa.field('total_threads_ingested', pa.int64()),
                pa.field('total_attachments_ingested', pa.int64()),
                pa.field('total_contacts_processed', pa.int64()),
                pa.field('last_ingestion_timestamp', pa.timestamp('us')),
                pa.field('total_size_mb', pa.float64()),
                pa.field('failed_ingestions', pa.int64()),
                pa.field('last_error_message', pa.string()),
                pa.field('avg_messages_per_sync', pa.float64()),
                pa.field('avg_processing_time_ms', pa.float64()),
                pa.field('created_at', pa.timestamp('us')),
                pa.field('updated_at', pa.timestamp('us'))
            ])
            
            # Create or open tables
            self.messages_table = self.db.create_table(
                "gmail_messages",
                schema=messages_schema,
                mode="overwrite"
            )
            
            self.threads_table = self.db.create_table(
                "gmail_threads",
                schema=threads_schema,
                mode="overwrite"
            )
            
            self.attachments_table = self.db.create_table(
                "gmail_attachments",
                schema=attachments_schema,
                mode="overwrite"
            )
            
            self.contacts_table = self.db.create_table(
                "gmail_contacts",
                schema=contacts_schema,
                mode="overwrite"
            )
            
            self.settings_table = self.db.create_table(
                GMAIL_USER_SETTINGS_TABLE_NAME,
                schema=settings_schema,
                mode="overwrite"
            )
            
            self.stats_table = self.db.create_table(
                GMAIL_INGESTION_STATS_TABLE_NAME,
                schema=stats_schema,
                mode="overwrite"
            )
            
            logger.info("Gmail LanceDB tables created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create Gmail LanceDB tables: {e}")
            raise
    
    def _calculate_content_hash(self, content: str) -> str:
        """Generate hash for content deduplication"""
        if not content:
            return ""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    
    def _generate_message_id(self, user_id: str, message_id: str) -> str:
        """Generate unique message ID"""
        return f"{user_id}:{message_id}"
    
    async def get_user_settings(self, user_id: str) -> GmailMemorySettings:
        """Get user Gmail memory settings"""
        try:
            if LANCEDB_AVAILABLE and self.settings_table:
                # Query from LanceDB
                results = self.settings_table.search().where(f"user_id = '{user_id}'").to_list()
                if results:
                    settings_data = results[0]
                    return GmailMemorySettings(**settings_data)
            
            # Mock database or no results
            default_settings = GmailMemorySettings(
                user_id=user_id,
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat()
            )
            
            return default_settings
            
        except Exception as e:
            logger.error(f"Error getting Gmail user settings: {e}")
            return GmailMemorySettings(user_id=user_id)
    
    async def save_user_settings(self, settings: GmailMemorySettings) -> bool:
        """Save user Gmail memory settings"""
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
                
                logger.info(f"Gmail user settings saved for {settings.user_id}")
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
            logger.error(f"Error saving Gmail user settings: {e}")
            return False
    
    async def get_ingestion_stats(self, user_id: str) -> GmailIngestionStats:
        """Get Gmail ingestion statistics"""
        try:
            if LANCEDB_AVAILABLE and self.stats_table:
                # Query from LanceDB
                results = self.stats_table.search().where(f"user_id = '{user_id}'").to_list()
                if results:
                    stats_data = results[0]
                    return GmailIngestionStats(**stats_data)
            
            # Mock database or no results
            default_stats = GmailIngestionStats(
                user_id=user_id,
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat()
            )
            
            return default_stats
            
        except Exception as e:
            logger.error(f"Error getting Gmail ingestion stats: {e}")
            return GmailIngestionStats(user_id=user_id)
    
    async def update_ingestion_stats(self, user_id: str, messages_count: int = 0,
                                  threads_count: int = 0, attachments_count: int = 0,
                                  contacts_count: int = 0, size_mb: float = 0.0,
                                  error_message: str = None) -> bool:
        """Update Gmail ingestion statistics"""
        try:
            # Get existing stats
            stats = await self.get_ingestion_stats(user_id)
            
            # Update stats
            stats.total_messages_ingested += messages_count
            stats.total_threads_ingested += threads_count
            stats.total_attachments_ingested += attachments_count
            stats.total_contacts_processed += contacts_count
            stats.total_size_mb += size_mb
            stats.last_ingestion_timestamp = datetime.utcnow().isoformat()
            stats.updated_at = datetime.utcnow().isoformat()
            
            if messages_count > 0:
                stats.avg_messages_per_sync = stats.total_messages_ingested / max(1, stats.total_threads_ingested)
            
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
            
            logger.info(f"Gmail ingestion stats updated for {user_id}: +{messages_count} messages, +{attachments_count} attachments")
            return True
            
        except Exception as e:
            logger.error(f"Error updating Gmail ingestion stats: {e}")
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
            logger.error(f"Error checking Gmail sync requirements: {e}")
            return False
    
    def _should_include_message(self, message: any, settings: GmailMemorySettings) -> bool:
        """Check if message should be included in sync"""
        # Check labels
        message_labels = message.labels or []
        
        if settings.exclude_labels:
            for exclude_label in settings.exclude_labels:
                if exclude_label in message_labels:
                    return False
        
        if settings.include_labels:
            for include_label in settings.include_labels:
                if include_label in message_labels:
                    break
            else:
                return False
        
        # Check message type
        if message.is_draft and not settings.include_drafts:
            return False
        
        if message.is_sent and not settings.include_sent:
            return False
        
        if message.is_inbox and not settings.include_received:
            return False
        
        return True
    
    def _can_index_attachment(self, mime_type: str, size: int, settings: GmailMemorySettings) -> bool:
        """Check if attachment should be indexed"""
        if not settings.include_attachments:
            return False
        
        if not settings.index_attachments:
            return False
        
        # Check size limit
        if size > settings.max_attachment_size_mb * 1024 * 1024:
            return False
        
        # Check MIME type
        if mime_type not in self.indexable_mime_types:
            return False
        
        return True
    
    async def ingest_gmail_messages(self, user_id: str, access_token: str,
                                  query: str = None, max_messages: int = None,
                                  force_sync: bool = False) -> Dict[str, Any]:
        """Ingest Gmail messages"""
        try:
            if not GMAIL_SERVICE_AVAILABLE:
                return {
                    'success': False,
                    'error': 'Gmail service not available',
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
            
            # Build query
            search_query = query or ''
            
            # Add label filters
            if settings.include_labels:
                label_query = ' OR '.join([f'label:{label}' for label in settings.include_labels])
                if search_query:
                    search_query = f'({search_query}) AND ({label_query})'
                else:
                    search_query = label_query
            
            # Get messages
            max_results = max_messages or settings.max_messages_per_sync
            
            messages_result = await gmail_enhanced_service.list_messages(
                access_token=access_token,
                max_results=max_results,
                query=search_query
            )
            
            if not messages_result.get('messages'):
                return {
                    'success': False,
                    'error': 'No messages found',
                    'error_type': 'no_messages'
                }
            
            # Process messages
            total_messages = 0
            total_threads = 0
            total_attachments = 0
            total_size = 0.0
            batch_id = f"{user_id}:{datetime.utcnow().isoformat()}"
            
            # Group messages by thread
            thread_messages = {}
            for message_data in messages_result['messages']:
                message_id = message_data.get('id', '')
                thread_id = message_data.get('thread_id', '')
                
                if thread_id not in thread_messages:
                    thread_messages[thread_id] = []
                
                thread_messages[thread_id].append(message_data)
            
            # Process each thread
            for thread_id, message_list in thread_messages.items():
                try:
                    # Get full messages
                    messages = []
                    for message_data in message_list:
                        message = await gmail_enhanced_service.get_message(
                            message_data.get('id', ''),
                            access_token
                        )
                        if message:
                            messages.append(message)
                    
                    if not messages:
                        continue
                    
                    # Filter messages based on settings
                    filtered_messages = [
                        msg for msg in messages if self._should_include_message(msg, settings)
                    ]
                    
                    if not filtered_messages:
                        continue
                    
                    # Process messages
                    for message in filtered_messages:
                        # Create message memory record
                        message_memory = GmailMessageMemory(
                            id=self._generate_message_id(user_id, message.id),
                            user_id=user_id,
                            thread_id=message.thread_id,
                            message_id=message.id,
                            subject=message.subject,
                            from_email=message.from_email,
                            from_name='',  # Could be parsed
                            to_emails=message.to_emails,
                            cc_emails=message.cc_emails,
                            bcc_emails=message.bcc_emails,
                            date=message.date,
                            body_text=message.body,
                            body_html=message.body_html,
                            snippet=message.snippet,
                            labels=message.labels,
                            is_read=message.is_read,
                            is_starred=message.is_starred,
                            is_draft=message.is_draft,
                            is_sent=message.is_sent,
                            is_inbox=message.is_inbox,
                            is_important=message.is_important,
                            attachment_count=len(message.attachments),
                            attachment_size_total=sum(att.get('size', 0) for att in message.attachments),
                            size=message.size,
                            history_id=message.history_id,
                            gmail_thread_id=message.thread_id,
                            processed_at=datetime.utcnow().isoformat(),
                            batch_id=batch_id
                        )
                        
                        # Store message
                        await self._store_message(message_memory)
                        total_messages += 1
                        total_size += message.size / (1024 * 1024)  # Convert to MB
                        
                        # Process attachments
                        for attachment_data in message.attachments:
                            attachment_memory = GmailAttachmentMemory(
                                id=f"{user_id}:{message.id}:{attachment_data.get('id', '')}",
                                user_id=user_id,
                                message_id=message.id,
                                thread_id=message.thread_id,
                                filename=attachment_data.get('filename', ''),
                                mime_type=attachment_data.get('mime_type', ''),
                                size=attachment_data.get('size', 0),
                                attachment_id=attachment_data.get('attachment_id', ''),
                                content_hash='',
                                is_indexed=self._can_index_attachment(
                                    attachment_data.get('mime_type', ''),
                                    attachment_data.get('size', 0),
                                    settings
                                ),
                                indexed_at='',
                                metadata={
                                    'source': 'gmail',
                                    'message_id': message.id,
                                    'thread_id': message.thread_id,
                                    'batch_id': batch_id,
                                    'ingested_at': datetime.utcnow().isoformat()
                                },
                                processed_at=datetime.utcnow().isoformat(),
                                batch_id=batch_id
                            )
                            
                            await self._store_attachment(attachment_memory)
                            total_attachments += 1
                    
                    # Create thread memory record
                    if settings.thread_tracking_enabled and len(messages) > 0:
                        sorted_messages = sorted(messages, key=lambda m: m.date)
                        first_message = sorted_messages[0]
                        last_message = sorted_messages[-1]
                        
                        participant_emails = set()
                        for msg in messages:
                            participant_emails.update(msg.to_emails)
                            participant_emails.update(msg.cc_emails)
                            participant_emails.update(msg.bcc_emails)
                        
                        thread_memory = GmailThreadMemory(
                            id=f"thread:{user_id}:{thread_id}",
                            user_id=user_id,
                            thread_id=thread_id,
                            subject=first_message.subject,
                            message_count=len(messages),
                            participant_emails=list(participant_emails),
                            first_message_date=first_message.date,
                            last_message_date=last_message.date,
                            is_unread=any(not msg.is_read for msg in messages),
                            labels=messages[0].labels,
                            total_size=sum(msg.size for msg in messages),
                            total_attachments=sum(len(msg.attachments) for msg in messages),
                            last_message_snippet=last_message.snippet,
                            processed_at=datetime.utcnow().isoformat(),
                            batch_id=batch_id
                        )
                        
                        await self._store_thread(thread_memory)
                        total_threads += 1
                    
                except Exception as e:
                    logger.error(f"Error processing Gmail thread {thread_id}: {e}")
                    continue
            
            # Process contacts
            if settings.contact_analysis_enabled:
                await self._process_contacts(user_id, access_token, batch_id)
            
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
                threads_count=total_threads,
                attachments_count=total_attachments,
                size_mb=total_size
            )
            
            logger.info(f"Gmail message ingestion completed for {user_id}: {total_messages} messages, {total_threads} threads")
            
            return {
                'success': True,
                'messages_ingested': total_messages,
                'threads_ingested': total_threads,
                'attachments_ingested': total_attachments,
                'total_size_mb': round(total_size, 2),
                'batch_id': batch_id,
                'next_sync': settings.next_sync_timestamp,
                'sync_frequency': settings.sync_frequency
            }
            
        except Exception as e:
            logger.error(f"Error in Gmail message ingestion: {e}")
            
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
    
    async def _store_message(self, message: GmailMessageMemory) -> bool:
        """Store message in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.messages_table:
                # Check if message already exists
                existing = (self.messages_table
                           .search()
                           .where(f"user_id = '{message.user_id}' AND message_id = '{message.message_id}'")
                           .to_list())
                
                if existing:
                    # Update existing message
                    self.messages_table.delete(f"user_id = '{message.user_id}' AND message_id = '{message.message_id}'")
                
                # Add new message
                message_data = [message.to_lancedb_schema()]
                self.messages_table.add(message_data)
                
                logger.info(f"Stored Gmail message: {message.message_id}")
                return True
            else:
                # Mock database
                # Remove existing
                self.messages_table.data = [
                    msg for msg in self.messages_table.data 
                    if not (msg.get('user_id') == message.user_id and msg.get('message_id') == message.message_id)
                ]
                
                # Add new
                self.messages_table.data.append(asdict(message))
                
                logger.info(f"Stored Gmail message in mock DB: {message.message_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error storing Gmail message: {e}")
            return False
    
    async def _store_thread(self, thread: GmailThreadMemory) -> bool:
        """Store thread in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.threads_table:
                # Check if thread already exists
                existing = (self.threads_table
                           .search()
                           .where(f"user_id = '{thread.user_id}' AND thread_id = '{thread.thread_id}'")
                           .to_list())
                
                if existing:
                    # Update existing thread
                    self.threads_table.delete(f"user_id = '{thread.user_id}' AND thread_id = '{thread.thread_id}'")
                
                # Add new thread
                thread_data = [thread.to_lancedb_schema()]
                self.threads_table.add(thread_data)
                
                logger.info(f"Stored Gmail thread: {thread.thread_id}")
                return True
            else:
                # Mock database
                # Remove existing
                self.threads_table.data = [
                    thr for thr in self.threads_table.data 
                    if not (thr.get('user_id') == thread.user_id and thr.get('thread_id') == thread.thread_id)
                ]
                
                # Add new
                self.threads_table.data.append(asdict(thread))
                
                logger.info(f"Stored Gmail thread in mock DB: {thread.thread_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error storing Gmail thread: {e}")
            return False
    
    async def _store_attachment(self, attachment: GmailAttachmentMemory) -> bool:
        """Store attachment in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.attachments_table:
                # Add attachment
                attachment_data = [attachment.to_lancedb_schema()]
                self.attachments_table.add(attachment_data)
                
                logger.info(f"Stored Gmail attachment: {attachment.filename}")
                return True
            else:
                # Mock database
                self.attachments_table.data.append(asdict(attachment))
                
                logger.info(f"Stored Gmail attachment in mock DB: {attachment.filename}")
                return True
                
        except Exception as e:
            logger.error(f"Error storing Gmail attachment: {e}")
            return False
    
    async def _process_contacts(self, user_id: str, access_token: str, batch_id: str) -> bool:
        """Process contacts from messages"""
        try:
            if not LANCEDB_AVAILABLE:
                return True  # Skip contact processing in mock mode
            
            # Get recent messages for contact analysis
            recent_messages_result = await gmail_enhanced_service.list_messages(
                access_token=access_token,
                max_results=1000,
                query='newer_than:30d'  # Last 30 days
            )
            
            contact_stats = {}
            
            for message_data in recent_messages_result.get('messages', []):
                message = await gmail_enhanced_service.get_message(
                    message_data.get('id', ''),
                    access_token
                )
                
                if not message:
                    continue
                
                # Process from email
                from_email = message.from_email
                if from_email and from_email not in contact_stats:
                    contact_stats[from_email] = {
                        'name': '',
                        'sent_count': 0,
                        'received_count': 0,
                        'common_subjects': [],
                        'common_labels': [],
                        'first_interaction': message.date,
                        'last_interaction': message.date
                    }
                
                if from_email:
                    contact_stats[from_email]['received_count'] += 1
                    contact_stats[from_email]['last_interaction'] = message.date
                    
                    if not contact_stats[from_email]['name']:
                        # Try to parse name from email
                        if '<' in from_email and '>' in from_email:
                            contact_stats[from_email]['name'] = from_email.split('<')[0].strip().strip('"')
                    
                    # Add to subjects
                    if message.subject not in contact_stats[from_email]['common_subjects']:
                        contact_stats[from_email]['common_subjects'].append(message.subject)
                    
                    # Add to labels
                    for label in message.labels:
                        if label not in contact_stats[from_email]['common_labels']:
                            contact_stats[from_email]['common_labels'].append(label)
            
            # Store contact records
            for email, stats in contact_stats.items():
                if stats['sent_count'] + stats['received_count'] > 1:  # Only store contacts with multiple interactions
                    contact_memory = GmailContactMemory(
                        id=f"contact:{user_id}:{hash(email)}",
                        user_id=user_id,
                        email=email,
                        name=stats['name'],
                        avatar_url='',
                        interaction_count=stats['sent_count'] + stats['received_count'],
                        first_interaction=stats['first_interaction'],
                        last_interaction=stats['last_interaction'],
                        sent_count=stats['sent_count'],
                        received_count=stats['received_count'],
                        common_subjects=stats['common_subjects'][:10],  # Limit to 10
                        common_labels=stats['common_labels'][:10],  # Limit to 10
                        metadata={
                            'source': 'gmail',
                            'analysis_date': datetime.utcnow().isoformat()
                        },
                        processed_at=datetime.utcnow().isoformat(),
                        batch_id=batch_id
                    )
                    
                    await self._store_contact(contact_memory)
            
            logger.info(f"Gmail contact processing completed for {user_id}: {len(contact_stats)} contacts")
            return True
            
        except Exception as e:
            logger.error(f"Error processing Gmail contacts: {e}")
            return False
    
    async def _store_contact(self, contact: GmailContactMemory) -> bool:
        """Store contact in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.contacts_table:
                # Check if contact already exists
                existing = (self.contacts_table
                           .search()
                           .where(f"user_id = '{contact.user_id}' AND email = '{contact.email}'")
                           .to_list())
                
                if existing:
                    # Update existing contact
                    self.contacts_table.delete(f"user_id = '{contact.user_id}' AND email = '{contact.email}'")
                
                # Add new contact
                contact_data = [contact.to_lancedb_schema()]
                self.contacts_table.add(contact_data)
                
                logger.info(f"Stored Gmail contact: {contact.email}")
                return True
            else:
                # Mock database
                # Remove existing
                self.contacts_table.data = [
                    cnt for cnt in self.contacts_table.data 
                    if not (cnt.get('user_id') == contact.user_id and cnt.get('email') == contact.email)
                ]
                
                # Add new
                self.contacts_table.data.append(asdict(contact))
                
                logger.info(f"Stored Gmail contact in mock DB: {contact.email}")
                return True
                
        except Exception as e:
            logger.error(f"Error storing Gmail contact: {e}")
            return False
    
    async def search_gmail_messages(self, user_id: str, query: str,
                                 label_filter: str = None, date_from: str = None,
                                 date_to: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Search Gmail messages in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.messages_table:
                # Build query
                where_clauses = [f"user_id = '{user_id}'"]
                
                if label_filter:
                    where_clauses.append(f"'{label_filter}' IN labels")
                
                if date_from:
                    where_clauses.append(f"date >= '{date_from}'")
                
                if date_to:
                    where_clauses.append(f"date <= '{date_to}'")
                
                where_clause = " AND ".join(where_clauses)
                
                # Perform search
                if query:
                    # Text search
                    results = (self.messages_table
                             .search(query)
                             .where(where_clause)
                             .limit(limit)
                             .to_list())
                else:
                    # Filter only
                    results = (self.messages_table
                             .search()
                             .where(where_clause)
                             .limit(limit)
                             .to_list())
                
                return results
            else:
                # Mock database search
                all_messages = self.messages_table.data
                
                # Filter by user
                filtered_messages = [msg for msg in all_messages if msg.get('user_id') == user_id]
                
                # Apply additional filters
                if label_filter:
                    filtered_messages = [msg for msg in filtered_messages 
                                      if label_filter in msg.get('labels', [])]
                
                if date_from:
                    filtered_messages = [msg for msg in filtered_messages 
                                      if msg.get('date') >= date_from]
                
                if date_to:
                    filtered_messages = [msg for msg in filtered_messages 
                                      if msg.get('date') <= date_to]
                
                if query:
                    filtered_messages = [msg for msg in filtered_messages 
                                      if query.lower() in msg.get('subject', '').lower() or 
                                         query.lower() in msg.get('body_text', '').lower()]
                
                # Sort by date and limit
                filtered_messages.sort(key=lambda x: x.get('date', ''), reverse=True)
                
                return filtered_messages[:limit]
                
        except Exception as e:
            logger.error(f"Error searching Gmail messages: {e}")
            return []
    
    async def search_gmail_threads(self, user_id: str, query: str,
                                label_filter: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Search Gmail threads in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.threads_table:
                # Build query
                where_clauses = [f"user_id = '{user_id}'"]
                
                if label_filter:
                    where_clauses.append(f"'{label_filter}' IN labels")
                
                where_clause = " AND ".join(where_clauses)
                
                # Perform search
                if query:
                    # Text search
                    results = (self.threads_table
                             .search(query)
                             .where(where_clause)
                             .limit(limit)
                             .to_list())
                else:
                    # Filter only
                    results = (self.threads_table
                             .search()
                             .where(where_clause)
                             .limit(limit)
                             .to_list())
                
                return results
            else:
                # Mock database search
                all_threads = self.threads_table.data
                
                # Filter by user
                filtered_threads = [thread for thread in all_threads if thread.get('user_id') == user_id]
                
                # Apply additional filters
                if label_filter:
                    filtered_threads = [thread for thread in filtered_threads 
                                      if label_filter in thread.get('labels', [])]
                
                if query:
                    filtered_threads = [thread for thread in filtered_threads 
                                      if query.lower() in thread.get('subject', '').lower()]
                
                # Sort by date and limit
                filtered_threads.sort(key=lambda x: x.get('last_message_date', ''), reverse=True)
                
                return filtered_threads[:limit]
                
        except Exception as e:
            logger.error(f"Error searching Gmail threads: {e}")
            return []
    
    async def search_gmail_contacts(self, user_id: str, query: str,
                                 limit: int = 50) -> List[Dict[str, Any]]:
        """Search Gmail contacts in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.contacts_table:
                # Build query
                where_clauses = [f"user_id = '{user_id}'"]
                where_clause = " AND ".join(where_clauses)
                
                # Perform search
                if query:
                    # Text search
                    results = (self.contacts_table
                             .search(query)
                             .where(where_clause)
                             .limit(limit)
                             .to_list())
                else:
                    # Filter only
                    results = (self.contacts_table
                             .search()
                             .where(where_clause)
                             .limit(limit)
                             .to_list())
                
                return results
            else:
                # Mock database search
                all_contacts = self.contacts_table.data
                
                # Filter by user
                filtered_contacts = [contact for contact in all_contacts if contact.get('user_id') == user_id]
                
                if query:
                    filtered_contacts = [contact for contact in filtered_contacts 
                                      if query.lower() in contact.get('email', '').lower() or 
                                         query.lower() in contact.get('name', '').lower()]
                
                # Sort by interaction count and limit
                filtered_contacts.sort(key=lambda x: x.get('interaction_count', 0), reverse=True)
                
                return filtered_contacts[:limit]
                
        except Exception as e:
            logger.error(f"Error searching Gmail contacts: {e}")
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
                    'total_threads_ingested': stats.total_threads_ingested,
                    'total_attachments_ingested': stats.total_attachments_ingested,
                    'total_contacts_processed': stats.total_contacts_processed,
                    'total_size_mb': stats.total_size_mb,
                    'failed_ingestions': stats.failed_ingestions,
                    'last_ingestion_timestamp': stats.last_ingestion_timestamp,
                    'avg_messages_per_sync': stats.avg_messages_per_sync,
                    'avg_processing_time_ms': stats.avg_processing_time_ms
                },
                'settings': {
                    'include_labels': settings.include_labels or [],
                    'exclude_labels': settings.exclude_labels or [],
                    'include_threads': settings.include_threads,
                    'include_drafts': settings.include_drafts,
                    'include_sent': settings.include_sent,
                    'include_received': settings.include_received,
                    'max_messages_per_sync': settings.max_messages_per_sync,
                    'max_attachment_size_mb': settings.max_attachment_size_mb,
                    'include_attachments': settings.include_attachments,
                    'index_attachments': settings.index_attachments,
                    'search_enabled': settings.search_enabled,
                    'semantic_search_enabled': settings.semantic_search_enabled,
                    'metadata_extraction_enabled': settings.metadata_extraction_enabled,
                    'thread_tracking_enabled': settings.thread_tracking_enabled,
                    'contact_analysis_enabled': settings.contact_analysis_enabled
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting Gmail sync status: {e}")
            return {
                'user_id': user_id,
                'error': str(e),
                'error_type': 'status_error'
            }
    
    async def delete_user_data(self, user_id: str) -> bool:
        """Delete all Gmail data for user"""
        try:
            # Delete from all tables
            if LANCEDB_AVAILABLE:
                self.messages_table.delete(f"user_id = '{user_id}'")
                self.threads_table.delete(f"user_id = '{user_id}'")
                self.attachments_table.delete(f"user_id = '{user_id}'")
                self.contacts_table.delete(f"user_id = '{user_id}'")
                self.settings_table.delete(f"user_id = '{user_id}'")
                self.stats_table.delete(f"user_id = '{user_id}'")
            else:
                # Mock database
                self.messages_table.data = [msg for msg in self.messages_table.data 
                                         if msg.get('user_id') != user_id]
                self.threads_table.data = [thr for thr in self.threads_table.data 
                                         if thr.get('user_id') != user_id]
                self.attachments_table.data = [att for att in self.attachments_table.data 
                                          if att.get('user_id') != user_id]
                self.contacts_table.data = [cnt for cnt in self.contacts_table.data 
                                         if cnt.get('user_id') != user_id]
                self.settings_table.data = [settings for settings in self.settings_table.data 
                                         if settings.get('user_id') != user_id]
                self.stats_table.data = [stats for stats in self.stats_table.data 
                                      if stats.get('user_id') != user_id]
            
            logger.info(f"All Gmail data deleted for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting Gmail user data: {e}")
            return False

# Create singleton instance
gmail_lancedb_service = GmailLanceDBIngestionService()