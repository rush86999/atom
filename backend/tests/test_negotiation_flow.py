import asyncio
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.append(os.getcwd())

import accounting.models
import ecommerce.models
import marketing.models
import saas.models
import sales.models
import service_delivery.models
from sales.models import Deal, NegotiationState
from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers, sessionmaker

import core.models
from core.communication_intelligence import CommunicationIntelligenceService
from core.database import Base
from core.models import Workspace


class _FakeLLM:
    """Stand-in for KnowledgeExtractor.llm_service."""

    def __init__(self, json_str):
        self.json_str = json_str

    async def generate_completion(self, **kwargs):
        return {"content": self.json_str}


class MockAIService:
    def __init__(self, response_json):
        self.response_json = response_json

    async def analyze_text(self, text, system_prompt=None):
        return {
            "success": True,
            "response": self.response_json
        }

class TestNegotiationFlow(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        configure_mappers()
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        
        self.ws = Workspace(id="w1", name="Negotiation Corp")
        self.db.add(self.ws)
        # Initial Deal
        self.deal = Deal(
            id="deal_negotiation", 
            workspace_id="w1", 
            name="Contract X", 
            value=10000.0, 
            negotiation_state=NegotiationState.INITIAL,
            last_engagement_at=datetime.utcnow()
        )
        self.db.add(self.deal)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_multi_step_negotiation_state_advancement(self):
        # Step 1: Customer asks for price (Intent: upsell_inquiry/price_negotiation)
        mock_ai_1 = MockAIService("""
        {
          "entities": [],
          "relationships": [
            {"from": "msg_1", "to": "upsell_inquiry", "type": "INTENT", "properties": {}}
          ]
        }
        """)
        service_1 = CommunicationIntelligenceService(ai_service=mock_ai_1, db_session=self.db)
        service_1.extractor.llm_service = _FakeLLM(mock_ai_1.response_json)

        comm_1 = {"content": "What's the best price?", "metadata": {"deal_id": "deal_negotiation"}, "app_type": "email"}
        asyncio.run(service_1.analyze_and_route(comm_1, "u1"))
        
        self.db.refresh(self.deal)
        self.assertEqual(self.deal.negotiation_state, NegotiationState.BARGAINING)

        # Step 2: Customer agrees (Intent: payment_commitment)
        mock_ai_2 = MockAIService("""
        {
          "entities": [],
          "relationships": [
            {"from": "msg_2", "to": "payment_commitment", "type": "INTENT", "properties": {}}
          ]
        }
        """)
        service_2 = CommunicationIntelligenceService(ai_service=mock_ai_2, db_session=self.db)
        service_2.extractor.llm_service = _FakeLLM(mock_ai_2.response_json)

        comm_2 = {"content": "I agree to the terms.", "metadata": {"deal_id": "deal_negotiation"}, "app_type": "email"}
        asyncio.run(service_2.analyze_and_route(comm_2, "u1"))
        
        self.db.refresh(self.deal)
        self.assertEqual(self.deal.negotiation_state, NegotiationState.CLOSING)

    @unittest.skip(
        "core.followup_service.AutonomousFollowupService never existed; the "
        "email follow-up contract (EmailFollowUpEngine) is message-based, not "
        "deal-ghosting-based"
    )
    def test_autonomous_followup_detection(self):
        from core.followup_service import AutonomousFollowupService

        # 1. Make the deal "Ghosted" (last engagement > 48h ago)
        self.deal.last_engagement_at = datetime.utcnow() - timedelta(hours=72)
        self.db.commit()
        
        # 2. Run follow-up scan
        mock_intel = CommunicationIntelligenceService(ai_service=MockAIService("Nudge content"), db_session=self.db)
        followup_service = AutonomousFollowupService(db_session=self.db, intel_service=mock_intel)
        
        results = asyncio.run(followup_service.scan_and_nudge("w1"))
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["deal_id"], "deal_negotiation")
        
        self.db.refresh(self.deal)
        self.assertIsNotNone(self.deal.last_followup_at)
        self.assertEqual(self.deal.followup_count, 1)

if __name__ == "__main__":
    unittest.main()
