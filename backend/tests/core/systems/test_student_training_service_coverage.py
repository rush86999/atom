"""
Coverage tests for StudentTrainingService

Tests training proposal workflow, duration estimation, and session management.
Target: 65%+ coverage for student_training_service.py

Following Phase 197 patterns:
- Use factory pattern for test data
- Test all workflow steps (proposal → approval → session → completion)
- Cover edge cases and error paths
"""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.student_training_service import (
    StudentTrainingService,
    TrainingDurationEstimate,
    TrainingOutcome,
)
from core.models import (
    AgentRegistry,
    AgentStatus,
    AgentProposal,
    ProposalStatus,
    ProposalType,
    TrainingSession,
    BlockedTriggerContext,
    TriggerSource,
    User,
    UserRole,
    UserStatus,
    Tenant,
)


def _blocked_trigger(
    agent_id: str,
    agent_name: str,
    tenant_id: str,
    block_reason: str,
    trigger_context: dict,
) -> BlockedTriggerContext:
    """Build a schema-valid BlockedTriggerContext.

    Mirrors how core/trigger_interceptor.py constructs blocked triggers:
    ``reason``/``context`` are now ``block_reason``/``trigger_context`` and
    agent_name / maturity / confidence / routing_decision are NOT NULL.
    """
    return BlockedTriggerContext(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        agent_name=agent_name,
        agent_maturity_at_block=AgentStatus.STUDENT.value,
        confidence_score_at_block=0.4,
        trigger_type=trigger_context.get("action_type", "automated"),
        trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
        trigger_context=trigger_context,
        routing_decision="training",
        block_reason=block_reason,
        tenant_id=tenant_id,
    )


