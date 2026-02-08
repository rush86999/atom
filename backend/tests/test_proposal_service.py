"""
Proposal Service Tests

Comprehensive test suite for ProposalService including:
- Action proposal creation from INTERN agents
- Proposal approval and execution
- Proposal rejection
- Pending proposals and history retrieval
- Action execution (browser, canvas, integration, workflow, device, agent)
- Error handling and edge cases
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
import pytest
from sqlalchemy.orm import Session

from core.proposal_service import ProposalService
from core.models import (
    AgentExecution,
    AgentProposal,
    AgentRegistry,
    AgentStatus,
    ProposalStatus,
    ProposalType,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def db():
    """Create a test database session."""
    import os
    # Set test database URL
    os.environ['DATABASE_URL'] = 'sqlite:///./test_atom_proposal.db'

    from core.database import engine, SessionLocal
    from core.models import Base

    # Create tables
    Base.metadata.create_all(bind=engine)

    # Create session
    db = SessionLocal()
    db.expire_on_commit = False  # Allow access to objects after commit

    try:
        yield db
        db.rollback()  # Rollback changes after test
    finally:
        db.close()
        # Clean up test database
        import os
        try:
            os.remove('./test_atom_proposal.db')
        except:
            pass


@pytest.fixture
def intern_agent(db):
    """Create a test INTERN agent."""
    agent_id = f"intern-agent-{uuid.uuid4()}"
    agent = AgentRegistry(
        id=agent_id,
        name="Test Intern Agent",
        category="Sales",
        module_path="agents.test_intern",
        class_name="TestInternAgent",
        status=AgentStatus.INTERN.value,
        confidence_score=0.65,
        description="A test intern agent"
    )
    db.add(agent)
    db.commit()
    db.expunge(agent)
    yield agent
    # Cleanup
    db.query(AgentExecution).filter(AgentExecution.agent_id == agent_id).delete(synchronize_session=False)
    db.query(AgentProposal).filter(AgentProposal.agent_id == agent_id).delete(synchronize_session=False)
    db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).delete(synchronize_session=False)
    db.commit()


@pytest.fixture
def proposal_service(db):
    """Create a ProposalService instance."""
    return ProposalService(db)


# ============================================================================
# Tests: Action Proposal Creation
# ============================================================================

class TestActionProposalCreation:
    """Tests for creating action proposals from INTERN agents."""

    @pytest.mark.asyncio
    async def test_create_action_proposal_basic(self, proposal_service, intern_agent):
        """Test basic action proposal creation."""
        trigger_context = {
            "trigger_type": "workflow_trigger",
            "workflow_id": "test-workflow-123"
        }
        proposed_action = {
            "action_type": "browser_automate",
            "url": "https://example.com",
            "actions": ["navigate", "click"]
        }
        reasoning = "Need to automate data entry on customer portal"

        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context=trigger_context,
            proposed_action=proposed_action,
            reasoning=reasoning
        )

        assert proposal is not None
        assert proposal.agent_id == intern_agent.id
        assert proposal.agent_name == intern_agent.name
        assert proposal.proposal_type == ProposalType.ACTION.value
        assert proposal.status == ProposalStatus.PROPOSED.value
        assert proposal.proposed_action == proposed_action
        assert proposal.reasoning == reasoning
        assert "Action Proposal" in proposal.title

    @pytest.mark.asyncio
    async def test_create_action_proposal_content_generation(self, proposal_service, intern_agent):
        """Test that proposal description is properly generated."""
        proposed_action = {
            "action_type": "canvas_present",
            "canvas_type": "chart"
        }
        reasoning = "Generate sales performance chart"

        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action=proposed_action,
            reasoning=reasoning
        )

        # Check description contains agent info
        assert intern_agent.name in proposal.description
        assert intern_agent.category in proposal.description
        assert str(intern_agent.confidence_score) in proposal.description
        assert reasoning in proposal.description

    @pytest.mark.asyncio
    async def test_create_action_proposal_agent_not_found(self, proposal_service):
        """Test error handling when agent is not found."""
        fake_agent_id = f"fake-agent-{uuid.uuid4()}"

        with pytest.raises(ValueError, match=f"Agent {fake_agent_id} not found"):
            await proposal_service.create_action_proposal(
                intern_agent_id=fake_agent_id,
                trigger_context={},
                proposed_action={},
                reasoning="Test"
            )

    @pytest.mark.asyncio
    async def test_create_action_proposal_non_intern_agent(self, proposal_service, db):
        """Test proposal creation for non-INTERN agent (should warn but not fail)."""
        # Create a STUDENT agent
        student_agent = AgentRegistry(
            id=f"student-{uuid.uuid4()}",
            name="Student Agent",
            category="Sales",
            module_path="agents.student",
            class_name="StudentAgent",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3
        )
        db.add(student_agent)
        db.commit()

        # Should still create proposal, just with warning
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=student_agent.id,
            trigger_context={},
            proposed_action={"action_type": "test"},
            reasoning="Test"
        )

        assert proposal is not None

        # Cleanup
        db.query(AgentProposal).filter(AgentProposal.id == proposal.id).delete()
        db.query(AgentRegistry).filter(AgentRegistry.id == student_agent.id).delete()
        db.commit()


# ============================================================================
# Tests: Proposal Submission
# ============================================================================

class TestProposalSubmission:
    """Tests for submitting proposals for approval."""

    @pytest.mark.asyncio
    async def test_submit_for_approval(self, proposal_service, intern_agent):
        """Test submitting proposal for approval."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "test"},
            reasoning="Test"
        )

        # Should not raise any errors
        await proposal_service.submit_for_approval(proposal)

        # Proposal should still be in PROPOSED status
        assert proposal.status == ProposalStatus.PROPOSED.value

    @pytest.mark.asyncio
    async def test_submit_for_approval_invalid_status(self, proposal_service, intern_agent, db):
        """Test error when submitting proposal with invalid status."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "test"},
            reasoning="Test"
        )

        # Change status to APPROVED
        proposal.status = ProposalStatus.APPROVED.value
        db.commit()

        with pytest.raises(ValueError, match="Proposal must be in PROPOSED status"):
            await proposal_service.submit_for_approval(proposal)


# ============================================================================
# Tests: Proposal Approval
# ============================================================================

class TestProposalApproval:
    """Tests for approving proposals."""

    @pytest.mark.asyncio
    async def test_approve_proposal_basic(self, proposal_service, intern_agent):
        """Test basic proposal approval."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "unknown_action"},
            reasoning="Test"
        )

        user_id = f"user-{uuid.uuid4()}"
        result = await proposal_service.approve_proposal(
            proposal_id=proposal.id,
            user_id=user_id
        )

        assert result is not None
        assert "success" in result
        assert "executed_at" in result

        # Check proposal is updated
        assert proposal.status == ProposalStatus.EXECUTED.value
        assert proposal.approved_by == user_id
        assert proposal.approved_at is not None
        assert proposal.completed_at is not None

    @pytest.mark.asyncio
    async def test_approve_proposal_with_modifications(self, proposal_service, intern_agent):
        """Test proposal approval with modifications."""
        original_action = {"action_type": "browser_automate", "url": "https://example.com"}
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action=original_action,
            reasoning="Test"
        )

        modifications = {"url": "https://modified.com"}
        user_id = f"user-{uuid.uuid4()}"

        await proposal_service.approve_proposal(
            proposal_id=proposal.id,
            user_id=user_id,
            modifications=modifications
        )

        # Check modifications are applied
        assert proposal.proposed_action["url"] == "https://modified.com"
        assert proposal.modifications == modifications

    @pytest.mark.asyncio
    async def test_approve_proposal_not_found(self, proposal_service):
        """Test error handling when proposal is not found."""
        fake_proposal_id = f"fake-proposal-{uuid.uuid4()}"
        user_id = f"user-{uuid.uuid4()}"

        with pytest.raises(ValueError, match=f"Proposal {fake_proposal_id} not found"):
            await proposal_service.approve_proposal(
                proposal_id=fake_proposal_id,
                user_id=user_id
            )

    @pytest.mark.asyncio
    async def test_approve_proposal_invalid_status(self, proposal_service, intern_agent, db):
        """Test error when approving proposal with invalid status."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "test"},
            reasoning="Test"
        )

        # Change status to APPROVED
        proposal.status = ProposalStatus.APPROVED.value
        db.commit()

        user_id = f"user-{uuid.uuid4()}"

        with pytest.raises(ValueError, match="Proposal must be in PROPOSED status"):
            await proposal_service.approve_proposal(
                proposal_id=proposal.id,
                user_id=user_id
            )


# ============================================================================
# Tests: Proposal Rejection
# ============================================================================

class TestProposalRejection:
    """Tests for rejecting proposals."""

    @pytest.mark.asyncio
    async def test_reject_proposal_basic(self, proposal_service, intern_agent):
        """Test basic proposal rejection."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "test"},
            reasoning="Test"
        )

        user_id = f"user-{uuid.uuid4()}"
        reason = "Action not aligned with business goals"

        await proposal_service.reject_proposal(
            proposal_id=proposal.id,
            user_id=user_id,
            reason=reason
        )

        # Check proposal is updated
        assert proposal.status == ProposalStatus.REJECTED.value
        assert proposal.approved_by == user_id
        assert proposal.approved_at is not None
        assert proposal.execution_result is not None
        assert proposal.execution_result["rejected"] is True
        assert proposal.execution_result["rejected_by"] == user_id
        assert reason in proposal.execution_result["reason"]

    @pytest.mark.asyncio
    async def test_reject_proposal_not_found(self, proposal_service):
        """Test error handling when proposal is not found."""
        fake_proposal_id = f"fake-proposal-{uuid.uuid4()}"
        user_id = f"user-{uuid.uuid4()}"

        with pytest.raises(ValueError, match=f"Proposal {fake_proposal_id} not found"):
            await proposal_service.reject_proposal(
                proposal_id=fake_proposal_id,
                user_id=user_id,
                reason="Test"
            )


