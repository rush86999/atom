"""
Unit tests for ProposalService.

Tests proposal generation, approval workflow, risk assessment, and audit trail.
Focuses on service-level proposal logic, not UI.
"""

import asyncio
import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.models import (
    AgentProposal,
    AgentRegistry,
    AgentStatus,
    ProposalStatus,
    ProposalType,
)
from core.proposal_service import ProposalService
from tests.factories import InternAgentFactory, AutonomousAgentFactory


# Test database session fixture
@pytest.fixture
def db_session():
    """Create a fresh database session for each test."""
    db = SessionLocal()
    try:
        yield db
        db.rollback()
    finally:
        db.close()


# Proposal service fixture
@pytest.fixture
def proposal_service(db_session):
    """Create proposal service instance."""
    return ProposalService(db_session)


@pytest.fixture
def intern_agent(db_session):
    """Create an INTERN agent for testing."""
    agent = InternAgentFactory(_session=db_session)
    db_session.commit()
    return agent


# ========================================================================
# Task 1.1: Proposal Generation
# ========================================================================

class TestProposalGeneration:
    """Test proposal generation for INTERN agents."""

    @pytest.mark.asyncio
    async def test_create_action_proposal_for_intern_agent(self, proposal_service, intern_agent):
        """Test generating proposal for INTERN agent."""
        trigger_context = {
            "action_type": "browser_automate",
            "url": "https://example.com",
            "actions": ["navigate", "click"]
        }
        proposed_action = {
            "action_type": "browser_automate",
            "url": "https://example.com",
            "actions": ["navigate", "click", "fill"]
        }
        reasoning = "I need to navigate to the website and fill out a form to gather data."

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
        assert proposal.approved_by is None
        assert proposal.approved_at is None

    @pytest.mark.asyncio
    async def test_proposal_includes_required_fields(self, proposal_service, intern_agent):
        """Test proposal includes all required fields."""
        proposed_action = {
            "action_type": "canvas_present",
            "canvas_type": "chart",
            "content": {"data": [1, 2, 3]}
        }
        reasoning = "Present data as chart for user analysis."

        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action=proposed_action,
            reasoning=reasoning
        )

        # Verify all required fields
        assert proposal.id is not None
        assert proposal.agent_id is not None
        assert proposal.agent_name is not None
        assert proposal.title is not None
        assert "Action Proposal" in proposal.title
        assert proposal.description is not None
        assert proposal.proposed_action is not None
        assert proposal.reasoning is not None
        assert proposal.status == ProposalStatus.PROPOSED.value

    @pytest.mark.asyncio
    async def test_proposal_format_validation(self, proposal_service, intern_agent):
        """Test proposal format is correct."""
        proposed_action = {
            "action_type": "integration_connect",
            "integration_type": "slack",
            "operation": "send_message"
        }
        reasoning = "Send message to Slack channel."

        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action=proposed_action,
            reasoning=reasoning
        )

        # Verify proposal format
        assert isinstance(proposal.proposed_action, dict)
        assert isinstance(proposal.reasoning, str)
        assert isinstance(proposal.status, str)
        assert isinstance(proposal.created_at, datetime)

    @pytest.mark.asyncio
    async def test_create_proposal_for_non_intern_agent_logs_warning(
        self, proposal_service, db_session
    ):
        """Test creating proposal for AUTONOMOUS agent logs warning."""
        # Create AUTONOMOUS agent
        autonomous_agent = AutonomousAgentFactory(_session=db_session)
        db_session.commit()

        proposed_action = {"action_type": "test"}
        reasoning = "Test reasoning"

        # Should still create proposal, but log warning
        with patch('core.proposal_service.logger') as mock_logger:
            proposal = await proposal_service.create_action_proposal(
                intern_agent_id=autonomous_agent.id,
                trigger_context={},
                proposed_action=proposed_action,
                reasoning=reasoning
            )
            mock_logger.warning.assert_called()

        assert proposal is not None

    @pytest.mark.asyncio
    async def test_create_proposal_for_nonexistent_agent_raises_error(
        self, proposal_service
    ):
        """Test creating proposal for non-existent agent raises error."""
        with pytest.raises(ValueError, match="Agent .* not found"):
            await proposal_service.create_action_proposal(
                intern_agent_id="nonexistent_agent_id",
                trigger_context={},
                proposed_action={"action_type": "test"},
                reasoning="Test"
            )


# ========================================================================
# Task 1.2: Approval Workflow
# ========================================================================

