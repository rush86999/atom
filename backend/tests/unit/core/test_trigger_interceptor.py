"""
Tests for Trigger Interceptor with Maturity-Based Routing

Tests the critical safety rail that intercepts agent triggers and routes
based on agent maturity levels (STUDENT, INTERN, SUPERVISED, AUTONOMOUS).

Coverage Target: 80%+
Priority: P0 (Critical Safety Rail)

Markers:
    unit: Fast, isolated tests
    P0: Critical priority
    governance: Agent governance tests
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

# Mark test class for pytest
pytestmark = [pytest.mark.unit, pytest.mark.P0, pytest.mark.governance]

from core.trigger_interceptor import (
    TriggerInterceptor,
    TriggerDecision,
    MaturityLevel,
    RoutingDecision,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Create a mock database session"""
    db = MagicMock(spec=Session)
    db.query = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def mock_cache():
    """Create a mock governance cache"""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)  # Cache miss by default
    cache.set = AsyncMock()
    return cache


@pytest.fixture
def student_agent():
    """Create a STUDENT agent fixture"""
    agent = MagicMock(spec=AgentRegistry)
    agent.id = "agent-student-001"
    agent.name = "Student Agent"
    agent.status = AgentStatus.STUDENT.value
    agent.confidence_score = 0.3
    agent.user_id = "user-001"
    return agent


@pytest.fixture
def intern_agent():
    """Create an INTERN agent fixture"""
    agent = MagicMock(spec=AgentRegistry)
    agent.id = "agent-intern-001"
    agent.name = "Intern Agent"
    agent.status = AgentStatus.INTERN.value
    agent.confidence_score = 0.6
    agent.user_id = "user-001"
    return agent


@pytest.fixture
def supervised_agent():
    """Create a SUPERVISED agent fixture"""
    agent = MagicMock(spec=AgentRegistry)
    agent.id = "agent-supervised-001"
    agent.name = "Supervised Agent"
    agent.status = AgentStatus.SUPERVISED.value
    agent.confidence_score = 0.8
    agent.user_id = "user-001"
    return agent


@pytest.fixture
def autonomous_agent():
    """Create an AUTONOMOUS agent fixture"""
    agent = MagicMock(spec=AgentRegistry)
    agent.id = "agent-autonomous-001"
    agent.name = "Autonomous Agent"
    agent.status = AgentStatus.AUTONOMOUS.value
    agent.confidence_score = 0.95
    agent.user_id = "user-001"
    return agent


@pytest.fixture
def trigger_context():
    """Create a sample trigger context"""
    return {
        "action_type": "send_email",
        "payload": {"to": "test@example.com", "body": "Test"},
        "timestamp": datetime.utcnow().isoformat(),
    }


@pytest.fixture
def interceptor(mock_db):
    """Create a TriggerInterceptor instance"""
    return TriggerInterceptor(db=mock_db, workspace_id="workspace-001")


# ============================================================================
# Test Maturity Level Determination
# ============================================================================

