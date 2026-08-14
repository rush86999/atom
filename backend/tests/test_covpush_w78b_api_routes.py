# -*- coding: utf-8 -*-
"""Coverage wave 78b — 7 API route modules (each >=95% standalone).

Targets:
- api/agent_coordination_routes.py  (canvas agent join/remove/list, handoffs,
                                     multi-agent coordinate)
- api/agent_guidance_routes.py      (operation tracking, view orchestration,
                                     error guidance, agent requests)
- api/board_routes.py               (Kanban board/column/task CRUD, rebalance,
                                     task-canvas redirect)
- api/dashboard_routes.py           (aggregate dashboard feed + fail-open helpers)
- api/dashboard_data_routes.py      (data/stats/events/tasks/messages/health)
- api/dynamic_options_routes.py     (Node-engine dynamic options + fallback)
- api/evolution_routes.py           (GEA evolution run + traces)

No LLM, no network, no real DB: FastAPI TestClient + dependency_overrides +
service/mock patches on REAL module names (no `backend.` prefix). DB-backed
endpoints use hermetic in-memory SQLite (StaticPool), never the worker DB.
"""
from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.auth import get_current_user as core_get_current_user
from core.database import Base, get_db


# ============================================================================
# Shared helpers
# ============================================================================

class FakeUser:
    id = "u-1"
    tenant_id = "t1"
    workspace_id = "ws-1"
    role = "admin"
    status = "active"
    email = "user@test.com"


def _auth_app(router, user=None, db=None, prefix=""):
    """Hermetic app with auth (+ optional db) overridden."""
    app = FastAPI()
    app.include_router(router, prefix=prefix)
    if user is not None:
        app.dependency_overrides[core_get_current_user] = lambda: user
    if db is not None:
        app.dependency_overrides[get_db] = lambda: db
    return app


def _auth_client(router, user=None, db=None, raise_exc=False, prefix=""):
    return TestClient(
        _auth_app(router, user=user or FakeUser(), db=db, prefix=prefix),
        raise_server_exceptions=raise_exc,
    )


def _anon_client(router, db=None, prefix=""):
    app = FastAPI()
    app.include_router(router, prefix=prefix)
    if db is not None:
        app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@contextlib.contextmanager
def _yield_session(session):
    yield session


@pytest.fixture
def db():
    """Hermetic in-memory SQLite (never touches worker/real DB)."""
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


def _chained(all_result=None, first_result=None):
    """Query mock where every chained call returns itself and `.all()`/`.first()` land."""
    q = MagicMock()
    q.filter.return_value = q
    q.outerjoin.return_value = q
    q.order_by.return_value = q
    q.limit.return_value = q
    if all_result is not None:
        q.all.return_value = all_result
    q.first.return_value = first_result
    return q


# ============================================================================
# api/agent_coordination_routes.py
# ============================================================================

