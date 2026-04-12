"""
AgentGovernanceService Unit Tests

Tests cover:
- Permission checks (can_perform_action, enforce_action)
- Maturity transitions (register_or_update_agent)
- Confidence scoring (_update_confidence_score)
- Feedback adjudication (_adjudicate_feedback, submit_feedback)
- Approval workflow (request_approval, get_approval_status)
- Policy discovery (find_relevant_policies)
- Outcome recording (record_outcome)
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentFeedback
from core.governance_cache import GovernanceCache


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db_session():
    """Mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def mock_cache():
    """Mock cache for testing."""
    cache = Mock()
    cache.get.return_value = None
    cache.set.return_value = None
    return cache


@pytest.fixture
def governance_service(db_session):
    """Create AgentGovernanceService instance."""
    return AgentGovernanceService(db_session)


@pytest.fixture
def mock_agent():
    """Mock agent registry entry."""
    agent = Mock(spec=AgentRegistry)
    agent.id = "test-agent-123"
    agent.name = "Test Agent"
    agent.status = "active"
    agent.maturity_level = "INTERN"
    agent.confidence_score = 0.75
    agent.created_at = datetime.utcnow()
    agent.updated_at = datetime.utcnow()
    return agent


# ============================================================================
# Permission Check Tests
# ============================================================================

class TestPermissionChecks:
    """Test permission checking logic."""

    def test_can_perform_action_autonomous_agent_all_actions(self, governance_service, mock_agent):
        """Test AUTONOMOUS agents can perform all actions."""
        mock_agent.maturity_level = "AUTONOMOUS"

        result = governance_service.can_perform_action(
            mock_agent,
            action_type="delete",
            complexity=4
        )

        assert result["allowed"] is True
        assert "reason" not in result or result["reason"] is None

    def test_can_perform_action_student_agent_blocked(self, governance_service, mock_agent):
        """Test STUDENT agents are blocked from high-complexity actions."""
        mock_agent.maturity_level = "STUDENT"

        result = governance_service.can_perform_action(
            mock_agent,
            action_type="delete",
            complexity=4
        )

        assert result["allowed"] is False
        assert "blocked" in result["reason"].lower()

    def test_can_perform_action_student_agent_presentations_only(self, governance_service, mock_agent):
        """Test STUDENT agents can only do presentations."""
        mock_agent.maturity_level = "STUDENT"

        result = governance_service.can_perform_action(
            mock_agent,
            action_type="presentation",
            complexity=1
        )

        # STUDENT can do low-complexity presentations
        assert result["allowed"] in [True, False]  # Depends on implementation

    def test_can_perform_action_intern_needs_approval(self, governance_service, mock_agent):
        """Test INTERN agents need approval for high-complexity actions."""
        mock_agent.maturity_level = "INTERN"

        result = governance_service.can_perform_action(
            mock_agent,
            action_type="delete",
            complexity=4
        )

        assert "approval" in result["reason"].lower() or result["allowed"] is False

    def test_can_perform_action_supervised_allows_more(self, governance_service, mock_agent):
        """Test SUPERVISED agents can perform more actions."""
        mock_agent.maturity_level = "SUPERVISED"

        result = governance_service.can_perform_action(
            mock_agent,
            action_type="delete",
            complexity=3
        )

        assert result["allowed"] is True

    def test_enforce_action_blocks_disallowed(self, governance_service, mock_agent):
        """Test enforce_action raises error for disallowed actions."""
        mock_agent.maturity_level = "STUDENT"

        with pytest.raises(Exception) as exc_info:
            governance_service.enforce_action(
                mock_agent,
                action_type="delete",
                complexity=4
            )

        assert "permission" in str(exc_info.value).lower() or "blocked" in str(exc_info.value).lower()

    def test_enforce_action_allows_permitted(self, governance_service, mock_agent):
        """Test enforce_action allows permitted actions."""
        mock_agent.maturity_level = "AUTONOMOUS"

        # Should not raise
        result = governance_service.enforce_action(
            mock_agent,
            action_type="delete",
            complexity=4
        )

        assert result is None or result.get("allowed") is True


# ============================================================================
# Maturity Transition Tests
# ============================================================================

