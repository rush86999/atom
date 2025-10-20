"""
LanceDB Handler for Document Ingestion Pipeline

This module provides functions for storing and retrieving processed documents
in LanceDB for efficient recall and search operations.
Integrated with incremental sync system for local + S3 storage.
"""

import os
import logging
import json
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union
import asyncio

# Try to import LanceDB, but provide fallback if not available
try:
    import lancedb
    import pyarrow as pa
    import pandas as pd
    import numpy as np
    from lancedb.table import Table

    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False
    logging.warning("LanceDB library not available. Document storage will be disabled.")

logger = logging.getLogger(__name__)

# Configuration - Import from sync system
try:
    from .sync import get_config

    config = get_config()
    LANCEDB_URI = config.local_db_path
    LANCEDB_TABLE_NAME = config.local_db_table_name
    LANCEDB_CHUNKS_TABLE_NAME = config.local_db_chunks_table_name
except ImportError:
    # Fallback to environment variables if sync system not available
    LANCEDB_URI = os.environ.get("LANCEDB_URI", "data/lancedb")
    LANCEDB_TABLE_NAME = os.environ.get("LANCEDB_TABLE_NAME", "processed_documents")
    LANCEDB_CHUNKS_TABLE_NAME = os.environ.get(
        "LANCEDB_CHUNKS_TABLE_NAME", "document_chunks"
    )

# Global connection cache
_db_connection = None


async def get_lancedb_connection():
    """
    Get a connection to LanceDB database.

    Returns:
        lancedb.DBConnection or None: LanceDB connection if available, None otherwise
    """
    global _db_connection

    if not LANCEDB_AVAILABLE:
        logger.warning("LanceDB not available - returning None connection")
        return None

    try:
        if _db_connection is None:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(LANCEDB_URI), exist_ok=True)

            # Connect to LanceDB
            _db_connection = lancedb.connect(LANCEDB_URI)
            logger.info(f"Connected to LanceDB at {LANCEDB_URI}")

            # Ensure tables exist
            await create_generic_document_tables_if_not_exist(_db_connection)

        return _db_connection

    except Exception as e:
        logger.error(f"Failed to connect to LanceDB: {e}")
        return None


async def create_generic_document_tables_if_not_exist(db_conn):
    """
    Create the necessary tables in LanceDB if they don't exist.

    Args:
        db_conn: LanceDB connection object

    Returns:
        bool: True if tables were created or already exist, False on error
    """
    if not LANCEDB_AVAILABLE or db_conn is None:
        logger.warning("LanceDB not available - skipping table creation")
        return False

    try:
        # Schema for main documents table
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
                pa.field("error_message", pa.string()),
                pa.field("total_chunks", pa.int32()),
                pa.field(
                    "vector_embedding", pa.list_(pa.float32(), 1536)
                ),  # OpenAI embedding dimension
            ]
        )

        # Schema for document chunks table
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
            ]
        )

        # Create tables if they don't exist
        if LANCEDB_TABLE_NAME not in db_conn.table_names():
            db_conn.create_table(LANCEDB_TABLE_NAME, schema=document_schema)
            logger.info(f"Created LanceDB table: {LANCEDB_TABLE_NAME}")

        if LANCEDB_CHUNKS_TABLE_NAME not in db_conn.table_names():
            db_conn.create_table(LANCEDB_CHUNKS_TABLE_NAME, schema=chunk_schema)
            logger.info(f"Created LanceDB table: {LANCEDB_CHUNKS_TABLE_NAME}")

        # Create sync metadata table if it doesn't exist
        sync_table_name = "sync_metadata"
        sync_schema = pa.schema(
            [
                pa.field("key", pa.string()),
                pa.field("value", pa.string()),
                pa.field("last_updated", pa.string()),
            ]
        )

        if sync_table_name not in db_conn.table_names():
            db_conn.create_table(sync_table_name, schema=sync_schema)
            logger.info(f"Created LanceDB table: {sync_table_name}")

        return True

    except Exception as e:
        logger.error(f"Failed to create LanceDB tables: {e}")
        return False


