# -*- coding: utf-8 -*-
"""Coverage wave 78 — core/communication_service. Universal messaging
dispatch: adapter registry, incoming message pipeline (identity resolution,
slash commands, HITL interactions, @agent routing, background agent
processing), outbound send_message, agent-handle resolution. Everything
mocked — no network, no DB (get_db_session patched).

Coverage:
- __init__ registers all 15 adapters; register/get_adapter incl. generic
  fallback.
- handle_incoming_message: empty content ignored; identity resolved (user with
  workspaces / no workspaces); identity without user rejected; no identity
  rejected; identity lookup exception; user not resolved; slash command
  handled / unhandled fallthrough; interaction; @handle with and without
  matched agent; normal message → background processing task.
- _handle_slash_commands: /agents, /workflow <id>, /run <text>, unknown.
- _process_and_reply: voice transcription (telegram ogg / others m4a), voice
  failure fallback, dict responses (final_output / response / output /
  actions_executed / empty), non-dict response, exception → error reply.
- send_message: success and failure, UI broadcast.
- _resolve_agent_by_handle: found / not found.
- _handle_interaction: APPROVE, REJECT, invalid format, exception path.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.communication_service as cs_mod
from core.communication_service import CommunicationService
from core.models import AgentRegistry, UserIdentity  # noqa: F401 (lazy-import keys)


class _FakeQuery:
    """Minimal query double for the fake DB session (filter/first)."""

    def __init__(self, row):
        self._row = row

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._row


class _FakeDb:
    def __init__(self, rows=None):
        # rows: dict of model -> row returned by first()
        self._rows = rows or {}
        self.closed = False

    def query(self, model):
        return _FakeQuery(self._rows.get(model))

    def close(self):
        self.closed = True


class _FakeSession:
    """get_db_session context manager substitute."""

    def __init__(self, db):
        self._db = db

    def __enter__(self):
        return self._db

    def __exit__(self, *exc):
        return False


class _BgRecorder:
    """Records background_tasks.add_task calls for later execution."""

    def __init__(self):
        self.tasks = []

    def add_task(self, fn, **kwargs):
        self.tasks.append((fn, kwargs))


def _user(uid="u1", tenant="t1", email="alice@example.com", with_ws=False):
    return SimpleNamespace(
        id=uid,
        tenant_id=tenant,
        email=email,
        workspaces=[SimpleNamespace(id="ws-1")] if with_ws else [],
    )


def _identity(user):
    return SimpleNamespace(user=user)


class _CommHarness:
    """Builds a service with all outbound surfaces mocked."""

    def __init__(self, db=None):
        self.svc = CommunicationService()
        self.db = db if db is not None else _FakeDb()
        self.bg = _BgRecorder()
        for name in self.svc._adapters:
            self.svc._adapters[name].send_message = AsyncMock(return_value=True)
            self.svc._adapters[name].get_media = AsyncMock(return_value=b"audio")
        self.session_patch = patch.object(cs_mod, "get_db_session",
                                          return_value=_FakeSession(self.db))
        self.session_patch.start()
        self.hmt = AsyncMock(return_value={"final_output": "done"})
        self.hmt_patch = patch.object(cs_mod, "handle_manual_trigger", self.hmt)
        self.hmt_patch.start()
        self.broadcast = AsyncMock()
        self.bcast_patch = patch.object(cs_mod.notification_manager, "broadcast",
                                        self.broadcast)
        self.bcast_patch.start()
        self.voice_svc = SimpleNamespace(
            transcribe_audio=AsyncMock(return_value=SimpleNamespace(text="transcribed"))
        )
        self.voice_patch = patch("core.voice_service.get_voice_service",
                                 return_value=self.voice_svc)
        self.voice_patch.start()
        self.hitl = MagicMock()
        self.hitl.resolve_action = AsyncMock(return_value={"resolved": True})
        self.hitl_patch = patch("core.hitl_service.hitl_service", self.hitl)
        self.hitl_patch.start()

    def stop(self):
        for p in [self.session_patch, self.hmt_patch, self.bcast_patch,
                  self.voice_patch, self.hitl_patch]:
            p.stop()


@pytest.fixture()
def harness():
    h = _CommHarness()
    yield h
    h.stop()


class TestAdapterRegistry:
    def test_all_adapters_registered(self):
        svc = CommunicationService()
        for name in ["slack", "discord", "whatsapp", "telegram", "teams",
                     "intercom", "email", "sms", "google_chat", "matrix",
                     "facebook", "line", "signal", "generic"]:
            assert name in svc._adapters
        assert len(svc._adapters) == 14

    def test_register_and_get(self):
        svc = CommunicationService()
        adapter = MagicMock()
        svc.register_adapter("custom", adapter)
        assert svc.get_adapter("custom") is adapter

    def test_get_adapter_unknown_falls_back_to_generic(self):
        svc = CommunicationService()
        assert svc.get_adapter("mystery") is svc._adapters["generic"]


class TestHandleIncomingMessage:
    def test_empty_content_ignored(self, harness):
        result = asyncio_run(harness.svc.handle_incoming_message(
            "slack", {"sender_id": "s1", "content": "", "channel_id": "c1"},
            harness.bg))
        assert result == {"status": "ignored", "reason": "empty_content"}

    def test_identity_resolved_with_workspace(self, harness):
        harness.db._rows = {UserIdentity: _identity(
            _user(with_ws=True))}
        result = asyncio_run(harness.svc.handle_incoming_message(
            "slack", {"sender_id": "s1", "content": "hello",
                      "channel_id": "c1", "metadata": {}}, harness.bg))
        assert result["status"] == "processing"
        assert len(harness.bg.tasks) == 1
        fn, kwargs = harness.bg.tasks[0]
        assert kwargs["workspace_id"] == "ws-1"
        assert kwargs["request"] == "hello"

    def test_identity_resolved_default_workspace(self, harness):
        harness.db._rows = {UserIdentity: _identity(_user())}
        result = asyncio_run(harness.svc.handle_incoming_message(
            "slack", {"sender_id": "s1", "content": "hello", "channel_id": "c1"},
            harness.bg))
        assert result["status"] == "processing"
        assert harness.bg.tasks[0][1]["workspace_id"] == "default"

    def test_identity_without_user_rejected(self, harness):
        harness.db._rows = {UserIdentity: SimpleNamespace(user=None)}
        result = asyncio_run(harness.svc.handle_incoming_message(
            "slack", {"sender_id": "s1", "content": "hello"}, harness.bg))
        assert result["status"] == "error"
        assert "identity" in result["message"].lower()

    def test_no_identity_rejected(self, harness):
        harness.db._rows = {UserIdentity: None}
        result = asyncio_run(harness.svc.handle_incoming_message(
            "slack", {"sender_id": "s1", "content": "hello"}, harness.bg))
        assert result["status"] == "error"
        assert "link your account" in result["message"]

    def test_identity_lookup_exception(self, harness):
        harness.db.query = MagicMock(side_effect=RuntimeError("db down"))
        result = asyncio_run(harness.svc.handle_incoming_message(
            "slack", {"sender_id": "s1", "content": "hello"}, harness.bg))
        assert result["status"] == "error"
        assert "Failed to resolve user identity" in result["message"]

    def test_slash_command_handled(self, harness):
        harness.db._rows = {UserIdentity: _identity(_user())}
        with patch.object(harness.svc, "_handle_slash_commands",
                          new=AsyncMock(return_value=True)) as slash:
            result = asyncio_run(harness.svc.handle_incoming_message(
                "slack", {"sender_id": "s1", "content": "/agents"}, harness.bg))
        assert result == {"status": "command_executed"}
        slash.assert_awaited_once()

    def test_slash_command_unhandled_falls_through(self, harness):
        harness.db._rows = {UserIdentity: _identity(_user())}
        with patch.object(harness.svc, "_handle_slash_commands",
                          new=AsyncMock(return_value=False)):
            result = asyncio_run(harness.svc.handle_incoming_message(
                "slack", {"sender_id": "s1", "content": "/unknown",
                          "channel_id": "c1"}, harness.bg))
        assert result["status"] == "processing"

    def test_interaction_routes_to_handler(self, harness):
        harness.db._rows = {UserIdentity: _identity(_user())}
        with patch.object(harness.svc, "_handle_interaction",
                          new=AsyncMock(return_value={"status": "resolved"})) as ih_:
            result = asyncio_run(harness.svc.handle_incoming_message(
                "slack", {"sender_id": "s1", "content": "APPROVE act-1",
                          "is_interaction": True, "channel_id": "c1"}, harness.bg))
        assert result == {"status": "resolved"}
        ih_.assert_awaited_once()

    def test_at_handle_resolved_to_agent(self, harness):
        harness.db._rows = {UserIdentity: _identity(_user())}
        with patch.object(harness.svc, "_resolve_agent_by_handle",
                          new=AsyncMock(return_value="ag-1")):
            result = asyncio_run(harness.svc.handle_incoming_message(
                "slack", {"sender_id": "s1", "content": "@Alex hello there",
                          "channel_id": "c1"}, harness.bg))
        assert result["status"] == "processing"
        _, kwargs = harness.bg.tasks[0]
        assert kwargs["target_agent_id"] == "ag-1"
        assert kwargs["request"] == "hello there"

    def test_at_handle_alone_without_agent(self, harness):
        harness.db._rows = {UserIdentity: _identity(_user())}
        with patch.object(harness.svc, "_resolve_agent_by_handle",
                          new=AsyncMock(return_value=None)):
            result = asyncio_run(harness.svc.handle_incoming_message(
                "slack", {"sender_id": "s1", "content": "@nobody",
                          "channel_id": "c1"}, harness.bg))
        assert result["status"] == "processing"
        _, kwargs = harness.bg.tasks[0]
        assert kwargs["target_agent_id"] is None
        assert kwargs["request"] == "@nobody"


class TestSlashCommands:
    def test_agents_lists_templates(self, harness):
        with patch.object(harness.svc, "send_message",
                          new=AsyncMock(return_value=None)) as send:
            handled = asyncio_run(harness.svc._handle_slash_commands(
                "/agents", _user(), "ws-1", "slack", "c1", harness.bg))
        assert handled is True
        assert send.await_count == 1
        message = send.await_args.args[2]
        assert "Specialty Agents" in message

    def test_workflow_triggers_background_run(self, harness):
        handled = asyncio_run(harness.svc._handle_slash_commands(
            "/workflow wf-123", _user(), "ws-1", "slack", "c1", harness.bg))
        assert handled is True
        assert len(harness.bg.tasks) == 1
        kwargs = harness.bg.tasks[0][1]
        assert "wf-123" in kwargs["request"]

    def test_run_triggers_background_run(self, harness):
        handled = asyncio_run(harness.svc._handle_slash_commands(
            "/run do the thing", _user(), "ws-1", "slack", "c1", harness.bg))
        assert handled is True
        assert harness.bg.tasks[0][1]["request"] == "do the thing"

    def test_unknown_command_returns_false(self, harness):
        handled = asyncio_run(harness.svc._handle_slash_commands(
            "/bogus", _user(), "ws-1", "slack", "c1", harness.bg))
        assert handled is False
        assert harness.bg.tasks == []


class TestProcessAndReply:
    def _run(self, harness, **overrides):
        kwargs = dict(
            user=_user(), workspace_id="ws-1", request="hello",
            source="slack", channel_id="c1",
        )
        kwargs.update(overrides)
        return asyncio_run(harness.svc._process_and_reply(**kwargs))

    def test_basic_reply_from_final_output(self, harness):
        harness.hmt.return_value = {"final_output": "all done"}
        self._run(harness)
        send = harness.svc._adapters["slack"].send_message
        send.assert_awaited_once_with("c1", "all done")

    def test_reply_fallback_to_response_key(self, harness):
        harness.hmt.return_value = {"response": "fallback text"}
        self._run(harness)
        send = harness.svc._adapters["slack"].send_message
        send.assert_awaited_once_with("c1", "fallback text")

    def test_reply_fallback_to_output_key(self, harness):
        harness.hmt.return_value = {"output": "output text"}
        self._run(harness)
        assert harness.svc._adapters["slack"].send_message.await_args.args[1] == "output text"

    def test_reply_summarizes_actions(self, harness):
        harness.hmt.return_value = {
            "actions_executed": [{"thought": "first step"}, {"thought": "second step"}]
        }
        self._run(harness)
        message = harness.svc._adapters["slack"].send_message.await_args.args[1]
        assert message.startswith("I executed 2 actions")
        assert "first step" in message

    def test_empty_dict_reply_uses_str(self, harness):
        harness.hmt.return_value = {}
        self._run(harness)
        assert harness.svc._adapters["slack"].send_message.await_args.args[1] == "{}"

    def test_non_dict_reply(self, harness):
        harness.hmt.return_value = "plain string"
        self._run(harness)
        assert harness.svc._adapters["slack"].send_message.await_args.args[1] == "plain string"

    def test_exception_sends_error_reply(self, harness):
        harness.hmt.side_effect = RuntimeError("boom")
        self._run(harness)
        message = harness.svc._adapters["slack"].send_message.await_args.args[1]
        assert "error processing" in message
        assert "boom" in message

    def test_voice_transcription_telegram_ogg(self, harness):
        metadata = {"media_id": "m1", "media_type": "audio"}
        self._run(harness, source="telegram", metadata=metadata)
        telegram = harness.svc._adapters["telegram"]
        telegram.get_media.assert_awaited_once_with("m1")
        harness.voice_svc.transcribe_audio.assert_awaited_once()
        assert harness.voice_svc.transcribe_audio.await_args.kwargs["audio_format"] == "ogg"
        harness.hmt.assert_awaited_once()
        assert harness.hmt.await_args.kwargs["request"] == "transcribed"

    def test_voice_transcription_other_platform_m4a(self, harness):
        metadata = {"media_id": "m1", "media_type": "voice"}
        self._run(harness, source="slack", metadata=metadata)
        assert harness.voice_svc.transcribe_audio.await_args.kwargs["audio_format"] == "m4a"

    def test_voice_failure_falls_back_to_text(self, harness):
        harness.svc._adapters["slack"].get_media = AsyncMock(
            side_effect=RuntimeError("download failed"))
        metadata = {"media_id": "m1", "media_type": "audio"}
        self._run(harness, source="slack", metadata=metadata)
        assert harness.hmt.await_args.kwargs["request"] == "hello"

    def test_no_media_skips_voice(self, harness):
        self._run(harness, source="slack", metadata={"media_type": "audio"})
        assert harness.hmt.await_args.kwargs["request"] == "hello"


class TestSendMessage:
    def test_success_broadcasts(self, harness):
        asyncio_run(harness.svc.send_message("slack", "c1", "hi there", "ws-1"))
        harness.svc._adapters["slack"].send_message.assert_awaited_once_with("c1", "hi there")
        harness.broadcast.assert_awaited_once()
        payload = harness.broadcast.await_args.args[0]
        assert payload["type"] == "agent_message"
        assert payload["source"] == "agent (slack)"
        assert payload["content"] == "hi there"

    def test_failure_logs_but_still_broadcasts(self, harness):
        harness.svc._adapters["slack"].send_message = AsyncMock(return_value=False)
        asyncio_run(harness.svc.send_message("slack", "c1", "nope", "ws-1"))
        harness.broadcast.assert_awaited_once()


class TestResolveAgentByHandle:
    def test_found(self, harness):
        harness.db._rows = {AgentRegistry: SimpleNamespace(id="ag-42")}
        agent_id = asyncio_run(
            harness.svc._resolve_agent_by_handle("alex", "t1", "ws-1"))
        assert agent_id == "ag-42"

    def test_not_found(self, harness):
        harness.db._rows = {AgentRegistry: None}
        agent_id = asyncio_run(
            harness.svc._resolve_agent_by_handle("ghost", "t1", "ws-1"))
        assert agent_id is None


class TestHandleInteraction:
    def test_approve(self, harness):
        result = asyncio_run(harness.svc._handle_interaction(
            "slack", {"content": "APPROVE act-1", "channel_id": "c1"},
            _user(), "ws-1", harness.bg))
        assert result == {"status": "resolved", "action_id": "act-1"}
        harness.hitl.resolve_action.assert_awaited_once_with(
            action_id="act-1", resolution="approved",
            resolver_id="u1",
            metadata={"source": "slack", "original_payload": {"content": "APPROVE act-1", "channel_id": "c1"}})
        harness.svc._adapters["slack"].send_message.assert_awaited_once_with(
            "c1", "✅ Action `act-1` has been approve.")

    def test_reject(self, harness):
        result = asyncio_run(harness.svc._handle_interaction(
            "slack", {"content": "REJECT act-2", "channel_id": "c1"},
            _user(), "ws-1", harness.bg))
        assert result["status"] == "resolved"
        assert harness.hitl.resolve_action.await_args.kwargs["resolution"] == "rejected"

    def test_invalid_format(self, harness):
        result = asyncio_run(harness.svc._handle_interaction(
            "slack", {"content": "APPROVE", "channel_id": "c1"},
            _user(), "ws-1", harness.bg))
        assert result == {"status": "error", "message": "Invalid interaction format"}
        harness.hitl.resolve_action.assert_not_called()

    def test_exception_sends_error_confirmation(self, harness):
        harness.hitl.resolve_action.side_effect = RuntimeError("resolve failed")
        result = asyncio_run(harness.svc._handle_interaction(
            "slack", {"content": "APPROVE act-1", "channel_id": "c1"},
            _user(), "ws-1", harness.bg))
        assert result["status"] == "error"
        message = harness.svc._adapters["slack"].send_message.await_args.args[1]
        assert "Error resolving action" in message


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)
