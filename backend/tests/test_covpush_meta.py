"""Coverage-push tests for core/atom_meta_agent.py (TDD bug-hunt included)."""

import os

os.environ["TESTING"] = "1"

import asyncio
import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from core.atom_meta_agent import (
    AtomMetaAgent,
    IntentCategory,
    IntentClassification,
    ReActStep,
    SpecialtyAgentTemplate,
    ToolCall,
    _is_error_observation,
    _meta_agent_sandbox_check,
    get_atom_agent,
    handle_data_event_trigger,
    handle_manual_trigger,
)
from core.models import AgentTriggerMode, AgentStatus


def _route_cls(category=IntentCategory.CHAT):
    return IntentClassification(
        category=category, confidence=0.9, reasoning="r",
        requires_execution=category != IntentCategory.CHAT,
        suggested_handler="llm_service",
        is_structured=False, is_long_horizon=False,
    )


@pytest.fixture
def fake_business_agents(monkeypatch):
    import sys
    import types
    mod = types.ModuleType("core.business_agents")
    mod.get_specialized_agent = lambda name, workspace_id: None
    sys.modules["core.business_agents"] = mod
    yield mod
    sys.modules.pop("core.business_agents", None)


@pytest.fixture
def meta_agent(monkeypatch):
    """AtomMetaAgent with all heavy services patched."""
    import core.atom_meta_agent as ama

    wm = MagicMock()
    monkeypatch.setattr(ama, "WorldModelService", MagicMock(return_value=wm))
    monkeypatch.setattr(ama, "AdvancedWorkflowOrchestrator", MagicMock())
    monkeypatch.setattr(ama, "CapabilityGraduationService", MagicMock())
    monkeypatch.setattr(ama, "get_canvas_provider", MagicMock(return_value=MagicMock()))
    monkeypatch.setattr(ama, "mcp_service", MagicMock())
    monkeypatch.setattr(ama, "AgentGovernanceService", MagicMock())
    monkeypatch.setattr(ama, "AgentFleetService", MagicMock())
    monkeypatch.setattr(ama, "FleetOptimizationService", MagicMock())
    monkeypatch.setattr(ama, "_TURN_FACT_VECTOR_RECALL_ENABLED", False)
    monkeypatch.setattr(ama, "_TURN_FACT_EXTRACTION_ENABLED", False)

    sl = MagicMock()
    sl.return_value.__enter__.return_value = MagicMock()
    monkeypatch.setattr(ama, "SessionLocal", sl)

    sf = MagicMock()
    sf.get_llm_service.return_value = MagicMock()
    monkeypatch.setattr("core.service_factory.ServiceFactory", sf)

    agent = ama.AtomMetaAgent()
    agent.llm = MagicMock()
    agent.world_model = wm
    return agent, sl


def _prepare_execute(agent, sl, monkeypatch, *, route_category=None, tools=None):
    import core.atom_meta_agent as ama
    from ai.nlp_engine import NaturalLanguageEngine, RouteCategory, RouteClassification

    workspace = SimpleNamespace(tenant_id="default")
    db = sl.return_value.__enter__.return_value
    db.query.return_value.filter.return_value.first.return_value = workspace

    nlu = MagicMock()
    nlu.classify_route = AsyncMock(return_value=RouteClassification(
        category=route_category or RouteCategory.ONE_OFF,
        reasoning="r", confidence=0.9,
    ))
    monkeypatch.setattr(ama, "NaturalLanguageEngine", MagicMock(return_value=nlu))

    agent.world_model.recall_experiences = AsyncMock(return_value={"experiences": []})
    agent.mcp.get_all_tools = AsyncMock(return_value=tools or [
        {"name": "trigger_workflow", "description": "d", "parameters": {}},
    ])
    monkeypatch.setattr("core.field_guide_service.get_field_guide_service",
                        lambda: MagicMock(get_field_guide_context=lambda w: "guide"))
    agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
    agent._persist_reasoning_step = MagicMock(return_value="step-id")
    agent._record_execution = AsyncMock()
    return nlu


class TestIsErrorObservation:
    def test_error_markers_detected(self):
        assert _is_error_observation("Tool error. something")
        assert _is_error_observation("governance blocked: x")
        assert _is_error_observation("sandbox blocked")
        assert _is_error_observation("was rejected")

    def test_none_and_normal(self):
        assert not _is_error_observation(None)
        assert not _is_error_observation("all good")
        assert not _is_error_observation("")

    def test_case_insensitive(self):
        assert _is_error_observation("TOOL EXECUTION FAILED")


class TestModels:
    def test_tool_call_model(self):
        tc = ToolCall(tool="x", params={"a": 1})
        assert tc.tool == "x"
        assert tc.params == {"a": 1}
        empty = ToolCall(tool="y")
        assert empty.params == {}

    def test_react_step_model(self):
        step = ReActStep(thought="t", final_answer="f")
        assert step.final_answer == "f"
        assert step.confidence == 0.9

    def test_intent_classification_model(self):
        ic = IntentClassification(
            category=IntentCategory.TASK, confidence=0.5, reasoning="r",
            requires_execution=True, suggested_handler="fleet_admiral",
        )
        assert ic.category == IntentCategory.TASK
        assert ic.is_structured is False
        assert ic.suggested_handler == "fleet_admiral"
        assert ic.requires_execution is True

    def test_templates(self):
        assert "king_agent" in SpecialtyAgentTemplate.TEMPLATES
        assert SpecialtyAgentTemplate.TEMPLATES["king_agent"]["class_name"] == "KingAgent"


