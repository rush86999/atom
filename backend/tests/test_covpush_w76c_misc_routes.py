# -*- coding: utf-8 -*-
"""Coverage wave 76c — misc route modules.

Targets (each >=95% standalone):
- api/project_routes.py        (unified tasks via MCP)
- api/reports.py               (reports root)
- api/supervision_routes.py    (SSE stream, intervene, complete, sessions, approve)
- api/time_travel_routes.py    (workflow fork)
- api/user_activity_routes.py  (heartbeat / state / override / supervisors / sessions)
- api/workspace_routes.py      (unified workspace sync CRUD)
- api/ab_testing.py            (A/B test lifecycle routes)

No LLM, no network, no real DB: FastAPI TestClient + dependency_overrides +
service/mcp patches on real module names.
"""
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import AsyncMock, Mock, patch

from api.project_routes import router as project_router
from api.reports import router as reports_router
from api.supervision_routes import router as supervision_router
from api.time_travel_routes import router as time_travel_router
from api.user_activity_routes import router as user_activity_router
from api.workspace_routes import router as workspace_router
from api.ab_testing import router as ab_testing_router

from core.auth import get_current_user
from core.database import get_db
from core.models import UserRole, UserState


# ============================================================================
# Shared helpers
# ============================================================================

def _make_client(router, db_session=None, user_id="test-user", role=UserRole.MEMBER):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: Mock(
        id=user_id, role=role, status="active"
    )
    if db_session is not None:
        app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def _empty_db_session():
    """Mock session whose queries return no rows."""
    mock_db = Mock(spec=Session)
    empty_filter = Mock()
    empty_filter.first = Mock(return_value=None)
    empty_filter.all = Mock(return_value=[])
    empty_query = Mock()
    empty_query.filter = Mock(return_value=empty_filter)
    empty_query.order_by = Mock(return_value=empty_query)
    mock_db.query = Mock(return_value=empty_query)
    mock_db.add = Mock()
    mock_db.commit = Mock()
    mock_db.rollback = Mock()
    mock_db.refresh = Mock()
    return mock_db


# ============================================================================
# api/reports.py
# ============================================================================

