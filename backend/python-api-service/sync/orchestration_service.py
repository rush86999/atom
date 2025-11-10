"""
Orchestration Service for LanceDB Ingestion Pipeline

This service orchestrates the complete document ingestion pipeline:
1. Source change detection
2. Incremental document processing
3. Local LanceDB storage
4. S3 remote sync
"""

import os
import logging
import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
import signal
import sys

from .incremental_sync_service import (
    IncrementalSyncService,
    create_incremental_sync_service,
    SyncConfig,
)
from .source_change_detector import (
    SourceChangeDetector,
    create_source_change_detector,
    SourceChange,
    SourceConfig,
    SourceType,
    ChangeType,
)

logger = logging.getLogger(__name__)


@dataclass
class OrchestrationConfig:
    """Configuration for the orchestration service"""

    local_db_path: str = "data/lancedb"
    s3_bucket: Optional[str] = None
    s3_prefix: str = "lancedb-backup"
    sync_state_dir: str = "data/sync_state"
    health_check_interval: int = 60  # seconds
    max_concurrent_processing: int = 5
    enable_source_monitoring: bool = True


class DocumentProcessingError(Exception):
    """Custom exception for document processing errors"""

    pass


class OrchestrationService:
    """
    Main orchestration service for the LanceDB ingestion pipeline
    """

    def __init__(self, config: OrchestrationConfig):
        self.config = config
        self.running = False
        self.sync_service: Optional[IncrementalSyncService] = None
        self.change_detector: Optional[SourceChangeDetector] = None
        self.processing_semaphore = asyncio.Semaphore(config.max_concurrent_processing)
        self.health_check_task: Optional[asyncio.Task] = None

        # Initialize services
        self._initialize_services()

        # Set up signal handlers for graceful shutdown
        self._setup_signal_handlers()

        logger.info("Initialized OrchestrationService")

    def _initialize_services(self):
        """Initialize all component services"""
        try:
            # Initialize sync service
            sync_config = SyncConfig(
                local_db_path=self.config.local_db_path,
                s3_bucket=self.config.s3_bucket,
                s3_prefix=self.config.s3_prefix,
            )
            self.sync_service = create_incremental_sync_service(
                local_db_path=sync_config.local_db_path,
                s3_bucket=sync_config.s3_bucket,
                s3_prefix=sync_config.s3_prefix,
            )
            logger.info("Initialized IncrementalSyncService")

            # Initialize change detector if enabled
            if self.config.enable_source_monitoring:
                self.change_detector = create_source_change_detector(
                    state_dir=self.config.sync_state_dir
                )

                # Register change handler
                self.change_detector.add_change_handler(self._handle_source_change)
                logger.info("Initialized SourceChangeDetector with change handler")

        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            raise

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown"""

        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            asyncio.create_task(self.stop())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def start(self):
        """Start the orchestration service"""
        if self.running:
            logger.warning("Orchestration service already running")
            return

        self.running = True
        logger.info("Starting OrchestrationService...")

        try:
            # Start source monitoring if enabled
            if self.change_detector:
                await self.change_detector.start_monitoring()
                logger.info("Started source change monitoring")

            # Start health check task
            self.health_check_task = asyncio.create_task(self._health_check_loop())

            logger.info("OrchestrationService started successfully")

        except Exception as e:
            logger.error(f"Failed to start OrchestrationService: {e}")
            await self.stop()
            raise

    async def stop(self):
        """Stop the orchestration service gracefully"""
        if not self.running:
            return

        self.running = False
        logger.info("Stopping OrchestrationService...")

        try:
            # Stop source monitoring
            if self.change_detector:
                await self.change_detector.stop_monitoring()
                logger.info("Stopped source change monitoring")

            # Cancel health check task
            if self.health_check_task:
                self.health_check_task.cancel()
                try:
                    await self.health_check_task
                except asyncio.CancelledError:
                    pass
                logger.info("Stopped health check monitoring")

            logger.info("OrchestrationService stopped gracefully")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    async def _health_check_loop(self):
        """Periodic health check loop"""
        while self.running:
            try:
                await self._perform_health_check()
                await asyncio.sleep(self.config.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(self.config.health_check_interval)

    async def _perform_health_check(self):
        """Perform health check on all components"""
        health_status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service_running": self.running,
            "components": {},
        }

        # Check sync service
        if self.sync_service:
            sync_status = await self.sync_service.get_sync_status("system")
            health_status["components"]["sync_service"] = {
                "local_db_available": sync_status["local_db_available"],
                "s3_sync_available": sync_status["s3_sync_available"],
                "pending_syncs": sync_status["pending_syncs"],
                "failed_syncs": sync_status["failed_syncs"],
            }

        # Check change detector
        if self.change_detector:
            detector_status = await self.change_detector.get_monitoring_status()
            health_status["components"]["change_detector"] = {
                "running": detector_status["running"],
                "sources_monitored": detector_status["sources_monitored"],
                "active_tasks": detector_status["active_tasks"],
            }

        # Log health status (could also send to monitoring system)
        if not all(
            [
                health_status["components"]
                .get("sync_service", {})
                .get("local_db_available", False),
                health_status["components"]
                .get("change_detector", {})
                .get("running", False)
                if self.change_detector
                else True,
            ]
        ):
            logger.warning(f"Health check issues detected: {health_status}")

    def _handle_source_change(self, change: SourceChange):
        """Handle detected source changes"""
        asyncio.create_task(self._process_source_change(change))

    async def _process_source_change(self, change: SourceChange):
        """Process a detected source change"""
        async with self.processing_semaphore:
            try:
                logger.info(
                    f"Processing change: {change.source_type} {change.change_type} - {change.item_path}"
                )

                # Handle different change types
                if change.change_type == ChangeType.DELETED:
                    await self._handle_deletion(change)
                else:
                    await self._handle_creation_or_update(change)

                logger.info(f"Successfully processed change: {change.item_path}")

            except Exception as e:
                logger.error(f"Failed to process change {change.item_path}: {e}")
                # Could add retry logic here

    async def _handle_creation_or_update(self, change: SourceChange):
        """Handle document creation or update"""
        try:
            # Extract document content based on source type
            (
                document_data,
                chunks_with_embeddings,
            ) = await self._extract_document_content(change)

            if not document_data or not chunks_with_embeddings:
                logger.warning(f"No content extracted from {change.item_path}")
                return

            # Process document incrementally
            user_id = change.metadata.get("user_id", "default_user")
            result = await self.sync_service.process_document_incrementally(
                user_id=user_id,
                source_uri=change.item_path,
                document_data=document_data,
                chunks_with_embeddings=chunks_with_embeddings,
            )

            if result["status"] != "success":
                raise DocumentProcessingError(
                    f"Sync service error: {result.get('message', 'Unknown error')}"
                )

        except Exception as e:
            logger.error(f"Error handling creation/update for {change.item_path}: {e}")
            raise

    async def _handle_deletion(self, change: SourceChange):
        """Handle document deletion"""
        try:
            logger.info(f"Handling document deletion for: {change.item_path}")
            
            # Initialize LanceDB connection if not already done
            if not hasattr(self, 'lancedb_client'):
                try:
                    import lancedb
                    self.lancedb_client = lancedb.connect("/tmp/lancedb")
                    self.documents_table = self.lancedb_client.open_table("documents")
                except Exception as e:
                    logger.warning(f"LanceDB not available for deletion: {e}")
                    # Fallback: just log the deletion
                    logger.info(
                        f"Document deleted from source (keeping in index): {change.item_path}"
                    )
                    return
            
            # Delete document from LanceDB
            if hasattr(self, 'documents_table'):
                # Delete by document ID or path
                try:
                    # Try to find and delete by doc_id first
                    if change.item_id:
                        self.documents_table.delete(f"doc_id = '{change.item_id}'")
                        logger.info(f"Deleted document with ID {change.item_id} from LanceDB")
                    
                    # Also try to delete by path if ID deletion didn't work
                    try:
                        self.documents_table.delete(f"metadata.path = '{change.item_path}'")
                        logger.info(f"Deleted document with path {change.item_path} from LanceDB")
                    except:
                        pass  # Path might not exist in metadata
                    
                except Exception as e:
                    logger.warning(f"Failed to delete document from LanceDB: {e}")
                    # Continue with logging
            
            logger.info(
                f"Document deletion processed: {change.item_path} (ID: {change.item_id})"
            )
            
        except Exception as e:
            logger.error(f"Error handling document deletion for {change.item_path}: {e}")
            # Don't raise - we don't want deletion errors to stop the sync process

    async def _extract_document_content(
        self, change: SourceChange
    ) -> tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        """Extract document content and generate embeddings"""
        # This is a placeholder implementation
        # In a real system, this would:
        # 1. Download/read the document based on source type
        # 2. Extract text content
        # 3. Chunk the content
        # 4. Generate embeddings

        try:
            # Mock document data
            document_data = {
                "doc_id": change.item_id,
                "doc_type": change.source_type.value,
                "title": change.item_path.split("/")[-1],
                "metadata": change.metadata,
            }

            # Mock chunks with embeddings
            chunks_with_embeddings = [
                {
                    "text_content": f"Sample content from {change.item_path}",
                    "embedding": [0.1] * 1536,  # Mock embedding
                    "metadata": {"chunk_index": 0},
                }
            ]

            return document_data, chunks_with_embeddings

        except Exception as e:
            logger.error(f"Error extracting content from {change.item_path}: {e}")
            return None, []

    # Public API methods

    async def add_source(self, source_config: SourceConfig) -> Dict[str, Any]:
        """Add a source to monitor"""
        if not self.change_detector:
            return {"status": "error", "message": "Source monitoring disabled"}

        try:
            self.change_detector.add_source(source_config)
            return {
                "status": "success",
                "message": f"Added source: {source_config.source_id}",
            }
        except Exception as e:
            logger.error(f"Failed to add source: {e}")
            return {"status": "error", "message": str(e)}

    async def remove_source(
        self, source_type: SourceType, source_id: str
    ) -> Dict[str, Any]:
        """Remove a source from monitoring"""
        if not self.change_detector:
            return {"status": "error", "message": "Source monitoring disabled"}

        try:
            self.change_detector.remove_source(source_type, source_id)
            return {"status": "success", "message": f"Removed source: {source_id}"}
        except Exception as e:
            logger.error(f"Failed to remove source: {e}")
            return {"status": "error", "message": str(e)}

    async def force_source_scan(
        self, source_type: SourceType, source_id: str
    ) -> Dict[str, Any]:
        """Force a scan of a specific source"""
        if not self.change_detector:
            return {"status": "error", "message": "Source monitoring disabled"}

        try:
            changes = await self.change_detector.force_scan(source_type, source_id)
            return {
                "status": "success",
                "message": f"Scanned source {source_id}, found {len(changes)} changes",
                "changes_found": len(changes),
            }
        except Exception as e:
            logger.error(f"Failed to force scan source: {e}")
            return {"status": "error", "message": str(e)}

    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service_running": self.running,
            "config": {
                "local_db_path": self.config.local_db_path,
                "s3_bucket": self.config.s3_bucket,
                "enable_source_monitoring": self.config.enable_source_monitoring,
            },
        }

        # Add sync service status
        if self.sync_service:
            sync_status = await self.sync_service.get_sync_status("system")
            status["sync_service"] = sync_status

        # Add change detector status
        if self.change_detector:
            detector_status = await self.change_detector.get_monitoring_status()
            status["change_detector"] = detector_status

        return status

    async def cleanup_failed_syncs(self, user_id: str = "system") -> Dict[str, Any]:
        """Clean up failed sync attempts"""
        if not self.sync_service:
            return {"status": "error", "message": "Sync service not available"}

        try:
            result = await self.sync_service.cleanup_failed_syncs(user_id)
            return result
        except Exception as e:
            logger.error(f"Failed to cleanup failed syncs: {e}")
            return {"status": "error", "message": str(e)}


# Factory function for easy service creation
def create_orchestration_service(
    local_db_path: str = "data/lancedb",
    s3_bucket: Optional[str] = None,
    s3_prefix: str = "lancedb-backup",
    sync_state_dir: str = "data/sync_state",
    enable_source_monitoring: bool = True,
) -> OrchestrationService:
    """Create an orchestration service with the specified configuration"""
    config = OrchestrationConfig(
        local_db_path=local_db_path,
        s3_bucket=s3_bucket,
        s3_prefix=s3_prefix,
        sync_state_dir=sync_state_dir,
        enable_source_monitoring=enable_source_monitoring,
    )
    return OrchestrationService(config)


# Example usage and main entry point
async def main():
    """Example main function demonstrating usage"""
    # Create orchestration service
    service = create_orchestration_service(
        local_db_path="data/lancedb",
        s3_bucket=os.environ.get("S3_BUCKET"),
        enable_source_monitoring=True,
    )

    try:
        # Start the service
        await service.start()

        # Add example sources
        local_source = SourceConfig(
            source_type=SourceType.LOCAL_FILESYSTEM,
            source_id="documents_folder",
            config={
                "watch_paths": ["/path/to/documents"],
                "file_patterns": ["*.pdf", "*.docx", "*.txt"],
            },
            poll_interval=300,
        )

        await service.add_source(local_source)

        # Keep the service running
        while service.running:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        await service.stop()


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run the service
    asyncio.run(main())
