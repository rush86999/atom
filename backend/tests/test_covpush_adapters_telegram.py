"""
Coverage-push + bug-hunt tests for integrations/atom_telegram_integration.py.

TDD targets (RED first):
1. handle_callback_query passes undefined `user_id` to callback handlers
   -> NameError for any callback with matching data prefix.
2. _perform_ai_search references AIRequest/AITaskType/AIModelType/AIServiceType
   which are undefined when the enterprise import fails -> NameError.
3. handle_inline_query calls non-existent lancedb_handler.semantic_search
   -> LanceDB semantic search never works (silently falls back).
"""

import asyncio
import json
import os
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest

import integrations.atom_telegram_integration as tg
from integrations.atom_telegram_integration import (
    AtomTelegramIntegration,
    TelegramChat,
    TelegramChatType,
    TelegramCommandType,
    TelegramMessage,
    TelegramMessageType,
    TelegramUser,
)


def _tgi(config=None):
    cfg = dict(config or {})
    cfg.setdefault("bot_token", "bot123")
    return AtomTelegramIntegration(cfg)


def _tchat(chat_id=1):
    return TelegramChat(
        chat_id=chat_id,
        chat_type=TelegramChatType.GROUP,
        title="Team Chat",
        username=None,
        first_name=None,
        last_name=None,
        description="d",
        permissions={},
        security_level="standard",
        is_active=True,
        member_count=5,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        last_message=datetime(2026, 1, 2, tzinfo=timezone.utc),
        metadata={})


def _tmsg(mid=1, chat_id=1, user_id=7, content="hello world"):
    return TelegramMessage(
        message_id=mid,
        chat_id=chat_id,
        user_id=user_id,
        message_type=TelegramMessageType.TEXT,
        content=content,
        media_path=None,
        reply_to_message_id=None,
        forward_from=None,
        forward_from_chat=None,
        edit_date=None,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        views=0,
        reactions=[],
        security_flags={},
        metadata={})


class TestTelegramModels:
    def test_enums(self):
        assert TelegramMessageType.POLL.value == "poll"
        assert TelegramMessageType.VENUE.value == "venue"
        assert TelegramChatType.SUPERGROUP.value == "supergroup"
        assert TelegramCommandType.START.value == "start"
        assert len(list(TelegramCommandType)) == 12

    def test_dataclasses(self):
        u = TelegramUser(
            user_id=1, username="bob", first_name="B", last_name=None,
            language_code="en", is_bot=False, is_premium=False, is_active=True,
            permissions=[], security_level="standard",
            created_at=datetime.now(timezone.utc),
            last_active=datetime.now(timezone.utc), metadata={})
        assert u.user_id == 1
        c = _tchat()
        assert c.chat_type == TelegramChatType.GROUP
        m = _tmsg()
        assert m.message_type == TelegramMessageType.TEXT
        assert m.timestamp.tzinfo is not None


class TestTelegramLifecycle:
    def test_init(self):
        svc = _tgi()
        assert svc.is_initialized is False
        assert svc.telegram_config["bot_token"] == "bot123"
        assert len(svc.callback_handlers) == 4
        assert svc.analytics_metrics["total_messages"] == 0

    def test_init_env_token(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "envtok")
        svc = _tgi({"bot_token": None})
        assert svc.telegram_config["bot_token"] == "envtok"

    def test_initialize_no_token(self):
        svc = _tgi({"bot_token": None})
        assert asyncio.run(svc.initialize()) is False

    def test_initialize_success(self):
        svc = _tgi()
        assert asyncio.run(svc.initialize()) is True
        assert svc.is_initialized is True
        assert hasattr(svc, "_start_time")

    def test_initialize_exception(self):
        svc = _tgi()
        svc._setup_security_and_compliance = AsyncMock(side_effect=Exception("boom"))
        assert asyncio.run(svc.initialize()) is False

    def test_initialize_no_enterprise(self):
        svc = _tgi({"enable_enterprise_features": False})
        assert asyncio.run(svc.initialize()) is True

    def test_get_service_status(self):
        svc = _tgi()
        svc._start_time = time.time() - 5
        status = asyncio.run(svc.get_service_status())
        assert status["status"] == "inactive"
        assert status["platform"] == "telegram"
        svc.is_initialized = True
        status = asyncio.run(svc.get_service_status())
        assert status["status"] == "active"
        assert status["uptime"] >= 5
        assert status["bot_username"] is None

    def test_close(self):
        svc = _tgi()
        asyncio.run(svc.close())


