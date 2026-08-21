"""
Fleet routing validation wiring (2026-08-21) — audit write + resolved enforce.

Extends ``test_fleet_routing_wire.py``: the fleet branch must audit EVERY
fleet-eligible decision (shadow, enforced, or failed recruitment) via
``record_fleet_decision``, resolve enforcement through
``resolved_fleet_enforce()`` (env kill-switch or automation override), and
join the execution outcome at the finalize points.

Run: ``cd backend && venv/bin/python -m pytest tests/unit/test_fleet_routing_audit_wire.py -v``
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.atom_meta_agent import AtomMetaAgent, AgentTriggerMode


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


def _force_task_route(monkeypatch):
    from ai.nlp_engine import RouteCategory

    route = MagicMock()
    route.category = RouteCategory.ONE_OFF
    route.reasoning = "one-off task"
    monkeypatch.setattr(
        "core.atom_meta_agent.NaturalLanguageEngine",
        lambda: MagicMock(classify_route=AsyncMock(return_value=route)),
    )


def _audit_spy(monkeypatch):
    calls = {"rows": []}
    real = None
    import core.atom_meta_agent as ama

    def _fake(**kwargs):
        calls["rows"].append(kwargs)
        return "audit-1"

    monkeypatch.setattr(
        "core.fleet_orchestration.fleet_routing_stats.record_fleet_decision",
        _fake,
    )
    return calls


async def _run_execute(atom_agent, request_text="analyze my sales pipeline in detail this quarter"):
    with patch("core.atom_meta_agent.SessionLocal"), \
         patch("core.atom_meta_agent.AgentGovernanceService"):
        try:
            result = await atom_agent.execute(request_text, trigger_mode=AgentTriggerMode.MANUAL)
            return result, None
        except Exception as exc:
            return None, exc


# 1. Shadow mode: audit written with enforced=False, response falls through.
@pytest.mark.asyncio
async def test_shadow_writes_audit_not_enforced(atom_agent, monkeypatch):
    monkeypatch.setenv("ATOM_FLEET_ROUTING_ENABLED", "true")
    monkeypatch.delenv("ATOM_FLEET_ROUTING_FORCE_ENFORCE", raising=False)
    _force_task_route(monkeypatch)
    calls = _audit_spy(monkeypatch)

    summary = {"status": "fleet_recruited", "chain_id": "chain-9", "specialists_count": 2}
    monkeypatch.setattr(
        atom_agent, "route_with_governance", AsyncMock(return_value=summary)
    )

    result, exc = await _run_execute(atom_agent)

    assert calls["rows"], "shadow mode must audit the fleet decision"
    assert calls["rows"][0]["enforced"] is False
    assert calls["rows"][0]["recruitment_succeeded"] is True
    assert calls["rows"][0]["specialists_count"] == 2
    assert calls["rows"][0]["error"] is None
    # Shadow falls through — the summary must NOT be returned.
    if exc is None and result is not None:
        assert result.get("status") != "fleet_recruited"


# 2. Enforced: audit written with enforced=True, summary returned.
@pytest.mark.asyncio
async def test_enforced_writes_audit_enforced_and_returns_summary(atom_agent, monkeypatch):
    monkeypatch.setenv("ATOM_FLEET_ROUTING_ENABLED", "true")
    monkeypatch.setenv("ATOM_FLEET_ROUTING_FORCE_ENFORCE", "true")
    _force_task_route(monkeypatch)
    calls = _audit_spy(monkeypatch)

    summary = {"status": "fleet_recruited", "chain_id": "chain-1", "specialists_count": 2}
    monkeypatch.setattr(
        atom_agent, "route_with_governance", AsyncMock(return_value=summary)
    )

    with patch("core.atom_meta_agent.SessionLocal"), \
         patch("core.atom_meta_agent.AgentGovernanceService"):
        result = await atom_agent.execute(
            "analyze my sales pipeline in detail this quarter",
            trigger_mode=AgentTriggerMode.MANUAL,
        )

    assert calls["rows"] and calls["rows"][0]["enforced"] is True
    assert result.get("status") == "fleet_recruited"


# 3. Recruitment failure: audit written with error + recruitment_succeeded=False.
@pytest.mark.asyncio
async def test_failed_recruitment_is_audited(atom_agent, monkeypatch):
    monkeypatch.setenv("ATOM_FLEET_ROUTING_ENABLED", "true")
    _force_task_route(monkeypatch)
    calls = _audit_spy(monkeypatch)

    async def _boom(request, intent, user_id, agent_id="atom_main"):
        raise RuntimeError("fleet admiral unavailable")

    monkeypatch.setattr(atom_agent, "route_with_governance", _boom)

    await _run_execute(atom_agent)

    assert calls["rows"], "failed recruitment must still be audited"
    row = calls["rows"][0]
    assert row["recruitment_succeeded"] is False
    assert row["error"] is not None
    assert row["specialists_count"] == 0


# 4. Even when recruitment fails, the fallback execution completes and the
#    outcome is joined at the finalize point (success=True — Queen fallback).
@pytest.mark.asyncio
async def test_failed_recruitment_still_joins_fallback_outcome(atom_agent, monkeypatch):
    monkeypatch.setenv("ATOM_FLEET_ROUTING_ENABLED", "true")
    monkeypatch.delenv("ATOM_FLEET_ROUTING_FORCE_ENFORCE", raising=False)
    _force_task_route(monkeypatch)
    _audit_spy(monkeypatch)

    joined = {"calls": []}
    import core.atom_meta_agent as ama

    def _join(**kwargs):
        joined["calls"].append(kwargs)

    monkeypatch.setattr(
        "core.fleet_orchestration.fleet_routing_stats.record_fleet_execution_outcome",
        _join,
    )

    async def _boom(request, intent, user_id, agent_id="atom_main"):
        raise RuntimeError("fleet admiral unavailable")

    monkeypatch.setattr(atom_agent, "route_with_governance", _boom)

    await _run_execute(atom_agent)

    assert joined["calls"], "finalize point must join the fallback outcome"
    assert joined["calls"][0]["success"] is True
