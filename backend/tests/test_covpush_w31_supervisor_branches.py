"""Coverage wave 31 — supervisor learning + performance branch completion (TDD).

Pushes `supervisor_learning_service` (69%) and `supervisor_performance_service`
(87%) to 90%+ by driving every remaining uncovered branch:
- learning: process_feedback_for_learning pipeline (rating/vote/intervention/
  unknown), get_top_performers (competence filter + 4 metric branches + else),
  update_competence_level (expert/advanced/intermediate/novice), create path of
  _get_or_create_performance, _process_rating boosts, _process_vote up/down,
  _process_intervention_outcome success/failure/partial, strengths/weaknesses
  branch matrix, recommendations success-rate>0.9, estimate months branches
- performance: track_intervention_outcome ValueError, leaderboard
  confidence/total_sessions metrics, recommendations declining + novice>20,
  _update_intervention_metrics effective/ineffective, success-rate no-outcomes
  fallback, learning-curve improving/declining trends
"""
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import (
    AgentRegistry,
    AgentStatus,
    InterventionOutcome,
    SupervisorRating,
    SupervisionSession,
    SupervisorPerformance,
)
from core.supervisor_learning_service import SupervisorLearningService
from core.supervisor_performance_service import SupervisorPerformanceService


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


def _agent(db):
    agent = AgentRegistry(
        id=f"agent-{uuid.uuid4().hex[:8]}",
        name="Helper", category="general", description="d",
        status=AgentStatus.SUPERVISED.value, confidence_score=0.75,
        module_path="core.agents.generic_agent", class_name="GenericAgent",
        workspace_id="ws-1",
    )
    db.add(agent)
    db.commit()
    return agent


def _session(db, agent=None, supervisor_id="u-sup", rating=4, completed=True):
    agent = agent or _agent(db)
    s = SupervisionSession(
        agent_id=agent.id, agent_name=agent.name, workspace_id="ws-1",
        trigger_context={"trigger_type": "manual"},
        status="completed" if completed else "running",
        supervisor_id=supervisor_id, supervisor_rating=rating,
        completed_at=datetime.now(timezone.utc) if completed else None,
        started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        duration_seconds=300,
    )
    db.add(s)
    db.commit()
    return s


def _outcome(db, session, supervisor_id="u-sup", outcome="success", days_ago=0):
    ts = datetime.now(timezone.utc) - timedelta(days=days_ago)
    o = InterventionOutcome(
        supervision_session_id=session.id, supervisor_id=supervisor_id,
        agent_id=session.agent_id, intervention_type="pause",
        outcome=outcome, was_effective=(outcome == "success"),
        assessed_at=ts, intervention_timestamp=ts,
    )
    db.add(o)
    db.commit()
    return o


def _performance(db, supervisor_id="u-sup", **kw):
    defaults = dict(
        supervisor_id=supervisor_id, confidence_score=0.5,
        competence_level="novice", performance_trend="stable",
        learning_rate=0.0, total_sessions_supervised=5,
        total_interventions=0, average_rating=None, total_ratings=0,
        rating_1_count=0, rating_2_count=0, rating_3_count=0,
        rating_4_count=0, rating_5_count=0, successful_interventions=0,
        failed_interventions=0, agents_promoted=0,
        agent_confidence_boosted=0, total_comments_given=0,
        total_upvotes_received=0, total_downvotes_received=0,
    )
    defaults.update(kw)
    perf = SupervisorPerformance(**defaults)
    db.add(perf)
    db.commit()
    return perf


def _rating(db, supervisor_id="u-sup", rating=5):
    r = SupervisorRating(
        supervision_session_id=uuid.uuid4().hex[:16],
        supervisor_id=supervisor_id, rater_id="rater-1",
        agent_id="agent-x", rating=rating,
        created_at=datetime.now(timezone.utc),
    )
    db.add(r)
    db.commit()
    return r


def await_coroutine(coro):
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ============================================================================
# SupervisorLearningService — process_feedback_for_learning pipeline
# ============================================================================