class TestTelegramSetup:
    def test_setup_enterprise_features_no_services(self):
        svc = _tgi()
        svc.enterprise_security = None
        svc.enterprise_automation = None
        asyncio.run(svc._setup_enterprise_features())

    def test_setup_enterprise_features_success(self):
        svc = _tgi()
        svc.enterprise_security = MagicMock()
        svc.enterprise_automation = MagicMock()
        asyncio.run(svc._setup_enterprise_features())
        assert svc.security_policies["user_access_control"]["enabled"] is True
        assert svc.compliance_rules["audit_logging"]["enabled"] is True
        assert "message_received" in svc.automation_triggers

    def test_setup_security_policies(self):
        svc = _tgi()
        asyncio.run(svc._setup_security_policies())
        assert "chat_security" in svc.security_policies

    def test_setup_compliance_rules(self):
        svc = _tgi()
        asyncio.run(svc._setup_compliance_rules())
        assert "message_retention" in svc.compliance_rules

    def test_setup_automation_triggers(self):
        svc = _tgi()
        asyncio.run(svc._setup_automation_triggers())
        assert "command_executed" in svc.automation_triggers

    def test_setup_automation_no_service(self):
        svc = _tgi()
        svc.enterprise_automation = None
        asyncio.run(svc._setup_automation())

    def test_setup_automation_success(self):
        svc = _tgi()
        svc.enterprise_automation = MagicMock()
        svc.enterprise_automation.create_integration_automation = AsyncMock(
            return_value={"ok": True})
        asyncio.run(svc._setup_automation())
        svc.enterprise_automation.create_integration_automation.assert_awaited_once()

    def test_setup_automation_failure(self):
        svc = _tgi()
        svc.enterprise_automation = MagicMock()
        svc.enterprise_automation.create_integration_automation = AsyncMock(
            return_value={"ok": False, "error": "e"})
        asyncio.run(svc._setup_automation())

    def test_setup_automation_exception(self):
        svc = _tgi()
        svc.enterprise_automation = MagicMock()
        svc.enterprise_automation.create_integration_automation = AsyncMock(
            side_effect=Exception("boom"))
        asyncio.run(svc._setup_automation())

    def test_setup_security_and_compliance(self):
        svc = _tgi()
        asyncio.run(svc._setup_security_and_compliance())
        assert svc.security_monitoring["message_anomaly_detection"]["enabled"]
        assert svc.compliance_monitoring["data_retention_management"]["enabled"]

    def test_setup_security_monitoring(self):
        svc = _tgi()
        asyncio.run(svc._setup_security_monitoring())
        assert "user_behavior_analysis" in svc.security_monitoring

    def test_setup_compliance_monitoring(self):
        svc = _tgi()
        asyncio.run(svc._setup_compliance_monitoring())
        assert "user_activity_auditing" in svc.compliance_monitoring

    def test_load_existing_data(self):
        svc = _tgi()
        asyncio.run(svc._load_existing_data())

    def test_start_bot(self):
        svc = _tgi()
        asyncio.run(svc._start_bot())
        assert svc._start_time > 0


