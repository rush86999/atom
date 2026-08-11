"""Coverage wave 30 — core/atom_meta_agent.py deterministic paths (TDD).

Drives the module helpers and governance/routing/delegation plumbing
with mocked dependencies: error-observation heuristics, the P9 sandbox
gate helper (all phases + fail-open), intent/specialty templates,
skill injection, budget pre-check, delegation, reasoning-step
persistence (+ turn-fact dispatch), communication-style loading,
governance-gated routing (chat bypass / workflow / task / auto-takeover
proposal), data-event triggers and the singleton factory — zero LLM
calls (all mocked), zero spend.
"""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.atom_meta_agent import (
    IntentCategory,
    IntentClassification,
    AtomMetaAgent,
    ReActStep,
    SpecialtyAgentTemplate,
    ToolCall,
    _is_error_observation,
    _meta_agent_sandbox_check,
    get_atom_agent,
    handle_data_event_trigger,
)


# ---------------------------------------------------------------------------
# module helpers
# ---------------------------------------------------------------------------


class TestIsErrorObservation:
    @pytest.mark.parametrize("text", [
        "Tool error. failed to run",
        "tool execution failed: boom",
        "Governance blocked: maturity too low",
        "governance error in dispatch",
        "proposal was rejected",
        "rejected or timed out",
        "sandbox blocked the call",
        "sandbox error: egress denied",
    ])
    def test_error_markers(self, text):
        assert _is_error_observation(text) is True

    def test_non_errors(self):
        assert _is_error_observation(None) is False
        assert _is_error_observation("all good") is False
        assert _is_error_observation("the word error inside json {'error': null}") is False


