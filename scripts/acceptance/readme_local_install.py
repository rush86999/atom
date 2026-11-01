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
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import docx

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
from scripts.readme_acceptance.common import reset_world  # noqa: E402
from scripts.readme_acceptance import mock_llm_server  # noqa: E402
PYTHON = Path(os.getenv(
    "ATOM_ACCEPTANCE_PYTHON",
    str((REPO / "backend" / "venv" / "bin" / "python").resolve())))
OVERLAY = os.getenv("ATOM_ACCEPTANCE_OVERLAY", "")
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
            "ATOM_LOCAL_ONLY": os.getenv("ATOM_INSTALL_LOCAL_ONLY", "false"),
            "ATOM_GOAL_RUN_AGENT_WORK": "0",
            "OLLAMA_BASE_URL": os.getenv("ATOM_INSTALL_LLM_URL", "http://127.0.0.1:59996/v1"),
            "OPENAI_BASE_URL": os.getenv("ATOM_INSTALL_LLM_URL", "http://127.0.0.1:59996/v1"),
            "OPENAI_API_KEY": "sk-install-acceptance-local-upstream",
            "PYTHONPATH": ":".join(
                part for part in (OVERLAY, str(REPO), str(BACKEND))
                if part),
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
    reset_world(
        args.world,
        reset=not args.keep_world,
        allowed_root=Path(os.getenv("ATOM_README_WORLD_ROOT", str(args.world.parent))),
    )
    (args.world / "logs").mkdir(parents=True, exist_ok=True)
    out = args.out or (args.world / "install-result.json")
    base = f"http://127.0.0.1:{args.port}"
    result = {"world": str(args.world), "base": base, "checks": {}}
    workflows_file = BACKEND / "workflows.json"
    workflows_backup = workflows_file.read_bytes() if workflows_file.exists() else None
    workflow_id = None
    execution_id = None

    llm = mock_llm_server.Server(59996).start()
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

        # A presented Office canvas must survive a real backend restart.
        office_dir = args.world / "office"
        office_dir.mkdir(parents=True, exist_ok=True)
        office_file = office_dir / "install_canvas.docx"
        document = docx.Document()
        document.add_paragraph("install canvas survives restart")
        document.save(str(office_file))
        status, presented = request(f"{base}/api/v1/office/present", "POST", {
            "file_path": str(office_file), "user_id": "acceptance",
            "title": "install canvas"}, token=token)
        canvas_id = presented.get("canvas_id")
        result["checks"]["office_canvas"] = {
            "canvas_id": canvas_id, "present_status": status}

        # A goal run paused on a human checkpoint must survive restart, keep
        # its identity, and resume into exactly one deliverable.
        status, goal = request(f"{base}/api/goals", "POST", {
            "title": "install goal restart acceptance",
            "description": "install restart goal",
            "criteria": [{"description": "create the deliverable"}],
        }, token=token)
        goal_id = (goal.get("goal_id") or goal.get("id")
                   or (goal.get("goal") or {}).get("id")
                   or (goal.get("data") or {}).get("id"))
        goal_run = None
        goal_run_id = None
        goal_hitl_id = None
        if goal_id:
            status, goal_run = request(f"{base}/api/goal-runs", "POST", {
                "goal_id": goal_id,
                "role": "acceptance",
                "start": False,
                "supervision_mode": "shadow",
                "plan": [
                    {"id": "install-checkpoint", "kind": "human_checkpoint",
                     "title": "Install restart checkpoint"},
                    {"id": "install-deliverable", "kind": "canvas_work",
                     "title": "Install restart deliverable",
                     "canvas_type": "document"},
                ],
            }, token=token)
            goal_run_id = (goal_run or {}).get("id") or ((goal_run or {}).get("run") or {}).get("id")
        if goal_run_id:
            status, advance = request(
                f"{base}/api/goal-runs/{goal_run_id}/advance", "POST", {},
                token=token)
            _, pending = request(f"{base}/api/agents/approvals/pending",
                                 token=token)
            for action in pending if isinstance(pending, list) else []:
                if (action.get("action_type") == "goal_run_checkpoint"
                        and str((action.get("params") or {}).get("run_id"))
                        == str(goal_run_id)):
                    goal_hitl_id = action.get("id")
                    break
            _, run_before_restart = request(
                f"{base}/api/goal-runs/{goal_run_id}", token=token)
            _, canvases_before = request(
                f"{base}/api/goal-runs/{goal_run_id}/canvases", token=token)
        else:
            advance = run_before_restart = canvases_before = {}
        result["checks"]["goal_run"] = {
            "goal_id": goal_id,
            "run_id": goal_run_id,
            "hitl_id": goal_hitl_id,
            "advance": advance,
            "before_restart": run_before_restart,
            "canvases_before": canvases_before,
        }
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
        canvas_id = (result["checks"].get("office_canvas") or {}).get("canvas_id")
        if canvas_id:
            status, canvas_after = request(
                f"{base}/api/canvas/{canvas_id}", token=token2)
            canvas_text = json.dumps(canvas_after)
            canvas_ok = (status == 200
                         and ("install_canvas" in canvas_text
                              or "office_file" in canvas_text))
            file_path = str(args.world / "office" / "install_canvas.docx")
            import urllib.parse
            query = urllib.parse.urlencode({
                "file_path": file_path, "canvas_id": canvas_id})
            download_ok = False
            try:
                req = urllib.request.Request(
                    f"{base}/api/v1/office/download?{query}",
                    headers={"authorization": f"Bearer {token2}"})
                with urllib.request.urlopen(req, timeout=30) as response:
                    download_ok = (response.status == 200
                                   and response.read(2) == b"PK")
            except Exception:
                download_ok = False
            result["checks"]["office_canvas"].update({
                "restart_status": status,
                "canvas_read": canvas_ok,
                "download_ok": download_ok,
            })

        goal_check = result["checks"].get("goal_run") or {}
        run_id = goal_check.get("run_id")
        hitl_id = goal_check.get("hitl_id")
        if run_id:
            status, run_after = request(
                f"{base}/api/goal-runs/{run_id}", token=token2)
            _, canvases_after = request(
                f"{base}/api/goal-runs/{run_id}/canvases", token=token2)
            before = goal_check.get("before_restart") or {}
            before_status = before.get("status")
            same_identity = str((run_after or {}).get("id")) == str(run_id)
            status_kept = (run_after or {}).get("status") == before_status
            before_canvases = len(
                (goal_check.get("canvases_before") or {}).get("canvases") or [])
            after_canvases = len((canvases_after or {}).get("canvases") or [])
            approve = {}
            if hitl_id:
                status, approve = request(
                    f"{base}/api/agents/approvals/{hitl_id}", "POST",
                    {"decision": "approved",
                     "feedback": "install restart approval"}, token=token2)
            _, run_resumed = request(
                f"{base}/api/goal-runs/{run_id}", token=token2)
            _, canvases_resumed = request(
                f"{base}/api/goal-runs/{run_id}/canvases", token=token2)
            resumed_canvases = len(
                (canvases_resumed or {}).get("canvases") or [])
            goal_check.update({
                "restart_status": status,
                "run_after_restart": run_after,
                "canvases_after_restart": canvases_after,
                "same_identity": same_identity,
                "status_kept": status_kept,
                "same_canvas_count_before_approval": (
                    before_canvases == after_canvases),
                "approve": approve,
                "run_resumed": run_resumed,
                "canvases_resumed": canvases_resumed,
                "resumed_canvas_count": resumed_canvases,
                "no_duplicate_effect": resumed_canvases == 1,
            })
            result["checks"]["goal_run"] = goal_check
    finally:
        restarted.stop()
        try:
            llm.stop()
        except Exception:
            pass
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
            and checks.get("office_canvas", {}).get("canvas_read")
            and checks.get("office_canvas", {}).get("download_ok")
            and checks.get("goal_run", {}).get("same_identity")
            and checks.get("goal_run", {}).get("status_kept")
            and checks.get("goal_run", {}).get("same_canvas_count_before_approval")
            and checks.get("goal_run", {}).get("no_duplicate_effect")
        ) else "partial"
    )
    # Never persist the plaintext credential in the evidence artifact.
    result["mock_llm_calls"] = mock_llm_server.calls()[-8:]
    result.pop("password", None)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result.get("status") == "verified" else 1)


if __name__ == "__main__":
    main()
