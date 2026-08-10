"""Coverage wave 24 — two-way-learning service stack + P4 taint tracker + P9 sandbox gate (TDD).

Picks up where wave 19b/20 left off: the SupervisorPerformance schema-drift fix
re-enabled the two-way-learning stack, but these services still had ~0%
coverage. This suite drives:

- ``core.supervisor_learning_service`` (process_feedback_for_learning,
  calculate_learning_insights, get_top_performers, update_competence_level)
- ``core.supervisor_performance_service`` (get_supervisor_metrics,
  track_intervention_outcome, get_leaderboard, recommendations, learning curve)
- ``core.feedback_service`` (rate_supervisor, threaded comments, votes,
  session feedback summary)
- ``core.data_taint_tracker`` (P4 — sensitivity classification, outbound gate)
- ``core.sandbox_gate`` (P9 — evaluate_tool_call: no-policy None, killrun
  block, fail-open, whitelist/fs/tripwire/caps phases)
"""
import os

# Convention (see test_agent_governance_service.py etc.): TESTING=1 must be
# set BEFORE core.database is first imported, or the engine binds to the dev
# DB (atom_dev.db) instead of the isolated test_integration.db.
os.environ["TESTING"] = "1"

import tempfile
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import (
    AgentRegistry,
    AgentStatus,
    InterventionOutcome,
    SupervisionSession,
    SupervisorComment,
    SupervisorPerformance,
    SupervisorRating,
)


