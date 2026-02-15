"""
Unit tests for TriggerInterceptor

Tests maturity-based routing for STUDENT, INTERN, SUPERVISED, and AUTONOMOUS agents.
Covers routing logic, audit logging, cache integration, and error handling.

Coverage target: 80%+ for trigger_interceptor.py
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from sqlalchemy.orm import Session

from core.trigger_interceptor import (
    TriggerInterceptor,
    MaturityLevel,
    RoutingDecision,
    TriggerDecision,
)
from core.models import (
    AgentRegistry,
    AgentStatus,
    BlockedTriggerContext,
    TriggerSource,
    ProposalStatus,
    SupervisionStatus,
)


class TestTriggerInterceptorRouting:
    """Test maturity-based routing decisions"""

    @pytest.mark.asyncio
    async def test_student_agent_blocked_from_automated_triggers(self, db_session: Session):
        """
        STUDENT agents (<0.5 confidence) should be BLOCKED and routed to training.
        """
        # Arrange
        agent = AgentRegistry(
            id="student_agent_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        interceptor = TriggerInterceptor(db_session, workspace_id="test_workspace")

        # Mock governance cache
        with patch('core.trigger_interceptor.get_async_governance_cache') as mock_cache_getter:
            mock_cache = AsyncMock()
            mock_cache.get = AsyncMock(return_value=None)  # Cache miss
            mock_cache.set = AsyncMock()
            mock_cache_getter.return_value = mock_cache

            # Act
            decision = await interceptor.intercept_trigger(
                agent_id=agent.id,
                trigger_source=TriggerSource.WORKFLOW_ENGINE,
                trigger_context={"action_type": "agent_message", "data": "test"},
                user_id=None
            )

        # Assert
        assert decision.execute is False
        assert decision.routing_decision == RoutingDecision.TRAINING
        assert decision.agent_id == agent.id
        assert "STUDENT agent blocked" in decision.reason
        assert decision.blocked_context is not None
        assert decision.blocked_context.agent_id == agent.id
        assert decision.blocked_context.routing_decision == "training"
        assert decision.proposal is not None  # Training proposal created

    @pytest.mark.asyncio
    async def test_intern_agent_generates_proposal(self, db_session: Session):
        """
        INTERN agents (0.5-0.7 confidence) should generate proposals for approval.
        """
        # Arrange
        agent = AgentRegistry(
            id="intern_agent_1",
            name="Intern Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db_session.add(agent)
        db_session.commit()

        interceptor = TriggerInterceptor(db_session, workspace_id="test_workspace")

        # Mock governance cache
        with patch('core.trigger_interceptor.get_async_governance_cache') as mock_cache_getter:
            mock_cache = AsyncMock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()
            mock_cache_getter.return_value = mock_cache

            # Act
            decision = await interceptor.intercept_trigger(
                agent_id=agent.id,
                trigger_source=TriggerSource.DATA_SYNC,
                trigger_context={"action_type": "workflow_trigger", "data": "test"},
                user_id=None
            )

        # Assert
        assert decision.execute is False
        assert decision.routing_decision == RoutingDecision.PROPOSAL
        assert decision.agent_id == agent.id
        assert "INTERN agent must generate proposal" in decision.reason
        assert decision.blocked_context is not None
        assert decision.blocked_context.routing_decision == "proposal"

    @pytest.mark.asyncio
    async def test_supervised_agent_executes_with_supervision(self, db_session: Session):
        """
        SUPERVISED agents (0.7-0.9 confidence) should execute with real-time monitoring.
        """
        # Arrange
        agent = AgentRegistry(
            id="supervised_agent_1",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8,
            user_id="test_user_1",
        )
        db_session.add(agent)
        db_session.commit()

        interceptor = TriggerInterceptor(db_session, workspace_id="test_workspace")

        # Mock governance cache and user activity service
        with patch('core.trigger_interceptor.get_async_governance_cache') as mock_cache_getter, \
             patch('core.user_activity_service.UserActivityService') as mock_user_activity:

            mock_cache = AsyncMock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()
            mock_cache_getter.return_value = mock_cache

            # Mock user as available
            mock_user_service = MagicMock()
            mock_user_activity.return_value = mock_user_service
            mock_user_service.get_user_state = AsyncMock(return_value="online")
            mock_user_service.should_supervise = MagicMock(return_value=True)

            # Act
            decision = await interceptor.intercept_trigger(
                agent_id=agent.id,
                trigger_source=TriggerSource.AI_COORDINATOR,
                trigger_context={"action_type": "form_submit", "data": "test"},
                user_id=None
            )

        # Assert
        assert decision.execute is True  # Allowed to execute
        assert decision.routing_decision == RoutingDecision.SUPERVISION
        assert decision.agent_id == agent.id
        assert "SUPERVISED agent will execute with real-time monitoring" in decision.reason

    @pytest.mark.asyncio
    async def test_autonomous_agent_full_execution(self, db_session: Session):
        """
        AUTONOMOUS agents (>0.9 confidence) should execute without oversight.
        """
        # Arrange
        agent = AgentRegistry(
            id="autonomous_agent_1",
            name="Autonomous Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95,
        )
        db_session.add(agent)
        db_session.commit()

        interceptor = TriggerInterceptor(db_session, workspace_id="test_workspace")

        # Mock governance cache
        with patch('core.trigger_interceptor.get_async_governance_cache') as mock_cache_getter:
            mock_cache = AsyncMock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()
            mock_cache_getter.return_value = mock_cache

            # Act
            decision = await interceptor.intercept_trigger(
                agent_id=agent.id,
                trigger_source=TriggerSource.WORKFLOW_ENGINE,
                trigger_context={"action_type": "agent_message", "data": "test"},
                user_id=None
            )

        # Assert
        assert decision.execute is True
        assert decision.routing_decision == RoutingDecision.EXECUTION
        assert decision.agent_id == agent.id
        assert "AUTONOMOUS agent" in decision.reason
        assert "approved for full execution" in decision.reason

    @pytest.mark.asyncio
    async def test_manual_trigger_always_allowed(self, db_session: Session):
        """
        MANUAL triggers (user-initiated) should always be allowed regardless of maturity.
        """
        # Arrange - Even STUDENT agents can execute manual triggers
        agent = AgentRegistry(
            id="student_agent_2",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        interceptor = TriggerInterceptor(db_session, workspace_id="test_workspace")

        # Mock governance cache
        with patch('core.trigger_interceptor.get_async_governance_cache') as mock_cache_getter:
            mock_cache = AsyncMock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()
            mock_cache_getter.return_value = mock_cache

            # Act
            decision = await interceptor.intercept_trigger(
                agent_id=agent.id,
                trigger_source=TriggerSource.MANUAL,
                trigger_context={"action_type": "agent_message", "data": "test"},
                user_id="test_user_1"
            )

        # Assert
        assert decision.execute is True
        assert decision.routing_decision == RoutingDecision.EXECUTION
        assert "Manual trigger by user test_user_1" in decision.reason
        # Should include warning for STUDENT agent
        assert "STUDENT mode" in decision.reason


class TestActionComplexityValidation:
    """Test action complexity validation"""

    @pytest.mark.asyncio
    async def test_confidence_score_determines_maturity_level(self, db_session: Session):
        """
        Test that confidence score ranges correctly determine maturity level.
        """
        interceptor = TriggerInterceptor(db_session, workspace_id="test_workspace")

        # Test confidence score boundaries
        test_cases = [
            (0.3, MaturityLevel.STUDENT),    # < 0.5
            (0.5, MaturityLevel.INTERN),      # 0.5 - 0.7
            (0.7, MaturityLevel.SUPERVISED),  # 0.7 - 0.9
            (0.95, MaturityLevel.AUTONOMOUS), # > 0.9
        ]

        for confidence, expected_maturity in test_cases:
            maturity = interceptor._determine_maturity_level(
                status="unknown",  # No explicit status
                confidence_score=confidence
            )
            assert maturity == expected_maturity, \
                f"Confidence {confidence} should map to {expected_maturity}, got {maturity}"

    @pytest.mark.asyncio
    async def test_status_enum_overrides_confidence_score(self, db_session: Session):
        """
        Test that explicit status enum overrides confidence score calculation.
        """
        interceptor = TriggerInterceptor(db_session, workspace_id="test_workspace")

        # Even with low confidence, explicit status should be used
        maturity = interceptor._determine_maturity_level(
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.3  # Low score but status is AUTONOMOUS
        )
        assert maturity == MaturityLevel.AUTONOMOUS


class TestAuditLogging:
    """Test audit trail completeness"""

    @pytest.mark.asyncio
    async def test_blocked_trigger_creates_audit_record(self, db_session: Session):
        """
        Verify all routing decisions are logged to BlockedTriggerContext.
        """
        # Arrange
        agent = AgentRegistry(
            id="student_agent_3",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
        )
        db_session.add(agent)
        db_session.commit()

        interceptor = TriggerInterceptor(db_session, workspace_id="test_workspace")

        # Mock governance cache
        with patch('core.trigger_interceptor.get_async_governance_cache') as mock_cache_getter:
            mock_cache = AsyncMock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()
            mock_cache_getter.return_value = mock_cache

            # Act
            decision = await interceptor.intercept_trigger(
                agent_id=agent.id,
                trigger_source=TriggerSource.WORKFLOW_ENGINE,
                trigger_context={"action_type": "delete", "resource_id": "123"},
                user_id=None
            )

        # Assert - Check audit record was created
        assert decision.blocked_context is not None
        blocked_context = db_session.query(BlockedTriggerContext).filter(
            BlockedTriggerContext.agent_id == agent.id
        ).first()

        assert blocked_context is not None
        assert blocked_context.agent_maturity_at_block == AgentStatus.STUDENT.value
        assert blocked_context.confidence_score_at_block == 0.4
        assert blocked_context.trigger_source == TriggerSource.WORKFLOW_ENGINE.value
        assert blocked_context.trigger_type == "delete"
        assert blocked_context.routing_decision == "training"
        assert blocked_context.resolved is False
        assert blocked_context.created_at is not None


class TestCacheIntegration:
    """Test governance cache integration"""

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_maturity(self, db_session: Session):
        """
        Test that cache hits return cached maturity data without database query.
        """
        # Arrange
        agent = AgentRegistry(
            id="cached_agent_1",
            name="Cached Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db_session.add(agent)
        db_session.commit()

        interceptor = TriggerInterceptor(db_session, workspace_id="test_workspace")

        cached_data = {
            "status": AgentStatus.INTERN.value,
            "confidence": 0.6
        }

        # Mock governance cache with HIT
        with patch('core.trigger_interceptor.get_async_governance_cache') as mock_cache_getter:
            mock_cache = AsyncMock()
            mock_cache.get = AsyncMock(return_value=cached_data)  # Cache hit
            mock_cache.set = AsyncMock()
            mock_cache_getter.return_value = mock_cache

            # Act
            decision = await interceptor.intercept_trigger(
                agent_id=agent.id,
                trigger_source=TriggerSource.WORKFLOW_ENGINE,
                trigger_context={"action_type": "agent_message"},
                user_id=None
            )

        # Assert
        assert decision.agent_maturity == AgentStatus.INTERN.value
        assert decision.confidence_score == 0.6
        # Cache.get was called once
        mock_cache.get.assert_called_once()
        # Cache.set was NOT called (no cache miss)
        mock_cache.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_queries_database_and_updates_cache(self, db_session: Session):
        """
        Test that cache misses query database and update cache with 300s TTL.
        """
        # Arrange
        agent = AgentRegistry(
            id="uncached_agent_1",
            name="Uncached Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.75,
            user_id="test_user_1",  # SUPERVISED agents require user_id
        )
        db_session.add(agent)
        db_session.commit()

        interceptor = TriggerInterceptor(db_session, workspace_id="test_workspace")

        # Mock governance cache with MISS
        with patch('core.trigger_interceptor.get_async_governance_cache') as mock_cache_getter:
            mock_cache = AsyncMock()
            mock_cache.get = AsyncMock(return_value=None)  # Cache miss
            mock_cache.set = AsyncMock()
            mock_cache_getter.return_value = mock_cache

            # Act
            decision = await interceptor.intercept_trigger(
                agent_id=agent.id,
                trigger_source=TriggerSource.WORKFLOW_ENGINE,
                trigger_context={"action_type": "agent_message"},
                user_id=None
            )

        # Assert
        assert decision.agent_maturity == AgentStatus.SUPERVISED.value
        assert decision.confidence_score == 0.75
        # Cache.get was called
        mock_cache.get.assert_called_once()
        # Cache.set was called with correct data
        mock_cache.set.assert_called_once()
        call_args = mock_cache.set.call_args
        assert call_args[0][2]["status"] == AgentStatus.SUPERVISED.value
        assert call_args[0][2]["confidence"] == 0.75


class TestErrorHandling:
    """Test error handling and graceful degradation"""

    @pytest.mark.asyncio
    async def test_missing_agent_id_raises_value_error(self, db_session: Session):
        """
        Test missing agent IDs raise ValueError.
        """
        # Arrange
        interceptor = TriggerInterceptor(db_session, workspace_id="test_workspace")

        # Mock governance cache with miss
        with patch('core.trigger_interceptor.get_async_governance_cache') as mock_cache_getter:
            mock_cache = AsyncMock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()
            mock_cache_getter.return_value = mock_cache

            # Act & Assert
            with pytest.raises(ValueError, match="Agent .* not found"):
                await interceptor.intercept_trigger(
                    agent_id="nonexistent_agent",
                    trigger_source=TriggerSource.WORKFLOW_ENGINE,
                    trigger_context={"action_type": "test"},
                    user_id=None
                )

    @pytest.mark.asyncio
    async def test_invalid_confidence_clamped_to_valid_range(self, db_session: Session):
        """
        Test invalid confidence scores are handled properly.
        Note: _determine_maturity_level doesn't clamp, it maps scores to maturity levels.
        """
        # Arrange
        interceptor = TriggerInterceptor(db_session, workspace_id="test_workspace")

        # Test boundary values - _determine_maturity_level maps score ranges to maturity
        test_cases = [
            (0.0, MaturityLevel.STUDENT),       # Minimum
            (0.49, MaturityLevel.STUDENT),      # Just below INTERN
            (0.5, MaturityLevel.INTERN),        # At INTERN threshold
            (0.7, MaturityLevel.SUPERVISED),    # At SUPERVISED threshold
            (0.9, MaturityLevel.AUTONOMOUS),    # At AUTONOMOUS threshold
            (1.0, MaturityLevel.AUTONOMOUS),    # Maximum
        ]

        for confidence, expected_maturity in test_cases:
            maturity = interceptor._determine_maturity_level(
                status="unknown",
                confidence_score=confidence
            )
            assert maturity == expected_maturity, \
                f"Confidence {confidence} should map to {expected_maturity}, got {maturity}"

    @pytest.mark.asyncio
    async def test_create_proposal_with_missing_agent_raises_error(self, db_session: Session):
        """
        Test create_proposal raises ValueError for nonexistent agent.
        """
        # Arrange
        interceptor = TriggerInterceptor(db_session, workspace_id="test_workspace")

        # Act & Assert
        with pytest.raises(ValueError, match="Agent .* not found"):
            await interceptor.create_proposal(
                intern_agent_id="nonexistent_agent",
                trigger_context={"action_type": "test"},
                proposed_action={"action": "test_action"},
                reasoning="Test reasoning"
            )

    @pytest.mark.asyncio
    async def test_execute_with_supervision_missing_agent_raises_error(self, db_session: Session):
        """
        Test execute_with_supervision raises ValueError for nonexistent agent.
        """
        # Arrange
        interceptor = TriggerInterceptor(db_session, workspace_id="test_workspace")

        # Act & Assert
        with pytest.raises(ValueError, match="Agent .* not found"):
            await interceptor.execute_with_supervision(
                trigger_context={"action_type": "test"},
                agent_id="nonexistent_agent",
                user_id="test_user"
            )

    @pytest.mark.asyncio
    async def test_allow_execution_missing_agent_raises_error(self, db_session: Session):
        """
        Test allow_execution raises ValueError for nonexistent agent.
        """
        # Arrange
        interceptor = TriggerInterceptor(db_session, workspace_id="test_workspace")

        # Act & Assert
        with pytest.raises(ValueError, match="Agent .* not found"):
            await interceptor.allow_execution(
                agent_id="nonexistent_agent",
                trigger_context={"action_type": "test"}
            )


class TestRoutingMethods:
    """Test individual routing methods"""

    @pytest.mark.asyncio
    async def test_route_to_training_creates_proposal(self, db_session: Session):
        """
        Test route_to_training creates training proposal.
        """
        # Arrange
        agent = AgentRegistry(
            id="training_agent_1",
            name="Training Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        interceptor = TriggerInterceptor(db_session, workspace_id="test_workspace")

        # Act
        proposal = await interceptor.route_to_training(blocked_trigger)

        # Assert
        assert proposal is not None
        assert proposal.agent_id == agent.id
        assert proposal.proposal_type == "training"
        assert proposal.status == ProposalStatus.PROPOSED.value
        assert blocked_trigger.proposal_id == proposal.id

    @pytest.mark.asyncio
    async def test_create_proposal_saves_to_database(self, db_session: Session):
        """
        Test create_proposal saves proposal with correct fields.
        """
        # Arrange
        agent = AgentRegistry(
            id="proposal_agent_1",
            name="Proposal Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db_session.add(agent)
        db_session.commit()

        interceptor = TriggerInterceptor(db_session, workspace_id="test_workspace")

        # Act
        proposal = await interceptor.create_proposal(
            intern_agent_id=agent.id,
            trigger_context={"action_type": "workflow_trigger"},
            proposed_action={"action_type": "deploy", "target": "production"},
            reasoning="Testing proposal creation"
        )

        # Assert
        assert proposal.agent_id == agent.id
        assert proposal.proposal_type == "action"
        assert "Action Proposal" in proposal.title
        assert "deploy" in proposal.description
        assert proposal.reasoning == "Testing proposal creation"
        assert proposal.status == ProposalStatus.PROPOSED.value
        assert proposal.proposed_by == agent.id

        # Verify in database
        db_session.refresh(proposal)
        assert proposal.id is not None

    @pytest.mark.asyncio
    async def test_execute_with_supervision_creates_session(self, db_session: Session):
        """
        Test execute_with_supervision creates supervision session.
        """
        # Arrange
        agent = AgentRegistry(
            id="supervision_agent_1",
            name="Supervision Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8,
        )
        db_session.add(agent)
        db_session.commit()

        interceptor = TriggerInterceptor(db_session, workspace_id="test_workspace")

        # Act
        session = await interceptor.execute_with_supervision(
            trigger_context={"action_type": "test"},
            agent_id=agent.id,
            user_id="test_user"
        )

        # Assert
        assert session is not None
        assert session.agent_id == agent.id
        assert session.workspace_id == "test_workspace"
        assert session.status == SupervisionStatus.RUNNING.value
        assert session.supervisor_id == "test_user"

    @pytest.mark.asyncio
    async def test_allow_execution_returns_context(self, db_session: Session):
        """
        Test allow_execution returns execution context.
        """
        # Arrange
        agent = AgentRegistry(
            id="execution_agent_1",
            name="Execution Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95,
        )
        db_session.add(agent)
        db_session.commit()

        interceptor = TriggerInterceptor(db_session, workspace_id="test_workspace")

        # Act
        context = await interceptor.allow_execution(
            agent_id=agent.id,
            trigger_context={"action_type": "test_action"}
        )

        # Assert
        assert context["allowed"] is True
        assert context["agent_id"] == agent.id
        assert context["agent_maturity"] == AgentStatus.AUTONOMOUS.value
        assert context["confidence_score"] == 0.95
        assert context["trigger_context"]["action_type"] == "test_action"
