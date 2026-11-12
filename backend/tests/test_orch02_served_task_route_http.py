"""ORCH-02/07 — served TASK route control: a REAL HTTP server process.

The accepted ORCH-02/07 fleet contracts
(``test_orch02_specialist_response.py`` / ``test_orch07_fleet_audit_consumer.py``)
drive ``AtomMetaAgent.execute`` in-process with a doubled recruitment summary,
so they never exercise the ordinary chat route or real ``FleetAdmiral``
recruitment. This harness closes that evidence gap the same way the ORCH-01
served control does:

- the production chat router (``POST /api/chat/message`` as mounted in
  ``integrations/chat_routes.py``) is served by a real uvicorn process over a
  bound TCP socket,
- the production auth chain (real ``get_current_user`` JWT validation, no
  dependency override) and the production ``get_db`` consumer are bound to a
  unique explicit scratch SQLite database,
- the production fleet admin route (``/api/v1/fleet/*``) performs the
  consent-gated approval, so enforcement is *persisted*, not patched,
- only the model transport is doubled: every ``LLMService`` generation
  entrypoint plus the NLU route/intent classifiers. No provider, integration,
  live database, deployment, or network action occurs.

Assertions cover both arms of the product claim: before consent the TASK turn
is shadow (recruitment audited, specialists NOT executed, baseline reply), and
after persisted admin approval a fresh session's TASK turn executes the
recruited roster through the real ``GenericAgent`` path and returns their
actual work in the HTTP response, joined to the routing audit row.
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

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.auth import create_access_token
from core.database import Base
from core.fleet_orchestration.fleet_routing_stats import workload_key_for
from core.models import (
    AgentExecution,
    AgentRegistry,
    ChainLink,
    DelegationChain,
    FleetRouterAutomationAction,
    FleetRoutingAudit,
    Tenant,
    User,
    Workspace,
)

TENANT = "default"
WORKSPACE = "default"
# Real second account/workspace on the same scratch store. Scope is resolved
# from the signed-in User row (not from a token claim or the model), so the
# served route must execute and audit as this tenant/workspace.
SCOPED_TENANT = "tenant-beta"
SCOPED_WORKSPACE = "workspace-beta"
FOREIGN_TENANT = "tenant-foreign"
FOREIGN_WORKSPACE = "workspace-foreign"
SCOPED_ADMIN = "admin-beta"
SCOPED_USER = "user-beta"
TASK = "Assemble a short checklist for restocking the office supply cabinet"
# Model-transport double outputs (deterministic, cited verbatim in the reply).
OPS_FINDING = "OPS: restock checklist drafted for cabinet A (gloves, tape, labels)."
COMMS_FINDING = "COMMS: posted a restock note to the team channel for Friday pickup."
SCOPED_OPS_FINDING = "BETA-OPS: beta checklist drafted for cabinet B (batteries, clips)."
SCOPED_COMMS_FINDING = "BETA-COMMS: beta restock note posted to the beta channel."


def _worker_source(trace_path: Path) -> str:
    """Build the served fixture module: production routers + doubled transport."""
    return f'''
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI

from core.llm_service import LLMService
from core.react_models import ReActStep
from ai.nlp_engine import CommandType, NaturalLanguageEngine, RouteCategory

trace = Path({str(trace_path)!r})
state = {{"calls": []}}


def save():
    trace.write_text(json.dumps(state))


def mark_route():
    from core.llm.model_provenance import set_served_route
    set_served_route("controlled-provider", "controlled-model")


class ControlledHandler:
    default_provider_id = "controlled-provider"
    clients = [object()]
    _last_used_model = "controlled-model"
    _last_used_provider = "controlled-provider"

    def analyze_query_complexity(self, query):
        return SimpleNamespace(value="medium")

    async def get_optimal_provider(self, *args, **kwargs):
        return ("controlled-provider", "controlled-model")

    async def get_ranked_providers(self, *args, **kwargs):
        return [("controlled-provider", "controlled-model")]


async def controlled_structured_response(self, **kwargs):
    mark_route()
    model = kwargs.get("response_model")
    name = getattr(model, "__name__", "")
    state["calls"].append({{"kind": "structured_response", "model": name}})
    save()
    if name == "TaskAnalysis":
        return model(
            complexity="medium",
            required_capabilities=["operations", "communications"],
            estimated_duration="30 minutes",
            specialist_count=2,
            reasoning="office-work checklist spanning operations and comms",
        )
    if name == "RecruitmentPlan":
        return model(
            goal_analysis="office-work checklist spanning operations and comms",
            required_domains=["operations", "communications"],
            domain_rationale={{
                "operations": "draft the restock checklist",
                "communications": "share the checklist with the team",
            }},
            complexity_estimate="medium",
            estimated_parallelizable=True,
            suggested_specialist_count=2,
        )
    if name == "ReActStep":
        # Shadow / legacy ReAct baseline (fleet not enforced for this turn).
        return model(thought="baseline", final_answer="controlled baseline answer")
    return None


async def controlled_structured(self, **kwargs):
    mark_route()
    prompt = kwargs.get("prompt", "")
    agent_id = kwargs.get("agent_id")
    state["calls"].append({{"kind": "specialist_step", "agent_id": agent_id}})
    save()
    if agent_id == "beta-ops":
        return ReActStep(thought="ops", final_answer={SCOPED_OPS_FINDING!r})
    if agent_id == "beta-comms":
        return ReActStep(thought="comms", final_answer={SCOPED_COMMS_FINDING!r})
    if "operations specialist" in prompt:
        return ReActStep(thought="ops", final_answer={OPS_FINDING!r})
    if "communications specialist" in prompt:
        return ReActStep(thought="comms", final_answer={COMMS_FINDING!r})
    return ReActStep(thought="done", final_answer="controlled baseline answer")


async def controlled_completion(self, **kwargs):
    mark_route()
    state["calls"].append({{"kind": "completion"}})
    save()
    # Empty content -> the reply leg returns None, so the feature handler's
    # answer (the specialist contributions) is the user-visible reply.
    return {{"content": "", "model": "controlled-model", "provider": "controlled-provider"}}


async def controlled_stream(self, **kwargs):
    state["calls"].append({{"kind": "stream"}})
    save()
    if False:
        yield ""


async def controlled_response(self, **kwargs):
    mark_route()
    return "controlled baseline answer"


async def controlled_generate(self, **kwargs):
    mark_route()
    return "controlled baseline answer"


def controlled_handler(self, *args, **kwargs):
    return ControlledHandler()


LLMService.generate_structured_response = controlled_structured_response
LLMService.generate_structured = controlled_structured
LLMService.generate_completion = controlled_completion
LLMService.stream_completion = controlled_stream
LLMService.generate_response = controlled_response
LLMService.generate = controlled_generate
LLMService._get_handler = controlled_handler


async def controlled_parse_command(self, message, **kwargs):
    return SimpleNamespace(
        command_type=CommandType.UNKNOWN, confidence=0.6,
        entities=[], platforms=[])


async def controlled_classify_route(self, prompt, **kwargs):
    return SimpleNamespace(
        category=RouteCategory.ONE_OFF,
        reasoning="controlled one-off office-work route",
        confidence=0.9)


NaturalLanguageEngine.parse_command = controlled_parse_command
NaturalLanguageEngine.classify_route = controlled_classify_route

# In-app notification side effect is not part of this control.
import core.fleet_orchestration.fleet_router_automation as fleet_automation
fleet_automation._spawn_notification = lambda *a, **k: None

from integrations.chat_routes import router as chat_router
from api.fleet_router_routes import router as fleet_router

save()
app = FastAPI()
app.include_router(chat_router)
app.include_router(fleet_router)
'''


class _Trace:
    def __init__(self, path: Path):
        self.path = path

    @property
    def calls(self):
        try:
            return json.loads(self.path.read_text())["calls"]
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return []


@pytest.fixture()
def served_task_env(tmp_path):
    db_path = tmp_path / "served_task.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        db.add_all([
            Tenant(id=TENANT, name="Default", subdomain="default"),
            Workspace(id=WORKSPACE, name="Default", tenant_id=TENANT),
            Tenant(id=SCOPED_TENANT, name="Beta", subdomain="beta"),
            Workspace(
                id=SCOPED_WORKSPACE, name="Beta", tenant_id=SCOPED_TENANT),
            Tenant(id=FOREIGN_TENANT, name="Foreign", subdomain="foreign"),
            Workspace(
                id=FOREIGN_WORKSPACE, name="Foreign",
                tenant_id=FOREIGN_TENANT),
        ])
        db.add_all([
            User(id="admin-1", email="admin@example.com",
                 hashed_password="x", first_name="Admin", last_name="Test",
                 role="admin", status="active", workspace_id=WORKSPACE,
                 tenant_id=TENANT, is_active=True),
            User(id="user-1", email="user@example.com",
                 hashed_password="x", first_name="U", last_name="Test",
                 role="member", status="active", workspace_id=WORKSPACE,
                 tenant_id=TENANT, is_active=True),
            User(id=SCOPED_ADMIN, email="admin-beta@example.com",
                 hashed_password="x", first_name="Beta", last_name="Admin",
                 role="admin", status="active", workspace_id=SCOPED_WORKSPACE,
                 tenant_id=SCOPED_TENANT, is_active=True),
            User(id=SCOPED_USER, email="user-beta@example.com",
                 hashed_password="x", first_name="Beta", last_name="User",
                 role="member", status="active", workspace_id=SCOPED_WORKSPACE,
                 tenant_id=SCOPED_TENANT, is_active=True),
        ])
        # Production-shaped Personal-Edition hires: registry rows created by
        # the API carry no workspace, which the default governance scope
        # treats as visible (see AgentGovernanceService._workspace_scope_condition).
        db.add_all([
            AgentRegistry(
                id="a1", name="Ops Coordinator", display_name="Ops Coordinator",
                category="operations", module_path="core.generic_agent",
                class_name="GenericAgent", tenant_id=TENANT,
                workspace_id=None, status="intern", enabled=True,
                capabilities=["operations"], specialty="operations",
                user_id="user-1"),
            AgentRegistry(
                id="a2", name="Comms Lead", display_name="Comms Lead",
                category="communications", module_path="core.generic_agent",
                class_name="GenericAgent", tenant_id=TENANT,
                workspace_id=None, status="intern", enabled=True,
                capabilities=["communications"], specialty="communications",
                user_id="user-1"),
        ])
        # The second account's own roster. Scope must come from the signed-in
        # User row, not from the process-wide default meta-agent singleton.
        db.add_all([
            AgentRegistry(
                id="beta-ops", name="Beta Ops", display_name="Beta Ops",
                category="operations", module_path="core.generic_agent",
                class_name="GenericAgent", tenant_id=SCOPED_TENANT,
                workspace_id=SCOPED_WORKSPACE, status="intern", enabled=True,
                capabilities=["operations"], specialty="operations",
                user_id=SCOPED_USER),
            AgentRegistry(
                id="beta-comms", name="Beta Comms", display_name="Beta Comms",
                category="communications", module_path="core.generic_agent",
                class_name="GenericAgent", tenant_id=SCOPED_TENANT,
                workspace_id=SCOPED_WORKSPACE, status="intern", enabled=True,
                capabilities=["communications"], specialty="communications",
                user_id=SCOPED_USER),
        ])
        # Stronger-scoring foreign agents. If recruitment or governance loses
        # the authenticated scope, these outrank the beta roster and would
        # either be recruited or abort recruitment — the test must never see
        # them in a roster, chain link or model call.
        db.add_all([
            AgentRegistry(
                id="foreign-ops", name="Foreign Ops",
                display_name="Foreign Ops", category="operations",
                module_path="core.generic_agent", class_name="GenericAgent",
                tenant_id=FOREIGN_TENANT, workspace_id=FOREIGN_WORKSPACE,
                status="autonomous", enabled=True, confidence_score=0.99,
                capabilities=[
                    "operations", "logistics", "supply", "inventory",
                    "fulfillment", "workflow"],
                specialty="operations", user_id="foreign-user"),
            AgentRegistry(
                id="foreign-comms", name="Foreign Comms",
                display_name="Foreign Comms", category="communications",
                module_path="core.generic_agent", class_name="GenericAgent",
                tenant_id=FOREIGN_TENANT, workspace_id=FOREIGN_WORKSPACE,
                status="autonomous", enabled=True, confidence_score=0.99,
                capabilities=[
                    "communications", "pr", "press", "email", "messaging",
                    "notification"],
                specialty="communications", user_id="foreign-user"),
        ])
        # Historical shadow baseline for the consent-gated calibration pass.
        # These are the same healthy, outcome-joined rows the accepted ORCH-07
        # consumer seeds; consent itself is granted through the served HTTP
        # automation/approve route below.
        wk = workload_key_for(TASK)
        for i in range(40):
            db.add(FleetRoutingAudit(
                tenant_id=TENANT, workspace_id=WORKSPACE,
                agent_id="atom_main", execution_id=f"historical-{i}",
                workload_key=wk, request_text=TASK[:200],
                chain_id=f"historical-chain-{i}", specialists_count=2,
                roster_json=[], recruitment_succeeded=True, enforced=False,
                decision_source="fleet_eligible", success=True,
                actual_model="controlled-model",
                actual_provider="controlled-provider"))
        db.commit()

    trace = tmp_path / "task-transport-observations.json"
    worker = tmp_path / "served_task_fixture.py"
    worker.write_text(_worker_source(trace))
    env = os.environ.copy()
    env.update(
        TESTING="1",
        DATABASE_URL=f"sqlite:///{db_path}",
        # Makes the explicit scratch URL authoritative even outside a pytest
        # parent (get_database_url honors non-dev URLs under this marker).
        PYTEST_CURRENT_TEST="tests/test_orch02_served_task_route_http.py",
        ATOM_DATA_DIR=str(tmp_path / "data"),
        LANCEDB_URI=str(tmp_path / "lancedb"),
        LANCEDB_PATH=str(tmp_path / "lancedb"),
        ATOM_DISABLE_TOOL_PLANNER="1",
        ATOM_FLEET_ROUTING_ENABLED="true",
        ATOM_FLEET_ROUTER_AUTO_ENFORCE="approve",
        ATOM_STREAM_FIRST_VISIBLE_SECONDS="1",
    )
    backend = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = backend
    assert str(db_path) in env["DATABASE_URL"]
    assert "data/atom.db" not in env["DATABASE_URL"]

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    base_url = f"http://127.0.0.1:{listener.getsockname()[1]}"
    log = (tmp_path / "server.log").open("w")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "served_task_fixture:app",
         "--app-dir", str(tmp_path), "--fd", str(listener.fileno()),
         "--log-level", "warning"],
        cwd=backend, env=env, pass_fds=(listener.fileno(),),
        stdout=log, stderr=log,
    )
    listener.close()
    try:
        deadline = time.monotonic() + 60
        while True:
            if process.poll() is not None:
                log.flush()
                pytest.fail((tmp_path / "server.log").read_text()[-8000:])
            try:
                with urllib.request.urlopen(base_url + "/openapi.json", timeout=1):
                    break
            except (OSError, urllib.error.URLError):
                if time.monotonic() >= deadline:
                    pytest.fail("served task fixture failed to start in 60 seconds")
                time.sleep(0.05)
        yield {
            "base_url": base_url,
            "trace": _Trace(trace),
            "Session": sessions,
            "server_pid": process.pid,
        }
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        log.close()
        engine.dispose()


# --- HTTP helpers (real socket, no TestClient) -------------------------------


def _token_for(user_id: str, served_task_env) -> str:
    with served_task_env["Session"]() as session:
        user = session.query(User).filter(User.id == user_id).one_or_none()
        assert user is not None
        return create_access_token({"sub": user_id}, user=user)


def _request(method: str, url: str, token: str | None, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"raw": body}


def _chat(base_url, token, message=TASK, session_id=None,
          context_workspace=WORKSPACE, context_tenant=None):
    context = {}
    if context_workspace is not None:
        context["workspace_id"] = context_workspace
    if context_tenant is not None:
        context["tenant_id"] = context_tenant
    return _request("POST", f"{base_url}/api/chat/message", token, {
        "message": message,
        "user_id": "ignored-by-route",
        "session_id": session_id,
        "context": context,
    })


def _audit_row(served_task_env, execution_id):
    db = served_task_env["Session"]()
    try:
        return db.query(FleetRoutingAudit).filter(
            FleetRoutingAudit.execution_id == execution_id).one()
    finally:
        db.close()


def _atom_run(base_url, token, session_id):
    """Resolve the meta-agent execution for a chat session over real HTTP.

    ``GET /api/chat/trace/{session_id}`` joins ``AgentExecution.metadata_json``
    to the session — this is the product's own readback surface, so it proves
    the audit row belongs to the authenticated session without guessing.
    """
    status, trace = _request(
        "GET", f"{base_url}/api/chat/trace/{session_id}", token)
    assert status == 200, trace
    runs = [run for run in trace["runs"] if run["agent_id"] == "atom_main"]
    assert len(runs) == 1, trace
    return runs[0]


# --- The served control ------------------------------------------------------


def test_served_task_route_shadow_then_persisted_consent_enforces(
        served_task_env):
    base_url = served_task_env["base_url"]
    assert served_task_env["server_pid"] != os.getpid()
    member = _token_for("user-1", served_task_env)
    admin = _token_for("admin-1", served_task_env)

    # Unauthenticated chat is refused by the REAL auth dependency.
    status, body = _request(
        "POST", f"{base_url}/api/chat/message", None,
        {"message": TASK, "user_id": "ignored"})
    assert status == 401, body

    # Opt-in enforcement is OFF: the served fleet status says shadow.
    status, before = _request(
        "GET", f"{base_url}/api/v1/fleet/automation/status", None)
    assert status == 200, before
    assert before["enforced"] is False
    assert before["phase"] == "ready", before

    # --- Shadow arm: ordinary TASK turn; recruitment audited, no dispatch ---
    status, shadow = _chat(base_url, member)
    assert status == 200, shadow
    assert shadow["success"] is True, shadow
    assert shadow["intent"] == "agent_request"
    assert shadow["message"] == "controlled baseline answer"
    assert "Specialist contributions" not in shadow["message"]
    assert shadow["execution_id"]

    shadow_run = _atom_run(
        base_url, member, shadow["session_id"])
    assert shadow_run["status"] == "completed"
    assert shadow_run["input_summary"] == TASK

    shadow_row = _audit_row(served_task_env, shadow_run["execution_id"])
    assert shadow_row.tenant_id == TENANT
    assert shadow_row.workspace_id == WORKSPACE
    assert shadow_row.agent_id == "atom_main"
    assert shadow_row.chain_id
    assert shadow_row.workload_key == workload_key_for(TASK)
    assert shadow_row.decision_source == "fleet_eligible"
    assert shadow_row.specialists_count == 2
    assert [item["agent_id"] for item in shadow_row.roster_json] == ["a1", "a2"]
    assert shadow_row.recruitment_succeeded is True
    assert shadow_row.enforced is False
    assert shadow_row.success is True
    assert shadow_row.error is None
    # The shadow arm really did recruit both specialists — it just never
    # dispatched them (links stay pending; verified by the empty model trace).
    db = served_task_env["Session"]()
    try:
        shadow_links = db.query(ChainLink).filter(
            ChainLink.chain_id == shadow_row.chain_id).all()
        assert {link.child_agent_id for link in shadow_links} == {"a1", "a2"}
        assert {link.status for link in shadow_links} == {"pending"}
    finally:
        db.close()
    # Shadow deliberately does not run specialists, so no fleet-arm model call.
    shadow_calls = served_task_env["trace"].calls
    assert shadow_calls == [
        {"kind": "structured_response", "model": "_Interpretation"},
        {"kind": "stream"},
        {"kind": "completion"},
        {"kind": "structured_response", "model": "TaskAnalysis"},
        {"kind": "structured_response", "model": "RecruitmentPlan"},
        {"kind": "structured_response", "model": "ReActStep"},
    ]

    # --- Consent via the real served admin route, persisted to scratch DB ---
    status, queued = _request(
        "POST", f"{base_url}/api/v1/fleet/automation/run-now", admin)
    assert status == 200, queued
    assert queued["queued"] == ["__global__"], queued

    status, automation = _request(
        "GET", f"{base_url}/api/v1/fleet/automation", admin)
    assert status == 200, automation
    pending = automation["pending_approvals"]
    assert len(pending) == 1, automation
    assert pending[0]["verdict"] == "enable"
    assert pending[0]["state"] == "approval"

    status, approved = _request(
        "POST", f"{base_url}/api/v1/fleet/automation/approve", admin, {})
    assert status == 200, approved
    assert approved["applied"] is True
    assert approved["verdict"] == "enable"
    action_id = approved["action_id"]

    fresh = served_task_env["Session"]()
    try:
        action = fresh.query(FleetRouterAutomationAction).filter(
            FleetRouterAutomationAction.id == action_id).one()
        assert action.workload_key == "__global__"
        assert action.verdict == "enable"
        assert action.mode == "approve"
        assert action.state == "applied"
        assert action.decided_at is not None
    finally:
        fresh.close()

    # The served process now resolves enforcement from the persisted action.
    status, after = _request(
        "GET", f"{base_url}/api/v1/fleet/automation/status", None)
    assert status == 200, after
    assert after["enforced"] is True
    assert after["phase"] == "enforced", after

    # --- Enforced arm: fresh session -> recruited work in the HTTP reply ----
    status, enforced = _chat(base_url, member)
    assert status == 200, enforced
    assert enforced["success"] is True, enforced
    assert enforced["intent"] == "agent_request"
    message = enforced["message"]
    assert "Specialist contributions" in message
    assert "Ops Coordinator" in message
    assert "Comms Lead" in message
    assert OPS_FINDING in message
    assert COMMS_FINDING in message
    assert "controlled baseline answer" not in message
    assert enforced["execution_id"] and enforced["session_id"]

    enforced_calls = served_task_env["trace"].calls
    specialist_ids = [
        call["agent_id"] for call in enforced_calls
        if call["kind"] == "specialist_step"
    ]
    assert specialist_ids == ["a1", "a2"]

    # Fresh-session routing audit readback: durable row + joined outcome.
    enforced_run = _atom_run(
        base_url, member, enforced["session_id"])
    assert enforced_run["status"] == "completed"
    row = _audit_row(served_task_env, enforced_run["execution_id"])
    assert row.tenant_id == TENANT
    assert row.workspace_id == WORKSPACE
    assert row.agent_id == "atom_main"
    assert row.chain_id
    assert row.workload_key == workload_key_for(TASK)
    assert row.decision_source == "fleet_eligible"
    assert row.specialists_count == 2
    assert [item["agent_id"] for item in row.roster_json] == ["a1", "a2"]
    assert {item["domain"] for item in row.roster_json} == {
        "operations", "communications"}
    assert row.recruitment_succeeded is True
    assert row.enforced is True
    assert row.success is True
    assert row.error is None
    assert row.actual_model == "controlled-model"
    assert row.actual_provider == "controlled-provider"
    assert row.actual_latency_ms is not None

    fresh = served_task_env["Session"]()
    try:
        execution = fresh.query(AgentExecution).filter(
            AgentExecution.id == enforced_run["execution_id"]).one()
        assert execution.status == "completed"
        assert execution.result_summary
        chain = fresh.query(DelegationChain).filter(
            DelegationChain.id == row.chain_id).one()
        assert chain.status == "completed"
        assert chain.metadata_json["specialist_execution"]["status"] == (
            "completed")
    finally:
        fresh.close()

    # Fresh-session HTTP readback: the persisted assistant turn carries the
    # same specialist work the live response returned.
    status, history = _request(
        "GET",
        f"{base_url}/api/chat/history/{enforced['session_id']}",
        member)
    assert status == 200, history
    assistant = [
        entry for entry in history["messages"]
        if entry.get("role") == "assistant"
    ]
    assert assistant, history
    assert "Specialist contributions" in assistant[-1]["response"]["message"]
    assert OPS_FINDING in assistant[-1]["response"]["message"]
    assert COMMS_FINDING in assistant[-1]["response"]["message"]


def test_served_task_route_non_default_tenant_and_workspace(
        served_task_env):
    """Same served TASK route, authenticated as a real second account.

    The default regression above proves the default scope still works. This
    arm proves the ordinary served route resolves the caller's scope from the
    signed-in User row, executes only that workspace's roster, and persists an
    audit row bound to exactly that tenant/workspace. Foreign-workspace agents
    are seeded stronger on purpose and must never enter a roster, a chain link,
    or a model call.
    """
    base_url = served_task_env["base_url"]
    assert served_task_env["server_pid"] != os.getpid()
    member = _token_for(SCOPED_USER, served_task_env)
    admin = _token_for(SCOPED_ADMIN, served_task_env)

    # Scope is not taken from the token claims or the request body: the helper
    # deliberately omits context.workspace_id, so the production chat route has
    # to resolve it from the authenticated User row.
    status, before = _request(
        "GET", f"{base_url}/api/v1/fleet/automation/status", None)
    assert status == 200, before
    assert before["enforced"] is False
    assert before["phase"] == "ready", before

    # --- Shadow arm in the second scope: recruit locally, never dispatch ---
    status, shadow = _chat(
        base_url, member, context_workspace=None)
    assert status == 200, shadow
    assert shadow["success"] is True, shadow
    assert shadow["intent"] == "agent_request"
    assert shadow["message"] == "controlled baseline answer"
    assert shadow["execution_id"]

    shadow_run = _atom_run(base_url, member, shadow["session_id"])
    assert shadow_run["status"] == "completed"
    shadow_row = _audit_row(served_task_env, shadow_run["execution_id"])
    assert shadow_row.tenant_id == SCOPED_TENANT
    assert shadow_row.workspace_id == SCOPED_WORKSPACE
    assert shadow_row.tenant_id != TENANT
    assert shadow_row.workspace_id != WORKSPACE
    assert shadow_row.agent_id == "atom_main"
    assert shadow_row.chain_id
    assert shadow_row.workload_key == workload_key_for(TASK)
    assert shadow_row.decision_source == "fleet_eligible"
    assert shadow_row.specialists_count == 2
    assert [item["agent_id"] for item in shadow_row.roster_json] == [
        "beta-ops", "beta-comms"]
    assert shadow_row.recruitment_succeeded is True
    assert shadow_row.enforced is False
    assert shadow_row.success is True
    assert shadow_row.error is None

    db = served_task_env["Session"]()
    try:
        shadow_links = db.query(ChainLink).filter(
            ChainLink.chain_id == shadow_row.chain_id).all()
        assert {link.child_agent_id for link in shadow_links} == {
            "beta-ops", "beta-comms"}
        assert {link.status for link in shadow_links} == {"pending"}
        # The stronger foreign agents were never even attached to the chain.
        assert not any(
            str(link.child_agent_id).startswith("foreign-")
            for link in shadow_links)
    finally:
        db.close()
    assert served_task_env["trace"].calls == [
        {"kind": "structured_response", "model": "_Interpretation"},
        {"kind": "stream"},
        {"kind": "completion"},
        {"kind": "structured_response", "model": "TaskAnalysis"},
        {"kind": "structured_response", "model": "RecruitmentPlan"},
        {"kind": "structured_response", "model": "ReActStep"},
    ]

    # --- Consent through the real served admin route -----------------------
    status, queued = _request(
        "POST", f"{base_url}/api/v1/fleet/automation/run-now", admin)
    assert status == 200, queued
    assert queued["queued"] == ["__global__"], queued

    status, automation = _request(
        "GET", f"{base_url}/api/v1/fleet/automation", admin)
    assert status == 200, automation
    pending = automation["pending_approvals"]
    assert len(pending) == 1, automation
    assert pending[0]["verdict"] == "enable"
    assert pending[0]["state"] == "approval"

    status, approved = _request(
        "POST", f"{base_url}/api/v1/fleet/automation/approve", admin, {})
    assert status == 200, approved
    assert approved["applied"] is True
    assert approved["verdict"] == "enable"
    action_id = approved["action_id"]

    fresh = served_task_env["Session"]()
    try:
        action = fresh.query(FleetRouterAutomationAction).filter(
            FleetRouterAutomationAction.id == action_id).one()
        assert action.workload_key == "__global__"
        assert action.verdict == "enable"
        assert action.mode == "approve"
        assert action.state == "applied"
        assert action.decided_at is not None
    finally:
        fresh.close()

    status, after = _request(
        "GET", f"{base_url}/api/v1/fleet/automation/status", None)
    assert status == 200, after
    assert after["enforced"] is True
    assert after["phase"] == "enforced", after

    # --- Enforced arm: beta work in the reply, no foreign execution --------
    status, enforced = _chat(
        base_url, member, context_workspace=None)
    assert status == 200, enforced
    assert enforced["success"] is True, enforced
    assert enforced["intent"] == "agent_request"
    message = enforced["message"]
    assert "Specialist contributions" in message
    assert "Beta Ops" in message
    assert "Beta Comms" in message
    assert SCOPED_OPS_FINDING in message
    assert SCOPED_COMMS_FINDING in message
    assert "Foreign Ops" not in message
    assert "Foreign Comms" not in message
    assert enforced["execution_id"] and enforced["session_id"]

    enforced_calls = served_task_env["trace"].calls
    specialist_ids = [
        call["agent_id"] for call in enforced_calls
        if call["kind"] == "specialist_step"
    ]
    assert specialist_ids == ["beta-ops", "beta-comms"]
    assert not any(
        str(agent_id).startswith("foreign-")
        for agent_id in specialist_ids)

    # Exact durable routing audit for THIS authenticated execution.
    enforced_run = _atom_run(base_url, member, enforced["session_id"])
    assert enforced_run["status"] == "completed"
    row = _audit_row(served_task_env, enforced_run["execution_id"])
    assert row.execution_id == enforced_run["execution_id"]
    assert row.tenant_id == SCOPED_TENANT
    assert row.workspace_id == SCOPED_WORKSPACE
    assert row.agent_id == "atom_main"
    assert row.chain_id
    assert row.workload_key == workload_key_for(TASK)
    assert row.decision_source == "fleet_eligible"
    assert row.specialists_count == 2
    assert [item["agent_id"] for item in row.roster_json] == [
        "beta-ops", "beta-comms"]
    assert {item["domain"] for item in row.roster_json} == {
        "operations", "communications"}
    assert not any(
        str(item["agent_id"]).startswith("foreign-")
        for item in row.roster_json)
    assert row.recruitment_succeeded is True
    assert row.enforced is True
    assert row.success is True
    assert row.error is None
    assert row.actual_model == "controlled-model"
    assert row.actual_provider == "controlled-provider"
    assert row.actual_latency_ms is not None

    fresh = served_task_env["Session"]()
    try:
        executions = fresh.query(AgentExecution).filter(
            AgentExecution.id == enforced_run["execution_id"]).all()
        assert len(executions) == 1
        execution = executions[0]
        assert execution.tenant_id == SCOPED_TENANT
        assert execution.workspace_id == SCOPED_WORKSPACE
        assert execution.status == "completed"
        assert execution.result_summary

        audits = fresh.query(FleetRoutingAudit).filter(
            FleetRoutingAudit.execution_id == enforced_run[
                "execution_id"]).all()
        assert len(audits) == 1
        assert audits[0].tenant_id == SCOPED_TENANT
        assert audits[0].workspace_id == SCOPED_WORKSPACE

        chain = fresh.query(DelegationChain).filter(
            DelegationChain.id == row.chain_id).one()
        assert chain.tenant_id == SCOPED_TENANT
        assert chain.metadata_json["workspace_id"] == SCOPED_WORKSPACE
        assert chain.status == "completed"
        assert chain.metadata_json["specialist_execution"]["status"] == (
            "completed")
        links = fresh.query(ChainLink).filter(
            ChainLink.chain_id == row.chain_id).all()
        assert sorted(link.child_agent_id for link in links) == [
            "beta-comms", "beta-ops"]
    finally:
        fresh.close()

    # Fresh-session HTTP readback carries the same beta-only specialist work.
    status, history = _request(
        "GET",
        f"{base_url}/api/chat/history/{enforced['session_id']}",
        member)
    assert status == 200, history
    assistant = [
        entry for entry in history["messages"]
        if entry.get("role") == "assistant"
    ]
    assert assistant, history
    persisted = assistant[-1]["response"]["message"]
    assert "Specialist contributions" in persisted
    assert SCOPED_OPS_FINDING in persisted
    assert SCOPED_COMMS_FINDING in persisted
    assert "Foreign Ops" not in persisted
    assert "Foreign Comms" not in persisted

    # --- Isolation arm: request-supplied scope cannot steer the fleet ------
    # ``context`` is client data. A caller may try to name the foreign
    # workspace/tenant explicitly; the served route must still execute and
    # audit as the signed-in principal's scope. This is the regression the
    # review hold named (an earlier draft trusted context.workspace_id).
    status, spoofed = _chat(
        base_url, member,
        context_workspace=FOREIGN_WORKSPACE,
        context_tenant=FOREIGN_TENANT,
    )
    assert status == 200, spoofed
    assert spoofed["success"] is True, spoofed
    assert spoofed["intent"] == "agent_request"
    spoofed_message = spoofed["message"]
    assert "Specialist contributions" in spoofed_message
    assert SCOPED_OPS_FINDING in spoofed_message
    assert SCOPED_COMMS_FINDING in spoofed_message
    assert "Foreign Ops" not in spoofed_message
    assert "Foreign Comms" not in spoofed_message

    spoofed_run = _atom_run(base_url, member, spoofed["session_id"])
    spoofed_row = _audit_row(served_task_env, spoofed_run["execution_id"])
    assert spoofed_row.tenant_id == SCOPED_TENANT
    assert spoofed_row.workspace_id == SCOPED_WORKSPACE
    assert spoofed_row.tenant_id != FOREIGN_TENANT
    assert spoofed_row.workspace_id != FOREIGN_WORKSPACE
    assert [item["agent_id"] for item in spoofed_row.roster_json] == [
        "beta-ops", "beta-comms"]
    assert not any(
        str(call.get("agent_id", "")).startswith("foreign-")
        for call in served_task_env["trace"].calls
        if call.get("kind") == "specialist_step")
