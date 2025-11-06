"""
Airtable LanceDB Ingestion Service
Complete Airtable data management memory ingestion with user controls
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

# Import enhanced Airtable service
try:
    from airtable_enhanced_service import airtable_enhanced_service
    AIRTABLE_SERVICE_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Airtable service not available: {e}")
    AIRTABLE_SERVICE_AVAILABLE = False

# Import encryption utilities
try:
    from atom_encryption import encrypt_data, decrypt_data
    ENCRYPTION_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Encryption not available: {e}")
    ENCRYPTION_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

# Airtable memory configuration
AIRTABLE_MEMORY_TABLE_NAME = "airtable_memory"
AIRTABLE_USER_SETTINGS_TABLE_NAME = "airtable_user_settings"
AIRTABLE_INGESTION_STATS_TABLE_NAME = "airtable_ingestion_stats"

@dataclass
class AirtableMemorySettings:
    """User-controlled Airtable memory settings"""
    user_id: str
    ingestion_enabled: bool = True
    sync_frequency: str = "hourly"  # real-time, hourly, daily, weekly, manual
    data_retention_days: int = 365
    include_bases: List[str] = None
    exclude_bases: List[str] = None
    include_archived_bases: bool = False
    include_tables: bool = True
    include_records: bool = True
    include_fields: bool = True
    include_views: bool = True
    include_attachments: bool = True
    include_webhooks: bool = True
    max_records_per_sync: int = 1000
    max_table_records_per_sync: int = 500
    sync_deleted_records: bool = True
    sync_record_attachments: bool = True
    index_record_content: bool = True
    search_enabled: bool = True
    semantic_search_enabled: bool = True
    metadata_extraction_enabled: bool = True
    base_tracking_enabled: bool = True
    table_analysis_enabled: bool = True
    field_analysis_enabled: bool = True
    last_sync_timestamp: str = None
    next_sync_timestamp: str = None
    sync_in_progress: bool = False
    error_message: str = None
    created_at: str = None
    updated_at: str = None

@dataclass
class AirtableBaseMemory:
    """Airtable base data for LanceDB storage"""
    id: str
    user_id: str
    base_id: str
    name: str
    permission_level: str
    sharing: str
    created_time: str
    last_modified_time: str
    base_icon_url: str
    base_color_theme: str
    workspace_id: str
    workspace_name: str
    total_tables: int
    total_records: int
    total_fields: int
    total_views: int
    total_collaborators: int
    collaboration: Dict[str, Any]
    processed_at: str
    batch_id: str
    
    def to_lancedb_schema(self) -> Dict[str, Any]:
        """Convert to LanceDB schema"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'base_id': self.base_id,
            'name': self.name,
            'permission_level': self.permission_level,
            'sharing': self.sharing,
            'created_time': self.created_time,
            'last_modified_time': self.last_modified_time,
            'base_icon_url': self.base_icon_url,
            'base_color_theme': self.base_color_theme,
            'workspace_id': self.workspace_id,
            'workspace_name': self.workspace_name,
            'total_tables': self.total_tables,
            'total_records': self.total_records,
            'total_fields': self.total_fields,
            'total_views': self.total_views,
            'total_collaborators': self.total_collaborators,
            'collaboration': json.dumps(self.collaboration),
            'processed_at': self.processed_at,
            'batch_id': self.batch_id
        }

@dataclass
class AirtableTableMemory:
    """Airtable table data for LanceDB storage"""
    id: str
    user_id: str
    table_id: str
    base_id: str
    base_name: str
    name: str
    primary_field_id: str
    primary_field_name: str
    description: str
    records_count: int
    views_count: int
    fields_count: int
    total_attachments: int
    total_comments: int
    fields: List[Dict[str, Any]]
    views: List[Dict[str, Any]]
    created_time: str
    last_modified_time: str
    icon_emoji: str
    icon_url: str
    field_types_distribution: Dict[str, int]
    metadata: Dict[str, Any]
    processed_at: str
    batch_id: str
    
    def to_lancedb_schema(self) -> Dict[str, Any]:
        """Convert to LanceDB schema"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'table_id': self.table_id,
            'base_id': self.base_id,
            'base_name': self.base_name,
            'name': self.name,
            'primary_field_id': self.primary_field_id,
            'primary_field_name': self.primary_field_name,
            'description': self.description,
            'records_count': self.records_count,
            'views_count': self.views_count,
            'fields_count': self.fields_count,
            'total_attachments': self.total_attachments,
            'total_comments': self.total_comments,
            'fields': json.dumps(self.fields),
            'views': json.dumps(self.views),
            'created_time': self.created_time,
            'last_modified_time': self.last_modified_time,
            'icon_emoji': self.icon_emoji,
            'icon_url': self.icon_url,
            'field_types_distribution': json.dumps(self.field_types_distribution),
            'metadata': json.dumps(self.metadata),
            'processed_at': self.processed_at,
            'batch_id': self.batch_id
        }

@dataclass
class AirtableFieldMemory:
    """Airtable field data for LanceDB storage"""
    id: str
    user_id: str
    field_id: str
    table_id: str
    table_name: str
    base_id: str
    base_name: str
    name: str
    type: str
    description: str
    options: Dict[str, Any]
    required: bool
    unique: bool
    hidden: bool
    formula: str
    validation: Dict[str, Any]
    lookup: Dict[str, Any]
    rollup: Dict[str, Any]
    multiple_record_links: Dict[str, Any]
    field_config: Dict[str, Any]
    metadata: Dict[str, Any]
    processed_at: str
    batch_id: str
    
    def to_lancedb_schema(self) -> Dict[str, Any]:
        """Convert to LanceDB schema"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'field_id': self.field_id,
            'table_id': self.table_id,
            'table_name': self.table_name,
            'base_id': self.base_id,
            'base_name': self.base_name,
            'name': self.name,
            'type': self.type,
            'description': self.description,
            'options': json.dumps(self.options),
            'required': self.required,
            'unique': self.unique,
            'hidden': self.hidden,
            'formula': self.formula,
            'validation': json.dumps(self.validation),
            'lookup': json.dumps(self.lookup),
            'rollup': json.dumps(self.rollup),
            'multiple_record_links': json.dumps(self.multiple_record_links),
            'field_config': json.dumps(self.field_config),
            'metadata': json.dumps(self.metadata),
            'processed_at': self.processed_at,
            'batch_id': self.batch_id
        }