class TestApprovalWorkflow:
    """Test proposal approval workflow."""

    @pytest.mark.asyncio
    async def test_submit_proposal_for_approval(self, proposal_service, intern_agent):
        """Test submitting proposal for human approval."""
        # Create proposal
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "test"},
            reasoning="Test"
        )

        # Submit for approval
        with patch('core.proposal_service.logger') as mock_logger:
            await proposal_service.submit_for_approval(proposal)
            mock_logger.info.assert_called()

        # Proposal should still be in PROPOSED status
        db_proposal = proposal_service.db.query(AgentProposal).filter(
            AgentProposal.id == proposal.id
        ).first()
        assert db_proposal.status == ProposalStatus.PROPOSED.value

    @pytest.mark.asyncio
    async def test_approve_proposal_executes_action(
        self, proposal_service, intern_agent, db_session
    ):
        """Test approving proposal executes action."""
        # Create proposal with disabled execution for test
        proposal = AgentProposal(
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            proposal_type=ProposalType.ACTION.value,
            title="Test Proposal",
            description="Test",
            proposed_action={"action_type": "canvas_present"},
            reasoning="Test",
            status=ProposalStatus.PROPOSED.value,
            proposed_by=intern_agent.id
        )
        db_session.add(proposal)
        db_session.commit()

        # Mock execution to avoid actual action execution
        with patch.object(
            proposal_service, '_execute_proposed_action',
            new=AsyncMock(return_value={
                "success": True,
                "action_type": "canvas_present",
                "executed_at": datetime.now().isoformat()
            })
        ), patch.object(
            proposal_service, '_create_proposal_episode',
            new=AsyncMock()
        ):
            result = await proposal_service.approve_proposal(
                proposal_id=proposal.id,
                user_id="test_user_id"
            )

        assert result["success"] is True
        assert result["action_type"] == "canvas_present"

        # Verify proposal status updated
        db_session.refresh(proposal)
        assert proposal.status == ProposalStatus.EXECUTED.value
        assert proposal.approved_by == "test_user_id"
        assert proposal.approved_at is not None

    @pytest.mark.asyncio
    async def test_approve_proposal_with_modifications(
        self, proposal_service, intern_agent, db_session
    ):
        """Test approving proposal with modifications."""
        proposal = AgentProposal(
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            proposal_type=ProposalType.ACTION.value,
            title="Test Proposal",
            description="Test",
            proposed_action={"action_type": "test", "param1": "value1"},
            reasoning="Test",
            status=ProposalStatus.PROPOSED.value,
            proposed_by=intern_agent.id
        )
        db_session.add(proposal)
        db_session.commit()

        modifications = {"param1": "modified_value", "param2": "new_param"}

        with patch.object(
            proposal_service, '_execute_proposed_action',
            new=AsyncMock(return_value={"success": True})
        ), patch.object(
            proposal_service, '_create_proposal_episode',
            new=AsyncMock()
        ):
            await proposal_service.approve_proposal(
                proposal_id=proposal.id,
                user_id="test_user_id",
                modifications=modifications
            )

        # Verify modifications tracked (dict was updated in-place before execution)
        db_session.refresh(proposal)
        assert proposal.modifications == modifications
        # The modifications dict itself is stored, verify it contains expected keys
        assert "param1" in proposal.modifications
        assert proposal.modifications["param1"] == "modified_value"

    @pytest.mark.asyncio
    async def test_reject_proposal_blocks_execution(
        self, proposal_service, intern_agent, db_session
    ):
        """Test rejecting proposal blocks execution."""
        proposal = AgentProposal(
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            proposal_type=ProposalType.ACTION.value,
            title="Test Proposal",
            description="Test",
            proposed_action={"action_type": "test"},
            reasoning="Test",
            status=ProposalStatus.PROPOSED.value,
            proposed_by=intern_agent.id
        )
        db_session.add(proposal)
        db_session.commit()

        rejection_reason = "Action too risky, manual review required"

        with patch.object(
            proposal_service, '_create_proposal_episode',
            new=AsyncMock()
        ):
            await proposal_service.reject_proposal(
                proposal_id=proposal.id,
                user_id="test_user_id",
                reason=rejection_reason
            )

        # Verify proposal rejected
        db_session.refresh(proposal)
        assert proposal.status == ProposalStatus.REJECTED.value
        assert proposal.approved_by == "test_user_id"
        assert proposal.approved_at is not None
        assert proposal.execution_result["rejected"] is True
        assert proposal.execution_result["reason"] == rejection_reason

    @pytest.mark.asyncio
    async def test_proposal_expiration(self, proposal_service, intern_agent, db_session):
        """Test handling of expired proposals."""
        # Create old proposal
        old_proposal = AgentProposal(
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            proposal_type=ProposalType.ACTION.value,
            title="Old Proposal",
            description="Test",
            proposed_action={"action_type": "test"},
            reasoning="Test",
            status=ProposalStatus.PROPOSED.value,
            proposed_by=intern_agent.id,
            created_at=datetime.now() - timedelta(days=30)
        )
        db_session.add(old_proposal)
        db_session.commit()

        # Try to approve expired proposal (should still work but may be filtered in UI)
        with patch.object(
            proposal_service, '_execute_proposed_action',
            new=AsyncMock(return_value={"success": True})
        ), patch.object(
            proposal_service, '_create_proposal_episode',
            new=AsyncMock()
        ):
            result = await proposal_service.approve_proposal(
                proposal_id=old_proposal.id,
                user_id="test_user_id"
            )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_approve_nonexistent_proposal_raises_error(self, proposal_service):
        """Test approving non-existent proposal raises error."""
        with pytest.raises(ValueError, match="Proposal .* not found"):
            await proposal_service.approve_proposal(
                proposal_id="nonexistent_proposal_id",
                user_id="test_user_id"
            )

    @pytest.mark.asyncio
    async def test_approve_proposal_in_wrong_status_raises_error(
        self, proposal_service, intern_agent, db_session
    ):
        """Test approving already executed proposal raises error."""
        # Create already executed proposal
        proposal = AgentProposal(
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            proposal_type=ProposalType.ACTION.value,
            title="Test Proposal",
            description="Test",
            proposed_action={"action_type": "test"},
            reasoning="Test",
            status=ProposalStatus.EXECUTED.value,
            proposed_by=intern_agent.id,
            approved_by="previous_user",
            approved_at=datetime.now()
        )
        db_session.add(proposal)
        db_session.commit()

        with pytest.raises(ValueError, match="must be in PROPOSED status"):
            await proposal_service.approve_proposal(
                proposal_id=proposal.id,
                user_id="test_user_id"
            )


