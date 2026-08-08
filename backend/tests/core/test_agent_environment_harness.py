"""
W5 — agent environment harness (P5b/P5c).

5b. Explicit utility: the maturity success ratio becomes an optimization
    target — the delta vs the run baseline is threaded into ``_react_step``
    and surfaced to the model as an OPTIMIZATION TARGET block.
5c. Agent-extensible tool surface: ``register_action`` + maturity-gated
    discovery; stuck-detector halts 3× identical tool+args calls.
    Both gated on ATOM_OBJECTIVE_LOOP_ENABLED (default true).
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.generic_agent import GenericAgent
from core.models import AgentRegistry
from core.react_models import ReActStep, ToolCall


def _agent_model(**cfg_overrides):
    config = {"system_prompt": "You are Test Agent.", "tools": "*", "max_steps": 4, **cfg_overrides}
    return AgentRegistry(
        id="agent-harness", name="Harness Agent",
        type="assistant", module_path="agents.assistant", class_name="AssistantAgent",
        category="general", configuration=config,
    )


def _build_agent(model=None, **patches):
    with patch("core.generic_agent.WorldModelService"), \
         patch("core.generic_agent.ReflectionService"), \
         patch("core.generic_agent.CanvasSummaryService"), \
         patch("core.generic_agent.mcp_service"), \
         patch("core.generic_agent.LLMService"):
        agent = GenericAgent(model or _agent_model())
    for k, v in patches.items():
        setattr(agent, k, v)
    return agent


def _base_agent(react_steps):
    agent = _build_agent(_agent_model())
    agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
    agent._react_step = AsyncMock(side_effect=react_steps)
    agent._step_act = AsyncMock(return_value="ok")
    agent._execute_parallel_tools = AsyncMock(return_value=[])
    agent.world_model.recall_experiences = AsyncMock(return_value={})
    agent.mcp.get_all_tools = AsyncMock(return_value=[])
    agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
    agent._record_execution = AsyncMock()
    return agent


# ---------------------------------------------------------------------------
# 5c — agent-extensible tool surface
# ---------------------------------------------------------------------------


async def test_register_action_dispatches_locally():
    """A registered action dispatches in _step_act, before any MCP call."""
    agent = _build_agent(_agent_model())
    received = []

    async def _handler(args, context):
        received.append((args, context))

    await agent.register_action("custom_probe", _handler, description="probe it")
    assert "custom_probe" in agent._custom_actions

    # Dispatch path (custom actions are agent-scoped, pre-authorized).
    result = await agent._step_act("custom_probe", {"x": 1}, {"user_id": "u1"})
    assert result is None
    assert received == [({"x": 1}, {"user_id": "u1"})]

    # Governance/MCP were never consulted for the custom action.
    with patch("core.generic_agent.AgentGovernanceService") as _gov:
        agent.mcp.call_tool = AsyncMock(return_value="mcp")
        out = await agent._step_act("custom_probe", {}, {})
        assert out is None
        agent.mcp.call_tool.assert_not_called()
        _gov.assert_not_called()


async def test_register_action_sync_handler_supported():
    """Sync handlers are awaited transparently."""
    agent = _build_agent(_agent_model())

    def _sync_handler(args, context):
        return f"handled:{args.get('v')}"

    await agent.register_action("sync_probe", _sync_handler, description="sync")
    out = await agent._step_act("sync_probe", {"v": 7}, {})
    assert out == "handled:7"


def test_register_action_maturity_gated_discovery():
    """Custom actions are hidden when the agent's maturity < the floor."""
    agent = _build_agent(_agent_model())
    asyncio.run(agent.register_action(
        "senior_probe", lambda a, c: None,
        description="senior only", min_maturity="SUPERVISED",
    ))
    agent._run_maturity = "INTERN"
    assert agent._custom_action_visible("senior_probe") is False
    agent._run_maturity = "AUTONOMOUS"
    assert agent._custom_action_visible("senior_probe") is True
    # Unspecified floor → always visible.
    asyncio.run(agent.register_action("open_probe", lambda a, c: None))
    agent._run_maturity = None
    assert agent._custom_action_visible("open_probe") is True


