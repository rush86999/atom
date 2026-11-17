# -*- coding: utf-8 -*-
"""Public HTTP contract for explicit specialist collaboration — scope/dataflow.

Test-only follow-ups to the frozen collaboration product commits
(``42d15b62c`` / ``e2b3fffd3``). No product file is edited.

The suite drives the REAL shipped public route through an actual FastAPI ASGI
app and ``TestClient``:

    POST /api/chat/message
      -> integrations.chat_routes.send_chat_message
      -> real get_current_user / real JWT validation / credential binding
      -> real ChatOrchestrator.process_chat_message
      -> real get_scoped_atom_agent / AtomMetaAgent construction (spied only;
         the shipped function is called with the authenticated scope)
      -> real governance, recruitment, DelegationChain/ChainLink, GenericAgent
         execution, fleet synthesis call and response composition
      -> durable ChatMessage assistant persistence

Only external LLM outputs are doubled (LLMService methods). The world-model/
LanceDB, MCP and reflection helpers are offline test doubles so no owner
memory, network or disk world is touched; their patch lifetime spans the real
atom factory and GenericAgent construction. Auth, permissions, governance,
fleet, recruitment, dispatch, orchestration and response composition are the
shipped implementations.

Every test uses a fresh absolute scratch SQLite file (TESTING=1 before app
imports). No owner/live DB, provider key, private runner/config/log/verifier
packet, Docker, download, build or shared server is used.
"""
from __future__ import annotations

import contextlib
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

# Absolute scratch URL before app imports. The per-test engine below is the
# actual store; pytest's conftest normally sets DATABASE_URL first, so this is
# only a standalone-run guard.
_SCRATCH_URL = (
    "sqlite:///" + str(Path(__file__).resolve().parent / ".http-collab-import.db")
)
os.environ.setdefault("DATABASE_URL", _SCRATCH_URL)

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.atom_meta_agent as ama
import core.auth as auth_mod
import core.chat_session_manager as csm
import core.database as dbmod
import core.generic_agent as ga
import core.llm_service as llm_service_mod
import integrations.chat_routes as chat_routes
from core import governance_cache as gc
from core.database import Base
from core.fleet_admiral import TaskAnalysis
from core.models import (
    AgentExecution, AgentRegistry, ChainLink, ChatMessage as ChatMessageModel,
    DelegationChain, FleetRoutingAudit, Tenant, User, Workspace,
)
from core.react_models import ReActStep
from core.recruitment_intelligence_service import RecruitmentPlan

MESSAGE = (
    "Analyze these synthetic Q3 facts with finance and sales specialists: "
    "closed revenue USD100, remaining pipeline USD200, target USD250. "
    "Compare closed revenue with target, identify the gap, and explain that "
    "pipeline is not closed revenue."
)
ORDINARY_MESSAGE = "Analyze these synthetic Q3 facts."

FINANCE = "A-FINANCE CONTRIBUTION: closed revenue USD100 is USD150 below the USD250 target."
SALES = "A-SALES CONTRIBUTION: remaining pipeline USD200 is not closed revenue."
B_FINANCE = "B-FINANCE CONTRIBUTION: actor B finance work."
B_SALES = "B-SALES CONTRIBUTION: actor B sales work."
FOREIGN_FINANCE = "FOREIGN-FINANCE CONTRIBUTION: foreign finance must not run."
FOREIGN_SALES = "FOREIGN-SALES CONTRIBUTION: foreign sales must not run."
ALL_MARKERS = (FINANCE, SALES, B_FINANCE, B_SALES,
               FOREIGN_FINANCE, FOREIGN_SALES)


class _Calls:
    def __init__(self):
        self.structured = []
        self.react = 0
        self.react_names = []
        self.raw = 0
        self.completions = 0
        self.interpretation = 0
        self.synthesis_texts = []

    @property
    def total(self):
        return (len(self.structured) + self.react + self.raw
                + self.completions)


