"""
VS Code LanceDB Ingestion Service
Complete VS Code development environment memory ingestion with user controls
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

# Import enhanced VS Code service
try:
    from vscode_enhanced_service import vscode_enhanced_service
    VSCODE_SERVICE_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"VS Code service not available: {e}")
    VSCODE_SERVICE_AVAILABLE = False

# Import encryption utilities
try:
    from atom_encryption import encrypt_data, decrypt_data
    ENCRYPTION_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Encryption not available: {e}")
    ENCRYPTION_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

# VS Code memory configuration
VSCODE_MEMORY_TABLE_NAME = "vscode_memory"
VSCODE_USER_SETTINGS_TABLE_NAME = "vscode_user_settings"
VSCODE_INGESTION_STATS_TABLE_NAME = "vscode_ingestion_stats"

@dataclass
class VSCodeMemorySettings:
    """User-controlled VS Code memory settings"""
    user_id: str
    ingestion_enabled: bool = True
    sync_frequency: str = "real-time"  # real-time, hourly, daily, weekly, manual
    data_retention_days: int = 365
    include_projects: List[str] = None
    exclude_projects: List[str] = None
    include_file_types: List[str] = None
    exclude_file_types: List[str] = None
    max_file_size_mb: int = 10
    max_files_per_project: int = 10000
    include_hidden_files: bool = False
    include_binary_files: bool = False
    code_search_enabled: bool = True
    semantic_search_enabled: bool = True
    metadata_extraction_enabled: bool = True
    activity_logging_enabled: bool = True
    last_sync_timestamp: str = None
    next_sync_timestamp: str = None
    sync_in_progress: bool = False
    error_message: str = None
    created_at: str = None
    updated_at: str = None

@dataclass
class VSCodeFileMemory:
    """VS Code file data for LanceDB storage"""
    id: str
    user_id: str
    project_id: str
    project_name: str
    file_path: str
    file_name: str
    extension: str
    language: str
    size: int
    created_at: str
    modified_at: str
    content: str
    content_hash: str
    line_count: int
    char_count: int
    encoding: str
    is_binary: bool
    is_hidden: bool
    git_status: str
    build_system: str
    metadata: Dict[str, Any]
    processed_at: str
    batch_id: str
    
    def to_lancedb_schema(self) -> Dict[str, Any]:
        """Convert to LanceDB schema"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'project_id': self.project_id,
            'project_name': self.project_name,
            'file_path': self.file_path,
            'file_name': self.file_name,
            'extension': self.extension,
            'language': self.language,
            'size': self.size,
            'created_at': self.created_at,
            'modified_at': self.modified_at,
            'content': self.content,
            'content_hash': self.content_hash,
            'line_count': self.line_count,
            'char_count': self.char_count,
            'encoding': self.encoding,
            'is_binary': self.is_binary,
            'is_hidden': self.is_hidden,
            'git_status': self.git_status,
            'build_system': self.build_system,
            'metadata': json.dumps(self.metadata)
        }

@dataclass
class VSCodeActivityMemory:
    """VS Code development activity data for LanceDB storage"""
    id: str
    user_id: str
    project_id: str
    project_name: str
    session_id: str
    action_type: str
    file_path: str
    file_name: str
    language: str
    content_before: str
    content_after: str
    change_summary: str
    timestamp: str
    duration_seconds: int
    git_commit_hash: str
    metadata: Dict[str, Any]
    processed_at: str
    
    def to_lancedb_schema(self) -> Dict[str, Any]:
        """Convert to LanceDB schema"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'project_id': self.project_id,
            'project_name': self.project_name,
            'session_id': self.session_id,
            'action_type': self.action_type,
            'file_path': self.file_path,
            'file_name': self.file_name,
            'language': self.language,
            'content_before': self.content_before,
            'content_after': self.content_after,
            'change_summary': self.change_summary,
            'timestamp': self.timestamp,
            'duration_seconds': self.duration_seconds,
            'git_commit_hash': self.git_commit_hash,
            'metadata': json.dumps(self.metadata)
        }

@dataclass
class VSCodeProjectMemory:
    """VS Code project metadata for LanceDB storage"""
    id: str
    user_id: str
    project_name: str
    project_path: str
    project_type: str
    build_system: str
    language_stats: Dict[str, int]
    total_files: int
    total_size: int
    git_info: Dict[str, Any]
    extensions: List[str]
    settings: Dict[str, Any]
    last_activity: str
    created_at: str
    updated_at: str
    metadata: Dict[str, Any]
    
    def to_lancedb_schema(self) -> Dict[str, Any]:
        """Convert to LanceDB schema"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'project_name': self.project_name,
            'project_path': self.project_path,
            'project_type': self.project_type,
            'build_system': self.build_system,
            'language_stats': json.dumps(self.language_stats),
            'total_files': self.total_files,
            'total_size': self.total_size,
            'git_info': json.dumps(self.git_info),
            'extensions': json.dumps(self.extensions),
            'settings': json.dumps(self.settings),
            'last_activity': self.last_activity,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'metadata': json.dumps(self.metadata)
        }

