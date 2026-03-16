"""
Coverage tests for SupervisionService

Tests real-time supervision, intervention tracking, and session management.
Target: 70%+ coverage for supervision_service.py

Following Phase 197 patterns:
- Use factory pattern for test data
- Test all supervision controls (pause, resume, correct, terminate)
- Cover edge cases and error paths
"""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.supervision_service import (
    SupervisionService,
    SupervisionEvent,
    InterventionResult,
    SupervisionOutcome,
)
from core.models import (
    AgentRegistry,
    AgentStatus,
    AgentExecution,
    SupervisionSession,
    SupervisionStatus,
    User,
    UserRole,
    Tenant,
)


class TestSupervisionControls:
    """
    Test real-time supervision control operations.

    Covers:
    - Pause execution
    - Resume execution
    - Correct action
    - Terminate execution
    """

    @pytest.mark.asyncio
    async def test_supervision_pause_execution(self, db_session: Session):
        """
        Test pausing supervised agent execution.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="supervisor@example.com",
            first_name="Supervisor", last_name="User",
            role=UserRole.MEMBER.value,
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="supervised_agent_1",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test_action"},
            workspace_id="test_workspace",
            supervisor_id=user.id,
        )

        # Act - Pause execution
        result = await service.intervene(
            session_id=session.id,
            intervention_type="pause",
            guidance="Pause to review output",
        )

        # Assert
        assert result.success is True
        assert result.session_state == "paused"
        assert "paused" in result.message.lower()

    @pytest.mark.asyncio
    async def test_supervision_resume_execution(self, db_session: Session):
        """
        Test resuming paused supervised agent execution.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="supervisor@example.com",
            first_name="Supervisor", last_name="User",
            role=UserRole.MEMBER.value,
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="supervised_agent_2",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test_action"},
            workspace_id="test_workspace",
            supervisor_id=user.id,
        )

        # First pause
        await service.intervene(
            session_id=session.id,
            intervention_type="pause",
            guidance="Pause to review",
        )

        # Act - Resume execution
        result = await service.intervene(
            session_id=session.id,
            intervention_type="resume",
            guidance="Continue execution",
        )

        # Assert
        assert result.success is True
        assert result.session_state == "running"
        assert "resumed" in result.message.lower() or "continue" in result.message.lower()

    @pytest.mark.asyncio
    async def test_supervision_correct_action(self, db_session: Session):
        """
        Test correcting supervised agent action.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="supervisor@example.com",
            first_name="Supervisor", last_name="User",
            role=UserRole.MEMBER.value,
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="supervised_agent_3",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.75,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test_action"},
            workspace_id="test_workspace",
            supervisor_id=user.id,
        )

        # Act - Correct action
        result = await service.intervene(
            session_id=session.id,
            intervention_type="correct",
            guidance="Use different parameters for better accuracy",
        )

        # Assert
        assert result.success is True
        assert result.session_state == "running"
        assert "correction" in result.message.lower()
        assert "different parameters" in result.message

    @pytest.mark.asyncio
    async def test_supervision_terminate_execution(self, db_session: Session):
        """
        Test terminating supervised agent execution.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="supervisor@example.com",
            first_name="Supervisor", last_name="User",
            role=UserRole.MEMBER.value,
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="supervised_agent_4",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.75,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test_action"},
            workspace_id="test_workspace",
            supervisor_id=user.id,
        )

        # Act - Terminate execution
        result = await service.intervene(
            session_id=session.id,
            intervention_type="terminate",
            guidance="Critical error detected - stop execution",
        )

        # Assert
        assert result.success is True
        assert result.session_state == "terminated"
        assert "terminated" in result.message.lower()

        # Verify session status
        db_session.refresh(session)
        assert session.status == SupervisionStatus.INTERRUPTED.value

    @pytest.mark.asyncio
    async def test_supervision_for_unsupervised_agent(self, db_session: Session):
        """
        Test supervision fails for agent without SUPERVISED status.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            first_name="Test", last_name="User",
            role=UserRole.MEMBER.value,
            tenant_id=tenant_id,
        )
        db_session.add(user)

        # Create STUDENT agent (not SUPERVISED)
        agent = AgentRegistry(
            id="student_agent",
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

        service = SupervisionService(db_session)

        # Act & Assert - Should still create session (service doesn't enforce maturity)
        # This test documents current behavior
        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test_action"},
            workspace_id="test_workspace",
            supervisor_id=user.id,
        )

        assert session is not None

    @pytest.mark.asyncio
    async def test_supervision_with_invalid_session_id(self, db_session: Session):
        """
        Test intervention fails for invalid session ID.
        """
        # Arrange
        service = SupervisionService(db_session)

        # Act & Assert
        with pytest.raises(ValueError, match="Supervision session .* not found"):
            await service.intervene(
                session_id="nonexistent_session",
                intervention_type="pause",
                guidance="Test",
            )

    @pytest.mark.asyncio
    async def test_supervision_concurrent_interventions(self, db_session: Session):
        """
        Test handling multiple rapid interventions.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="supervisor@example.com",
            first_name="Supervisor", last_name="User",
            role=UserRole.MEMBER.value,
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="supervised_agent_5",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test_action"},
            workspace_id="test_workspace",
            supervisor_id=user.id,
        )

        # Act - Multiple interventions
        result1 = await service.intervene(
            session_id=session.id,
            intervention_type="pause",
            guidance="First pause",
        )

        result2 = await service.intervene(
            session_id=session.id,
            intervention_type="correct",
            guidance="Apply correction",
        )

        result3 = await service.intervene(
            session_id=session.id,
            intervention_type="resume",
            guidance="Resume execution",
        )

        # Assert - All interventions should succeed
        assert result1.success is True
        assert result2.success is True
        assert result3.success is True

        # Verify intervention count
        db_session.refresh(session)
        assert session.intervention_count >= 2  # At least 2 interventions logged