def _agent(agent_id, name, category, workspace_id, user_id):
    return AgentRegistry(
        id=agent_id, name=name, display_name=name, category=category,
        module_path="core.generic_agent", class_name="GenericAgent",
        tenant_id="t-http", workspace_id=workspace_id, user_id=user_id,
        status="autonomous", enabled=True,
        capabilities=[category.lower()], specialty=category.lower())


@pytest.fixture()
def http_boundary(tmp_path, monkeypatch):
    """Real route/auth orchestrator over one fresh absolute scratch DB."""
    db_path = (tmp_path / "http-collab.db").resolve()
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    tenant_id = "t-http"
    user_a = User(
        id="u-a", tenant_id=tenant_id, email="a@example.test",
        hashed_password="http-a-credential", first_name="A", last_name="User",
        role="owner", status="active", workspace_id="w-a", is_active=True)
    user_b = User(
        id="u-b", tenant_id=tenant_id, email="b@example.test",
        hashed_password="http-b-credential", first_name="B", last_name="User",
        role="owner", status="active", workspace_id="w-b", is_active=True)
    db = Session()
    db.add_all([
        Tenant(id=tenant_id, name="HTTP", subdomain="http"),
        Workspace(id="w-a", name="A", tenant_id=tenant_id),
        Workspace(id="w-b", name="B", tenant_id=tenant_id),
        Workspace(id="w-foreign", name="Foreign", tenant_id=tenant_id),
        user_a, user_b,
        # Global meta-agent row: the shipped narrow global admission uses it
        # for every authenticated workspace. This is not a scope selector.
        AgentRegistry(
            id="atom_main", name="Atom", display_name="Atom",
            category="system", module_path="core.atom_meta_agent",
            class_name="AtomMetaAgent", tenant_id=tenant_id,
            workspace_id=None, status="autonomous", enabled=True,
            capabilities=["operations"], specialty="operations", user_id=None),
        _agent("a-finance", "Finance Analyst", "Finance", "w-a", "u-a"),
        _agent("a-sales", "Sales Analyst", "Sales", "w-a", "u-a"),
        _agent("b-finance", "B Finance Analyst", "Finance", "w-b", "u-b"),
        _agent("b-sales", "B Sales Analyst", "Sales", "w-b", "u-b"),
        _agent("c-finance", "Foreign Finance Analyst", "Finance",
               "w-foreign", "u-f"),
        _agent("c-sales", "Foreign Sales Analyst", "Sales",
               "w-foreign", "u-f"),
    ])
    db.commit()
    db.close()

    @contextlib.contextmanager
    def _scratch_db():
        session = Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _scratch_db_dependency():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    # ONE scoped factory through every module that opens its own session.
    monkeypatch.setattr(dbmod, "get_db_session", _scratch_db)
    monkeypatch.setattr(dbmod, "SessionLocal", Session)
    monkeypatch.setattr(dbmod, "get_db", _scratch_db_dependency)
    monkeypatch.setattr(dbmod, "engine", engine)
    monkeypatch.setattr(csm, "get_db_session", _scratch_db)
    monkeypatch.setattr(csm, "SessionLocal", Session)
    monkeypatch.setattr(ama, "SessionLocal", Session)
    monkeypatch.setattr(ga, "SessionLocal", Session)
    monkeypatch.setattr(ga, "get_db_session", _scratch_db)

    # Real session manager/session store redirected to the scratch DB.
    original_manager = chat_routes.chat_orchestrator.session_manager
    chat_routes.chat_orchestrator.session_manager = csm.ChatSessionManager(
        sessions_file=str((tmp_path / "chat_sessions.json").resolve()))
    chat_routes.chat_orchestrator.session_manager.use_db = True
    chat_routes.chat_orchestrator.conversation_sessions = {}

    # Offline external-service doubles. They stay installed across the real
    # atom factory calls and GenericAgent construction below.
    from unittest.mock import AsyncMock, MagicMock

    world = AsyncMock()
    world.recall_experiences = AsyncMock(return_value={
        "experiences": [], "knowledge": [], "formulas": [],
        "business_facts": []})
    world.record_experience = AsyncMock()
    mcp = AsyncMock()
    mcp.get_all_tools = AsyncMock(return_value=[])
    mcp.call_tool = AsyncMock(return_value="ok")
    monkeypatch.setattr(ama, "WorldModelService", lambda *a, **k: world)
    monkeypatch.setattr(ama, "mcp_service", mcp)
    monkeypatch.setattr(ama, "AdvancedWorkflowOrchestrator",
                        lambda *a, **k: MagicMock())
    monkeypatch.setattr(ga, "WorldModelService", lambda *a, **k: world)
    monkeypatch.setattr(ga, "mcp_service", mcp)

    # REAL scoped factories, spied only to prove the exact authenticated args.
    ama._atom_instance = None
    real_default = ama.get_atom_agent
    real_scoped = ama.get_scoped_atom_agent
    factory_calls = []

    def spy_default(workspace_id="default"):
        factory_calls.append({
            "kind": "default", "workspace_id": workspace_id,
            "tenant_id": None, "user_id": None})
        return real_default(workspace_id)

    def spy_scoped(workspace_id="default", tenant_id=None, user=None):
        factory_calls.append({
            "kind": "scoped", "workspace_id": workspace_id,
            "tenant_id": tenant_id,
            "user_id": getattr(user, "id", None)})
        return real_scoped(workspace_id, tenant_id, user)

    monkeypatch.setattr(ama, "get_atom_agent", spy_default)
    monkeypatch.setattr(ama, "get_scoped_atom_agent", spy_scoped)

    token_a = auth_mod.create_access_token(
        {"sub": user_a.id, "type": "access"}, user=user_a)
    token_b = auth_mod.create_access_token(
        {"sub": user_b.id, "type": "access"}, user=user_b)
    app = FastAPI()
    app.include_router(chat_routes.router)
    app.dependency_overrides[dbmod.get_db] = _scratch_db_dependency

    # Clear process-global governance decisions so one actor's cached allow
    # cannot mask another actor's scope.
    try:
        if gc._governance_cache is not None:
            gc._governance_cache.clear()
    except Exception:
        pass

    yield {
        "engine": engine,
        "Session": Session,
        "app": app,
        "token_a": token_a,
        "token_b": token_b,
        "tenant_id": tenant_id,
        "workspace_a": "w-a",
        "workspace_b": "w-b",
        "user_a": "u-a",
        "user_b": "u-b",
        "factory_calls": factory_calls,
    }

    # Do not leave the global orchestrator/session manager, atom singleton or
    # governance cache pointing at this test's world.
    chat_routes.chat_orchestrator.session_manager = original_manager
    chat_routes.chat_orchestrator.conversation_sessions = {}
    ama._atom_instance = None
    try:
        if gc._governance_cache is not None:
            gc._governance_cache.clear()
            task = getattr(gc._governance_cache, "_cleanup_task", None)
            if task is not None and not task.done():
                task.cancel()
    except Exception:
        pass
    try:
        engine.dispose()
    except Exception:
        pass