class TestInitAndSimple:
    def test_init_defaults(self, meta_agent):
        agent, _ = meta_agent
        assert agent.workspace_id == "default"
        assert agent.tenant_id == "default"
        assert agent.spawned_agents == {}
        assert agent.queen is None

    @pytest.mark.asyncio
    async def test_execute_simple_final_answer(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))

        result = await agent.execute("hi there", context={"user_id": "u1"})

        assert result["status"] == "success"
        assert result["final_output"] == "done"
        assert result["failure_reason"] is None
        assert result["actions_executed"]

    @pytest.mark.asyncio
    async def test_execute_sets_original_request(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="ok"))

        await agent.execute("please do the thing", context={})

        assert agent._react_step.call_args.kwargs["context"]["original_request"] == "please do the thing"

    @pytest.mark.asyncio
    async def test_execute_workspace_not_found(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        db = sl.return_value.__enter__.return_value
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException):
            await agent.execute("hello")

    @pytest.mark.asyncio
    async def test_execute_no_action_converts_thought(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        agent._react_step = AsyncMock(return_value=ReActStep(thought="just thinking", action=None))

        result = await agent.execute("hello")

        assert result["final_output"] == "just thinking"
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_execute_empty_thought_fallback(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        agent._react_step = AsyncMock(return_value=ReActStep(thought="", action=None))

        result = await agent.execute("hello")

        assert "unable to proceed" in result["final_output"].lower()

    @pytest.mark.asyncio
    async def test_execute_max_steps_timeout(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        agent._react_step = AsyncMock(
            return_value=ReActStep(thought="t", action=ToolCall(tool="some_tool", params={}))
        )
        agent._execute_tool_with_governance = AsyncMock(return_value="observation")

        result = await agent.execute("hello")

        assert result["status"] == "timeout"
        assert "Maximum reasoning steps" in result["final_output"]

    @pytest.mark.asyncio
    async def test_execute_budget_exceeded(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        agent._check_budget_before_react = AsyncMock(
            return_value={"allowed": False, "reason": "over budget", "enforcement_mode": "hard_stop"}
        )
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="unused"))

        result = await agent.execute("hello")

        assert result["status"] == "budget_exceeded"
        assert result["failure_reason"] == "over budget"
        assert result["failure_mode"] == "hard_stop"

    @pytest.mark.asyncio
    async def test_execute_step_callback_receives_steps(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))
        seen = []

        async def cb(record):
            seen.append(record)

        await agent.execute("hello", step_callback=cb)

        assert seen
        assert seen[0]["execution_id"]

    @pytest.mark.asyncio
    async def test_execute_mcp_tool_search_action(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        agent._react_step = AsyncMock(side_effect=[
            ReActStep(thought="t", action=ToolCall(tool="mcp_tool_search", params={"query": "q"})),
            ReActStep(thought="t", final_answer="done"),
        ])
        agent.mcp.search_tools = AsyncMock(return_value=[
            {"name": "new_tool", "description": "d", "parameters": {}}
        ])

        result = await agent.execute("hello")

        assert result["status"] == "success"
        assert any(t["name"] == "new_tool" for t in agent.session_tools)

    @pytest.mark.asyncio
    async def test_execute_mcp_tool_search_dedup(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        agent.session_tools = [{"name": "dup_tool", "description": "d", "parameters": {}}]
        _prepare_execute(agent, sl, monkeypatch)
        agent._react_step = AsyncMock(side_effect=[
            ReActStep(thought="t", action=ToolCall(tool="mcp_tool_search", params={"query": "q"})),
            ReActStep(thought="t", final_answer="done"),
        ])
        agent.mcp.search_tools = AsyncMock(return_value=[
            {"name": "dup_tool", "description": "d", "parameters": {}}
        ])

        await agent.execute("hello")

        assert len(agent.session_tools) == 1

    @pytest.mark.asyncio
    async def test_execute_delegate_task_action(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        agent._react_step = AsyncMock(side_effect=[
            ReActStep(thought="t", action=ToolCall(tool="delegate_task", params={"agent_name": "sales", "task": "x"})),
            ReActStep(thought="t", final_answer="done"),
        ])
        agent._execute_delegation = AsyncMock(return_value="delegation result")

        result = await agent.execute("hello")

        assert result["status"] == "success"
        agent._execute_delegation.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_regular_tool_observation_critique(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        agent._react_step = AsyncMock(side_effect=[
            ReActStep(thought="t", action=ToolCall(tool="some_tool", params={})),
            ReActStep(thought="t", final_answer="done"),
        ])
        agent._execute_tool_with_governance = AsyncMock(return_value="Tool error. something broke")

        result = await agent.execute("hello")

        assert result["status"] == "success"
        history = " ".join(s.get("thought", "") for s in result["actions_executed"])

    @pytest.mark.asyncio
    async def test_execute_parallel_tools_branch(self, meta_agent, monkeypatch):
        import core.atom_meta_agent as ama
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled", lambda: True)
        agent._react_step = AsyncMock(side_effect=[
            ReActStep(thought="t", actions=[ToolCall(tool="a", params={}), ToolCall(tool="b", params={})]),
            ReActStep(thought="t", final_answer="done"),
        ])
        agent._execute_parallel_tools = AsyncMock(return_value=[
            {"tool_name": "a", "params": {}, "output": "oa", "verified_kind": "unverified", "verified_evidence": None},
            {"tool_name": "b", "params": {}, "output": "ob", "verified_kind": "unverified", "verified_evidence": None},
        ])

        result = await agent.execute("hello")

        assert result["status"] == "success"
        assert len(result["actions_executed"]) == 3

    @pytest.mark.asyncio
    async def test_execute_parallel_tools_critique_output(self, meta_agent, monkeypatch):
        import core.atom_meta_agent as ama
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled", lambda: True)
        agent._react_step = AsyncMock(side_effect=[
            ReActStep(thought="t", actions=[ToolCall(tool="a", params={})]),
            ReActStep(thought="t", final_answer="done"),
        ])
        agent._execute_parallel_tools = AsyncMock(return_value=[
            {"tool_name": "a", "params": {}, "output": "Tool error. x", "verified_kind": "unverified", "verified_evidence": None},
        ])

        await agent.execute("hello")

    @pytest.mark.asyncio
    async def test_execute_parallel_disabled_promote_first(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled", lambda: False)
        agent._react_step = AsyncMock(side_effect=[
            ReActStep(thought="t", actions=[ToolCall(tool="only_tool", params={})]),
            ReActStep(thought="t", final_answer="done"),
        ])
        agent._execute_tool_with_governance = AsyncMock(return_value="ok")

        result = await agent.execute("hello")

        assert result["status"] == "success"
        args = agent._execute_tool_with_governance.call_args
        assert args.args[0] == "only_tool"

    @pytest.mark.asyncio
    async def test_execute_queen_planning_automation(self, meta_agent, monkeypatch):
        import core.atom_meta_agent as ama
        from ai.nlp_engine import RouteCategory
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch, route_category=RouteCategory.AUTOMATION)
        queen = MagicMock()
        queen.generate_blueprint = AsyncMock(return_value={
            "architecture_name": "Blue",
            "nodes": [{"name": "n1", "type": "agent", "capability_required": "c"}],
            "missing_capabilities": [{"name": "mc"}],
        })
        agent.queen = queen
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))

        result = await agent.execute("analyze the market deeply today")

        assert result["status"] == "success"
        queen.generate_blueprint.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_queen_planning_creates_queen(self, meta_agent, monkeypatch):
        import core.atom_meta_agent as ama
        from ai.nlp_engine import RouteCategory
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch, route_category=RouteCategory.AUTOMATION)
        queen = MagicMock()
        queen.generate_blueprint = AsyncMock(return_value={
            "architecture_name": "Blue", "nodes": [{"name": "n1", "type": "agent"}],
        })
        sf = MagicMock()
        sf.get_queen_agent.return_value = queen
        monkeypatch.setattr("core.service_factory.ServiceFactory", sf)
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))

        await agent.execute("analyze the market deeply today")

        assert agent.queen is queen

    @pytest.mark.asyncio
    async def test_execute_queen_failure_falls_back(self, meta_agent, monkeypatch):
        import core.atom_meta_agent as ama
        from ai.nlp_engine import RouteCategory
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch, route_category=RouteCategory.AUTOMATION)
        queen = MagicMock()
        queen.generate_blueprint = AsyncMock(side_effect=Exception("llm down"))
        agent.queen = queen
        agent.orchestrator.generate_dynamic_workflow = AsyncMock(
            return_value={"nodes": [{"name": "n1"}]}
        )
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))

        result = await agent.execute("analyze the market deeply today")

        assert result["status"] == "success"
        agent.orchestrator.generate_dynamic_workflow.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_canvas_context(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        canvas_provider = agent.canvas_provider
        canvas_state = SimpleNamespace(
            canvas_id="c1", artifact_count=2,
            comments=[SimpleNamespace(content="note")],
        )
        canvas_provider.get_canvas_context = AsyncMock(return_value=canvas_state)
        canvas_provider.format_for_agent = MagicMock(return_value="canvas text")
        agent.world_model.recall_episodes = AsyncMock(return_value=[
            {"canvas_id": "c1", "task_description": "t", "outcome": "completed", "canvas_boost": 0.5}
        ])
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))

        result = await agent.execute(
            "hello", canvas_context={"canvas_id": "c1"}, context={"user_id": "u1"}
        )

        assert result["status"] == "success"
        canvas_provider.get_canvas_context.assert_awaited_once()
        agent.world_model.recall_episodes.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_canvas_failure_finalizes_failed(self, meta_agent, monkeypatch):
        import core.atom_meta_agent as ama
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        canvas_provider = agent.canvas_provider
        canvas_provider.get_canvas_context = AsyncMock(side_effect=Exception("canvas boom"))
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))

        with pytest.raises(Exception):
            await agent.execute("hello", canvas_context={"canvas_id": "c1"})


class TestDelegation:
    @pytest.mark.asyncio
    async def test_delegate_success(self, meta_agent, fake_business_agents):
        agent, _ = meta_agent
        sub = MagicMock()
        sub.name = "Sales"
        sub.execute = AsyncMock(return_value={"final_output": "done"})
        fake_business_agents.get_specialized_agent = lambda n, w: sub

        result = await agent._execute_delegation("sales", "task", {})

        assert "Sales" in result
        assert "done" in result

    @pytest.mark.asyncio
    async def test_delegate_not_found(self, meta_agent, fake_business_agents):
        agent, _ = meta_agent
        fake_business_agents.get_specialized_agent = lambda n, w: None

        result = await agent._execute_delegation("ghost", "task", {})

        assert "not found" in result

    @pytest.mark.asyncio
    async def test_delegate_exception(self, meta_agent, fake_business_agents):
        agent, _ = meta_agent
        fake_business_agents.get_specialized_agent = (
            lambda n, w: (_ for _ in ()).throw(Exception("boom"))
        )

        result = await agent._execute_delegation("sales", "task", {})

        assert result == "Delegation failed. Please try again."


