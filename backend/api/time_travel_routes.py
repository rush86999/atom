
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging

from advanced_workflow_orchestrator import get_orchestrator

router = APIRouter(prefix="/api/time-travel", tags=["time_travel"])
logger = logging.getLogger(__name__)

# Single instance/factory pattern should be used in real app
# For now, we assume one orchestrator exists or is created per request (which matches current tests but not prod)
# TO-DO: Inject the singleton orchestrator from main_api_app

class ForkRequest(BaseModel):
    step_id: str
    new_variables: Optional[Dict[str, Any]] = None

@router.post("/workflows/{execution_id}/fork")
async def fork_workflow(execution_id: str, request: ForkRequest):
    """
    [Lesson 3] Fork a workflow execution from a specific step.
    Creates a 'Parallel Universe' with modified variables.
    """
    logger.info(f"⏳ Time-Travel Request: Forking {execution_id} at {request.step_id}")
    
    
    # Use the shared singleton instance
    orch = get_orchestrator()
    
    new_execution_id = await orch.fork_execution(
        original_execution_id=execution_id,
        step_id=request.step_id,
        new_variables=request.new_variables
    )
    
    if not new_execution_id:
        raise HTTPException(status_code=404, detail="Snapshot not found or fork failed")
        
    return {
        "status": "success", 
        "original_execution_id": execution_id,
        "new_execution_id": new_execution_id,
        "message": "Welcome to the Multiverse. 🌌"
    }
