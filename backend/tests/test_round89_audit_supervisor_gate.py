"""R89 RED tests — audit trail API must not expose other users' agent runs.

Original finding: every /api/audit/* endpoint required only get_current_user,
so any member JWT could enumerate the entire org's AI decision history
(tool arguments, prompt excerpts, model/provider per LLM call).

F1 keeps that security intent under an owner-scoped read: a member may inspect
their OWN audited work, supervisors get the CURRENT workspace (never a global
all-users query), and another user's rows/prompt excerpt never appear. These
tests therefore assert scope rather than a blanket 403.
"""
import os
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import AuditLog, User, UserRole, UserStatus


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
def client(db):
    from api.audit_routes import router
    from core.auth import get_current_user as cu
    from core.database import get_db as core_get_db

    db.add_all([
        User(id="u-member", email="m@test.local", first_name="M", last_name="B",
             hashed_password="x", role=UserRole.MEMBER.value,
             status=UserStatus.ACTIVE.value),
        User(id="u-lead", email="l@test.local", first_name="L", last_name="B",
             hashed_password="x", role=UserRole.TEAM_LEAD.value,
             status=UserStatus.ACTIVE.value),
        AuditLog(
            id="ev-1", event_type="agent_action", security_level="medium",
            threat_level="low", action="tool_call", user_id="someone-else",
            description="agent tool invocation",
            resource="agent-x",
            metadata_json='{"prompt_excerpt":"CONFIDENTIAL-PROMPT","tool_args":{"q":"payroll"}}',
            success=True,
        ),
        # Owned work is readable to the member under the owner-scoped read
        # (F1); the foreign row above must never join it.
        AuditLog(
            id="ev-own", event_type="agent_action", security_level="low",
            threat_level="none", action="execution_start", user_id="u-member",
            workspace_id="default", description="own run start",
            resource="agent-own",
            metadata_json='{"agent_execution_id":"own-exec","task_input":"my task"}',
            success=True,
        ),
    ])
    db.commit()

    current = {"id": "u-member"}

    app = FastAPI()
    app.include_router(router)

    def _over_db():
        yield db

    def _over_user():
        return db.query(User).filter(User.id == current["id"]).first()

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


def test_member_cannot_read_org_wide_event_feed(client):
    """R89's security intent is preserved under F1 owner scope.

    The member may read their own audited work, but the org-wide feed —
    including another user's prompt excerpt and tool arguments — must not
    appear. The scope marker tells the UI this is an own-scope read.
    """
    _auth(client)
    resp = client.get("/api/audit/events")
    assert resp.status_code == 200, (
        f"member own-work read failed: {resp.status_code} {resp.text}"
    )
    body = resp.json()
    ids = {item.get("id") for item in body.get("items", [])}
    assert "ev-own" in ids
    assert "ev-1" not in ids
    assert "CONFIDENTIAL-PROMPT" not in (resp.text or "")
    assert body.get("read_scope", {}).get("kind") == "owner"


@pytest.mark.parametrize("path,expected", [
    ("/api/audit/executions", 200),
    ("/api/audit/executions/some-exec", 404),
    ("/api/audit/summary", 200),
])
def test_member_audit_surfaces_are_owner_scoped(client, path, expected):
    _auth(client)
    resp = client.get(path)
    assert resp.status_code == expected, resp.text
    assert "CONFIDENTIAL-PROMPT" not in (resp.text or "")
    if path == "/api/audit/executions":
        items = resp.json().get("items", [])
        assert [item["execution_id"] for item in items] == ["own-exec"]
    if path == "/api/audit/summary":
        body = resp.json()
        assert body["total_events"] == 1
        assert body["read_scope"]["kind"] == "owner"


def test_supervisor_can_review(client):
    client.atom_current["id"] = "u-lead"
    _auth(client)
    resp = client.get("/api/audit/events")
    assert resp.status_code == 200, resp.text
    items = resp.json().get("items", [])
    assert any(i.get("id") == "ev-1" for i in items)
    assert resp.json()["read_scope"]["kind"] == "workspace"
