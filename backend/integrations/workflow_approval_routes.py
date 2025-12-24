import logging
import json
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import WorkflowExecution, WorkflowExecutionStatus
from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator, WorkflowStatus
from core.auth_endpoints import get_current_user
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/workflows/approvals", tags=["Workflow Approvals"])

class ApprovalResponse(BaseModel):
    decision: str # "approve" or "reject"
    step_id: str
    comments: Optional[str] = None

@router.get("/pending")
async def get_pending_approvals(db: Session = Depends(get_db), user = Depends(get_current_user)):
    """List all workflow executions waiting for human approval"""
    pending = db.query(WorkflowExecution).filter(
        WorkflowExecution.status == WorkflowExecutionStatus.PAUSED.value
    ).all()
    
    results = []
    for p in pending:
        context_data = json.loads(p.context) if p.context else {}
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
            "input_data": json.loads(p.input_data) if p.input_data else {},
            "created_at": p.created_at.isoformat()
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
        
    if execution.status != WorkflowStatus.WAITING_APPROVAL.value:
        raise HTTPException(status_code=400, detail=f"Execution is in {execution.status} state, not WAITING_APPROVAL")

    orchestrator = AdvancedWorkflowOrchestrator() # In real app, this should be a singleton/injected
    
    if response.decision == "approve":
        try:
            # Resume the workflow
            await orchestrator.resume_workflow(execution_id, response.step_id)
            return {"status": "success", "message": f"Workflow {execution_id} resumed"}
        except Exception as e:
            logger.error(f"Failed to resume workflow: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    else:
        # Reject/Cancel
        execution.status = WorkflowExecutionStatus.FAILED.value
        execution.error = f"Rejected by user: {response.comments}"
        db.commit()
        return {"status": "cancelled", "message": f"Workflow {execution_id} was rejected"}
