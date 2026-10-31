#!/usr/bin/env python3
"""Clean-root install/restart acceptance for the documented local backend.

Starts the real backend process (the same ``uvicorn main_api_app:app`` the
documented scripts launch) against a brand-new data root, performs a user
operation through the HTTP API, kills the process, starts a new one against the
same root, and reads the state back. Also checks the bootstrap password file.

This is deliberately process-level: in-process TestClient runs cannot prove
durable restart or the documented launch command.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
PYTHON = Path(os.getenv(
    "ATOM_ACCEPTANCE_PYTHON",
    "/Users/rushiparikh/projects/atom-phase-d/backend/venv/bin/python"))
OVERLAY = os.getenv(
    "ATOM_ACCEPTANCE_OVERLAY",
    "/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-pyoverlay")
ADMIN_PASSWORD = "ReadmeInstall!2026"


def request(url, method="GET", payload=None, token=None, timeout=60):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"content-type": "application/json"}
    if token:
        headers["authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode() or "{}")
        except Exception:
            body = {}
        return exc.code, body


def wait_ready(base, proc, timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"backend exited early with {proc.returncode}")
        try:
            status, _ = request(f"{base}/health/ready", timeout=5)
            if status == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("backend did not become ready")


class Backend:
    def __init__(self, world: Path, port: int):
        self.world = world
        self.port = port
        self.proc = None

    def start(self):
        env = {
            **os.environ,
            "ENVIRONMENT": "development",
            "SECRET_KEY": "install-acceptance-secret",
            "JWT_SECRET_KEY": "install-acceptance-jwt",
            "DATABASE_URL": f"sqlite:///{self.world / 'atom.db'}",
            # A fresh documented install generates the admin password and
            # writes it to the 0600 file the README points at. Do NOT preset
            # ADMIN_PASSWORD (that suppresses the file by design).
            "ATOM_BOOTSTRAP_PASSWORD_FILE": str(self.world / "logs" / "bootstrap_admin_password.txt"),
            "ENABLE_SCHEDULER": "false",
            "ENABLE_INGESTION_SYNC": "false",
            "ATOM_AGENT_EVOLUTION_ENABLED": "false",
            "ATOM_PRODUCT_PROFILE": "full",
            "ATOM_OFFICE_DIR": str(self.world / "office"),
            "BYOK_CONFIG_FILE": str(self.world / "byok_config.json"),
            "BYOK_KEYS_FILE": str(self.world / "byok_keys.json"),
            "BYOK_ENC_KEY_FILE": str(self.world / "byok_encryption_key"),
            "ATOM_LOCAL_ONLY": "true",
            "PYTHONPATH": f"{OVERLAY}:{REPO}:{BACKEND}",
            "LOG_LEVEL": "WARNING",
        }
        log = open(self.world / f"backend-{self.port}.log", "w")
        self.proc = subprocess.Popen(
            [str(PYTHON), "-m", "uvicorn", "main_api_app:app",
             "--host", "127.0.0.1", "--port", str(self.port)],
            cwd=str(BACKEND), env=env, stdout=log, stderr=subprocess.STDOUT,
        )
        wait_ready(f"http://127.0.0.1:{self.port}", self.proc)
        return self

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=10)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--world", type=Path,
                        default=Path("/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-install-world"))
    parser.add_argument("--port", type=int, default=8137)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--keep-world", action="store_true")
    args = parser.parse_args()
    if args.world.exists() and not args.keep_world:
        shutil.rmtree(args.world)
    (args.world / "logs").mkdir(parents=True, exist_ok=True)
    out = args.out or (args.world / "install-result.json")
    base = f"http://127.0.0.1:{args.port}"
    result = {"world": str(args.world), "base": base, "checks": {}}
    workflows_file = BACKEND / "workflows.json"
    workflows_backup = workflows_file.read_bytes() if workflows_file.exists() else None
    workflow_id = None
    execution_id = None

    backend = Backend(args.world, args.port)
    try:
        backend.start()
        pw_path = args.world / "logs" / "bootstrap_admin_password.txt"
        password = ""
        for _ in range(30):
            if pw_path.is_file():
                password = pw_path.read_text().strip()
                break
            time.sleep(1)
        result["checks"]["password_file"] = {
            "exists": pw_path.is_file(),
            "mode": oct(pw_path.stat().st_mode & 0o777) if pw_path.is_file() else None,
            "length": len(password),
        }
        status, login = request(f"{base}/api/auth/login", "POST", {
            "username": "admin@example.com", "password": password})
        token = login.get("access_token")
        result["checks"]["login"] = {"status": status, "token": bool(token)}

        status, profile = request(f"{base}/api/product/profile", token=token)
        result["checks"]["profile"] = {"status": status,
                                       "profile": profile.get("profile")}

        # A durable user operation: create a task row, then read it back.
        status, created = request(f"{base}/api/v1/tasks", "POST", {
            "title": "install acceptance durable task",
            "status": "todo", "priority": "medium"}, token=token)
        task_id = (created.get("id") or (created.get("data") or {}).get("id")
                   or (created.get("task") or {}).get("id"))
        result["checks"]["task_create"] = {"status": status, "id": task_id,
                                           "body": created}
        result["password"] = password

        # A real workflow execution: create, execute, and read it after the
        # process restart (durable execution state).
        definition = {
            "name": f"install-acceptance-{time.time_ns()}",
            "description": "install acceptance workflow",
            "version": "1.0.0",
            "nodes": [{
                "id": "node-1", "type": "trigger", "title": "start",
                "description": "acceptance", "position": {"x": 0, "y": 0},
                "config": {"service": "database", "action": "query",
                           "parameters": {}},
                "connections": [],
            }],
            "connections": [], "triggers": ["manual"], "enabled": True,
        }
        status, wf = request(f"{base}/api/v1/workflows/workflows", "POST",
                             definition, token=token)
        workflow_id = wf.get("id")
        if workflow_id:
            status, ex = request(
                f"{base}/api/v1/workflows/workflows/{workflow_id}/execute",
                "POST", {}, token=token)
            execution_id = ex.get("execution_id")
            for _ in range(30):
                _, history = request(
                    f"{base}/api/v1/workflows/workflows/{workflow_id}/executions",
                    token=token)
                if isinstance(history, list) and any(
                        h.get("execution_id") == execution_id
                        and h.get("status") == "completed" for h in history):
                    break
                time.sleep(1)
        result["checks"]["workflow"] = {
            "workflow_id": workflow_id, "execution_id": execution_id,
            "create_status": status}
    finally:
        backend.stop()

    # ---- restart with the same data root ------------------------------
    restarted = Backend(args.world, args.port)
    try:
        restarted.start()
        status, login2 = request(f"{base}/api/auth/login", "POST", {
            "username": "admin@example.com", "password": result.get("password") or ""})
        token2 = login2.get("access_token")
        status, tasks = request(f"{base}/api/v1/tasks", token=token2)
        items = tasks.get("tasks") or tasks.get("data") or tasks
        found = task_id and task_id in json.dumps(items)
        result["checks"]["restart"] = {
            "login_status": status,
            "task_survives": bool(found),
            "task_id": task_id,
        }
        if workflow_id and execution_id:
            _, history2 = request(
                f"{base}/api/v1/workflows/workflows/{workflow_id}/executions",
                token=token2)
            survived = isinstance(history2, list) and any(
                h.get("execution_id") == execution_id for h in history2)
            result["checks"]["workflow"]["survives_restart"] = bool(survived)
            result["checks"]["workflow"]["history_after_restart"] = history2
    finally:
        restarted.stop()
        if workflows_backup is not None:
            workflows_file.write_bytes(workflows_backup)
        elif workflows_file.exists():
            workflows_file.unlink()

    checks = result["checks"]
    result["status"] = (
        "verified" if (
            checks.get("login", {}).get("token")
            and checks.get("profile", {}).get("status") == 200
            and checks.get("task_create", {}).get("id")
            and checks.get("password_file", {}).get("mode") == "0o600"
            and checks.get("password_file", {}).get("length", 0) >= 16
            and checks.get("restart", {}).get("task_survives")
            and checks.get("workflow", {}).get("survives_restart")
        ) else "partial"
    )
    # Never persist the plaintext credential in the evidence artifact.
    result.pop("password", None)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
