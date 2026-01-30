
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from operations.business_health_service import BusinessHealthService
from finance.forensics_service import FinancialForensicsService
from protection.customer_protection_service import CustomerProtectionService

logger = logging.getLogger(__name__)

class SystemIntelligenceService:
    def __init__(self, db: Session):
        self.db = db
        self.health_service = BusinessHealthService(db)
        self.forensics_service = FinancialForensicsService(db)
        self.protection_service = CustomerProtectionService(db)

    def get_aggregated_context(self, workspace_id: str = "default") -> str:
        """
        Aggregates critical business intelligence into a natural language summary
        for the Main Chat agent.
        """
        context_parts = []
        
        # 1. Business Health
        try:
            health = self.health_service.get_business_health_score(workspace_id)
            score = health.get("score", 0)
            status = health.get("status", "Unknown")
            context_parts.append(f"Business Health is {status} (Score: {score}/100).")
        except Exception as e:
            logger.error(f"Error fetching health context: {e}")

        # 2. Daily Priorities
        try:
            priorities = self.health_service.get_daily_priorities(workspace_id)
            if priorities:
                top_3 = ", ".join([p["title"] for p in priorities[:3]])
                context_parts.append(f"Top priorities today: {top_3}.")
        except Exception as e:
            logger.error(f"Error fetching priority context: {e}")

        # 3. Financial Alerts
        try:
            drift = self.forensics_service.analyze_vendor_price_drift(workspace_id)
            if drift:
                vendors = ", ".join([d["vendor_name"] for d in drift])
                context_parts.append(f"ALERT: Price drift detected for {vendors}.")
        except Exception as e:
            logger.error(f"Error fetching forensics context: {e}")

        # 4. Risk / Churn
        try:
            churn = self.protection_service.predict_churn_risk(workspace_id)
            if churn:
                risky_clients = ", ".join([c["client_name"] for c in churn])
                context_parts.append(f"WARNING: Churn risk detected for {risky_clients}.")
        except Exception as e:
            logger.error(f"Error fetching churn context: {e}")

        return " ".join(context_parts)
