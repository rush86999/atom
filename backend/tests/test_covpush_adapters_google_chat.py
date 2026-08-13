"""
Coverage-push + bug-hunt tests for integrations/atom_google_chat_integration.py.

TDD target (RED first): _setup_cross_platform_handlers references
GoogleChatEventType which is never imported/defined in this module ->
initialize() always fails with NameError when a Google Chat service is
present.
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# google_chat_enhanced_service does a module-level `import google.auth` (and
# related google-* packages). These are optional enterprise deps absent on CI's
# ubuntu runner; skip the whole module cleanly instead of hard-failing
# collection. Placed before the integrations imports below so the skip fires
# before the module-level google import is triggered.
pytest.importorskip("google")

import integrations.atom_google_chat_integration as gchat
from integrations.google_chat_enhanced_service import GoogleChatEventType


class FakeSpace:
    def __init__(self, space_id="sp1", name="spaces/sp1", display_name="Team Room",
                 space_type="SPACE", is_active=True):
        self.space_id = space_id
        self.name = name
        self.display_name = display_name
        self.type = space_type
        self.description = "desc"
        self.space_threading_state = "THREADED"
        self.space_uri = "https://chat.google.com/room/sp1"
        self.space_permission_level = "COLLABORATOR"
        self.threaded = True
        self.is_active = is_active
        self.is_archived = False
        self.member_count = 4
        self.message_count = 10
        self.last_modified_at = "2026-01-01T00:00:00Z"
        self.single_user_bot_dm = False
        self.external_user_permission = "UNKNOWN"
        self.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)


class FakeMessage:
    def __init__(self, message_id="m1", text="hello", space_id="sp1"):
        self.message_id = message_id
        self.text = text
        self.formatted_text = "<b>hello</b>"
        self.user_id = "u1"
        self.user_name = "Alice"
        self.user_email = "a@x.com"
        self.user_avatar = "av"
        self.timestamp = "2026-01-01T10:00:00Z"
        self.thread_id = None
        self.reply_to_id = None
        self.message_type = "MESSAGE"
        self.is_edited = False
        self.edit_timestamp = None
        self.reactions = []
        self.attachment = []
        self.annotations = []
        self.gu_id = None
        self.sender_type = "HUMAN"
        self.space_threading_state = "THREADED"
        self.thread_name = None
        self.thread_id_created_by = None
        self.quoted_message_id = None
        self.card_v2 = []
        self.slash_command = None
        self.action_response = None
        self.arguments = None
        self.space_id = space_id
        self.integration_data = {}


def _gchat(**cfg):
    return gchat.AtomGoogleChatIntegration(cfg)


@pytest.fixture(autouse=True)
def _restore_gchat_module_state():
    attrs = {k: getattr(gchat, k) for k in (
        "google_chat_enhanced_service", "google_chat_analytics_engine",
        "UnifiedWorkspace", "GoogleChatEventType")}
    yield
    for k, v in attrs.items():
        setattr(gchat, k, v)


class TestGoogleChatBasics:
    def test_init(self):
        svc = _gchat()
        assert svc.is_initialized is False
        assert svc.active_spaces == [] and svc.unified_messages == []
        assert svc.communication_channels == []

    def test_init_no_service(self):
        svc = _gchat()
        svc.google_chat_service = None
        assert svc.google_chat_service is None

    def test_init_with_db(self):
        db = MagicMock()
        svc = _gchat(database=db)
        assert svc.workspace_sync is not None

    def test_initialize_missing_services(self):
        svc = _gchat()
        assert asyncio.run(svc.initialize()) is False

    def test_initialize_success(self, monkeypatch):
        fake_service = MagicMock()
        fake_service.event_handlers = {}
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake_service)
        monkeypatch.setattr(gchat, "GoogleChatEventType", GoogleChatEventType)
        svc = _gchat(atom_memory_service=MagicMock(), atom_search_service=MagicMock())
        svc._start_integration_workers = AsyncMock()
        svc._initialize_unified_data = AsyncMock()
        svc._setup_cross_platform_handlers = AsyncMock()
        assert asyncio.run(svc.initialize()) is True
        assert svc.is_initialized is True

    def test_initialize_exception(self, monkeypatch):
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", MagicMock())
        svc = _gchat(atom_memory_service=MagicMock(),
                     atom_search_service=MagicMock())
        svc._start_integration_workers = AsyncMock(side_effect=Exception("boom"))
        assert asyncio.run(svc.initialize()) is False

    def test_get_service_status_inactive(self):
        svc = _gchat()
        svc.google_chat_service = None
        status = asyncio.run(svc.get_service_status())
        assert status["status"] == "inactive"
        assert status["service_name"] == "Google Chat"
        assert status["active_spaces_count"] == 0

    def test_get_service_status_active(self, monkeypatch):
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", MagicMock())
        svc = _gchat()
        svc.is_initialized = True
        svc.active_spaces = [FakeSpace()]
        status = asyncio.run(svc.get_service_status())
        assert status["status"] == "active"
        assert status["active_spaces_count"] == 1
        assert status["has_analytics"] is False


class TestGoogleChatUnified:
    def test_get_unified_workspaces(self, monkeypatch):
        fake = MagicMock()
        fake.get_spaces = AsyncMock(return_value=[FakeSpace(), FakeSpace("sp2")])
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        ws = asyncio.run(svc.get_unified_workspaces("u1"))
        assert len(ws) == 2
        assert ws[0]["id"] == "google_chat_sp1"
        assert ws[0]["type"] == "google_chat"
        assert ws[0]["status"] == "connected"
        assert ws[0]["capabilities"]["messaging"] is True
        assert svc.active_spaces[0].space_id == "sp1"

    def test_get_unified_workspaces_disconnected(self, monkeypatch):
        fake = MagicMock()
        fake.get_spaces = AsyncMock(return_value=[FakeSpace(is_active=False)])
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        ws = asyncio.run(svc.get_unified_workspaces("u1"))
        assert ws[0]["status"] == "disconnected"

    def test_get_unified_workspaces_error(self, monkeypatch):
        fake = MagicMock()
        fake.get_spaces = AsyncMock(side_effect=Exception("boom"))
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        assert asyncio.run(svc.get_unified_workspaces("u1")) == []

    def test_get_unified_channels(self):
        svc = _gchat()
        svc.active_spaces = [FakeSpace()]
        ch = asyncio.run(svc.get_unified_channels("google_chat_sp1"))
        assert len(ch) == 1
        assert ch[0]["id"] == "google_chat_sp1"
        assert ch[0]["status"] == "active"
        assert ch[0]["is_private"] is False
        assert len(svc.communication_channels) == 1

    def test_get_unified_channels_archived(self):
        svc = _gchat()
        space = FakeSpace()
        space.is_archived = True
        svc.active_spaces = [space]
        ch = asyncio.run(svc.get_unified_channels("google_chat_sp1"))
        assert ch[0]["status"] == "archived"

    def test_get_unified_channels_wrong_prefix(self):
        svc = _gchat()
        assert asyncio.run(svc.get_unified_channels("slack_ws")) == []

    def test_get_unified_channels_space_missing(self):
        svc = _gchat()
        assert asyncio.run(svc.get_unified_channels("google_chat_nope")) == []

    def test_send_unified_message_success(self, monkeypatch):
        fake = MagicMock()
        fake.send_message = AsyncMock(return_value={"ok": True, "message_id": "m1"})
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        svc.atom_memory = MagicMock()
        svc.atom_memory.store = AsyncMock()
        svc.atom_search = MagicMock()
        svc.atom_search.index = AsyncMock()
        svc.atom_workflow = MagicMock()
        svc.atom_workflow.trigger_workflows = AsyncMock()
        result = asyncio.run(svc.send_unified_message("w", "google_chat_sp1", "hi",
                                                      {"thread_id": "t"}))
        assert result["ok"] is True
        assert result["message_id"] == "m1"
        assert result["platform"] == "Google Chat"
        fake.send_message.assert_awaited_once()
        assert fake.send_message.call_args[1]["thread_id"] == "t"
        svc.atom_memory.store.assert_awaited_once()
        svc.atom_search.index.assert_awaited_once()
        svc.atom_workflow.trigger_workflows.assert_awaited_once()

    def test_send_unified_message_service_failure(self, monkeypatch):
        fake = MagicMock()
        fake.send_message = AsyncMock(return_value={"ok": False, "error": "nope"})
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        result = asyncio.run(svc.send_unified_message("w", "google_chat_sp1", "hi"))
        assert result["ok"] is False

    def test_send_unified_message_unsupported(self):
        svc = _gchat()
        result = asyncio.run(svc.send_unified_message("w", "slack_c1", "hi"))
        assert result["ok"] is False
        assert result["error"] == "Unsupported platform"

    def test_send_unified_message_exception(self):
        svc = _gchat()
        result = asyncio.run(svc.send_unified_message("w", "google_chat_sp1", "hi"))
        assert result["ok"] is False

    def test_get_unified_messages(self, monkeypatch):
        fake = MagicMock()
        fake.get_space_messages = AsyncMock(return_value=[FakeMessage()])
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        msgs = asyncio.run(svc.get_unified_messages("w", "google_chat_sp1"))
        assert len(msgs) == 1
        assert msgs[0]["id"] == "google_chat_m1"
        assert msgs[0]["platform"] == "Google Chat"
        assert msgs[0]["reactions"] == []
        assert msgs[0]["is_edited"] is False
        assert msgs[0]["metadata"]["is_bot_message"] is False
        assert len(svc.unified_messages) == 1

    def test_get_unified_messages_wrong_platform(self):
        svc = _gchat()
        assert asyncio.run(svc.get_unified_messages("w", "slack_c1")) == []

    def test_get_unified_messages_error(self, monkeypatch):
        fake = MagicMock()
        fake.get_space_messages = AsyncMock(side_effect=Exception("boom"))
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        assert asyncio.run(svc.get_unified_messages("w", "google_chat_sp1")) == []

    def test_unified_search(self, monkeypatch):
        fake = MagicMock()
        fake.search_messages = AsyncMock(
            return_value={"ok": True, "messages": [FakeMessage()]})
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        results = asyncio.run(svc.unified_search("hello", channel_id="google_chat_sp1"))
        assert len(results) == 1
        assert results[0]["title"] == "Message from Alice"
        assert results[0]["relevance_score"] == 1.0

    def test_unified_search_not_ok(self, monkeypatch):
        fake = MagicMock()
        fake.search_messages = AsyncMock(return_value={"ok": False})
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        assert asyncio.run(svc.unified_search("hi", channel_id="google_chat_sp1")) == []

    def test_unified_search_non_google(self):
        svc = _gchat()
        assert asyncio.run(svc.unified_search("hi", channel_id="slack_c1")) == []

    def test_unified_search_error(self, monkeypatch):
        fake = MagicMock()
        fake.search_messages = AsyncMock(side_effect=Exception("boom"))
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        assert asyncio.run(svc.unified_search("hi", channel_id="google_chat_sp1")) == []

    def test_create_unified_workflow_google_chat(self):
        svc = _gchat()
        data = {"triggers": [{"platform": "slack", "event": "x"}],
                "actions": [{"platform": "google_chat", "action": "send"}]}
        result = asyncio.run(svc.create_unified_workflow(data))
        assert result["ok"] is True
        assert result["platform"] == "google_chat"
        assert result["workflow_id"].startswith("gc_workflow_")

    def test_create_unified_workflow_trigger_google(self):
        svc = _gchat()
        data = {"triggers": [{"platform": "x", "event": "google_chat_message"}]}
        result = asyncio.run(svc.create_unified_workflow(data))
        assert result["ok"] is True

    def test_create_unified_workflow_standard(self):
        svc = _gchat()
        svc.atom_workflow = MagicMock()
        svc.atom_workflow.create_workflow = AsyncMock(return_value={"ok": True})
        result = asyncio.run(svc.create_unified_workflow(
            {"triggers": [{"platform": "slack", "event": "message"}],
             "actions": [{"platform": "slack", "action": "post"}]}))
        assert result["ok"] is True
        svc.atom_workflow.create_workflow.assert_awaited_once()

    def test_create_unified_workflow_no_service(self):
        svc = _gchat()
        result = asyncio.run(svc.create_unified_workflow({"triggers": [], "actions": []}))
        assert result["ok"] is False

    def test_create_unified_workflow_error(self):
        svc = _gchat()
        svc.atom_workflow = MagicMock()
        svc.atom_workflow.create_workflow = AsyncMock(side_effect=Exception("boom"))
        result = asyncio.run(svc.create_unified_workflow({"triggers": [], "actions": []}))
        assert result["ok"] is False

    def test_get_unified_analytics(self, monkeypatch):
        analytics = MagicMock()
        analytics.get_analytics = AsyncMock(return_value=[
            SimpleNamespace(timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                            value=5, dimensions={}, metadata={})])
        monkeypatch.setattr(gchat, "google_chat_analytics_engine", analytics)
        svc = _gchat()
        result = asyncio.run(svc.get_unified_analytics(
            "message_volume", "today", "google_chat_sp1"))
        assert result["platform"] == "Google Chat"
        assert result["total_points"] == 1
        assert result["data_points"][0]["value"] == 5

    def test_get_unified_analytics_no_engine(self):
        svc = _gchat()
        result = asyncio.run(svc.get_unified_analytics("message_volume", "today"))
        assert result["total_points"] == 0

    def test_get_unified_analytics_error(self):
        svc = _gchat()
        svc.google_chat_analytics = MagicMock()
        svc.google_chat_analytics.get_analytics = AsyncMock(side_effect=Exception("boom"))
        result = asyncio.run(svc.get_unified_analytics("x", "y"))
        assert result["ok"] is False


class TestGoogleChatHelpers:
    def test_get_space_by_id(self):
        svc = _gchat()
        svc.active_spaces = [FakeSpace("sp1")]
        assert svc._get_space_by_id("sp1").space_id == "sp1"
        assert svc._get_space_by_id("nope") is None

    def test_convert_reactions(self):
        svc = _gchat()
        out = svc._convert_google_chat_reactions(
            [{"emoji": "thumbs_up", "count": 3, "user_ids": ["u1"]},
             {"emoji": "heart"}])
        assert out[0]["count"] == 3
        assert out[1]["user_ids"] == []

    def test_convert_attachments(self):
        svc = _gchat()
        out = svc._convert_google_chat_attachments([{
            "name": "files/1", "title": "doc", "contentType": "application/pdf",
            "downloadUri": "http://dl", "thumbnailUri": "http://th"}])
        assert out[0]["id"] == "files/1"
        assert out[0]["content_type"] == "application/pdf"

    def test_convert_mentions(self):
        svc = _gchat()
        out = svc._convert_google_chat_mentions([
            {"type": "user_mention", "userMention": {"name": "u1", "displayName": "Al"}},
            {"type": "other"}])
        assert len(out) == 1
        assert out[0]["name"] == "Al"
        assert out[0]["platform"] == "Google Chat"

    def test_convert_files(self):
        svc = _gchat()
        out = svc._convert_google_chat_files([
            {"contentType": "image/png", "name": "f1", "title": "pic", "size": 5},
            {"contentType": "text/plain", "name": "f2"}])
        assert len(out) == 1
        assert out[0]["type"] == "google_chat_file"
        assert out[0]["url"] is None

    def test_generate_search_highlights(self):
        svc = _gchat()
        highlights = svc._generate_search_highlights(
            "the quick brown fox jumps over the lazy dog", "fox")
        assert any("fox" in h for h in highlights)

    def test_store_message_in_memory(self):
        svc = _gchat()
        svc.atom_memory = MagicMock()
        svc.atom_memory.store = AsyncMock()
        asyncio.run(svc._store_message_in_memory({"message_id": "m1", "text": "hi"},
                                                 "google_chat", {"k": 1}))
        svc.atom_memory.store.assert_awaited_once()
        data = svc.atom_memory.store.call_args[0][0]
        assert data["type"] == "unified_message"
        assert data["options"] == {"k": 1}
        asyncio.run(_gchat()._store_message_in_memory({}, "google_chat"))

    def test_store_message_in_memory_error(self):
        svc = _gchat()
        svc.atom_memory = MagicMock()
        svc.atom_memory.store = AsyncMock(side_effect=Exception("boom"))
        asyncio.run(svc._store_message_in_memory({"message_id": "m1"}, "g"))

    def test_index_message_in_search(self):
        svc = _gchat()
        svc.atom_search = MagicMock()
        svc.atom_search.index = AsyncMock()
        asyncio.run(svc._index_message_in_search({"message_id": "m1", "text": "hi"},
                                                 "google_chat"))
        svc.atom_search.index.assert_awaited_once()
        data = svc.atom_search.index.call_args[0][0]
        assert data["id"] == "google_chat_m1"
        asyncio.run(_gchat()._index_message_in_search({}, "google_chat"))

    def test_index_message_in_search_error(self):
        svc = _gchat()
        svc.atom_search = MagicMock()
        svc.atom_search.index = AsyncMock(side_effect=Exception("boom"))
        asyncio.run(svc._index_message_in_search({"message_id": "m1"}, "g"))

    def test_trigger_workflows(self):
        svc = _gchat()
        svc.atom_workflow = MagicMock()
        svc.atom_workflow.trigger_workflows = AsyncMock()
        asyncio.run(svc._trigger_workflows({}, "ev"))
        svc.atom_workflow.trigger_workflows.assert_awaited_once()
        asyncio.run(_gchat()._trigger_workflows({}, "ev"))

    def test_trigger_workflows_error(self):
        svc = _gchat()
        svc.atom_workflow = MagicMock()
        svc.atom_workflow.trigger_workflows = AsyncMock(side_effect=Exception("boom"))
        asyncio.run(svc._trigger_workflows({}, "ev"))

    def test_start_integration_workers(self):
        svc = _gchat()
        created = []
        svc._google_chat_message_ingestion_worker = AsyncMock()
        svc._google_chat_event_processing_worker = AsyncMock()
        svc._unified_search_indexing_worker = AsyncMock()
        with patch.object(asyncio, "create_task", side_effect=lambda c: created.append(c)):
            asyncio.run(svc._start_integration_workers())
        assert len(created) == 3

    def test_initialize_unified_data(self):
        svc = _gchat()
        svc.atom_memory = MagicMock()
        svc.atom_memory.query = AsyncMock(return_value=[])
        asyncio.run(svc._initialize_unified_data())
        assert svc.atom_memory.query.await_count == 3
        asyncio.run(_gchat()._initialize_unified_data())

    def test_initialize_unified_data_error(self):
        svc = _gchat()
        svc.atom_memory = MagicMock()
        svc.atom_memory.query = AsyncMock(side_effect=Exception("boom"))
        asyncio.run(svc._initialize_unified_data())

    def test_cross_platform_message_handler(self):
        svc = _gchat()
        svc.atom_memory = MagicMock()
        svc.atom_memory.store = AsyncMock()
        asyncio.run(svc._handle_google_chat_message_cross_platform({"message_id": "m1"}))
        svc2 = _gchat()
        svc2.atom_memory = MagicMock()
        svc2.atom_memory.store = AsyncMock(side_effect=Exception("boom"))
        asyncio.run(svc2._handle_google_chat_message_cross_platform({}))

    def test_cross_platform_space_event(self):
        svc = _gchat()
        svc._update_workspace_cross_platform = AsyncMock()
        svc._trigger_workflows = AsyncMock()
        asyncio.run(svc._handle_google_chat_space_event_cross_platform({}))
        svc._update_workspace_cross_platform.assert_awaited_once()

    def test_update_workspace_cross_platform_no_sync(self):
        svc = _gchat()
        asyncio.run(svc._update_workspace_cross_platform({}, "google_chat"))

    def test_update_workspace_cross_platform_success(self):
        svc = _gchat()
        svc.workspace_sync = MagicMock()
        svc.workspace_sync.propagate_change = AsyncMock()
        unified = MagicMock()
        unified.id = "uw1"
        svc._get_or_create_unified_workspace = AsyncMock(return_value=unified)
        event = {"space": {"name": "spaces/sp1"}, "type": "SPACE_UPDATED"}
        asyncio.run(svc._update_workspace_cross_platform(event, "google_chat"))
        svc.workspace_sync.propagate_change.assert_awaited_once()
        change = svc.workspace_sync.propagate_change.call_args[1]
        assert change["change_type"] == "name_change"
        assert change["source_platform"] == "google_chat"

    def test_update_workspace_cross_platform_member_events(self):
        svc = _gchat()
        svc.workspace_sync = MagicMock()
        svc.workspace_sync.propagate_change = AsyncMock()
        unified = MagicMock()
        unified.id = "uw1"
        svc._get_or_create_unified_workspace = AsyncMock(return_value=unified)
        for ev_type, expected in (("MEMBER_ADDED", "member_add"),
                                  ("MEMBER_REMOVED", "member_remove"),
                                  ("SETTINGS_UPDATED", "settings_change"),
                                  ("OTHER", "settings_change")):
            svc.workspace_sync.propagate_change.reset_mock()
            asyncio.run(svc._update_workspace_cross_platform(
                {"space": {"name": "spaces/sp1"}, "type": ev_type}, "google_chat"))
            assert svc.workspace_sync.propagate_change.call_args[1]["change_type"] == expected

    def test_update_workspace_cross_platform_create_failure(self):
        svc = _gchat()
        svc.workspace_sync = MagicMock()
        svc._get_or_create_unified_workspace = AsyncMock(return_value=None)
        asyncio.run(svc._update_workspace_cross_platform(
            {"space": {"name": "spaces/sp1"}, "type": "RENAME_SPACE"}, "google_chat"))

    def test_update_workspace_cross_platform_error(self):
        svc = _gchat()
        svc.workspace_sync = MagicMock()
        svc.workspace_sync.propagate_change = AsyncMock(side_effect=Exception("boom"))
        svc._get_or_create_unified_workspace = AsyncMock(
            return_value=SimpleNamespace(id="uw1"))
        asyncio.run(svc._update_workspace_cross_platform(
            {"space": {"name": "spaces/sp1"}, "type": "SPACE_UPDATED"}, "google_chat"))

    def test_get_or_create_unified_workspace_existing(self):
        svc = _gchat()
        db = MagicMock()
        existing = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = existing
        svc.db = db
        with patch.object(gchat, "UnifiedWorkspace", MagicMock()):
            result = asyncio.run(svc._get_or_create_unified_workspace("sp1", "Room"))
        assert result is existing

    def test_get_or_create_unified_workspace_create(self):
        from sqlalchemy import Column, String, create_engine
        from sqlalchemy.orm import declarative_base, sessionmaker

        Base = declarative_base()

        class UWS(Base):
            __tablename__ = "unified_workspaces"
            id = Column(String, primary_key=True)
            google_chat_space_id = Column(String)

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        svc = _gchat(database=session)
        svc.workspace_sync = MagicMock()
        created = MagicMock()
        created.id = "uw1"
        svc.workspace_sync.create_unified_workspace.return_value = created
        with patch.object(gchat, "UnifiedWorkspace", UWS):
            result = asyncio.run(svc._get_or_create_unified_workspace("sp1", "Room"))
        assert result.id == "uw1"
        svc.workspace_sync.create_unified_workspace.assert_called_once()

    def test_get_or_create_unified_workspace_error(self):
        svc = _gchat()
        svc.db = MagicMock()
        svc.db.query.side_effect = Exception("boom")
        with patch.object(gchat, "UnifiedWorkspace", MagicMock()):
            result = asyncio.run(svc._get_or_create_unified_workspace("sp1", "Room"))
        assert result is None


class TestGoogleChatOAuth:
    def test_get_oauth_url(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CHAT_CLIENT_ID", "cid")
        svc = _gchat()
        url = asyncio.run(svc.get_oauth_url("http://x/cb", state="st"))
        assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth")
        assert "client_id=cid" in url
        assert "state=st" in url
        assert "access_type=offline" in url

    def test_get_oauth_url_missing_client(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_CHAT_CLIENT_ID", raising=False)
        svc = _gchat()
        with pytest.raises(ValueError):
            asyncio.run(svc.get_oauth_url("http://x/cb"))

    def test_handle_oauth_callback_success(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CHAT_CLIENT_ID", "cid")
        monkeypatch.setenv("GOOGLE_CHAT_CLIENT_SECRET", "cs")
        svc = _gchat()

        class FakeClient:
            async def __aenter__(self):
                self.post = AsyncMock(return_value=httpx.Response(200, request=httpx.Request("POST", "http://x"), json={
                    "access_token": "at", "refresh_token": "rt", "expires_in": 3600}))
                return self

            async def __aexit__(self, *a):
                return False

        monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: FakeClient())
        result = asyncio.run(svc.handle_oauth_callback("code", "st"))
        assert result["success"] is True
        assert result["access_token"] == "at"
        assert result["expires_in"] == 3600

    def test_handle_oauth_callback_missing_state(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CHAT_CLIENT_ID", "cid")
        monkeypatch.setenv("GOOGLE_CHAT_CLIENT_SECRET", "cs")
        svc = _gchat()
        result = asyncio.run(svc.handle_oauth_callback("code"))
        assert result["success"] is False

    def test_handle_oauth_callback_missing_creds(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_CHAT_CLIENT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_CHAT_CLIENT_SECRET", raising=False)
        svc = _gchat()
        result = asyncio.run(svc.handle_oauth_callback("code"))
        assert result["success"] is False

    def test_handle_oauth_callback_http_error(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CHAT_CLIENT_ID", "cid")
        monkeypatch.setenv("GOOGLE_CHAT_CLIENT_SECRET", "cs")
        svc = _gchat()

        class FakeClient:
            async def __aenter__(self):
                self.post = AsyncMock(side_effect=httpx.HTTPStatusError(
                    "400", request=httpx.Request("POST", "http://x"),
                    response=httpx.Response(400)))
                return self

            async def __aexit__(self, *a):
                return False

        monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: FakeClient())
        result = asyncio.run(svc.handle_oauth_callback("code", "st"))
        assert result["success"] is False

    def test_refresh_access_token_success(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CHAT_CLIENT_ID", "cid")
        monkeypatch.setenv("GOOGLE_CHAT_CLIENT_SECRET", "cs")
        svc = _gchat()

        class FakeClient:
            async def __aenter__(self):
                self.post = AsyncMock(return_value=httpx.Response(200, request=httpx.Request("POST", "http://x"), json={
                    "access_token": "at2"}))
                return self

            async def __aexit__(self, *a):
                return False

        monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: FakeClient())
        result = asyncio.run(svc.refresh_access_token("rt"))
        assert result["success"] is True
        assert result["access_token"] == "at2"
        assert result["refresh_token"] == "rt"

    def test_refresh_access_token_missing_creds(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_CHAT_CLIENT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_CHAT_CLIENT_SECRET", raising=False)
        svc = _gchat()
        assert asyncio.run(svc.refresh_access_token("rt"))["success"] is False

    def test_refresh_access_token_http_error(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CHAT_CLIENT_ID", "cid")
        monkeypatch.setenv("GOOGLE_CHAT_CLIENT_SECRET", "cs")
        svc = _gchat()

        class FakeClient:
            async def __aenter__(self):
                self.post = AsyncMock(side_effect=httpx.HTTPStatusError(
                    "400", request=httpx.Request("POST", "http://x"),
                    response=httpx.Response(400)))
                return self

            async def __aexit__(self, *a):
                return False

        monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: FakeClient())
        assert asyncio.run(svc.refresh_access_token("rt"))["success"] is False


class TestGoogleChatActions:
    def test_send_card_with_service(self, monkeypatch):
        fake = MagicMock()
        fake.send_message = AsyncMock(return_value={"ok": True, "message_id": "m1"})
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        result = asyncio.run(svc.send_card(
            "spaces/sp1", message="hi",
            card={"cardHeader": {"title": "T"}, "sections": []},
            header={"title": "H"}, sections=[{"widgets": []}],
            widgets=[{"textParagraph": {}}]))
        assert result["success"] is True
        assert result["message_name"] == "m1"
        assert fake.send_message.call_args[1]["message_format"] == "CARD"

    def test_send_card_multiple(self, monkeypatch):
        fake = MagicMock()
        fake.send_message = AsyncMock(return_value={"ok": True, "message_id": "m1"})
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        result = asyncio.run(svc.send_card("spaces/sp1", cards=[{"x": 1}, {"y": 2}],
                                           card={"z": 3}))
        assert result["success"] is True
        payload = fake.send_message.call_args[1]["card_v2"][0]
        assert payload == {"z": 3}

    def test_send_card_service_failure(self, monkeypatch):
        fake = MagicMock()
        fake.send_message = AsyncMock(return_value={"ok": False, "error": "e"})
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        result = asyncio.run(svc.send_card("spaces/sp1", "hi"))
        assert result["success"] is False
        assert result["error"] == "e"

    def test_send_card_no_service(self):
        svc = _gchat()
        svc.google_chat_service = None
        result = asyncio.run(svc.send_card("spaces/sp1", "hi"))
        assert result["success"] is True
        assert "simulated" in result["note"]

    def test_update_card(self, monkeypatch):
        fake = MagicMock()
        fake.update_message = AsyncMock(return_value={"ok": True})
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        result = asyncio.run(svc.update_card("spaces/sp1", "m1"))
        assert result["success"] is True

    def test_update_card_error(self, monkeypatch):
        fake = MagicMock()
        fake.update_message = AsyncMock(side_effect=Exception("boom"))
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        result = asyncio.run(svc.update_card("spaces/sp1", "m1"))
        assert result["success"] is False

    def test_update_card_no_service(self):
        svc = _gchat()
        svc.google_chat_service = None
        result = asyncio.run(svc.update_card("spaces/sp1", "m1"))
        assert result["success"] is True

    def test_open_dialog(self, monkeypatch):
        fake = MagicMock()
        fake.open_dialog = AsyncMock(return_value={"ok": True})
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        result = asyncio.run(svc.open_dialog("spaces/sp1", {"body": {}}))
        assert result["success"] is True
        assert result["dialog"] == {"body": {}}

    def test_open_dialog_error(self, monkeypatch):
        fake = MagicMock()
        fake.open_dialog = AsyncMock(side_effect=Exception("boom"))
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        result = asyncio.run(svc.open_dialog("spaces/sp1", {}))
        assert result["success"] is False

    def test_open_dialog_no_service(self):
        svc = _gchat()
        svc.google_chat_service = None
        result = asyncio.run(svc.open_dialog("spaces/sp1", {"body": {}}))
        assert result["success"] is True

    def test_create_space(self, monkeypatch):
        fake = MagicMock()
        fake.create_space = AsyncMock(return_value={"ok": True, "space_name": "spaces/sp1"})
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        with patch.object(svc, "add_space_members", AsyncMock()) as add:
            result = asyncio.run(svc.create_space("Room", members=["a@x.com", "b@x.com"]))
        assert result["success"] is True
        assert result["members_added"] == 2
        assert add.await_count == 2

    def test_create_space_failure(self, monkeypatch):
        fake = MagicMock()
        fake.create_space = AsyncMock(return_value={"ok": False, "error": "e"})
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        result = asyncio.run(svc.create_space("Room"))
        assert result["success"] is False

    def test_create_space_no_service(self):
        svc = _gchat()
        svc.google_chat_service = None
        result = asyncio.run(svc.create_space("Room"))
        assert result["success"] is True
        assert result["space_name"].startswith("spaces/")

    def test_list_spaces(self, monkeypatch):
        fake = MagicMock()
        fake.get_spaces = AsyncMock(return_value={"ok": True, "spaces": [
            {"space_name": "spaces/sp1", "display_name": "Room", "type": "SPACE"}]})
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        result = asyncio.run(svc.list_spaces())
        assert result["success"] is True
        assert result["count"] == 1

    def test_list_spaces_not_ok(self, monkeypatch):
        fake = MagicMock()
        fake.get_spaces = AsyncMock(return_value={"ok": False})
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        result = asyncio.run(svc.list_spaces())
        assert result["spaces"] == []

    def test_list_spaces_no_service(self):
        svc = _gchat()
        svc.google_chat_service = None
        result = asyncio.run(svc.list_spaces())
        assert result["spaces"] == []

    def test_list_spaces_error(self, monkeypatch):
        fake = MagicMock()
        fake.get_spaces = AsyncMock(side_effect=Exception("boom"))
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        result = asyncio.run(svc.list_spaces())
        assert result["success"] is False

    def test_get_space_info(self, monkeypatch):
        fake = MagicMock()
        fake.get_space = AsyncMock(return_value={"ok": True, "space": {
            "space_name": "spaces/sp1", "display_name": "Room"}})
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        result = asyncio.run(svc.get_space_info("spaces/sp1"))
        assert result["success"] is True
        assert result["name"] == "spaces/sp1"

    def test_get_space_info_not_ok(self, monkeypatch):
        fake = MagicMock()
        fake.get_space = AsyncMock(return_value={"ok": False})
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        result = asyncio.run(svc.get_space_info("spaces/sp1"))
        assert result["success"] is True
        assert result["name"] == "spaces/sp1"

    def test_get_space_info_no_service(self):
        svc = _gchat()
        svc.google_chat_service = None
        result = asyncio.run(svc.get_space_info("spaces/sp1"))
        assert result["name"] == "spaces/sp1"

    def test_get_space_info_error(self, monkeypatch):
        fake = MagicMock()
        fake.get_space = AsyncMock(side_effect=Exception("boom"))
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        result = asyncio.run(svc.get_space_info("spaces/sp1"))
        assert result["success"] is False

    def test_add_remove_space_members(self, monkeypatch):
        fake = MagicMock()
        fake.add_member = AsyncMock(side_effect=[{"ok": True}, {"ok": False}])
        fake.remove_member = AsyncMock(return_value={"ok": True})
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        result = asyncio.run(svc.add_space_members("spaces/sp1", ["a@x.com", "b@x.com"]))
        assert result["added_count"] == 1
        assert result["total_requested"] == 2
        result2 = asyncio.run(svc.remove_space_members("spaces/sp1", ["a@x.com"]))
        assert result2["removed_count"] == 1

    def test_add_space_members_error(self):
        svc = _gchat()
        svc.google_chat_service = MagicMock()
        svc.google_chat_service.add_member = AsyncMock(side_effect=Exception("boom"))
        result = asyncio.run(svc.add_space_members("spaces/sp1", ["a"]))
        assert result["success"] is False

    def test_remove_space_members_error(self):
        svc = _gchat()
        svc.google_chat_service = MagicMock()
        svc.google_chat_service.remove_member = AsyncMock(side_effect=Exception("boom"))
        result = asyncio.run(svc.remove_space_members("spaces/sp1", ["a"]))
        assert result["success"] is False

    def test_set_space_webhook(self):
        svc = _gchat()
        result = asyncio.run(svc.set_space_webhook("spaces/sp1", "http://wh", state="s"))
        assert result["success"] is True
        assert result["state"] == "s"
        assert result["webhook_url"] == "http://wh"

    def test_send_message_with_service(self, monkeypatch):
        fake = MagicMock()
        fake.send_message = AsyncMock(return_value={"ok": True, "message_id": "m1"})
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        result = asyncio.run(svc.send_message("spaces/sp1", "hi", thread_key="t"))
        assert result["success"] is True
        assert result["message_name"] == "m1"
        assert fake.send_message.call_args[1]["thread_id"] == "t"

    def test_send_message_service_failure(self, monkeypatch):
        fake = MagicMock()
        fake.send_message = AsyncMock(return_value={"ok": False, "error": "e"})
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        result = asyncio.run(svc.send_message("spaces/sp1", "hi"))
        assert result["success"] is False

    def test_send_message_no_service(self):
        svc = _gchat()
        svc.google_chat_service = None
        result = asyncio.run(svc.send_message("spaces/sp1", "hi"))
        assert result["success"] is True

    def test_upload_file_path(self, monkeypatch, tmp_path):
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF-1.4 test")
        fake = MagicMock()
        fake.upload_file = AsyncMock(return_value={"ok": True, "file_name": "files/1"})
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        result = asyncio.run(svc.upload_file("spaces/sp1", file_path=str(f)))
        assert result["success"] is True
        assert result["filename"] == "doc.pdf"
        assert result["mime_type"] == "application/pdf"

    def test_upload_file_content(self, monkeypatch):
        fake = MagicMock()
        fake.upload_file = AsyncMock(return_value={"ok": True, "file_name": "files/1"})
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        result = asyncio.run(svc.upload_file("spaces/sp1", content="data",
                                             filename="a.txt", mime_type="text/plain"))
        assert result["success"] is True

    def test_upload_file_missing_args(self):
        svc = _gchat()
        result = asyncio.run(svc.upload_file("spaces/sp1"))
        assert result["success"] is False

    def test_upload_file_missing_file(self):
        svc = _gchat()
        result = asyncio.run(svc.upload_file("spaces/sp1", file_path="/nope/x.txt"))
        assert result["success"] is False

    def test_upload_file_service_failure(self, monkeypatch):
        fake = MagicMock()
        fake.upload_file = AsyncMock(return_value={"ok": False, "error": "e"})
        monkeypatch.setattr(gchat, "google_chat_enhanced_service", fake)
        svc = _gchat()
        result = asyncio.run(svc.upload_file("spaces/sp1", content="x", filename="a.bin",
                                             mime_type="application/octet-stream"))
        assert result["success"] is False

    def test_upload_file_no_service(self):
        svc = _gchat()
        svc.google_chat_service = None
        result = asyncio.run(svc.upload_file("spaces/sp1", content="x", filename="a.txt"))
        assert result["success"] is True