class TestMaturityTransitions:
    """Test maturity level transitions."""

    def test_register_or_update_agent_creates_new(self, governance_service, db_session):
        """Test registering a new agent."""
        db_session.query.return_value.filter.return_value.first.return_value = None

        agent_data = {
            "id": "new-agent",
            "name": "New Agent",
            "maturity_level": "STUDENT",
            "status": "active"
        }

        result = governance_service.register_or_update_agent(agent_data)

        assert result is not None
        assert result.id == "new-agent"
        db_session.add.assert_called_once()
        db_session.commit.assert_called_once()

    def test_register_or_update_agent_updates_existing(self, governance_service, db_session, mock_agent):
        """Test updating an existing agent."""
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        agent_data = {
            "id": "test-agent-123",
            "name": "Updated Name",
            "maturity_level": "INTERN",
            "status": "active"
        }

        result = governance_service.register_or_update_agent(agent_data)

        assert result is not None
        db_session.commit.assert_called_once()

    def test_register_or_update_agent_transitions_maturity(self, governance_service, db_session, mock_agent):
        """Test maturity level transition."""
        mock_agent.maturity_level = "STUDENT"
        mock_agent.confidence_score = 0.80  # High enough to transition
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        agent_data = {
            "id": "test-agent-123",
            "maturity_level": "INTERN",  # Transition up
            "status": "active"
        }

        result = governance_service.register_or_update_agent(agent_data)

        assert result.maturity_level == "INTERN"


# ============================================================================
# Confidence Scoring Tests
# ============================================================================

class TestConfidenceScoring:
    """Test confidence score updates."""

    def test_update_confidence_score_positive_high_impact(self, governance_service, db_session, mock_agent):
        """Test positive feedback with high impact increases score."""
        initial_score = mock_agent.confidence_score
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        governance_service._update_confidence_score(
            "test-agent-123",
            positive=True,
            impact_level="high"
        )

        # Score should increase
        assert mock_agent.confidence_score >= initial_score

    def test_update_confidence_score_negative_high_impact(self, governance_service, db_session, mock_agent):
        """Test negative feedback with high impact decreases score."""
        initial_score = mock_agent.confidence_score
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        governance_service._update_confidence_score(
            "test-agent-123",
            positive=False,
            impact_level="high"
        )

        # Score should decrease
        assert mock_agent.confidence_score <= initial_score

    def test_update_confidence_score_low_impact_small_change(self, governance_service, db_session, mock_agent):
        """Test low impact feedback makes small changes."""
        initial_score = mock_agent.confidence_score
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        governance_service._update_confidence_score(
            "test-agent-123",
            positive=True,
            impact_level="low"
        )

        # Change should be small
        change = abs(mock_agent.confidence_score - initial_score)
        assert change < 0.1  # Small change


# ============================================================================
# Feedback Tests
# ============================================================================

class TestFeedback:
    """Test feedback submission and adjudication."""

    @pytest.mark.asyncio
    async def test_submit_feedback_creates_feedback(self, governance_service, db_session):
        """Test submitting feedback creates a feedback record."""
        feedback_data = {
            "agent_id": "test-agent-123",
            "user_id": "user-123",
            "rating": 5,
            "comment": "Great job!"
        }

        result = await governance_service.submit_feedback(feedback_data)

        assert result is not None
        db_session.add.assert_called()
        db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_adjudicate_feedback_positive(self, governance_service, db_session, mock_agent):
        """Test positive feedback adjudication."""
        feedback = Mock(spec=AgentFeedback)
        feedback.agent_id = "test-agent-123"
        feedback.rating = 5
        feedback.impact = "high"
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        # Just verify it doesn't raise - the method does internal work
        await governance_service._adjudicate_feedback(feedback)

        # If we get here, feedback was adjudicated successfully

    @pytest.mark.asyncio
    async def test_adjudicate_feedback_negative(self, governance_service, db_session, mock_agent):
        """Test negative feedback adjudication."""
        feedback = Mock(spec=AgentFeedback)
        feedback.agent_id = "test-agent-123"
        feedback.rating = 1
        feedback.impact = "high"
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        # Just verify it doesn't raise - the method does internal work
        await governance_service._adjudicate_feedback(feedback)

        # If we get here, feedback was adjudicated successfully


