"""
Tests for Trigger Interceptor and Maturity-Based Routing

Tests trigger interception, maturity-based routing decisions,
and integration with all trigger sources.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from sqlalchemy.orm import Session

from core.trigger_interceptor import (
    TriggerInterceptor, TriggerSource, MaturityLevel, RoutingDecision
)
from core.models import (
    AgentRegistry, AgentStatus, BlockedTriggerContext,
    AgentProposal, SupervisionSession, SupervisionStatus
)


@pytest.fixture
def db_session():
    """Mock database session"""
    return Mock(spec=Session)


@pytest.fixture
def mock_student_agent():
    """Mock student agent"""
    agent = Mock(spec=AgentRegistry)
    agent.id = "student_agent_1"
    agent.name = "Student Finance Agent"
    agent.status = AgentStatus.STUDENT.value
    agent.confidence_score = 0.3
    agent.category = "Finance"
    return agent


@pytest.fixture
def mock_intern_agent():
    """Mock intern agent"""
    agent = Mock(spec=AgentRegistry)
    agent.id = "intern_agent_1"
    agent.name = "Intern Sales Agent"
    agent.status = AgentStatus.INTERN.value
    agent.confidence_score = 0.6
    agent.category = "Sales"
    return agent


@pytest.fixture
def mock_supervised_agent():
    """Mock supervised agent"""
    agent = Mock(spec=AgentRegistry)
    agent.id = "supervised_agent_1"
    agent.name = "Supervised Operations Agent"
    agent.status = AgentStatus.SUPERVISED.value
    agent.confidence_score = 0.8
    agent.category = "Operations"
    return agent


@pytest.fixture
def mock_autonomous_agent():
    """Mock autonomous agent"""
    agent = Mock(spec=AgentRegistry)
    agent.id = "autonomous_agent_1"
    agent.name = "Autonomous HR Agent"
    agent.status = AgentStatus.AUTONOMOUS.value
    agent.confidence_score = 0.95
    agent.category = "HR"
    return agent


class TestTriggerInterceptor:
    """Tests for TriggerInterceptor"""

    @pytest.mark.asyncio
    async def test_student_agent_blocked_from_automated_trigger(
        self, db_session, mock_student_agent
    ):
        """Test that STUDENT agents are blocked from automated triggers"""
        # Setup
        db_session.query.return_value.filter.return_value.first.return_value = mock_student_agent

        interceptor = TriggerInterceptor(db_session, "workspace_1")
        trigger_context = {
            "action_type": "agent_message",
            "data": {"test": "data"}
        }

        # Mock cache
        with patch('core.trigger_interceptor.get_async_governance_cache', new_callable=AsyncMock) as mock_get_cache:
            mock_cache = Mock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()
            mock_get_cache.return_value = mock_cache

            # Mock training service to avoid database queries
            with patch.object(interceptor, 'route_to_training', new_callable=AsyncMock) as mock_training:
                mock_proposal = Mock(id="proposal_1")
                mock_training.return_value = mock_proposal

                # Execute
                decision = await interceptor.intercept_trigger(
                agent_id=mock_student_agent.id,
                trigger_source=TriggerSource.AI_COORDINATOR,
                trigger_context=trigger_context
            )

        # Assert
        assert decision.routing_decision == RoutingDecision.TRAINING
        assert decision.execute is False
        assert decision.agent_maturity == AgentStatus.STUDENT.value
        assert decision.blocked_context is not None
        assert "blocked" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_intern_agent_requires_proposal(
        self, db_session, mock_intern_agent
    ):
        """Test that INTERN agents generate proposals for human review"""
        # Setup
        db_session.query.return_value.filter.return_value.first.return_value = mock_intern_agent

        interceptor = TriggerInterceptor(db_session, "workspace_1")
        trigger_context = {
            "action_type": "workflow_trigger",
            "data": {"test": "data"}
        }

        # Mock cache
        with patch('core.trigger_interceptor.get_async_governance_cache', new_callable=AsyncMock) as mock_get_cache:
            mock_cache = Mock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()
            mock_get_cache.return_value = mock_cache

            # Execute
            decision = await interceptor.intercept_trigger(
                agent_id=mock_intern_agent.id,
                trigger_source=TriggerSource.WORKFLOW_ENGINE,
                trigger_context=trigger_context
            )

        # Assert
        assert decision.routing_decision == RoutingDecision.PROPOSAL
        assert decision.execute is False
        assert decision.agent_maturity == AgentStatus.INTERN.value
        assert decision.blocked_context is not None
        assert "proposal" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_supervised_agent_executes_with_supervision(
        self, db_session, mock_supervised_agent
    ):
        """Test that SUPERVISED agents execute with supervision"""
        # Setup
        db_session.query.return_value.filter.return_value.first.return_value = mock_supervised_agent

        interceptor = TriggerInterceptor(db_session, "workspace_1")
        trigger_context = {
            "action_type": "data_sync",
            "data": {"test": "data"}
        }

        # Mock cache
        with patch('core.trigger_interceptor.get_async_governance_cache', new_callable=AsyncMock) as mock_get_cache:
            mock_cache = Mock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()
            mock_get_cache.return_value = mock_cache

            # Execute
            decision = await interceptor.intercept_trigger(
                agent_id=mock_supervised_agent.id,
                trigger_source=TriggerSource.DATA_SYNC,
                trigger_context=trigger_context
            )

        # Assert
        assert decision.routing_decision == RoutingDecision.SUPERVISION
        assert decision.execute is True  # Can execute, but under supervision
        assert decision.agent_maturity == AgentStatus.SUPERVISED.value
        assert "supervised" in decision.reason.lower() or "monitoring" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_autonomous_agent_full_execution(
        self, db_session, mock_autonomous_agent
    ):
        """Test that AUTONOMOUS agents execute without oversight"""
        # Setup
        db_session.query.return_value.filter.return_value.first.return_value = mock_autonomous_agent

        interceptor = TriggerInterceptor(db_session, "workspace_1")
        trigger_context = {
            "action_type": "agent_message",
            "data": {"test": "data"}
        }

        # Mock cache
        with patch('core.trigger_interceptor.get_async_governance_cache', new_callable=AsyncMock) as mock_get_cache:
            mock_cache = Mock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()
            mock_get_cache.return_value = mock_cache

            # Mock training service to avoid database queries
            with patch.object(interceptor, 'route_to_training', new_callable=AsyncMock) as mock_training:
                mock_proposal = Mock(id="proposal_1")
                mock_training.return_value = mock_proposal

                # Execute
                decision = await interceptor.intercept_trigger(
                agent_id=mock_autonomous_agent.id,
                trigger_source=TriggerSource.AI_COORDINATOR,
                trigger_context=trigger_context
            )

        # Assert
        assert decision.routing_decision == RoutingDecision.EXECUTION
        assert decision.execute is True
        assert decision.agent_maturity == AgentStatus.AUTONOMOUS.value
        assert "approved" in decision.reason.lower() or "full execution" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_manual_trigger_always_allowed(
        self, db_session, mock_student_agent
    ):
        """Test that MANUAL triggers always allowed, even for STUDENT agents"""
        # Setup
        db_session.query.return_value.filter.return_value.first.return_value = mock_student_agent

        interceptor = TriggerInterceptor(db_session, "workspace_1")
        trigger_context = {
            "action_type": "agent_message",
            "user_initiated": True
        }

        # Mock cache
        with patch('core.trigger_interceptor.get_async_governance_cache', new_callable=AsyncMock) as mock_get_cache:
            mock_cache = Mock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()
            mock_get_cache.return_value = mock_cache

            # Execute
            decision = await interceptor.intercept_trigger(
                agent_id=mock_student_agent.id,
                trigger_source=TriggerSource.MANUAL,
                trigger_context=trigger_context,
                user_id="user_1"
            )

        # Assert
        assert decision.routing_decision == RoutingDecision.EXECUTION
        assert decision.execute is True
        assert "manual" in decision.reason.lower()
        # Should still warn about student status
        assert "student" in decision.reason.lower() or "warning" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_maturity_determination_from_status(self):
        """Test maturity level determination from agent status"""
        interceptor = TriggerInterceptor(Mock(), "workspace_1")

        # Test STUDENT
        maturity = interceptor._determine_maturity_level(AgentStatus.STUDENT.value, 0.3)
        assert maturity == MaturityLevel.STUDENT

        # Test INTERN
        maturity = interceptor._determine_maturity_level(AgentStatus.INTERN.value, 0.6)
        assert maturity == MaturityLevel.INTERN

        # Test SUPERVISED
        maturity = interceptor._determine_maturity_level(AgentStatus.SUPERVISED.value, 0.8)
        assert maturity == MaturityLevel.SUPERVISED

        # Test AUTONOMOUS
        maturity = interceptor._determine_maturity_level(AgentStatus.AUTONOMOUS.value, 0.95)
        assert maturity == MaturityLevel.AUTONOMOUS

    @pytest.mark.asyncio
    async def test_maturity_determination_from_confidence(self):
        """Test maturity level determination from confidence score when status is unknown"""
        interceptor = TriggerInterceptor(Mock(), "workspace_1")

        # Unknown status, use confidence ranges
        maturity = interceptor._determine_maturity_level("unknown", 0.3)
        assert maturity == MaturityLevel.STUDENT

        maturity = interceptor._determine_maturity_level("unknown", 0.6)
        assert maturity == MaturityLevel.INTERN

        maturity = interceptor._determine_maturity_level("unknown", 0.8)
        assert maturity == MaturityLevel.SUPERVISED

        maturity = interceptor._determine_maturity_level("unknown", 0.95)
        assert maturity == MaturityLevel.AUTONOMOUS

    @pytest.mark.asyncio
    async def test_all_trigger_sources_supported(self, db_session, mock_autonomous_agent):
        """Test that all trigger sources are supported"""
        db_session.query.return_value.filter.return_value.first.return_value = mock_autonomous_agent

        interceptor = TriggerInterceptor(db_session, "workspace_1")
        trigger_context = {"action_type": "test"}

        with patch('core.trigger_interceptor.get_async_governance_cache', new_callable=AsyncMock) as mock_get_cache:
            mock_cache = Mock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()
            mock_get_cache.return_value = mock_cache

            # Test each trigger source
            for source in [TriggerSource.MANUAL, TriggerSource.DATA_SYNC,
                          TriggerSource.WORKFLOW_ENGINE, TriggerSource.AI_COORDINATOR]:
                decision = await interceptor.intercept_trigger(
                    agent_id=mock_autonomous_agent.id,
                    trigger_source=source,
                    trigger_context=trigger_context
                )

                assert decision is not None
                assert decision.agent_id == mock_autonomous_agent.id


class TestMaturityRouting:
    """Tests for maturity-based routing logic"""

    @pytest.mark.asyncio
    async def test_route_to_training_creates_proposal(
        self, db_session, mock_student_agent
    ):
        """Test that routing to training creates a proposal"""
        # Setup
        db_session.query.return_value.filter.return_value.first.return_value = mock_student_agent
        db_session.add = Mock()
        db_session.commit = Mock()
        db_session.refresh = Mock()

        blocked_context = BlockedTriggerContext(
            id="blocked_1",
            agent_id=mock_student_agent.id,
            agent_name=mock_student_agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=mock_student_agent.confidence_score,
            trigger_source=TriggerSource.AI_COORDINATOR.value,
            trigger_type="agent_message",
            trigger_context={"test": "data"},
            routing_decision="training",
            block_reason="Student agent blocked"
        )

        interceptor = TriggerInterceptor(db_session, "workspace_1")

        # Mock training service
        with patch.object(interceptor, 'training_service') as mock_service:
            mock_proposal = Mock(id="proposal_1")
            mock_service.create_training_proposal = AsyncMock(return_value=mock_proposal)

            # Execute
            proposal = await interceptor.route_to_training(blocked_context)

            # Assert
            assert proposal.id == "proposal_1"
            mock_service.create_training_proposal.assert_called_once_with(blocked_context)

    @pytest.mark.asyncio
    async def test_supervision_session_created(
        self, db_session, mock_supervised_agent
    ):
        """Test that supervision creates a session"""
        # Setup
        db_session.query.return_value.filter.return_value.first.return_value = mock_supervised_agent
        db_session.add = Mock()
        db_session.commit = Mock()
        db_session.refresh = Mock()

        interceptor = TriggerInterceptor(db_session, "workspace_1")
        trigger_context = {"action_type": "test"}

        # Execute
        session = await interceptor.execute_with_supervision(
            trigger_context=trigger_context,
            agent_id=mock_supervised_agent.id,
            user_id="supervisor_1"
        )

        # Assert
        assert session.agent_id == mock_supervised_agent.id
        assert session.workspace_id == "workspace_1"
        assert session.supervisor_id == "supervisor_1"
        assert session.status == SupervisionStatus.RUNNING.value


class TestPerformance:
    """Performance tests"""

    @pytest.mark.asyncio
    async def test_cached_maturity_lookup(self, db_session, mock_autonomous_agent):
        """Test that cached maturity lookups are fast"""
        db_session.query.return_value.filter.return_value.first.return_value = mock_autonomous_agent

        interceptor = TriggerInterceptor(db_session, "workspace_1")
        trigger_context = {"action_type": "test"}

        with patch('core.trigger_interceptor.get_async_governance_cache', new_callable=AsyncMock) as mock_get_cache:
            mock_cache = Mock()
            # First call - cache miss
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()
            mock_get_cache.return_value = mock_cache

            await interceptor.intercept_trigger(
                agent_id=mock_autonomous_agent.id,
                trigger_source=TriggerSource.AI_COORDINATOR,
                trigger_context=trigger_context
            )

            # Verify cache was set
            assert mock_cache.set.called

            # Second call - cache hit
            mock_cache.get = AsyncMock(return_value={
                "status": AgentStatus.AUTONOMOUS.value,
                "confidence": 0.95
            })

            decision = await interceptor.intercept_trigger(
                agent_id=mock_autonomous_agent.id,
                trigger_source=TriggerSource.AI_COORDINATOR,
                trigger_context=trigger_context
            )

            # Should not query database again
            assert decision.routing_decision == RoutingDecision.EXECUTION
