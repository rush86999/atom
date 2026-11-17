# -*- coding: utf-8 -*-
"""Explicit specialist collaboration: semantic contract + deterministic routing.

Live defect (2026-11-17 synthetic Q3 chat): the user asked to "Analyze these
synthetic Q3 facts with finance and sales specialists". The shared turn
interpretation had no collaboration vocabulary, so the accepted decision was
``conversation`` and the turn answered from one perspective — no fleet, no
specialist contributions.

The fix is SEMANTIC, not lexical: the ONE existing structured interpretation
schema/prompt can now express ``collaboration`` with the user's role labels,
``explicit``/``generic`` semantics; the deterministic decision/program/planner
only CARRY that accepted requirement into the existing governed fleet lane.
These tests feed structured synthetic interpretations (as the root verifier is
expected to) and prove the routing contract, not a regex's reading of English.
"""
from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.atom_meta_agent as ama
import core.chat_tool_planner as ctp
import core.turn_decision as td
from core.action_program import (
    AUTH_GRANTED as AP_AUTH_GRANTED,
    AUTH_NEEDS_CONFIRMATION as AP_AUTH_NEEDS_CONFIRMATION,
    CollaborateOp,
    compute_authorizations,
    program_from_decision,
)
from core.database import Base
from core.models import (
    AgentExecution, AgentRegistry, DelegationChain, FleetRoutingAudit,
    Tenant, User, Workspace,
)
from core.turn_decision import (
    AUTH_GRANTED,
    AUTH_NEEDS_CONFIRMATION,
    COLLABORATION_OBJECTIVE_MAX,
    COLLABORATION_ROLE_LABEL_MAX,
    COLLABORATION_ROLE_LIMIT,
    INTERPRETATION_ACTION_KINDS,
    apply_interpretation_actions,
    build_turn_decision,
    collaboration_requirement_from_action,
    interpret_turn_request,
    turn_collaboration_requirement,
)

MESSAGE = (
    "Analyze these synthetic Q3 facts with finance and sales specialists: "
    "closed revenue USD100, remaining pipeline USD200, target USD250. "
    "Compare closed revenue with target, identify the gap, and explain that "
    "pipeline is not closed revenue."
)


def _interpretation(*actions, origin="llm:synthetic", scope="replace"):
    return {
        "schema": td.INTERPRETATION_SCHEMA,
        "origin": origin,
        "scope_change": scope,
        "message": MESSAGE,
        "actions": list(actions),
        "subjects": [],
        "sources": [],
        "constraints": [],
    }


def _collaboration(roles=("finance", "sales"), explicit=True, generic=False):
    return {
        "kind": "collaboration",
        "roles": list(roles),
        "explicit": explicit,
        "generic": generic,
    }


def _kinds(decision):
    return [a["kind"] for a in decision["requested_actions"]]


# ---------------------------------------------------------------------------
# 1. The shared interpretation can EXPRESS the request.
# ---------------------------------------------------------------------------

def test_collaboration_is_first_class_interpretation_vocabulary():
    assert "collaboration" in INTERPRETATION_ACTION_KINDS
    prompt = td._interpretation_prompt(MESSAGE, [], {}, {})
    assert "COLLABORATION" in prompt
    assert "roles" in prompt and "explicit" in prompt
    assert "perspective" in prompt and "hypothetical" in prompt
    assert "quoted" in prompt and "negated" in prompt
    # One structured interpreter, no second parser.
    assert not hasattr(td, "detect_explicit_specialist_collaboration")


def test_interpret_turn_request_carries_roles_and_policy_verdict(monkeypatch):
    async def _fake_structured(*args, **kwargs):
        return {
            "actions": [_collaboration()],
            "subjects": [],
            "sources": [],
            "requested_fields": [],
            "output_format": "",
            "constraints": [],
            "scope_change": "replace",
            "confidence": 0.92,
        }

    monkeypatch.setattr(
        "core.llm.pinned_planning.pinned_structured_call",
        _fake_structured)
    monkeypatch.setattr(
        "core.llm.pinned_planning.resolve_pinned_provider_model",
        lambda *a, **k: None)
    td.reset_interpretation_for_tests()

    record = asyncio.run(interpret_turn_request(
        MESSAGE, {}, [], {}, request_id="r-collab",
        llm_service=object()))

    assert record["origin"].startswith("llm")
    action = next(a for a in record["actions"]
                  if a["kind"] == "collaboration")
    assert action["roles"] == ["finance", "sales"]
    assert action["authorization"] == AUTH_GRANTED
    assert action["explicit"] is True
    assert record["collaboration"]["required"] is True
    assert record["collaboration"]["roles"] == ["finance", "sales"]
    assert record["deterministic_decision"]["requested_actions"][-1][
        "kind"] == "collaboration"


def test_ambiguous_collaboration_requires_clarification_not_a_direct_answer():
    decision = build_turn_decision(MESSAGE, {})
    composed = apply_interpretation_actions(
        decision, _interpretation(_collaboration(roles=(), generic=False)))
    requirement = turn_collaboration_requirement(composed)
    assert requirement["required"] is True
    assert requirement["clarification_required"] is True
    assert requirement["authorization"] == AUTH_NEEDS_CONFIRMATION
    assert requirement["question"]
    assert "collaboration" in _kinds(composed)


# ---------------------------------------------------------------------------
# 2. The deterministic decision/program preserve the accepted request.
# ---------------------------------------------------------------------------

