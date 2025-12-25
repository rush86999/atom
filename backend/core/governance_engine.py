"""
ATOM External Contact Governance Engine
Implements safety guardrails for agent-driven external communications.
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from core.database import SessionLocal
from core.models import Workspace, HITLAction, HITLActionStatus

logger = logging.getLogger(__name__)

class ContactGovernance:
    """
    Manages approval logic for agent communications.
    Enforces 'Learning Phase' and 'User Confidence' gates.
    """

    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session

    def is_external_contact(self, platform: str, params: Dict[str, Any]) -> bool:
        """
        Heuristic to determine if a recipient is external to the workspace.
        """
        recipient_id = params.get("recipient_id", "")
        
        # Simple heuristics:
        # 1. Email: Check if it's outside a 'known_internal_domains' list (placeholder logic)
        if "@" in recipient_id:
            # In a real system, we'd fetch the workspace domains from DB
            internal_domains = ["atom.ai", "workspace.local"]
            domain = recipient_id.split("@")[-1].lower()
            return domain not in internal_domains
            
        # 2. Phone (WhatsApp): External if not in a 'team_numbers' list
        # For now, treat all messaging recipients as external unless explicitly marked internal
        if platform in ["whatsapp", "messenger", "slack"]:
            return params.get("is_internal") is not True

        return True

    async def should_require_approval(self, workspace_id: str, action_type: str, platform: str, params: Dict[str, Any]) -> bool:
        """
        Determines if the action must be paused for HITL review.
        """
        db = self.db or SessionLocal()
        try:
            workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
            if not workspace:
                logger.warning(f"Workspace {workspace_id} not found for governance check.")
                return True 

            # Autonomy Condition: Handled 'OR' logic
            # Autonomy if (Learning Phase is Over) OR (High User Confidence for this pattern)
            
            # 1. Check Confidence first (Pattern Graduation)
            confidence = self.get_confidence_score(workspace_id, action_type, platform)
            if confidence >= 0.9:
                logger.info(f"Action approved autonomously: High confidence ({confidence}) for pattern.")
                return False

            # 2. Check override flag (Workspace graduation)
            if workspace.learning_phase_completed:
                logger.info(f"Action approved autonomously: Workspace {workspace_id} graduation flag set.")
                return False

            # Default to pause if not graduated nor confident
            logger.info(f"Action paused: Learning phase in progress and low pattern confidence ({confidence}).")
            return True
        finally:
            if not self.db:
                db.close()

    def get_confidence_score(self, workspace_id: str, action_type: str, platform: str) -> float:
        """
        Calculates confidence score based on historical approval ratings.
        """
        db = self.db or SessionLocal()
        try:
            # Fetch recent HITL actions for this pattern
            actions = db.query(HITLAction).filter(
                HITLAction.workspace_id == workspace_id,
                HITLAction.action_type == action_type,
                HITLAction.platform == platform
            ).order_by(HITLAction.created_at.desc()).limit(10).all()

            if not actions:
                return 0.0

            approved_count = len([a for a in actions if a.status == HITLActionStatus.APPROVED.value])
            total_count = len(actions)
            
            return approved_count / total_count
        finally:
            if not self.db:
                db.close()

    async def request_approval(self, workspace_id: str, action_type: str, platform: str, params: Dict[str, Any], reason: str) -> str:
        """
        Pauses the action and creates a HITL record in the database.
        """
        db = self.db or SessionLocal()
        try:
            hitl_action = HITLAction(
                workspace_id=workspace_id,
                agent_id=params.get("agent_id"),
                action_type=action_type,
                platform=platform,
                params=params,
                reason=reason,
                status=HITLActionStatus.PENDING.value,
                confidence_score=self.get_confidence_score(workspace_id, action_type, platform)
            )
            db.add(hitl_action)
            db.commit()
            db.refresh(hitl_action)
            
            logger.info(f"Created HITL action {hitl_action.id} for workspace {workspace_id}")
            return hitl_action.id
        finally:
            if not self.db:
                db.close()

# Global governance instance
contact_governance = ContactGovernance()
