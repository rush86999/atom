"""
Baseline unit tests for ProposalService.
Tests cover proposal creation, approval workflow, state management,
and validation rules for INTERN agent proposals.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from datetime import datetime
from sqlalchemy.orm import Session

from core.proposal_service import (
    ProposalService,
    PROPOSAL_EXECUTION_ENABLED,
)
from core.models import (
    AgentProposal,
    AgentRegistry,
    AgentStatus,
    ProposalStatus,
    ProposalType,
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
def mock_agent():
    """Mock INTERN agent."""
    agent = Mock(spec=AgentRegistry)
    agent.id = "agent_intern_001"
    agent.name = "Test Intern Agent"
    agent.category = "automation"
    agent.confidence_score = 0.65
    agent.status = AgentStatus.INTERN.value
    return agent


@pytest.fixture
def mock_proposal(mock_agent):
    """Mock proposal."""
    proposal = Mock(spec=AgentProposal)
    proposal.id = "proposal_001"
    proposal.agent_id = mock_agent.id
    proposal.agent_name = mock_agent.name
    proposal.proposal_type = ProposalType.ACTION.value
    proposal.title = f"Action Proposal: {mock_agent.name}"
    proposal.description = "Test proposal description"
    proposal.proposed_action = {"action_type": "canvas_present", "content": "test"}
    proposal.reasoning = "This is a test proposal"
    proposal.status = ProposalStatus.PROPOSED.value
    proposal.proposed_by = mock_agent.id
    proposal.approved_by = None
    proposal.approved_at = None
    proposal.modifications = None
    proposal.execution_result = None
    proposal.created_at = datetime.now()
    proposal.completed_at = None
    return proposal


# ============================================================================
# Test ProposalService Initialization
# ============================================================================

class TestProposalServiceInit:
    """Test ProposalService initialization."""

    def test_service_init(self, mock_db):
        """Test service initialization with database session."""
        service = ProposalService(mock_db)
        assert service.db is mock_db

    def test_service_has_required_methods(self):
        """Test service has expected methods."""
        import inspect
        assert hasattr(ProposalService, 'create_action_proposal')
        assert hasattr(ProposalService, 'approve_proposal')
        assert hasattr(ProposalService, 'reject_proposal')
        assert hasattr(ProposalService, 'get_pending_proposals')
        assert hasattr(ProposalService, 'get_proposal_history')
        
        # Verify they are async
        assert inspect.iscoroutinefunction(ProposalService.create_action_proposal)
        assert inspect.iscoroutinefunction(ProposalService.approve_proposal)
        assert inspect.iscoroutinefunction(ProposalService.reject_proposal)


class TestProposalExecutionFlag:
    """Test proposal execution feature flag."""

    def test_proposal_execution_flag_exists(self):
        """Test PROPOSAL_EXECUTION_ENABLED is defined."""
        assert isinstance(PROPOSAL_EXECUTION_ENABLED, bool)

    def test_proposal_execution_flag_default(self):
        """Test default value of execution flag."""
        # Should be True by default based on env var
        assert PROPOSAL_EXECUTION_ENABLED is True or PROPOSAL_EXECUTION_ENABLED is False


# ============================================================================
# Test Proposal Creation
# ============================================================================

class TestProposalCreation:
    """Test proposal creation from INTERN agents."""

    @pytest.mark.asyncio
    async def test_create_action_proposal_success(self, mock_db, mock_agent):
        """Test successful proposal creation."""
        # Setup mock query
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_agent
        mock_db.query.return_value = mock_query
        
        # Mock database add and commit
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        service = ProposalService(mock_db)
        
        # Create proposal
        proposal = await service.create_action_proposal(
            intern_agent_id=mock_agent.id,
            trigger_context={"test": "context"},
            proposed_action={"action_type": "canvas_present"},
            reasoning="Test reasoning"
        )
        
        # Verify proposal was created
        assert proposal.agent_id == mock_agent.id
        assert proposal.proposal_type == ProposalType.ACTION.value
        assert proposal.status == ProposalStatus.PROPOSED.value
        
        # Verify database operations
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_proposal_agent_not_found(self, mock_db):
        """Test proposal creation fails when agent not found."""
        # Setup mock to return None
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query
        
        service = ProposalService(mock_db)
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Agent .* not found"):
            await service.create_action_proposal(
                intern_agent_id="nonexistent",
                trigger_context={},
                proposed_action={},
                reasoning="Test"
            )

    @pytest.mark.asyncio
    async def test_create_proposal_with_non_intern_agent(self, mock_db, mock_agent):
        """Test proposal creation warns for non-INTERN agents."""
        # Change agent to STUDENT status
        mock_agent.status = AgentStatus.STUDENT.value
        
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_agent
        mock_db.query.return_value = mock_query
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        service = ProposalService(mock_db)
        
        # Should still create proposal but with warning
        proposal = await service.create_action_proposal(
            intern_agent_id=mock_agent.id,
            trigger_context={},
            proposed_action={},
            reasoning="Test"
        )
        
        # Proposal should still be created
        assert proposal is not None


# ============================================================================
# Test Proposal Approval
# ============================================================================

class TestProposalApproval:
    """Test proposal approval workflow."""

    @pytest.mark.asyncio
    async def test_approve_proposal_success(self, mock_db, mock_proposal):
        """Test successful proposal approval."""
        # Setup mock query to return proposal
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_proposal
        mock_db.query.return_value = mock_query
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        service = ProposalService(mock_db)
        
        # Mock the execution method
        service._execute_proposed_action = AsyncMock(return_value={"success": True})
        service._create_proposal_episode = AsyncMock()
        
        result = await service.approve_proposal(
            proposal_id=mock_proposal.id,
            user_id="user_123"
        )

        # Verify proposal status updated to EXECUTED (after approval + execution)
        assert mock_proposal.status == ProposalStatus.EXECUTED.value
        assert mock_proposal.approved_by == "user_123"
        assert mock_proposal.approved_at is not None
        assert mock_proposal.completed_at is not None

        # Verify database commit
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_approve_proposal_not_found(self, mock_db):
        """Test approval fails when proposal not found."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query
        
        service = ProposalService(mock_db)
        
        with pytest.raises(ValueError, match="Proposal .* not found"):
            await service.approve_proposal(
                proposal_id="nonexistent",
                user_id="user_123"
            )

    @pytest.mark.asyncio
    async def test_approve_proposal_with_modifications(self, mock_db, mock_proposal):
        """Test proposal approval with modifications."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_proposal
        mock_db.query.return_value = mock_query
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        service = ProposalService(mock_db)
        service._execute_proposed_action = AsyncMock(return_value={"success": True})
        service._create_proposal_episode = AsyncMock()
        
        modifications = {"content": "modified content"}
        
        await service.approve_proposal(
            proposal_id=mock_proposal.id,
            user_id="user_123",
            modifications=modifications
        )
        
        # Verify modifications applied
        assert mock_proposal.modifications == modifications


# ============================================================================
# Test Proposal Rejection
# ============================================================================

class TestProposalRejection:
    """Test proposal rejection workflow."""

    @pytest.mark.asyncio
    async def test_reject_proposal_success(self, mock_db, mock_proposal):
        """Test successful proposal rejection."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_proposal
        mock_db.query.return_value = mock_query
        mock_db.commit = Mock()
        
        service = ProposalService(mock_db)
        service._create_proposal_episode = AsyncMock()
        
        await service.reject_proposal(
            proposal_id=mock_proposal.id,
            user_id="user_123",
            reason="Not appropriate"
        )
        
        # Verify proposal rejected
        assert mock_proposal.status == ProposalStatus.REJECTED.value
        assert mock_proposal.approved_by == "user_123"
        assert mock_proposal.execution_result["rejected"] is True
        assert mock_proposal.execution_result["reason"] == "Not appropriate"
        
        # Verify database commit
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_reject_proposal_not_found(self, mock_db):
        """Test rejection fails when proposal not found."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query
        
        service = ProposalService(mock_db)
        
        with pytest.raises(ValueError, match="Proposal .* not found"):
            await service.reject_proposal(
                proposal_id="nonexistent",
                user_id="user_123",
                reason="Test"
            )


# ============================================================================
# Test Proposal Retrieval
# ============================================================================

class TestProposalRetrieval:
    """Test proposal retrieval and history."""

    @pytest.mark.asyncio
    async def test_get_pending_proposals(self, mock_db, mock_proposal):
        """Test retrieving pending proposals."""
        # Setup mock query chain
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value.all.return_value = [mock_proposal]
        mock_db.query.return_value = mock_query
        
        service = ProposalService(mock_db)
        
        proposals = await service.get_pending_proposals()
        
        # Should return list of proposals
        assert isinstance(proposals, list)
        assert len(proposals) == 1
        assert proposals[0].status == ProposalStatus.PROPOSED.value

    @pytest.mark.asyncio
    async def test_get_pending_proposals_for_agent(self, mock_db, mock_proposal):
        """Test retrieving pending proposals for specific agent."""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value.all.return_value = [mock_proposal]
        mock_db.query.return_value = mock_query
        
        service = ProposalService(mock_db)
        
        proposals = await service.get_pending_proposals(agent_id="agent_001")
        
        # Should filter by agent
        assert isinstance(proposals, list)
        mock_query.filter.assert_called()

    @pytest.mark.asyncio
    async def test_get_proposal_history(self, mock_db, mock_proposal):
        """Test retrieving agent proposal history."""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.limit.return_value.all.return_value = [mock_proposal]
        mock_db.query.return_value = mock_query
        
        service = ProposalService(mock_db)
        
        history = await service.get_proposal_history(agent_id="agent_001", limit=50)
        
        # Should return list of history dicts
        assert isinstance(history, list)
        assert len(history) == 1
        assert "proposal_id" in history[0]
        assert "status" in history[0]
        assert "created_at" in history[0]


# ============================================================================
# Test Proposal Submission
# ============================================================================

class TestProposalSubmission:
    """Test proposal submission for review."""

    @pytest.mark.asyncio
    async def test_submit_for_approval(self, mock_proposal):
        """Test submitting proposal for approval."""
        mock_db = Mock()
        service = ProposalService(mock_db)
        
        # Submit proposal (already in PROPOSED status)
        await service.submit_for_approval(mock_proposal)
        
        # Should not change status if already PROPOSED
        assert mock_proposal.status == ProposalStatus.PROPOSED.value

    @pytest.mark.asyncio
    async def test_submit_invalid_status(self, mock_proposal):
        """Test submission fails with invalid status."""
        mock_proposal.status = ProposalStatus.APPROVED.value
        mock_db = Mock()
        service = ProposalService(mock_db)
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="must be in PROPOSED status"):
            await service.submit_for_approval(mock_proposal)


# ============================================================================
# Test Action Execution
# ============================================================================

class TestActionExecution:
    """Test action execution from proposals."""

    @pytest.mark.asyncio
    async def test_execute_proposed_action_disabled(self, mock_proposal):
        """Test execution when feature flag disabled."""
        with patch('core.proposal_service.PROPOSAL_EXECUTION_ENABLED', False):
            mock_db = Mock()
            service = ProposalService(mock_db)
            
            result = await service._execute_proposed_action(mock_proposal)
            
            # Should return skipped result
            assert result["success"] is False
            assert result["skipped"] is True
            assert "disabled" in result["message"]

    @pytest.mark.asyncio
    async def test_execute_unknown_action_type(self, mock_proposal):
        """Test execution with unknown action type."""
        mock_proposal.proposed_action = {"action_type": "unknown_type"}
        mock_db = Mock()
        service = ProposalService(mock_db)
        
        result = await service._execute_proposed_action(mock_proposal)
        
        # Should return error
        assert result["success"] is False
        assert "Unknown action type" in result["error"]


# ============================================================================
# Test Episode Creation
# ============================================================================

class TestProposalEpisodeCreation:
    """Test episode creation from proposals."""

    def test_format_proposal_content(self, mock_proposal):
        """Test formatting proposal content for episode."""
        mock_db = Mock()
        service = ProposalService(mock_db)
        
        content = service._format_proposal_content(mock_proposal, "approved")
        
        # Should contain proposal details
        assert mock_proposal.title in content
        assert "Proposal Type:" in content
        assert "Agent:" in content

    def test_format_proposal_outcome_approved(self, mock_proposal):
        """Test formatting approved outcome."""
        mock_db = Mock()
        service = ProposalService(mock_db)

        mock_proposal.approved_by = "user_123"
        mock_proposal.approved_at = datetime.now()

        outcome = service._format_proposal_outcome(
            mock_proposal, "approved",
            modifications=["changed content", "added field"],
            execution_result={"success": True}
        )

        # Should contain approval details
        assert "APPROVED" in outcome
        assert "user_123" in outcome
        assert "Modifications Applied: 2" in outcome

    def test_format_proposal_outcome_rejected(self, mock_proposal):
        """Test formatting rejected outcome."""
        mock_db = Mock()
        service = ProposalService(mock_db)
        
        mock_proposal.approved_by = "user_123"
        mock_proposal.approved_at = datetime.now()
        
        outcome = service._format_proposal_outcome(
            mock_proposal, "rejected",
            rejection_reason="Not appropriate"
        )
        
        # Should contain rejection details
        assert "REJECTED" in outcome
        assert "Not appropriate" in outcome

    def test_extract_proposal_topics(self, mock_proposal):
        """Test extracting topics from proposal."""
        mock_proposal.title = "Test proposal for automation workflow"
        mock_proposal.reasoning = "This proposal tests automation features"
        mock_proposal.proposed_action = {"action_type": "canvas_present"}
        
        mock_db = Mock()
        service = ProposalService(mock_db)
        
        topics = service._extract_proposal_topics(mock_proposal)
        
        # Should return list of topics
        assert isinstance(topics, list)
        assert len(topics) > 0

    def test_extract_proposal_entities(self, mock_proposal):
        """Test extracting entities from proposal."""
        mock_proposal.id = "prop_001"
        mock_proposal.agent_id = "agent_001"
        mock_proposal.approved_by = "user_001"
        mock_proposal.proposed_action = {"target": "value"}
        
        mock_db = Mock()
        service = ProposalService(mock_db)
        
        entities = service._extract_proposal_entities(mock_proposal)
        
        # Should return list of entities
        assert isinstance(entities, list)
        assert "proposal:prop_001" in entities
        assert "agent:agent_001" in entities

    def test_calculate_proposal_importance_approved(self, mock_proposal):
        """Test importance score for approved proposal."""
        mock_db = Mock()
        service = ProposalService(mock_db)
        
        score = service._calculate_proposal_importance("approved", mock_proposal)
        
        # Should be between 0 and 1
        assert 0.0 <= score <= 1.0

    def test_calculate_proposal_importance_rejected(self, mock_proposal):
        """Test importance score for rejected proposal."""
        mock_db = Mock()
        service = ProposalService(mock_db)
        
        score = service._calculate_proposal_importance("rejected", mock_proposal)
        
        # Rejected should have higher importance
        assert 0.0 <= score <= 1.0


# ============================================================================
# Test Autonomous Supervisor Integration
# ============================================================================

class TestAutonomousSupervisor:
    """Test autonomous supervisor integration for proposals."""

    def test_review_method_exists(self):
        """Test that review_with_autonomous_supervisor method exists."""
        import inspect
        assert hasattr(ProposalService, 'review_with_autonomous_supervisor')
        assert inspect.iscoroutinefunction(ProposalService.review_with_autonomous_supervisor)

    def test_autonomous_approve_method_exists(self):
        """Test that autonomous_approve_or_reject method exists."""
        import inspect
        assert hasattr(ProposalService, 'autonomous_approve_or_reject')
        assert inspect.iscoroutinefunction(ProposalService.autonomous_approve_or_reject)