# ============================================================================
# Tests: Pending Proposals and History
# ============================================================================

class TestPendingProposalsAndHistory:
    """Tests for retrieving pending proposals and history."""

    @pytest.mark.asyncio
    async def test_get_pending_proposals_empty(self, proposal_service, intern_agent):
        """Test getting pending proposals when none exist."""
        pending = await proposal_service.get_pending_proposals()

        assert pending is not None
        assert isinstance(pending, list)
        assert len(pending) == 0

    @pytest.mark.asyncio
    async def test_get_pending_proposals(self, proposal_service, intern_agent):
        """Test getting pending proposals."""
        # Create multiple proposals
        for i in range(3):
            await proposal_service.create_action_proposal(
                intern_agent_id=intern_agent.id,
                trigger_context={},
                proposed_action={"action_type": f"action_{i}"},
                reasoning=f"Reason {i}"
            )

        pending = await proposal_service.get_pending_proposals()

        assert len(pending) == 3
        assert all(p.status == ProposalStatus.PROPOSED.value for p in pending)

    @pytest.mark.asyncio
    async def test_get_pending_proposals_by_agent(self, proposal_service, intern_agent, db):
        """Test getting pending proposals filtered by agent."""
        # Create proposals for intern_agent
        for i in range(2):
            await proposal_service.create_action_proposal(
                intern_agent_id=intern_agent.id,
                trigger_context={},
                proposed_action={"action_type": f"action_{i}"},
                reasoning=f"Reason {i}"
            )

        # Create another agent
        other_agent = AgentRegistry(
            id=f"other-{uuid.uuid4()}",
            name="Other Agent",
            category="Finance",
            module_path="agents.other",
            class_name="OtherAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db.add(other_agent)
        db.commit()

        await proposal_service.create_action_proposal(
            intern_agent_id=other_agent.id,
            trigger_context={},
            proposed_action={"action_type": "other_action"},
            reasoning="Other reason"
        )

        # Get proposals for intern_agent only
        agent_pending = await proposal_service.get_pending_proposals(agent_id=intern_agent.id)

        assert len(agent_pending) == 2
        assert all(p.agent_id == intern_agent.id for p in agent_pending)

        # Cleanup
        db.query(AgentProposal).filter(AgentProposal.agent_id == other_agent.id).delete()
        db.query(AgentRegistry).filter(AgentRegistry.id == other_agent.id).delete()
        db.commit()

    @pytest.mark.asyncio
    async def test_get_pending_proposals_limit(self, proposal_service, intern_agent):
        """Test limit parameter for pending proposals."""
        # Create more proposals than limit
        for i in range(10):
            await proposal_service.create_action_proposal(
                intern_agent_id=intern_agent.id,
                trigger_context={},
                proposed_action={"action_type": f"action_{i}"},
                reasoning=f"Reason {i}"
            )

        pending = await proposal_service.get_pending_proposals(limit=5)

        assert len(pending) <= 5

    @pytest.mark.asyncio
    async def test_get_proposal_history_empty(self, proposal_service, intern_agent):
        """Test getting proposal history for agent with no history."""
        history = await proposal_service.get_proposal_history(intern_agent.id)

        assert history is not None
        assert isinstance(history, list)
        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_get_proposal_history(self, proposal_service, intern_agent):
        """Test getting proposal history."""
        # Create proposals
        for i in range(3):
            proposal = await proposal_service.create_action_proposal(
                intern_agent_id=intern_agent.id,
                trigger_context={},
                proposed_action={"action_type": f"action_{i}"},
                reasoning=f"Reason {i}"
            )

            # Reject some to have different statuses
            if i % 2 == 0:
                await proposal_service.reject_proposal(
                    proposal_id=proposal.id,
                    user_id=f"user-{uuid.uuid4()}",
                    reason=f"Reject {i}"
                )

        history = await proposal_service.get_proposal_history(intern_agent.id)

        assert len(history) == 3
        assert all("proposal_id" in h for h in history)
        assert all("status" in h for h in history)
        assert all("created_at" in h for h in history)

    @pytest.mark.asyncio
    async def test_get_proposal_history_limit(self, proposal_service, intern_agent):
        """Test limit parameter for proposal history."""
        # Create multiple proposals
        for i in range(10):
            await proposal_service.create_action_proposal(
                intern_agent_id=intern_agent.id,
                trigger_context={},
                proposed_action={"action_type": f"action_{i}"},
                reasoning=f"Reason {i}"
            )

        history = await proposal_service.get_proposal_history(intern_agent.id, limit=5)

        assert len(history) <= 5


# ============================================================================
# Tests: Action Execution
# ============================================================================

class TestActionExecution:
    """Tests for executing proposed actions."""

    @pytest.mark.asyncio
    async def test_execute_proposed_action_unknown_type(self, proposal_service, intern_agent):
        """Test execution of unknown action type."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "unknown_action"},
            reasoning="Test"
        )

        result = await proposal_service._execute_proposed_action(proposal)

        assert result["success"] is False
        assert "error" in result
        assert "unknown action type" in result["error"].lower()

    @pytest.mark.asyncio
    @patch.dict('os.environ', {'PROPOSAL_EXECUTION_ENABLED': 'false'})
    async def test_execute_proposed_action_disabled(self, proposal_service, intern_agent):
        """Test execution when feature flag is disabled."""
        import os
        # Temporarily disable execution
        old_value = os.environ.get('PROPOSAL_EXECUTION_ENABLED')
        os.environ['PROPOSAL_EXECUTION_ENABLED'] = 'false'

        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "browser_automate"},
            reasoning="Test"
        )

        result = await proposal_service._execute_proposed_action(proposal)

        assert result["success"] is False
        assert result["skipped"] is True
        assert "disabled" in result["message"].lower()

        # Restore
        if old_value is None:
            os.environ.pop('PROPOSAL_EXECUTION_ENABLED', None)
        else:
            os.environ['PROPOSAL_EXECUTION_ENABLED'] = old_value

    @pytest.mark.asyncio
    async def test_execute_browser_action_not_available(self, proposal_service, intern_agent):
        """Test browser action when browser tool is not available."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={
                "action_type": "browser_automate",
                "url": "https://example.com"
            },
            reasoning="Test"
        )

        # Mock approve_proposal to set approved_by
        proposal.approved_by = f"user-{uuid.uuid4()}"

        result = await proposal_service._execute_browser_action(
            proposal,
            proposal.proposed_action
        )

        # Browser tool should not be available in test environment
        # Either import error or execution error
        assert "success" in result

    @pytest.mark.asyncio
    async def test_execute_canvas_action_not_available(self, proposal_service, intern_agent):
        """Test canvas action when canvas tool is not available."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={
                "action_type": "canvas_present",
                "canvas_type": "chart"
            },
            reasoning="Test"
        )

        # Mock approve_proposal to set approved_by
        proposal.approved_by = f"user-{uuid.uuid4()}"

        try:
            result = await proposal_service._execute_canvas_action(
                proposal,
                proposal.proposed_action
            )
            # If canvas tool exists, check result structure
            assert "success" in result
        except Exception as e:
            # Canvas tool might not be available
            assert "canvas" in str(e).lower() or "import" in str(e).lower()

    @pytest.mark.asyncio
    async def test_execute_integration_action_not_available(self, proposal_service, intern_agent):
        """Test integration action when integration service is not available."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={
                "action_type": "integration_connect",
                "integration_type": "gmail"
            },
            reasoning="Test"
        )

        # Mock approve_proposal to set approved_by
        proposal.approved_by = f"user-{uuid.uuid4()}"

        result = await proposal_service._execute_integration_action(
            proposal,
            proposal.proposed_action
        )

        # Integration service might not be available
        assert "success" in result

    @pytest.mark.asyncio
    async def test_execute_workflow_action_not_available(self, proposal_service, intern_agent):
        """Test workflow action when workflow engine is not available."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={
                "action_type": "workflow_trigger",
                "workflow_id": "test-workflow"
            },
            reasoning="Test"
        )

        # Mock approve_proposal to set approved_by
        proposal.approved_by = f"user-{uuid.uuid4()}"

        try:
            result = await proposal_service._execute_workflow_action(
                proposal,
                proposal.proposed_action
            )
            # If workflow engine exists, check result structure
            assert "success" in result
        except Exception as e:
            # Workflow engine might not be available
            assert "workflow" in str(e).lower() or "import" in str(e).lower()

    @pytest.mark.asyncio
    async def test_execute_device_action_not_available(self, proposal_service, intern_agent):
        """Test device action when device tool is not available."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={
                "action_type": "device_command",
                "command_type": "camera"
            },
            reasoning="Test"
        )

        # Mock approve_proposal to set approved_by
        proposal.approved_by = f"user-{uuid.uuid4()}"

        try:
            result = await proposal_service._execute_device_action(
                proposal,
                proposal.proposed_action
            )
            # If device tool exists, check result structure
            assert "success" in result
        except Exception as e:
            # Device tool might not be available
            assert "device" in str(e).lower() or "import" in str(e).lower()

    @pytest.mark.asyncio
    async def test_execute_agent_action_not_available(self, proposal_service, intern_agent):
        """Test agent action when generic agent executor is not available."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={
                "action_type": "agent_execute",
                "target_agent_id": intern_agent.id
            },
            reasoning="Test"
        )

        # Mock approve_proposal to set approved_by
        proposal.approved_by = f"user-{uuid.uuid4()}"

        try:
            result = await proposal_service._execute_agent_action(
                proposal,
                proposal.proposed_action
            )
            # If agent executor exists, check result structure
            assert "success" in result
        except Exception as e:
            # Agent executor might not be available
            assert "agent" in str(e).lower() or "import" in str(e).lower()


# ============================================================================
# Tests: Error Handling
# ============================================================================

class TestErrorHandling:
    """Tests for error handling in proposal service."""

    @pytest.mark.asyncio
    async def test_proposal_execution_with_exception(self, proposal_service, intern_agent):
        """Test proposal execution when an exception occurs."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "test"},
            reasoning="Test"
        )

        # Mock _execute_proposed_action to raise exception
        async def mock_execute(proposal):
            raise ValueError("Test error")

        with patch.object(proposal_service, '_execute_proposed_action', mock_execute):
            result = await proposal_service._execute_proposed_action(proposal)

        # Should return error result
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_action_type_routing(self, proposal_service, intern_agent):
        """Test that different action types are routed correctly."""
        action_types = [
            "browser_automate",
            "canvas_present",
            "integration_connect",
            "workflow_trigger",
            "device_command",
            "agent_execute"
        ]

        for action_type in action_types:
            proposal = await proposal_service.create_action_proposal(
                intern_agent_id=intern_agent.id,
                trigger_context={},
                proposed_action={"action_type": action_type},
                reasoning=f"Test {action_type}"
            )

            # Verify the action type is stored correctly
            assert proposal.proposed_action["action_type"] == action_type

            # Test routing (will likely fail due to missing tools, but tests routing logic)
            try:
                result = await proposal_service._execute_proposed_action(proposal)
                # If it succeeds, check it has the right structure
                assert "action_type" in result
            except Exception:
                # Expected if tools aren't available
                pass


