"""
Periodic System Tasks
Executed by the SQS Worker on a schedule (Heartbeat).
"""
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from saas.models import Workspace
from core.config import get_config

logger = logging.getLogger(__name__)

async def run_global_ingestion_pulse():
    """
    Heartbeat Task: Triggers document ingestion sync for all active workspaces.
    
    Architecture:
    1. AWS EventBridge fires 'System Heartbeat' every 5 minutes.
    2. API receives pulse -> Dispatches this task to SQS.
    3. This task iterates ALL Workspaces.
    4. Dispatches individual 'sync_integration' tasks for each enabled integration.
    5. The individual tasks check Tier Limits (Tier 1 = Skip if <60m, Tier 2 = Sync).
    """
    config = get_config()
    engine = create_engine(config.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    logger.info("❤️ Global Ingestion Heartbeat Started")
    
    try:
        with get_db_session() as db:
            workspaces = db.query(Workspace).all()
            logger.info(f"Found {len(workspaces)} workspaces to check")
            
            from sqs_worker import dispatch_task
            from core.auto_document_ingestion import get_document_ingestion_service
            
            total_dispatched = 0
            
            for ws in workspaces:
                # Get service for this workspace
                service = get_document_ingestion_service(ws.id)
                settings_list = service.get_all_settings()
                
                for settings in settings_list:
                    if settings.enabled:
                        # Dispatch Sync Task
                        # We do NOT force here. We let the task logic decide if it's time based on Tier.
                        dispatch_task(
                            task_name="handle_document_ingestion_sync",
                            payload={
                                "integration_id": settings.integration_id,
                                "workspace_id": ws.id,
                                "force": False 
                            }
                        )
                        
                # Also trigger Dashboard Analytics Sync (Check if due)
                # The worker service will handle frequency checks (e.g. once per hour)
                dispatch_task(
                    task_name="sync_dashboard_stats",
                    payload={"workspace_id": ws.id}
                )
                
                total_dispatched += 1
            
            logger.info(f"❤️ Heartbeat Complete: and dispatched analytics syncs")

            return {"workspaces_checked": len(workspaces), "tasks_dispatched": total_dispatched}
            
    except Exception as e:
        logger.error(f"Heartbeat failed: {e}")
        return {"error": str(e)}