class TestMaturityLevelDetermination:
    """Test _determine_maturity_level method"""

    def test_student_by_status(self, interceptor):
        """Test STUDENT maturity from explicit status"""
        result = interceptor._determine_maturity_level(
            AgentStatus.STUDENT.value, 0.3
        )
        assert result == MaturityLevel.STUDENT

    def test_intern_by_status(self, interceptor):
        """Test INTERN maturity from explicit status"""
        result = interceptor._determine_maturity_level(
            AgentStatus.INTERN.value, 0.6
        )
        assert result == MaturityLevel.INTERN

    def test_supervised_by_status(self, interceptor):
        """Test SUPERVISED maturity from explicit status"""
        result = interceptor._determine_maturity_level(
            AgentStatus.SUPERVISED.value, 0.8
        )
        assert result == MaturityLevel.SUPERVISED

    def test_autonomous_by_status(self, interceptor):
        """Test AUTONOMOUS maturity from explicit status"""
        result = interceptor._determine_maturity_level(
            AgentStatus.AUTONOMOUS.value, 0.95
        )
        assert result == MaturityLevel.AUTONOMOUS

    def test_student_by_confidence(self, interceptor):
        """Test STUDENT maturity from confidence score (<0.5)"""
        result = interceptor._determine_maturity_level("unknown", 0.4)
        assert result == MaturityLevel.STUDENT

    def test_intern_by_confidence(self, interceptor):
        """Test INTERN maturity from confidence score (0.5-0.7)"""
        result = interceptor._determine_maturity_level("unknown", 0.55)
        assert result == MaturityLevel.INTERN

    def test_supervised_by_confidence(self, interceptor):
        """Test SUPERVISED maturity from confidence score (0.7-0.9)"""
        result = interceptor._determine_maturity_level("unknown", 0.75)
        assert result == MaturityLevel.SUPERVISED

    def test_autonomous_by_confidence(self, interceptor):
        """Test AUTONOMOUS maturity from confidence score (>0.9)"""
        result = interceptor._determine_maturity_level("unknown", 0.92)
        assert result == MaturityLevel.AUTONOMOUS

    def test_boundary_confidence_0_5(self, interceptor):
        """Test boundary at 0.5 confidence"""
        result = interceptor._determine_maturity_level("unknown", 0.5)
        assert result == MaturityLevel.INTERN

    def test_boundary_confidence_0_7(self, interceptor):
        """Test boundary at 0.7 confidence"""
        result = interceptor._determine_maturity_level("unknown", 0.7)
        assert result == MaturityLevel.SUPERVISED

    def test_boundary_confidence_0_9(self, interceptor):
        """Test boundary at 0.9 confidence"""
        result = interceptor._determine_maturity_level("unknown", 0.9)
        assert result == MaturityLevel.AUTONOMOUS


# ============================================================================
# Test Manual Trigger Handling
# ============================================================================

class TestManualTriggerHandling:
    """Test _handle_manual_trigger method"""

    @pytest.mark.asyncio
    async def test_manual_trigger_student_warning(self, interceptor, student_agent):
        """Test manual trigger with STUDENT agent shows warning"""
        decision = await interceptor._handle_manual_trigger(
            agent_id=student_agent.id,
            maturity_level=MaturityLevel.STUDENT,
            confidence_score=0.3,
            trigger_context={"action": "test"},
            user_id="user-001"
        )

        assert decision.routing_decision == RoutingDecision.EXECUTION
        assert decision.execute is True
        assert "STUDENT mode" in decision.reason
        assert "user-001" in decision.reason

    @pytest.mark.asyncio
    async def test_manual_trigger_intern_note(self, interceptor, intern_agent):
        """Test manual trigger with INTERN agent shows note"""
        decision = await interceptor._handle_manual_trigger(
            agent_id=intern_agent.id,
            maturity_level=MaturityLevel.INTERN,
            confidence_score=0.6,
            trigger_context={"action": "test"},
            user_id="user-002"
        )

        assert decision.routing_decision == RoutingDecision.EXECUTION
        assert decision.execute is True
        assert "INTERN learning mode" in decision.reason

    @pytest.mark.asyncio
    async def test_manual_trigger_supervised_info(self, interceptor, supervised_agent):
        """Test manual trigger with SUPERVISED agent shows info"""
        decision = await interceptor._handle_manual_trigger(
            agent_id=supervised_agent.id,
            maturity_level=MaturityLevel.SUPERVISED,
            confidence_score=0.8,
            trigger_context={"action": "test"},
            user_id="user-003"
        )

        assert decision.routing_decision == RoutingDecision.EXECUTION
        assert decision.execute is True
        assert "SUPERVISION mode" in decision.reason

    @pytest.mark.asyncio
    async def test_manual_trigger_autonomous(self, interceptor, autonomous_agent):
        """Test manual trigger with AUTONOMOUS agent"""
        decision = await interceptor._handle_manual_trigger(
            agent_id=autonomous_agent.id,
            maturity_level=MaturityLevel.AUTONOMOUS,
            confidence_score=0.95,
            trigger_context={"action": "test"},
            user_id="user-004"
        )

        assert decision.routing_decision == RoutingDecision.EXECUTION
        assert decision.execute is True
        assert "user-004" in decision.reason

    @pytest.mark.asyncio
    async def test_manual_trigger_unknown_user(self, interceptor, autonomous_agent):
        """Test manual trigger with unknown user"""
        decision = await interceptor._handle_manual_trigger(
            agent_id=autonomous_agent.id,
            maturity_level=MaturityLevel.AUTONOMOUS,
            confidence_score=0.95,
            trigger_context={"action": "test"},
            user_id=None
        )

        assert decision.execute is True
        assert "unknown" in decision.reason