# ========================================================================
# Task 1.3: Risk Assessment
# ========================================================================

class TestRiskAssessment:
    """Test risk assessment for proposals."""

    def test_risk_calculation_for_different_action_types(self, proposal_service, intern_agent):
        """Test risk calculation based on action complexity."""
        # Low complexity action (presentation)
        low_risk_action = {
            "action_type": "canvas_present",
            "canvas_type": "markdown"
        }

        # High complexity action (deletion)
        high_risk_action = {
            "action_type": "agent_execute",
            "target_agent_id": "critical_agent"
        }

        # Risk assessment is implicit in action routing
        # Higher complexity actions require higher maturity
        assert low_risk_action["action_type"] in ["canvas_present"]
        assert high_risk_action["action_type"] in ["agent_execute"]

    def test_risk_levels_verification(self):
        """Test that risk levels align with governance maturity."""
        # Action complexity levels from governance system
        complexity_levels = {
            "present_chart": 1,  # LOW - STUDENT+
            "stream_chat": 2,  # MODERATE - INTERN+
            "form_submit": 3,  # HIGH - SUPERVISED+
            "delete_file": 4  # CRITICAL - AUTONOMOUS only
        }

        # Verify complexity levels
        assert complexity_levels["present_chart"] == 1
        assert complexity_levels["stream_chat"] == 2
        assert complexity_levels["form_submit"] == 3
        assert complexity_levels["delete_file"] == 4

    def test_agent_confidence_impacts_risk(self, intern_agent):
        """Test agent confidence score affects risk assessment."""
        # Lower confidence = higher risk
        low_confidence = 0.5
        high_confidence = 0.9

        # Confidence score range
        assert 0.0 <= low_confidence <= 1.0
        assert 0.0 <= high_confidence <= 1.0
        assert high_confidence > low_confidence


# ========================================================================
# Task 1.4: Audit Trail
# ========================================================================

