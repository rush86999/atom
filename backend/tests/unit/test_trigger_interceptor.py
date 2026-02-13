"""
Unit tests for Trigger Interceptor

Tests cover:
- Maturity level determination
- Student agent routing (blocking)
- Intern agent routing (proposals)
- Supervised agent routing (supervision)
- Autonomous agent routing (execution)
- Manual trigger handling
- Training proposal creation
- Trigger decision data structure
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from sqlalchemy.orm import Session

from core.trigger_interceptor import (
    TriggerInterceptor,
    MaturityLevel,
    RoutingDecision,
    TriggerDecision,
    TriggerSource
)
from core.models import (
    AgentRegistry,
    AgentStatus,
    BlockedTriggerContext,
    AgentProposal,
    SupervisionSession,
    ProposalStatus,
    SupervisionStatus
)


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock(spec=Session)
    db.query = MagicMock()
    db.add = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.refresh = Mock()
    db.flush = Mock()
    return db


@pytest.fixture
def interceptor(mock_db):
    """Create trigger interceptor instance."""
    return TriggerInterceptor(mock_db, "workspace_123")


@pytest.fixture
def student_agent():
    """Create STUDENT maturity agent."""
    return AgentRegistry(
        id="student_agent",
        name="Student Agent",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.4
    )


@pytest.fixture
def intern_agent():
    """Create INTERN maturity agent."""
    return AgentRegistry(
        id="intern_agent",
        name="Intern Agent",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6
    )


@pytest.fixture
def supervised_agent():
    """Create SUPERVISED maturity agent."""
    return AgentRegistry(
        id="supervised_agent",
        name="Supervised Agent",
        status=AgentStatus.SUPERVISED.value,
        confidence_score=0.8
    )


@pytest.fixture
def autonomous_agent():
    """Create AUTONOMOUS maturity agent."""
    return AgentRegistry(
        id="autonomous_agent",
        name="Autonomous Agent",
        status=AgentStatus.AUTONOMOUS.value,
        confidence_score=0.95
    )


# ============================================================================
# Maturity Level Determination Tests
# ============================================================================

class TestMaturityLevelDetermination:
    """Tests for maturity level determination logic."""

    def test_student_maturity_below_05(self, interceptor):
        """Test confidence < 0.5 maps to STUDENT."""
        maturity = interceptor._determine_maturity_level(
            AgentStatus.STUDENT.value,
            0.4
        )
        assert maturity == MaturityLevel.STUDENT

    def test_student_maturity_at_boundary(self, interceptor):
        """Test confidence at 0.49 maps to STUDENT."""
        maturity = interceptor._determine_maturity_level(
            AgentStatus.STUDENT.value,
            0.49
        )
        assert maturity == MaturityLevel.STUDENT

    def test_intern_maturity_05_to_07(self, interceptor):
        """Test confidence 0.5-0.7 maps to INTERN."""
        maturity = interceptor._determine_maturity_level(
            AgentStatus.INTERN.value,
            0.6
        )
        assert maturity == MaturityLevel.INTERN

    def test_intern_at_lower_boundary(self, interceptor):
        """Test confidence at 0.5 maps to INTERN."""
        maturity = interceptor._determine_maturity_level(
            AgentStatus.INTERN.value,
            0.5
        )
        assert maturity == MaturityLevel.INTERN

    def test_supervised_maturity_07_to_09(self, interceptor):
        """Test confidence 0.7-0.9 maps to SUPERVISED."""
        maturity = interceptor._determine_maturity_level(
            AgentStatus.SUPERVISED.value,
            0.8
        )
        assert maturity == MaturityLevel.SUPERVISED

    def test_supervised_at_lower_boundary(self, interceptor):
        """Test confidence at 0.7 maps to SUPERVISED."""
        maturity = interceptor._determine_maturity_level(
            AgentStatus.SUPERVISED.value,
            0.7
        )
        assert maturity == MaturityLevel.SUPERVISED

    def test_autonomous_maturity_above_09(self, interceptor):
        """Test confidence > 0.9 maps to AUTONOMOUS."""
        maturity = interceptor._determine_maturity_level(
            AgentStatus.AUTONOMOUS.value,
            0.95
        )
        assert maturity == MaturityLevel.AUTONOMOUS

    def test_autonomous_at_boundary(self, interceptor):
        """Test confidence at 0.9 maps to AUTONOMOUS."""
        maturity = interceptor._determine_maturity_level(
            AgentStatus.AUTONOMOUS.value,
            0.9
        )
        assert maturity == MaturityLevel.AUTONOMOUS


# ============================================================================
# Student Agent Routing Tests
# ============================================================================

class TestStudentAgentRouting:
    """Tests for STUDENT agent trigger blocking."""

    @pytest.mark.asyncio
    async def test_student_blocked_for_automated_trigger(self, interceptor, mock_db, student_agent):
        """Test STUDENT agents are blocked for automated triggers."""
        # Mock the agent query
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = student_agent
        mock_db.query.return_value = mock_query
        
        # Mock training service
        with patch.object(interceptor.training_service, 'create_training_proposal', new=AsyncMock()) as mock_create:
            mock_create.return_value = AgentProposal(
                id="proposal_123",
                agent_id="student_agent",
                proposal_type="training"
            )
            
            decision = await interceptor.intercept_trigger(
                agent_id="student_agent",
                trigger_source=TriggerSource.DATA_SYNC,
                trigger_context={"action": "sync_data"}
            )

            assert decision.execute is False
            assert decision.routing_decision == RoutingDecision.TRAINING

    @pytest.mark.asyncio
    async def test_student_creates_blocked_trigger_context(self, interceptor, mock_db, student_agent):
        """Test STUDENT routing creates blocked trigger context."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = student_agent
        mock_db.query.return_value = mock_query
        
        # Mock training service
        with patch.object(interceptor.training_service, 'create_training_proposal', new=AsyncMock()) as mock_create:
            mock_create.return_value = AgentProposal(
                id="proposal_123",
                agent_id="student_agent",
                proposal_type="training"
            )
            
            decision = await interceptor.intercept_trigger(
                agent_id="student_agent",
                trigger_source=TriggerSource.WORKFLOW_ENGINE,
                trigger_context={"workflow_id": "wf_123"}
            )

            assert decision.blocked_context is not None

    @pytest.mark.asyncio
    async def test_student_blocked_for_all_automated_sources(self, interceptor, mock_db, student_agent):
        """Test STUDENT blocked for all automated trigger sources."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = student_agent
        mock_db.query.return_value = mock_query
        
        # Mock training service
        with patch.object(interceptor.training_service, 'create_training_proposal', new=AsyncMock()) as mock_create:
            mock_create.return_value = AgentProposal(
                id="proposal_123",
                agent_id="student_agent",
                proposal_type="training"
            )
            
            automated_sources = [
                TriggerSource.DATA_SYNC,
                TriggerSource.WORKFLOW_ENGINE,
                TriggerSource.AI_COORDINATOR
            ]

            for source in automated_sources:
                decision = await interceptor.intercept_trigger(
                    agent_id="student_agent",
                    trigger_source=source,
                    trigger_context={}
                )

                assert decision.execute is False


# ============================================================================
# Intern Agent Routing Tests
# ============================================================================

class TestInternAgentRouting:
    """Tests for INTERN agent proposal routing."""

    @pytest.mark.asyncio
    async def test_intern_generates_proposal(self, interceptor, mock_db, intern_agent):
        """Test INTERN agents generate proposals for automated triggers."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = intern_agent
        mock_db.query.return_value = mock_query
        
        decision = await interceptor.intercept_trigger(
            agent_id="intern_agent",
            trigger_source=TriggerSource.AI_COORDINATOR,
            trigger_context={"action": "coordinate"}
        )

        assert decision.execute is False
        assert decision.routing_decision == RoutingDecision.PROPOSAL
        assert decision.blocked_context is not None

    @pytest.mark.asyncio
    async def test_intern_blocked_for_all_automated_sources(self, interceptor, mock_db, intern_agent):
        """Test INTERN generates proposal for all automated trigger sources."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = intern_agent
        mock_db.query.return_value = mock_query
        
        automated_sources = [
            TriggerSource.DATA_SYNC,
            TriggerSource.WORKFLOW_ENGINE,
            TriggerSource.AI_COORDINATOR
        ]

        for source in automated_sources:
            decision = await interceptor.intercept_trigger(
                agent_id="intern_agent",
                trigger_source=source,
                trigger_context={}
            )

            assert decision.routing_decision == RoutingDecision.PROPOSAL


# ============================================================================
# Supervised Agent Routing Tests
# ============================================================================

class TestSupervisedAgentRouting:
    """Tests for SUPERVISED agent supervision routing."""

    @pytest.mark.asyncio
    async def test_supervised_requires_supervision(self, interceptor, mock_db, supervised_agent):
        """Test SUPERVISED agents require supervision for automated triggers."""
        # Add user_id to supervised_agent for the test
        supervised_agent.user_id = "user_123"
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = supervised_agent
        mock_db.query.return_value = mock_query

        # Mock user activity service and supervised queue service
        with patch('core.user_activity_service.UserActivityService') as mock_uas, \
             patch('core.supervised_queue_service.SupervisedQueueService') as mock_sqs:
            mock_uas_instance = MagicMock()
            mock_uas_instance.get_user_state = AsyncMock(return_value="active")
            mock_uas_instance.should_supervise = Mock(return_value=True)
            mock_uas.return_value = mock_uas_instance

            mock_sqs_instance = MagicMock()
            mock_sqs_instance.enqueue_execution = AsyncMock()
            mock_sqs.return_value = mock_sqs_instance

            decision = await interceptor.intercept_trigger(
                agent_id="supervised_agent",
                trigger_source=TriggerSource.DATA_SYNC,
                trigger_context={"action": "sync"}
            )

            assert decision.execute is True
            assert decision.routing_decision == RoutingDecision.SUPERVISION

    @pytest.mark.asyncio
    async def test_supervised_for_all_automated_sources(self, interceptor, mock_db, supervised_agent):
        """Test SUPERVISED supervision for all automated trigger sources."""
        supervised_agent.user_id = "user_123"
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = supervised_agent
        mock_db.query.return_value = mock_query

        # Mock user activity service and supervised queue service
        with patch('core.user_activity_service.UserActivityService') as mock_uas, \
             patch('core.supervised_queue_service.SupervisedQueueService') as mock_sqs:
            mock_uas_instance = MagicMock()
            mock_uas_instance.get_user_state = AsyncMock(return_value="active")
            mock_uas_instance.should_supervise = Mock(return_value=True)
            mock_uas.return_value = mock_uas_instance

            mock_sqs_instance = MagicMock()
            mock_sqs_instance.enqueue_execution = AsyncMock()
            mock_sqs.return_value = mock_sqs_instance

            automated_sources = [
                TriggerSource.DATA_SYNC,
                TriggerSource.WORKFLOW_ENGINE,
                TriggerSource.AI_COORDINATOR
            ]

            for source in automated_sources:
                decision = await interceptor.intercept_trigger(
                    agent_id="supervised_agent",
                    trigger_source=source,
                    trigger_context={}
                )

                assert decision.routing_decision == RoutingDecision.SUPERVISION


# ============================================================================
# Autonomous Agent Routing Tests
# ============================================================================

class TestAutonomousAgentRouting:
    """Tests for AUTONOMOUS agent execution."""

    @pytest.mark.asyncio
    async def test_autonomous_allowed_full_execution(self, interceptor, mock_db, autonomous_agent):
        """Test AUTONOMOUS agents allowed full execution."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = autonomous_agent
        mock_db.query.return_value = mock_query
        
        decision = await interceptor.intercept_trigger(
            agent_id="autonomous_agent",
            trigger_source=TriggerSource.AI_COORDINATOR,
            trigger_context={"action": "coordinate"}
        )

        assert decision.execute is True
        assert decision.routing_decision == RoutingDecision.EXECUTION

    @pytest.mark.asyncio
    async def test_autonomous_for_all_trigger_sources(self, interceptor, mock_db, autonomous_agent):
        """Test AUTONOMOUS execution for all trigger sources."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = autonomous_agent
        mock_db.query.return_value = mock_query
        
        all_sources = [
            TriggerSource.MANUAL,
            TriggerSource.DATA_SYNC,
            TriggerSource.WORKFLOW_ENGINE,
            TriggerSource.AI_COORDINATOR
        ]

        for source in all_sources:
            decision = await interceptor.intercept_trigger(
                agent_id="autonomous_agent",
                trigger_source=source,
                trigger_context={}
            )

            assert decision.execute is True


# ============================================================================
# Manual Trigger Handling Tests
# ============================================================================

class TestManualTriggerHandling:
    """Tests for manual trigger handling."""

    @pytest.mark.asyncio
    async def test_manual_trigger_always_allowed(self, interceptor, mock_db, student_agent):
        """Test manual triggers are always allowed regardless of maturity."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = student_agent
        mock_db.query.return_value = mock_query
        
        decision = await interceptor.intercept_trigger(
            agent_id="student_agent",
            trigger_source=TriggerSource.MANUAL,
            trigger_context={"action": "manual_action"},
            user_id="user_123"
        )

        assert decision.execute is True
        assert decision.routing_decision == RoutingDecision.EXECUTION

    @pytest.mark.asyncio
    async def test_manual_trigger_with_student_includes_warning(self, interceptor, mock_db, student_agent):
        """Test manual trigger for STUDENT includes warning."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = student_agent
        mock_db.query.return_value = mock_query
        
        decision = await interceptor.intercept_trigger(
            agent_id="student_agent",
            trigger_source=TriggerSource.MANUAL,
            trigger_context={},
            user_id="user_123"
        )

        assert "warning" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_manual_trigger_with_intern_includes_note(self, interceptor, mock_db, intern_agent):
        """Test manual trigger for INTERN includes note."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = intern_agent
        mock_db.query.return_value = mock_query
        
        decision = await interceptor.intercept_trigger(
            agent_id="intern_agent",
            trigger_source=TriggerSource.MANUAL,
            trigger_context={},
            user_id="user_123"
        )

        assert "note" in decision.reason.lower() or "learning mode" in decision.reason.lower()


