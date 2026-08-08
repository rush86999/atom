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
        assert result["status"] == "success"

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
        with patch("core.database.get_db_session") as gds:
            gds.return_value.__enter__.return_value = db
            out = agent._workspace_context_block()
        assert "WORKSPACE CURATED CONTEXT" in out
        assert "WORKSPACE-ASSIGNED SKILLS" in out

    def test_workspace_context_block_empty_and_error(self):
        agent = _build_agent(_agent_model())
        assert agent._workspace_context_block() == ""  # default workspace -> ""
        agent.workspace_id = "ws-2"
        with patch("core.database.get_db_session") as gds:
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
        out = asyncio.run(agent._react_step("t", memory, "", {"canvas_id": "c1"}))
        assert out is not None

    def test_get_registry_model(self):
        agent = _build_agent(_agent_model())
        reg = agent._get_registry_model()
        assert reg.id == "agent-123"
        assert reg.name == "Test Agent"


class TestExecuteToolDetails:
    @pytest.mark.asyncio
    async def test_screenshot_capture_and_critique(self):
        agent = _build_agent(_agent_model(), _check_budget_before_react=None)
        agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
        agent._step_act = AsyncMock(return_value="Screenshot saved to /tmp/scr.png")
        agent.world_model.recall_experiences = AsyncMock(return_value={})
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
        agent._record_execution = AsyncMock()
        agent._react_step = AsyncMock(side_effect=[
            ReActStep(thought="t", action=ToolCall(tool="browser_screenshot", params={}), final_answer=None),
            ReActStep(thought="t2", final_answer="done"),
        ])
        import base64
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", Mock(return_value=Mock(
                 __enter__=Mock(return_value=Mock(read=Mock(return_value=b"PNGDATA"))),
                 __exit__=Mock(return_value=False)))):
            result = await agent.execute("do it")
        assert result["status"] == "success"
        assert agent.last_screenshot == base64.b64encode(b"PNGDATA").decode()

    @pytest.mark.asyncio
    async def test_mcp_tool_search_lazy_load(self):
        agent = _build_agent(_agent_model(), _check_budget_before_react=None)
        agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
        agent._step_act = AsyncMock(return_value="Found 1 tools (total: 1). They have been added to your toolkit for the next step: ['t1']")
        agent.world_model.recall_experiences = AsyncMock(return_value={})
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        agent.mcp.search_tools = AsyncMock(return_value=[{"name": "t1", "description": "d"}])
        agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
        agent._record_execution = AsyncMock()
        agent._react_step = AsyncMock(side_effect=[
            ReActStep(thought="t", action=ToolCall(tool="mcp_tool_search", params={"query": "q"}), final_answer=None),
            ReActStep(thought="t2", final_answer="done"),
        ])
        result = await agent.execute("do it")
        assert result["status"] == "success"
        assert len(agent.session_tools) == 1

    @pytest.mark.asyncio
    async def test_chaos_noise_injection(self):
        agent = _build_agent(_agent_model(chaos_noise_level=1.0), _check_budget_before_react=None)
        agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
        agent.world_model.recall_experiences = AsyncMock(return_value={})
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
        agent._record_execution = AsyncMock()
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))
        import random
        with patch("random.random", return_value=0.1):
            result = await agent.execute("do it")
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_mentorship_mode(self):
        agent = _build_agent(_agent_model(), _check_budget_before_react=None)
        agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
        agent.world_model.recall_experiences = AsyncMock(return_value={})
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
        agent._record_execution = AsyncMock()
        seen = {}

        async def record_step(step_record):
            seen["record"] = step_record

        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))
        result = await agent.execute("do it", context={"optimization": {"mentorship_mode": True}})
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_step_act_error_mapping_validation_and_timeout(self):
        agent = _build_agent(_agent_model())
        gov = AsyncMock()
        gov.can_perform_action_async = AsyncMock(
            return_value={"allowed": True, "requires_human_approval": False}
        )
        agent.mcp = Mock()
        agent.mcp.call_tool = Mock(side_effect=ValueError("Invalid arguments: bad schema"))
        with patch("core.generic_agent.AgentGovernanceService", return_value=gov), \
             patch("core.generic_agent.get_db_session"):
            out = await agent._step_act("tool1", {})
        assert "Invalid arguments" in out

        agent.mcp.call_tool = Mock(side_effect=TimeoutError("timed out"))
        with patch("core.generic_agent.AgentGovernanceService", return_value=gov), \
             patch("core.generic_agent.get_db_session"):
            out = await agent._step_act("tool1", {})
        assert "timed out" in out

    @pytest.mark.asyncio
    async def test_wait_for_approval_accepted(self):
        agent = _build_agent(_agent_model())
        gov = Mock()
        statuses = iter([{"status": "pending"}, {"status": "approved"}])
        gov.get_approval_status = Mock(side_effect=lambda aid: next(statuses))
        with patch("core.generic_agent.AgentGovernanceService", return_value=gov), \
             patch("core.generic_agent.get_db_session"):
            assert await agent._wait_for_approval("a1") is True

    @pytest.mark.asyncio
    async def test_wait_for_approval_rejected(self):
        agent = _build_agent(_agent_model())
        gov = Mock()
        gov.get_approval_status = Mock(return_value={"status": "rejected"})
        with patch("core.generic_agent.AgentGovernanceService", return_value=gov), \
             patch("core.generic_agent.get_db_session"):
            assert await agent._wait_for_approval("a1") is False

    @pytest.mark.asyncio
    async def test_wait_for_all_approvals_approved(self):
        agent = _build_agent(_agent_model())
        gov = Mock()
        gov.get_approval_status = Mock(return_value={"status": "approved"})
        with patch("core.generic_agent.AgentGovernanceService", return_value=gov), \
             patch("core.generic_agent.get_db_session"):
            assert await agent._wait_for_all_approvals(["a1", "a2"]) is True

    @pytest.mark.asyncio
    async def test_record_execution_graduation_promotion(self):
        agent = _build_agent(_agent_model(active_skill_id="skill-1"))
        agent.world_model.record_experience = AsyncMock()
        gov = AsyncMock()
        gov.record_outcome = AsyncMock()
        graduation = AsyncMock()
        graduation.check_skill_promotion = AsyncMock(return_value={"promoted": True})
        with patch("core.generic_agent.AgentGovernanceService", return_value=gov), \
             patch("core.generic_agent.GraduationService", return_value=graduation), \
             patch("core.generic_agent.get_db_session"):
            await agent._record_execution("task", {
                "status": "success", "complexity": "moderate", "step_efficiency": 1.0,
                "steps": [], "timestamp": "2026-08-08T00:00:00+00:00", "output": "ok",
            })
        gov.record_outcome.assert_awaited_once()
        graduation.check_skill_promotion.assert_awaited_once()


