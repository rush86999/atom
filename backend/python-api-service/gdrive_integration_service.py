"""
Google Drive Integration Service for ATOM Agent Memory System

This service provides integration between Google Drive and ATOM agent memory
through LanceDB ingestion pipeline.
"""

import os
import logging
import asyncio
from typing import Dict, List, Any, Optional

from .google_drive_document_processor import (
    GoogleDriveDocumentProcessor,
    GoogleDriveProcessorConfig,
    create_google_drive_processor,
    initialize_google_drive_processor_for_user,
)
from .sync.orchestration_service import OrchestrationService
from .sync.source_change_detector import (
    SourceConfig,
    SourceType,
)

logger = logging.getLogger(__name__)


class GoogleDriveIntegrationService:
    """
    Service for Google Drive integration with ATOM agent memory system
    """
    
    def __init__(self):
        self.processors: Dict[str, GoogleDriveDocumentProcessor] = {}
        self.orchestration_service: Optional[OrchestrationService] = None
        self.running = False
        self.health_check_task: Optional[asyncio.Task] = None
        
        logger.info("Initialized GoogleDriveIntegrationService")
    
    async def initialize(
        self, 
        orchestration_service: Optional[OrchestrationService] = None
    ) -> bool:
        """Initialize Google Drive integration service"""
        try:
            self.orchestration_service = orchestration_service
            self.running = True
            self.health_check_task = asyncio.create_task(self._health_monitoring_loop())
            
            logger.info("GoogleDriveIntegrationService initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize GoogleDriveIntegrationService: {e}")
            return False
    
    async def shutdown(self) -> None:
        """Shutdown Google Drive integration service gracefully"""
        try:
            self.running = False
            
            # Stop all processors
            shutdown_tasks = []
            for user_id, processor in self.processors.items():
                shutdown_tasks.append(processor.stop_processing())
            
            if shutdown_tasks:
                await asyncio.gather(*shutdown_tasks, return_exceptions=True)
            
            # Stop health monitoring
            if self.health_check_task:
                self.health_check_task.cancel()
                try:
                    await self.health_check_task
                except asyncio.CancelledError:
                    pass
            
            self.processors.clear()
            logger.info("GoogleDriveIntegrationService shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during Google Drive service shutdown: {e}")
    
    async def add_user_gdrive_integration(
        self, 
        user_id: str, 
        config_overrides: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Add Google Drive integration for a user"""
        try:
            logger.info(f"Adding Google Drive integration for user: {user_id}")
            
            # Check if user already has integration
            if user_id in self.processors:
                return {
                    "status": "exists",
                    "message": "User already has Google Drive integration",
                    "user_id": user_id,
                }
            
            # Initialize processor for user
            processor = await initialize_google_drive_processor_for_user(
                user_id, config_overrides
            )
            
            if not processor:
                return {
                    "status": "failed",
                    "message": "Failed to initialize Google Drive processor",
                    "user_id": user_id,
                }
            
            # Store processor
            self.processors[user_id] = processor
            
            # Add to orchestration service if available
            if self.orchestration_service:
                await self._add_user_to_orchestration(user_id, processor)
            
            logger.info(f"Successfully added Google Drive integration for user: {user_id}")
            
            return {
                "status": "success",
                "message": "Google Drive integration added successfully",
                "user_id": user_id,
                "processor_config": {
                    "sync_interval": processor.config.sync_interval,
                    "max_files": processor.config.max_files,
                    "include_shared": processor.config.include_shared,
                }
            }
            
        except Exception as e:
            logger.error(f"Error adding Google Drive integration for user {user_id}: {e}")
            return {
                "status": "error",
                "message": f"Error adding integration: {str(e)}",
                "user_id": user_id,
            }
    
    async def remove_user_gdrive_integration(
        self, user_id: str
    ) -> Dict[str, Any]:
        """Remove Google Drive integration for a user"""
        try:
            logger.info(f"Removing Google Drive integration for user: {user_id}")
            
            # Check if user has integration
            if user_id not in self.processors:
                return {
                    "status": "not_found",
                    "message": "User does not have Google Drive integration",
                    "user_id": user_id,
                }
            
            # Stop and remove processor
            processor = self.processors[user_id]
            await processor.stop_processing()
            del self.processors[user_id]
            
            # Remove from orchestration service if available
            if self.orchestration_service:
                await self._remove_user_from_orchestration(user_id)
            
            logger.info(f"Successfully removed Google Drive integration for user: {user_id}")
            
            return {
                "status": "success",
                "message": "Google Drive integration removed successfully",
                "user_id": user_id,
            }
            
        except Exception as e:
            logger.error(f"Error removing Google Drive integration for user {user_id}: {e}")
            return {
                "status": "error",
                "message": f"Error removing integration: {str(e)}",
                "user_id": user_id,
            }
    
    async def get_user_gdrive_status(
        self, user_id: str
    ) -> Dict[str, Any]:
        """Get Google Drive integration status for a user"""
        try:
            # Check if user has integration
            if user_id not in self.processors:
                return {
                    "status": "not_integrated",
                    "message": "User does not have Google Drive integration",
                    "user_id": user_id,
                }
            
            processor = self.processors[user_id]
            
            # Get processor status
            status_info = {
                "status": "active",
                "message": "Google Drive integration is active",
                "user_id": user_id,
                "running": processor.running,
                "processed_documents": len(processor.processed_docs),
                "config": {
                    "sync_interval": processor.config.sync_interval,
                    "max_files": processor.config.max_files,
                    "include_shared": processor.config.include_shared,
                }
            }
            
            # Check if drive service is available
            if not processor.drive_service:
                status_info["status"] = "service_error"
                status_info["message"] = "Google Drive service not available"
            else:
                # Test Google Drive connection
                try:
                    test_response = processor.drive_service.about().get(fields="user, storageQuota").execute()
                    status_info["gdrive_connection"] = "active"
                    status_info["gdrive_user"] = {
                        "emailAddress": test_response.get("user", {}).get("emailAddress"),
                        "displayName": test_response.get("user", {}).get("displayName"),
                    }
                    status_info["storage_info"] = test_response.get("storageQuota", {})
                except Exception as e:
                    status_info["gdrive_connection"] = "error"
                    status_info["gdrive_error"] = str(e)
            
            return status_info
            
        except Exception as e:
            logger.error(f"Error getting Google Drive status for user {user_id}: {e}")
            return {
                "status": "error",
                "message": f"Error getting status: {str(e)}",
                "user_id": user_id,
            }
    
    async def _add_user_to_orchestration(
        self, user_id: str, processor: GoogleDriveDocumentProcessor
    ) -> None:
        """Add user to orchestration service"""
        try:
            if not self.orchestration_service:
                return
            
            # Create Google Drive source configuration
            source_config = SourceConfig(
                source_type=SourceType.NOTION,  # Reusing NOTION enum for document sources
                source_id=f"gdrive_user_{user_id}",
                config={
                    "user_id": user_id,
                    "processor": processor,
                    "service_type": "google_drive",
                },
                poll_interval=processor.config.sync_interval,
            )
            
            # Add to orchestration service
            self.orchestration_service.change_detector.add_source(source_config)
            
            logger.debug(f"Added user {user_id} to orchestration service")
            
        except Exception as e:
            logger.error(f"Error adding user {user_id} to orchestration: {e}")
    
    async def _remove_user_from_orchestration(self, user_id: str) -> None:
        """Remove user from orchestration service"""
        try:
            if not self.orchestration_service:
                return
            
            # Remove from orchestration service
            self.orchestration_service.change_detector.remove_source(
                SourceType.NOTION,  # Reusing NOTION enum
                f"gdrive_user_{user_id}"
            )
            
            logger.debug(f"Removed user {user_id} from orchestration service")
            
        except Exception as e:
            logger.error(f"Error removing user {user_id} from orchestration: {e}")
    
    async def _health_monitoring_loop(self) -> None:
        """Health monitoring loop for integration service"""
        while self.running:
            try:
                # Check health of all processors
                unhealthy_users = []
                
                for user_id, processor in self.processors.items():
                    try:
                        # Check if processor is still healthy
                        if processor.running and processor.drive_service:
                            # Test connection
                            processor.drive_service.about().get(fields="user").execute()
                        else:
                            unhealthy_users.append(user_id)
                            
                    except Exception as e:
                        logger.warning(f"User {user_id} processor unhealthy: {e}")
                        unhealthy_users.append(user_id)
                
                # Log health status
                total_users = len(self.processors)
                healthy_users = total_users - len(unhealthy_users)
                
                logger.info(
                    f"Google Drive integration health: {healthy_users}/{total_users} users healthy"
                )
                
                # Wait for next health check
                await asyncio.sleep(300)  # 5 minutes
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait before retry


# Global service instance
_gdrive_integration_service: Optional[GoogleDriveIntegrationService] = None


def get_gdrive_integration_service() -> GoogleDriveIntegrationService:
    """Get global Google Drive integration service instance"""
    global _gdrive_integration_service
    
    if _gdrive_integration_service is None:
        _gdrive_integration_service = GoogleDriveIntegrationService()
    
    return _gdrive_integration_service


async def initialize_gdrive_integration_service(
    orchestration_service: Optional[OrchestrationService] = None
) -> bool:
    """Initialize global Google Drive integration service"""
    service = get_gdrive_integration_service()
    return await service.initialize(orchestration_service)


async def shutdown_gdrive_integration_service() -> None:
    """Shutdown global Google Drive integration service"""
    service = get_gdrive_integration_service()
    await service.shutdown()