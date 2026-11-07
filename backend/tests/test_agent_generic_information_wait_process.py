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

The same file also covers the accepted-answer crash row: the answer route
commits the durable HITL answer and the process hard-exits at a test-only crash
hook (before or after the job claim). A fresh process calls the real bounded
``recover_accepted_information_waits`` join (the function the production
lifespan wires in). A pre-claim crash resumes the same job exactly once,
including when two successor processes race; a post-claim crash is reported as
uncertain and never re-dispatched.
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
import uuid
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


def _child_env(scratch: Path, port: int, extra: dict | None = None) -> dict:
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
    if extra:
        env.update({str(key): str(value) for key, value in extra.items()})
    (scratch / "data").mkdir(parents=True, exist_ok=True)
    (scratch / "lance").mkdir(parents=True, exist_ok=True)
    return env


def _spawn(scratch: Path, log_name: str, extra_env: dict | None = None):
    scratch.mkdir(parents=True, exist_ok=True)
    port = _free_port()
    log_path = scratch / log_name
    log = log_path.open("a", encoding="utf-8")
    proc = subprocess.Popen(
        [PROJECT_PYTHON, str(WORKER)],
        cwd=str(BACKEND),
        env=_child_env(scratch, port, extra_env),
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    return proc, port, log, log_path


def _await_health(proc, port: int, log, log_path: Path):
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


def _seed_completed_wait_history(scratch: Path, count: int = 20) -> list:
    """Create real completed job/execution/wait rows, as durable history."""
    connection = sqlite3.connect(scratch / "probe.db")
    action_ids = []
    try:
        for index in range(count):
            job_id = str(uuid.uuid4())
            execution_id = str(uuid.uuid4())
            action_id = str(uuid.uuid4())
            correlation_id = str(uuid.uuid4())
            action_ids.append(action_id)
            payload = {
                "execution_id": execution_id,
                "dispatch_execution_id": execution_id,
                "wait_receipt": {
                    "hitl_action_id": action_id,
                    "correlation_id": correlation_id,
                    "verified": True,
                    "kind": "information_request",
                },
                "waiting": False,
                "finished": True,
                "status": "success",
                "outcome": "success",
                "reason": "execution_succeeded",
                "next_action": "none",
            }
            subject = {
                "job_id": job_id,
                "execution_id": execution_id,
                "agent_id": "a1",
                "workspace_id": "ws1",
            }
            snapshot = {
                "job_id": job_id,
                "execution_id": execution_id,
                "run_id": execution_id,
                "agent_id": "a1",
                "workspace_id": "ws1",
                "tenant_id": "t1",
                "actor_id": "member-1",
                "user_id": "member-1",
                "correlation_id": correlation_id,
                "channel": "user:member-1",
                "question": f"Historical question {index}",
                "subject": subject,
            }
            params = {
                "question": f"Historical question {index}",
                "subject": subject,
                "correlation_id": correlation_id,
                "channel": "user:member-1",
            }
            connection.execute(
                "insert into agent_jobs "
                "(id,tenant_id,agent_id,status,start_time,result_summary) "
                "values (?,?,?,?,?,?)",
                (job_id, "t1", "a1", "success",
                 f"2026-01-01 00:{index:02d}:00", json.dumps(payload)))
            connection.execute(
                "insert into agent_executions "
                "(id,agent_id,tenant_id,workspace_id,status,metadata_json) "
                "values (?,?,?,?,?,?)",
                (execution_id, "a1", "t1", "ws1", "completed", "{}"))
            connection.execute(
                "insert into hitl_actions "
                "(id,workspace_id,tenant_id,agent_id,user_id,action_type,"
                "platform,params,reason,status,user_feedback,"
                "context_snapshot,created_at) "
                "values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (action_id, "ws1", "t1", "a1", "member-1",
                 "agent_information_request", "internal",
                 json.dumps(params), "historical wait", "approved", ANSWER,
                 json.dumps(snapshot), f"2026-01-01 00:{index:02d}:00"))
        connection.commit()
    finally:
        connection.close()
    return action_ids


def _start(scratch: Path, log_name: str, extra_env: dict | None = None):
    return _await_health(*_spawn(scratch, log_name, extra_env))


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


def _call_disconnect(port: int, path: str, body):
    """POST to a worker that is expected to hard-exit mid-request."""
    data = json.dumps(body).encode()
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
        return None, None


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
        scratch,
        "select id,status,action_type,user_feedback,context_snapshot "
        "from hitl_actions")
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


