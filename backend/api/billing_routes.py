from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from core.database import get_db
from sqlalchemy.orm import Session
from core.billing_orchestrator import billing_orchestrator
from service_delivery.models import Milestone, MilestoneStatus

router = APIRouter(prefix="/billing", tags=["Billing & Invoicing"])

@router.post("/milestone/{milestone_id}")
async def bill_milestone(milestone_id: str, workspace_id: str = "default"):
    """
    Manually trigger billing for a completed milestone.
    """
    result = await billing_orchestrator.process_milestone_completion(milestone_id, workspace_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@router.get("/unbilled-milestones")
async def get_unbilled_milestones(workspace_id: str = "default", db: Session = Depends(get_db)):
    """
    List completed milestones that haven't been invoiced yet.
    """
    milestones = db.query(Milestone).filter(
        Milestone.workspace_id == workspace_id,
        Milestone.status == MilestoneStatus.COMPLETED,
        Milestone.invoice_id == None
    ).all()
    
    return [
        {
            "id": m.id,
            "name": m.name,
            "project_id": m.project_id,
            "amount": m.amount,
            "percentage": m.percentage
        } for m in milestones
    ]
