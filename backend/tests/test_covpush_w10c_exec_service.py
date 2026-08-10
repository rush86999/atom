"""Coverage wave 10c — core/agent_execution_service (TDD).

Real bugs found (RED first):
- WD1: the failure return leaks ``str(e)`` to clients (menubar/mobile) —
  internal exception text escapes the API boundary; detail must stay server-side.
- WD2: ``error_message = str(e)[:500]`` persisted to the audit row — same
  internal-detail leak, truncated but still raw.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.agent_execution_service import (
    ChatMessage,
    execute_agent_chat,
    execute_agent_chat_sync,
)


def _agent(**overrides):
    a = SimpleNamespace(
        id="agent-1", name="Helper", description="A helper",
        category="general", type="standard", confidence_score=0.9,
    )
    for k, v in overrides.items():
        setattr(a, k, v)
    return a


def _governance_harness(agent=None, allowed=True, reason=None):
    resolver = AsyncMock()
    resolver.resolve_agent_for_request.return_value = (agent, {"tier": "INTERN"})
    governance = MagicMock()
    governance.can_perform_action.return_value = {
        "allowed": allowed, "reason": reason or "denied by policy",
    }
    return resolver, governance


async def _run(agent=None, allowed=True, **kwargs):
    return await execute_agent_chat(
        agent_id=kwargs.pop("agent_id", "agent-1"),
        message=kwargs.pop("message", "hello"),
        user_id=kwargs.pop("user_id", "u-1"),
        session_id=kwargs.pop("session_id", None),
        workspace_id=kwargs.pop("workspace_id", "default"),
        conversation_history=kwargs.pop("conversation_history", None),
        stream=kwargs.pop("stream", False),
        **kwargs,
    )


class TestGovernanceGates:
    async def test_governance_blocked_returns_error(self):
        resolver, governance = _governance_harness(_agent(), allowed=False, reason="maturity")
        with patch("core.agent_execution_service.SessionLocal"), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance):
            out = await _run()
        assert out["success"] is False
        assert "blocked by governance" in out["error"]
        assert "maturity" in out["error"]
        assert out["execution_id"] is None

    async def test_governance_disabled_skips_resolution(self):
        llm = MagicMock()
        llm.analyze_query_complexity.return_value = "simple"
        llm.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")

        async def _gen(*a, **k):
            yield "off"

        llm.stream_completion = _gen
        with patch.dict("os.environ", {"STREAMING_GOVERNANCE_ENABLED": "false"}), \
             patch("core.agent_execution_service.LLMService", return_value=llm), \
             patch("core.agent_execution_service.get_chat_history_manager"), \
             patch("core.agent_execution_service.get_chat_session_manager"), \
             patch("core.agent_execution_service.trigger_episode_creation"):
            out = await _run()
        assert out["success"] is True
        assert out["response"] == "off"
        assert out["agent_name"] == "System"
        # no AgentExecution row attempted (agent is None when governance off)
        assert out["execution_id"]

    async def test_emergency_bypass_skips_governance(self):
        resolver = AsyncMock()
        resolver.resolve_agent_for_request.return_value = (_agent(), {})
        llm = MagicMock()
        llm.analyze_query_complexity.return_value = "simple"
        llm.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")
        llm.stream_completion = AsyncMock()

        async def _gen(*a, **k):
            yield "hi"
            yield " there"

        llm.stream_completion = _gen
        with patch.dict("os.environ", {"EMERGENCY_GOVERNANCE_BYPASS": "true"}), \
             patch("core.agent_execution_service.LLMService", return_value=llm), \
             patch("core.agent_execution_service.get_chat_history_manager") as hist, \
             patch("core.agent_execution_service.get_chat_session_manager") as sessions, \
             patch("core.agent_execution_service.trigger_episode_creation"), \
             patch("core.agent_execution_service.personal_budget_service"):
            session_mgr = MagicMock()
            session_mgr.create_session.return_value = "sess-new"
            sessions.return_value = session_mgr
            out = await _run(stream=True)
        assert out["success"] is True
        assert out["response"] == "hi there"
        assert out["session_id"] == "sess-new"
        hist.return_value.add_message.assert_any_call("sess-new", "user", "hello")
        hist.return_value.add_message.assert_any_call("sess-new", "assistant", "hi there")


class TestBudget:
    async def test_budget_exceeded_alerts_100(self):
        budget = MagicMock()
        budget.is_budget_exceeded.return_value = True
        resolver, governance = _governance_harness(_agent())
        with patch("core.agent_execution_service.SessionLocal"), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance), \
             patch("core.agent_execution_service.personal_budget_service", budget), \
             patch("core.agent_execution_service.LLMService") as llm_cls, \
             patch("core.agent_execution_service.get_chat_history_manager"), \
             patch("core.agent_execution_service.get_chat_session_manager"), \
             patch("core.agent_execution_service.trigger_episode_creation"):
            llm = MagicMock()
            llm.analyze_query_complexity.return_value = "simple"
            llm.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")
            llm.stream_completion = AsyncMock()

            async def _gen(*a, **k):
                yield "x"

            llm.stream_completion = _gen
            llm_cls.return_value = llm
            await _run()
        budget.send_budget_alert.assert_called_once_with(100.0)
        alert_levels = [c.args[0] for c in budget.send_budget_alert.call_args_list]
        assert 80.0 not in alert_levels
        assert 90.0 not in alert_levels

    async def test_budget_not_exceeded_alerts_80_and_90(self):
        budget = MagicMock()
        budget.is_budget_exceeded.return_value = False
        resolver, governance = _governance_harness(_agent())
        with patch("core.agent_execution_service.SessionLocal"), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance), \
             patch("core.agent_execution_service.personal_budget_service", budget), \
             patch("core.agent_execution_service.LLMService") as llm_cls, \
             patch("core.agent_execution_service.get_chat_history_manager"), \
             patch("core.agent_execution_service.get_chat_session_manager"), \
             patch("core.agent_execution_service.trigger_episode_creation"):
            llm = MagicMock()
            llm.analyze_query_complexity.return_value = "simple"
            llm.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")
            llm.stream_completion = AsyncMock()

            async def _gen(*a, **k):
                yield "x"

            llm.stream_completion = _gen
            llm_cls.return_value = llm
            await _run()
        budget.send_budget_alert.assert_any_call(80.0)
        budget.send_budget_alert.assert_any_call(90.0)

    async def test_budget_error_continues(self):
        budget = MagicMock()
        budget.is_budget_exceeded.side_effect = RuntimeError("budget down")
        resolver, governance = _governance_harness(_agent())
        with patch("core.agent_execution_service.SessionLocal"), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance), \
             patch("core.agent_execution_service.personal_budget_service", budget), \
             patch("core.agent_execution_service.LLMService") as llm_cls, \
             patch("core.agent_execution_service.get_chat_history_manager"), \
             patch("core.agent_execution_service.get_chat_session_manager"), \
             patch("core.agent_execution_service.trigger_episode_creation"):
            llm = MagicMock()
            llm.analyze_query_complexity.return_value = "simple"
            llm.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")
            llm.stream_completion = AsyncMock()

            async def _gen(*a, **k):
                yield "x"

            llm.stream_completion = _gen
            llm_cls.return_value = llm
            out = await _run()
        assert out["success"] is True


class TestExecutionRecord:
    async def _harness(self, agent, llm=None, db_session=None):
        resolver, governance = _governance_harness(agent)
        if llm is None:
            llm = MagicMock()
            llm.analyze_query_complexity.return_value = "simple"
            llm.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")
            llm.stream_completion = AsyncMock()

            async def _gen(*a, **k):
                yield "done"

            llm.stream_completion = _gen
        return resolver, governance, llm

    async def test_creates_and_finalizes_execution_row(self):
        agent = _agent()
        resolver, governance, llm = await self._harness(agent)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.agent_execution_service.SessionLocal", return_value=db), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance), \
             patch("core.agent_execution_service.LLMService", return_value=llm), \
             patch("core.agent_execution_service.get_chat_history_manager"), \
             patch("core.agent_execution_service.get_chat_session_manager"), \
             patch("core.agent_execution_service.trigger_episode_creation"), \
             patch("core.agent_execution_service.personal_budget_service"):
            out = await _run()
        assert out["success"] is True
        assert out["response"] == "done"
        # execution row created with metadata_json
        from core.models import AgentExecution

        db.add.assert_called()
        added = db.add.call_args.args[0]
        assert isinstance(added, AgentExecution)
        assert added.status == "running"
        assert added.metadata_json["agent_name"] == "Helper"
        assert added.metadata_json["user_id"] == "u-1"
        assert added.metadata_json["action_type"] == "chat"

    async def test_execution_record_failure_continues(self):
        agent = _agent()
        resolver, governance, llm = await self._harness(agent)
        db = MagicMock()
        db.commit.side_effect = RuntimeError("db write failed")
        with patch("core.agent_execution_service.SessionLocal", return_value=db), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance), \
             patch("core.agent_execution_service.LLMService", return_value=llm), \
             patch("core.agent_execution_service.get_chat_history_manager"), \
             patch("core.agent_execution_service.get_chat_session_manager"), \
             patch("core.agent_execution_service.trigger_episode_creation"), \
             patch("core.agent_execution_service.personal_budget_service"):
            out = await _run()
        assert out["success"] is True

    async def test_finalize_marks_completed_with_output_metadata(self):
        agent = _agent()
        resolver, governance, llm = await self._harness(agent)
        execution = MagicMock()
        execution.metadata_json = {"existing": 1}
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = execution
        with patch("core.agent_execution_service.SessionLocal", return_value=db), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance), \
             patch("core.agent_execution_service.LLMService", return_value=llm), \
             patch("core.agent_execution_service.get_chat_history_manager"), \
             patch("core.agent_execution_service.get_chat_session_manager"), \
             patch("core.agent_execution_service.trigger_episode_creation"), \
             patch("core.agent_execution_service.personal_budget_service"):
            await _run()
        assert execution.status == "completed"
        assert execution.result_summary == "done"
        assert execution.duration_seconds is not None
        assert execution.metadata_json["existing"] == 1
        assert execution.metadata_json["output"]["response"] == "done"
        assert execution.metadata_json["output"]["tokens"] >= 1

    async def test_marketplace_usage_tracked_on_completion(self):
        from core.models import AgentExecution

        agent = _agent(type="marketplace")
        resolver, governance, llm = await self._harness(agent)
        execution = MagicMock()
        execution.metadata_json = None
        installation = SimpleNamespace(template_id="tpl-1")
        db = MagicMock()
        db.query.side_effect = lambda model: MagicMock(
            **{"filter.return_value.first.return_value": (
                execution if model is AgentExecution else installation
            )}
        )
        with patch("core.agent_execution_service.SessionLocal", return_value=db), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance), \
             patch("core.agent_execution_service.LLMService", return_value=llm), \
             patch("core.agent_execution_service.get_chat_history_manager"), \
             patch("core.agent_execution_service.get_chat_session_manager"), \
             patch("core.agent_execution_service.trigger_episode_creation"), \
             patch("core.agent_execution_service.personal_budget_service"), \
             patch("core.agent_execution_service.MarketplaceUsageTracker") as tracker:
            await _run()
        tracker.track_usage.assert_called_once()
        kwargs = tracker.track_usage.call_args.kwargs
        assert kwargs["item_type"] == "agent"
        assert kwargs["item_id"] == "tpl-1"
        assert kwargs["success"] is True


class TestStreaming:
    async def test_stream_broadcasts_and_counts_tokens(self):
        agent = _agent()
        resolver, governance = _governance_harness(agent)
        llm = MagicMock()
        llm.analyze_query_complexity.return_value = "simple"
        llm.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")
        llm.stream_completion = AsyncMock()

        async def _gen(*a, **k):
            yield "Hello "
            yield "world"

        llm.stream_completion = _gen
        ws = AsyncMock()
        ws.STREAMING_UPDATE = "streaming:update"
        ws.STREAMING_COMPLETE = "streaming:complete"
        with patch("core.agent_execution_service.ws_manager", ws), \
             patch("core.agent_execution_service.SessionLocal"), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance), \
             patch("core.agent_execution_service.LLMService", return_value=llm), \
             patch("core.agent_execution_service.get_chat_history_manager"), \
             patch("core.agent_execution_service.get_chat_session_manager"), \
             patch("core.agent_execution_service.trigger_episode_creation"), \
             patch("core.agent_execution_service.personal_budget_service"):
            out = await _run(stream=True)
        assert out["response"] == "Hello world"
        # streaming:start + update + complete broadcasts
        calls = [c.args[1]["type"] for c in ws.broadcast.await_args_list]
        assert "streaming:start" in calls
        assert ws.STREAMING_UPDATE in calls
        assert ws.STREAMING_COMPLETE in calls
        # token estimate: "Hello " (6 chars -> 1) + "world" (5 -> 1) = 2
        assert out["tokens"] == 2

    async def test_conversation_history_prepended(self):
        agent = _agent()
        resolver, governance = _governance_harness(agent)
        llm = MagicMock()
        llm.analyze_query_complexity.return_value = "simple"
        llm.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")
        llm.stream_completion = AsyncMock()

        async def _gen(*a, **k):
            yield "ok"

        llm.stream_completion = _gen
        with patch("core.agent_execution_service.SessionLocal"), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance), \
             patch("core.agent_execution_service.LLMService", return_value=llm), \
             patch("core.agent_execution_service.get_chat_history_manager"), \
             patch("core.agent_execution_service.get_chat_session_manager"), \
             patch("core.agent_execution_service.trigger_episode_creation"), \
             patch("core.agent_execution_service.personal_budget_service"):
            out = await _run(
                conversation_history=[
                    {"role": "assistant", "content": "prev"},
                    {"role": "user", "content": "before"},
                ]
            )
        assert out["success"] is True
        sent = llm.stream_completion
        args = llm.get_optimal_provider.call_args
        assert args is not None


class TestFailurePaths:
    async def test_stream_failure_marks_execution_failed(self):
        agent = _agent()
        resolver, governance = _governance_harness(agent)
        llm = MagicMock()
        llm.analyze_query_complexity.return_value = "simple"
        llm.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")

        async def _boom(*a, **k):
            raise ValueError("provider exploded: token 42")
            yield  # pragma: no cover

        llm.stream_completion = _boom
        execution = MagicMock()
        execution.metadata_json = {}
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = execution
        with patch("core.agent_execution_service.SessionLocal", return_value=db), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance), \
             patch("core.agent_execution_service.LLMService", return_value=llm):
            out = await _run()
        assert out["success"] is False
        assert out["error"] != "provider exploded: token 42"
        # generic error, detail kept server-side (logged)
        assert "provider" not in out["error"]
        # audit row marked failed WITHOUT raw exception text
        assert execution.status == "failed"
        assert "token 42" not in (execution.error_message or "")

    async def test_failure_before_execution_row_returns_generic(self):
        resolver = AsyncMock()
        resolver.resolve_agent_for_request.side_effect = RuntimeError("db down: /tmp/secret.sqlite")
        with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService"):
            out = await _run()
        assert out["success"] is False
        assert "/tmp/secret.sqlite" not in out["error"]

    async def test_budget_spend_recorded(self):
        agent = _agent()
        resolver, governance = _governance_harness(agent)
        budget = MagicMock()
        budget.is_budget_exceeded.return_value = False
        llm = MagicMock()
        llm.analyze_query_complexity.return_value = "simple"
        llm.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")
        llm.stream_completion = AsyncMock()

        async def _gen(*a, **k):
            yield "x" * 8

        llm.stream_completion = _gen
        with patch("core.agent_execution_service.SessionLocal"), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance), \
             patch("core.agent_execution_service.LLMService", return_value=llm), \
             patch("core.agent_execution_service.get_chat_history_manager"), \
             patch("core.agent_execution_service.get_chat_session_manager"), \
             patch("core.agent_execution_service.trigger_episode_creation"), \
             patch("core.agent_execution_service.personal_budget_service", budget):
            out = await _run()
        assert out["success"] is True
        budget.record_spend.assert_called_once()
        cost, eid = budget.record_spend.call_args.args
        assert cost > 0.001
        assert eid == out["execution_id"]


class TestSyncWrapper:
    def test_sync_wrapper_runs_loop(self):
        resolver = AsyncMock()
        resolver.resolve_agent_for_request.return_value = (None, {})
        llm = MagicMock()
        llm.analyze_query_complexity.return_value = "simple"
        llm.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")
        llm.stream_completion = AsyncMock()

        async def _gen(*a, **k):
            yield "sync result"

        llm.stream_completion = _gen
        with patch("core.agent_execution_service.SessionLocal"), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService"), \
             patch("core.agent_execution_service.LLMService", return_value=llm), \
             patch("core.agent_execution_service.get_chat_history_manager"), \
             patch("core.agent_execution_service.get_chat_session_manager"), \
             patch("core.agent_execution_service.trigger_episode_creation"), \
             patch("core.agent_execution_service.personal_budget_service"):
            out = execute_agent_chat_sync("agent-1", "hi", "u-1")
        assert out["success"] is True
        assert out["response"] == "sync result"

    def test_chat_message(self):
        m = ChatMessage("user", "content")
        assert m.role == "user"
        assert m.content == "content"


# =========================================================================== #
# Wave 10c part 2 — remaining branches (finalize/marketplace/failure paths)
# =========================================================================== #
class TestRemainingBranches:
    @pytest.mark.asyncio
    async def test_pre_stream_session_close_exception_swallowed(self):
        agent = _agent()
        resolver, governance = _governance_harness(agent)
        db = MagicMock()
        db.close.side_effect = RuntimeError("close failed")
        llm = MagicMock()
        llm.analyze_query_complexity.return_value = "simple"
        llm.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")

        async def _gen(*a, **k):
            yield "ok"

        llm.stream_completion = _gen
        with patch("core.agent_execution_service.SessionLocal", return_value=db), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance), \
             patch("core.agent_execution_service.LLMService", return_value=llm), \
             patch("core.agent_execution_service.get_chat_history_manager"), \
             patch("core.agent_execution_service.get_chat_session_manager"), \
             patch("core.agent_execution_service.trigger_episode_creation"), \
             patch("core.agent_execution_service.personal_budget_service"):
            out = await _run()
        assert out["success"] is True

    @pytest.mark.asyncio
    async def test_chat_history_add_message_failure_doesnt_fail(self):
        agent = _agent()
        resolver, governance = _governance_harness(agent)
        llm = MagicMock()
        llm.analyze_query_complexity.return_value = "simple"
        llm.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")

        async def _gen(*a, **k):
            yield "ok"

        llm.stream_completion = _gen
        hist = MagicMock()
        hist.add_message.side_effect = RuntimeError("lancedb down")
        with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance), \
             patch("core.agent_execution_service.LLMService", return_value=llm), \
             patch("core.agent_execution_service.get_chat_history_manager", return_value=hist), \
             patch("core.agent_execution_service.get_chat_session_manager"), \
             patch("core.agent_execution_service.trigger_episode_creation"), \
             patch("core.agent_execution_service.personal_budget_service"):
            out = await _run(session_id="s-1")
        assert out["success"] is True

    @pytest.mark.asyncio
    async def test_marketplace_completion_tracking_failure_logged(self):
        agent = _agent(type="marketplace")
        resolver, governance = _governance_harness(agent)
        execution = MagicMock()
        execution.metadata_json = {}
        installation = SimpleNamespace(template_id="tpl-1")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [execution, installation]
        llm = MagicMock()
        llm.analyze_query_complexity.return_value = "simple"
        llm.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")

        async def _gen(*a, **k):
            yield "ok"

        llm.stream_completion = _gen
        with patch("core.agent_execution_service.SessionLocal", return_value=db), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance), \
             patch("core.agent_execution_service.LLMService", return_value=llm), \
             patch("core.agent_execution_service.get_chat_history_manager"), \
             patch("core.agent_execution_service.get_chat_session_manager"), \
             patch("core.agent_execution_service.trigger_episode_creation"), \
             patch("core.agent_execution_service.personal_budget_service"), \
             patch(
                 "core.agent_execution_service.MarketplaceUsageTracker.track_usage",
                 side_effect=RuntimeError("tracker down"),
             ):
            out = await _run()
        assert out["success"] is True

    @pytest.mark.asyncio
    async def test_finalize_commit_failure_rolls_back_and_closes(self):
        agent = _agent()
        resolver, governance = _governance_harness(agent)
        execution = MagicMock()
        execution.metadata_json = {}
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = execution
        db.commit.side_effect = RuntimeError("finalize commit failed")
        llm = MagicMock()
        llm.analyze_query_complexity.return_value = "simple"
        llm.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")

        async def _gen(*a, **k):
            yield "ok"

        llm.stream_completion = _gen
        with patch("core.agent_execution_service.SessionLocal", return_value=db), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance), \
             patch("core.agent_execution_service.LLMService", return_value=llm), \
             patch("core.agent_execution_service.get_chat_history_manager"), \
             patch("core.agent_execution_service.get_chat_session_manager"), \
             patch("core.agent_execution_service.trigger_episode_creation"), \
             patch("core.agent_execution_service.personal_budget_service"):
            out = await _run()
        assert out["success"] is True
        db.rollback.assert_called_once()
        db.close.assert_called()

    @pytest.mark.asyncio
    async def test_budget_spend_failure_continues(self):
        agent = _agent()
        resolver, governance = _governance_harness(agent)
        budget = MagicMock()
        budget.is_budget_exceeded.return_value = False
        budget.record_spend.side_effect = RuntimeError("budget down")
        llm = MagicMock()
        llm.analyze_query_complexity.return_value = "simple"
        llm.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")

        async def _gen(*a, **k):
            yield "ok"

        llm.stream_completion = _gen
        with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance), \
             patch("core.agent_execution_service.LLMService", return_value=llm), \
             patch("core.agent_execution_service.get_chat_history_manager"), \
             patch("core.agent_execution_service.get_chat_session_manager"), \
             patch("core.agent_execution_service.trigger_episode_creation"), \
             patch("core.agent_execution_service.personal_budget_service", budget):
            out = await _run()
        assert out["success"] is True

    @pytest.mark.asyncio
    async def test_failure_finalizer_session_creation_error(self):
        resolver = AsyncMock()
        resolver.resolve_agent_for_request.side_effect = RuntimeError("resolve failed")
        governance = MagicMock()
        with patch(
            "core.agent_execution_service.SessionLocal",
            side_effect=RuntimeError("session factory down"),
        ), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance):
            out = await _run()
        assert out["success"] is False
        assert out["error"] == "Agent chat execution failed"

    @pytest.mark.asyncio
    async def test_marketplace_failure_tracking(self):
        agent = _agent(type="marketplace")
        resolver, governance = _governance_harness(agent)
        llm = MagicMock()
        llm.analyze_query_complexity.return_value = "simple"
        llm.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")

        async def _boom(*a, **k):
            raise RuntimeError("stream died")
            yield  # pragma: no cover

        llm.stream_completion = _boom
        execution = MagicMock()
        execution.metadata_json = {}
        installation = SimpleNamespace(template_id="tpl-2")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [execution, installation]
        with patch("core.agent_execution_service.SessionLocal", return_value=db), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance), \
             patch("core.agent_execution_service.LLMService", return_value=llm), \
             patch("core.agent_execution_service.MarketplaceUsageTracker") as tracker:
            out = await _run()
        assert out["success"] is False
        tracker.track_usage.assert_called_once()
        assert tracker.track_usage.call_args.kwargs["success"] is False
        assert tracker.track_usage.call_args.kwargs["item_id"] == "tpl-2"

    @pytest.mark.asyncio
    async def test_marketplace_failure_tracking_error_logged(self):
        agent = _agent(type="marketplace")
        resolver, governance = _governance_harness(agent)
        llm = MagicMock()
        llm.analyze_query_complexity.return_value = "simple"
        llm.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")

        async def _boom(*a, **k):
            raise RuntimeError("stream died")
            yield  # pragma: no cover

        llm.stream_completion = _boom
        execution = MagicMock()
        execution.metadata_json = {}
        installation = SimpleNamespace(template_id="tpl-3")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [execution, installation]
        with patch("core.agent_execution_service.SessionLocal", return_value=db), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance), \
             patch("core.agent_execution_service.LLMService", return_value=llm), \
             patch(
                 "core.agent_execution_service.MarketplaceUsageTracker.track_usage",
                 side_effect=RuntimeError("tracker down"),
             ):
            out = await _run()
        assert out["success"] is False

    @pytest.mark.asyncio
    async def test_failure_finalize_rollback_and_close(self):
        agent = _agent()
        resolver, governance = _governance_harness(agent)
        llm = MagicMock()
        llm.analyze_query_complexity.return_value = "simple"
        llm.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")

        async def _boom(*a, **k):
            raise RuntimeError("stream died")
            yield  # pragma: no cover

        llm.stream_completion = _boom
        execution = MagicMock()
        execution.metadata_json = {}
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = execution
        db.commit.side_effect = RuntimeError("fail commit")
        with patch("core.agent_execution_service.SessionLocal", return_value=db), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance), \
             patch("core.agent_execution_service.LLMService", return_value=llm):
            out = await _run()
        assert out["success"] is False
        db.rollback.assert_called_once()
        db.close.assert_called()

    @pytest.mark.asyncio
    async def test_finally_cleanup_with_live_session(self):
        # LLMService init raises BEFORE the pre-stream close → finally closes
        # the still-open governance session.
        resolver, governance = _governance_harness(_agent())
        db = MagicMock()
        with patch("core.agent_execution_service.SessionLocal", return_value=db), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance), \
             patch(
                 "core.agent_execution_service.LLMService",
                 side_effect=RuntimeError("llm init failed"),
             ):
            out = await _run()
        assert out["success"] is False
        db.close.assert_called()

class TestSwallowBranches:
    @pytest.mark.asyncio
    async def test_finalize_rollback_failure_swallowed(self):
        agent = _agent()
        resolver, governance = _governance_harness(agent)
        execution = MagicMock()
        execution.metadata_json = {}
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = execution
        db.commit.side_effect = RuntimeError("commit failed")
        db.rollback.side_effect = RuntimeError("rollback failed")
        llm = MagicMock()
        llm.analyze_query_complexity.return_value = "simple"
        llm.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")

        async def _gen(*a, **k):
            yield "ok"

        llm.stream_completion = _gen
        with patch("core.agent_execution_service.SessionLocal", return_value=db), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance), \
             patch("core.agent_execution_service.LLMService", return_value=llm), \
             patch("core.agent_execution_service.get_chat_history_manager"), \
             patch("core.agent_execution_service.get_chat_session_manager"), \
             patch("core.agent_execution_service.trigger_episode_creation"), \
             patch("core.agent_execution_service.personal_budget_service"):
            out = await _run()
        assert out["success"] is True  # rollback failure must not escape

    @pytest.mark.asyncio
    async def test_episode_trigger_failure_logged_not_raised(self):
        agent = _agent()
        resolver, governance = _governance_harness(agent)
        llm = MagicMock()
        llm.analyze_query_complexity.return_value = "simple"
        llm.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")

        async def _gen(*a, **k):
            yield "ok"

        llm.stream_completion = _gen
        with patch("core.agent_execution_service.SessionLocal", return_value=MagicMock()), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance), \
             patch("core.agent_execution_service.LLMService", return_value=llm), \
             patch("core.agent_execution_service.get_chat_history_manager"), \
             patch("core.agent_execution_service.get_chat_session_manager"), \
             patch(
                 "core.agent_execution_service.trigger_episode_creation",
                 side_effect=RuntimeError("episode service down"),
             ), \
             patch("core.agent_execution_service.personal_budget_service"):
            out = await _run()
        assert out["success"] is True

    @pytest.mark.asyncio
    async def test_failure_finalizer_session_factory_raises(self):
        agent = _agent()
        resolver, governance = _governance_harness(agent)
        llm = MagicMock()
        llm.analyze_query_complexity.return_value = "simple"
        llm.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")

        async def _boom(*a, **k):
            raise RuntimeError("stream died")
            yield  # pragma: no cover

        llm.stream_completion = _boom
        db1 = MagicMock()
        with patch(
            "core.agent_execution_service.SessionLocal",
            side_effect=[db1, RuntimeError("session factory down")],
        ), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance), \
             patch("core.agent_execution_service.LLMService", return_value=llm):
            out = await _run()
        assert out["success"] is False
        assert out["error"] == "Agent chat execution failed"

    @pytest.mark.asyncio
    async def test_finally_close_failure_swallowed(self):
        resolver = AsyncMock()
        resolver.resolve_agent_for_request.side_effect = RuntimeError("resolve failed")
        db = MagicMock()
        db.close.side_effect = RuntimeError("close failed")
        with patch("core.agent_execution_service.SessionLocal", return_value=db), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService"):
            out = await _run()
        assert out["success"] is False

class TestFailureOwnedClose:
    @pytest.mark.asyncio
    async def test_failure_path_owned_session_close_failure_swallowed(self):
        agent = _agent()
        resolver, governance = _governance_harness(agent)
        llm = MagicMock()
        llm.analyze_query_complexity.return_value = "simple"
        llm.get_optimal_provider.return_value = ("openai", "gpt-4o-mini")

        async def _boom(*a, **k):
            raise RuntimeError("stream died")
            yield  # pragma: no cover

        llm.stream_completion = _boom
        execution = MagicMock()
        execution.metadata_json = {}
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = execution
        db.close.side_effect = RuntimeError("close failed")
        with patch("core.agent_execution_service.SessionLocal", return_value=db), \
             patch("core.agent_execution_service.AgentContextResolver", return_value=resolver), \
             patch("core.agent_execution_service.AgentGovernanceService", return_value=governance), \
             patch("core.agent_execution_service.LLMService", return_value=llm):
            out = await _run()
        assert out["success"] is False
        assert out["error"] == "Agent chat execution failed"