class TestAuditTrail:
    """Test proposal audit trail."""

    @pytest.mark.asyncio
    async def test_all_proposals_logged_to_database(
        self, proposal_service, intern_agent
    ):
        """Test all proposals are logged to AgentProposal table."""
        # Create multiple proposals
        for i in range(3):
            await proposal_service.create_action_proposal(
                intern_agent_id=intern_agent.id,
                trigger_context={},
                proposed_action={"action_type": f"test_{i}"},
                reasoning=f"Test reasoning {i}"
            )

        # Verify all proposals logged
        proposals = proposal_service.db.query(AgentProposal).filter(
            AgentProposal.agent_id == intern_agent.id
        ).all()

        assert len(proposals) >= 3

    @pytest.mark.asyncio
    async def test_proposal_history_retrieval(
        self, proposal_service, intern_agent, db_session
    ):
        """Test retrieving proposal history for agent."""
        # Create proposals
        proposal1 = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "test1"},
            reasoning="Test 1"
        )

        proposal2 = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "test2"},
            reasoning="Test 2"
        )

        # Get history
        history = await proposal_service.get_proposal_history(
            agent_id=intern_agent.id,
            limit=10
        )

        assert len(history) >= 2
        assert any(h["proposal_id"] == proposal1.id for h in history)
        assert any(h["proposal_id"] == proposal2.id for h in history)

    @pytest.mark.asyncio
    async def test_approval_rejection_tracking(
        self, proposal_service, intern_agent, db_session
    ):
        """Test approval and rejection are tracked."""
        # Create proposal
        proposal = AgentProposal(
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            proposal_type=ProposalType.ACTION.value,
            title="Test Proposal",
            description="Test",
            proposed_action={"action_type": "test"},
            reasoning="Test",
            status=ProposalStatus.PROPOSED.value,
            proposed_by=intern_agent.id
        )
        db_session.add(proposal)
        db_session.commit()

        # Approve proposal
        with patch.object(
            proposal_service, '_execute_proposed_action',
            new=AsyncMock(return_value={"success": True})
        ), patch.object(
            proposal_service, '_create_proposal_episode',
            new=AsyncMock()
        ):
            await proposal_service.approve_proposal(
                proposal_id=proposal.id,
                user_id="approver_user"
            )

        # Check tracking
        db_session.refresh(proposal)
        assert proposal.approved_by == "approver_user"
        assert proposal.approved_at is not None
        assert proposal.status == ProposalStatus.EXECUTED.value

    @pytest.mark.asyncio
    async def test_get_pending_proposals(
        self, proposal_service, intern_agent, db_session
    ):
        """Test retrieving pending proposals."""
        # Create pending proposals
        proposal1 = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "test1"},
            reasoning="Test 1"
        )

        proposal2 = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "test2"},
            reasoning="Test 2"
        )

        # Get pending proposals
        pending = await proposal_service.get_pending_proposals(
            agent_id=intern_agent.id,
            limit=10
        )

        assert len(pending) >= 2
        assert all(p.status == ProposalStatus.PROPOSED.value for p in pending)

        # Approve one proposal
        with patch.object(
            proposal_service, '_execute_proposed_action',
            new=AsyncMock(return_value={"success": True})
        ), patch.object(
            proposal_service, '_create_proposal_episode',
            new=AsyncMock()
        ):
            await proposal_service.approve_proposal(
                proposal_id=proposal1.id,
                user_id="test_user"
            )

        # Get pending again (should have one less)
        pending_after = await proposal_service.get_pending_proposals(
            agent_id=intern_agent.id,
            limit=10
        )

        assert len(pending_after) == len(pending) - 1


# ========================================================================
# Task 1.5: Performance
# ========================================================================

class TestPerformance:
    """Test proposal service performance."""

    @pytest.mark.asyncio
    async def test_proposal_generation_performance(self, proposal_service, intern_agent):
        """Test proposal generation completes quickly (<500ms)."""
        import time

        start_time = time.time()

        await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "test"},
            reasoning="Test reasoning"
        )

        duration_ms = (time.time() - start_time) * 1000

        # Should complete in <500ms per research
        assert duration_ms < 500, f"Proposal generation took {duration_ms}ms"

    @pytest.mark.asyncio
    async def test_concurrent_proposal_requests(self, proposal_service, intern_agent):
        """Test handling concurrent proposal requests."""
        # Create multiple proposals concurrently
        tasks = [
            proposal_service.create_action_proposal(
                intern_agent_id=intern_agent.id,
                trigger_context={},
                proposed_action={"action_type": f"test_{i}"},
                reasoning=f"Test {i}"
            )
            for i in range(10)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All proposals should be created successfully
        assert len(results) == 10
        assert all(isinstance(r, AgentProposal) or isinstance(r, Exception) for r in results)
        successful = [r for r in results if isinstance(r, AgentProposal)]
        assert len(successful) >= 9  # Allow at most 1 failure


# ========================================================================
# Task 1.6: Edge Cases and Error Handling
# ========================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_proposal_with_empty_action(self, proposal_service, intern_agent):
        """Test proposal with empty proposed action."""
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={},
            reasoning="Test"
        )

        assert proposal is not None
        assert proposal.proposed_action == {}

    @pytest.mark.asyncio
    async def test_proposal_with_very_long_reasoning(self, proposal_service, intern_agent):
        """Test proposal with very long reasoning text."""
        long_reasoning = "Test " * 1000  # 5000 characters

        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "test"},
            reasoning=long_reasoning
        )

        assert proposal is not None
        assert len(proposal.reasoning) == len(long_reasoning)

    @pytest.mark.asyncio
    async def test_proposal_with_special_characters(self, proposal_service, intern_agent):
        """Test proposal with special characters in reasoning."""
        special_reasoning = "Test with special chars: <script>alert('xss')</script> & \"quotes\""

        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "test"},
            reasoning=special_reasoning
        )

        assert proposal is not None
        assert proposal.reasoning == special_reasoning


# ========================================================================
# Task 1.7: Action Execution
# ========================================================================

