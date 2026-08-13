"""
Coverage wave 64f — core/provider_health_monitor + core/llm_usage_tracker +
core/websockets (TDD, no network, no real DB).

- ProviderHealthMonitor: EMA scoring (70% success / 30% latency), sliding
  window trimming, threshold filtering, singleton double-checked locking.
- LLMUsageTracker: records, daily rolling budgets, lazy date pruning,
  bounded record list, singleton.
- ConnectionManager: auth'd connect (incl. dev-token bypass), disconnect,
  subscribe/unsubscribe, broadcast error paths, personal messages,
  device/workflow event wrappers.
"""

import asyncio
from collections import deque
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core import llm_usage_tracker as lut
from core import provider_health_monitor as phm
from core.llm_usage_tracker import LLMUsageTracker
from core.provider_health_monitor import (
    ProviderHealthMonitor,
    get_provider_health_monitor,
)
from core.websockets import ConnectionManager, get_connection_manager


# ---------------------------------------------------------------------------
# ProviderHealthMonitor
# ---------------------------------------------------------------------------

class TestProviderHealthMonitor:
    def test_init_defaults(self):
        monitor = ProviderHealthMonitor()
        assert monitor.window_minutes == 5
        assert monitor.call_history == {}
        assert monitor.health_scores == {}

    def test_init_custom_window(self):
        monitor = ProviderHealthMonitor(window_minutes=10)
        assert monitor.window_minutes == 10

    def test_record_call_success_scores_high(self):
        monitor = ProviderHealthMonitor()
        monitor.record_call("openai", True, 500)
        assert "openai" in monitor.call_history
        assert len(monitor.call_history["openai"]) == 1
        assert monitor.get_health_score("openai") > 0.9

    def test_record_call_failures_scores_low(self):
        monitor = ProviderHealthMonitor()
        for _ in range(5):
            monitor.record_call("anthropic", False, 500)
        assert monitor.get_health_score("anthropic") < 0.5

    def test_high_latency_caps_latency_score(self):
        monitor = ProviderHealthMonitor()
        for _ in range(4):
            monitor.record_call("slow", True, 6000)
        # latency score clamped to 0: score = 1.0 * 0.7 + 0 * 0.3
        assert monitor.get_health_score("slow") == 0.7

    def test_mixed_success_rate(self):
        monitor = ProviderHealthMonitor()
        for _ in range(4):
            monitor.record_call("mixed", True, 1000)
        for _ in range(1):
            monitor.record_call("mixed", False, 1000)
        # success_rate 0.8, latency 0.8 -> 0.8
        assert monitor.get_health_score("mixed") == 0.8

    def test_get_health_score_unknown_provider_defaults_1(self):
        monitor = ProviderHealthMonitor()
        assert monitor.get_health_score("ghost") == 1.0

    def test_get_healthy_providers_filters_by_threshold(self):
        monitor = ProviderHealthMonitor()
        for _ in range(5):
            monitor.record_call("good", True, 300)
        for _ in range(5):
            monitor.record_call("bad", False, 300)
        healthy = monitor.get_healthy_providers(min_score=0.5)
        assert healthy == ["good"]
        assert "bad" not in healthy

    def test_get_healthy_providers_default_threshold(self):
        monitor = ProviderHealthMonitor()
        for _ in range(3):
            monitor.record_call("ok", True, 500)
        assert "ok" in monitor.get_healthy_providers()

    def test_trim_old_entries(self):
        monitor = ProviderHealthMonitor()
        old = datetime.now(timezone.utc) - timedelta(minutes=10)
        fresh = datetime.now(timezone.utc)
        monitor.call_history["p"] = deque([(old, True, 100), (fresh, True, 100)])
        monitor.record_call("p", True, 100)
        assert len(monitor.call_history["p"]) == 2  # old entry trimmed, 2 added

    def test_trim_old_entries_unknown_provider(self):
        monitor = ProviderHealthMonitor()
        # must be a no-op for unknown providers
        monitor._trim_old_entries("nope")
        assert "nope" not in monitor.call_history

    def test_update_health_score_empty_history_defaults_1(self):
        monitor = ProviderHealthMonitor()
        monitor.call_history["empty"] = deque()
        monitor._update_health_score("empty")
        assert monitor.health_scores["empty"] == 1.0

    def test_update_health_score_unknown_provider(self):
        monitor = ProviderHealthMonitor()
        monitor._update_health_score("ghost")
        assert monitor.health_scores["ghost"] == 1.0

    def test_singleton_created_once(self, monkeypatch):
        original = phm._health_monitor
        try:
            monkeypatch.setattr(phm, "_health_monitor", None)
            first = get_provider_health_monitor()
            second = get_provider_health_monitor()
            assert first is second
            assert isinstance(first, ProviderHealthMonitor)
        finally:
            phm._health_monitor = original

    def test_singleton_returns_existing(self):
        monitor = ProviderHealthMonitor()
        with patch.object(phm, "_health_monitor", monitor):
            assert get_provider_health_monitor() is monitor


