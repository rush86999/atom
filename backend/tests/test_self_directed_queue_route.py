"""GET /api/maturity/training/self-directed — the STUDENT validation queue.

Powers the Training panel's graduation card: for each STUDENT agent, the
evidence vs the graduation floors, the readiness verdict, guidance steps,
and the recent outcome-tracked work. ``agent_id`` narrows to one agent;
promote goes through the existing graduation endpoint.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.agent_maturity_routes import router
from core.auth import get_current_user
from core.database import get_db as _get_db
from core.models import AgentRegistry, AgentStatus, User, UserRole


# ============================================================================
# Fixtures / seed helpers
# ============================================================================


def _make_client(db, viewer_id: str) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: Mock(
        id=viewer_id, tenant_id=None, status="active"
    )
    app.dependency_overrides[_get_db] = lambda: db
    return TestClient(app)


@pytest.fixture
def supervisor_client(db_session):
    db_session.add(User(
        id="sd-lead", email="sd-lead@example.com", first_name="Sd",
        last_name="Lead", role=UserRole.TEAM_LEAD.value, status="active",
    ))
    db_session.commit()
    return _make_client(db_session, "sd-lead")


def _student(db, agent_id="sd-agent-1", name="Student Hire",
             confidence=0.6, status=AgentStatus.STUDENT.value):
    agent = AgentRegistry(
        id=agent_id, name=name, category="email",
        module_path="m", class_name="C", status=status,
        confidence_score=confidence,
    )
    db.add(agent)
    db.commit()
    return agent


# ============================================================================
# Queue + single-agent snapshot
# ============================================================================


def test_queue_returns_student_snapshot(supervisor_client, db_session):
    _student(db_session)
    resp = supervisor_client.get("/api/maturity/training/self-directed")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    progress = body["agents"][0]
    # payload shape the SelfDirectedPathwayCard renders
    for key in ("agent_name", "tier", "confidence", "episode_progress",
                "ready_for_review", "readiness", "recent_episodes", "guidance",
                "evidence"):
        assert key in progress, key
    assert progress["tier"] == AgentStatus.STUDENT.value
    assert isinstance(progress["guidance"], list) and progress["guidance"]


def test_queue_narrows_by_agent_id(supervisor_client, db_session):
    _student(db_session, "sd-agent-1", name="One")
    _student(db_session, "sd-agent-2", name="Two")
    resp = supervisor_client.get(
        "/api/maturity/training/self-directed", params={"agent_id": "sd-agent-2"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["agents"][0]["agent_name"] == "Two"


def test_queue_excludes_non_student_tiers(supervisor_client, db_session):
    _student(db_session, "sd-agent-1")
    _student(db_session, "sd-intern", name="Already Intern",
             status=AgentStatus.INTERN.value)
    resp = supervisor_client.get("/api/maturity/training/self-directed")
    body = resp.json()
    names = [a["agent_name"] for a in body["agents"]]
    assert names == ["Student Hire"]


def test_unknown_agent_id_returns_empty_queue(supervisor_client, db_session):
    resp = supervisor_client.get(
        "/api/maturity/training/self-directed", params={"agent_id": "nope"}
    )
    assert resp.status_code == 200
    assert resp.json() == {"agents": [], "count": 0}


def test_snapshot_degrades_when_readiness_evaluation_fails(
    supervisor_client, db_session, monkeypatch
):
    """The card must render even when the multi-pathway readiness
    evaluation explodes — pathway degrades to unknown, never a 500."""
    _student(db_session)

    def _boom(self, agent):
        raise RuntimeError("readiness engine down")

    # the import inside snapshot() is lazy — patch the service class method
    from core.student_training_service import StudentTrainingService
    monkeypatch.setattr(
        StudentTrainingService, "_evaluate_intern_readiness", _boom
    )
    resp = supervisor_client.get("/api/maturity/training/self-directed")
    assert resp.status_code == 200
    progress = resp.json()["agents"][0]
    assert progress["readiness"]["pathway"] in (None, "unknown")


# ============================================================================
# Promotion (supervisor judgment via the existing graduation endpoint —
# this queue only supplies the evidence, so here we pin the queue's
# student-only contract that the UI relies on)
# ============================================================================


def test_promoted_agent_leaves_the_queue(supervisor_client, db_session):
    from core.models import AgentStatus as _AS

    agent = _student(db_session, "sd-agent-1")
    agent.status = _AS.INTERN.value
    db_session.commit()
    resp = supervisor_client.get("/api/maturity/training/self-directed")
    assert resp.json()["count"] == 0