class TestTelegramIntelligence:
    def test_get_intelligent_workspaces(self):
        svc = _tgi()
        svc.active_chats = {1: _tchat(), 2: _tchat(2)}
        svc.active_chats[2].is_active = False
        ws = asyncio.run(svc.get_intelligent_workspaces(7))
        assert len(ws) == 1
        assert ws[0]["id"] == 1
        assert ws[0]["platform"] == "telegram"
        assert ws[0]["type"] == "group"

    def test_get_intelligent_workspaces_error(self):
        svc = _tgi()
        svc.active_chats = {1: None}
        assert asyncio.run(svc.get_intelligent_workspaces(7)) == []

    def test_get_intelligent_channels(self):
        svc = _tgi()
        svc.active_chats = {1: _tchat()}
        ch = asyncio.run(svc.get_intelligent_channels(1, 7))
        assert len(ch) == 1
        assert ch[0]["is_active"] is True
        assert asyncio.run(svc.get_intelligent_channels(99, 7)) == []

    def test_send_intelligent_message(self):
        svc = _tgi()
        svc._log_message_event = AsyncMock()
        result = asyncio.run(svc.send_intelligent_message(1, "hi", {"k": "v"}))
        assert result["success"] is False
        assert svc._log_message_event.await_count == 0

    def test_send_intelligent_message_error(self):
        svc = _tgi()
        svc.telegram_config["bot_token"] = None
        result = asyncio.run(svc.send_intelligent_message(1, "hi"))
        assert result["success"] is False

    def test_perform_intelligent_search(self):
        svc = _tgi()
        svc.message_history = {1: [_tmsg(content="hello world"),
                                  _tmsg(mid=2, content="something else")]}
        results = asyncio.run(svc.perform_intelligent_search("hello", 7))
        assert len(results) == 1
        assert results[0]["id"] == 1
        assert results[0]["platform"] == "telegram"

    def test_perform_intelligent_search_scoped(self):
        svc = _tgi()
        svc.message_history = {1: [_tmsg(content="hello world")],
                               2: [_tmsg(mid=5, chat_id=2, content="hello there")]}
        results = asyncio.run(svc.perform_intelligent_search("hello", 7, workspace_id=2))
        assert results[0]["id"] == 5

    def test_perform_intelligent_search_with_ai(self):
        svc = _tgi()
        svc.message_history = {1: [_tmsg(content="hello world")]}
        ai_result = {"id": "ai1", "type": "ai", "title": "T", "content": "c",
                     "channel_id": 1, "user_id": 7,
                     "timestamp": "2026-01-01T00:00:00Z",
                     "message_type": "text", "platform": "telegram",
                     "relevance_score": 1.0}
        svc.ai_service = MagicMock()
        svc._perform_ai_search = AsyncMock(return_value=[ai_result])
        results = asyncio.run(svc.perform_intelligent_search("hello", 7))
        assert any(r["id"] == "ai1" for r in results)

    def test_perform_intelligent_search_error(self):
        svc = _tgi()
        svc.message_history = {1: [_tmsg(content="hello")]}
        svc.ai_service = MagicMock()
        svc._perform_ai_search = AsyncMock(side_effect=Exception("boom"))
        assert asyncio.run(svc.perform_intelligent_search("hello", 7)) == []

    def test_get_user_conversation_history(self):
        svc = _tgi()
        svc.message_history = {1: [_tmsg(content="a", user_id=7),
                                   _tmsg(mid=2, content="b", user_id=8),
                                   _tmsg(mid=3, content="c", user_id=7)]}
        hist = asyncio.run(svc.get_user_conversation_history(7, 1, limit=1))
        assert len(hist) == 1
        assert hist[0]["content"] == "c"
        assert asyncio.run(svc.get_user_conversation_history(7, 99)) == []

    def test_calculate_relevance_score(self):
        svc = _tgi()
        assert svc._calculate_relevance_score("hello world", "hello world") == 1.0
        assert svc._calculate_relevance_score("hello", "goodbye") == 0.0
        assert svc._calculate_relevance_score("", "anything") == 0.0

    def test_perform_ai_search_no_service(self):
        svc = _tgi()
        svc.ai_service = None
        assert asyncio.run(svc._perform_ai_search("q", 1)) == []

    def test_perform_ai_search_success(self, monkeypatch):
        svc = _tgi()
        svc.ai_service = MagicMock()
        response = MagicMock()
        response.ok = True
        response.output_data = {"results": [{"id": "r1"}]}
        svc.ai_service.process_ai_request = AsyncMock(return_value=response)
        monkeypatch.setattr(tg, "AIRequest", MagicMock)
        monkeypatch.setattr(tg, "AITaskType", SimpleNamespace(SEARCH_QUERY="s"))
        monkeypatch.setattr(tg, "AIModelType", SimpleNamespace(GPT_4="g"))
        monkeypatch.setattr(tg, "AIServiceType", SimpleNamespace(OPENAI="o"))
        result = asyncio.run(svc._perform_ai_search("q", 1))
        assert result == [{"id": "r1"}]
        assert svc.ai_service.process_ai_request.await_count == 1

    def test_perform_ai_search_not_ok(self, monkeypatch):
        svc = _tgi()
        svc.ai_service = MagicMock()
        response = MagicMock()
        response.ok = False
        svc.ai_service.process_ai_request = AsyncMock(return_value=response)
        monkeypatch.setattr(tg, "AIRequest", MagicMock)
        monkeypatch.setattr(tg, "AITaskType", SimpleNamespace(SEARCH_QUERY="s"))
        monkeypatch.setattr(tg, "AIModelType", SimpleNamespace(GPT_4="g"))
        monkeypatch.setattr(tg, "AIServiceType", SimpleNamespace(OPENAI="o"))
        assert asyncio.run(svc._perform_ai_search("q", 1)) == []

    def test_log_message_event(self):
        svc = _tgi()
        svc.enterprise_security = MagicMock()
        svc.enterprise_security.audit_event = AsyncMock()
        asyncio.run(svc._log_message_event("message_sent", 1, {"user_id": 7}))
        svc.enterprise_security.audit_event.assert_awaited_once()
        asyncio.run(_tgi()._log_message_event("x", 1, {}))

    def test_log_message_event_error(self):
        svc = _tgi()
        svc.enterprise_security = MagicMock()
        svc.enterprise_security.audit_event = AsyncMock(side_effect=Exception("boom"))
        asyncio.run(svc._log_message_event("x", 1, {}))