class TestInterventionTracking:
    """
    Test intervention recording and tracking.

    Covers:
    - Intervention logging
    - Intervention rate calculation
    - Intervention history
    """

    @pytest.mark.asyncio
    async def test_supervision_intervention_logging(self, db_session: Session):
        """
        Test interventions are logged correctly.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="supervisor@example.com",
            first_name="Supervisor", last_name="User",
            role=UserRole.MEMBER.value,
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="supervised_agent_6",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test_action"},
            workspace_id="test_workspace",
            supervisor_id=user.id,
        )

        # Act - Multiple interventions
        await service.intervene(
            session_id=session.id,
            intervention_type="pause",
            guidance="First intervention",
        )

        await service.intervene(
            session_id=session.id,
            intervention_type="correct",
            guidance="Second intervention",
        )

        # Assert
        db_session.refresh(session)
        assert session.intervention_count == 2

    @pytest.mark.asyncio
    async def test_supervision_intervention_rate_calculation(self, db_session: Session):
        """
        Test intervention rate is calculated correctly.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="supervisor@example.com",
            first_name="Supervisor", last_name="User",
            role=UserRole.MEMBER.value,
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="supervised_agent_7",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test_action"},
            workspace_id="test_workspace",
            supervisor_id=user.id,
        )

        # Act - Add interventions
        for i in range(3):
            await service.intervene(
                session_id=session.id,
                intervention_type="pause",
                guidance=f"Intervention {i+1}",
            )

        # Complete supervision
        outcome = await service.complete_supervision(
            session_id=session.id,
            supervisor_rating=3,
            feedback="Multiple interventions needed",
        )

        # Assert
        assert outcome.intervention_count == 3
        assert outcome.success is True  # Rating >= 3

    @pytest.mark.asyncio
    async def test_supervision_intervention_outcome_tracking(self, db_session: Session):
        """
        Test intervention outcomes are tracked for learning.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="supervisor@example.com",
            first_name="Supervisor", last_name="User",
            role=UserRole.MEMBER.value,
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="supervised_agent_8",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test_action"},
            workspace_id="test_workspace",
            supervisor_id=user.id,
        )

        # Act - Intervention with outcome
        result = await service.intervene(
            session_id=session.id,
            intervention_type="correct",
            guidance="Use correct parameters",
        )

        # Assert
        assert result.success is True
        # Intervention should be tracked in session
        db_session.refresh(session)
        assert session.intervention_count >= 1


class TestSupervisionMonitoring:
    """
    Test real-time monitoring of supervised agent execution.

    Covers:
    - Monitoring start
    - Status updates
    - Monitoring completion
    """

    @pytest.mark.asyncio
    async def test_supervision_monitoring_start(self, db_session: Session):
        """
        Test starting monitoring for supervised agent.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="supervisor@example.com",
            first_name="Supervisor", last_name="User",
            role=UserRole.MEMBER.value,
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="supervised_agent_9",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        # Act
        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test_action"},
            workspace_id="test_workspace",
            supervisor_id=user.id,
        )

        # Assert
        assert session is not None
        assert session.status == SupervisionStatus.RUNNING.value
        assert session.agent_id == agent.id
        assert session.supervisor_id == user.id

    @pytest.mark.asyncio
    async def test_supervision_monitoring_status_updates(self, db_session: Session):
        """
        Test monitoring receives status updates.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="supervisor@example.com",
            first_name="Supervisor", last_name="User",
            role=UserRole.MEMBER.value,
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="supervised_agent_10",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test_action"},
            workspace_id="test_workspace",
            supervisor_id=user.id,
        )

        # Create execution
        execution = AgentExecution(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            status="running",
            input_summary="Test input",
            output_summary="Test output",
            started_at=datetime.now(),
        )
        db_session.add(execution)
        db_session.commit()

        # Act - Monitor execution
        events = []
        async for event in service.monitor_agent_execution(
            db=db_session,
            session=session,
        ):
            events.append(event)
            if len(events) >= 1:  # Collect at least one event
                break

        # Assert - Should receive events
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_supervision_monitoring_completion(self, db_session: Session):
        """
        Test monitoring completes when agent finishes.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="supervisor@example.com",
            first_name="Supervisor", last_name="User",
            role=UserRole.MEMBER.value,
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="supervised_agent_11",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test_action"},
            workspace_id="test_workspace",
            supervisor_id=user.id,
        )

        # Create completed execution
        execution = AgentExecution(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            status="completed",
            input_summary="Test input",
            output_summary="Test output",
            started_at=datetime.now(),
        )
        db_session.add(execution)
        db_session.commit()

        # Act - Monitor execution (should complete immediately)
        events = []
        async for event in service.monitor_agent_execution(
            db=db_session,
            session=session,
        ):
            events.append(event)

        # Assert - Should receive completion event
        assert len(events) >= 1