def _install_fake_llm(monkeypatch, *, mode: str):
    """Double external LLM outputs only; capture synthesis dataflow."""
    calls = _Calls()

    async def _structured_response(_self, *args, **kwargs):
        model = kwargs.get("response_model")
        name = getattr(model, "__name__", "")
        calls.structured.append(name)
        if name == "_Interpretation":
            calls.interpretation += 1
            if mode == "collaboration":
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
            return {
                "actions": [{"kind": "conversation"}],
                "subjects": [], "sources": [], "requested_fields": [],
                "output_format": "", "constraints": [],
                "scope_change": "replace", "confidence": 0.9,
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
            import core.chat_tool_planner as ctp
            return ctp.ToolPlan(
                use_tool=False,
                suggested_intent=(
                    "data_analysis" if mode == "collaboration"
                    else "search_request"),
                routing_confidence=0.8,
                reason="http boundary plan")
        if name == "RouteClassification":
            from ai.nlp_engine import RouteCategory, RouteClassification
            return RouteClassification(
                category=RouteCategory.KNOWLEDGE_QUERY,
                reasoning="HTTP collaboration boundary", confidence=0.9)
        if name == "CommandIntentResult":
            from ai.nlp_engine import CommandIntentResult, CommandType
            return CommandIntentResult(
                command_type=CommandType.SEARCH, platforms=[], entities=[],
                parameters={}, confidence=0.8, reasoning="ordinary search")
        return None

    async def _structured(_self, *args, **kwargs):
        model = kwargs.get("response_model")
        if getattr(model, "__name__", "") == "ReActStep":
            calls.react += 1
            blob = (
                f"{kwargs.get('system_instruction') or ''}\n"
                f"{kwargs.get('prompt') or ''}")
            # Exact marker order: foreign/B names before the A names they
            # contain as substrings.
            for marker, name in (
                (FOREIGN_FINANCE, "Foreign Finance Analyst"),
                (FOREIGN_SALES, "Foreign Sales Analyst"),
                (B_FINANCE, "B Finance Analyst"),
                (B_SALES, "B Sales Analyst"),
                (FINANCE, "Finance Analyst"),
                (SALES, "Sales Analyst"),
            ):
                if name in blob:
                    calls.react_names.append(name)
                    return ReActStep(thought=name, final_answer=marker)
            calls.react_names.append("unknown")
            return ReActStep(
                thought="specialist", final_answer="CONTRIBUTION: analysis.")
        return None

    async def _generate(_self, *args, **kwargs):
        calls.raw += 1
        return "Final answer: ordinary response."

    async def _completion(_self, *args, **kwargs):
        calls.completions += 1
        messages = kwargs.get("messages") or []
        text = "\n".join(
            str(m.get("content", "")) if isinstance(m, dict) else str(m)
            for m in messages)
        calls.synthesis_texts.append(text)
        # DATAFLOW PROOF: the final text is assembled from markers actually
        # present in the received synthesis prompt/messages. A prompt that
        # omitted a specialist's real finding yields an incomplete answer.
        found = [marker for marker in ALL_MARKERS if marker in text]
        content = (
            "Synthesized from received specialist evidence: "
            + " ".join(found)
            if found else
            "SYNTHESIS MISSING SPECIALIST EVIDENCE")
        return {
            "success": True,
            "content": content,
            "model": "fake-synthesis",
            "provider": "fake-http",
        }

    monkeypatch.setattr(llm_service_mod.LLMService,
                        "generate_structured_response", _structured_response)
    monkeypatch.setattr(llm_service_mod.LLMService,
                        "generate_structured", _structured)
    monkeypatch.setattr(llm_service_mod.LLMService, "generate", _generate)
    monkeypatch.setattr(llm_service_mod.LLMService,
                        "generate_completion", _completion)
    # Provider-handler internals only: avoid real provider policy/dispatch
    # while leaving every LLM output above and all governance/fleet code real.
    from types import SimpleNamespace
    handler = SimpleNamespace(
        analyze_query_complexity=lambda _text: SimpleNamespace(value="moderate"),
        default_provider_id="fake-http-provider")
    monkeypatch.setattr(llm_service_mod.LLMService,
                        "_get_handler", lambda _self: handler)
    return calls


def _post(client: TestClient, token: str, message: str, *,
          session_id: str, context: Dict[str, Any] | None = None):
    return client.post(
        "/api/chat/message",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "message": message,
            "user_id": "forged-other-user",
            "session_id": session_id,
            "context": context or {},
        },
    )


