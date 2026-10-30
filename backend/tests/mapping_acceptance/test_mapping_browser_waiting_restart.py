"""Workbook B: reject the mapping proposal, restart, then confirm Amount.

The same assignment and the same outstanding request must survive a backend
restart. Rejection is an acknowledgement only: it must not apply a mapping,
write a result, or change teaching. The corrected workbook then completes at
35.00 USD with exactly one accepted mapping update.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import docx
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from test_mapping_browser_b import (  # noqa: E402
    BACKEND,
    FRONTEND_BUILD,
    REPO,
    _attempt_dir,
    _call,
    _evidence_identity,
    _port_free,
    _seed,
    _server_source,
    _wait,
)

TMP = Path(
    "/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/"
    "mapping_waiting_restart_acceptance")
BASE = "http://127.0.0.1:8071"
FRONTEND = "http://127.0.0.1:3130"
PASSWORD = "MappingPass123!"
OBJECTIVE = "Waiting restart price total"


def _start_backend(env: dict) -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "--app-dir", str(TMP),
         "mapping_server:app", "--host", "127.0.0.1", "--port", "8071"],
        cwd=BACKEND, env=env,
        stdout=(TMP / "backend.log").open("ab"), stderr=subprocess.STDOUT,
        start_new_session=True)
    _wait(f"{BASE}/api/health")
    return proc


def _stop(proc: subprocess.Popen) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:
        pass
    try:
        proc.wait(timeout=20)
    except Exception:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            pass
    deadline = time.time() + 20
    while time.time() < deadline and not _port_free(8071):
        time.sleep(0.25)


def _login(page) -> None:
    page.goto(f"{FRONTEND}/login", wait_until="domcontentloaded")
    page.get_by_test_id("login-email-input").fill("admin@example.com")
    page.get_by_test_id("login-password-input").fill(PASSWORD)
    page.get_by_test_id("login-submit-button").click()
    page.wait_for_url("**/dashboard", timeout=30000)


def _open_assignment(page):
    page.goto(f"{FRONTEND}/assignments", wait_until="domcontentloaded")
    page.get_by_text(OBJECTIVE).first.wait_for(timeout=30000)
    page.get_by_role("button").filter(has_text=OBJECTIVE).first.click()
    detail = page.get_by_test_id("assignment-detail")
    detail.wait_for(timeout=30000)
    objective = detail.get_by_test_id("assignment-detail-objective")
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            if OBJECTIVE in objective.inner_text():
                break
        except Exception:
            pass
        time.sleep(0.25)
    assert OBJECTIVE in objective.inner_text(), objective.inner_text()
    return detail


def _durable_parameters(root: Path, run_id: str) -> str:
    con = sqlite3.connect(f"file:{root / 'atom.db'}?mode=ro", uri=True)
    try:
        row = con.execute(
            "select parameters from goal_runs where id=?", (run_id,)).fetchone()
        assert row is not None, f"no durable run {run_id}"
        return row[0]
    finally:
        con.close()


def _durable_assignment(root: Path, run_id: str) -> dict:
    return json.loads(_durable_parameters(root, run_id))[
        "task_lifecycle"]["assignment"]


def _lesson_config(root: Path, agent_id: str) -> dict:
    con = sqlite3.connect(f"file:{root / 'atom.db'}?mode=ro", uri=True)
    try:
        row = con.execute(
            "select configuration from agent_registry where id=?",
            (agent_id,)).fetchone()
        assert row is not None
        return json.loads(row[0] or "{}")
    finally:
        con.close()


def _lesson_mapping(config: dict) -> dict:
    for entry in (config.get("learning") or {}).get("log") or []:
        for mapping in (entry.get("context") or {}).get(
                "field_mappings") or []:
            if str(mapping.get("concept") or "").lower() == "price":
                return dict(mapping)
    raise AssertionError("Price mapping was not persisted on the lesson")


def _mapping(assignment: dict) -> dict:
    for item in (assignment.get("teaching_snapshot") or {}).get(
            "field_mappings") or []:
        if str(item.get("concept") or "").lower() == "price":
            return dict(item)
    raise AssertionError("Price mapping is missing")


def _step(assignment: dict, step_id: str) -> dict:
    return next(
        step for step in assignment.get("steps") or []
        if step.get("step_id") == step_id)


def _artifact(assignment: dict) -> dict:
    return next(
        item for item in assignment.get("deliverables") or []
        if item.get("kind") == "document")


def _docx_text(path: str) -> str:
    document = docx.Document(path)
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def _gap_identity(detail: dict) -> dict:
    gap = next(
        item for item in detail.get("open_gaps") or []
        if (item.get("inputs") or {}).get("mapping"))
    mapping = dict(gap["inputs"]["mapping"])
    return {
        "question_id": gap["question_id"],
        "assignment_id": detail["assignment"]["assignment_id"],
        "objective": detail["assignment"]["objective"],
        "teaching_revision": detail["assignment"].get("teaching_revision"),
        "source_version": mapping.get("source_version"),
        "mapping_teaching_revision": mapping.get("teaching_revision"),
        "required_unit": mapping.get("required_unit"),
        "source_unit": mapping.get("source_unit"),
        "candidates": [
            {
                "column": item.get("column"),
                "sample_values": item.get("sample_values"),
                "inferred_type": item.get("inferred_type"),
            }
            for item in mapping.get("candidates") or []
        ],
        "mapping": mapping,
    }


@pytest.mark.timeout(600)
def test_mapping_waiting_restart_reject_then_confirm():
    if not _port_free(8071) or not _port_free(3130):
        pytest.skip("ports 8071/3130 are in use; isolated harness requires them free")
    guard = subprocess.run(
        [sys.executable, "-m", "core.world_storage_guard", "check"],
        cwd=BACKEND, capture_output=True, text=True)
    assert guard.returncode == 0, guard.stderr + guard.stdout
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True)
    (TMP / "office" / "assignments").mkdir(parents=True)
    meta = _seed(TMP)
    assert meta["expected"] == "35.00"

    server_file = TMP / "mapping_server.py"
    server_file.write_text(_server_source(TMP))
    frontend = TMP / "frontend"
    shutil.copytree(FRONTEND_BUILD / "standalone", frontend)
    (frontend / ".next").mkdir(exist_ok=True)
    shutil.copytree(FRONTEND_BUILD / "static", frontend / ".next" / "static")
    if (REPO / "frontend-nextjs" / "public").is_dir():
        shutil.copytree(
            REPO / "frontend-nextjs" / "public", frontend / "public",
            dirs_exist_ok=True)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(BACKEND)
    env["SECRET_KEY"] = "mapping-waiting-restart-harness-secret"
    backend = _start_backend(env)
    frontend_proc = subprocess.Popen(
        ["node", "server.js"], cwd=frontend,
        env={**env, "PORT": "3130", "HOSTNAME": "127.0.0.1"},
        stdout=(TMP / "frontend.log").open("wb"), stderr=subprocess.STDOUT,
        start_new_session=True)
    try:
        _wait(f"{FRONTEND}/login")
        status, login = _call(
            BASE, "POST", "/api/auth/login",
            {"username": "admin@example.com", "password": PASSWORD})
        assert status == 200 and login.get("access_token"), login
        token = login["access_token"]

        # 1. Start workbook B and reach the unresolved mapping.
        status, created = _call(
            BASE, "POST", "/api/assignments", {
                "objective": OBJECTIVE,
                "agent_id": meta["agent_id"],
                "sources": [{
                    "kind": "workbook",
                    "dataset_name": meta["dataset_name"],
                    "source": "outlook",
                    "external_id": "fixture-b",
                    "source_version": meta["source_version"],
                    "sheet": meta["sheet"],
                }],
                "calculation": {"aggregate": {
                    "operation": "sum", "value_column": "Price"}},
                "deliverables": [{"kind": "document",
                                  "description": "Waiting restart total"}],
            }, token)
        assert status == 200, created
        run_id = created["run_id"]
        assignment_id = created["assignment"]["assignment"]["assignment_id"]
        status, initial_detail = _call(
            BASE, "GET", f"/api/assignments/{run_id}", token=token)
        assert status == 200, initial_detail
        initial = _gap_identity(initial_detail)
        assert initial["assignment_id"] == assignment_id
        assert initial["objective"] == OBJECTIVE
        assert initial["source_version"] == meta["source_version"]
        assert initial["mapping_teaching_revision"] == (
            initial["teaching_revision"])
        assert initial["required_unit"] == "USD"
        assert initial["source_unit"] == "USD"
        assert "Amount" in [
            item["column"] for item in initial["candidates"]]
        assert "Discount" in [
            item["column"] for item in initial["candidates"]]

        params_before_reject = _durable_parameters(TMP, run_id)
        assignment_before_reject = _durable_assignment(TMP, run_id)
        lesson_before_reject = _lesson_config(TMP, meta["agent_id"])
        assert _step(assignment_before_reject, "source-1")["result"] is None
        assert _mapping(assignment_before_reject)["column"] == "Unit Price"

        from playwright.sync_api import sync_playwright
        attempt_dir = _attempt_dir("waiting-restart", run_id)
        attempt_dir.mkdir(parents=True, exist_ok=True)

        # 2-3. Reject through the panel; objective and request stay open.
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1200})
            _login(page)
            detail_el = _open_assignment(page)
            candidates = detail_el.get_by_test_id("mapping-candidates")
            candidates.wait_for(timeout=30000)
            candidate_text = candidates.inner_text()
            assert "Amount" in candidate_text
            assert "Discount" in candidate_text
            page.screenshot(path=str(attempt_dir / "unresolved-before-reject.png"),
                            full_page=True)
            detail_el.get_by_test_id("mapping-reject").click()
            notice = page.get_by_test_id("assignment-notice")
            notice.wait_for(timeout=30000)
            assert "same request remains open" in notice.inner_text().lower()
            candidates = detail_el.get_by_test_id("mapping-candidates")
            candidates.wait_for(timeout=30000)
            assert "Amount" in candidates.inner_text()
            assert OBJECTIVE in detail_el.get_by_test_id(
                "assignment-detail-objective").inner_text()
            assert detail_el.get_by_test_id(
                "assignment-result-source-1").count() == 0
            page.screenshot(path=str(attempt_dir / "rejected-still-open.png"),
                            full_page=True)
            browser.close()

        # Rejection is an acknowledgement, not an execution or teaching write.
        assert _durable_parameters(TMP, run_id) == params_before_reject
        assignment_after_reject = _durable_assignment(TMP, run_id)
        assert assignment_after_reject == assignment_before_reject
        assert _lesson_config(TMP, meta["agent_id"]) == lesson_before_reject
        status, rejected_detail = _call(
            BASE, "GET", f"/api/assignments/{run_id}", token=token)
        assert status == 200, rejected_detail
        rejected_gap = _gap_identity(rejected_detail)
        assert rejected_gap["question_id"] == initial["question_id"]
        assert rejected_gap["candidates"] == initial["candidates"]
        assert rejected_gap["teaching_revision"] == initial["teaching_revision"]

        saved_identity = {
            "run_id": run_id,
            "assignment_id": assignment_id,
            "question_id": initial["question_id"],
            "objective": initial["objective"],
            "source_version": initial["source_version"],
            "teaching_revision": initial["teaching_revision"],
            "mapping_teaching_revision": initial[
                "mapping_teaching_revision"],
            "required_unit": initial["required_unit"],
            "source_unit": initial["source_unit"],
        }

        # 5. Restart ONLY the backend against the same stores.
        _stop(backend)
        backend = _start_backend(env)
        status, login_after = _call(
            BASE, "POST", "/api/auth/login",
            {"username": "admin@example.com", "password": PASSWORD})
        assert status == 200 and login_after.get("access_token"), login_after
        token_after = login_after["access_token"]

        # 6-7. Reopen through normal authentication; same request survives.
        status, after_restart = _call(
            BASE, "GET", f"/api/assignments/{run_id}", token=token_after)
        assert status == 200, after_restart
        reopened = _gap_identity(after_restart)
        assert reopened["assignment_id"] == assignment_id
        assert reopened["question_id"] == initial["question_id"]
        assert reopened["objective"] == OBJECTIVE
        assert reopened["source_version"] == meta["source_version"]
        assert reopened["teaching_revision"] == initial["teaching_revision"]
        assert reopened["mapping_teaching_revision"] == (
            initial["mapping_teaching_revision"])
        assert reopened["candidates"] == initial["candidates"]
        assert _durable_parameters(TMP, run_id) == params_before_reject

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1200})
            _login(page)
            detail_el = _open_assignment(page)
            candidates = detail_el.get_by_test_id("mapping-candidates")
            candidates.wait_for(timeout=30000)
            assert "Amount" in candidates.inner_text()
            assert "Discount" in candidates.inner_text()
            page.screenshot(
                path=str(attempt_dir / "reopened-after-restart.png"),
                full_page=True)

            # 8. Confirm Amount on the SAME request.
            detail_el.get_by_test_id("mapping-candidate-Amount").click()
            result_el = detail_el.get_by_test_id("assignment-result-source-1")
            result_el.wait_for(timeout=90000)
            deadline = time.time() + 60
            while time.time() < deadline:
                if "35.00" in result_el.inner_text():
                    break
                time.sleep(0.5)
            assert "35.00" in result_el.inner_text(), result_el.inner_text()
            detail_el.get_by_text("completed", exact=True).wait_for(
                timeout=60000)
            page.screenshot(
                path=str(attempt_dir / "confirmed-after-restart.png"),
                full_page=True)

            # 10. Reload and compare the user-visible state.
            page.reload(wait_until="domcontentloaded")
            detail_el = _open_assignment(page)
            result_el = detail_el.get_by_test_id("assignment-result-source-1")
            result_el.wait_for(timeout=30000)
            assert "35.00" in result_el.inner_text()
            assert "Amount" in detail_el.inner_text()
            page.screenshot(
                path=str(attempt_dir / "reloaded-after-confirm.png"),
                full_page=True)
            browser.close()

        status, final_detail = _call(
            BASE, "GET", f"/api/assignments/{run_id}", token=token_after)
        assert status == 200, final_detail
        assignment = final_detail["assignment"]
        assert assignment["assignment_id"] == assignment_id
        assert assignment["status"] == "completed"
        assert assignment["objective"] == OBJECTIVE
        mapping = _mapping(_durable_assignment(TMP, run_id))
        assert mapping["column"] == "Amount"
        assert mapping["revision"] == 2
        assert mapping["unit_authority"] == "source_evidence"
        assert mapping["required_unit"] == "USD"
        assert mapping["source_unit"] == "USD"

        durable = _durable_assignment(TMP, run_id)
        source_step = _step(durable, "source-1")
        assert source_step["result"]["value"] == "35.00"
        assert source_step["result"]["unit"] == "USD"
        artifact = _artifact(durable)
        assert Path(artifact["artifact_path"]).exists()
        assert hashlib.sha256(
            Path(artifact["artifact_path"]).read_bytes()).hexdigest() == (
                artifact["sha256"])
        assert "35.00" in _docx_text(artifact["artifact_path"])

        question = next(
            item for item in (
                json.loads(_durable_parameters(TMP, run_id))[
                    "task_lifecycle"]["task_revision"]["unresolved"]
            ) if item.get("question_id") == initial["question_id"])
        assert question["status"] == "resolved"
        assert initial["question_id"] in str(question.get("resolution"))
        operations = json.loads(_durable_parameters(TMP, run_id))[
            "task_lifecycle"]["operations"]
        applied = [
            op for op in operations
            if op.get("status") == "applied"
            and op.get("step_id") == "source-1"
        ]
        superseded = [
            op for op in operations
            if op.get("status") == "superseded"
            and op.get("step_id") == "source-1"
        ]
        assert len(applied) == 1
        assert len(superseded) == 1

        lesson_after = _lesson_config(TMP, meta["agent_id"])
        lesson_mapping = _lesson_mapping(lesson_after)
        assert lesson_mapping["column"] == "Amount"
        assert lesson_mapping["revision"] == 2
        assert len([
            item for item in (
                (lesson_after.get("learning") or {}).get("log") or [{}]
            )[0].get("context", {}).get("field_mappings") or []
            if item.get("concept") == "Price"
        ]) == 1

        # Reload/API compare: durable state did not fork after completion.
        durable_after_reload = _durable_parameters(TMP, run_id)
        status, reloaded_detail = _call(
            BASE, "GET", f"/api/assignments/{run_id}", token=token_after)
        assert status == 200, reloaded_detail
        assert _durable_parameters(TMP, run_id) == durable_after_reload
        assert _mapping(_durable_assignment(TMP, run_id)) == mapping
        assert _step(_durable_assignment(TMP, run_id), "source-1")[
            "result"]["value"] == "35.00"
        assert _artifact(_durable_assignment(TMP, run_id))["sha256"] == (
            artifact["sha256"])
        assert reloaded_detail["assignment"]["status"] == "completed"
        assert len(reloaded_detail["assignment"]["mappings"]) == 1
        assert reloaded_detail["assignment"]["mapping_history"] == []

        identity = _evidence_identity(Path(__file__))
        evidence = {
            "schema": "atom-mapping-waiting-restart-browser-1",
            "status": "passed",
            **identity,
            **saved_identity,
            "fixture": (
                "controlled acceptance workbook_b: Amount 35.00, "
                "Discount distractor; not live-connected"),
            "rejection": {
                "same_question_id": True,
                "same_candidates": True,
                "durable_unchanged": True,
                "teaching_unchanged": True,
                "no_result": True,
            },
            "restart": {
                "same_assignment_id": True,
                "same_question_id": True,
                "same_candidates": True,
                "same_source_version": True,
                "same_teaching_revision": True,
                "durable_unchanged": True,
            },
            "confirmation": {
                "question_id": initial["question_id"],
                "mapping": mapping,
                "result": source_step["result"]["value"],
                "unit": source_step["result"]["unit"],
                "artifact_path": artifact["artifact_path"],
                "artifact_sha256": artifact["sha256"],
                "applied_calculation_operations": len(applied),
                "superseded_calculation_operations": len(superseded),
                "question_status": question["status"],
                "lesson_mapping": lesson_mapping,
            },
            "reload": {
                "status": reloaded_detail["assignment"]["status"],
                "mapping": mapping,
                "result": "35.00",
                "artifact_sha256": artifact["sha256"],
                "mapping_history": reloaded_detail["assignment"][
                    "mapping_history"],
                "durable_unchanged": True,
            },
            "screenshots": [
                "unresolved-before-reject.png",
                "rejected-still-open.png",
                "reopened-after-restart.png",
                "confirmed-after-restart.png",
                "reloaded-after-confirm.png",
            ],
        }
        (attempt_dir / "result.json").write_text(
            json.dumps(evidence, indent=2) + "\n")
    finally:
        for proc in (frontend_proc, backend):
            try:
                _stop(proc) if proc is backend else os.killpg(
                    os.getpgid(proc.pid), signal.SIGTERM)
            except Exception:
                pass
        time.sleep(1)


if __name__ == "__main__":
    test_mapping_waiting_restart_reject_then_confirm()
