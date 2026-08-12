"""Coverage wave 41 — core/atom_meta_agent.py execute() ReAct loop (TDD, mocked deps).

Drives the main agent surface: workspace validation, execution-record
creation, canvas context + episodic recall, tool assembly (dedup,
mcp_tool_search injection), routing, governed fleet branch (enabled/
force-enforce), planning (Queen + fallback orchestrator), and the full
ReAct loop — final answer, single tool (mcp_tool_search / delegate_task
/ generic governed tool with verification envelope + CRITIQUE), parallel
tools, budget halt, max-steps timeout, no-action conversion, KillRun
abort, body-exception finalization — all LLM/tool calls mocked, zero
spend.
"""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.atom_meta_agent import AtomMetaAgent, ReActStep, ToolCall


def make_exec_agent(**kw):
    with patch("core.atom_meta_agent.WorldModelService",
               return_value=MagicMock()), \
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
        agent = AtomMetaAgent(workspace_id="default")
    agent.llm = MagicMock()
    agent.world_model = MagicMock()
    agent.world_model.recall_experiences = AsyncMock(return_value={})
    agent.mcp = MagicMock()
    agent.mcp.get_all_tools = AsyncMock(return_value=[])
    agent.mcp.search_tools = AsyncMock(return_value=[])
    agent.canvas_provider = MagicMock()
    agent._persist_reasoning_step = MagicMock(return_value="step-1")
    agent._record_execution = AsyncMock()
    agent._check_budget_before_react = AsyncMock(
        return_value={"allowed": True, "reason": "ok"})
    for k, v in kw.items():
        setattr(agent, k, v)
    return agent


def _registry(status="autonomous", category="general"):
    return SimpleNamespace(id="ag-1", status=status, category=category,
                           confidence_score=0.8)


def _session_mock(execution=None):
    db = MagicMock()
    db.__enter__ = MagicMock(return_value=db)
    db.__exit__ = MagicMock(return_value=False)
    db.add = MagicMock()
    db.commit = MagicMock()
    db.close = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = (
        execution or SimpleNamespace(id="ex-1"))
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = (
        execution or SimpleNamespace(id="ex-1"))
    return db


def _workspace_session(workspace=None):
    db = MagicMock()
    db.__enter__ = MagicMock(return_value=db)
    db.__exit__ = MagicMock(return_value=False)
    db.add = MagicMock()
    db.commit = MagicMock()
    db.close = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = (
        workspace or SimpleNamespace(tenant_id="t-1"))
    return db


class _Route:
    def __init__(self, category):
        self.category = SimpleNamespace(value=category)
        self.reasoning = "reasoning"


