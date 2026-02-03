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
from service_delivery.models import Milestone, Project, ProjectTask
from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers, sessionmaker

import core.models
from core.database import Base
from core.models import Team, User, Workspace
from core.resource_reasoning import ResourceReasoningEngine
from core.workforce_analytics import WorkforceAnalyticsService


class TestWorkforceIntelligence(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        configure_mappers()
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        
        # Setup Data
        self.ws = Workspace(id="w_workforce", name="Workforce Corp")
        self.db.add(self.ws)
        
        # 2 Users: Expert and Loader
        self.u1 = User(id="u_expert", email="expert@corp.com", first_name="Alice", last_name="Expert", skills="Python, AI")
        self.u2 = User(id="u_loader", email="loader@corp.com", first_name="Bob", last_name="Loader", skills="Java")
        self.db.add_all([self.u1, self.u2])
        
        self.p1 = Project(id="p1", workspace_id="w_workforce", name="AI Integration")
        self.db.add(self.p1)
        self.m1 = Milestone(id="m1", workspace_id="w_workforce", project_id="p1", name="M1")
        self.db.add(self.m1)
        
        self.db.commit()
        
        self.analytics = WorkforceAnalyticsService(db_session=self.db)
        self.reasoning = ResourceReasoningEngine(db_session=self.db)

    def tearDown(self):
        self.db.close()

    def test_bottleneck_detection(self):
        # Assign 6 tasks to Bob (User 2)
        for i in range(6):
            task = ProjectTask(
                workspace_id="w_workforce", project_id="p1", milestone_id="m1",
                name=f"Task {i}", status="in_progress", assigned_to="u_loader"
            )
            self.db.add(task)
        self.db.commit()
        
        bottlenecks = self.analytics.detect_bottlenecks("w_workforce")
        self.assertTrue(any(b["user_id"] == "u_loader" for b in bottlenecks))
        self.assertEqual(bottlenecks[0]["reason"], "high_workload")

    def test_resource_matching(self):
        # Alice is the expert for 'Python AI'
        # Bob already has load
        task = ProjectTask(
            workspace_id="w_workforce", project_id="p1", milestone_id="m1",
            name="New AI Task", status="pending"
        )
        self.db.add(task)
        self.db.commit()
        
        result = asyncio.run(self.reasoning.get_optimal_assignee("w_workforce", "AI Task"))
        
        self.assertEqual(result["suggested_user"]["user_id"], "u_expert")
        self.assertGreater(result["suggested_user"]["skill_score"], 0.5)

    def test_burnout_risk(self):
        # Give someone 10 tasks
        for i in range(10):
            task = ProjectTask(
                workspace_id="w_workforce", project_id="p1", milestone_id="m1",
                name=f"Busy Task {i}", status="in_progress", assigned_to="u_loader"
            )
            self.db.add(task)
        self.db.commit()
        
        risk = self.reasoning.assess_burnout_risk("u_loader")
        self.assertEqual(risk["risk_level"], "medium") # Threshold is > 8
        self.assertIn("high_active_load", risk["reasons"])

if __name__ == "__main__":
    unittest.main()
