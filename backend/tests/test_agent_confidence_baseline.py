"""New-agent confidence baseline + step-feedback idempotency.

Two production incidents (Aug 30, the Sales Assistant):
1. Tier is a pure function of confidence (>=0.5 INTERN). New agents were
   created at exactly 0.5 on several paths, so the first +0.01 outcome
   drip promoted STUDENT→INTERN immediately — the student phase was
   unreachable. Fix: one shared baseline (NEW_AGENT_CONFIDENCE = 0.35)
   at every creation path and in the NULL fallback.
2. One thumbs-up submitted twice (page refresh + re-click) produced two
   identical AgentFeedback rows, each adjudicated, double-counting the
   confidence bump. Fix: the /api/reasoning/feedback idempotency guard.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from core.models_registration import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def _make_agent(db, agent_id="agent-1", name="Sales Assistant", confidence=None, status="student"):
    from core.models import AgentRegistry

    kwargs = dict(
        id=agent_id,
        name=name,
        category="Sales",
        module_path="core.generic_agent",
        class_name="GenericAgent",
        workspace_id="default",
        status=status,
    )
    if confidence is not None:
        kwargs["confidence_score"] = confidence
    db.add(AgentRegistry(**kwargs))
    db.commit()
    return db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).one()


class TestConfidenceBaseline:
    def test_shared_constant_sits_below_intern_floor(self):
        from core.models import NEW_AGENT_CONFIDENCE

        assert NEW_AGENT_CONFIDENCE < 0.5

    def test_column_default_below_intern_floor(self, db_session):
        """Creation sites that omit confidence_score get the shared
        baseline, not the old boundary-sitting 0.5."""
        agent = _make_agent(db_session)  # no explicit confidence
        assert agent.confidence_score == 0.35
        assert agent.confidence_score < 0.5

    def test_first_success_keeps_new_agent_student(self, db_session):
        """The incident: a fresh agent's first +0.01 outcome drip promoted
        it to INTERN. From the shared baseline it stays STUDENT."""
        from core.agent_governance_service import AgentGovernanceService
        from core.models import NEW_AGENT_CONFIDENCE

        agent = _make_agent(db_session, confidence=NEW_AGENT_CONFIDENCE)
        svc = AgentGovernanceService(db_session, workspace_id="default")
        svc._update_confidence_score(agent.id, positive=True, impact_level="low")
        db_session.refresh(agent)
        assert agent.confidence_score == pytest.approx(0.36)
        assert agent.status == "student"

    def test_boundary_crossing_is_gated_without_evidence(self, db_session):
        """Crossing 0.50 wants INTERN, but the evidence gate holds STUDENT:
        this agent has no training sessions, episodes, or mentor record —
        score drips alone must not promote (the alignment fix)."""
        from core.agent_governance_service import AgentGovernanceService

        agent = _make_agent(db_session, confidence=0.49)
        svc = AgentGovernanceService(db_session, workspace_id="default")
        svc._update_confidence_score(agent.id, positive=True, impact_level="low")
        db_session.refresh(agent)
        assert agent.confidence_score == pytest.approx(0.50)
        assert agent.status == "student"

    def test_boundary_crossing_promotes_when_evidence_met(self, db_session):
        """Same score crossing, gate satisfied (e.g. the system-agent
        pathway or full training evidence) → the rung is earned."""
        from unittest.mock import patch

        from core.agent_governance_service import AgentGovernanceService

        agent = _make_agent(db_session, confidence=0.49)
        svc = AgentGovernanceService(db_session, workspace_id="default")
        with patch.object(
            AgentGovernanceService, "_promotion_evidence_met", return_value=(True, {})
        ):
            svc._update_confidence_score(agent.id, positive=True, impact_level="low")
        db_session.refresh(agent)
        assert agent.confidence_score == pytest.approx(0.50)
        assert agent.status == "intern"

    def test_higher_rung_also_gated(self, db_session):
        """INTERN at 0.69 crossing 0.70 wants SUPERVISED — held without
        graduation-readiness evidence."""
        from core.agent_governance_service import AgentGovernanceService

        agent = _make_agent(db_session, confidence=0.69, status="intern")
        svc = AgentGovernanceService(db_session, workspace_id="default")
        svc._update_confidence_score(agent.id, positive=True, impact_level="low")
        db_session.refresh(agent)
        assert agent.confidence_score == pytest.approx(0.70)
        assert agent.status == "intern"

    def test_demotion_stays_score_based(self, db_session):
        """Downward moves need no evidence — re-earning the rung re-gates
        it, but losing it is immediate."""
        from core.agent_governance_service import AgentGovernanceService

        agent = _make_agent(db_session, confidence=0.55, status="intern")
        svc = AgentGovernanceService(db_session, workspace_id="default")
        svc._update_confidence_score(agent.id, positive=False, impact_level="high")
        db_session.refresh(agent)
        assert agent.confidence_score == pytest.approx(0.45)
        assert agent.status == "student"

    def test_lifecycle_status_not_resurrected_by_confidence(self, db_session):
        """A paused agent's confidence update must not un-pause it into a
        tier — the old recompute overwrote lifecycle states."""
        from core.agent_governance_service import AgentGovernanceService

        agent = _make_agent(db_session, confidence=0.35, status="paused")
        svc = AgentGovernanceService(db_session, workspace_id="default")
        svc._update_confidence_score(agent.id, positive=True, impact_level="high")
        db_session.refresh(agent)
        assert agent.confidence_score == pytest.approx(0.40)
        assert agent.status == "paused"

    def test_evidence_gate_kill_switch(self, db_session, monkeypatch):
        """ATOM_PROMOTION_EVIDENCE_GATE=0 restores score-only behavior for
        deployments that want it."""
        from core.agent_governance_service import AgentGovernanceService

        monkeypatch.setenv("ATOM_PROMOTION_EVIDENCE_GATE", "0")
        agent = _make_agent(db_session, confidence=0.49)
        svc = AgentGovernanceService(db_session, workspace_id="default")
        svc._update_confidence_score(agent.id, positive=True, impact_level="low")
        db_session.refresh(agent)
        assert agent.status == "intern"

    def test_null_confidence_row_uses_shared_baseline(self, db_session):
        """NULL rows previously fell back to 0.5 — the same boundary bug
        via _update_confidence_score's `or 0.5`."""
        from sqlalchemy import text

        from core.agent_governance_service import AgentGovernanceService

        agent = _make_agent(db_session, confidence=0.35)
        db_session.execute(text("UPDATE agent_registry SET confidence_score = NULL WHERE id='agent-1'"))
        db_session.commit()
        svc = AgentGovernanceService(db_session, workspace_id="default")
        svc._update_confidence_score(agent.id, positive=True, impact_level="low")
        db_session.refresh(agent)
        assert agent.confidence_score == pytest.approx(0.36)
        assert agent.status == "student"

    def test_marketplace_declared_intern_gets_score_in_band(self):
        """Marketplace installs declare status=intern; the creation site
        must set a confidence inside the INTERN band or the first outcome
        drip would demote the install to student."""
        import inspect

        from core import agent_marketplace_service

        src = inspect.getsource(agent_marketplace_service)
        assert 'status="intern"' in src
        assert "confidence_score=0.55" in src


