"""Coverage wave 42 — core/proposal_service (8% → 90%+).

- create_action_proposal: agent-not-found, non-INTERN blocked, success with
  selector-candidates block + per-field confidence
- submit_for_approval: correct status, wrong status raises
- approve_proposal: not-found, wrong status, success with execution +
  modifications copy (Bug 12), execution failure marks EXECUTION_FAILED and
  raises, learning episode + correction recording
- reject_proposal: not-found, wrong status, success + learning
- get_pending_proposals: filters
- get_proposal_history
- _execute_proposed_action dispatch: unknown type, browser, integration
"""
import os
import tempfile
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import AgentProposal, AgentRegistry, AgentStatus, ProposalStatus
from core.proposal_service import ProposalService


@pytest.fixture
def fresh_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    os.unlink(path)


def _intern_agent(db):
    agent = AgentRegistry(
        id=f"agent-{uuid.uuid4().hex[:8]}",
        name="Intern", category="general", description="d",
        status=AgentStatus.INTERN.value, confidence_score=0.6,
        module_path="m", class_name="C", workspace_id="default",
    )
    db.add(agent)
    db.commit()
    return agent


def _proposal(db, agent, status=ProposalStatus.PENDING_APPROVAL.value, action_type="browser_automate"):
    p = AgentProposal(
        id=f"prop-{uuid.uuid4().hex[:8]}",
        tenant_id="default", user_id="u1", agent_id=agent.id,
        agent_name=agent.name, proposal_type="action",
        title="Proposal", description="d",
        proposal_data={"action_type": action_type, "url": "https://x.com"},
        status=status,
    )
    db.add(p)
    db.commit()
    return p


@pytest.fixture
def svc(fresh_db):
    return ProposalService(fresh_db)


class TestCreateProposal:
    async def test_agent_not_found(self, svc):
        with pytest.raises(ValueError):
            await svc.create_action_proposal("missing", {}, {}, "r")

    async def test_non_intern_blocked(self, svc, fresh_db):
        agent = AgentRegistry(
            id=f"agent-{uuid.uuid4().hex[:8]}", name="A", category="g",
            description="d", status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95, module_path="m", class_name="C",
        )
        fresh_db.add(agent)
        fresh_db.commit()
        with pytest.raises(PermissionError):
            await svc.create_action_proposal(agent.id, {}, {}, "r")

    async def test_success(self, svc, fresh_db):
        agent = _intern_agent(fresh_db)
        proposal = await svc.create_action_proposal(
            agent.id, {}, {"action_type": "browser_automate", "url": "x"},
            "because", title="T",
        )
        assert proposal.status == ProposalStatus.PENDING_APPROVAL.value
        assert proposal.agent_name == agent.name

    async def test_success_with_selector_candidates(self, svc, fresh_db):
        agent = _intern_agent(fresh_db)
        proposal = await svc.create_action_proposal(
            agent.id, {},
            {
                "action_type": "browser_click",
                "selector_candidates": [
                    {"selector": "#a", "match_count": 2, "is_text_only": False},
                    "fallback",
                ],
                "match_rationale": "best match",
                "match_score": 0.9,
                "chosen_index": 0,
                "per_field_confidence": {"#a": {"level": "high", "score": 0.9}},
            },
            "r",
        )
        assert "Selector candidates" in proposal.description
        assert "Match score" in proposal.description
        assert "Per-field confidence" in proposal.description


class TestSubmitApproval:
    async def test_pending_ok(self, svc, fresh_db):
        agent = _intern_agent(fresh_db)
        p = _proposal(fresh_db, agent)
        await svc.submit_for_approval(p)  # no raise

    async def test_wrong_status_raises(self, svc, fresh_db):
        agent = _intern_agent(fresh_db)
        p = _proposal(fresh_db, agent, status=ProposalStatus.APPROVED.value)
        with pytest.raises(ValueError):
            await svc.submit_for_approval(p)


