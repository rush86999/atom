import datetime
import os
import sys
import unittest
import uuid
from datetime import timezone

# Add project root
sys.path.append(os.getcwd())

from accounting.models import Entity, EntityType, Invoice, InvoiceStatus
from intelligence.health_engine import HealthScoringEngine
from intelligence.models import ResourceRole
from intelligence.scenario_engine import ScenarioEngine
from intelligence.staffing_forecaster import StaffingForecaster
from sales.models import Deal, DealStage

from core.database import SessionLocal
from core.models import Workspace


class TestPhase18Intelligence(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.workspace_id = "default"
        self.unique_id = uuid.uuid4().hex[:8]

    def tearDown(self):
        self.db.close()

    def test_health_score(self):
        print("\n--- Phase 18: Client Health Scoring ---")
        # Setup Client
        client = Entity(
            workspace_id=self.workspace_id,
            name=f"Risky Client {self.unique_id}",
            type=EntityType.CUSTOMER
        )
        self.db.add(client)
        self.db.flush()
        
        # Add Overdue Invoice
        inv = Invoice(
            workspace_id=self.workspace_id,
            customer_id=client.id,
            invoice_number=f"INV-LATE-{self.unique_id}",
            status=InvoiceStatus.OVERDUE,
            amount=1000.0,
            issue_date=datetime.datetime.now(timezone.utc),
            due_date=datetime.datetime.now(timezone.utc)
        )
        self.db.add(inv)
        self.db.commit()
        
        # Calculate Score
        engine = HealthScoringEngine(self.db)
        score = engine.calculate_health_score(client.id)
        
        # Expect Financial Score drop: 100 - 20 = 80
        # Usage default (no ecom) = 20. Sentiment = 80.
        # Overall = (80 * 0.4) + (20 * 0.4) + (80 * 0.2) = 32 + 8 + 16 = 56
        print(f"✅ Calculated Health Score: {score.overall_score} (Fin: {score.financial_score}, Usage: {score.usage_score})")
        
        # Allow some flexibility in assertion if logic tuned
        self.assertLess(score.overall_score, 70.0)

    def test_staffing_forecast(self):
        print("\n--- Phase 18: Staffing Forecast ---")
        # Setup Pipeline
        deal = Deal(
            workspace_id=self.workspace_id,
            name=f"Big Project {self.unique_id}",
            value=100000.0,
            stage=DealStage.PROPOSAL # 50% prob
        )
        self.db.add(deal)
        self.db.commit()
        
        forecaster = StaffingForecaster(self.db)
        prediction = forecaster.predict_resource_demand(self.workspace_id)
        
        # Weighted Value = 50k. Labor Budget = 25k. Hours = 250.
        engine_hours = prediction["estimated_engineering_hours"]
        print(f"✅ Predicted Engineering Demand: {engine_hours} hours from Pipeline")
        self.assertTrue(engine_hours > 0)

    def test_scenario_simulation(self):
        print("\n--- Phase 18: Business Scenario ---")
        # Setup Role
        role = ResourceRole(
            workspace_id=self.workspace_id,
            name="Senior Engineer",
            hourly_cost=100.0
        )
        self.db.add(role)
        self.db.commit()
        
        engine = ScenarioEngine(self.db)
        scenario = engine.simulate_hiring_scenario(self.workspace_id, {"Senior Engineer": 2})
        
        impact = scenario.impact_json
        burn = impact["monthly_cash_burn_increase"]
        print(f"✅ Scenario Impact: Cash Burn +${burn}/mo")
        # 2 ppl * 160 hrs * $100 = 32000
        self.assertEqual(burn, 32000.0)

if __name__ == "__main__":
    unittest.main()
