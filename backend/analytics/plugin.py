from fastapi import FastAPI
import logging
from analytics.routes import router as analytics_router
from analytics.instrumentation import activate_analytics

logger = logging.getLogger(__name__)

def enable_workflow_dna(app: FastAPI):
    """
    Enables the Workflow DNA plugin:
    1. Registers the Analytics API routes
    2. Hooks into the Orchestrator to begin collecting data
    """
    try:
        # 1. Register API
        # Proxy redirects /api/analytics -> /api/v1/analytics, so we need to match that
        app.include_router(analytics_router, prefix="/api/v1") 
        logger.info("🔌 Workflow DNA Plugin: API Routes Registered (at /api/v1/analytics)")
        
        # 1.5. Ensure Analytics Tables Exist
        from core.database import engine
        from analytics.models import WorkflowExecutionLog
        WorkflowExecutionLog.metadata.create_all(bind=engine)
        logger.info("🔌 Workflow DNA Plugin: Database Schema Verified")

        # 2. Activate Instrumentation
        # We need to find the active orchestrator instance.
        # usually it's in a global or dependency injection container.
        # For now, we will try to find it via the workflow modules if they are loaded.
        
        # Strategy: We will import the orchestrator instance from where it's instantiated.
        # Assuming it's in core/workflow_endpoints or similar. 
        # But wait, looking at main_api_app.py, we don't clear see where the orchestrator is held.
        # It's usually instantiated in the `workflow_routes.py` or similar.
        
        # Checking `core/workflow_endpoints.py` usually reveals `orchestrator = AdvancedWorkflowOrchestrator()`
        
        from advanced_workflow_orchestrator import orchestrator
        activate_analytics(orchestrator)
        
    except Exception as e:
        logger.error(f"⚠️ Failed to enable Workflow DNA Plugin: {e}")