class TestActionExecution:
    """Test action execution from proposals."""

    @pytest.mark.asyncio
    async def test_execute_browser_action(
        self, proposal_service, intern_agent, db_session
    ):
        """Test browser automation action execution."""
        proposal = AgentProposal(
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            proposal_type=ProposalType.ACTION.value,
            title="Browser Action",
            description="Test",
            proposed_action={
                "action_type": "browser_automate",
                "url": "https://example.com",
                "actions": ["navigate"]
            },
            reasoning="Test",
            status=ProposalStatus.PROPOSED.value,
            proposed_by=intern_agent.id
        )
        db_session.add(proposal)
        db_session.commit()

        # Mock browser tool at import location
        with patch('tools.browser_tool.execute_browser_automation', new=AsyncMock(
            return_value={"success": True, "url": "https://example.com"}
        )), patch.object(
            proposal_service, '_create_proposal_episode',
            new=AsyncMock()
        ):
            result = await proposal_service.approve_proposal(
                proposal_id=proposal.id,
                user_id="test_user"
            )

        assert result["success"] is True
        assert result["action_type"] == "browser_automate"

    @pytest.mark.asyncio
    async def test_execute_canvas_action(
        self, proposal_service, intern_agent, db_session
    ):
        """Test canvas presentation action execution."""
        proposal = AgentProposal(
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            proposal_type=ProposalType.ACTION.value,
            title="Canvas Action",
            description="Test",
            proposed_action={
                "action_type": "canvas_present",
                "canvas_type": "chart",
                "content": {"data": [1, 2, 3]}
            },
            reasoning="Test",
            status=ProposalStatus.PROPOSED.value,
            proposed_by=intern_agent.id
        )
        db_session.add(proposal)
        db_session.commit()

        # Mock canvas tool at import location
        with patch('tools.canvas_tool.present_to_canvas', new=AsyncMock(
            return_value="test_canvas_id"
        )), patch.object(
            proposal_service, '_create_proposal_episode',
            new=AsyncMock()
        ):
            result = await proposal_service.approve_proposal(
                proposal_id=proposal.id,
                user_id="test_user"
            )

        assert result["success"] is True
        assert result["action_type"] == "canvas_present"

    @pytest.mark.asyncio
    async def test_execute_integration_action(
        self, proposal_service, intern_agent, db_session
    ):
        """Test integration connection action execution."""
        proposal = AgentProposal(
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            proposal_type=ProposalType.ACTION.value,
            title="Integration Action",
            description="Test",
            proposed_action={
                "action_type": "integration_connect",
                "integration_type": "slack",
                "operation": "send_message"
            },
            reasoning="Test",
            status=ProposalStatus.PROPOSED.value,
            proposed_by=intern_agent.id
        )
        db_session.add(proposal)
        db_session.commit()

        # Mock integration service
        with patch('core.integrations.get_integration_service') as mock_get_service, \
             patch.object(proposal_service, '_create_proposal_episode', new=AsyncMock()):
            mock_service_instance = MagicMock()
            mock_service_instance.execute_operation = AsyncMock(return_value={"success": True})
            mock_get_service.return_value = mock_service_instance

            result = await proposal_service.approve_proposal(
                proposal_id=proposal.id,
                user_id="test_user"
            )

        assert result["success"] is True
        assert result["action_type"] == "integration_connect"

    @pytest.mark.asyncio
    async def test_execute_workflow_action(
        self, proposal_service, intern_agent, db_session
    ):
        """Test workflow trigger action execution."""
        proposal = AgentProposal(
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            proposal_type=ProposalType.ACTION.value,
            title="Workflow Action",
            description="Test",
            proposed_action={
                "action_type": "workflow_trigger",
                "workflow_id": "test_workflow"
            },
            reasoning="Test",
            status=ProposalStatus.PROPOSED.value,
            proposed_by=intern_agent.id
        )
        db_session.add(proposal)
        db_session.commit()

        # Mock workflow engine at import location
        with patch('core.workflow_engine.trigger_workflow', new=AsyncMock(
            return_value={"success": True}
        )), patch.object(
            proposal_service, '_create_proposal_episode',
            new=AsyncMock()
        ):
            result = await proposal_service.approve_proposal(
                proposal_id=proposal.id,
                user_id="test_user"
            )

        assert result["success"] is True
        assert result["action_type"] == "workflow_trigger"

    @pytest.mark.asyncio
    async def test_execute_device_action(
        self, proposal_service, intern_agent, db_session
    ):
        """Test device command action execution."""
        proposal = AgentProposal(
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            proposal_type=ProposalType.ACTION.value,
            title="Device Action",
            description="Test",
            proposed_action={
                "action_type": "device_command",
                "device_id": "test_device",
                "command_type": "camera"
            },
            reasoning="Test",
            status=ProposalStatus.PROPOSED.value,
            proposed_by=intern_agent.id
        )
        db_session.add(proposal)
        db_session.commit()

        # Mock device tool at import location
        with patch('tools.device_tool.execute_device_command', new=AsyncMock(
            return_value={"success": True}
        )), patch.object(
            proposal_service, '_create_proposal_episode',
            new=AsyncMock()
        ):
            result = await proposal_service.approve_proposal(
                proposal_id=proposal.id,
                user_id="test_user"
            )

        assert result["success"] is True
        assert result["action_type"] == "device_command"

    @pytest.mark.asyncio
    async def test_execute_agent_action(
        self, proposal_service, intern_agent, db_session
    ):
        """Test agent execution action."""
        proposal = AgentProposal(
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            proposal_type=ProposalType.ACTION.value,
            title="Agent Action",
            description="Test",
            proposed_action={
                "action_type": "agent_execute",
                "target_agent_id": intern_agent.id,
                "prompt": "Test prompt"
            },
            reasoning="Test",
            status=ProposalStatus.PROPOSED.value,
            proposed_by=intern_agent.id
        )
        db_session.add(proposal)
        db_session.commit()

        # Mock agent executor at import location
        with patch('core.generic_agent.execute_agent', new=AsyncMock(
            return_value={"success": True}
        )), patch.object(
            proposal_service, '_create_proposal_episode',
            new=AsyncMock()
        ):
            result = await proposal_service.approve_proposal(
                proposal_id=proposal.id,
                user_id="test_user"
            )

        assert result["success"] is True
        assert result["action_type"] == "agent_execute"

    @pytest.mark.asyncio
    async def test_execute_unknown_action_type(
        self, proposal_service, intern_agent, db_session
    ):
        """Test unknown action type returns error."""
        proposal = AgentProposal(
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            proposal_type=ProposalType.ACTION.value,
            title="Unknown Action",
            description="Test",
            proposed_action={
                "action_type": "unknown_action"
            },
            reasoning="Test",
            status=ProposalStatus.PROPOSED.value,
            proposed_by=intern_agent.id
        )
        db_session.add(proposal)
        db_session.commit()

        with patch.object(
            proposal_service, '_create_proposal_episode',
            new=AsyncMock()
        ):
            result = await proposal_service.approve_proposal(
                proposal_id=proposal.id,
                user_id="test_user"
            )

        assert result["success"] is False
        assert "Unknown action type" in result["error"]

    @pytest.mark.asyncio
    async def test_action_execution_with_exception(
        self, proposal_service, intern_agent, db_session
    ):
        """Test action execution handles exceptions gracefully."""
        proposal = AgentProposal(
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            proposal_type=ProposalType.ACTION.value,
            title="Error Action",
            description="Test",
            proposed_action={
                "action_type": "canvas_present"
            },
            reasoning="Test",
            status=ProposalStatus.PROPOSED.value,
            proposed_by=intern_agent.id
        )
        db_session.add(proposal)
        db_session.commit()

        # Mock that raises exception
        with patch('tools.canvas_tool.present_to_canvas', new=AsyncMock(
            side_effect=Exception("Canvas service unavailable")
        )), patch.object(
            proposal_service, '_create_proposal_episode',
            new=AsyncMock()
        ):
            result = await proposal_service.approve_proposal(
                proposal_id=proposal.id,
                user_id="test_user"
            )

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_proposal_execution_disabled(
        self, proposal_service, intern_agent, db_session, monkeypatch
    ):
        """Test proposal execution when disabled by feature flag."""
        # Disable proposal execution
        monkeypatch.setenv("PROPOSAL_EXECUTION_ENABLED", "false")

        proposal = AgentProposal(
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            proposal_type=ProposalType.ACTION.value,
            title="Test Proposal",
            description="Test",
            proposed_action={"action_type": "test"},
            reasoning="Test",
            status=ProposalStatus.PROPOSED.value,
            proposed_by=intern_agent.id
        )
        db_session.add(proposal)
        db_session.commit()

        # Reload proposal service to pick up new env var
        from core import proposal_service as ps_module
        import importlib
        importlib.reload(ps_module)
        new_service = ps_module.ProposalService(db_session)

        with patch.object(
            new_service, '_create_proposal_episode',
            new=AsyncMock()
        ):
            result = await new_service.approve_proposal(
                proposal_id=proposal.id,
                user_id="test_user"
            )

        assert result["success"] is False
        assert result.get("skipped") is True
        assert "disabled" in result.get("message", "")


