"""P1 — Delegation contracts + effort scaling (AGENT_ORG_POLITICS_PLAN.md Phase 1).

Implements:
- core/fleet_orchestration/delegation_contracts.py: DelegationContract dataclass,
  recommended_effort() scaling table, build_contract(), render_contract_prompt()
- Wire-in: AtomMetaAgent._recruit_fleet stores a contract per ChainLink
  context_json["delegation_contract"]; ConductorAgent._execute_step injects
  one into step.parameters for AGENT-type steps.
- Flag ATOM_DELEGATION_CONTRACTS_ENABLED (default ON; off = exact prior behavior).

Style: zero LLM spend, no network.
"""

from __future__ import annotations

import pytest


# ============================================================================
# Contract model
# ============================================================================


class TestDelegationContract:
    def test_fields_and_roundtrip(self):
        from core.fleet_orchestration.delegation_contracts import (
            DelegationContract,
        )

        c = DelegationContract(
            objective="Analyze Q3 churn",
            output_format="markdown summary with 3 bullets",
            tool_guidance=["prefer documents.search over web"],
            task_boundaries="do not contact customers",
            effort_budget={"max_steps": 8, "max_tool_calls": 20},
        )
        d = c.to_dict()
        assert DelegationContract.from_dict(d) == c

    def test_defaults_are_safe(self):
        from core.fleet_orchestration.delegation_contracts import (
            DelegationContract,
        )

        c = DelegationContract(objective="x")
        assert c.output_format
        assert c.task_boundaries
        assert isinstance(c.tool_guidance, list)
        assert "max_steps" in c.effort_budget and "max_tool_calls" in c.effort_budget

    def test_from_dict_tolerates_garbage(self):
        from core.fleet_orchestration.delegation_contracts import (
            DelegationContract,
        )

        c = DelegationContract.from_dict("not-a-dict")
        assert isinstance(c, DelegationContract)
        c2 = DelegationContract.from_dict({"objective": 42, "bogus": "field"})
        assert c2.objective == "42"


# ============================================================================
# Effort scaling (Anthropic R2: scale effort to query complexity)
# ============================================================================


class TestRecommendedEffort:
    def test_simple_fact_gets_small_budget(self):
        from core.fleet_orchestration.delegation_contracts import (
            recommended_effort,
        )

        budget = recommended_effort("What is the status of invoice INV-12?")
        assert budget["max_steps"] <= 6
        assert budget["max_tool_calls"] <= 10

    def test_complex_analysis_gets_larger_budget(self):
        from core.fleet_orchestration.delegation_contracts import (
            recommended_effort,
        )

        simple = recommended_effort("list open deals")
        complex_ = recommended_effort(
            "Comprehensively analyze churn across finance, sales and marketing "
            "datasets, compare every segment, and produce an exhaustive report"
        )
        assert complex_["max_steps"] > simple["max_steps"]
        assert complex_["max_tool_calls"] > simple["max_tool_calls"]

    def test_budget_is_capped(self):
        from core.fleet_orchestration.delegation_contracts import (
            MAX_STEPS_CAP,
            MAX_TOOL_CALLS_CAP,
            recommended_effort,
        )

        budget = recommended_effort(
            "exhaustively research analyze everything everywhere all at once "
            * 20
        )
        assert budget["max_steps"] <= MAX_STEPS_CAP
        assert budget["max_tool_calls"] <= MAX_TOOL_CALLS_CAP


# ============================================================================
# build + render
# ============================================================================


class TestBuildAndRender:
    def test_build_contract_includes_goal_and_task(self):
        from core.fleet_orchestration.delegation_contracts import build_contract

        c = build_contract(
            goal="Reduce churn",
            task_desc="Analyze support tickets for cancellation drivers",
            domain="finance",
        )
        assert "Reduce churn" in c.objective
        assert "cancellation drivers" in c.objective
        assert c.effort_budget["max_steps"] >= 1

    def test_render_contains_sections(self):
        from core.fleet_orchestration.delegation_contracts import (
            build_contract,
            render_contract_prompt,
        )

        text = render_contract_prompt(
            build_contract(goal="g", task_desc="t", domain="sales")
        )
        for section in ("OBJECTIVE", "OUTPUT FORMAT", "TOOL GUIDANCE", "BOUNDARIES"):
            assert section in text


