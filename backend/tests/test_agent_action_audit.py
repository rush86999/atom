"""
Tests for the agent action audit trail (core/agent_action_audit.py) and its
integration points: the GenericAgent._step_act wrapper and the LLMService
per-call ledger.

Covers:
- log_agent_action / log_llm_call write AuditLog rows with execution linkage
- audit write failures are loud (ERROR log) but never raise
- LLM calls are ledgered only inside an agent-run context
- _step_act audits every tool invocation (success, string-error, exception)
- check_execution_audit_completeness detects gaps
"""

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core import agent_action_audit as aaa
from core.agent_action_audit import (
    audited_llm_call,
    check_execution_audit_completeness,
    log_agent_action,
    log_llm_call,
    set_audit_context,
)


@pytest.fixture
def mock_db_session():
    """Patch get_db_session inside the audit module with a recording session."""
    session = MagicMock()
    written = []

    def add(row):
        written.append(row)

    session.add.side_effect = add
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=session)
    ctx.__exit__ = MagicMock(return_value=False)

    with patch("core.database.get_db_session", return_value=ctx):
        # agent_action_audit imports get_db_session lazily from
        # core.database, so patching the module attribute is enough.
        yield session, written


class TestLogAgentAction:
    def test_writes_audit_row_with_execution_linkage(self, mock_db_session):
        _, written = mock_db_session
        with set_audit_context("agent-1", "exec-1", user_id="user-1", workspace_id="ws"):
            result = log_agent_action(
                action="tool:browser_navigate",
                metadata={"tool": "browser_navigate", "args": {"url": "https://x.com"}},
            )
        assert result is not None
        assert len(written) == 1
        row = written[0]
        assert row.event_type == "agent_action"
        assert row.action == "tool:browser_navigate"
        assert row.success is True
        meta = json.loads(row.metadata_json)
        assert meta["agent_id"] == "agent-1"
        assert meta["agent_execution_id"] == "exec-1"

    def test_no_context_still_writes_row(self, mock_db_session):
        _, written = mock_db_session
        log_agent_action(action="execution_start", metadata={"x": 1})
        assert len(written) == 1
        meta = json.loads(written[0].metadata_json)
        assert "agent_execution_id" not in meta

    def test_failure_never_raises_but_logs_error(self, mock_db_session, caplog):
        session, written = mock_db_session
        session.commit.side_effect = RuntimeError("db down")
        with caplog.at_level(logging.ERROR):
            result = log_agent_action(action="tool:x", metadata={})
        assert result is None
        assert "AUDIT WRITE FAILED" in caplog.text

    def test_payload_truncation(self, mock_db_session):
        _, written = mock_db_session
        log_agent_action(action="tool:x", metadata={"blob": "a" * 10_000})
        meta = json.loads(written[0].metadata_json)
        assert len(meta["blob"]) < 2100
        assert "truncated" in meta["blob"]


class TestLLMCallLedger:
    def test_llm_call_logged_inside_agent_context(self, mock_db_session):
        _, written = mock_db_session
        with set_audit_context("agent-1", "exec-1"):
            log_llm_call(model="gpt-4o", prompt="why?", response="because", latency_ms=12.3)
        assert len(written) == 1
        row = written[0]
        assert row.event_type == "llm_call"
        meta = json.loads(row.metadata_json)
        assert meta["model"] == "gpt-4o"
        assert meta["prompt_excerpt"] == "why?"
        assert meta["response_excerpt"] == "because"
        assert "prompt_digest" in meta

    def test_llm_call_skipped_outside_agent_context(self, mock_db_session):
        _, written = mock_db_session
        assert log_llm_call(model="gpt-4o", prompt="p", response="r") is None
        assert written == []

    @pytest.mark.asyncio
    async def test_audited_llm_call_passthrough_and_ledger(self, mock_db_session):
        _, written = mock_db_session
        call = AsyncMock(return_value="the answer")

        # Outside a run: passthrough, no row.
        out = await audited_llm_call("m1", "prompt", call)
        assert out == "the answer"
        assert written == []

        with set_audit_context("agent-1", "exec-1"):
            out = await audited_llm_call("m1", "prompt", call, provider="openai")
        assert out == "the answer"
        assert len(written) == 1
        assert written[0].event_type == "llm_call"

    @pytest.mark.asyncio
    async def test_audited_llm_call_ledgers_failure(self, mock_db_session):
        _, written = mock_db_session
        call = AsyncMock(side_effect=RuntimeError("provider 500"))
        with set_audit_context("agent-1", "exec-1"):
            with pytest.raises(RuntimeError):
                await audited_llm_call("m1", "prompt", call)
        assert len(written) == 1
        row = written[0]
        assert row.success is False
        assert "provider 500" in row.error_message


