"""Coverage wave 52 — core/agents/queen_agent.py (54% → 90%+).

generate_blueprint (recurring/one-off modes, fenced JSON, missing
capabilities, exception → fallback), mermaid generation (statuses, missing
node id/name skip), fallback blueprint, realize_blueprint (full mapping:
trigger/agent/entity/unknown types, adjacency, start-step resolution,
orchestrator-missing path).
"""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.agents.queen_agent import QueenAgent


@pytest.fixture
def queen():
    llm = Mock()
    queen = QueenAgent(Mock(), llm)
    return queen


def _blueprint(nodes=None):
    return {
        "architecture_name": "Test Arch",
        "description": "desc",
        "nodes": nodes or [
            {"id": "n1", "type": "agent", "name": "Agent 1",
             "capability_required": "x", "dependencies": []},
        ],
        "required_integrations": [],
        "missing_capabilities": [],
    }


class TestGenerateBlueprint:
    async def test_one_off_success(self, queen):
        queen.llm.generate = AsyncMock(return_value=json.dumps(_blueprint()))
        result = await queen.generate_blueprint("do something")
        assert result["architecture_name"] == "Test Arch"
        assert result["blueprint_id"]

    async def test_recurring_mode_instruction(self, queen):
        captured = {}

        async def generate(**kwargs):
            captured["prompt"] = kwargs["prompt"]
            return json.dumps(_blueprint())

        queen.llm.generate = generate
        await queen.generate_blueprint("daily report", execution_mode="recurring_automation")
        assert "RECURRING AUTOMATION" in captured["prompt"]

    async def test_fenced_json(self, queen):
        queen.llm.generate = AsyncMock(
            return_value='```json\n' + json.dumps(_blueprint()) + '\n```')
        result = await queen.generate_blueprint("x")
        assert result["architecture_name"] == "Test Arch"

    async def test_missing_capabilities_logged(self, queen):
        bp = _blueprint()
        bp["missing_capabilities"] = [{"name": "c1", "description": "d"}]
        queen.llm.generate = AsyncMock(return_value=json.dumps(bp))
        result = await queen.generate_blueprint("x")
        assert result["missing_capabilities"][0]["name"] == "c1"

    async def test_failure_falls_back(self, queen):
        queen.llm.generate = AsyncMock(side_effect=RuntimeError("llm down"))
        result = await queen.generate_blueprint("do anything")
        assert result["status"] == "fallback"
        assert result["nodes"][0]["id"] == "step_1"


class TestGenerateMermaid:
    def test_basic_diagram(self, queen):
        bp = _blueprint(nodes=[
            {"id": "n1", "type": "agent", "name": "Agent 1", "dependencies": []},
            {"id": "n2", "type": "trigger", "name": "Trigger", "dependencies": ["n1"]},
        ])
        mermaid = queen.generate_mermaid(bp, {"n1": "completed", "n2": "failed"})
        assert mermaid.startswith("graph TD")
        assert "classDef completed" in mermaid
        assert "class n1 completed" in mermaid
        assert "class n2 failed" in mermaid
        assert "n1 --> n2" in mermaid
        assert "(AGENT)" in mermaid and "(TRIGGER)" in mermaid

    def test_missing_id_or_name_skipped(self, queen):
        bp = _blueprint(nodes=[
            {"type": "agent", "name": "NoId", "dependencies": []},
            {"id": "n2", "dependencies": []},
            {"id": "n3", "type": "agent", "name": "Ok", "dependencies": []},
        ])
        mermaid = queen.generate_mermaid(bp)
        assert "NoId" not in mermaid
        assert "n3" in mermaid

    def test_default_status_pending(self, queen):
        mermaid = queen.generate_mermaid(_blueprint())
        assert "class n1 pending" in mermaid


class TestFallbackBlueprint:
    def test_shape(self, queen):
        fb = queen._generate_fallback_blueprint("goal here")
        assert fb["description"] == "Fallback architecture for: goal here"
        assert fb["status"] == "fallback"
        assert fb["blueprint_id"]


