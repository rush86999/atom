# -*- coding: utf-8 -*-
"""
Coverage-push tests for the "messaging trio":
    - integrations/atom_teams_integration.py
    - integrations/google_chat_enhanced_service.py
    - integrations/atom_whatsapp_integration.py

TDD targets (RED first):
  T1 (HIGH)   atom_teams_integration.get_unified_channels reads
              channel.workspaceName (no such attribute — TeamsChannel has
              workspace_id) -> AttributeError on every channel -> the method
              always returns [] via the swallow-all except.
  T2 (MED)    atom_teams_integration leaks str(e) into send_unified_message /
              create_unified_workflow / get_unified_analytics error dicts.
  T3 (MED)    atom_teams_integration.get_unified_messages crashes the whole
              listing (returns []) when a message has a None timestamp
              (sort key hits TypeError).
  G1 (HIGH)   google_chat_enhanced_service.get_space_messages caches results
              with json.dumps(asdict(...)) — created_at is a datetime, so
              json.dumps raises TypeError and the successful call collapses
              to [] whenever a redis client is configured.
  G2 (MED)    _save_user_space with neither db nor redis raises AttributeError
              and always returns False (no in-memory fallback).
  G3 (MED)    google_chat leaks str(e) into 5 error dicts.
  W1 (MED)    atom_whatsapp_integration.initialize() ignores
              _verify_api_connection() failure — a 401 from the Graph API
              still yields is_initialized=True.
  W2 (MED)    atom_whatsapp_integration leaks str(e) in
              send_intelligent_message / get_service_status error dicts.
"""

from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import asdict
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import integrations.atom_teams_integration as tmi
import integrations.google_chat_enhanced_service as gces
import integrations.atom_whatsapp_integration as wai

from integrations.teams_enhanced_service import (
    TeamsChannel,
    TeamsEventType,
    TeamsMessage,
    TeamsWorkspace,
)
from integrations.google_chat_enhanced_service import (
    GoogleChatConnectionStatus,
    GoogleChatEventType,
    GoogleChatFile,
    GoogleChatMessage,
    GoogleChatRateLimiter,
    GoogleChatSpace,
)


@pytest.fixture(scope="session", autouse=True)
def _close_whatsapp_global():
    yield
    inst = wai.atom_whatsapp_integration
    if inst is not None and getattr(inst, "http_session", None) is not None:
        try:
            asyncio.run(inst.http_session.aclose())
        except Exception:
            pass


def _workspace(team_id="team_1", is_active=True, last_sync=None):
    return TeamsWorkspace(
        team_id=team_id,
        name="Engineering",
        description="Eng team",
        display_name="Engineering",
        visibility="private",
        mail_nickname="eng",
        created_at=datetime.now(timezone.utc),
        created_by="u1",
        tenant_id="tenant_1",
        web_url="https://teams.example",
        last_sync=last_sync,
        is_active=is_active,
        member_count=12,
        channel_count=3,
    )


def _channel(channel_id="channel_1", channel_type="standard", workspace_id="team_1"):
    return TeamsChannel(
        channel_id=channel_id,
        name="General",
        display_name="General",
        description="All hands",
        workspace_id=workspace_id,
        channel_type=channel_type,
        email="general@example.com",
        web_url="https://teams.example/c",
        last_activity_at=datetime.now(timezone.utc),
        member_count=12,
        message_count=40,
        is_archived=False,
        allow_cross_team_posts=True,
        is_favorite_by_default=True,
    )


def _message(message_id="msg_1", text="hello world", timestamp="2026-08-01T10:00:00Z",
             thread_id=None, user_name="Alice", importance="normal"):
    return TeamsMessage(
        message_id=message_id,
        text=text,
        user_id="user_1",
        user_name=user_name,
        user_email="alice@example.com",
        channel_id="channel_1",
        workspace_id="team_1",
        tenant_id="tenant_1",
        timestamp=timestamp,
        html="<p>hello</p>",
        thread_id=thread_id,
        reply_to_id=None,
        message_type="message",
        importance=importance,
        subject="subj",
        is_edited=True,
        edit_timestamp="2026-08-01T10:05:00Z",
        reactions=[{"type": "like"}],
        attachments=[{"id": "a1"}],
        mentions=[{"id": "u2", "displayName": "Bob", "userPrincipalName": "b@x.com"}],
        files=[{"id": "f1", "name": "f.txt", "webUrl": "https://f", "size": 10}],
        etag="etag1",
        channel_identity={"displayName": "General"},
        participant_count=3,
    )


def _make_teams_integration(monkeypatch, **config):
    monkeypatch.setattr(tmi, "teams_enhanced_service", MagicMock())
    monkeypatch.setattr(tmi, "teams_analytics_engine", MagicMock())
    return tmi.AtomTeamsIntegration({
        "atom_memory_service": AsyncMock(),
        "atom_search_service": AsyncMock(),
        "atom_workflow_service": AsyncMock(),
        "atom_ingestion_pipeline": AsyncMock(),
        **config,
    })


# ---------------------------------------------------------------------------
# atom_teams_integration
# ---------------------------------------------------------------------------

