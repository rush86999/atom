
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentFeedback, User, AgentStatus
from core.agent_world_model import AgentExperience

@pytest.fixture
def mock_db_session():
    session = MagicMock()
    return session

@pytest.mark.asyncio
async def test_feedback_triggers_learning(mock_db_session):
    """
    Test that submitting feedback triggers recording of an experience in World Model.
    """
    # Setup
    service = AgentGovernanceService(mock_db_session)
    
    # Mock Data
    agent = AgentRegistry(id="agent-123", name="Test Agent", category="finance", status=AgentStatus.STUDENT.value, confidence_score=0.5)
    user = User(id="user-1", email="admin@example.com", role="workspace_admin", specialty="finance")
    
    mock_db_session.query.return_value.filter.return_value.first.side_effect = [agent, user, agent, agent] 
    # 1. get agent (submit)
    # 2. get user (adjudicate)
    # 3. get agent (adjudicate)
    # 4. get agent (update_confidence)
    
    # Mock World Model
    with patch("core.agent_world_model.WorldModelService") as MockWM:
        wm_instance = MockWM.return_value
        wm_instance.record_experience = AsyncMock()
        
        # Execute
        await service.submit_feedback(
            agent_id="agent-123",
            user_id="user-1", # Admin
            original_output="Incorrect Output",
            user_correction="Correct Output",
            input_context="Think step 1"
        )
        
        # Verify World Model was called
        MockWM.assert_called()
        wm_instance.record_experience.assert_called_once()
        
        # Verify Argument (AgentExperience)
        args, _ = wm_instance.record_experience.call_args
        experience = args[0]
        assert isinstance(experience, AgentExperience)
        assert experience.agent_id == "agent-123"
        assert "User Correction: Correct Output" in experience.learnings
        assert experience.outcome == "Failure"

        # Verify Confidence Update (High impact for Admin)
        assert agent.confidence_score < 0.5 # Should decrease (penalty is 0.1)
