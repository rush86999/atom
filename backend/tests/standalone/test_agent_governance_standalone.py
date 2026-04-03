#!/usr/bin/env python3
"""
Standalone Tests for Agent Governance Service

Coverage Target: 80%+
Priority: P0 (Critical Governance)
"""
import sys
import os
sys.path.insert(0, '.')
os.environ['ENVIRONMENT'] = 'development'

from core.agent_governance_service import AgentGovernanceService
from core.models import AgentStatus, UserRole, FeedbackStatus
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio


def test_action_complexity_levels():
    """Test ACTION_COMPLEXITY classification"""
    print("Testing action complexity levels...")
    
    # Level 1: READ ONLY
    assert AgentGovernanceService.ACTION_COMPLEXITY["search"] == 1
    assert AgentGovernanceService.ACTION_COMPLEXITY["read"] == 1
    assert AgentGovernanceService.ACTION_COMPLEXITY["get"] == 1
    assert AgentGovernanceService.ACTION_COMPLEXITY["list"] == 1
    
    # Level 2: PROPOSE / DRAFT
    assert AgentGovernanceService.ACTION_COMPLEXITY["analyze"] == 2
    assert AgentGovernanceService.ACTION_COMPLEXITY["draft"] == 2
    assert AgentGovernanceService.ACTION_COMPLEXITY["suggest"] == 2
    
    # Level 3: EXECUTE (Supervised)
    assert AgentGovernanceService.ACTION_COMPLEXITY["create"] == 3
    assert AgentGovernanceService.ACTION_COMPLEXITY["update"] == 3
    assert AgentGovernanceService.ACTION_COMPLEXITY["send_email"] == 3
    
    # Level 4: CRITICAL (Autonomous)
    assert AgentGovernanceService.ACTION_COMPLEXITY["delete"] == 4
    assert AgentGovernanceService.ACTION_COMPLEXITY["execute"] == 4
    assert AgentGovernanceService.ACTION_COMPLEXITY["deploy"] == 4
    
    print("✓ Action complexity levels tests passed")


def test_maturity_requirements():
    """Test MATURITY_REQUIREMENTS mapping"""
    print("Testing maturity requirements...")
    
    assert AgentGovernanceService.MATURITY_REQUIREMENTS[1] == AgentStatus.STUDENT
    assert AgentGovernanceService.MATURITY_REQUIREMENTS[2] == AgentStatus.INTERN
    assert AgentGovernanceService.MATURITY_REQUIREMENTS[3] == AgentStatus.SUPERVISED
    assert AgentGovernanceService.MATURITY_REQUIREMENTS[4] == AgentStatus.AUTONOMOUS
    
    print("✓ Maturity requirements tests passed")


def test_service_initialization():
    """Test service initialization"""
    print("Testing service initialization...")
    mock_db = MagicMock()
    
    service = AgentGovernanceService(db=mock_db, workspace_id="test-workspace")
    
    assert service.db == mock_db
    assert service.workspace_id == "test-workspace"
    assert service.continuous_learning is not None
    
    print("✓ Service initialization tests passed")