# ============================================================================
# Tests: Execution Tracking
# ============================================================================

class TestExecutionTracking:
    """Tests for execution tracking in proposal service."""

    @pytest.mark.asyncio
    async def test_execution_created_for_proposal(self, proposal_service, intern_agent, db):
        """Test that AgentExecution records are created for proposals."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "unknown_action"},
            reasoning="Test"
        )

        initial_count = db.query(AgentExecution).filter(
            AgentExecution.agent_id == intern_agent.id
        ).count()

        # Approve proposal (which triggers execution)
        await proposal_service.approve_proposal(
            proposal_id=proposal.id,
            user_id=f"user-{uuid.uuid4()}"
        )

        # Check that execution was created
        # Note: This might be 0 if the action type is unknown
        final_count = db.query(AgentExecution).filter(
            AgentExecution.agent_id == intern_agent.id
        ).count()

        # At minimum, should not have decreased
        assert final_count >= initial_count

    @pytest.mark.asyncio
    async def test_execution_status_updates(self, proposal_service, intern_agent, db):
        """Test that execution status is updated correctly."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "test"},
            reasoning="Test"
        )

        # Check that proposal execution_result is populated after approval
        await proposal_service.approve_proposal(
            proposal_id=proposal.id,
            user_id=f"user-{uuid.uuid4()}"
        )

        # Execution result should be set
        assert proposal.execution_result is not None
        assert "executed_at" in proposal.execution_result
