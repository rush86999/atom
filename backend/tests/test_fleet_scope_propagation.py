"""Defensive scope propagation through meta-agent governance and recruitment.

Review findings locked here:

1. The meta-agent's routing governance used to construct
   ``AgentGovernanceService(db)`` with the default scope, so an authenticated
   caller in a NON-DEFAULT workspace could not see its own agents
   (``Agent not found``) — a fail-closed but wrong deny. The authenticated
   workspace/tenant must be forwarded.
2. Recruitment's governance/matching/analytics graph must receive the same
   scope. Analytics history is keyed by the account (tenant), never by the
   acting user id.
3. ``RecruitmentAnalyticsService.record_recruitment_decision`` merged
   telemetry metadata LAST, so a model-supplied ``tenant_id``/``chain_id``
   could override server-owned identity.
4. ``FleetAnalyticsService`` must reuse ``core.sql_json.json_field_equals``
   instead of an ad-hoc SQLite/Postgres branch (malformed-JSON safe, portable).

Everything runs on a per-test scratch SQLite file with controlled LLM output.
No live app, provider, integration, deployment or network call is used.
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from core.agent_governance_service import AgentGovernanceService
from core.database import Base
from core.fleet_admiral import FleetAdmiral, TaskAnalysis
from core.models import (
    AgentRegistry,
    AgentStatus,
    ChainLink,
    DelegationChain,
    Tenant,
    Workspace,
)
from core.recruitment_analytics_service import RecruitmentAnalyticsService
from core.recruitment_intelligence_service import (
    RecruitmentIntelligenceService,
    RecruitmentPlan,
)
from core.specialist_matcher import SpecialistMatcher
from analytics.fleet_analytics_service import FleetAnalyticsService

import core.atom_meta_agent as ama


TENANT = "tenant-ops"
WORKSPACE = "ws-ops"
OTHER_TENANT = "tenant-other"
OTHER_WORKSPACE = "ws-other"
USER = "user-ops"


@pytest.fixture()
def scratch(tmp_path):
    """Isolated SQLite file (never the live dev DB)."""
    db_path = tmp_path / "scope.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        db.add_all([
            Tenant(id=TENANT, name="Ops", subdomain="ops"),
            Tenant(id=OTHER_TENANT, name="Other", subdomain="other"),
            Workspace(id=WORKSPACE, name="Ops", tenant_id=TENANT),
            Workspace(id=OTHER_WORKSPACE, name="Other", tenant_id=OTHER_TENANT),
        ])
        db.add_all([
            AgentRegistry(
                id="ops-1", name="Ops Specialist", display_name="Ops Specialist",
                category="operations", module_path="core.generic_agent",
                class_name="GenericAgent", tenant_id=TENANT,
                workspace_id=WORKSPACE, status=AgentStatus.AUTONOMOUS.value,
                enabled=True, capabilities=["operations"],
                specialty="operations", user_id=USER),
            # A stronger-scoring foreign agent: recruitment must not even
            # consider it for the non-default workspace (scope isolation).
            AgentRegistry(
                id="foreign-1", name="Foreign Ops", display_name="Foreign Ops",
                category="operations", module_path="core.generic_agent",
                class_name="GenericAgent", tenant_id=OTHER_TENANT,
                workspace_id=OTHER_WORKSPACE,
                status=AgentStatus.AUTONOMOUS.value, enabled=True,
                capabilities=["operations", "logistics", "supply", "inventory"],
                specialty="operations", user_id="foreign-user"),
            AgentRegistry(
                id="student-1", name="Student Ops", display_name="Student Ops",
                category="operations", module_path="core.generic_agent",
                class_name="GenericAgent", tenant_id=TENANT,
                workspace_id=WORKSPACE, status=AgentStatus.STUDENT.value,
                enabled=True, capabilities=["operations"],
                specialty="operations", user_id=USER),
        ])
        db.commit()
    try:
        yield engine, Session
    finally:
        engine.dispose()


def _plan() -> RecruitmentPlan:
    return RecruitmentPlan(
        goal_analysis="office-work checklist",
        required_domains=["operations"],
        domain_rationale={"operations": "draft the checklist"},
        complexity_estimate="medium",
        estimated_parallelizable=False,
        suggested_specialist_count=1,
    )


# ---------------------------------------------------------------------------
# 1. Authorized non-default workspace: governance sees its own agent.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_meta_agent_governance_forwards_non_default_workspace(
        scratch, monkeypatch):
    _engine, Session = scratch
    monkeypatch.setattr(ama, "SessionLocal", Session)

    owner = SimpleNamespace(workspace_id=WORKSPACE, tenant_id=TENANT)
    allowed, reason = await ama.AtomMetaAgent._check_governance(
        owner, USER, "ops-1", "task")
    assert allowed is True, reason

    # The same call WITHOUT the authenticated scope is the old failure mode:
    # the default scope cannot see a non-default workspace agent.
    default_scope = AgentGovernanceService(Session())
    try:
        denied = await default_scope.can_perform_action_async(
            "ops-1", "route_to_task")
        assert denied["allowed"] is False
        assert denied["reason"] == "Agent not found"
    finally:
        default_scope.db.close()


@pytest.mark.asyncio
async def test_meta_agent_governance_denies_foreign_workspace(scratch, monkeypatch):
    _engine, Session = scratch
    monkeypatch.setattr(ama, "SessionLocal", Session)

    owner = SimpleNamespace(workspace_id=WORKSPACE, tenant_id=TENANT)
    allowed, reason = await ama.AtomMetaAgent._check_governance(
        owner, USER, "foreign-1", "task")
    assert allowed is False
    assert reason == "Agent not found"


@pytest.mark.asyncio
async def test_meta_agent_governance_keeps_normal_maturity_deny(scratch, monkeypatch):
    _engine, Session = scratch
    monkeypatch.setattr(ama, "SessionLocal", Session)

    owner = SimpleNamespace(workspace_id=WORKSPACE, tenant_id=TENANT)
    allowed, reason = await ama.AtomMetaAgent._check_governance(
        owner, USER, "student-1", "task")
    assert allowed is False
    assert "Maturity check failed" in (reason or "")


# ---------------------------------------------------------------------------
# 2. Recruitment propagates scope and uses the ACTUAL tenant for analytics.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_recruitment_uses_workspace_scope_and_actual_tenant(scratch):
    _engine, Session = scratch
    db = Session()
    try:
        llm = MagicMock()
        llm.generate_structured_response = AsyncMock(return_value=_plan())
        analytics = MagicMock()
        optimizer = MagicMock()
        optimizer.get_optimization_parameters = MagicMock(
            return_value={"model": "auto"})
        svc = RecruitmentIntelligenceService(
            db=db,
            llm=llm,
            specialist_matcher=SpecialistMatcher(db),
            analytics=analytics,
            fleet_service=MagicMock(),
            optimizer=optimizer,
            governance=AgentGovernanceService(
                db, workspace_id=WORKSPACE, tenant_id=TENANT),
            workspace_id=WORKSPACE,
            tenant_id=TENANT,
        )

        result = await svc.orchestrate_recruitment(
            goal="Draft an operations checklist",
            user_id=USER,
            context={},
            chain_id="chain-ops",
        )

        assert result["success"] is True, result
        assert [item["agent_id"] for item in result["recruitment_roster"]] == [
            "ops-1"]

        # Analytics/optimization key on the account, not the acting user.
        optimizer.get_optimization_parameters.assert_called_once()
        assert optimizer.get_optimization_parameters.call_args.kwargs[
            "tenant_id"] == TENANT

        analytics.record_recruitment_decision.assert_called_once()
        recorded = analytics.record_recruitment_decision.call_args.kwargs
        assert recorded["tenant_id"] == TENANT
        assert recorded["workspace_id"] == WORKSPACE
        assert recorded["user_id"] == USER
        assert recorded["chain_id"] == "chain-ops"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_recruitment_default_scope_still_admits_null_workspace_agents(
        scratch):
    """Personal-Edition parity: default scope keeps NULL-workspace hires."""
    _engine, Session = scratch
    db = Session()
    try:
        db.add(AgentRegistry(
            id="legacy-1", name="Legacy Ops", display_name="Legacy Ops",
            category="operations", module_path="core.generic_agent",
            class_name="GenericAgent", tenant_id="default",
            workspace_id=None, status=AgentStatus.AUTONOMOUS.value,
            enabled=True, capabilities=["operations"],
            specialty="operations", user_id=USER))
        db.commit()

        llm = MagicMock()
        llm.generate_structured_response = AsyncMock(return_value=_plan())
        svc = RecruitmentIntelligenceService(
            db=db,
            llm=llm,
            specialist_matcher=SpecialistMatcher(db),
            analytics=MagicMock(),
            fleet_service=MagicMock(),
            optimizer=MagicMock(),
            governance=AgentGovernanceService(
                db, workspace_id="default", tenant_id="default"),
            workspace_id="default",
            tenant_id="default",
        )
        result = await svc.orchestrate_recruitment(
            goal="Draft an operations checklist", user_id=USER, context={})
        assert result["success"] is True, result
        ids = [item["agent_id"] for item in result["recruitment_roster"]]
        assert "legacy-1" in ids
        assert "foreign-1" not in ids
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 3. FleetAdmiral forwards the authenticated scope into recruitment.
# ---------------------------------------------------------------------------
def test_fleet_admiral_builds_scoped_recruitment_graph(scratch):
    _engine, Session = scratch
    db = Session()
    try:
        admiral = FleetAdmiral(db, MagicMock())
        with patch("core.fleet_admiral.RecruitmentIntelligenceService") as ris, \
                patch("core.agent_governance_service.AgentGovernanceService") as gov:
            admiral._initialize_recruitment_intelligence(
                workspace_id=WORKSPACE, tenant_id=TENANT)

        kwargs = ris.call_args.kwargs
        assert kwargs["workspace_id"] == WORKSPACE
        assert kwargs["tenant_id"] == TENANT
        gov.assert_called_once_with(
            db, workspace_id=WORKSPACE, tenant_id=TENANT)
    finally:
        db.close()


@pytest.mark.asyncio
async def test_fleet_admiral_recruits_in_non_default_workspace(scratch):
    """End-to-end recruitment on a non-default workspace, real services."""
    _engine, Session = scratch
    db = Session()
    try:
        async def structured(**kwargs):
            model = kwargs.get("response_model")
            if model is TaskAnalysis:
                return TaskAnalysis(
                    complexity="medium",
                    required_capabilities=["operations"],
                    estimated_duration="30 minutes",
                    specialist_count=1,
                    reasoning="one operations specialist",
                )
            if model is RecruitmentPlan:
                return _plan()
            raise AssertionError(f"unexpected response_model {model!r}")

        llm = MagicMock()
        llm.generate_structured_response = AsyncMock(side_effect=structured)
        admiral = FleetAdmiral(db, llm)

        result = await admiral.recruit_and_execute(
            task="Draft an operations checklist for the office cabinet",
            user_id=USER,
            tenant_id=TENANT,
            workspace_id=WORKSPACE,
        )

        assert result["fleet_status"] != "failed", result
        assert result["specialists_count"] == 1
        assert result["recruitment_roster"][0]["agent_id"] == "ops-1"
        assert result["recruitment_roster"][0]["domain"] == "operations"

        chain = db.query(DelegationChain).filter(
            DelegationChain.id == result["chain_id"]).one()
        assert chain.tenant_id == TENANT
        assert chain.metadata_json["workspace_id"] == WORKSPACE
        links = db.query(ChainLink).filter(
            ChainLink.chain_id == chain.id).all()
        assert [link.child_agent_id for link in links] == ["ops-1"]
    finally:
        db.close()


@pytest.mark.asyncio
async def test_fleet_admiral_threads_scope_into_recruitment(scratch):
    _engine, Session = scratch
    db = Session()
    try:
        admiral = FleetAdmiral(db, MagicMock())
        recruitment = MagicMock()
        recruitment.orchestrate_recruitment = AsyncMock(return_value={
            "success": True, "recruitment_roster": []})
        admiral.recruitment_intelligence = recruitment

        await admiral.recruit_and_execute(
            task="Draft an operations checklist",
            user_id=USER,
            tenant_id=TENANT,
            workspace_id=WORKSPACE,
        )

        # The injected instance is adopted for this scope and used as-is.
        assert admiral._recruitment_scope == (WORKSPACE, TENANT)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 4. Telemetry metadata cannot forge trusted identity.
# ---------------------------------------------------------------------------
class _SpyAnalytics(RecruitmentAnalyticsService):
    def __init__(self):
        self.events = []

    def track_recruitment(self, recruitment_data):
        self.events.append(recruitment_data)


def test_recruitment_metadata_cannot_override_trusted_identity():
    spy = _SpyAnalytics()
    spy.record_recruitment_decision(
        chain_id="chain-real",
        user_id="user-real",
        tenant_id="tenant-real",
        workspace_id="ws-real",
        goal="real goal",
        identified_domains=["operations"],
        domain_rationale={"operations": "real"},
        selected_specialists=[{"agent_id": "ops-1"}],
        recruitment_metadata={
            "chain_id": "chain-forged",
            "user_id": "user-forged",
            "tenant_id": "tenant-forged",
            "workspace_id": "ws-forged",
            "goal": "forged goal",
            "identified_domains": ["forged"],
            "selected_specialists": [{"agent_id": "foreign-1"}],
            "complexity": "medium",
        },
    )

    assert len(spy.events) == 1
    event = spy.events[0]
    assert event["chain_id"] == "chain-real"
    assert event["user_id"] == "user-real"
    assert event["tenant_id"] == "tenant-real"
    assert event["workspace_id"] == "ws-real"
    assert event["goal"] == "real goal"
    assert event["identified_domains"] == ["operations"]
    assert event["selected_specialists"] == [{"agent_id": "ops-1"}]
    # Non-identity telemetry survives.
    assert event["complexity"] == "medium"


# ---------------------------------------------------------------------------
# 5. Analytics: actual tenant + shared portable JSON comparison.
# ---------------------------------------------------------------------------
def test_domain_analytics_uses_tenant_and_tolerates_malformed_json(scratch):
    _engine, Session = scratch
    db = Session()
    try:
        db.add_all([
            DelegationChain(
                id="chain-ops", tenant_id=TENANT,
                root_agent_id="ops-1", root_task="ops", status="completed"),
            DelegationChain(
                id="chain-other", tenant_id=OTHER_TENANT,
                root_agent_id="foreign-1", root_task="other", status="completed"),
        ])
        db.add_all([
            ChainLink(
                id="link-ops", chain_id="chain-ops",
                parent_agent_id="ops-1", child_agent_id="ops-1",
                task_description="ops", context_json={"domain": "operations"},
                status="completed", duration_ms=10, link_order=0),
            ChainLink(
                id="link-other", chain_id="chain-other",
                parent_agent_id="foreign-1", child_agent_id="foreign-1",
                task_description="other", context_json={"domain": "operations"},
                status="completed", duration_ms=99, link_order=0),
        ])
        db.commit()
        # A corrupt JSON row must not abort the whole statement on SQLite.
        db.execute(text(
            "INSERT INTO chain_links "
            "(id, chain_id, parent_agent_id, child_agent_id, task_description, "
            " context_json, status, started_at, link_order) "
            "VALUES ('link-bad', 'chain-ops', 'ops-1', 'ops-1', 'bad', "
            "        '{{not-json', 'completed', CURRENT_TIMESTAMP, 1)"))
        db.commit()

        stats = FleetAnalyticsService(db).get_domain_performance_stats(
            TENANT, "operations")
        assert stats["total_interactions"] == 1
        assert stats["success_rate"] == 1.0
        assert stats["avg_duration_ms"] == 10.0
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 6. Global root registry identity: narrow routing admission, caller scope kept
#    for policy/budget. (Review hold 2026-11-11.)
# ---------------------------------------------------------------------------
def _add_global_root(db, agent_id: str = "atom_main") -> None:
    db.add(AgentRegistry(
        id=agent_id,
        name="Atom" if agent_id == "atom_main" else agent_id,
        display_name="Atom",
        category="system",
        module_path="core.atom_meta_agent",
        class_name="AtomMetaAgent",
        tenant_id=None,
        workspace_id=None,
        status=AgentStatus.AUTONOMOUS.value,
        enabled=True,
        capabilities=[],
        specialty="system",
        user_id=None,
        confidence_score=1.0,
    ))
    db.commit()


def test_global_root_budget_keeps_authenticated_tenant(scratch):
    """The root lookup exception must not erase the caller's budget account."""
    _engine, Session = scratch
    db = Session()
    try:
        _add_global_root(db)
        governance = AgentGovernanceService(
            db, workspace_id=WORKSPACE, tenant_id=TENANT)

        # Without the narrow global-root admission the non-default workspace
        # cannot see the installation's global atom_main row at all.
        denied = governance._budget_scope("atom_main")
        assert denied["allowed"] is False
        assert "unavailable" in denied["reason"]

        # With it, the row resolves but the budget stays on the AUTHENTICATED
        # tenant rather than collapsing to the root row's NULL account.
        scope = governance._budget_scope(
            "atom_main", include_global_agent_id="atom_main")
        assert scope == {"tenant_id": TENANT}
    finally:
        db.close()


