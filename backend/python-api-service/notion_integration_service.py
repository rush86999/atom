"""
Notion Integration Service for ATOM Agent Memory System

This service provides the main interface for Notion document processing
and integration with the LanceDB ingestion pipeline.
"""

import os
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from .notion_document_processor import (
    NotionDocumentProcessor,
    NotionProcessorConfig,
    create_notion_processor,
    initialize_notion_processor_for_user,
)
from .sync.orchestration_service import OrchestrationService
from .sync.source_change_detector import (
    SourceConfig,
    SourceType,
    SourceChange,
    ChangeType,
)

logger = logging.getLogger(__name__)


class NotionIntegrationService:
    """
    Main service for Notion integration with ATOM agent memory system
    """
    
    def __init__(self):
        self.processors: Dict[str, NotionDocumentProcessor] = {}
        self.orchestration_service: Optional[OrchestrationService] = None
        self.running = False
        self.health_check_task: Optional[asyncio.Task] = None
        
        logger.info("Initialized NotionIntegrationService")
    
    async def initialize(
        self, 
        orchestration_service: Optional[OrchestrationService] = None
    ) -> bool:
        """
        Initialize Notion integration service
        
        Args:
            orchestration_service: Orchestration service for document processing
        
        Returns:
            bool: True if initialization successful
        """
        try:
            # Set orchestration service
            self.orchestration_service = orchestration_service
            
            # Start health monitoring
            self.running = True
            self.health_check_task = asyncio.create_task(self._health_monitoring_loop())
            
            logger.info("NotionIntegrationService initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize NotionIntegrationService: {e}")
            return False
    
    async def shutdown(self) -> None:
        """Shutdown Notion integration service gracefully"""
        try:
            self.running = False
            
            # Stop all processors
            shutdown_tasks = []
            for user_id, processor in self.processors.items():
                shutdown_tasks.append(processor.stop_processing())
            
            # Wait for all to stop
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
            logger.info("NotionIntegrationService shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during Notion service shutdown: {e}")
    
    async def add_user_notion_integration(
        self, 
        user_id: str, 
        config_overrides: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Add Notion integration for a user
        
        Args:
            user_id: User identifier
            config_overrides: Configuration overrides
        
        Returns:
            Dictionary with result status
        """
        try:
            logger.info(f"Adding Notion integration for user: {user_id}")
            
            # Check if user already has integration
            if user_id in self.processors:
                return {
                    "status": "exists",
                    "message": "User already has Notion integration",
                    "user_id": user_id,
                }
            
            # Initialize processor for user
            processor = await initialize_notion_processor_for_user(
                user_id, config_overrides
            )
            
            if not processor:
                return {
                    "status": "failed",
                    "message": "Failed to initialize Notion processor",
                    "user_id": user_id,
                }
            
            # Store processor
            self.processors[user_id] = processor
            
            # Add to orchestration service if available
            if self.orchestration_service:
                await self._add_user_to_orchestration(user_id, processor)
            
            logger.info(f"Successfully added Notion integration for user: {user_id}")
            
            return {
                "status": "success",
                "message": "Notion integration added successfully",
                "user_id": user_id,
                "processor_config": {
                    "sync_interval": processor.config.sync_interval,
                    "include_pages": processor.config.include_pages,
                    "include_databases": processor.config.include_databases,
                    "exclude_archived": processor.config.exclude_archived,
                }
            }
            
        except Exception as e:
            logger.error(f"Error adding Notion integration for user {user_id}: {e}")
            return {
                "status": "error",
                "message": f"Error adding integration: {str(e)}",
                "user_id": user_id,
            }
    
    async def remove_user_notion_integration(
        self, user_id: str
    ) -> Dict[str, Any]:
        """
        Remove Notion integration for a user
        
        Args:
            user_id: User identifier
        
        Returns:
            Dictionary with result status
        """
        try:
            logger.info(f"Removing Notion integration for user: {user_id}")
            
            # Check if user has integration
            if user_id not in self.processors:
                return {
                    "status": "not_found",
                    "message": "User does not have Notion integration",
                    "user_id": user_id,
                }
            
            # Stop and remove processor
            processor = self.processors[user_id]
            await processor.stop_processing()
            del self.processors[user_id]
            
            # Remove from orchestration service if available
            if self.orchestration_service:
                await self._remove_user_from_orchestration(user_id)
            
            logger.info(f"Successfully removed Notion integration for user: {user_id}")
            
            return {
                "status": "success",
                "message": "Notion integration removed successfully",
                "user_id": user_id,
            }
            
        except Exception as e:
            logger.error(f"Error removing Notion integration for user {user_id}: {e}")
            return {
                "status": "error",
                "message": f"Error removing integration: {str(e)}",
                "user_id": user_id,
            }
    
    async def get_user_notion_status(
        self, user_id: str
    ) -> Dict[str, Any]:
        """
        Get Notion integration status for a user
        
        Args:
            user_id: User identifier
        
        Returns:
            Dictionary with status information
        """
        try:
            # Check if user has integration
            if user_id not in self.processors:
                return {
                    "status": "not_integrated",
                    "message": "User does not have Notion integration",
                    "user_id": user_id,
                }
            
            processor = self.processors[user_id]
            
            # Get processor status
            status_info = {
                "status": "active",
                "message": "Notion integration is active",
                "user_id": user_id,
                "running": processor.running,
                "config": {
                    "sync_interval": processor.config.sync_interval,
                    "include_pages": processor.config.include_pages,
                    "include_databases": processor.config.include_databases,
                    "exclude_archived": processor.config.exclude_archived,
                    "chunk_size": processor.config.chunk_size,
                },
                "processed_documents": len(processor.processed_docs),
                "last_sync": datetime.now(timezone.utc).isoformat(),
            }
            
            # Check if client is available
            if not processor.notion_client:
                status_info["status"] = "client_error"
                status_info["message"] = "Notion client not available"
            else:
                # Test Notion connection
                try:
                    test_response = processor.notion_client.users.me()
                    status_info["notion_connection"] = "active"
                    status_info["notion_user"] = {
                        "id": test_response.get("id"),
                        "name": test_response.get("name"),
                        "avatar_url": test_response.get("avatar_url"),
                    }
                except Exception as e:
                    status_info["notion_connection"] = "error"
                    status_info["notion_error"] = str(e)
            
            return status_info
            
        except Exception as e:
            logger.error(f"Error getting Notion status for user {user_id}: {e}")
            return {
                "status": "error",
                "message": f"Error getting status: {str(e)}",
                "user_id": user_id,
            }
    
    async def trigger_user_sync(
        self, 
        user_id: str, 
        sync_type: str = "full"
    ) -> Dict[str, Any]:
        """
        Trigger manual sync for a user
        
        Args:
            user_id: User identifier
            sync_type: Type of sync ("full" or "incremental")
        
        Returns:
            Dictionary with sync result
        """
        try:
            logger.info(f"Triggering {sync_type} sync for user: {user_id}")
            
            # Check if user has integration
            if user_id not in self.processors:
                return {
                    "status": "not_integrated",
                    "message": "User does not have Notion integration",
                    "user_id": user_id,
                }
            
            processor = self.processors[user_id]
            
            # Trigger sync cycle
            await processor._process_notion_documents()
            
            logger.info(f"Successfully triggered {sync_type} sync for user: {user_id}")
            
            return {
                "status": "success",
                "message": f"{sync_type.title()} sync completed successfully",
                "user_id": user_id,
                "sync_type": sync_type,
                "processed_documents": len(processor.processed_docs),
                "sync_timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error triggering sync for user {user_id}: {e}")
            return {
                "status": "error",
                "message": f"Error triggering sync: {str(e)}",
                "user_id": user_id,
            }
    
    async def get_integration_statistics(self) -> Dict[str, Any]:
        """
        Get overall integration statistics
        
        Returns:
            Dictionary with statistics
        """
        try:
            total_users = len(self.processors)
            active_users = sum(
                1 for processor in self.processors.values() 
                if processor.running
            )
            
            total_processed_docs = sum(
                len(processor.processed_docs) 
                for processor in self.processors.values()
            )
            
            statistics = {
                "status": "active" if self.running else "inactive",
                "total_users": total_users,
                "active_users": active_users,
                "total_processed_documents": total_processed_docs,
                "orchestration_service_active": self.orchestration_service is not None,
                "last_health_check": datetime.now(timezone.utc).isoformat(),
                "supported_features": {
                    "page_processing": True,
                    "database_processing": True,
                    "incremental_sync": True,
                    "lancedb_integration": True,
                    "embedding_generation": True,
                    "real_time_sync": True,
                }
            }
            
            # Add user-specific details
            user_details = {}
            for user_id, processor in self.processors.items():
                user_details[user_id] = {
                    "running": processor.running,
                    "processed_docs": len(processor.processed_docs),
                    "config": {
                        "sync_interval": processor.config.sync_interval,
                        "include_pages": processor.config.include_pages,
                        "include_databases": processor.config.include_databases,
                    }
                }
            
            statistics["user_details"] = user_details
            
            return statistics
            
        except Exception as e:
            logger.error(f"Error getting integration statistics: {e}")
            return {
                "status": "error",
                "message": f"Error getting statistics: {str(e)}",
            }
    
    async def _add_user_to_orchestration(
        self, user_id: str, processor: NotionDocumentProcessor
    ) -> None:
        """Add user to orchestration service"""
        try:
            if not self.orchestration_service:
                return
            
            # Create Notion source configuration
            source_config = SourceConfig(
                source_type=SourceType.NOTION,
                source_id=f"notion_user_{user_id}",
                config={
                    "user_id": user_id,
                    "processor": processor,
                    "include_pages": processor.config.include_pages,
                    "include_databases": processor.config.include_databases,
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
                SourceType.NOTION, f"notion_user_{user_id}"
            )
            
            logger.debug(f"Removed user {user_id} from orchestration service")
            
        except Exception as e:
            logger.error(f"Error removing user {user_id} from orchestration: {e}")
    
    async def _health_monitoring_loop(self) -> None:
        """Health monitoring loop for the integration service"""
        while self.running:
            try:
                # Check health of all processors
                unhealthy_users = []
                
                for user_id, processor in self.processors.items():
                    try:
                        # Check if processor is still healthy
                        if processor.running and processor.notion_client:
                            # Test connection
                            processor.notion_client.users.me()
                        else:
                            unhealthy_users.append(user_id)
                            
                    except Exception as e:
                        logger.warning(f"User {user_id} processor unhealthy: {e}")
                        unhealthy_users.append(user_id)
                
                # Log health status
                total_users = len(self.processors)
                healthy_users = total_users - len(unhealthy_users)
                
                logger.info(
                    f"Notion integration health: {healthy_users}/{total_users} users healthy"
                )
                
                # Wait for next health check
                await asyncio.sleep(300)  # 5 minutes
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait before retry


# Global service instance
_notion_integration_service: Optional[NotionIntegrationService] = None


def get_notion_integration_service() -> NotionIntegrationService:
    """
    Get the global Notion integration service instance
    
    Returns:
        NotionIntegrationService instance
    """
    global _notion_integration_service
    
    if _notion_integration_service is None:
        _notion_integration_service = NotionIntegrationService()
    
    return _notion_integration_service


async def initialize_notion_integration_service(
    orchestration_service: Optional[OrchestrationService] = None
) -> bool:
    """
    Initialize the global Notion integration service
    
    Args:
        orchestration_service: Orchestration service for integration
    
    Returns:
        bool: True if initialization successful
    """
    service = get_notion_integration_service()
    return await service.initialize(orchestration_service)


async def shutdown_notion_integration_service() -> None:
    """Shutdown the global Notion integration service"""
    service = get_notion_integration_service()
    await service.shutdown()