def _stop(proc, log, *, kill: bool) -> int:
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
    return proc.returncode


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


def _begin_wait(scratch: Path, log_name: str):
    """Run one admitted job to a durable wait, then hard-kill its process."""
    proc, port, log, log_path = _start(scratch, log_name)
    try:
        status, started = _call(
            port,
            "/api/agents/a1/run?operation_id=generic-process-recovery",
            {"parameters": {
                "sync": True,
                "task_input": "Create the closing task",
            }},
        )
        assert status == 202, (status, started)
        data = started["data"]
        assert data["job_status"] == "waiting", data
        assert data["wait_receipt"]["correlation_id"], data
        payload = (
            data["job_id"], data["execution_id"], data["wait_receipt"],
            proc.pid, log_path)
    finally:
        _stop(proc, log, kill=True)
    return payload


def test_actual_process_startup_resumes_accepted_answer_after_crash_before_claim(
        tmp_path):
    """Accepted answer survives a crash before claim and wakes the same job.

    The answer route commits HITLAction approved + user_feedback, then the
    second process hard-exits before the resume consumer claims the job. A
    fresh process running the same bounded startup join must resume the SAME
    job/execution from the durable row exactly once; a second restart is inert.
    """
    _require_python()
    scratch = tmp_path / "generic-accepted-answer-world"
    job_id, execution_id, receipt, first_pid, _ = _begin_wait(
        scratch, "accepted-first.log")

    crashing, crashing_port, crashing_log, _ = _start(
        scratch, "accepted-answer-crash.log",
        {"GENERIC_WAIT_CRASH": "before_claim"})
    try:
        status, body = _call_disconnect(
            crashing_port,
            f"/api/agents/a1/jobs/{job_id}/answer",
            {"answer": ANSWER, "correlation_id": receipt["correlation_id"]},
        )
        assert status is None, body
    finally:
        crash_exit = _stop(crashing, crashing_log, kill=False)
    assert crash_exit == 17, crash_exit
    assert crashing.pid != first_pid

    accepted = _state(scratch)
    assert accepted["jobs"][0]["id"] == job_id, accepted
    assert accepted["jobs"][0]["status"] == "waiting", accepted
    assert accepted["executions"][0]["id"] == execution_id, accepted
    assert accepted["executions"][0]["status"] == "waiting", accepted
    assert accepted["waits"][0]["status"] == "approved", accepted
    assert accepted["waits"][0]["user_feedback"] == ANSWER, accepted
    assert accepted["tasks"] == [], accepted
    assert json.loads((scratch / "phase.json").read_text())["step"] == 1

    recovering, _, recovering_log, _ = _start(
        scratch, "accepted-recovery.log",
        {"GENERIC_WAIT_RECOVER_ACCEPTED": "1"})
    try:
        recovery = json.loads(
            (scratch / f"accepted-recovery-{recovering.pid}.json").read_text())
        assert recovery["ran"] is True, recovery
        assert recovery["result"]["resumed"] == 1, recovery
        assert recovery["result"]["refused"] == 0, recovery
        detail = recovery["result"]["details"][0]
        assert detail["status"] == "resumed", detail
        assert detail["job_id"] == job_id, detail
        assert detail["execution_id"] == execution_id, detail

        after = _state(scratch)
        assert after["jobs"][0]["id"] == job_id, after
        assert after["jobs"][0]["status"] == "success", after
        assert after["executions"][0]["id"] == execution_id, after
        assert after["executions"][0]["status"] == "success", after
        assert len(after["tasks"]) == 1, after
        assert after["tasks"][0]["title"] == ANSWER, after
        phase = json.loads((scratch / "phase.json").read_text())
        assert phase["step"] == 3, phase
        assert "AUTHORIZED INFORMATION ANSWER" in phase["prompts"][1], phase
        assert ANSWER in phase["prompts"][1], phase
    finally:
        _stop(recovering, recovering_log, kill=False)

    # A second restart must not re-dispatch the already completed answer.
    again, _, again_log, _ = _start(
        scratch, "accepted-recovery-again.log",
        {"GENERIC_WAIT_RECOVER_ACCEPTED": "1"})
    try:
        second_recovery = json.loads(
            (scratch / f"accepted-recovery-{again.pid}.json").read_text())
        assert second_recovery["ran"] is True, second_recovery
        assert second_recovery["result"]["resumed"] == 0, second_recovery
        assert second_recovery["result"]["uncertain"] == 0, second_recovery
        final = _state(scratch)
        assert len(final["tasks"]) == 1, final
        assert final["tasks"][0]["title"] == ANSWER, final
        assert json.loads(
            (scratch / "phase.json").read_text())["step"] == 3
    finally:
        _stop(again, again_log, kill=False)