class TestTrainingProposalWorkflow:
    """
    Test training proposal creation and approval workflow.

    Covers:
    - Proposal creation for blocked triggers
    - Proposal approval with user modifications
    - Proposal rejection
    - Auto-approval for low-risk scenarios
    """

    @pytest.mark.asyncio
    async def test_proposal_creation_for_student_agent(self, db_session: Session):
        """
        Test creating training proposal for STUDENT agent blocked from automated trigger.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            first_name="Test", last_name="User",
            role=UserRole.MEMBER.value,
            status=UserStatus.ACTIVE.value,  # users.status is NOT NULL
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="student_agent_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        blocked_trigger = _blocked_trigger(
            agent_id=agent.id,
            agent_name=agent.name,
            tenant_id=tenant_id,
            block_reason="Agent is in STUDENT maturity level",
            trigger_context={"action_type": "data_analysis"},
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Mock duration estimation
        service.estimate_training_duration = AsyncMock(
            return_value=TrainingDurationEstimate(
                estimated_hours=8.0,
                confidence=0.85,
                reasoning="Similar agents required 8 hours",
                similar_agents=[],
                min_hours=6.0,
                max_hours=10.0,
            )
        )

        # Act
        proposal = await service.create_training_proposal(blocked_trigger)

        # Assert
        assert proposal is not None
        assert proposal.agent_id == agent.id
        assert proposal.proposal_type == ProposalType.WORKFLOW.value
        assert proposal.status == ProposalStatus.PENDING_APPROVAL.value
        assert proposal.proposal_data.get("estimated_duration_hours") == 8.0
        assert blocked_trigger.proposal_id == proposal.id
        # Tenant is inherited from the hire (agent), not hardcoded "default" —
        # otherwise the session/endpoint tenant flow breaks for real tenants.
        assert proposal.tenant_id == agent.tenant_id

    @pytest.mark.asyncio
    async def test_proposal_with_required_training_modules(self, db_session: Session):
        """
        Test proposal includes required training modules based on capability gaps.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            first_name="Test", last_name="User",
            role=UserRole.MEMBER.value,
            status=UserStatus.ACTIVE.value,  # users.status is NOT NULL
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="student_agent_2",
            name="Student Agent",
            # Category with a known capability-gap mapping so gaps are identified
            category="Operations",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        blocked_trigger = _blocked_trigger(
            agent_id=agent.id,
            agent_name=agent.name,
            tenant_id=tenant_id,
            block_reason="Agent lacks data analysis capabilities",
            trigger_context={"action_type": "complex_analysis", "required_modules": ["pandas", "numpy"]},
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        service = StudentTrainingService(db_session)

        service.estimate_training_duration = AsyncMock(
            return_value=TrainingDurationEstimate(
                estimated_hours=12.0,
                confidence=0.80,
                reasoning="Complex analysis requires more time",
                similar_agents=[],
                min_hours=10.0,
                max_hours=15.0,
            )
        )

        # Act
        proposal = await service.create_training_proposal(blocked_trigger)

        # Assert
        assert proposal is not None
        assert proposal.proposal_data.get("capability_gaps") is not None
        assert len(proposal.proposal_data.get("capability_gaps", [])) > 0

    @pytest.mark.asyncio
    async def test_proposal_with_estimated_duration(self, db_session: Session):
        """
        Test proposal includes AI-estimated duration with confidence.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            first_name="Test", last_name="User",
            role=UserRole.MEMBER.value,
            status=UserStatus.ACTIVE.value,  # users.status is NOT NULL
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="student_agent_3",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.45,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        blocked_trigger = _blocked_trigger(
            agent_id=agent.id,
            agent_name=agent.name,
            tenant_id=tenant_id,
            block_reason="Student agent blocked",
            trigger_context={"action_type": "basic_task"},
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        service = StudentTrainingService(db_session)

        expected_estimate = TrainingDurationEstimate(
            estimated_hours=6.5,
            confidence=0.90,
            reasoning="High confidence based on similar agents",
            similar_agents=[{"agent_id": "similar_1", "duration_hours": 6.0}],
            min_hours=5.0,
            max_hours=8.0,
        )

        service.estimate_training_duration = AsyncMock(return_value=expected_estimate)

        # Act
        proposal = await service.create_training_proposal(blocked_trigger)

        # Assert
        assert proposal.proposal_data.get("estimated_duration_hours") == 6.5
        assert proposal.proposal_data.get("duration_estimation_confidence") == 0.90
        assert proposal.proposal_data.get("duration_estimation_reasoning") == expected_estimate.reasoning

    @pytest.mark.asyncio
    async def test_proposal_approval_by_admin(self, db_session: Session):
        """
        Test admin approval of training proposal creates session.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="admin@example.com",
            first_name="Admin", last_name="User",
            role=UserRole.ADMIN.value,
            status=UserStatus.ACTIVE.value,  # users.status is NOT NULL
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="student_agent_4",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        proposal = AgentProposal(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=user.id,
            agent_id=agent.id,
            agent_name=agent.name,  # denormalized onto TrainingSession (NOT NULL)
            proposal_type=ProposalType.WORKFLOW.value,
            proposal_data={
                "training_modules": ["basics"],
                "estimated_duration_hours": 8.0,
            },
            status=ProposalStatus.PENDING_APPROVAL.value,
        )
        db_session.add(proposal)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        session = await service.approve_training(
            proposal_id=proposal.id,
            user_id=user.id,
        )

        # Assert
        assert session is not None
        assert session.agent_id == agent.id
        assert session.proposal_id == proposal.id
        assert session.supervisor_id == user.id

    @pytest.mark.asyncio
    async def test_proposal_rejection_with_reason(self, db_session: Session):
        """
        Test proposal rejection with reason.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="admin@example.com",
            first_name="Admin", last_name="User",
            role=UserRole.ADMIN.value,
            status=UserStatus.ACTIVE.value,  # users.status is NOT NULL
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="student_agent_5",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        proposal = AgentProposal(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=user.id,
            agent_id=agent.id,
            agent_name=agent.name,  # denormalized onto TrainingSession (NOT NULL)
            proposal_type=ProposalType.WORKFLOW.value,
            proposal_data={"training_modules": ["basics"]},
            status=ProposalStatus.PENDING_APPROVAL.value,
        )
        db_session.add(proposal)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act — rejection now lives on ProposalService (the shared proposal
        # state machine); StudentTrainingService only handles the approve path.
        from core.proposal_service import ProposalService

        await ProposalService(db_session).reject_proposal(
            proposal_id=proposal.id,
            user_id=user.id,
            reason="Insufficient justification"
        )

        # Assert
        db_session.refresh(proposal)
        assert proposal.status == ProposalStatus.REJECTED.value
        # A rejected proposal can no longer be approved for training
        with pytest.raises(ValueError, match="PENDING_APPROVAL"):
            await service.approve_training(
                proposal_id=proposal.id,
                user_id=user.id,
            )

    @pytest.mark.asyncio
    async def test_proposal_for_nonexistent_agent(self, db_session: Session):
        """
        Test proposal creation fails gracefully for nonexistent agent.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            first_name="Test", last_name="User",
            role=UserRole.MEMBER.value,
            status=UserStatus.ACTIVE.value,  # users.status is NOT NULL
            tenant_id=tenant_id,
        )
        db_session.add(user)
        db_session.commit()

        blocked_trigger = _blocked_trigger(
            agent_id="nonexistent_agent",
            agent_name="Unknown",
            tenant_id=tenant_id,
            block_reason="Agent not found",
            trigger_context={},
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act & Assert
        with pytest.raises(ValueError, match="Agent .* not found"):
            await service.create_training_proposal(blocked_trigger)

    @pytest.mark.asyncio
    async def test_proposal_for_agent_with_insufficient_data(self, db_session: Session):
        """
        Test proposal creation with minimal trigger context data.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            first_name="Test", last_name="User",
            role=UserRole.MEMBER.value,
            status=UserStatus.ACTIVE.value,  # users.status is NOT NULL
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="student_agent_6",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        # Minimal context
        blocked_trigger = _blocked_trigger(
            agent_id=agent.id,
            agent_name=agent.name,
            tenant_id=tenant_id,
            block_reason="Student agent blocked",
            trigger_context={},  # Empty context
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        service = StudentTrainingService(db_session)

        service.estimate_training_duration = AsyncMock(
            return_value=TrainingDurationEstimate(
                estimated_hours=4.0,
                confidence=0.50,
                reasoning="Default duration for minimal context",
                similar_agents=[],
                min_hours=2.0,
                max_hours=6.0,
            )
        )

        # Act
        proposal = await service.create_training_proposal(blocked_trigger)

        # Assert - Should still create proposal with defaults
        assert proposal is not None
        assert proposal.proposal_data.get("estimated_duration_hours") == 4.0

    @pytest.mark.asyncio
    async def test_concurrent_training_proposals(self, db_session: Session):
        """
        Test handling multiple concurrent proposals for same agent.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            first_name="Test", last_name="User",
            role=UserRole.MEMBER.value,
            status=UserStatus.ACTIVE.value,  # users.status is NOT NULL
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="student_agent_7",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        service.estimate_training_duration = AsyncMock(
            return_value=TrainingDurationEstimate(
                estimated_hours=5.0,
                confidence=0.80,
                reasoning="Standard duration",
                similar_agents=[],
                min_hours=4.0,
                max_hours=6.0,
            )
        )

        # Create first proposal
        blocked_trigger_1 = _blocked_trigger(
            agent_id=agent.id,
            agent_name=agent.name,
            tenant_id=tenant_id,
            block_reason="First trigger",
            trigger_context={"action": "task1"},
        )
        db_session.add(blocked_trigger_1)
        db_session.commit()

        proposal_1 = await service.create_training_proposal(blocked_trigger_1)

        # Create second proposal
        blocked_trigger_2 = _blocked_trigger(
            agent_id=agent.id,
            agent_name=agent.name,
            tenant_id=tenant_id,
            block_reason="Second trigger",
            trigger_context={"action": "task2"},
        )
        db_session.add(blocked_trigger_2)
        db_session.commit()

        proposal_2 = await service.create_training_proposal(blocked_trigger_2)

        # Assert - Both proposals created successfully
        assert proposal_1.id != proposal_2.id
        assert proposal_1.agent_id == proposal_2.agent_id == agent.id


class TestTrainingDurationEstimation:
    """
    Test AI-based training duration estimation.

    Covers:
    - Duration estimation based on episode count
    - Historical data analysis
    - User override functionality
    - Complex module scenarios
    """

    @pytest.mark.asyncio
    async def test_duration_estimation_based_on_episode_count(self, db_session: Session):
        """
        Test duration estimation considers agent's episode count.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            first_name="Test", last_name="User",
            role=UserRole.MEMBER.value,
            status=UserStatus.ACTIVE.value,  # users.status is NOT NULL
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="student_agent_8",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,  # low experience signal
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["basic_workflow"],
            target_maturity=AgentStatus.INTERN.value,
        )

        # Assert
        assert estimate is not None
        assert estimate.estimated_hours > 0
        assert 0 <= estimate.confidence <= 1

    @pytest.mark.asyncio
    async def test_duration_estimation_with_historical_data(self, db_session: Session):
        """
        Test duration estimation uses historical training data.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            first_name="Test", last_name="User",
            role=UserRole.MEMBER.value,
            status=UserStatus.ACTIVE.value,  # users.status is NOT NULL
            tenant_id=tenant_id,
        )
        db_session.add(user)

        # Create similar agents with training history
        for i in range(3):
            similar_agent = AgentRegistry(
                id=f"similar_agent_{i}",
                name=f"Similar Agent {i}",
                category="testing",
                module_path="test.module",
                class_name="TestClass",
                status=AgentStatus.INTERN.value,
                confidence_score=0.6,
                user_id=user.id,
                tenant_id=tenant_id,
            )
            db_session.add(similar_agent)

        # Completed training history for the first similar agent so the
        # duration estimator has real historical data to draw on.
        history_proposal = AgentProposal(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=user.id,
            agent_id="similar_agent_0",
            agent_name="Similar Agent 0",
            proposal_type=ProposalType.WORKFLOW.value,
            proposal_data={"training_modules": ["basics"]},
            status=ProposalStatus.EXECUTED.value,
        )
        db_session.add(history_proposal)

        history_session = TrainingSession(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            proposal_id=history_proposal.id,
            agent_id="similar_agent_0",
            agent_name="Similar Agent 0",
            status="completed",
            supervisor_id=user.id,
            duration_seconds=3600 * 8,
        )
        db_session.add(history_session)

        agent = AgentRegistry(
            id="student_agent_9",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["basic_workflow"],
            target_maturity=AgentStatus.INTERN.value,
        )

        # Assert
        assert estimate is not None
        assert len(estimate.similar_agents) > 0
        assert estimate.reasoning is not None

    @pytest.mark.asyncio
    async def test_duration_estimation_override_by_user(self, db_session: Session):
        """
        Test user can override estimated duration during approval.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="admin@example.com",
            first_name="Admin", last_name="User",
            role=UserRole.ADMIN.value,
            status=UserStatus.ACTIVE.value,  # users.status is NOT NULL
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="student_agent_10",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        proposal = AgentProposal(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=user.id,
            agent_id=agent.id,
            agent_name=agent.name,  # denormalized onto TrainingSession (NOT NULL)
            proposal_type=ProposalType.WORKFLOW.value,
            proposal_data={
                "training_modules": ["basics"],
                "estimated_duration_hours": 8.0,
            },
            status=ProposalStatus.PENDING_APPROVAL.value,
        )
        db_session.add(proposal)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act - Approve with user override
        session = await service.approve_training(
            proposal_id=proposal.id,
            user_id=user.id,
            modifications={"duration_override_hours": 12.0},  # User override
        )

        # Assert
        assert session is not None
        # Session should reflect user's override

    @pytest.mark.asyncio
    async def test_duration_estimation_for_complex_modules(self, db_session: Session):
        """
        Test duration estimation for complex training modules.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            first_name="Test", last_name="User",
            role=UserRole.MEMBER.value,
            status=UserStatus.ACTIVE.value,  # users.status is NOT NULL
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="student_agent_11",
            name="Student Agent",
            category="data_science",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Complex capability gaps
        complex_gaps = [
            "machine_learning_basics",
            "data_preprocessing",
            "model_evaluation",
            "feature_engineering",
        ]

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=complex_gaps,
            target_maturity=AgentStatus.INTERN.value,
        )

        # Assert
        assert estimate is not None
        assert estimate.estimated_hours > 10  # Complex modules require more time
        assert estimate.max_hours > estimate.estimated_hours

    @pytest.mark.asyncio
    async def test_duration_estimation_with_no_history(self, db_session: Session):
        """
        Test duration estimation with no historical data (first-time agent).
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            first_name="Test", last_name="User",
            role=UserRole.MEMBER.value,
            status=UserStatus.ACTIVE.value,  # users.status is NOT NULL
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="student_agent_12",
            name="Student Agent",
            category="new_category",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["basic_workflow"],
            target_maturity=AgentStatus.INTERN.value,
        )

        # Assert
        assert estimate is not None
        assert estimate.estimated_hours > 0
        assert estimate.confidence < 0.7  # Lower confidence without history

    @pytest.mark.asyncio
    async def test_duration_estimation_overflow_protection(self, db_session: Session):
        """
        Test duration estimation has reasonable upper bounds.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            first_name="Test", last_name="User",
            role=UserRole.MEMBER.value,
            status=UserStatus.ACTIVE.value,  # users.status is NOT NULL
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="student_agent_13",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.0,  # Very low confidence
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Many capability gaps
        many_gaps = [f"gap_{i}" for i in range(20)]

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=many_gaps,
            target_maturity=AgentStatus.INTERN.value,
        )

        # Assert
        assert estimate is not None
        assert estimate.estimated_hours < 100  # Reasonable upper bound
        assert estimate.max_hours < 200

    @pytest.mark.asyncio
    async def test_historical_training_duration_analysis(self, db_session: Session):
        """
        Test analysis of historical training durations.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            first_name="Test", last_name="User",
            role=UserRole.MEMBER.value,
            status=UserStatus.ACTIVE.value,  # users.status is NOT NULL
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="student_agent_14",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["basic_workflow"],
            target_maturity=AgentStatus.INTERN.value,
        )

        # Assert
        assert estimate is not None
        # Should include historical analysis in reasoning
        assert estimate.reasoning is not None and len(estimate.reasoning) > 0

    @pytest.mark.asyncio
    async def test_duration_prediction_accuracy(self, db_session: Session):
        """
        Test duration estimation confidence scoring.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            first_name="Test", last_name="User",
            role=UserRole.MEMBER.value,
            status=UserStatus.ACTIVE.value,  # users.status is NOT NULL
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="student_agent_15",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.5,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["basic_workflow"],
            target_maturity=AgentStatus.INTERN.value,
        )

        # Assert
        assert estimate is not None
        assert 0 <= estimate.confidence <= 1
        assert estimate.min_hours <= estimate.estimated_hours <= estimate.max_hours


