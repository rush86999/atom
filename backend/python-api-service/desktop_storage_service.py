"""
ATOM Desktop Storage System
Local storage as primary with S3 as secondary backup
"""

import os
import json
import sqlite3
import shutil
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Import storage backends
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

# Import ATOM components
try:
    import lancedb
    import pyarrow as pa
    from lancedb import LanceDB
    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False

logger = logging.getLogger(__name__)


class LocalStorageConfig:
    """Configuration for local storage"""
    
    def __init__(
        self,
        base_path: str = None,
        max_local_size_gb: float = 50.0,
        compression_enabled: bool = True,
        encryption_enabled: bool = False
    ):
        self.base_path = Path(base_path or self._get_default_path())
        self.max_local_size_bytes = int(max_local_size_gb * 1024 * 1024 * 1024)
        self.compression_enabled = compression_enabled
        self.encryption_enabled = encryption_enabled
        
        # Ensure base path exists
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_default_path(self) -> Path:
        """Get default local storage path based on OS"""
        if os.name == 'nt':  # Windows
            return Path(os.environ.get('LOCALAPPDATA', 'C:/Users')) / 'ATOM' / 'Storage'
        elif os.name == 'posix':  # macOS/Linux
            home = Path.home()
            if os.path.exists('/Applications'):  # macOS
                return home / 'Library' / 'Application Support' / 'ATOM' / 'Storage'
            else:  # Linux
                return home / '.local' / 'share' / 'atom' / 'storage'
        else:
            return Path('./atom_storage')
    
    @property
    def db_path(self) -> Path:
        return self.base_path / 'data' / 'atom.db'
    
    @property
    def lancedb_path(self) -> Path:
        return self.base_path / 'lancedb'
    
    @property
    def cache_path(self) -> Path:
        return self.base_path / 'cache'
    
    @property
    def backup_path(self) -> Path:
        return self.base_path / 'backups'
    
    @property
    def temp_path(self) -> Path:
        return self.base_path / 'temp'


class S3StorageConfig:
    """Configuration for S3 backup storage"""
    
    def __init__(
        self,
        bucket_name: str,
        region: str = 'us-west-2',
        prefix: str = 'atom-desktop/',
        access_key_id: str = None,
        secret_access_key: str = None,
        session_token: str = None,
        endpoint_url: str = None,
        storage_class: str = 'STANDARD',
        lifecycle_days: int = 90
    ):
        self.bucket_name = bucket_name
        self.region = region
        self.prefix = prefix
        self.access_key_id = access_key_id or os.getenv('AWS_ACCESS_KEY_ID')
        self.secret_access_key = secret_access_key or os.getenv('AWS_SECRET_ACCESS_KEY')
        self.session_token = session_token or os.getenv('AWS_SESSION_TOKEN')
        self.endpoint_url = endpoint_url
        self.storage_class = storage_class
        self.lifecycle_days = lifecycle_days
    
    def validate(self) -> bool:
        """Validate S3 configuration"""
        return (
            self.bucket_name and
            self.access_key_id and
            self.secret_access_key
        )


