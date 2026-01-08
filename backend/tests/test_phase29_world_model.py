import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime
import sys
import os

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.agent_world_model import WorldModelService, AgentExperience
from core.models import AgentRegistry, AgentStatus
from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator, WorkflowStep, WorkflowStepType, WorkflowContext

class TestWorldModel(unittest.TestCase):
    def setUp(self):
        # Mock LanceDB Handler
        self.mock_db = MagicMock()
        with patch("core.agent_world_model.get_lancedb_handler", return_value=self.mock_db):
            self.service = WorldModelService()

    async def test_scoping_finance_cannot_see_hr(self):
        # 1. Mock DB returning mixed results
        # One HR memory, one Finance memory
        mock_results = [
            {
                "id": "mem_hr",
                "text": "Task: Payroll\nInput: secret checks\nLearnings: HR Secret",
                "metadata": {"agent_id": "hr_bot", "agent_role": "hr", "task_type": "payroll", "outcome": "Success"},
                "created_at": datetime.now().isoformat()
            },
            {
                "id": "mem_fin",
                "text": "Task: Reconciliation\nInput: ledger\nLearnings: Finance Info",
                "metadata": {"agent_id": "fin_bot", "agent_role": "finance", "task_type": "recon", "outcome": "Success"},
                "created_at": datetime.now().isoformat()
            }
        ]
        self.mock_db.search.return_value = mock_results # For both calls (experience & knowledge)

        # 2. Agent is Finance
        finance_agent = AgentRegistry(
            id="fin_bot", 
            category="Finance",
            name="Finance Bot"
        )
        
        # 3. Call Recall
        result = await self.service.recall_experiences(finance_agent, "reconcile payroll")
        
        # 4. Verify Experiences (Should only see Finance)
        experiences = result["experiences"]
        self.assertEqual(len(experiences), 1)
        self.assertEqual(experiences[0].input_summary, "ledger")
        self.assertEqual(experiences[0].learnings, "Finance Info")
        
    async def test_general_knowledge_access(self):
        # General knowledge call uses table="documents"
        # Mock DB search to return distinct results for the second call
        
        # Logic: recall_experiences calls search TWICE. 
        # 1st call: Agent Experience Table
        # 2nd call: Documents Table
        
        exp_results = [] # No experiences
        doc_results = [{
            "id": "doc_1",
            "text": "General Company Policy",
            "metadata": {"type": "policy"},
            "created_at": datetime.now().isoformat()
        }]
        
        self.mock_db.search.side_effect = [exp_results, doc_results]
        
        agent = AgentRegistry(id="any_agent", category="Operations")
        
        result = await self.service.recall_experiences(agent, "policy")
        
        # Verify Knowledge
        self.assertEqual(len(result["knowledge"]), 1)
        self.assertEqual(result["knowledge"][0]["text"], "General Company Policy")

    @patch("advanced_workflow_orchestrator.SessionLocal")
    @patch("advanced_workflow_orchestrator.WorldModelService")
    async def test_orchestrator_integration(self, MockWMService, MockSession):
        # Setup Orchestrator
        orchestrator = AdvancedWorkflowOrchestrator()
        
        # Mock DB Session for Agent Lookup
        mock_db = MagicMock()
        MockSession.return_value.__enter__.return_value = mock_db
        
        mock_agent = AgentRegistry(
            id="test_agent", 
            name="Test Agent", 
            category="Testing", 
            module_path="test.mod", 
            class_name="TestClass"
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent
        
        # Mock World Model Service
        mock_wm_instance = MockWMService.return_value
        mock_wm_instance.recall_experiences = AsyncMock(return_value={"experiences": [], "knowledge": []})
        mock_wm_instance.record_experience = AsyncMock()
        
        # Mock Agent Logic Execution (dynamic import)
        with patch("builtins.__import__", side_effect=ImportError("Mocked dynamic import")):
            # We expect it to fail at import, BUT it should have already called recall_experiences
            # and attempted record_experience (failure)
            
            step = WorkflowStep(
                step_id="step1", 
                step_type=WorkflowStepType.AGENT_EXECUTION, 
                description="Run agent",
                parameters={"agent_id": "test_agent"}
            )
            context = WorkflowContext(workflow_id="wf1")
            
            await orchestrator._execute_agent_step(step, context)
            
            # Verify Recall was called
            mock_wm_instance.recall_experiences.assert_called_once()
            
            # Verify Record was called (with Failure since import failed)
            # args[0] is the AgentExperience object
            call_args = mock_wm_instance.record_experience.call_args
            self.assertIsNotNone(call_args)
            exp_obj = call_args[0][0]
            self.assertEqual(exp_obj.outcome, "Failure") # Expected failure from mock import

if __name__ == "__main__":
    unittest.main()