@dataclass
class VSCodeIngestionStats:
    """VS Code ingestion statistics"""
    user_id: str
    total_projects_ingested: int = 0
    total_files_ingested: int = 0
    total_activities_ingested: int = 0
    last_ingestion_timestamp: str = None
    total_size_mb: float = 0.0
    failed_ingestions: int = 0
    last_error_message: str = None
    avg_files_per_project: float = 0.0
    avg_processing_time_ms: float = 0.0
    created_at: str = None
    updated_at: str = None

class VSCodeLanceDBIngestionService:
    """VS Code LanceDB ingestion service with user controls"""
    
    def __init__(self, lancedb_uri: str = None):
        self.lancedb_uri = lancedb_uri or os.getenv('LANCEDB_URI', 'lancedb/vscode_memory')
        self.db = None
        self.files_table = None
        self.activities_table = None
        self.projects_table = None
        self.settings_table = None
        self.stats_table = None
        self._init_lancedb()
        
        # Ingestion state
        self.ingestion_workers = {}
        self.ingestion_locks = {}
        
        # File type detection
        self.text_file_extensions = {
            '.txt', '.md', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg',
            '.conf', '.log', '.csv', '.tsv', '.xml', '.html', '.htm', '.css',
            '.scss', '.sass', '.less', '.js', '.jsx', '.ts', '.tsx', '.vue',
            '.py', '.java', '.cpp', '.c', '.cs', '.go', '.rs', '.php', '.rb',
            '.swift', '.kt', '.scala', '.r', '.m', '.dart', '.lua', '.sh',
            '.ps1', '.bat', '.cmd', '.sql', '.graphql', '.dockerfile',
            '.gitignore', '.gitattributes', '.editorconfig', '.eslintrc',
            '.prettierrc', '.babelrc', '.tsconfig', '.webpack', '.package'
        }
    
    def _init_lancedb(self):
        """Initialize LanceDB connection"""
        try:
            if LANCEDB_AVAILABLE:
                self.db = lancedb.connect(self.lancedb_uri)
                self._create_tables()
                logger.info(f"VS Code LanceDB service initialized: {self.lancedb_uri}")
            else:
                logger.warning("LanceDB not available - using mock database")
                self._init_mock_database()
        except Exception as e:
            logger.error(f"Failed to initialize VS Code LanceDB: {e}")
            self._init_mock_database()
    
    def _init_mock_database(self):
        """Initialize mock database for testing"""
        self.db = type('MockDB', (), {})()
        self.files_table = type('MockTable', (), {})()
        self.activities_table = type('MockTable', (), {})()
        self.projects_table = type('MockTable', (), {})()
        self.settings_table = type('MockTable', (), {})()
        self.stats_table = type('MockTable', (), {})()
        self.files_table.data = []
        self.activities_table.data = []
        self.projects_table.data = []
        self.settings_table.data = []
        self.stats_table.data = []
    
    def _create_tables(self):
        """Create LanceDB tables"""
        if not LANCEDB_AVAILABLE or not self.db:
            return
        
        try:
            # VS Code files table schema
            files_schema = pa.schema([
                pa.field('id', pa.string()),
                pa.field('user_id', pa.string()),
                pa.field('project_id', pa.string()),
                pa.field('project_name', pa.string()),
                pa.field('file_path', pa.string()),
                pa.field('file_name', pa.string()),
                pa.field('extension', pa.string()),
                pa.field('language', pa.string()),
                pa.field('size', pa.int64()),
                pa.field('created_at', pa.timestamp('us')),
                pa.field('modified_at', pa.timestamp('us')),
                pa.field('content', pa.string()),
                pa.field('content_hash', pa.string()),
                pa.field('line_count', pa.int64()),
                pa.field('char_count', pa.int64()),
                pa.field('encoding', pa.string()),
                pa.field('is_binary', pa.bool_()),
                pa.field('is_hidden', pa.bool_()),
                pa.field('git_status', pa.string()),
                pa.field('build_system', pa.string()),
                pa.field('metadata', pa.string())
            ])
            
            # VS Code activities table schema
            activities_schema = pa.schema([
                pa.field('id', pa.string()),
                pa.field('user_id', pa.string()),
                pa.field('project_id', pa.string()),
                pa.field('project_name', pa.string()),
                pa.field('session_id', pa.string()),
                pa.field('action_type', pa.string()),
                pa.field('file_path', pa.string()),
                pa.field('file_name', pa.string()),
                pa.field('language', pa.string()),
                pa.field('content_before', pa.string()),
                pa.field('content_after', pa.string()),
                pa.field('change_summary', pa.string()),
                pa.field('timestamp', pa.timestamp('us')),
                pa.field('duration_seconds', pa.int64()),
                pa.field('git_commit_hash', pa.string()),
                pa.field('metadata', pa.string())
            ])
            
            # VS Code projects table schema
            projects_schema = pa.schema([
                pa.field('id', pa.string()),
                pa.field('user_id', pa.string()),
                pa.field('project_name', pa.string()),
                pa.field('project_path', pa.string()),
                pa.field('project_type', pa.string()),
                pa.field('build_system', pa.string()),
                pa.field('language_stats', pa.string()),
                pa.field('total_files', pa.int64()),
                pa.field('total_size', pa.int64()),
                pa.field('git_info', pa.string()),
                pa.field('extensions', pa.list_(pa.string())),
                pa.field('settings', pa.string()),
                pa.field('last_activity', pa.timestamp('us')),
                pa.field('created_at', pa.timestamp('us')),
                pa.field('updated_at', pa.timestamp('us')),
                pa.field('metadata', pa.string())
            ])
            
            # Settings table schema
            settings_schema = pa.schema([
                pa.field('user_id', pa.string()),
                pa.field('ingestion_enabled', pa.bool_()),
                pa.field('sync_frequency', pa.string()),
                pa.field('data_retention_days', pa.int64()),
                pa.field('include_projects', pa.list_(pa.string())),
                pa.field('exclude_projects', pa.list_(pa.string())),
                pa.field('include_file_types', pa.list_(pa.string())),
                pa.field('exclude_file_types', pa.list_(pa.string())),
                pa.field('max_file_size_mb', pa.int64()),
                pa.field('max_files_per_project', pa.int64()),
                pa.field('include_hidden_files', pa.bool_()),
                pa.field('include_binary_files', pa.bool_()),
                pa.field('code_search_enabled', pa.bool_()),
                pa.field('semantic_search_enabled', pa.bool_()),
                pa.field('metadata_extraction_enabled', pa.bool_()),
                pa.field('activity_logging_enabled', pa.bool_()),
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
                pa.field('total_projects_ingested', pa.int64()),
                pa.field('total_files_ingested', pa.int64()),
                pa.field('total_activities_ingested', pa.int64()),
                pa.field('last_ingestion_timestamp', pa.timestamp('us')),
                pa.field('total_size_mb', pa.float64()),
                pa.field('failed_ingestions', pa.int64()),
                pa.field('last_error_message', pa.string()),
                pa.field('avg_files_per_project', pa.float64()),
                pa.field('avg_processing_time_ms', pa.float64()),
                pa.field('created_at', pa.timestamp('us')),
                pa.field('updated_at', pa.timestamp('us'))
            ])
            
            # Create or open tables
            self.files_table = self.db.create_table(
                "vscode_files",
                schema=files_schema,
                mode="overwrite"
            )
            
            self.activities_table = self.db.create_table(
                "vscode_activities",
                schema=activities_schema,
                mode="overwrite"
            )
            
            self.projects_table = self.db.create_table(
                "vscode_projects",
                schema=projects_schema,
                mode="overwrite"
            )
            
            self.settings_table = self.db.create_table(
                VSCODE_USER_SETTINGS_TABLE_NAME,
                schema=settings_schema,
                mode="overwrite"
            )
            
            self.stats_table = self.db.create_table(
                VSCODE_INGESTION_STATS_TABLE_NAME,
                schema=stats_schema,
                mode="overwrite"
            )
            
            logger.info("VS Code LanceDB tables created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create VS Code LanceDB tables: {e}")
            raise
    
    def _is_text_file(self, file_path: str, file_name: str) -> bool:
        """Check if file is text file"""
        ext = os.path.splitext(file_name)[1].lower()
        return ext in self.text_file_extensions or ext == ''
    
    def _calculate_content_hash(self, content: str) -> str:
        """Generate hash for content deduplication"""
        if not content:
            return ""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    
    def _generate_file_id(self, user_id: str, project_id: str, file_path: str) -> str:
        """Generate unique file ID"""
        return f"{user_id}:{project_id}:{hashlib.md5(file_path.encode()).hexdigest()}"
    
    async def get_user_settings(self, user_id: str) -> VSCodeMemorySettings:
        """Get user VS Code memory settings"""
        try:
            if LANCEDB_AVAILABLE and self.settings_table:
                # Query from LanceDB
                results = self.settings_table.search().where(f"user_id = '{user_id}'").to_list()
                if results:
                    settings_data = results[0]
                    return VSCodeMemorySettings(**settings_data)
            
            # Mock database or no results
            default_settings = VSCodeMemorySettings(
                user_id=user_id,
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat()
            )
            
            return default_settings
            
        except Exception as e:
            logger.error(f"Error getting VS Code user settings: {e}")
            return VSCodeMemorySettings(user_id=user_id)
    
    async def save_user_settings(self, settings: VSCodeMemorySettings) -> bool:
        """Save user VS Code memory settings"""
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
                
                logger.info(f"VS Code user settings saved for {settings.user_id}")
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
            logger.error(f"Error saving VS Code user settings: {e}")
            return False
    
    async def get_ingestion_stats(self, user_id: str) -> VSCodeIngestionStats:
        """Get VS Code ingestion statistics"""
        try:
            if LANCEDB_AVAILABLE and self.stats_table:
                # Query from LanceDB
                results = self.stats_table.search().where(f"user_id = '{user_id}'").to_list()
                if results:
                    stats_data = results[0]
                    return VSCodeIngestionStats(**stats_data)
            
            # Mock database or no results
            default_stats = VSCodeIngestionStats(
                user_id=user_id,
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat()
            )
            
            return default_stats
            
        except Exception as e:
            logger.error(f"Error getting VS Code ingestion stats: {e}")
            return VSCodeIngestionStats(user_id=user_id)
    
    async def update_ingestion_stats(self, user_id: str, projects_count: int = 0,
                                  files_count: int = 0, activities_count: int = 0,
                                  size_mb: float = 0.0, error_message: str = None) -> bool:
        """Update VS Code ingestion statistics"""
        try:
            # Get existing stats
            stats = await self.get_ingestion_stats(user_id)
            
            # Update stats
            stats.total_projects_ingested += projects_count
            stats.total_files_ingested += files_count
            stats.total_activities_ingested += activities_count
            stats.total_size_mb += size_mb
            stats.last_ingestion_timestamp = datetime.utcnow().isoformat()
            stats.updated_at = datetime.utcnow().isoformat()
            
            if files_count > 0 and projects_count > 0:
                stats.avg_files_per_project = stats.total_files_ingested / stats.total_projects_ingested
            
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
            
            logger.info(f"VS Code ingestion stats updated for {user_id}: +{projects_count} projects, +{files_count} files")
            return True
            
        except Exception as e:
            logger.error(f"Error updating VS Code ingestion stats: {e}")
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
            logger.error(f"Error checking VS Code sync requirements: {e}")
            return False
    
    def _should_include_project(self, project_path: str, settings: VSCodeMemorySettings) -> bool:
        """Check if project should be included in sync"""
        project_name = os.path.basename(project_path)
        
        if settings.exclude_projects and project_name in settings.exclude_projects:
            return False
        
        if settings.include_projects and project_name not in settings.include_projects:
            return False
        
        return True
    
    def _should_include_file(self, file_path: str, file_name: str, file_size: int,
                           settings: VSCodeMemorySettings) -> bool:
        """Check if file should be included in sync"""
        # Check file size
        if file_size > settings.max_file_size_mb * 1024 * 1024:
            return False
        
        # Check if hidden file
        is_hidden = file_name.startswith('.')
        if is_hidden and not settings.include_hidden_files:
            return False
        
        # Check if binary file
        is_binary = not self._is_text_file(file_path, file_name)
        if is_binary and not settings.include_binary_files:
            return False
        
        # Check file type inclusion/exclusion
        ext = os.path.splitext(file_name)[1].lower()
        
        if settings.exclude_file_types and ext in settings.exclude_file_types:
            return False
        
        if settings.include_file_types and ext not in settings.include_file_types:
            return False
        
        return True
    
    async def ingest_vscode_project(self, user_id: str, project_path: str,
                                  force_sync: bool = False) -> Dict[str, Any]:
        """Ingest VS Code project files and metadata"""
        try:
            if not VSCODE_SERVICE_AVAILABLE:
                return {
                    'success': False,
                    'error': 'VS Code service not available',
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
            
            # Get workspace information
            workspace_info = await vscode_enhanced_service.get_workspace_info(project_path, user_id)
            
            if not workspace_info:
                return {
                    'success': False,
                    'error': 'Failed to get workspace information',
                    'error_type': 'workspace_error'
                }
            
            # Check if project should be included
            if not self._should_include_project(project_path, settings):
                return {
                    'success': False,
                    'error': 'Project excluded by user settings',
                    'error_type': 'project_excluded'
                }
            
            # Get project structure
            folders, files = await vscode_enhanced_service._get_project_structure(
                project_path, max_depth=10
            )
            
            # Filter files based on settings
            files_to_process = []
            for file_path in files:
                full_path = os.path.join(project_path, file_path)
                try:
                    file_size = os.path.getsize(full_path)
                    file_name = os.path.basename(file_path)
                    
                    if self._should_include_file(file_path, file_name, file_size, settings):
                        files_to_process.append({
                            'path': file_path,
                            'name': file_name,
                            'size': file_size,
                            'full_path': full_path
                        })
                except OSError:
                    continue
            
            # Limit files per project
            files_to_process = files_to_process[:settings.max_files_per_project]
            
            total_files = 0
            total_size = 0
            batch_id = f"{user_id}:{workspace_info.id}:{datetime.utcnow().isoformat()}"
            
            # Process files
            file_memories = []
            for file_info in files_to_process:
                try:
                    # Get file content
                    file_content = await vscode_enhanced_service.get_file_content(
                        project_path, file_info['path']
                    )
                    
                    if file_content:
                        # Create file memory record
                        file_memory = VSCodeFileMemory(
                            id=self._generate_file_id(user_id, workspace_info.id, file_info['path']),
                            user_id=user_id,
                            project_id=workspace_info.id,
                            project_name=workspace_info.name,
                            file_path=file_info['path'],
                            file_name=file_info['name'],
                            extension=os.path.splitext(file_info['name'])[1],
                            language=file_content.language,
                            size=file_info['size'],
                            created_at=file_content.created_at,
                            modified_at=file_content.modified_at,
                            content=file_content.content,
                            content_hash=self._calculate_content_hash(file_content.content),
                            line_count=file_content.line_count,
                            char_count=file_content.char_count,
                            encoding=file_content.encoding,
                            is_binary=not self._is_text_file(file_info['path'], file_info['name']),
                            is_hidden=file_info['name'].startswith('.'),
                            git_status='',
                            build_system=workspace_info.build_system,
                            metadata={
                                'source': 'vscode',
                                'project_id': workspace_info.id,
                                'batch_id': batch_id,
                                'ingested_at': datetime.utcnow().isoformat()
                            }
                        )
                        
                        file_memories.append(file_memory)
                        total_files += 1
                        total_size += file_info['size'] / (1024 * 1024)  # Convert to MB
                        
                        # Batch insert every 100 files
                        if len(file_memories) >= 100:
                            await self._store_files_batch(file_memories)
                            file_memories = []
                
                except Exception as e:
                    logger.error(f"Error processing VS Code file {file_info['path']}: {e}")
                    continue
            
            # Insert remaining files
            if file_memories:
                await self._store_files_batch(file_memories)
            
            # Store project metadata
            project_memory = VSCodeProjectMemory(
                id=f"project:{user_id}:{workspace_info.id}",
                user_id=user_id,
                project_name=workspace_info.name,
                project_path=workspace_info.path,
                project_type=workspace_info.type,
                build_system=workspace_info.build_system,
                language_stats=workspace_info.language_stats,
                total_files=total_files,
                total_size=int(total_size * 1024 * 1024),  # Convert back to bytes
                git_info=workspace_info.git_info,
                extensions=workspace_info.extensions,
                settings=workspace_info.settings,
                last_activity=workspace_info.last_activity,
                created_at=workspace_info.created_at,
                updated_at=datetime.utcnow().isoformat(),
                metadata={
                    'source': 'vscode',
                    'workspace_id': workspace_info.id,
                    'batch_id': batch_id,
                    'ingested_at': datetime.utcnow().isoformat()
                }
            )
            
            await self._store_project(project_memory)
            
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
                projects_count=1,
                files_count=total_files,
                size_mb=total_size
            )
            
            logger.info(f"VS Code project ingestion completed for {user_id}: {total_files} files from {workspace_info.name}")
            
            return {
                'success': True,
                'project_ingested': workspace_info.name,
                'files_ingested': total_files,
                'total_size_mb': round(total_size, 2),
                'batch_id': batch_id,
                'next_sync': settings.next_sync_timestamp,
                'sync_frequency': settings.sync_frequency
            }
            
        except Exception as e:
            logger.error(f"Error in VS Code project ingestion: {e}")
            
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
    
    async def ingest_vscode_activity(self, user_id: str, activity_data: Dict[str, Any]) -> bool:
        """Ingest VS Code development activity"""
        try:
            if not activity_data or not activity_data.get('action_type'):
                return False
            
            activity_memory = VSCodeActivityMemory(
                id=f"activity:{user_id}:{datetime.utcnow().timestamp()}",
                user_id=user_id,
                project_id=activity_data.get('project_id', ''),
                project_name=activity_data.get('project_name', ''),
                session_id=activity_data.get('session_id', f"session_{datetime.utcnow().timestamp()}"),
                action_type=activity_data['action_type'],
                file_path=activity_data.get('file_path', ''),
                file_name=os.path.basename(activity_data.get('file_path', '')),
                language=activity_data.get('language', ''),
                content_before=activity_data.get('content_before', ''),
                content_after=activity_data.get('content_after', ''),
                change_summary=activity_data.get('change_summary', ''),
                timestamp=activity_data.get('timestamp', datetime.utcnow().isoformat()),
                duration_seconds=activity_data.get('duration_seconds', 0),
                git_commit_hash=activity_data.get('git_commit_hash', ''),
                metadata={
                    'source': 'vscode',
                    'user_agent': activity_data.get('user_agent'),
                    'vscode_version': activity_data.get('vscode_version'),
                    'ingested_at': datetime.utcnow().isoformat()
                }
            )
            
            # Store activity
            await self._store_activity(activity_memory)
            
            # Update ingestion stats
            await self.update_ingestion_stats(user_id, activities_count=1)
            
            logger.info(f"VS Code activity ingested: {activity_data['action_type']}")
            return True
            
        except Exception as e:
            logger.error(f"Error ingesting VS Code activity: {e}")
            return False
    
    async def _store_files_batch(self, files: List[VSCodeFileMemory]) -> bool:
        """Store batch of files in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.files_table:
                # Convert to LanceDB format
                batch_data = [file.to_lancedb_schema() for file in files]
                
                # Add batch to table
                self.files_table.add(batch_data)
                
                logger.info(f"Stored {len(files)} VS Code files in LanceDB")
                return True
            else:
                # Mock database
                batch_data = [asdict(file) for file in files]
                self.files_table.data.extend(batch_data)
                
                logger.info(f"Stored {len(files)} VS Code files in mock DB")
                return True
                
        except Exception as e:
            logger.error(f"Error storing VS Code files batch: {e}")
            return False
    
    async def _store_project(self, project: VSCodeProjectMemory) -> bool:
        """Store project metadata in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.projects_table:
                # Remove existing project
                self.projects_table.delete(f"user_id = '{project.user_id}' AND project_id = '{project.project_id}'")
                
                # Add new project
                project_data = [project.to_lancedb_schema()]
                self.projects_table.add(project_data)
                
                logger.info(f"Stored VS Code project: {project.project_name}")
                return True
            else:
                # Mock database
                # Remove existing
                self.projects_table.data = [
                    p for p in self.projects_table.data 
                    if not (p.get('user_id') == project.user_id and p.get('project_id') == project.project_id)
                ]
                
                # Add new
                self.projects_table.data.append(asdict(project))
                
                logger.info(f"Stored VS Code project in mock DB: {project.project_name}")
                return True
                
        except Exception as e:
            logger.error(f"Error storing VS Code project: {e}")
            return False
    
    async def _store_activity(self, activity: VSCodeActivityMemory) -> bool:
        """Store activity in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.activities_table:
                # Add activity to table
                activity_data = [activity.to_lancedb_schema()]
                self.activities_table.add(activity_data)
                
                logger.info(f"Stored VS Code activity: {activity.action_type}")
                return True
            else:
                # Mock database
                self.activities_table.data.append(asdict(activity))
                
                logger.info(f"Stored VS Code activity in mock DB: {activity.action_type}")
                return True
                
        except Exception as e:
            logger.error(f"Error storing VS Code activity: {e}")
            return False
    
    async def search_vscode_files(self, user_id: str, query: str, 
                                project_id: str = None, language: str = None,
                                limit: int = 50, date_from: str = None,
                                date_to: str = None) -> List[Dict[str, Any]]:
        """Search VS Code files in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.files_table:
                # Build query
                where_clauses = [f"user_id = '{user_id}'"]
                
                if project_id:
                    where_clauses.append(f"project_id = '{project_id}'")
                
                if language:
                    where_clauses.append(f"language = '{language}'")
                
                if date_from:
                    where_clauses.append(f"modified_at >= '{date_from}'")
                
                if date_to:
                    where_clauses.append(f"modified_at <= '{date_to}'")
                
                where_clause = " AND ".join(where_clauses)
                
                # Perform search
                if query:
                    # Text search
                    results = (self.files_table
                             .search(query)
                             .where(where_clause)
                             .limit(limit)
                             .to_list())
                else:
                    # Filter only
                    results = (self.files_table
                             .search()
                             .where(where_clause)
                             .limit(limit)
                             .to_list())
                
                return results
            else:
                # Mock database search
                all_files = self.files_table.data
                
                # Filter by user
                filtered_files = [file for file in all_files if file.get('user_id') == user_id]
                
                # Apply additional filters
                if project_id:
                    filtered_files = [file for file in filtered_files if file.get('project_id') == project_id]
                
                if language:
                    filtered_files = [file for file in filtered_files if file.get('language') == language]
                
                if query:
                    filtered_files = [file for file in filtered_files 
                                      if query.lower() in file.get('content', '').lower() or 
                                         query.lower() in file.get('file_name', '').lower()]
                
                # Sort by modified date and limit
                filtered_files.sort(key=lambda x: x.get('modified_at', ''), reverse=True)
                
                return filtered_files[:limit]
                
        except Exception as e:
            logger.error(f"Error searching VS Code files: {e}")
            return []
    
    async def search_vscode_activities(self, user_id: str, query: str,
                                    project_id: str = None, action_type: str = None,
                                    limit: int = 50, date_from: str = None,
                                    date_to: str = None) -> List[Dict[str, Any]]:
        """Search VS Code activities in LanceDB"""
        try:
            if LANCEDB_AVAILABLE and self.activities_table:
                # Build query
                where_clauses = [f"user_id = '{user_id}'"]
                
                if project_id:
                    where_clauses.append(f"project_id = '{project_id}'")
                
                if action_type:
                    where_clauses.append(f"action_type = '{action_type}'")
                
                if date_from:
                    where_clauses.append(f"timestamp >= '{date_from}'")
                
                if date_to:
                    where_clauses.append(f"timestamp <= '{date_to}'")
                
                where_clause = " AND ".join(where_clauses)
                
                # Perform search
                if query:
                    # Text search
                    results = (self.activities_table
                             .search(query)
                             .where(where_clause)
                             .limit(limit)
                             .to_list())
                else:
                    # Filter only
                    results = (self.activities_table
                             .search()
                             .where(where_clause)
                             .limit(limit)
                             .to_list())
                
                return results
            else:
                # Mock database search
                all_activities = self.activities_table.data
                
                # Filter by user
                filtered_activities = [activity for activity in all_activities if activity.get('user_id') == user_id]
                
                # Apply additional filters
                if project_id:
                    filtered_activities = [activity for activity in filtered_activities if activity.get('project_id') == project_id]
                
                if action_type:
                    filtered_activities = [activity for activity in filtered_activities if activity.get('action_type') == action_type]
                
                if query:
                    filtered_activities = [activity for activity in filtered_activities 
                                          if query.lower() in activity.get('change_summary', '').lower()]
                
                # Sort by timestamp and limit
                filtered_activities.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                
                return filtered_activities[:limit]
                
        except Exception as e:
            logger.error(f"Error searching VS Code activities: {e}")
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
                    'total_projects_ingested': stats.total_projects_ingested,
                    'total_files_ingested': stats.total_files_ingested,
                    'total_activities_ingested': stats.total_activities_ingested,
                    'total_size_mb': stats.total_size_mb,
                    'failed_ingestions': stats.failed_ingestions,
                    'last_ingestion_timestamp': stats.last_ingestion_timestamp,
                    'avg_files_per_project': stats.avg_files_per_project,
                    'avg_processing_time_ms': stats.avg_processing_time_ms
                },
                'settings': {
                    'include_projects': settings.include_projects or [],
                    'exclude_projects': settings.exclude_projects or [],
                    'include_file_types': settings.include_file_types or [],
                    'exclude_file_types': settings.exclude_file_types or [],
                    'max_file_size_mb': settings.max_file_size_mb,
                    'max_files_per_project': settings.max_files_per_project,
                    'include_hidden_files': settings.include_hidden_files,
                    'include_binary_files': settings.include_binary_files,
                    'code_search_enabled': settings.code_search_enabled,
                    'semantic_search_enabled': settings.semantic_search_enabled,
                    'metadata_extraction_enabled': settings.metadata_extraction_enabled,
                    'activity_logging_enabled': settings.activity_logging_enabled
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting VS Code sync status: {e}")
            return {
                'user_id': user_id,
                'error': str(e),
                'error_type': 'status_error'
            }
    
    async def delete_user_data(self, user_id: str) -> bool:
        """Delete all VS Code data for user"""
        try:
            # Delete from all tables
            if LANCEDB_AVAILABLE:
                self.files_table.delete(f"user_id = '{user_id}'")
                self.activities_table.delete(f"user_id = '{user_id}'")
                self.projects_table.delete(f"user_id = '{user_id}'")
                self.settings_table.delete(f"user_id = '{user_id}'")
                self.stats_table.delete(f"user_id = '{user_id}'")
            else:
                # Mock database
                self.files_table.data = [file for file in self.files_table.data 
                                       if file.get('user_id') != user_id]
                self.activities_table.data = [activity for activity in self.activities_table.data 
                                            if activity.get('user_id') != user_id]
                self.projects_table.data = [project for project in self.projects_table.data 
                                          if project.get('user_id') != user_id]
                self.settings_table.data = [settings for settings in self.settings_table.data 
                                          if settings.get('user_id') != user_id]
                self.stats_table.data = [stats for stats in self.stats_table.data 
                                       if stats.get('user_id') != user_id]
            
            logger.info(f"All VS Code data deleted for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting VS Code user data: {e}")
            return False

# Create singleton instance
vscode_lancedb_service = VSCodeLanceDBIngestionService()