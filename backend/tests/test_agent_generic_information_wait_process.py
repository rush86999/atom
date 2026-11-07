"""Actual-OS-process Generic information-wait restart acceptance.

The two processes are real interpreters (not an in-process ``TestClient``
standing in for a restart). Each one serves the real ``api.agent_routes``
router over HTTP against the same scratch SQLite/Lance root. The first process
stops at a genuine model-selected information wait and is hard-killed; the
successor runs the production startup recovery owner and then answers through
the normal public job-answer route. Only ``LLMService.generate_structured`` is
scripted, so ``GenericAgent._react_step`` and every lifecycle/registry/oracle
seam run unpatched.

No provider, network, live credential, shared DB, replacement objective or
injected plan is used. Authentication uses the repository's existing FastAPI
dependency override for a seeded principal (controlled API scope, not an
ordinary login/browser session). The successor invokes the same execution
recovery helper the production lifespan calls; the full ``main_api_app`` boot
is deliberately not claimed here.
"""
from __future__ import annotations

import json
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
WORKER = Path(__file__).resolve().parent / "process_support" / (
    "generic_information_wait_process_worker.py")
PROJECT_PYTHON = os.getenv("ATOM_TEST_PYTHON", sys.executable)

BOARD_ID = "board-generic-wait"
COLUMN_ID = "column-generic-wait"
ANSWER = "Quarterly close checklist"


def _require_python() -> None:
    if not Path(PROJECT_PYTHON).exists():
        pytest.fail(
            f"configured child Python {PROJECT_PYTHON!r} is absent; "
            "actual-process acceptance requires an executable interpreter")


def _free_port() -> int:
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


def _child_env(scratch: Path, port: int) -> dict:
    env = dict(os.environ)
    # A pytest child must not inherit the verifier's DB/data selections.
    for key in (
            "PYTEST_CURRENT_TEST", "PYTEST_VERSION",
            "DATABASE_URL", "ATOM_DATA_DIR", "ATOM_LANCEDB_PATH",
            "LANCEDB_URI", "LANCEDB_URI_BASE", "ATOM_OFFICE_DIR"):
        env.pop(key, None)
    env.update({
        "PYTHONPATH": str(BACKEND),
        "PYTHONDONTWRITEBYTECODE": "1",
        "ENVIRONMENT": "development",
        "TESTING": "1",
        # core.database honors an explicit non-dev URL for a pytest-marked
        # process; this child is a real process but must use the scratch DB.
        "PYTEST_CURRENT_TEST": "generic_information_wait_process_worker",
        "SECRET_KEY": "generic-wait-process-test",
        "DATABASE_URL": f"sqlite:///{scratch / 'probe.db'}",
        "ATOM_DATA_DIR": str(scratch / "data"),
        "ATOM_LANCEDB_PATH": str(scratch / "lance"),
        "LANCEDB_URI": str(scratch / "lance"),
        "LANCEDB_URI_BASE": str(scratch / "lance"),
        "ATOM_OFFICE_DIR": str(scratch),
        "ATOM_EXECUTION_RECOVERY_ENABLED": "true",
        "ENABLE_SCHEDULER": "false",
        "GENERIC_WAIT_SCRATCH": str(scratch),
        "GENERIC_WAIT_BOARD_ID": BOARD_ID,
        "GENERIC_WAIT_COLUMN_ID": COLUMN_ID,
        "GENERIC_WAIT_ANSWER": ANSWER,
        "GENERIC_WAIT_PORT": str(port),
    })
    (scratch / "data").mkdir(parents=True, exist_ok=True)
    (scratch / "lance").mkdir(parents=True, exist_ok=True)
    return env


def _start(scratch: Path, log_name: str):
    scratch.mkdir(parents=True, exist_ok=True)
    port = _free_port()
    log_path = scratch / log_name
    log = log_path.open("a", encoding="utf-8")
    proc = subprocess.Popen(
        [PROJECT_PYTHON, str(WORKER)],
        cwd=str(BACKEND),
        env=_child_env(scratch, port),
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    deadline = time.time() + 120
    while time.time() < deadline:
        if proc.poll() is not None:
            log.close()
            raise AssertionError(
                f"worker exited {proc.returncode} before health; "
                f"log={log_path.read_text()[-4000:]}")
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health", timeout=1) as response:
                if response.status == 200:
                    return proc, port, log, log_path
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            time.sleep(0.25)
    proc.kill()
    proc.wait(timeout=30)
    log.close()
    raise AssertionError(
        f"worker did not become healthy; log={log_path.read_text()[-4000:]}")


def _call(port: int, path: str, body=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        method="POST" if body is not None else "GET",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def _query(scratch: Path, sql: str, params=()):
    connection = sqlite3.connect(scratch / "probe.db")
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute(sql, params)]
    finally:
        connection.close()


def _state(scratch: Path) -> dict:
    jobs = _query(scratch, "select id,status,result_summary from agent_jobs")
    executions = _query(
        scratch, "select id,status,metadata_json from agent_executions")
    waits = _query(
        scratch, "select id,status,action_type from hitl_actions")
    tasks = _query(scratch, "select id,title,status from board_tasks")
    return {
        "jobs": [
            {**row, "result_summary": json.loads(row["result_summary"] or "{}")}
            for row in jobs
        ],
        "executions": [
            {**row, "metadata_json": json.loads(row["metadata_json"] or "{}")}
            for row in executions
        ],
        "waits": waits,
        "tasks": tasks,
    }


def _stop(proc, log, *, kill: bool) -> None:
    if proc.poll() is None:
        if kill:
            os.kill(proc.pid, signal.SIGKILL)
        else:
            os.kill(proc.pid, signal.SIGTERM)
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=30)
    log.close()


