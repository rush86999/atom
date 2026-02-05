import logging
from typing import Any, Dict, List, Optional
from fastapi import Depends, Request
from service_delivery.models import Milestone, MilestoneStatus
from sqlalchemy.orm import Session

from core.api_governance import ActionComplexity, require_governance
from core.base_routes import BaseAPIRouter
from core.billing_orchestrator import billing_orchestrator
from core.database import get_db

router = BaseAPIRouter(prefix="/billing", tags=["Billing & Invoicing"])
logger = logging.getLogger(__name__)

@router.post("/milestone/{milestone_id}")
@require_governance(
    action_complexity=ActionComplexity.CRITICAL,
    action_name="bill_milestone",
    feature="billing"
)
async def bill_milestone(
    milestone_id: str,
    request: Request,
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Manually trigger billing for a completed milestone.

    **Governance**: Requires AUTONOMOUS maturity (CRITICAL complexity).
    - Payment processing requires AUTONOMOUS maturity
    - Financial operations are tightly controlled
    """
    result = await billing_orchestrator.process_milestone_completion(milestone_id, "default")
    if result["status"] == "error":
        raise router.error_response(
            error_code="BILLING_FAILED",
            message=result.get("message", "Failed to process milestone billing"),
            status_code=400
        )

    logger.info(f"Milestone billed: {milestone_id}")
    return router.success_response(
        data=result,
        message="Milestone billed successfully"
    )

@router.get("/unbilled-milestones")
async def get_unbilled_milestones(db: Session = Depends(get_db)):
    """
    List completed milestones that haven't been invoiced yet.
    """
    milestones = db.query(Milestone).filter(
        Milestone.workspace_id == "default",
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
