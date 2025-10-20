"""
Migration Script for Existing LanceDB Data

This script migrates existing LanceDB data to the new sync system,
enabling incremental updates and S3 backup capabilities.
"""

import os
import sys
import asyncio
import logging
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sync.integration_service import create_integration_service
from sync.orchestration_service import SourceType, ChangeType
from sync.source_change_detector import SourceChange

logger = logging.getLogger(__name__)


class DataMigrationService:
    """
    Service for migrating existing LanceDB data to the sync system
    """

    def __init__(self):
        self.integration_service = None
        self.migration_stats = {
            "total_documents": 0,
            "documents_migrated": 0,
            "chunks_migrated": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None,
        }

    async def initialize(self) -> bool:
        """Initialize the migration service"""
        try:
            logger.info("Initializing data migration service...")

            # Create integration service with migration enabled
            self.integration_service = create_integration_service(
                enable_legacy_fallback=True,
                migrate_existing_data=True,
                sync_enabled_by_default=True,
            )

            await self.integration_service.initialize()
            logger.info("Data migration service initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize migration service: {e}")
            return False

    async def migrate_user_data(self, user_id: str) -> Dict[str, Any]:
        """
        Migrate all data for a specific user

        Args:
            user_id: User identifier

        Returns:
            Migration results
        """
        self.migration_stats["start_time"] = datetime.now(timezone.utc).isoformat()
        self.migration_stats["total_documents"] = 0
        self.migration_stats["documents_migrated"] = 0
        self.migration_stats["chunks_migrated"] = 0
        self.migration_stats["errors"] = 0

        try:
            logger.info(f"Starting data migration for user: {user_id}")

            # Get existing LanceDB connection
            try:
                from lancedb_handler import get_lancedb_connection

                lancedb_conn = await get_lancedb_connection()
            except ImportError:
                logger.error("LanceDB handler not available")
                return {
                    "status": "error",
                    "message": "LanceDB handler not available",
                    "user_id": user_id,
                }

            if not lancedb_conn:
                logger.error("Failed to connect to LanceDB")
                return {
                    "status": "error",
                    "message": "Failed to connect to LanceDB",
                    "user_id": user_id,
                }

            # Migrate documents from processed_documents table
            await self._migrate_documents_table(lancedb_conn, user_id)

            # Migrate document chunks
            await self._migrate_chunks_table(lancedb_conn, user_id)

            self.migration_stats["end_time"] = datetime.now(timezone.utc).isoformat()

            logger.info(
                f"Migration completed for user {user_id}: {self.migration_stats}"
            )

            return {
                "status": "success",
                "message": "Data migration completed",
                "user_id": user_id,
                "migration_stats": self.migration_stats.copy(),
            }

        except Exception as e:
            logger.error(f"Migration failed for user {user_id}: {e}")
            self.migration_stats["end_time"] = datetime.now(timezone.utc).isoformat()

            return {
                "status": "error",
                "message": f"Migration failed: {str(e)}",
                "user_id": user_id,
                "migration_stats": self.migration_stats.copy(),
            }

    async def _migrate_documents_table(self, lancedb_conn, user_id: str) -> None:
        """Migrate documents from processed_documents table"""
        try:
            # Open the documents table
            try:
                docs_table = lancedb_conn.open_table("processed_documents")
            except Exception as e:
                logger.warning(f"Documents table not found: {e}")
                return

            # Query documents for the user
            user_docs = (
                docs_table.search([0.0] * 1536)
                .where(f"user_id = '{user_id}'")
                .to_list()
            )

            self.migration_stats["total_documents"] = len(user_docs)
            logger.info(f"Found {len(user_docs)} documents for user {user_id}")

            for doc in user_docs:
                try:
                    await self._migrate_single_document(doc, user_id)
                    self.migration_stats["documents_migrated"] += 1

                except Exception as e:
                    logger.error(f"Failed to migrate document {doc.get('doc_id')}: {e}")
                    self.migration_stats["errors"] += 1

        except Exception as e:
            logger.error(f"Error migrating documents table: {e}")
            raise

    async def _migrate_chunks_table(self, lancedb_conn, user_id: str) -> None:
        """Migrate document chunks"""
        try:
            # Open the chunks table
            try:
                chunks_table = lancedb_conn.open_table("document_chunks")
            except Exception as e:
                logger.warning(f"Chunks table not found: {e}")
                return

            # Query chunks for the user
            user_chunks = (
                chunks_table.search([0.0] * 1536)
                .where(f"user_id = '{user_id}'")
                .to_list()
            )

            # Group chunks by document
            chunks_by_doc = {}
            for chunk in user_chunks:
                doc_id = chunk.get("doc_id")
                if doc_id not in chunks_by_doc:
                    chunks_by_doc[doc_id] = []
                chunks_by_doc[doc_id].append(chunk)

            logger.info(f"Found chunks for {len(chunks_by_doc)} documents")

            # Note: Chunks are migrated as part of document migration
            # This method primarily collects statistics

        except Exception as e:
            logger.error(f"Error migrating chunks table: {e}")
            raise

    async def _migrate_single_document(
        self, doc_data: Dict[str, Any], user_id: str
    ) -> None:
        """Migrate a single document to the sync system"""
        try:
            doc_id = doc_data.get("doc_id")
            source_uri = doc_data.get("source_uri", f"migrated://{doc_id}")

            logger.info(f"Migrating document: {doc_id}")

            # Prepare document metadata
            document_data = {
                "doc_id": doc_id,
                "doc_type": doc_data.get("doc_type", "unknown"),
                "title": doc_data.get("title", ""),
                "metadata": self._parse_metadata(doc_data.get("metadata_json", "")),
            }

            # Get chunks for this document
            chunks_with_embeddings = await self._get_document_chunks(doc_id, user_id)

            self.migration_stats["chunks_migrated"] += len(chunks_with_embeddings)

            # Create a source change to trigger sync system processing
            change = SourceChange(
                source_type=SourceType.LOCAL_FILESYSTEM,
                source_id="migration",
                item_id=doc_id,
                item_path=source_uri,
                change_type=ChangeType.CREATED,
                timestamp=datetime.now(timezone.utc).isoformat(),
                metadata={
                    "user_id": user_id,
                    "migration_source": "legacy_system",
                    "original_ingested_at": doc_data.get("ingested_at"),
                    "original_data": {
                        "processing_status": doc_data.get("processing_status"),
                        "total_chunks": doc_data.get("total_chunks", 0),
                    },
                },
                checksum=self._generate_document_checksum(
                    document_data, chunks_with_embeddings
                ),
            )

            # Process through sync system
            if (
                self.integration_service
                and self.integration_service.orchestration_service
            ):
                await self.integration_service.orchestration_service._process_source_change(
                    change
                )

            logger.info(f"Successfully migrated document: {doc_id}")

        except Exception as e:
            logger.error(f"Failed to migrate document {doc_data.get('doc_id')}: {e}")
            raise

    async def _get_document_chunks(
        self, doc_id: str, user_id: str
    ) -> List[Dict[str, Any]]:
        """Get chunks for a specific document"""
        try:
            from lancedb_handler import get_lancedb_connection

            lancedb_conn = await get_lancedb_connection()
            if not lancedb_conn:
                return []

            chunks_table = lancedb_conn.open_table("document_chunks")
            chunks = (
                chunks_table.search([0.0] * 1536)
                .where(f"doc_id = '{doc_id}' AND user_id = '{user_id}'")
                .to_list()
            )

            # Convert to sync system format
            chunks_with_embeddings = []
            for chunk in chunks:
                chunk_data = {
                    "text_content": chunk.get("chunk_text", ""),
                    "embedding": chunk.get("vector_embedding", []),
                    "metadata": {
                        "chunk_index": chunk.get("chunk_index", 0),
                        "original_created_at": chunk.get("created_at"),
                    },
                }
                chunks_with_embeddings.append(chunk_data)

            return chunks_with_embeddings

        except Exception as e:
            logger.error(f"Error getting chunks for document {doc_id}: {e}")
            return []

    def _parse_metadata(self, metadata_json: str) -> Dict[str, Any]:
        """Parse metadata JSON string"""
        try:
            if metadata_json and metadata_json.strip():
                return json.loads(metadata_json)
        except (json.JSONDecodeError, TypeError):
            pass
        return {}

    def _generate_document_checksum(
        self, document_data: Dict[str, Any], chunks: List[Dict[str, Any]]
    ) -> str:
        """Generate checksum for document data"""
        combined_data = {
            "document": document_data,
            "chunks": chunks,
        }
        return hashlib.md5(
            json.dumps(combined_data, sort_keys=True).encode()
        ).hexdigest()

    async def get_migration_status(self) -> Dict[str, Any]:
        """Get current migration status"""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "migration_stats": self.migration_stats.copy(),
            "integration_service_available": self.integration_service is not None,
        }

    async def shutdown(self) -> None:
        """Shutdown the migration service"""
        if self.integration_service:
            await self.integration_service.shutdown()