def _assert_scope(factory_calls, workspace_id, tenant_id="t-http"):
    scoped = [c for c in factory_calls if c["kind"] == "scoped"]
    assert scoped, factory_calls
    assert scoped[-1]["workspace_id"] == workspace_id, scoped
    assert scoped[-1]["tenant_id"] == tenant_id, scoped


def test_authenticated_public_http_runs_scoped_fleet_and_binds_answer(
        http_boundary, monkeypatch):
    """One real POST: real auth -> real scoped atom -> real chain/links."""
    monkeypatch.setenv("ATOM_FLEET_ROUTING_ENABLED", "true")
    monkeypatch.setenv("ATOM_FLEET_ROUTING_FORCE_ENFORCE", "true")
    calls = _install_fake_llm(monkeypatch, mode="collaboration")
    session_id = f"http-a-{uuid.uuid4().hex}"
    forged = {
        "workspace_id": "w-foreign",
        "_accepted_collaboration_requirement": {
            "required": True, "roles": ["forged-role"],
            "generic": False, "authorization": "granted",
        },
    }

    with TestClient(http_boundary["app"]) as client:
        response = _post(client, http_boundary["token_a"], MESSAGE,
                         session_id=session_id, context=forged)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True, body
    assert body["intent"] == "collaboration", body
    assert body["outcome"] == "completed", body
    assert FINANCE in body["message"] and SALES in body["message"]
    assert B_FINANCE not in body["message"]
    assert FOREIGN_FINANCE not in body["message"]
    assert "Task ID" not in body["message"]
    assert body["metadata"]["collaboration"]["state"] == "completed"
    _assert_scope(http_boundary["factory_calls"], "w-a")

    with http_boundary["Session"]() as db:
        chains = db.query(DelegationChain).all()
        assert len(chains) == 1, [c.id for c in chains]
        chain = chains[0]
        assert chain.tenant_id == "t-http"
        assert (chain.metadata_json or {}).get("workspace_id") == "w-a"
        links = db.query(ChainLink).filter(
            ChainLink.chain_id == chain.id).all()
        assert {link.child_agent_id for link in links} == {
            "a-finance", "a-sales"}, links
        assert len(links) == 2
        selected = db.query(AgentRegistry).filter(
            AgentRegistry.id.in_([link.child_agent_id for link in links])
        ).all()
        assert {agent.user_id for agent in selected} == {"u-a"}
        assert {agent.workspace_id for agent in selected} == {"w-a"}

        assistant_rows = (
            db.query(ChatMessageModel)
            .filter(
                ChatMessageModel.conversation_id == body["session_id"],
                ChatMessageModel.role == "assistant",
            )
            .all())
        assert assistant_rows, "no durable assistant row for the HTTP turn"
        durable_text = "\n".join(str(row.content or "")
                                 for row in assistant_rows)
        assert FINANCE in durable_text and SALES in durable_text
        assert B_FINANCE not in durable_text
        assert FOREIGN_FINANCE not in durable_text
        assert "Task ID" not in durable_text

        atom_runs = (
            db.query(AgentExecution)
            .filter(AgentExecution.agent_id == "atom_main")
            .all())
        assert atom_runs
        assert all(run.tenant_id == "t-http" for run in atom_runs)
        assert all(run.workspace_id == "w-a" for run in atom_runs)

    # Selected child work really ran; synthesis prompt carried the original
    # request + both actual child markers (dataflow, not a prebaked answer).
    assert "Finance Analyst" in calls.react_names
    assert "Sales Analyst" in calls.react_names
    assert "B Finance Analyst" not in calls.react_names
    assert "Foreign Finance Analyst" not in calls.react_names
    assert calls.synthesis_texts, "fleet synthesis was never called"
    synthesis_text = "\n".join(calls.synthesis_texts)
    assert MESSAGE in synthesis_text
    assert FINANCE in synthesis_text and SALES in synthesis_text
    assert B_FINANCE not in synthesis_text
    assert FOREIGN_FINANCE not in synthesis_text


