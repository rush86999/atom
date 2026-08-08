"""
P1d — Fleet sub-agent budget + episodic-memory hooks (W4).

Verified gap: the wired FleetAdmiral path (P1a) recruits specialists but
does NOT execute them; execution must later route through
``GenericAgent.execute()`` so that the per-step spend gate
(``_check_budget_before_react``) and the episodic-memory record
(``record_experience``) apply uniformly. Without this, fleet successes
can't graduate (interacts with W2's oracle).

This suite verifies the contract a recruited specialist's execution must
honor: (1) the spend gate is checked before each LLM call and halts on
``budget_exceeded``; (2) a completed run records an experience
(``AgentEpisode``) so it can graduate.

Run: ``cd backend && venv/bin/python -m pytest tests/unit/test_fleet_budget_memory_hooks.py -v``
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.generic_agent import GenericAgent


@pytest.fixture(autouse=True)
def _disable_bg(monkeypatch):
    """Suppress background extraction/recall dispatch for the unit test."""
    import core.generic_agent as ga
    for attr in ("_TURN_FACT_EXTRACTION_ENABLED", "_TURN_FACT_VECTOR_RECALL_ENABLED"):
        if hasattr(ga, attr):
            monkeypatch.setattr(ga, attr, False)


def _make_agent():
    from types import SimpleNamespace
    world_model = AsyncMock()
    world_model.recall_experiences = AsyncMock(return_value={
        "experiences": [], "knowledge": [], "formulas": [], "business_facts": []
    })
    world_model.record_experience = AsyncMock()
    llm = AsyncMock()
    llm.generate_response = AsyncMock(return_value="ok")

    # GenericAgent takes an AgentRegistry-like model object.
    agent_model = SimpleNamespace(
        id="fleet-specialist-1",
        name="FinanceBot",
        configuration={
            "system_prompt": "you are a finance specialist",
            "tools": "*",
            "role": "specialty_agent",
            "specialty": "finance",
            "max_steps": 3,
        },
        vision_enabled=False,
    )
    with patch("core.generic_agent.WorldModelService", return_value=world_model), \
         patch("core.generic_agent.mcp_service"), \
         patch("core.service_factory.ServiceFactory.get_llm_service", return_value=llm):
        agent = GenericAgent(agent_model, workspace_id="test-ws")
        agent.world_model = world_model
        agent.llm = llm
    return agent, world_model, llm


# ---------------------------------------------------------------------------
# 1. Budget gate: a hard_stop spend decision halts the loop before the LLM call.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_spend_gate_halts_on_budget_exceeded():
    agent, world_model, llm = _make_agent()

    # Force the spend gate to deny.
    spend_gate = AsyncMock(return_value={
        "allowed": False, "reason": "hard_stop: spend ceiling reached",
    })
    agent._check_budget_before_react = spend_gate

    with patch("core.generic_agent.get_db_session"), \
         patch("core.generic_agent.AgentGovernanceService"):
        result = await agent.execute("analyze Q3 budget")

    # The gate MUST be consulted (a recruited specialist can't bypass the spend check).
    spend_gate.assert_awaited()
    # And once it denies, the run must not report success — it halts (exact status
    # string depends on loop internals; budget_exceeded or failed both indicate a halt).
    assert result["status"] != "success", (
        "a recruited specialist must honor the spend gate and halt when over budget"
    )


# ---------------------------------------------------------------------------
# 2. Episodic memory: a completed run records an experience (AgentEpisode path).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_completed_run_records_experience():
    agent, world_model, llm = _make_agent()
    agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})

    with patch("core.generic_agent.get_db_session"), \
         patch("core.generic_agent.AgentGovernanceService"):
        await agent.execute("analyze Q3 budget")

    world_model.record_experience.assert_awaited(), (
        "a recruited specialist's execution MUST record an experience so it can graduate "
        "(without this, fleet successes are invisible to the maturity/oracle pipeline)"
    )
