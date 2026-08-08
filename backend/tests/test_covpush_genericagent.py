"""Coverage-push + bug-hunt tests for core.generic_agent (TDD).

Bugs found via red tests first:
- GA-1: ``execute()`` calls ``self.llm._get_handler().analyze_query_complexity()``
  OUTSIDE its try/except. When no LLM provider is configured
  (``NoProvidersConfiguredError``), the whole execution raises instead of
  returning the designed ``{"status": "failed"}`` dict.
"""

import asyncio
import base64
import contextlib
import json
import os
import sys
import types
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

os.environ["TESTING"] = "1"

import pytest

import core.generic_agent as ga
from core.generic_agent import GenericAgent
from core.models import AgentRegistry, HITLActionStatus


def _agent_model(config=None, agent_id="agent-123", name="Test Agent"):
    return AgentRegistry(
        id=agent_id,
        name=name,
        type="assistant",
        module_path="agents.assistant",
        class_name="AssistantAgent",
        category="general",
        configuration=config or {},
    )


@pytest.fixture
def env(monkeypatch):
    mocks = {}

    world = AsyncMock()
    world.recall_experiences.return_value = {}
    world.record_experience = AsyncMock()
    mocks["world"] = world

    reflection = MagicMock()
    reflection.generate_critique = AsyncMock(return_value=None)
    reflection.get_relevant_critiques = AsyncMock(return_value=[])
    mocks["reflection"] = reflection

    llm = AsyncMock()
    llm.generate = AsyncMock(return_value=None)
    handler = SimpleNamespace(
        default_provider_id="openai",
        analyze_query_complexity=lambda p: SimpleNamespace(value="simple"),
    )
    llm._get_handler = MagicMock(return_value=handler)
    mocks["llm"] = llm
    mocks["handler"] = handler

    mcp = AsyncMock()
    mcp.get_all_tools.return_value = []
    mcp.call_tool.return_value = "tool result"
    mcp.search_tools.return_value = []
    mocks["mcp"] = mcp

    gov = MagicMock()
    gov.can_perform_action_async = AsyncMock(
        return_value={"allowed": True, "requires_human_approval": False, "reason": "ok"}
    )
    gov.request_approval = MagicMock(return_value="action-1")
    gov.get_approval_status = MagicMock(return_value={"status": HITLActionStatus.APPROVED.value})
    gov.record_outcome = AsyncMock(return_value=None)
    mocks["gov"] = gov

    budget = MagicMock()
    budget.check_budget_before_action = AsyncMock(return_value={"allowed": True})
    budget.__enter__ = MagicMock(return_value=budget)
    budget.__exit__ = MagicMock(return_value=False)
    mocks["budget"] = budget

    graduation = AsyncMock()
    graduation.check_skill_promotion = AsyncMock(return_value={"promoted": False})
    mocks["graduation"] = graduation

    canvas_summary = AsyncMock()
    canvas_summary.generate_summary = AsyncMock(return_value="canvas summary text")
    mocks["canvas_summary"] = canvas_summary

    db = MagicMock()
    mocks["db"] = db

    @contextlib.contextmanager
    def _db_cm():
        yield db

    mocks["db_cm"] = _db_cm

    monkeypatch.setattr("core.generic_agent.get_db_session", _db_cm)
    monkeypatch.setattr("core.generic_agent.WorldModelService", lambda ws: world)
    monkeypatch.setattr("core.generic_agent.ReflectionService", lambda ws: reflection)
    monkeypatch.setattr("core.generic_agent.CanvasSummaryService", lambda llm_: canvas_summary)
    monkeypatch.setattr("core.generic_agent.LLMService", lambda **kw: llm)
    monkeypatch.setattr("core.generic_agent.mcp_service", mcp)
    monkeypatch.setattr("core.generic_agent.AgentGovernanceService", lambda db_: gov)
    monkeypatch.setattr("core.generic_agent.GraduationService", lambda db_: graduation)
    monkeypatch.setattr(
        "core.budget_enforcement_service.BudgetEnforcementService", lambda: budget
    )
    return mocks


def _agent(env, config=None, workspace_id="default", **kw):
    return GenericAgent(_agent_model(config=config, **kw), workspace_id=workspace_id)


def _step(thought="t", tool=None, params=None, actions=None, final=None):
    action = None
    if tool is not None:
        action = SimpleNamespace(
            model_dump=lambda: {"tool": tool, "params": params or {}}
        )
    acts = None
    if actions is not None:
        acts = [
            SimpleNamespace(
                tool=a[0],
                params=a[1],
                model_dump=lambda a=a: {"tool": a[0], "params": a[1]},
            )
            for a in actions
        ]
    return SimpleNamespace(
        thought=thought, action=action, actions=acts, final_answer=final
    )


def _prompt_from(env, call_index=-1):
    return env["llm"].generate_structured.await_args_list[call_index].kwargs["prompt"]


class TestInit:
    def test_initialization_populates_fields(self, env):
        agent = _agent(env, config={"system_prompt": "custom", "tools": ["a"]})
        assert agent.id == "agent-123"
        assert agent.name == "Test Agent"
        assert agent.system_prompt == "custom"
        assert agent.allowed_tools == ["a"]
        assert agent.session_tools == []
        assert agent.mcp is env["mcp"]

    def test_default_system_prompt_and_tools(self, env):
        agent = _agent(env)
        assert "Test Agent" in agent.system_prompt
        assert agent.allowed_tools == "*"
        assert agent.vision_enabled is False

    def test_get_registry_model(self, env):
        agent = _agent(env, config={"tools": "*"})
        reg = agent._get_registry_model()
        assert reg.id == "agent-123"
        assert reg.name == "Test Agent"
        assert reg.configuration == {"tools": "*"}


