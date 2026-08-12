"""Coverage wave 41b — core/atom_meta_agent.py tool/approval/spawn paths (TDD).

Closes the remaining blocks: _execute_parallel_tools (disabled
sequential, blocked batch, rejected approvals, gather exceptions incl.
KillRun re-raise, serial mcp_tool_search + failure), HITL wait
(single + all-or-nothing approve/reject/timeout), spawn_agent
(template/custom/unknown/persist + ephemeral), query_memory scopes,
mentorship guidance (with/without interim supervisor), and the
registry accessor — zero LLM (mocked), zero spend.
"""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.atom_meta_agent import AtomMetaAgent, ToolCall


def make_tool_agent(**kw):
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
    agent.mcp = MagicMock()
    agent.mcp.search_tools = AsyncMock(return_value=[])
    agent.world_model = MagicMock()
    agent.graduation_service = MagicMock()
    for k, v in kw.items():
        setattr(agent, k, v)
    return agent


class TestParallelTools:
    async def test_disabled_falls_back_sequential(self):
        agent = make_tool_agent()
        agent._execute_tool_with_governance = AsyncMock(
            return_value={"ok": True})
        with patch("core.hallucination_config.is_parallel_tools_enabled",
                   return_value=False), \
             patch("core.hallucination_config.get_max_parallel_tools",
                   return_value=2):
            records = await agent._execute_parallel_tools(
                [ToolCall(tool="a", params={}), ToolCall(tool="b", params={})],
                {}, None)
        assert len(records) == 2
        assert agent._execute_tool_with_governance.call_count == 2

    async def test_blocked_batch(self):
        agent = make_tool_agent()
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(
            return_value={"allowed": False, "action_complexity": 1,
                          "reason": "denied"})
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        with patch("core.hallucination_config.is_parallel_tools_enabled",
                   return_value=True), \
             patch("core.hallucination_config.get_max_parallel_tools",
                   return_value=4), \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal", return_value=db):
            records = await agent._execute_parallel_tools(
                [ToolCall(tool="danger", params={})], {}, None)
        assert records[0]["verified_kind"] == "blocked"
        assert "Governance blocked" in records[0]["output"]

    async def test_rejected_approval(self):
        agent = make_tool_agent()
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(
            return_value={"allowed": True, "action_complexity": 3})
        gov.request_approval.return_value = "act-1"
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        with patch("core.hallucination_config.is_parallel_tools_enabled",
                   return_value=True), \
             patch("core.hallucination_config.get_max_parallel_tools",
                   return_value=4), \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal", return_value=db), \
             patch.object(agent, "_wait_for_all_approvals",
                          new=AsyncMock(return_value=False)):
            records = await agent._execute_parallel_tools(
                [ToolCall(tool="heavy", params={})], {}, None)
        assert records[0]["verified_kind"] == "rejected"
        assert "REJECTED" in records[0]["output"]

    async def test_approved_batch_executes(self):
        agent = make_tool_agent()
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(
            return_value={"allowed": True, "action_complexity": 1})
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        agent._execute_tool_with_governance = AsyncMock(
            return_value={"status": "success", "output": "x"})
        with patch("core.hallucination_config.is_parallel_tools_enabled",
                   return_value=True), \
             patch("core.hallucination_config.get_max_parallel_tools",
                   return_value=4), \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal", return_value=db):
            records = await agent._execute_parallel_tools(
                [ToolCall(tool="a", params={}), ToolCall(tool="b", params={})],
                {}, None)
        assert len(records) == 2
        assert agent._execute_tool_with_governance.call_count == 2
        for call in agent._execute_tool_with_governance.call_args_list:
            assert call.kwargs["pre_approved"] is True

    async def test_gather_exception_tolerated(self):
        agent = make_tool_agent()
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(
            return_value={"allowed": True, "action_complexity": 1})
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        agent._execute_tool_with_governance = AsyncMock(
            side_effect=RuntimeError("tool boom"))
        with patch("core.hallucination_config.is_parallel_tools_enabled",
                   return_value=True), \
             patch("core.hallucination_config.get_max_parallel_tools",
                   return_value=4), \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal", return_value=db):
            records = await agent._execute_parallel_tools(
                [ToolCall(tool="a", params={})], {}, None)
        assert records[0]["verified_kind"] == "error"
        assert "Tool error for a" in records[0]["output"]

    async def test_gather_killrun_reraises(self):
        from core.sandbox_killrun import KillRunAborted
        agent = make_tool_agent()
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(
            return_value={"allowed": True, "action_complexity": 1})
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        agent._execute_tool_with_governance = AsyncMock(
            side_effect=KillRunAborted("killed"))
        with patch("core.hallucination_config.is_parallel_tools_enabled",
                   return_value=True), \
             patch("core.hallucination_config.get_max_parallel_tools",
                   return_value=4), \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal", return_value=db):
            with pytest.raises(KillRunAborted):
                await agent._execute_parallel_tools(
                    [ToolCall(tool="a", params={})], {}, None)

    async def test_serial_mcp_tool_search(self):
        agent = make_tool_agent()
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(
            return_value={"allowed": True, "action_complexity": 1})
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        agent.mcp.search_tools = AsyncMock(return_value=[
            {"name": "n1", "description": "d"}])
        with patch("core.hallucination_config.is_parallel_tools_enabled",
                   return_value=True), \
             patch("core.hallucination_config.get_max_parallel_tools",
                   return_value=4), \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal", return_value=db):
            records = await agent._execute_parallel_tools(
                [ToolCall(tool="mcp_tool_search", params={"query": "q"})],
                {}, None)
        assert len(records) == 1
        assert "Found 1 new tools" in records[0]["output"]
        assert len(agent.session_tools) == 1

    async def test_serial_search_failure(self):
        agent = make_tool_agent()
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(
            return_value={"allowed": True, "action_complexity": 1})
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        agent.mcp.search_tools = AsyncMock(side_effect=RuntimeError("search down"))
        with patch("core.hallucination_config.is_parallel_tools_enabled",
                   return_value=True), \
             patch("core.hallucination_config.get_max_parallel_tools",
                   return_value=4), \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal", return_value=db):
            records = await agent._execute_parallel_tools(
                [ToolCall(tool="mcp_tool_search", params={"query": "q"})],
                {}, None)
        assert "Tool search failed" in records[0]["output"]