def test_accepted_collaboration_replaces_floor_conversation_and_compiles():
    decision = build_turn_decision(MESSAGE, {})
    assert _kinds(decision) == ["conversation"], (
        "the synchronous floor is intentionally semantic-free; the accepted "
        "interpretation is what carries explicit collaboration")

    composed = apply_interpretation_actions(
        decision, _interpretation(_collaboration()))

    assert _kinds(composed) == ["collaboration"], _kinds(composed)
    assert composed["action_program"]["actions"][0]["op"] == "collaborate"
    assert composed["action_program"]["actions"][0]["roles"] == [
        "finance", "sales"]

    program = program_from_decision(composed)
    op = program.actions[0]
    assert isinstance(op, CollaborateOp)
    assert op.roles == ["finance", "sales"]

    requirement = turn_collaboration_requirement(composed)
    assert requirement["required"] is True
    assert requirement["authorization"] == AUTH_GRANTED

    verdicts = compute_authorizations(
        program, {"collaboration_requirement": requirement})
    assert verdicts[op.action_id] == AP_AUTH_GRANTED
    # Fail closed when no accepted requirement is supplied.
    assert compute_authorizations(program)[op.action_id] == (
        AP_AUTH_NEEDS_CONFIRMATION)


def test_non_collaboration_interpretation_keeps_single_answer_program():
    decision = build_turn_decision(MESSAGE, {})
    for semantic in (
        {"kind": "conversation"},
        # The interpreter is the semantic authority: quoted, negated,
        # hypothetical and perspective-framing readings all arrive as
        # conversation, never as collaboration.
        {"kind": "conversation", "note": "quoted example"},
        {"kind": "conversation", "note": "negated"},
        {"kind": "conversation", "note": "hypothetical"},
        {"kind": "conversation", "note": "perspective framing"},
    ):
        composed = apply_interpretation_actions(
            decision, _interpretation(semantic))
        assert _kinds(composed) == ["conversation"], semantic
        assert turn_collaboration_requirement(composed)["required"] is False
        program = program_from_decision(composed)
        assert [op.op for op in program.actions] == ["converse"]


def test_degraded_interpretation_never_adds_collaboration():
    decision = build_turn_decision(MESSAGE, {})
    degraded = _interpretation(_collaboration(), origin="unresolved")
    composed = apply_interpretation_actions(decision, degraded)
    assert _kinds(composed) == ["conversation"]
    assert turn_collaboration_requirement(composed)["required"] is False


# ---------------------------------------------------------------------------
# 3. The planner carries the accepted requirement (no second reading).
# ---------------------------------------------------------------------------

def test_planner_forces_agent_route_from_accepted_requirement(monkeypatch):
    async def _ordinary(*args, **kwargs):
        return ctp.ToolPlan(
            use_tool=False, suggested_intent="data_analysis",
            routing_confidence=0.9, reason="ordinary analysis")

    monkeypatch.setattr(ctp, "_structured_with_fallback", _ordinary)
    monkeypatch.setattr(ctp, "get_connected_services", lambda user_id: [])

    plan = asyncio.run(ctp.plan_tool_use(
        MESSAGE, [], "user-1", object(),
        collaboration_requirement={
            "required": True, "roles": ["finance", "sales"],
            "generic": False, "authorization": AUTH_GRANTED}))

    assert plan.collaboration_required is True
    assert plan.specialist_roles == ["finance", "sales"]
    assert plan.suggested_intent == "agent_request"
    assert plan.routing_confidence >= 0.95


def test_planner_ignores_unaccepted_or_absent_requirement(monkeypatch):
    async def _ordinary(*args, **kwargs):
        return ctp.ToolPlan(
            use_tool=False, suggested_intent="data_analysis",
            routing_confidence=0.9, reason="ordinary analysis")

    monkeypatch.setattr(ctp, "_structured_with_fallback", _ordinary)
    monkeypatch.setattr(ctp, "get_connected_services", lambda user_id: [])

    plan = asyncio.run(ctp.plan_tool_use(
        "Analyze these Q3 facts.", [], "user-1", object(),
        collaboration_requirement={"required": False}))
    assert plan.collaboration_required is False
    assert plan.specialist_roles == []
    assert plan.suggested_intent == "data_analysis"


# ---------------------------------------------------------------------------
# 4. Existing registered capabilities resolve roles; missing roles clarify.
# ---------------------------------------------------------------------------

@pytest.fixture()
def scratch(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'collab.db'}",
        connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield Session
    finally:
        engine.dispose()


def _seed_roster(Session):
    db = Session()
    db.add_all([
        Tenant(id="t-collab", name="Collab", subdomain="collab"),
        Workspace(id="w-collab", name="Collab", tenant_id="t-collab"),
        AgentRegistry(
            id="spec-finance", name="Finance Analyst",
            display_name="Finance Analyst", category="Finance",
            module_path="core.generic_agent", class_name="GenericAgent",
            tenant_id="t-collab", workspace_id="w-collab",
            user_id="u-collab", status="intern", enabled=True,
            capabilities=["finance"], specialty="finance"),
        AgentRegistry(
            id="spec-sales", name="Sales Analyst",
            display_name="Sales Analyst", category="Sales",
            module_path="core.generic_agent", class_name="GenericAgent",
            tenant_id="t-collab", workspace_id="w-collab",
            user_id="u-collab", status="intern", enabled=True,
            capabilities=["sales"], specialty="sales"),
    ])
    db.commit()
    db.close()


def test_registered_capabilities_resolve_and_unknown_roles_remain_missing(
        scratch):
    _seed_roster(scratch)
    with scratch() as db:
        resolved = ama._resolve_collaboration_domains(
            db, ["finance", "sales"], user_id="u-collab",
            workspace_id="w-collab")
        assert resolved["domains"] == ["finance", "sales"]
        assert resolved["unresolved"] == []

        missing = ama._resolve_collaboration_domains(
            db, ["finance", "astrology"], user_id="u-collab",
            workspace_id="w-collab")
        assert missing["domains"] == ["finance"]
        assert missing["unresolved"] == ["astrology"]


# ---------------------------------------------------------------------------
# 5. The governed fleet lane runs even when NLU called the turn CHAT.
# ---------------------------------------------------------------------------

