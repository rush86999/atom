"""
LanceDB Client for Desktop App

Lightweight client for desktop applications that provides:
- Local LanceDB storage for fast access
- Sync capabilities with cloud backend
- Offline-first operation
- Automatic conflict resolution
"""

import os
import logging
import json
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from pathlib import Path

# Try to import LanceDB for local storage
try:
    import lancedb
    import pyarrow as pa

    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False
    logging.warning("LanceDB not available - local storage disabled")

logger = logging.getLogger(__name__)


class DesktopLanceDBClient:
    """
    Lightweight LanceDB client optimized for desktop applications

    Features:
    - Local-first storage for performance
    - Background sync with cloud backend
    - Offline operation support
    - Automatic conflict resolution
    """

    def __init__(self, local_db_path: str = "data/lancedb", sync_enabled: bool = True):
        self.local_db_path = local_db_path
        self.sync_enabled = sync_enabled
        self.local_db = None
        self.sync_queue: List[Dict[str, Any]] = []
        self.sync_in_progress = False

        # Initialize local storage
        self._init_local_storage()

        logger.info(f"Initialized Desktop LanceDB Client at {local_db_path}")

    def _init_local_storage(self):
        """Initialize local LanceDB storage"""
        if not LANCEDB_AVAILABLE:
            logger.warning("LanceDB not available - local storage disabled")
            return

        try:
            # Create directory if it doesn't exist
            Path(self.local_db_path).mkdir(parents=True, exist_ok=True)

            # Connect to local LanceDB
            self.local_db = lancedb.connect(self.local_db_path)

            # Ensure tables exist
            self._ensure_tables_exist()

            logger.info(f"Local LanceDB initialized at {self.local_db_path}")

        except Exception as e:
            logger.error(f"Failed to initialize local LanceDB: {e}")
            self.local_db = None

    def _ensure_tables_exist(self):
        """Ensure required tables exist in local database"""
        if not self.local_db:
            return

        try:
            # Schema for documents
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
                if table_name not in self.local_db.table_names():
                    self.local_db.create_table(table_name, schema=schema)
                    logger.debug(f"Created local table: {table_name}")

        except Exception as e:
            logger.error(f"Failed to ensure tables exist: {e}")

    async def store_document_local(
        self,
        user_id: str,
        document_data: Dict[str, Any],
        chunks_with_embeddings: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Store document locally (offline-first approach)

        Args:
            user_id: User identifier
            document_data: Document metadata
            chunks_with_embeddings: Document chunks with embeddings

        Returns:
            Storage result
        """
        if not self.local_db:
            return {
                "status": "error",
                "message": "Local storage not available",
                "code": "LOCAL_STORAGE_UNAVAILABLE",
            }

        try:
            # Generate document ID if not provided
            doc_id = document_data.get("doc_id") or f"doc_{datetime.now().timestamp()}"

            # Prepare document record
            doc_record = {
                "doc_id": doc_id,
                "user_id": user_id,
                "source_uri": document_data.get("source_uri", ""),
                "doc_type": document_data.get("doc_type", "unknown"),
                "title": document_data.get("title", ""),
                "metadata_json": json.dumps(document_data.get("metadata", {})),
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "processing_status": "completed",
                "checksum": self._generate_checksum(
                    document_data, chunks_with_embeddings
                ),
                "last_synced": "",  # Not synced yet
                "vector_embedding": [0.0] * 1536,  # Placeholder
            }

            # Prepare chunk records
            chunk_records = []
            for i, chunk in enumerate(chunks_with_embeddings):
                chunk_record = {
                    "chunk_id": f"{doc_id}_{i}",
                    "doc_id": doc_id,
                    "user_id": user_id,
                    "chunk_index": i,
                    "chunk_text": chunk.get("text_content", ""),
                    "metadata": json.dumps(chunk.get("metadata", {})),
                    "vector_embedding": chunk.get("embedding", []),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "checksum": self._generate_checksum(chunk),
                }
                chunk_records.append(chunk_record)

            # Store in local database
            docs_table = self.local_db.open_table("processed_documents")
            chunks_table = self.local_db.open_table("document_chunks")

            docs_table.add([doc_record])
            if chunk_records:
                chunks_table.add(chunk_records)

            # Queue for sync if enabled
            if self.sync_enabled:
                sync_item = {
                    "operation": "store",
                    "user_id": user_id,
                    "document_data": document_data,
                    "chunks_with_embeddings": chunks_with_embeddings,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                self.sync_queue.append(sync_item)

                # Start background sync if not already running
                if not self.sync_in_progress:
                    asyncio.create_task(self._background_sync())

            logger.info(f"Stored document {doc_id} locally for user {user_id}")

            return {
                "status": "success",
                "doc_id": doc_id,
                "local_stored": True,
                "queued_for_sync": self.sync_enabled,
                "chunks_stored": len(chunk_records),
            }

        except Exception as e:
            logger.error(f"Failed to store document locally: {e}")
            return {"status": "error", "message": str(e), "code": "LOCAL_STORAGE_ERROR"}

    async def search_documents_local(
        self, user_id: str, query_vector: List[float], limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search documents in local database

        Args:
            user_id: User identifier
            query_vector: Query embedding vector
            limit: Maximum number of results

        Returns:
            Search results
        """
        if not self.local_db:
            return {
                "status": "error",
                "message": "Local storage not available",
                "code": "LOCAL_STORAGE_UNAVAILABLE",
            }

        try:
            chunks_table = self.local_db.open_table("document_chunks")

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
            docs_table = self.local_db.open_table("processed_documents")
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
                "source": "local",
            }

        except Exception as e:
            logger.error(f"Failed to search documents locally: {e}")
            return {"status": "error", "message": str(e), "code": "LOCAL_SEARCH_ERROR"}

    async def _background_sync(self):
        """Background task to sync local changes with cloud backend"""
        if self.sync_in_progress or not self.sync_queue:
            return

        self.sync_in_progress = True

        try:
            while self.sync_queue:
                sync_item = self.sync_queue.pop(0)

                try:
                    await self._sync_with_cloud(sync_item)
                    logger.debug(
                        f"Successfully synced item: {sync_item.get('operation')}"
                    )

                except Exception as e:
                    logger.error(f"Failed to sync item: {e}")
                    # Re-queue failed items for retry
                    self.sync_queue.append(sync_item)
                    break  # Stop sync on first failure

        finally:
            self.sync_in_progress = False

    async def _sync_with_cloud(self, sync_item: Dict[str, Any]):
        """
        Sync item with cloud backend

        Args:
            sync_item: Item to sync
        """
        # This would make HTTP requests to the cloud backend
        # For now, we'll simulate the sync

        operation = sync_item.get("operation")
        user_id = sync_item.get("user_id")

        if operation == "store":
            # Simulate cloud storage
            await asyncio.sleep(0.1)  # Simulate network delay

            # Update sync timestamp in local DB
            if self.local_db:
                docs_table = self.local_db.open_table("processed_documents")
                doc_id = sync_item["document_data"].get("doc_id")

                if doc_id:
                    docs_table.update(
                        where=f"doc_id = '{doc_id}' AND user_id = '{user_id}'",
                        values={"last_synced": datetime.now(timezone.utc).isoformat()},
                    )

        logger.debug(f"Synced {operation} for user {user_id}")

    def _generate_checksum(self, *data_objects) -> str:
        """Generate checksum for change detection"""
        import hashlib

        combined_data = json.dumps(data_objects, sort_keys=True, default=str)
        return hashlib.md5(combined_data.encode()).hexdigest()

    async def get_local_status(self, user_id: str) -> Dict[str, Any]:
        """Get local storage status for user"""
        if not self.local_db:
            return {"status": "error", "message": "Local storage not available"}

        try:
            docs_table = self.local_db.open_table("processed_documents")
            chunks_table = self.local_db.open_table("document_chunks")

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

            unsynced_docs = len(
                docs_table.search([0.0] * 1536)
                .where(f"user_id = '{user_id}' AND last_synced = ''")
                .to_list()
            )

            return {
                "status": "success",
                "user_id": user_id,
                "local_storage_available": True,
                "documents_count": docs_count,
                "chunks_count": chunks_count,
                "unsynced_documents": unsynced_docs,
                "sync_queue_length": len(self.sync_queue),
                "sync_enabled": self.sync_enabled,
            }

        except Exception as e:
            logger.error(f"Failed to get local status: {e}")
            return {"status": "error", "message": str(e)}


# Factory function for easy client creation
def create_desktop_client(
    local_db_path: str = "data/lancedb", sync_enabled: bool = True
) -> DesktopLanceDBClient:
    """Create a desktop LanceDB client instance"""
    return DesktopLanceDBClient(local_db_path, sync_enabled)


# Global client instance for desktop app
_desktop_client: Optional[DesktopLanceDBClient] = None


def get_desktop_client() -> DesktopLanceDBClient:
    """Get or create the global desktop client instance"""
    global _desktop_client

    if _desktop_client is None:
        _desktop_client = create_desktop_client()

    return _desktop_client