def test_second_actor_gets_own_scope_agents_and_no_cross_session_leak(
        http_boundary, monkeypatch):
    """Two real actors; B's session cannot bind A, and vice versa."""
    monkeypatch.setenv("ATOM_FLEET_ROUTING_ENABLED", "true")
    monkeypatch.setenv("ATOM_FLEET_ROUTING_FORCE_ENFORCE", "true")
    calls = _install_fake_llm(monkeypatch, mode="collaboration")
    session_b = f"http-b-{uuid.uuid4().hex}"

    with TestClient(http_boundary["app"]) as client:
        response_b = _post(client, http_boundary["token_b"], MESSAGE,
                           session_id=session_b, context={})
        assert response_b.status_code == 200, response_b.text
        body_b = response_b.json()
        assert B_FINANCE in body_b["message"] and B_SALES in body_b["message"]
        assert FINANCE not in body_b["message"]
        assert FOREIGN_FINANCE not in body_b["message"]
        _assert_scope(http_boundary["factory_calls"], "w-b")

        with http_boundary["Session"]() as db:
            b_chains = db.query(DelegationChain).all()
            assert len(b_chains) == 1
            b_links = db.query(ChainLink).filter(
                ChainLink.chain_id == b_chains[0].id).all()
            assert {link.child_agent_id for link in b_links} == {
                "b-finance", "b-sales"}
            selected_b = db.query(AgentRegistry).filter(
                AgentRegistry.id.in_(
                    [link.child_agent_id for link in b_links])).all()
            assert {agent.user_id for agent in selected_b} == {"u-b"}
            assert {agent.workspace_id for agent in selected_b} == {"w-b"}
            b_durable = db.query(ChatMessageModel).filter(
                ChatMessageModel.conversation_id == body_b["session_id"],
                ChatMessageModel.role == "assistant").all()
            assert b_durable
            b_text = "\n".join(str(r.content or "") for r in b_durable)
            assert B_FINANCE in b_text
            b_message_id = str(b_durable[-1].id)
            b_message_content = str(b_durable[-1].content or "")

        # A uses B's session id + forged foreign workspace. The shipped
        # ownership logic creates a fresh A session internally. The response
        # envelope currently echoes the client-supplied B id (separate known
        # product bug, pinned by the xfail below), so this assertion proves
        # the durable safety property instead: A's answer is never written
        # into B's conversation, and B's row is untouched.
        response_a = _post(
            client, http_boundary["token_a"], MESSAGE,
            session_id=session_b, context={"workspace_id": "w-foreign"})
        assert response_a.status_code == 200, response_a.text
        body_a = response_a.json()
        assert FINANCE in body_a["message"] and SALES in body_a["message"]
        assert B_FINANCE not in body_a["message"]
        assert FOREIGN_FINANCE not in body_a["message"]
        _assert_scope(http_boundary["factory_calls"], "w-a")

        with http_boundary["Session"]() as db:
            b_row = db.query(ChatMessageModel).filter(
                ChatMessageModel.id == b_message_id).first()
            assert b_row is not None
            assert str(b_row.content or "") == b_message_content
            a_assistant_rows = [
                row for row in db.query(ChatMessageModel)
                .filter(ChatMessageModel.role == "assistant").all()
                if FINANCE in str(row.content or "")]
            assert a_assistant_rows, "A answer was not durably persisted"
            assert all(str(row.conversation_id) != session_b
                       for row in a_assistant_rows), (
                "A answer leaked into B's conversation")
            a_chains = [c for c in db.query(DelegationChain).all()
                        if (c.metadata_json or {}).get("workspace_id") == "w-a"]
            assert len(a_chains) == 1
            a_links = db.query(ChainLink).filter(
                ChainLink.chain_id == a_chains[0].id).all()
            assert {link.child_agent_id for link in a_links} == {
                "a-finance", "a-sales"}
            assert "b-finance" not in {
                link.child_agent_id for link in a_links}

    # B ran first, A second: both real scoped factory calls are visible.
    assert [c["workspace_id"] for c in http_boundary["factory_calls"]
            if c["kind"] == "scoped"][-2:] == ["w-b", "w-a"]


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Known public-route bug: when an authenticated user reuses another "
        "user's session id, ChatOrchestrator._get_or_create_session creates a "
        "fresh internal session but process_chat_message/the route still echo "
        "the client-supplied foreign session_id in the HTTP envelope. Durable "
        "data is isolated (A's assistant row is under the new id; B's row is "
        "untouched), but the envelope id is stale/foreign."))
