"""R89 RED tests — workflow execution status/results are cross-tenant readable.

Finding: GET /api/workflow-templates/executions/{id}/status and /results match
on execution_id OR workflow_id with NO ownership/tenant filter, returning
another user's run status, error text, step history, and output payloads
(the orchestrator-persisted context blob). WorkflowExecution has user_id /
owner_id / tenant_id / visibility columns; the readers use none of them, and
execute_template never stamps the caller's identity into the run.
"""
import os
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import User, UserRole, UserStatus, WorkflowExecution


@pytest.fixture
def db():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    for table in Base.metadata.sorted_tables:
        try:
            table.create(engine, checkfirst=True)
        except exc.NoReferencedTableError:
            continue
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def seeded(db):
    alice = User(
        id="user-alice", email="a@test.local", first_name="A", last_name="B",
        hashed_password="x", role=UserRole.MEMBER.value,
        status=UserStatus.ACTIVE.value, tenant_id="tenant-1",
    )
    bob = User(
        id="user-bob", email="b@test.local", first_name="B", last_name="C",
        hashed_password="x", role=UserRole.MEMBER.value,
        status=UserStatus.ACTIVE.value, tenant_id="tenant-2",
    )
    db.add_all([alice, bob])

    ctx = '{"results":{"crm_export":"SECRET-PIPELINE-DATA"},"execution_history":[{"step_id":"s1"}]}'
    rows = [
        # Alice's run — Bob must NOT see it.
        WorkflowExecution(
            execution_id="exec-alice-1", workflow_id="wf-alice",
            status="COMPLETED", context=ctx,
            user_id="user-alice", owner_id="user-alice", tenant_id="tenant-1",
        ),
        # Legacy unattributed row (NULL user/owner/tenant): grandfathered.
        WorkflowExecution(
            execution_id="exec-legacy", workflow_id="wf-legacy",
            status="COMPLETED", context=ctx,
        ),
        # Tenant-scoped but pre-user-stamp row of tenant-1: visible to
        # tenant-1 members, NOT to tenant-2 Bob.
        WorkflowExecution(
            execution_id="exec-t1-nouser", workflow_id="wf-t1",
            status="COMPLETED", context=ctx, tenant_id="tenant-1",
        ),
    ]
    db.add_all(rows)
    db.commit()
    return {"alice": alice, "bob": bob}


@pytest.fixture
def client(db, seeded):
    from api.workflow_template_routes import router
    from core.database import get_db as core_get_db

    current = {"id": "user-bob"}

    app = FastAPI()
    app.include_router(router)

    def _over_db():
        yield db

    def _over_user():
        return db.query(User).filter(User.id == current["id"]).first()

    from core.auth import get_current_user as cu
    app.dependency_overrides[core_get_db] = _over_db
    app.dependency_overrides[cu] = _over_user

    c = TestClient(app)
    c.atom_current = current
    yield c


def _auth(client):
    import core.auth as ca

    client.headers["Authorization"] = (
        "Bearer " + ca.create_access_token({"sub": client.atom_current["id"]})
    )


def test_bob_cannot_read_alices_execution_status(client, db):
    _auth(client)
    resp = client.get("/api/workflow-templates/executions/exec-alice-1/status")
    assert resp.status_code == 404, (
        f"cross-user execution readable: {resp.status_code} {resp.text}"
    )


def test_bob_cannot_read_alices_execution_results(client, db):
    _auth(client)
    for ident in ("exec-alice-1", "wf-alice"):
        resp = client.get(f"/api/workflow-templates/executions/{ident}/results")
        assert resp.status_code == 404, f"{ident}: {resp.status_code}"
    assert "SECRET-PIPELINE-DATA" not in (
        client.get("/api/workflow-templates/executions/wf-alice/results").text or ""
    )


def test_bob_cannot_read_other_tenants_unstamped_rows(client, db):
    _auth(client)
    resp = client.get("/api/workflow-templates/executions/exec-t1-nouser/status")
    assert resp.status_code == 404, resp.text


def test_owner_still_reads_own_run(client, db):
    client.atom_current["id"] = "user-alice"
    _auth(client)
    resp = client.get("/api/workflow-templates/executions/exec-alice-1/status")
    assert resp.status_code == 200, resp.text
    assert resp.json()["execution_id"] == "exec-alice-1"

    results = client.get("/api/workflow-templates/executions/exec-alice-1/results")
    assert results.status_code == 200
    assert "SECRET-PIPELINE-DATA" in results.text


def test_legacy_unattributed_row_grandfathered(client, db):
    """Pre-R89 identity-less rows: tenant-scoped ones stay in-tenant;
    fully anonymous rows belong to no one — not to everyone."""
    client.atom_current["id"] = "user-alice"
    _auth(client)
    # Tenant-stamped unstamped-user row of her own tenant: readable.
    assert client.get(
        "/api/workflow-templates/executions/exec-t1-nouser/status"
    ).status_code == 200

    db.add(WorkflowExecution(
        execution_id="exec-anon", workflow_id="wf-anon",
        status="COMPLETED",
    ))
    db.commit()

    # Alice carries a tenant → fully anonymous row is not hers to read.
    resp = client.get("/api/workflow-templates/executions/exec-anon/status")
    assert resp.status_code == 404, resp.text

    client.atom_current["id"] = "user-bob"
    _auth(client)
    assert client.get(
        "/api/workflow-templates/executions/exec-t1-nouser/status"
    ).status_code == 404


def test_execute_template_stamps_caller_identity(client, db, monkeypatch):
    """New runs carry the caller's user_id so future reads scope correctly."""
    captured = {}

    class _FakeOrch:
        async def execute_workflow(self, workflow_id, input_data=None, execution_context=None):
            captured["execution_context"] = execution_context
            captured["workflow_id"] = workflow_id
            status_value = "COMPLETED"

            class _S:
                workflow_id = captured["workflow_id"]
                status = type("S", (), {"value": status_value})()

            return _S()

    import asyncio

    import api.workflow_template_routes as wtr

    class _FakeManager:
        def create_workflow_from_template(self, *a, **k):
            return {
                "workflow_id": "wf-new",
                "workflow_definition": {},
                "workflow_name": "x",
            }

    async def _noop(*a, **k):
        return None

    monkeypatch.setattr(wtr, "get_template_manager", lambda: _FakeManager())
    monkeypatch.setattr(
        "advanced_workflow_orchestrator.get_orchestrator", lambda: _FakeOrch()
    )
    monkeypatch.setattr(wtr, "require_workflow_executor_definition", _noop)

    alice = db.query(User).filter(User.id == "user-alice").first()
    # Call the undecorated handler: this test targets the identity stamping,
    # not the governance decorator / orchestrator wiring.
    result = asyncio.run(
        wtr.execute_template.__wrapped__(
            template_id="tpl-1",
            parameters={},
            request=None,
            current_user=alice,
            db=db,
            agent_id=None,
        )
    )
    assert result["status"] == "success"
    assert captured["execution_context"]["user_id"] == "user-alice"
    assert captured["execution_context"]["tenant_id"] == "tenant-1"