class TestMetaAgentSandboxCheck:
    def test_disabled_returns_none(self):
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=False):
            assert _meta_agent_sandbox_check("tool", {}, {"run_id": "r"}) is None

    def test_no_run_id_returns_none(self):
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=True), \
             patch("core.sandbox_policy.PolicyIssuer"):
            assert _meta_agent_sandbox_check("tool", {}, {}) is None

    def test_no_tier_returns_none(self):
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=True), \
             patch("core.sandbox_policy.PolicyIssuer"):
            assert _meta_agent_sandbox_check(
                "tool", {}, {"run_id": "r1"}) is None

    def test_allowed_flow(self):
        allowed = SimpleNamespace(is_allowed=True, requires_review=False,
                                  decision="allowed", args_hash="h",
                                  violation_detail=None, metadata_json={})
        issuer = MagicMock()
        issuer.issue.return_value = "policy"
        issuer.check.return_value = allowed
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=True), \
             patch("core.sandbox_config.is_sandbox_fs_enabled", return_value=True), \
             patch("core.sandbox_config.is_sandbox_tripwires_enabled", return_value=True), \
             patch("core.sandbox_config.is_sandbox_caps_enabled", return_value=True), \
             patch("core.sandbox_policy.PolicyIssuer", return_value=issuer), \
             patch("core.sandbox_fs.validate",
                   return_value=SimpleNamespace(requires_review=False,
                                                decision="allowed",
                                                args_hash="h",
                                                metadata_json={})), \
             patch("core.sandbox_tripwire.check",
                   return_value=SimpleNamespace(decision="allowed",
                                                killrun_triggered=False,
                                                violation_detail=None,
                                                args_hash="h",
                                                metadata_json={})), \
             patch("core.sandbox_caps.check_caps",
                   return_value=SimpleNamespace(requires_review=False,
                                                decision="allowed")), \
             patch("core.sandbox_killrun.guard"):
            result = _meta_agent_sandbox_check(
                "run_tool", {"a": 1},
                {"run_id": "r1", "tier_at_issuance": "SUPERVISED",
                 "agent_id": "ag-1", "workspace_id": "ws"})
        assert result.is_allowed is True
        issuer.issue.assert_called_once()

    def test_requires_review_writes_violation(self):
        decision = SimpleNamespace(is_allowed=False, requires_review=True,
                                   decision="review", args_hash="h",
                                   violation_detail="nope", metadata_json={})
        issuer = MagicMock()
        issuer.check.return_value = decision
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=True), \
             patch("core.sandbox_policy.PolicyIssuer", return_value=issuer), \
             patch("core.sandbox_audit.write_violation") as wv:
            result = _meta_agent_sandbox_check(
                "run_tool", {},
                {"run_id": "r1", "tier": "intern", "tenant_id": "t",
                 "workspace_id": "w", "agent_id": "a", "user_id": "u",
                 "session_id": "s"})
        assert result.requires_review is True
        wv.assert_called_once()

    def test_tripwire_killrun(self):
        allowed = SimpleNamespace(is_allowed=True, requires_review=False,
                                  decision="allowed", args_hash="h",
                                  violation_detail=None, metadata_json={})
        tw = SimpleNamespace(decision="blocked", is_allowed=False,
                             requires_review=False,
                             killrun_triggered=True,
                             violation_detail="tripwire-hit", args_hash="h",
                             metadata_json={"tripwire_id": "tw1"})
        issuer = MagicMock()
        issuer.check.return_value = allowed
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=True), \
             patch("core.sandbox_config.is_sandbox_tripwires_enabled", return_value=True), \
             patch("core.sandbox_config.is_sandbox_force_enforce_enabled", return_value=True), \
             patch("core.sandbox_policy.PolicyIssuer", return_value=issuer), \
             patch("core.sandbox_tripwire.check", return_value=tw), \
             patch("core.sandbox_killrun.trigger_killrun") as trigger, \
             patch("core.sandbox_killrun.guard"):
            result = _meta_agent_sandbox_check(
                "run_tool", {}, {"run_id": "r1", "tier": "supervised"})
        assert result.decision == "blocked"
        trigger.assert_called_once()

    def test_exception_fails_open(self):
        issuer = MagicMock()
        issuer.check.side_effect = RuntimeError("sandbox broken")
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=True), \
             patch("core.sandbox_policy.PolicyIssuer", return_value=issuer), \
             patch("core.sandbox_policy.SandboxDecision",
                   lambda **kw: SimpleNamespace(**kw)):
            result = _meta_agent_sandbox_check(
                "run_tool", {}, {"run_id": "r1", "tier": "intern"})
        assert result.decision == "allowed"
        assert "error" in result.metadata_json

    def test_killrun_aborted_propagates(self):
        from core.sandbox_killrun import KillRunAborted
        with patch("core.sandbox_config.is_sandbox_enabled", return_value=True), \
             patch("core.sandbox_policy.PolicyIssuer",
                   side_effect=KillRunAborted("killed")):
            with pytest.raises(KillRunAborted):
                _meta_agent_sandbox_check(
                    "run_tool", {}, {"run_id": "r1", "tier": "intern"})


# ---------------------------------------------------------------------------
# models + templates
# ---------------------------------------------------------------------------


class TestModelsAndTemplates:
    def test_tool_call(self):
        tc = ToolCall(tool="run_tool", params={"a": 1})
        assert tc.tool == "run_tool"
        assert tc.params == {"a": 1}

    def test_react_step_variants(self):
        step = ReActStep(thought="think", action=ToolCall(tool="t"))
        assert step.action.tool == "t"
        multi = ReActStep(thought="t", actions=[ToolCall(tool="a"), ToolCall(tool="b")])
        assert len(multi.actions) == 2
        final = ReActStep(thought="t", final_answer="done", confidence=0.5)
        assert final.final_answer == "done"

    def test_intent_classification(self):
        ic = IntentClassification(category=IntentCategory.WORKFLOW,
                                  confidence=0.9, reasoning="r",
                                  requires_execution=True,
                                  suggested_handler="queen_agent",
                                  is_structured=True, is_long_horizon=True,
                                  requires_agent_recruitment=True,
                                  blueprint_applicable=True)
        assert ic.category == IntentCategory.WORKFLOW
        assert ic.is_structured is True

    def test_specialty_templates(self):
        assert "finance_analyst" in SpecialtyAgentTemplate.TEMPLATES
        assert "king_agent" in SpecialtyAgentTemplate.TEMPLATES
        king = SpecialtyAgentTemplate.TEMPLATES["king_agent"]
        assert king["module_path"] == "core.agents.king_agent"
        assert "delegate_task" in king["capabilities"]
        for name in ["finance_analyst", "sales_assistant", "ops_coordinator",
                     "hr_assistant", "procurement_specialist", "knowledge_analyst",
                     "marketing_analyst"]:
            t = SpecialtyAgentTemplate.TEMPLATES[name]
            assert t["name"] and t["category"] and t["capabilities"]


