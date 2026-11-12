"""MEM-07 consolidated chain: real tool error -> pending Memento candidate ->
authenticated review -> existing typed-prompt apply -> fresh-session ordinary-work
consumption.

Only the Memento model transport is doubled (controlled generated-code text).
No live model/provider/network/sandbox/account/credential is used.  Generated
code is never applied; the agent configuration is never mutated.
"""
from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.auto_dev.models import SkillCandidate
from core.database import Base
from core.models import (
    AgentExecution,
    AgentRegistry,
    EpisodeSegment,
    Skill,
    SkillExecution,
    Tenant,
    User,
    Workspace,
)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("ATOM_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ATOM_WORKSPACE_SKILLS_ROOT", str(tmp_path / "skills"))
    path = tmp_path / "mem07.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()

    @contextmanager
    def _session():
        session = factory()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    monkeypatch.setattr("core.database.SessionLocal", factory)
    monkeypatch.setattr("core.database.get_db_session", _session)
    monkeypatch.setattr("core.generic_agent.get_db_session", _session)

    tenant = Tenant(
        id="tenant-mem07", name="MEM-07 Tenant", subdomain="mem07-runtime")
    workspace = Workspace(
        id="ws-mem07", name="MEM-07 Workspace", tenant_id=tenant.id,
        metadata_json={"auto_dev": {"enabled": True}})
    agent = AgentRegistry(
        id="agent-mem07", name="MEM-07 Employee", category="operations",
        module_path="core.generic_agent", class_name="GenericAgent",
        status="intern", confidence_score=0.5,
        configuration={
            "system_prompt": "original",
            "capability_maturities": {"*": "intern"},
        },
        capabilities=[], workspace_id=workspace.id, tenant_id=tenant.id)
    user = User(
        id="reviewer-mem07", email="reviewer@example.invalid",
        hashed_password="x", first_name="R", last_name="V",
        role="workspace_admin", status="active",
        workspace_id=workspace.id, tenant_id=tenant.id, is_active=True)
    viewer = User(
        id="viewer-mem07", email="viewer@example.invalid",
        hashed_password="x", first_name="V", last_name="W",
        role="viewer", status="active",
        workspace_id=workspace.id, tenant_id=tenant.id, is_active=True)
    execution = AgentExecution(
        id="exec-mem07", agent_id=agent.id, tenant_id=tenant.id,
        workspace_id=workspace.id, status="running", metadata_json={})
    db.add_all([tenant, workspace, agent, user, viewer, execution])
    db.commit()
    try:
        yield {
            "db": db, "factory": factory, "engine": engine,
            "tenant": tenant, "workspace": workspace, "agent": agent,
            "user": user, "viewer": viewer, "execution_id": execution.id,
            "path": path, "tmp_path": tmp_path, "monkeypatch": monkeypatch,
        }
    finally:
        db.close()
        engine.dispose()


TASK = "look up the customer email in outlook"


def _failing_agent(env):
    from core.generic_agent import GenericAgent

    agent = GenericAgent(env["agent"], workspace_id=env["workspace"].id)

    def boom(_args, _context):
        raise RuntimeError("400 Syntax error on the customer email search")

    agent._custom_actions = {"unknown.tool": boom}
    return agent


def _controlled_memento_llm(monkeypatch, calls):
    """Only the model transport is doubled; all lifecycle code is real."""
    llm = MagicMock()
    llm.generate_completion = AsyncMock(
        side_effect=lambda **kw: calls.append(kw) or {
            "content": "def repair_unknown_tool():\n    return 1"})
    monkeypatch.setattr(
        "core.auto_dev.memento_engine.MementoEngine._get_llm_service",
        lambda self: llm)
    return llm


def _pending_candidate_from_tool_error(env):
    """Drive the real episode event through the registered consumer.

    No EpisodeSegment is inserted and no TaskEvent/process_failure is authored
    here: EpisodeService emits the failure event on the real event bus and the
    real registered ReflectionEngine consumes it in a fresh session.  The whole
    producer/consumer run is one asyncio loop; only the Memento model leaf is
    doubled.
    """
    from core.auto_dev.event_hooks import event_bus
    from core.auto_dev.reflection_engine import ReflectionEngine
    from core.episode_service import EpisodeService

    calls = []
    _controlled_memento_llm(env["monkeypatch"], calls)
    env["monkeypatch"].setattr(event_bus, "_fail_handlers", [])
    ReflectionEngine(db=None, failure_threshold=1).register()

    async def _run():
        agent = _failing_agent(env)
        context = {
            "execution_id": env["execution_id"],
            "tenant_id": env["tenant"].id,
            "run_id": "run-mem07-natural",
            "operation_id": "op-mem07-natural",
        }
        for _ in range(2):
            result = await agent._step_act("unknown.tool", {}, context)
            assert "Error" in result

        env["db"].expire_all()
        execution = env["db"].query(AgentExecution).filter(
            AgentExecution.id == env["execution_id"]).one()
        assert execution.metadata_json["tool_errors"]

        episode = await EpisodeService(
            env["db"]).create_episode_from_execution(
                env["execution_id"], TASK, outcome="success", success=True,
                metadata={})
        assert episode.success is False
        assert episode.outcome == "partial"

        # The emitted event is dispatched to the registered consumer on this
        # loop; poll a fresh session for its durable candidate.
        for _ in range(300):
            await asyncio.sleep(0.01)
            with env["factory"]() as fresh:
                rows = fresh.query(SkillCandidate).filter(
                    SkillCandidate.agent_id == env["agent"].id).all()
                if rows:
                    assert len(rows) == 1
                    assert rows[0].validation_status == "pending"
                    assert calls, "controlled Memento model leaf was not reached"
                    return rows[0], calls
        raise AssertionError(
            "actual emitted failure event did not create a pending candidate")

    return asyncio.run(_run())


