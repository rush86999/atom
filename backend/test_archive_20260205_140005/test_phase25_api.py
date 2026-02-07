
import asyncio
import os
import sys
import unittest
from fastapi.testclient import TestClient

try:
    from unittest.mock import AsyncMock, MagicMock, patch
except ImportError:
    from unittest.mock import MagicMock, patch

    # Fallback for older python, though env claims it has it
    AsyncMock = MagicMock 

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main_api_app import app

from api.agent_routes import AGENT_STATE, AGENTS


class TestPhase25AgentAPI(unittest.TestCase):
    
    def setUp(self):
        self.client = TestClient(app)
        
    def test_list_agents(self):
        print("\n🧪 Testing List Agents API...")
        response = self.client.get("/api/v1/agents")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        
        # Verify structure
        agent = data[0]
        self.assertIn("id", agent)
        self.assertIn("name", agent)
        self.assertIn("status", agent)
        print(f"✅ Listed {len(data)} agents successfully.")

    @patch('api.agent_routes.notification_manager') 
    def test_run_agent(self, mock_notify):
        print("\n🧪 Testing Run Agent API...")
        
        # Configure AsyncMock
        mock_notify.broadcast = AsyncMock()
        mock_notify.send_urgent_notification = AsyncMock()
        
        agent_id = list(AGENTS.keys())[0] # Pick first agent
        
        # Ensure idle
        AGENT_STATE[agent_id]["status"] = "idle"
        
        # Mock background tasks to avoid actual execution loop in unit test
        with patch('api.agent_routes.execute_agent_task') as mock_exec:
            response = self.client.post(f"/api/v1/agents/{agent_id}/run", json={"parameters": {}})
            
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "started")
            
            # Verify State Updated
            self.assertEqual(AGENT_STATE[agent_id]["status"], "running")
            
            # Verify Notification Broadcast
            mock_notify.broadcast.assert_called()
            
            print(f"✅ Agent {agent_id} started successfully.")

if __name__ == "__main__":
    unittest.main()
