"""
Tests for ProposalService - Agent proposal workflow and governance.

Wave 116 (2026-08-13): rewritten against the current async API
(create_action_proposal / submit_for_approval / approve_proposal /
reject_proposal / get_pending_proposals / get_proposal_history). The
previous version exercised a phantom sync API (create_proposal,
batch_approve, reviewer_id kwargs) and failed 26/26.

Coverage Goals:
- Proposal creation and validation (INTERN gate, unknown agent)
- Approval workflow (modifications, execution failure, wrong status)
- Rejection workflow with reason capture
- Governance enforcement (INTERN maturity)
- Proposal history and pending-proposal filtering
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.orm import Session

from core.models import AgentProposal, AgentRegistry, AgentStatus
from core.proposal_service import ProposalService


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def make_proposal(**overrides):
    execution_result = overrides.pop("execution_result", None)
    fields = {
        "id": "prop-1",
        "tenant_id": "default",
        "user_id": "system",
        "agent_id": "agent-123",
        "agent_name": "Intern Agent",
        "title": "Action Proposal",
        "proposal_type": "action",
        "proposal_data": {"action_type": "canvas_create", "canvas_type": "chart"},
        "status": "pending_approval",
        "created_at": datetime(2026, 8, 1, 12, 0, 0),
        "approved_by": None,
        "approved_at": None,
    }
    fields.update(overrides)
    proposal = AgentProposal(**fields)
    proposal.execution_result = execution_result
    return proposal


def make_agent(status="intern", **overrides):
    fields = {
        "id": "agent-123",
        "name": "Intern Agent",
        "category": "general",
        "confidence_score": 0.65,
        "tenant_id": "default",
        "user_id": "system",
        "status": status,
    }
    fields.update(overrides)
    return AgentRegistry(**fields)


@pytest.fixture
def mock_db():
    return Mock(spec=Session)


@pytest.fixture
def service(mock_db):
    return ProposalService(db=mock_db)


class TestProposalCreation:
    """Proposal creation and validation."""

    def test_create_proposal_intern_agent(self, mock_db, service):
        """INTERN agents can create proposals for human review."""
        mock_agent = make_agent()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent

        proposal = run(service.create_action_proposal(
            intern_agent_id="agent-123",
            trigger_context={"query": "create a chart"},
            proposed_action={"action_type": "canvas_create", "canvas_type": "chart"},
            reasoning="The user asked for a chart",
        ))

        assert proposal.agent_id == "agent-123"
        assert proposal.status == "pending_approval"
        assert proposal.proposal_type == "action"
        assert "chart" in proposal.title or proposal.title is not None

    def test_create_proposal_with_title_and_selector_candidates(
        self, mock_db, service
    ):
        mock_agent = make_agent()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent

        proposal = run(service.create_action_proposal(
            intern_agent_id="agent-123",
            trigger_context={},
            proposed_action={
                "action_type": "browser_click",
                "selector_candidates": [
                    {"selector": "#submit", "match_count": 3, "is_text_only": False},
                ],
                "match_rationale": "best match",
                "match_score": 0.9,
                "chosen_index": 0,
                "per_field_confidence": {"email": {"level": "high", "score": 0.8}},
            },
            reasoning="clicking submit",
            canvas_id="canvas-1",
            session_id="session-1",
            title="Custom title",
        ))

        assert proposal.canvas_id == "canvas-1"
        assert proposal.session_id == "session-1"
        assert proposal.title == "Custom title"
        assert "Selector candidates" in proposal.description

    def test_create_proposal_unknown_agent_raises(self, mock_db, service):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(ValueError, match="not found"):
            run(service.create_action_proposal(
                intern_agent_id="ghost",
                trigger_context={},
                proposed_action={"action_type": "canvas_create"},
                reasoning="",
            ))

    def test_create_proposal_student_agent_blocked(self, mock_db, service):
        """STUDENT agents cannot create proposals (hard block, not warning)."""
        mock_agent = make_agent(status="student")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent

        with pytest.raises(PermissionError, match="not an INTERN agent"):
            run(service.create_action_proposal(
                intern_agent_id="agent-123",
                trigger_context={},
                proposed_action={"action_type": "canvas_create"},
                reasoning="",
            ))


class TestSubmitForApproval:
    """Submission state machine."""

    def test_submit_pending_proposal(self, service):
        proposal = make_proposal()
        run(service.submit_for_approval(proposal))  # must not raise

    def test_submit_wrong_status_raises(self, service):
        proposal = make_proposal(status="executed")
        with pytest.raises(ValueError, match="PENDING_APPROVAL"):
            run(service.submit_for_approval(proposal))


class TestApproval:
    """Approval workflow."""

    def test_approve_proposal_executes_action(self, mock_db, service):
        proposal = make_proposal()
        mock_db.query.return_value.filter.return_value.first.return_value = proposal

        with patch.object(
            service, "_execute_proposed_action_with",
            new=AsyncMock(return_value={"success": True, "result": "done"}),
        ), patch.object(service, "_create_proposal_episode", new=AsyncMock()), \
             patch("core.proposal_service.AgentLearningEnhanced") as learning_cls:
            learning = learning_cls.return_value
            learning.record_user_correction = AsyncMock()
            result = run(service.approve_proposal("prop-1", "user-1"))

        assert result["success"] is True
        assert proposal.status == "executed"
        assert proposal.approved_by == "user-1"
        assert proposal.execution_result["success"] is True

    def test_approve_proposal_not_found(self, mock_db, service):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(ValueError, match="not found"):
            run(service.approve_proposal("ghost", "user-1"))

    def test_approve_wrong_status_raises(self, mock_db, service):
        proposal = make_proposal(status="rejected")
        mock_db.query.return_value.filter.return_value.first.return_value = proposal
        with pytest.raises(ValueError, match="PENDING_APPROVAL"):
            run(service.approve_proposal("prop-1", "user-1"))

    def test_approve_with_modifications_merges_action(self, mock_db, service):
        proposal = make_proposal()
        mock_db.query.return_value.filter.return_value.first.return_value = proposal

        with patch.object(
            service, "_execute_proposed_action_with",
            new=AsyncMock(return_value={"success": True, "result": "ok"}),
        ), patch.object(service, "_create_proposal_episode", new=AsyncMock()), \
             patch("core.proposal_service.AgentLearningEnhanced") as learning_cls:
            learning = learning_cls.return_value
            learning.record_user_correction = AsyncMock()
            run(service.approve_proposal(
                "prop-1", "user-1", modifications={"canvas_type": "bar"}))

        assert proposal.proposal_data["canvas_type"] == "bar"
        assert proposal.modifications == {"canvas_type": "bar"}
        learning.record_user_correction.assert_awaited_once()

    def test_approve_execution_failure_marks_failed(self, mock_db, service):
        proposal = make_proposal()
        mock_db.query.return_value.filter.return_value.first.return_value = proposal

        with patch.object(
            service, "_execute_proposed_action_with",
            new=AsyncMock(return_value={"success": False, "error": "boom"}),
        ), patch.object(service, "_create_proposal_episode", new=AsyncMock()), \
             patch("core.proposal_service.AgentLearningEnhanced"):
            result = run(service.approve_proposal("prop-1", "user-1"))

        assert result["success"] is False
        assert proposal.status == "execution_failed"

    def test_approve_execution_exception_marks_failed_and_raises(
        self, mock_db, service
    ):
        proposal = make_proposal()
        mock_db.query.return_value.filter.return_value.first.return_value = proposal

        with patch.object(
            service, "_execute_proposed_action_with",
            new=AsyncMock(side_effect=RuntimeError("executor exploded")),
        ), patch("core.proposal_service.AgentLearningEnhanced"):
            with pytest.raises(RuntimeError, match="executor exploded"):
                run(service.approve_proposal("prop-1", "user-1"))

        assert proposal.status == "execution_failed"
        assert proposal.execution_result["success"] is False


class TestRejection:
    """Rejection workflow."""

    def test_reject_proposal_records_reason(self, mock_db, service):
        proposal = make_proposal()
        mock_db.query.return_value.filter.return_value.first.return_value = proposal

        with patch.object(service, "_create_proposal_episode", new=AsyncMock()), \
             patch("core.proposal_service.AgentLearningEnhanced") as learning_cls:
            learning = learning_cls.return_value
            learning.record_rejection = AsyncMock()
            run(service.reject_proposal("prop-1", "user-1", "not needed"))

        assert proposal.status == "rejected"
        assert proposal.approved_by == "user-1"
        assert proposal.execution_result["reason"] == "not needed"
        assert proposal.execution_result["rejected"] is True
        learning.record_rejection.assert_awaited_once()

    def test_reject_proposal_not_found(self, mock_db, service):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(ValueError, match="not found"):
            run(service.reject_proposal("ghost", "user-1", "nope"))

    def test_reject_already_executed_proposal_raises(self, mock_db, service):
        """A proposal that already ran must not be flipped to REJECTED."""
        proposal = make_proposal(status="executed")
        mock_db.query.return_value.filter.return_value.first.return_value = proposal
        with pytest.raises(ValueError, match="PENDING_APPROVAL"):
            run(service.reject_proposal("prop-1", "user-1", "too late"))


class TestQueries:
    """Pending proposals and history."""

    def test_get_pending_all(self, service):
        service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        assert run(service.get_pending_proposals()) == []

    def test_get_pending_filters(self, service):
        proposals = [make_proposal(), make_proposal(id="prop-2")]
        deep = service.db.query.return_value.filter.return_value
        deepest = deep.filter.return_value.filter.return_value.filter.return_value
        deepest.order_by.return_value.limit.return_value.all.return_value = proposals
        result = run(service.get_pending_proposals(
            agent_id="agent-123", canvas_id="canvas-1", tenant_id="default", limit=10))
        assert result == proposals
        assert deep.filter.call_count >= 1  # agent filter applied

    def test_get_proposal_history(self, service):
        proposals = [
            make_proposal(id="p1", status="executed", approved_by="user-1",
                          approved_at=datetime(2026, 8, 2, 9, 0, 0),
                          execution_result={"success": True}),
            make_proposal(id="p2", status="rejected"),
        ]
        service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = proposals

        history = run(service.get_proposal_history("agent-123"))

        assert len(history) == 2
        assert history[0]["proposal_id"] == "p1"
        assert history[0]["status"] == "executed"
        assert history[0]["approved_at"] is not None
        assert history[0]["approved_by"] == "user-1"
        assert history[1]["approved_at"] is None