class TestExecuteLoop:
    @pytest.mark.asyncio
    async def test_success_with_final_answer(self, env):
        env["llm"].generate_structured.side_effect = [
            _step(final="Hello there")
        ]
        agent = _agent(env, config={"max_steps": 3})
        result = await agent.execute("say hello")
        assert result["status"] == "success"
        assert result["output"] == "Hello there"
        assert result["complexity"] == "simple"
        assert result["plan_adherence"] == 1.0
        env["world"].recall_experiences.assert_awaited_once()
        env["world"].record_experience.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_max_steps_with_tool_actions(self, env):
        env["llm"].generate_structured.side_effect = [
            _step(tool="browser_navigate", params={"url": "x"}),
            _step(tool="browser_navigate", params={"url": "y"}),
        ]
        agent = _agent(env, config={"max_steps": 2})
        result = await agent.execute("task")
        assert result["status"] == "max_steps_exceeded"
        assert result["output"] == "Maximum steps reached without final answer."
        assert result["plan_adherence"] == 0.5
        assert env["mcp"].call_tool.await_count == 2

    @pytest.mark.asyncio
    async def test_no_action_last_step_uses_thought(self, env):
        env["llm"].generate_structured.side_effect = [_step(thought="last thought")]
        agent = _agent(env, config={"max_steps": 1})
        result = await agent.execute("task")
        assert result["status"] == "max_steps_exceeded"
        assert result["output"] == "last thought"

    @pytest.mark.asyncio
    async def test_optimization_max_steps_override(self, env):
        env["llm"].generate_structured.side_effect = [
            _step(tool="browser_navigate"),
            _step(tool="browser_navigate"),
        ]
        agent = _agent(env, config={"max_steps": 5})
        result = await agent.execute("task", context={"optimization": {"max_steps": 1}})
        assert result["status"] == "max_steps_exceeded"
        assert env["mcp"].call_tool.await_count == 1

    @pytest.mark.asyncio
    async def test_timeout(self, env):
        async def _slow(*a, **k):
            await asyncio.sleep(0.5)
            return _step(final="too late")

        env["llm"].generate_structured.side_effect = _slow
        agent = _agent(env, config={"timeout_seconds": 0.2, "max_steps": 5})
        result = await agent.execute("task")
        assert result["status"] == "timeout"
        assert "Timed Out" in result["output"]
        assert result["plan_adherence"] == 0.0

    @pytest.mark.asyncio
    async def test_loop_exception_returns_failed(self, env):
        env["llm"].generate_structured.side_effect = RuntimeError("boom")
        agent = _agent(env, config={"max_steps": 3})
        result = await agent.execute("task")
        assert result["status"] == "failed"
        assert "Error during execution" in result["output"]
        assert result["plan_adherence"] == 0.0

    @pytest.mark.asyncio
    async def test_budget_denied_halts_cleanly(self, env):
        env["budget"].check_budget_before_action = AsyncMock(
            return_value={"allowed": False, "reason": "over budget"}
        )
        env["llm"].generate_structured.side_effect = [_step(final="unused")]
        agent = _agent(env, config={"max_steps": 3})
        result = await agent.execute("task")
        assert result["status"] == "failed"
        assert "Budget limit reached" in result["output"]
        env["llm"].generate_structured.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_step_callback_receives_starting_event(self, env):
        env["llm"].generate_structured.side_effect = [_step(final="done")]
        agent = _agent(env, config={"max_steps": 3})
        events = []

        async def cb(step_data):
            events.append(step_data)

        await agent.execute("task", step_callback=cb)
        assert events[0]["status"] == "starting"
        assert events[0]["step"] == 0
        assert any(e.get("final_answer") == "done" for e in events)

    @pytest.mark.asyncio
    async def test_audit_mode_attaches_report(self, env, monkeypatch):
        fake_mod = types.ModuleType("core.agent_auditor")
        fake_mod.auditor = SimpleNamespace(
            audit_trace=AsyncMock(return_value={"score": 8.5, "verdict": "ok"})
        )
        monkeypatch.setitem(sys.modules, "core.agent_auditor", fake_mod)
        env["llm"].generate_structured.side_effect = [_step(final="done")]
        agent = _agent(env, config={"max_steps": 3, "audit_mode": True})
        result = await agent.execute("task")
        assert result["audit_report"]["score"] == 8.5

    @pytest.mark.asyncio
    async def test_audit_mode_failure_is_nonfatal(self, env, monkeypatch):
        fake_mod = types.ModuleType("core.agent_auditor")
        fake_mod.auditor = SimpleNamespace(
            audit_trace=AsyncMock(side_effect=RuntimeError("audit down"))
        )
        monkeypatch.setitem(sys.modules, "core.agent_auditor", fake_mod)
        env["llm"].generate_structured.side_effect = [_step(final="done")]
        agent = _agent(env, config={"max_steps": 3, "audit_mode": True})
        result = await agent.execute("task")
        assert result["status"] == "success"
        assert result["audit_report"] is None

    @pytest.mark.asyncio
    async def test_audit_mode_missing_module_degrades_gracefully(self, env, monkeypatch):
        """core.agent_auditor does not exist in the tree — audit must not break runs."""
        env["llm"].generate_structured.side_effect = [_step(final="done")]
        agent = _agent(env, config={"max_steps": 3, "audit_mode": True})
        result = await agent.execute("task")
        assert result["status"] == "success"
        assert result["audit_report"] is None

    @pytest.mark.asyncio
    async def test_mcp_tool_search_lazy_loads_session_tools(self, env):
        env["llm"].generate_structured.side_effect = [
            _step(tool="mcp_tool_search", params={"query": "email"}),
            _step(final="found"),
        ]
        env["mcp"].call_tool.return_value = "Found 2 tools: email_send, email_list"
        env["mcp"].search_tools.return_value = [{"name": "email_send"}, {"name": "email_list"}]
        agent = _agent(env, config={"max_steps": 3, "tools": "*"})
        result = await agent.execute("task")
        assert result["status"] == "success"
        assert len(agent.session_tools) == 2
        env["mcp"].search_tools.assert_awaited_once_with("email", limit=5)

    @pytest.mark.asyncio
    async def test_tool_not_in_allowed_list_skipped(self, env):
        env["llm"].generate_structured.side_effect = [
            _step(tool="browser_screenshot"),
            _step(final="done"),
        ]
        agent = _agent(env, config={"max_steps": 3, "tools": ["browser_navigate"]})
        result = await agent.execute("task")
        assert result["status"] == "success"
        env["mcp"].call_tool.assert_not_awaited()
        assert "not allowed" in result["steps"][0]["output"]

    @pytest.mark.asyncio
    async def test_error_observation_appends_critique(self, env):
        env["llm"].generate_structured.side_effect = [
            _step(tool="browser_navigate"),
            _step(final="recovered"),
        ]
        env["mcp"].call_tool.return_value = "Tool error. Connection refused."
        agent = _agent(env, config={"max_steps": 3, "tools": "*"})
        result = await agent.execute("task")
        assert result["status"] == "success"
        second_prompt = _prompt_from(env, 1)
        assert "[CRITIQUE]" in second_prompt

    @pytest.mark.asyncio
    async def test_compression_replaces_verbose_output(self, env):
        from core.llm import compression

        def _compress(text):
            return ("[compressed]", SimpleNamespace(savings_tokens=50))

        compression.get_compression_pipeline = MagicMock(
            return_value=SimpleNamespace(compress_tool_output=_compress)
        )
        env["llm"].generate_structured.side_effect = [
            _step(tool="browser_navigate"),
            _step(final="done"),
        ]
        env["mcp"].call_tool.return_value = "x" * 5000
        agent = _agent(env, config={"max_steps": 3, "tools": "*"})
        result = await agent.execute("task")
        assert "[compressed]" in _prompt_from(env, 1)

    @pytest.mark.asyncio
    async def test_compression_zero_savings_keeps_output(self, env):
        from core.llm import compression

        compression.get_compression_pipeline = MagicMock(
            return_value=SimpleNamespace(
                compress_tool_output=lambda t: (t, SimpleNamespace(savings_tokens=0))
            )
        )
        env["llm"].generate_structured.side_effect = [
            _step(tool="browser_navigate"),
            _step(final="done"),
        ]
        env["mcp"].call_tool.return_value = "raw observation"
        agent = _agent(env, config={"max_steps": 3, "tools": "*"})
        result = await agent.execute("task")
        assert result["steps"][0]["output"] == "raw observation"

    @pytest.mark.asyncio
    async def test_observation_filter_replaces_history(self, env):
        monkey_filtered = []

        class _FakeObsFilter:
            def __init__(self, llm):
                pass

            async def filter_history(self, history, step, task):
                return "FILTERED HISTORY", {"savings_tokens": 25}

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(ga, "_OBS_FILTER_AVAILABLE", True)
        monkeypatch.setattr(ga, "OBSERVATION_FILTER_ENABLED", True)
        monkeypatch.setattr(ga, "ObservationFilterService", _FakeObsFilter)
        try:
            env["llm"].generate_structured.side_effect = [
                _step(tool="browser_navigate"),
                _step(final="done"),
            ]
            env["mcp"].call_tool.return_value = "tool result"
            agent = _agent(env, config={"max_steps": 3, "tools": "*"})
            result = await agent.execute("task")
            assert result["status"] == "success"
            assert "FILTERED HISTORY" in _prompt_from(env, 1)
        finally:
            monkeypatch.undo()

    @pytest.mark.asyncio
    async def test_observation_filter_error_is_ignored(self, env):
        class _BoomFilter:
            def __init__(self, llm):
                pass

            async def filter_history(self, history, step, task):
                raise RuntimeError("filter down")

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(ga, "_OBS_FILTER_AVAILABLE", True)
        monkeypatch.setattr(ga, "OBSERVATION_FILTER_ENABLED", True)
        monkeypatch.setattr(ga, "ObservationFilterService", _BoomFilter)
        try:
            env["llm"].generate_structured.side_effect = [
                _step(tool="browser_navigate"),
                _step(final="done"),
            ]
            env["mcp"].call_tool.return_value = "tool result"
            agent = _agent(env, config={"max_steps": 3, "tools": "*"})
            result = await agent.execute("task")
            assert result["status"] == "success"
        finally:
            monkeypatch.undo()

    @pytest.mark.asyncio
    async def test_parallel_error_observation_appends_critique(self, env):
        env["llm"].generate_structured.side_effect = [
            _step(actions=[("tool_a", {})]),
            _step(final="recovered"),
        ]
        env["mcp"].call_tool.return_value = "Tool error. Retry."
        agent = _agent(env, config={"max_steps": 3, "tools": "*"})
        result = await agent.execute("task")
        assert result["status"] == "success"
        assert "[CRITIQUE]" in _prompt_from(env, 1)

    @pytest.mark.asyncio
    async def test_compression_exception_never_breaks_loop(self, env):
        def _boom(text):
            raise RuntimeError("compression down")

        from core.llm import compression

        compression.get_compression_pipeline = MagicMock(
            return_value=SimpleNamespace(compress_tool_output=_boom)
        )
        env["llm"].generate_structured.side_effect = [
            _step(tool="browser_navigate"),
            _step(final="done"),
        ]
        env["mcp"].call_tool.return_value = "raw output"
        agent = _agent(env, config={"max_steps": 3, "tools": "*"})
        result = await agent.execute("task")
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_step_callback_after_action_execution(self, env):
        env["llm"].generate_structured.side_effect = [
            _step(tool="browser_navigate"),
            _step(final="done"),
        ]
        agent = _agent(env, config={"max_steps": 3, "tools": "*"})
        events = []

        async def cb(step_data):
            events.append(step_data)

        await agent.execute("task", step_callback=cb)
        action_events = [e for e in events if e.get("action") and e.get("output")]
        assert len(action_events) == 2
        assert action_events[0]["output"] == "tool result"

    @pytest.mark.asyncio
    async def test_step_act_hitl_paused_callback(self, env):
        env["gov"].can_perform_action_async = AsyncMock(
            return_value={
                "allowed": True,
                "requires_human_approval": True,
                "reason": "needs review",
            }
        )
        events = []

        async def cb(step_data):
            events.append(step_data)

        agent = _agent(env, config={"tools": "*"})
        obs = await agent._step_act("browser_navigate", {}, step_callback=cb)
        assert obs == "tool result"
        paused = [e for e in events if e.get("type") == "hitl_paused"]
        assert len(paused) == 1
        assert paused[0]["action_id"] == "action-1"

    @pytest.mark.asyncio
    async def test_wait_for_approval_pending_then_timeout(self, env, monkeypatch):
        env["gov"].get_approval_status.return_value = {
            "status": HITLActionStatus.PENDING.value
        }
        monkeypatch.setattr("asyncio.sleep", AsyncMock(return_value=None))
        agent = _agent(env, config={"hitl_timeout": 5})
        assert await agent._wait_for_approval("a1") is False

    @pytest.mark.asyncio
    async def test_wait_for_all_approvals_pending_then_timeout(self, env, monkeypatch):
        env["gov"].get_approval_status.return_value = {
            "status": HITLActionStatus.PENDING.value
        }
        monkeypatch.setattr("asyncio.sleep", AsyncMock(return_value=None))
        agent = _agent(env, config={"hitl_timeout": 5})
        assert await agent._wait_for_all_approvals(["a1", "a2"]) is False

    @pytest.mark.asyncio
    async def test_parallel_batch_hitl_paused_callback_and_approve(self, env):
        env["gov"].can_perform_action_async = AsyncMock(
            return_value={
                "allowed": True,
                "requires_human_approval": True,
                "reason": "review",
            }
        )
        env["mcp"].call_tool.return_value = "batch result"
        events = []

        async def cb(step_data):
            events.append(step_data)

        agent = _agent(env, config={"tools": "*"})
        agent._wait_for_all_approvals = AsyncMock(return_value=True)
        with patch(
            "core.hallucination_config.is_parallel_tools_enabled", return_value=True
        ), patch("core.hallucination_config.get_max_parallel_tools", return_value=4):
            records = await agent._execute_parallel_tools(
                [SimpleNamespace(tool="a", params={})], {}, cb
            )
        assert records[0]["output"] == "batch result"
        paused = [e for e in events if e.get("type") == "hitl_paused"]
        assert paused[0]["parallel_batch"] is True

    @pytest.mark.asyncio
    async def test_parallel_hitl_reject_callback_flow(self, env):
        env["gov"].can_perform_action_async = AsyncMock(
            return_value={
                "allowed": True,
                "requires_human_approval": True,
                "reason": "review",
            }
        )
        agent = _agent(env, config={"tools": "*"})
        agent._wait_for_all_approvals = AsyncMock(return_value=False)
        with patch(
            "core.hallucination_config.is_parallel_tools_enabled", return_value=True
        ), patch("core.hallucination_config.get_max_parallel_tools", return_value=4):
            records = await agent._execute_parallel_tools(
                [SimpleNamespace(tool="a", params={})], {}, None
            )
        assert records[0]["verified_kind"] == "rejected"

    @pytest.mark.asyncio
    async def test_parallel_tools_executed_in_loop(self, env):
        env["llm"].generate_structured.side_effect = [
            _step(actions=[("tool_a", {"x": 1}), ("tool_b", {"y": 2})]),
            _step(final="done"),
        ]
        env["mcp"].call_tool.side_effect = ["result a", "result b"]
        agent = _agent(env, config={"max_steps": 3, "tools": "*"})
        events = []

        async def cb(step_data):
            events.append(step_data)

        result = await agent.execute("task", step_callback=cb)
        assert result["status"] == "success"
        acted = [s for s in result["steps"] if s["action"]]
        tool_names = [s["action"]["tool"] for s in acted]
        assert "tool_a" in tool_names and "tool_b" in tool_names
        parallel_records = [
            e
            for e in events
            if (e.get("action") or {}).get("tool") in ("tool_a", "tool_b")
        ]
        assert len(parallel_records) == 2

    @pytest.mark.asyncio
    async def test_actions_promoted_when_parallel_disabled(self, env):
        env["llm"].generate_structured.side_effect = [
            _step(actions=[("tool_a", {"x": 1}), ("tool_b", {"y": 2})]),
            _step(final="done"),
        ]
        env["mcp"].call_tool.return_value = "result a"
        agent = _agent(env, config={"max_steps": 3, "tools": "*"})
        with patch(
            "core.hallucination_config.is_parallel_tools_enabled", return_value=False
        ):
            result = await agent.execute("task")
        assert result["status"] == "success"
        assert env["mcp"].call_tool.await_count == 1

    @pytest.mark.asyncio
    async def test_critique_generation_on_failure(self, env):
        env["llm"].generate_structured.side_effect = RuntimeError("boom")
        agent = _agent(env, config={"max_steps": 3, "specialty": "data"})
        result = await agent.execute("task")
        assert result["status"] == "failed"
        env["reflection"].generate_critique.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_critique_failure_is_nonfatal(self, env):
        env["reflection"].generate_critique = AsyncMock(
            side_effect=RuntimeError("reflection down")
        )
        env["llm"].generate_structured.side_effect = RuntimeError("boom")
        agent = _agent(env, config={"max_steps": 3})
        result = await agent.execute("task")
        assert result["status"] == "failed"