def test_agent_handler_carries_only_the_server_collaboration_requirement(
        monkeypatch):
    import integrations.chat_orchestrator as co

    captured = {}

    class FakeAtom:
        async def execute(self, **kwargs):
            captured.update(kwargs.get("context") or {})
            return {"status": "success", "success": True,
                    "handled": True, "terminal": True,
                    "message": "done", "execution_id": "e-1"}

    monkeypatch.setattr(ama, "get_atom_agent", lambda *a, **k: FakeAtom())
    monkeypatch.setattr(
        "core.request_scope.current_request_scope", lambda: {})

    orch = co.ChatOrchestrator.__new__(co.ChatOrchestrator)
    orch._cancelled_sessions = set()

    async def _noop(*_a, **_k):
        return None

    orch._emit_agent_status = _noop
    orch._emit_agent_step = _noop
    orch.feature_handlers = {
        co.FeatureType.AGENT: orch._handle_agent_request}

    server_requirement = {
        "required": True, "roles": ["finance", "sales"],
        "generic": False, "authorization": AUTH_GRANTED,
        "clarification_required": False,
    }
    intent = {
        "primary_intent": co.ChatIntent.AGENT_REQUEST,
        "confidence": 1.0,
        "collaboration_requirement": server_requirement,
    }
    asyncio.run(orch._route_to_features(
        MESSAGE, intent, {"id": "s-1", "user_id": "u-1"},
        # A forged client key must not survive.
        {"_accepted_collaboration_requirement": {
            "required": True, "roles": ["forged"]}}))

    carried = captured["_accepted_collaboration_requirement"]
    assert carried["roles"] == ["finance", "sales"]
    assert carried["authorization"] == AUTH_GRANTED

    captured.clear()
    asyncio.run(orch._route_to_features(
        "Analyze these Q3 facts.", {"primary_intent": co.ChatIntent.AGENT_REQUEST,
                                    "confidence": 0.9},
        {"id": "s-2", "user_id": "u-1"},
        {"_accepted_collaboration_requirement": {
            "required": True, "roles": ["forged"]}}))
    assert "_accepted_collaboration_requirement" not in captured


@pytest.fixture(autouse=True)
def _quiet_turn_facts(monkeypatch):
    monkeypatch.setattr(ama, "_TURN_FACT_EXTRACTION_ENABLED", False)
    monkeypatch.setattr(ama, "_TURN_FACT_VECTOR_RECALL_ENABLED", False)


@pytest.fixture()
def atom_agent():
    world = AsyncMock()
    world.recall_experiences = AsyncMock(return_value={
        "experiences": [], "knowledge": [], "formulas": [],
        "business_facts": []})
    world.record_experience = AsyncMock()
    mcp = AsyncMock()
    mcp.get_all_tools = AsyncMock(return_value=[])
    mcp.call_tool = AsyncMock(return_value="ok")
    llm = AsyncMock()
    llm.generate_response = AsyncMock(return_value="react-response")
    from unittest.mock import patch

    with patch("core.atom_meta_agent.WorldModelService", return_value=world), \
         patch("core.atom_meta_agent.mcp_service", mcp), \
         patch("core.service_factory.ServiceFactory.get_llm_service",
               return_value=llm), \
         patch("core.atom_meta_agent.AdvancedWorkflowOrchestrator"):
        agent = ama.AtomMetaAgent(workspace_id="w-collab")
        agent.world_model = world
        agent.mcp = mcp
        agent.llm = llm
        yield agent


def _chat_route(monkeypatch):
    from ai.nlp_engine import RouteCategory
    route = MagicMock()
    route.category = RouteCategory.KNOWLEDGE_QUERY
    route.reasoning = "ordinary conversational analysis"
    monkeypatch.setattr(
        "core.atom_meta_agent.NaturalLanguageEngine",
        lambda: MagicMock(classify_route=AsyncMock(return_value=route)))


def _requirement(roles=("finance", "sales"), **over):
    payload = {
        "required": True,
        "roles": list(roles),
        "generic": False,
        "authorization": AUTH_GRANTED,
        "clarification_required": False,
        "objective": MESSAGE,
    }
    payload.update(over)
    return payload


@pytest.mark.asyncio
async def test_atom_executes_collaboration_even_when_route_is_chat(
        atom_agent, monkeypatch):
    from unittest.mock import patch
    monkeypatch.setenv("ATOM_FLEET_ROUTING_ENABLED", "true")
    monkeypatch.setenv("ATOM_FLEET_ROUTING_FORCE_ENFORCE", "true")
    _chat_route(monkeypatch)
    monkeypatch.setattr(
        ama, "_resolve_collaboration_domains",
        lambda *a, **k: {"domains": ["finance", "sales"],
                         "unresolved": []})

    summary = {
        "status": "fleet_recruited", "chain_id": "chain-collab",
        "specialists_count": 2,
        "specialists": [
            {"agent_id": "spec-finance", "domain": "finance"},
            {"agent_id": "spec-sales", "domain": "sales"}],
    }
    route = AsyncMock(return_value=summary)
    monkeypatch.setattr(atom_agent, "route_with_governance", route)
    execute_specialists = AsyncMock(return_value={
        "success": True, "status": "specialists_executed",
        "final_output": "Finance and Sales contributions.",
        "specialist_results": [
            {"agent_id": "spec-finance", "status": "success"},
            {"agent_id": "spec-sales", "status": "success"}],
        "specialists_count": 2, "chain_id": "chain-collab"})
    monkeypatch.setattr(
        atom_agent, "_execute_fleet_specialists", execute_specialists)

    with patch("core.atom_meta_agent.SessionLocal"), \
         patch("core.atom_meta_agent.AgentGovernanceService"):
        result = await atom_agent.execute(
            MESSAGE,
            context={"_accepted_collaboration_requirement": _requirement()},
            trigger_mode=ama.AgentTriggerMode.MANUAL)

    route.assert_awaited()
    kwargs = route.await_args.kwargs
    assert kwargs.get("requested_specialist_domains") == [
        "finance", "sales"]
    execute_specialists.assert_awaited()
    assert result["status"] == "specialists_executed"
    assert result["final_output"] == "Finance and Sales contributions."


