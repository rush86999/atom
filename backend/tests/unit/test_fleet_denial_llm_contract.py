"""Fleet denial + canonical LLM contract regressions.

These tests reproduce the observed negative (governance denial -> a nonexistent
``LLMService.generate_response`` -> AttributeError -> Queen/ReAct fallback) at
the public controller boundary, then lock the corrected contract:

  * enforced denial is terminal and durable, with no model/recruitment/tool
    dispatch and no Queen/ReAct escape;
  * governance unavailability fails closed in enforced mode;
  * ordinary CHAT and mentorship guidance use the canonical completion API,
    keep full messages and authenticated scope, and never publish a failure as
    an answer.

The fake LLM exposes ONLY the canonical ``LLMService`` surface
(``generate_completion`` / ``generate_structured_response``). It deliberately
has no ``generate_response`` attribute, so a regression fails loudly instead of
being hidden by a permissive AsyncMock.

All state is an own scratch SQLite file. No provider, network, credential or
live database is used.
"""
from __future__ import annotations

import os

os.environ.setdefault("TESTING", "1")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import (
    AgentExecution,
    AgentRegistry,
    AgentStatus,
    Tenant,
    User,
    UserRole,
    UserStatus,
    Workspace,
)

TASK = ("Analyze the quarterly operations backlog and prepare a short "
        "remediation note with one proposed next step.")


class CanonicalFakeLLM:
    """Minimal fake that matches the real LLMService text/structured surface."""

    def __init__(self, *, text="canonical reply", success=True):
        self.text = text
        self.success = success
        self.completion_calls: list[dict] = []
        self.structured_calls: list[dict] = []

    async def generate_completion(self, messages, model="auto", temperature=0.7,
                                  max_tokens=None, workspace_id=None,
                                  tenant_id=None, **kwargs):
        self.completion_calls.append({
            "messages": messages, "model": model,
            "temperature": temperature, "max_tokens": max_tokens,
            "workspace_id": workspace_id, "tenant_id": tenant_id,
            "kwargs": kwargs,
        })
        if not self.success:
            return {
                "success": False, "content": "", "text": "",
                "model": None, "provider": None,
                "finish_reason": None,
                "error": "provider unavailable",
                "failure": {"reason": "provider_unavailable",
                            "message": "provider unavailable"},
            }
        return {
            "success": True, "content": self.text, "text": self.text,
            "model": "fake-model", "provider": "fake-provider",
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1,
                      "total_tokens": 2},
        }

    async def generate_structured_response(self, **kwargs):
        self.structured_calls.append(kwargs)
        return kwargs.get("response_model")(**{}) if False else None


def _assert_canonical_surface(fake: CanonicalFakeLLM) -> None:
    assert not hasattr(fake, "generate_response"), (
        "the fake must not expose the nonexistent generate_response method")