# ---------------------------------------------------------------------------
# agent construction
# ---------------------------------------------------------------------------


def _intent(category):
    return IntentClassification(
        category=category, confidence=1.0, reasoning="r",
        requires_execution=category != IntentCategory.CHAT,
        suggested_handler="queen_agent")


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


# ---------------------------------------------------------------------------
# delegation / skill injection / budget
# ---------------------------------------------------------------------------


class TestDelegationAndSkills:
    async def test_delegation_agent_not_found(self):
        agent = make_agent()
        with patch("core.business_agents.get_specialized_agent", return_value=None):
            result = await agent._execute_delegation("ghost", "task", {})
        assert "not found" in result

    async def test_delegation_success(self):
        agent = make_agent()
        sub = MagicMock()
        sub.name = "Sales"
        sub.execute = AsyncMock(return_value={"final_output": "done!"})
        with patch("core.business_agents.get_specialized_agent", return_value=sub):
            result = await agent._execute_delegation(
                "sales", "task", {}, execution_id="ex-1")
        assert "Delegation Result from Sales" in result
        assert "done!" in result

    async def test_delegation_exception(self):
        agent = make_agent()
        with patch("core.business_agents.get_specialized_agent",
                   side_effect=RuntimeError("boom")):
            result = await agent._execute_delegation("sales", "task", {})
        assert "Delegation failed" in result

    def test_skill_injection_disabled(self):
        agent = make_agent()
        with patch("core.hallucination_config.is_skill_injection_enabled",
                   return_value=False):
            assert agent._retrieve_skill_instructions("request") == ""

    def test_skill_injection_success(self):
        agent = make_agent()
        svc = MagicMock()
        svc.retrieve_top_skills.return_value = "SKILLS BLOCK"
        with patch("core.hallucination_config.is_skill_injection_enabled",
                   return_value=True), \
             patch("core.skill_retrieval_service.get_skill_retrieval_service",
                   return_value=svc), \
             patch("core.atom_meta_agent.SessionLocal") as sl:
            sl.return_value.__enter__.return_value = MagicMock()
            assert agent._retrieve_skill_instructions("request") == "SKILLS BLOCK"

    def test_skill_injection_exception(self):
        agent = make_agent()
        with patch("core.hallucination_config.is_skill_injection_enabled",
                   side_effect=RuntimeError("boom")):
            assert agent._retrieve_skill_instructions("request") == ""

    async def test_budget_check_allowed(self):
        agent = make_agent()
        with patch("core.budget_enforcement_service.BudgetEnforcementService") as cls:
            cls.return_value.__enter__.return_value.check_budget_before_action = \
                AsyncMock(return_value={"allowed": True, "reason": "ok"})
            result = await agent._check_budget_before_react()
        assert result["allowed"] is True

    async def test_budget_check_denied(self):
        agent = make_agent()
        with patch("core.budget_enforcement_service.BudgetEnforcementService") as cls:
            cls.return_value.__enter__.return_value.check_budget_before_action = \
                AsyncMock(return_value={"allowed": False, "reason": "over"})
            result = await agent._check_budget_before_react()
        assert result["allowed"] is False

    async def test_budget_check_fail_open(self):
        agent = make_agent()
        with patch("core.budget_enforcement_service.BudgetEnforcementService",
                   side_effect=RuntimeError("budget down")):
            result = await agent._check_budget_before_react()
        assert result["allowed"] is True
        assert result["enforcement_mode"] == "unknown"


