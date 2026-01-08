import unittest
import os
import sys
import asyncio
from datetime import datetime
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

class TestDomainAgnosticSkills(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        configure_mappers()
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        
        # Setup Data
        self.ws = Workspace(id="w_agnostic", name="Agnostic Corp")
        self.db.add(self.ws)
        
        # Non-IT Users
        self.u1 = User(id="u_electrician", email="sparky@corp.com", first_name="Elec", last_name="Trician", skills="Electrical Wiring, Safety Inspection", status="active")
        self.u2 = User(id="u_lawyer", email="legal@corp.com", first_name="Sue", last_name="Diligence", skills="Contract Review, Litigation", status="active")
        self.db.add_all([self.u1, self.u2])
        
        self.p1 = Project(id="p1", workspace_id="w_agnostic", name="Construction Project")
        self.db.add(self.p1)
        
        self.db.commit()
        
        self.analytics = WorkforceAnalyticsService(db_session=self.db)
        self.reasoning = ResourceReasoningEngine(db_session=self.db)

    def tearDown(self):
        self.db.close()

    def test_construction_skill_matching(self):
        # Task: Electrical installation
        # Should match "Electrical Wiring"
        result = asyncio.run(self.reasoning.get_optimal_assignee("w_agnostic", "Fix Electrical Wiring", "Requires: electrical wiring and safety inspection"))
        
        self.assertEqual(result["suggested_user"]["user_id"], "u_electrician")
        self.assertGreaterEqual(result["suggested_user"]["skill_score"], 0.9)

    def test_legal_gap_detection(self):
        # Task that requires "Plumbing"
        # Since we only have an Electrician and a Lawyer, "Plumbing" should be a gap.
        task = ProjectTask(
            id="t_plumb", workspace_id="w_agnostic", project_id="p1", milestone_id="m1",
            name="Fix Pipes", status="pending",
            metadata_json={"required_skills": ["Plumbing"]}
        )
        self.db.add(task)
        self.db.commit()
        
        result = self.analytics.map_skill_gaps("w_agnostic")
        self.assertIn("plumbing", result["unmet_requirements"])

    def test_multi_word_skill_matching(self):
        # Ensure "Contract Review" matches correctly
        result = asyncio.run(self.reasoning.get_optimal_assignee("w_agnostic", "Review Vendor Agreement", "Required Skills: Contract Review"))
        
        self.assertEqual(result["suggested_user"]["user_id"], "u_lawyer")
        self.assertGreaterEqual(result["suggested_user"]["skill_score"], 0.9)

if __name__ == "__main__":
    unittest.main()
