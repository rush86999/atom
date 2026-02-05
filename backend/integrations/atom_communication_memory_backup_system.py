"""
ATOM Communication Memory - Backup and Disaster Recovery
Comprehensive backup and recovery system for LanceDB database
"""

import asyncio
from datetime import datetime, timedelta
import gzip
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict, List, Optional
import boto3
import botocore

from integrations.atom_communication_ingestion_pipeline import memory_manager

logger = logging.getLogger(__name__)

class AtomCommunicationMemoryBackupSystem:
    """Backup and disaster recovery system for ATOM communication memory"""
    
    def __init__(self):
        self.backup_config = {
            'backup_interval_hours': 6,  # Backup every 6 hours
            'retention_days': 30,  # Keep backups for 30 days
            'compression_enabled': True,
            's3_backup_enabled': True,
            'local_backup_path': '/backup/atom/memory',
            's3_bucket': 'atom-communication-memory-backups',
            's3_region': 'us-east-1'
        }
        
        self.backup_status = {
            'last_backup': None,
            'last_s3_backup': None,
            'backup_in_progress': False,
            'total_backups': 0,
            'backup_errors': []
        }
        
        # Ensure backup directory exists
        Path(self.backup_config['local_backup_path']).mkdir(parents=True, exist_ok=True)
    
    async def start_backup_system(self):
        """Start automated backup system"""
        logger.info("Starting ATOM Communication Memory Backup System")
        
        while True:
            try:
                # Check if backup is needed
                if self._should_create_backup():
                    await self._create_backup()
                
                # Cleanup old backups
                await self._cleanup_old_backups()
                
                # Wait for next backup interval
                await asyncio.sleep(self.backup_config['backup_interval_hours'] * 3600)
                
            except Exception as e:
                logger.error(f"Error in backup system loop: {str(e)}")
                await asyncio.sleep(3600)  # Wait longer on error
    
    def _should_create_backup(self) -> bool:
        """Check if backup should be created"""
        if self.backup_status['backup_in_progress']:
            return False
        
        if not self.backup_status['last_backup']:
            return True
        
        # Check if enough time has passed since last backup
        time_since_last = datetime.now() - self.backup_status['last_backup']
        return time_since_last.total_seconds() >= self.backup_config['backup_interval_hours'] * 3600
    
    async def _create_backup(self):
        """Create a complete backup of the communication memory"""
        try:
            self.backup_status['backup_in_progress'] = True
            backup_start_time = datetime.now()
            
            logger.info(f"Starting backup at {backup_start_time}")
            
            # Create backup directory
            backup_dir_name = f"backup_{backup_start_time.strftime('%Y%m%d_%H%M%S')}"
            backup_path = Path(self.backup_config['local_backup_path']) / backup_dir_name
            backup_path.mkdir(parents=True, exist_ok=True)
            
            # Backup LanceDB database
            if memory_manager.db_path and memory_manager.db_path.exists():
                await self._backup_database(backup_path)
            
            # Backup configuration files
            await self._backup_configuration(backup_path)
            
            # Create backup metadata
            await self._create_backup_metadata(backup_path, backup_start_time)
            
            # Compress backup if enabled
            if self.backup_config['compression_enabled']:
                compressed_path = await self._compress_backup(backup_path)
                # Remove uncompressed directory
                shutil.rmtree(backup_path)
                backup_path = compressed_path
            
            # Upload to S3 if enabled
            if self.backup_config['s3_backup_enabled']:
                await self._upload_to_s3(backup_path)
            
            # Update backup status
            self.backup_status['last_backup'] = datetime.now()
            self.backup_status['total_backups'] += 1
            
            backup_duration = datetime.now() - backup_start_time
            logger.info(f"Backup completed successfully in {backup_duration}")
            
        except Exception as e:
            logger.error(f"Error creating backup: {str(e)}")
            self.backup_status['backup_errors'].append({
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            })
        finally:
            self.backup_status['backup_in_progress'] = False
    
    async def _backup_database(self, backup_path: Path):
        """Backup LanceDB database"""
        try:
            if memory_manager.db_path and memory_manager.db_path.exists():
                db_backup_path = backup_path / 'database'
                shutil.copytree(memory_manager.db_path, db_backup_path)
                logger.info(f"Database backed up to {db_backup_path}")
        except Exception as e:
            logger.error(f"Error backing up database: {str(e)}")
            raise
    
    async def _backup_configuration(self, backup_path: Path):
        """Backup configuration files"""
        try:
            config_backup_path = backup_path / 'configuration'
            config_backup_path.mkdir(exist_ok=True)
            
            # Backup ingestion pipeline configuration
            from integrations.atom_communication_ingestion_pipeline import ingestion_pipeline
            config_data = {
                'ingestion_configs': ingestion_pipeline.ingestion_configs,
                'active_streams': list(ingestion_pipeline.active_streams.keys()),
                'timestamp': datetime.now().isoformat()
            }
            
            with open(config_backup_path / 'ingestion_config.json', 'w') as f:
                json.dump(config_data, f, indent=2, default=str)
            
            logger.info(f"Configuration backed up to {config_backup_path}")
            
        except Exception as e:
            logger.error(f"Error backing up configuration: {str(e)}")
    
    async def _create_backup_metadata(self, backup_path: Path, backup_start_time: datetime):
        """Create backup metadata file"""
        try:
            metadata = {
                'backup_info': {
                    'backup_id': backup_path.name,
                    'created_at': backup_start_time.isoformat(),
                    'backup_type': 'full',
                    'compression_enabled': self.backup_config['compression_enabled']
                },
                'database_info': {
                    'path': str(memory_manager.db_path),
                    'tables': memory_manager.db.table_names() if memory_manager.db else []
                },
                'system_info': {
                    'hostname': os.uname().nodename,
                    'platform': os.uname().sysname,
                    'architecture': os.uname().machine
                },
                'config_info': self.backup_config
            }
            
            with open(backup_path / 'backup_metadata.json', 'w') as f:
                json.dump(metadata, f, indent=2, default=str)
            
        except Exception as e:
            logger.error(f"Error creating backup metadata: {str(e)}")
    
    async def _compress_backup(self, backup_path: Path) -> Path:
        """Compress backup directory"""
        try:
            compressed_path = Path(f"{backup_path}.tar.gz")
            
            # Create tar.gz archive
            with open(compressed_path, 'wb') as f_out:
                with gzip.GzipFile(fileobj=f_out, mode='wb') as gz_out:
                    with tarfile.open(fileobj=gz_out, mode='w|') as tar:
                        tar.add(backup_path, arcname=backup_path.name)
            
            logger.info(f"Backup compressed to {compressed_path}")
            return compressed_path
            
        except Exception as e:
            logger.error(f"Error compressing backup: {str(e)}")
            raise
    
    async def _upload_to_s3(self, backup_path: Path):
        """Upload backup to AWS S3"""
        try:
            import boto3
            from botocore.exceptions import ClientError
            
            s3_client = boto3.client('s3', region_name=self.backup_config['s3_region'])
            
            # Upload backup file
            s3_key = f"backups/{backup_path.name}"
            
            s3_client.upload_file(
                str(backup_path),
                self.backup_config['s3_bucket'],
                s3_key,
                ExtraArgs={
                    'ServerSideEncryption': 'AES256',
                    'StorageClass': 'STANDARD_IA'  # Infrequent Access for cost savings
                }
            )
            
            self.backup_status['last_s3_backup'] = datetime.now()
            logger.info(f"Backup uploaded to S3: s3://{self.backup_config['s3_bucket']}/{s3_key}")
            
        except Exception as e:
            logger.error(f"Error uploading to S3: {str(e)}")
            # Don't raise exception - backup is still available locally
    
    async def _cleanup_old_backups(self):
        """Clean up old backup files based on retention policy"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.backup_config['retention_days'])
            
            # Cleanup local backups
            backup_path = Path(self.backup_config['local_backup_path'])
            for backup_dir in backup_path.iterdir():
                if backup_dir.is_dir() or backup_dir.suffix in ['.tar', '.gz']:
                    # Get modification time
                    mod_time = datetime.fromtimestamp(backup_dir.stat().st_mtime)
                    
                    if mod_time < cutoff_date:
                        if backup_dir.is_dir():
                            shutil.rmtree(backup_dir)
                        else:
                            backup_dir.unlink()
                        
                        logger.info(f"Deleted old backup: {backup_dir.name}")
            
            # Cleanup S3 backups (if S3 is enabled)
            if self.backup_config['s3_backup_enabled']:
                await self._cleanup_s3_backups(cutoff_date)
                
        except Exception as e:
            logger.error(f"Error cleaning up old backups: {str(e)}")
    
    async def _cleanup_s3_backups(self, cutoff_date: datetime):
        """Clean up old S3 backups"""
        try:
            import boto3
            
            s3_client = boto3.client('s3', region_name=self.backup_config['s3_region'])
            
            # List objects in backups folder
            response = s3_client.list_objects_v2(
                Bucket=self.backup_config['s3_bucket'],
                Prefix='backups/'
            )
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    if obj['LastModified'].replace(tzinfo=None) < cutoff_date:
                        s3_client.delete_object(
                            Bucket=self.backup_config['s3_bucket'],
                            Key=obj['Key']
                        )
                        logger.info(f"Deleted old S3 backup: {obj['Key']}")
                        
        except Exception as e:
            logger.error(f"Error cleaning up S3 backups: {str(e)}")
    
    async def restore_from_backup(self, backup_id: str, restore_location: Optional[str] = None) -> bool:
        """Restore database from backup"""
        try:
            backup_path = Path(self.backup_config['local_backup_path']) / backup_id
            
            # If backup doesn't exist locally, try to download from S3
            if not backup_path.exists():
                await self._download_from_s3(backup_id, backup_path)
            
            # Extract if compressed
            if backup_path.suffix == '.gz':
                extract_path = backup_path.with_suffix('')
                await self._extract_backup(backup_path, extract_path)
                backup_path = extract_path
            
            # Restore database
            if restore_location:
                restore_path = Path(restore_location)
                restore_path.mkdir(parents=True, exist_ok=True)
            else:
                restore_path = memory_manager.db_path
                restore_path.mkdir(parents=True, exist_ok=True)
            
            db_backup_path = backup_path / 'database'
            if db_backup_path.exists():
                # Remove existing database
                if restore_path.exists():
                    shutil.rmtree(restore_path)
                
                # Restore database
                shutil.copytree(db_backup_path, restore_path)
                
                logger.info(f"Database restored from backup to {restore_path}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error restoring from backup: {str(e)}")
            return False
    
    async def _download_from_s3(self, backup_id: str, local_path: Path):
        """Download backup from S3"""
        try:
            import boto3
            
            s3_client = boto3.client('s3', region_name=self.backup_config['s3_region'])
            
            # Try different file extensions
            for ext in ['', '.tar.gz']:
                s3_key = f"backups/{backup_id}{ext}"
                
                try:
                    s3_client.download_file(
                        self.backup_config['s3_bucket'],
                        s3_key,
                        str(local_path)
                    )
                    logger.info(f"Downloaded backup from S3: {s3_key}")
                    return
                except s3_client.exceptions.NoSuchKey:
                    continue
            
            raise FileNotFoundError(f"Backup {backup_id} not found in S3")
            
        except Exception as e:
            logger.error(f"Error downloading from S3: {str(e)}")
            raise
    
    async def _extract_backup(self, backup_path: Path, extract_path: Path):
        """Extract compressed backup"""
        try:
            import gzip
            import tarfile
            
            with open(backup_path, 'rb') as f:
                with gzip.GzipFile(fileobj=f) as gz:
                    with tarfile.open(fileobj=gz) as tar:
                        tar.extractall(extract_path)
            
            logger.info(f"Backup extracted to {extract_path}")
            
        except Exception as e:
            logger.error(f"Error extracting backup: {str(e)}")
            raise
    
    def get_backup_status(self) -> Dict[str, Any]:
        """Get current backup system status"""
        try:
            # Get list of local backups
            backup_path = Path(self.backup_config['local_backup_path'])
            local_backups = []
            
            for item in backup_path.iterdir():
                if item.exists():
                    stat = item.stat()
                    local_backups.append({
                        'id': item.name,
                        'size': stat.st_size,
                        'created_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        'type': 'directory' if item.is_dir() else 'file'
                    })
            
            return {
                'backup_status': self.backup_status,
                'local_backups': local_backups,
                'backup_config': self.backup_config,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting backup status: {str(e)}")
            return {"error": str(e)}
    
    async def create_manual_backup(self, backup_name: Optional[str] = None) -> str:
        """Create a manual backup with optional name"""
        try:
            if not backup_name:
                backup_name = f"manual_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            backup_start_time = datetime.now()
            backup_path = Path(self.backup_config['local_backup_path']) / backup_name
            backup_path.mkdir(parents=True, exist_ok=True)
            
            # Create backup
            await self._backup_database(backup_path)
            await self._backup_configuration(backup_path)
            await self._create_backup_metadata(backup_path, backup_start_time)
            
            # Compress if enabled
            if self.backup_config['compression_enabled']:
                backup_path = await self._compress_backup(backup_path)
            
            # Upload to S3 if enabled
            if self.backup_config['s3_backup_enabled']:
                await self._upload_to_s3(backup_path)
            
            logger.info(f"Manual backup created: {backup_name}")
            return backup_name
            
        except Exception as e:
            logger.error(f"Error creating manual backup: {str(e)}")
            raise

# Create global backup system instance
atom_backup_system = AtomCommunicationMemoryBackupSystem()

# Export for use
__all__ = [
    'AtomCommunicationMemoryBackupSystem',
    'atom_backup_system'
]
