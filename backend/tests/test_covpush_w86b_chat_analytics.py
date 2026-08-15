# -*- coding: utf-8 -*-
"""W86B — coverage push for 10 backend modules (standalone >=95% each).

Measured before-% (existing carrier suites, no W86B file) -> after-% (this
file alone, 339 tests):

  1. core/chat_process_manager.py      (109 stmts)  100% -> 100%
  2. core/chat_session_manager.py      (261 stmts)   58% ->  99% (2 unreachable)
  3. core/chat_context_manager.py      ( 73 stmts)  100% -> 100%
  4. core/behavior_analyzer.py         ( 44 stmts)  100% -> 100%
  5. core/analytics_engine.py          (134 stmts)  100% -> 100%
  6. core/workflow_analytics_engine.py (706 stmts)   98% -> 100%
  7. core/debug_insight_engine.py      (168 stmts)  100% -> 100%
  8. core/debug_monitor.py             (148 stmts)   85% -> 100%
  9. core/debug_query.py               (167 stmts)  100% -> 100%
 10. core/activity_publisher.py        ( 42 stmts)  100% -> 100%

Style: mocked deps, zero LLM spend, zero network, fake sessions (no real DB —
the workflow analytics engine's own SQLite store runs in tmp_path, matching
its established carrier-suite convention). All async DB access is AsyncMock.
"""
from __future__ import annotations

import asyncio
import builtins
import io
import json
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

import core.analytics_engine as ae_mod
import core.activity_publisher as ap_mod
import core.behavior_analyzer as ba_mod
import core.chat_context_manager as ccm_mod
import core.chat_process_manager as cpm_mod
import core.chat_session_manager as csm_mod
import core.debug_insight_engine as die_mod
import core.debug_monitor as dm_mod
import core.debug_query as dq_mod
import core.workflow_analytics_engine as wae_mod
from core.analytics_engine import (
    AnalyticsEngine,
    IntegrationMetric,
    WorkflowMetric as AeWorkflowMetric,
    get_analytics_engine as ae_get_engine,
)
from core.activity_publisher import ActivityPublisher, get_activity_publisher
from core.behavior_analyzer import BehaviorAnalyzer, get_behavior_analyzer
from core.chat_context_manager import ChatContextManager, get_chat_context_manager
from core.chat_process_manager import ChatProcessManager, get_process_manager
from core.chat_session_manager import ChatSessionManager, get_chat_session_manager
from core.debug_insight_engine import DebugInsightEngine
from core.debug_monitor import DebugMonitor
from core.debug_query import DebugQuery
from core.workflow_analytics_engine import (
    Alert,
    AlertSeverity,
    MetricType,
    WorkflowAnalyticsEngine,
    WorkflowExecutionEvent,
    WorkflowMetric as WaeWorkflowMetric,
    WorkflowStatus,
    get_analytics_engine as wae_get_engine,
)


# ============================================================================
# 1. behavior_analyzer
# ============================================================================


class TestBehaviorAnalyzer:
    @pytest.fixture()
    def analytics(self):
        return Mock()

    @pytest.fixture()
    def analyzer(self, analytics):
        with patch("core.behavior_analyzer.get_analytics_engine", return_value=analytics):
            return BehaviorAnalyzer()

    def test_log_user_action_new_window(self, analyzer, analytics):
        analyzer.log_user_action("u1", "meeting_ended", metadata={"m": 1})
        assert analyzer.user_action_windows["default_u1"][0]["action_type"] == "meeting_ended"
        assert analyzer.user_action_windows["default_u1"][0]["metadata"] == {"m": 1}
        analytics.track_user_activity.assert_called_once_with(
            "u1", "meeting_ended", metadata={"m": 1}, workspace_id="default"
        )

    def test_log_user_action_existing_window(self, analyzer):
        analyzer.log_user_action("u1", "a")
        analyzer.log_user_action("u1", "b")
        assert [a["action_type"] for a in analyzer.user_action_windows["default_u1"]] == ["a", "b"]

    def test_log_user_action_workspace_scoped(self, analyzer, analytics):
        analyzer.log_user_action("u1", "a", workspace_id="ws-1")
        assert "ws-1_u1" in analyzer.user_action_windows
        analytics.track_user_activity.assert_called_once_with(
            "u1", "a", metadata=None, workspace_id="ws-1"
        )

    def test_log_user_action_window_overflow(self, analyzer):
        for i in range(11):
            analyzer.log_user_action("u1", f"a{i}")
        assert len(analyzer.user_action_windows["default_u1"]) == 10
        assert analyzer.user_action_windows["default_u1"][0]["action_type"] == "a1"

    def test_log_user_action_none_metadata(self, analyzer):
        analyzer.log_user_action("u1", "a")
        assert analyzer.user_action_windows["default_u1"][0]["metadata"] == {}

    def test_detect_patterns_insufficient_actions(self, analyzer):
        analyzer.user_action_windows["default_u1"] = [{"action_type": "a"}]
        assert analyzer.detect_patterns("u1") == []

    def test_detect_patterns_empty_window(self, analyzer):
        assert analyzer.detect_patterns("u1") == []

    def test_detect_patterns_meeting(self, analyzer):
        analyzer.user_action_windows["default_u1"] = [
            {"action_type": "meeting_ended"},
            {"action_type": "task_created"},
            {"action_type": "x"},
        ]
        patterns = analyzer.detect_patterns("u1")
        assert patterns[0]["name"] == "Meeting Follow-up Automation"
        assert patterns[0]["confidence"] == 0.8

    def test_detect_patterns_document(self, analyzer):
        analyzer.user_action_windows["default_u1"] = [
            {"action_type": "document_uploaded"},
            {"action_type": "knowledge_update"},
            {"action_type": "x"},
        ]
        patterns = analyzer.detect_patterns("u1")
        assert patterns[0]["name"] == "Automated Knowledge Extraction"
        assert patterns[0]["confidence"] == 0.9

    def test_detect_patterns_both(self, analyzer):
        analyzer.user_action_windows["default_u1"] = [
            {"action_type": "meeting_ended"},
            {"action_type": "task_created"},
            {"action_type": "document_uploaded"},
            {"action_type": "knowledge_update"},
        ]
        names = [p["name"] for p in analyzer.detect_patterns("u1")]
        assert "Meeting Follow-up Automation" in names
        assert "Automated Knowledge Extraction" in names

    def test_detect_patterns_workspace_scoped(self, analyzer):
        analyzer.user_action_windows["ws-1_u1"] = [
            {"action_type": "meeting_ended"},
            {"action_type": "task_created"},
            {"action_type": "x"},
        ]
        patterns = analyzer.detect_patterns("u1", workspace_id="ws-1")
        assert patterns[0]["name"] == "Meeting Follow-up Automation"

    def test_get_behavior_analyzer_singleton(self):
        ba_mod._behavior_analyzer = None
        a = get_behavior_analyzer()
        b = get_behavior_analyzer()
        assert a is b
        ba_mod._behavior_analyzer = None


# ============================================================================
# 2. analytics_engine
# ============================================================================


@pytest.fixture(autouse=True)
def _reset_ae_singletons():
    AnalyticsEngine._instance = None
    ae_mod._analytics_engine = None
    yield
    AnalyticsEngine._instance = None
    ae_mod._analytics_engine = None


@pytest.fixture
def ae_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(ae_mod.os.path, "join", Mock(side_effect=lambda *p: str(tmp_path / str(p[-1]))))
    monkeypatch.setattr(ae_mod.os, "makedirs", Mock())
    return tmp_path


@pytest.fixture
def ae_engine(ae_paths, monkeypatch):
    monkeypatch.setattr(ae_mod.os.path, "exists", Mock(return_value=False))
    return AnalyticsEngine()


class TestAeMetrics:
    def test_workflow_metric_zero_rates(self):
        m = AeWorkflowMetric()
        assert m.success_rate == 0.0
        assert m.average_duration == 0.0

    def test_workflow_metric_computed(self):
        m = AeWorkflowMetric(execution_count=4, success_count=3, total_duration_seconds=80)
        assert m.success_rate == 75.0
        assert m.average_duration == 20.0

    def test_integration_metric_zero_rates(self):
        m = IntegrationMetric()
        assert m.error_rate == 0.0
        assert m.average_response_time == 0.0
        assert m.uptime_percentage == 100.0

    def test_integration_metric_computed(self):
        m = IntegrationMetric(call_count=10, error_count=2, total_response_time_ms=500)
        assert m.error_rate == 20.0
        assert m.average_response_time == 50.0
        assert m.uptime_percentage == 80.0


class TestAeLifecycle:
    def test_singleton_new_and_init_guard(self, ae_paths, monkeypatch):
        monkeypatch.setattr(ae_mod.os.path, "exists", Mock(return_value=False))
        e1 = AnalyticsEngine()
        assert e1._initialized is True
        e2 = AnalyticsEngine()
        assert e2 is e1

    def test_load_data_both_files(self, ae_paths, monkeypatch):
        (ae_paths / "workflow_metrics.json").write_text(json.dumps({
            "wf1": {
                "execution_count": 3, "success_count": 2, "failure_count": 1,
                "total_duration_seconds": 30.0, "total_time_saved_seconds": 5.0,
                "total_business_value": 10.0, "last_executed": "2026-01-01T00:00:00Z",
            }
        }))
        (ae_paths / "integration_metrics.json").write_text(json.dumps({
            "ig1": {
                "call_count": 5, "error_count": 1, "total_response_time_ms": 100.0,
                "last_called": "x", "status": "PARTIAL",
            }
        }))
        monkeypatch.setattr(ae_mod.os.path, "exists", Mock(side_effect=lambda p: Path(p).exists()))
        e = AnalyticsEngine()
        assert e.workflow_metrics["wf1"].success_count == 2
        assert e.integration_metrics["ig1"].status == "PARTIAL"

    def test_load_data_one_file_missing(self, ae_paths, monkeypatch):
        (ae_paths / "workflow_metrics.json").write_text("{}")
        monkeypatch.setattr(ae_mod.os.path, "exists", Mock(side_effect=lambda p: Path(p).exists()))
        e = AnalyticsEngine()
        assert e.workflow_metrics == {}
        assert e.integration_metrics == {}

    def test_load_data_corrupt_json(self, ae_paths, monkeypatch):
        (ae_paths / "workflow_metrics.json").write_text("{corrupt")
        monkeypatch.setattr(ae_mod.os.path, "exists", Mock(side_effect=lambda p: Path(p).exists()))
        e = AnalyticsEngine()
        assert e.workflow_metrics == {}

    def test_save_data_failure_logged(self, ae_engine):
        with patch("builtins.open", side_effect=RuntimeError("io down")):
            ae_engine._save_data()

    def test_save_data_roundtrip(self, ae_engine):
        ae_engine.workflow_metrics["wf1"] = AeWorkflowMetric(execution_count=1)
        ae_engine._save_data()
        assert Path(os.path.join(ae_engine.data_dir, "workflow_metrics.json")).exists()


class TestAeTracking:
    def test_track_workflow_execution_success(self, ae_engine):
        ae_engine.track_workflow_execution("wf1", True, 10.0, time_saved_seconds=5.0, business_value=3.0)
        m = ae_engine.workflow_metrics["wf1"]
        assert m.execution_count == 1
        assert m.success_count == 1
        assert m.total_duration_seconds == 10.0
        assert m.last_executed is not None

    def test_track_workflow_execution_failure_updates_existing(self, ae_engine):
        ae_engine.track_workflow_execution("wf1", True, 1.0)
        ae_engine.track_workflow_execution("wf1", False, 2.0)
        m = ae_engine.workflow_metrics["wf1"]
        assert m.execution_count == 2
        assert m.success_count == 1
        assert m.failure_count == 1

    def test_track_integration_call_error_status(self, ae_engine):
        ae_engine.track_integration_call("ig1", True, 10.0)
        ae_engine.track_integration_call("ig1", False, 20.0)
        assert ae_engine.integration_metrics["ig1"].status == "ERROR"
        assert ae_engine.integration_metrics["ig1"].error_count == 1

    def test_track_integration_call_partial_status(self, ae_engine):
        for _ in range(11):
            ae_engine.track_integration_call("ig2", True, 1.0)
        ae_engine.track_integration_call("ig2", False, 1.0)
        assert ae_engine.integration_metrics["ig2"].status == "PARTIAL"

    def test_track_integration_call_ready_status(self, ae_engine):
        ae_engine.track_integration_call("ig3", True, 5.0)
        assert ae_engine.integration_metrics["ig3"].status == "READY"


class TestAeReads:
    def test_get_workflow_analytics(self, ae_engine):
        ae_engine.workflow_metrics["wf1"] = AeWorkflowMetric(
            execution_count=4, total_time_saved_seconds=7200, total_business_value=42.5
        )
        result = ae_engine.get_workflow_analytics()
        assert result["total_executions"] == 4
        assert result["total_time_saved_hours"] == 2.0
        assert result["total_business_value"] == 42.5
        assert result["workflow_count"] == 1

    def test_get_workflow_analytics_empty(self, ae_engine):
        result = ae_engine.get_workflow_analytics()
        assert result["total_executions"] == 0
        assert result["workflows"] == {}

    def test_get_integration_health(self, ae_engine):
        ae_engine.integration_metrics["ig1"] = IntegrationMetric(status="READY")
        ae_engine.integration_metrics["ig2"] = IntegrationMetric(status="ERROR")
        result = ae_engine.get_integration_health()
        assert result["total_integrations"] == 2
        assert result["ready_count"] == 1

    def test_get_analytics_engine_singleton(self, monkeypatch):
        monkeypatch.setattr(ae_mod.os.path, "join", Mock(return_value="/tmp/nonexistent-ae"))
        monkeypatch.setattr(ae_mod.os.path, "exists", Mock(return_value=False))
        monkeypatch.setattr(ae_mod.os, "makedirs", Mock())
        a = ae_get_engine()
        b = ae_get_engine()
        assert a is b


# ============================================================================
# 3. activity_publisher
# ============================================================================


class TestActivityPublisher:
    def test_init_disabled_no_redis(self):
        p = ActivityPublisher()
        assert p.enabled is False
        assert p.redis is None

    def test_init_disabled_explicit(self):
        p = ActivityPublisher(redis_client=Mock(), enabled=False)
        assert p.enabled is False

    def test_init_enabled_with_redis(self):
        redis = Mock()
        p = ActivityPublisher(redis_client=redis)
        assert p.enabled is True
        assert p.redis is redis

    def test_publish_disabled_returns_false(self):
        assert ActivityPublisher().publish_activity("t1", "a1", "reasoning", "thinking") is False

    def test_publish_activity_both_channels(self):
        redis = Mock()
        p = ActivityPublisher(redis_client=redis)
        assert p.publish_activity("t1", "a1", "reasoning", "thinking", metadata={"m": 1}) is True
        assert redis.publish.call_count == 2
        payload = json.loads(redis.publish.call_args_list[0].args[1])
        assert payload["tenant_id"] == "t1"
        assert payload["metadata"] == {"m": 1}
        assert payload["session_key"] == "main"
        assert redis.publish.call_args_list[1].args[0] == "activity:t1:all"

    def test_publish_activity_default_metadata(self):
        redis = Mock()
        p = ActivityPublisher(redis_client=redis)
        p.publish_activity("t1", "a1", "reasoning", "thinking")
        payload = json.loads(redis.publish.call_args.args[1])
        assert payload["metadata"] == {}

    def test_publish_activity_custom_session(self):
        redis = Mock()
        p = ActivityPublisher(redis_client=redis)
        p.publish_activity("t1", "a1", "t", "s", session_key="alt")
        assert json.loads(redis.publish.call_args.args[1])["session_key"] == "alt"

    def test_publish_activity_redis_error_returns_false(self):
        redis = Mock()
        redis.publish.side_effect = RuntimeError("redis down")
        p = ActivityPublisher(redis_client=redis)
        assert p.publish_activity("t1", "a1", "t", "s") is False

    def test_publish_skill_execution(self):
        redis = Mock()
        p = ActivityPublisher(redis_client=redis)
        assert p.publish_skill_execution("t1", "a1", "skill-x", "working", "desc") is True
        payload = json.loads(redis.publish.call_args.args[1])
        assert payload["activity_type"] == "skill-execution"
        assert payload["metadata"] == {"skill_name": "skill-x", "task_description": "desc"}

    def test_publish_reasoning_activity(self):
        redis = Mock()
        p = ActivityPublisher(redis_client=redis)
        p.publish_reasoning_activity("t1", "a1", "planning")
        payload = json.loads(redis.publish.call_args.args[1])
        assert payload["activity_type"] == "reasoning"
        assert payload["state"] == "thinking"
        assert payload["metadata"] == {"phase": "planning"}

    def test_publish_episode_recording(self):
        redis = Mock()
        p = ActivityPublisher(redis_client=redis)
        p.publish_episode_recording("t1", "a1", "ep-1")
        payload = json.loads(redis.publish.call_args.args[1])
        assert payload["activity_type"] == "episode-recording"
        assert payload["state"] == "completed"
        assert payload["metadata"] == {"episode_id": "ep-1"}


