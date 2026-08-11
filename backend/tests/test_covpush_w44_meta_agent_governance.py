"""Coverage wave 44 — core/atom_meta_agent.py governance tool path + parallel tools (TDD).

Picks up from W30 (53%). Targets:
- _execute_tool_with_governance: allowed/blocked/HITL approval granted+rejected,
  special tools (trigger_workflow/delegate_task/recruit_fleet/invoke_capability
  student+success+exception), sandbox requires-review enforced+shadow,
  ActionJudge BLOCK/ESCALATE/disabled, mcp call success, KillRunAborted
  re-raise, generic error → "Tool error"
- _wait_for_approval: approved/rejected/timeout
- _wait_for_all_approvals: all-granted/one-rejected
- _execute_parallel_tools: batch execution + pre-approved governance
- _recruit_fleet branches
- generate_mentorship_guidance
"""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.atom_meta_agent import AtomMetaAgent


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


def _gov(**kw):
    """Governance service mock."""
    gov = MagicMock()
    defaults = {
        "can_perform_action_async": AsyncMock(
            return_value={"allowed": True, "action_complexity": 1, "reason": "ok"}),
        "request_approval": MagicMock(return_value="action-1"),
    }
    defaults.update(kw)
    for k, v in defaults.items():
        setattr(gov, k, v)
    return gov


