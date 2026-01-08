import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, configure_mappers
import uuid
from datetime import datetime

# Import models
from core.database import Base
import core.models
import service_delivery.models
import sales.models
import accounting.models

from service_delivery.models import Project, Milestone, ProjectTask, Contract, ContractType
from sales.models import Deal, DealStage
from core.pm_orchestrator import PMOrchestrator

class TestCRMToDelivery(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Setup in-memory SQLite for testing
        self.engine = create_engine("sqlite:///:memory:")
        configure_mappers()
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        
        self.user_id = "test_user_crm"
        self.workspace_id = "test_workspace_crm"
        
        # Patch SessionLocal in pm_orchestrator and pm_engine
        self.patcher_db = patch("core.pm_orchestrator.SessionLocal", return_value=self.db)
        self.patcher_db.start()
        
        self.pm_orch = PMOrchestrator()

    async def asyncTearDown(self):
        self.db.close()
        self.patcher_db.stop()

    @patch("core.pm_orchestrator.pm_engine")
    @patch("core.pm_orchestrator.graphrag_engine")
    async def test_provision_from_deal(self, mock_graphrag, mock_pm_engine):
        # 1. Setup Mock Deal
        deal_id = f"deal_{uuid.uuid4().hex[:8]}"
        deal = Deal(
            id=deal_id,
            workspace_id=self.workspace_id,
            name="Test Enterprise Cloud Migration",
            value=100000.0,
            currency="USD",
            stage=DealStage.CLOSED_WON
        )
        self.db.add(deal)
        self.db.commit()
        
        # 2. Mock PM Engine response
        mock_pm_engine.generate_project_from_nl = AsyncMock(return_value={
            "status": "success",
            "project_id": "proj_mock_123",
            "name": "Cloud Migration Project"
        })
        
        # 3. Mock GraphRAG for stakeholders
        mock_graphrag.query = MagicMock(return_value={
            "entities": [
                {"name": "Alice Stakeholder", "type": "person"},
                {"name": "Bob Tech Lead", "type": "person"}
            ]
        })
        
        # 4. Execute Provisioning
        result = await self.pm_orch.provision_from_deal(deal_id, self.user_id, self.workspace_id)
        
        # 5. Verify Results
        self.assertEqual(result["status"], "success")
        self.assertIn("contract_id", result)
        self.assertIn("project_id", result)
        self.assertEqual(len(result["stakeholders_identified"]), 2)
        self.assertIn("Alice Stakeholder", result["stakeholders_identified"])
        
        # Check DB for Contract
        contract = self.db.query(Contract).filter(Contract.deal_id == deal_id).first()
        self.assertIsNotNone(contract)
        self.assertEqual(contract.total_amount, 100000.0)
        
        print("\n[SUCCESS] CRM to Delivery Provisioning Verified.")

if __name__ == "__main__":
    unittest.main()