@dataclass
class AirtableViewMemory:
    """Airtable view data for LanceDB storage"""
    id: str
    user_id: str
    view_id: str
    table_id: str
    table_name: str
    base_id: str
    base_name: str
    name: str
    type: str
    personal: bool
    description: str
    filters: List[Dict[str, Any]]
    sorts: List[Dict[str, Any]]
    field_options: Dict[str, Any]
    view_config: Dict[str, Any]
    metadata: Dict[str, Any]
    processed_at: str
    batch_id: str
    
    def to_lancedb_schema(self) -> Dict[str, Any]:
        """Convert to LanceDB schema"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'view_id': self.view_id,
            'table_id': self.table_id,
            'table_name': self.table_name,
            'base_id': self.base_id,
            'base_name': self.base_name,
            'name': self.name,
            'type': self.type,
            'personal': self.personal,
            'description': self.description,
            'filters': json.dumps(self.filters),
            'sorts': json.dumps(self.sorts),
            'field_options': json.dumps(self.field_options),
            'view_config': json.dumps(self.view_config),
            'metadata': json.dumps(self.metadata),
            'processed_at': self.processed_at,
            'batch_id': self.batch_id
        }

@dataclass
class AirtableRecordMemory:
    """Airtable record data for LanceDB storage"""
    id: str
    user_id: str
    record_id: str
    table_id: str
    table_name: str
    base_id: str
    base_name: str
    created_time: str
    last_modified_time: str
    fields: Dict[str, Any]
    field_values: Dict[str, Any]
    field_types: Dict[str, str]
    attachments: List[Dict[str, Any]]
    linked_records: List[Dict[str, Any]]
    comments_count: int
    total_field_count: int
    text_fields_count: int
    numeric_fields_count: int
    date_fields_count: int
    attachment_fields_count: int
    linked_fields_count: int
    formula_fields_count: int
    search_content: str
    metadata: Dict[str, Any]
    processed_at: str
    batch_id: str
    
    def to_lancedb_schema(self) -> Dict[str, Any]:
        """Convert to LanceDB schema"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'record_id': self.record_id,
            'table_id': self.table_id,
            'table_name': self.table_name,
            'base_id': self.base_id,
            'base_name': self.base_name,
            'created_time': self.created_time,
            'last_modified_time': self.last_modified_time,
            'fields': json.dumps(self.fields),
            'field_values': json.dumps(self.field_values),
            'field_types': json.dumps(self.field_types),
            'attachments': json.dumps(self.attachments),
            'linked_records': json.dumps(self.linked_records),
            'comments_count': self.comments_count,
            'total_field_count': self.total_field_count,
            'text_fields_count': self.text_fields_count,
            'numeric_fields_count': self.numeric_fields_count,
            'date_fields_count': self.date_fields_count,
            'attachment_fields_count': self.attachment_fields_count,
            'linked_fields_count': self.linked_fields_count,
            'formula_fields_count': self.formula_fields_count,
            'search_content': self.search_content,
            'metadata': json.dumps(self.metadata),
            'processed_at': self.processed_at,
            'batch_id': self.batch_id
        }

