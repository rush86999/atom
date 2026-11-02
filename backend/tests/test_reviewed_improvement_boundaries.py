"""Boundary controls for reviewed-improvement review/apply.

These mirror the independent probes: review RBAC, moved-employee authority,
atomic failure, stale-session idempotency and changed-material re-review.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auto_dev.models import SkillCandidate
from core.models import AgentRegistry, SkillExecution, Workspace
from core.reviewed_improvement import apply_reviewed_skill
from core.skill_builder_service import SkillBuilderService
from core.skill_registry_service import SkillRegistryService
from tests.test_reviewed_improvement_apply import _apply, _candidate, env  # noqa: F401


def _client(env, role):
    from api.autodev_review_routes import router
    from core.auth import get_current_tenant, get_current_user
    from core.database import get_db

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: env["db"]
    app.dependency_overrides[get_current_tenant] = lambda: env["tenant"]
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="reviewer", role=role, workspace_id=env["workspace"].id,
        tenant_id=env["tenant"].id, email="reviewer@example.invalid")
    return TestClient(app)


def test_viewer_cannot_validate_candidate(env):  # noqa: F811
    candidate = _candidate(env, status="pending")
    response = _client(env, "viewer").post(
        f"/api/autodev/skills/{candidate.id}/approve")
    assert response.status_code == 403, response.text
    env["db"].refresh(candidate)
    assert candidate.validation_status == "pending"


def test_moved_employee_does_not_redirect_apply(env, monkeypatch):  # noqa: F811
    from api import autodev_review_routes as routes

    candidate = _candidate(env)
    other = Workspace(
        id="other-workspace", name="Other", tenant_id=env["tenant"].id)
    env["db"].add(other)
    env["agent"].workspace_id = other.id
    env["db"].commit()
    called = []

    async def capture(_db, _candidate, **kwargs):
        called.append(kwargs)
        return {"status": "promoted", "already_applied": False}

    monkeypatch.setattr(routes, "apply_reviewed_skill", capture)
    response = _client(env, "team_lead").post(
        f"/api/autodev/skills/{candidate.id}/apply")
    assert response.status_code in (403, 404), (response.text, called)
    assert not called


def test_failed_apply_leaves_no_active_registry_entry(env, monkeypatch):  # noqa: F811
    candidate = _candidate(env)
    execute = env["db"].execute

    def fail_link(statement, *args, **kwargs):
        if (getattr(statement, "is_insert", False)
                and getattr(getattr(statement, "table", None), "name", None)
                == "workspace_skills"):
            raise ValueError("injected failure before workspace link")
        return execute(statement, *args, **kwargs)

    monkeypatch.setattr(env["db"], "execute", fail_link)
    with pytest.raises(ValueError, match="injected failure"):
        _apply(env, candidate)
    env["db"].rollback()
    fresh = env["factory"]()
    try:
        assert fresh.query(SkillExecution).count() == 0
    finally:
        fresh.close()


def test_stale_second_session_apply_is_idempotent(env):  # noqa: F811
    candidate = _candidate(env)
    second = env["factory"]()
    stale = second.query(SkillCandidate).filter_by(id=candidate.id).one()
    first = _apply(env, candidate)
    try:
        result = asyncio.run(apply_reviewed_skill(
            second, stale, tenant_id=env["tenant"].id,
            workspace_id=env["workspace"].id,
            builder=SkillBuilderService(
                workspace_root=str(env["tmp_path"])),
            registry=SkillRegistryService(second)))
        assert result["skill_id"] == first["skill_id"], (first, result)
        assert second.query(SkillExecution).count() == 1
    finally:
        second.close()


def test_changed_material_requires_fresh_review(env):  # noqa: F811
    candidate = _candidate(env, status="pending")
    response = _client(env, "team_lead").post(
        f"/api/autodev/skills/{candidate.id}/approve")
    assert response.status_code == 200, response.text
    candidate.skill_description = (
        "Unreviewed replacement instructions for the employee")
    env["db"].commit()
    with pytest.raises(ValueError, match="changed|review|conflict"):
        _apply(env, candidate)
    assert env["db"].query(SkillExecution).count() == 0