# ============================================================================
# Routing Decision Tests
# ============================================================================

class TestTriggerDecision:
    """Tests for TriggerDecision data structure."""

    def test_trigger_decision_all_fields(self):
        """Test TriggerDecision contains all required fields."""
        decision = TriggerDecision(
            routing_decision=RoutingDecision.EXECUTION,
            execute=True,
            agent_id="agent_123",
            agent_maturity=MaturityLevel.AUTONOMOUS.value,
            confidence_score=0.95,
            trigger_source=TriggerSource.MANUAL,
            reason="Test decision"
        )

        assert decision.routing_decision == RoutingDecision.EXECUTION
        assert decision.execute is True
        assert decision.agent_id == "agent_123"
        assert decision.agent_maturity == MaturityLevel.AUTONOMOUS.value
        assert decision.confidence_score == 0.95
        assert decision.trigger_source == TriggerSource.MANUAL

    def test_trigger_decision_with_blocked_context(self):
        """Test TriggerDecision with blocked context."""
        blocked = BlockedTriggerContext(
            id="blocked_123",
            agent_id="agent_123",
            agent_name="Test Agent",
            agent_maturity_at_block="student",
            confidence_score_at_block=0.4,
            trigger_type="test",
            trigger_source="workflow",
            trigger_context={},
            routing_decision="training",
            block_reason="Test"
        )

        decision = TriggerDecision(
            routing_decision=RoutingDecision.TRAINING,
            execute=False,
            agent_id="agent_123",
            agent_maturity=MaturityLevel.STUDENT.value,
            confidence_score=0.4,
            trigger_source=TriggerSource.WORKFLOW_ENGINE,
            blocked_context=blocked
        )

        assert decision.blocked_context is not None
        assert decision.blocked_context.id == "blocked_123"

    def test_trigger_decision_with_proposal(self):
        """Test TriggerDecision with proposal."""
        proposal = AgentProposal(
            id="proposal_123",
            agent_id="agent_123",
            agent_name="Test Agent",
            proposal_type="action",
            title="Action Proposal",
            description="Test proposal",
            status=ProposalStatus.PROPOSED.value,
            proposed_by="agent_123"
        )

        decision = TriggerDecision(
            routing_decision=RoutingDecision.PROPOSAL,
            execute=False,
            agent_id="agent_123",
            agent_maturity=MaturityLevel.INTERN.value,
            confidence_score=0.6,
            trigger_source=TriggerSource.AI_COORDINATOR,
            proposal=proposal
        )

        assert decision.proposal is not None
        assert decision.proposal.id == "proposal_123"

    def test_trigger_decision_with_supervision_session(self):
        """Test TriggerDecision with supervision session."""
        supervision = SupervisionSession(
            id="supervision_123",
            agent_id="agent_123",
            agent_name="Test Agent",
            workspace_id="workspace_123",
            trigger_context={},
            status=SupervisionStatus.RUNNING.value,
            supervisor_id="user_123"
        )

        decision = TriggerDecision(
            routing_decision=RoutingDecision.SUPERVISION,
            execute=True,
            agent_id="agent_123",
            agent_maturity=MaturityLevel.SUPERVISED.value,
            confidence_score=0.8,
            trigger_source=TriggerSource.DATA_SYNC,
            supervision_session=supervision
        )

        assert decision.supervision_session is not None
        assert decision.supervision_session.id == "supervision_123"