class TestExecuteComplexityBug:
    @pytest.mark.asyncio
    async def test_handler_unavailable_returns_failed_dict(self, env):
        """GA-1 (red first): no provider configured must NOT raise out of execute()."""
        from core.llm.byok_handler import NoProvidersConfiguredError

        env["llm"].generate_structured.side_effect = NoProvidersConfiguredError("no providers")
        env["llm"]._get_handler.side_effect = NoProvidersConfiguredError("no providers")
        agent = _agent(env, config={"max_steps": 3})
        result = await agent.execute("task")
        assert result["status"] == "failed"
        assert "Error during execution" in result["output"]
        assert result["complexity"] == "moderate"


class TestReactStep:
    @pytest.mark.asyncio
    async def test_core_tools_filtered_and_search_injected(self, env):
        env["mcp"].get_all_tools.return_value = [
            {"name": "mcp_tool_search", "description": "s"},
            {"name": "save_business_fact", "description": "f"},
            {"name": "some_other", "description": "o"},
        ]
        env["llm"].generate_structured.return_value = _step(final="ok")
        agent = _agent(env, config={"max_steps": 3})
        step = await agent._react_step("task", {}, "")
        assert step.final_answer == "ok"
        sys_instr = env["llm"].generate_structured.await_args_list[0].kwargs[
            "system_instruction"
        ]
        tool_block = sys_instr.split("AVAILABLE TOOLS:")[1].split("FORMAT:")[0].strip()
        tools = json.loads(tool_block)
        assert [t["name"] for t in tools] == ["mcp_tool_search", "save_business_fact"]

    @pytest.mark.asyncio
    async def test_explicit_allowed_tools(self, env):
        env["mcp"].get_all_tools.return_value = [
            {"name": "a", "description": ""},
            {"name": "b", "description": ""},
            {"name": "c", "description": ""},
        ]
        env["llm"].generate_structured.return_value = _step(final="ok")
        agent = _agent(env, config={"tools": ["b", "c"]})
        await agent._react_step("task", {}, "")
        tool_block = env["llm"].generate_structured.await_args_list[0].kwargs[
            "system_instruction"
        ]
        assert '"name": "b"' in tool_block and '"name": "a"' not in tool_block

    @pytest.mark.asyncio
    async def test_mentorship_mode_appends_focus(self, env):
        env["llm"].generate_structured.return_value = _step(final="ok")
        agent = _agent(env, config={"max_steps": 3})
        await agent._react_step(
            "task", {}, "", context={"optimization": {"mentorship_mode": True}}
        )
        sys = env["llm"].generate_structured.await_args_list[0].kwargs["system_instruction"]
        assert "MENTORSHIP FOCUS" in sys

    @pytest.mark.asyncio
    async def test_memory_sections_built(self, env):
        env["world"].recall_experiences.return_value = {
            "experiences": [{"input_summary": "prev task", "outcome": "success"}],
            "knowledge": [{"text": "doc text"}],
            "formulas": [{"name": "growth", "description": "calc"}],
            "business_facts": [
                SimpleNamespace(
                    verification_status="verified",
                    fact="2+2=4",
                    metadata={"source": "manual"},
                )
            ],
        }
        env["llm"].generate_structured.return_value = _step(final="ok")
        agent = _agent(env, config={"max_steps": 3})
        await agent._react_step("task", env["world"].recall_experiences.return_value, "")
        prompt = _prompt_from(env)
        assert "PAST EXPERIENCES" in prompt
        assert "RELEVANT KNOWLEDGE" in prompt
        assert "AVAILABLE FORMULAS" in prompt
        assert "TRUSTED BUSINESS FACTS" in prompt
        assert "2+2=4" in prompt

    @pytest.mark.asyncio
    async def test_no_memory_placeholder(self, env):
        env["llm"].generate_structured.return_value = _step(final="ok")
        agent = _agent(env, config={"max_steps": 3})
        await agent._react_step("task", {}, "")
        assert "(No prior context)" in _prompt_from(env)

    @pytest.mark.asyncio
    async def test_chaos_noise_injection(self, env):
        env["llm"].generate_structured.return_value = _step(final="ok")
        agent = _agent(env, config={"chaos_noise_level": 1.0})
        with patch("random.random", return_value=0.1):
            await agent._react_step("task", {}, "")
        assert "UNCORRELATED_SIGNAL" in _prompt_from(env)

    @pytest.mark.asyncio
    async def test_no_noise_when_level_zero(self, env):
        env["llm"].generate_structured.return_value = _step(final="ok")
        agent = _agent(env, config={"chaos_noise_level": 0.0})
        await agent._react_step("task", {}, "")
        assert "UNCORRELATED_SIGNAL" not in _prompt_from(env)

    @pytest.mark.asyncio
    async def test_canvas_summary_used_when_vision_disabled(self, env):
        env["llm"].generate_structured.return_value = _step(final="ok")
        agent = _agent(env, config={"max_steps": 3})
        await agent._react_step(
            "task",
            {},
            "",
            context={"canvas_id": "c1", "canvas_state": {"a": 1}, "canvas_type": "dashboard"},
        )
        prompt = _prompt_from(env)
        assert "SEMANTIC UI LAYOUT" in prompt
        assert "canvas summary text" in prompt
        env["canvas_summary"].generate_summary.assert_awaited_once_with(
            canvas_type="dashboard", canvas_state={"a": 1}, agent_task="task"
        )

    @pytest.mark.asyncio
    async def test_canvas_summary_failure_is_nonfatal(self, env):
        env["canvas_summary"].generate_summary = AsyncMock(
            side_effect=RuntimeError("summary down")
        )
        env["llm"].generate_structured.return_value = _step(final="ok")
        agent = _agent(env, config={"max_steps": 3})
        await agent._react_step(
            "task", {}, "", context={"canvas_id": "c1", "canvas_state": {"a": 1}}
        )
        assert "SEMANTIC UI LAYOUT" not in _prompt_from(env)

    @pytest.mark.asyncio
    async def test_minimax_provider_uses_summary_even_with_vision(self, env):
        env["handler"].default_provider_id = "minimax"
        env["llm"].generate_structured.return_value = _step(final="ok")
        agent = _agent(env, config={"max_steps": 3})
        await agent._react_step(
            "task", {}, "", context={"canvas_id": "c1", "canvas_state": {"a": 1}}
        )
        assert "SEMANTIC UI LAYOUT" in _prompt_from(env)

    @pytest.mark.asyncio
    async def test_vision_screenshot_passed_as_image(self, env):
        env["llm"].generate_structured.return_value = _step(final="ok")
        model = _agent_model(config={"max_steps": 3})
        model.vision_enabled = True
        agent = GenericAgent(model)
        agent.last_screenshot = "base64data"
        await agent._react_step("task", {}, "")
        kwargs = env["llm"].generate_structured.await_args_list[0].kwargs
        assert kwargs["image_payload"] == "base64data"
        assert agent.last_screenshot is None

    @pytest.mark.asyncio
    async def test_critiques_included_in_prompt(self, env):
        env["reflection"].get_relevant_critiques.return_value = [
            SimpleNamespace(critique="verify outputs")
        ]
        env["llm"].generate_structured.return_value = _step(final="ok")
        agent = _agent(env, config={"max_steps": 3})
        await agent._react_step("task", {}, "")
        assert "SELF-EVOLUTION CRITIQUES" in _prompt_from(env)
        assert "verify outputs" in _prompt_from(env)

    @pytest.mark.asyncio
    async def test_field_guide_appended(self, env):
        from core import field_guide_service

        field_guide_service.get_field_guide_service = MagicMock(
            return_value=SimpleNamespace(
                get_field_guide_context=lambda ws: "FIELD GUIDE BLOCK"
            )
        )
        env["llm"].generate_structured.return_value = _step(final="ok")
        agent = _agent(env, config={"max_steps": 3})
        await agent._react_step("task", {}, "")
        assert "FIELD GUIDE BLOCK" in _prompt_from(env)

    @pytest.mark.asyncio
    async def test_field_guide_failure_ignored(self, env):
        from core import field_guide_service

        def _boom(ws):
            raise RuntimeError("guide down")

        field_guide_service.get_field_guide_service = MagicMock(
            return_value=SimpleNamespace(get_field_guide_context=_boom)
        )
        env["llm"].generate_structured.return_value = _step(final="ok")
        agent = _agent(env, config={"max_steps": 3})
        await agent._react_step("task", {}, "")
        assert "guide down" not in _prompt_from(env)

    @pytest.mark.asyncio
    async def test_raw_fallback_none(self, env):
        env["llm"].generate_structured.return_value = None
        env["llm"].generate.return_value = None
        agent = _agent(env, config={"max_steps": 3})
        step = await agent._react_step("task", {}, "")
        assert step.thought == "LLM not available"
        assert "LLM not configured" in step.final_answer

    @pytest.mark.asyncio
    async def test_raw_fallback_not_initialized(self, env):
        env["llm"].generate_structured.return_value = None
        env["llm"].generate.return_value = "LLM not initialized for this workspace"
        agent = _agent(env, config={"max_steps": 3})
        step = await agent._react_step("task", {}, "")
        assert step.thought == "LLM not available"
        assert step.final_answer == "LLM not initialized for this workspace"

    @pytest.mark.asyncio
    async def test_raw_fallback_final_marker(self, env):
        env["llm"].generate_structured.return_value = None
        env["llm"].generate.return_value = "Final Answer: 42"
        agent = _agent(env, config={"max_steps": 3})
        step = await agent._react_step("task", {}, "")
        assert step.final_answer == "Final Answer: 42"

    @pytest.mark.asyncio
    async def test_raw_fallback_plain_response(self, env):
        env["llm"].generate_structured.return_value = None
        env["llm"].generate.return_value = "just reasoning aloud"
        agent = _agent(env, config={"max_steps": 3})
        step = await agent._react_step("task", {}, "")
        assert step.final_answer is None
        assert step.thought == "just reasoning aloud"

    @pytest.mark.asyncio
    async def test_reasoning_tier_maps_to_quality_for_raw(self, env):
        env["llm"].generate_structured.return_value = None
        env["llm"].generate.return_value = None
        agent = _agent(env, config={"max_steps": 3})
        await agent._react_step(
            "task", {}, "", context={"optimization": {"model": "reasoning"}}
        )
        kwargs = env["llm"].generate.await_args_list[0].kwargs
        assert kwargs["model"] == "quality"


