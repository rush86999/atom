"""ORCH-07 controlled-consumer proof for governed fleet-routing audit rows.

The real `AtomMetaAgent.execute` path is exercised against a scratch SQLite
world with a doubled NLU/fleet transport. The audit row must bind the
authenticated execution/tenant/workspace, record the truthful recruitment
snapshot, and receive an exact first-writer outcome join. A shadow recruitment
is not an enforced fleet win; an enforced recruitment summary without specialist
execution is not a successful fleet outcome.
"""
from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.atom_meta_agent as ama
import core.database as cdb
import core.fleet_orchestration.fleet_router_automation as automation
import core.fleet_orchestration.fleet_routing_stats as stats
import core.fleet_routing_config as fleet_config
import core.service_factory as service_factory
from core.atom_meta_agent import AgentTriggerMode, AtomMetaAgent, ReActStep
from core.database import Base
from core.llm.model_provenance import clear_route_attribution, set_served_route
from core.models import (
    AgentExecution,
    FleetRouterAutomationAction,
    FleetRoutingAudit,
    Tenant,
    Workspace,
)

WORKSPACE = "workspace-1"
TENANT = "tenant-1"
REQUEST = "analyze my sales pipeline in detail this quarter"


def _summary(*, chain="chain-controlled", count=2, error=None,
             status="active"):
    return {
        "route": "TASK",
        "handler": "FleetAdmiral",
        "chain_id": chain,
        "specialists_count": count,
        "status": "task_routed",
        "result": {
            "chain_id": chain,
            "specialists_count": count,
            "fleet_status": status,
            "error": error,
            "recruitment_roster": [
                {"agent_id": "a1", "agent_name": "Analyst",
                 "domain": "sales"},
                {"agent_id": "a2", "agent_name": "Reviewer",
                 "domain": "analysis"},
            ][:count],
        },
    }


@pytest.fixture()
def env(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path}/orch07.db",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    seed = Session()
    seed.add_all([
        Tenant(id=TENANT, name="Tenant One", subdomain="tenant-one"),
        Workspace(id=WORKSPACE, name="Workspace One", tenant_id=TENANT),
    ])
    seed.commit()
    seed.close()

    @contextmanager
    def db_session():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    world_model = MagicMock()
    world_model.recall_experiences = AsyncMock(return_value={
        "experiences": [], "knowledge": [], "formulas": [],
        "business_facts": [],
    })
    world_model.record_experience = AsyncMock()
    llm = MagicMock()
    llm.handler = SimpleNamespace(
        _last_used_model="controlled-model",
        _last_used_provider="controlled-provider",
    )
    llm.generate_response = AsyncMock(return_value="react-response")
    mcp = MagicMock()
    mcp.get_all_tools = AsyncMock(return_value=[])
    mcp.call_tool = AsyncMock(return_value="ok")

    monkeypatch.setattr(ama, "SessionLocal", Session)
    monkeypatch.setattr(cdb, "get_db_session", db_session)
    monkeypatch.setattr(ama, "ensure_atom_registry_persisted", lambda db: None)
    monkeypatch.setattr(ama, "WorldModelService", lambda **kw: world_model)
    monkeypatch.setattr(ama, "mcp_service", mcp)
    monkeypatch.setattr(ama, "AdvancedWorkflowOrchestrator", MagicMock)
    monkeypatch.setattr(
        service_factory.ServiceFactory, "get_llm_service",
        lambda **kw: llm)

    from ai.nlp_engine import RouteCategory

    route = MagicMock()
    route.category = RouteCategory.ONE_OFF
    route.reasoning = "controlled one-off task"
    monkeypatch.setattr(
        ama, "NaturalLanguageEngine",
        lambda: MagicMock(classify_route=AsyncMock(return_value=route)))
    monkeypatch.setattr(fleet_config, "fleet_routing_enabled", lambda: True)

    agent = AtomMetaAgent(workspace_id=WORKSPACE, tenant_id=TENANT)
    agent.world_model = world_model
    agent.llm = llm
    agent._get_atom_registry = lambda: SimpleNamespace(status="autonomous")
    agent._react_step = AsyncMock(
        return_value=ReActStep(thought="controlled", final_answer="answer"))
    agent._record_execution = AsyncMock()
    agent.queen = MagicMock()
    agent.queen.generate_blueprint = AsyncMock(return_value={"nodes": []})

    def run(*, enforced=False, summary=None, served=True):
        monkeypatch.setattr(
            automation, "resolved_fleet_enforce",
            lambda db=None: bool(enforced))
        agent.route_with_governance = AsyncMock(
            return_value=summary or _summary())
        clear_route_attribution()
        if served:
            set_served_route("controlled-provider", "controlled-model")
        import asyncio

        return asyncio.run(agent.execute(
            REQUEST, trigger_mode=AgentTriggerMode.MANUAL))

    def rows():
        db = Session()
        try:
            return db.query(FleetRoutingAudit).all()
        finally:
            db.close()

    def row_for(execution_id):
        db = Session()
        try:
            return db.query(FleetRoutingAudit).filter(
                FleetRoutingAudit.execution_id == execution_id).one()
        finally:
            db.close()

    def add_execution(execution_id="exec-manual", tenant=TENANT,
                      workspace=WORKSPACE):
        db = Session()
        try:
            db.add(AgentExecution(
                id=execution_id, agent_id="atom_main", tenant_id=tenant,
                workspace_id=workspace, status="running"))
            db.commit()
        finally:
            db.close()

    yield SimpleNamespace(
        engine=engine, Session=Session, agent=agent, run=run, rows=rows,
        row_for=row_for, add_execution=add_execution,
        monkeypatch=monkeypatch,
    )


