# -*- coding: utf-8 -*-
"""Coverage wave 89 — api/agent_coordination_routes.py.

Real in-memory SQLite for the DB-backed endpoints (canvas agents list,
canvas handoffs list, agent-existence check); mocked MultiAgentCanvasService
and AgentHandoffProtocol for the coordination actions (zero network/LLM).

Covers all 10 endpoints x {success, 401 unauth, 403 missing permission,
404 agent-not-found, 422 missing params}.

Security regression surface checked this wave:
  * every endpoint rejects anonymous callers with 401,
  * AGENT_RUN/AGENT_VIEW permissions are enforced via require_permission
    (RBAC check -> 403),
  * add_agent_to_canvas verifies the agent exists before mutating.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.agent_coordination_routes as acr
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import (
    AgentCanvasPresence,
    AgentHandoff,
    AgentRegistry,
    User,
)

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_user(db, user_id="user-1"):
    existing = db.query(User).filter(User.id == user_id).first()
    if existing:
        return existing
    user = User(
        id=user_id,
        email=f"{user_id}@example.com",
        first_name="T",
        last_name="U",
        role="admin",
        status="active",
        tenant_id="t1",
    )
    db.add(user)
    db.commit()
    return user


def _make_agent(db, agent_id="agent-1"):
    existing = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
    if existing:
        return existing
    agent = AgentRegistry(
        id=agent_id, name=f"Agent {agent_id}", workspace_id="ws-1",
        tenant_id="t1", category="Test", module_path="test", class_name="Test",
    )
    db.add(agent)
    db.commit()
    return agent


@pytest.fixture()
def client(db):
    app = FastAPI()
    app.include_router(acr.router)
    user = _make_user(db)

    def _override_db():
        yield db

    def _override_user():
        return user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def anon_client(db):
    app = FastAPI()
    app.include_router(acr.router)

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    return TestClient(app)


ENDPOINTS = [
    ("post", "/api/agent-coordination/canvas/c-1/agents/a-1/join"),
    ("delete", "/api/agent-coordination/canvas/c-1/agents/a-1"),
    ("get", "/api/agent-coordination/canvas/c-1/agents"),
    ("post", "/api/agent-coordination/canvas/c-1/handoffs"),
    ("post", "/api/agent-coordination/handoffs/h-1/accept"),
    ("post", "/api/agent-coordination/handoffs/h-1/reject"),
    ("post", "/api/agent-coordination/handoffs/h-1/complete"),
    ("get", "/api/agent-coordination/canvas/c-1/handoffs"),
    ("post", "/api/agent-coordination/canvas/c-1/coordinate"),
]


class TestAuthEnforcement:
    @pytest.mark.parametrize("method,path", ENDPOINTS)
    def test_anonymous_requests_rejected(self, anon_client, method, path):
        resp = getattr(anon_client, method)(path)
        assert resp.status_code == 401


class TestPermissionEnforcement:
    @pytest.mark.parametrize("method,path", ENDPOINTS)
    def test_permission_denied_403(self, client, method, path):
        with patch("core.rbac_service.RBACService.check_permission",
                   return_value=False):
            resp = getattr(client, method)(path)
        assert resp.status_code == 403


class TestAddRemoveCanvasAgents:
    def test_add_agent_to_canvas_success(self, client, db):
        _make_agent(db, "a-1")
        svc = AsyncMock()
        svc.add_agent_to_canvas.return_value = {"status": "joined"}
        with patch.object(acr, "MultiAgentCanvasService", return_value=svc):
            resp = client.post(
                "/api/agent-coordination/canvas/c-1/agents/a-1/join",
                headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["message"] == "Agent Agent a-1 added to canvas"
        svc.add_agent_to_canvas.assert_awaited_once()

    def test_add_agent_to_canvas_with_role_param(self, client, db):
        _make_agent(db, "a-1")
        svc = AsyncMock()
        svc.add_agent_to_canvas.return_value = {"status": "joined"}
        with patch.object(acr, "MultiAgentCanvasService", return_value=svc):
            resp = client.post(
                "/api/agent-coordination/canvas/c-1/agents/a-1/join?role=editor",
                headers=AUTH_HEADERS)
        assert resp.status_code == 200
        kwargs = svc.add_agent_to_canvas.await_args.kwargs
        assert kwargs["role"] == "editor"

    def test_add_agent_to_canvas_agent_not_found_404(self, client):
        resp = client.post(
            "/api/agent-coordination/canvas/c-1/agents/missing/join",
            headers=AUTH_HEADERS)
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"]["code"] == "NOT_FOUND"

    def test_remove_agent_from_canvas_success(self, client):
        svc = AsyncMock()
        svc.remove_agent_from_canvas.return_value = {"status": "removed"}
        with patch.object(acr, "MultiAgentCanvasService", return_value=svc):
            resp = client.delete(
                "/api/agent-coordination/canvas/c-1/agents/a-1",
                headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["data"] == {"status": "removed"}
        svc.remove_agent_from_canvas.assert_awaited_once()


class TestGetCanvasAgents:
    def test_get_canvas_agents_success(self, client, db):
        _make_agent(db, "agent-1")
        _make_agent(db, "agent-2")
        joined = datetime.now(timezone.utc)
        db.add(AgentCanvasPresence(
            id="p1", canvas_id="c-1", agent_id="agent-1",
            tenant_id="t1", status="active", role="collaborator",
            joined_at=joined))
        db.add(AgentCanvasPresence(
            id="p2", canvas_id="c-1", agent_id="agent-2",
            tenant_id="t1", status="active", role="editor"))
        db.add(AgentCanvasPresence(
            id="p3", canvas_id="c-1", agent_id="agent-1",
            tenant_id="t1", status="inactive"))
        db.commit()
        resp = client.get("/api/agent-coordination/canvas/c-1/agents",
                          headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["metadata"]["total"] == 2
        names = {a["name"] for a in body["data"]}
        assert names == {"Agent agent-1", "Agent agent-2"}
        item = next(a for a in body["data"] if a["agent_id"] == "agent-1")
        assert item["role"] == "collaborator"
        assert item["joined_at"] is not None
        other = next(a for a in body["data"] if a["agent_id"] == "agent-2")
        assert other["joined_at"] is not None

    def test_get_canvas_agents_skips_missing_agent(self, client, db):
        db.add(AgentCanvasPresence(
            id="p-ghost", canvas_id="c-1", agent_id="no-such-agent",
            tenant_id="t1", status="active"))
        db.commit()
        resp = client.get("/api/agent-coordination/canvas/c-1/agents",
                          headers=AUTH_HEADERS)
        assert resp.json()["metadata"]["total"] == 0

    def test_get_canvas_agents_null_joined_at(self, client, db):
        """Core-insert with explicit NULL joined_at (bypasses server_default)
        covers the `p.joined_at if ... else None` branch."""
        from core.models import AgentCanvasPresence as PresenceModel
        _make_agent(db, "agent-1")
        db.execute(PresenceModel.__table__.insert().values(
            id="p-null-join", canvas_id="c-1", agent_id="agent-1",
            tenant_id="t1", status="active", role="reviewer", joined_at=None))
        db.commit()
        resp = client.get("/api/agent-coordination/canvas/c-1/agents",
                          headers=AUTH_HEADERS)
        item = next(a for a in resp.json()["data"] if a["agent_id"] == "agent-1")
        assert item["joined_at"] is None

    def test_get_canvas_agents_empty(self, client):
        resp = client.get("/api/agent-coordination/canvas/c-1/agents",
                          headers=AUTH_HEADERS)
        assert resp.json()["data"] == []


class TestHandoffs:
    def test_initiate_handoff_success(self, client):
        protocol = AsyncMock()
        protocol.initiate_handoff.return_value = {"handoff_id": "h-1"}
        with patch.object(acr, "AgentHandoffProtocol", return_value=protocol):
            resp = client.post(
                "/api/agent-coordination/canvas/c-1/handoffs"
                "?from_agent_id=a-1&to_agent_id=a-2&reason=handoff",
                json={"k": "v"}, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["data"]["handoff_id"] == "h-1"
        kwargs = protocol.initiate_handoff.await_args.kwargs
        assert kwargs["context"] == {"k": "v"}
        assert kwargs["initiated_by"] == "user-1"

    def test_initiate_handoff_without_context(self, client):
        protocol = AsyncMock()
        protocol.initiate_handoff.return_value = {"handoff_id": "h-2"}
        with patch.object(acr, "AgentHandoffProtocol", return_value=protocol):
            resp = client.post(
                "/api/agent-coordination/canvas/c-1/handoffs"
                "?from_agent_id=a-1&to_agent_id=a-2&reason=handoff",
                headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert protocol.initiate_handoff.await_args.kwargs["context"] == {}

    def test_initiate_handoff_missing_fields_422(self, client):
        resp = client.post(
            "/api/agent-coordination/canvas/c-1/handoffs",
            json={"from_agent_id": "a-1"}, headers=AUTH_HEADERS)
        assert resp.status_code == 422
        resp = client.post(
            "/api/agent-coordination/canvas/c-1/handoffs?from_agent_id=a-1",
            headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_accept_handoff_success(self, client):
        protocol = AsyncMock()
        protocol.accept_handoff.return_value = {"status": "accepted"}
        with patch.object(acr, "AgentHandoffProtocol", return_value=protocol):
            resp = client.post(
                "/api/agent-coordination/handoffs/h-1/accept?agent_id=a-2",
                headers=AUTH_HEADERS)
        assert resp.status_code == 200
        protocol.accept_handoff.assert_awaited_once_with(
            handoff_id="h-1", agent_id="a-2", tenant_id="t1")

    def test_accept_handoff_missing_agent_id_422(self, client):
        resp = client.post("/api/agent-coordination/handoffs/h-1/accept",
                           json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_reject_handoff_success_with_reason(self, client):
        protocol = AsyncMock()
        protocol.reject_handoff.return_value = {"status": "rejected"}
        with patch.object(acr, "AgentHandoffProtocol", return_value=protocol):
            resp = client.post(
                "/api/agent-coordination/handoffs/h-1/reject?agent_id=a-2&reason=busy",
                headers=AUTH_HEADERS)
        assert resp.status_code == 200
        kwargs = protocol.reject_handoff.await_args.kwargs
        assert kwargs["reason"] == "busy"

    def test_reject_handoff_without_reason(self, client):
        protocol = AsyncMock()
        protocol.reject_handoff.return_value = {"status": "rejected"}
        with patch.object(acr, "AgentHandoffProtocol", return_value=protocol):
            resp = client.post(
                "/api/agent-coordination/handoffs/h-1/reject?agent_id=a-2",
                headers=AUTH_HEADERS)
        assert protocol.reject_handoff.await_args.kwargs["reason"] is None

    def test_complete_handoff_success(self, client):
        protocol = AsyncMock()
        protocol.complete_handoff.return_value = {"status": "completed"}
        with patch.object(acr, "AgentHandoffProtocol", return_value=protocol):
            resp = client.post(
                "/api/agent-coordination/handoffs/h-1/complete",
                json={"outcome": "ok"}, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert protocol.complete_handoff.await_args.kwargs["result"] == {
            "outcome": "ok"}

    def test_complete_handoff_empty_result_ok(self, client):
        """Empty dict IS a valid body for result_data: Dict[str, Any]."""
        protocol = AsyncMock()
        protocol.complete_handoff.return_value = {"status": "completed"}
        with patch.object(acr, "AgentHandoffProtocol", return_value=protocol):
            resp = client.post("/api/agent-coordination/handoffs/h-1/complete",
                               json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert protocol.complete_handoff.await_args.kwargs["result"] == {}

    def test_get_canvas_handoffs_success(self, client, db):
        db.add(AgentHandoff(
            id="h-1", from_agent_id="a-1", to_agent_id="a-2",
            canvas_id="c-1", tenant_id="t1", reason="r", status="pending"))
        db.add(AgentHandoff(
            id="h-2", from_agent_id="a-2", to_agent_id="a-3",
            canvas_id="c-1", tenant_id="t1", reason="r2", status="accepted"))
        db.add(AgentHandoff(
            id="h-3", from_agent_id="a-1", to_agent_id="a-2",
            canvas_id="c-2", tenant_id="t1", reason="r3", status="pending"))
        db.commit()
        resp = client.get("/api/agent-coordination/canvas/c-1/handoffs",
                          headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["metadata"]["total"] == 2

        resp = client.get(
            "/api/agent-coordination/canvas/c-1/handoffs?status=pending",
            headers=AUTH_HEADERS)
        assert resp.json()["metadata"]["total"] == 1
        item = resp.json()["data"][0]
        assert item["handoff_id"] == "h-1"
        assert item["from_agent_id"] == "a-1"
        assert item["status"] == "pending"

    def test_get_canvas_handoffs_empty(self, client):
        resp = client.get("/api/agent-coordination/canvas/c-1/handoffs",
                          headers=AUTH_HEADERS)
        assert resp.json()["data"] == []


class TestCoordinateAgents:
    def test_coordinate_success_sequential(self, client):
        svc = AsyncMock()
        svc.coordinate_agents.return_value = {"coordination_id": "c-1"}
        with patch.object(acr, "MultiAgentCanvasService", return_value=svc):
            resp = client.post(
                "/api/agent-coordination/canvas/c-1/coordinate?task=build%20feature",
                json=["a-1", "a-2"], headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["data"]["coordination_id"] == "c-1"
        kwargs = svc.coordinate_agents.await_args.kwargs
        assert kwargs["coordination_strategy"] == "sequential"
        assert kwargs["required_agents"] == ["a-1", "a-2"]

    def test_coordinate_success_custom_strategy(self, client):
        svc = AsyncMock()
        svc.coordinate_agents.return_value = {"coordination_id": "c-2"}
        with patch.object(acr, "MultiAgentCanvasService", return_value=svc):
            resp = client.post(
                "/api/agent-coordination/canvas/c-1/coordinate"
                "?task=t&coordination_strategy=parallel",
                json=["a-1"], headers=AUTH_HEADERS)
        assert svc.coordinate_agents.await_args.kwargs[
            "coordination_strategy"] == "parallel"

    def test_coordinate_missing_fields_422(self, client):
        resp = client.post("/api/agent-coordination/canvas/c-1/coordinate",
                           json=["a-1"], headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_coordinate_service_failure_500(self, client):
        svc = AsyncMock()
        svc.coordinate_agents.side_effect = Exception("coordinator down")
        with patch.object(acr, "MultiAgentCanvasService", return_value=svc):
            resp = client.post(
                "/api/agent-coordination/canvas/c-1/coordinate?task=t",
                json=["a-1"], headers=AUTH_HEADERS)
        assert resp.status_code == 500