@pytest.fixture
def fresh_db():
    """Isolated temp-file SQLite DB per test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    os.unlink(path)


def _agent(db, agent_id=None):
    agent = AgentRegistry(
        id=agent_id or f"agent-{uuid.uuid4().hex[:8]}",
        name="Helper", category="general", description="d",
        status=AgentStatus.SUPERVISED.value, confidence_score=0.75,
        module_path="core.agents.generic_agent", class_name="GenericAgent",
        workspace_id="default", tenant_id="default",
    )
    db.add(agent)
    db.commit()
    return agent


def _perf(db, supervisor_id="u-sup", **overrides):
    kwargs = dict(
        supervisor_id=supervisor_id,
        confidence_score=0.5,
        competence_level="novice",
        total_sessions_supervised=0,
        total_interventions=0,
        successful_interventions=0,
        failed_interventions=0,
        total_ratings=0,
        average_rating=0.0,
        performance_trend="stable",
        learning_rate=0.0,
    )
    kwargs.update(overrides)
    p = SupervisorPerformance(**kwargs)
    db.add(p)
    db.commit()
    return p


def _completed_session(db, agent, supervisor_id="u-sup", rating=4, started=None):
    # naive datetimes: the services compare against datetime.now() (naive local)
    s = SupervisionSession(
        agent_id=agent.id, agent_name=agent.name, workspace_id="default",
        trigger_context={"trigger_type": "manual"}, status="completed",
        supervisor_id=supervisor_id, supervisor_rating=rating,
        started_at=started or (datetime.now() - timedelta(minutes=5)),
        completed_at=datetime.now(),
        duration_seconds=300,
    )
    db.add(s)
    db.commit()
    return s


# ============================================================================
# SupervisorLearningService
# ============================================================================

class TestLearningProcessFeedback:
    @pytest.mark.asyncio
    async def test_rating_five_boosts_confidence(self, fresh_db):
        from core.supervisor_learning_service import SupervisorLearningService
        svc = SupervisorLearningService(fresh_db)
        result = await svc.process_feedback_for_learning(
            "u-sup", "rating", {"rating": 5, "session_id": "s1"}
        )
        assert result["confidence_change"] > 0
        assert result["new_confidence"] > 0.5
        assert result["old_competence"] == "novice"

    @pytest.mark.asyncio
    async def test_rating_one_penalizes_confidence(self, fresh_db):
        from core.supervisor_learning_service import SupervisorLearningService
        _perf(fresh_db, confidence_score=0.7, total_ratings=3)
        svc = SupervisorLearningService(fresh_db)
        result = await svc.process_feedback_for_learning(
            "u-sup", "rating", {"rating": 1}
        )
        assert result["confidence_change"] < 0
        assert result["new_confidence"] < 0.7

    @pytest.mark.asyncio
    async def test_vote_up_and_down(self, fresh_db):
        from core.supervisor_learning_service import SupervisorLearningService
        svc = SupervisorLearningService(fresh_db)
        up = await svc.process_feedback_for_learning("u-sup", "vote", {"vote_type": "up"})
        down = await svc.process_feedback_for_learning("u-sup", "vote", {"vote_type": "down"})
        assert up["new_confidence"] > down["new_confidence"]

    @pytest.mark.asyncio
    async def test_intervention_outcome_effective(self, fresh_db):
        from core.supervisor_learning_service import SupervisorLearningService
        svc = SupervisorLearningService(fresh_db)
        result = await svc.process_feedback_for_learning(
            "u-sup", "intervention_outcome",
            {"outcome": "success", "was_effective": True},
        )
        assert result["confidence_change"] > 0
        row = fresh_db.query(SupervisorPerformance).filter(
            SupervisorPerformance.supervisor_id == "u-sup").first()
        assert row.total_interventions == 1
        assert row.successful_interventions == 1

    @pytest.mark.asyncio
    async def test_intervention_outcome_failure(self, fresh_db):
        from core.supervisor_learning_service import SupervisorLearningService
        svc = SupervisorLearningService(fresh_db)
        result = await svc.process_feedback_for_learning(
            "u-sup", "intervention_outcome",
            {"outcome": "failure", "was_effective": False},
        )
        assert result["confidence_change"] < 0
        row = fresh_db.query(SupervisorPerformance).filter(
            SupervisorPerformance.supervisor_id == "u-sup").first()
        assert row.failed_interventions == 1

    @pytest.mark.asyncio
    async def test_unknown_feedback_type_warns(self, fresh_db):
        from core.supervisor_learning_service import SupervisorLearningService
        svc = SupervisorLearningService(fresh_db)
        with patch("core.supervisor_learning_service.logger") as mock_logger:
            await svc.process_feedback_for_learning("u-sup", "bogus", {})
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_confidence_clamped(self, fresh_db):
        from core.supervisor_learning_service import SupervisorLearningService
        _perf(fresh_db, confidence_score=0.94, total_ratings=10)
        svc = SupervisorLearningService(fresh_db)
        result = await svc.process_feedback_for_learning("u-sup", "rating", {"rating": 5})
        assert result["new_confidence"] <= 0.95


class TestLearningInsights:
    @pytest.mark.asyncio
    async def test_insights_empty(self, fresh_db):
        from core.supervisor_learning_service import SupervisorLearningService
        svc = SupervisorLearningService(fresh_db)
        insights = await svc.calculate_learning_insights("ghost")
        assert insights["current_state"]["confidence_score"] == 0.5
        assert insights["recommendations"] == ["Start supervising sessions to establish baseline"]
        assert insights["recent_feedback_summary"]["total_ratings"] == 0

    @pytest.mark.asyncio
    async def test_insights_populated(self, fresh_db):
        from core.supervisor_learning_service import SupervisorLearningService
        _perf(fresh_db, confidence_score=0.8, competence_level="expert",
              learning_rate=0.01, performance_trend="improving",
              total_sessions_supervised=25, total_interventions=10,
              successful_interventions=8, average_rating=4.5, total_ratings=20)
        fresh_db.add(SupervisorRating(
            id=str(uuid.uuid4()), supervision_session_id="s1",
            supervisor_id="u-sup", rater_id="r1", rating=5,
            rating_category="session_outcome",
            created_at=datetime.now(),
        ))
        fresh_db.add(InterventionOutcome(
            id=str(uuid.uuid4()), supervision_session_id="s1",
            supervisor_id="u-sup", agent_id="a1",
            intervention_type="correct",
            intervention_timestamp=datetime.now(),
            outcome="success", was_effective=True,
        ))
        fresh_db.commit()
        svc = SupervisorLearningService(fresh_db)
        insights = await svc.calculate_learning_insights("u-sup")
        assert insights["current_state"]["confidence_score"] == 0.8
        assert insights["current_state"]["competence_level"] == "expert"
        assert insights["recent_feedback_summary"]["total_ratings"] == 1
        assert insights["recent_feedback_summary"]["average_rating"] == 5.0
        assert insights["recent_feedback_summary"]["intervention_success_rate"] == 1.0


class TestTopPerformers:
    @pytest.mark.asyncio
    async def test_top_by_confidence(self, fresh_db):
        from core.supervisor_learning_service import SupervisorLearningService
        _perf(fresh_db, supervisor_id="a", confidence_score=0.9)
        _perf(fresh_db, supervisor_id="b", confidence_score=0.6)
        svc = SupervisorLearningService(fresh_db)
        top = await svc.get_top_performers(metric="confidence_score", limit=1)
        assert len(top) == 1
        assert top[0]["supervisor_id"] == "a"

    @pytest.mark.asyncio
    async def test_top_by_success_rate_unknown_metric_and_filter(self, fresh_db):
        from core.supervisor_learning_service import SupervisorLearningService
        _perf(fresh_db, supervisor_id="a", confidence_score=0.8,
              successful_interventions=5, failed_interventions=0,
              competence_level="expert")
        _perf(fresh_db, supervisor_id="b", confidence_score=0.9,
              successful_interventions=0, failed_interventions=5,
              competence_level="novice")
        svc = SupervisorLearningService(fresh_db)
        top = await svc.get_top_performers(metric="success_rate", limit=10)
        assert top[0]["supervisor_id"] == "a"
        filtered = await svc.get_top_performers(metric="average_rating",
                                                competence_level="novice")
        assert all(t["competence_level"] == "novice" for t in filtered)
        by_sessions = await svc.get_top_performers(metric="total_sessions", limit=10)
        assert len(by_sessions) == 2
        unknown = await svc.get_top_performers(metric="nonsense", limit=10)
        assert len(unknown) == 2


class TestCompetenceLevel:
    @pytest.mark.asyncio
    async def test_novice_when_low_confidence(self, fresh_db):
        from core.supervisor_learning_service import SupervisorLearningService
        _perf(fresh_db, confidence_score=0.3)
        svc = SupervisorLearningService(fresh_db)
        result = await svc.update_competence_level("u-sup")
        assert result["new_level"] == "novice"
        assert result["level_changed"] is False

    @pytest.mark.asyncio
    async def test_expert_when_criteria_met(self, fresh_db):
        from core.supervisor_learning_service import SupervisorLearningService
        _perf(fresh_db, confidence_score=0.9, total_sessions_supervised=150,
              successful_interventions=20, failed_interventions=0,
              competence_level="advanced")
        svc = SupervisorLearningService(fresh_db)
        result = await svc.update_competence_level("u-sup")
        assert result["new_level"] == "expert"
        assert result["level_changed"] is True


# ============================================================================
# SupervisorPerformanceService
# ============================================================================

class TestPerfMetrics:
    @pytest.mark.asyncio
    async def test_metrics_empty(self, fresh_db):
        from core.supervisor_performance_service import SupervisorPerformanceService
        svc = SupervisorPerformanceService(fresh_db)
        metrics = await svc.get_supervisor_metrics("ghost")
        assert metrics["overall"]["confidence_score"] == 0.5
        assert metrics["overall"]["competence_level"] == "novice"
        assert metrics["interventions"]["total"] == 0

    @pytest.mark.asyncio
    async def test_metrics_populated(self, fresh_db):
        from core.supervisor_performance_service import SupervisorPerformanceService
        agent = _agent(fresh_db)
        for i in range(3):
            session = _completed_session(fresh_db, agent, rating=4 + (i % 2))
            fresh_db.add(SupervisorRating(
                id=str(uuid.uuid4()), supervision_session_id=session.id,
                supervisor_id="u-sup", rater_id="r1",
                rating=4 + (i % 2), rating_category="session_outcome",
                created_at=datetime.now() - timedelta(days=i),
            ))
            fresh_db.add(InterventionOutcome(
                id=str(uuid.uuid4()), supervision_session_id=session.id,
                supervisor_id="u-sup", agent_id=agent.id,
                intervention_type="correct",
                intervention_timestamp=datetime.now(),
                assessed_at=datetime.now(),
                outcome="success",
            ))
        _perf(fresh_db, confidence_score=0.8, competence_level="expert",
              total_sessions_supervised=3, total_interventions=4,
              successful_interventions=3, failed_interventions=1,
              average_rating=4.3, total_ratings=3, rating_4_count=2, rating_5_count=1,
              total_upvotes_received=5, total_downvotes_received=1)
        fresh_db.commit()
        svc = SupervisorPerformanceService(fresh_db)
        metrics = await svc.get_supervisor_metrics("u-sup")
        assert metrics["overall"]["confidence_score"] == 0.8
        assert metrics["overall"]["total_sessions"] == 3
        assert metrics["interventions"]["successful"] == 3
        assert metrics["ratings"]["distribution"][4] == 2
        assert metrics["feedback"]["vote_ratio"] == pytest.approx(5 / 6, abs=0.001)


class TestTrackOutcome:
    @pytest.mark.asyncio
    async def test_missing_session_raises(self, fresh_db):
        from core.supervisor_performance_service import SupervisorPerformanceService
        svc = SupervisorPerformanceService(fresh_db)
        with pytest.raises(ValueError):
            await svc.track_intervention_outcome(
                supervision_session_id="nope",
                intervention_type="correct",
                intervention_timestamp=datetime.now(),
                outcome="success",
            )

    @pytest.mark.asyncio
    async def test_ineffective_outcome_counts_failure(self, fresh_db):
        from core.supervisor_performance_service import SupervisorPerformanceService
        agent = _agent(fresh_db)
        session = _completed_session(fresh_db, agent)
        _perf(fresh_db, confidence_score=0.6, total_interventions=1,
              successful_interventions=1)
        svc = SupervisorPerformanceService(fresh_db)
        outcome = await svc.track_intervention_outcome(
            supervision_session_id=session.id,
            intervention_type="correct",
            intervention_timestamp=datetime.now(),
            outcome="failure",
            was_effective=False,
        )
        assert outcome.outcome == "failure"
        fresh_db.expire_all()
        row = fresh_db.query(SupervisorPerformance).filter(
            SupervisorPerformance.supervisor_id == "u-sup").first()
        assert row.total_interventions == 2
        assert row.successful_interventions == 1
        assert row.failed_interventions == 1
        assert row.confidence_score < 0.6  # penalty applied


class TestLeaderboardAndCurve:
    @pytest.mark.asyncio
    async def test_leaderboard_empty_and_metric(self, fresh_db):
        from core.supervisor_performance_service import SupervisorPerformanceService
        svc = SupervisorPerformanceService(fresh_db)
        empty = await svc.get_leaderboard(limit=5)
        assert empty == []
        _perf(fresh_db, supervisor_id="a", confidence_score=0.9, average_rating=4.8)
        _perf(fresh_db, supervisor_id="b", confidence_score=0.5, average_rating=4.1)
        fresh_db.add(SupervisionSession(
            agent_id="ag1", agent_name="A", workspace_id="default",
            trigger_context={}, status="completed", supervisor_id="a",
            supervisor_rating=5, started_at=datetime.now() - timedelta(days=1),
            completed_at=datetime.now(),
        ))
        fresh_db.commit()
        by_rating = await svc.get_leaderboard(metric="average_rating", limit=1)
        assert by_rating[0]["supervisor_id"] == "a"
        by_confidence = await svc.get_leaderboard(metric="confidence_score")
        assert by_confidence[0]["supervisor_id"] == "a"

    @pytest.mark.asyncio
    async def test_recommendations_empty_and_trend(self, fresh_db):
        from core.supervisor_performance_service import SupervisorPerformanceService
        svc = SupervisorPerformanceService(fresh_db)
        assert await svc.get_performance_recommendations("ghost") == []
        _perf(fresh_db, performance_trend="declining",
              total_ratings=15, confidence_score=0.6)
        recs = await svc.get_performance_recommendations("u-sup")
        assert any("declining" in r for r in recs)

    @pytest.mark.asyncio
    async def test_success_rate_and_learning_curve(self, fresh_db):
        from core.supervisor_performance_service import SupervisorPerformanceService
        agent = _agent(fresh_db)
        svc = SupervisorPerformanceService(fresh_db)
        assert await svc.calculate_intervention_success_rate("u-sup") == 0.0
        for outcome in ("success", "success", "failure"):
            session = _completed_session(fresh_db, agent)
            fresh_db.add(InterventionOutcome(
                id=str(uuid.uuid4()), supervision_session_id=session.id,
                supervisor_id="u-sup", agent_id=agent.id,
                intervention_type="correct",
                intervention_timestamp=datetime.now(),
                assessed_at=datetime.now(),
                outcome=outcome,
            ))
        fresh_db.commit()
        rate = await svc.calculate_intervention_success_rate("u-sup")
        assert rate == pytest.approx(2 / 3)
        curve = await svc.get_supervisor_learning_curve("u-sup")
        assert curve["trend"] in ("stable", "improving", "declining")
        # bucketed per week — all 3 sessions land in the same bucket
        assert len(curve["ratings"]) == 1
        assert curve["ratings"][0] == pytest.approx(4.0, abs=0.01)


# ============================================================================
# FeedbackService
# ============================================================================

class TestRateSupervisor:
    @pytest.mark.asyncio
    async def test_rating_out_of_range(self, fresh_db):
        from core.feedback_service import FeedbackService
        svc = FeedbackService(fresh_db)
        with pytest.raises(ValueError):
            await svc.rate_supervisor(
                supervision_session_id="s1", rater_id="r1", rating=6,
                rating_category="session_outcome",
            )

    @pytest.mark.asyncio
    async def test_missing_session(self, fresh_db):
        from core.feedback_service import FeedbackService
        svc = FeedbackService(fresh_db)
        with pytest.raises(ValueError):
            await svc.rate_supervisor(
                supervision_session_id="nope", rater_id="r1", rating=4,
                rating_category="session_outcome",
            )

    @pytest.mark.asyncio
    async def test_session_not_completed(self, fresh_db):
        from core.feedback_service import FeedbackService
        from core.models import SupervisionStatus
        agent = _agent(fresh_db)
        s = SupervisionSession(
            agent_id=agent.id, agent_name=agent.name, workspace_id="default",
            trigger_context={}, status=SupervisionStatus.RUNNING.value,
            supervisor_id="u-sup",
        )
        fresh_db.add(s)
        fresh_db.commit()
        svc = FeedbackService(fresh_db)
        with pytest.raises(ValueError):
            await svc.rate_supervisor(
                supervision_session_id=s.id, rater_id="r1", rating=4,
                rating_category="session_outcome",
            )

    @pytest.mark.asyncio
    async def test_rate_creates_and_updates(self, fresh_db):
        from core.feedback_service import FeedbackService
        agent = _agent(fresh_db)
        session = _completed_session(fresh_db, agent)
        svc = FeedbackService(fresh_db)
        rating = await svc.rate_supervisor(
            supervision_session_id=session.id, rater_id="system_u-sup",
            rating=4, rating_category="session_outcome", agent_id=agent.id,
        )
        assert rating.rating == 4
        perf = fresh_db.query(SupervisorPerformance).filter(
            SupervisorPerformance.supervisor_id == "u-sup").first()
        assert perf is not None
        assert perf.total_ratings == 1
        updated = await svc.rate_supervisor(
            supervision_session_id=session.id, rater_id="system_u-sup",
            rating=2, rating_category="session_outcome", agent_id=agent.id,
        )
        assert updated.rating == 2
        assert fresh_db.query(SupervisorRating).count() == 1

    @pytest.mark.asyncio
    async def test_get_supervisor_ratings(self, fresh_db):
        from core.feedback_service import FeedbackService
        agent = _agent(fresh_db)
        for i in range(2):
            session = _completed_session(fresh_db, agent)
            svc = FeedbackService(fresh_db)
            await svc.rate_supervisor(
                supervision_session_id=session.id, rater_id="r1",
                rating=5 - i, rating_category="session_outcome",
            )
        ratings = await FeedbackService(fresh_db).get_supervisor_ratings("u-sup")
        assert len(ratings) == 2
        assert {r["rating"] for r in ratings} == {5, 4}


class TestComments:
    @pytest.mark.asyncio
    async def test_comment_lifecycle(self, fresh_db):
        from core.feedback_service import FeedbackService
        agent = _agent(fresh_db)
        session = _completed_session(fresh_db, agent)
        svc = FeedbackService(fresh_db)
        comment = await svc.add_comment(
            supervision_session_id=session.id,
            author_id="u-sup",
            content="First comment",
        )
        assert comment.id
        thread = await svc.get_comment_thread(session.id)
        assert len(thread) == 1

        updated = await svc.update_comment(comment.id, "u-sup", content="Edited")
        assert updated.is_edited is True
        with pytest.raises(ValueError):
            await svc.update_comment(comment.id, "other-user", content="nope")
        with pytest.raises(ValueError):
            await svc.update_comment("ghost", "u-sup", content="nope")

        vote = await svc.vote_on_comment(comment.id, "voter1", "up")
        assert vote.vote_type == "up"
        with pytest.raises(ValueError):
            await svc.vote_on_comment(comment.id, "voter1", "sideways")

        summary = await svc.get_session_feedback_summary(session.id)
        assert summary["upvotes"] == 1
        assert summary["comment_count"] == 1


# ============================================================================
# DataTaintTracker (P4)
# ============================================================================

class TestDataTaint:
    def test_classify_sensitivity(self):
        from core.data_taint_tracker import classify_sensitivity
        assert classify_sensitivity("") == "internal"
        assert classify_sensitivity("public marketing copy") == "public"
        assert classify_sensitivity("confidential budget review") == "confidential"
        assert classify_sensitivity("restricted access only") == "restricted"
        assert classify_sensitivity("plain internal note") == "internal"
        assert classify_sensitivity("email r.parikh@example.com here") == "restricted"

    def test_credit_card_luhn(self):
        from core.data_taint_tracker import classify_sensitivity
        assert classify_sensitivity("card 4111 1111 1111 1111") == "restricted"
        assert classify_sensitivity("count 1234 5678 9012 3456") != "restricted"

    def test_higher_sensitivity(self):
        from core.data_taint_tracker import higher_sensitivity
        assert higher_sensitivity("internal", "restricted") == "restricted"
        assert higher_sensitivity("restricted", "public") == "restricted"
        assert higher_sensitivity("internal", "public") == "internal"

    def test_tracker_observe_and_outbound(self):
        from core.data_taint_tracker import DataTaintTracker
        t = DataTaintTracker(run_id="r1")
        assert t.max_observed() == "public"
        t.observe("confidential strategy doc", source="doc-1")
        t.observe("public stuff")
        assert t.max_observed() == "confidential"
        assert t.check_outbound("internal") == {"allowed": True}
        res = t.check_outbound("external", service="slack")
        assert res["allowed"] is False
        assert res["violation_type"] == "provenance"
        assert res["max_observed"] == "confidential"
        meta = t.to_metadata()
        assert meta["run_id"] == "r1"
        assert "confidential" in meta["observed_labels"]
        assert meta["sources"]["confidential"] == ["doc-1"]

    def test_tracker_blocks_restricted(self):
        from core.data_taint_tracker import DataTaintTracker
        t = DataTaintTracker()
        t.observe("customer email a@b.com")
        res = t.check_outbound("external")
        assert res["allowed"] is False
        assert res["max_observed"] == "restricted"

    def test_tracker_clean_outbound(self):
        from core.data_taint_tracker import DataTaintTracker
        t = DataTaintTracker()
        t.observe("public sales report")
        assert t.check_outbound("external")["allowed"] is True


# ============================================================================
# Sandbox Gate (P9)
# ============================================================================

class TestSandboxGate:
    def test_disabled_returns_none(self):
        from core.sandbox_gate import evaluate_tool_call
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=False):
            assert evaluate_tool_call("browser_click", {}, {}) is None

    def test_no_run_id_returns_none(self):
        from core.sandbox_gate import evaluate_tool_call
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=True):
            assert evaluate_tool_call("browser_click", {}, {"tier": "autonomous"}) is None

    def test_no_tier_returns_none(self):
        from core.sandbox_gate import evaluate_tool_call
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=True):
            assert evaluate_tool_call("browser_click", {}, {"run_id": "r1"}) is None

    def test_killrun_blocks(self, fresh_db):
        from core.sandbox_gate import evaluate_tool_call
        from core import sandbox_killrun
        sandbox_killrun.trigger_killrun(
            "run-killed", reason="tripwire test",
            tripwire_id="tw-1", execution_id="run-killed",
        )
        try:
            with patch("core.sandbox_config.is_sandbox_enabled", return_value=True), \
                 patch("core.sandbox_audit.write_violation") as mock_audit:
                decision = evaluate_tool_call(
                    "browser_click", {},
                    {"run_id": "run-killed", "tier": "autonomous", "tenant_id": "t1"},
                )
            assert decision is not None
            assert decision.decision == "blocked"
            assert decision.killrun_triggered is True
            mock_audit.assert_called_once()
        finally:
            sandbox_killrun.get_registry().release("run-killed")

    def test_allowed_path_returns_decision(self, fresh_db):
        from core.sandbox_gate import evaluate_tool_call
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=True), \
             patch("core.sandbox_config.is_sandbox_whitelist_enabled", return_value=False):
            decision = evaluate_tool_call(
                "browser_click", {"url": "https://example.com"},
                {"run_id": "r-safe", "tier": "autonomous", "agent_id": "a1"},
            )
        assert decision is not None
        assert decision.decision == "allowed"

    def test_exception_fails_open(self):
        from core.sandbox_gate import evaluate_tool_call
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=True), \
             patch("core.sandbox_config.is_sandbox_whitelist_enabled",
                   side_effect=RuntimeError("boom")):
            decision = evaluate_tool_call(
                "browser_click", {},
                {"run_id": "r-x", "tier": "supervised"},
            )
        assert decision is not None
        assert decision.decision == "allowed"
        assert "error" in (decision.metadata_json or {})


# ============================================================================
# Integration: two-way learning round-trip (no mocks)
# ============================================================================

class TestRoundTrip:
    @pytest.mark.asyncio
    async def test_rating_then_insights_round_trip(self, fresh_db):
        from core.feedback_service import FeedbackService
        from core.supervisor_learning_service import SupervisorLearningService
        from core.supervisor_performance_service import SupervisorPerformanceService
        agent = _agent(fresh_db)
        session = _completed_session(fresh_db, agent, rating=5)
        fb = FeedbackService(fresh_db)
        await fb.rate_supervisor(
            supervision_session_id=session.id, rater_id="system_u-sup",
            rating=5, rating_category="session_outcome", agent_id=agent.id,
        )
        learning = SupervisorLearningService(fresh_db)
        result = await learning.process_feedback_for_learning(
            "u-sup", "rating", {"rating": 5, "session_id": session.id}
        )
        assert result["new_confidence"] > 0.5
        perf = SupervisorPerformanceService(fresh_db)
        metrics = await perf.get_supervisor_metrics("u-sup")
        assert metrics["overall"]["total_sessions"] >= 1
        insights = await learning.calculate_learning_insights("u-sup")
        assert insights["current_state"]["confidence_score"] > 0.5
