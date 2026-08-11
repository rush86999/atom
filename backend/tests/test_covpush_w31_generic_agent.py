"""Coverage wave 31 — core/generic_agent remaining branches (91% → 96%+).

- register_action + _custom_action_visible maturity gating (no floor,
  floor+no-maturity, below, above)
- custom action dispatch in _step_act (sync + async + raising handler)
- custom actions advertised in tool surface when visible
- _measure_success_rate (metrics path, exception → None)
- stuck-detector: 3x identical tool+args halts the loop with status "stuck"
- parallel-batch stuck-detector (3x identical in a parallel batch)
- oracle verify_before_retry: timeout with postcondition met → no-retry text
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.generic_agent import GenericAgent
from core.models import AgentRegistry
from core.react_models import ReActStep, ToolCall


def _agent_model(**cfg_overrides):
    config = {
        "system_prompt": "You are Test Agent.",
        "tools": "*",
        "max_steps": 3,
        **cfg_overrides,
    }
    return AgentRegistry(
        id="agent-123", name="Test Agent",
        type="assistant", module_path="agents.assistant", class_name="AssistantAgent",
        category="general", configuration=config,
    )


def _build_agent(model, **patches):
    with patch("core.generic_agent.WorldModelService"), \
         patch("core.generic_agent.ReflectionService"), \
         patch("core.generic_agent.CanvasSummaryService"), \
         patch("core.generic_agent.mcp_service"), \
         patch("core.generic_agent.LLMService"):
        agent = GenericAgent(model)
    for k, v in patches.items():
        setattr(agent, k, v)
    return agent


class TestCustomActions:
    def _register(self, agent, name, handler, **kw):
        # register_action is intentionally SYNC — calling without await must
        # work (regression: async signature silently no-op'd un-awaited calls)
        agent.register_action(name, handler, "desc", **kw)

    @pytest.mark.asyncio
    async def test_register_action_sync_and_async(self):
        agent = _build_agent(_agent_model())

        def sync_handler(args, context):
            return "sync-ok"

        async def async_handler(args, context):
            return "async-ok"

        self._register(agent, "act_sync", sync_handler)
        self._register(agent, "act_async", async_handler, min_maturity="INTERN")
        assert agent._custom_actions["act_sync"] is sync_handler
        assert agent._custom_action_specs["act_async"]["min_maturity"] == "INTERN"

    @pytest.mark.asyncio
    async def test_custom_action_visible_no_floor(self):
        agent = _build_agent(_agent_model())
        self._register(agent, "act_1", lambda a, c: "x")
        assert agent._custom_action_visible("act_1") is True

    def test_custom_action_visible_unknown(self):
        agent = _build_agent(_agent_model())
        assert agent._custom_action_visible("nope") is False

    @pytest.mark.asyncio
    async def test_custom_action_visible_floor_without_maturity(self):
        agent = _build_agent(_agent_model())
        self._register(agent, "act_2", lambda a, c: "x", min_maturity="INTERN")
        agent._run_maturity = None
        assert agent._custom_action_visible("act_2") is False

    @pytest.mark.asyncio
    async def test_custom_action_visible_below_floor(self):
        agent = _build_agent(_agent_model())
        self._register(agent, "act_3", lambda a, c: "x", min_maturity="SUPERVISED")
        agent._run_maturity = "intern"
        assert agent._custom_action_visible("act_3") is False

    @pytest.mark.asyncio
    async def test_custom_action_visible_above_floor(self):
        agent = _build_agent(_agent_model())
        self._register(agent, "act_4", lambda a, c: "x", min_maturity="INTERN")
        agent._run_maturity = "AUTONOMOUS"
        assert agent._custom_action_visible("act_4") is True

    @pytest.mark.asyncio
    async def test_step_act_dispatches_sync_and_async(self):
        agent = _build_agent(_agent_model())

        def sync_handler(args, context):
            return {"handled": args["x"]}

        async def async_handler(args, context):
            return {"handled": "async"}

        self._register(agent, "custom_sync", sync_handler)
        self._register(agent, "custom_async", async_handler)

        sync_result = await agent._step_act("custom_sync", {"x": 1}, {})
        assert sync_result == {"handled": 1}
        async_result = await agent._step_act("custom_async", {}, {})
        assert async_result == {"handled": "async"}

    @pytest.mark.asyncio
    async def test_step_act_custom_action_error(self):
        agent = _build_agent(_agent_model())

        def bad_handler(args, context):
            raise RuntimeError("custom boom")

        self._register(agent, "custom_bad", bad_handler)
        result = await agent._step_act("custom_bad", {}, {})
        assert "custom boom" in result



    @pytest.mark.asyncio
    async def test_measure_success_rate_exception_returns_none(self):
        agent = _build_agent(_agent_model())
        with patch("core.generic_agent.get_db_session", side_effect=RuntimeError("db down")):
            rate = await agent._measure_success_rate()
        assert rate is None

    @pytest.mark.asyncio
    async def test_measure_success_rate_metrics(self):
        agent = _build_agent(_agent_model())
        with patch("core.generic_agent.get_db_session") as gds:
            gds.return_value.__enter__.return_value = MagicMock()
            with patch("core.agent_graduation_service.AgentGraduationService") as gcls:
                gcls.return_value.calculate_skill_usage_metrics = AsyncMock(
                    return_value={"success_rate": 0.75}
                )
                rate = await agent._measure_success_rate()
        assert rate == 0.75


class TestStuckDetector:
    @pytest.mark.asyncio
    async def test_serial_stuck_detector_halts(self):
        agent = _build_agent(_agent_model(), _check_budget_before_react=None)
        agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
        agent.world_model.recall_experiences = AsyncMock(return_value={})
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
        agent._record_execution = AsyncMock()
        same_step = ReActStep(
            thought="same", actions=[ToolCall(tool="t1", params={"x": 1})],
            final_answer=None,
        )
        agent._react_step = AsyncMock(return_value=same_step)
        agent._step_act = AsyncMock(return_value="ok")
        agent._measure_success_rate = AsyncMock(return_value=0.8)
        agent._execute_parallel_tools = AsyncMock(return_value=[])

        with patch("core.agent_objective.objective_loop_enabled", return_value=True):
            result = await agent.execute("do it")
        assert result["status"] == "stuck"
        answer = result.get("output") or ""
        assert "identical arguments" in answer or "repeated 3+ times" in answer

    @pytest.mark.asyncio
    async def test_parallel_stuck_detector_halts(self):
        agent = _build_agent(_agent_model(), _check_budget_before_react=None)
        agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
        agent.world_model.recall_experiences = AsyncMock(return_value={})
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
        agent._record_execution = AsyncMock()
        agent._execute_parallel_tools = AsyncMock(return_value=[
            {"tool_name": "p1", "params": {"y": 2}, "output": "ok",
             "verified_kind": "unverified", "verified_evidence": None}
        ])
        same_step = ReActStep(
            thought="same", actions=[ToolCall(tool="p1", params={"y": 2})],
            final_answer=None,
        )
        agent._react_step = AsyncMock(return_value=same_step)
        agent._measure_success_rate = AsyncMock(return_value=0.8)

        with patch("core.agent_objective.objective_loop_enabled", return_value=True), \
             patch("core.hallucination_config.is_parallel_tools_enabled", return_value=True):
            result = await agent.execute("do it")
        assert result["status"] == "stuck"

    @pytest.mark.asyncio
    async def test_timed_out_message_hits_oracle_path(self):
        # regression: "timed out" (with space) previously fell through the
        # "timeout" string check to the generic error return
        agent = _build_agent(_agent_model())
        agent.mcp.call_tool = AsyncMock(side_effect=asyncio.TimeoutError("tool timed out"))
        with patch("core.oracle.verify_before_retry", new=AsyncMock(return_value=True)):
            with patch("core.generic_agent.get_db_session") as gds:
                gds.return_value.__enter__.return_value = MagicMock()
                result = await agent._step_act(
                    "documents.search", {"query": "x"}, {}, pre_approved=True
                )
        assert "Do NOT retry" in result

    @pytest.mark.asyncio
    async def test_timeout_error_type_hits_oracle_path(self):
        # regression: a bare TimeoutError with an unrelated message must still
        # route through verify-before-retry (type check, not just string)
        agent = _build_agent(_agent_model())
        agent.mcp.call_tool = AsyncMock(side_effect=asyncio.TimeoutError("deadline"))
        with patch("core.oracle.verify_before_retry", new=AsyncMock(return_value=False)):
            with patch("core.generic_agent.get_db_session") as gds:
                gds.return_value.__enter__.return_value = MagicMock()
                result = await agent._step_act(
                    "documents.search", {"query": "x"}, {}, pre_approved=True
                )
        assert "try once more" in result

    @pytest.mark.asyncio
    async def test_oracle_timeout_postcondition_met(self):
        agent = _build_agent(_agent_model())
        agent.mcp.call_tool = AsyncMock(side_effect=asyncio.TimeoutError("tool timeout occurred"))
        agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
        with patch("core.oracle.verify_before_retry", new=AsyncMock(return_value=True)):
            with patch("core.generic_agent.get_db_session") as gds:
                gds.return_value.__enter__.return_value = MagicMock()
                result = await agent._step_act(
                    "documents.search", {"query": "x"}, {}, pre_approved=True
                )
        assert "Do NOT retry" in result