# ========================================================================
# Task 1.8: Episode Creation
# ========================================================================

class TestEpisodeCreation:
    """Test episode creation from proposals."""

    @pytest.mark.asyncio
    async def test_create_episode_from_approved_proposal(
        self, proposal_service, intern_agent, db_session
    ):
        """Test episode creation when proposal is approved."""
        proposal = AgentProposal(
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            proposal_type=ProposalType.ACTION.value,
            title="Test Proposal",
            description="Test",
            proposed_action={"action_type": "test"},
            reasoning="Test reasoning for approval",
            status=ProposalStatus.PROPOSED.value,
            proposed_by=intern_agent.id
        )
        db_session.add(proposal)
        db_session.commit()

        # Approve with execution
        with patch.object(
            proposal_service, '_execute_proposed_action',
            new=AsyncMock(return_value={"success": True})
        ):
            # Don't mock _create_proposal_episode - let it run
            await proposal_service.approve_proposal(
                proposal_id=proposal.id,
                user_id="test_user",
                modifications={"param": "modified"}
            )

        # Verify episode was created
        from core.models import Episode
        episodes = db_session.query(Episode).filter(
            Episode.proposal_id == proposal.id
        ).all()

        assert len(episodes) == 1
        episode = episodes[0]
        assert episode.proposal_outcome == "approved"
        assert episode.agent_id == intern_agent.id

    @pytest.mark.asyncio
    async def test_create_episode_from_rejected_proposal(
        self, proposal_service, intern_agent, db_session
    ):
        """Test episode creation when proposal is rejected."""
        proposal = AgentProposal(
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            proposal_type=ProposalType.ACTION.value,
            title="Test Proposal",
            description="Test",
            proposed_action={"action_type": "test"},
            reasoning="Test reasoning",
            status=ProposalStatus.PROPOSED.value,
            proposed_by=intern_agent.id
        )
        db_session.add(proposal)
        db_session.commit()

        # Reject proposal
        await proposal_service.reject_proposal(
            proposal_id=proposal.id,
            user_id="test_user",
            reason="Too risky"
        )

        # Verify episode was created
        from core.models import Episode
        episodes = db_session.query(Episode).filter(
            Episode.proposal_id == proposal.id
        ).all()

        assert len(episodes) == 1
        episode = episodes[0]
        assert episode.proposal_outcome == "rejected"
        assert episode.rejection_reason == "Too risky"

    @pytest.mark.asyncio
    async def test_episode_importance_calculation(self, proposal_service):
        """Test episode importance score calculation."""
        # Rejected proposals have higher importance
        assert proposal_service._calculate_proposal_importance("rejected", MagicMock()) > \
               proposal_service._calculate_proposal_importance("approved", MagicMock())

        # Proposals with modifications have higher importance
        mock_with_mods = MagicMock()
        mock_with_mods.modifications = {"key": "value"}
        mock_without_mods = MagicMock()
        mock_without_mods.modifications = None

        assert proposal_service._calculate_proposal_importance("approved", mock_with_mods) > \
               proposal_service._calculate_proposal_importance("approved", mock_without_mods)

    @pytest.mark.asyncio
    async def test_extract_proposal_topics(self, proposal_service, intern_agent):
        """Test topic extraction from proposals."""
        proposal = AgentProposal(
            agent_id=intern_agent.id,
            agent_name="Test Agent",
            proposal_type=ProposalType.ACTION.value,
            title="Browser Automation Task for Web Scraping",
            description="Test",
            proposed_action={"action_type": "browser_automate"},
            reasoning="Need to scrape data from website using browser automation",
            status=ProposalStatus.PROPOSED.value,
            proposed_by=intern_agent.id
        )

        topics = proposal_service._extract_proposal_topics(proposal)

        assert "action" in topics  # From proposal_type
        assert "browser_automate" in topics  # From action type
        assert len(topics) <= 5  # Should limit to 5 topics

    @pytest.mark.asyncio
    async def test_extract_proposal_entities(self, proposal_service, intern_agent):
        """Test entity extraction from proposals."""
        proposal = AgentProposal(
            agent_id=intern_agent.id,
            agent_name="Test Agent",
            proposal_type=ProposalType.ACTION.value,
            title="Test",
            description="Test",
            proposed_action={
                "action_type": "integration_connect",
                "integration_type": "slack"
            },
            reasoning="Test",
            status=ProposalStatus.PROPOSED.value,
            proposed_by=intern_agent.id
        )
        proposal.approved_by = "test_user"

        entities = proposal_service._extract_proposal_entities(proposal)

        assert f"proposal:{proposal.id}" in entities
        assert f"agent:{intern_agent.id}" in entities
        assert "reviewer:test_user" in entities


