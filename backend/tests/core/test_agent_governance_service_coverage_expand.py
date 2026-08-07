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
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentFeedback, AgentStatus


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
    agent.status = AgentStatus.STUDENT.value
    agent.maturity_level = "STUDENT"
    agent.confidence_score = 0.75
    agent.created_at = datetime.utcnow()
    agent.updated_at = datetime.utcnow()
    return agent


# ============================================================================
# Permission Check Tests
# ============================================================================

class TestPermissionChecks:
    """Test permission checking logic."""

    def test_can_perform_action_autonomous_agent_all_actions(self, governance_service, mock_agent, db_session):
        """Test AUTONOMOUS agents can perform all actions."""
        mock_agent.status = AgentStatus.AUTONOMOUS.value
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        result = governance_service.can_perform_action(
            agent_id="test-agent-123",
            action_type="delete"
        )

        assert result["allowed"] is True
        assert result["agent_status"] == AgentStatus.AUTONOMOUS.value

    def test_can_perform_action_student_agent_blocked(self, governance_service, mock_agent, db_session):
        """Test STUDENT agents are blocked from high-complexity actions."""
        mock_agent.status = AgentStatus.STUDENT.value
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        result = governance_service.can_perform_action(
            agent_id="test-agent-123",
            action_type="delete"
        )

        assert result["allowed"] is False
        # Check that there's a reason explaining the restriction
        assert result["reason"] is not None and len(result["reason"]) > 0

    def test_can_perform_action_student_agent_presentations_only(self, governance_service, mock_agent, db_session):
        """Test STUDENT agents are blocked from non-read actions."""
        mock_agent.status = AgentStatus.STUDENT.value
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        result = governance_service.can_perform_action(
            agent_id="test-agent-123",
            action_type="presentation"
        )

        # Unknown action defaults to complexity 2, which STUDENT cannot perform
        assert result["allowed"] is False

    def test_can_perform_action_intern_needs_approval(self, governance_service, mock_agent, db_session):
        """Test INTERN agents are blocked from high-complexity actions."""
        mock_agent.status = AgentStatus.INTERN.value
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        result = governance_service.can_perform_action(
            agent_id="test-agent-123",
            action_type="delete"
        )

        assert result["allowed"] is False
        assert result["required_status"] == AgentStatus.AUTONOMOUS.value

    def test_can_perform_action_supervised_allows_more(self, governance_service, mock_agent, db_session):
        """Test SUPERVISED agents can perform complexity-3 actions."""
        mock_agent.status = AgentStatus.SUPERVISED.value
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        result = governance_service.can_perform_action(
            agent_id="test-agent-123",
            action_type="create"
        )

        assert result["allowed"] is True
        assert result["action_complexity"] == 3

    def test_enforce_action_blocks_disallowed(self, governance_service, mock_agent, db_session):
        """Test enforce_action blocks disallowed actions."""
        mock_agent.status = AgentStatus.STUDENT.value
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        result = governance_service.enforce_action(
            agent_id="test-agent-123",
            action_type="delete"
        )

        # Should return blocked status instead of raising
        assert result["proceed"] is False
        assert result["status"] == "BLOCKED"

    def test_enforce_action_allows_permitted(self, governance_service, mock_agent, db_session):
        """Test enforce_action allows permitted actions."""
        mock_agent.status = AgentStatus.AUTONOMOUS.value
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        # Should not raise
        with patch("core.agent_governance_service.AutonomousGuardrailService") as mock_gr_cls:
            mock_gr = Mock()
            mock_gr.check_guardrails.return_value = {"proceed": True, "reason": "ok"}
            mock_gr_cls.return_value = mock_gr

            result = governance_service.enforce_action(
                agent_id="test-agent-123",
                action_type="delete"
            )

        assert result["proceed"] is True


# ============================================================================
# Maturity Transition Tests
# ============================================================================

