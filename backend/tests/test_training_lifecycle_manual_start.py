"""GOV-04 — real training lifecycle, not a maturity assignment shortcut.

Start a training round as a STUDENT, persist the proposal and its guidance,
approve it into a session, complete the session from linked work evidence,
and observe the approval-gated promotion. Directly setting
``agent.status = intern`` is never part of the path.
"""
from __future__ import annotations

import asyncio
import os

os.environ.setdefault("TESTING", "1")

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models import (
    AgentEpisode,
    AgentProposal,
    AgentRegistry,
    Base,
    ProposalStatus,
    TrainingSession,
    User,
    UserRole,
)
from core.student_training_service import StudentTrainingService, TrainingOutcome


@pytest.fixture()
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    monkeypatch.setenv("ATOM_TRAINING_REQUIRE_EVIDENCE", "1")
    monkeypatch.setenv("ATOM_TRAINING_MIN_EVIDENCE_EPISODES", "3")
    monkeypatch.setenv("ATOM_PROMOTION_MIN_TRAINING_SESSIONS", "1")
    monkeypatch.setenv("ATOM_PROMOTION_MIN_EPISODES", "3")
    monkeypatch.setenv("ATOM_PROMOTION_MIN_SUCCESS_RATIO", "0.7")
    monkeypatch.setenv("ATOM_PROMOTION_DYNAMIC_TUNING", "false")
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _student(db):
    row = AgentRegistry(
        id="student-1", name="New Hire", category="Operations",
        module_path="tests.student", class_name="StudentAgent",
        status="student", confidence_score=0.5, capabilities=[],
        workspace_id="default", tenant_id="default",
    )
    db.add(row)
    db.commit()
    return row


def test_start_creates_only_a_pending_proposal_with_guidance(db):
    _student(db)
    service = StudentTrainingService(db)
    proposal = asyncio.run(service.start_training(
        "student-1", "supervisor-1", reason="onboarding",
        capability_gaps=["vendor_reconciliation"]))

    assert proposal.status == ProposalStatus.PENDING_APPROVAL.value
    assert db.query(AgentProposal).filter(
        AgentProposal.id == proposal.id).first() is not None
    assert db.query(TrainingSession).count() == 0
    agent = db.query(AgentRegistry).filter(
        AgentRegistry.id == "student-1").first()
    assert agent.status == "student", "starting training must not assign maturity"
    assert "vendor_reconciliation" in (
        proposal.proposal_data or {}).get("capability_gaps", [])