@pytest.fixture()
def scratch(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'fleet-denial.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        db.add(Tenant(id="tenant-1", name="T", subdomain="t"))
        db.add(Workspace(id="ws-1", name="W", tenant_id="tenant-1"))
        db.add(User(
            id="user-1", email="u@example.invalid",
            hashed_password="synthetic", first_name="U", last_name="One",
            role=UserRole.SUPER_ADMIN.value, status=UserStatus.ACTIVE.value,
            is_active=True, tenant_id="tenant-1", workspace_id="ws-1",
        ))
        db.add(AgentRegistry(
            id="atom_main", name="Atom", category="Meta",
            module_path="offline.test", class_name="Atom",
            capabilities=[], enabled=True,
            status=AgentStatus.AUTONOMOUS.value, confidence_score=1.0,
            tenant_id="tenant-1", workspace_id=None,
        ))
        db.commit()
        user = db.query(User).filter(User.id == "user-1").one()

    import core.atom_meta_agent as ama
    monkeypatch.setattr(ama, "SessionLocal", Session, raising=False)
    # Fleet telemetry must never touch a live DB in this test.
    import core.fleet_orchestration.fleet_routing_stats as frs
    monkeypatch.setattr(frs, "record_fleet_decision",
                        lambda **kw: "audit-test", raising=False)
    monkeypatch.setattr(frs, "record_fleet_execution_outcome",
                        lambda **kw: None, raising=False)
    return {"Session": Session, "user": user, "ama": ama}


def _make_agent(scratch, fake_llm, *, monkeypatch):
    ama = scratch["ama"]
    wm = AsyncMock()
    wm.recall_experiences = AsyncMock(return_value={
        "experiences": [], "knowledge": [], "formulas": [],
        "business_facts": []})
    wm.record_experience = AsyncMock()
    mcp = AsyncMock()
    mcp.get_all_tools = AsyncMock(return_value=[])
    mcp.call_tool = AsyncMock(return_value="ok")
    with patch("core.atom_meta_agent.WorldModelService", return_value=wm), \
         patch("core.atom_meta_agent.mcp_service", mcp), \
         patch("core.service_factory.ServiceFactory.get_llm_service",
               return_value=fake_llm), \
         patch("core.atom_meta_agent.AdvancedWorkflowOrchestrator"), \
         patch("core.atom_meta_agent.CapabilityGraduationService"), \
         patch("core.atom_meta_agent.SessionLocal", scratch["Session"]):
        agent = ama.AtomMetaAgent(workspace_id="ws-1",
                                  tenant_id="tenant-1",
                                  user=scratch["user"])
    agent.world_model = wm
    agent.mcp = mcp
    agent.llm = fake_llm
    return agent


def _force_one_off(monkeypatch):
    from ai.nlp_engine import RouteCategory
    route = MagicMock()
    route.category = RouteCategory.ONE_OFF
    route.reasoning = "one-off task"
    monkeypatch.setattr(
        "core.atom_meta_agent.NaturalLanguageEngine",
        lambda: MagicMock(classify_route=AsyncMock(return_value=route)),
    )


@pytest.fixture(autouse=True)
def _flags(monkeypatch):
    monkeypatch.setenv("ATOM_FLEET_ROUTING_ENABLED", "true")
    monkeypatch.setenv("ATOM_FLEET_ROUTING_FORCE_ENFORCE", "true")
    import core.atom_meta_agent as ama
    monkeypatch.setattr(ama, "_TURN_FACT_EXTRACTION_ENABLED", False)
    monkeypatch.setattr(ama, "_TURN_FACT_VECTOR_RECALL_ENABLED", False)


@pytest.mark.asyncio
async def test_enforced_governance_denial_is_terminal_and_durable(
        scratch, monkeypatch):
    """Retained negative twin, now terminal at the public controller boundary."""
    from api.agent_routes import AtomExecuteRequest, execute_atom

    fake = CanonicalFakeLLM()
    _assert_canonical_surface(fake)
    agent = _make_agent(scratch, fake, monkeypatch=monkeypatch)
    _force_one_off(monkeypatch)

    agent._check_governance = AsyncMock(
        return_value=(False, "Agent not found"))
    dispatch = AsyncMock(side_effect=AssertionError(
        "specialist dispatch must not run on a governance denial"))
    agent._execute_fleet_specialists = dispatch
    queen = MagicMock()
    queen.generate_blueprint = AsyncMock(side_effect=AssertionError(
        "Queen must not plan an enforced denied task"))
    agent.queen = queen

    monkeypatch.setattr(scratch["ama"], "AtomMetaAgent",
                        lambda *a, **k: agent)

    response = await execute_atom(
        AtomExecuteRequest(request=TASK), user=scratch["user"])
    data = response["data"]

    assert data["status"] == "denied"
    assert data["success"] is False
    assert data["failure_reason"] == "governance_denied"
    assert data["handler"] == "governance"
    assert data["specialists_count"] == 0
    assert data["chain_id"] is None
    assert "Agent not found" in data["final_output"]
    assert "No task, recruitment, specialist or tool work" in data["final_output"]

    dispatch.assert_not_awaited()
    queen.generate_blueprint.assert_not_awaited()
    assert fake.completion_calls == []
    assert fake.structured_calls == []

    with scratch["Session"]() as db:
        rows = db.query(AgentExecution).all()
        assert len(rows) == 1
        assert rows[0].status == "failed"
        assert rows[0].id == data["execution_id"]


@pytest.mark.asyncio
async def test_governance_unavailable_fails_closed(scratch, monkeypatch):
    from api.agent_routes import AtomExecuteRequest, execute_atom

    fake = CanonicalFakeLLM()
    agent = _make_agent(scratch, fake, monkeypatch=monkeypatch)
    _force_one_off(monkeypatch)
    agent._check_governance = AsyncMock(
        side_effect=RuntimeError("governance store unavailable"))
    dispatch = AsyncMock(side_effect=AssertionError("must not dispatch"))
    agent._execute_fleet_specialists = dispatch
    agent.queen = MagicMock()
    agent.queen.generate_blueprint = AsyncMock(
        side_effect=AssertionError("must not fall back to Queen"))
    monkeypatch.setattr(scratch["ama"], "AtomMetaAgent",
                        lambda *a, **k: agent)

    response = await execute_atom(
        AtomExecuteRequest(request=TASK), user=scratch["user"])
    data = response["data"]

    assert data["status"] == "partial"
    assert data["success"] is False
    assert data["outcome"] == "partial_unknown"
    assert data["failure_reason"] == "fleet_routing_interrupted"
    assert data["execution_attempted"] is True
    assert data["specialists_count"] is None
    assert "Some preparation may already have started" in data["final_output"]
    assert "RuntimeError" not in data["final_output"]
    assert "No task, recruitment, specialist or tool work" not in data["final_output"]
    dispatch.assert_not_awaited()
    assert fake.completion_calls == []
    with scratch["Session"]() as db:
        execution = db.query(AgentExecution).one()
        assert execution.status == "failed"
        assert "partial_unknown" in (execution.error_message or "")


@pytest.mark.asyncio
async def test_allowed_task_still_reaches_real_recruitment(scratch, monkeypatch):
    """The denial fix must not block an allowed TASK from real routing."""
    from core.intent_classifier import (
        IntentCategory, IntentClassification,
    )

    fake = CanonicalFakeLLM()
    agent = _make_agent(scratch, fake, monkeypatch=monkeypatch)
    agent._check_governance = AsyncMock(return_value=(True, None))
    fleet = MagicMock()
    fleet.recruit_and_execute = AsyncMock(return_value={
        "chain_id": "chain-allowed", "specialists_count": 1,
        "specialists": [{"agent_id": "a1"}]})
    monkeypatch.setattr("core.fleet_admiral.FleetAdmiral",
                        MagicMock(return_value=fleet), raising=False)
    intent = IntentClassification(
        category=IntentCategory.TASK, confidence=0.9, reasoning="task",
        requires_execution=True, suggested_handler="fleet_admiral",
    )
    result = await agent.route_with_governance(TASK, intent, "user-1")
    assert result["governance_allowed"] is True
    assert result["route"] == "TASK"
    fleet.recruit_and_execute.assert_awaited()
    assert fake.completion_calls == []


@pytest.mark.asyncio
async def test_chat_uses_canonical_contract_and_preserves_scope(scratch,
                                                               monkeypatch):
    fake = CanonicalFakeLLM(text="hello operator")
    agent = _make_agent(scratch, fake, monkeypatch=monkeypatch)
    result = await agent._route_to_chat("hello", "user-1")

    assert result["status"] == "chat_complete"
    assert result["success"] is True
    assert result["response"] == "hello operator"
    assert result["model"] == "fake-model"
    assert result["provider"] == "fake-provider"
    assert result["finish_reason"] == "stop"
    call = fake.completion_calls[0]
    assert call["messages"] == [
        {"role": "system", "content": "You are a helpful AI assistant."},
        {"role": "user", "content": "hello"},
    ]
    assert call["workspace_id"] == "ws-1"
    assert call["tenant_id"] == "tenant-1"


@pytest.mark.asyncio
async def test_chat_failure_is_not_published_as_an_answer(scratch, monkeypatch):
    fake = CanonicalFakeLLM(success=False)
    agent = _make_agent(scratch, fake, monkeypatch=monkeypatch)
    result = await agent._route_to_chat("hello", "user-1")

    assert result["status"] == "chat_unavailable"
    assert result["success"] is False
    assert result["error"] == "provider_unavailable"
    assert result["response"].startswith("I couldn't generate a response")
    assert "provider is unavailable" in result["response"]
    assert result["failure"]["reason"] == "provider_unavailable"


@pytest.mark.asyncio
async def test_guidance_failure_is_deterministic(scratch, monkeypatch):
    fake = CanonicalFakeLLM(success=False)
    agent = _make_agent(scratch, fake, monkeypatch=monkeypatch)
    with patch("core.atom_meta_agent.SessionLocal", scratch["Session"]):
        text = await agent.generate_mentorship_guidance(
            "student-1", "create_record", {}, "needs approval")
    assert "guidance is unavailable" in text
    assert "remains blocked" in text
    assert fake.completion_calls
    assert "provider unavailable" not in text


@pytest.mark.asyncio
async def test_partial_preparation_after_real_chain_is_truthful(
        scratch, monkeypatch):
    """A routing exception after a real committed chain is not "zero work"."""
    from api.agent_routes import AtomExecuteRequest, execute_atom
    from core.agent_fleet_service import AgentFleetService
    from core.models import DelegationChain

    fake = CanonicalFakeLLM()
    agent = _make_agent(scratch, fake, monkeypatch=monkeypatch)
    _force_one_off(monkeypatch)
    prepared: list[str] = []

    async def partial_route(request, intent, user_id, agent_id="atom_main",
                            execution_id=None):
        with scratch["Session"]() as db:
            chain = AgentFleetService(db).initialize_fleet(
                tenant_id="tenant-1", root_agent_id="atom_main",
                root_task=request, root_execution_id=execution_id)
            prepared.append(chain.id)
        raise RuntimeError("synthetic interruption after initialization")

    agent.route_with_governance = partial_route
    agent._execute_fleet_specialists = AsyncMock(
        side_effect=AssertionError("must not dispatch"))
    agent.queen = MagicMock()
    agent.queen.generate_blueprint = AsyncMock(
        side_effect=AssertionError("must not fall back to Queen"))
    monkeypatch.setattr(scratch["ama"], "AtomMetaAgent",
                        lambda *a, **k: agent)

    response = await execute_atom(
        AtomExecuteRequest(request=TASK), user=scratch["user"])
    data = response["data"]

    assert data["status"] == "partial"
    assert data["outcome"] == "partial_unknown"
    assert data["execution_attempted"] is True
    assert data["chain_id"] == prepared[0]
    assert data["chain_recovered"] is True
    assert data["specialists_count"] is None
    assert "Some preparation may already have started" in data["final_output"]
    assert "RuntimeError" not in data["final_output"]
    assert "synthetic interruption" not in data["final_output"]
    assert "No task, recruitment, specialist or tool work" not in data["final_output"]

    with scratch["Session"]() as db:
        assert db.query(DelegationChain).filter(
            DelegationChain.id == prepared[0]).count() == 1
        execution = db.query(AgentExecution).one()
        assert execution.status == "failed"
        assert "partial_unknown" in (execution.error_message or "")
        assert "Some preparation may already have started" in (
            execution.result_summary or "")
    assert fake.completion_calls == []


def test_completion_text_outcome_rejects_non_string_content():
    from core.atom_meta_agent import _completion_text_outcome

    for bad in ({"error": "synthetic-not-an-answer"}, ["x"], True, 7, 1.5):
        text, failure = _completion_text_outcome(
            {"success": True, "content": bad})
        assert text is None
        assert failure["reason"] == "invalid_completion_content"

    # Both canonical text keys as strings: accepted, content preferred.
    assert _completion_text_outcome(
        {"success": True, "content": "a", "text": "b"}) == ("a", None)
    # Legacy text-only string is still accepted.
    assert _completion_text_outcome(
        {"success": True, "text": "b"}) == ("b", None)
    # Whitespace-only is an empty generation, not text.
    assert _completion_text_outcome(
        {"success": True, "content": "  "})[1]["reason"] == "empty_generation"
    # A typed failure is preserved verbatim.
    typed = {"reason": "provider_unavailable", "message": "unavailable"}
    assert _completion_text_outcome(
        {"success": False, "failure": typed}) == (None, typed)
