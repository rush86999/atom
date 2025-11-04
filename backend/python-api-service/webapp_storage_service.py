"""
Web App Storage Service - S3 Only for LanceDB Memory
Configuration for web deployment with cloud-native storage
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Import S3 backend
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

# Import LanceDB
try:
    import lancedb
    import pyarrow as pa
    from lancedb import LanceDB
    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False

logger = logging.getLogger(__name__)


class S3LanceDBConfig:
    """Configuration for S3-based LanceDB storage"""
    
    def __init__(
        self,
        bucket_name: str,
        region: str = 'us-west-2',
        lancedb_prefix: str = 'lancedb/',
        access_key_id: str = None,
        secret_access_key: str = None,
        session_token: str = None,
        endpoint_url: str = None,
        storage_class: str = 'STANDARD_IA',  # Infrequent access for data
        cache_size_mb: int = 1000,  # Local cache for LanceDB
        auto_compact: bool = True,
        compact_interval_hours: int = 24
    ):
        self.bucket_name = bucket_name
        self.region = region
        self.lancedb_prefix = lancedb_prefix.rstrip('/') + '/'
        self.access_key_id = access_key_id or os.getenv('AWS_ACCESS_KEY_ID')
        self.secret_access_key = secret_access_key or os.getenv('AWS_SECRET_ACCESS_KEY')
        self.session_token = session_token or os.getenv('AWS_SESSION_TOKEN')
        self.endpoint_url = endpoint_url
        self.storage_class = storage_class
        self.cache_size_mb = cache_size_mb
        self.auto_compact = auto_compact
        self.compact_interval_hours = compact_interval_hours
    
    def validate(self) -> bool:
        """Validate S3 configuration"""
        return (
            self.bucket_name and
            self.access_key_id and
            self.secret_access_key
        )


class S3LanceDBManager:
    """LanceDB manager with S3 backend for web deployment"""
    
    def __init__(self, config: S3LanceDBConfig):
        self.config = config
        self.s3_client = None
        self.s3_resource = None
        self.lancedb_local_cache = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Initialize S3 and local cache
        self._initialize_s3()
        self._initialize_local_cache()
        
        logger.info(f"Initialized S3 LanceDB manager for bucket: {config.bucket_name}")
    
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
            
            logger.info("S3 client initialized successfully")
            
        except (ClientError, NoCredentialsError) as e:
            logger.error(f"Failed to initialize S3: {e}")
            raise
    
    def _initialize_local_cache(self):
        """Initialize local cache for LanceDB"""
        try:
            # Create cache directory
            import tempfile
            cache_dir = Path(tempfile.gettempdir()) / 'atom_lancedb_cache'
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize LanceDB with S3 URI
            if LANCEDB_AVAILABLE:
                s3_uri = f"s3://{self.config.bucket_name}/{self.config.lancedb_prefix}"
                self.lancedb_local_cache = LanceDB.create(cache_dir, mode="overwrite")
                
                logger.info(f"LanceDB cache initialized at: {cache_dir}")
            else:
                logger.warning("LanceDB not available")
            
        except Exception as e:
            logger.error(f"Failed to initialize LanceDB cache: {e}")
    
    async def create_table(
        self,
        table_name: str,
        schema: pa.Schema = None,
        data: pa.Table = None
    ) -> bool:
        """Create LanceDB table in S3"""
        try:
            if not self.lancedb_local_cache:
                raise RuntimeError("LanceDB not initialized")
            
            # Create table in local cache first
            if schema:
                table = self.lancedb_local_cache.create_table(
                    table_name,
                    schema=schema,
                    mode="overwrite"
                )
            elif data:
                table = self.lancedb_local_cache.create_table(
                    table_name,
                    data=data,
                    mode="overwrite"
                )
            else:
                raise ValueError("Either schema or data must be provided")
            
            # Sync table to S3
            await self._sync_table_to_s3(table_name)
            
            logger.info(f"Created LanceDB table: {table_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create table {table_name}: {e}")
            return False
    
    async def get_table(self, table_name: str) -> Optional[Any]:
        """Get LanceDB table (load from cache if available)"""
        try:
            if not self.lancedb_local_cache:
                return None
            
            # Try to open from local cache
            try:
                table = self.lancedb_local_cache.open_table(table_name)
                return table
            except Exception:
                # Table not in cache, download from S3
                success = await self._download_table_from_s3(table_name)
                if success:
                    table = self.lancedb_local_cache.open_table(table_name)
                    return table
                else:
                    return None
            
        except Exception as e:
            logger.error(f"Failed to get table {table_name}: {e}")
            return None
    
    async def add_to_table(
        self,
        table_name: str,
        data: Union[pa.Table, List[Dict[str, Any]]]
    ) -> bool:
        """Add data to LanceDB table"""
        try:
            table = await self.get_table(table_name)
            if not table:
                logger.error(f"Table {table_name} not found")
                return False
            
            # Add data to table
            table.add(data)
            
            # Sync to S3
            await self._sync_table_to_s3(table_name)
            
            logger.info(f"Added data to table {table_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add to table {table_name}: {e}")
            return False
    
    async def search_table(
        self,
        table_name: str,
        query_vector: List[float] = None,
        limit: int = 10,
        filter_expression: str = None,
        prefilter: bool = True
    ) -> List[Dict[str, Any]]:
        """Search LanceDB table"""
        try:
            table = await self.get_table(table_name)
            if not table:
                return []
            
            # Perform search
            if query_vector:
                results = table.search(query_vector).limit(limit).to_pandas()
            else:
                results = table.to_pandas()
            
            # Apply filter if provided
            if filter_expression:
                # This would need proper pandas query implementation
                pass
            
            return results.to_dict('records')
            
        except Exception as e:
            logger.error(f"Failed to search table {table_name}: {e}")
            return []
    
    async def _sync_table_to_s3(self, table_name: str):
        """Sync LanceDB table to S3"""
        try:
            # Get table path in local cache
            table_path = Path(self.lancedb_local_cache.uri) / f"{table_name}.lance"
            
            if not table_path.exists():
                logger.warning(f"Table path not found: {table_path}")
                return
            
            # Create S3 key for table
            s3_key = f"{self.config.lancedb_prefix}{table_name}.lance"
            
            # Upload table files to S3
            loop = asyncio.get_event_loop()
            
            def upload_table():
                return self._upload_directory_to_s3(
                    table_path,
                    self.config.bucket_name,
                    s3_key
                )
            
            await loop.run_in_executor(self.executor, upload_table)
            
            logger.debug(f"Synced table {table_name} to S3")
            
        except Exception as e:
            logger.error(f"Failed to sync table {table_name} to S3: {e}")
    
    async def _download_table_from_s3(self, table_name: str) -> bool:
        """Download LanceDB table from S3"""
        try:
            # Get S3 key for table
            s3_key = f"{self.config.lancedb_prefix}{table_name}.lance"
            
            # Download table files from S3
            loop = asyncio.get_event_loop()
            
            def download_table():
                return self._download_directory_from_s3(
                    self.config.bucket_name,
                    s3_key,
                    Path(self.lancedb_local_cache.uri)
                )
            
            success = await loop.run_in_executor(self.executor, download_table)
            
            if success:
                logger.info(f"Downloaded table {table_name} from S3")
            else:
                logger.warning(f"Table {table_name} not found in S3")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to download table {table_name} from S3: {e}")
            return False
    
    def _upload_directory_to_s3(
        self,
        local_dir: Path,
        bucket_name: str,
        s3_prefix: str
    ) -> bool:
        """Upload directory to S3"""
        try:
            for file_path in local_dir.rglob('*'):
                if file_path.is_file():
                    # Calculate relative path
                    relative_path = file_path.relative_to(local_dir)
                    s3_key = f"{s3_prefix}/{relative_path}"
                    
                    # Upload file
                    self.s3_client.upload_file(
                        str(file_path),
                        bucket_name,
                        s3_key,
                        ExtraArgs={'StorageClass': self.config.storage_class}
                    )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to upload directory to S3: {e}")
            return False
    
    def _download_directory_from_s3(
        self,
        bucket_name: str,
        s3_prefix: str,
        local_dir: Path
    ) -> bool:
        """Download directory from S3"""
        try:
            # Check if prefix exists
            response = self.s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=s3_prefix,
                MaxKeys=1
            )
            
            if 'Contents' not in response:
                return False  # Prefix doesn't exist
            
            # Download all files
            paginator = self.s3_client.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(
                Bucket=bucket_name,
                Prefix=s3_prefix
            ):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        s3_key = obj['Key']
                        
                        # Calculate local path
                        relative_path = s3_key[len(s3_prefix):].lstrip('/')
                        local_path = local_dir / relative_path
                        
                        # Create directory if needed
                        local_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Download file
                        self.s3_client.download_file(bucket_name, s3_key, str(local_path))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to download directory from S3: {e}")
            return False
    
    async def compact_table(self, table_name: str):
        """Compact LanceDB table to optimize storage"""
        try:
            table = await self.get_table(table_name)
            if not table:
                return False
            
            # Compact table
            table.compact_files()
            
            # Sync to S3
            await self._sync_table_to_s3(table_name)
            
            logger.info(f"Compacted table {table_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to compact table {table_name}: {e}")
            return False
    
    async def delete_table(self, table_name: str) -> bool:
        """Delete LanceDB table from both local cache and S3"""
        try:
            # Delete from local cache
            try:
                if self.lancedb_local_cache:
                    self.lancedb_local_cache.drop_table(table_name)
            except Exception:
                pass  # Table might not exist in cache
            
            # Delete from S3
            s3_key = f"{self.config.lancedb_prefix}{table_name}.lance"
            
            paginator = self.s3_client.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(
                Bucket=self.config.bucket_name,
                Prefix=s3_key
            ):
                if 'Contents' in page:
                    delete_keys = [{'Key': obj['Key']} for obj in page['Contents']]
                    self.s3_client.delete_objects(
                        Bucket=self.config.bucket_name,
                        Delete={'Objects': delete_keys}
                    )
            
            logger.info(f"Deleted table {table_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete table {table_name}: {e}")
            return False
    
    def list_tables(self) -> List[str]:
        """List all LanceDB tables in S3"""
        try:
            tables = []
            
            paginator = self.s3_client.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(
                Bucket=self.config.bucket_name,
                Prefix=self.config.lancedb_prefix,
                Delimiter='/'
            ):
                if 'CommonPrefixes' in page:
                    for prefix in page['CommonPrefixes']:
                        # Extract table name from prefix
                        full_prefix = prefix['Prefix']
                        if full_prefix.startswith(self.config.lancedb_prefix):
                            table_name = full_prefix[len(self.config.lancedb_prefix):].rstrip('/')
                            if table_name and table_name not in tables:
                                tables.append(table_name)
            
            return tables
            
        except Exception as e:
            logger.error(f"Failed to list tables: {e}")
            return []
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get S3 storage statistics for LanceDB"""
        try:
            total_size = 0
            object_count = 0
            table_stats = {}
            
            paginator = self.s3_client.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(
                Bucket=self.config.bucket_name,
                Prefix=self.config.lancedb_prefix
            ):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        size = obj['Size']
                        key = obj['Key']
                        
                        total_size += size
                        object_count += 1
                        
                        # Extract table name
                        if key.startswith(self.config.lancedb_prefix):
                            suffix = key[len(self.config.lancedb_prefix):]
                            if '/' in suffix:
                                table_name = suffix.split('/')[0]
                            else:
                                table_name = suffix.replace('.lance', '')
                            
                            if table_name not in table_stats:
                                table_stats[table_name] = {
                                    'size_bytes': 0,
                                    'object_count': 0
                                }
                            
                            table_stats[table_name]['size_bytes'] += size
                            table_stats[table_name]['object_count'] += 1
            
            return {
                'total_size_bytes': total_size,
                'total_size_gb': total_size / (1024 * 1024 * 1024),
                'total_objects': object_count,
                'table_count': len(table_stats),
                'bucket_name': self.config.bucket_name,
                'lancedb_prefix': self.config.lancedb_prefix,
                'tables': table_stats
            }
            
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {}
    
    def close(self):
        """Close S3 connections"""
        try:
            if self.lancedb_local_cache:
                self.lancedb_local_cache.close()
            
            self.executor.shutdown(wait=True)
            
            logger.info("Closed S3 LanceDB manager")
            
        except Exception as e:
            logger.error(f"Error closing S3 LanceDB manager: {e}")


