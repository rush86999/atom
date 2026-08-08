"""
P1d — Fleet sub-agent budget + memory hooks.

Locked contract (FLEET_ORCHESTRATION.md § Fleet sub-agent budget + memory):
- Spend gate: ``GenericAgent._check_budget_before_react`` halts a fleet
  specialist's run when the tenant budget is exhausted (hard stop).
- Episodic memory: a completed specialist run records an ``AgentExperience``
  via ``world_model.record_experience`` so fleet successes can graduate
  (feeds the W2 oracle's verified-episode tier).

Run: ``cd backend && venv/bin/python -m pytest tests/core/test_fleet_budget_memory_hooks.py -v``
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models import AgentRegistry, AgentStatus
from core.react_models import ReActStep


def _specialist_agent(db_session, agent_id=None):
    """A real AgentRegistry-backed fleet specialist (P1d placeholder shape)."""
    from core.generic_agent import GenericAgent

    agent_id = agent_id or f"spec-{uuid.uuid4().hex[:8]}"
    model = AgentRegistry(
        id=agent_id, name="fleet-specialist", category="finance",
        capabilities=["analyze", "forecast"],
        module_path="core.generic_agent", class_name="GenericAgent",
        status=AgentStatus.SUPERVISED.value, confidence_score=0.8,
        workspace_id="default",
    )
    db_session.add(model)
    db_session.commit()

    agent = GenericAgent(model, workspace_id="default")
    agent.world_model = AsyncMock()
    agent.world_model.recall_experiences = AsyncMock(return_value={
        "experiences": [], "knowledge": [], "formulas": [], "business_facts": []
    })
    agent.world_model.record_experience = AsyncMock()
    agent.mcp = AsyncMock()
    agent.mcp.get_all_tools = AsyncMock(return_value=[])
    agent.llm = AsyncMock()
    return agent


class TestSpendGate:
    @pytest.mark.asyncio
    async def test_spend_gate_halts_fleet_specialist(self, db_session):
        """Budget-exhausted tenant → the gate denies the LLM react step."""
        agent = _specialist_agent(db_session)

        fake_svc = MagicMock()
        fake_svc.__enter__.return_value = fake_svc
        fake_svc.check_budget_before_action = AsyncMock(return_value={
            "allowed": False,
            "reason": "budget_exceeded",
            "enforcement_mode": "hard_stop",
            "current_spend_usd": 10.0,
            "budget_limit_usd": 5.0,
            "utilization_percent": 200.0,
        })

        with patch(
            "core.budget_enforcement_service.BudgetEnforcementService",
            return_value=fake_svc,
        ):
            decision = await agent._check_budget_before_react()

        assert decision["allowed"] is False
        assert decision["reason"] == "budget_exceeded"
        fake_svc.check_budget_before_action.assert_awaited_once_with(
            tenant_id="default", agent_id=agent.id, action="llm_react_step"
        )

    @pytest.mark.asyncio
    async def test_budget_gate_halts_before_llm_call(self, db_session):
        """A run denied by the spend gate never reaches the LLM react step."""
        agent = _specialist_agent(db_session)
        react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="nope"))

        with patch.object(agent, "_check_budget_before_react", new=AsyncMock(
            return_value={"allowed": False, "reason": "budget_exceeded",
                          "enforcement_mode": "hard_stop"}
        )), patch("core.generic_agent.get_db_session", return_value=db_session), \
             patch.object(agent, "_react_step", new=react_step):
            result = await agent.execute("run some task")

            # The in-loop sentinel is normalized to a valid ExecutionStatus at
            # the boundary (generic_agent.py:436-437); the halt is observable
            # via the output message + the LLM step never running.
            assert result["status"] == "failed"
            assert "Budget limit reached" in result["output"]
            react_step.assert_not_awaited()


class TestEpisodicMemory:
    @pytest.mark.asyncio
    async def test_completed_specialist_run_records_experience(self, db_session):
        """A successful specialist run records an AgentExperience episode."""
        agent = _specialist_agent(db_session)

        with patch.object(agent, "_check_budget_before_react", new=AsyncMock(
            return_value={"allowed": True, "reason": "ok",
                          "enforcement_mode": "tracking"}
        )), patch("core.generic_agent.get_db_session", return_value=db_session), \
             patch.object(agent, "_react_step", new=AsyncMock(
                 return_value=ReActStep(thought="analyzed", final_answer="done"))
             ):
            result = await agent.execute("analyze the pipeline")

        assert result["status"] == "success"
        agent.world_model.record_experience.assert_awaited_once()
        experience = agent.world_model.record_experience.await_args.args[0]
        assert experience.agent_id == agent.id
        assert experience.outcome == "success"
        assert experience.task_type == "custom_task_react"
