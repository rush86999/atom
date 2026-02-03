import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel

from sqlalchemy.orm import Session
from core.database import get_db_session

# Import domain services
from core.risk_prevention import customer_protection, early_warning
from core.financial_forensics import get_forensics_services
from core.business_health_service import business_health_service

logger = logging.getLogger(__name__)

class Intervention(BaseModel):
    id: str
    type: str # URGENT, OPPORTUNITY, AUTOMATION
    title: str
    description: str
    suggested_action: str # e.g., 'draft_email', 'create_task', 'pause_ads'
    action_payload: Dict[str, Any] = {}
    status: str = "PENDING"
    created_at: str = datetime.now().isoformat()

class CrossSystemReasoningEngine:
    """
    The 'Brain' that connects dots between Marketing, Finance, and Risk.
    Generates Active Interventions.
    """
    
    def __init__(self, db: Session = None):
        self._db = db

    @property
    def db(self):
        return self._db or get_db_session()

    async def generate_interventions(self, workspace_id: str) -> List[Intervention]:
        """
        Analyzes cross-domain signals to propose interventions.
        """
        db = self.db
        interventions = []
        
        try:
            # 1. Gather Signals
            # Risk Signals
            churn_risk = await customer_protection.get_churn_risk(db, workspace_id)
            ar_alerts = await early_warning.get_ar_alerts(db, workspace_id)
            
            # Financial Signals
            forensics = get_forensics_services(db)
            waste = await forensics["waste"].find_zombie_subscriptions(workspace_id)
            
            # Growth Signals (from Business Health / Leads)
            priorities_data = await business_health_service.get_daily_priorities(workspace_id)
            priorities = priorities_data.get("priorities", [])
            
            logger.info(f"[DEBUG] Churn Risk: {churn_risk}")
            logger.info(f"[DEBUG] AR Alerts: {ar_alerts}")
            logger.info(f"[DEBUG] Waste: {waste}")
            logger.info(f"[DEBUG] Priorities: {len(priorities)}")
            
            # 2. Correlate & Reason
            
            # Scenario A: High Churn Risk (Risk) + No Engagement (derived from risk data)
            # If high value client is at risk, trigger urgent retention
            for risk in churn_risk:
                if risk.get("risk_level") == "HIGH":
                    interventions.append(Intervention(
                        id=str(uuid.uuid4()),
                        type="URGENT",
                        title=f"Retention Alert: {risk['client_name']}",
                        description=f"High-value client (${risk['value']:,}) silent for {risk['days_silent']} days. Immediate outreach required.",
                        suggested_action="draft_retention_email",
                        action_payload={"client_name": risk['client_name'], "deal_id": risk['deal_id']}
                    ))

            # Scenario B: Financial Waste (Finance) -> Auto-Fix
            # If zombie sub detected, offer to cancel
            for item in waste:
                interventions.append(Intervention(
                    id=str(uuid.uuid4()),
                    type="AUTOMATION",
                    title=f"Cancel Unused SaaS: {item['service_name']}",
                    description=f"Stop bleeding money. You are paying ${item['mrr']}/mo for a service marked as zombie.",
                    suggested_action="cancel_subscription",
                    action_payload={"subscription_id": item['subscription_id'], "service_name": item['service_name']}
                ))

            # Scenario C: Cash Flow Pressure (AR Alerts) + Growth Opportunities (Priorities)
            # If AR is high (cash trapped) AND we have high-intent leads (need resources to close),
            # priority is collecting cash to fuel sales.
            total_overdue = sum(a['amount'] for a in ar_alerts)
            high_value_leads = [p for p in priorities if p['type'] == 'GROWTH']
            
            if total_overdue > 5000 and len(high_value_leads) > 0:
                interventions.append(Intervention(
                    id=str(uuid.uuid4()),
                    type="OPPORTUNITY",
                    title="Unlock Cash for Growth",
                    description=f"You have ${total_overdue:,} in overdue invoices. Collecting this will fund your pursuit of {len(high_value_leads)} hot leads.",
                    suggested_action="bulk_remind_invoices",
                    action_payload={"invoice_ids": [a['id'] for a in ar_alerts]}
                ))
                
        except Exception as e:
            logger.error(f"Error generating interventions: {e}")
        finally:
            if not self._db:
                db.close()
                
        return interventions
