import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.append(os.getcwd())

import accounting.models
import ecommerce.models
import marketing.models
import saas.models
import sales.models
import service_delivery.models
from marketing.intelligence_service import MarketingIntelligenceService
from marketing.models import AdSpendEntry, AttributionEvent, MarketingChannel
from sales.models import Lead
from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers, sessionmaker

import core.models
from core.database import Base
from core.models import Workspace


class TestMarketingIntelligence(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        configure_mappers()
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        
        # Setup Workspace
        self.ws = Workspace(id="w1", name="Growth Corp")
        self.db.add(self.ws)
        
        # Setup Channels
        self.google = MarketingChannel(id="ch_google", workspace_id="w1", name="Google Ads", type="paid_search")
        self.linkedin = MarketingChannel(id="ch_linkedin", workspace_id="w1", name="LinkedIn Ads", type="paid_social")
        self.db.add_all([self.google, self.linkedin])
        
        # Setup Ad Spend
        self.db.add(AdSpendEntry(
            workspace_id="w1", channel_id="ch_google", amount=1000.0, date=datetime.now(timezone.utc) - timedelta(days=5)
        ))
        self.db.add(AdSpendEntry(
            workspace_id="w1", channel_id="ch_linkedin", amount=2000.0, date=datetime.now(timezone.utc) - timedelta(days=5)
        ))
        
        # Setup Leads
        self.l1 = Lead(id="l1", workspace_id="w1", email="l1@test.com", is_converted=True, updated_at=datetime.now(timezone.utc))
        self.l2 = Lead(id="l2", workspace_id="w1", email="l2@test.com", is_converted=True, updated_at=datetime.now(timezone.utc))
        self.db.add_all([self.l1, self.l2])
        
        # Setup Attribution Events (Conversions)
        self.db.add(AttributionEvent(workspace_id="w1", lead_id="l1", channel_id="ch_google", event_type="conversion"))
        self.db.add(AttributionEvent(workspace_id="w1", lead_id="l2", channel_id="ch_linkedin", event_type="conversion"))
        
        # Touchpoints
        self.db.add(AttributionEvent(workspace_id="w1", lead_id="l1", channel_id="ch_google", event_type="touchpoint"))
        self.db.add(AttributionEvent(workspace_id="w1", lead_id="l2", channel_id="ch_linkedin", event_type="touchpoint"))
        
        self.db.commit()
        self.service = MarketingIntelligenceService(self.db)

    def tearDown(self):
        self.db.close()

    def test_cac_calculation(self):
        # Total spend = 1000 + 2000 = 3000
        # Total converted leads = 2
        # CAC = 3000 / 2 = 1500
        result = self.service.calculate_cac("w1")
        self.assertEqual(result["total_spend"], 3000.0)
        self.assertEqual(result["new_customers"], 2)
        self.assertEqual(result["cac"], 1500.0)

    def test_channel_performance(self):
        performance = self.service.get_channel_performance("w1")
        
        # Check Google
        google_stats = next(p for p in performance if p["channel_name"] == "Google Ads")
        self.assertEqual(google_stats["spend"], 1000.0)
        self.assertEqual(google_stats["conversions"], 1)
        self.assertEqual(google_stats["cpa"], 1000.0)
        
        # Check LinkedIn
        linkedin_stats = next(p for p in performance if p["channel_name"] == "LinkedIn Ads")
        self.assertEqual(linkedin_stats["spend"], 2000.0)
        self.assertEqual(linkedin_stats["conversions"], 1)
        self.assertEqual(linkedin_stats["cpa"], 2000.0)

    def test_record_touchpoint(self):
        self.service.record_touchpoint(lead_id="l1", workspace_id="w1", channel_name="Organic Search", utm_params={"utm_source": "google"})
        
        # Verify event created
        event = self.db.query(AttributionEvent).join(MarketingChannel).filter(
            AttributionEvent.lead_id == "l1",
            MarketingChannel.name == "Organic Search"
        ).first()
        
        self.assertIsNotNone(event)
        self.assertEqual(event.touchpoint_order, 2) # l1 already had 1 touchpoint in setUp
        self.assertEqual(event.source, "google")

if __name__ == "__main__":
    unittest.main()
