"""Reviewed improvement lifecycle: review, explicit typed apply, consumption.

Pending is not permission. Validation alone changes nothing. An explicit
authorized apply writes only the prompt skill (no generated code) and ordinary
work retrieval must see it after a new session.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.auto_dev.models import SkillCandidate
from core.database import Base, get_db
from core.models import AgentRegistry, SkillExecution, Tenant, User, Workspace
from core.reviewed_improvement import apply_reviewed_skill
from core.skill_builder_service import SkillBuilderService
from core.skill_registry_service import SkillRegistryService


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("TESTING", "1")
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    tenant = Tenant(
        id="tenant-review", name="Review Tenant", subdomain="review")
    workspace = Workspace(
        id="ws-review", name="Review Workspace", tenant_id=tenant.id)
    agent = AgentRegistry(
        id="agent-review", name="Review Employee", category="operations",
        module_path="core.generic_agent", class_name="GenericAgent",
        status="intern", confidence_score=0.5,
        configuration={"system_prompt": "original"},
        capabilities=[], workspace_id=workspace.id, tenant_id=tenant.id)
    user = User(
        id="reviewer", email="reviewer@example.invalid",
        hashed_password="x", first_name="R", last_name="V",
        role="workspace_admin", status="active",
        workspace_id=workspace.id, tenant_id=tenant.id, is_active=True)
    db.add_all([tenant, workspace, agent, user])
    db.commit()
    try:
        yield {
            "db": db, "factory": factory, "engine": engine,
            "tenant": tenant, "workspace": workspace, "agent": agent,
            "user": user, "tmp_path": tmp_path,
        }
    finally:
        db.close()
        engine.dispose()


def _candidate(env, status="validated", name="repair_outlook_search"):
    db = env["db"]
    row = SkillCandidate(
        id=f"cand-{name}", tenant_id=env["tenant"].id,
        agent_id=env["agent"].id, source_episode_id="episode-1",
        skill_name=name,
        skill_description="repair outlook customer email search failures",
        generated_code="def repair_outlook_search():\n    return []",
        failure_pattern={
            "failure_summary": "outlook search failed on the customer email"},
        validation_status=status,
    )
    db.add(row)
    db.commit()
    return row


def _apply(env, candidate):
    return asyncio.run(apply_reviewed_skill(
        env["db"], candidate, tenant_id=env["tenant"].id,
        workspace_id=env["workspace"].id,
        builder=SkillBuilderService(workspace_root=str(env["tmp_path"])),
        registry=SkillRegistryService(env["db"]),
    ))


def test_pending_candidate_cannot_be_applied(env):
    candidate = _candidate(env, status="pending")
    with pytest.raises(ValueError, match="candidate_not_reviewed"):
        _apply(env, candidate)
    assert env["db"].query(SkillExecution).count() == 0
    assert not list(env["tmp_path"].rglob("SKILL.md"))


def test_validation_alone_changes_nothing(env):
    candidate = _candidate(env, status="validated")
    assert candidate.validation_status == "validated"
    assert env["db"].query(SkillExecution).count() == 0
    assert not list(env["tmp_path"].rglob("SKILL.md"))
    db = env["db"]
    db.refresh(env["agent"])
    assert env["agent"].configuration == {"system_prompt": "original"}


def test_apply_writes_typed_skill_and_ordinary_work_consumes_it(env):
    from core.skill_retrieval_service import SkillRetrievalService

    candidate = _candidate(env)
    result = _apply(env, candidate)
    assert result["status"] == "promoted"
    assert result["generated_code_applied"] is False
    assert result["skill_id"]

    package = env["tmp_path"] / env["tenant"].id / "skills" / (
        "repair_outlook_search")
    markdown = (package / "SKILL.md").read_text()
    assert "repair outlook customer email search failures" in markdown
    assert "def repair_outlook_search" not in markdown
    assert not list(package.rglob("*.py"))

    text = SkillRetrievalService().retrieve_top_skills(
        env["db"], env["tenant"].id, env["workspace"].id,
        "outlook customer email search")
    assert "repair_outlook_search" in text

    env["db"].refresh(env["agent"])
    assert env["agent"].configuration == {"system_prompt": "original"}
    env["db"].refresh(candidate)
    assert candidate.validation_status == "promoted"

    # Restart: a new session still sees the promoted skill and retrieval works.
    fresh = env["factory"]()
    try:
        assert fresh.query(SkillCandidate).filter(
            SkillCandidate.id == candidate.id,
            SkillCandidate.validation_status == "promoted").one()
        assert "repair_outlook_search" in (
            SkillRetrievalService().retrieve_top_skills(
                fresh, env["tenant"].id, env["workspace"].id,
                "outlook customer email search"))
    finally:
        fresh.close()


def test_duplicate_apply_is_idempotent(env):
    candidate = _candidate(env)
    first = _apply(env, candidate)
    second = _apply(env, candidate)
    assert first["already_applied"] is False
    assert second["already_applied"] is True
    assert second["skill_id"] == first["skill_id"]
    assert env["db"].query(SkillExecution).count() == 1


def test_route_requires_reviewer_authority(env, monkeypatch):
    from api.autodev_review_routes import router
    from core.auth import get_current_tenant, get_current_user

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: env["db"]

    def _client(role):
        user = SimpleNamespace(
            id=f"{role}-user", role=role,
            workspace_id=env["workspace"].id,
            tenant_id=env["tenant"].id, email=f"{role}@example.invalid")
        app.dependency_overrides[get_current_user] = lambda: user
        return TestClient(app)

    candidate = _candidate(env, name="viewer_candidate")
    viewer = _client("viewer")
    response = viewer.post(f"/api/autodev/skills/{candidate.id}/apply")
    assert response.status_code == 403, response.text

    candidate2 = _candidate(env, name="admin_candidate")
    admin = _client("workspace_admin")
    app.dependency_overrides[get_current_tenant] = lambda: env["tenant"]
    response = admin.post(f"/api/autodev/skills/{candidate2.id}/apply")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "promoted"
