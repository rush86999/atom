
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

class ForkApiTest(unittest.TestCase):
    
    @patch('advanced_workflow_orchestrator.AdvancedWorkflowOrchestrator.fork_execution', new_callable=AsyncMock)
    @patch('core.database.SessionLocal') # Mock DB to prevent startup errors
    @patch('advanced_workflow_orchestrator.MODELS_AVAILABLE', True)
    def test_fork_endpoint(self, mock_fork, mock_session):
        """
        Verify that POST /api/time-travel/workflows/:id/fork calls the orchestrator.
        """
        # Setup Mock Return
        mock_fork.return_value = "forked-123"
        
        # Import app AFTER mocking to avoid premature startup logic
        try:
            from main_api_app import app
            client = TestClient(app)
            
            print("\n[Test API] Calling Fork Endpoint...")
            response = client.post(
                "/api/time-travel/workflows/origin-123/fork",
                json={"step_id": "step_5", "new_variables": {"a": 1}}
            )
            
            print(f"[Test API] Status: {response.status_code}")
            print(f"[Test API] Response: {response.json()}")
            
            # Assertions
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["new_execution_id"], "forked-123")
            
            # Verify Orchestrator Call
            mock_fork.assert_called_once()
            print("SUCCESS: Endpoint correctly routed to Orchestrator.")
            
        except ImportError:
            import traceback
            print(f"IMPORT ERROR:\n{traceback.format_exc()}")
            raise
        except Exception:
            import traceback
            print(f"TEST EXECUTION ERROR:\n{traceback.format_exc()}")
            raise

if __name__ == '__main__':
    unittest.main()
