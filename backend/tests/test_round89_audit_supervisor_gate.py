"""R89 RED tests — audit trail API must be supervisor-gated.

Finding: every /api/audit/* endpoint requires only get_current_user. The
serialized events carry full metadata (tool arguments, prompt excerpts,
model/provider per LLM call) for ALL users' agent runs — any member JWT
could enumerate the entire org's AI decision history. This is an
accountant/reviewer surface: gate it to TEAM_LEAD+ like the other
supervision surfaces.
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


def test_member_cannot_read_event_feed(client):
    _auth(client)
    resp = client.get("/api/audit/events")
    assert resp.status_code == 403, (
        f"member reads org-wide audit feed: {resp.status_code} {resp.text}"
    )
    assert "CONFIDENTIAL-PROMPT" not in (resp.text or "")


@pytest.mark.parametrize("path", [
    "/api/audit/executions",
    "/api/audit/executions/some-exec",
    "/api/audit/summary",
])
def test_member_blocked_on_all_audit_surfaces(client, path):
    _auth(client)
    assert client.get(path).status_code == 403


def test_supervisor_can_review(client):
    client.atom_current["id"] = "u-lead"
    _auth(client)
    resp = client.get("/api/audit/events")
    assert resp.status_code == 200, resp.text
    items = resp.json().get("items", [])
    assert any(i.get("id") == "ev-1" for i in items)
