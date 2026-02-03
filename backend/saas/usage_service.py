import datetime
import logging
from datetime import timezone
from typing import Dict, Optional
from ecommerce.models import Subscription
from saas.models import UsageEvent
from sqlalchemy import func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class UsageMeteringService:
    def __init__(self, db: Session):
        self.db = db

    def ingest_event(self, subscription_id: str, event_type: str, quantity: float = 1.0, metadata: dict = None) -> UsageEvent:
        """
        Record a usage event and update the subscription cache.
        """
        sub = self.db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if not sub:
            logger.error(f"Subscription {subscription_id} not found")
            return None
            
        # 1. Store Raw Event
        event = UsageEvent(
            workspace_id=sub.workspace_id,
            subscription_id=subscription_id,
            event_type=event_type,
            quantity=quantity,
            metadata_json=metadata,
            timestamp=datetime.datetime.now(timezone.utc)
        )
        self.db.add(event)
        
        # 2. Update Cache (Atomic Increment approach is better, but JSON update is MVP)
        current_usage = sub.current_period_usage or {}
        current_val = current_usage.get(event_type, 0.0)
        current_usage[event_type] = current_val + quantity
        
        # Re-assign to trigger SQL update for JSON
        sub.current_period_usage = dict(current_usage)
        
        self.db.commit()
        return event

    def get_aggregated_usage(self, subscription_id: str, start_date: datetime.datetime, end_date: datetime.datetime) -> Dict[str, float]:
        """
        Sum usage by type for a given period.
        """
        results = self.db.query(
            UsageEvent.event_type,
            func.sum(UsageEvent.quantity)
        ).filter(
            UsageEvent.subscription_id == subscription_id,
            UsageEvent.timestamp >= start_date,
            UsageEvent.timestamp <= end_date
        ).group_by(UsageEvent.event_type).all()
        
        return {r[0]: r[1] for r in results}