class TestAgentCoordinationRoutes:
    """Coverage: api/agent_coordination_routes.py"""

    MOD = "api.agent_coordination_routes"

    def _make_user(self, db, user_id="user-1"):
        from core.models import User
        existing = db.query(User).filter(User.id == user_id).first()
        if existing:
            return existing
        user = User(
            id=user_id, email=f"{user_id}@example.com",
            first_name="T", last_name="U", role="admin",
            status="active", tenant_id="t1",
        )
        db.add(user)
        db.commit()
        return user

    def _make_agent(self, db, agent_id="agent-1"):
        from core.models import AgentRegistry
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

    @pytest.fixture
    def client(self, db):
        user = self._make_user(db)
        return _auth_client(
            self._router(),
            user=user,
            db=db,
            raise_exc=False,
        )

    @pytest.fixture
    def anon(self, db):
        return _anon_client(self._router(), db=db)

    @staticmethod
    def _router():
        import importlib
        return importlib.import_module("api.agent_coordination_routes").router

    def _deny_rbac(self):
        return patch("core.rbac_service.RBACService.check_permission", return_value=False)

    # -- auth --------------------------------------------------------------

    def test_all_endpoints_require_auth(self, anon):
        checks = [
            ("post", "/api/agent-coordination/canvas/c-1/agents/a-1/join"),
            ("delete", "/api/agent-coordination/canvas/c-1/agents/a-1"),
            ("get", "/api/agent-coordination/canvas/c-1/agents"),
            ("post", "/api/agent-coordination/canvas/c-1/handoffs?from_agent_id=a-1&to_agent_id=a-2&reason=r"),
            ("post", "/api/agent-coordination/handoffs/h-1/accept?agent_id=a-1"),
            ("post", "/api/agent-coordination/handoffs/h-1/reject?agent_id=a-1"),
            ("post", "/api/agent-coordination/handoffs/h-1/complete"),
            ("get", "/api/agent-coordination/canvas/c-1/handoffs"),
            ("post", "/api/agent-coordination/canvas/c-1/coordinate?task=t"),
        ]
        for method, path in checks:
            resp = getattr(anon, method)(path)
            assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}"

    def test_all_endpoints_enforce_rbac(self, client):
        with self._deny_rbac():
            assert client.post(
                "/api/agent-coordination/canvas/c-1/agents/a-1/join"
            ).status_code == 403
            assert client.delete(
                "/api/agent-coordination/canvas/c-1/agents/a-1"
            ).status_code == 403
            assert client.get(
                "/api/agent-coordination/canvas/c-1/agents"
            ).status_code == 403
            assert client.post(
                "/api/agent-coordination/canvas/c-1/handoffs",
                params={"from_agent_id": "a-1", "to_agent_id": "a-2", "reason": "r"},
            ).status_code == 403
            assert client.post(
                "/api/agent-coordination/handoffs/h-1/accept",
                params={"agent_id": "a-1"},
            ).status_code == 403
            assert client.post(
                "/api/agent-coordination/handoffs/h-1/reject",
                params={"agent_id": "a-1"},
            ).status_code == 403
            assert client.post(
                "/api/agent-coordination/handoffs/h-1/complete",
                json={"status": "done"},
            ).status_code == 403
            assert client.get(
                "/api/agent-coordination/canvas/c-1/handoffs"
            ).status_code == 403
            assert client.post(
                "/api/agent-coordination/canvas/c-1/coordinate",
                params={"task": "t"},
                json=["a-1"],
            ).status_code == 403

    def test_join_missing_agent_404(self, client, db):
        resp = client.post("/api/agent-coordination/canvas/c-1/agents/ghost/join")
        assert resp.status_code == 404
        assert "Agent" in resp.json()["detail"]["error"]["message"]

    def test_join_success_default_role(self, client, db):
        self._make_agent(db)
        with patch(f"{self.MOD}.MultiAgentCanvasService") as svc_cls:
            svc = svc_cls.return_value
            svc.add_agent_to_canvas = AsyncMock(return_value={"added": True})
            resp = client.post("/api/agent-coordination/canvas/c-1/agents/agent-1/join")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["data"] == {"added": True}
        svc.add_agent_to_canvas.assert_awaited_once_with(
            agent_id="agent-1", canvas_id="c-1",
            tenant_id="t1", role="collaborator",
        )

    def test_join_success_explicit_role(self, client, db):
        self._make_agent(db)
        with patch(f"{self.MOD}.MultiAgentCanvasService") as svc_cls:
            svc = svc_cls.return_value
            svc.add_agent_to_canvas = AsyncMock(return_value={})
            resp = client.post(
                "/api/agent-coordination/canvas/c-1/agents/agent-1/join?role=reviewer"
            )
        assert resp.status_code == 200
        assert "added to canvas" in resp.json()["message"]
        svc.add_agent_to_canvas.assert_awaited_once_with(
            agent_id="agent-1", canvas_id="c-1",
            tenant_id="t1", role="reviewer",
        )

    def test_join_service_exception_500(self, client, db):
        self._make_agent(db)
        with patch(f"{self.MOD}.MultiAgentCanvasService") as svc_cls:
            svc_cls.return_value.add_agent_to_canvas = AsyncMock(
                side_effect=RuntimeError("boom")
            )
            resp = client.post("/api/agent-coordination/canvas/c-1/agents/agent-1/join")
        assert resp.status_code == 500

    def test_remove_success(self, client):
        with patch(f"{self.MOD}.MultiAgentCanvasService") as svc_cls:
            svc = svc_cls.return_value
            svc.remove_agent_from_canvas = AsyncMock(return_value={"removed": True})
            resp = client.delete("/api/agent-coordination/canvas/c-1/agents/a-1")
        assert resp.status_code == 200
        assert resp.json()["data"] == {"removed": True}
        svc.remove_agent_from_canvas.assert_awaited_once_with(
            agent_id="a-1", canvas_id="c-1", tenant_id="t1",
        )

    def test_remove_service_exception_500(self, client):
        with patch(f"{self.MOD}.MultiAgentCanvasService") as svc_cls:
            svc_cls.return_value.remove_agent_from_canvas = AsyncMock(
                side_effect=RuntimeError("boom")
            )
            resp = client.delete("/api/agent-coordination/canvas/c-1/agents/a-1")
        assert resp.status_code == 500

    def test_canvas_agents_empty(self, client):
        resp = client.get("/api/agent-coordination/canvas/c-1/agents")
        assert resp.status_code == 200
        assert resp.json()["data"] == []
        assert resp.json()["metadata"]["total"] == 0

    def test_canvas_agents_with_presence_and_joined_at(self, client, db):
        from core.models import AgentCanvasPresence
        self._make_agent(db, "agent-1")
        self._make_agent(db, "agent-2")
        db.add(AgentCanvasPresence(
            id="p1", canvas_id="c-1", agent_id="agent-1", tenant_id="t1",
            status="active", role="collaborator",
            joined_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        ))
        db.add(AgentCanvasPresence(
            id="p2", canvas_id="c-1", agent_id="agent-2", tenant_id="t1",
            status="active", role="reviewer",
        ))
        db.add(AgentCanvasPresence(
            id="p3", canvas_id="c-1", agent_id="ghost-agent", tenant_id="t1",
            status="active", role="observer", joined_at=None,
        ))
        db.add(AgentCanvasPresence(
            id="p4", canvas_id="c-1", agent_id="agent-1", tenant_id="t1",
            status="left", role="collaborator",
        ))
        db.commit()
        p2 = db.query(AgentCanvasPresence).filter(AgentCanvasPresence.id == "p2").first()
        p2.joined_at = None
        db.commit()
        resp = client.get("/api/agent-coordination/canvas/c-1/agents")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        assert data[0]["agent_id"] == "agent-1"
        assert data[0]["joined_at"] is not None
        assert data[1]["joined_at"] is None

    def test_canvas_agents_wrong_tenant_excluded(self, client, db):
        from core.models import AgentCanvasPresence
        self._make_agent(db, "agent-1")
        db.add(AgentCanvasPresence(
            id="p1", canvas_id="c-1", agent_id="agent-1", tenant_id="other",
            status="active", role="collaborator", joined_at=None,
        ))
        db.commit()
        resp = client.get("/api/agent-coordination/canvas/c-1/agents")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_handoff_initiate_success_with_context(self, client):
        with patch(f"{self.MOD}.AgentHandoffProtocol") as proto_cls:
            proto = proto_cls.return_value
            proto.initiate_handoff = AsyncMock(return_value={"handoff_id": "h-1"})
            resp = client.post(
                "/api/agent-coordination/canvas/c-1/handoffs",
                params={"from_agent_id": "a-1", "to_agent_id": "a-2", "reason": "handoff"},
                json={"k": "v"},
            )
        assert resp.status_code == 200
        assert resp.json()["data"] == {"handoff_id": "h-1"}
        proto.initiate_handoff.assert_awaited_once_with(
            from_agent_id="a-1", to_agent_id="a-2", canvas_id="c-1",
            tenant_id="t1", context={"k": "v"}, reason="handoff",
            initiated_by="user-1",
        )

    def test_handoff_initiate_context_none_defaults_empty(self, client):
        with patch(f"{self.MOD}.AgentHandoffProtocol") as proto_cls:
            proto = proto_cls.return_value
            proto.initiate_handoff = AsyncMock(return_value={})
            resp = client.post(
                "/api/agent-coordination/canvas/c-1/handoffs",
                params={
                    "from_agent_id": "a-1", "to_agent_id": "a-2",
                    "reason": "handoff",
                },
            )
        assert resp.status_code == 200
        proto.initiate_handoff.assert_awaited_once_with(
            from_agent_id="a-1", to_agent_id="a-2", canvas_id="c-1",
            tenant_id="t1", context={}, reason="handoff", initiated_by="user-1",
        )

    def test_handoff_initiate_missing_reason_422(self, client):
        resp = client.post(
            "/api/agent-coordination/canvas/c-1/handoffs",
            params={"from_agent_id": "a-1", "to_agent_id": "a-2"},
        )
        assert resp.status_code == 422

    def test_handoff_initiate_service_exception_500(self, client):
        with patch(f"{self.MOD}.AgentHandoffProtocol") as proto_cls:
            proto_cls.return_value.initiate_handoff = AsyncMock(
                side_effect=RuntimeError("boom")
            )
            resp = client.post(
                "/api/agent-coordination/canvas/c-1/handoffs",
                params={
                    "from_agent_id": "a-1", "to_agent_id": "a-2", "reason": "r",
                },
            )
        assert resp.status_code == 500

    def test_handoff_accept_success(self, client):
        with patch(f"{self.MOD}.AgentHandoffProtocol") as proto_cls:
            proto = proto_cls.return_value
            proto.accept_handoff = AsyncMock(return_value={"accepted": True})
            resp = client.post(
                "/api/agent-coordination/handoffs/h-1/accept",
                params={"agent_id": "a-1"},
            )
        assert resp.status_code == 200
        proto.accept_handoff.assert_awaited_once_with(
            handoff_id="h-1", agent_id="a-1", tenant_id="t1",
        )

    def test_handoff_accept_service_exception_500(self, client):
        with patch(f"{self.MOD}.AgentHandoffProtocol") as proto_cls:
            proto_cls.return_value.accept_handoff = AsyncMock(
                side_effect=RuntimeError("boom")
            )
            resp = client.post(
                "/api/agent-coordination/handoffs/h-1/accept",
                params={"agent_id": "a-1"},
            )
        assert resp.status_code == 500

    def test_handoff_reject_success_with_reason(self, client):
        with patch(f"{self.MOD}.AgentHandoffProtocol") as proto_cls:
            proto = proto_cls.return_value
            proto.reject_handoff = AsyncMock(return_value={})
            resp = client.post(
                "/api/agent-coordination/handoffs/h-1/reject",
                params={"agent_id": "a-1", "reason": "busy"},
            )
        assert resp.status_code == 200
        proto.reject_handoff.assert_awaited_once_with(
            handoff_id="h-1", agent_id="a-1", tenant_id="t1", reason="busy",
        )

    def test_handoff_reject_reason_none(self, client):
        with patch(f"{self.MOD}.AgentHandoffProtocol") as proto_cls:
            proto = proto_cls.return_value
            proto.reject_handoff = AsyncMock(return_value={})
            resp = client.post(
                "/api/agent-coordination/handoffs/h-1/reject",
                params={"agent_id": "a-1"},
            )
        assert resp.status_code == 200
        proto.reject_handoff.assert_awaited_once_with(
            handoff_id="h-1", agent_id="a-1", tenant_id="t1", reason=None,
        )

    def test_handoff_reject_service_exception_500(self, client):
        with patch(f"{self.MOD}.AgentHandoffProtocol") as proto_cls:
            proto_cls.return_value.reject_handoff = AsyncMock(
                side_effect=RuntimeError("boom")
            )
            resp = client.post(
                "/api/agent-coordination/handoffs/h-1/reject",
                params={"agent_id": "a-1"},
            )
        assert resp.status_code == 500

    def test_handoff_complete_success(self, client):
        with patch(f"{self.MOD}.AgentHandoffProtocol") as proto_cls:
            proto = proto_cls.return_value
            proto.complete_handoff = AsyncMock(return_value={})
            resp = client.post(
                "/api/agent-coordination/handoffs/h-1/complete",
                json={"result": "ok"},
            )
        assert resp.status_code == 200
        proto.complete_handoff.assert_awaited_once_with(
            handoff_id="h-1", result={"result": "ok"}, tenant_id="t1",
        )

    def test_handoff_complete_missing_body_422(self, client):
        resp = client.post("/api/agent-coordination/handoffs/h-1/complete")
        assert resp.status_code == 422

    def test_handoff_complete_service_exception_500(self, client):
        with patch(f"{self.MOD}.AgentHandoffProtocol") as proto_cls:
            proto_cls.return_value.complete_handoff = AsyncMock(
                side_effect=RuntimeError("boom")
            )
            resp = client.post(
                "/api/agent-coordination/handoffs/h-1/complete",
                json={"result": "ok"},
            )
        assert resp.status_code == 500

    def test_canvas_handoffs_empty(self, client):
        resp = client.get("/api/agent-coordination/canvas/c-1/handoffs")
        assert resp.status_code == 200
        assert resp.json()["data"] == []
        assert resp.json()["metadata"]["total"] == 0

    def test_canvas_handoffs_with_status_filter(self, client, db):
        from core.models import AgentHandoff
        db.add(AgentHandoff(
            id="h-1", canvas_id="c-1", tenant_id="t1",
            from_agent_id="a-1", to_agent_id="a-2", status="pending",
            reason="r1", initiated_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        ))
        db.add(AgentHandoff(
            id="h-2", canvas_id="c-1", tenant_id="t1",
            from_agent_id="a-1", to_agent_id="a-3", status="accepted",
            reason=None,
        ))
        db.add(AgentHandoff(
            id="h-3", canvas_id="c-2", tenant_id="t1",
            from_agent_id="a-1", to_agent_id="a-2", status="pending",
            reason="other-canvas",
        ))
        db.commit()
        h2 = db.query(AgentHandoff).filter(AgentHandoff.id == "h-2").first()
        h2.initiated_at = None
        db.commit()
        resp = client.get("/api/agent-coordination/canvas/c-1/handoffs?status=pending")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["handoff_id"] == "h-1"
        assert data[0]["status"] == "pending"
        assert data[0]["initiated_at"] is not None

    def test_canvas_handoffs_no_filter(self, client, db):
        from core.models import AgentHandoff
        db.add(AgentHandoff(
            id="h-1", canvas_id="c-1", tenant_id="t1",
            from_agent_id="a-1", to_agent_id="a-2", status="pending",
            reason="r",
        ))
        db.commit()
        h1 = db.query(AgentHandoff).filter(AgentHandoff.id == "h-1").first()
        h1.initiated_at = None
        db.commit()
        resp = client.get("/api/agent-coordination/canvas/c-1/handoffs")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1
        assert resp.json()["data"][0]["initiated_at"] is None

    def test_canvas_handoffs_query_exception_500(self, client, db):
        from core.models import AgentHandoff
        real_query = db.query

        def boom(*a, **k):
            raise RuntimeError("db down")
        db.query = boom
        try:
            resp = client.get("/api/agent-coordination/canvas/c-1/handoffs")
        finally:
            db.query = real_query
        assert resp.status_code == 500

    def test_coordinate_success_default_strategy(self, client):
        with patch(f"{self.MOD}.MultiAgentCanvasService") as svc_cls:
            svc = svc_cls.return_value
            svc.coordinate_agents = AsyncMock(return_value={"task_id": "t-1"})
            resp = client.post(
                "/api/agent-coordination/canvas/c-1/coordinate",
                params={"task": "Summarize"},
                json=["a-1", "a-2"],
            )
        assert resp.status_code == 200
        assert resp.json()["data"] == {"task_id": "t-1"}
        svc.coordinate_agents.assert_awaited_once_with(
            canvas_id="c-1", tenant_id="t1", task="Summarize",
            required_agents=["a-1", "a-2"], coordination_strategy="sequential",
        )

    def test_coordinate_success_explicit_strategy(self, client):
        with patch(f"{self.MOD}.MultiAgentCanvasService") as svc_cls:
            svc = svc_cls.return_value
            svc.coordinate_agents = AsyncMock(return_value={})
            resp = client.post(
                "/api/agent-coordination/canvas/c-1/coordinate",
                params={"task": "T", "coordination_strategy": "coordinated"},
                json=["a-1"],
            )
        assert resp.status_code == 200
        svc.coordinate_agents.assert_awaited_once_with(
            canvas_id="c-1", tenant_id="t1", task="T",
            required_agents=["a-1"], coordination_strategy="coordinated",
        )

    def test_coordinate_missing_required_agents_422(self, client):
        resp = client.post(
            "/api/agent-coordination/canvas/c-1/coordinate",
            params={"task": "T"},
        )
        assert resp.status_code == 422

    def test_coordinate_service_exception_500(self, client):
        with patch(f"{self.MOD}.MultiAgentCanvasService") as svc_cls:
            svc_cls.return_value.coordinate_agents = AsyncMock(
                side_effect=RuntimeError("boom")
            )
            resp = client.post(
                "/api/agent-coordination/canvas/c-1/coordinate",
                params={"task": "T"},
                json=["a-1"],
            )
        assert resp.status_code == 500


# ============================================================================
# api/agent_guidance_routes.py
# ============================================================================