# ============================================================================
# Route to Training Tests
# ============================================================================

class TestRouteToTraining:
    """Tests for routing to training."""

    @pytest.mark.asyncio
    async def test_route_to_training_creates_proposal(self, interceptor, mock_db):
        """Test routing to training creates proposal via training service."""
        blocked_trigger = BlockedTriggerContext(
            id="blocked_123",
            agent_id="student_agent",
            agent_name="Student Agent",
            agent_maturity_at_block="student",
            confidence_score_at_block=0.4,
            trigger_type="workflow",
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_context={},
            routing_decision="training",
            block_reason="STUDENT blocked"
        )

        with patch.object(interceptor.training_service, 'create_training_proposal', new=AsyncMock()) as mock_create:
            mock_create.return_value = AgentProposal(
                id="proposal_123",
                agent_id="student_agent",
                agent_name="Student Agent",
                proposal_type="training",
                title="Training Proposal",
                description="Test training proposal",
                status=ProposalStatus.PROPOSED.value,
                proposed_by="system"
            )

            proposal = await interceptor.route_to_training(blocked_trigger)

            assert proposal.id == "proposal_123"
            assert proposal.proposal_type == "training"
            mock_create.assert_called_once_with(blocked_trigger)


# ============================================================================
# Create Proposal Tests
# ============================================================================

