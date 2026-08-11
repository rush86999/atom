"""Coverage wave 44b — core/atom_meta_agent.py execute() ReAct loop (TDD).

Drives the full execute() flow with a mocked ReAct loop:
- happy path: model returns final_answer on step 1 → success
- tool-execution path: model returns a tool action → observation → next step
  final answer (covers _execute_tool_with_governance integration + persistence)
- mcp_tool_search special handling in-loop
- max-steps exceeded → timeout status
- budget-exceeded → budget_exceeded status + FAILED persistence
- no-action-no-answer → thought-as-final
- body exception → failed finalization
- KillRunAborted → killed_sandbox
- parallel tools in-loop
"""
import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.atom_meta_agent import (
    AgentTriggerMode,
    AtomMetaAgent,
    ReActStep,
    ToolCall,
)


def make_agent(**kw):
    with patch("core.atom_meta_agent.WorldModelService", return_value=MagicMock()), \
         patch("core.atom_meta_agent.AdvancedWorkflowOrchestrator",
               return_value=MagicMock()), \
         patch("core.atom_meta_agent.CapabilityGraduationService",
               return_value=MagicMock()), \
         patch("core.atom_meta_agent.SessionLocal",
               return_value=MagicMock()), \
         patch("core.service_factory.ServiceFactory.get_llm_service",
               return_value=MagicMock()), \
         patch("core.atom_meta_agent.get_canvas_provider",
               return_value=MagicMock()):
        agent = AtomMetaAgent(
            workspace_id=kw.pop("workspace_id", "default"),
            tenant_id=kw.pop("tenant_id", None),
            user=kw.pop("user", None))
    agent.llm = MagicMock()
    agent.world_model = MagicMock()
    agent.graduation_service = MagicMock()
    for k, v in kw.items():
        setattr(agent, k, v)
    return agent


def _env(agent, steps, budget_allowed=True, workspace=True):
    """Wire the execute() dependencies: react steps, budget, persistence."""
    agent._react_step = AsyncMock(side_effect=steps)
    agent._check_budget_before_react = AsyncMock(
        return_value={"allowed": budget_allowed, "reason": "ok",
                      "enforcement_mode": "soft_stop"})
    agent._record_execution = AsyncMock()
    agent._persist_reasoning_step = MagicMock(return_value="rs-1")
    agent.world_model.recall_experiences = AsyncMock(return_value={})
    agent.mcp = MagicMock()
    agent.mcp.get_all_tools = AsyncMock(return_value=[])
    agent.mcp.call_tool = AsyncMock(return_value="tool-observation")
    # The governance tool path is covered in depth by W44 — stub it here so
    # the execute-loop tests stay hermetic (no real DB/governance service).
    agent._execute_tool_with_governance = AsyncMock(
        return_value="tool-observation")

    db = MagicMock()
    if workspace:
        ws = MagicMock()
        ws.tenant_id = "t-1"
        db.query.return_value.filter.return_value.first.return_value = ws
    else:
        db.query.return_value.filter.return_value.first.return_value = None
    return agent, db


async def _run(agent, db, *args, **kwargs):
    """execute() with the workspace-mock SessionLocal patched."""
    with patch("core.atom_meta_agent.SessionLocal") as mock_session:
        mock_session.return_value.__enter__.return_value = db
        return await agent.execute(*args, **kwargs)


class TestExecuteHappyPath:
    async def test_final_answer_step_one(self):
        agent = make_agent()
        agent._get_atom_registry = MagicMock()
        agent._get_atom_registry.return_value.status = "autonomous"
        agent, db = _env(agent, [ReActStep(thought="direct", final_answer="Hello!")])
        result = await _run(agent, db, "hello", {}, execution_id="ex-1")
        assert result["status"] == "success"
        assert result["final_output"] == "Hello!"
        agent._record_execution.assert_awaited_once()

    async def test_tool_then_final_answer(self):
        agent = make_agent()
        agent, db = _env(agent, [
            ReActStep(thought="need tool",
                      action=ToolCall(tool="search_documents", params={"q": "x"})),
            ReActStep(thought="got it", final_answer="Found it"),
        ])
        result = await _run(agent, db, "find docs", {}, execution_id="ex-2")
        assert result["status"] == "success"
        assert "Found it" in result["final_output"]
        # tool was executed via the governance path (context is mutated by execute)
        assert agent._execute_tool_with_governance.await_count == 1
        call = agent._execute_tool_with_governance.await_args
        assert call.args[0] == "search_documents"
        assert call.args[1] == {"q": "x"}

    async def test_no_action_no_answer_uses_thought(self):
        agent = make_agent()
        agent, db = _env(agent, [ReActStep(thought="I can't proceed")])
        result = await _run(agent, db, "vague", {}, execution_id="ex-3")
        assert result["status"] == "success"
        assert result["final_output"] == "I can't proceed"

    async def test_max_steps_exceeded(self):
        agent = make_agent()
        # Always emit an action that returns an observation → never final
        agent, db = _env(agent, [
            ReActStep(thought=f"step {i}",
                      action=ToolCall(tool="search_documents", params={}))
            for i in range(12)
        ])
        result = await _run(agent, db, "loop forever", {}, execution_id="ex-4")
        assert result["status"] == "timeout"
        assert "Maximum reasoning steps" in result["final_output"]