@pytest.mark.asyncio
async def test_atom_without_requirement_keeps_no_fleet_behavior(
        atom_agent, monkeypatch):
    from unittest.mock import patch
    monkeypatch.setenv("ATOM_FLEET_ROUTING_ENABLED", "true")
    _chat_route(monkeypatch)
    route = AsyncMock(return_value={})
    monkeypatch.setattr(atom_agent, "route_with_governance", route)

    with patch("core.atom_meta_agent.SessionLocal"), \
         patch("core.atom_meta_agent.AgentGovernanceService"):
        try:
            await atom_agent.execute(
                "Analyze these Q3 facts.",
                context={}, trigger_mode=ama.AgentTriggerMode.MANUAL)
        except Exception:
            pass

    route.assert_not_awaited()


@pytest.mark.asyncio
async def test_unavailable_specialist_clarifies_without_dispatching(
        atom_agent, monkeypatch):
    from unittest.mock import patch
    monkeypatch.setenv("ATOM_FLEET_ROUTING_ENABLED", "true")
    _chat_route(monkeypatch)
    monkeypatch.setattr(
        ama, "_resolve_collaboration_domains",
        lambda *a, **k: {"domains": ["finance"],
                         "unresolved": ["astrology"]})
    route = AsyncMock(return_value={})
    monkeypatch.setattr(atom_agent, "route_with_governance", route)
    finalize = AsyncMock()
    monkeypatch.setattr(
        atom_agent, "_finalize_collaboration_pending", finalize)
    finalize.return_value = {
        "status": "pending_collaboration", "success": False,
        "objective_pending": True, "handled": True, "terminal": True,
        "final_output": "Which specialists should I involve?"}

    with patch("core.atom_meta_agent.SessionLocal"), \
         patch("core.atom_meta_agent.AgentGovernanceService"):
        result = await atom_agent.execute(
            MESSAGE,
            context={"_accepted_collaboration_requirement": _requirement(
                roles=("finance", "astrology"))},
            trigger_mode=ama.AgentTriggerMode.MANUAL)

    route.assert_not_awaited()
    finalize.assert_awaited()
    assert result["status"] == "pending_collaboration"
    assert result["objective_pending"] is True
    assert result["success"] is False
    assert "astrology" in str(finalize.await_args.kwargs.get("unresolved"))


# ---------------------------------------------------------------------------
# 6. Accepted roles constrain recruitment; unknown roles fail honestly.
# ---------------------------------------------------------------------------

def _recruitment_service(monkeypatch):
    from core.recruitment_intelligence_service import (
        RecruitmentIntelligenceService, RecruitmentPlan)
    from core.specialist_matcher import SpecialistMatcher

    matcher = MagicMock(spec=SpecialistMatcher)
    matcher.find_specialists_for_domains.side_effect = (
        lambda domains, **kwargs: {
            domain: [{
                "agent_id": f"spec-{domain}",
                "name": f"{domain.title()} Analyst",
                "capability_score": 0.9,
            }]
            for domain in domains
        })
    svc = RecruitmentIntelligenceService(
        db=MagicMock(),
        llm=MagicMock(),
        specialist_matcher=matcher,
        analytics=MagicMock(),
        fleet_service=MagicMock(),
        optimizer=MagicMock(
            get_optimization_parameters=MagicMock(return_value={})),
        governance=MagicMock(
            can_perform_action_async=AsyncMock(
                return_value={"allowed": True})),
        workspace_id="w-collab", tenant_id="t-collab",
    )

    # The model's own plan disagrees (marketing); the accepted requirement
    # must win.
    async def _plan(*args, **kwargs):
        return RecruitmentPlan(
            goal_analysis="model plan", required_domains=["marketing"],
            domain_rationale={"marketing": "model guess"},
            complexity_estimate="medium", estimated_parallelizable=True,
            suggested_specialist_count=1)

    monkeypatch.setattr(svc, "analyze_goal_domains", _plan)
    return svc


def test_requested_domains_are_exact_constraints_on_recruitment(monkeypatch):
    svc = _recruitment_service(monkeypatch)
    result = asyncio.run(svc.orchestrate_recruitment(
        "Analyze Q3 facts with finance and sales specialists", "u-collab", {},
        requested_domains=["finance", "sales"]))
    assert result["success"] is True
    assert [item["domain"] for item in result["recruitment_roster"]] == [
        "finance", "sales"]
    assert result["recruitment_plan"]["required_domains"] == [
        "finance", "sales"]


def test_unknown_requested_domain_fails_before_fleet_substitution(monkeypatch):
    svc = _recruitment_service(monkeypatch)
    result = asyncio.run(svc.orchestrate_recruitment(
        "Analyze Q3 facts with finance and astrology specialists",
        "u-collab", {}, requested_domains=["finance", "astrology"]))
    assert result["success"] is False
    assert "astrology" in result["error"]
    assert result["unresolved_domains"] == ["astrology"]


# ---------------------------------------------------------------------------
# 9. Orchestrator early seam: pending before reply, exact resume on approval.
# ---------------------------------------------------------------------------

def _orch_collab(manager=None):
    import integrations.chat_orchestrator as co
    orch = co.ChatOrchestrator.__new__(co.ChatOrchestrator)
    orch.tenant_id = "t-collab"
    orch.session_manager = manager
    orch.conversation_sessions = {}
    orch._handle_agent_request = AsyncMock(return_value={
        "success": True, "status": "success", "outcome": "success",
        "message": "FINANCE CONTRIBUTION: gap 150. "
                   "SALES CONTRIBUTION: pipeline is not closed revenue.",
        "chain_id": "chain-collab", "specialists_count": 2,
        "execution_id": "exec-agent"})
    return orch