class TestExecuteToolWithGovernance:
    async def test_allowed_simple_tool(self):
        agent = make_agent()
        agent.mcp = MagicMock()
        agent.mcp.call_tool = AsyncMock(return_value="result-ok")
        gov = _gov()
        with patch("core.atom_meta_agent.SessionLocal") as mock_session, \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov):
            mock_session.return_value.__enter__.return_value = MagicMock()
            result = await agent._execute_tool_with_governance(
                "search_documents", {}, {}, None)
        assert "result-ok" in result
        agent.mcp.call_tool.assert_awaited_once()

    async def test_governance_blocked(self):
        agent = make_agent()
        gov = _gov(can_perform_action_async=AsyncMock(
            return_value={"allowed": False, "action_complexity": 1,
                          "reason": "not allowed"}))
        with patch("core.atom_meta_agent.SessionLocal") as mock_session, \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov):
            mock_session.return_value.__enter__.return_value = MagicMock()
            result = await agent._execute_tool_with_governance(
                "delete_data", {}, {}, None)
        assert "Governance blocked" in result

    async def test_hitl_approval_granted(self):
        agent = make_agent()
        gov = _gov(can_perform_action_async=AsyncMock(
            return_value={"allowed": True, "action_complexity": 3,
                          "requires_human_approval": True,
                          "reason": "complex action"}))
        agent.mcp = MagicMock()
        agent.mcp.call_tool = AsyncMock(return_value="done")
        with patch("core.atom_meta_agent.SessionLocal") as mock_session, \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch.object(agent, "_wait_for_approval",
                          new=AsyncMock(return_value=True)):
            mock_session.return_value.__enter__.return_value = MagicMock()
            result = await agent._execute_tool_with_governance(
                "create_record", {"a": 1}, {}, None)
        assert "done" in result
        gov.request_approval.assert_called_once()

    async def test_hitl_approval_rejected(self):
        agent = make_agent()
        gov = _gov(can_perform_action_async=AsyncMock(
            return_value={"allowed": True, "action_complexity": 3,
                          "requires_human_approval": True,
                          "reason": "complex"}))
        with patch("core.atom_meta_agent.SessionLocal") as mock_session, \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch.object(agent, "_wait_for_approval",
                          new=AsyncMock(return_value=False)):
            mock_session.return_value.__enter__.return_value = MagicMock()
            result = await agent._execute_tool_with_governance(
                "create_record", {}, {}, None)
        assert "REJECTED" in result

    async def test_trigger_workflow_special_tool(self):
        agent = make_agent()
        with patch("core.workflow_engine.get_workflow_engine") as mock_get:
            engine = MagicMock()
            engine.start_workflow = AsyncMock(return_value="exec-1")
            mock_get.return_value = engine
            result = await agent._execute_tool_with_governance(
                "trigger_workflow", {"workflow_id": "wf-1", "params": {"x": 1}},
                {}, None, pre_approved=True)
        assert "wf-1" in result
        assert "exec-1" in result

    async def test_trigger_workflow_missing_id(self):
        agent = make_agent()
        result = await agent._trigger_workflow(None, {}, {})
        assert "workflow_id is required" in result

    async def test_trigger_workflow_error(self):
        agent = make_agent()
        with patch("core.workflow_engine.get_workflow_engine",
                   side_effect=RuntimeError("engine down")):
            result = await agent._trigger_workflow("wf-1", {}, {})
        assert "Error triggering workflow" in result

    async def test_delegate_task_special_tool(self):
        agent = make_agent()
        with patch.object(agent, "_execute_delegation",
                          new=AsyncMock(return_value="delegated")):
            result = await agent._execute_tool_with_governance(
                "delegate_task", {"agent_name": "sales", "task": "x"},
                {}, None, pre_approved=True)
        assert "delegated" in result

    async def test_recruit_fleet_special_tool(self):
        agent = make_agent()
        with patch.object(agent, "_recruit_fleet",
                          new=AsyncMock(return_value="fleet-ready")):
            result = await agent._execute_tool_with_governance(
                "recruit_fleet", {"goal": "g", "sub_tasks": []},
                {}, None, pre_approved=True)
        assert "fleet-ready" in result

    async def test_invoke_capability_student_blocked(self):
        agent = make_agent()
        agent.graduation_service.get_maturity = MagicMock(return_value="student")
        result = await agent._execute_tool_with_governance(
            "invoke_capability", {"capability_name": "c1", "params": {}},
            {}, None, pre_approved=True)
        assert "STUDENT" in result

    async def test_invoke_capability_success(self):
        agent = make_agent()
        agent.graduation_service.get_maturity = MagicMock(return_value="autonomous")
        agent.mcp = MagicMock()
        agent.mcp.call_tool = AsyncMock(return_value={"success": True, "result": "cap-done"})
        result = await agent._execute_tool_with_governance(
            "invoke_capability", {"capability_name": "c2", "params": {}},
            {}, None, pre_approved=True)
        assert "cap-done" in result
        agent.graduation_service.record_usage.assert_called_once()

    async def test_invoke_capability_usage_exception(self):
        agent = make_agent()
        agent.graduation_service.get_maturity = MagicMock(return_value="autonomous")
        calls = {"n": 0}

        def _record_usage(*a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boom")
            return None

        agent.graduation_service.record_usage = MagicMock(side_effect=_record_usage)
        agent.mcp = MagicMock()
        agent.mcp.call_tool = AsyncMock(return_value={"success": True, "result": "x"})
        result = await agent._execute_tool_with_governance(
            "invoke_capability", {"capability_name": "c3", "params": {}},
            {}, None, pre_approved=True)
        assert "x" in result  # usage bookkeeping failure falls back, turn survives
        assert calls["n"] == 2

    async def test_sandbox_enforced_blocks(self):
        agent = make_agent()
        decision = SimpleNamespace(
            requires_review=True, enforced=True,
            decision="BLOCKED", violation_detail="fs escape",
            violation_type="VT_PROVENANCE")
        with patch("core.atom_meta_agent._meta_agent_sandbox_check",
                   return_value=decision):
            result = await agent._execute_tool_with_governance(
                "read_file", {"path": "/etc/passwd"}, {}, None, pre_approved=True)
        assert "Sandbox BLOCKED" in result

    async def test_sandbox_shadow_proceeds(self):
        agent = make_agent()
        agent.mcp = MagicMock()
        agent.mcp.call_tool = AsyncMock(return_value="shadow-ok")
        decision = SimpleNamespace(
            requires_review=True, enforced=False,
            decision="REVIEW", violation_detail="d",
            violation_type="VT_FS")
        with patch("core.atom_meta_agent._meta_agent_sandbox_check",
                   return_value=decision):
            result = await agent._execute_tool_with_governance(
                "read_file", {"path": "/x"}, {}, None, pre_approved=True)
        assert "shadow-ok" in result

    async def test_action_judge_block(self):
        from core.llm.action_judge import JudgeVerdict
        agent = make_agent()
        judge_result = SimpleNamespace(verdict=JudgeVerdict.BLOCK, rationale="unsafe")
        with patch("core.sandbox_config.is_sandbox_judge_enabled",
                   return_value=True), \
             patch("core.llm.action_judge.ActionJudge") as mock_judge_cls:
            mock_judge = MagicMock()
            mock_judge.evaluate = AsyncMock(return_value=judge_result)
            mock_judge_cls.return_value = mock_judge
            result = await agent._execute_tool_with_governance(
                "create_record", {}, {}, None, pre_approved=True)
        assert "safety judge" in result

    async def test_action_judge_escalate_approved(self):
        from core.llm.action_judge import JudgeVerdict
        agent = make_agent()
        judge_result = SimpleNamespace(verdict=JudgeVerdict.ESCALATE, rationale="review")
        agent.mcp = MagicMock()
        agent.mcp.call_tool = AsyncMock(return_value="escalated-ok")
        with patch("core.sandbox_config.is_sandbox_judge_enabled",
                   return_value=True), \
             patch("core.llm.action_judge.ActionJudge") as mock_judge_cls, \
             patch("core.atom_meta_agent.SessionLocal") as mock_session, \
             patch("core.atom_meta_agent.AgentGovernanceService") as mock_gov_cls, \
             patch.object(agent, "_wait_for_approval",
                          new=AsyncMock(return_value=True)):
            mock_judge = MagicMock()
            mock_judge.evaluate = AsyncMock(return_value=judge_result)
            mock_judge_cls.return_value = mock_judge
            gov = MagicMock()
            gov.request_approval = MagicMock(return_value="a-9")
            mock_gov_cls.return_value = gov
            mock_session.return_value.__enter__.return_value = MagicMock()
            result = await agent._execute_tool_with_governance(
                "create_record", {}, {}, None, pre_approved=True)
        assert "escalated-ok" in result

    async def test_killrun_aborted_reraises(self):
        from core.sandbox_killrun import KillRunAborted
        agent = make_agent()
        agent.mcp = MagicMock()
        agent.mcp.call_tool = AsyncMock(side_effect=KillRunAborted("killed"))
        with pytest.raises(KillRunAborted):
            await agent._execute_tool_with_governance(
                "read_file", {}, {}, None, pre_approved=True)

    async def test_generic_error_returns_tool_error(self):
        agent = make_agent()
        agent.mcp = MagicMock()
        agent.mcp.call_tool = AsyncMock(side_effect=RuntimeError("mcp down"))
        result = await agent._execute_tool_with_governance(
            "read_file", {}, {}, None, pre_approved=True)
        assert "Tool error" in result


class TestApprovalWait:
    def _gov_status(self, status):
        gov = MagicMock()
        gov.get_approval_status = MagicMock(
            return_value={"status": status, "action_id": "a-1"})
        return gov

    async def test_wait_for_approval_approved(self):
        agent = make_agent()
        with patch("core.atom_meta_agent.SessionLocal") as mock_session, \
             patch("core.atom_meta_agent.AgentGovernanceService") as mock_gov_cls:
            mock_gov_cls.return_value = self._gov_status("approved")
            mock_session.return_value.__enter__.return_value = MagicMock()
            assert await agent._wait_for_approval("a-1") is True

    async def test_wait_for_approval_rejected(self):
        agent = make_agent()
        with patch("core.atom_meta_agent.SessionLocal") as mock_session, \
             patch("core.atom_meta_agent.AgentGovernanceService") as mock_gov_cls:
            mock_gov_cls.return_value = self._gov_status("rejected")
            mock_session.return_value.__enter__.return_value = MagicMock()
            assert await agent._wait_for_approval("a-1") is False

    async def test_wait_for_approval_timeout(self):
        agent = make_agent()
        with patch("core.atom_meta_agent.SessionLocal") as mock_session, \
             patch("core.atom_meta_agent.AgentGovernanceService") as mock_gov_cls:
            mock_gov_cls.return_value = self._gov_status("pending")
            mock_session.return_value.__enter__.return_value = MagicMock()
            with patch("asyncio.sleep", new=AsyncMock()):
                assert await agent._wait_for_approval("a-1") is False

    async def test_wait_for_all_approvals_all_granted(self):
        agent = make_agent()
        with patch("core.atom_meta_agent.SessionLocal") as mock_session, \
             patch("core.atom_meta_agent.AgentGovernanceService") as mock_gov_cls:
            mock_gov_cls.return_value = self._gov_status("approved")
            mock_session.return_value.__enter__.return_value = MagicMock()
            assert await agent._wait_for_all_approvals(["a-1", "a-2"]) is True

    async def test_wait_for_all_approvals_one_rejected(self):
        agent = make_agent()

        def _status(action_id):
            if action_id == "a-2":
                return {"status": "rejected", "action_id": action_id}
            return {"status": "pending", "action_id": action_id}

        gov = MagicMock()
        gov.get_approval_status = MagicMock(side_effect=_status)
        with patch("core.atom_meta_agent.SessionLocal") as mock_session, \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov):
            mock_session.return_value.__enter__.return_value = MagicMock()
            assert await agent._wait_for_all_approvals(["a-1", "a-2"]) is False

    async def test_wait_for_all_approvals_timeout(self):
        agent = make_agent()
        gov = MagicMock()
        gov.get_approval_status = MagicMock(
            return_value={"status": "pending", "action_id": "a-1"})
        with patch("core.atom_meta_agent.SessionLocal") as mock_session, \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("asyncio.sleep", new=AsyncMock()):
            mock_session.return_value.__enter__.return_value = MagicMock()
            assert await agent._wait_for_all_approvals(["a-1"]) is False


