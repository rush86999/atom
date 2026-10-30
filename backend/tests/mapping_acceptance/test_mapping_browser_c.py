"""Workbook C: no source-established unit, explicit confirmation, 75.00 USD.

Controlled acceptance harness. It seeds a scratch database/parquet, starts the
real assignment/auth routes and uses the built Assignments panel. It does not
touch live sources, the pilot, the frozen release or any outbound transport.
"""
from __future__ import annotations

import json
import hashlib
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
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
    _server_source,
    _wait,
)
from fixtures import C_ROWS, expected_sum  # noqa: E402

TMP = Path(
    "/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/"
    "mapping_c_acceptance")
BASE = "http://127.0.0.1:8071"
FRONTEND = "http://127.0.0.1:3130"
PASSWORD = "MappingPass123!"


def _seed(root: Path) -> dict:
    os.environ["ATOM_DATA_DIR"] = str(root)
    os.environ["DATABASE_URL"] = f"sqlite:///{root / 'atom.db'}"
    os.environ["ATOM_OFFICE_DIR"] = str(root / "office")
    os.environ["ATOM_ASSIGNMENT_OUTPUT_DIR"] = str(root / "office" / "assignments")
    os.environ.pop("TESTING", None)
    sys.path.insert(0, str(BACKEND))
    from core.database import Base, SessionLocal, engine
    import core.models  # noqa: F401
    from core.models import AgentRegistry, IntegrationToken, User
    from core.auth import get_password_hash
    from core.sheet_dataset_service import materialize_sheet_bytes_sync
    from core.student_learning_service import journal_standing_lesson_entry

    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        db.add(User(
            id="map-user", email="admin@example.com",
            hashed_password=get_password_hash(PASSWORD),
            first_name="Map", last_name="User", role="workspace_admin",
            status="active", workspace_id="default", tenant_id="default",
            is_active=True))
        db.add(AgentRegistry(
            id="map-agent", name="Mapping Agent", category="operations",
            description="mapping acceptance", module_path="core.generic_agent",
            class_name="GenericAgent", status="intern", confidence_score=0.5,
            configuration={}, capabilities=[], workspace_id="default",
            tenant_id="default"))
        db.add(IntegrationToken(
            id="map-token", tenant_id="default", user_id="map-user",
            workspace_id="default", provider="outlook",
            access_token="scratch-not-a-secret", status="active",
            expires_at=datetime_now_plus()))
        db.commit()
        journal_standing_lesson_entry(
            db, "map-agent",
            "Price means the monetary value per unit; the method requires USD.",
            source="teacher", topic="price mapping", applies_to=["document"],
            context={"field_mappings": [{
                "concept": "Price", "sheet": "Sheet1",
                "column": "Unit Price", "unit": "USD",
                "source_version": "a" * 40, "revision": 1,
            }]}, workspace_id="default")
        buf = root / "workbook_c.xlsx"
        pd.DataFrame(C_ROWS).to_excel(buf, index=False)
        result = materialize_sheet_bytes_sync(
            buf.read_bytes(), "workbook_c.xlsx", "outlook",
            user_id="map-user", workspace_id="default",
            external_id="fixture-c")
        assert result["status"] == "materialized", result
        dataset = result["datasets"][0]
        return {
            "dataset_name": dataset["dataset_name"],
            "source_version": dataset["content_hash"],
            "sheet": dataset["entity_name"],
            "expected": expected_sum(C_ROWS, "Value"),
            "columns": list(C_ROWS[0].keys()),
            "user_id": "map-user",
            "agent_id": "map-agent",
        }
    finally:
        db.close()


def datetime_now_plus():
    from datetime import datetime, timedelta, timezone
    return datetime.now(timezone.utc) + timedelta(hours=2)


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
    params = json.loads(_durable_parameters(root, run_id))
    return params["task_lifecycle"]["assignment"]