def test_start_route_is_supervisor_only_and_persists_proposal(db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from unittest.mock import Mock

    from api.agent_maturity_routes import router
    from core.auth import get_current_user
    from core.database import get_db as _get_db

    _student(db)
    db.add(User(
        id="lead-1", email="lead@example.com", first_name="Lead",
        last_name="One", role=UserRole.TEAM_LEAD.value, status="active",
    ))
    db.add(User(
        id="member-1", email="member@example.com", first_name="Mem",
        last_name="Ber", role=UserRole.MEMBER.value, status="active",
    ))
    db.commit()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[_get_db] = lambda: db

    app.dependency_overrides[get_current_user] = lambda: Mock(
        id="lead-1", tenant_id=None, status="active")
    lead = TestClient(app)
    response = lead.post("/api/maturity/training/start", json={
        "agent_id": "student-1", "reason": "manual onboarding",
        "capability_gaps": ["vendor_reconciliation"],
    })
    assert response.status_code == 200, response.text
    proposal_id = response.json()["proposal_id"]
    assert db.query(AgentProposal).filter(
        AgentProposal.id == proposal_id).first() is not None
    assert db.query(TrainingSession).count() == 0

    app.dependency_overrides[get_current_user] = lambda: Mock(
        id="member-1", tenant_id=None, status="active")
    member = TestClient(app)
    denied = member.post("/api/maturity/training/start", json={
        "agent_id": "student-1"})
    assert denied.status_code == 403


def test_approve_creates_session_with_guidance_then_completion_promotes(db):
    _student(db)
    service = StudentTrainingService(db)
    proposal = asyncio.run(service.start_training(
        "student-1", "supervisor-1", reason="onboarding"))

    session = asyncio.run(service.approve_training(
        proposal.id, "supervisor-1"))
    assert session.status == "scheduled"
    assert session.supervisor_guidance.get("lesson_plan")
    assert session.supervisor_guidance["lesson_plan"].get("tasks")
    assert db.query(TrainingSession).filter(
        TrainingSession.id == session.id).first() is not None

    # The hire must actually perform supervised work inside the session
    # window; completion grades the ledger, not the supervisor's typed score.
    for index in range(3):
        db.add(AgentEpisode(
            id=f"ep-{index}", agent_id="student-1", tenant_id="default",
            maturity_at_time="student", outcome="success", success=True,
            status="completed", started_at=datetime.now(timezone.utc),
        ))
    db.commit()

    result = asyncio.run(service.complete_training_session(
        session.id,
        TrainingOutcome(
            performance_score=1.0,
            supervisor_feedback="supervised pass completed",
            errors_count=0,
            tasks_completed=3,
            total_tasks=3,
            capabilities_developed=["vendor_reconciliation"],
            capability_gaps_remaining=[],
        ),
    ))
    assert result["evidence"]["episodes"] == 3
    assert result["promoted_to_intern"] is True
    agent = db.query(AgentRegistry).filter(
        AgentRegistry.id == "student-1").first()
    assert agent.status == "intern"
    executed = db.query(AgentProposal).filter(
        AgentProposal.id == proposal.id).first()
    assert executed.status == ProposalStatus.EXECUTED.value

    # Completion is idempotent: a retry cannot double-apply confidence.
    again = asyncio.run(service.complete_training_session(
        session.id,
        TrainingOutcome(
            performance_score=1.0,
            supervisor_feedback="retry",
            errors_count=0,
            tasks_completed=3,
            total_tasks=3,
            capabilities_developed=[],
            capability_gaps_remaining=[],
        ),
    ))
    assert again["already_completed"] is True
    assert db.query(AgentRegistry).filter(
        AgentRegistry.id == "student-1").first().confidence_score == (
            agent.confidence_score)


def test_unauthorized_transitions_and_insufficient_evidence(db):
    """Invalid lifecycle transitions are refused; no evidence, no promotion."""
    _student(db)
    service = StudentTrainingService(db)

    # Unknown proposal / session.
    with pytest.raises(ValueError):
        asyncio.run(service.approve_training("missing-proposal", "supervisor-1"))
    with pytest.raises(ValueError):
        asyncio.run(service.complete_training_session(
            "missing-session",
            TrainingOutcome(
                performance_score=1.0, supervisor_feedback="x",
                errors_count=0, tasks_completed=0, total_tasks=1,
                capabilities_developed=[], capability_gaps_remaining=[])))

    # Approve once, then a second approval of the same proposal is refused.
    proposal = asyncio.run(service.start_training(
        "student-1", "supervisor-1", reason="onboarding"))
    asyncio.run(service.approve_training(proposal.id, "supervisor-1"))
    with pytest.raises(ValueError):
        asyncio.run(service.approve_training(proposal.id, "supervisor-1"))

    # A session completed with no linked evidence cannot promote.
    db.add(AgentRegistry(
        id="student-2", name="Second Hire", category="Operations",
        module_path="tests.student", class_name="StudentAgent",
        status="student", confidence_score=0.5, capabilities=[],
        workspace_id="default", tenant_id="default",
    ))
    db.commit()
    second = asyncio.run(service.start_training(
        "student-2", "supervisor-1", reason="second round"))
    session = asyncio.run(service.approve_training(second.id, "supervisor-1"))
    from core.student_training_service import InsufficientTrainingEvidenceError

    with pytest.raises(InsufficientTrainingEvidenceError):
        asyncio.run(service.complete_training_session(
            session.id,
            TrainingOutcome(
                performance_score=1.0,
                supervisor_feedback="no evidence recorded",
                errors_count=0,
                tasks_completed=3,
                total_tasks=3,
                capabilities_developed=[],
                capability_gaps_remaining=[],
            ),
        ))
    agent = db.query(AgentRegistry).filter(
        AgentRegistry.id == "student-2").first()
    assert agent.status == "student"


def test_repeated_start_reuses_the_proposal_without_a_duplicate_session(db):
    _student(db)
    service = StudentTrainingService(db)
    first = asyncio.run(service.start_training(
        "student-1", "supervisor-1", reason="onboarding"))
    second = asyncio.run(service.start_training(
        "student-1", "supervisor-1", reason="retry"))
    assert second.id == first.id
    assert db.query(AgentProposal).count() == 1
    assert db.query(TrainingSession).count() == 0

    asyncio.run(service.approve_training(first.id, "supervisor-1"))
    assert db.query(TrainingSession).count() == 1
