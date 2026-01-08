import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.atom_meta_agent import (
    AtomMetaAgent, 
    SpecialtyAgentTemplate, 
    AgentTriggerMode,
    handle_manual_trigger,
    handle_data_event_trigger
)
from core.models import AgentRegistry, AgentStatus, User, UserRole


class TestAtomMetaAgent(unittest.TestCase):
    
    def setUp(self):
        # Mock dependencies
        with patch("core.atom_meta_agent.WorldModelService"), \
             patch("core.atom_meta_agent.AdvancedWorkflowOrchestrator"):
            self.atom = AtomMetaAgent(workspace_id="test_workspace")
    
    def test_specialty_templates_exist(self):
        """Verify all expected specialty agent templates are defined"""
        templates = SpecialtyAgentTemplate.TEMPLATES
        
        self.assertIn("finance_analyst", templates)
        self.assertIn("sales_assistant", templates)
        self.assertIn("ops_coordinator", templates)
        self.assertIn("hr_assistant", templates)
        self.assertIn("marketing_analyst", templates)
        
        # Verify template structure
        finance = templates["finance_analyst"]
        self.assertEqual(finance["category"], "Finance")
        self.assertIn("reconciliation", finance["capabilities"])
    
    async def test_spawn_agent_from_template(self):
        """Test spawning an agent from a predefined template"""
        agent = await self.atom.spawn_agent("finance_analyst", persist=False)
        
        self.assertIsNotNone(agent)
        self.assertIn("spawned_finance_analyst", agent.id)
        self.assertEqual(agent.category, "Finance")
        self.assertEqual(agent.status, AgentStatus.STUDENT.value)  # New agents start as STUDENT
        self.assertEqual(agent.confidence_score, 0.5)  # Default confidence
    
    async def test_spawn_unknown_template_fails(self):
        """Test that spawning unknown template raises error"""
        with self.assertRaises(ValueError):
            await self.atom.spawn_agent("nonexistent_template")
    
    async def test_execute_with_manual_trigger(self):
        """Test Atom execution with manual trigger mode"""
        # Mock World Model
        self.atom.world_model = MagicMock()
        self.atom.world_model.recall_experiences = AsyncMock(return_value={
            "experiences": [],
            "knowledge": []
        })
        self.atom.world_model.record_experience = AsyncMock()
        
        result = await self.atom.execute(
            request="Analyze my Q4 expenses",
            context={"user_id": "test_user"},
            trigger_mode=AgentTriggerMode.MANUAL
        )
        
        self.assertEqual(result["trigger_mode"], "manual")
        self.assertIn("actions_executed", result)
        self.assertIn("final_output", result)
        
        # Verify experience was recorded
        self.atom.world_model.record_experience.assert_called_once()
    
    async def test_execute_spawns_finance_agent_for_expense_query(self):
        """Test that expense-related queries spawn a finance agent"""
        self.atom.world_model = MagicMock()
        self.atom.world_model.recall_experiences = AsyncMock(return_value={"experiences": [], "knowledge": []})
        self.atom.world_model.record_experience = AsyncMock()
        
        result = await self.atom.execute(
            request="Help me reconcile the payroll for December",
            trigger_mode=AgentTriggerMode.MANUAL
        )
        
        # Should have spawned a finance agent
        self.assertIn("spawned_agent", result)
        self.assertIn("finance_analyst", result["spawned_agent"])
        
        # Verify action was recorded
        actions = result["actions_executed"]
        spawn_action = next((a for a in actions if a["action"] == "spawn_agent"), None)
        self.assertIsNotNone(spawn_action)
        self.assertEqual(spawn_action["agent_name"], "Finance Analyst")
    
    async def test_data_event_trigger(self):
        """Test event-driven trigger for new data"""
        with patch("core.atom_meta_agent.AtomMetaAgent.execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"status": "success", "final_output": "Processed"}
            
            result = await handle_data_event_trigger(
                event_type="invoice_uploaded",
                data={"invoice_id": "INV-123", "amount": 5000},
                workspace_id="test"
            )
            
            # Verify execute was called with DATA_EVENT trigger mode
            call_args = mock_execute.call_args
            self.assertEqual(call_args.kwargs["trigger_mode"], AgentTriggerMode.DATA_EVENT)


class TestAtomIntegration(unittest.TestCase):
    """Integration tests for Atom in the broader system"""
    
    @patch("core.atom_meta_agent.SessionLocal")
    async def test_persist_spawned_agent(self, mock_session):
        """Test that persisted agents get registered in database"""
        mock_db = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db
        
        with patch("core.atom_meta_agent.WorldModelService"), \
             patch("core.atom_meta_agent.AdvancedWorkflowOrchestrator"), \
             patch("core.atom_meta_agent.AgentGovernanceService") as mock_gov:
            
            mock_gov_instance = mock_gov.return_value
            mock_gov_instance.register_or_update_agent.return_value = AgentRegistry(
                id="persisted_agent_123",
                name="Sales Assistant",
                category="Sales"
            )
            
            atom = AtomMetaAgent()
            agent = await atom.spawn_agent("sales_assistant", persist=True)
            
            # Verify governance service was called to persist
            mock_gov_instance.register_or_update_agent.assert_called_once()


if __name__ == "__main__":
    unittest.main()