# ============================================================================
# Wire-in: fleet recruitment
# ============================================================================


class TestFleetRecruitWireIn:
    def test_helper_builds_contract_per_subtask(self):
        from core.fleet_orchestration.delegation_contracts import contract_for_link

        st = {"task": "Audit invoices", "domain": "finance"}
        c = contract_for_link(goal="Year-end close", sub_task=st)
        assert "Audit invoices" in c.objective
        assert "delegation_contract" not in st  # input not mutated

    def test_meta_agent_source_wires_contracts(self):
        import inspect

        from core import atom_meta_agent

        src = inspect.getsource(atom_meta_agent.AtomMetaAgent._recruit_fleet)
        assert "contract_for_link" in src or "delegation_contract" in src


# ============================================================================
# Wire-in: conductor steps
# ============================================================================


class TestConductorWireIn:
    @pytest.mark.asyncio
    async def test_agent_step_gets_contract_in_parameters(self):
        from core.orchestration.conductor_agent import (
            ConductorAgent,
            ExecutionStatus,
            StepType,
            WorkflowExecutionContext,
            WorkflowStep,
        )

        conductor = ConductorAgent()
        captured = {}

        async def fake_executor(step, ctx):
            captured["params"] = step.parameters
            step.status = ExecutionStatus.COMPLETED
            return {"ok": True}

        conductor.set_step_executor(fake_executor)

        step = WorkflowStep(
            step_id="s1",
            step_type=StepType.AGENT,
            name="analyze",
            description="Deep churn analysis across segments",
            parameters={"prompt": "go"},
        )
        ctx = WorkflowExecutionContext(
            workflow_id="wf", execution_id="ex", start_step="s1"
        )
        await conductor.execute_workflow([step], "s1")

        contract = captured["params"].get("delegation_contract")
        assert isinstance(contract, dict)
        assert "churn analysis" in contract["objective"].lower()

    @pytest.mark.asyncio
    async def test_flag_off_leaves_parameters_untouched(self, monkeypatch):
        monkeypatch.setenv("ATOM_DELEGATION_CONTRACTS_ENABLED", "false")
        from core.orchestration.conductor_agent import (
            ConductorAgent,
            ExecutionStatus,
            StepType,
            WorkflowExecutionContext,
            WorkflowStep,
        )

        conductor = ConductorAgent()
        captured = {}

        async def fake_executor(step, ctx):
            captured["params"] = dict(step.parameters)
            step.status = ExecutionStatus.COMPLETED
            return {"ok": True}

        conductor.set_step_executor(fake_executor)

        step = WorkflowStep(
            step_id="s1",
            step_type=StepType.AGENT,
            name="analyze",
            description="Deep churn analysis across segments",
            parameters={"prompt": "go"},
        )
        ctx = WorkflowExecutionContext(
            workflow_id="wf", execution_id="ex", start_step="s1"
        )
        await conductor.execute_workflow([step], "s1")
        assert "delegation_contract" not in captured["params"]

    @pytest.mark.asyncio
    async def test_non_agent_step_skipped(self):
        from core.orchestration.conductor_agent import (
            ConductorAgent,
            ExecutionStatus,
            StepType,
            WorkflowExecutionContext,
            WorkflowStep,
        )

        conductor = ConductorAgent()
        captured = {}

        async def fake_executor(step, ctx):
            captured["params"] = dict(step.parameters)
            step.status = ExecutionStatus.COMPLETED
            return {"ok": True}

        conductor.set_step_executor(fake_executor)

        step = WorkflowStep(
            step_id="w1",
            step_type=StepType.INTEGRATION,
            name="hook",
            description="call integration",
            parameters={"url": "https://example.com"},
        )
        ctx = WorkflowExecutionContext(
            workflow_id="wf", execution_id="ex", start_step="w1"
        )
        await conductor.execute_workflow([step], "w1")
        assert "delegation_contract" not in captured["params"]
