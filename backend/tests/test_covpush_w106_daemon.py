# -*- coding: utf-8 -*-
"""Coverage wave 106 — cli/daemon.py (DaemonManager background service).
Fully mocked (subprocess.Popen, os.kill, psutil) — no real daemons spawned,
no signals sent, no network.

Covers: get_pid (missing/valid/invalid/IOError), is_running (no pid,
psutil true/false/exception, no-psutil signal fallback alive+dead),
start_daemon (already-running RuntimeError, success incl. cwd pinning,
dev --reload, host-mount env, log-open IOError, Popen RuntimeError w/ closed
log, PID-write IOError w/ terminate), stop_daemon (not running, graceful,
force-kill, ProcessLookupError, unlink IOError), get_status (not running,
stale pid, psutil-less limited, full dict — asserts uptime is WALL-CLOCK not
cpu_times().system — died_unexpectedly on NoSuchProcess).
"""
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import psutil
import pytest

import cli.daemon as daemon_mod


@pytest.fixture()
def paths(tmp_path, monkeypatch):
    pid_dir = tmp_path / "pids"
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(daemon_mod, "PID_DIR", pid_dir)
    monkeypatch.setattr(daemon_mod, "PID_FILE", pid_dir / "atom-os.pid")
    monkeypatch.setattr(daemon_mod, "LOG_DIR", log_dir)
    monkeypatch.setattr(daemon_mod, "LOG_FILE", log_dir / "daemon.log")
    return daemon_mod.PID_FILE, daemon_mod.LOG_FILE


def _write_pid(path, pid):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(pid))


def _proc_mock(pid=7777):
    proc = MagicMock()
    proc.pid = pid
    return proc


# ============================================================================
# get_pid
# ============================================================================

def test_get_pid_missing(paths):
    assert daemon_mod.DaemonManager.get_pid() is None


def test_get_pid_valid(paths):
    pid_file, _ = paths
    _write_pid(pid_file, 4242)
    assert daemon_mod.DaemonManager.get_pid() == 4242


def test_get_pid_invalid(paths):
    pid_file, _ = paths
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text("junk")
    assert daemon_mod.DaemonManager.get_pid() is None


def test_get_pid_ioerror(paths):
    pid_file, _ = paths
    _write_pid(pid_file, 4242)
    real_open = open

    def _flaky(path, *a, **k):
        if str(path).endswith("atom-os.pid") and k.get("mode", a[0] if a else "r") == "r":
            raise IOError("boom")
        return real_open(path, *a, **k)

    with patch("builtins.open", side_effect=_flaky):
        assert daemon_mod.DaemonManager.get_pid() is None


# ============================================================================
# is_running
# ============================================================================

def test_is_running_no_pid(paths):
    assert daemon_mod.DaemonManager.is_running() is False


def test_is_running_psutil_true(paths):
    pid_file, _ = paths
    _write_pid(pid_file, 4242)
    with patch("cli.daemon.psutil.pid_exists", return_value=True):
        assert daemon_mod.DaemonManager.is_running() is True


def test_is_running_psutil_false(paths):
    pid_file, _ = paths
    _write_pid(pid_file, 4242)
    with patch("cli.daemon.psutil.pid_exists", return_value=False):
        assert daemon_mod.DaemonManager.is_running() is False


def test_is_running_psutil_exception(paths):
    pid_file, _ = paths
    _write_pid(pid_file, 4242)
    with patch("cli.daemon.psutil.pid_exists", side_effect=RuntimeError("denied")):
        assert daemon_mod.DaemonManager.is_running() is False


def test_is_running_no_psutil_alive(paths, monkeypatch):
    import os
    pid_file, _ = paths
    _write_pid(pid_file, os.getpid())
    monkeypatch.setattr(daemon_mod, "psutil", None)
    assert daemon_mod.DaemonManager.is_running() is True


def test_is_running_no_psutil_dead(paths, monkeypatch):
    pid_file, _ = paths
    _write_pid(pid_file, 99999999)
    monkeypatch.setattr(daemon_mod, "psutil", None)
    assert daemon_mod.DaemonManager.is_running() is False


# ============================================================================
# start_daemon
# ============================================================================

def test_start_already_running_raises(paths):
    with patch("cli.daemon.DaemonManager.is_running", return_value=True), \
         patch("cli.daemon.DaemonManager.get_pid", return_value=99):
        with pytest.raises(RuntimeError, match="already running"):
            daemon_mod.DaemonManager.start_daemon()


