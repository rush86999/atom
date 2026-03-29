"""
ATOM External Contact Governance Engine
Implements safety guardrails for agent-driven external communications.
"""

from datetime import datetime
import json
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from core.database import get_db_session
from core.models import HITLAction, HITLActionStatus, Workspace

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
        Uses workspace domains from database for proper email governance.
        """
        recipient_id = params.get("recipient_id", "")

        # 1. Email: Check against workspace internal domains from database
        if "@" in recipient_id:
            domain = recipient_id.split("@")[-1].lower()

            # Fetch workspace domains from database
            db = self.db or get_db_session()
            try:
                # Get workspace_id from params
                workspace_id = params.get("workspace_id")
                if not workspace_id and "agent_id" in params:
                    # Try to get workspace from agent
                    from core.models import AgentRegistry
                    agent = db.query(AgentRegistry).filter(
                        AgentRegistry.id == params["agent_id"]
                    ).first()
                    if agent:
                        workspace_id = agent.workspace_id

                if workspace_id:
                    workspace = db.query(Workspace).filter(
                        Workspace.id == workspace_id
                    ).first()

                    if workspace and workspace.metadata_json:
                        # Get internal domains from workspace metadata
                        internal_domains = workspace.metadata_json.get("internal_domains", [])
                        if isinstance(internal_domains, list):
                            # Normalize domains to lowercase
                            internal_domains = [d.lower() for d in internal_domains]
                            return domain not in internal_domains

                # Fallback to environment variable or default
                import os
                default_domains = os.getenv("INTERNAL_EMAIL_DOMAINS", "atom.ai,workspace.local")
                internal_domains = [d.strip().lower() for d in default_domains.split(",")]
                return domain not in internal_domains

            finally:
                if not self.db:
                    db.close()

        # 2. Phone (WhatsApp): External if not in a 'team_numbers' list
        if platform in ["whatsapp", "messenger", "slack"]:
            return params.get("is_internal") is not True

        return True

    async def should_require_approval(self, workspace_id: str, action_type: str, platform: str, params: Dict[str, Any]) -> bool:
        """
        Determines if the action must be paused for HITL review.
        """
        db = self.db or get_db_session()
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
        db = self.db or get_db_session()
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
        Triggers messaging notifications for high-priority actions.
        """
        db = self.db or get_db_session()
        try:
            # 1. Determine Priority
            priority = params.get("priority", "MEDIUM")
            if action_type in ["delete_customer", "wipe_database", "send_mass_email"]:
                priority = "URGENT"
            elif action_type in ["update_billing", "change_role"]:
                priority = "HIGH"

            # 2. Create HITL Record
            hitl_action = HITLAction(
                workspace_id=workspace_id,
                tenant_id=params.get("tenant_id"),
                agent_id=params.get("agent_id"),
                action_type=action_type,
                platform=platform,
                params=params,
                reason=reason,
                status=HITLActionStatus.PENDING.value,
                priority=priority,
                confidence_score=self.get_confidence_score(workspace_id, action_type, platform)
            )
            db.add(hitl_action)
            db.commit()
            db.refresh(hitl_action)
            
            logger.info(f"Created HITL action {hitl_action.id} for workspace {workspace_id} (Priority: {priority})")

            # 3. Trigger Notification if Urgent/High
            if priority in ["HIGH", "URGENT"]:
                await self._notify_governance_channel(db, hitl_action)

            return hitl_action.id
        finally:
            if not self.db:
                db.close()

    async def _notify_governance_channel(self, db, hitl_action: HITLAction):
        """Send notification to the configured governance channel"""
        from core.communication_service import communication_service
        from core.models import TenantSetting
        
        # 1. Get Governance Channel from Tenant Settings
        setting = db.query(TenantSetting).filter(
            TenantSetting.tenant_id == hitl_action.tenant_id,
            TenantSetting.setting_key == "governance_alerts_channel"
        ).first()
        
        if not setting:
            logger.warning(f"No governance_alerts_channel configured for tenant {hitl_action.tenant_id}")
            return

        # 2. Determine Platform (Default to slack if not specified in setting format 'slack:C123...')
        channel_val = setting.setting_value
        source = "slack"
        channel_id = channel_val
        
        if ":" in channel_val:
            source, channel_id = channel_val.split(":", 1)

        # 3. Send Notification
        adapter = communication_service.get_adapter(source)
        details = {
            "action_type": hitl_action.action_type,
            "reason": hitl_action.reason,
            "params": hitl_action.params
        }
        
        success = await adapter.send_approval_request(
            target_id=channel_id,
            action_id=hitl_action.id,
            details=details,
            priority=hitl_action.priority
        )
        
        if success:
            hitl_action.notified_channel_id = f"{source}:{channel_id}"
            db.commit()
            logger.info(f"Sent HITL notification for {hitl_action.id} to {source}:{channel_id}")

# Global governance instance
contact_governance = ContactGovernance()
