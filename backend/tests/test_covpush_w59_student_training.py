"""Coverage wave 59 — core/student_training_service.py (13% → 90%+).

create_training_proposal (missing agent, full flow), approve_training
(missing proposal, wrong status, success), complete_training_session
(missing session, confidence boost, proposal completion), training history,
duration estimation (confidence/gaps/similar-agents/learning-rate factors +
missing agent), capability gaps mapping, learning objectives, scenario
template, confidence boost, similar-agents history, learning rate.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.student_training_service import StudentTrainingService
from core.models import AgentStatus


def _agent(**kw):
    base = dict(id="a1", name="Agent 1", category="Finance",
                status=AgentStatus.STUDENT.value, confidence_score=0.3,
                module_path="core.agents.generic_agent",
                class_name="GenericAgent", workspace_id="default",
                tenant_id="default")
    base.update(kw)
    return SimpleNamespace(**base)


def _trigger(**kw):
    base = dict(agent_id="a1", trigger_type="agent_message",
                trigger_context={"message": "help"}, user_id="u1")
    base.update(kw)
    return SimpleNamespace(**base)


def _proposal(**kw):
    base = dict(id="p1", agent_id="a1", agent_name="Agent 1",
                proposal_type="workflow", title="Training Proposal",
                description="d", status="pending", tenant_id="default",
                workspace_id="default", proposal_data={})
    base.update(kw)
    return MagicMock(**base)


def _session(**kw):
    base = dict(id="s1", agent_id="a1", proposal_id="p1",
                status="completed", performance_score=0.8,
                duration_seconds=7200, tenant_id="default",
                workspace_id="default", started_at=None)
    base.update(kw)
    return MagicMock(**base)


def _arm_evidence_queries(db):
    """Round-86 evidence gate adds count()/all() queries (sessions, episodes,
    success ratio, mentor candidates) that plain Mock chains can't serve."""
    chain = db.query.return_value.filter.return_value
    chain.count.return_value = 10
    chain.all.return_value = []
    chain.order_by.return_value.all.return_value = []
    chain.order_by.return_value.limit.return_value.all.return_value = []
    return db


@pytest.fixture
def svc():
    return StudentTrainingService(_arm_evidence_queries(Mock()))


class TestCreateProposal:
    async def test_missing_agent_raises(self, svc):
        svc.db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(ValueError):
            await svc.create_training_proposal(_trigger())

    async def test_full_flow(self, svc):
        svc.db.query.return_value.filter.return_value.first.return_value = _agent()
        with patch.object(svc, "_identify_capability_gaps",
                          new=AsyncMock(return_value=["task_execution"])), \
             patch.object(svc, "_generate_learning_objectives",
                          new=AsyncMock(return_value=["obj1"])), \
             patch.object(svc, "estimate_training_duration",
                          new=AsyncMock(return_value=SimpleNamespace(
                              estimated_hours=40.0, confidence=0.6,
                              reasoning="r", similar_agents=[],
                              min_hours=28.0, max_hours=60.0))):
            proposal = await svc.create_training_proposal(_trigger())
        assert proposal.agent_id == "a1"
        assert "Training Proposal" in proposal.title


class TestApproveTraining:
    async def test_missing_proposal_raises(self, svc):
        svc.db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(ValueError):
            await svc.approve_training("p1", "u1")

    async def test_wrong_status_raises(self, svc):
        svc.db.query.return_value.filter.return_value.first.return_value = \
            _proposal(status="approved")
        with pytest.raises(ValueError):
            await svc.approve_training("p1", "u1")

    async def test_success(self, svc):
        proposal = _proposal(status="pending_approval")
        svc.db.query.return_value.filter.return_value.first.return_value = proposal
        session = await svc.approve_training("p1", "u1")
        assert session.agent_id == "a1"
        assert session.proposal_id == "p1"
        svc.db.commit.assert_called()


class TestCompleteTraining:
    async def test_missing_session_raises(self, svc):
        svc.db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(ValueError):
            await svc.complete_training_session(
                "s1", MagicMock(performance_score=0.9, tasks_completed=5))

    async def test_success_with_confidence_boost(self, svc):
        agent = _agent(confidence_score=0.3)
        sess = _session()
        state = {"n": 0}

        def _first(*a, **k):
            state["n"] += 1
            return sess if state["n"] == 1 else agent

        svc.db.query.return_value.filter.return_value.first.side_effect = _first
        with patch.object(svc, "_calculate_confidence_boost",
                          return_value=0.1):
            result = await svc.complete_training_session(
                "s1", MagicMock(performance_score=0.9, tasks_completed=5))
        assert result["session_id"] == "s1"
        assert agent.confidence_score == 0.4
        svc.db.commit.assert_called()