class TestSkillRetrievalAndBudget:
    @pytest.mark.asyncio
    async def test_retrieve_skill_instructions_disabled(self, meta_agent, monkeypatch):
        agent, _ = meta_agent
        monkeypatch.setattr("core.hallucination_config.is_skill_injection_enabled", lambda: False)
        assert agent._retrieve_skill_instructions("query") == ""

    @pytest.mark.asyncio
    async def test_retrieve_skill_instructions_enabled(self, meta_agent, monkeypatch):
        agent, _ = meta_agent
        monkeypatch.setattr("core.hallucination_config.is_skill_injection_enabled", lambda: True)
        svc = MagicMock()
        svc.retrieve_top_skills.return_value = "use the skill"
        monkeypatch.setattr("core.skill_retrieval_service.get_skill_retrieval_service", lambda: svc)

        assert agent._retrieve_skill_instructions("query") == "use the skill"

    @pytest.mark.asyncio
    async def test_retrieve_skill_instructions_exception(self, meta_agent, monkeypatch):
        agent, _ = meta_agent
        monkeypatch.setattr("core.hallucination_config.is_skill_injection_enabled", lambda: True)
        monkeypatch.setattr("core.skill_retrieval_service.get_skill_retrieval_service",
                            lambda: (_ for _ in ()).throw(Exception("boom")))

        assert agent._retrieve_skill_instructions("query") == ""

    @pytest.mark.asyncio
    async def test_check_budget_allowed(self, meta_agent, monkeypatch):
        agent, _ = meta_agent
        svc = MagicMock()
        svc.check_budget_before_action = AsyncMock(return_value={"allowed": True})
        ctx = MagicMock()
        ctx.__enter__.return_value = svc
        monkeypatch.setattr("core.budget_enforcement_service.BudgetEnforcementService", lambda: ctx)

        result = await agent._check_budget_before_react()

        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_check_budget_fail_open(self, meta_agent, monkeypatch):
        agent, _ = meta_agent
        monkeypatch.setattr("core.budget_enforcement_service.BudgetEnforcementService",
                            lambda: (_ for _ in ()).throw(Exception("db down")))

        result = await agent._check_budget_before_react()

        assert result == {"allowed": True, "reason": "budget-check-error", "enforcement_mode": "unknown"}


class TestReactStep:
    @pytest.mark.asyncio
    async def test_react_step_structured_result(self, meta_agent):
        agent, _ = meta_agent
        agent.llm.generate_structured_response = AsyncMock(return_value=ReActStep(thought="t", final_answer="f"))
        agent._get_communication_instruction = MagicMock(return_value="")
        agent._retrieve_skill_instructions = MagicMock(return_value="")

        step = await agent._react_step("req", {}, "tools", "", {}, canvas_text="canvas")

        assert step.final_answer == "f"

    @pytest.mark.asyncio
    async def test_react_step_fallback_error_response(self, meta_agent):
        agent, _ = meta_agent
        agent.llm.generate_structured_response = AsyncMock(return_value=None)
        agent.llm.generate_completion = AsyncMock(return_value={"content": "No eligible provider"})
        agent._get_communication_instruction = MagicMock(return_value="")
        agent._retrieve_skill_instructions = MagicMock(return_value="")

        step = await agent._react_step("req", {}, "tools", "", {})

        assert "issue or restriction" in step.thought
        assert step.final_answer == "No eligible provider"

    @pytest.mark.asyncio
    async def test_react_step_fallback_empty_response(self, meta_agent):
        agent, _ = meta_agent
        agent.llm.generate_structured_response = AsyncMock(return_value=None)
        agent.llm.generate_completion = AsyncMock(return_value={"content": None})
        agent._get_communication_instruction = MagicMock(return_value="")
        agent._retrieve_skill_instructions = MagicMock(return_value="")

        step = await agent._react_step("req", {}, "tools", "", {})

        assert "AI provider unavailable" in step.final_answer

    @pytest.mark.asyncio
    async def test_react_step_fallback_plain_answer(self, meta_agent):
        agent, _ = meta_agent
        agent.llm.generate_structured_response = AsyncMock(return_value=None)
        agent.llm.generate_completion = AsyncMock(return_value={"content": "Here is the answer"})
        agent._get_communication_instruction = MagicMock(return_value="")
        agent._retrieve_skill_instructions = MagicMock(return_value="")

        step = await agent._react_step("req", {}, "tools", "", {})

        assert step.final_answer == "Here is the answer"

    @pytest.mark.asyncio
    async def test_react_step_memory_assembly(self, meta_agent, monkeypatch):
        import core.atom_meta_agent as ama
        agent, _ = meta_agent
        exp = SimpleNamespace(input_summary="task", outcome="completed")
        fact = SimpleNamespace(verification_status="verified", fact="f1", metadata={"source": "s"})
        durable = SimpleNamespace(category="pref", fact_text="durable fact")
        agent.llm.generate_structured_response = AsyncMock(return_value=ReActStep(thought="t", final_answer="f"))
        agent._get_communication_instruction = MagicMock(return_value="")
        agent._retrieve_skill_instructions = MagicMock(return_value="")
        monkeypatch.setattr(ama, "_get_active_facts_for_prompt", lambda db, w, limit=5: [durable])

        memory = {
            "experiences": [exp],
            "knowledge": [{"text": "doc"}],
            "formulas": [{"name": "F", "description": "d"}],
            "business_facts": [fact],
            "canvas_episodes": [{"canvas_id": "c1", "task_description": "t", "outcome": "ok", "canvas_boost": 0.5}],
        }
        context = {"_field_guide_context": "guide text", "prefetched_facts": [{"fact_text": "pf"}, "plain"]}

        step = await agent._react_step("req", memory, "tools", "hist", context)

        assert step.final_answer == "f"
        prompt = agent.llm.generate_structured_response.call_args.kwargs["prompt"]
        assert "PAST EXPERIENCES" in prompt
        assert "CANVAS EPISODES" in prompt
        assert "RELEVANT KNOWLEDGE" in prompt
        assert "AVAILABLE FORMULAS" in prompt
        assert "TRUSTED BUSINESS FACTS" in prompt
        assert "DURABLE FACTS" in prompt
        assert "guide text" in prompt
        assert "SEMANTICALLY RELATED FACTS" in prompt

    @pytest.mark.asyncio
    async def test_react_step_memory_empty(self, meta_agent, monkeypatch):
        import core.atom_meta_agent as ama
        agent, _ = meta_agent
        agent.llm.generate_structured_response = AsyncMock(return_value=ReActStep(thought="t", final_answer="f"))
        monkeypatch.setattr(ama, "_get_active_facts_for_prompt", lambda db, w, limit=5: [])
        agent._get_communication_instruction = MagicMock(return_value="")
        agent._retrieve_skill_instructions = MagicMock(return_value="")

        step = await agent._react_step("req", {}, "tools", "", {})

        assert step.final_answer == "f"
        prompt = agent.llm.generate_structured_response.call_args.kwargs["prompt"]
        assert "(No prior context)" in prompt

    @pytest.mark.asyncio
    async def test_react_step_durable_facts_failure(self, meta_agent, monkeypatch):
        import core.atom_meta_agent as ama
        agent, _ = meta_agent
        agent.llm.generate_structured_response = AsyncMock(return_value=ReActStep(thought="t", final_answer="f"))
        agent._get_communication_instruction = MagicMock(return_value="")
        agent._retrieve_skill_instructions = MagicMock(return_value="")
        monkeypatch.setattr(ama, "_get_active_facts_for_prompt",
                            lambda db, w, limit=5: (_ for _ in ()).throw(Exception("db")))

        step = await agent._react_step("req", {}, "tools", "", {})

        assert step.final_answer == "f"


