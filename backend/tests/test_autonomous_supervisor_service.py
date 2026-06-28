"""
Comprehensive test suite for AutonomousSupervisorService

Tests autonomous agent fallback supervision when users are unavailable.
AUTONOMOUS agents supervise INTERN and SUPERVISED agents via LLM-based analysis.

Target File: core/autonomous_supervisor_service.py (551 lines)
Test Coverage: 25-30 tests across 4 test classes
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from datetime import datetime
from sqlalchemy.orm import Session

from core.autonomous_supervisor_service import (
    AutonomousSupervisorService,
    ProposalReview,
    SupervisionEvent
)
from core.models import (
    AgentRegistry,
    AgentProposal,
    AgentExecution,
    AgentStatus,
    ProposalStatus,
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock(spec=Session)
    return db


@pytest.fixture
def intern_agent():
    """Mock INTERN agent needing supervision."""
    return AgentRegistry(
        id="intern-001",
        name="Data Analyst Intern",
        category="data_analysis",
        confidence_score=0.65,
        status=AgentStatus.INTERN.value,
        diversity_profile={"risk_profile": "conservative", "latency_focus": False}
    )


@pytest.fixture
def autonomous_supervisor():
    """Mock AUTONOMOUS supervisor agent."""
    return AgentRegistry(
        id="auto-001",
        name="Senior Data Analyst",
        category="data_analysis",
        confidence_score=0.95,
        status=AgentStatus.AUTONOMOUS.value,
        diversity_profile={"risk_profile": "balanced", "latency_focus": True}
    )


@pytest.fixture
def agent_proposal():
    """Mock agent proposal."""
    proposal = AgentProposal(
        id="prop-001",
        agent_id="intern-001",
        proposed_action={
            "action_type": "canvas_present",
            "canvas_type": "chart",
            "data": {"labels": ["Q1", "Q2"], "values": [100, 200]}
        },
        reasoning="Present sales data as chart"
    )
    proposal.status = ProposalStatus.PENDING_APPROVAL.value
    return proposal


@pytest.fixture
def service(mock_db):
    """AutonomousSupervisorService instance."""
    return AutonomousSupervisorService(mock_db)


# ============================================================================
# Test Class 1: Supervisor Discovery
# ============================================================================

class TestSupervisorDiscovery:
    """Tests for finding autonomous supervisors."""

    @pytest.mark.asyncio
    async def test_find_autonomous_supervisor_with_category_match(
        self, service, intern_agent, autonomous_supervisor
    ):
        """Test finding supervisor with matching category."""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [autonomous_supervisor]
        service.db.query.return_value = mock_query

        # Act
        result = await service.find_autonomous_supervisor(
            intern_agent=intern_agent,
            category="data_analysis"
        )

        # Assert
        assert result is not None
        assert result.id == "auto-001"
        assert result.category == "data_analysis"
        assert result.confidence_score >= 0.9

    @pytest.mark.asyncio
    async def test_find_autonomous_supervisor_confidence_filtering(
        self, service, intern_agent
    ):
        """Test finding supervisor filters by confidence >= 0.9."""
        # Arrange
        low_confidence = AgentRegistry(
            id="auto-002",
            name="Junior Analyst",
            category="data_analysis",
            confidence_score=0.85,  # Below threshold
            status=AgentStatus.AUTONOMOUS.value
        )
        high_confidence = AgentRegistry(
            id="auto-001",
            name="Senior Analyst",
            category="data_analysis",
            confidence_score=0.95,
            status=AgentStatus.AUTONOMOUS.value
        )

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [high_confidence]
        service.db.query.return_value = mock_query

        # Act
        result = await service.find_autonomous_supervisor(
            intern_agent=intern_agent
        )

        # Assert
        assert result is not None
        assert result.confidence_score >= 0.9
        assert result.id == "auto-001"

    @pytest.mark.asyncio
    async def test_find_autonomous_supervisor_no_supervisor_available(
        self, service, intern_agent
    ):
        """Test behavior when no supervisor available."""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        service.db.query.return_value = mock_query

        # Act
        result = await service.find_autonomous_supervisor(
            intern_agent=intern_agent
        )

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_find_autonomous_supervisor_adversarial_mode(
        self, service, intern_agent, autonomous_supervisor
    ):
        """Test adversarial mode prioritizes diversity mismatch."""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [autonomous_supervisor]
        service.db.query.return_value = mock_query

        # Act
        result = await service.find_autonomous_supervisor(
            intern_agent=intern_agent,
            adversarial=True
        )

        # Assert
        assert result is not None
        # Adversarial mode should find supervisor with different diversity_profile

    @pytest.mark.asyncio
    async def test_find_autonomous_supervisor_same_category_preference(
        self, service, intern_agent, autonomous_supervisor
    ):
        """Test preference for same category as intern agent."""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [autonomous_supervisor]
        service.db.query.return_value = mock_query

        # Act
        result = await service.find_autonomous_supervisor(
            intern_agent=intern_agent
        )

        # Assert
        assert result is not None
        assert result.category == intern_agent.category

    @pytest.mark.asyncio
    async def test_find_autonomous_supervisor_highest_confidence_selected(
        self, service, intern_agent
    ):
        """Test highest confidence supervisor selected when multiple available."""
        # Arrange
        supervisors = [
            AgentRegistry(
                id=f"auto-{i:03d}",
                name=f"Supervisor {i}",
                category="data_analysis",
                confidence_score=0.90 + (i * 0.01),
                status=AgentStatus.AUTONOMOUS.value
            )
            for i in range(1, 6)
        ]

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = supervisors
        service.db.query.return_value = mock_query

        # Act
        result = await service.find_autonomous_supervisor(
            intern_agent=intern_agent
        )

        # Assert
        assert result is not None
        assert result.confidence_score == max(s.confidence_score for s in supervisors)


# ============================================================================
# Test Class 2: Proposal Review
# ============================================================================

class TestProposalReview:
    """Tests for LLM-based proposal review."""

    @pytest.mark.asyncio
    async def test_review_proposal_safe_approval(
        self, service, agent_proposal, autonomous_supervisor
    ):
        """Test proposal review with safe action type."""
        # Arrange
        agent_proposal.proposed_action = {"action_type": "canvas_present"}

        # Act
        review = await service.review_proposal(
            proposal=agent_proposal,
            supervisor=autonomous_supervisor
        )

        # Assert
        assert isinstance(review, ProposalReview)
        assert review.risk_level == "safe"
        assert review.approved is True
        assert review.reasoning is not None

    @pytest.mark.asyncio
    async def test_review_proposal_high_risk_rejection(
        self, service, agent_proposal, autonomous_supervisor
    ):
        """Test proposal review rejects high-risk actions."""
        # Arrange
        agent_proposal.proposed_action = {"action_type": "device_command"}
        low_confidence_supervisor = AgentRegistry(
            id="auto-002",
            name="Low Confidence Supervisor",
            category="device",
            confidence_score=0.92,  # Below 0.95 threshold
            status=AgentStatus.AUTONOMOUS.value
        )

        # Act
        review = await service.review_proposal(
            proposal=agent_proposal,
            supervisor=low_confidence_supervisor
        )

        # Assert
        assert isinstance(review, ProposalReview)
        assert review.risk_level == "high"
        # High-risk actions require >=0.95 confidence
        assert review.approved is False or review.confidence_score < 0.95

    @pytest.mark.asyncio
    async def test_review_proposal_medium_risk_conditional_approval(
        self, service, agent_proposal, autonomous_supervisor
    ):
        """Test proposal review with medium risk and conditional approval."""
        # Arrange
        agent_proposal.proposed_action = {"action_type": "browser_automate"}

        # Act
        review = await service.review_proposal(
            proposal=agent_proposal,
            supervisor=autonomous_supervisor
        )

        # Assert
        assert isinstance(review, ProposalReview)
        assert review.risk_level == "medium"
        # Medium-risk requires >=0.85 confidence and >=0.90 supervisor confidence
        assert review.confidence_score is not None

    @pytest.mark.asyncio
    async def test_review_proposal_confidence_score_calculation(
        self, service, agent_proposal, autonomous_supervisor
    ):
        """Test confidence score calculation based on action type."""
        # Arrange
        agent_proposal.proposed_action = {"action_type": "canvas_present"}

        # Act
        review = await service.review_proposal(
            proposal=agent_proposal,
            supervisor=autonomous_supervisor
        )

        # Assert
        assert isinstance(review, ProposalReview)
        assert isinstance(review.confidence_score, float)
        assert 0.0 <= review.confidence_score <= 1.0

    @pytest.mark.asyncio
    async def test_review_proposal_suggested_modifications_generation(
        self, service, agent_proposal, autonomous_supervisor, mock_db
    ):
        """Test suggested modifications can be generated."""
        # Arrange
        agent_proposal.proposed_action = {"action_type": "canvas_present"}

        # Mock world model
        with patch('core.autonomous_supervisor_service.WorldModelService') as mock_world_model:
            mock_world_model.return_value.get_experience_statistics = AsyncMock(
                return_value={"success_rate": 0.85}
            )

            # Act
            review = await service.review_proposal(
                proposal=agent_proposal,
                supervisor=autonomous_supervisor
            )

            # Assert
            assert isinstance(review, ProposalReview)
            assert isinstance(review.suggested_modifications, list)

    @pytest.mark.asyncio
    async def test_review_proposal_llm_analysis_integration(
        self, service, agent_proposal, autonomous_supervisor
    ):
        """Test LLM-based analysis integration."""
        # Arrange
        agent_proposal.proposed_action = {
            "action_type": "workflow_trigger",
            "workflow_id": "daily-report"
        }
        agent_proposal.reasoning = "Execute daily sales report workflow"

        # Mock world model
        with patch('core.autonomous_supervisor_service.WorldModelService') as mock_world_model:
            mock_world_model.return_value.get_experience_statistics = AsyncMock(
                return_value={"success_rate": 0.90}
            )

            # Act
            review = await service.review_proposal(
                proposal=agent_proposal,
                supervisor=autonomous_supervisor
            )

            # Assert
            assert isinstance(review, ProposalReview)
            assert review.reasoning is not None
            assert "workflow_trigger" in review.reasoning or "safe" in review.risk_level


# ============================================================================
# Test Class 3: Execution Monitoring
# ============================================================================

class TestExecutionMonitoring:
    """Tests for real-time execution monitoring."""

    @pytest.mark.asyncio
    async def test_monitor_execution_safe_operations(
        self, service, autonomous_supervisor, mock_db
    ):
        """Test monitoring safe operations completes successfully."""
        # Arrange
        execution_id = "exec-001"
        execution = AgentExecution(
            id=execution_id,
            agent_id="intern-001",
            status="completed",
            duration_seconds=5.0,
            output_summary="Chart presented successfully"
        )

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = execution
        mock_db.query.return_value = mock_query

        # Act
        events = []
        async for event in service.monitor_execution(
            execution_id=execution_id,
            supervisor=autonomous_supervisor
        ):
            events.append(event)
            if event.event_type in ["execution_completed", "error"]:
                break

        # Assert
        assert len(events) > 0
        assert events[0].event_type == "monitoring_started"
        assert any(e.event_type == "execution_completed" for e in events)

    @pytest.mark.asyncio
    async def test_monitor_execution_detecting_anomalies(
        self, service, autonomous_supervisor, mock_db
    ):
        """Test monitoring detects anomalies during execution."""
        # Arrange
        execution_id = "exec-002"
        execution = AgentExecution(
            id=execution_id,
            agent_id="intern-001",
            status="running"
        )

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = execution
        mock_db.query.return_value = mock_query

        # Act
        events = []
        async for event in service.monitor_execution(
            execution_id=execution_id,
            supervisor=autonomous_supervisor
        ):
            events.append(event)
            if len(events) > 2:  # Limit iterations for test
                break

        # Assert
        assert len(events) > 0
        assert events[0].event_type == "monitoring_started"

    @pytest.mark.asyncio
    async def test_monitor_execution_real_time_event_generation(
        self, service, autonomous_supervisor, mock_db
    ):
        """Test real-time event generation during monitoring."""
        # Arrange
        execution_id = "exec-003"
        execution = AgentExecution(
            id=execution_id,
            agent_id="intern-001",
            status="failed",
            error_message="Timeout exceeded"
        )

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = execution
        mock_db.query.return_value = mock_query

        # Act
        events = []
        async for event in service.monitor_execution(
            execution_id=execution_id,
            supervisor=autonomous_supervisor
        ):
            events.append(event)
            if event.event_type in ["execution_failed", "error"]:
                break

        # Assert
        assert len(events) > 0
        assert events[0].event_type == "monitoring_started"
        assert any(e.event_type == "execution_failed" for e in events)

    @pytest.mark.asyncio
    async def test_monitor_execution_supervision_event_creation(
        self, service, autonomous_supervisor
    ):
        """Test SupervisionEvent objects are created correctly."""
        # Arrange
        execution_id = "exec-004"

        # Act
        events = []
        async for event in service.monitor_execution(
            execution_id=execution_id,
            supervisor=autonomous_supervisor
        ):
            events.append(event)
            if len(events) > 1:
                break

        # Assert
        assert len(events) > 0
        event = events[0]
        assert isinstance(event, SupervisionEvent)
        assert event.event_type in ["monitoring_started", "error"]
        assert isinstance(event.timestamp, datetime)
        assert isinstance(event.data, dict)

    @pytest.mark.asyncio
    async def test_monitor_execution_intervention_triggers(
        self, service, autonomous_supervisor, mock_db
    ):
        """Test intervention triggers based on execution concerns."""
        # Arrange
        execution_id = "exec-005"
        execution = AgentExecution(
            id=execution_id,
            agent_id="intern-001",
            status="running"
        )

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = execution
        mock_db.query.return_value = mock_query

        # Act
        events = []
        async for event in service.monitor_execution(
            execution_id=execution_id,
            supervisor=autonomous_supervisor
        ):
            events.append(event)
            if len(events) > 3:
                break

        # Assert
        assert len(events) > 0
        # Events should include monitoring_started

    @pytest.mark.asyncio
    async def test_monitor_execution_event_aggregation(
        self, service, autonomous_supervisor, mock_db
    ):
        """Test event aggregation over monitoring duration."""
        # Arrange
        execution_id = "exec-006"
        execution = AgentExecution(
            id=execution_id,
            agent_id="intern-001",
            status="running"
        )

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = execution
        mock_db.query.return_value = mock_query

        # Act
        events = []
        async for event in service.monitor_execution(
            execution_id=execution_id,
            supervisor=autonomous_supervisor
        ):
            events.append(event)
            if len(events) >= 5:
                break

        # Assert
        assert len(events) >= 5
        assert all(isinstance(e, SupervisionEvent) for e in events)


# ============================================================================
# Test Class 4: Fallback Supervision
# ============================================================================

class TestFallbackSupervision:
    """Tests for autonomous fallback supervision behavior."""

    @pytest.mark.asyncio
    async def test_autonomous_supervision_when_human_unavailable(
        self, service, intern_agent, autonomous_supervisor, agent_proposal
    ):
        """Test autonomous supervision when human supervisor unavailable."""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [autonomous_supervisor]
        service.db.query.return_value = mock_query

        # Act
        supervisor = await service.find_autonomous_supervisor(
            intern_agent=intern_agent
        )

        # Assert
        assert supervisor is not None
        assert supervisor.status == AgentStatus.AUTONOMOUS.value

    @pytest.mark.asyncio
    async def test_fallback_to_human_supervisor(
        self, service, intern_agent
    ):
        """Test fallback when no autonomous supervisor available."""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        service.db.query.return_value = mock_query

        # Act
        supervisor = await service.find_autonomous_supervisor(
            intern_agent=intern_agent
        )

        # Assert
        assert supervisor is None  # Should return None to trigger human fallback

    @pytest.mark.asyncio
    async def test_supervision_status_tracking(
        self, service, autonomous_supervisor, agent_proposal, mock_db
    ):
        """Test supervision status is tracked correctly."""
        # Arrange
        agent_proposal.id = "prop-002"
        agent_proposal.status = ProposalStatus.PENDING_APPROVAL.value

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = agent_proposal
        mock_db.query.return_value = mock_query

        # Act
        review = ProposalReview(
            approved=True,
            confidence_score=0.90,
            risk_level="safe",
            reasoning="Safe action"
        )

        result = await service.approve_proposal(
            proposal_id="prop-002",
            supervisor_id="auto-001",
            review=review
        )

        # Assert
        assert result is True
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_multi_agent_supervision(
        self, service, intern_agent, autonomous_supervisor
    ):
        """Test multiple autonomous supervisors can be available."""
        # Arrange
        supervisors = [
            AgentRegistry(
                id=f"auto-{i:03d}",
                name=f"Supervisor {i}",
                category="data_analysis",
                confidence_score=0.90 + (i * 0.02),
                status=AgentStatus.AUTONOMOUS.value
            )
            for i in range(1, 4)
        ]

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = supervisors
        service.db.query.return_value = mock_query

        # Act
        result = await service.get_available_supervisors(
            category="data_analysis"
        )

        # Assert
        assert isinstance(result, list)
        assert len(result) == 3
        assert all(s.status == AgentStatus.AUTONOMOUS.value for s in result)

    @pytest.mark.asyncio
    async def test_supervision_termination(
        self, service, autonomous_supervisor, mock_db
    ):
        """Test supervision session terminates gracefully."""
        # Arrange
        execution_id = "exec-007"
        execution = AgentExecution(
            id=execution_id,
            agent_id="intern-001",
            status="completed"
        )

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = execution
        mock_db.query.return_value = mock_query

        # Act
        events = []
        async for event in service.monitor_execution(
            execution_id=execution_id,
            supervisor=autonomous_supervisor
        ):
            events.append(event)
            if event.event_type in ["execution_completed", "error"]:
                break

        # Assert
        assert len(events) > 0
        # Should terminate after completion


# ============================================================================
# Additional Helper Tests
# ============================================================================

class TestHelperMethods:
    """Tests for private helper methods."""

    def test_calculate_risk_level_by_action_type(self, service):
        """Test risk level calculation for different action types."""
        # Arrange & Act
        safe_risk = service._calculate_risk_level("canvas_present", {})
        medium_risk = service._calculate_risk_level("browser_automate", {})
        high_risk = service._calculate_risk_level("device_command", {})

        # Assert
        assert safe_risk == "safe"
        assert medium_risk == "medium"
        assert high_risk == "high"

    def test_should_approve_proposal_risk_thresholds(self, service):
        """Test approval thresholds based on risk level."""
        # Arrange
        high_conf_analysis = {"confidence": 0.96}
        medium_conf_analysis = {"confidence": 0.87}
        low_conf_analysis = {"confidence": 0.70}

        # Act & Assert
        # High-risk requires >=0.95 confidence
        assert service._should_approve_proposal(
            high_conf_analysis, "high", 0.96
        ) is True
        assert service._should_approve_proposal(
            low_conf_analysis, "high", 0.96
        ) is False

        # Safe requires >=0.75 confidence
        assert service._should_approve_proposal(
            medium_conf_analysis, "safe", 0.85
        ) is True
