"""Coverage wave 20 — SupervisorPerformance schema drift fix (TDD).

Real-bug probe: ``core/models.SupervisorPerformance`` was rewritten during the
Hive port to an approval-tracking schema (``approvals_granted``,
``supervisor_confidence`` ...) while every consumer — ``SupervisorLearningService``
(``_get_or_create_performance``), ``FeedbackService.rate_supervisor``
(``_update_supervisor_performance``) and ``SupervisorPerformanceService``
(``track_intervention_outcome`` / leaderboard / trends) — still uses the
learning schema columns:

    confidence_score, competence_level, learning_rate, performance_trend,
    total_sessions_supervised, total_interventions, average_rating,
    total_ratings, rating_1_count..5_count, successful_interventions,
    failed_interventions, agents_promoted, agent_confidence_boosted,
    total_comments_given, total_upvotes_received, total_downvotes_received,
    last_updated

Every first-use crashed with: ``'confidence_score' is an invalid keyword
argument for SupervisorPerformance`` — the whole two-way-learning path from
``supervision_service.complete_supervision`` swallowed the exception and
logged ``Error processing supervision feedback``. This suite locks the
learning schema back onto the model so the real flow (no mocks) succeeds.
"""
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.feedback_service import FeedbackService
from core.models import (
    AgentExecution,
    AgentRegistry,
    AgentStatus,
    SupervisionSession,
    SupervisionStatus,
    SupervisorPerformance,
)
from core.supervisor_learning_service import SupervisorLearningService
from core.supervisor_performance_service import SupervisorPerformanceService


@pytest.fixture
def fresh_db():
    """Isolated temp-file SQLite DB per test (model schema is authoritative)."""
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
        workspace_id="ws-1",
    )
    db.add(agent)
    db.commit()
    return agent


def _completed_session(db, agent, supervisor_id="u-sup", rating=4):
    s = SupervisionSession(
        agent_id=agent.id, agent_name=agent.name, workspace_id="ws-1",
        trigger_context={"trigger_type": "manual"}, status="completed",
        supervisor_id=supervisor_id, supervisor_rating=rating,
        completed_at=datetime.now(timezone.utc),
        started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        duration_seconds=300,
    )
    db.add(s)
    db.commit()
    return s


class TestPerformanceModel:
    """RED: constructing with learning-schema kwargs must not raise."""

    def test_construct_with_learning_columns(self):
        perf = SupervisorPerformance(
            supervisor_id="s-1",
            confidence_score=0.5,
            competence_level="novice",
            learning_rate=0.0,
            performance_trend="stable",
            total_sessions_supervised=0,
            total_interventions=0,
            average_rating=0.0,
            total_ratings=0,
            successful_interventions=0,
            failed_interventions=0,
            agents_promoted=0,
            agent_confidence_boosted=0.0,
            total_comments_given=0,
            total_upvotes_received=0,
            total_downvotes_received=0,
        )
        assert perf.supervisor_id == "s-1"
        assert perf.confidence_score == 0.5
        assert perf.competence_level == "novice"

    def test_insert_and_read_back(self, fresh_db):
        perf = SupervisorPerformance(
            supervisor_id="s-2",
            confidence_score=0.7,
            competence_level="competent",
        )
        fresh_db.add(perf)
        fresh_db.commit()
        fresh_db.refresh(perf)
        assert perf.confidence_score == 0.7
        assert perf.learning_rate is not None
        row = fresh_db.query(SupervisorPerformance).filter(
            SupervisorPerformance.supervisor_id == "s-2"
        ).first()
        assert row is not None
        assert row.competence_level == "competent"
        assert row.performance_trend in ("stable", None)
        # tenant_id defaults so legacy constructors (no tenant) still insert
        assert row.tenant_id


class TestLearningService:
    """RED: _get_or_create_performance must persist learning columns."""

    @pytest.mark.asyncio
    async def test_get_or_create_persists_columns(self, fresh_db):
        svc = SupervisorLearningService(fresh_db)
        perf = await svc._get_or_create_performance("s-1")
        assert perf is not None
        assert perf.supervisor_id == "s-1"
        assert perf.confidence_score == 0.5
        assert perf.competence_level == "novice"
        fresh_db.expire_all()
        again = await svc._get_or_create_performance("s-1")
        assert again.id == perf.id  # idempotent

    @pytest.mark.asyncio
    async def test_process_feedback_updates_learning_columns(self, fresh_db):
        svc = SupervisorLearningService(fresh_db)
        perf = await svc._get_or_create_performance("s-1")
        await svc._process_rating(perf, {"rating": 5})
        fresh_db.commit()
        fresh_db.expire_all()
        row = fresh_db.query(SupervisorPerformance).filter(
            SupervisorPerformance.supervisor_id == "s-1"
        ).first()
        assert row.average_rating is not None
        assert row.confidence_score > 0.5