def test_start_success(paths):
    pid_file, log_file = paths
    proc = _proc_mock(4242)
    with patch("cli.daemon.DaemonManager.is_running", return_value=False), \
         patch("subprocess.Popen", return_value=proc) as popen:
        pid = daemon_mod.DaemonManager.start_daemon(port=9000, host="127.0.0.1", workers=2)
    assert pid == 4242
    assert pid_file.read_text() == "4242"
    assert log_file.exists()
    cmd = popen.call_args.args[0]
    assert cmd == [popen.call_args.args[0][0], "-m", "uvicorn", "main_api_app:app",
                   "--host", "127.0.0.1", "--port", "9000", "--workers", "2"]
    assert popen.call_args.kwargs["start_new_session"] is True


def test_start_pins_cwd_to_backend(paths):
    """The daemon subprocess must run with the backend dir as cwd, otherwise
    'main_api_app:app' cannot be imported when the CLI is invoked from any
    other directory."""
    proc = _proc_mock(4242)
    expected = str(Path(daemon_mod.__file__).parent.parent)
    with patch("cli.daemon.DaemonManager.is_running", return_value=False), \
         patch("subprocess.Popen", return_value=proc) as popen:
        daemon_mod.DaemonManager.start_daemon()
    assert popen.call_args.kwargs["cwd"] == expected


def test_start_dev_appends_reload(paths):
    proc = _proc_mock(4242)
    with patch("cli.daemon.DaemonManager.is_running", return_value=False), \
         patch("subprocess.Popen", return_value=proc) as popen:
        daemon_mod.DaemonManager.start_daemon(dev=True)
    assert "--reload" in popen.call_args.args[0]


def test_start_host_mount_sets_env(paths):
    proc = _proc_mock(4242)
    with patch("cli.daemon.DaemonManager.is_running", return_value=False), \
         patch("subprocess.Popen", return_value=proc) as popen:
        daemon_mod.DaemonManager.start_daemon(host_mount=True)
    assert popen.call_args.kwargs["env"]["ATOM_HOST_MOUNT_ENABLED"] == "true"


def test_start_log_open_error(paths):
    pid_file, log_file = paths
    log_file.mkdir(parents=True)  # LOG_FILE is a directory -> open('a') fails
    with patch("cli.daemon.DaemonManager.is_running", return_value=False):
        with pytest.raises(IOError, match="Cannot open log file"):
            daemon_mod.DaemonManager.start_daemon()


def test_start_popen_error(paths):
    pid_file, log_file = paths
    with patch("cli.daemon.DaemonManager.is_running", return_value=False), \
         patch("subprocess.Popen", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError, match="Failed to start daemon"):
            daemon_mod.DaemonManager.start_daemon()


def test_start_pid_write_error_terminates(paths):
    pid_file, log_file = paths
    pid_file.mkdir(parents=True)  # PID_FILE is a directory -> open('w') fails
    proc = _proc_mock(4242)
    with patch("cli.daemon.DaemonManager.is_running", return_value=False), \
         patch("subprocess.Popen", return_value=proc):
        with pytest.raises(IOError, match="Cannot write PID file"):
            daemon_mod.DaemonManager.start_daemon()
    proc.terminate.assert_called_once()


# ============================================================================
# stop_daemon
# ============================================================================

def test_stop_not_running(paths):
    assert daemon_mod.DaemonManager.stop_daemon() is False


def test_stop_graceful(paths):
    pid_file, _ = paths
    _write_pid(pid_file, 4242)
    with patch("os.kill") as kill, patch("time.sleep"), \
         patch("cli.daemon.DaemonManager.is_running", side_effect=[False, False]):
        assert daemon_mod.DaemonManager.stop_daemon() is True
    kill.assert_called_once_with(4242, 15)  # SIGTERM
    assert not pid_file.exists()


def test_stop_force_kill(paths):
    pid_file, _ = paths
    _write_pid(pid_file, 4242)
    with patch("os.kill") as kill, patch("time.sleep"), \
         patch("cli.daemon.DaemonManager.is_running", side_effect=[True, True, True, True, False, True, False]):
        assert daemon_mod.DaemonManager.stop_daemon() is True
    assert kill.call_count == 2  # SIGTERM then SIGKILL
    assert not pid_file.exists()


