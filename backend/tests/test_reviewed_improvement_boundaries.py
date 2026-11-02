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


def _interleave_claim(env, candidate, action):
    """Run an action in another session exactly before the DB claim update."""
    from sqlalchemy.orm import Query

    original = Query.update
    fired = []

    def wrapper(query, values, *args, **kwargs):
        if values == {"validation_status": "applying"} and not fired:
            fired.append(True)
            writer = env["factory"]()
            try:
                row = writer.query(SkillCandidate).filter_by(
                    id=candidate.id).one()
                action(row, writer)
                writer.commit()
            finally:
                writer.close()
        return original(query, values, *args, **kwargs)

    return wrapper, fired


def test_new_review_between_validation_and_claim_is_preserved(
        env, monkeypatch):  # noqa: F811
    from core.reviewed_improvement import mark_reviewed

    candidate = _candidate(env)

    def replace_review(row, _writer):
        row.skill_description = "Newly reviewed replacement instructions"
        mark_reviewed(
            row, reviewer_id="other-reviewer",
            tenant_id=env["tenant"].id,
            workspace_id=env["workspace"].id)

    wrapper, fired = _interleave_claim(env, candidate, replace_review)
    monkeypatch.setattr("sqlalchemy.orm.Query.update", wrapper)
    with pytest.raises(ValueError, match="conflict|stale|review"):
        _apply(env, candidate)
    assert fired
    fresh = env["factory"]()
    try:
        row = fresh.query(SkillCandidate).filter_by(id=candidate.id).one()
        assert row.validation_status == "validated"
        assert row.skill_description == "Newly reviewed replacement instructions"
        assert row.validation_result["review"]["review_revision"] == 2
        assert fresh.query(SkillExecution).count() == 0
    finally:
        fresh.close()


def test_identical_material_rereview_invalidates_older_claim(
        env, monkeypatch):  # noqa: F811
    from core.reviewed_improvement import mark_reviewed

    candidate = _candidate(env)

    def same_material_new_revision(row, _writer):
        mark_reviewed(
            row, reviewer_id="second-reviewer",
            tenant_id=env["tenant"].id,
            workspace_id=env["workspace"].id)

    wrapper, fired = _interleave_claim(
        env, candidate, same_material_new_revision)
    monkeypatch.setattr("sqlalchemy.orm.Query.update", wrapper)
    with pytest.raises(ValueError, match="conflict|stale|review"):
        _apply(env, candidate)
    assert fired
    fresh = env["factory"]()
    try:
        row = fresh.query(SkillCandidate).filter_by(id=candidate.id).one()
        assert row.validation_status == "validated"
        assert row.validation_result["review"]["review_revision"] == 2
        assert fresh.query(SkillExecution).count() == 0
    finally:
        fresh.close()


def test_rejection_between_validation_and_claim_wins(env, monkeypatch):  # noqa: F811
    candidate = _candidate(env)

    def reject(row, _writer):
        row.validation_status = "rejected"

    wrapper, fired = _interleave_claim(env, candidate, reject)
    monkeypatch.setattr("sqlalchemy.orm.Query.update", wrapper)
    with pytest.raises(ValueError, match="conflict|review"):
        _apply(env, candidate)
    assert fired
    fresh = env["factory"]()
    try:
        row = fresh.query(SkillCandidate).filter_by(id=candidate.id).one()
        assert row.validation_status == "rejected"
        assert fresh.query(SkillExecution).count() == 0
    finally:
        fresh.close()


def test_employee_move_between_validation_and_claim_is_refused(
        env, monkeypatch):  # noqa: F811
    from core.models import AgentRegistry

    candidate = _candidate(env)
    other = Workspace(
        id="moved-workspace", name="Moved", tenant_id=env["tenant"].id)
    env["db"].add(other)
    env["db"].commit()

    def move(row, writer):
        agent = writer.query(AgentRegistry).filter_by(
            id=candidate.agent_id).one()
        agent.workspace_id = other.id
        assert row.id

    wrapper, fired = _interleave_claim(env, candidate, move)
    monkeypatch.setattr("sqlalchemy.orm.Query.update", wrapper)
    with pytest.raises(ValueError, match="conflict|workspace|review"):
        _apply(env, candidate)
    assert fired
    fresh = env["factory"]()
    try:
        assert fresh.query(SkillExecution).count() == 0
        assert fresh.query(SkillCandidate).filter_by(
            id=candidate.id).one().validation_status == "validated"
    finally:
        fresh.close()


def test_two_applies_same_review_produce_one_skill(env, monkeypatch):  # noqa: F811
    from core.reviewed_improvement import apply_reviewed_skill
    from core.skill_builder_service import SkillBuilderService
    from core.skill_registry_service import SkillRegistryService

    candidate = _candidate(env)
    winner = {}

    def second_apply(_row, _writer):
        import threading

        def worker():
            session = env["factory"]()
            try:
                row = session.query(SkillCandidate).filter_by(
                    id=candidate.id).one()
                result = asyncio.run(apply_reviewed_skill(
                    session, row, tenant_id=env["tenant"].id,
                    workspace_id=env["workspace"].id,
                    builder=SkillBuilderService(
                        workspace_root=str(env["tmp_path"])),
                    registry=SkillRegistryService(session)))
                winner.update(result)
            finally:
                session.close()

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()

    wrapper, fired = _interleave_claim(env, candidate, second_apply)
    monkeypatch.setattr("sqlalchemy.orm.Query.update", wrapper)
    result = _apply(env, candidate)
    assert fired
    assert result["skill_id"] == winner["skill_id"], (result, winner)
    assert result["already_applied"] is True
    fresh = env["factory"]()
    try:
        assert fresh.query(SkillExecution).count() == 1
    finally:
        fresh.close()


def test_failed_apply_retry_reuses_package_and_stays_inert(env, monkeypatch):  # noqa: F811
    from core.skill_retrieval_service import SkillRetrievalService

    candidate = _candidate(env)
    execute = env["db"].execute
    failed = {"count": 0}

    def fail_once(statement, *args, **kwargs):
        if (getattr(statement, "is_insert", False)
                and getattr(getattr(statement, "table", None), "name", None)
                == "workspace_skills" and not failed["count"]):
            failed["count"] += 1
            raise ValueError("injected once before workspace link")
        return execute(statement, *args, **kwargs)

    monkeypatch.setattr(env["db"], "execute", fail_once)
    with pytest.raises(ValueError, match="injected once"):
        _apply(env, candidate)
    env["db"].rollback()
    fresh = env["factory"]()
    try:
        assert fresh.query(SkillExecution).count() == 0
        assert SkillRetrievalService().retrieve_top_skills(
            fresh, env["tenant"].id, env["workspace"].id,
            "outlook customer email search") == ""
    finally:
        fresh.close()

    result = _apply(env, candidate)
    assert result["status"] == "promoted"
    assert failed["count"] == 1
    fresh = env["factory"]()
    try:
        assert fresh.query(SkillExecution).count() == 1
        assert "repair_outlook_search" in (
            SkillRetrievalService().retrieve_top_skills(
                fresh, env["tenant"].id, env["workspace"].id,
                "outlook customer email search"))
    finally:
        fresh.close()
