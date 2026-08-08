"""Coverage push for core/generic_agent.py (48% -> 95%)."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.generic_agent import GenericAgent
from core.models import AgentRegistry
from core.react_models import ReActStep, ToolCall


def _agent_model(**cfg_overrides):
    config = {
        "system_prompt": "You are Test Agent.",
        "tools": "*",
        "max_steps": 3,
        **cfg_overrides,
    }
    return AgentRegistry(
        id="agent-123", name="Test Agent",
        type="assistant", module_path="agents.assistant", class_name="AssistantAgent",
        category="general", configuration=config,
    )


def _build_agent(model, **patches):
    with patch("core.generic_agent.WorldModelService"), \
         patch("core.generic_agent.ReflectionService"), \
         patch("core.generic_agent.CanvasSummaryService"), \
         patch("core.generic_agent.mcp_service"), \
         patch("core.generic_agent.LLMService"):
        agent = GenericAgent(model)
    for k, v in patches.items():
        setattr(agent, k, v)
    return agent


def _noop_step_callback():
    async def cb(record):
        pass
    return cb


class TestExecuteBranches:
    @pytest.mark.asyncio
    async def test_execute_with_parallel_tools(self):
        agent = _build_agent(_agent_model(), _check_budget_before_react=None)
        agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
        agent._execute_parallel_tools = AsyncMock(return_value=[
            {"tool_name": "t1", "params": {}, "output": "ok",
             "verified_kind": "unverified", "verified_evidence": None}
        ])
        agent._react_step = AsyncMock(side_effect=[
            ReActStep(thought="parallel", actions=[ToolCall(tool="t1", params={})],
                      final_answer=None),
            ReActStep(thought="done", final_answer="finished"),
        ])
        agent.world_model.recall_experiences = AsyncMock(return_value={})
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
        agent._record_execution = AsyncMock()

        with patch("core.hallucination_config.is_parallel_tools_enabled", return_value=True):
            result = await agent.execute("do it")
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_execute_tool_execution_and_compression(self):
        agent = _build_agent(_agent_model(), _check_budget_before_react=None)
        agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
        agent._step_act = AsyncMock(return_value="saved to /tmp/scr_1.png")
        agent.world_model.recall_experiences = AsyncMock(return_value={})
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
        agent._record_execution = AsyncMock()

        step1 = ReActStep(thought="navigate", action=ToolCall(tool="browser_navigate", params={}), final_answer=None)
        step2 = ReActStep(thought="done", final_answer="finished")
        agent._react_step = AsyncMock(side_effect=[step1, step2])

        compressor = Mock()
        compressor.compress_tool_output = Mock(return_value=("compressed", SimpleNamespace(savings_tokens=50)))
        with patch("core.llm.compression.get_compression_pipeline", return_value=compressor), \
             patch("os.path.exists", return_value=False):
            result = await agent.execute("do it")
        assert result["status"] == "success"
        assert result["output"] == "finished"

    @pytest.mark.asyncio
    async def test_execute_budget_exceeded_fails_closed(self):
        agent = _build_agent(_agent_model(), _check_budget_before_react=None)
        agent._check_budget_before_react = AsyncMock(return_value={"allowed": False, "reason": "over"})
        agent.world_model.recall_experiences = AsyncMock(return_value={})
        agent._record_execution = AsyncMock()
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])

        result = await agent.execute("do it")
        assert result["status"] == "failed"  # budget_exceeded normalized at boundary

    @pytest.mark.asyncio
    async def test_execute_unexpected_exception(self):
        agent = _build_agent(_agent_model(), _check_budget_before_react=None)
        agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
        agent._react_step = AsyncMock(side_effect=RuntimeError("react boom"))
        agent.world_model.recall_experiences = AsyncMock(return_value={})
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
        agent._record_execution = AsyncMock()

        result = await agent.execute("do it")
        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_execute_audit_mode(self):
        agent = _build_agent(_agent_model(audit_mode=True), _check_budget_before_react=None)
        agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
        agent.world_model.recall_experiences = AsyncMock(return_value={})
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
        agent._record_execution = AsyncMock()
        agent._react_step = AsyncMock(return_value=ReActStep(thought="x", final_answer="ans"))
        result = await agent.execute("do it")
        assert result["status"] == "success"


class TestToolGateAndStepAct:
    @pytest.mark.asyncio
    async def test_disallowed_tool_blocked(self):
        agent = _build_agent(_agent_model(tools=["allowed_tool"]), _check_budget_before_react=None)
        agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
        agent.world_model.recall_experiences = AsyncMock(return_value={})
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
        agent._record_execution = AsyncMock()
        agent._react_step = AsyncMock(side_effect=[
            ReActStep(thought="t", action=ToolCall(tool="evil_tool", params={}), final_answer=None),
            ReActStep(thought="t2", final_answer="done"),
        ])
        result = await agent.execute("do it")
        assert result["status"] == "success

    @pytest.mark.asyncio
    async def test_step_act_governance_denied(self):
        agent = _build_agent(_agent_model())
        gov = AsyncMock()
        gov.can_perform_action_async = AsyncMock(
            return_value={"allowed": False, "reason": "nope", "requires_human_approval": False}
        )
        with patch("core.generic_agent.AgentGovernanceService", return_value=gov), \
             patch("core.generic_agent.get_db_session"):
            out = await agent._step_act("tool1", {"a": 1})
        assert "Governance Error" in out

    @pytest.mark.asyncio
    async def test_step_act_hitl_approved(self):
        agent = _build_agent(_agent_model())
        gov = AsyncMock()
        gov.can_perform_action_async = AsyncMock(
            return_value={"allowed": False, "reason": "approve me", "requires_human_approval": True}
        )
        gov.request_approval = Mock(return_value="act-1")
        agent._wait_for_approval = AsyncMock(return_value=True)
        agent.mcp = Mock()
        agent.mcp.call_tool = AsyncMock(return_value="executed")
        with patch("core.generic_agent.AgentGovernanceService", return_value=gov), \
             patch("core.generic_agent.get_db_session"):
            out = await agent._step_act("tool1", {"a": 1})
        assert out == "executed"

    @pytest.mark.asyncio
    async def test_step_act_hitl_rejected(self):
        agent = _build_agent(_agent_model())
        gov = AsyncMock()
        gov.can_perform_action_async = AsyncMock(
            return_value={"allowed": False, "reason": "approve me", "requires_human_approval": True}
        )
        gov.request_approval = Mock(return_value="act-1")
        agent._wait_for_approval = AsyncMock(return_value=False)
        with patch("core.generic_agent.AgentGovernanceService", return_value=gov), \
             patch("core.generic_agent.get_db_session"):
            out = await agent._step_act("tool1", {"a": 1})
        assert "REJECTED" in out

    @pytest.mark.asyncio
    async def test_step_act_error_mapping(self):
        agent = _build_agent(_agent_model())
        gov = AsyncMock()
        gov.can_perform_action_async = AsyncMock(
            return_value={"allowed": True, "requires_human_approval": False}
        )
        agent.mcp = Mock()
        agent.mcp.call_tool = AsyncMock(side_effect=ValueError("Tool not found"))
        with patch("core.generic_agent.AgentGovernanceService", return_value=gov), \
             patch("core.generic_agent.get_db_session"):
            out = await agent._step_act("ghost", {})
        assert "not found" in out

    @pytest.mark.asyncio
    async def test_wait_for_approval_timeout(self):
        agent = _build_agent(_agent_model(hitl_timeout=0))
        gov = Mock()
        gov.get_approval_status = Mock(return_value={"status": "pending"})
        with patch("core.generic_agent.AgentGovernanceService", return_value=gov), \
             patch("core.generic_agent.get_db_session"):
            assert await agent._wait_for_approval("a1") is False

    @pytest.mark.asyncio
    async def test_wait_for_all_approvals(self):
        agent = _build_agent(_agent_model(hitl_timeout=0))
        gov = Mock()
        gov.get_approval_status = Mock(return_value={"status": "rejected"})
        with patch("core.generic_agent.AgentGovernanceService", return_value=gov), \
             patch("core.generic_agent.get_db_session"):
            assert await agent._wait_for_all_approvals(["a1"]) is False


class TestParallelTools:
    @pytest.mark.asyncio
    async def test_parallel_tools_blocked_batch(self):
        agent = _build_agent(_agent_model())
        gov = AsyncMock()
        gov.can_perform_action_async = AsyncMock(
            return_value={"allowed": False, "reason": "blocked", "requires_human_approval": False}
        )
        with patch("core.hallucination_config.is_parallel_tools_enabled", return_value=True), \
             patch("core.hallucination_config.get_max_parallel_tools", return_value=2), \
             patch("core.generic_agent.AgentGovernanceService", return_value=gov), \
             patch("core.generic_agent.get_db_session"):
            records = await agent._execute_parallel_tools(
                [ToolCall(tool="a", params={}), ToolCall(tool="b", params={})], {}, None)
        assert records[0]["verified_kind"] == "blocked"

    @pytest.mark.asyncio
    async def test_parallel_tools_sequential_fallback(self):
        agent = _build_agent(_agent_model())
        agent._step_act = AsyncMock(return_value="ran")
        with patch("core.hallucination_config.is_parallel_tools_enabled", return_value=False), \
             patch("core.hallucination_config.get_max_parallel_tools", return_value=1):
            records = await agent._execute_parallel_tools(
                [ToolCall(tool="a", params={})], {}, None)
        assert records[0]["output"] == "ran"

    @pytest.mark.asyncio
    async def test_parallel_tools_rejected_batch(self):
        agent = _build_agent(_agent_model())
        gov = AsyncMock()
        gov.can_perform_action_async = AsyncMock(
            return_value={"allowed": False, "reason": "approve", "requires_human_approval": True}
        )
        gov.request_approval = Mock(return_value="a1")
        agent._wait_for_all_approvals = AsyncMock(return_value=False)
        with patch("core.hallucination_config.is_parallel_tools_enabled", return_value=True), \
             patch("core.hallucination_config.get_max_parallel_tools", return_value=2), \
             patch("core.generic_agent.AgentGovernanceService", return_value=gov), \
             patch("core.generic_agent.get_db_session"):
            records = await agent._execute_parallel_tools(
                [ToolCall(tool="a", params={}), ToolCall(tool="b", params={})], {}, None)
        assert records[0]["verified_kind"] == "rejected"

    @pytest.mark.asyncio
    async def test_parallel_tools_success_batch(self):
        agent = _build_agent(_agent_model())
        gov = AsyncMock()
        gov.can_perform_action_async = AsyncMock(
            return_value={"allowed": True, "requires_human_approval": False}
        )
        agent._step_act = AsyncMock(return_value="ok")
        agent.mcp.search_tools = AsyncMock(return_value=[{"name": "found"}])
        with patch("core.hallucination_config.is_parallel_tools_enabled", return_value=True), \
             patch("core.hallucination_config.get_max_parallel_tools", return_value=2), \
             patch("core.generic_agent.AgentGovernanceService", return_value=gov), \
             patch("core.generic_agent.get_db_session"):
            records = await agent._execute_parallel_tools(
                [ToolCall(tool="a", params={}), ToolCall(tool="mcp_tool_search", params={"query": "q"})],
                {}, None)
        assert len(records) == 2
        assert records[0]["output"] == "ok"
        assert "Found 1 new tools" in records[1]["output"]


class TestPromptHelpers:
    def test_workspace_context_block(self):
        agent = _build_agent(_agent_model())
        agent.workspace_id = "ws-1"
        workspace = SimpleNamespace(metadata_json={
            "curated_context": ["Fact A", "Fact B"]
        })
        db = Mock()
        calls = {"n": 0}

        def _query(m):
            calls["n"] += 1
            if calls["n"] == 1:
                q = Mock()
                q.filter.return_value.first.return_value = workspace
                return q
            q2 = Mock()
            q2.join.return_value.filter.return_value.all.return_value = [("Skill1",)]
            return q2

        db.query = Mock(side_effect=_query)
        with patch("core.generic_agent.get_db_session") as gds:
            gds.return_value.__enter__.return_value = db
            out = agent._workspace_context_block()
        assert "WORKSPACE CURATED CONTEXT" in out
        assert "WORKSPACE-ASSIGNED SKILLS" in out

    def test_workspace_context_block_empty_and_error(self):
        agent = _build_agent(_agent_model())
        assert agent._workspace_context_block() == ""  # default workspace -> ""
        agent.workspace_id = "ws-2"
        with patch("core.generic_agent.get_db_session") as gds:
            gds.return_value.__enter__.side_effect = RuntimeError("db down")
            assert agent._workspace_context_block() == ""

    def test_retrieve_skill_instructions(self):
        agent = _build_agent(_agent_model())
        with patch("core.hallucination_config.is_skill_injection_enabled", return_value=False):
            assert agent._retrieve_skill_instructions("task") == ""
        with patch("core.hallucination_config.is_skill_injection_enabled", return_value=True), \
             patch("core.skill_retrieval_service.get_skill_retrieval_service") as srs:
            srs.return_value.retrieve_top_skills = Mock(return_value="SKILLS")
            with patch("core.generic_agent.get_db_session"):
                assert agent._retrieve_skill_instructions("task") == "SKILLS"
        with patch("core.hallucination_config.is_skill_injection_enabled", return_value=True), \
             patch("core.skill_retrieval_service.get_skill_retrieval_service",
                   side_effect=RuntimeError("boom")):
            assert agent._retrieve_skill_instructions("task") == ""

    def test_react_step_fallback_parse(self):
        agent = _build_agent(_agent_model())
        agent.mcp = Mock()
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        agent.reflection_service = Mock()
        agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
        agent.llm = AsyncMock()
        agent.llm.generate_structured = AsyncMock(return_value=None)
        agent.llm.generate = AsyncMock(return_value="Final answer: done")
        out = asyncio.run(agent._react_step("t", {}, "", {}))
        assert out.final_answer == "Final answer: done"

        agent.llm.generate = AsyncMock(return_value="")
        out2 = asyncio.run(agent._react_step("t", {}, "", {}))
        assert out2.final_answer == "Unable to process - LLM not configured."

    def test_react_step_memory_sections(self):
        agent = _build_agent(_agent_model())
        agent.mcp = Mock()
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        agent.reflection_service = Mock()
        agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
        agent.llm = AsyncMock()
        agent.llm.generate_structured = AsyncMock(return_value=None)
        agent.llm.generate = AsyncMock(return_value="answer: x")
        memory = {
            "experiences": [{"input_summary": "E", "outcome": "Success"}],
            "knowledge": [{"text": "K"}],
            "formulas": [{"name": "F", "description": "d"}],
            "business_facts": [SimpleNamespace(verification_status="verified", fact="Fact",
                                               metadata={"source": "src"})],
        }
        out = asyncio.run(agent._react_step("t", memory, "", {}, {"canvas_id": "c1"}))
        assert out is not None

    def test_get_registry_model(self):
        agent = _build_agent(_agent_model())
        reg = agent._get_registry_model()
        assert reg.id == "agent-123"
        assert reg.name == "Test Agent"
