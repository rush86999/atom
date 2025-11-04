"""
OneDrive Integration Service for ATOM Agent Memory System

This service provides integration between OneDrive and ATOM agent memory
through LanceDB ingestion pipeline.
"""

import os
import logging
import asyncio
from typing import Dict, List, Any, Optional

from .onedrive_document_processor import (
    OneDriveDocumentProcessor,
    OneDriveProcessorConfig,
    create_onedrive_processor,
    initialize_onedrive_processor_for_user,
)
from .sync.orchestration_service import OrchestrationService
from .sync.source_change_detector import (
    SourceConfig,
    SourceType,
)

logger = logging.getLogger(__name__)


class OneDriveIntegrationService:
    """
    Service for OneDrive integration with ATOM agent memory system
    """
    
    def __init__(self):
        self.processors: Dict[str, OneDriveDocumentProcessor] = {}
        self.orchestration_service: Optional[OrchestrationService] = None
        self.running = False
        self.health_check_task: Optional[asyncio.Task] = None
        
        logger.info("Initialized OneDriveIntegrationService")
    
    async def initialize(
        self, 
        orchestration_service: Optional[OrchestrationService] = None
    ) -> bool:
        """Initialize OneDrive integration service"""
        try:
            self.orchestration_service = orchestration_service
            self.running = True
            self.health_check_task = asyncio.create_task(self._health_monitoring_loop())
            
            logger.info("OneDriveIntegrationService initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize OneDriveIntegrationService: {e}")
            return False
    
    async def shutdown(self) -> None:
        """Shutdown OneDrive integration service gracefully"""
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
            logger.info("OneDriveIntegrationService shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during OneDrive service shutdown: {e}")
    
    async def add_user_onedrive_integration(
        self, 
        user_id: str, 
        config_overrides: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Add OneDrive integration for a user"""
        try:
            logger.info(f"Adding OneDrive integration for user: {user_id}")
            
            # Check if user already has integration
            if user_id in self.processors:
                return {
                    "status": "exists",
                    "message": "User already has OneDrive integration",
                    "user_id": user_id,
                }
            
            # Initialize processor for user
            processor = await initialize_onedrive_processor_for_user(
                user_id, config_overrides
            )
            
            if not processor:
                return {
                    "status": "failed",
                    "message": "Failed to initialize OneDrive processor",
                    "user_id": user_id,
                }
            
            # Store processor
            self.processors[user_id] = processor
            
            # Add to orchestration service if available
            if self.orchestration_service:
                await self._add_user_to_orchestration(user_id, processor)
            
            logger.info(f"Successfully added OneDrive integration for user: {user_id}")
            
            return {
                "status": "success",
                "message": "OneDrive integration added successfully",
                "user_id": user_id,
                "processor_config": {
                    "sync_interval": processor.config.sync_interval,
                    "max_files": processor.config.max_files,
                    "include_shared": processor.config.include_shared,
                }
            }
            
        except Exception as e:
            logger.error(f"Error adding OneDrive integration for user {user_id}: {e}")
            return {
                "status": "error",
                "message": f"Error adding integration: {str(e)}",
                "user_id": user_id,
            }
    
    async def remove_user_onedrive_integration(
        self, user_id: str
    ) -> Dict[str, Any]:
        """Remove OneDrive integration for a user"""
        try:
            logger.info(f"Removing OneDrive integration for user: {user_id}")
            
            # Check if user has integration
            if user_id not in self.processors:
                return {
                    "status": "not_found",
                    "message": "User does not have OneDrive integration",
                    "user_id": user_id,
                }
            
            # Stop and remove processor
            processor = self.processors[user_id]
            await processor.stop_processing()
            del self.processors[user_id]
            
            # Remove from orchestration service if available
            if self.orchestration_service:
                await self._remove_user_from_orchestration(user_id)
            
            logger.info(f"Successfully removed OneDrive integration for user: {user_id}")
            
            return {
                "status": "success",
                "message": "OneDrive integration removed successfully",
                "user_id": user_id,
            }
            
        except Exception as e:
            logger.error(f"Error removing OneDrive integration for user {user_id}: {e}")
            return {
                "status": "error",
                "message": f"Error removing integration: {str(e)}",
                "user_id": user_id,
            }
    
    async def get_user_onedrive_status(
        self, user_id: str
    ) -> Dict[str, Any]:
        """Get OneDrive integration status for a user"""
        try:
            # Check if user has integration
            if user_id not in self.processors:
                return {
                    "status": "not_integrated",
                    "message": "User does not have OneDrive integration",
                    "user_id": user_id,
                }
            
            processor = self.processors[user_id]
            
            # Get processor status
            status_info = {
                "status": "active",
                "message": "OneDrive integration is active",
                "user_id": user_id,
                "running": processor.running,
                "config": {
                    "sync_interval": processor.config.sync_interval,
                    "max_files": processor.config.max_files,
                    "include_shared": processor.config.include_shared,
                    "exclude_recycle_bin": processor.config.exclude_recycle_bin,
                },
                "processed_documents": len(processor.processed_docs),
            }
            
            # Check if Graph client is available
            if not processor.graph_client:
                status_info["status"] = "client_error"
                status_info["message"] = "Microsoft Graph client not available"
            else:
                # Test OneDrive connection
                try:
                    response = processor.graph_client.get('https://graph.microsoft.com/v1.0/me')
                    if response.status_code == 200:
                        user_data = response.json()
                        status_info["onedrive_connection"] = "active"
                        status_info["onedrive_user"] = {
                            "id": user_data.get("id"),
                            "displayName": user_data.get("displayName"),
                            "mail": user_data.get("mail"),
                        }
                    else:
                        status_info["onedrive_connection"] = "error"
                        status_info["onedrive_error"] = f"HTTP {response.status_code}"
                except Exception as e:
                    status_info["onedrive_connection"] = "error"
                    status_info["onedrive_error"] = str(e)
            
            return status_info
            
        except Exception as e:
            logger.error(f"Error getting OneDrive status for user {user_id}: {e}")
            return {
                "status": "error",
                "message": f"Error getting status: {str(e)}",
                "user_id": user_id,
            }
    
    async def _add_user_to_orchestration(
        self, user_id: str, processor: OneDriveDocumentProcessor
    ) -> None:
        """Add user to orchestration service"""
        try:
            if not self.orchestration_service:
                return
            
            # Create OneDrive source configuration
            source_config = SourceConfig(
                source_type=SourceType.NOTION,  # Reusing NOTION enum for document sources
                source_id=f"onedrive_user_{user_id}",
                config={
                    "user_id": user_id,
                    "processor": processor,
                    "service_type": "onedrive",
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
                f"onedrive_user_{user_id}"
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
                        if processor.running and processor.graph_client:
                            # Test connection
                            response = processor.graph_client.get('https://graph.microsoft.com/v1.0/me')
                            if response.status_code != 200:
                                unhealthy_users.append(user_id)
                        else:
                            unhealthy_users.append(user_id)
                            
                    except Exception as e:
                        logger.warning(f"User {user_id} processor unhealthy: {e}")
                        unhealthy_users.append(user_id)
                
                # Log health status
                total_users = len(self.processors)
                healthy_users = total_users - len(unhealthy_users)
                
                logger.info(
                    f"OneDrive integration health: {healthy_users}/{total_users} users healthy"
                )
                
                # Wait for next health check
                await asyncio.sleep(300)  # 5 minutes
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait before retry


# Global service instance
_onedrive_integration_service: Optional[OneDriveIntegrationService] = None


def get_onedrive_integration_service() -> OneDriveIntegrationService:
    """Get global OneDrive integration service instance"""
    global _onedrive_integration_service
    
    if _onedrive_integration_service is None:
        _onedrive_integration_service = OneDriveIntegrationService()
    
    return _onedrive_integration_service


async def initialize_onedrive_integration_service(
    orchestration_service: Optional[OrchestrationService] = None
) -> bool:
    """Initialize global OneDrive integration service"""
    service = get_onedrive_integration_service()
    return await service.initialize(orchestration_service)


async def shutdown_onedrive_integration_service() -> None:
    """Shutdown global OneDrive integration service"""
    service = get_onedrive_integration_service()
    await service.shutdown()