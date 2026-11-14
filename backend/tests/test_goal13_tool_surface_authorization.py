"""Goal 13 — advertised specialist tool surface must stay inside the
authorization gates that dispatch actually enforces.

Evidence (2026-11-13): a recruited fleet specialist (AgentRegistry status
``intern``, capabilities ``["sales"]``) was shown an 11-tool AVAILABLE TOOLS
catalog while only 5 passed P2 and none passed the default-on P9 sandbox tier
whitelist. The model burned every ReAct step on ``mcp_tool_search`` /
``documents.grep`` / invented tools, and the run ended
``max_steps_exceeded`` with "Maximum steps reached without final answer."
instead of a business answer.

These tests pin the advertisement/authorization alignment. They do NOT loosen
any gate: ``mcp_service.call_tool`` remains the enforcer, and the sandbox
whitelist still blocks dotted actions at INTERN.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.capability_resolver import (
    build_dispatch_tool_predicate,
    is_tool_allowed,
    resolve_allowed_tools,
)
from core.generic_agent import GenericAgent, _dispatch_denial_note
from core.models import AgentRegistry
from core.react_models import ReActStep, ToolCall


def _intern_specialist(**overrides):
    fields = dict(
        id="spec-sales",
        name="Sales Analyst",
        category="Sales",
        module_path="core.generic_agent",
        class_name="GenericAgent",
        status="intern",
        enabled=True,
        capabilities=["sales"],
        specialty="sales",
        configuration={"tools": "*", "max_steps": 4},
    )
    fields.update(overrides)
    return AgentRegistry(**fields)


def _agent_with(mock_mcp, mock_llm, agent_model):
    reflection = MagicMock()
    reflection.get_relevant_critiques = AsyncMock(return_value=[])
    reflection.add_critique = AsyncMock(return_value=None)
    with patch("core.generic_agent.WorldModelService"), \
         patch("core.generic_agent.ReflectionService",
               return_value=reflection), \
         patch("core.generic_agent.CanvasSummaryService"), \
         patch("core.generic_agent.mcp_service", mock_mcp), \
         patch("core.generic_agent.LLMService", return_value=mock_llm):
        return GenericAgent(agent_model, workspace_id="w")


def _mock_llm():
    llm = AsyncMock()
    llm.generate_structured.return_value = ReActStep(
        thought="done", final_answer="answer")
    handler = MagicMock()
    handler.analyze_query_complexity.return_value = MagicMock(value="simple")
    llm._get_handler = MagicMock(return_value=handler)
    llm.generate.return_value = None
    return llm


def _catalog_block(system_prompt: str) -> str:
    """The AVAILABLE TOOLS section only (not incidental prompt mentions)."""
    start = system_prompt.index("AVAILABLE TOOLS:")
    end = system_prompt.index("\n\nFORMAT:", start)
    return system_prompt[start:end]


# ============================================================================
# The dispatch-authority predicate mirrors BOTH gates
# ============================================================================

class TestDispatchToolPredicate:
    def test_intern_specialist_is_denied_registered_dotted_action_by_sandbox(self):
        """P2 admits documents.* via the action-registry rule; the default-on
        P9 tier whitelist does not. Advertising it was the Goal-13 loop."""
        agent = _intern_specialist()
        allowed = resolve_allowed_tools(agent, tier="intern")
        # P2 alone admits the registered dotted action...
        assert is_tool_allowed(allowed, "documents.grep") is True

        predicate = build_dispatch_tool_predicate(agent, tier="intern")
        # ...but dispatch refuses it, so it must not be advertised.
        assert predicate("documents.grep") is False
        assert predicate("mcp_tool_search") is False
        assert predicate("save_business_fact") is False

    def test_tools_on_both_allowlists_stay_advertisable(self):
        agent = _intern_specialist(
            capabilities=["memory_remember", "operator_get_status"])
        predicate = build_dispatch_tool_predicate(agent, tier="intern")
        assert predicate("memory_remember") is True
        assert predicate("operator_get_status") is True

    def test_capability_narrowing_still_wins(self):
        agent = _intern_specialist(capabilities=["memory_remember"])
        predicate = build_dispatch_tool_predicate(agent, tier="intern")
        assert predicate("memory_remember") is True
        # In the sandbox floor, but not in the agent's declared capabilities.
        assert predicate("memory_search") is False

    def test_autonomous_unrestricted_is_unchanged(self):
        agent = _intern_specialist(status="autonomous", capabilities=[])
        predicate = build_dispatch_tool_predicate(agent, tier="autonomous")
        assert predicate("anything_at_all") is True
        assert predicate("mcp_tool_search") is True

    def test_disabling_sandbox_removes_only_the_sandbox_leg(self, monkeypatch):
        monkeypatch.setattr(
            "core.sandbox_config.is_sandbox_enabled", lambda: False)
        agent = _intern_specialist()
        predicate = build_dispatch_tool_predicate(agent, tier="intern")
        # P2's dotted-action rule now stands alone.
        assert predicate("documents.grep") is True
        # P2 itself has no wildcard here, so search stays denied.
        assert predicate("mcp_tool_search") is False


# ============================================================================
# _react_step advertises only dispatchable tools
# ============================================================================

CORE_CATALOG = [
    {"name": "documents.search", "description": "search"},
    {"name": "documents.ls", "description": "ls"},
    {"name": "documents.cat", "description": "cat"},
    {"name": "documents.read", "description": "read"},
    {"name": "documents.grep", "description": "grep"},
    {"name": "ingest_knowledge_from_text", "description": "ingest"},
    {"name": "save_business_fact", "description": "fact"},
    {"name": "verify_citation", "description": "cite"},
    {"name": "get_system_health", "description": "health"},
    {"name": "request_human_intervention", "description": "hitl"},
]


class TestAdvertisedSurface:
    @pytest.mark.asyncio
    async def test_no_authorized_tool_renders_truthful_no_tools_contract(self):
        agent_model = _intern_specialist()
        mock_mcp = AsyncMock()
        mock_mcp.get_all_tools.return_value = list(CORE_CATALOG)
        mock_llm = _mock_llm()
        agent = _agent_with(mock_mcp, mock_llm, agent_model)
        agent._dispatch_tool_allowed = build_dispatch_tool_predicate(
            agent_model, tier="intern")

        await agent._react_step("diagnose shortfall", {}, "", {"optimization": {}})

        system_prompt = mock_llm.generate_structured.call_args.kwargs[
            "system_instruction"]
        assert "AVAILABLE TOOLS: none." in system_prompt
        assert "No tool is authorized" in system_prompt
        # The refused discovery tool must not be offered or pointed at.
        assert "mcp_tool_search" not in system_prompt
        # Broad capability claims are false with no authorized tool.
        assert "ORCHESTRATION POWERS" not in system_prompt
    @pytest.mark.asyncio
    async def test_catalog_lists_only_tools_both_gates_admit(self):
        agent_model = _intern_specialist(
            capabilities=["memory_remember"],
            configuration={
                "tools": ["memory_remember", "save_business_fact"],
                "max_steps": 4,
            },
        )
        mock_mcp = AsyncMock()
        mock_mcp.get_all_tools.return_value = [
            {"name": "memory_remember", "description": "remember"},
            {"name": "save_business_fact", "description": "fact"},
            {"name": "mcp_tool_search", "description": "search"},
        ]
        mock_llm = _mock_llm()
        agent = _agent_with(mock_mcp, mock_llm, agent_model)
        agent._dispatch_tool_allowed = build_dispatch_tool_predicate(
            agent_model, tier="intern")

        await agent._react_step("remember this", {}, "", {"optimization": {}})

        system_prompt = mock_llm.generate_structured.call_args.kwargs[
            "system_instruction"]
        catalog = _catalog_block(system_prompt)
        assert '"memory_remember"' in catalog
        assert "save_business_fact" not in catalog
        assert "mcp_tool_search" not in catalog
        # The full powers text would re-advertise refused tools.
        assert "ORCHESTRATION POWERS (limited" in system_prompt

    @pytest.mark.asyncio
    async def test_unresolved_identity_keeps_legacy_surface(self):
        """No governance row -> no advertisement filter (dispatch gates still
        run). This is the backward-compatible path for callers without an
        agent identity."""
        agent_model = _intern_specialist()
        mock_mcp = AsyncMock()
        mock_mcp.get_all_tools.return_value = list(CORE_CATALOG)
        mock_llm = _mock_llm()
        agent = _agent_with(mock_mcp, mock_llm, agent_model)
        # Leave agent._dispatch_tool_allowed at its default (None).

        await agent._react_step("diagnose", {}, "", {"optimization": {}})

        system_prompt = mock_llm.generate_structured.call_args.kwargs[
            "system_instruction"]
        assert "mcp_tool_search" in system_prompt


# ============================================================================
# Denied dispatches cannot be retried into success
# ============================================================================

class TestDispatchDenialNote:
    def test_capability_gate_refusal_is_explained(self):
        note = _dispatch_denial_note(
            "mcp_tool_search",
            {"success": False,
             "error": "Tool 'mcp_tool_search' is not allowed for this agent",
             "blocked_by": "capability_gate"})
        assert "TOOL DENIED" in note
        assert "Do not request it again" in note

    def test_sandbox_refusal_is_explained(self):
        note = _dispatch_denial_note(
            "documents.grep",
            "Sandbox blocked: tool 'documents.grep' not in policy whitelist")
        assert "TOOL DENIED" in note
        assert "sandbox" in note

    def test_ordinary_tool_error_is_not_mislabeled(self):
        assert _dispatch_denial_note(
            "documents.grep", "Error: no matches found") == ""
        assert _dispatch_denial_note(
            "documents.grep", {"success": False, "error": "timeout"}) == ""

    @pytest.mark.asyncio
    async def test_denial_then_answer_ends_with_final_answer_not_max_steps(self):
        """Reproduces the Goal-13 shape: step 1 is refused by the capability
        gate; step 2 must see the deterministic denial note and answer."""
        agent_model = _intern_specialist(configuration={"max_steps": 2})
        denied = {
            "success": False,
            "error": "Tool 'mcp_tool_search' is not allowed for this agent",
            "blocked_by": "capability_gate",
        }
        mock_mcp = AsyncMock()
        mock_mcp.get_all_tools.return_value = []
        mock_mcp.call_tool.return_value = denied

        mock_world_model = AsyncMock()
        mock_world_model.recall_experiences.return_value = {}
        mock_reflection = AsyncMock()
        mock_reflection.get_relevant_critiques.return_value = []
        mock_reflection.generate_critique.return_value = None

        mock_llm = _mock_llm()
        prompts = []

        async def generate(**kwargs):
            prompts.append(kwargs.get("prompt") or "")
            if len(prompts) == 1:
                return ReActStep(
                    thought="search for a tool",
                    action=ToolCall(tool="mcp_tool_search", params={}))
            return ReActStep(
                thought="answer from supplied figures",
                final_answer="Shortfall is 42000 USD.")

        mock_llm.generate_structured.side_effect = generate

        mock_gov_cls = MagicMock()
        mock_gov_cls.return_value.can_perform_action_async = AsyncMock(
            return_value={"allowed": True,
                          "requires_human_approval": False})
        mock_gov_cls.return_value.record_outcome = AsyncMock(return_value=None)

        with patch("core.generic_agent.WorldModelService",
                   return_value=mock_world_model), \
             patch("core.generic_agent.ReflectionService",
                   return_value=mock_reflection), \
             patch("core.generic_agent.CanvasSummaryService"), \
             patch("core.generic_agent.mcp_service", mock_mcp), \
             patch("core.generic_agent.LLMService", return_value=mock_llm), \
             patch("core.generic_agent.AgentGovernanceService", mock_gov_cls), \
             patch.object(GenericAgent, "_check_budget_before_react",
                          new=AsyncMock(return_value={"allowed": True})):
            agent = GenericAgent(agent_model, workspace_id="w")
            result = await agent.execute("diagnose shortfall")

        assert result["status"] == "success"
        assert result["output"] == "Shortfall is 42000 USD."
        assert len(prompts) == 2
        assert "[TOOL DENIED]" in prompts[1]
        assert "Do not request it again" in prompts[1]
