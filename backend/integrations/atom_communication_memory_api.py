"""
ATOM Communication Memory API
Comprehensive API for all communication apps with LanceDB ingestion
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Body
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
import logging
from integrations.atom_communication_ingestion_pipeline import (
    memory_manager, 
    ingestion_pipeline, 
    CommunicationAppType,
    CommunicationData,
    IngestionConfig
)
from integrations.atom_communication_apps_lancedb_integration import communication_ingestion_router

logger = logging.getLogger(__name__)

class AtomCommunicationMemoryAPI:
    """Main API for ATOM communication memory system"""
    
    def __init__(self):
        self.router = APIRouter(prefix="/api/atom/communication/memory", tags=["ATOM Communication Memory"])
        self.setup_routes()
    
    def setup_routes(self):
        """Setup comprehensive API routes"""
        
        @self.router.get("/status")
        async def get_memory_system_status():
            """Get complete memory system status"""
            try:
                # Initialize if needed
                if not memory_manager.db:
                    memory_manager.initialize()
                
                # Get ingestion stats
                ingestion_stats = ingestion_pipeline.get_ingestion_stats()
                
                # Get database stats
                db_stats = {
                    "database_type": "LanceDB",
                    "database_path": str(memory_manager.db_path),
                    "tables": memory_manager.db.table_names(),
                    "total_records": 0
                }
                
                # Get record count
                if memory_manager.connections_table:
                    records = memory_manager.connections_table.to_pandas()
                    db_stats["total_records"] = len(records)
                    
                    # App distribution
                    app_dist = records["app_type"].value_counts().to_dict()
                    db_stats["app_distribution"] = app_dist
                
                return {
                    "status": "active",
                    "timestamp": datetime.now().isoformat(),
                    "memory_system": "LanceDB Vector Database",
                    "total_apps_configured": len(ingestion_stats.get("configured_apps", [])),
                    "active_streams": ingestion_stats.get("active_streams", []),
                    "total_messages_ingested": ingestion_stats.get("total_messages", 0),
                    "database_statistics": db_stats,
                    "features": {
                        "real_time_ingestion": True,
                        "batch_processing": True,
                        "vector_search": True,
                        "text_search": True,
                        "metadata_storage": True,
                        "attachment_handling": True,
                        "embedding_support": True
                    }
                }
            except Exception as e:
                logger.error(f"Error getting memory system status: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/apps")
        async def get_configured_memory_apps():
            """Get all apps configured for memory ingestion"""
            try:
                apps = []
                for app_type in CommunicationAppType:
                    config = ingestion_pipeline.ingestion_configs.get(app_type.value)
                    
                    app_info = {
                        "id": app_type.value,
                        "name": app_type.value.replace("_", " ").title(),
                        "type": "communication",
                        "memory_ingestion_enabled": config.get("enabled", False) if config else False,
                        "real_time_support": config.get("real_time", False) if config else False,
                        "batch_support": config.get("batch_size", 0) > 0 if config else False,
                        "attachment_support": config.get("ingest_attachments", False) if config else False,
                        "embedding_support": config.get("embed_content", False) if config else False
                    }
                    
                    apps.append(app_info)
                
                return {
                    "apps": apps,
                    "total": len(apps),
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                logger.error(f"Error getting configured apps: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/ingest")
        async def ingest_communication_message(
            app_id: str = Query(..., description="Communication app ID"),
            message_data: Dict[str, Any] = Body(..., description="Message data to ingest")
        ):
            """Ingest single communication message to memory"""
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
                        "message_id": message_data.get("id", "unknown"),
                        "timestamp": datetime.now().isoformat(),
                        "memory_system": "LanceDB"
                    }
                else:
                    raise HTTPException(status_code=500, detail="Failed to ingest message")
                    
            except ValueError:
                raise HTTPException(status_code=404, detail=f"Invalid app_id: {app_id}")
            except Exception as e:
                logger.error(f"Error ingesting message: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/ingest/batch")
        async def ingest_communication_batch(
            app_id: str = Query(..., description="Communication app ID"),
            messages: List[Dict[str, Any]] = Body(..., description="Batch of messages to ingest")
        ):
            """Ingest batch of communication messages to memory"""
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
                    "success_rate": f"{(success_count / len(messages)) * 100:.1f}%",
                    "timestamp": datetime.now().isoformat(),
                    "memory_system": "LanceDB"
                }
                    
            except ValueError:
                raise HTTPException(status_code=404, detail=f"Invalid app_id: {app_id}")
            except Exception as e:
                logger.error(f"Error ingesting batch: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/search")
        async def search_memory(
            query: str = Query(..., description="Search query"),
            app_id: Optional[str] = Query(None, description="Filter by app ID"),
            limit: int = Query(10, ge=1, le=100, description="Result limit"),
            time_start: Optional[str] = Query(None, description="Start date (ISO format)"),
            time_end: Optional[str] = Query(None, description="End date (ISO format)")
        ):
            """Search memory with various filters"""
            try:
                # Initialize memory manager if needed
                if not memory_manager.db:
                    memory_manager.initialize()
                
                # Build search results
                if time_start and time_end:
                    # Time-based search
                    start_dt = datetime.fromisoformat(time_start)
                    end_dt = datetime.fromisoformat(time_end)
                    results = memory_manager.get_communications_by_timeframe(start_dt, end_dt)
                    
                    # Filter by app if specified
                    if app_id:
                        results = [r for r in results if r.get("app_type") == app_id]
                    
                    # Filter by content query
                    if query:
                        results = [r for r in results if query.lower() in r.get("content", "").lower()]
                else:
                    # Regular search
                    results = memory_manager.search_communications(query, limit, app_id)
                
                return {
                    "success": True,
                    "query": query,
                    "app_filter": app_id,
                    "time_range": {"start": time_start, "end": time_end} if time_start or time_end else None,
                    "limit": limit,
                    "total_results": len(results),
                    "results": results,
                    "timestamp": datetime.now().isoformat(),
                    "memory_system": "LanceDB"
                }
                
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
            except Exception as e:
                logger.error(f"Error searching memory: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/communications/{app_id}")
        async def get_app_communications(
            app_id: str,
            limit: int = Query(50, ge=1, le=1000, description="Result limit"),
            time_start: Optional[str] = Query(None, description="Start date (ISO format)"),
            time_end: Optional[str] = Query(None, description="End date (ISO format)")
        ):
            """Get communications by app type"""
            try:
                # Validate app_id
                CommunicationAppType(app_id)
                
                # Initialize memory manager if needed
                if not memory_manager.db:
                    memory_manager.initialize()
                
                # Get communications
                if time_start and time_end:
                    # Time-based search
                    start_dt = datetime.fromisoformat(time_start)
                    end_dt = datetime.fromisoformat(time_end)
                    all_results = memory_manager.get_communications_by_timeframe(start_dt, end_dt)
                    results = [r for r in all_results if r.get("app_type") == app_id]
                else:
                    # Regular app-based search
                    results = memory_manager.get_communications_by_app(app_id, limit)
                
                return {
                    "success": True,
                    "app_id": app_id,
                    "app_name": app_id.replace("_", " ").title(),
                    "limit": limit,
                    "time_range": {"start": time_start, "end": time_end} if time_start or time_end else None,
                    "total_results": len(results),
                    "communications": results,
                    "timestamp": datetime.now().isoformat(),
                    "memory_system": "LanceDB"
                }
                
            except ValueError:
                raise HTTPException(status_code=404, detail=f"Invalid app_id: {app_id}")
            except Exception as e:
                logger.error(f"Error getting communications: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/analytics")
        async def get_memory_analytics(
            time_start: Optional[str] = Query(None, description="Start date (ISO format)"),
            time_end: Optional[str] = Query(None, description="End date (ISO format)")
        ):
            """Get memory analytics and statistics"""
            try:
                # Initialize memory manager if needed
                if not memory_manager.db:
                    memory_manager.initialize()
                
                # Get base analytics
                stats = ingestion_pipeline.get_ingestion_stats()
                
                # Get database records for analysis
                all_records = []
                if memory_manager.connections_table:
                    df = memory_manager.connections_table.to_pandas()
                    all_records = df.to_dict('records')
                
                # Apply time filters if specified
                if time_start and time_end:
                    start_dt = datetime.fromisoformat(time_start)
                    end_dt = datetime.fromisoformat(time_end)
                    filtered_records = [
                        r for r in all_records 
                        if start_dt <= datetime.fromisoformat(r["timestamp"]) <= end_dt
                    ]
                else:
                    filtered_records = all_records
                
                # Generate analytics
                analytics = {
                    "summary": {
                        "total_messages": len(filtered_records),
                        "unique_apps": len(set(r.get("app_type") for r in filtered_records)),
                        "date_range": {
                            "start": time_start,
                            "end": time_end
                        }
                    },
                    "app_distribution": {},
                    "direction_distribution": {"inbound": 0, "outbound": 0, "internal": 0},
                    "priority_distribution": {},
                    "status_distribution": {},
                    "timeline_data": {}
                }
                
                # Analyze records
                for record in filtered_records:
                    # App distribution
                    app_type = record.get("app_type", "unknown")
                    analytics["app_distribution"][app_type] = analytics["app_distribution"].get(app_type, 0) + 1
                    
                    # Direction distribution
                    direction = record.get("direction", "unknown")
                    if direction in analytics["direction_distribution"]:
                        analytics["direction_distribution"][direction] += 1
                    
                    # Priority distribution
                    priority = record.get("priority", "normal")
                    analytics["priority_distribution"][priority] = analytics["priority_distribution"].get(priority, 0) + 1
                    
                    # Status distribution
                    status = record.get("status", "unknown")
                    analytics["status_distribution"][status] = analytics["status_distribution"].get(status, 0) + 1
                    
                    # Timeline data (by day)
                    if "timestamp" in record:
                        try:
                            record_date = datetime.fromisoformat(record["timestamp"]).date().isoformat()
                            analytics["timeline_data"][record_date] = analytics["timeline_data"].get(record_date, 0) + 1
                        except:
                            pass
                
                return {
                    "success": True,
                    "analytics": analytics,
                    "ingestion_stats": stats,
                    "timestamp": datetime.now().isoformat(),
                    "memory_system": "LanceDB"
                }
                
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
            except Exception as e:
                logger.error(f"Error getting analytics: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/configure")
        async def configure_app_memory(
            app_id: str,
            config: IngestionConfig = Body(..., description="Memory ingestion configuration")
        ):
            """Configure memory ingestion for specific app"""
            try:
                # Validate app_id
                app_type = CommunicationAppType(app_id)
                
                # Configure app
                ingestion_pipeline.configure_app(app_type, config)
                
                return {
                    "success": True,
                    "message": f"Memory ingestion configured for {app_id}",
                    "app_id": app_id,
                    "app_name": app_id.replace("_", " ").title(),
                    "configuration": config.__dict__,
                    "timestamp": datetime.now().isoformat()
                }
                
            except ValueError:
                raise HTTPException(status_code=404, detail=f"Invalid app_id: {app_id}")
            except Exception as e:
                logger.error(f"Error configuring app: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
    
    def get_router(self):
        """Get the configured router"""
        return self.router

# Create global instance
atom_memory_api = AtomCommunicationMemoryAPI()
atom_memory_router = atom_memory_api.get_router()

# Export for main app
__all__ = [
    'AtomCommunicationMemoryAPI',
    'atom_memory_api',
    'atom_memory_router'
]