class TestActivityPublisherFactory:
    def test_factory_redis_enabled(self):
        fake_redis = types = Mock()
        fake_module = types
        fake_module.from_url = Mock(return_value=fake_redis)
        config = Mock()
        config.redis.enabled = True
        config.redis.url = "redis://localhost:6379"
        with patch.dict("sys.modules", {"redis": fake_module}):
            with patch("core.config.get_config", return_value=config):
                p = get_activity_publisher()
        assert p.enabled is True
        assert p.redis is fake_redis

    def test_factory_redis_disabled(self):
        config = Mock()
        config.redis.enabled = False
        with patch("core.config.get_config", return_value=config):
            p = get_activity_publisher()
        assert p.enabled is False

    def test_factory_config_error_falls_back(self):
        with patch("core.config.get_config", side_effect=RuntimeError("cfg down")):
            p = get_activity_publisher()
        assert p.enabled is False

    def test_factory_redis_import_error_falls_back(self):
        config = Mock()
        config.redis.enabled = True
        real_import = builtins.__import__

        def _no_redis(name, *args, **kwargs):
            if name == "redis":
                raise ImportError("no redis")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_no_redis):
            with patch("core.config.get_config", return_value=config):
                p = get_activity_publisher()
        assert p.enabled is False


# ============================================================================
# 4. chat_context_manager
# ============================================================================


class FakeFrame:
    """Minimal pandas-DataFrame stand-in: len + sort_values + iterrows."""

    def __init__(self, rows):
        self.rows = rows

    def __len__(self):
        return len(self.rows)

    def sort_values(self, _col, ascending=True):
        self.rows = sorted(self.rows, key=lambda r: r["created_at"], reverse=True)
        return self

    def iterrows(self):
        return iter([(i, r) for i, r in enumerate(self.rows)])


def ccm_rows(entries):
    """entries: list of (id, created_at, metadata_json_or_None)."""
    return FakeFrame([
        {"id": eid, "created_at": ts, "metadata": meta if meta is not None else ""}
        for eid, ts, meta in entries
    ])


def ccm_table(rows=None):
    table = MagicMock()
    table.search = Mock(return_value=table)
    table.where = Mock(return_value=table)
    table.limit = Mock(return_value=table)
    table.to_pandas = Mock(return_value=ccm_rows([]) if rows is None else rows)
    return table


@pytest.fixture
def ccm_handler():
    return Mock(get_table=Mock(return_value=None))


@pytest.fixture
def ccm_manager(ccm_handler):
    return ChatContextManager(lancedb_handler=ccm_handler)


class TestResolveReference:
    async def test_no_db_returns_none(self):
        with patch("core.chat_context_manager.get_lancedb_handler", return_value=None):
            m = ChatContextManager(lancedb_handler=None)
        assert m.db is None
        assert await m.resolve_reference("text", "s1") is None

    async def test_no_session_id_returns_none(self, ccm_manager):
        assert await ccm_manager.resolve_reference("text", None) is None
        assert await ccm_manager.resolve_reference("text", "") is None

    async def test_no_table_returns_none(self, ccm_manager):
        assert await ccm_manager.resolve_reference("text", "s1") is None

    async def test_empty_results_returns_none(self, ccm_handler):
        m = ChatContextManager(lancedb_handler=ccm_handler)
        ccm_handler.get_table.return_value = ccm_table()
        assert await m.resolve_reference("text", "s1") is None

    async def test_typed_workflow_metadata_hit(self, ccm_handler):
        m = ChatContextManager(lancedb_handler=ccm_handler)
        now = datetime.now(timezone.utc).isoformat()
        ccm_handler.get_table.return_value = ccm_table(ccm_rows([
            ("m1", now, json.dumps({"workflow_id": "wf-1", "workflow_name": "W"})),
        ]))
        result = await m.resolve_reference("that workflow", "s1", entity_type="workflow")
        assert result == {"type": "workflow", "id": "wf-1", "name": "W"}

    async def test_typed_entities_hit(self, ccm_handler):
        m = ChatContextManager(lancedb_handler=ccm_handler)
        now = datetime.now(timezone.utc).isoformat()
        ccm_handler.get_table.return_value = ccm_table(ccm_rows([
            ("m1", now, json.dumps({"entities": {"task_id": "t-9", "task_name": "Task"}})),
        ]))
        result = await m.resolve_reference("it", "s1", entity_type="task")
        assert result == {"type": "task", "id": "t-9", "name": "Task"}

    async def test_untyped_metadata_workflow_hit(self, ccm_handler):
        m = ChatContextManager(lancedb_handler=ccm_handler)
        now = datetime.now(timezone.utc).isoformat()
        ccm_handler.get_table.return_value = ccm_table(ccm_rows([
            ("m1", now, json.dumps({"workflow_id": "wf-2"})),
        ]))
        result = await m.resolve_reference("it", "s1")
        assert result == {"type": "workflow", "id": "wf-2", "name": None}

    async def test_untyped_entities_workflow_hit(self, ccm_handler):
        m = ChatContextManager(lancedb_handler=ccm_handler)
        now = datetime.now(timezone.utc).isoformat()
        ccm_handler.get_table.return_value = ccm_table(ccm_rows([
            ("m1", now, json.dumps({"entities": {"workflow_id": "wf-3", "workflow_name": "N"}})),
        ]))
        result = await m.resolve_reference("it", "s1")
        assert result == {"type": "workflow", "id": "wf-3", "name": "N"}

    async def test_bad_metadata_row_skipped(self, ccm_handler):
        m = ChatContextManager(lancedb_handler=ccm_handler)
        now = datetime.now(timezone.utc).isoformat()
        ccm_handler.get_table.return_value = ccm_table(ccm_rows([
            ("m1", now, "{not json"),
        ]))
        assert await m.resolve_reference("it", "s1") is None

    async def test_newest_row_wins(self, ccm_handler):
        m = ChatContextManager(lancedb_handler=ccm_handler)
        old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        now = datetime.now(timezone.utc).isoformat()
        ccm_handler.get_table.return_value = ccm_table(ccm_rows([
            ("m1", old, json.dumps({"workflow_id": "old"})),
            ("m2", now, json.dumps({"workflow_id": "new"})),
        ]))
        result = await m.resolve_reference("it", "s1", entity_type="workflow")
        assert result["id"] == "new"

    async def test_search_exception_returns_none(self, ccm_handler):
        m = ChatContextManager(lancedb_handler=ccm_handler)
        ccm_handler.get_table.side_effect = RuntimeError("lance down")
        assert await m.resolve_reference("it", "s1") is None


class TestGetRecentContext:
    @pytest.fixture()
    def chat_history(self):
        return Mock()

    @pytest.fixture()
    def patched_history(self, chat_history):
        with patch("core.lancedb_handler.get_chat_history_manager", return_value=chat_history):
            yield chat_history

    async def test_no_messages_returns_empty(self, patched_history, ccm_handler):
        patched_history.get_session_history.return_value = []
        m = ChatContextManager(lancedb_handler=ccm_handler)
        assert await m.get_recent_context("s1", workspace_id="ws-1") == ""

    async def test_formats_messages(self, patched_history, ccm_handler):
        patched_history.get_session_history.return_value = [
            {"role": "user", "text": "hello"},
            {"role": "assistant", "text": "hi"},
            {"text": "no role"},
        ]
        m = ChatContextManager(lancedb_handler=ccm_handler)
        result = await m.get_recent_context("s1", workspace_id="ws-1", limit=5)
        assert "User: hello" in result
        assert "Assistant: hi" in result
        assert "Unknown: no role" in result

    async def test_truncates_long_content(self, patched_history, ccm_handler):
        patched_history.get_session_history.return_value = [
            {"role": "user", "text": "x" * 250},
        ]
        m = ChatContextManager(lancedb_handler=ccm_handler)
        result = await m.get_recent_context("s1")
        assert "..." in result
        assert result == "User: " + "x" * 197 + "..."


class TestStoreWorkflowContext:
    @pytest.fixture()
    def chat_history(self):
        return Mock(save_message=Mock(return_value=True))

    async def test_with_execution_id(self, chat_history, ccm_handler):
        with patch("core.lancedb_handler.get_chat_history_manager", return_value=chat_history):
            m = ChatContextManager(lancedb_handler=ccm_handler)
            assert await m.store_workflow_context("s1", "u1", "ws1", "wf-1", "W", execution_id="ex-1") is True
        kwargs = chat_history.save_message.call_args.kwargs
        assert kwargs["role"] == "system"
        assert "Execution ID: ex-1" in kwargs["content"]
        assert kwargs["metadata"]["type"] == "workflow_execution"
        assert kwargs["metadata"]["status"] == "started"

    async def test_without_execution_id(self, chat_history, ccm_handler):
        with patch("core.lancedb_handler.get_chat_history_manager", return_value=chat_history):
            m = ChatContextManager(lancedb_handler=ccm_handler)
            await m.store_workflow_context("s1", "u1", "ws1", "wf-1", "W", status="completed")
        content = chat_history.save_message.call_args.kwargs["content"]
        assert "Execution ID" not in content
        assert "completed" in content


class TestCcmFactory:
    def test_get_chat_context_manager(self):
        fake = Mock()
        with patch("core.lancedb_handler.get_chat_context_manager", return_value=fake):
            assert get_chat_context_manager("ws-1") is fake


# ============================================================================
# 5. chat_process_manager
# ============================================================================


class _CapturingProcess:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.__dict__.update(kwargs)
        type(self).instances.append(self)


def cpm_fake_process(**overrides):
    base = dict(
        id="p-1", user_id="u-1", name="proc", current_step=1, total_steps=3,
        steps='[{"step": 1}]', context='{"k": "v"}', inputs='{"a": 1}',
        outputs='{"step_0": {"o": 1}}', status="active",
        missing_parameters='["x"]',
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def cpm_db():
    """AsyncMock's return_value is itself an AsyncMock, so
    `result.scalar_one_or_none()` on an awaited execute() would return a
    coroutine instead of the configured value. Give db a MagicMock body with
    only execute()/commit() async."""
    cm = AsyncMock()
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock())
    db.commit = AsyncMock(return_value=None)
    cm.__aenter__.return_value = db
    cm.__aexit__ = AsyncMock(return_value=False)
    with patch("core.chat_process_manager.get_async_db_session", return_value=cm):
        yield db


class TestCreateProcess:
    async def test_with_tenant_id(self, cpm_db):
        _CapturingProcess.instances = []
        with patch("core.chat_process_manager.ChatProcess", _CapturingProcess):
            manager = ChatProcessManager()
            pid = await manager.create_process("u-1", "proc", [{"s": 1}], initial_context={"k": "v"}, tenant_id="t-1")
        assert cpm_db.execute.call_count == 0
        created = _CapturingProcess.instances[0]
        assert created.kwargs["tenant_id"] == "t-1"
        assert created.kwargs["steps"] == json.dumps([{"s": 1}])
        assert created.kwargs["context"] == json.dumps({"k": "v"})
        assert created.kwargs["status"] == "active"
        assert created.kwargs["total_steps"] == 1
        assert pid == created.kwargs["id"]
        cpm_db.add.assert_called_once()
        cpm_db.commit.assert_awaited_once()

    async def test_tenant_derived_from_user(self, cpm_db):
        _CapturingProcess.instances = []
        user = SimpleNamespace(tenant_id="t-user")
        cpm_db.execute.return_value.scalar_one_or_none.return_value = user
        with patch("core.chat_process_manager.ChatProcess", _CapturingProcess):
            manager = ChatProcessManager()
            await manager.create_process("u-1", "proc", [], tenant_id=None)
        assert _CapturingProcess.instances[0].kwargs["tenant_id"] == "t-user"

    async def test_tenant_default_when_user_missing(self, cpm_db):
        _CapturingProcess.instances = []
        cpm_db.execute.return_value.scalar_one_or_none.return_value = None
        with patch("core.chat_process_manager.ChatProcess", _CapturingProcess):
            manager = ChatProcessManager()
            await manager.create_process("u-1", "proc", [], tenant_id=None)
        assert _CapturingProcess.instances[0].kwargs["tenant_id"] == "default"

    async def test_default_context(self, cpm_db):
        _CapturingProcess.instances = []
        with patch("core.chat_process_manager.ChatProcess", _CapturingProcess):
            manager = ChatProcessManager()
            await manager.create_process("u-1", "proc", [], tenant_id="t")
        assert _CapturingProcess.instances[0].kwargs["context"] == "{}"


class TestGetProcess:
    async def test_not_found_returns_none(self, cpm_db):
        cpm_db.execute.return_value.scalar_one_or_none.return_value = None
        assert await ChatProcessManager().get_process("p-missing") is None

    async def test_found_converts_json(self, cpm_db):
        cpm_db.execute.return_value.scalar_one_or_none.return_value = cpm_fake_process()
        result = await ChatProcessManager().get_process("p-1")
        assert result["steps"] == [{"step": 1}]
        assert result["context"] == {"k": "v"}
        assert result["inputs"] == {"a": 1}
        assert result["outputs"] == {"step_0": {"o": 1}}
        assert result["missing_parameters"] == ["x"]
        assert result["created_at"] == "2026-01-01T00:00:00+00:00"
        assert result["status"] == "active"

    async def test_found_native_fields(self, cpm_db):
        cpm_db.execute.return_value.scalar_one_or_none.return_value = cpm_fake_process(
            steps=[{"step": 1}], context={"k": 2}, inputs={"a": 3},
            outputs={"o": 4}, missing_parameters=["y"], created_at=None,
        )
        result = await ChatProcessManager().get_process("p-1")
        assert result["steps"] == [{"step": 1}]
        assert result["context"] == {"k": 2}
        assert result["created_at"] is None
        assert result["updated_at"] is not None

    async def test_json_parse_error_returns_none(self, cpm_db):
        cpm_db.execute.return_value.scalar_one_or_none.return_value = cpm_fake_process(steps="{bad json")
        assert await ChatProcessManager().get_process("p-1") is None


class TestUpdateProcessStep:
    async def test_not_found_raises(self, cpm_db):
        cpm_db.execute.return_value.scalar_one_or_none.return_value = None
        with pytest.raises(ValueError):
            await ChatProcessManager().update_process_step("p-x", {"a": 1})

    async def test_missing_parameters_pauses(self, cpm_db):
        process = cpm_fake_process()
        cpm_db.execute.return_value.scalar_one_or_none.return_value = process
        result = await ChatProcessManager().update_process_step("p-1", {"a": 2}, missing_parameters=["x", "y"])
        assert result == {"next_step": 1, "status": "paused", "missing_parameters": ["x", "y"]}
        assert process.status == "paused"
        assert json.loads(process.inputs) == {"a": 2}
        assert process.updated_at is not None
        cpm_db.commit.assert_awaited_once()

    async def test_step_output_stored(self, cpm_db):
        process = cpm_fake_process()
        cpm_db.execute.return_value.scalar_one_or_none.return_value = process
        await ChatProcessManager().update_process_step("p-1", {}, step_output={"r": 1})
        assert json.loads(process.outputs) == {"step_0": {"o": 1}, "step_1": {"r": 1}}

    async def test_no_step_output_keeps_outputs(self, cpm_db):
        process = cpm_fake_process()
        cpm_db.execute.return_value.scalar_one_or_none.return_value = process
        await ChatProcessManager().update_process_step("p-1", {"a": 1})
        assert json.loads(process.outputs) == {"step_0": {"o": 1}}

    async def test_advances_to_next_step(self, cpm_db):
        process = cpm_fake_process()
        cpm_db.execute.return_value.scalar_one_or_none.return_value = process
        result = await ChatProcessManager().update_process_step("p-1", {"a": 1})
        assert result["next_step"] == 2
        assert result["status"] == "active"
        assert process.status == "active"

    async def test_last_step_completes(self, cpm_db):
        process = cpm_fake_process(current_step=2, total_steps=3)
        cpm_db.execute.return_value.scalar_one_or_none.return_value = process
        result = await ChatProcessManager().update_process_step("p-1", {"a": 1})
        assert result == {"next_step": 2, "status": "completed", "missing_parameters": []}
        assert process.status == "completed"

    async def test_native_inputs_dict(self, cpm_db):
        process = cpm_fake_process(inputs={"a": 1})
        cpm_db.execute.return_value.scalar_one_or_none.return_value = process
        await ChatProcessManager().update_process_step("p-1", {"b": 2})
        assert json.loads(process.inputs) == {"a": 1, "b": 2}


class TestResumeProcess:
    async def test_not_found_raises(self, cpm_db):
        cpm_db.execute.return_value.scalar_one_or_none.return_value = None
        with pytest.raises(ValueError):
            await ChatProcessManager().resume_process("p-x", {"a": 1})

    async def test_not_paused_raises(self, cpm_db):
        cpm_db.execute.return_value.scalar_one_or_none.return_value = cpm_fake_process(status="active")
        with pytest.raises(ValueError):
            await ChatProcessManager().resume_process("p-1", {"a": 1})

    async def test_resume_clears_all_missing(self, cpm_db):
        process = cpm_fake_process(status="paused", missing_parameters='["x", "y"]')
        cpm_db.execute.return_value.scalar_one_or_none.return_value = process
        result = await ChatProcessManager().resume_process("p-1", {"x": 1, "y": 2})
        assert result == {"status": "active", "remaining_missing": []}
        assert process.status == "active"
        assert json.loads(process.missing_parameters) == []
        assert json.loads(process.inputs) == {"a": 1, "x": 1, "y": 2}

    async def test_resume_partial_keeps_paused(self, cpm_db):
        process = cpm_fake_process(status="paused", missing_parameters='["x", "y"]')
        cpm_db.execute.return_value.scalar_one_or_none.return_value = process
        result = await ChatProcessManager().resume_process("p-1", {"x": 1})
        assert result == {"status": "paused", "remaining_missing": ["y"]}
        assert process.status == "paused"

    async def test_resume_native_missing_list(self, cpm_db):
        process = cpm_fake_process(status="paused", missing_parameters=["x"])
        cpm_db.execute.return_value.scalar_one_or_none.return_value = process
        result = await ChatProcessManager().resume_process("p-1", {"x": 1})
        assert result["remaining_missing"] == []