class TestStepAct:
    @pytest.mark.asyncio
    async def test_governance_allows_execution(self, env):
        env["mcp"].call_tool.return_value = "executed"
        agent = _agent(env, config={"tools": "*"})
        obs = await agent._step_act("browser_navigate", {"url": "x"})
        assert obs == "executed"
        env["gov"].can_perform_action_async.assert_awaited_once_with(
            "agent-123", "browser_navigate"
        )

    @pytest.mark.asyncio
    async def test_hitl_approval_flows_through(self, env):
        env["gov"].can_perform_action_async = AsyncMock(
            return_value={
                "allowed": True,
                "requires_human_approval": True,
                "reason": "needs review",
            }
        )
        env["gov"].get_approval_status.return_value = {
            "status": HITLActionStatus.APPROVED.value
        }
        env["mcp"].call_tool.return_value = "executed"
        agent = _agent(env, config={"tools": "*"})
        obs = await agent._step_act("browser_navigate", {})
        assert obs == "executed"
        env["gov"].request_approval.assert_called_once()

    @pytest.mark.asyncio
    async def test_hitl_rejection_blocks_tool(self, env):
        env["gov"].can_perform_action_async = AsyncMock(
            return_value={
                "allowed": True,
                "requires_human_approval": True,
                "reason": "needs review",
            }
        )
        env["gov"].get_approval_status.return_value = {
            "status": HITLActionStatus.REJECTED.value
        }
        agent = _agent(env, config={"tools": "*"})
        obs = await agent._step_act("browser_navigate", {})
        assert "REJECTED" in obs
        env["mcp"].call_tool.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_governance_denied(self, env):
        env["gov"].can_perform_action_async = AsyncMock(
            return_value={"allowed": False, "requires_human_approval": False, "reason": "maturity"}
        )
        agent = _agent(env, config={"tools": "*"})
        obs = await agent._step_act("browser_navigate", {})
        assert "maturity" in obs
        env["mcp"].call_tool.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_pre_approved_skips_governance(self, env):
        env["mcp"].call_tool.return_value = "executed"
        agent = _agent(env, config={"tools": "*"})
        obs = await agent._step_act("browser_navigate", {}, pre_approved=True)
        assert obs == "executed"
        env["gov"].can_perform_action_async.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_tool_not_found_error(self, env):
        env["mcp"].call_tool.side_effect = ValueError("Tool 'x' not found")
        agent = _agent(env, config={"tools": "*"})
        obs = await agent._step_act("x", {})
        assert "not found" in obs

    @pytest.mark.asyncio
    async def test_validation_error(self, env):
        env["mcp"].call_tool.side_effect = ValueError("Invalid arguments for tool")
        agent = _agent(env, config={"tools": "*"})
        obs = await agent._step_act("x", {})
        assert "Invalid arguments" in obs

    @pytest.mark.asyncio
    async def test_timeout_error(self, env):
        env["mcp"].call_tool.side_effect = TimeoutError("request timeout exceeded")
        agent = _agent(env, config={"tools": "*"})
        obs = await agent._step_act("x", {})
        assert "timed out" in obs

    @pytest.mark.asyncio
    async def test_generic_error(self, env):
        env["mcp"].call_tool.side_effect = RuntimeError("boom")
        agent = _agent(env, config={"tools": "*"})
        obs = await agent._step_act("x", {})
        assert "Tool Execution Failed" in obs

    @pytest.mark.asyncio
    async def test_screenshot_capture(self, env):
        env["llm"].generate_structured.side_effect = [
            _step(tool="browser_screenshot"),
        ]
        env["mcp"].call_tool.return_value = "Screenshot saved to /tmp/shot.png"
        with patch("os.path.exists", return_value=True), patch(
            "builtins.open", create=True
        ) as mock_open, patch("base64.b64encode", return_value=b"b64data"):
            mock_open.return_value.__enter__.return_value.read.return_value = b"img"
            agent = _agent(env, config={"tools": "*", "max_steps": 1})
            result = await agent.execute("task")
        assert result["status"] == "max_steps_exceeded"
        assert agent.last_screenshot == "b64data"

    @pytest.mark.asyncio
    async def test_screenshot_capture_failure_ignored(self, env):
        env["llm"].generate_structured.side_effect = [
            _step(tool="browser_screenshot"),
        ]
        env["mcp"].call_tool.return_value = "Screenshot saved to /tmp/shot.png"
        with patch("os.path.exists", return_value=True), patch(
            "builtins.open", side_effect=OSError("nope"), create=True
        ):
            agent = _agent(env, config={"tools": "*", "max_steps": 1})
            result = await agent.execute("task")
        assert result["status"] == "max_steps_exceeded"
        assert agent.last_screenshot is None