# ---------------------------------------------------------------------------
# LLMUsageTracker
# ---------------------------------------------------------------------------

class TestLLMUsageTracker:
    def test_record_all_fields(self):
        tracker = LLMUsageTracker()
        tracker.record(
            workspace_id="w1", provider="openai", model="gpt-4o",
            input_tokens=100, output_tokens=50, cost_usd=0.01,
            savings_usd=0.05, agent_id="a1", complexity="high",
            is_managed_service=True, chain_id="c1",
        )
        rec = tracker._records[0]
        assert rec.workspace_id == "w1"
        assert rec.provider == "openai"
        assert rec.model == "gpt-4o"
        assert rec.input_tokens == 100
        assert rec.output_tokens == 50
        assert rec.cost_usd == 0.01
        assert rec.savings_usd == 0.05
        assert rec.agent_id == "a1"
        assert rec.chain_id == "c1"
        assert rec.complexity == "high"
        assert rec.is_managed_service is True

    def test_record_defaults(self):
        tracker = LLMUsageTracker()
        tracker.record("w1", "openai", "gpt-4o", 1, 1, 0.0)
        rec = tracker._records[0]
        assert rec.savings_usd == 0.0
        assert rec.agent_id is None
        assert rec.complexity == "moderate"
        assert rec.is_managed_service is True

    def test_records_bounded(self, monkeypatch):
        monkeypatch.setattr(LLMUsageTracker, "_MAX_RECORDS", 3)
        tracker = LLMUsageTracker()
        for i in range(6):
            tracker.record(f"w{i}", "openai", "m", 1, 1, 0.01)
        assert len(tracker._records) == 3
        # most recent retained
        assert {r.workspace_id for r in tracker._records} == {"w3", "w4", "w5"}

    def test_daily_usage_and_lazy_prune(self):
        tracker = LLMUsageTracker()
        today = date.today()
        # Seed two stale dates so the record() prune branch (>2 dates) fires.
        tracker._usage["w1"] = {
            today - timedelta(days=2): 0.5,
            today - timedelta(days=1): 0.25,
        }
        tracker.record("w1", "openai", "m", 1, 1, 0.1)
        # prune keeps only today's spend
        assert set(tracker._usage["w1"].keys()) == {today}
        assert tracker._usage["w1"][today] == 0.1

    def test_set_and_get_budget(self):
        tracker = LLMUsageTracker()
        assert tracker.get_budget("w1") is None
        tracker.set_budget("w1", 5.0)
        assert tracker.get_budget("w1") == 5.0

    def test_budget_exceeded_no_budget(self):
        assert LLMUsageTracker().is_budget_exceeded("w1") is False

    def test_budget_exceeded_under_limit(self):
        tracker = LLMUsageTracker()
        tracker.set_budget("w1", 1.0)
        tracker.record("w1", "openai", "m", 1, 1, 0.5)
        assert tracker.is_budget_exceeded("w1") is False

    def test_budget_exceeded_at_limit(self):
        tracker = LLMUsageTracker()
        tracker.set_budget("w1", 1.0)
        tracker.record("w1", "openai", "m", 1, 1, 1.0)
        assert tracker.is_budget_exceeded("w1") is True

    def test_budget_exceeded_over_limit(self):
        tracker = LLMUsageTracker()
        tracker.set_budget("w1", 1.0)
        tracker.record("w1", "openai", "m", 1, 1, 0.6)
        tracker.record("w1", "openai", "m", 1, 1, 0.6)
        assert tracker.is_budget_exceeded("w1") is True

    def test_get_usage_default_zero(self):
        assert LLMUsageTracker().get_usage("w1") == 0.0

    def test_get_usage_accumulates(self):
        tracker = LLMUsageTracker()
        tracker.record("w1", "openai", "m", 1, 1, 0.25)
        tracker.record("w1", "openai", "m", 1, 1, 0.75)
        assert tracker.get_usage("w1") == 1.0

    def test_get_records_filters_and_orders(self):
        tracker = LLMUsageTracker()
        tracker.record("w1", "openai", "m", 1, 1, 0.1)
        tracker.record("w2", "openai", "m", 1, 1, 0.2)
        tracker.record("w1", "openai", "m", 1, 1, 0.3)
        records = tracker.get_records("w1")
        assert [r.cost_usd for r in records] == [0.3, 0.1]  # most recent first

    def test_get_records_limit(self):
        tracker = LLMUsageTracker()
        for i in range(5):
            tracker.record("w1", "openai", "m", 1, 1, float(i))
        records = tracker.get_records("w1", limit=2)
        assert [r.cost_usd for r in records] == [4.0, 3.0]

    def test_get_records_empty_workspace(self):
        assert LLMUsageTracker().get_records("ghost") == []

    def test_reset_usage(self):
        tracker = LLMUsageTracker()
        tracker.record("w1", "openai", "m", 1, 1, 0.5)
        assert tracker.get_usage("w1") == 0.5
        tracker.reset_usage("w1")
        assert tracker.get_usage("w1") == 0.0

    def test_reset_usage_unknown_workspace(self):
        tracker = LLMUsageTracker()
        tracker.reset_usage("ghost")
        assert tracker._usage["ghost"] == {date.today(): 0.0}

    def test_singleton_created_once(self, monkeypatch):
        original = lut._llm_usage_tracker
        try:
            monkeypatch.setattr(lut, "_llm_usage_tracker", None)
            first = lut.get_llm_usage_tracker()
            second = lut.get_llm_usage_tracker()
            assert first is second
            assert isinstance(first, LLMUsageTracker)
        finally:
            lut._llm_usage_tracker = original

    def test_singleton_module_instance(self):
        assert isinstance(lut.llm_usage_tracker, LLMUsageTracker)

    def test_usage_records_isolated_by_workspace(self):
        tracker = LLMUsageTracker()
        tracker.set_budget("a", 1.0)
        tracker.record("a", "openai", "m", 1, 1, 0.9)
        tracker.record("b", "openai", "m", 1, 1, 0.9)
        assert tracker.is_budget_exceeded("a") is False
        assert tracker.is_budget_exceeded("b") is False  # no budget set for b