def test_shadow_consumer_writes_scoped_decision_and_exact_outcome(env):
    result = env.run(enforced=False)
    execution_id = result["execution_id"]
    assert result["final_output"] == "answer"

    row = env.row_for(execution_id)
    assert row.tenant_id == TENANT
    assert row.workspace_id == WORKSPACE
    assert row.agent_id == "atom_main"
    assert row.chain_id == "chain-controlled"
    assert row.specialists_count == 2
    assert len(row.roster_json) == 2
    assert row.recruitment_succeeded is True
    assert row.enforced is False
    assert row.error is None
    assert row.success is True
    assert row.actual_model == "controlled-model"
    assert row.actual_provider == "controlled-provider"
    assert row.actual_latency_ms is not None

    # Fresh session sees the same joined decision.
    db = env.Session()
    try:
        fresh = db.query(FleetRoutingAudit).filter(
            FleetRoutingAudit.id == row.id).one()
        assert fresh.success is True
        assert fresh.execution_id == execution_id
    finally:
        db.close()


def test_enforced_recruitment_summary_is_not_a_fleet_win(env):
    result = env.run(enforced=True)
    assert result["route"] == "TASK"
    assert result["status"] in ("task_routed", "fleet_recruited")
    row = env.row_for(result["execution_id"])
    assert row.enforced is True
    assert row.success is False
    assert "without specialist execution" in (row.error or "")
    assert row.actual_model is None and row.actual_provider is None


def test_outcome_join_is_exact_idempotent_and_stale_refused(env):
    env.add_execution("exec-manual")
    audit_id = stats.record_fleet_decision(
        execution_id="exec-manual", tenant_id=TENANT,
        workspace_id=WORKSPACE, agent_id="atom_main", request=REQUEST,
        chain_id="chain-manual", specialists_count=1,
        roster=[{"agent_id": "a1", "agent_name": "A", "domain": "sales"}],
        recruitment_succeeded=True, enforced=False)
    assert audit_id

    first = stats.record_fleet_execution_outcome(
        "exec-manual", True, actual_model="m", actual_provider="p",
        audit_id=audit_id, tenant_id=TENANT, workspace_id=WORKSPACE)
    assert first["status"] == "applied"
    duplicate = stats.record_fleet_execution_outcome(
        "exec-manual", True, audit_id=audit_id, tenant_id=TENANT,
        workspace_id=WORKSPACE)
    assert duplicate["status"] == "already_applied"
    stale = stats.record_fleet_execution_outcome(
        "exec-manual", False, audit_id=audit_id, tenant_id=TENANT,
        workspace_id=WORKSPACE)
    assert stale["status"] == "conflict"

    db = env.Session()
    try:
        row = db.query(FleetRoutingAudit).filter(
            FleetRoutingAudit.id == audit_id).one()
        assert row.success is True
        assert row.actual_model == "m"
        assert row.actual_provider == "p"
    finally:
        db.close()

    # A different execution's audit row cannot be completed by this join.
    env.add_execution("exec-other")
    other_id = stats.record_fleet_decision(
        execution_id="exec-other", tenant_id=TENANT,
        workspace_id=WORKSPACE, request=REQUEST,
        recruitment_succeeded=True, enforced=False)
    wrong = stats.record_fleet_execution_outcome(
        "exec-manual", True, audit_id=other_id, tenant_id=TENANT,
        workspace_id=WORKSPACE)
    assert wrong["status"] == "conflict"
    db = env.Session()
    try:
        assert db.query(FleetRoutingAudit).filter(
            FleetRoutingAudit.id == other_id).one().success is None
    finally:
        db.close()


