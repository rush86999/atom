"""
HITL Service - Centralized resolution logic for Human-in-the-Loop actions.
Handles approvals, rejections, 2FA enforcement, and workflow resumption.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from core.database import get_db_session
from core.models import HITLAction, HITLActionStatus, User
from core.communication_service import communication_service

logger = logging.getLogger(__name__)

class HITLService:
    """
    Manages the lifecycle of HITL actions after they are created.
    """

    async def resolve_action(
        self,
        action_id: str,
        resolution: str,
        resolver_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Resolves a pending HITL action.
        
        Returns:
            Dict containing final status and any required next steps (e.g. 2FA).
        """
        with get_db_session() as db:
            action = db.query(HITLAction).filter(HITLAction.id == action_id).first()
            if not action:
                raise ValueError(f"HITL Action {action_id} not found")

            if action.status in [HITLActionStatus.APPROVED.value, HITLActionStatus.REJECTED.value]:
                return {"status": action.status, "message": "Action already resolved"}

            user = db.query(User).filter(User.id == resolver_id).first()
            if not user:
                raise ValueError(f"Resolver user {resolver_id} not found")

            # 1. Handle Rejection
            if resolution == "rejected":
                action.status = HITLActionStatus.REJECTED.value
                action.resolver_id = resolver_id
                action.resolved_at = datetime.now(timezone.utc)
                db.commit()
                logger.info(f"HITL Action {action_id} REJECTED by {user.email}")
                return {"status": "rejected"}

            # 2. Check for 2FA Enforcement (Phase 5)
            # High-stakes actions (URGENT priority) require 2FA if enabled for user
            if action.priority == "URGENT" and user.two_factor_enabled:
                # Check session/metadata for recent 2FA verification
                # For now, we transition to PENDING_2FA and prompt
                verified_2fa = metadata.get("verified_2fa", False) if metadata else False
                
                if not verified_2fa:
                    action.status = HITLActionStatus.PENDING_2FA.value
                    db.commit()
                    logger.info(f"HITL Action {action_id} requires 2FA from {user.email}")
                    
                    # Notify user to verify 2FA
                    await self._prompt_for_2fa(action, user)
                    return {"status": "pending_2fa", "message": "2FA verification required"}

            # 3. Handle Approval
            action.status = HITLActionStatus.APPROVED.value
            action.resolver_id = resolver_id
            action.resolved_at = datetime.now(timezone.utc)
            db.commit()
            
            logger.info(f"HITL Action {action_id} APPROVED by {user.email}")

            # 4. Resume Workflow (Phase 4)
            # This would typically notify the waiting agent or trigger a QStash callback
            await self._resume_workflow(action)

            return {"status": "approved"}

    async def _prompt_for_2fa(self, action: HITLAction, user: User):
        """Send a 2FA verification prompt to the user"""
        source = "slack"
        channel_id = None
        
        if action.notified_channel_id and ":" in action.notified_channel_id:
            source, channel_id = action.notified_channel_id.split(":", 1)
        
        if not channel_id:
            return

        msg = (
            f"🔒 *2FA Required*: The action `{action.action_type}` is marked as high-stakes.\n"
            f"Please verify your identity to proceed. [Link to 2FA Dashboard]"
        )
        
        adapter = communication_service.get_adapter(source)
        await adapter.send_message(channel_id, msg)

    async def _resume_workflow(self, action: HITLAction):
        """Notify the system that the action is approved and can proceed"""
        # Logic to unblock the agent that called request_approval
        # In the current sync implementation, request_approval waits on an event or polling.
        # For async persistence, we would trigger the callback URL if provided.
        logger.info(f"Resuming workflow for action {action.id}")
        
        # Placeholder for actual resumption logic (e.g. QStash/Redis trigger)
        # If the action has a callback_url in params, we hit it.
        callback_url = (action.params or {}).get("callback_url")
        if callback_url:
            import httpx
            async with httpx.AsyncClient() as client:
                try:
                    await client.post(callback_url, json={
                        "action_id": action.id,
                        "status": "approved",
                        "resolver_id": action.resolver_id
                    })
                except Exception as e:
                    logger.error(f"Failed to trigger HITL callback: {e}")

# Singleton
hitl_service = HITLService()