class TestProcessFeedbackPipeline:
    def test_rating_feedback_creates_and_updates(self, fresh_db):
        svc = SupervisorLearningService(fresh_db)
        result = await_coroutine(svc.process_feedback_for_learning(
            "u-new", "rating", {"rating": 5}))
        assert result["feedback_type"] == "rating"
        assert result["new_confidence"] > 0.5
        assert result["confidence_change"] > 0
        perf = fresh_db.query(SupervisorPerformance).filter(
            SupervisorPerformance.supervisor_id == "u-new").first()
        assert perf is not None and perf.total_ratings == 1

    def test_rating_low_boost_branch(self, fresh_db):
        _performance(fresh_db, confidence_score=0.94)
        svc = SupervisorLearningService(fresh_db)
        result = await_coroutine(svc.process_feedback_for_learning(
            "u-sup", "rating", {"rating": 1}))
        assert result["confidence_change"] == round(0.2 * -0.05, 3)  # -0.01
        assert result["new_confidence"] == round(0.94 + 0.2 * -0.05, 3)

    def test_vote_up_and_down(self, fresh_db):
        _performance(fresh_db, confidence_score=0.5)
        svc = SupervisorLearningService(fresh_db)
        up = await_coroutine(svc.process_feedback_for_learning(
            "u-sup", "vote", {"vote_type": "up"}))
        assert up["new_confidence"] == round(0.5 + 0.1 * 0.01, 3)
        down = await_coroutine(svc.process_feedback_for_learning(
            "u-sup", "vote", {"vote_type": "down"}))
        assert down["new_confidence"] < up["new_confidence"]

    def test_intervention_outcome_success_effective(self, fresh_db):
        _performance(fresh_db, confidence_score=0.5)
        svc = SupervisorLearningService(fresh_db)
        result = await_coroutine(svc.process_feedback_for_learning(
            "u-sup", "intervention_outcome",
            {"outcome": "success", "was_effective": True}))
        assert result["new_confidence"] > 0.5
        perf = fresh_db.query(SupervisorPerformance).filter(
            SupervisorPerformance.supervisor_id == "u-sup").first()
        assert perf.total_interventions == 1
        assert perf.successful_interventions == 1

    def test_intervention_outcome_failure(self, fresh_db):
        _performance(fresh_db, confidence_score=0.5)
        svc = SupervisorLearningService(fresh_db)
        result = await_coroutine(svc.process_feedback_for_learning(
            "u-sup", "intervention_outcome",
            {"outcome": "failure", "was_effective": False}))
        assert result["new_confidence"] < 0.5
        perf = fresh_db.query(SupervisorPerformance).filter(
            SupervisorPerformance.supervisor_id == "u-sup").first()
        assert perf.failed_interventions == 1

    def test_intervention_outcome_partial(self, fresh_db):
        _performance(fresh_db, confidence_score=0.5)
        svc = SupervisorLearningService(fresh_db)
        result = await_coroutine(svc.process_feedback_for_learning(
            "u-sup", "intervention_outcome", {"outcome": "partial"}))
        assert result["confidence_change"] == 0.0

    def test_unknown_feedback_type(self, fresh_db):
        _performance(fresh_db)
        svc = SupervisorLearningService(fresh_db)
        result = await_coroutine(svc.process_feedback_for_learning(
            "u-sup", "mystery", {}))
        assert result["feedback_type"] == "mystery"
        assert result["confidence_change"] == 0.0


