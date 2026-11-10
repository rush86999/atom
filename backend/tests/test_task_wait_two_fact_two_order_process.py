"""TASK-WAIT-01 joined two-fact, both-order, actual-process acceptance.

This closes the coverage gap left by the existing controls:

* the two-fact in-process test proves invoice -> receiving on one assignment;
* the G5 two-order packet proves one missing fact in both restart orders with a
  served model;
* the actual-process recovery tests prove one missing fact with a real child
  process.

Here one assignment has two distinct missing facts, in both arrival orders,
across real OS processes, with no model/provider call. The controlled proposal
transport selects the actual missing role; it never supplies a final plan or
expected result.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from zipfile import ZipFile

import pytest

BACKEND = Path(__file__).resolve().parents[1]
WORKER = Path(__file__).resolve().parent / "process_support" / (
    "task_wait_two_fact_process_worker.py")
PROJECT_PYTHON = os.getenv("ATOM_TEST_PYTHON", sys.executable)

PO = "PO-TWO-ORDER-1"
INVOICE = "INV-TWO-ORDER-1"
EXPECTED_TOTAL = "140.25"


def _write_facts(scratch: Path) -> None:
    sources = scratch / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    (sources / "po.json").write_text(json.dumps({
        "po_id": PO, "vendor_id": "V-7", "quantity": "3",
        "unit_price": "42.50", "freight": "12.75", "currency": "USD"}))
    (sources / "receiving.json").write_text(json.dumps({
        "po_id": PO, "received_quantity": "3"}))
    (sources / "invoice.json").write_text(json.dumps({
        "po_id": PO, "invoice_id": INVOICE, "quantity": "3",
        "unit_price": "42.50", "freight": "12.75", "currency": "USD"}))


def _child_env(scratch: Path) -> dict:
    env = dict(os.environ)
    for key in (
            "PYTEST_CURRENT_TEST", "PYTEST_VERSION",
            "ATOM_DATA_DIR", "ATOM_LANCEDB_PATH", "DATABASE_URL"):
        env.pop(key, None)
    env.update({
        "PYTHONPATH": str(BACKEND),
        "PYTHONDONTWRITEBYTECODE": "1",
        "ATOM_TASK_WAIT_SCRATCH": str(scratch),
        "ATOM_ASSIGNMENT_EVIDENCE_RECOVERY_CLAIM_TTL": "20",
    })
    return env


def _spawn(scratch: Path, phase: str, *, order: str = "",
           run_id: str = "", first_role: str = "",
           second_role: str = "", timeout: int = 240):
    reports = scratch / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    stamp = f"{phase}-{os.getpid()}-{time.time_ns()}"
    report = reports / f"{stamp}.json"
    cmd = [
        PROJECT_PYTHON, str(WORKER),
        "--phase", phase,
        "--scratch", str(scratch),
        "--report", str(report),
    ]
    if order:
        cmd.extend(["--order", order])
    if run_id:
        cmd.extend(["--run-id", run_id])
    if first_role:
        cmd.extend(["--first-role", first_role])
    if second_role:
        cmd.extend(["--second-role", second_role])
    proc = subprocess.run(
        cmd, cwd=str(BACKEND), env=_child_env(scratch),
        capture_output=True, text=True, timeout=timeout)
    payload = json.loads(report.read_text()) if report.exists() else None
    entry = {
        "phase": phase,
        "pid": (payload or {}).get("pid"),
        "exit": proc.returncode,
        "report": report.name,
    }
    with (scratch / "process-log.jsonl").open("a") as log:
        log.write(json.dumps(entry, sort_keys=True) + "\n")
    return proc, payload


def _require_python() -> None:
    if not Path(PROJECT_PYTHON).exists():
        pytest.fail(
            f"configured child Python {PROJECT_PYTHON!r} is absent; "
            "actual-process acceptance requires an executable interpreter")


def _fail_message(proc, payload) -> str:
    return (
        f"child exit={proc.returncode}\n"
        f"stdout:\n{proc.stdout[-4000:]}\n"
        f"stderr:\n{proc.stderr[-4000:]}\n"
        f"report={json.dumps(payload, indent=2, default=str)[-6000:]}")


@pytest.mark.parametrize("order,first,second", [
    ("invoice", "invoice", "receiving"),
    ("receiving", "receiving", "invoice"),
])
def test_two_facts_both_orders_survive_restart_and_publish_one_current_artifact(
        tmp_path, order, first, second):
    _require_python()
    scratch = tmp_path / f"process-world-{order}"
    _write_facts(scratch)

    start_proc, started = _spawn(
        scratch, "start", order=order, first_role=first)
    assert start_proc.returncode == 0, _fail_message(start_proc, started)
    run_id = started["run_id"]
    assert started["open_questions"], started
    assert len(started["open_questions"]) == 1, started
    assert first in started["adaptation_call_log"][-1]["missing"], started
    assert started["adaptation_call_log"][-1]["chosen"] == first, started
    assert started["reconciliations"] == [], started
    assert started["artifacts"] == [], started
    assert started["status"] != "completed", started

    first_proc, after_first = _spawn(
        scratch, "source-first", run_id=run_id, first_role=first)
    assert first_proc.returncode == 0, _fail_message(
        first_proc, after_first)
    assert after_first["source_response_status"] == 200, after_first
    assert after_first["run_id"] == run_id, after_first
    assert after_first["objective"] == started["objective"], after_first
    assert len(after_first["open_questions"]) == 1, after_first
    assert after_first["adaptation_call_log"][-1]["missing"] == [second], (
        after_first)
    assert after_first["reconciliations"] == [], after_first
    assert after_first["artifacts"] == [], after_first
    assert after_first["status"] != "completed", after_first

    restart_proc, recovered = _spawn(
        scratch, "startup-recover", run_id=run_id)
    assert restart_proc.returncode == 0, _fail_message(
        restart_proc, recovered)
    assert recovered["pid"] != after_first["pid"], (
        "this must be a real second process")
    assert recovered["run_id"] == run_id, recovered
    assert recovered["objective"] == started["objective"], recovered
    assert len(recovered["open_questions"]) == 1, recovered
    assert recovered["adaptation_calls"] == 0, (
        "fresh recovery process must not model-poll while the second fact is missing")
    assert recovered["reconciliations"] == [], recovered
    assert recovered["artifacts"] == [], recovered
    assert recovered["status"] != "completed", recovered

    second_proc, final = _spawn(
        scratch, "source-second", run_id=run_id, second_role=second)
    assert second_proc.returncode == 0, _fail_message(second_proc, final)
    assert final["pid"] not in (started["pid"], after_first["pid"]), (
        "the source answer must be consumed by a fresh process")
    assert final["run_id"] == run_id, final
    assert final["objective"] == started["objective"], final
    assert final["status"] == "completed", final
    assert final["open_questions"] == [], final
    assert len(final["reconciliations"]) == 1, final
    assert final["reconciliations"][0]["result_value"] == EXPECTED_TOTAL, final
    assert len(final["artifacts"]) == 1, final
    source_steps = final["source_steps"]
    assert len(source_steps) >= 2, source_steps
    assert all(step["status"] == "applied" for step in source_steps), source_steps
    assert all(step["source_version"] for step in source_steps), source_steps
    source_data = [step.get("result_data") or {} for step in source_steps]
    assert any(item.get("invoice_id") == INVOICE for item in source_data), source_data
    assert any(item.get("received_quantity") == "3" for item in source_data), source_data

    artifact = final["artifacts"][0]
    artifact_path = Path(artifact["path"])
    assert artifact_path.exists(), artifact
    assert artifact_path.is_relative_to(scratch), artifact
    with open(artifact_path, "rb") as handle:
        import hashlib
        assert hashlib.sha256(handle.read()).hexdigest() == artifact["sha256"]
    with ZipFile(artifact_path) as document:
        xml = document.read("word/document.xml").decode("utf-8")
    assert EXPECTED_TOTAL in xml, "the final document must carry the current verified total"

    duplicate_proc, duplicate = _spawn(
        scratch, "duplicate-second", run_id=run_id, second_role=second)
    assert duplicate_proc.returncode == 0, _fail_message(
        duplicate_proc, duplicate)
    assert duplicate["source_response_status"] == 200, duplicate
    assert len(duplicate["reconciliations"]) == 1, duplicate
    assert len(duplicate["artifacts"]) == 1, duplicate
    assert duplicate["adaptation_calls"] == 0, duplicate
    assert duplicate["status"] == "completed", duplicate
