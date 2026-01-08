import unittest
import asyncio
import os
import sys
from datetime import datetime, timedelta
sys.path.append(os.getcwd())

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, configure_mappers
from core.database import Base
import core.models
import sales.models
import saas.models
import ecommerce.models
import accounting.models
import service_delivery.models
from core.models import Workspace, User
from service_delivery.models import Project, Milestone, ProjectTask
from core.workforce_analytics import WorkforceAnalyticsService
from core.resource_reasoning import ResourceReasoningEngine
from core.pm_engine import AIProjectManager

class TestEstimationBias(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        configure_mappers()
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        
        # Setup Data
        self.ws = Workspace(id="w_bias", name="Bias Corp")
        self.db.add(self.ws)
        
        # User 1: Optimistic (Under-estimates, takes 2x time)
        self.u_opt = User(id="u_opt", email="opt@corp.com", first_name="Optimistic", last_name="Oliver", status="active")
        # User 2: Pessimistic (Over-estimates, takes 0.5x time)
        self.u_pess = User(id="u_pess", email="pess@corp.com", first_name="Pessimistic", last_name="Pete", status="active")
        self.db.add_all([self.u_opt, self.u_pess])
        
        self.p1 = Project(id="p1", workspace_id="w_bias", name="Bias Project")
        self.db.add(self.p1)
        self.m1 = Milestone(id="m1", workspace_id="w_bias", project_id="p1", name="M1")
        self.db.add(self.m1)
        
        # Seed Tasks for Oliver (Optimistic) - Duration Bias ~2.0
        now = datetime.now()
        for i in range(5):
            created = now - timedelta(days=10)
            due = now - timedelta(days=5) # Planned 5 days
            completed = now # Actual 10 days (2x bias)
            
            task = ProjectTask(
                id=f"t_opt_{i}",
                workspace_id="w_bias", project_id="p1", milestone_id="m1",
                name=f"Opt Task {i}", status="completed", assigned_to="u_opt",
                created_at=created, due_date=due, completed_at=completed
            )
            self.db.add(task)
            
        # Seed Tasks for Pete (Pessimistic) - Duration Bias ~0.5
        for i in range(5):
            created = now - timedelta(days=10)
            due = now # Planned 10 days
            completed = now - timedelta(days=5) # Actual 5 days (0.5x bias)
            
            task = ProjectTask(
                id=f"t_pess_{i}",
                workspace_id="w_bias", project_id="p1", milestone_id="m1",
                name=f"Pess Task {i}", status="completed", assigned_to="u_pess",
                created_at=created, due_date=due, completed_at=completed
            )
            self.db.add(task)
            
        self.db.commit()
        
        self.analytics = WorkforceAnalyticsService(db_session=self.db)
        self.reasoning = ResourceReasoningEngine(db_session=self.db)
        self.pm = AIProjectManager(db_session=self.db)

    def tearDown(self):
        self.db.close()

    def test_calculate_bias_factors(self):
        # 1. Test Oliver (Optimistic)
        opt_bias = self.analytics.calculate_estimation_bias("w_bias", "u_opt")
        self.assertEqual(opt_bias["category"], "optimistic")
        self.assertGreaterEqual(opt_bias["bias_factor"], 1.4) # Weighted avg of 2.0 (duration) and 1.0 (hour) = 1.4
        
        # 2. Test Pete (Pessimistic)
        pess_bias = self.analytics.calculate_estimation_bias("w_bias", "u_pess")
        self.assertEqual(pess_bias["category"], "pessimistic")
        self.assertLessEqual(pess_bias["bias_factor"], 0.8) # Weighted avg of 0.5 (duration) and 1.0 (hour) = 0.8
        
        # 3. Test Workspace Bias
        ws_bias = self.analytics.calculate_estimation_bias("w_bias")
        self.assertAlmostEqual(ws_bias["bias_factor"], 1.1, delta=0.1) # Avg of 1.4 and 0.8 is 1.1

    def test_resource_reasoning_bias_penalty(self):
        # Both share identical skills for this test
        self.u_opt.skills = "Python"
        self.u_pess.skills = "Python"
        self.db.commit()
        
        # Suggest assignee for a Python task
        # Pete should win because Oliver takes 2x longer (bias penalty)
        result = asyncio.run(self.reasoning.get_optimal_assignee("w_bias", "Python Task"))
        
        self.assertEqual(result["suggested_user"]["user_id"], "u_pess")
        self.assertGreater(result["suggested_user"]["composite_score"], 0)

    def test_pm_duration_adjustment(self):
        from unittest.mock import patch, MagicMock, AsyncMock
        
        # Mock AI response
        mock_ai_response = {
            "nlu_result": {
                "name": "Biased Project",
                "planned_duration_days": 10,
                "milestones": []
            }
        }
        
        # Using AsyncMock for async method
        with patch.object(self.pm.ai, 'process_with_nlu', new_callable=AsyncMock) as mock_nlu:
            mock_nlu.return_value = mock_ai_response
            
            # Force workspace bias to be 2.0 for clear test
            with patch.object(self.analytics, 'calculate_estimation_bias', return_value={"bias_factor": 2.0}):
                # We need to ensure the pm engine uses our mocked analytics
                self.pm.analytics = self.analytics
                
                # Create project
                result = asyncio.run(self.pm.generate_project_from_nl("Make a project", "user_1", "w_bias"))
                
                # Verify project duration in DB is 20 days (10 planned * 2.0 bias)
                project = self.db.query(Project).filter(Project.id == result["project_id"]).first()
                delta = (project.planned_end_date - project.planned_start_date).days
                self.assertEqual(delta, 20)

if __name__ == "__main__":
    unittest.main()