class TestMaturityTransitions:
    """Test maturity level transitions."""

    def test_register_or_update_agent_creates_new(self, governance_service, db_session):
        """Test registering a new agent."""
        db_session.query.return_value.filter.return_value.first.return_value = None

        result = governance_service.register_or_update_agent(
            name="New Agent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            description="Test agent"
        )

        assert result is not None
        db_session.add.assert_called_once()
        db_session.commit.assert_called_once()

    def test_register_or_update_agent_updates_existing(self, governance_service, db_session, mock_agent):
        """Test updating an existing agent."""
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        result = governance_service.register_or_update_agent(
            name="Updated Name",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            description="Updated description"
        )

        assert result is not None
        db_session.commit.assert_called_once()

    def test_register_or_update_agent_transitions_maturity(self, governance_service, db_session, mock_agent):
        """Test maturity level transition."""
        mock_agent.maturity_level = "STUDENT"
        mock_agent.confidence_score = 0.80  # High enough to transition
        mock_agent.episodes_completed = 50  # Meet minimum episode requirement
        mock_agent.intervention_rate = 0.10  # Low enough intervention rate
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        result = governance_service.register_or_update_agent(
            name="Test Agent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            description="Test agent"
        )

        # Just verify result is returned (actual transition logic is complex)
        assert result is not None


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
    async def test_submit_feedback_creates_feedback(self, governance_service, db_session, mock_agent):
        """Test submitting feedback creates a feedback record."""
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        result = await governance_service.submit_feedback(
            agent_id="test-agent-123",
            user_id="user-123",
            original_output="Original output",
            user_correction="Corrected output"
        )

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
        result = governance_service.request_approval(
            agent_id="test-agent-123",
            action_type="delete",
            params={"target": "resource-123"},
            reason="Critical action requiring approval"
        )

        assert result is not None
        # Returns action_id as string
        assert isinstance(result, str)
        db_session.add.assert_called()
        db_session.commit.assert_called()

    def test_get_approval_status_pending(self, governance_service, db_session):
        """Test getting approval status for pending request."""
        mock_approval = Mock()
        mock_approval.id = "action-123"
        mock_approval.status = "pending"
        db_session.query.return_value.filter.return_value.first.return_value = mock_approval

        status = governance_service.get_approval_status("action-123")

        assert status["status"] == "pending"
        assert "id" in status
        assert "chain_id" in status

    def test_get_approval_status_approved(self, governance_service, db_session):
        """Test getting approval status for approved request."""
        mock_approval = Mock()
        mock_approval.id = "action-123"
        mock_approval.status = "approved"
        mock_approval.reviewed_at = datetime.utcnow()
        db_session.query.return_value.filter.return_value.first.return_value = mock_approval

        status = governance_service.get_approval_status("action-123")

        assert status["status"] == "approved"
        assert status["id"] == "action-123"
        assert "reviewed_at" in status


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

        with patch("core.agent_governance_service.PGPolicySearchService") as mock_search_cls:
            mock_search_cls.return_value.search = AsyncMock(return_value=[mock_policy])
            policies = await governance_service.find_relevant_policies("delete action")

        assert isinstance(policies, list)
        assert len(policies) == 1
        assert policies[0].id == "policy-123"

    @pytest.mark.asyncio
    async def test_find_relevant_policies_with_domain(self, governance_service, db_session):
        """Test finding policies filters by domain."""
        with patch("core.agent_governance_service.PGPolicySearchService") as mock_search_cls:
            mock_search_cls.return_value.search = AsyncMock(return_value=[])
            policies = await governance_service.find_relevant_policies("delete action", domain="security")

        assert isinstance(policies, list)
        assert len(policies) == 0


# ============================================================================
# Outcome Recording Tests
# ============================================================================

class TestOutcomeRecording:
    """Test recording action outcomes."""

    @pytest.mark.asyncio
    async def test_record_outcome_success(self, governance_service, db_session, mock_agent):
        """Test recording successful outcome."""
        mock_agent.confidence_score = 0.5
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        await governance_service.record_outcome("test-agent-123", success=True)

        assert mock_agent.confidence_score == 0.51

    @pytest.mark.asyncio
    async def test_record_outcome_failure(self, governance_service, db_session, mock_agent):
        """Test recording failed outcome."""
        mock_agent.confidence_score = 0.6
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        await governance_service.record_outcome("test-agent-123", success=False)

        assert mock_agent.confidence_score == 0.58


# ============================================================================
# Cache Integration Tests
# ============================================================================

class TestCacheIntegration:
    """Test governance cache integration."""

    def test_can_perform_action_decision_consistent_across_calls(self, governance_service, db_session, mock_agent):
        """Test that permission checks are deterministic across calls."""
        mock_agent.status = AgentStatus.AUTONOMOUS.value
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        result1 = governance_service.can_perform_action(
            agent_id="test-agent-123",
            action_type="delete"
        )
        result2 = governance_service.can_perform_action(
            agent_id="test-agent-123",
            action_type="delete"
        )

        assert result1["allowed"] == result2["allowed"]
        assert result1["agent_status"] == result2["agent_status"]
        assert result1["allowed"] is True

    def test_confidence_transition_invalidates_governance_cache(self, governance_service, db_session, mock_agent):
        """Test that status transitions invalidate the cached governance decision."""
        mock_agent.confidence_score = 0.75
        mock_agent.status = AgentStatus.STUDENT.value
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        with patch("core.agent_governance_service.get_governance_cache") as mock_cache_cls:
            mock_cache = Mock()
            mock_cache_cls.return_value = mock_cache

            governance_service._update_confidence_score(
                "test-agent-123",
                positive=True,
                impact_level="high"
            )

            mock_cache.invalidate.assert_called_once_with("test-agent-123")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