class TestGetTopPerformers:
    def _setup(self, fresh_db):
        _performance(fresh_db, supervisor_id="u-a", confidence_score=0.9,
                     average_rating=4.8, total_sessions_supervised=100,
                     competence_level="advanced", successful_interventions=9,
                     failed_interventions=1)
        _performance(fresh_db, supervisor_id="u-b", confidence_score=0.5,
                     average_rating=3.2, total_sessions_supervised=30,
                     competence_level="intermediate", successful_interventions=1,
                     failed_interventions=9)

    def test_confidence_metric(self, fresh_db):
        self._setup(fresh_db)
        svc = SupervisorLearningService(fresh_db)
        top = await_coroutine(svc.get_top_performers(metric="confidence_score"))
        assert top[0]["supervisor_id"] == "u-a"

    def test_average_rating_metric(self, fresh_db):
        self._setup(fresh_db)
        svc = SupervisorLearningService(fresh_db)
        top = await_coroutine(svc.get_top_performers(metric="average_rating"))
        assert top[0]["average_rating"] == 4.8

    def test_success_rate_metric_and_competence_filter(self, fresh_db):
        self._setup(fresh_db)
        svc = SupervisorLearningService(fresh_db)
        top = await_coroutine(svc.get_top_performers(
            metric="success_rate", competence_level="advanced"))
        assert len(top) == 1
        assert top[0]["supervisor_id"] == "u-a"
        assert top[0]["competence_level"] == "advanced"

    def test_total_sessions_metric(self, fresh_db):
        self._setup(fresh_db)
        svc = SupervisorLearningService(fresh_db)
        top = await_coroutine(svc.get_top_performers(metric="total_sessions"))
        assert top[0]["total_sessions"] == 100

    def test_unknown_metric_preserves_db_order_and_limit(self, fresh_db):
        self._setup(fresh_db)
        svc = SupervisorLearningService(fresh_db)
        top = await_coroutine(svc.get_top_performers(metric="bogus", limit=1))
        assert len(top) == 1


class TestUpdateCompetenceLevel:
    def test_expert_promotion(self, fresh_db):
        _performance(fresh_db, confidence_score=0.9, total_sessions_supervised=150,
                     successful_interventions=95, failed_interventions=5)
        svc = SupervisorLearningService(fresh_db)
        result = await_coroutine(svc.update_competence_level("u-sup"))
        assert result["new_level"] == "expert"
        assert result["level_changed"] is True

    def test_advanced_promotion(self, fresh_db):
        _performance(fresh_db, confidence_score=0.75, total_sessions_supervised=60,
                     successful_interventions=50, failed_interventions=10)
        svc = SupervisorLearningService(fresh_db)
        result = await_coroutine(svc.update_competence_level("u-sup"))
        assert result["new_level"] == "advanced"

    def test_intermediate_promotion(self, fresh_db):
        _performance(fresh_db, confidence_score=0.6, total_sessions_supervised=25,
                     successful_interventions=20, failed_interventions=5)
        svc = SupervisorLearningService(fresh_db)
        result = await_coroutine(svc.update_competence_level("u-sup"))
        assert result["new_level"] == "intermediate"

    def test_novice_demotion(self, fresh_db):
        _performance(fresh_db, competence_level="advanced",
                     confidence_score=0.2, total_sessions_supervised=3)
        svc = SupervisorLearningService(fresh_db)
        result = await_coroutine(svc.update_competence_level("u-sup"))
        assert result["new_level"] == "novice"

    def test_no_change_and_missing_record(self, fresh_db):
        _performance(fresh_db, confidence_score=0.5, total_sessions_supervised=5)
        svc = SupervisorLearningService(fresh_db)
        result = await_coroutine(svc.update_competence_level("u-sup"))
        assert result["new_level"] == "novice" and result["level_changed"] is False
        created = await_coroutine(svc.update_competence_level("u-ghost"))
        assert created["old_level"] == "novice"