@pytest.mark.asyncio
async def test_meta_agent_governance_admits_only_global_root(scratch, monkeypatch):
    _engine, Session = scratch
    monkeypatch.setattr(ama, "SessionLocal", Session)
    db = Session()
    try:
        _add_global_root(db)
        _add_global_root(db, "global_not_root")
    finally:
        db.close()

    owner = SimpleNamespace(workspace_id=WORKSPACE, tenant_id=TENANT)
    allowed, reason = await ama.AtomMetaAgent._check_governance(
        owner, USER, "atom_main", "task")
    assert allowed is True, reason

    # Another global (NULL-workspace) row is NOT admitted: the exception is
    # only the installation's own meta-agent identity.
    denied, denial = await ama.AtomMetaAgent._check_governance(
        owner, USER, "global_not_root", "task")
    assert denied is False
    assert denial == "Agent not found"


# ---------------------------------------------------------------------------
# 7. Recruitment authorizes the SELECTED specialist, not every runner-up.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_recruitment_authorizes_selected_specialist_not_runner_up(scratch):
    _engine, Session = scratch
    db = Session()
    try:
        llm = MagicMock()
        llm.generate_structured_response = AsyncMock(return_value=_plan())
        matcher = MagicMock()
        matcher.get_all_available_domains = MagicMock(
            return_value=["operations"])
        matcher.find_specialists_for_domains = MagicMock(return_value={
            "operations": [
                {"agent_id": "ops-1", "name": "Ops Specialist",
                 "capability_score": 0.9},
                # Runner-up would be DENIED. It is not selected, so its
                # governance outcome must not block the selected specialist.
                {"agent_id": "student-1", "name": "Student Ops",
                 "capability_score": 0.8},
            ]
        })
        governance = MagicMock()

        async def decide(agent_id, action_type):
            return {"allowed": agent_id == "ops-1", "reason": "denied"}

        governance.can_perform_action_async = AsyncMock(side_effect=decide)
        optimizer = MagicMock()
        optimizer.get_optimization_parameters = MagicMock(return_value={})

        svc = RecruitmentIntelligenceService(
            db=db,
            llm=llm,
            specialist_matcher=matcher,
            analytics=MagicMock(),
            fleet_service=MagicMock(),
            optimizer=optimizer,
            governance=governance,
            workspace_id=WORKSPACE,
            tenant_id=TENANT,
        )
        result = await svc.orchestrate_recruitment(
            goal="Draft an operations checklist", user_id=USER, context={})

        assert result["success"] is True, result
        assert [item["agent_id"] for item in result["recruitment_roster"]] == [
            "ops-1"]
        # Only the authorized selection was ever checked.
        assert [
            call.args[0]
            for call in governance.can_perform_action_async.await_args_list
        ] == ["ops-1"]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 8. Chat fleet scope is the server-published turn scope, never request.context.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_chat_fleet_scope_ignores_request_supplied_scope(monkeypatch):
    from core.request_scope import reset_request_scope, set_request_scope
    from integrations.chat_orchestrator import ChatOrchestrator

    orchestrator = object.__new__(ChatOrchestrator)
    orchestrator._emit_agent_step = AsyncMock()
    orchestrator._emit_agent_status = AsyncMock()

    atom = MagicMock()
    atom.execute = AsyncMock(
        return_value={"final_output": "ok", "execution_id": "exec-1"})
    scoped_factory = MagicMock(return_value=atom)
    default_factory = MagicMock()
    fake_module = types.ModuleType("core.atom_meta_agent")
    fake_module.AgentTriggerMode = SimpleNamespace(MANUAL="manual")
    fake_module.get_atom_agent = default_factory
    fake_module.get_scoped_atom_agent = scoped_factory
    monkeypatch.setitem(sys.modules, "core.atom_meta_agent", fake_module)

    context = {
        # Client-supplied values that must NOT choose the durable scope.
        "workspace_id": OTHER_WORKSPACE,
        "tenant_id": OTHER_TENANT,
    }
    # Server-bound authority: process_chat_message publishes this from the
    # authenticated User row for the turn's lifetime.
    token = set_request_scope(WORKSPACE, TENANT)
    try:
        result = await orchestrator._handle_agent_request(
            "draft the checklist",
            {},
            {"id": "session-1", "user_id": USER},
            context,
        )
    finally:
        reset_request_scope(token)

    assert result["success"] is True
    scoped_factory.assert_called_once_with(WORKSPACE, TENANT)
    default_factory.assert_not_called()
    executed = atom.execute.await_args.kwargs["context"]
    assert executed["workspace_id"] == WORKSPACE
    assert executed["tenant_id"] == TENANT
    # The retired authority keys never appear downstream.
    assert "_authenticated_workspace_id" not in executed
    assert "_authenticated_tenant_id" not in executed