@pytest.fixture()
def durable_file_manager(tmp_path, monkeypatch):
    """A real first-class file-mode session store (durable across instances).

    The pending contract is durable-authority first; an in-memory-only test
    double cannot prove cold resume or honest save failures.
    """
    monkeypatch.setattr("core.chat_session_manager.DB_AVAILABLE", False)
    monkeypatch.setattr("core.chat_session_manager.SessionLocal", None)
    monkeypatch.setenv("ATOM_CHAT_STORAGE", "file")
    monkeypatch.setenv("CHAT_PERSISTENCE_MODE", "FILE")
    from core.chat_session_manager import ChatSessionManager

    manager = ChatSessionManager(
        sessions_file=str(tmp_path / "collab-sessions.json"))
    manager.create_session(user_id="u-collab", session_id="s-collab")
    return manager


def _seed_durable_collab_pending(manager, session_id="s-collab"):
    import integrations.chat_orchestrator as co

    record = {
        "state": "pending",
        "reason": "fleet_pilot_not_enforced",
        "request": MESSAGE,
        "objective": MESSAGE,
        "roles": ["finance", "sales"],
        "generic": False,
        "question": "The request is preserved as pending.",
        "user_id": "u-collab",
        "workspace_id": "t-collab",
        "tenant_id": "t-collab",
        "session_id": session_id,
        "pending_id": "pending-1",
        "created_at": "2026-11-17T00:00:00+00:00",
        "revision": "rev-1",
        "request_digest": co.ChatOrchestrator._collaboration_request_digest(
            MESSAGE, MESSAGE, ["finance", "sales"], False),
    }
    assert manager.update_session_metadata(
        session_id,
        {
            co._PENDING_COLLABORATION_KEY: record,
            co._PENDING_COLLABORATION_REVISION_KEY: "rev-1",
        },
    )
    return record


@pytest.mark.parametrize("master,enforce,reason", [
    ("false", False, "fleet_routing_disabled"),
    ("true", False, "fleet_pilot_not_enforced"),
])
def test_orchestrator_pending_before_reply_for_master_and_shadow(
        monkeypatch, durable_file_manager, master, enforce, reason):
    import core.fleet_routing_config as frc
    import core.fleet_orchestration.fleet_router_automation as fra
    monkeypatch.setattr(frc, "fleet_routing_enabled", lambda: master == "true")
    monkeypatch.setattr(fra, "resolved_fleet_enforce", lambda: enforce)
    import integrations.chat_orchestrator as co

    decision = apply_interpretation_actions(
        build_turn_decision(MESSAGE, {}),
        _interpretation(_collaboration()))
    session = {"id": "s-collab", "history": []}
    deadline = MagicMock()
    deadline.remaining.return_value = 60.0
    orch = _orch_collab(durable_file_manager)

    response = asyncio.run(orch._route_accepted_collaboration(
        decision=decision, message=MESSAGE, session=session,
        session_id="s-collab", user_id="u-collab", context={},
        execution_id="exec-chat", deadline=deadline))

    assert response is not None
    assert response["outcome"] == "pending"
    assert response["objective_pending"] is True
    assert response["data"]["collaboration"]["reason"] == reason
    assert response["data"]["collaboration"]["request_preserved"] is True
    assert response["data"]["collaboration"]["request"] == MESSAGE
    orch._handle_agent_request.assert_not_awaited()
    pending = session[co._PENDING_COLLABORATION_KEY]
    assert pending["request"] == MESSAGE
    assert pending["roles"] == ["finance", "sales"]
    assert pending["state"] == "pending"


def test_orchestrator_approved_pilot_runs_exact_request(monkeypatch):
    import core.fleet_routing_config as frc
    import core.fleet_orchestration.fleet_router_automation as fra
    monkeypatch.setattr(frc, "fleet_routing_enabled", lambda: True)
    monkeypatch.setattr(fra, "resolved_fleet_enforce", lambda: True)
    import integrations.chat_orchestrator as co

    decision = apply_interpretation_actions(
        build_turn_decision(MESSAGE, {}),
        _interpretation(_collaboration()))
    session = {"id": "s-collab", "history": []}
    deadline = MagicMock()
    deadline.remaining.return_value = 60.0
    orch = _orch_collab()

    response = asyncio.run(orch._route_accepted_collaboration(
        decision=decision, message=MESSAGE, session=session,
        session_id="s-collab", user_id="u-collab", context={},
        execution_id="exec-chat", deadline=deadline))

    orch._handle_agent_request.assert_awaited_once()
    assert orch._handle_agent_request.await_args.args[0] == MESSAGE
    assert response["outcome"] == "completed"
    assert "FINANCE CONTRIBUTION" in response["message"]
    assert "SALES CONTRIBUTION" in response["message"]
    assert co._PENDING_COLLABORATION_KEY not in session


def test_orchestrator_approval_resumes_original_pending_request(
        monkeypatch, durable_file_manager):
    import core.fleet_routing_config as frc
    import core.fleet_orchestration.fleet_router_automation as fra
    monkeypatch.setattr(frc, "fleet_routing_enabled", lambda: True)
    monkeypatch.setattr(fra, "resolved_fleet_enforce", lambda: True)
    import integrations.chat_orchestrator as co

    decision = build_turn_decision(MESSAGE, {})
    _seed_durable_collab_pending(durable_file_manager)
    session = {"id": "s-collab", "history": []}
    deadline = MagicMock()
    deadline.remaining.return_value = 60.0
    orch = _orch_collab(durable_file_manager)

    response = asyncio.run(orch._route_accepted_collaboration(
        decision=decision, message="go ahead", session=session,
        session_id="s-collab", user_id="u-collab", context={},
        execution_id="exec-chat", deadline=deadline))

    orch._handle_agent_request.assert_awaited_once()
    assert orch._handle_agent_request.await_args.args[0] == MESSAGE
    assert response["outcome"] == "completed"

