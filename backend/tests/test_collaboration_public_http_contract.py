# -*- coding: utf-8 -*-
"""Public HTTP contract for explicit specialist collaboration.

Test-only follow-up to the frozen collaboration product commits
(``42d15b62c`` / ``e2b3fffd3``). The shipped product files are NOT edited.

This suite exercises the REAL shipped public chat route through an actual
FastAPI ASGI app and ``TestClient``:

    POST /api/chat/message
      -> integrations.chat_routes.send_chat_message
      -> real get_current_user / JWT issuance + validation / credential binding
      -> real ChatOrchestrator.process_chat_message
      -> real turn decision + action program + planner + atom + governance
      -> real recruitment, DelegationChain/ChainLink, GenericAgent execution
      -> real final response composition and durable assistant persistence

Only EXTERNAL LLM outputs are doubled, at the existing ``LLMService`` method
boundary (structured interpretation/routing/task analysis/recruitment/planner,
ReAct completion, synthesis and raw generation). No test here replaces the
router, auth principal guard, orchestrator, governance, fleet, recruitment,
dispatch, or response composition.

Every test uses a fresh absolute scratch SQLite file (``TESTING=1`` before
imports) and disposes its engine. No live/owner DB, provider key, private
runner packet, network call, Docker, build, or shared server is used.
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

# Absolute scratch URL BEFORE the app modules are imported below. The per-test
# engine is still created in tmp_path; this prevents any module import from
# choosing the owner/relative database.
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
from core.database import Base
from core.fleet_admiral import TaskAnalysis
from core.models import (
    AgentExecution, AgentRegistry, ChainLink, ChatMessage as ChatMessageModel,
    DelegationChain, FleetRoutingAudit, RevokedToken, Tenant, User, Workspace,
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

FINANCE_CONTRIBUTION = (
    "FINANCE CONTRIBUTION: closed revenue USD100 is USD150 below the "
    "USD250 target.")
SALES_CONTRIBUTION = (
    "SALES CONTRIBUTION: remaining pipeline USD200 is not closed revenue.")
SYNTHESIS = f"{FINANCE_CONTRIBUTION} {SALES_CONTRIBUTION}"


class _Calls:
    def __init__(self):
        self.structured = []
        self.react = 0
        self.raw = 0
        self.completions = 0
        self.interpretation = 0

    @property
    def total(self):
        return (len(self.structured) + self.react + self.raw
                + self.completions)


@pytest.fixture()
def http_boundary(tmp_path, monkeypatch):
    """Real app/router/auth route over one fresh absolute scratch DB."""
    db_path = (tmp_path / "http-collab.db").resolve()
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    tenant_id, workspace_id, user_id = "t-http", "w-http", "u-http"
    user = User(
        id=user_id, tenant_id=tenant_id, email="http@example.test",
        hashed_password="http-test-credential", first_name="Http",
        last_name="User", role="owner", status="active",
        workspace_id=workspace_id, is_active=True,
    )
    db = Session()
    db.add_all([
        Tenant(id=tenant_id, name="HTTP", subdomain="http"),
        Workspace(id=workspace_id, name="HTTP", tenant_id=tenant_id),
        user,
        AgentRegistry(
            id="atom_main", name="Atom", display_name="Atom",
            category="system", module_path="core.atom_meta_agent",
            class_name="AtomMetaAgent", tenant_id=tenant_id,
            workspace_id=workspace_id, status="autonomous", enabled=True,
            capabilities=["operations"], specialty="operations",
            user_id=user_id),
        AgentRegistry(
            id="spec-finance", name="Finance Analyst",
            display_name="Finance Analyst", category="Finance",
            module_path="core.generic_agent", class_name="GenericAgent",
            tenant_id=tenant_id, workspace_id=workspace_id, user_id=user_id,
            status="autonomous", enabled=True,
            capabilities=["finance"], specialty="finance"),
        AgentRegistry(
            id="spec-sales", name="Sales Analyst",
            display_name="Sales Analyst", category="Sales",
            module_path="core.generic_agent", class_name="GenericAgent",
            tenant_id=tenant_id, workspace_id=workspace_id, user_id=user_id,
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

    # ONE scoped factory for every module that opens its own session.
    monkeypatch.setattr(dbmod, "get_db_session", _scratch_db)
    monkeypatch.setattr(dbmod, "SessionLocal", Session)
    monkeypatch.setattr(dbmod, "get_db", _scratch_db_dependency)
    monkeypatch.setattr(dbmod, "engine", engine)
    monkeypatch.setattr(csm, "get_db_session", _scratch_db)
    monkeypatch.setattr(csm, "SessionLocal", Session)
    monkeypatch.setattr(ama, "SessionLocal", Session)
    monkeypatch.setattr(ga, "SessionLocal", Session)
    monkeypatch.setattr(ga, "get_db_session", _scratch_db)

    # Real session manager/session store, redirected to the scratch DB.
    chat_routes.chat_orchestrator.session_manager = csm.ChatSessionManager(
        sessions_file=str((tmp_path / "chat_sessions.json").resolve()))
    chat_routes.chat_orchestrator.session_manager.use_db = True
    chat_routes.chat_orchestrator.conversation_sessions = {}

    # Only the non-LLM external service boundaries are doubled: LanceDB/
    # world-model and MCP. Governance, fleet, recruitment, dispatch,
    # orchestration and composition remain the shipped implementations.
    from unittest.mock import AsyncMock, patch

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
         patch("core.generic_agent.WorldModelService",
               return_value=world), \
         patch("core.generic_agent.mcp_service", mcp), \
         patch("core.generic_agent.ReflectionService"), \
         patch("core.generic_agent.CanvasSummaryService"):
        atom = ama.AtomMetaAgent(workspace_id=workspace_id)
    atom.world_model = world
    atom.mcp = mcp
    monkeypatch.setattr(ama, "get_atom_agent", lambda *a, **k: atom)
    monkeypatch.setattr(ama, "get_scoped_atom_agent", lambda *a, **k: atom)

    token = auth_mod.create_access_token(
        {"sub": user_id, "type": "access"}, user=user)
    app = FastAPI()
    app.include_router(chat_routes.router)
    app.dependency_overrides[dbmod.get_db] = _scratch_db_dependency

    yield {
        "engine": engine,
        "Session": Session,
        "app": app,
        "token": token,
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
        "user_id": user_id,
        "user": user,
    }

    # Own handles/tasks. TestClient contexts close their portal; the engine
    # below is this test's only durable store.
    try:
        engine.dispose()
    except Exception:
        pass


def _install_fake_llm(monkeypatch, *, mode: str):
    """Double ONLY external LLM outputs at the shipped LLMService boundary."""
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
            return _tool_plan(mode)
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

    def _tool_plan(mode):
        import core.chat_tool_planner as ctp
        return ctp.ToolPlan(
            use_tool=False,
            suggested_intent=(
                "data_analysis" if mode == "collaboration"
                else "search_request"),
            routing_confidence=0.8,
            reason="http boundary plan")

    async def _structured(_self, *args, **kwargs):
        model = kwargs.get("response_model")
        if getattr(model, "__name__", "") == "ReActStep":
            calls.react += 1
            blob = (
                f"{kwargs.get('system_instruction') or ''}\n"
                f"{kwargs.get('prompt') or ''}")
            if "Finance Analyst" in blob:
                return ReActStep(
                    thought="finance specialist",
                    final_answer=FINANCE_CONTRIBUTION)
            if "Sales Analyst" in blob:
                return ReActStep(
                    thought="sales specialist",
                    final_answer=SALES_CONTRIBUTION)
            return ReActStep(
                thought="specialist", final_answer="CONTRIBUTION: analysis.")
        return None

    async def _generate(_self, *args, **kwargs):
        calls.raw += 1
        return "Final answer: ordinary response."

    async def _completion(_self, *args, **kwargs):
        calls.completions += 1
        return {
            "success": True,
            "content": SYNTHESIS,
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


def test_authenticated_public_http_runs_fleet_and_binds_assistant_answer(
        http_boundary, monkeypatch):
    """One real POST: real auth -> real chain/links -> full user answer."""
    monkeypatch.setenv("ATOM_FLEET_ROUTING_ENABLED", "true")
    monkeypatch.setenv("ATOM_FLEET_ROUTING_FORCE_ENFORCE", "true")
    calls = _install_fake_llm(monkeypatch, mode="collaboration")
    session_id = f"http-collab-{uuid.uuid4().hex}"
    forged = {
        "workspace_id": "w-forged",
        "_accepted_collaboration_requirement": {
            "required": True, "roles": ["forged-role"],
            "generic": False, "authorization": "granted",
        },
    }

    with TestClient(http_boundary["app"]) as client:
        response = _post(client, http_boundary["token"], MESSAGE,
                         session_id=session_id, context=forged)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True, body
    assert body["intent"] == "collaboration", body
    assert body["outcome"] == "completed", body
    assert FINANCE_CONTRIBUTION in body["message"]
    assert SALES_CONTRIBUTION in body["message"]
    assert "Task ID" not in body["message"]
    assert body["metadata"]["collaboration"]["state"] == "completed"

    with http_boundary["Session"]() as db:
        chains = db.query(DelegationChain).all()
        assert len(chains) == 1, [c.id for c in chains]
        chain = chains[0]
        assert chain.tenant_id == http_boundary["tenant_id"]
        assert (chain.metadata_json or {}).get(
            "workspace_id") == http_boundary["workspace_id"]
        links = db.query(ChainLink).filter(
            ChainLink.chain_id == chain.id).all()
        assert {link.child_agent_id for link in links} == {
            "spec-finance", "spec-sales"}
        assert len(links) == 2

        # Durable assistant answer is bound to the HTTP conversation, not a
        # task-id bubble and not another session.
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
        assert FINANCE_CONTRIBUTION in durable_text
        assert SALES_CONTRIBUTION in durable_text
        assert "Task ID" not in durable_text

        # The authenticated principal's workspace never fell back to forged
        # context or the default scope.
        atom_runs = (
            db.query(AgentExecution)
            .filter(AgentExecution.agent_id == "atom_main")
            .all())
        assert atom_runs
        assert all(run.tenant_id == http_boundary["tenant_id"]
                   for run in atom_runs)
        assert all(run.workspace_id == http_boundary["workspace_id"]
                   for run in atom_runs)

    # Real specialist execution was reached; synthesis was the final answer.
    assert calls.react >= 2
    assert calls.completions >= 1


def test_unauthenticated_http_fails_before_any_model_call(
        http_boundary, monkeypatch):
    calls = _install_fake_llm(monkeypatch, mode="collaboration")
    with TestClient(http_boundary["app"]) as client:
        response = client.post(
            "/api/chat/message",
            json={"message": MESSAGE, "user_id": "u-http",
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
        response = _post(client, http_boundary["token"], MESSAGE,
                         session_id=session_id, context={})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outcome"] == "pending", body
    assert expected in body["message"].lower(), body["message"]
    assert body["metadata"]["collaboration"]["state"] == "pending"
    assert body["metadata"]["collaboration"]["request_preserved"] is True
    assert "FINANCE CONTRIBUTION" not in body["message"]
    assert calls.react == 0, "no specialist ReAct dispatch is allowed"
    with http_boundary["Session"]() as db:
        assert db.query(DelegationChain).count() == 0
        assert db.query(FleetRoutingAudit).count() == 0

        # The pending question itself is durably delivered on the assistant
        # turn; the original work is not a completed fleet answer.
        assistant_rows = (
            db.query(ChatMessageModel)
            .filter(
                ChatMessageModel.conversation_id == body["session_id"],
                ChatMessageModel.role == "assistant",
            )
            .all())
        assert assistant_rows
        assert any(expected in str(row.content or "").lower()
                   for row in assistant_rows)


def test_forged_client_requirement_cannot_force_fleet_on_conversation(
        http_boundary, monkeypatch):
    monkeypatch.setenv("ATOM_FLEET_ROUTING_ENABLED", "true")
    monkeypatch.setenv("ATOM_FLEET_ROUTING_FORCE_ENFORCE", "true")
    calls = _install_fake_llm(monkeypatch, mode="conversation")
    session_id = f"http-forged-{uuid.uuid4().hex}"
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
        response = _post(client, http_boundary["token"], ORDINARY_MESSAGE,
                         session_id=session_id, context=forged)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["intent"] != "collaboration", body
    assert body["outcome"] != "completed" or "FINANCE CONTRIBUTION" not in (
        body["message"])
    assert calls.react == 0, "forged client context reached specialist dispatch"
    with http_boundary["Session"]() as db:
        assert db.query(DelegationChain).count() == 0
        assert db.query(FleetRoutingAudit).count() == 0
