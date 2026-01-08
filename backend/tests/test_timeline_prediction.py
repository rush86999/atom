import unittest
import os
import sys
from datetime import datetime, timedelta
sys.path.append(os.getcwd())

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, configure_mappers
from core.database import Base
import core.models
import ecommerce.models
import sales.models
import saas.models
import marketing.models
import accounting.models
import service_delivery.models
from core.models import Workspace, User
from service_delivery.models import Project, ProjectTask, Milestone
from core.timeline_prediction import TimelinePredictionService
from core.risk_forecaster import ProjectRiskForecaster

class MockAnalyticsService:
    def calculate_team_velocity(self, workspace_id: str, days: int = 30):
        # Mock velocity: 0.5 tasks/day = 2 hours/day (assuming 4h/task)
        return {"throughput_per_day": 0.5}

class MockReasoningEngine:
    def __init__(self, high_risk_user=None):
        self.high_risk_user = high_risk_user

    def assess_burnout_risk(self, user_id: str):
        if user_id == self.high_risk_user:
            return {"risk_level": "high"}
        return {"risk_level": "low"}

class TestTimelinePrediction(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        configure_mappers()
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        
        # Setup Data
        self.ws = Workspace(id="w_predict", name="Predict Corp")
        self.db.add(self.ws)
        
        self.u1 = User(id="u_busy", email="busy@corp.com", first_name="Bob", last_name="Busy")
        self.db.add(self.u1)
        
        self.p1 = Project(
            id="p_forecast", 
            workspace_id="w_predict", 
            name="Alpha Launch",
            planned_end_date=datetime.utcnow() + timedelta(days=5) # Tight deadline
        )
        self.db.add(self.p1)
        
        self.m1 = Milestone(id="m_forecast", workspace_id="w_predict", project_id="p_forecast", name="M1")
        self.db.add(self.m1)
        
        # Add 10 pending tasks (40 hours of work)
        for i in range(10):
            task = ProjectTask(
                workspace_id="w_predict", project_id="p_forecast", milestone_id="m_forecast",
                name=f"Task {i}", status="pending", assigned_to="u_busy"
            )
            self.db.add(task)
            
        self.db.commit()
        
        # Services
        self.analytics = MockAnalyticsService()
        self.prediction = TimelinePredictionService(db_session=self.db, analytics_service=self.analytics)
        self.reasoning = MockReasoningEngine(high_risk_user="u_busy")
        self.forecaster = ProjectRiskForecaster(db_session=self.db, reasoning_engine=self.reasoning)

    def tearDown(self):
        self.db.close()

    def test_timeline_prediction(self):
        # 40 hours of work / (0.5 tasks/day * 4 hours/task = 2h/day) = 20 days
        predicted_date = self.prediction.predict_completion("p_forecast")
        
        self.assertIsNotNone(predicted_date)
        delta_days = (predicted_date - datetime.utcnow()).days
        # Should be roughly 20 days from now
        self.assertGreaterEqual(delta_days, 19)
        self.assertLessEqual(delta_days, 21)

    def test_risk_forecasting(self):
        # First predict completion
        self.prediction.predict_completion("p_forecast")
        
        # Now evaluate risks
        risk_data = self.forecaster.evaluate_risks("p_forecast")
        
        self.assertEqual(risk_data["risk_level"], "high")
        self.assertIn("Predicted delay", risk_data["rationale"])
        self.assertIn("burnout risk", risk_data["rationale"].lower())
        self.assertIn("Scope Smog", risk_data["rationale"])

if __name__ == "__main__":
    unittest.main()