class TestExecuteParallelTools:
    async def test_parallel_tools_success(self):
        from core.atom_meta_agent import ToolCall
        agent = make_agent()
        agent.mcp = MagicMock()
        agent.mcp.call_tool = AsyncMock(return_value="parallel-ok")
        gov = _gov(can_perform_action_async=AsyncMock(
            return_value={"allowed": True, "action_complexity": 1, "reason": "ok"}))
        with patch("core.atom_meta_agent.SessionLocal") as mock_session, \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.hallucination_config.is_parallel_tools_enabled",
                   return_value=True), \
             patch("core.hallucination_config.get_max_parallel_tools",
                   return_value=4):
            mock_session.return_value.__enter__.return_value = MagicMock()
            results = await agent._execute_parallel_tools(
                [ToolCall(tool="a", params={}), ToolCall(tool="b", params={})],
                {}, None)
        assert isinstance(results, list)
        assert len(results) == 2

    async def test_parallel_tools_sequential_fallback(self):
        from core.atom_meta_agent import ToolCall
        agent = make_agent()
        agent.mcp = MagicMock()
        agent.mcp.call_tool = AsyncMock(return_value="seq-ok")
        gov = _gov(can_perform_action_async=AsyncMock(
            return_value={"allowed": True, "action_complexity": 1, "reason": "ok"}))
        with patch("core.atom_meta_agent.SessionLocal") as mock_session, \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.hallucination_config.is_parallel_tools_enabled",
                   return_value=False), \
             patch("core.hallucination_config.get_max_parallel_tools",
                   return_value=4):
            mock_session.return_value.__enter__.return_value = MagicMock()
            results = await agent._execute_parallel_tools(
                [ToolCall(tool="a", params={})], {}, None)
        assert len(results) == 1
        assert results[0]["tool_name"] == "a"

    async def test_parallel_batch_hitl_approved(self):
        from core.atom_meta_agent import ToolCall
        agent = make_agent()
        gov = _gov(can_perform_action_async=AsyncMock(
            return_value={"allowed": True, "action_complexity": 3,
                          "requires_human_approval": True, "reason": "complex"}))
        agent._execute_tool_with_governance = AsyncMock(return_value="pre-ok")
        with patch("core.atom_meta_agent.SessionLocal") as mock_session, \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.hallucination_config.is_parallel_tools_enabled",
                   return_value=True), \
             patch("core.hallucination_config.get_max_parallel_tools",
                   return_value=4), \
             patch.object(agent, "_wait_for_all_approvals",
                          new=AsyncMock(return_value=True)):
            mock_session.return_value.__enter__.return_value = MagicMock()
            results = await agent._execute_parallel_tools(
                [ToolCall(tool="a", params={})], {}, None)
        assert results[0]["output"] == "pre-ok"
        agent._execute_tool_with_governance.assert_awaited_once()
        assert agent._execute_tool_with_governance.await_args.kwargs["pre_approved"] is True

    async def test_parallel_batch_hitl_rejected(self):
        from core.atom_meta_agent import ToolCall
        agent = make_agent()
        gov = _gov(can_perform_action_async=AsyncMock(
            return_value={"allowed": True, "action_complexity": 3,
                          "requires_human_approval": True, "reason": "complex"}))
        with patch("core.atom_meta_agent.SessionLocal") as mock_session, \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.hallucination_config.is_parallel_tools_enabled",
                   return_value=True), \
             patch("core.hallucination_config.get_max_parallel_tools",
                   return_value=4), \
             patch.object(agent, "_wait_for_all_approvals",
                          new=AsyncMock(return_value=False)):
            mock_session.return_value.__enter__.return_value = MagicMock()
            results = await agent._execute_parallel_tools(
                [ToolCall(tool="a", params={})], {}, None)
        assert "REJECTED" in results[0]["output"]
        assert results[0]["verified_kind"] == "rejected"

    async def test_parallel_batch_blocked(self):
        from core.atom_meta_agent import ToolCall
        agent = make_agent()
        gov = _gov(can_perform_action_async=AsyncMock(
            return_value={"allowed": False, "action_complexity": 1,
                          "reason": "denied"}))
        with patch("core.atom_meta_agent.SessionLocal") as mock_session, \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.hallucination_config.is_parallel_tools_enabled",
                   return_value=True), \
             patch("core.hallucination_config.get_max_parallel_tools",
                   return_value=4):
            mock_session.return_value.__enter__.return_value = MagicMock()
            results = await agent._execute_parallel_tools(
                [ToolCall(tool="a", params={})], {}, None)
        assert "Governance blocked" in results[0]["output"]
        assert results[0]["verified_kind"] == "blocked"

    async def test_parallel_batch_tool_error(self):
        from core.atom_meta_agent import ToolCall
        agent = make_agent()
        gov = _gov()
        agent._execute_tool_with_governance = AsyncMock(
            side_effect=RuntimeError("tool boom"))
        with patch("core.atom_meta_agent.SessionLocal") as mock_session, \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.hallucination_config.is_parallel_tools_enabled",
                   return_value=True), \
             patch("core.hallucination_config.get_max_parallel_tools",
                   return_value=4):
            mock_session.return_value.__enter__.return_value = MagicMock()
            results = await agent._execute_parallel_tools(
                [ToolCall(tool="a", params={})], {}, None)
        assert "Tool error" in results[0]["output"]
        assert results[0]["verified_kind"] == "error"

    async def test_parallel_batch_killrun_reraises(self):
        from core.sandbox_killrun import KillRunAborted
        from core.atom_meta_agent import ToolCall
        agent = make_agent()
        gov = _gov()
        agent._execute_tool_with_governance = AsyncMock(
            side_effect=KillRunAborted("killed"))
        with patch("core.atom_meta_agent.SessionLocal") as mock_session, \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.hallucination_config.is_parallel_tools_enabled",
                   return_value=True), \
             patch("core.hallucination_config.get_max_parallel_tools",
                   return_value=4):
            mock_session.return_value.__enter__.return_value = MagicMock()
            with pytest.raises(KillRunAborted):
                await agent._execute_parallel_tools(
                    [ToolCall(tool="a", params={})], {}, None)

    async def test_parallel_batch_serial_tool_search(self):
        from core.atom_meta_agent import ToolCall
        agent = make_agent()
        gov = _gov()
        agent.mcp = MagicMock()
        agent.mcp.search_tools = AsyncMock(
            return_value=[{"name": "found_tool", "description": "d"}])
        agent.session_tools = []
        with patch("core.atom_meta_agent.SessionLocal") as mock_session, \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.hallucination_config.is_parallel_tools_enabled",
                   return_value=True), \
             patch("core.hallucination_config.get_max_parallel_tools",
                   return_value=4):
            mock_session.return_value.__enter__.return_value = MagicMock()
            results = await agent._execute_parallel_tools(
                [ToolCall(tool="mcp_tool_search", params={"query": "q"})], {}, None)
        assert any("found_tool" in r["output"] for r in results)

    async def test_parallel_batch_serial_search_error(self):
        from core.atom_meta_agent import ToolCall
        agent = make_agent()
        gov = _gov()
        agent.mcp = MagicMock()
        agent.mcp.search_tools = AsyncMock(side_effect=RuntimeError("search down"))
        agent.session_tools = []
        with patch("core.atom_meta_agent.SessionLocal") as mock_session, \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.hallucination_config.is_parallel_tools_enabled",
                   return_value=True), \
             patch("core.hallucination_config.get_max_parallel_tools",
                   return_value=4):
            mock_session.return_value.__enter__.return_value = MagicMock()
            results = await agent._execute_parallel_tools(
                [ToolCall(tool="mcp_tool_search", params={"query": "q"})], {}, None)
        assert "Tool search failed" in results[0]["output"]