@pytest.fixture()
def durable_world(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'collab-durable.db'}",
        connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()
    db.add_all([
        Tenant(id="t-collab", name="Collab", subdomain="collab"),
        Workspace(id="w-collab", name="Collab", tenant_id="t-collab"),
        User(id="u-collab", tenant_id="t-collab", email="u@collab.test",
             first_name="U", last_name="Collab", role="owner",
             status="active", workspace_id="w-collab", is_active=True),
        AgentRegistry(
            id="atom_main", name="Atom", display_name="Atom",
            category="system", module_path="core.atom_meta_agent",
            class_name="AtomMetaAgent", tenant_id="t-collab",
            workspace_id="w-collab", status="autonomous", enabled=True,
            capabilities=["operations"], specialty="operations",
            user_id="u-collab"),
        AgentRegistry(
            id="spec-finance", name="Finance Analyst",
            display_name="Finance Analyst", category="Finance",
            module_path="core.generic_agent", class_name="GenericAgent",
            tenant_id="t-collab", workspace_id="w-collab",
            user_id="u-collab", status="autonomous", enabled=True,
            capabilities=["finance"], specialty="finance"),
        AgentRegistry(
            id="spec-sales", name="Sales Analyst",
            display_name="Sales Analyst", category="Sales",
            module_path="core.generic_agent", class_name="GenericAgent",
            tenant_id="t-collab", workspace_id="w-collab",
            user_id="u-collab", status="autonomous", enabled=True,
            capabilities=["sales"], specialty="sales"),
    ])
    db.commit()
    db.close()
    try:
        yield engine, Session
    finally:
        engine.dispose()


def _pending_atom(monkeypatch, Session):
    from unittest.mock import patch

    monkeypatch.setattr(ama, "SessionLocal", Session)
    if not hasattr(ama, "_TURN_FACT_EXTRACTION_ENABLED"):
        pass
    monkeypatch.setattr(ama, "_TURN_FACT_EXTRACTION_ENABLED", False)
    monkeypatch.setattr(ama, "_TURN_FACT_VECTOR_RECALL_ENABLED", False)
    from ai.nlp_engine import RouteCategory
    route = MagicMock()
    route.category = RouteCategory.KNOWLEDGE_QUERY
    route.reasoning = "analysis"
    monkeypatch.setattr(
        ama, "NaturalLanguageEngine",
        lambda: MagicMock(classify_route=AsyncMock(return_value=route)))
    world = AsyncMock()
    world.recall_experiences = AsyncMock(return_value={
        "experiences": [], "knowledge": [], "formulas": [],
        "business_facts": []})
    world.record_experience = AsyncMock()
    mcp = AsyncMock()
    mcp.get_all_tools = AsyncMock(return_value=[])
    mcp.call_tool = AsyncMock(return_value="ok")
    with patch("core.atom_meta_agent.WorldModelService", return_value=world), \
         patch("core.atom_meta_agent.mcp_service", mcp), \
         patch("core.service_factory.ServiceFactory.get_llm_service",
               return_value=AsyncMock()), \
         patch("core.atom_meta_agent.AdvancedWorkflowOrchestrator"):
        atom = ama.AtomMetaAgent(workspace_id="w-collab")
        atom.world_model = world
        atom.mcp = mcp
        atom.llm = AsyncMock()
        return atom


@pytest.mark.asyncio
@pytest.mark.parametrize("master,force", [
    ("false", None),
    ("true", "false"),
])
async def test_master_off_and_shadow_are_durable_pending_not_success(
        durable_world, monkeypatch, master, force):
    _engine, Session = durable_world
    monkeypatch.setenv("ATOM_FLEET_ROUTING_ENABLED", master)
    if force is None:
        monkeypatch.delenv("ATOM_FLEET_ROUTING_FORCE_ENFORCE", raising=False)
    else:
        monkeypatch.setenv("ATOM_FLEET_ROUTING_FORCE_ENFORCE", force)
    atom = _pending_atom(monkeypatch, Session)
    route = AsyncMock(return_value={})
    monkeypatch.setattr(atom, "route_with_governance", route)

    result = await atom.execute(
        MESSAGE,
        context={"_accepted_collaboration_requirement": _requirement()},
        trigger_mode=ama.AgentTriggerMode.MANUAL,
        execution_id="exec-collab-pending")

    route.assert_not_awaited()
    assert result["status"] == "pending_collaboration"
    assert result["success"] is False
    assert result["objective_pending"] is True
    assert result["chain_id"] is None
    assert result["specialists_count"] == 0
    assert ama._execution_succeeded(result) is False

    with Session() as db:
        execution = db.query(AgentExecution).filter(
            AgentExecution.id == "exec-collab-pending").first()
        assert execution is not None
        assert execution.status == "paused", execution.status
        assert db.query(FleetRoutingAudit).count() == 0
        assert db.query(DelegationChain).count() == 0

def test_eight_and_nine_role_requests_are_preserved_end_to_end():
    eight = [f"role-{i}" for i in range(8)]
    nine = [f"role-{i}" for i in range(9)]
    for roles in (eight, nine):
        requirement = collaboration_requirement_from_action({
            "kind": "collaboration", "roles": roles, "explicit": True},
            MESSAGE)
        assert requirement["clarification_required"] is False
        assert requirement["roles"] == roles
        assert requirement["limits"]["requested_count"] == len(roles)

        decision = apply_interpretation_actions(
            build_turn_decision(MESSAGE, {}),
            _interpretation(_collaboration(roles=roles)))
        action = next(a for a in decision["requested_actions"]
                      if a["kind"] == "collaboration")
        assert action["roles"] == roles
        program = program_from_decision(decision)
        collab = next(op for op in program.actions
                      if isinstance(op, CollaborateOp))
        assert collab.roles == roles
        # Atom's server-side normalizer also keeps every label.
        normalized = ama._accepted_collaboration_requirement({
            "_accepted_collaboration_requirement": requirement})
        assert normalized["roles"] == roles
        assert normalized["clarification_required"] is False


def test_duplicate_roles_dedupe_without_triggering_the_limit():
    roles = ["finance", "Finance", "sales", "finance", "sales",
             "Sales", "finance", "sales"]
    requirement = collaboration_requirement_from_action({
        "kind": "collaboration", "roles": roles, "explicit": True},
        MESSAGE)
    assert requirement["roles"] == ["finance", "sales"]
    assert requirement["clarification_required"] is False
    assert requirement["limits"]["requested_count"] == 2


