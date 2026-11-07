"""Failure-first contracts for workspace-scoped agent readback.

The supplied leading counterexample (member in ``ws1`` receiving a ``ws2``
execution summary from ``GET /api/agents/history``) is the first assertion
here.  The rest of the file gates the bounded Agents read family:
history, list, detail, status and graduation progress.

Every request goes through the real FastAPI router on a scratch SQLite world;
only the authentication leaf (``get_current_user``) is controlled.  No model,
provider, credential, live DB, job dispatch or effect is used.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from api.agent_routes import router as agent_router
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import (
    AgentExecution,
    AgentRegistry,
    Tenant,
    User,
    Workspace,
)


@pytest.fixture()
def world(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/agent-read-scope.db",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    seed = Session()
    seed.add_all([
        Tenant(id="t1", name="Tenant One", subdomain="tenant-one"),
        Tenant(id="t2", name="Tenant Two", subdomain="tenant-two"),
        Workspace(id="ws1", name="Workspace One", tenant_id="t1"),
        Workspace(id="ws2", name="Workspace Two", tenant_id="t1"),
        Workspace(id="ws3", name="Workspace Three", tenant_id="t2"),
        User(id="member-1", tenant_id="t1", workspace_id="ws1",
             email="member1@example.test", first_name="M", last_name="One",
             role="member", status="active", is_active=True),
        User(id="member-2", tenant_id="t1", workspace_id="ws2",
             email="member2@example.test", first_name="M", last_name="Two",
             role="member", status="active", is_active=True),
        User(id="admin-1", tenant_id="t1", workspace_id="ws1",
             email="admin@example.test", first_name="A", last_name="One",
             role="admin", status="active", is_active=True),
        User(id="personal-1", tenant_id=None, workspace_id=None,
             email="personal@example.test", first_name="P", last_name="One",
             role="member", status="active", is_active=True),
    ])
    seed.add_all([
        AgentRegistry(
            id="a1", name="Workspace One Agent", description="own",
            category="operations", module_path="agents.one",
            class_name="AgentOne", status="student", capabilities=[],
            tenant_id="t1", workspace_id="ws1", configuration={},
            enabled=True),
        AgentRegistry(
            id="a2", name="Workspace Two Agent", description="peer",
            category="operations", module_path="agents.two",
            class_name="AgentTwo", status="student", capabilities=[],
            tenant_id="t1", workspace_id="ws2", configuration={},
            enabled=True),
        AgentRegistry(
            id="a3", name="Foreign Tenant Agent", description="foreign",
            category="operations", module_path="agents.three",
            class_name="AgentThree", status="student", capabilities=[],
            tenant_id="t2", workspace_id="ws3", configuration={},
            enabled=True),
        AgentRegistry(
            id="a-shared", name="Shared Personal Agent", description="shared",
            category="operations", module_path="agents.shared",
            class_name="SharedAgent", status="student", capabilities=[],
            tenant_id="default", workspace_id="default", configuration={},
            enabled=True),
    ])
    seed.add_all([
        AgentExecution(
            id="history-own", agent_id="a1", tenant_id="t1",
            workspace_id="ws1", status="success",
            result_summary="OWN-RESULT"),
        AgentExecution(
            id="history-peer", agent_id="a2", tenant_id="t1",
            workspace_id="ws2", status="success",
            result_summary="PEER-RESULT"),
        AgentExecution(
            id="history-foreign", agent_id="a3", tenant_id="t2",
            workspace_id="ws3", status="success",
            result_summary="FOREIGN-TENANT-RESULT"),
        # Missing execution scope is unknown, not the caller's scope.
        AgentExecution(
            id="history-unbound", agent_id="a1", tenant_id="t1",
            workspace_id=None, status="success",
            result_summary="UNBOUND-RESULT"),
        # Workspace and tenant disagree: fail closed.
        AgentExecution(
            id="history-contradictory", agent_id="a1", tenant_id="t2",
            workspace_id="ws1", status="success",
            result_summary="CONTRADICTORY-RESULT"),
        # Legacy personal-tenant alias on a real workspace row is still the
        # old workspace's legitimate history.
        AgentExecution(
            id="history-legacy-tenant", agent_id="a1", tenant_id="default",
            workspace_id="ws1", status="success",
            result_summary="LEGACY-TENANT-RESULT"),
        # Explicit personal/default scope remains readable by a personal
        # principal, but never by a real-workspace principal.
        AgentExecution(
            id="history-personal", agent_id="a-shared", tenant_id="default",
            workspace_id="default", status="success",
            result_summary="PERSONAL-RESULT"),
        AgentExecution(
            id="history-personal-null", agent_id="a-shared", tenant_id=None,
            workspace_id=None, status="success",
            result_summary="PERSONAL-NULL-RESULT"),
        # Frozen execution scope: the agent now lives in ws2, but this result
        # belongs to ws1 and must not be relabelled into ws2.
        AgentExecution(
            id="history-moved", agent_id="a2", tenant_id="t1",
            workspace_id="ws1", status="success",
            result_summary="MOVED-OLD-RESULT"),
    ])
    seed.commit()
    seed.close()

    def db_override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    def client(actor: User):
        app = FastAPI()
        app.include_router(agent_router)
        app.dependency_overrides[get_db] = db_override
        app.dependency_overrides[get_current_user] = lambda: actor
        return TestClient(app, raise_server_exceptions=False)

    actors = {
        key: Session().query(User).filter(User.id == key).one()
        for key in ("member-1", "member-2", "admin-1", "personal-1")
    }
    yield SimpleNamespace(
        engine=engine, Session=Session, client=client, actors=actors)


def _history(world, actor):
    response = world.client(actor).get("/api/agents/history")
    assert response.status_code == 200, response.text
    return response


def _ids(response):
    return {row["id"] for row in response.json()}


def _set_user(world, user_id, **values):
    db = world.Session()
    try:
        user = db.query(User).filter(User.id == user_id).one()
        for key, value in values.items():
            setattr(user, key, value)
        db.commit()
    finally:
        db.close()


def test_member_history_exposes_only_the_same_workspace(world):
    """Supplied counterexample: ws1 member must not receive ws2 results."""
    response = _history(world, world.actors["member-1"])
    rows = response.json()
    ids = {row["id"] for row in rows}

    assert "history-own" in ids, rows
    assert "history-peer" not in ids, response.text
    assert "history-foreign" not in ids, response.text
    assert "history-unbound" not in ids, response.text
    assert "history-contradictory" not in ids, response.text
    assert "history-personal" not in ids, response.text
    assert "history-personal-null" not in ids, response.text
    # Frozen old workspace row stays readable to the old workspace even
    # though its agent has moved to ws2.
    assert "history-moved" in ids, rows
    assert "history-legacy-tenant" in ids, rows

    rendered = response.text
    for private in (
        "PEER-RESULT", "FOREIGN-TENANT-RESULT", "UNBOUND-RESULT",
        "CONTRADICTORY-RESULT", "PERSONAL-RESULT", "PERSONAL-NULL-RESULT",
    ):
        assert private not in rendered


def test_peer_workspace_reads_peer_history_but_not_old_workspace(world):
    response = _history(world, world.actors["member-2"])
    ids = _ids(response)
    assert "history-peer" in ids
    assert "history-own" not in ids
    assert "history-moved" not in ids


def test_personal_principal_reads_only_explicit_personal_scope(world):
    response = _history(world, world.actors["personal-1"])
    ids = _ids(response)
    assert "history-personal" in ids
    assert "history-personal-null" in ids
    # A tenant-bound row with a missing workspace is still unknown, not the
    # personal caller's row.
    assert "history-unbound" not in ids
    assert "history-own" not in ids
    assert "history-peer" not in ids
    assert "history-foreign" not in ids
    assert "history-contradictory" not in ids
    assert "history-legacy-tenant" not in ids


def test_admin_current_workspace_is_a_normal_positive(world):
    response = _history(world, world.actors["admin-1"])
    ids = _ids(response)
    assert "history-own" in ids
    assert "history-peer" not in ids
    assert "history-foreign" not in ids
    assert "history-legacy-tenant" in ids


def test_stale_actor_is_reloaded_from_the_authoritative_database(world):
    stale = world.actors["member-1"]
    _set_user(world, "member-1", workspace_id="ws2")

    response = _history(world, stale)
    ids = _ids(response)
    assert "history-peer" in ids
    assert "history-own" not in ids


def test_deactivated_stale_principal_is_refused(world):
    stale = world.actors["member-1"]
    _set_user(world, "member-1", status="suspended", is_active=False)

    response = world.client(stale).get("/api/agents/history")
    assert response.status_code == 403, response.text


def test_agent_list_detail_status_and_graduation_are_workspace_scoped(world):
    member = world.client(world.actors["member-1"])

    listing = member.get("/api/agents/")
    assert listing.status_code == 200, listing.text
    listed = {row["id"] for row in listing.json()["data"]}
    assert "a1" in listed
    assert "a-shared" in listed
    assert "a2" not in listed
    assert "a3" not in listed

    own = member.get("/api/agents/a1")
    assert own.status_code == 200, own.text
    assert "Workspace One Agent" in own.text

    for suffix in ("", "/status", "/graduation-progress"):
        peer = member.get(f"/api/agents/a2{suffix}")
        assert peer.status_code == 404, (suffix, peer.text)
        foreign = member.get(f"/api/agents/a3{suffix}")
        assert foreign.status_code == 404, (suffix, foreign.text)

    shared = member.get("/api/agents/a-shared/status")
    assert shared.status_code == 200, shared.text


def test_history_readback_does_not_change_durable_rows(world):
    db = world.Session()
    try:
        before = db.query(AgentExecution).order_by(
            AgentExecution.id).all()
        before_state = [
            (row.id, row.status, row.result_summary) for row in before]
    finally:
        db.close()

    _history(world, world.actors["member-1"])
    _history(world, world.actors["member-2"])

    db = world.Session()
    try:
        after = db.query(AgentExecution).order_by(
            AgentExecution.id).all()
        after_state = [
            (row.id, row.status, row.result_summary) for row in after]
    finally:
        db.close()
    assert after_state == before_state


def test_unavailable_history_store_is_not_a_successful_empty_list(world):
    with world.engine.begin() as connection:
        connection.execute(text("DROP TABLE agent_executions"))

    response = world.client(world.actors["member-1"]).get(
        "/api/agents/history")
    assert response.status_code == 503, response.text
    body = response.json()
    payload = body.get("detail") or body
    assert payload.get("success") is False
    assert payload["error"]["code"] == "AGENT_HISTORY_UNAVAILABLE"
    assert "Traceback" not in response.text