class TestRecruitFleet:
    async def test_recruit_fleet_no_subtasks(self):
        agent = make_agent()
        result = await agent._recruit_fleet("goal", [], {}, None)
        assert isinstance(result, str)

    async def test_recruit_fleet_with_subtasks(self):
        agent = make_agent()
        sub = MagicMock()
        sub.name = "Specialist"
        sub.execute = AsyncMock(return_value={"final_output": "sub-done"})
        with patch("core.business_agents.get_specialized_agent",
                   return_value=sub):
            result = await agent._recruit_fleet(
                "goal", [{"agent": "sales", "task": "t"}], {}, None)
        assert isinstance(result, str)


class TestMentorship:
    async def test_generate_mentorship_guidance(self):
        agent = make_agent()
        agent.llm.generate_response = AsyncMock(return_value="Check the params carefully")
        db = MagicMock()
        student = MagicMock()
        student.category = "sales"
        # student lookup via .first()
        first_q = MagicMock()
        first_q.first.return_value = student
        # supervisor count via .count()
        count_q = MagicMock()
        count_q.count.return_value = 0
        db.query.return_value.filter.return_value.first.return_value = student
        db.query.return_value.filter.return_value.count.return_value = 0
        with patch("core.atom_meta_agent.SessionLocal") as mock_session:
            mock_session.return_value.__enter__.return_value = db
            result = await agent.generate_mentorship_guidance(
                "student-1", "create_record", {"a": 1}, "needs approval")
        assert "Check the params carefully" in result

    async def test_generate_mentorship_guidance_no_student(self):
        agent = make_agent()
        agent.llm.generate_response = AsyncMock(
            return_value="Meta-Agent was unable to provide guidance for this action.")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.atom_meta_agent.SessionLocal") as mock_session:
            mock_session.return_value.__enter__.return_value = db
            result = await agent.generate_mentorship_guidance(
                "student-1", "create_record", {}, "needs approval")
        assert isinstance(result, str)
        assert result

    async def test_generate_mentorship_guidance_db_error(self):
        agent = make_agent()
        agent.llm.generate_response = AsyncMock(return_value="safe guidance")
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        with patch("core.atom_meta_agent.SessionLocal") as mock_session:
            mock_session.return_value.__enter__.return_value = db
            result = await agent.generate_mentorship_guidance(
                "student-1", "create_record", {}, "needs approval")
        assert isinstance(result, str)


