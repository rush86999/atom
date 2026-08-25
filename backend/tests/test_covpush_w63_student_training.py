"""Coverage wave 63 — core/student_training_service.py (92% → 95%+).

Closes the remaining holes: real TrainingOutcome construction (60-66),
approve_training modifications (duration override + hours-per-day limit,
205-210/219), complete_training_session missing-agent (289), and the
category-driven scenario template selection (614-616).
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.models import AgentStatus
from core.student_training_service import (
    StudentTrainingService,
    TrainingOutcome,
)


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


@pytest.fixture
def svc():
    return StudentTrainingService(Mock())


class TestTrainingOutcome:
    def test_outcome_attrs(self):
        outcome = TrainingOutcome(
            performance_score=0.8,
            supervisor_feedback="good",
            errors_count=2,
            tasks_completed=3,
            total_tasks=5,
            capabilities_developed=["task_execution"],
            capability_gaps_remaining=["reporting"],
        )
        assert outcome.performance_score == 0.8
        assert outcome.supervisor_feedback == "good"
        assert outcome.errors_count == 2
        assert outcome.tasks_completed == 3
        assert outcome.total_tasks == 5
        assert outcome.capabilities_developed == ["task_execution"]
        assert outcome.capability_gaps_remaining == ["reporting"]

    def test_outcome_defaults_empty_lists(self):
        outcome = TrainingOutcome(0.5, "", 0, 0, 0, [], [])
        assert outcome.capabilities_developed == []
        assert outcome.capability_gaps_remaining == []


class TestApproveTrainingModifications:
    async def test_with_duration_override(self, svc):
        proposal = _proposal(status="pending_approval",
                             proposal_data={
                                 "estimated_duration_hours": 40.0,
                                 "learning_objectives": ["o1", "o2"]})
        svc.db.query.return_value.filter.return_value.first.return_value = proposal
        session = await svc.approve_training(
            "p1", "u1",
            modifications={"duration_override_hours": 16.0,
                           "hours_per_day_limit": 4.0})
        # 16h / 4h-per-day = 4 days; JSON re-assign forces ORM change tracking
        assert session.agent_id == "a1"
        assert proposal.proposal_data["user_override_duration_hours"] == 16.0
        assert proposal.proposal_data["hours_per_day_limit"] == 4.0
        assert proposal.proposal_data["training_end_date"] > \
            proposal.proposal_data["training_start_date"]

    async def test_modifications_without_limit_uses_8h_day(self, svc):
        proposal = _proposal(status="pending_approval",
                             proposal_data={
                                 "estimated_duration_hours": 40.0,
                                 "learning_objectives": []})
        svc.db.query.return_value.filter.return_value.first.return_value = proposal
        await svc.approve_training("p1", "u1")
        # default 8h/day for 40h -> 5 days, no override recorded
        assert "user_override_duration_hours" not in proposal.proposal_data


class TestCompleteTrainingMissingAgent:
    async def test_missing_agent_raises(self, svc):
        state = {"n": 0}

        def _first(*a, **k):
            state["n"] += 1
            return _session() if state["n"] == 1 else None

        svc.db.query.return_value.filter.return_value.first.side_effect = _first
        outcome = TrainingOutcome(0.8, "ok", 1, 2, 3, ["c"], [])
        with pytest.raises(ValueError):
            await svc.complete_training_session("s1", outcome)

    async def test_full_flow_with_real_outcome(self, svc):
        agent = _agent(confidence_score=0.3)
        sess = _session()
        proposal = MagicMock(status="pending_approval",
                             proposal_data={"capability_gaps": ["g"]})
        state = {"n": 0}

        def _first(*a, **k):
            state["n"] += 1
            if state["n"] == 1:
                return sess
            if state["n"] == 2:
                return agent
            return proposal

        svc.db.query.return_value.filter.return_value.first.side_effect = _first
        # Round 86 evidence gate issues its own aggregate queries; keep them
        # inert (no sessions, no episodes) so this test stays about the
        # completion flow itself.
        _flt = svc.db.query.return_value.filter.return_value
        _flt.count.return_value = 0
        _flt.all.return_value = []
        outcome = TrainingOutcome(
            performance_score=0.6, supervisor_feedback="solid", errors_count=1,
            tasks_completed=4, total_tasks=5,
            capabilities_developed=["task_execution", "reporting"],
            capability_gaps_remaining=["forecasting"])
        with patch.object(svc, "_calculate_confidence_boost",
                          return_value=0.15):
            result = await svc.complete_training_session("s1", outcome)
        assert result["performance_score"] == 0.6
        assert sess.capabilities_developed == ["task_execution", "reporting"]
        assert sess.capability_gaps_remaining == ["forecasting"]
        assert sess.errors_count == 1
        assert sess.tasks_completed == 4
        assert proposal.executed_at is not None
        assert proposal.supervision_metadata["confidence_boost"] == \
            pytest.approx(0.15)


class TestScenarioTemplate:
    def test_category_from_trigger_context(self, svc):
        t = svc._select_scenario_template(
            _trigger(trigger_context={"category": "Finance"}))
        assert t == "Finance Fundamentals"
        t2 = svc._select_scenario_template(
            _trigger(trigger_context={"category": "Sales"}))
        assert t2 == "Sales Operations"
        t3 = svc._select_scenario_template(
            _trigger(trigger_context={"category": "Operations"}))
        assert t3 == "Process Automation"
        t4 = svc._select_scenario_template(
            _trigger(trigger_context={"category": "HR"}))
        assert t4 == "HR Management"
        t5 = svc._select_scenario_template(
            _trigger(trigger_context={"category": "Support"}))
        assert t5 == "Customer Support"

    def test_unknown_category_defaults_general(self, svc):
        t = svc._select_scenario_template(
            _trigger(trigger_context={"category": "R&D"}))
        assert t == "General Operations"


class TestHistoryBranch:
    async def test_history_with_no_duration(self, svc):
        proposal = MagicMock(title="T", proposal_data={"capability_gaps": ["g"]})
        svc.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            _session(duration_seconds=0)]
        svc.db.query.return_value.filter.return_value.first.return_value = proposal
        history = await svc.get_training_history("a1")
        assert history[0]["training_duration_hours"] is None

    async def test_history_no_proposal(self, svc):
        svc.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            _session(completed_at=None)]
        svc.db.query.return_value.filter.return_value.first.return_value = None
        history = await svc.get_training_history("a1")
        assert history[0]["proposal_title"] is None
        assert history[0]["capability_gaps"] == []


class TestSimilarAgentsBranch:
    async def test_similar_agents_without_sessions(self, svc):
        similar = _agent(category="Finance", status=AgentStatus.INTERN.value,
                         confidence_score=0.8)
        svc.db.query.return_value.filter.return_value.all.side_effect = [
            [similar], []]
        history = await svc._get_similar_agents_training_history("Finance", "intern")
        assert history == []

    async def test_learning_rate_clamped(self, svc):
        svc.db.query.return_value.filter.return_value.all.return_value = [
            _session(performance_score=0.1), _session(performance_score=0.2)]
        rate = await svc._calculate_learning_rate("a1")
        assert rate == 0.5  # clamped at minimum
        svc.db.query.return_value.filter.return_value.all.return_value = [
            _session(performance_score=1.4), _session(performance_score=1.5)]
        rate2 = await svc._calculate_learning_rate("a1")
        assert rate2 == 2.0  # clamped at maximum