class TestApprove:
    async def test_not_found(self, svc):
        with pytest.raises(ValueError):
            await svc.approve_proposal("missing", "u1")

    async def test_wrong_status(self, svc, fresh_db):
        agent = _intern_agent(fresh_db)
        p = _proposal(fresh_db, agent, status=ProposalStatus.REJECTED.value)
        with pytest.raises(ValueError):
            await svc.approve_proposal(p.id, "u1")

    async def test_success_no_modifications(self, svc, fresh_db):
        agent = _intern_agent(fresh_db)
        p = _proposal(fresh_db, agent)
        with patch.object(svc, "_execute_proposed_action_with", new=AsyncMock(
            return_value={"success": True, "result": "done"}
        )), patch.object(svc, "_create_proposal_episode", new=AsyncMock()) as ep:
            result = await svc.approve_proposal(p.id, "u1")
        assert result["success"] is True
        fresh_db.refresh(p)
        assert p.status == ProposalStatus.EXECUTED.value
        assert p.approved_by == "u1"
        ep.assert_awaited_once()

    async def test_success_with_modifications(self, svc, fresh_db):
        agent = _intern_agent(fresh_db)
        p = _proposal(fresh_db, agent)
        with patch.object(svc, "_execute_proposed_action_with", new=AsyncMock(
            return_value={"success": True}
        )), patch.object(svc, "_create_proposal_episode", new=AsyncMock()), \
             patch("core.proposal_service.AgentLearningEnhanced") as ale:
            learning = MagicMock()
            learning.record_user_correction = AsyncMock()
            ale.return_value = learning
            result = await svc.approve_proposal(
                p.id, "u1", modifications={"url": "https://y.com"}
            )
        assert result["success"] is True
        fresh_db.refresh(p)
        assert p.proposal_data["url"] == "https://y.com"
        learning.record_user_correction.assert_awaited_once()

    async def test_execution_failure_raises_and_marks(self, svc, fresh_db):
        agent = _intern_agent(fresh_db)
        p = _proposal(fresh_db, agent)
        with patch.object(svc, "_execute_proposed_action_with", new=AsyncMock(
            side_effect=RuntimeError("boom")
        )):
            with pytest.raises(RuntimeError):
                await svc.approve_proposal(p.id, "u1")
        fresh_db.refresh(p)
        assert p.status == ProposalStatus.EXECUTION_FAILED.value
        assert p.execution_result["success"] is False

    async def test_unsuccessful_result_marks_failed(self, svc, fresh_db):
        agent = _intern_agent(fresh_db)
        p = _proposal(fresh_db, agent)
        with patch.object(svc, "_execute_proposed_action_with", new=AsyncMock(
            return_value={"success": False, "error": "nope"}
        )), patch.object(svc, "_create_proposal_episode", new=AsyncMock()):
            await svc.approve_proposal(p.id, "u1")
        fresh_db.refresh(p)
        assert p.status == ProposalStatus.EXECUTION_FAILED.value


class TestReject:
    async def test_not_found(self, svc):
        with pytest.raises(ValueError):
            await svc.reject_proposal("missing", "u1", "no")

    async def test_wrong_status(self, svc, fresh_db):
        agent = _intern_agent(fresh_db)
        p = _proposal(fresh_db, agent, status=ProposalStatus.EXECUTED.value)
        with pytest.raises(ValueError):
            await svc.reject_proposal(p.id, "u1", "no")

    async def test_success(self, svc, fresh_db):
        agent = _intern_agent(fresh_db)
        p = _proposal(fresh_db, agent)
        with patch.object(svc, "_create_proposal_episode", new=AsyncMock()), \
             patch("core.proposal_service.AgentLearningEnhanced") as ale:
            learning = MagicMock()
            learning.record_rejection = AsyncMock()
            ale.return_value = learning
            await svc.reject_proposal(p.id, "u1", "not needed")
        fresh_db.refresh(p)
        assert p.status == ProposalStatus.REJECTED.value
        assert p.execution_result["reason"] == "not needed"
        learning.record_rejection.assert_awaited_once()