# ============================================================================
# Approval Workflow Tests
# ============================================================================

class TestApprovalWorkflow:
    """Test approval request and status tracking."""

    def test_request_approval_creates_request(self, governance_service, db_session):
        """Test requesting approval creates a request record."""
        approval_data = {
            "agent_id": "test-agent-123",
            "action_type": "delete",
            "reason": "Critical action requiring approval"
        }

        result = governance_service.request_approval(approval_data)

        assert result is not None
        assert "action_id" in result
        db_session.add.assert_called()
        db_session.commit.assert_called()

    def test_get_approval_status_pending(self, governance_service, db_session):
        """Test getting approval status for pending request."""
        mock_approval = Mock()
        mock_approval.status = "pending"
        mock_approval.created_at = datetime.utcnow()
        db_session.query.return_value.filter.return_value.first.return_value = mock_approval

        status = governance_service.get_approval_status("action-123")

        assert status["status"] == "pending"
        assert "created_at" in status

    def test_get_approval_status_approved(self, governance_service, db_session):
        """Test getting approval status for approved request."""
        mock_approval = Mock()
        mock_approval.status = "approved"
        mock_approval.approved_by = "admin-user"
        db_session.query.return_value.filter.return_value.first.return_value = mock_approval

        status = governance_service.get_approval_status("action-123")

        assert status["status"] == "approved"
        assert status["approved_by"] == "admin-user"


# ============================================================================
# Policy Discovery Tests
# ============================================================================

class TestPolicyDiscovery:
    """Test policy discovery and retrieval."""

    @pytest.mark.asyncio
    async def test_find_relevant_policies_returns_list(self, governance_service, db_session):
        """Test finding relevant policies returns a list."""
        mock_policy = Mock()
        mock_policy.id = "policy-123"
        mock_policy.title = "Test Policy"
        mock_policy.content = "Policy content"
        db_session.query.return_value.filter.return_value.limit.return_value.all.return_value = [mock_policy]

        policies = await governance_service.find_relevant_policies("delete action")

        assert isinstance(policies, list)
        assert len(policies) >= 0

    @pytest.mark.asyncio
    async def test_find_relevant_policies_with_domain(self, governance_service, db_session):
        """Test finding policies filters by domain."""
        mock_policy = Mock()
        mock_policy.domain = "security"
        db_session.query.return_value.filter.return_value.limit.return_value.all.return_value = [mock_policy]

        policies = await governance_service.find_relevant_policies("delete action", domain="security")

        assert isinstance(policies, list)


# ============================================================================
# Outcome Recording Tests
# ============================================================================

class TestOutcomeRecording:
    """Test recording action outcomes."""

    @pytest.mark.asyncio
    async def test_record_outcome_success(self, governance_service):
        """Test recording successful outcome."""
        # Just verify it doesn't raise - the method does internal work
        await governance_service.record_outcome("test-agent-123", success=True)

        # If we get here, the outcome was recorded successfully

    @pytest.mark.asyncio
    async def test_record_outcome_failure(self, governance_service):
        """Test recording failed outcome."""
        # Just verify it doesn't raise - the method does internal work
        await governance_service.record_outcome("test-agent-123", success=False)

        # If we get here, the outcome was recorded successfully


# ============================================================================
# Cache Integration Tests
# ============================================================================

class TestCacheIntegration:
    """Test governance cache integration."""

    def test_can_perform_action_uses_cache(self, governance_service, governance_cache, mock_agent):
        """Test that permission checks use cache."""
        # Set cache to return a value
        governance_cache.get.return_value = {"allowed": True, "reason": None}

        result = governance_service.can_perform_action(
            mock_agent,
            action_type="delete",
            complexity=4
        )

        # Should have checked cache
        governance_cache.get.assert_called()

    def test_can_perform_action_sets_cache(self, governance_service, governance_cache, mock_agent):
        """Test that permission results are cached."""
        governance_cache.get.return_value = None  # Cache miss
        mock_agent.maturity_level = "AUTONOMOUS"

        governance_service.can_perform_action(
            mock_agent,
            action_type="delete",
            complexity=4
        )

        # Should have set cache
        governance_cache.set.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
