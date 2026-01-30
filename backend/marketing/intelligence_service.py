import logging
from sqlalchemy import func
from sqlalchemy.orm import Session
from marketing.models import MarketingChannel, AdSpendEntry, AttributionEvent
from sales.models import Lead, Deal
from ecommerce.models import EcommerceOrder
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class MarketingIntelligenceService:
    def __init__(self, db: Session):
        self.db = db

    def calculate_cac(self, workspace_id: str = "default", days: int = 30) -> Dict[str, Any]:
        """
        Calculates Customer Acquisition Cost (CAC) for a given period.
        CAC = Total Marketing Spend / Total New Customers
        """
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        # 1. Get total spend
        total_spend = self.db.query(func.sum(AdSpendEntry.amount)).filter(
            AdSpendEntry.workspace_id == workspace_id,
            AdSpendEntry.date >= start_date
        ).scalar() or 0.0

        # 2. Get new customers (converted leads)
        # We define a "customer" as a converted lead that has at least one order
        new_customer_count = self.db.query(Lead).filter(
            Lead.workspace_id == workspace_id,
            Lead.is_converted == True,
            Lead.updated_at >= start_date
        ).count()

        cac = total_spend / new_customer_count if new_customer_count > 0 else total_spend

        return {
            "total_spend": total_spend,
            "new_customers": new_customer_count,
            "cac": cac,
            "period_days": days
        }

    def get_channel_performance(self, workspace_id: str = "default") -> List[Dict[str, Any]]:
        """
        Ranks channels by conversion rate and ROI.
        """
        channels = self.db.query(MarketingChannel).filter(MarketingChannel.workspace_id == workspace_id).all()
        results = []

        for channel in channels:
            spend = self.db.query(func.sum(AdSpendEntry.amount)).filter(
                AdSpendEntry.channel_id == channel.id
            ).scalar() or 0.0

            leads_count = self.db.query(AttributionEvent).filter(
                AttributionEvent.channel_id == channel.id,
                AttributionEvent.event_type == "touchpoint"
            ).count()

            conversions_count = self.db.query(AttributionEvent).filter(
                AttributionEvent.channel_id == channel.id,
                AttributionEvent.event_type == "conversion"
            ).count()

            conversion_rate = (conversions_count / leads_count * 100) if leads_count > 0 else 0.0
            cpa = (spend / conversions_count) if conversions_count > 0 else spend

            results.append({
                "channel_name": channel.name,
                "spend": spend,
                "leads": leads_count,
                "conversions": conversions_count,
                "conversion_rate": conversion_rate,
                "cpa": cpa
            })

        return sorted(results, key=lambda x: x["conversions"], reverse=True)

    def record_touchpoint(self, lead_id: str, workspace_id: str = "default", channel_name: str = "direct", utm_params: Dict[str, str] = None):
        """
        Records a marketing touchpoint for a lead.
        """
        # Find or create channel
        channel = self.db.query(MarketingChannel).filter(
            MarketingChannel.workspace_id == workspace_id,
            MarketingChannel.name == channel_name
        ).first()

        if not channel:
            channel = MarketingChannel(
                workspace_id=workspace_id,
                name=channel_name,
                type="direct" # Default
            )
            self.db.add(channel)
            self.db.flush()

        # Find touchpoint order
        existing_touches = self.db.query(AttributionEvent).filter(
            AttributionEvent.lead_id == lead_id,
            AttributionEvent.event_type == "touchpoint"
        ).count()

        event = AttributionEvent(
            workspace_id=workspace_id,
            lead_id=lead_id,
            channel_id=channel.id,
            event_type="touchpoint",
            touchpoint_order=existing_touches + 1,
            source=utm_params.get("utm_source") if utm_params else None,
            medium=utm_params.get("utm_medium") if utm_params else None,
            campaign=utm_params.get("utm_campaign") if utm_params else None
        )
        self.db.add(event)
        self.db.commit()