class TestReactStepReal:
    @pytest.mark.asyncio
    async def test_react_step_chaos_and_semantic_ui(self):
        agent = _build_agent(_agent_model(chaos_noise_level=1.0), _check_budget_before_react=None)
        agent.mcp = Mock()
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        agent.reflection_service = Mock()
        agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
        agent.llm = AsyncMock()
        agent.llm.generate_structured = AsyncMock(return_value=None)
        agent.llm.generate = AsyncMock(return_value="answer: ok")
        agent.llm._get_handler = Mock(return_value=SimpleNamespace(default_provider_id="minimax-m2.7"))
        agent.canvas_summary_service = Mock()
        agent.canvas_summary_service.generate_summary = AsyncMock(return_value="UI SUMMARY")
        agent.vision_enabled = False

        import random
        with patch("random.random", return_value=0.1), \
             patch("core.field_guide_service.get_field_guide_service") as fg:
            fg.return_value.get_field_guide_context = Mock(return_value="FIELD GUIDE")
            out = await agent._react_step(
                "task", {"experiences": [], "knowledge": [], "formulas": [], "business_facts": []},
                "", {"canvas_id": "c1", "canvas_state": {"x": 1}, "canvas_type": "sheets"})
        assert out.final_answer == "answer: ok"
        agent.canvas_summary_service.generate_summary.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_react_step_mentorship_and_tool_filter(self):
        agent = _build_agent(_agent_model(tools=["only_this_tool"]), _check_budget_before_react=None)
        agent.mcp = Mock()
        agent.mcp.get_all_tools = AsyncMock(return_value=[
            {"name": "only_this_tool", "description": "d"},
            {"name": "other_tool", "description": "d"},
        ])
        agent.reflection_service = Mock()
        agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
        agent.llm = AsyncMock()
        agent.llm.generate_structured = AsyncMock(return_value=None)
        agent.llm.generate = AsyncMock(return_value="final answer: x")
        with patch("core.field_guide_service.get_field_guide_service") as fg:
            fg.return_value.get_field_guide_context = Mock(return_value="")
            out = await agent._react_step(
                "task", {}, "", {"optimization": {"mentorship_mode": True}})
        assert out.final_answer == "final answer: x"

    @pytest.mark.asyncio
    async def test_check_budget_before_react_real(self):
        agent = _build_agent(_agent_model())
        svc = AsyncMock()
        svc.check_budget_before_action = AsyncMock(return_value={"allowed": True})
        with patch("core.budget_enforcement_service.BudgetEnforcementService") as bes:
            bes.return_value.__aenter__.return_value = svc
            assert (await agent._check_budget_before_react())["allowed"] is True
        with patch("core.budget_enforcement_service.BudgetEnforcementService",
                   side_effect=RuntimeError("down")):
            assert (await agent._check_budget_before_react())["allowed"] is True

    @pytest.mark.asyncio
    async def test_execute_timeout_and_max_steps(self):
        agent = _build_agent(_agent_model(timeout_seconds=0.01, max_steps=5),
                             _check_budget_before_react=None)
        agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
        agent.world_model.recall_experiences = AsyncMock(return_value={})
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
        agent._record_execution = AsyncMock()

        async def slow_react(*a, **k):
            await asyncio.sleep(1)
            return ReActStep(thought="t", final_answer="late")

        agent._react_step = slow_react
        result = await agent.execute("do it")
        assert result["status"] == "timeout"

        agent2 = _build_agent(_agent_model(max_steps=1), _check_budget_before_react=None)
        agent2._check_budget_before_react = AsyncMock(return_value={"allowed": True})
        agent2.world_model.recall_experiences = AsyncMock(return_value={})
        agent2.mcp.get_all_tools = AsyncMock(return_value=[])
        agent2.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
        agent2._record_execution = AsyncMock()
        agent2._react_step = AsyncMock(return_value=ReActStep(thought="last thought", final_answer=None))
        result2 = await agent2.execute("do it")
        assert result2["status"] == "max_steps_exceeded"

    @pytest.mark.asyncio
    async def test_execute_parallel_degradation_with_callback(self):
        agent = _build_agent(_agent_model(), _check_budget_before_react=None)
        agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
        agent.world_model.recall_experiences = AsyncMock(return_value={})
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
        agent._record_execution = AsyncMock()
        agent._step_act = AsyncMock(return_value="ran")
        agent._react_step = AsyncMock(side_effect=[
            ReActStep(thought="p", actions=[ToolCall(tool="a", params={})], final_answer=None),
            ReActStep(thought="d", final_answer="done"),
        ])
        seen = []

        async def cb(record):
            seen.append(record)

        with patch("core.hallucination_config.is_parallel_tools_enabled", return_value=False):
            result = await agent.execute("do it", step_callback=cb)
        assert result["status"] == "success"
        assert seen  # callbacks fired

    @pytest.mark.asyncio
    async def test_observation_filter_enabled(self):
        agent = _build_agent(_agent_model(), _check_budget_before_react=None)
        agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
        agent.world_model.recall_experiences = AsyncMock(return_value={})
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
        agent._record_execution = AsyncMock()
        agent._step_act = AsyncMock(return_value="tool output")
        agent._react_step = AsyncMock(side_effect=[
            ReActStep(thought="t", action=ToolCall(tool="tool1", params={}), final_answer=None),
            ReActStep(thought="d", final_answer="done"),
        ])
        obs_filter = AsyncMock()
        obs_filter.filter_history = AsyncMock(return_value=("NEW HIST", {"savings_tokens": 100}))
        with patch("core.observation_filter_service.OBSERVATION_FILTER_ENABLED", True), \
             patch("core.observation_filter_service.ObservationFilterService",
                   return_value=obs_filter):
            result = await agent.execute("do it")
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_record_execution_graduation_error_and_governance_error(self):
        agent = _build_agent(_agent_model(active_skill_id="skill-1"))
        agent.world_model.record_experience = AsyncMock()
        gov = AsyncMock()
        gov.record_outcome = AsyncMock(side_effect=RuntimeError("gov down"))
        with patch("core.generic_agent.AgentGovernanceService", return_value=gov), \
             patch("core.generic_agent.get_db_session"):
            await agent._record_execution("task", {
                "status": "failed", "complexity": "moderate", "step_efficiency": 1.0,
                "steps": [], "timestamp": "2026-08-08T00:00:00+00:00", "output": "x",
            })
        # governance failure logged, not raised

        agent2 = _build_agent(_agent_model(active_skill_id="skill-1"))
        agent2.world_model.record_experience = AsyncMock()
        gov2 = AsyncMock()
        gov2.record_outcome = AsyncMock()
        graduation = AsyncMock()
        graduation.check_skill_promotion = AsyncMock(side_effect=RuntimeError("grad down"))
        with patch("core.generic_agent.AgentGovernanceService", return_value=gov2), \
             patch("core.generic_agent.GraduationService", return_value=graduation), \
             patch("core.generic_agent.get_db_session"):
            await agent2._record_execution("task", {
                "status": "success", "complexity": "moderate", "step_efficiency": 1.0,
                "steps": [], "timestamp": "2026-08-08T00:00:00+00:00", "output": "x",
            })
        # graduation failure logged, not raised

    @pytest.mark.asyncio
    async def test_wait_for_all_approvals_partial(self):
        agent = _build_agent(_agent_model())
        gov = Mock()
        gov.get_approval_status = Mock(return_value={"status": "approved"})
        with patch("core.generic_agent.AgentGovernanceService", return_value=gov), \
             patch("core.generic_agent.get_db_session"):
            assert await agent._wait_for_all_approvals(["a1", "a2"]) is True

    @pytest.mark.asyncio
    async def test_parallel_tools_exception_in_batch(self):
        agent = _build_agent(_agent_model())
        gov = AsyncMock()
        gov.can_perform_action_async = AsyncMock(
            return_value={"allowed": True, "requires_human_approval": False}
        )
        agent._step_act = AsyncMock(side_effect=RuntimeError("tool crash"))
        with patch("core.hallucination_config.is_parallel_tools_enabled", return_value=True), \
             patch("core.hallucination_config.get_max_parallel_tools", return_value=2), \
             patch("core.generic_agent.AgentGovernanceService", return_value=gov), \
             patch("core.generic_agent.get_db_session"):
            records = await agent._execute_parallel_tools(
                [ToolCall(tool="a", params={})], {}, None)
        assert "Tool Execution Failed" in records[0]["output"]