class TestCreateProposal:
    """Tests for action proposal creation."""

    @pytest.mark.asyncio
    async def test_create_proposal_for_intern_action(self, interceptor, mock_db, intern_agent):
        """Test creating proposal for INTERN agent action."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = intern_agent
        mock_db.query.return_value = mock_query

        proposal = await interceptor.create_proposal(
            intern_agent_id="intern_agent",
            trigger_context={"action": "delete"},
            proposed_action={"type": "delete", "target": "resource"},
            reasoning="INTERN agent proposing delete action"
        )

        assert proposal.agent_id == "intern_agent"
        assert proposal.proposal_type == "action"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_proposal_for_nonexistent_agent_raises(self, interceptor, mock_db):
        """Test proposal creation fails for nonexistent agent."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(ValueError):
            await interceptor.create_proposal(
                intern_agent_id="nonexistent",
                trigger_context={},
                proposed_action={},
                reasoning="test"
            )

    @pytest.mark.asyncio
    async def test_create_proposal_includes_reasoning(self, interceptor, mock_db, intern_agent):
        """Test proposal includes reasoning."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = intern_agent
        mock_db.query.return_value = mock_query

        proposal = await interceptor.create_proposal(
            intern_agent_id="intern_agent",
            trigger_context={},
            proposed_action={},
            reasoning="This is reasoning for proposal"
        )

        assert "reasoning" in proposal.description.lower() or "this is reasoning" in proposal.description.lower()


# ============================================================================
# Execute with Supervision Tests
# ============================================================================

class TestExecuteWithSupervision:
    """Tests for execution with supervision."""

    @pytest.mark.asyncio
    async def test_execute_with_supervision_creates_session(self, interceptor, mock_db, supervised_agent):
        """Test supervised execution creates supervision session."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = supervised_agent
        mock_db.query.return_value = mock_query

        trigger_context = {"action": "update"}
        session = await interceptor.execute_with_supervision(
            trigger_context=trigger_context,
            agent_id="supervised_agent",
            user_id="user_123"
        )

        assert session.agent_id == "supervised_agent"
        assert session.status == SupervisionStatus.RUNNING.value
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_supervision_for_nonexistent_agent_raises(self, interceptor, mock_db):
        """Test supervised execution fails for nonexistent agent."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(ValueError):
            await interceptor.execute_with_supervision(
                trigger_context={},
                agent_id="nonexistent",
                user_id="user_123"
            )


# ============================================================================
# Allow Execution Tests
# ============================================================================

class TestAllowExecution:
    """Tests for allowing execution."""

    @pytest.mark.asyncio
    async def test_allow_execution_returns_context(self, interceptor, mock_db, autonomous_agent):
        """Test allowing execution returns execution context."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = autonomous_agent
        mock_db.query.return_value = mock_query

        trigger_context = {"action": "execute"}

        result = await interceptor.allow_execution(
            agent_id="autonomous_agent",
            trigger_context=trigger_context
        )

        assert result["allowed"] is True
        assert result["agent_id"] == "autonomous_agent"

    @pytest.mark.asyncio
    async def test_allow_execution_for_nonexistent_agent_raises(self, interceptor, mock_db):
        """Test allow execution fails for nonexistent agent."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(ValueError):
            await interceptor.allow_execution(
                agent_id="nonexistent",
                trigger_context={}
            )


# ============================================================================
# Agent Maturity Cache Tests
# ============================================================================

class TestGetAgentMaturityCached:
    """Tests for cached agent maturity retrieval."""

    @pytest.mark.asyncio
    async def test_get_agent_maturity_cached_returns_tuple(self, interceptor):
        """Test cached retrieval returns (status, confidence) tuple."""
        agent = AgentRegistry(
            id="agent_123",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        interceptor.db.query.return_value = mock_query
        
        # Mock cache
        with patch('core.trigger_interceptor.get_async_governance_cache') as mock_cache_func:
            cache = MagicMock()
            cache.get = AsyncMock(return_value=None)
            cache.set = AsyncMock()
            mock_cache_func.return_value = cache

            status, confidence = await interceptor._get_agent_maturity_cached("agent_123")

            assert status == AgentStatus.INTERN.value
            assert confidence == 0.6
            cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_agent_maturity_cached_from_cache(self, interceptor):
        """Test cache hit returns cached value."""
        # Mock cache
        with patch('core.trigger_interceptor.get_async_governance_cache') as mock_cache_func:
            cache = MagicMock()
            cache.get = AsyncMock(return_value={"status": AgentStatus.SUPERVISED.value, "confidence": 0.8})
            mock_cache_func.return_value = cache

            status, confidence = await interceptor._get_agent_maturity_cached("agent_123")

            assert status == AgentStatus.SUPERVISED.value
            assert confidence == 0.8

    @pytest.mark.asyncio
    async def test_get_agent_maturity_cached_raises_on_not_found(self, interceptor, mock_db):
        """Test cached retrieval raises when agent not found."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with patch('core.trigger_interceptor.get_async_governance_cache') as mock_cache_func:
            cache = MagicMock()
            cache.get = AsyncMock(return_value=None)
            mock_cache_func.return_value = cache

            with pytest.raises(ValueError):
                await interceptor._get_agent_maturity_cached("nonexistent")