class TestDurationEstimate:
    async def test_missing_agent_raises(self, svc):
        svc.db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(ValueError):
            await svc.estimate_training_duration("a1", ["g1"], "intern")

    async def test_with_history_and_fast_learning(self, svc):
        agent = _agent(confidence_score=0.4)
        svc.db.query.return_value.filter.return_value.first.return_value = agent
        with patch.object(svc, "_get_similar_agents_training_history",
                          new=AsyncMock(return_value=[
                              {"agent_id": "x", "duration_hours": 30.0,
                               "session_count": 2}])), \
             patch.object(svc, "_calculate_learning_rate",
                          new=AsyncMock(return_value=1.5)):
            est = await svc.estimate_training_duration("a1", ["g1", "g2"], "intern")
        assert est.estimated_hours > 0
        assert est.min_hours < est.estimated_hours < est.max_hours
        assert est.confidence > 0.5
        assert "1.5" in est.reasoning

    async def test_without_history(self, svc):
        agent = _agent(confidence_score=0.3)
        svc.db.query.return_value.filter.return_value.first.return_value = agent
        with patch.object(svc, "_get_similar_agents_training_history",
                          new=AsyncMock(return_value=[])), \
             patch.object(svc, "_calculate_learning_rate",
                          new=AsyncMock(return_value=1.0)):
            est = await svc.estimate_training_duration("a1", [], "intern")
        assert est.estimated_hours > 0
        assert est.confidence == 0.5


class TestHelpers:
    async def test_capability_gaps_mapping(self, svc):
        gaps = await svc._identify_capability_gaps(
            _agent(), _trigger(trigger_type="form_submit"))
        assert "data_validation" in gaps
        assert "financial_analysis" in gaps  # category Finance

    async def test_capability_gaps_unknown(self, svc):
        gaps = await svc._identify_capability_gaps(
            _agent(category="Unknown"), _trigger(trigger_type="mystery"))
        assert gaps == []

    async def test_learning_objectives(self, svc):
        objectives = await svc._generate_learning_objectives(
            _agent(), _trigger(), ["gap_one", "gap_two"])
        assert "Understand agent_message execution flow" in objectives
        assert "Develop proficiency in gap one" in objectives
        assert "Accurately process financial data" in objectives

    def test_scenario_template(self, svc):
        t = svc._select_scenario_template(_trigger(trigger_type="workflow_trigger"))
        assert isinstance(t, str) and t
        t2 = svc._select_scenario_template(_trigger(trigger_type="unknown"))
        assert isinstance(t2, str)

    def test_confidence_boost(self, svc):
        assert svc._calculate_confidence_boost(1.0) > svc._calculate_confidence_boost(0.2)
        assert svc._calculate_confidence_boost(0.0) == 0.05
        assert svc._calculate_confidence_boost(0.4) == 0.10
        assert svc._calculate_confidence_boost(0.6) == 0.15
        assert svc._calculate_confidence_boost(0.9) == 0.20

    async def test_similar_agents_history(self, svc):
        similar = _agent(category="Finance", status=AgentStatus.INTERN.value,
                         confidence_score=0.8)
        svc.db.query.return_value.filter.return_value.all.side_effect = [
            [similar], [_session(duration_seconds=5400)]]
        history = await svc._get_similar_agents_training_history("Finance", "intern")
        assert len(history) == 1
        assert history[0]["duration_hours"] == 1.5

    async def test_learning_rate(self, svc):
        svc.db.query.return_value.filter.return_value.all.return_value = []
        assert await svc._calculate_learning_rate("a1") == 1.0
        svc.db.query.return_value.filter.return_value.all.return_value = [
            _session(performance_score=0.7), _session(performance_score=1.4)]
        rate = await svc._calculate_learning_rate("a1")
        assert rate == pytest.approx(1.5)


class TestHistoryAndPromotion:
    async def test_training_history(self, svc):
        proposal = MagicMock(title="T", proposal_data={"capability_gaps": ["g"]})
        svc.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            _session(completed_at=None)]
        svc.db.query.return_value.filter.return_value.first.return_value = proposal
        history = await svc.get_training_history("a1")
        assert len(history) == 1
        assert history[0]["proposal_title"] == "T"

    async def test_promotion_path(self, svc):
        agent = _agent(confidence_score=0.45)
        sess = _session()
        proposal = MagicMock(status="pending_approval", proposal_data={})
        state = {"n": 0}

        def _first(*a, **k):
            state["n"] += 1
            if state["n"] == 1:
                return sess
            if state["n"] == 2:
                return agent
            return proposal

        svc.db.query.return_value.filter.return_value.first.side_effect = _first
        with patch.object(svc, "_calculate_confidence_boost",
                          return_value=0.1):
            result = await svc.complete_training_session(
                "s1", MagicMock(performance_score=0.95, tasks_completed=5,
                                capabilities_developed=["c1"]))
        assert result["promoted_to_intern"] is True
        assert agent.status == AgentStatus.INTERN.value
