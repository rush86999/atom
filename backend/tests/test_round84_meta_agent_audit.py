"""Round 84 — meta-agent per-decision audit trail parity (bot journey gap).

GenericAgent got the R84c audit wrapper (execution_start/complete brackets +
tool-call + LLM ledger). AtomMetaAgent — the TASK-intent surface (chat,
fleet, workflows) — dispatches tools via _execute_tool_with_governance with
ZERO audit rows: a whole class of agent runs was invisible to the
per-decision trail served at /api/audit.

Closes (mirrors core/generic_agent.py R84c):
- execute() binds run identity, brackets the run with execution_start /
  execution_complete, and runs the completeness gate; unbind is guaranteed
  on both success and exception paths.
- _execute_tool_with_governance audits every tool invocation: success,
  error-string results, exceptions (audited then reraised), and never
  lets an audit-write failure break the tool call.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.atom_meta_agent as ama
from core.atom_meta_agent import AtomMetaAgent


@pytest.fixture
def meta_agent(monkeypatch):
    monkeypatch.setattr(ama, "WorldModelService", MagicMock())
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

    agent = AtomMetaAgent()
    agent.llm = MagicMock()
    agent.world_model = MagicMock()
    return agent


class TestToolDispatchAudit:
    """Every _execute_tool_with_governance invocation writes an audit row."""

    @pytest.mark.asyncio
    async def test_successful_tool_call_audited(self, meta_agent):
        with patch.object(
            meta_agent, "_execute_tool_with_governance_unaudited",
            AsyncMock(return_value={"ok": True}),
        ), patch("core.agent_action_audit.log_agent_action") as mock_log:
            result = await meta_agent._execute_tool_with_governance(
                "browser_navigate", {"url": "https://x.com"}, {}
            )
        assert result == {"ok": True}
        mock_log.assert_called_once()
        kwargs = mock_log.call_args.kwargs
        assert kwargs["action"] == "tool:browser_navigate"
        assert kwargs["success"] is True
        assert kwargs["metadata"]["tool"] == "browser_navigate"
        assert "duration_ms" in kwargs["metadata"]

    @pytest.mark.asyncio
    async def test_error_string_result_marked_failed(self, meta_agent):
        with patch.object(
            meta_agent, "_execute_tool_with_governance_unaudited",
            AsyncMock(return_value="Governance blocked: not allowed"),
        ), patch("core.agent_action_audit.log_agent_action") as mock_log:
            await meta_agent._execute_tool_with_governance(
                "device_execute_command", {}, {}
            )
        kwargs = mock_log.call_args.kwargs
        assert kwargs["success"] is False
        assert "blocked" in kwargs["error_message"]

    @pytest.mark.asyncio
    async def test_exception_audited_then_reraised(self, meta_agent):
        with patch.object(
            meta_agent, "_execute_tool_with_governance_unaudited",
            AsyncMock(side_effect=RuntimeError("tool crashed")),
        ), patch("core.agent_action_audit.log_agent_action") as mock_log:
            with pytest.raises(RuntimeError, match="tool crashed"):
                await meta_agent._execute_tool_with_governance(
                    "explode_tool", {}, {}
                )
        kwargs = mock_log.call_args.kwargs
        assert kwargs["success"] is False
        assert "tool crashed" in kwargs["error_message"]

    @pytest.mark.asyncio
    async def test_killrun_still_reraises_after_audit(self, meta_agent):
        from core.sandbox_killrun import KillRunAborted

        with patch.object(
            meta_agent, "_execute_tool_with_governance_unaudited",
            AsyncMock(side_effect=KillRunAborted("killed")),
        ), patch("core.agent_action_audit.log_agent_action") as mock_log:
            with pytest.raises(KillRunAborted):
                await meta_agent._execute_tool_with_governance(
                    "fs_write", {}, {}
                )
        mock_log.assert_called_once()
        assert mock_log.call_args.kwargs["success"] is False

    @pytest.mark.asyncio
    async def test_audit_failure_does_not_break_tool(self, meta_agent):
        with patch.object(
            meta_agent, "_execute_tool_with_governance_unaudited",
            AsyncMock(return_value="fine"),
        ), patch(
            "core.agent_action_audit.log_agent_action",
            side_effect=RuntimeError("audit db down"),
        ):
            result = await meta_agent._execute_tool_with_governance(
                "some_tool", {}, {}
            )
        assert result == "fine"


class TestLLMDecisionLedger:
    """ReAct LLM decisions must be ledgered like GenericAgent's are."""

    @pytest.mark.asyncio
    async def test_ledger_method_writes_row(self, meta_agent):
        from core import agent_action_audit as aaa

        with patch.object(aaa, "log_llm_call") as mock_log:
            meta_agent._ledger_llm_decision(
                model="fast", prompt="what next?", response={"thought": "t"}
            )
        mock_log.assert_called_once()
        kwargs = mock_log.call_args.kwargs
        assert kwargs["model"] == "fast"
        assert kwargs["prompt"] == "what next?"
        assert kwargs["response"] == {"thought": "t"}

    @pytest.mark.asyncio
    async def test_ledger_never_raises(self, meta_agent):
        from core import agent_action_audit as aaa

        with patch.object(aaa, "log_llm_call", side_effect=RuntimeError("x")):
            meta_agent._ledger_llm_decision(
                model="fast", prompt="p", response="r"
            )  # must not raise


