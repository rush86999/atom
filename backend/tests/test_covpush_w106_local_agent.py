# -*- coding: utf-8 -*-
"""Coverage wave 106 — cli/local_agent.py (local agent CLI management).
Fully mocked (subprocess, os.kill, local agent service) — zero LLM spend,
no network, no real subprocesses.

Covers: group no-arg, start (already running / confirm declined / success with
defaults / backend-url override / Popen failure / PID-write failure must
terminate the orphaned subprocess), status (not running / stale / running with
ATOM_BACKEND_URL), stop (not running / stale cleanup yes+no / graceful /
force-kill / ProcessLookupError / generic error), execute (allowed full output,
timed out, no streams, denied with+without requires_approval, exception,
directory+agent-id passthrough), _get_local_agent_pid (valid/invalid/IOError/
missing), _is_local_agent_running (no pid / alive / dead), __main__ entry.
"""
import os
import runpy
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from cli import local_agent as la


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def pid_path(tmp_path, monkeypatch):
    """Point the module at a tmp pid file/dir."""
    pid_dir = tmp_path / "pids"
    monkeypatch.setattr(la, "LOCAL_AGENT_PID_DIR", pid_dir)
    monkeypatch.setattr(la, "LOCAL_AGENT_PID_FILE", pid_dir / "local-agent.pid")
    return la.LOCAL_AGENT_PID_FILE


def _write_pid(path, pid):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(pid))


def _service_mock(result):
    svc = MagicMock()
    svc.execute_command = AsyncMock(return_value=result)
    svc.close = AsyncMock()
    return svc


# ============================================================================
# Group / start
# ============================================================================

def test_group_no_args_shows_help(runner):
    res = runner.invoke(la.local_agent, [])
    assert res.exit_code == 2
    assert "Usage:" in res.output


def test_start_already_running_exit1(runner, pid_path):
    _write_pid(pid_path, os.getpid())
    res = runner.invoke(la.local_agent, ["start"], input="y\n")
    assert res.exit_code == 1
    assert f"already running (PID: {os.getpid()})" in res.output


def test_start_confirm_declined(runner, pid_path):
    res = runner.invoke(la.local_agent, ["start"], input="n\n")
    assert res.exit_code == 0
    assert "Cancelled" in res.output
    assert not pid_path.exists()


def test_start_success_defaults(runner, pid_path):
    proc = MagicMock()
    proc.pid = 4242
    with patch("subprocess.Popen", return_value=proc) as popen:
        res = runner.invoke(la.local_agent, ["start"], input="y\n")
    assert res.exit_code == 0
    assert f"Local agent started (PID: {proc.pid})" in res.output
    assert "Backend API: http://localhost:8000" in res.output
    assert pid_path.read_text() == "4242"
    env = popen.call_args.kwargs["env"]
    assert env["ATOM_BACKEND_URL"] == "http://localhost:8000"
    assert popen.call_args.kwargs["start_new_session"] is True


def test_start_backend_url_override(runner, pid_path):
    proc = MagicMock()
    proc.pid = 4243
    with patch("subprocess.Popen", return_value=proc) as popen:
        res = runner.invoke(
            la.local_agent, ["start", "--backend-url", "http://api.example:9000/"], input="y\n"
        )
    assert res.exit_code == 0
    assert "Backend API: http://api.example:9000" in res.output
    assert popen.call_args.kwargs["env"]["ATOM_BACKEND_URL"] == "http://api.example:9000"


def test_start_custom_port_host(runner, pid_path):
    proc = MagicMock()
    proc.pid = 4244
    with patch("subprocess.Popen", return_value=proc):
        res = runner.invoke(la.local_agent, ["start", "--port", "3000", "--host", "0.0.0.0"], input="y\n")
    assert res.exit_code == 0
    assert "Backend API: http://0.0.0.0:3000" in res.output


def test_start_popen_failure_exit1(runner, pid_path):
    with patch("subprocess.Popen", side_effect=RuntimeError("boom")):
        res = runner.invoke(la.local_agent, ["start"], input="y\n")
    assert res.exit_code == 1
    assert "Failed to start local agent" in res.output


def test_start_pid_write_failure_terminates_orphan(runner, pid_path):
    """PID file path blocked (a directory) -> Popen already spawned -> the
    spawned process must be terminated instead of leaked."""
    proc = MagicMock()
    proc.pid = 4245
    proc.terminate.side_effect = OSError("already gone")  # even if terminate fails, exit cleanly
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.mkdir()  # open(..., 'w') on a directory raises IsADirectoryError
    with patch("subprocess.Popen", return_value=proc) as popen:
        res = runner.invoke(la.local_agent, ["start"], input="y\n")
    assert res.exit_code == 1
    assert "Failed to start local agent" in res.output
    assert popen.called
    proc.terminate.assert_called_once()