class TestTeamsUnifiedWorkspaces:
    async def test_get_unified_workspaces_success(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.teams_service.get_workspaces = AsyncMock(return_value=[
            _workspace("team_1", last_sync=datetime(2026, 8, 1, tzinfo=timezone.utc)),
            _workspace("team_2", is_active=False, last_sync=None),
        ])
        result = await integ.get_unified_workspaces("user_1")
        assert len(result) == 2
        assert result[0]["id"] == "teams_team_1"
        assert result[0]["platform"] == "Microsoft Teams"
        assert result[0]["status"] == "connected"
        assert result[1]["status"] == "disconnected"
        assert result[0]["integration_data"]["last_sync"] is not None
        assert result[1]["integration_data"]["last_sync"] is None
        assert len(integ.active_workspaces) == 2
        integ.teams_service.get_workspaces.assert_awaited_once_with("user_1")

    async def test_get_unified_workspaces_error_returns_empty(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.teams_service.get_workspaces = AsyncMock(side_effect=RuntimeError("boom"))
        assert await integ.get_unified_workspaces("u") == []


class TestTeamsUnifiedChannels:
    async def test_get_unified_channels_success(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.teams_service.get_channels = AsyncMock(return_value=[
            _channel("channel_1", workspace_id="team_1"),
            _channel("channel_2", channel_type="private", workspace_id="team_1"),
        ])
        result = await integ.get_unified_channels("teams_team_1", "user_1")
        # T1: workspaceName AttributeError used to turn every successful call
        # into an empty list. workspace_name must come from workspace_id.
        assert len(result) == 2
        assert result[0]["id"] == "teams_channel_1"
        assert result[0]["workspace_id"] == "teams_team_1"
        assert result[0]["workspace_name"] == "team_1"
        assert result[0]["is_private"] is False
        assert result[1]["is_private"] is True
        assert result[0]["status"] == "active"
        assert result[0]["last_activity"] is not None
        integ.teams_service.get_channels.assert_awaited_once_with(
            "team_1", "user_1", include_private=True, include_archived=False
        )

    async def test_get_unified_channels_non_teams_workspace(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        assert await integ.get_unified_channels("slack_team_1", "u") == []

    async def test_get_unified_channels_error_returns_empty(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.teams_service.get_channels = AsyncMock(side_effect=RuntimeError("boom"))
        assert await integ.get_unified_channels("teams_team_1", "u") == []


class TestTeamsSendUnifiedMessage:
    async def test_send_success_stores_and_indexes(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.teams_service.send_message = AsyncMock(return_value={
            "ok": True, "message_id": "m1", "text": "hi",
        })
        result = await integ.send_unified_message(
            "teams_team_1", "teams_channel_1", "hi",
            {"importance": "high", "subject": "s", "thread_id": "t1"},
        )
        assert result["ok"] is True
        assert result["message_id"] == "m1"
        assert result["platform"] == "Microsoft Teams"
        integ.teams_service.send_message.assert_awaited_once()
        assert integ.atom_memory.store.await_count == 1
        assert integ.atom_search.index.await_count == 1
        assert integ.atom_workflow.trigger_workflows.await_count == 1

    async def test_send_returns_service_failure_passthrough(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.teams_service.send_message = AsyncMock(return_value={"ok": False, "error": "nope"})
        result = await integ.send_unified_message("teams_team_1", "teams_channel_1", "hi")
        assert result == {"ok": False, "error": "nope"}

    async def test_send_invalid_workspace_prefix(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        result = await integ.send_unified_message("slack_w", "teams_channel_1", "hi")
        assert result["ok"] is False

    async def test_send_unsupported_platform(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        result = await integ.send_unified_message("slack_w", "slack_c", "hi")
        assert result == {"ok": False, "error": "Unsupported platform"}

    async def test_send_error_does_not_leak_exception_detail(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.teams_service.send_message = AsyncMock(side_effect=ValueError("db password=secret"))
        result = await integ.send_unified_message("teams_team_1", "teams_channel_1", "hi")
        assert result["ok"] is False
        assert "secret" not in result.get("error", "")


class TestTeamsUnifiedMessages:
    async def test_get_unified_messages_success(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.teams_service.get_channel_messages = AsyncMock(return_value=[
            _message("m2", "second", "2026-08-01T11:00:00Z"),
            _message("m1", "first", "2026-08-01T10:00:00Z", thread_id="t1"),
        ])
        result = await integ.get_unified_messages("teams_team_1", "teams_channel_1", limit=10)
        assert len(result) == 2
        assert result[0]["id"] == "teams_m2"  # newest first
        assert result[1]["thread_id"] == "teams_t1"
        assert result[1]["mentions"][0]["name"] == "Bob"
        assert result[1]["files"][0]["url"] == "https://f"
        assert result[1]["metadata"]["reply_count"] == 0
        assert result[1]["metadata"]["importance_level"] == 2
        integ.teams_service.get_channel_messages.assert_awaited_once_with(
            "team_1", "channel_1", limit=10, latest=None, oldest=None
        )

    async def test_get_unified_messages_none_timestamp_does_not_wipe_listing(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.teams_service.get_channel_messages = AsyncMock(return_value=[
            _message("m1", "first", None),
            _message("m2", "second", "2026-08-01T11:00:00Z"),
        ])
        result = await integ.get_unified_messages("teams_team_1", "teams_channel_1")
        assert len(result) == 2

    async def test_get_unified_messages_non_teams(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        assert await integ.get_unified_messages("slack_w", "slack_c") == []

    async def test_get_unified_messages_missing_workspace(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        assert await integ.get_unified_messages("slack_w", "teams_channel_1") == []

    async def test_get_unified_messages_error_returns_empty(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.teams_service.get_channel_messages = AsyncMock(side_effect=RuntimeError("boom"))
        assert await integ.get_unified_messages("teams_team_1", "teams_channel_1") == []


class TestTeamsUnifiedSearch:
    async def test_unified_search_success(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        msg = _message("m1", "alpha beta gamma", timestamp="2026-08-01T10:00:00Z",
                       thread_id="t1")
        integ.teams_service.search_messages = AsyncMock(return_value={
            "ok": True, "messages": [msg],
        })
        result = await integ.unified_search("beta", "teams_team_1", "teams_channel_1",
                                            {"user_id": "u1", "limit": 10})
        assert len(result) == 1
        assert result[0]["title"] == "subj"
        assert result[0]["relevance_score"] == 1.0
        assert result[0]["url"].startswith("https://teams.microsoft.com/l/message/m1/thread/")
        assert result[0]["highlights"] != []
        integ.teams_service.search_messages.assert_awaited_once_with(
            "team_1", "beta", channel_id="channel_1", user_id="u1", limit=10
        )

    async def test_unified_search_no_channel(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        assert await integ.unified_search("q", "teams_team_1") == []

    async def test_unified_search_not_ok(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.teams_service.search_messages = AsyncMock(return_value={"ok": False, "messages": []})
        assert await integ.unified_search("q", "teams_team_1", "teams_channel_1") == []

    async def test_unified_search_error_returns_empty(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.teams_service.search_messages = AsyncMock(side_effect=RuntimeError("boom"))
        assert await integ.unified_search("q", "teams_team_1", "teams_channel_1") == []


class TestTeamsWorkflowAndAnalytics:
    async def test_create_workflow_non_teams_delegates(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.atom_workflow.create_workflow = AsyncMock(return_value={"ok": True})
        data = {"name": "w", "triggers": [{"platform": "slack"}], "actions": []}
        result = await integ.create_unified_workflow(data)
        assert result == {"ok": True}

    async def test_create_workflow_non_teams_no_service(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.atom_workflow = None
        result = await integ.create_unified_workflow({"name": "w", "triggers": [], "actions": []})
        assert result == {"ok": False, "error": "Workflow service not available"}

    async def test_create_workflow_teams_engine_missing(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        monkeypatch.setattr(tmi, "teams_workflow_engine", None)
        data = {"name": "w", "triggers": [{"platform": "microsoft_teams", "event": "message"}],
                "actions": []}
        result = await integ.create_unified_workflow(data)
        assert result == {"ok": False, "error": "Teams workflow engine not available"}

    async def test_create_workflow_teams_involved(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        data = {"name": "w", "triggers": [{"platform": "slack"}],
                "actions": [{"platform": "microsoft_teams", "action": "post"}]}
        result = await integ.create_unified_workflow(data)
        assert result == {"ok": False, "error": "Teams workflow engine not available"}

    async def test_create_workflow_teams_trigger_event(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        data = {"name": "w", "triggers": [{"platform": "slack", "event": "teams.message"}],
                "actions": []}
        result = await integ.create_unified_workflow(data)
        assert result["ok"] is False

    async def test_create_workflow_error_generic(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        result = await integ.create_unified_workflow({"triggers": [1], "actions": []})
        assert result["ok"] is False
        assert "int" not in result.get("error", "")

    async def test_get_unified_analytics_success(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        point = MagicMock()
        point.timestamp = datetime(2026, 8, 1, tzinfo=timezone.utc)
        point.value = 5
        point.dimensions = {}
        point.metadata = {}
        integ.teams_analytics.get_analytics = AsyncMock(return_value=[point, point])
        result = await integ.get_unified_analytics("messages", "7d", "teams_team_1", {"filters": {}})
        assert result["platform"] == "Microsoft Teams"
        assert result["total_points"] == 2
        assert result["data_points"][0]["value"] == 5
        integ.teams_analytics.get_analytics.assert_awaited_once_with(
            metric="messages", time_range="7d", workspace_id="team_1", filters={}
        )

    async def test_get_unified_analytics_error_generic(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.teams_analytics.get_analytics = AsyncMock(side_effect=RuntimeError("tenant-42 secret"))
        result = await integ.get_unified_analytics("messages", "7d")
        assert result["ok"] is False
        assert "secret" not in result.get("error", "")


class TestTeamsLifecycle:
    async def test_initialize_success(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ._start_integration_workers = AsyncMock()
        integ._initialize_unified_data = AsyncMock()
        integ._setup_cross_platform_handlers = AsyncMock()
        assert await integ.initialize() is True
        assert integ.is_initialized is True

    async def test_initialize_missing_services(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.teams_service = None
        assert await integ.initialize() is False

    async def test_initialize_exception(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ._start_integration_workers = AsyncMock(side_effect=RuntimeError("boom"))
        assert await integ.initialize() is False

    async def test_start_integration_workers(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ._teams_message_ingestion_worker = AsyncMock()
        integ._teams_event_processing_worker = AsyncMock()
        integ._unified_search_indexing_worker = AsyncMock()
        await integ._start_integration_workers()
        await asyncio.sleep(0)
        integ._teams_message_ingestion_worker.assert_awaited_once()
        integ._teams_event_processing_worker.assert_awaited_once()
        integ._unified_search_indexing_worker.assert_awaited_once()

    async def test_initialize_unified_data(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.atom_memory.query = AsyncMock(side_effect=[[], [], []])
        await integ._initialize_unified_data()
        assert integ.atom_memory.query.await_count == 3

    async def test_initialize_unified_data_error(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.atom_memory.query = AsyncMock(side_effect=RuntimeError("boom"))
        await integ._initialize_unified_data()

    async def test_setup_cross_platform_handlers(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        handlers = {e: [] for e in TeamsEventType}
        integ.teams_service.event_handlers = handlers
        await integ._setup_cross_platform_handlers()
        assert len(handlers[TeamsEventType.MESSAGE]) == 1
        assert len(handlers[TeamsEventType.FILE_UPLOAD]) == 1
        assert len(handlers[TeamsEventType.USER_JOIN]) == 1

    async def test_setup_cross_platform_handlers_no_service(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.teams_service = None
        await integ._setup_cross_platform_handlers()

    async def test_module_level_instance(self):
        assert tmi.atom_teams_integration.is_initialized is False


class TestTeamsCrossPlatformHandlers:
    async def test_message_cross_platform_success(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ._store_message_in_memory = AsyncMock()
        integ._index_message_in_search = AsyncMock()
        integ._trigger_workflows = AsyncMock()
        await integ._handle_teams_message_cross_platform({"message_id": "m1"})
        integ._store_message_in_memory.assert_awaited_once()
        integ._index_message_in_search.assert_awaited_once()
        integ._trigger_workflows.assert_awaited_once()

    async def test_message_cross_platform_error(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ._store_message_in_memory = AsyncMock(side_effect=RuntimeError("boom"))
        await integ._handle_teams_message_cross_platform({"message_id": "m1"})

    async def test_file_cross_platform_success(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ._index_file_in_search = AsyncMock()
        integ._store_file_in_memory = AsyncMock()
        integ._trigger_workflows = AsyncMock()
        await integ._handle_teams_file_cross_platform({"file_id": "f1"})
        integ._index_file_in_search.assert_awaited_once()
        integ._store_file_in_memory.assert_awaited_once()
        integ._trigger_workflows.assert_awaited_once()

    async def test_file_cross_platform_error(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ._index_file_in_search = AsyncMock(side_effect=RuntimeError("boom"))
        await integ._handle_teams_file_cross_platform({"file_id": "f1"})

    async def test_user_event_cross_platform_success(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ._update_user_profile_cross_platform = AsyncMock()
        integ._trigger_workflows = AsyncMock()
        await integ._handle_teams_user_event_cross_platform({"user_id": "u1"})
        integ._update_user_profile_cross_platform.assert_awaited_once()
        integ._trigger_workflows.assert_awaited_once()

    async def test_user_event_cross_platform_error(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ._update_user_profile_cross_platform = AsyncMock(side_effect=RuntimeError("boom"))
        await integ._handle_teams_user_event_cross_platform({"user_id": "u1"})


class TestTeamsMemorySearchWorkflows:
    async def test_store_message_in_memory_no_memory(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.atom_memory = None
        await integ._store_message_in_memory({"message_id": "m1"}, "teams")

    async def test_store_message_in_memory_success(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        await integ._store_message_in_memory(
            {"message_id": "m1", "text": "hi", "user_id": "u1"}, "teams", {"k": "v"}
        )
        integ.atom_memory.store.assert_awaited_once()

    async def test_store_message_in_memory_error(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.atom_memory.store = AsyncMock(side_effect=RuntimeError("boom"))
        await integ._store_message_in_memory({"message_id": "m1"}, "teams")

    async def test_index_message_in_search_no_search(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.atom_search = None
        await integ._index_message_in_search({"message_id": "m1"}, "teams")

    async def test_index_message_in_search_success(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        await integ._index_message_in_search(
            {"message_id": "m1", "subject": "s", "user_name": "A"}, "teams"
        )
        integ.atom_search.index.assert_awaited_once()

    async def test_index_message_in_search_error(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.atom_search.index = AsyncMock(side_effect=RuntimeError("boom"))
        await integ._index_message_in_search({"message_id": "m1"}, "teams")

    async def test_trigger_workflows_no_service(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.atom_workflow = None
        await integ._trigger_workflows({"message_id": "m1"}, "evt")

    async def test_trigger_workflows_success(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        await integ._trigger_workflows({"message_id": "m1"}, "evt", {"k": "v"})
        integ.atom_workflow.trigger_workflows.assert_awaited_once()

    async def test_trigger_workflows_error(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.atom_workflow.trigger_workflows = AsyncMock(side_effect=RuntimeError("boom"))
        await integ._trigger_workflows({"message_id": "m1"}, "evt")

    def test_generate_search_highlights(self):
        integ = tmi.AtomTeamsIntegration({})
        assert integ._generate_search_highlights(
            "alpha beta gamma delta epsilon", "beta"
        ) == ["alpha beta gamma delta epsilon"]
        assert integ._generate_search_highlights("no match here", "zzz") == []
        assert integ._generate_search_highlights(None, "q") == []


class TestTeamsWorkers:
    @pytest.mark.asyncio
    async def test_message_ingestion_worker_loop(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        calls = {"n": 0}

        async def fake_sleep(_):
            calls["n"] += 1
            if calls["n"] >= 2:
                raise RuntimeError("stop")

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        with pytest.raises(RuntimeError):
            await integ._teams_message_ingestion_worker()

    @pytest.mark.asyncio
    async def test_event_processing_worker_loop(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        calls = {"n": 0}

        async def fake_sleep(_):
            calls["n"] += 1
            if calls["n"] >= 2:
                raise RuntimeError("stop")

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        with pytest.raises(RuntimeError):
            await integ._teams_event_processing_worker()

    @pytest.mark.asyncio
    async def test_search_indexing_worker_loop(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.atom_memory.query = AsyncMock(return_value=[
            {"id": "m1", "message_id": "m1"},
            {"id": "m2", "message_id": "m2"},
        ])
        integ.atom_memory.update = AsyncMock()
        calls = {"n": 0}

        async def fake_sleep(_):
            calls["n"] += 1
            if calls["n"] >= 2:
                raise RuntimeError("stop")

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        with pytest.raises(RuntimeError):
            await integ._unified_search_indexing_worker()
        assert integ.atom_memory.query.await_count == 2
        assert integ.atom_memory.update.await_count == 4
        assert integ.atom_search.index.await_count == 4

    @pytest.mark.asyncio
    async def test_search_indexing_worker_no_services(self, monkeypatch):
        integ = _make_teams_integration(monkeypatch)
        integ.atom_search = None
        integ.atom_memory = None
        calls = {"n": 0}

        async def fake_sleep(_):
            calls["n"] += 1
            if calls["n"] >= 2:
                raise RuntimeError("stop")

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        with pytest.raises(RuntimeError):
            await integ._unified_search_indexing_worker()


# ---------------------------------------------------------------------------
# google_chat_enhanced_service
# ---------------------------------------------------------------------------

class _FakeRedis:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.store[key] = value

    def keys(self, pattern):
        prefix = pattern.rstrip("*")
        return [k for k in self.store if k.startswith(prefix)]

    def pipeline(self):
        return self

    def incr(self, key):
        self.store[key] = int(self.store.get(key, 0)) + 1
        return self

    def expire(self, key, ttl):
        return self

    def execute(self):
        return []

    def close(self):
        pass


class _FakeDB:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.last_params = None

    def execute(self, sql, params=None):
        self.last_params = params
        return self

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows

    def commit(self):
        pass


def _fernet_key() -> str:
    return base64.urlsafe_b64encode(b"k" * 32).decode()


def _gchat_service(monkeypatch, **config):
    defaults = {
        "client_id": "cid", "client_secret": "csec", "redirect_uri": "http://r",
        "encryption_key": _fernet_key(),
    }
    defaults.update(config)
    svc = gces.GoogleChatEnhancedService(tenant_id="t1", config=defaults)
    return svc


def _gchat_space(space_id="spaces/sp1", user_id="user_1", access_token="tok123"):
    return GoogleChatSpace(
        space_id=space_id,
        name="spaces/sp1",
        display_name="SP1",
        type="ROOM",
        user_id=user_id,
        access_token=access_token,
        refresh_token="rt",
        scopes=["chat"],
    )


def _gchat_message(create_time="2026-08-01T00:00:00Z"):
    return GoogleChatMessage(
        message_id="spaces/sp1/messages/m1",
        text="hi",
        user_id="u1",
        user_name="Bob",
        user_email="b@x.com",
        space_id="spaces/sp1",
        timestamp=create_time,
        created_at=datetime.fromisoformat(create_time.replace("Z", "+00:00")),
        thread_id="spaces/sp1/threads/t1",
    )


class TestGoogleChatEnumsAndModels:
    def test_space_post_init_defaults(self):
        space = GoogleChatSpace(space_id="s", name="n", display_name="d", type="ROOM")
        assert space.space_admins == []
        assert space.scopes == []
        assert space.integration_data == {}
        assert space.created_at is not None

    def test_message_post_init_defaults(self):
        msg = GoogleChatMessage(
            message_id="m", text="t", user_id="u", user_name="n",
            user_email="e", space_id="s", timestamp="ts",
        )
        assert msg.card_v2 == [] and msg.mentions == [] and msg.files == []
        assert msg.created_at is not None

    def test_file_post_init_defaults(self):
        f = GoogleChatFile(
            file_id="f", name="n", display_name="d", mime_type="m",
            file_type="t", size=1, user_id="u", user_name="n",
            user_email="e", space_id="s", timestamp="ts",
        )
        assert f.tags == [] and f.metadata == {} and f.integration_data == {}
        assert f.created_at is not None

    def test_enum_values(self):
        assert GoogleChatEventType.MESSAGE.value == "message"
        assert GoogleChatConnectionStatus.CONNECTED.value == "connected"


class TestGoogleChatRateLimiter:
    async def test_local_limit_under(self):
        rl = GoogleChatRateLimiter()
        assert await rl.check_limit("sp", "messages_send") is True

    async def test_local_limit_at_limit(self):
        rl = GoogleChatRateLimiter()
        for _ in range(100):
            assert await rl.check_limit("sp", "messages_send") is True
        assert await rl.check_limit("sp", "messages_send") is False

    async def test_local_limit_window_reset(self, monkeypatch):
        rl = GoogleChatRateLimiter()
        assert await rl.check_limit("sp", "messages_send") is True
        monkeypatch.setattr(gces.time, "time", lambda: 9999999999)
        assert await rl.check_limit("sp", "messages_send") is True

    async def test_redis_limit_under_and_at_limit(self):
        redis = _FakeRedis()
        rl = GoogleChatRateLimiter(redis)
        assert await rl.check_limit("sp", "members_list") is True
        redis.store["gc_rate:sp:members_list"] = "60"
        assert await rl.check_limit("sp", "members_list") is False

    async def test_unknown_endpoint_default_limit(self):
        rl = GoogleChatRateLimiter()
        for _ in range(10):
            assert await rl.check_limit("sp", "unknown_ep") is True
        assert await rl.check_limit("sp", "unknown_ep") is False


class TestGoogleChatInitAndCrypto:
    def test_init_without_config(self):
        svc = gces.GoogleChatEnhancedService()
        assert svc.client_id is None
        assert svc.cipher is None

    def test_init_with_config(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        assert svc.oauth_flow is not None
        assert svc.rate_limiter is not None

    def test_setup_oauth_flow_failure(self, monkeypatch):
        monkeypatch.setattr(gces.Flow, "from_client_config", MagicMock(side_effect=RuntimeError("x")))
        svc = gces.GoogleChatEnhancedService(tenant_id="t", config={
            "client_id": "a", "client_secret": "b", "redirect_uri": "c",
        })
        assert svc.oauth_flow is None

    def test_encrypt_token_no_cipher_raises(self):
        svc = gces.GoogleChatEnhancedService()
        with pytest.raises(RuntimeError):
            svc._encrypt_token("tok")

    def test_encrypt_decrypt_roundtrip(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        enc = svc._encrypt_token("tok123")
        assert enc != "tok123"
        assert svc._decrypt_token(enc) == "tok123"

    def test_decrypt_no_cipher_returns_raw(self, monkeypatch):
        svc = gces.GoogleChatEnhancedService()
        assert svc._decrypt_token("rawtok") == "rawtok"

    def test_decrypt_corrupt_falls_back(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        assert svc._decrypt_token("not-valid-fernet-token") == "not-valid-fernet-token"

    def test_health_check(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        h = svc.health_check()
        assert h["healthy"] is True
        svc2 = gces.GoogleChatEnhancedService()
        assert svc2.health_check()["healthy"] is False

    async def test_get_service_info(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        info = await svc.get_service_info()
        assert info["name"] == "Google Chat Enhanced Service"
        assert info["status"]["encryption_enabled"] is True
    def test_get_capabilities(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        caps = svc.get_capabilities()
        assert caps["supports_webhooks"] is True
        assert len(caps["operations"]) == 3


class TestGoogleChatOAuth:
    def test_generate_oauth_url(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        flow = MagicMock()
        flow.authorization_url.return_value = ("https://auth.example/x", "state")
        svc.oauth_flow = flow
        url = svc.generate_oauth_url("st", "u1")
        assert url == "https://auth.example/x"

    def test_generate_oauth_url_no_flow(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc.oauth_flow = None
        with pytest.raises(Exception):
            svc.generate_oauth_url("st", "u1")

    async def test_exchange_code_success(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        creds = MagicMock()
        creds.token = "tok"
        creds.refresh_token = "rt"
        creds.scopes = ["chat"]
        creds.expiry = None
        flow = MagicMock()
        flow.credentials = creds
        svc.oauth_flow = flow

        def fake_build(name, version, credentials=None):
            if name == "oauth2":
                svc2 = MagicMock()
                svc2.userinfo().get().execute.return_value = {"id": "user_1", "email": "u@x.com"}
                return svc2
            svc3 = MagicMock()
            svc3.spaces().list(pageSize=100, filter="spaceType = SPACE").execute.return_value = {
                "spaces": [{
                    "name": "spaces/sp1", "displayName": "SP1", "type": "ROOM",
                    "spaceThreadingState": "THREADING_ENABLED",
                    "createTime": "2026-08-01T00:00:00Z",
                }]
            }
            return svc3

        monkeypatch.setattr(gces, "build", fake_build)
        result = await svc.exchange_code_for_tokens("code", "state")
        assert result["ok"] is True
        assert len(result["spaces"]) == 1
        assert result["spaces"][0]["space_id"] == "spaces/sp1"

    async def test_exchange_code_no_spaces(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        creds = MagicMock()
        creds.token = "tok"
        creds.refresh_token = "rt"
        creds.scopes = ["chat"]
        creds.expiry = None
        flow = MagicMock()
        flow.credentials = creds
        svc.oauth_flow = flow

        def fake_build(name, version, credentials=None):
            svc2 = MagicMock()
            svc2.userinfo().get().execute.return_value = {"id": "user_1"}
            svc3 = MagicMock()
            svc3.spaces().list(pageSize=100, filter="spaceType = SPACE").execute.return_value = {}
            return svc3 if name == "chat" else svc2

        monkeypatch.setattr(gces, "build", fake_build)
        result = await svc.exchange_code_for_tokens("code", "state")
        assert result["ok"] is False
        assert result["error"] == "No accessible spaces found"

    async def test_exchange_code_error_no_flow(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc.oauth_flow = None
        result = await svc.exchange_code_for_tokens("code", "state")
        assert result["ok"] is False

    async def test_exchange_code_error_no_leak(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        flow = MagicMock()
        flow.fetch_token = MagicMock(side_effect=ValueError("token endpoint leaked secret"))
        svc.oauth_flow = flow
        result = await svc.exchange_code_for_tokens("code", "state")
        assert result["ok"] is False
        assert "secret" not in result.get("error", "")


class TestGoogleChatSpaces:
    def test_get_user_space_db(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        db = _FakeDB(rows=[{
            "space_id": "spaces/sp1", "name": "spaces/sp1", "display_name": "SP1",
            "type": "ROOM",
        }])
        svc.db = db
        space = svc._get_user_space("user_1")
        assert space is not None
        assert space.space_id == "spaces/sp1"

    def test_get_user_space_cache(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        redis = _FakeRedis()
        redis.store["gc_space_user:user_1"] = json.dumps({
            "space_id": "spaces/sp1", "name": "spaces/sp1", "display_name": "SP1",
            "type": "ROOM",
        })
        svc.redis_client = redis
        space = svc._get_user_space("user_1")
        assert space is not None

    def test_get_user_space_none(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        assert svc._get_user_space("user_1") is None

    def test_get_user_space_error(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        db = _FakeDB()
        db.execute = MagicMock(side_effect=RuntimeError("boom"))
        svc.db = db
        assert svc._get_user_space("user_1") is None

    def test_get_user_space_by_id_db(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        db = _FakeDB(rows=[{
            "space_id": "spaces/sp1", "name": "spaces/sp1", "display_name": "SP1",
            "type": "ROOM",
        }])
        svc.db = db
        assert svc._get_user_space_by_id("spaces/sp1") is not None

    def test_get_user_space_by_id_cache(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        redis = _FakeRedis()
        redis.store["gc_space_id:spaces/sp1"] = json.dumps({
            "space_id": "spaces/sp1", "name": "spaces/sp1", "display_name": "SP1",
            "type": "ROOM",
        })
        svc.redis_client = redis
        assert svc._get_user_space_by_id("spaces/sp1") is not None

    def test_get_user_space_by_id_error(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        db = _FakeDB()
        db.execute = MagicMock(side_effect=RuntimeError("boom"))
        svc.db = db
        assert svc._get_user_space_by_id("spaces/sp1") is None

    async def test_get_spaces_db_with_user(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc.db = _FakeDB(rows=[{
            "space_id": "spaces/sp1", "name": "spaces/sp1", "display_name": "SP1",
            "type": "ROOM",
        }])
        spaces = await svc.get_spaces("user_1")
        assert len(spaces) == 1

    async def test_get_spaces_db_all(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc.db = _FakeDB(rows=[{
            "space_id": "spaces/sp1", "name": "spaces/sp1", "display_name": "SP1",
            "type": "ROOM",
        }])
        assert len(await svc.get_spaces()) == 1

    async def test_get_spaces_cache(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        redis = _FakeRedis()
        redis.store["gc_space_user:user_1"] = json.dumps({
            "space_id": "spaces/sp1", "name": "spaces/sp1", "display_name": "SP1",
            "type": "ROOM", "user_id": "user_1",
        })
        svc.redis_client = redis
        spaces = await svc.get_spaces("user_1")
        assert len(spaces) == 1
        assert await svc.get_spaces("other") == []

    async def test_get_spaces_error(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        db = _FakeDB()
        db.execute = MagicMock(side_effect=RuntimeError("boom"))
        svc.db = db
        assert await svc.get_spaces("user_1") == []

    def test_save_user_space_db(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc.db = _FakeDB()
        space = _gchat_space()
        assert svc._save_user_space(space) is True
        assert svc.connection_status["spaces/sp1"] == GoogleChatConnectionStatus.CONNECTED
        assert svc.db.last_params[20] != "tok123"  # access token encrypted at rest

    def test_save_user_space_db_real_sqlite(self, monkeypatch):
        import sqlite3
        svc = _gchat_service(monkeypatch)
        conn = sqlite3.connect(":memory:")
        conn.execute(
            """CREATE TABLE google_chat_spaces (
               space_id TEXT, name TEXT, display_name TEXT, type TEXT, description TEXT,
               space_threading_state TEXT, space_type TEXT, space_uri TEXT,
               space_permission_level TEXT, space_admins TEXT, created_at TEXT,
               last_modified_at TEXT, single_user_bot_dm INT, threaded INT,
               member_count INT, message_count INT, files_count INT, is_archived INT,
               is_active INT, external_user_permission TEXT, access_token TEXT,
               refresh_token TEXT, scopes TEXT, user_id TEXT, tenant_id TEXT,
               integration_data TEXT)"""
        )
        svc.db = conn
        # G4: INSERT had 28 placeholders for 26 columns — real sqlite always
        # raised OperationalError, so no space could ever be persisted.
        assert svc._save_user_space(_gchat_space()) is True

    def test_save_user_space_cache(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc.redis_client = _FakeRedis()
        assert svc._save_user_space(_gchat_space()) is True

    def test_save_user_space_no_backend_no_error(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        assert svc._save_user_space(_gchat_space()) is True
        assert svc.connection_status["spaces/sp1"] == GoogleChatConnectionStatus.CONNECTED

    def test_save_user_space_error(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        db = _FakeDB()
        db.execute = MagicMock(side_effect=RuntimeError("boom"))
        svc.db = db
        assert svc._save_user_space(_gchat_space()) is False

    def test_get_chat_service_cached(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc.chat_services["user_1"] = "svc"
        assert svc._get_chat_service("user_1") == "svc"

    def test_get_chat_service_new(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space = MagicMock(return_value=_gchat_space())
        monkeypatch.setattr(gces, "build", MagicMock(return_value="built"))
        assert svc._get_chat_service("user_1") == "built"
        assert svc.chat_services["user_1"] == "built"

    def test_get_chat_service_no_space(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space = MagicMock(return_value=None)
        assert svc._get_chat_service("user_1") is None

    def test_get_chat_service_no_token(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space = MagicMock(return_value=_gchat_space(access_token=None))
        assert svc._get_chat_service("user_1") is None

    def test_get_chat_service_error(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space = MagicMock(side_effect=RuntimeError("boom"))
        assert svc._get_chat_service("user_1") is None


class TestGoogleChatMessages:
    def _chat_mock(self, result=None, raise_exc=False):
        svc = MagicMock()
        create = svc.spaces().messages().create
        if raise_exc:
            create.side_effect = RuntimeError("gapi boom")
        else:
            create.return_value.execute.return_value = result or {
                "name": "spaces/sp1/messages/m1",
                "thread": {"name": "spaces/sp1/threads/t1"},
                "createTime": "2026-08-01T00:00:00Z",
            }
        return svc

    async def test_send_message_success(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space_by_id = MagicMock(return_value=_gchat_space())
        svc._get_chat_service = MagicMock(return_value=self._chat_mock())
        result = await svc.send_message("spaces/sp1", "hi", message_format="TEXT")
        assert result["ok"] is True
        assert result["message_id"] == "spaces/sp1/messages/m1"

    async def test_send_message_thread(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space_by_id = MagicMock(return_value=_gchat_space())
        chat = MagicMock()
        svc._get_chat_service = MagicMock(return_value=chat)
        chat.spaces().messages().create.return_value.execute.return_value = {
            "name": "spaces/sp1/messages/m1",
            "createTime": "2026-08-01T00:00:00Z",
        }
        result = await svc.send_message(
            "spaces/sp1", "hi", thread_id="t1", message_format="MARKDOWN",
            card_v2=[{"card": {}}],
        )
        assert result["ok"] is True
        parent = chat.spaces().messages().create.call_args.kwargs["parent"]
        assert parent == "spaces/sp1/threads/t1"

    async def test_send_message_markdown_body(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space_by_id = MagicMock(return_value=_gchat_space())
        chat = MagicMock()
        svc._get_chat_service = MagicMock(return_value=chat)
        chat.spaces().messages().create.return_value.execute.return_value = {
            "name": "m", "createTime": "2026-08-01T00:00:00Z",
        }
        await svc.send_message("spaces/sp1", "hi", message_format="MARKDOWN")
        body = chat.spaces().messages().create.call_args.kwargs["body"]
        assert "text" not in body
        assert body["formattedText"] == "hi"

    async def test_send_message_rate_limited(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc.rate_limiter.check_limit = AsyncMock(return_value=False)
        result = await svc.send_message("spaces/sp1", "hi")
        assert result["ok"] is False

    async def test_send_message_space_not_found(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space_by_id = MagicMock(return_value=None)
        result = await svc.send_message("spaces/sp1", "hi")
        assert result["ok"] is False

    async def test_send_message_no_chat_service(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space_by_id = MagicMock(return_value=_gchat_space())
        svc._get_chat_service = MagicMock(return_value=None)
        result = await svc.send_message("spaces/sp1", "hi")
        assert result["ok"] is False

    async def test_send_message_api_error_no_leak(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space_by_id = MagicMock(return_value=_gchat_space())
        svc._get_chat_service = MagicMock(return_value=self._chat_mock(raise_exc=True))
        result = await svc.send_message("spaces/sp1", "hi")
        assert result["ok"] is False
        assert "gapi" not in result.get("error", "")

    async def test_get_space_messages_success_with_redis(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space_by_id = MagicMock(return_value=_gchat_space())
        chat = MagicMock()
        chat.spaces().messages().list.return_value.execute.return_value = {
            "messages": [{
                "name": "spaces/sp1/messages/m1",
                "text": "hi",
                "formattedText": "hi",
                "sender": {"name": "users/u1", "displayName": "Bob", "email": "b@x.com"},
                "thread": {"name": "spaces/sp1/threads/t1"},
                "createTime": "2026-08-01T00:00:00Z",
                "lastModifiedTime": "2026-08-01T00:05:00Z",
                "type": "MESSAGE",
            }]
        }
        svc._get_chat_service = MagicMock(return_value=chat)
        redis = _FakeRedis()
        svc.redis_client = redis
        messages = await svc.get_space_messages("spaces/sp1", limit=10)
        # G1: cache write with asdict() used to crash on datetime -> []
        assert len(messages) == 1
        assert messages[0].text == "hi"
        assert redis.store["gc_messages:spaces/sp1"] is not None

    async def test_get_space_messages_empty(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space_by_id = MagicMock(return_value=_gchat_space())
        chat = MagicMock()
        chat.spaces().messages().list.return_value.execute.return_value = {}
        svc._get_chat_service = MagicMock(return_value=chat)
        assert await svc.get_space_messages("spaces/sp1") == []

    async def test_get_space_messages_rate_limited(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc.rate_limiter.check_limit = AsyncMock(return_value=False)
        assert await svc.get_space_messages("spaces/sp1") == []

    async def test_get_space_messages_cache_fallback(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space_by_id = MagicMock(return_value=_gchat_space())
        chat = MagicMock()
        chat.spaces().messages().list.return_value.execute.side_effect = RuntimeError("boom")
        svc._get_chat_service = MagicMock(return_value=chat)
        redis = _FakeRedis()
        cached = json.dumps([asdict(_gchat_message())], default=str)
        redis.store["gc_messages:spaces/sp1"] = cached
        svc.redis_client = redis
        messages = await svc.get_space_messages("spaces/sp1")
        assert len(messages) == 1

    async def test_get_space_messages_error_no_cache(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space_by_id = MagicMock(return_value=_gchat_space())
        chat = MagicMock()
        chat.spaces().messages().list.return_value.execute.side_effect = RuntimeError("boom")
        svc._get_chat_service = MagicMock(return_value=chat)
        assert await svc.get_space_messages("spaces/sp1") == []

    async def test_send_message_updates_db_stats(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space_by_id = MagicMock(return_value=_gchat_space())
        svc._get_chat_service = MagicMock(return_value=self._chat_mock())
        svc.db = _FakeDB()
        result = await svc.send_message("spaces/sp1", "hi")
        assert result["ok"] is True
        assert svc.db.last_params[1] == "spaces/sp1"

    async def test_send_message_falsy_result(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space_by_id = MagicMock(return_value=_gchat_space())
        chat = MagicMock()
        chat.spaces().messages().create.return_value.execute.return_value = {}
        svc._get_chat_service = MagicMock(return_value=chat)
        result = await svc.send_message("spaces/sp1", "hi")
        assert result["ok"] is False

    async def test_get_space_messages_space_not_found(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space_by_id = MagicMock(return_value=None)
        assert await svc.get_space_messages("spaces/sp1") == []

    async def test_get_space_messages_no_chat_service(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space_by_id = MagicMock(return_value=_gchat_space())
        svc._get_chat_service = MagicMock(return_value=None)
        assert await svc.get_space_messages("spaces/sp1") == []

    async def test_search_messages_space_not_found(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space_by_id = MagicMock(return_value=None)
        result = await svc.search_messages("spaces/sp1", "q")
        assert result["ok"] is False

    async def test_search_messages_no_chat_service(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space_by_id = MagicMock(return_value=_gchat_space())
        svc._get_chat_service = MagicMock(return_value=None)
        result = await svc.search_messages("spaces/sp1", "q")
        assert result["ok"] is False

    async def test_search_messages_success(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space_by_id = MagicMock(return_value=_gchat_space())
        chat = MagicMock()
        chat.spaces().messages().list.return_value.execute.return_value = {
            "messages": [{
                "name": "spaces/sp1/messages/m1",
                "text": "hi",
                "sender": {"name": "users/u1", "displayName": "Bob", "email": "b@x.com"},
                "createTime": "2026-08-01T00:00:00Z",
            }],
            "nextPageToken": "tok",
        }
        svc._get_chat_service = MagicMock(return_value=chat)
        result = await svc.search_messages("spaces/sp1", "hi")
        assert result["ok"] is True
        assert result["total"] == 1
        assert result["next_page_token"] == "tok"
        assert result["messages"][0].message_id == "spaces/sp1/messages/m1"

    async def test_search_messages_empty(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space_by_id = MagicMock(return_value=_gchat_space())
        chat = MagicMock()
        chat.spaces().messages().list.return_value.execute.return_value = {}
        svc._get_chat_service = MagicMock(return_value=chat)
        result = await svc.search_messages("spaces/sp1", "hi")
        assert result["ok"] is True
        assert result["messages"] == []

    async def test_search_messages_rate_limited(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc.rate_limiter.check_limit = AsyncMock(return_value=False)
        result = await svc.search_messages("spaces/sp1", "hi")
        assert result["ok"] is False

    async def test_search_messages_error_no_leak(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space_by_id = MagicMock(return_value=_gchat_space())
        chat = MagicMock()
        chat.spaces().messages().list.return_value.execute.side_effect = RuntimeError("gapi boom")
        svc._get_chat_service = MagicMock(return_value=chat)
        result = await svc.search_messages("spaces/sp1", "hi")
        assert result["ok"] is False
        assert "gapi" not in result.get("error", "")


class TestGoogleChatConnectionAndOps:
    async def test_test_connection_success(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        space = _gchat_space()
        svc._get_user_space_by_id = MagicMock(return_value=space)
        chat = MagicMock()
        chat.spaces().get.return_value.execute.return_value = {
            "name": "spaces/sp1", "displayName": "SP1", "type": "ROOM",
            "spaceThreadingState": "THREADING_ENABLED",
        }
        svc._get_chat_service = MagicMock(return_value=chat)
        result = await svc.test_connection("spaces/sp1")
        assert result["connected"] is True
        assert svc.connection_status["spaces/sp1"] == GoogleChatConnectionStatus.CONNECTED

    async def test_test_connection_space_not_found(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space_by_id = MagicMock(return_value=None)
        result = await svc.test_connection("spaces/sp1")
        assert result["connected"] is False
        assert svc.connection_status["spaces/sp1"] == GoogleChatConnectionStatus.ERROR

    async def test_test_connection_no_service(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space_by_id = MagicMock(return_value=_gchat_space())
        svc._get_chat_service = MagicMock(return_value=None)
        result = await svc.test_connection("spaces/sp1")
        assert result["connected"] is False

    async def test_test_connection_invalid_response(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space_by_id = MagicMock(return_value=_gchat_space())
        chat = MagicMock()
        chat.spaces().get.return_value.execute.return_value = {}
        svc._get_chat_service = MagicMock(return_value=chat)
        result = await svc.test_connection("spaces/sp1")
        assert result["connected"] is False

    async def test_test_connection_error_no_leak(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc._get_user_space_by_id = MagicMock(return_value=_gchat_space())
        chat = MagicMock()
        chat.spaces().get.return_value.execute.side_effect = RuntimeError("gapi secret")
        svc._get_chat_service = MagicMock(return_value=chat)
        result = await svc.test_connection("spaces/sp1")
        assert result["connected"] is False
        assert "secret" not in result.get("error", "")

    async def test_execute_operation_send_message(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc.send_message = AsyncMock(return_value={"ok": True, "message_id": "m1"})
        result = await svc.execute_operation("send_message", {"space_id": "s", "text": "hi"})
        assert result["success"] is True

    async def test_execute_operation_get_messages(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc.get_space_messages = AsyncMock(return_value=[_gchat_message()])
        result = await svc.execute_operation("get_space_messages", {"space_id": "s"})
        assert result["success"] is True
        assert result["result"][0]["message_id"] == "spaces/sp1/messages/m1"

    async def test_execute_operation_search(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        svc.search_messages = AsyncMock(return_value={"ok": False, "messages": []})
        result = await svc.execute_operation("search_messages", {"space_id": "s", "query": "q"})
        assert result["success"] is False

    async def test_execute_operation_unknown(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        result = await svc.execute_operation("nope", {})
        assert result["success"] is False
        assert "send_message" in result["details"]["available_operations"]

    async def test_execute_operation_tenant_mismatch(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        result = await svc.execute_operation("send_message", {}, {"tenant_id": "other"})
        assert result["success"] is False
        assert result["error"] == "Tenant mismatch"

    async def test_execute_operation_error_no_leak(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        result = await svc.execute_operation("send_message", {})
        assert result["success"] is False
        assert "space_id" not in result.get("error", "")

    async def test_close(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        redis = _FakeRedis()
        svc.redis_client = redis
        svc.chat_services["u"] = "svc"
        await svc.close()
        assert svc.chat_services == {}

    async def test_close_without_redis(self, monkeypatch):
        svc = _gchat_service(monkeypatch)
        await svc.close()


# ---------------------------------------------------------------------------
# atom_whatsapp_integration
# ---------------------------------------------------------------------------

def _make_whatsapp(monkeypatch, **config):
    monkeypatch.setattr(wai, "httpx", MagicMock())
    defaults = {
        "phone_number_id": "pn_1",
        "business_account_id": "ba_1",
        "access_token": "tok",
        "webhook_url": "https://hook",
        "webhook_secret": "wsec",
        "database": None,
        "cache": None,
    }
    defaults.update(config)
    integ = wai.AtomWhatsAppIntegration(defaults)
    integ.http_session = AsyncMock()
    return integ


class TestWhatsAppModels:
    def test_enums(self):
        assert wai.WhatsAppMessageType.TEXT.value == "text"
        assert wai.WhatsAppChatType.GROUP.value == "group"
        assert wai.WhatsAppCommandType.HELP.value == "help"


class TestWhatsAppInit:
    def test_init_with_config(self, monkeypatch):
        monkeypatch.setattr(wai, "httpx", MagicMock())
        integ = wai.AtomWhatsAppIntegration({"phone_number_id": "p", "access_token": "t"})
        assert integ.whatsapp_config["api_version"] == "v18.0"
        assert integ.whatsapp_config["max_message_length"] == 4000

    def test_module_level_instance(self):
        assert wai.atom_whatsapp_integration.is_initialized is False


class TestWhatsAppInitialize:
    async def test_initialize_no_token(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch, access_token=None)
        assert await integ.initialize() is False

    async def test_initialize_success(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ._verify_api_connection = AsyncMock()
        integ._setup_webhook = AsyncMock()
        integ._setup_enterprise_features = AsyncMock()
        integ._setup_security_and_compliance = AsyncMock()
        integ._setup_automation = AsyncMock()
        integ._setup_monitoring = AsyncMock()
        integ._load_existing_data = AsyncMock()
        assert await integ.initialize() is True
        assert integ.is_initialized is True

    async def test_initialize_webhook_skipped_without_url(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch, webhook_url=None)
        integ._verify_api_connection = AsyncMock()
        integ._setup_webhook = AsyncMock()
        integ._setup_enterprise_features = AsyncMock()
        integ._setup_security_and_compliance = AsyncMock()
        integ._setup_automation = AsyncMock()
        integ._setup_monitoring = AsyncMock()
        integ._load_existing_data = AsyncMock()
        assert await integ.initialize() is True
        integ._setup_webhook.assert_not_awaited()

    async def test_initialize_fails_when_api_verification_fails(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.http_session.get = AsyncMock(return_value=MagicMock(status_code=401))
        assert await integ.initialize() is False
        assert integ.is_initialized is False

    async def test_initialize_exception(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ._verify_api_connection = AsyncMock()
        integ._setup_webhook = AsyncMock(side_effect=RuntimeError("boom"))
        assert await integ.initialize() is False


class TestWhatsAppWorkspacesAndChannels:
    async def test_get_intelligent_workspaces(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        chat = wai.WhatsAppChat(
            chat_id="c1", chat_type=wai.WhatsAppChatType.GROUP, name="Team",
            description="d", profile_picture=None, participants=["u1", "u2"],
            admin_participants=["u1"], permissions={}, security_level="standard",
            is_active=True, member_count=2,
            created_at=datetime.now(timezone.utc), last_message=datetime.now(timezone.utc),
            metadata={},
        )
        integ.active_chats["c1"] = chat
        integ.active_chats["c2"] = wai.WhatsAppChat(
            chat_id="c2", chat_type=wai.WhatsAppChatType.PRIVATE, name=None,
            description=None, profile_picture=None, participants=["u9"],
            admin_participants=[], permissions={}, security_level="standard",
            is_active=True, member_count=1,
            created_at=datetime.now(timezone.utc), last_message=datetime.now(timezone.utc),
            metadata={},
        )
        result = await integ.get_intelligent_workspaces("u1")
        assert len(result) == 1
        assert result[0]["id"] == "c1"
        assert result[0]["is_group"] is True

    async def test_get_intelligent_workspaces_error(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        bad = MagicMock()
        bad.participants = None
        bad.is_active = True
        integ.active_chats["c1"] = bad
        assert await integ.get_intelligent_workspaces("u1") == []

    async def test_get_intelligent_channels(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        chat = wai.WhatsAppChat(
            chat_id="c1", chat_type=wai.WhatsAppChatType.PRIVATE, name="DM",
            description=None, profile_picture=None, participants=["u1", "u2"],
            admin_participants=[], permissions={}, security_level="standard",
            is_active=True, member_count=2,
            created_at=datetime.now(timezone.utc), last_message=datetime.now(timezone.utc),
            metadata={},
        )
        integ.active_chats["c1"] = chat
        result = await integ.get_intelligent_channels("c1", "u1")
        assert len(result) == 1
        assert result[0]["is_private"] is True
        assert await integ.get_intelligent_channels("c1", "nobody") == []
        assert await integ.get_intelligent_channels("missing", "u1") == []

    async def test_get_intelligent_channels_error(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.active_chats = None
        assert await integ.get_intelligent_channels("c1", "u1") == []


class TestWhatsAppMessaging:
    def _resp(self, status_code=200, payload=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = payload
        return resp

    async def test_send_intelligent_message_success(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.enterprise_security = AsyncMock()
        integ.http_session.post = AsyncMock(return_value=self._resp(
            200, {"messages": [{"id": "wamid1"}]}
        ))
        result = await integ.send_intelligent_message("15551234567", "hello", {"k": "v"})
        assert result["success"] is True
        assert result["message_id"] == "wamid1"
        assert result["metadata"] == {"k": "v"}
        integ.enterprise_security.audit_event.assert_awaited_once()
        body = integ.http_session.post.call_args.kwargs["json"]
        assert body["to"] == "15551234567"

    async def test_send_intelligent_message_api_error(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.http_session.post = AsyncMock(return_value=self._resp(
            400, {"error": {"message": "invalid recipient"}}
        ))
        result = await integ.send_intelligent_message("15551234567", "hello")
        assert result["success"] is False
        assert result["error"] == "invalid recipient"

    async def test_send_intelligent_message_exception_no_leak(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.http_session.post = AsyncMock(side_effect=RuntimeError("graph secret"))
        result = await integ.send_intelligent_message("15551234567", "hello")
        assert result["success"] is False
        assert "secret" not in result.get("error", "")

    async def test_send_intelligent_message_no_enterprise_logging(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch, enable_enterprise_features=False)
        integ.http_session.post = AsyncMock(return_value=self._resp(
            200, {"messages": [{"id": "wamid1"}]}
        ))
        result = await integ.send_intelligent_message("15551234567", "hello")
        assert result["success"] is True


class TestWhatsAppSearchHistory:
    async def test_perform_intelligent_search(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        msg = wai.WhatsAppMessage(
            message_id="m1", chat_id="c1", user_id="u1",
            message_type=wai.WhatsAppMessageType.TEXT, content="hello world foo",
            media_path=None, reply_to_message_id=None, forward_from=None,
            edit_date=None, timestamp=datetime.now(timezone.utc), views=1,
            reactions=[], security_flags={}, metadata={},
        )
        integ.message_history["c1"] = [msg]
        integ.message_history["c2"] = [
            wai.WhatsAppMessage(
                message_id="m2", chat_id="c2", user_id="u2",
                message_type=wai.WhatsAppMessageType.TEXT, content="nothing here",
                media_path=None, reply_to_message_id=None, forward_from=None,
                edit_date=None, timestamp=datetime.now(timezone.utc), views=0,
                reactions=[], security_flags={}, metadata={},
            )
        ]
        result = await integ.perform_intelligent_search("hello", "u1")
        assert len(result) == 1
        assert result[0]["id"] == "m1"
        assert result[0]["relevance_score"] == 1.0

    async def test_perform_intelligent_search_workspace_filter(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        msg = wai.WhatsAppMessage(
            message_id="m1", chat_id="c1", user_id="u1",
            message_type=wai.WhatsAppMessageType.TEXT, content="hello",
            media_path=None, reply_to_message_id=None, forward_from=None,
            edit_date=None, timestamp=datetime.now(timezone.utc), views=1,
            reactions=[], security_flags={}, metadata={},
        )
        integ.message_history["c1"] = [msg]
        assert await integ.perform_intelligent_search("hello", "u1", "c2") == []

    async def test_perform_intelligent_search_with_ai(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.ai_service = MagicMock()
        integ.ai_service.process_ai_request = AsyncMock(return_value=MagicMock(
            ok=True, output_data={"results": [{"id": "ai1"}]}
        ))
        monkeypatch.setattr(wai, "AIRequest", dict)
        monkeypatch.setattr(wai, "AITaskType", type("T", (), {"SEARCH_QUERY": "q"}))
        monkeypatch.setattr(wai, "AIModelType", type("T", (), {"GPT_4": "g"}))
        monkeypatch.setattr(wai, "AIServiceType", type("T", (), {"OPENAI": "o"}))
        msg = wai.WhatsAppMessage(
            message_id="m1", chat_id="c1", user_id="u1",
            message_type=wai.WhatsAppMessageType.TEXT, content="hello",
            media_path=None, reply_to_message_id=None, forward_from=None,
            edit_date=None, timestamp=datetime.now(timezone.utc), views=1,
            reactions=[], security_flags={}, metadata={},
        )
        integ.message_history["c1"] = [msg]
        result = await integ.perform_intelligent_search("hello", "u1")
        assert len(result) == 2
        integ.ai_service.process_ai_request.assert_awaited_once()

    async def test_perform_intelligent_search_ai_not_ok(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.ai_service = MagicMock()
        integ.ai_service.process_ai_request = AsyncMock(return_value=MagicMock(
            ok=False, output_data=None
        ))
        monkeypatch.setattr(wai, "AIRequest", dict)
        monkeypatch.setattr(wai, "AITaskType", type("T", (), {"SEARCH_QUERY": "q"}))
        monkeypatch.setattr(wai, "AIModelType", type("T", (), {"GPT_4": "g"}))
        monkeypatch.setattr(wai, "AIServiceType", type("T", (), {"OPENAI": "o"}))
        assert await integ.perform_intelligent_search("hello", "u1") == []

    async def test_perform_intelligent_search_error(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.message_history = None
        assert await integ.perform_intelligent_search("hello", "u1") == []

    async def test_perform_ai_search_no_service(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.ai_service = None
        assert await integ._perform_ai_search("q") == []

    async def test_perform_ai_search_error(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.ai_service = MagicMock()
        integ.ai_service.process_ai_request = AsyncMock(side_effect=RuntimeError("boom"))
        monkeypatch.setattr(wai, "AIRequest", dict)
        monkeypatch.setattr(wai, "AITaskType", type("T", (), {"SEARCH_QUERY": "q"}))
        monkeypatch.setattr(wai, "AIModelType", type("T", (), {"GPT_4": "g"}))
        monkeypatch.setattr(wai, "AIServiceType", type("T", (), {"OPENAI": "o"}))
        assert await integ._perform_ai_search("q") == []

    async def test_get_user_conversation_history(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        msgs = [
            wai.WhatsAppMessage(
                message_id=f"m{i}", chat_id="c1", user_id="u1",
                message_type=wai.WhatsAppMessageType.TEXT, content=f"c{i}",
                media_path=None, reply_to_message_id=None, forward_from=None,
                edit_date=None, timestamp=datetime.now(timezone.utc), views=1,
                reactions=[], security_flags={}, metadata={"k": "v"},
            )
            for i in range(3)
        ]
        integ.message_history["c1"] = msgs
        result = await integ.get_user_conversation_history("u1", "c1", limit=2)
        assert len(result) == 2
        assert result[0]["content"] == "c1"

    async def test_get_user_conversation_history_empty(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        assert await integ.get_user_conversation_history("u1", "c1") == []

    async def test_get_user_conversation_history_error(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.message_history = {"c1": [1]}
        assert await integ.get_user_conversation_history("u1", "c1") == []


class TestWhatsAppStatusAndScoring:
    async def test_get_service_status_active(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.is_initialized = True
        integ._start_time = 1000.0
        result = await integ.get_service_status()
        assert result["status"] == "active"
        assert result["total_messages"] == 0
        assert result["uptime"] >= 0

    async def test_get_service_status_inactive(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        result = await integ.get_service_status()
        assert result["status"] == "inactive"

    async def test_get_service_status_error_no_leak(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.analytics_metrics = None
        result = await integ.get_service_status()
        assert "NoneType" not in result.get("error", "")

    def test_calculate_relevance_score(self, monkeypatch):
        monkeypatch.setattr(wai, "httpx", MagicMock())
        integ = wai.AtomWhatsAppIntegration({"access_token": "t"})
        assert integ._calculate_relevance_score("hello world", "world hello x") == 1.0
        assert integ._calculate_relevance_score("zzz", "hello") == 0.0
        assert integ._calculate_relevance_score("", "hello") == 0.0
        assert integ._calculate_relevance_score("q", None) == 0.0
        integ.http_session = AsyncMock()
        asyncio.run(integ.close())


class TestWhatsAppSetup:
    async def test_verify_api_connection_ok(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.http_session.get = AsyncMock(return_value=MagicMock(status_code=200))
        await integ._verify_api_connection()

    async def test_verify_api_connection_failure_raises(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.http_session.get = AsyncMock(return_value=MagicMock(status_code=401))
        with pytest.raises(RuntimeError):
            await integ._verify_api_connection()

    async def test_verify_api_connection_exception_fails_closed(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.http_session.get = AsyncMock(side_effect=RuntimeError("network down"))
        with pytest.raises(RuntimeError):
            await integ._verify_api_connection()

    async def test_setup_webhook_ok(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.http_session.post = AsyncMock(return_value=MagicMock(status_code=200))
        await integ._setup_webhook()
        body = integ.http_session.post.call_args.kwargs["json"]
        assert body["verify_token"] == "wsec"
        assert body["fields"] == ["messages", "message_reactions"]

    async def test_setup_webhook_failed(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.http_session.post = AsyncMock(return_value=MagicMock(status_code=500))
        await integ._setup_webhook()

    async def test_setup_webhook_exception(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.http_session.post = AsyncMock(side_effect=RuntimeError("boom"))
        await integ._setup_webhook()

    async def test_setup_enterprise_features_missing_services(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.enterprise_security = None
        integ.enterprise_automation = None
        await integ._setup_enterprise_features()

    async def test_setup_enterprise_features_success(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.enterprise_security = MagicMock()
        integ.enterprise_automation = MagicMock()
        integ._setup_security_policies = AsyncMock()
        integ._setup_compliance_rules = AsyncMock()
        integ._setup_automation_triggers = AsyncMock()
        await integ._setup_enterprise_features()
        integ._setup_security_policies.assert_awaited_once()

    async def test_setup_enterprise_features_error(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.enterprise_security = MagicMock()
        integ.enterprise_automation = MagicMock()
        integ._setup_security_policies = AsyncMock(side_effect=RuntimeError("boom"))
        await integ._setup_enterprise_features()

    async def test_setup_security_policies(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        await integ._setup_security_policies()
        assert integ.security_policies["message_content_filter"]["enabled"] is True

    async def test_setup_compliance_rules(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        await integ._setup_compliance_rules()
        assert integ.compliance_rules["message_retention"]["retention_period"] == 365

    async def test_setup_automation_triggers(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        await integ._setup_automation_triggers()
        assert integ.automation_triggers["command_executed"]["enabled"] is True

    async def test_setup_automation_no_service(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.enterprise_automation = None
        await integ._setup_automation()

    async def test_setup_automation_success(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.enterprise_automation = AsyncMock()
        integ.enterprise_automation.create_integration_automation = AsyncMock(return_value={"ok": True})
        await integ._setup_automation()
        integ.enterprise_automation.create_integration_automation.assert_awaited_once()

    async def test_setup_automation_failure(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.enterprise_automation = AsyncMock()
        integ.enterprise_automation.create_integration_automation = AsyncMock(
            return_value={"ok": False, "error": "x"}
        )
        await integ._setup_automation()

    async def test_setup_automation_error(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.enterprise_automation = AsyncMock()
        integ.enterprise_automation.create_integration_automation = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        await integ._setup_automation()

    async def test_setup_security_and_compliance_on(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ._setup_security_monitoring = AsyncMock()
        integ._setup_compliance_monitoring = AsyncMock()
        await integ._setup_security_and_compliance()
        integ._setup_security_monitoring.assert_awaited_once()

    async def test_setup_security_and_compliance_off(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch, enable_enterprise_features=False)
        await integ._setup_security_and_compliance()

    async def test_setup_security_and_compliance_error(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ._setup_security_monitoring = AsyncMock(side_effect=RuntimeError("boom"))
        await integ._setup_security_and_compliance()

    async def test_setup_security_monitoring(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        await integ._setup_security_monitoring()
        assert integ.security_monitoring["message_anomaly_detection"]["enabled"] is True

    async def test_setup_compliance_monitoring(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        await integ._setup_compliance_monitoring()
        assert integ.compliance_monitoring["data_retention_management"]["action"] == "manage"

    async def test_setup_monitoring(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        await integ._setup_monitoring()
        assert integ._start_time > 0
        assert integ.performance_metrics["webhook_response_time"] == 0.0

    async def test_load_existing_data(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        await integ._load_existing_data()

    async def test_log_message_event(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.enterprise_security = AsyncMock()
        await integ._log_message_event("message_sent", "c1", {"user_id": "u1"})
        integ.enterprise_security.audit_event.assert_awaited_once()

    async def test_log_message_event_no_service(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.enterprise_security = None
        await integ._log_message_event("message_sent", "c1", {})

    async def test_log_message_event_error(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.enterprise_security = AsyncMock()
        integ.enterprise_security.audit_event = AsyncMock(side_effect=RuntimeError("boom"))
        await integ._log_message_event("message_sent", "c1", {})

    async def test_close(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        await integ.close()
        integ.http_session.aclose.assert_awaited_once()

    async def test_close_error(self, monkeypatch):
        integ = _make_whatsapp(monkeypatch)
        integ.http_session.aclose = AsyncMock(side_effect=RuntimeError("boom"))
        await integ.close()
