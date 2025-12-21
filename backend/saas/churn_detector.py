import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from saas.models import UsageEvent
from ecommerce.models import Subscription
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

class ChurnRiskDetector:
    def __init__(self, db: Session):
        self.db = db

    def analyze_usage_trend(self, current_usage: Dict[str, float], previous_usage: Dict[str, float]) -> Dict[str, Any]:
        """
        Detects churn risk based on usage drop.
        """
        metrics = ["api_call", "active_seat", "login", "storage_gb"]
        drops = []
        risk_score = 0
        
        for metric in metrics:
            curr = current_usage.get(metric, 0)
            prev = previous_usage.get(metric, 0)
            
            if prev > 2: # Minor usage filtering
                drop_pct = (prev - curr) / prev
                if drop_pct > 0.40: # High risk
                    drops.append(f"{metric} critical drop ({int(drop_pct*100)}%)")
                    risk_score += 80
                elif drop_pct > 0.15: # Warning
                    drops.append(f"{metric} declining ({int(drop_pct*100)}%)")
                    risk_score += 15
            
        if risk_score >= 40:
            return {
                "risk_level": "high",
                "risk_score": min(risk_score, 100),
                "reason": ", ".join(drops)
            }
        elif risk_score > 0:
            return {
                "risk_level": "medium",
                "risk_score": risk_score,
                "reason": ", ".join(drops)
            }
            
        return {
            "risk_level": "low",
            "risk_score": 5,
            "reason": "Stable usage"
        }

    def predict_churn_risk(self, subscription_id: str) -> Dict[str, Any]:
        """
        Compares current period usage vs previous period usage from events.
        """
        sub = self.db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if not sub:
            return {"error": "Subscription not found"}

        now = datetime.now(timezone.utc)
        # Previous 30 days vs 30-60 days ago
        p1_start = now - timedelta(days=30)
        p2_start = now - timedelta(days=60)
        
        def get_usage(start, end):
            results = self.db.query(
                UsageEvent.event_type,
                func.sum(UsageEvent.quantity)
            ).filter(
                UsageEvent.subscription_id == subscription_id,
                UsageEvent.timestamp >= start,
                UsageEvent.timestamp < end
            ).group_by(UsageEvent.event_type).all()
            return {r[0]: r[1] for r in results}

        from sqlalchemy import func
        curr_usage = get_usage(p1_start, now)
        prev_usage = get_usage(p2_start, p1_start)
        
        return self.analyze_usage_trend(curr_usage, prev_usage)
