from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from core.database import SessionLocal
from core.models import HITLAction, HITLActionStatus, User, AgentRegistry, UserRole
import logging
import json

logger = logging.getLogger(__name__)

class InterventionService:
    """
    Service for managing Human-in-the-Loop (HITL) interventions.
    Handles creation, retrieval, and resolution of HITL actions.
    """
    
    async def request_intervention(
        self,
        workspace_id: str,
        action_type: str,
        platform: str,
        params: Dict[str, Any],
        reason: str,
        agent_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new HITL action request in the database.
        """
        try:
            with SessionLocal() as db:
                hitl_action = HITLAction(
                    workspace_id=workspace_id,
                    agent_id=agent_id,
                    user_id=user_id,
                    action_type=action_type,
                    platform=platform,
                    params=params, # SQLAlchemy JSON type handles dict
                    reason=reason,
                    status=HITLActionStatus.PENDING.value
                )
                db.add(hitl_action)
                db.commit()
                db.refresh(hitl_action)
                
                logger.info(f"Created HITL action {hitl_action.id} for agent {agent_id}")
                
                return {
                    "status": "PAUSED",
                    "action_id": hitl_action.id,
                    "message": f"Action paused for human review: {reason}",
                    "requires_approval": True
                }
        except Exception as e:
            logger.error(f"Failed to request intervention: {e}")
            return {
                "status": "ERROR",
                "message": f"Failed to persist intervention request: {str(e)}"
            }

    def get_pending_interventions(self, workspace_id: str = None, user_id: str = None) -> List[Dict[str, Any]]:
        """
        Get all pending interventions, optionally filtered by workspace or user ownership.
        """
        with SessionLocal() as db:
            query = db.query(HITLAction).filter(HITLAction.status == HITLActionStatus.PENDING.value)
            
            if workspace_id and workspace_id != "default":
                query = query.filter(HITLAction.workspace_id == workspace_id)
            
            # If user_id is provided, we might want to filter by ownership or role
            # For now, we return all applicable to the workspace
            
            actions = query.all()
            
            results = []
            for action in actions:
                agent_name = "Unknown Agent"
                if action.agent_id:
                    agent = db.query(AgentRegistry).filter(AgentRegistry.id == action.agent_id).first()
                    if agent:
                        agent_name = agent.name
                
                results.append({
                    "id": action.id,
                    "agent_id": action.agent_id,
                    "agent_name": agent_name,
                    "user_id": action.user_id,
                    "action_type": action.action_type,
                    "platform": action.platform,
                    "params": action.params,
                    "reason": action.reason,
                    "created_at": action.created_at.isoformat(),
                    "status": action.status
                })
            return results

    async def approve_intervention(self, action_id: str, approver_id: str) -> Dict[str, Any]:
        """
        Approve a pending intervention.
        """
        with SessionLocal() as db:
            action = db.query(HITLAction).filter(HITLAction.id == action_id).first()
            if not action:
                return {"success": False, "message": "Action not found"}
            
            if action.status != HITLActionStatus.PENDING.value:
                return {"success": False, "message": f"Action is {action.status}, cannot approve."}
            
            # Update status
            action.status = HITLActionStatus.APPROVED.value
            action.reviewed_by = approver_id
            action.reviewed_at = datetime.now()
            
            db.commit()
            
            # In a real system, this would resume the suspended workflow/agent.
            # For now, we just mark it approved. The agent/workflow needs to poll or be triggered.
            
            return {
                "success": True,
                "message": "Action approved",
                "action_id": action.id
            }

    async def reject_intervention(self, action_id: str, approver_id: str, reason: str) -> Dict[str, Any]:
        """
        Reject a pending intervention.
        """
        with SessionLocal() as db:
            action = db.query(HITLAction).filter(HITLAction.id == action_id).first()
            if not action:
                return {"success": False, "message": "Action not found"}
            
            action.status = HITLActionStatus.REJECTED.value
            action.reviewed_by = approver_id
            action.reviewed_at = datetime.now()
            action.user_feedback = reason
            
            db.commit()
            
            return {
                "success": True,
                "message": "Action rejected",
                "action_id": action.id
            }

# Singleton instance
intervention_service = InterventionService()
