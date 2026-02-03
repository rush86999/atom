import logging
from typing import Any, Dict
from ecommerce.models import Subscription
from saas.models import SaaSTier
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class TieredBillingService:
    def __init__(self, db: Session):
        self.db = db

    def calculate_overages(self, subscription_id: str) -> Dict[str, Any]:
        """
        Public method to calculate overages for an active subscription.
        """
        sub = self.db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if not sub:
             return {"error": "Subscription not found"}
        
        usage = sub.current_period_usage or {}
        return self.calculate_billable_amount(sub, usage)

    def _calculate_metric_cost(self, usage: float, included: float, flat_rate: float, tiered_config: list = None) -> Dict[str, Any]:
        """Helper to calculate cost for a single metric with tier support."""
        if usage <= included:
            return {"overage_qty": 0, "amount": 0}
        
        overage_qty = usage - included
        
        # Simple flat rate if no tiered config
        if not tiered_config:
            return {
                "overage_qty": overage_qty,
                "amount": round(overage_qty * flat_rate, 2)
            }
        
        # Tiered logic
        # tiered_config: [{"limit": 1000, "rate": 0.05}, {"limit": 10000, "rate": 0.01}, {"limit": -1, "rate": 0.005}]
        total_cost = 0.0
        remaining_overage = overage_qty
        
        for tier in tiered_config:
            limit = tier.get("limit", -1)
            rate = tier.get("rate", 0.0)
            
            if limit == -1 or remaining_overage <= limit:
                total_cost += remaining_overage * rate
                remaining_overage = 0
                break
            else:
                total_cost += limit * rate
                remaining_overage -= limit
        
        return {
            "overage_qty": overage_qty,
            "amount": round(total_cost, 2)
        }

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
        pricing_config = tier.pricing_config or {}
        
        # 1. API Calls
        api_usage = usage_data.get("api_call", 0)
        api_calc = self._calculate_metric_cost(
            api_usage, 
            tier.included_api_calls, 
            tier.overage_rate_api, 
            pricing_config.get("api_call")
        )
        if api_calc["amount"] > 0:
            total += api_calc["amount"]
            breakdown.append({
                "item": f"API Overage ({int(api_calc['overage_qty'])} calls)",
                "amount": api_calc["amount"]
            })
            
        # 2. Seats
        seat_usage = usage_data.get("active_seat", 0)
        seat_calc = self._calculate_metric_cost(
            seat_usage, 
            tier.included_seats, 
            tier.overage_rate_seat, 
            pricing_config.get("active_seat")
        )
        if seat_calc["amount"] > 0:
            total += seat_calc["amount"]
            breakdown.append({
                "item": f"Seat Overage ({int(seat_calc['overage_qty'])} seats)",
                "amount": seat_calc["amount"]
            })
            
        # 3. Storage
        storage_usage = usage_data.get("storage_gb", 0)
        storage_calc = self._calculate_metric_cost(
            storage_usage, 
            tier.included_storage_gb, 
            tier.overage_rate_storage, 
            pricing_config.get("storage_gb")
        )
        if storage_calc["amount"] > 0:
            total += storage_calc["amount"]
            breakdown.append({
                "item": f"Storage Overage ({round(storage_calc['overage_qty'], 2)} GB)",
                "amount": storage_calc["amount"]
            })
            
        return {
            "total": round(total, 2),
            "currency": tier.currency,
            "breakdown": breakdown
        }