def test_register_new_agent():
    """Test registering a new agent"""
    print("Testing register new agent...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = None  # Agent doesn't exist
    mock_db.query.return_value = mock_query
    
    service = AgentGovernanceService(db=mock_db, workspace_id="test-ws")
    
    result = service.register_or_update_agent(
        name="Test Agent",
        category="testing",
        module_path="test.module",
        class_name="TestAgent",
        description="Test agent for testing"
    )
    
    # Verify agent was created with correct defaults
    assert mock_db.add.called
    assert mock_db.commit.called
    assert mock_db.refresh.called
    assert result.status == AgentStatus.STUDENT.value
    assert result.confidence_score == 0.5
    
    print("✓ Register new agent tests passed")


def test_update_existing_agent():
    """Test updating an existing agent"""
    print("Testing update existing agent...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.name = "Old Name"
    mock_agent.status = AgentStatus.SUPERVISED.value
    mock_query.filter.return_value.first.return_value = mock_agent
    mock_db.query.return_value = mock_query
    
    service = AgentGovernanceService(db=mock_db, workspace_id="test-ws")
    
    result = service.register_or_update_agent(
        name="Updated Name",
        category="updated_category",
        module_path="test.module",
        class_name="TestAgent",
        description="Updated description",
        handle="test_handle",
        display_name="Test Display"
    )
    
    # Verify agent was updated
    assert mock_agent.name == "Updated Name"
    assert mock_agent.category == "updated_category"
    assert mock_agent.description == "Updated description"
    assert mock_agent.handle == "test_handle"
    assert mock_agent.display_name == "Test Display"
    assert mock_db.commit.called
    
    print("✓ Update existing agent tests passed")


async def test_submit_feedback():
    """Test submitting feedback"""
    print("Testing submit feedback...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-001"
    mock_query.filter.return_value.first.return_value = mock_agent
    mock_db.query.return_value = mock_query
    
    service = AgentGovernanceService(db=mock_db, workspace_id="test-ws")
    
    # Mock _adjudicate_feedback to avoid complex dependencies
    service._adjudicate_feedback = AsyncMock()
    
    result = await service.submit_feedback(
        agent_id="agent-001",
        user_id="user-001",
        original_output="Original output",
        user_correction="Corrected output",
        input_context="Test context"
    )
    
    # Verify feedback was created (without workspace_id which doesn't exist in model)
    assert mock_db.add.called
    assert mock_db.commit.called
    assert result.status == FeedbackStatus.PENDING.value
    
    # Verify adjudication was triggered
    service._adjudicate_feedback.assert_called_once()
    
    print("✓ Submit feedback tests passed")


async def test_adjudicate_feedback_trusted_user():
    """Test feedback adjudication with trusted user"""
    print("Testing adjudicate feedback (trusted user)...")
    mock_db = MagicMock()
    
    # Setup mocks
    mock_user_query = MagicMock()
    mock_user = MagicMock()
    mock_user.role = UserRole.SUPER_ADMIN.value
    mock_user.specialty = "testing"
    mock_user_query.filter.return_value.first.return_value = mock_user
    
    mock_agent_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-001"
    mock_agent.category = "testing"
    mock_agent_query.filter.return_value.first.return_value = mock_agent
    
    def query_side_effect(model):
        if model.__name__ == 'User':
            return mock_user_query
        elif model.__name__ == 'AgentRegistry':
            return mock_agent_query
        return MagicMock()
    
    mock_db.query.side_effect = query_side_effect
    
    service = AgentGovernanceService(db=mock_db, workspace_id="test-ws")
    service._update_confidence_score = MagicMock()
    service.continuous_learning = MagicMock()
    service.continuous_learning.update_from_feedback = MagicMock()
    
    mock_feedback = MagicMock()
    mock_feedback.user_id = "user-001"
    mock_feedback.agent_id = "agent-001"
    
    await service._adjudicate_feedback(mock_feedback)
    
    # Verify feedback was accepted
    assert mock_feedback.status == FeedbackStatus.ACCEPTED.value
    assert "trusted" in mock_feedback.ai_reasoning.lower()
    
    # Verify confidence was updated (negative feedback)
    service._update_confidence_score.assert_called_once_with(
        "agent-001", positive=False, impact_level="high"
    )
    
    print("✓ Adjudicate feedback (trusted user) tests passed")


async def test_adjudicate_feedback_untrusted_user():
    """Test feedback adjudication with untrusted user"""
    print("Testing adjudicate feedback (untrusted user)...")
    mock_db = MagicMock()
    
    # Setup mocks
    mock_user_query = MagicMock()
    mock_user = MagicMock()
    mock_user.role = UserRole.MEMBER.value  # Not admin
    mock_user.specialty = "different"  # Doesn't match agent category
    mock_user_query.filter.return_value.first.return_value = mock_user
    
    mock_agent_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-001"
    mock_agent.category = "testing"
    mock_agent_query.filter.return_value.first.return_value = mock_agent
    
    def query_side_effect(model):
        if model.__name__ == 'User':
            return mock_user_query
        elif model.__name__ == 'AgentRegistry':
            return mock_agent_query
        return MagicMock()
    
    mock_db.query.side_effect = query_side_effect
    
    service = AgentGovernanceService(db=mock_db, workspace_id="test-ws")
    service._update_confidence_score = MagicMock()
    
    mock_feedback = MagicMock()
    mock_feedback.user_id = "user-001"
    mock_feedback.agent_id = "agent-001"
    
    await service._adjudicate_feedback(mock_feedback)
    
    # Verify feedback is pending
    assert mock_feedback.status == FeedbackStatus.PENDING.value
    assert "pending" in mock_feedback.ai_reasoning.lower()
    
    print("✓ Adjudicate feedback (untrusted user) tests passed")


def test_enforce_action_allowed():
    """Test enforce_action for allowed action"""
    print("Testing enforce_action (allowed)...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-001"
    mock_agent.status = AgentStatus.AUTONOMOUS.value
    mock_agent.confidence_score = 0.95
    mock_query.filter.return_value.first.return_value = mock_agent
    mock_db.query.return_value = mock_query
    
    service = AgentGovernanceService(db=mock_db, workspace_id="test-ws")
    
    # Mock guardrail service to avoid complex dependencies
    with patch('core.agent_governance_service.AutonomousGuardrailService') as MockGuardrail:
        mock_guardrail = MagicMock()
        mock_guardrail.check_guardrails.return_value = {"proceed": True}
        MockGuardrail.return_value = mock_guardrail
        
        result = service.enforce_action(
            agent_id="agent-001",
            action_type="create"
        )
        
        assert result["proceed"] is True
        assert result["status"] == "APPROVED"
    
    print("✓ enforce_action (allowed) tests passed")


def test_enforce_action_denied():
    """Test enforce_action for denied action"""
    print("Testing enforce_action (denied)...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-001"
    mock_agent.status = AgentStatus.STUDENT.value
    mock_agent.confidence_score = 0.3
    mock_query.filter.return_value.first.return_value = mock_agent
    mock_db.query.return_value = mock_query
    
    service = AgentGovernanceService(db=mock_db, workspace_id="test-ws")
    
    result = service.enforce_action(
        agent_id="agent-001",
        action_type="delete"
    )
    
    assert result["proceed"] is False
    assert result["status"] == "BLOCKED"
    
    print("✓ enforce_action (denied) tests passed")


def test_can_perform_action_paused_agent():
    """Test can_perform_action for paused agent"""
    print("Testing can_perform_action (paused agent)...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-001"
    mock_agent.status = AgentStatus.PAUSED.value
    mock_query.filter.return_value.first.return_value = mock_agent
    mock_db.query.return_value = mock_query
    
    service = AgentGovernanceService(db=mock_db, workspace_id="test-ws")
    
    result = service.can_perform_action(
        agent_id="agent-001",
        action_type="create"
    )
    
    assert result["allowed"] is False
    assert "Agent is paused" in result.get("reason", "")
    
    print("✓ can_perform_action (paused agent) tests passed")


def test_can_perform_action_stopped_agent():
    """Test can_perform_action for stopped agent"""
    print("Testing can_perform_action (stopped agent)...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-001"
    mock_agent.status = AgentStatus.STOPPED.value
    mock_query.filter.return_value.first.return_value = mock_agent
    mock_db.query.return_value = mock_query
    
    service = AgentGovernanceService(db=mock_db, workspace_id="test-ws")
    
    result = service.can_perform_action(
        agent_id="agent-001",
        action_type="create"
    )
    
    assert result["allowed"] is False
    assert "Agent is stopped" in result.get("reason", "")
    
    print("✓ can_perform_action (stopped agent) tests passed")


def test_can_perform_action_require_approval():
    """Test can_perform_action with require_approval flag"""
    print("Testing can_perform_action (require approval)...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-001"
    mock_agent.status = AgentStatus.AUTONOMOUS.value
    mock_query.filter.return_value.first.return_value = mock_agent
    mock_db.query.return_value = mock_query
    
    service = AgentGovernanceService(db=mock_db, workspace_id="test-ws")
    
    result = service.can_perform_action(
        agent_id="agent-001",
        action_type="create",
        require_approval=True
    )
    
    assert result["allowed"] is True
    assert result["requires_approval"] is True
    
    print("✓ can_perform_action (require approval) tests passed")


def test_can_perform_action_supervised_complexity():
    """Test can_perform_action for SUPERVISED agent with complexity 3"""
    print("Testing can_perform_action (supervised complexity)...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-001"
    mock_agent.status = AgentStatus.SUPERVISED.value
    mock_agent.confidence_score = 0.8
    mock_query.filter.return_value.first.return_value = mock_agent
    mock_db.query.return_value = mock_query
    
    service = AgentGovernanceService(db=mock_db, workspace_id="test-ws")
    
    result = service.can_perform_action(
        agent_id="agent-001",
        action_type="send_email"
    )
    
    assert result["allowed"] is True
    assert result["requires_approval"] is True  # SUPERVISED + complexity 3 needs approval
    
    print("✓ can_perform_action (supervised complexity) tests passed")


def test_action_complexity_search():
    """Test action complexity for search actions (level 1)"""
    print("Testing action complexity (search)...")
    assert AgentGovernanceService.ACTION_COMPLEXITY["search"] == 1
    assert AgentGovernanceService.ACTION_COMPLEXITY["read"] == 1
    assert AgentGovernanceService.ACTION_COMPLEXITY["get"] == 1
    print("✓ Action complexity (search) tests passed")


def test_action_complexity_propose():
    """Test action complexity for propose actions (level 2)"""
    print("Testing action complexity (propose)...")
    assert AgentGovernanceService.ACTION_COMPLEXITY["analyze"] == 2
    assert AgentGovernanceService.ACTION_COMPLEXITY["suggest"] == 2
    assert AgentGovernanceService.ACTION_COMPLEXITY["draft"] == 2
    print("✓ Action complexity (propose) tests passed")


def test_action_complexity_execute():
    """Test action complexity for execute actions (level 3)"""
    print("Testing action complexity (execute)...")
    assert AgentGovernanceService.ACTION_COMPLEXITY["create"] == 3
    assert AgentGovernanceService.ACTION_COMPLEXITY["update"] == 3
    assert AgentGovernanceService.ACTION_COMPLEXITY["send_email"] == 3
    print("✓ Action complexity (execute) tests passed")


def test_action_complexity_critical():
    """Test action complexity for critical actions (level 4)"""
    print("Testing action complexity (critical)...")
    assert AgentGovernanceService.ACTION_COMPLEXITY["delete"] == 4
    assert AgentGovernanceService.ACTION_COMPLEXITY["execute"] == 4
    assert AgentGovernanceService.ACTION_COMPLEXITY["deploy"] == 4
    print("✓ Action complexity (critical) tests passed")


def test_maturity_requirements_all_levels():
    """Test maturity requirements for all levels"""
    print("Testing maturity requirements (all levels)...")
    assert AgentGovernanceService.MATURITY_REQUIREMENTS[1] == AgentStatus.STUDENT
    assert AgentGovernanceService.MATURITY_REQUIREMENTS[2] == AgentStatus.INTERN
    assert AgentGovernanceService.MATURITY_REQUIREMENTS[3] == AgentStatus.SUPERVISED
    assert AgentGovernanceService.MATURITY_REQUIREMENTS[4] == AgentStatus.AUTONOMOUS
    print("✓ Maturity requirements (all levels) tests passed")


def test_agent_not_found_can_perform():
    """Test can_perform_action when agent not found"""
    print("Testing can_perform_action (agent not found)...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = None
    mock_db.query.return_value = mock_query
    
    service = AgentGovernanceService(db=mock_db, workspace_id="test-ws")
    
    result = service.can_perform_action(
        agent_id="nonexistent-agent",
        action_type="create"
    )
    
    assert result["allowed"] is False
    assert "Agent not found" in result.get("reason", "")
    
    print("✓ can_perform_action (agent not found) tests passed")


def test_update_confidence_score_positive():
    """Test positive confidence score update"""
    print("Testing confidence score update (positive)...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-001"
    mock_agent.name = "Test Agent"
    mock_agent.confidence_score = 0.5
    mock_agent.status = AgentStatus.INTERN.value
    mock_query.filter.return_value.first.return_value = mock_agent
    mock_db.query.return_value = mock_query
    
    service = AgentGovernanceService(db=mock_db, workspace_id="test-ws")
    
    # Positive update with high impact
    service._update_confidence_score("agent-001", positive=True, impact_level="high")
    
    # Verify score increased
    assert mock_agent.confidence_score > 0.5
    assert mock_agent.confidence_score == 0.55  # 0.5 + 0.05
    
    print("✓ Confidence score update (positive) tests passed")


def test_update_confidence_score_negative():
    """Test negative confidence score update"""
    print("Testing confidence score update (negative)...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-001"
    mock_agent.name = "Test Agent"
    mock_agent.confidence_score = 0.5
    mock_agent.status = AgentStatus.INTERN.value
    mock_query.filter.return_value.first.return_value = mock_agent
    mock_db.query.return_value = mock_query
    
    service = AgentGovernanceService(db=mock_db, workspace_id="test-ws")
    
    # Negative update with high impact
    service._update_confidence_score("agent-001", positive=False, impact_level="high")
    
    # Verify score decreased
    assert mock_agent.confidence_score < 0.5
    assert mock_agent.confidence_score == 0.4  # 0.5 - 0.1
    
    print("✓ Confidence score update (negative) tests passed")


def test_update_confidence_score_promotion():
    """Test agent promotion based on confidence score"""
    print("Testing agent promotion...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-001"
    mock_agent.name = "Test Agent"
    mock_agent.confidence_score = 0.65  # Close to SUPERVISED
    mock_agent.status = AgentStatus.INTERN.value
    mock_query.filter.return_value.first.return_value = mock_agent
    mock_db.query.return_value = mock_query
    
    service = AgentGovernanceService(db=mock_db, workspace_id="test-ws")
    
    # Positive update should promote to SUPERVISED
    service._update_confidence_score("agent-001", positive=True, impact_level="high")
    
    # Verify promotion (0.65 + 0.05 = 0.70 -> SUPERVISED)
    assert mock_agent.status == AgentStatus.SUPERVISED.value
    
    print("✓ Agent promotion tests passed")


def test_update_confidence_score_demotion():
    """Test agent demotion based on confidence score"""
    print("Testing agent demotion...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-001"
    mock_agent.name = "Test Agent"
    mock_agent.confidence_score = 0.51  # Just above INTERN
    mock_agent.status = AgentStatus.INTERN.value
    mock_query.filter.return_value.first.return_value = mock_agent
    mock_db.query.return_value = mock_query
    
    service = AgentGovernanceService(db=mock_db, workspace_id="test-ws")
    
    # Negative update should demote to STUDENT
    service._update_confidence_score("agent-001", positive=False, impact_level="high")
    
    # Verify demotion (0.51 - 0.1 = 0.41 -> STUDENT)
    assert mock_agent.status == AgentStatus.STUDENT.value
    
    print("✓ Agent demotion tests passed")


def test_can_perform_action_allowed():
    """Test can_perform_action for allowed action"""
    print("Testing can_perform_action (allowed)...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-001"
    mock_agent.status = AgentStatus.SUPERVISED.value
    mock_agent.confidence_score = 0.8
    mock_query.filter.return_value.first.return_value = mock_agent
    mock_db.query.return_value = mock_query
    
    service = AgentGovernanceService(db=mock_db, workspace_id="test-ws")
    
    # SUPERVISED agent can perform level 3 action
    result = service.can_perform_action(
        agent_id="agent-001",
        action_type="create"
    )
    
    assert result["allowed"] is True
    assert result["action_complexity"] == 3
    assert result["agent_status"] == AgentStatus.SUPERVISED.value
    assert result["required_status"] == AgentStatus.SUPERVISED.value
    
    print("✓ can_perform_action (allowed) tests passed")


def test_can_perform_action_denied():
    """Test can_perform_action for denied action"""
    print("Testing can_perform_action (denied)...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-001"
    mock_agent.status = AgentStatus.INTERN.value
    mock_agent.confidence_score = 0.6
    mock_query.filter.return_value.first.return_value = mock_agent
    mock_db.query.return_value = mock_query
    
    service = AgentGovernanceService(db=mock_db, workspace_id="test-ws")
    
    # INTERN agent cannot perform level 4 (CRITICAL) action
    result = service.can_perform_action(
        agent_id="agent-001",
        action_type="delete"
    )
    
    assert result["allowed"] is False
    assert result["action_complexity"] == 4
    assert result["agent_status"] == AgentStatus.INTERN.value
    assert result["required_status"] == AgentStatus.AUTONOMOUS.value
    assert "Maturity check failed" in result.get("reason", "")
    
    print("✓ can_perform_action (denied) tests passed")


def test_can_perform_action_unknown_action():
    """Test can_perform_action for unknown action type"""
    print("Testing can_perform_action (unknown action)...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "agent-001"
    mock_agent.status = AgentStatus.AUTONOMOUS.value
    mock_query.filter.return_value.first.return_value = mock_agent
    mock_db.query.return_value = mock_query
    
    service = AgentGovernanceService(db=mock_db, workspace_id="test-ws")
    
    # Unknown action - should use default or highest level
    result = service.can_perform_action(
        agent_id="agent-001",
        action_type="unknown_action_xyz"
    )
    
    # AUTONOMOUS can perform any action
    assert result["allowed"] is True
    assert result["agent_status"] == AgentStatus.AUTONOMOUS.value
    
    print("✓ can_perform_action (unknown action) tests passed")


def test_agent_not_found():
    """Test handling of non-existent agent"""
    print("Testing agent not found...")
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = None
    mock_db.query.return_value = mock_query
    
    service = AgentGovernanceService(db=mock_db, workspace_id="test-ws")
    
    try:
        service.register_or_update_agent(
            name="Test",
            category="test",
            module_path="test",
            class_name="Test"
        )
        # Should create new agent, not raise error
        assert mock_db.add.called
        print("✓ Agent not found (creates new) tests passed")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        raise


async def main():
    """Run all tests"""
    print("=" * 60)
    print("Running Agent Governance Service Tests (Standalone)")
    print("=" * 60)
    
    try:
        # Sync tests
        test_action_complexity_levels()
        test_maturity_requirements()
        test_service_initialization()
        test_register_new_agent()
        test_update_existing_agent()
        test_update_confidence_score_positive()
        test_update_confidence_score_negative()
        test_update_confidence_score_promotion()
        test_update_confidence_score_demotion()
        test_can_perform_action_allowed()
        test_can_perform_action_denied()
        test_can_perform_action_unknown_action()
        test_agent_not_found()
        test_enforce_action_allowed()
        test_enforce_action_denied()
        test_can_perform_action_paused_agent()
        test_can_perform_action_stopped_agent()
        test_can_perform_action_require_approval()
        test_can_perform_action_supervised_complexity()
        test_action_complexity_search()
        test_action_complexity_propose()
        test_action_complexity_execute()
        test_action_complexity_critical()
        test_maturity_requirements_all_levels()
        test_agent_not_found_can_perform()
        
        # Async tests
        await test_submit_feedback()
        await test_adjudicate_feedback_trusted_user()
        await test_adjudicate_feedback_untrusted_user()
        
        print("=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
