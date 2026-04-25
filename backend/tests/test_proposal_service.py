"""
Tests for ProposalService - Agent proposal workflow and governance.

Coverage Goals (25-30% on 1209 lines):
- Proposal creation and validation
- Proposal approval workflow
- Proposal execution
- Governance enforcement (INTERN maturity)
- Proposal history and audit trail
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.models import (
    AgentProposal,
    AgentRegistry,
    AgentStatus
)


class TestProposalCreation:
    """Test proposal creation and validation."""

    def test_create_proposal_intern_agent(self):
        """INTERN agents can create proposals for human review."""
        mock_db = Mock(spec=Session)
        mock_agent = Mock()
        mock_agent.id = "agent-123"
        mock_agent.status = "INTERN"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Import proposal service
        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        proposal = service.create_proposal(
            agent_id="agent-123",
            action_type="canvas_create",
            proposal_data={"canvas_type": "chart"}
        )

        assert proposal.agent_id == "agent-123"
        assert proposal.action_type == "canvas_create"
        assert proposal.status == "pending"

    def test_create_proposal_supervised_agent(self):
        """SUPERVISED agents can create proposals."""
        mock_db = Mock(spec=Session)
        mock_agent = Mock()
        mock_agent.status = "SUPERVISED"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent
        mock_db.add = Mock()
        mock_db.commit = Mock()

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        proposal = service.create_proposal(
            agent_id="agent-456",
            action_type="form_submission",
            proposal_data={"form_id": "form-123"}
        )

        assert proposal.status == "pending"

    def test_create_proposal_student_agent_blocked(self):
        """STUDENT agents cannot create proposals."""
        mock_db = Mock(spec=Session)
        mock_agent = Mock()
        mock_agent.status = "STUDENT"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        with pytest.raises(PermissionError) as exc_info:
            service.create_proposal(
                agent_id="agent-789",
                action_type="canvas_create",
                proposal_data={}
            )

        assert "STUDENT" in str(exc_info.value)

    def test_proposal_validation_action_type(self):
        """Proposal action_type is validated."""
        mock_db = Mock(spec=Session)
        mock_agent = Mock()
        mock_agent.status = "INTERN"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        # Valid action types
        valid_types = ["canvas_create", "form_submit", "browser_automate"]

        for action_type in valid_types:
            proposal = service.create_proposal(
                agent_id="agent-123",
                action_type=action_type,
                proposal_data={}
            )
            assert proposal.action_type == action_type

    def test_proposal_validation_schema(self):
        """Proposal data is validated against schema."""
        mock_db = Mock(spec=Session)
        mock_agent = Mock()
        mock_agent.status = "INTERN"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent
        mock_db.add = Mock()
        mock_db.commit = Mock()

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        # Valid proposal data
        proposal_data = {
            "canvas_type": "chart",
            "data_source": "sales_db",
            "visualization": "line"
        }

        proposal = service.create_proposal(
            agent_id="agent-123",
            action_type="canvas_create",
            proposal_data=proposal_data
        )

        assert proposal.proposal_data == proposal_data


class TestProposalApproval:
    """Test proposal approval workflow."""

    def test_approve_proposal(self):
        """Human reviewer can approve pending proposal."""
        mock_db = Mock(spec=Session)
        mock_proposal = Mock()
        mock_proposal.id = "proposal-123"
        mock_proposal.status = "pending"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_proposal
        mock_db.commit = Mock()

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        approved_proposal = service.approve_proposal(
            proposal_id="proposal-123",
            reviewer_id="user-456",
            comments="Looks good"
        )

        assert approved_proposal.status == "approved"

    def test_reject_proposal(self):
        """Human reviewer can reject pending proposal."""
        mock_db = Mock(spec=Session)
        mock_proposal = Mock()
        mock_proposal.id = "proposal-123"
        mock_proposal.status = "pending"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_proposal
        mock_db.commit = Mock()

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        rejected_proposal = service.reject_proposal(
            proposal_id="proposal-123",
            reviewer_id="user-456",
            rejection_reason="Security concern"
        )

        assert rejected_proposal.status == "rejected"

    def test_approve_already_approved_proposal_fails(self):
        """Cannot approve a proposal that's already approved."""
        mock_db = Mock(spec=Session)
        mock_proposal = Mock()
        mock_proposal.id = "proposal-123"
        mock_proposal.status = "approved"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_proposal

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        with pytest.raises(ValueError) as exc_info:
            service.approve_proposal(
                proposal_id="proposal-123",
                reviewer_id="user-456"
            )

        assert "already approved" in str(exc_info.value).lower()

    def test_batch_approve_proposals(self):
        """Approve multiple proposals at once."""
        mock_db = Mock(spec=Session)

        mock_proposals = [
            Mock(id="p1", status="pending"),
            Mock(id="p2", status="pending"),
            Mock(id="p3", status="pending"),
        ]

        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = mock_proposals
        mock_db.query.return_value.filter.return_value = mock_query
        mock_db.commit = Mock()

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        approved_count = service.batch_approve(
            proposal_ids=["p1", "p2", "p3"],
            reviewer_id="user-789"
        )

        assert approved_count == 3


