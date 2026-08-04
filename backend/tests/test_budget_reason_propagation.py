"""
Tests for machine-readable budget-exceeded reason propagation.

When the budget gate halts an agent run, the failure reason must travel from
the meta-agent's result_payload → ``_handle_agent_request`` → the top-level
chat response → the HTTP envelope as a structured ``error_code``/
``failure_reason`` so the frontend can render a distinct budget-exceeded UI
(mirroring the existing ``no_llm_provider`` structured-error convention).

These tests target the propagation hops that previously LOST the signal —
not the budget gate itself (covered by test_budget_control.py).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def orchestrator():
    from integrations.chat_orchestrator import ChatOrchestrator
    return ChatOrchestrator(tenant_id="default")


# ============================================================================
# _handle_agent_request: budget signal must propagate, not be swallowed
# ============================================================================

class TestHandleAgentRequestBudgetPropagation:
    """``_handle_agent_request`` previously hardcoded ``status: "success"``,
    silently overwriting the meta-agent's budget_exceeded status. It must now
    propagate the structured signal."""

    @pytest.mark.asyncio
    async def test_budget_exceeded_result_propagates_error_code(self, orchestrator):
        """A meta-agent result with failure_reason must surface as
        error_code='budget_exceeded' + success=False in the feature response."""
        fake_result = {
            "final_output": "Budget limit reached — execution halted. (over budget)",
            "actions_executed": [],
            "status": "budget_exceeded",
            "failure_reason": "Budget exceeded. All operations halted immediately.",
        }
        fake_agent = MagicMock()
        fake_agent.execute = AsyncMock(return_value=fake_result)

        with patch("core.atom_meta_agent.get_atom_agent", return_value=fake_agent):
            result = await orchestrator._handle_agent_request(
                message="run an expensive task",
                intent_analysis={"primary_intent": MagicMock(value="AGENT_REQUEST")},
                session={"id": "s1", "user_id": "u1"},
                context=None,
            )

        assert result["error_code"] == "budget_exceeded", (
            f"Expected error_code='budget_exceeded', got {result.get('error_code')!r}"
        )
        assert result["success"] is False, (
            "A budget-exceeded feature response must set success=False"
        )
        assert "Budget exceeded" in result.get("failure_reason", ""), (
            "failure_reason must carry the underlying budget reason"
        )
        assert "Budget limit reached" in result["message"], (
            "The human-readable message must still be present"
        )

    @pytest.mark.asyncio
    async def test_successful_result_has_no_error_code(self, orchestrator):
        """A normal (non-budget) agent result must NOT set error_code."""
        fake_result = {
            "final_output": "Done! Created the task.",
            "actions_executed": [{"name": "create_task"}],
            "status": "success",
            "failure_reason": None,
        }
        fake_agent = MagicMock()
        fake_agent.execute = AsyncMock(return_value=fake_result)

        with patch("core.atom_meta_agent.get_atom_agent", return_value=fake_agent):
            result = await orchestrator._handle_agent_request(
                message="create a task",
                intent_analysis={"primary_intent": MagicMock(value="AGENT_REQUEST")},
                session={"id": "s1", "user_id": "u1"},
                context=None,
            )

        assert result.get("error_code") is None
        assert result["success"] is True
        assert result["status"] == "success"