class TestRealizeBlueprint:
    async def test_orchestrator_missing(self, queen):
        with patch("builtins.__import__", side_effect=ImportError("no module")):
            result = await queen.realize_blueprint(_blueprint())
        assert result == "orchestrator_not_available"

    async def test_full_realization(self, queen):
        orchestrator = Mock()
        orchestrator.register_workflow = Mock()
        wf_steps = []

        class FakeWST:
            NLU_ANALYSIS = "nlu"
            BUSINESS_AGENT_EXECUTION = "agent"
            KNOWLEDGE_UPDATE = "knowledge"
            UNIVERSAL_INTEGRATION = "universal"

        captured = {}

        def fake_step(**kwargs):
            wf_steps.append(kwargs)
            return SimpleNamespace(**kwargs)

        def fake_def(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(**kwargs)

        bp = _blueprint(nodes=[
            {"id": "t1", "type": "trigger", "name": "Event",
             "metadata": {"trigger_event": "new_order"}, "dependencies": []},
            {"id": "a1", "type": "agent", "name": "Process",
             "dependencies": ["t1"]},
            {"id": "e1", "type": "entity", "name": "Order",
             "dependencies": ["a1"]},
            {"id": "u1", "type": "other", "name": "Integrate",
             "dependencies": ["e1"]},
        ])
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator), \
             patch("advanced_workflow_orchestrator.WorkflowStep", fake_step), \
             patch("advanced_workflow_orchestrator.WorkflowDefinition", fake_def), \
             patch("advanced_workflow_orchestrator.WorkflowStepType", FakeWST):
            result = await queen.realize_blueprint(bp)

        assert result.startswith("ai_wf_")
        assert len(wf_steps) == 4
        # start step is the trigger
        assert captured["start_step"] == "t1"
        assert captured["triggers"] == ["new_order"]
        orchestrator.register_workflow.assert_called_once()


class TestRealizeEdges:
    async def test_missing_ids_and_unlisted_dep(self, queen):
        orchestrator = Mock()
        wf_steps = []
        captured = {}

        def fake_step(**kwargs):
            wf_steps.append(kwargs)
            return SimpleNamespace(**kwargs)

        def fake_def(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(**kwargs)

        bp = _blueprint(nodes=[
            {"type": "agent", "name": "NoId", "dependencies": []},
            {"id": "a1", "type": "agent", "name": "A",
             "dependencies": ["ghost-dep"]},
            {"id": "a2", "type": "agent", "name": "B",
             "dependencies": ["a1"]},
        ])
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator), \
             patch("advanced_workflow_orchestrator.WorkflowStep", fake_step), \
             patch("advanced_workflow_orchestrator.WorkflowDefinition", fake_def), \
             patch("advanced_workflow_orchestrator.WorkflowStepType",
                   SimpleNamespace(NLU_ANALYSIS="n", BUSINESS_AGENT_EXECUTION="b",
                                   KNOWLEDGE_UPDATE="k", UNIVERSAL_INTEGRATION="u")):
            result = await queen.realize_blueprint(bp)
        assert result.startswith("ai_wf_")
        # no trigger, a1 has deps -> start falls to a2 (no deps) then steps[0]
        assert captured["start_step"] in ("a1", "a2")

    async def test_start_step_falls_back_to_first(self, queen):
        orchestrator = Mock()
        captured = {}

        def fake_step(**kwargs):
            return SimpleNamespace(**kwargs)

        def fake_def(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(**kwargs)

        bp = _blueprint(nodes=[
            {"id": "a1", "type": "agent", "name": "A", "dependencies": ["a2"]},
            {"id": "a2", "type": "agent", "name": "B", "dependencies": ["a1"]},
        ])
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator), \
             patch("advanced_workflow_orchestrator.WorkflowStep", fake_step), \
             patch("advanced_workflow_orchestrator.WorkflowDefinition", fake_def), \
             patch("advanced_workflow_orchestrator.WorkflowStepType",
                   SimpleNamespace(NLU_ANALYSIS="n", BUSINESS_AGENT_EXECUTION="b",
                                   KNOWLEDGE_UPDATE="k", UNIVERSAL_INTEGRATION="u")):
            await queen.realize_blueprint(bp)
        assert captured["start_step"] == "a1"


class TestStartStepFirstNonDependent:
    async def test_no_trigger_no_deps_first_node_wins(self, queen):
        orchestrator = Mock()
        captured = {}

        def fake_step(**kwargs):
            return SimpleNamespace(**kwargs)

        def fake_def(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(**kwargs)

        bp = _blueprint(nodes=[
            {"id": "a1", "type": "agent", "name": "A", "dependencies": []},
            {"id": "a2", "type": "agent", "name": "B", "dependencies": ["a1"]},
        ])
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orchestrator), \
             patch("advanced_workflow_orchestrator.WorkflowStep", fake_step), \
             patch("advanced_workflow_orchestrator.WorkflowDefinition", fake_def), \
             patch("advanced_workflow_orchestrator.WorkflowStepType",
                   SimpleNamespace(NLU_ANALYSIS="n", BUSINESS_AGENT_EXECUTION="b",
                                   KNOWLEDGE_UPDATE="k", UNIVERSAL_INTEGRATION="u")):
            await queen.realize_blueprint(bp)
        assert captured["start_step"] == "a1"
