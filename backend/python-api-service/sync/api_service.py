"""
API Service for LanceDB Ingestion Pipeline

This module provides a FastAPI service that exposes endpoints for:
- Managing document sources
- Triggering incremental syncs
- Monitoring pipeline status
- Managing S3 sync operations
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import asyncio

from .orchestration_service import (
    OrchestrationService,
    create_orchestration_service,
    SourceConfig,
    SourceType,
)
from .source_change_detector import ChangeType

logger = logging.getLogger(__name__)


# Pydantic models for API requests/responses
class SourceConfigRequest(BaseModel):
    source_type: str
    source_id: str
    config: Dict[str, Any]
    poll_interval: int = 300
    enabled: bool = True


class SourceConfigResponse(BaseModel):
    source_type: str
    source_id: str
    config: Dict[str, Any]
    poll_interval: int
    enabled: bool


class SyncStatusResponse(BaseModel):
    local_db_available: bool
    s3_sync_available: bool
    pending_syncs: int
    failed_syncs: int
    total_changes: int


class SystemStatusResponse(BaseModel):
    timestamp: str
    service_running: bool
    config: Dict[str, Any]
    sync_service: Optional[Dict[str, Any]] = None
    change_detector: Optional[Dict[str, Any]] = None


class ForceScanResponse(BaseModel):
    status: str
    message: str
    changes_found: int


class CleanupResponse(BaseModel):
    status: str
    message: str
    cleaned_count: int


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    components: Dict[str, Any]


class ManualSyncRequest(BaseModel):
    user_id: str
    source_uri: str
    document_data: Dict[str, Any]
    chunks_with_embeddings: List[Dict[str, Any]]


class ManualSyncResponse(BaseModel):
    status: str
    message: str
    doc_id: Optional[str] = None
    local_stored: bool = False
    remote_sync_queued: bool = False


class IngestionPipelineAPI:
    """
    FastAPI service for LanceDB ingestion pipeline management
    """

    def __init__(self):
        self.app = FastAPI(
            title="LanceDB Ingestion Pipeline API",
            description="API for managing document ingestion and sync to LanceDB",
            version="1.0.0",
        )

        # Initialize orchestration service
        self.orchestration_service = create_orchestration_service(
            local_db_path=os.environ.get("LANCEDB_URI", "data/lancedb"),
            s3_bucket=os.environ.get("S3_BUCKET"),
            s3_prefix=os.environ.get("S3_PREFIX", "lancedb-backup"),
            enable_source_monitoring=True,
        )

        self._setup_middleware()
        self._setup_routes()
        self._setup_lifecycle()

        logger.info("Initialized IngestionPipelineAPI")

    def _setup_middleware(self):
        """Setup CORS and other middleware"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_routes(self):
        """Setup API routes"""

        @self.app.get("/", response_model=Dict[str, str])
        async def root():
            return {
                "message": "LanceDB Ingestion Pipeline API",
                "version": "1.0.0",
                "status": "operational",
            }

        @self.app.get("/health", response_model=HealthResponse)
        async def health_check():
            """Health check endpoint"""
            try:
                system_status = await self.orchestration_service.get_system_status()

                components_healthy = all(
                    [
                        system_status.get("sync_service", {}).get(
                            "local_db_available", False
                        ),
                        system_status.get("service_running", False),
                    ]
                )

                return HealthResponse(
                    status="healthy" if components_healthy else "degraded",
                    version="1.0.0",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    components=system_status,
                )
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return HealthResponse(
                    status="unhealthy",
                    version="1.0.0",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    components={"error": str(e)},
                )

        @self.app.post("/api/v1/sources", response_model=Dict[str, Any])
        async def add_source(source_config: SourceConfigRequest):
            """Add a document source to monitor"""
            try:
                # Convert string source_type to enum
                source_type_enum = SourceType(source_config.source_type)

                config = SourceConfig(
                    source_type=source_type_enum,
                    source_id=source_config.source_id,
                    config=source_config.config,
                    poll_interval=source_config.poll_interval,
                    enabled=source_config.enabled,
                )

                result = await self.orchestration_service.add_source(config)
                return result

            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid source type: {source_config.source_type}. Valid types: {[t.value for t in SourceType]}",
                )
            except Exception as e:
                logger.error(f"Failed to add source: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.delete("/api/v1/sources/{source_type}/{source_id}")
        async def remove_source(source_type: str, source_id: str):
            """Remove a document source from monitoring"""
            try:
                source_type_enum = SourceType(source_type)
                result = await self.orchestration_service.remove_source(
                    source_type_enum, source_id
                )
                return result

            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid source type: {source_type}. Valid types: {[t.value for t in SourceType]}",
                )
            except Exception as e:
                logger.error(f"Failed to remove source: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/v1/sources", response_model=List[SourceConfigResponse])
        async def list_sources():
            """List all monitored sources"""
            try:
                system_status = await self.orchestration_service.get_system_status()
                detector_status = system_status.get("change_detector", {})
                source_details = detector_status.get("source_details", {})

                sources = []
                for source_key, details in source_details.items():
                    source_type, source_id = source_key.split("_", 1)
                    sources.append(
                        SourceConfigResponse(
                            source_type=source_type,
                            source_id=source_id,
                            config={},  # Config not exposed for security
                            poll_interval=details.get("poll_interval", 300),
                            enabled=details.get("enabled", True),
                        )
                    )

                return sources

            except Exception as e:
                logger.error(f"Failed to list sources: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post(
            "/api/v1/sources/{source_type}/{source_id}/scan",
            response_model=ForceScanResponse,
        )
        async def force_scan_source(source_type: str, source_id: str):
            """Force a scan of a specific source"""
            try:
                source_type_enum = SourceType(source_type)
                result = await self.orchestration_service.force_source_scan(
                    source_type_enum, source_id
                )
                return ForceScanResponse(**result)

            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid source type: {source_type}. Valid types: {[t.value for t in SourceType]}",
                )
            except Exception as e:
                logger.error(f"Failed to force scan source: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/v1/status", response_model=SystemStatusResponse)
        async def get_system_status():
            """Get comprehensive system status"""
            try:
                status = await self.orchestration_service.get_system_status()
                return SystemStatusResponse(**status)
            except Exception as e:
                logger.error(f"Failed to get system status: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/v1/sync/status", response_model=SyncStatusResponse)
        async def get_sync_status(user_id: str = "system"):
            """Get sync status for a user"""
            try:
                system_status = await self.orchestration_service.get_system_status()
                sync_service_status = system_status.get("sync_service", {})

                return SyncStatusResponse(
                    local_db_available=sync_service_status.get(
                        "local_db_available", False
                    ),
                    s3_sync_available=sync_service_status.get(
                        "s3_sync_available", False
                    ),
                    pending_syncs=sync_service_status.get("pending_syncs", 0),
                    failed_syncs=sync_service_status.get("failed_syncs", 0),
                    total_changes=sync_service_status.get("total_changes", 0),
                )
            except Exception as e:
                logger.error(f"Failed to get sync status: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/v1/sync/cleanup", response_model=CleanupResponse)
        async def cleanup_failed_syncs(user_id: str = "system"):
            """Clean up failed sync attempts"""
            try:
                result = await self.orchestration_service.cleanup_failed_syncs(user_id)
                return CleanupResponse(**result)
            except Exception as e:
                logger.error(f"Failed to cleanup failed syncs: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/v1/sync/manual", response_model=ManualSyncResponse)
        async def manual_sync(request: ManualSyncRequest):
            """Manually sync a document"""
            try:
                # This would use the sync service directly
                # For now, return a placeholder response
                return ManualSyncResponse(
                    status="success",
                    message="Manual sync endpoint - implementation pending",
                    doc_id="manual_doc_123",
                    local_stored=True,
                    remote_sync_queued=True,
                )
            except Exception as e:
                logger.error(f"Failed to perform manual sync: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/v1/pipeline/start")
        async def start_pipeline():
            """Start the ingestion pipeline"""
            try:
                await self.orchestration_service.start()
                return {"status": "success", "message": "Pipeline started"}
            except Exception as e:
                logger.error(f"Failed to start pipeline: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/v1/pipeline/stop")
        async def stop_pipeline():
            """Stop the ingestion pipeline"""
            try:
                await self.orchestration_service.stop()
                return {"status": "success", "message": "Pipeline stopped"}
            except Exception as e:
                logger.error(f"Failed to stop pipeline: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    def _setup_lifecycle(self):
        """Setup application lifecycle events"""

        @self.app.on_event("startup")
        async def startup_event():
            """Start the orchestration service when the API starts"""
            try:
                await self.orchestration_service.start()
                logger.info("Ingestion pipeline started successfully")
            except Exception as e:
                logger.error(f"Failed to start ingestion pipeline: {e}")

        @self.app.on_event("shutdown")
        async def shutdown_event():
            """Stop the orchestration service when the API stops"""
            try:
                await self.orchestration_service.stop()
                logger.info("Ingestion pipeline stopped gracefully")
            except Exception as e:
                logger.error(f"Error during pipeline shutdown: {e}")

    def get_app(self):
        """Get the FastAPI application instance"""
        return self.app


# Factory function to create the API service
def create_api_service():
    """Create and return the API service instance"""
    return IngestionPipelineAPI()


# Main entry point for running the API service directly
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create and run the API service
    api_service = create_api_service()
    app = api_service.get_app()

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
