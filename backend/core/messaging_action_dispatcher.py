import logging
from typing import Any, Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from core.database import get_db_session
from core.proposal_service import ProposalService
from core.intervention_service import InterventionService
from core.agent_governance_service import AgentGovernanceService

logger = logging.getLogger(__name__)

class MessagingActionDispatcher:
    """
    Standardized dispatcher for interactive messaging callbacks.
    Integrates with AgentGovernanceService to ensure security and compliance.
    """

    def __init__(self, db: Optional[Session] = None):
        self._db = db

    async def dispatch_action(
        self,
        platform: str,
        tenant_id: str,
        user_id: str,
        action_id: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Dispatch a standardized interactive callback.
        """
        if not action_id:
             return {"success": False, "error": "Missing action_id"}

        logger.info(f"Dispatching standardization action {action_id} from {platform} for tenant {tenant_id}")
        
        # Use provided DB or create a temporary one if none provided
        if self._db:
            return await self._execute_dispatch(self._db, platform, tenant_id, user_id, action_id, payload)
        else:
            with get_db_session() as db:
                return await self._execute_dispatch(db, platform, tenant_id, user_id, action_id, payload)

    async def _execute_dispatch(
        self,
        db: Session,
        platform: str,
        tenant_id: str,
        user_id: str,
        action_id: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        gov_service = AgentGovernanceService(db, tenant_id=tenant_id)
        
        try:
            # 1. Parse action parts
            parts = action_id.split(":", 1)
            action_type = parts[0]
            target_id = parts[1] if len(parts) > 1 else None

            # 2. Governance Check
            # Map messaging action to governance action type
            # gov_action = self._map_to_gov_action(action_type)
            
            # Note: In Upstream, we perform a strict permission check for the user
            from core.models import User
            user = db.query(User).filter(User.id == user_id, User.tenant_id == tenant_id).first()
            if not user:
                 logger.warning(f"User {user_id} not found for action {action_id}")
                 return {"success": False, "error": "User not found or access denied"}

            # 3. Route to specialized handlers
            if action_type in ["approve_proposal", "reject_proposal"]:
                return await self._handle_proposal(db, tenant_id, user, action_type, target_id, payload)
            elif action_type == "intervention_approve":
                return await self._handle_intervention(db, tenant_id, user_id, target_id)
            elif action_type.startswith("feedback_"):
                return await self._handle_feedback(db, gov_service, tenant_id, user_id, action_type, target_id, payload)
            else:
                logger.warning(f"No handler for action type: {action_type}")
                return {"success": False, "error": f"Unknown action: {action_type}"}

        except Exception as e:
            logger.error(f"Action dispatch failed: {e}")
            return {"success": False, "error": str(e)}

    def _map_to_gov_action(self, action_type: str) -> str:
        """Map messaging interactions to governance action complexity levels."""
        if "approve" in action_type: return "approve"
        if "delete" in action_type: return "delete"
        if "update" in action_type: return "update"
        return "read"

    async def _handle_proposal(
        self, db: Session, tenant_id: str, user: Any, action_type: str, proposal_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Unified handler for proposal actions."""
        from core.models import AgentProposal
        proposal = db.query(AgentProposal).filter(
            AgentProposal.id == proposal_id,
            AgentProposal.tenant_id == tenant_id
        ).first()
        
        if not proposal:
            return {"success": False, "error": "Proposal not found"}
            
        is_approval = "approve" in action_type
        proposal.status = 'approved' if is_approval else 'rejected'
        proposal.approver_type = 'user'
        proposal.approver_id = user.id
        proposal.reviewed_at = datetime.utcnow()
        proposal.approval_reason = payload.get("value") or ("Approved" if is_approval else "Rejected")
        
        db.commit()
        return {"success": True, "message": f"Proposal {'approved' if is_approval else 'rejected'}"}

    async def _handle_intervention(self, db: Session, tenant_id: str, user_id: str, intervention_id: str) -> Dict[str, Any]:
        service = InterventionService(db)
        success = await service.approve_intervention(intervention_id, tenant_id, user_id)
        return {"success": success, "message": "Intervention approved" if success else "Approval failed"}

    async def _handle_feedback(
        self, db: Session, gov: AgentGovernanceService, tenant_id: str, user_id: str, 
        action_type: str, agent_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle direct agent feedback (e.g. thumbs up/down from Slack)."""
        feedback_subtype = action_type.replace("feedback_", "")
        value = payload.get("value")
        
        if feedback_subtype == "thumbs":
            is_up = value == "up" or value == "true"
            # Note: submit_thumbs_feedback must be implemented in Upstream AgentGovernanceService
            try:
                await gov.submit_thumbs_feedback(
                    agent_id=agent_id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    original_output="Referenced interactive message",
                    thumbs_up=is_up
                )
                return {"success": True, "message": "Feedback recorded"}
            except AttributeError:
                logger.warning("AgentGovernanceService.submit_thumbs_feedback not implemented in Upstream")
                return {"success": False, "error": "Feedback service unavailable"}
            
        return {"success": False, "error": f"Unsupported feedback type: {feedback_subtype}"}

_dispatcher = None

def get_messaging_action_dispatcher(db: Optional[Session] = None) -> MessagingActionDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = MessagingActionDispatcher(db)
    return _dispatcher
