import asyncio
import os
import unittest
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers, sessionmaker

# Override DATABASE_URL for in-memory testing
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import accounting.models
import sales.models
import service_delivery.models
from service_delivery.models import Milestone, MilestoneStatus, Project, ProjectStatus, ProjectTask

import core.models
from core.database import Base
from core.pm_engine import AIProjectManager


class TestAIPMMVP(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.user_id = "test_user_pm"
        self.workspace_id = "test_workspace_pm"
        
        # New engine for in-memory DB
        self.engine = create_engine("sqlite:///:memory:")
        self.SessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        configure_mappers()
        
        self.db = self.SessionLocal()
        
        # New instance for each test to avoid stale state
        self.pm = AIProjectManager()
        # Mock SessionLocal in pm_engine to use our in-memory DB
        self.pm_patcher = patch("core.pm_engine.SessionLocal", side_effect=lambda: self.SessionLocal())
        self.pm_patcher.start()

    async def asyncTearDown(self):
        self.pm_patcher.stop()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    async def test_project_generation(self):
        # Mock LLM Response
        mock_ai = self.pm.ai = MagicMock()
        mock_ai.process_with_nlu = AsyncMock(return_value={
            "nlu_result": {
                "name": "Cloud Migration",
                "description": "Migrate on-prem servers to AWS",
                "priority": "high",
                "planned_duration_days": 45,
                "budget_amount": 50000,
                "milestones": [
                    {
                        "name": "Infrastructure Setup",
                        "order": 1,
                        "planned_start_day": 0,
                        "duration_days": 14,
                        "tasks": [
                            {"name": "Provision VPC", "description": "Setup network topology"},
                            {"name": "Setup IAM", "description": "Configure roles and policies"}
                        ]
                    }
                ]
            }
        })
        
        prompt = "Plan a cloud migration for AWS with 50k budget in 45 days"
        result = await self.pm.generate_project_from_nl(prompt, self.user_id, self.workspace_id)
        
        if result["status"] == "failed":
             print(f"DEBUG: Failed with {result.get('error')}")
             
        self.assertEqual(result["status"], "success")
        project_id = result["project_id"]
        
        # Verify in DB
        project = self.db.query(Project).filter(Project.id == project_id).first()
        self.assertIsNotNone(project)
        self.assertEqual(project.name, "Cloud Migration")
        
        milestones = self.db.query(Milestone).filter(Milestone.project_id == project_id).all()
        self.assertEqual(len(milestones), 1)
        
        tasks = self.db.query(ProjectTask).filter(ProjectTask.milestone_id == milestones[0].id).all()
        self.assertEqual(len(tasks), 2)

    @patch("core.pm_engine.graphrag_engine")
    async def test_status_inference(self, mock_graphrag):
        # Create a project and task
        project = Project(
            id=f"test_proj_{uuid.uuid4().hex[:4]}",
            workspace_id=self.workspace_id,
            contract_id="test_contract",
            name="Test Inference Project",
            status=ProjectStatus.PENDING
        )
        self.db.add(project)
        self.db.commit()
        
        milestone = Milestone(
            id=f"test_ms_{uuid.uuid4().hex[:4]}",
            workspace_id=self.workspace_id,
            project_id=project.id,
            name="Test Milestone",
            status=MilestoneStatus.PENDING
        )
        self.db.add(milestone)
        self.db.commit()
        
        task = ProjectTask(
            id=f"test_task_{uuid.uuid4().hex[:4]}",
            workspace_id=self.workspace_id,
            milestone_id=milestone.id,
            name="Test Task",
            status="pending"
        )
        self.db.add(task)
        self.db.commit()
        
        # Mock GraphRAG
        mock_graphrag.query = MagicMock(return_value={"answer": "The user successfully finished the Test Task yesterday."})
        
        result = await self.pm.infer_project_status(project.id, self.user_id)
        
        self.assertEqual(result["status"], "success")
        self.db.refresh(task)
        self.assertEqual(task.status, "completed")

    async def test_risk_analysis(self):
        project = Project(
            id=f"risk_proj_{uuid.uuid4().hex[:4]}",
            workspace_id=self.workspace_id,
            contract_id="test_contract",
            name="Risk Project",
            planned_end_date=datetime.now() - timedelta(days=1),
            status=ProjectStatus.ACTIVE,
            budget_hours=100.0,
            actual_hours=120.0
        )
        self.db.add(project)
        self.db.commit()
        
        result = await self.pm.analyze_project_risks(project.id, self.user_id)
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["risk_level"], "high")

if __name__ == "__main__":
    unittest.main()
