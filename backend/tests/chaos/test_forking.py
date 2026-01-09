
import unittest
from unittest.mock import MagicMock, patch, ANY
import sys
import os
import json

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

class ForkingTest(unittest.TestCase):
    
    @patch('core.database.SessionLocal')
    @patch('advanced_workflow_orchestrator.MODELS_AVAILABLE', True)
    def test_fork_execution(self, mock_session_cls):
        """
        Verify that fork_execution creates a parallel universe.
        """
        # 1. Setup Mock DB
        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_db
        
        # 2. Mock Snapshot (The Save Point)
        mock_snapshot = MagicMock()
        mock_snapshot.execution_id = "origin_timeline"
        mock_snapshot.step_id = "step_5"
        mock_snapshot.context_snapshot = json.dumps({
            "variables": {"status": "broken", "money": 0},
            "results": {"step_4": "ok"},
            "execution_history": ["step_1", "step_2", "step_3", "step_4"],
            "current_step": "step_5"
        })
        
        # 3. Mock Original Execution (for metadata clonging)
        mock_orig_exec = MagicMock()
        mock_orig_exec.workflow_id = "wf_financial"
        mock_orig_exec.input_data = '{"client": "BigCorp"}'
        mock_orig_exec.version = 1
        
        # Configure DB Query Side Effects
        def query_side_effect(model):
            query_mock = MagicMock()
            if "WorkflowSnapshot" in str(model):
                # The implementation uses .filter(A, B).first() -> Single filter call
                query_mock.filter.return_value.first.return_value = mock_snapshot
            elif "WorkflowExecution" in str(model):
                 query_mock.filter.return_value.first.return_value = mock_orig_exec
            return query_mock
            
        mock_db.query.side_effect = query_side_effect
        
        # 4. Run the Fork
        from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator
        orch = AdvancedWorkflowOrchestrator()
        
        print("\n[Test Fork] Attempting to fork execution...")
        # We apply a "Fix" during the fork
        new_id = self.loop.run_until_complete(
            orch.fork_execution(
                "origin_timeline", 
                "step_5", 
                new_variables={"status": "fixed", "money": 1000}
            )
        )
        
        # 5. Verify the "Parallel Universe"
        print(f"[Test Fork] New Universe ID: {new_id}")
        self.assertIsNotNone(new_id)
        self.assertNotEqual(new_id, "origin_timeline")
        self.assertIn("fork", new_id)
        
        # Check DB Insert
        mock_db.add.assert_called_once()
        new_exec_record = mock_db.add.call_args[0][0]
        self.assertEqual(new_exec_record.execution_id, new_id)
        
        # Check Initial State
        context_data = json.loads(new_exec_record.context)
        self.assertEqual(context_data["variables"]["status"], "fixed", "Variables were not patched!")
        self.assertEqual(context_data["variables"]["money"], 1000, "Variables were not patched!")
        self.assertEqual(context_data["current_step"], "step_5", "Wrong starting step")
        
        # Check In-Memory Load
        self.assertIn(new_id, orch.active_contexts)
        mem_ctx = orch.active_contexts[new_id]
        self.assertEqual(mem_ctx.variables["status"], "fixed")
        
        print("SUCCESS: Fork created successfully with patched variables.")

    def setUp(self):
        import asyncio
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
    
    def tearDown(self):
        self.loop.close()

if __name__ == '__main__':
    unittest.main()
