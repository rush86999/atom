"""GET /api/maturity/training/context — canvas training-panel resolver.

Powers the training panel on /canvas/{id}: resolves which agent is being
trained on a canvas and which training session it links to, following the
same precedence the product loop relies on (audit stamp ->
supervisor_guidance.canvas_id -> the agent's ACTIVE session), with the
tenant IDOR guard and the viewer role flag.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.agent_maturity_routes import router
from core.auth import get_current_user
from core.database import get_db as _get_db
from core.models import (
    AgentProposal,
    AgentRegistry,
    AgentStatus,
    Canvas,
    CanvasAudit,
    ProposalStatus,
    ProposalType,
    TrainingSession,
    User,
    UserRole,
)


# ============================================================================
# Fixtures / seed helpers
# ============================================================================


def _make_client(db, viewer_id: str) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    # Mock identity: tenant resolves via the attribute; the role check reads
    # the real User row below so viewer_is_supervisor reflects the DB.
    app.dependency_overrides[get_current_user] = lambda: Mock(
        id=viewer_id, tenant_id=None, status="active"
    )
    app.dependency_overrides[_get_db] = lambda: db
    return TestClient(app)


@pytest.fixture
def supervisor_client(db_session):
    db_session.add(User(
        id="ctx-lead", email="ctx-lead@example.com", first_name="Ctx",
        last_name="Lead", role=UserRole.TEAM_LEAD.value, status="active",
    ))
    db_session.commit()
    return _make_client(db_session, "ctx-lead")


@pytest.fixture
def member_client(db_session):
    db_session.add(User(
        id="ctx-member", email="ctx-member@example.com", first_name="Ctx",
        last_name="Member", role=UserRole.MEMBER.value, status="active",
    ))
    db_session.commit()
    return _make_client(db_session, "ctx-member")


def _agent(db, agent_id="agent-1", status=AgentStatus.STUDENT.value):
    agent = AgentRegistry(
        id=agent_id, name="Hire One", category="email",
        module_path="m", class_name="C", status=status, confidence_score=0.3,
    )
    db.add(agent)
    db.commit()
    return agent


def _proposal(db, agent, status=ProposalStatus.PENDING_APPROVAL.value):
    proposal = AgentProposal(
        tenant_id="default", user_id="ctx-lead", agent_id=agent.id,
        agent_name=agent.name, proposal_type=ProposalType.WORKFLOW.value,
        proposal_data={"capability_gaps": ["email"], "learning_objectives": ["obj"],
                       "estimated_duration_hours": 4},
        status=status, title="Training: email triage", description="d",
    )
    db.add(proposal)
    db.commit()
    return proposal


def _session(db, proposal, agent, status="in_progress", guidance=None):
    session = TrainingSession(
        tenant_id="default", proposal_id=proposal.id, agent_id=agent.id,
        agent_name=agent.name, status=status, supervisor_id="ctx-lead",
        supervisor_guidance=guidance or {},
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()
    return session


def _canvas(db, canvas_id="cv-1", content=None, tenant_id="default"):
    canvas = Canvas(
        id=canvas_id, tenant_id=tenant_id, workspace_id="default",
        created_by="ctx-lead", name="Canvas", canvas_type="document",
        content=content or {"type": "doc", "content": "draft"}, status="active",
    )
    db.add(canvas)
    db.commit()
    return canvas


def _audit(db, canvas_id, session_id=None, agent_id=None,
           action_type="create", tenant_id="default"):
    audit = CanvasAudit(
        canvas_id=canvas_id, tenant_id=tenant_id, session_id=session_id,
        agent_id=agent_id, canvas_type="document", action_type=action_type,
        user_id="ctx-lead", details_json={},
    )
    db.add(audit)
    db.commit()
    return audit


# ============================================================================
# Agent + session resolution
# ============================================================================


class TestTrainingCanvasResolution:
    def test_training_canvas_resolves_agent_and_session(self, supervisor_client, db_session):
        """The training mini-canvas (audit stamp + content.student) resolves
        both the trainee and its session in one read."""
        agent = _agent(db_session)
        proposal = _proposal(db_session, agent, status=ProposalStatus.APPROVED.value)
        session = _session(db_session, proposal, agent, guidance={
            "canvas_id": "cv-tr", "lesson_plan": {"objective": "Triage inbox", "tasks": ["t1"]},
        })
        _canvas(db_session, "cv-tr", content={
            "type": "training_session",
            "student": {"id": agent.id, "name": agent.name},
            "session_id": session.id,
        })
        _audit(db_session, "cv-tr", session_id=session.id, agent_id=agent.id,
               action_type="training_session_started")

        resp = supervisor_client.get("/api/maturity/training/context", params={"canvas_id": "cv-tr"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["agent"]["id"] == agent.id
        assert body["agent"]["tier"] == AgentStatus.STUDENT.value
        assert body["agent"]["confidence"] == 0.3
        assert body["linked_session"]["id"] == session.id
        assert body["linked_session"]["lesson_plan"]["objective"] == "Triage inbox"
        evidence = body["linked_session"]["evidence"]
        assert evidence["episodes"] == 0
        assert "required_episodes" in evidence
        assert body["viewer_is_supervisor"] is True

    def test_draft_canvas_falls_back_to_agents_active_session(self, supervisor_client, db_session):
        """A chat-draft canvas carries no session stamp, but the co-editor
        agent's ACTIVE session is still the one being trained — surface it."""
        agent = _agent(db_session)
        proposal = _proposal(db_session, agent, status=ProposalStatus.APPROVED.value)
        session = _session(db_session, proposal, agent, status="scheduled")
        _canvas(db_session, "cv-draft")
        _audit(db_session, "cv-draft", agent_id=agent.id, action_type="create")

        resp = supervisor_client.get("/api/maturity/training/context", params={"canvas_id": "cv-draft"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["agent"]["id"] == agent.id  # via the audit row's agent_id
        assert body["linked_session"]["id"] == session.id  # active-session fallback

    def test_guidance_canvas_id_links_without_audit_stamp(self, supervisor_client, db_session):
        """supervisor_guidance.canvas_id is an independent linkage path — a
        canvas with no training audit row still finds its session."""
        agent = _agent(db_session)
        proposal = _proposal(db_session, agent, status=ProposalStatus.APPROVED.value)
        session = _session(db_session, proposal, agent, guidance={"canvas_id": "cv-guid"})
        _canvas(db_session, "cv-guid")

        resp = supervisor_client.get("/api/maturity/training/context", params={"canvas_id": "cv-guid"})
        assert resp.status_code == 200
        assert resp.json()["linked_session"]["id"] == session.id

    def test_completed_round_yields_to_newer_active_session(self, supervisor_client, db_session):
        """A canvas tied to a COMPLETED round must show the agent's newer
        active session — the panel trains the present, not the history."""
        agent = _agent(db_session)
        p1 = _proposal(db_session, agent, status=ProposalStatus.EXECUTED.value)
        _session(db_session, p1, agent, status="completed", guidance={"canvas_id": "cv-old"})
        p2 = _proposal(db_session, agent, status=ProposalStatus.APPROVED.value)
        active = _session(db_session, p2, agent, status="in_progress")
        _canvas(db_session, "cv-old")

        resp = supervisor_client.get("/api/maturity/training/context", params={"canvas_id": "cv-old"})
        assert resp.status_code == 200
        assert resp.json()["linked_session"]["id"] == active.id

    def test_agent_hint_resolves_when_canvas_has_no_agent(self, supervisor_client, db_session):
        """Standalone canvases with no provenance still train via the
        client-supplied agent hint (chat-expanded canvases carry ?agent_id=)."""
        agent = _agent(db_session)
        _canvas(db_session, "cv-bare")

        resp = supervisor_client.get(
            "/api/maturity/training/context",
            params={"canvas_id": "cv-bare", "agent_id": agent.id},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["agent"]["id"] == agent.id
        assert body["linked_session"] is None

    def test_no_agent_at_all_returns_null_agent(self, supervisor_client, db_session):
        _canvas(db_session, "cv-anon")

        resp = supervisor_client.get("/api/maturity/training/context", params={"canvas_id": "cv-anon"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["agent"] is None
        assert body["linked_session"] is None
        assert body["pending_proposal"] is None


class TestPendingProposalSurface:
    def test_pending_proposal_returned_when_no_active_session(self, supervisor_client, db_session):
        agent = _agent(db_session)
        proposal = _proposal(db_session, agent)  # pending_approval
        _canvas(db_session, "cv-pend")

        resp = supervisor_client.get(
            "/api/maturity/training/context",
            params={"canvas_id": "cv-pend", "agent_id": agent.id},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["linked_session"] is None
        assert body["pending_proposal"]["id"] == proposal.id
        assert body["pending_proposal"]["capability_gaps"] == ["email"]


# ============================================================================
# Access control
# ============================================================================


class TestContextAccessControl:
    def test_foreign_tenant_canvas_404s(self, supervisor_client, db_session):
        """A canvas outside the viewer's tenant must 404 — no existence leak."""
        _canvas(db_session, "cv-foreign", tenant_id="other-tenant")

        resp = supervisor_client.get("/api/maturity/training/context", params={"canvas_id": "cv-foreign"})
        assert resp.status_code == 404

    def test_unknown_canvas_404s(self, supervisor_client):
        resp = supervisor_client.get("/api/maturity/training/context", params={"canvas_id": "nope"})
        assert resp.status_code == 404

    def test_member_viewer_gets_role_flag_not_a_gate(self, member_client, db_session):
        """Employees legitimately open the panel (teach + progress) — the
        endpoint returns viewer_is_supervisor=False instead of 403."""
        agent = _agent(db_session)
        _canvas(db_session, "cv-member")
        _audit(db_session, "cv-member", agent_id=agent.id)

        resp = member_client.get("/api/maturity/training/context", params={"canvas_id": "cv-member"})
        assert resp.status_code == 200
        assert resp.json()["viewer_is_supervisor"] is False
