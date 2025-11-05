"""
Trello LanceDB Ingestion Service
Complete Trello project management memory ingestion with user controls
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

# Import enhanced Trello service
try:
    from trello_enhanced_service import trello_enhanced_service
    TRELLO_SERVICE_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Trello service not available: {e}")
    TRELLO_SERVICE_AVAILABLE = False

# Import encryption utilities
try:
    from atom_encryption import encrypt_data, decrypt_data
    ENCRYPTION_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Encryption not available: {e}")
    ENCRYPTION_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

# Trello memory configuration
TRELLO_MEMORY_TABLE_NAME = "trello_memory"
TRELLO_USER_SETTINGS_TABLE_NAME = "trello_user_settings"
TRELLO_INGESTION_STATS_TABLE_NAME = "trello_ingestion_stats"

@dataclass
class TrelloMemorySettings:
    """User-controlled Trello memory settings"""
    user_id: str
    ingestion_enabled: bool = True
    sync_frequency: str = "hourly"  # real-time, hourly, daily, weekly, manual
    data_retention_days: int = 365
    include_boards: List[str] = None
    exclude_boards: List[str] = None
    include_archived_boards: bool = False
    include_cards: bool = True
    include_lists: bool = True
    include_members: bool = True
    include_checklists: bool = True
    include_labels: bool = True
    include_attachments: bool = True
    include_activities: bool = True
    max_cards_per_sync: int = 1000
    max_activities_per_sync: int = 500
    sync_archived_cards: bool = False
    sync_card_attachments: bool = True
    index_card_content: bool = True
    search_enabled: bool = True
    semantic_search_enabled: bool = True
    metadata_extraction_enabled: bool = True
    board_tracking_enabled: bool = True
    member_analysis_enabled: bool = True
    last_sync_timestamp: str = None
    next_sync_timestamp: str = None
    sync_in_progress: bool = False
    error_message: str = None
    created_at: str = None
    updated_at: str = None

@dataclass
class TrelloBoardMemory:
    """Trello board data for LanceDB storage"""
    id: str
    user_id: str
    board_id: str
    name: str
    description: str
    closed: bool
    organization_id: str
    pinned: bool
    url: str
    short_url: str
    short_link: str
    date_last_activity: str
    date_last_view: str
    creation_date: str
    background_color: str
    background_image: str
    card_cover_images: bool
    calendar_feed_enabled: bool
    comment_permissions: str
    invitations_enabled: bool
    voting_permitted: bool
    level: str
    member_level: str
    starred: bool
    subscribed: bool
    preferences: Dict[str, Any]
    label_names: Dict[str, str]
    total_cards: int
    total_lists: int
    total_members: int
    total_checklists: int
    processed_at: str
    batch_id: str
    
    def to_lancedb_schema(self) -> Dict[str, Any]:
        """Convert to LanceDB schema"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'board_id': self.board_id,
            'name': self.name,
            'description': self.description,
            'closed': self.closed,
            'organization_id': self.organization_id,
            'pinned': self.pinned,
            'url': self.url,
            'short_url': self.short_url,
            'short_link': self.short_link,
            'date_last_activity': self.date_last_activity,
            'date_last_view': self.date_last_view,
            'creation_date': self.creation_date,
            'background_color': self.background_color,
            'background_image': self.background_image,
            'card_cover_images': self.card_cover_images,
            'calendar_feed_enabled': self.calendar_feed_enabled,
            'comment_permissions': self.comment_permissions,
            'invitations_enabled': self.invitations_enabled,
            'voting_permitted': self.voting_permitted,
            'level': self.level,
            'member_level': self.member_level,
            'starred': self.starred,
            'subscribed': self.subscribed,
            'preferences': json.dumps(self.preferences),
            'label_names': json.dumps(self.label_names),
            'total_cards': self.total_cards,
            'total_lists': self.total_lists,
            'total_members': self.total_members,
            'total_checklists': self.total_checklists,
            'processed_at': self.processed_at,
            'batch_id': self.batch_id
        }

@dataclass
class TrelloCardMemory:
    """Trello card data for LanceDB storage"""
    id: str
    user_id: str
    card_id: str
    board_id: str
    list_id: str
    name: str
    description: str
    closed: bool
    due_date: str
    due_complete: bool
    start_date: str
    position: float
    url: str
    short_url: str
    short_link: str
    subscribed: bool
    address: str
    labels: List[Dict[str, Any]]
    members: List[Dict[str, Any]]
    checklists: List[Dict[str, Any]]
    attachments: List[Dict[str, Any]]
    badges: Dict[str, Any]
    custom_fields: List[Dict[str, Any]]
    cover: Dict[str, Any]
    date_last_activity: str
    creation_date: str
    comments_count: int
    checklists_count: int
    check_items_completed: int
    check_items_total: int
    attachments_count: int
    members_count: int
    labels_count: int
    archived: bool
    metadata: Dict[str, Any]
    processed_at: str
    batch_id: str
    
    def to_lancedb_schema(self) -> Dict[str, Any]:
        """Convert to LanceDB schema"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'card_id': self.card_id,
            'board_id': self.board_id,
            'list_id': self.list_id,
            'name': self.name,
            'description': self.description,
            'closed': self.closed,
            'due_date': self.due_date,
            'due_complete': self.due_complete,
            'start_date': self.start_date,
            'position': self.position,
            'url': self.url,
            'short_url': self.short_url,
            'short_link': self.short_link,
            'subscribed': self.subscribed,
            'address': self.address,
            'labels': json.dumps(self.labels),
            'members': json.dumps(self.members),
            'checklists': json.dumps(self.checklists),
            'attachments': json.dumps(self.attachments),
            'badges': json.dumps(self.badges),
            'custom_fields': json.dumps(self.custom_fields),
            'cover': json.dumps(self.cover),
            'date_last_activity': self.date_last_activity,
            'creation_date': self.creation_date,
            'comments_count': self.comments_count,
            'checklists_count': self.checklists_count,
            'check_items_completed': self.check_items_completed,
            'check_items_total': self.check_items_total,
            'attachments_count': self.attachments_count,
            'members_count': self.members_count,
            'labels_count': self.labels_count,
            'archived': self.archived,
            'metadata': json.dumps(self.metadata),
            'processed_at': self.processed_at,
            'batch_id': self.batch_id
        }

@dataclass
class TrelloListMemory:
    """Trello list data for LanceDB storage"""
    id: str
    user_id: str
    list_id: str
    board_id: str
    name: str
    closed: bool
    position: float
    subscribed: bool
    soft_limit: int
    url: str
    short_url: str
    short_link: str
    total_cards: int
    closed_cards: int
    total_checklists: int
    total_attachments: int
    date_last_activity: str
    creation_date: str
    metadata: Dict[str, Any]
    processed_at: str
    batch_id: str
    
    def to_lancedb_schema(self) -> Dict[str, Any]:
        """Convert to LanceDB schema"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'list_id': self.list_id,
            'board_id': self.board_id,
            'name': self.name,
            'closed': self.closed,
            'position': self.position,
            'subscribed': self.subscribed,
            'soft_limit': self.soft_limit,
            'url': self.url,
            'short_url': self.short_url,
            'short_link': self.short_link,
            'total_cards': self.total_cards,
            'closed_cards': self.closed_cards,
            'total_checklists': self.total_checklists,
            'total_attachments': self.total_attachments,
            'date_last_activity': self.date_last_activity,
            'creation_date': self.creation_date,
            'metadata': json.dumps(self.metadata),
            'processed_at': self.processed_at,
            'batch_id': self.batch_id
        }

