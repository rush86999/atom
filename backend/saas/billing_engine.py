import logging
from sqlalchemy.orm import Session
from typing import Dict, Any

from saas.models import SaaSTier
from ecommerce.models import Subscription

logger = logging.getLogger(__name__)

class TieredBillingService:
    def __init__(self, db: Session):
        self.db = db

    def calculate_billable_amount(self, subscription: Subscription, usage_data: Dict[str, float]) -> Dict[str, Any]:
        """
        Calculate total bill based on Tier rules and Usage.
        Returns breakdown: {total: float, breakdown: [...]}
        """
        if not subscription.tier_id:
            # Fallback to MRR if no advanced tier linked
            return {
                "total": subscription.mrr,
                "breakdown": [{"item": "Flat Rate", "amount": subscription.mrr}]
            }
            
        tier = self.db.query(SaaSTier).filter(SaaSTier.id == subscription.tier_id).first()
        if not tier:
             return {"total": subscription.mrr, "error": "Tier not found"}

        total = tier.base_price
        breakdown = [{"item": f"Base Plan ({tier.name})", "amount": total}]
        
        # Calculate Overages
        # 1. API Calls
        api_usage = usage_data.get("api_call", 0)
        api_included = tier.included_api_calls
        if api_usage > api_included:
            overage_qty = api_usage - api_included
            overage_cost = overage_qty * tier.overage_rate_api
            total += overage_cost
            breakdown.append({
                "item": f"API Overage ({int(overage_qty)} calls)",
                "amount": overage_cost
            })
            
        # 2. Seats
        seat_usage = usage_data.get("active_seat", 0) # Assumes 'active_seat' is the metric name
        seats_included = tier.included_seats
        if seat_usage > seats_included:
            overage_qty = seat_usage - seats_included
            overage_cost = overage_qty * tier.overage_rate_seat
            total += overage_cost
            breakdown.append({
                "item": f"Seat Overage ({int(overage_qty)} seats)",
                "amount": overage_cost
            })
            
        return {
            "total": round(total, 2),
            "currency": tier.currency,
            "breakdown": breakdown
        }
