import json
import logging
from typing import Any, Dict, List, Optional
from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator, WorkflowStatus
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing_extensions import Literal

from core.auth_endpoints import get_current_user
from core.database import get_db
from core.intervention_service import intervention_service
from core.models import HITLAction, WorkflowExecution, WorkflowExecutionStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/workflows/approvals", tags=["Workflow Approvals"])

class ApprovalResponse(BaseModel):
    decision: Literal["approve", "reject"] # "approve" or "reject"
    step_id: str
    comments: Optional[str] = None

def _safe_json(value: Optional[str]) -> Dict[str, Any]:
    """Parse persisted JSON safely — a corrupt row must not 500 the list."""
    if not value:
        return {}
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return {}


def _waiting_result(execution: Any, step_id: str) -> Dict[str, Any]:
    context_data = _safe_json(getattr(execution, "context", None))
    result = (context_data.get("results") or {}).get(step_id)
    return dict(result) if isinstance(result, dict) else {}


def _scoped_action(db: Session, action_id: str, user: Any) -> Optional[HITLAction]:
    """Load a durable checkpoint inside the authenticated scope."""
    query = db.query(HITLAction).filter(HITLAction.id == str(action_id))
    workspace_id = getattr(user, "workspace_id", None)
    tenant_id = getattr(user, "tenant_id", None)
    if workspace_id:
        query = query.filter(HITLAction.workspace_id == workspace_id)
    if tenant_id:
        query = query.filter(HITLAction.tenant_id == tenant_id)
    return query.first()


def _action_binding_error(
    action: HITLAction, execution_id: str, step_id: str,
    workflow_id: str = "",
) -> Optional[str]:
    params = action.params or {}
    if not isinstance(params, dict):
        return "Approval has no readable execution binding"
    bound_execution = str(
        params.get("execution_id") or params.get("workflow_id") or "")
    if bound_execution != str(execution_id):
        return "Approval does not match this execution"
    if str(params.get("step_id") or "") != str(step_id):
        return "Approval does not match this step"
    bound_definition = str(params.get("definition_id") or "")
    if bound_definition and workflow_id and (
            bound_definition != str(workflow_id)):
        return "Approval does not match this workflow definition"
    return None

@router.get("/pending")
async def get_pending_approvals(db: Session = Depends(get_db), user = Depends(get_current_user)):
    """List all workflow executions waiting for human approval"""
    pending = db.query(WorkflowExecution).filter(
        WorkflowExecution.status.in_([
            WorkflowExecutionStatus.PAUSED.value,
            WorkflowStatus.WAITING_APPROVAL.value,
        ])
    ).all()
    
    results = []
    for p in pending:
        context_data = _safe_json(p.context)
        # Find which step is actually waiting
        waiting_steps = [
            sid for sid, res in context_data.get("results", {}).items() 
            if res.get("status") == "waiting_approval"
        ]
        
        results.append({
            "execution_id": p.execution_id,
            "workflow_id": p.workflow_id,
            "status": p.status,
            "waiting_steps": waiting_steps,
            "input_data": _safe_json(p.input_data),
            "created_at": p.created_at.isoformat() if p.created_at else None
        })
        
    return results

@router.post("/{execution_id}/respond")
async def respond_to_approval(
    execution_id: str,
    response: ApprovalResponse,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Approve or reject a pending workflow step"""
    execution = db.query(WorkflowExecution).filter(
        WorkflowExecution.execution_id == execution_id
    ).first()
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
        
    # The pending list filters on WorkflowExecutionStatus.PAUSED, so a PAUSED
    # execution is the normal state here. Accept both the persisted PAUSED
    # value and the orchestrator's "waiting_approval" marker (legacy runs).
    if execution.status not in (
        WorkflowExecutionStatus.PAUSED.value,
        WorkflowStatus.WAITING_APPROVAL.value,
    ):
        raise HTTPException(status_code=400, detail="Execution is not waiting for approval")

    waiting = _waiting_result(execution, response.step_id)
    hitl_action_id = str(waiting.get("hitl_action_id") or "")
    action = None
    if hitl_action_id:
        action = _scoped_action(db, hitl_action_id, user)
        if action is None:
            raise HTTPException(status_code=404, detail="Approval not found")
        binding_error = _action_binding_error(
            action, execution_id, response.step_id,
            str(getattr(execution, "workflow_id", "") or ""))
        if binding_error:
            raise HTTPException(status_code=409, detail=binding_error)

    if response.decision == "approve":
        if action is not None:
            action_status = str(action.status or "").lower()
            if action_status == "pending":
                result = await intervention_service.approve_intervention(
                    action.id, str(user.id))
                if not result.get("success"):
                    raise HTTPException(
                        status_code=403,
                        detail=result.get("message") or "Approval denied")
            elif action_status != "approved":
                raise HTTPException(
                    status_code=409,
                    detail=f"Approval is {action_status}, cannot approve")
            # The durable checkpoint is now the authority. Use the registered
            # orchestrator so the execution's definition is resolvable.
            from advanced_workflow_orchestrator import get_orchestrator

            orchestrator = get_orchestrator()
        else:
            # Documented legacy compatibility: a non-server-required wait
            # without a durable HITL row keeps the pre-repair resume path.
            orchestrator = AdvancedWorkflowOrchestrator()
        try:
            context = await orchestrator.resume_workflow(
                execution_id, response.step_id)
            if context is None:
                raise HTTPException(
                    status_code=409,
                    detail="Workflow execution could not be resumed")
            status = getattr(context, "status", None)
            status_value = getattr(status, "value", str(status or ""))
            if status_value in ("failed", "cancelled"):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Approval does not match the authoritative "
                        "execution/definition/step/scope binding; a fresh "
                        "matching review is required"))
            if status_value == "waiting_approval":
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Approval is still pending; the workflow was not "
                        "released"))
            return {"status": "success", "message": f"Workflow {execution_id} resumed"}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to resume workflow: {e}")
            raise HTTPException(status_code=500, detail="Internal error")
    else:
        if action is not None:
            action_status = str(action.status or "").lower()
            if action_status == "pending":
                result = await intervention_service.reject_intervention(
                    action.id, str(user.id),
                    response.comments or "Rejected via workflow approval")
                if not result.get("success"):
                    raise HTTPException(
                        status_code=403,
                        detail=result.get("message") or "Rejection denied")
            elif action_status != "rejected":
                raise HTTPException(
                    status_code=409,
                    detail=f"Approval is {action_status}, cannot reject")
        # Reject/Cancel
        execution.status = WorkflowExecutionStatus.FAILED.value
        execution.error = f"Rejected by user: {response.comments}"
        db.commit()
        return {"status": "cancelled", "message": f"Workflow {execution_id} was rejected"}
