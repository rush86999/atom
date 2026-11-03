#!/usr/bin/env python3
"""Normal-app controlled provider-lost-confirmation recovery.

Starts the real application backend (``main_api_app``) on a scratch SQLite /
LanceDB world with normal admin bootstrap and the environment-gated controlled
outbox adapter. The control is intentionally API-level for Agent 2 support:
the effect is accepted locally, the response is lost, the backend restarts,
the original operation is reconciled against the outbox, and no second effect
is created.

No live provider is contacted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
DEFAULT_WORLD_ROOT = Path(
    "/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode")
PYTHON = sys.executable
sys.path.insert(0, str(BACKEND))
ADMIN_PASSWORD = "Scratch-Pass-123"


class Backend:
    def __init__(self, world: Path, out: Path, port: int) -> None:
        self.world = world
        self.out = out
        self.port = port
        self.proc: Optional[subprocess.Popen] = None
        self.log = None

    def start(self, reset: bool) -> None:
        try:
            probe = socket.create_connection(
                ("127.0.0.1", self.port), timeout=0.5)
        except OSError:
            probe = None
        if probe is not None:
            probe.close()
            raise RuntimeError(
                f"port {self.port} is already served by another process")
        env = dict(os.environ)
        env.update({
            "DATABASE_URL": f"sqlite:///{self.world}/atom.db",
            "ATOM_DATA_DIR": str(self.world / "data"),
            "LANCEDB_URI": str(self.world / "data" / "atom_memory"),
            "LANCEDB_URI_BASE": str(self.world / "data" / "atom_memory"),
            "ATOM_OFFICE_DIR": str(self.world / "data" / "office"),
            "ADMIN_PASSWORD": ADMIN_PASSWORD,
            "ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT": "1",
            "ATOM_ASSIGNMENT_OUTBOX": str(self.world / "outbox.jsonl"),
            "ATOM_ASSIGNMENT_CONTROLLED_OUTCOME": "uncertain",
            "ATOM_LOCAL_ONLY": "true",
            "ENABLE_SCHEDULER": "false",
            "ENABLE_INGESTION_SYNC": "false",
            "PYTHONPATH": str(BACKEND),
        })
        self.log = open(self.out / "server.log", "a")
        self.proc = subprocess.Popen(
            [PYTHON, "-m", "uvicorn", "main_api_app:app",
             "--host", "127.0.0.1", "--port", str(self.port)],
            cwd=str(BACKEND), env=env,
            stdout=self.log, stderr=subprocess.STDOUT)
        self.wait_ready()

    def wait_ready(self) -> None:
        deadline = time.time() + 240
        while time.time() < deadline:
            try:
                response = httpx.get(
                    f"http://127.0.0.1:{self.port}/api/health", timeout=2)
                if response.status_code == 200:
                    return
            except Exception:
                pass
            time.sleep(0.5)
        raise RuntimeError("normal app backend did not become ready")

    def stop(self) -> None:
        if self.proc is None:
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.proc = None
        if self.log is not None:
            self.log.close()
            self.log = None

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"


def _prepare_world(raw: str) -> Path:
    from core.assignment_launcher_guard import (
        MARKER_NAME, UnsafeScratchError, prepare_scratch_dir,
        validate_scratch_dir,
    )

    if not raw:
        candidate = DEFAULT_WORLD_ROOT / (
            f"atom-g5-uncertain-{os.getpid()}-{uuid.uuid4().hex[:8]}")
        candidate.mkdir(parents=True)
        prepare_scratch_dir(candidate)
        return candidate
    candidate = validate_scratch_dir(raw)
    if candidate.exists() and any(candidate.iterdir()):
        if not (candidate / MARKER_NAME).exists():
            raise UnsafeScratchError(
                f"refusing an existing unmarked world: {candidate}")
        raise UnsafeScratchError(
            "this control owns a fresh scratch world; omit --world")
    prepare_scratch_dir(candidate)
    return candidate


def _check(checks: List[Dict[str, Any]], name: str, ok: bool, detail: Any):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})
    print(("PASS" if ok else "FAIL"), name,
          json.dumps(detail, default=str)[:600])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--world", default="")
    parser.add_argument("--port", type=int, default=8098)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    world = _prepare_world(args.world)
    report: Dict[str, Any] = {
        "schema": "atom-employee-g5-uncertain-normal-app-1",
        "world": str(world),
        "checks": [],
    }
    checks: List[Dict[str, Any]] = report["checks"]
    server = Backend(world, out, args.port)
    client = httpx.Client(timeout=180)

    def login() -> Dict[str, str]:
        response = client.post(
            server.base + "/api/auth/login",
            json={"username": "admin@example.com",
                  "password": ADMIN_PASSWORD})
        response.raise_for_status()
        return {"Authorization":
                f"Bearer {response.json()['access_token']}"}

    try:
        server.start(reset=True)
        headers = login()
        report["serving_identity_before"] = client.get(
            server.base + "/api/health").json()

        note = world / "note.txt"
        note.write_text("Controlled delivery note.\n")
        with note.open("rb") as handle:
            uploaded = client.post(
                server.base + "/api/document-ingestion/upload",
                headers=headers,
                files={"file": ("note.txt", handle, "text/plain")})
        uploaded.raise_for_status()
        upload_body = uploaded.json()
        data = upload_body.get("data") if isinstance(
            upload_body.get("data"), dict) else upload_body
        document_id = str(data.get("document_id") or "")
        _check(checks, "normal upload creates an authorized document",
               bool(document_id), document_id)

        created = client.post(
            server.base + "/api/assignments",
            headers=headers,
            json={
                "objective": "Send one controlled delivery notice",
                "sources": [{"document_id": document_id}],
                "outbound": {
                    "to": ["customer@example.invalid"],
                    "subject": "Controlled notice",
                    "body": "Controlled body",
                },
                "transport": "controlled",
                "authorized_actions": ["outbound"],
            })
        created.raise_for_status()
        created_body = created.json()
        run_id = created_body["run_id"]
        report["run_id"] = run_id
        detail = client.get(
            server.base + f"/api/assignments/{run_id}",
            headers=headers).json()
        send = next(
            step for step in detail["assignment"]["steps"]
            if step.get("operation_type") == "outbound")
        _check(checks, "outbound effect awaits explicit approval",
               send.get("status") == "awaiting_approval",
               send.get("status"))

        approved = client.post(
            server.base + f"/api/assignments/{run_id}/approve/{send['step_id']}",
            headers=headers, json={"note": "controlled approval"})
        approved.raise_for_status()
        resumed = client.post(
            server.base + f"/api/assignments/{run_id}/resume",
            headers=headers).json()
        detail = client.get(
            server.base + f"/api/assignments/{run_id}",
            headers=headers).json()
        send_state = next(
            step for step in detail["assignment"]["steps"]
            if step["step_id"] == send["step_id"])
        outbox = world / "outbox.jsonl"
        outbox_lines = [
            json.loads(line) for line in outbox.read_text().splitlines()
            if line.strip()
        ] if outbox.exists() else []
        operation_id = send_state.get("operation_id")
        report["operation_id"] = operation_id
        report["outbox_sha256"] = hashlib.sha256(
            outbox.read_bytes()).hexdigest() if outbox.exists() else None
        _check(checks, "provider accepted then lost confirmation",
               send_state.get("status") == "uncertain",
               send_state.get("failure"))
        _check(checks, "assignment is blocked, not completed",
               detail["assignment"]["status"] == "blocked",
               detail["assignment"]["status"])
        _check(checks, "exactly one controlled effect exists",
               len(outbox_lines) == 1, len(outbox_lines))

        # Real process restart while the effect is uncertain.
        server.stop()
        server.start(reset=False)
        headers = login()
        report["serving_identity_after_restart"] = client.get(
            server.base + "/api/health").json()
        detail = client.get(
            server.base + f"/api/assignments/{run_id}",
            headers=headers).json()
        send_state = next(
            step for step in detail["assignment"]["steps"]
            if step["step_id"] == send["step_id"])
        _check(checks, "uncertain original operation survives restart",
               send_state.get("status") == "uncertain"
               and send_state.get("operation_id") == operation_id,
               send_state.get("status"))
        _check(checks, "no second effect after restart",
               len([line for line in outbox.read_text().splitlines()
                    if line.strip()]) == 1,
               report["outbox_sha256"])

        reconciled = client.post(
            server.base
            + f"/api/assignments/{run_id}/reconcile/{send['step_id']}",
            headers=headers,
            json={
                "verdict": "applied",
                "evidence": (
                    "the controlled outbox contains the accepted operation "
                    "identity"),
                "evidence_ref": str(outbox),
                "provider_ref": operation_id,
            })
        reconciled.raise_for_status()
        resumed = client.post(
            server.base + f"/api/assignments/{run_id}/resume",
            headers=headers).json()
        detail = client.get(
            server.base + f"/api/assignments/{run_id}",
            headers=headers).json()
        send_state = next(
            step for step in detail["assignment"]["steps"]
            if step["step_id"] == send["step_id"])
        final_lines = [
            line for line in outbox.read_text().splitlines() if line.strip()
        ]
        _check(checks, "original operation reconciles to applied",
               send_state.get("status") == "applied",
               send_state.get("status"))
        _check(checks, "reconciled assignment completes",
               detail["assignment"]["status"] == "completed",
               detail["assignment"]["status"])
        _check(checks, "no resend after reconciliation",
               len(final_lines) == 1,
               len(final_lines))
        _check(checks, "same original operation identity retained",
               send_state.get("operation_id") == operation_id,
               operation_id)
        report["outbox_lines"] = [
            json.loads(line) for line in final_lines]
        report["assignment"] = detail
        report["ok"] = all(item["ok"] for item in checks)
        (out / "report.json").write_text(
            json.dumps(report, indent=2, default=str) + "\n")
        print(json.dumps({"ok": report["ok"], "checks": checks},
                         indent=2, default=str)[:8000])
        return 0 if report["ok"] else 1
    finally:
        server.stop()
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
