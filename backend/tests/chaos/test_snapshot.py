
import unittest
from unittest.mock import MagicMock, patch, ANY
import sys
import os
import json

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

class SnapshotTest(unittest.TestCase):
    
    @patch('core.database.SessionLocal')
    @patch('advanced_workflow_orchestrator.MODELS_AVAILABLE', True)
    def test_snapshot_creation(self, mock_session_cls):
        """
        Verify that _create_snapshot is called and saves to DB.
        """
        # 1. Setup Mock DB
        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_db
        
        from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator, WorkflowContext
        
        orch = AdvancedWorkflowOrchestrator()
        
        # 2. Create Dummy Context
        ctx = WorkflowContext(
            workflow_id="test_time_travel",
            variables={"hero": "Mario"},
            results={"step_1": {"status": "completed", "score": 100}}
        )
        ctx.execution_history = [{"step_id": "step_1"}]
        
        # 3. Trigger Snapshot manually (unit test the method first)
        print("\n[Test Snapshot] Triggering snapshot...")
        orch._create_snapshot(ctx, "step_1")
        
        # 4. Verify DB Insert
        # We expect db.add() to be called with a WorkflowSnapshot object
        mock_db.add.assert_called_once()
        args, _ = mock_db.add.call_args
        snapshot = args[0]
        
        print(f"[Test Snapshot] Captured object: {type(snapshot).__name__}")
        self.assertEqual(snapshot.execution_id, "test_time_travel")
        self.assertEqual(snapshot.step_id, "step_1")
        self.assertEqual(snapshot.step_order, 1)
        
        # Verify JSON serialization
        content = json.loads(snapshot.context_snapshot)
        self.assertEqual(content["variables"]["hero"], "Mario")
        print("SUCCESS: Snapshot saved with correct state data.")

if __name__ == '__main__':
    unittest.main()
