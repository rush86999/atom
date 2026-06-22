"""
TDD regression tests for round 8 broken-endpoint fixes.

Covers:
- BUG R8-3: /api/agents/{id}/promote calls non-existent promote_to_autonomous method
- BUG R8-4: /api/canvas/{id}/summary uses wrong service + wrong generate_summary signature
"""

from __future__ import annotations

import inspect


# ---------------------------------------------------------------------------
# BUG R8-3: promote_agent endpoint crashes (no promote_to_autonomous method)
# ---------------------------------------------------------------------------


class TestPromoteAgentEndpoint:
    """/api/agents/{id}/promote must work without crashing."""

    def test_does_not_call_missing_method(self):
        """Endpoint must NOT call service.promote_to_autonomous (doesn't exist)."""
        from api import agent_routes

        src = inspect.getsource(agent_routes.promote_agent)
        assert "promote_to_autonomous" not in src, (
            "promote_agent still calls non-existent AgentGovernanceService.promote_to_autonomous"
        )

    def test_sets_agent_status_to_autonomous(self):
        """Endpoint must set the agent's status to AUTONOMOUS."""
        from api import agent_routes

        src = inspect.getsource(agent_routes.promote_agent)
        # Must reference AgentStatus.AUTONOMOUS or equivalent
        assert "AUTONOMOUS" in src, (
            "promote_agent does not set status to AUTONOMOUS"
        )


# ---------------------------------------------------------------------------
# BUG R8-4: canvas summary endpoint uses wrong service + signature
# ---------------------------------------------------------------------------


class TestCanvasSummaryEndpoint:
    """/api/canvas/{id}/summary must call generate_summary with correct signature."""

    def test_does_not_pass_canvas_id_to_generate_summary(self):
        """generate_summary takes canvas_type+canvas_state, not canvas_id+user_id."""
        from api import canvas_routes

        src = inspect.getsource(canvas_routes.get_canvas_summary)
        # The buggy pattern: service.generate_summary(canvas_id=..., user_id=...)
        assert "generate_summary(\n            canvas_id=" not in src, (
            "get_canvas_summary still passes canvas_id to generate_summary"
        )
        assert "generate_summary(\n            user_id=" not in src, (
            "get_canvas_summary still passes user_id to generate_summary"
        )