class TestProposalExecution:
    """Test proposal execution after approval."""

    def test_execute_approved_proposal(self):
        """Approved proposals can be executed."""
        mock_db = Mock(spec=Session)
        mock_proposal = Mock()
        mock_proposal.id = "proposal-123"
        mock_proposal.status = "approved"
        mock_proposal.action_type = "canvas_create"
        mock_proposal.proposal_data = {"canvas_type": "chart"}

        mock_db.query.return_value.filter.return_value.first.return_value = mock_proposal
        mock_db.commit = Mock()

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        result = service.execute_proposal(
            proposal_id="proposal-123"
        )

        assert result["success"] is True

    def test_execute_rejected_proposal_fails(self):
        """Rejected proposals cannot be executed."""
        mock_db = Mock(spec=Session)
        mock_proposal = Mock()
        mock_proposal.id = "proposal-123"
        mock_proposal.status = "rejected"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_proposal

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        with pytest.raises(ValueError) as exc_info:
            service.execute_proposal(
                proposal_id="proposal-123"
            )

        assert "rejected" in str(exc_info.value).lower()

    def test_execute_pending_proposal_fails(self):
        """Pending proposals cannot be executed (must be approved first)."""
        mock_db = Mock(spec=Session)
        mock_proposal = Mock()
        mock_proposal.id = "proposal-123"
        mock_proposal.status = "pending"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_proposal

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        with pytest.raises(ValueError) as exc_info:
            service.execute_proposal(
                proposal_id="proposal-123"
            )

        assert "not approved" in str(exc_info.value).lower()


class TestGovernanceEnforcement:
    """Test governance enforcement for proposals."""

    def test_intern_maturity_required(self):
        """Only INTERN+ agents can create proposals."""
        mock_db = Mock(spec=Session)
        mock_student_agent = Mock()
        mock_student_agent.status = "STUDENT"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_student_agent

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        with pytest.raises(PermissionError):
            service.create_proposal(
                agent_id="student-agent",
                action_type="canvas_create",
                proposal_data={}
            )

    def test_supervised_maturity_allowed(self):
        """SUPERVISED agents can create proposals."""
        mock_db = Mock(spec=Session)
        mock_agent = Mock()
        mock_agent.status = "SUPERVISED"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent
        mock_db.add = Mock()
        mock_db.commit = Mock()

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        proposal = service.create_proposal(
            agent_id="supervised-agent",
            action_type="canvas_create",
            proposal_data={}
        )

        assert proposal is not None

    def test_autonomous_maturity_allowed(self):
        """AUTONOMOUS agents can create proposals."""
        mock_db = Mock(spec=Session)
        mock_agent = Mock()
        mock_agent.status = "AUTONOMOUS"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent
        mock_db.add = Mock()
        mock_db.commit = Mock()

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        proposal = service.create_proposal(
            agent_id="autonomous-agent",
            action_type="canvas_create",
            proposal_data={}
        )

        assert proposal is not None


class TestProposalHistory:
    """Test proposal history and audit trail."""

    def test_get_proposal_history(self):
        """Get full history of proposals for an agent."""
        mock_db = Mock(spec=Session)

        mock_proposals = [
            Mock(id="p1", status="approved", created_at=datetime.utcnow()),
            Mock(id="p2", status="rejected", created_at=datetime.utcnow()),
            Mock(id="p3", status="pending", created_at=datetime.utcnow()),
        ]

        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = mock_proposals
        mock_db.query.return_value.filter.return_value = mock_query

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        history = service.get_agent_proposal_history(
            agent_id="agent-123"
        )

        assert len(history) == 3

    def test_proposal_audit_trail(self):
        """Proposal has complete audit trail of status changes."""
        mock_db = Mock(spec=Session)
        mock_proposal = Mock()
        mock_proposal.id = "proposal-123"

        mock_audit_trail = [
            {"status": "pending", "timestamp": datetime.utcnow(), "user_id": None},
            {"status": "approved", "timestamp": datetime.utcnow(), "user_id": "user-456"},
        ]

        mock_proposal.audit_trail = mock_audit_trail

        mock_db.query.return_value.filter.return_value.first.return_value = mock_proposal

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        audit_trail = service.get_proposal_audit_trail("proposal-123")

        assert len(audit_trail) == 2
        assert audit_trail[1]["status"] == "approved"

    def test_proposal_versioning(self):
        """Proposal changes are versioned."""
        mock_db = Mock(spec=Session)
        mock_proposal = Mock()
        mock_proposal.id = "proposal-123"
        mock_proposal.version = 2

        mock_db.query.return_value.filter.return_value.first.return_value = mock_proposal

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        version = service.get_proposal_version("proposal-123")

        assert version == 2


