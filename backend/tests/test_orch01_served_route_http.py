"""ORCH-01 — served production-route control: a REAL HTTP server process.

Gap this closes (CLI_WORK_ORDER.md): the accepted ORCH-01 blueprint controls
(``test_orch01_workflow_blueprint.py``) use ``TestClient`` — no actual
HTTP-serving application process. This harness drives the SAME production
route (``POST /api/v1/workflows/generate-from-agent`` as mounted in
``main_api_app.py``) over a real bound TCP socket served by uvicorn, with:

- the production auth chain (real ``require_permission``/``get_current_user``
  JWT validation — NO dependency override),
- the production ``get_db`` consumer bound to a unique explicit scratch
  SQLite database (``TESTING=1`` + non-dev ``DATABASE_URL``, honored by
  ``core.database.get_database_url``),
- model transport doubled (LLM structured leaf + route classifier), with an
  observing orchestrator double that records any registration/execution call,
- a minimal mounted-router FastAPI process — deliberately narrower than the
  whole application; this is NOT a whole-app bootstrap proof.

No execution, no trigger activation, no provider/network call.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.auth import create_access_token
from core.models import Tenant, User, Workflow


# --- Accepted deterministic controls (same doubles as the TestClient suite) --

def _draft(*, name="Vendor invoice intake and review", mode="one_off"):
    return {
        "architecture_name": name,
        "description": "A reusable review workflow.",
        "execution_mode": mode,
        "nodes": [
            {"id": "intake", "type": "agent", "name": "Intake request",
             "action": {"kind": "read"}},
            {"id": "triage", "type": "agent", "name": "Triage request",
             "dependencies": ["intake"], "action": {"kind": "compute"}},
            {"id": "notify", "type": "agent", "name": "Notify reviewer",
             "dependencies": ["triage"],
             "action": {"kind": "notify", "service": "email",
                        "action": "send"}},
            {"id": "record", "type": "entity", "name": "Record review",
             "dependencies": ["notify"], "action": {"kind": "write"}},
        ],
        "required_integrations": [],
        "missing_capabilities": [],
    }


class FakeOrchestrator:
    def __init__(self):
        self.registered = []
        self.executed = []

    def register_workflow(self, definition):
        self.registered.append(definition)
        return definition.workflow_id

    async def execute_workflow(self, *args, **kwargs):
        self.executed.append((args, kwargs))
        raise AssertionError("blueprint generation must not execute")


# --- Environment fixtures ----------------------------------------------------


def _trace(path):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {"calls": [], "registered": [], "executed": []}


class _ObservedEffects:
    def __init__(self, path):
        self.path = path

    @property
    def registered(self):
        return _trace(self.path)["registered"]

    @property
    def executed(self):
        return _trace(self.path)["executed"]


@pytest.fixture()
def served_env(tmp_path):
    db_path = tmp_path / "served.db"
    engine = create_engine(f"sqlite:///{db_path}")
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    with sessions() as db:
        db.add(Tenant(id="tenant-1", name="Tenant One", subdomain="tenant-one"))
        for uid, ws, tenant in [("user-1", "ws-1", "tenant-1"),
                                ("user-2", "ws-2", "tenant-1"),
                                ("user-3", "ws-1", "tenant-2")]:
            db.add(User(id=uid, email=f"{uid}@example.com", hashed_password="x",
                        first_name="U", last_name="Test", role="member",
                        status="active", workspace_id=ws, tenant_id=tenant,
                        is_active=True))
        db.commit()
    trace = tmp_path / "transport-observations.json"
    worker = tmp_path / "served_workflow_fixture.py"
    worker.write_text(
        "import json\nfrom pathlib import Path\nfrom types import SimpleNamespace\n"
        "from fastapi import FastAPI\n"
        "from core.llm_service import LLMService\n"
        "from ai.nlp_engine import NaturalLanguageEngine, RouteCategory\n"
        "import advanced_workflow_orchestrator\n"
        "from advanced_workflow_api import router\n"
        f"trace=Path({str(trace)!r})\n"
        f"draft={_draft()!r}\n"
        "state={'calls':[],'registered':[],'executed':[]}\n"
        "def save(): trace.write_text(json.dumps(state))\n"
        "class ObservedOrchestrator:\n"
        " def register_workflow(self, definition):\n"
        "  state['registered'].append(definition.workflow_id);save();return definition.workflow_id\n"
        " async def execute_workflow(self,*a,**k):\n"
        "  state['executed'].append(True);save();raise AssertionError('generation executed workflow')\n"
        "orchestrator=ObservedOrchestrator()\n"
        "advanced_workflow_orchestrator.get_orchestrator=lambda:orchestrator\n"
        "async def structured(self,**kwargs):\n"
        " state['calls'].append({'capability_profile':kwargs.get('capability_profile')});save()\n"
        " if 'no-suitable-fixture' in kwargs.get('prompt',''):\n"
        "  from core.llm.byok_handler import NoSuitableConfiguredModelError\n"
        "  raise NoSuitableConfiguredModelError('workflow_blueprint', {'selection_reason':'controlled no eligible route'})\n"
        " if 'invalid-fixture' in kwargs.get('prompt',''): return kwargs['response_model'].model_validate({'architecture_name':'x','nodes':[]})\n"
        " return kwargs['response_model'].model_validate(draft)\n"
        "async def classify(self,prompt,**kwargs):\n"
        " return SimpleNamespace(category=RouteCategory.ONE_OFF,reasoning='controlled route')\n"
        "LLMService.generate_structured_response=structured\n"
        "NaturalLanguageEngine.classify_route=classify\n"
        "save()\napp=FastAPI()\napp.include_router(router)\n"
    )
    env = os.environ.copy()
    env.update(TESTING="1", DATABASE_URL=f"sqlite:///{db_path}",
               ATOM_DATA_DIR=str(tmp_path / "data"),
               LANCEDB_URI=str(tmp_path / "lancedb"),
               LANCEDB_PATH=str(tmp_path / "lancedb"))
    backend = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = backend
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    base_url = f"http://127.0.0.1:{listener.getsockname()[1]}"
    log = (tmp_path / "server.log").open("w")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "served_workflow_fixture:app",
         "--app-dir", str(tmp_path), "--fd", str(listener.fileno()),
         "--log-level", "warning"], cwd=backend, env=env,
        pass_fds=(listener.fileno(),), stdout=log, stderr=log)
    listener.close()
    try:
        deadline = time.monotonic() + 40
        while True:
            if process.poll() is not None:
                log.flush()
                pytest.fail((tmp_path / "server.log").read_text()[-6000:])
            try:
                with urllib.request.urlopen(base_url + "/openapi.json", timeout=1):
                    break
            except (OSError, urllib.error.URLError):
                if time.monotonic() >= deadline:
                    pytest.fail("served fixture failed to start within 40 seconds")
                time.sleep(0.05)
        yield {"base_url": base_url, "trace": trace,
               "fake": _ObservedEffects(trace), "Session": sessions,
               "server_pid": process.pid}
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        log.close()
        engine.dispose()


# --- HTTP helpers (real socket, no TestClient) -------------------------------


def _token_for(user_id: str) -> str:
    return create_access_token({"sub": user_id})


def _request(method: str, url: str, token: str | None, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"raw": body}


# --- The served-route control ------------------------------------------------


def test_served_http_route_persists_and_reads_back_across_fresh_sessions(
        served_env):
    base_url = served_env["base_url"]
    assert served_env["server_pid"] != os.getpid()
    token = _token_for("user-1")

    # Unauthenticated request is refused by the REAL auth dependency —
    # no override seam exists in this process.
    status, body = _request(
        "POST", f"{base_url}/api/v1/workflows/generate-from-agent",
        None, {"prompt": "Review the service intake request"})
    assert status == 401, body

    status, created = _request(
        "POST", f"{base_url}/api/v1/workflows/generate-from-agent",
        token, {"prompt": "Review the service intake request"})
    assert status == 200, created
    assert created["workflow_id"].startswith("ai_wf_")
    assert created["status"] == "designed"
    assert created["definition_digest"]
    assert created["hitl_gates"]
    assert created["execution_ready"] is False
    assert created["execution_blockers"]
    assert created["registration"]["registered"] is False
    assert len(_trace(served_env["trace"])["calls"]) == 1
    assert _trace(served_env["trace"])["calls"][0]["capability_profile"] == "workflow_blueprint"
    assert served_env["fake"].executed == []

    workflow_id = created["workflow_id"]

    # Fresh-session durable readback: a brand-new session opened directly on
    # the scratch store, plus a separate authenticated HTTP request (which the
    # production get_db dependency serves with its own fresh session).
    fresh_session = served_env["Session"]()
    try:
        row = fresh_session.query(Workflow).filter(
            Workflow.id == workflow_id).one()
        assert row.tenant_id == "tenant-1"
        assert row.status == "designed"
        assert row.configuration["workspace_id"] == "ws-1"
        assert row.configuration["definition_digest"] == (
            created["definition_digest"])
    finally:
        fresh_session.close()

    status, readback = _request(
        "GET", f"{base_url}/api/v1/workflows/generated/{workflow_id}",
        token)
    assert status == 200, readback
    assert readback["definition_digest"] == created["definition_digest"]
    assert readback["nodes"] == created["nodes"]
    assert readback["steps"] == created["steps"]
    assert readback["start_step"] == created["start_step"]
    assert readback["triggers"] == created["triggers"]

    # Scoped readback as actually supported for single-tenant users:
    # exact workspace and tenant match is required.
    status, _ = _request(
        "GET", f"{base_url}/api/v1/workflows/generated/{workflow_id}",
        _token_for("user-2"))
    assert status == 404
    status, _ = _request(
        "GET", f"{base_url}/api/v1/workflows/generated/{workflow_id}",
        _token_for("user-3"))
    assert status == 404

    # Empty request safe negative — refused before the model leaf.
    status, body = _request(
        "POST", f"{base_url}/api/v1/workflows/generate-from-agent",
        token, {"prompt": "   "})
    assert status == 422, body
    assert body["detail"]["error"] == "workflow_request_empty"
    assert len(_trace(served_env["trace"])["calls"]) == 1

    # Invalid draft safe negative — typed refusal, nothing persisted,
    # nothing registered.
    # The controlled model leaf rejects this fixture prompt.
    with served_env["Session"]() as fresh:
        before = fresh.query(Workflow).count()
    status, body = _request(
        "POST", f"{base_url}/api/v1/workflows/generate-from-agent",
        token, {"prompt": "Build an invalid-fixture workflow"})
    assert status == 422, body
    assert body["detail"]["error"] == "workflow_blueprint_invalid"
    with served_env["Session"]() as fresh:
        assert fresh.query(Workflow).count() == before
    assert served_env["fake"].registered == []
    assert served_env["fake"].executed == []

    # Real route preserves the typed no-suitable response without persistence.
    status, body = _request(
        "POST", f"{base_url}/api/v1/workflows/generate-from-agent",
        token, {"prompt": "Build a no-suitable-fixture workflow"})
    assert status == 503, body
    assert body["detail"]["error"] == "workflow_blueprint_no_suitable_route"
    with served_env["Session"]() as fresh:
        assert fresh.query(Workflow).count() == before
    assert served_env["fake"].registered == []
    assert served_env["fake"].executed == []
