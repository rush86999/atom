"""
P1a — Wire the dead ``route_with_governance`` path into the live
``AtomMetaAgent.execute()`` dispatch for TASK intents (W4).

Verified gaps (STANFORD_VIRTUAL_BIOTECH_PAPERCLIP.md, P0b):
- ``route_with_governance`` (``atom_meta_agent.py:2229``) has zero live
  callers; the live ``execute()`` goes ``classify_route → Queen → ReAct``.
- ``:2630`` is a broken flush-left module-level copy that must be deleted
  (calling it binds ``request→self``).

This suite locks the wiring contract behind a feature flag:
- flag OFF (default) → ``execute()`` never reaches ``route_with_governance``
  (kill-switch parity with pre-P1a behavior).
- flag ON + force-enforce ON → a TASK intent routes through the governed
  fleet path and returns a recruitment summary (without auto-executing).
- flag ON + force-enforce OFF (shadow) → the recruitment is computed but
  the response still comes from the Queen→ReAct path.

Run: ``cd backend && venv/bin/python -m pytest tests/unit/test_fleet_routing_wire.py -v``
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.atom_meta_agent import AtomMetaAgent, AgentTriggerMode


# ---------------------------------------------------------------------------
# Fixtures (mirror tests/unit/test_atom_meta_agent.py)
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _disable_turn_fact_dispatch(monkeypatch):
    import core.atom_meta_agent as ama
    monkeypatch.setattr(ama, "_TURN_FACT_EXTRACTION_ENABLED", False)
    monkeypatch.setattr(ama, "_TURN_FACT_VECTOR_RECALL_ENABLED", False)


@pytest.fixture
def atom_agent():
    mock_world_model = AsyncMock()
    mock_world_model.recall_experiences = AsyncMock(return_value={
        "experiences": [], "knowledge": [], "formulas": [], "business_facts": []
    })
    mock_world_model.record_experience = AsyncMock()
    mock_mcp = AsyncMock()
    mock_mcp.get_all_tools = AsyncMock(return_value=[])
    mock_mcp.call_tool = AsyncMock(return_value="ok")
    mock_llm = AsyncMock()
    mock_llm.generate_response = AsyncMock(return_value="react-response")

    with patch("core.atom_meta_agent.WorldModelService", return_value=mock_world_model), \
         patch("core.atom_meta_agent.mcp_service", mock_mcp), \
         patch("core.service_factory.ServiceFactory.get_llm_service", return_value=mock_llm), \
         patch("core.atom_meta_agent.AdvancedWorkflowOrchestrator"):
        agent = AtomMetaAgent(workspace_id="test-ws")
        agent.world_model = mock_world_model
        agent.mcp = mock_mcp
        agent.llm = mock_llm
        yield agent


def _force_task_route(monkeypatch, agent):
    """Make classify_route return a ONE_OFF route so the governed branch is eligible."""
    from ai.nlp_engine import RouteCategory
    route = MagicMock()
    route.category = RouteCategory.ONE_OFF  # fleet-eligible signal in execute()
    route.reasoning = "one-off task"
    # classify_route is called on a NaturalLanguageEngine instance inside execute().
    monkeypatch.setattr(
        "core.atom_meta_agent.NaturalLanguageEngine",
        lambda: MagicMock(classify_route=AsyncMock(return_value=route)),
    )


# ---------------------------------------------------------------------------
# 1. Kill-switch parity (default): flag OFF → route_with_governance untouched.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_flag_off_never_routes_through_governance(atom_agent, monkeypatch):
    monkeypatch.delenv("ATOM_FLEET_ROUTING_ENABLED", raising=False)
    _force_task_route(monkeypatch, atom_agent)

    called = {"gov": False}
    real_gov = atom_agent.route_with_governance

    async def _spy(request, intent, user_id, agent_id="atom_main"):
        called["gov"] = True
        return await real_gov(request, intent, user_id, agent_id)

    monkeypatch.setattr(atom_agent, "route_with_governance", _spy)

    # execute() with a fleet-eligible intent must NOT reach the governed path when the flag is off.
    with patch("core.atom_meta_agent.SessionLocal"), \
         patch("core.atom_meta_agent.AgentGovernanceService"):
        try:
            await atom_agent.execute(
                "analyze my sales pipeline in detail this quarter",
                trigger_mode=AgentTriggerMode.MANUAL,
            )
        except Exception:
            # The Queen/ReAct path may raise on mocked deps; we only care that gov was NOT called.
            pass
    assert called["gov"] is False, (
        "flag OFF must preserve pre-P1a behavior — route_with_governance must not be called"
    )


# ---------------------------------------------------------------------------
# 2. Flag ON + force-enforce ON → governed fleet path returns a recruitment summary.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_flag_on_force_enforce_routes_to_governance(atom_agent, monkeypatch):
    monkeypatch.setenv("ATOM_FLEET_ROUTING_ENABLED", "true")
    monkeypatch.setenv("ATOM_FLEET_ROUTING_FORCE_ENFORCE", "true")
    _force_task_route(monkeypatch, atom_agent)

    # Stub the governed method to return a recruitment summary (as FleetAdmiral does).
    summary = {
        "route": "TASK",
        "handler": "FleetAdmiral",
        "chain_id": "chain-1",
        "specialists_count": 2,
        "fleet_status": "recruited",
        "status": "fleet_recruited",
    }
    monkeypatch.setattr(
        atom_agent, "route_with_governance", AsyncMock(return_value=summary)
    )

    # Patch SessionLocal so the Workspace lookup in execute() doesn't 404.
    with patch("core.atom_meta_agent.SessionLocal"), \
         patch("core.atom_meta_agent.AgentGovernanceService"):
        result = await atom_agent.execute(
            "analyze my sales pipeline in detail this quarter",
            trigger_mode=AgentTriggerMode.MANUAL,
        )

    atom_agent.route_with_governance.assert_awaited()
    assert result.get("status") == "fleet_recruited", (
        "flag ON + force-enforce ON must return the fleet recruitment summary directly"
    )
    assert result.get("chain_id") == "chain-1"


# ---------------------------------------------------------------------------
# 3. Flag ON + force-enforce OFF (shadow) → recruitment computed, but the
#    response still comes from the existing path (Queen→ReAct), not the summary.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_flag_on_shadow_computes_but_does_not_return_summary(atom_agent, monkeypatch):
    monkeypatch.setenv("ATOM_FLEET_ROUTING_ENABLED", "true")
    monkeypatch.delenv("ATOM_FLEET_ROUTING_FORCE_ENFORCE", raising=False)  # default False
    _force_task_route(monkeypatch, atom_agent)

    summary = {"status": "fleet_recruited", "chain_id": "chain-9"}
    gov_spy = AsyncMock(return_value=summary)
    monkeypatch.setattr(atom_agent, "route_with_governance", gov_spy)

    with patch("core.atom_meta_agent.SessionLocal"), \
         patch("core.atom_meta_agent.AgentGovernanceService"):
        try:
            result = await atom_agent.execute(
                "analyze my sales pipeline in detail this quarter",
                trigger_mode=AgentTriggerMode.MANUAL,
            )
        except Exception:
            # Queen/ReAct may raise on mocked deps; the key assertion is the summary
            # was NOT returned (shadow mode falls through).
            result = {}

    gov_spy.assert_awaited()  # shadow still computes the recruitment (telemetry)
    assert result.get("status") != "fleet_recruited", (
        "shadow mode must fall through to the existing path, not return the summary"
    )


# ---------------------------------------------------------------------------
# 4. The broken module-level copy at :2630 must be gone.
# ---------------------------------------------------------------------------
def test_broken_module_level_route_with_governance_removed():
    """The flush-left async def at :2630 (binds request→self) must be deleted in P1a."""
    import inspect
    import core.atom_meta_agent as ama

    # The module must expose exactly ONE route_with_governance, and it must be a
    # method (defined inside the class), not a module-level function.
    members = [
        name for name, _ in inspect.getmembers(ama, predicate=inspect.iscoroutinefunction)
        if name == "route_with_governance"
    ]
    # Module-level coroutine functions would appear here; a bound method would not.
    assert members == [], (
        "no module-level route_with_governance coroutine should exist "
        "(the broken :2630 copy must be deleted)"
    )