# ============================================================================
# Workspace Tests
# ============================================================================

class TestWorkspace:
    """Tests for workspace configuration."""

    def test_interceptor_has_workspace_id(self, interceptor):
        """Test interceptor stores workspace_id."""
        assert interceptor.workspace_id == "workspace_123"

    def test_interceptor_has_training_service(self, interceptor):
        """Test interceptor has training service."""
        assert interceptor.training_service is not None


# ============================================================================
# Maturity Level Enum Tests
# ============================================================================

class TestMaturityLevelEnum:
    """Tests for MaturityLevel enum values."""

    def test_maturity_level_student_value(self):
        """Test STUDENT maturity level value."""
        assert MaturityLevel.STUDENT == "student"

    def test_maturity_level_intern_value(self):
        """Test INTERN maturity level value."""
        assert MaturityLevel.INTERN == "intern"

    def test_maturity_level_supervised_value(self):
        """Test SUPERVISED maturity level value."""
        assert MaturityLevel.SUPERVISED == "supervised"

    def test_maturity_level_autonomous_value(self):
        """Test AUTONOMOUS maturity level value."""
        assert MaturityLevel.AUTONOMOUS == "autonomous"


# ============================================================================
# Routing Decision Enum Tests
# ============================================================================

class TestRoutingDecisionEnum:
    """Tests for RoutingDecision enum values."""

    def test_routing_decision_training_value(self):
        """Test TRAINING routing decision value."""
        assert RoutingDecision.TRAINING == "training"

    def test_routing_decision_proposal_value(self):
        """Test PROPOSAL routing decision value."""
        assert RoutingDecision.PROPOSAL == "proposal"

    def test_routing_decision_supervision_value(self):
        """Test SUPERVISION routing decision value."""
        assert RoutingDecision.SUPERVISION == "supervision"

    def test_routing_decision_execution_value(self):
        """Test EXECUTION routing decision value."""
        assert RoutingDecision.EXECUTION == "execution"
