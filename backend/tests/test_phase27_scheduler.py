import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.append(os.getcwd())

from api.agent_routes import router as agent_router
from core.auth import get_current_user
from core.database import get_db
from core.models import User, UserRole


class TestPhase27Scheduler(unittest.TestCase):

    def setUp(self):
        # Create a fresh app for testing to avoid main_api_app dependency hell.
        # NOTE: api.agent_routes.AgentRouter already declares its own
        # prefix="/api/agents", so include WITHOUT a prefix (adding one would
        # double the path to /api/agents/api/agents/... and 404 everything).
        self.app = FastAPI()
        self.app.include_router(agent_router)

        # Auth: routes require an authenticated SUPER_ADMIN user
        fake_user = User(
            id="test-user",
            email="test@example.com",
            hashed_password="x",
            role=UserRole.SUPER_ADMIN.value,
        )
        self.app.dependency_overrides[get_current_user] = lambda: fake_user
        self.client = TestClient(self.app)

    @patch("core.scheduler.AgentScheduler")
    def test_schedule_agent(self, MockAgentScheduler):
        print("\n--- Phase 27: Scheduler API Test (Mocked) ---")

        # Mock Scheduler (AgentScheduler lives in core.scheduler, not api.agent_routes)
        mock_scheduler_instance = MagicMock()
        MockAgentScheduler.get_instance.return_value = mock_scheduler_instance

        cron = "*/1 * * * *"

        # Mock DB (other test modules replace core.database.SessionLocal with a
        # temp-file engine and never restore it — never touch a real DB here).
        # AgentRegistry.id is a column default assigned on flush/insert, so the
        # stub refresh simulates it (MagicMock alone would leave id=None).
        mock_db = MagicMock()
        mock_db.refresh.side_effect = lambda obj: setattr(
            obj, "id", getattr(obj, "id", None) or "mocked-agent-id"
        )
        self.app.dependency_overrides[get_db] = lambda: mock_db

        # Scheduling is exposed via POST /api/agents/custom with schedule_config
        response = self.client.post(
            "/api/agents/custom",
            json={
                "name": "Competitive Intel Agent",
                "category": "intelligence",
                "configuration": {},
                "schedule_config": {"active": True, "cron": cron},
            },
        )

        print(f"Schedule Response: {response.json()}")

        # Verify call
        MockAgentScheduler.get_instance.assert_called_once()
        mock_scheduler_instance.schedule_agent.assert_called_once()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["agent_id"], "mocked-agent-id")
        self.assertEqual(
            response.json()["message"],
            "Custom agent Competitive Intel Agent created successfully",
        )

    def test_history_endpoint(self):
        print("\n--- Phase 27: History API Test (Mocked) ---")

        # Mock DB
        mock_db = MagicMock()
        self.app.dependency_overrides[get_db] = lambda: mock_db

        # Mock Query Result
        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_job.agent_id = "test_agent"
        mock_job.status = "success"
        mock_job.started_at = MagicMock()
        mock_job.started_at.isoformat.return_value = "2023-01-01T00:00:00"
        mock_job.completed_at = None
        mock_job.duration_seconds = 60.0
        mock_job.result_summary = "{}"
        mock_job.error_message = None
        mock_job.triggered_by = "manual"

        # Setup chain: db.query().order_by().limit().all()
        mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_job]

        response = self.client.get("/api/agents/history")

        print(f"History Response Status: {response.status_code}")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "job-123")


if __name__ == "__main__":
    unittest.main()