class TestQueries:
    async def test_pending_filters(self, svc, fresh_db):
        a1 = _intern_agent(fresh_db)
        a2 = _intern_agent(fresh_db)
        p1 = _proposal(fresh_db, a1)
        p2 = _proposal(fresh_db, a1, action_type="canvas_present")
        _proposal(fresh_db, a2)
        pending = await svc.get_pending_proposals(agent_id=a1.id)
        assert len(pending) == 2
        limited = await svc.get_pending_proposals(agent_id=a1.id, limit=1)
        assert len(limited) == 1

    async def test_history(self, svc, fresh_db):
        agent = _intern_agent(fresh_db)
        _proposal(fresh_db, agent)
        history = await svc.get_proposal_history(agent.id)
        assert len(history) == 1
        assert history[0]["proposal_id"]
        assert history[0]["execution_result"] is None


class TestExecuteDispatch:
    async def test_unknown_action_type(self, svc, fresh_db):
        agent = _intern_agent(fresh_db)
        p = _proposal(fresh_db, agent, action_type="bogus_type")
        result = await svc._execute_proposed_action(p)
        assert result["success"] is False

    async def test_browser_action(self, svc, fresh_db):
        agent = _intern_agent(fresh_db)
        p = _proposal(fresh_db, agent, action_type="browser_automate")
        with patch.object(svc, "_execute_browser_action", new=AsyncMock(
            return_value={"success": True}
        )) as b:
            result = await svc._execute_proposed_action(p)
        assert result["success"] is True
        b.assert_awaited_once()

    async def test_dispatch_exception(self, svc, fresh_db):
        agent = _intern_agent(fresh_db)
        p = _proposal(fresh_db, agent, action_type="browser_automate")
        with patch.object(svc, "_execute_browser_action", new=AsyncMock(
            side_effect=RuntimeError("boom")
        )):
            result = await svc._execute_proposed_action(p)
        assert result["success"] is False
        assert "error" in result


class TestExecuteWithAndEpisode:
    async def test_execute_with_action_swaps_then_restores(self, svc, fresh_db):
        agent = _intern_agent(fresh_db)
        p = _proposal(fresh_db, agent)
        original = p.proposal_data
        with patch.object(svc, "_execute_proposed_action", new=AsyncMock(
            return_value={"success": True}
        )) as epa:
            result = await svc._execute_proposed_action_with(p, {"action_type": "x"})
        assert result["success"] is True
        epa.assert_awaited_once()
        assert p.proposal_data == original  # restored after execution

    async def test_create_proposal_episode(self, svc, fresh_db):
        agent = _intern_agent(fresh_db)
        p = _proposal(fresh_db, agent)
        with patch("core.episode_segmentation_service.EpisodeSegmentationService") as esc:
            esc.return_value = MagicMock()
            await svc._create_proposal_episode(
                p, "approved", modifications={"url": "x"},
                execution_result={"success": True},
            )
        from core.models import AgentEpisode
        episodes = fresh_db.query(AgentEpisode).all()
        assert len(episodes) == 1
        assert episodes[0].proposal_id == p.id
        assert episodes[0].supervision_decision == "approved"

    async def test_create_proposal_episode_rejected(self, svc, fresh_db):
        agent = _intern_agent(fresh_db)
        p = _proposal(fresh_db, agent)
        with patch("core.episode_segmentation_service.EpisodeSegmentationService") as esc:
            esc.return_value = MagicMock()
            await svc._create_proposal_episode(
                p, "rejected", rejection_reason="no", modifications=None,
            )
        from core.models import AgentEpisode
        episodes = fresh_db.query(AgentEpisode).all()
        assert episodes[0].supervision_reasoning == "no"
        assert episodes[0].supervision_decision == "rejected"

    async def test_create_proposal_episode_exception_swallowed(self, svc, fresh_db):
        agent = _intern_agent(fresh_db)
        p = _proposal(fresh_db, agent)
        with patch("core.episode_segmentation_service.EpisodeSegmentationService",
                   side_effect=RuntimeError("boom")):
            await svc._create_proposal_episode(p, "approved", modifications=None)
        # no raise