class TestExecuteFinalAnswer:
    async def test_simple_final_answer(self):
        agent = make_exec_agent()
        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch.object(agent, "_react_step",
                          new=AsyncMock(return_value=ReActStep(
                              thought="thinking", final_answer="All done!"))), \
             patch("ai.nlp_engine.NaturalLanguageEngine") as nlu_cls, \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False):
            nlu_cls.return_value.classify_route = AsyncMock(
                return_value=_Route("chat"))
            result = await agent.execute("hello")
        assert result["final_output"] == "All done!"
        assert result["status"] == "success"
        assert len(result["actions_executed"]) == 1
        agent._record_execution.assert_called_once()

    async def test_single_tool_then_final(self):
        agent = make_exec_agent()
        tool_obs = {"status": "success", "output": "data"}
        agent._execute_tool_with_governance = AsyncMock(return_value=tool_obs)
        react_returns = [
            ReActStep(thought="t1", action=ToolCall(tool="run_tool",
                                                    params={"a": 1})),
            ReActStep(thought="t2", final_answer="Done"),
        ]
        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch.object(agent, "_react_step",
                          new=AsyncMock(side_effect=react_returns)), \
             patch("ai.nlp_engine.NaturalLanguageEngine") as nlu_cls, \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False):
            nlu_cls.return_value.classify_route = AsyncMock(
                return_value=_Route("chat"))
            result = await agent.execute("do something")
        assert result["final_output"] == "Done"
        assert result["status"] == "success"
        assert len(result["actions_executed"]) == 2
        agent._execute_tool_with_governance.assert_called_once()

    async def test_mcp_tool_search_path(self):
        agent = make_exec_agent()
        agent.mcp.search_tools = AsyncMock(return_value=[
            {"name": "new_tool", "description": "d"},
            {"name": "new_tool2", "description": "d2"}])
        react_returns = [
            ReActStep(thought="t1", action=ToolCall(tool="mcp_tool_search",
                                                    params={"query": "x"})),
            ReActStep(thought="t2", final_answer="found tools"),
        ]
        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch.object(agent, "_react_step",
                          new=AsyncMock(side_effect=react_returns)), \
             patch("ai.nlp_engine.NaturalLanguageEngine") as nlu_cls, \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False):
            nlu_cls.return_value.classify_route = AsyncMock(
                return_value=_Route("chat"))
            result = await agent.execute("find a tool")
        assert result["status"] == "success"
        assert len(agent.session_tools) == 2

    async def test_delegate_task_path(self):
        agent = make_exec_agent()
        agent._execute_delegation = AsyncMock(return_value="delegated result")
        react_returns = [
            ReActStep(thought="t1", action=ToolCall(
                tool="delegate_task",
                params={"agent_name": "sales", "task": "do it"})),
            ReActStep(thought="t2", final_answer="Done"),
        ]
        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch.object(agent, "_react_step",
                          new=AsyncMock(side_effect=react_returns)), \
             patch("ai.nlp_engine.NaturalLanguageEngine") as nlu_cls, \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False):
            nlu_cls.return_value.classify_route = AsyncMock(
                return_value=_Route("chat"))
            result = await agent.execute("delegate please")
        assert result["status"] == "success"
        agent._execute_delegation.assert_called_once()

    async def test_parallel_tools_path(self):
        agent = make_exec_agent()
        agent._execute_parallel_tools = AsyncMock(return_value=[
            {"tool_name": "tool_a", "params": {}, "output": "A out",
             "verified_kind": "verified", "verified_evidence": "ev"},
            {"tool_name": "tool_b", "params": {}, "output": "Tool error. failed",
             "verified_kind": "unverified"},
        ])
        react_returns = [
            ReActStep(thought="t1", actions=[
                ToolCall(tool="tool_a", params={}),
                ToolCall(tool="tool_b", params={})]),
            ReActStep(thought="t2", final_answer="parallel done"),
        ]
        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch.object(agent, "_react_step",
                          new=AsyncMock(side_effect=react_returns)), \
             patch("core.hallucination_config.is_parallel_tools_enabled",
                   return_value=True), \
             patch("ai.nlp_engine.NaturalLanguageEngine") as nlu_cls, \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False):
            nlu_cls.return_value.classify_route = AsyncMock(
                return_value=_Route("chat"))
            result = await agent.execute("run both")
        assert result["status"] == "success"
        assert agent._execute_parallel_tools.call_count == 1

    async def test_no_action_converted_to_final(self):
        agent = make_exec_agent()
        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch.object(agent, "_react_step",
                          new=AsyncMock(return_value=ReActStep(
                              thought="just thinking"))), \
             patch("ai.nlp_engine.NaturalLanguageEngine") as nlu_cls, \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False):
            nlu_cls.return_value.classify_route = AsyncMock(
                return_value=_Route("chat"))
            result = await agent.execute("think about it")
        assert result["final_output"] == "just thinking"
        assert result["status"] == "success"

    async def test_budget_halt(self):
        agent = make_exec_agent()
        agent._check_budget_before_react = AsyncMock(
            return_value={"allowed": False, "reason": "over budget",
                          "enforcement_mode": "hard_stop"})
        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch("ai.nlp_engine.NaturalLanguageEngine") as nlu_cls, \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False):
            nlu_cls.return_value.classify_route = AsyncMock(
                return_value=_Route("chat"))
            result = await agent.execute("do it")
        assert result["status"] == "budget_exceeded"
        assert result["failure_reason"] == "over budget"
        assert result["failure_mode"] == "hard_stop"
        assert "Budget limit" in result["final_output"]

    async def test_max_steps_timeout(self):
        agent = make_exec_agent()
        agent._execute_tool_with_governance = AsyncMock(return_value={"ok": True})
        step = ReActStep(thought="t", action=ToolCall(tool="run_tool", params={}))
        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch.object(agent, "_react_step",
                          new=AsyncMock(return_value=step)), \
             patch("ai.nlp_engine.NaturalLanguageEngine") as nlu_cls, \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False):
            nlu_cls.return_value.classify_route = AsyncMock(
                return_value=_Route("chat"))
            result = await agent.execute("loop forever")
        assert result["status"] == "timeout"
        assert "Maximum reasoning steps" in result["final_output"]


