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
    execution = AgentExecution(
        id="exec-mem07", agent_id=agent.id, tenant_id=tenant.id,
        workspace_id=workspace.id, status="running", metadata_json={})
    db.add_all([tenant, workspace, agent, user, execution])
    db.commit()
    try:
        yield {
            "db": db, "factory": factory, "engine": engine,
            "tenant": tenant, "workspace": workspace, "agent": agent,
            "user": user, "execution_id": execution.id,
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
    from core.auto_dev.event_hooks import TaskEvent
    from core.auto_dev.reflection_engine import ReflectionEngine
    from core.episode_service import EpisodeService

    agent = _failing_agent(env)
    context = {
        "execution_id": env["execution_id"],
        "tenant_id": env["tenant"].id,
        "run_id": "run-mem07",
        "operation_id": "op-mem07",
    }
    for _ in range(2):
        result = asyncio.run(agent._step_act("unknown.tool", {}, context))
        assert "Error" in result

    db = env["db"]
    db.expire_all()
    execution = db.query(AgentExecution).filter(
        AgentExecution.id == env["execution_id"]).one()
    assert execution.metadata_json["tool_errors"]

    episode = asyncio.run(EpisodeService(db).create_episode_from_execution(
        env["execution_id"], TASK, outcome="success", success=True,
        metadata={}))
    assert episode.success is False
    assert episode.outcome == "partial"
    db.add(EpisodeSegment(
        episode_id=episode.id, segment_type="error", sequence_order=1,
        content="Tool call: unknown.tool - failed: 400 Syntax error"))
    db.commit()

    calls = []
    _controlled_memento_llm(env["monkeypatch"], calls)
    event = TaskEvent(
        episode_id=episode.id, agent_id=env["agent"].id,
        tenant_id=env["tenant"].id, task_description=TASK,
        error_trace=str(episode.metadata_json.get("error") or ""),
        outcome=episode.outcome, metadata=episode.metadata_json)
    asyncio.run(ReflectionEngine(
        db=db, failure_threshold=1).process_failure(event))
    candidate = db.query(SkillCandidate).filter(
        SkillCandidate.agent_id == env["agent"].id).one()
    assert candidate.validation_status == "pending"
    assert calls, "controlled model leaf was not reached"
    return candidate, calls


def _route_objects(env):
    return dict(
        tenant=env["tenant"], current_user=env["user"], db=env["db"])


def _approve_and_apply(env, candidate):
    from api.autodev_review_routes import (
        apply_skill_candidate,
        approve_skill_candidate,
    )

    approved = asyncio.run(approve_skill_candidate(
        str(candidate.id), **_route_objects(env)))
    assert approved["data"]["status"] == "validated"
    applied = asyncio.run(apply_skill_candidate(
        str(candidate.id), **_route_objects(env)))
    return approved, applied


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
    candidate, _calls = _pending_candidate_from_tool_error(env)
    original_config = dict(env["agent"].configuration)
    generated_code = candidate.generated_code

    _approved, applied = _approve_and_apply(env, candidate)

    assert applied["data"]["status"] == "promoted", applied
    assert applied["data"]["generated_code_applied"] is False, applied
    env["db"].refresh(env["agent"])
    assert env["agent"].configuration == original_config
    env["db"].refresh(candidate)
    assert candidate.validation_status == "promoted"

    package = next((env["tmp_path"] / "skills" / env["tenant"].id / "skills").glob(
        f"{candidate.skill_name}_r*"))
    markdown = (package / "SKILL.md").read_text()
    assert candidate.skill_description in markdown
    assert generated_code not in markdown
    assert not list(package.rglob("*.py"))

    skill_row = env["db"].query(Skill).filter(
        Skill.name == f"{candidate.skill_name}_r"
        f"{candidate.validation_result['review']['review_revision']}").one()
    assert candidate.skill_description in skill_row.long_description
    assert generated_code not in skill_row.long_description

    prompt = _fresh_prompt(env, candidate.skill_description or TASK)
    assert candidate.skill_name in prompt
    assert "look up the customer email in outlook" in prompt
    assert "unknown.tool" in prompt
    assert generated_code not in prompt

    # Repeat apply is idempotent and does not create a second skill/execution.
    from api.autodev_review_routes import apply_skill_candidate

    second = asyncio.run(apply_skill_candidate(
        str(candidate.id), **_route_objects(env)))
    assert second["data"]["already_applied"] is True, second
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
    from fastapi import HTTPException
    from api.autodev_review_routes import apply_skill_candidate

    candidate, _calls = _pending_candidate_from_tool_error(env)
    assert candidate.validation_status == "pending"

    with pytest.raises(HTTPException) as exc:
        asyncio.run(apply_skill_candidate(
            str(candidate.id), **_route_objects(env)))
    assert exc.value.status_code == 409
    _assert_no_promotion(env)


def test_rejected_candidate_cannot_apply(env):
    from fastapi import HTTPException
    from api.autodev_review_routes import (
        apply_skill_candidate,
        reject_skill_candidate,
    )

    candidate, _calls = _pending_candidate_from_tool_error(env)
    rejected = asyncio.run(reject_skill_candidate(
        str(candidate.id), **_route_objects(env)))
    assert rejected["data"]["status"] == "rejected"

    with pytest.raises(HTTPException) as exc:
        asyncio.run(apply_skill_candidate(
            str(candidate.id), **_route_objects(env)))
    assert exc.value.status_code == 409
    _assert_no_promotion(env)


def test_changed_reviewed_material_cannot_apply(env):
    from fastapi import HTTPException
    from api.autodev_review_routes import (
        apply_skill_candidate,
        approve_skill_candidate,
    )

    candidate, _calls = _pending_candidate_from_tool_error(env)
    approved = asyncio.run(approve_skill_candidate(
        str(candidate.id), **_route_objects(env)))
    assert approved["data"]["status"] == "validated"

    # The reviewer approved an exact snapshot.  Changing generated code after
    # review invalidates the binding even though no code is ever promoted.
    candidate.generated_code = "def changed_after_review():\n    return 99"
    env["db"].commit()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(apply_skill_candidate(
            str(candidate.id), **_route_objects(env)))
    assert exc.value.status_code == 409
    assert "stale_review" in str(exc.value.detail)
    _assert_no_promotion(env)