def test_stop_process_lookup_error(paths):
    pid_file, _ = paths
    _write_pid(pid_file, 4242)
    with patch("os.kill", side_effect=ProcessLookupError("gone")):
        assert daemon_mod.DaemonManager.stop_daemon() is True
    assert not pid_file.exists()


def test_stop_unlink_error_raises(paths):
    pid_file, _ = paths
    _write_pid(pid_file, 4242)
    with patch("os.kill"), patch("time.sleep"), \
         patch("cli.daemon.DaemonManager.is_running", side_effect=[False, False]), \
         patch("pathlib.Path.unlink", side_effect=IOError("locked")):
        with pytest.raises(IOError, match="Cannot remove PID file"):
            daemon_mod.DaemonManager.stop_daemon()


def test_stop_process_lookup_unlink_error_swallowed(paths):
    pid_file, _ = paths
    _write_pid(pid_file, 4242)
    with patch("os.kill", side_effect=ProcessLookupError("gone")), \
         patch("pathlib.Path.unlink", side_effect=IOError("locked")):
        assert daemon_mod.DaemonManager.stop_daemon() is True


# ============================================================================
# get_status
# ============================================================================

def test_status_not_running(paths):
    st = daemon_mod.DaemonManager.get_status()
    assert st == {
        "running": False, "pid": None, "uptime_seconds": None,
        "memory_mb": None, "cpu_percent": None, "status": "not_running",
    }


def test_status_stale_pid(paths):
    pid_file, _ = paths
    _write_pid(pid_file, 99999999)
    with patch("cli.daemon.psutil.pid_exists", return_value=False):
        st = daemon_mod.DaemonManager.get_status()
    assert st["running"] is False
    assert st["status"] == "stale_pid_file"
    assert st["pid"] == 99999999


def test_status_limited_without_psutil(paths, monkeypatch):
    import os
    pid_file, _ = paths
    _write_pid(pid_file, os.getpid())
    monkeypatch.setattr(daemon_mod, "psutil", None)
    st = daemon_mod.DaemonManager.get_status()
    assert st["running"] is True
    assert st["status"] == "running"
    assert st["uptime_seconds"] is None


def test_status_full_uptime_is_wall_clock(paths):
    """uptime_seconds must be wall-clock uptime (time.time() - create_time()),
    not cpu_times().system (which is CPU time, typically ~0 for a fresh
    daemon and never equals uptime)."""
    pid_file, _ = paths
    _write_pid(pid_file, 4242)
    now = time.time()
    proc = MagicMock()
    proc.create_time.return_value = now - 1234.5
    proc.cpu_times.return_value.system = 5.0  # the wrong source
    proc.memory_info.return_value.rss = 209715200
    proc.cpu_percent.return_value = 3.5
    with patch("cli.daemon.psutil.pid_exists", return_value=True), \
         patch("cli.daemon.psutil.Process", return_value=proc):
        st = daemon_mod.DaemonManager.get_status()
    assert st["running"] is True
    assert st["status"] == "running"
    assert st["pid"] == 4242
    assert st["uptime_seconds"] == pytest.approx(1234.5, abs=5.0)
    assert st["memory_mb"] == pytest.approx(200.0, abs=0.1)
    assert st["cpu_percent"] == 3.5


def test_status_died_unexpectedly(paths):
    pid_file, _ = paths
    _write_pid(pid_file, 4242)
    with patch("cli.daemon.psutil.pid_exists", return_value=True), \
         patch("cli.daemon.psutil.Process", side_effect=psutil.NoSuchProcess(4242)):
        st = daemon_mod.DaemonManager.get_status()
    assert st["running"] is False
    assert st["status"] == "died_unexpectedly"
    assert st["note"] == "Process died unexpectedly"


def test_psutil_import_fallback():
    """If psutil is missing, the module degrades to signal-0 checks and a
    limited status dict instead of crashing at import time."""
    import builtins
    import importlib

    real_import = builtins.__import__

    def _fake_import(name, *a, **k):
        if name == "psutil":
            raise ImportError("no psutil")
        return real_import(name, *a, **k)

    with patch("builtins.__import__", side_effect=_fake_import):
        importlib.reload(daemon_mod)
    assert daemon_mod.psutil is None
    assert daemon_mod.DaemonManager.is_running() is False  # no pid file in home
    importlib.reload(daemon_mod)  # restore real psutil for later tests
    assert daemon_mod.psutil is not None