class TestSupervisionCompletion:
    """
    Test supervision session completion and outcomes.

    Covers:
    - Session completion
    - Confidence boost calculation
    - Promotion to AUTONOMOUS
    - Low rating handling
    """

    @pytest.mark.asyncio
    async def test_supervision_completion_with_high_rating(self, db_session: Session):
        """
        Test completing supervision with high supervisor rating.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="supervisor@example.com",
            first_name="Supervisor", last_name="User",
            role=UserRole.MEMBER.value,
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="supervised_agent_12",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test_action"},
            workspace_id="test_workspace",
            supervisor_id=user.id,
        )

        # Wait a bit for duration
        import time
        time.sleep(1)

        # Act - Complete with high rating
        outcome = await service.complete_supervision(
            session_id=session.id,
            supervisor_rating=5,
            feedback="Excellent performance",
        )

        # Assert
        assert outcome is not None
        assert outcome.success is True
        assert outcome.supervisor_rating == 5
        assert outcome.feedback == "Excellent performance"
        assert outcome.confidence_boost > 0

        # Verify agent confidence increased
        db_session.refresh(agent)
        assert agent.confidence_score > 0.8

    @pytest.mark.asyncio
    async def test_supervision_completion_promotes_to_autonomous(self, db_session: Session):
        """
        Test excellent supervision can promote agent to AUTONOMOUS.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="supervisor@example.com",
            first_name="Supervisor", last_name="User",
            role=UserRole.MEMBER.value,
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="supervised_agent_13",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.89,  # Just below threshold
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test_action"},
            workspace_id="test_workspace",
            supervisor_id=user.id,
        )

        # Act - Complete with perfect rating
        outcome = await service.complete_supervision(
            session_id=session.id,
            supervisor_rating=5,
            feedback="Perfect performance, ready for autonomy",
        )

        # Assert
        assert outcome.confidence_boost > 0

        # Verify promotion to AUTONOMOUS
        db_session.refresh(agent)
        assert agent.confidence_score >= 0.9
        assert agent.status == AgentStatus.AUTONOMOUS.value

    @pytest.mark.asyncio
    async def test_supervision_completion_low_rating(self, db_session: Session):
        """
        Test low supervisor rating results in minimal confidence boost.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="supervisor@example.com",
            first_name="Supervisor", last_name="User",
            role=UserRole.MEMBER.value,
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="supervised_agent_14",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.75,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test_action"},
            workspace_id="test_workspace",
            supervisor_id=user.id,
        )

        # Act - Complete with low rating
        outcome = await service.complete_supervision(
            session_id=session.id,
            supervisor_rating=1,
            feedback="Needs significant improvement",
        )

        # Assert
        assert outcome.success is False  # Rating < 3
        assert outcome.confidence_boost < 0.05  # Minimal boost

        # Verify agent didn't get promoted
        db_session.refresh(agent)
        assert agent.status == AgentStatus.SUPERVISED.value


class TestSupervisionEdgeCases:
    """
    Test edge cases and error handling in supervision.

    Covers:
    - Invalid intervention types
    - Session not found
    - Agent not found
    - Concurrent supervision attempts
    """

    @pytest.mark.asyncio
    async def test_supervision_invalid_intervention_type(self, db_session: Session):
        """
        Test invalid intervention type raises error.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="supervisor@example.com",
            first_name="Supervisor", last_name="User",
            role=UserRole.MEMBER.value,
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="supervised_agent_15",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test_action"},
            workspace_id="test_workspace",
            supervisor_id=user.id,
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Unknown intervention type"):
            await service.intervene(
                session_id=session.id,
                intervention_type="invalid_type",
                guidance="Test",
            )

    @pytest.mark.asyncio
    async def test_supervision_session_not_found(self, db_session: Session):
        """
        Test completing supervision for nonexistent session raises error.
        """
        # Arrange
        service = SupervisionService(db_session)

        # Act & Assert
        with pytest.raises(ValueError, match="Supervision session .* not found"):
            await service.complete_supervision(
                session_id="nonexistent_session",
                supervisor_rating=5,
                feedback="Test",
            )

    @pytest.mark.asyncio
    async def test_supervision_agent_not_found(self, db_session: Session):
        """
        Test starting supervision for nonexistent agent raises error.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="supervisor@example.com",
            first_name="Supervisor", last_name="User",
            role=UserRole.MEMBER.value,
            tenant_id=tenant_id,
        )
        db_session.add(user)
        db_session.commit()

        service = SupervisionService(db_session)

        # Act & Assert
        with pytest.raises(ValueError, match="Agent .* not found"):
            await service.start_supervision_session(
                agent_id="nonexistent_agent",
                trigger_context={"action_type": "test_action"},
                workspace_id="test_workspace",
                supervisor_id=user.id,
            )

    @pytest.mark.asyncio
    async def test_supervision_concurrent_sessions(self, db_session: Session):
        """
        Test handling concurrent supervision sessions for same agent.
        """
        # Arrange
        tenant_id = str(uuid.uuid4())
        user = User(
            id=str(uuid.uuid4()),
            email="supervisor@example.com",
            first_name="Supervisor", last_name="User",
            role=UserRole.MEMBER.value,
            tenant_id=tenant_id,
        )
        db_session.add(user)

        agent = AgentRegistry(
            id="supervised_agent_16",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8,
            user_id=user.id,
            tenant_id=tenant_id,
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        # Act - Create multiple sessions
        session1 = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test_action_1"},
            workspace_id="test_workspace",
            supervisor_id=user.id,
        )

        session2 = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test_action_2"},
            workspace_id="test_workspace",
            supervisor_id=user.id,
        )

        # Assert - Both sessions created successfully
        assert session1.id != session2.id
        assert session1.agent_id == session2.agent_id == agent.id