class TestExecutionBrackets:
    """execute() brackets the run with execution_start/execution_complete."""

    def _payload(self):
        return {
            "final_output": "done",
            "actions_executed": [{"action": "x"}, {"action": None}],
            "status": "success",
            "trigger_mode": "manual",
        }

    @pytest.mark.asyncio
    async def test_success_bracket_and_unbind(self, meta_agent):
        payload = self._payload()
        with patch.object(
            meta_agent, "execute_unaudited", AsyncMock(return_value=payload)
        ) as inner, patch("core.agent_action_audit.log_agent_action") as mock_log, \
             patch("core.agent_action_audit.bind_audit_context", return_value="tok") as mock_bind, \
             patch("core.agent_action_audit.unbind_audit_context") as mock_unbind, \
             patch("core.agent_action_audit.check_execution_audit_completeness",
                   return_value={"complete": True}):
            result = await meta_agent.execute(
                "do the thing", context={"user_id": "u1"}, execution_id="exec-9"
            )
        assert result is payload
        inner.assert_awaited_once()

        actions = [c.kwargs.get("action") for c in mock_log.call_args_list]
        assert actions[0] == "execution_start"
        assert actions[-1] == "execution_complete"

        bound = mock_bind.call_args
        assert bound.args[0] == "atom_main"
        assert bound.args[1] == "exec-9"
        assert bound.kwargs.get("user_id") == "u1"

        complete = mock_log.call_args_list[-1].kwargs
        assert complete["metadata"]["status"] == "success"
        assert complete["success"] is True
        # completeness gate counts only steps that actually dispatched a tool
        complete_call = [
            c for c in mock_log.call_args_list
            if c.kwargs.get("action") == "execution_start"
        ]
        assert complete_call  # start logged before run
        mock_unbind.assert_called_once_with("tok")

    @pytest.mark.asyncio
    async def test_exception_brackets_failure_and_unbinds(self, meta_agent):
        with patch.object(
            meta_agent, "execute_unaudited",
            AsyncMock(side_effect=RuntimeError("run exploded")),
        ), patch("core.agent_action_audit.log_agent_action") as mock_log, \
             patch("core.agent_action_audit.bind_audit_context", return_value="tok"), \
             patch("core.agent_action_audit.unbind_audit_context") as mock_unbind:
            with pytest.raises(RuntimeError, match="run exploded"):
                await meta_agent.execute("boom", execution_id="exec-10")
        complete = mock_log.call_args_list[-1].kwargs
        assert complete["action"] == "execution_complete"
        assert complete["success"] is False
        assert "run exploded" in (complete.get("error_message") or "")
        mock_unbind.assert_called_once_with("tok")

    @pytest.mark.asyncio
    async def test_completeness_gate_counts_audited_steps(self, meta_agent):
        payload = {
            **self._payload(),
            "actions_executed": [
                {"action": {"name": "t1"}},
                {"action": {"name": "t2"}},
                {"action": None},
            ],
        }
        with patch.object(
            meta_agent, "execute_unaudited", AsyncMock(return_value=payload)
        ), patch("core.agent_action_audit.log_agent_action"), \
             patch("core.agent_action_audit.bind_audit_context", return_value="tok"), \
             patch("core.agent_action_audit.unbind_audit_context"), \
             patch(
                 "core.agent_action_audit.check_execution_audit_completeness",
                 return_value={"complete": True},
             ) as mock_gate:
            await meta_agent.execute("multi-tool", execution_id="exec-11")
        kwargs = mock_gate.call_args.kwargs
        assert kwargs["expected_tool_calls"] == 2
        assert kwargs["expected_llm_calls"] == 3

    @pytest.mark.asyncio
    async def test_audit_closeout_failure_never_breaks_run(self, meta_agent):
        payload = self._payload()
        with patch.object(
            meta_agent, "execute_unaudited", AsyncMock(return_value=payload)
        ), patch(
            "core.agent_action_audit.log_agent_action",
            side_effect=RuntimeError("db down"),
        ), patch(
            "core.agent_action_audit.bind_audit_context", return_value="tok"
        ), patch("core.agent_action_audit.unbind_audit_context"):
            result = await meta_agent.execute("resilient", execution_id="exec-12")
        assert result is payload