def _lesson_mapping(root: Path, agent_id: str) -> dict:
    con = sqlite3.connect(f"file:{root / 'atom.db'}?mode=ro", uri=True)
    try:
        row = con.execute(
            "select configuration from agent_registry where id=?",
            (agent_id,)).fetchone()
        assert row is not None
        config = json.loads(row[0] or "{}")
    finally:
        con.close()
    for entry in (config.get("learning") or {}).get("log") or []:
        for mapping in (entry.get("context") or {}).get(
                "field_mappings") or []:
            if str(mapping.get("concept") or "").lower() == "price":
                return dict(mapping)
    raise AssertionError("Price mapping was not persisted on the teaching point")


def _mapping_in_snapshot(assignment: dict) -> dict:
    for mapping in (assignment.get("teaching_snapshot") or {}).get(
            "field_mappings") or []:
        if str(mapping.get("concept") or "").lower() == "price":
            return dict(mapping)
    raise AssertionError("Price mapping is missing from the durable snapshot")


def _resolution(gap: dict, assignment_id: str, column: str,
                unit: str | None = None) -> str:
    payload = {
        "request_id": gap["question_id"],
        "assignment_id": assignment_id,
        "column": column,
    }
    if unit is not None:
        payload["unit"] = unit
    return json.dumps(payload)


def _assert_no_mutation(root: Path, run_id: str, params_before: str,
                        before_mapping: dict, gap_id: str) -> dict:
    params_after = _durable_parameters(root, run_id)
    assert params_after == params_before, (
        "a refused confirmation mutated durable assignment state")
    assignment = _durable_assignment(root, run_id)
    assert _mapping_in_snapshot(assignment) == before_mapping
    source_step = next(
        step for step in assignment.get("steps") or []
        if step.get("step_id") == "source-1")
    assert source_step.get("result") is None
    assert assignment.get("status") != "completed"
    return assignment


