import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from service_delivery.models import Milestone, MilestoneStatus
from sqlalchemy.orm import Session

from core.billing_orchestrator import billing_orchestrator
from core.database import get_db

router = APIRouter(prefix="/billing", tags=["Billing & Invoicing"])
logger = logging.getLogger(__name__)

# Governance feature flags
BILLING_GOVERNANCE_ENABLED = os.getenv("BILLING_GOVERNANCE_ENABLED", "true").lower() == "true"
EMERGENCY_GOVERNANCE_BYPASS = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"

@router.post("/milestone/{milestone_id}")
async def bill_milestone(milestone_id: str, agent_id: Optional[str] = None):
    """
    Manually trigger billing for a completed milestone.

    **Governance**: Requires AUTONOMOUS maturity for billing operations.
    """
    # Governance check for billing operations
    if BILLING_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and agent_id:
        from core.agent_governance_service import AgentGovernanceService

        db = next(get_db())
        try:
            governance = AgentGovernanceService(db)
            check = governance.can_perform_action(
                agent_id=agent_id,
                action="bill_milestone",
                resource_type="billing",
                complexity=4  # CRITICAL - financial transaction
            )

            if not check["allowed"]:
                logger.warning(f"Governance check failed for bill_milestone by agent {agent_id}: {check['reason']}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Governance check failed: {check['reason']}"
                )
        finally:
            db.close()

    result = await billing_orchestrator.process_milestone_completion(milestone_id, "default")
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])

    logger.info(f"Milestone billed: {milestone_id} by agent {agent_id or 'system'}")
    return result

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
