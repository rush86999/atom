
import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import json

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

class OrchestratorPersistenceTest(unittest.TestCase):
    
    @patch('core.database.SessionLocal')
    @patch('advanced_workflow_orchestrator.MODELS_AVAILABLE', True) # Force enable
    def test_ghost_resurrection(self, mock_session_cls):
        """
        Verify that __init__ calls _restore_active_executions and loads from DB.
        """
        # 1. Setup Mock DB
        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_db
        
        # Mock Query Results
        mock_execution = MagicMock()
        mock_execution.workflow_id = "ghost_flow_1"
        mock_execution.status = "RUNNING" # ENUM typically uses uppercase
        mock_execution.context = json.dumps({
            "variables": {"status": "alive"},
            "current_step": "step_5"
        })
        mock_execution.input_data = "{}"
        mock_execution.user_id = "test_user"
        
        # When db.query().filter().all() is called
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_execution]
        
        # 2. Initialize Orchestrator
        # We need to ensure we import the class where the patch is active
        # The patching above hits 'advanced_workflow_orchestrator.SessionLocal'
        # So we import the module
        import advanced_workflow_orchestrator
        # Force reload? No, simpler to just import.
        from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator
        
        print("\n[Test Persistence] Initializing Orchestrator...")
        # Check if patch worked by inspecting the imported module's SessionLocal if possible?
        # Actually, since we use 'from core.database import SessionLocal' inside the function,
        # checking sys.modules['core.database'].SessionLocal is what matters.
        import core.database
        print(f"DEBUG: core.database.SessionLocal is {core.database.SessionLocal}")
        
        orch = AdvancedWorkflowOrchestrator()
        
        # 3. Validation
        print(f"[Test Persistence] Active Contexts: {len(orch.active_contexts)}")
        
        self.assertIn("ghost_flow_1", orch.active_contexts, "Ghost workflow was NOT restored!")
        restored_ctx = orch.active_contexts["ghost_flow_1"]
        self.assertEqual(restored_ctx.variables.get("status"), "alive", "Context variables lost")
        print("SUCCESS: Ghost Workflow 'ghost_flow_1' was successfully resurrected from DB.")

if __name__ == '__main__':
    unittest.main()
