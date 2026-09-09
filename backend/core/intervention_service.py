from datetime import datetime
import json
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from core.database import get_db_session
from core.models import AgentRegistry, HITLAction, HITLActionStatus, User, UserRole

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
        user_id: Optional[str] = None,
        required_role: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new HITL action request in the database.

        ``required_role`` (from governance config ``roles`` map) is persisted
        in ``context_snapshot`` so the approval surface can enforce it; the
        kwarg was already being passed by mcp_service._check_hitl_policy —
        before it existed here every governed intercept raised TypeError and
        failed closed into "policy check unavailable".
        """
        try:
            with get_db_session() as db:
                hitl_action = HITLAction(
                    workspace_id=workspace_id,
                    agent_id=agent_id,
                    user_id=user_id,
                    action_type=action_type,
                    platform=platform,
                    params=params, # SQLAlchemy JSON type handles dict
                    reason=reason,
                    context_snapshot={"required_role": required_role} if required_role else None,
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
        with get_db_session() as db:
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

    async def approve_intervention(
        self,
        action_id: str,
        approver_id: str,
        modified_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Approve a pending intervention.

        Enforces the per-action ``required_role`` persisted by
        ``request_intervention`` (from the governance config ``roles`` map):
        the approver must hold at least that role. Unknown role strings fail
        closed. ``modified_params`` replaces the action's params so the row
        reflects what was actually approved (the UI "Modify before approve"
        flow).
        """
        with get_db_session() as db:
            action = db.query(HITLAction).filter(HITLAction.id == action_id).first()
            if not action:
                return {"success": False, "message": "Action not found"}

            if action.status != HITLActionStatus.PENDING.value:
                return {"success": False, "message": f"Action is {action.status}, cannot approve."}

            denial = self._required_role_denial(db, action, approver_id)
            if denial:
                return {"success": False, "message": denial}

            if modified_params is not None:
                action.params = modified_params

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

        Enforces the same ``required_role`` gate as approval — rejection is
        also a governance decision.
        """
        with get_db_session() as db:
            action = db.query(HITLAction).filter(HITLAction.id == action_id).first()
            if not action:
                return {"success": False, "message": "Action not found"}

            if action.status != HITLActionStatus.PENDING.value:
                return {"success": False, "message": f"Action is {action.status}, cannot reject."}

            denial = self._required_role_denial(db, action, approver_id)
            if denial:
                return {"success": False, "message": denial}

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

    @staticmethod
    def _required_role_denial(db: Session, action: HITLAction, approver_id: str) -> Optional[str]:
        """
        Return a denial reason if ``approver_id`` may not decide ``action``,
        else None. The approver must be a verified (existing, ACTIVE) user;
        when the action carries ``required_role`` they must hold at least
        that role. Unknown role strings deny (fail closed).
        """
        approver = db.query(User).filter(User.id == approver_id).first()
        if not approver or getattr(approver, "status", None) not in (None, "active"):
            return "Approver could not be verified; decision denied (fail closed)"

        required_raw = (action.context_snapshot or {}).get("required_role")
        if not required_raw:
            return None

        normalized = str(required_raw).strip().lower()
        try:
            required_role = UserRole(normalized)
        except ValueError:
            logger.error(
                "HITL action %s requires unknown role %r; denying (fail closed)",
                action.id,
                required_raw,
            )
            return (
                f"Action requires unreadable role '{required_raw}'; "
                "decision denied (fail closed)"
            )

        from core.security.rbac import user_meets_role

        if not user_meets_role(approver, required_role):
            return (
                f"Approver role '{approver.role}' is below the required role "
                f"'{required_role.value}' for this action"
            )
        return None

# Singleton instance
intervention_service = InterventionService()