class TestHITLWaits:
    async def test_wait_approval_approved(self):
        agent = make_tool_agent()
        gov = MagicMock()
        gov.get_approval_status.return_value = {"status": "approved"}
        db = MagicMock()
        db.close = MagicMock()
        with patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal", return_value=db):
            assert await agent._wait_for_approval("act-1") is True

    async def test_wait_approval_rejected(self):
        agent = make_tool_agent()
        gov = MagicMock()
        gov.get_approval_status.return_value = {"status": "rejected"}
        db = MagicMock()
        db.close = MagicMock()
        with patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal", return_value=db):
            assert await agent._wait_for_approval("act-1") is False

    async def test_wait_approval_timeout(self):
        agent = make_tool_agent()
        gov = MagicMock()
        gov.get_approval_status.return_value = {"status": "pending"}
        db = MagicMock()
        db.close = MagicMock()

        async def _no_sleep(*a, **k):
            pass

        with patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal", return_value=db), \
             patch("core.atom_meta_agent.asyncio.sleep", new=_no_sleep):
            assert await agent._wait_for_approval("act-1") is False

    async def test_wait_all_approved(self):
        agent = make_tool_agent()
        gov = MagicMock()
        gov.get_approval_status.return_value = {"status": "approved"}
        db = MagicMock()
        db.close = MagicMock()
        with patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal", return_value=db):
            assert await agent._wait_for_all_approvals(["a1", "a2"]) is True

    async def test_wait_all_rejected(self):
        agent = make_tool_agent()
        gov = MagicMock()
        gov.get_approval_status.return_value = {"status": "rejected"}
        db = MagicMock()
        db.close = MagicMock()
        with patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal", return_value=db):
            assert await agent._wait_for_all_approvals(["a1"]) is False

    async def test_wait_all_pending_then_approved(self):
        agent = make_tool_agent()
        gov = MagicMock()
        statuses = iter([{"status": "pending"}, {"status": "approved"}])
        gov.get_approval_status.side_effect = lambda aid: next(statuses)
        db = MagicMock()
        db.close = MagicMock()

        async def _no_sleep(*a, **k):
            pass

        with patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal", return_value=db), \
             patch("core.atom_meta_agent.asyncio.sleep", new=_no_sleep):
            assert await agent._wait_for_all_approvals(["a1"]) is True