class StorageQuota:
    """Storage quota management"""
    
    def __init__(self, local_config: LocalStorageConfig):
        self.local_config = local_config
        self.quota_info = self._get_quota_info()
    
    def _get_quota_info(self) -> Dict[str, Any]:
        """Get current storage usage"""
        total_size = 0
        file_count = 0
        
        for root, dirs, files in os.walk(self.local_config.base_path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    file_size = os.path.getsize(file_path)
                    total_size += file_size
                    file_count += 1
                except OSError:
                    continue
        
        return {
            'total_size_bytes': total_size,
            'total_size_gb': total_size / (1024 * 1024 * 1024),
            'total_size_mb': total_size / (1024 * 1024),
            'file_count': file_count,
            'max_size_gb': self.local_config.max_local_size_bytes / (1024 * 1024 * 1024),
            'available_bytes': self.local_config.max_local_size_bytes - total_size,
            'usage_percentage': (total_size / self.local_config.max_local_size_bytes) * 100
        }
    
    def is_quota_exceeded(self) -> bool:
        """Check if local storage quota is exceeded"""
        return self.quota_info['total_size_bytes'] >= self.local_config.max_local_size_bytes
    
    def get_cleanup_candidates(self) -> List[str]:
        """Get files that can be cleaned up to free space"""
        candidates = []
        
        # Prioritize cache files, temp files, old backups
        cleanup_dirs = [
            self.local_config.cache_path,
            self.local_config.temp_path,
            self.local_config.backup_path
        ]
        
        for cleanup_dir in cleanup_dirs:
            if cleanup_dir.exists():
                for item in cleanup_dir.iterdir():
                    candidates.append(str(item))
        
        return sorted(candidates, key=os.path.getctime, reverse=True)


class LocalStorageManager:
    """Primary local storage manager"""
    
    def __init__(self, config: LocalStorageConfig):
        self.config = config
        self.quota = StorageQuota(config)
        self.lancedb_client: Optional[LanceDB] = None
        self.db_connection: Optional[sqlite3.Connection] = None
        
        # Initialize storage directories
        self._initialize_directories()
        
        # Initialize databases
        self._initialize_databases()
        
        logger.info(f"Initialized local storage at: {config.base_path}")
    
    def _initialize_directories(self):
        """Create necessary directories"""
        directories = [
            self.config.db_path.parent,
            self.config.lancedb_path,
            self.config.cache_path,
            self.config.backup_path,
            self.config.temp_path
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _initialize_databases(self):
        """Initialize SQLite and LanceDB databases"""
        try:
            # Initialize SQLite for metadata
            self.db_connection = sqlite3.connect(self.config.db_path)
            self._create_metadata_tables()
            
            # Initialize LanceDB for vector storage
            if LANCEDB_AVAILABLE:
                self.lancedb_client = LanceDB.create(self.config.lancedb_path)
                logger.info("Initialized LanceDB client")
            else:
                logger.warning("LanceDB not available")
            
        except Exception as e:
            logger.error(f"Failed to initialize databases: {e}")
            raise
    
    def _create_metadata_tables(self):
        """Create metadata tables"""
        cursor = self.db_connection.cursor()
        
        # Files table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                local_path TEXT UNIQUE NOT NULL,
                s3_key TEXT,
                file_size INTEGER NOT NULL,
                hash TEXT,
                mime_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_synced_at TIMESTAMP,
                sync_status TEXT DEFAULT 'local',
                is_encrypted BOOLEAN DEFAULT FALSE,
                metadata JSON
            )
        ''')
        
        # Sync log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT,
                operation TEXT NOT NULL,
                status TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                error_message TEXT,
                bytes_transferred INTEGER
            )
        ''')
        
        # Storage stats table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS storage_stats (
                id INTEGER PRIMARY KEY,
                total_files INTEGER DEFAULT 0,
                total_size INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_files_sync_status ON files(sync_status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_files_last_synced ON files(last_synced_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sync_log_timestamp ON sync_log(timestamp)')
        
        self.db_connection.commit()
    
    def store_file(
        self,
        file_id: str,
        local_path: str,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """Store file metadata in local storage"""
        try:
            # Get file info
            if not os.path.exists(local_path):
                logger.error(f"File does not exist: {local_path}")
                return False
            
            file_stat = os.stat(local_path)
            file_size = file_stat.st_size
            
            # Calculate file hash
            file_hash = self._calculate_file_hash(local_path)
            
            # Determine MIME type
            mime_type = self._get_mime_type(local_path)
            
            cursor = self.db_connection.cursor()
            
            # Insert or update file record
            cursor.execute('''
                INSERT OR REPLACE INTO files (
                    id, filename, local_path, file_size, hash, 
                    mime_type, updated_at, metadata, sync_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'local')
            ''', (
                file_id,
                os.path.basename(local_path),
                local_path,
                file_size,
                file_hash,
                mime_type,
                datetime.now(timezone.utc).isoformat(),
                json.dumps(metadata) if metadata else None
            ))
            
            self.db_connection.commit()
            self._update_storage_stats()
            
            logger.debug(f"Stored file metadata: {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store file metadata: {e}")
            return False
    
    def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file metadata"""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute('''
                SELECT * FROM files WHERE id = ?
            ''', (file_id,))
            
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                file_data = dict(zip(columns, row))
                
                # Parse JSON metadata
                if file_data.get('metadata'):
                    file_data['metadata'] = json.loads(file_data['metadata'])
                
                return file_data
            else:
                return None
                
        except Exception as e:
            logger.error(f"Failed to get file metadata: {e}")
            return None
    
    def list_files(
        self,
        sync_status: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List files with optional filtering"""
        try:
            cursor = self.db_connection.cursor()
            
            query = 'SELECT * FROM files'
            params = []
            
            if sync_status:
                query += ' WHERE sync_status = ?'
                params.append(sync_status)
            
            query += ' ORDER BY updated_at DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            columns = [description[0] for description in cursor.description]
            files = []
            
            for row in rows:
                file_data = dict(zip(columns, row))
                if file_data.get('metadata'):
                    file_data['metadata'] = json.loads(file_data['metadata'])
                files.append(file_data)
            
            return files
            
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []
    
    def update_sync_status(self, file_id: str, s3_key: str, sync_status: str):
        """Update file sync status"""
        try:
            cursor = self.db_connection.cursor()
            
            cursor.execute('''
                UPDATE files 
                SET s3_key = ?, sync_status = ?, last_synced_at = ?
                WHERE id = ?
            ''', (
                s3_key,
                sync_status,
                datetime.now(timezone.utc).isoformat(),
                file_id
            ))
            
            self.db_connection.commit()
            
        except Exception as e:
            logger.error(f"Failed to update sync status: {e}")
    
    def log_sync_operation(
        self,
        file_id: str,
        operation: str,
        status: str,
        error_message: str = None,
        bytes_transferred: int = None
    ):
        """Log a sync operation"""
        try:
            cursor = self.db_connection.cursor()
            
            cursor.execute('''
                INSERT INTO sync_log (
                    file_id, operation, status, error_message, bytes_transferred
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                file_id, operation, status, error_message, bytes_transferred
            ))
            
            self.db_connection.commit()
            
        except Exception as e:
            logger.error(f"Failed to log sync operation: {e}")
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file"""
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate file hash: {e}")
            return ""
    
    def _get_mime_type(self, file_path: str) -> str:
        """Get MIME type of file"""
        import mimetypes
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type or 'application/octet-stream'
    
    def _update_storage_stats(self):
        """Update storage statistics"""
        try:
            cursor = self.db_connection.cursor()
            
            # Calculate current stats
            cursor.execute('SELECT COUNT(*), SUM(file_size) FROM files')
            result = cursor.fetchone()
            file_count, total_size = result[0], result[1] or 0
            
            # Update stats table
            cursor.execute('''
                INSERT OR REPLACE INTO storage_stats (id, total_files, total_size, last_updated)
                VALUES (1, ?, ?, ?)
            ''', (
                file_count,
                total_size,
                datetime.now(timezone.utc).isoformat()
            ))
            
            self.db_connection.commit()
            
        except Exception as e:
            logger.error(f"Failed to update storage stats: {e}")
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get comprehensive storage statistics"""
        try:
            cursor = self.db_connection.cursor()
            
            # Get current stats
            cursor.execute('SELECT * FROM storage_stats WHERE id = 1')
            row = cursor.fetchone()
            
            if row:
                columns = [description[0] for description in cursor.description]
                stats = dict(zip(columns, row))
            else:
                stats = {}
            
            # Add quota info
            stats.update(self.quota._get_quota_info())
            
            # Get sync status breakdown
            cursor.execute('''
                SELECT sync_status, COUNT(*) as count
                FROM files
                GROUP BY sync_status
            ''')
            
            sync_breakdown = dict(cursor.fetchall())
            stats['sync_breakdown'] = sync_breakdown
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {}
    
    def cleanup_old_files(self, days: int = 30) -> int:
        """Clean up old cache and temp files"""
        try:
            cleaned_count = 0
            cutoff_time = datetime.now().timestamp() - (days * 24 * 3600)
            
            # Clean cache directory
            if self.config.cache_path.exists():
                for item in self.config.cache_path.iterdir():
                    if item.stat().st_mtime < cutoff_time:
                        if item.is_file():
                            item.unlink()
                        else:
                            shutil.rmtree(item)
                        cleaned_count += 1
            
            # Clean temp directory
            if self.config.temp_path.exists():
                for item in self.config.temp_path.iterdir():
                    if item.stat().st_mtime < cutoff_time:
                        if item.is_file():
                            item.unlink()
                        else:
                            shutil.rmtree(item)
                        cleaned_count += 1
            
            logger.info(f"Cleaned up {cleaned_count} old files")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old files: {e}")
            return 0
    
    def close(self):
        """Close storage connections"""
        try:
            if self.db_connection:
                self.db_connection.close()
            
            if self.lancedb_client:
                self.lancedb_client.close()
                
            logger.info("Closed local storage connections")
            
        except Exception as e:
            logger.error(f"Error closing storage connections: {e}")


class S3StorageManager:
    """Secondary S3 backup storage manager"""
    
    def __init__(self, config: S3StorageConfig):
        self.config = config
        self.s3_client = None
        self.s3_resource = None
        
        # Initialize S3 client
        self._initialize_s3()
        
        logger.info(f"Initialized S3 storage for bucket: {config.bucket_name}")
    
    def _initialize_s3(self):
        """Initialize AWS S3 client"""
        try:
            if not BOTO3_AVAILABLE:
                raise ImportError("boto3 not available")
            
            if not self.config.validate():
                raise ValueError("Invalid S3 configuration")
            
            # Create S3 client
            client_kwargs = {
                'region_name': self.config.region
            }
            
            if self.config.access_key_id and self.config.secret_access_key:
                client_kwargs.update({
                    'aws_access_key_id': self.config.access_key_id,
                    'aws_secret_access_key': self.config.secret_access_key
                })
            
            if self.config.session_token:
                client_kwargs['aws_session_token'] = self.config.session_token
            
            if self.config.endpoint_url:
                client_kwargs['endpoint_url'] = self.config.endpoint_url
            
            self.s3_client = boto3.client('s3', **client_kwargs)
            self.s3_resource = boto3.resource('s3', **client_kwargs)
            
            # Test connection
            self.s3_client.head_bucket(Bucket=self.config.bucket_name)
            
            # Configure lifecycle if needed
            self._configure_lifecycle()
            
        except (ClientError, NoCredentialsError) as e:
            logger.error(f"Failed to initialize S3: {e}")
            raise
    
    def _configure_lifecycle(self):
        """Configure S3 bucket lifecycle"""
        try:
            lifecycle_configuration = {
                'Rules': [
                    {
                        'ID': 'AtomStorageCleanup',
                        'Status': 'Enabled',
                        'Expiration': {
                            'Days': self.config.lifecycle_days
                        },
                        'Filter': {
                            'Prefix': self.config.prefix
                        }
                    }
                ]
            }
            
            self.s3_client.put_bucket_lifecycle_configuration(
                Bucket=self.config.bucket_name,
                LifecycleConfiguration=lifecycle_configuration
            )
            
            logger.info(f"Configured S3 lifecycle rule for {self.config.lifecycle_days} days")
            
        except ClientError as e:
            logger.warning(f"Failed to configure S3 lifecycle: {e}")
    
    def upload_file(
        self,
        local_path: str,
        s3_key: str,
        metadata: Dict[str, Any] = None,
        progress_callback=None
    ) -> bool:
        """Upload file to S3"""
        try:
            # Prepare upload arguments
            upload_args = {
                'Key': s3_key,
                'StorageClass': self.config.storage_class
            }
            
            # Add metadata
            if metadata:
                upload_args['Metadata'] = metadata
            
            # Upload file
            self.s3_client.upload_file(
                local_path,
                self.config.bucket_name,
                s3_key,
                ExtraArgs=upload_args,
                Callback=progress_callback
            )
            
            logger.debug(f"Uploaded file to S3: {s3_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to upload file to S3: {e}")
            return False
    
    def download_file(
        self,
        s3_key: str,
        local_path: str,
        progress_callback=None
    ) -> bool:
        """Download file from S3"""
        try:
            # Download file
            self.s3_client.download_file(
                self.config.bucket_name,
                s3_key,
                local_path,
                Callback=progress_callback
            )
            
            logger.debug(f"Downloaded file from S3: {s3_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to download file from S3: {e}")
            return False
    
    def delete_file(self, s3_key: str) -> bool:
        """Delete file from S3"""
        try:
            self.s3_client.delete_object(
                Bucket=self.config.bucket_name,
                Key=s3_key
            )
            
            logger.debug(f"Deleted file from S3: {s3_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to delete file from S3: {e}")
            return False
    
    def file_exists(self, s3_key: str) -> bool:
        """Check if file exists in S3"""
        try:
            self.s3_client.head_object(
                Bucket=self.config.bucket_name,
                Key=s3_key
            )
            return True
            
        except ClientError:
            return False
    
    def get_file_metadata(self, s3_key: str) -> Optional[Dict[str, Any]]:
        """Get file metadata from S3"""
        try:
            response = self.s3_client.head_object(
                Bucket=self.config.bucket_name,
                Key=s3_key
            )
            
            return {
                'content_length': response.get('ContentLength'),
                'last_modified': response.get('LastModified'),
                'content_type': response.get('ContentType'),
                'metadata': response.get('Metadata', {}),
                'etag': response.get('ETag')
            }
            
        except ClientError as e:
            logger.error(f"Failed to get S3 file metadata: {e}")
            return None
    
    def list_files(self, prefix: str = None, max_keys: int = 1000) -> List[Dict[str, Any]]:
        """List files in S3 bucket"""
        try:
            list_kwargs = {
                'Bucket': self.config.bucket_name,
                'MaxKeys': max_keys
            }
            
            if prefix:
                list_kwargs['Prefix'] = prefix
            else:
                list_kwargs['Prefix'] = self.config.prefix
            
            files = []
            paginator = self.s3_client.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(**list_kwargs):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        files.append({
                            'key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'],
                            'etag': obj['ETag']
                        })
            
            return files
            
        except ClientError as e:
            logger.error(f"Failed to list S3 files: {e}")
            return []
    
    def get_storage_usage(self) -> Dict[str, Any]:
        """Get S3 storage usage statistics"""
        try:
            # Get total size and object count
            total_size = 0
            object_count = 0
            
            paginator = self.s3_client.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(
                Bucket=self.config.bucket_name,
                Prefix=self.config.prefix
            ):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        total_size += obj['Size']
                        object_count += 1
            
            return {
                'total_size_bytes': total_size,
                'total_size_gb': total_size / (1024 * 1024 * 1024),
                'object_count': object_count,
                'bucket_name': self.config.bucket_name,
                'prefix': self.config.prefix
            }
            
        except ClientError as e:
            logger.error(f"Failed to get S3 storage usage: {e}")
            return {}


class DesktopStorageManager:
    """Unified desktop storage manager combining local and S3 storage"""
    
    def __init__(
        self,
        local_config: LocalStorageConfig,
        s3_config: S3StorageConfig = None,
        auto_sync: bool = True,
        sync_interval_minutes: int = 30
    ):
        self.local_manager = LocalStorageManager(local_config)
        self.s3_manager = S3StorageManager(s3_config) if s3_config else None
        self.auto_sync = auto_sync
        self.sync_interval_seconds = sync_interval_minutes * 60
        self.sync_task: Optional[asyncio.Task] = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Sync status
        self.is_syncing = False
        self.last_sync_time = None
        
        logger.info("Initialized desktop storage manager")
    
    async def start_sync_service(self):
        """Start automatic sync service"""
        if not self.auto_sync or not self.s3_manager:
            logger.info("Auto-sync disabled or S3 not configured")
            return
        
        self.sync_task = asyncio.create_task(self._sync_loop())
        logger.info("Started auto-sync service")
    
    async def stop_sync_service(self):
        """Stop automatic sync service"""
        if self.sync_task:
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass
            self.sync_task = None
        
        logger.info("Stopped auto-sync service")
    
    async def _sync_loop(self):
        """Main sync loop"""
        while True:
            try:
                await self.sync_to_cloud()
                await asyncio.sleep(self.sync_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
                await asyncio.sleep(60)  # Wait before retry
    
    async def sync_to_cloud(self) -> Dict[str, Any]:
        """Sync local files to S3"""
        if not self.s3_manager or self.is_syncing:
            return {"status": "skipped", "reason": "S3 not configured or sync in progress"}
        
        self.is_syncing = True
        sync_start = datetime.now()
        
        try:
            # Get files that need syncing
            files_to_sync = self.local_manager.list_files(
                sync_status='local',
                limit=100
            )
            
            if not files_to_sync:
                logger.info("No files to sync")
                return {
                    "status": "success",
                    "synced_files": 0,
                    "duration_seconds": (datetime.now() - sync_start).total_seconds()
                }
            
            # Sync files in parallel
            sync_tasks = []
            for file_data in files_to_sync:
                sync_tasks.append(
                    self._sync_single_file(file_data)
                )
            
            sync_results = await asyncio.gather(*sync_tasks, return_exceptions=True)
            
            # Count successful syncs
            successful_syncs = sum(
                1 for result in sync_results
                if isinstance(result, bool) and result
            )
            
            self.last_sync_time = datetime.now()
            
            return {
                "status": "success",
                "total_files": len(files_to_sync),
                "synced_files": successful_syncs,
                "failed_files": len(files_to_sync) - successful_syncs,
                "duration_seconds": (datetime.now() - sync_start).total_seconds(),
                "synced_at": self.last_sync_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Sync to cloud failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "duration_seconds": (datetime.now() - sync_start).total_seconds()
            }
        finally:
            self.is_syncing = False
    
    async def _sync_single_file(self, file_data: Dict[str, Any]) -> bool:
        """Sync a single file to S3"""
        try:
            file_id = file_data['id']
            local_path = file_data['local_path']
            
            # Generate S3 key
            s3_key = f"atom-desktop/{file_id}/{file_data['filename']}"
            
            # Check if file already exists in S3
            if self.s3_manager.file_exists(s3_key):
                # Compare file hashes if available
                local_hash = file_data.get('hash')
                s3_metadata = self.s3_manager.get_file_metadata(s3_key)
                
                if s3_metadata and s3_metadata.get('metadata', {}).get('hash') == local_hash:
                    # File is already synced and unchanged
                    self.local_manager.update_sync_status(
                        file_id, s3_key, 'synced'
                    )
                    self.local_manager.log_sync_operation(
                        file_id, 'verify', 'success', bytes_transferred=0
                    )
                    return True
            
            # Upload file to S3
            loop = asyncio.get_event_loop()
            
            def upload():
                return self.s3_manager.upload_file(
                    local_path=local_path,
                    s3_key=s3_key,
                    metadata={'hash': file_data.get('hash')}
                )
            
            upload_success = await loop.run_in_executor(self.executor, upload)
            
            if upload_success:
                self.local_manager.update_sync_status(
                    file_id, s3_key, 'synced'
                )
                self.local_manager.log_sync_operation(
                    file_id, 'upload', 'success',
                    bytes_transferred=file_data['file_size']
                )
                return True
            else:
                self.local_manager.log_sync_operation(
                    file_id, 'upload', 'failed', 'Upload to S3 failed'
                )
                return False
                
        except Exception as e:
            logger.error(f"Failed to sync file {file_data.get('id')}: {e}")
            self.local_manager.log_sync_operation(
                file_data.get('id'), 'upload', 'failed', str(e)
            )
            return False
    
    async def restore_from_cloud(
        self,
        file_id: str,
        local_path: str = None
    ) -> bool:
        """Restore file from S3"""
        if not self.s3_manager:
            return False
        
        try:
            # Get file metadata from local storage
            file_data = self.local_manager.get_file(file_id)
            if not file_data:
                logger.error(f"File not found in local storage: {file_id}")
                return False
            
            # Generate S3 key
            s3_key = file_data.get('s3_key') or f"atom-desktop/{file_id}/{file_data['filename']}"
            
            # Determine local path
            restore_path = local_path or file_data['local_path']
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(restore_path), exist_ok=True)
            
            # Download file
            loop = asyncio.get_event_loop()
            
            def download():
                return self.s3_manager.download_file(s3_key, restore_path)
            
            download_success = await loop.run_in_executor(self.executor, download)
            
            if download_success:
                self.local_manager.log_sync_operation(
                    file_id, 'restore', 'success',
                    bytes_transferred=file_data['file_size']
                )
                return True
            else:
                self.local_manager.log_sync_operation(
                    file_id, 'restore', 'failed', 'Download from S3 failed'
                )
                return False
                
        except Exception as e:
            logger.error(f"Failed to restore file {file_id}: {e}")
            self.local_manager.log_sync_operation(
                file_id, 'restore', 'failed', str(e)
            )
            return False
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive storage statistics"""
        stats = {
            'local_storage': self.local_manager.get_storage_stats(),
            'sync_status': {
                'auto_sync_enabled': self.auto_sync,
                'is_syncing': self.is_syncing,
                'last_sync_time': self.last_sync_time.isoformat() if self.last_sync_time else None,
                'sync_interval_minutes': self.sync_interval_seconds / 60
            }
        }
        
        # Add S3 stats if available
        if self.s3_manager:
            stats['cloud_storage'] = self.s3_manager.get_storage_usage()
        else:
            stats['cloud_storage'] = {'status': 'not_configured'}
        
        return stats
    
    async def cleanup_storage(self, cleanup_days: int = 30) -> Dict[str, Any]:
        """Cleanup storage (local cache and old backups)"""
        try:
            # Cleanup local files
            local_cleaned = self.local_manager.cleanup_old_files(cleanup_days)
            
            # Cleanup S3 if available (files older than lifecycle days)
            s3_cleaned = 0
            if self.s3_manager:
                # S3 lifecycle handles automatic cleanup
                s3_cleaned = 'managed_by_lifecycle'
            
            return {
                'status': 'success',
                'local_files_cleaned': local_cleaned,
                's3_cleanup': s3_cleaned,
                'cleanup_days': cleanup_days
            }
            
        except Exception as e:
            logger.error(f"Storage cleanup failed: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def close(self):
        """Close storage managers"""
        try:
            self.local_manager.close()
            
            # Stop sync service
            if self.sync_task:
                self.sync_task.cancel()
            
            # Shutdown executor
            self.executor.shutdown(wait=True)
            
            logger.info("Closed desktop storage manager")
            
        except Exception as e:
            logger.error(f"Error closing storage manager: {e}")


# Factory functions
def create_desktop_storage_manager(
    local_path: str = None,
    max_local_size_gb: float = 50.0,
    s3_bucket: str = None,
    s3_region: str = 'us-west-2',
    auto_sync: bool = True,
    sync_interval_minutes: int = 30
) -> DesktopStorageManager:
    """
    Create desktop storage manager with default configurations
    
    Args:
        local_path: Path for local storage
        max_local_size_gb: Maximum local storage size in GB
        s3_bucket: S3 bucket name for backup
        s3_region: S3 region
        auto_sync: Enable automatic sync to cloud
        sync_interval_minutes: Sync interval in minutes
    
    Returns:
        Configured DesktopStorageManager
    """
    # Create local storage config
    local_config = LocalStorageConfig(
        base_path=local_path,
        max_local_size_gb=max_local_size_gb
    )
    
    # Create S3 config if bucket provided
    s3_config = None
    if s3_bucket:
        s3_config = S3StorageConfig(
            bucket_name=s3_bucket,
            region=s3_region
        )
    
    # Create and return storage manager
    return DesktopStorageManager(
        local_config=local_config,
        s3_config=s3_config,
        auto_sync=auto_sync,
        sync_interval_minutes=sync_interval_minutes
    )