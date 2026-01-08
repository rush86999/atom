import unittest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
import sys
import os

# Add backend directory to path so we can import from core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import User, UserRole, AgentRegistry, AgentStatus, AgentFeedback, FeedbackStatus
from core.agent_governance_service import AgentGovernanceService
from core.rbac_service import Permission

class TestAgentGovernance(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock(spec=Session)
        self.service = AgentGovernanceService(self.mock_db)
        
    def test_register_agent(self):
        # Mock query return None (new agent)
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        
        agent = self.service.register_or_update_agent(
            name="Test Bot",
            category="Test",
            module_path="test.mod",
            class_name="TestClass"
        )
        
        self.mock_db.add.assert_called_once()
        self.mock_db.commit.assert_called_once()
        # Verify default status
        self.assertEqual(agent.status, AgentStatus.STUDENT.value)

    async def test_feedback_penalty_specialty(self):
        # Mock Agent (Finance)
        mock_agent = AgentRegistry(
            id="a1", 
            confidence_score=0.8, 
            status=AgentStatus.SUPERVISED.value,
            category="Finance"
        )
        # Mock User (Member but Accountant)
        mock_user = User(id="u1", role=UserRole.MEMBER, specialty="Finance")
        
        # We need query to return agent first, then user, then agent again
        self.mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_user, mock_agent, mock_agent # Adjudicate: user -> agent, Update: agent
        ]
        
        await self.service.submit_feedback(
            agent_id="a1",
            user_id="u1",
            original_output="bad",
            user_correction="good"
        )
        
        # Verify confidence penalty (High impact because specialty matched)
        # 0.8 - 0.1 = 0.7
        self.assertAlmostEqual(mock_agent.confidence_score, 0.7)
        self.assertEqual(mock_agent.status, AgentStatus.SUPERVISED.value)

    def test_auto_promotion_maturity_model(self):
        # Mock Agent near threshold for Autonomous (0.9)
        mock_agent = AgentRegistry(
            id="a2", 
            name="Smart Agent", 
            confidence_score=0.88, 
            status=AgentStatus.SUPERVISED.value
        )
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_agent
        
        # Trigger boost via internal method (High impact)
        self.service._update_confidence_score("a2", positive=True, impact_level="high")
        
        # 0.88 + 0.05 = 0.93 (> 0.9 threshold)
        self.assertAlmostEqual(mock_agent.confidence_score, 0.93)
        self.assertEqual(mock_agent.status, AgentStatus.AUTONOMOUS.value)

    def test_low_impact_feedback_mismatch(self):
        # Mock Agent (Operations)
        mock_agent = AgentRegistry(
            id="a4", 
            confidence_score=0.5, 
            status=AgentStatus.INTERN.value,
            category="Operations"
        )
        # Member (Sales) - Mismatch
        mock_agent.required_role_for_autonomy = UserRole.TEAM_LEAD
        
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_agent
        
        # Call internal update directly to test math (Low Impact)
        self.service._update_confidence_score("a4", positive=True, impact_level="low")
        
        # 0.5 + 0.01 = 0.51
        self.assertAlmostEqual(mock_agent.confidence_score, 0.51)
        
    def test_manual_promotion_rbac(self):
        mock_agent = AgentRegistry(id="a3", status=AgentStatus.STUDENT.value)
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_agent
        
        # 1. Member (No permission) -> Should Fail
        member = User(role=UserRole.MEMBER)
        with patch("core.rbac_service.RBACService.check_permission", return_value=False):
            with self.assertRaises(Exception): # HTTPException in real app
                self.service.promote_to_autonomous("a3", member)
                
        # 2. Admin (Has permission) -> Should Success
        admin = User(role=UserRole.WORKSPACE_ADMIN)
        with patch("core.rbac_service.RBACService.check_permission", return_value=True):
            self.service.promote_to_autonomous("a3", admin)
            self.assertEqual(mock_agent.status, AgentStatus.AUTONOMOUS.value) # Note: promote_to_autonomous sets ACTIVE, need to check if we want that or AUTONOMOUS enum


if __name__ == "__main__":
    unittest.main()