class _FakeHttpxClient:
    def __init__(self, ok=True, result=None, description=None, exc=None):
        if exc:
            self.post = AsyncMock(side_effect=exc)
        else:
            data = {"ok": ok, "result": result or {}}
            if description:
                data["description"] = description
            self.post = AsyncMock(return_value=httpx.Response(200, json=data))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class TestTelegramApiCalls:
    def _patch_client(self, monkeypatch, **kwargs):
        holder = {}

        def factory(*a, **k):
            client = _FakeHttpxClient(**kwargs)
            holder["client"] = client
            return client

        monkeypatch.setattr(tg.httpx, "AsyncClient", factory)
        return holder

    def test_send_message_with_keyboard_success(self, monkeypatch):
        self._patch_client(monkeypatch, ok=True, result={"message_id": 42})
        svc = _tgi()
        result = asyncio.run(svc.send_message_with_keyboard(
            1, "hi", [[{"text": "Go", "callback_data": "action_x"}]],
            parse_mode="Markdown", disable_notification=True, reply_to_message_id=5))
        assert result["success"] is True
        assert result["message_id"] == 42

    def test_send_message_with_keyboard_no_token(self):
        svc = _tgi({"bot_token": None})
        result = asyncio.run(svc.send_message_with_keyboard(1, "hi", [[]]))
        assert result["success"] is False

    def test_send_message_with_keyboard_api_failure(self, monkeypatch):
        self._patch_client(monkeypatch, ok=False, description="bot blocked")
        svc = _tgi()
        result = asyncio.run(svc.send_message_with_keyboard(1, "hi", [[]]))
        assert result["success"] is False
        assert result["error"] == "bot blocked"

    def test_send_message_with_keyboard_exception(self, monkeypatch):
        self._patch_client(monkeypatch, exc=httpx.ConnectError("conn refused"))
        svc = _tgi()
        result = asyncio.run(svc.send_message_with_keyboard(1, "hi", [[]]))
        assert result["success"] is False

    def test_edit_message_keyboard(self, monkeypatch):
        self._patch_client(monkeypatch, ok=True)
        svc = _tgi()
        result = asyncio.run(svc.edit_message_keyboard(1, 42, [[{"text": "X"}]],
                                                       ))
        assert result["success"] is True
        assert result["message_id"] == 42

    def test_edit_message_keyboard_no_token(self):
        svc = _tgi({"bot_token": None})
        assert asyncio.run(svc.edit_message_keyboard(1, 42, [[]]))["success"] is False

    def test_edit_message_keyboard_error(self, monkeypatch):
        self._patch_client(monkeypatch, ok=False, description="bad message")
        svc = _tgi()
        result = asyncio.run(svc.edit_message_keyboard(1, 42, [[]]))
        assert result["error"] == "bad message"

    def test_answer_callback_query(self, monkeypatch):
        self._patch_client(monkeypatch, ok=True)
        svc = _tgi()
        result = asyncio.run(svc.answer_callback_query("cq1", text="Done", show_alert=True))
        assert result["success"] is True

    def test_answer_callback_query_no_token(self):
        svc = _tgi({"bot_token": None})
        assert asyncio.run(svc.answer_callback_query("cq1"))["success"] is False

    def test_answer_inline_query(self, monkeypatch):
        holder = self._patch_client(monkeypatch, ok=True)
        svc = _tgi()
        results = [{"id": "r1", "title": "T", "description": "D", "message": "M"}]
        result = asyncio.run(svc.answer_inline_query("iq1", results, next_offset="2"))
        assert result["success"] is True
        payload = holder["client"].post.call_args[1]["json"]
        assert payload["next_offset"] == "2"
        assert payload["is_personal"] is False

    def test_answer_inline_query_no_token(self):
        svc = _tgi({"bot_token": None})
        assert asyncio.run(svc.answer_inline_query("iq1", []))["success"] is False

    def test_answer_inline_query_failure(self, monkeypatch):
        self._patch_client(monkeypatch, ok=False, description="fail")
        svc = _tgi()
        assert asyncio.run(svc.answer_inline_query("iq1", []))["success"] is False

    def test_send_chat_action(self, monkeypatch):
        self._patch_client(monkeypatch, ok=True)
        svc = _tgi()
        result = asyncio.run(svc.send_chat_action(1, "typing", progress=50))
        assert result["success"] is True

    def test_send_chat_action_no_token(self):
        svc = _tgi({"bot_token": None})
        assert asyncio.run(svc.send_chat_action(1, "typing"))["success"] is False

    def test_send_intelligent_message_enhanced(self, monkeypatch):
        holder = self._patch_client(monkeypatch, ok=True, result={"message_id": 7})
        svc = _tgi()
        result = asyncio.run(svc.send_intelligent_message(
            1, "hi", {"meta": 1}, parse_mode="HTML", reply_to_message_id=3))
        assert result["success"] is True
        assert result["message_id"] == 7
        payload = holder["client"].post.call_args[1]["json"]
        assert payload["parse_mode"] == "HTML"
        assert payload["reply_to_message_id"] == 3

    def test_send_intelligent_message_enhanced_no_token(self):
        svc = _tgi({"bot_token": None})
        assert asyncio.run(svc.send_intelligent_message(1, "hi"))["success"] is False

    def test_send_photo(self, monkeypatch):
        self._patch_client(monkeypatch, ok=True, result={"message_id": 9})
        svc = _tgi()
        result = asyncio.run(svc.send_photo(1, "https://x/pic.png", caption="c"))
        assert result["success"] is True
        assert result["message_id"] == 9

    def test_send_photo_no_token(self):
        svc = _tgi({"bot_token": None})
        assert asyncio.run(svc.send_photo(1, "pic"))["success"] is False

    def test_send_poll(self, monkeypatch):
        self._patch_client(monkeypatch, ok=True, result={"message_id": 3, "poll_id": 9})
        svc = _tgi()
        result = asyncio.run(svc.send_poll(1, "Q?", ["a", "b"], explanation="why"))
        assert result["success"] is True
        assert result["poll_id"] == 9

    def test_send_poll_no_token(self):
        svc = _tgi({"bot_token": None})
        assert asyncio.run(svc.send_poll(1, "Q", ["a"]))["success"] is False

    def test_get_chat_info(self, monkeypatch):
        self._patch_client(monkeypatch, ok=True, result={"id": 1, "type": "group"})
        svc = _tgi()
        result = asyncio.run(svc.get_chat_info(1))
        assert result["success"] is True
        assert result["chat_info"]["type"] == "group"

    def test_get_chat_info_no_token(self):
        svc = _tgi({"bot_token": None})
        assert asyncio.run(svc.get_chat_info(1))["success"] is False


