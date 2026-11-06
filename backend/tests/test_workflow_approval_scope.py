"""Same-scope visibility/decision for a real governance-created approval.

The regression this pins: ``AgentGovernanceService.request_approval`` stored
``workspace_id`` but omitted the authoritative ``tenant_id``, so the real
tenant review queue hid the row and its correct reviewer got 404 on decision.
Foreign workspace/tenant reviewers must stay refused.

No model, external provider, workflow executor or approval writer is doubled.
Only the app's authenticated principal and database connection are supplied by
the isolated test fixture. The tested defect happens before any effect.
"""
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.approvals_routes import router
from core.agent_governance_service import AgentGovernanceService
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import AgentRegistry, HITLAction, Tenant, User, Workspace


@pytest.fixture
def approval_world(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path}/public-approval.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        db.add(Tenant(id="tenant-local", name="Local", subdomain="local"))
        db.add(Workspace(id="workspace-local", name="Local", tenant_id="tenant-local"))
        reviewer = User(
            id="local-reviewer", email="reviewer@example.invalid",
            first_name="Local", last_name="Reviewer",
            tenant_id="tenant-local", workspace_id="workspace-local",
            role="team_lead", status="active", is_active=True,
        )
        db.add(reviewer)
        db.add(AgentRegistry(
            id="local-agent", name="Local", category="test",
            module_path="test", class_name="TestAgent", status="student",
            tenant_id="tenant-local", workspace_id="workspace-local",
        ))
        db.commit()

    @contextmanager
    def session_context():
        with Session() as db:
            yield db

    def db_dependency():
        with Session() as db:
            yield db

    import core.intervention_service as intervention_module
    monkeypatch.setattr(intervention_module, "get_db_session", session_context)

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = db_dependency
    app.dependency_overrides[get_current_user] = lambda: reviewer
    with Session() as db:
        governance = AgentGovernanceService(
            db, workspace_id="workspace-local", tenant_id="tenant-local"
        )
        action_id = governance.request_approval(
            agent_id="local-agent", action_type="local_write",
            params={"execution_id": "local-execution", "workflow_id": "local-workflow",
                    "step_id": "local-step", "parameters": {"value": "local"}},
            reason="Controlled workflow approval",
        )
    with TestClient(app, raise_server_exceptions=False) as client:
        yield Session, client, action_id
    engine.dispose()


def test_governance_created_approval_is_visible_to_scoped_reviewer(approval_world):
    Session, client, action_id = approval_world
    response = client.get("/api/agents/approvals/pending")
    assert response.status_code == 200, response.text
    assert action_id in {row["id"] for row in response.json()}, response.json()


def test_governance_created_approval_is_decidable_in_its_own_scope(approval_world):
    Session, client, action_id = approval_world
    response = client.post(
        f"/api/agents/approvals/{action_id}", json={"decision": "rejected"}
    )
    assert response.status_code == 200, response.text
    with Session() as db:
        row = db.get(HITLAction, action_id)
        assert row.tenant_id == "tenant-local"
        assert row.workspace_id == "workspace-local"
        assert row.status == "rejected"


@pytest.mark.parametrize("foreign_scope", ["workspace", "tenant"])
def test_wrong_scope_reviewer_cannot_list_or_decide(approval_world, foreign_scope):
    Session, client, action_id = approval_world
    with Session() as db:
        tenant_id = "tenant-local"
        if foreign_scope == "tenant":
            tenant_id = "tenant-foreign"
            db.add(Tenant(id=tenant_id, name="Foreign", subdomain="foreign"))
        db.add(Workspace(id="workspace-foreign", name="Foreign", tenant_id=tenant_id))
        reviewer = User(
            id="foreign-reviewer", email="foreign@example.invalid",
            first_name="Foreign", last_name="Reviewer", role="team_lead",
            tenant_id=tenant_id, workspace_id="workspace-foreign",
            status="active", is_active=True,
        )
        db.add(reviewer)
        db.commit()
    client.app.dependency_overrides[get_current_user] = lambda: reviewer
    listed = client.get("/api/agents/approvals/pending")
    assert listed.status_code == 200, listed.text
    assert listed.json() == []
    decided = client.post(
        f"/api/agents/approvals/{action_id}", json={"decision": "rejected"}
    )
    assert decided.status_code == 404, decided.text
    with Session() as db:
        assert db.get(HITLAction, action_id).status == "pending"