@pytest.mark.timeout(360)
def test_workbook_c_requires_explicit_unit_then_resumes():
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
    assert meta["expected"] == "75.00"
    assert "Currency" not in meta["columns"]
    assert "Unit" not in meta["columns"]
    source_path = TMP / "workbook_c.xlsx"
    source_bytes = source_path.read_bytes()

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
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "--app-dir", str(TMP),
         "mapping_server:app", "--host", "127.0.0.1", "--port", "8071"],
        cwd=BACKEND, env=env, stdout=(TMP / "backend.log").open("wb"),
        stderr=subprocess.STDOUT, start_new_session=True)
    frontend_proc = subprocess.Popen(
        ["node", "server.js"], cwd=frontend,
        env={**env, "PORT": "3130", "HOSTNAME": "127.0.0.1"},
        stdout=(TMP / "frontend.log").open("wb"), stderr=subprocess.STDOUT,
        start_new_session=True)
    try:
        _wait(f"{BASE}/api/health")
        _wait(f"{FRONTEND}/login")
        status, login = _call(
            BASE, "POST", "/api/auth/login",
            {"username": "admin@example.com", "password": PASSWORD})
        assert status == 200 and login.get("access_token"), login
        token = login["access_token"]
        status, created = _call(
            BASE, "POST", "/api/assignments", {
                "objective": "Mapping C sum Price",
                "agent_id": meta["agent_id"],
                "sources": [{
                    "kind": "workbook",
                    "dataset_name": meta["dataset_name"],
                    "source": "outlook",
                    "external_id": "fixture-c",
                    "source_version": meta["source_version"],
                    "sheet": meta["sheet"],
                }],
                "calculation": {"aggregate": {
                    "operation": "sum", "value_column": "Price"}},
                "deliverables": [{"kind": "document",
                                  "description": "Mapping C total"}],
            }, token)
        assert status == 200, created
        run_id = created["run_id"]
        assignment_id = created["assignment"]["assignment"]["assignment_id"]

        status, detail = _call(
            BASE, "GET", f"/api/assignments/{run_id}", token=token)
        assert status == 200, detail
        gap = next(g for g in detail.get("open_gaps", [])
                   if g.get("inputs", {}).get("mapping"))
        mapping_gap = gap["inputs"]["mapping"]
        assert mapping_gap["required_unit"] == "USD", mapping_gap
        assert mapping_gap["source_unit"] == "", mapping_gap
        assert mapping_gap.get("source_unit_column", "") == "", mapping_gap
        assert "Value" in [
            item["column"] for item in mapping_gap.get("candidates") or []]
        assert "Currency" not in [
            item["column"] for item in mapping_gap.get("candidates") or []]

        params_before = _durable_parameters(TMP, run_id)
        before_mapping = _mapping_in_snapshot(
            _durable_assignment(TMP, run_id))
        assert before_mapping["column"] == "Unit Price"
        assert before_mapping["revision"] == 1
        lesson_before = _lesson_mapping(TMP, "map-agent")
        assert lesson_before["column"] == "Unit Price"

        # 1. The API refuses a confirmation that names a column but no unit.
        status, refused_missing = _call(
            BASE, "POST",
            f"/api/assignments/{run_id}/gaps/{gap['question_id']}/resolve",
            {"resolution": _resolution(gap, assignment_id, "Value")}, token)
        assert status == 409, (status, refused_missing)
        assert "explicit unit" in str(
            refused_missing.get("detail") or "").lower(), refused_missing
        _assert_no_mutation(
            TMP, run_id, params_before, before_mapping, gap["question_id"])
        assert _lesson_mapping(TMP, "map-agent") == lesson_before

        # 2. A conflicting unit is refused without conversion or mutation.
        status, refused_conflict = _call(
            BASE, "POST",
            f"/api/assignments/{run_id}/gaps/{gap['question_id']}/resolve",
            {"resolution": _resolution(
                gap, assignment_id, "Value", "EUR")}, token)
        assert status == 409, (status, refused_conflict)
        conflict_detail = str(
            refused_conflict.get("detail") or "").lower()
        assert "no conversion" in conflict_detail or "does not match" in conflict_detail, refused_conflict
        _assert_no_mutation(
            TMP, run_id, params_before, before_mapping, gap["question_id"])
        assert _lesson_mapping(TMP, "map-agent") == lesson_before

        from playwright.sync_api import sync_playwright
        attempt_dir = _attempt_dir("c", run_id)
        attempt_dir.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1100})
            page.goto(f"{FRONTEND}/login", wait_until="domcontentloaded")
            page.get_by_test_id("login-email-input").fill("admin@example.com")
            page.get_by_test_id("login-password-input").fill(PASSWORD)
            page.get_by_test_id("login-submit-button").click()
            page.wait_for_url("**/dashboard", timeout=30000)
            page.goto(f"{FRONTEND}/assignments", wait_until="domcontentloaded")
            page.get_by_text("Mapping C sum Price").first.wait_for(
                timeout=30000)
            page.get_by_role("button").filter(
                has_text="Mapping C sum Price").first.click()
            detail_el = page.get_by_test_id("assignment-detail")
            detail_el.get_by_test_id("mapping-candidates").wait_for(
                timeout=30000)
            unresolved = detail_el.get_by_test_id("mapping-unit-unresolved")
            unresolved.wait_for(timeout=30000)
            panel_text = detail_el.inner_text()
            assert "Taught unit: USD" in panel_text, panel_text
            assert "Source unit: not established" in panel_text, panel_text
            assert "Unit is unresolved" in panel_text, panel_text
            assert "Required: USD" in panel_text, panel_text
            page.screenshot(path=str(attempt_dir / "unit-unresolved.png"),
                            full_page=True)
            detail_el.get_by_test_id("mapping-unit-input").fill("USD")
            detail_el.get_by_test_id("mapping-candidate-Value").click()
            detail_el.get_by_text("completed", exact=True).wait_for(
                timeout=60000)
            page.screenshot(path=str(attempt_dir / "unit-confirmed.png"),
                            full_page=True)
            browser.close()

        status, final = _call(
            BASE, "GET", f"/api/assignments/{run_id}", token=token)
        assert status == 200, final
        assert final["assignment"]["assignment_id"] == assignment_id
        assert final["assignment"]["status"] == "completed", final

        assignment = _durable_assignment(TMP, run_id)
        source_mapping = _mapping_in_snapshot(assignment)
        assert source_mapping["column"] == "Value", source_mapping
        assert source_mapping["unit"] == "USD", source_mapping
        assert source_mapping["unit_authority"] == "user_confirmed", source_mapping
        assert source_mapping["revision"] == 2, source_mapping
        assert source_mapping.get("lesson_id"), source_mapping
        source_step = next(
            step for step in assignment.get("steps") or []
            if step.get("step_id") == "source-1")
        result = source_step.get("result") or {}
        assert result.get("value") == meta["expected"], result
        source_binding = (assignment.get("sources") or [{}])[0].get(
            "binding") or {}
        assert source_binding.get("external_id") == "fixture-c"
        assert source_binding.get("source_version") == meta["source_version"]

        lesson_mapping = _lesson_mapping(TMP, "map-agent")
        assert lesson_mapping["column"] == "Value", lesson_mapping
        assert lesson_mapping["unit"] == "USD", lesson_mapping
        assert lesson_mapping["unit_authority"] == "user_confirmed", lesson_mapping
        assert lesson_mapping["revision"] == 2, lesson_mapping

        artifact = next(
            item for item in final["assignment"].get("deliverables") or []
            if item.get("kind") == "document")
        assert source_path.read_bytes() == source_bytes, (
            "the confirmation mutated the source workbook")
        artifact_path = Path(artifact["artifact_path"])
        assert artifact_path.exists(), artifact
        artifact_sha256 = hashlib.sha256(
            artifact_path.read_bytes()).hexdigest()
        assert artifact_sha256 == artifact["sha256"], artifact
        assert {
            item.get("kind")
            for item in final["assignment"].get("deliverables") or []
        } == {"document"}
        evidence = {
            "schema": "atom-mapping-browser-c-1",
            "status": "passed",
            **(_evidence_identity(Path(__file__))),
            "run_id": run_id,
            "assignment_id": assignment_id,
            "fixture": (
                "controlled acceptance workbook_c: columns Product,Qty,Value,"
                "Note; no source unit; not live-connected"),
            "expected": meta["expected"],
            "result": result["value"],
            "currency": "USD",
            "unit_authority": source_mapping["unit_authority"],
            "source_version": meta["source_version"],
            "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "source_bytes_unchanged": True,
            "mapping": source_mapping,
            "teaching_persisted": lesson_mapping,
            "gap": {
                "question_id": gap["question_id"],
                "required_unit": mapping_gap["required_unit"],
                "source_unit": mapping_gap["source_unit"],
                "source_unit_column": mapping_gap.get("source_unit_column", ""),
                "candidates": [
                    item["column"]
                    for item in mapping_gap.get("candidates") or []],
            },
            "refusals": [
                {
                    "kind": "missing_unit",
                    "http_status": 409,
                    "detail": refused_missing.get("detail"),
                },
                {
                    "kind": "incompatible_unit",
                    "unit": "EUR",
                    "http_status": 409,
                    "detail": refused_conflict.get("detail"),
                },
            ],
            "no_mutation": {
                "durable_parameters_identical": True,
                "mapping_before": before_mapping,
                "result_before_confirmation": None,
            },
            "confirmation": {
                "surface": "Assignments panel",
                "column": "Value",
                "unit": "USD",
            },
            "artifact_path": artifact.get("artifact_path"),
            "artifact_sha256": artifact_sha256,
            "artifact_bytes_verified": True,
            "screenshots": ["unit-unresolved.png", "unit-confirmed.png"],
        }
        (attempt_dir / "result.json").write_text(
            json.dumps(evidence, indent=2) + "\n")
    finally:
        for proc in (frontend_proc, backend):
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception:
                pass
        time.sleep(1)


if __name__ == "__main__":
    test_workbook_c_requires_explicit_unit_then_resumes()