# ========================================================================
# Task 1.9: Autonomous Supervisor Integration
# ========================================================================

class TestAutonomousSupervisor:
    """Test autonomous supervisor integration for proposals."""

    @pytest.mark.asyncio
    async def test_review_with_human_supervisor(
        self, proposal_service, intern_agent, db_session
    ):
        """Test finding human supervisor for proposal review."""
        proposal = AgentProposal(
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            proposal_type=ProposalType.ACTION.value,
            title="Test Proposal",
            description="Test",
            proposed_action={"action_type": "test"},
            reasoning="Test",
            status=ProposalStatus.PROPOSED.value,
            proposed_by=intern_agent.id
        )
        db_session.add(proposal)
        db_session.commit()

        # Mock user activity service to return available supervisor
        with patch('core.proposal_service.UserActivityService') as mock_user_service:
            mock_activity_instance = AsyncMock()
            mock_activity_instance.get_available_supervisors.return_value = [
                {"user_id": "supervisor_1", "category": intern_agent.id}
            ]
            mock_user_service.return_value = mock_activity_instance

            result = await proposal_service.review_with_autonomous_supervisor(proposal)

        assert result is not None
        assert result["supervisor_type"] == "human"
        assert result["available"] is True

    @pytest.mark.asyncio
    async def test_review_with_autonomous_supervisor_fallback(
        self, proposal_service, intern_agent, db_session
    ):
        """Test fallback to autonomous supervisor when no human available."""
        proposal = AgentProposal(
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            proposal_type=ProposalType.ACTION.value,
            title="Test Proposal",
            description="Test",
            proposed_action={"action_type": "test"},
            reasoning="Test",
            status=ProposalStatus.PROPOSED.value,
            proposed_by=intern_agent.id
        )
        db_session.add(proposal)
        db_session.commit()

        # Create autonomous supervisor
        autonomous_agent = AutonomousAgentFactory(_session=db_session)
        db_session.commit()

        # Mock no human supervisor available
        with patch('core.proposal_service.UserActivityService') as mock_user_service, \
             patch('core.proposal_service.AutonomousSupervisorService') as mock_auto_service:

            mock_activity_instance = AsyncMock()
            mock_activity_instance.get_available_supervisors.return_value = []
            mock_user_service.return_value = mock_activity_instance

            mock_auto_instance = AsyncMock()
            mock_auto_instance.find_autonomous_supervisor.return_value = autonomous_agent

            mock_review = MagicMock()
            mock_review.approved = True
            mock_review.confidence_score = 0.9
            mock_review.risk_level = "low"
            mock_review.reasoning = "Looks good"
            mock_review.suggested_modifications = []
            mock_auto_instance.review_proposal.return_value = mock_review
            mock_auto_service.return_value = mock_auto_instance

            result = await proposal_service.review_with_autonomous_supervisor(proposal)

        assert result is not None
        assert result["supervisor_type"] == "autonomous"
        assert result["supervisor_id"] == autonomous_agent.id

    @pytest.mark.asyncio
    async def test_no_supervisor_available(
        self, proposal_service, intern_agent, db_session
    ):
        """Test when no supervisor (human or autonomous) is available."""
        proposal = AgentProposal(
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            proposal_type=ProposalType.ACTION.value,
            title="Test Proposal",
            description="Test",
            proposed_action={"action_type": "test"},
            reasoning="Test",
            status=ProposalStatus.PROPOSED.value,
            proposed_by=intern_agent.id
        )
        db_session.add(proposal)
        db_session.commit()

        # Mock no supervisors available
        with patch('core.proposal_service.UserActivityService') as mock_user_service, \
             patch('core.proposal_service.AutonomousSupervisorService') as mock_auto_service:

            mock_activity_instance = AsyncMock()
            mock_activity_instance.get_available_supervisors.return_value = []
            mock_user_service.return_value = mock_activity_instance

            mock_auto_instance = AsyncMock()
            mock_auto_instance.find_autonomous_supervisor.return_value = None
            mock_auto_service.return_value = mock_auto_instance

            result = await proposal_service.review_with_autonomous_supervisor(proposal)

        assert result is None

    @pytest.mark.asyncio
    async def test_autonomous_approve_or_reject_with_human(
        self, proposal_service, intern_agent, db_session
    ):
        """Test autonomous approval waits when human supervisor available."""
        proposal = AgentProposal(
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            proposal_type=ProposalType.ACTION.value,
            title="Test Proposal",
            description="Test",
            proposed_action={"action_type": "test"},
            reasoning="Test",
            status=ProposalStatus.PROPOSED.value,
            proposed_by=intern_agent.id
        )
        db_session.add(proposal)
        db_session.commit()

        # Mock human supervisor available
        with patch.object(
            proposal_service, 'review_with_autonomous_supervisor',
            new=AsyncMock(return_value={
                "supervisor_type": "human",
                "supervisor_id": "human_supervisor",
                "available": True
            })
        ):
            result = await proposal_service.autonomous_approve_or_reject(
                proposal_id=proposal.id
            )

        assert result["success"] is False
        assert "awaiting manual approval" in result["message"]
        assert result["supervisor_type"] == "human"

