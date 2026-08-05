"""
P9 — Sandbox Default-On tests (G5).

Two goals:
1. Route the legacy dispatch (generic agents, fleet, workflow, business agents)
   through the same sandbox gate as atom_meta_agent — today only atom_meta_agent
   + the dead core.mcp_service enforce. The shared helper enforces at
   integrations/mcp_service.call_tool, so all callers are gated.
2. Flip the sandbox defaults to enforce-on (ATOM_SANDBOX_FORCE_ENFORCE etc.).
   Shadow-mode-by-default tests must now assert enforced-by-default; the kill
   switch (ATOM_SANDBOX_FORCE_ENFORCE=false) returns to shadow instantly.

This is the highest-behavioral-risk change and the last phase — gated behind
kill switches so a single env var restores shadow behavior.
"""
import pytest
from unittest.mock import MagicMock


# ============================================================================
# Shared sandbox gate at the dispatch layer (legacy callers now gated)
# ============================================================================

class TestSharedSandboxGate:
    @pytest.mark.asyncio
    async def test_call_tool_runs_sandbox_check(self, monkeypatch):
        """integrations/mcp_service.call_tool must invoke the shared sandbox gate
        for legacy callers (generic agents, fleet, workflow, business agents)."""
        from integrations.mcp_service import MCPService
        from core import sandbox_gate

        checked = {"called": False}

        def fake_gate(tool_name, args, context):
            checked["called"] = True
            return None  # no decision -> allowed

        monkeypatch.setattr(sandbox_gate, "evaluate_tool_call", fake_gate)

        # Register a throwaway action so call_tool dispatches.
        from core.action_registry import register_action

        @register_action("test.sandbox.gate")
        async def _ok(args, context):
            return {"ok": True}

        svc = MCPService()
        await svc.call_tool("test.sandbox.gate", {}, context={"agent_id": "a1"})
        assert checked["called"] is True

    @pytest.mark.asyncio
    async def test_blocked_decision_blocks_call(self, monkeypatch):
        """When the shared gate returns an enforced BLOCKED decision, call_tool
        returns the block message instead of dispatching."""
        from integrations.mcp_service import MCPService
        from core import sandbox_gate

        decision = MagicMock()
        decision.requires_review = True
        decision.enforced = True
        decision.decision = "blocked"
        decision.violation_detail = "fs path outside root"
        decision.violation_type = "fs_path"
        monkeypatch.setattr(
            sandbox_gate, "evaluate_tool_call",
            lambda tool_name, args, context: decision,
        )

        dispatched = {"ran": False}
        from core.action_registry import register_action

        @register_action("test.sandbox.block")
        async def _should_not_run(args, context):
            dispatched["ran"] = True
            return {"ok": True}

        svc = MCPService()
        result = await svc.call_tool("test.sandbox.block", {}, context={"agent_id": "a1"})
        assert dispatched["ran"] is False
        assert "blocked" in str(result).lower() or "fs path" in str(result).lower()


# ============================================================================
# evaluate_tool_call helper (the shared gate)
# ============================================================================

class TestEvaluateToolCall:
    def test_returns_none_when_sandbox_disabled(self, monkeypatch):
        """Master switch off -> no decision (allowed)."""
        from core import sandbox_gate, sandbox_config
        monkeypatch.setattr(sandbox_config, "is_sandbox_enabled", lambda: False)
        assert sandbox_gate.evaluate_tool_call("any_tool", {}, {"run_id": "r1", "tier": "intern"}) is None

    def test_returns_none_when_no_run_id(self, monkeypatch):
        """Without a run_id the policy can't be scoped -> allowed."""
        from core import sandbox_gate, sandbox_config
        monkeypatch.setattr(sandbox_config, "is_sandbox_enabled", lambda: True)
        assert sandbox_gate.evaluate_tool_call("any_tool", {}, {"tier": "intern"}) is None


# ============================================================================
# Default flip — kill switch returns shadow instantly
# ============================================================================

class TestKillSwitch:
    def test_force_enforce_false_returns_shadow(self, monkeypatch):
        """ATOM_SANDBOX_FORCE_ENFORCE=false must return shadow behavior instantly."""
        from core import sandbox_config
        monkeypatch.setenv("ATOM_SANDBOX_FORCE_ENFORCE", "false")
        assert sandbox_config.is_sandbox_force_enforce_enabled() is False

    def test_force_enforce_true_enforces(self, monkeypatch):
        from core import sandbox_config
        monkeypatch.setenv("ATOM_SANDBOX_FORCE_ENFORCE", "true")
        assert sandbox_config.is_sandbox_force_enforce_enabled() is True