class TestRoutingHelpers:
    """Module-level routing methods (single-tenant port)."""

    async def test_check_governance_allowed(self):
        from core.atom_meta_agent import _check_governance
        agent = make_agent()
        decision = MagicMock()
        decision.allowed = True
        decision.reason = None
        gov = MagicMock()
        gov.canPerformAction = AsyncMock(return_value=decision)
        with patch("core.database.SessionLocal") as mock_session, \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov):
            mock_session.return_value.__enter__.return_value = MagicMock()
            allowed, reason = await _check_governance(agent, "u-1", "a-1", "chat")
        assert allowed is True
        assert reason is None

    async def test_check_governance_denied(self):
        from core.atom_meta_agent import _check_governance
        agent = make_agent()
        decision = MagicMock()
        decision.allowed = False
        decision.reason = "maturity too low"
        gov = MagicMock()
        gov.canPerformAction = AsyncMock(return_value=decision)
        with patch("core.database.SessionLocal") as mock_session, \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov):
            mock_session.return_value.__enter__.return_value = MagicMock()
            allowed, reason = await _check_governance(agent, "u-1", "a-1", "task")
        assert allowed is False
        assert reason == "maturity too low"

    async def test_route_to_chat(self):
        from core.atom_meta_agent import _route_to_chat
        agent = make_agent()
        agent.llm.generate_response = AsyncMock(return_value="chat reply")
        result = await _route_to_chat(agent, "hello", "u-1")
        assert result["route"] == "CHAT"
        assert result["response"] == "chat reply"

    async def test_route_to_workflow(self):
        from core.atom_meta_agent import _route_to_workflow
        agent = make_agent()
        queen = MagicMock()
        queen.generate_blueprint = AsyncMock(return_value={
            "blueprint_id": "bp-1", "architecture_name": "Arch",
            "nodes": [{"name": "n1"}]})
        with patch("core.database.SessionLocal") as mock_session:
            mock_session.return_value.__enter__.return_value = MagicMock()
            agent.queen = queen
            result = await _route_to_workflow(agent, "build pipeline", "u-1")
        assert result["route"] == "WORKFLOW"
        assert result["blueprint_id"] == "bp-1"
        assert result["node_count"] == 1

    async def test_route_to_workflow_lazy_queen(self):
        from core.atom_meta_agent import _route_to_workflow
        agent = make_agent()
        queen = MagicMock()
        queen.generate_blueprint = AsyncMock(return_value={
            "blueprint_id": "bp-2", "architecture_name": "Arch",
            "nodes": []})
        with patch("core.database.SessionLocal") as mock_session, \
             patch("core.agents.queen_agent.QueenAgent",
                   return_value=queen):
            mock_session.return_value.__enter__.return_value = MagicMock()
            result = await _route_to_workflow(agent, "build", "u-1")
        assert result["status"] == "blueprint_generated"
        assert agent.queen is queen

    async def test_route_to_task(self):
        from core.atom_meta_agent import _route_to_task
        agent = make_agent()
        fleet = MagicMock()
        fleet.recruit_and_execute = AsyncMock(return_value={"done": True})
        with patch("core.database.SessionLocal") as mock_session, \
             patch("core.fleet_admiral.FleetAdmiral",
                   return_value=fleet):
            mock_session.return_value.__enter__.return_value = MagicMock()
            result = await _route_to_task(agent, "do task", "u-1")
        assert result["route"] == "TASK"
        assert result["status"] == "task_routed"

    async def test_route_to_task_exception(self):
        from core.atom_meta_agent import _route_to_task
        agent = make_agent()
        fleet = MagicMock()
        fleet.recruit_and_execute = AsyncMock(side_effect=RuntimeError("fleet down"))
        with patch("core.database.SessionLocal") as mock_session, \
             patch("core.fleet_admiral.FleetAdmiral",
                   return_value=fleet):
            mock_session.return_value.__enter__.return_value = MagicMock()
            with pytest.raises(RuntimeError, match="fleet down"):
                await _route_to_task(agent, "do task", "u-1")

    async def test_propose_chat_alternative(self):
        from core.atom_meta_agent import _propose_chat_alternative
        agent = make_agent()
        agent.llm.generate_response = AsyncMock(return_value="chat alternative")
        result = await _propose_chat_alternative(
            agent, "original", "workflow", "not enough maturity", "u-1")
        assert isinstance(result, dict)
        assert "chat_response" in result or "response" in result or "proposal" in result