# ============================================================================
# status
# ============================================================================

def test_status_not_running(runner, pid_path):
    res = runner.invoke(la.local_agent, ["status"])
    assert res.exit_code == 1
    assert "Local agent not running" in res.output


def test_status_stale_pid(runner, pid_path):
    _write_pid(pid_path, 99999999)
    res = runner.invoke(la.local_agent, ["status"])
    assert res.exit_code == 1
    assert "stale PID file: 99999999" in res.output


def test_status_running(runner, pid_path, monkeypatch):
    _write_pid(pid_path, os.getpid())
    monkeypatch.setenv("ATOM_BACKEND_URL", "http://agent.internal:7777")
    res = runner.invoke(la.local_agent, ["status"])
    assert res.exit_code == 0
    assert "Local agent running" in res.output
    assert f"PID: {os.getpid()}" in res.output
    assert "Backend URL: http://agent.internal:7777" in res.output


def test_status_running_default_backend_url(runner, pid_path, monkeypatch):
    _write_pid(pid_path, os.getpid())
    monkeypatch.delenv("ATOM_BACKEND_URL", raising=False)
    res = runner.invoke(la.local_agent, ["status"])
    assert res.exit_code == 0
    assert "Backend URL: http://localhost:8000" in res.output


# ============================================================================
# stop
# ============================================================================

def test_stop_not_running(runner, pid_path):
    res = runner.invoke(la.local_agent, ["stop"])
    assert res.exit_code == 1
    assert "Local agent not running" in res.output


def test_stop_stale_cleanup_confirmed(runner, pid_path):
    _write_pid(pid_path, 99999999)
    res = runner.invoke(la.local_agent, ["stop"], input="y\n")
    assert res.exit_code == 1
    assert "PID file removed" in res.output
    assert not pid_path.exists()


def test_stop_stale_cleanup_declined(runner, pid_path):
    _write_pid(pid_path, 99999999)
    res = runner.invoke(la.local_agent, ["stop"], input="n\n")
    assert res.exit_code == 1
    assert pid_path.exists()


def test_stop_graceful(runner, pid_path):
    _write_pid(pid_path, 99999998)
    with patch("os.kill") as kill, patch("time.sleep"), \
         patch("cli.local_agent._is_local_agent_running", side_effect=[True, False, False]):
        res = runner.invoke(la.local_agent, ["stop"])
    assert res.exit_code == 0
    assert "Local agent stopped" in res.output
    assert kill.call_count == 1
    assert not pid_path.exists()


def test_stop_force_kill(runner, pid_path):
    _write_pid(pid_path, 99999998)
    with patch("os.kill") as kill, patch("time.sleep"), \
         patch("cli.local_agent._is_local_agent_running", side_effect=[True, True, True, False, True, False]):
        res = runner.invoke(la.local_agent, ["stop"])
    assert res.exit_code == 0
    assert kill.call_count == 2  # SIGTERM + SIGKILL
    assert not pid_path.exists()


def test_stop_process_lookup_error(runner, pid_path):
    _write_pid(pid_path, 99999998)
    with patch("os.kill", side_effect=ProcessLookupError("gone")), \
         patch("cli.local_agent._is_local_agent_running", return_value=True):
        res = runner.invoke(la.local_agent, ["stop"])
    assert res.exit_code == 0
    assert "already dead" in res.output
    assert not pid_path.exists()


def test_stop_generic_error(runner, pid_path):
    _write_pid(pid_path, 99999998)
    with patch("os.kill", side_effect=RuntimeError("denied")), \
         patch("cli.local_agent._is_local_agent_running", return_value=True):
        res = runner.invoke(la.local_agent, ["stop"])
    assert res.exit_code == 1
    assert "Failed to stop local agent" in res.output


# ============================================================================
# execute
# ============================================================================

def test_execute_allowed_full_output(runner):
    svc = _service_mock({
        "allowed": True, "exit_code": 0, "duration_seconds": 1.5,
        "stdout": "hello", "stderr": "warn", "timed_out": False,
    })
    with patch("core.local_agent_service.get_local_agent_service", return_value=svc) as factory:
        res = runner.invoke(la.local_agent, ["execute", "ls -la"])
    assert res.exit_code == 0
    assert "Executing: ls -la" in res.output
    assert "Command executed" in res.output
    assert "Exit code: 0" in res.output
    assert "Duration: 1.50s" in res.output
    assert "hello" in res.output
    assert "warn" in res.output
    factory.assert_called_once_with(backend_url="http://localhost:8000")
    svc.close.assert_awaited_once()