# ---------------------------------------------------------------------------
# ConnectionManager (websockets)
# ---------------------------------------------------------------------------

class FakeWebSocket:
    def __init__(self, send_side_effect=None):
        self.accepted = False
        self.closed = None
        self.sent = []
        self.send_side_effect = send_side_effect

    async def accept(self):
        self.accepted = True

    async def close(self, code=1000):
        self.closed = code

    async def send_json(self, message):
        if self.send_side_effect is not None:
            raise self.send_side_effect
        self.sent.append(message)


def _db_ctx(db):
    @contextmanager
    def fake_ctx():
        yield db

    return fake_ctx()


def _db_patch(db):
    """Patch helper: returns a fresh context manager per get_db_session() call
    (a _GeneratorContextManager can only be entered once)."""
    return patch(
        "core.websockets.get_db_session",
        side_effect=lambda: _db_ctx(db),
    )


def _make_user(user_id="u1", email="u@example.com", teams=None, workspace_id="w1"):
    return SimpleNamespace(
        id=user_id, email=email, teams=teams or [], workspace_id=workspace_id
    )


class TestConnectionManagerConnect:
    def test_dev_token_bypass(self):
        cm = ConnectionManager()
        ws = FakeWebSocket()
        with patch.dict("os.environ", {"ALLOW_WS_DEV_TOKEN": "true", "ENVIRONMENT": "development"}):
            with _db_patch(MagicMock()), \
                 patch("core.websockets.get_current_user_ws", new=AsyncMock()) as auth_mock:
                user = asyncio.run(cm.connect(ws, "dev-token"))
        assert user is not None
        assert user.id == "dev-user"
        assert ws.accepted is True
        auth_mock.assert_not_awaited()
        assert "user:dev-user" in cm.active_connections
        assert "workspace:default" in cm.active_connections

    def test_dev_token_rejected_when_flag_off(self):
        cm = ConnectionManager()
        ws = FakeWebSocket()
        db = MagicMock()
        with patch.dict("os.environ", {"ALLOW_WS_DEV_TOKEN": "false", "ENVIRONMENT": "development"}):
            with _db_patch(db), \
                 patch("core.websockets.get_current_user_ws", new=AsyncMock(return_value=_make_user())) as auth_mock:
                user = asyncio.run(cm.connect(ws, "dev-token"))
        assert user is not None
        auth_mock.assert_awaited_once_with("dev-token", db)

    def test_auth_success_subscribes_channels(self):
        cm = ConnectionManager()
        ws = FakeWebSocket()
        team = SimpleNamespace(id="t1")
        user = _make_user(user_id="u1", teams=[team], workspace_id="w1")
        with _db_patch(MagicMock()), \
             patch("core.websockets.get_current_user_ws", new=AsyncMock(return_value=user)):
            result = asyncio.run(cm.connect(ws, "token"))
        assert result is user
        assert ws.accepted is True
        assert "user:u1" in cm.active_connections
        assert "team:t1" in cm.active_connections
        assert "workspace:w1" in cm.active_connections
        assert ws in cm.user_connections["u1"]

    def test_second_connection_appends(self):
        cm = ConnectionManager()
        ws1, ws2 = FakeWebSocket(), FakeWebSocket()
        with _db_patch(MagicMock()), \
             patch("core.websockets.get_current_user_ws",
                   new=AsyncMock(return_value=_make_user(user_id="u1"))):
            asyncio.run(cm.connect(ws1, "token"))
            asyncio.run(cm.connect(ws2, "token"))
        assert cm.user_connections["u1"] == [ws1, ws2]

    def test_unauthorized_user_closed(self):
        cm = ConnectionManager()
        ws = FakeWebSocket()
        with _db_patch(MagicMock()), \
             patch("core.websockets.get_current_user_ws", new=AsyncMock(return_value=None)):
            result = asyncio.run(cm.connect(ws, "bad-token"))
        assert result is None
        assert ws.closed == 4001

    def test_exception_closes_socket(self):
        cm = ConnectionManager()
        ws = FakeWebSocket()
        with _db_patch(MagicMock()), \
             patch("core.websockets.get_current_user_ws",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = asyncio.run(cm.connect(ws, "token"))
        assert result is None
        assert ws.closed == 1000

    def test_exception_when_close_raises_runtime_error(self):
        cm = ConnectionManager()
        ws = FakeWebSocket()

        async def close_raises(code=1000):
            raise RuntimeError("already closed")

        ws.close = close_raises
        with _db_patch(MagicMock()), \
             patch("core.websockets.get_current_user_ws",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = asyncio.run(cm.connect(ws, "token"))
        assert result is None

    def test_user_without_workspace(self):
        cm = ConnectionManager()
        ws = FakeWebSocket()
        with _db_patch(MagicMock()), \
             patch("core.websockets.get_current_user_ws",
                   new=AsyncMock(return_value=_make_user(workspace_id=None))):
            result = asyncio.run(cm.connect(ws, "token"))
        assert result is not None
        assert "user:u1" in cm.active_connections
        assert not any(c.startswith("workspace:") for c in cm.active_connections)


class TestConnectionManagerChannels:
    def test_disconnect_removes_user_and_channel_memberships(self):
        cm = ConnectionManager()
        ws = FakeWebSocket()
        cm.user_connections["u1"] = [ws]
        cm.active_connections["user:u1"] = [ws]
        cm.active_connections["team:t1"] = [ws, FakeWebSocket()]
        cm.disconnect(ws, "u1")
        assert cm.user_connections["u1"] == []
        assert ws not in cm.active_connections["user:u1"]
        assert ws not in cm.active_connections["team:t1"]
        assert len(cm.active_connections["team:t1"]) == 1

    def test_disconnect_unknown_user(self):
        cm = ConnectionManager()
        cm.disconnect(FakeWebSocket(), "ghost")
        assert "ghost" not in cm.user_connections

    def test_disconnect_ws_not_registered(self):
        cm = ConnectionManager()
        ws = FakeWebSocket()
        other = FakeWebSocket()
        cm.user_connections["u1"] = [other]
        cm.active_connections["user:u1"] = [other]
        cm.disconnect(ws, "u1")
        assert cm.user_connections["u1"] == [other]

    def test_subscribe_new_and_existing_channel(self):
        cm = ConnectionManager()
        ws = FakeWebSocket()
        cm.subscribe(ws, "chan")
        cm.subscribe(ws, "chan")  # duplicate ignored
        cm.subscribe(ws, "other")
        assert cm.active_connections["chan"] == [ws]
        assert cm.active_connections["other"] == [ws]

    def test_unsubscribe_existing(self):
        cm = ConnectionManager()
        ws = FakeWebSocket()
        cm.active_connections["chan"] = [ws]
        cm.unsubscribe(ws, "chan")
        assert cm.active_connections["chan"] == []

    def test_unsubscribe_missing_channel_and_ws(self):
        cm = ConnectionManager()
        ws = FakeWebSocket()
        cm.unsubscribe(ws, "missing")
        cm.active_connections["chan"] = []
        cm.unsubscribe(ws, "chan")
        assert cm.active_connections["chan"] == []


class TestConnectionManagerBroadcast:
    def test_broadcast_sends_to_all(self):
        cm = ConnectionManager()
        ws1, ws2 = FakeWebSocket(), FakeWebSocket()
        cm.active_connections["chan"] = [ws1, ws2]
        asyncio.run(cm.broadcast("chan", {"type": "x"}))
        assert ws1.sent == [{"type": "x"}]
        assert ws2.sent == [{"type": "x"}]

    def test_broadcast_continues_after_failing_connection(self):
        cm = ConnectionManager()
        ws1 = FakeWebSocket(send_side_effect=RuntimeError("client gone"))
        ws2 = FakeWebSocket()
        cm.active_connections["chan"] = [ws1, ws2]
        asyncio.run(cm.broadcast("chan", {"type": "x"}))
        assert ws2.sent == [{"type": "x"}]

    def test_broadcast_empty_channel_warns(self):
        cm = ConnectionManager()
        asyncio.run(cm.broadcast("missing", {"type": "x"}))  # must not raise
        assert "missing" not in cm.active_connections

    def test_broadcast_event_message_shape(self):
        cm = ConnectionManager()
        ws = FakeWebSocket()
        cm.active_connections["chan"] = [ws]
        asyncio.run(cm.broadcast_event("chan", "evt:one", {"k": "v"}))
        msg = ws.sent[0]
        assert msg["type"] == "evt:one"
        assert msg["data"] == {"k": "v"}
        assert "timestamp" in msg

    def test_send_personal_message(self):
        cm = ConnectionManager()
        ws = FakeWebSocket()
        cm.user_connections["u1"] = [ws]
        asyncio.run(cm.send_personal_message("u1", {"hello": 1}))
        assert ws.sent == [{"hello": 1}]

    def test_send_personal_message_failing_connection(self):
        cm = ConnectionManager()
        ws = FakeWebSocket(send_side_effect=RuntimeError("gone"))
        cm.user_connections["u1"] = [ws]
        asyncio.run(cm.send_personal_message("u1", {"hello": 1}))  # must not raise

    def test_send_personal_message_unknown_user(self):
        cm = ConnectionManager()
        asyncio.run(cm.send_personal_message("ghost", {"hello": 1}))  # no-op


class TestConnectionManagerStatsAndEvents:
    def test_get_stats(self):
        cm = ConnectionManager()
        cm.active_connections["chan"] = [FakeWebSocket(), FakeWebSocket()]
        cm.user_connections["u1"] = [FakeWebSocket()]
        stats = cm.get_stats()
        assert stats["active_channels"] == 1
        assert stats["connected_users"] == 1
        assert stats["channels"] == {"chan": 2}

    @pytest.mark.asyncio
    async def test_device_event_wrappers(self):
        cm = ConnectionManager()
        with patch.object(cm, "broadcast_event", new=AsyncMock()) as bev:
            await cm.broadcast_device_registered("u1", {"d": 1})
            await cm.broadcast_device_command("u1", {"d": 1})
            await cm.broadcast_device_camera_ready("u1", {"d": 1})
            await cm.broadcast_device_recording_complete("u1", {"d": 1})
            await cm.broadcast_device_location_update("u1", {"d": 1})
            await cm.broadcast_device_notification_sent("u1", {"d": 1})
            await cm.broadcast_device_command_output("u1", {"d": 1})
            await cm.broadcast_device_session_created("u1", {"d": 1})
            await cm.broadcast_device_session_closed("u1", {"d": 1})
            await cm.broadcast_device_audit_log("u1", {"d": 1})
            await cm.notify_workflow_status("u1", "exec-1", "running", {"step": 1})
        assert bev.call_count == 11
        types = [call.args[1] for call in bev.call_args_list]
        assert types == [
            "device:registered", "device:command", "device:camera:ready",
            "device:recording:complete", "device:location:update",
            "device:notification:sent", "device:command:output",
            "device:session:created", "device:session:closed",
            "device:audit:log", "workflow:status",
        ]
        # workflow status carries execution_id/status/data
        wf_call = bev.call_args_list[-1]
        assert wf_call.args[2] == {
            "execution_id": "exec-1", "status": "running", "data": {"step": 1}
        }

    def test_get_connection_manager_singleton(self):
        assert get_connection_manager() is get_connection_manager()
        assert isinstance(get_connection_manager(), ConnectionManager)