# ---------------------------------------------------------------------------
# reasoning-step persistence
# ---------------------------------------------------------------------------


class TestPersistReasoningStep:
    def test_success(self):
        agent = make_agent()
        db = MagicMock()
        db_step = SimpleNamespace(id="step-1")
        db.add = MagicMock()
        db.commit = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        extractor = MagicMock()
        extractor.extract_from_turn = AsyncMock()
        with patch("core.atom_meta_agent.SessionLocal", return_value=db), \
             patch("core.atom_meta_agent.AgentReasoningStep", lambda **kw: db_step), \
             patch("core.atom_meta_agent.get_turn_fact_extractor",
                   return_value=extractor), \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", True):
            step_id = agent._persist_reasoning_step(
                "ex-1", 1, "thought", "thinking", {"tool": "t"}, "obs",
                0.9, "verified", "evidence", 12.5, "request",
                "final", {"session_id": "s", "user_id": "u"})
        assert step_id == "step-1"
        db.add.assert_called_once()

    def test_turn_fact_disabled(self):
        agent = make_agent()
        db = MagicMock()
        db_step = SimpleNamespace(id="step-2")
        db.add = MagicMock()
        db.commit = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        with patch("core.atom_meta_agent.SessionLocal", return_value=db), \
             patch("core.atom_meta_agent.AgentReasoningStep", lambda **kw: db_step), \
             patch("core.atom_meta_agent.get_turn_fact_extractor") as gte, \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False):
            step_id = agent._persist_reasoning_step(
                "ex-1", 1, "thought", "thinking", None, None,
                0.9, "verified", None, 1.0, "request", None, None,
                dispatch_turn_fact=True)
        assert step_id == "step-2"
        gte.assert_not_called()

    def test_exception_returns_empty(self):
        agent = make_agent()
        with patch("core.atom_meta_agent.SessionLocal",
                   side_effect=RuntimeError("db down")):
            assert agent._persist_reasoning_step(
                "ex-1", 1, "t", "th", None, None, 0.9, "v", None, 1.0,
                "r", None, None) == ""


# ---------------------------------------------------------------------------
# communication instruction
# ---------------------------------------------------------------------------


class TestCommunicationInstruction:
    def test_no_user_id(self):
        agent = make_agent()
        assert agent._get_communication_instruction({}) == ""

    def test_no_personalization(self):
        agent = make_agent()
        user = SimpleNamespace(metadata_json={"communication_style": {}})
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = user
        db.close = MagicMock()
        with patch("core.atom_meta_agent.SessionLocal", return_value=db):
            assert agent._get_communication_instruction({"user_id": "u1"}) == ""
        db.close.assert_called_once()

    def test_with_style_guide(self):
        agent = make_agent()
        user = SimpleNamespace(metadata_json={
            "communication_style": {"enable_personalization": True,
                                    "style_guide": "Be concise."}})
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = user
        db.close = MagicMock()
        with patch("core.atom_meta_agent.SessionLocal", return_value=db):
            result = agent._get_communication_instruction({"user_id": "u1"})
        assert "COMMUNICATION STYLE" in result
        assert "Be concise." in result

    def test_exception_returns_empty(self):
        agent = make_agent()
        with patch("core.atom_meta_agent.SessionLocal",
                   side_effect=RuntimeError("db down")):
            assert agent._get_communication_instruction({"user_id": "u1"}) == ""

    def test_user_object_fallback(self):
        agent = make_agent(user=SimpleNamespace(id="u-self"))
        assert agent._get_communication_instruction({}) == ""


# ---------------------------------------------------------------------------
# governance-gated routing
# ---------------------------------------------------------------------------