async def test_registered_actions_appear_in_available_tools():
    """_react_step advertises visible custom actions in AVAILABLE TOOLS."""
    agent = _build_agent(_agent_model())
    agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
    agent.world_model.recall_experiences = AsyncMock(return_value={})
    agent.mcp.get_all_tools = AsyncMock(return_value=[])
    agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
    agent._record_execution = AsyncMock()
    agent.llm.generate_structured = AsyncMock(
        return_value=ReActStep(thought="t", final_answer="done")
    )
    await agent.register_action("probe_a", lambda a, c: None, description="probe A")
    await agent.register_action(
        "probe_hidden", lambda a, c: None, description="hidden", min_maturity="AUTONOMOUS"
    )
    agent._run_maturity = "INTERN"

    await agent.execute("do it")

    prompt = agent.llm.generate_structured.call_args.kwargs["system_instruction"]
    assert "probe_a" in prompt
    assert "probe_hidden" not in prompt


# ---------------------------------------------------------------------------
# 5c — stuck-detector (3× identical tool+args → halt)
# ---------------------------------------------------------------------------


async def test_stuck_detector_halts_identical_repeats():
    """3 consecutive identical tool+args calls halt the loop with status 'stuck'."""
    agent = _base_agent([
        ReActStep(thought="s1", action=ToolCall(tool="search", params={"q": "x"})),
        ReActStep(thought="s2", action=ToolCall(tool="search", params={"q": "x"})),
        ReActStep(thought="s3", action=ToolCall(tool="search", params={"q": "x"})),
        ReActStep(thought="s4", final_answer="too late"),
    ])
    result = await agent.execute("do it")
    assert result["status"] == "stuck"
    assert "3+ times" in str(result["output"])
    # Steps 1-2 executed; step 3 halted before execution.
    assert agent._step_act.await_count == 2


async def test_stuck_detector_flag_off_runs_identically(monkeypatch):
    """Flag off (kill-switch) → 3 identical calls are NOT halted."""
    monkeypatch.setenv("ATOM_OBJECTIVE_LOOP_ENABLED", "false")
    agent = _base_agent([
        ReActStep(thought="s1", action=ToolCall(tool="search", params={"q": "x"})),
        ReActStep(thought="s2", action=ToolCall(tool="search", params={"q": "x"})),
        ReActStep(thought="s3", action=ToolCall(tool="search", params={"q": "x"})),
        ReActStep(thought="s4", final_answer="done"),
    ])
    result = await agent.execute("do it")
    assert result["status"] == "success", "legacy behavior: no stuck halt"
    assert agent._step_act.await_count == 3


async def test_stuck_detector_ignores_different_args():
    """Same tool with different args is progress, not stuck."""
    agent = _base_agent([
        ReActStep(thought="s1", action=ToolCall(tool="search", params={"q": "a"})),
        ReActStep(thought="s2", action=ToolCall(tool="search", params={"q": "b"})),
        ReActStep(thought="s3", action=ToolCall(tool="search", params={"q": "a"})),
        ReActStep(thought="s4", final_answer="done"),
    ])
    result = await agent.execute("do it")
    assert result["status"] == "success"


# ---------------------------------------------------------------------------
# 5b — explicit utility (success ratio delta → _react_step)
# ---------------------------------------------------------------------------


async def test_utility_delta_threaded_into_react_step():
    """The success-ratio delta is passed to _react_step after each action."""
    recorded = {}

    async def _fake_react(task_input, memory, history, context, utility_delta=None):
        recorded["deltas"] = recorded.get("deltas", []) + [utility_delta]
        if len(recorded["deltas"]) == 1:
            return ReActStep(thought="s1", action=ToolCall(tool="search", params={"q": "a"}))
        return ReActStep(thought="s2", final_answer="done")

    agent = _base_agent([])
    agent._react_step = _fake_react
    agent._measure_success_rate = AsyncMock(side_effect=[0.5, 0.6, 0.6])

    result = await agent.execute("do it")
    assert result["status"] == "success"
    # First call has no prior delta; the step-2 call carries +0.1.
    assert recorded["deltas"][0] is None
    assert recorded["deltas"][1] == pytest.approx(0.1)


def test_react_step_surfaces_optimization_target():
    """utility_delta → OPTIMIZATION TARGET block in the system prompt."""
    agent = _build_agent(_agent_model())
    agent.llm.generate_structured = AsyncMock(
        return_value=ReActStep(thought="t", final_answer="done")
    )
    agent.mcp.get_all_tools = AsyncMock(return_value=[])
    agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
    asyncio.run(agent._react_step(
        "task", {}, "", {}, utility_delta=0.1
    ))
    prompt = agent.llm.generate_structured.call_args.kwargs["system_instruction"]
    assert "OPTIMIZATION TARGET" in prompt
    assert "+10.0%" in prompt

    asyncio.run(agent._react_step("task", {}, "", {}))
    prompt2 = agent.llm.generate_structured.call_args.kwargs["system_instruction"]
    assert "OPTIMIZATION TARGET" not in prompt2