@dataclass
class AirtableWebhookMemory:
    """Airtable webhook data for LanceDB storage"""
    id: str
    user_id: str
    webhook_id: str
    base_id: str
    base_name: str
    is_hook_enabled: bool
    cursor: int
    last_hook_time: str
    base_notification_url: str
    spec: Dict[str, Any]
    expiration_time: str
    created_time: str
    webhook_events: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    processed_at: str
    batch_id: str
    
    def to_lancedb_schema(self) -> Dict[str, Any]:
        """Convert to LanceDB schema"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'webhook_id': self.webhook_id,
            'base_id': self.base_id,
            'base_name': self.base_name,
            'is_hook_enabled': self.is_hook_enabled,
            'cursor': self.cursor,
            'last_hook_time': self.last_hook_time,
            'base_notification_url': self.base_notification_url,
            'spec': json.dumps(self.spec),
            'expiration_time': self.expiration_time,
            'created_time': self.created_time,
            'webhook_events': json.dumps(self.webhook_events),
            'metadata': json.dumps(self.metadata),
            'processed_at': self.processed_at,
            'batch_id': self.batch_id
        }

@dataclass
class AirtableIngestionStats:
    """Airtable ingestion statistics"""
    user_id: str
    total_bases_ingested: int = 0
    total_tables_ingested: int = 0
    total_records_ingested: int = 0
    total_fields_ingested: int = 0
    total_views_ingested: int = 0
    total_webhooks_ingested: int = 0
    total_attachments_ingested: int = 0
    total_comments_ingested: int = 0
    last_ingestion_timestamp: str = None
    total_size_mb: float = 0.0
    failed_ingestions: int = 0
    last_error_message: str = None
    avg_records_per_table: float = 0.0
    avg_fields_per_table: float = 0.0
    avg_processing_time_ms: float = 0.0
    created_at: str = None
    updated_at: str = None

class AirtableLanceDBIngestionService:
    """Airtable LanceDB ingestion service with user controls"""
    
    def __init__(self, lancedb_uri: str = None):
        self.lancedb_uri = lancedb_uri or os.getenv('LANCEDB_URI', 'lancedb/airtable_memory')
        self.db = None
        self.bases_table = None
        self.tables_table = None
        self.records_table = None
        self.fields_table = None
        self.views_table = None
        self.webhooks_table = None
        self.settings_table = None
        self.stats_table = None
        self._init_lancedb()
        
        # Ingestion state
        self.ingestion_workers = {}
        self.ingestion_locks = {}
        
        # Field type categories
        self.field_type_categories = {
            'text': ['single_line_text', 'long_text', 'rich_text', 'email', 'url'],
            'numeric': ['number', 'percent', 'currency', 'rating', 'duration'],
            'date': ['date', 'datetime', 'created_time', 'modified_time'],
            'select': ['single_select', 'multiple_selects'],
            'link': ['multiple_record_links'],
            'lookup': ['lookup'],
            'rollup': ['rollup'],
            'formula': ['formula'],
            'attachment': ['attachment'],
            'user': ['created_by', 'modified_by'],
            'other': ['checkbox', 'barcode', 'unknown']
        }
    
    def _init_lancedb(self):
        """Initialize LanceDB connection"""
        try:
            if LANCEDB_AVAILABLE:
                self.db = lancedb.connect(self.lancedb_uri)
                self._create_tables()
                logger.info(f"Airtable LanceDB service initialized: {self.lancedb_uri}")
            else:
                logger.warning("LanceDB not available - using mock database")
                self._init_mock_database()
        except Exception as e:
            logger.error(f"Failed to initialize Airtable LanceDB: {e}")
            self._init_mock_database()
    
    def _init_mock_database(self):
        """Initialize mock database for testing"""
        self.db = type('MockDB', (), {})()
        self.bases_table = type('MockTable', (), {})()
        self.tables_table = type('MockTable', (), {})()
        self.records_table = type('MockTable', (), {})()
        self.fields_table = type('MockTable', (), {})()
        self.views_table = type('MockTable', (), {})()
        self.webhooks_table = type('MockTable', (), {})()
        self.settings_table = type('MockTable', (), {})()
        self.stats_table = type('MockTable', (), {})()
        self.bases_table.data = []
        self.tables_table.data = []
        self.records_table.data = []
        self.fields_table.data = []
        self.views_table.data = []
        self.webhooks_table.data = []
        self.settings_table.data = []
        self.stats_table.data = []
    
    def _create_tables(self):
        """Create LanceDB tables"""
        if not LANCEDB_AVAILABLE or not self.db:
            return
        
        try:
            # Airtable bases table schema
            bases_schema = pa.schema([
                pa.field('id', pa.string()),
                pa.field('user_id', pa.string()),
                pa.field('base_id', pa.string()),
                pa.field('name', pa.string()),
                pa.field('permission_level', pa.string()),
                pa.field('sharing', pa.string()),
                pa.field('created_time', pa.timestamp('us')),
                pa.field('last_modified_time', pa.timestamp('us')),
                pa.field('base_icon_url', pa.string()),
                pa.field('base_color_theme', pa.string()),
                pa.field('workspace_id', pa.string()),
                pa.field('workspace_name', pa.string()),
                pa.field('total_tables', pa.int64()),
                pa.field('total_records', pa.int64()),
                pa.field('total_fields', pa.int64()),
                pa.field('total_views', pa.int64()),
                pa.field('total_collaborators', pa.int64()),
                pa.field('collaboration', pa.string()),
                pa.field('processed_at', pa.timestamp('us')),
                pa.field('batch_id', pa.string())
            ])
            
            # Airtable tables table schema
            tables_schema = pa.schema([
                pa.field('id', pa.string()),
                pa.field('user_id', pa.string()),
                pa.field('table_id', pa.string()),
                pa.field('base_id', pa.string()),
                pa.field('base_name', pa.string()),
                pa.field('name', pa.string()),
                pa.field('primary_field_id', pa.string()),
                pa.field('primary_field_name', pa.string()),
                pa.field('description', pa.string()),
                pa.field('records_count', pa.int64()),
                pa.field('views_count', pa.int64()),
                pa.field('fields_count', pa.int64()),
                pa.field('total_attachments', pa.int64()),
                pa.field('total_comments', pa.int64()),
                pa.field('fields', pa.string()),
                pa.field('views', pa.string()),
                pa.field('created_time', pa.timestamp('us')),
                pa.field('last_modified_time', pa.timestamp('us')),
                pa.field('icon_emoji', pa.string()),
                pa.field('icon_url', pa.string()),
                pa.field('field_types_distribution', pa.string()),
                pa.field('metadata', pa.string()),
                pa.field('processed_at', pa.timestamp('us')),
                pa.field('batch_id', pa.string())
            ])
            
            # Airtable records table schema
            records_schema = pa.schema([
                pa.field('id', pa.string()),
                pa.field('user_id', pa.string()),
                pa.field('record_id', pa.string()),
                pa.field('table_id', pa.string()),
                pa.field('table_name', pa.string()),
                pa.field('base_id', pa.string()),
                pa.field('base_name', pa.string()),
                pa.field('created_time', pa.timestamp('us')),
                pa.field('last_modified_time', pa.timestamp('us')),
                pa.field('fields', pa.string()),
                pa.field('field_values', pa.string()),
                pa.field('field_types', pa.string()),
                pa.field('attachments', pa.string()),
                pa.field('linked_records', pa.string()),
                pa.field('comments_count', pa.int64()),
                pa.field('total_field_count', pa.int64()),
                pa.field('text_fields_count', pa.int64()),
                pa.field('numeric_fields_count', pa.int64()),
                pa.field('date_fields_count', pa.int64()),
                pa.field('attachment_fields_count', pa.int64()),
                pa.field('linked_fields_count', pa.int64()),
                pa.field('formula_fields_count', pa.int64()),
                pa.field('search_content', pa.string()),
                pa.field('metadata', pa.string()),
                pa.field('processed_at', pa.timestamp('us')),
                pa.field('batch_id', pa.string())
            ])
            
            # Airtable fields table schema
            fields_schema = pa.schema([
                pa.field('id', pa.string()),
                pa.field('user_id', pa.string()),
                pa.field('field_id', pa.string()),
                pa.field('table_id', pa.string()),
                pa.field('table_name', pa.string()),
                pa.field('base_id', pa.string()),
                pa.field('base_name', pa.string()),
                pa.field('name', pa.string()),
                pa.field('type', pa.string()),
                pa.field('description', pa.string()),
                pa.field('options', pa.string()),
                pa.field('required', pa.bool_()),
                pa.field('unique', pa.bool_()),
                pa.field('hidden', pa.bool_()),
                pa.field('formula', pa.string()),
                pa.field('validation', pa.string()),
                pa.field('lookup', pa.string()),
                pa.field('rollup', pa.string()),
                pa.field('multiple_record_links', pa.string()),
                pa.field('field_config', pa.string()),
                pa.field('metadata', pa.string()),
                pa.field('processed_at', pa.timestamp('us')),
                pa.field('batch_id', pa.string())
            ])
            
            # Airtable views table schema
            views_schema = pa.schema([
                pa.field('id', pa.string()),
                pa.field('user_id', pa.string()),
                pa.field('view_id', pa.string()),
                pa.field('table_id', pa.string()),
                pa.field('table_name', pa.string()),
                pa.field('base_id', pa.string()),
                pa.field('base_name', pa.string()),
                pa.field('name', pa.string()),
                pa.field('type', pa.string()),
                pa.field('personal', pa.bool_()),
                pa.field('description', pa.string()),
                pa.field('filters', pa.string()),
                pa.field('sorts', pa.string()),
                pa.field('field_options', pa.string()),
                pa.field('view_config', pa.string()),
                pa.field('metadata', pa.string()),
                pa.field('processed_at', pa.timestamp('us')),
                pa.field('batch_id', pa.string())
            ])
            
            # Airtable webhooks table schema
            webhooks_schema = pa.schema([
                pa.field('id', pa.string()),
                pa.field('user_id', pa.string()),
                pa.field('webhook_id', pa.string()),
                pa.field('base_id', pa.string()),
                pa.field('base_name', pa.string()),
                pa.field('is_hook_enabled', pa.bool_()),
                pa.field('cursor', pa.int64()),
                pa.field('last_hook_time', pa.timestamp('us')),
                pa.field('base_notification_url', pa.string()),
                pa.field('spec', pa.string()),
                pa.field('expiration_time', pa.timestamp('us')),
                pa.field('created_time', pa.timestamp('us')),
                pa.field('webhook_events', pa.string()),
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
                pa.field('include_bases', pa.list_(pa.string())),
                pa.field('exclude_bases', pa.list_(pa.string())),
                pa.field('include_archived_bases', pa.bool_()),
                pa.field('include_tables', pa.bool_()),
                pa.field('include_records', pa.bool_()),
                pa.field('include_fields', pa.bool_()),
                pa.field('include_views', pa.bool_()),
                pa.field('include_attachments', pa.bool_()),
                pa.field('include_webhooks', pa.bool_()),
                pa.field('max_records_per_sync', pa.int64()),
                pa.field('max_table_records_per_sync', pa.int64()),
                pa.field('sync_deleted_records', pa.bool_()),
                pa.field('sync_record_attachments', pa.bool_()),
                pa.field('index_record_content', pa.bool_()),
                pa.field('search_enabled', pa.bool_()),
                pa.field('semantic_search_enabled', pa.bool_()),
                pa.field('metadata_extraction_enabled', pa.bool_()),
                pa.field('base_tracking_enabled', pa.bool_()),
                pa.field('table_analysis_enabled', pa.bool_()),
                pa.field('field_analysis_enabled', pa.bool_()),
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
                pa.field('total_bases_ingested', pa.int64()),
                pa.field('total_tables_ingested', pa.int64()),
                pa.field('total_records_ingested', pa.int64()),
                pa.field('total_fields_ingested', pa.int64()),
                pa.field('total_views_ingested', pa.int64()),
                pa.field('total_webhooks_ingested', pa.int64()),
                pa.field('total_attachments_ingested', pa.int64()),
                pa.field('total_comments_ingested', pa.int64()),
                pa.field('last_ingestion_timestamp', pa.timestamp('us')),
                pa.field('total_size_mb', pa.float64()),
                pa.field('failed_ingestions', pa.int64()),
                pa.field('last_error_message', pa.string()),
                pa.field('avg_records_per_table', pa.float64()),
                pa.field('avg_fields_per_table', pa.float64()),
                pa.field('avg_processing_time_ms', pa.float64()),
                pa.field('created_at', pa.timestamp('us')),
                pa.field('updated_at', pa.timestamp('us'))
            ])
            
            # Create or open tables
            self.bases_table = self.db.create_table(
                "airtable_bases",
                schema=bases_schema,
                mode="overwrite"
            )
            
            self.tables_table = self.db.create_table(
                "airtable_tables",
                schema=tables_schema,
                mode="overwrite"
            )
            
            self.records_table = self.db.create_table(
                "airtable_records",
                schema=records_schema,
                mode="overwrite"
            )
            
            self.fields_table = self.db.create_table(
                "airtable_fields",
                schema=fields_schema,
                mode="overwrite"
            )
            
            self.views_table = self.db.create_table(
                "airtable_views",
                schema=views_schema,
                mode="overwrite"
            )
            
            self.webhooks_table = self.db.create_table(
                "airtable_webhooks",
                schema=webhooks_schema,
                mode="overwrite"
            )
            
            self.settings_table = self.db.create_table(
                AIRTABLE_USER_SETTINGS_TABLE_NAME,
                schema=settings_schema,
                mode="overwrite"
            )
            
            self.stats_table = self.db.create_table(
                AIRTABLE_INGESTION_STATS_TABLE_NAME,
                schema=stats_schema,
                mode="overwrite"
            )
            
            logger.info("Airtable LanceDB tables created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create Airtable LanceDB tables: {e}")
            raise
    
    def _calculate_content_hash(self, content: str) -> str:
        """Generate hash for content deduplication"""
        if not content:
            return ""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    
    def _generate_base_id(self, user_id: str, base_id: str) -> str:
        """Generate unique base ID"""
        return f"{user_id}:{base_id}"
    
    def _generate_table_id(self, user_id: str, table_id: str) -> str:
        """Generate unique table ID"""
        return f"{user_id}:{table_id}"
    
    def _generate_record_id(self, user_id: str, record_id: str) -> str:
        """Generate unique record ID"""
        return f"{user_id}:{record_id}"
    
    def _generate_field_id(self, user_id: str, field_id: str) -> str:
        """Generate unique field ID"""
        return f"{user_id}:{field_id}"
    
    def _generate_view_id(self, user_id: str, view_id: str) -> str:
        """Generate unique view ID"""
        return f"{user_id}:{view_id}"
    
    def _generate_webhook_id(self, user_id: str, webhook_id: str) -> str:
        """Generate unique webhook ID"""
        return f"{user_id}:{webhook_id}"
    
    def _categorize_field_type(self, field_type: str) -> str:
        """Categorize field type"""
        for category, types in self.field_type_categories.items():
            if field_type in types:
                return category
        return 'other'
    
    async def get_user_settings(self, user_id: str) -> AirtableMemorySettings:
        """Get user Airtable memory settings"""
        try:
            if LANCEDB_AVAILABLE and self.settings_table:
                # Query from LanceDB
                results = self.settings_table.search().where(f"user_id = '{user_id}'").to_list()
                if results:
                    settings_data = results[0]
                    return AirtableMemorySettings(**settings_data)
            
            # Mock database or no results
            default_settings = AirtableMemorySettings(
                user_id=user_id,
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat()
            )
            
            return default_settings
            
        except Exception as e:
            logger.error(f"Error getting Airtable user settings: {e}")
            return AirtableMemorySettings(user_id=user_id)
    
    async def save_user_settings(self, settings: AirtableMemorySettings) -> bool:
        """Save user Airtable memory settings"""
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
                
                logger.info(f"Airtable user settings saved for {settings.user_id}")
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
            logger.error(f"Error saving Airtable user settings: {e}")
            return False
    
    async def get_ingestion_stats(self, user_id: str) -> AirtableIngestionStats:
        """Get Airtable ingestion statistics"""
        try:
            if LANCEDB_AVAILABLE and self.stats_table:
                # Query from LanceDB
                results = self.stats_table.search().where(f"user_id = '{user_id}'").to_list()
                if results:
                    stats_data = results[0]
                    return AirtableIngestionStats(**stats_data)
            
            # Mock database or no results
            default_stats = AirtableIngestionStats(
                user_id=user_id,
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat()
            )
            
            return default_stats
            
        except Exception as e:
            logger.error(f"Error getting Airtable ingestion stats: {e}")
            return AirtableIngestionStats(user_id=user_id)
    
    async def update_ingestion_stats(self, user_id: str, bases_count: int = 0,
                                 tables_count: int = 0, records_count: int = 0,
                                 fields_count: int = 0, views_count: int = 0,
                                 webhooks_count: int = 0, attachments_count: int = 0,
                                 size_mb: float = 0.0, error_message: str = None) -> bool:
        """Update Airtable ingestion statistics"""
        try:
            # Get existing stats
            stats = await self.get_ingestion_stats(user_id)
            
            # Update stats
            stats.total_bases_ingested += bases_count
            stats.total_tables_ingested += tables_count
            stats.total_records_ingested += records_count
            stats.total_fields_ingested += fields_count
            stats.total_views_ingested += views_count
            stats.total_webhooks_ingested += webhooks_count
            stats.total_attachments_ingested += attachments_count
            stats.last_ingestion_timestamp = datetime.utcnow().isoformat()
            stats.updated_at = datetime.utcnow().isoformat()
            stats.total_size_mb += size_mb
            
            if bases_count > 0 and tables_count > 0:
                stats.avg_tables_per_base = stats.total_tables_ingested / max(1, stats.total_bases_ingested)
            
            if tables_count > 0 and records_count > 0:
                stats.avg_records_per_table = stats.total_records_ingested / max(1, stats.total_tables_ingested)
            
            if tables_count > 0 and fields_count > 0:
                stats.avg_fields_per_table = stats.total_fields_ingested / max(1, stats.total_tables_ingested)
            
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
            
            logger.info(f"Airtable ingestion stats updated for {user_id}: +{bases_count} bases, +{tables_count} tables, +{records_count} records")
            return True
            
        except Exception as e:
            logger.error(f"Error updating Airtable ingestion stats: {e}")
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
            logger.error(f"Error checking Airtable sync requirements: {e}")
            return False
    
    def _should_include_base(self, base_id: str, base_name: str, settings: AirtableMemorySettings) -> bool:
        """Check if base should be included in sync"""
        # Check base inclusion/exclusion
        if settings.exclude_bases:
            for exclude_base in settings.exclude_bases:
                if exclude_base.lower() in base_id.lower() or exclude_base.lower() in base_name.lower():
                    return False
        
        if settings.include_bases:
            for include_base in settings.include_bases:
                if include_base.lower() in base_id.lower() or include_base.lower() in base_name.lower():
                    break
            else:
                return False
        
        return True
    
    async def ingest_airtable_data(self, user_id: str, api_key: str = None,
                               force_sync: bool = False, base_ids: List[str] = None) -> Dict[str, Any]:
        """Ingest Airtable data"""
        try:
            if not AIRTABLE_SERVICE_AVAILABLE:
                return {
                    'success': False,
                    'error': 'Airtable service not available',
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
            
            # Initialize Airtable service
            airtable_service = AirtableEnhancedService(api_key or os.getenv('AIRTABLE_API_KEY'))
            
            # Get bases to sync
            if base_ids:
                # Use specified base IDs
                bases_to_sync = []
                for base_id in base_ids:
                    base = await airtable_service.get_base(base_id, user_id)
                    if base and self._should_include_base(base_id, base.name, settings):
                        bases_to_sync.append(base)
            else:
                # Get user's bases
                user_bases = await airtable_service.get_bases(user_id)
                bases_to_sync = []
                for base in user_bases:
                    if self._should_include_base(base.id, base.name, settings):
                        bases_to_sync.append(base)
            
            # Process bases
            total_bases = 0
            total_tables = 0
            total_records = 0
            total_fields = 0
            total_views = 0
            total_webhooks = 0
            total_attachments = 0
            total_size = 0.0
            batch_id = f"{user_id}:{datetime.utcnow().isoformat()}"
            
            for base in bases_to_sync:
                try:
                    # Store base
                    base_memory = AirtableBaseMemory(
                        id=self._generate_base_id(user_id, base.id),
                        user_id=user_id,
                        base_id=base.id,
                        name=base.name,
                        permission_level=base.permission_level,
                        sharing=base.sharing,
                        created_time=base.created_time,
                        last_modified_time=base.last_modified_time,
                        base_icon_url=base.base_icon_url,
                        base_color_theme=base.base_color_theme,
                        workspace_id=base.workspace_id,
                        workspace_name=base.workspace_name,
                        total_tables=len([table for table in (await airtable_service.get_tables(base.id, user_id) or [])]),
                        total_records=0,  # Will be calculated
                        total_fields=0,  # Will be calculated
                        total_views=0,  # Will be calculated
                        total_collaborators=0,  # Will be calculated from collaboration data
                        collaboration=base.collaboration,
                        processed_at=datetime.utcnow().isoformat(),
                        batch_id=batch_id
                    )
                    
                    await self._store_base(base_memory)
                    total_bases += 1
                    total_size += len(base.name) / (1024 * 1024)  # Convert to MB
                    
                    # Process tables if enabled
                    if settings.include_tables:
                        tables = await airtable_service.get_tables(base.id, user_id)
                        base_total_records = 0
                        base_total_fields = 0
                        base_total_views = 0
                        base_total_attachments = 0
                        
                        for table in tables:
                            # Calculate field distribution
                            field_types_distribution = {}
                            for field in table.fields:
                                field_type = field.get('type', 'unknown')
                                category = self._categorize_field_type(field_type)
                                field_types_distribution[category] = field_types_distribution.get(category, 0) + 1
                            
                            table_memory = AirtableTableMemory(
                                id=self._generate_table_id(user_id, table.id),
                                user_id=user_id,
                                table_id=table.id,
                                base_id=base.id,
                                base_name=base.name,
                                name=table.name,
                                primary_field_id=table.primary_field_id,
                                primary_field_name=table.primary_field_name,
                                description=table.description,
                                records_count=table.records_count,
                                views_count=table.views_count,
                                fields_count=len(table.fields),
                                total_attachments=0,  # Will be calculated from records
                                total_comments=0,  # Will be calculated from records
                                fields=table.fields,
                                views=table.views,
                                created_time=table.created_time,
                                last_modified_time=table.last_modified_time,
                                icon_emoji=table.icon_emoji,
                                icon_url=table.icon_url,
                                field_types_distribution=field_types_distribution,
                                metadata=table.metadata,
                                processed_at=datetime.utcnow().isoformat(),
                                batch_id=batch_id
                            )
                            
                            await self._store_table(table_memory)
                            total_tables += 1
                            base_total_fields += len(table.fields)
                            base_total_views += len(table.views)
                            
                            # Process fields if enabled
                            if settings.include_fields:
                                for field in table.fields:
                                    field_memory = AirtableFieldMemory(
                                        id=self._generate_field_id(user_id, field.id),
                                        user_id=user_id,
                                        field_id=field.id,
                                        table_id=table.id,
                                        table_name=table.name,
                                        base_id=base.id,
                                        base_name=base.name,
                                        name=field.name,
                                        type=field.type,
                                        description=field.description,
                                        options=field.options,
                                        required=field.required,
                                        unique=field.unique,
                                        hidden=field.hidden,
                                        formula=field.formula,
                                        validation=field.validation,
                                        lookup=field.lookup,
                                        rollup=field.rollup,
                                        multiple_record_links=field.multiple_record_links,
                                        field_config=field.options,
                                        metadata={
                                            'category': self._categorize_field_type(field.type),
                                            'searchable': field.type in self.field_type_categories['text'],
                                            'sortable': field.type in self.field_type_categories['text'] + self.field_type_categories['numeric'],
                                            'linkable': field.type in self.field_type_categories['link'],
                                            'calculated': field.type in self.field_type_categories['formula'] + self.field_type_categories['rollup']
                                        },
                                        processed_at=datetime.utcnow().isoformat(),
                                        batch_id=batch_id
                                    )
                                    
                                    await self._store_field(field_memory)
                                    total_fields += 1
                            
                            # Process records if enabled
                            if settings.include_records:
                                records_result = await airtable_service.get_records(
                                    base.id, table.id,
                                    max_records=settings.max_table_records_per_sync,
                                    user_id=user_id
                                )
                                
                                table_total_attachments = 0
                                
                                for record in records_result.get('records', []):
                                    # Count field types in record
                                    field_types = {}
                                    text_fields_count = 0
                                    numeric_fields_count = 0
                                    date_fields_count = 0
                                    attachment_fields_count = 0
                                    linked_fields_count = 0
                                    formula_fields_count = 0
                                    
                                    for field in table.fields:
                                        field_name = field.name
                                        field_value = record.fields.get(field_name)
                                        field_type = field.type
                                        
                                        field_types[field_name] = field_type
                                        
                                        if field_type in self.field_type_categories['text']:
                                            text_fields_count += 1
                                        elif field_type in self.field_type_categories['numeric']:
                                            numeric_fields_count += 1
                                        elif field_type in self.field_type_categories['date']:
                                            date_fields_count += 1
                                        elif field_type in self.field_type_categories['attachment']:
                                            attachment_fields_count += len(field_value) if isinstance(field_value, list) else 0
                                            table_total_attachments += attachment_fields_count
                                        elif field_type in self.field_type_categories['link']:
                                            linked_fields_count += len(field_value) if isinstance(field_value, list) else 0
                                        elif field_type in self.field_type_categories['formula']:
                                            formula_fields_count += 1
                                    
                                    # Create search content
                                    search_content_parts = []
                                    for field_name, field_value in record.fields.items():
                                        if isinstance(field_value, str) and field_value:
                                            search_content_parts.append(field_value)
                                    
                                    record_memory = AirtableRecordMemory(
                                        id=self._generate_record_id(user_id, record.id),
                                        user_id=user_id,
                                        record_id=record.id,
                                        table_id=table.id,
                                        table_name=table.name,
                                        base_id=base.id,
                                        base_name=base.name,
                                        created_time=record.created_time,
                                        last_modified_time=record.last_modified_time,
                                        fields=record.fields,
                                        field_values=record.fields,
                                        field_types=field_types,
                                        attachments=record.attachments,
                                        linked_records=record.linked_records,
                                        comments_count=record.comments_count,
                                        total_field_count=len(record.fields),
                                        text_fields_count=text_fields_count,
                                        numeric_fields_count=numeric_fields_count,
                                        date_fields_count=date_fields_count,
                                        attachment_fields_count=attachment_fields_count,
                                        linked_fields_count=linked_fields_count,
                                        formula_fields_count=formula_fields_count,
                                        search_content=' '.join(search_content_parts),
                                        metadata=record.metadata,
                                        processed_at=datetime.utcnow().isoformat(),
                                        batch_id=batch_id
                                    )
                                    
                                    await self._store_record(record_memory)
                                    total_records += 1
                                    total_size += len(record.name) + len(record.description)  # Rough size estimate
                                
                                # Update table attachment count
                                table_memory.total_attachments = table_total_attachments
                                await self._store_table(table_memory)
                                base_total_attachments += table_total_attachments
                                base_total_records += len(records_result.get('records', []))
                            
                            # Process views if enabled
                            if settings.include_views:
                                for view in table.views:
                                    view_memory = AirtableViewMemory(
                                        id=self._generate_view_id(user_id, view.id),
                                        user_id=user_id,
                                        view_id=view.id,
                                        table_id=table.id,
                                        table_name=table.name,
                                        base_id=base.id,
                                        base_name=base.name,
                                        name=view.name,
                                        type=view.type,
                                        personal=view.personal,
                                        description=view.description,
                                        filters=view.filters,
                                        sorts=view.sorts,
                                        field_options=view.field_options,
                                        view_config=view.field_options,
                                        metadata={
                                            'grid_columns': view.field_options.get('gridColumns', {}),
                                            'color_config': view.field_options.get('colorConfig', {}),
                                            'conditional_format': view.field_options.get('conditionalFormat', {})
                                        },
                                        processed_at=datetime.utcnow().isoformat(),
                                        batch_id=batch_id
                                    )
                                    
                                    await self._store_view(view_memory)
                                    total_views += 1
                        
                        # Update base totals
                        base_memory.total_records = base_total_records
                        base_memory.total_fields = base_total_fields
                        base_memory.total_views = base_total_views
                        base_memory.total_attachments = base_total_attachments
                        await self._store_base(base_memory)
                        total_size += base_total_fields * 50 / (1024 * 1024)  # Rough field size estimate
                    
                    # Process webhooks if enabled
                    if settings.include_webhooks:
                        webhooks = await airtable_service.get_webhooks(base.id, user_id)
                        for webhook in webhooks:
                            webhook_memory = AirtableWebhookMemory(
                                id=self._generate_webhook_id(user_id, webhook.id),
                                user_id=user_id,
                                webhook_id=webhook.id,
                                base_id=base.id,
                                base_name=base.name,
                                is_hook_enabled=webhook.is_hook_enabled,
                                cursor=webhook.cursor,
                                last_hook_time=webhook.last_hook_time,
                                base_notification_url=webhook.base_notification_url,
                                spec=webhook.spec,
                                expiration_time=webhook.expiration_time,
                                created_time=webhook.created_time,
                                webhook_events=[],  # Would need separate API call to get events
                                metadata={
                                    'events_tracked': webhook.spec.get('notification_events', []),
                                    'webhook_status': 'active' if webhook.is_hook_enabled else 'inactive',
                                    'webhook_health': 'unknown'  # Would need health check
                                },
                                processed_at=datetime.utcnow().isoformat(),
                                batch_id=batch_id
                            )
                            
                            await self._store_webhook(webhook_memory)
                            total_webhooks += 1
                
                except Exception as e:
                    logger.error(f"Error processing Airtable base {base.id}: {e}")
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
                bases_count=total_bases,
                tables_count=total_tables,
                records_count=total_records,
                fields_count=total_fields,
                views_count=total_views,
                webhooks_count=total_webhooks,
                attachments_count=total_attachments,
                size_mb=total_size
            )
            
            logger.info(f"Airtable data ingestion completed for {user_id}: {total_bases} bases, {total_tables} tables, {total_records} records")
            
            return {
                'success': True,
                'bases_ingested': total_bases,
                'tables_ingested': total_tables,
                'records_ingested': total_records,
                'fields_ingested': total_fields,
                'views_ingested': total_views,
                'webhooks_ingested': total_webhooks,
                'attachments_ingested': total_attachments,
                'total_size_mb': round(total_size, 2),
                'batch_id': batch_id,
                'next_sync': settings.next_sync_timestamp,
                'sync_frequency': settings.sync_frequency
            }
            
        except Exception as e:
            logger.error(f"Error in Airtable data ingestion: {e}")
            
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
    
    async def _store_base(self, base: AirtableBaseMemory) -> bool:
        """Store base in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.bases_table:
                # Check if base already exists
                existing = (self.bases_table
                           .search()
                           .where(f"user_id = '{base.user_id}' AND base_id = '{base.base_id}'")
                           .to_list())
                
                if existing:
                    # Update existing base
                    self.bases_table.delete(f"user_id = '{base.user_id}' AND base_id = '{base.base_id}'")
                
                # Add new base
                base_data = [base.to_lancedb_schema()]
                self.bases_table.add(base_data)
                
                logger.info(f"Stored Airtable base: {base.base_id}")
                return True
            else:
                # Mock database
                # Remove existing
                self.bases_table.data = [
                    base for base in self.bases_table.data 
                    if not (base.get('user_id') == base.user_id and base.get('base_id') == base.base_id)
                ]
                
                # Add new
                self.bases_table.data.append(asdict(base))
                
                logger.info(f"Stored Airtable base in mock DB: {base.base_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error storing Airtable base: {e}")
            return False
    
    async def _store_table(self, table: AirtableTableMemory) -> bool:
        """Store table in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.tables_table:
                # Check if table already exists
                existing = (self.tables_table
                           .search()
                           .where(f"user_id = '{table.user_id}' AND table_id = '{table.table_id}'")
                           .to_list())
                
                if existing:
                    # Update existing table
                    self.tables_table.delete(f"user_id = '{table.user_id}' AND table_id = '{table.table_id}'")
                
                # Add new table
                table_data = [table.to_lancedb_schema()]
                self.tables_table.add(table_data)
                
                logger.info(f"Stored Airtable table: {table.table_id}")
                return True
            else:
                # Mock database
                # Remove existing
                self.tables_table.data = [
                    tbl for tbl in self.tables_table.data 
                    if not (tbl.get('user_id') == table.user_id and tbl.get('table_id') == table.table_id)
                ]
                
                # Add new
                self.tables_table.data.append(asdict(table))
                
                logger.info(f"Stored Airtable table in mock DB: {table.table_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error storing Airtable table: {e}")
            return False
    
    async def _store_record(self, record: AirtableRecordMemory) -> bool:
        """Store record in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.records_table:
                # Check if record already exists
                existing = (self.records_table
                           .search()
                           .where(f"user_id = '{record.user_id}' AND record_id = '{record.record_id}'")
                           .to_list())
                
                if existing:
                    # Update existing record
                    self.records_table.delete(f"user_id = '{record.user_id}' AND record_id = '{record.record_id}'")
                
                # Add new record
                record_data = [record.to_lancedb_schema()]
                self.records_table.add(record_data)
                
                logger.info(f"Stored Airtable record: {record.record_id}")
                return True
            else:
                # Mock database
                # Remove existing
                self.records_table.data = [
                    rec for rec in self.records_table.data 
                    if not (rec.get('user_id') == record.user_id and rec.get('record_id') == record.record_id)
                ]
                
                # Add new
                self.records_table.data.append(asdict(record))
                
                logger.info(f"Stored Airtable record in mock DB: {record.record_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error storing Airtable record: {e}")
            return False
    
    async def _store_field(self, field: AirtableFieldMemory) -> bool:
        """Store field in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.fields_table:
                # Check if field already exists
                existing = (self.fields_table
                           .search()
                           .where(f"user_id = '{field.user_id}' AND field_id = '{field.field_id}'")
                           .to_list())
                
                if existing:
                    # Update existing field
                    self.fields_table.delete(f"user_id = '{field.user_id}' AND field_id = '{field.field_id}'")
                
                # Add new field
                field_data = [field.to_lancedb_schema()]
                self.fields_table.add(field_data)
                
                logger.info(f"Stored Airtable field: {field.field_id}")
                return True
            else:
                # Mock database
                # Remove existing
                self.fields_table.data = [
                    field for field in self.fields_table.data 
                    if not (field.get('user_id') == field.user_id and field.get('field_id') == field.field_id)
                ]
                
                # Add new
                self.fields_table.data.append(asdict(field))
                
                logger.info(f"Stored Airtable field in mock DB: {field.field_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error storing Airtable field: {e}")
            return False
    
    async def _store_view(self, view: AirtableViewMemory) -> bool:
        """Store view in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.views_table:
                # Check if view already exists
                existing = (self.views_table
                           .search()
                           .where(f"user_id = '{view.user_id}' AND view_id = '{view.view_id}'")
                           .to_list())
                
                if existing:
                    # Update existing view
                    self.views_table.delete(f"user_id = '{view.user_id}' AND view_id = '{view.view_id}'")
                
                # Add new view
                view_data = [view.to_lancedb_schema()]
                self.views_table.add(view_data)
                
                logger.info(f"Stored Airtable view: {view.view_id}")
                return True
            else:
                # Mock database
                # Remove existing
                self.views_table.data = [
                    view for view in self.views_table.data 
                    if not (view.get('user_id') == view.user_id and view.get('view_id') == view.view_id)
                ]
                
                # Add new
                self.views_table.data.append(asdict(view))
                
                logger.info(f"Stored Airtable view in mock DB: {view.view_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error storing Airtable view: {e}")
            return False
    
    async def _store_webhook(self, webhook: AirtableWebhookMemory) -> bool:
        """Store webhook in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.webhooks_table:
                # Check if webhook already exists
                existing = (self.webhooks_table
                           .search()
                           .where(f"user_id = '{webhook.user_id}' AND webhook_id = '{webhook.webhook_id}'")
                           .to_list())
                
                if existing:
                    # Update existing webhook
                    self.webhooks_table.delete(f"user_id = '{webhook.user_id}' AND webhook_id = '{webhook.webhook_id}'")
                
                # Add new webhook
                webhook_data = [webhook.to_lancedb_schema()]
                self.webhooks_table.add(webhook_data)
                
                logger.info(f"Stored Airtable webhook: {webhook.webhook_id}")
                return True
            else:
                # Mock database
                # Remove existing
                self.webhooks_table.data = [
                    webhook for webhook in self.webhooks_table.data 
                    if not (webhook.get('user_id') == webhook.user_id and webhook.get('webhook_id') == webhook.webhook_id)
                ]
                
                # Add new
                self.webhooks_table.data.append(asdict(webhook))
                
                logger.info(f"Stored Airtable webhook in mock DB: {webhook.webhook_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error storing Airtable webhook: {e}")
            return False
    
    async def search_airtable_bases(self, user_id: str, query: str = '',
                                sharing: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Search Airtable bases in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.bases_table:
                # Build query
                where_clauses = [f"user_id = '{user_id}'"]
                
                if sharing:
                    where_clauses.append(f"sharing = '{sharing}'")
                
                where_clause = " AND ".join(where_clauses)
                
                # Perform search
                if query:
                    # Text search
                    results = (self.bases_table
                             .search(query)
                             .where(where_clause)
                             .limit(limit)
                             .to_list())
                else:
                    # Filter only
                    results = (self.bases_table
                             .search()
                             .where(where_clause)
                             .limit(limit)
                             .to_list())
                
                return results
            else:
                # Mock database search
                all_bases = self.bases_table.data
                
                # Filter by user
                filtered_bases = [base for base in all_bases if base.get('user_id') == user_id]
                
                # Apply additional filters
                if sharing:
                    filtered_bases = [base for base in filtered_bases 
                                  if base.get('sharing') == sharing]
                
                if query:
                    filtered_bases = [base for base in filtered_bases 
                                  if query.lower() in base.get('name', '').lower() or 
                                     query.lower() in base.get('description', '').lower()]
                
                # Sort by last modified and limit
                filtered_bases.sort(key=lambda x: x.get('last_modified_time', ''), reverse=True)
                
                return filtered_bases[:limit]
                
        except Exception as e:
            logger.error(f"Error searching Airtable bases: {e}")
            return []
    
    async def search_airtable_records(self, user_id: str, query: str = '',
                                   base_id: str = None, table_id: str = None,
                                   field_type: str = null, limit: int = 50) -> List[Dict[str, Any]]:
        """Search Airtable records in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.records_table:
                # Build query
                where_clauses = [f"user_id = '{user_id}'"]
                
                if base_id:
                    where_clauses.append(f"base_id = '{base_id}'")
                if table_id:
                    where_clauses.append(f"table_id = '{table_id}'")
                
                where_clause = " AND ".join(where_clauses)
                
                # Perform search
                if query:
                    # Text search on search_content field
                    results = (self.records_table
                             .search(query)
                             .where(where_clause)
                             .limit(limit)
                             .to_list())
                else:
                    # Filter only
                    results = (self.records_table
                             .search()
                             .where(where_clause)
                             .limit(limit)
                             .to_list())
                
                return results
            else:
                # Mock database search
                all_records = self.records_table.data
                
                # Filter by user
                filtered_records = [record for record in all_records if record.get('user_id') == user_id]
                
                # Apply additional filters
                if base_id:
                    filtered_records = [record for record in filtered_records 
                                  if record.get('base_id') == base_id]
                if table_id:
                    filtered_records = [record for record in filtered_records 
                                  if record.get('table_id') == table_id]
                if query:
                    filtered_records = [record for record in filtered_records 
                                  if query.lower() in record.get('search_content', '').lower()]
                
                # Sort by last modified and limit
                filtered_records.sort(key=lambda x: x.get('last_modified_time', ''), reverse=True)
                
                return filtered_records[:limit]
                
        except Exception as e:
            logger.error(f"Error searching Airtable records: {e}")
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
                    'total_bases_ingested': stats.total_bases_ingested,
                    'total_tables_ingested': stats.total_tables_ingested,
                    'total_records_ingested': stats.total_records_ingested,
                    'total_fields_ingested': stats.total_fields_ingested,
                    'total_views_ingested': stats.total_views_ingested,
                    'total_webhooks_ingested': stats.total_webhooks_ingested,
                    'total_attachments_ingested': stats.total_attachments_ingested,
                    'last_ingestion_timestamp': stats.last_ingestion_timestamp,
                    'total_size_mb': stats.total_size_mb,
                    'failed_ingestions': stats.failed_ingestions,
                    'last_error_message': stats.last_error_message,
                    'avg_records_per_table': stats.avg_records_per_table,
                    'avg_fields_per_table': stats.avg_fields_per_table,
                    'avg_processing_time_ms': stats.avg_processing_time_ms
                },
                'settings': {
                    'include_bases': settings.include_bases or [],
                    'exclude_bases': settings.exclude_bases or [],
                    'include_archived_bases': settings.include_archived_bases,
                    'include_tables': settings.include_tables,
                    'include_records': settings.include_records,
                    'include_fields': settings.include_fields,
                    'include_views': settings.include_views,
                    'include_attachments': settings.include_attachments,
                    'include_webhooks': settings.include_webhooks,
                    'max_records_per_sync': settings.max_records_per_sync,
                    'max_table_records_per_sync': settings.max_table_records_per_sync,
                    'sync_deleted_records': settings.sync_deleted_records,
                    'sync_record_attachments': settings.sync_record_attachments,
                    'index_record_content': settings.index_record_content,
                    'search_enabled': settings.search_enabled,
                    'semantic_search_enabled': settings.semantic_search_enabled,
                    'metadata_extraction_enabled': settings.metadata_extraction_enabled,
                    'base_tracking_enabled': settings.base_tracking_enabled,
                    'table_analysis_enabled': settings.table_analysis_enabled,
                    'field_analysis_enabled': settings.field_analysis_enabled
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting Airtable sync status: {e}")
            return {
                'user_id': user_id,
                'error': str(e),
                'error_type': 'status_error'
            }
    
    async def delete_user_data(self, user_id: str) -> bool:
        """Delete all Airtable data for user"""
        try:
            # Delete from all tables
            if LANCEDB_AVAILABLE:
                self.bases_table.delete(f"user_id = '{user_id}'")
                self.tables_table.delete(f"user_id = '{user_id}'")
                self.records_table.delete(f"user_id = '{user_id}'")
                self.fields_table.delete(f"user_id = '{user_id}'")
                self.views_table.delete(f"user_id = '{user_id}'")
                self.webhooks_table.delete(f"user_id = '{user_id}'")
                self.settings_table.delete(f"user_id = '{user_id}'")
                self.stats_table.delete(f"user_id = '{user_id}'")
            else:
                # Mock database
                self.bases_table.data = [base for base in self.bases_table.data 
                                         if base.get('user_id') != user_id]
                self.tables_table.data = [table for table in self.tables_table.data 
                                        if table.get('user_id') != user_id]
                self.records_table.data = [record for record in self.records_table.data 
                                        if record.get('user_id') != user_id]
                self.fields_table.data = [field for field in self.fields_table.data 
                                       if field.get('user_id') != user_id]
                self.views_table.data = [view for view in self.views_table.data 
                                      if view.get('user_id') != user_id]
                self.webhooks_table.data = [webhook for webhook in self.webhooks_table.data 
                                          if webhook.get('user_id') != user_id]
                self.settings_table.data = [settings for settings in self.settings_table.data 
                                          if settings.get('user_id') != user_id]
                self.stats_table.data = [stats for stats in self.stats_table.data 
                                       if stats.get('user_id') != user_id]
            
            logger.info(f"All Airtable data deleted for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting Airtable user data: {e}")
            return False

# Create singleton instance
airtable_lancedb_service = AirtableLanceDBIngestionService()