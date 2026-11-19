
import asyncio
from datetime import datetime, timedelta, timezone
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

        Subscriptions are tenant-keyed while this service is called with a
        workspace id, so the workspace's persisted tenant binding is resolved
        first. An empty, unknown, or unbound workspace refuses the read instead
        of falling back to an unscoped query across every tenant.
        """
        try:
            from core.models import Subscription, Workspace
        except Exception:
            Subscription = None
            Workspace = None

        if self.db is None or Subscription is None or Workspace is None:
            return []

        workspace_key = str(workspace_id or "").strip()
        if not workspace_key:
            logger.warning(
                "Subscription waste requested without a workspace id; "
                "refusing unscoped subscription read.")
            return []

        workspace = (
            self.db.query(Workspace)
            .filter(Workspace.id == workspace_key)
            .first()
        )
        tenant_id = (
            getattr(workspace, "tenant_id", None)
            if workspace is not None
            else None
        )
        if not tenant_id:
            logger.warning(
                "Workspace %s has no tenant binding; refusing unscoped "
                "subscription read.", workspace_key)
            return []

        rows = (
            self.db.query(Subscription)
            .filter(Subscription.tenant_id == str(tenant_id))
            .all()
        )
        zombies: List[Dict[str, Any]] = []
        now = datetime.now(timezone.utc)
        for row in rows:
            status = str(getattr(row, "status", "") or "").lower()
            next_billing = getattr(row, "next_billing_at", None)
            if isinstance(next_billing, datetime):
                if next_billing.tzinfo is None:
                    # Stored timestamps may be naive; treat them as UTC so the
                    # comparison never mixes naive and aware datetimes.
                    next_billing = next_billing.replace(tzinfo=timezone.utc)
                still_billed = next_billing > now
            else:
                still_billed = False
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
