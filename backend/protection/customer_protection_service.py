
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from sales.models import Deal, DealStage, Lead, LeadStatus
from ecommerce.models import EcommerceCustomer, EcommerceOrder

logger = logging.getLogger(__name__)

class CustomerProtectionService:
    def __init__(self, db: Session):
        self.db = db

    def predict_churn_risk(self, workspace_id: str = "default") -> List[Dict[str, Any]]:
        """
        Identifies customers/leads with dropping engagement.
        Rule: No engagement for > 30 days on active deals or leads.
        """
        risks = []
        
        # 1. Check Stalled Deals (Mid-funnel but ghosted)
        stalled_deals = self.db.query(Deal).filter(
            Deal.workspace_id == workspace_id,
            Deal.stage.in_([DealStage.DISCOVERY, DealStage.QUALIFICATION, DealStage.PROPOSAL, DealStage.NEGOTIATION]),
            Deal.last_engagement_at < datetime.utcnow() - timedelta(days=30)
        ).all()
        
        for deal in stalled_deals:
            days_silent = (datetime.utcnow() - deal.last_engagement_at).days if deal.last_engagement_at else 30
            risks.append({
                "type": "stalled_deal",
                "entity_name": deal.name,
                "risk_score": min(days_silent, 100), # Cap at 100
                "details": f"No engagement for {days_silent} days. Deal Value: ${deal.value}",
                "action": "Schedule check-in execution."
            })

        # 2. Check "Ghost" Leads (New but untouched)
        ghost_leads = self.db.query(Lead).filter(
            Lead.workspace_id == workspace_id,
            Lead.status == LeadStatus.NEW,
            Lead.updated_at < datetime.utcnow() - timedelta(days=45)
        ).all()
        
        for lead in ghost_leads:
            risks.append({
                "type": "ghost_lead",
                "entity_name": lead.email,
                "risk_score": 80,
                "details": "New lead untouched for 45+ days.",
                "action": "Add to re-engagement drip."
            })

        return sorted(risks, key=lambda x: x['risk_score'], reverse=True)

    def prioritize_vips(self, workspace_id: str = "default") -> List[Dict[str, Any]]:
        """
        Identifies High Value Customers needing attention.
        Rule: Top 10% by LTV or Deal Value.
        """
        vips = []
        
        # 1. High Value Deals
        big_deals = self.db.query(Deal).filter(
            Deal.workspace_id == workspace_id,
            Deal.value > 10000, # Mock threshold, real world would use percentile
            Deal.status != "closed_lost" # Assuming we want active or won
        ).order_by(Deal.value.desc()).limit(10).all()
        
        for deal in big_deals:
            vips.append({
                "name": deal.name,
                "value": deal.value,
                "type": "Active Deal",
                "status": "VIP"
            })
            
        return vips
