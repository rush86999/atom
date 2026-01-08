import unittest
import asyncio
from datetime import datetime
from core.budget_guardrail import BudgetGuardrailService
from core.change_order_agent import ChangeOrderAgent
from service_delivery.models import Project, ProjectTask, BudgetStatus, Contract
from accounting.models import Transaction, Entity, EntityType
from core.models import Workspace, User
from core.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, configure_mappers
import core.models
import ecommerce.models
import saas.models
import sales.models
import accounting.models
import service_delivery.models

class MockAIService:
    async def analyze_text(self, text, system_prompt=None):
        return {"success": True, "response": "Mocked AI Response for Change Order"}
    
    async def extract_structured_data(self, text, schema_prompt=None):
        return {"entities": []}

class TestBudgetGuardrails(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        configure_mappers()
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        
        self.ai = MockAIService()
        self.guardrail = BudgetGuardrailService(db_session=self.db)
        self.agent = ChangeOrderAgent(ai_service=self.ai)
        
        # Setup data
        self.ws = Workspace(id="w_guard", name="Guardrail Workspace")
        self.user = User(id="u_dev", email="dev@atom.ai", hourly_cost_rate=100.0)
        self.db.add_all([self.ws, self.user])
        
        self.project = Project(
            id="p_guard", 
            workspace_id="w_guard", 
            name="Construction Project",
            budget_amount=1000.0
        )
        self.db.add(self.project)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_project_burn_logic(self):
        loop = asyncio.get_event_loop()
        
        # 1. Add Labor Burn ($500)
        task = ProjectTask(
            id="t1", 
            workspace_id="w_guard", 
            project_id="p_guard", 
            milestone_id="m1", 
            name="Build Foundation",
            actual_hours=5.0,
            assigned_to="u_dev"
        )
        self.db.add(task)
        
        # 2. Add Expense Burn ($400)
        tx = Transaction(
            id="tx1",
            workspace_id="w_guard",
            project_id="p_guard",
            amount=400.0,
            transaction_date=datetime.now(),
            source="manual"
        )
        self.db.add(tx)
        self.db.commit()
        
        # 3. Calculate Burn
        result = loop.run_until_complete(self.guardrail.calculate_project_burn("p_guard"))
        
        self.assertEqual(result["labor_burn"], 500.0)
        self.assertEqual(result["expense_burn"], 400.0)
        self.assertEqual(result["total_burn"], 900.0)
        self.assertEqual(result["status"], "at_risk") # 90% of $1000

    def test_change_order_trigger(self):
        loop = asyncio.get_event_loop()
        
        # Push project over budget ($1100 total)
        tx = Transaction(
            id="tx_over",
            workspace_id="w_guard",
            project_id="p_guard",
            amount=1100.0,
            transaction_date=datetime.now(),
            source="manual"
        )
        self.db.add(tx)
        self.db.commit()
        
        # Run guardrail to update status
        loop.run_until_complete(self.guardrail.calculate_project_burn("p_guard"))
        
        from unittest.mock import patch
        with patch('core.change_order_agent.SessionLocal', return_value=self.db), \
             patch('core.lifecycle_comm_generator.SessionLocal', return_value=self.db):
            
            result = loop.run_until_complete(self.agent.analyze_and_trigger("p_guard", "w_guard"))
            
            self.assertIsNotNone(result)
            self.assertIn("change_order_content", result)
            self.assertEqual(result["suggested_status"], "PAUSED_CLIENT")

if __name__ == "__main__":
    unittest.main()
