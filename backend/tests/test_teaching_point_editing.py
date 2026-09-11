"""Teaching-point editing.

The canvas Training tab shows the agent's learning journal (see
``GET /api/maturity/training/context`` → ``teaching_points``). Lessons are
PERMANENT — ``get_agent_lessons`` injects them into every chat turn, canvas
edit plan, and task execution — so a bad, duplicated, or superseded point must
be correctable in place, not only appendable:

- ``PATCH  /api/maturity/agents/{agent_id}/teaching-points/{point_id}``
- ``DELETE /api/maturity/agents/{agent_id}/teaching-points/{point_id}``

Editing is the correction of a lesson any signed-in human may teach (parity
with ``POST /api/agents/{id}/teach``); deleting standing guidance is
destructive and stays supervisor-gated (TEAM_LEAD+, the R65 gate).
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import Mock

from api.agent_maturity_routes import router
from core.auth import get_current_user
from core.database import get_db as _get_db
from core.models import AgentRegistry, AgentStatus, Canvas, CanvasAudit, User, UserRole
from core.student_learning_service import (
    delete_teaching_point,
    get_agent_lessons,
    update_teaching_point,
)


# ============================================================================
# Fixtures / helpers
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
        id="tp-lead", email="tp-lead@example.com", first_name="Tp",
        last_name="Lead", role=UserRole.TEAM_LEAD.value, status="active",
    ))
    db_session.commit()
    return _make_client(db_session, "tp-lead")


@pytest.fixture
def member_client(db_session):
    db_session.add(User(
        id="tp-member", email="tp-member@example.com", first_name="Tp",
        last_name="Member", role=UserRole.MEMBER.value, status="active",
    ))
    db_session.commit()
    return _make_client(db_session, "tp-member")


LOG = [
    {"source": "teacher", "teacher_agent_id": "human_supervisor",
     "topic": "email tone", "lesson": "Keep refund emails short.",
     "learned_at": "2026-08-30T10:00:00+00:00"},
    {"source": "observation", "observation_type": "human_correction",
     "summary": "Supervisor fixed the greeting.",
     "learned_at": "2026-08-31T09:00:00+00:00"},
]


def _agent(db, agent_id="agent-1", log=None, tenant_id="default", confidence=0.3):
    agent = AgentRegistry(
        id=agent_id, name="Hire One", category="email",
        module_path="m", class_name="C", status=AgentStatus.STUDENT.value,
        confidence_score=confidence, tenant_id=tenant_id, workspace_id="default",
        configuration={"learning": {"log": [dict(e) for e in (log if log is not None else LOG)]}},
    )
    db.add(agent)
    db.commit()
    return agent


def _canvas(db, canvas_id="cv-tp"):
    canvas = Canvas(
        id=canvas_id, tenant_id="default", workspace_id="default",
        created_by="tp-lead", name="Canvas", canvas_type="document",
        content={"type": "doc"}, status="active",
    )
    db.add(canvas)
    db.commit()
    return canvas


def _read_context(client, agent, canvas_id="cv-tp", db=None):
    if db is not None:
        # Force a real SELECT: the edit must be persisted, not just mutated
        # on the session's identity-mapped instance.
        db.expire_all()
    resp = client.get(
        "/api/maturity/training/context",
        params={"canvas_id": canvas_id, "agent_id": agent.id},
    )
    assert resp.status_code == 200
    return resp.json()["teaching_points"]


def _log(db, agent_id="agent-1"):
    from core.models import AgentRegistry as _A

    db.expire_all()
    row = db.query(_A).filter(_A.id == agent_id).first()
    return row.configuration["learning"]["log"]


# ============================================================================
# Service layer
# ============================================================================


class TestTeachingPointService:
    def test_edit_teacher_lesson_text_and_topic(self, db_session):
        agent = _agent(db_session)

        result = update_teaching_point(
            db_session, agent.id, "log:0",
            text="Keep refund emails under three sentences.",
            topic="refund tone",
        )

        assert result["status"] == "ok"
        entry = _log(db_session)[0]
        assert entry["lesson"] == "Keep refund emails under three sentences."
        assert entry["topic"] == "refund tone"
        assert entry["learned_at"] == "2026-08-30T10:00:00+00:00"  # preserved
        assert entry["edited_at"]  # stamped
        assert entry["id"]  # a stable id is minted on first edit

    def test_edit_does_not_touch_other_entries_or_confidence(self, db_session):
        agent = _agent(db_session, confidence=0.3)

        update_teaching_point(db_session, agent.id, "log:0", text="Rewritten rule.")

        log = _log(db_session)
        assert log[0]["lesson"] == "Rewritten rule."
        assert log[1]["summary"] == "Supervisor fixed the greeting."
        assert log[1].get("edited_at") is None
        db_session.refresh(agent)
        assert agent.confidence_score == pytest.approx(0.3)

    def test_edit_observation_edits_the_summary(self, db_session):
        agent = _agent(db_session)

        result = update_teaching_point(
            db_session, agent.id, "log:1", text="Corrected: always greet by name.",
        )

        assert result["status"] == "ok"
        assert _log(db_session)[1]["summary"] == "Corrected: always greet by name."

    def test_topic_is_not_editable_on_observations(self, db_session):
        """observation_type classifies the entry (human_correction IS standing
        guidance) — retyping it via a topic edit would silently change how the
        lesson is applied at work time."""
        agent = _agent(db_session)

        result = update_teaching_point(
            db_session, agent.id, "log:1", text="x", topic="hitl_approval",
        )

        assert result["status"] == "error"
        assert result["reason"] == "topic_not_editable"
        assert _log(db_session)[1]["observation_type"] == "human_correction"

    def test_legacy_entry_resolves_by_position_then_by_minted_id(self, db_session):
        agent = _agent(db_session)

        first = update_teaching_point(db_session, agent.id, "log:0", text="One.")
        assert first["status"] == "ok"
        minted = _log(db_session)[0]["id"]

        second = update_teaching_point(db_session, agent.id, minted, text="Two.")

        assert second["status"] == "ok"
        assert _log(db_session)[0]["lesson"] == "Two."
        # The positional handle is spent once the row carries a real id.
        assert update_teaching_point(db_session, agent.id, "log:0", text="Three.")["status"] == "error"

    def test_unknown_point_and_unknown_agent_report_not_found(self, db_session):
        agent = _agent(db_session)

        assert update_teaching_point(db_session, agent.id, "nope", text="x")["reason"] == "point_not_found"
        assert update_teaching_point(db_session, "ghost", "log:0", text="x")["reason"] == "agent_not_found"
        assert delete_teaching_point(db_session, agent.id, "log:99")["status"] == "error"

    def test_edit_reaches_work_time_lesson_injection(self, db_session):
        """The point of the journal: get_agent_lessons feeds every chat turn /
        canvas edit / task execution, so an edit must be what the agent gets."""
        agent = _agent(db_session)

        update_teaching_point(
            db_session, agent.id, "log:0",
            text="Never quote a rounded list price.",
        )

        lessons = get_agent_lessons(db_session, agent.id)
        teacher = next(entry for entry in lessons if entry.get("source") == "teacher")
        assert teacher["lesson"] == "Never quote a rounded list price."

    def test_delete_removes_only_the_targeted_entry(self, db_session):
        agent = _agent(db_session)

        result = delete_teaching_point(db_session, agent.id, "log:0")

        assert result["status"] == "ok"
        log = _log(db_session)
        assert len(log) == 1
        assert log[0]["observation_type"] == "human_correction"


# ============================================================================
# API routes
# ============================================================================


class TestTeachingPointRoutes:
    def test_read_payload_exposes_stable_ids(self, supervisor_client, db_session):
        agent = _agent(db_session)
        _canvas(db_session)

        points = _read_context(supervisor_client, agent)

        assert [p["id"] for p in points] == ["log:1", "log:0"]

    def test_supervisor_edit_is_reflected_in_the_journal(self, supervisor_client, db_session):
        agent = _agent(db_session)
        _canvas(db_session)

        resp = supervisor_client.patch(
            f"/api/maturity/agents/{agent.id}/teaching-points/log:0",
            json={"text": "Always CC the team lead.", "topic": "cc policy"},
        )

        assert resp.status_code == 200
        points = _read_context(supervisor_client, agent, db=db_session)
        teacher = next(p for p in points if p["source"] == "teacher")
        assert teacher["text"] == "Always CC the team lead."
        assert teacher["topic"] == "cc policy"
        assert teacher["edited_at"]
        assert teacher["id"]

    def test_member_may_edit_but_not_delete(self, member_client, db_session):
        """Teaching is the guidance channel any signed-in human owns (parity
        with /teach); removing standing guidance stays supervisor-only."""
        agent = _agent(db_session)
        _canvas(db_session)

        edit = member_client.patch(
            f"/api/maturity/agents/{agent.id}/teaching-points/log:0",
            json={"text": "Corrected wording."},
        )
        assert edit.status_code == 200

        delete = member_client.delete(
            f"/api/maturity/agents/{agent.id}/teaching-points/log:0"
        )
        assert delete.status_code == 403
        assert len(_log(db_session)) == 2

    def test_supervisor_delete_removes_the_point(self, supervisor_client, db_session):
        agent = _agent(db_session)
        _canvas(db_session)

        resp = supervisor_client.delete(
            f"/api/maturity/agents/{agent.id}/teaching-points/log:0"
        )

        assert resp.status_code == 200
        assert len(_log(db_session)) == 1

    def test_foreign_tenant_agent_404s(self, supervisor_client, db_session):
        agent = _agent(db_session, "agent-foreign", tenant_id="other-tenant")

        resp = supervisor_client.patch(
            f"/api/maturity/agents/{agent.id}/teaching-points/log:0",
            json={"text": "sneaky"},
        )

        assert resp.status_code == 404
        assert _log(db_session, "agent-foreign")[0]["lesson"] == "Keep refund emails short."

    def test_url_encoded_handle_resolves(self, supervisor_client, db_session):
        """The panel sends the handle URL-encoded (`log%3A0`); the route must
        decode it to the same positional handle."""
        agent = _agent(db_session)

        resp = supervisor_client.patch(
            f"/api/maturity/agents/{agent.id}/teaching-points/log%3A0",
            json={"text": "Encoded handle still edits the right lesson."},
        )

        assert resp.status_code == 200
        assert _log(db_session)[0]["lesson"] == "Encoded handle still edits the right lesson."

    def test_unknown_point_404s_and_empty_patch_400s(self, supervisor_client, db_session):
        agent = _agent(db_session)
        _canvas(db_session)

        missing = supervisor_client.patch(
            f"/api/maturity/agents/{agent.id}/teaching-points/log:42",
            json={"text": "x"},
        )
        assert missing.status_code == 404

        empty = supervisor_client.patch(
            f"/api/maturity/agents/{agent.id}/teaching-points/log:0", json={},
        )
        assert empty.status_code == 400