# ============================================================================
# Test STUDENT Agent Routing
# ============================================================================

class TestStudentAgentRouting:
    """Test _route_student_agent method"""

    @pytest.mark.asyncio
    async def test_student_automated_trigger_blocked(
        self, interceptor, mock_db, student_agent, trigger_context
    ):
        """Test STUDENT agent automated triggers are blocked"""
        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = student_agent
        mock_db.query.return_value = mock_query

        # Mock training service
        mock_proposal = MagicMock(spec=AgentProposal)
        mock_proposal.id = "proposal-001"
        interceptor.training_service.create_training_proposal = AsyncMock(
            return_value=mock_proposal
        )

        decision = await interceptor._route_student_agent(
            agent_id=student_agent.id,
            trigger_source=TriggerSource.WORKFLOW_ENGINE,
            trigger_context=trigger_context,
            confidence_score=0.3
        )

        # Verify decision
        assert decision.routing_decision == RoutingDecision.TRAINING
        assert decision.execute is False
        assert decision.agent_id == student_agent.id
        assert "STUDENT agent blocked" in decision.reason
        assert decision.proposal == mock_proposal

        # Verify blocked context was created
        assert mock_db.add.called
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_student_trigger_creates_blocked_context(
        self, interceptor, mock_db, student_agent, trigger_context
    ):
        """Test blocked context is created for STUDENT agent"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = student_agent
        mock_db.query.return_value = mock_query

        mock_proposal = MagicMock(spec=AgentProposal)
        mock_proposal.id = "proposal-002"
        interceptor.training_service.create_training_proposal = AsyncMock(
            return_value=mock_proposal
        )

        await interceptor._route_student_agent(
            agent_id=student_agent.id,
            trigger_source=TriggerSource.DATA_SYNC,
            trigger_context=trigger_context,
            confidence_score=0.25
        )

        # Verify BlockedTriggerContext was created with correct fields
        call_args = mock_db.add.call_args
        blocked_context = call_args[0][0]
        
        assert isinstance(blocked_context, BlockedTriggerContext)
        assert blocked_context.agent_id == student_agent.id
        assert blocked_context.agent_maturity_at_block == AgentStatus.STUDENT.value
        assert blocked_context.routing_decision == RoutingDecision.TRAINING.value
        assert "STUDENT agent" in blocked_context.block_reason

    @pytest.mark.asyncio
    async def test_student_training_proposal_created(
        self, interceptor, mock_db, student_agent, trigger_context
    ):
        """Test training proposal is created for STUDENT agent"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = student_agent
        mock_db.query.return_value = mock_query

        mock_proposal = MagicMock(spec=AgentProposal)
        mock_proposal.id = "proposal-003"
        interceptor.training_service.create_training_proposal = AsyncMock(
            return_value=mock_proposal
        )

        decision = await interceptor._route_student_agent(
            agent_id=student_agent.id,
            trigger_source=TriggerSource.AI_COORDINATOR,
            trigger_context=trigger_context,
            confidence_score=0.4
        )

        # Verify training service was called
        interceptor.training_service.create_training_proposal.assert_called_once()
        
        # Verify proposal ID in decision
        assert decision.proposal.id == "proposal-003"
        assert f"Training proposal {decision.proposal.id} created" in decision.reason


# ============================================================================
# Test INTERN Agent Routing
# ============================================================================