def test_actual_process_concurrent_startup_wakes_accepted_answer_once(
        tmp_path):
    """Two real startup processes race one accepted answer: exactly one wakes."""
    _require_python()
    scratch = tmp_path / "generic-concurrent-recovery-world"
    job_id, execution_id, receipt, first_pid, _ = _begin_wait(
        scratch, "concurrent-first.log")

    crashing, crashing_port, crashing_log, _ = _start(
        scratch, "concurrent-answer-crash.log",
        {"GENERIC_WAIT_CRASH": "before_claim"})
    try:
        status, _body = _call_disconnect(
            crashing_port,
            f"/api/agents/a1/jobs/{job_id}/answer",
            {"answer": ANSWER, "correlation_id": receipt["correlation_id"]},
        )
        assert status is None
    finally:
        crash_exit = _stop(crashing, crashing_log, kill=False)
    assert crash_exit == 17, crash_exit
    assert crashing.pid != first_pid

    gate = scratch / "recovery-gate"
    env = {
        "GENERIC_WAIT_RECOVER_ACCEPTED": "1",
        "GENERIC_WAIT_RECOVERY_GATE": str(gate),
    }
    a_proc, a_port, a_log, a_path = _spawn(
        scratch, "concurrent-recovery-a.log", env)
    b_proc, b_port, b_log, b_path = _spawn(
        scratch, "concurrent-recovery-b.log", env)
    try:
        deadline = time.time() + 120
        while time.time() < deadline:
            if a_proc.poll() is not None or b_proc.poll() is not None:
                raise AssertionError(
                    "a concurrent recovery worker exited before the race: "
                    f"a={a_proc.returncode} b={b_proc.returncode}\n"
                    f"a-log={a_path.read_text()[-3000:]}\n"
                    f"b-log={b_path.read_text()[-3000:]}")
            ready = list(scratch.glob("recovery-ready-*.json"))
            if len(ready) >= 2:
                break
            time.sleep(0.05)
        else:
            raise AssertionError("both recovery workers never reached the gate")
        gate.write_text("go")
        _await_health(a_proc, a_port, a_log, a_path)
        _await_health(b_proc, b_port, b_log, b_path)

        reports = [
            json.loads(
                (scratch / f"accepted-recovery-{proc.pid}.json").read_text())
            for proc in (a_proc, b_proc)
        ]
        assert all(report["ran"] for report in reports), reports
        resumed = [report["result"]["resumed"] for report in reports]
        assert sorted(resumed) == [0, 1], reports
        assert sum(report["result"]["uncertain"] for report in reports) == 0

        after = _state(scratch)
        assert after["jobs"][0]["id"] == job_id, after
        assert after["jobs"][0]["status"] == "success", after
        assert after["executions"][0]["id"] == execution_id, after
        assert after["executions"][0]["status"] == "success", after
        assert len(after["tasks"]) == 1, after
        assert after["tasks"][0]["title"] == ANSWER, after
        assert json.loads(
            (scratch / "phase.json").read_text())["step"] == 3
    finally:
        _stop(a_proc, a_log, kill=False)
        _stop(b_proc, b_log, kill=False)


