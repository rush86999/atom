"""
Enhanced coverage tests for agent_governance_service.py

Focus on high-impact uncovered paths:
- Error handling in can_perform_action
- Edge cases in enforce_action
- Feedback adjudication logic
- Confidence score updates
- Approval request workflow
- Policy discovery

Target: Increase coverage from 70% to 85%+
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.models import (
    AgentRegistry,
    AgentStatus,
    AgentFeedback,
    FeedbackStatus,
    User,
    UserRole,
    HITLAction,
    HITLActionStatus,
    DelegationChain
)
from core.database import SessionLocal


class TestAgentGovernanceServiceEnhanced:
    """Enhanced coverage for AgentGovernanceService error paths and edge cases."""

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
    def test_agent(self, governance_service, db_session):
        """Create test agent."""
        agent = governance_service.register_or_update_agent(
            name="Test Agent",
            category="Finance",
            module_path="test.finance",
            class_name="FinanceAgent"
        )
        return agent

    # ============================================================================
    # can_perform_action - Error Paths & Edge Cases
    # ============================================================================

    def test_can_perform_action_with_chain_id_recursion_limit(self, governance_service, test_agent, db_session):
        """Test recursion depth limit enforcement with chain_id."""
        # Create delegation chain at max depth
        chain = DelegationChain(
            id="test-chain-123",
            workspace_id="default",
            max_depth=5,
            links=["link1", "link2", "link3", "link4", "link5"],  # Already at max
            metadata_json={}
        )
        db_session.add(chain)
        db_session.commit()

        result = governance_service.can_perform_action(
            agent_id=test_agent.id,
            action_type="read",
            chain_id="test-chain-123"
        )

        assert result["allowed"] == False
        assert result["status_code"] == "RECURSION_LIMIT"
        assert "recursion" in result["reason"].lower()

    def test_can_perform_action_with_chain_id_below_limit(self, governance_service, test_agent, db_session):
        """Test chain_id when below recursion limit."""
        # Create delegation chain below max depth
        chain = DelegationChain(
            id="test-chain-456",
            workspace_id="default",
            max_depth=10,
            links=["link1", "link2"],  # Below max
            metadata_json={}
        )
        db_session.add(chain)
        db_session.commit()

        result = governance_service.can_perform_action(
            agent_id=test_agent.id,
            action_type="read",
            chain_id="test-chain-456"
        )

        # Should allow (agent status permitting)
        assert "allowed" in result

    def test_can_perform_action_unknown_action_complexity(self, governance_service, test_agent):
        """Test action type not in complexity mapping defaults to level 2."""
        result = governance_service.can_perform_action(
            agent_id=test_agent.id,
            action_type="unknown_action_xyz"
        )

        # Unknown actions should default to complexity 2 (INTERN level)
        assert "complexity" in result
        assert result["complexity"] == 2

    def test_can_perform_action_budget_check_skipped_on_error(self, governance_service, test_agent, db_session):
        """Test budget check failure is logged but doesn't block action."""
        # Set agent to AUTONOMOUS to pass maturity check
        test_agent.status = AgentStatus.AUTONOMOUS.value
        db_session.commit()

        # Mock BudgetEnforcementService to raise exception
        with patch('core.agent_governance_service.BudgetEnforcementService') as mock_budget:
            mock_budget.return_value.check_budget_before_action.side_effect = Exception("Budget service unavailable")

            result = governance_service.can_perform_action(
                agent_id=test_agent.id,
                action_type="read"
            )

            # Should still allow action (budget check failure is non-blocking)
            assert result["allowed"] == True

    def test_can_perform_action_budget_exceeded(self, governance_service, test_agent, db_session):
        """Test action blocked when budget exceeded."""
        # Set agent to AUTONOMOUS
        test_agent.status = AgentStatus.AUTONOMOUS.value
        db_session.commit()

        # Mock budget check to return exceeded
        with patch('core.agent_governance_service.BudgetEnforcementService') as mock_budget:
            mock_budget_svc = Mock()
            mock_budget_svc.check_budget_before_action = AsyncMock(return_value={
                "allowed": False,
                "reason": "Budget exceeded"
            })
            mock_budget.return_value = mock_budget_svc

            result = governance_service.can_perform_action(
                agent_id=test_agent.id,
                action_type="read"
            )

            assert result["allowed"] == False
            assert result["status_code"] == "BUDGET_EXCEEDED"
            assert "budget" in result["reason"].lower()

    # ============================================================================
    # enforce_action - Guardrail Paths
    # ============================================================================

    def test_enforce_action_blocked_by_guardrail(self, governance_service, test_agent, db_session):
        """Test autonomous guardrail violation blocks action."""
        # Set agent to AUTONOMOUS (triggers guardrail check)
        test_agent.status = AgentStatus.AUTONOMOUS.value
        db_session.commit()

        # Mock guardrail to detect violation
        with patch('core.agent_governance_service.AutonomousGuardrailService') as mock_gr:
            mock_gr_svc = Mock()
            mock_gr_svc.check_guardrails.return_value = {
                "proceed": False,
                "violation_type": "safety",
                "reason": "Unsafe action detected",
                "requires_downgrade": True
            }
            mock_gr.return_value = mock_gr_svc

            result = governance_service.enforce_action(
                agent_id=test_agent.id,
                action_type="delete",
                action_details={"target": "production"}
            )

            assert result["proceed"] == False
            assert result["status"] == "BLOCKED_BY_GUARDRAIL"
            assert "unsafe" in result["reason"].lower()

    def test_enforce_action_guardrail_pass(self, governance_service, test_agent, db_session):
        """Test action proceeds when guardrails pass."""
        # Set agent to AUTONOMOUS
        test_agent.status = AgentStatus.AUTONOMOUS.value
        db_session.commit()

        # Mock guardrail to allow
        with patch('core.agent_governance_service.AutonomousGuardrailService') as mock_gr:
            mock_gr_svc = Mock()
            mock_gr_svc.check_guardrails.return_value = {
                "proceed": True
            }
            mock_gr.return_value = mock_gr_svc

            result = governance_service.enforce_action(
                agent_id=test_agent.id,
                action_type="read",
                action_details={"target": "logs"}
            )

            assert result["proceed"] == True
            assert result["status"] == "APPROVED"

    def test_enforce_action_supervised_requires_approval(self, governance_service, test_agent, db_session):
        """Test supervised agent with high complexity requires approval."""
        # Set agent to SUPERVISED
        test_agent.status = AgentStatus.SUPERVISED.value
        db_session.commit()

        result = governance_service.enforce_action(
            agent_id=test_agent.id,
            action_type="delete"  # Complexity 4
        )

        assert result["proceed"] == True
        assert result["status"] == "PENDING_APPROVAL"
        assert result["action_required"] == "WAIT_FOR_APPROVAL"

    # ============================================================================
    # Feedback Adjudication
    # ============================================================================

    @pytest.mark.asyncio
    async def test_submit_feedback_admin_accepted(self, governance_service, test_agent, test_user, db_session):
        """Test admin feedback is auto-accepted."""
        feedback = await governance_service.submit_feedback(
            agent_id=test_agent.id,
            user_id=test_user.id,
            original_output="Bad response",
            user_correction="Better response"
        )

        assert feedback.status == FeedbackStatus.ACCEPTED.value
        assert "trusted" in feedback.ai_reasoning.lower()

    @pytest.mark.asyncio
    async def test_submit_feedback_specialty_match_accepted(self, governance_service, test_agent, test_user, db_session):
        """Test feedback from user with matching specialty is accepted."""
        # User specialty matches agent category
        test_user.specialty = "Finance"  # Matches agent.category
        test_user.role = UserRole.MEMBER  # Not admin
        db_session.commit()

        feedback = await governance_service.submit_feedback(
            agent_id=test_agent.id,
            user_id=test_user.id,
            original_output="Okay response",
            user_correction="Improved response"
        )

        assert feedback.status == FeedbackStatus.ACCEPTED.value

    @pytest.mark.asyncio
    async def test_submit_feedback_non_specialist_pending(self, governance_service, test_agent, test_user, db_session):
        """Test feedback from non-specialist user is pending."""
        # User specialty doesn't match
        test_user.specialty = "Engineering"
        test_user.role = UserRole.MEMBER
        db_session.commit()

        feedback = await governance_service.submit_feedback(
            agent_id=test_agent.id,
            user_id=test_user.id,
            original_output="Response",
            user_correction="Correction"
        )

        assert feedback.status == FeedbackStatus.PENDING.value
        assert "specialty" in feedback.ai_reasoning.lower()

    @pytest.mark.asyncio
    async def test_submit_feedback_agent_not_found(self, governance_service, test_user):
        """Test feedback submission fails for non-existent agent."""
        with pytest.raises(Exception):  # handle_not_found raises HTTPException
            await governance_service.submit_feedback(
                agent_id="nonexistent-agent",
                user_id=test_user.id,
                original_output="Output",
                user_correction="Correction"
            )

    @pytest.mark.asyncio
    async def test_adjudicate_feedback_continuous_learning_failure(self, governance_service, test_agent, test_user, db_session):
        """Test continuous learning failure is handled gracefully."""
        test_user.role = UserRole.WORKSPACE_ADMIN

        # Mock continuous learning to raise exception
        with patch.object(governance_service.continuous_learning, 'update_from_feedback', side_effect=Exception("DB error")):
            feedback = await governance_service.submit_feedback(
                agent_id=test_agent.id,
                user_id=test_user.id,
                original_output="Output",
                user_correction="Correction"
            )

            # Feedback should still be accepted despite continuous learning failure
            assert feedback.status == FeedbackStatus.ACCEPTED.value

    # ============================================================================
    # Confidence Score Updates
    # ============================================================================

    def test_update_confidence_score_positive_high_impact(self, governance_service, test_agent, db_session):
        """Test positive feedback with high impact increases confidence."""
        initial_score = test_agent.confidence_score

        governance_service._update_confidence_score(
            agent_id=test_agent.id,
            positive=True,
            impact_level="high"
        )

        db_session.refresh(test_agent)
        assert test_agent.confidence_score > initial_score
        assert test_agent.confidence_score <= 1.0

    def test_update_confidence_score_negative_low_impact(self, governance_service, test_agent, db_session):
        """Test negative feedback with low impact decreases confidence slightly."""
        test_agent.confidence_score = 0.8
        db_session.commit()

        initial_score = test_agent.confidence_score

        governance_service._update_confidence_score(
            agent_id=test_agent.id,
            positive=False,
            impact_level="low"
        )

        db_session.refresh(test_agent)
        assert test_agent.confidence_score < initial_score
        assert test_agent.confidence_score >= 0.0

    def test_update_confidence_score_maturity_transition_up(self, governance_service, test_agent, db_session):
        """Test confidence increase triggers maturity transition."""
        # Set to INTERN with high confidence
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
            mock_cache_inst.invalidate.assert_called_once()

    def test_update_confidence_score_maturity_transition_down(self, governance_service, test_agent, db_session):
        """Test confidence decrease triggers maturity demotion."""
        # Set to SUPERVISED with low confidence
        test_agent.status = AgentStatus.SUPERVISED.value
        test_agent.confidence_score = 0.71
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
            assert test_agent.status == AgentStatus.INTERN.value

    def test_update_confidence_score_nonexistent_agent(self, governance_service):
        """Test confidence update for non-existent agent doesn't crash."""
        # Should not raise exception
        governance_service._update_confidence_score(
            agent_id="nonexistent-agent",
            positive=True,
            impact_level="high"
        )

    # ============================================================================
    # Approval Workflow
    # ============================================================================

    def test_request_approval_basic(self, governance_service, test_agent):
        """Test basic approval request creation."""
        action_id = governance_service.request_approval(
            agent_id=test_agent.id,
            action_type="delete",
            params={"target": "resource"},
            reason="High risk action"
        )

        assert action_id is not None
        assert isinstance(action_id, str)

        # Verify HITL action was created
        hitl = governance_service.db.query(HITLAction).filter(
            HITLAction.id == action_id
        ).first()
        assert hitl is not None
        assert hitl.status == HITLActionStatus.PENDING.value
        assert hitl.agent_id == test_agent.id

    def test_request_approval_with_chain_id(self, governance_service, test_agent, db_session):
        """Test approval request with delegation chain context."""
        # Create delegation chain
        chain = DelegationChain(
            id="test-chain-789",
            workspace_id="default",
            max_depth=5,
            links=["link1"],
            metadata_json={"context": "fleet_operation"}
        )
        db_session.add(chain)
        db_session.commit()

        action_id = governance_service.request_approval(
            agent_id=test_agent.id,
            action_type="execute",
            params={"task": "complex"},
            reason="Requires oversight",
            chain_id="test-chain-789"
        )

        # Verify chain context captured
        hitl = governance_service.db.query(HITLAction).filter(
            HITLAction.id == action_id
        ).first()
        assert hitl.chain_id == "test-chain-789"
        assert hitl.context_snapshot is not None

    def test_get_approval_status_existing(self, governance_service, test_agent):
        """Test get approval status for existing action."""
        # Create approval request
        action_id = governance_service.request_approval(
            agent_id=test_agent.id,
            action_type="delete",
            params={},
            reason="Test"
        )

        status = governance_service.get_approval_status(action_id)

        assert status["status"] == HITLActionStatus.PENDING.value
        assert status["id"] == action_id

    def test_get_approval_status_not_found(self, governance_service):
        """Test get approval status for non-existent action."""
        status = governance_service.get_approval_status("nonexistent-action")

        assert status["status"] == "not_found"

    # ============================================================================
    # Policy Discovery
    # ============================================================================

    @pytest.mark.asyncio
    async def test_find_relevant_policies_basic(self, governance_service):
        """Test policy search with basic query."""
        with patch('core.agent_governance_service.PGPolicySearchService') as mock_search:
            mock_svc = Mock()
            mock_svc.search = AsyncMock(return_value=[
                {"id": "policy-1", "content": "Finance policy"},
                {"id": "policy-2", "content": "Approval policy"}
            ])
            mock_search.return_value = mock_svc

            results = await governance_service.find_relevant_policies(
                context="How to approve expenses?",
                domain="finance",
                limit=5
            )

            assert len(results) == 2
            mock_svc.search.assert_called_once_with(
                query="How to approve expenses?",
                domain="finance",
                limit=5
            )

    @pytest.mark.asyncio
    async def test_find_relevant_policies_no_domain(self, governance_service):
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

    # ============================================================================
    # Outcome Recording
    # ============================================================================

    @pytest.mark.asyncio
    async def test_record_outcome_success(self, governance_service, test_agent, db_session):
        """Test recording successful outcome increases confidence."""
        initial_score = test_agent.confidence_score

        await governance_service.record_outcome(
            agent_id=test_agent.id,
            success=True
        )

        db_session.refresh(test_agent)
        assert test_agent.confidence_score >= initial_score

    @pytest.mark.asyncio
    async def test_record_outcome_failure(self, governance_service, test_agent, db_session):
        """Test recording failure outcome decreases confidence."""
        test_agent.confidence_score = 0.8
        db_session.commit()

        initial_score = test_agent.confidence_score

        await governance_service.record_outcome(
            agent_id=test_agent.id,
            success=False
        )

        db_session.refresh(test_agent)
        assert test_agent.confidence_score <= initial_score