class _Payload:
    """Mirror of the frontend canvas thumbs-up submission."""

    def __init__(self, agent_id="agent-1", feedback_type="thumbs_up", comment=None, summary="Cleaned the draft"):
        self.agent_id = agent_id
        self.run_id = "run-1"
        self.step_index = -1
        self.feedback_type = feedback_type
        self.comment = comment
        self.step_content = {
            "input_summary": summary,
            "canvas_id": "canvas-1",
            "source": "canvas_chat",
        }
        self.execution_id = None
        self.step_number = None


class TestFeedbackIdempotency:
    """The /api/reasoning/feedback duplicate guard: a page refresh clears
    the client thumbs state, and re-clicking the same thumb must not
    append another adjudicated AgentFeedback row."""

    @pytest.fixture()
    def client(self, db_session):
        from api.reasoning_routes import router
        from api.reasoning_routes import get_current_user, get_db
        from core.auth import User  # noqa: F401  (import surface check)

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: db_session
        user = MagicMock()
        user.id = "user-1"
        app.dependency_overrides[get_current_user] = lambda: user
        yield TestClient(app)
        app.dependency_overrides.clear()

    @staticmethod
    def _insert_feedback_row(db, payload: _Payload, user_id="user-1"):
        import json

        from core.models import AgentFeedback

        context = {
            "run_id": payload.run_id,
            "step_index": payload.step_index,
            "feedback_type": payload.feedback_type,
            "step_content": payload.step_content,
        }
        db.add(AgentFeedback(
            agent_id=payload.agent_id,
            user_id=user_id,
            input_context=json.dumps(context),
            original_output='""',
            user_correction=payload.comment or payload.feedback_type,
            feedback_type=payload.feedback_type,
        ))
        db.commit()

    def test_identical_resubmit_is_a_noop(self, client, db_session):
        payload = _Payload()
        self._insert_feedback_row(db_session, payload)

        with patch("api.reasoning_routes.AgentGovernanceService") as GovMock:
            GovMock.return_value.submit_feedback = AsyncMock()
            res = client.post("/api/reasoning/feedback", json=payload.__dict__)

        assert res.status_code == 200
        body = res.json()
        data = body.get("data") or body
        assert data.get("duplicate") is True
        GovMock.return_value.submit_feedback.assert_not_awaited()
        # Still exactly one row.
        from core.models import AgentFeedback

        assert db_session.query(AgentFeedback).count() == 1

    def test_changed_polarity_still_records(self, client, db_session):
        self._insert_feedback_row(db_session, _Payload(feedback_type="thumbs_up"))

        with patch("api.reasoning_routes.AgentGovernanceService") as GovMock:
            GovMock.return_value.submit_feedback = AsyncMock(
                return_value=MagicMock(id="fb-new")
            )
            res = client.post(
                "/api/reasoning/feedback",
                json=_Payload(feedback_type="thumbs_down").__dict__,
            )

        assert res.status_code == 200
        GovMock.return_value.submit_feedback.assert_awaited_once()