class TestInternAgentRouting:
    """Test _route_intern_agent method"""

    @pytest.mark.asyncio
    async def test_intern_trigger_requires_proposal(
        self, interceptor, mock_db, intern_agent, trigger_context
    ):
        """Test INTERN agent triggers require proposal"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = intern_agent
        mock_db.query.return_value = mock_query

        decision = await interceptor._route_intern_agent(
            agent_id=intern_agent.id,
            trigger_source=TriggerSource.WORKFLOW_ENGINE,
            trigger_context=trigger_context,
            confidence_score=0.6
        )

        assert decision.routing_decision == RoutingDecision.PROPOSAL
        assert decision.execute is False
        assert "INTERN agent" in decision.reason
        assert "proposal" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_intern_trigger_creates_blocked_context(
        self, interceptor, mock_db, intern_agent, trigger_context
    ):
        """Test blocked context is created for INTERN agent"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = intern_agent
        mock_db.query.return_value = mock_query

        await interceptor._route_intern_agent(
            agent_id=intern_agent.id,
            trigger_source=TriggerSource.DATA_SYNC,
            trigger_context=trigger_context,
            confidence_score=0.55
        )

        # Verify BlockedTriggerContext was created
        call_args = mock_db.add.call_args
        blocked_context = call_args[0][0]
        
        assert isinstance(blocked_context, BlockedTriggerContext)
        assert blocked_context.agent_id == intern_agent.id
        assert blocked_context.agent_maturity_at_block == AgentStatus.INTERN.value
        assert blocked_context.routing_decision == RoutingDecision.PROPOSAL.value


# ============================================================================
# Test SUPERVISED Agent Routing
# ============================================================================