async def migrate_all_users() -> Dict[str, Any]:
    """
    Migrate data for all users found in the system

    Returns:
        Migration results for all users
    """
    migration_service = DataMigrationService()

    if not await migration_service.initialize():
        return {
            "status": "error",
            "message": "Failed to initialize migration service",
        }

    try:
        # Get all users from the system
        users = await _get_all_users()
        results = {}

        logger.info(f"Starting migration for {len(users)} users")

        for user_id in users:
            user_result = await migration_service.migrate_user_data(user_id)
            results[user_id] = user_result

        # Generate summary
        total_documents = sum(
            r["migration_stats"]["total_documents"]
            for r in results.values()
            if r["status"] == "success"
        )
        migrated_documents = sum(
            r["migration_stats"]["documents_migrated"]
            for r in results.values()
            if r["status"] == "success"
        )
        errors = sum(r["migration_stats"]["errors"] for r in results.values())

        summary = {
            "status": "completed",
            "total_users": len(users),
            "successful_users": len(
                [r for r in results.values() if r["status"] == "success"]
            ),
            "failed_users": len(
                [r for r in results.values() if r["status"] == "error"]
            ),
            "total_documents": total_documents,
            "migrated_documents": migrated_documents,
            "total_errors": errors,
            "user_results": results,
        }

        logger.info(f"Migration completed: {summary}")
        return summary

    finally:
        await migration_service.shutdown()


