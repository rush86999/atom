"""Coverage wave 90 — api/shell_routes.py (56% → 95%+).

Sensitive surface: /api/shell/execute runs host commands. Tests pin the
governance flow (validate-command gate BEFORE execution, service-level
maturity/whitelist gate via mocked host_shell_service) and every error
branch: invalid command 403, PermissionError 403, ValueError 400,
generic 500 with no str(e) leak. Sessions/validate auth-verified (401).
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.shell_routes as sr
from core.auth import get_current_user


class FakeUser:
    id = "u-1"


@pytest.fixture
def mock_service():
    svc = MagicMock()
    svc.validate_command.return_value = {"valid": True}
    svc.execute_shell_command = AsyncMock(return_value={
        "exit_code": 0,
        "stdout": "ok",
        "stderr": "",
        "timed_out": False,
        "session_id": "s1",
        "duration_seconds": 0.1,
    })
    return svc


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def client(mock_service, mock_db):
    app = FastAPI()
    app.include_router(sr.router)
    app.dependency_overrides[get_current_user] = lambda: FakeUser()
    app.dependency_overrides[sr.get_db] = lambda: mock_db
    with patch.object(sr, "host_shell_service", mock_service):
        yield TestClient(app)
    app.dependency_overrides = {}


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(sr.router)
    yield TestClient(app)
    app.dependency_overrides = {}


EXEC = "/api/shell/execute?agent_id=a1"


class TestExecuteAuth:
    def test_execute_requires_auth(self, anon_client):
        assert anon_client.post(EXEC, json={"command": "ls"}).status_code == 401


class TestExecute:
    def test_execute_success(self, client, mock_service):
        resp = client.post(EXEC, json={"command": "ls -la", "timeout": 30})
        assert resp.status_code == 200
        body = resp.json()
        assert body["exit_code"] == 0
        assert body["stdout"] == "ok"
        assert body["session_id"] == "s1"
        mock_service.validate_command.assert_called_once_with("ls -la")
        mock_service.execute_shell_command.assert_awaited_once()

    def test_execute_with_working_directory(self, client, mock_service):
        resp = client.post(
            EXEC, json={"command": "pwd", "working_directory": "/tmp"}
        )
        assert resp.status_code == 200
        kwargs = mock_service.execute_shell_command.await_args.kwargs
        assert kwargs["working_directory"] == "/tmp"
        assert kwargs["agent_id"] == "a1"
        assert kwargs["user_id"] == "u-1"

    def test_execute_validation_gate_rejects_blocked_command(self, client, mock_service):
        """Command never reaches execution when the whitelist gate fails."""
        mock_service.validate_command.return_value = {
            "valid": False,
            "reason": "blocked",
            "allowed_commands": ["ls", "cat"],
        }
        resp = client.post(EXEC, json={"command": "rm -rf /"})
        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert detail["reason"] == "blocked"
        assert "ls" in detail["allowed_commands"]
        mock_service.execute_shell_command.assert_not_awaited()

    def test_execute_missing_agent_id_422(self, client):
        resp = client.post("/api/shell/execute", json={"command": "ls"})
        assert resp.status_code == 422

    def test_execute_missing_command_422(self, client):
        resp = client.post(EXEC, json={})
        assert resp.status_code == 422

    def test_execute_timeout_bounds_422(self, client):
        resp = client.post(EXEC, json={"command": "ls", "timeout": 0})
        assert resp.status_code == 422
        resp = client.post(EXEC, json={"command": "ls", "timeout": 601})
        assert resp.status_code == 422

    def test_execute_permission_error_403(self, client, mock_service):
        mock_service.execute_shell_command.side_effect = PermissionError("denied")
        resp = client.post(EXEC, json={"command": "sudo rm"})
        assert resp.status_code == 403
        assert "Permission denied" == resp.json()["detail"]

    def test_execute_value_error_400(self, client, mock_service):
        mock_service.execute_shell_command.side_effect = ValueError("bad dir")
        resp = client.post(EXEC, json={"command": "ls", "working_directory": "/etc/../../.."})
        assert resp.status_code == 400
        assert "Invalid request" == resp.json()["detail"]

    def test_execute_generic_error_500_no_leak(self, client, mock_service):
        mock_service.execute_shell_command.side_effect = RuntimeError("secret internal detail")
        resp = client.post(EXEC, json={"command": "ls"})
        assert resp.status_code == 500
        assert "Shell execution failed" == resp.json()["detail"]
        assert "secret internal detail" not in resp.text


def _session(sid="s1"):
    s = MagicMock()
    s.id = sid
    s.agent_id = "a1"
    s.command = "ls"
    s.exit_code = 0
    s.timed_out = False
    s.started_at = None
    s.duration_seconds = 0.5
    return s


class TestSessions:
    def test_sessions_require_auth(self, anon_client):
        assert anon_client.get("/api/shell/sessions").status_code == 401

    def test_sessions_scoped_to_user(self, client, mock_db):
        q = MagicMock()
        f = MagicMock()
        f.all.return_value = [_session()]
        f.order_by.return_value = f
        f.limit.return_value = f
        q.filter.return_value = f
        mock_db.query.return_value = q
        resp = client.get("/api/shell/sessions")
        assert resp.status_code == 200
        body = resp.json()["sessions"]
        assert len(body) == 1
        assert body[0]["id"] == "s1"
        assert body[0]["started_at"] is None
        assert mock_db.query.call_args[0][0] is sr.ShellSession
        assert str(q.filter.call_args[0][0]) == "shell_sessions.user_id = :user_id_1"

    def test_sessions_filter_by_agent(self, client, mock_db):
        q = MagicMock()
        f = MagicMock()
        f.all.return_value = []
        f.order_by.return_value = f
        f.limit.return_value = f
        f.filter.return_value = f
        q.filter.return_value = f
        mock_db.query.return_value = q
        resp = client.get("/api/shell/sessions?agent_id=a1&limit=10")
        assert resp.status_code == 200
        assert resp.json()["sessions"] == []
        assert f.filter.call_count >= 1
        assert str(f.filter.call_args[0][0]) == "shell_sessions.agent_id = :agent_id_1"
        assert f.limit.call_args[0][0] == 10


class TestValidate:
    def test_validate_requires_auth(self, anon_client):
        assert anon_client.get("/api/shell/validate", params={"command": "ls"}).status_code == 401

    def test_validate_returns_whitelist_result(self, client, mock_service):
        mock_service.validate_command.return_value = {
            "valid": True, "command": "ls", "whitelisted": True,
        }
        resp = client.get("/api/shell/validate", params={"command": "ls"})
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_validate_reports_blocked(self, client, mock_service):
        mock_service.validate_command.return_value = {
            "valid": False, "command": "rm", "blocked": True,
        }
        resp = client.get("/api/shell/validate", params={"command": "rm -rf /"})
        assert resp.status_code == 200
        assert resp.json()["blocked"] is True