async def add_processed_document(
    db_conn, doc_meta: Dict[str, Any], chunks_with_embeddings: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Add a processed document and its chunks to LanceDB.

    Args:
        db_conn: LanceDB connection object
        doc_meta: Document metadata dictionary
        chunks_with_embeddings: List of chunk dictionaries with embeddings

    Returns:
        Dict with status and message
    """
    if not LANCEDB_AVAILABLE or db_conn is None:
        return {
            "status": "error",
            "message": "LanceDB not available",
            "code": "LANCEDB_UNAVAILABLE",
        }

    try:
        # Get tables
        docs_table = db_conn.open_table(LANCEDB_TABLE_NAME)
        chunks_table = db_conn.open_table(LANCEDB_CHUNKS_TABLE_NAME)

        # Prepare document data
        doc_data = {
            "doc_id": doc_meta.get("doc_id"),
            "user_id": doc_meta.get("user_id"),
            "source_uri": doc_meta.get("source_uri"),
            "doc_type": doc_meta.get("doc_type"),
            "title": doc_meta.get("title", ""),
            "metadata_json": doc_meta.get("metadata_json"),
            "ingested_at": doc_meta.get(
                "ingested_at", datetime.now(timezone.utc).isoformat()
            ),
            "processing_status": doc_meta.get("processing_status", "completed"),
            "error_message": doc_meta.get("error_message", ""),
            "total_chunks": len(chunks_with_embeddings),
            "vector_embedding": [0.0]
            * 1536,  # Placeholder embedding for document level
            "checksum": doc_meta.get("checksum", ""),  # For incremental sync
            "last_synced": doc_meta.get("last_synced", ""),  # For S3 sync tracking
        }

        # Prepare chunks data
        chunks_data = []
        for chunk in chunks_with_embeddings:
            chunk_data = {
                "chunk_id": f"{doc_meta.get('doc_id')}_{chunk.get('chunk_sequence', 0)}",
                "doc_id": doc_meta.get("doc_id"),
                "user_id": doc_meta.get("user_id"),
                "chunk_index": chunk.get("chunk_sequence", 0),
                "chunk_text": chunk.get("text_content", ""),
                "metadata": chunk.get("metadata_json", ""),
                "vector_embedding": chunk.get("embedding", []),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "checksum": chunk.get("checksum", ""),  # For incremental sync
            }
            chunks_data.append(chunk_data)

        # Insert data
        if chunks_data:
            chunks_table.add(chunks_data)

        docs_table.add([doc_data])

        logger.info(
            f"Successfully stored document {doc_meta.get('doc_id')} with {len(chunks_data)} chunks"
        )
        return {"status": "success", "message": "Document stored successfully"}

    except Exception as e:
        logger.error(f"Failed to store document in LanceDB: {e}")
        return {
            "status": "error",
            "message": f"LanceDB storage failed: {str(e)}",
            "code": "LANCEDB_STORAGE_ERROR",
        }


async def search_documents(
    db_conn, query_vector: List[float], user_id: str, limit: int = 10
) -> Dict[str, Any]:
    """
    Search for documents using vector similarity.

    Args:
        db_conn: LanceDB connection object
        query_vector: Query embedding vector
        user_id: User ID to filter results
        limit: Maximum number of results

    Returns:
        Dict with search results
    """
    if not LANCEDB_AVAILABLE or db_conn is None:
        return {
            "status": "error",
            "message": "LanceDB not available",
            "code": "LANCEDB_UNAVAILABLE",
        }

    try:
        chunks_table = db_conn.open_table(LANCEDB_CHUNKS_TABLE_NAME)

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

        # Get document metadata for each result
        docs_table = db_conn.open_table(LANCEDB_TABLE_NAME)
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
        logger.error(f"Failed to search documents in LanceDB: {e}")
        return {
            "status": "error",
            "message": f"LanceDB search failed: {str(e)}",
            "code": "LANCEDB_SEARCH_ERROR",
        }


async def get_document_chunks(db_conn, doc_id: str, user_id: str) -> Dict[str, Any]:
    """
    Get all chunks for a specific document.

    Args:
        db_conn: LanceDB connection object
        doc_id: Document ID
        user_id: User ID

    Returns:
        Dict with document chunks
    """
    if not LANCEDB_AVAILABLE or db_conn is None:
        return {
            "status": "error",
            "message": "LanceDB not available",
            "code": "LANCEDB_UNAVAILABLE",
        }

    try:
        chunks_table = db_conn.open_table(LANCEDB_CHUNKS_TABLE_NAME)

        results = (
            chunks_table.search([0.0] * 1536)
            .where(f"doc_id = '{doc_id}' AND user_id = '{user_id}'")
            .to_list()
        )

        # Sort by chunk index
        results.sort(key=lambda x: x.get("chunk_index", 0))

        return {"status": "success", "chunks": results, "count": len(results)}

    except Exception as e:
        logger.error(f"Failed to get document chunks from LanceDB: {e}")
        return {
            "status": "error",
            "message": f"LanceDB retrieval failed: {str(e)}",
            "code": "LANCEDB_RETRIEVAL_ERROR",
        }


async def delete_document(db_conn, doc_id: str, user_id: str) -> Dict[str, Any]:
    """
    Delete a document and all its chunks from LanceDB.

    Args:
        db_conn: LanceDB connection object
        doc_id: Document ID
        user_id: User ID

    Returns:
        Dict with deletion status
    """
    if not LANCEDB_AVAILABLE or db_conn is None:
        return {
            "status": "error",
            "message": "LanceDB not available",
            "code": "LANCEDB_UNAVAILABLE",
        }

    try:
        docs_table = db_conn.open_table(LANCEDB_TABLE_NAME)
        chunks_table = db_conn.open_table(LANCEDB_CHUNKS_TABLE_NAME)

        # Delete chunks first
        chunks_table.delete(f"doc_id = '{doc_id}' AND user_id = '{user_id}'")

        # Delete document
        docs_table.delete(f"doc_id = '{doc_id}' AND user_id = '{user_id}'")

        logger.info(f"Deleted document {doc_id} and its chunks from LanceDB")
        return {"status": "success", "message": "Document deleted successfully"}

    except Exception as e:
        logger.error(f"Failed to delete document from LanceDB: {e}")
        return {
            "status": "error",
            "message": f"LanceDB deletion failed: {str(e)}",
            "code": "LANCEDB_DELETION_ERROR",
        }


async def get_document_stats(db_conn, user_id: str) -> Dict[str, Any]:
    """
    Get statistics about documents in LanceDB for a user.

    Args:
        db_conn: LanceDB connection object
        user_id: User ID

    Returns:
        Dict with statistics
    """
    if not LANCEDB_AVAILABLE or db_conn is None:
        return {
            "status": "error",
            "message": "LanceDB not available",
            "code": "LANCEDB_UNAVAILABLE",
        }

    try:
        docs_table = db_conn.open_table(LANCEDB_TABLE_NAME)
        chunks_table = db_conn.open_table(LANCEDB_CHUNKS_TABLE_NAME)

        # Get document count
        docs = docs_table.search([0.0] * 1536).where(f"user_id = '{user_id}'").to_list()

        # Get chunk count
        chunks = (
            chunks_table.search([0.0] * 1536).where(f"user_id = '{user_id}'").to_list()
        )

        # Count by document type
        doc_types = {}
        for doc in docs:
            doc_type = doc.get("doc_type", "unknown")
            doc_types[doc_type] = doc_types.get(doc_type, 0) + 1

        return {
            "status": "success",
            "total_documents": len(docs),
            "total_chunks": len(chunks),
            "documents_by_type": doc_types,
        }

    except Exception as e:
        logger.error(f"Failed to get document stats from LanceDB: {e}")
        return {
            "status": "error",
            "message": f"LanceDB stats retrieval failed: {str(e)}",
            "code": "LANCEDB_STATS_ERROR",
        }


async def get_sync_status(db_conn, user_id: str) -> Dict[str, Any]:
    """
    Get sync status information for a user.

    Args:
        db_conn: LanceDB connection object
        user_id: User ID

    Returns:
        Dict with sync status information
    """
    if not LANCEDB_AVAILABLE or db_conn is None:
        return {
            "status": "error",
            "message": "LanceDB not available",
            "code": "LANCEDB_UNAVAILABLE",
        }

    try:
        docs_table = db_conn.open_table(LANCEDB_TABLE_NAME)
        chunks_table = db_conn.open_table(LANCEDB_CHUNKS_TABLE_NAME)
        sync_table = db_conn.open_table("sync_metadata")

        # Get document count
        docs = docs_table.search([0.0] * 1536).where(f"user_id = '{user_id}'").to_list()

        # Get chunk count
        chunks = (
            chunks_table.search([0.0] * 1536).where(f"user_id = '{user_id}'").to_list()
        )

        # Get last sync time
        sync_records = (
            sync_table.search([0.0] * 1536)
            .where(f"key = 'last_sync_{user_id}'")
            .limit(1)
            .to_list()
        )

        last_sync = sync_records[0].get("value") if sync_records else None

        # Count documents needing sync
        docs_needing_sync = (
            docs_table.search([0.0] * 1536)
            .where(f"user_id = '{user_id}' AND last_synced = ''")
            .to_list()
        )

        return {
            "status": "success",
            "total_documents": len(docs),
            "total_chunks": len(chunks),
            "last_sync_time": last_sync,
            "documents_needing_sync": len(docs_needing_sync),
            "sync_ready": True,
        }

    except Exception as e:
        logger.error(f"Failed to get sync status from LanceDB: {e}")
        return {
            "status": "error",
            "message": f"LanceDB sync status retrieval failed: {str(e)}",
            "code": "LANCEDB_SYNC_STATUS_ERROR",
        }