class TestTelegramCallbackHandling:
    def test_handle_callback_query_routes_action(self):
        svc = _tgi()
        svc.answer_callback_query = AsyncMock()
        handler = AsyncMock()
        svc.callback_handlers = {"action_": handler}
        asyncio.run(svc.handle_callback_query(
            {"id": "cq1", "data": "action_approve_request_123",
             "from": {"id": 42}, "message": {}}))
        handler.assert_awaited_once_with("cq1", "action_approve_request_123", 42)
        svc.answer_callback_query.assert_awaited_once()

    def test_handle_callback_query_unknown_prefix(self):
        svc = _tgi()
        svc.answer_callback_query = AsyncMock()
        asyncio.run(svc.handle_callback_query(
            {"id": "cq1", "data": "weird_thing", "from": {"id": 42}, "message": {}}))
        assert svc.answer_callback_query.await_count == 2
        assert svc.answer_callback_query.await_args.kwargs["show_alert"] is True

    def test_handle_callback_query_no_data(self):
        svc = _tgi()
        svc.answer_callback_query = AsyncMock()
        asyncio.run(svc.handle_callback_query(
            {"id": "cq1", "data": "", "from": {"id": 42}, "message": {}}))
        assert svc.answer_callback_query.await_count == 2

    def test_handle_callback_query_error(self):
        svc = _tgi()
        svc.answer_callback_query = AsyncMock(side_effect=Exception("boom"))
        asyncio.run(svc.handle_callback_query(
            {"id": "cq1", "data": "action_x", "from": {"id": 42}, "message": {}}))

    def test_handle_action_callback_approve(self):
        svc = _tgi()
        svc.answer_callback_query = AsyncMock()
        asyncio.run(svc._handle_action_callback("cq1", "action_approve_request_123", 7))
        assert svc.answer_callback_query.await_args.kwargs["text"] == "Request approved"

    def test_handle_action_callback_deny(self):
        svc = _tgi()
        svc.answer_callback_query = AsyncMock()
        asyncio.run(svc._handle_action_callback("cq1", "action_deny_request_456", 7))
        assert svc.answer_callback_query.await_args.kwargs["text"] == "Request denied"

    def test_handle_action_callback_execute(self):
        svc = _tgi()
        svc.answer_callback_query = AsyncMock()
        asyncio.run(svc._handle_action_callback("cq1", "action_execute_workflow_w1", 7))
        assert "started" in svc.answer_callback_query.await_args.kwargs["text"]

    def test_handle_action_callback_unknown(self):
        svc = _tgi()
        svc.answer_callback_query = AsyncMock()
        asyncio.run(svc._handle_action_callback("cq1", "action_bogus_x", 7))
        assert "Unknown action" in svc.answer_callback_query.await_args.kwargs["text"]

    def test_handle_action_callback_invalid_format(self):
        svc = _tgi()
        svc.answer_callback_query = AsyncMock()
        asyncio.run(svc._handle_action_callback("cq1", "action", 7))
        assert svc.answer_callback_query.await_args.kwargs["show_alert"] is True

    def test_handle_action_callback_error(self):
        svc = _tgi()
        svc.answer_callback_query = AsyncMock(
            side_effect=[Exception("boom"), None])
        asyncio.run(svc._handle_action_callback("cq1", "action_x", 7))
        assert svc.answer_callback_query.await_count == 2

    def test_handle_search_callback(self):
        svc = _tgi()
        svc.answer_callback_query = AsyncMock()
        asyncio.run(svc._handle_search_callback("cq1", "search_recent_messages", 7))
        assert svc.answer_callback_query.await_args.kwargs["text"] == "Search completed"

    def test_handle_search_callback_communications(self):
        svc = _tgi()
        svc.answer_callback_query = AsyncMock()
        asyncio.run(svc._handle_search_callback("cq1", "search_communications_invoice", 7))
        assert svc.answer_callback_query.await_args.kwargs["text"] == "Search completed"

    def test_handle_search_callback_workflows(self):
        svc = _tgi()
        svc.answer_callback_query = AsyncMock()
        asyncio.run(svc._handle_search_callback("cq1", "search_workflows_my_flow", 7))

    def test_handle_search_callback_unknown(self):
        svc = _tgi()
        svc.answer_callback_query = AsyncMock()
        asyncio.run(svc._handle_search_callback("cq1", "search_bogus_q", 7))
        assert "Unknown search type" in svc.answer_callback_query.await_args.kwargs["text"]

    def test_handle_search_callback_invalid_format(self):
        svc = _tgi()
        svc.answer_callback_query = AsyncMock()
        asyncio.run(svc._handle_search_callback("cq1", "search", 7))

    def test_handle_workflow_callback(self):
        svc = _tgi()
        svc.answer_callback_query = AsyncMock()
        asyncio.run(svc._handle_workflow_callback("cq1", "workflow_123_start", 7))
        assert svc.answer_callback_query.await_args.kwargs["text"] == "Workflow started"

    def test_handle_workflow_callback_stop_status(self):
        svc = _tgi()
        svc.answer_callback_query = AsyncMock()
        asyncio.run(svc._handle_workflow_callback("cq1", "workflow_123_stop", 7))
        assert svc.answer_callback_query.await_args.kwargs["text"] == "Workflow stopped"
        asyncio.run(svc._handle_workflow_callback("cq1", "workflow_123_status", 7))
        assert "Status" in svc.answer_callback_query.await_args.kwargs["text"]

    def test_handle_workflow_callback_unknown(self):
        svc = _tgi()
        svc.answer_callback_query = AsyncMock()
        asyncio.run(svc._handle_workflow_callback("cq1", "workflow_123_bogus", 7))
        assert "Unknown workflow action" in svc.answer_callback_query.await_args.kwargs["text"]

    def test_handle_workflow_callback_invalid_format(self):
        svc = _tgi()
        svc.answer_callback_query = AsyncMock()
        asyncio.run(svc._handle_workflow_callback("cq1", "workflow_123", 7))

    def test_handle_settings_callback(self):
        svc = _tgi()
        svc.answer_callback_query = AsyncMock()
        asyncio.run(svc._handle_settings_callback("cq1", "settings_notifications_on", 7))
        assert svc.answer_callback_query.await_args.kwargs["text"] == "Notifications updated"

    def test_handle_settings_callback_language_theme(self):
        svc = _tgi()
        svc.answer_callback_query = AsyncMock()
        asyncio.run(svc._handle_settings_callback("cq1", "settings_language_es", 7))
        assert svc.answer_callback_query.await_args.kwargs["text"] == "Language updated"
        asyncio.run(svc._handle_settings_callback("cq1", "settings_theme_dark", 7))
        assert svc.answer_callback_query.await_args.kwargs["text"] == "Theme updated"

    def test_handle_settings_callback_unknown(self):
        svc = _tgi()
        svc.answer_callback_query = AsyncMock()
        asyncio.run(svc._handle_settings_callback("cq1", "settings_bogus_x", 7))
        assert "Unknown setting" in svc.answer_callback_query.await_args.kwargs["text"]

    def test_handle_settings_callback_invalid_format(self):
        svc = _tgi()
        svc.answer_callback_query = AsyncMock()
        asyncio.run(svc._handle_settings_callback("cq1", "settings_on", 7))

    def test_sub_handlers(self):
        svc = _tgi()
        svc.answer_callback_query = AsyncMock()
        asyncio.run(svc._handle_approve_request("cq1", ["r1"], 7))
        asyncio.run(svc._handle_deny_request("cq1", [], 7))
        asyncio.run(svc._handle_execute_workflow("cq1", ["w1"], 7))
        asyncio.run(svc._handle_search_recent_messages("cq1", 7))
        asyncio.run(svc._handle_search_communications("cq1", "q", 7))
        asyncio.run(svc._handle_search_workflows("cq1", "q", 7))
        asyncio.run(svc._handle_start_workflow("cq1", "w1", 7))
        asyncio.run(svc._handle_stop_workflow("cq1", "w1", 7))
        asyncio.run(svc._handle_workflow_status("cq1", "w1", 7))
        asyncio.run(svc._handle_notifications_setting("cq1", "off", 7))
        asyncio.run(svc._handle_language_setting("cq1", "en", 7))
        asyncio.run(svc._handle_theme_setting("cq1", "light", 7))
        assert svc.answer_callback_query.await_count == 12


