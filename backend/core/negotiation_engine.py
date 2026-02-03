import logging
from typing import Dict, Any, Optional, List
from sales.models import Deal, NegotiationState
from core.database import get_db_session
from datetime import datetime

logger = logging.getLogger(__name__)

class NegotiationStateMachine:
    """
    Manages the lifecycle of a business negotiation.
    Advances state based on communication signals and intents.
    """
    
    STATE_TRANSITIONS = {
        NegotiationState.INITIAL: ["discovery", "bargaining", "lost"],
        NegotiationState.DISCOVERY: ["bargaining", "lost"],
        NegotiationState.BARGAINING: ["closing", "lost"],
        NegotiationState.CLOSING: ["won", "lost"],
        NegotiationState.FOLLOW_UP: ["discovery", "bargaining", "closing", "lost"]
    }

    def __init__(self, db_session: Any = None):
        self.db = db_session

    def update_deal_state(self, deal_id: str, signals: List[str]) -> NegotiationState:
        """
        Calculates and updates the next state for a deal based on AI signals.
        Signals: list of intents (e.g., ['upsell_inquiry', 'meeting_request'])
        """
        db = self.db or get_db_session()
        try:
            deal = db.query(Deal).filter(Deal.id == deal_id).first()
            if not deal:
                logger.error(f"Deal {deal_id} not found for state update")
                return None

            current_state = deal.negotiation_state
            next_state = self._calculate_next_state(current_state, signals)

            if next_state and next_state != current_state:
                logger.info(f"Advancing Deal {deal_id} from {current_state} to {next_state}")
                deal.negotiation_state = next_state
                deal.last_engagement_at = datetime.now()
                db.commit()
                return next_state
            
            return current_state
        finally:
            if not self.db:
                db.close()

    def _calculate_next_state(self, current: NegotiationState, signals: List[str]) -> NegotiationState:
        """
        Heuristic logic to advance negotiation state.
        """
        # Intent-driven transitions
        if "payment_commitment" in signals or "approval" in signals:
            return NegotiationState.CLOSING
        
        if "upsell_inquiry" in signals or "price_negotiation" in signals:
            return NegotiationState.BARGAINING
            
        if "meeting_request" in signals:
            if current == NegotiationState.INITIAL:
                return NegotiationState.DISCOVERY
        
        if "lost_interest" in signals or "unsubscribe" in signals:
            return NegotiationState.LOST

        return current

    def get_strategy_prompt(self, deal_id: str) -> str:
        """
        Returns a customized system prompt for the AI based on the current negotiation state.
        """
        db = self.db or get_db_session()
        try:
            deal = db.query(Deal).filter(Deal.id == deal_id).first()
            state = deal.negotiation_state if deal else NegotiationState.INITIAL
            
            strategies = {
                NegotiationState.INITIAL: "Goal: Establish initial rapport and qualify requirements.",
                NegotiationState.DISCOVERY: "Goal: Uncover pain points, budget, and decision-making process.",
                NegotiationState.BARGAINING: "Goal: Negotiate terms while protecting margin. Focus on value over price.",
                NegotiationState.CLOSING: "Goal: Finalize paperwork and secure signature. Address last-minute friction.",
                NegotiationState.FOLLOW_UP: "Goal: Gently nudge for a response without being intrusive.",
                NegotiationState.WON: "Goal: Onboard the client and ensure successful handoff.",
                NegotiationState.LOST: "Goal: Conduct an exit survey and preserve the relationship for future."
            }
            
            return strategies.get(state, "Goal: Advance the conversation.")
        finally:
            if not self.db:
                db.close()
