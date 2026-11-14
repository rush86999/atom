"""Thought-only structured ReAct steps must recover or exhaust honestly.

Goal 13 replay: a specialist model returned ``ReActStep(thought=...)`` with no
action/actions/final_answer. The loop silently burned every remaining step and
then promoted the last private thought to the user-facing answer. These tests
pin the two halves of the fix: an explicit deterministic contract for the next
call, and an honest exhaustion result that never contains model reasoning.
"""

import pytest
from unittest.mock import AsyncMock, patch

from core.generic_agent import GenericAgent, _MAX_STEPS_WITHOUT_ANSWER
from core.models import AgentRegistry
from core.react_models import ReActStep


def _agent_model(**overrides):
    config = {
        "system_prompt": "You are Test Agent.",
        "tools": "*",
        "max_steps": 3,
        **overrides,
    }
    return AgentRegistry(
        id="agent-thought-only",
        name="Thought Only Agent",
        type="assistant",
        module_path="agents.assistant",
        class_name="AssistantAgent",
        category="general",
        configuration=config,
    )


def _build_agent(model):
    with patch("core.generic_agent.WorldModelService"), \
         patch("core.generic_agent.ReflectionService"), \
         patch("core.generic_agent.CanvasSummaryService"), \
         patch("core.generic_agent.mcp_service"), \
         patch("core.generic_agent.LLMService"):
        agent = GenericAgent(model)

    agent._check_budget_before_react = AsyncMock(
        return_value={"allowed": True, "reason": "ok"})
    agent.world_model.recall_experiences = AsyncMock(return_value={})
    agent.mcp.get_all_tools = AsyncMock(return_value=[])
    agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
    # Keep the test at the loop boundary: no DB/episode side effects.
    agent._record_execution = AsyncMock()
    return agent


@pytest.mark.asyncio
async def test_thought_only_step_instructs_next_call_then_recovers():
    """One thought-only step gets a deterministic contract; next call answers."""
    agent = _build_agent(_agent_model(max_steps=3))
    histories = []

    async def fake_react_step(task_input, memory, history, context=None,
                              utility_delta=None):
        histories.append(history)
        if len(histories) == 1:
            return ReActStep(thought="I should compute the shortfall first.")
        return ReActStep(
            thought="The calculation is complete.",
            final_answer="The shortfall is $42,000.",
        )

    agent._react_step = fake_react_step

    result = await agent.execute("Diagnose the revenue shortfall")

    assert result["status"] == "success"
    assert result["output"] == "The shortfall is $42,000."
    assert result["output"] != result["steps"][0]["thought"]
    # Recovery consumed no extra model call or step beyond the budget.
    assert len(histories) == 2
    assert agent._check_budget_before_react.await_count == 2

    recovery = result["steps"][0]["recovery_instruction"]
    assert "[NO CONTROL FIELD]" in recovery
    assert "final_answer" in recovery
    assert "action" in recovery
    assert "actions" in recovery
    assert "information_wait" in recovery
    # The instruction is visible to the NEXT model call through history.
    assert recovery in histories[1]
    assert "I should compute the shortfall first." in histories[1]
    assert "final_answer" not in result["steps"][0]


@pytest.mark.asyncio
async def test_thought_only_steps_exhaust_without_promoting_thought():
    """Exhaustion returns an honest message, never the last thought."""
    agent = _build_agent(_agent_model(max_steps=2))
    histories = []

    async def fake_react_step(task_input, memory, history, context=None,
                              utility_delta=None):
        histories.append(history)
        return ReActStep(thought=f"private reasoning {len(histories)}")

    agent._react_step = fake_react_step

    result = await agent.execute("Diagnose the revenue shortfall")

    assert result["status"] == "max_steps_exceeded"
    assert result["output"] == _MAX_STEPS_WITHOUT_ANSWER
    assert result["output"] != "private reasoning 2"
    assert "private reasoning" not in str(result["output"])
    # Still bounded by the existing step/budget limits.
    assert len(histories) == 2
    assert agent._check_budget_before_react.await_count == 2

    # Step 1 was recoverable, so its contract reached step 2.
    assert "[NO CONTROL FIELD]" in histories[1]
    assert "recovery_instruction" in result["steps"][0]
    # Step 2 was the last permitted step: flagged as exhausted, not answered.
    assert result["steps"][1]["exhausted_without_answer"] is True
    assert "recovery_instruction" not in result["steps"][1]