class TestGovernanceRouting:
    async def test_check_governance_allowed(self):
        agent = make_agent()
        gov = MagicMock()
        gov.canPerformAction = AsyncMock(
            return_value=SimpleNamespace(allowed=True, reason=None))
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        with patch("core.atom_meta_agent.SessionLocal", return_value=db), \
             patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            allowed, reason = await agent._check_governance("u1", "ag-1", "workflow")
        assert allowed is True
        assert reason is None

    async def test_check_governance_denied(self):
        agent = make_agent()
        gov = MagicMock()
        gov.canPerformAction = AsyncMock(
            return_value=SimpleNamespace(allowed=False, reason="maturity"))
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        with patch("core.atom_meta_agent.SessionLocal", return_value=db), \
             patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            allowed, reason = await agent._check_governance("u1", "ag-1", "task")
        assert allowed is False
        assert reason == "maturity"

    async def test_route_chat_bypasses_governance(self):
        agent = make_agent()
        agent.llm.generate_response = AsyncMock(return_value="hello!")
        result = await agent.route_with_governance(
            "hi", _intent(IntentCategory.CHAT), "u1")
        assert result["route"] == "CHAT"
        assert result["governance_checked"] is False
        assert result["decision_id"]

    async def test_route_workflow_denied_proposes_chat(self):
        agent = make_agent()
        agent.llm.generate_response = AsyncMock(return_value="proposal text")
        with patch.object(agent, "_check_governance",
                          new=AsyncMock(return_value=(False, "intern required"))):
            result = await agent.route_with_governance(
                "run payroll", _intent(IntentCategory.WORKFLOW), "u1")
        assert result["route"] == "CHAT"
        assert result["auto_takeover"] is True
        assert result["governance_allowed"] is False
        assert result["denial_reason"] == "intern required"

    async def test_route_workflow_allowed(self):
        agent = make_agent()
        queen = MagicMock()
        queen.generate_blueprint = AsyncMock(return_value={
            "blueprint_id": "bp-1", "architecture_name": "arch",
            "nodes": [{"id": "n1"}]})
        agent.queen = queen
        with patch.object(agent, "_check_governance",
                          new=AsyncMock(return_value=(True, None))), \
             patch("core.atom_meta_agent.SessionLocal") as sl:
            sl.return_value.__enter__.return_value = MagicMock()
            result = await agent.route_with_governance(
                "run payroll", _intent(IntentCategory.WORKFLOW), "u1")
        assert result["route"] == "WORKFLOW"
        assert result["blueprint_id"] == "bp-1"
        assert result["node_count"] == 1
        assert result["governance_allowed"] is True

    async def test_route_task_allowed(self):
        agent = make_agent()
        admiral = MagicMock()
        admiral.recruit_and_execute = AsyncMock(return_value={
            "chain_id": "ch-1", "specialists_count": 2})
        with patch.object(agent, "_check_governance",
                          new=AsyncMock(return_value=(True, None))), \
             patch("core.fleet_admiral.FleetAdmiral", return_value=admiral), \
             patch("core.atom_meta_agent.SessionLocal") as sl:
            sl.return_value.__enter__.return_value = MagicMock()
            result = await agent.route_with_governance(
                "analyze leads", _intent(IntentCategory.TASK), "u1")
        assert result["route"] == "TASK"
        assert result["chain_id"] == "ch-1"
        assert result["specialists_count"] == 2

    async def test_route_to_chat(self):
        agent = make_agent()
        agent.llm.generate_response = AsyncMock(return_value="hi back")
        result = await agent._route_to_chat("hello", "u1")
        assert result["route"] == "CHAT"
        assert result["status"] == "chat_complete"
        assert result["response"] == "hi back"

    async def test_route_to_workflow_lazy_queen(self):
        agent = make_agent()
        queen = MagicMock()
        queen.generate_blueprint = AsyncMock(return_value={
            "blueprint_id": "bp-2", "architecture_name": "a", "nodes": []})
        with patch("core.atom_meta_agent.QueenAgent", return_value=queen), \
             patch("core.atom_meta_agent.SessionLocal") as sl:
            sl.return_value.__enter__.return_value = MagicMock()
            result = await agent._route_to_workflow("goal", "u1")
        assert result["status"] == "blueprint_generated"
        assert agent.queen is queen  # lazy init cached

    async def test_propose_chat_alternative(self):
        agent = make_agent()
        agent.llm.generate_response = AsyncMock(return_value="try chat instead")
        result = await agent._propose_chat_alternative(
            "run x", "workflow", "intern required", "u1")
        assert result["auto_takeover"] is True
        assert result["original_route"] == "workflow"
        assert result["proposal"] == "try chat instead"
        assert "intern required" in result["denial_reason"]


