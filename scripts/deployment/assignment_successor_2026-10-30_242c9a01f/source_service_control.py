#!/usr/bin/env python3
"""Verify, stop and restore the one authorized source service.

The deployment root never owns the source process. This helper is the
operator-facing boundary: it verifies the process against
``config/source_shutdown_scope.json`` immediately before a signal, refuses a
PID-only stop, and can restore the exact command/CWD/environment on failure.

Receipts contain process identity and paths only; no environment values or
secrets are written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCOPE_KEYS = ("pid", "service", "commit", "database", "restore_command")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_scope(root: Path) -> dict:
    path = root / "config" / "source_shutdown_scope.json"
    if not path.is_file():
        raise SystemExit(f"REFUSED: missing {path}")
    scope = json.loads(path.read_text())
    missing = [key for key in SCOPE_KEYS if scope.get(key) in (None, "")]
    if missing:
        raise SystemExit(f"REFUSED: source scope missing {missing}")
    return scope


def run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=20).stdout.strip()
    except Exception:
        return ""


def process_command(pid: int) -> str:
    return run(["ps", "-p", str(pid), "-o", "command="])


def process_cwd(pid: int) -> str:
    out = run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"])
    for line in out.splitlines():
        if line.startswith("n"):
            return line[1:]
    return ""


def process_holds(pid: int, path: str) -> bool:
    out = run(["lsof", "-p", str(pid)])
    return path in out


def db_holders(path: str) -> list[int]:
    out = run(["lsof", "-t", path])
    return sorted({int(line) for line in out.splitlines() if line.strip().isdigit()})


def listener_pids(port: int) -> list[int]:
    out = run(["lsof", "-nP", "-iTCP:%d" % port, "-sTCP:LISTEN", "-t"])
    return sorted({int(line) for line in out.splitlines() if line.strip().isdigit()})


def _norm(text: str) -> str:
    return " ".join(str(text or "").split())


def verify_scope(scope: dict) -> dict:
    pid = int(scope["pid"])
    errors = []
    command = process_command(pid)
    cwd = process_cwd(pid)
    if not command:
        errors.append("process_missing")
    elif _norm(command) != _norm(scope.get("command")):
        errors.append("command_mismatch")
    if cwd and cwd != str(scope.get("cwd")):
        errors.append("cwd_mismatch")
    if pid not in listener_pids(int(scope.get("port") or 0)):
        errors.append("listener_not_owned")
    if not process_holds(pid, str(scope.get("database"))):
        errors.append("source_db_not_held")
    other = [item for item in db_holders(str(scope.get("database")))
             if item != pid]
    if other:
        errors.append("other_source_db_holders")
    return {
        "schema": "atom-source-verification-1",
        "checked_at": now(),
        "pid": pid,
        "command": command,
        "cwd": cwd,
        "database": str(scope.get("database")),
        "port": int(scope.get("port") or 0),
        "scope_sha256": sha256_file(
            Path(scope.get("_scope_path") or "")),
        "ok": not errors,
        "errors": errors,
        "other_source_db_holders": other,
    }


def cmd_verify(root: Path) -> int:
    scope = load_scope(root)
    scope["_scope_path"] = str(root / "config" / "source_shutdown_scope.json")
    receipt = verify_scope(scope)
    out = root / "run" / "source_verification.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["ok"] else 2


def cmd_stop(root: Path) -> int:
    scope = load_scope(root)
    scope["_scope_path"] = str(root / "config" / "source_shutdown_scope.json")
    verification = verify_scope(scope)
    if not verification["ok"]:
        print(json.dumps(verification, indent=2))
        return 2
    pid = int(scope["pid"])
    os.kill(pid, signal.SIGTERM)
    deadline = time.time() + 30
    while time.time() < deadline and process_command(pid):
        time.sleep(0.5)
    still_running = bool(process_command(pid))
    remaining_holders = db_holders(str(scope["database"]))
    remaining_listeners = listener_pids(int(scope["port"]))
    receipt = {
        "schema": "atom-source-stop-1",
        "stopped_at": now(),
        "pid": pid,
        "service": scope.get("service"),
        "commit": scope.get("commit"),
        "command": scope.get("command"),
        "cwd": scope.get("cwd"),
        "database": scope.get("database"),
        "port": int(scope.get("port") or 0),
        "verification": verification,
        "still_running": still_running,
        "remaining_db_holders": remaining_holders,
        "remaining_listeners": remaining_listeners,
        "stopped": not still_running and not remaining_holders and not remaining_listeners,
    }
    out = root / "run" / "source_stop.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["stopped"] else 2


def cmd_check_stopped(root: Path) -> int:
    scope = load_scope(root)
    pid = int(scope["pid"])
    holders = db_holders(str(scope["database"]))
    listeners = listener_pids(int(scope["port"]))
    running = bool(process_command(pid))
    receipt = {
        "schema": "atom-source-stopped-check-1",
        "checked_at": now(),
        "pid": pid,
        "running": running,
        "db_holders": holders,
        "listeners": listeners,
        "stopped": not running and not holders and not listeners,
    }
    out = root / "run" / "source_stopped_check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["stopped"] else 2


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            values[key] = value
    return values


def cmd_restore(root: Path) -> int:
    scope = load_scope(root)
    pid = int(scope["pid"])
    port = int(scope.get("port") or 0)
    if process_command(pid) or listener_pids(port) or db_holders(str(scope["database"])):
        receipt = {
            "schema": "atom-source-restore-1",
            "restored_at": now(),
            "already_running": True,
            "pid": pid,
            "port": port,
            "ok": True,
        }
        out = root / "run" / "source_restore.json"
        out.write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps(receipt, indent=2))
        return 0
    command = str(scope.get("restore_command") or "")
    argv = shlex.split(command)
    if not argv:
        raise SystemExit("REFUSED: restore_command is empty")
    cwd = Path(str(scope.get("restore_cwd") or scope.get("cwd") or root))
    if not cwd.is_dir():
        raise SystemExit(f"REFUSED: restore cwd missing: {cwd}")
    env = dict(os.environ)
    env.update(_read_env(Path(str(scope.get("restore_env_source") or ""))))
    log = root / "logs" / "source_restore.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("ab", buffering=0) as fh:
        proc = subprocess.Popen(
            argv, cwd=cwd, env=env, stdout=fh, stderr=subprocess.STDOUT,
            start_new_session=True)
    deadline = time.time() + 60
    while time.time() < deadline and not listener_pids(port):
        time.sleep(0.5)
    ok = bool(listener_pids(port))
    receipt = {
        "schema": "atom-source-restore-1",
        "restored_at": now(),
        "already_running": False,
        "pid": proc.pid,
        "expected_pid": pid,
        "port": port,
        "command": command,
        "cwd": str(cwd),
        "listener_ready": ok,
        "ok": ok,
    }
    out = root / "run" / "source_restore.json"
    out.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    return 0 if ok else 2


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("command", choices=("verify", "stop", "check-stopped", "restore"))
    args = ap.parse_args()
    root = Path(args.root).resolve()
    result = {
        "verify": cmd_verify,
        "stop": cmd_stop,
        "check-stopped": cmd_check_stopped,
        "restore": cmd_restore,
    }[args.command](root)
    raise SystemExit(result)


if __name__ == "__main__":
    main()
