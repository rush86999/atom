"""
P2 — Agent Capability Bindings tests (G2, tool-level).

Per-agent zero-trust tool scoping enforced at the dispatch layer
(``integrations/mcp_service.call_tool``), NOT only in the agent loop. An agent's
resolved tool set is the intersection of its declared ``capabilities`` with its
tier floor (``TIER_FLOOR_TOOL_WHITELISTS``). Backward-compatible:
``capabilities = []`` or ``["*"]`` (the column default) preserves the current
unrestricted behavior.

This closes the gap that ``generic_agent.py:249`` is an agent-loop-only check,
bypassed by workflow / meta-agent / fleet dispatch paths — all of which route
through ``call_tool``.
"""
import pytest
from unittest.mock import MagicMock


# ============================================================================
# resolve_allowed_tools
# ============================================================================

class TestResolveAllowedTools:
    def test_default_empty_capabilities_bounded_by_tier_floor(self):
        """An agent with no capabilities set is unrestricted *by declaration*,
        but still bounded by its tier floor (a SUPERVISED agent can never exceed
        the supervised floor, even with empty capabilities)."""
        from core.capability_resolver import resolve_allowed_tools
        from core.sandbox_policy import TIER_FLOOR_TOOL_WHITELISTS
        agent = MagicMock()
        agent.capabilities = []
        agent.status = None
        result = resolve_allowed_tools(agent, tier="supervised")
        assert set(result) == set(TIER_FLOOR_TOOL_WHITELISTS["supervised"])

    def test_star_capabilities_bounded_by_tier_floor(self):
        """['*'] (unrestricted declaration) is still bounded by tier floor."""
        from core.capability_resolver import resolve_allowed_tools
        from core.sandbox_policy import TIER_FLOOR_TOOL_WHITELISTS
        agent = MagicMock()
        agent.capabilities = ["*"]
        agent.status = None
        assert set(resolve_allowed_tools(agent, tier="intern")) == set(TIER_FLOOR_TOOL_WHITELISTS["intern"])

    def test_none_capabilities_bounded_by_tier_floor(self):
        from core.capability_resolver import resolve_allowed_tools
        from core.sandbox_policy import TIER_FLOOR_TOOL_WHITELISTS
        agent = MagicMock()
        agent.capabilities = None
        agent.status = None
        assert set(resolve_allowed_tools(agent, tier="student")) == set(TIER_FLOOR_TOOL_WHITELISTS["student"])

    def test_unrestricted_at_autonomous_tier(self):
        """AUTONOMOUS floor is ('*',), so unrestricted caps -> truly unrestricted."""
        from core.capability_resolver import resolve_allowed_tools
        agent = MagicMock()
        agent.capabilities = []
        agent.status = None
        assert resolve_allowed_tools(agent, tier="autonomous") == ("*",)

    def test_explicit_allowlist_intersects_tier_floor(self):
        """An agent may never EXCEED its tier floor. A SUPERVISED agent asking
        for a tool NOT in the supervised floor gets it dropped."""
        from core.capability_resolver import resolve_allowed_tools
        agent = MagicMock()
        # 'terminal_command' is NOT in the supervised floor.
        agent.capabilities = ["canvas_render", "terminal_command", "memory_search"]
        result = resolve_allowed_tools(agent, tier="supervised")
        result_set = set(result)
        assert "canvas_render" in result_set
        assert "memory_search" in result_set
        # terminal_command is outside the supervised floor -> dropped.
        assert "terminal_command" not in result_set

    def test_autonomous_floor_passes_anything(self):
        """AUTONOMOUS floor is ('*',) so any declared capability is allowed."""
        from core.capability_resolver import resolve_allowed_tools
        agent = MagicMock()
        agent.capabilities = ["terminal_command", "browser_navigate"]
        result = resolve_allowed_tools(agent, tier="autonomous")
        assert set(result) == {"terminal_command", "browser_navigate"}

    def test_unknown_tier_falls_back_to_student_floor(self):
        from core.capability_resolver import resolve_allowed_tools
        agent = MagicMock()
        agent.capabilities = ["canvas_render"]
        result = resolve_allowed_tools(agent, tier="bogus_tier")
        # Falls back to student floor; canvas_render is in it.
        assert "canvas_render" in result

    def test_is_tool_allowed_helper(self):
        from core.capability_resolver import is_tool_allowed
        # Unrestricted
        assert is_tool_allowed(("*",), "anything") is True
        # Explicit set
        assert is_tool_allowed(("a", "b"), "a") is True
        assert is_tool_allowed(("a", "b"), "c") is False


# ============================================================================
# Enforcement at call_tool (all callers route through here)
# ============================================================================

class TestCallToolEnforcement:
    @pytest.mark.asyncio
    async def test_tool_not_in_capabilities_is_blocked(self, monkeypatch):
        """A tool outside the resolved capability set is blocked at call_tool."""
        from core.capability_resolver import resolve_allowed_tools
        from integrations.mcp_service import MCPService
        from core.models import AgentRegistry

        # An agent with a narrow allowlist (intersected with student floor).
        agent = MagicMock(spec=AgentRegistry)
        agent.capabilities = ["canvas_render"]  # in student floor
        agent.status = "STUDENT"

        # Patch the resolver lookup so call_tool sees this agent.
        monkeypatch.setattr(
            "core.capability_resolver.get_agent_for_context",
            lambda context: agent,
        )

        svc = MCPService()
        # 'memory_remember' is NOT in the resolved set -> blocked.
        result = await svc.call_tool(
            "memory_remember",
            {"content": "x"},
            context={"agent_id": "agent-1", "tier": "student"},
        )
        # Blocked tools return an error dict (never raise into the agent loop).
        assert isinstance(result, dict)
        assert result.get("success") is False or "not allowed" in str(result).lower() or "error" in str(result).lower()

    @pytest.mark.asyncio
    async def test_unrestricted_agent_tool_passes_gate(self, monkeypatch):
        """A default ('*') agent is not blocked by the capability gate."""
        from integrations.mcp_service import MCPService
        from core.models import AgentRegistry

        agent = MagicMock(spec=AgentRegistry)
        agent.capabilities = []
        agent.status = "AUTONOMOUS"
        monkeypatch.setattr(
            "core.capability_resolver.get_agent_for_context",
            lambda context: agent,
        )

        # Register a throwaway action so call_tool has something to dispatch to.
        from core.action_registry import action_registry, register_action

        @register_action("test.cap.pass")
        async def _ok(args, context):
            return {"ok": True}

        svc = MCPService()
        result = await svc.call_tool("test.cap.pass", {}, context={"agent_id": "a1"})
        assert result.get("ok") is True


# ============================================================================
# Agent API — capabilities field on PATCH /{agent_id}
# ============================================================================

class TestAgentRouteCapabilities:
    def test_update_request_accepts_capabilities(self):
        """AgentUpdateRequest must accept a capabilities field (P2)."""
        from api.agent_routes import AgentUpdateRequest
        req = AgentUpdateRequest(capabilities=["canvas_render", "memory_search"])
        assert req.capabilities == ["canvas_render", "memory_search"]

    def test_update_request_capabilities_optional(self):
        from api.agent_routes import AgentUpdateRequest
        req = AgentUpdateRequest(name="x")
        assert req.capabilities is None