def test_cross_user_session_id_is_not_reused_in_http_envelope(
        http_boundary, monkeypatch):
    monkeypatch.setenv("ATOM_FLEET_ROUTING_ENABLED", "true")
    monkeypatch.setenv("ATOM_FLEET_ROUTING_FORCE_ENFORCE", "true")
    _install_fake_llm(monkeypatch, mode="collaboration")
    session_b = f"http-xfail-b-{uuid.uuid4().hex}"

    with TestClient(http_boundary["app"]) as client:
        response_b = _post(client, http_boundary["token_b"], MESSAGE,
                           session_id=session_b, context={})
        assert response_b.status_code == 200, response_b.text
        response_a = _post(client, http_boundary["token_a"], MESSAGE,
                           session_id=session_b, context={})
        assert response_a.status_code == 200, response_a.text

    assert response_a.json()["session_id"] != session_b


def test_unauthenticated_http_fails_before_any_model_call(
        http_boundary, monkeypatch):
    calls = _install_fake_llm(monkeypatch, mode="collaboration")
    with TestClient(http_boundary["app"]) as client:
        response = client.post(
            "/api/chat/message",
            json={"message": MESSAGE, "user_id": "u-a",
                  "session_id": f"http-unauth-{uuid.uuid4().hex}",
                  "context": {}})

    assert response.status_code in (401, 403), response.text
    assert calls.total == 0, calls.structured
    with http_boundary["Session"]() as db:
        assert db.query(DelegationChain).count() == 0


