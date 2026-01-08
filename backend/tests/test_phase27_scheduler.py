import sys
import os
import unittest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.append(os.getcwd())

from api.agent_routes import router as agent_router

class TestPhase27Scheduler(unittest.TestCase):
    
    def setUp(self):
        # Create a fresh app for testing to avoid main_api_app dependency hell
        self.app = FastAPI()
        self.app.include_router(agent_router, prefix="/api/agents")
        self.client = TestClient(self.app)

    @patch("api.agent_routes.AgentScheduler")
    @patch("api.agent_routes.SessionLocal")
    @patch("api.agent_routes.AgentJob")
    def test_schedule_agent(self, MockAgentJob, MockSessionLocal, MockAgentScheduler):
        print("\n--- Phase 27: Scheduler API Test (Mocked) ---")
        
        # Mock Scheduler
        mock_scheduler_instance = MagicMock()
        mock_scheduler_instance.schedule_job.return_value = "job-123"
        MockAgentScheduler.get_instance.return_value = mock_scheduler_instance
        
        agent_id = "competitive_intel"
        cron = "*/1 * * * *"
        
        response = self.client.post(
            f"/api/agents/{agent_id}/schedule",
            json={"cron_expression": cron}
        )
        
        print(f"Schedule Response: {response.json()}")
        
        # Verify call
        MockAgentScheduler.get_instance.assert_called_once()
        mock_scheduler_instance.schedule_job.assert_called_once()
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job_id"], "job-123")
        self.assertEqual(response.json()["status"], "scheduled")

    @patch("api.agent_routes.SessionLocal")
    @patch("api.agent_routes.AgentJob")
    def test_history_endpoint(self, MockAgentJob, MockSessionLocal):
        print("\n--- Phase 27: History API Test (Mocked) ---")
        
        # Mock DB
        mock_db = MagicMock()
        MockSessionLocal.return_value = mock_db
        
        # Mock Query Result
        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_job.agent_id = "test_agent"
        mock_job.status = "success"
        mock_job.start_time = "2023-01-01T00:00:00"
        mock_job.end_time = "2023-01-01T00:01:00"
        mock_job.logs = "Test Logs"
        mock_job.result_summary = "{}"
        
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
