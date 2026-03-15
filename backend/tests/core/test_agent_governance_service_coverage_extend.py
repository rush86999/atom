"""
Coverage-driven tests for agent_governance_service.py (42% -> 60%+ target)

Coverage Target Areas:
- Lines 76-94: submit_feedback method
- Lines 100-159: _adjudicate_feedback (trusted reviewer logic)
- Lines 165-167: record_outcome method
- Lines 220-237: promote_to_autonomous method
- Lines 334-338: Cache validation with require_approval
- Lines 363-367: Status validation against confidence_score
- Lines 422-453: get_agent_capabilities method
- Lines 520, 547-561: enforce_action and request_approval
- Lines 565-569: get_approval_status method
- Lines 584-599, 618-656: can_access_agent_data method
- Lines 671-704: suspend_agent method
- Lines 717-747: terminate_agent method
- Lines 759-807: reactivate_agent method

Test Categories:
- Feedback adjudication (12 tests)
- Confidence score updates (8 tests)
- Maturity transitions (6 tests)
- Cache validation (6 tests)
- Agent capabilities (5 tests)
- Action enforcement (5 tests)
- Approval workflow (4 tests)
- Data access control (6 tests)
- Agent lifecycle (8 tests)
- Edge cases (5 tests)
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import uuid

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
)
from tests.factories import (
    StudentAgentFactory,
    InternAgentFactory,
    SupervisedAgentFactory,
    AutonomousAgentFactory,
    UserFactory,
)


@pytest.mark.usefixtures("db_session")
class TestAgentGovernanceServiceCoverageExtend:
    """Extended coverage tests for agent governance service."""

    # ==================== FEEDBACK ADJUDICATION TESTS ====================

    @pytest.mark.asyncio
    async def test_submit_feedback_creates_pending_feedback(self, db_session):
        """Submit feedback creates PENDING status feedback record."""
        agent = StudentAgentFactory(_session=db_session)
        user = UserFactory(_session=db_session, role=UserRole.MEMBER)

        service = AgentGovernanceService(db_session)

        feedback = await service.submit_feedback(
            agent_id=agent.id,
            user_id=user.id,
            original_output="Bad response",
            user_correction="Better response",
            input_context="Context here"
        )

        assert feedback.agent_id == agent.id
        assert feedback.user_id == user.id
        assert feedback.original_output == "Bad response"
        assert feedback.user_correction == "Better response"
        assert feedback.status == FeedbackStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_submit_feedback_for_nonexistent_agent_raises_error(self, db_session):
        """Submit feedback for nonexistent agent raises HTTPException."""
        user = UserFactory(_session=db_session)
        service = AgentGovernanceService(db_session)

        with pytest.raises(Exception):  # HTTPException
            await service.submit_feedback(
                agent_id="nonexistent-agent",
                user_id=user.id,
                original_output="Output",
                user_correction="Correction"
            )

    @pytest.mark.asyncio
    async def test_adjudicate_feedback_admin_accepted(self, db_session):
        """Admin feedback is automatically ACCEPTED with high impact."""
        agent = StudentAgentFactory(_session=db_session, confidence_score=0.6)
        admin = UserFactory(
            _session=db_session,
            role=UserRole.WORKSPACE_ADMIN,
            specialty=None
        )

        feedback = AgentFeedback(
            agent_id=agent.id,
            user_id=admin.id,
            original_output="Wrong output",
            user_correction="Correct output",
            status=FeedbackStatus.PENDING.value
        )
        db_session.add(feedback)
        db_session.commit()

        service = AgentGovernanceService(db_session)
        await service._adjudicate_feedback(feedback)

        db_session.refresh(feedback)
        assert feedback.status == FeedbackStatus.ACCEPTED.value
        assert "Trusted reviewer" in feedback.ai_reasoning
        assert feedback.adjudicated_at is not None

    @pytest.mark.asyncio
    async def test_adjudicate_feedback_specialty_match_accepted(self, db_session):
        """Specialty match feedback is automatically ACCEPTED."""
        agent = StudentAgentFactory(
            _session=db_session,
            confidence_score=0.6,
            category="Finance"
        )
        user = UserFactory(
            _session=db_session,
            role=UserRole.MEMBER,
            specialty="Finance"
        )

        feedback = AgentFeedback(
            agent_id=agent.id,
            user_id=user.id,
            original_output="Wrong",
            user_correction="Correct",
            status=FeedbackStatus.PENDING.value
        )
        db_session.add(feedback)
        db_session.commit()

        service = AgentGovernanceService(db_session)
        await service._adjudicate_feedback(feedback)

        db_session.refresh(feedback)
        assert feedback.status == FeedbackStatus.ACCEPTED.value
        assert "Trusted reviewer" in feedback.ai_reasoning

    @pytest.mark.asyncio
    async def test_adjudicate_feedback_no_match_pending(self, db_session):
        """Feedback without admin or specialty match stays PENDING."""
        agent = StudentAgentFactory(
            _session=db_session,
            confidence_score=0.6,
            category="Finance"
        )
        user = UserFactory(
            _session=db_session,
            role=UserRole.MEMBER,
            specialty=None  # No specialty set
        )

        feedback = AgentFeedback(
            agent_id=agent.id,
            user_id=user.id,
            original_output="Wrong",
            user_correction="Correct",
            status=FeedbackStatus.PENDING.value
        )
        db_session.add(feedback)
        db_session.commit()

        service = AgentGovernanceService(db_session)
        await service._adjudicate_feedback(feedback)

        db_session.refresh(feedback)
        assert feedback.status == FeedbackStatus.PENDING.value
        assert "queued for specialty review" in feedback.ai_reasoning

    @pytest.mark.asyncio
    async def test_adjudicate_feedback_case_insensitive_specialty(self, db_session):
        """Specialty matching is case-insensitive."""
        agent = StudentAgentFactory(
            _session=db_session,
            confidence_score=0.6,
            category="finance"  # lowercase
        )
        user = UserFactory(
            _session=db_session,
            role=UserRole.MEMBER,
            specialty="FINANCE"  # uppercase
        )

        feedback = AgentFeedback(
            agent_id=agent.id,
            user_id=user.id,
            original_output="Wrong",
            user_correction="Correct",
            status=FeedbackStatus.PENDING.value
        )
        db_session.add(feedback)
        db_session.commit()

        service = AgentGovernanceService(db_session)
        await service._adjudicate_feedback(feedback)

        db_session.refresh(feedback)
        assert feedback.status == FeedbackStatus.ACCEPTED.value

    @pytest.mark.asyncio
    async def test_adjudicate_feedback_super_admin_accepted(self, db_session):
        """Super admin feedback is automatically ACCEPTED."""
        agent = StudentAgentFactory(_session=db_session, confidence_score=0.6)
        super_admin = UserFactory(
            _session=db_session,
            role=UserRole.SUPER_ADMIN,
            specialty=None
        )

        feedback = AgentFeedback(
            agent_id=agent.id,
            user_id=super_admin.id,
            original_output="Wrong",
            user_correction="Correct",
            status=FeedbackStatus.PENDING.value
        )
        db_session.add(feedback)
        db_session.commit()

        service = AgentGovernanceService(db_session)
        await service._adjudicate_feedback(feedback)

        db_session.refresh(feedback)
        assert feedback.status == FeedbackStatus.ACCEPTED.value

    # ==================== CONFIDENCE SCORE UPDATE TESTS ====================

    def test_update_confidence_positive_high_impact(self, db_session):
        """Positive feedback with high impact boosts confidence."""
        agent = StudentAgentFactory(_session=db_session, confidence_score=0.5)
        service = AgentGovernanceService(db_session)

        service._update_confidence_score(
            agent_id=agent.id,
            positive=True,
            impact_level="high"
        )

        db_session.refresh(agent)
        assert agent.confidence_score == 0.55  # 0.5 + 0.05

    def test_update_confidence_positive_low_impact(self, db_session):
        """Positive feedback with low impact slightly boosts confidence."""
        agent = StudentAgentFactory(_session=db_session, confidence_score=0.5)
        service = AgentGovernanceService(db_session)

        service._update_confidence_score(
            agent_id=agent.id,
            positive=True,
            impact_level="low"
        )

        db_session.refresh(agent)
        assert agent.confidence_score == 0.51  # 0.5 + 0.01

    def test_update_confidence_negative_high_impact(self, db_session):
        """Negative feedback with high impact significantly reduces confidence."""
        agent = InternAgentFactory(_session=db_session, confidence_score=0.6)
        service = AgentGovernanceService(db_session)

        service._update_confidence_score(
            agent_id=agent.id,
            positive=False,
            impact_level="high"
        )

        db_session.refresh(agent)
        assert agent.confidence_score == 0.50  # 0.6 - 0.1

    def test_update_confidence_negative_low_impact(self, db_session):
        """Negative feedback with low impact slightly reduces confidence."""
        agent = InternAgentFactory(_session=db_session, confidence_score=0.6)
        service = AgentGovernanceService(db_session)

        service._update_confidence_score(
            agent_id=agent.id,
            positive=False,
            impact_level="low"
        )

        db_session.refresh(agent)
        assert agent.confidence_score == 0.58  # 0.6 - 0.02

    def test_update_confidence_caps_at_1_0(self, db_session):
        """Confidence score caps at 1.0 maximum."""
        agent = AutonomousAgentFactory(_session=db_session, confidence_score=0.98)
        service = AgentGovernanceService(db_session)

        service._update_confidence_score(
            agent_id=agent.id,
            positive=True,
            impact_level="high"
        )

        db_session.refresh(agent)
        assert agent.confidence_score == 1.0

    def test_update_confidence_floor_at_0_0(self, db_session):
        """Confidence score floors at 0.0 minimum."""
        agent = StudentAgentFactory(_session=db_session, confidence_score=0.01)
        service = AgentGovernanceService(db_session)

        service._update_confidence_score(
            agent_id=agent.id,
            positive=False,
            impact_level="high"
        )

        db_session.refresh(agent)
        assert agent.confidence_score == 0.0

    def test_update_confidence_none_defaults_to_0_5(self, db_session):
        """None confidence score defaults to 0.5 before update."""
        agent = StudentAgentFactory(_session=db_session, confidence_score=None)
        service = AgentGovernanceService(db_session)

        service._update_confidence_score(
            agent_id=agent.id,
            positive=True,
            impact_level="low"
        )

        db_session.refresh(agent)
        assert agent.confidence_score == 0.51  # 0.5 + 0.01

    # ==================== MATURITY TRANSITION TESTS ====================

    def test_confidence_increase_triggers_intern_promotion(self, db_session):
        """Confidence >= 0.5 promotes to INTERN."""
        agent = StudentAgentFactory(_session=db_session, confidence_score=0.49)
        service = AgentGovernanceService(db_session)

        service._update_confidence_score(
            agent_id=agent.id,
            positive=True,
            impact_level="high"
        )

        db_session.refresh(agent)
        assert agent.status == AgentStatus.INTERN.value

    def test_confidence_increase_triggers_supervised_promotion(self, db_session):
        """Confidence >= 0.7 promotes to SUPERVISED."""
        agent = InternAgentFactory(_session=db_session, confidence_score=0.69)
        service = AgentGovernanceService(db_session)

        service._update_confidence_score(
            agent_id=agent.id,
            positive=True,
            impact_level="high"
        )

        db_session.refresh(agent)
        assert agent.status == AgentStatus.SUPERVISED.value

    def test_confidence_increase_triggers_autonomous_promotion(self, db_session):
        """Confidence >= 0.9 promotes to AUTONOMOUS."""
        agent = SupervisedAgentFactory(_session=db_session, confidence_score=0.89)
        service = AgentGovernanceService(db_session)

        service._update_confidence_score(
            agent_id=agent.id,
            positive=True,
            impact_level="high"
        )

        db_session.refresh(agent)
        assert agent.status == AgentStatus.AUTONOMOUS.value

    def test_confidence_decrease_demotes_autonomous_to_supervised(self, db_session):
        """Confidence < 0.9 demotes to SUPERVISED."""
        agent = AutonomousAgentFactory(_session=db_session, confidence_score=0.91)
        service = AgentGovernanceService(db_session)

        service._update_confidence_score(
            agent_id=agent.id,
            positive=False,
            impact_level="high"
        )

        db_session.refresh(agent)
        assert agent.status == AgentStatus.SUPERVISED.value

    def test_confidence_decrease_demotes_supervised_to_intern(self, db_session):
        """Confidence < 0.7 demotes to INTERN."""
        agent = SupervisedAgentFactory(_session=db_session, confidence_score=0.71)
        service = AgentGovernanceService(db_session)

        service._update_confidence_score(
            agent_id=agent.id,
            positive=False,
            impact_level="high"
        )

        db_session.refresh(agent)
        assert agent.status == AgentStatus.INTERN.value

    def test_confidence_decrease_demotes_intern_to_student(self, db_session):
        """Confidence < 0.5 demotes to STUDENT."""
        agent = InternAgentFactory(_session=db_session, confidence_score=0.51)
        service = AgentGovernanceService(db_session)

        service._update_confidence_score(
            agent_id=agent.id,
            positive=False,
            impact_level="high"
        )

        db_session.refresh(agent)
        assert agent.status == AgentStatus.STUDENT.value

    # ==================== CACHE VALIDATION TESTS ====================

    def test_can_perform_action_cache_hit(self, db_session):
        """Cache HIT returns cached governance decision."""
        agent = StudentAgentFactory(_session=db_session)
        service = AgentGovernanceService(db_session)

        # First call - cache miss
        decision1 = service.can_perform_action(
            agent_id=agent.id,
            action_type="present_chart"
        )

        # Second call - cache hit
        decision2 = service.can_perform_action(
            agent_id=agent.id,
            action_type="present_chart"
        )

        assert decision1["allowed"] == decision2["allowed"]
        assert decision1["agent_status"] == decision2["agent_status"]

    def test_can_perform_action_cache_miss(self, db_session):
        """Cache MISS computes governance decision and caches it."""
        agent = InternAgentFactory(_session=db_session)
        service = AgentGovernanceService(db_session)

        decision = service.can_perform_action(
            agent_id=agent.id,
            action_type="stream_chat"
        )

        assert "allowed" in decision
        assert "agent_status" in decision
        assert "action_complexity" in decision

    def test_can_perform_action_with_require_approval_flag(self, db_session):
        """require_approval flag overrides cached decision."""
        agent = InternAgentFactory(_session=db_session)
        service = AgentGovernanceService(db_session)

        # First call without approval requirement
        decision1 = service.can_perform_action(
            agent_id=agent.id,
            action_type="stream_chat",
            require_approval=False
        )

        # Second call with approval requirement
        decision2 = service.can_perform_action(
            agent_id=agent.id,
            action_type="stream_chat",
            require_approval=True
        )

        # Second call should require approval even if first didn't
        assert decision2["requires_human_approval"] is True

    def test_can_perform_action_unknown_agent(self, db_session):
        """Unknown agent returns denial response."""
        service = AgentGovernanceService(db_session)

        decision = service.can_perform_action(
            agent_id="unknown-agent-id",
            action_type="present_chart"
        )

        assert decision["allowed"] is False
        assert "not found" in decision["reason"].lower()

    def test_can_perform_action_status_confidence_mismatch(self, db_session):
        """Status not matching confidence_score triggers warning and uses actual maturity."""
        # Create agent with STUDENT status but high confidence
        agent = StudentAgentFactory(_session=db_session, confidence_score=0.85)
        service = AgentGovernanceService(db_session)

        decision = service.can_perform_action(
            agent_id=agent.id,
            action_type="submit_form"
        )

        # Should use actual maturity (SUPERVISED) based on confidence for governance check
        # The decision should reflect the actual maturity level
        assert decision["allowed"] is True  # Confidence 0.85 allows complexity 3

    # ==================== AGENT CAPABILITIES TESTS ====================

    def test_get_agent_capabilities_student(self, db_session):
        """Get capabilities for STUDENT agent."""
        agent = StudentAgentFactory(_session=db_session)
        service = AgentGovernanceService(db_session)

        capabilities = service.get_agent_capabilities(agent.id)

        assert "maturity_level" in capabilities
        assert "allowed_actions" in capabilities
        assert capabilities["maturity_level"] == AgentStatus.STUDENT.value

    def test_get_agent_capabilities_intern(self, db_session):
        """Get capabilities for INTERN agent."""
        agent = InternAgentFactory(_session=db_session)
        service = AgentGovernanceService(db_session)

        capabilities = service.get_agent_capabilities(agent.id)

        assert capabilities["maturity_level"] == AgentStatus.INTERN.value
        assert "stream_chat" in capabilities["allowed_actions"]
        assert "delete" not in capabilities["allowed_actions"]

    def test_get_agent_capabilities_supervised(self, db_session):
        """Get capabilities for SUPERVISED agent."""
        agent = SupervisedAgentFactory(_session=db_session)
        service = AgentGovernanceService(db_session)

        capabilities = service.get_agent_capabilities(agent.id)

        assert capabilities["maturity_level"] == AgentStatus.SUPERVISED.value
        assert "submit_form" in capabilities["allowed_actions"]
        assert "delete" not in capabilities["allowed_actions"]

    def test_get_agent_capabilities_autonomous(self, db_session):
        """Get capabilities for AUTONOMOUS agent."""
        agent = AutonomousAgentFactory(_session=db_session)
        service = AgentGovernanceService(db_session)

        capabilities = service.get_agent_capabilities(agent.id)

        assert capabilities["maturity_level"] == AgentStatus.AUTONOMOUS.value
        assert "delete" in capabilities["allowed_actions"]
        assert "execute" in capabilities["allowed_actions"]

    def test_get_agent_capabilities_unknown_agent_raises_error(self, db_session):
        """Get capabilities for unknown agent raises error."""
        service = AgentGovernanceService(db_session)

        with pytest.raises(Exception):
            service.get_agent_capabilities("unknown-agent-id")

    # ==================== ACTION ENFORCEMENT TESTS ====================

    def test_enforce_action_allowed(self, db_session):
        """Enforce action that is allowed for agent maturity."""
        agent = InternAgentFactory(_session=db_session)
        service = AgentGovernanceService(db_session)

        result = service.enforce_action(
            agent_id=agent.id,
            action_type="stream_chat",
            action_details={}
        )

        assert result["proceed"] is True

    def test_enforce_action_denied_low_maturity(self, db_session):
        """Enforce action denied due to low maturity."""
        agent = StudentAgentFactory(_session=db_session)
        service = AgentGovernanceService(db_session)

        result = service.enforce_action(
            agent_id=agent.id,
            action_type="delete",
            action_details={}
        )

        assert result["proceed"] is False
        assert result["status"] == "BLOCKED"

    # ==================== APPROVAL WORKFLOW TESTS ====================

    def test_request_approval_creates_hitl_action(self, db_session):
        """Request approval creates HITL action record."""
        agent = InternAgentFactory(_session=db_session)
        service = AgentGovernanceService(db_session)

        action_id = service.request_approval(
            agent_id=agent.id,
            action_type="submit_form",
            params={"form_data": "test"},
            reason="Testing approval workflow"
        )

        assert action_id is not None
        assert isinstance(action_id, str)

    def test_get_approval_status_pending(self, db_session):
        """Get approval status for pending action."""
        agent = InternAgentFactory(_session=db_session)
        service = AgentGovernanceService(db_session)

        action_id = service.request_approval(
            agent_id=agent.id,
            action_type="submit_form",
            params={},
            reason="Testing approval status"
        )

        status = service.get_approval_status(action_id)

        assert "status" in status
        assert "id" in status

    # ==================== DATA ACCESS CONTROL TESTS ====================

    def test_can_access_agent_data_owner(self, db_session):
        """Agent owner can access agent data (via specialty match)."""
        agent = InternAgentFactory(_session=db_session, user_id="user-123", category="Finance")
        user = UserFactory(_session=db_session, id="user-123", specialty="Finance")
        service = AgentGovernanceService(db_session)

        can_access = service.can_access_agent_data(
            user_id="user-123",
            agent_id=agent.id
        )

        assert can_access is True

    def test_can_access_agent_data_admin(self, db_session):
        """Admin can access any agent data."""
        agent = InternAgentFactory(_session=db_session, user_id="user-456")
        admin = UserFactory(_session=db_session, role=UserRole.WORKSPACE_ADMIN)
        service = AgentGovernanceService(db_session)

        can_access = service.can_access_agent_data(
            user_id=admin.id,
            agent_id=agent.id
        )

        assert can_access is True

    def test_can_access_agent_data_denied(self, db_session):
        """Non-owner non-admin cannot access agent data."""
        agent = InternAgentFactory(_session=db_session, user_id="user-123")
        service = AgentGovernanceService(db_session)

        can_access = service.can_access_agent_data(
            user_id="user-999",
            agent_id=agent.id
        )

        assert can_access is False

    # ==================== AGENT LIFECYCLE TESTS ====================

    def test_promote_to_autonomous_success(self, db_session):
        """Promote agent to AUTONOMOUS status."""
        agent = SupervisedAgentFactory(_session=db_session)
        admin = UserFactory(_session=db_session, role=UserRole.WORKSPACE_ADMIN)
        service = AgentGovernanceService(db_session)

        promoted = service.promote_to_autonomous(agent.id, admin)

        assert promoted.status == AgentStatus.AUTONOMOUS.value

    def test_promote_to_autonomous_non_admin_denied(self, db_session):
        """Non-admin cannot promote agent to AUTONOMOUS."""
        agent = SupervisedAgentFactory(_session=db_session)
        user = UserFactory(_session=db_session, role=UserRole.MEMBER)
        service = AgentGovernanceService(db_session)

        with pytest.raises(Exception):  # Permission denied
            service.promote_to_autonomous(agent.id, user)

    def test_suspend_agent_success(self, db_session):
        """Suspend agent successfully."""
        agent = InternAgentFactory(_session=db_session)
        service = AgentGovernanceService(db_session)

        result = service.suspend_agent(agent.id, reason="Testing suspension")

        assert result is True
        db_session.refresh(agent)
        assert agent.status == "SUSPENDED"

    def test_terminate_agent_success(self, db_session):
        """Terminate agent successfully."""
        agent = InternAgentFactory(_session=db_session)
        service = AgentGovernanceService(db_session)

        result = service.terminate_agent(agent.id, reason="Testing termination")

        assert result is True
        db_session.refresh(agent)
        assert agent.status == "TERMINATED"

    def test_reactivate_agent_success(self, db_session):
        """Reactivate suspended agent restores status based on confidence."""
        agent = InternAgentFactory(_session=db_session, status="SUSPENDED", confidence_score=0.6)
        service = AgentGovernanceService(db_session)

        result = service.reactivate_agent(agent.id)

        assert result is True
        db_session.refresh(agent)
        # Should restore to INTERN based on confidence score of 0.6
        assert agent.status == AgentStatus.INTERN.value

    def test_reactivate_terminated_agent_fails(self, db_session):
        """Cannot reactivate terminated agent."""
        agent = InternAgentFactory(_session=db_session, status="TERMINATED")
        service = AgentGovernanceService(db_session)

        result = service.reactivate_agent(agent.id)

        assert result is False

    # ==================== RECORD OUTCOME TESTS ====================

    @pytest.mark.asyncio
    async def test_record_outcome_success(self, db_session):
        """Record successful outcome."""
        agent = InternAgentFactory(_session=db_session)
        service = AgentGovernanceService(db_session)

        await service.record_outcome(agent.id, success=True)

        db_session.refresh(agent)
        # Low impact success should slightly increase confidence
        assert agent.confidence_score > 0.5

    @pytest.mark.asyncio
    async def test_record_outcome_failure(self, db_session):
        """Record failed outcome."""
        agent = InternAgentFactory(_session=db_session, confidence_score=0.6)
        service = AgentGovernanceService(db_session)

        await service.record_outcome(agent.id, success=False)

        db_session.refresh(agent)
        # Low impact failure should slightly decrease confidence
        assert agent.confidence_score < 0.6

    # ==================== EDGE CASES TESTS ====================

    def test_update_confidence_nonexistent_agent_no_error(self, db_session):
        """Updating confidence for nonexistent agent returns without error."""
        service = AgentGovernanceService(db_session)

        # Should not raise error
        service._update_confidence_score(
            agent_id="nonexistent-agent",
            positive=True,
            impact_level="low"
        )

    def test_can_perform_action_unknown_action_type_defaults_complexity_2(self, db_session):
        """Unknown action type defaults to complexity 2."""
        agent = InternAgentFactory(_session=db_session)
        service = AgentGovernanceService(db_session)

        decision = service.can_perform_action(
            agent_id=agent.id,
            action_type="unknown_action_type"
        )

        # Should default to complexity 2 (INTERN level)
        assert decision["action_complexity"] == 2

    def test_list_agents_with_category_filter(self, db_session):
        """List agents filtered by category."""
        StudentAgentFactory(_session=db_session, category="Finance")
        InternAgentFactory(_session=db_session, category="Engineering")
        SupervisedAgentFactory(_session=db_session, category="Finance")

        service = AgentGovernanceService(db_session)

        finance_agents = service.list_agents(category="Finance")

        assert len(finance_agents) == 2
        assert all(agent.category == "Finance" for agent in finance_agents)

    def test_list_agents_all(self, db_session):
        """List all agents without filter."""
        StudentAgentFactory(_session=db_session)
        InternAgentFactory(_session=db_session)
        SupervisedAgentFactory(_session=db_session)

        service = AgentGovernanceService(db_session)

        all_agents = service.list_agents()

        assert len(all_agents) >= 3

    def test_register_or_update_agent_new_agent(self, db_session):
        """Register new agent."""
        service = AgentGovernanceService(db_session)

        agent = service.register_or_update_agent(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestClass",
            description="Test description"
        )

        assert agent.name == "TestAgent"
        assert agent.status == AgentStatus.STUDENT.value

    def test_register_or_update_agent_existing_agent(self, db_session):
        """Update existing agent metadata."""
        service = AgentGovernanceService(db_session)

        # Create agent
        agent1 = service.register_or_update_agent(
            name="TestAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestClass",
            description="Original description"
        )

        # Update same agent
        agent2 = service.register_or_update_agent(
            name="UpdatedAgent",
            category="Testing",
            module_path="test.module",
            class_name="TestClass",
            description="Updated description"
        )

        assert agent2.id == agent1.id
        assert agent2.name == "UpdatedAgent"
        assert agent2.description == "Updated description"