class TestRecruitFleetBranches:
    async def test_recruit_fleet_specialist_not_found(self):
        agent = make_agent()
        with patch("core.business_agents.get_specialized_agent",
                   return_value=None):
            result = await agent._recruit_fleet(
                "goal", [{"agent": "ghost", "task": "t"}], {}, None)
        assert isinstance(result, str)

    async def test_recruit_fleet_subagent_error(self):
        agent = make_agent()
        sub = MagicMock()
        sub.name = "Sales"
        sub.execute = AsyncMock(side_effect=RuntimeError("subagent boom"))
        with patch("core.business_agents.get_specialized_agent",
                   return_value=sub):
            result = await agent._recruit_fleet(
                "goal", [{"agent": "sales", "task": "t"}], {}, None)
        assert isinstance(result, str)


class TestSpawnAgent:
    async def test_spawn_agent_template(self):
        agent = make_agent()
        with patch("core.atom_meta_agent.SessionLocal") as mock_session:
            mock_session.return_value.__enter__.return_value = MagicMock()
            result = await agent.spawn_agent(
                "finance_analyst", {"region": "west"}, persist=False)
        assert result is not None

    async def test_spawn_agent_custom(self):
        agent = make_agent()
        result = await agent.spawn_agent(
            "custom", {"name": "Custom Agent", "capabilities": ["read"]},
            persist=False)
        assert result is not None