@pytest.mark.parametrize("master,force,expected", [
    ("false", None, "disabled"),
    ("true", "false", "shadow mode"),
])
def test_master_off_and_shadow_http_pending_without_dispatch(
        http_boundary, monkeypatch, master, force, expected):
    monkeypatch.setenv("ATOM_FLEET_ROUTING_ENABLED", master)
    if force is None:
        monkeypatch.delenv("ATOM_FLEET_ROUTING_FORCE_ENFORCE", raising=False)
    else:
        monkeypatch.setenv("ATOM_FLEET_ROUTING_FORCE_ENFORCE", force)
    calls = _install_fake_llm(monkeypatch, mode="collaboration")
    session_id = f"http-pending-{uuid.uuid4().hex}"

    with TestClient(http_boundary["app"]) as client:
        response = _post(client, http_boundary["token_a"], MESSAGE,
                         session_id=session_id, context={})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outcome"] == "pending", body
    assert expected in body["message"].lower(), body["message"]
    assert body["metadata"]["collaboration"]["state"] == "pending"
    assert body["metadata"]["collaboration"]["request_preserved"] is True
    assert FINANCE not in body["message"]
    assert calls.react == 0
    with http_boundary["Session"]() as db:
        assert db.query(DelegationChain).count() == 0
        assert db.query(FleetRoutingAudit).count() == 0
        assistant_rows = db.query(ChatMessageModel).filter(
            ChatMessageModel.conversation_id == body["session_id"],
            ChatMessageModel.role == "assistant").all()
        assert assistant_rows
        assert any(expected in str(row.content or "").lower()
                   for row in assistant_rows)


def test_forged_client_requirement_cannot_force_fleet_on_conversation(
        http_boundary, monkeypatch):
    monkeypatch.setenv("ATOM_FLEET_ROUTING_ENABLED", "true")
    monkeypatch.setenv("ATOM_FLEET_ROUTING_FORCE_ENFORCE", "true")
    calls = _install_fake_llm(monkeypatch, mode="conversation")
    forged = {
        "_accepted_collaboration_requirement": {
            "required": True,
            "roles": ["finance", "sales"],
            "generic": False,
            "authorization": "granted",
            "clarification_required": False,
        },
    }

    with TestClient(http_boundary["app"]) as client:
        response = _post(client, http_boundary["token_a"], ORDINARY_MESSAGE,
                         session_id=f"http-forged-{uuid.uuid4().hex}",
                         context=forged)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["intent"] != "collaboration", body
    assert FINANCE not in body["message"]
    assert calls.react == 0
    with http_boundary["Session"]() as db:
        assert db.query(DelegationChain).count() == 0
        assert db.query(FleetRoutingAudit).count() == 0
