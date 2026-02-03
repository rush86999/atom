import asyncio
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import accounting.models
import sales.models
import service_delivery.models
from sales.models import Deal, DealStage
from service_delivery.models import Milestone, Project, ProjectTask
from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers, sessionmaker

import core.models

# Import models
from core.database import Base
from core.pm_orchestrator import PMOrchestrator


class TestPMExternalSync(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Setup in-memory SQLite for testing
        self.engine = create_engine("sqlite:///:memory:")
        configure_mappers()
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        
        self.user_id = "test_user_sync"
        self.workspace_id = "test_workspace_sync"
        
        # Patch SessionLocal
        self.patcher_db = patch("core.pm_orchestrator.SessionLocal", return_value=self.db)
        self.patcher_db_sync = patch("core.external_pm_sync.SessionLocal", return_value=self.db)
        self.patcher_db.start()
        self.patcher_db_sync.start()
        
        self.pm_orch = PMOrchestrator()

    async def asyncTearDown(self):
        self.db.close()
        self.patcher_db.stop()
        self.patcher_db_sync.stop()

    @patch("core.pm_orchestrator.pm_engine")
    @patch("core.pm_orchestrator.graphrag_engine")
    @patch("core.external_pm_sync.asana_real_service")
    async def test_asana_sync(self, mock_asana, mock_graphrag, mock_pm_engine):
        # 1. Setup Mock Deal
        deal_id = "deal_asana_1"
        deal = Deal(id=deal_id, workspace_id=self.workspace_id, name="Asana Sync Deal", value=5000, stage=DealStage.CLOSED_WON)
        self.db.add(deal)
        self.db.commit()
        
        # 2. Mock PM Engine to return a project with one milestone and one task
        project_id = "proj_asana_1"
        mock_pm_engine.generate_project_from_nl = AsyncMock(return_value={
            "status": "success", "project_id": project_id, "name": "Asana Project"
        })
        
        # Add a milestone and task manually since generate_project_from_nl is mocked but the orchestrator expects them in DB for sync
        ms = Milestone(id="ms1", project_id=project_id, workspace_id=self.workspace_id, name="Phase 1", order=1)
        task = ProjectTask(id="tk1", milestone_id="ms1", project_id=project_id, workspace_id=self.workspace_id, name="Initial Setup")
        project = Project(id=project_id, workspace_id=self.workspace_id, name="Asana Project", contract_id="c1")
        self.db.add_all([project, ms, task])
        self.db.commit()

        # 3. Mock Asana service
        mock_asana.create_project = AsyncMock(return_value={"id": "asana_proj_gid", "name": "Asana Project"})
        mock_asana.create_task = AsyncMock(return_value={"id": "asana_task_gid"})
        
        # 4. Execute Provisioning with Asana Sync
        result = await self.pm_orch.provision_from_deal(deal_id, self.user_id, self.workspace_id, external_platform="asana")
        
        # 5. Verify
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["external_sync"]["platform"], "asana")
        self.assertEqual(result["external_sync"]["external_id"], "asana_proj_gid")
        
        # Check that Asana service was called
        mock_asana.create_project.assert_called_once()
        mock_asana.create_task.assert_called()

    @patch("core.pm_orchestrator.pm_engine")
    @patch("core.pm_orchestrator.graphrag_engine")
    @patch("core.external_pm_sync.linear_service")
    async def test_linear_sync(self, mock_linear, mock_graphrag, mock_pm_engine):
        # 1. Setup Mock Deal
        deal_id = "deal_linear_1"
        deal = Deal(id=deal_id, workspace_id=self.workspace_id, name="Linear Sync Deal", value=7000, stage=DealStage.CLOSED_WON)
        self.db.add(deal)
        self.db.commit()

        project_id = "proj_linear_1"
        mock_pm_engine.generate_project_from_nl = AsyncMock(return_value={
            "status": "success", "project_id": project_id, "name": "Linear Project"
        })
        
        ms = Milestone(id="ms2", project_id=project_id, workspace_id=self.workspace_id, name="Build Phase", order=1)
        task = ProjectTask(id="tk2", milestone_id="ms2", project_id=project_id, workspace_id=self.workspace_id, name="Coding")
        project = Project(id=project_id, workspace_id=self.workspace_id, name="Linear Project", contract_id="c2")
        self.db.add_all([project, ms, task])
        self.db.commit()

        # 2. Mock Linear service
        mock_linear.get_teams = AsyncMock(return_value=[{"id": "team_1", "name": "Engineering"}])
        mock_linear.create_project = AsyncMock(return_value={"success": True, "project": {"id": "linear_proj_id"}})
        mock_linear.create_issue = AsyncMock(return_value={"success": True})
        
        # 3. Execute
        result = await self.pm_orch.provision_from_deal(deal_id, self.user_id, self.workspace_id, external_platform="linear")
        
        # 4. Verify
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["external_sync"]["platform"], "linear")
        
        mock_linear.create_project.assert_called_once()
        mock_linear.create_issue.assert_called()

if __name__ == "__main__":
    unittest.main()
