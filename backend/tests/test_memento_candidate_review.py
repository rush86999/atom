"""MEM-07: a tool-error failure becomes a pending, reviewable candidate; no
agent behavior changes until explicit review/application."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.auto_dev.memento_engine import MementoEngine
from core.database import Base
from core.models import AgentRegistry


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _agent(db):
    agent = AgentRegistry(
        id="memento-agent", name="Memento Employee", category="operations",
        module_path="core.generic_agent", class_name="GenericAgent",
        status="intern", confidence_score=0.5,
        configuration={"system_prompt": "original"},
        capabilities=[], workspace_id="ws-memento", tenant_id="tenant-memento",
    )
    db.add(agent)
    db.commit()
    return agent


def test_tool_error_candidate_stays_pending_and_review_does_not_mutate_agent(db):
    from api.autodev_review_routes import (
        approve_skill_candidate,
        list_candidates,
        reject_skill_candidate,
    )

    agent = _agent(db)
    llm = MagicMock()
    llm.generate_completion = AsyncMock(
        return_value={"content": "def repaired_search():\n    return []"})
    engine = MementoEngine(db=db, llm_service=llm)
    candidate = asyncio.run(engine.generate_skill_candidate(
        tenant_id="tenant-memento",
        agent_id=agent.id,
        episode_id="episode-tool-error",
        failure_analysis={
            "episode_id": "episode-tool-error",
            "task_description": "search the customer email",
            "error_trace": "outlook.search_emails: 400 Syntax error",
            "failure_summary": "tool error on customer email search",
            "suggested_skill_name": "repair_outlook_search",
            "tenant_id": "tenant-memento",
            "agent_id": agent.id,
        },
    ))
    assert candidate.validation_status == "pending"
    db.refresh(agent)
    assert agent.configuration == {"system_prompt": "original"}

    tenant = SimpleNamespace(id="tenant-memento")
    user = SimpleNamespace(id="reviewer")
    listed = asyncio.run(list_candidates(
        agent_id=agent.id, status="pending", tenant=tenant,
        current_user=user, db=db))
    assert listed["data"]["count"] == 1
    assert listed["data"]["candidates"][0]["id"] == str(candidate.id)
    assert listed["data"]["candidates"][0]["status"] == "pending"

    approved = asyncio.run(approve_skill_candidate(
        str(candidate.id), tenant=tenant, current_user=user, db=db))
    assert approved["data"]["status"] == "validated"
    db.refresh(agent)
    assert agent.configuration == {"system_prompt": "original"}

    rejected = asyncio.run(reject_skill_candidate(
        str(candidate.id), tenant=tenant, current_user=user, db=db))
    assert rejected["data"]["status"] == "rejected"
    db.refresh(agent)
    assert agent.configuration == {"system_prompt": "original"}


def test_runtime_tool_failure_trigger_files_the_pending_candidate(db, monkeypatch):
    from core.auto_dev.event_hooks import TaskEvent
    from core.auto_dev.memento_engine import MementoEngine
    from core.auto_dev.models import SkillCandidate
    from core.auto_dev.reflection_engine import ReflectionEngine
    from core.models import AgentEpisode, EpisodeSegment, Tenant, Workspace

    tenant = Tenant(
        id="tenant-memento", name="Memento Tenant",
        subdomain="memento-runtime")
    workspace = Workspace(
        id="ws-memento", name="Memento Workspace",
        tenant_id=tenant.id,
        metadata_json={"auto_dev": {"enabled": True}},
    )
    db.add_all([tenant, workspace])
    agent = _agent(db)
    agent.configuration = {
        "system_prompt": "original",
        "capability_maturities": {"*": "intern"},
    }
    db.commit()
    episode = AgentEpisode(
        id="episode-runtime-tool-error", agent_id=agent.id,
        tenant_id=tenant.id, workspace_id=workspace.id,
        task_description="look up the customer email",
        maturity_at_time="intern", outcome="failure", success=False,
        status="failed",
        metadata_json={"tool_errors": [{
            "signature": "unknown.tool",
            "error": "400 Syntax error",
        }]},
    )
    db.add(episode)
    db.add(EpisodeSegment(
        episode_id=episode.id, segment_type="error", sequence_order=1,
        content="Tool call: unknown.tool - failed: 400 Syntax error",
    ))
    db.commit()

    llm = MagicMock()
    llm.generate_completion = AsyncMock(
        return_value={"content": "def repair_unknown_tool():\n    return 1"})
    monkeypatch.setattr(
        MementoEngine, "_get_llm_service", lambda self: llm)

    event = TaskEvent(
        episode_id=episode.id, agent_id=agent.id, tenant_id=tenant.id,
        task_description=episode.task_description,
        error_trace="unknown.tool: 400 Syntax error", outcome="failure",
        metadata={"tool_errors": [{
            "signature": "unknown.tool", "error": "400 Syntax error"}]},
    )
    engine = ReflectionEngine(db=db, failure_threshold=1)
    from core.auto_dev.capability_gate import AutoDevCapabilityService
    asyncio.run(engine.process_failure(event))

    candidate = env_candidate = db.query(SkillCandidate).filter(
        SkillCandidate.agent_id == agent.id).first()
    assert candidate is not None, "runtime trigger filed no candidate"
    assert candidate.validation_status == "pending"
    assert candidate.source_episode_id == episode.id
    assert "customer email" in json_text(candidate.failure_pattern)
    db.refresh(agent)
    assert agent.configuration["system_prompt"] == "original"
    assert agent.configuration["capability_maturities"] == {"*": "intern"}

    from api.autodev_review_routes import list_candidates

    listed = asyncio.run(list_candidates(
        agent_id=agent.id, status="pending",
        tenant=SimpleNamespace(id=tenant.id),
        current_user=SimpleNamespace(id="reviewer"), db=db))
    assert listed["data"]["count"] == 1
    assert listed["data"]["candidates"][0]["id"] == str(candidate.id)


def json_text(value):
    import json
    return json.dumps(value or {}, default=str)
