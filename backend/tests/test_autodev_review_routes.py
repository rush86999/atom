"""Auto-Dev review routes — the supervisor API for the evolution harness.

Covers the journey contract: pending candidates (Memento skills +
AlphaEvolver tool mutations) list unified; approve/reject transition
statuses; tool-error signals aggregate per signature for the review UI.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.autodev_review_routes import router as review_router
from core.auto_dev.models import SkillCandidate, ToolMutation
from core.auth import get_current_tenant, get_current_user
from core.database import Base, get_db
from core.models import (
    AgentExecution,
    AgentRegistry,
    AuditLog,
    Tenant,
    User,
    Workspace,
)


@pytest.fixture()
def env(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/autodev-review.db",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    seed = Session()
    tenant = Tenant(id="tenant-1", name="Tenant One", subdomain="tenant-one")
    workspace = Workspace(
        id="workspace-1", name="Workspace One", tenant_id="tenant-1")
    lead = User(
        id="lead-1", tenant_id="tenant-1", workspace_id="workspace-1",
        email="lead@example.com", first_name="Lead", last_name="One",
        role="team_lead", status="active", is_active=True)
    agent = AgentRegistry(
        id="agent-1", name="Agent One", category="Operations",
        module_path="agents.one", class_name="AgentOne",
        tenant_id="tenant-1", workspace_id="workspace-1")
    candidate = SkillCandidate(
        id="cand-1", tenant_id="tenant-1", agent_id="agent-1",
        skill_name="outlook_search_fix",
        skill_description="Search the mailbox safely",
        generated_code="def run(): ...",
        failure_pattern={"failure_summary": "outlook search 400s on emails"},
        validation_status="pending")
    mutation = ToolMutation(
        id="mut-1", tenant_id="tenant-1",
        tool_name="outlook.search_emails",
        mutated_code="def mutated(): ...",
        sandbox_status="pending", execution_error=None)
    executions = [
        AgentExecution(
            id="exec-1", agent_id="agent-1", tenant_id="tenant-1",
            status="completed",
            metadata_json={"tool_errors": [{
                "signature": "outlook.search_emails",
                "error": "400 '@'",
                "at": "2026-09-02T18:00:00",
            }]}),
        AgentExecution(
            id="exec-2", agent_id="agent-1", tenant_id="tenant-1",
            status="completed",
            metadata_json={"tool_errors": [{
                "signature": "outlook.search_emails",
                "error": "400 '@' again",
                "at": "2026-09-02T19:00:00",
            }]}),
    ]
    seed.add_all([
        tenant, workspace, lead, agent, candidate, mutation, *executions])
    seed.commit()
    seed.close()

    db = Session()
    actor = db.query(User).filter(User.id == "lead-1").one()
    tenant_row = db.query(Tenant).filter(Tenant.id == "tenant-1").one()
    db.close()

    app = FastAPI()
    app.include_router(review_router)

    def db_override():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_current_user] = lambda: actor
    app.dependency_overrides[get_current_tenant] = lambda: tenant_row
    return Session, TestClient(app, raise_server_exceptions=False)


def test_list_candidates_unifies_skills_and_mutations(env):
    Session, client = env
    response = client.get("/api/autodev/candidates")
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    kinds = {c["kind"] for c in body["candidates"]}
    assert kinds == {"skill", "mutation"}
    assert body["count"] == 2
    names = {c["name"] for c in body["candidates"]}
    assert names == {"outlook_search_fix", "outlook.search_emails"}


def test_approve_skill_marks_validated_and_commits(env):
    Session, client = env
    response = client.post("/api/autodev/skills/cand-1/approve")
    assert response.status_code == 200, response.text
    db = Session()
    try:
        candidate = db.query(SkillCandidate).filter(
            SkillCandidate.id == "cand-1").one()
        assert candidate.validation_status == "validated"
        assert candidate.validated_at is not None
        review = (candidate.validation_result or {}).get("review") or {}
        assert review.get("digest")
        assert review.get("review_revision") == 1
    finally:
        db.close()


def test_reject_mutation_marks_rejected(env):
    Session, client = env
    response = client.post(
        "/api/autodev/mutations/mut-1/reject?operation_id=route-reject")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "rejected"
    db = Session()
    try:
        mutation = db.query(ToolMutation).filter(
            ToolMutation.id == "mut-1").one()
        assert mutation.sandbox_status == "rejected"
        audit = db.query(AuditLog).filter(
            AuditLog.id == "autodev:tool-mutation:route-reject").one()
        assert audit.action == "tool_mutation_rejected"
    finally:
        db.close()


def test_approve_missing_candidate_404(env):
    _Session, client = env
    response = client.post("/api/autodev/skills/nope/approve")
    assert response.status_code == 404


def test_tool_errors_aggregate_by_signature(env):
    _Session, client = env
    response = client.get(
        "/api/autodev/tool-errors", params={"agent_id": "agent-1"})
    assert response.status_code == 200, response.text
    body = response.json()["data"]["tool_errors"]
    assert len(body) == 1
    assert body[0]["signature"] == "outlook.search_emails"
    assert body[0]["count"] == 2
    assert "again" in body[0]["last_error"]