class TestCancelProcess:
    async def test_cancel_found(self, cpm_db):
        process = cpm_fake_process(status="paused")
        cpm_db.execute.return_value.scalar_one_or_none.return_value = process
        await ChatProcessManager().cancel_process("p-1")
        assert process.status == "cancelled"
        assert process.updated_at is not None
        cpm_db.commit.assert_awaited_once()

    async def test_cancel_not_found(self, cpm_db):
        cpm_db.execute.return_value.scalar_one_or_none.return_value = None
        await ChatProcessManager().cancel_process("p-x")
        cpm_db.commit.assert_not_awaited()


class TestGetUserProcesses:
    @pytest.fixture()
    def procs(self, cpm_db):
        cpm_db.execute.return_value.scalars.return_value.all.return_value = [
            cpm_fake_process(),
            cpm_fake_process(id="p-2", created_at=None),
        ]
        return cpm_db

    async def test_with_status(self, procs):
        result = await ChatProcessManager().get_user_processes("u-1", status="active")
        assert len(result) == 2
        assert result[0]["created_at"] == "2026-01-01T00:00:00+00:00"
        assert result[1]["created_at"] is None

    async def test_without_status(self, procs):
        result = await ChatProcessManager().get_user_processes("u-1")
        assert result[0]["name"] == "proc"

    async def test_empty(self, cpm_db):
        cpm_db.execute.return_value.scalars.return_value.all.return_value = []
        assert await ChatProcessManager().get_user_processes("u-1") == []


class TestProcessManagerSingleton:
    def test_get_process_manager(self):
        cpm_mod._process_manager = None
        a = get_process_manager()
        b = get_process_manager()
        assert a is b
        cpm_mod._process_manager = None


# ============================================================================
# 6. chat_session_manager
# ============================================================================


@pytest.fixture
def sessions_file(tmp_path):
    return str(tmp_path / "sessions.json")


def csm_db_cm(db):
    cm = MagicMock()
    cm.__enter__.return_value = db
    cm.__exit__.return_value = False
    return cm


def csm_file_manager(sessions_file, monkeypatch):
    monkeypatch.setenv("CHAT_PERSISTENCE_MODE", "HYBRID")
    monkeypatch.setenv("ATOM_CHAT_STORAGE", "file")
    return ChatSessionManager(sessions_file=sessions_file)


def csm_db_manager(sessions_file, monkeypatch, db):
    monkeypatch.setenv("CHAT_PERSISTENCE_MODE", "HYBRID")
    monkeypatch.setenv("ATOM_CHAT_STORAGE", "auto")
    monkeypatch.setattr("core.chat_session_manager.get_db_session", lambda: csm_db_cm(db))
    return ChatSessionManager(sessions_file=sessions_file)


def csm_strict_manager(sessions_file, monkeypatch, db=None, connection_error=False):
    monkeypatch.setenv("CHAT_PERSISTENCE_MODE", "STRICT_DB")
    monkeypatch.setenv("ATOM_CHAT_STORAGE", "auto")
    if connection_error:
        with patch("core.chat_session_manager.DB_AVAILABLE", True), \
             patch("core.chat_session_manager.SessionLocal", object), \
             patch("core.chat_session_manager.get_db_session", side_effect=RuntimeError("conn down")):
            return ChatSessionManager(sessions_file=sessions_file)
    with patch("core.chat_session_manager.DB_AVAILABLE", True), \
         patch("core.chat_session_manager.SessionLocal", object):
        monkeypatch.setattr(
            "core.chat_session_manager.get_db_session",
            lambda: csm_db_cm(db or MagicMock()),
        )
        return ChatSessionManager(sessions_file=sessions_file)