def test_role_limit_overflow_clarifies_and_preserves_every_role():
    roles = [f"role-{i}" for i in range(COLLABORATION_ROLE_LIMIT + 1)]
    requirement = collaboration_requirement_from_action({
        "kind": "collaboration", "roles": roles, "explicit": True},
        MESSAGE)
    assert requirement["clarification_required"] is True
    assert requirement["authorization"] == AUTH_NEEDS_CONFIRMATION
    assert requirement["roles"] == roles
    assert requirement["limits"]["requested_count"] == len(roles)
    assert str(COLLABORATION_ROLE_LIMIT) in requirement["question"]


def test_long_role_label_is_preserved_and_clarified_never_renamed():
    long_label = "Regional " + ("Finance " * 40) + "Operations"
    assert len(long_label) > COLLABORATION_ROLE_LABEL_MAX
    requirement = collaboration_requirement_from_action({
        "kind": "collaboration", "roles": [long_label], "explicit": True},
        MESSAGE)
    assert requirement["clarification_required"] is True
    assert requirement["roles"] == [long_label]
    assert requirement["limits"]["label_overflow"] == [long_label]
    assert str(COLLABORATION_ROLE_LABEL_MAX) in requirement["question"]


def test_long_objective_is_preserved_and_clarified():
    objective = MESSAGE + (" additional context" * 400)
    assert len(objective) > COLLABORATION_OBJECTIVE_MAX
    requirement = collaboration_requirement_from_action({
        "kind": "collaboration", "roles": ["finance"], "explicit": True},
        objective)
    assert requirement["clarification_required"] is True
    assert requirement["objective"] == objective
    assert requirement["limits"]["objective_overflow"] is True
    assert str(COLLABORATION_OBJECTIVE_MAX) in requirement["question"]


def test_nine_roles_survive_the_planner_requirement():
    async def _ordinary(*args, **kwargs):
        return ctp.ToolPlan(use_tool=False,
                            suggested_intent="data_analysis",
                            routing_confidence=0.9)

    roles = [f"role-{i}" for i in range(9)]
    requirement = collaboration_requirement_from_action({
        "kind": "collaboration", "roles": roles, "explicit": True},
        MESSAGE)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(ctp, "_structured_with_fallback", _ordinary)
        mp.setattr(ctp, "get_connected_services", lambda user_id: [])
        plan = asyncio.run(ctp.plan_tool_use(
            MESSAGE, [], "user-1", object(),
            collaboration_requirement=requirement))
    assert plan.specialist_roles == roles
    assert plan.collaboration_required is True