class TestPersistReasoningStepBranches:
    def test_persist_reasoning_step_success(self):
        agent = make_agent()
        db = MagicMock()
        db_step = MagicMock()
        db_step.id = "rs-99"
        db.add = MagicMock()
        db.commit = MagicMock()
        db.query.return_value.get.return_value = db_step
        # make AgentReasoningStep construct return our mock via patched class
        with patch("core.atom_meta_agent.AgentReasoningStep",
                   return_value=db_step), \
             patch("core.atom_meta_agent.SessionLocal") as mock_session:
            mock_session.return_value.__enter__.return_value = db
            step_id = agent._persist_reasoning_step(
                execution_id="ex-1", step_number=1, step_type="action",
                thought="t", action_dict={"tool": "a"}, observation="o",
                confidence=0.9, verified_kind="unverified",
                verification_evidence=None, duration_ms=10.0,
                request="r", final_answer=None, context={},
                dispatch_turn_fact=False)
        assert step_id == "rs-99"

    def test_persist_reasoning_step_db_error(self):
        agent = make_agent()
        with patch("core.atom_meta_agent.SessionLocal",
                   side_effect=RuntimeError("db down")):
            step_id = agent._persist_reasoning_step(
                execution_id="ex-1", step_number=1, step_type="action",
                thought="t", action_dict=None, observation="o",
                confidence=0.9, verified_kind="unverified",
                verification_evidence=None, duration_ms=1.0,
                request="r", final_answer=None, context={})
        assert step_id == ""

    def test_persist_reasoning_step_turn_fact_dispatch(self):
        agent = make_agent()
        db = MagicMock()
        db_step = MagicMock()
        db_step.id = "rs-100"
        db.add = MagicMock()
        db.commit = MagicMock()
        extractor = MagicMock()
        extractor.extract_from_turn = AsyncMock()
        with patch("core.atom_meta_agent.AgentReasoningStep",
                   return_value=db_step), \
             patch("core.atom_meta_agent.SessionLocal") as mock_session, \
             patch("core.atom_meta_agent.get_turn_fact_extractor",
                   return_value=extractor), \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", True):
            mock_session.return_value.__enter__.return_value = db
            step_id = agent._persist_reasoning_step(
                execution_id="ex-1", step_number=1, step_type="action",
                thought="t", action_dict=None, observation="o",
                confidence=0.9, verified_kind="unverified",
                verification_evidence=None, duration_ms=1.0,
                request="r", final_answer="done", context={"user_id": "u-1"},
                dispatch_turn_fact=True)
        assert step_id == "rs-100"
        extractor.extract_from_turn.assert_called_once()

    def test_persist_reasoning_step_extraction_error(self):
        agent = make_agent()
        db = MagicMock()
        db_step = MagicMock()
        db_step.id = "rs-101"
        db.add = MagicMock()
        db.commit = MagicMock()
        with patch("core.atom_meta_agent.AgentReasoningStep",
                   return_value=db_step), \
             patch("core.atom_meta_agent.SessionLocal") as mock_session, \
             patch("core.atom_meta_agent.get_turn_fact_extractor",
                   side_effect=RuntimeError("extractor down")), \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", True):
            mock_session.return_value.__enter__.return_value = db
            step_id = agent._persist_reasoning_step(
                execution_id="ex-1", step_number=1, step_type="action",
                thought="t", action_dict=None, observation="o",
                confidence=0.9, verified_kind="unverified",
                verification_evidence=None, duration_ms=1.0,
                request="r", final_answer=None, context={})
        assert step_id == "rs-101"  # step persisted; extraction failure swallowed


