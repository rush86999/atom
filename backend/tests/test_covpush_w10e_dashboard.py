"""Coverage wave 10e — api/agent_guidance_routes + api/dashboard_data_routes (TDD).

Real-bug probes:
- WF1: ``agent_guidance_routes`` uses ``get_current_user`` from
  ``core.security_dependencies`` — verify consistent with how tests/other
  routes override auth (if the module's dependency differs from core.auth,
  cross-route overrides may not apply).
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.database import get_db

USER = SimpleNamespace(id="u-1")


@pytest.fixture
def fresh_db():
    """Isolated temp-file SQLite DB per test (never touches worker DB)."""
    import os
    import tempfile
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.database import Base

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    os.unlink(path)


def _app(router):
    app = FastAPI()
    app.include_router(router)
    return app


def _client(router, db):
    app = _app(router)
    from api.agent_guidance_routes import get_current_user as agu
    from api.dashboard_data_routes import get_current_user as ddu

    for dep in (agu, ddu):
        app.dependency_overrides[dep] = lambda: USER
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


# =========================================================================== #
# agent_guidance_routes
# =========================================================================== #
class TestAgentGuidanceRoutes:
    def _c(self, db=None):
        from api.agent_guidance_routes import router

        return _client(router, db or MagicMock())

    @pytest.fixture
    def sys(self):
        """Patch the 4 guidance-system factories with AsyncMocks."""
        guidance = AsyncMock()
        coordinator = AsyncMock()
        error_engine = AsyncMock()
        request_manager = AsyncMock()
        with patch("api.agent_guidance_routes.get_agent_guidance_system", return_value=guidance), \
             patch("api.agent_guidance_routes.get_view_coordinator", return_value=coordinator), \
             patch("api.agent_guidance_routes.get_error_guidance_engine", return_value=error_engine), \
             patch("api.agent_guidance_routes.get_agent_request_manager", return_value=request_manager):
            yield {
                "guidance": guidance,
                "coordinator": coordinator,
                "error_engine": error_engine,
                "request_manager": request_manager,
            }

    def test_start_operation(self, sys):
        guidance = sys["guidance"]
        guidance.start_operation.return_value = "op-1"
        r = self._c().post("/api/agent-guidance/operation/start", json={
            "agent_id": "a-1", "operation_type": "analysis", "context": {"k": "v"},
            "total_steps": 3, "metadata": {"m": 1},
        })
        assert r.status_code == 200
        assert r.json()["data"]["operation_id"] == "op-1"
        kwargs = guidance.start_operation.await_args.kwargs
        assert kwargs["user_id"] == "u-1"
        assert kwargs["agent_id"] == "a-1"
        assert kwargs["total_steps"] == 3

    def test_start_operation_error_500(self, sys):
        sys["guidance"].start_operation.side_effect = RuntimeError("boom")
        r = self._c().post("/api/agent-guidance/operation/start", json={
            "agent_id": "a-1", "operation_type": "analysis", "context": {},
        })
        assert r.status_code == 500

    def test_update_operation_step_and_context(self, sys):
        guidance = sys["guidance"]
        r = self._c().put("/api/agent-guidance/operation/op-1/update", json={
            "step": "step-2", "progress": 50, "add_log": {"msg": "hi"},
            "what": "doing", "why": "because", "next_steps": "more",
        })
        assert r.status_code == 200
        guidance.update_step.assert_awaited_once()
        guidance.update_context.assert_awaited_once()
        assert guidance.update_step.await_args.kwargs["operation_id"] == "op-1"
        assert guidance.update_context.await_args.kwargs["what"] == "doing"

    def test_update_operation_no_fields_skips_calls(self, sys):
        guidance = sys["guidance"]
        r = self._c().put("/api/agent-guidance/operation/op-1/update", json={})
        assert r.status_code == 200
        guidance.update_step.assert_not_awaited()
        guidance.update_context.assert_not_awaited()

    def test_update_operation_error_500(self, sys):
        sys["guidance"].update_step.side_effect = RuntimeError("boom")
        r = self._c().put("/api/agent-guidance/operation/op-1/update", json={"step": "s"})
        assert r.status_code == 500

    def test_complete_operation(self, sys):
        guidance = sys["guidance"]
        r = self._c().post("/api/agent-guidance/operation/op-1/complete", json={
            "status": "failed", "final_message": "oops",
        })
        assert r.status_code == 200
        kwargs = guidance.complete_operation.await_args.kwargs
        assert kwargs["operation_id"] == "op-1"
        assert kwargs["status"] == "failed"

    def test_complete_operation_error_500(self, sys):
        sys["guidance"].complete_operation.side_effect = RuntimeError("boom")
        r = self._c().post("/api/agent-guidance/operation/op-1/complete", json={})
        assert r.status_code == 500

    def test_get_operation_found(self):
        from core.models import AgentOperationTracker

        op = MagicMock(spec=AgentOperationTracker)
        op.operation_id = "op-1"
        op.agent_id = "a-1"
        op.operation_type = "analysis"
        op.status = "running"
        op.current_step = "s1"
        op.total_steps = 3
        op.current_step_index = 1
        op.progress = 33
        op.what_explanation = "w"
        op.why_explanation = "y"
        op.next_steps = "n"
        op.logs = []
        op.operation_metadata = {}
        op.started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        op.completed_at = None
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = op
        r = self._c(db).get("/api/agent-guidance/operation/op-1")
        assert r.status_code == 200
        body = r.json()["data"]["operation"]
        assert body["operation_id"] == "op-1"
        assert body["context"] == {"what": "w", "why": "y", "next": "n"}
        assert body["started_at"] is not None
        assert body["completed_at"] is None

    def test_get_operation_missing_404(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._c(db).get("/api/agent-guidance/operation/ghost")
        assert r.status_code == 404

    def test_get_operation_error_500(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        r = self._c(db).get("/api/agent-guidance/operation/op-1")
        assert r.status_code == 500

    def test_switch_view_browser(self, sys):
        coordinator = sys["coordinator"]
        r = self._c().post("/api/agent-guidance/view/switch", json={
            "agent_id": "a-1", "view_type": "browser", "url": "https://x", "guidance": "g",
        })
        assert r.status_code == 200
        coordinator.switch_to_browser_view.assert_awaited_once()
        assert coordinator.switch_to_browser_view.await_args.kwargs["url"] == "https://x"

    def test_switch_view_browser_missing_url_422(self, sys):
        r = self._c().post("/api/agent-guidance/view/switch", json={
            "agent_id": "a-1", "view_type": "browser", "guidance": "g",
        })
        assert r.status_code == 422

    def test_switch_view_terminal(self, sys):
        coordinator = sys["coordinator"]
        r = self._c().post("/api/agent-guidance/view/switch", json={
            "agent_id": "a-1", "view_type": "terminal", "command": "ls", "guidance": "g",
        })
        assert r.status_code == 200
        coordinator.switch_to_terminal_view.assert_awaited_once()
        assert coordinator.switch_to_terminal_view.await_args.kwargs["command"] == "ls"

    def test_switch_view_unknown_type_422(self, sys):
        r = self._c().post("/api/agent-guidance/view/switch", json={
            "agent_id": "a-1", "view_type": "holodeck", "guidance": "g",
        })
        assert r.status_code == 422

    def test_switch_view_error_500(self, sys):
        sys["coordinator"].switch_to_browser_view.side_effect = RuntimeError("boom")
        r = self._c().post("/api/agent-guidance/view/switch", json={
            "agent_id": "a-1", "view_type": "browser", "url": "https://x", "guidance": "g",
        })
        assert r.status_code == 500

    def test_set_layout(self, sys):
        coordinator = sys["coordinator"]
        r = self._c().post("/api/agent-guidance/view/layout", json={
            "layout": "split_horizontal", "session_id": "s-1",
        })
        assert r.status_code == 200
        coordinator.set_layout.assert_awaited_once_with(
            user_id="u-1", layout="split_horizontal", session_id="s-1"
        )

    def test_set_layout_error_500(self, sys):
        sys["coordinator"].set_layout.side_effect = RuntimeError("boom")
        r = self._c().post("/api/agent-guidance/view/layout", json={"layout": "tabs"})
        assert r.status_code == 500

    def test_present_error(self, sys):
        error_engine = sys["error_engine"]
        r = self._c().post("/api/agent-guidance/error/present", json={
            "operation_id": "op-1", "error": {"type": "timeout"}, "agent_id": "a-1",
        })
        assert r.status_code == 200
        kwargs = error_engine.present_error.await_args.kwargs
        assert kwargs["error"] == {"type": "timeout"}
        assert kwargs["agent_id"] == "a-1"

    def test_present_error_500(self, sys):
        sys["error_engine"].present_error.side_effect = RuntimeError("boom")
        r = self._c().post("/api/agent-guidance/error/present", json={
            "operation_id": "op-1", "error": {},
        })
        assert r.status_code == 500

    def test_track_resolution(self, sys):
        error_engine = sys["error_engine"]
        r = self._c().post("/api/agent-guidance/error/track-resolution", json={
            "error_type": "timeout", "error_code": "E1", "resolution_attempted": "retry",
            "success": True, "user_feedback": "worked", "agent_suggested": False,
        })
        assert r.status_code == 200
        kwargs = error_engine.track_resolution.await_args.kwargs
        assert kwargs["success"] is True
        assert kwargs["agent_suggested"] is False

    def test_create_permission_request(self, sys):
        rm = sys["request_manager"]
        rm.create_permission_request.return_value = "req-1"
        r = self._c().post("/api/agent-guidance/request/permission", json={
            "agent_id": "a-1", "title": "Access DB", "permission": "db.read",
            "context": {"table": "x"}, "urgency": "high", "expires_in": 300,
        })
        assert r.status_code == 200
        assert r.json()["data"]["request_id"] == "req-1"
        assert rm.create_permission_request.await_args.kwargs["urgency"] == "high"

    def test_create_decision_request(self, sys):
        rm = sys["request_manager"]
        rm.create_decision_request.return_value = "req-2"
        r = self._c().post("/api/agent-guidance/request/decision", json={
            "agent_id": "a-1", "title": "Which?", "explanation": "expl",
            "options": ["a", "b"], "context": {}, "suggested_option": 1,
        })
        assert r.status_code == 200
        kwargs = rm.create_decision_request.await_args.kwargs
        assert kwargs["options"] == ["a", "b"]
        assert kwargs["suggested_option"] == 1

    def test_respond_to_request(self, sys):
        rm = sys["request_manager"]
        r = self._c().post("/api/agent-guidance/request/req-1/respond", json={
            "request_id": "req-1", "response": {"approve": True},
        })
        assert r.status_code == 200
        rm.handle_response.assert_awaited_once_with(
            user_id="u-1", request_id="req-1", response={"approve": True}
        )

    def test_get_request_found_and_missing(self):
        from core.models import AgentRequestLog

        log = MagicMock(spec=AgentRequestLog)
        log.request_id = "req-1"
        log.agent_id = "a-1"
        log.request_type = "permission"
        log.request_data = {"p": 1}
        log.user_response = None
        log.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        log.responded_at = None
        log.expires_at = None
        log.revoked = False
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = log
        r = self._c(db).get("/api/agent-guidance/request/req-1")
        assert r.status_code == 200
        body = r.json()["data"]["request"]
        assert body["request_type"] == "permission"
        assert body["revoked"] is False

        db2 = MagicMock()
        db2.query.return_value.filter.return_value.first.return_value = None
        r2 = self._c(db2).get("/api/agent-guidance/request/ghost")
        assert r2.status_code == 404

    def test_requires_auth(self):
        from api.agent_guidance_routes import router

        client = TestClient(_app(router), raise_server_exceptions=False)
        assert client.get("/api/agent-guidance/operation/op-1").status_code == 401
        assert client.post(
            "/api/agent-guidance/operation/start",
            json={"agent_id": "a", "operation_type": "t", "context": {}},
        ).status_code == 401


# =========================================================================== #
# dashboard_data_routes
# =========================================================================== #
class TestDashboardDataRoutes:
    def _c(self, db=None):
        from api.dashboard_data_routes import router

        return _client(router, db or MagicMock())

    def _seed(self, db):
        import uuid as _uuid
        from core.models import AgentJob, AuditLog, WorkflowExecution, User

        # clear prior runs' rows (shared worker DB)
        db.query(AgentJob).delete()
        db.query(AuditLog).delete()
        db.query(WorkflowExecution).delete()
        db.query(User).delete()
        db.commit()

        # unique id+email per test run (UNIQUE columns, worker DB shared)
        uid = f"u-{_uuid.uuid4().hex[:8]}"
        user = User(id=uid, email=f"{uid}@t.com",
                    first_name="A", last_name="B", role="user", status="active",
                    tenant_id="t-1")
        db.add(user)
        db.commit()
        now = datetime(2026, 1, 5, tzinfo=timezone.utc)
        db.add(WorkflowExecution(
            execution_id=f"wf-exec-{_uuid.uuid4().hex[:8]}-1", workflow_id="wf-1", status="completed",
            user_id=uid, created_at=now, updated_at=now, input_data="input",
        ))
        db.add(WorkflowExecution(
            execution_id=f"wf-exec-{_uuid.uuid4().hex[:8]}-2", workflow_id="wf-2", status="failed",
            user_id=uid, created_at=now - timedelta(days=1), input_data=None,
        ))
        db.add(AgentJob(
            id=f"job-{_uuid.uuid4().hex[:8]}", agent_id="a-1", status="success",
            start_time=now - timedelta(hours=2), end_time=now - timedelta(hours=1),
            result_summary="done", tenant_id="t-1",
        ))
        db.add(AuditLog(
            id=f"audit-{_uuid.uuid4().hex[:8]}", event_type="login", threat_level="low", security_level="low",
            action="login", description="user login", user_id=uid,
            user_email=f"{uid}@t.com", timestamp=now, tenant_id="t-1",
            success=True,
        ))
        db.commit()

    def test_dashboard_data(self, fresh_db):
        from api.dashboard_data_routes import router

        db = fresh_db
        self._seed(db)
        r = self._c(db).get("/api/dashboard/data")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["stats"]["upcoming_events"] == 2
        events = body["data"]["calendar"]
        assert len(events) == 2
        assert events[0]["status"] == "confirmed"  # completed
        tasks = body["data"]["tasks"]
        assert any(t["title"] == "Agent Job: a-1" for t in tasks)
        assert any(t["priority"] == "high" for t in tasks)  # failed workflow
        messages = body["data"]["messages"]
        assert len(messages) >= 1
        assert messages[0]["platform"] == "system"

    def test_dashboard_stats(self, fresh_db):
        db = fresh_db
        self._seed(db)
        r = self._c(db).get("/api/dashboard/stats")
        assert r.status_code == 200
        stats = r.json()
        assert stats["upcoming_events"] == 2
        assert stats["overdue_tasks"] == 1
        assert stats["unread_messages"] >= 1

    def test_calendar_events(self, fresh_db):
        db = fresh_db
        self._seed(db)
        r = self._c(db).get("/api/dashboard/events?limit=5")
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_tasks_endpoint(self, fresh_db):
        db = fresh_db
        self._seed(db)
        r = self._c(db).get("/api/dashboard/tasks")
        assert r.status_code == 200
        assert len(r.json()) == 3  # 2 workflows + 1 job

    def test_messages_endpoint(self, fresh_db):
        db = fresh_db
        self._seed(db)
        r = self._c(db).get("/api/dashboard/messages")
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 1
        assert rows[0]["priority"] == "low"  # threat_level low

    def test_health_endpoint(self):
        r = self._c().get("/api/dashboard/health")
        assert r.status_code == 200
        body = r.json()
        assert body.get("status") == "healthy" and body.get("service") == "dashboard-data"

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

    def test_requires_auth(self):
        from api.dashboard_data_routes import router

        client = TestClient(_app(router), raise_server_exceptions=False)
        assert client.get("/api/dashboard/data").status_code == 401
        assert client.get("/api/dashboard/stats").status_code == 401


class TestDashboardBranches:
    def _c(self, db=None):
        from api.dashboard_data_routes import router

        return _client(router, db or MagicMock())

    def _seed(self, db):
        import uuid as _uuid
        from core.models import AgentJob, AuditLog, WorkflowExecution, User

        db.query(AgentJob).delete()
        db.query(AuditLog).delete()
        db.query(WorkflowExecution).delete()
        db.query(User).delete()
        db.commit()
        uid = "u-1"
        db.add(User(id=uid, email=f"u-1-{_uuid.uuid4().hex[:8]}@t.com",
                    first_name="A", last_name="B", role="user", status="active",
                    tenant_id="t-1"))
        now = datetime(2026, 1, 5, tzinfo=timezone.utc)
        db.add(WorkflowExecution(
            execution_id=f"wf-{_uuid.uuid4().hex[:8]}", workflow_id="wf-1",
            status="completed", user_id=uid, created_at=now, updated_at=now,
            input_data="input"))
        db.add(AgentJob(
            id=f"job-r-{_uuid.uuid4().hex[:8]}", agent_id="a-1", status="running",
            start_time=now - timedelta(hours=1), result_summary=None, tenant_id="t-1"))
        db.add(AgentJob(
            id=f"job-f-{_uuid.uuid4().hex[:8]}", agent_id="a-1", status="failed",
            start_time=now - timedelta(hours=2), end_time=now - timedelta(hours=1),
            result_summary="x", tenant_id="t-1"))
        db.add(AuditLog(
            id=f"aud-{_uuid.uuid4().hex[:8]}", event_type="anomaly", threat_level="critical",
            security_level="high", action="detect", description="x", user_id=uid,
            user_email=f"{uid}@t.com", timestamp=now, tenant_id="t-1", success=True))
        db.commit()
        return uid

    def test_helpers_without_user_filter(self, fresh_db):
        import api.dashboard_data_routes as ddr

        db = fresh_db
        self._seed(db)
        events = ddr.get_user_upcoming_events(db, None)
        assert len(events) == 1
        tasks = ddr.get_user_tasks(db, None)
        # running -> in-progress, failed -> high priority
        statuses = {t["status"] for t in tasks}
        assert "in-progress" in statuses
        assert "completed" in statuses
        prios = {t["priority"] for t in tasks}
        assert "high" in prios
        messages = ddr.get_user_messages(db, None)
        assert messages[0]["priority"] == "high"  # critical threat
        stats = ddr.calculate_dashboard_stats(db, None)
        assert stats["upcoming_events"] == 1
        assert stats["overdue_tasks"] == 0
        assert stats["unread_messages"] == 1

    def test_user_id_clamped_to_current(self, fresh_db):
        db = fresh_db
        self._seed(db)
        r = self._c(db).get("/api/dashboard/data?user_id=someone-else&limit=5")
        assert r.status_code == 200
        assert r.json()["stats"]["upcoming_events"] == 1  # still own data

    def test_data_limit_bounds(self):
        assert self._c().get("/api/dashboard/data?limit=0").status_code == 422
        assert self._c().get("/api/dashboard/data?limit=101").status_code == 422

    def test_endpoint_errors_degrade_gracefully(self):
        # helpers catch db errors internally -> endpoints stay 200 with empty data
        for path in ("/api/dashboard/data", "/api/dashboard/stats",
                     "/api/dashboard/events", "/api/dashboard/tasks",
                     "/api/dashboard/messages"):
            db = MagicMock()
            db.query.side_effect = RuntimeError("db down")
            r = self._c(db).get(path)
            assert r.status_code == 200, path

    def test_stats_missing_user_ok(self, fresh_db):
        db = fresh_db
        self._seed(db)
        r = self._c(db).get("/api/dashboard/stats")
        assert r.status_code == 200
        assert r.json()["upcoming_events"] == 1


class TestAgentGuidanceErrorBranches:
    def _c(self, db=None):
        from api.agent_guidance_routes import router

        return _client(router, db or MagicMock())

    def test_track_resolution_error_500(self):
        engine = AsyncMock()
        engine.track_resolution.side_effect = RuntimeError("boom")
        with patch("api.agent_guidance_routes.get_error_guidance_engine", return_value=engine):
            r = self._c().post("/api/agent-guidance/error/track-resolution", json={
                "error_type": "t", "resolution_attempted": "r", "success": True,
            })
        assert r.status_code == 500

    def test_permission_request_error_500(self):
        rm = AsyncMock()
        rm.create_permission_request.side_effect = RuntimeError("boom")
        with patch("api.agent_guidance_routes.get_agent_request_manager", return_value=rm):
            r = self._c().post("/api/agent-guidance/request/permission", json={
                "agent_id": "a", "title": "t", "permission": "p", "context": {},
            })
        assert r.status_code == 500

    def test_decision_request_error_500(self):
        rm = AsyncMock()
        rm.create_decision_request.side_effect = RuntimeError("boom")
        with patch("api.agent_guidance_routes.get_agent_request_manager", return_value=rm):
            r = self._c().post("/api/agent-guidance/request/decision", json={
                "agent_id": "a", "title": "t", "explanation": "e",
                "options": ["x"], "context": {},
            })
        assert r.status_code == 500

    def test_respond_error_500(self):
        rm = AsyncMock()
        rm.handle_response.side_effect = RuntimeError("boom")
        with patch("api.agent_guidance_routes.get_agent_request_manager", return_value=rm):
            r = self._c().post("/api/agent-guidance/request/r1/respond", json={
                "request_id": "r1", "response": {},
            })
        assert r.status_code == 500

    def test_get_request_error_500(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        r = self._c(db).get("/api/agent-guidance/request/r1")
        assert r.status_code == 500
