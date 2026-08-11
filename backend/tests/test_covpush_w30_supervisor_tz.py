"""Coverage wave 30 — supervisor timezone correctness (TDD, real bug).

Picks up the round-13 bug class: ``core/supervisor_performance_service.py`` and
``core/supervisor_learning_service.py`` compute time-range cutoffs with naive
``datetime.now()`` and compare them against ``DateTime(timezone=True)`` columns
(``assessed_at``, ``started_at``, ``created_at``). On PostgreSQL this raises
TypeError (aware vs naive comparison); on SQLite the wall-clock mismatch drops
rows aged within the last 5h30m of the window on any machine whose local time
is ahead of UTC.

These tests simulate a UTC+5:30 machine by stubbing the module-level ``datetime``
with a ``now()`` that returns a naive local wall clock 5h30m ahead of real UTC.
Rows are placed at ``now - 30d + 2h`` — inside the window for an aware UTC
cutoff, outside it for the naive local cutoff. With the bug, the rows are
excluded; with the fix, they are included and metrics/trends compute correctly.
"""
import asyncio
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

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

UTC_PLUS_5_30 = 5 * 60 + 30


class _KolkataWallClockDatetime:
    """Stand-in for the service modules' ``datetime``: ``now()`` returns the
    naive local wall clock of a UTC+5:30 machine (5h30m ahead of real UTC),
    while ``now(tz=...)`` returns the true aware UTC time."""

    @classmethod
    def now(cls, tz=None):
        if tz is not None:
            return datetime.now(timezone.utc)
        return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
            minutes=UTC_PLUS_5_30
        )


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


def _session(db, agent, supervisor_id="u-sup", rating=4):
    s = SupervisionSession(
        agent_id=agent.id, agent_name=agent.name, workspace_id="ws-1",
        trigger_context={"trigger_type": "manual"},
        status="completed",
        supervisor_id=supervisor_id, supervisor_rating=rating,
        completed_at=datetime.now(timezone.utc),
        started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        duration_seconds=300,
    )
    db.add(s)
    db.commit()
    return s


def _outcome(db, session, supervisor_id="u-sup", outcome="success", age=timedelta(days=30)):
    """Outcome aged ``age`` (default: 30 days — inside the 30d window only for
    an aware UTC cutoff, excluded by the naive local cutoff)."""
    ts = datetime.now(timezone.utc) - age + timedelta(hours=2)
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
        created_at=datetime.now(timezone.utc) - timedelta(days=30) + timedelta(hours=2),
    )
    db.add(r)
    db.commit()
    return r


def await_coroutine(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestPerformanceServiceTimeRangeCutoff:
    def test_cutoff_counts_recent_outcome(self, fresh_db):
        _performance(fresh_db)
        agent = _agent(fresh_db)
        sess = _session(fresh_db, agent)
        _outcome(fresh_db, sess, outcome="success")
        _outcome(fresh_db, sess, outcome="failure")
        svc = SupervisorPerformanceService(fresh_db)
        with patch("core.supervisor_performance_service.datetime", _KolkataWallClockDatetime):
            rate = await_coroutine(
                svc.calculate_intervention_success_rate("u-sup", time_range_days=30)
            )
            metrics = await_coroutine(svc.get_supervisor_metrics("u-sup", time_range_days=30))
        assert rate == 0.5
        assert metrics["interventions"]["total"] == 2

    def test_leaderboard_success_rate_counts_boundary_outcomes(self, fresh_db):
        _performance(fresh_db)
        agent = _agent(fresh_db)
        sess = _session(fresh_db, agent)
        _outcome(fresh_db, sess, outcome="success")
        svc = SupervisorPerformanceService(fresh_db)
        with patch("core.supervisor_performance_service.datetime", _KolkataWallClockDatetime):
            board = await_coroutine(svc.get_leaderboard(metric="success_rate"))
        assert board, "leaderboard must include the supervisor"
        assert board[0]["score"] == 1.0


class TestLearningServiceTimeRangeCutoff:
    def test_update_learning_metrics_sees_recent_ratings(self, fresh_db):
        perf = _performance(fresh_db, learning_rate=0.0, performance_trend="stable")
        # 10 boundary-aged ratings: first half 3s, second half 5s → improving.
        for i in range(10):
            _rating(fresh_db, rating=3 if i < 5 else 5)
        svc = SupervisorLearningService(fresh_db)
        with patch("core.supervisor_learning_service.datetime", _KolkataWallClockDatetime):
            await_coroutine(svc._update_learning_metrics(perf))
        assert perf.performance_trend == "improving"
        assert perf.learning_rate > 0

    def test_insights_include_boundary_ratings(self, fresh_db):
        _performance(fresh_db)
        for _ in range(3):
            _rating(fresh_db, rating=5)
        svc = SupervisorLearningService(fresh_db)
        with patch("core.supervisor_learning_service.datetime", _KolkataWallClockDatetime):
            insights = await_coroutine(svc.calculate_learning_insights("u-sup", time_range_days=30))
        assert insights["recent_feedback_summary"]["total_ratings"] == 3
