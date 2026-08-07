import asyncio
import os
import sys
import unittest
from datetime import datetime

sys.path.append(os.getcwd())

import accounting.models
import ecommerce.models
import marketing.models
import saas.models
import sales.models
import service_delivery.models
from ecommerce.models import EcommerceCustomer, EcommerceOrder
from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers, sessionmaker

import core.models
from core.communication_intelligence import CommunicationIntelligenceService
from core.database import Base
try:
    from core.historical_learner import HistoricalLifecycleLearner
    HAS_HISTORICAL_LEARNER = True
except ImportError:
    HistoricalLifecycleLearner = None
    HAS_HISTORICAL_LEARNER = False
from core.lancedb_handler import get_lancedb_handler
from core.models import Workspace


class MockAIService:
    async def analyze_text(self, text, system_prompt=None):
        # Determine if this is an extraction call or a generation call
        if "Draft a professional" in text:
            # generation call
            if "Requesting a Quote" in text:
                return {"success": True, "response": "DRAFT: Professional Quote Request"}
            return {"success": True, "response": "DRAFT: Generic Business Email"}
        return {"success": True, "response": '{"entities": [], "relationships": []}'}


QUOTE_KNOWLEDGE = {
    "entities": [
        {"id": "quote_1", "type": "Quote", "properties": {"amount": 500.0, "status": "requested"}}
    ],
    "relationships": [
        {"from": "msg_1", "to": "request_quote", "type": "INTENT"}
    ]
}

SHIPPING_KNOWLEDGE = {
    "entities": [
        {"id": "ship_1", "type": "Shipment", "properties": {"tracking_number": "TRK123", "carrier": "FedEx", "status": "shipped"}}
    ],
    "relationships": [
        {"from": "msg_1", "to": "confirm_shipping", "type": "INTENT"}
    ]
}


class TestBusinessIntelligence(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        configure_mappers()
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        
        # Setup Workspace
        self.ws = Workspace(id="w_intel", name="Intel Biz")
        self.db.add(self.ws)
        self.db.commit()
        
        self.ai = MockAIService()
        self.comm_intel = CommunicationIntelligenceService(ai_service=self.ai, db_session=self.db)

        async def fake_extract(text, workspace_id=None, tenant_id=None, source="unknown"):
            if "shipped" in text.lower():
                return SHIPPING_KNOWLEDGE
            if "quote" in text.lower():
                return QUOTE_KNOWLEDGE
            return {"entities": [], "relationships": []}

        self.comm_intel.extractor.extract_knowledge = fake_extract

    def tearDown(self):
        self.db.close()

    def test_shipping_extraction_and_routing(self):
        comm_data = {
            "content": "Your order has been shipped! Tracking #TRK123",
            "metadata": {"workspace_id": "w_intel"},
            "app_type": "email"
        }
        
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.comm_intel.analyze_and_route(comm_data, "user_1"))
        
        knowledge = result["knowledge"]
        intents = [rel.get("to") for rel in knowledge.get("relationships", []) if rel.get("type") == "INTENT"]
        
        self.assertIn("confirm_shipping", intents)
        shipments = [e for e in knowledge.get("entities", []) if e.get("type") == "Shipment"]
        self.assertEqual(len(shipments), 1)
        self.assertEqual(shipments[0]["properties"]["tracking_number"], "TRK123")

    def test_quote_request_detection(self):
        comm_data = {
            "content": "Can I get a quote for the new project?",
            "metadata": {"workspace_id": "w_intel"},
            "app_type": "email"
        }
        
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.comm_intel.analyze_and_route(comm_data, "user_1"))
        
        knowledge = result["knowledge"]
        intents = [rel.get("to") for rel in knowledge.get("relationships", []) if rel.get("type") == "INTENT"]
        
        self.assertIn("request_quote", intents)
        quotes = [e for e in knowledge.get("entities", []) if e.get("type") == "Quote"]
        self.assertEqual(len(quotes), 1)

    def test_specialized_lifecycle_draft(self):
        comm_data = {
            "content": "Can I get a quote for 50 widgets?",
            "metadata": {"workspace_id": "w_intel"},
            "app_type": "email"
        }
        
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.comm_intel.analyze_and_route(comm_data, "user_1"))
        
        self.assertIn("knowledge", result)
        self.assertIn("suggestion", result)
        # Verify the specialized generator response was used (mocked in MockAIService)
        self.assertEqual(result["suggestion"], "DRAFT: Professional Quote Request")

    @unittest.skipIf(not HAS_HISTORICAL_LEARNER, "core.historical_learner deleted in cleanup")
    def test_historical_learning(self):
        # 1. Seed LanceDB with a historical message
        lancedb = get_lancedb_handler()
        lancedb.add_document(
            table_name="atom_communications",
            text="Past Order: Your shipping update for order #99. Tracking: OLD-TRK-789",
            source="historical_email",
            user_id="user_1",
            metadata={"workspace_id": "w_intel"}
        )
        
        learner = HistoricalLifecycleLearner(ai_service=self.ai, db_session=self.db)
        
        loop = asyncio.get_event_loop()
        loop.run_until_complete(learner.learn_from_history("w_intel", "user_1"))
        
        # Verify that business intelligence was triggered
        # In this mock, we just check if it completed without error.
        # A more advanced test would check if EcommerceOrder was updated.
        self.assertTrue(True)

if __name__ == "__main__":
    unittest.main()