class TestRecordExecution:
    @pytest.mark.asyncio
    async def test_success_records_experience_and_graduation(self, env):
        env["graduation"].check_skill_promotion.return_value = {"promoted": True}
        agent = _agent(
            env,
            config={"active_skill_id": "sk-1", "role": "specialty_agent", "specialty": "data"},
        )
        result = {
            "status": "success",
            "output": "ok",
            "steps": [1],
            "complexity": "simple",
            "step_efficiency": 1.0,
            "plan_adherence": 1.0,
            "audit_report": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await agent._record_execution("task", result)
        env["world"].record_experience.assert_awaited_once()
        exp = env["world"].record_experience.await_args_list[0].args[0]
        assert exp.confidence_score == 1.0
        assert exp.task_type == "custom_task_react"
        env["gov"].record_outcome.assert_awaited_once_with("agent-123", success=True)
        env["graduation"].check_skill_promotion.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_graduation_error_nonfatal(self, env):
        env["graduation"].check_skill_promotion = AsyncMock(
            side_effect=RuntimeError("graduation down")
        )
        agent = _agent(env, config={"active_skill_id": "sk-1"})
        result = {
            "status": "success",
            "output": "ok",
            "steps": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await agent._record_execution("task", result)

    @pytest.mark.asyncio
    async def test_failed_status_zero_confidence(self, env):
        agent = _agent(env, config={"tools": "*"})
        result = {
            "status": "failed",
            "output": "nope",
            "steps": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await agent._record_execution("task", result)
        exp = env["world"].record_experience.await_args_list[0].args[0]
        assert exp.confidence_score == 0.0
        env["gov"].record_outcome.assert_awaited_once_with("agent-123", success=False)

    @pytest.mark.asyncio
    async def test_max_steps_half_confidence(self, env):
        agent = _agent(env, config={"tools": "*"})
        result = {
            "status": "max_steps_exceeded",
            "output": "out",
            "steps": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await agent._record_execution("task", result)
        exp = env["world"].record_experience.await_args_list[0].args[0]
        assert exp.confidence_score == 0.5

    @pytest.mark.asyncio
    async def test_governance_record_failure_nonfatal(self, env):
        env["gov"].record_outcome = AsyncMock(side_effect=RuntimeError("gov down"))
        agent = _agent(env, config={"tools": "*"})
        result = {
            "status": "success",
            "output": "ok",
            "steps": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await agent._record_execution("task", result)


class TestWaitForApproval:
    @pytest.mark.asyncio
    async def test_approved(self, env):
        env["gov"].get_approval_status.return_value = {
            "status": HITLActionStatus.APPROVED.value
        }
        agent = _agent(env, config={"hitl_timeout": 60})
        assert await agent._wait_for_approval("a1") is True

    @pytest.mark.asyncio
    async def test_rejected(self, env):
        env["gov"].get_approval_status.return_value = {
            "status": HITLActionStatus.REJECTED.value
        }
        agent = _agent(env, config={"hitl_timeout": 60})
        assert await agent._wait_for_approval("a1") is False

    @pytest.mark.asyncio
    async def test_timeout(self, env):
        env["gov"].get_approval_status.return_value = {
            "status": HITLActionStatus.PENDING.value
        }
        agent = _agent(env, config={"hitl_timeout": 0})
        assert await agent._wait_for_approval("a1") is False


class TestWaitForAllApprovals:
    @pytest.mark.asyncio
    async def test_all_approved(self, env):
        env["gov"].get_approval_status.return_value = {
            "status": HITLActionStatus.APPROVED.value
        }
        agent = _agent(env, config={"hitl_timeout": 60})
        assert await agent._wait_for_all_approvals(["a1", "a2"]) is True

    @pytest.mark.asyncio
    async def test_one_rejected(self, env):
        def _status(action_id):
            if action_id == "a1":
                return {"status": HITLActionStatus.APPROVED.value}
            return {"status": HITLActionStatus.REJECTED.value}

        env["gov"].get_approval_status.side_effect = _status
        agent = _agent(env, config={"hitl_timeout": 60})
        assert await agent._wait_for_all_approvals(["a1", "a2"]) is False

    @pytest.mark.asyncio
    async def test_timeout(self, env):
        env["gov"].get_approval_status.return_value = {
            "status": HITLActionStatus.PENDING.value
        }
        agent = _agent(env, config={"hitl_timeout": 0})
        assert await agent._wait_for_all_approvals(["a1", "a2"]) is False


class TestExecuteParallelTools:
    @pytest.mark.asyncio
    async def test_sequential_fallback_when_disabled(self, env):
        env["mcp"].call_tool.side_effect = ["r1", "r2"]
        agent = _agent(env, config={"tools": "*"})
        with patch(
            "core.hallucination_config.is_parallel_tools_enabled", return_value=False
        ), patch("core.hallucination_config.get_max_parallel_tools", return_value=2):
            records = await agent._execute_parallel_tools(
                [
                    SimpleNamespace(tool="a", params={}),
                    SimpleNamespace(tool="b", params={}),
                    SimpleNamespace(tool="c", params={}),
                ],
                {},
                None,
            )
        assert [r["tool_name"] for r in records] == ["a", "b"]
        assert records[0]["verified_kind"] == "unverified"
        assert env["mcp"].call_tool.await_count == 2

    @pytest.mark.asyncio
    async def test_blocked_batch_aborts_all(self, env):
        env["gov"].can_perform_action_async = AsyncMock(
            return_value={"allowed": False, "requires_human_approval": False, "reason": "blocked"}
        )
        agent = _agent(env, config={"tools": "*"})
        with patch(
            "core.hallucination_config.is_parallel_tools_enabled", return_value=True
        ), patch("core.hallucination_config.get_max_parallel_tools", return_value=4):
            records = await agent._execute_parallel_tools(
                [
                    SimpleNamespace(tool="a", params={}),
                    SimpleNamespace(tool="b", params={}),
                ],
                {},
                None,
            )
        assert len(records) == 2
        assert all(r["verified_kind"] == "blocked" for r in records)
        assert all("Governance Error" in r["output"] for r in records)
        env["mcp"].call_tool.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejected_batch(self, env):
        env["gov"].can_perform_action_async = AsyncMock(
            return_value={
                "allowed": True,
                "requires_human_approval": True,
                "reason": "review",
            }
        )
        agent = _agent(env, config={"tools": "*"})
        agent._wait_for_all_approvals = AsyncMock(return_value=False)
        with patch(
            "core.hallucination_config.is_parallel_tools_enabled", return_value=True
        ), patch("core.hallucination_config.get_max_parallel_tools", return_value=4):
            records = await agent._execute_parallel_tools(
                [SimpleNamespace(tool="a", params={})], {}, None
            )
        assert records[0]["verified_kind"] == "rejected"
        assert "REJECTED" in records[0]["output"]
        env["mcp"].call_tool.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_batch_executes_with_preapproval(self, env):
        env["mcp"].call_tool.side_effect = ["r1", "r2"]
        agent = _agent(env, config={"tools": "*"})
        with patch(
            "core.hallucination_config.is_parallel_tools_enabled", return_value=True
        ), patch("core.hallucination_config.get_max_parallel_tools", return_value=4):
            records = await agent._execute_parallel_tools(
                [
                    SimpleNamespace(tool="a", params={"x": 1}),
                    SimpleNamespace(tool="b", params={"y": 2}),
                ],
                {},
                None,
            )
        assert [r["tool_name"] for r in records] == ["a", "b"]
        assert [r["output"] for r in records] == ["r1", "r2"]
        env["gov"].can_perform_action_async.assert_awaited()

    @pytest.mark.asyncio
    async def test_gather_exception_recorded(self, env):
        async def _boom(tool, args, context=None, step_callback=None, pre_approved=False):
            raise RuntimeError("tool died")

        agent = _agent(env, config={"tools": "*"})
        agent._step_act = _boom
        with patch(
            "core.hallucination_config.is_parallel_tools_enabled", return_value=True
        ), patch("core.hallucination_config.get_max_parallel_tools", return_value=4):
            records = await agent._execute_parallel_tools(
                [SimpleNamespace(tool="a", params={})], {}, None
            )
        assert "Tool Execution Failed" in records[0]["output"]

    @pytest.mark.asyncio
    async def test_serial_search_action(self, env):
        env["mcp"].search_tools.return_value = [{"name": "t1"}, {"name": "t2"}]
        agent = _agent(env, config={"tools": "*"})
        with patch(
            "core.hallucination_config.is_parallel_tools_enabled", return_value=True
        ), patch("core.hallucination_config.get_max_parallel_tools", return_value=4):
            records = await agent._execute_parallel_tools(
                [SimpleNamespace(tool="mcp_tool_search", params={"query": "mail"})],
                {},
                None,
            )
        assert "Found 2 new tools" in records[0]["output"]
        assert agent.session_tools == [{"name": "t1"}, {"name": "t2"}]

    @pytest.mark.asyncio
    async def test_serial_search_failure(self, env):
        env["mcp"].search_tools.side_effect = RuntimeError("search down")
        agent = _agent(env, config={"tools": "*"})
        with patch(
            "core.hallucination_config.is_parallel_tools_enabled", return_value=True
        ), patch("core.hallucination_config.get_max_parallel_tools", return_value=4):
            records = await agent._execute_parallel_tools(
                [SimpleNamespace(tool="mcp_tool_search", params={"query": "mail"})],
                {},
                None,
            )
        assert "Tool search failed" in records[0]["output"]


class TestSkillInjection:
    def test_flag_off_returns_empty(self, env, monkeypatch):
        monkeypatch.setattr(
            "core.hallucination_config.is_skill_injection_enabled", lambda: False
        )
        agent = _agent(env)
        assert agent._retrieve_skill_instructions("task") == ""

    def test_flag_on_returns_skills(self, env, monkeypatch):
        from core import skill_retrieval_service

        @contextlib.contextmanager
        def _cm():
            yield MagicMock()

        monkeypatch.setattr("core.database.get_db_session", _cm)
        monkeypatch.setattr(
            "core.hallucination_config.is_skill_injection_enabled", lambda: True
        )
        skill_retrieval_service.get_skill_retrieval_service = MagicMock(
            return_value=SimpleNamespace(
                retrieve_top_skills=lambda db, tenant, ws, task, limit: "SKILL BLOCK"
            )
        )
        agent = _agent(env)
        assert agent._retrieve_skill_instructions("task") == "SKILL BLOCK"

    def test_exception_returns_empty(self, env, monkeypatch):
        monkeypatch.setattr(
            "core.hallucination_config.is_skill_injection_enabled", lambda: True
        )
        monkeypatch.setattr(
            "core.skill_retrieval_service.get_skill_retrieval_service",
            lambda: SimpleNamespace(retrieve_top_skills=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down"))),
        )
        agent = _agent(env)
        assert agent._retrieve_skill_instructions("task") == ""


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **k):
        return self

    def join(self, *a, **k):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, workspace_row=None, skill_rows=None, raise_on_query=False):
        self._workspace_row = workspace_row
        self._skill_rows = skill_rows or []
        self._raise = raise_on_query

    def query(self, entity):
        from core.models import Skill, Workspace

        if self._raise:
            raise RuntimeError("db down")
        if entity is Workspace:
            return _FakeQuery([self._workspace_row] if self._workspace_row else [])
        if entity is Skill.name:
            return _FakeQuery(list(self._skill_rows))
        raise AssertionError(f"unexpected entity: {entity!r}")


def _patch_workspace_db(monkeypatch, fake_db):
    @contextlib.contextmanager
    def _cm():
        yield fake_db

    monkeypatch.setattr("core.database.get_db_session", _cm)


class TestWorkspaceContext:
    def test_no_workspace_id(self, env, monkeypatch):
        agent = GenericAgent(_agent_model(config={}))
        agent.workspace_id = None
        assert agent._workspace_context_block() == ""

    def test_default_workspace_short_circuit(self, env, monkeypatch):
        _patch_workspace_db(monkeypatch, _FakeDB())
        agent = _agent(env, workspace_id="default")
        assert agent._workspace_context_block() == ""

    def test_missing_workspace_row(self, env, monkeypatch):
        _patch_workspace_db(monkeypatch, _FakeDB())
        agent = _agent(env, workspace_id="ws-1")
        assert agent._workspace_context_block() == ""

    def test_curated_context_list(self, env, monkeypatch):
        _patch_workspace_db(
            monkeypatch,
            _FakeDB(
                workspace_row=SimpleNamespace(
                    metadata_json={"curated_context": ["fact one", "", "fact two"]}
                )
            ),
        )
        agent = _agent(env, workspace_id="ws-1")
        block = agent._workspace_context_block()
        assert "WORKSPACE CURATED CONTEXT" in block
        assert "fact one" in block and "fact two" in block

    def test_curated_context_string(self, env, monkeypatch):
        _patch_workspace_db(
            monkeypatch,
            _FakeDB(workspace_row=SimpleNamespace(metadata_json={"curated_context": "single"})),
        )
        agent = _agent(env, workspace_id="ws-1")
        assert "single" in agent._workspace_context_block()

    def test_assigned_skills(self, env, monkeypatch):
        _patch_workspace_db(
            monkeypatch,
            _FakeDB(
                workspace_row=SimpleNamespace(metadata_json={}),
                skill_rows=[("alpha",), ("zeta",), ("alpha",)],
            ),
        )
        agent = _agent(env, workspace_id="ws-1")
        block = agent._workspace_context_block()
        assert "WORKSPACE-ASSIGNED SKILLS: alpha, zeta" in block

    def test_nothing_configured(self, env, monkeypatch):
        _patch_workspace_db(
            monkeypatch,
            _FakeDB(workspace_row=SimpleNamespace(metadata_json={})),
        )
        agent = _agent(env, workspace_id="ws-1")
        assert agent._workspace_context_block() == ""

    def test_db_error_returns_empty(self, env, monkeypatch):
        _patch_workspace_db(monkeypatch, _FakeDB(raise_on_query=True))
        agent = _agent(env, workspace_id="ws-1")
        assert agent._workspace_context_block() == ""


class TestBudgetCheck:
    @pytest.mark.asyncio
    async def test_allowed(self, env):
        agent = _agent(env)
        env["budget"].check_budget_before_action = AsyncMock(
            return_value={"allowed": True, "reason": "ok"}
        )
        result = await agent._check_budget_before_react()
        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_denied(self, env):
        env["budget"].check_budget_before_action = AsyncMock(
            return_value={"allowed": False, "reason": "over"}
        )
        agent = _agent(env)
        result = await agent._check_budget_before_react()
        assert result["allowed"] is False

    @pytest.mark.asyncio
    async def test_fail_open_on_error(self, env, monkeypatch):
        def _boom(*a, **k):
            raise RuntimeError("budget service down")

        monkeypatch.setattr(
            "core.budget_enforcement_service.BudgetEnforcementService", _boom
        )
        agent = _agent(env)
        result = await agent._check_budget_before_react()
        assert result["allowed"] is True
        assert result["reason"] == "budget-check-error"
