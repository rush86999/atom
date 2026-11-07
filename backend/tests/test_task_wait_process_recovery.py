"""TASK-WAIT-01 actual-process recovery acceptance.

These tests launch real OS child processes against one scratch SQLite/data
root. The children run the real public assignment router, compiler and
executor with the repository's existing controlled proposal transport. The
parent never reuses an in-process executor to stand in for a restart.

Negative control (before the repair): after ``source-interrupt`` durably
accepts/reads the invoice and settles the missing-invoice obligation, the
child hard-exits before adaptation. A successor process running only the
existing assignment recovery owner must finish the same task without a second
``/sources`` POST, ``/advance``, new objective, injected plan/result or model
polling while the material evidence is still missing.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
WORKER = Path(__file__).resolve().parent / "process_support" / (
    "task_wait_process_worker.py")
PROJECT_PYTHON = os.getenv(
    "ATOM_TEST_PYTHON",
    "/Users/rushiparikh/projects/atom/backend/venv314/bin/python")

PO = "PO-TRIGGER-63"
INVOICE = "INV-TRIGGER-91"
EXPECTED_TOTAL = "140.25"


def _write_facts(scratch: Path) -> None:
    sources = scratch / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    (sources / "po.json").write_text(json.dumps({
        "po_id": PO, "vendor_id": "V-6", "quantity": "3",
        "unit_price": "42.50", "freight": "12.75", "currency": "USD"}))
    (sources / "receiving.json").write_text(json.dumps({
        "po_id": PO, "received_quantity": "3"}))
    (sources / "invoice.json").write_text(json.dumps({
        "po_id": PO, "invoice_id": INVOICE, "quantity": "3",
        "unit_price": "42.50", "freight": "12.75", "currency": "USD"}))


def _child_env(scratch: Path) -> dict:
    env = dict(os.environ)
    # A pytest child must not think it is still the verifier's own process.
    for key in (
            "PYTEST_CURRENT_TEST", "PYTEST_VERSION",
            "ATOM_DATA_DIR", "ATOM_LANCEDB_PATH", "DATABASE_URL"):
        env.pop(key, None)
    env.update({
        "PYTHONPATH": str(BACKEND),
        "PYTHONDONTWRITEBYTECODE": "1",
        "ATOM_TASK_WAIT_SCRATCH": str(scratch),
    })
    return env


def _spawn(scratch: Path, phase: str, *, run_id: str = "",
           timeout: int = 240):
    reports = scratch / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    stamp = f"{phase}-{os.getpid()}-{time.time_ns()}"
    report = reports / f"{stamp}.json"
    checkpoint = reports / f"{stamp}-checkpoint.json"
    cmd = [
        PROJECT_PYTHON, str(WORKER),
        "--phase", phase,
        "--scratch", str(scratch),
        "--report", str(report),
        "--checkpoint", str(checkpoint),
    ]
    if run_id:
        cmd.extend(["--run-id", run_id])
    proc = subprocess.run(
        cmd, cwd=str(BACKEND), env=_child_env(scratch),
        capture_output=True, text=True, timeout=timeout)
    payload = None
    if report.exists():
        payload = json.loads(report.read_text())
    checkpoint_payload = None
    if checkpoint.exists():
        checkpoint_payload = json.loads(checkpoint.read_text())
    return proc, payload, checkpoint_payload


def _require_python() -> None:
    if not Path(PROJECT_PYTHON).exists():
        pytest.skip(
            f"project Python {PROJECT_PYTHON!r} is absent in this sandbox; "
            "the actual-process acceptance cannot be reproduced here")


def _reconciliations(payload: dict) -> list:
    return payload.get("reconciliations") or []


def _source_step(payload: dict) -> dict:
    steps = payload.get("source_steps") or []
    invoice = [
        step for step in steps
        if str((step.get("result_data") or {}).get("invoice_id") or "")
        == INVOICE]
    assert len(invoice) == 1, steps
    return invoice[0]


def _operation_ids(payload: dict) -> dict:
    return {
        str(step.get("step_id")): step.get("operation_id")
        for step in payload.get("steps") or []
        if step.get("operation_id")
    }


def _fail_message(proc, payload) -> str:
    return (
        f"child exit={proc.returncode}\n"
        f"stdout:\n{proc.stdout[-4000:]}\n"
        f"stderr:\n{proc.stderr[-4000:]}\n"
        f"report={json.dumps(payload, indent=2, default=str)[-6000:]}")


def test_actual_process_restart_does_not_model_poll_a_missing_prerequisite(
        tmp_path):
    """Restart while genuinely waiting: no model call, no advance, no result.

    The authorized invoice then arrives as a normal source through the real
    public route in the successor process; the same task must complete.
    """
    _require_python()
    scratch = tmp_path / "process-world"
    _write_facts(scratch)

    started_proc, started, _ = _spawn(scratch, "start")
    assert started_proc.returncode == 0, _fail_message(started_proc, started)
    assert started["open_questions"], started
    run_id = started["run_id"]

    missing_proc, missing, _ = _spawn(
        scratch, "startup-recover", run_id=run_id)
    assert missing_proc.returncode == 0, _fail_message(missing_proc, missing)
    assert missing["pid"] != started["pid"], "this must be a real second process"
    assert missing["adaptation_calls"] == 0, missing
    assert missing["reconciliations"] == [], missing
    assert missing["status"] != "completed", missing
    assert missing["open_questions"], missing

    answered_proc, answered, _ = _spawn(
        scratch, "source-complete", run_id=run_id)
    assert answered_proc.returncode == 0, _fail_message(
        answered_proc, answered)
    assert answered["run_id"] == run_id
    assert answered["objective"] == started["objective"]
    reconciliations = _reconciliations(answered)
    assert len(reconciliations) == 1, answered
    assert reconciliations[0]["result_value"] == EXPECTED_TOTAL
    assert answered["status"] == "completed", answered
    assert answered["open_questions"] == []
    assert answered["adaptation_calls"] == 1, answered


def test_actual_process_restart_recovers_accepted_source_without_replay(
        tmp_path):
    """Accept/read/settle, hard-exit before adaptation, recover on relaunch.

    The successor process runs only the existing assignment recovery owner.
    It must hand the durable accepted evidence to the same adaptation consumer
    exactly once. No source is re-posted and no advance/new objective/plan is
    supplied by the verifier; a later duplicate delivery stays inert.
    """
    _require_python()
    scratch = tmp_path / "process-world"
    _write_facts(scratch)

    started_proc, started, _ = _spawn(scratch, "start")
    assert started_proc.returncode == 0, _fail_message(started_proc, started)
    run_id = started["run_id"]
    assert started["open_questions"], started
    started_ops = _operation_ids(started)

    interrupt_proc, _, committed = _spawn(
        scratch, "source-interrupt", run_id=run_id)
    assert interrupt_proc.returncode == 17, _fail_message(
        interrupt_proc, committed)
    assert committed is not None, "the pre-exit checkpoint must be captured"
    assert committed["pid"] != started["pid"]
    assert committed["run_id"] == run_id
    assert committed["objective"] == started["objective"]
    assert committed["assignment_id"] == started["assignment_id"]
    assert committed["open_questions"] == [], committed
    assert committed["reconciliations"] == [], committed
    assert committed["status"] != "completed", committed
    assert committed["evidence_observations"], committed
    assert _source_step(committed)["status"] == "applied"
    committed_source = _source_step(committed)
    committed_ops = _operation_ids(committed)

    recovered_proc, recovered, _ = _spawn(
        scratch, "startup-recover", run_id=run_id)
    assert recovered_proc.returncode == 0, _fail_message(
        recovered_proc, recovered)
    assert recovered["pid"] not in (started["pid"], committed["pid"]), (
        "recovery must run in a fresh OS process")
    assert recovered["run_id"] == run_id
    assert recovered["objective"] == started["objective"]
    assert recovered["assignment_id"] == started["assignment_id"]
    assert recovered["open_questions"] == [], recovered
    assert recovered["adaptation_calls"] == 1, recovered
    assert recovered["status"] == "completed", recovered
    reconciliations = _reconciliations(recovered)
    assert len(reconciliations) == 1, recovered
    assert reconciliations[0]["result_value"] == EXPECTED_TOTAL

    # Original receipts survive recover; the accepted source is not re-read
    # under a new operation and prior applied reads keep their operation ids.
    recovered_source = _source_step(recovered)
    assert recovered_source["operation_id"] == committed_source["operation_id"]
    assert recovered_source["source_version"] == (
        committed_source["source_version"])
    assert recovered_source["status"] == "applied"
    recovered_ops = _operation_ids(recovered)
    for step_id, operation_id in committed_ops.items():
        if step_id in recovered_ops:
            assert recovered_ops[step_id] == operation_id, (
                step_id, committed_ops, recovered_ops)
    for step_id, operation_id in started_ops.items():
        if step_id in recovered_ops:
            assert recovered_ops[step_id] == operation_id, (
                step_id, started_ops, recovered_ops)

    # A later duplicate delivery is inert: no second dependent operation, no
    # second adaptation, and no second reconciliation.
    duplicate_proc, duplicate, _ = _spawn(
        scratch, "duplicate-source", run_id=run_id)
    assert duplicate_proc.returncode == 0, _fail_message(
        duplicate_proc, duplicate)
    assert duplicate["source_response"]["status"] == "already_present", (
        duplicate["source_response"])
    assert duplicate["adaptation_calls"] == 0, duplicate
    assert len(_reconciliations(duplicate)) == 1, duplicate
    assert duplicate["status"] == "completed", duplicate
    assert duplicate["run_id"] == run_id
