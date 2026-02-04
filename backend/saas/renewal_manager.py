import logging
import uuid
from datetime import datetime, timedelta, timezone
from ecommerce.models import Subscription
from sales.models import Deal, DealStage
from sqlalchemy.orm import Session

from core.database import SessionLocal

logger = logging.getLogger(__name__)

class RenewalManager:
    """
    Automates the renewal sales pipeline.
    """

    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()

    def check_upcoming_renewals(self, workspace_id: str = None) -> int:
        """
        Find subscriptions expiring soon and create renewal deals.
        """
        now = datetime.now(timezone.utc)
        renew_threshold = now + timedelta(days=60)
        
        # Find active subscriptions expiring within 60 days that don't already have renewal deals
        query = self.db.query(Subscription).filter(
            Subscription.status == "active",
            Subscription.next_billing_at <= renew_threshold
        )
        if workspace_id:
            query = query.filter(Subscription.workspace_id == workspace_id)
            
        subs = query.all()
        created_count = 0

        for sub in subs:
            # Check if renewal deal already exists in metadata or by name pattern
            existing_deal = self.db.query(Deal).filter(
                Deal.workspace_id == sub.workspace_id,
                Deal.name.like(f"Renewal: %{sub.id[:8]}%"),
                Deal.stage != DealStage.CLOSED_LOST
            ).first()

            if not existing_deal:
                self.create_renewal_deal(sub)
                created_count += 1
        
        self.db.commit()
        return created_count

    def create_renewal_deal(self, sub: Subscription) -> Deal:
        """
        Creates a 'Renewal' type deal in the system.
        """
        deal_value = sub.mrr * 12 if sub.billing_interval == "month" else sub.mrr
        
        renewal_deal = Deal(
            id=str(uuid.uuid4()),
            workspace_id=sub.workspace_id,
            name=f"Renewal: {sub.plan_name} ({sub.id[:8]})",
            value=deal_value,
            stage=DealStage.QUALIFICATION, # Start at qualification for renewal logic
            probability=80.0, # Renewals have higher baseline probability
            metadata_json={
                "type": "RENEWAL",
                "subscription_id": sub.id,
                "customer_id": sub.customer_id
            }
        )
        self.db.add(renewal_deal)
        logger.info(f"Created renewal deal for subscription {sub.id} (Value: {deal_value})")
        return renewal_deal

renewal_manager = RenewalManager()