class TestStrengthsWeaknessesRecommendations:
    def test_strengths_all_branches(self, fresh_db):
        _performance(fresh_db, confidence_score=0.9, performance_trend="improving",
                     total_sessions_supervised=120, competence_level="advanced")
        agent = _agent(fresh_db)
        for i in range(5):
            _rating(fresh_db, rating=5)
            _session(fresh_db, agent)
            _outcome(fresh_db, _session(fresh_db, agent), outcome="success")
        svc = SupervisorLearningService(fresh_db)
        insights = await_coroutine(svc.calculate_learning_insights("u-sup"))
        assert "High overall confidence" in insights["strengths"]
        assert "Exceptional supervisor ratings" in insights["strengths"]
        assert "Excellent intervention success rate" in insights["strengths"]
        assert "Extensive supervision experience" in insights["strengths"]
        assert "Consistently improving performance" in insights["strengths"]

    def test_strengths_strong_ratings_and_good_success(self, fresh_db):
        _performance(fresh_db, confidence_score=0.5, total_sessions_supervised=5)
        agent = _agent(fresh_db)
        for _ in range(5):
            _rating(fresh_db, rating=4)
            _session(fresh_db, agent)
        # 8 of 10 success → 0.8 "Good intervention success rate"
        for _ in range(10):
            _outcome(fresh_db, _session(fresh_db, agent),
                     outcome="success" if _ < 8 else "failure")
        svc = SupervisorLearningService(fresh_db)
        insights = await_coroutine(svc.calculate_learning_insights("u-sup"))
        assert "Strong supervisor ratings" in insights["strengths"]
        assert "Good intervention success rate" in insights["strengths"]

    def test_strengths_fallback_developing(self, fresh_db):
        _performance(fresh_db, confidence_score=0.4, total_sessions_supervised=2)
        svc = SupervisorLearningService(fresh_db)
        insights = await_coroutine(svc.calculate_learning_insights("u-sup"))
        assert insights["strengths"] == ["Developing core skills"]

    def test_weaknesses_all_branches(self, fresh_db):
        _performance(fresh_db, confidence_score=0.3, performance_trend="declining",
                     total_sessions_supervised=3)
        agent = _agent(fresh_db)
        for _ in range(3):
            _rating(fresh_db, rating=2)
            _session(fresh_db, agent)
        _outcome(fresh_db, _session(fresh_db, agent), outcome="failure")
        svc = SupervisorLearningService(fresh_db)
        insights = await_coroutine(svc.calculate_learning_insights("u-sup"))
        joined = " ".join(insights["weaknesses"])
        assert "Low confidence" in joined
        assert "Below-average" in joined
        assert "success rate needs improvement" in joined
        assert "Declining performance trend" in joined
        assert "Limited supervision experience" in joined

    def test_weaknesses_fallback(self, fresh_db):
        _performance(fresh_db, confidence_score=0.6, total_sessions_supervised=30)
        svc = SupervisorLearningService(fresh_db)
        insights = await_coroutine(svc.calculate_learning_insights("u-sup"))
        assert insights["weaknesses"] == ["No significant weaknesses identified"]

    def test_recommendations_high_success_branch(self, fresh_db):
        _performance(fresh_db, competence_level="intermediate")
        agent = _agent(fresh_db)
        for _ in range(5):
            _outcome(fresh_db, _session(fresh_db, agent), outcome="success")
        svc = SupervisorLearningService(fresh_db)
        insights = await_coroutine(svc.calculate_learning_insights("u-sup"))
        assert any("Excellent success rate" in r for r in insights["recommendations"])

    def test_recommendations_continue_fallback(self, fresh_db):
        _performance(fresh_db, competence_level="novice", performance_trend="stable")
        svc = SupervisorLearningService(fresh_db)
        insights = await_coroutine(svc.calculate_learning_insights("u-sup"))
        assert any("training modules" in r for r in insights["recommendations"])

    def test_insights_missing_performance_returns_empty(self, fresh_db):
        svc = SupervisorLearningService(fresh_db)
        insights = await_coroutine(svc.calculate_learning_insights("u-ghost"))
        assert insights["recommendations"] == ["Start supervising sessions to establish baseline"]
        assert insights["current_state"]["confidence_score"] == 0.5

    def test_estimate_time_months_plus(self, fresh_db):
        _performance(fresh_db, confidence_score=0.1, learning_rate=0.0001)
        svc = SupervisorLearningService(fresh_db)
        perf = fresh_db.query(SupervisorPerformance).first()
        est = svc._estimate_time_to_next_level(perf)
        assert est is not None and "+ months" in est


# ============================================================================
# SupervisorPerformanceService — remaining branches
# ============================================================================