def test_scope_conflict_and_missing_execution_do_not_default(env):
    env.add_execution("exec-scope")
    conflict_id = stats.record_fleet_decision(
        execution_id="exec-scope", tenant_id="tenant-2",
        workspace_id="workspace-2", agent_id="atom_main", request=REQUEST,
        recruitment_succeeded=True, enforced=False)
    db = env.Session()
    try:
        row = db.query(FleetRoutingAudit).filter(
            FleetRoutingAudit.id == conflict_id).one()
        assert row.tenant_id == TENANT
        assert row.workspace_id == WORKSPACE
        assert row.decision_source == "scope_conflict"
        assert "conflicted" in (row.error or "")
    finally:
        db.close()

    missing_id = stats.record_fleet_decision(
        execution_id="exec-missing", tenant_id=TENANT,
        workspace_id=WORKSPACE, request=REQUEST,
        recruitment_succeeded=True, enforced=False)
    db = env.Session()
    try:
        missing = db.query(FleetRoutingAudit).filter(
            FleetRoutingAudit.id == missing_id).one()
        assert missing.decision_source == "scope_unverified"
        assert "unavailable" in (missing.error or "")
        assert missing.success is None
    finally:
        db.close()
    join = stats.record_fleet_execution_outcome(
        "exec-missing", True, audit_id=missing_id)
    assert join["status"] == "scope_unavailable"


def test_calibration_excludes_pending_and_scope_unverified(env):
    env.add_execution("exec-cal")
    pending_id = stats.record_fleet_decision(
        execution_id="exec-cal", tenant_id=TENANT,
        workspace_id=WORKSPACE, request=REQUEST,
        recruitment_succeeded=True, enforced=False)
    # pending_id has success=None; a scope-unverified row also has success=None.
    stats.record_fleet_decision(
        execution_id="exec-missing", tenant_id=TENANT,
        workspace_id=WORKSPACE, request=REQUEST,
        recruitment_succeeded=True, enforced=False)
    db = env.Session()
    try:
        db.add(FleetRoutingAudit(
            tenant_id=TENANT, workspace_id=WORKSPACE,
            workload_key=stats.workload_key_for(REQUEST),
            request_text=REQUEST[:200], chain_id="chain-shadow",
            specialists_count=1, roster_json=[], recruitment_succeeded=True,
            enforced=False, decision_source="fleet_eligible", success=True))
        db.add(FleetRoutingAudit(
            tenant_id=TENANT, workspace_id=WORKSPACE,
            workload_key=stats.workload_key_for(REQUEST),
            request_text=REQUEST[:200], chain_id="chain-enforced",
            specialists_count=1, roster_json=[], recruitment_succeeded=True,
            enforced=True, decision_source="fleet_eligible", success=False,
            error="fleet recruitment summary returned without specialist execution"))
        db.commit()
        workloads = stats._workload_stats(db)
        wk = workloads[stats.workload_key_for(REQUEST)]
        assert wk["n"] == 2
        assert wk["enforced_n"] == 1
        assert wk["shadow_n"] == 1
    finally:
        db.close()

    env.monkeypatch.setattr(
        automation, "resolved_fleet_enforce", lambda db=None: False)
    status = stats.fleet_calibration_status()
    assert status["phase"] == "collecting"
    assert status["counts"]["outcome_joined"] == 2
    assert status["enforced"] is False


def test_shadow_only_healthy_data_queues_consent_not_silent_enforce(env):
    db = env.Session()
    try:
        for i in range(40):
            db.add(FleetRoutingAudit(
                tenant_id=TENANT, workspace_id=WORKSPACE,
                workload_key=stats.workload_key_for(REQUEST),
                request_text=REQUEST[:200], chain_id=f"chain-{i}",
                specialists_count=1, roster_json=[],
                recruitment_succeeded=True, enforced=False,
                decision_source="fleet_eligible", success=True))
        db.commit()
    finally:
        db.close()

    env.monkeypatch.setattr(automation, "_mode", "approve")
    env.monkeypatch.setattr(automation, "_spawn_notification",
                            lambda *a, **k: None)
    result = automation.run_auto_certification()
    assert result.get("certified") == []
    assert result.get("queued") == ["__global__"]
    db = env.Session()
    try:
        actions = db.query(FleetRouterAutomationAction).all()
        assert len(actions) == 1
        assert actions[0].state == "approval"
        assert actions[0].verdict == "enable"
    finally:
        db.close()


def test_attempted_route_is_not_reported_as_served(env):
    env.agent.llm.handler._last_used_model = None
    env.agent.llm.handler._last_used_provider = None
    result = env.run(enforced=False, served=False)
    row = env.row_for(result["execution_id"])
    assert row.success is True
    assert row.actual_model is None
    assert row.actual_provider is None
