"""MEM-07: a real tool failure feeds the ONE canonical Memento lifecycle.

The generic-agent hook records a structured signal on the running execution;
episode finalization merges it, downgrades a nominal success to partial and
emits the TaskEvent that ReflectionEngine consumes. The result is a pending
SkillCandidate reviewed through the existing Auto-Dev API — not a second
HITL candidate store, and never an agent configuration change.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict, deque
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


def _scope_rows(env, *, auto_dev_enabled, maturity=None):
    """Scratch tenant/workspace/agent/execution for one controlled scope.

    ``auto_dev_enabled=False`` is the served-default (flag-disabled) world:
    nothing in the workspace metadata opts the agents into Auto-Dev."""
    config = {
        "system_prompt": "original",
        "capability_maturities": {"*": "intern"},
    }
    if maturity:
        config["capability_maturities"][maturity[0]] = maturity[1]
    tenant = Tenant(
        id=f"tenant-scope-{auto_dev_enabled}",
        name=f"Scope Tenant {auto_dev_enabled}",
        subdomain=f"scope-{auto_dev_enabled}")
    workspace = Workspace(
        id=f"ws-scope-{auto_dev_enabled}",
        name=f"Scope Workspace {auto_dev_enabled}",
        tenant_id=tenant.id,
        metadata_json={"auto_dev": {"enabled": True}} if auto_dev_enabled
        else {},
    )
    agent = AgentRegistry(
        id=f"agent-scope-{auto_dev_enabled}",
        name=f"Scope Employee {auto_dev_enabled}",
        category="operations", module_path="core.generic_agent",
        class_name="GenericAgent", status="intern", confidence_score=0.5,
        configuration=config, capabilities=[],
        workspace_id=workspace.id, tenant_id=tenant.id,
    )
    execution = AgentExecution(
        id=f"exec-scope-{auto_dev_enabled}", agent_id=agent.id,
        tenant_id=tenant.id, workspace_id=workspace.id,
        status="running", metadata_json={},
    )
    env["db"].add_all([tenant, workspace, agent, execution])
    env["db"].commit()
    return {
        "tenant": tenant, "workspace": workspace,
        "agent": agent, "execution": execution, "config": config,
    }


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


# ─────────────────────────────────────────────────────────────────────────────
# MEM-07 disabled / opt-in cases — the refusal boundary on the REAL gate
# ─────────────────────────────────────────────────────────────────────────────


def _counting_llm_double(monkeypatch, calls):
    """Model-transport double: never touches a provider; only counts."""
    llm = MagicMock()
    llm.generate_completion = AsyncMock(
        side_effect=lambda **kw: calls.append(kw) or {"content": "# no-op"})
    return llm


def test_disabled_workspace_refuses_the_candidate(env, monkeypatch):
    """Refusal case: with Auto-Dev NOT enabled on the workspace (the served
    default behind ATOM_AGENT_EVOLUTION_ENABLED=false), a real tool error is
    still OBSERVED — the durable signal on the execution, episode downgraded
    to partial — but the candidate creation is refused at the REAL workspace
    gate: no SkillCandidate, no proposal LLM call, configuration untouched.
    The gate is not mocked; only the LLM transport is doubled."""
    from core.auto_dev.event_hooks import TaskEvent
    from core.auto_dev.memento_engine import MementoEngine
    from core.auto_dev.reflection_engine import ReflectionEngine
    from core.auto_dev.models import SkillCandidate
    from core.episode_service import EpisodeService

    rows = _scope_rows(env, auto_dev_enabled=False)
    agent = GenericAgent_for_scope(env, rows)
    context = {
        "execution_id": rows["execution"].id,
        "tenant_id": rows["tenant"].id,
        "run_id": "run-disabled",
        "operation_id": "op-disabled",
    }
    for _ in range(2):
        result = asyncio.run(agent._step_act("unknown.tool", {}, context))
        assert "Error" in result

    db = env["db"]
    db.expire_all()
    execution = db.query(AgentExecution).filter(
        AgentExecution.id == rows["execution"].id).one()
    assert execution.metadata_json["tool_errors"]  # observed, not swallowed
    episode = asyncio.run(EpisodeService(db).create_episode_from_execution(
        rows["execution"].id, "look up the customer email",
        outcome="success", success=True, metadata={}))
    assert episode.outcome == "partial"

    llm_calls: list = []
    monkeypatch.setattr(
        MementoEngine, "_get_llm_service",
        lambda self: _counting_llm_double(monkeypatch, llm_calls))
    event = TaskEvent(
        episode_id=episode.id, agent_id=rows["agent"].id,
        tenant_id=rows["tenant"].id,
        task_description=episode.task_description,
        error_trace="unknown.tool: 400 Syntax error",
        outcome=episode.outcome, metadata=episode.metadata_json,
    )
    # The REAL gate runs inside process_failure — _should_process_agent is
    # NOT patched here.
    asyncio.run(ReflectionEngine(
        db=db, failure_threshold=1).process_failure(event))

    assert llm_calls == []
    assert db.query(SkillCandidate).filter(
        SkillCandidate.agent_id == rows["agent"].id).count() == 0
    db.expire_all()
    assert rows["agent"].configuration["system_prompt"] == "original"
    # Durable absence: a NEW session also sees no candidate rows.
    fresh = env["factory"]()
    try:
        assert fresh.query(SkillCandidate).filter(
            SkillCandidate.agent_id == rows["agent"].id).count() == 0
    finally:
        fresh.close()


def _fresh_error_ring(monkeypatch):
    """Isolate the in-process tool-error ring so reservation tests do not
    inherit repeats from other tests."""
    from core.auto_dev import tool_error_signals as tes

    monkeypatch.setattr(
        tes, "_RECENT_ERRORS", defaultdict(lambda: deque(maxlen=32)))
    monkeypatch.setattr(tes, "_LIVE_TRIGGERED", {})


def _registered_tool(monkeypatch, name="outlook.search_emails"):
    """Register a REAL inspectable Python tool on the action registry."""
    import core.action_registry as ar_mod

    def search_emails(_args, _context):  # pragma: no cover
        return "source"

    fake_registry = SimpleNamespace(
        get_action=lambda n: SimpleNamespace(handler=search_emails)
        if n == name else None)
    monkeypatch.setattr(ar_mod, "action_registry", fake_registry)
    return search_emails


def _failing_loop_service(monkeypatch):
    import integrations.universal_integration_service as uis_mod

    svc = uis_mod.UniversalIntegrationService(workspace_id="ws-scope")
    svc._dispatch_execution = AsyncMock(
        return_value={"status": "error", "error": "400 Syntax error: '@'"})
    return svc


def _drive_chokepoint_errors(svc, agent_id, tenant_id):
    """Run the production-quality error path twice through the REAL
    integration chokepoint and let the scheduled live trigger task run."""

    async def run():
        for _ in range(2):
            await svc.execute(
                "outlook", "search_emails", {"query": "x"},
                {"user_id": "reviewer", "agent_id": agent_id,
                 "tenant_id": tenant_id},
            )
        await asyncio.sleep(0.05)

    asyncio.run(run())


def test_live_tool_fix_refuses_when_not_opted_in(env, monkeypatch):
    """The REAL-TIME path (integration chokepoint → live trigger) must obey
    the same Auto-Dev opt-in gate as the episode-time path. In the
    disabled default world a repeated REAL tool error must NOT propose a
    tool mutation; the signal is recorded on the running execution.
    LLM transport doubled — nothing reaches a provider either way."""
    from core.auto_dev import tool_error_signals as tes
    from core.auto_dev.alpha_evolver_engine import AlphaEvolverEngine
    from core.auto_dev.models import ToolMutation

    _fresh_error_ring(monkeypatch)
    _registered_tool(monkeypatch)
    llm_calls: list = []
    monkeypatch.setattr(
        AlphaEvolverEngine, "_get_llm_service",
        lambda self: _counting_llm_double(monkeypatch, llm_calls))

    rows = _scope_rows(env, auto_dev_enabled=False)
    svc = _failing_loop_service(monkeypatch)
    _drive_chokepoint_errors(svc, rows["agent"].id, rows["tenant"].id)

    env["db"].expire_all()
    assert env["db"].query(ToolMutation).filter(
        ToolMutation.tenant_id == rows["tenant"].id).count() == 0
    assert llm_calls == []


def test_live_tool_fix_proposes_pending_mutation_when_opted_in(env, monkeypatch):
    """Positive control on the LIVE path: WITH the workspace opt-in and a
    supervised agent, the same real chokepoint errors DO file one PENDING
    ToolMutation through the real proposal persistence, visible on the
    existing authenticated review route — and the agent configuration is
    still untouched while it awaits human approval."""
    from types import SimpleNamespace as NS

    from api.autodev_review_routes import list_candidates
    from core.auto_dev import tool_error_signals as tes
    from core.auto_dev.alpha_evolver_engine import AlphaEvolverEngine
    from core.auto_dev.models import ToolMutation

    _fresh_error_ring(monkeypatch)
    _registered_tool(monkeypatch)
    llm_calls: list = []
    monkeypatch.setattr(
        AlphaEvolverEngine, "_get_llm_service",
        lambda self: _counting_llm_double(monkeypatch, llm_calls))

    rows = _scope_rows(
        env, auto_dev_enabled=True,
        maturity=("auto_dev.alpha_evolver", "supervised"))
    svc = _failing_loop_service(monkeypatch)
    _drive_chokepoint_errors(svc, rows["agent"].id, rows["tenant"].id)

    db = env["db"]
    db.expire_all()
    mutation = db.query(ToolMutation).filter(
        ToolMutation.tenant_id == rows["tenant"].id).one()
    assert mutation.sandbox_status == "pending"
    assert mutation.tool_name == "outlook.search_emails"
    assert llm_calls, "opted-in live fix proposes via the LLM transport"

    listed = asyncio.run(list_candidates(
        agent_id=rows["agent"].id, status="pending",
        tenant=NS(id=rows["tenant"].id),
        current_user=NS(id="reviewer"), db=db))
    assert listed["data"]["count"] == 1
    assert listed["data"]["candidates"][0]["kind"] == "mutation"

    db.expire_all()
    assert rows["agent"].configuration["system_prompt"] == "original"


def GenericAgent_for_scope(env, rows):
    from core.generic_agent import GenericAgent

    agent = GenericAgent(rows["agent"], workspace_id=rows["workspace"].id)

    def boom(_args, _context):
        raise RuntimeError("400 Syntax error on the customer email search")

    agent._custom_actions = {"unknown.tool": boom}
    return agent