class TestExecuteSpecialPaths:
    async def test_budget_exceeded_halts(self):
        agent = make_agent()
        agent, db = _env(agent, [], budget_allowed=False)
        result = await _run(agent, db, "expensive", {}, execution_id="ex-5")
        assert result["status"] == "budget_exceeded"
        assert "Budget limit" in result["final_output"]
        assert result["failure_mode"] == "soft_stop"

    async def test_mcp_tool_search_in_loop(self):
        agent = make_agent()
        agent, db = _env(agent, [
            ReActStep(thought="search",
                      action=ToolCall(tool="mcp_tool_search", params={"query": "q"})),
            ReActStep(thought="done", final_answer="ok"),
        ])
        agent.mcp.search_tools = AsyncMock(
            return_value=[{"name": "new_tool", "description": "d"}])
        agent.session_tools = []
        result = await _run(agent, db, "find tools", {}, execution_id="ex-6")
        assert result["status"] == "success"
        assert any(t["name"] == "new_tool" for t in agent.session_tools)

    async def test_parallel_actions_in_loop(self):
        agent = make_agent()
        agent, db = _env(agent, [
            ReActStep(thought="parallel",
                      actions=[ToolCall(tool="a", params={}),
                               ToolCall(tool="b", params={})]),
            ReActStep(thought="done", final_answer="all done"),
        ])
        agent._execute_parallel_tools = AsyncMock(return_value=[
            {"tool_name": "a", "params": {}, "output": "a-ok",
             "verified_kind": "unverified", "verified_evidence": None},
            {"tool_name": "b", "params": {}, "output": "b-ok",
             "verified_kind": "unverified", "verified_evidence": None},
        ])
        with patch("core.hallucination_config.is_parallel_tools_enabled",
                   return_value=True), \
             patch("core.hallucination_config.get_max_parallel_tools",
                   return_value=4):
            result = await _run(agent, db, "run both", {}, execution_id="ex-7")
        assert result["status"] == "success"
        assert any("parallel" in str(s.get("step_type", "")) for s in result["actions_executed"])


class TestExecuteFailures:
    async def test_body_exception_finalizes_failed(self):
        agent = make_agent()
        agent, db = _env(agent, [])
        agent.world_model.recall_experiences = AsyncMock(
            side_effect=RuntimeError("world model down"))
        agent._record_execution = AsyncMock()
        with patch("core.atom_meta_agent.SessionLocal") as mock_session:
            mock_session.return_value.__enter__.return_value = db
            with pytest.raises(RuntimeError, match="world model down"):
                await agent.execute("boom", {}, execution_id="ex-8")

    async def test_killrun_aborted_returns_killed(self):
        from core.sandbox_killrun import KillRunAborted
        agent = make_agent()
        agent, db = _env(agent, [])
        agent.world_model.recall_experiences = AsyncMock(
            side_effect=KillRunAborted("tripwire"))
        agent._record_execution = AsyncMock()
        with patch("core.atom_meta_agent.SessionLocal") as mock_session:
            mock_session.return_value.__enter__.return_value = db
            result = await agent.execute("kill", {}, execution_id="ex-9")
        assert result["status"] == "killed_sandbox"
        assert "killed" in result["final_output"]

    async def test_workspace_not_found_raises_404(self):
        from fastapi import HTTPException
        agent = make_agent()
        agent, db = _env(agent, [], workspace=False)
        with patch("core.atom_meta_agent.SessionLocal") as mock_session:
            mock_session.return_value.__enter__.return_value = db
            with pytest.raises(HTTPException) as exc:
                await agent.execute("x", {}, execution_id="ex-10")
        assert exc.value.status_code == 404

    async def test_execution_record_creation_failure_logged(self):
        agent = make_agent()
        agent.world_model.recall_experiences = AsyncMock(return_value={})
        agent._react_step = AsyncMock(
            return_value=ReActStep(thought="t", final_answer="done"))
        agent._check_budget_before_react = AsyncMock(
            return_value={"allowed": True, "reason": "ok"})
        agent._record_execution = AsyncMock()
        agent._persist_reasoning_step = MagicMock(return_value="rs-1")
        db = MagicMock()
        ws = MagicMock()
        ws.tenant_id = "t-1"
        db.query.return_value.filter.return_value.first.return_value = ws
        db.add.side_effect = RuntimeError("db add boom")
        with patch("core.atom_meta_agent.SessionLocal") as mock_session:
            mock_session.return_value.__enter__.return_value = db
            result = await agent.execute("x", {}, execution_id="ex-11")
        assert result["status"] == "success"
