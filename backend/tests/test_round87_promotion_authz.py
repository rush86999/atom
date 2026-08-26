"""R87 RED tests — graduation/promote must be supervisor-gated.

Finding: POST /api/episodes/graduation/promote only required
get_current_user — any authenticated member could promote ANY agent to ANY
maturity (e.g. AUTONOMOUS), bypassing the maturity system entirely
(AgentGraduationService.promote_agent performs no role check either).
Contrast: agent_maturity_routes.py gates its mutations behind
_require_supervisor (TEAM_LEAD+). The graduation surface must match.
"""
import os
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import AgentRegistry, AgentStatus, User, UserRole


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
def users(db):
    member = User(
        id="u-member",
        email="member@test.local",
        first_name="Mem",
        last_name="Ber",
        hashed_password="x",
        role=UserRole.MEMBER.value,
        status="active",
    )
    lead = User(
        id="u-lead",
        email="lead@test.local",
        first_name="Lead",
        last_name="Er",
        hashed_password="x",
        role=UserRole.TEAM_LEAD.value,
        status="active",
    )
    db.add_all([member, lead])
    db.commit()
    return {"member": member, "lead": lead}


@pytest.fixture
def agent(db):
    row = AgentRegistry(
        id="agent-1",
        name="Student Bot",
        category="sales",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.4,
        capabilities=[],
        module_path="core.generic_agent",
        class_name="GenericAgent",
    )
    db.add(row)
    db.commit()
    return row


@pytest.fixture
def client(db, users, agent):
    from core.database import get_db as core_get_db
    from core.security_dependencies import get_current_user as sd_user
    from core.auth import get_current_user as auth_user

    from api.episode_routes import router

    app = FastAPI()
    app.include_router(router)

    def _over_db():
        yield db

    app.dependency_overrides[core_get_db] = _over_db

    current = {"id": users["member"].id}

    def _over_user():
        from core.models import User as U

        return db.query(U).filter(U.id == current["id"]).first()

    app.dependency_overrides[sd_user] = _over_user
    app.dependency_overrides[auth_user] = _over_user

    client = TestClient(app)
    client.atom_current = current
    yield client


def test_member_cannot_promote_any_agent(client, db, agent):
    """A plain member JWT must NOT be able to hand out maturity levels."""
    client.atom_current["id"] = "u-member"
    resp = client.post(
        "/api/episodes/graduation/promote",
        params={"agent_id": "agent-1", "new_maturity": "AUTONOMOUS"},
    )
    assert resp.status_code == 403, resp.text
    db.expire_all()
    assert (
        db.query(AgentRegistry).filter_by(id="agent-1").first().status
        == AgentStatus.STUDENT.value
    )


def test_supervisor_can_promote(client, db, agent):
    """TEAM_LEAD+ keeps the ability to promote (legitimate flow intact)."""
    client.atom_current["id"] = "u-lead"
    resp = client.post(
        "/api/episodes/graduation/promote",
        params={"agent_id": "agent-1", "new_maturity": "INTERN"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["promoted"] is True
    db.expire_all()
    assert (
        db.query(AgentRegistry).filter_by(id="agent-1").first().status
        == AgentStatus.INTERN.value
    )


def test_member_cannot_run_lifecycle_maintenance(client, db):
    """Decay/consolidate are fleet-wide maintenance ops — not member tools."""
    for path, params in (
        ("/api/episodes/lifecycle/decay", {}),
        ("/api/episodes/lifecycle/consolidate", {"agent_id": "agent-1"}),
    ):
        client.atom_current["id"] = "u-member"
        resp = client.post(path, params=params)
        assert resp.status_code == 403, f"{path}: {resp.status_code} {resp.text}"