class TestFeedbackService:
    """RED: rate_supervisor → _update_supervisor_performance must not crash."""

    @pytest.mark.asyncio
    async def test_rate_supervisor_creates_performance(self, fresh_db):
        agent = _agent(fresh_db)
        session = _completed_session(fresh_db, agent)
        svc = FeedbackService(fresh_db)
        rating = await svc.rate_supervisor(
            supervision_session_id=session.id,
            rater_id="system_u-sup",
            rating=4,
            rating_category="session_outcome",
            agent_id=agent.id,
        )
        assert rating.rating == 4
        perf = fresh_db.query(SupervisorPerformance).filter(
            SupervisorPerformance.supervisor_id == "u-sup"
        ).first()
        assert perf is not None
        assert perf.confidence_score >= 0.5  # recalculated on first rating
        assert perf.total_sessions_supervised >= 0


class TestPerformanceService:
    """RED: track_intervention_outcome metrics path needs learning columns."""

    @pytest.mark.asyncio
    async def test_track_intervention_updates_metrics(self, fresh_db):
        agent = _agent(fresh_db)
        session = _completed_session(fresh_db, agent)
        fresh_db.add(SupervisorPerformance(
            supervisor_id="u-sup",
            confidence_score=0.5,
            competence_level="novice",
            total_interventions=0,
            successful_interventions=0,
            failed_interventions=0,
            total_sessions_supervised=1,
        ))
        fresh_db.commit()

        svc = SupervisorPerformanceService(fresh_db)
        outcome = await svc.track_intervention_outcome(
            supervision_session_id=session.id,
            intervention_type="correct",
            intervention_timestamp=datetime.now(),
            outcome="success",
            was_effective=True,
        )
        assert outcome.outcome == "success"

        fresh_db.expire_all()
        perf = fresh_db.query(SupervisorPerformance).filter(
            SupervisorPerformance.supervisor_id == "u-sup"
        ).first()
        assert perf.total_interventions == 1
        assert perf.successful_interventions == 1
        assert perf.confidence_score == 0.51
        assert perf.last_updated is not None

    @pytest.mark.asyncio
    async def test_get_performance_summary_learning_fields(self, fresh_db):
        fresh_db.add(SupervisorPerformance(
            supervisor_id="u-sup",
            confidence_score=0.8,
            competence_level="expert",
            total_sessions_supervised=5,
            total_interventions=3,
            successful_interventions=2,
            agents_promoted=1,
            agent_confidence_boosted=0.2,
            average_rating=4.5,
        ))
        fresh_db.commit()
        svc = SupervisorPerformanceService(fresh_db)
        summary = await svc.get_supervisor_metrics("u-sup")
        assert summary["overall"]["confidence_score"] == 0.8
        assert summary["overall"]["competence_level"] == "expert"
        assert summary["overall"]["total_sessions"] == 5
        assert summary["overall"]["total_interventions"] == 3
        assert summary["learning"]["agents_promoted"] == 1


class TestSupervisionTwoWayLearning:
    """RED: the real complete_supervision flow must not log feedback errors."""

    @pytest.mark.asyncio
    async def test_complete_supervision_full_flow(self, fresh_db):
        agent = _agent(fresh_db)
        from core.supervision_service import SupervisionService

        svc = SupervisionService(fresh_db)
        session = await svc.start_supervision_session(
            agent_id=agent.id, trigger_context={"trigger_type": "manual"},
            workspace_id="ws-1", supervisor_id="u-sup",
        )
        fresh_db.add(AgentExecution(
            id=f"exec-{uuid.uuid4().hex[:8]}", agent_id=agent.id,
            status="running", started_at=datetime.now(timezone.utc),
            workspace_id="ws-1", triggered_by="test",
        ))
        fresh_db.commit()

        with patch("core.supervision_service.logger") as mock_logger, \
             patch("core.supervision_service.asyncio.create_task") as mock_task:
            outcome = await svc.complete_supervision(
                session_id=session.id,
                supervisor_rating=4,
                feedback="good work",
            )
            # run the scheduled task inline
            for call in mock_task.call_args_list:
                await call.args[0]

        assert outcome.success is True
        errors = [str(c) for c in mock_logger.error.call_args_list]
        assert not any("processing supervision feedback" in e for e in errors), errors
        fresh_db.expire_all()
        done = fresh_db.query(SupervisionSession).filter(
            SupervisionSession.id == session.id
        ).first()
        assert done.status == "completed"
        perf = fresh_db.query(SupervisorPerformance).filter(
            SupervisorPerformance.supervisor_id == "u-sup"
        ).first()
        assert perf is not None


class TestInterventionPersist:
    """RED: in-place append must actually persist to DB (wave-19 rebind fix)."""

    @pytest.mark.asyncio
    async def test_intervention_survives_commit(self, fresh_db):
        agent = _agent(fresh_db)
        from core.supervision_service import SupervisionService

        svc = SupervisionService(fresh_db)
        session = await svc.start_supervision_session(
            agent_id=agent.id, trigger_context={"trigger_type": "manual"},
            workspace_id="ws-1", supervisor_id="u-sup",
        )
        await svc.intervene(
            session_id=session.id,
            intervention_type="pause",
            guidance="wait for approval",
        )
        fresh_db.expire_all()
        reloaded = fresh_db.query(SupervisionSession).filter(
            SupervisionSession.id == session.id
        ).first()
        assert reloaded.interventions
        assert reloaded.interventions[0]["type"] == "pause"
        assert reloaded.intervention_count == 1