def csm_fake_session(**overrides):
    base = dict(
        id="s-1", user_id="u-1", title="T", metadata_json={"k": "v"},
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        message_count=2, channel_id="ch-1", thread_id="th-1",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def csm_fake_message(**overrides):
    base = dict(
        role="user", content="hello",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestCsmInit:
    def test_strict_db_missing_deps_raises(self, monkeypatch):
        monkeypatch.setenv("CHAT_PERSISTENCE_MODE", "STRICT_DB")
        with patch("core.chat_session_manager.DB_AVAILABLE", False):
            with pytest.raises(RuntimeError):
                ChatSessionManager()

    def test_strict_db_connection_failure_raises(self, monkeypatch, sessions_file):
        monkeypatch.setenv("CHAT_PERSISTENCE_MODE", "STRICT_DB")
        with patch("core.chat_session_manager.DB_AVAILABLE", True), \
             patch("core.chat_session_manager.SessionLocal", object), \
             patch("core.chat_session_manager.get_db_session", side_effect=RuntimeError("conn down")):
            with pytest.raises(RuntimeError):
                ChatSessionManager(sessions_file=sessions_file)

    def test_strict_db_success(self, monkeypatch, sessions_file):
        m = csm_strict_manager(sessions_file, monkeypatch, db=MagicMock())
        assert m.use_db is True

    def test_hybrid_db_mode_default(self, monkeypatch, sessions_file):
        db = MagicMock()
        m = csm_db_manager(sessions_file, monkeypatch, db)
        assert m.use_db is True
        assert m.persistence_mode == "HYBRID"

    def test_hybrid_file_mode(self, monkeypatch, sessions_file):
        m = csm_file_manager(sessions_file, monkeypatch)
        assert m.use_db is False
        assert os.path.exists(sessions_file)

    def test_no_db_available_uses_file(self, monkeypatch, sessions_file):
        monkeypatch.setenv("CHAT_PERSISTENCE_MODE", "HYBRID")
        monkeypatch.setenv("ATOM_CHAT_STORAGE", "auto")
        with patch("core.chat_session_manager.DB_AVAILABLE", False), \
             patch("core.chat_session_manager.SessionLocal", None):
            m = ChatSessionManager(sessions_file=sessions_file)
        assert m.use_db is False
        assert os.path.exists(sessions_file)

    def test_storage_env_check_exception_defaults_file(self, monkeypatch, sessions_file):
        monkeypatch.setenv("CHAT_PERSISTENCE_MODE", "HYBRID")
        monkeypatch.setenv("ATOM_CHAT_STORAGE", "auto")
        real_getenv = os.getenv

        def _boom(name, *args, **kwargs):
            if name == "ATOM_CHAT_STORAGE":
                raise RuntimeError("getenv boom")
            return real_getenv(name, *args, **kwargs)

        monkeypatch.setattr("core.chat_session_manager.os.getenv", _boom)
        with patch("core.chat_session_manager.DB_AVAILABLE", True), \
             patch("core.chat_session_manager.SessionLocal", object):
            m = ChatSessionManager(sessions_file=sessions_file)
        assert m.use_db is False
        assert os.path.exists(sessions_file)

    def test_import_failure_sets_db_unavailable(self, monkeypatch, sessions_file):
        """Cover the module-level except ImportError branch by re-executing
        the module source with core.database unavailable (import-time code,
        only reachable that way)."""
        monkeypatch.setenv("CHAT_PERSISTENCE_MODE", "STRICT_DB")
        src = Path(csm_mod.__file__).read_text()
        code = compile(src, csm_mod.__file__, "exec")
        real_import = builtins.__import__

        def _no_database(name, *args, **kwargs):
            if name == "core.database":
                raise ImportError("db dep missing")
            return real_import(name, *args, **kwargs)

        ns = {"__name__": "core.chat_session_manager_import_check", "__file__": csm_mod.__file__}
        with patch("builtins.__import__", side_effect=_no_database):
            with pytest.raises(RuntimeError):
                exec(code, ns)


class TestCsmFileOps:
    def test_save_and_load_roundtrip(self, sessions_file, monkeypatch):
        m = csm_file_manager(sessions_file, monkeypatch)
        assert m._save_sessions_file([{"session_id": "s1", "user_id": "u1"}]) is True
        loaded = m._load_sessions_file()
        assert loaded[0]["session_id"] == "s1"

    def test_load_missing_file(self, sessions_file, monkeypatch):
        m = csm_file_manager(sessions_file, monkeypatch)
        os.unlink(sessions_file)
        assert m._load_sessions_file() == []

    def test_load_corrupt_file(self, sessions_file, monkeypatch):
        with open(sessions_file, "w") as f:
            f.write("{not json")
        m = csm_file_manager(sessions_file, monkeypatch)
        assert m._load_sessions_file() == []

    def test_save_failure_returns_false(self, sessions_file, monkeypatch):
        m = csm_file_manager(sessions_file, monkeypatch)
        with patch("builtins.open", side_effect=RuntimeError("io down")):
            assert m._save_sessions_file([{"session_id": "s1"}]) is False

    def test_load_sessions_db_path(self, sessions_file, monkeypatch):
        db = MagicMock()
        db.query.return_value.all.return_value = [csm_fake_session(), csm_fake_session(id="s-2", created_at=None)]
        m = csm_db_manager(sessions_file, monkeypatch, db)
        sessions = m._load_sessions()
        assert sessions[0]["session_id"] == "s-1"
        assert sessions[0]["metadata"] == {"k": "v"}
        assert sessions[1]["created_at"] is None
        db.close.assert_called()

    def test_load_sessions_db_failure_falls_back_to_file(self, sessions_file, monkeypatch):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        m = csm_db_manager(sessions_file, monkeypatch, db)
        with open(sessions_file, "w") as f:
            json.dump([{"session_id": "s-f", "user_id": "u-1"}], f)
        assert m._load_sessions()[0]["session_id"] == "s-f"


class TestCsmFileMode:
    def test_create_and_get_session(self, sessions_file, monkeypatch):
        m = csm_file_manager(sessions_file, monkeypatch)
        sid = m.create_session(user_id="u-1", metadata={"k": "v"})
        session = m.get_session(sid)
        assert session["session_id"] == sid
        assert session["user_id"] == "u-1"
        assert session["metadata"] == {"k": "v"}
        assert session["message_count"] == 0

    def test_create_session_with_channel_and_thread(self, sessions_file, monkeypatch):
        m = csm_file_manager(sessions_file, monkeypatch)
        sid = m.create_session(user_id="u-1", channel_id="ch-9", thread_id="th-9")
        session = m.get_session(sid)
        assert session["metadata"]["channel_id"] == "ch-9"
        assert session["metadata"]["thread_id"] == "th-9"

    def test_create_session_explicit_id(self, sessions_file, monkeypatch):
        m = csm_file_manager(sessions_file, monkeypatch)
        sid = m.create_session(user_id="u-1", session_id="fixed-1")
        assert sid == "fixed-1"

    def test_get_missing_session(self, sessions_file, monkeypatch):
        m = csm_file_manager(sessions_file, monkeypatch)
        assert m.get_session("missing") is None

    def test_update_activity_with_history(self, sessions_file, monkeypatch):
        m = csm_file_manager(sessions_file, monkeypatch)
        sid = m.create_session(user_id="u-1")
        m.update_session_activity(sid, history=[{"role": "user"}], last_message="hi")
        session = m.get_session(sid)
        assert session["history"] == [{"role": "user"}]
        assert session["message_count"] == 1
        assert session["last_message"] == "hi"

    def test_update_activity_no_history(self, sessions_file, monkeypatch):
        m = csm_file_manager(sessions_file, monkeypatch)
        sid = m.create_session(user_id="u-1")
        m.update_session_activity(sid)
        assert m.get_session(sid)["message_count"] == 0

    def test_update_activity_missing_auto_recovers(self, sessions_file, monkeypatch):
        m = csm_file_manager(sessions_file, monkeypatch)
        m.update_session_activity("ghost", history=[{"role": "user"}])
        session = m.get_session("ghost")
        assert session is not None
        assert session["user_id"] == "default"
        assert session["metadata"] == {"source": "recovered"}

    def test_update_activity_missing_no_history(self, sessions_file, monkeypatch):
        m = csm_file_manager(sessions_file, monkeypatch)
        m.update_session_activity("ghost2")
        session = m.get_session("ghost2")
        assert session["history"] == []

    def test_list_user_sessions(self, sessions_file, monkeypatch):
        m = csm_file_manager(sessions_file, monkeypatch)
        m.create_session(user_id="u-1")
        m.create_session(user_id="u-1")
        m.create_session(user_id="u-2")
        assert len(m.list_user_sessions("u-1")) == 2
        assert len(m.list_user_sessions("u-1", limit=1)) == 1

    def test_delete_session(self, sessions_file, monkeypatch):
        m = csm_file_manager(sessions_file, monkeypatch)
        sid = m.create_session(user_id="u-1")
        assert m.delete_session(sid) is True
        assert m.get_session(sid) is None
        assert m.delete_session(sid) is False

    def test_rename_session(self, sessions_file, monkeypatch):
        m = csm_file_manager(sessions_file, monkeypatch)
        sid = m.create_session(user_id="u-1")
        assert m.rename_session(sid, "New") is True
        assert m.get_session(sid)["title"] == "New"
        assert m.rename_session("missing", "X") is False

    def test_rebind_owner_file(self, sessions_file, monkeypatch):
        m = csm_file_manager(sessions_file, monkeypatch)
        sid = m.create_session(user_id="u-1")
        assert m.rebind_session_owner(sid, "u-2") is True
        assert m.get_session(sid)["user_id"] == "u-2"

    def test_rebind_owner_missing(self, sessions_file, monkeypatch):
        m = csm_file_manager(sessions_file, monkeypatch)
        assert m.rebind_session_owner("nope", "u-2") is False


class TestCsmDbMode:
    def test_create_session_success(self, sessions_file, monkeypatch):
        db = MagicMock()
        m = csm_db_manager(sessions_file, monkeypatch, db)
        sid = m.create_session(user_id="u-1", metadata={"k": "v"}, channel_id="ch-1", thread_id="th-1")
        assert sid is not None
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_create_session_db_failure_falls_back_to_file(self, sessions_file, monkeypatch):
        db = MagicMock()
        db.add.side_effect = RuntimeError("db down")
        m = csm_db_manager(sessions_file, monkeypatch, db)
        sid = m.create_session(user_id="u-1")
        assert sid is not None
        assert m.get_session(sid) is not None
        db.rollback.assert_called_once()

    def test_get_session_found_with_history(self, sessions_file, monkeypatch):
        db = MagicMock()
        q1, q2 = MagicMock(), MagicMock()
        db.query.side_effect = [q1, q2]
        q1.filter.return_value.first.return_value = csm_fake_session()
        q2.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            csm_fake_message(), csm_fake_message(role="assistant", created_at=None),
        ]
        m = csm_db_manager(sessions_file, monkeypatch, db)
        session = m.get_session("s-1")
        assert session["user_id"] == "u-1"
        assert session["channel_id"] == "ch-1"
        assert session["thread_id"] == "th-1"
        assert session["message_count"] == 2
        assert session["history"][1]["created_at"] is None

    def test_get_session_metadata_none(self, sessions_file, monkeypatch):
        db = MagicMock()
        q1, q2 = MagicMock(), MagicMock()
        db.query.side_effect = [q1, q2]
        q1.filter.return_value.first.return_value = csm_fake_session(metadata_json=None)
        q2.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        m = csm_db_manager(sessions_file, monkeypatch, db)
        assert m.get_session("s-1")["metadata"] == {}

    def test_get_session_not_found_falls_back_to_file(self, sessions_file, monkeypatch):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.first.return_value = None
        m = csm_db_manager(sessions_file, monkeypatch, db)
        with open(sessions_file, "w") as f:
            json.dump([{"session_id": "s-f", "user_id": "u-1", "metadata": {}}], f)
        assert m.get_session("s-f")["session_id"] == "s-f"

    def test_get_session_db_failure_hybrid_falls_back(self, sessions_file, monkeypatch):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        m = csm_db_manager(sessions_file, monkeypatch, db)
        with open(sessions_file, "w") as f:
            json.dump([{"session_id": "s-f", "user_id": "u-1", "metadata": {}}], f)
        assert m.get_session("s-f")["session_id"] == "s-f"

    def test_update_activity_found(self, sessions_file, monkeypatch):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        session = csm_fake_session()
        q1.filter.return_value.first.return_value = session
        m = csm_db_manager(sessions_file, monkeypatch, db)
        m.update_session_activity("s-1", history=[{"role": "user"}, {"role": "assistant"}])
        assert session.message_count == 2
        db.commit.assert_called_once()

    def test_update_activity_not_found_auto_recovers(self, sessions_file, monkeypatch):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.first.return_value = None
        m = csm_db_manager(sessions_file, monkeypatch, db)
        m.update_session_activity("ghost", history=[])
        assert m.get_session("ghost") is not None

    def test_update_activity_db_failure_hybrid(self, sessions_file, monkeypatch):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        m = csm_db_manager(sessions_file, monkeypatch, db)
        m.update_session_activity("ghost2")
        assert m.get_session("ghost2") is not None

    def test_list_user_sessions_db_only_no_legacy(self, sessions_file, monkeypatch):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [csm_fake_session()]
        m = csm_db_manager(sessions_file, monkeypatch, db)
        results = m.list_user_sessions("u-1")
        assert results[0]["session_id"] == "s-1"
        assert results[0]["title"] == "T"

    def test_list_user_sessions_hybrid_merge(self, sessions_file, monkeypatch):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [csm_fake_session()]
        m = csm_db_manager(sessions_file, monkeypatch, db)
        with open(sessions_file, "w") as f:
            json.dump([
                {"session_id": "legacy-1", "user_id": "u-1", "last_active": "2026-01-03T00:00:00Z", "history": []},
                {"session_id": "s-1", "user_id": "u-1", "last_active": "2026-01-01T00:00:00Z"},  # in DB → excluded
                {"session_id": "legacy-2", "user_id": "u-9", "last_active": "2026-01-04T00:00:00Z"},  # other user
            ], f)
        results = m.list_user_sessions("u-1")
        assert {r["session_id"] for r in results} == {"s-1", "legacy-1"}
        assert results[0]["session_id"] == "legacy-1"  # newest last_active first

    def test_list_user_sessions_hybrid_merge_failure(self, sessions_file, monkeypatch):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [csm_fake_session()]
        m = csm_db_manager(sessions_file, monkeypatch, db)
        with patch.object(m, "_load_sessions_file", side_effect=RuntimeError("boom")):
            results = m.list_user_sessions("u-1")
        assert results[0]["session_id"] == "s-1"

    def test_list_user_sessions_db_failure_uses_file(self, sessions_file, monkeypatch):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        m = csm_db_manager(sessions_file, monkeypatch, db)
        with open(sessions_file, "w") as f:
            json.dump([{"session_id": "s-f", "user_id": "u-1", "last_active": "2026-01-01T00:00:00Z", "history": []}], f)
        results = m.list_user_sessions("u-1")
        assert results[0]["session_id"] == "s-f"

    def test_rebind_owner_both_stores(self, sessions_file, monkeypatch):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.first.return_value = csm_fake_session()
        m = csm_db_manager(sessions_file, monkeypatch, db)
        with open(sessions_file, "w") as f:
            json.dump([{"session_id": "s-1", "user_id": "u-1"}], f)
        assert m.rebind_session_owner("s-1", "u-2") is True
        assert m.get_session("s-1")["user_id"] == "u-2"

    def test_rebind_owner_db_only(self, sessions_file, monkeypatch):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.first.return_value = csm_fake_session()
        m = csm_db_manager(sessions_file, monkeypatch, db)
        assert m.rebind_session_owner("s-1", "u-2") is True

    def test_rebind_owner_db_missing_file_saves(self, sessions_file, monkeypatch):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.first.return_value = None
        m = csm_db_manager(sessions_file, monkeypatch, db)
        with open(sessions_file, "w") as f:
            json.dump([{"session_id": "s-1", "user_id": "u-1"}], f)
        assert m.rebind_session_owner("s-1", "u-2") is True

    def test_rebind_owner_db_failure_file_succeeds(self, sessions_file, monkeypatch):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        m = csm_db_manager(sessions_file, monkeypatch, db)
        with open(sessions_file, "w") as f:
            json.dump([{"session_id": "s-1", "user_id": "u-1"}], f)
        assert m.rebind_session_owner("s-1", "u-2") is True

    def test_rebind_owner_file_save_failure(self, sessions_file, monkeypatch):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.first.return_value = csm_fake_session()
        m = csm_db_manager(sessions_file, monkeypatch, db)
        with open(sessions_file, "w") as f:
            json.dump([{"session_id": "s-1", "user_id": "u-1"}], f)
        with patch.object(m, "_save_sessions_file", return_value=False):
            assert m.rebind_session_owner("s-1", "u-2") is True  # DB store still durable

    def test_rebind_owner_file_load_failure(self, sessions_file, monkeypatch):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.first.return_value = csm_fake_session()
        m = csm_db_manager(sessions_file, monkeypatch, db)
        with patch.object(m, "_load_sessions_file", side_effect=RuntimeError("boom")):
            assert m.rebind_session_owner("s-1", "u-2") is True

    def test_delete_session_found(self, sessions_file, monkeypatch):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.first.return_value = csm_fake_session()
        m = csm_db_manager(sessions_file, monkeypatch, db)
        assert m.delete_session("s-1") is True
        db.delete.assert_called_once()

    def test_delete_session_db_failure_file_cleanup(self, sessions_file, monkeypatch):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        m = csm_db_manager(sessions_file, monkeypatch, db)
        with open(sessions_file, "w") as f:
            json.dump([{"session_id": "s-1", "user_id": "u-1"}], f)
        assert m.delete_session("s-1") is True

    def test_rename_session_found(self, sessions_file, monkeypatch):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        session = csm_fake_session()
        q1.filter.return_value.first.return_value = session
        m = csm_db_manager(sessions_file, monkeypatch, db)
        assert m.rename_session("s-1", "Renamed") is True
        assert session.title == "Renamed"
        db.commit.assert_called_once()

    def test_rename_session_db_failure_returns_false(self, sessions_file, monkeypatch):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        m = csm_db_manager(sessions_file, monkeypatch, db)
        assert m.rename_session("s-1", "Renamed") is False


class TestCsmStrictDbMode:
    def test_create_session_success(self, sessions_file, monkeypatch):
        db = MagicMock()
        m = csm_strict_manager(sessions_file, monkeypatch, db=db)
        assert m.create_session(user_id="u-1") is not None
        db.commit.assert_called_once()

    def test_create_session_failure_raises(self, sessions_file, monkeypatch):
        db = MagicMock()
        db.add.side_effect = RuntimeError("db down")
        m = csm_strict_manager(sessions_file, monkeypatch, db=db)
        with pytest.raises(RuntimeError):
            m.create_session(user_id="u-1")
        db.rollback.assert_called_once()

    def test_get_session_found(self, sessions_file, monkeypatch):
        db = MagicMock()
        q1, q2 = MagicMock(), MagicMock()
        db.query.side_effect = [q1, q2]
        q1.filter.return_value.first.return_value = csm_fake_session()
        q2.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        m = csm_strict_manager(sessions_file, monkeypatch, db=db)
        assert m.get_session("s-1")["user_id"] == "u-1"

    def test_get_session_not_found_returns_none(self, sessions_file, monkeypatch):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.first.return_value = None
        m = csm_strict_manager(sessions_file, monkeypatch, db=db)
        assert m.get_session("missing") is None

    def test_get_session_failure_raises(self, sessions_file, monkeypatch):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        m = csm_strict_manager(sessions_file, monkeypatch, db=db)
        with pytest.raises(RuntimeError):
            m.get_session("s-1")

    def test_update_activity_found(self, sessions_file, monkeypatch):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        session = csm_fake_session()
        q1.filter.return_value.first.return_value = session
        m = csm_strict_manager(sessions_file, monkeypatch, db=db)
        m.update_session_activity("s-1", history=[{"role": "user"}])
        assert session.message_count == 1

    def test_update_activity_not_found_returns(self, sessions_file, monkeypatch):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.first.return_value = None
        m = csm_strict_manager(sessions_file, monkeypatch, db=db)
        assert m.update_session_activity("missing", history=[]) is None

    def test_update_activity_failure_raises(self, sessions_file, monkeypatch):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        m = csm_strict_manager(sessions_file, monkeypatch, db=db)
        with pytest.raises(RuntimeError):
            m.update_session_activity("s-1")

    def test_list_user_sessions_strict_returns_db_only(self, sessions_file, monkeypatch):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [csm_fake_session()]
        m = csm_strict_manager(sessions_file, monkeypatch, db=db)
        results = m.list_user_sessions("u-1")
        assert len(results) == 1
        with open(sessions_file, "w") as f:
            json.dump([{"session_id": "legacy-1", "user_id": "u-1", "last_active": "2026-01-01T00:00:00Z", "history": []}], f)
        assert len(m.list_user_sessions("u-1")) == 1  # no hybrid merge in strict

    def test_rebind_owner_strict(self, sessions_file, monkeypatch):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.first.return_value = csm_fake_session()
        m = csm_strict_manager(sessions_file, monkeypatch, db=db)
        assert m.rebind_session_owner("s-1", "u-2") is True

    def test_delete_session_strict(self, sessions_file, monkeypatch):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.first.return_value = csm_fake_session()
        m = csm_strict_manager(sessions_file, monkeypatch, db=db)
        assert m.delete_session("s-1") is True

    def test_rename_session_strict(self, sessions_file, monkeypatch):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        session = csm_fake_session()
        q1.filter.return_value.first.return_value = session
        m = csm_strict_manager(sessions_file, monkeypatch, db=db)
        assert m.rename_session("s-1", "X") is True


class TestCsmFactory:
    def test_get_chat_session_manager(self, monkeypatch):
        monkeypatch.setenv("CHAT_PERSISTENCE_MODE", "FILE")
        m = get_chat_session_manager("ws-2")
        assert isinstance(m, ChatSessionManager)
        assert m.workspace_id == "ws-2"


# ============================================================================
# 7. debug_query
# ============================================================================


def dq_event(**overrides):
    base = dict(
        id="e-1", event_type="log", component_type="agent", component_id="agent-1",
        correlation_id="corr-1", level="INFO", message="msg", data={},
        timestamp=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def dq_insight(**overrides):
    base = dict(
        id="i-1", insight_type="error", severity="warning", title="T", summary="S",
        confidence_score=0.9, generated_at=datetime.now(timezone.utc),
        description="desc", suggestions=["s1"], source_event_id=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def dq_cache():
    return MagicMock()


@pytest.fixture
def dq_no_cache():
    with patch("core.debug_query.DEBUG_QUERY_CACHE_ENABLED", False):
        yield


def _dq_health_db(total, errors, insights=None):
    """db whose query chains model get_component_health's two queries."""
    db = MagicMock()
    q1, q2 = MagicMock(), MagicMock()
    db.query.side_effect = [q1, q2]
    f1 = q1.filter.return_value
    f1.count.return_value = total
    f1.filter.return_value.count.return_value = errors
    f2 = q2.filter.return_value
    f2.order_by.return_value.limit.return_value.all.return_value = insights or []
    return db


class TestDqComponentHealth:
    async def test_no_events_unknown(self, dq_no_cache, dq_cache):
        db = _dq_health_db(0, 0)
        with patch("core.debug_query.get_debug_cache", return_value=dq_cache):
            result = await DebugQuery(db).get_component_health("agent", "ghost-1", "1h")
        assert result["status"] == "unknown"
        assert result["health_score"] == 100
        assert result["error_rate"] == 0

    async def test_healthy(self, dq_no_cache, dq_cache):
        db = _dq_health_db(20, 1)
        with patch("core.debug_query.get_debug_cache", return_value=dq_cache):
            result = await DebugQuery(db).get_component_health("agent", "agent-1", "1h")
        assert result["status"] == "healthy"
        assert result["health_score"] == 95
        assert result["error_events"] == 1

    async def test_degraded(self, dq_no_cache, dq_cache):
        db = _dq_health_db(20, 6)
        with patch("core.debug_query.get_debug_cache", return_value=dq_cache):
            result = await DebugQuery(db).get_component_health("agent", "agent-1", "1h")
        assert result["status"] == "degraded"
        assert result["health_score"] == 70

    async def test_unhealthy(self, dq_no_cache, dq_cache):
        db = _dq_health_db(10, 5)
        with patch("core.debug_query.get_debug_cache", return_value=dq_cache):
            result = await DebugQuery(db).get_component_health("agent", "agent-1", "1h")
        assert result["status"] == "unhealthy"

    async def test_insights_serialized(self, dq_no_cache, dq_cache):
        db = _dq_health_db(1, 0, insights=[
            dq_insight(generated_at=datetime.now(timezone.utc)),
            dq_insight(generated_at=None),
        ])
        with patch("core.debug_query.get_debug_cache", return_value=dq_cache):
            result = await DebugQuery(db).get_component_health("agent", "agent-1", "1h")
        assert result["insights"][0]["title"] == "T"
        assert result["insights"][1]["generated_at"] is None

    async def test_cache_hit_skips_query(self, dq_cache):
        db = MagicMock()
        dq_cache.get.return_value = {"cached": True}
        with patch("core.debug_query.get_debug_cache", return_value=dq_cache):
            result = await DebugQuery(db).get_component_health("agent", "agent-1", "1h")
        assert result == {"cached": True}
        db.query.assert_not_called()

    async def test_cache_miss_stores_result(self, dq_cache):
        dq_cache.get.return_value = None
        db = _dq_health_db(0, 0)
        with patch("core.debug_query.get_debug_cache", return_value=dq_cache):
            await DebugQuery(db).get_component_health("agent", "agent-1", "1h")
        dq_cache.set.assert_called_once()
        assert dq_cache.set.call_args.args[0].startswith("health:agent:agent-1:")

    async def test_exception_returns_error_dict(self, dq_no_cache, dq_cache):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        with patch("core.debug_query.get_debug_cache", return_value=dq_cache):
            result = await DebugQuery(db).get_component_health("agent", "agent-1", "1h")
        assert result["status"] == "error"
        assert result["health_score"] == 0


class TestDqOperationProgress:
    @pytest.fixture()
    def progress_db(self):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.order_by.return_value.all.return_value = None
        return db

    async def test_not_found(self, progress_db):
        progress_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        result = await DebugQuery(progress_db).get_operation_progress("op-x")
        assert result["status"] == "not_found"
        assert result["progress"] == 0

    async def test_completed(self, progress_db):
        now = datetime.now(timezone.utc)
        progress_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            dq_event(data={"step": 1, "status": "completed"}, timestamp=now),
            dq_event(data={"step": 2, "progress": 1.0}, timestamp=now),
        ]
        result = await DebugQuery(progress_db).get_operation_progress("op-1")
        assert result["status"] == "completed"
        assert result["progress"] == 1.0
        assert result["total_steps"] == 2
        assert result["completed_steps"] == 2
        assert "Operation has 2 steps" in result["insights"]

    async def test_failed(self, progress_db):
        now = datetime.now(timezone.utc)
        progress_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            dq_event(data={"step": 1}, level="ERROR", timestamp=now),
        ]
        result = await DebugQuery(progress_db).get_operation_progress("op-1")
        assert result["status"] == "failed"
        assert result["error_count"] == 1

    async def test_in_progress_with_last_action(self, progress_db):
        now = datetime.now(timezone.utc)
        progress_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            dq_event(data={"step": 1, "status": "completed"}, message="step one", timestamp=now),
            dq_event(data={"step": 2, "status": "running"}, message="step two", timestamp=now),
        ]
        result = await DebugQuery(progress_db).get_operation_progress("op-1")
        assert result["status"] == "in_progress"
        assert result["progress"] == 0.5
        assert "Last action: step two" in result["insights"]

    async def test_started_no_timestamps(self, progress_db):
        progress_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            dq_event(data={"step": 1}, message=None, timestamp=None),
        ]
        result = await DebugQuery(progress_db).get_operation_progress("op-1")
        assert result["status"] == "started"
        assert result["progress"] == 0
        assert result["started_at"] is None
        assert result["updated_at"] is None
        assert result["insights"] == ["Operation has 1 steps"]

    async def test_exception_returns_error_dict(self, progress_db):
        progress_db.query.side_effect = RuntimeError("db down")
        result = await DebugQuery(progress_db).get_operation_progress("op-1")
        assert result["status"] == "error"


