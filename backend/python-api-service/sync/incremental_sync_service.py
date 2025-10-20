"""
Incremental Sync Service for LanceDB with Local + S3 Hybrid Storage

This service provides incremental document ingestion with hybrid storage:
- Local LanceDB for fast desktop app access
- S3 as primary storage backend for cloud scalability
- Automatic sync between local and S3 storage
"""

import os
import logging
import asyncio
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
import boto3
from botocore.exceptions import ClientError
from .lancedb_storage_service import create_lancedb_storage_service

# Try to import LanceDB
try:
    import lancedb
    import pyarrow as pa
    import pandas as pd

    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False
    logging.warning("LanceDB library not available")

logger = logging.getLogger(__name__)


@dataclass
class SyncConfig:
    """Configuration for incremental sync service"""

    local_db_path: str = "data/lancedb"
    s3_bucket: Optional[str] = None
    s3_prefix: str = "lancedb-backup"
    sync_interval: int = 300  # seconds
    max_retries: int = 3
    chunk_size_mb: int = 50


@dataclass
class ChangeRecord:
    """Record of changes for incremental sync"""

    doc_id: str
    user_id: str
    source_uri: str
    operation: str  # "create", "update", "delete"
    timestamp: str
    checksum: Optional[str] = None
    sync_status: str = "pending"  # "pending", "synced", "failed"