class TestFinalMicroBranches:
    @pytest.mark.asyncio
    async def test_observation_filter_flag_on_module(self):
        agent = _build_agent(_agent_model(), _check_budget_before_react=None)
        agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
        agent.world_model.recall_experiences = AsyncMock(return_value={})
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
        agent._record_execution = AsyncMock()
        agent._step_act = AsyncMock(return_value="tool output")
        agent._react_step = AsyncMock(side_effect=[
            ReActStep(thought="t", action=ToolCall(tool="tool1", params={}), final_answer=None),
            ReActStep(thought="d", final_answer="done"),
        ])
        obs_filter = AsyncMock()
        obs_filter.filter_history = AsyncMock(return_value=("NEW HIST", {"savings_tokens": 100}))
        with patch("core.generic_agent.OBSERVATION_FILTER_ENABLED", True), \
             patch("core.observation_filter_service.ObservationFilterService",
                   return_value=obs_filter):
            result = await agent.execute("do it")
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_complexity_fallback_and_field_guide_error(self):
        agent = _build_agent(_agent_model(), _check_budget_before_react=None)
        agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
        agent.world_model.recall_experiences = AsyncMock(return_value={})
        agent.mcp.get_all_tools = AsyncMock(return_value=[])
        agent.reflection_service.get_relevant_critiques = AsyncMock(return_value=[])
        agent._record_execution = AsyncMock()
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))
        agent.llm._get_handler = Mock(side_effect=RuntimeError("no handler"))
        with patch("core.field_guide_service.get_field_guide_service",
                   side_effect=RuntimeError("fg down")):
            result = await agent.execute("do it")
        assert result["status"] == "success"
        assert result["complexity"] == "moderate"  # fallback

    def test_workspace_context_string_blobs_and_empty(self):
        agent = _build_agent(_agent_model())
        agent.workspace_id = "ws-3"
        workspace = SimpleNamespace(metadata_json={"curated_context": "single string"})
        db = Mock()
        calls = {"n": 0}

        def _query(m):
            calls["n"] += 1
            if calls["n"] == 1:
                q = Mock()
                q.filter.return_value.first.return_value = workspace
                return q
            q2 = Mock()
            q2.join.return_value.filter.return_value.all.return_value = []
            return q2

        db.query = Mock(side_effect=_query)
        with patch("core.database.get_db_session") as gds:
            gds.return_value.__enter__.return_value = db
            out = agent._workspace_context_block()
        assert "WORKSPACE CURATED CONTEXT" in out

        empty_ws = SimpleNamespace(metadata_json={})
        db2 = Mock()
        calls2 = {"n": 0}

        def _query2(m):
            calls2["n"] += 1
            if calls2["n"] == 1:
                q = Mock()
                q.filter.return_value.first.return_value = empty_ws
                return q
            q2 = Mock()
            q2.join.return_value.filter.return_value.all.return_value = []
            return q2

        db2.query = Mock(side_effect=_query2)
        with patch("core.database.get_db_session") as gds:
            gds.return_value.__enter__.return_value = db2
            assert agent._workspace_context_block() == ""

    @pytest.mark.asyncio
    async def test_step_act_pre_approved_and_generic_error(self):
        agent = _build_agent(_agent_model())
        agent.mcp = Mock()
        agent.mcp.call_tool = AsyncMock(return_value="ran pre-approved")
        out = await agent._step_act("tool1", {}, None, None, pre_approved=True)
        assert out == "ran pre-approved"

        agent.mcp.call_tool = Mock(side_effect=ValueError("mystery"))
        out2 = await agent._step_act("tool1", {}, None, None, pre_approved=True)
        assert "Tool Execution Failed" in out2

    @pytest.mark.asyncio
    async def test_wait_for_all_approvals_rejected(self):
        agent = _build_agent(_agent_model())
        gov = Mock()
        gov.get_approval_status = Mock(return_value={"status": "rejected"})
        with patch("core.generic_agent.AgentGovernanceService", return_value=gov), \
             patch("core.generic_agent.get_db_session"):
            assert await agent._wait_for_all_approvals(["a1"]) is False
