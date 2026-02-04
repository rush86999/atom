import os
import sys
import unittest
from datetime import datetime

sys.path.append(os.getcwd())

import accounting.models
import ecommerce.models
import saas.models
import sales.models
import service_delivery.models
from service_delivery.models import Milestone, Project, ProjectTask
from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers, sessionmaker

import core.models
from core.database import Base
from core.models import User, Workspace
from core.workforce_analytics import WorkforceAnalyticsService


class TestSkillGaps(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        configure_mappers()
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        
        # Setup Data
        self.ws = Workspace(id="w_gaps", name="Gap Corp")
        self.db.add(self.ws)
        
        # Users
        self.u1 = User(id="u_python", email="py@corp.com", first_name="Python", last_name="Dev", skills="Python, SQL", status="active")
        self.u2 = User(id="u_rust", email="rs@corp.com", first_name="Rust", last_name="Expert", skills="Rust, C++", status="active")
        self.db.add_all([self.u1, self.u2])
        
        self.p1 = Project(id="p1", workspace_id="w_gaps", name="Gaps Project")
        self.db.add(self.p1)
        self.m1 = Milestone(id="m1", workspace_id="w_gaps", project_id="p1", name="M1")
        self.db.add(self.m1)
        
        # Tasks
        # 1. Met requirement (Python task assigned to Python dev)
        self.t1 = ProjectTask(
            id="t1", workspace_id="w_gaps", project_id="p1", milestone_id="m1",
            name="Python Task", assigned_to="u_python", status="in_progress",
            metadata_json={"required_skills": ["Python"]}
        )
        
        # 2. Assignment Mismatch (Rust task assigned to Python dev)
        self.t2 = ProjectTask(
            id="t2", workspace_id="w_gaps", project_id="p1", milestone_id="m1",
            name="Rust Task Mismatch", assigned_to="u_python", status="in_progress",
            metadata_json={"required_skills": ["Rust"]}
        )
        
        # 3. Unmet Requirement (Nobody has "Go")
        self.t3 = ProjectTask(
            id="t3", workspace_id="w_gaps", project_id="p1", milestone_id="m1",
            name="Go Task", status="pending",
            metadata_json={"required_skills": ["Go"]}
        )
        
        self.db.add_all([self.t1, self.t2, self.t3])
        self.db.commit()
        
        self.analytics = WorkforceAnalyticsService(db_session=self.db)

    def tearDown(self):
        self.db.close()

    def test_map_skill_gaps(self):
        result = self.analytics.map_skill_gaps("w_gaps")
        
        # 1. Unmet Requirements: "go" should be unmet
        self.assertIn("go", result["unmet_requirements"])
        self.assertIn("t3", result["unmet_requirements"]["go"])
        
        # 2. Assignment Mismatches: t2 should be a mismatch
        mismatches = result["assignment_mismatches"]
        self.assertTrue(any(m["task_id"] == "t2" and "rust" in m["missing_skills"] for m in mismatches))
        
        # 3. Competency Density: "python" should have 1, "rust" should have 1
        self.assertEqual(result["competency_density"]["python"], 1)
        self.assertEqual(result["competency_density"]["rust"], 1)
        self.assertEqual(result["team_size"], 2)

if __name__ == "__main__":
    unittest.main()