class TestExecuteFailures:
    async def test_killrun_aborted(self):
        from core.sandbox_killrun import KillRunAborted
        agent = make_exec_agent()
        agent._record_execution = AsyncMock()
        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch.object(agent, "_react_step",
                          new=AsyncMock(side_effect=KillRunAborted("killed"))), \
             patch("ai.nlp_engine.NaturalLanguageEngine") as nlu_cls, \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False), \
             patch.object(agent, "_record_execution", new=AsyncMock()):
            nlu_cls.return_value.classify_route = AsyncMock(
                return_value=_Route("chat"))
            result = await agent.execute("run")
        assert result["status"] == "killed_sandbox"
        assert "killed by sandbox" in result["final_output"]

    async def test_body_exception_reraises(self):
        agent = make_exec_agent()
        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch.object(agent, "_react_step",
                          new=AsyncMock(side_effect=RuntimeError("boom"))), \
             patch("ai.nlp_engine.NaturalLanguageEngine") as nlu_cls, \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False):
            nlu_cls.return_value.classify_route = AsyncMock(
                return_value=_Route("chat"))
            with pytest.raises(RuntimeError, match="boom"):
                await agent.execute("run")

    async def test_workspace_not_found(self):
        agent = make_exec_agent()
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal", return_value=db), \
             patch("ai.nlp_engine.NaturalLanguageEngine"):
            with pytest.raises(Exception) as exc:
                await agent.execute("run")
        assert exc.value.status_code == 404


class TestExecuteFleetAndCanvas:
    async def test_fleet_force_enforce(self):
        agent = make_exec_agent()
        agent.route_with_governance = AsyncMock(return_value={
            "status": "fleet_recruited", "specialists_count": 2,
            "chain_id": "ch-1"})
        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch("core.fleet_routing_config.fleet_routing_enabled",
                   return_value=True), \
             patch("core.fleet_routing_config.fleet_routing_force_enforce",
                   return_value=True), \
             patch("ai.nlp_engine.NaturalLanguageEngine") as nlu_cls, \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False):
            nlu_cls.return_value.classify_route = AsyncMock(
                return_value=_Route("one_off"))
            result = await agent.execute("x" * 60)
        assert result["status"] == "fleet_recruited"
        assert result["specialists_count"] == 2

    async def test_canvas_context_loaded(self):
        agent = make_exec_agent()
        canvas_state = SimpleNamespace(
            canvas_id="cv-1", artifact_count=2, comments=[
                SimpleNamespace(content="user comment")])
        agent.canvas_provider.get_canvas_context = AsyncMock(
            return_value=canvas_state)
        agent.canvas_provider.format_for_agent = MagicMock(
            return_value="CANVAS TEXT")
        agent.world_model.recall_episodes = AsyncMock(
            return_value=[{"episode_id": "e1"}])
        captured = {}

        async def _react(**kwargs):
            captured["canvas_text"] = kwargs["canvas_text"]
            return ReActStep(thought="t", final_answer="ok")

        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch.object(agent, "_react_step", new=_react), \
             patch("ai.nlp_engine.NaturalLanguageEngine") as nlu_cls, \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False):
            nlu_cls.return_value.classify_route = AsyncMock(
                return_value=_Route("chat"))
            result = await agent.execute(
                "with canvas", canvas_context={"canvas_id": "cv-1"})
        assert result["status"] == "success"
        assert captured["canvas_text"] == "CANVAS TEXT"
        agent.world_model.recall_episodes.assert_called_once()

    async def test_complex_planning_queen_path(self):
        agent = make_exec_agent()
        agent.queen = MagicMock()
        agent.queen.generate_blueprint = AsyncMock(return_value={
            "architecture_name": "Blue", "nodes": [
                {"name": "n1", "type": "action", "capability_required": "x"}],
            "missing_capabilities": []})
        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch.object(agent, "_react_step",
                          new=AsyncMock(return_value=ReActStep(
                              thought="t", final_answer="planned"))), \
             patch("ai.nlp_engine.NaturalLanguageEngine") as nlu_cls, \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False):
            nlu_cls.return_value.classify_route = AsyncMock(
                return_value=_Route("automation"))
            result = await agent.execute(
                "Create a comprehensive monthly report for the board including all divisions")
        assert result["status"] == "success"
        agent.queen.generate_blueprint.assert_called_once()

    async def test_queen_failure_falls_back_to_orchestrator(self):
        agent = make_exec_agent()
        agent.queen = MagicMock()
        agent.queen.generate_blueprint = AsyncMock(
            side_effect=RuntimeError("queen down"))
        agent.orchestrator.generate_dynamic_workflow = AsyncMock(
            return_value={"nodes": [{"name": "n1", "type": "action"}]})
        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch.object(agent, "_react_step",
                          new=AsyncMock(return_value=ReActStep(
                              thought="t", final_answer="planned"))), \
             patch("ai.nlp_engine.NaturalLanguageEngine") as nlu_cls, \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False):
            nlu_cls.return_value.classify_route = AsyncMock(
                return_value=_Route("automation"))
            result = await agent.execute(
                "Create a comprehensive monthly report for the board including all divisions")
        assert result["status"] == "success"
        agent.orchestrator.generate_dynamic_workflow.assert_called_once()
