import asyncio
import logging
import unittest
from unittest.mock import MagicMock, patch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestAgentRedisQueue(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    @patch('core.task_queue.get_task_queue')
    @patch('core.atom_meta_agent.AtomMetaAgent')
    def test_handle_data_event_trigger_enqueues_to_redis(self, MockAtom, mock_get_task_queue):
        # This import must happen inside the test or after the patches if possible
        # to ensure it uses the patched versions
        from core.atom_meta_agent import handle_data_event_trigger, AgentTriggerMode
        
        # Setup mock task queue
        mock_queue = MagicMock()
        mock_queue.enabled = True
        mock_queue.enqueue_job.return_value = "job_123"
        mock_get_task_queue.return_value = mock_queue
        
        # Call the handler
        result = self.loop.run_until_complete(handle_data_event_trigger(
            event_type="test_event",
            data={"key": "value"},
            workspace_id="test_workspace"
        ))
        
        # Assertions
        self.assertEqual(result["status"], "queued")
        self.assertEqual(result["task_id"], "job_123")
        
        mock_queue.enqueue_job.assert_called_once()
        args, kwargs = mock_queue.enqueue_job.call_args
        
        self.assertEqual(kwargs["queue_name"], "workflows")
        self.assertEqual(kwargs["task_data"]["tenant_id"], "test_workspace")
        self.assertEqual(kwargs["task_data"]["trigger_mode"], AgentTriggerMode.DATA_EVENT.value)
        
        # Verify inline fallback was NOT called
        MockAtom.assert_not_called()

    @patch('core.task_queue.get_task_queue')
    @patch('core.atom_meta_agent.AtomMetaAgent')
    def test_handle_data_event_trigger_falls_back_when_redis_disabled(self, MockAtom, mock_get_task_queue):
        from core.atom_meta_agent import handle_data_event_trigger
        
        # Setup mock task queue as disabled
        mock_queue = MagicMock()
        mock_queue.enabled = False
        mock_get_task_queue.return_value = mock_queue
        
        # Setup mock Atom instance for fallback
        mock_atom_instance = MagicMock()
        mock_atom_instance.execute = MagicMock()
        
        # Create a future for the async execution
        fut = asyncio.Future(loop=self.loop)
        fut.set_result({"status": "success"})
        mock_atom_instance.execute.return_value = fut
        
        MockAtom.return_value = mock_atom_instance
        
        # Call the handler
        result = self.loop.run_until_complete(handle_data_event_trigger(
            event_type="test_event",
            data={"key": "value"},
            workspace_id="test_workspace"
        ))
        
        # Assertions
        self.assertEqual(result["status"], "success")
        MockAtom.assert_called_once_with("test_workspace")
        mock_atom_instance.execute.assert_called_once()

if __name__ == "__main__":
    unittest.main()
