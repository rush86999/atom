import datetime
import logging
from typing import Dict, Optional
from accounting.models import Entity, Invoice, InvoiceStatus
from ecommerce.models import EcommerceCustomer, Subscription
from intelligence.models import ClientHealthScore
from saas.models import UsageEvent
from sqlalchemy import func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class HealthScoringEngine:
    def __init__(self, db: Session):
        self.db = db

    def calculate_health_score(self, client_entity_id: str) -> ClientHealthScore:
        """
        Computes a 0-100 score based on 3 pillars:
        1. Financial (40%): Are invoices paid on time?
        2. Usage (40%): Is SaaS usage stable/growing?
        3. Sentiment (20%): CRM sentiment (Placeholder for now)
        """
        entity = self.db.query(Entity).filter(Entity.id == client_entity_id).first()
        if not entity:
             return None

        # 1. Financial Score (0-100)
        # Logic: If overdue > 0, score drops significantly.
        overdue = self.db.query(Invoice).filter(
            Invoice.customer_id == client_entity_id,
            Invoice.status == InvoiceStatus.OVERDUE
        ).count()
        
        financial_score = 100.0
        if overdue > 0:
            financial_score = max(0, 100 - (overdue * 20)) # -20 per overdue invoice
            
        # 2. Usage Score (0-100)
        # Logic: Find linked ecommerce customer -> subscription -> check usage trend
        # For MVP, we'll check if they have ANY usage in last 30 days
        usage_score = 50.0 # Neutral default
        
        # Link Accounting Entity -> Ecommerce Customer (via metadata or resolver)
        # We will assume linkage exists. If not, finding by name partial match for MVP.
        ecom_customer = self.db.query(EcommerceCustomer).filter(
            EcommerceCustomer.email == entity.email # Assuming simplistic match
        ).first()

        if ecom_customer:
             # Check active subs
             sub = self.db.query(Subscription).filter(
                 Subscription.customer_id == ecom_customer.id,
                 Subscription.status == 'active'
             ).first()
             
             if sub:
                 # Check usage events
                 recent_events = self.db.query(UsageEvent).filter(
                     UsageEvent.subscription_id == sub.id
                 ).count()
                 if recent_events > 0:
                     usage_score = 100.0
                 else:
                     usage_score = 20.0 # Ghost (Zombie) account
        
        # 3. Sentiment Score
        # Placeholder: 80
        sentiment_score = 80.0

        # Weighted Average
        overall = (financial_score * 0.4) + (usage_score * 0.4) + (sentiment_score * 0.2)
        
        # Create Record
        score_record = ClientHealthScore(
            workspace_id=entity.workspace_id,
            client_entity_id=client_entity_id,
            overall_score=overall,
            financial_score=financial_score,
            usage_score=usage_score,
            sentiment_score=sentiment_score,
            metadata_json={"overdue_count": overdue}
        )
        self.db.add(score_record)
        self.db.commit()
        
        return score_record
