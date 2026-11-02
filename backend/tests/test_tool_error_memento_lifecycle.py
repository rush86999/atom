"""MEM-07: a real tool failure feeds the ONE canonical Memento lifecycle.

The generic-agent hook records a structured signal on the running execution;
episode finalization merges it, downgrades a nominal success to partial and
emits the TaskEvent that ReflectionEngine consumes. The result is a pending
SkillCandidate reviewed through the existing Auto-Dev API — not a second
HITL candidate store, and never an agent configuration change.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from core.models import (
    AgentExecution,
    AgentRegistry,
    EpisodeSegment,
    Tenant,
    Workspace,
)


@pytest.fixture()
def env(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    monkeypatch.setattr("core.database.SessionLocal", factory)
    tenant = Tenant(
        id="tenant-memento", name="Memento Tenant",
        subdomain="memento-runtime")
    workspace = Workspace(
        id="ws-memento", name="Memento Workspace",
        tenant_id=tenant.id,
        metadata_json={"auto_dev": {"enabled": True}},
    )
    agent = AgentRegistry(
        id="memento-agent", name="Memento Employee", category="operations",
        module_path="core.generic_agent", class_name="GenericAgent",
        status="intern", confidence_score=0.5,
        configuration={
            "system_prompt": "original",
            "capability_maturities": {"*": "intern"},
        },
        capabilities=[], workspace_id=workspace.id, tenant_id=tenant.id,
    )
    execution = AgentExecution(
        id="exec-tool-error", agent_id=agent.id, tenant_id=tenant.id,
        workspace_id=workspace.id, status="running", metadata_json={},
    )
    db.add_all([tenant, workspace, agent, execution])
    db.commit()
    try:
        yield {
            "db": db, "factory": factory, "engine": engine,
            "tenant": tenant, "workspace": workspace,
            "agent": agent, "execution_id": execution.id,
            "monkeypatch": monkeypatch,
        }
    finally:
        db.close()
        engine.dispose()


def _failing_agent(env):
    from core.generic_agent import GenericAgent

    agent = GenericAgent(env["agent"], workspace_id=env["workspace"].id)

    def boom(_args, _context):
        raise RuntimeError("400 Syntax error on the customer email search")

    agent._custom_actions = {"unknown.tool": boom}
    return agent


def test_tool_errors_feed_the_canonical_memento_candidate(env):
    from core.auto_dev.event_hooks import TaskEvent
    from core.auto_dev.memento_engine import MementoEngine
    from core.auto_dev.reflection_engine import ReflectionEngine
    from core.auto_dev.models import SkillCandidate
    from core.episode_service import EpisodeService

    agent = _failing_agent(env)
    context = {
        "execution_id": env["execution_id"],
        "tenant_id": env["tenant"].id,
        "run_id": "run-tool-error",
        "operation_id": "op-tool-error",
    }
    for _ in range(2):
        result = asyncio.run(agent._step_act("unknown.tool", {}, context))
        assert "Error" in result

    db = env["db"]
    db.expire_all()
    execution = db.query(AgentExecution).filter(
        AgentExecution.id == env["execution_id"]).one()
    errors = execution.metadata_json["tool_errors"]
    assert len(errors) == 2  # occurrences preserved
    assert errors[0]["signature"] == "unknown.tool"
    assert errors[0]["run_id"] == "run-tool-error"
    assert errors[0]["operation_id"] == "op-tool-error"

    episode = asyncio.run(EpisodeService(db).create_episode_from_execution(
        env["execution_id"], "look up the customer email",
        outcome="success", success=True, metadata={}))
    # A nominal success with tool errors is not a clean success.
    assert episode.success is False
    assert episode.outcome == "partial"
    assert episode.metadata_json["tool_errors"]
    db.add(EpisodeSegment(
        episode_id=episode.id, segment_type="error", sequence_order=1,
        content="Tool call: unknown.tool - failed: 400 Syntax error",
    ))
    db.commit()

    llm = MagicMock()
    llm.generate_completion = AsyncMock(
        return_value={"content": "def repair_unknown_tool():\n    return 1"})
    env["monkeypatch"].setattr(
        MementoEngine, "_get_llm_service", lambda self: llm)
    event = TaskEvent(
        episode_id=episode.id, agent_id=env["agent"].id,
        tenant_id=env["tenant"].id,
        task_description=episode.task_description,
        error_trace=str(episode.metadata_json.get("error") or ""),
        outcome=episode.outcome, metadata=episode.metadata_json,
    )
    asyncio.run(ReflectionEngine(
        db=db, failure_threshold=1).process_failure(event))

    candidate = db.query(SkillCandidate).filter(
        SkillCandidate.agent_id == env["agent"].id).one()
    assert candidate.validation_status == "pending"
    assert candidate.source_episode_id == episode.id
    db.expire_all()
    assert env["agent"].configuration["system_prompt"] == "original"

    # Restart/read-back: a new session still sees the same pending candidate.
    fresh = env["factory"]()
    try:
        assert fresh.query(SkillCandidate).filter(
            SkillCandidate.id == candidate.id,
            SkillCandidate.validation_status == "pending").one()
    finally:
        fresh.close()

    # Authenticated review uses the canonical Auto-Dev route.
    from api.autodev_review_routes import list_candidates

    listed = asyncio.run(list_candidates(
        agent_id=env["agent"].id, status="pending",
        tenant=SimpleNamespace(id=env["tenant"].id),
        current_user=SimpleNamespace(id="reviewer"), db=db))
    assert listed["data"]["count"] == 1
    assert listed["data"]["candidates"][0]["id"] == str(candidate.id)


def test_raised_dispatch_error_is_recorded_too(env):
    """The exception path must feed the same signal, without a candidate."""
    agent = _failing_agent(env)

    async def explode(*_args, **_kwargs):
        raise RuntimeError("dispatch exploded before returning")

    agent._step_act_unaudited = explode
    with pytest.raises(RuntimeError):
        asyncio.run(agent._step_act(
            "unknown.tool", {},
            {"execution_id": env["execution_id"],
             "tenant_id": env["tenant"].id}))

    db = env["db"]
    db.expire_all()
    execution = db.query(AgentExecution).filter(
        AgentExecution.id == env["execution_id"]).one()
    errors = execution.metadata_json["tool_errors"]
    assert len(errors) == 1
    assert errors[0]["signature"] == "unknown.tool"
    assert "dispatch exploded" in errors[0]["error"]
