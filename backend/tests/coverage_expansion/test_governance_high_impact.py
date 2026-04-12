"""
High-impact coverage tests for agent_governance_service.py

Focus on uncovered code paths that don't require schema changes:
- can_perform_action edge cases (budget checks, unknown actions)
- enforce_action guardrail paths
- Feedback adjudication logic
- Confidence score transitions
- Policy discovery

Target: Increase coverage by testing existing functionality
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.models import (
    AgentRegistry,
    AgentStatus,
    AgentFeedback,
    FeedbackStatus,
    User,
    UserRole,
)
from core.database import SessionLocal


class TestGovernanceHighImpact:
    """High-impact coverage for AgentGovernanceService."""

    @pytest.fixture
    def db_session(self):
        """Get test database session."""
        session = SessionLocal()
        yield session
        session.rollback()
        session.close()

    @pytest.fixture
    def governance_service(self, db_session):
        """Get governance service instance."""
        return AgentGovernanceService(db_session)

    @pytest.fixture
    def test_user(self, db_session):
        """Create test user."""
        user = User(
            id="test-user-123",
            email="test@example.com",
            role=UserRole.WORKSPACE_ADMIN,
            specialty="Finance"
        )
        db_session.add(user)
        db_session.commit()
        return user

    @pytest.fixture
    def test_agent(self, db_session):
        """Create test agent directly without using register_or_update_agent."""
        agent = AgentRegistry(
            id="test-agent-123",
            name="Test Agent",
            category="Finance",
            module_path="test.finance",
            class_name="FinanceAgent",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.5,
            workspace_id="default"
        )
        db_session.add(agent)
        db_session.commit()
        return agent

    # ==========================================================================
    # can_perform_action - Edge Cases & Error Paths
    # ==========================================================================

    def test_can_perform_action_unknown_action_default_complexity(self, governance_service, test_agent):
        """Test action type not in complexity mapping defaults to level 2."""
        result = governance_service.can_perform_action(
            agent_id=test_agent.id,
            action_type="unknown_action_xyz123"
        )

        assert "complexity" in result
        assert result["complexity"] == 2  # Default complexity

    def test_can_perform_action_budget_service_unavailable(self, governance_service, test_agent, db_session):
        """Test budget check failure is logged but doesn't block."""
        # Set agent to AUTONOMOUS to pass maturity check
        test_agent.status = AgentStatus.AUTONOMOUS.value
        db_session.commit()

        # Mock BudgetEnforcementService to raise exception
        with patch('core.agent_governance_service.BudgetEnforcementService') as mock_budget:
            mock_budget.return_value.check_budget_before_action.side_effect = Exception("Service unavailable")

            result = governance_service.can_perform_action(
                agent_id=test_agent.id,
                action_type="read"
            )

            # Should still allow (budget check failure is non-blocking)
            assert result["allowed"] == True

    def test_can_perform_action_stopped_agent(self, governance_service, test_agent, db_session):
        """Test stopped agent cannot perform actions."""
        test_agent.status = AgentStatus.STOPPED.value
        db_session.commit()

        result = governance_service.can_perform_action(
            agent_id=test_agent.id,
            action_type="read"
        )

        assert result["allowed"] == False
        assert "stopped" in result["reason"].lower()

    def test_can_perform_action_deprecated_agent(self, governance_service, test_agent, db_session):
        """Test deprecated agent cannot perform actions."""
        test_agent.status = AgentStatus.DEPRECATED.value
        db_session.commit()

        result = governance_service.can_perform_action(
            agent_id=test_agent.id,
            action_type="read"
        )

        assert result["allowed"] == False
        assert "deprecated" in result["reason"].lower()

    # ==========================================================================
    # enforce_action - Guardrail & Approval Paths
    # ==========================================================================

    def test_enforce_action_blocked_by_maturity(self, governance_service, test_agent, db_session):
        """Test action blocked by maturity check."""
        # Student agent trying high complexity action
        test_agent.status = AgentStatus.STUDENT.value
        db_session.commit()

        result = governance_service.enforce_action(
            agent_id=test_agent.id,
            action_type="delete"
        )

        assert result["proceed"] == False
        assert result["status"] == "BLOCKED"

    def test_enforce_action_supervised_requires_approval(self, governance_service, test_agent, db_session):
        """Test supervised agent with high complexity requires approval."""
        test_agent.status = AgentStatus.SUPERVISED.value
        db_session.commit()

        result = governance_service.enforce_action(
            agent_id=test_agent.id,
            action_type="delete"  # Complexity 4
        )

        assert result["proceed"] == True
        assert result["status"] == "PENDING_APPROVAL"
        assert result["action_required"] == "WAIT_FOR_APPROVAL"

    def test_enforce_action_autonomous_approved(self, governance_service, test_agent, db_session):
        """Test autonomous agent approved for low complexity."""
        test_agent.status = AgentStatus.AUTONOMOUS.value
        db_session.commit()

        result = governance_service.enforce_action(
            agent_id=test_agent.id,
            action_type="read"
        )

        assert result["proceed"] == True
        assert result["status"] == "APPROVED"

    # ==========================================================================
    # Feedback Adjudication
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_submit_feedback_admin_auto_accepted(self, governance_service, test_agent, test_user, db_session):
        """Test admin feedback is auto-accepted."""
        test_user.role = UserRole.WORKSPACE_ADMIN
        db_session.commit()

        feedback = await governance_service.submit_feedback(
            agent_id=test_agent.id,
            user_id=test_user.id,
            original_output="Bad output",
            user_correction="Better output"
        )

        assert feedback.status == FeedbackStatus.ACCEPTED.value
        assert "trusted" in feedback.ai_reasoning.lower()

    @pytest.mark.asyncio
    async def test_submit_feedback_specialty_match_accepted(self, governance_service, test_agent, test_user, db_session):
        """Test feedback from user with matching specialty is accepted."""
        # User specialty matches agent category
        test_user.specialty = "Finance"
        test_user.role = UserRole.MEMBER
        db_session.commit()

        feedback = await governance_service.submit_feedback(
            agent_id=test_agent.id,
            user_id=test_user.id,
            original_output="Output",
            user_correction="Correction"
        )

        assert feedback.status == FeedbackStatus.ACCEPTED.value

    @pytest.mark.asyncio
    async def test_submit_feedback_non_specialist_pending(self, governance_service, test_agent, test_user, db_session):
        """Test feedback from non-specialist requires review."""
        test_user.specialty = "Engineering"  # Doesn't match Finance
        test_user.role = UserRole.MEMBER
        db_session.commit()

        feedback = await governance_service.submit_feedback(
            agent_id=test_agent.id,
            user_id=test_user.id,
            original_output="Output",
            user_correction="Correction"
        )

        assert feedback.status == FeedbackStatus.PENDING.value
        assert "specialty" in feedback.ai_reasoning.lower()

    @pytest.mark.asyncio
    async def test_submit_feedback_with_input_context(self, governance_service, test_agent, test_user, db_session):
        """Test feedback submission with input context."""
        test_user.role = UserRole.WORKSPACE_ADMIN
        db_session.commit()

        feedback = await governance_service.submit_feedback(
            agent_id=test_agent.id,
            user_id=test_user.id,
            original_output="Output",
            user_correction="Correction",
            input_context="User asked for X but got Y"
        )

        assert feedback.input_context == "User asked for X but got Y"
        assert feedback.status == FeedbackStatus.ACCEPTED.value

    @pytest.mark.asyncio
    async def test_adjudicate_feedback_continuous_learning_failure(self, governance_service, test_agent, test_user, db_session):
        """Test continuous learning failure doesn't block feedback."""
        test_user.role = UserRole.WORKSPACE_ADMIN
        db_session.commit()

        # Mock continuous learning to raise exception
        with patch.object(governance_service.continuous_learning, 'update_from_feedback', side_effect=Exception("DB error")):
            feedback = await governance_service.submit_feedback(
                agent_id=test_agent.id,
                user_id=test_user.id,
                original_output="Output",
                user_correction="Correction"
            )

            # Feedback should still be accepted
            assert feedback.status == FeedbackStatus.ACCEPTED.value

    # ==========================================================================
    # Confidence Score Updates
    # ==========================================================================

    def test_update_confidence_positive_high_impact(self, governance_service, test_agent, db_session):
        """Test positive feedback with high impact."""
        initial = test_agent.confidence_score

        governance_service._update_confidence_score(
            agent_id=test_agent.id,
            positive=True,
            impact_level="high"
        )

        db_session.refresh(test_agent)
        assert test_agent.confidence_score > initial
        assert test_agent.confidence_score <= 1.0

    def test_update_confidence_positive_low_impact(self, governance_service, test_agent, db_session):
        """Test positive feedback with low impact."""
        test_agent.confidence_score = 0.5
        db_session.commit()

        initial = test_agent.confidence_score

        governance_service._update_confidence_score(
            agent_id=test_agent.id,
            positive=True,
            impact_level="low"
        )

        db_session.refresh(test_agent)
        assert test_agent.confidence_score > initial
        assert test_agent.confidence_score <= 1.0

    def test_update_confidence_negative_high_impact(self, governance_service, test_agent, db_session):
        """Test negative feedback with high impact."""
        test_agent.confidence_score = 0.8
        db_session.commit()

        initial = test_agent.confidence_score

        governance_service._update_confidence_score(
            agent_id=test_agent.id,
            positive=False,
            impact_level="high"
        )

        db_session.refresh(test_agent)
        assert test_agent.confidence_score < initial
        assert test_agent.confidence_score >= 0.0

    def test_update_confidence_negative_low_impact(self, governance_service, test_agent, db_session):
        """Test negative feedback with low impact."""
        test_agent.confidence_score = 0.8
        db_session.commit()

        initial = test_agent.confidence_score

        governance_service._update_confidence_score(
            agent_id=test_agent.id,
            positive=False,
            impact_level="low"
        )

        db_session.refresh(test_agent)
        assert test_agent.confidence_score < initial
        assert test_agent.confidence_score >= 0.0

    def test_update_confidence_clamps_to_one(self, governance_service, test_agent, db_session):
        """Test confidence score clamps to maximum 1.0."""
        test_agent.confidence_score = 0.99
        db_session.commit()

        governance_service._update_confidence_score(
            agent_id=test_agent.id,
            positive=True,
            impact_level="high"
        )

        db_session.refresh(test_agent)
        assert test_agent.confidence_score == 1.0

    def test_update_confidence_clamps_to_zero(self, governance_service, test_agent, db_session):
        """Test confidence score clamps to minimum 0.0."""
        test_agent.confidence_score = 0.01
        db_session.commit()

        governance_service._update_confidence_score(
            agent_id=test_agent.id,
            positive=False,
            impact_level="high"
        )

        db_session.refresh(test_agent)
        assert test_agent.confidence_score == 0.0

    def test_update_confidence_maturity_transition_student_to_intern(self, governance_service, test_agent, db_session):
        """Test confidence increase triggers maturity upgrade."""
        test_agent.status = AgentStatus.STUDENT.value
        test_agent.confidence_score = 0.49
        db_session.commit()

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            mock_cache_inst = Mock()
            mock_cache.return_value = mock_cache_inst

            governance_service._update_confidence_score(
                agent_id=test_agent.id,
                positive=True,
                impact_level="high"
            )

            db_session.refresh(test_agent)
            assert test_agent.status == AgentStatus.INTERN.value
            mock_cache_inst.invalidate.assert_called_once_with(test_agent.id)

    def test_update_confidence_maturity_transition_intern_to_supervised(self, governance_service, test_agent, db_session):
        """Test confidence increase triggers upgrade to SUPERVISED."""
        test_agent.status = AgentStatus.INTERN.value
        test_agent.confidence_score = 0.69
        db_session.commit()

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            mock_cache_inst = Mock()
            mock_cache.return_value = mock_cache_inst

            governance_service._update_confidence_score(
                agent_id=test_agent.id,
                positive=True,
                impact_level="high"
            )

            db_session.refresh(test_agent)
            assert test_agent.status == AgentStatus.SUPERVISED.value

    def test_update_confidence_maturity_transition_supervised_to_autonomous(self, governance_service, test_agent, db_session):
        """Test confidence increase triggers upgrade to AUTONOMOUS."""
        test_agent.status = AgentStatus.SUPERVISED.value
        test_agent.confidence_score = 0.89
        db_session.commit()

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            mock_cache_inst = Mock()
            mock_cache.return_value = mock_cache_inst

            governance_service._update_confidence_score(
                agent_id=test_agent.id,
                positive=True,
                impact_level="high"
            )

            db_session.refresh(test_agent)
            assert test_agent.status == AgentStatus.AUTONOMOUS.value

    def test_update_confidence_maturity_demotion_autonomous_to_supervised(self, governance_service, test_agent, db_session):
        """Test confidence decrease triggers demotion."""
        test_agent.status = AgentStatus.AUTONOMOUS.value
        test_agent.confidence_score = 0.91
        db_session.commit()

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            mock_cache_inst = Mock()
            mock_cache.return_value = mock_cache_inst

            governance_service._update_confidence_score(
                agent_id=test_agent.id,
                positive=False,
                impact_level="high"
            )

            db_session.refresh(test_agent)
            assert test_agent.status == AgentStatus.SUPERVISED.value

    def test_update_confidence_nonexistent_agent(self, governance_service):
        """Test confidence update for nonexistent agent doesn't crash."""
        # Should not raise exception
        governance_service._update_confidence_score(
            agent_id="nonexistent-agent",
            positive=True,
            impact_level="high"
        )

    def test_update_confidence_no_transition_same_status(self, governance_service, test_agent, db_session):
        """Test confidence update within same status doesn't trigger cache invalidation."""
        test_agent.status = AgentStatus.INTERN.value
        test_agent.confidence_score = 0.55
        db_session.commit()

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            mock_cache_inst = Mock()
            mock_cache.return_value = mock_cache_inst

            governance_service._update_confidence_score(
                agent_id=test_agent.id,
                positive=True,
                impact_level="low"
            )

            # Status unchanged, cache should not be invalidated
            mock_cache_inst.invalidate.assert_not_called()

    # ==========================================================================
    # Outcome Recording
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_record_outcome_success(self, governance_service, test_agent, db_session):
        """Test recording successful outcome."""
        initial = test_agent.confidence_score

        await governance_service.record_outcome(
            agent_id=test_agent.id,
            success=True
        )

        db_session.refresh(test_agent)
        assert test_agent.confidence_score >= initial

    @pytest.mark.asyncio
    async def test_record_outcome_failure(self, governance_service, test_agent, db_session):
        """Test recording failure outcome."""
        test_agent.confidence_score = 0.8
        db_session.commit()

        initial = test_agent.confidence_score

        await governance_service.record_outcome(
            agent_id=test_agent.id,
            success=False
        )

        db_session.refresh(test_agent)
        assert test_agent.confidence_score <= initial

    # ==========================================================================
    # Policy Discovery
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_find_relevant_policies_with_domain(self, governance_service):
        """Test policy search with domain filter."""
        with patch('core.agent_governance_service.PGPolicySearchService') as mock_search:
            mock_svc = Mock()
            mock_svc.search = AsyncMock(return_value=[
                {"id": "policy-1", "content": "Finance policy"}
            ])
            mock_search.return_value = mock_svc

            results = await governance_service.find_relevant_policies(
                context="Expense approval",
                domain="finance",
                limit=5
            )

            assert len(results) == 1
            mock_svc.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_relevant_policies_without_domain(self, governance_service):
        """Test policy search without domain filter."""
        with patch('core.agent_governance_service.PGPolicySearchService') as mock_search:
            mock_svc = Mock()
            mock_svc.search = AsyncMock(return_value=[])
            mock_search.return_value = mock_svc

            results = await governance_service.find_relevant_policies(
                context="General question"
            )

            assert results == []
            mock_svc.search.assert_called_once_with(
                query="General question",
                domain=None,
                limit=5
            )

    @pytest.mark.asyncio
    async def test_find_relevant_policies_custom_limit(self, governance_service):
        """Test policy search with custom limit."""
        with patch('core.agent_governance_service.PGPolicySearchService') as mock_search:
            mock_svc = Mock()
            mock_svc.search = AsyncMock(return_value=[])
            mock_search.return_value = mock_svc

            await governance_service.find_relevant_policies(
                context="Query",
                limit=10
            )

            mock_svc.search.assert_called_once_with(
                query="Query",
                domain=None,
                limit=10
            )