class TestExecuteToolWithGovernance:
    @pytest.mark.asyncio
    async def test_pre_approved_skips_governance(self, meta_agent):
        agent, _ = meta_agent
        agent.mcp.call_tool = AsyncMock(return_value="result")

        result = await agent._execute_tool_with_governance("t", {}, {}, None, pre_approved=True)

        assert result == "result"
        agent.mcp.call_tool.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_governance_blocked(self, meta_agent):
        agent, sl = meta_agent
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={"action_complexity": 1, "allowed": False, "reason": "no"})

        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            result = await agent._execute_tool_with_governance("t", {}, {}, None)

        assert "Governance blocked" in result

    @pytest.mark.asyncio
    async def test_governance_requires_approval_approved(self, meta_agent):
        agent, sl = meta_agent
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={"action_complexity": 2, "allowed": True, "requires_human_approval": False, "reason": ""})
        gov.request_approval.return_value = "action-1"
        from core.atom_meta_agent import AgentGovernanceService
        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            agent._wait_for_approval = AsyncMock(return_value=True)
            agent.mcp.call_tool = AsyncMock(return_value="ok")
            result = await agent._execute_tool_with_governance("t", {"k": "v"}, {}, None)

        assert result == "ok"
        gov.request_approval.assert_called_once()

    @pytest.mark.asyncio
    async def test_governance_requires_approval_rejected(self, meta_agent):
        agent, sl = meta_agent
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={"action_complexity": 2, "allowed": True, "requires_human_approval": False, "reason": "r"})
        gov.request_approval.return_value = "action-1"
        from core.atom_meta_agent import AgentGovernanceService
        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            agent._wait_for_approval = AsyncMock(return_value=False)
            result = await agent._execute_tool_with_governance("t", {}, {}, None)

        assert "REJECTED or timed out" in result

    @pytest.mark.asyncio
    async def test_hitl_callback_emitted(self, meta_agent):
        agent, sl = meta_agent
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={"action_complexity": 2, "allowed": True, "requires_human_approval": False, "reason": "r"})
        gov.request_approval.return_value = "action-1"
        seen = []
        from core.atom_meta_agent import AgentGovernanceService
        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            agent._wait_for_approval = AsyncMock(return_value=True)
            agent.mcp.call_tool = AsyncMock(return_value="ok")

            async def cb(record):
                seen.append(record)

            await agent._execute_tool_with_governance("t", {}, {}, cb)

        assert seen and seen[0]["type"] == "hitl_paused"

    @pytest.mark.asyncio
    async def test_special_tool_trigger_workflow(self, meta_agent):
        agent, _ = meta_agent
        agent._trigger_workflow = AsyncMock(return_value="triggered")
        agent.mcp.call_tool = AsyncMock(return_value="unused")

        result = await agent._execute_tool_with_governance("trigger_workflow", {"workflow_id": "w1", "params": {}}, {}, None, pre_approved=True)

        assert result == "triggered"

    @pytest.mark.asyncio
    async def test_special_tool_delegate(self, meta_agent):
        agent, _ = meta_agent
        agent._execute_delegation = AsyncMock(return_value="delegated")
        result = await agent._execute_tool_with_governance("delegate_task", {"agent_name": "a", "task": "t"}, {}, None, pre_approved=True)
        assert result == "delegated"

    @pytest.mark.asyncio
    async def test_special_tool_recruit_fleet(self, meta_agent):
        agent, _ = meta_agent
        agent._recruit_fleet = AsyncMock(return_value="fleet")
        result = await agent._execute_tool_with_governance(
            "recruit_fleet", {"goal": "g", "sub_tasks": []}, {}, None, pre_approved=True
        )
        assert result == "fleet"

    @pytest.mark.asyncio
    async def test_invoke_capability_student_blocked(self, meta_agent):
        agent, _ = meta_agent
        agent.graduation_service.get_maturity.return_value = "student"
        result = await agent._execute_tool_with_governance("invoke_capability", {"capability_name": "c"}, {}, None, pre_approved=True)
        assert "STUDENT level" in result

    @pytest.mark.asyncio
    async def test_invoke_capability_verified(self, meta_agent):
        agent, _ = meta_agent
        agent.graduation_service.get_maturity.return_value = "intern"
        agent.mcp.call_tool = AsyncMock(return_value=json.dumps({"success": True, "verified": True, "evidence": "row-1"}))
        result = await agent._execute_tool_with_governance("invoke_capability", {"capability_name": "c", "params": {}}, {}, None, pre_approved=True)
        assert "row-1" in result
        agent.graduation_service.record_usage.assert_called_once()

    @pytest.mark.asyncio
    async def test_invoke_capability_unverified_fallback(self, meta_agent):
        agent, _ = meta_agent
        agent.graduation_service.get_maturity.return_value = "intern"
        agent.mcp.call_tool = AsyncMock(return_value="boom")
        agent.graduation_service.record_usage.side_effect = [Exception("parse broke"), None]
        result = await agent._execute_tool_with_governance("invoke_capability", {"capability_name": "c", "params": {}}, {}, None, pre_approved=True)
        assert "boom" in result

    @pytest.mark.asyncio
    async def test_sandbox_enforced_block(self, meta_agent, monkeypatch):
        agent, _ = meta_agent
        decision = SimpleNamespace(requires_review=True, enforced=True, decision="BLOCKED",
                                   violation_detail="fs scope", violation_type="fs")
        monkeypatch.setattr("core.atom_meta_agent._meta_agent_sandbox_check", lambda *a, **k: decision)
        agent.mcp.call_tool = AsyncMock(return_value="unused")
        result = await agent._execute_tool_with_governance("t", {}, {}, None, pre_approved=True)
        assert "Sandbox BLOCKED" in result

    @pytest.mark.asyncio
    async def test_sandbox_shadow_proceeds(self, meta_agent, monkeypatch):
        agent, _ = meta_agent
        decision = SimpleNamespace(requires_review=True, enforced=False, decision="BLOCKED",
                                   violation_type="fs")
        monkeypatch.setattr("core.atom_meta_agent._meta_agent_sandbox_check", lambda *a, **k: decision)
        agent.mcp.call_tool = AsyncMock(return_value="ok")
        result = await agent._execute_tool_with_governance("t", {}, {}, None, pre_approved=True)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_judge_block(self, meta_agent, monkeypatch):
        agent, _ = meta_agent
        monkeypatch.setattr("core.sandbox_config.is_sandbox_judge_enabled", lambda: True)
        judge = MagicMock()
        judge.evaluate = AsyncMock(return_value=SimpleNamespace(verdict="BLOCK", rationale="unsafe"))
        monkeypatch.setattr("core.llm.action_judge.ActionJudge", lambda llm_service: judge)
        monkeypatch.setattr("core.llm.action_judge.JudgeVerdict", type("V", (), {"BLOCK": "BLOCK", "ESCALATE": "ESCALATE"}))
        agent.mcp.call_tool = AsyncMock(return_value="unused")
        result = await agent._execute_tool_with_governance("t", {}, {}, None, pre_approved=True)
        assert "safety judge" in result

    @pytest.mark.asyncio
    async def test_judge_escalate_rejected(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        monkeypatch.setattr("core.sandbox_config.is_sandbox_judge_enabled", lambda: True)
        judge = MagicMock()
        judge.evaluate = AsyncMock(return_value=SimpleNamespace(verdict="ESCALATE", rationale="risky"))
        monkeypatch.setattr("core.llm.action_judge.ActionJudge", lambda llm_service: judge)
        monkeypatch.setattr("core.llm.action_judge.JudgeVerdict", type("V", (), {"BLOCK": "BLOCK", "ESCALATE": "ESCALATE"}))
        gov = MagicMock()
        gov.request_approval.return_value = "action-j"
        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            agent._wait_for_approval = AsyncMock(return_value=False)
            result = await agent._execute_tool_with_governance("t", {}, {}, None, pre_approved=True)
        assert "REJECTED or timed out" in result

    @pytest.mark.asyncio
    async def test_tool_error_fallback(self, meta_agent):
        agent, _ = meta_agent
        agent.mcp.call_tool = AsyncMock(side_effect=Exception("mcp down"))
        result = await agent._execute_tool_with_governance("t", {}, {}, None, pre_approved=True)
        assert result == "Tool error. Please try again."


class TestRecruitFleet:
    @pytest.mark.asyncio
    async def test_recruit_fleet_success(self, meta_agent, monkeypatch, fake_business_agents):
        agent, _ = meta_agent
        chain = SimpleNamespace(id="chain-1")
        fleet_svc = MagicMock()
        fleet_svc.initialize_fleet.return_value = chain
        fleet_svc.recruit_member.return_value = SimpleNamespace(id="link-1")
        optimizer = MagicMock()
        optimizer.get_optimization_parameters.return_value = {"optimization_reason": "best"}
        from core.atom_meta_agent import AgentFleetService, FleetOptimizationService
        with patch("core.atom_meta_agent.AgentFleetService", return_value=fleet_svc), \
             patch("core.atom_meta_agent.FleetOptimizationService", return_value=optimizer):
            sub = SimpleNamespace(id="a1", name="Sales")
            fake_business_agents.get_specialized_agent = lambda n, w: sub
            seen = []

            async def cb(record):
                seen.append(record)

            result = await agent._recruit_fleet(
                "goal", [{"domain": "sales", "task": "t1"}, {"domain": "ops", "task": "t2", "use_optimizer": False}],
                {"execution_id": "e1"}, cb,
            )

        assert "Fleet Successfully Recruited" in result
        assert "chain-1" in result
        assert seen and seen[0]["type"] == "fleet_recruited"

    @pytest.mark.asyncio
    async def test_recruit_fleet_exception(self, meta_agent):
        agent, _ = meta_agent
        from core.atom_meta_agent import AgentFleetService
        with patch("core.atom_meta_agent.AgentFleetService",
                   side_effect=Exception("fleet down")):
            result = await agent._recruit_fleet("goal", [], {})
        assert result == "Fleet recruitment failed. Please try again."


class TestSpawnAgent:
    @pytest.mark.asyncio
    async def test_spawn_template_ephemeral(self, meta_agent):
        agent, sl = meta_agent
        agent.graduation_service.reset_maturity = MagicMock()
        result = await agent.spawn_agent("finance_analyst")
        assert result.id.startswith("spawned_finance_analyst_")
        assert result.id in agent.spawned_agents
        agent.graduation_service.reset_maturity.assert_called()

    @pytest.mark.asyncio
    async def test_spawn_custom(self, meta_agent):
        agent, _ = meta_agent
        result = await agent.spawn_agent("custom", custom_params={"focus": "x"})
        assert result.configuration == {"focus": "x"}

    @pytest.mark.asyncio
    async def test_spawn_invalid_template(self, meta_agent):
        agent, _ = meta_agent
        with pytest.raises(ValueError):
            await agent.spawn_agent("nope")

    @pytest.mark.asyncio
    async def test_spawn_persist_with_db(self, meta_agent):
        agent, _ = meta_agent
        db = MagicMock()
        registered = SimpleNamespace(id="reg-1", name="Registered", category="c",
                                     module_path="m", class_name="k", description="d")
        gov = MagicMock()
        gov.register_or_update_agent.return_value = registered
        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            result = await agent.spawn_agent("hr_assistant", persist=True, db=db)
        assert result == registered

    @pytest.mark.asyncio
    async def test_spawn_persist_new_session(self, meta_agent):
        agent, sl = meta_agent
        registered = SimpleNamespace(id="reg-2", name="Registered")
        gov = MagicMock()
        gov.register_or_update_agent.return_value = registered
        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            result = await agent.spawn_agent("sales_assistant", persist=True)
        assert result == registered


class TestQueryMemoryAndGuidance:
    @pytest.mark.asyncio
    async def test_query_memory_scopes(self, meta_agent):
        agent, _ = meta_agent
        agent.world_model.recall_experiences = AsyncMock(
            return_value={"experiences": ["e"], "knowledge": ["k"]}
        )
        assert (await agent.query_memory("q", scope="experiences")) == {"experiences": ["e"]}
        assert (await agent.query_memory("q", scope="knowledge")) == {"knowledge": ["k"]}
        assert (await agent.query_memory("q", scope="all"))["experiences"] == ["e"]

    @pytest.mark.asyncio
    async def test_mentorship_guidance_no_supervisors(self, meta_agent):
        agent, sl = meta_agent
        db = sl.return_value.__enter__.return_value
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(category="Finance")
        db.query.return_value.filter.return_value.count.return_value = 0
        agent.llm.generate_response = AsyncMock(return_value="guidance text")
        result = await agent.generate_mentorship_guidance("student-1", "run_report", {}, "too risky")
        assert result == "guidance text"

    @pytest.mark.asyncio
    async def test_mentorship_guidance_with_supervisors(self, meta_agent):
        agent, sl = meta_agent
        db = sl.return_value.__enter__.return_value
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(category="Finance")
        db.query.return_value.filter.return_value.count.return_value = 1
        agent.llm.generate_response = AsyncMock(return_value="guidance text")
        result = await agent.generate_mentorship_guidance("student-1", "a", {}, "r")
        assert result == "guidance text"

    @pytest.mark.asyncio
    async def test_mentorship_guidance_empty_response(self, meta_agent):
        agent, sl = meta_agent
        db = sl.return_value.__enter__.return_value
        db.query.return_value.filter.return_value.first.return_value = None
        agent.llm.generate_response = AsyncMock(return_value="")
        result = await agent.generate_mentorship_guidance("student-1", "a", {}, "r")
        assert "unable to provide guidance" in result


class TestWaitForApproval:
    @pytest.mark.asyncio
    async def test_wait_approved(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        gov = MagicMock()
        gov.get_approval_status.return_value = {"status": "approved"}
        from core.atom_meta_agent import AgentGovernanceService
        monkeypatch.setattr("core.atom_meta_agent.asyncio.sleep", AsyncMock())
        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            assert await agent._wait_for_approval("a1") is True

    @pytest.mark.asyncio
    async def test_wait_rejected(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        gov = MagicMock()
        gov.get_approval_status.return_value = {"status": "rejected"}
        monkeypatch.setattr("core.atom_meta_agent.asyncio.sleep", AsyncMock())
        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            assert await agent._wait_for_approval("a1") is False

    @pytest.mark.asyncio
    async def test_wait_timeout(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        gov = MagicMock()
        gov.get_approval_status.return_value = {"status": "pending"}
        monkeypatch.setattr("core.atom_meta_agent.asyncio.sleep", AsyncMock())
        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            assert await agent._wait_for_approval("a1") is False

    @pytest.mark.asyncio
    async def test_wait_all_approved(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        gov = MagicMock()
        gov.get_approval_status.side_effect = [{"status": "approved"}, {"status": "approved"}]
        monkeypatch.setattr("core.atom_meta_agent.asyncio.sleep", AsyncMock())
        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            assert await agent._wait_for_all_approvals(["a1", "a2"]) is True

    @pytest.mark.asyncio
    async def test_wait_all_rejected(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        gov = MagicMock()
        gov.get_approval_status.side_effect = [{"status": "approved"}, {"status": "rejected"}]
        monkeypatch.setattr("core.atom_meta_agent.asyncio.sleep", AsyncMock())
        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            assert await agent._wait_for_all_approvals(["a1", "a2"]) is False

    @pytest.mark.asyncio
    async def test_wait_all_timeout(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        gov = MagicMock()
        gov.get_approval_status.return_value = {"status": "pending"}
        monkeypatch.setattr("core.atom_meta_agent.asyncio.sleep", AsyncMock())
        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            assert await agent._wait_for_all_approvals(["a1"]) is False


class TestExecuteParallelTools:
    @pytest.mark.asyncio
    async def test_parallel_disabled_sequential(self, meta_agent, monkeypatch):
        agent, _ = meta_agent
        monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled", lambda: False)
        monkeypatch.setattr("core.hallucination_config.get_max_parallel_tools", lambda: 4)
        agent._execute_tool_with_governance = AsyncMock(return_value="obs")
        records = await agent._execute_parallel_tools(
            [ToolCall(tool="a", params={}), ToolCall(tool="b", params={})], {}, None
        )
        assert len(records) == 2
        assert records[0]["output"] == "obs"

    @pytest.mark.asyncio
    async def test_parallel_blocked_batch(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled", lambda: True)
        monkeypatch.setattr("core.hallucination_config.get_max_parallel_tools", lambda: 4)
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={"action_complexity": 1, "allowed": False, "reason": "denied"})
        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            records = await agent._execute_parallel_tools(
                [ToolCall(tool="a", params={}), ToolCall(tool="b", params={})], {}, None
            )
        assert all(r["verified_kind"] == "blocked" for r in records)
        assert "Governance blocked" in records[0]["output"]

    @pytest.mark.asyncio
    async def test_parallel_batch_rejected(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled", lambda: True)
        monkeypatch.setattr("core.hallucination_config.get_max_parallel_tools", lambda: 4)
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={"action_complexity": 2, "allowed": True, "requires_human_approval": False, "reason": "r"})
        gov.request_approval.return_value = "act-1"
        agent._wait_for_all_approvals = AsyncMock(return_value=False)
        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            records = await agent._execute_parallel_tools([ToolCall(tool="a", params={})], {}, None)
        assert records[0]["verified_kind"] == "rejected"

    @pytest.mark.asyncio
    async def test_parallel_success_verified(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled", lambda: True)
        monkeypatch.setattr("core.hallucination_config.get_max_parallel_tools", lambda: 4)
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={"action_complexity": 1, "allowed": True, "requires_human_approval": False, "reason": ""})
        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            agent._execute_tool_with_governance = AsyncMock(
                return_value=json.dumps({"success": True, "verified": True, "evidence": "ev-1"})
            )
            records = await agent._execute_parallel_tools([ToolCall(tool="a", params={})], {}, None)
        assert records[0]["verified_kind"] == "verified"
        assert records[0]["verified_evidence"] == "ev-1"

    @pytest.mark.asyncio
    async def test_parallel_tool_exception(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled", lambda: True)
        monkeypatch.setattr("core.hallucination_config.get_max_parallel_tools", lambda: 4)
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={"action_complexity": 1, "allowed": True})
        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            agent._execute_tool_with_governance = AsyncMock(side_effect=Exception("boom"))
            records = await agent._execute_parallel_tools([ToolCall(tool="a", params={})], {}, None)
        assert records[0]["verified_kind"] == "error"

    @pytest.mark.asyncio
    async def test_parallel_serial_tool_search(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled", lambda: True)
        monkeypatch.setattr("core.hallucination_config.get_max_parallel_tools", lambda: 4)
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={"action_complexity": 1, "allowed": True})
        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            agent.mcp.search_tools = AsyncMock(return_value=[
                {"name": "st1", "description": "d", "parameters": {}}
            ])
            records = await agent._execute_parallel_tools(
                [ToolCall(tool="mcp_tool_search", params={"query": "q"})], {}, None
            )
        assert "Found 1 new tools" in records[0]["output"]
        assert agent.session_tools == [{"name": "st1", "description": "d", "parameters": {}}]

    @pytest.mark.asyncio
    async def test_parallel_serial_tool_search_error(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled", lambda: True)
        monkeypatch.setattr("core.hallucination_config.get_max_parallel_tools", lambda: 4)
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={"action_complexity": 1, "allowed": True})
        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            agent.mcp.search_tools = AsyncMock(side_effect=Exception("search down"))
            records = await agent._execute_parallel_tools(
                [ToolCall(tool="mcp_tool_search", params={"query": "q"})], {}, None
            )
        assert "Tool search failed" in records[0]["output"]

    @pytest.mark.asyncio
    async def test_parallel_hitl_callback(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled", lambda: True)
        monkeypatch.setattr("core.hallucination_config.get_max_parallel_tools", lambda: 4)
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={"action_complexity": 2, "allowed": True, "requires_human_approval": False, "reason": "r"})
        gov.request_approval.return_value = "act-1"
        agent._wait_for_all_approvals = AsyncMock(return_value=False)
        seen = []
        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            async def cb(record):
                seen.append(record)
            await agent._execute_parallel_tools([ToolCall(tool="a", params={})], {}, cb)
        assert seen[0]["parallel_batch"] is True


class TestPersistReasoningStep:
    def test_persist_success(self, meta_agent):
        agent, sl = meta_agent
        db = sl.return_value.__enter__.return_value
        step_id = agent._persist_reasoning_step(
            "e1", 1, "action", "thought", {"tool": "t"}, "obs", 0.9,
            "verified", "ev", 10.0, "req", "final", {"session_id": "s1"}, dispatch_turn_fact=False,
        )
        assert step_id
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_persist_commit_failure(self, meta_agent):
        agent, sl = meta_agent
        db = sl.return_value.__enter__.return_value
        db.commit.side_effect = Exception("db down")
        step_id = agent._persist_reasoning_step(
            "e1", 1, "action", "thought", None, "obs", 0.9, "unverified", None,
            1.0, "req", None, None, dispatch_turn_fact=False,
        )
        assert step_id == ""

    @pytest.mark.asyncio
    async def test_persist_dispatch_fact_extraction(self, meta_agent, monkeypatch):
        import core.atom_meta_agent as ama
        agent, sl = meta_agent
        ama._pending_extraction_tasks.clear()  # drop orphaned cross-loop tasks
        monkeypatch.setattr(ama, "_TURN_FACT_EXTRACTION_ENABLED", True)
        extractor = MagicMock()
        extractor.extract_from_turn = AsyncMock()
        monkeypatch.setattr(ama, "get_turn_fact_extractor", lambda workspace_id, tenant_id: extractor)
        agent.graduation_service.get_maturity.return_value = "intern"

        step_id = agent._persist_reasoning_step(
            "e1", 1, "action", "thought", None, "obs", 0.9, "unverified", None,
            1.0, "req", "final", {"session_id": "s1"}, dispatch_turn_fact=True,
        )

        assert step_id
        assert ama._pending_extraction_tasks
        if ama._pending_extraction_tasks:
            await asyncio.gather(*list(ama._pending_extraction_tasks), return_exceptions=True)

    @pytest.mark.asyncio
    async def test_persist_dispatch_maturity_error(self, meta_agent, monkeypatch):
        import core.atom_meta_agent as ama
        agent, sl = meta_agent
        ama._pending_extraction_tasks.clear()  # drop orphaned cross-loop tasks
        monkeypatch.setattr(ama, "_TURN_FACT_EXTRACTION_ENABLED", True)
        extractor = MagicMock()
        extractor.extract_from_turn = AsyncMock()
        monkeypatch.setattr(ama, "get_turn_fact_extractor", lambda workspace_id, tenant_id: extractor)
        agent.graduation_service.get_maturity.side_effect = Exception("maturity down")

        step_id = agent._persist_reasoning_step(
            "e1", 1, "action", "thought", None, "obs", 0.9, "unverified", None,
            1.0, "req", "final", {"session_id": "s1"}, dispatch_turn_fact=True,
        )

        assert step_id
        if ama._pending_extraction_tasks:
            await asyncio.gather(*list(ama._pending_extraction_tasks), return_exceptions=True)

    @pytest.mark.asyncio
    async def test_persist_dispatch_extractor_error(self, meta_agent, monkeypatch):
        import core.atom_meta_agent as ama
        agent, sl = meta_agent
        ama._pending_extraction_tasks.clear()  # drop orphaned cross-loop tasks
        monkeypatch.setattr(ama, "_TURN_FACT_EXTRACTION_ENABLED", True)
        extractor = MagicMock()
        extractor.extract_from_turn = lambda *a, **k: (_ for _ in ()).throw(Exception("extract down"))
        monkeypatch.setattr(ama, "get_turn_fact_extractor", lambda workspace_id, tenant_id: extractor)
        step_id = agent._persist_reasoning_step(
            "e1", 1, "action", "thought", None, "obs", 0.9, "unverified", None,
            1.0, "req", "final", {"session_id": "s1"}, dispatch_turn_fact=True,
        )
        assert step_id


class TestRecordExecution:
    @pytest.mark.asyncio
    async def test_record_execution_success(self, meta_agent):
        agent, sl = meta_agent
        agent.world_model.record_experience = AsyncMock()
        gov = MagicMock()
        gov.record_outcome = AsyncMock()
        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            await agent._record_execution("req", {"status": "success", "final_output": "ok", "actions_executed": []}, AgentTriggerMode.MANUAL)
        agent.world_model.record_experience.assert_awaited_once()
        gov.record_outcome.assert_awaited_once_with("atom_main", success=True)

    @pytest.mark.asyncio
    async def test_record_execution_governance_error(self, meta_agent):
        agent, sl = meta_agent
        agent.world_model.record_experience = AsyncMock()
        with patch("core.atom_meta_agent.AgentGovernanceService",
                   side_effect=Exception("gov down")):
            await agent._record_execution("req", {"status": "failed", "final_output": None, "actions_executed": []}, AgentTriggerMode.MANUAL)
        agent.world_model.record_experience.assert_awaited_once()


class TestCommunicationInstruction:
    @pytest.mark.asyncio
    async def test_style_enabled(self, meta_agent):
        agent, sl = meta_agent
        user = SimpleNamespace(
            metadata_json={"communication_style": {"enable_personalization": True, "style_guide": "be brief"}}
        )
        db = sl.return_value
        db.query.return_value.filter.return_value.first.return_value = user
        result = agent._get_communication_instruction({"user_id": "u1"})
        assert "be brief" in result

    @pytest.mark.asyncio
    async def test_style_disabled(self, meta_agent):
        agent, sl = meta_agent
        user = SimpleNamespace(
            metadata_json={"communication_style": {"enable_personalization": False, "style_guide": "x"}}
        )
        db = sl.return_value
        db.query.return_value.filter.return_value.first.return_value = user
        assert agent._get_communication_instruction({"user_id": "u1"}) == ""

    @pytest.mark.asyncio
    async def test_no_user_id(self, meta_agent):
        agent, _ = meta_agent
        assert agent._get_communication_instruction({}) == ""

    @pytest.mark.asyncio
    async def test_style_exception(self, meta_agent):
        agent, sl = meta_agent
        db = sl.return_value
        db.query.side_effect = Exception("db down")
        assert agent._get_communication_instruction({"user_id": "u1"}) == ""

    @pytest.mark.asyncio
    async def test_style_user_missing(self, meta_agent):
        agent, sl = meta_agent
        db = sl.return_value
        db.query.return_value.filter.return_value.first.return_value = None
        assert agent._get_communication_instruction({"user_id": "u1"}) == ""


class TestCheckGovernanceClass:
    @pytest.mark.asyncio
    async def test_denied_returns_reason(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        decision = SimpleNamespace(allowed=False, reason="maturity too low")
        gov = MagicMock()
        gov.canPerformAction = AsyncMock(return_value=decision)
        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            allowed, reason = await agent._check_governance("u1", "a1", "workflow")
        assert allowed is False
        assert reason == "maturity too low"

    @pytest.mark.asyncio
    async def test_allowed(self, meta_agent):
        agent, sl = meta_agent
        decision = SimpleNamespace(allowed=True, reason=None)
        gov = MagicMock()
        gov.canPerformAction = AsyncMock(return_value=decision)
        with patch("core.atom_meta_agent.AgentGovernanceService", return_value=gov):
            allowed, reason = await agent._check_governance("u1", "a1", "task")
        assert allowed is True
        assert reason is None


class TestRouteWithGovernanceClass:
    @pytest.mark.asyncio
    async def test_chat_bypasses_governance(self, meta_agent):
        agent, _ = meta_agent
        agent.llm.generate_response = AsyncMock(return_value="chat reply")
        result = await agent.route_with_governance("hi", _route_cls(IntentCategory.CHAT), "u1")
        assert result["route"] == "CHAT"
        assert result["governance_checked"] is False

    @pytest.mark.asyncio
    async def test_workflow_allowed(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        agent._check_governance = AsyncMock(return_value=(True, None))
        queen = MagicMock()
        queen.generate_blueprint = AsyncMock(return_value={
            "blueprint_id": "b1", "architecture_name": "Arch", "nodes": [{"id": "n1"}],
        })
        with patch("core.atom_meta_agent.QueenAgent", return_value=queen):
            result = await agent.route_with_governance("build a report", _route_cls(IntentCategory.WORKFLOW), "u1")
        assert result["route"] == "WORKFLOW"
        assert result["blueprint_id"] == "b1"
        assert result["governance_allowed"] is True

    @pytest.mark.asyncio
    async def test_workflow_denied_proposes_chat(self, meta_agent):
        agent, _ = meta_agent
        agent._check_governance = AsyncMock(return_value=(False, "not mature enough"))
        agent.llm.generate_response = AsyncMock(return_value="here is what I can do")
        result = await agent.route_with_governance("build a report", _route_cls(IntentCategory.WORKFLOW), "u1")
        assert result["route"] == "CHAT"
        assert result["auto_takeover"] is True
        assert result["governance_allowed"] is False
        assert result["original_route"] == "workflow"

    @pytest.mark.asyncio
    async def test_task_allowed(self, meta_agent):
        agent, _ = meta_agent
        agent._check_governance = AsyncMock(return_value=(True, None))
        agent._route_to_task = AsyncMock(return_value={"route": "TASK", "chain_id": "c1"})
        result = await agent.route_with_governance("research competitors", _route_cls(IntentCategory.TASK), "u1")
        assert result["route"] == "TASK"
        assert result["governance_allowed"] is True


class TestRouteToTask:
    @pytest.mark.asyncio
    async def test_route_to_task(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        admiral = MagicMock()
        admiral.recruit_and_execute = AsyncMock(return_value={"chain_id": "ch1", "specialists_count": 2})
        with patch("core.fleet_admiral.FleetAdmiral", return_value=admiral):
            result = await agent._route_to_task("task", "u1")
        assert result["route"] == "TASK"
        assert result["chain_id"] == "ch1"


class TestProposeChatAlternative:
    @pytest.mark.asyncio
    async def test_propose(self, meta_agent):
        agent, _ = meta_agent
        agent.llm.generate_response = AsyncMock(return_value="proposal text")
        result = await agent._propose_chat_alternative("req", "workflow", "reason", "u1")
        assert result["auto_takeover"] is True
        assert result["proposal"] == "proposal text"
        assert result["status"] == "auto_takeover_proposal"


class TestSandboxCheckHelper:
    def test_disabled_returns_none(self, monkeypatch):
        monkeypatch.setattr("core.sandbox_config.is_sandbox_enabled", lambda: False)
        assert _meta_agent_sandbox_check("t", {}, {}) is None

    def test_no_run_id(self, monkeypatch):
        monkeypatch.setattr("core.sandbox_config.is_sandbox_enabled", lambda: True)
        assert _meta_agent_sandbox_check("t", {}, {}) is None

    def test_no_tier(self, monkeypatch):
        monkeypatch.setattr("core.sandbox_config.is_sandbox_enabled", lambda: True)
        assert _meta_agent_sandbox_check("t", {}, {"run_id": "r1"}) is None

    def test_allowed_decision(self, monkeypatch):
        monkeypatch.setattr("core.sandbox_config.is_sandbox_enabled", lambda: True)
        monkeypatch.setattr("core.sandbox_config.is_sandbox_fs_enabled", lambda: True)
        monkeypatch.setattr("core.sandbox_config.is_sandbox_tripwires_enabled", lambda: True)
        monkeypatch.setattr("core.sandbox_config.is_sandbox_caps_enabled", lambda: True)
        monkeypatch.setattr("core.sandbox_config.is_sandbox_force_enforce_enabled", lambda: False)
        issuer = MagicMock()
        decision = SimpleNamespace(
            is_allowed=True, args_hash="h", requires_review=False, decision="allowed",
            violation_detail=None, violation_type=None, metadata_json={}, enforced=False,
        )
        issuer.issue.return_value = MagicMock()
        issuer.check.return_value = decision
        monkeypatch.setattr("core.sandbox_policy.PolicyIssuer", lambda: issuer)
        fs_decision = SimpleNamespace(requires_review=False)
        monkeypatch.setattr("core.sandbox_fs.validate", lambda *a, **k: fs_decision)
        tw_decision = SimpleNamespace(decision="allowed", killrun_triggered=False, violation_detail=None, metadata_json={})
        monkeypatch.setattr("core.sandbox_tripwire.check", lambda *a, **k: tw_decision)
        monkeypatch.setattr("core.sandbox_caps.check_caps", lambda *a, **k: SimpleNamespace(requires_review=False))
        monkeypatch.setattr("core.sandbox_killrun.guard", lambda run_id: None)

        result = _meta_agent_sandbox_check(
            "tool", {}, {"run_id": "r1", "tier": "autonomous", "agent_id": "a1"}
        )

        assert result is decision

    def test_tripwire_killrun(self, monkeypatch):
        monkeypatch.setattr("core.sandbox_config.is_sandbox_enabled", lambda: True)
        monkeypatch.setattr("core.sandbox_config.is_sandbox_fs_enabled", lambda: False)
        monkeypatch.setattr("core.sandbox_config.is_sandbox_tripwires_enabled", lambda: True)
        monkeypatch.setattr("core.sandbox_config.is_sandbox_caps_enabled", lambda: False)
        monkeypatch.setattr("core.sandbox_config.is_sandbox_force_enforce_enabled", lambda: True)
        issuer = MagicMock()
        decision = SimpleNamespace(
            is_allowed=True, args_hash="h", requires_review=False, decision="allowed",
            violation_detail=None, violation_type=None, metadata_json={}, enforced=False,
        )
        issuer.issue.return_value = MagicMock()
        issuer.check.return_value = decision
        monkeypatch.setattr("core.sandbox_policy.PolicyIssuer", lambda: issuer)
        tw_decision = SimpleNamespace(
            decision="blocked", killrun_triggered=True,
            violation_detail="trip", metadata_json={"tripwire_id": "tw1"},
        )
        monkeypatch.setattr("core.sandbox_tripwire.check", lambda *a, **k: tw_decision)
        killrun = MagicMock()
        monkeypatch.setattr("core.sandbox_killrun.trigger_killrun", killrun)
        monkeypatch.setattr("core.sandbox_killrun.guard", lambda run_id: None)

        result = _meta_agent_sandbox_check("t", {}, {"run_id": "r1", "tier": "autonomous"})

        killrun.assert_called_once()

    def test_requires_review_writes_violation(self, monkeypatch):
        monkeypatch.setattr("core.sandbox_config.is_sandbox_enabled", lambda: True)
        monkeypatch.setattr("core.sandbox_config.is_sandbox_fs_enabled", lambda: False)
        monkeypatch.setattr("core.sandbox_config.is_sandbox_tripwires_enabled", lambda: False)
        monkeypatch.setattr("core.sandbox_config.is_sandbox_caps_enabled", lambda: False)
        issuer = MagicMock()
        decision = SimpleNamespace(
            is_allowed=False, args_hash="h", requires_review=True, decision="blocked",
            violation_detail="v", violation_type="t", metadata_json={}, enforced=False,
        )
        issuer.issue.return_value = MagicMock()
        issuer.check.return_value = decision
        monkeypatch.setattr("core.sandbox_policy.PolicyIssuer", lambda: issuer)
        monkeypatch.setattr("core.sandbox_killrun.guard", lambda run_id: None)
        write_violation = MagicMock()
        monkeypatch.setattr("core.sandbox_audit.write_violation", write_violation)

        result = _meta_agent_sandbox_check("t", {}, {"run_id": "r1", "tier": "autonomous"})

        write_violation.assert_called_once()

    def test_exception_fails_open(self, monkeypatch):
        monkeypatch.setattr("core.sandbox_config.is_sandbox_enabled",
                            lambda: (_ for _ in ()).throw(RuntimeError("config broke")))
        result = _meta_agent_sandbox_check("t", {}, {})
        assert result.decision == "allowed"
        assert "error" in result.metadata_json

    def test_killrun_aborted_propagates(self, monkeypatch):
        monkeypatch.setattr("core.sandbox_config.is_sandbox_enabled", lambda: True)
        issuer = MagicMock()
        issuer.issue.side_effect = RuntimeError("killrun")
        monkeypatch.setattr("core.sandbox_policy.PolicyIssuer", lambda: issuer)
        monkeypatch.setattr("core.sandbox_killrun.KillRunAborted", RuntimeError)
        with pytest.raises(RuntimeError):
            _meta_agent_sandbox_check("t", {}, {"run_id": "r1", "tier": "autonomous"})


class TestDataEventTrigger:
    @pytest.mark.asyncio
    async def test_queue_enabled(self, monkeypatch):
        queue = MagicMock()
        queue.enabled = True
        queue.enqueue_job.return_value = "task-1"
        with patch("core.task_queue.get_task_queue", return_value=queue):
            result = await handle_data_event_trigger("sale.created", {"id": 1})
        assert result["status"] == "queued"
        assert result["task_id"] == "task-1"

    @pytest.mark.asyncio
    async def test_queue_disabled_inline(self, monkeypatch):
        queue = MagicMock()
        queue.enabled = False
        agent = MagicMock()
        agent.execute = AsyncMock(return_value={"status": "success"})
        with patch("core.task_queue.get_task_queue", return_value=queue), \
             patch("core.atom_meta_agent.AtomMetaAgent", return_value=agent):
            result = await handle_data_event_trigger("sale.created", {"id": 1})
        assert result == {"status": "success"}
        agent.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_queue_exception_inline(self, monkeypatch):
        agent = MagicMock()
        agent.execute = AsyncMock(return_value={"status": "success"})
        with patch("core.task_queue.get_task_queue", side_effect=Exception("redis down")), \
             patch("core.atom_meta_agent.AtomMetaAgent", return_value=agent):
            result = await handle_data_event_trigger("sale.created", {"id": 1})
        assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_queue_enabled_no_task_id(self, monkeypatch):
        queue = MagicMock()
        queue.enabled = True
        queue.enqueue_job.return_value = None
        agent = MagicMock()
        agent.execute = AsyncMock(return_value={"status": "success"})
        with patch("core.task_queue.get_task_queue", return_value=queue), \
             patch("core.atom_meta_agent.AtomMetaAgent", return_value=agent):
            result = await handle_data_event_trigger("sale.created", {"id": 1})
        assert result == {"status": "success"}


class TestManualTrigger:
    @pytest.mark.asyncio
    async def test_manual_trigger_streams(self, monkeypatch):
        agent = MagicMock()
        agent.execute = AsyncMock(return_value={"status": "success"})
        ws = MagicMock()
        ws.broadcast = AsyncMock()
        tracker = MagicMock()
        with patch("core.atom_meta_agent.AtomMetaAgent", return_value=agent), \
             patch("core.websockets.manager", ws), \
             patch("core.reasoning_chain.get_reasoning_tracker", return_value=tracker), \
             patch("core.reasoning_chain.ReasoningStep", MagicMock()), \
             patch("core.reasoning_chain.ReasoningStepType", type("T", (), {
                 "ACTION": "action", "FINAL_ANSWER": "final", "INTENT_ANALYSIS": "plan", "DECISION": "decision",
                 "CONCLUSION": "conclusion"
             })):
            user = SimpleNamespace(id="u1", email="e@x.com")
            result = await handle_manual_trigger("do it", user, additional_context={"board_id": "b1"})
        assert result == {"status": "success"}
        agent.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_manual_trigger_callback_persists(self, monkeypatch):
        captured = {}

        async def fake_execute(request, context, trigger_mode, step_callback, execution_id):
            captured["cb"] = step_callback
            await step_callback({"execution_id": "e1", "step_type": "action", "thought": "t",
                                 "action": {"tool": "x"}, "output": "o", "confidence": 0.9,
                                 "duration_ms": 1.0, "step": 1})
            return {"status": "success"}

        agent = MagicMock()
        agent.execute = fake_execute
        ws = MagicMock()
        ws.broadcast = AsyncMock()
        tracker = MagicMock()
        with patch("core.atom_meta_agent.AtomMetaAgent", return_value=agent), \
             patch("core.websockets.manager", ws), \
             patch("core.reasoning_chain.get_reasoning_tracker", return_value=tracker), \
             patch("core.reasoning_chain.ReasoningStep", MagicMock()), \
             patch("core.reasoning_chain.ReasoningStepType", type("T", (), {
                 "ACTION": "action", "FINAL_ANSWER": "final", "INTENT_ANALYSIS": "plan", "DECISION": "decision",
                 "CONCLUSION": "conclusion"
             })):
            user = SimpleNamespace(id="u1", email="e@x.com")
            await handle_manual_trigger("do it", user)
        ws.broadcast.assert_awaited_once()
        tracker.persist_step_to_db.assert_called_once()

    @pytest.mark.asyncio
    async def test_manual_trigger_callback_error_suppressed(self, monkeypatch):
        captured = {}

        async def fake_execute(request, context, trigger_mode, step_callback, execution_id):
            await step_callback({"execution_id": "e1", "step_type": "planning", "thought": "t"})
            return {"status": "success"}

        agent = MagicMock()
        agent.execute = fake_execute
        with patch("core.atom_meta_agent.AtomMetaAgent", return_value=agent), \
             patch("core.websockets.manager", MagicMock(broadcast=AsyncMock(side_effect=Exception("ws down")))), \
             patch("core.reasoning_chain.get_reasoning_tracker", MagicMock()):
            user = SimpleNamespace(id="u1", email="e@x.com")
            result = await handle_manual_trigger("do it", user)
        assert result == {"status": "success"}


class TestGetAtomAgent:
    def test_singleton(self, monkeypatch):
        import core.atom_meta_agent as ama
        monkeypatch.setattr(ama, "_atom_instance", None)
        with patch.object(ama.AtomMetaAgent, "__init__",
                          lambda self, w="default", t=None, u=None: setattr(self, "workspace_id", w)):
            a1 = get_atom_agent("default")
            a2 = get_atom_agent("default")
        assert a1 is a2

    def test_different_workspace_new_instance(self, monkeypatch):
        import core.atom_meta_agent as ama
        monkeypatch.setattr(ama, "_atom_instance", None)
        with patch.object(ama.AtomMetaAgent, "__init__",
                          lambda self, w="default", t=None, u=None: setattr(self, "workspace_id", w)):
            a1 = get_atom_agent("default")
            a2 = get_atom_agent("other")
        assert a1 is not a2


class TestGetAtomRegistry:
    def test_registry(self, meta_agent):
        agent, _ = meta_agent
        reg = agent._get_atom_registry()
        assert reg.id == "atom_main"
        assert reg.status == AgentStatus.AUTONOMOUS.value