# ---------------------------------------------------------------------------
# record execution + module functions
# ---------------------------------------------------------------------------


class TestRecordExecution:
    async def test_success(self):
        agent = make_agent()
        agent.world_model.record_experience = AsyncMock()
        gov = MagicMock()
        gov.record_outcome = AsyncMock()
        db = MagicMock()
        db.close = MagicMock()
        with patch("core.atom_meta_agent.SessionLocal", return_value=db), \
             patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov), \
             patch("core.atom_meta_agent.AgentExperience",
                   lambda **kw: SimpleNamespace(**kw)):
            await agent._record_execution(
                "request", {"status": "success", "final_output": "out",
                            "actions_executed": [1, 2]},
                SimpleNamespace(value="manual"))
        agent.world_model.record_experience.assert_called_once()
        gov.record_outcome.assert_called_once()

    async def test_governance_error_tolerated(self):
        agent = make_agent()
        agent.world_model.record_experience = AsyncMock()
        db = MagicMock()
        db.close = MagicMock()
        with patch("core.atom_meta_agent.SessionLocal", return_value=db), \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   side_effect=RuntimeError("gov down")), \
             patch("core.atom_meta_agent.AgentExperience",
                   lambda **kw: SimpleNamespace(**kw)):
            await agent._record_execution(
                "request", {"final_output": "partial"}, SimpleNamespace(value="x"))


class TestDataEventTrigger:
    async def test_queue_disabled_inline(self):
        q = MagicMock()
        q.enabled = False
        with patch("core.task_queue.get_task_queue", return_value=q), \
             patch.object(AtomMetaAgent, "execute",
                          new=AsyncMock(return_value={"status": "done"})) as ex:
            result = await handle_data_event_trigger("lead.created", {"x": 1})
        assert result == {"status": "done"}
        ex.assert_called_once()

    async def test_queue_enabled_returns_task_id(self):
        q = MagicMock()
        q.enabled = True
        q.enqueue_job.return_value = "job-1"
        with patch("core.task_queue.get_task_queue", return_value=q):
            result = await handle_data_event_trigger("lead.created", {"x": 1})
        assert result["status"] == "queued"
        assert result["task_id"] == "job-1"

    async def test_queue_exception_falls_back_inline(self):
        with patch("core.task_queue.get_task_queue",
                   side_effect=RuntimeError("redis down")), \
             patch.object(AtomMetaAgent, "execute",
                          new=AsyncMock(return_value={"status": "done"})):
            result = await handle_data_event_trigger("lead.created", {})
        assert result["status"] == "done"


class TestSingleton:
    def test_get_atom_agent(self):
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
            a1 = get_atom_agent()
            a2 = get_atom_agent()
            assert a1 is a2
            # different workspace → new instance
            from core.atom_meta_agent import _atom_instance
            _atom_instance = None
            a3 = get_atom_agent("other")
            assert a3 is not a1


# ---------------------------------------------------------------------------
# wave-30b — _react_step + memory assembly (mocked llm)
# ---------------------------------------------------------------------------


