"""
LanceDB Storage Service with Local + S3 Hybrid Storage

This service provides a unified interface for LanceDB operations with support for:
- Local storage for fast desktop access
- S3 as primary storage backend
- Automatic sync between local and S3
- Multi-user isolation
- Backend location detection (cloud vs local)
- Frontend-specific storage modes

Key Assumptions:
- Backend folder might be in cloud or local environment
- Desktop app will always be local for LanceDB sync
- Backend will have cloud default settings for web app
"""

import os
import logging
import asyncio
import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import tempfile

# Try to import LanceDB and S3 dependencies
try:
    import lancedb
    import pyarrow as pa
    import boto3
    from botocore.exceptions import ClientError

    LANCEDB_AVAILABLE = True
    S3_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Required dependencies not available: {e}")
    LANCEDB_AVAILABLE = False
    S3_AVAILABLE = False

from . import get_config

logger = logging.getLogger(__name__)


class LanceDBStorageService:
    """
    Unified LanceDB storage service with frontend-specific storage configurations
    - Web App: Cloud-native (S3 primary with local cache)
    - Desktop App: Local-first (local storage with S3 backup)
    - Backend Location: Cloud vs local environment detection
    """

    def __init__(self, config=None):
        self.config = config or get_config()
        self.local_db = None
        self.s3_client = None
        self.user_connections: Dict[str, Any] = {}

        self._initialize_storage()
        logger.info(
            f"Initialized LanceDBStorageService for {self.config.frontend_type} frontend (backend: {self.config.backend_location})"
        )

    def _initialize_storage(self):
        """Initialize storage backends based on frontend configuration and backend location"""
        # Web app: S3 primary with local cache (cloud backend) or local primary (local backend)
        # Desktop app: Local primary with S3 backup (always local-first)

        # Initialize S3 client if enabled and backend is in cloud
        if (
            self.config.s3_storage_enabled
            and S3_AVAILABLE
            and self.config.is_cloud_backend()
        ):
            try:
                self.s3_client = boto3.client(
                    "s3",
                    region_name=self.config.s3_region,
                    endpoint_url=self.config.s3_endpoint,
                )
                # Test S3 connectivity
                if self.config.s3_bucket:
                    self.s3_client.head_bucket(Bucket=self.config.s3_bucket)
                    logger.info(
                        f"Connected to S3 bucket: {self.config.s3_bucket} (cloud backend)"
                    )
            except ClientError as e:
                logger.error(f"Failed to initialize S3 client: {e}")
                self.s3_client = None
            except Exception as e:
                logger.error(f"Unexpected error initializing S3: {e}")
                self.s3_client = None

        # Initialize local storage if enabled (always for desktop, optional for web)
        if self.config.local_cache_enabled and LANCEDB_AVAILABLE:
            try:
                local_path = Path(self.config.local_db_path)
                local_path.mkdir(parents=True, exist_ok=True)
                logger.info(
                    f"Local storage initialized at: {local_path} (backend: {self.config.backend_location})"
                )
            except Exception as e:
                logger.error(f"Failed to initialize local storage: {e}")

    async def get_user_connection(self, user_id: str) -> Any:
        """
        Get LanceDB connection for a specific user based on frontend type

        Args:
            user_id: User identifier

        Returns:
            LanceDB connection object
        """
        if user_id in self.user_connections:
            return self.user_connections[user_id]

        try:
            if self.config.is_web_frontend():
                # Web app: Use S3 as primary with local cache (cloud backend) or local primary (local backend)
                if self.config.is_cloud_backend() and self.config.use_s3_as_primary:
                    connection = await self._get_s3_primary_connection(user_id)
                    logger.debug(
                        f"Web app storage: S3 primary for user {user_id} (cloud backend)"
                    )
                else:
                    connection = await self._get_local_connection(user_id)
                    logger.debug(
                        f"Web app storage: Local primary for user {user_id} (local backend)"
                    )
            else:
                # Desktop app: Always use local storage with S3 backup (local-first)
                connection = await self._get_local_connection(user_id)
                logger.debug(
                    f"Desktop app storage: Local primary for user {user_id} (local-first)"
                )

            self.user_connections[user_id] = connection
            return connection

        except Exception as e:
            logger.error(f"Failed to get connection for user {user_id}: {e}")
            raise

    async def _get_s3_primary_connection(self, user_id: str) -> Any:
        """Get LanceDB connection using S3 as primary storage (web app default)"""
        if not LANCEDB_AVAILABLE or not self.s3_client:
            raise RuntimeError("S3 storage not available")

        try:
            s3_uri = self.config.get_lancedb_uri(user_id)
            connection = lancedb.connect(s3_uri)

            # Ensure tables exist
            await self._ensure_user_tables_exist(connection, user_id)

            logger.info(
                f"Connected to S3 primary storage for user {user_id} (cloud backend)"
            )
            return connection

        except Exception as e:
            logger.error(f"Failed to connect to S3 primary storage: {e}")
            # Fall back to local storage
            return await self._get_local_connection(user_id)

    async def _get_local_connection(self, user_id: str) -> Any:
        """Get LanceDB connection using local storage (desktop app default)"""
        if not LANCEDB_AVAILABLE:
            raise RuntimeError("LanceDB not available")

        try:
            local_uri = self.config.get_lancedb_uri(user_id)
            connection = lancedb.connect(local_uri)

            # Ensure tables exist
            await self._ensure_user_tables_exist(connection, user_id)

            logger.info(
                f"Connected to local storage for user {user_id} (backend: {self.config.backend_location})"
            )
            return connection

        except Exception as e:
            logger.error(f"Failed to connect to local storage: {e}")
            raise

    async def _ensure_user_tables_exist(self, connection, user_id: str):
        """Ensure required tables exist for a user"""
        try:
            # Schema for processed documents
            document_schema = pa.schema(
                [
                    pa.field("doc_id", pa.string()),
                    pa.field("user_id", pa.string()),
                    pa.field("source_uri", pa.string()),
                    pa.field("doc_type", pa.string()),
                    pa.field("title", pa.string()),
                    pa.field("metadata_json", pa.string()),
                    pa.field("ingested_at", pa.string()),
                    pa.field("processing_status", pa.string()),
                    pa.field("checksum", pa.string()),
                    pa.field("last_synced", pa.string()),
                    pa.field("vector_embedding", pa.list_(pa.float32(), 1536)),
                ]
            )

            # Schema for document chunks
            chunk_schema = pa.schema(
                [
                    pa.field("chunk_id", pa.string()),
                    pa.field("doc_id", pa.string()),
                    pa.field("user_id", pa.string()),
                    pa.field("chunk_index", pa.int32()),
                    pa.field("chunk_text", pa.string()),
                    pa.field("metadata", pa.string()),
                    pa.field("vector_embedding", pa.list_(pa.float32(), 1536)),
                    pa.field("created_at", pa.string()),
                    pa.field("checksum", pa.string()),
                ]
            )

            # Schema for sync metadata
            sync_schema = pa.schema(
                [
                    pa.field("key", pa.string()),
                    pa.field("value", pa.string()),
                    pa.field("last_updated", pa.string()),
                ]
            )

            tables_to_create = {
                "processed_documents": document_schema,
                "document_chunks": chunk_schema,
                "sync_metadata": sync_schema,
            }

            for table_name, schema in tables_to_create.items():
                if table_name not in connection.table_names():
                    connection.create_table(table_name, schema=schema)
                    logger.debug(f"Created table {table_name} for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to ensure tables exist for user {user_id}: {e}")
            raise

    async def store_document(
        self,
        user_id: str,
        document_data: Dict[str, Any],
        chunks_with_embeddings: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Store document and chunks with frontend-specific storage

        Args:
            user_id: User identifier
            document_data: Document metadata
            chunks_with_embeddings: Document chunks with embeddings

        Returns:
            Storage result
        """
        try:
            connection = await self.get_user_connection(user_id)

            # Generate checksum for change detection
            doc_checksum = self._generate_checksum(
                document_data, chunks_with_embeddings
            )

            # Prepare document record
            doc_record = {
                "doc_id": document_data.get("doc_id"),
                "user_id": user_id,
                "source_uri": document_data.get("source_uri", ""),
                "doc_type": document_data.get("doc_type", "unknown"),
                "title": document_data.get("title", ""),
                "metadata_json": json.dumps(document_data.get("metadata", {})),
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "processing_status": "completed",
                "checksum": doc_checksum,
                "last_synced": "",
                "vector_embedding": [0.0] * 1536,  # Placeholder
            }

            # Prepare chunk records
            chunk_records = []
            for i, chunk in enumerate(chunks_with_embeddings):
                chunk_record = {
                    "chunk_id": f"{doc_record['doc_id']}_{i}",
                    "doc_id": doc_record["doc_id"],
                    "user_id": user_id,
                    "chunk_index": i,
                    "chunk_text": chunk.get("text_content", ""),
                    "metadata": json.dumps(chunk.get("metadata", {})),
                    "vector_embedding": chunk.get("embedding", []),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "checksum": self._generate_checksum(chunk),
                }
                chunk_records.append(chunk_record)

            # Store in primary storage
            docs_table = connection.open_table("processed_documents")
            chunks_table = connection.open_table("document_chunks")

            docs_table.add([doc_record])
            if chunk_records:
                chunks_table.add(chunk_records)

            # Sync to S3 backup for desktop app or if explicitly configured
            if self.config.should_sync_to_s3():
                if self.config.is_desktop_frontend():
                    # Desktop app: Always sync to S3 backup
                    await self._sync_to_s3_backup(user_id, doc_record["doc_id"])
                elif not self.config.should_use_s3_primary():
                    # Web app: Only sync if not using S3 primary
                    await self._sync_to_s3_backup(user_id, doc_record["doc_id"])

            logger.info(f"Stored document {doc_record['doc_id']} for user {user_id}")

            return {
                "status": "success",
                "doc_id": doc_record["doc_id"],
                "storage_backend": "s3_primary"
                if self.config.is_web_frontend()
                else "local_primary",
                "frontend_type": self.config.frontend_type,
                "chunks_stored": len(chunk_records),
            }

        except Exception as e:
            logger.error(f"Failed to store document for user {user_id}: {e}")
            return {
                "status": "error",
                "message": str(e),
                "code": "STORAGE_ERROR",
            }

    async def search_documents(
        self, user_id: str, query_vector: List[float], limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search documents using vector similarity

        Args:
            user_id: User identifier
            query_vector: Query embedding vector
            limit: Maximum number of results

        Returns:
            Search results
        """
        try:
            connection = await self.get_user_connection(user_id)
            chunks_table = connection.open_table("document_chunks")

            # Search for similar chunks
            results = (
                chunks_table.search(query_vector)
                .where(f"user_id = '{user_id}'")
                .limit(limit)
                .to_list()
            )

            # Group results by document
            document_results = {}
            for result in results:
                doc_id = result.get("doc_id")
                if doc_id not in document_results:
                    document_results[doc_id] = {
                        "doc_id": doc_id,
                        "user_id": result.get("user_id"),
                        "chunks": [],
                        "max_score": result.get("_distance", 0.0),
                    }
                document_results[doc_id]["chunks"].append(
                    {
                        "chunk_id": result.get("chunk_id"),
                        "chunk_text": result.get("chunk_text", ""),
                        "score": result.get("_distance", 0.0),
                    }
                )

            # Get document metadata
            docs_table = connection.open_table("processed_documents")
            final_results = []
            for doc_id, doc_data in document_results.items():
                doc_info = (
                    docs_table.search([0.0] * 1536)
                    .where(f"doc_id = '{doc_id}' AND user_id = '{user_id}'")
                    .limit(1)
                    .to_list()
                )

                if doc_info:
                    final_results.append(
                        {
                            **doc_data,
                            "title": doc_info[0].get("title", ""),
                            "source_uri": doc_info[0].get("source_uri", ""),
                            "doc_type": doc_info[0].get("doc_type", ""),
                        }
                    )

            return {
                "status": "success",
                "results": final_results,
                "count": len(final_results),
            }

        except Exception as e:
            logger.error(f"Failed to search documents for user {user_id}: {e}")
            return {
                "status": "error",
                "message": str(e),
                "code": "SEARCH_ERROR",
            }

    async def _sync_to_s3_backup(self, user_id: str, doc_id: str):
        """Sync document to S3 backup (primarily for desktop app)"""
        if not self.s3_client or not self.config.s3_backup_bucket:
            return

        try:
            connection = await self.get_user_connection(user_id)

            # Get document and chunks
            docs_table = connection.open_table("processed_documents")
            chunks_table = connection.open_table("document_chunks")

            doc_data = (
                docs_table.search([0.0] * 1536)
                .where(f"doc_id = '{doc_id}' AND user_id = '{user_id}'")
                .limit(1)
                .to_list()
            )

            chunks_data = (
                chunks_table.search([0.0] * 1536)
                .where(f"doc_id = '{doc_id}' AND user_id = '{user_id}'")
                .to_list()
            )

            if not doc_data:
                return

            # Prepare backup data
            backup_data = {
                "document": doc_data[0],
                "chunks": chunks_data,
                "backup_timestamp": datetime.now(timezone.utc).isoformat(),
                "user_id": user_id,
            }

            # Upload to S3 backup
            s3_key = f"{self.config.get_s3_backup_key_prefix(user_id)}/documents/{doc_id}.json"
            self.s3_client.put_object(
                Bucket=self.config.s3_backup_bucket,
                Key=s3_key,
                Body=json.dumps(backup_data, indent=2),
                ContentType="application/json",
            )

            # Update sync timestamp
            docs_table.update(
                where=f"doc_id = '{doc_id}' AND user_id = '{user_id}'",
                values={"last_synced": datetime.now(timezone.utc).isoformat()},
            )

            logger.debug(f"Synced document {doc_id} to S3 backup")

        except Exception as e:
            logger.error(f"Failed to sync document {doc_id} to S3 backup: {e}")

    async def sync_user_data(self, user_id: str) -> Dict[str, Any]:
        """
        Sync all user data between local and S3 storage
        - Desktop app: Sync local → S3 backup
        - Web app: Sync S3 ↔ local cache

        Args:
            user_id: User identifier

        Returns:
            Sync results
        """
        try:
            if (
                not self.config.s3_backup_enabled
                and not self.config.should_use_s3_primary()
            ):
                return {
                    "status": "skipped",
                    "message": "S3 backup not enabled",
                }

            connection = await self.get_user_connection(user_id)
            docs_table = connection.open_table("processed_documents")

            # Find documents that need sync
            # For desktop app: sync all documents to S3 backup
            # For web app: sync only if not using S3 primary
            if self.config.is_desktop_frontend():
                unsynced_docs = (
                    docs_table.search([0.0] * 1536)
                    .where(f"user_id = '{user_id}' AND last_synced = ''")
                    .to_list()
                )
            else:
                # Web app: only sync if explicitly configured for backup
                unsynced_docs = (
                    (
                        docs_table.search([0.0] * 1536)
                        .where(f"user_id = '{user_id}' AND last_synced = ''")
                        .to_list()
                    )
                    if self.config.s3_backup_enabled
                    else []
                )

            sync_results = {
                "total_documents": len(unsynced_docs),
                "synced_documents": 0,
                "failed_syncs": 0,
            }

            for doc in unsynced_docs:
                try:
                    await self._sync_to_s3_backup(user_id, doc["doc_id"])
                    sync_results["synced_documents"] += 1
                except Exception as e:
                    logger.error(f"Failed to sync document {doc['doc_id']}: {e}")
                    sync_results["failed_syncs"] += 1

            return {
                "status": "success",
                "message": f"Synced {sync_results['synced_documents']} documents",
                "sync_results": sync_results,
            }

        except Exception as e:
            logger.error(f"Failed to sync user data for {user_id}: {e}")
            return {
                "status": "error",
                "message": str(e),
                "code": "SYNC_ERROR",
            }

    def _generate_checksum(self, *data_objects) -> str:
        """Generate checksum for change detection"""
        combined_data = json.dumps(data_objects, sort_keys=True, default=str)
        return hashlib.md5(combined_data.encode()).hexdigest()

    async def get_storage_status(self, user_id: str) -> Dict[str, Any]:
        """
        Get storage status for a user

        Args:
            user_id: User identifier

        Returns:
            Storage status information
        """
        try:
            connection = await self.get_user_connection(user_id)

            docs_table = connection.open_table("processed_documents")
            chunks_table = connection.open_table("document_chunks")

            docs_count = len(
                docs_table.search([0.0] * 1536)
                .where(f"user_id = '{user_id}'")
                .to_list()
            )

            chunks_count = len(
                chunks_table.search([0.0] * 1536)
                .where(f"user_id = '{user_id}'")
                .to_list()
            )

            return {
                "status": "success",
                "user_id": user_id,
                "frontend_type": self.config.frontend_type,
                "storage_backend": "s3_primary"
                if self.config.is_web_frontend()
                else "local_primary",
                "documents_count": docs_count,
                "chunks_count": chunks_count,
                "s3_backup_enabled": self.config.s3_backup_enabled,
                "local_cache_enabled": self.config.local_cache_enabled,
                "recommended_mode": self.config.get_recommended_storage_mode(),
            }

        except Exception as e:
            logger.error(f"Failed to get storage status for user {user_id}: {e}")
            return {
                "status": "error",
                "message": str(e),
                "code": "STATUS_ERROR",
            }


# Factory function for easy service creation
def create_lancedb_storage_service(config=None):
    """Create a LanceDB storage service instance"""
    return LanceDBStorageService(config)


# Global storage service instance
_storage_service: Optional[LanceDBStorageService] = None


async def get_storage_service() -> LanceDBStorageService:
    """Get or create the global storage service instance"""
    global _storage
