
import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class VendorIntelligenceService:
    def __init__(self, db: Session = None):
        self.db = db

    async def detect_price_drift(self, workspace_id: str) -> List[Dict[str, Any]]:
        """
        Analyzes vendor spend to find price increases.

        Returns only recorded accounting rows. This used to return a hardcoded
        AWS/Figma story whenever no keys were configured, which presented
        invented spend as a live finding. With no accounting integration the
        honest result is empty; the caller surfaces "not connected".
        """
        logger.info(
            "No accounting integration is connected for workspace %s; "
            "vendor price drift has no recorded rows.", workspace_id)
        return []

class PricingAdvisorService:
    def __init__(self, db: Session = None):
        self.db = db

    async def get_pricing_recommendations(self, workspace_id: str) -> List[Dict[str, Any]]:
        """
        Identifies products/services with sub-optimal margins from recorded
        product rows. Returns [] when no product catalogue is loaded; the
        caller labels the state instead of inventing consulting-hour advice.
        """
        try:
            from core.models import BusinessProductService
        except Exception:
            BusinessProductService = None

        if self.db is None or BusinessProductService is None:
            return []

        rows = (
            self.db.query(BusinessProductService)
            .filter(BusinessProductService.workspace_id == workspace_id)
            .all()
        )
        recs: List[Dict[str, Any]] = []
        for row in rows:
            price = getattr(row, "base_price", None) or getattr(row, "price", None)
            cost = getattr(row, "unit_cost", None) or getattr(row, "cost", None)
            if price is None or cost is None or not price:
                continue
            margin = (float(price) - float(cost)) / float(price)
            if margin < 0.35:
                target = float(cost) / 0.6 if cost else float(price) * 1.25
                recs.append({
                    "sku": getattr(row, "id", None) or getattr(row, "sku", ""),
                    "item": getattr(row, "name", None) or getattr(row, "item", "Recorded item"),
                    "current_price": round(float(price), 2),
                    "target_price": round(target, 2),
                    "margin_impact": f"{(target - float(price)):+.2f} per unit",
                    "reason": f"Recorded gross margin is {margin:.0%}, below the 35% threshold.",
                    "confidence": "Recorded data",
                })
        return recs

class SubscriptionWasteService:
    def __init__(self, db: Session = None):
        self.db = db

    async def find_zombie_subscriptions(self, workspace_id: str) -> List[Dict[str, Any]]:
        """
        Correlates billing with usage. Without a connected billing source (or
        recorded subscription rows) there is nothing to report; this used to
        return a fictional Adobe subscription as a live saving.
        """
        try:
            from core.models import Subscription
        except Exception:
            Subscription = None

        if self.db is None or Subscription is None:
            return []

        rows = self.db.query(Subscription).all()
        zombies: List[Dict[str, Any]] = []
        now = datetime.now()
        for row in rows:
            status = str(getattr(row, "status", "") or "").lower()
            next_billing = getattr(row, "next_billing_at", None)
            still_billed = bool(next_billing and next_billing > now)
            if status in {"canceled", "cancelled"} and still_billed:
                zombies.append({
                    "subscription_id": getattr(row, "id", ""),
                    "service_name": getattr(row, "plan_name", None)
                    or "Recorded subscription",
                    "mrr": float(getattr(row, "mrr", 0) or 0),
                    "reason": "Recorded as canceled but still scheduled to bill.",
                })
        return zombies

def get_forensics_services(db: Session = None):
    return {
        "vendor": VendorIntelligenceService(db),
        "pricing": PricingAdvisorService(db),
        "waste": SubscriptionWasteService(db)
    }
