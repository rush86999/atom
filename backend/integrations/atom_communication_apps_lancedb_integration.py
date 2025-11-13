"""
ATOM Communication Apps - LanceDB Ingestion Integration
Add LanceDB memory ingestion option to all communication apps
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
import logging
from integrations.atom_communication_ingestion_pipeline import (
    CommunicationAppType,
    IngestionConfig,
    memory_manager,
    ingestion_pipeline
)

logger = logging.getLogger(__name__)

class CommunicationAppIngestionIntegration:
    """Integration layer for all communication apps with LanceDB ingestion"""
    
    def __init__(self):
        self.router = APIRouter(prefix="/api/memory/ingestion", tags=["Communication Memory"])
        self.setup_routes()
        self._initialize_default_configs()
    
    def _initialize_default_configs(self):
        """Initialize default ingestion configurations for all apps"""
        default_configs = {
            "whatsapp": IngestionConfig(
                app_type=CommunicationAppType.WHATSAPP,
                enabled=True,
                real_time=True,
                batch_size=50,
                ingest_attachments=True,
                embed_content=True,
                retention_days=365,
                vector_dim=768
            ),
            "slack": IngestionConfig(
                app_type=CommunicationAppType.SLACK,
                enabled=True,
                real_time=True,
                batch_size=100,
                ingest_attachments=True,
                embed_content=True,
                retention_days=365,
                vector_dim=768
            ),
            "email": IngestionConfig(
                app_type=CommunicationAppType.EMAIL,
                enabled=True,
                real_time=False,
                batch_size=200,
                ingest_attachments=True,
                embed_content=True,
                retention_days=365,
                vector_dim=768
            ),
            "telegram": IngestionConfig(
                app_type=CommunicationAppType.TELEGRAM,
                enabled=True,
                real_time=True,
                batch_size=50,
                ingest_attachments=True,
                embed_content=True,
                retention_days=365,
                vector_dim=768
            ),
            "discord": IngestionConfig(
                app_type=CommunicationAppType.DISCORD,
                enabled=True,
                real_time=True,
                batch_size=100,
                ingest_attachments=True,
                embed_content=True,
                retention_days=365,
                vector_dim=768
            ),
            "sms": IngestionConfig(
                app_type=CommunicationAppType.SMS,
                enabled=True,
                real_time=True,
                batch_size=50,
                ingest_attachments=False,
                embed_content=True,
                retention_days=180,
                vector_dim=768
            ),
            "calls": IngestionConfig(
                app_type=CommunicationAppType.CALLS,
                enabled=True,
                real_time=True,
                batch_size=50,
                ingest_attachments=False,
                embed_content=True,
                retention_days=365,
                vector_dim=768
            ),
            "microsoft_teams": IngestionConfig(
                app_type=CommunicationAppType.MICROSOFT_TEAMS,
                enabled=True,
                real_time=True,
                batch_size=100,
                ingest_attachments=True,
                embed_content=True,
                retention_days=365,
                vector_dim=768
            ),
            "zoom": IngestionConfig(
                app_type=CommunicationAppType.ZOOM,
                enabled=True,
                real_time=False,
                batch_size=50,
                ingest_attachments=True,
                embed_content=True,
                retention_days=365,
                vector_dim=768
            ),
            "notion": IngestionConfig(
                app_type=CommunicationAppType.NOTION,
                enabled=True,
                real_time=False,
                batch_size=100,
                ingest_attachments=True,
                embed_content=True,
                retention_days=365,
                vector_dim=768
            ),
            "linear": IngestionConfig(
                app_type=CommunicationAppType.LINEAR,
                enabled=True,
                real_time=False,
                batch_size=50,
                ingest_attachments=False,
                embed_content=True,
                retention_days=365,
                vector_dim=768
            ),
            "outlook": IngestionConfig(
                app_type=CommunicationAppType.OUTLOOK,
                enabled=True,
                real_time=False,
                batch_size=200,
                ingest_attachments=True,
                embed_content=True,
                retention_days=365,
                vector_dim=768
            ),
            "gmail": IngestionConfig(
                app_type=CommunicationAppType.GMAIL,
                enabled=True,
                real_time=False,
                batch_size=200,
                ingest_attachments=True,
                embed_content=True,
                retention_days=365,
                vector_dim=768
            ),
            "salesforce": IngestionConfig(
                app_type=CommunicationAppType.SALESFORCE,
                enabled=True,
                real_time=False,
                batch_size=100,
                ingest_attachments=True,
                embed_content=True,
                retention_days=365,
                vector_dim=768
            ),
            "asana": IngestionConfig(
                app_type=CommunicationAppType.ASANA,
                enabled=True,
                real_time=False,
                batch_size=50,
                ingest_attachments=True,
                embed_content=True,
                retention_days=365,
                vector_dim=768
            ),
            "dropbox": IngestionConfig(
                app_type=CommunicationAppType.DROPBOX,
                enabled=True,
                real_time=False,
                batch_size=100,
                ingest_attachments=True,
                embed_content=True,
                retention_days=365,
                vector_dim=768
            ),
            "box": IngestionConfig(
                app_type=CommunicationAppType.BOX,
                enabled=True,
                real_time=False,
                batch_size=100,
                ingest_attachments=True,
                embed_content=True,
                retention_days=365,
                vector_dim=768
            ),
            "tableau": IngestionConfig(
                app_type=CommunicationAppType.TABLEAU,
                enabled=True,
                real_time=False,
                batch_size=50,
                ingest_attachments=False,
                embed_content=True,
                retention_days=365,
                vector_dim=768
            )
        }
        
        # Configure all apps
        for app_name, config in default_configs.items():
            ingestion_pipeline.configure_app(config.app_type, config)
    
    def setup_routes(self):
        """Setup API routes for communication ingestion"""
        
        @self.router.get("/status")
        async def get_ingestion_status():
            """Get overall ingestion status"""
            try:
                # Initialize memory manager if not already done
                if not memory_manager.db:
                    memory_manager.initialize()
                
                stats = ingestion_pipeline.get_ingestion_stats()
                
                return {
                    "status": "active",
                    "timestamp": datetime.now().isoformat(),
                    "memory_database": "LanceDB",
                    "total_apps_configured": len(stats.get("configured_apps", [])),
                    "active_streams": stats.get("active_streams", []),
                    "total_messages_ingested": stats.get("total_messages", 0),
                    "app_statistics": stats.get("app_stats", {}),
                    "memory_database_path": str(memory_manager.db_path)
                }
            except Exception as e:
                logger.error(f"Error getting ingestion status: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/apps")
        async def get_configured_apps():
            """Get list of configured communication apps"""
            try:
                apps = []
                for app_type in CommunicationAppType:
                    apps.append({
                        "id": app_type.value,
                        "name": app_type.value.replace("_", " ").title(),
                        "type": "communication",
                        "supports_ingestion": True,
                        "supports_real_time": True,
                        "supports_embeddings": True
                    })
                
                return {
                    "apps": apps,
                    "total": len(apps),
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                logger.error(f"Error getting configured apps: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/apps/{app_id}")
        async def get_app_ingestion_config(app_id: str):
            """Get ingestion configuration for specific app"""
            try:
                app_type = CommunicationAppType(app_id)
                config = ingestion_pipeline.ingestion_configs.get(app_id)
                
                if not config:
                    raise HTTPException(status_code=404, detail=f"App {app_id} not configured")
                
                return {
                    "app_id": app_id,
                    "app_name": app_id.replace("_", " ").title(),
                    "config": config,
                    "timestamp": datetime.now().isoformat()
                }
            except ValueError:
                raise HTTPException(status_code=404, detail=f"Invalid app_id: {app_id}")
            except Exception as e:
                logger.error(f"Error getting app config: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/ingest/{app_id}")
        async def ingest_message(app_id: str, message_data: Dict[str, Any]):
            """Ingest single message from communication app"""
            try:
                # Validate app_id
                CommunicationAppType(app_id)
                
                # Initialize memory manager if needed
                if not memory_manager.db:
                    memory_manager.initialize()
                
                # Ingest message
                success = ingestion_pipeline.ingest_message(app_id, message_data)
                
                if success:
                    return {
                        "success": True,
                        "message": f"Message from {app_id} ingested successfully",
                        "app_id": app_id,
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    raise HTTPException(status_code=500, detail="Failed to ingest message")
                    
            except ValueError:
                raise HTTPException(status_code=404, detail=f"Invalid app_id: {app_id}")
            except Exception as e:
                logger.error(f"Error ingesting message: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/ingest/{app_id}/batch")
        async def ingest_messages_batch(app_id: str, messages: List[Dict[str, Any]]):
            """Ingest batch of messages from communication app"""
            try:
                # Validate app_id
                CommunicationAppType(app_id)
                
                # Initialize memory manager if needed
                if not memory_manager.db:
                    memory_manager.initialize()
                
                # Ingest batch
                success_count = 0
                for message in messages:
                    if ingestion_pipeline.ingest_message(app_id, message):
                        success_count += 1
                
                return {
                    "success": True,
                    "message": f"Batch ingestion completed for {app_id}",
                    "app_id": app_id,
                    "total_messages": len(messages),
                    "success_count": success_count,
                    "failure_count": len(messages) - success_count,
                    "timestamp": datetime.now().isoformat()
                }
                    
            except ValueError:
                raise HTTPException(status_code=404, detail=f"Invalid app_id: {app_id}")
            except Exception as e:
                logger.error(f"Error ingesting batch: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/stream/start/{app_id}")
        async def start_real_time_stream(app_id: str):
            """Start real-time ingestion stream for app"""
            try:
                # Validate app_id
                CommunicationAppType(app_id)
                
                # Initialize memory manager if needed
                if not memory_manager.db:
                    memory_manager.initialize()
                
                # Start stream
                success = ingestion_pipeline.start_real_time_stream(app_id)
                
                if success:
                    return {
                        "success": True,
                        "message": f"Real-time stream started for {app_id}",
                        "app_id": app_id,
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    raise HTTPException(status_code=500, detail="Failed to start stream")
                    
            except ValueError:
                raise HTTPException(status_code=404, detail=f"Invalid app_id: {app_id}")
            except Exception as e:
                logger.error(f"Error starting stream: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/search")
        async def search_memory(query: str, app_id: Optional[str] = None, limit: int = 10):
            """Search ingested communications"""
            try:
                # Initialize memory manager if needed
                if not memory_manager.db:
                    memory_manager.initialize()
                
                # Search communications
                results = memory_manager.search_communications(query, limit, app_id)
                
                return {
                    "success": True,
                    "query": query,
                    "app_filter": app_id,
                    "limit": limit,
                    "total_results": len(results),
                    "results": results,
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                logger.error(f"Error searching memory: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/communications/{app_id}")
        async def get_app_communications(app_id: str, limit: int = 100):
            """Get communications by app type"""
            try:
                # Validate app_id
                CommunicationAppType(app_id)
                
                # Initialize memory manager if needed
                if not memory_manager.db:
                    memory_manager.initialize()
                
                # Get communications
                results = memory_manager.get_communications_by_app(app_id, limit)
                
                return {
                    "success": True,
                    "app_id": app_id,
                    "limit": limit,
                    "total_results": len(results),
                    "communications": results,
                    "timestamp": datetime.now().isoformat()
                }
                
            except ValueError:
                raise HTTPException(status_code=404, detail=f"Invalid app_id: {app_id}")
            except Exception as e:
                logger.error(f"Error getting communications: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/communications/timeline")
        async def get_communications_timeline(
            start_date: str,
            end_date: str,
            app_id: Optional[str] = None
        ):
            """Get communications within time frame"""
            try:
                # Parse dates
                start_dt = datetime.fromisoformat(start_date)
                end_dt = datetime.fromisoformat(end_date)
                
                # Initialize memory manager if needed
                if not memory_manager.db:
                    memory_manager.initialize()
                
                # Get communications
                results = memory_manager.get_communications_by_timeframe(start_dt, end_dt)
                
                # Filter by app if specified
                if app_id:
                    results = [r for r in results if r.get("app_type") == app_id]
                
                return {
                    "success": True,
                    "start_date": start_date,
                    "end_date": end_date,
                    "app_filter": app_id,
                    "total_results": len(results),
                    "communications": results,
                    "timestamp": datetime.now().isoformat()
                }
                
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
            except Exception as e:
                logger.error(f"Error getting timeline: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/memory/stats")
        async def get_memory_stats():
            """Get detailed memory statistics"""
            try:
                # Initialize memory manager if needed
                if not memory_manager.db:
                    memory_manager.initialize()
                
                stats = ingestion_pipeline.get_ingestion_stats()
                
                # Get database statistics
                db_stats = {
                    "database_type": "LanceDB",
                    "database_path": str(memory_manager.db_path),
                    "tables": memory_manager.db.table_names()
                }
                
                # Get table statistics
                if memory_manager.connections_table:
                    comm_count = memory_manager.connections_table.to_pandas()
                    db_stats["total_communications"] = len(comm_count)
                    db_stats["app_distribution"] = comm_count["app_type"].value_counts().to_dict()
                
                return {
                    "success": True,
                    "ingestion_stats": stats,
                    "database_stats": db_stats,
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                logger.error(f"Error getting memory stats: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

# Create global instance
communication_ingestion_integration = CommunicationAppIngestionIntegration()
communication_ingestion_router = communication_ingestion_integration.router

# Export for main app
__all__ = [
    'communication_ingestion_integration',
    'communication_ingestion_router'
]