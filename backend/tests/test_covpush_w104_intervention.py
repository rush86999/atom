# -*- coding: utf-8 -*-
"""Coverage wave 104 — core/intervention_service.py.

HITL intervention lifecycle against an in-memory SQLite DB:
- request_intervention: success (PAUSED + requires_approval), persistence
  failure -> ERROR envelope.
- get_pending_interventions: pending-only filter, workspace filtering
  (specific + "default" no-filter), agent-name resolution (found / missing
  agent / missing agent_id -> "Unknown Agent").
- approve_intervention: missing action, non-pending action, success
  (status/reviewed_by/reviewed_at persisted).
- reject_intervention: missing action, success (user_feedback persisted).

No LLM spend, no network; get_db_session is patched to a real session.
"""
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.intervention_service import InterventionService, intervention_service
from core.models import AgentRegistry, HITLAction, HITLActionStatus  # noqa: F401


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture()
def svc(db_session, monkeypatch):
    from contextlib import contextmanager

    @contextmanager
    def _session():
        yield db_session

    monkeypatch.setattr(
        "core.intervention_service.get_db_session", _session
    )
    return InterventionService()


@pytest.fixture()
def agent(db_session):
    a = AgentRegistry(
        id="agent-1",
        name="Research Agent",
        category="general",
        module_path="core.agents.queen_agent",
        class_name="QueenAgent",
    )
    db_session.add(a)
    db_session.commit()
    return a


def _request(svc, **kw):
    import asyncio

    params = {
        "workspace_id": "ws-1",
        "action_type": "send_message",
        "platform": "whatsapp",
        "params": {"to": "user-9", "text": "hello"},
        "reason": "Needs human review",
    }
    params.update(kw)
    return asyncio.run(svc.request_intervention(**params))


class TestRequestIntervention:
    def test_success(self, svc, db_session):
        result = _request(svc, agent_id="agent-1", user_id="u1")
        assert result["status"] == "PAUSED"
        assert result["requires_approval"] is True
        assert result["message"].startswith("Action paused for human review")
        row = db_session.query(HITLAction).first()
        assert row.id == result["action_id"]
        assert row.status == HITLActionStatus.PENDING.value
        assert row.workspace_id == "ws-1"
        assert row.agent_id == "agent-1"
        assert row.user_id == "u1"
        assert row.action_type == "send_message"
        assert row.platform == "whatsapp"
        assert row.params == {"to": "user-9", "text": "hello"}
        assert row.reason == "Needs human review"

    def test_without_agent(self, svc):
        result = _request(svc)
        assert result["action_id"] is not None
        assert result["status"] == "PAUSED"

    def test_persist_failure_returns_error(self, svc, monkeypatch):
        def _boom(**kwargs):
            raise RuntimeError("disk full")

        monkeypatch.setattr(
            "core.intervention_service.HITLAction", _boom
        )
        result = _request(svc)
        assert result["status"] == "ERROR"
        assert "Failed to persist intervention request" in result["message"]
        assert "disk full" in result["message"]


class TestGetPendingInterventions:
    def test_all_pending(self, svc):
        _request(svc)
        _request(svc, workspace_id="ws-2", action_type="other")
        results = svc.get_pending_interventions()
        assert len(results) == 2

    def test_workspace_filter(self, svc):
        _request(svc)
        _request(svc, workspace_id="ws-2")
        results = svc.get_pending_interventions(workspace_id="ws-1")
        assert len(results) == 1
        assert results[0]["action_type"] == "send_message"

    def test_default_workspace_no_filter(self, svc):
        _request(svc, workspace_id="ws-1")
        _request(svc, workspace_id="ws-2")
        assert len(svc.get_pending_interventions(workspace_id="default")) == 2

    def test_serialized_shape(self, svc, db_session):
        _request(svc, agent_id="agent-1", user_id="u1")
        results = svc.get_pending_interventions()
        row = results[0]
        assert row["agent_id"] == "agent-1"
        assert row["user_id"] == "u1"
        assert row["platform"] == "whatsapp"
        assert row["reason"] == "Needs human review"
        assert row["status"] == "pending"
        assert isinstance(row["created_at"], str)
        assert datetime.fromisoformat(row["created_at"]) is not None

    def test_agent_name_resolved(self, svc, agent):
        _request(svc, agent_id="agent-1")
        assert svc.get_pending_interventions()[0]["agent_name"] == "Research Agent"

    def test_unknown_agent_name(self, svc):
        _request(svc, agent_id="ghost-agent")
        assert svc.get_pending_interventions()[0]["agent_name"] == "Unknown Agent"

    def test_no_agent_name(self, svc):
        _request(svc)
        assert svc.get_pending_interventions()[0]["agent_name"] == "Unknown Agent"

    def test_empty(self, svc):
        assert svc.get_pending_interventions() == []


class TestApproveIntervention:
    def test_missing_action(self, svc):
        result = _approve(svc, "nope", "approver-1")
        assert result == {"success": False, "message": "Action not found"}

    def test_non_pending_action(self, svc, db_session):
        action = _make_action(db_session, status=HITLActionStatus.APPROVED.value)
        result = _approve(svc, action.id, "approver-1")
        assert result["success"] is False
        assert "cannot approve" in result["message"]

    def test_success(self, svc, db_session):
        action = _make_action(db_session)
        result = _approve(svc, action.id, "approver-1")
        assert result["success"] is True
        assert result["action_id"] == action.id
        db_session.expire_all()
        fresh = db_session.query(HITLAction).filter(HITLAction.id == action.id).first()
        assert fresh.status == HITLActionStatus.APPROVED.value
        assert fresh.reviewed_by == "approver-1"
        assert fresh.reviewed_at is not None


class TestRejectIntervention:
    def test_missing_action(self, svc):
        import asyncio

        result = asyncio.run(
            svc.reject_intervention("nope", "approver-1", "bad idea")
        )
        assert result == {"success": False, "message": "Action not found"}

    def test_success(self, svc, db_session):
        action = _make_action(db_session)
        import asyncio

        result = asyncio.run(
            svc.reject_intervention(action.id, "approver-1", "out of scope")
        )
        assert result["success"] is True
        db_session.expire_all()
        fresh = db_session.query(HITLAction).filter(HITLAction.id == action.id).first()
        assert fresh.status == HITLActionStatus.REJECTED.value
        assert fresh.reviewed_by == "approver-1"
        assert fresh.user_feedback == "out of scope"


class TestSingleton:
    def test_module_singleton(self):
        assert isinstance(intervention_service, InterventionService)


def _approve(svc, action_id, approver_id):
    import asyncio

    return asyncio.run(svc.approve_intervention(action_id, approver_id))


def _make_action(db_session, status=HITLActionStatus.PENDING.value):
    action = HITLAction(
        workspace_id="ws-1",
        agent_id="agent-1",
        action_type="send_message",
        platform="slack",
        params={"text": "hi"},
        reason="review me",
        status=status,
    )
    db_session.add(action)
    db_session.commit()
    return action
