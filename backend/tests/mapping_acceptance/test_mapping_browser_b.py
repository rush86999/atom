"""One isolated browser slice: workbook B mapping clarification -> 35.00 USD.

This is a controlled acceptance harness. It seeds only a scratch database and
scratch parquet, starts the real assignment/auth/product-profile routes, and
uses the built Assignments panel. No live source, pilot data or production
transport is touched.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[3]
BACKEND = REPO / "backend"
FRONTEND_BUILD = REPO / "frontend-nextjs" / ".next"
EVIDENCE = REPO / "docs" / "acceptance" / "evidence" / "durable_assignment_20261029" / "mapping-browser-b"
TMP = Path("/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/mapping_b_acceptance")


def _port_free(port: int) -> bool:
    out = subprocess.run(["lsof", "-ti", f"tcp:{port}"], capture_output=True, text=True)
    return not out.stdout.strip()


def _wait(url: str, timeout=90):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                return response.status
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(0.5)
    raise RuntimeError(f"not ready: {url}: {last}")


def _call(base, method, path, body=None, token=""):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(base + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode() or "{}")


def _server_source(root: Path) -> str:
    return f'''
import os, sys
from pathlib import Path
sys.path.insert(0, r"{BACKEND}")
root = Path(r"{root}")
os.environ["DATABASE_URL"] = f"sqlite:///{{root / 'atom.db'}}"
os.environ["ATOM_DATA_DIR"] = str(root)
os.environ["ATOM_OFFICE_DIR"] = str(root / "office")
os.environ["ATOM_ASSIGNMENT_OUTPUT_DIR"] = str(root / "office" / "assignments")
os.environ["ATOM_DEPLOYMENT_AUDIENCE"] = "single_user"
os.environ["ATOM_PILOT_USER_EMAIL"] = "admin@example.com"
os.environ["ATOM_EMAIL_SEND_DISABLED"] = "1"
os.environ["ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS"] = "0"
os.environ["ENABLE_SCHEDULER"] = "false"
os.environ["ENABLE_INGESTION_SYNC"] = "false"
os.environ["ALLOWED_ORIGINS"] = "http://127.0.0.1:3130"
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.assignment_routes import router as assignment_router
from api.product_profile_routes import router as profile_router
from core.auth_endpoints import router as auth_router
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:3130", "http://localhost:3130"], allow_methods=["*"], allow_headers=["*"])
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(assignment_router)
@app.get("/api/health")
def health():
    return {{"status": "healthy", "identity": {{"revision": "mapping-harness", "dirty": False}}}}
'''


def _seed(root: Path):
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
        user = User(id="map-user", email="admin@example.com",
                    hashed_password=get_password_hash("MappingPass123!"),
                    first_name="Map", last_name="User", role="workspace_admin",
                    status="active", workspace_id="default", tenant_id="default",
                    is_active=True)
        db.add(user)
        agent = AgentRegistry(
            id="map-agent", name="Mapping Agent", category="operations",
            description="mapping acceptance", module_path="core.generic_agent",
            class_name="GenericAgent", status="intern", confidence_score=0.5,
            configuration={}, capabilities=[], workspace_id="default",
            tenant_id="default")
        db.add(agent)
        st = IntegrationToken(
            id="map-token", tenant_id="default", user_id="map-user",
            workspace_id="default", provider="outlook",
            access_token="scratch-not-a-secret", status="active",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2))
        db.add(st)
        db.commit()
        journal_standing_lesson_entry(
            db, "map-agent", "Price means Amount in the mapping fixture.",
            source="teacher", topic="price mapping", applies_to=["document"],
            context={"field_mappings": [{
                "concept": "Price", "sheet": "Sheet1", "column": "Unit Price",
                "unit": "USD", "source_version": "a" * 40, "revision": 1,
            }]}, workspace_id="default")
        rows = [
            {"SKU": "B-1", "Quantity": 2, "Amount": 15.0,
             "Discount": 1.0, "Currency": "USD", "Note": ""},
            {"SKU": "B-2", "Quantity": 3, "Amount": 20.0,
             "Discount": 2.0, "Currency": "USD", "Note": "renamed"},
        ]
        buf = root / "workbook_b.xlsx"
        pd.DataFrame(rows).to_excel(buf, index=False)
        result = materialize_sheet_bytes_sync(
            buf.read_bytes(), "workbook_b.xlsx", "outlook",
            user_id="map-user", workspace_id="default",
            external_id="fixture-b")
        assert result["status"] == "materialized", result
        dataset = result["datasets"][0]
        return {
            "dataset_name": dataset["dataset_name"],
            "source_version": dataset["content_hash"],
            "sheet": dataset["entity_name"],
            "expected": "35.00",
            "user_id": "map-user",
            "agent_id": "map-agent",
        }
    finally:
        db.close()


@pytest.mark.timeout(300)
def test_workbook_b_mapping_confirmation_completes():
    if not _port_free(8071) or not _port_free(3130):
        pytest.skip("ports 8071/3130 are in use; isolated harness requires them free")
    _wait_guard = subprocess.run(
        [sys.executable, "-m", "core.world_storage_guard", "check"],
        cwd=BACKEND, capture_output=True, text=True)
    assert _wait_guard.returncode == 0, _wait_guard.stderr + _wait_guard.stdout
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True)
    (TMP / "office" / "assignments").mkdir(parents=True)
    meta = _seed(TMP)
    server_file = TMP / "mapping_server.py"
    server_file.write_text(_server_source(TMP))
    frontend = TMP / "frontend"
    shutil.copytree(FRONTEND_BUILD / "standalone", frontend)
    (frontend / ".next").mkdir(exist_ok=True)
    shutil.copytree(FRONTEND_BUILD / "static", frontend / ".next" / "static")
    if (REPO / "frontend-nextjs" / "public").is_dir():
        shutil.copytree(REPO / "frontend-nextjs" / "public", frontend / "public",
                        dirs_exist_ok=True)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(BACKEND)
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "--app-dir", str(TMP), "mapping_server:app",
         "--host", "127.0.0.1", "--port", "8071"],
        cwd=BACKEND, env=env, stdout=(TMP / "backend.log").open("wb"),
        stderr=subprocess.STDOUT, start_new_session=True)
    frontend_proc = subprocess.Popen(
        ["node", "server.js"], cwd=frontend,
        env={**env, "PORT": "3130", "HOSTNAME": "127.0.0.1"},
        stdout=(TMP / "frontend.log").open("wb"), stderr=subprocess.STDOUT,
        start_new_session=True)
    try:
        _wait("http://127.0.0.1:8071/api/health")
        _wait("http://127.0.0.1:3130/login")
        status, login = _call("http://127.0.0.1:8071", "POST", "/api/auth/login",
                              {"username": "admin@example.com",
                               "password": "MappingPass123!"})
        assert status == 200 and login.get("access_token"), login
        token = login["access_token"]
        status, created = _call(
            "http://127.0.0.1:8071", "POST", "/api/assignments", {
                "objective": "Mapping B sum Price",
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
                                  "description": "Mapping B total"}],
            }, token)
        assert status == 200, created
        run_id = created["run_id"]
        assignment_id = created["assignment"]["assignment"]["assignment_id"]
        status, detail = _call(
            "http://127.0.0.1:8071", "GET", f"/api/assignments/{run_id}", token=token)
        assert status == 200
        gap = next(g for g in detail.get("open_gaps", [])
                   if g.get("inputs", {}).get("mapping"))
        assert "Amount" in [c["column"] for c in gap["inputs"]["mapping"]["candidates"]]
        assert "Discount" in [c["column"] for c in gap["inputs"]["mapping"]["candidates"]]

        from playwright.sync_api import sync_playwright
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1100})
            page.goto("http://127.0.0.1:3130/login", wait_until="domcontentloaded")
            page.get_by_test_id("login-email-input").fill("admin@example.com")
            page.get_by_test_id("login-password-input").fill("MappingPass123!")
            page.get_by_test_id("login-submit-button").click()
            page.wait_for_url("**/dashboard", timeout=30000)
            page.goto("http://127.0.0.1:3130/assignments", wait_until="domcontentloaded")
            page.get_by_text("Mapping B sum Price").first.wait_for(timeout=30000)
            page.get_by_role("button").filter(has_text="Mapping B sum Price").first.click()
            detail_el = page.get_by_test_id("assignment-detail")
            detail_el.get_by_test_id("mapping-candidates").wait_for(timeout=30000)
            page.screenshot(path=str(EVIDENCE / "mapping-candidates.png"), full_page=True)
            detail_el.get_by_test_id("mapping-candidate-Amount").click()
            detail_el.get_by_text("completed", exact=True).wait_for(timeout=60000)
            page.screenshot(path=str(EVIDENCE / "mapping-completed.png"), full_page=True)
            browser.close()

        status, final = _call(
            "http://127.0.0.1:8071", "GET", f"/api/assignments/{run_id}", token=token)
        assert status == 200
        assignment = final["assignment"]
        assert assignment["assignment_id"] == assignment_id
        assert assignment["status"] == "completed"
        import sqlite3
        con = sqlite3.connect(f"file:{TMP / 'atom.db'}?mode=ro", uri=True)
        try:
            params = json.loads(con.execute(
                "select parameters from goal_runs where id=?", (run_id,)
            ).fetchone()[0])
        finally:
            con.close()
        durable = params["task_lifecycle"]["assignment"]
        result = next(s for s in durable["steps"]
                      if s["step_id"] == "source-1")["result"]
        assert result["value"] == "35.00"
        artifact = next(d for d in assignment["deliverables"]
                        if d["kind"] == "document")
        evidence = {
            "schema": "atom-mapping-browser-b-1",
            "status": "passed",
            "run_id": run_id,
            "assignment_id": assignment_id,
            "result": result["value"],
            "currency": "USD",
            "source_version": meta["source_version"],
            "mapping_revision": durable["teaching_snapshot"][
                "field_mappings"][0]["revision"],
            "artifact_path": artifact["artifact_path"],
            "artifact_sha256": artifact["sha256"],
            "first_gap": gap,
            "screenshots": ["mapping-candidates.png", "mapping-completed.png"],
            "fixture": "controlled acceptance workbook_b (not live-connected)",
        }
        (EVIDENCE / "result.json").write_text(json.dumps(evidence, indent=2) + "\n")
    finally:
        for proc in (frontend_proc, backend):
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception:
                pass
        time.sleep(1)


if __name__ == "__main__":
    test_workbook_b_mapping_confirmation_completes()
