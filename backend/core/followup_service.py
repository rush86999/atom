import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List
from sales.models import Deal, NegotiationState

from core.communication_intelligence import CommunicationIntelligenceService
from core.database import get_db_session

logger = logging.getLogger(__name__)

class AutonomousFollowupService:
    """
    Scans for 'Ghosted' deals and triggers proactive nudges.
    """

    def __init__(self, db_session: Any = None, intel_service: Any = None):
        self.db = db_session
        self.intel_service = intel_service or CommunicationIntelligenceService()

    async def scan_and_nudge(self, workspace_id: str):
        """
        Main entry point for the follow-up background worker.
        """
        db = self.db or get_db_session()
        try:
            # Find deals that haven't been engaged in > 48 hours
            # and aren't already WON/LOST
            forty_eight_hours_ago = datetime.utcnow() - timedelta(hours=48)
            
            ghosted_deals = (
                db.query(Deal)
                .filter(Deal.workspace_id == workspace_id)
                .filter(Deal.negotiation_state.notin_([NegotiationState.WON, NegotiationState.LOST]))
                .filter(Deal.last_engagement_at <= forty_eight_hours_ago)
                .all()
            )

            results = []
            for deal in ghosted_deals:
                success = await self._trigger_nudge(deal, db)
                results.append({"deal_id": deal.id, "success": success})
            
            return results
        finally:
            if not self.db:
                db.close()

    async def _trigger_nudge(self, deal: Deal, db: Any) -> bool:
        """
        Generates and dispatches a nudge for a specific deal.
        """
        try:
            logger.info(f"Triggering autonomous nudge for Deal {deal.id} (State: {deal.negotiation_state})")
            
            # Construct context for the nudge
            context = {
                "deal_name": deal.name,
                "negotiation_state": deal.negotiation_state,
                "value": deal.value,
                "nudge_type": "autonomous_followup"
            }
            
            # Use CommunicationIntelligenceService to generate and execute the response
            # Note: In a real system, we'd pull the last thread_id from atom_communications
            comm_data = {
                "content": "[SYSTEM TRIGGER: FOLLOW-UP NUDGE]",
                "metadata": {"deal_id": deal.id, "is_nudge": True},
                "app_type": "email" # Default
            }
            
            # Use analyze_and_route to handle Suggest/Draft/Send modes
            await self.intel_service.analyze_and_route(comm_data, "system")
            
            # Update deal metadata
            deal.last_followup_at = datetime.utcnow()
            deal.followup_count += 1
            db.commit()
            
            return True
        except Exception as e:
            logger.error(f"Failed to nudge deal {deal.id}: {e}")
            return False