@dataclass
class TrelloMemberMemory:
    """Trello member data for LanceDB storage"""
    id: str
    user_id: str
    member_id: str
    username: str
    full_name: str
    email: str
    avatar_url: str
    avatar_hash: str
    bio: str
    status: str
    member_type: str
    confirmed: bool
    activity_blocked: bool
    login_allowed: bool
    boards_count: int
    organizations_count: int
    invited_boards_count: int
    total_cards_assigned: int
    total_cards_created: int
    total_checklists_completed: int
    total_comments: int
    total_votes: int
    first_activity: str
    last_activity: str
    member_since: str
    premium_features: List[str]
    preferences: Dict[str, Any]
    metadata: Dict[str, Any]
    processed_at: str
    batch_id: str
    
    def to_lancedb_schema(self) -> Dict[str, Any]:
        """Convert to LanceDB schema"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'member_id': self.member_id,
            'username': self.username,
            'full_name': self.full_name,
            'email': self.email,
            'avatar_url': self.avatar_url,
            'avatar_hash': self.avatar_hash,
            'bio': self.bio,
            'status': self.status,
            'member_type': self.member_type,
            'confirmed': self.confirmed,
            'activity_blocked': self.activity_blocked,
            'login_allowed': self.login_allowed,
            'boards_count': self.boards_count,
            'organizations_count': self.organizations_count,
            'invited_boards_count': self.invited_boards_count,
            'total_cards_assigned': self.total_cards_assigned,
            'total_cards_created': self.total_cards_created,
            'total_checklists_completed': self.total_checklists_completed,
            'total_comments': self.total_comments,
            'total_votes': self.total_votes,
            'first_activity': self.first_activity,
            'last_activity': self.last_activity,
            'member_since': self.member_since,
            'premium_features': json.dumps(self.premium_features),
            'preferences': json.dumps(self.preferences),
            'metadata': json.dumps(self.metadata),
            'processed_at': self.processed_at,
            'batch_id': self.batch_id
        }

@dataclass
class TrelloActivityMemory:
    """Trello activity data for LanceDB storage"""
    id: str
    user_id: str
    activity_id: str
    board_id: str
    card_id: str
    list_id: str
    member_id: str
    member_creator_id: str
    type: str
    date: str
    text: str
    translation_key: str
    data: Dict[str, Any]
    member: Dict[str, Any]
    member_creator: Dict[str, Any]
    board: Dict[str, Any]
    card: Dict[str, Any]
    list_data: Dict[str, Any]
    organization: Dict[str, Any]
    display: Dict[str, Any]
    app: Dict[str, Any]
    metadata: Dict[str, Any]
    processed_at: str
    batch_id: str
    
    def to_lancedb_schema(self) -> Dict[str, Any]:
        """Convert to LanceDB schema"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'activity_id': self.activity_id,
            'board_id': self.board_id,
            'card_id': self.card_id,
            'list_id': self.list_id,
            'member_id': self.member_id,
            'member_creator_id': self.member_creator_id,
            'type': self.type,
            'date': self.date,
            'text': self.text,
            'translation_key': self.translation_key,
            'data': json.dumps(self.data),
            'member': json.dumps(self.member),
            'member_creator': json.dumps(self.member_creator),
            'board': json.dumps(self.board),
            'card': json.dumps(self.card),
            'list_data': json.dumps(self.list_data),
            'organization': json.dumps(self.organization),
            'display': json.dumps(self.display),
            'app': json.dumps(self.app),
            'metadata': json.dumps(self.metadata),
            'processed_at': self.processed_at,
            'batch_id': self.batch_id
        }

@dataclass
class TrelloIngestionStats:
    """Trello ingestion statistics"""
    user_id: str
    total_boards_ingested: int = 0
    total_cards_ingested: int = 0
    total_lists_ingested: int = 0
    total_members_ingested: int = 0
    total_activities_ingested: int = 0
    total_checklists_ingested: int = 0
    total_attachments_ingested: int = 0
    last_ingestion_timestamp: str = None
    total_size_mb: float = 0.0
    failed_ingestions: int = 0
    last_error_message: str = None
    avg_cards_per_board: float = 0.0
    avg_processing_time_ms: float = 0.0
    created_at: str = None
    updated_at: str = None