class TestDqExplainError:
    @pytest.fixture()
    def explain_db(self):
        db = MagicMock()
        q1, q2 = MagicMock(), MagicMock()
        db.query.side_effect = [q1, q2]
        return db, q1, q2

    async def test_not_found(self, explain_db):
        db, q1, q2 = explain_db
        q1.filter.return_value.first.return_value = None
        result = await DebugQuery(db).explain_error("err-x")
        assert result["found"] is False

    async def test_basic_explanation(self, explain_db):
        db, q1, q2 = explain_db
        now = datetime.now(timezone.utc)
        q1.filter.return_value.first.return_value = dq_event(
            id="err-1", level="ERROR", message="boom", timestamp=now
        )
        q2.filter.return_value.all.return_value = []
        result = await DebugQuery(db).explain_error("err-1")
        assert result["found"] is True
        assert result["message"] == "boom"
        assert result["root_cause"] == "Error in agent"
        assert result["confidence"] == 0.5
        assert len(result["suggestions"]) == 3

    async def test_insight_backed_explanation(self, explain_db):
        db, q1, q2 = explain_db
        now = datetime.now(timezone.utc)
        q1.filter.return_value.first.return_value = dq_event(
            id="err-1", level="ERROR", message="boom", timestamp=None
        )
        q2.filter.return_value.all.return_value = [
            dq_insight(description="root cause", suggestions=["fix it"], confidence_score=0.9)
        ]
        result = await DebugQuery(db).explain_error("err-1")
        assert result["root_cause"] == "root cause"
        assert result["suggestions"] == ["fix it"]
        assert result["confidence"] == 0.9
        assert result["timestamp"] is None

    async def test_exception_returns_error_dict(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        result = await DebugQuery(db).explain_error("err-1")
        assert result["found"] is False
        assert "error" in result


class TestDqCompareComponents:
    @pytest.fixture(autouse=True)
    def _fresh_cache(self):
        """The real DebugInsightCache is a module-level singleton shared by
        every test in the process — one test's get_component_health call
        caches entries the next test then consumes (skipping its db.query
        side_effects and shifting which mock query is used). Give each
        compare test its own isolated cache so the mock query layout is
        deterministic."""
        from core.debug_cache import DebugInsightCache
        with patch("core.debug_query.get_debug_cache", return_value=DebugInsightCache()):
            yield

    @pytest.fixture()
    def compare_db(self):
        db = MagicMock()
        q1, q2, q3, q4 = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        db.query.side_effect = [q1, q2, q3, q4]
        f1, f3 = q1.filter.return_value, q3.filter.return_value
        f1.count.return_value = 10
        f1.filter.return_value.count.return_value = 1
        f3.count.return_value = 10
        f3.filter.return_value.count.return_value = 4
        return db

    async def test_single_component_needs_two(self, compare_db):
        result = await DebugQuery(compare_db).compare_components([{"type": "agent", "id": "a1"}])
        assert result["insights"] == ["Need at least 2 components to compare"]

    async def test_health_gap_and_error_variance(self, compare_db):
        # a1: 10 events 1 error (90 health), a2: 10 events 4 errors (60 health)
        result = await DebugQuery(compare_db).compare_components([
            {"type": "agent", "id": "a1"},
            {"type": "agent", "id": "a2"},
        ])
        assert any("points healthier" in i for i in result["insights"])
        assert any("Error rate varies" in i for i in result["insights"])

    async def test_no_insights(self):
        db = MagicMock()
        q1, q2, q3, q4 = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        db.query.side_effect = [q1, q2, q3, q4]
        f1, f3 = q1.filter.return_value, q3.filter.return_value
        f1.count.return_value = 100
        f1.filter.return_value.count.return_value = 10
        f3.count.return_value = 100
        f3.filter.return_value.count.return_value = 12
        result = await DebugQuery(db).compare_components([
            {"type": "agent", "id": "a1"},
            {"type": "agent", "id": "a2"},
        ])
        assert result["insights"] == []

    async def test_exception_returns_failure(self):
        db = MagicMock()
        with patch.object(DebugQuery, "get_component_health", side_effect=RuntimeError("db down")):
            result = await DebugQuery(db).compare_components([{"type": "agent", "id": "a1"}])
        assert "Comparison failed" in result["insights"][0]


class TestDqAsk:
    async def test_why_is_workflow_failing(self):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            dq_event(message="db timeout"),
            dq_event(message="db timeout"),
            dq_event(message="db timeout"),
        ]
        result = await DebugQuery(db).ask("Why is workflow-789 failing?")
        assert result["confidence"] == 0.85
        assert "db timeout" in result["answer"]
        assert result["evidence"][0]["error_count"] == 3
        assert len(result["suggestions"]) == 3

    async def test_why_is_agent_failing_no_errors(self):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        result = await DebugQuery(db).ask("Why is agent-42 failing?")
        assert result["answer"] == "No recent errors found for agent-42"
        assert result["confidence"] == 0.8

    async def test_health_agent(self):
        db = _dq_health_db(5, 1)
        result = await DebugQuery(db).ask("what is the health of agent-1")
        assert result["confidence"] == 0.9
        assert "agent-1 is" in result["answer"]
        assert "1 errors in 5 events" in result["answer"]
        assert result["evidence"][0]["health_score"] == 80

    async def test_health_browser(self):
        db = _dq_health_db(0, 0)
        result = await DebugQuery(db).ask("browser-7 health?")
        assert "browser-7 is unknown" in result["answer"]

    async def test_error_branch(self):
        db = MagicMock()
        result = await DebugQuery(db).ask("there is an error somewhere")
        assert result["answer"] == "Please provide the error ID"

    async def test_default_response(self):
        db = MagicMock()
        result = await DebugQuery(db).ask("hello there")
        assert result["confidence"] == 0.3
        assert "couldn't understand" in result["answer"]

    async def test_exception_returns_error_answer(self):
        db = MagicMock()
        with patch.object(DebugQuery, "get_component_health", side_effect=RuntimeError("boom")):
            result = await DebugQuery(db).ask("health agent-1?")
        assert result["confidence"] == 0.0
        assert "Error processing question" in result["answer"]