class TestCompletenessGate:
    def test_complete_when_audits_cover_expected(self, mock_db_session):
        session, _ = mock_db_session
        session.query.return_value.filter.return_value.filter.return_value.count.return_value = 5
        result = check_execution_audit_completeness("exec-1", expected_tool_calls=3, expected_llm_calls=2)
        assert result["complete"] is True
        assert result["coverage_percentage"] == 100.0

    def test_gap_detected_when_audits_missing(self, mock_db_session):
        session, _ = mock_db_session
        session.query.return_value.filter.return_value.filter.return_value.count.return_value = 2
        result = check_execution_audit_completeness("exec-1", expected_tool_calls=5)
        assert result["complete"] is False
        assert result["coverage_percentage"] == 40.0

    def test_count_failure_reported_not_raised(self, mock_db_session):
        session, _ = mock_db_session
        session.query.side_effect = RuntimeError("boom")
        result = check_execution_audit_completeness("exec-1", expected_tool_calls=1)
        assert result["complete"] is False
        assert "error" in result


class TestStepActAuditWrapper:
    """The GenericAgent._step_act wrapper must audit every invocation."""

    def _make_agent(self):
        from core.generic_agent import GenericAgent
        from core.models import AgentRegistry

        agent_model = AgentRegistry(
            id="agent-123", name="Audited Agent", type="assistant",
            module_path="agents.assistant", class_name="AssistantAgent",
            category="general", configuration={},
        )
        with patch("core.generic_agent.WorldModelService"), \
             patch("core.generic_agent.ReflectionService"), \
             patch("core.generic_agent.CanvasSummaryService"), \
             patch("core.generic_agent.mcp_service"), \
             patch("core.generic_agent.LLMService"):
            return GenericAgent(agent_model, workspace_id="default")

    @pytest.mark.asyncio
    async def test_successful_tool_call_audited(self):
        agent = self._make_agent()
        with patch.object(
            agent, "_step_act_unaudited", AsyncMock(return_value={"ok": True})
        ), patch("core.agent_action_audit.log_agent_action") as mock_log:
            result = await agent._step_act("browser_navigate", {"url": "https://x.com"})
        assert result == {"ok": True}
        mock_log.assert_called_once()
        kwargs = mock_log.call_args.kwargs
        assert kwargs["action"] == "tool:browser_navigate"
        assert kwargs["success"] is True
        assert kwargs["metadata"]["tool"] == "browser_navigate"
        assert "duration_ms" in kwargs["metadata"]

    @pytest.mark.asyncio
    async def test_error_string_result_marked_failed(self):
        agent = self._make_agent()
        with patch.object(
            agent, "_step_act_unaudited",
            AsyncMock(return_value="Governance Error: rejected by user"),
        ), patch("core.agent_action_audit.log_agent_action") as mock_log:
            await agent._step_act("device_execute_command", {})
        kwargs = mock_log.call_args.kwargs
        assert kwargs["success"] is False
        assert "rejected" in kwargs["error_message"]

    @pytest.mark.asyncio
    async def test_exception_audited_then_reraised(self):
        agent = self._make_agent()
        with patch.object(
            agent, "_step_act_unaudited", AsyncMock(side_effect=RuntimeError("tool crashed"))
        ), patch("core.agent_action_audit.log_agent_action") as mock_log:
            with pytest.raises(RuntimeError, match="tool crashed"):
                await agent._step_act("explode_tool", {})
        kwargs = mock_log.call_args.kwargs
        assert kwargs["success"] is False
        assert "tool crashed" in kwargs["error_message"]

    @pytest.mark.asyncio
    async def test_audit_failure_does_not_break_tool(self):
        agent = self._make_agent()
        with patch.object(
            agent, "_step_act_unaudited", AsyncMock(return_value="fine")
        ), patch(
            "core.agent_action_audit.log_agent_action",
            side_effect=RuntimeError("audit db down"),
        ):
            result = await agent._step_act("some_tool", {})
        assert result == "fine"
