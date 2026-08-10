
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from core.agent_governance_service import AgentGovernanceService
from core.agent_world_model import AgentExperience
from core.models import AgentFeedback, AgentRegistry, AgentStatus, User


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
    user = User(id="user-1", email="admin@example.com", role="workspace_admin", first_name="Test", last_name="User", status="active")
    
    mock_db_session.query.return_value.filter.return_value.first.side_effect = [agent, user, agent, agent] 
    # 1. get agent (submit)
    # 2. get user (adjudicate)
    # 3. get agent (adjudicate)
    # 4. get agent (update_confidence)
    
    # Mock continuous learning (constructed during __init__, patch the instance)
    cl_instance = MagicMock()
    service.continuous_learning = cl_instance

    # Execute
    await service.submit_feedback(
        agent_id="agent-123",
        user_id="user-1", # Admin
        original_output="Incorrect Output",
        user_correction="Correct Output",
        input_context="Think step 1"
    )

    # Verify continuous learning received the adjudicated feedback
    cl_instance.update_from_feedback.assert_called_once()
    fed_feedback = cl_instance.update_from_feedback.call_args[0][0]
    assert isinstance(fed_feedback, AgentFeedback)
    assert fed_feedback.agent_id == "agent-123"
    assert fed_feedback.user_correction == "Correct Output"

    # Verify Confidence Update (High impact for Admin)
    assert agent.confidence_score < 0.5 # Should decrease (penalty is 0.1)