class WebAppStorageManager:
    """Web app storage manager - S3 only for LanceDB memory"""
    
    def __init__(
        self,
        s3_lancedb_config: S3LanceDBConfig,
        auto_compact: bool = True,
        compact_interval_hours: int = 24
    ):
        self.s3_lancedb_manager = S3LanceDBManager(s3_lancedb_config)
        self.auto_compact = auto_compact
        self.compact_interval_seconds = compact_interval_hours * 3600
        self.compact_task: Optional[asyncio.Task] = None
        
        logger.info("Initialized web app storage manager")
    
    async def start_maintenance_service(self):
        """Start maintenance service (compaction, optimization)"""
        if self.auto_compact:
            self.compact_task = asyncio.create_task(self._maintenance_loop())
            logger.info("Started maintenance service")
    
    async def stop_maintenance_service(self):
        """Stop maintenance service"""
        if self.compact_task:
            self.compact_task.cancel()
            try:
                await self.compact_task
            except asyncio.CancelledError:
                pass
            self.compact_task = None
        
        logger.info("Stopped maintenance service")
    
    async def _maintenance_loop(self):
        """Main maintenance loop"""
        while True:
            try:
                # Compact all tables
                tables = self.s3_lancedb_manager.list_tables()
                
                for table_name in tables:
                    await self.s3_lancedb_manager.compact_table(table_name)
                
                # Wait for next maintenance cycle
                await asyncio.sleep(self.compact_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in maintenance loop: {e}")
                await asyncio.sleep(300)  # Wait before retry
    
    async def create_memory_table(
        self,
        table_name: str,
        schema: pa.Schema = None,
        data: pa.Table = None
    ) -> bool:
        """Create memory table in S3"""
        return await self.s3_lancedb_manager.create_table(
            table_name, schema, data
        )
    
    async def store_memory_data(
        self,
        table_name: str,
        data: Union[pa.Table, List[Dict[str, Any]]]
    ) -> bool:
        """Store memory data to S3"""
        return await self.s3_lancedb_manager.add_to_table(
            table_name, data
        )
    
    async def search_memory(
        self,
        table_name: str,
        query_vector: List[float] = None,
        limit: int = 10,
        filter_expression: str = None
    ) -> List[Dict[str, Any]]:
        """Search memory in S3"""
        return await self.s3_lancedb_manager.search_table(
            table_name, query_vector, limit, filter_expression
        )
    
    async def get_memory_table(self, table_name: str) -> Optional[Any]:
        """Get memory table from S3"""
        return await self.s3_lancedb_manager.get_table(table_name)
    
    async def delete_memory_table(self, table_name: str) -> bool:
        """Delete memory table from S3"""
        return await self.s3_lancedb_manager.delete_table(table_name)
    
    def list_memory_tables(self) -> List[str]:
        """List all memory tables in S3"""
        return self.s3_lancedb_manager.list_tables()
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get comprehensive storage statistics"""
        stats = {
            'lancedb_storage': self.s3_lancedb_manager.get_storage_stats(),
            'maintenance_status': {
                'auto_compact_enabled': self.auto_compact,
                'compact_interval_hours': self.compact_interval_seconds / 3600,
                'maintenance_running': self.compact_task is not None
            }
        }
        
        return stats
    
    def close(self):
        """Close storage manager"""
        try:
            self.s3_lancedb_manager.close()
            
            # Stop maintenance service
            if self.compact_task:
                self.compact_task.cancel()
                try:
                    asyncio.run(self.compact_task)
                except asyncio.CancelledError:
                    pass
                self.compact_task = None
            
            logger.info("Closed web app storage manager")
            
        except Exception as e:
            logger.error(f"Error closing storage manager: {e}")


# Factory functions
def create_web_app_storage_manager(
    s3_bucket: str,
    s3_region: str = 'us-west-2',
    lancedb_prefix: str = 'lancedb/',
    access_key_id: str = None,
    secret_access_key: str = None,
    auto_compact: bool = True,
    compact_interval_hours: int = 24
) -> WebAppStorageManager:
    """
    Create web app storage manager with S3-only configuration for LanceDB
    
    Args:
        s3_bucket: S3 bucket name
        s3_region: S3 region
        lancedb_prefix: Prefix for LanceDB files
        access_key_id: AWS access key ID (optional, uses env var)
        secret_access_key: AWS secret access key (optional, uses env var)
        auto_compact: Enable automatic table compaction
        compact_interval_hours: Interval between compactions in hours
    
    Returns:
        Configured WebAppStorageManager
    """
    s3_config = S3LanceDBConfig(
        bucket_name=s3_bucket,
        region=s3_region,
        lancedb_prefix=lancedb_prefix,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        auto_compact=auto_compact,
        compact_interval_hours=compact_interval_hours
    )
    
    return WebAppStorageManager(
        s3_lancedb_config=s3_config,
        auto_compact=auto_compact,
        compact_interval_hours=compact_interval_hours
    )