def test_actual_process_wait_restart_answers_same_job_with_verified_effect(
        tmp_path):
    """A hard-killed waiter resumes in a new process through the public route.

    The successor must keep the SAME admitted job/execution, use its exact
    server-owned wait correlation, run a real registered ``tasks.create`` and
    leave an independently verified durable result. Replayed/late events must
    not repeat the effect.
    """
    _require_python()
    scratch = tmp_path / "generic-wait-world"

    first, first_port, first_log, first_log_path = _start(
        scratch, "first-process.log")
    try:
        status, started = _call(
            first_port,
            "/api/agents/a1/run?operation_id=generic-process-wait",
            {"parameters": {
                "sync": True,
                "task_input": "Create the closing task",
            }},
        )
        assert status == 202, (status, started)
        data = started["data"]
        job_id = data["job_id"]
        execution_id = data["execution_id"]
        receipt = data["wait_receipt"]
        assert data["job_status"] == "waiting", data
        assert receipt["kind"] == "information_request", receipt
        assert receipt["correlation_id"], receipt

        before = _state(scratch)
        assert len(before["jobs"]) == 1, before
        assert before["jobs"][0]["id"] == job_id
        assert before["jobs"][0]["status"] == "waiting", before
        assert len(before["executions"]) == 1, before
        assert before["executions"][0]["id"] == execution_id
        assert before["executions"][0]["status"] == "waiting", before
        assert len(before["waits"]) == 1, before
        assert before["waits"][0]["status"] == "pending", before
        assert before["tasks"] == [], before
        # Durable prior work must exist before the restart, not only in memory.
        resume_state = before["executions"][0]["metadata_json"].get(
            "resume_state") or {}
        assert resume_state.get("history"), before
        first_pid = first.pid
    finally:
        # Real process loss, not an in-process reset.
        _stop(first, first_log, kill=True)

    second, second_port, second_log, second_log_path = _start(
        scratch, "second-process.log")
    try:
        assert second.pid != first_pid, "restart must be a real new OS process"
        after_restart = _state(scratch)
        assert after_restart["jobs"][0]["id"] == job_id, after_restart
        assert after_restart["jobs"][0]["status"] == "waiting", after_restart
        assert after_restart["executions"][0]["id"] == execution_id, (
            after_restart)
        assert after_restart["executions"][0]["status"] == "waiting", (
            after_restart)
        assert after_restart["waits"][0]["status"] == "pending", after_restart
        assert after_restart["tasks"] == [], after_restart

        recovery = json.loads(
            (scratch / f"recovery-{second.pid}.json").read_text())
        assert recovery["ran"] is True, recovery
        assert recovery["result"]["agent_recovered"] == 0, recovery
        assert recovery["result"]["enabled"] is True, recovery

        status, answered = _call(
            second_port,
            f"/api/agents/a1/jobs/{job_id}/answer",
            {"answer": ANSWER, "correlation_id": receipt["correlation_id"]},
        )
        assert status == 200, (status, answered)
        body = answered["data"]
        assert body["job_status"] == "success", body
        assert body["execution_id"] == execution_id, body
        task_steps = [
            step for step in body["result"].get("steps") or []
            if (step.get("action") or {}).get("tool") == "tasks.create"
        ]
        assert task_steps, body
        assert task_steps[0]["output"].get("oracle_verified") is True, body

        after = _state(scratch)
        assert after["jobs"][0]["id"] == job_id, after
        assert after["jobs"][0]["status"] == "success", after
        assert after["executions"][0]["id"] == execution_id, after
        assert after["executions"][0]["status"] == "success", after
        assert len(after["tasks"]) == 1, after
        assert after["tasks"][0]["title"] == ANSWER, after

        # Replaying the exact accepted event is idempotent and inert.
        replay_status, replay = _call(
            second_port,
            f"/api/agents/a1/jobs/{job_id}/answer",
            {"answer": ANSWER, "correlation_id": receipt["correlation_id"]},
        )
        assert replay_status == 200, (replay_status, replay)
        assert replay["data"].get("already_resumed") is True, replay

        # A different late answer cannot rewrite the accepted fact or create
        # a second effect.
        late_status, late = _call(
            second_port,
            f"/api/agents/a1/jobs/{job_id}/answer",
            {"answer": "A different title",
             "correlation_id": receipt["correlation_id"]},
        )
        assert late_status == 409, (late_status, late)

        final = _state(scratch)
        assert len(final["tasks"]) == 1, final
        assert final["tasks"][0]["title"] == ANSWER, final
        phase = json.loads((scratch / "phase.json").read_text())
        assert phase["step"] == 3, phase
        assert "AUTHORIZED INFORMATION ANSWER" in phase["prompts"][1], phase
        assert ANSWER in phase["prompts"][1], phase
        # Server-owned wait identity is never taught to the model.
        for prompt in phase["prompts"]:
            assert receipt["correlation_id"] not in prompt, prompt
            assert receipt["hitl_action_id"] not in prompt, prompt
    finally:
        _stop(second, second_log, kill=False)

    # Preserve first child output for post-hoc evidence inspection.
    assert first_log_path.exists() and second_log_path.exists()
