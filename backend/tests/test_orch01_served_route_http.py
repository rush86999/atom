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

The default ``served_env`` fixture doubles the model transport: no execution,
no trigger activation, no provider/network call.

``real_ollama_env`` is an OPT-IN qualification of the same served route against
the real local Ollama model declared below. It is skipped unless
``ATOM_ORCH01_REAL_OLLAMA=1``. When enabled it:

- strips every remote-provider credential from the worker environment,
- pins ``ATOM_LLM_PROVIDER_POLICY`` to ``ollama`` only (no remote provider),
- talks only to the loopback endpoint ``127.0.0.1:11434`` (rejects any other
  host/port), and verifies the declared model is pulled before starting,
- keeps the production auth chain, the scratch ``TESTING=1`` SQLite store and
  the observing orchestrator double, and records the provider-echoed model
  identity (``served_route`` + ``resolved_model``) for the qualification.

It still performs no workflow execution and activates no trigger.
"""
from __future__ import annotations

import contextlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.auth import create_access_token
from core.models import Tenant, User, Workflow


# --- Opt-in real local-model qualification configuration --------------------

#: Set to "1" to run the real-Ollama served qualification. Unset (or any
#: other value) skips it, so the ordinary test run stays fully deterministic.
OPT_IN_REAL_OLLAMA = "ATOM_ORCH01_REAL_OLLAMA"

#: Loopback-only local runtime (never a gateway, never a remote host).
OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
OLLAMA_MODEL = "llama3.1:8b"
OLLAMA_CONTEXT_WINDOW = "16384"
OLLAMA_DEADLINE_SECONDS = "180"
#: The blueprint JSON is large; the local 8b model needs more than the
#: helper's default client read timeout.
REAL_BLUEPRINT_HTTP_TIMEOUT = 240

#: The design request. It names a send/state change and explicitly requires
#: gating, so the qualification covers mandatory HITL insertion as well as
#: free-form model design.
REAL_OLLAMA_PROMPT = (
    "Design a one-off service intake and review workflow: intake the request, "
    "triage it, notify the reviewer, and record the review decision. Read-only "
    "analysis must not need approval; any send or state change must be gated.")

#: Credentials for remote providers must not exist in the qualification
#: worker environment: lack of a client is one more barrier to a remote call.
REMOTE_PROVIDER_KEY_ENV = (
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY",
    "OPENROUTER_API_KEY", "GOOGLE_API_KEY", "OPENCODE_API_KEY",
    "MOONSHOT_API_KEY", "DEEPINFRA_API_KEY", "GROQ_API_KEY",
    "MISTRAL_API_KEY", "XAI_API_KEY", "TOGETHER_API_KEY",
)


def _ollama_api_root(base_url: str) -> str:
    """Return the native API root, enforcing loopback + the declared port."""
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        root = root[: -len("/v1")]
    parsed = urllib.parse.urlsplit(root)
    assert parsed.scheme == "http", f"Ollama must be plain http, got {root!r}"
    assert parsed.hostname == "127.0.0.1", (
        f"Ollama qualification is loopback-only, got {root!r}")
    assert parsed.port == 11434, (
        f"Ollama qualification is pinned to port 11434, got {root!r}")
    return root


def _probe_local_ollama() -> dict:
    """Return the runtime catalogue, or skip when the local server is down."""
    root = _ollama_api_root(OLLAMA_BASE_URL)
    try:
        with urllib.request.urlopen(
                f"{root}/api/tags", timeout=5) as response:
            return json.loads(response.read().decode())
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        pytest.skip(f"local Ollama at {root} is not reachable: {exc}")


def _declared_model_entry(catalogue: dict) -> dict:
    """Require the declared model tag and return its runtime identity."""
    entries = {
        str(item.get("name") or ""): item
        for item in catalogue.get("models") or []
        if isinstance(item, dict)
    }
    entry = entries.get(OLLAMA_MODEL)
    if entry is None:
        pytest.fail(
            f"declared model {OLLAMA_MODEL!r} is not pulled on the local "
            f"Ollama runtime; available={sorted(entries)}")
    assert entry.get("digest"), f"model {OLLAMA_MODEL!r} has no runtime digest"
    return entry


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


def _worker_source(trace: Path, draft: dict, *, real_ollama: bool) -> str:
    """Return the served subprocess worker source.

    The route classifier and the observing orchestrator are doubled in both
    modes. Only the structured model leaf differs:

    - ``real_ollama=False``: a deterministic draft double (accepted control).
    - ``real_ollama=True``: delegate to the production LLMService and record
      the real call scope plus the provider-echoed model identity.
    """
    lines = [
        "import json",
        "from pathlib import Path",
        "from types import SimpleNamespace",
        "from fastapi import FastAPI",
        "from core.llm_service import LLMService",
        "from ai.nlp_engine import NaturalLanguageEngine, RouteCategory",
        "import advanced_workflow_orchestrator",
        "from advanced_workflow_api import router",
        f"trace=Path({str(trace)!r})",
        f"draft={draft!r}",
        "state={'calls':[],'registered':[],'executed':[]}",
        "def save(): trace.write_text(json.dumps(state))",
        "class ObservedOrchestrator:",
        " def register_workflow(self, definition):",
        "  state['registered'].append(definition.workflow_id);save();return definition.workflow_id",
        " async def execute_workflow(self,*a,**k):",
        "  state['executed'].append(True);save();raise AssertionError('generation executed workflow')",
        "orchestrator=ObservedOrchestrator()",
        "advanced_workflow_orchestrator.get_orchestrator=lambda:orchestrator",
    ]
    if real_ollama:
        lines += [
            "real_structured=LLMService.generate_structured_response",
            "async def structured(self,**kwargs):",
            " record={'capability_profile':kwargs.get('capability_profile'),"
            "'output_mode':kwargs.get('output_mode'),"
            "'response_model':getattr(kwargs.get('response_model'),'__name__',str(kwargs.get('response_model'))),"
            "'workspace_id':kwargs.get('workspace_id'),"
            "'tenant_id':kwargs.get('tenant_id')}",
            " state['calls'].append(record)",
            " save()",
            " try:",
            "  result=await real_structured(self,**kwargs)",
            " except Exception as exc:",
            "  record['error_type']=type(exc).__name__",
            "  record['error']=str(exc)[:2000]",
            "  save()",
            "  raise",
            " from core.llm.model_provenance import get_route_attribution",
            " record['attribution']=get_route_attribution()",
            " handler=self._get_handler()",
            " record['served_provider']=getattr(handler,'_last_used_provider',None)",
            " record['served_model']=getattr(handler,'_last_used_model',None)",
            " record['client_providers']=sorted(set(getattr(handler,'clients',{}) or {})|set(getattr(handler,'async_clients',{}) or {}))",
            " policy=getattr(handler,'provider_policy',None)",
            " record['policy_mode']=getattr(policy,'mode',None)",
            " record['policy_allowed']=sorted(getattr(policy,'allowed_providers',[]) or [])",
            " save()",
            " return result",
            "LLMService.generate_structured_response=structured",
        ]
    else:
        lines += [
            "async def structured(self,**kwargs):",
            " state['calls'].append({'capability_profile':kwargs.get('capability_profile')});save()",
            " if 'no-suitable-fixture' in kwargs.get('prompt',''):",
            "  from core.llm.byok_handler import NoSuitableConfiguredModelError",
            "  raise NoSuitableConfiguredModelError('workflow_blueprint', {'selection_reason':'controlled no eligible route'})",
            " if 'invalid-fixture' in kwargs.get('prompt',''): return kwargs['response_model'].model_validate({'architecture_name':'x','nodes':[]})",
            " return kwargs['response_model'].model_validate(draft)",
            "LLMService.generate_structured_response=structured",
        ]
    lines += [
        "async def classify(self,prompt,**kwargs):",
        " return SimpleNamespace(category=RouteCategory.ONE_OFF,reasoning='controlled route')",
        "NaturalLanguageEngine.classify_route=classify",
        "save()",
        "app=FastAPI()",
        "app.include_router(router)",
    ]
    return "\n".join(lines) + "\n"


@contextlib.contextmanager
def _served_environment(tmp_path, *, real_ollama: bool):
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
        _worker_source(trace, _draft(), real_ollama=real_ollama))
    env = os.environ.copy()
    env.update(TESTING="1", DATABASE_URL=f"sqlite:///{db_path}",
               ATOM_DATA_DIR=str(tmp_path / "data"),
               LANCEDB_URI=str(tmp_path / "lancedb"),
               LANCEDB_PATH=str(tmp_path / "lancedb"))
    if real_ollama:
        # No remote credential and no parent preference may leak in. The
        # provider policy is the hard dispatch boundary; the missing keys mean
        # no remote client is even built.
        for name in REMOTE_PROVIDER_KEY_ENV + (
                "ATOM_PREFERRED_LLM_PROVIDER", "ATOM_PREFERRED_LLM_MODEL",
                "ATOM_REVIEW_PROVIDER", "ATOM_REVIEW_MODEL",
                "OLLAMA_BASE_URL", "OLLAMA_MODEL"):
            env.pop(name, None)
        (tmp_path / "data").mkdir(parents=True, exist_ok=True)
        env.update({
            "OLLAMA_BASE_URL": OLLAMA_BASE_URL,
            "OLLAMA_MODEL": OLLAMA_MODEL,
            "OLLAMA_CONTEXT_WINDOW": OLLAMA_CONTEXT_WINDOW,
            "OLLAMA_REQUEST_TIMEOUT": "600",
            "ATOM_LLM_PROVIDER_POLICY": json.dumps({
                "mode": "selected",
                "allowed_providers": ["ollama"],
                "preferred": {"provider": "ollama", "model": OLLAMA_MODEL},
            }, separators=(",", ":")),
            "ATOM_WORKFLOW_BLUEPRINT_DEADLINE_SECONDS":
                OLLAMA_DEADLINE_SECONDS,
            "ATOM_LOCAL_ONLY": "true",
            # Drift state defaults to ./data under the repo; keep all durable
            # writes inside this scratch directory.
            "ATOM_MODEL_DRIFT_DETECTION_ENABLED": "false",
            "BYOK_KEYS_FILE": str(tmp_path / "byok_keys.json"),
            "BYOK_CONFIG_FILE": str(tmp_path / "byok_config.json"),
            "BYOK_ENC_KEY_FILE": str(tmp_path / "byok_encryption_key"),
            "ENABLE_SCHEDULER": "false",
            "ENABLE_INGESTION_SYNC": "false",
        })
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


@pytest.fixture()
def served_env(tmp_path):
    """The accepted deterministic control (doubled model transport)."""
    with _served_environment(tmp_path, real_ollama=False) as env:
        yield env


@pytest.fixture()
def real_ollama_env(tmp_path):
    """Opt-in qualification against the real local Ollama model.

    Skipped unless ``ATOM_ORCH01_REAL_OLLAMA=1``. The server catalogue is
    checked BEFORE the process starts so the declared identity is known to be
    present (and is surfaced in the trace for the qualification record).
    """
    if os.environ.get(OPT_IN_REAL_OLLAMA) != "1":
        pytest.skip(
            f"real Ollama qualification is opt-in: set {OPT_IN_REAL_OLLAMA}=1")
    runtime = _declared_model_entry(_probe_local_ollama())
    with _served_environment(tmp_path, real_ollama=True) as env:
        env["ollama_runtime"] = runtime
        yield env


# --- HTTP helpers (real socket, no TestClient) -------------------------------


def _token_for(user_id: str, served_env) -> str:
    with served_env["Session"]() as session:
        user = session.query(User).filter(User.id == user_id).one_or_none()
        assert user is not None
        return create_access_token({"sub": user_id}, user=user)


def _request(method: str, url: str, token: str | None, payload=None, *,
             timeout: float = 30):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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
    token = _token_for("user-1", served_env)

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
        _token_for("user-2", served_env))
    assert status == 404
    status, _ = _request(
        "GET", f"{base_url}/api/v1/workflows/generated/{workflow_id}",
        _token_for("user-3", served_env))
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


# --- Opt-in real local-model qualification ----------------------------------


def test_served_http_route_real_ollama_persists_and_reads_back(
        real_ollama_env):
    """Same served route, real local Ollama, fresh-store readback + isolation.

    Opt-in (``ATOM_ORCH01_REAL_OLLAMA=1``). Happy path only: the qualified
    claim is that the authenticated route carries a real model design through
    validation/persistence and that the provider-echoed identity is the
    declared local model. The doubled-leaf safe negatives stay in the
    controlled test above.
    """
    env = real_ollama_env
    base_url = env["base_url"]
    assert env["server_pid"] != os.getpid()
    # The runtime identity was captured from /api/tags before the process
    # started; the tag (not just the shared weights digest) is the contract.
    runtime = env["ollama_runtime"]
    assert runtime["name"] == OLLAMA_MODEL
    assert runtime.get("digest")
    token = _token_for("user-1", env)

    # The real auth chain still refuses an unauthenticated request.
    status, body = _request(
        "POST", f"{base_url}/api/v1/workflows/generate-from-agent",
        None, {"prompt": REAL_OLLAMA_PROMPT})
    assert status == 401, body

    status, created = _request(
        "POST", f"{base_url}/api/v1/workflows/generate-from-agent",
        token, {"prompt": REAL_OLLAMA_PROMPT},
        timeout=REAL_BLUEPRINT_HTTP_TIMEOUT)
    assert status == 200, created
    assert created["workflow_id"].startswith("ai_wf_")
    assert created["status"] == "designed"
    assert created["definition_digest"]
    assert created["model_generated"] is True
    # The request names a send and a state change, so the server must insert
    # the mandatory approval checkpoint before them.
    assert created["hitl_gates"]
    assert created["execution_ready"] is False
    assert created["execution_blockers"]
    assert created["registration"]["registered"] is False

    # Model identity and scope, captured at the real transport boundary.
    trace = _trace(env["trace"])
    assert len(trace["calls"]) == 1, trace
    call = trace["calls"][0]
    assert call["capability_profile"] == "workflow_blueprint"
    assert call["output_mode"] == "json"
    assert call["response_model"] == "WorkflowBlueprintDraft"
    # The authenticated request scope is the only scope the model sees.
    assert call["workspace_id"] == "ws-1"
    assert call["tenant_id"] == "tenant-1"
    # The declared local route actually served the accepted response: the
    # handler's post-flight identity and the provider's own echo agree.
    assert call["served_provider"] == "ollama"
    assert call["served_model"] == OLLAMA_MODEL
    attribution = call["attribution"]
    assert attribution["served_route"] == {
        "provider": "ollama", "model": OLLAMA_MODEL}
    assert attribution["requested_route"] == {
        "provider": "ollama", "model": OLLAMA_MODEL}
    assert attribution["resolved_model"] == OLLAMA_MODEL
    # No remote provider can be dispatched: the policy allows ollama only.
    assert call["policy_mode"] == "selected"
    assert call["policy_allowed"] == ["ollama"]
    assert "ollama" in call["client_providers"]
    # Generation must not execute or register the design.
    assert env["fake"].executed == []
    assert env["fake"].registered == []

    workflow_id = created["workflow_id"]

    # Fresh-session durable readback on the scratch store.
    fresh_session = env["Session"]()
    try:
        row = fresh_session.query(Workflow).filter(
            Workflow.id == workflow_id).one()
        assert row.tenant_id == "tenant-1"
        assert row.user_id == "user-1"
        assert row.status == "designed"
        assert row.configuration["workspace_id"] == "ws-1"
        assert row.configuration["definition_digest"] == (
            created["definition_digest"])
        assert row.configuration["generation"]["profile"] == (
            "workflow_blueprint")
        assert row.configuration["generation"]["source"] == "model"
    finally:
        fresh_session.close()

    # Authenticated HTTP readback (production get_db, its own fresh session).
    status, readback = _request(
        "GET", f"{base_url}/api/v1/workflows/generated/{workflow_id}",
        token)
    assert status == 200, readback
    assert readback["definition_digest"] == created["definition_digest"]
    assert readback["nodes"] == created["nodes"]
    assert readback["steps"] == created["steps"]
    assert readback["start_step"] == created["start_step"]
    assert readback["triggers"] == created["triggers"]

    # Workspace/tenant isolation: user-2 is a different workspace in the same
    # tenant; user-3 is the same workspace id under a different tenant. Both
    # must be denied (the tenant id and the workspace id are both enforced).
    status, _ = _request(
        "GET", f"{base_url}/api/v1/workflows/generated/{workflow_id}",
        _token_for("user-2", env))
    assert status == 404
    status, _ = _request(
        "GET", f"{base_url}/api/v1/workflows/generated/{workflow_id}",
        _token_for("user-3", env))
    assert status == 404
    assert env["fake"].executed == []
    assert env["fake"].registered == []
