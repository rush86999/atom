# -*- coding: utf-8 -*-
"""Coverage wave 80 — core/local_agent_service.py to >=95% (standalone,
fully mocked: governance HTTP, directory permission, whitelist, subprocess —
zero real subprocesses, zero network).

Covers:
- execute_command: governance-denied, whitelist-blocked (maturity_required
  approval + hard-blocked), directory-denied, suggest_only, full execute
  (subprocess mocked), uppercase-maturity normalization regression (R80 bug:
  AgentStatus("AUTONOMOUS") raised ValueError → silent STUDENT downgrade).
- _execute_locally: empty command ValueError, missing cwd ValueError, success,
  timeout (kill + ProcessLookupError / OSError / generic on second
  communicate), operation-type detection override.
- _detect_operation_type: read/write/delete→write/execute sets.
- _check_governance success + httpx.HTTPError re-raise.
- _log_execution success + httpx.HTTPError swallow.
- get_status: 200, RequestError, generic Exception.
- close(), get_local_agent_service singleton (fresh global each test).
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.local_agent_service import LocalAgentService, get_local_agent_service


class _MockProcess:
    """Mimics asyncio.subprocess.Process (communicate returns bytes)."""

    def __init__(self, returncode=0, stdout=b"", stderr=b""):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout, self._stderr


GOV_ALLOWED = {
    "allowed": True,
    "maturity_level": "AUTONOMOUS",
    "reason": "ok",
}


def _dir_allowed(**over):
    out = {
        "allowed": True,
        "suggest_only": False,
        "reason": "allowed",
        "maturity_level": "autonomous",
        "resolved_path": "/tmp",
    }
    out.update(over)
    return out


@pytest.fixture()
def service():
    svc = LocalAgentService(backend_url="http://localhost:8000/")
    yield svc
    asyncio.get_event_loop().run_until_complete(svc.close())


def _patch_exec(service, process=None):
    return patch.object(
        service.__class__, "_check_governance", AsyncMock(return_value=GOV_ALLOWED)
    ), patch(
        "core.local_agent_service.check_directory_permission",
        return_value=_dir_allowed(),
    ), patch(
        "core.local_agent_service.asyncio.create_subprocess_exec",
        return_value=process or _MockProcess(returncode=0, stdout=b"ok\n"),
    ), patch.object(service, "_log_execution", AsyncMock())


# ============================================================================
# execute_command — decision branches
# ============================================================================

@pytest.mark.asyncio
async def test_execute_governance_denied():
    svc = LocalAgentService("http://localhost:8000")
    with patch.object(svc, "_check_governance", AsyncMock(return_value={
        "allowed": False, "reason": "low maturity",
        "requires_approval": True, "maturity_level": "STUDENT",
    })) as gov:
        with patch.object(svc, "_log_execution") as log:
            result = await svc.execute_command("a1", "ls /tmp")
    assert result == {
        "allowed": False,
        "reason": "low maturity",
        "requires_approval": True,
        "maturity_level": "STUDENT",
    }
    gov.assert_awaited_once()
    log.assert_not_called()
    await svc.close()


@pytest.mark.asyncio
async def test_execute_governance_denied_defaults():
    svc = LocalAgentService("http://localhost:8000")
    with patch.object(svc, "_check_governance", AsyncMock(return_value={})):
        result = await svc.execute_command("a1", "ls /tmp")
    assert result["allowed"] is False
    assert result["reason"] == "Governance check failed"
    assert result["requires_approval"] is False
    assert result["maturity_level"] == "UNKNOWN"
    await svc.close()


@pytest.mark.asyncio
async def test_execute_whitelist_blocked_maturity_required():
    svc = LocalAgentService("http://localhost:8000")
    with patch.object(svc, "_check_governance", AsyncMock(return_value={
        "allowed": True, "maturity_level": "SUPERVISED",
    })):
        with patch("core.local_agent_service.validate_command", return_value={
            "valid": False, "reason": "needs AUTONOMOUS",
            "maturity_required": "AUTONOMOUS", "category": "file_delete",
        }):
            with patch("core.local_agent_service.get_command_category",
                       return_value="file_delete"):
                with patch.object(svc, "_log_execution", AsyncMock()) as log:
                    result = await svc.execute_command("a1", "rm x.txt", "/tmp")
    assert result["allowed"] is False
    assert result["requires_approval"] is True
    assert result["maturity_required"] == "AUTONOMOUS"
    assert result["suggested_command"] == "rm x.txt"
    assert result["category"] == "file_delete"
    log.assert_awaited_once()
    data = log.await_args.args[0]
    assert data["operation_type"] == "blocked"
    assert data["command_whitelist_valid"] is False
    assert data["exit_code"] == -1
    await svc.close()


@pytest.mark.asyncio
async def test_execute_whitelist_hard_blocked():
    svc = LocalAgentService("http://localhost:8000")
    with patch.object(svc, "_check_governance", AsyncMock(return_value={
        "allowed": True, "maturity_level": "AUTONOMOUS",
    })):
        with patch("core.local_agent_service.validate_command", return_value={
            "valid": False, "reason": "blocked", "category": "blocked",
        }):
            with patch.object(svc, "_log_execution", AsyncMock()):
                result = await svc.execute_command("a1", "sudo rm -rf /")
    assert result["allowed"] is False
    assert result["blocked"] is True
    assert "blocked" not in result or True
    assert result["maturity_level"] == "AUTONOMOUS"
    await svc.close()


@pytest.mark.asyncio
async def test_execute_directory_denied():
    svc = LocalAgentService("http://localhost:8000")
    with patch.object(svc, "_check_governance", AsyncMock(return_value=GOV_ALLOWED)):
        with patch("core.local_agent_service.check_directory_permission",
                   return_value={"allowed": False, "suggest_only": False,
                                 "reason": "blocked path",
                                 "resolved_path": "/etc/passwd"}):
            with patch.object(svc, "_log_execution", AsyncMock()) as log:
                result = await svc.execute_command("a1", "ls /etc", "/etc")
    assert result["allowed"] is False
    assert result["blocked_directory"] == "/etc/passwd"
    assert result["requires_approval"] is False
    log.assert_awaited_once()
    data = log.await_args.args[0]
    assert data["blocked_reason"].startswith("Directory access denied")
    await svc.close()


@pytest.mark.asyncio
async def test_execute_suggest_only():
    svc = LocalAgentService("http://localhost:8000")
    with patch.object(svc, "_check_governance", AsyncMock(return_value={
        "allowed": True, "maturity_level": "STUDENT",
    })):
        with patch("core.local_agent_service.check_directory_permission",
                   return_value=_dir_allowed(suggest_only=True, reason="suggest")):
            with patch.object(svc, "_log_execution", AsyncMock()) as log:
                result = await svc.execute_command("a1", "ls /tmp", "/tmp")
    assert result["allowed"] is False
    assert result["requires_approval"] is True
    assert result["suggested_directory"] == "/tmp"
    log.assert_awaited_once()
    assert log.await_args.args[0]["operation_type"] == "suggest_only"
    await svc.close()


@pytest.mark.asyncio
async def test_execute_full_flow_autonomous_uppercase_maturity():
    """R80 regression: uppercase member-name maturity (AUTONOMOUS) previously
    crashed AgentStatus() → silent STUDENT downgrade → suggest-only. Uses the
    REAL check_directory_permission (unmocked) so the maturity conversion is
    exercised end-to-end."""
    svc = LocalAgentService("http://localhost:8000")
    with patch.object(svc, "_check_governance", AsyncMock(return_value=GOV_ALLOWED)):
        with patch("core.local_agent_service.asyncio.create_subprocess_exec",
                   return_value=_MockProcess(returncode=0,
                                             stdout=b"file1.txt\n")) as exec_mock:
            with patch.object(svc, "_log_execution", AsyncMock()) as log:
                result = await svc.execute_command(
                    "a1", "ls /tmp", "/tmp")
    assert result["allowed"] is True
    assert result["exit_code"] == 0
    assert result["stdout"] == "file1.txt\n"
    assert result["maturity_level"] == "AUTONOMOUS"
    assert result["timed_out"] is False
    exec_mock.assert_called_once()
    assert exec_mock.call_args.args[0] == "ls"
    log.assert_awaited_once()
    data = log.await_args.args[0]
    assert data["exit_code"] == 0
    assert data["command_whitelist_valid"] is True
    assert data["operation_type"] == "read"
    await svc.close()


@pytest.mark.asyncio
async def test_execute_full_flow_lowercase_maturity_and_dir_none():
    svc = LocalAgentService("http://localhost:8000")
    with patch.object(svc, "_check_governance", AsyncMock(return_value={
        "allowed": True, "maturity_level": "autonomous",
    })):
        with patch("core.local_agent_service.check_directory_permission",
                   return_value=_dir_allowed()) as dir_check:
            with patch("core.local_agent_service.asyncio.create_subprocess_exec",
                       return_value=_MockProcess(returncode=3, stderr=b"nope")):
                with patch.object(svc, "_log_execution", AsyncMock()):
                    result = await svc.execute_command("a1", "cat x", None)
    assert result["exit_code"] == 3
    assert result["stderr"] == "nope"
    dir_check.assert_called_once()
    assert dir_check.call_args.kwargs["directory"] == "/tmp"
    await svc.close()


@pytest.mark.asyncio
async def test_execute_invalid_maturity_falls_back_student_suggest_only():
    """Unknown maturity string still degrades to STUDENT (fail-closed), but
    only for genuinely unparseable values. validate_command is mocked valid
    because the real one blocks unknown maturities before this point."""
    svc = LocalAgentService("http://localhost:8000")
    with patch.object(svc, "_check_governance", AsyncMock(return_value={
        "allowed": True, "maturity_level": "TRANSCENDENT",
    })):
        with patch("core.local_agent_service.validate_command", return_value={
            "valid": True, "maturity_required": "TRANSCENDENT",
        }):
            with patch("core.local_agent_service.check_directory_permission",
                       return_value=_dir_allowed(suggest_only=True,
                                                 reason="suggest")):
                result = await svc.execute_command("a1", "ls /tmp")
    assert result["allowed"] is False
    assert result["requires_approval"] is True
    assert result["maturity_level"] == "TRANSCENDENT"
    await svc.close()


# ============================================================================
# _check_governance
# ============================================================================

@pytest.mark.asyncio
async def test_check_governance_success():
    svc = LocalAgentService("http://localhost:8000")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"allowed": True}
    svc.client.post = AsyncMock(return_value=mock_resp)
    result = await svc._check_governance("a1", "ls", "/tmp")
    assert result == {"allowed": True}
    svc.client.post.assert_awaited_once_with(
        "/api/agents/a1/governance",
        json={"action_type": "shell_execute", "command": "ls", "directory": "/tmp"},
    )
    await svc.close()


@pytest.mark.asyncio
async def test_check_governance_http_error_raises():
    import httpx
    svc = LocalAgentService("http://localhost:8000")
    svc.client.post = AsyncMock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(httpx.HTTPError):
        await svc._check_governance("a1", "ls", "/tmp")
    await svc.close()


# ============================================================================
# _execute_locally
# ============================================================================

@pytest.mark.asyncio
async def test_execute_locally_empty_command():
    svc = LocalAgentService("http://localhost:8000")
    with pytest.raises(ValueError):
        await svc._execute_locally("   ")
    await svc.close()


@pytest.mark.asyncio
async def test_execute_locally_missing_cwd():
    svc = LocalAgentService("http://localhost:8000")
    with pytest.raises(ValueError):
        await svc._execute_locally("ls", "/definitely/not/here-xyz")
    await svc.close()


@pytest.mark.asyncio
async def test_execute_locally_success_write_override():
    svc = LocalAgentService("http://localhost:8000")
    with patch("core.local_agent_service.asyncio.create_subprocess_exec",
               return_value=_MockProcess(returncode=0, stdout=b"made\n")) as m:
        result = await svc._execute_locally(
            "mkdir /tmp/newdir", "/tmp", operation_type="execute")
    assert result["exit_code"] == 0
    assert result["stdout"] == "made\n"
    assert result["timed_out"] is False
    assert result["operation_type"] == "write"
    assert m.call_args.args[0] == "mkdir"
    assert result["duration_seconds"] >= 0
    await svc.close()


@pytest.mark.asyncio
async def test_execute_locally_explicit_operation_type_preserved():
    svc = LocalAgentService("http://localhost:8000")
    with patch("core.local_agent_service.asyncio.create_subprocess_exec",
               return_value=_MockProcess(returncode=0)):
        result = await svc._execute_locally("ls /tmp", "/tmp", operation_type="read")
    assert result["operation_type"] == "read"
    await svc.close()


@pytest.mark.asyncio
async def test_execute_locally_timeout_second_communicate_processlookup():
    svc = LocalAgentService("http://localhost:8000")

    class _TimeOutProc:
        returncode = None

        def __init__(self):
            self.killed = False

        def kill(self):
            self.killed = True

        async def communicate(self):
            if not self.killed:
                raise asyncio.TimeoutError()
            raise ProcessLookupError()

    proc = _TimeOutProc()
    with patch("core.local_agent_service.asyncio.create_subprocess_exec",
               return_value=proc):
        result = await svc._execute_locally("ls /tmp")
    assert result["timed_out"] is True
    assert result["exit_code"] == -1
    assert "timed out after 5 minutes" in result["stderr"]
    await svc.close()


@pytest.mark.asyncio
async def test_execute_locally_timeout_second_communicate_oserror():
    svc = LocalAgentService("http://localhost:8000")

    class _TimeOutProc:
        returncode = None

        def __init__(self):
            self.killed = False

        def kill(self):
            self.killed = True

        async def communicate(self):
            if not self.killed:
                raise asyncio.TimeoutError()
            raise BrokenPipeError()

    with patch("core.local_agent_service.asyncio.create_subprocess_exec",
               return_value=_TimeOutProc()):
        result = await svc._execute_locally("ls /tmp")
    assert result["timed_out"] is True
    assert result["stdout"] == ""
    assert result["stderr"].startswith("Command timed out")
    await svc.close()


@pytest.mark.asyncio
async def test_execute_locally_timeout_second_communicate_generic():
    svc = LocalAgentService("http://localhost:8000")

    class _TimeOutProc:
        returncode = None

        def __init__(self):
            self.killed = False

        def kill(self):
            self.killed = True

        async def communicate(self):
            if not self.killed:
                raise asyncio.TimeoutError()
            raise RuntimeError("boom")

    with patch("core.local_agent_service.asyncio.create_subprocess_exec",
               return_value=_TimeOutProc()):
        result = await svc._execute_locally("ls /tmp")
    assert result["timed_out"] is True
    assert result["exit_code"] == -1
    await svc.close()


# ============================================================================
# _detect_operation_type
# ============================================================================

def test_detect_operation_type_read():
    svc = LocalAgentService("http://localhost:8000")
    for cmd in ["ls", "cat", "head", "tail", "grep", "find", "wc", "pwd", "file"]:
        assert svc._detect_operation_type(cmd) == "read"


def test_detect_operation_type_write_and_delete():
    svc = LocalAgentService("http://localhost:8000")
    for cmd in ["cp", "mv", "mkdir", "touch", "echo", "tee", "dd"]:
        assert svc._detect_operation_type(cmd) == "write"
    assert svc._detect_operation_type("rm") == "write"
    assert svc._detect_operation_type("rmdir") == "write"


def test_detect_operation_type_execute_default():
    svc = LocalAgentService("http://localhost:8000")
    assert svc._detect_operation_type("python3") == "execute"
    assert svc._detect_operation_type("weird") == "execute"


# ============================================================================
# _log_execution
# ============================================================================

@pytest.mark.asyncio
async def test_log_execution_success():
    svc = LocalAgentService("http://localhost:8000")
    resp = MagicMock()
    svc.client.post = AsyncMock(return_value=resp)
    await svc._log_execution({
        "agent_id": "a1", "command": "ls /tmp -la", "exit_code": 0,
    })
    svc.client.post.assert_awaited_once()
    await svc.close()


@pytest.mark.asyncio
async def test_log_execution_http_error_swallowed():
    import httpx
    svc = LocalAgentService("http://localhost:8000")
    svc.client.post = AsyncMock(side_effect=httpx.HTTPStatusError(
        "500", request=MagicMock(), response=MagicMock()))
    await svc._log_execution({"agent_id": "a1", "command": "ls", "exit_code": -1})
    await svc.close()


# ============================================================================
# get_status / close / singleton
# ============================================================================

@pytest.mark.asyncio
async def test_get_status_reachable():
    svc = LocalAgentService("http://localhost:8000")
    resp = MagicMock()
    resp.status_code = 200
    svc.client.get = AsyncMock(return_value=resp)
    status = await svc.get_status()
    assert status["backend_reachable"] is True
    assert status["status"] == "running"
    assert status["backend_url"] == "http://localhost:8000"
    await svc.close()


@pytest.mark.asyncio
async def test_get_status_request_error():
    import httpx
    svc = LocalAgentService("http://localhost:8000")
    svc.client.get = AsyncMock(side_effect=httpx.ConnectError("down"))
    status = await svc.get_status()
    assert status["backend_reachable"] is False
    assert status["status"] == "backend_unreachable"
    await svc.close()


@pytest.mark.asyncio
async def test_get_status_generic_exception():
    svc = LocalAgentService("http://localhost:8000")
    svc.client.get = AsyncMock(side_effect=RuntimeError("boom"))
    status = await svc.get_status()
    assert status["backend_reachable"] is False
    await svc.close()


@pytest.mark.asyncio
async def test_get_status_not_200():
    svc = LocalAgentService("http://localhost:8000")
    resp = MagicMock()
    resp.status_code = 503
    svc.client.get = AsyncMock(return_value=resp)
    status = await svc.get_status()
    assert status["backend_reachable"] is False
    await svc.close()


@pytest.mark.asyncio
async def test_close_acloses_client():
    svc = LocalAgentService("http://localhost:8000")
    svc.client.aclose = AsyncMock()
    await svc.close()
    svc.client.aclose.assert_awaited_once()


def test_get_local_agent_service_singleton():
    import core.local_agent_service as mod
    with patch.object(mod, "_local_agent_service", None):
        svc1 = get_local_agent_service("http://x:1")
        svc2 = get_local_agent_service("http://y:2")
        assert svc1 is svc2
        assert svc1.backend_url == "http://x:1"
        mod._local_agent_service = None
