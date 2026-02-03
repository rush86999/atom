import asyncio
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.append(os.getcwd())

import accounting.models
import ecommerce.models
import saas.models
import sales.models
import service_delivery.models
from service_delivery.models import Milestone, Project, ProjectStatus, ProjectTask
from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers, sessionmaker

import core.models
from core.database import Base
from core.models import User, Workspace
from core.pm_engine import AIProjectManager


class TestPMSwarm(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        configure_mappers()
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        
        # Setup Data
        self.ws = Workspace(id="w_swarm", name="Swarm Corp")
        self.db.add(self.ws)
        
        # User with historical bias (taking 2x longer)
        self.u1 = User(id="u_bias", email="bias@corp.com", first_name="Opti", last_name="Mistic", skills="Python", status="active")
        self.db.add(self.u1)
        
        # Project that is overdue
        self.p1 = Project(
            id="p_sw", workspace_id="w_swarm", name="Delayed Project",
            planned_start_date=datetime.now() - timedelta(days=10),
            planned_end_date=datetime.now() - timedelta(days=1),
            status=ProjectStatus.ACTIVE
        )
        self.db.add(self.p1)
        self.m1 = Milestone(id="m1", workspace_id="w_swarm", project_id="p_sw", name="M1")
        self.db.add(self.m1)
        
        # Tasks: one completed (2x longer), one overdue
        self.t1 = ProjectTask(
            id="t1", workspace_id="w_swarm", project_id="p_sw", milestone_id="m1",
            name="Legacy Task", status="completed", assigned_to="u_bias", actual_hours=20.0,
            metadata_json={"planned_hours": 10.0}
        )
        self.t2 = ProjectTask(
            id="t2", workspace_id="w_swarm", project_id="p_sw", milestone_id="m1",
            name="Skill Gap Task", status="pending", due_date=datetime.now() - timedelta(days=2),
            metadata_json={"required_skills": ["Rust"]} # Skill Gap
        )
        self.db.add_all([self.t1, self.t2])
        self.db.commit()
        
        self.pm = AIProjectManager(db_session=self.db)

    def tearDown(self):
        self.db.close()

    def test_swarm_startup_bypass(self):
        # Mark as startup
        self.ws.is_startup = True
        self.db.commit()
        
        result = asyncio.run(self.pm.trigger_autonomous_correction("w_swarm", "p_sw"))
        self.assertEqual(result["decision"]["status"], "approved" if not result["decision"]["hitl_request"] else "pending_user")
        
        # Verify changes applied
        updated_project = self.db.query(Project).filter(Project.id == "p_sw").first()
        self.assertGreater(updated_project.planned_end_date, datetime.now())

    def test_swarm_learning_mode(self):
        # Mark as established, learning phase not done
        self.ws.is_startup = False
        self.ws.learning_phase_completed = False
        self.db.commit()
        
        # Reset project date to past for testing
        self.p1.planned_end_date = datetime.now() - timedelta(days=1)
        self.db.commit()
        
        result = asyncio.run(self.pm.trigger_autonomous_correction("w_swarm", "p_sw"))
        self.assertEqual(result["decision"]["status"], "learning_mode")
        self.assertIn("Learning Phase", result["decision"]["hitl_request"])
        
        # Verify NO changes applied
        updated_project = self.db.query(Project).filter(Project.id == "p_sw").first()
        self.assertLess(updated_project.planned_end_date, datetime.now())

    def test_swarm_established_completed(self):
        # Mark as established, learning phase DONE
        self.ws.is_startup = False
        self.ws.learning_phase_completed = True
        self.db.commit()
        
        result = asyncio.run(self.pm.trigger_autonomous_correction("w_swarm", "p_sw"))
        # Should be approved (or pending_user if skill gap blocked executor)
        status = result["decision"]["status"]
        self.assertIn(status, ["approved", "pending_user"])
        
        if status == "approved":
            updated_project = self.db.query(Project).filter(Project.id == "p_sw").first()
            self.assertGreater(updated_project.planned_end_date, datetime.now())

if __name__ == "__main__":
    unittest.main()