# ---------------------------------------------------------------------------
# 10. Joined public-chat boundary: only LLM outputs are doubled.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_public_chat_reaches_governed_fleet_and_final_answer(
        tmp_path, monkeypatch):
    """The real public entry, routing, program, fleet dispatch and completion.

    Only external LLM outputs are doubled at the ``LLMService`` boundary.
    The structured interpretation, turn decision, action program, planner,
    atom route, governance, recruitment, chain/link writes, GenericAgent
    execution, synthesis and chat completion all execute for real.
    """
    import contextlib
    from unittest.mock import patch

    import core.llm_service as ls
    import core.generic_agent as ga
    import integrations.chat_orchestrator as co
    from core.fleet_admiral import TaskAnalysis
    from core.models import ChainLink
    from core.react_models import ReActStep
    from core.recruitment_intelligence_service import RecruitmentPlan

    engine = create_engine(
        f"sqlite:///{tmp_path / 'public-collab.db'}",
        connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()
    db.add_all([
        Tenant(id="t-pub", name="Public", subdomain="pub"),
        Workspace(id="w-pub", name="Public", tenant_id="t-pub"),
        User(id="u-pub", tenant_id="t-pub", email="pub@example.test",
             first_name="Pub", last_name="User", role="owner",
             status="active", workspace_id="w-pub", is_active=True),
        AgentRegistry(
            id="atom_main", name="Atom", display_name="Atom",
            category="system", module_path="core.atom_meta_agent",
            class_name="AtomMetaAgent", tenant_id="t-pub",
            workspace_id="w-pub", status="autonomous", enabled=True,
            capabilities=["operations"], specialty="operations",
            user_id="u-pub"),
        AgentRegistry(
            id="spec-finance", name="Finance Analyst",
            display_name="Finance Analyst", category="Finance",
            module_path="core.generic_agent", class_name="GenericAgent",
            tenant_id="t-pub", workspace_id="w-pub", user_id="u-pub",
            status="autonomous", enabled=True,
            capabilities=["finance"], specialty="finance"),
        AgentRegistry(
            id="spec-sales", name="Sales Analyst",
            display_name="Sales Analyst", category="Sales",
            module_path="core.generic_agent", class_name="GenericAgent",
            tenant_id="t-pub", workspace_id="w-pub", user_id="u-pub",
            status="autonomous", enabled=True,
            capabilities=["sales"], specialty="sales"),
    ])
    db.commit()
    db.close()

    @contextlib.contextmanager
    def _scratch_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr("core.database.get_db_session", _scratch_db)
    monkeypatch.setattr("core.database.SessionLocal", Session)
    monkeypatch.setattr(ama, "SessionLocal", Session)
    monkeypatch.setattr(ga, "get_db_session", _scratch_db)
    monkeypatch.setattr(ga, "SessionLocal", Session)

    monkeypatch.setenv("ATOM_FLEET_ROUTING_ENABLED", "true")
    monkeypatch.setenv("ATOM_FLEET_ROUTING_FORCE_ENFORCE", "true")
    monkeypatch.setenv("TESTING", "1")

    async def _structured_response(*args, **kwargs):
        model = kwargs.get("response_model")
        name = getattr(model, "__name__", "")
        if name == "_Interpretation":
            return {
                "actions": [{
                    "kind": "collaboration",
                    "roles": ["finance", "sales"],
                    "explicit": True, "generic": False,
                }],
                "subjects": [], "sources": [], "requested_fields": [],
                "output_format": "", "constraints": [],
                "scope_change": "replace", "confidence": 0.95,
            }
        if name == "TaskAnalysis":
            return TaskAnalysis(
                complexity="medium",
                required_capabilities=["finance", "sales"],
                estimated_duration="10 minutes", specialist_count=2,
                reasoning="two explicitly requested specialist domains")
        if name == "RecruitmentPlan":
            return RecruitmentPlan(
                goal_analysis="Q3 revenue gap and pipeline explanation",
                required_domains=["finance", "sales"],
                domain_rationale={
                    "finance": "compare closed revenue with target",
                    "sales": "explain that pipeline is not closed revenue",
                },
                complexity_estimate="medium",
                estimated_parallelizable=True,
                suggested_specialist_count=2)
        if name == "ToolPlan":
            return ctp.ToolPlan(
                use_tool=False, suggested_intent="data_analysis",
                routing_confidence=0.8, reason="ordinary analysis")
        return None

    async def _structured(*args, **kwargs):
        model = kwargs.get("response_model")
        if getattr(model, "__name__", "") == "ReActStep":
            prompt = str(kwargs.get("prompt") or "")
            system = str(kwargs.get("system_instruction") or "")
            blob = f"{system}\n{prompt}"
            if "Finance Analyst" in blob:
                return ReActStep(
                    thought="finance specialist",
                    final_answer=(
                        "FINANCE CONTRIBUTION: closed revenue USD100 is "
                        "USD150 below the USD250 target."))
            if "Sales Analyst" in blob:
                return ReActStep(
                    thought="sales specialist",
                    final_answer=(
                        "SALES CONTRIBUTION: remaining pipeline USD200 is "
                        "not closed revenue."))
            return ReActStep(
                thought="specialist",
                final_answer="CONTRIBUTION: specialist analysis.")
        return None

    async def _generate(*args, **kwargs):
        return "Final answer: specialist analysis."

    async def _completion(*args, **kwargs):
        return {
            "success": True,
            "content": (
                "FINANCE CONTRIBUTION: closed revenue USD100 is USD150 "
                "below the USD250 target. SALES CONTRIBUTION: remaining "
                "pipeline USD200 is not closed revenue."),
            "model": "fake-synthesis",
            "provider": "fake",
        }

    monkeypatch.setattr(ls.LLMService, "generate_structured_response",
                        _structured_response)
    monkeypatch.setattr(ls.LLMService, "generate_structured", _structured)
    monkeypatch.setattr(ls.LLMService, "generate", _generate)
    monkeypatch.setattr(ls.LLMService, "generate_completion", _completion)

    from ai.nlp_engine import RouteCategory
    route = MagicMock()
    route.category = RouteCategory.KNOWLEDGE_QUERY
    route.reasoning = "public chat analysis"
    monkeypatch.setattr(
        ama, "NaturalLanguageEngine",
        lambda: MagicMock(classify_route=AsyncMock(return_value=route)))
    world = AsyncMock()
    world.recall_experiences = AsyncMock(return_value={
        "experiences": [], "knowledge": [], "formulas": [],
        "business_facts": []})
    world.record_experience = AsyncMock()
    mcp = AsyncMock()
    mcp.get_all_tools = AsyncMock(return_value=[])
    mcp.call_tool = AsyncMock(return_value="ok")
    with patch("core.atom_meta_agent.WorldModelService",
               return_value=world), \
         patch("core.atom_meta_agent.mcp_service", mcp), \
         patch("core.generic_agent.WorldModelService", return_value=world), \
         patch("core.generic_agent.mcp_service", mcp):
        atom = ama.AtomMetaAgent(workspace_id="w-pub")
    atom.world_model = world
    atom.mcp = mcp
    monkeypatch.setattr(ama, "get_atom_agent", lambda *a, **k: atom)
    monkeypatch.setattr(ama, "get_scoped_atom_agent", lambda *a, **k: atom)

    orch = co.ChatOrchestrator()
    orch.session_manager = None
    orch.ai_engines = {}
    session = {"id": "s-pub", "user_id": "u-pub", "history": []}
    monkeypatch.setattr(orch, "_get_or_create_session",
                        lambda *a, **k: session)
    monkeypatch.setattr(orch, "_emit_agent_status", AsyncMock())
    monkeypatch.setattr(orch, "_record_chat_step", AsyncMock())
    monkeypatch.setattr(orch, "_dispatch_turn_fact_extraction",
                        lambda *a, **k: None)
    monkeypatch.setattr(orch, "_try_canvas_edit",
                        AsyncMock(return_value=None))
    monkeypatch.setattr(orch, "_try_canvas_action",
                        AsyncMock(return_value=None))
    monkeypatch.setattr(orch, "_resolve_canvas_ctx",
                        AsyncMock(return_value=None))
    forbidden = AsyncMock(side_effect=AssertionError("direct reply path ran"))
    monkeypatch.setattr(orch, "_get_qwen_response", forbidden)
    monkeypatch.setattr(orch, "_analyze_intent", forbidden)
    monkeypatch.setattr(orch, "_route_to_features", forbidden)

    response = await orch.process_chat_message(
        user_id="u-pub", message=MESSAGE, session_id="s-pub", context={})

    forbidden.assert_not_awaited()
    assert response["intent"] == "collaboration"
    assert response["outcome"] == "completed"
    assert "FINANCE CONTRIBUTION" in response["message"]
    assert "SALES CONTRIBUTION" in response["message"]

    with Session() as db:
        chains = db.query(DelegationChain).all()
        assert len(chains) == 1, [c.id for c in chains]
        links = db.query(ChainLink).filter(
            ChainLink.chain_id == chains[0].id).all()
        assert {link.child_agent_id for link in links} == {
            "spec-finance", "spec-sales"}

    assert co._PENDING_COLLABORATION_KEY not in session