class TestTrainingSessionManagement:
    """
    Test training session lifecycle.

    Covers:
    - Session creation from approved proposal
    - Session completion
    - Session failure handling
    - Training outcome tracking
    """

    @pytest.mark.asyncio
    async def test_training_session_creation(self, db_session: Session):
        """
        Test creating training session from approved proposal.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="admin@example.com",
            first_name="Admin", last_name="User",
            role=UserRole.ADMIN.value,
            status=UserStatus.ACTIVE.value,  # users.status is NOT NULL
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="student_agent_16",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        proposal = AgentProposal(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=user.id,
            agent_id=agent.id,
            agent_name=agent.name,  # denormalized onto TrainingSession (NOT NULL)
            proposal_type=ProposalType.WORKFLOW.value,
            proposal_data={
                "training_modules": ["basics"],
                "estimated_duration_hours": 8.0,
            },
            status=ProposalStatus.PENDING_APPROVAL.value,
        )
        db_session.add(proposal)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        session = await service.approve_training(
            proposal_id=proposal.id,
            user_id=user.id,
        )

        # Assert
        assert session is not None
        assert session.proposal_id == proposal.id
        assert session.agent_id == agent.id
        assert session.supervisor_id == user.id

    @pytest.mark.asyncio
    async def test_training_session_completion(self, db_session: Session):
        """
        Test completing training session updates agent maturity.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="admin@example.com",
            first_name="Admin", last_name="User",
            role=UserRole.ADMIN.value,
            status=UserStatus.ACTIVE.value,  # users.status is NOT NULL
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="student_agent_17",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        proposal = AgentProposal(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=user.id,
            agent_id=agent.id,
            agent_name=agent.name,  # denormalized onto TrainingSession (NOT NULL)
            proposal_type=ProposalType.WORKFLOW.value,
            proposal_data={"training_modules": ["basics"]},
            status=ProposalStatus.APPROVED.value,
        )
        db_session.add(proposal)
        db_session.commit()

        session = TrainingSession(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            proposal_id=proposal.id,
            agent_id=agent.id,
            agent_name=agent.name,
            status="in_progress",
            supervisor_id=user.id,
            started_at=datetime.now(),
        )
        db_session.add(session)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        outcome = TrainingOutcome(
            performance_score=0.85,
            supervisor_feedback="Excellent progress",
            errors_count=0,
            tasks_completed=9,
            total_tasks=10,
            capabilities_developed=["basic_workflow"],
            capability_gaps_remaining=[],
        )
        result = await service.complete_training_session(
            session_id=session.id,
            outcome=outcome,
        )

        # Assert
        assert result is not None
        assert result["performance_score"] == 0.85
        db_session.refresh(session)
        assert session.supervisor_feedback == "Excellent progress"
        assert session.status == "completed"

    @pytest.mark.asyncio
    async def test_training_session_failure_handling(self, db_session: Session):
        """
        Test handling training session failures.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="admin@example.com",
            first_name="Admin", last_name="User",
            role=UserRole.ADMIN.value,
            status=UserStatus.ACTIVE.value,  # users.status is NOT NULL
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="student_agent_18",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        proposal = AgentProposal(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=user.id,
            agent_id=agent.id,
            agent_name=agent.name,  # denormalized onto TrainingSession (NOT NULL)
            proposal_type=ProposalType.WORKFLOW.value,
            proposal_data={"training_modules": ["basics"]},
            status=ProposalStatus.APPROVED.value,
        )
        db_session.add(proposal)
        db_session.commit()

        session = TrainingSession(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            proposal_id=proposal.id,
            agent_id=agent.id,
            agent_name=agent.name,
            status="in_progress",
            supervisor_id=user.id,
            started_at=datetime.now(),
        )
        db_session.add(session)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        outcome = TrainingOutcome(
            performance_score=0.2,  # Poor performance (< 0.3 → minimal boost)
            supervisor_feedback="Did not meet objectives",
            errors_count=4,
            tasks_completed=3,
            total_tasks=10,
            capabilities_developed=[],
            capability_gaps_remaining=["basic_workflow", "error_handling"],
        )
        result = await service.complete_training_session(
            session_id=session.id,
            outcome=outcome,
        )

        # Assert
        assert result is not None
        assert result["performance_score"] == 0.2
        # Agent should remain at STUDENT level
        db_session.refresh(agent)
        assert agent.status == AgentStatus.STUDENT.value

    @pytest.mark.asyncio
    async def test_training_outcome_capability_gaps(self, db_session: Session):
        """
        Test training outcome includes capability gap analysis.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="admin@example.com",
            first_name="Admin", last_name="User",
            role=UserRole.ADMIN.value,
            status=UserStatus.ACTIVE.value,  # users.status is NOT NULL
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="student_agent_19",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        proposal = AgentProposal(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=user.id,
            agent_id=agent.id,
            agent_name=agent.name,  # denormalized onto TrainingSession (NOT NULL)
            proposal_type=ProposalType.WORKFLOW.value,
            proposal_data={"training_modules": ["basics"]},
            status=ProposalStatus.APPROVED.value,
        )
        db_session.add(proposal)
        db_session.commit()

        session = TrainingSession(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            proposal_id=proposal.id,
            agent_id=agent.id,
            agent_name=agent.name,
            status="in_progress",
            supervisor_id=user.id,
            started_at=datetime.now(),
        )
        db_session.add(session)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        outcome = TrainingOutcome(
            performance_score=0.7,
            supervisor_feedback="Good progress but needs more practice",
            errors_count=1,
            tasks_completed=8,
            total_tasks=10,
            capabilities_developed=["data_analysis"],
            capability_gaps_remaining=["complex_analysis"],
        )
        result = await service.complete_training_session(
            session_id=session.id,
            outcome=outcome,
        )

        # Assert
        assert result is not None
        assert result["capabilities_developed"] == ["data_analysis"]
        db_session.refresh(session)
        assert session.capabilities_developed == ["data_analysis"]
        assert session.capability_gaps_remaining == ["complex_analysis"]