class TestDqExplainComponentFailure:
    async def test_no_errors(self):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        result = await DebugQuery(db)._explain_component_failure("agent-1")
        assert result["answer"] == "No recent errors found for agent-1"

    async def test_most_common_error(self):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            dq_event(message="same", level="ERROR"),
            dq_event(message="same", level="ERROR"),
            dq_event(message="other", level="CRITICAL"),
        ]
        result = await DebugQuery(db)._explain_component_failure("agent-1")
        assert result["answer"].endswith("same")
        assert result["evidence"][0]["error_count"] == 2
        assert result["evidence"][0]["recent_errors"] == 3

    async def test_exception(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        result = await DebugQuery(db)._explain_component_failure("agent-1")
        assert result["confidence"] == 0.0


class TestDqHelpers:
    def test_parse_time_range(self):
        q = DebugQuery(MagicMock())
        now = datetime.now(timezone.utc)
        assert (now - q._parse_time_range("1h")).total_seconds() == pytest.approx(3600, abs=5)
        assert (now - q._parse_time_range("2d")).total_seconds() == pytest.approx(172800, abs=5)
        assert (now - q._parse_time_range("30m")).total_seconds() == pytest.approx(1800, abs=5)

    def test_parse_time_range_invalid_suffix_falls_back(self):
        q = DebugQuery(MagicMock())
        now = datetime.now(timezone.utc)
        assert (now - q._parse_time_range("invalid")).total_seconds() == pytest.approx(3600, abs=5)

    def test_parse_time_range_unknown_suffix(self):
        q = DebugQuery(MagicMock())
        now = datetime.now(timezone.utc)
        assert (now - q._parse_time_range("5x")).total_seconds() == pytest.approx(3600, abs=5)

    def test_insight_to_dict(self):
        q = DebugQuery(MagicMock())
        d = q._insight_to_dict(dq_insight())
        assert d["id"] == "i-1"
        assert d["type"] == "error"
        assert d["generated_at"] is not None

    def test_insight_to_dict_no_generated_at(self):
        q = DebugQuery(MagicMock())
        d = q._insight_to_dict(dq_insight(generated_at=None))
        assert d["generated_at"] is None


# ============================================================================
# 8. debug_monitor
# ============================================================================


def dm_insight(**overrides):
    base = dict(
        id="i-1", insight_type="error", severity="warning", title="T", summary="S",
        affected_components=[{"type": "agent", "id": "agent-1"}],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestDmSystemHealth:
    async def test_healthy(self):
        db = MagicMock()
        q1, q2, q3, q4 = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        db.query.side_effect = [q1, q2, q3, q4]
        q1.filter.return_value.scalar.return_value = 100
        q2.filter.return_value.scalar.return_value = 5
        q3.filter.return_value.scalar.return_value = 2
        q4.filter.return_value.group_by.return_value.all.return_value = [("agent", 100, 5)]
        result = await DebugMonitor(db).get_system_health()
        assert result["status"] == "healthy"
        assert result["overall_health_score"] == 95
        assert result["total_events"] == 100
        assert result["active_operations"] == 2
        assert result["components"]["agent"]["health_score"] == 95

    async def test_degraded_and_unhealthy(self):
        db = MagicMock()
        q1, q2, q3, q4 = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        db.query.side_effect = [q1, q2, q3, q4]
        q1.filter.return_value.scalar.return_value = 100
        q2.filter.return_value.scalar.return_value = 30
        q3.filter.return_value.scalar.return_value = 0
        q4.filter.return_value.group_by.return_value.all.return_value = []
        result = await DebugMonitor(db).get_system_health()
        assert result["status"] == "degraded"

        db2 = MagicMock()
        q1, q2, q3, q4 = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        db2.query.side_effect = [q1, q2, q3, q4]
        q1.filter.return_value.scalar.return_value = 100
        q2.filter.return_value.scalar.return_value = 40
        q3.filter.return_value.scalar.return_value = 0
        q4.filter.return_value.group_by.return_value.all.return_value = []
        result2 = await DebugMonitor(db2).get_system_health()
        assert result2["status"] == "unhealthy"

    async def test_no_events(self):
        db = MagicMock()
        q1, q2, q3, q4 = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        db.query.side_effect = [q1, q2, q3, q4]
        q1.filter.return_value.scalar.return_value = 0
        q2.filter.return_value.scalar.return_value = 0
        q3.filter.return_value.scalar.return_value = 0
        q4.filter.return_value.group_by.return_value.all.return_value = []
        result = await DebugMonitor(db).get_system_health()
        assert result["overall_health_score"] == 100
        assert result["status"] == "healthy"
        assert result["error_rate"] == 0

    async def test_exception_returns_error_dict(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        result = await DebugMonitor(db).get_system_health()
        assert result["status"] == "error"
        assert result["overall_health_score"] == 0


class TestDmComponentHealth:
    @pytest.fixture()
    def comp_db(self):
        db = MagicMock()
        q1, q2, q3 = MagicMock(), MagicMock(), MagicMock()
        db.query.side_effect = [q1, q2, q3]
        q1.filter.return_value.scalar.return_value = 10
        q2.filter.return_value.scalar.return_value = 1
        q3.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        return db

    async def test_healthy(self, comp_db):
        result = await DebugMonitor(comp_db).get_component_health("agent", "agent-1")
        assert result["status"] == "healthy"
        assert result["health_score"] == 90
        assert result["error_rate"] == 10.0

    async def test_degraded(self):
        db = MagicMock()
        q1, q2, q3 = MagicMock(), MagicMock(), MagicMock()
        db.query.side_effect = [q1, q2, q3]
        q1.filter.return_value.scalar.return_value = 10
        q2.filter.return_value.scalar.return_value = 3
        q3.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        result = await DebugMonitor(db).get_component_health("agent", "agent-1")
        assert result["status"] == "degraded"

    async def test_unhealthy(self):
        db = MagicMock()
        q1, q2, q3 = MagicMock(), MagicMock(), MagicMock()
        db.query.side_effect = [q1, q2, q3]
        q1.filter.return_value.scalar.return_value = 10
        q2.filter.return_value.scalar.return_value = 5
        q3.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        result = await DebugMonitor(db).get_component_health("agent", "agent-1")
        assert result["status"] == "unhealthy"
        assert result["health_score"] == 50

    async def test_unhealthy_no_events_is_healthy(self):
        db = MagicMock()
        q1, q2, q3 = MagicMock(), MagicMock(), MagicMock()
        db.query.side_effect = [q1, q2, q3]
        q1.filter.return_value.scalar.return_value = 0
        q2.filter.return_value.scalar.return_value = 0
        q3.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        result = await DebugMonitor(db).get_component_health("agent", "ghost")
        assert result["status"] == "healthy"
        assert result["health_score"] == 100

    async def test_relevant_insights_attached(self):
        db = MagicMock()
        q1, q2, q3 = MagicMock(), MagicMock(), MagicMock()
        db.query.side_effect = [q1, q2, q3]
        q1.filter.return_value.scalar.return_value = 1
        q2.filter.return_value.scalar.return_value = 0
        q3.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            dm_insight(),
            dm_insight(affected_components=[{"type": "agent", "id": "other"}]),
            dm_insight(affected_components=None),
            dm_insight(affected_components=[{"type": "agent", "id": "agent-1"}, {"type": "x", "id": "y"}]),
        ]
        result = await DebugMonitor(db).get_component_health("agent", "agent-1")
        assert len(result["recent_insights"]) == 2

    async def test_exception_returns_error_dict(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        result = await DebugMonitor(db).get_component_health("agent", "agent-1")
        assert result["status"] == "error"
        assert result["health_score"] == 0


class TestDmActiveOperations:
    @pytest.fixture()
    def ops_db(self):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = None
        return db

    async def test_statuses(self, ops_db):
        now = datetime.now(timezone.utc)
        ops_db.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = [
            ("op-1", now, now, 5, 2),                              # errors
            ("op-2", now, datetime.now() - timedelta(minutes=3), 3, 0),  # naive, stalled
            ("op-3", now, now - timedelta(seconds=10), 3, 0),      # active
            ("op-4", now, None, 3, 0),                             # no last activity → stalled
        ]
        result = await DebugMonitor(ops_db).get_active_operations()
        by_id = {r["correlation_id"]: r for r in result}
        assert by_id["op-1"]["status"] == "errors"
        assert by_id["op-1"]["error_count"] == 2
        assert by_id["op-2"]["status"] == "stalled"
        assert by_id["op-3"]["status"] == "active"
        assert by_id["op-4"]["status"] == "stalled"

    async def test_aware_last_activity_stalled(self, ops_db):
        now = datetime.now(timezone.utc)
        ops_db.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = [
            ("op-5", now, now - timedelta(minutes=10), 1, 0),  # aware but stale
        ]
        result = await DebugMonitor(ops_db).get_active_operations()
        assert result[0]["status"] == "stalled"

    async def test_empty(self, ops_db):
        ops_db.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
        assert await DebugMonitor(ops_db).get_active_operations() == []

    async def test_exception_returns_empty(self, ops_db):
        ops_db.query.side_effect = RuntimeError("db down")
        assert await DebugMonitor(ops_db).get_active_operations() == []


class TestDmErrorRates:
    async def test_rates_sorted_and_limited(self):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.group_by.return_value.having.return_value.all.return_value = [
            ("agent", "a1", 10, 2),
            ("agent", "a2", 10, 9),
            ("agent", "a3", 10, 0),
        ]
        result = await DebugMonitor(db).get_error_rate_by_component(limit=2)
        assert result[0]["component_id"] == "a2"  # highest rate first
        assert len(result) == 2
        assert result[0]["error_rate"] == 90.0

    async def test_zero_total_guard(self):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.group_by.return_value.having.return_value.all.return_value = [
            ("agent", "a1", 0, 0),
        ]
        result = await DebugMonitor(db).get_error_rate_by_component()
        assert result[0]["error_rate"] == 0.0

    async def test_exception_returns_empty(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        assert await DebugMonitor(db).get_error_rate_by_component() == []


class TestDmThroughput:
    async def test_metrics(self):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.group_by.return_value.all.return_value = [
            ("agent", 60),
            ("browser", 120),
        ]
        result = await DebugMonitor(db).get_throughput_metrics("last_1h")
        assert result["total_events"] == 180
        assert result["throughput_by_component"]["agent"]["events_per_minute"] == 1.0
        assert result["throughput_by_component"]["browser"]["events_per_minute"] == 2.0
        assert result["events_per_minute"] == 3.0

    async def test_empty(self):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.group_by.return_value.all.return_value = []
        result = await DebugMonitor(db).get_throughput_metrics()
        assert result["total_events"] == 0

    async def test_exception_returns_empty(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        assert await DebugMonitor(db).get_throughput_metrics() == {}


class TestDmInsightSummary:
    async def test_summary(self):
        db = MagicMock()
        q1, q2, q3 = MagicMock(), MagicMock(), MagicMock()
        db.query.side_effect = [q1, q2, q3]
        q1.filter.return_value.group_by.return_value.all.return_value = [
            ("error", "critical", 2),
            ("performance", "info", 1),
        ]
        q2.filter.return_value.scalar.return_value = 1
        q3.filter.return_value.scalar.return_value = 2
        result = await DebugMonitor(db).get_insight_summary()
        assert result["total_count"] == 3
        assert result["by_type"]["error"]["critical"] == 2
        assert result["resolved_count"] == 1
        assert result["unresolved_count"] == 2

    async def test_none_counts_zeroed(self):
        db = MagicMock()
        q1, q2, q3 = MagicMock(), MagicMock(), MagicMock()
        db.query.side_effect = [q1, q2, q3]
        q1.filter.return_value.group_by.return_value.all.return_value = []
        q2.filter.return_value.scalar.return_value = None
        q3.filter.return_value.scalar.return_value = None
        result = await DebugMonitor(db).get_insight_summary()
        assert result["total_count"] == 0
        assert result["resolved_count"] == 0

    async def test_exception_returns_empty(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        assert await DebugMonitor(db).get_insight_summary() == {}


class TestDmBreakdown:
    async def test_breakdown(self):
        db = MagicMock()
        q1 = MagicMock()
        db.query.return_value = q1
        q1.filter.return_value.group_by.return_value.all.return_value = [
            ("agent", 10, 2),
            ("browser", 0, None),
        ]
        result = await DebugMonitor(db)._get_component_breakdown(datetime.now(timezone.utc))
        assert result["agent"]["health_score"] == 80
        assert result["browser"]["health_score"] == 100
        assert result["browser"]["error_events"] == 0

    async def test_exception_returns_empty(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        assert await DebugMonitor(db)._get_component_breakdown(datetime.now(timezone.utc)) == {}


class TestDmTimeRanges:
    def test_parse_time_range(self):
        m = DebugMonitor(MagicMock())
        now = datetime.now(timezone.utc)
        assert (now - m._parse_time_range("last_1h")).total_seconds() == pytest.approx(3600, abs=5)
        assert (now - m._parse_time_range("last_24h")).total_seconds() == pytest.approx(86400, abs=5)
        assert (now - m._parse_time_range("last_7d")).total_seconds() == pytest.approx(604800, abs=5)
        assert (now - m._parse_time_range("bogus")).total_seconds() == pytest.approx(3600, abs=5)

    def test_duration_minutes(self):
        m = DebugMonitor(MagicMock())
        assert m._get_duration_minutes("last_1h") == 60
        assert m._get_duration_minutes("last_24h") == 1440
        assert m._get_duration_minutes("last_7d") == 10080
        assert m._get_duration_minutes("bogus") == 60


# ============================================================================
# 9. debug_insight_engine
# ============================================================================


def die_event(**overrides):
    base = dict(
        id="e-1", event_type="log", component_type="agent", component_id="agent-1",
        correlation_id="corr-1", level="INFO", message="msg", data={},
        timestamp=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def die_snapshot(**overrides):
    base = dict(
        id="s-1", component_type="agent", component_id="node-1", operation_id="op-1",
        state_data={"x": 1}, captured_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def die_db():
    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    db.query.return_value = q
    return db


class TestDieGenerateInsights:
    async def test_no_events_returns_empty(self, die_db):
        die_db.query.return_value.order_by.return_value.all.return_value = []
        engine = DebugInsightEngine(die_db)
        assert await engine.generate_insights_from_events(correlation_id="corr-x") == []

    async def test_full_pipeline(self, die_db):
        base = datetime.now(timezone.utc)
        events = [
            die_event(id="e-snap", event_type="state_snapshot", data={"step": 1}, ts_ignored=1, timestamp=base + timedelta(minutes=5)),
            die_event(id="e-flow", level="ERROR", message="flow broke", timestamp=base + timedelta(minutes=5)),
            die_event(id="e-err1", level="ERROR", message="same failure", timestamp=base + timedelta(minutes=5)),
            die_event(id="e-err2", level="ERROR", message="same failure", timestamp=base + timedelta(minutes=5)),
            die_event(id="e-slow", data={"duration_ms": 9000}, timestamp=base + timedelta(minutes=5)),
        ]
        for i in range(5):
            events.append(die_event(id=f"e-vol-a{i}", timestamp=base + timedelta(minutes=i)))
        for i in range(8):
            events.append(die_event(id=f"e-vol-b{i}", timestamp=base + timedelta(minutes=6)))
        die_db.query.return_value.order_by.return_value.all.return_value = events
        engine = DebugInsightEngine(die_db)
        insights = await engine.generate_insights_from_events()
        kinds = {i.insight_type for i in insights}
        assert kinds == {"consistency", "flow", "error", "performance", "anomaly"}
        die_db.commit.assert_called_once()
        assert die_db.add.call_count == len(insights)

    async def test_confidence_threshold_blocks_persistence(self, die_db):
        die_db.query.return_value.order_by.return_value.all.return_value = [
            die_event(id="e-err1", level="ERROR", message="same failure"),
            die_event(id="e-err2", level="ERROR", message="same failure"),
        ]
        engine = DebugInsightEngine(die_db)
        with patch.object(die_mod, "DEBUG_INSIGHT_CONFIDENCE_THRESHOLD", 1.0):
            insights = await engine.generate_insights_from_events()
        assert len(insights) == 2
        die_db.add.assert_not_called()

    async def test_anomaly_disabled(self, die_db):
        die_db.query.return_value.order_by.return_value.all.return_value = [
            die_event(id="e-err1", level="ERROR", message="same failure"),
            die_event(id="e-err2", level="ERROR", message="same failure"),
        ]
        engine = DebugInsightEngine(die_db)
        with patch.object(die_mod, "DEBUG_ANOMALY_DETECTION_ENABLED", False):
            insights = await engine.generate_insights_from_events()
        assert all(i.insight_type != "anomaly" for i in insights)

    async def test_exception_returns_empty(self, die_db):
        die_db.query.return_value.order_by.return_value.all.return_value = [
            die_event(id="e-err1", level="ERROR", message="same failure"),
            die_event(id="e-err2", level="ERROR", message="same failure"),
        ]
        engine = DebugInsightEngine(die_db)
        with patch.object(engine.db, "commit", side_effect=RuntimeError("db down")):
            assert await engine.generate_insights_from_events() == []


class TestDieStateConsistency:
    async def test_no_snapshots_returns_none(self, die_db):
        die_db.query.return_value.order_by.return_value.all.return_value = []
        engine = DebugInsightEngine(die_db)
        assert await engine.analyze_state_consistency("op-1", ["node-1"]) is None

    async def test_missing_components_warning(self, die_db):
        die_db.query.return_value.order_by.return_value.all.return_value = [die_snapshot(component_id="node-1")]
        engine = DebugInsightEngine(die_db)
        insight = await engine.analyze_state_consistency("op-1", ["node-1", "node-2"])
        assert insight.severity == "warning"
        assert insight.title == "Incomplete state coverage"
        assert insight.affected_components == [{"type": "agent", "id": "node-2"}]
        assert insight.confidence_score == 0.95

    async def test_inconsistent_state(self, die_db):
        die_db.query.return_value.order_by.return_value.all.return_value = [
            die_snapshot(component_id="node-1", state_data={"x": 1}),
            die_snapshot(component_id="node-2", state_data={"x": 2}),
        ]
        engine = DebugInsightEngine(die_db)
        insight = await engine.analyze_state_consistency("op-1", ["node-1", "node-2"])
        assert insight.title == "State inconsistency detected"
        assert insight.severity == "warning"
        assert insight.confidence_score == 0.90
        assert insight.evidence["inconsistencies"][0]["key"] == "x"

    async def test_consistent_state(self, die_db):
        die_db.query.return_value.order_by.return_value.all.return_value = [
            die_snapshot(component_id="node-1", state_data={"x": 1}),
            die_snapshot(component_id="node-2", state_data={"x": 1}),
        ]
        engine = DebugInsightEngine(die_db)
        insight = await engine.analyze_state_consistency("op-1", ["node-1", "node-2"])
        assert insight.title == "State consistent across all components"
        assert insight.severity == "info"
        assert insight.confidence_score == 1.0

    async def test_exception_returns_none(self, die_db):
        die_db.query.side_effect = RuntimeError("db down")
        engine = DebugInsightEngine(die_db)
        assert await engine.analyze_state_consistency("op-1", ["node-1"]) is None


class _BoomEvent:
    """DebugEvent stand-in whose first attribute access for the named field
    raises — drives the except paths of the insight sub-generators."""

    def __init__(self, boom_attr):
        self._boom_attr = boom_attr

    def __getattr__(self, name):
        if name == self._boom_attr:
            raise RuntimeError("boom")
        raise AttributeError(name)


class TestDieSubGenerators:
    async def test_consistency_insights(self, die_db):
        engine = DebugInsightEngine(die_db)
        insights = await engine._generate_consistency_insights([
            die_event(event_type="state_snapshot", data={"x": 1}),
            die_event(event_type="state_snapshot", data=None),
            die_event(event_type="log"),
        ])
        assert len(insights) == 1
        assert insights[0].insight_type == "consistency"
        assert insights[0].confidence_score == 0.85

    async def test_consistency_insights_exception(self, die_db):
        engine = DebugInsightEngine(die_db)
        assert await engine._generate_consistency_insights([_BoomEvent("correlation_id")]) == []

    async def test_flow_insights(self, die_db):
        engine = DebugInsightEngine(die_db)
        insights = await engine._generate_flow_insights([
            die_event(level="ERROR", message="e1"),
            die_event(level="INFO"),
        ])
        assert len(insights) == 1
        assert insights[0].insight_type == "flow"
        assert insights[0].severity == "warning"
        assert insights[0].evidence["error_count"] == 1

    async def test_flow_insights_timestamp_sort(self, die_db):
        engine = DebugInsightEngine(die_db)
        insights = await engine._generate_flow_insights([
            die_event(level="ERROR", timestamp=None),
            die_event(level="ERROR", message="e2"),
        ])
        assert len(insights) == 1

    async def test_flow_insights_exception(self, die_db):
        engine = DebugInsightEngine(die_db)
        assert await engine._generate_flow_insights([_BoomEvent("correlation_id")]) == []

    async def test_error_insights_none(self, die_db):
        engine = DebugInsightEngine(die_db)
        assert await engine._generate_error_insights([die_event(level="INFO")]) == []

    async def test_error_insights_repeated_warning(self, die_db):
        engine = DebugInsightEngine(die_db)
        insights = await engine._generate_error_insights([
            die_event(level="ERROR", message="same failure", timestamp=None),
            die_event(level="ERROR", message="same failure"),
        ])
        assert len(insights) == 1
        assert insights[0].severity == "warning"
        assert insights[0].confidence_score == 0.90
        assert insights[0].evidence["occurrences"] == 2

    async def test_error_insights_repeated_critical(self, die_db):
        engine = DebugInsightEngine(die_db)
        insights = await engine._generate_error_insights([
            die_event(level="ERROR", message="same failure"),
            die_event(level="CRITICAL", message="same failure"),
        ])
        assert insights[0].severity == "critical"

    async def test_error_insights_exception(self, die_db):
        engine = DebugInsightEngine(die_db)
        assert await engine._generate_error_insights([_BoomEvent("level")]) == []

    async def test_performance_insights_exception(self, die_db):
        engine = DebugInsightEngine(die_db)
        assert await engine._generate_performance_insights([_BoomEvent("data")]) == []

    async def test_anomaly_insights_exception(self, die_db):
        engine = DebugInsightEngine(die_db)
        assert await engine._generate_anomaly_insights([_BoomEvent("timestamp")]) == []

    async def test_performance_insights(self, die_db):
        engine = DebugInsightEngine(die_db)
        insights = await engine._generate_performance_insights([
            die_event(data={"duration_ms": 9000}, message="slow op"),
            die_event(data={"duration_ms": 100}, message="fast op"),
            die_event(data={}),
            die_event(data=None),
        ])
        assert len(insights) == 1
        assert insights[0].insight_type == "performance"
        assert insights[0].evidence["slow_operations"][0]["duration_ms"] == 9000

    async def test_performance_insights_none(self, die_db):
        engine = DebugInsightEngine(die_db)
        assert await engine._generate_performance_insights([die_event(data={"duration_ms": 100})]) == []

    async def test_anomaly_insights_spike(self, die_db):
        engine = DebugInsightEngine(die_db)
        base = datetime.now(timezone.utc)
        events = [die_event(timestamp=base + timedelta(minutes=i)) for i in range(5)]
        events += [die_event(timestamp=base + timedelta(minutes=6)) for _ in range(6)]
        insights = await engine._generate_anomaly_insights(events)
        assert len(insights) == 1
        assert insights[0].insight_type == "anomaly"
        assert insights[0].confidence_score == 0.75

    async def test_anomaly_insights_no_spike(self, die_db):
        engine = DebugInsightEngine(die_db)
        base = datetime.now(timezone.utc)
        events = [die_event(timestamp=base + timedelta(minutes=i)) for i in range(3)]
        assert await engine._generate_anomaly_insights(events) == []

    async def test_anomaly_insights_no_timestamps(self, die_db):
        engine = DebugInsightEngine(die_db)
        assert await engine._generate_anomaly_insights([die_event(timestamp=None)]) == []


class TestDieQueryEvents:
    async def test_all_filters(self, die_db):
        die_db.query.return_value.order_by.return_value.all.return_value = [die_event()]
        engine = DebugInsightEngine(die_db)
        result = await engine._query_events(
            correlation_id="c1", component_type="agent", component_id="agent-1", time_range="last_1h"
        )
        assert len(result) == 1

    async def test_unknown_time_range_no_filter(self, die_db):
        die_db.query.return_value.order_by.return_value.all.return_value = [die_event()]
        engine = DebugInsightEngine(die_db)
        result = await engine._query_events(time_range="bogus")
        assert len(result) == 1

    async def test_exception_returns_empty(self, die_db):
        die_db.query.side_effect = RuntimeError("db down")
        engine = DebugInsightEngine(die_db)
        assert await engine._query_events() == []


class TestDieParseTimeRange:
    def test_all_branches(self):
        engine = DebugInsightEngine(MagicMock())
        now = datetime.now(timezone.utc)
        assert (now - engine._parse_time_range("last_1h")).total_seconds() == pytest.approx(3600, abs=5)
        assert (now - engine._parse_time_range("last_24h")).total_seconds() == pytest.approx(86400, abs=5)
        assert (now - engine._parse_time_range("last_7d")).total_seconds() == pytest.approx(604800, abs=5)
        assert (now - engine._parse_time_range("last_30d")).total_seconds() == pytest.approx(2592000, abs=5)
        assert engine._parse_time_range("bogus") is None


# ============================================================================
# 10. workflow_analytics_engine
# ============================================================================


@pytest.fixture(autouse=True)
def _reset_wae_singleton():
    wae_mod._analytics_engine = None
    yield
    wae_mod._analytics_engine = None


@pytest.fixture
def wae(tmp_path):
    engine = WorkflowAnalyticsEngine(db_path=str(tmp_path / "analytics.db"))
    yield engine


def wae_insert_event(db_path, *, event_id, workflow_id="wf", execution_id="ex",
                     event_type="workflow_started", timestamp=None, status=None,
                     duration_ms=None, error_message=None, user_id="u1",
                     workspace_id="default", metadata=None):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """INSERT INTO workflow_events (event_id, workflow_id, execution_id, user_id,
           event_type, timestamp, step_id, step_name, duration_ms, status,
           error_message, metadata, resource_id, workspace_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (event_id, workflow_id, execution_id, user_id, event_type,
         (timestamp or datetime.now()).isoformat(), None, None, duration_ms,
         status, error_message, json.dumps(metadata) if metadata else None,
         None, workspace_id),
    )
    conn.commit()
    conn.close()


def wae_metric(db_path, workflow_id, metric_name, value, timestamp=None, step_name=None):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """INSERT INTO workflow_metrics (workflow_id, metric_name, metric_type, value,
           timestamp, tags, step_id, step_name, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (workflow_id, metric_name, "gauge", str(value),
         (timestamp or datetime.now()).isoformat(), None, None, step_name, "u1"),
    )
    conn.commit()
    conn.close()


class TestWaeInit:
    def test_init_creates_store(self, tmp_path):
        engine = WorkflowAnalyticsEngine(db_path=str(tmp_path / "x.db"))
        assert engine.db_path.exists()
        assert engine.events_buffer.maxlen == 50000
        assert engine.metrics_buffer.maxlen == 10000

    def test_init_with_tenant_and_workspace(self, tmp_path):
        engine = WorkflowAnalyticsEngine(db_path=str(tmp_path / "y.db"), workspace_id="ws-1", tenant_id="t-1")
        assert engine.workspace_id == "ws-1"
        assert engine.tenant_id == "t-1"

    def test_start_background_processing_noop_when_disabled(self, wae):
        assert wae._start_background_processing() is None
        assert wae._background_thread is None

    def test_default_db_path_resolution(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "rel").mkdir()
        engine = WorkflowAnalyticsEngine(db_path="rel/a.db", enable_background_thread=False)
        assert engine.db_path.is_absolute()
        assert engine.db_path == (Path.cwd() / "rel" / "a.db").expanduser().absolute()

    def test_init_starts_background_thread(self, tmp_path):
        captured = {}
        fake_loop = MagicMock()
        fake_loop.create_task.side_effect = lambda coro: captured.setdefault("coro", coro) or MagicMock()
        with patch("core.workflow_analytics_engine.asyncio.new_event_loop", return_value=fake_loop), \
             patch("core.workflow_analytics_engine.asyncio.set_event_loop"), \
             patch("threading.Thread"):
            engine = WorkflowAnalyticsEngine(db_path=str(tmp_path / "bg3.db"), enable_background_thread=True)
        assert engine._background_thread is not None
        assert engine._stop_event is not None
        assert captured["coro"] is not None


class TestWaeTracking:
    def test_track_workflow_start(self, wae):
        wae.track_workflow_start("wf1", "ex1", user_id="u1", workspace_id="ws", tenant_id="t",
                                 metadata={"m": 1})
        assert len(wae.events_buffer) == 1
        assert wae.events_buffer[0].event_type == "workflow_started"
        assert len(wae.metrics_buffer) == 1

    def test_track_workflow_completion_enum_and_metadata(self, wae):
        wae.track_workflow_completion(
            "wf1", "ex1", WorkflowStatus.COMPLETED, 500,
            step_outputs={"a": 1}, user_id="u1", metadata={"extra": 2},
        )
        event = wae.events_buffer[-1]
        assert event.status == "completed"
        assert event.duration_ms == 500
        assert event.metadata == {"step_count": 1, "extra": 2}
        names = {m.metric_name for m in wae.metrics_buffer}
        assert "successful_executions" in names

    def test_track_workflow_completion_str_status_and_failure(self, wae):
        wae.track_workflow_completion(
            "wf1", "ex2", "failed", 100, error_message="boom",
            step_outputs=None, metadata=None,
        )
        event = wae.events_buffer[-1]
        assert event.status == "failed"
        assert event.metadata == {"step_count": 0}
        names = {m.metric_name for m in wae.metrics_buffer}
        assert "failed_executions" in names
        assert "execution_duration_ms" in names

    def test_track_step_execution_with_duration(self, wae):
        wae.track_step_execution("wf1", "ex1", "s1", "Step One", duration_ms=250, status="completed",
                                 error_message=None, resource_id="r1", user_id="u1")
        event = wae.events_buffer[-1]
        assert event.event_type == "step_completed"
        assert event.resource_id == "r1"
        assert any(m.metric_name == "step_duration_ms" for m in wae.metrics_buffer)

    def test_track_step_execution_explicit_event_type(self, wae):
        wae.track_step_execution("wf1", "ex1", "s1", "Step", event_type="step_started")
        assert wae.events_buffer[-1].event_type == "step_started"

    def test_track_step_execution_default_event_type(self, wae):
        wae.track_step_execution("wf1", "ex1", "s1", "Step", status=None)
        assert wae.events_buffer[-1].event_type == "step_executed"

    def test_track_step_execution_no_duration(self, wae):
        wae.track_step_execution("wf1", "ex1", "s1", "Step", status="running")
        assert all(m.metric_name != "step_duration_ms" for m in wae.metrics_buffer)

    def test_track_manual_override_full(self, wae):
        wae.track_manual_override("wf1", "ex1", "r1", action="modify", original_value="a",
                                  new_value="b", reason="user choice", metadata={"m": 1},
                                  user_id="u1", workspace_id="ws", tenant_id="t")
        event = wae.events_buffer[-1]
        assert event.event_type == "manual_override"
        assert event.status == "OVERRIDDEN"
        assert event.metadata["reason"] == "user choice"
        assert event.step_name == "modify"
        assert any(m.metric_name == "manual_override_count" for m in wae.metrics_buffer)

    def test_track_manual_override_minimal(self, wae):
        wae.track_manual_override("wf1", "ex1", "r1")
        event = wae.events_buffer[-1]
        assert event.step_name == "r1"
        assert "reason" not in event.metadata

    def test_track_resource_usage_full(self, wae):
        wae.track_resource_usage("wf1", 50.0, 128.0, step_id="s1", disk_io=1000, network_io=2000)
        names = {m.metric_name for m in wae.metrics_buffer}
        assert names == {"cpu_usage_percent", "memory_usage_mb", "disk_io_bytes", "network_io_bytes"}

    def test_track_resource_usage_minimal(self, wae):
        wae.track_resource_usage("wf1", 50.0, 128.0)
        names = {m.metric_name for m in wae.metrics_buffer}
        assert names == {"cpu_usage_percent", "memory_usage_mb"}

    def test_track_user_activity(self, wae):
        wae.track_user_activity("u1", "login", workflow_id="wf1", metadata={"m": 1})
        assert wae.events_buffer[-1].event_type == "user_activity"
        assert wae.events_buffer[-1].metadata == {"action": "login", "m": 1}

    def test_track_user_activity_system_default(self, wae):
        wae.track_user_activity("u1", "click")
        assert wae.events_buffer[-1].workflow_id == "system"
        assert wae.metrics_buffer[-1].workflow_id == "system"

    def test_track_metric(self, wae):
        wae.track_metric("wf1", "custom", MetricType.GAUGE, 42, tags={"a": "b"}, step_id="s1",
                         step_name="S", user_id="u1", workspace_id="ws", tenant_id="t")
        m = wae.metrics_buffer[-1]
        assert m.metric_name == "custom"
        assert m.metric_type == MetricType.GAUGE


class TestWaePerformanceMetrics:
    def test_no_events(self, wae):
        metrics = wae.get_workflow_performance_metrics("wf-empty")
        assert metrics.total_executions == 0
        assert metrics.error_rate == 0
        assert metrics.most_common_errors == []
        assert metrics.average_duration_ms == 0

    def test_with_events(self, wae):
        for i in range(5):
            wae.track_workflow_start("wf1", f"ex{i}")
        for i in range(4):
            wae.track_workflow_completion("wf1", f"ex{i}", WorkflowStatus.COMPLETED, 100 + i)
        wae.track_workflow_completion("wf1", "ex4", WorkflowStatus.FAILED, 500, error_message="boom")
        wae.track_resource_usage("wf1", 50.0, 300.0)
        wae.track_step_execution("wf1", "ex0", "s1", "Step One", duration_ms=100)
        wae.track_step_execution("wf1", "ex0", "s2", "Step Two", duration_ms=200)
        metrics = wae.get_workflow_performance_metrics("wf1", "24h")
        assert metrics.total_executions == 5
        assert metrics.successful_executions == 4
        assert metrics.failed_executions == 1
        assert metrics.error_rate == 20.0
        assert metrics.most_common_errors[0]["error"] == "boom"
        # engine SQL averages cpu+memory rows together (single AVG over both)
        assert metrics.average_cpu_usage == 175.0
        assert metrics.peak_memory_usage == 300.0
        assert metrics.average_step_duration["Step One"] == 100.0

    def test_p95_p99(self, wae):
        for i in range(5):
            wae.track_workflow_start("wf1", f"ex{i}")
        for i in range(101):
            wae.track_workflow_completion("wf1", f"ex{i % 5}-{i}", WorkflowStatus.COMPLETED, 100 + i)
        metrics = wae.get_workflow_performance_metrics("wf1", "24h")
        assert metrics.p95_duration_ms > 0
        assert metrics.p99_duration_ms > 0

    def test_cache_fresh_hit(self, wae):
        wae.track_workflow_start("wf1", "ex1")
        a = wae.get_workflow_performance_metrics("wf1", "24h")
        b = wae.get_workflow_performance_metrics("wf1", "24h")
        assert a is b

    def test_cache_stale_recomputes(self, wae):
        wae.track_workflow_start("wf1", "ex1")
        a = wae.get_workflow_performance_metrics("wf1", "24h")
        cached = wae.performance_cache["wf1_24h"]
        cached.timestamp = datetime.now() - timedelta(seconds=10000)
        b = wae.get_workflow_performance_metrics("wf1", "24h")
        assert b is not cached

    def test_unknown_window_defaults(self, wae):
        metrics = wae.get_workflow_performance_metrics("wf1", "bogus")
        assert metrics.time_window == "bogus"

    def test_exception_raises(self, wae):
        with patch("core.workflow_analytics_engine.sqlite3.connect", side_effect=RuntimeError("db down")):
            with pytest.raises(RuntimeError):
                wae.get_workflow_performance_metrics("wf1")

    def test_query_error_raises(self, wae):
        """Exception INSIDE the try block (query executes, fetch fails) — hits
        the except/raise path that a connect-time failure bypasses."""
        conn = MagicMock()
        conn.cursor().execute.side_effect = RuntimeError("query boom")
        with patch("core.workflow_analytics_engine.sqlite3.connect", return_value=conn):
            with pytest.raises(RuntimeError):
                wae.get_workflow_performance_metrics("wf1")
        conn.close.assert_called_once()


class TestWaeSystemOverview:
    def test_empty(self, wae):
        result = wae.get_system_overview()
        assert result["total_workflows"] == 0
        assert result["total_executions"] == 0
        assert result["success_rate"] == 0
        assert result["average_execution_time_ms"] == 0

    def test_with_data(self, wae):
        wae_insert_event(wae.db_path, event_id="a1", workflow_id="wf1", event_type="workflow_started")
        wae_insert_event(wae.db_path, event_id="a2", workflow_id="wf1", event_type="workflow_started")
        wae_insert_event(wae.db_path, event_id="a3", workflow_id="wf2", event_type="workflow_started")
        wae_insert_event(wae.db_path, event_id="c1", workflow_id="wf1", event_type="workflow_completed",
                         status="completed", duration_ms=100)
        wae_insert_event(wae.db_path, event_id="c2", workflow_id="wf1", event_type="workflow_completed",
                         status="failed", error_message="boom")
        wae_metric(wae.db_path, "wf1", "workflow_executions", 1)
        wae_metric(wae.db_path, "wf2", "workflow_executions", 1)
        result = wae.get_system_overview("1h")
        assert result["total_workflows"] == 2
        assert result["total_executions"] == 3
        assert result["success_rate"] == 50.0
        assert result["average_execution_time_ms"] == 100
        assert result["top_workflows"][0]["workflow_id"] == "wf1"
        assert result["recent_errors"][0]["error_message"] == "boom"

    def test_exception_raises(self, wae):
        with patch("core.workflow_analytics_engine.sqlite3.connect", side_effect=RuntimeError("db down")):
            with pytest.raises(RuntimeError):
                wae.get_system_overview()

    def test_query_error_raises(self, wae):
        conn = MagicMock()
        conn.cursor().execute.side_effect = RuntimeError("query boom")
        with patch("core.workflow_analytics_engine.sqlite3.connect", return_value=conn):
            with pytest.raises(RuntimeError):
                wae.get_system_overview()
        conn.close.assert_called_once()


class TestWaeAlerts:
    def test_create_alert_kwargs(self, wae):
        alert = wae.create_alert(
            name="High failure", description="d", severity=AlertSeverity.HIGH,
            condition="x > 5", threshold_value=5.0, metric_name="failure_rate",
            workflow_id="wf1", step_id="s1", notification_channels=["slack"],
        )
        assert alert.alert_id in wae.active_alerts
        alerts = wae.get_all_alerts()
        assert alerts[0].name == "High failure"
        assert alerts[0].severity == AlertSeverity.HIGH

    def test_create_alert_object_style(self, wae):
        alert = Alert(
            alert_id="custom-1", name="N", description="d", severity=AlertSeverity.LOW,
            condition="c", threshold_value=1, metric_name="m",
        )
        result = wae.create_alert(alert)
        assert result is alert
        assert alert.alert_id in wae.active_alerts

    def test_create_alert_alert_kwarg(self, wae):
        alert = Alert(
            alert_id="custom-2", name="N", description="d", severity=AlertSeverity.MEDIUM,
            condition="c", threshold_value=None, metric_name="m", enabled=False,
        )
        wae.create_alert(alert=alert)
        assert alert.alert_id in wae.active_alerts
        stored = wae.get_all_alerts()
        assert stored[0].enabled is False
        assert stored[0].threshold_value is None

    def test_create_alert_condition_dict(self, wae):
        wae.create_alert(name="N", description="d", severity=AlertSeverity.LOW,
                         condition={"a": 1}, threshold_value=2, metric_name="m")
        assert wae.get_all_alerts()[0].condition == '{"a": 1}'

    def test_create_alert_from_object_exception(self, wae):
        alert = Alert(alert_id="x", name="N", description="d", severity=AlertSeverity.LOW,
                      condition="c", threshold_value=1, metric_name="m")
        with patch("core.workflow_analytics_engine.sqlite3.connect", side_effect=RuntimeError("db down")):
            with pytest.raises(RuntimeError):
                wae._create_alert_from_object(alert)

    def test_check_alerts_triggers_and_resolves(self, wae):
        wae.create_alert(name="Threshold", description="d", severity=AlertSeverity.HIGH,
                         condition="v > 5", threshold_value=5.0, metric_name="x_rate")
        wae.track_metric("wf1", "x_rate", MetricType.COUNTER, 3)
        wae.check_alerts()
        alert = list(wae.active_alerts.values())[0]
        assert alert.triggered_at is None  # below threshold → resolve is a no-op
        wae.track_metric("wf1", "x_rate", MetricType.COUNTER, 10)
        wae.check_alerts()
        assert alert.triggered_at is not None
        wae.check_alerts()  # already triggered → no-op
        assert alert.resolved_at is None
        wae.track_metric("wf1", "x_rate", MetricType.COUNTER, 1)
        wae.check_alerts()
        assert alert.resolved_at is not None
        wae.check_alerts()  # already resolved → no-op

    def test_check_alerts_alert_not_in_active(self, wae):
        alert = wae.create_alert(name="T", description="d", severity=AlertSeverity.LOW,
                                 condition="v > 5", threshold_value=5.0, metric_name="x_rate")
        del wae.active_alerts[alert.alert_id]
        wae.track_metric("wf1", "x_rate", MetricType.COUNTER, 10)
        wae.check_alerts()
        wae.check_alerts()  # _resolve_alert early-return path

    def test_check_alerts_inner_error_skipped(self, wae):
        conn = sqlite3.connect(str(wae.db_path))
        conn.execute(
            """INSERT INTO analytics_alerts (alert_id, name, description, severity, condition,
               threshold_value, metric_name, workflow_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("bad-1", "Bad", "d", "low", "c", "not-a-number", "m", None),
        )
        conn.commit()
        conn.close()
        wae.check_alerts()  # float() raises → inner except, no crash

    def test_check_alerts_outer_error_logged(self, wae):
        with patch("core.workflow_analytics_engine.sqlite3.connect", side_effect=RuntimeError("db down")):
            wae.check_alerts()  # no raise

    def test_update_alert_enabled_and_threshold(self, wae):
        alert = wae.create_alert(name="T", description="d", severity=AlertSeverity.LOW,
                                 condition="v > 5", threshold_value=5.0, metric_name="m")
        wae.update_alert(alert.alert_id, enabled=False, threshold_value=9.5)
        assert alert.enabled is False
        assert alert.threshold_value == 9.5
        stored = wae.get_all_alerts(enabled_only=False)
        assert stored[0].enabled is False

    def test_update_alert_threshold_only(self, wae):
        alert = wae.create_alert(name="T", description="d", severity=AlertSeverity.LOW,
                                 condition="v > 5", threshold_value=5.0, metric_name="m")
        wae.update_alert(alert.alert_id, threshold_value=7.0)
        assert alert.threshold_value == 7.0

    def test_update_alert_no_fields_noop(self, wae):
        alert = wae.create_alert(name="T", description="d", severity=AlertSeverity.LOW,
                                 condition="v > 5", threshold_value=5.0, metric_name="m")
        wae.update_alert(alert.alert_id)
        stored = wae.get_all_alerts()
        assert stored[0].threshold_value == 5.0

    def test_update_alert_not_in_memory(self, wae):
        alert = wae.create_alert(name="T", description="d", severity=AlertSeverity.LOW,
                                 condition="v > 5", threshold_value=5.0, metric_name="m")
        del wae.active_alerts[alert.alert_id]
        wae.update_alert(alert.alert_id, enabled=False)
        stored = wae.get_all_alerts()
        assert stored[0].enabled is False

    def test_update_alert_exception_raises(self, wae):
        alert = wae.create_alert(name="T", description="d", severity=AlertSeverity.LOW,
                                 condition="v > 5", threshold_value=5.0, metric_name="m")
        with patch("core.workflow_analytics_engine.sqlite3.connect", side_effect=RuntimeError("db down")):
            with pytest.raises(RuntimeError):
                wae.update_alert(alert.alert_id, enabled=True)

    def test_delete_alert(self, wae):
        alert = wae.create_alert(name="T", description="d", severity=AlertSeverity.LOW,
                                 condition="v > 5", threshold_value=5.0, metric_name="m")
        wae.delete_alert(alert.alert_id)
        assert alert.alert_id not in wae.active_alerts
        assert wae.get_all_alerts() == []

    def test_delete_alert_exception_raises(self, wae):
        with patch("core.workflow_analytics_engine.sqlite3.connect", side_effect=RuntimeError("db down")):
            with pytest.raises(RuntimeError):
                wae.delete_alert("nope")

    def test_resolve_alert_early_return(self, wae):
        wae._resolve_alert("not-in-active")  # early return, no DB touch

    def test_get_all_alerts_filters(self, wae):
        a1 = wae.create_alert(name="N1", description="d", severity=AlertSeverity.LOW,
                              condition="c", threshold_value=1, metric_name="m", workflow_id="wf1")
        a2 = wae.create_alert(name="N2", description="d", severity=AlertSeverity.LOW,
                              condition="c", threshold_value=1, metric_name="m")
        wae.update_alert(a2.alert_id, enabled=False)
        assert [x.alert_id for x in wae.get_all_alerts(workflow_id="wf1")] == [a1.alert_id]
        assert [x.alert_id for x in wae.get_all_alerts(enabled_only=True)] == [a1.alert_id]
        assert [x.alert_id for x in wae.get_all_alerts(workflow_id="wf1", enabled_only=True)] == [a1.alert_id]
        assert wae.get_all_alerts(workflow_id="other") == []
        assert len(wae.get_all_alerts()) == 2

    def test_get_all_alerts_exception(self, wae):
        with patch("core.workflow_analytics_engine.sqlite3.connect", side_effect=RuntimeError("db down")):
            assert wae.get_all_alerts() == []

    def test_create_alert_from_object_mid_error(self, wae):
        alert = Alert(alert_id="x", name="N", description="d", severity=AlertSeverity.LOW,
                      condition="c", threshold_value=1, metric_name="m")
        conn = MagicMock()
        conn.cursor().execute.side_effect = RuntimeError("insert boom")
        with patch("core.workflow_analytics_engine.sqlite3.connect", return_value=conn):
            with pytest.raises(RuntimeError):
                wae._create_alert_from_object(alert)
        conn.rollback.assert_called_once()

    def test_update_alert_mid_error(self, wae):
        alert = wae.create_alert(name="T", description="d", severity=AlertSeverity.LOW,
                                 condition="c", threshold_value=5.0, metric_name="m")
        conn = MagicMock()
        conn.cursor().execute.side_effect = RuntimeError("update boom")
        with patch("core.workflow_analytics_engine.sqlite3.connect", return_value=conn):
            with pytest.raises(RuntimeError):
                wae.update_alert(alert.alert_id, enabled=True)
        conn.rollback.assert_called_once()

    def test_delete_alert_mid_error(self, wae):
        conn = MagicMock()
        conn.cursor().execute.side_effect = RuntimeError("delete boom")
        with patch("core.workflow_analytics_engine.sqlite3.connect", return_value=conn):
            with pytest.raises(RuntimeError):
                wae.delete_alert("nope")
        conn.rollback.assert_called_once()


class TestWaeReadPaths:
    def test_get_performance_metrics_star(self, wae):
        wae.track_workflow_start("wf1", "ex1")
        wae.track_workflow_completion("wf1", "ex1", WorkflowStatus.COMPLETED, 100)
        metrics = wae.get_performance_metrics("*", "24h")
        assert metrics.workflow_id == "*"
        assert metrics.total_executions == 1

    def test_get_performance_metrics_specific(self, wae):
        wae.track_workflow_start("wf1", "ex1")
        metrics = wae.get_performance_metrics("wf1", "24h")
        assert metrics.workflow_id == "wf1"

    def test_all_workflows_metrics_empty(self, wae):
        metrics = wae._get_all_workflows_metrics("24h")
        assert metrics.total_executions == 0
        assert metrics.unique_users == 0

    def test_all_workflows_metrics_with_data(self, wae):
        for i in range(3):
            wae.track_workflow_start(f"wf{i}", f"ex{i}", user_id=f"u{i}")
        for i in range(2):
            wae.track_workflow_completion(f"wf{i}", f"ex{i}", WorkflowStatus.COMPLETED, 100, user_id=f"u{i}")
        metrics = wae._get_all_workflows_metrics("24h")
        assert metrics.total_executions == 3
        assert metrics.successful_executions == 2
        assert metrics.unique_users == 3

    def test_all_workflows_metrics_p95(self, wae):
        for i in range(5):
            wae.track_workflow_start(f"wf{i}", f"ex{i}")
        for i in range(101):
            wae.track_workflow_completion("wf0", f"ex{i}", WorkflowStatus.COMPLETED, 100 + i)
        metrics = wae._get_all_workflows_metrics("24h")
        assert metrics.p95_duration_ms > 0
        assert metrics.p99_duration_ms > 0

    def test_all_workflows_metrics_exception(self, wae):
        with patch("core.workflow_analytics_engine.sqlite3.connect", side_effect=RuntimeError("db down")):
            with pytest.raises(RuntimeError):
                wae._get_all_workflows_metrics("24h")

    def test_all_workflows_metrics_query_error(self, wae):
        conn = MagicMock()
        conn.cursor().execute.side_effect = RuntimeError("query boom")
        with patch("core.workflow_analytics_engine.sqlite3.connect", return_value=conn):
            with pytest.raises(RuntimeError):
                wae._get_all_workflows_metrics("24h")
        conn.close.assert_called_once()

    def test_all_workflows_metrics_with_errors(self, wae):
        wae.track_workflow_start("wf1", "ex1")
        wae.track_workflow_completion("wf1", "ex1", WorkflowStatus.FAILED, 100, error_message="boom")
        wae.track_workflow_completion("wf1", "ex1-2", WorkflowStatus.FAILED, 100, error_message="boom")
        metrics = wae._get_all_workflows_metrics("24h")
        assert metrics.failed_executions == 2
        assert metrics.most_common_errors == [{"error": "boom", "count": 2, "percentage": 100.0}]

    def test_unique_workflow_count(self, wae):
        assert wae.get_unique_workflow_count() == 0
        wae.track_workflow_start("wf1", "ex1")
        wae.track_workflow_start("wf2", "ex2")
        assert wae.get_unique_workflow_count("1h") == 2

    def test_get_workflow_name(self, wae):
        assert wae.get_workflow_name("wf1") == "wf1"

    def test_get_all_workflow_ids(self, wae):
        assert wae.get_all_workflow_ids() == []
        wae.track_workflow_start("wf1", "ex1")
        wae.track_workflow_start("wf2", "ex2")
        assert wae.get_all_workflow_ids("1h") == ["wf1", "wf2"]

    def test_get_last_execution_time(self, wae):
        assert wae.get_last_execution_time("wf1") is None
        wae.track_workflow_start("wf1", "ex1")
        assert wae.get_last_execution_time("wf1") is not None

    def test_execution_timeline_specific(self, wae):
        now = datetime.now()
        wae_insert_event(wae.db_path, event_id="s1", workflow_id="wf1",
                         event_type="workflow_started", timestamp=now - timedelta(minutes=50))
        wae_insert_event(wae.db_path, event_id="c1", workflow_id="wf1",
                         event_type="workflow_completed", status="completed",
                         duration_ms=100, timestamp=now - timedelta(minutes=50))
        wae_insert_event(wae.db_path, event_id="s2", workflow_id="wf1",
                         event_type="workflow_started", timestamp=now - timedelta(minutes=10))
        wae_insert_event(wae.db_path, event_id="c2", workflow_id="wf1",
                         event_type="workflow_completed", status="failed",
                         duration_ms=200, timestamp=now - timedelta(minutes=10))
        wae_insert_event(wae.db_path, event_id="s3", workflow_id="wf2",
                         event_type="workflow_started", timestamp=now - timedelta(minutes=10))
        timeline = wae.get_execution_timeline("wf1", time_window="1h", interval="15m")
        buckets = {b["timestamp"]: b for b in timeline}
        start = now - timedelta(hours=1)
        first = min(buckets, key=lambda t: t)
        # Buckets start at the engine's own now (computed at call time, a few
        # ms after the test's `now`) — compare approximately, not exactly.
        assert abs((first - start).total_seconds()) < 30
        assert buckets[first]["count"] == 1
        assert buckets[first]["success_count"] == 1
        assert buckets[first]["average_duration_ms"] == 100
        # events at now-10m fall in the bucket containing that instant
        target = now - timedelta(minutes=10)
        third = next(
            b for b in buckets.values()
            if b["timestamp"] <= target < b["timestamp"] + timedelta(minutes=15)
        )
        assert third["count"] == 1
        assert third["failure_count"] == 1
        assert third["average_duration_ms"] == 200

    def test_execution_timeline_star(self, wae):
        now = datetime.now()
        wae_insert_event(wae.db_path, event_id="s1", workflow_id="wf1",
                         event_type="workflow_started", timestamp=now - timedelta(minutes=10))
        wae_insert_event(wae.db_path, event_id="s2", workflow_id="wf2",
                         event_type="workflow_started", timestamp=now - timedelta(minutes=10))
        timeline = wae.get_execution_timeline("*", time_window="1h", interval="1h")
        assert sum(b["count"] for b in timeline) == 2

    def test_execution_timeline_default_interval(self, wae):
        timeline = wae.get_execution_timeline("wf1", time_window="1h", interval="bogus")
        assert len(timeline) > 0
        assert all(b["count"] == 0 for b in timeline)

    def test_execution_timeline_exception_returns_empty(self, wae):
        conn = MagicMock()
        conn.cursor().execute.side_effect = RuntimeError("query boom")
        with patch("core.workflow_analytics_engine.sqlite3.connect", return_value=conn):
            assert wae.get_execution_timeline("wf1") == []

    def test_error_breakdown_star(self, wae):
        now = datetime.now()
        wae_insert_event(wae.db_path, event_id="f1", workflow_id="wf1", event_type="workflow_completed",
                         status="failed", error_message="boom", timestamp=now)
        wae_insert_event(wae.db_path, event_id="f2", workflow_id="wf2", event_type="workflow_completed",
                         status="failed", error_message="boom", timestamp=now)
        wae_insert_event(wae.db_path, event_id="f3", workflow_id="wf1", event_type="workflow_completed",
                         status="failed", error_message="", timestamp=now)
        result = wae.get_error_breakdown("*", "24h")
        assert result["workflows_with_errors"][0]["workflow_id"] == "wf1"
        assert result["error_types"][0]["type"] == "boom"
        assert any(t["type"] == "Unknown" for t in result["error_types"])
        assert len(result["recent_errors"]) == 3

    def test_error_breakdown_specific(self, wae):
        now = datetime.now()
        wae_insert_event(wae.db_path, event_id="f1", workflow_id="wf1", event_type="workflow_completed",
                         status="failed", error_message="boom boom boom", timestamp=now)
        result = wae.get_error_breakdown("wf1", "24h")
        assert result["workflow_id"] == "wf1"
        assert result["error_types"][0]["count"] == 1
        assert result["recent_errors"][0]["step_name"] is None

    def test_error_breakdown_exception_returns_empty(self, wae):
        with patch("core.workflow_analytics_engine.sqlite3.connect", side_effect=RuntimeError("db down")):
            assert wae.get_error_breakdown("wf1") == {}

    def test_get_recent_events_all(self, wae):
        wae.track_workflow_start("wf1", "ex1", metadata={"m": 1})
        wae.track_workflow_completion("wf1", "ex1", WorkflowStatus.COMPLETED, 100)
        events = wae.get_recent_events(limit=10)
        assert len(events) == 2
        assert events[1].metadata == {"m": 1}  # start event (older)
        assert events[0].timestamp is not None

    def test_get_recent_events_workflow_filter(self, wae):
        wae.track_workflow_start("wf1", "ex1")
        wae.track_workflow_start("wf2", "ex2")
        events = wae.get_recent_events(limit=10, workflow_id="wf1")
        assert len(events) == 1
        assert events[0].workflow_id == "wf1"

    def test_get_recent_events_exception_returns_empty(self, wae):
        with patch("core.workflow_analytics_engine.sqlite3.connect", side_effect=RuntimeError("db down")):
            assert wae.get_recent_events() == []


class TestWaePersistence:
    def test_write_through_and_persist_no_clear(self, wae):
        wae.track_workflow_start("wf1", "ex1")
        assert len(wae.events_buffer) == 1  # write-through keeps buffers
        wae._persist_buffers_sync(clear=False)
        assert len(wae.events_buffer) == 1
        assert len(wae.metrics_buffer) == 1
        assert len(wae.get_recent_events()) == 1

    def test_flush_drains_buffers(self, wae):
        wae.track_workflow_start("wf1", "ex1")
        wae._flush_buffers_sync()
        assert len(wae.events_buffer) == 0
        assert len(wae.metrics_buffer) == 0

    def test_write_through_no_duplicate_rows(self, wae):
        """Regression: write-through on every track_* call used to re-persist
        the FULL buffer, duplicating every previously-written metric row on
        each call (O(n^2) growth, inflated aggregations)."""
        for i in range(3):
            wae.track_workflow_start("wf1", f"ex{i}")
        wae.track_resource_usage("wf1", 50.0, 300.0)
        wae.track_step_execution("wf1", "ex0", "s1", "Step One", duration_ms=100)
        conn = sqlite3.connect(str(wae.db_path))
        counts = dict(conn.execute(
            "SELECT metric_name, COUNT(*) FROM workflow_metrics GROUP BY metric_name"
        ).fetchall())
        conn.close()
        assert counts["workflow_executions"] == 3
        assert counts["cpu_usage_percent"] == 1
        assert counts["memory_usage_mb"] == 1
        assert counts["step_duration_ms"] == 1
        assert len(wae.get_recent_events()) == 4  # 3 starts + 1 step, no dup events

    def test_write_through_retries_failed_batch(self, wae):
        wae.track_workflow_start("wf1", "ex1")
        with patch("core.workflow_analytics_engine.sqlite3.connect", side_effect=RuntimeError("db down")):
            wae._persist_buffers_sync(clear=False)
        wae._persist_buffers_sync(clear=False)
        conn = sqlite3.connect(str(wae.db_path))
        n = conn.execute("SELECT COUNT(*) FROM workflow_metrics").fetchone()[0]
        conn.close()
        assert n == 1  # failed write retried, not dropped, no duplicate

    def test_write_through_retries_failed_track(self, wae):
        """A failed write-through during track_* must not advance the
        persisted-prefix index — the row is retried (not dropped) on the
        next call."""
        with patch("core.workflow_analytics_engine.sqlite3.connect", side_effect=RuntimeError("db down")):
            wae.track_workflow_start("wf1", "ex1")
        wae._persist_buffers_sync(clear=False)
        conn = sqlite3.connect(str(wae.db_path))
        n = conn.execute("SELECT COUNT(*) FROM workflow_metrics").fetchone()[0]
        conn.close()
        assert n == 1

    async def test_flush_async(self, wae):
        wae.track_workflow_start("wf1", "ex1")
        await wae.flush()
        assert len(wae.events_buffer) == 0

    async def test_process_metrics_batch_wrapper(self, wae):
        metric = WaeWorkflowMetric(
            workflow_id="wf1", metric_name="m", metric_type=MetricType.COUNTER,
            value=1, timestamp=datetime.now(), tags={"a": "b"}, step_id="s1",
            step_name="S", user_id="u1", workspace_id="ws", tenant_id="t",
        )
        await wae._process_metrics_batch([metric])
        assert wae.get_unique_workflow_count("1h") == 0  # metrics not events

    async def test_process_events_batch_wrapper(self, wae):
        event = WorkflowExecutionEvent(
            event_id="ev-1", workflow_id="wf1", execution_id="ex1",
            event_type="workflow_started", timestamp=datetime.now(),
            metadata={"k": "v"}, user_id="u1", workspace_id="ws", tenant_id="t",
        )
        await wae._process_events_batch([event])
        events = wae.get_recent_events()
        assert events[0].event_id == "ev-1"
        assert events[0].metadata == {"k": "v"}

    def test_persist_metrics_batch_error(self, wae):
        metric = WaeWorkflowMetric(workflow_id="wf1", metric_name="m",
                                   metric_type=MetricType.COUNTER, value=1,
                                   timestamp=datetime.now())
        with patch("core.workflow_analytics_engine.sqlite3.connect", side_effect=RuntimeError("db down")):
            assert wae._persist_metrics_batch([metric]) is False  # logs, no raise

    def test_persist_metrics_batch_mid_function_error(self, wae):
        metric = WaeWorkflowMetric(workflow_id="wf1", metric_name="m",
                                   metric_type=MetricType.COUNTER, value=1,
                                   timestamp=datetime.now())
        conn = MagicMock()
        conn.cursor().execute.side_effect = RuntimeError("insert boom")
        with patch("core.workflow_analytics_engine.sqlite3.connect", return_value=conn):
            assert wae._persist_metrics_batch([metric]) is False
        conn.rollback.assert_called_once()

    def test_persist_events_batch_error(self, wae):
        event = WorkflowExecutionEvent(event_id="ev-1", workflow_id="wf1", execution_id="ex1",
                                       event_type="workflow_started", timestamp=datetime.now())
        with patch("core.workflow_analytics_engine.sqlite3.connect", side_effect=RuntimeError("db down")):
            assert wae._persist_events_batch([event]) is False  # logs, no raise

    def test_persist_events_batch_mid_function_error(self, wae):
        event = WorkflowExecutionEvent(event_id="ev-1", workflow_id="wf1", execution_id="ex1",
                                       event_type="workflow_started", timestamp=datetime.now())
        conn = MagicMock()
        conn.cursor().execute.side_effect = RuntimeError("insert boom")
        with patch("core.workflow_analytics_engine.sqlite3.connect", return_value=conn):
            assert wae._persist_events_batch([event]) is False
        conn.rollback.assert_called_once()

    async def test_cleanup_old_data(self, wae):
        old = datetime.now() - timedelta(days=100)
        wae_insert_event(wae.db_path, event_id="old1", event_type="workflow_started", timestamp=old)
        wae_insert_event(wae.db_path, event_id="new1", event_type="workflow_started")
        await wae._cleanup_old_data()
        assert len(wae.get_recent_events(limit=100)) == 1

    async def test_cleanup_old_data_error(self, wae):
        with patch("core.workflow_analytics_engine.sqlite3.connect", side_effect=RuntimeError("db down")):
            await wae._cleanup_old_data()  # logs, no raise

    async def test_cleanup_old_data_mid_error(self, wae):
        conn = MagicMock()
        conn.cursor().execute.side_effect = RuntimeError("delete boom")
        with patch("core.workflow_analytics_engine.sqlite3.connect", return_value=conn):
            await wae._cleanup_old_data()  # logs, no raise
        conn.rollback.assert_called_once()

    async def test_background_processing_loop(self, tmp_path):
        engine = WorkflowAnalyticsEngine(db_path=str(tmp_path / "bg.db"))
        engine.enable_background_thread = True
        captured = {}
        fake_loop = MagicMock()
        fake_loop.create_task.side_effect = lambda coro: captured.setdefault("coro", coro) or MagicMock()
        with patch("core.workflow_analytics_engine.asyncio.new_event_loop", return_value=fake_loop), \
             patch("core.workflow_analytics_engine.asyncio.set_event_loop"), \
             patch("threading.Thread") as thread_cls:
            engine._start_background_processing()
        assert engine._background_thread is thread_cls.return_value
        assert engine._stop_event is not None

        engine.track_workflow_start("wf1", "ex1")
        engine.track_metric("wf1", "m", MetricType.COUNTER, 1)
        sleep_mock = AsyncMock(side_effect=RuntimeError("stop loop"))
        with patch("core.workflow_analytics_engine.asyncio.sleep", sleep_mock):
            with pytest.raises(RuntimeError):
                await captured["coro"]
        assert len(engine.events_buffer) == 0
        assert len(engine.metrics_buffer) == 0
        assert len(engine.get_recent_events()) == 1

    async def test_background_processing_error_branch(self, tmp_path):
        engine = WorkflowAnalyticsEngine(db_path=str(tmp_path / "bg2.db"))
        engine.enable_background_thread = True
        captured = {}
        fake_loop = MagicMock()
        fake_loop.create_task.side_effect = lambda coro: captured.setdefault("coro", coro) or MagicMock()
        with patch("core.workflow_analytics_engine.asyncio.new_event_loop", return_value=fake_loop), \
             patch("core.workflow_analytics_engine.asyncio.set_event_loop"), \
             patch("threading.Thread"):
            engine._start_background_processing()

        engine.track_workflow_start("wf1", "ex1")
        sleep_mock = AsyncMock(side_effect=RuntimeError("stop loop"))
        with patch("core.workflow_analytics_engine.asyncio.sleep", sleep_mock), \
             patch.object(engine, "check_alerts", side_effect=RuntimeError("alerts boom")):
            with pytest.raises(RuntimeError):
                await captured["coro"]
        assert len(engine.events_buffer) == 0
        assert len(engine.metrics_buffer) == 0


class TestWaeSingleton:
    def test_get_analytics_engine(self):
        fake = MagicMock()
        with patch("core.workflow_analytics_engine.WorkflowAnalyticsEngine", return_value=fake):
            a = wae_get_engine()
            b = wae_get_engine()
        assert a is fake
        assert b is fake

