"""First-gate reconciliation: actual public routes, real compile output.

Only the model transport is doubled (LLMService.generate_structured_response).
Everything else is the real route, compiler, SQLite persistence, and the real
canonical orchestrator trigger handler.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

assert os.environ["TESTING"] == "1"
assert os.environ["DATABASE_URL"].startswith("sqlite:///<scratch-path>

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.auth as auth_module
import core.database as database_module
from core.database import Base
from core.models import AgentRegistry, Tenant, User, Workspace
from core.agents.workflow_blueprint import WorkflowBlueprintDraft

TENANT = "tenant-gate"
WORKSPACE = "ws-gate"
USER_ID = "user-gate"
AGENT_ID = "agent-gate"

engine = create_engine(
    os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine, expire_on_commit=False)

seed = Session()
seed.add(Tenant(id=TENANT, name="Gate Tenant", subdomain="gate-tenant"))
seed.add(Workspace(id=WORKSPACE, name="Gate Workspace", tenant_id=TENANT))
gate_user = User(
    id=USER_ID, tenant_id=TENANT, workspace_id=WORKSPACE,
    first_name="Gate", last_name="User", role="super_admin",
    status="active", is_active=True)
seed.add(gate_user)
seed.add(AgentRegistry(
    id=AGENT_ID, name="Gate Agent", category="Operations",
    module_path="core.agents.queen_agent", class_name="QueenAgent",
    confidence_score=0.95, status="active", tenant_id=TENANT,
    workspace_id=WORKSPACE, enabled=True, is_system_agent=False,
    required_role_for_autonomy="team_lead"))
seed.commit()
seed.close()


def override_get_db():
    db = Session()
    try:
        yield db
    finally:
        db.close()


async def override_current_user():
    db = Session()
    try:
        return db.query(User).filter(User.id == USER_ID).one()
    finally:
        db.close()


database_module.get_db = override_get_db
auth_module.get_current_user = override_current_user

# ---- model transport double (the only doubled seam) ----
from core.llm_service import LLMService

DRAFT = {
    "architecture_name": "Gate manual trigger design",
    "description": "One real compiled trigger step for route reconciliation.",
    "execution_mode": "one_off",
    "nodes": [{
        "id": "start",
        "type": "trigger",
        "name": "Manual start",
        "metadata": {"trigger_event": "manual"},
    }],
    "required_integrations": [],
    "missing_capabilities": [],
}


async def fake_structured_response(self, **kwargs):
    return WorkflowBlueprintDraft.model_validate(DRAFT)


LLMService.generate_structured_response = fake_structured_response

from core.workflow_endpoints import router as workflow_router
from advanced_workflow_api import router as advanced_router
from api.agent_governance_routes import router as governance_router

app = FastAPI()
# Same order as backend/main_api_app.py: live store routes first, advanced
# generated-blueprint routes later, governance last.
app.include_router(workflow_router, prefix="/api/v1/workflows")
app.include_router(advanced_router)
app.include_router(governance_router)

client = TestClient(app)
out = {"steps": []}

# Route-order evidence: which route owns the literal /workflows path?
matching = []
for route in app.routes:
    path = getattr(route, "path", "")
    if path == "/api/v1/workflows/workflows":
        matching.append({
            "path": path,
            "name": getattr(route, "name", ""),
            "methods": sorted(getattr(route, "methods", []) or []),
        })
out["route_resolution"] = matching

# 1. Real generate-from-agent route.
gen = client.post(
    "/api/v1/workflows/generate-from-agent",
    json={"prompt": "design a workflow with a manual start"},
)
out["steps"].append({"step": "generate", "status": gen.status_code,
                     "body": gen.json()})
gen_body = gen.json()
workflow_id = gen_body.get("workflow_id")
digest = gen_body.get("definition_digest")

# 2. Scoped generated readback.
read = client.get(f"/api/v1/workflows/generated/{workflow_id}")
out["steps"].append({"step": "generated_readback", "status": read.status_code,
                     "body": read.json()})

# 3. My Workflows list before any deploy.
before = client.get("/api/v1/workflows/workflows")
out["steps"].append({"step": "my_workflows_before", "status": before.status_code,
                     "ids": [w.get("id") for w in before.json()]})

# 4. The old Deploy route does not exist.
deploy = client.post(
    f"/api/v1/workflows/{workflow_id}/deploy",
    json={"definition_digest": digest, "agent_id": AGENT_ID},
)
out["steps"].append({"step": "deploy_route_absent", "status": deploy.status_code,
                     "body": deploy.text[:300]})

# 5. Current canonical execute path uses the in-memory registration.
execute_body = {"workflow_id": workflow_id, "input_data": {"probe": True}}
executed = client.post("/api/v1/workflows/execute", json=execute_body)
out["steps"].append({"step": "canonical_execute_in_memory",
                     "status": executed.status_code,
                     "body": executed.json()})

# 6. Fresh-process simulation: clear the process-local registration and retry.
from advanced_workflow_orchestrator import get_orchestrator

orch = get_orchestrator()
orch.workflows.pop(workflow_id, None)
restart_exec = client.post("/api/v1/workflows/execute", json=execute_body)
out["steps"].append({"step": "canonical_execute_after_registry_cleared",
                     "status": restart_exec.status_code,
                     "body": restart_exec.text[:400]})

# 7. No scheduler job was created anywhere in the sequence.
jobs = client.get("/api/v1/workflows/scheduler/jobs")
out["steps"].append({"step": "scheduler_jobs", "status": jobs.status_code,
                     "body": jobs.json()})

# 8. The SQL blueprint status and the file catalog were not silently mutated.
from core.models import Workflow
from core.workflow_endpoints import WORKFLOWS_FILE

db = Session()
try:
    row = db.query(Workflow).filter(Workflow.id == workflow_id).one()
    sql_status = row.status
finally:
    db.close()
out["sql_blueprint_status"] = sql_status
out["catalog_path"] = WORKFLOWS_FILE
out["catalog_exists"] = Path(WORKFLOWS_FILE).exists()
out["catalog_rows"] = (
    json.loads(Path(WORKFLOWS_FILE).read_text())
    if Path(WORKFLOWS_FILE).exists() else None)

print(json.dumps(out, indent=2))