class TestProposalExpiration:
    """Test proposal expiration and timeout."""

    def test_proposal_expiration_timeout(self):
        """Proposals expire after timeout period."""
        mock_db = Mock(spec=Session)
        mock_proposal = Mock()
        mock_proposal.id = "proposal-123"
        mock_proposal.status = "pending"
        mock_proposal.created_at = datetime.utcnow() - timedelta(hours=25)

        mock_db.query.return_value.filter.return_value.first.return_value = mock_proposal
        mock_db.commit = Mock()

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        # Check if proposal is expired
        is_expired = service.is_proposal_expired("proposal-123")

        assert is_expired is True

    def test_auto_reject_expired_proposals(self):
        """Expired proposals are automatically rejected."""
        mock_db = Mock(spec=Session)

        mock_proposals = [
            Mock(id="p1", status="pending", created_at=datetime.utcnow() - timedelta(hours=25)),
            Mock(id="p2", status="pending", created_at=datetime.utcnow() - timedelta(hours=30)),
        ]

        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = mock_proposals
        mock_db.query.return_value.filter.return_value = mock_query
        mock_db.commit = Mock()

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        expired_count = service.auto_reject_expired_proposals()

        assert expired_count == 2


class TestProposalNotifications:
    """Test notification system for pending proposals."""

    def test_notify_pending_proposals(self):
        """Notify reviewers of pending proposals."""
        mock_db = Mock(spec=Session)

        mock_proposals = [
            Mock(id="p1", agent_id="agent-1", action_type="canvas_create"),
            Mock(id="p2", agent_id="agent-2", action_type="form_submit"),
        ]

        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = mock_proposals
        mock_db.query.return_value.filter.return_value = mock_query

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        pending = service.get_pending_proposals()

        assert len(pending) == 2

    def test_notify_approval_alerts(self):
        """Agents are notified when proposals are approved."""
        mock_db = Mock(spec=Session)
        mock_proposal = Mock()
        mock_proposal.id = "proposal-123"
        mock_proposal.agent_id = "agent-456"
        mock_proposal.status = "approved"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_proposal

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        # Simulate notification
        notification = service.create_approval_notification("proposal-123")

        assert notification["agent_id"] == "agent-456"
        assert notification["proposal_id"] == "proposal-123"
        assert notification["status"] == "approved"


class TestProposalStatistics:
    """Test proposal statistics and metrics."""

    def test_get_proposal_statistics(self):
        """Get statistics for agent proposals."""
        mock_db = Mock(spec=Session)

        mock_stats = {
            "total": 100,
            "pending": 10,
            "approved": 80,
            "rejected": 10,
            "approval_rate": 0.80
        }

        mock_query = Mock()
        mock_query.filter.return_value.count.return_value = 100
        mock_db.query.return_value.filter.return_value = mock_query

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        stats = service.get_proposal_statistics("agent-123")

        assert stats["total"] == 100

    def test_approval_rate_calculation(self):
        """Calculate approval rate for agent."""
        mock_db = Mock(spec=Session)

        mock_proposals = [
            Mock(status="approved"),
            Mock(status="approved"),
            Mock(status="rejected"),
            Mock(status="pending"),
        ]

        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = mock_proposals
        mock_db.query.return_value.filter.return_value = mock_query

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        approval_rate = service.calculate_approval_rate("agent-123")

        assert approval_rate == 0.5  # 2 approved out of 4 total


class TestErrorHandling:
    """Test error handling in proposal operations."""

    def test_proposal_not_found(self):
        """Return None when proposal doesn't exist."""
        mock_db = Mock(spec=Session)

        mock_db.query.return_value.filter.return_value.first.return_value = None

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        proposal = service.get_proposal("nonexistent-proposal")

        assert proposal is None

    def test_agent_not_found_for_proposal(self):
        """Raise error when agent doesn't exist."""
        mock_db = Mock(spec=Session)

        mock_db.query.return_value.filter.return_value.first.return_value = None

        from core.proposal_service import ProposalService
        service = ProposalService(db=mock_db)

        with pytest.raises(ValueError):
            service.create_proposal(
                agent_id="nonexistent-agent",
                action_type="canvas_create",
                proposal_data={}
            )
