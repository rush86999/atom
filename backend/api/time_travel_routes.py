"""Time-travel workflow fork route.

Restored from .archive/dead-routes-2026-07/time_travel_routes.py — the
WorkflowAutomation frontend still calls POST /api/time-travel/workflows/{id}/fork,
but the route had been archived, so the feature 404'd in real usage.

Restored with two adjustments for real-world / cloud usage:
- Auth via get_current_user (frontend sends its Bearer token; keeps a
  state-changing endpoint from being unauthenticated in production).
- Response exposes new_execution_id at the top level to match the frontend
  contract (it reads data.new_execution_id directly).
"""
from typing import Any, Dict, Optional

from fastapi import Depends
from pydantic import BaseModel

from advanced_workflow_orchestrator import get_orchestrator
from core.auth import get_current_user
from core.base_routes import BaseAPIRouter

router = BaseAPIRouter(prefix="/api/time-travel", tags=["time_travel"])


class ForkRequest(BaseModel):
    step_id: str
    new_variables: Optional[Dict[str, Any]] = None


@router.post("/workflows/{execution_id}/fork")
async def fork_workflow(
    execution_id: str,
    request: ForkRequest,
    user: Any = Depends(get_current_user),
):
    """Fork a workflow execution from a specific step (Parallel Universe)."""
    orch = get_orchestrator()
    new_execution_id = await orch.fork_execution(
        original_execution_id=execution_id,
        step_id=request.step_id,
        new_variables=request.new_variables,
    )

    if not new_execution_id:
        raise router.not_found_error(
            resource="WorkflowSnapshot",
            resource_id=request.step_id,
            details={"execution_id": execution_id, "reason": "Snapshot not found or fork failed"},
        )

    return {
        "success": True,
        "original_execution_id": execution_id,
        "new_execution_id": new_execution_id,
        "message": "Welcome to the Multiverse.",
    }
