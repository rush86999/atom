# -*- coding: utf-8 -*-
"""
Coverage + bug-hunt tests for core/webhook_handlers.py.

Existing coverage lives in tests/test_webhook_handlers.py (handlers + processor
happy paths) and tests/test_slack_webhook_hmac.py (HMAC secret loading). This
file targets the remaining branches:

- SlackWebhookHandler.verify_signature generic-exception path
- SlackWebhookHandler.parse_event exception path
- TeamsWebhookHandler.parse_event: value as dict, exception path
- TeamsWebhookHandler.verify_signature production-missing-header path
- GmailWebhookHandler.verify_signature production-no-header path + bad content-type
- WebhookProcessor.process_*_webhook: invalid signature, unhandled event,
  duplicate detection, internal-error 500, callback dispatch
- WebhookProcessor._process_message: Gmail auto-resumption block
  (no states, with states, critical-workflow refusal, resume error)
- WebhookProcessor._teams_dedup_key: id present, value-as-dict, hash fallback
- get_webhook_processor singleton

All DB / external services are mocked. No real network.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import HTTPException

from core.webhook_handlers import (
    GmailWebhookHandler,
    SlackWebhookHandler,
    TeamsWebhookHandler,
    WebhookEvent,
    WebhookProcessor,
    get_webhook_processor,
    webhook_processor,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_request(body: bytes = b"{}", json_data=None, headers=None):
    """Build a FastAPI Request mock."""
    req = MagicMock()
    req.headers = headers or {}
    req.body = AsyncMock(return_value=body)
    if json_data is not None:
        req.json = AsyncMock(return_value=json_data)
    else:
        req.json = AsyncMock(return_value=json.loads(body))
    return req


def _mock_background():
    bg = MagicMock()
    bg.add_task = MagicMock()
    return bg


def _slack_sig(secret: str, timestamp: str, body: bytes) -> str:
    base = f"v0:{timestamp}".encode() + body
    return "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()


def _gmail_payload(email_address="cand@example.com", history_id="h123"):
    notif = {"emailAddress": email_address, "historyId": history_id}
    data = base64.b64encode(json.dumps(notif).encode()).decode()
    return {"message": {"data": data}}, notif


# ---------------------------------------------------------------------------
# WebhookEvent.to_unified_message
# ---------------------------------------------------------------------------

class TestWebhookEventUnified:
    def test_unified_message_contains_fields(self):
        ts = datetime(2024, 1, 1, 12, 0, 0)
        ev = WebhookEvent(
            platform="slack", event_type="message",
            event_data={"x": 1}, raw_payload={"orig": True}, timestamp=ts,
        )
        unified = ev.to_unified_message()
        assert unified["app_type"] == "slack"
        assert unified["event_type"] == "message"
        assert unified["raw_event"] == {"orig": True}
        assert unified["timestamp"] == ts.isoformat()

    def test_default_timestamp_set_when_none(self):
        ev = WebhookEvent("slack", "message", {}, {})
        assert ev.timestamp is not None
        assert ev.processed is False


# ---------------------------------------------------------------------------
# SlackWebhookHandler
# ---------------------------------------------------------------------------

class TestSlackVerifySignatureException:
    def test_verify_returns_false_on_unexpected_exception(self):
        """The generic except branch must return False, not raise."""
        handler = SlackWebhookHandler(signing_secret="secret")
        # signing_secret.encode() works, but break hmac by making timestamp a
        # non-encodable object so f-string encode raises inside the try.
        with patch("core.webhook_handlers.hmac.new", side_effect=RuntimeError("boom")):
            result = handler.verify_signature("123", "v0=x", b"body")
        assert result is False


class TestSlackParseEventException:
    def test_parse_event_returns_none_on_exception(self):
        handler = SlackWebhookHandler()
        # raw_event with a .get that raises -> exception branch
        result = handler.parse_event(None)
        assert result is None

    def test_parse_unhandled_event_type_returns_none(self):
        handler = SlackWebhookHandler()
        result = handler.parse_event({"type": "totally_unknown"})
        assert result is None

    def test_parse_event_callback_non_message_returns_none(self):
        handler = SlackWebhookHandler()
        raw = {"type": "event_callback", "event": {"type": "reaction_added"}}
        result = handler.parse_event(raw)
        assert result is None

    def test_parse_message_uses_ts_when_no_client_msg_id(self):
        handler = SlackWebhookHandler()
        raw = {
            "type": "event_callback",
            "event": {"type": "message", "ts": "999.0", "text": "hi",
                      "user": "U1", "channel": "C1"},
        }
        ev = handler.parse_event(raw)
        assert ev.event_data["id"] == "999.0"
        assert ev.event_data["sender"] == "U1"


# ---------------------------------------------------------------------------
# TeamsWebhookHandler
# ---------------------------------------------------------------------------

class TestTeamsVerifySignature:
    def test_production_missing_header_rejected(self):
        with patch("core.webhook_handlers.os.getenv", return_value="production"):
            handler = TeamsWebhookHandler()
            assert handler.verify_signature(None) is False

    def test_dev_missing_header_bypassed(self):
        with patch("core.webhook_handlers.os.getenv", return_value="development"):
            handler = TeamsWebhookHandler()
            assert handler.verify_signature(None) is True

    def test_non_bearer_rejected(self):
        handler = TeamsWebhookHandler()
        assert handler.verify_signature("Basic abc") is False
        assert handler.verify_signature("token123") is False

    def test_valid_bearer_accepted(self):
        handler = TeamsWebhookHandler()
        assert handler.verify_signature("Bearer eyJabc") is True


class TestTeamsParseEvent:
    def test_value_as_dict_normalized_to_list(self):
        """value can arrive as a single dict, not a list — must be normalized."""
        handler = TeamsWebhookHandler()
        raw = {
            "type": "Message",
            "value": {
                "@odata.type": "#Microsoft.Graph.chatMessage",
                "id": "msg-1",
                "body": {"content": "Hi", "contentType": "html"},
                "from": {"user": {"displayName": "Jane", "email": "j@x.com"}},
                "chatId": "chat-1",
                "createdDateTime": "2024-01-01T00:00:00Z",
            },
        }
        ev = handler.parse_event(raw)
        assert ev is not None
        assert ev.event_data["content"] == "Hi"
        assert ev.event_data["sender"] == "Jane"
        assert ev.event_data["sender_email"] == "j@x.com"

    def test_no_chat_message_returns_none(self):
        handler = TeamsWebhookHandler()
        raw = {"type": "Message", "value": [{"@odata.type": "Other"}]}
        assert handler.parse_event(raw) is None

    def test_empty_value_returns_none(self):
        handler = TeamsWebhookHandler()
        assert handler.parse_event({"type": "Message", "value": []}) is None

    def test_parse_event_exception_returns_none(self):
        handler = TeamsWebhookHandler()
        assert handler.parse_event(None) is None


# ---------------------------------------------------------------------------
# GmailWebhookHandler
# ---------------------------------------------------------------------------

class TestGmailVerifySignature:
    def test_production_no_header_rejected(self):
        with patch("core.webhook_handlers.os.getenv", return_value="production"):
            handler = GmailWebhookHandler()
            assert handler.verify_signature({}) is False
            assert handler.verify_signature(None) is False

    def test_dev_no_header_bypassed(self):
        with patch("core.webhook_handlers.os.getenv", return_value="development"):
            handler = GmailWebhookHandler()
            assert handler.verify_signature(None) is True
            assert handler.verify_signature({}) is True

    def test_valid_headers_accepted(self):
        handler = GmailWebhookHandler()
        assert handler.verify_signature({"content-type": "application/json"}) is True

    def test_non_message_content_type_logs_warning_but_returns_true(self, caplog):
        """Non-multipart content-type logs a warning but does not reject."""
        handler = GmailWebhookHandler()
        import logging
        with caplog.at_level(logging.WARNING):
            result = handler.verify_signature({"content-type": "text/plain"})
        assert result is True


class TestGmailParseEvent:
    def test_empty_data_returns_none(self):
        handler = GmailWebhookHandler()
        assert handler.parse_event({"message": {}}) is None
        assert handler.parse_event({"message": {"data": ""}}) is None

    def test_invalid_base64_returns_none(self):
        handler = GmailWebhookHandler()
        assert handler.parse_event({"message": {"data": "!!!not-base64!!!"}}) is None

    def test_valid_notification_parsed(self):
        handler = GmailWebhookHandler()
        payload, notif = _gmail_payload("user@x.com", "h999")
        ev = handler.parse_event(payload)
        assert ev is not None
        assert ev.event_type == "push_notification"
        assert ev.event_data["email_address"] == "user@x.com"
        assert ev.event_data["history_id"] == "h999"
        assert ev.event_data["status"] == "pending_fetch"

    def test_parse_exception_returns_none(self):
        handler = GmailWebhookHandler()
        assert handler.parse_event(None) is None


# ---------------------------------------------------------------------------
# WebhookProcessor — process_slack_webhook
# ---------------------------------------------------------------------------

class TestProcessSlackWebhook:
    async def test_invalid_signature_in_production_raises_401(self):
        processor = WebhookProcessor()
        with patch("core.webhook_handlers.os.getenv", return_value="production"):
            processor.slack_handler = MagicMock()
            processor.slack_handler.verify_signature.return_value = False
            req = _mock_request(b"{}", headers={
                "X-Slack-Request-Timestamp": "1", "X-Slack-Signature": "v0=x"})
            with pytest.raises(HTTPException) as exc:
                await processor.process_slack_webhook(req, _mock_background())
            assert exc.value.status_code == 401

    async def test_unhandled_event_returns_ignored(self):
        processor = WebhookProcessor()
        processor.slack_handler = MagicMock()
        processor.slack_handler.verify_signature.return_value = True
        processor.slack_handler.parse_event.return_value = None
        req = _mock_request(b'{"type":"unknown"}')
        result = await processor.process_slack_webhook(req, _mock_background())
        assert result["status"] == "ignored"

    async def test_url_verification_returns_challenge(self):
        processor = WebhookProcessor()
        processor.slack_handler = MagicMock()
        processor.slack_handler.verify_signature.return_value = True
        challenge_ev = WebhookEvent("slack", "url_verification",
                                    {"challenge": "abc"}, {})
        processor.slack_handler.parse_event.return_value = challenge_ev
        req = _mock_request(b'{"type":"url_verification"}')
        result = await processor.process_slack_webhook(req, _mock_background())
        assert result["challenge"] == "abc"

    async def test_duplicate_event_detected(self):
        processor = WebhookProcessor()
        processor.slack_handler = MagicMock()
        processor.slack_handler.verify_signature.return_value = True
        msg_ev = WebhookEvent("slack", "message", {}, {"event_id": "e1"})
        processor.slack_handler.parse_event.return_value = msg_ev
        req = _mock_request(b'{"event_id":"e1"}')
        # First call: success
        r1 = await processor.process_slack_webhook(req, _mock_background())
        assert r1["status"] == "success"
        # Second call: duplicate
        req2 = _mock_request(b'{"event_id":"e1"}')
        r2 = await processor.process_slack_webhook(req2, _mock_background())
        assert r2["status"] == "duplicate"

    async def test_message_event_dispatches_background_task(self):
        processor = WebhookProcessor()
        processor.on_message_received = AsyncMock()
        processor.slack_handler = MagicMock()
        processor.slack_handler.verify_signature.return_value = True
        msg_ev = WebhookEvent("slack", "message", {"content": "hi"}, {"event_id": "e2"})
        processor.slack_handler.parse_event.return_value = msg_ev
        bg = _mock_background()
        req = _mock_request(b'{"event_id":"e2"}')
        result = await processor.process_slack_webhook(req, bg)
        assert result["status"] == "success"
        bg.add_task.assert_called_once()

    async def test_internal_error_raises_500(self):
        processor = WebhookProcessor()
        processor.slack_handler = MagicMock()
        processor.slack_handler.verify_signature.return_value = True
        processor.slack_handler.parse_event.side_effect = RuntimeError("boom")
        req = _mock_request(b"{}")
        with pytest.raises(HTTPException) as exc:
            await processor.process_slack_webhook(req, _mock_background())
        assert exc.value.status_code == 500

    async def test_http_exception_propagates(self):
        """A raised HTTPException (401) must propagate, not be swallowed."""
        processor = WebhookProcessor()
        processor.slack_handler = MagicMock()
        processor.slack_handler.verify_signature.return_value = False
        with patch("core.webhook_handlers.os.getenv", return_value="production"):
            req = _mock_request(b"{}", headers={
                "X-Slack-Request-Timestamp": "1", "X-Slack-Signature": "v0=x"})
            with pytest.raises(HTTPException) as exc:
                await processor.process_slack_webhook(req, _mock_background())
            # Must be the 401 from signature failure, NOT a 500 from the catch-all
            assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# WebhookProcessor — process_teams_webhook
# ---------------------------------------------------------------------------

class TestProcessTeamsWebhook:
    async def test_unhandled_returns_ignored(self):
        processor = WebhookProcessor()
        processor.teams_handler = MagicMock()
        processor.teams_handler.parse_event.return_value = None
        req = _mock_request(b'{"type":"X"}')
        result = await processor.process_teams_webhook(req, _mock_background())
        assert result["status"] == "ignored"

    async def test_message_dispatches(self):
        processor = WebhookProcessor()
        processor.on_message_received = AsyncMock()
        processor.teams_handler = MagicMock()
        msg_ev = WebhookEvent("teams", "message", {}, {"value": [{"id": "m1"}]})
        processor.teams_handler.parse_event.return_value = msg_ev
        bg = _mock_background()
        req = _mock_request(b'{"value":[{"id":"m1"}]}')
        result = await processor.process_teams_webhook(req, bg)
        assert result["status"] == "success"
        assert result["platform"] == "teams"
        bg.add_task.assert_called_once()

    async def test_duplicate_teams_detected(self):
        processor = WebhookProcessor()
        processor.teams_handler = MagicMock()
        msg_ev = WebhookEvent("teams", "message", {}, {"value": [{"id": "dup"}]})
        processor.teams_handler.parse_event.return_value = msg_ev
        req = _mock_request(b'{"value":[{"id":"dup"}]}')
        r1 = await processor.process_teams_webhook(req, _mock_background())
        assert r1["status"] == "success"
        req2 = _mock_request(b'{"value":[{"id":"dup"}]}')
        r2 = await processor.process_teams_webhook(req2, _mock_background())
        assert r2["status"] == "duplicate"

    async def test_internal_error_raises_500(self):
        processor = WebhookProcessor()
        req = _mock_request(b"{}")
        req.json = AsyncMock(side_effect=RuntimeError("db down"))
        with pytest.raises(HTTPException) as exc:
            await processor.process_teams_webhook(req, _mock_background())
        assert exc.value.status_code == 500


# ---------------------------------------------------------------------------
# WebhookProcessor — process_gmail_webhook
# ---------------------------------------------------------------------------

class TestProcessGmailWebhook:
    async def test_invalid_notification_returns_ignored(self):
        processor = WebhookProcessor()
        processor.gmail_handler = MagicMock()
        processor.gmail_handler.parse_event.return_value = None
        req = _mock_request(b'{"message":{}}')
        result = await processor.process_gmail_webhook(req, _mock_background())
        assert result["status"] == "ignored"

    async def test_push_notification_dispatches(self):
        processor = WebhookProcessor()
        processor.on_message_received = AsyncMock()
        processor.gmail_handler = MagicMock()
        payload, _ = _gmail_payload("u@x.com", "h1")
        ev = WebhookEvent("gmail", "push_notification", {}, payload)
        processor.gmail_handler.parse_event.return_value = ev
        bg = _mock_background()
        req = _mock_request(json.dumps(payload).encode())
        result = await processor.process_gmail_webhook(req, bg)
        assert result["status"] == "success"
        assert result["platform"] == "gmail"
        bg.add_task.assert_called_once()

    async def test_duplicate_gmail_detected(self):
        processor = WebhookProcessor()
        processor.gmail_handler = MagicMock()
        payload, _ = _gmail_payload("u@x.com", "h1")
        ev = WebhookEvent("gmail", "push_notification", {}, payload)
        processor.gmail_handler.parse_event.return_value = ev
        req = _mock_request(json.dumps(payload).encode())
        await processor.process_gmail_webhook(req, _mock_background())
        req2 = _mock_request(json.dumps(payload).encode())
        r2 = await processor.process_gmail_webhook(req2, _mock_background())
        assert r2["status"] == "duplicate"

    async def test_internal_error_raises_500(self):
        processor = WebhookProcessor()
        req = _mock_request(b"{}")
        req.json = AsyncMock(side_effect=RuntimeError("fail"))
        with pytest.raises(HTTPException) as exc:
            await processor.process_gmail_webhook(req, _mock_background())
        assert exc.value.status_code == 500


# ---------------------------------------------------------------------------
# WebhookProcessor — dedup helpers
# ---------------------------------------------------------------------------

class TestDedupHelpers:
    def test_is_duplicate_false_then_true(self):
        p = WebhookProcessor()
        assert p._is_duplicate("x") is False
        p._mark_processed("x")
        assert p._is_duplicate("x") is True

    def test_mark_processed_stores_datetime(self):
        p = WebhookProcessor()
        p._mark_processed("evt")
        assert isinstance(p.processed_events["evt"], datetime)

    def test_teams_dedup_key_uses_value_id(self):
        p = WebhookProcessor()
        key = p._teams_dedup_key({"value": [{"id": "msg-42"}]})
        assert key == "teams_msg-42"

    def test_teams_dedup_key_value_as_dict(self):
        p = WebhookProcessor()
        key = p._teams_dedup_key({"value": {"id": "msg-7"}})
        assert key == "teams_msg-7"

    def test_teams_dedup_key_falls_back_to_hash(self):
        """No message id -> content-hash fallback (distinct events -> distinct keys)."""
        p = WebhookProcessor()
        k1 = p._teams_dedup_key({"value": [{"body": "a"}]})
        k2 = p._teams_dedup_key({"value": [{"body": "b"}]})
        assert k1 != k2
        assert k1.startswith("teams_")
        # Same payload -> same key (deterministic)
        assert p._teams_dedup_key({"value": [{"body": "a"}]}) == k1

    def test_teams_dedup_key_empty_value(self):
        p = WebhookProcessor()
        key = p._teams_dedup_key({"value": []})
        assert key.startswith("teams_")

    def test_cleanup_removes_oldest(self):
        p = WebhookProcessor()
        # Fill past the 10000 threshold
        for i in range(10001):
            p.processed_events[f"e{i}"] = datetime.now()
        p._mark_processed("new")
        # Should have removed ~1000 oldest
        assert len(p.processed_events) <= 10001


# ---------------------------------------------------------------------------
# WebhookProcessor._process_message — non-gmail paths
# ---------------------------------------------------------------------------

class TestProcessMessageNonGmail:
    async def test_calls_registered_callback(self):
        processor = WebhookProcessor()
        callback_called = []
        async def cb(data):
            callback_called.append(data)
        processor.register_message_callback(cb)
        ev = WebhookEvent("slack", "message", {"content": "x"}, {})
        await processor._process_message(ev)
        assert len(callback_called) == 1
        assert callback_called[0]["app_type"] == "slack"

    async def test_no_callback_does_not_crash(self):
        processor = WebhookProcessor()
        ev = WebhookEvent("teams", "message", {}, {})
        # Should not raise
        await processor._process_message(ev)

    async def test_callback_exception_swallowed(self):
        """Errors in the callback must be caught (background-task safety)."""
        processor = WebhookProcessor()
        async def cb(data):
            raise RuntimeError("callback boom")
        processor.register_message_callback(cb)
        ev = WebhookEvent("slack", "message", {}, {})
        # Must not raise
        await processor._process_message(ev)


# ---------------------------------------------------------------------------
# WebhookProcessor._process_message — Gmail auto-resumption block
# ---------------------------------------------------------------------------

class TestProcessMessageGmailAutoResume:
    async def _gmail_event(self, email_address="cand@example.com"):
        notif = {"emailAddress": email_address, "historyId": "h1"}
        event_data = {"app_type": "gmail", "metadata": {"notification": notif}}
        return WebhookEvent("gmail", "push_notification", event_data, {})

    @pytest.fixture(autouse=True)
    def _inject_deps(self):
        """The auto-resume block does lazy imports of CandidateBookingState,
        get_db_session, get_orchestrator, has_critical_step. Several of these
        don't exist as real symbols, so inject fakes for the duration of each
        test in this class."""
        import core.models as models_mod
        import core.database as db_mod
        CandidateFake = MagicMock(name="CandidateBookingState")
        # .status is used in a filter expression; just needs to be a usable attr
        CandidateFake.status = "pending_candidate"
        session_ctx = MagicMock()
        session_ctx.__enter__.return_value = MagicMock()
        session_ctx.__exit__.return_value = False
        get_db_session = MagicMock(return_value=session_ctx)
        get_orchestrator = MagicMock()
        has_critical_step = MagicMock(return_value=False)
        setattr(models_mod, "CandidateBookingState", CandidateFake)
        setattr(db_mod, "get_db_session", get_db_session)
        # advanced_workflow_orchestrator + core.workflow_security may not be
        # importable in test env; inject into sys.modules
        import sys
        import types
        added_modules = []
        if "advanced_workflow_orchestrator" not in sys.modules:
            mod = types.ModuleType("advanced_workflow_orchestrator")
            mod.get_orchestrator = get_orchestrator
            sys.modules["advanced_workflow_orchestrator"] = mod
            added_modules.append("advanced_workflow_orchestrator")
        else:
            sys.modules["advanced_workflow_orchestrator"].get_orchestrator = get_orchestrator
        if "core.workflow_security" not in sys.modules:
            mod = types.ModuleType("core.workflow_security")
            mod.has_critical_step = has_critical_step
            sys.modules["core.workflow_security"] = mod
            added_modules.append("core.workflow_security")
        else:
            sys.modules["core.workflow_security"].has_critical_step = has_critical_step
        yield
        if hasattr(models_mod, "CandidateBookingState"):
            delattr(models_mod, "CandidateBookingState")

    async def test_no_email_address_skips_resume(self):
        """notification without emailAddress -> skip resume block entirely."""
        processor = WebhookProcessor()
        ev = WebhookEvent(
            "gmail", "push_notification",
            {"app_type": "gmail", "metadata": {"notification": {}}},  # no emailAddress
            {},
        )
        import core.database as db_mod
        # Should not raise and should not open a db session
        get_db = getattr(db_mod, "get_db_session")
        await processor._process_message(ev)
        get_db.assert_not_called()

    async def test_no_pending_states(self):
        processor = WebhookProcessor()
        ev = await self._gmail_event()
        session = MagicMock()
        session.query.return_value.filter.return_value.all.return_value = []
        import core.database as db_mod
        db_mod.get_db_session.return_value.__enter__.return_value = session
        await processor._process_message(ev)
        session.query.assert_called()

    async def test_resume_with_active_context(self):
        processor = WebhookProcessor()
        ev = await self._gmail_event()

        state = MagicMock()
        state.candidate_email = "cand@example.com"
        state.workflow_execution_id = "wf-exec-1"
        state.status = "pending_candidate"

        session = MagicMock()
        session.query.return_value.filter.return_value.all.return_value = [state]

        wf_ctx = MagicMock()
        wf_ctx.variables = {}
        wf_ctx.results = {"wait_for_reply": {"status": "old"}}

        wf_def = MagicMock()
        wf_def.steps = []
        wf_def.workflow_id = "wf-1"

        orchestrator = MagicMock()
        orchestrator.active_contexts = {"wf-exec-1": wf_ctx}
        orchestrator.workflows = {"wf-1": wf_def}
        orchestrator.resume_workflow = AsyncMock()

        import core.database as db_mod
        db_mod.get_db_session.return_value.__enter__.return_value = session
        import sys
        sys.modules["advanced_workflow_orchestrator"].get_orchestrator.return_value = orchestrator
        sys.modules["core.workflow_security"].has_critical_step.return_value = False

        await processor._process_message(ev)

        orchestrator.resume_workflow.assert_awaited_once_with("wf-exec-1", "wait_for_reply")
        assert state.status == "processing_reply"
        session.commit.assert_called()
        assert wf_ctx.variables["candidate_reply_text"] == "I will take the Friday 10am slot."

    async def test_resume_skipped_for_critical_workflow(self):
        """R69: critical workflows without allow_event_critical must NOT auto-resume."""
        processor = WebhookProcessor()
        ev = await self._gmail_event()

        state = MagicMock()
        state.candidate_email = "cand@example.com"
        state.workflow_execution_id = "wf-exec-1"
        state.status = "pending_candidate"

        session = MagicMock()
        session.query.return_value.filter.return_value.all.return_value = [state]

        wf_ctx = MagicMock()
        wf_ctx.variables = {}

        wf_def = MagicMock()
        wf_def.steps = [MagicMock(step_id="wait_for_reply")]
        wf_def.workflow_id = "wf-critical"
        wf_def.allow_event_critical = False

        orchestrator = MagicMock()
        orchestrator.active_contexts = {"wf-exec-1": wf_ctx}
        orchestrator.workflows = {"wf-critical": wf_def}
        orchestrator.resume_workflow = AsyncMock()

        import core.database as db_mod
        db_mod.get_db_session.return_value.__enter__.return_value = session
        import sys
        sys.modules["advanced_workflow_orchestrator"].get_orchestrator.return_value = orchestrator
        sys.modules["core.workflow_security"].has_critical_step.return_value = True

        await processor._process_message(ev)

        # Must NOT resume
        orchestrator.resume_workflow.assert_not_called()
        # State must NOT be changed
        assert state.status == "pending_candidate"

    async def test_critical_workflow_with_opt_in_resumes(self):
        """allow_event_critical=True bypasses the refusal."""
        processor = WebhookProcessor()
        ev = await self._gmail_event()

        state = MagicMock()
        state.candidate_email = "cand@example.com"
        state.workflow_execution_id = "wf-exec-1"
        state.status = "pending_candidate"

        session = MagicMock()
        session.query.return_value.filter.return_value.all.return_value = [state]

        wf_ctx = MagicMock()
        wf_ctx.variables = {}
        wf_ctx.results = {}

        wf_def = MagicMock()
        wf_def.steps = [MagicMock(step_id="wait_for_reply")]
        wf_def.workflow_id = "wf-optin"
        wf_def.allow_event_critical = True

        orchestrator = MagicMock()
        orchestrator.active_contexts = {"wf-exec-1": wf_ctx}
        orchestrator.workflows = {"wf-optin": wf_def}
        orchestrator.resume_workflow = AsyncMock()

        import core.database as db_mod
        db_mod.get_db_session.return_value.__enter__.return_value = session
        import sys
        sys.modules["advanced_workflow_orchestrator"].get_orchestrator.return_value = orchestrator
        sys.modules["core.workflow_security"].has_critical_step.return_value = True

        await processor._process_message(ev)

        orchestrator.resume_workflow.assert_awaited_once()

    async def test_resume_error_swallowed(self):
        """If resume_workflow raises, the error is logged (not propagated)."""
        processor = WebhookProcessor()
        ev = await self._gmail_event()

        state = MagicMock()
        state.candidate_email = "cand@example.com"
        state.workflow_execution_id = "wf-exec-1"
        state.status = "pending_candidate"

        session = MagicMock()
        session.query.return_value.filter.return_value.all.return_value = [state]

        wf_ctx = MagicMock()
        wf_ctx.variables = {}
        wf_ctx.results = {}

        wf_def = MagicMock()
        wf_def.steps = []
        wf_def.workflow_id = "wf-1"

        orchestrator = MagicMock()
        orchestrator.active_contexts = {"wf-exec-1": wf_ctx}
        orchestrator.workflows = {"wf-1": wf_def}
        orchestrator.resume_workflow = AsyncMock(side_effect=RuntimeError("resume failed"))

        import core.database as db_mod
        db_mod.get_db_session.return_value.__enter__.return_value = session
        import sys
        sys.modules["advanced_workflow_orchestrator"].get_orchestrator.return_value = orchestrator
        sys.modules["core.workflow_security"].has_critical_step.return_value = False

        # Must not raise
        await processor._process_message(ev)

    async def test_state_not_in_active_contexts_skipped(self):
        """workflow_execution_id not in active_contexts -> skip that state."""
        processor = WebhookProcessor()
        ev = await self._gmail_event()

        state = MagicMock()
        state.candidate_email = "cand@example.com"
        state.workflow_execution_id = "missing"
        state.status = "pending_candidate"

        session = MagicMock()
        session.query.return_value.filter.return_value.all.return_value = [state]

        orchestrator = MagicMock()
        orchestrator.active_contexts = {}  # empty
        orchestrator.workflows = {}
        orchestrator.resume_workflow = AsyncMock()

        import core.database as db_mod
        db_mod.get_db_session.return_value.__enter__.return_value = session
        import sys
        sys.modules["advanced_workflow_orchestrator"].get_orchestrator.return_value = orchestrator

        await processor._process_message(ev)
        orchestrator.resume_workflow.assert_not_called()

    async def test_inner_block_exception_swallowed(self, caplog):
        """If the imports/DB inside the inner block fail, it's caught at outer."""
        processor = WebhookProcessor()
        ev = await self._gmail_event()
        import logging
        import sys
        # Force failure inside the inner block by making the orchestrator getter raise
        sys.modules["advanced_workflow_orchestrator"].get_orchestrator.side_effect = RuntimeError("boom")
        with caplog.at_level(logging.ERROR):
            # Must not raise
            await processor._process_message(ev)
        assert any("Error checking for workflow resumption" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_webhook_processor_returns_singleton(self):
        p = get_webhook_processor()
        assert p is webhook_processor

    def test_singleton_is_webhook_processor_instance(self):
        assert isinstance(get_webhook_processor(), WebhookProcessor)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
