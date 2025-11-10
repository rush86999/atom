"""
Integration Service for LanceDB Sync System

This service provides integration between the existing ATOM API and the new
LanceDB sync system, allowing seamless migration and coexistence.
"""

import os
import logging
import asyncio
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timezone
from dataclasses import dataclass

from .orchestration_service import (
    OrchestrationService,
    create_orchestration_service,
    SourceConfig,
    SourceType,
)
from .incremental_sync_service import IncrementalSyncService
from .source_change_detector import SourceChangeDetector, SourceChange, ChangeType
from . import get_config

logger = logging.getLogger(__name__)


@dataclass
class IntegrationConfig:
    """Configuration for integration service"""

    enable_legacy_fallback: bool = True
    migrate_existing_data: bool = False
    sync_enabled_by_default: bool = True
    health_check_interval: int = 30


class IntegrationService:
    """
    Service that integrates the LanceDB sync system with existing ATOM API
    """

    def __init__(self, config: IntegrationConfig = None):
        self.config = config or IntegrationConfig()
        self.orchestration_service: Optional[OrchestrationService] = None
        self.legacy_services: Dict[str, Any] = {}
        self.migration_in_progress = False
        self.health_check_task: Optional[asyncio.Task] = None

        logger.info("Initialized IntegrationService")

    async def initialize(self) -> bool:
        """
        Initialize the integration service

        Returns:
            bool: True if initialization successful
        """
        try:
            logger.info("Initializing integration service...")

            # Get sync system configuration
            sync_config = get_config()

            # Create orchestration service
            self.orchestration_service = create_orchestration_service(
                local_db_path=sync_config.local_db_path,
                s3_bucket=sync_config.s3_bucket,
                s3_prefix=sync_config.s3_prefix,
                sync_state_dir=sync_config.sync_state_dir,
                enable_source_monitoring=sync_config.enable_source_monitoring,
            )

            # Start the orchestration service
            await self.orchestration_service.start()

            # Initialize legacy service connections
            await self._initialize_legacy_services()

            # Start health monitoring
            self.health_check_task = asyncio.create_task(self._health_monitoring_loop())

            logger.info("Integration service initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize integration service: {e}")
            return False

    async def shutdown(self) -> bool:
        """
        Shutdown the integration service gracefully

        Returns:
            bool: True if shutdown successful
        """
        try:
            logger.info("Shutting down integration service...")

            # Stop health monitoring
            if self.health_check_task:
                self.health_check_task.cancel()
                try:
                    await self.health_check_task
                except asyncio.CancelledError:
                    pass

            # Stop orchestration service
            if self.orchestration_service:
                await self.orchestration_service.stop()

            # Clean up legacy services
            await self._cleanup_legacy_services()

            logger.info("Integration service shutdown completed")
            return True

        except Exception as e:
            logger.error(f"Error during integration service shutdown: {e}")
            return False

    async def _initialize_legacy_services(self) -> None:
        """Initialize connections to legacy services"""
        try:
            # Import legacy services dynamically to avoid dependency issues
            legacy_services = {}

            # Try to import document service
            try:
                from document_service_enhanced import EnhancedDocumentService

                legacy_services["document_service"] = EnhancedDocumentService
                logger.info("Legacy document service available")
            except ImportError as e:
                logger.warning(f"Legacy document service not available: {e}")

            # Try to import LanceDB handler
            try:
                from lancedb_handler import get_lancedb_connection

                legacy_services["lancedb_handler"] = get_lancedb_connection
                logger.info("Legacy LanceDB handler available")
            except ImportError as e:
                logger.warning(f"Legacy LanceDB handler not available: {e}")

            self.legacy_services = legacy_services

        except Exception as e:
            logger.error(f"Failed to initialize legacy services: {e}")

    async def _cleanup_legacy_services(self) -> None:
        """Clean up legacy service connections"""
        self.legacy_services.clear()

    async def process_document(
        self,
        user_id: str,
        file_data: bytes,
        filename: str,
        source_uri: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        use_sync_system: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Process a document using either sync system or legacy service

        Args:
            user_id: User identifier
            file_data: Document file bytes
            filename: Original filename
            source_uri: Source URI for tracking
            metadata: Additional metadata
            use_sync_system: Whether to use sync system (None = auto-detect)

        Returns:
            Processing results
        """
        try:
            # Auto-detect whether to use sync system
            if use_sync_system is None:
                use_sync_system = self.config.sync_enabled_by_default

            if use_sync_system and self.orchestration_service:
                return await self._process_with_sync_system(
                    user_id, file_data, filename, source_uri, metadata
                )
            elif self.config.enable_legacy_fallback:
                return await self._process_with_legacy_service(
                    user_id, file_data, filename, source_uri, metadata
                )
            else:
                return {
                    "status": "error",
                    "message": "No available processing method",
                    "code": "NO_PROCESSING_METHOD",
                }

        except Exception as e:
            logger.error(f"Failed to process document: {e}")
            return {
                "status": "error",
                "message": f"Document processing failed: {str(e)}",
                "code": "PROCESSING_ERROR",
            }

    async def _process_with_sync_system(
        self,
        user_id: str,
        file_data: bytes,
        filename: str,
        source_uri: Optional[str],
        metadata: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Process document using sync system"""
        try:
            # For now, this is a placeholder implementation
            # In a full implementation, this would:
            # 1. Extract document content
            # 2. Generate embeddings
            # 3. Use sync service for storage

            # Create a mock source change to trigger processing
            from .source_change_detector import SourceChange, ChangeType

            change = SourceChange(
                source_type=SourceType.LOCAL_FILESYSTEM,
                source_id="api_upload",
                item_id=f"upload_{datetime.now(timezone.utc).timestamp()}",
                item_path=source_uri or f"upload://{filename}",
                change_type=ChangeType.CREATED,
                timestamp=datetime.now(timezone.utc).isoformat(),
                metadata={
                    "user_id": user_id,
                    "filename": filename,
                    "file_size": len(file_data),
                    "upload_metadata": metadata or {},
                },
            )

            # Process the change through orchestration service
            await self.orchestration_service._process_source_change(change)

            return {
                "status": "success",
                "message": "Document queued for processing with sync system",
                "processing_method": "sync_system",
                "doc_id": change.item_id,
            }

        except Exception as e:
            logger.error(f"Sync system processing failed: {e}")
            raise

    async def _process_with_legacy_service(
        self,
        user_id: str,
        file_data: bytes,
        filename: str,
        source_uri: Optional[str],
        metadata: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Process document using legacy service"""
        try:
            if "document_service" not in self.legacy_services:
                return {
                    "status": "error",
                    "message": "Legacy document service not available",
                    "code": "LEGACY_SERVICE_UNAVAILABLE",
                }

            # Create document service instance with sync service integration
            DocumentService = self.legacy_services["document_service"]

            # Get LanceDB connection for legacy service
            lancedb_conn = None
            if "lancedb_handler" in self.legacy_services:
                lancedb_conn = await self.legacy_services["lancedb_handler"]()

            # Create document service with sync service integration
            doc_service = DocumentService(
                db_pool=None,
                lancedb_connection=lancedb_conn,
                sync_service=self.orchestration_service.sync_service
                if self.orchestration_service
                else None,
            )

            # Process document
            result = await doc_service.process_and_store_document(
                user_id=user_id,
                file_data=file_data,
                filename=filename,
                source_uri=source_uri,
                metadata=metadata,
                use_incremental_sync=True,  # Use sync system if available
            )

            return {
                "status": "success",
                "message": "Document processed with legacy service",
                "processing_method": "legacy_service",
                **result,
            }

        except Exception as e:
            logger.error(f"Legacy service processing failed: {e}")
            raise

    async def search_documents(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
        use_sync_system: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Search documents using either sync system or legacy service

        Args:
            user_id: User identifier
            query: Search query
            limit: Maximum results
            use_sync_system: Whether to use sync system (None = auto-detect)

        Returns:
            Search results
        """
        try:
            # For now, use legacy service for search
            # In future, this could use sync system's search capabilities

            if "document_service" not in self.legacy_services:
                return {
                    "status": "error",
                    "message": "Search service not available",
                    "code": "SEARCH_SERVICE_UNAVAILABLE",
                }

            DocumentService = self.legacy_services["document_service"]

            # Get LanceDB connection
            lancedb_conn = None
            if "lancedb_handler" in self.legacy_services:
                lancedb_conn = await self.legacy_services["lancedb_handler"]()

            doc_service = DocumentService(
                db_pool=None,
                lancedb_connection=lancedb_conn,
            )

            # Perform search
            result = await doc_service.search_documents(
                user_id=user_id,
                query=query,
                doc_type=None,  # Search all types
                limit=limit,
            )

            return {
                "status": "success",
                "search_method": "legacy_service",
                **result,
            }

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return {
                "status": "error",
                "message": f"Search failed: {str(e)}",
                "code": "SEARCH_ERROR",
            }

    async def migrate_existing_data(self, user_id: str) -> Dict[str, Any]:
        """
        Migrate existing data from legacy storage to sync system

        Args:
            user_id: User identifier

        Returns:
            Migration results
        """
        if self.migration_in_progress:
            return {
                "status": "error",
                "message": "Migration already in progress",
                "code": "MIGRATION_IN_PROGRESS",
            }

        if not self.config.migrate_existing_data:
            return {
                "status": "error",
                "message": "Data migration disabled in configuration",
                "code": "MIGRATION_DISABLED",
            }

        self.migration_in_progress = True

        try:
            logger.info(f"Starting data migration for user {user_id}")

            # This would scan existing LanceDB tables and re-process documents
            # through the sync system to enable incremental updates and S3 backup

            # Scan existing LanceDB tables for user documents
            try:
                import lancedb
                
                # Connect to existing databases
                lancedb_client = lancedb.connect("/tmp/lancedb")
                
                migration_stats = {
                    "documents_processed": 0,
                    "documents_migrated": 0,
                    "tables_processed": 0,
                    "errors": 0,
                }
                
                # Get all table names
                table_names = lancedb_client.table_names()
                logger.info(f"Found {len(table_names)} tables to migrate: {table_names}")
                
                for table_name in table_names:
                    try:
                        table = lancedb_client.open_table(table_name)
                        
                        # Get all documents from this table
                        documents = table.to_pandas()
                        
                        if len(documents) > 0:
                            logger.info(f"Processing table {table_name}: {len(documents)} documents")
                            migration_stats["tables_processed"] += 1
                            
                            # Process each document through sync system
                            for idx, doc in documents.iterrows():
                                try:
                                    migration_stats["documents_processed"] += 1
                                    
                                    # Extract document metadata
                                    doc_metadata = {
                                        'original_table': table_name,
                                        'doc_id': doc.get('doc_id', f"{table_name}_{idx}"),
                                        'title': doc.get('title', f"Document {idx}"),
                                        'source_type': 'lancedb_migration',
                                        'migration_timestamp': datetime.utcnow().isoformat(),
                                        'original_data': doc.to_dict()
                                    }
                                    
                                    # Create change record for sync system
                                    from .orchestration_service import SourceChange
                                    change = SourceChange(
                                        change_type='created',
                                        item_id=doc_metadata['doc_id'],
                                        item_path=f"migrated/{table_name}/{doc_metadata['doc_id']}",
                                        source_type='lancedb_migration',
                                        timestamp=doc_metadata['migration_timestamp'],
                                        metadata=doc_metadata
                                    )
                                    
                                    # Process through sync system (if available)
                                    if hasattr(self, 'orchestration_service'):
                                        await self.orchestration_service._handle_creation(change)
                                        migration_stats["documents_migrated"] += 1
                                    
                                except Exception as doc_error:
                                    logger.warning(f"Error processing document {idx} from {table_name}: {doc_error}")
                                    migration_stats["errors"] += 1
                                    continue
                        else:
                            logger.info(f"Table {table_name} is empty, skipping")
                            
                    except Exception as table_error:
                        logger.error(f"Error processing table {table_name}: {table_error}")
                        migration_stats["errors"] += 1
                        continue
                
                # Migration summary
                logger.info(
                    f"LanceDB migration completed for user {user_id}: "
                    f"Tables: {migration_stats['tables_processed']}, "
                    f"Docs Processed: {migration_stats['documents_processed']}, "
                    f"Docs Migrated: {migration_stats['documents_migrated']}, "
                    f"Errors: {migration_stats['errors']}"
                )
                
            except ImportError:
                logger.warning("LanceDB not available for migration")
                migration_stats["errors"] += 1
            except Exception as e:
                logger.error(f"LanceDB migration failed for user {user_id}: {e}")
                migration_stats["errors"] += 1

            logger.info(
                f"Data migration completed for user {user_id}: {migration_stats}"
            )

            return {
                "status": "success",
                "message": "Data migration completed",
                "migration_stats": migration_stats,
            }

        except Exception as e:
            logger.error(f"Data migration failed: {e}")
            return {
                "status": "error",
                "message": f"Data migration failed: {str(e)}",
                "code": "MIGRATION_ERROR",
            }
        finally:
            self.migration_in_progress = False

    async def get_integration_status(self) -> Dict[str, Any]:
        """
        Get integration service status

        Returns:
            Status information
        """
        status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sync_system_available": self.orchestration_service is not None,
            "legacy_services_available": len(self.legacy_services) > 0,
            "migration_in_progress": self.migration_in_progress,
            "config": {
                "enable_legacy_fallback": self.config.enable_legacy_fallback,
                "migrate_existing_data": self.config.migrate_existing_data,
                "sync_enabled_by_default": self.config.sync_enabled_by_default,
            },
        }

        # Add sync system status if available
        if self.orchestration_service:
            sync_status = await self.orchestration_service.get_system_status()
            status["sync_system_status"] = sync_status

        # Add legacy service availability
        status["legacy_services"] = list(self.legacy_services.keys())

        return status

    async def _health_monitoring_loop(self) -> None:
        """Health monitoring background task"""
        while True:
            try:
                await self._perform_health_check()
                await asyncio.sleep(self.config.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(self.config.health_check_interval)

    async def _perform_health_check(self) -> None:
        """Perform health check on all components"""
        try:
            status = await self.get_integration_status()

            # Check if critical components are healthy
            components_healthy = (
                status["sync_system_available"] or status["legacy_services_available"]
            )

            if not components_healthy:
                logger.warning("Integration service health check: degraded state")

        except Exception as e:
            logger.error(f"Health check failed: {e}")


# Factory function for easy service creation
def create_integration_service(
    enable_legacy_fallback: bool = True,
    migrate_existing_data: bool = False,
    sync_enabled_by_default: bool = True,
) -> IntegrationService:
    """Create an integration service with the specified configuration"""
    config = IntegrationConfig(
        enable_legacy_fallback=enable_legacy_fallback,
        migrate_existing_data=migrate_existing_data,
        sync_enabled_by_default=sync_enabled_by_default,
    )
    return IntegrationService(config)


# Global integration service instance
_integration_service: Optional[IntegrationService] = None


async def get_integration_service() -> IntegrationService:
    """Get or create the global integration service instance"""
    global _integration_service

    if _integration_service is None:
        _integration_service = create_integration_service()
        await _integration_service.initialize()

    return _integration_service


async def shutdown_integration_service() -> None:
    """Shutdown the global integration service"""
    global _integration_service

    if _integration_service:
        await _integration_service.shutdown()
        _integration_service = None
