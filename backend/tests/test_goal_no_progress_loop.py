"""GOAL-04: the real agent loop stops on repeated no-progress observations.

Self-contained: drives GenericAgent.execute() with a stubbed structured step
(the model boundary), so it does not depend on the historical ReAct parsing
suite or on live providers.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from core.generic_agent import GenericAgent
from core.models import AgentRegistry, AgentStatus
from core.react_models import ReActStep, ToolCall


@pytest.fixture()
def agent():
    registry = AgentRegistry(
        id="goal04-agent", name="Goal 04 Agent", category="Test",
        status=AgentStatus.STUDENT.value,
        configuration={"tools": ["calculator"], "max_steps": 6},
    )
    with patch("core.generic_agent.WorldModelService"), \
            patch("core.generic_agent.LLMService"), \
            patch("core.generic_agent.ReflectionService"), \
            patch("core.generic_agent.CanvasSummaryService"), \
            patch("core.generic_agent.mcp_service"):
        instance = GenericAgent(registry)
    instance.llm = AsyncMock()
    instance.world_model.recall_experiences = AsyncMock(
        return_value={"experiences": []})
    instance.world_model.record_experience = AsyncMock()
    instance.mcp.get_all_tools = AsyncMock(return_value=[])
    instance.reflection_service.get_relevant_critiques = AsyncMock(
        return_value=[])
    instance.reflection_service.add_critique = AsyncMock()
    instance._record_execution = AsyncMock()
    instance._check_budget_before_react = AsyncMock(
        return_value={"allowed": True})
    instance._measure_success_rate = AsyncMock(return_value=None)
    instance._step_act = AsyncMock(return_value="2")
    return instance


async def _same_action(_self, *args, **kwargs):
    return ReActStep(
        thought="The same lookup again should help.",
        action=ToolCall(tool="calculator", params={"expression": "1+1"}),
    )


@pytest.mark.asyncio
async def test_repeated_equivalent_observations_stop_and_record_the_reason(agent):
    with patch.object(GenericAgent, "_react_step", new=_same_action):
        result = await agent.execute("Keep retrying the same lookup.")

    assert result["status"] == "stuck"
    assert "without progress" in result["output"]
    # The third equivalent call is refused BEFORE it can run a tool again.
    assert agent._step_act.await_count == 2
    agent.reflection_service.add_critique.assert_awaited()
    kwargs = agent.reflection_service.add_critique.await_args.kwargs
    assert kwargs["outcome_state"] == "stuck"
    assert "stuck" in kwargs["critique_text"]


@pytest.mark.asyncio
async def test_different_arguments_are_real_progress(agent):
    calls = {"n": 0}

    async def _varying(_self, *args, **kwargs):
        calls["n"] += 1
        return ReActStep(
            thought="Try the next value.",
            action=ToolCall(
                tool="calculator", params={"expression": f"1+{calls['n']}"}),
        )

    with patch.object(GenericAgent, "_react_step", new=_varying):
        result = await agent.execute("Try different inputs.")

    assert result["status"] != "stuck"
    assert agent._step_act.await_count == agent.config.get("max_steps", 6)