class TestHandleManualTrigger:
    async def test_handle_manual_trigger_success(self):
        from core.atom_meta_agent import handle_manual_trigger
        user = MagicMock()
        user.id = "u-1"
        user.email = "u@example.com"
        with patch("core.atom_meta_agent.AtomMetaAgent") as mock_cls:
            agent = MagicMock()
            agent.execute = AsyncMock(return_value={
                "final_output": "done", "actions_executed": [],
                "status": "success"})
            mock_cls.return_value = agent
            result = await handle_manual_trigger(
                "hello", user, execution_id="ex-1")
        assert result["status"] == "success"
        agent.execute.assert_awaited_once()

    async def test_handle_manual_trigger_streaming_callback(self):
        from core.atom_meta_agent import handle_manual_trigger
        user = MagicMock()
        user.id = "u-1"
        user.email = "u@example.com"
        captured = {}

        async def _execute(request, context, trigger_mode, step_callback,
                           execution_id):
            captured["cb"] = step_callback
            await step_callback({
                "execution_id": execution_id,
                "step": 1, "step_type": "action",
                "thought": "thinking", "action": {"tool": "a"},
                "output": "obs", "confidence": 0.9,
                "duration_ms": 5.0,
            })
            return {"final_output": "done", "actions_executed": [],
                    "status": "success"}

        with patch("core.atom_meta_agent.AtomMetaAgent") as mock_cls, \
             patch("core.websockets.manager") as mock_ws:
            mock_ws.broadcast = AsyncMock()
            tracker = MagicMock()
            with patch("core.reasoning_chain.get_reasoning_tracker",
                       return_value=tracker):
                agent = MagicMock()
                agent.execute = AsyncMock(side_effect=_execute)
                mock_cls.return_value = agent
                result = await handle_manual_trigger(
                    "hello", user, execution_id="ex-1")
        assert result["status"] == "success"
        mock_ws.broadcast.assert_awaited_once()
        tracker.persist_step_to_db.assert_called_once()

    async def test_handle_manual_trigger_callback_error_swallowed(self):
        from core.atom_meta_agent import handle_manual_trigger
        user = MagicMock()
        user.id = "u-1"
        user.email = "u@example.com"

        async def _execute(request, context, trigger_mode, step_callback,
                           execution_id):
            await step_callback({"execution_id": execution_id, "step": 1,
                                 "step_type": "action", "thought": "t"})
            return {"final_output": "done", "actions_executed": [],
                    "status": "success"}

        with patch("core.atom_meta_agent.AtomMetaAgent") as mock_cls, \
             patch("core.websockets.manager") as mock_ws, \
             patch("core.reasoning_chain.get_reasoning_tracker",
                   side_effect=RuntimeError("tracker down")):
            mock_ws.broadcast = AsyncMock(side_effect=RuntimeError("ws down"))
            agent = MagicMock()
            agent.execute = AsyncMock(side_effect=_execute)
            mock_cls.return_value = agent
            result = await handle_manual_trigger(
                "hello", user, execution_id="ex-1")
        assert result["status"] == "success"

    async def test_handle_manual_trigger_additional_context(self):
        from core.atom_meta_agent import handle_manual_trigger
        user = MagicMock()
        user.id = "u-1"
        user.email = "u@example.com"
        with patch("core.atom_meta_agent.AtomMetaAgent") as mock_cls:
            agent = MagicMock()
            agent.execute = AsyncMock(return_value={
                "final_output": "done", "actions_executed": [],
                "status": "success"})
            mock_cls.return_value = agent
            result = await handle_manual_trigger(
                "hello", user, additional_context={"channel": "web"},
                execution_id="ex-1")
        assert result["status"] == "success"
        ctx = agent.execute.await_args.kwargs["context"]
        assert ctx["channel"] == "web"
        assert ctx["user_id"] == "u-1"
