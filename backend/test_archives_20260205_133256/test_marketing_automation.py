import asyncio
import unittest
from typing import Any, Dict
import accounting.models
import ecommerce.models
import saas.models
import sales.models
import service_delivery.models
from ecommerce.models import EcommerceCustomer
from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers, sessionmaker

import core.models
from core.database import Base
from core.marketing_agent import MarketingAgent, RetentionEngine
from core.marketing_analytics import MarketingIntelligence
from core.models import Workspace
from integrations.google_business_profile import GoogleBusinessProfileClient


class MockAIService:
    async def analyze_text(self, text, system_prompt=None):
        if "marketing metrics" in text.lower():
            return {"success": True, "response": "NARRATIVE: Google is performing much better than Facebook."}
        return {"success": True, "response": "Mocked AI Response"}

class TestMarketingAutomation(unittest.TestCase):
    def setUp(self):
        # Fresh in-memory database for each test
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        configure_mappers()
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        
        self.ai = MockAIService()
        self.marketing_agent = MarketingAgent(ai_service=self.ai, db_session=self.db)
        self.marketing_intel = MarketingIntelligence(ai_service=self.ai, db_session=self.db)
        self.gbp = GoogleBusinessProfileClient()
    
        # Setup workspace and customer
        self.workspace = Workspace(id="w_marketing", name="Marketing Test")
        self.db.add(self.workspace)
        self.db.commit()

        self.customer = EcommerceCustomer(id="cust_marketing", workspace_id="w_marketing", email="marketing@example.com")
        self.db.add(self.customer)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_review_routing(self):
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.marketing_agent.trigger_review_request("cust_marketing", "w_marketing"))
        
        self.assertEqual(result["status"], "success")
        self.assertIn("leave us a review", result["message"]) # Should be positive by default

    def test_rebooking_logic(self):
        engine = RetentionEngine(db_session=self.db)
        loop = asyncio.get_event_loop()
        opportunities = loop.run_until_complete(engine.scan_for_rebooking_opportunities("w_marketing"))
        
        self.assertIsInstance(opportunities, list)

    def test_narrative_analytics(self):
        loop = asyncio.get_event_loop()
        report = loop.run_until_complete(self.marketing_intel.generate_narrative_report("w_marketing"))
        
        self.assertIn("NARRATIVE:", report)
        self.assertIn("Google", report)

    def test_gbp_automation(self):
        loop = asyncio.get_event_loop()
        post_res = loop.run_until_complete(self.gbp.post_update("5 new projects completed!"))
        qa_res = loop.run_until_complete(self.gbp.monitor_qa())
        
        self.assertEqual(post_res["status"], "success")
        self.assertTrue(len(qa_res) > 0)

if __name__ == "__main__":
    unittest.main()
