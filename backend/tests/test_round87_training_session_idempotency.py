"""R87 RED tests — training-session completion must be idempotent.

Finding: StudentTrainingService.complete_training_session had no
completed-state guard. A retried POST /api/maturity/training/sessions/{id}/complete
(or double-click) applied the confidence boost a second time, re-ran the
INTERN readiness evaluation against inflated session counts, and re-flipped
the proposal to EXECUTED. Confidence feeds SpecialistMatcher, fleet routing,
and governance maturity mapping, so double-counting is a privilege-adjacent
integrity bug.
"""
import asyncio
import os
import tempfile

import pytest
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import AgentRegistry, AgentStatus, TrainingSession
from core.student_training_service import StudentTrainingService, TrainingOutcome


@pytest.fixture
def db():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    for table in Base.metadata.sorted_tables:
        try:
            table.create(engine, checkfirst=True)
        except exc.NoReferencedTableError:
            continue
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def student_and_session(db):
    agent = AgentRegistry(
        id="agent-stu",
        name="Trainee",
        category="sales",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.40,
        capabilities=[],
        module_path="core.generic_agent",
        class_name="GenericAgent",
    )
    session = TrainingSession(
        id="sess-1",
        tenant_id="tenant-1",
        proposal_id="prop-1",
        agent_id="agent-stu",
        agent_name="Trainee",
        supervisor_id="supervisor-1",
        status="in_progress",
    )
    db.add_all([agent, session])
    db.commit()
    return agent, session


def _outcome():
    return TrainingOutcome(
        performance_score=0.9,
        supervisor_feedback="Great rehearsal",
        errors_count=0,
        tasks_completed=5,
        total_tasks=5,
        capabilities_developed=["crm_updates"],
        capability_gaps_remaining=[],
    )


def test_double_completion_applies_boost_once(db, student_and_session):
    agent, _session = student_and_session
    svc = StudentTrainingService(db)

    first = asyncio.run(svc.complete_training_session("sess-1", _outcome()))
    confidence_after_first = agent.confidence_score
    assert confidence_after_first > 0.40  # boost applied once

    second = asyncio.run(svc.complete_training_session("sess-1", _outcome()))
    assert agent.confidence_score == confidence_after_first, (
        "duplicate completion re-applied the confidence boost"
    )
    assert second["promoted_to_intern"] is False or first["promoted_to_intern"]


def test_duplicate_completion_reports_already_completed(db, student_and_session):
    _agent, _session = student_and_session
    svc = StudentTrainingService(db)

    asyncio.run(svc.complete_training_session("sess-1", _outcome()))
    repeat = asyncio.run(svc.complete_training_session("sess-1", _outcome()))

    assert repeat.get("already_completed") is True
    assert repeat["confidence_boost"] == 0.0


def test_session_counts_not_inflated_by_retries(db, student_and_session):
    """The evidence gate counts completed sessions — retries must not add."""
    from core.models import AgentEpisode

    agent, _session = student_and_session
    # Give the agent exactly one clean episode so a single legit completion
    # could satisfy ratio floors but repeated counting would inflate.
    db.add(AgentEpisode(
        agent_id="agent-stu",
        tenant_id="tenant-1",
        task_description="rehearsal",
        outcome="success",
        maturity_at_time="student",
    ))
    db.commit()

    svc = StudentTrainingService(db)
    asyncio.run(svc.complete_training_session("sess-1", _outcome()))
    snapshot_first = dict(
        svc._evaluate_intern_readiness(agent)
    ) if hasattr(svc, "_evaluate_intern_readiness") else {}

    asyncio.run(svc.complete_training_session("sess-1", _outcome()))
    after_retry = svc._evaluate_intern_readiness(agent)

    if snapshot_first:
        assert after_retry.get("completed_sessions") == snapshot_first.get(
            "completed_sessions"
        ), "retry inflated completed-session count"
