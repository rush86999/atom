import os
import sys
import unittest

sys.path.append(os.getcwd())

from datetime import datetime, timedelta, timezone
import accounting.models
import ecommerce.models
import saas.models
import sales.models
import service_delivery.models
from ecommerce.models import EcommerceCustomer, Subscription
from saas.models import SaaSTier, UsageEvent
from saas.renewal_manager import RenewalManager
from saas.retention_service import RetentionService
from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers, sessionmaker

import core.models
from core.database import Base
from core.models import Team, Workspace


class TestSaaSRetentionAndRenewals(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        configure_mappers()
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        
        # Setup Workspace & Team
        self.ws = Workspace(id="w1", name="Retention Corp")
        self.db.add(self.ws)
        self.team = Team(id="t1", workspace_id="w1", name="CS Team")
        self.db.add(self.team)
        
        # Setup Customer
        self.customer = EcommerceCustomer(id="c1", workspace_id="w1", email="churn@risk.com")
        self.db.add(self.customer)
        
        # Setup Subscription
        self.sub = Subscription(
            id="s_expiring",
            workspace_id="w1",
            customer_id="c1",
            plan_name="Enterprise",
            mrr=5000.0,
            status="active",
            billing_interval="year",
            next_billing_at=datetime.now(timezone.utc) + timedelta(days=45) # Expiring soon
        )
        self.db.add(self.sub)
        
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_churn_detection_velocity(self):
        now = datetime.now(timezone.utc)
        # Period 2 (30-60 days ago): High usage
        for i in range(10):
            self.db.add(UsageEvent(
                subscription_id="s_expiring",
                workspace_id="w1",
                event_type="api_call",
                quantity=10.0,
                timestamp=now - timedelta(days=45)
            ))
        
        # Period 1 (0-30 days ago): Low usage (Velocity drop)
        self.db.add(UsageEvent(
            subscription_id="s_expiring",
            workspace_id="w1",
            event_type="api_call",
            quantity=10.0,
            timestamp=now - timedelta(days=5)
        ))
        self.db.commit()

        service = RetentionService(self.db)
        flagged = service.run_daily_churn_check("w1")
        
        self.assertEqual(flagged, 1)
        self.db.refresh(self.customer)
        self.assertEqual(self.customer.risk_level, "high")
        
        # Verify alert message
        from core.models import TeamMessage
        msg = self.db.query(TeamMessage).filter(TeamMessage.content.contains("RETENTION ALERT")).first()
        self.assertIsNotNone(msg)

    def test_renewal_opportunity_automation(self):
        manager = RenewalManager(self.db)
        created = manager.check_upcoming_renewals("w1")
        
        self.assertEqual(created, 1)
        
        from sales.models import Deal
        deal = self.db.query(Deal).filter(Deal.name.contains("Renewal")).first()
        self.assertIsNotNone(deal)
        self.assertEqual(deal.value, 5000.0) # Annual sub
        self.assertEqual(deal.metadata_json["subscription_id"], "s_expiring")

if __name__ == "__main__":
    unittest.main()