def test_actual_process_recovery_selects_new_wait_behind_completed_history(
        tmp_path):
    """20 completed approved waits must not hide the 21st live accepted wait."""
    _require_python()
    scratch = tmp_path / "generic-history-world"
    job_id, execution_id, receipt, first_pid, _ = _begin_wait(
        scratch, "history-first.log")

    crashing, crashing_port, crashing_log, _ = _start(
        scratch, "history-answer-crash.log",
        {"GENERIC_WAIT_CRASH": "before_claim"})
    try:
        status, _body = _call_disconnect(
            crashing_port,
            f"/api/agents/a1/jobs/{job_id}/answer",
            {"answer": ANSWER, "correlation_id": receipt["correlation_id"]},
        )
        assert status is None
    finally:
        crash_exit = _stop(crashing, crashing_log, kill=False)
    assert crash_exit == 17, crash_exit
    assert crashing.pid != first_pid

    history_ids = _seed_completed_wait_history(scratch, 20)

    recovering, _, recovering_log, _ = _start(
        scratch, "history-recovery.log",
        {"GENERIC_WAIT_RECOVER_ACCEPTED": "1"})
    try:
        recovery = json.loads(
            (scratch / f"accepted-recovery-{recovering.pid}.json").read_text())
        assert recovery["ran"] is True, recovery
        assert recovery["result"]["examined"] == 1, recovery
        assert recovery["result"]["resumed"] == 1, recovery
        assert recovery["result"]["details"][0]["job_id"] == job_id, recovery

        after_job = _query(
            scratch, "select id,status from agent_jobs where id=?", (job_id,))
        assert len(after_job) == 1 and after_job[0]["status"] == "success", (
            after_job)
        after_execution = _query(
            scratch, "select id,status from agent_executions where id=?",
            (execution_id,))
        assert len(after_execution) == 1, after_execution
        assert after_execution[0]["status"] == "success", after_execution
        tasks = _query(
            scratch, "select id,title,status from board_tasks")
        assert len(tasks) == 1, tasks
        assert tasks[0]["title"] == ANSWER, tasks
        assert json.loads(
            (scratch / "phase.json").read_text())["step"] == 3

        history = _query(
            scratch,
            "select id,status from hitl_actions where id in (%s)"
            % ",".join("?" for _ in history_ids), history_ids)
        assert len(history) == 20, history
        assert {row["status"] for row in history} == {"approved"}, history
    finally:
        _stop(recovering, recovering_log, kill=False)


def test_actual_process_interrupted_resume_claim_is_not_resent(tmp_path):
    """A crash AFTER the job claim is uncertain: report, never re-dispatch."""
    _require_python()
    scratch = tmp_path / "generic-claimed-answer-world"
    job_id, execution_id, receipt, first_pid, _ = _begin_wait(
        scratch, "claimed-first.log")

    crashing, crashing_port, crashing_log, _ = _start(
        scratch, "claimed-answer-crash.log",
        {"GENERIC_WAIT_CRASH": "after_claim"})
    try:
        status, body = _call_disconnect(
            crashing_port,
            f"/api/agents/a1/jobs/{job_id}/answer",
            {"answer": ANSWER, "correlation_id": receipt["correlation_id"]},
        )
        assert status is None, body
    finally:
        crash_exit = _stop(crashing, crashing_log, kill=False)
    assert crash_exit == 17, crash_exit
    assert crashing.pid != first_pid

    claimed = _state(scratch)
    assert claimed["jobs"][0]["id"] == job_id, claimed
    assert claimed["jobs"][0]["status"] == "running", claimed
    claim = claimed["jobs"][0]["result_summary"].get("resume_claim") or {}
    assert claim.get("action_id") == receipt["hitl_action_id"], claimed
    assert claim.get("execution_id") == execution_id, claimed
    assert claimed["executions"][0]["status"] == "waiting", claimed
    assert claimed["waits"][0]["status"] == "approved", claimed
    assert claimed["tasks"] == [], claimed
    assert json.loads((scratch / "phase.json").read_text())["step"] == 1

    recovering, _, recovering_log, _ = _start(
        scratch, "claimed-recovery.log",
        {"GENERIC_WAIT_RECOVER_ACCEPTED": "1"})
    try:
        recovery = json.loads(
            (scratch / f"accepted-recovery-{recovering.pid}.json").read_text())
        assert recovery["ran"] is True, recovery
        assert recovery["result"]["resumed"] == 0, recovery
        assert recovery["result"]["uncertain"] == 1, recovery
        detail = recovery["result"]["details"][0]
        assert detail["status"] == "uncertain", detail
        assert detail["reason"] == "resume_claim_interrupted_uncertain", detail

        after = _state(scratch)
        assert after["jobs"][0]["status"] == "failed", after
        assert after["jobs"][0]["result_summary"][
            "requires_reconciliation"] is True, after
        assert after["jobs"][0]["result_summary"]["reason"] == (
            "execution_uncertain"), after
        assert after["executions"][0]["status"] == "failed", after
        assert after["tasks"] == [], after
        # No model continuation happened: the only scripted step is the wait.
        assert json.loads((scratch / "phase.json").read_text())["step"] == 1
    finally:
        _stop(recovering, recovering_log, kill=False)


def test_recovery_join_is_a_bounded_async_startup_pass():
    """The join is async and explicitly bounded, for the lifespan hook."""
    import inspect

    import core.information_wait as information_wait

    assert inspect.iscoroutinefunction(
        information_wait.recover_accepted_information_waits)
    signature = inspect.signature(
        information_wait.recover_accepted_information_waits)
    assert signature.parameters["limit"].default == 20