def test_execute_allowed_timed_out(runner):
    svc = _service_mock({
        "allowed": True, "exit_code": 1, "duration_seconds": 300.0,
        "stdout": "", "timed_out": True,
    })
    with patch("core.local_agent_service.get_local_agent_service", return_value=svc):
        res = runner.invoke(la.local_agent, ["execute", "sleep 999"])
    assert res.exit_code == 0
    assert "timed out after 5 minutes" in res.output


def test_execute_allowed_no_streams(runner):
    svc = _service_mock({"allowed": True, "exit_code": 0, "duration_seconds": 0.1})
    with patch("core.local_agent_service.get_local_agent_service", return_value=svc):
        res = runner.invoke(la.local_agent, ["execute", "pwd"])
    assert res.exit_code == 0
    assert "Stdout:" not in res.output
    assert "Stderr:" not in res.output


def test_execute_denied_requires_approval(runner):
    svc = _service_mock({"allowed": False, "reason": "maturity too low", "requires_approval": True})
    with patch("core.local_agent_service.get_local_agent_service", return_value=svc):
        res = runner.invoke(la.local_agent, ["execute", "rm -rf /"])
    assert res.exit_code == 0
    assert "Command not allowed" in res.output
    assert "Reason: maturity too low" in res.output
    assert "Requires approval: Yes" in res.output


def test_execute_denied_no_approval_key(runner):
    svc = _service_mock({"allowed": False, "reason": "blocked"})
    with patch("core.local_agent_service.get_local_agent_service", return_value=svc):
        res = runner.invoke(la.local_agent, ["execute", "rm -rf /"])
    assert res.exit_code == 0
    assert "Requires approval" not in res.output


def test_execute_exception(runner):
    svc = _service_mock({})
    svc.execute_command = AsyncMock(side_effect=RuntimeError("backend down"))
    with patch("core.local_agent_service.get_local_agent_service", return_value=svc):
        res = runner.invoke(la.local_agent, ["execute", "ls"])
    assert res.exit_code == 0
    assert "Execution failed" in res.output
    svc.close.assert_awaited_once()


def test_execute_directory_and_agent_id_passthrough(runner):
    svc = _service_mock({"allowed": True, "exit_code": 0, "duration_seconds": 0.1})
    with patch("core.local_agent_service.get_local_agent_service", return_value=svc) as factory:
        res = runner.invoke(
            la.local_agent, ["execute", "git status", "--directory", "/tmp/work", "--agent-id", "a-1"]
        )
    assert res.exit_code == 0
    assert "Directory: /tmp/work" in res.output
    svc.execute_command.assert_awaited_once_with(
        agent_id="a-1", command="git status", working_directory="/tmp/work"
    )


def test_execute_default_agent_id(runner):
    svc = _service_mock({"allowed": True, "exit_code": 0, "duration_seconds": 0.1})
    with patch("core.local_agent_service.get_local_agent_service", return_value=svc):
        res = runner.invoke(la.local_agent, ["execute", "whoami"])
    assert res.exit_code == 0
    svc.execute_command.assert_awaited_once_with(
        agent_id="test-local-agent", command="whoami", working_directory=None
    )


def test_execute_missing_command_usage_error(runner):
    res = runner.invoke(la.local_agent, ["execute"])
    assert res.exit_code == 2  # required argument missing


# ============================================================================
# Helpers
# ============================================================================

def test_get_pid_valid(pid_path):
    _write_pid(pid_path, 123)
    assert la._get_local_agent_pid() == 123


def test_get_pid_missing(pid_path):
    assert la._get_local_agent_pid() is None


def test_get_pid_invalid_content(pid_path):
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text("not-a-number")
    assert la._get_local_agent_pid() is None


def test_get_pid_ioerror(pid_path):
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text("123")
    real_open = open

    def _flaky(path, *a, **k):
        if str(path).endswith("local-agent.pid") and k.get("mode", a[0] if a else "r") == "r":
            raise IOError("boom")
        return real_open(path, *a, **k)

    with patch("builtins.open", side_effect=_flaky):
        assert la._get_local_agent_pid() is None


def test_is_running_no_pid(pid_path):
    assert la._is_local_agent_running() is False


def test_is_running_alive(pid_path):
    _write_pid(pid_path, os.getpid())
    assert la._is_local_agent_running() is True


def test_is_running_dead(pid_path):
    _write_pid(pid_path, 99999999)
    assert la._is_local_agent_running() is False


def test_main_entry():
    with patch("sys.argv", ["local_agent.py"]):
        with pytest.raises(SystemExit) as ei:
            runpy.run_path(str(Path(la.__file__)), run_name="__main__")
    assert ei.value.code == 2  # group without subcommand shows help