def _http_client(env, *, user=None):
    """Actual mounted router + real normal JWT auth dependencies.

    Only the persistence dependency is pointed at the scratch SQLite factory;
    ``get_current_user``/``get_current_tenant`` run normally from the bearer
    token, real User/Tenant rows and workspace authority.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.autodev_review_routes import router as review_router
    from core.auth import create_access_token
    from core.database import get_db

    app = FastAPI()
    app.include_router(review_router)

    def _db():
        session = env["factory"]()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _db
    actor = user or env["user"]
    token = create_access_token({"sub": actor.id}, user=actor)
    return (
        TestClient(app, raise_server_exceptions=False),
        {"Authorization": f"Bearer {token}"},
    )


def _approve_and_apply(env, candidate):
    client, headers = _http_client(env)
    approved = client.post(
        f"/api/autodev/skills/{candidate.id}/approve", headers=headers)
    assert approved.status_code == 200, approved.text
    applied = client.post(
        f"/api/autodev/skills/{candidate.id}/apply", headers=headers)
    assert applied.status_code == 200, applied.text
    return client, headers, approved.json()["data"], applied.json()["data"]


def _list_skill(client, headers, candidate_id, *, status):
    response = client.get(
        "/api/autodev/candidates", params={"status": status},
        headers=headers)
    assert response.status_code == 200, response.text
    return next(
        item for item in response.json()["data"]["candidates"]
        if item["kind"] == "skill" and item["id"] == str(candidate_id))


def _machine_validate(env, candidate_id):
    """Run the real machine-validation path; only the sandbox leaf is doubled."""
    from core.auto_dev.memento_engine import MementoEngine

    sandbox = SimpleNamespace(
        execute_raw_python=AsyncMock(return_value={
            "status": "success", "output": "", "execution_seconds": 0.0}))
    result = asyncio.run(MementoEngine(
        db=env["db"], sandbox=sandbox).validate_candidate(
            candidate_id, env["tenant"].id))
    assert result["passed"] is True, result


def _fresh_prompt(env, query):
    from core.generic_agent import GenericAgent

    fresh = env["factory"]()
    try:
        agent_row = fresh.query(AgentRegistry).filter(
            AgentRegistry.id == env["agent"].id).one()
        agent = GenericAgent(agent_row, workspace_id=env["workspace"].id)
        agent.tenant_id = env["tenant"].id
        return agent._retrieve_skill_instructions(query)
    finally:
        fresh.close()


def test_consolidated_tool_error_to_fresh_session_consumption(env):
    natural, _calls = _pending_candidate_from_tool_error(env)
    candidate = env["db"].query(SkillCandidate).filter(
        SkillCandidate.id == natural.id).one()
    original_config = dict(env["agent"].configuration)
    generated_code = candidate.generated_code

    client, headers, approved, applied = _approve_and_apply(env, candidate)

    assert approved["status"] == "validated", approved
    assert applied["status"] == "promoted", applied
    assert applied["generated_code_applied"] is False, applied
    env["db"].refresh(env["agent"])
    assert env["agent"].configuration == original_config
    env["db"].refresh(candidate)
    assert candidate.validation_status == "promoted"

    package = next((env["tmp_path"] / "skills" / env["tenant"].id / "skills").glob(
        f"{candidate.skill_name}_r*"))
    markdown = (package / "SKILL.md").read_text()
    assert candidate.skill_description.strip() in markdown
    assert generated_code not in markdown
    assert not list(package.rglob("*.py"))

    skill_row = env["db"].query(Skill).filter(
        Skill.name == f"{candidate.skill_name}_r"
        f"{candidate.validation_result['review']['review_revision']}").one()
    assert candidate.skill_description.strip() in skill_row.long_description
    assert generated_code not in skill_row.long_description

    prompt = _fresh_prompt(env, candidate.skill_description or TASK)
    assert candidate.skill_name in prompt
    assert "look up the customer email in outlook" in prompt
    assert generated_code not in prompt

    # Repeat apply is idempotent and does not create a second skill/execution.
    second = client.post(
        f"/api/autodev/skills/{candidate.id}/apply", headers=headers)
    assert second.status_code == 200, second.text
    assert second.json()["data"]["already_applied"] is True, second.text
    assert env["db"].query(Skill).count() == 1
    assert env["db"].query(SkillExecution).count() == 1


def _assert_no_promotion(env):
    from core.models import Skill, SkillExecution

    assert env["db"].query(Skill).count() == 0
    assert env["db"].query(SkillExecution).count() == 0
    env["db"].refresh(env["agent"])
    assert env["agent"].configuration == {
        "system_prompt": "original",
        "capability_maturities": {"*": "intern"},
    }


def test_unreviewed_pending_candidate_cannot_apply(env):
    candidate, _calls = _pending_candidate_from_tool_error(env)
    client, headers = _http_client(env)

    response = client.post(
        f"/api/autodev/skills/{candidate.id}/apply", headers=headers)
    assert response.status_code == 409, response.text
    _assert_no_promotion(env)


def test_rejected_candidate_cannot_apply(env):
    candidate, _calls = _pending_candidate_from_tool_error(env)
    client, headers = _http_client(env)

    rejected = client.post(
        f"/api/autodev/skills/{candidate.id}/reject", headers=headers)
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["data"]["status"] == "rejected"

    response = client.post(
        f"/api/autodev/skills/{candidate.id}/apply", headers=headers)
    assert response.status_code == 409, response.text
    _assert_no_promotion(env)


def test_changed_reviewed_material_cannot_apply(env):
    candidate, _calls = _pending_candidate_from_tool_error(env)
    client, headers = _http_client(env)

    approved = client.post(
        f"/api/autodev/skills/{candidate.id}/approve", headers=headers)
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["status"] == "validated"

    # The reviewer approved an exact snapshot.  Changing generated code after
    # review invalidates the binding even though no code is ever promoted.
    current = env["db"].query(SkillCandidate).filter(
        SkillCandidate.id == candidate.id).one()
    current.generated_code = "def changed_after_review():\n    return 99"
    env["db"].commit()

    response = client.post(
        f"/api/autodev/skills/{candidate.id}/apply", headers=headers)
    assert response.status_code == 409, response.text
    assert "stale_review" in response.text
    _assert_no_promotion(env)


def test_list_apply_eligibility_tracks_review_binding(env):
    candidate, _calls = _pending_candidate_from_tool_error(env)
    client, headers = _http_client(env)

    # Machine validation alone writes ``validated`` but is not human review.
    _machine_validate(env, candidate.id)
    machine = _list_skill(
        client, headers, candidate.id, status="validated")
    assert machine["status"] == "validated", machine
    assert machine["reviewed"] is False, machine
    assert machine["apply_eligible"] is False, machine

    approved = client.post(
        f"/api/autodev/skills/{candidate.id}/approve", headers=headers)
    assert approved.status_code == 200, approved.text
    reviewed = _list_skill(
        client, headers, candidate.id, status="validated")
    assert reviewed["reviewed"] is True, reviewed
    assert reviewed["apply_eligible"] is True, reviewed

    # Material changed after review makes the binding stale; the list signal
    # mirrors the authoritative apply refusal.
    current = env["db"].query(SkillCandidate).filter(
        SkillCandidate.id == candidate.id).one()
    current.skill_description = "Replacement instructions after review"
    env["db"].commit()

    stale = _list_skill(
        client, headers, candidate.id, status="validated")
    assert stale["reviewed"] is True, stale
    assert stale["apply_eligible"] is False, stale

    refused = client.post(
        f"/api/autodev/skills/{candidate.id}/apply", headers=headers)
    assert refused.status_code == 409, refused.text
    assert "stale_review" in refused.text


def test_http_review_apply_requires_real_authentication(env):
    candidate, _calls = _pending_candidate_from_tool_error(env)
    # No bearer token is rejected by the real get_current_user dependency.
    unauthenticated, _headers = _http_client(env)
    response = unauthenticated.post(
        f"/api/autodev/skills/{candidate.id}/approve")
    assert response.status_code == 401, response.text

    # A real viewer JWT reaches the real router but lacks TEAM_LEAD authority.
    viewer_client, viewer_headers = _http_client(env, user=env["viewer"])
    response = viewer_client.post(
        f"/api/autodev/skills/{candidate.id}/approve",
        headers=viewer_headers)
    assert response.status_code == 403, response.text

    current = env["db"].query(SkillCandidate).filter(
        SkillCandidate.id == candidate.id).one()
    assert current.validation_status == "pending"
    _assert_no_promotion(env)