class TestTelegramInline:
    def test_handle_inline_query_with_lancedb(self):
        svc = _tgi()
        lancedb = MagicMock()
        lancedb.search = Mock(return_value=[{
            "id": "comm1", "subject": "Subject", "body": "Body text",
            "sender": "alice", "platform": "telegram", "timestamp": "t"}])
        svc.lancedb_handler = lancedb
        svc.answer_inline_query = AsyncMock()
        asyncio.run(svc.handle_inline_query(
            {"id": "iq1", "query": "query", "from": {"id": 7}}))
        lancedb.search.assert_called_once_with(
            table_name="communications", query="query", limit=10)
        results = svc.answer_inline_query.call_args[1]["results"]
        assert results[0]["title"] == "Subject"

    def test_handle_inline_query_fallback(self):
        svc = _tgi()
        svc.lancedb_handler = None
        svc.answer_inline_query = AsyncMock()
        asyncio.run(svc.handle_inline_query(
            {"id": "iq1", "query": "query", "from": {"id": 7}}))
        results = svc.answer_inline_query.call_args[1]["results"]
        assert results[0]["id"] == "help_1"

    def test_handle_inline_query_short_query(self):
        svc = _tgi()
        svc.lancedb_handler = None
        svc.answer_inline_query = AsyncMock()
        asyncio.run(svc.handle_inline_query(
            {"id": "iq1", "query": "a", "from": {"id": 7}}))
        assert svc.answer_inline_query.call_args[1]["results"] == []

    def test_handle_inline_query_search_error_fallback(self):
        svc = _tgi()
        lancedb = MagicMock()
        lancedb.search = Mock(side_effect=Exception("lancedb down"))
        svc.lancedb_handler = lancedb
        svc.answer_inline_query = AsyncMock()
        asyncio.run(svc.handle_inline_query(
            {"id": "iq1", "query": "query", "from": {"id": 7}}))
        results = svc.answer_inline_query.call_args[1]["results"]
        assert results[0]["id"] == "help_1"

    def test_handle_inline_query_error(self):
        svc = _tgi()
        svc.lancedb_handler = None
        svc.answer_inline_query = AsyncMock(side_effect=Exception("boom"))
        asyncio.run(svc.handle_inline_query(
            {"id": "iq1", "query": "query", "from": {"id": 7}}))

    def test_format_lancedb_result(self):
        svc = _tgi()
        result = svc._format_lancedb_result_for_inline({
            "id": "c1", "subject": "Subj", "body": "b" * 250,
            "sender": "s", "platform": "p", "timestamp": "t"})
        assert result["title"] == "Subj"
        assert "b" * 200 + "..." in result["input_message_content"]["message_text"]

    def test_format_lancedb_result_missing(self):
        svc = _tgi()
        result = svc._format_lancedb_result_for_inline({})
        assert result["title"] == "No Subject"
        assert result["id"]

    def test_format_lancedb_result_error(self):
        svc = _tgi()
        result = svc._format_lancedb_result_for_inline(None)
        assert result is None

    def test_perform_simple_inline_search(self):
        svc = _tgi()
        results = asyncio.run(svc._perform_simple_inline_search("query"))
        assert results[0]["id"] == "help_1"
