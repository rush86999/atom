import logging
import uuid
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

from ecommerce.models import Subscription, SubscriptionAudit, EcommerceCustomer, EcommerceOrder

logger = logging.getLogger(__name__)

class SubscriptionService:
    def __init__(self, db: Session):
        self.db = db

    def create_or_update_subscription(self, workspace_id: str, customer_id: str, 
                                      external_id: str, plan_name: str, 
                                      price: float, interval: str = "month",
                                      status: str = "active") -> Subscription:
        """
        Creates a new subscription or updates an existing one based on external_id.
        Logs audit events for MRR changes.
        """
        sub = self.db.query(Subscription).filter(
            Subscription.workspace_id == workspace_id,
            Subscription.external_id == external_id
        ).first()

        old_mrr = 0.0
        new_mrr = price if interval == "month" else price / 12.0
        
        if sub:
            old_mrr = sub.mrr
            # Update existing
            sub.plan_name = plan_name
            sub.mrr = new_mrr
            sub.status = status
            sub.billing_interval = interval
            sub.updated_at = datetime.now(timezone.utc)
            
            event_type = "update"
            if status == "canceled" and sub.status != "canceled":
                event_type = "churn"
                sub.canceled_at = datetime.now(timezone.utc)
            elif new_mrr > old_mrr:
                event_type = "upgrade"
            elif new_mrr < old_mrr:
                event_type = "downgrade"
                
        else:
            # Create new
            sub = Subscription(
                id=str(uuid.uuid4()),
                workspace_id=workspace_id,
                customer_id=customer_id,
                external_id=external_id,
                plan_name=plan_name,
                mrr=new_mrr,
                status=status,
                billing_interval=interval,
                next_billing_at=datetime.now(timezone.utc) + timedelta(days=30 if interval == "month" else 365) 
            )
            self.db.add(sub)
            event_type = "new_business"

        self.db.flush() # get ID

        # Log Audit if MRR changed or status changed
        if abs(new_mrr - old_mrr) > 0.01 or event_type in ["churn", "new_business"]:
            audit = SubscriptionAudit(
                subscription_id=sub.id,
                event_type=event_type,
                previous_mrr=old_mrr,
                new_mrr=new_mrr if status != "canceled" else 0.0,
                metadata_json={"plan": plan_name, "reason": "sync_update"}
            )
            self.db.add(audit)
        
        self.db.commit()
        self.db.refresh(sub)
        logger.info(f"Processed subscription {sub.id}: {event_type} (MRR: {old_mrr} -> {new_mrr})")
        return sub

    def process_recurring_order(self, order: EcommerceOrder) -> Optional[Subscription]:
        """
        Links an order to a subscription and updates next billing date.
        Assumes order has metadata or logic to identify it as recurring.
        """
        if not order.customer_id:
            return None
            
        # Simplified: Find the active subscription for this customer with matching value?
        # In robust systems, the webhook payload tells us the subscription_id
        # Here we'll do a basic lookup
        
        sub = self.db.query(Subscription).filter(
            Subscription.customer_id == order.customer_id,
            Subscription.status == "active"
        ).first() # Assuming single sub for now
        
        if sub:
            order.subscription_id = sub.id
            # Advance billing date
            if sub.billing_interval == "month":
                 sub.next_billing_at = (sub.next_billing_at or datetime.now(timezone.utc)) + timedelta(days=30)
            
            self.db.add(order)
            self.db.commit()
            return sub
            
        return None

    def get_analytics(self, workspace_id: str) -> Dict[str, float]:
        """Returns MRR, ARR, and Active Subscriber count"""
        subs = self.db.query(Subscription).filter(
            Subscription.workspace_id == workspace_id,
            Subscription.status == "active"
        ).all()
        
        total_mrr = sum(s.mrr for s in subs)
        return {
            "total_mrr": total_mrr,
            "total_arr": total_mrr * 12,
            "active_subscribers": len(subs)
        }