class TrelloLanceDBIngestionService:
    """Trello LanceDB ingestion service with user controls"""
    
    def __init__(self, lancedb_uri: str = None):
        self.lancedb_uri = lancedb_uri or os.getenv('LANCEDB_URI', 'lancedb/trello_memory')
        self.db = None
        self.boards_table = None
        self.cards_table = None
        self.lists_table = None
        self.members_table = None
        self.activities_table = None
        self.settings_table = None
        self.stats_table = None
        self._init_lancedb()
        
        # Ingestion state
        self.ingestion_workers = {}
        self.ingestion_locks = {}
        
        # Card states
        self.card_states = {
            'todo': 'To Do',
            'in_progress': 'In Progress',
            'review': 'Review',
            'done': 'Done',
            'blocked': 'Blocked'
        }
        
        # Priority levels
        self.priority_levels = {
            'low': 1,
            'medium': 2,
            'high': 3,
            'critical': 4
        }
    
    def _init_lancedb(self):
        """Initialize LanceDB connection"""
        try:
            if LANCEDB_AVAILABLE:
                self.db = lancedb.connect(self.lancedb_uri)
                self._create_tables()
                logger.info(f"Trello LanceDB service initialized: {self.lancedb_uri}")
            else:
                logger.warning("LanceDB not available - using mock database")
                self._init_mock_database()
        except Exception as e:
            logger.error(f"Failed to initialize Trello LanceDB: {e}")
            self._init_mock_database()
    
    def _init_mock_database(self):
        """Initialize mock database for testing"""
        self.db = type('MockDB', (), {})()
        self.boards_table = type('MockTable', (), {})()
        self.cards_table = type('MockTable', (), {})()
        self.lists_table = type('MockTable', (), {})()
        self.members_table = type('MockTable', (), {})()
        self.activities_table = type('MockTable', (), {})()
        self.settings_table = type('MockTable', (), {})()
        self.stats_table = type('MockTable', (), {})()
        self.boards_table.data = []
        self.cards_table.data = []
        self.lists_table.data = []
        self.members_table.data = []
        self.activities_table.data = []
        self.settings_table.data = []
        self.stats_table.data = []
    
    def _create_tables(self):
        """Create LanceDB tables"""
        if not LANCEDB_AVAILABLE or not self.db:
            return
        
        try:
            # Trello boards table schema
            boards_schema = pa.schema([
                pa.field('id', pa.string()),
                pa.field('user_id', pa.string()),
                pa.field('board_id', pa.string()),
                pa.field('name', pa.string()),
                pa.field('description', pa.string()),
                pa.field('closed', pa.bool_()),
                pa.field('organization_id', pa.string()),
                pa.field('pinned', pa.bool_()),
                pa.field('url', pa.string()),
                pa.field('short_url', pa.string()),
                pa.field('short_link', pa.string()),
                pa.field('date_last_activity', pa.timestamp('us')),
                pa.field('date_last_view', pa.timestamp('us')),
                pa.field('creation_date', pa.timestamp('us')),
                pa.field('background_color', pa.string()),
                pa.field('background_image', pa.string()),
                pa.field('card_cover_images', pa.bool_()),
                pa.field('calendar_feed_enabled', pa.bool_()),
                pa.field('comment_permissions', pa.string()),
                pa.field('invitations_enabled', pa.bool_()),
                pa.field('voting_permitted', pa.bool_()),
                pa.field('level', pa.string()),
                pa.field('member_level', pa.string()),
                pa.field('starred', pa.bool_()),
                pa.field('subscribed', pa.bool_()),
                pa.field('preferences', pa.string()),
                pa.field('label_names', pa.string()),
                pa.field('total_cards', pa.int64()),
                pa.field('total_lists', pa.int64()),
                pa.field('total_members', pa.int64()),
                pa.field('total_checklists', pa.int64()),
                pa.field('processed_at', pa.timestamp('us')),
                pa.field('batch_id', pa.string())
            ])
            
            # Trello cards table schema
            cards_schema = pa.schema([
                pa.field('id', pa.string()),
                pa.field('user_id', pa.string()),
                pa.field('card_id', pa.string()),
                pa.field('board_id', pa.string()),
                pa.field('list_id', pa.string()),
                pa.field('name', pa.string()),
                pa.field('description', pa.string()),
                pa.field('closed', pa.bool_()),
                pa.field('due_date', pa.timestamp('us')),
                pa.field('due_complete', pa.bool_()),
                pa.field('start_date', pa.timestamp('us')),
                pa.field('position', pa.float64()),
                pa.field('url', pa.string()),
                pa.field('short_url', pa.string()),
                pa.field('short_link', pa.string()),
                pa.field('subscribed', pa.bool_()),
                pa.field('address', pa.string()),
                pa.field('labels', pa.string()),
                pa.field('members', pa.string()),
                pa.field('checklists', pa.string()),
                pa.field('attachments', pa.string()),
                pa.field('badges', pa.string()),
                pa.field('custom_fields', pa.string()),
                pa.field('cover', pa.string()),
                pa.field('date_last_activity', pa.timestamp('us')),
                pa.field('creation_date', pa.timestamp('us')),
                pa.field('comments_count', pa.int64()),
                pa.field('checklists_count', pa.int64()),
                pa.field('check_items_completed', pa.int64()),
                pa.field('check_items_total', pa.int64()),
                pa.field('attachments_count', pa.int64()),
                pa.field('members_count', pa.int64()),
                pa.field('labels_count', pa.int64()),
                pa.field('archived', pa.bool_()),
                pa.field('metadata', pa.string()),
                pa.field('processed_at', pa.timestamp('us')),
                pa.field('batch_id', pa.string())
            ])
            
            # Trello lists table schema
            lists_schema = pa.schema([
                pa.field('id', pa.string()),
                pa.field('user_id', pa.string()),
                pa.field('list_id', pa.string()),
                pa.field('board_id', pa.string()),
                pa.field('name', pa.string()),
                pa.field('closed', pa.bool_()),
                pa.field('position', pa.float64()),
                pa.field('subscribed', pa.bool_()),
                pa.field('soft_limit', pa.int64()),
                pa.field('url', pa.string()),
                pa.field('short_url', pa.string()),
                pa.field('short_link', pa.string()),
                pa.field('total_cards', pa.int64()),
                pa.field('closed_cards', pa.int64()),
                pa.field('total_checklists', pa.int64()),
                pa.field('total_attachments', pa.int64()),
                pa.field('date_last_activity', pa.timestamp('us')),
                pa.field('creation_date', pa.timestamp('us')),
                pa.field('metadata', pa.string()),
                pa.field('processed_at', pa.timestamp('us')),
                pa.field('batch_id', pa.string())
            ])
            
            # Trello members table schema
            members_schema = pa.schema([
                pa.field('id', pa.string()),
                pa.field('user_id', pa.string()),
                pa.field('member_id', pa.string()),
                pa.field('username', pa.string()),
                pa.field('full_name', pa.string()),
                pa.field('email', pa.string()),
                pa.field('avatar_url', pa.string()),
                pa.field('avatar_hash', pa.string()),
                pa.field('bio', pa.string()),
                pa.field('status', pa.string()),
                pa.field('member_type', pa.string()),
                pa.field('confirmed', pa.bool_()),
                pa.field('activity_blocked', pa.bool_()),
                pa.field('login_allowed', pa.bool_()),
                pa.field('boards_count', pa.int64()),
                pa.field('organizations_count', pa.int64()),
                pa.field('invited_boards_count', pa.int64()),
                pa.field('total_cards_assigned', pa.int64()),
                pa.field('total_cards_created', pa.int64()),
                pa.field('total_checklists_completed', pa.int64()),
                pa.field('total_comments', pa.int64()),
                pa.field('total_votes', pa.int64()),
                pa.field('first_activity', pa.timestamp('us')),
                pa.field('last_activity', pa.timestamp('us')),
                pa.field('member_since', pa.timestamp('us')),
                pa.field('premium_features', pa.string()),
                pa.field('preferences', pa.string()),
                pa.field('metadata', pa.string()),
                pa.field('processed_at', pa.timestamp('us')),
                pa.field('batch_id', pa.string())
            ])
            
            # Trello activities table schema
            activities_schema = pa.schema([
                pa.field('id', pa.string()),
                pa.field('user_id', pa.string()),
                pa.field('activity_id', pa.string()),
                pa.field('board_id', pa.string()),
                pa.field('card_id', pa.string()),
                pa.field('list_id', pa.string()),
                pa.field('member_id', pa.string()),
                pa.field('member_creator_id', pa.string()),
                pa.field('type', pa.string()),
                pa.field('date', pa.timestamp('us')),
                pa.field('text', pa.string()),
                pa.field('translation_key', pa.string()),
                pa.field('data', pa.string()),
                pa.field('member', pa.string()),
                pa.field('member_creator', pa.string()),
                pa.field('board', pa.string()),
                pa.field('card', pa.string()),
                pa.field('list_data', pa.string()),
                pa.field('organization', pa.string()),
                pa.field('display', pa.string()),
                pa.field('app', pa.string()),
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
                pa.field('include_boards', pa.list_(pa.string())),
                pa.field('exclude_boards', pa.list_(pa.string())),
                pa.field('include_archived_boards', pa.bool_()),
                pa.field('include_cards', pa.bool_()),
                pa.field('include_lists', pa.bool_()),
                pa.field('include_members', pa.bool_()),
                pa.field('include_checklists', pa.bool_()),
                pa.field('include_labels', pa.bool_()),
                pa.field('include_attachments', pa.bool_()),
                pa.field('include_activities', pa.bool_()),
                pa.field('max_cards_per_sync', pa.int64()),
                pa.field('max_activities_per_sync', pa.int64()),
                pa.field('sync_archived_cards', pa.bool_()),
                pa.field('sync_card_attachments', pa.bool_()),
                pa.field('index_card_content', pa.bool_()),
                pa.field('search_enabled', pa.bool_()),
                pa.field('semantic_search_enabled', pa.bool_()),
                pa.field('metadata_extraction_enabled', pa.bool_()),
                pa.field('board_tracking_enabled', pa.bool_()),
                pa.field('member_analysis_enabled', pa.bool_()),
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
                pa.field('total_boards_ingested', pa.int64()),
                pa.field('total_cards_ingested', pa.int64()),
                pa.field('total_lists_ingested', pa.int64()),
                pa.field('total_members_ingested', pa.int64()),
                pa.field('total_activities_ingested', pa.int64()),
                pa.field('total_checklists_ingested', pa.int64()),
                pa.field('total_attachments_ingested', pa.int64()),
                pa.field('last_ingestion_timestamp', pa.timestamp('us')),
                pa.field('total_size_mb', pa.float64()),
                pa.field('failed_ingestions', pa.int64()),
                pa.field('last_error_message', pa.string()),
                pa.field('avg_cards_per_board', pa.float64()),
                pa.field('avg_processing_time_ms', pa.float64()),
                pa.field('created_at', pa.timestamp('us')),
                pa.field('updated_at', pa.timestamp('us'))
            ])
            
            # Create or open tables
            self.boards_table = self.db.create_table(
                "trello_boards",
                schema=boards_schema,
                mode="overwrite"
            )
            
            self.cards_table = self.db.create_table(
                "trello_cards",
                schema=cards_schema,
                mode="overwrite"
            )
            
            self.lists_table = self.db.create_table(
                "trello_lists",
                schema=lists_schema,
                mode="overwrite"
            )
            
            self.members_table = self.db.create_table(
                "trello_members",
                schema=members_schema,
                mode="overwrite"
            )
            
            self.activities_table = self.db.create_table(
                "trello_activities",
                schema=activities_schema,
                mode="overwrite"
            )
            
            self.settings_table = self.db.create_table(
                TRELLO_USER_SETTINGS_TABLE_NAME,
                schema=settings_schema,
                mode="overwrite"
            )
            
            self.stats_table = self.db.create_table(
                TRELLO_INGESTION_STATS_TABLE_NAME,
                schema=stats_schema,
                mode="overwrite"
            )
            
            logger.info("Trello LanceDB tables created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create Trello LanceDB tables: {e}")
            raise
    
    def _calculate_content_hash(self, content: str) -> str:
        """Generate hash for content deduplication"""
        if not content:
            return ""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    
    def _generate_board_id(self, user_id: str, board_id: str) -> str:
        """Generate unique board ID"""
        return f"{user_id}:{board_id}"
    
    def _generate_card_id(self, user_id: str, card_id: str) -> str:
        """Generate unique card ID"""
        return f"{user_id}:{card_id}"
    
    def _generate_list_id(self, user_id: str, list_id: str) -> str:
        """Generate unique list ID"""
        return f"{user_id}:{list_id}"
    
    def _generate_member_id(self, user_id: str, member_id: str) -> str:
        """Generate unique member ID"""
        return f"{user_id}:{member_id}"
    
    def _generate_activity_id(self, user_id: str, activity_id: str) -> str:
        """Generate unique activity ID"""
        return f"{user_id}:{activity_id}"
    
    async def get_user_settings(self, user_id: str) -> TrelloMemorySettings:
        """Get user Trello memory settings"""
        try:
            if LANCEDB_AVAILABLE and self.settings_table:
                # Query from LanceDB
                results = self.settings_table.search().where(f"user_id = '{user_id}'").to_list()
                if results:
                    settings_data = results[0]
                    return TrelloMemorySettings(**settings_data)
            
            # Mock database or no results
            default_settings = TrelloMemorySettings(
                user_id=user_id,
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat()
            )
            
            return default_settings
            
        except Exception as e:
            logger.error(f"Error getting Trello user settings: {e}")
            return TrelloMemorySettings(user_id=user_id)
    
    async def save_user_settings(self, settings: TrelloMemorySettings) -> bool:
        """Save user Trello memory settings"""
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
                
                logger.info(f"Trello user settings saved for {settings.user_id}")
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
            logger.error(f"Error saving Trello user settings: {e}")
            return False
    
    async def get_ingestion_stats(self, user_id: str) -> TrelloIngestionStats:
        """Get Trello ingestion statistics"""
        try:
            if LANCEDB_AVAILABLE and self.stats_table:
                # Query from LanceDB
                results = self.stats_table.search().where(f"user_id = '{user_id}'").to_list()
                if results:
                    stats_data = results[0]
                    return TrelloIngestionStats(**stats_data)
            
            # Mock database or no results
            default_stats = TrelloIngestionStats(
                user_id=user_id,
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat()
            )
            
            return default_stats
            
        except Exception as e:
            logger.error(f"Error getting Trello ingestion stats: {e}")
            return TrelloIngestionStats(user_id=user_id)
    
    async def update_ingestion_stats(self, user_id: str, boards_count: int = 0,
                                 cards_count: int = 0, lists_count: int = 0,
                                 members_count: int = 0, activities_count: int = 0,
                                 checklists_count: int = 0, attachments_count: int = 0,
                                 size_mb: float = 0.0, error_message: str = None) -> bool:
        """Update Trello ingestion statistics"""
        try:
            # Get existing stats
            stats = await self.get_ingestion_stats(user_id)
            
            # Update stats
            stats.total_boards_ingested += boards_count
            stats.total_cards_ingested += cards_count
            stats.total_lists_ingested += lists_count
            stats.total_members_ingested += members_count
            stats.total_activities_ingested += activities_count
            stats.total_checklists_ingested += checklists_count
            stats.total_attachments_ingested += attachments_count
            stats.last_ingestion_timestamp = datetime.utcnow().isoformat()
            stats.updated_at = datetime.utcnow().isoformat()
            stats.total_size_mb += size_mb
            
            if boards_count > 0 and cards_count > 0:
                stats.avg_cards_per_board = stats.total_cards_ingested / max(1, stats.total_boards_ingested)
            
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
            
            logger.info(f"Trello ingestion stats updated for {user_id}: +{boards_count} boards, +{cards_count} cards")
            return True
            
        except Exception as e:
            logger.error(f"Error updating Trello ingestion stats: {e}")
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
            logger.error(f"Error checking Trello sync requirements: {e}")
            return False
    
    def _should_include_board(self, board_id: str, board_name: str, settings: TrelloMemorySettings) -> bool:
        """Check if board should be included in sync"""
        # Check board inclusion/exclusion
        if settings.exclude_boards:
            for exclude_board in settings.exclude_boards:
                if exclude_board.lower() in board_id.lower() or exclude_board.lower() in board_name.lower():
                    return False
        
        if settings.include_boards:
            for include_board in settings.include_boards:
                if include_board.lower() in board_id.lower() or include_board.lower() in board_name.lower():
                    break
            else:
                return False
        
        return True
    
    async def ingest_trello_data(self, user_id: str, api_key: str = None,
                               oauth_token: str = None, force_sync: bool = False,
                               board_ids: List[str] = None) -> Dict[str, Any]:
        """Ingest Trello data"""
        try:
            if not TRELLO_SERVICE_AVAILABLE:
                return {
                    'success': False,
                    'error': 'Trello service not available',
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
            
            # Initialize Trello service
            trello_service = TrelloEnhancedService(api_key or os.getenv('TRELLO_API_KEY'),
                                                 oauth_token or os.getenv('TRELLO_OAUTH_TOKEN'))
            
            # Get boards to sync
            if board_ids:
                # Use specified board IDs
                boards_to_sync = []
                for board_id in board_ids:
                    board = await trello_service.get_board(board_id)
                    if board and self._should_include_board(board_id, board.name, settings):
                        boards_to_sync.append(board)
            else:
                # Get user's boards
                user_boards = await trello_service.get_boards(user_id, 'open')
                boards_to_sync = []
                for board in user_boards:
                    if self._should_include_board(board.id, board.name, settings):
                        boards_to_sync.append(board)
                
                # Include archived boards if requested
                if settings.include_archived_boards:
                    archived_boards = await trello_service.get_boards(user_id, 'closed')
                    for board in archived_boards:
                        if self._should_include_board(board.id, board.name, settings):
                            boards_to_sync.append(board)
            
            # Process boards
            total_boards = 0
            total_cards = 0
            total_lists = 0
            total_members = 0
            total_activities = 0
            total_checklists = 0
            total_attachments = 0
            total_size = 0.0
            batch_id = f"{user_id}:{datetime.utcnow().isoformat()}"
            
            for board in boards_to_sync:
                try:
                    # Store board
                    board_memory = TrelloBoardMemory(
                        id=self._generate_board_id(user_id, board.id),
                        user_id=user_id,
                        board_id=board.id,
                        name=board.name,
                        description=board.description,
                        closed=board.closed,
                        organization_id=board.organization_id,
                        pinned=board.pinned,
                        url=board.url,
                        short_url=board.short_url,
                        short_link=board.short_link,
                        date_last_activity=board.date_last_activity,
                        date_last_view=board.date_last_view,
                        creation_date=board.creation_date,
                        background_color=board.background_color,
                        background_image=board.background_image,
                        card_cover_images=board.card_cover_images,
                        calendar_feed_enabled=board.calendar_feed_enabled,
                        comment_permissions=board.comment_permissions,
                        invitations_enabled=board.invitations_enabled,
                        voting_permitted=board.voting_permitted,
                        level=board.level,
                        member_level=board.member_level,
                        starred=board.starred,
                        subscribed=board.subscribed,
                        preferences=board.preferences,
                        label_names=board.label_names,
                        total_cards=len([card for card in (await trello_service.get_cards(board.id) or [])]),
                        total_lists=len([list for list in (await trello_service.get_lists(board.id) or [])]),
                        total_members=len([member for member in (await trello_service.get_members(board.id) or [])]),
                        total_checklists=0,  # Will be calculated
                        processed_at=datetime.utcnow().isoformat(),
                        batch_id=batch_id
                    )
                    
                    await self._store_board(board_memory)
                    total_boards += 1
                    total_size += len(board.description) / (1024 * 1024)  # Convert to MB
                    
                    # Process lists if enabled
                    if settings.include_lists:
                        lists = await trello_service.get_lists(board.id)
                        for trello_list in lists:
                            list_memory = TrelloListMemory(
                                id=self._generate_list_id(user_id, trello_list.id),
                                user_id=user_id,
                                list_id=trello_list.id,
                                board_id=board.id,
                                name=trello_list.name,
                                closed=trello_list.closed,
                                position=trello_list.pos,
                                subscribed=trello_list.subscribed,
                                soft_limit=trello_list.soft_limit,
                                url=trello_list.url,
                                short_url=trello_list.short_url,
                                short_link=trello_list.short_link,
                                total_cards=len(trello_list.cards),
                                closed_cards=len([card for card in trello_list.cards if card.closed]),
                                total_checklists=len([checklist for card in trello_list.cards for checklist in card.checklists]),
                                total_attachments=len([attachment for card in trello_list.cards for attachment in card.attachments]),
                                date_last_activity=trello_list.metadata.get('last_activity', ''),
                                creation_date=trello_list.metadata.get('created_at', ''),
                                metadata=trello_list.metadata,
                                processed_at=datetime.utcnow().isoformat(),
                                batch_id=batch_id
                            )
                            
                            await self._store_list(list_memory)
                            total_lists += 1
                    
                    # Process cards if enabled
                    if settings.include_cards:
                        cards = await trello_service.get_cards(board.id)
                        for card in cards:
                            # Skip archived cards if not requested
                            if card.closed and not settings.sync_archived_cards:
                                continue
                            
                            # Calculate checklist completion
                            check_items_completed = 0
                            check_items_total = 0
                            for checklist in card.checklists:
                                for check_item in checklist.get('checkItems', []):
                                    check_items_total += 1
                                    if check_item.get('state') == 'complete':
                                        check_items_completed += 1
                            
                            card_memory = TrelloCardMemory(
                                id=self._generate_card_id(user_id, card.id),
                                user_id=user_id,
                                card_id=card.id,
                                board_id=board.id,
                                list_id=card.id_list,
                                name=card.name,
                                description=card.desc,
                                closed=card.closed,
                                due_date=card.due,
                                due_complete=card.due_complete,
                                start_date=card.start,
                                position=card.pos,
                                url=card.url,
                                short_url=card.short_url,
                                short_link=card.short_link,
                                subscribed=card.subscribed,
                                address=card.address,
                                labels=card.labels,
                                members=card.members,
                                checklists=card.checklists,
                                attachments=card.attachments,
                                badges=card.badges,
                                custom_fields=card.custom_field_items,
                                cover=card.cover,
                                date_last_activity=card.date_last_activity,
                                creation_date=card.creation_date,
                                comments_count=card.badges.get('comments', 0),
                                checklists_count=len(card.checklists),
                                check_items_completed=check_items_completed,
                                check_items_total=check_items_total,
                                attachments_count=len(card.attachments),
                                members_count=len(card.id_members),
                                labels_count=len(card.id_labels),
                                archived=card.closed,
                                metadata=card.metadata,
                                processed_at=datetime.utcnow().isoformat(),
                                batch_id=batch_id
                            )
                            
                            await self._store_card(card_memory)
                            total_cards += 1
                            total_checklists += len(card.checklists)
                            total_attachments += len(card.attachments)
                            total_size += len(card.name) + len(card.desc)  # Rough size estimate
                            
                            # Limit cards per sync
                            if total_cards >= settings.max_cards_per_sync:
                                break
                        
                        if total_cards >= settings.max_cards_per_sync:
                            break
                    
                    # Process members if enabled
                    if settings.include_members:
                        members = await trello_service.get_members(board.id)
                        for member in members:
                            # Calculate member statistics
                            total_cards_assigned = 0
                            total_cards_created = 0
                            total_checklists_completed = 0
                            total_comments = 0
                            total_votes = 0
                            first_activity = None
                            last_activity = None
                            
                            # These would need to be calculated from actual board data
                            # For now, using placeholder calculations
                            
                            member_memory = TrelloMemberMemory(
                                id=self._generate_member_id(user_id, member.id),
                                user_id=user_id,
                                member_id=member.id,
                                username=member.username,
                                full_name=member.full_name,
                                email=member.email,
                                avatar_url=member.avatar_url,
                                avatar_hash=member.avatar_hash,
                                bio=member.bio,
                                status=member.status,
                                member_type=member.member_type,
                                confirmed=member.confirmed,
                                activity_blocked=member.activity_blocked,
                                login_allowed=member.login_allowed,
                                boards_count=len(member.boards),
                                organizations_count=len(member.organizations),
                                invited_boards_count=len(member.invited),
                                total_cards_assigned=total_cards_assigned,
                                total_cards_created=total_cards_created,
                                total_checklists_completed=total_checklists_completed,
                                total_comments=total_comments,
                                total_votes=total_votes,
                                first_activity=first_activity or '',
                                last_activity=last_activity or '',
                                member_since=member.metadata.get('created_at', ''),
                                premium_features=member.premium_features,
                                preferences=member.preferences,
                                metadata=member.metadata,
                                processed_at=datetime.utcnow().isoformat(),
                                batch_id=batch_id
                            )
                            
                            await self._store_member(member_memory)
                            total_members += 1
                    
                    # Process activities if enabled
                    if settings.include_activities:
                        activities = await trello_service.get_board_activities(
                            board.id, 
                            settings.max_activities_per_sync
                        )
                        for activity in activities:
                            activity_memory = TrelloActivityMemory(
                                id=self._generate_activity_id(user_id, activity.id),
                                user_id=user_id,
                                activity_id=activity.id,
                                board_id=board.id,
                                card_id=activity.data.get('card', {}).get('id', ''),
                                list_id=activity.data.get('list', {}).get('id', ''),
                                member_id=activity.data.get('member', {}).get('id', ''),
                                member_creator_id=activity.member_creator.get('id', ''),
                                type=activity.type,
                                date=activity.date,
                                text=activity.text,
                                translation_key=activity.translation_key,
                                data=activity.data,
                                member=activity.member,
                                member_creator=activity.member_creator,
                                board=activity.board,
                                card=activity.card,
                                list_data=activity.list,
                                organization=activity.organization,
                                display=activity.display,
                                app=activity.app,
                                metadata=activity.metadata,
                                processed_at=datetime.utcnow().isoformat(),
                                batch_id=batch_id
                            )
                            
                            await self._store_activity(activity_memory)
                            total_activities += 1
                
                except Exception as e:
                    logger.error(f"Error processing Trello board {board.id}: {e}")
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
                boards_count=total_boards,
                cards_count=total_cards,
                lists_count=total_lists,
                members_count=total_members,
                activities_count=total_activities,
                checklists_count=total_checklists,
                attachments_count=total_attachments,
                size_mb=total_size
            )
            
            logger.info(f"Trello data ingestion completed for {user_id}: {total_boards} boards, {total_cards} cards")
            
            return {
                'success': True,
                'boards_ingested': total_boards,
                'cards_ingested': total_cards,
                'lists_ingested': total_lists,
                'members_ingested': total_members,
                'activities_ingested': total_activities,
                'checklists_ingested': total_checklists,
                'attachments_ingested': total_attachments,
                'total_size_mb': round(total_size, 2),
                'batch_id': batch_id,
                'next_sync': settings.next_sync_timestamp,
                'sync_frequency': settings.sync_frequency
            }
            
        except Exception as e:
            logger.error(f"Error in Trello data ingestion: {e}")
            
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
    
    async def _store_board(self, board: TrelloBoardMemory) -> bool:
        """Store board in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.boards_table:
                # Check if board already exists
                existing = (self.boards_table
                           .search()
                           .where(f"user_id = '{board.user_id}' AND board_id = '{board.board_id}'")
                           .to_list())
                
                if existing:
                    # Update existing board
                    self.boards_table.delete(f"user_id = '{board.user_id}' AND board_id = '{board.board_id}'")
                
                # Add new board
                board_data = [board.to_lancedb_schema()]
                self.boards_table.add(board_data)
                
                logger.info(f"Stored Trello board: {board.board_id}")
                return True
            else:
                # Mock database
                # Remove existing
                self.boards_table.data = [
                    brd for brd in self.boards_table.data 
                    if not (brd.get('user_id') == board.user_id and brd.get('board_id') == board.board_id)
                ]
                
                # Add new
                self.boards_table.data.append(asdict(board))
                
                logger.info(f"Stored Trello board in mock DB: {board.board_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error storing Trello board: {e}")
            return False
    
    async def _store_card(self, card: TrelloCardMemory) -> bool:
        """Store card in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.cards_table:
                # Check if card already exists
                existing = (self.cards_table
                           .search()
                           .where(f"user_id = '{card.user_id}' AND card_id = '{card.card_id}'")
                           .to_list())
                
                if existing:
                    # Update existing card
                    self.cards_table.delete(f"user_id = '{card.user_id}' AND card_id = '{card.card_id}'")
                
                # Add new card
                card_data = [card.to_lancedb_schema()]
                self.cards_table.add(card_data)
                
                logger.info(f"Stored Trello card: {card.card_id}")
                return True
            else:
                # Mock database
                # Remove existing
                self.cards_table.data = [
                    crd for crd in self.cards_table.data 
                    if not (crd.get('user_id') == card.user_id and crd.get('card_id') == card.card_id)
                ]
                
                # Add new
                self.cards_table.data.append(asdict(card))
                
                logger.info(f"Stored Trello card in mock DB: {card.card_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error storing Trello card: {e}")
            return False
    
    async def _store_list(self, trello_list: TrelloListMemory) -> bool:
        """Store list in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.lists_table:
                # Check if list already exists
                existing = (self.lists_table
                           .search()
                           .where(f"user_id = '{trello_list.user_id}' AND list_id = '{trello_list.list_id}'")
                           .to_list())
                
                if existing:
                    # Update existing list
                    self.lists_table.delete(f"user_id = '{trello_list.user_id}' AND list_id = '{trello_list.list_id}'")
                
                # Add new list
                list_data = [trello_list.to_lancedb_schema()]
                self.lists_table.add(list_data)
                
                logger.info(f"Stored Trello list: {trello_list.list_id}")
                return True
            else:
                # Mock database
                # Remove existing
                self.lists_table.data = [
                    lst for lst in self.lists_table.data 
                    if not (lst.get('user_id') == trello_list.user_id and lst.get('list_id') == trello_list.list_id)
                ]
                
                # Add new
                self.lists_table.data.append(asdict(trello_list))
                
                logger.info(f"Stored Trello list in mock DB: {trello_list.list_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error storing Trello list: {e}")
            return False
    
    async def _store_member(self, member: TrelloMemberMemory) -> bool:
        """Store member in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.members_table:
                # Check if member already exists
                existing = (self.members_table
                           .search()
                           .where(f"user_id = '{member.user_id}' AND member_id = '{member.member_id}'")
                           .to_list())
                
                if existing:
                    # Update existing member
                    self.members_table.delete(f"user_id = '{member.user_id}' AND member_id = '{member.member_id}'")
                
                # Add new member
                member_data = [member.to_lancedb_schema()]
                self.members_table.add(member_data)
                
                logger.info(f"Stored Trello member: {member.member_id}")
                return True
            else:
                # Mock database
                # Remove existing
                self.members_table.data = [
                    mem for mem in self.members_table.data 
                    if not (mem.get('user_id') == member.user_id and mem.get('member_id') == member.member_id)
                ]
                
                # Add new
                self.members_table.data.append(asdict(member))
                
                logger.info(f"Stored Trello member in mock DB: {member.member_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error storing Trello member: {e}")
            return False
    
    async def _store_activity(self, activity: TrelloActivityMemory) -> bool:
        """Store activity in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.activities_table:
                # Add new activity (activities are immutable)
                activity_data = [activity.to_lancedb_schema()]
                self.activities_table.add(activity_data)
                
                logger.info(f"Stored Trello activity: {activity.activity_id}")
                return True
            else:
                # Mock database
                self.activities_table.data.append(asdict(activity))
                
                logger.info(f"Stored Trello activity in mock DB: {activity.activity_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error storing Trello activity: {e}")
            return False
    
    async def search_trello_boards(self, user_id: str, query: str = '',
                                closed: bool = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Search Trello boards in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.boards_table:
                # Build query
                where_clauses = [f"user_id = '{user_id}'"]
                
                if closed is not None:
                    where_clauses.append(f"closed = {closed}")
                
                where_clause = " AND ".join(where_clauses)
                
                # Perform search
                if query:
                    # Text search
                    results = (self.boards_table
                             .search(query)
                             .where(where_clause)
                             .limit(limit)
                             .to_list())
                else:
                    # Filter only
                    results = (self.boards_table
                             .search()
                             .where(where_clause)
                             .limit(limit)
                             .to_list())
                
                return results
            else:
                # Mock database search
                all_boards = self.boards_table.data
                
                # Filter by user
                filtered_boards = [brd for brd in all_boards if brd.get('user_id') == user_id]
                
                # Apply additional filters
                if closed is not None:
                    filtered_boards = [brd for brd in filtered_boards 
                                  if brd.get('closed') == closed]
                
                if query:
                    filtered_boards = [brd for brd in filtered_boards 
                                  if query.lower() in brd.get('name', '').lower() or 
                                     query.lower() in brd.get('description', '').lower()]
                
                # Sort by last activity and limit
                filtered_boards.sort(key=lambda x: x.get('date_last_activity', ''), reverse=True)
                
                return filtered_boards[:limit]
                
        except Exception as e:
            logger.error(f"Error searching Trello boards: {e}")
            return []
    
    async def search_trello_cards(self, user_id: str, query: str = '',
                               board_id: str = None, list_id: str = None,
                               member_id: str = None, label_name: str = None,
                               closed: bool = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Search Trello cards in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.cards_table:
                # Build query
                where_clauses = [f"user_id = '{user_id}'"]
                
                if board_id:
                    where_clauses.append(f"board_id = '{board_id}'")
                if list_id:
                    where_clauses.append(f"list_id = '{list_id}'")
                if member_id:
                    where_clauses.append(f"'{member_id}' IN members")
                if label_name:
                    where_clauses.append(f"'{label_name}' IN labels")
                if closed is not None:
                    where_clauses.append(f"closed = {closed}")
                
                where_clause = " AND ".join(where_clauses)
                
                # Perform search
                if query:
                    # Text search
                    results = (self.cards_table
                             .search(query)
                             .where(where_clause)
                             .limit(limit)
                             .to_list())
                else:
                    # Filter only
                    results = (self.cards_table
                             .search()
                             .where(where_clause)
                             .limit(limit)
                             .to_list())
                
                return results
            else:
                # Mock database search
                all_cards = self.cards_table.data
                
                # Filter by user
                filtered_cards = [crd for crd in all_cards if crd.get('user_id') == user_id]
                
                # Apply additional filters
                if board_id:
                    filtered_cards = [crd for crd in filtered_cards 
                                  if crd.get('board_id') == board_id]
                if list_id:
                    filtered_cards = [crd for crd in filtered_cards 
                                  if crd.get('list_id') == list_id]
                if member_id:
                    filtered_cards = [crd for crd in filtered_cards 
                                  if member_id in crd.get('members', [])]
                if label_name:
                    filtered_cards = [crd for crd in filtered_cards 
                                  if label_name in crd.get('labels', [])]
                if closed is not None:
                    filtered_cards = [crd for crd in filtered_cards 
                                  if crd.get('closed') == closed]
                
                if query:
                    filtered_cards = [crd for crd in filtered_cards 
                                  if query.lower() in crd.get('name', '').lower() or 
                                     query.lower() in crd.get('description', '').lower()]
                
                # Sort by last activity and limit
                filtered_cards.sort(key=lambda x: x.get('date_last_activity', ''), reverse=True)
                
                return filtered_cards[:limit]
                
        except Exception as e:
            logger.error(f"Error searching Trello cards: {e}")
            return []
    
    async def search_trello_members(self, user_id: str, query: str = '',
                                 limit: int = 50) -> List[Dict[str, Any]]:
        """Search Trello members in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.members_table:
                # Build query
                where_clauses = [f"user_id = '{user_id}'"]
                where_clause = " AND ".join(where_clauses)
                
                # Perform search
                if query:
                    # Text search
                    results = (self.members_table
                             .search(query)
                             .where(where_clause)
                             .limit(limit)
                             .to_list())
                else:
                    # Filter only
                    results = (self.members_table
                             .search()
                             .where(where_clause)
                             .limit(limit)
                             .to_list())
                
                return results
            else:
                # Mock database search
                all_members = self.members_table.data
                
                # Filter by user
                filtered_members = [mem for mem in all_members if mem.get('user_id') == user_id]
                
                if query:
                    filtered_members = [mem for mem in filtered_members 
                                  if query.lower() in mem.get('username', '').lower() or 
                                     query.lower() in mem.get('full_name', '').lower() or
                                     query.lower() in mem.get('email', '').lower()]
                
                # Sort by last activity and limit
                filtered_members.sort(key=lambda x: x.get('last_activity', ''), reverse=True)
                
                return filtered_members[:limit]
                
        except Exception as e:
            logger.error(f"Error searching Trello members: {e}")
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
                    'total_boards_ingested': stats.total_boards_ingested,
                    'total_cards_ingested': stats.total_cards_ingested,
                    'total_lists_ingested': stats.total_lists_ingested,
                    'total_members_ingested': stats.total_members_ingested,
                    'total_activities_ingested': stats.total_activities_ingested,
                    'total_checklists_ingested': stats.total_checklists_ingested,
                    'total_attachments_ingested': stats.total_attachments_ingested,
                    'last_ingestion_timestamp': stats.last_ingestion_timestamp,
                    'total_size_mb': stats.total_size_mb,
                    'failed_ingestions': stats.failed_ingestions,
                    'last_error_message': stats.last_error_message,
                    'avg_cards_per_board': stats.avg_cards_per_board,
                    'avg_processing_time_ms': stats.avg_processing_time_ms
                },
                'settings': {
                    'include_boards': settings.include_boards or [],
                    'exclude_boards': settings.exclude_boards or [],
                    'include_archived_boards': settings.include_archived_boards,
                    'include_cards': settings.include_cards,
                    'include_lists': settings.include_lists,
                    'include_members': settings.include_members,
                    'include_checklists': settings.include_checklists,
                    'include_labels': settings.include_labels,
                    'include_attachments': settings.include_attachments,
                    'include_activities': settings.include_activities,
                    'max_cards_per_sync': settings.max_cards_per_sync,
                    'max_activities_per_sync': settings.max_activities_per_sync,
                    'sync_archived_cards': settings.sync_archived_cards,
                    'sync_card_attachments': settings.sync_card_attachments,
                    'index_card_content': settings.index_card_content,
                    'search_enabled': settings.search_enabled,
                    'semantic_search_enabled': settings.semantic_search_enabled,
                    'metadata_extraction_enabled': settings.metadata_extraction_enabled,
                    'board_tracking_enabled': settings.board_tracking_enabled,
                    'member_analysis_enabled': settings.member_analysis_enabled
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting Trello sync status: {e}")
            return {
                'user_id': user_id,
                'error': str(e),
                'error_type': 'status_error'
            }
    
    async def delete_user_data(self, user_id: str) -> bool:
        """Delete all Trello data for user"""
        try:
            # Delete from all tables
            if LANCEDB_AVAILABLE:
                self.boards_table.delete(f"user_id = '{user_id}'")
                self.cards_table.delete(f"user_id = '{user_id}'")
                self.lists_table.delete(f"user_id = '{user_id}'")
                self.members_table.delete(f"user_id = '{user_id}'")
                self.activities_table.delete(f"user_id = '{user_id}'")
                self.settings_table.delete(f"user_id = '{user_id}'")
                self.stats_table.delete(f"user_id = '{user_id}'")
            else:
                # Mock database
                self.boards_table.data = [brd for brd in self.boards_table.data 
                                         if brd.get('user_id') != user_id]
                self.cards_table.data = [crd for crd in self.cards_table.data 
                                        if crd.get('user_id') != user_id]
                self.lists_table.data = [lst for lst in self.lists_table.data 
                                       if lst.get('user_id') != user_id]
                self.members_table.data = [mem for mem in self.members_table.data 
                                         if mem.get('user_id') != user_id]
                self.activities_table.data = [act for act in self.activities_table.data 
                                           if act.get('user_id') != user_id]
                self.settings_table.data = [settings for settings in self.settings_table.data 
                                          if settings.get('user_id') != user_id]
                self.stats_table.data = [stats for stats in self.stats_table.data 
                                       if stats.get('user_id') != user_id]
            
            logger.info(f"All Trello data deleted for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting Trello user data: {e}")
            return False

# Create singleton instance
trello_lancedb_service = TrelloLanceDBIngestionService()