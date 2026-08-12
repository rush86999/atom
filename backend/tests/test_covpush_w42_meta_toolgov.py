"""Coverage wave 42 — core/atom_meta_agent.py tool-governance + fleet paths (TDD).

Closes the remaining execution blocks: _trigger_workflow (missing id /
success / exception), _execute_tool_with_governance (pre-approved skip,
complexity>1 HITL gate approved/rejected, governance-blocked, special
tools trigger_workflow/delegate_task/recruit_fleet, invoke_capability
student-block/success/record_usage paths, sandbox enforced+shadow,
ActionJudge BLOCK/ESCALATE/disabled, generic tool execution, KillRun
re-raise, error envelope) and _recruit_fleet (full orchestration with
optimizer + radio bridge + error path) — all mocked, zero spend.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.atom_meta_agent import AtomMetaAgent


def make_gov_agent(**kw):
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
    agent.mcp.call_tool = AsyncMock(return_value={"status": "success", "output": "ok"})
    agent.mcp.search_tools = AsyncMock(return_value=[])
    agent.graduation_service = MagicMock()
    agent.graduation_service.get_maturity = MagicMock(return_value="supervised")
    for k, v in kw.items():
        setattr(agent, k, v)
    return agent


def _gov(auth_check=None):
    gov = MagicMock()
    gov.can_perform_action_async = AsyncMock(
        return_value=auth_check or {"allowed": True, "action_complexity": 1,
                                    "reason": "ok"})
    gov.request_approval.return_value = "act-1"
    return gov


def _db(gov=None):
    db = MagicMock()
    db.__enter__ = MagicMock(return_value=db)
    db.__exit__ = MagicMock(return_value=False)
    db.close = MagicMock()
    return db


class TestTriggerWorkflow:
    async def test_missing_id(self):
        agent = make_gov_agent()
        result = await agent._trigger_workflow(None, {}, {})
        assert "workflow_id is required" in result

    async def test_success(self):
        agent = make_gov_agent()
        engine = MagicMock()
        engine.start_workflow = AsyncMock(return_value="ex-1")
        with patch("core.workflow_engine.get_workflow_engine",
                   return_value=engine):
            result = await agent._trigger_workflow("wf-1", {"x": 1}, {})
        assert "wf-1" in result and "ex-1" in result

    async def test_exception(self):
        agent = make_gov_agent()
        with patch("core.workflow_engine.get_workflow_engine",
                   side_effect=RuntimeError("engine down")):
            result = await agent._trigger_workflow("wf-1", {}, {})
        assert "Error triggering" in result


class TestExecuteToolWithGovernance:
    async def test_pre_approved_skips_governance(self):
        agent = make_gov_agent()
        result = await agent._execute_tool_with_governance(
            "run_tool", {"a": 1}, {}, None, pre_approved=True)
        assert result == "{'status': 'success', 'output': 'ok'}"
        agent.mcp.call_tool.assert_called_once()

    async def test_complexity_approval_approved(self):
        agent = make_gov_agent()
        gov = _gov({"allowed": True, "action_complexity": 3, "reason": "complex"})
        with patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_db()), \
             patch.object(agent, "_wait_for_approval",
                          new=AsyncMock(return_value=True)):
            result = await agent._execute_tool_with_governance(
                "run_tool", {}, {"agent_id": "ag"}, None)
        assert "success" in result
        gov.request_approval.assert_called_once()

    async def test_complexity_approval_rejected(self):
        agent = make_gov_agent()
        gov = _gov({"allowed": True, "action_complexity": 3, "reason": "complex"})
        with patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_db()), \
             patch.object(agent, "_wait_for_approval",
                          new=AsyncMock(return_value=False)):
            result = await agent._execute_tool_with_governance(
                "run_tool", {}, {}, None)
        assert "REJECTED or timed out" in result
        agent.mcp.call_tool.assert_not_called()

    async def test_governance_blocked(self):
        agent = make_gov_agent()
        gov = _gov({"allowed": False, "action_complexity": 1, "reason": "maturity"})
        with patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_db()):
            result = await agent._execute_tool_with_governance(
                "run_tool", {}, {}, None)
        assert "Governance blocked" in result
        assert "maturity" in result

    async def test_trigger_workflow_tool(self):
        agent = make_gov_agent()
        gov = _gov()
        engine = MagicMock()
        engine.start_workflow = AsyncMock(return_value="ex-9")
        with patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_db()), \
             patch("core.workflow_engine.get_workflow_engine",
                   return_value=engine):
            result = await agent._execute_tool_with_governance(
                "trigger_workflow", {"workflow_id": "wf-1"}, {}, None)
        assert "triggered" in result

    async def test_delegate_task_tool(self):
        agent = make_gov_agent()
        gov = _gov()
        agent._execute_delegation = AsyncMock(return_value="delegated")
        with patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_db()):
            result = await agent._execute_tool_with_governance(
                "delegate_task", {"agent_name": "sales", "task": "t"}, {}, None)
        assert result == "delegated"

    async def test_recruit_fleet_tool(self):
        agent = make_gov_agent()
        gov = _gov()
        agent._recruit_fleet = AsyncMock(return_value="fleet ready")
        with patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_db()):
            result = await agent._execute_tool_with_governance(
                "recruit_fleet", {"goal": "g", "sub_tasks": []}, {}, None)
        assert result == "fleet ready"

    async def test_invoke_capability_student_blocked(self):
        agent = make_gov_agent()
        gov = _gov()
        agent.graduation_service.get_maturity.return_value = "student"
        with patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_db()):
            result = await agent._execute_tool_with_governance(
                "invoke_capability", {"capability_name": "analysis"}, {}, None)
        assert "STUDENT level" in result
        agent.mcp.call_tool.assert_not_called()

    async def test_invoke_capability_success(self):
        agent = make_gov_agent()
        gov = _gov()
        agent.mcp.call_tool = AsyncMock(return_value={"status": "success", "output": "r"})
        with patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_db()):
            result = await agent._execute_tool_with_governance(
                "invoke_capability", {"capability_name": "analysis",
                                      "params": {}}, {}, None)
        assert "success" in result
        agent.graduation_service.record_usage.assert_called_once()

    async def test_invoke_capability_record_usage_failure(self):
        agent = make_gov_agent()
        gov = _gov()
        agent.mcp.call_tool = AsyncMock(return_value={"ok": True})
        with patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_db()), \
             patch("core.atom_meta_agent.parse_tool_outcome",
                   side_effect=RuntimeError("parse fail")):
            result = await agent._execute_tool_with_governance(
                "invoke_capability", {"capability_name": "analysis"}, {}, None)
        assert "ok" in result
        # parse failed → only the except-fallback record_usage runs
        assert agent.graduation_service.record_usage.call_count == 1
        assert agent.graduation_service.record_usage.call_args.kwargs["verified"] == "unverified"

    async def test_sandbox_enforced_block(self):
        agent = make_gov_agent()
        gov = _gov()
        decision = SimpleNamespace(requires_review=True, enforced=True,
                                   decision="blocked", violation_detail="fs scope")
        with patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_db()), \
             patch("core.atom_meta_agent._meta_agent_sandbox_check",
                   return_value=decision):
            result = await agent._execute_tool_with_governance(
                "run_tool", {}, {"agent_id": "ag"}, None)
        assert "Sandbox blocked" in result
        agent.mcp.call_tool.assert_not_called()

    async def test_sandbox_shadow_proceeds(self):
        agent = make_gov_agent()
        gov = _gov()
        decision = SimpleNamespace(requires_review=True, enforced=False,
                                   decision="review",
                                   violation_detail="d",
                                   violation_type="fs")
        with patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_db()), \
             patch("core.atom_meta_agent._meta_agent_sandbox_check",
                   return_value=decision):
            result = await agent._execute_tool_with_governance(
                "run_tool", {}, {"agent_id": "ag"}, None)
        assert "success" in result
        agent.mcp.call_tool.assert_called_once()

    async def test_action_judge_block(self):
        agent = make_gov_agent()
        gov = _gov()
        judge_result = SimpleNamespace(verdict="block", rationale="unsafe")
        judge = MagicMock()
        judge.evaluate = AsyncMock(return_value=judge_result)
        with patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_db()), \
             patch("core.sandbox_config.is_sandbox_judge_enabled",
                   return_value=True), \
             patch("core.llm.action_judge.ActionJudge",
                   return_value=judge):
            result = await agent._execute_tool_with_governance(
                "run_tool", {}, {"agent_id": "ag"}, None)
        assert "blocked by the safety judge" in result
        agent.mcp.call_tool.assert_not_called()

    async def test_action_judge_escalate_rejected(self):
        agent = make_gov_agent()
        gov = _gov()
        gov.request_approval.return_value = "judge-act"
        judge_result = SimpleNamespace(verdict="escalate", rationale="risky")
        judge = MagicMock()
        judge.evaluate = AsyncMock(return_value=judge_result)
        with patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_db()), \
             patch("core.sandbox_config.is_sandbox_judge_enabled",
                   return_value=True), \
             patch("core.llm.action_judge.ActionJudge",
                   return_value=judge), \
             patch.object(agent, "_wait_for_approval",
                          new=AsyncMock(return_value=False)):
            result = await agent._execute_tool_with_governance(
                "run_tool", {}, {"agent_id": "ag"}, None)
        assert "safety-judge escalation" in result
        agent.mcp.call_tool.assert_not_called()

    async def test_killrun_reraises(self):
        from core.sandbox_killrun import KillRunAborted
        agent = make_gov_agent()
        gov = _gov()
        with patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_db()), \
             patch("core.atom_meta_agent._meta_agent_sandbox_check",
                   side_effect=KillRunAborted("killed")):
            with pytest.raises(KillRunAborted):
                await agent._execute_tool_with_governance(
                    "run_tool", {}, {}, None)

    async def test_generic_error_envelope(self):
        agent = make_gov_agent()
        gov = _gov()
        agent.mcp.call_tool = AsyncMock(side_effect=RuntimeError("mcp down"))
        with patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_db()):
            result = await agent._execute_tool_with_governance(
                "run_tool", {}, {}, None)
        assert result == "Tool error. Please try again."


class TestRecruitFleet:
    async def test_full_flow(self):
        agent = make_gov_agent()
        fleet = MagicMock()
        chain = SimpleNamespace(id="chain-1")
        fleet.initialize_fleet.return_value = chain
        fleet.recruit_member.return_value = SimpleNamespace(id="link-1")
        optimizer = MagicMock()
        optimizer.get_optimization_parameters.return_value = {
            "optimization_reason": "budget", "params": {}}
        specialist = SimpleNamespace(id="spec-1", name="Sales")
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        with patch("core.business_agents.get_specialized_agent",
                   return_value=specialist), \
             patch("core.atom_meta_agent.AgentFleetService",
                   return_value=fleet), \
             patch("core.atom_meta_agent.FleetOptimizationService",
                   return_value=optimizer), \
             patch("core.atom_meta_agent.SessionLocal", return_value=db), \
             patch("core.agent_radio.radio_adapter.attach_thread_for_chain",
                   return_value="thread-1"):
            result = await agent._recruit_fleet(
                "big goal",
                [{"domain": "sales", "task": "analyze", "use_optimizer": True}],
                {"execution_id": "ex-1"}, None)
        assert "Fleet" in result
        fleet.initialize_fleet.assert_called_once()
        fleet.recruit_member.assert_called_once()
        optimizer.get_optimization_parameters.assert_called_once()

    async def test_no_specialist_uses_placeholder(self):
        agent = make_gov_agent()
        fleet = MagicMock()
        chain = SimpleNamespace(id="chain-2")
        fleet.initialize_fleet.return_value = chain
        fleet.recruit_member.return_value = SimpleNamespace(id="link-2")
        optimizer = MagicMock()
        optimizer.get_optimization_parameters.return_value = {
            "optimization_reason": "r", "params": {}}
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        with patch("core.business_agents.get_specialized_agent",
                   return_value=None), \
             patch("core.atom_meta_agent.AgentFleetService",
                   return_value=fleet), \
             patch("core.atom_meta_agent.FleetOptimizationService",
                   return_value=optimizer), \
             patch("core.atom_meta_agent.SessionLocal", return_value=db), \
             patch("core.agent_radio.radio_adapter.attach_thread_for_chain",
                   return_value=None):
            result = await agent._recruit_fleet(
                "goal", [{"domain": "ghost", "task": "t", "use_optimizer": False}],
                {}, None)
        assert "Fleet" in result

    async def test_exception(self):
        agent = make_gov_agent()
        with patch("core.atom_meta_agent.AgentFleetService",
                   side_effect=RuntimeError("fleet down")):
            result = await agent._recruit_fleet("goal", [], {}, None)
        assert "Fleet recruitment failed" in result