class TestAgentGuidanceRoutes:
    """Coverage: api/agent_guidance_routes.py"""

    MOD = "api.agent_guidance_routes"

    @pytest.fixture
    def sys(self):
        """Patch the 4 guidance-system factories with AsyncMocks."""
        guidance = AsyncMock()
        coordinator = AsyncMock()
        error_engine = AsyncMock()
        request_manager = AsyncMock()
        with patch(f"{self.MOD}.get_agent_guidance_system", return_value=guidance), \
             patch(f"{self.MOD}.get_view_coordinator", return_value=coordinator), \
             patch(f"{self.MOD}.get_error_guidance_engine", return_value=error_engine), \
             patch(f"{self.MOD}.get_agent_request_manager", return_value=request_manager):
            yield {
                "guidance": guidance,
                "coordinator": coordinator,
                "error_engine": error_engine,
                "request_manager": request_manager,
            }

    @pytest.fixture
    def client(self):
        from api.agent_guidance_routes import router
        return _auth_client(router, db=MagicMock())

    @pytest.fixture
    def anon(self):
        from api.agent_guidance_routes import router
        return _anon_client(router)

    def _op(self, completed_at=None):
        return SimpleNamespace(
            operation_id="op-1", agent_id="a-1", operation_type="analysis",
            status="running", current_step="step 1", total_steps=5,
            current_step_index=2, progress=40,
            what_explanation="what", why_explanation="why", next_steps="next",
            logs=[{"ts": "t"}], operation_metadata={"m": 1},
            started_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            completed_at=completed_at,
        )

    def _request_log(self, responded_at=None, expires_at=None, revoked=False):
        return SimpleNamespace(
            request_id="req-1", agent_id="a-1", request_type="permission",
            request_data={"perm": "x"}, user_response=None,
            created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            responded_at=responded_at, expires_at=expires_at, revoked=revoked,
        )

    # -- auth --------------------------------------------------------------

    ENDPOINTS = [
        ("post", "/api/agent-guidance/operation/start"),
        ("put", "/api/agent-guidance/operation/op-1/update"),
        ("post", "/api/agent-guidance/operation/op-1/complete"),
        ("get", "/api/agent-guidance/operation/op-1"),
        ("post", "/api/agent-guidance/view/switch"),
        ("post", "/api/agent-guidance/view/layout"),
        ("post", "/api/agent-guidance/error/present"),
        ("post", "/api/agent-guidance/error/track-resolution"),
        ("post", "/api/agent-guidance/request/permission"),
        ("post", "/api/agent-guidance/request/decision"),
        ("post", "/api/agent-guidance/request/req-1/respond"),
        ("get", "/api/agent-guidance/request/req-1"),
    ]

    @pytest.mark.parametrize("method,path", ENDPOINTS)
    def test_anonymous_requests_rejected(self, anon, method, path):
        resp = getattr(anon, method)(path)
        assert resp.status_code == 401

    # -- operation tracking -------------------------------------------------

    def test_start_operation(self, client, sys):
        sys["guidance"].start_operation.return_value = "op-1"
        resp = client.post("/api/agent-guidance/operation/start", json={
            "agent_id": "a-1", "operation_type": "analysis", "context": {"k": "v"},
            "total_steps": 3, "metadata": {"m": 1},
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["operation_id"] == "op-1"
        sys["guidance"].start_operation.assert_awaited_once_with(
            user_id="u-1", agent_id="a-1", operation_type="analysis",
            context={"k": "v"}, total_steps=3, metadata={"m": 1},
        )

    def test_start_operation_optional_fields_none(self, client, sys):
        sys["guidance"].start_operation.return_value = "op-2"
        resp = client.post("/api/agent-guidance/operation/start", json={
            "agent_id": "a-1", "operation_type": "analysis", "context": {},
        })
        assert resp.status_code == 200
        sys["guidance"].start_operation.assert_awaited_once_with(
            user_id="u-1", agent_id="a-1", operation_type="analysis",
            context={}, total_steps=None, metadata=None,
        )

    def test_start_operation_missing_required_422(self, client):
        resp = client.post("/api/agent-guidance/operation/start", json={
            "agent_id": "a-1",
        })
        assert resp.status_code == 422

    def test_start_operation_error_500(self, client, sys):
        sys["guidance"].start_operation.side_effect = RuntimeError("boom")
        resp = client.post("/api/agent-guidance/operation/start", json={
            "agent_id": "a-1", "operation_type": "analysis", "context": {},
        })
        assert resp.status_code == 500

    def test_update_operation_all_fields(self, client, sys):
        resp = client.put("/api/agent-guidance/operation/op-1/update", json={
            "step": "s2", "progress": 50, "add_log": {"ts": "t"},
            "what": "w", "why": "y", "next_steps": "n",
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        sys["guidance"].update_step.assert_awaited_once_with(
            user_id="u-1", operation_id="op-1",
            step="s2", progress=50, add_log={"ts": "t"},
        )
        sys["guidance"].update_context.assert_awaited_once_with(
            user_id="u-1", operation_id="op-1",
            what="w", why="y", next_steps="n",
        )

    def test_update_operation_no_fields_skips_calls(self, client, sys):
        resp = client.put("/api/agent-guidance/operation/op-1/update", json={})
        assert resp.status_code == 200
        sys["guidance"].update_step.assert_not_awaited()
        sys["guidance"].update_context.assert_not_awaited()

    def test_update_operation_step_only(self, client, sys):
        resp = client.put("/api/agent-guidance/operation/op-1/update", json={
            "step": "s3",
        })
        assert resp.status_code == 200
        sys["guidance"].update_step.assert_awaited_once()
        sys["guidance"].update_context.assert_not_awaited()

    def test_update_operation_context_only(self, client, sys):
        resp = client.put("/api/agent-guidance/operation/op-1/update", json={
            "what": "w2",
        })
        assert resp.status_code == 200
        sys["guidance"].update_step.assert_not_awaited()
        sys["guidance"].update_context.assert_awaited_once()

    def test_update_operation_error_500(self, client, sys):
        sys["guidance"].update_step.side_effect = RuntimeError("boom")
        resp = client.put("/api/agent-guidance/operation/op-1/update", json={
            "step": "s2",
        })
        assert resp.status_code == 500

    def test_complete_operation_completed(self, client, sys):
        resp = client.post("/api/agent-guidance/operation/op-1/complete", json={
            "status": "completed", "final_message": "done",
        })
        assert resp.status_code == 200
        sys["guidance"].complete_operation.assert_awaited_once_with(
            user_id="u-1", operation_id="op-1",
            status="completed", final_message="done",
        )

    def test_complete_operation_failed_no_message(self, client, sys):
        resp = client.post("/api/agent-guidance/operation/op-1/complete", json={
            "status": "failed",
        })
        assert resp.status_code == 200
        assert resp.json()["message"] == "Operation failed"
        sys["guidance"].complete_operation.assert_awaited_once_with(
            user_id="u-1", operation_id="op-1",
            status="failed", final_message=None,
        )

    def test_complete_operation_error_500(self, client, sys):
        sys["guidance"].complete_operation.side_effect = RuntimeError("boom")
        resp = client.post("/api/agent-guidance/operation/op-1/complete", json={})
        assert resp.status_code == 500

    def test_get_operation_found(self, client, db):
        from api.agent_guidance_routes import router
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = (
            self._op(completed_at=datetime(2026, 8, 2, tzinfo=timezone.utc))
        )
        client = _auth_client(router, db=mock_db)
        resp = client.get("/api/agent-guidance/operation/op-1")
        assert resp.status_code == 200
        op = resp.json()["data"]["operation"]
        assert op["operation_id"] == "op-1"
        assert op["context"] == {"what": "what", "why": "why", "next": "next"}
        assert op["started_at"] is not None
        assert op["completed_at"] is not None

    def test_get_operation_not_found_404(self, client, db):
        from api.agent_guidance_routes import router
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        client = _auth_client(router, db=mock_db)
        resp = client.get("/api/agent-guidance/operation/op-missing")
        assert resp.status_code == 404

    def test_get_operation_error_500(self, client, db):
        from api.agent_guidance_routes import router
        mock_db = MagicMock()
        mock_db.query.side_effect = RuntimeError("boom")
        client = _auth_client(router, db=mock_db)
        resp = client.get("/api/agent-guidance/operation/op-1")
        assert resp.status_code == 500

    # -- view orchestration -------------------------------------------------

    def test_switch_view_browser(self, client, sys):
        resp = client.post("/api/agent-guidance/view/switch", json={
            "agent_id": "a-1", "view_type": "browser",
            "url": "https://example.com", "guidance": "g", "session_id": "s-1",
        })
        assert resp.status_code == 200
        sys["coordinator"].switch_to_browser_view.assert_awaited_once_with(
            user_id="u-1", agent_id="a-1", url="https://example.com",
            guidance="g", session_id="s-1",
        )

    def test_switch_view_browser_missing_url_422(self, client, sys):
        resp = client.post("/api/agent-guidance/view/switch", json={
            "agent_id": "a-1", "view_type": "browser", "guidance": "g",
        })
        assert resp.status_code == 422
        sys["coordinator"].switch_to_browser_view.assert_not_awaited()

    def test_switch_view_terminal(self, client, sys):
        resp = client.post("/api/agent-guidance/view/switch", json={
            "agent_id": "a-1", "view_type": "terminal",
            "command": "ls -la", "guidance": "g",
        })
        assert resp.status_code == 200
        sys["coordinator"].switch_to_terminal_view.assert_awaited_once_with(
            user_id="u-1", agent_id="a-1", command="ls -la",
            guidance="g", session_id=None,
        )

    def test_switch_view_terminal_missing_command_422(self, client, sys):
        resp = client.post("/api/agent-guidance/view/switch", json={
            "agent_id": "a-1", "view_type": "terminal", "guidance": "g",
        })
        assert resp.status_code == 422
        sys["coordinator"].switch_to_terminal_view.assert_not_awaited()

    def test_switch_view_unknown_type_422(self, client, sys):
        resp = client.post("/api/agent-guidance/view/switch", json={
            "agent_id": "a-1", "view_type": "canvas", "guidance": "g",
        })
        assert resp.status_code == 422
        sys["coordinator"].switch_to_browser_view.assert_not_awaited()
        sys["coordinator"].switch_to_terminal_view.assert_not_awaited()

    def test_switch_view_error_500(self, client, sys):
        sys["coordinator"].switch_to_browser_view.side_effect = RuntimeError("boom")
        resp = client.post("/api/agent-guidance/view/switch", json={
            "agent_id": "a-1", "view_type": "browser",
            "url": "https://example.com", "guidance": "g",
        })
        assert resp.status_code == 500

    def test_set_layout(self, client, sys):
        resp = client.post("/api/agent-guidance/view/layout", json={
            "layout": "split_horizontal", "session_id": "s-1",
        })
        assert resp.status_code == 200
        sys["coordinator"].set_layout.assert_awaited_once_with(
            user_id="u-1", layout="split_horizontal", session_id="s-1",
        )

    def test_set_layout_no_session(self, client, sys):
        resp = client.post("/api/agent-guidance/view/layout", json={"layout": "tabs"})
        assert resp.status_code == 200
        sys["coordinator"].set_layout.assert_awaited_once_with(
            user_id="u-1", layout="tabs", session_id=None,
        )

    def test_set_layout_error_500(self, client, sys):
        sys["coordinator"].set_layout.side_effect = RuntimeError("boom")
        resp = client.post("/api/agent-guidance/view/layout", json={"layout": "grid"})
        assert resp.status_code == 500

    # -- error guidance ------------------------------------------------------

    def test_present_error_with_agent(self, client, sys):
        resp = client.post("/api/agent-guidance/error/present", json={
            "operation_id": "op-1", "error": {"msg": "boom"}, "agent_id": "a-1",
        })
        assert resp.status_code == 200
        sys["error_engine"].present_error.assert_awaited_once_with(
            user_id="u-1", operation_id="op-1",
            error={"msg": "boom"}, agent_id="a-1",
        )

    def test_present_error_no_agent(self, client, sys):
        resp = client.post("/api/agent-guidance/error/present", json={
            "operation_id": "op-1", "error": {"msg": "boom"},
        })
        assert resp.status_code == 200
        sys["error_engine"].present_error.assert_awaited_once_with(
            user_id="u-1", operation_id="op-1",
            error={"msg": "boom"}, agent_id=None,
        )

    def test_present_error_500(self, client, sys):
        sys["error_engine"].present_error.side_effect = RuntimeError("boom")
        resp = client.post("/api/agent-guidance/error/present", json={
            "operation_id": "op-1", "error": {},
        })
        assert resp.status_code == 500

    def test_track_resolution(self, client, sys):
        resp = client.post("/api/agent-guidance/error/track-resolution", json={
            "error_type": "syntax", "error_code": "E001",
            "resolution_attempted": "fix", "success": True,
            "user_feedback": "worked", "agent_suggested": False,
        })
        assert resp.status_code == 200
        sys["error_engine"].track_resolution.assert_awaited_once_with(
            error_type="syntax", error_code="E001",
            resolution_attempted="fix", success=True,
            user_feedback="worked", agent_suggested=False,
        )

    def test_track_resolution_defaults(self, client, sys):
        resp = client.post("/api/agent-guidance/error/track-resolution", json={
            "error_type": "timeout", "resolution_attempted": "retry", "success": False,
        })
        assert resp.status_code == 200
        sys["error_engine"].track_resolution.assert_awaited_once_with(
            error_type="timeout", error_code=None,
            resolution_attempted="retry", success=False,
            user_feedback=None, agent_suggested=True,
        )

    def test_track_resolution_500(self, client, sys):
        sys["error_engine"].track_resolution.side_effect = RuntimeError("boom")
        resp = client.post("/api/agent-guidance/error/track-resolution", json={
            "error_type": "t", "resolution_attempted": "r", "success": True,
        })
        assert resp.status_code == 500

    # -- agent requests -------------------------------------------------------

    def test_create_permission_request(self, client, sys):
        sys["request_manager"].create_permission_request.return_value = "req-1"
        resp = client.post("/api/agent-guidance/request/permission", json={
            "agent_id": "a-1", "title": "Access DB", "permission": "db.read",
            "context": {"table": "users"}, "urgency": "high", "expires_in": 60,
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["request_id"] == "req-1"
        sys["request_manager"].create_permission_request.assert_awaited_once_with(
            user_id="u-1", agent_id="a-1", title="Access DB",
            permission="db.read", context={"table": "users"},
            urgency="high", expires_in=60,
        )

    def test_create_permission_request_defaults(self, client, sys):
        sys["request_manager"].create_permission_request.return_value = "req-2"
        resp = client.post("/api/agent-guidance/request/permission", json={
            "agent_id": "a-1", "title": "T", "permission": "p",
            "context": {}, "urgency": "medium",
        })
        assert resp.status_code == 200
        sys["request_manager"].create_permission_request.assert_awaited_once_with(
            user_id="u-1", agent_id="a-1", title="T",
            permission="p", context={}, urgency="medium", expires_in=None,
        )

    def test_create_permission_request_500(self, client, sys):
        sys["request_manager"].create_permission_request.side_effect = RuntimeError("boom")
        resp = client.post("/api/agent-guidance/request/permission", json={
            "agent_id": "a-1", "title": "T", "permission": "p", "context": {},
        })
        assert resp.status_code == 500

    def test_create_decision_request(self, client, sys):
        sys["request_manager"].create_decision_request.return_value = "req-3"
        resp = client.post("/api/agent-guidance/request/decision", json={
            "agent_id": "a-1", "title": "Choose", "explanation": "e",
            "options": ["a", "b"], "context": {"k": "v"},
            "urgency": "high", "suggested_option": 1, "expires_in": 30,
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["request_id"] == "req-3"
        sys["request_manager"].create_decision_request.assert_awaited_once_with(
            user_id="u-1", agent_id="a-1", title="Choose",
            explanation="e", options=["a", "b"], context={"k": "v"},
            urgency="high", suggested_option=1, expires_in=30,
        )

    def test_create_decision_request_defaults(self, client, sys):
        sys["request_manager"].create_decision_request.return_value = "req-4"
        resp = client.post("/api/agent-guidance/request/decision", json={
            "agent_id": "a-1", "title": "Choose", "explanation": "e",
            "options": [], "context": {},
        })
        assert resp.status_code == 200
        sys["request_manager"].create_decision_request.assert_awaited_once_with(
            user_id="u-1", agent_id="a-1", title="Choose",
            explanation="e", options=[], context={},
            urgency="low", suggested_option=0, expires_in=None,
        )

    def test_create_decision_request_500(self, client, sys):
        sys["request_manager"].create_decision_request.side_effect = RuntimeError("boom")
        resp = client.post("/api/agent-guidance/request/decision", json={
            "agent_id": "a-1", "title": "T", "explanation": "e",
            "options": [], "context": {},
        })
        assert resp.status_code == 500

    def test_respond_to_request(self, client, sys):
        resp = client.post("/api/agent-guidance/request/req-1/respond", json={
            "request_id": "req-1", "response": {"approved": True},
        })
        assert resp.status_code == 200
        sys["request_manager"].handle_response.assert_awaited_once_with(
            user_id="u-1", request_id="req-1", response={"approved": True},
        )

    def test_respond_to_request_500(self, client, sys):
        sys["request_manager"].handle_response.side_effect = RuntimeError("boom")
        resp = client.post("/api/agent-guidance/request/req-1/respond", json={
            "request_id": "req-1", "response": {},
        })
        assert resp.status_code == 500

    def test_get_request_found(self, client):
        from api.agent_guidance_routes import router
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = (
            self._request_log(
                responded_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
                expires_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
                revoked=True,
            )
        )
        client = _auth_client(router, db=mock_db)
        resp = client.get("/api/agent-guidance/request/req-1")
        assert resp.status_code == 200
        req = resp.json()["data"]["request"]
        assert req["request_id"] == "req-1"
        assert req["responded_at"] is not None
        assert req["expires_at"] is not None
        assert req["revoked"] is True

    def test_get_request_found_unanswered(self, client):
        from api.agent_guidance_routes import router
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = (
            self._request_log()
        )
        client = _auth_client(router, db=mock_db)
        resp = client.get("/api/agent-guidance/request/req-1")
        assert resp.status_code == 200
        req = resp.json()["data"]["request"]
        assert req["responded_at"] is None
        assert req["expires_at"] is None
        assert req["revoked"] is False

    def test_get_request_not_found_404(self, client):
        from api.agent_guidance_routes import router
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        client = _auth_client(router, db=mock_db)
        resp = client.get("/api/agent-guidance/request/req-missing")
        assert resp.status_code == 404

    def test_get_request_error_500(self, client):
        from api.agent_guidance_routes import router
        mock_db = MagicMock()
        mock_db.query.side_effect = RuntimeError("boom")
        client = _auth_client(router, db=mock_db)
        resp = client.get("/api/agent-guidance/request/req-1")
        assert resp.status_code == 500


# ============================================================================
# api/board_routes.py
# ============================================================================

class TestBoardRoutes:
    """Coverage: api/board_routes.py — real BoardService + in-memory SQLite."""

    def _make_user(self, db, user_id="user-1"):
        from core.models import User
        existing = db.query(User).filter(User.id == user_id).first()
        if existing:
            return existing
        user = User(
            id=user_id, email=f"{user_id}@example.com",
            first_name="T", last_name="U", role="admin",
            status="active", tenant_id="t1",
        )
        db.add(user)
        db.commit()
        return user

    @pytest.fixture
    def client(self, db):
        from api.board_routes import router
        user = self._make_user(db)
        return _auth_client(router, user=user, db=db, raise_exc=False)

    @pytest.fixture
    def anon(self, db):
        from api.board_routes import router
        return _anon_client(router, db=db)

    @staticmethod
    def _emitter():
        return patch("api.board_routes._emitter", new=AsyncMock())

    # -- auth ---------------------------------------------------------------

    ENDPOINTS = [
        ("post", "/api/boards", {"name": "N", "seed_default_columns": False}),
        ("get", "/api/boards", None),
        ("get", "/api/boards/board-1", None),
        ("post", "/api/boards/board-1/columns", {"name": "C"}),
        ("post", "/api/boards/board-1/tasks", {"title": "T", "column_id": "col-1"}),
        ("get", "/api/boards/board-1/tasks", None),
        ("patch", "/api/boards/board-1/tasks/task-1", {"expected_version": 1}),
        ("delete", "/api/boards/board-1/tasks/task-1", None),
        ("get", "/api/boards/board-1/tasks/task-1/canvas", None),
        ("post", "/api/boards/board-1/rebalance", {"column_id": "col-1"}),
    ]

    @pytest.mark.parametrize("method,path,body", ENDPOINTS)
    def test_anonymous_requests_rejected(self, anon, method, path, body):
        kwargs = {"json": body} if body is not None else {}
        resp = getattr(anon, method)(path, **kwargs)
        assert resp.status_code == 401

    # -- helpers ------------------------------------------------------------

    def test_serialize_task_with_canvas_summary(self, client, db):
        from core.models import AgentCanvasPresence, Artifact, Canvas
        from core.models_board import BoardTask
        board = _board_create(client)
        col = _board_column(client, board["id"])
        canvas = Canvas(
            id="canvas-2", name="WS2", canvas_type="kanban", status="active",
            tenant_id="t1", created_by="user-1",
        )
        db.add(canvas)
        db.add(Artifact(id="art-1", canvas_id="canvas-2", type="doc",
                        tenant_id="t1", workspace_id="ws-1", name="a1", content="c"))
        db.add(AgentCanvasPresence(
            id="pres-1", canvas_id="canvas-2", agent_id="agent-9",
            tenant_id="t1", status="active", role="collaborator"))
        db.add(AgentCanvasPresence(
            id="pres-2", canvas_id="canvas-2", agent_id="agent-8",
            tenant_id="t1", status="inactive", role="collaborator"))
        db.commit()
        task = _board_task(client, board["id"], col["id"], labels=["urgent"], assignee_user_id="user-1")
        obj = db.query(BoardTask).filter(BoardTask.id == task["id"]).first()
        obj.canvas_id = "canvas-2"
        obj.root_task_id = task["id"]
        obj.parent_task_id = task["id"]
        db.commit()
        resp = client.get(f"/api/boards/{board['id']}/tasks")
        body = resp.json()[0]
        summary = body["canvas"]
        assert summary["canvas_id"] == "canvas-2"
        assert summary["name"] == "WS2"
        assert summary["artifact_count"] == 1
        assert summary["presence_count"] == 1
        assert body["assignee_user_id"] == "user-1"
        assert body["parent_task_id"] == task["id"]
        assert body["root_task_id"] == task["id"]
        assert body["labels"] == ["urgent"]

    def test_serialize_task_canvas_row_missing(self, client, db):
        from core.models_board import BoardTask
        board = _board_create(client)
        col = _board_column(client, board["id"])
        task = _board_task(client, board["id"], col["id"])
        obj = db.query(BoardTask).filter(BoardTask.id == task["id"]).first()
        obj.canvas_id = "ghost-canvas"
        db.commit()
        resp = client.get(f"/api/boards/{board['id']}/tasks")
        assert resp.json()[0]["canvas"] is None

    def test_serialize_task_canvas_id_none(self, client):
        board = _board_create(client)
        col = _board_column(client, board["id"])
        task = _board_task(client, board["id"], col["id"])
        assert task["canvas"] is None
        assert task["labels"] == []
        assert task["metadata_json"] == {}
        assert task["assignee_user_id"] is None
        assert task["assignee_agent_id"] is None
        assert task["parent_task_id"] is None
        assert task["root_task_id"] is None
        assert task["created_by_user_id"] == "user-1"

    def test_serialize_task_assignee_agent_and_created_by_null(self, client, db):
        from core.models_board import BoardTask
        board = _board_create(client)
        col = _board_column(client, board["id"])
        task = _board_task(client, board["id"], col["id"], assignee_agent_id="agent-7")
        obj = db.query(BoardTask).filter(BoardTask.id == task["id"]).first()
        obj.created_by_user_id = None
        obj.metadata_json = {"custom": 1}
        db.commit()
        resp = client.get(f"/api/boards/{board['id']}/tasks")
        body = resp.json()[0]
        assert body["assignee_agent_id"] == "agent-7"
        assert body["created_by_user_id"] is None
        assert body["metadata_json"] == {"custom": 1}

    # -- board CRUD ---------------------------------------------------------

    def test_create_board_success(self, client):
        resp = client.post("/api/boards", json={
            "name": "New", "slug": "new-slug", "description": "d",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "New"
        assert body["slug"] == "new-slug"
        assert body["description"] == "d"
        assert body["owner_user_id"] == "user-1"
        assert body["version_id"] == 1

    def test_create_board_no_seed(self, client):
        resp = client.post("/api/boards", json={
            "name": "Empty", "seed_default_columns": False,
        })
        assert resp.status_code == 201
        assert resp.json()["name"] == "Empty"

    def test_create_board_empty_name_422(self, client):
        resp = client.post("/api/boards", json={"name": ""})
        assert resp.status_code == 422

    def test_list_boards_excludes_archived(self, client, db):
        from core.board_service import BoardService
        board = _board_create(client, name="A")
        service = BoardService(db)
        obj = service.get_board(board["id"])
        obj.archived_at = datetime.now(timezone.utc)
        db.commit()
        resp = client.get("/api/boards")
        assert resp.json() == []
        resp = client.get("/api/boards?include_archived=true")
        assert len(resp.json()) == 1
        assert resp.json()[0]["archived_at"] is not None
        assert resp.json()[0]["owner_user_id"] == "user-1"

    def test_get_board_with_columns_and_counts(self, client):
        board = _board_create(client)
        col = _board_column(client, board["id"], "Todo", 0)
        _board_task(client, board["id"], col["id"], "T1")
        resp = client.get(f"/api/boards/{board['id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Board A"
        assert len(body["columns"]) >= 1
        todo = next(c for c in body["columns"] if c["name"] == "Todo")
        assert todo["task_count"] == 1
        assert todo["wip_limit"] is None

    def test_get_board_404(self, client):
        resp = client.get("/api/boards/nonexistent")
        assert resp.status_code == 404

    # -- column CRUD ---------------------------------------------------------

    def test_create_column_success(self, client):
        board = _board_create(client)
        resp = client.post(f"/api/boards/{board['id']}/columns", json={
            "name": "In Progress", "position": 3, "wip_limit": 5,
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "In Progress"
        assert body["position"] == 3
        assert body["wip_limit"] == 5
        assert body["task_count"] == 0

    def test_create_column_missing_board_404(self, client):
        resp = client.post("/api/boards/nope/columns", json={"name": "C"})
        assert resp.status_code == 404

    def test_create_column_empty_name_422(self, client):
        board = _board_create(client)
        resp = client.post(f"/api/boards/{board['id']}/columns", json={"name": ""})
        assert resp.status_code == 422

    # -- task CRUD ------------------------------------------------------------

    def test_create_task_success(self, client):
        board = _board_create(client)
        col = _board_column(client, board["id"])
        with self._emitter() as emitter:
            resp = client.post(f"/api/boards/{board['id']}/tasks", json={
                "title": "First task", "column_id": col["id"],
                "priority": "high", "due_at": "2026-09-01T00:00:00Z",
            })
            emitter.emit_task_created.assert_awaited_once()
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "First task"
        assert body["column_id"] == col["id"]
        assert body["sort_order"] == 0.0
        assert body["priority"] == "high"

    def test_create_task_with_workspace_canvas(self, client):
        board = _board_create(client)
        col = _board_column(client, board["id"])
        resp = client.post(f"/api/boards/{board['id']}/tasks", json={
            "title": "WS task", "column_id": col["id"], "workspace": True,
        })
        assert resp.status_code == 201
        assert resp.json()["canvas"] is not None

    def test_create_task_unknown_status_422(self, client):
        board = _board_create(client)
        col = _board_column(client, board["id"])
        resp = client.post(f"/api/boards/{board['id']}/tasks", json={
            "title": "T", "column_id": col["id"], "status": "bogus",
        })
        assert resp.status_code == 422

    def test_create_task_missing_column_404(self, client):
        board = _board_create(client)
        resp = client.post(f"/api/boards/{board['id']}/tasks", json={
            "title": "T", "column_id": "missing-col",
        })
        assert resp.status_code == 404

    def test_create_task_missing_board_404(self, client):
        resp = client.post("/api/boards/nope/tasks", json={
            "title": "T", "column_id": "col-1",
        })
        assert resp.status_code == 404

    def test_create_task_empty_title_422(self, client):
        board = _board_create(client)
        col = _board_column(client, board["id"])
        resp = client.post(f"/api/boards/{board['id']}/tasks", json={
            "title": "", "column_id": col["id"],
        })
        assert resp.status_code == 422

    def test_list_tasks_with_column_filter(self, client):
        board = _board_create(client)
        col1 = _board_column(client, board["id"], "Todo", 0)
        col2 = _board_column(client, board["id"], "Done", 1)
        _board_task(client, board["id"], col1["id"], "T1")
        _board_task(client, board["id"], col2["id"], "T2")
        resp = client.get(f"/api/boards/{board['id']}/tasks")
        assert len(resp.json()) == 2
        resp = client.get(f"/api/boards/{board['id']}/tasks?column_id={col1['id']}")
        assert len(resp.json()) == 1
        assert resp.json()[0]["title"] == "T1"

    def test_list_tasks_empty(self, client):
        board = _board_create(client)
        resp = client.get(f"/api/boards/{board['id']}/tasks")
        assert resp.json() == []

    def test_patch_task_title_emits_updated(self, client):
        board = _board_create(client)
        col = _board_column(client, board["id"])
        task = _board_task(client, board["id"], col["id"])
        with self._emitter() as emitter:
            resp = client.patch(
                f"/api/boards/{board['id']}/tasks/{task['id']}",
                json={"expected_version": 1, "title": "Renamed"},
            )
            emitter.emit_task_updated.assert_awaited_once()
        assert resp.status_code == 200
        assert resp.json()["title"] == "Renamed"
        assert resp.json()["version_id"] == 2

    def test_patch_task_move_emits_moved(self, client):
        board = _board_create(client)
        col1 = _board_column(client, board["id"], "Todo", 0)
        col2 = _board_column(client, board["id"], "Done", 1)
        task = _board_task(client, board["id"], col1["id"])
        with self._emitter() as emitter:
            resp = client.patch(
                f"/api/boards/{board['id']}/tasks/{task['id']}",
                json={"expected_version": 1, "column_id": col2["id"]},
            )
            emitter.emit_task_moved.assert_awaited_once()
            emitter.emit_task_updated.assert_not_awaited()
        assert resp.json()["column_id"] == col2["id"]

    def test_patch_task_status_transition_emits_transitioned(self, client):
        board = _board_create(client)
        col = _board_column(client, board["id"])
        task = _board_task(client, board["id"], col["id"])
        with self._emitter() as emitter:
            resp = client.patch(
                f"/api/boards/{board['id']}/tasks/{task['id']}",
                json={"expected_version": 1, "status": "todo"},
            )
            emitter.emit_task_transitioned.assert_awaited_once()
            emitter.emit_task_updated.assert_not_awaited()
        assert resp.json()["status"] == "todo"

    def test_patch_task_move_and_transition_no_updated(self, client):
        board = _board_create(client)
        col1 = _board_column(client, board["id"], "Todo", 0)
        col2 = _board_column(client, board["id"], "Done", 1)
        task = _board_task(client, board["id"], col1["id"])
        with self._emitter() as emitter:
            resp = client.patch(
                f"/api/boards/{board['id']}/tasks/{task['id']}",
                json={"expected_version": 1, "column_id": col2["id"],
                      "status": "todo"},
            )
            emitter.emit_task_moved.assert_awaited_once()
            emitter.emit_task_transitioned.assert_awaited_once()
            emitter.emit_task_updated.assert_not_awaited()
        assert resp.status_code == 200

    def test_patch_task_sort_order_only_no_emits(self, client):
        board = _board_create(client)
        col = _board_column(client, board["id"])
        task = _board_task(client, board["id"], col["id"])
        with self._emitter() as emitter:
            resp = client.patch(
                f"/api/boards/{board['id']}/tasks/{task['id']}",
                json={"expected_version": 1, "sort_order": 5.0},
            )
            emitter.emit_task_moved.assert_not_awaited()
            emitter.emit_task_transitioned.assert_not_awaited()
            emitter.emit_task_updated.assert_not_awaited()
        assert resp.json()["sort_order"] == 5.0

    def test_patch_task_stale_version_409(self, client):
        board = _board_create(client)
        col = _board_column(client, board["id"])
        task = _board_task(client, board["id"], col["id"])
        resp = client.patch(
            f"/api/boards/{board['id']}/tasks/{task['id']}",
            json={"expected_version": 99, "title": "X"},
        )
        assert resp.status_code == 409

    def test_patch_task_illegal_transition_422(self, client):
        board = _board_create(client)
        col = _board_column(client, board["id"])
        task = _board_task(client, board["id"], col["id"])
        resp = client.patch(
            f"/api/boards/{board['id']}/tasks/{task['id']}",
            json={"expected_version": 1, "status": "archived"},
        )
        assert resp.status_code == 422

    def test_patch_task_missing_404(self, client):
        board = _board_create(client)
        resp = client.patch(
            f"/api/boards/{board['id']}/tasks/nope",
            json={"expected_version": 1, "title": "X"},
        )
        assert resp.status_code == 404

    def test_patch_task_missing_expected_version_422(self, client):
        board = _board_create(client)
        resp = client.patch(
            f"/api/boards/{board['id']}/tasks/nope",
            json={"title": "X"},
        )
        assert resp.status_code == 422

    def test_delete_task_success_204(self, client):
        board = _board_create(client)
        col = _board_column(client, board["id"])
        task = _board_task(client, board["id"], col["id"])
        with self._emitter() as emitter:
            resp = client.delete(f"/api/boards/{board['id']}/tasks/{task['id']}")
            emitter.emit_task_deleted.assert_awaited_once()
        assert resp.status_code == 204

    def test_delete_task_missing_404(self, client):
        board = _board_create(client)
        resp = client.delete(f"/api/boards/{board['id']}/tasks/nope")
        assert resp.status_code == 404

    # -- task canvas / rebalance ----------------------------------------------

    def test_get_task_canvas_redirect(self, client, db):
        from core.models import Canvas
        from core.models_board import BoardTask
        board = _board_create(client)
        col = _board_column(client, board["id"])
        canvas = Canvas(
            id="canvas-1", name="WS", canvas_type="kanban", status="active",
            tenant_id="t1", created_by="user-1",
        )
        db.add(canvas)
        db.commit()
        task = _board_task(client, board["id"], col["id"])
        obj = db.query(BoardTask).filter(BoardTask.id == task["id"]).first()
        obj.canvas_id = "canvas-1"
        db.commit()
        resp = client.get(
            f"/api/boards/{board['id']}/tasks/{task['id']}/canvas",
            follow_redirects=False,
        )
        assert resp.status_code in (302, 307)
        assert resp.headers["location"] == "/canvas/canvas-1"

    def test_get_task_canvas_404_when_task_missing(self, client):
        board = _board_create(client)
        resp = client.get(f"/api/boards/{board['id']}/tasks/nope/canvas")
        assert resp.status_code == 404

    def test_get_task_canvas_404_when_no_canvas(self, client):
        board = _board_create(client)
        col = _board_column(client, board["id"])
        task = _board_task(client, board["id"], col["id"])
        resp = client.get(f"/api/boards/{board['id']}/tasks/{task['id']}/canvas")
        assert resp.status_code == 404

    def test_rebalance_specific_column(self, client):
        board = _board_create(client)
        col = _board_column(client, board["id"])
        _board_task(client, board["id"], col["id"])
        resp = client.post(
            f"/api/boards/{board['id']}/rebalance", json={"column_id": col["id"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["moved_tasks"] == 0
        assert body["rebalanced_columns"] == [col["id"]]

    def test_rebalance_all_columns(self, client):
        resp = client.post("/api/boards", json={
            "name": "NoSeed", "seed_default_columns": False,
        })
        board = resp.json()
        _board_column(client, board["id"], "Todo", 0)
        _board_column(client, board["id"], "Done", 1)
        resp = client.post(
            f"/api/boards/{board['id']}/rebalance", json={"column_id": None},
        )
        assert resp.status_code == 200
        assert len(resp.json()["rebalanced_columns"]) == 2

    def test_rebalance_missing_board_404(self, client):
        resp = client.post("/api/boards/nope/rebalance", json={"column_id": None})
        assert resp.status_code == 404


def _board_create(client, name="Board A", slug=None):
    resp = client.post("/api/boards", json={
        "name": name, "slug": slug or name.lower().replace(" ", "-"),
    })
    assert resp.status_code == 201
    return resp.json()


def _board_column(client, board_id, name="Todo", position=0):
    resp = client.post(f"/api/boards/{board_id}/columns", json={
        "name": name, "position": position,
    })
    assert resp.status_code == 201
    return resp.json()


def _board_task(client, board_id, column_id, title="Task 1", **extra):
    payload = {"title": title, "column_id": column_id, **extra}
    resp = client.post(f"/api/boards/{board_id}/tasks", json=payload)
    assert resp.status_code == 201
    return resp.json()


# ============================================================================
# api/dashboard_routes.py
# ============================================================================

class TestDashboardRoutes:
    """Coverage: api/dashboard_routes.py — chained-query mocks (fail-open)."""

    @pytest.fixture
    def client(self):
        import api.dashboard_routes as dr
        return _auth_client(dr.router, db=MagicMock())

    @pytest.fixture
    def anon(self):
        import api.dashboard_routes as dr
        return _anon_client(dr.router)

    @staticmethod
    def _agent(name="Bot", status="intern"):
        a = MagicMock()
        a.id = "a1"
        a.name = name
        a.status = status
        a.updated_at = None
        return a

    def test_feed_requires_auth(self, anon):
        assert anon.get("/api/dashboard/feed").status_code == 401

    def test_feed_success_populates_all_sections(self, client, db):
        import api.dashboard_routes as dr
        import core.agent_graduation_service as graduation_mod
        exec_row = MagicMock()
        exec_row.id = "e1"
        exec_row.agent_id = "a1"
        exec_row.status = "completed"
        exec_row.input_summary = "x" * 300
        exec_row.started_at = datetime(2026, 8, 1, 12, 0, 0)
        exec_row.duration_seconds = 3.5

        canvas = MagicMock()
        canvas.id = "c1"
        canvas.canvas_id = "cv-1"
        canvas.action_type = "present"
        canvas.created_at = datetime(2026, 8, 1, 11, 0, 0)

        chat = MagicMock()
        chat.id = "chat-1"
        chat.title = "My session"
        chat.updated_at = datetime(2026, 8, 1, 10, 0, 0)

        def side_effect(model, *a, **k):
            if model is dr.CanvasAudit:
                return _chained(all_result=[canvas])
            if model is dr.ChatSession:
                return _chained(first_result=chat)
            if model is dr.AgentRegistry:
                return _chained(all_result=[self._agent(status="intern")])
            return _chained(all_result=[(exec_row, "Agent Name"), (exec_row, None)])

        mock_db = MagicMock()
        mock_db.query.side_effect = side_effect
        client = _auth_client(dr.router, db=mock_db)
        with patch.object(graduation_mod.AgentGraduationService, "CRITERIA",
                          {"SUPERVISED": {"min_episodes": 25}}, create=True):
            resp = client.get("/api/dashboard/feed")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["recent_executions"]) == 2
        assert data["recent_executions"][0]["agent_name"] == "Agent Name"
        assert data["recent_executions"][1]["agent_name"] == "Unknown"
        assert data["recent_executions"][0]["input_summary"] == "x" * 200
        assert data["recent_executions"][0]["duration_seconds"] == 3.5
        assert len(data["recent_canvases"]) == 1
        assert data["last_chat_session"]["id"] == "chat-1"
        assert data["agents_progress"][0]["next_threshold_episodes"] == 25

    def test_feed_agents_progress_tiers(self, client, db):
        import api.dashboard_routes as dr
        import core.agent_graduation_service as graduation_mod

        def side_effect(model, *a, **k):
            if model is dr.CanvasAudit:
                return _chained(all_result=[])
            if model is dr.ChatSession:
                return _chained(first_result=None)
            if model is dr.AgentRegistry:
                return _chained(all_result=[
                    self._agent(status="bogus"),        # unknown -> student
                    self._agent(name="A2", status="autonomous"),
                    self._agent(name="A3", status="supervised"),
                ])
            return _chained(all_result=[])

        mock_db = MagicMock()
        mock_db.query.side_effect = side_effect
        client = _auth_client(dr.router, db=mock_db)
        with patch.object(graduation_mod.AgentGraduationService, "CRITERIA",
                          {"INTERN": {"min_episodes": 10}}, create=True):
            resp = client.get("/api/dashboard/feed")

        assert resp.status_code == 200
        progress = resp.json()["data"]["agents_progress"]
        assert progress[0]["current_tier"] == "student"
        assert progress[0]["next_tier"] == "intern"
        assert progress[1]["current_tier"] == "autonomous"
        assert progress[1]["next_tier"] is None
        assert progress[1]["next_threshold_episodes"] is None
        assert progress[2]["current_tier"] == "supervised"
        assert progress[2]["next_threshold_episodes"] is None  # not in criteria

    def test_feed_graduation_import_failure_uses_empty_criteria(self, client, db):
        import api.dashboard_routes as dr

        def side_effect(model, *a, **k):
            if model is dr.CanvasAudit:
                return _chained(all_result=[])
            if model is dr.ChatSession:
                return _chained(first_result=None)
            if model is dr.AgentRegistry:
                return _chained(all_result=[self._agent(status="intern")])
            return _chained(all_result=[])

        mock_db = MagicMock()
        mock_db.query.side_effect = side_effect
        client = _auth_client(dr.router, db=mock_db)

        class NoCriteria:
            pass
        with patch("core.agent_graduation_service.AgentGraduationService", NoCriteria):
            resp = client.get("/api/dashboard/feed")

        assert resp.status_code == 200
        progress = resp.json()["data"]["agents_progress"]
        assert progress[0]["next_threshold_episodes"] is None

    def test_feed_last_chat_session_untitled(self, client, db):
        import api.dashboard_routes as dr
        chat = MagicMock()
        chat.id = "chat-2"
        chat.title = None
        chat.updated_at = None

        def side_effect(model, *a, **k):
            if model is dr.CanvasAudit:
                return _chained(all_result=[])
            if model is dr.ChatSession:
                return _chained(first_result=chat)
            if model is dr.AgentRegistry:
                return _chained(all_result=[])
            return _chained(all_result=[])

        mock_db = MagicMock()
        mock_db.query.side_effect = side_effect
        client = _auth_client(dr.router, db=mock_db)
        resp = client.get("/api/dashboard/feed")
        assert resp.status_code == 200
        session = resp.json()["data"]["last_chat_session"]
        assert session["title"] == "Untitled session"
        assert session["updated_at"] is None

    def test_helpers_fail_open_on_exception(self):
        import api.dashboard_routes as dr
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        assert dr._recent_executions(db, "ws-1") == []
        assert dr._recent_canvases(db, "t1") == []
        assert dr._last_chat_session(db, "u-1") is None
        assert dr._agents_progress(db, "ws-1") == []

    def test_recent_executions_serialization_edges(self):
        import api.dashboard_routes as dr
        db = MagicMock()
        row = MagicMock()
        row.id = "e1"
        row.agent_id = "a1"
        row.status = "failed"
        row.input_summary = None
        row.started_at = None
        row.duration_seconds = None
        db.query.return_value = _chained(all_result=[(row, None)])
        out = dr._recent_executions(db, "ws-1", limit=5)
        assert out[0]["agent_name"] == "Unknown"
        assert out[0]["input_summary"] == ""
        assert out[0]["started_at"] is None
        assert out[0]["duration_seconds"] == 0.0

    def test_recent_canvases_created_at_none(self):
        import api.dashboard_routes as dr
        db = MagicMock()
        r = MagicMock()
        r.canvas_id = "cv-1"
        r.action_type = "present"
        r.created_at = None
        db.query.return_value = _chained(all_result=[r])
        out = dr._recent_canvases(db, "t1", limit=3)
        assert out[0]["created_at"] is None

    def test_agents_progress_empty_rows(self):
        import api.dashboard_routes as dr
        db = MagicMock()
        db.query.return_value = _chained(all_result=[])
        assert dr._agents_progress(db, "ws-1") == []


# ============================================================================
# api/dashboard_data_routes.py
# ============================================================================

class TestDashboardDataRoutes:
    """Coverage: api/dashboard_data_routes.py — in-memory SQLite seeds."""

    MOD = "api.dashboard_data_routes"

    @pytest.fixture
    def client(self, db):
        from api.dashboard_data_routes import router
        return _auth_client(router, db=db, raise_exc=False)

    @pytest.fixture
    def anon(self, db):
        from api.dashboard_data_routes import router
        return _anon_client(router, db=db)

    def _seed(self, db, user_id="u-1"):
        import uuid as _uuid
        from core.models import (
            AgentJob, AgentRegistry, AuditLog, ChatProcess, WorkflowExecution, User,
        )
        existing = db.query(User).filter(User.id == user_id).first()
        if not existing:
            user = User(
                id=user_id, email=f"{user_id}@example.com",
                first_name="A", last_name="B", role="user", status="active",
                tenant_id="t1",
            )
            db.add(user)
            db.commit()
        now = datetime(2026, 1, 5, tzinfo=timezone.utc)
        db.add(WorkflowExecution(
            execution_id=f"wf-{_uuid.uuid4().hex[:8]}-1", workflow_id="wf-1",
            status="completed", user_id=user_id, owner_id=user_id,
            created_at=now, updated_at=now, input_data="input",
        ))
        db.add(WorkflowExecution(
            execution_id=f"wf-{_uuid.uuid4().hex[:8]}-2", workflow_id="wf-2",
            status="failed", user_id=user_id,
            created_at=now - timedelta(days=1), input_data=None,
        ))
        db.add(WorkflowExecution(
            execution_id=f"wf-{_uuid.uuid4().hex[:8]}-3", workflow_id="wf-3",
            status="running", user_id=user_id, owner_id=user_id,
            created_at=now - timedelta(days=2), updated_at=None, input_data=None,
        ))
        db.add(AgentJob(
            id=f"job-{_uuid.uuid4().hex[:8]}-1", agent_id="a-1", status="success",
            start_time=now - timedelta(hours=2), end_time=now - timedelta(hours=1),
            result_summary="done", tenant_id="t1",
        ))
        db.add(AgentJob(
            id=f"job-{_uuid.uuid4().hex[:8]}-2", agent_id="a-1", status="running",
            start_time=now - timedelta(hours=3), end_time=None,
            result_summary=None, tenant_id="t1",
        ))
        db.add(AgentJob(
            id=f"job-{_uuid.uuid4().hex[:8]}-3", agent_id="a-1", status="failed",
            start_time=now - timedelta(hours=4), end_time=None,
            result_summary="boom", tenant_id="t1",
        ))
        db.add(AgentJob(
            id=f"job-{_uuid.uuid4().hex[:8]}-4", agent_id="a-1", status="pending",
            start_time=now - timedelta(hours=5), end_time=None,
            result_summary=None, tenant_id="t1",
        ))
        db.add(AuditLog(
            id=f"audit-{_uuid.uuid4().hex[:8]}-1", event_type="login",
            threat_level="low", security_level="low", action="login",
            description="login", user_id=user_id, user_email=f"{user_id}@example.com",
            timestamp=now, tenant_id="t1", success=True,
        ))
        db.add(AuditLog(
            id=f"audit-{_uuid.uuid4().hex[:8]}-2", event_type="alert",
            threat_level="high", security_level="high", action="alert",
            description="alert", user_id=user_id, user_email=f"{user_id}@example.com",
            timestamp=now - timedelta(hours=1), tenant_id="t1", success=True,
        ))
        db.add(AuditLog(
            id=f"audit-{_uuid.uuid4().hex[:8]}-3", event_type="info",
            threat_level="normal", security_level="low", action="info",
            description="info", user_id=None, user_email=None,
            timestamp=now - timedelta(hours=2), tenant_id="t1", success=True,
        ))
        db.add(ChatProcess(
            id=f"chat-{_uuid.uuid4().hex[:8]}", tenant_id="t1", user_id=user_id,
            name="cp", total_steps=2, status="active",
        ))
        db.add(AgentRegistry(
            id=f"reg-{_uuid.uuid4().hex[:8]}", name="Agent", workspace_id="ws-1",
            tenant_id="t1", category="Test", module_path="test", class_name="Test",
        ))
        db.commit()

    # -- auth ---------------------------------------------------------------

    def test_requires_auth(self, anon):
        for path in ("/api/dashboard/data", "/api/dashboard/stats",
                     "/api/dashboard/events", "/api/dashboard/tasks",
                     "/api/dashboard/messages"):
            assert anon.get(path).status_code == 401

    def test_health_public(self, anon):
        resp = anon.get("/api/dashboard/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["service"] == "dashboard-data"
        assert body["timestamp"]

    # -- endpoint success paths ---------------------------------------------

    def test_dashboard_data(self, client, db):
        self._seed(db)
        resp = client.get("/api/dashboard/data")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        events = body["data"]["calendar"]
        assert len(events) == 3
        assert events[0]["status"] == "confirmed"
        assert events[1]["status"] == "tentative"
        assert body["stats"]["upcoming_events"] == 3
        assert body["stats"]["overdue_tasks"] == 1
        assert body["stats"]["unread_messages"] == 3
        assert body["stats"]["completed_tasks"] == 1
        assert body["stats"]["active_workflows"] == 1
        assert body["stats"]["total_agents"] == 1

    def test_dashboard_data_with_limit(self, client, db):
        self._seed(db)
        resp = client.get("/api/dashboard/data?limit=2")
        assert resp.status_code == 200
        assert len(resp.json()["data"]["calendar"]) == 2
        assert len(resp.json()["data"]["tasks"]) == 2

    def test_dashboard_stats(self, client, db):
        self._seed(db)
        resp = client.get("/api/dashboard/stats")
        assert resp.status_code == 200
        stats = resp.json()
        assert stats["upcoming_events"] == 3
        assert stats["overdue_tasks"] == 1
        assert stats["unread_messages"] == 3
        assert stats["active_workflows"] == 1
        assert stats["total_agents"] == 1

    def test_calendar_events(self, client, db):
        self._seed(db)
        resp = client.get("/api/dashboard/events?limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_tasks_endpoint(self, client, db):
        self._seed(db)
        resp = client.get("/api/dashboard/tasks")
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 7  # 3 workflows + 4 jobs
        statuses = {r["status"] for r in rows}
        assert {"completed", "failed", "running", "todo", "in-progress"} <= statuses
        priorities = {r["priority"] for r in rows}
        assert {"high", "low", "medium"} <= priorities

    def test_tasks_endpoint_status_filter(self, client, db):
        self._seed(db)
        resp = client.get("/api/dashboard/tasks?status=completed")
        assert resp.status_code == 200
        rows = resp.json()
        assert rows and all(r["status"] == "completed" for r in rows)

    def test_tasks_endpoint_status_filter_no_match(self, client, db):
        self._seed(db)
        resp = client.get("/api/dashboard/tasks?status=bogus")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_messages_endpoint(self, client, db):
        self._seed(db)
        resp = client.get("/api/dashboard/messages")
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 3
        priorities = {r["priority"] for r in rows}
        assert {"high", "low", "normal"} <= priorities
        assert all(r["platform"] == "system" for r in rows)

    def test_messages_endpoint_unread_only(self, client, db):
        self._seed(db)
        resp = client.get("/api/dashboard/messages?unread_only=true")
        assert resp.status_code == 200
        assert resp.json() == []

    # -- user_id clamp --------------------------------------------------------

    def test_user_id_clamped_to_current_on_data(self, client, db):
        self._seed(db)
        resp = client.get("/api/dashboard/data", params={"user_id": "someone-else"})
        assert resp.status_code == 200
        assert resp.json()["stats"]["upcoming_events"] == 3

    def test_user_id_clamped_to_current_on_stats(self, client, db):
        self._seed(db)
        resp = client.get("/api/dashboard/stats", params={"user_id": "evil"})
        assert resp.status_code == 200
        assert resp.json()["upcoming_events"] == 3

    def test_user_id_clamped_on_events_tasks_messages(self, client, db):
        self._seed(db)
        assert client.get(
            "/api/dashboard/events", params={"user_id": "evil"}
        ).status_code == 200
        assert client.get(
            "/api/dashboard/tasks", params={"user_id": "evil"}
        ).status_code == 200
        assert client.get(
            "/api/dashboard/messages", params={"user_id": "evil"}
        ).status_code == 200

    def test_user_id_matching_current(self, client, db):
        self._seed(db)
        resp = client.get("/api/dashboard/data", params={"user_id": "u-1"})
        assert resp.status_code == 200
        assert resp.json()["stats"]["unread_messages"] == 2  # None-user log excluded

    # -- 422 bounds ----------------------------------------------------------

    def test_limit_bounds_422(self, client, db):
        self._seed(db)
        assert client.get("/api/dashboard/data", params={"limit": 0}).status_code == 422
        assert client.get("/api/dashboard/data", params={"limit": 101}).status_code == 422
        assert client.get("/api/dashboard/events", params={"limit": 51}).status_code == 422
        assert client.get("/api/dashboard/tasks", params={"limit": 101}).status_code == 422
        assert client.get("/api/dashboard/messages", params={"limit": 101}).status_code == 422

    # -- endpoint 500 branches (helper raises) -------------------------------

    def test_data_endpoint_helper_exception_500(self, client, db):
        self._seed(db)
        with patch(f"{self.MOD}.calculate_dashboard_stats",
                   side_effect=RuntimeError("boom")):
            resp = client.get("/api/dashboard/data")
        assert resp.status_code == 500

    def test_stats_endpoint_helper_exception_500(self, client, db):
        self._seed(db)
        with patch(f"{self.MOD}.calculate_dashboard_stats",
                   side_effect=RuntimeError("boom")):
            resp = client.get("/api/dashboard/stats")
        assert resp.status_code == 500

    def test_events_endpoint_helper_exception_500(self, client, db):
        self._seed(db)
        with patch(f"{self.MOD}.get_user_upcoming_events",
                   side_effect=RuntimeError("boom")):
            resp = client.get("/api/dashboard/events")
        assert resp.status_code == 500

    def test_tasks_endpoint_helper_exception_500(self, client, db):
        self._seed(db)
        with patch(f"{self.MOD}.get_user_tasks", side_effect=RuntimeError("boom")):
            resp = client.get("/api/dashboard/tasks")
        assert resp.status_code == 500

    def test_messages_endpoint_helper_exception_500(self, client, db):
        self._seed(db)
        with patch(f"{self.MOD}.get_user_messages", side_effect=RuntimeError("boom")):
            resp = client.get("/api/dashboard/messages")
        assert resp.status_code == 500

    # -- helpers: direct unit coverage ----------------------------------------

    def test_helpers_error_returns_empty(self):
        import api.dashboard_data_routes as ddr
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        assert ddr.get_user_upcoming_events(db, "u-1") == []
        assert ddr.get_user_tasks(db, "u-1") == []
        assert ddr.get_user_messages(db, "u-1") == []
        stats = ddr.calculate_dashboard_stats(db, "u-1")
        assert stats["upcoming_events"] == 0
        assert stats["overdue_tasks"] == 0
        assert stats["unread_messages"] == 0
        assert stats["completed_tasks"] == 0
        assert stats["active_workflows"] == 0
        assert stats["total_agents"] == 0

    def test_helpers_without_user_filter(self, db):
        import api.dashboard_data_routes as ddr
        self._seed(db)
        events = ddr.get_user_upcoming_events(db, None, limit=10)
        assert len(events) == 3
        tasks = ddr.get_user_tasks(db, None, limit=20)
        assert len(tasks) == 7
        messages = ddr.get_user_messages(db, None, limit=20)
        assert len(messages) == 3
        stats = ddr.calculate_dashboard_stats(db, None)
        assert stats["upcoming_events"] == 3

    def test_helpers_empty_db_zero_stats(self, db):
        import api.dashboard_data_routes as ddr
        assert ddr.get_user_upcoming_events(db, "u-1") == []
        assert ddr.get_user_tasks(db, "u-1") == []
        assert ddr.get_user_messages(db, "u-1") == []
        stats = ddr.calculate_dashboard_stats(db, "u-1")
        assert stats["upcoming_events"] == 0
        assert stats["overdue_tasks"] == 0
        assert stats["unread_messages"] == 0
        assert stats["completed_tasks"] == 0
        assert stats["active_workflows"] == 0
        assert stats["total_agents"] == 0


# ============================================================================
# api/dynamic_options_routes.py
# ============================================================================

class TestDynamicOptionsRoutes:
    """Coverage: api/dynamic_options_routes.py"""

    MOD = "api.dynamic_options_routes"
    PATH = "/api/v1/integrations/dynamic-options"

    @pytest.fixture
    def client(self):
        from api.dynamic_options_routes import router
        return _auth_client(router, raise_exc=False)

    @pytest.fixture
    def anon(self):
        from api.dynamic_options_routes import router
        return _anon_client(router)

    def _payload(self, **over):
        payload = {
            "pieceId": "slack", "propertyName": "channel",
            "actionName": "post", "triggerName": None,
            "config": {}, "connectionId": None,
        }
        payload.update(over)
        return payload

    @staticmethod
    def _bridge(result=None, side_effect=None):
        bridge = AsyncMock()
        if result is not None:
            bridge.get_dynamic_options.return_value = result
        if side_effect is not None:
            bridge.get_dynamic_options.side_effect = side_effect
        return patch(
            "integrations.bridge.node_bridge_service.node_bridge", new=bridge
        )

    def test_requires_auth(self, anon):
        resp = anon.post(self.PATH, json=self._payload())
        assert resp.status_code == 401

    def test_missing_required_fields_422(self, client):
        assert client.post(self.PATH, json={}).status_code == 422
        assert client.post(
            self.PATH, json={"pieceId": "slack"}
        ).status_code == 422

    def test_success_with_options(self, client):
        with self._bridge(result={
            "options": [{"label": "general", "value": "general"}],
            "placeholder": "Pick a channel",
        }):
            resp = client.post(self.PATH, json=self._payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["options"] == [{"label": "general", "value": "general"}]
        assert body["data"]["placeholder"] == "Pick a channel"
        assert "1 options" in body["message"]

    def test_options_with_error_falls_back(self, client):
        with self._bridge(result={"options": [], "error": "slack auth failed"}):
            resp = client.post(self.PATH, json=self._payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["options"] == []
        assert "No options available" in body["message"]

    def test_empty_result_falls_back(self, client):
        with self._bridge(result={"options": []}):
            resp = client.post(self.PATH, json=self._payload())
        assert resp.status_code == 200
        assert resp.json()["data"]["options"] == []

    def test_bridge_import_error_falls_back(self, client):
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if "node_bridge_service" in name:
                raise ImportError("bridge unavailable")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            resp = client.post(self.PATH, json=self._payload())
        assert resp.status_code == 200
        assert resp.json()["data"]["options"] == []

    def test_bridge_generic_exception_falls_back(self, client):
        with self._bridge(side_effect=RuntimeError("boom")):
            resp = client.post(self.PATH, json=self._payload())
        assert resp.status_code == 200
        assert resp.json()["data"]["options"] == []

    def test_with_connection_credentials_success(self, client):
        with patch(
            "core.connection_service.connection_service"
        ) as conn_svc, self._bridge(result={"options": [{"label": "l"}]}):
            conn_svc.get_connection_credentials = AsyncMock(
                return_value={"token": "t"}
            )
            resp = client.post(self.PATH, json=self._payload(connectionId="conn-1"))
        assert resp.status_code == 200
        assert resp.json()["data"]["options"] == [{"label": "l"}]
        conn_svc.get_connection_credentials.assert_awaited_once_with("conn-1", "u-1")

    def test_with_connection_credentials_fallback(self, client):
        with patch(
            "core.connection_service.connection_service"
        ) as conn_svc, self._bridge(result={"options": []}):
            conn_svc.get_connection_credentials = AsyncMock(
                return_value={"token": "t"}
            )
            resp = client.post(self.PATH, json=self._payload(connectionId="conn-1"))
        assert resp.status_code == 200
        assert resp.json()["data"]["options"] == []

    def test_credentials_fetch_error_response(self, client):
        with patch(
            "core.connection_service.connection_service"
        ) as conn_svc:
            conn_svc.get_connection_credentials = AsyncMock(
                side_effect=RuntimeError("creds down")
            )
            resp = client.post(self.PATH, json=self._payload(connectionId="conn-1"))
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["placeholder"] == "Failed to retrieve credentials"
        assert "Failed to retrieve credentials" in body["message"]


# ============================================================================
# api/evolution_routes.py
# ============================================================================

class TestEvolutionRoutes:
    """Coverage: api/evolution_routes.py"""

    MOD = "api.evolution_routes"

    @pytest.fixture
    def client(self):
        from api.evolution_routes import router
        return _auth_client(router, prefix="/api/evolution", raise_exc=False)

    @pytest.fixture
    def anon(self):
        from api.evolution_routes import router
        return _anon_client(router, prefix="/api/evolution")

    def test_run_requires_auth(self, anon):
        resp = anon.post("/api/evolution/run", params={"tenant_id": "t1"})
        assert resp.status_code == 401

    def test_traces_requires_auth(self, anon):
        resp = anon.get("/api/evolution/traces/a-1")
        assert resp.status_code == 401

    def test_run_missing_tenant_422(self, client):
        resp = client.post("/api/evolution/run")
        assert resp.status_code == 422

    def test_run_starts_background_cycle(self, client):
        loop = MagicMock()
        loop.run_evolution_cycle = AsyncMock(return_value=None)
        with patch(f"{self.MOD}.AgentEvolutionLoop", return_value=loop):
            resp = client.post(
                "/api/evolution/run",
                params={"tenant_id": "t-1", "target_agent_id": "a-1", "group_size": 3},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "started"
        assert body["tenant_id"] == "t-1"
        loop.run_evolution_cycle.assert_awaited_once_with(
            tenant_id="t-1", group_size=3, target_agent_id="a-1",
        )

    def test_run_default_group_size_no_target(self, client):
        loop = MagicMock()
        loop.run_evolution_cycle = AsyncMock(return_value=None)
        with patch(f"{self.MOD}.AgentEvolutionLoop", return_value=loop):
            resp = client.post("/api/evolution/run", params={"tenant_id": "t-2"})
        assert resp.status_code == 200
        loop.run_evolution_cycle.assert_awaited_once_with(
            tenant_id="t-2", group_size=5, target_agent_id=None,
        )

    def test_traces_returns_serialized_rows(self, client):
        mock_db = MagicMock()
        rows = [
            SimpleNamespace(
                id="tr-1", generation=3, performance_score=0.8,
                novelty_score=0.2, evolving_requirements=["directive"],
                created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            ),
            SimpleNamespace(
                id="tr-2", generation=1, performance_score=0.5,
                novelty_score=0.4, evolving_requirements=[],
                created_at=None,
            ),
        ]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = rows
        from api.evolution_routes import router
        client = _auth_client(router, prefix="/api/evolution", db=mock_db)
        resp = client.get("/api/evolution/traces/a-1")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["id"] == "tr-1"
        assert body[0]["generation"] == 3
        assert body[0]["directives"] == ["directive"]
        assert body[1]["directives"] == []

    def test_traces_empty(self, client):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        from api.evolution_routes import router
        client = _auth_client(router, prefix="/api/evolution", db=mock_db)
        resp = client.get("/api/evolution/traces/ghost")
        assert resp.status_code == 200
        assert resp.json() == []
