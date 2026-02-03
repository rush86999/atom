import asyncio
import json
import unittest
import uuid
from unittest.mock import MagicMock, patch
import accounting.models  # Required for Invoice/Entity relationships
import sales.models  # Required for Deal relationship
import service_delivery.models
from service_delivery.models import ProjectTask
from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers, sessionmaker

import core.models

# Import models
from core.database import Base
from core.models import Team, User, Workspace
from core.resource_manager import ResourceMonitor
from core.staffing_advisor import StaffingAdvisor


class TestResourceIntelligence(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Setup in-memory SQLite for testing
        self.engine = create_engine("sqlite:///:memory:")
        configure_mappers()
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        
        self.workspace_id = "test_ws_resources"
        
        # Patch SessionLocal for managers
        self.patcher_db = patch("core.resource_manager.SessionLocal", return_value=self.db)
        self.patch_rm = self.patcher_db.start()
        
        self.patcher_db2 = patch("core.staffing_advisor.SessionLocal", return_value=self.db)
        self.patch_sa = self.patcher_db2.start()

        self.rm = ResourceMonitor()
        self.sa = StaffingAdvisor()

        # Seed data
        self.user1 = User(
            id="u1", 
            email="dev1@test.com", 
            first_name="Alice", 
            last_name="Dev",
            workspace_id=self.workspace_id,
            skills=json.dumps(["Python", "PostgreSQL", "React"]),
            capacity_hours=40.0,
            status="active"
        )
        self.user2 = User(
            id="u2", 
            email="sales1@test.com", 
            first_name="Bob", 
            last_name="Sales",
            workspace_id=self.workspace_id,
            skills=json.dumps(["Salesforce", "Communication", "Negotiation"]),
            capacity_hours=30.0,
            status="active"
        )
        self.db.add(self.user1)
        self.db.add(self.user2)
        self.db.commit()

    async def asyncTearDown(self):
        self.db.close()
        self.patcher_db.stop()
        self.patcher_db2.stop()

    async def test_utilization_calculation(self):
        # Add tasks to Alice (u1)
        task1 = ProjectTask(
            id="t1",
            workspace_id=self.workspace_id,
            milestone_id="m1",
            project_id="p1",
            name="Implement Backend",
            assigned_to="u1",
            status="in_progress",
            metadata_json={"estimated_hours": 10.0}
        )
        task2 = ProjectTask(
            id="t2",
            workspace_id=self.workspace_id,
            milestone_id="m2",
            project_id="p1",
            name="Fix React Bugs",
            assigned_to="u1",
            status="pending",
            metadata_json={"estimated_hours": 10.0}
        )
        self.db.add(task1)
        self.db.add(task2)
        self.db.commit()

        # Calculate Alice's utilization
        res = self.rm.calculate_utilization("u1", db=self.db)
        
        # 20 hours / 40 capacity = 50%
        self.assertEqual(res["utilization_percentage"], 50.0)
        self.assertEqual(res["active_task_count"], 2)
        self.assertEqual(res["risk_level"], "low")

        # Add heavy task to push into high risk
        task3 = ProjectTask(
            id="t3",
            workspace_id=self.workspace_id,
            milestone_id="m3",
            project_id="p2",
            name="Massive Migration",
            assigned_to="u1",
            status="in_progress",
            metadata_json={"estimated_hours": 25.0}
        )
        self.db.add(task3)
        self.db.commit()

        # 45 hours / 40 capacity = 112.5%
        res = self.rm.calculate_utilization("u1", db=self.db)
        self.assertEqual(res["utilization_percentage"], 112.5)
        self.assertEqual(res["risk_level"], "high")

    @patch("core.staffing_advisor.get_ai_service")
    async def test_staffing_recommendation(self, mock_get_ai):
        # Mock AI skill extraction
        mock_ai = MagicMock()
        
        async def mock_nlu(text, system_prompt=None):
            return ["Python", "React"]
        
        mock_ai.process_with_nlu = mock_nlu
        mock_get_ai.return_value = mock_ai

        # Request recommendation for a dev project
        res = await self.sa.recommend_staff("We need a senior fullstack dev for Python and React work", self.workspace_id)
        
        if res.get("status") == "error":
            print(f"DEBUG: StaffingAdvisor Error: {res.get('message')}")
            
        self.assertEqual(res["status"], "success")
        self.assertIn("Python", res["required_skills"])
        
        # User 1 (Alice) should be the top match
        self.assertEqual(len(res["recommendations"]), 1)
        self.assertEqual(res["recommendations"][0]["name"], "Alice Dev")
        self.assertEqual(res["recommendations"][0]["match_score"], 100.0)

        # Bob (User 2) should NOT match Python/React
        
        print("\n[SUCCESS] Resource Intelligence Verified (Utilization & AI Staffing).")

if __name__ == "__main__":
    unittest.main()
