import asyncio
import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.append(os.getcwd())

import accounting.models
import ecommerce.models
import marketing.models
import saas.models
import sales.models
import service_delivery.models
from sales.models import Deal
from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers, sessionmaker

import core.models
from core.communication_intelligence import CommunicationIntelligenceService
from core.database import Base
from core.models import Workspace


class MockAIService:
    async def analyze_text(self, text, system_prompt=None):
        # Simulate extraction of a Deal link and decision
        if system_prompt and ("entities" in system_prompt or "entities" in text.lower()):
            return {
                "success": True,
                "response": """
                {
                  "entities": [
                    {"id": "d1", "type": "Deal", "properties": {"name": "Big Contract", "external_id": "ext_deal_123", "value": 5000.0}},
                    {"id": "p1", "type": "Person", "properties": {"name": "Alice", "role": "Stakeholder"}}
                  ],
                  "relationships": [
                    {"from": "msg_1", "to": "approval", "type": "INTENT", "properties": {"confidence": 0.95}},
                    {"from": "msg_1", "to": "ext_deal_123", "type": "LINKS_TO_EXTERNAL", "properties": {}}
                  ]
                }
                """
            }
        return {"success": True, "response": "Suggested: Let's finalize the Big Contract ($5k)."}

class TestCommunicationIntelligence(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        configure_mappers()
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        
        # Setup Workspace & Deal
        self.ws = Workspace(id="w1", name="Intel Corp")
        self.db.add(self.ws)
        self.deal = Deal(id="deal_1", workspace_id="w1", name="Big Contract", value=5000.0, external_id="ext_deal_123", stage="negotiation")
        self.db.add(self.deal)
        self.db.commit()
        
        self.mock_ai = MockAIService()
        self.service = CommunicationIntelligenceService(ai_service=self.mock_ai, db_session=self.db)

    def tearDown(self):
        self.db.close()

    def test_analyze_and_route_suggest(self):
        # Mock settings to 'suggest'
        from core.automation_settings import get_automation_settings
        settings = get_automation_settings()
        settings.update_settings({"response_control_mode": "suggest"})
        
        comm_data = {
            "id": "msg_1",
            "content": "Let's move forward with the $5k deal.",
            "app_type": "email",
            "metadata": {"user_id": "u1"}
        }
        
        result = asyncio.run(self.service.analyze_and_route(comm_data, "u1"))
        
        # Verify extraction
        self.assertEqual(len(result["knowledge"]["entities"]), 2)
        # Verify cross-system enrichment
        self.assertIn("deal_deal_1", result["enriched_context"])
        self.assertEqual(result["enriched_context"]["deal_deal_1"]["value"], 5000.0)
        self.assertEqual(result["response_mode"], "suggest")

    def test_response_mode_settings(self):
        from core.automation_settings import get_automation_settings
        settings = get_automation_settings()
        
        # Test Draft mode
        settings.update_settings({"response_control_mode": "draft"})
        comm_data = {"id": "msg_2", "content": "Hello", "app_type": "slack", "metadata": {}}
        
        result = asyncio.run(self.service.analyze_and_route(comm_data, "u1"))
        self.assertEqual(result["response_mode"], "draft")

if __name__ == "__main__":
    unittest.main()
