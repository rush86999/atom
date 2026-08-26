"""R89 RED tests — canvas logic read/run ownership + non-bypassable gate.

Findings:
1. GET /{canvas_id}/logic and POST /{canvas_id}/logic/run had NO ownership
   check (PUT does): any authenticated user could read another user's logic
   source and execute it with attacker-chosen inputs.
2. The AUTONOMOUS governance gate keyed off an OPTIONAL client-supplied
   agent_id — omitting it silently skipped check_governance entirely, so a
   plain human JWT executed server-side Python in the sandbox runtime
   without any maturity check, violating the documented AUTONOMOUS contract.
"""
import asyncio
import os
import tempfile
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import AgentRegistry, AgentStatus, Canvas, User, UserRole, UserStatus


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


def _user(uid, role):
    return User(id=uid, email=f"{uid}@t.local", first_name="A", last_name="B",
                hashed_password="x", role=role, status=UserStatus.ACTIVE.value)


@pytest.fixture
def seeded(db):
    owner = _user("u-owner", UserRole.MEMBER.value)
    stranger = _user("u-stranger", UserRole.MEMBER.value)
    db.add_all([owner, stranger])
    canvas = Canvas(
        id="canvas-1",
        tenant_id="tenant-1",
        name="Private board",
        created_by="u-owner",
        is_collaborative=False,
    )
    autonomous_agent = AgentRegistry(
        id="agent-auto", name="Auto", category="ops",
        status=AgentStatus.AUTONOMOUS.value, capabilities=[],
        module_path="core.generic_agent", class_name="GenericAgent",
    )
    student_agent = AgentRegistry(
        id="agent-stu", name="Stu", category="ops",
        status=AgentStatus.STUDENT.value, capabilities=[],
        module_path="core.generic_agent", class_name="GenericAgent",
    )
    db.add_all([canvas, autonomous_agent, student_agent])

    # Saved logic row so GET/run have something to find.
    from core.models import CanvasLogic

    db.add(CanvasLogic(
        canvas_id="canvas-1",
        source="print(inputs.get('secret'))",
        language="python",
        created_by="u-owner",
    ))
    db.commit()
    return {"canvas": canvas}


@pytest.fixture
def client(db, seeded):
    from api.canvas_routes import router
    from core.auth import get_current_user as cu
    from core.database import get_db as core_get_db

    current = {"id": "u-owner"}

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


# --- ownership ---------------------------------------------------------------

def test_stranger_cannot_read_logic_source(client):
    client.atom_current["id"] = "u-stranger"
    _auth(client)
    resp = client.get("/api/canvas/canvas-1/logic")
    assert resp.status_code in (403, 404), (
        f"stranger read logic source: {resp.status_code} {resp.text}"
    )
    assert "print(inputs" not in (resp.text or "")


def test_stranger_cannot_run_logic(client):
    client.atom_current["id"] = "u-stranger"
    _auth(client)

    async def _fake_run(*a, **k):
        return {"success": True}

    with patch("core.canvas_logic_service.CanvasLogicService.run", new=_fake_run):
        resp = client.post(
            "/api/canvas/canvas-1/logic/run",
            json={"inputs": {}, "agent_id": "agent-auto"},
        )
    assert resp.status_code in (403, 404), (
        f"stranger ran someone else's canvas logic: {resp.status_code}"
    )


def test_owner_can_read_and_run(client):
    client.atom_current["id"] = "u-owner"
    _auth(client)

    got = client.get("/api/canvas/canvas-1/logic")
    assert got.status_code == 200, got.text

    async def _fake_run(*a, **k):
        return {"success": True}

    with patch("core.canvas_logic_service.CanvasLogicService.run", new=_fake_run):
        ran = client.post(
            "/api/canvas/canvas-1/logic/run",
            json={"inputs": {}, "agent_id": "agent-auto"},
        )
    assert ran.status_code == 200, ran.text


# --- mandatory governance ----------------------------------------------------

def test_run_without_agent_id_is_rejected_not_silent(client):
    """Omitting agent_id must NOT bypass the AUTONOMOUS gate."""
    client.atom_current["id"] = "u-owner"
    _auth(client)

    ran_calls = []

    async def _spy_run(self, *a, **k):
        ran_calls.append(k)
        return {"success": True}

    with patch(
        "core.canvas_logic_service.CanvasLogicService.run", new=_spy_run
    ):
        resp = client.post(
            "/api/canvas/canvas-1/logic/run",
            json={"inputs": {}},
        )
    assert resp.status_code == 403, (
        f"agentless run skipped governance: {resp.status_code} {resp.text}"
    )
    assert ran_calls == [], "run() executed despite missing agent context"


def test_save_without_agent_id_is_rejected(client):
    client.atom_current["id"] = "u-owner"
    _auth(client)
    resp = client.put(
        "/api/canvas/canvas-1/logic",
        json={"source": "x = 1", "language": "python"},
    )
    assert resp.status_code == 403, resp.text


def test_student_agent_cannot_run_canvas_logic(client):
    client.atom_current["id"] = "u-owner"
    _auth(client)
    resp = client.post(
        "/api/canvas/canvas-1/logic/run",
        json={"inputs": {}, "agent_id": "agent-stu"},
    )
    assert resp.status_code == 403, resp.text


def test_autonomous_agent_run_passes_gate_and_scopes(client):
    client.atom_current["id"] = "u-owner"
    _auth(client)

    captured = {}

    async def _fake_run(self, canvas_id, inputs=None, agent_id=None, scopes=None):
        captured["agent_id"] = agent_id
        return {"success": True}

    with patch(
        "core.canvas_logic_service.CanvasLogicService.run", new=_fake_run
    ):
        resp = client.post(
            "/api/canvas/canvas-1/logic/run",
            json={"inputs": {}, "agent_id": "agent-auto"},
        )
    assert resp.status_code == 200, resp.text
    assert captured["agent_id"] == "agent-auto"