class TestSupervisedAgentRouting:
    """Test _route_supervised_agent method"""

    @pytest.mark.asyncio
    async def test_supervised_user_available(
        self, interceptor, mock_db, supervised_agent, trigger_context
    ):
        """Test SUPERVISED agent with available user"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = supervised_agent
        mock_db.query.return_value = mock_query

        # Mock user activity service
        with patch('core.trigger_interceptor.UserActivityService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_user_state = AsyncMock(return_value="active")
            mock_service.should_supervise = MagicMock(return_value=True)
            mock_service_class.return_value = mock_service

            decision = await interceptor._route_supervised_agent(
                agent_id=supervised_agent.id,
                trigger_source=TriggerSource.WORKFLOW_ENGINE,
                trigger_context=trigger_context,
                confidence_score=0.8
            )

            assert decision.routing_decision == RoutingDecision.SUPERVISION
            assert decision.execute is True
            assert "real-time monitoring" in decision.reason
            assert "user available" in decision.reason

    @pytest.mark.asyncio
    async def test_supervised_user_unavailable(
        self, interceptor, mock_db, supervised_agent, trigger_context
    ):
        """Test SUPERVISED agent with unavailable user"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = supervised_agent
        mock_db.query.return_value = mock_query

        # Mock user activity service
        with patch('core.trigger_interceptor.UserActivityService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_user_state = AsyncMock(return_value="away")
            mock_service.should_supervise = MagicMock(return_value=False)
            mock_service_class.return_value = mock_service

            # Mock queue service
            with patch('core.trigger_interceptor.SupervisedQueueService') as mock_queue_class:
                mock_queue = AsyncMock()
                mock_queue.enqueue_execution = AsyncMock()
                mock_queue_class.return_value = mock_queue

                decision = await interceptor._route_supervised_agent(
                    agent_id=supervised_agent.id,
                    trigger_source=TriggerSource.DATA_SYNC,
                    trigger_context=trigger_context,
                    confidence_score=0.75
                )

                assert decision.routing_decision == RoutingDecision.SUPERVISION
                assert decision.execute is False
                assert "queued" in decision.reason
                assert "user unavailable" in decision.reason

                # Verify queue service was called
                mock_queue.enqueue_execution.assert_called_once()

    @pytest.mark.asyncio
    async def test_supervised_agent_not_found(
        self, interceptor, mock_db, trigger_context
    ):
        """Test SUPERVISED routing when agent not found"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        decision = await interceptor._route_supervised_agent(
            agent_id="nonexistent-agent",
            trigger_source=TriggerSource.WORKFLOW_ENGINE,
            trigger_context=trigger_context,
            confidence_score=0.8
        )

        assert decision.routing_decision == RoutingDecision.SUPERVISION
        assert decision.execute is False
        assert "not found" in decision.reason


# ============================================================================
# Test AUTONOMOUS Agent Routing
# ============================================================================

class TestAutonomousAgentRouting:
    """Test _allow_execution method"""

    @pytest.mark.asyncio
    async def test_autonomous_agent_execution_allowed(
        self, interceptor, mock_db, autonomous_agent, trigger_context
    ):
        """Test AUTONOMOUS agent execution is allowed"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = autonomous_agent
        mock_db.query.return_value = mock_query

        decision = await interceptor._allow_execution(
            agent_id=autonomous_agent.id,
            trigger_source=TriggerSource.WORKFLOW_ENGINE,
            trigger_context=trigger_context,
            confidence_score=0.95
        )

        assert decision.routing_decision == RoutingDecision.EXECUTION
        assert decision.execute is True
        assert "AUTONOMOUS agent" in decision.reason
        assert "approved for full execution" in decision.reason

    @pytest.mark.asyncio
    async def test_autonomous_agent_not_found(
        self, interceptor, mock_db, trigger_context
    ):
        """Test AUTONOMOUS routing when agent not found"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(ValueError, match="Agent .* not found"):
            await interceptor._allow_execution(
                agent_id="nonexistent-agent",
                trigger_source=TriggerSource.WORKFLOW_ENGINE,
                trigger_context=trigger_context,
                confidence_score=0.95
            )


# ============================================================================
# Test Main Intercept Method
# ============================================================================

class TestInterceptTrigger:
    """Test main intercept_trigger method"""

    @pytest.mark.asyncio
    async def test_intercept_manual_trigger(
        self, interceptor, mock_db, student_agent, trigger_context
    ):
        """Test intercept with MANUAL trigger source"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = student_agent
        mock_db.query.return_value = mock_query

        # Mock cache
        with patch('core.trigger_interceptor.get_async_governance_cache') as mock_cache_getter:
            mock_cache = AsyncMock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache_getter.return_value = mock_cache

            decision = await interceptor.intercept_trigger(
                agent_id=student_agent.id,
                trigger_source=TriggerSource.MANUAL,
                trigger_context=trigger_context,
                user_id="user-001"
            )

            assert decision.execute is True
            assert "Manual trigger" in decision.reason

    @pytest.mark.asyncio
    async def test_intercept_student_automated(
        self, interceptor, mock_db, student_agent, trigger_context
    ):
        """Test intercept with STUDENT agent automated trigger"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = student_agent
        mock_db.query.return_value = mock_query

        mock_proposal = MagicMock(spec=AgentProposal)
        mock_proposal.id = "proposal-004"
        interceptor.training_service.create_training_proposal = AsyncMock(
            return_value=mock_proposal
        )

        with patch('core.trigger_interceptor.get_async_governance_cache') as mock_cache_getter:
            mock_cache = AsyncMock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache_getter.return_value = mock_cache

            decision = await interceptor.intercept_trigger(
                agent_id=student_agent.id,
                trigger_source=TriggerSource.WORKFLOW_ENGINE,
                trigger_context=trigger_context,
                user_id=None
            )

            assert decision.execute is False
            assert decision.routing_decision == RoutingDecision.TRAINING

    @pytest.mark.asyncio
    async def test_intercept_intern_automated(
        self, interceptor, mock_db, intern_agent, trigger_context
    ):
        """Test intercept with INTERN agent automated trigger"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = intern_agent
        mock_db.query.return_value = mock_query

        with patch('core.trigger_interceptor.get_async_governance_cache') as mock_cache_getter:
            mock_cache = AsyncMock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache_getter.return_value = mock_cache

            decision = await interceptor.intercept_trigger(
                agent_id=intern_agent.id,
                trigger_source=TriggerSource.DATA_SYNC,
                trigger_context=trigger_context,
                user_id=None
            )

            assert decision.execute is False
            assert decision.routing_decision == RoutingDecision.PROPOSAL

    @pytest.mark.asyncio
    async def test_intercept_supervised_automated(
        self, interceptor, mock_db, supervised_agent, trigger_context
    ):
        """Test intercept with SUPERVISED agent automated trigger"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = supervised_agent
        mock_db.query.return_value = mock_query

        with patch('core.trigger_interceptor.get_async_governance_cache') as mock_cache_getter:
            mock_cache = AsyncMock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache_getter.return_value = mock_cache

            with patch('core.trigger_interceptor.UserActivityService') as mock_service_class:
                mock_service = AsyncMock()
                mock_service.get_user_state = AsyncMock(return_value="active")
                mock_service.should_supervise = MagicMock(return_value=True)
                mock_service_class.return_value = mock_service

                decision = await interceptor.intercept_trigger(
                    agent_id=supervised_agent.id,
                    trigger_source=TriggerSource.AI_COORDINATOR,
                    trigger_context=trigger_context,
                    user_id=None
                )

                assert decision.execute is True
                assert decision.routing_decision == RoutingDecision.SUPERVISION

    @pytest.mark.asyncio
    async def test_intercept_autonomous_automated(
        self, interceptor, mock_db, autonomous_agent, trigger_context
    ):
        """Test intercept with AUTONOMOUS agent automated trigger"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = autonomous_agent
        mock_db.query.return_value = mock_query

        with patch('core.trigger_interceptor.get_async_governance_cache') as mock_cache_getter:
            mock_cache = AsyncMock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache_getter.return_value = mock_cache

            decision = await interceptor.intercept_trigger(
                agent_id=autonomous_agent.id,
                trigger_source=TriggerSource.WORKFLOW_ENGINE,
                trigger_context=trigger_context,
                user_id=None
            )

            assert decision.execute is True
            assert decision.routing_decision == RoutingDecision.EXECUTION


# ============================================================================
# Test Cache Integration
# ============================================================================

class TestCacheIntegration:
    """Test governance cache integration"""

    @pytest.mark.asyncio
    async def test_cache_hit(self, interceptor, mock_db):
        """Test agent maturity from cache hit"""
        with patch('core.trigger_interceptor.get_async_governance_cache') as mock_cache_getter:
            mock_cache = AsyncMock()
            mock_cache.get = AsyncMock(return_value={
                "status": AgentStatus.AUTONOMOUS.value,
                "confidence": 0.95
            })
            mock_cache_getter.return_value = mock_cache

            status, confidence = await interceptor._get_agent_maturity_cached(
                "agent-001"
            )

            assert status == AgentStatus.AUTONOMOUS.value
            assert confidence == 0.95
            mock_cache.get.assert_called_once_with("agent-001", "maturity")
            mock_db.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss(self, interceptor, mock_db, autonomous_agent):
        """Test agent maturity from database on cache miss"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = autonomous_agent
        mock_db.query.return_value = mock_query

        with patch('core.trigger_interceptor.get_async_governance_cache') as mock_cache_getter:
            mock_cache = AsyncMock()
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()
            mock_cache_getter.return_value = mock_cache

            status, confidence = await interceptor._get_agent_maturity_cached(
                "agent-001"
            )

            assert status == AgentStatus.AUTONOMOUS.value
            assert confidence == 0.95
            mock_cache.get.assert_called_once()
            mock_cache.set.assert_called_once()
            mock_db.query.assert_called_once()


# ============================================================================
# Test TriggerDecision Class
# ============================================================================

class TestTriggerDecisionClass:
    """Test TriggerDecision data class"""

    def test_create_decision_with_all_fields(self):
        """Test creating TriggerDecision with all fields"""
        blocked_ctx = MagicMock(spec=BlockedTriggerContext)
        proposal = MagicMock(spec=AgentProposal)
        session = MagicMock(spec=SupervisionSession)

        decision = TriggerDecision(
            routing_decision=RoutingDecision.SUPERVISION,
            execute=True,
            agent_id="agent-001",
            agent_maturity=AgentStatus.SUPERVISED.value,
            confidence_score=0.8,
            trigger_source=TriggerSource.WORKFLOW_ENGINE,
            blocked_context=blocked_ctx,
            proposal=proposal,
            supervision_session=session,
            reason="Test decision"
        )

        assert decision.routing_decision == RoutingDecision.SUPERVISION
        assert decision.execute is True
        assert decision.agent_id == "agent-001"
        assert decision.confidence_score == 0.8
        assert decision.reason == "Test decision"

    def test_create_decision_minimal_fields(self):
        """Test creating TriggerDecision with minimal fields"""
        decision = TriggerDecision(
            routing_decision=RoutingDecision.EXECUTION,
            execute=True,
            agent_id="agent-001",
            agent_maturity=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95,
            trigger_source=TriggerSource.MANUAL
        )

        assert decision.routing_decision == RoutingDecision.EXECUTION
        assert decision.execute is True
        assert decision.blocked_context is None
        assert decision.proposal is None
        assert decision.supervision_session is None
        assert decision.reason == ""


# ============================================================================
# Test Route to Training Method
# ============================================================================

class TestRouteToTraining:
    """Test route_to_training method"""

    @pytest.mark.asyncio
    async def test_route_creates_training_proposal(
        self, interceptor, mock_db
    ):
        """Test route_to_training creates proposal via service"""
        blocked_trigger = MagicMock(spec=BlockedTriggerContext)
        blocked_trigger.agent_id = "agent-student-001"
        blocked_trigger.trigger_type = "send_email"

        mock_proposal = MagicMock(spec=AgentProposal)
        mock_proposal.id = "proposal-training-001"
        interceptor.training_service.create_training_proposal = AsyncMock(
            return_value=mock_proposal
        )

        result = await interceptor.route_to_training(blocked_trigger)

        assert result == mock_proposal
        assert result.id == "proposal-training-001"
        interceptor.training_service.create_training_proposal.assert_called_once_with(
            blocked_trigger
        )


# ============================================================================
# Test Create Proposal Method
# ============================================================================

class TestCreateProposal:
    """Test create_proposal method"""

    @pytest.mark.asyncio
    async def test_create_intern_proposal(
        self, interceptor, mock_db, intern_agent
    ):
        """Test creating proposal for INTERN agent"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = intern_agent
        mock_db.query.return_value = mock_query

        proposed_action = {"action_type": "send_email", "to": "test@example.com"}
        reasoning = "User requested email to be sent"

        result = await interceptor.create_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={"action": "test"},
            proposed_action=proposed_action,
            reasoning=reasoning
        )

        assert isinstance(result, AgentProposal)
        assert result.agent_id == intern_agent.id
        assert result.proposal_type == ProposalType.ACTION.value
        assert result.status == ProposalStatus.PROPOSED.value
        assert "send_email" in result.description

        # Verify database operations
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called()
        mock_db.refresh.assert_called()

    @pytest.mark.asyncio
    async def test_create_proposal_agent_not_found(self, interceptor, mock_db):
        """Test create_proposal with nonexistent agent"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(ValueError, match="Agent .* not found"):
            await interceptor.create_proposal(
                intern_agent_id="nonexistent-agent",
                trigger_context={},
                proposed_action={},
                reasoning="test"
            )


# ============================================================================
# Test Execute with Supervision Method
# ============================================================================

class TestExecuteWithSupervision:
    """Test execute_with_supervision method"""

    @pytest.mark.asyncio
    async def test_create_supervision_session(
        self, interceptor, mock_db, supervised_agent
    ):
        """Test creating supervision session"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = supervised_agent
        mock_db.query.return_value = mock_query

        trigger_context = {"action": "test_action"}
        user_id = "supervisor-001"

        result = await interceptor.execute_with_supervision(
            trigger_context=trigger_context,
            agent_id=supervised_agent.id,
            user_id=user_id
        )

        assert isinstance(result, SupervisionSession)
        assert result.agent_id == supervised_agent.id
        assert result.supervisor_id == user_id
        assert result.status == SupervisionStatus.RUNNING.value
        assert result.trigger_context == trigger_context

        # Verify database operations
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called()
        mock_db.refresh.assert_called()

    @pytest.mark.asyncio
    async def test_execute_with_supervision_agent_not_found(
        self, interceptor, mock_db
    ):
        """Test execute_with_supervision with nonexistent agent"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(ValueError, match="Agent .* not found"):
            await interceptor.execute_with_supervision(
                trigger_context={},
                agent_id="nonexistent-agent",
                user_id="supervisor-001"
            )
