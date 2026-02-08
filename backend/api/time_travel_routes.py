
import logging
from typing import Any, Dict, Optional
from advanced_workflow_orchestrator import get_orchestrator
from pydantic import BaseModel

from core.base_routes import BaseAPIRouter

router = BaseAPIRouter(prefix="/api/time-travel", tags=["time_travel"])
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
        raise router.not_found_error(
            resource="WorkflowSnapshot",
            resource_id=request.step_id,
            details={"execution_id": execution_id, "reason": "Snapshot not found or fork failed"}
        )

    return router.success_response(
        data={
            "original_execution_id": execution_id,
            "new_execution_id": new_execution_id
        },
        message="Welcome to the Multiverse. 🌌"
    )