class TestSpawnAgent:
    async def test_unknown_template(self):
        agent = make_tool_agent()
        with pytest.raises(ValueError, match="Unknown agent template"):
            await agent.spawn_agent("ghost")

    async def test_template_spawn_ephemeral(self):
        agent = make_tool_agent()
        with patch("core.atom_meta_agent.AgentRegistry",
                   lambda **kw: SimpleNamespace(**kw)), \
             patch("core.atom_meta_agent.SessionLocal") as sl:
            sl.return_value.__enter__.return_value = MagicMock()
            result = await agent.spawn_agent("finance_analyst")
        assert result.id.startswith("spawned_finance_analyst_")
        assert result.status == "student"
        assert len(agent.spawned_agents) == 1

    async def test_custom_spawn_persist(self):
        agent = make_tool_agent()
        registered = SimpleNamespace(id="reg-1")
        gov = MagicMock()
        gov.register_or_update_agent.return_value = registered
        with patch("core.atom_meta_agent.AgentRegistry",
                   lambda **kw: SimpleNamespace(**kw)), \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov):
            result = await agent.spawn_agent(
                "custom",
                {"name": "Custom", "category": "Ops",
                 "description": "d", "default_params": {"x": 1}},
                persist=True, db=MagicMock())
        assert result.id == "reg-1"

    async def test_template_spawn_persist_no_db(self):
        agent = make_tool_agent()
        registered = SimpleNamespace(id="reg-2")
        gov = MagicMock()
        gov.register_or_update_agent.return_value = registered
        with patch("core.atom_meta_agent.AgentRegistry",
                   lambda **kw: SimpleNamespace(**kw)), \
             patch("core.atom_meta_agent.SessionLocal") as sl, \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov):
            sl.return_value.__enter__.return_value = MagicMock()
            result = await agent.spawn_agent("sales_assistant", persist=True)
        assert result.id == "reg-2"


class TestQueryMemoryAndMentorship:
    async def test_query_memory_scopes(self):
        agent = make_tool_agent()
        agent.world_model.recall_experiences = AsyncMock(
            return_value={"experiences": [1], "knowledge": [2]})
        with patch.object(agent, "_get_atom_registry"):
            assert (await agent.query_memory("q", "experiences"))["experiences"] == [1]
            assert (await agent.query_memory("q", "knowledge"))["knowledge"] == [2]
            assert (await agent.query_memory("q", "all"))["experiences"] == [1]

    async def test_mentorship_with_supervisor(self):
        agent = make_tool_agent()
        agent.llm.generate_response = AsyncMock(return_value="good guidance")
        student = SimpleNamespace(category="Finance")
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        db.query.return_value.filter.return_value.first.return_value = student
        db.query.return_value.filter.return_value.filter.return_value.count.return_value = 1
        with patch("core.atom_meta_agent.SessionLocal", return_value=db):
            guidance = await agent.generate_mentorship_guidance(
                "student-1", "run_tool", {"a": 1}, "blocked")
        assert guidance == "good guidance"

    async def test_mentorship_interim_supervisor(self):
        agent = make_tool_agent()
        agent.llm.generate_response = AsyncMock(return_value="mentor mode")
        student = SimpleNamespace(category="Finance")
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        db.query.return_value.filter.return_value.first.return_value = student
        db.query.return_value.filter.return_value.count.return_value = 0
        with patch("core.atom_meta_agent.SessionLocal", return_value=db):
            guidance = await agent.generate_mentorship_guidance(
                "student-1", "run_tool", {}, "blocked")
        assert guidance == "mentor mode"
        system = agent.llm.generate_response.call_args.kwargs["system_instruction"]
        assert "Interim Supervisor" in system

    async def test_mentorship_no_student(self):
        agent = make_tool_agent()
        agent.llm.generate_response = AsyncMock(return_value="g")
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.count.return_value = 0
        with patch("core.atom_meta_agent.SessionLocal", return_value=db):
            guidance = await agent.generate_mentorship_guidance(
                "ghost", "run_tool", {}, "blocked")
        assert guidance == "g"

    async def test_mentorship_fallback(self):
        agent = make_tool_agent()
        agent.llm.generate_response = AsyncMock(return_value=None)
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.count.return_value = 0
        with patch("core.atom_meta_agent.SessionLocal", return_value=db):
            guidance = await agent.generate_mentorship_guidance(
                "ghost", "run_tool", {}, "blocked")
        assert "unable to provide guidance" in guidance

    def test_get_atom_registry(self):
        agent = make_tool_agent()
        registry = agent._get_atom_registry()
        assert registry.id == "atom_main"
        assert registry.category == "Meta"
        assert registry.status == "autonomous"
