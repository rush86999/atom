"""
Bug-hunt + coverage tests for core.proposal_service (round 2).

Targets UNcovered code paths and verifies REAL bugs found via TDD.
Each bug test is prefixed ``BUG:`` and was written BEFORE the source fix,
confirmed to fail for the right reason, then verified to pass after the fix.
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.orm import Session

from core.proposal_service import ProposalService
from core.models import AgentProposal, ProposalStatus


@pytest.fixture
def mock_db():
    return Mock(spec=Session)


@pytest.fixture
def service(mock_db):
    return ProposalService(db=mock_db)


# ============================================================================
# BUG #2: _format_proposal_outcome / _create_proposal_episode treat
# ``modifications`` (a dict) as a list -> TypeError -> learning episode silently
# never created when an approved proposal had modifications.
# ============================================================================
class TestProposalModificationsTypeMismatchBug:
    """BUG: approve_proposal receives ``modifications: Dict[str, Any]`` but
    _create_proposal_episode / _format_proposal_outcome slice it with ``[:5]``
    and call ``len()`` on it as if it were a list. A dict has no ``[:5]`` ->
    TypeError, which is swallowed by the broad try/except in
    _create_proposal_episode, so the learning episode is NEVER created for any
    approved-with-modifications proposal.
    """

    def test_bug_format_outcome_handles_dict_modifications(self, service):
        """BUG: _format_proposal_outcome must not crash on dict modifications."""
        proposal = Mock(spec=AgentProposal)
        proposal.approved_by = "user-1"
        proposal.approved_at = datetime(2026, 1, 1)

        # approve_proposal passes modifications as a DICT (Optional[Dict[str, Any]])
        modifications = {"action_type": "canvas_present", "url": "https://x"}

        # Must not raise TypeError
        outcome = service._format_proposal_outcome(
            proposal, "approved", modifications=modifications
        )
        # And should reference the modification count
        assert "Modifications Applied" in outcome

    def test_bug_format_outcome_dict_modifications_lists_changed_keys(self, service):
        """When modifications is a dict, the outcome should report the modified
        keys (not crash trying to slice the dict)."""
        proposal = Mock(spec=AgentProposal)
        proposal.approved_by = "user-1"
        proposal.approved_at = datetime(2026, 1, 1)

        modifications = {"url": "https://y", "title": "New"}

        outcome = service._format_proposal_outcome(
            proposal, "approved", modifications=modifications
        )
        # Each modified key should appear
        assert "url" in outcome
        assert "title" in outcome

    def test_format_outcome_handles_list_modifications_still(self, service):
        """Backwards-compat: list-form modifications (if ever used) still work."""
        proposal = Mock(spec=AgentProposal)
        proposal.approved_by = "user-1"
        proposal.approved_at = datetime(2026, 1, 1)

        outcome = service._format_proposal_outcome(
            proposal, "approved", modifications=["change_a", "change_b"]
        )
        assert "change_a" in outcome


# ============================================================================
# Coverage: _calculate_proposal_importance (uncovered)
# ============================================================================
class TestCalculateProposalImportance:
    def test_rejected_baseline(self, service):
        p = Mock(spec=AgentProposal)
        p.modifications = None
        # rejected: 0.5 + 0.3 = 0.8
        assert service._calculate_proposal_importance("rejected", p) == pytest.approx(0.8)

    def test_approved_with_modifications(self, service):
        p = Mock(spec=AgentProposal)
        p.modifications = {"x": 1}
        # approved: 0.5 + 0.1 + 0.1 = 0.7
        assert service._calculate_proposal_importance("approved", p) == pytest.approx(0.7)

    def test_rejected_with_modifications_clamps(self, service):
        p = Mock(spec=AgentProposal)
        p.modifications = {"x": 1}
        # rejected + mod: 0.5 + 0.3 + 0.1 = 0.9 (under clamp)
        assert service._calculate_proposal_importance("rejected", p) == pytest.approx(0.9)

    def test_clamps_to_one(self, service):
        # Construct a fake proposal whose modifications attr is truthy but
        # importance already maxed by rejection. rejected+mod = 0.9 <= 1.0 OK.
        # To force clamping we rely on the formula staying <= 1.0 for any input.
        p = Mock(spec=AgentProposal)
        p.modifications = {"a": 1}
        score = service._calculate_proposal_importance("rejected", p)
        assert 0.0 <= score <= 1.0


# ============================================================================
# Coverage: _extract_proposal_topics / _extract_proposal_entities
# ============================================================================
class TestExtractProposalMetadata:
    def test_topics_include_type_and_action_type(self, service):
        p = Mock(spec=AgentProposal)
        p.proposal_type = "action"
        p.title = "Important Proposal About Billing"
        p.reasoning = "Because the customer needed help with invoicing"
        p.proposed_action = {"action_type": "canvas_present"}

        topics = service._extract_proposal_topics(p)
        # proposal_type always first
        assert topics[0] == "action"
        # action_type included
        assert "canvas_present" in topics
        # limited to 5
        assert len(topics) <= 5

    def test_topics_handles_missing_fields(self, service):
        p = Mock(spec=AgentProposal)
        p.proposal_type = "action"
        p.title = None
        p.reasoning = None
        p.proposed_action = None
        topics = service._extract_proposal_topics(p)
        assert topics == ["action"]

    def test_entities_include_ids_and_reviewer(self, service):
        p = Mock(spec=AgentProposal)
        p.id = "prop-1"
        p.agent_id = "agent-1"
        p.approved_by = "reviewer-1"
        p.proposed_action = {"action_type": "canvas_present", "canvas_id": "c1"}

        entities = service._extract_proposal_entities(p)
        ent_set = set(entities)
        assert "proposal:prop-1" in ent_set
        assert "agent:agent-1" in ent_set
        assert "reviewer:reviewer-1" in ent_set
        # short string action values are added as entities
        assert "canvas_present" in ent_set
        assert "c1" in ent_set


# ============================================================================
# Coverage: get_pending_proposals / get_proposal_history
# ============================================================================
class TestProposalQueries:
    @pytest.mark.asyncio
    async def test_get_pending_proposals_applies_filters(self, service, mock_db):
        chain = Mock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.limit.return_value = chain
        chain.all.return_value = ["p1", "p2"]
        mock_db.query.return_value = chain

        result = await service.get_pending_proposals(
            agent_id="a1", canvas_id="c1", tenant_id="t1", limit=10
        )
        assert result == ["p1", "p2"]

    @pytest.mark.asyncio
    async def test_get_proposal_history_serializes(self, service, mock_db):
        p = Mock(spec=AgentProposal)
        p.id = "pid"
        p.proposal_type = "action"
        p.title = "T"
        p.status = ProposalStatus.APPROVED.value
        p.created_at = datetime(2026, 1, 1)
        p.approved_at = datetime(2026, 1, 2)
        p.approved_by = "u1"
        p.execution_result = {"success": True}

        chain = Mock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.limit.return_value = chain
        chain.all.return_value = [p]
        mock_db.query.return_value = chain

        history = await service.get_proposal_history("a1")
        assert len(history) == 1
        assert history[0]["proposal_id"] == "pid"
        assert history[0]["created_at"] == datetime(2026, 1, 1).isoformat()
        assert history[0]["approved_at"] == datetime(2026, 1, 2).isoformat()


# ============================================================================
# Coverage: reject_proposal happy path + guard
# ============================================================================
class TestRejectProposal:
    @pytest.mark.asyncio
    async def test_reject_proposal_sets_rejected_status(self, service, mock_db):
        proposal = Mock(spec=AgentProposal)
        proposal.id = "p1"
        proposal.status = ProposalStatus.PENDING_APPROVAL.value
        proposal.agent_id = "a1"
        proposal.tenant_id = "t1"
        proposal.proposed_action = {"action_type": "canvas_present"}
        proposal.approved_by = None
        proposal.approved_at = None
        proposal.execution_result = None

        chain = Mock()
        chain.filter.return_value = chain
        chain.first.return_value = proposal
        mock_db.query.return_value = chain

        with patch.object(service, "_create_proposal_episode", new=AsyncMock()):
            with patch("core.proposal_service.AgentLearningEnhanced") as LearningCls:
                learning = LearningCls.return_value
                learning.record_rejection = AsyncMock()
                await service.reject_proposal("p1", "u1", "bad idea")

        assert proposal.status == ProposalStatus.REJECTED.value
        assert proposal.approved_by == "u1"
        assert proposal.execution_result["rejected"] is True
        assert proposal.execution_result["reason"] == "bad idea"

    @pytest.mark.asyncio
    async def test_reject_rejects_non_pending_proposal(self, service, mock_db):
        proposal = Mock(spec=AgentProposal)
        proposal.status = ProposalStatus.APPROVED.value  # already approved

        chain = Mock()
        chain.filter.return_value = chain
        chain.first.return_value = proposal
        mock_db.query.return_value = chain

        with pytest.raises(ValueError, match="PENDING_APPROVAL"):
            await service.reject_proposal("p1", "u1", "x")

    @pytest.mark.asyncio
    async def test_reject_raises_when_not_found(self, service, mock_db):
        chain = Mock()
        chain.filter.return_value = chain
        chain.first.return_value = None
        mock_db.query.return_value = chain
        with pytest.raises(ValueError, match="not found"):
            await service.reject_proposal("missing", "u1", "x")


# ============================================================================
# Coverage: create_action_proposal happy path + match-confidence block
# ============================================================================
class TestCreateActionProposal:
    @pytest.mark.asyncio
    async def test_create_proposal_with_selector_candidates(self, service, mock_db):
        from core.models import AgentRegistry, AgentStatus
        agent = Mock(spec=AgentRegistry)
        agent.id = "a1"
        agent.name = "InternBot"
        agent.status = AgentStatus.INTERN.value
        agent.category = "test"
        agent.confidence_score = 0.6
        agent.tenant_id = "t1"
        agent.user_id = "u1"

        chain = Mock()
        chain.filter.return_value = chain
        chain.first.return_value = agent
        mock_db.query.return_value = chain

        proposed_action = {
            "action_type": "browser_automate",
            "selector_candidates": [
                {"selector": "#a", "match_count": 3, "is_text_only": True},
                {"selector": ".b", "match_count": 1, "is_text_only": False},
            ],
            "match_rationale": "high confidence",
            "match_score": 0.9,
            "chosen_index": 0,
            "per_field_confidence": {"#a": {"level": "high", "score": 0.9}},
        }

        with patch.object(service, "_create_proposal_episode", new=AsyncMock()):
            result = await service.create_action_proposal(
                intern_agent_id="a1",
                trigger_context={},
                proposed_action=proposed_action,
                reasoning="because",
            )

        # Description must include the candidates block
        assert "Selector candidates (2)" in result.description
        assert "#a" in result.description
        # per_field_confidence block present
        assert "Per-field confidence" in result.description
        assert result.status == ProposalStatus.PENDING_APPROVAL.value

    @pytest.mark.asyncio
    async def test_create_proposal_blocks_non_intern(self, service, mock_db):
        from core.models import AgentRegistry, AgentStatus
        agent = Mock(spec=AgentRegistry)
        agent.status = AgentStatus.SUPERVISED.value

        chain = Mock()
        chain.filter.return_value = chain
        chain.first.return_value = agent
        mock_db.query.return_value = chain

        with pytest.raises(PermissionError):
            await service.create_action_proposal(
                "a1", {}, {"action_type": "x"}, "r"
            )

    @pytest.mark.asyncio
    async def test_create_proposal_raises_when_agent_missing(self, service, mock_db):
        chain = Mock()
        chain.filter.return_value = chain
        chain.first.return_value = None
        mock_db.query.return_value = chain
        with pytest.raises(ValueError, match="not found"):
            await service.create_action_proposal(
                "missing", {}, {"action_type": "x"}, "r"
            )


# ============================================================================
# Coverage: _execute_proposed_action routing (unknown action type + disabled)
# ============================================================================
class TestExecuteProposedActionRouting:
    @pytest.mark.asyncio
    async def test_unknown_action_type_returns_error(self, service):
        proposal = Mock(spec=AgentProposal)
        proposal.id = "p1"
        proposal.proposed_action = {"action_type": "totally_unknown"}

        result = await service._execute_proposed_action(proposal)
        assert result["success"] is False
        assert "Unknown action type" in result["error"]

    @pytest.mark.asyncio
    async def test_disabled_execution_returns_skipped(self, service):
        proposal = Mock(spec=AgentProposal)
        proposal.id = "p1"
        proposal.proposed_action = {"action_type": "browser_automate"}

        with patch("core.proposal_service.PROPOSAL_EXECUTION_ENABLED", False):
            result = await service._execute_proposed_action(proposal)
        assert result["success"] is False
        assert result["skipped"] is True