async def _get_all_users() -> List[str]:
    """Get list of all users in the system"""
    try:
        from lancedb_handler import get_lancedb_connection

        lancedb_conn = await get_lancedb_connection()
        if not lancedb_conn:
            return []

        # Try to get users from documents table
        try:
            docs_table = lancedb_conn.open_table("processed_documents")
            all_docs = docs_table.search([0.0] * 1536).to_list()

            # Extract unique user IDs
            users = set()
            for doc in all_docs:
                user_id = doc.get("user_id")
                if user_id:
                    users.add(user_id)

            return list(users)

        except Exception:
            # If documents table doesn't exist, return empty list
            return []

    except ImportError:
        logger.warning("LanceDB handler not available")
        return []


async def main():
    """Main function for standalone migration execution"""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler("migration.log")],
    )

    logger.info("Starting LanceDB data migration...")

    # Parse command line arguments
    import argparse

    parser = argparse.ArgumentParser(description="Migrate LanceDB data to sync system")
    parser.add_argument("--user", help="Migrate specific user only")
    parser.add_argument("--all-users", action="store_true", help="Migrate all users")

    args = parser.parse_args()

    migration_service = DataMigrationService()

    if not await migration_service.initialize():
        logger.error("Failed to initialize migration service")
        return 1

    try:
        if args.user:
            # Migrate specific user
            result = await migration_service.migrate_user_data(args.user)
            logger.info(f"Migration result for user {args.user}: {result}")

        elif args.all_users:
            # Migrate all users
            result = await migrate_all_users()
            logger.info(f"Migration completed: {result}")

        else:
            logger.info("No migration target specified. Use --user or --all-users")

        return 0

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return 1

    finally:
        await migration_service.shutdown()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
