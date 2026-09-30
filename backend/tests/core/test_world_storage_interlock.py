"""Concurrency tests for the worlds storage interlock.

The defect these exist to prevent is a TOCTOU race, so they use REAL
processes and REAL flock contention rather than mocking it. A test that
simulated the lock would pass no matter how the production code behaved.

The scenario, end to end:

    launcher:   preflight -> flock(LOCK_SH) held for process lifetime -> work
    maintenance:              flock(LOCK_EX) BLOCKING until all SH released

A launcher that passed preflight a microsecond before the window opened is
still registered, so the window cannot complete until that launcher exits.
That is the property a lock-file check alone cannot provide.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from core import world_storage_guard as G

BACKEND = Path(__file__).resolve().parents[2]

# A real launcher: preflight, register (shared lock, held for process life),
# then stay alive so the test can contend with it.
_HOLDER_SRC = """
import sys, time
sys.path.insert(0, {backend!r})
from core.world_storage_guard import require_storage_ready
require_storage_ready()
print("REGISTERED", flush=True)
time.sleep({hold!r})
"""


def _isolate(monkeypatch, tmp_path: Path) -> Path:
    """Redirect every lock/config path at tmp, for both this process and children."""
    cfg = tmp_path / "world_storage.json"
    root = tmp_path / "acceptance_worlds"
    root.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        json.dumps(
            {
                "enabled": True,
                "layout": "local",
                "worlds": {"root": str(root)},
                "symlink_sample": 0,
            }
        )
    )
    monkeypatch.setattr(G, "CONFIG_PATH", cfg)
    # Use the REAL filenames: a child process resolves them from
    # ATOM_WORLD_STORAGE_PATHS using the module's own constant names, so
    # inventing shorter names here would silently point the parent and the
    # child at two different lock files — which is precisely the
    # "not interlocked at all" failure this suite exists to prevent.
    monkeypatch.setattr(G, "LOCK_PATH", tmp_path / G.LOCK_PATH.name)
    monkeypatch.setattr(G, "REGISTRY_LOCK_PATH", tmp_path / G.REGISTRY_LOCK_PATH.name)
    monkeypatch.setattr(G, "RUNNERS_DIR", tmp_path / G.RUNNERS_DIR.name)
    monkeypatch.setenv("ATOM_WORLD_STORAGE_PATHS", str(tmp_path))
    return tmp_path


def _child_env(tmp_path: Path) -> dict:
    """Env that points a child process at the same isolated lock paths."""
    env = dict(os.environ)
    env["ATOM_WORLD_STORAGE_PATHS"] = str(tmp_path)
    return env


def _start_holder(tmp_path: Path, hold: float) -> subprocess.Popen:
    src = _HOLDER_SRC.format(backend=str(BACKEND), hold=hold)
    script = tmp_path / "holder.py"
    script.write_text(src)
    proc = subprocess.Popen(
        [sys.executable, str(script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_child_env(tmp_path),
    )
    # Wait until it has actually registered before contending.
    deadline = time.time() + 30
    while time.time() < deadline:
        line = proc.stdout.readline()
        if "REGISTERED" in line:
            return proc
        if proc.poll() is not None:
            raise AssertionError(f"holder died: {proc.stderr.read()}")
    raise AssertionError("holder never registered")


# ---------------------------------------------------------------------------
# the race itself
# ---------------------------------------------------------------------------
def test_live_launcher_blocks_window_acquisition(tmp_path, monkeypatch):
    """A running launcher must prevent the window from being granted.

    This is the whole point: the window is not granted on the strength of a
    flag saying "no lock was set a moment ago".
    """
    _isolate(monkeypatch, tmp_path)
    holder = _start_holder(tmp_path, hold=6.0)
    try:
        with pytest.raises(G.WorldStorageError) as exc:
            G.acquire_maintenance_lock("race", drain_timeout=1.0)
        msg = str(exc.value)
        assert "CANNOT start" in msg
        # It must NAME the holder, so the operator knows what to stop.
        assert str(holder.pid) in msg
        # And no lock file may have been written.
        assert not G.LOCK_PATH.exists()
    finally:
        holder.kill()
        holder.wait(timeout=10)


def test_window_waits_for_launcher_then_succeeds(tmp_path, monkeypatch):
    """With a drain timeout, the window opens only AFTER the launcher exits."""
    _isolate(monkeypatch, tmp_path)
    holder = _start_holder(tmp_path, hold=1.5)
    try:
        payload = G.acquire_maintenance_lock("drain", drain_timeout=30.0)
        assert payload["active"] is True
        assert payload["drained"] is True, "should have reported that it drained"
        assert holder.poll() is not None, "window opened while a launcher was live"
    finally:
        try:
            G.release_maintenance_lock()
        except Exception:
            pass
        holder.kill()
        holder.wait(timeout=10)


def test_launcher_refused_while_window_held(tmp_path, monkeypatch):
    """The other direction: once the window is open, new launches are refused."""
    _isolate(monkeypatch, tmp_path)
    G.acquire_maintenance_lock("window")
    try:
        with pytest.raises(G.WorldStorageError):
            G.register_runner(role="launcher")
    finally:
        G.release_maintenance_lock()
    # And once released, registration works again.
    reg = G.register_runner(role="launcher")
    reg.close()


def test_exclusive_then_shared_is_refused(tmp_path, monkeypatch):
    """Kernel-level check of the shared/exclusive semantics themselves."""
    import fcntl

    _isolate(monkeypatch, tmp_path)
    G.acquire_maintenance_lock("window")
    try:
        fd = os.open(str(G.REGISTRY_LOCK_PATH), os.O_RDWR | os.O_CREAT, 0o644)
        try:
            with pytest.raises(OSError):
                fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        finally:
            os.close(fd)
    finally:
        G.release_maintenance_lock()


# ---------------------------------------------------------------------------
# registration bookkeeping
# ---------------------------------------------------------------------------
def test_runner_record_is_written_and_reaped(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    reg = G.register_runner(role="launcher")
    try:
        holders = G.list_runners()
        assert any(h.get("pid") == os.getpid() for h in holders)
    finally:
        reg.close()
    assert not any(h.get("pid") == os.getpid() for h in G.list_runners())


def test_dead_runner_record_is_reaped(tmp_path, monkeypatch):
    """A SIGKILLed launcher drops its flock but leaves a record.

    The record must not make a later window look blocked forever.
    """
    _isolate(monkeypatch, tmp_path)
    G.RUNNERS_DIR.mkdir(parents=True, exist_ok=True)
    # PID 999999 is not a live process on this machine.
    stale = G.RUNNERS_DIR / "999999-1.json"
    stale.write_text(json.dumps({"pid": 999999, "role": "launcher", "argv": ["ghost"]}))
    holders = G.list_runners()
    assert not any(h.get("pid") == 999999 for h in holders)
    assert not stale.exists()


def test_registration_double_call_is_idempotent(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    a = G._register_current_process()
    b = G._register_current_process()
    try:
        assert a is b
    finally:
        a.close()


def test_bypass_skips_registration(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv(G.BYPASS_ENV, "1")
    reg = G.register_runner(role="launcher")
    assert reg.payload.get("bypassed") is True
    reg.close()


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------
def _cli(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "core.world_storage_guard", *args],
        capture_output=True,
        text=True,
        cwd=str(BACKEND),
        env=_child_env(tmp_path),
        timeout=120,
    )


def test_cli_lock_refuses_when_worlds_busy(tmp_path, monkeypatch):
    """The CLI must exit non-zero and name the holder, not hang or claim success."""
    _isolate(monkeypatch, tmp_path)
    holder = _start_holder(tmp_path, hold=6.0)
    try:
        r = _cli(tmp_path, "lock", "--reason", "cli race", "--drain-timeout", "1")
        assert r.returncode == 1
        assert "CANNOT start" in r.stdout
        assert str(holder.pid) in r.stdout
    finally:
        holder.kill()
        holder.wait(timeout=10)


def test_cli_runners_lists_and_clears(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path)
    holder = _start_holder(tmp_path, hold=4.0)
    try:
        r = _cli(tmp_path, "runners")
        assert r.returncode == 0
        assert str(holder.pid) in r.stdout
    finally:
        holder.kill()
        holder.wait(timeout=10)
    r = _cli(tmp_path, "runners")
    assert "no world launchers" in r.stdout
