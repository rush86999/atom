"""Real-SQL/JWT authority controls for training proposal list/detail/review."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

import core.models  # noqa: F401
from api.agent_maturity_routes import router
from core.auth import create_access_token
from core.database import Base, get_db
from core.models import (
    AgentProposal,
    AgentRegistry,
    ProposalStatus,
    ProposalType,
    Tenant,
    TrainingSession,
    User,
    UserStatus,
    Workspace,
)
from core.student_training_service import (
    StudentTrainingService,
    TrainingAuthorityError,
    TrainingProposalNotFound,
)


def _proposal(db, proposal_id, agent_id, tenant_id, user_id, status=ProposalStatus.PENDING_APPROVAL.value, proposal_type=ProposalType.WORKFLOW.value, expires_at=None):
    row = AgentProposal(
        id=proposal_id,
        tenant_id=tenant_id,
        user_id=user_id,
        agent_id=agent_id,
        agent_name=f"Agent {agent_id}",
        proposal_type=proposal_type,
        title=f"Proposal {proposal_id}",
        description="synthetic",
        proposal_data={
            "capability_gaps": ["gap"],
            "learning_objectives": ["objective"],
            "estimated_duration_hours": 4,
        },
        status=status,
        expires_at=expires_at,
    )
    db.add(row)
    return row


@pytest.fixture()
def env(tmp_path):
    assert os.environ.get("TESTING") == "1"
    db_path = tmp_path / "training_authority.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
        poolclass=NullPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    for scope in ("a", "b"):
        db.add(Tenant(id=scope, name=scope, subdomain=f"training-{scope}", edition="personal", is_active=True))
        db.add(Workspace(id=f"ws-{scope}", name=scope, tenant_id=scope, status="active"))
    db.add(Tenant(id="default", name="Default", subdomain="training-default", edition="personal", is_active=True))
    db.add(Workspace(id="default", name="Default", tenant_id="default", status="active"))
    db.commit()

    def user(user_id, role, tenant_id, workspace_id, status=UserStatus.ACTIVE.value, active=True):
        row = User(
            id=user_id, email=f"{user_id}@example.invalid", hashed_password="h",
            first_name="Training", last_name=user_id, role=role, status=status,
            is_active=active, tenant_id=tenant_id, workspace_id=workspace_id,
        )
        db.add(row)
        return row

    user("lead-a", "team_lead", "a", "ws-a")
    user("member-a", "member", "a", "ws-a")
    user("lead-b", "team_lead", "b", "ws-b")
    user("lead-default", "team_lead", "default", "default")
    inactive = user("inactive-a", "team_lead", "a", "ws-a")
    db.commit()

    def agent(agent_id, tenant_id, workspace_id, owner="lead-a"):
        row = AgentRegistry(
            id=agent_id, name=f"Agent {agent_id}", category="operations",
            module_path="core.generic_agent", class_name="GenericAgent",
            status="student", tenant_id=tenant_id, workspace_id=workspace_id,
            user_id=owner,
        )
        db.add(row)
        return row

    agent("agent-a", "a", "ws-a")
    agent("agent-b", "b", "ws-b", owner="lead-b")
    agent("agent-null", None, None, owner="lead-default")
    agent("agent-contradict", "a", "ws-a")
    agent("agent-null-foreign", None, None, owner="lead-b")
    db.commit()

    _proposal(db, "proposal-a", "agent-a", "a", "lead-b")
    _proposal(db, "proposal-b", "agent-b", "b", "lead-b")
    _proposal(db, "proposal-null", "agent-null", "default", "lead-default")
    _proposal(db, "proposal-contradict", "agent-contradict", "b", "lead-a")
    _proposal(db, "proposal-null-foreign", "agent-null-foreign", "b", "lead-b")
    _proposal(db, "proposal-expired", "agent-a", "a", "lead-a",
              expires_at=datetime.now(timezone.utc) - timedelta(days=1))
    _proposal(db, "proposal-action", "agent-a", "a", "lead-a", proposal_type=ProposalType.ACTION.value)
    _proposal(db, "proposal-terminal", "agent-a", "a", "lead-a", status=ProposalStatus.REJECTED.value)
    db.commit()

    tokens = {}
    for uid in ("lead-a", "member-a", "lead-b", "lead-default", "inactive-a"):
        row = db.get(User, uid)
        tokens[uid] = create_access_token(data={"sub": uid}, user=row)
    inactive.status = UserStatus.SUSPENDED.value
    inactive.is_active = False
    db.commit()

    app = FastAPI()

    def _get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.include_router(router)
    app.dependency_overrides[get_db] = _get_db
    client = TestClient(app, base_url="http://testserver")

    def headers(uid):
        return {"Authorization": f"Bearer {tokens[uid]}"}

    yield SimpleNamespace(
        db=db, Session=Session, engine=engine, client=client, headers=headers,
        path=str(db_path), tokens=tokens,
    )

    client.close()
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _count(env, proposal_id):
    return env.db.query(TrainingSession).filter(TrainingSession.proposal_id == proposal_id).count()


def test_member_same_scope_reads_but_cannot_review(env):
    member = env.headers("member-a")
    listing = env.client.get("/api/maturity/training/proposals", headers=member)
    assert listing.status_code == 200, listing.text
    assert {p["id"] for p in listing.json()["proposals"]} >= {"proposal-a"}
    detail = env.client.get("/api/maturity/training/proposals/proposal-a", headers=member)
    assert detail.status_code == 200, detail.text
    reject = env.client.post(
        "/api/maturity/training/proposals/proposal-a/reject",
        json={"reason": "member attempt"}, headers=member)
    assert reject.status_code == 403, reject.text
    approve = env.client.post(
        "/api/maturity/training/proposals/proposal-a/approve",
        json={"approve": True}, headers=member)
    assert approve.status_code == 403, approve.text
    env.db.expire_all()
    assert env.db.get(AgentProposal, "proposal-a").status == ProposalStatus.PENDING_APPROVAL.value
    assert _count(env, "proposal-a") == 0


def test_supervisor_scope_list_detail_and_foreign_review_refusal(env):
    lead_a = env.headers("lead-a")
    listing = env.client.get("/api/maturity/training/proposals", headers=lead_a)
    ids = {p["id"] for p in listing.json()["proposals"]}
    assert "proposal-a" in ids
    assert "proposal-b" not in ids
    assert "proposal-contradict" not in ids
    assert env.client.get("/api/maturity/training/proposals/proposal-b", headers=lead_a).status_code == 404
    reject = env.client.post(
        "/api/maturity/training/proposals/proposal-b/reject",
        json={"reason": "foreign"}, headers=lead_a)
    assert reject.status_code == 404, reject.text
    approve = env.client.post(
        "/api/maturity/training/proposals/proposal-b/approve",
        json={"approve": True}, headers=lead_a)
    assert approve.status_code == 404, approve.text
    env.db.expire_all()
    assert env.db.get(AgentProposal, "proposal-b").status == ProposalStatus.PENDING_APPROVAL.value
    assert _count(env, "proposal-b") == 0


def test_contradictory_proposal_agent_tenant_is_absent(env):
    lead_a = env.headers("lead-a")
    listing = env.client.get("/api/maturity/training/proposals", headers=lead_a)
    assert "proposal-contradict" not in {p["id"] for p in listing.json()["proposals"]}
    assert env.client.get("/api/maturity/training/proposals/proposal-contradict", headers=lead_a).status_code == 404


def test_legacy_null_agent_scope_remains_readable(env):
    lead = env.headers("lead-default")
    listing = env.client.get("/api/maturity/training/proposals", headers=lead)
    assert "proposal-null" in {p["id"] for p in listing.json()["proposals"]}
    assert env.client.get("/api/maturity/training/proposals/proposal-null", headers=lead).status_code == 200


def test_inactive_demoted_and_moved_actor_refuse_zero_effect(env):
    # inactive token is rejected by current auth
    assert env.client.get(
        "/api/maturity/training/proposals", headers=env.headers("inactive-a")
    ).status_code in (401, 403)

    # demoted current actor loses the decision gate
    actor = env.db.get(User, "lead-a")
    actor.role = "member"
    env.db.commit()
    rejected = env.client.post(
        "/api/maturity/training/proposals/proposal-a/reject",
        json={"reason": "demoted"}, headers=env.headers("lead-a"))
    assert rejected.status_code == 403, rejected.text
    env.db.expire_all()
    assert env.db.get(AgentProposal, "proposal-a").status == ProposalStatus.PENDING_APPROVAL.value

    # moved workspace is outside the authoritative agent scope
    actor = env.db.get(User, "lead-a")
    actor.role = "team_lead"
    actor.workspace_id = "ws-b"
    env.db.commit()
    assert env.client.get(
        "/api/maturity/training/proposals/proposal-a", headers=env.headers("lead-a")
    ).status_code == 404
    assert _count(env, "proposal-a") == 0


def test_approve_creates_one_session_and_duplicate_conflicts(env):
    lead = env.headers("lead-a")
    first = env.client.post(
        "/api/maturity/training/proposals/proposal-a/approve",
        json={"approve": True}, headers=lead)
    assert first.status_code == 200, first.text
    session_id = first.json()["session_id"]
    second = env.client.post(
        "/api/maturity/training/proposals/proposal-a/approve",
        json={"approve": True}, headers=lead)
    assert second.status_code == 409, second.text
    env.db.expire_all()
    proposal = env.db.get(AgentProposal, "proposal-a")
    session = env.db.get(TrainingSession, session_id)
    assert proposal.status == ProposalStatus.APPROVED.value
    assert proposal.approved_by == "lead-a"
    assert session.supervisor_id == "lead-a"
    assert _count(env, "proposal-a") == 1


def test_approve_false_rejects_without_session_and_duplicate_conflicts(env):
    lead = env.headers("lead-a")
    first = env.client.post(
        "/api/maturity/training/proposals/proposal-a/approve",
        json={"approve": False}, headers=lead)
    assert first.status_code == 200, first.text
    second = env.client.post(
        "/api/maturity/training/proposals/proposal-a/approve",
        json={"approve": False}, headers=lead)
    assert second.status_code == 409, second.text
    env.db.expire_all()
    proposal = env.db.get(AgentProposal, "proposal-a")
    assert proposal.status == ProposalStatus.REJECTED.value
    assert proposal.approver_id == "lead-a"
    assert _count(env, "proposal-a") == 0


def test_terminal_and_wrong_type_cannot_start_session(env):
    lead = env.headers("lead-a")
    terminal = env.client.post(
        "/api/maturity/training/proposals/proposal-terminal/approve",
        json={"approve": True}, headers=lead)
    assert terminal.status_code == 409, terminal.text
    wrong = env.client.post(
        "/api/maturity/training/proposals/proposal-action/approve",
        json={"approve": True}, headers=lead)
    assert wrong.status_code == 404, wrong.text
    assert _count(env, "proposal-terminal") == 0
    assert _count(env, "proposal-action") == 0


def test_direct_service_consumers_enforce_scope_and_role(env):
    service = StudentTrainingService(env.db)
    with pytest.raises(TrainingProposalNotFound):
        service.reject_training("proposal-b", "lead-a", reason="direct foreign")
    with pytest.raises(TrainingProposalNotFound):
        import asyncio
        asyncio.run(service.approve_training("proposal-b", "lead-a"))
    with pytest.raises(TrainingAuthorityError):
        service.reject_training("proposal-a", "member-a", reason="direct member")
    assert _count(env, "proposal-b") == 0
    assert env.db.get(AgentProposal, "proposal-b").status == ProposalStatus.PENDING_APPROVAL.value


def test_competing_proposal_material_is_refused_zero_effect(env):
    fired = {"done": False}

    def _change_material(conn, cursor, statement, parameters, context, executemany):
        if fired["done"] or not statement.lower().lstrip().startswith("update users"):
            return
        fired["done"] = True
        peer = env.Session()
        try:
            row = peer.get(AgentProposal, "proposal-a")
            row.proposal_data = {**row.proposal_data, "competing": True}
            peer.commit()
        finally:
            peer.close()

    event.listen(env.engine, "before_cursor_execute", _change_material)
    try:
        response = env.client.post(
            "/api/maturity/training/proposals/proposal-a/approve",
            json={"approve": True}, headers=env.headers("lead-a"))
    finally:
        event.remove(env.engine, "before_cursor_execute", _change_material)
    assert fired["done"] is True
    assert response.status_code == 409, response.text
    env.db.expire_all()
    assert env.db.get(AgentProposal, "proposal-a").status == ProposalStatus.PENDING_APPROVAL.value
    assert _count(env, "proposal-a") == 0


def test_moved_agent_target_is_refused_zero_effect(env):
    fired = {"done": False}

    def _move_agent(conn, cursor, statement, parameters, context, executemany):
        if fired["done"] or not statement.lower().lstrip().startswith("update users"):
            return
        fired["done"] = True
        peer = env.Session()
        try:
            row = peer.get(AgentRegistry, "agent-a")
            row.workspace_id = "ws-b"
            peer.commit()
        finally:
            peer.close()

    event.listen(env.engine, "before_cursor_execute", _move_agent)
    try:
        response = env.client.post(
            "/api/maturity/training/proposals/proposal-a/approve",
            json={"approve": True}, headers=env.headers("lead-a"))
    finally:
        event.remove(env.engine, "before_cursor_execute", _move_agent)
    assert fired["done"] is True
    assert response.status_code == 409, response.text
    env.db.expire_all()
    assert env.db.get(AgentProposal, "proposal-a").status == ProposalStatus.PENDING_APPROVAL.value
    assert _count(env, "proposal-a") == 0


_CHILD = """
import json, sqlite3, sys
c=sqlite3.connect(sys.argv[1])
p=c.execute('select status, approved_by from agent_proposals where id=?',(sys.argv[2],)).fetchone()
s=c.execute('select count(*), max(supervisor_id) from training_sessions where proposal_id=?',(sys.argv[2],)).fetchone()
print(json.dumps({'status':p[0],'reviewer':p[1],'sessions':s[0],'supervisor':s[1]}))
"""


def test_fresh_child_process_readback_exact_decision(env):
    response = env.client.post(
        "/api/maturity/training/proposals/proposal-a/approve",
        json={"approve": True}, headers=env.headers("lead-a"))
    assert response.status_code == 200, response.text
    completed = subprocess.run(
        [sys.executable, "-c", _CHILD, env.path, "proposal-a"],
        capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout.strip().splitlines()[-1])
    assert summary == {
        "status": ProposalStatus.APPROVED.value,
        "reviewer": "lead-a",
        "sessions": 1,
        "supervisor": "lead-a",
    }


def test_null_agent_does_not_hide_foreign_proposal_tenant(env):
    default_lead = env.headers("lead-default")
    listing = env.client.get("/api/maturity/training/proposals", headers=default_lead)
    ids = {p["id"] for p in listing.json()["proposals"]}
    assert "proposal-null-foreign" not in ids
    assert env.client.get(
        "/api/maturity/training/proposals/proposal-null-foreign",
        headers=default_lead).status_code == 404
    # The proposal's owner tenant still resolves it consistently.
    foreign_lead = env.headers("lead-b")
    foreign_listing = env.client.get("/api/maturity/training/proposals", headers=foreign_lead)
    assert "proposal-null-foreign" in {p["id"] for p in foreign_listing.json()["proposals"]}
    assert env.client.get(
        "/api/maturity/training/proposals/proposal-null-foreign",
        headers=foreign_lead).status_code == 200


def test_expired_approval_refused_and_rejection_terminalizes(env):
    lead = env.headers("lead-a")
    listing = env.client.get("/api/maturity/training/proposals", headers=lead)
    expired = next(p for p in listing.json()["proposals"] if p["id"] == "proposal-expired")
    assert expired["expired"] is True
    approve = env.client.post(
        "/api/maturity/training/proposals/proposal-expired/approve",
        json={"approve": True}, headers=lead)
    assert approve.status_code == 409, approve.text
    env.db.expire_all()
    assert env.db.get(AgentProposal, "proposal-expired").status == ProposalStatus.PENDING_APPROVAL.value
    assert _count(env, "proposal-expired") == 0
    reject = env.client.post(
        "/api/maturity/training/proposals/proposal-expired/reject",
        json={"reason": "expired cleanup"}, headers=lead)
    assert reject.status_code == 200, reject.text
    env.db.expire_all()
    proposal = env.db.get(AgentProposal, "proposal-expired")
    assert proposal.status == ProposalStatus.REJECTED.value
    assert proposal.approver_id == "lead-a"
    assert _count(env, "proposal-expired") == 0


def test_peer_expiry_change_before_claim_wins(env):
    fired = {"done": False}

    def _expire(conn, cursor, statement, parameters, context, executemany):
        if fired["done"] or not statement.lower().lstrip().startswith("update users"):
            return
        fired["done"] = True
        peer = env.Session()
        try:
            row = peer.get(AgentProposal, "proposal-a")
            row.expires_at = datetime.now(timezone.utc) - timedelta(days=2)
            peer.commit()
        finally:
            peer.close()

    event.listen(env.engine, "before_cursor_execute", _expire)
    try:
        response = env.client.post(
            "/api/maturity/training/proposals/proposal-a/approve",
            json={"approve": True}, headers=env.headers("lead-a"))
    finally:
        event.remove(env.engine, "before_cursor_execute", _expire)
    assert fired["done"] is True
    assert response.status_code == 409, response.text
    env.db.expire_all()
    assert env.db.get(AgentProposal, "proposal-a").status == ProposalStatus.PENDING_APPROVAL.value
    assert _count(env, "proposal-a") == 0
