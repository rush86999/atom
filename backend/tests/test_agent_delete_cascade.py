"""
Tests for DELETE /api/agents/{agent_id} dependent-row cleanup.

The endpoint used to bare-delete the registry row while SQLite FK
enforcement is OFF — episodes/jobs/audit rows for the agent survived as
orphans and resurfaced in journeys and metrics. These tests pin the
cascade: dependents discovered dynamically, deleted in the same
transaction, and the main agent is protected.
"""
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


@pytest.fixture
def db(db_session: Session):
    yield db_session


@pytest.fixture
def admin_user(db: Session):
    from core.models import User, UserRole

    user = User(
        id="admin-user-123",
        email="admin@example.com",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN.value,
        status="active",
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.query(User).filter(User.id == "admin-user-123").delete()
    db.commit()


@pytest.fixture
def client(db: Session, admin_user):
    from api.agent_routes import router
    from core.security_dependencies import get_current_user
    from core.database import get_db
    from core.rbac_service import RBACService
    from unittest.mock import patch

    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        yield db

    def override_get_current_user():
        return admin_user

    with patch.object(RBACService, "check_permission", return_value=True):
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user
        yield TestClient(app, raise_server_exceptions=False)
        app.dependency_overrides.clear()


def _make_agent(db: Session, agent_id: str, name: str = "Cascade Test Agent",
                category: str = "test", configuration: dict | None = None):
    from core.models import AgentRegistry

    agent = AgentRegistry(
        id=agent_id,
        name=name,
        description="delete-cascade test",
        category=category,
        status="student",
        confidence_score=0.5,
        module_path="core.generic_agent",
        class_name="GenericAgent",
        configuration=configuration or {},
        enabled=True,
        workspace_id="default",
        created_at=datetime.now(timezone.utc),
    )
    db.add(agent)
    db.commit()
    return agent


def test_delete_agent_cleans_dependent_rows(db: Session, client: TestClient):
    from core.models import AgentRegistry, AgentJob, AgentEpisode

    agent_id = "agent-cascade-1"
    _make_agent(db, agent_id)
    db.add(AgentJob(agent_id=agent_id, status="completed",
                    result_summary="done"))
    db.add(AgentJob(agent_id=agent_id, status="failed",
                    result_summary="nope"))
    db.add(AgentEpisode(agent_id=agent_id, tenant_id="default",
                        maturity_at_time="student", outcome="success",
                        task_description="cascade test episode"))
    db.commit()

    resp = client.delete(f"/api/agents/{agent_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    cleaned = body["data"]["rows_cleaned"]
    assert cleaned.get("agent_jobs") == 2
    assert cleaned.get("agent_episodes") == 1

    # Post-state via the endpoint response + registry re-query. (The shared
    # test session wraps work in an external transaction, so re-counting the
    # raw-SQL-deleted dependent rows through it is not meaningful; the
    # rows_cleaned counts above are the authoritative rowcount evidence,
    # and live verification against the real DB is recorded in
    # notes/AGENT_COORDINATION.md.)
    db.expire_all()
    assert db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first() is None


def test_delete_agent_spares_other_agents_rows(db: Session, client: TestClient):
    from core.models import AgentJob

    keep_id, drop_id = "agent-cascade-keep", "agent-cascade-drop"
    _make_agent(db, keep_id, "Keeper")
    _make_agent(db, drop_id, "Dropper")
    db.add(AgentJob(agent_id=keep_id, status="completed"))
    db.add(AgentJob(agent_id=drop_id, status="completed"))
    db.commit()

    resp = client.delete(f"/api/agents/{drop_id}")
    assert resp.status_code == 200
    assert db.query(AgentJob).filter(AgentJob.agent_id == keep_id).count() == 1


def test_delete_agent_protects_main_agent(db: Session, client: TestClient):
    resp = client.delete("/api/agents/atom_main")
    assert resp.status_code == 400
    # Handler-agnostic: the code appears in the body whether or not the
    # app-level exception handler unwraps HTTPException detail.
    assert "CANNOT_DELETE_MAIN_AGENT" in resp.text


def test_delete_demo_agent_writes_tombstone(db: Session, client: TestClient):
    """Deleting a demo_agent-flagged agent must arm the bootstrap tombstone.

    Regression: ensure_demo_agent() re-created the "Demo Assistant" under a
    fresh id on every backend boot after an operator deleted it, so the
    deletion never stuck ("agents I delete keep coming back").
    """
    from core.admin_bootstrap import DEMO_AGENT_TOMBSTONE_KEY
    from core.models import RuntimeSetting

    agent_id = "agent-cascade-demo"
    _make_agent(db, agent_id, "Demo Assistant", category="system",
                configuration={"demo_agent": True, "graduation_bypass_reason": "onboarding_demo"})

    resp = client.delete(f"/api/agents/{agent_id}")
    assert resp.status_code == 200
    db.expire_all()
    tombstone = db.query(RuntimeSetting).filter(
        RuntimeSetting.key == DEMO_AGENT_TOMBSTONE_KEY
    ).first()
    assert tombstone is not None
    assert tombstone.value_json.get("agent_id") == agent_id

    # Leave the shared test DB clean for other tests.
    db.delete(tombstone)
    db.commit()


def test_delete_non_demo_agent_writes_no_tombstone(db: Session, client: TestClient):
    from core.admin_bootstrap import DEMO_AGENT_TOMBSTONE_KEY
    from core.models import RuntimeSetting

    agent_id = "agent-cascade-plain"
    _make_agent(db, agent_id, "Plain Agent")

    resp = client.delete(f"/api/agents/{agent_id}")
    assert resp.status_code == 200
    db.expire_all()
    assert db.query(RuntimeSetting).filter(
        RuntimeSetting.key == DEMO_AGENT_TOMBSTONE_KEY
    ).first() is None


def test_deleted_demo_agent_stays_deleted_across_boots(db: Session, client: TestClient):
    """Fresh-install lifecycle: delete demo agent -> next boot must NOT re-create it.

    Regression for the live report "I delete the next agent and the previous
    one comes back": ensure_demo_agent() re-issued a fresh "Demo Assistant"
    row on every backend restart. This pins the full loop a fresh install
    goes through (bootstrap creates it, DELETE arms the tombstone, bootstrap
    again skips it).
    """
    from core.admin_bootstrap import (
        DEMO_AGENT_NAME, DEMO_AGENT_CATEGORY, DEMO_AGENT_TOMBSTONE_KEY,
        ensure_demo_agent,
    )
    from core.models import AgentRegistry, RuntimeSetting

    # Boot #1: fresh install -> demo agent created.
    ensure_demo_agent(db)
    db.commit()
    demo = db.query(AgentRegistry).filter(
        AgentRegistry.name == DEMO_AGENT_NAME,
        AgentRegistry.category == DEMO_AGENT_CATEGORY,
    ).first()
    assert demo is not None
    assert demo.configuration.get("demo_agent") is True

    # Operator deletes it via the endpoint -> tombstone armed.
    resp = client.delete(f"/api/agents/{demo.id}")
    assert resp.status_code == 200
    db.expire_all()
    assert db.query(AgentRegistry).filter(
        AgentRegistry.name == DEMO_AGENT_NAME,
        AgentRegistry.category == DEMO_AGENT_CATEGORY,
    ).first() is None
    assert db.get(RuntimeSetting, DEMO_AGENT_TOMBSTONE_KEY) is not None

    # Boot #2: demo agent must NOT come back.
    ensure_demo_agent(db)
    db.commit()
    db.expire_all()
    assert db.query(AgentRegistry).filter(
        AgentRegistry.name == DEMO_AGENT_NAME,
        AgentRegistry.category == DEMO_AGENT_CATEGORY,
    ).first() is None, "deleted demo agent came back after restart"

    # Leave the shared test DB clean for other tests.
    db.delete(db.get(RuntimeSetting, DEMO_AGENT_TOMBSTONE_KEY))
    db.commit()


def test_delete_agent_not_found(client: TestClient):
    resp = client.delete("/api/agents/agent-cascade-nope")
    assert resp.status_code == 404