@pytest.mark.asyncio
async def test_chat_fleet_direct_default_call_keeps_default_singleton(monkeypatch):
    """No published request scope (direct/internal call) keeps default.

    A2A and ACP callers do not pass a context dict, but they DO pass the
    authenticated user id into ``process_chat_message``, which publishes the
    scope; a direct ``_handle_agent_request`` call with neither must retain the
    deliberate default singleton rather than inventing a scope.
    """
    from integrations.chat_orchestrator import ChatOrchestrator

    orchestrator = object.__new__(ChatOrchestrator)
    orchestrator._emit_agent_step = AsyncMock()
    orchestrator._emit_agent_status = AsyncMock()

    atom = MagicMock()
    atom.execute = AsyncMock(
        return_value={"final_output": "ok", "execution_id": "exec-1"})
    scoped_factory = MagicMock()
    default_factory = MagicMock(return_value=atom)
    fake_module = types.ModuleType("core.atom_meta_agent")
    fake_module.AgentTriggerMode = SimpleNamespace(MANUAL="manual")
    fake_module.get_atom_agent = default_factory
    fake_module.get_scoped_atom_agent = scoped_factory
    monkeypatch.setitem(sys.modules, "core.atom_meta_agent", fake_module)

    result = await orchestrator._handle_agent_request(
        "draft the checklist",
        {},
        {"id": "session-1", "user_id": USER},
        None,
    )

    assert result["success"] is True
    default_factory.assert_called_once_with()
    scoped_factory.assert_not_called()
    executed = atom.execute.await_args.kwargs["context"]
    assert executed["workspace_id"] == "default"
    assert executed["tenant_id"] == "default"