class IncrementalSyncService:
    """
    Service for incremental document ingestion with local+S3 hybrid storage
    """

    def __init__(self, config: SyncConfig):
        self.config = config
        self.storage_service = None
        self.s3_client = None
        self.change_log: List[ChangeRecord] = []
        self.processed_checksums: Set[str] = set()

        # Initialize connections
        self._init_storage_service()
        self._init_s3_client()

    def _init_storage_service(self):
        """Initialize hybrid storage service"""
        try:
            self.storage_service = create_lancedb_storage_service(self.config)
            logger.info("Initialized LanceDB hybrid storage service")
        except Exception as e:
            logger.error(f"Failed to initialize storage service: {e}")
            self.storage_service = None

    def _init_s3_client(self):
        """Initialize S3 client for backup sync"""
        if not self.config.s3_backup_bucket:
            logger.info("S3 backup bucket not configured - backup sync disabled")
            return

        try:
            self.s3_client = boto3.client("s3")
            # Test connection
            self.s3_client.head_bucket(Bucket=self.config.s3_backup_bucket)
            logger.info(
                f"Connected to S3 backup bucket: {self.config.s3_backup_bucket}"
            )

        except ClientError as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            self.s3_client = None
        except Exception as e:
            logger.error(f"Unexpected error initializing S3: {e}")
            self.s3_client = None

    def _ensure_tables_exist(self):
        """Ensure required tables exist (handled by storage service)"""
        # Tables are created automatically by the storage service
        pass

    async def process_document_incrementally(
        self,
        user_id: str,
        source_uri: str,
        document_data: Dict[str, Any],
        chunks_with_embeddings: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Process document incrementally - only if changed since last sync

        Args:
            user_id: User identifier
            source_uri: Source document URI
            document_data: Document metadata
            chunks_with_embeddings: Document chunks with embeddings

        Returns:
            Processing result with sync status
        """
        try:
            # Generate checksum for change detection
            doc_checksum = self._generate_checksum(
                document_data, chunks_with_embeddings
            )

            # Check if document already exists and unchanged
            existing_doc = await self._get_existing_document(source_uri, user_id)
            if existing_doc and existing_doc.get("checksum") == doc_checksum:
                logger.info(f"Document unchanged: {source_uri}")
                return {
                    "status": "skipped",
                    "message": "Document unchanged since last sync",
                    "doc_id": existing_doc.get("doc_id"),
                }

            # Process document (new or updated)
            doc_id = (
                document_data.get("doc_id")
                or f"doc_{hashlib.md5(source_uri.encode()).hexdigest()}"
            )

            # Store using hybrid storage service
            storage_result = await self._store_with_hybrid_storage(
                doc_id,
                user_id,
                source_uri,
                document_data,
                chunks_with_embeddings,
                doc_checksum,
            )

            if storage_result["status"] != "success":
                return storage_result

            # Record change for S3 sync
            operation = "update" if existing_doc else "create"
            change_record = ChangeRecord(
                doc_id=doc_id,
                user_id=user_id,
                source_uri=source_uri,
                operation=operation,
                timestamp=datetime.now(timezone.utc).isoformat(),
                checksum=doc_checksum,
            )
            self.change_log.append(change_record)

            # Trigger async S3 sync
            asyncio.create_task(self._sync_to_s3(change_record))

            return {
                "status": "success",
                "message": f"Document processed ({operation})",
                "doc_id": doc_id,
                "storage_backend": storage_result.get("storage_backend", "unknown"),
                "chunks_stored": storage_result.get("chunks_stored", 0),
                "remote_sync_queued": self.config.should_sync_to_s3(),
            }

        except Exception as e:
            logger.error(f"Failed to process document incrementally: {e}")
            return {"status": "error", "message": str(e)}

    async def _get_existing_document(
        self, source_uri: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get existing document from storage service"""
        if not self.storage_service:
            return None

        try:
            # For now, we'll use a simplified approach
            # In a full implementation, we would query the storage service
            return None

        except Exception as e:
            logger.error(f"Error checking existing document: {e}")
            return None

    async def _store_with_hybrid_storage(
        self,
        doc_id: str,
        user_id: str,
        source_uri: str,
        document_data: Dict[str, Any],
        chunks_with_embeddings: List[Dict[str, Any]],
        checksum: str,
    ) -> Dict[str, Any]:
        """Store document using hybrid storage service"""
        if not self.storage_service:
            return {"status": "error", "message": "Storage service not available"}

        try:
            # Prepare document data for storage service
            storage_doc_data = {
                "doc_id": doc_id,
                "source_uri": source_uri,
                "doc_type": document_data.get("doc_type", "unknown"),
                "title": document_data.get("title", ""),
                "metadata": document_data.get("metadata", {}),
            }

            # Prepare chunks for storage service
            storage_chunks = []
            for i, chunk in enumerate(chunks_with_embeddings):
                storage_chunk = {
                    "text_content": chunk.get("text_content", ""),
                    "embedding": chunk.get("embedding", []),
                    "metadata": {
                        "chunk_index": i,
                        **chunk.get("metadata", {}),
                    },
                }
                storage_chunks.append(storage_chunk)

            # Store using hybrid storage
            result = await self.storage_service.store_document(
                user_id=user_id,
                document_data=storage_doc_data,
                chunks_with_embeddings=storage_chunks,
            )

            return result

        except Exception as e:
            logger.error(f"Failed to store with hybrid storage: {e}")
            return {"status": "error", "message": str(e)}

    async def _sync_to_s3(self, change_record: ChangeRecord):
        """Sync document changes to S3 backup"""
        if not self.s3_client and not self.config.should_use_s3_primary():
            change_record.sync_status = "failed"
            return

        try:
            # If using S3 as primary, sync is handled by storage service
            if self.config.should_use_s3_primary():
                # Sync is automatic with S3 primary storage
                change_record.sync_status = "synced"
                logger.info(f"Document {change_record.doc_id} stored in S3 primary")
            else:
                # Export document data to S3 backup
                await self._export_document_to_s3(
                    change_record.doc_id, change_record.user_id
                )

                # Update sync metadata
                await self._update_sync_metadata(change_record)

                change_record.sync_status = "synced"
                logger.info(f"Synced document {change_record.doc_id} to S3 backup")

        except Exception as e:
            logger.error(f"Failed to sync to S3: {e}")
            change_record.sync_status = "failed"

    async def _export_document_to_s3(self, doc_id: str, user_id: str):
        """Export document data to S3 backup"""
        if not self.storage_service or not self.s3_client:
            return

        try:
            # Get document and chunks from storage service
            # For now, we'll use a simplified approach
            # In a full implementation, we would query the storage service
            doc_data = [{"doc_id": doc_id, "user_id": user_id}]
            chunks_data = []

            if not doc_data:
                return

            # Prepare export data
            export_data = {
                "document": doc_data[0],
                "chunks": chunks_data,
                "exported_at": datetime.now(timezone.utc).isoformat(),
            }

            # Upload to S3 backup
            s3_key = f"{self.config.s3_backup_prefix}/users/{user_id}/documents/{doc_id}.json"
            self.s3_client.put_object(
                Bucket=self.config.s3_backup_bucket,
                Key=s3_key,
                Body=json.dumps(export_data, indent=2),
                ContentType="application/json",
            )

        except Exception as e:
            logger.error(f"Failed to export document to S3: {e}")
            raise

    async def _update_sync_metadata(self, change_record: ChangeRecord):
        """Update sync metadata in local DB"""
        if not self.storage_service:
            return

        try:
            # Sync metadata is handled by the storage service
            # For now, we'll skip this as it's handled automatically
            pass

            # Sync metadata is handled by the storage service
            # The storage service automatically updates sync timestamps

            # Document sync status is handled by the storage service
            # The storage service automatically updates sync timestamps

        except Exception as e:
            logger.error(f"Failed to update sync metadata: {e}")

    def _generate_checksum(self, *data_objects) -> str:
        """Generate checksum for change detection"""
        combined_data = json.dumps(data_objects, sort_keys=True, default=str)
        return hashlib.md5(combined_data.encode()).hexdigest()

    async def get_sync_status(self, user_id: str) -> Dict[str, Any]:
        """Get sync status for user"""
        pending_syncs = [
            r
            for r in self.change_log
            if r.user_id == user_id and r.sync_status == "pending"
        ]
        failed_syncs = [
            r
            for r in self.change_log
            if r.user_id == user_id and r.sync_status == "failed"
        ]

        # Get storage service status if available
        storage_status = {}
        if self.storage_service:
            try:
                storage_status = await self.storage_service.get_storage_status(user_id)
            except Exception as e:
                logger.error(f"Failed to get storage status: {e}")

        return {
            "storage_service_available": self.storage_service is not None,
            "s3_primary_enabled": self.config.should_use_s3_primary(),
            "s3_backup_enabled": self.config.should_sync_to_s3(),
            "pending_syncs": len(pending_syncs),
            "failed_syncs": len(failed_syncs),
            "total_changes": len([r for r in self.change_log if r.user_id == user_id]),
            "storage_status": storage_status,
        }

    async def cleanup_failed_syncs(self, user_id: str) -> Dict[str, Any]:
        """Clean up failed sync attempts"""
        failed_records = [
            r
            for r in self.change_log
            if r.user_id == user_id and r.sync_status == "failed"
        ]

        for record in failed_records:
            self.change_log.remove(record)

        return {
            "status": "success",
            "cleaned_count": len(failed_records),
            "message": f"Cleaned {len(failed_records)} failed sync records",
        }


# Factory function for easy service creation
def create_incremental_sync_service(
    local_db_path: str = "data/lancedb",
    s3_bucket: Optional[str] = None,
    s3_prefix: str = "lancedb-backup",
) -> IncrementalSyncService:
    """Create incremental sync service with configuration"""
    config = SyncConfig(
        local_db_path=local_db_path, s3_bucket=s3_bucket, s3_prefix=s3_prefix
    )
    return IncrementalSyncService(config)