class TestReactStep:
    async def test_structured_result(self):
        agent = make_agent()
        step = ReActStep(thought="think", final_answer="done")
        agent.llm.generate_structured_response = AsyncMock(return_value=step)
        agent.llm.generate_completion = AsyncMock()
        result = await agent._react_step(
            "request", {}, "tools", "", {}, turn_index=0)
        assert result is step
        agent.llm.generate_completion.assert_not_called()

    async def test_fallback_completion_error(self):
        agent = make_agent()
        agent.llm.generate_structured_response = AsyncMock(return_value=None)
        agent.llm.generate_completion = AsyncMock(
            return_value={"content": "AI provider not initialized"})
        result = await agent._react_step("request", {}, "tools", "", {})
        assert "issue or restriction" in result.thought

    async def test_fallback_completion_plain(self):
        agent = make_agent()
        agent.llm.generate_structured_response = AsyncMock(return_value=None)
        agent.llm.generate_completion = AsyncMock(
            return_value={"content": "Here is the answer"})
        result = await agent._react_step("request", {}, "tools", "", {})
        assert result.final_answer == "Here is the answer"

    async def test_memory_sections_assembled(self):
        agent = make_agent()
        agent.llm.generate_structured_response = AsyncMock(
            return_value=ReActStep(thought="t", final_answer="ok"))
        fact = SimpleNamespace(verification_status="verified", fact="F",
                               metadata={"source": "s"})
        durable = [SimpleNamespace(category="policy", fact_text="Durable fact")]
        memory_context = {
            "experiences": [SimpleNamespace(input_summary="exp", outcome="success")],
            "canvas_episodes": [{"canvas_id": "cv-12345678", "task_description": "task",
                                 "outcome": "success", "canvas_boost": 0.5}],
            "knowledge": [{"text": "doc text"}],
            "formulas": [{"name": "F1", "description": "formula desc"}],
            "business_facts": [fact],
        }
        with patch("core.atom_meta_agent.SessionLocal") as sl, \
             patch("core.atom_meta_agent._get_active_facts_for_prompt",
                   return_value=durable):
            sl.return_value.__enter__.return_value = MagicMock()
            result = await agent._react_step(
                "request", memory_context, "tools", "hist",
                {"_field_guide_context": "FIELD GUIDE TEXT",
                 "prefetched_facts": [{"fact_text": "semantic fact"}]})
        assert result.final_answer == "ok"
        prompt = agent.llm.generate_structured_response.call_args.kwargs["prompt"]
        assert "PAST EXPERIENCES" in prompt
        assert "CANVAS EPISODES" in prompt
        assert "TRUSTED BUSINESS FACTS" in prompt
        assert "DURABLE FACTS" in prompt
        assert "FIELD GUIDE TEXT" in prompt
        assert "SEMANTICALLY RELATED FACTS" in prompt

    async def test_prefetched_facts_string_entries(self):
        agent = make_agent()
        agent.llm.generate_structured_response = AsyncMock(
            return_value=ReActStep(thought="t", final_answer="ok"))
        with patch("core.atom_meta_agent.SessionLocal") as sl, \
             patch("core.atom_meta_agent._get_active_facts_for_prompt",
                   return_value=[]):
            sl.return_value.__enter__.return_value = MagicMock()
            await agent._react_step(
                "request", {}, "tools", "",
                {"prefetched_facts": ["plain string fact"]})
        prompt = agent.llm.generate_structured_response.call_args.kwargs["prompt"]
        assert "plain string fact" in prompt

    async def test_durable_facts_failure_tolerated(self):
        agent = make_agent()
        agent.llm.generate_structured_response = AsyncMock(
            return_value=ReActStep(thought="t", final_answer="ok"))
        with patch("core.atom_meta_agent.SessionLocal",
                   side_effect=RuntimeError("db down")):
            result = await agent._react_step("request", {}, "tools", "", {})
        assert result.final_answer == "ok"

    async def test_skill_instructions_injected(self):
        agent = make_agent()
        agent.llm.generate_structured_response = AsyncMock(
            return_value=ReActStep(thought="t", final_answer="ok"))
        with patch.object(agent, "_retrieve_skill_instructions",
                          return_value="SKILL: web_search"), \
             patch("core.atom_meta_agent.SessionLocal") as sl, \
             patch("core.atom_meta_agent._get_active_facts_for_prompt",
                   return_value=[]):
            sl.return_value.__enter__.return_value = MagicMock()
            await agent._react_step("request", {}, "tools", "", {})
        prompt = agent.llm.generate_structured_response.call_args.kwargs[
            "system_instruction"]
        assert "SKILL: web_search" in prompt