class TestPerformanceRemaining:
    def test_track_outcome_unknown_session_raises(self, fresh_db):
        svc = SupervisorPerformanceService(fresh_db)
        with pytest.raises(ValueError):
            await_coroutine(svc.track_intervention_outcome(
                "no-such-session", "pause", datetime.now(timezone.utc), "success",
                was_effective=True))

    def test_leaderboard_confidence_and_total_sessions(self, fresh_db):
        _performance(fresh_db, supervisor_id="u-a", confidence_score=0.9,
                     total_sessions_supervised=40, average_rating=4.5)
        _performance(fresh_db, supervisor_id="u-b", confidence_score=0.4,
                     total_sessions_supervised=10, average_rating=2.0)
        agent = _agent(fresh_db)
        for sid in ("u-a", "u-b"):
            _session(fresh_db, agent, supervisor_id=sid)
        svc = SupervisorPerformanceService(fresh_db)
        by_conf = await_coroutine(svc.get_leaderboard(metric="confidence_score"))
        assert by_conf[0]["supervisor_id"] == "u-a"
        by_sessions = await_coroutine(svc.get_leaderboard(metric="total_sessions"))
        assert by_sessions[0]["total_sessions"] == 40

    def test_recommendations_declining_and_novice_over20(self, fresh_db):
        _performance(fresh_db, performance_trend="declining", total_ratings=25,
                     rating_4_count=25, total_sessions_supervised=25,
                     total_upvotes_received=10, total_downvotes_received=2)
        svc = SupervisorPerformanceService(fresh_db)
        recs = await_coroutine(svc.get_performance_recommendations("u-sup"))
        joined = " ".join(recs)
        assert "declining recently" in joined
        assert "20+ supervision sessions" in joined

    def test_update_intervention_metrics_effective_and_ineffective(self, fresh_db):
        perf = _performance(fresh_db, confidence_score=0.5)
        agent = _agent(fresh_db)
        sess = _session(fresh_db, agent)
        svc = SupervisorPerformanceService(fresh_db)
        await_coroutine(svc.track_intervention_outcome(
            sess.id, "pause", datetime.now(timezone.utc), "success",
            was_effective=True))
        await_coroutine(svc.track_intervention_outcome(
            sess.id, "pause", datetime.now(timezone.utc), "failure",
            was_effective=False))
        fresh_db.refresh(perf)
        assert perf.total_interventions == 2
        assert perf.successful_interventions == 1
        assert perf.failed_interventions == 1
        assert perf.confidence_score == round(0.5 + 0.01 - 0.02, 3)
        assert perf.last_updated is not None

    def test_success_rate_no_outcomes_returns_zero(self, fresh_db):
        _performance(fresh_db)
        svc = SupervisorPerformanceService(fresh_db)
        rate = await_coroutine(svc.calculate_intervention_success_rate("u-sup"))
        assert rate == 0.0

    def test_learning_curve_improving_trend(self, fresh_db):
        _performance(fresh_db)
        agent = _agent(fresh_db)
        now = datetime.now(timezone.utc)
        # 5 weeks: older weeks rated 3, recent weeks rated 5 → improving.
        for i, rating in enumerate([3, 3, 3, 5, 5]):
            s = SupervisionSession(
                agent_id=agent.id, agent_name=agent.name, workspace_id="ws-1",
                trigger_context={"trigger_type": "manual"}, status="completed",
                supervisor_id="u-sup", supervisor_rating=rating,
                started_at=now - timedelta(weeks=5 - i),
                completed_at=now - timedelta(weeks=5 - i) + timedelta(minutes=30),
                duration_seconds=300,
            )
            fresh_db.add(s)
        fresh_db.commit()
        svc = SupervisorPerformanceService(fresh_db)
        curve = await_coroutine(svc.get_supervisor_learning_curve("u-sup", time_range_days=90))
        assert curve["trend"] == "improving"
        assert len(curve["dates"]) >= 4
        assert len(curve["ratings"]) == len(curve["dates"])
        assert len(curve["success_rates"]) == len(curve["dates"])
        assert len(curve["confidence_scores"]) == len(curve["dates"])

    def test_learning_curve_declining_trend(self, fresh_db):
        _performance(fresh_db)
        agent = _agent(fresh_db)
        now = datetime.now(timezone.utc)
        for i, rating in enumerate([5, 5, 5, 3, 3]):
            s = SupervisionSession(
                agent_id=agent.id, agent_name=agent.name, workspace_id="ws-1",
                trigger_context={"trigger_type": "manual"}, status="completed",
                supervisor_id="u-sup", supervisor_rating=rating,
                started_at=now - timedelta(weeks=5 - i),
                completed_at=now - timedelta(weeks=5 - i) + timedelta(minutes=30),
                duration_seconds=300,
            )
            fresh_db.add(s)
        fresh_db.commit()
        svc = SupervisorPerformanceService(fresh_db)
        curve = await_coroutine(svc.get_supervisor_learning_curve("u-sup", time_range_days=90))
        assert curve["trend"] == "declining"
