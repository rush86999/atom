import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sales.models import CallTranscript

logger = logging.getLogger(__name__)

class ObjectionService:
    """
    Analyzes sales calls to extract, categorize, and provide rebuttals for objections.
    """
    def __init__(self, db: Session):
        self.db = db

    def track_objection(self, workspace_id: str, deal_id: str, objection_text: str):
        """
        Record a new objection and categorize it using NLP/LLM logic.
        """
        # In a real app, this would use an LLM to categorize the objection
        # Categories: "Pricing", "Timeline", "Competition", "Technical", "Authority"
        
        category = self._categorize_objection(objection_text)
        logger.info(f"Tracking objection for deal {deal_id}: {objection_text} (Category: {category})")
        
        # We could store these in a dedicated Objection model, 
        # but for now, we'll assume they are part of the transcript's metadata 
        # or a general workspace-level library.
        return {
            "text": objection_text,
            "category": category,
            "suggested_response": self.get_suggested_response(objection_text, category)
        }

    def get_suggested_response(self, objection_text: str, category: str = None) -> str:
        """
        Generate a proven rebuttal or counter-point for a given objection.
        """
        if not category:
            category = self._categorize_objection(objection_text)

        rebuttals = {
            "Pricing": "Highlight the TCO (Total Cost of Ownership) and estimated ROI of 300% within 12 months. Mention our flexible monthly billing.",
            "Timeline": "Emphasize our rapid deployment framework which gets 80% of value live in under 14 days. We can start with a pilot for the most critical team.",
            "Competition": "Focus on our unique 'Universal Chat' and integrated 'Workflow Agent' which Competition X lacks. We are the only SOC-2 compliant platform in this niche.",
            "Technical": "Offer a technical deep-dive with our solutions architect. Point to our robust API documentation and integration library with 50+ pre-built connectors.",
            "Authority": "Suggest a high-level executive summary specifically for the CFO/CTO level that highlights business-level impact and safety guardrails."
        }

        return rebuttals.get(category, "Address the concern by asking 'Could you share more about why that is a concern?' followed by a success story from a similar client.")

    def _categorize_objection(self, text: str) -> str:
        text = text.lower()
        if any(w in text for w in ["expensive", "cost", "budget", "price", "money"]):
            return "Pricing"
        if any(w in text for w in ["time", "fast", "slow", "when", "months", "weeks", "long"]):
            return "Timeline"
        if any(w in text for w in ["rival", "competitor", "other guy", "compare"]):
            return "Competition"
        if any(w in text for w in ["api", "integration", "setup", "install", "tech", "security"]):
            return "Technical"
        if any(w in text for w in ["manager", "boss", "owner", "decide", "vp", "cfo"]):
            return "Authority"
        return "General"
