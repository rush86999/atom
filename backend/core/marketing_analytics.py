import logging
import json
from typing import Dict, Any, List
from core.database import SessionLocal
from sales.models import Lead, Deal
from accounting.models import Transaction

logger = logging.getLogger(__name__)

class MarketingIntelligence:
    """
    Provides plain-English marketing insights for small business owners.
    """

    def __init__(self, ai_service: Any = None, db_session: Any = None):
        self.ai = ai_service
        self.db = db_session

    async def generate_narrative_report(self, workspace_id: str) -> str:
        """
        Converts marketing metrics into a human-readable narrative.
        """
        # 1. Gather raw data (simulated for prototype)
        # In a real system, we'd query Lead sources, Deal conversions, and Ad spend.
        metrics = {
            "google_calls": 12,
            "facebook_calls": 1,
            "top_source": "Google Business Profile",
            "weekly_leads": 15,
            "conversion_rate": "20%"
        }
        
        # 2. Use AI to generate narrative if available
        prompt = f"""
        Convert the following marketing metrics into a short, plain-English summary for a small business owner.
        Metrics: {json.dumps(metrics)}
        
        Instructions:
        - Be direct and helpful.
        - Recommend where to spend more or less.
        - Avoid marketing jargon.
        """
        
        if self.ai and hasattr(self.ai, 'analyze_text'):
            res = await self.ai.analyze_text(prompt)
            return res.get("response", "Marketing summary not available.")
            
        # Fallback template
        return f"Google brought {metrics['google_calls']} calls last week, while Facebook only brought {metrics['facebook_calls']}. Your top performing source is {metrics['top_source']}. We recommend shifting more focus toward Google."

    def calculate_cac_ltv(self, workspace_id: str) -> Dict[str, float]:
        """
        Calculates basic Customer Acquisition Cost and Lifetime Value.
        """
        # Placeholder for complex financial math
        return {"cac": 50.0, "ltv": 250.0, "roi": 5.0}