class TestReportsRoutes:
    """Coverage: api/reports.py"""

    def test_reports_root_success(self):
        client = _make_client(reports_router)
        resp = client.get("/api/reports/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["message"] == "Reports API"


# ============================================================================
# api/project_routes.py
# ============================================================================

class TestProjectRoutes:
    """Coverage: api/project_routes.py"""

    def test_get_unified_tasks_success(self):
        client = _make_client(project_router, _empty_db_session())
        with patch("api.project_routes.mcp_service") as mcp:
            mcp.execute_tool = AsyncMock(
                return_value=[{"id": "task-1", "title": "T1"}]
            )
            resp = client.get("/api/projects/unified-tasks")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        mcp.execute_tool.assert_called_once_with(
            "local-tools", "get_tasks", {}, {"user_id": "test-user"}
        )

    def test_get_unified_tasks_service_error(self):
        client = _make_client(project_router, _empty_db_session())
        with patch("api.project_routes.mcp_service") as mcp:
            mcp.execute_tool = AsyncMock(side_effect=Exception("boom"))
            resp = client.get("/api/projects/unified-tasks")
        assert resp.status_code == 500
        assert resp.json()["detail"]["success"] is False

    def test_create_unified_task_success(self):
        client = _make_client(project_router, _empty_db_session())
        with patch("api.project_routes.mcp_service") as mcp:
            mcp.execute_tool = AsyncMock(return_value={"id": "task-new"})
            resp = client.post(
                "/api/projects/unified-tasks",
                json={"title": "New Task", "priority": "high"},
            )
        assert resp.status_code == 200
        assert resp.json()["data"] == {"id": "task-new"}
        mcp.execute_tool.assert_called_once()
        args = mcp.execute_tool.call_args
        assert args[0][2] == {"title": "New Task", "priority": "high"}
        assert args[0][3] == {"user_id": "test-user"}

    def test_create_unified_task_service_error(self):
        client = _make_client(project_router, _empty_db_session())
        with patch("api.project_routes.mcp_service") as mcp:
            mcp.execute_tool = AsyncMock(side_effect=Exception("boom"))
            resp = client.post(
                "/api/projects/unified-tasks", json={"title": "New Task"}
            )
        assert resp.status_code == 500
        assert resp.json()["detail"]["success"] is False


# ============================================================================
# api/time_travel_routes.py
# ============================================================================

class TestTimeTravelRoutes:
    """Coverage: api/time_travel_routes.py"""

    @pytest.fixture
    def client(self):
        return _make_client(time_travel_router, None)

    def test_fork_workflow_success(self, client):
        orch = Mock()
        orch.fork_execution = AsyncMock(return_value="new-exec-1")
        with patch("api.time_travel_routes.get_orchestrator",
                   return_value=orch):
            resp = client.post(
                "/api/time-travel/workflows/exec-1/fork",
                json={"step_id": "step-9", "new_variables": {"x": 1}},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["original_execution_id"] == "exec-1"
        assert body["new_execution_id"] == "new-exec-1"
        orch.fork_execution.assert_awaited_once_with(
            original_execution_id="exec-1",
            step_id="step-9",
            new_variables={"x": 1},
        )

    def test_fork_workflow_without_variables(self, client):
        orch = Mock()
        orch.fork_execution = AsyncMock(return_value="new-exec-2")
        with patch("api.time_travel_routes.get_orchestrator",
                   return_value=orch):
            resp = client.post(
                "/api/time-travel/workflows/exec-2/fork",
                json={"step_id": "step-1"},
            )
        assert resp.status_code == 200
        orch.fork_execution.assert_awaited_once_with(
            original_execution_id="exec-2",
            step_id="step-1",
            new_variables=None,
        )

    def test_fork_workflow_not_found(self, client):
        orch = Mock()
        orch.fork_execution = AsyncMock(return_value=None)
        with patch("api.time_travel_routes.get_orchestrator",
                   return_value=orch):
            resp = client.post(
                "/api/time-travel/workflows/exec-3/fork",
                json={"step_id": "missing-step"},
            )
        assert resp.status_code == 404
        assert resp.json()["detail"]["success"] is False

    def test_fork_workflow_missing_step_id_422(self, client):
        resp = client.post("/api/time-travel/workflows/exec-4/fork", json={})
        assert resp.status_code == 422

    def test_fork_workflow_unauthorized(self):
        app = FastAPI()
        app.include_router(time_travel_router)
        client = TestClient(app)
        resp = client.post(
            "/api/time-travel/workflows/exec-5/fork", json={"step_id": "s1"}
        )
        assert resp.status_code == 401


# ============================================================================
# api/supervision_routes.py
# ============================================================================

class _FakeSupervisionService:
    """Stand-in for SupervisionService with configurable async methods."""

    def __init__(self, db=None, monitor_events=None, monitor_error=None,
                 intervene_result=None, complete_result=None,
                 active_sessions=None, history=None):
        self.db = db
        self.monitor_events = monitor_events or []
        self.monitor_error = monitor_error
        self.intervene_result = intervene_result or Mock(
            success=True, message="Intervention applied", session_state="paused"
        )
        self.complete_result = complete_result or Mock(
            session_id="session-1", duration_seconds=300,
            intervention_count=2, confidence_boost=0.1
        )
        self.active_sessions = active_sessions or []
        self.history = history or []

    async def monitor_agent_execution(self, session=None, db=None):
        if self.monitor_error:
            raise self.monitor_error
        for event in self.monitor_events:
            yield event

    async def intervene(self, session_id, intervention_type, guidance):
        return self.intervene_result

    async def complete_supervision(self, session_id, supervisor_rating, feedback):
        return self.complete_result

    async def get_active_sessions(self, workspace_id=None, limit=50):
        return self.active_sessions

    async def get_supervision_history(self, agent_id, limit=50):
        return self.history


def _supervision_db(execution=None, session=None, supervisor=None):
    """Mock db: User -> supervisor (or None), AgentExecution/SupervisionSession
    -> execution/session, everything else empty."""
    mock_db = Mock(spec=Session)

    def chain(row):
        f = Mock()
        f.first = Mock(return_value=row)
        q = Mock()
        q.filter = Mock(return_value=f)
        return q

    def query_impl(model):
        from core.models import AgentExecution, SupervisionSession, User
        if model is User:
            return chain(supervisor)
        if model is AgentExecution:
            return chain(execution)
        if model is SupervisionSession:
            return chain(session)
        return _empty_db_session().query

    mock_db.query = Mock(side_effect=query_impl)
    return mock_db


def _supervision_event(event_type="execution_completed", **data):
    from core.supervision_service import SupervisionEvent
    return SupervisionEvent(
        event_type=event_type,
        timestamp=datetime.now(timezone.utc),
        data=data,
    )


class TestSupervisionRoutes:
    """Coverage: api/supervision_routes.py"""

    @pytest.fixture
    def execution(self):
        from core.models import AgentExecution
        exec_ = Mock(spec=AgentExecution)
        exec_.id = "exec-1"
        exec_.agent_id = "agent-1"
        exec_.agent_name = "Test Agent"
        return exec_

    @pytest.fixture
    def session(self):
        from core.models import SupervisionSession
        s = Mock(spec=SupervisionSession)
        s.id = "session-1"
        s.agent_id = "agent-1"
        s.agent_name = "Test Agent"
        s.supervisor_id = "user-1"
        s.status = "active"
        s.started_at = datetime.now(timezone.utc)
        s.completed_at = None
        s.duration_seconds = 300
        s.intervention_count = 2
        return s

    @pytest.fixture
    def supervisor(self):
        from core.models import User
        u = Mock(spec=User)
        u.id = "test-user"
        u.role = UserRole.SUPER_ADMIN.value
        return u

    # ---- SSE stream ----

    def test_stream_success_with_completion_event(self, execution, session,
                                                  supervisor):
        db_session = _supervision_db(execution, session, supervisor)
        client = _make_client(supervision_router, db_session)
        fake = _FakeSupervisionService(
            db=db_session,
            monitor_events=[
                _supervision_event("action", msg="doing"),
                _supervision_event("execution_completed", outcome="ok"),
            ],
        )
        with patch("api.supervision_routes.SupervisionService",
                   return_value=fake):
            resp = client.get("/api/supervision/exec-1/stream")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        text = resp.text
        assert "event: connected" in text
        assert '"execution_id": "exec-1"' in text
        assert "event: supervision_event" in text
        assert "event: done" in text
        assert "event: error" not in text

    def test_stream_success_with_error_event(self, execution, session, supervisor):
        db_session = _supervision_db(execution, session, supervisor)
        client = _make_client(supervision_router, db_session)
        fake = _FakeSupervisionService(
            db=db_session,
            monitor_events=[_supervision_event("execution_failed")],
        )
        with patch("api.supervision_routes.SupervisionService",
                   return_value=fake):
            resp = client.get("/api/supervision/exec-1/stream")
        assert resp.status_code == 200
        assert "event: done" in resp.text

    def test_stream_service_error_yields_error_event(self, execution, session,
                                                     supervisor):
        db_session = _supervision_db(execution, session, supervisor)
        client = _make_client(supervision_router, db_session)
        fake = _FakeSupervisionService(db=db_session,
                                       monitor_error=RuntimeError("kaboom"))
        with patch("api.supervision_routes.SupervisionService",
                   return_value=fake):
            resp = client.get("/api/supervision/exec-1/stream")
        assert resp.status_code == 200
        assert "event: error" in resp.text
        assert "kaboom" in resp.text

    def test_stream_execution_not_found(self, supervisor):
        db_session = _supervision_db(execution=None, session=None,
                                     supervisor=supervisor)
        client = _make_client(supervision_router, db_session)
        resp = client.get("/api/supervision/nope/stream")
        assert resp.status_code == 404

    def test_stream_unauthorized(self, execution, session, supervisor):
        db_session = _supervision_db(execution, session, supervisor)
        app = FastAPI()
        app.include_router(supervision_router)
        client = TestClient(app)
        resp = client.get("/api/supervision/exec-1/stream")
        assert resp.status_code == 401

    # ---- intervene ----

    def test_intervene_success(self, supervisor):
        db_session = _supervision_db(supervisor=supervisor)
        client = _make_client(supervision_router, db_session)
        fake = _FakeSupervisionService(db=db_session)
        with patch("api.supervision_routes.SupervisionService",
                   return_value=fake):
            resp = client.post(
                "/api/supervision/sessions/session-1/intervene",
                json={"intervention_type": "pause", "guidance": "stop"},
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["session_state"] == "paused"

    def test_intervene_supervisor_not_found_404(self):
        db_session = _supervision_db(supervisor=None)
        client = _make_client(supervision_router, db_session)
        fake = _FakeSupervisionService(db=db_session)
        with patch("api.supervision_routes.SupervisionService",
                   return_value=fake):
            resp = client.post(
                "/api/supervision/sessions/session-1/intervene",
                json={"intervention_type": "pause", "guidance": "stop"},
            )
        assert resp.status_code == 404

    def test_intervene_non_supervisor_forbidden(self):
        from core.models import User
        member = Mock(spec=User)
        member.id = "test-user"
        member.role = UserRole.MEMBER.value
        db_session = _supervision_db(supervisor=member)
        client = _make_client(supervision_router, db_session)
        fake = _FakeSupervisionService(db=db_session)
        with patch("api.supervision_routes.SupervisionService",
                   return_value=fake):
            resp = client.post(
                "/api/supervision/sessions/session-1/intervene",
                json={"intervention_type": "pause", "guidance": "stop"},
            )
        assert resp.status_code == 403
        assert "TEAM_LEAD" in resp.json()["detail"]

    def test_intervene_value_error_404(self, supervisor):
        db_session = _supervision_db(supervisor=supervisor)
        client = _make_client(supervision_router, db_session)
        fake = _FakeSupervisionService(db=db_session)
        fake.intervene = AsyncMock(side_effect=ValueError("no session"))
        with patch("api.supervision_routes.SupervisionService",
                   return_value=fake):
            resp = client.post(
                "/api/supervision/sessions/session-1/intervene",
                json={"intervention_type": "pause", "guidance": "stop"},
            )
        assert resp.status_code == 404
        assert "Internal error" in resp.json()["detail"]

    def test_intervene_generic_error_500(self, supervisor):
        db_session = _supervision_db(supervisor=supervisor)
        client = _make_client(supervision_router, db_session)
        fake = _FakeSupervisionService(db=db_session)
        fake.intervene = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("api.supervision_routes.SupervisionService",
                   return_value=fake):
            resp = client.post(
                "/api/supervision/sessions/session-1/intervene",
                json={"intervention_type": "pause", "guidance": "stop"},
            )
        assert resp.status_code == 500

    def test_intervene_missing_guidance_422(self, supervisor):
        db_session = _supervision_db(supervisor=supervisor)
        client = _make_client(supervision_router, db_session)
        resp = client.post(
            "/api/supervision/sessions/session-1/intervene",
            json={"intervention_type": "pause"},
        )
        assert resp.status_code == 422

    # ---- complete ----

    def test_complete_success(self, supervisor):
        db_session = _supervision_db(supervisor=supervisor)
        client = _make_client(supervision_router, db_session)
        fake = _FakeSupervisionService(db=db_session)
        with patch("api.supervision_routes.SupervisionService",
                   return_value=fake):
            resp = client.post(
                "/api/supervision/sessions/session-1/complete"
                "?supervisor_rating=4&feedback=great",
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["session_id"] == "session-1"
        assert body["confidence_boost"] == 0.1

    def test_complete_value_error_404(self, supervisor):
        db_session = _supervision_db(supervisor=supervisor)
        client = _make_client(supervision_router, db_session)
        fake = _FakeSupervisionService(db=db_session)
        fake.complete_supervision = AsyncMock(
            side_effect=ValueError("no session"))
        with patch("api.supervision_routes.SupervisionService",
                   return_value=fake):
            resp = client.post(
                "/api/supervision/sessions/session-1/complete"
                "?supervisor_rating=3&feedback=ok",
            )
        assert resp.status_code == 404

    def test_complete_non_supervisor_forbidden(self):
        from core.models import User
        member = Mock(spec=User)
        member.id = "test-user"
        member.role = UserRole.VIEWER.value
        db_session = _supervision_db(supervisor=member)
        client = _make_client(supervision_router, db_session)
        fake = _FakeSupervisionService(db=db_session)
        with patch("api.supervision_routes.SupervisionService",
                   return_value=fake):
            resp = client.post(
                "/api/supervision/sessions/session-1/complete"
                "?supervisor_rating=3&feedback=ok",
            )
        assert resp.status_code == 403

    def test_complete_generic_error_500(self, supervisor):
        db_session = _supervision_db(supervisor=supervisor)
        client = _make_client(supervision_router, db_session)
        fake = _FakeSupervisionService(db=db_session)
        fake.complete_supervision = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("api.supervision_routes.SupervisionService",
                   return_value=fake):
            resp = client.post(
                "/api/supervision/sessions/session-1/complete"
                "?supervisor_rating=3&feedback=ok",
            )
        assert resp.status_code == 500

    def test_complete_missing_rating_422(self, supervisor):
        db_session = _supervision_db(supervisor=supervisor)
        client = _make_client(supervision_router, db_session)
        resp = client.post(
            "/api/supervision/sessions/session-1/complete?feedback=ok"
        )
        assert resp.status_code == 422

    def test_complete_rating_out_of_range_422(self, supervisor):
        db_session = _supervision_db(supervisor=supervisor)
        client = _make_client(supervision_router, db_session)
        resp = client.post(
            "/api/supervision/sessions/session-1/complete"
            "?supervisor_rating=6&feedback=ok",
        )
        assert resp.status_code == 422

    # ---- active sessions ----

    def test_get_active_sessions_success(self, supervisor):
        db_session = _supervision_db(supervisor=supervisor)
        client = _make_client(supervision_router, db_session)
        done = Mock()
        done.id = "session-2"
        done.agent_id = "agent-2"
        done.agent_name = "Agent Two"
        done.supervisor_id = "user-2"
        done.status = "completed"
        done.started_at = datetime.now(timezone.utc)
        done.completed_at = datetime.now(timezone.utc)
        done.duration_seconds = 42
        done.intervention_count = 1
        active = Mock()
        active.id = "session-1"
        active.agent_id = "agent-1"
        active.agent_name = "Agent One"
        active.supervisor_id = "user-1"
        active.status = "active"
        active.started_at = datetime.now(timezone.utc)
        active.completed_at = None
        active.duration_seconds = None
        active.intervention_count = 0
        fake = _FakeSupervisionService(db=db_session,
                                       active_sessions=[active, done])
        with patch("api.supervision_routes.SupervisionService",
                   return_value=fake):
            resp = client.get("/api/supervision/sessions/active?limit=10")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["session_id"] == "session-1"
        assert body[0]["completed_at"] is None
        assert body[1]["completed_at"] is not None
        assert body[1]["duration_seconds"] == 42

    def test_get_active_sessions_empty(self, supervisor):
        db_session = _supervision_db(supervisor=supervisor)
        client = _make_client(supervision_router, db_session)
        fake = _FakeSupervisionService(db=db_session, active_sessions=[])
        with patch("api.supervision_routes.SupervisionService",
                   return_value=fake):
            resp = client.get("/api/supervision/sessions/active")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_active_sessions_error_500(self, supervisor):
        db_session = _supervision_db(supervisor=supervisor)
        client = _make_client(supervision_router, db_session)
        fake = _FakeSupervisionService(db=db_session)
        fake.get_active_sessions = AsyncMock(
            side_effect=RuntimeError("boom"))
        with patch("api.supervision_routes.SupervisionService",
                   return_value=fake):
            resp = client.get("/api/supervision/sessions/active")
        assert resp.status_code == 500

    # ---- agent history ----

    def test_get_agent_history_success(self, supervisor):
        db_session = _supervision_db(supervisor=supervisor)
        client = _make_client(supervision_router, db_session)
        fake = _FakeSupervisionService(db=db_session, history=[
            {
                "session_id": "session-1",
                "status": "completed",
                "started_at": "2026-08-01T10:00:00",
                "completed_at": "2026-08-01T10:05:00",
                "duration_seconds": 300,
                "intervention_count": 2,
            },
            {
                "session_id": "session-2",
                "status": "active",
                "started_at": "2026-08-01T11:00:00",
            },
        ])
        with patch("api.supervision_routes.SupervisionService",
                   return_value=fake):
            resp = client.get("/api/supervision/agents/agent-1/sessions")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["session_id"] == "session-1"
        assert body[0]["intervention_count"] == 2
        assert body[1]["completed_at"] is None
        assert body[1]["intervention_count"] == 0

    def test_get_agent_history_error_500(self, supervisor):
        db_session = _supervision_db(supervisor=supervisor)
        client = _make_client(supervision_router, db_session)
        fake = _FakeSupervisionService(db=db_session)
        fake.get_supervision_history = AsyncMock(
            side_effect=RuntimeError("boom"))
        with patch("api.supervision_routes.SupervisionService",
                   return_value=fake):
            resp = client.get("/api/supervision/agents/agent-1/sessions")
        assert resp.status_code == 500

    def test_get_agent_history_limit_validation_422(self, supervisor):
        db_session = _supervision_db(supervisor=supervisor)
        client = _make_client(supervision_router, db_session)
        resp = client.get("/api/supervision/agents/agent-1/sessions?limit=0")
        assert resp.status_code == 422

    # ---- get session ----

    def test_get_supervision_session_success(self, session, supervisor):
        db_session = _supervision_db(supervisor=supervisor, session=session)
        client = _make_client(supervision_router, db_session)
        resp = client.get("/api/supervision/sessions/session-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == "session-1"
        assert body["agent_name"] == "Test Agent"
        assert body["supervisor_type"] == "user"

    def test_get_supervision_session_not_found(self, supervisor):
        db_session = _supervision_db(supervisor=supervisor, session=None)
        client = _make_client(supervision_router, db_session)
        resp = client.get("/api/supervision/sessions/ghost")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    # ---- autonomous approve ----

    def test_autonomous_approve_success(self, supervisor):
        db_session = _supervision_db(supervisor=supervisor)
        client = _make_client(supervision_router, db_session)
        with patch("core.proposal_service.ProposalService") as MockPS:
            svc = MockPS.return_value
            svc.autonomous_approve_or_reject = AsyncMock(
                return_value={"status": "approved", "proposal_id": "p-1"})
            resp = client.post(
                "/api/supervision/proposals/p-1/autonomous-approve"
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_autonomous_approve_value_error_404(self, supervisor):
        db_session = _supervision_db(supervisor=supervisor)
        client = _make_client(supervision_router, db_session)
        with patch("core.proposal_service.ProposalService") as MockPS:
            svc = MockPS.return_value
            svc.autonomous_approve_or_reject = AsyncMock(
                side_effect=ValueError("nope"))
            resp = client.post(
                "/api/supervision/proposals/p-1/autonomous-approve"
            )
        assert resp.status_code == 404

    def test_autonomous_approve_non_supervisor_forbidden(self):
        from core.models import User
        member = Mock(spec=User)
        member.id = "test-user"
        member.role = UserRole.MEMBER.value
        db_session = _supervision_db(supervisor=member)
        client = _make_client(supervision_router, db_session)
        with patch("core.proposal_service.ProposalService") as MockPS:
            svc = MockPS.return_value
            svc.autonomous_approve_or_reject = AsyncMock()
            resp = client.post(
                "/api/supervision/proposals/p-1/autonomous-approve"
            )
        assert resp.status_code == 403

    def test_autonomous_approve_generic_error_500(self, supervisor):
        db_session = _supervision_db(supervisor=supervisor)
        client = _make_client(supervision_router, db_session)
        with patch("core.proposal_service.ProposalService") as MockPS:
            svc = MockPS.return_value
            svc.autonomous_approve_or_reject = AsyncMock(
                side_effect=RuntimeError("boom"))
            resp = client.post(
                "/api/supervision/proposals/p-1/autonomous-approve"
            )
        assert resp.status_code == 500


# ============================================================================
# api/user_activity_routes.py
# ============================================================================

class _FakeUserActivityService:
    """Stand-in for UserActivityService with configurable async methods."""

    def __init__(self, db=None, heartbeat=None, state=None, override=None,
                 clear=None, supervisors=None, sessions=None, terminated=None,
                 state_error=None):
        self.db = db
        self.heartbeat = heartbeat
        self.state = state or UserState.online
        self.override = override
        self.clear = clear
        self.supervisors = supervisors or []
        self.sessions = sessions or []
        self.terminated = terminated if terminated is not None else True
        self.state_error = state_error

    async def record_heartbeat(self, user_id, session_token, session_type,
                               user_agent, ip_address):
        return self.heartbeat

    async def get_user_state(self, user_id):
        if self.state_error:
            raise self.state_error
        return self.state

    async def set_manual_override(self, user_id, state, expires_at):
        return self.override

    async def clear_manual_override(self, user_id):
        return self.clear

    async def get_available_supervisors(self, category):
        return self.supervisors

    async def get_active_sessions(self, user_id):
        return self.sessions

    async def terminate_session(self, session_token):
        return self.terminated


def _activity(expires_at=None, state=UserState.online):
    a = Mock()
    a.user_id = "user-1"
    a.state = state
    a.last_activity_at = datetime.now(timezone.utc)
    a.manual_override = True
    a.manual_override_expires_at = expires_at
    return a


class TestUserActivityRoutes:
    """Coverage: api/user_activity_routes.py"""

    # ---- heartbeat ----

    def test_send_heartbeat_success(self):
        db_session = _empty_db_session()
        client = _make_client(user_activity_router, db_session)
        fake = _FakeUserActivityService(db=db_session,
                                        heartbeat=_activity())
        with patch("api.user_activity_routes.UserActivityService",
                   return_value=fake):
            resp = client.post(
                "/api/users/user-1/activity/heartbeat",
                json={"session_token": "tok-1", "session_type": "web"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == "user-1"
        assert body["state"] == "online"
        assert body["manual_override"] is True
        assert body["manual_override_expires_at"] is None

    def test_send_heartbeat_with_expiry(self):
        db_session = _empty_db_session()
        client = _make_client(user_activity_router, db_session)
        fake = _FakeUserActivityService(
            db=db_session,
            heartbeat=_activity(expires_at=datetime.now(timezone.utc)),
        )
        with patch("api.user_activity_routes.UserActivityService",
                   return_value=fake):
            resp = client.post(
                "/api/users/user-1/activity/heartbeat",
                json={"session_token": "tok-1",
                      "session_type": "desktop",
                      "user_agent": "ua", "ip_address": "1.2.3.4"},
            )
        assert resp.status_code == 200
        assert resp.json()["manual_override_expires_at"] is not None

    def test_send_heartbeat_service_error_500(self):
        db_session = _empty_db_session()
        client = _make_client(user_activity_router, db_session)
        fake = _FakeUserActivityService(db=db_session, heartbeat=Exception)
        fake.record_heartbeat = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("api.user_activity_routes.UserActivityService",
                   return_value=fake):
            resp = client.post(
                "/api/users/user-1/activity/heartbeat",
                json={"session_token": "tok-1"},
            )
        assert resp.status_code == 500

    def test_send_heartbeat_missing_token_422(self):
        db_session = _empty_db_session()
        client = _make_client(user_activity_router, db_session)
        resp = client.post("/api/users/user-1/activity/heartbeat", json={})
        assert resp.status_code == 422

    # ---- get state ----

    def test_get_user_state_with_record(self):
        db_session = _empty_db_session()
        record = _activity(expires_at=datetime.now(timezone.utc))
        chain = Mock()
        chain.first = Mock(return_value=record)
        query = Mock()
        query.filter = Mock(return_value=chain)
        db_session.query = Mock(return_value=query)
        client = _make_client(user_activity_router, db_session)
        fake = _FakeUserActivityService(db=db_session)
        with patch("api.user_activity_routes.UserActivityService",
                   return_value=fake):
            resp = client.get("/api/users/user-1/activity/state")
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == "user-1"
        assert body["state"] == "online"
        assert body["manual_override_expires_at"] is not None

    def test_get_user_state_without_record(self):
        db_session = _empty_db_session()
        client = _make_client(user_activity_router, db_session)
        fake = _FakeUserActivityService(db=db_session,
                                        state=UserState.away)
        with patch("api.user_activity_routes.UserActivityService",
                   return_value=fake):
            resp = client.get("/api/users/user-1/activity/state")
        assert resp.status_code == 200
        body = resp.json()
        assert body["state"] == "away"
        assert body["manual_override"] is False
        assert body["manual_override_expires_at"] is None

    def test_get_user_state_error_500(self):
        db_session = _empty_db_session()
        client = _make_client(user_activity_router, db_session)
        fake = _FakeUserActivityService(db=db_session,
                                        state_error=RuntimeError("boom"))
        with patch("api.user_activity_routes.UserActivityService",
                   return_value=fake):
            resp = client.get("/api/users/user-1/activity/state")
        assert resp.status_code == 500

    # ---- manual override ----

    def test_set_manual_override_success(self):
        db_session = _empty_db_session()
        client = _make_client(user_activity_router, db_session)
        fake = _FakeUserActivityService(
            db=db_session,
            override=_activity(expires_at=datetime.now(timezone.utc)),
        )
        with patch("api.user_activity_routes.UserActivityService",
                   return_value=fake):
            resp = client.post(
                "/api/users/user-1/activity/override",
                json={"state": "away",
                      "expires_at": "2026-08-13T23:59:59Z"},
            )
        assert resp.status_code == 200
        assert resp.json()["state"] == "online"
        assert resp.json()["manual_override_expires_at"] is not None

    def test_set_manual_override_without_expiry(self):
        db_session = _empty_db_session()
        client = _make_client(user_activity_router, db_session)
        fake = _FakeUserActivityService(db=db_session,
                                        override=_activity())
        with patch("api.user_activity_routes.UserActivityService",
                   return_value=fake):
            resp = client.post(
                "/api/users/user-1/activity/override",
                json={"state": "offline"},
            )
        assert resp.status_code == 200
        assert resp.json()["manual_override_expires_at"] is None

    def test_set_manual_override_invalid_state_400(self):
        db_session = _empty_db_session()
        client = _make_client(user_activity_router, db_session)
        fake = _FakeUserActivityService(db=db_session)
        with patch("api.user_activity_routes.UserActivityService",
                   return_value=fake):
            resp = client.post(
                "/api/users/user-1/activity/override",
                json={"state": "zombie"},
            )
        assert resp.status_code == 400
        assert "Invalid state" in resp.json()["detail"]

    def test_set_manual_override_invalid_expiry_400(self):
        db_session = _empty_db_session()
        client = _make_client(user_activity_router, db_session)
        fake = _FakeUserActivityService(db=db_session)
        with patch("api.user_activity_routes.UserActivityService",
                   return_value=fake):
            resp = client.post(
                "/api/users/user-1/activity/override",
                json={"state": "away", "expires_at": "not-a-date"},
            )
        assert resp.status_code == 400
        assert "Invalid datetime" in resp.json()["detail"]

    def test_set_manual_override_service_error_500(self):
        db_session = _empty_db_session()
        client = _make_client(user_activity_router, db_session)
        fake = _FakeUserActivityService(db=db_session)
        fake.set_manual_override = AsyncMock(
            side_effect=RuntimeError("boom"))
        with patch("api.user_activity_routes.UserActivityService",
                   return_value=fake):
            resp = client.post(
                "/api/users/user-1/activity/override",
                json={"state": "away"},
            )
        assert resp.status_code == 500

    # ---- clear override ----

    def test_clear_manual_override_success(self):
        db_session = _empty_db_session()
        client = _make_client(user_activity_router, db_session)
        fake = _FakeUserActivityService(
            db=db_session,
            clear=_activity(expires_at=datetime.now(timezone.utc)),
        )
        with patch("api.user_activity_routes.UserActivityService",
                   return_value=fake):
            resp = client.delete("/api/users/user-1/activity/override")
        assert resp.status_code == 200
        assert resp.json()["manual_override_expires_at"] is not None

    def test_clear_manual_override_value_error_404(self):
        db_session = _empty_db_session()
        client = _make_client(user_activity_router, db_session)
        fake = _FakeUserActivityService(db=db_session)
        fake.clear_manual_override = AsyncMock(
            side_effect=ValueError("no activity"))
        with patch("api.user_activity_routes.UserActivityService",
                   return_value=fake):
            resp = client.delete("/api/users/user-1/activity/override")
        assert resp.status_code == 404

    def test_clear_manual_override_error_500(self):
        db_session = _empty_db_session()
        client = _make_client(user_activity_router, db_session)
        fake = _FakeUserActivityService(db=db_session)
        fake.clear_manual_override = AsyncMock(
            side_effect=RuntimeError("boom"))
        with patch("api.user_activity_routes.UserActivityService",
                   return_value=fake):
            resp = client.delete("/api/users/user-1/activity/override")
        assert resp.status_code == 500

    # ---- available supervisors ----

    def _supervisor_dict(self, user_id, specialty, state="online"):
        return {
            "user_id": user_id,
            "email": f"{user_id}@example.com",
            "first_name": "A",
            "last_name": "B",
            "state": state,
            "last_activity_at": "2026-08-13T10:00:00",
            "specialty": specialty,
        }

    def test_get_available_supervisors_all(self):
        db_session = _empty_db_session()
        client = _make_client(user_activity_router, db_session)
        fake = _FakeUserActivityService(db=db_session, supervisors=[
            self._supervisor_dict("u1", "backend"),
            self._supervisor_dict("u2", "frontend"),
        ])
        with patch("api.user_activity_routes.UserActivityService",
                   return_value=fake):
            resp = client.get("/api/users/available-supervisors")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_count"] == 2
        assert len(body["supervisors"]) == 2

    def test_get_available_supervisors_filtered(self):
        db_session = _empty_db_session()
        client = _make_client(user_activity_router, db_session)
        fake = _FakeUserActivityService(db=db_session, supervisors=[
            self._supervisor_dict("u1", "backend"),
            self._supervisor_dict("u2", "frontend"),
            self._supervisor_dict("u3", "backend"),
        ])
        with patch("api.user_activity_routes.UserActivityService",
                   return_value=fake):
            resp = client.get("/api/users/available-supervisors?category=backend")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_count"] == 2
        assert {s["user_id"] for s in body["supervisors"]} == {"u1", "u3"}

    def test_get_available_supervisors_filtered_no_match(self):
        db_session = _empty_db_session()
        client = _make_client(user_activity_router, db_session)
        fake = _FakeUserActivityService(db=db_session, supervisors=[
            self._supervisor_dict("u1", "backend"),
        ])
        with patch("api.user_activity_routes.UserActivityService",
                   return_value=fake):
            resp = client.get("/api/users/available-supervisors?category=devops")
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 0

    def test_get_available_supervisors_error_500(self):
        db_session = _empty_db_session()
        client = _make_client(user_activity_router, db_session)
        fake = _FakeUserActivityService(db=db_session)
        fake.get_available_supervisors = AsyncMock(
            side_effect=RuntimeError("boom"))
        with patch("api.user_activity_routes.UserActivityService",
                   return_value=fake):
            resp = client.get("/api/users/available-supervisors")
        assert resp.status_code == 500

    # ---- active sessions ----

    def test_get_active_sessions_success(self):
        db_session = _empty_db_session()
        client = _make_client(user_activity_router, db_session)
        s = Mock()
        s.id = "sess-1"
        s.session_type = "web"
        s.session_token = "tok-1"
        s.last_heartbeat = datetime.now(timezone.utc)
        s.user_agent = "Mozilla"
        s.ip_address = "9.9.9.9"
        s.created_at = datetime.now(timezone.utc)
        fake = _FakeUserActivityService(db=db_session, sessions=[s])
        with patch("api.user_activity_routes.UserActivityService",
                   return_value=fake):
            resp = client.get("/api/users/user-1/activity/sessions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_count"] == 1
        assert body["sessions"][0]["session_token"] == "tok-1"

    def test_get_active_sessions_empty(self):
        db_session = _empty_db_session()
        client = _make_client(user_activity_router, db_session)
        fake = _FakeUserActivityService(db=db_session, sessions=[])
        with patch("api.user_activity_routes.UserActivityService",
                   return_value=fake):
            resp = client.get("/api/users/user-1/activity/sessions")
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 0

    def test_get_active_sessions_error_500(self):
        db_session = _empty_db_session()
        client = _make_client(user_activity_router, db_session)
        fake = _FakeUserActivityService(db=db_session)
        fake.get_active_sessions = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("api.user_activity_routes.UserActivityService",
                   return_value=fake):
            resp = client.get("/api/users/user-1/activity/sessions")
        assert resp.status_code == 500

    # ---- terminate session ----

    def test_terminate_session_success(self):
        db_session = _empty_db_session()
        client = _make_client(user_activity_router, db_session)
        fake = _FakeUserActivityService(db=db_session, terminated=True)
        with patch("api.user_activity_routes.UserActivityService",
                   return_value=fake):
            resp = client.delete("/api/users/activity/sessions/tok-1")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_terminate_session_not_found_404(self):
        db_session = _empty_db_session()
        client = _make_client(user_activity_router, db_session)
        fake = _FakeUserActivityService(db=db_session, terminated=False)
        with patch("api.user_activity_routes.UserActivityService",
                   return_value=fake):
            resp = client.delete("/api/users/activity/sessions/tok-1")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    def test_terminate_session_error_500(self):
        db_session = _empty_db_session()
        client = _make_client(user_activity_router, db_session)
        fake = _FakeUserActivityService(db=db_session)
        fake.terminate_session = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("api.user_activity_routes.UserActivityService",
                   return_value=fake):
            resp = client.delete("/api/users/activity/sessions/tok-1")
        assert resp.status_code == 500


# ============================================================================
# api/workspace_routes.py
# ============================================================================

def _workspace(user_id="test-user", with_dates=True):
    from core.models import UnifiedWorkspace
    w = Mock(spec=UnifiedWorkspace)
    w.id = "ws-1"
    w.user_id = user_id
    w.name = "My Workspace"
    w.description = "desc"
    w.slack_workspace_id = "S123"
    w.discord_guild_id = "G123"
    w.google_chat_space_id = "GC123"
    w.teams_team_id = "T123"
    w.sync_status = "synced"
    if with_dates:
        w.last_sync_at = datetime.now(timezone.utc)
        w.created_at = datetime.now(timezone.utc)
        w.updated_at = datetime.now(timezone.utc)
    else:
        w.last_sync_at = None
        w.created_at = None
        w.updated_at = None
    w.platform_count = 3
    w.member_count = 5
    return w


def _workspace_db(workspace=None, all_workspaces=None, user_id="test-user"):
    """Mock db: UnifiedWorkspace queries return workspace / all_workspaces."""
    if workspace is None and all_workspaces:
        workspace = all_workspaces[0]
    mock_db = Mock(spec=Session)
    f = Mock()
    f.first = Mock(return_value=workspace)
    o = Mock()
    o.all = Mock(return_value=all_workspaces or [])
    q = Mock()
    q.filter = Mock(return_value=f)
    f.order_by = Mock(return_value=o)
    q.order_by = Mock(return_value=o)

    def query_impl(model):
        return q

    mock_db.query = Mock(side_effect=query_impl)
    mock_db.delete = Mock()
    mock_db.commit = Mock()
    mock_db.rollback = Mock()
    return mock_db


class TestWorkspaceRoutes:
    """Coverage: api/workspace_routes.py"""

    def _client(self, db_session):
        return _make_client(workspace_router, db_session)

    # ---- create ----

    def test_create_workspace_success(self):
        db_session = _workspace_db(workspace=_workspace())
        client = self._client(db_session)
        with patch("api.workspace_routes.WorkspaceSyncService") as MockSvc:
            svc = MockSvc.return_value
            svc.create_unified_workspace.return_value = _workspace()
            resp = client.post(
                "/api/v1/workspaces/unified",
                json={
                    "user_id": "evil-other-user",
                    "name": "My Workspace",
                    "description": "desc",
                    "slack_workspace_id": "S123",
                    "discord_guild_id": "G123",
                    "google_chat_space_id": "GC123",
                    "teams_team_id": "T123",
                    "sync_config": {"x": 1},
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["name"] == "My Workspace"
        # R54: ownership comes from the token, never the body
        assert svc.create_unified_workspace.call_args.kwargs["user_id"] == \
            "test-user"

    def test_create_workspace_no_platform_422(self):
        db_session = _workspace_db(workspace=None)
        client = self._client(db_session)
        with patch("api.workspace_routes.WorkspaceSyncService") as MockSvc:
            resp = client.post(
                "/api/v1/workspaces/unified",
                json={"user_id": "body-user", "name": "No Platforms"},
            )
        assert resp.status_code == 422
        assert "At least one platform ID" in \
            resp.json()["detail"]["error"]["message"]

    def test_create_workspace_empty_name_422(self):
        db_session = _workspace_db(workspace=None)
        client = self._client(db_session)
        resp = client.post(
            "/api/v1/workspaces/unified",
            json={"user_id": "body-user", "name": "",
                  "slack_workspace_id": "S1"},
        )
        assert resp.status_code == 422

    def test_create_workspace_value_error_422(self):
        db_session = _workspace_db(workspace=None)
        client = self._client(db_session)
        with patch("api.workspace_routes.WorkspaceSyncService") as MockSvc:
            MockSvc.return_value.create_unified_workspace.side_effect = \
                ValueError("bad workspace")
            resp = client.post(
                "/api/v1/workspaces/unified",
                json={"user_id": "body-user", "name": "X",
                      "slack_workspace_id": "S1"},
            )
        assert resp.status_code == 422
        assert "bad workspace" in \
            resp.json()["detail"]["error"]["message"]

    def test_create_workspace_generic_error_500(self):
        db_session = _workspace_db(workspace=None)
        client = self._client(db_session)
        with patch("api.workspace_routes.WorkspaceSyncService") as MockSvc:
            MockSvc.return_value.create_unified_workspace.side_effect = \
                RuntimeError("boom")
            resp = client.post(
                "/api/v1/workspaces/unified",
                json={"user_id": "body-user", "name": "X",
                      "slack_workspace_id": "S1"},
            )
        assert resp.status_code == 500
        assert resp.json()["detail"]["success"] is False

    # ---- add platform ----

    def test_add_platform_success(self):
        db_session = _workspace_db(workspace=_workspace())
        client = self._client(db_session)
        with patch("api.workspace_routes.WorkspaceSyncService") as MockSvc:
            MockSvc.return_value.add_platform_to_workspace.return_value = \
                _workspace()
            resp = client.post(
                "/api/v1/workspaces/unified/ws-1/platforms",
                json={"workspace_id": "ws-1", "platform": "slack",
                      "platform_id": "S456"},
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_add_platform_workspace_not_found_404(self):
        db_session = _workspace_db(workspace=None)
        client = self._client(db_session)
        with patch("api.workspace_routes.WorkspaceSyncService") as MockSvc:
            resp = client.post(
                "/api/v1/workspaces/unified/ws-1/platforms",
                json={"workspace_id": "ws-1", "platform": "slack",
                      "platform_id": "S456"},
            )
        assert resp.status_code == 404

    def test_add_platform_value_error_404(self):
        db_session = _workspace_db(workspace=_workspace())
        client = self._client(db_session)
        with patch("api.workspace_routes.WorkspaceSyncService") as MockSvc:
            MockSvc.return_value.add_platform_to_workspace.side_effect = \
                ValueError("unknown platform")
            resp = client.post(
                "/api/v1/workspaces/unified/ws-1/platforms",
                json={"workspace_id": "ws-1", "platform": "slack",
                      "platform_id": "S456"},
            )
        assert resp.status_code == 404

    def test_add_platform_generic_error_500(self):
        db_session = _workspace_db(workspace=_workspace())
        client = self._client(db_session)
        with patch("api.workspace_routes.WorkspaceSyncService") as MockSvc:
            MockSvc.return_value.add_platform_to_workspace.side_effect = \
                RuntimeError("boom")
            resp = client.post(
                "/api/v1/workspaces/unified/ws-1/platforms",
                json={"workspace_id": "ws-1", "platform": "slack",
                      "platform_id": "S456"},
            )
        assert resp.status_code == 500

    def test_add_platform_cross_user_403(self):
        db_session = _workspace_db(workspace=_workspace(user_id="other"))
        client = self._client(db_session)
        with patch("api.workspace_routes.WorkspaceSyncService") as MockSvc:
            resp = client.post(
                "/api/v1/workspaces/unified/ws-1/platforms",
                json={"workspace_id": "ws-1", "platform": "slack",
                      "platform_id": "S456"},
            )
        assert resp.status_code == 403
        assert "Permission denied" in \
            resp.json()["detail"]["error"]["message"]

    # ---- propagate ----

    def test_propagate_changes_success(self):
        db_session = _workspace_db(workspace=_workspace())
        client = self._client(db_session)
        with patch("api.workspace_routes.WorkspaceSyncService") as MockSvc:
            MockSvc.return_value.propagate_change.return_value = {
                "status": "completed", "changed": 3}
            resp = client.post(
                "/api/v1/workspaces/unified/ws-1/sync",
                json={
                    "workspace_id": "ws-1",
                    "source_platform": "slack",
                    "change_type": "name_change",
                    "change_data": {"name": "New Name"},
                },
            )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "completed"
        assert resp.json()["message"] == "Change propagated to completed status"

    def test_propagate_changes_value_error_404(self):
        db_session = _workspace_db(workspace=_workspace())
        client = self._client(db_session)
        with patch("api.workspace_routes.WorkspaceSyncService") as MockSvc:
            MockSvc.return_value.propagate_change.side_effect = \
                ValueError("no workspace")
            resp = client.post(
                "/api/v1/workspaces/unified/ws-1/sync",
                json={
                    "workspace_id": "ws-1",
                    "source_platform": "slack",
                    "change_type": "member_add",
                    "change_data": {"member": "u1"},
                },
            )
        assert resp.status_code == 404

    def test_propagate_changes_workspace_not_found_404(self):
        db_session = _workspace_db(workspace=None)
        client = self._client(db_session)
        with patch("api.workspace_routes.WorkspaceSyncService") as MockSvc:
            resp = client.post(
                "/api/v1/workspaces/unified/ws-1/sync",
                json={
                    "workspace_id": "ws-1",
                    "source_platform": "slack",
                    "change_type": "member_add",
                    "change_data": {"member": "u1"},
                },
            )
        assert resp.status_code == 404

    def test_propagate_changes_generic_error_500(self):
        db_session = _workspace_db(workspace=_workspace())
        client = self._client(db_session)
        with patch("api.workspace_routes.WorkspaceSyncService") as MockSvc:
            MockSvc.return_value.propagate_change.side_effect = \
                RuntimeError("boom")
            resp = client.post(
                "/api/v1/workspaces/unified/ws-1/sync",
                json={
                    "workspace_id": "ws-1",
                    "source_platform": "slack",
                    "change_type": "member_add",
                    "change_data": {"member": "u1"},
                },
            )
        assert resp.status_code == 500

    # ---- get status ----

    def test_get_workspace_status_success(self):
        db_session = _workspace_db(workspace=_workspace())
        client = self._client(db_session)
        with patch("api.workspace_routes.WorkspaceSyncService") as MockSvc:
            MockSvc.return_value.get_workspace_sync_status.return_value = {
                "workspace_id": "ws-1", "status": "synced"}
            resp = client.get("/api/v1/workspaces/unified/ws-1")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "synced"

    def test_get_workspace_status_not_found_404(self):
        db_session = _workspace_db(workspace=None)
        client = self._client(db_session)
        with patch("api.workspace_routes.WorkspaceSyncService") as MockSvc:
            resp = client.get("/api/v1/workspaces/unified/ws-1")
        assert resp.status_code == 404

    def test_get_workspace_status_value_error_404(self):
        db_session = _workspace_db(workspace=_workspace())
        client = self._client(db_session)
        with patch("api.workspace_routes.WorkspaceSyncService") as MockSvc:
            MockSvc.return_value.get_workspace_sync_status.side_effect = \
                ValueError("no workspace")
            resp = client.get("/api/v1/workspaces/unified/ws-1")
        assert resp.status_code == 404

    def test_get_workspace_status_generic_error_500(self):
        db_session = _workspace_db(workspace=_workspace())
        client = self._client(db_session)
        with patch("api.workspace_routes.WorkspaceSyncService") as MockSvc:
            MockSvc.return_value.get_workspace_sync_status.side_effect = \
                RuntimeError("boom")
            resp = client.get("/api/v1/workspaces/unified/ws-1")
        assert resp.status_code == 500

    def test_get_workspace_status_cross_user_403(self):
        db_session = _workspace_db(workspace=_workspace(user_id="other"))
        client = self._client(db_session)
        with patch("api.workspace_routes.WorkspaceSyncService") as MockSvc:
            resp = client.get("/api/v1/workspaces/unified/ws-1")
        assert resp.status_code == 403

    # ---- list ----

    def test_list_workspaces_success(self):
        db_session = _workspace_db(all_workspaces=[_workspace(with_dates=True)])
        client = self._client(db_session)
        resp = client.get("/api/v1/workspaces/unified")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"][0]["id"] == "ws-1"
        assert body["data"][0]["last_sync_at"] is not None
        assert body["metadata"]["total"] == 1

    def test_list_workspaces_empty(self):
        db_session = _workspace_db(all_workspaces=[])
        client = self._client(db_session)
        resp = client.get("/api/v1/workspaces/unified")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_list_workspaces_generic_error_500(self):
        db_session = _workspace_db(all_workspaces=[])
        db_session.query = Mock(side_effect=RuntimeError("boom"))
        client = self._client(db_session)
        resp = client.get("/api/v1/workspaces/unified")
        assert resp.status_code == 500

    def test_list_workspaces_http_exception_passthrough(self):
        from fastapi import HTTPException
        db_session = _workspace_db(all_workspaces=[])
        db_session.query = Mock(
            side_effect=HTTPException(status_code=409, detail="conflict"))
        client = self._client(db_session)
        resp = client.get("/api/v1/workspaces/unified")
        assert resp.status_code == 409
        assert resp.json()["detail"] == "conflict"

    def test_list_workspaces_ignores_query_user(self):
        db_session = _workspace_db(all_workspaces=[_workspace()])
        client = self._client(db_session)
        resp = client.get("/api/v1/workspaces/unified?user_id=someone-else")
        assert resp.status_code == 200
        assert resp.json()["data"][0]["user_id"] == "test-user"

    # ---- delete ----

    def test_delete_workspace_success(self):
        db_session = _workspace_db(workspace=_workspace())
        client = self._client(db_session)
        resp = client.delete("/api/v1/workspaces/unified/ws-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["deleted_workspace_id"] == "ws-1"
        db_session.delete.assert_called_once()
        db_session.commit.assert_called_once()

    def test_delete_workspace_not_found_404(self):
        db_session = _workspace_db(workspace=None)
        client = self._client(db_session)
        resp = client.delete("/api/v1/workspaces/unified/ws-1")
        assert resp.status_code == 404

    def test_delete_workspace_cross_user_403(self):
        db_session = _workspace_db(workspace=_workspace(user_id="other"))
        client = self._client(db_session)
        resp = client.delete("/api/v1/workspaces/unified/ws-1")
        assert resp.status_code == 403

    def test_delete_workspace_generic_error_500(self):
        db_session = _workspace_db(workspace=_workspace())
        db_session.commit = Mock(side_effect=RuntimeError("boom"))
        client = self._client(db_session)
        resp = client.delete("/api/v1/workspaces/unified/ws-1")
        assert resp.status_code == 500

    # ---- _workspace_to_dict None-date branches ----

    def test_workspace_to_dict_none_dates(self):
        db_session = _workspace_db(
            all_workspaces=[_workspace(with_dates=False)])
        client = self._client(db_session)
        resp = client.get("/api/v1/workspaces/unified")
        assert resp.status_code == 200
        item = resp.json()["data"][0]
        assert item["last_sync_at"] is None
        assert item["created_at"] is None
        assert item["updated_at"] is None


# ============================================================================
# api/ab_testing.py
# ============================================================================

class _FakeABTestingService:
    """Stand-in for ABTestingService with per-test results."""

    def __init__(self, db=None, create=None, start=None, complete=None,
                 assign=None, record=None, results=None, tests=None):
        self.db = db
        self.create = create or {"test_id": "t-1"}
        self.start = start or {"test_id": "t-1", "status": "running"}
        self.complete = complete or {"test_id": "t-1", "winner": "A"}
        self.assign = assign or {"variant": "A"}
        self.record = record or {"recorded": True}
        self.results = results or {"test_id": "t-1", "winner": "A"}
        self.tests = tests if tests is not None else [{"test_id": "t-1"}]

    def create_test(self, **kwargs):
        return self.create

    def start_test(self, test_id):
        return self.start

    def complete_test(self, test_id):
        return self.complete

    def assign_variant(self, test_id, user_id, session_id):
        return self.assign

    def record_metric(self, test_id, user_id, success, metric_value, metadata):
        return self.record

    def get_test_results(self, test_id):
        return self.results

    def list_tests(self, agent_id, status, limit):
        return self.tests


class TestABTestingRoutes:
    """Coverage: api/ab_testing.py"""

    def _client(self, db_session):
        return _make_client(ab_testing_router, db_session)

    def _payload(self, **overrides):
        payload = {
            "name": "Test 1",
            "test_type": "prompt",
            "agent_id": "agent-1",
            "variant_a_config": {"prompt": "A"},
            "variant_b_config": {"prompt": "B"},
            "primary_metric": "success_rate",
            "variant_a_name": "Control",
            "variant_b_name": "Treatment",
            "description": "desc",
            "traffic_percentage": 0.5,
            "min_sample_size": 100,
            "confidence_level": 0.95,
            "secondary_metrics": ["latency"],
        }
        payload.update(overrides)
        return payload

    # ---- create ----

    def test_create_test_success(self):
        db_session = _empty_db_session()
        client = self._client(db_session)
        fake = _FakeABTestingService(db=db_session)
        with patch("api.ab_testing.ABTestingService", return_value=fake):
            resp = client.post("/api/ab-tests/create", json=self._payload())
        assert resp.status_code == 200
        assert resp.json()["data"]["test_id"] == "t-1"

    def test_create_test_error_400(self):
        db_session = _empty_db_session()
        client = self._client(db_session)
        fake = _FakeABTestingService(db=db_session,
                                     create={"error": "test_type invalid"})
        with patch("api.ab_testing.ABTestingService", return_value=fake):
            resp = client.post("/api/ab-tests/create", json=self._payload())
        assert resp.status_code == 400
        assert resp.json()["detail"]["success"] is False

    def test_create_test_missing_fields_422(self):
        db_session = _empty_db_session()
        client = self._client(db_session)
        resp = client.post("/api/ab-tests/create", json={"name": "x"})
        assert resp.status_code == 422

    # ---- start ----

    def test_start_test_success(self):
        db_session = _empty_db_session()
        client = self._client(db_session)
        fake = _FakeABTestingService(db=db_session)
        with patch("api.ab_testing.ABTestingService", return_value=fake):
            resp = client.post("/api/ab-tests/t-1/start")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "running"

    def test_start_test_error_400(self):
        db_session = _empty_db_session()
        client = self._client(db_session)
        fake = _FakeABTestingService(db=db_session,
                                     start={"error": "already running"})
        with patch("api.ab_testing.ABTestingService", return_value=fake):
            resp = client.post("/api/ab-tests/t-1/start")
        assert resp.status_code == 400

    # ---- complete ----

    def test_complete_test_success(self):
        db_session = _empty_db_session()
        client = self._client(db_session)
        fake = _FakeABTestingService(db=db_session)
        with patch("api.ab_testing.ABTestingService", return_value=fake):
            resp = client.post("/api/ab-tests/t-1/complete")
        assert resp.status_code == 200
        assert resp.json()["data"]["winner"] == "A"

    def test_complete_test_error_400(self):
        db_session = _empty_db_session()
        client = self._client(db_session)
        fake = _FakeABTestingService(db=db_session,
                                     complete={"error": "not running"})
        with patch("api.ab_testing.ABTestingService", return_value=fake):
            resp = client.post("/api/ab-tests/t-1/complete")
        assert resp.status_code == 400

    # ---- assign ----

    def test_assign_variant_success(self):
        db_session = _empty_db_session()
        client = self._client(db_session)
        fake = _FakeABTestingService(db=db_session)
        with patch("api.ab_testing.ABTestingService", return_value=fake):
            resp = client.post(
                "/api/ab-tests/t-1/assign",
                json={"user_id": "u-1", "session_id": "s-1"},
            )
        assert resp.status_code == 200
        assert resp.json()["data"]["variant"] == "A"

    def test_assign_variant_without_session(self):
        db_session = _empty_db_session()
        client = self._client(db_session)
        fake = _FakeABTestingService(db=db_session)
        with patch("api.ab_testing.ABTestingService", return_value=fake):
            resp = client.post(
                "/api/ab-tests/t-1/assign", json={"user_id": "u-1"}
            )
        assert resp.status_code == 200

    def test_assign_variant_error_400(self):
        db_session = _empty_db_session()
        client = self._client(db_session)
        fake = _FakeABTestingService(db=db_session,
                                     assign={"error": "test not running"})
        with patch("api.ab_testing.ABTestingService", return_value=fake):
            resp = client.post(
                "/api/ab-tests/t-1/assign", json={"user_id": "u-1"}
            )
        assert resp.status_code == 400

    def test_assign_variant_missing_user_422(self):
        db_session = _empty_db_session()
        client = self._client(db_session)
        resp = client.post("/api/ab-tests/t-1/assign", json={})
        assert resp.status_code == 422

    # ---- record ----

    def test_record_metric_success(self):
        db_session = _empty_db_session()
        client = self._client(db_session)
        fake = _FakeABTestingService(db=db_session)
        with patch("api.ab_testing.ABTestingService", return_value=fake):
            resp = client.post(
                "/api/ab-tests/t-1/record",
                json={"user_id": "u-1", "success": True,
                      "metric_value": 0.9, "metadata": {"a": 1}},
            )
        assert resp.status_code == 200
        assert resp.json()["data"]["recorded"] is True

    def test_record_metric_minimal(self):
        db_session = _empty_db_session()
        client = self._client(db_session)
        fake = _FakeABTestingService(db=db_session)
        with patch("api.ab_testing.ABTestingService", return_value=fake):
            resp = client.post(
                "/api/ab-tests/t-1/record", json={"user_id": "u-1"}
            )
        assert resp.status_code == 200

    def test_record_metric_error_400(self):
        db_session = _empty_db_session()
        client = self._client(db_session)
        fake = _FakeABTestingService(db=db_session,
                                     record={"error": "bad metric"})
        with patch("api.ab_testing.ABTestingService", return_value=fake):
            resp = client.post(
                "/api/ab-tests/t-1/record", json={"user_id": "u-1"}
            )
        assert resp.status_code == 400

    # ---- results ----

    def test_get_test_results_success(self):
        db_session = _empty_db_session()
        client = self._client(db_session)
        fake = _FakeABTestingService(db=db_session)
        with patch("api.ab_testing.ABTestingService", return_value=fake):
            resp = client.get("/api/ab-tests/t-1/results")
        assert resp.status_code == 200
        assert resp.json()["data"]["winner"] == "A"

    def test_get_test_results_error_404(self):
        db_session = _empty_db_session()
        client = self._client(db_session)
        fake = _FakeABTestingService(db=db_session,
                                     results={"error": "not found"})
        with patch("api.ab_testing.ABTestingService", return_value=fake):
            resp = client.get("/api/ab-tests/t-1/results")
        assert resp.status_code == 404
        assert resp.json()["detail"]["success"] is False

    # ---- list ----

    def test_list_tests_default(self):
        db_session = _empty_db_session()
        client = self._client(db_session)
        fake = _FakeABTestingService(db=db_session)
        with patch("api.ab_testing.ABTestingService", return_value=fake):
            resp = client.get("/api/ab-tests")
        assert resp.status_code == 200
        assert resp.json()[0]["test_id"] == "t-1"

    def test_list_tests_with_filters(self):
        db_session = _empty_db_session()
        client = self._client(db_session)
        fake = _FakeABTestingService(db=db_session)
        fake.list_tests = Mock(return_value=[{"test_id": "t-1"}])
        with patch("api.ab_testing.ABTestingService", return_value=fake):
            resp = client.get(
                "/api/ab-tests?agent_id=agent-1&status=running&limit=25"
            )
        assert resp.status_code == 200
        fake.list_tests.assert_called_once_with(
            agent_id="agent-1", status="running", limit=25)
        assert resp.json() == [{"test_id": "t-1"}]

    def test_list_tests_invalid_limit_422(self):
        db_session = _empty_db_session()
        client = self._client(db_session)
        fake = _FakeABTestingService(db=db_session)
        with patch("api.ab_testing.ABTestingService", return_value=fake):
            resp = client.get("/api/ab-tests?limit=0")
        assert resp.status_code == 422
