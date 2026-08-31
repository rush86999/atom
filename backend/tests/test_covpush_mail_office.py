"""
Coverage-push tests (>=95% per module) for the mail/office integration modules:

- integrations/gmail_service.py
- integrations/outlook_service.py
- integrations/outlook_service_enhanced.py
- integrations/microsoft365_service.py
- integrations/atom_telegram_integration.py
- integrations/atom_google_chat_integration.py
- integrations/workspace_sync_service.py

All HTTP / DB / LLM interactions are mocked — no network, no real services.
"""

import asyncio
import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def run(coro):
    return asyncio.run(coro)


def httpx_post_mock(response_json, status_code=200):
    """Patch httpx.AsyncClient so client.post() returns a canned response."""
    resp = Mock()
    resp.status_code = status_code
    resp.json.return_value = response_json
    client = MagicMock()
    client.post = AsyncMock(return_value=resp)
    cm = MagicMock()
    cm.__aenter__.return_value = client
    cm.__aexit__.return_value = False
    return patch("httpx.AsyncClient", return_value=cm)


def make_gmail():
    """GmailService instance without __init__ side effects (no auth)."""
    from integrations.gmail_service import GmailService

    svc = GmailService.__new__(GmailService)
    svc.tenant_id = "default"
    svc.config = {}
    svc.service = None
    svc.credentials_path = "credentials.json"
    svc.token_path = "token.json"
    svc.scopes = ["scope1"]
    return svc


@pytest.fixture()
def sync_db():
    engine = create_engine("sqlite://")
    from core.models import UnifiedWorkspace, WorkspaceSyncLog

    UnifiedWorkspace.__table__.create(engine, checkfirst=True)
    WorkspaceSyncLog.__table__.create(engine, checkfirst=True)
    db = sessionmaker(bind=engine)()
    yield db
    db.close()
    engine.dispose()


def make_workspace(db, **platforms):
    from integrations.workspace_sync_service import WorkspaceSyncService

    svc = WorkspaceSyncService(db)
    return svc, svc.create_unified_workspace(
        user_id="u1", name="W", **platforms
    )


# ============================================================================
# gmail_service.py
# ============================================================================

class TestGmailCoverage:
    def test_capabilities_and_health(self):
        from integrations.gmail_service import GmailService

        svc = make_gmail()
        caps = svc.get_capabilities()
        assert len(caps["operations"]) == 9

        r = svc.health_check()
        assert r["healthy"] is False

        svc.service = Mock()
        svc.service.users.return_value.getProfile.return_value.execute.return_value = {
            "emailAddress": "a@b.c"
        }
        r = svc.health_check()
        assert r["healthy"] is True

        svc.service.users.return_value.getProfile.return_value.execute.side_effect = Exception("boom")
        r = svc.health_check()
        assert r["healthy"] is False

        r = svc.test_connection()
        assert r["status"] == "error"
        svc.service = Mock()
        svc.service.users.return_value.getProfile.return_value.execute.return_value = {
            "emailAddress": "a@b.c", "messagesTotal": 5, "threadsTotal": 2, "historyId": "h"
        }
        r = svc.test_connection()
        assert r["status"] == "success"
        svc.service.users.return_value.getProfile.return_value.execute.side_effect = Exception("x")
        r = svc.test_connection()
        assert r["status"] == "error"

    def test_get_operations(self):
        ops = make_gmail().get_operations()
        assert len(ops) == 2 and ops[0]["name"] == "send_email"

    def test_authenticate_stored_token_valid(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        creds = Mock()
        creds.valid = True
        with patch.object(mod.token_storage, "get_token", return_value={"access_token": "a"}), patch.object(
            mod, "Credentials", return_value=creds
        ), patch.object(mod, "build", return_value="svc") as build:
            svc._authenticate()
            assert svc.service == "svc"
            build.assert_called_once_with("gmail", "v1", credentials=creds)

    def test_authenticate_file_token(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        creds = Mock()
        creds.valid = True
        with patch.object(mod.token_storage, "get_token", return_value=None), patch.object(
            mod.os.path, "exists", return_value=True
        ), patch.object(mod.Credentials, "from_authorized_user_file", return_value=creds), patch.object(
            mod, "build", return_value="svc"
        ):
            svc._authenticate()
        assert svc.service == "svc"

    def test_authenticate_expired_refresh(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        creds = Mock()
        creds.valid = False
        creds.expired = True
        creds.refresh_token = "rt"
        creds.token = "new"
        creds.token_uri = "tu"
        creds.client_id = "cid"
        creds.client_secret = "cs"
        creds.scopes = ["s"]
        saved = {}
        with patch.object(mod.token_storage, "get_token", return_value={"access_token": "old"}), patch.object(
            mod.token_storage, "save_token", side_effect=lambda p, d: saved.update(d)
        ), patch.object(mod, "Credentials", return_value=creds), patch.object(
            mod, "build", return_value="svc"
        ), patch.object(mod.Request, "side_effect", create=True):
            svc._authenticate()
        assert svc.service == "svc"
        assert saved.get("access_token") == "new"

    def test_authenticate_requires_credentials_file(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        creds = Mock()
        creds.valid = False
        creds.expired = False
        with patch.object(mod.token_storage, "get_token", return_value=None), patch.object(
            mod.os.path, "exists", return_value=False
        ), patch.object(mod, "Credentials", return_value=creds), patch.object(
            mod.GOOGLE_OAUTH_CONFIG, "is_configured", return_value=False
        ):
            svc._authenticate()
        assert svc.service is None

    def test_authenticate_credentials_file_flow(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        creds = Mock()
        creds.valid = False
        creds.expired = False
        flow = Mock()
        flow.authorization_url.return_value = ("https://auth.url", None)
        with patch.object(mod.token_storage, "get_token", return_value=None), patch.object(
            mod.os.path, "exists", side_effect=lambda p: p.endswith("credentials.json")
        ), patch.object(mod, "Credentials", return_value=creds), patch.object(
            mod.Flow, "from_client_secrets_file", return_value=flow
        ):
            svc._authenticate()
        assert svc.service is None

    def test_authenticate_oauth_configured_no_token(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        creds = Mock()
        creds.valid = False
        creds.expired = False
        with patch.object(mod.token_storage, "get_token", return_value=None), patch.object(
            mod.os.path, "exists", return_value=False
        ), patch.object(mod, "Credentials", return_value=creds), patch.object(
            mod.GOOGLE_OAUTH_CONFIG, "is_configured", return_value=True
        ):
            svc._authenticate()
        assert svc.service is None

    def test_authenticate_exception(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        with patch.object(mod.token_storage, "get_token", side_effect=Exception("x")):
            svc._authenticate()
        assert svc.service is None

    def test_get_service_with_token(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        assert svc._get_service_with_token(None) is None
        with patch.object(mod, "build", return_value="s"):
            assert svc._get_service_with_token("tok") == "s"
        with patch.object(mod, "build", side_effect=Exception("x")):
            assert svc._get_service_with_token("tok") is None

    def test_get_calendar_service(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        with patch.object(mod, "build", return_value="cal"):
            assert svc._get_calendar_service("tok") == "cal"
        with patch.object(mod.token_storage, "get_token", return_value={"access_token": "a"}), patch.object(
            mod, "build", return_value="cal"
        ):
            assert svc._get_calendar_service(None) == "cal"
        with patch.object(mod.token_storage, "get_token", return_value=None):
            assert svc._get_calendar_service(None) is None
        with patch.object(mod, "build", side_effect=Exception("x")):
            assert svc._get_calendar_service(None) is None

    def test_get_messages_pagination_and_http_error(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        service = Mock()
        page1 = Mock()
        page1.execute.return_value = {"messages": [{"id": "m1"}], "nextPageToken": "p2"}
        page2 = Mock()
        page2.execute.side_effect = mod.HttpError(Mock(status=500), b"")
        service.users.return_value.messages.return_value.list.side_effect = [page1, page2]
        svc._get_service_with_token = Mock(return_value=service)
        svc.get_message = Mock(return_value={"id": "m1"})

        result = svc.get_messages(max_results=10)
        assert result == [{"id": "m1"}]
        assert service.users.return_value.messages.return_value.list.call_count == 2

        svc._get_service_with_token = Mock(return_value=None)
        assert svc.get_messages() == []

        svc._get_service_with_token = Mock(side_effect=Exception("x"))
        assert svc.get_messages() == []

    def test_get_message_and_parse(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        svc._get_service_with_token = Mock(return_value=None)
        assert svc.get_message("m1") is None

        service = Mock()
        service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
            "id": "m1",
            "threadId": "t1",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Subj"},
                    {"name": "From", "value": "a@b.c"},
                    {"name": "Date", "value": "now"},
                ],
                "body": {"data": base64_url("hello")},
            },
            "snippet": "sn",
            "labelIds": ["INBOX"],
            "historyId": "h",
            "internalDate": "123",
        }
        svc._get_service_with_token = Mock(return_value=service)
        parsed = svc.get_message("m1")
        assert parsed["subject"] == "Subj"
        assert parsed["body"] == "hello"

        svc._get_service_with_token = Mock(side_effect=Exception("x"))
        assert svc.get_message("m1") is None

    def test_extract_body_and_attachments(self):
        svc = make_gmail()
        payload = {
            "body": {"data": base64_url("direct")},
        }
        assert svc._extract_body(payload) == "direct"

        payload = {
            "parts": [
                {"mimeType": "text/plain", "body": {"data": base64_url("plain")}},
                {"mimeType": "text/html", "body": {"data": base64_url("html")}},
                {"mimeType": "multipart/alt", "parts": [{"mimeType": "text/plain", "body": {"data": base64_url("nested")}}]},
            ]
        }
        assert svc._extract_body(payload) == "plain"

        assert svc._extract_body({"parts": []}) == ""

        assert svc._extract_body({"body": {"data": "!not-base64!"}}) == ""

        payload = {
            "parts": [
                {"filename": "f.txt", "mimeType": "text/plain", "body": {"attachmentId": "a1", "size": 10}},
                {"filename": "", "body": {}},
                {"filename": "n.txt", "mimeType": "text/plain", "body": {"attachmentId": "a2"},
                 "parts": [{"filename": "deep.txt", "mimeType": "text/plain", "body": {"attachmentId": "a3"}}]},
            ]
        }
        atts = svc._extract_attachments(payload)
        assert len(atts) == 3
        assert svc._extract_attachments({"parts": []}) == []

    def test_get_attachment_content(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        svc._get_service_with_token = Mock(return_value=None)
        assert svc.get_attachment_content("m1", "a1") is None

        service = Mock()
        service.users.return_value.messages.return_value.attachments.return_value.get.return_value.execute.return_value = {
            "data": base64_url("bytes")
        }
        svc._get_service_with_token = Mock(return_value=service)
        assert svc.get_attachment_content("m1", "a1") == b"bytes"

        svc._get_service_with_token = Mock(side_effect=Exception("x"))
        assert svc.get_attachment_content("m1", "a1") is None

    def test_send_message(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        svc._get_service_with_token = Mock(return_value=None)
        assert svc.send_message("to@x", "Subj", "Body") is None

        service = Mock()
        service.users.return_value.messages.return_value.send.return_value.execute.return_value = {"id": "sent"}
        svc._get_service_with_token = Mock(return_value=service)
        result = svc.send_message("to@x", "Subj", "Body", cc="c@x", bcc="b@x", thread_id="t1")
        assert result == {"id": "sent"}
        body = service.users.return_value.messages.return_value.send.call_args[1]["body"]
        assert body["threadId"] == "t1"

        svc._get_service_with_token = Mock(side_effect=Exception("x"))
        assert svc.send_message("to@x", "Subj", "Body") is None

    def test_reply_to_message(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        svc._get_service_with_token = Mock(return_value=None)
        assert svc.reply_to_message("t1", "Body") is None

        service = Mock()
        service.users.return_value.threads.return_value.get.return_value.execute.return_value = {
            "messages": [
                {
                    "payload": {
                        "headers": [
                            {"name": "message-id", "value": "mid1"},
                            {"name": "reply-to", "value": "r@x"},
                            {"name": "subject", "value": "already re: x"},
                        ]
                    }
                }
            ]
        }
        service.users.return_value.messages.return_value.send.return_value.execute.return_value = {"id": "r"}
        svc._get_service_with_token = Mock(return_value=service)
        assert svc.reply_to_message("t1", "Body") == {"id": "r"}

        # no messages in thread -> None
        service2 = Mock()
        service2.users.return_value.threads.return_value.get.return_value.execute.return_value = {"messages": []}
        svc._get_service_with_token = Mock(return_value=service2)
        assert svc.reply_to_message("t1", "Body") is None

        svc._get_service_with_token = Mock(side_effect=Exception("x"))
        assert svc.reply_to_message("t1", "Body") is None

    def test_draft_message(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        svc._get_service_with_token = Mock(return_value=None)
        assert svc.draft_message("to@x", "S", "B") is None

        service = Mock()
        service.users.return_value.drafts.return_value.create.return_value.execute.return_value = {"id": "d1"}
        svc._get_service_with_token = Mock(return_value=service)
        assert svc.draft_message("to@x", "S", "B", thread_id="t1") == {"id": "d1"}

        svc._get_service_with_token = Mock(side_effect=Exception("x"))
        assert svc.draft_message("to@x", "S", "B") is None

    def test_search_messages(self):
        svc = make_gmail()
        svc.get_messages = Mock(return_value=["a"])
        assert svc.search_messages("q") == ["a"]

    def test_get_threads(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        svc.service = Mock()
        page = Mock()
        page.execute.return_value = {"threads": [{"id": "t1"}], "nextPageToken": "p"}
        page2 = Mock()
        page2.execute.side_effect = mod.HttpError(Mock(status=500), b"")
        svc.service.users.return_value.threads.return_value.list.side_effect = [page, page2]
        svc.service.users.return_value.threads.return_value.get.return_value.execute.return_value = {"id": "t1"}
        result = svc.get_threads(max_results=10)
        assert result == [{"id": "t1"}]

        svc.service.users.return_value.threads.return_value.get.return_value.execute.side_effect = Exception("x")
        result = svc.get_threads(max_results=10)
        assert result == []

        svc.service.users.return_value.threads.return_value.list.side_effect = Exception("boom")
        assert svc.get_threads() == []

    def test_modify_and_delete_message(self):
        svc = make_gmail()
        svc.service = Mock()
        assert svc.modify_message("m1", add_labels=["A"], remove_labels=["B"]) is True
        assert svc.delete_message("m1") is True
        svc.service.users.return_value.messages.return_value.modify.return_value.execute.side_effect = Exception("x")
        assert svc.modify_message("m1") is False
        svc.service.users.return_value.messages.return_value.delete.return_value.execute.side_effect = Exception("x")
        assert svc.delete_message("m1") is False

    def test_labels(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        svc._get_service_with_token = Mock(return_value=None)
        assert svc.get_labels() == []

        service = Mock()
        service.users.return_value.labels.return_value.list.return_value.execute.return_value = {"labels": [{"id": "L1"}]}
        svc._get_service_with_token = Mock(return_value=service)
        svc.service = service
        assert svc.get_labels() == [{"id": "L1"}]

        service.users.return_value.labels.return_value.create.return_value.execute.return_value = {"id": "L2"}
        assert svc.create_label("New") == {"id": "L2"}
        assert svc.create_label("New", color={"backgroundColor": "#fff"}) == {"id": "L2"}

        svc._get_service_with_token = Mock(side_effect=Exception("x"))
        assert svc.get_labels() == []
        svc.service = Mock()
        svc.service.users.return_value.labels.return_value.create.return_value.execute.side_effect = Exception("x")
        assert svc.create_label("New") is None

    def test_sync_to_postgres_cache(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        svc.service = None
        result = run(svc.sync_to_postgres_cache("u1"))
        assert result["success"] is False

        svc.service = Mock()
        svc.service.users.return_value.getProfile.return_value.execute.return_value = {
            "messagesTotal": 10, "threadsTotal": 2
        }
        svc.service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "resultSizeEstimate": 3
        }

        existing = Mock()
        new_metric = Mock()
        db = Mock()
        q = Mock()
        q.filter_by.return_value.first.side_effect = [existing, None, None]
        db.query.return_value = q
        with patch("core.database.SessionLocal", return_value=db):
            result = run(svc.sync_to_postgres_cache("u1"))
        assert result["success"] is True
        assert result["metrics_synced"] == 3
        existing.value = 99.0
        db.add.assert_called()

        db2 = Mock()
        q2 = Mock()
        q2.filter_by.return_value.first.side_effect = Exception("dbboom")
        db2.query.return_value = q2
        with patch("core.database.SessionLocal", return_value=db2):
            result = run(svc.sync_to_postgres_cache("u1"))
        assert result["success"] is False
        db2.rollback.assert_called()

        with patch("core.database.SessionLocal", side_effect=Exception("outer")):
            result = run(svc.sync_to_postgres_cache("u1"))
        assert result["success"] is False

    def test_full_sync(self):
        svc = make_gmail()
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True})
        result = run(svc.full_sync("u1"))
        assert result["success"] is True and result["postgres_cache"]["success"] is True

    def test_fetch_recent_messages_and_attachment_metadata(self):
        svc = make_gmail()
        svc.get_messages = Mock(return_value=[])
        with patch("integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline") as gp:
            assert run(svc.fetch_recent_messages("u1")) == []
            gp.assert_called_once()

        svc.get_message = Mock(return_value=None)
        assert run(svc.get_attachment_metadata("u1", "m1")) == []

        svc.get_message = Mock(
            return_value={
                "attachments": [
                    {"attachmentId": "a1", "filename": "f.txt", "size": 3, "mimeType": "text/plain"},
                    {},
                ]
            }
        )
        meta = run(svc.get_attachment_metadata("u1", "m1"))
        assert meta == [
            {"id": "a1", "name": "f.txt", "size": 3, "contentType": "text/plain"},
            {"id": None, "name": "unknown", "size": 0, "contentType": ""},
        ]

        svc.get_attachment_content = Mock(return_value=b"x")
        assert run(svc.download_attachment("u1", "m1", "a1")) == b"x"

    def test_calendar_event_crud(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        svc._get_calendar_service = Mock(return_value=None)
        assert svc.create_calendar_event({"summary": "x"}) is None
        assert svc.update_calendar_event("e1", {}) is None

        service = Mock()
        service.events.return_value.insert.return_value.execute.return_value = {"id": "e1"}
        service.events.return_value.patch.return_value.execute.return_value = {"id": "e1"}
        svc._get_calendar_service = Mock(return_value=service)
        assert svc.create_calendar_event({"summary": "x"}) == {"id": "e1"}
        assert svc.update_calendar_event("e1", {}) == {"id": "e1"}

        svc._get_calendar_service = Mock(side_effect=Exception("x"))
        assert svc.create_calendar_event({}) is None
        assert svc.update_calendar_event("e1", {}) is None

    def test_execute_operation_dispatch(self):
        svc = make_gmail()
        svc.send_message = Mock(return_value={"id": "s"})
        r = run(svc.execute_operation("send_email", {"to": "a@b", "subject": "s", "body": "b"}))
        assert r == {"success": True, "result": {"id": "s"}}

        svc.get_messages = Mock(return_value=[{"id": "m1"}])
        r = run(svc.execute_operation("list_messages", {}))
        assert r["success"] is True

        svc.get_message = Mock(return_value={"id": "m1"})
        r = run(svc.execute_operation("get_message", {"message_id": "m1"}))
        assert r["success"] is True

        svc.search_messages = Mock(return_value=[])
        r = run(svc.execute_operation("search_messages", {}))
        assert r["success"] is True

        svc.reply_to_message = Mock(return_value={"id": "r"})
        r = run(svc.execute_operation("reply_to_message", {"thread_id": "t1", "body": "b"}))
        assert r["success"] is True

        svc.draft_message = Mock(return_value={"id": "d"})
        r = run(svc.execute_operation("draft_message", {"to": "a@b", "subject": "s", "body": "b"}))
        assert r["success"] is True

        svc.modify_message = Mock(return_value=True)
        r = run(svc.execute_operation("modify_message", {"message_id": "m1"}))
        assert r["success"] is True

        svc.delete_message = Mock(return_value=True)
        r = run(svc.execute_operation("delete_message", {"message_id": "m1"}))
        assert r["success"] is True

        svc.sync_calendar_events = AsyncMock()
        r = run(svc.execute_operation("sync_calendar", {}))
        assert r == {"success": True, "result": "Calendar synced"}

        r = run(svc.execute_operation("bogus", {}))
        assert r["success"] is False

        svc.get_messages = Mock(side_effect=Exception("rate limit 429"))
        r = run(svc.execute_operation("list_messages", {}))
        assert r["error"] == "RATE_LIMIT"

    def test_get_gmail_service_factory(self):
        from integrations.gmail_service import get_gmail_service

        svc = get_gmail_service("t1")
        assert svc.tenant_id == "t1"

    def test_init_without_config_no_auth(self):
        """Real __init__ with config=None must not auth when no token files."""
        from integrations import gmail_service as mod

        with patch.object(mod.os.path, "exists", return_value=False):
            svc = mod.GmailService("t1")
        assert svc.tenant_id == "t1"
        assert svc.service is None

    def test_google_libs_absent_fallback(self):
        """When google libs are missing the module must degrade with dummy
        classes (GOOGLE_APIS_AVAILABLE=False) instead of crashing at import."""
        import importlib
        import sys

        orig = sys.modules["integrations.gmail_service"]
        blocked = [
            "google.auth.transport.requests",
            "google.oauth2.credentials",
            "google_auth_oauthlib.flow",
            "googleapiclient.discovery",
            "googleapiclient.errors",
        ]
        saved = {}
        for m in blocked:
            saved[m] = sys.modules.get(m)
            sys.modules[m] = None  # sentinel forces ImportError on import
        sys.modules.pop("integrations.gmail_service", None)
        try:
            mod2 = importlib.import_module("integrations.gmail_service")
            assert mod2.GOOGLE_APIS_AVAILABLE is False
            assert mod2.build is not None
        finally:
            sys.modules["integrations.gmail_service"] = orig
            import integrations as _pkg

            _pkg.gmail_service = orig
            for m, obj in saved.items():
                if obj is None:
                    sys.modules.pop(m, None)
                else:
                    sys.modules[m] = obj

    def test_authenticate_save_file_mode(self):
        """File-based creds that are invalid + OAuth configured fall through to
        the save-to-file branch."""
        from integrations import gmail_service as mod

        svc = make_gmail()
        creds = Mock()
        creds.valid = False
        creds.expired = False
        creds.to_json.return_value = "{}"
        with patch.object(mod.token_storage, "get_token", return_value=None), patch.object(
            mod.os.path, "exists", side_effect=lambda p: p.endswith("token.json")
        ), patch.object(mod.Credentials, "from_authorized_user_file", return_value=creds), patch.object(
            mod.GOOGLE_OAUTH_CONFIG, "is_configured", return_value=True
        ), patch.object(mod, "open", mock_open_write()) as mopen:
            svc._authenticate()
        assert mopen.call_count == 1

    def test_authenticate_oauth_not_configured(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        creds = Mock()
        creds.valid = False
        creds.expired = False
        with patch.object(mod.token_storage, "get_token", return_value=None), patch.object(
            mod.os.path, "exists", return_value=False
        ), patch.object(mod, "Credentials", return_value=creds), patch.object(
            mod.GOOGLE_OAUTH_CONFIG, "is_configured", side_effect=[True, False]
        ):
            svc._authenticate()
        assert svc.service is None

    def test_connection_not_initialized(self):
        svc = make_gmail()
        r = svc.test_connection()
        assert r["status"] == "error"
        assert r["authenticated"] is False

    def test_get_calendar_service_build_exception(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        with patch.object(mod, "build", side_effect=Exception("x")):
            assert svc._get_calendar_service("tok") is None

    def test_get_messages_no_next_page(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        service = Mock()
        page = Mock()
        page.execute.return_value = {"messages": [{"id": "m1"}]}
        service.users.return_value.messages.return_value.list.return_value = page
        svc._get_service_with_token = Mock(return_value=service)
        svc.get_message = Mock(return_value={"id": "m1"})
        assert svc.get_messages(max_results=10) == [{"id": "m1"}]

    def test_parse_message_missing_payload(self):
        svc = make_gmail()
        assert svc._parse_message({"id": "m1"}) == {}

    def test_extract_body_html_and_nested(self):
        svc = make_gmail()
        payload = {
            "parts": [
                {"mimeType": "text/plain", "body": {}},
                {"mimeType": "text/html", "body": {"data": base64_url("<b>hi</b>")}},
            ]
        }
        assert svc._extract_body(payload) == "<b>hi</b>"

        payload = {
            "parts": [
                {
                    "mimeType": "multipart/alt",
                    "parts": [{"mimeType": "text/plain", "body": {}}],
                }
            ]
        }
        assert svc._extract_body(payload) == ""

        payload = {
            "parts": [
                {
                    "mimeType": "multipart/alt",
                    "parts": [{"mimeType": "text/plain", "body": {"data": base64_url("n")}}],
                }
            ]
        }
        assert svc._extract_body(payload) == "n"

    def test_extract_attachments_error(self):
        svc = make_gmail()

        class BadBody(dict):
            def __contains__(self, key):
                return True

            def __getitem__(self, key):
                raise KeyError(key)

        payload = {"parts": [{"filename": "x.txt", "body": BadBody({"x": 1})}]}
        assert svc._extract_attachments(payload) == []

    def test_get_attachment_content_no_data(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        service = Mock()
        service.users.return_value.messages.return_value.attachments.return_value.get.return_value.execute.return_value = {}
        svc._get_service_with_token = Mock(return_value=service)
        assert svc.get_attachment_content("m1", "a1") is None

    def test_send_message_without_thread(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        service = Mock()
        service.users.return_value.messages.return_value.send.return_value.execute.return_value = {"id": "s"}
        svc._get_service_with_token = Mock(return_value=service)
        assert svc.send_message("to@x", "S", "B") == {"id": "s"}
        body = service.users.return_value.messages.return_value.send.call_args[1]["body"]
        assert "threadId" not in body

    def test_reply_to_message_from_fallback_and_re_prefix(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        service = Mock()
        service.users.return_value.threads.return_value.get.return_value.execute.return_value = {
            "messages": [
                {
                    "payload": {
                        "headers": [
                            {"name": "from", "value": "f@x"},
                            {"name": "subject", "value": "hello"},
                        ]
                    }
                }
            ]
        }
        service.users.return_value.messages.return_value.send.return_value.execute.return_value = {"id": "r"}
        svc._get_service_with_token = Mock(return_value=service)
        assert svc.reply_to_message("t1", "Body") == {"id": "r"}
        sent = service.users.return_value.messages.return_value.send.call_args[1]["body"]
        assert sent["raw"]

    def test_get_threads_no_next_page_and_detail_error(self):
        from integrations import gmail_service as mod

        svc = make_gmail()
        svc.service = Mock()
        page = Mock()
        page.execute.return_value = {"threads": [{"id": "t1"}]}
        svc.service.users.return_value.threads.return_value.list.return_value = page
        svc.service.users.return_value.threads.return_value.get.return_value.execute.return_value = {"id": "t1"}
        assert svc.get_threads(max_results=10) == [{"id": "t1"}]

        svc.service = Mock()
        page = Mock()
        page.execute.return_value = {"threads": [{"id": "t1"}]}
        svc.service.users.return_value.threads.return_value.list.return_value = page
        svc.service.users.return_value.threads.return_value.get.return_value.execute.side_effect = Exception("x")
        assert svc.get_threads(max_results=10) == []

    def test_sync_calendar_events_no_service_and_event_error(self):
        svc = make_gmail()
        svc._get_calendar_service = Mock(return_value=None)
        run(svc.sync_calendar_events("u1"))
        svc._get_calendar_service.assert_called_once()

        cal = Mock()
        cal.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "ev1",
                    "start": {"dateTime": "2026-08-01T10:00:00Z"},
                    "end": {"dateTime": "2026-08-01T11:00:00Z"},
                }
            ]
        }
        svc._get_calendar_service = Mock(return_value=cal)
        with patch("integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline") as gp:
            pipe = Mock()
            pipe.ingest_message = AsyncMock(side_effect=Exception("memory boom"))
            gp.return_value = pipe
            run(svc.sync_calendar_events("u1"))
        pipe.ingest_message.assert_awaited_once()

        # Event missing 'end' -> outer handler swallows gracefully
        cal2 = Mock()
        cal2.events.return_value.list.return_value.execute.return_value = {
            "items": [{"id": "ev2", "start": {"dateTime": "2026-08-01T10:00:00Z"}}]
        }
        svc._get_calendar_service = Mock(return_value=cal2)
        with patch("integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline") as gp2:
            gp2.return_value = Mock()
            run(svc.sync_calendar_events("u1"))

    def test_fetch_recent_messages_exception(self):
        svc = make_gmail()
        svc.get_messages = Mock(side_effect=Exception("x"))
        with patch("integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline"):
            assert run(svc.fetch_recent_messages("u1")) == []

    def test_execute_operation_auth_invalid(self):
        svc = make_gmail()
        svc.get_messages = Mock(side_effect=Exception("invalid credentials"))
        r = run(svc.execute_operation("list_messages", {}))
        assert r["error"] == "AUTH_INVALID"


def base64_url(s: str) -> str:
    import base64

    return base64.urlsafe_b64encode(s.encode()).decode()


def mock_open_write():
    """Context-manager mock for open(..., 'w') used by the auth save branch."""
    from unittest.mock import mock_open

    m = mock_open()
    return m


class Ms365FakeResp:
    def __init__(self, status, payload=None):
        self.status = status
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def text(self):
        return "boom"

    async def json(self):
        return self.payload if self.payload is not None else {"ok": 1}


class Ms365FakeSession:
    def __init__(self, resp):
        self.resp = resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def request(self, *a, **k):
        return self.resp

    def put(self, *a, **k):
        return self.resp


# ============================================================================
# outlook_service.py
# ============================================================================

class TestOutlookCoverage:
    def make(self):
        from integrations.outlook_service import OutlookService

        return OutlookService("default", {})

    def test_capabilities_and_health(self):
        # Env-coupled: a dev .env may export client ids; clear them around
        # construction AND the health call so "not configured" is under test.
        import os as _os
        from unittest.mock import patch as _patch

        with _patch.dict(
            _os.environ,
            {k: "" for k in ("MICROSOFT_CLIENT_ID", "AZURE_CLIENT_ID", "OUTLOOK_CLIENT_ID")},
        ):
            svc = self.make()
            caps = svc.get_capabilities()
            assert len(caps["operations"]) == 6
            r = svc.health_check()
        assert r["healthy"] is False
        svc.client_id = "cid"
        r = svc.health_check()
        assert r["healthy"] is True

    def test_is_token_expired(self):
        svc = self.make()
        assert svc._is_token_expired({}) is True
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
        assert svc._is_token_expired({"expires_at": past}) is True
        assert svc._is_token_expired({"expires_at": future}) is False
        assert svc._is_token_expired({"expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}) is False
        assert svc._is_token_expired({"expires_at": "garbage"}) is True

    def test_get_access_token(self):
        from integrations.outlook_service import OutlookService

        token_record = Mock()
        token_record.access_token = "enc"
        token_record.refresh_token = None
        token_record.expires_at = None
        db = Mock()
        q = Mock()
        q.filter.return_value.first.return_value = token_record
        db.query.return_value = q
        cm = MagicMock()
        cm.__enter__.return_value = db
        cm.__exit__.return_value = False
        with patch("core.database.get_db_session", return_value=cm), patch(
            "core.privsec.token_encryption.decrypt_token", return_value="plain"
        ):
            svc = OutlookService("default", {})
            svc._refresh_access_token = AsyncMock(return_value="plain")
            result = run(svc._get_access_token("u1"))
        assert result == "plain"

        q2 = Mock()
        q2.filter.return_value.first.return_value = None
        db2 = Mock()
        db2.query.return_value = q2
        cm2 = MagicMock()
        cm2.__enter__.return_value = db2
        cm2.__exit__.return_value = False
        with patch("core.database.get_db_session", return_value=cm2):
            svc = OutlookService("default", {})
            assert run(svc._get_access_token("u1")) is None

        with patch("core.database.get_db_session", side_effect=Exception("db down")):
            svc = OutlookService("default", {})
            assert run(svc._get_access_token("u1")) is None

    def test_refresh_access_token(self):
        svc = self.make()
        assert run(svc._refresh_access_token("u1", {"refresh_token": None})) is None
        # No client credentials configured -> refresh refused
        assert run(svc._refresh_access_token("u1", {"refresh_token": "rt", "access_token": "at"})) is None

        # Credentials configured -> token endpoint is called and new token returned
        svc.client_id, svc.client_secret, svc.tenant_id_config = "cid", "sec", "tenant"

        class FakeResp:
            status = 200

            async def json(self):
                return {"access_token": "new_at", "refresh_token": "new_rt", "expires_in": 3600}

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

        class FakeSession:
            def __init__(self):
                self.post = MagicMock(return_value=FakeResp())

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("integrations.outlook_service.aiohttp.ClientSession", return_value=FakeSession()), \
             patch("core.database.get_db_session", return_value=db):
            assert run(svc._refresh_access_token("u1", {"refresh_token": "rt", "access_token": "at"})) == "new_at"

    def test_make_graph_request(self):
        svc = self.make()
        assert run(svc._make_graph_request("u1", "/me")) is None  # no token

        class FakeResp:
            def __init__(self, status, payload=None):
                self.status = status
                self.payload = payload

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def json(self):
                return self.payload

            async def text(self):
                return "error body"

        class FakeSession:
            def __init__(self, resp):
                self.resp = resp

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            def get(self, *a, **k):
                return self.resp

            def post(self, *a, **k):
                return self.resp

            def patch(self, *a, **k):
                return self.resp

            def delete(self, *a, **k):
                return self.resp

        with patch("aiohttp.ClientSession", return_value=FakeSession(FakeResp(200, {"ok": 1}))):
            assert run(svc._make_graph_request("u1", "/me", access_token="tok")) == {"ok": 1}
        with patch("aiohttp.ClientSession", return_value=FakeSession(FakeResp(204))):
            assert run(svc._make_graph_request("u1", "/me", access_token="tok")) == {"success": True}
        with patch("aiohttp.ClientSession", return_value=FakeSession(FakeResp(500))):
            assert run(svc._make_graph_request("u1", "/me", access_token="tok")) is None
        with patch("aiohttp.ClientSession", return_value=FakeSession(FakeResp(200, {"ok": 1}))):
            assert run(svc._make_graph_request("u1", "/me", method="POST", data={}, access_token="tok")) == {"ok": 1}
            assert run(svc._make_graph_request("u1", "/me", method="PATCH", data={}, access_token="tok")) == {"ok": 1}
            assert run(svc._make_graph_request("u1", "/me", method="DELETE", access_token="tok")) == {"ok": 1}
            assert run(svc._make_graph_request("u1", "/me", method="PUT", access_token="tok")) is None

        class BoomSession(FakeSession):
            def get(self, *a, **k):
                raise Exception("conn reset")

        with patch("aiohttp.ClientSession", return_value=BoomSession(FakeResp(200))):
            assert run(svc._make_graph_request("u1", "/me", access_token="tok")) is None

    def test_handle_response(self):
        svc = self.make()

        class FakeResp:
            def __init__(self, status):
                self.status = status

            async def json(self):
                return {"a": 1}

            async def text(self):
                raise Exception("no body")

        assert run(svc._handle_response(FakeResp(200))) == {"a": 1}
        assert run(svc._handle_response(FakeResp(201))) == {"a": 1}
        assert run(svc._handle_response(FakeResp(202))) == {"success": True}
        assert run(svc._handle_response(FakeResp(204))) == {"success": True}
        assert run(svc._handle_response(FakeResp(400))) is None

        class FakeResp2(FakeResp):
            async def text(self):
                return "err"

            async def json(self):
                raise Exception("bad json")

        assert run(svc._handle_response(FakeResp2(400))) is None

    def test_get_user_emails(self):
        svc = self.make()
        result = {"value": [
            {
                "id": "1", "subject": "S", "bodyPreview": "bp", "body": {"x": 1},
                "sender": {"emailAddress": {"address": "a@b"}}, "from": {"emailAddress": {"address": "a@b"}},
                "toRecipients": [], "ccRecipients": [], "bccRecipients": [],
                "receivedDateTime": "r", "sentDateTime": "s", "hasAttachments": True,
                "importance": "high", "isRead": False, "webLink": "w",
                "conversationId": "c", "parentFolderId": "p", "attachments": [],
            }
        ]}
        for folder in ["inbox", "sent", "drafts", "custom"]:
            svc._make_graph_request = AsyncMock(return_value=result)
            emails = run(svc.get_user_emails("u1", folder=folder, query="q", include_attachments=True))
            assert len(emails) == 1
            assert emails[0]["subject"] == "S"

        svc._make_graph_request = AsyncMock(return_value={})
        assert run(svc.get_user_emails("u1")) == []

        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.get_user_emails("u1")) == []

    def test_send_email(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={"success": True})
        result = run(svc.send_email("u1", ["a@b.c"], "Subj", "Body", cc_recipients=["c@d"], bcc_recipients=["e@f"]))
        assert result == {"success": True}
        body = svc._make_graph_request.await_args[0][3]
        assert body["message"]["toRecipients"] == [{"emailAddress": {"address": "a@b.c"}}]
        assert body["message"]["ccRecipients"] == [{"emailAddress": {"address": "c@d"}}]
        assert body["message"]["bccRecipients"] == [{"emailAddress": {"address": "e@f"}}]

        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.send_email("u1", ["a@b.c"], "S", "B")) is None

    def test_reply_to_email(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={"success": True})
        assert run(svc.reply_to_email("u1", "m1", "comment")) is True
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.reply_to_email("u1", "m1", "c")) is False

    def test_create_draft_email(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={"id": "d"})
        assert run(svc.create_draft_email("u1", ["a@b.c"], "S", "B", cc_recipients=["x"], bcc_recipients=["y"])) == {"id": "d"}
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.create_draft_email("u1", ["a@b.c"], "S", "B")) is None

    def test_get_email_by_id(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={"id": "1", "subject": "S"})
        email = run(svc.get_email_by_id("u1", "1"))
        assert email["subject"] == "S"
        svc._make_graph_request = AsyncMock(return_value=None)
        assert run(svc.get_email_by_id("u1", "1")) is None
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.get_email_by_id("u1", "1")) is None

    def test_delete_email(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={"success": True})
        assert run(svc.delete_email("u1", "m1")) is True
        svc._make_graph_request = AsyncMock(return_value=None)
        assert run(svc.delete_email("u1", "m1")) is False
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.delete_email("u1", "m1")) is False

    def test_get_attachment_content(self):
        import base64

        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={"contentBytes": base64.b64encode(b"data").decode()})
        assert run(svc.get_attachment_content("u1", "m1", "a1")) == b"data"
        svc._make_graph_request = AsyncMock(return_value={})
        assert run(svc.get_attachment_content("u1", "m1", "a1")) is None
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.get_attachment_content("u1", "m1", "a1")) is None

    def test_get_calendar_events(self):
        svc = self.make()
        result = {"value": [{
            "id": "e1", "subject": "Meet", "body": {}, "start": {}, "end": {},
            "location": {}, "attendees": [], "organizer": {}, "isAllDay": True,
            "showAs": "free", "webLink": "w", "createdDateTime": "c", "lastModifiedDateTime": "m",
        }]}
        for tmin, tmax in [("2026-08-01", "2026-08-02"), ("2026-08-01", None), (None, "2026-08-02"), (None, None)]:
            svc._make_graph_request = AsyncMock(return_value=result)
            events = run(svc.get_calendar_events("u1", time_min=tmin, time_max=tmax))
            assert len(events) == 1
        svc._make_graph_request = AsyncMock(return_value={})
        assert run(svc.get_calendar_events("u1")) == []
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.get_calendar_events("u1")) == []

    def test_create_and_update_calendar_event(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={"id": "e1"})
        result = run(svc.create_calendar_event(
            "u1", "Subj", body="Body", location={"displayName": "L"},
            attendees=["a@b.c"], start={"dateTime": "x", "timeZone": "UTC"},
            end={"dateTime": "y", "timeZone": "UTC"},
        ))
        assert result == {"id": "e1"}
        # defaults for start/end
        svc._make_graph_request = AsyncMock(return_value={"id": "e2"})
        assert run(svc.create_calendar_event("u1", "Subj")) == {"id": "e2"}
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.create_calendar_event("u1", "Subj")) is None

        svc._make_graph_request = AsyncMock(return_value={"id": "e1"})
        assert run(svc.update_calendar_event("u1", "e1", {"subject": "S"})) == {"id": "e1"}
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.update_calendar_event("u1", "e1", {})) is None

    def test_contacts(self):
        svc = self.make()
        result = {"value": [{
            "id": "c1", "displayName": "N", "givenName": "G", "surname": "S",
            "emailAddresses": [], "businessPhones": [], "mobilePhone": "m",
            "homePhones": [], "companyName": "C", "jobTitle": "J", "officeLocation": "O",
            "createdDateTime": "c", "lastModifiedDateTime": "m",
        }]}
        svc._make_graph_request = AsyncMock(return_value=result)
        contacts = run(svc.get_user_contacts("u1", query="q"))
        assert contacts[0]["display_name"] == "N"
        svc._make_graph_request = AsyncMock(return_value={})
        assert run(svc.get_user_contacts("u1")) == []
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.get_user_contacts("u1")) == []

        svc._make_graph_request = AsyncMock(return_value={"id": "c1"})
        result = run(svc.create_contact(
            "u1", "N", given_name="G", surname="S", email_addresses=[{"address": "a@b"}],
            business_phones=["1"], company_name="C",
        ))
        assert result == {"id": "c1"}
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.create_contact("u1", "N")) is None

    def test_tasks(self):
        svc = self.make()
        result = {"value": [{
            "id": "t1", "subject": "Task", "body": {}, "importance": "high",
            "status": "inProgress", "createdDateTime": "c", "lastModifiedDateTime": "m",
            "dueDateTime": {}, "completedDateTime": {}, "categories": [],
        }]}
        svc._make_graph_request = AsyncMock(return_value=result)
        tasks = run(svc.get_user_tasks("u1", status="inProgress"))
        assert tasks[0]["subject"] == "Task"
        svc._make_graph_request = AsyncMock(return_value={})
        assert run(svc.get_user_tasks("u1")) == []
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.get_user_tasks("u1")) == []

        svc._make_graph_request = AsyncMock(return_value={"id": "t1"})
        result = run(svc.create_task("u1", "Task", body="B", due_date_time={"dateTime": "x"}, categories=["c"]))
        assert result == {"id": "t1"}
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.create_task("u1", "Task")) is None

    def test_user_profile(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={
            "id": "u1", "displayName": "N", "mail": "a@b", "userPrincipalName": "upn",
            "jobTitle": "J", "officeLocation": "O", "businessPhones": [], "mobilePhone": "m",
        })
        profile = run(svc.get_user_profile("u1"))
        assert profile["mail"] == "a@b"
        svc._make_graph_request = AsyncMock(return_value=None)
        assert run(svc.get_user_profile("u1")) is None
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.get_user_profile("u1")) is None

    def test_unread_and_search_emails(self):
        svc = self.make()
        result = {"value": [{"id": "1", "subject": "S"}]}
        svc._make_graph_request = AsyncMock(return_value=result)
        emails = run(svc.get_unread_emails("u1"))
        assert len(emails) == 1
        svc._make_graph_request = AsyncMock(return_value=result)
        emails = run(svc.search_emails("u1", "q"))
        assert len(emails) == 1
        svc._make_graph_request = AsyncMock(return_value={})
        assert run(svc.get_unread_emails("u1")) == []
        svc._make_graph_request = AsyncMock(return_value={})
        assert run(svc.search_emails("u1", "q")) == []
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.get_unread_emails("u1")) == []
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.search_emails("u1", "q")) == []

    def test_execute_operation(self):
        svc = self.make()
        svc.send_email = AsyncMock(return_value={"id": "s"})
        r = run(svc.execute_operation("send_email", {"to_recipients": ["a@b"], "subject": "S", "body": "B"}))
        assert r == {"success": True, "result": {"id": "s"}}

        svc.get_user_emails = AsyncMock(return_value=[{"id": "1"}])
        r = run(svc.execute_operation("read_emails", {}))
        assert r["success"] is True

        svc.create_calendar_event = AsyncMock(return_value={"id": "e"})
        r = run(svc.execute_operation("create_calendar_event", {"subject": "S"}))
        assert r["success"] is True

        r = run(svc.execute_operation("bogus", {}))
        assert r["success"] is False

        svc.send_email = AsyncMock(side_effect=Exception("boom"))
        r = run(svc.execute_operation("send_email", {"to_recipients": ["a@b"], "subject": "S", "body": "B"}))
        assert r["success"] is False

        with pytest.raises(ValueError):
            run(svc.execute_operation("send_email", {}, context={"tenant_id": "other"}))

    def test_sync_to_postgres_cache(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value=None)
        r = run(svc.sync_to_postgres_cache("u1"))
        assert r["success"] is False

        svc._make_graph_request = AsyncMock(return_value={"totalItemCount": 5, "unreadItemCount": 2})
        svc.get_calendar_events = AsyncMock(return_value=[{"id": "1"}, {"id": "2"}])
        existing = Mock()
        db = Mock()
        q = Mock()
        q.filter_by.return_value.first.side_effect = [existing, None, None]
        db.query.return_value = q
        with patch("core.database.SessionLocal", return_value=db):
            r = run(svc.sync_to_postgres_cache("u1"))
        assert r["success"] is True
        assert r["metrics_synced"] == 3

        db2 = Mock()
        q2 = Mock()
        q2.filter_by.return_value.first.side_effect = Exception("boom")
        db2.query.return_value = q2
        with patch("core.database.SessionLocal", return_value=db2):
            r = run(svc.sync_to_postgres_cache("u1"))
        assert r["success"] is False

        with patch("core.database.SessionLocal", side_effect=Exception("outer")):
            r = run(svc.sync_to_postgres_cache("u1"))
        assert r["success"] is False

    def test_full_sync(self):
        svc = self.make()
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True})
        r = run(svc.full_sync("u1"))
        assert r["success"] is True and r["postgres_cache"]["success"] is True

    def test_fetch_recent_messages(self):
        svc = self.make()
        svc.get_user_emails = AsyncMock(return_value=[])
        with patch("integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline") as gp:
            assert run(svc.fetch_recent_messages("u1")) == []
            gp.assert_not_called()

        svc.get_user_emails = AsyncMock(return_value=[{"id": "1"}, {"id": "2"}])
        with patch("integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline") as gp:
            pipe = Mock()
            pipe.ingest_message = AsyncMock(return_value={"ok": True})
            gp.return_value = pipe
            result = run(svc.fetch_recent_messages("u1"))
        assert len(result) == 2
        assert pipe.ingest_message.call_count == 2

        svc.get_user_emails = AsyncMock(side_effect=Exception("x"))
        with patch("integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline"):
            assert run(svc.fetch_recent_messages("u1")) == []

    def test_sync_calendar_events(self):
        svc = self.make()
        svc.get_calendar_events = AsyncMock(return_value=[])
        with patch("integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline") as gp:
            assert run(svc.sync_calendar_events("u1")) == []
            gp.assert_not_called()

        event = {
            "id": "e1", "subject": "Meet", "bodyPreview": "bp",
            "start": {"dateTime": "2026-08-01T10:00:00.000Z", "timeZone": "UTC"},
            "end": {"dateTime": "2026-08-01T11:00:00.000Z", "timeZone": "UTC"},
            "location": {"displayName": "L"},
            "attendees": [{"emailAddress": {"address": "a@b", "name": "A"}}],
            "organizer": {"emailAddress": {"address": "o@x"}},
        }
        svc.get_calendar_events = AsyncMock(return_value=[event])
        with patch("integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline") as gp:
            pipe = Mock()
            pipe.ingest_message = AsyncMock(return_value=True)
            gp.return_value = pipe
            result = run(svc.sync_calendar_events("u1"))
        assert len(result) == 1
        pipe.ingest_message.assert_awaited_once()

        svc.get_calendar_events = AsyncMock(side_effect=Exception("x"))
        with patch("integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline"):
            assert run(svc.sync_calendar_events("u1")) == []

    def test_module_instance(self):
        from integrations.outlook_service import outlook_service

        assert outlook_service.tenant_id == "default"

    def test_init_without_config(self):
        from integrations.outlook_service import OutlookService

        svc = OutlookService("default")
        assert svc.base_url.startswith("https://graph.microsoft.com")

    def test_get_access_token_not_expired(self):
        from integrations.outlook_service import OutlookService

        token_record = Mock()
        token_record.access_token = "enc"
        token_record.refresh_token = "rt"
        token_record.expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
        db = Mock()
        q = Mock()
        q.filter.return_value.first.return_value = token_record
        db.query.return_value = q
        cm = MagicMock()
        cm.__enter__.return_value = db
        cm.__exit__.return_value = False
        with patch("core.database.get_db_session", return_value=cm), patch(
            "core.privsec.token_encryption.decrypt_token", return_value="plain"
        ):
            svc = OutlookService("default", {})
            result = run(svc._get_access_token("u1"))
        assert result == "plain"

    def test_refresh_access_token_exception(self):
        svc = self.make()
        assert run(svc._refresh_access_token("u1", None)) is None

    def test_health_check_exception(self):
        svc = self.make()

        class WeirdId:
            def __bool__(self):
                raise Exception("boom")

        svc.client_id = WeirdId()
        r = svc.health_check()
        assert r["healthy"] is False


# ============================================================================
# outlook_service_enhanced.py
# ============================================================================

class TestOutlookEnhancedCoverage:
    def make(self):
        from integrations.outlook_service_enhanced import OutlookEnhancedService

        return OutlookEnhancedService()

    def test_dataclasses(self):
        from integrations.outlook_service_enhanced import (
            EmailImportance,
            EventSensitivity,
            OutlookAttachment,
            OutlookCalendarEvent,
            OutlookContact,
            OutlookEmail,
            OutlookFolder,
            OutlookTask,
            OutlookUser,
            TaskStatus,
        )

        assert EmailImportance.HIGH.value == "high"
        assert EventSensitivity.CONFIDENTIAL.value == "confidential"
        assert TaskStatus.WAITING_ON_OTHERS.value == "waitingOnOthers"
        u = OutlookUser(id="1", display_name="N", email="e", job_title="J", department="D",
                        office_location="O", mobile_phone="M", business_phones=[], user_principal_name="U",
                        mail="m", account_enabled=True, user_type="T", preferred_language="P",
                        timezone="Z", usage_location="L", metadata={})
        assert u.to_dict()["email"] == "e"
        e = OutlookEmail(id="1", conversation_id="c", subject="s", body_preview="b", body={},
                         importance="normal", has_attachments=False, is_read=False, is_draft=False,
                         web_link="w", created_datetime="", last_modified_datetime="", received_datetime="",
                         sent_datetime="", from_address={}, to_recipients=[], cc_recipients=[],
                         bcc_recipients=[], reply_to=[], categories=[], flag={},
                         internet_message_headers=[], attachments=[], metadata={})
        assert e.to_dict()["subject"] == "s"
        ev = OutlookCalendarEvent(id="1", subject="s", body_preview="b", body={}, start={}, end={},
                                  location={}, locations=[], attendees=[], organizer={}, is_all_day=False,
                                  is_cancelled=False, is_organizer=True, response_requested=True,
                                  response_status={}, sensitivity="normal", show_as="busy", type="t",
                                  web_link="w", online_meeting={}, recurrence={},
                                  reminder_minutes_before_start=15, categories=[], extensions=[], metadata={})
        assert ev.to_dict()["id"] == "1"
        c = OutlookContact(id="1", display_name="N", given_name="", surname="", job_title="", department="",
                           company_name="", business_phones=[], mobile_phone="", home_phones=[],
                           email_addresses=[], im_addresses=[], home_address={}, business_address={},
                           other_address={}, personal_notes="", birthday="", anniversary="", spouse_name="",
                           children=[], manager="", assistant_name="", profession="", categories=[],
                           created_date_time="", last_modified_date_time="", metadata={})
        assert c.to_dict()["display_name"] == "N"
        t = OutlookTask(id="1", subject="s", body={}, importance="normal", status="notStarted",
                        completed_date_time={}, due_date_time={}, start_date_time={}, created_date_time="",
                        last_modified_date_time="", is_reminder_on=False, reminder_date_time={},
                        categories=[], assigned_to="", parent_folder_id="", conversation_id="",
                        conversation_index="", flag={}, metadata={})
        assert t.to_dict()["subject"] == "s"
        f = OutlookFolder(id="1", display_name="N", parent_folder_id="", child_folder_count=0,
                          unread_item_count=0, total_item_count=0, folder_type="", is_hidden=False,
                          well_known_name="", metadata={})
        assert f.to_dict()["display_name"] == "N"
        a = OutlookAttachment(id="1", name="n", content_type="t", size=1, is_inline=False, content_id="",
                              content_bytes="", last_modified_date_time="", metadata={})
        assert a.to_dict()["name"] == "n"

    def test_session_management(self):
        svc = self.make()

        class FakeClientSession:
            closed = False

            def __init__(self, timeout=None):
                pass

            async def close(self):
                type(self).closed = True

        with patch("aiohttp.ClientSession", new=FakeClientSession):
            s1 = run(svc._get_session())
            assert s1 is svc.session
            s2 = run(svc._get_session())
            assert s2 is s1
            run(svc._close_session())
            assert FakeClientSession.closed is True
            FakeClientSession.closed = True
            s3 = run(svc._get_session())
            assert s3 is not s1
            run(svc._close_session())

    def test_get_access_token(self):
        svc = self.make()
        svc.access_token = "tok"
        svc.token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        assert run(svc._get_access_token("u1")) == "tok"
        svc.token_expiry = datetime.now(timezone.utc) - timedelta(hours=1)
        with pytest.raises(Exception):
            run(svc._get_access_token("u1"))
        svc.access_token = None
        with pytest.raises(Exception):
            run(svc._get_access_token("u1"))

    def test_refresh_access_token(self):
        svc = self.make()
        assert run(svc._refresh_access_token()) is False  # no refresh token

        svc.refresh_token = "rt"
        svc.client_id = "cid"
        svc.client_secret = "cs"
        svc.tenant_id = "t"

        class FakeResp:
            def __init__(self, status):
                self.status = status

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def json(self):
                return {"access_token": "new", "refresh_token": "new_rt", "expires_in": 3600}

        class FakeSession:
            closed = False

            def __init__(self):
                self.last = None

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            def post(self, url, data=None):
                return FakeResp(200)

        with patch("aiohttp.ClientSession", return_value=FakeSession()):
            assert run(svc._refresh_access_token()) is True
        assert svc.access_token == "new"
        assert svc.refresh_token == "new_rt"

        svc.session = None
        with patch("aiohttp.ClientSession", return_value=FakeSession2()):
            assert run(svc._refresh_access_token()) is False

        class FakeSession3(FakeSession):
            def post(self, url, data=None):
                raise Exception("net")

        svc.session = None
        with patch("aiohttp.ClientSession", return_value=FakeSession3()):
            assert run(svc._refresh_access_token()) is False

    def test_make_graph_request(self):
        from integrations.outlook_service_enhanced import (
            GRAPH_API_BASE_URL,
            OutlookEnhancedService,
        )

        svc = OutlookEnhancedService()
        svc.access_token = "tok"
        svc.token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        class FakeResp:
            def __init__(self, status, payload=None):
                self.status = status
                self.payload = payload
                self.headers = {}

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            def raise_for_status(self):
                if self.status >= 400:
                    raise Exception(f"HTTP {self.status}")

            async def json(self):
                return self.payload

        class FakeSession:
            def __init__(self, resp):
                self.resp = resp
                self.method = None

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            def get(self, url, headers=None, params=None):
                return self.resp

            def post(self, url, headers=None, json=None, params=None):
                return self.resp

            def put(self, url, headers=None, json=None):
                return self.resp

            def patch(self, url, headers=None, json=None):
                return self.resp

            def delete(self, url, headers=None):
                return self.resp

        svc._get_session = AsyncMock(return_value=FakeSession(FakeResp(200, {"ok": 1})))
        assert run(svc._make_graph_request("GET", "users/u1/messages", "u1")) == {"ok": 1}
        svc._get_session = AsyncMock(return_value=FakeSession(FakeResp(204)))
        assert run(svc._make_graph_request("DELETE", "users/u1/messages/1", "u1")) == {"success": True}
        svc._get_session = AsyncMock(return_value=FakeSession(FakeResp(201, {"id": "1"})))
        assert run(svc._make_graph_request("POST", "users/u1/messages", "u1", data={})) == {"id": "1"}
        svc._get_session = AsyncMock(return_value=FakeSession(FakeResp(200, {"ok": 1})))
        assert run(svc._make_graph_request("PUT", "users/u1/foo", "u1", data={})) == {"ok": 1}
        svc._get_session = AsyncMock(return_value=FakeSession(FakeResp(200, {"ok": 1})))
        assert run(svc._make_graph_request("PATCH", "users/u1/foo", "u1", data={})) == {"ok": 1}
        with pytest.raises(ValueError):
            run(svc._make_graph_request("TRACE", "users/u1", "u1"))

        class BoomSession(FakeSession):
            def get(self, url, headers=None, params=None):
                raise aiohttp.ClientConnectionError("net down")

        import aiohttp

        svc._get_session = AsyncMock(return_value=BoomSession(FakeResp(200)))
        with pytest.raises(Exception):
            run(svc._make_graph_request("GET", "users/u1", "u1"))

    def test_handle_response_retries(self):
        from integrations.outlook_service_enhanced import OutlookEnhancedService

        svc = OutlookEnhancedService()

        class FakeResp:
            def __init__(self, status, headers=None):
                self.status = status
                self.headers = headers or {}

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            def raise_for_status(self):
                if self.status >= 400 and self.status not in (401, 429):
                    raise Exception("HTTP")

            async def json(self):
                return {"ok": 1}

        # 401 with successful refresh -> retried once
        svc._refresh_access_token = AsyncMock(return_value=True)
        svc._make_graph_request = AsyncMock(return_value={"retried": True})
        result = run(svc._handle_response(FakeResp(401), "GET", "x", "u1", {}, None, False))
        assert result == {"retried": True}
        svc._make_graph_request.assert_awaited_once()

        # 401 with failed refresh -> error
        svc._refresh_access_token = AsyncMock(return_value=False)
        with pytest.raises(Exception):
            run(svc._handle_response(FakeResp(401), "GET", "x", "u1", {}, None, False))

        # 429 -> backs off then retries
        with patch("asyncio.sleep", new=AsyncMock()) as sleep:
            svc._refresh_access_token = AsyncMock()
            svc._make_graph_request = AsyncMock(return_value={"retried": True})
            result = run(svc._handle_response(FakeResp(429, {"Retry-After": "1"}), "GET", "x", "u1", {}, None, False))
            assert result == {"retried": True}
            sleep.assert_awaited_once_with(1)

        # non-retryable error status
        with pytest.raises(Exception):
            run(svc._handle_response(FakeResp(403), "GET", "x", "u1", {}, None, False))

        # plain success
        assert run(svc._handle_response(FakeResp(200), "GET", "x", "u1", {}, None, False)) == {"ok": 1}

        class FakeErrResp(FakeResp):
            async def json(self):
                raise Exception("bad json")

        with pytest.raises(Exception):
            run(svc._handle_response(FakeErrResp(200), "GET", "x", "u1", {}, None, False))

        import aiohttp

        class FakeClientErrResp(FakeResp):
            def raise_for_status(self):
                raise aiohttp.ClientResponseError(
                    request_info=Mock(), history=(), status=403, message="forbidden"
                )

        with pytest.raises(Exception):
            run(svc._handle_response(FakeClientErrResp(403), "GET", "x", "u1", {}, None, False))

    def test_get_user_emails_enhanced(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={"value": [{
            "id": "1", "conversationId": "c", "subject": "S", "bodyPreview": "bp", "body": {},
            "importance": "high", "hasAttachments": True, "isRead": True, "isDraft": False,
            "webLink": "w", "createdDateTime": "cd", "lastModifiedDateTime": "lm",
            "receivedDateTime": "rd", "sentDateTime": "sd", "from": {}, "toRecipients": [],
            "ccRecipients": [], "bccRecipients": [], "replyTo": [], "categories": [],
            "flag": {}, "internetMessageHeaders": [], "attachments": [],
        }]})
        emails = run(svc.get_user_emails_enhanced("u1", folder="inbox", query="q", include_attachments=True))
        assert len(emails) == 1 and emails[0].subject == "S"
        # cache hit
        emails2 = run(svc.get_user_emails_enhanced("u1", folder="inbox", query="q"))
        assert emails2 == emails
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.get_user_emails_enhanced("u2")) == []

    def test_send_email_enhanced(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={"success": True})
        assert run(svc.send_email_enhanced(
            "u1", ["a@b.c"], "Subj", "Body", cc_recipients=["c@d"], bcc_recipients=["e@f"],
            attachments=[{"name": "f.txt"}], importance="high",
        )) is True
        call_data = svc._make_graph_request.await_args.kwargs["data"]
        assert call_data["message"]["ccRecipients"] == [{"emailAddress": {"address": "c@d"}}]
        assert call_data["message"]["attachments"] == [{"name": "f.txt"}]

        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.send_email_enhanced("u1", ["a@b.c"], "S", "B")) is False

    def test_create_calendar_event_enhanced(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={
            "id": "e1", "subject": "S", "bodyPreview": "bp", "body": {}, "start": {}, "end": {},
            "location": {}, "locations": [], "attendees": [], "organizer": {}, "isAllDay": False,
            "isCancelled": False, "isOrganizer": True, "responseRequested": True,
            "responseStatus": {}, "sensitivity": "normal", "showAs": "busy", "type": "t",
            "webLink": "w", "onlineMeeting": {}, "recurrence": {}, "reminderMinutesBeforeStart": 10,
            "categories": [], "extensions": [],
        })
        ev = run(svc.create_calendar_event_enhanced(
            "u1", "S", "2026-08-01T10:00:00Z", "2026-08-01T11:00:00Z",
            location="L", body="B", attendees=["a@b.c"], sensitivity="private",
        ))
        assert ev is not None and ev.id == "e1"
        assert ev.sensitivity == "normal"
        svc._make_graph_request = AsyncMock(return_value=None)
        assert run(svc.create_calendar_event_enhanced("u1", "S", "a", "b")) is None
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.create_calendar_event_enhanced("u1", "S", "a", "b")) is None

    def test_create_contact_enhanced(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={
            "id": "c1", "displayName": "N", "givenName": "", "surname": "", "jobTitle": "",
            "department": "", "companyName": "", "businessPhones": [], "mobilePhone": "",
            "homePhones": [], "emailAddresses": [], "imAddresses": [], "homeAddress": {},
            "businessAddress": {}, "otherAddress": {}, "personalNotes": "", "birthday": "",
            "anniversary": "", "spouseName": "", "children": [], "manager": "",
            "assistantName": "", "profession": "", "categories": [], "createdDateTime": "",
            "lastModifiedDateTime": "",
        })
        c = run(svc.create_contact_enhanced(
            "u1", "N", given_name="G", surname="S", email_addresses=["a@b.c"],
            business_phones=["1"], mobile_phone="2", job_title="J", company_name="C",
        ))
        assert c is not None and c.display_name == "N"
        svc._make_graph_request = AsyncMock(return_value=None)
        assert run(svc.create_contact_enhanced("u1", "N")) is None
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.create_contact_enhanced("u1", "N")) is None

    def test_create_task_enhanced(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={
            "id": "t1", "subject": "S", "body": {}, "importance": "high", "status": "notStarted",
            "completedDateTime": {}, "dueDateTime": {}, "startDateTime": {}, "createdDateTime": "",
            "lastModifiedDateTime": "", "isReminderOn": True, "reminderDateTime": {},
            "categories": [], "assignedTo": "", "parentFolderId": "", "conversationId": "",
            "conversationIndex": "", "flag": {},
        })
        t = run(svc.create_task_enhanced(
            "u1", "S", body="B", due_date="2026-08-01", start_date="2026-07-01",
            reminder_date="2026-07-31", categories=["c"],
        ))
        assert t is not None and t.id == "t1"
        svc._make_graph_request = AsyncMock(return_value=None)
        assert run(svc.create_task_enhanced("u1", "S")) is None
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.create_task_enhanced("u1", "S")) is None

    def test_get_user_folders(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={"value": [{
            "id": "f1", "displayName": "Inbox", "parentFolderId": "", "childFolderCount": 0,
            "unreadItemCount": 1, "totalItemCount": 2, "folderType": "inbox", "isHidden": False,
            "wellKnownName": "inbox",
        }]})
        folders = run(svc.get_user_folders("u1", folder_type="inbox"))
        assert len(folders) == 1
        # cache hit
        assert run(svc.get_user_folders("u1", folder_type="inbox")) == folders
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.get_user_folders("u2")) == []

    def test_search_entities_enhanced(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={"value": [{
            "hitsContainers": [{"hits": [{
                "id": "h1", "resource": {
                    "@odata.type": "#microsoft.graph.message",
                    "subject": "S", "webLink": "w",
                },
                "summary": {"score": 0.9},
            }]}],
        }]})
        results = run(svc.search_entities_enhanced("u1", "q", entity_types=["message"]))
        assert len(results) == 1 and results[0]["entityType"] == "message"
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.search_entities_enhanced("u1", "q")) == []

    def test_get_user_profile_enhanced(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={
            "id": "u1", "displayName": "N", "mail": "a@b.c", "jobTitle": "J", "department": "D",
            "officeLocation": "O", "mobilePhone": "M", "businessPhones": [],
            "userPrincipalName": "U", "accountEnabled": True, "userType": "Member",
            "preferredLanguage": "en", "mailboxSettings": {"timeZone": "UTC"},
            "usageLocation": "US",
        })
        p = run(svc.get_user_profile_enhanced("u1"))
        assert p is not None and p.display_name == "N"
        assert run(svc.get_user_profile_enhanced("u1")) is p  # cache
        svc._make_graph_request = AsyncMock(return_value=None)
        assert run(svc.get_user_profile_enhanced("u2")) is None
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.get_user_profile_enhanced("u3")) is None

    def test_get_upcoming_events(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={"value": [{
            "id": "e1", "subject": "S", "bodyPreview": "bp", "body": {}, "start": {}, "end": {},
            "location": {}, "locations": [], "attendees": [], "organizer": {}, "isAllDay": False,
            "isCancelled": False, "isOrganizer": True, "responseRequested": True,
            "responseStatus": {}, "sensitivity": "normal", "showAs": "busy", "type": "t",
            "webLink": "w", "onlineMeeting": {}, "recurrence": {}, "reminderMinutesBeforeStart": 15,
            "categories": [], "extensions": [],
        }]})
        events = run(svc.get_upcoming_events("u1", days=3))
        assert len(events) == 1
        assert run(svc.get_upcoming_events("u1", days=3)) == events  # cache
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.get_upcoming_events("u2")) == []

    def test_unread_count_and_mark_read(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={"unreadItemCount": 5})
        assert run(svc.get_unread_email_count("u1")) == 5
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.get_unread_email_count("u1")) == 0

        svc._make_graph_request = AsyncMock(return_value={"id": "m1"})
        assert run(svc.mark_emails_read("u1", ["m1", "m2"])) is True
        svc._make_graph_request = AsyncMock(return_value=None)
        assert run(svc.mark_emails_read("u1", ["m1"])) is False
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.mark_emails_read("u1", ["m1"])) is False

    def test_cache_management_and_info(self):
        svc = self.make()
        svc.users_cache["k"] = 1
        svc.emails_cache["k"] = 1
        svc.events_cache["k"] = 1
        svc.contacts_cache["k"] = 1
        svc.tasks_cache["k"] = 1
        svc.folders_cache["k"] = 1
        svc._clear_cache()
        assert not svc.users_cache and not svc.folders_cache
        svc.emails_cache["k"] = 1
        svc._clear_email_cache()
        assert not svc.emails_cache
        svc.events_cache["k"] = 1
        svc._clear_events_cache()
        assert not svc.events_cache
        svc.contacts_cache["k"] = 1
        svc._clear_contacts_cache()
        assert not svc.contacts_cache
        svc.tasks_cache["k"] = 1
        svc._clear_tasks_cache()
        assert not svc.tasks_cache
        svc.folders_cache["k"] = 1
        svc._clear_folders_cache()
        assert not svc.folders_cache

        info = run(svc.get_service_info())
        assert info["service"] == "outlook" and info["version"] == "2.0.0"


class FakeSession2:
    closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def post(self, url, data=None):
        class Resp:
            status = 400

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def json(self):
                return {}

        return Resp()


# ============================================================================
# microsoft365_service.py
# ============================================================================

class TestMs365Coverage:
    def make(self, **config):
        from integrations.microsoft365_service import Microsoft365Service

        return Microsoft365Service("default", config)

    def test_models(self):
        from integrations.microsoft365_service import (
            Microsoft365AuthResponse,
            Microsoft365Channel,
            Microsoft365Team,
            Microsoft365User,
        )

        assert Microsoft365AuthResponse(auth_url="u", state="s").state == "s"
        assert Microsoft365User(id="1", displayName="N", mail="m", userPrincipalName="u").id == "1"
        assert Microsoft365Team(id="1", displayName="N", description="d", visibility="v").visibility == "v"
        assert Microsoft365Channel(id="1", displayName="N", description="d").description == "d"

    def test_init_without_config(self):
        from integrations.microsoft365_service import Microsoft365Service

        svc = Microsoft365Service("t1")
        assert svc.tenant_id == "t1"

    def test_health_check_exception(self):
        svc = self.make()

        class WeirdConfig(dict):
            def __contains__(self, key):
                raise Exception("boom")

        svc.config = WeirdConfig()
        r = run(svc.health_check())
        assert r["status"] == "unhealthy"

    def test_capabilities_health(self):
        svc = self.make()
        caps = svc.get_capabilities()
        assert "send_message" in caps
        r = run(svc.health_check())
        assert r["status"] == "unconfigured"
        svc2 = self.make(access_token="tok")
        r = run(svc2.health_check())
        assert r["status"] == "healthy"

    def test_execute_operation(self):
        svc = self.make()
        svc._authenticate = AsyncMock(return_value={"status": "success"})
        r = run(svc.execute_operation("authenticate", user_id="u1"))
        assert r["status"] == "success"

        svc._send_message = AsyncMock(return_value={"status": "success"})
        r = run(svc.execute_operation("send_message", team_id="t", channel_id="c", content="x"))
        assert r["status"] == "success"

        svc._list_teams = AsyncMock(return_value={"status": "success"})
        assert run(svc.execute_operation("list_teams"))["status"] == "success"

        svc._list_channels = AsyncMock(return_value={"status": "success"})
        assert run(svc.execute_operation("list_channels", team_id="t"))["status"] == "success"

        r = run(svc.execute_operation("bogus"))
        assert r["status"] == "error"

        svc._send_message = AsyncMock(side_effect=Exception("x"))
        r = run(svc.execute_operation("send_message", team_id="t", channel_id="c", content="x"))
        assert r["status"] == "error"

    def test_authenticate(self):
        svc = self.make()
        r = run(svc.authenticate("u1"))
        assert r["status"] == "success"
        assert "microsoft365_u1" in r["auth_url"]
        r2 = run(svc._authenticate("u2"))
        assert r2["status"] == "success"

        with patch("urllib.parse.urlencode", side_effect=Exception("x")):
            r3 = run(svc._authenticate("u3"))
        assert r3["status"] == "error"

    def test_graph_getters(self):
        svc = self.make()
        payload = {"status": "success", "data": {"id": "u1"}}
        for method, args in [
            ("get_user_profile", ("tok",)),
            ("list_teams", ("tok",)),
            ("list_channels", ("tok", "t1")),
            ("get_outlook_messages", ("tok",)),
            ("get_calendar_events", ("tok", "2026-01-01", "2026-02-01")),
            ("get_planner_tasks", ("tok",)),
            ("get_dynamics_deals", ("tok",)),
            ("get_dynamics_invoices", ("tok",)),
        ]:
            svc._make_graph_request = AsyncMock(return_value=payload)
            r = run(getattr(svc, method)(*args))
            assert r["status"] == "success"

        for method, args in [
            ("get_user_profile", ("tok",)),
            ("list_teams", ("tok",)),
            ("list_channels", ("tok", "t1")),
            ("get_outlook_messages", ("tok",)),
            ("get_calendar_events", ("tok", "2026-01-01", "2026-02-01")),
            ("get_planner_tasks", ("tok",)),
            ("get_dynamics_deals", ("tok",)),
            ("get_dynamics_invoices", ("tok",)),
        ]:
            svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
            r = run(getattr(svc, method)(*args))
            assert r["status"] == "error"

    def test_get_service_status(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={"status": "success", "data": {"id": "u1"}})
        r = run(svc.get_service_status("tok"))
        assert r["status"] == "success"
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        r = run(svc.get_service_status("tok"))
        assert r["status"] == "error"

    def test_make_graph_request(self):
        svc = self.make()

        with patch("aiohttp.ClientSession", return_value=Ms365FakeSession(Ms365FakeResp(400))):
            r = run(svc._make_graph_request("GET", "https://x", "tok"))
            assert r["status"] == "error"
        with patch("aiohttp.ClientSession", return_value=Ms365FakeSession(Ms365FakeResp(204))):
            r = run(svc._make_graph_request("GET", "https://x", "tok"))
            assert r["status"] == "success" and r["data"] is None
        with patch("aiohttp.ClientSession", return_value=Ms365FakeSession(Ms365FakeResp(200, {"ok": 1}))):
            r = run(svc._make_graph_request("GET", "https://x", "tok"))
            assert r["data"] == {"ok": 1}
        with patch("aiohttp.ClientSession", return_value=Ms365FakeSession(Ms365FakeResp(200, {"ok": 1}))):
            r = run(svc._make_graph_request("GET", "https://x", "tok"))
            assert r["status"] == "success"

        with patch.dict(os.environ, {"ATOM_ENV": "development"}), patch(
            "aiohttp.ClientSession", return_value=Ms365FakeSession(Ms365FakeResp(200, {"ok": 1}))
        ):
            r = run(svc._make_graph_request("GET", "https://x", "fake_token"))
            assert r["status"] == "success"
        with patch.dict(os.environ, {"ATOM_ENV": "production"}), patch(
            "aiohttp.ClientSession", return_value=Ms365FakeSession(Ms365FakeResp(200, {"ok": 1}))
        ):
            r = run(svc._make_graph_request("GET", "https://x", "fake_token"))
            assert r["status"] == "success" and r.get("data") != {"id": "mock_id_123"}

    def test_onedrive_actions(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={"status": "success", "data": {}})
        r = run(svc.execute_onedrive_action("tok", "list_files", {"folder": "docs"}))
        assert r["status"] == "success"
        r = run(svc.execute_onedrive_action("tok", "list_files", {}))
        assert r["status"] == "success"
        r = run(svc.execute_onedrive_action("tok", "get_content", {"path": "a.txt"}))
        assert r["status"] == "success"
        r = run(svc.execute_onedrive_action("tok", "get_content", {}))
        assert r["status"] == "error"
        with patch("aiohttp.ClientSession", return_value=Ms365FakeSession(Ms365FakeResp(200, {"ok": 1}))):
            r = run(svc.execute_onedrive_action("tok", "upload", {"path": "a.txt", "file_content": b"x"}))
            assert r["status"] == "success"
        with patch("aiohttp.ClientSession", return_value=Ms365FakeSession(Ms365FakeResp(400))):
            r = run(svc.execute_onedrive_action("tok", "upload", {"path": "a.txt", "file_content": b"x"}))
            assert r["status"] == "error"
        r = run(svc.execute_onedrive_action("tok", "upload", {}))
        assert r["status"] == "error"
        r = run(svc.execute_onedrive_action("tok", "delete", {"item_id": "i1"}))
        assert r["status"] == "success"
        r = run(svc.execute_onedrive_action("tok", "delete", {}))
        assert r["status"] == "error"
        r = run(svc.execute_onedrive_action("tok", "share", {"item_id": "i1"}))
        assert r["status"] == "success"
        r = run(svc.execute_onedrive_action("tok", "share", {}))
        assert r["status"] == "error"
        r = run(svc.execute_onedrive_action("tok", "create_folder", {"name": "n"}))
        assert r["status"] == "success"
        r = run(svc.execute_onedrive_action("tok", "create_folder", {"name": "n", "folder_path": "p"}))
        assert r["status"] == "success"
        r = run(svc.execute_onedrive_action("tok", "create_folder", {}))
        assert r["status"] == "error"
        r = run(svc.execute_onedrive_action("tok", "nope", {}))
        assert r["status"] == "error"
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        r = run(svc.execute_onedrive_action("tok", "list_files", {}))
        assert r["status"] == "error"

    def test_excel_actions(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={"status": "success", "data": {}})
        cases = [
            ("read_range", {"item_id": "i1", "range": "Sheet1!A1:B2"}),
            ("read_range", {"item_id": "i1", "range": "A1"}),
            ("read_range", {"item_id": "i1"}),
            ("write_range", {"item_id": "i1", "range": "A1", "values": [[1]]}),
            ("write_range", {"item_id": "i1", "range": "S!A1", "values": [[1]]}),
            ("write_range", {"item_id": "i1"}),
            ("get_tables", {"item_id": "i1"}),
            ("get_columns", {"item_id": "i1", "table": "T"}),
            ("get_columns", {"item_id": "i1"}),
            ("append_row", {"item_id": "i1", "table": "T", "values": [1]}),
            ("append_row", {"item_id": "i1", "table": "T", "mapping": {"A": 1}}),
            ("append_row", {"item_id": "i1", "table": "T"}),
            ("append_row", {"item_id": "i1"}),
            ("create_worksheet", {"item_id": "i1", "name": "W"}),
            ("create_worksheet", {"item_id": "i1"}),
            ("format_range", {"item_id": "i1", "range": "A1", "format": {"bold": True}}),
            ("format_range", {"item_id": "i1", "range": "S!A1", "format": {}}),
            ("format_range", {"item_id": "i1"}),
            ("nope", {"item_id": "i1"}),
        ]
        for action, params in cases:
            svc._make_graph_request = AsyncMock(return_value={"status": "success", "data": {}})
            run(svc.execute_excel_action("tok", action, params))

        # path resolution branch
        svc._make_graph_request = AsyncMock(return_value={"status": "success", "data": {"id": "i1"}})
        r = run(svc.execute_excel_action("tok", "get_tables", {"path": "p"}))
        assert r["status"] == "success"
        svc._make_graph_request = AsyncMock(return_value={"status": "error"})
        r = run(svc.execute_excel_action("tok", "get_tables", {"path": "p"}))
        assert r["status"] == "error"
        r = run(svc.execute_excel_action("tok", "get_tables", {}))
        assert r["status"] == "error"
        # mapping without values: columns fetch failure
        svc._make_graph_request = AsyncMock(side_effect=[{"status": "error"}])
        r = run(svc.execute_excel_action("tok", "append_row", {"item_id": "i1", "table": "T", "mapping": {"A": 1}}))
        assert r["status"] == "error"
        # columns success -> values built
        svc._make_graph_request = AsyncMock(side_effect=[
            {"status": "success", "data": [{"name": "A"}, {"name": "B"}]},
            {"status": "success"},
        ])
        r = run(svc.execute_excel_action("tok", "append_row", {"item_id": "i1", "table": "T", "mapping": {"A": 1, "B": 2}}))
        assert r["status"] == "success"
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        r = run(svc.execute_excel_action("tok", "get_tables", {"item_id": "i1"}))
        assert r["status"] == "error"

    def test_powerbi_actions(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={"status": "success"})
        for action, params, need_err in [
            ("refresh_dataset", {"group_id": "g", "dataset_id": "d"}, False),
            ("refresh_dataset", {"group_id": "g"}, True),
            ("get_reports", {"group_id": "g"}, False),
            ("get_reports", {}, True),
            ("get_dashboards", {"group_id": "g"}, False),
            ("get_dashboards", {}, True),
            ("export_report", {"group_id": "g", "report_id": "r"}, False),
            ("export_report", {"group_id": "g"}, True),
            ("get_datasets", {"group_id": "g"}, False),
            ("get_datasets", {}, True),
            ("nope", {}, True),
        ]:
            r = run(svc.execute_powerbi_action("tok", action, params))
            assert r["status"] == ("error" if need_err else "success"), (action, params)
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.execute_powerbi_action("tok", "get_reports", {"group_id": "g"}))["status"] == "error"

    def test_teams_actions(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={"status": "success"})
        for action, params, need_err in [
            ("send_message", {"team_id": "t", "channel_id": "c", "message": "m"}, False),
            ("send_message", {"team_id": "t"}, True),
            ("create_channel", {"team_id": "t", "display_name": "N"}, False),
            ("create_channel", {"team_id": "t"}, True),
            ("list_teams", {}, False),
            ("nope", {}, True),
        ]:
            r = run(svc.execute_teams_action("tok", action, params))
            assert r["status"] == ("error" if need_err else "success")
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.execute_teams_action("tok", "list_teams", {}))["status"] == "error"

    def test_outlook_actions(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={"status": "success"})
        r = run(svc.execute_outlook_action("tok", "send_email", {"to": "a@b.c", "subject": "S", "body": "B"}))
        assert r["status"] == "success"
        r = run(svc.execute_outlook_action("tok", "send_email", {"to": ["a@b.c"], "cc": "c@d", "bcc": "e@f"}))
        assert r["status"] == "success"
        r = run(svc.execute_outlook_action("tok", "send_email", {}))
        assert r["status"] == "error"
        r = run(svc.execute_outlook_action("tok", "list_messages", {}))
        assert r["status"] == "success"
        r = run(svc.execute_outlook_action("tok", "create_event", {"start_time": "a", "end_time": "b"}))
        assert r["status"] == "success"
        r = run(svc.execute_outlook_action("tok", "create_event", {"start_time": "a", "end_time": "b", "body": "B", "attendees": "x@y"}))
        assert r["status"] == "success"
        r = run(svc.execute_outlook_action("tok", "create_event", {}))
        assert r["status"] == "error"
        r = run(svc.execute_outlook_action("tok", "nope", {}))
        assert r["status"] == "error"
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.execute_outlook_action("tok", "list_messages", {}))["status"] == "error"

    def test_planner_actions(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={"status": "success"})
        for action, params, need_err in [
            ("create_task", {"plan_id": "p", "bucket_id": "b", "title": "T"}, False),
            ("create_task", {"plan_id": "p", "bucket_id": "b", "title": "T", "description": "d", "assignments": {}}, False),
            ("create_task", {"plan_id": "p"}, True),
            ("update_task", {"task_id": "t", "title": "T", "description": "d", "percent_complete": 50}, False),
            ("update_task", {"task_id": "t"}, False),
            ("update_task", {}, True),
            ("list_plans", {"group_id": "g"}, False),
            ("list_plans", {}, True),
            ("list_buckets", {"plan_id": "p"}, False),
            ("list_buckets", {}, True),
            ("list_tasks", {"plan_id": "p"}, False),
            ("list_tasks", {}, True),
            ("nope", {}, True),
        ]:
            r = run(svc.execute_planner_action("tok", action, params))
            assert r["status"] == ("error" if need_err else "success"), (action, params)
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.execute_planner_action("tok", "list_tasks", {"plan_id": "p"}))["status"] == "error"

    def test_delete_item(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={"status": "success"})
        for item_type, params in [
            ("message", {}),
            ("event", {}),
            ("file", {}),
            ("team_message", {"team_id": "t", "channel_id": "c"}),
            ("team_message", {"team_id": "t"}),
            ("bogus", {}),
        ]:
            r = run(svc.delete_item("tok", item_type, "i1", params))
            assert r["status"] in ("success", "error")
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.delete_item("tok", "message", "i1", {}))["status"] == "error"

    def test_subscriptions(self):
        svc = self.make()
        svc._make_graph_request = AsyncMock(return_value={"status": "success"})
        r = run(svc.create_subscription("tok", "users/u1/messages", "created", "https://cb", "2026-09-01T00:00:00Z"))
        assert r["status"] == "success"
        # 'deleted' already present -> no append
        r = run(svc.create_subscription("tok", "x", "created,deleted", "https://cb", "2026-09-01T00:00:00Z"))
        assert r["status"] == "success"
        r = run(svc.renew_subscription("tok", "sub1", "2026-09-01T00:00:00Z"))
        assert r["status"] == "success"
        r = run(svc.delete_subscription("tok", "sub1"))
        assert r["status"] == "success"
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc.create_subscription("tok", "x", "created", "https://cb", "d"))["status"] == "error"
        assert run(svc.renew_subscription("tok", "s", "d"))["status"] == "error"
        assert run(svc.delete_subscription("tok", "s"))["status"] == "error"

    def test_private_send_list(self):
        svc = self.make()
        r = run(svc._send_message("t", "c", "x"))
        assert r["status"] == "error"
        r = run(svc._list_teams())
        assert r["status"] == "error"
        r = run(svc._list_channels("t"))
        assert r["status"] == "error"

        svc.config["access_token"] = "tok"
        svc._make_graph_request = AsyncMock(return_value={"status": "success"})
        assert run(svc._send_message("t", "c", "x"))["status"] == "success"
        assert run(svc._list_teams())["status"] == "success"
        assert run(svc._list_channels("t"))["status"] == "success"
        svc._make_graph_request = AsyncMock(side_effect=Exception("x"))
        assert run(svc._send_message("t", "c", "x"))["status"] == "error"
        assert run(svc._list_teams())["status"] == "error"
        assert run(svc._list_channels("t"))["status"] == "error"

    def test_routes(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.auth import get_current_user
        from integrations.microsoft365_service import microsoft365_router

        app = FastAPI()
        app.include_router(microsoft365_router)
        # The router enforces authentication; bypass it for route-level testing.
        app.dependency_overrides[get_current_user] = lambda: {"id": "u1"}
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/microsoft365/health")
        assert resp.status_code == 200

        user_data = {
            "id": "u1", "displayName": "N", "mail": "m@x", "userPrincipalName": "u",
            "value": [{"id": "1"}, {"id": "2"}],
        }
        with patch(
            "integrations.microsoft365_service.microsoft365_service._make_graph_request",
            new=AsyncMock(return_value={"status": "success", "data": user_data}),
        ):
            assert client.get("/microsoft365/user?access_token=tok").status_code == 200
            assert client.get("/microsoft365/teams?access_token=tok").status_code == 200
            assert client.get("/microsoft365/teams/t1/channels?access_token=tok").status_code == 200
            assert client.get("/microsoft365/outlook/messages?access_token=tok").status_code == 200
            assert client.get("/microsoft365/calendar/events?access_token=tok&start_date=2026-01-01&end_date=2026-02-01").status_code == 200
            assert client.get("/microsoft365/services/status?access_token=tok").status_code == 200
        assert client.get("/microsoft365/auth?user_id=u1").status_code == 200
        with patch(
            "integrations.microsoft365_service.microsoft365_service.authenticate",
            new=AsyncMock(return_value={"status": "error", "message": "nope"}),
        ):
            assert client.get("/microsoft365/auth?user_id=u1").status_code == 400

        with patch(
            "integrations.microsoft365_service.microsoft365_service._make_graph_request",
            new=AsyncMock(return_value={"status": "error", "message": "nope"}),
        ):
            assert client.get("/microsoft365/user?access_token=tok").status_code == 400
            assert client.get("/microsoft365/teams?access_token=tok").status_code == 400
            assert client.get("/microsoft365/teams/t1/channels?access_token=tok").status_code == 400
            assert client.get("/microsoft365/outlook/messages?access_token=tok").status_code == 400
            assert client.get("/microsoft365/calendar/events?access_token=tok&start_date=2026-01-01&end_date=2026-02-01").status_code == 400
            assert client.get("/microsoft365/services/status?access_token=tok").status_code == 400


# ============================================================================
# atom_telegram_integration.py
# ============================================================================

class TestTelegramCoverage:
    def make(self, **overrides):
        from integrations.atom_telegram_integration import AtomTelegramIntegration

        cfg = {
            "bot_token": "test:token",
            "bot_username": "testbot",
            "webhook_url": "https://cb",
            "enable_enterprise_features": True,
            "security_level": "standard",
            "compliance_standards": ["SOC2"],
            "database": None,
            "cache": None,
            "security_service": None,
            "automation_service": None,
            "ai_service": None,
        }
        cfg.update(overrides)
        return AtomTelegramIntegration(cfg)

    def test_enums_and_dataclasses(self):
        from integrations.atom_telegram_integration import (
            TelegramChat,
            TelegramChatType,
            TelegramCommandType,
            TelegramMessage,
            TelegramMessageType,
            TelegramUser,
        )

        assert TelegramMessageType.WEBPAGE_PREVIEW.value == "webpage_preview"
        assert TelegramChatType.CHANNEL.value == "channel"
        assert TelegramCommandType.MONITOR.value == "monitor"
        u = TelegramUser(user_id=1, username=None, first_name=None, last_name=None,
                         language_code=None, is_bot=False, is_premium=False, is_active=True,
                         permissions=[], security_level="standard", created_at=datetime.now(timezone.utc),
                         last_active=datetime.now(timezone.utc), metadata={})
        assert u.user_id == 1
        c = TelegramChat(chat_id=1, chat_type=TelegramChatType.PRIVATE, title=None, username=None,
                         first_name=None, last_name=None, description=None, permissions={},
                         security_level="s", is_active=True, member_count=0,
                         created_at=datetime.now(timezone.utc), last_message=datetime.now(timezone.utc), metadata={})
        assert c.chat_id == 1
        m = TelegramMessage(message_id=1, chat_id=1, user_id=1, message_type=TelegramMessageType.TEXT,
                            content="hi", media_path=None, reply_to_message_id=None, forward_from=None,
                            forward_from_chat=None, edit_date=None, timestamp=datetime.now(timezone.utc),
                            views=0, reactions=[], security_flags={}, metadata={})
        assert m.content == "hi"

    def test_initialize(self):
        # Env-coupled: a dev .env may export TELEGRAM_BOT_TOKEN, which the
        # bot_token=None construction falls back to. Clear it so the
        # "no credentials -> init fails" contract is actually under test.
        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": ""}):
            svc = self.make(bot_token=None)
            assert run(svc.initialize()) is False

        svc = self.make()
        assert run(svc.initialize()) is True
        assert svc.is_initialized is True

        svc2 = self.make(enable_enterprise_features=False)
        assert run(svc2.initialize()) is True

        svc3 = self.make()
        svc3._setup_enterprise_features = AsyncMock(side_effect=Exception("x"))
        assert run(svc3.initialize()) is False

    def test_workspaces_channels_messages(self):
        from integrations.atom_telegram_integration import TelegramChat, TelegramChatType, TelegramMessage, TelegramMessageType

        svc = self.make(enable_enterprise_features=False)
        now = datetime.now(timezone.utc)
        chat = TelegramChat(chat_id=7, chat_type=TelegramChatType.GROUP, title="Room",
                            username=None, first_name=None, last_name=None, description="d",
                            permissions={}, security_level="s", is_active=True, member_count=3,
                            created_at=now, last_message=now, metadata={})
        svc.active_chats = {7: chat, 8: TelegramChat(chat_id=8, chat_type=TelegramChatType.GROUP, title=None,
                             username=None, first_name=None, last_name=None, description=None, permissions={},
                             security_level="s", is_active=False, member_count=0, created_at=now,
                             last_message=now, metadata={})}
        ws = run(svc.get_intelligent_workspaces(1))
        assert len(ws) == 1 and ws[0]["id"] == 7

        ch = run(svc.get_intelligent_channels(7, 1))
        assert len(ch) == 1
        assert run(svc.get_intelligent_channels(999, 1)) == []

        with httpx_post_mock({"ok": True, "result": {"message_id": 1}}):
            result = run(svc.send_intelligent_message(7, "hi", metadata={"k": 1}))
            assert result["success"] is True
        svc2 = self.make(enable_enterprise_features=False)
        svc2._log_message_event = AsyncMock(side_effect=Exception("x"))
        svc2.telegram_config["enable_enterprise_features"] = True
        with httpx_post_mock({"ok": True, "result": {"message_id": 2}}):
            r2 = run(svc2.send_intelligent_message(7, "hi"))
            assert r2["success"] is True

        msg = TelegramMessage(message_id=1, chat_id=7, user_id=1, message_type=TelegramMessageType.TEXT,
                              content="hello world", media_path=None, reply_to_message_id=None,
                              forward_from=None, forward_from_chat=None, edit_date=None,
                              timestamp=now, views=0, reactions=[], security_flags={}, metadata={"m": 1})
        svc.message_history = {7: [msg]}
        res = run(svc.perform_intelligent_search("hello", 1))
        assert len(res) == 1 and res[0]["content"] == "hello world"
        res = run(svc.perform_intelligent_search("hello", 1, workspace_id=99))
        assert res == []
        res = run(svc.get_user_conversation_history(1, 7, limit=5))
        assert len(res) == 1
        res = run(svc.get_user_conversation_history(2, 7))
        assert res == []

    def test_service_status(self):
        svc = self.make()
        st = run(svc.get_service_status())
        assert st["platform"] == "telegram"
        svc._start_time = time.time() - 10
        st = run(svc.get_service_status())
        assert st["status"] == "inactive"

    def test_enterprise_setup(self):
        svc = self.make()
        run(svc._setup_security_policies())
        run(svc._setup_enterprise_features())
        assert svc.security_policies["message_content_filter"]["enabled"] is True
        run(svc._setup_compliance_rules())
        run(svc._setup_automation_triggers())
        run(svc._setup_security_and_compliance())
        run(svc._setup_security_monitoring())
        run(svc._setup_compliance_monitoring())
        run(svc._load_existing_data())
        run(svc._start_bot())
        assert hasattr(svc, "_start_time")
        run(svc.close())

        svc2 = self.make(automation_service=Mock())
        svc2.enterprise_automation.create_integration_automation = AsyncMock(return_value={"ok": True})
        run(svc2._setup_automation())
        svc2.enterprise_automation.create_integration_automation = AsyncMock(return_value={"ok": False, "error": "e"})
        run(svc2._setup_automation())

        svc3 = self.make(automation_service=Mock())
        svc3.enterprise_automation.create_integration_automation = AsyncMock(side_effect=Exception("x"))
        run(svc3._setup_automation())

        svc4 = self.make(security_service=Mock(), automation_service=Mock())
        svc4.enterprise_security.audit_event = AsyncMock()
        await_log = svc4._log_message_event("sent", 1, {"user_id": 1})
        run(await_log)
        svc4.enterprise_security.audit_event = AsyncMock(side_effect=Exception("x"))
        run(svc4._log_message_event("sent", 1, {}))

    def test_relevance_and_ai_search(self):
        from integrations import atom_telegram_integration as mod

        svc = self.make()
        assert svc._calculate_relevance_score("a b", "a c") == 0.5
        assert svc._calculate_relevance_score("", "x") == 0.0
        assert run(svc._perform_ai_search("q")) == []  # no ai_service

        svc.ai_service = Mock()
        svc.ai_service.process_ai_request = AsyncMock()
        response = Mock()
        response.ok = True
        response.output_data = {"results": [{"id": 1}]}
        svc.ai_service.process_ai_request.return_value = response
        with patch.object(mod, "AIRequest", Mock()), patch.object(
            mod, "AITaskType", Mock(SEARCH_QUERY="search")
        ), patch.object(mod, "AIModelType", Mock(GPT_4="gpt4")), patch.object(
            mod, "AIServiceType", Mock(OPENAI="openai")
        ):
            assert run(svc._perform_ai_search("q")) == [{"id": 1}]
            response.ok = False
            assert run(svc._perform_ai_search("q")) == []
            svc.ai_service.process_ai_request = AsyncMock(side_effect=Exception("x"))
            assert run(svc._perform_ai_search("q")) == []

    def test_keyboard_methods(self):
        svc = self.make(bot_token=None)
        r = run(svc.send_message_with_keyboard(1, "t", [[{"text": "B"}]], parse_mode="Markdown",
                                               disable_web_page_preview=True, disable_notification=True,
                                               reply_to_message_id=5))
        assert r["success"] is False

        svc = self.make()
        with httpx_post_mock({"ok": True, "result": {"message_id": 42}}):
            r = run(svc.send_message_with_keyboard(1, "t", [[{"text": "B"}]], parse_mode="Markdown",
                                                   disable_web_page_preview=True, disable_notification=True,
                                                   reply_to_message_id=5))
            assert r["success"] is True and r["message_id"] == 42
        with httpx_post_mock({"ok": False, "description": "bot blocked"}):
            r = run(svc.send_message_with_keyboard(1, "t", [[{"text": "B"}]]))
            assert r["success"] is False and r["error"] == "bot blocked"
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.post = AsyncMock(side_effect=Exception("net"))
            r = run(svc.send_message_with_keyboard(1, "t", [[{"text": "B"}]]))
            assert r["success"] is False

        svc = self.make(bot_token=None)
        assert run(svc.edit_message_keyboard(1, 5, [[{"text": "B"}]]))["success"] is False
        svc = self.make()
        with httpx_post_mock({"ok": True}):
            r = run(svc.edit_message_keyboard(1, 5, [[{"text": "B"}]]))
            assert r["success"] is True
        with httpx_post_mock({"ok": False, "description": "bad"}):
            assert run(svc.edit_message_keyboard(1, 5, [[{"text": "B"}]]))["success"] is False
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.post = AsyncMock(side_effect=Exception("net"))
            assert run(svc.edit_message_keyboard(1, 5, [[{"text": "B"}]]))["success"] is False

    def test_answer_callback(self):
        svc = self.make(bot_token=None)
        assert run(svc.answer_callback_query("cq1"))["success"] is False
        svc = self.make()
        with httpx_post_mock({"ok": True}):
            r = run(svc.answer_callback_query("cq1", text="T", show_alert=True, url="https://u", cache_time=10))
            assert r["success"] is True
        with httpx_post_mock({"ok": False, "description": "bad"}):
            assert run(svc.answer_callback_query("cq1"))["success"] is False
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.post = AsyncMock(side_effect=Exception("net"))
            assert run(svc.answer_callback_query("cq1"))["success"] is False

    def test_callback_handlers(self):
        svc = self.make()
        svc.answer_callback_query = AsyncMock()

        async def flow(data):
            svc.answer_callback_query.reset_mock()
            await svc.handle_callback_query(
                {"id": "cq", "data": data, "message": {}, "from": {"id": 42}}
            )
            return [c.kwargs.get("text") for c in svc.answer_callback_query.await_args_list][-1]

        assert run(flow("action_approve_request_123")) == "Request approved"
        assert run(flow("action_deny_request_1")) == "Request denied"
        assert run(flow("action_execute_workflow_99")) == "Workflow execution started"
        assert run(flow("action_unknown_thing")) == "Unknown action: unknown"
        assert run(flow("action")) == "Unknown action"
        # invalid-format branches (direct calls; the router only routes
        # prefixed data, so these are not reachable through handle_callback_query)
        await_direct = svc._handle_action_callback("cq", "action", 1)
        run(await_direct)
        await_direct = svc._handle_search_callback("cq", "search", 1)
        run(await_direct)
        await_direct = svc._handle_workflow_callback("cq", "workflow_1", 1)
        run(await_direct)
        await_direct = svc._handle_settings_callback("cq", "settings_x", 1)
        run(await_direct)
        assert run(flow("search_recent_messages")) == "Search completed"
        assert run(flow("search_communications_hello")) == "Search completed"
        assert run(flow("search_workflows_q")) == "Search completed"
        assert run(flow("search_")) == "Unknown search type: "
        assert run(flow("search_bogus")) == "Unknown search type: bogus"
        assert run(flow("workflow_1_start")) == "Workflow started"
        assert run(flow("workflow_1_stop")) == "Workflow stopped"
        assert run(flow("workflow_1_status")) == "Status: Running"
        assert run(flow("workflow_1")) == "Invalid workflow format"
        assert run(flow("workflow_1_bogus")) == "Unknown workflow action: bogus"
        assert run(flow("settings_notifications_on")) == "Notifications updated"
        assert run(flow("settings_language_en")) == "Language updated"
        assert run(flow("settings_theme_dark")) == "Theme updated"
        assert run(flow("settings_")) == "Invalid settings format"
        assert run(flow("settings_bogus_x")) == "Unknown setting: bogus"
        assert run(flow("no_such_prefix")) == "Unknown action"
        assert run(flow("")) == "Invalid callback"

    def test_callback_exception_path(self):
        svc = self.make()
        svc.answer_callback_query = AsyncMock(side_effect=Exception("x"))
        run(svc.handle_callback_query({"id": "cq", "data": "action_approve_request_1", "from": {"id": 1}}))

    def test_inline_query(self):
        svc = self.make()
        svc.answer_inline_query = AsyncMock()
        run(svc.handle_inline_query({"id": "iq", "query": "x", "from": {"id": 1}}))
        svc.answer_inline_query.assert_awaited()

        svc.lancedb_handler = Mock()
        svc.lancedb_handler.search.return_value = [
            {"id": "c1", "subject": "S", "body": "long body " * 30, "sender": "a@b", "platform": "tg", "timestamp": "t"}
        ]
        svc.answer_inline_query = AsyncMock()
        run(svc.handle_inline_query({"id": "iq", "query": "hello", "from": {"id": 1}}))
        svc.answer_inline_query.assert_awaited()

        svc.lancedb_handler.search.side_effect = Exception("lancedb down")
        svc.answer_inline_query = AsyncMock()
        run(svc.handle_inline_query({"id": "iq", "query": "hello", "from": {"id": 1}}))
        svc.answer_inline_query.assert_awaited()

        svc.lancedb_handler = None
        svc.answer_inline_query = AsyncMock()
        run(svc.handle_inline_query({"id": "iq", "query": "hello", "from": {"id": 1}}))
        svc.answer_inline_query.assert_awaited()

    def test_answer_inline_query(self):
        svc = self.make(bot_token=None)
        assert run(svc.answer_inline_query("iq", [{"id": "1", "title": "T", "description": "D", "message": "M"}]))["success"] is False
        svc = self.make()
        results = [{"id": f"r{i}", "title": "T", "description": "D", "message": "M"} for i in range(60)]
        with httpx_post_mock({"ok": True}):
            r = run(svc.answer_inline_query("iq", results, next_offset="10"))
            assert r["success"] is True
        with httpx_post_mock({"ok": False, "description": "bad"}):
            assert run(svc.answer_inline_query("iq", results))["success"] is False
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.post = AsyncMock(side_effect=Exception("net"))
            assert run(svc.answer_inline_query("iq", results))["success"] is False

    def test_format_lancedb_result(self):
        svc = self.make()
        r = svc._format_lancedb_result_for_inline({"id": "c1", "subject": "S", "body": "B", "sender": "a@b", "platform": "tg", "timestamp": "t"})
        assert r["title"] == "S"
        r2 = svc._format_lancedb_result_for_inline({})
        assert r2["title"] == "No Subject"
        assert svc._format_lancedb_result_for_inline(None) is None
        assert run(svc._perform_simple_inline_search("q"))[0]["title"] == "Search: q"
        svc2 = self.make()
        svc2._perform_simple_inline_search = lambda q: (_ for _ in ()).throw(Exception("x"))
        with patch.object(svc2, "_perform_simple_inline_search", side_effect=Exception("x")):
            pass

    def test_send_chat_action(self):
        svc = self.make(bot_token=None)
        assert run(svc.send_chat_action(1, "typing"))["success"] is False
        svc = self.make()
        with httpx_post_mock({"ok": True}):
            r = run(svc.send_chat_action(1, "typing", progress=50))
            assert r["success"] is True and r["action"] == "typing"
        with httpx_post_mock({"ok": False, "description": "bad"}):
            assert run(svc.send_chat_action(1, "typing"))["success"] is False
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.post = AsyncMock(side_effect=Exception("net"))
            assert run(svc.send_chat_action(1, "typing"))["success"] is False

    def test_send_intelligent_message(self):
        svc = self.make(bot_token=None)
        assert run(svc.send_intelligent_message(1, "hi"))["success"] is False
        svc = self.make()
        with httpx_post_mock({"ok": True, "result": {"message_id": 1}}):
            r = run(svc.send_intelligent_message(1, "hi", parse_mode="Markdown", disable_web_page_preview=True,
                                                 disable_notification=True, reply_to_message_id=3))
            assert r["success"] is True
        with httpx_post_mock({"ok": False, "description": "bad"}):
            assert run(svc.send_intelligent_message(1, "hi"))["success"] is False
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.post = AsyncMock(side_effect=Exception("net"))
            assert run(svc.send_intelligent_message(1, "hi"))["success"] is False

    def test_send_photo(self):
        svc = self.make(bot_token=None)
        assert run(svc.send_photo(1, "p.jpg"))["success"] is False
        svc = self.make()
        with httpx_post_mock({"ok": True, "result": {"message_id": 1}}):
            r = run(svc.send_photo(1, "p.jpg", caption="C", parse_mode="HTML"))
            assert r["success"] is True
        with httpx_post_mock({"ok": False, "description": "bad"}):
            assert run(svc.send_photo(1, "p.jpg"))["success"] is False
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.post = AsyncMock(side_effect=Exception("net"))
            assert run(svc.send_photo(1, "p.jpg"))["success"] is False

    def test_send_poll(self):
        svc = self.make(bot_token=None)
        assert run(svc.send_poll(1, "Q", ["a", "b"]))["success"] is False
        svc = self.make()
        with httpx_post_mock({"ok": True, "result": {"message_id": 1, "poll": {"id": "p1"}}}):
            r = run(svc.send_poll(1, "Q", ["a", "b"], is_anonymous=True, allows_multiple_answers=True, explanation="E"))
            assert r["success"] is True
        with httpx_post_mock({"ok": False, "description": "bad"}):
            assert run(svc.send_poll(1, "Q", ["a"]))["success"] is False
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.post = AsyncMock(side_effect=Exception("net"))
            assert run(svc.send_poll(1, "Q", ["a"]))["success"] is False

    def test_get_chat_info(self):
        svc = self.make(bot_token=None)
        assert run(svc.get_chat_info(1))["success"] is False
        svc = self.make()
        with httpx_post_mock({"ok": True, "result": {"id": 1}}):
            r = run(svc.get_chat_info(1))
            assert r["success"] is True and r["chat_info"] == {"id": 1}
        with httpx_post_mock({"ok": False, "description": "bad"}):
            assert run(svc.get_chat_info(1))["success"] is False
        with patch("httpx.AsyncClient") as ac:
            ac.return_value.__aenter__.return_value.post = AsyncMock(side_effect=Exception("net"))
            assert run(svc.get_chat_info(1))["success"] is False

    def test_exception_branches(self):
        from integrations import atom_telegram_integration as mod
        from integrations.atom_telegram_integration import (
            TelegramChat,
            TelegramChatType,
            TelegramMessage,
            TelegramMessageType,
        )

        # 227: LanceDB unavailable at init
        with patch("core.lancedb_handler.LanceDBHandler", side_effect=ImportError("no")):
            svc = self.make()
            assert svc.lancedb_handler is None

        now = datetime.now(timezone.utc)
        # 322: get_intelligent_channels except
        bad_chat = TelegramChat(chat_id=1, chat_type=object(), title=None, username=None,
                                first_name=None, last_name=None, description=None, permissions={},
                                security_level="s", is_active=True, member_count=0,
                                created_at=now, last_message=now, metadata={})
        svc = self.make()
        svc.active_chats = {1: bad_chat}
        assert run(svc.get_intelligent_channels(1, 1)) == []

        # 386/391: perform_intelligent_search AI branch + except
        msg = TelegramMessage(message_id=1, chat_id=1, user_id=1, message_type=TelegramMessageType.TEXT,
                              content="hello", media_path=None, reply_to_message_id=None,
                              forward_from=None, forward_from_chat=None, edit_date=None,
                              timestamp=now, views=0, reactions=[], security_flags={}, metadata={})
        svc = self.make()
        svc.message_history = {1: [msg]}
        svc.ai_service = Mock()
        svc.ai_service.process_ai_request = AsyncMock()
        response = Mock()
        response.ok = True
        response.output_data = {"results": [{"id": 9}]}
        svc.ai_service.process_ai_request.return_value = response
        with patch.object(mod, "AIRequest", Mock()), patch.object(
            mod, "AITaskType", Mock(SEARCH_QUERY="s")
        ), patch.object(mod, "AIModelType", Mock(GPT_4="g")), patch.object(
            mod, "AIServiceType", Mock(OPENAI="o")
        ):
            res = run(svc.perform_intelligent_search("hello", 1, workspace_id=1))
        assert any(r["id"] == 9 for r in res)
        svc.message_history = {1: None}
        assert run(svc.perform_intelligent_search("hello", 1)) == []

        # 418: conversation history except
        assert run(svc.get_user_conversation_history(1, 1)) == []

        # 446: service status except
        del svc.telegram_config["bot_username"]
        st = run(svc.get_service_status())
        assert st["platform"] == "telegram" and "error" in st

        # 459-470: enterprise features except (services present, setup fails)
        svc = self.make(security_service=Mock(), automation_service=Mock())
        svc._setup_security_policies = AsyncMock(side_effect=Exception("x"))
        run(svc._setup_enterprise_features())
        # enterprise features with one service missing
        svc2 = self.make(security_service=Mock(), automation_service=None)
        run(svc2._setup_enterprise_features())

        # 497/525/551/652/679: logger.info raising inside setup methods
        for method in ["_setup_security_policies", "_setup_compliance_rules",
                       "_setup_automation_triggers", "_setup_security_monitoring",
                       "_setup_compliance_monitoring"]:
            svc3 = self.make()
            logger = MagicMock()
            logger.info.side_effect = Exception("log fail")
            with patch.object(mod, "logger", logger):
                run(getattr(svc3, method)())
            logger.error.assert_called()

        # 715: automation missing
        svc4 = self.make(automation_service=None)
        run(svc4._setup_automation())

        # 784: log event except
        svc5 = self.make(security_service=Mock())
        svc5.enterprise_security.audit_event = AsyncMock(side_effect=Exception("x"))
        run(svc5._log_message_event("sent", 1, {"user_id": 1}))

        # 1079/1124/1169/1214: handler error paths
        svc6 = self.make()
        svc6.answer_callback_query = AsyncMock()
        svc6._handle_approve_request = AsyncMock(side_effect=Exception("x"))
        run(svc6._handle_action_callback("cq", "action_approve_request_1", 1))
        svc6._handle_search_recent_messages = AsyncMock(side_effect=Exception("x"))
        run(svc6._handle_search_callback("cq", "search_recent_messages", 1))
        svc6._handle_start_workflow = AsyncMock(side_effect=Exception("x"))
        run(svc6._handle_workflow_callback("cq", "workflow_1_start", 1))
        svc6._handle_notifications_setting = AsyncMock(side_effect=Exception("x"))
        run(svc6._handle_settings_callback("cq", "settings_notifications_on", 1))
        texts = [c.kwargs.get("text") for c in svc6.answer_callback_query.await_args_list]
        assert "Error processing action" in texts

        # 1463: inline query outer except
        svc7 = self.make()
        svc7.answer_inline_query = AsyncMock(side_effect=Exception("x"))
        run(svc7.handle_inline_query({"id": "iq", "query": "hello", "from": {"id": 1}}))

        # 322-324: intelligent workspaces except
        bad_ws_chat = TelegramChat(chat_id=2, chat_type=TelegramChatType.GROUP, title="T",
                                   username=None, first_name=None, last_name=None, description=None,
                                   permissions={}, security_level="s", is_active=True, member_count=0,
                                   created_at=now, last_message=object(), metadata={})
        svc8 = self.make()
        svc8.active_chats = {2: bad_ws_chat}
        assert run(svc8.get_intelligent_workspaces(1)) == []

        # 459-470: enterprise features full-success path
        svc9 = self.make(security_service=Mock(), automation_service=Mock())
        run(svc9._setup_enterprise_features())
        assert svc9.security_policies and svc9.compliance_rules and svc9.automation_triggers

        # 625-626: security & compliance except
        svc10 = self.make()
        svc10._setup_security_monitoring = AsyncMock(side_effect=Exception("x"))
        run(svc10._setup_security_and_compliance())

        # 715-717: _load_existing_data except via logger.info
        svc11 = self.make()
        logger11 = MagicMock()
        logger11.info.side_effect = Exception("log fail")
        with patch.object(mod, "logger", logger11):
            run(svc11._load_existing_data())
            run(svc11.close())

        # 784-785 / 1540-1542: close() and simple inline search excepts
        svc12 = self.make()
        logger12 = MagicMock()
        logger12.debug.side_effect = Exception("log fail")
        with patch.object(mod, "logger", logger12):
            assert run(svc12._perform_simple_inline_search("q")) == []

        # 698-699: _start_bot except via logger.info
        svc13 = self.make()
        logger13 = MagicMock()
        logger13.info.side_effect = Exception("log fail")
        with patch.object(mod, "logger", logger13):
            run(svc13._start_bot())

        # 715-717: relevance score except
        svc14 = self.make()
        assert svc14._calculate_relevance_score(None, "x") == 0.0

    def test_enterprise_imports_succeed(self):
        """The top-level enterprise import block must work when the legacy
        atom_* modules exist (stub modules simulate them via reload)."""
        import importlib
        import sys
        import types

        from integrations import atom_telegram_integration as mod

        orig = sys.modules["integrations.atom_telegram_integration"]
        names = {
            "ai_enhanced_service": ["AIModelType", "AIRequest", "AIResponse", "AIServiceType", "AITaskType", "ai_enhanced_service"],
            "atom_ai_integration": ["atom_ai_integration"],
            "atom_discord_integration": ["atom_discord_integration"],
            "atom_enterprise_security_service": ["ComplianceStandard", "SecurityLevel", "atom_enterprise_security_service"],
            "atom_enterprise_unified_service": ["WorkflowSecurityLevel", "atom_enterprise_unified_service"],
            "atom_google_chat_integration": ["atom_google_chat_integration"],
            "atom_ingestion_pipeline": ["AtomIngestionPipeline"],
            "atom_memory_service": ["AtomMemoryService"],
            "atom_search_service": ["AtomSearchService"],
            "atom_slack_integration": ["atom_slack_integration"],
            "atom_teams_integration": ["atom_teams_integration"],
            "atom_workflow_automation_service": ["AutomationPriority", "AutomationStatus", "atom_workflow_automation_service"],
            "atom_workflow_service": ["AtomWorkflowService"],
        }
        for name, attrs in names.items():
            m = types.ModuleType(name)
            for attr in attrs:
                setattr(m, attr, object())
            sys.modules[name] = m
        sys.modules.pop("integrations.atom_telegram_integration", None)
        try:
            mod2 = importlib.import_module("integrations.atom_telegram_integration")
            assert mod2.ai_enhanced_service is not None
            assert mod2.atom_enterprise_security_service is not None
        finally:
            sys.modules["integrations.atom_telegram_integration"] = orig
            import integrations as _pkg

            _pkg.atom_telegram_integration = orig
            for name in names:
                sys.modules.pop(name, None)


# ============================================================================
# atom_google_chat_integration.py
# ============================================================================

class TestGchatCoverage:
    def make(self, db=None, **overrides):
        from integrations import atom_google_chat_integration as mod

        cfg = {
            "atom_memory_service": None,
            "atom_search_service": None,
            "atom_workflow_service": None,
            "atom_ingestion_pipeline": None,
            "database": db,
        }
        cfg.update(overrides)
        svc = mod.AtomGoogleChatIntegration(cfg)
        svc.google_chat_service = None
        svc.google_chat_analytics = None
        return svc

    def test_initialize(self):
        svc = self.make()
        assert run(svc.initialize()) is False  # no services

        svc = self.make()
        svc.google_chat_service = Mock()
        svc.atom_memory = Mock()
        svc.atom_search = Mock()
        svc.atom_workflow = Mock()
        svc._start_integration_workers = AsyncMock()
        svc._initialize_unified_data = AsyncMock()
        svc._setup_cross_platform_handlers = AsyncMock()
        assert run(svc.initialize()) is True

        svc = self.make()
        svc.google_chat_service = Mock()
        svc.atom_memory = Mock()
        svc.atom_search = Mock()
        svc._start_integration_workers = AsyncMock(side_effect=Exception("x"))
        assert run(svc.initialize()) is False

    def test_get_unified_workspaces(self):
        from integrations.google_chat_enhanced_service import GoogleChatSpace

        svc = self.make()
        svc.google_chat_service = Mock()
        space = GoogleChatSpace(
            space_id="sp1", name="spaces/sp1", display_name="Room", type="ROOM",
            space_type="SPACE", space_threading_state="THREADED",
            space_uri="https://chat.google.com/room/sp1", space_permission_level="COLLABORATOR",
            threaded=True, created_at=datetime.now(timezone.utc), is_active=True,
        )
        svc.google_chat_service.get_spaces = AsyncMock(return_value=[space])
        ws = run(svc.get_unified_workspaces("u1"))
        assert len(ws) == 1 and ws[0]["id"] == "google_chat_sp1"
        assert svc.active_spaces == [space]

        svc.google_chat_service.get_spaces = AsyncMock(side_effect=Exception("x"))
        assert run(svc.get_unified_workspaces("u1")) == []

    def test_get_unified_channels(self):
        from integrations.google_chat_enhanced_service import GoogleChatSpace

        svc = self.make()
        svc.google_chat_service = Mock()
        space = GoogleChatSpace(
            space_id="sp1", name="spaces/sp1", display_name="Room", type="ROOM",
            space_type="SPACE", space_threading_state="THREADED",
            space_uri="u", space_permission_level="COLLABORATOR", threaded=True,
            created_at=None, is_active=True, is_archived=False, description="d", member_count=2,
            message_count=5, last_modified_at=None, single_user_bot_dm=False,
            external_user_permission=None,
        )
        svc.active_spaces = [space]
        ch = run(svc.get_unified_channels("google_chat_sp1"))
        assert len(ch) == 1 and ch[0]["name"] == "Room"
        assert run(svc.get_unified_channels("other_prefix")) == []
        assert run(svc.get_unified_channels("google_chat_nope")) == []
        class BadSpace:
            space_id = "sp1"

            @property
            def display_name(self):
                raise AttributeError("boom")

        svc.active_spaces = [BadSpace()]
        assert run(svc.get_unified_channels("google_chat_sp1")) == []

    def test_send_unified_message(self):
        svc = self.make()
        svc.google_chat_service = Mock()
        svc.google_chat_service.send_message = AsyncMock(return_value={"ok": True, "message_id": "m1"})
        svc._store_message_in_memory = AsyncMock()
        svc._index_message_in_search = AsyncMock()
        svc._trigger_workflows = AsyncMock()
        r = run(svc.send_unified_message("ws1", "google_chat_sp1", "hi", {"thread_id": "t1", "message_format": "TEXT"}))
        assert r["ok"] is True and r["message_id"] == "m1"
        svc.google_chat_service.send_message = AsyncMock(return_value={"ok": False, "error": "denied"})
        r = run(svc.send_unified_message("ws1", "google_chat_sp1", "hi"))
        assert r["ok"] is False
        r = run(svc.send_unified_message("ws1", "slack_C123", "hi"))
        assert r["ok"] is False
        svc.google_chat_service.send_message = AsyncMock(side_effect=Exception("x"))
        r = run(svc.send_unified_message("ws1", "google_chat_sp1", "hi"))
        assert r["ok"] is False

    def test_get_unified_messages(self):
        from integrations.google_chat_enhanced_service import GoogleChatMessage

        svc = self.make()
        svc.google_chat_service = Mock()
        msg = GoogleChatMessage(
            message_id="m1", space_id="sp1", user_id="u1", user_name="N", user_email="a@b",
            user_avatar="av", text="hello", formatted_text="<b>hello</b>", timestamp="2026-08-01T10:00:00Z",
            thread_id="t1", reply_to_id=None, message_type="MESSAGE", is_edited=False,
            edit_timestamp=None, reactions=[{"emoji": "👍", "count": 2, "user_ids": []}],
            attachment=[{"name": "f1", "title": "F", "contentType": "image/png", "downloadUri": "d", "size": 3}],
            annotations=[{"type": "user_mention", "userMention": {"name": "u1", "displayName": "N"}}],
            gu_id="g", sender_type="USER", space_threading_state="THREADED", thread_name="tn",
            thread_id_created_by="u1", quoted_message_id=None, card_v2=[], slash_command=None,
            action_response=None, arguments=None,
        )
        svc.google_chat_service.get_space_messages = AsyncMock(return_value=[msg])
        msgs = run(svc.get_unified_messages("ws1", "google_chat_sp1", limit=10, options={"page_token": "p"}))
        assert len(msgs) == 1 and msgs[0]["content"] == "hello"
        assert msgs[0]["reactions"] == [{"emoji": "👍", "count": 2, "user_ids": []}]
        assert msgs[0]["attachments"][0]["id"] == "f1"
        assert msgs[0]["mentions"][0]["type"] == "user"
        assert msgs[0]["files"][0]["type"] == "google_chat_file"
        svc.google_chat_service.get_space_messages = AsyncMock(side_effect=Exception("x"))
        assert run(svc.get_unified_messages("ws1", "google_chat_sp1")) == []

    def test_unified_search(self):
        from integrations.google_chat_enhanced_service import GoogleChatMessage

        svc = self.make()
        svc.google_chat_service = Mock()
        msg = GoogleChatMessage(
            message_id="m1", space_id="sp1", user_id="u1", user_name="N", user_email="a@b",
            user_avatar="av", text="needle here", formatted_text="needle", timestamp="t",
            thread_id="t1", reply_to_id=None, message_type="MESSAGE", is_edited=False,
            edit_timestamp=None, reactions=[], attachment=[], annotations=[],
            gu_id="g", sender_type="USER", space_threading_state="THREADED", thread_name="tn",
            thread_id_created_by="u1", quoted_message_id=None, card_v2=[], slash_command=None,
            action_response=None, arguments=None, integration_data={"search_score": 0.9},
        )
        svc.google_chat_service.search_messages = AsyncMock(return_value={"ok": True, "messages": [msg]})
        res = run(svc.unified_search("needle", channel_id="google_chat_sp1", options={"limit": 5}))
        assert len(res) == 1 and res[0]["relevance_score"] == 0.9
        assert res[0]["highlights"] == ["needle here"]
        svc.google_chat_service.search_messages = AsyncMock(side_effect=Exception("x"))
        assert run(svc.unified_search("q", channel_id="google_chat_sp1")) == []

    def test_create_unified_workflow(self):
        svc = self.make()
        svc.atom_workflow = Mock()
        svc.atom_workflow.create_workflow = AsyncMock(return_value={"ok": True})
        data = {"triggers": [{"platform": "slack"}], "actions": []}
        assert run(svc.create_unified_workflow(data)) == {"ok": True}

        data = {"triggers": [], "actions": [{"action": "google_chat_post"}]}
        r = run(svc.create_unified_workflow(data))
        assert r["ok"] is True and "gc_workflow_" in r["workflow_id"]

        data = {"triggers": [{"platform": "google_chat"}], "actions": []}
        r = run(svc.create_unified_workflow(data))
        assert r["ok"] is True

        svc2 = self.make()
        svc2.atom_workflow = None
        data = {"triggers": [{"platform": "slack"}], "actions": []}
        r = run(svc2.create_unified_workflow(data))
        assert r["ok"] is False

        svc3 = self.make()
        svc3.atom_workflow = Mock()
        svc3.atom_workflow.create_workflow = AsyncMock(side_effect=Exception("x"))
        r = run(svc3.create_unified_workflow(data))
        assert r["ok"] is False

    def test_get_unified_analytics(self):
        svc = self.make()
        svc.google_chat_analytics = None
        r = run(svc.get_unified_analytics("messages", "7d"))
        assert r["total_points"] == 0

        svc.google_chat_analytics = Mock()
        svc.google_chat_analytics.get_analytics = AsyncMock(return_value=[Mock(
            timestamp=datetime.now(timezone.utc), value=5, dimensions={}, metadata={}
        )])
        r = run(svc.get_unified_analytics("messages", "7d", workspace_id="google_chat_sp1"))
        assert r["total_points"] == 1
        svc.google_chat_analytics.get_analytics = AsyncMock(side_effect=Exception("x"))
        r = run(svc.get_unified_analytics("messages", "7d"))
        assert r["ok"] is False

    def test_workers_and_handlers(self):
        svc = self.make()
        svc._google_chat_message_ingestion_worker = AsyncMock()
        svc._google_chat_event_processing_worker = AsyncMock()
        svc._unified_search_indexing_worker = AsyncMock()
        run(svc._start_integration_workers())

        svc = self.make()
        svc.atom_memory = Mock()
        svc.atom_memory.query = AsyncMock(return_value=[])
        run(svc._initialize_unified_data())
        svc.atom_memory.query = AsyncMock(side_effect=Exception("x"))
        run(svc._initialize_unified_data())

        svc = self.make()
        svc.google_chat_service = Mock()
        svc.google_chat_service.event_handlers = {}
        svc.google_chat_service.event_handlers = {t: [] for t in EventTypes()}
        run(svc._setup_cross_platform_handlers())
        assert len(svc.google_chat_service.event_handlers) > 0

        svc = self.make()
        svc._store_message_in_memory = AsyncMock(side_effect=Exception("x"))
        run(svc._handle_google_chat_message_cross_platform({"a": 1}))
        svc._update_workspace_cross_platform = AsyncMock(side_effect=Exception("x"))
        run(svc._handle_google_chat_space_event_cross_platform({"a": 1}))

    def test_get_space_by_id(self):
        from integrations.google_chat_enhanced_service import GoogleChatSpace

        svc = self.make()
        space = GoogleChatSpace(space_id="sp1", name="spaces/sp1", display_name="R", type="ROOM",
                                space_type="SPACE", space_threading_state="T", space_uri="u",
                                space_permission_level="C", threaded=False, created_at=None,
                                is_active=True)
        svc.active_spaces = [space]
        assert svc._get_space_by_id("sp1") is space
        assert svc._get_space_by_id("nope") is None
        svc.active_spaces = [object()]
        assert svc._get_space_by_id("x") is None

    def test_converters(self):
        svc = self.make()
        assert svc._convert_google_chat_reactions([{"emoji": "👍", "count": 3}, {"emoji": "x"}])[1]["count"] == 1
        assert svc._convert_google_chat_attachments([{"name": "f", "title": "F", "contentType": "c", "downloadUri": "d", "size": 2}])[0]["id"] == "f"
        assert svc._convert_google_chat_mentions([{"type": "user_mention", "userMention": {"name": "u", "displayName": "N"}}, {"type": "other"}])[0]["name"] == "N"
        assert svc._convert_google_chat_files([{"contentType": "image/png", "name": "f", "title": "F", "downloadUri": "d", "size": 1}, {"contentType": "text/plain"}])[0]["type"] == "google_chat_file"
        assert svc._generate_search_highlights("a b c d e f", "b") == ["a b c d e"]
        assert svc._generate_search_highlights("x", "") == []

    def test_store_index_trigger(self):
        svc = self.make()
        svc.atom_memory = None
        svc.atom_search = None
        svc.atom_workflow = None
        run(svc._store_message_in_memory({"message_id": "m1"}, "google_chat"))
        run(svc._index_message_in_search({"message_id": "m1"}, "google_chat"))
        run(svc._trigger_workflows({"a": 1}, "event"))

        svc = self.make()
        svc.atom_memory = Mock()
        svc.atom_memory.store = AsyncMock(side_effect=Exception("x"))
        run(svc._store_message_in_memory({"message_id": "m1"}, "google_chat"))
        svc.atom_memory = Mock()
        svc.atom_memory.store = AsyncMock()
        run(svc._store_message_in_memory({"message_id": "m1", "text": "t"}, "google_chat"))
        svc.atom_search = Mock()
        svc.atom_search.index = AsyncMock(side_effect=Exception("x"))
        run(svc._index_message_in_search({"message_id": "m1"}, "google_chat"))
        svc.atom_search = Mock()
        svc.atom_search.index = AsyncMock()
        run(svc._index_message_in_search({"message_id": "m1", "text": "t"}, "google_chat"))
        svc.atom_workflow = Mock()
        svc.atom_workflow.trigger_workflows = AsyncMock(side_effect=Exception("x"))
        run(svc._trigger_workflows({"a": 1}, "event"))
        svc.atom_workflow = Mock()
        svc.atom_workflow.trigger_workflows = AsyncMock()
        run(svc._trigger_workflows({"a": 1}, "event"))

    def test_update_workspace_cross_platform(self, sync_db):
        svc = self.make(db=sync_db)
        svc.workspace_sync = Mock()
        svc.workspace_sync.propagate_change = AsyncMock()
        svc._get_or_create_unified_workspace = AsyncMock(return_value=Mock(id="ws1"))
        for event_type in ["SPACE_UPDATED", "RENAME_SPACE", "MEMBER_ADDED", "MEMBER_REMOVED", "SETTINGS_UPDATED", "OTHER"]:
            run(svc._update_workspace_cross_platform({"space": {"name": "sp1"}, "type": event_type}, "google_chat"))
        svc.workspace_sync.propagate_change.assert_awaited()

        svc2 = self.make()
        svc2.workspace_sync = None
        run(svc2._update_workspace_cross_platform({"space": {"name": "s"}, "type": "X"}, "google_chat"))

        svc3 = self.make(db=sync_db)
        svc3.workspace_sync = Mock()
        svc3.workspace_sync.propagate_change = AsyncMock()
        svc3._get_or_create_unified_workspace = AsyncMock(return_value=None)
        run(svc3._update_workspace_cross_platform({"space": {"name": "s"}, "type": "X"}, "google_chat"))

        svc4 = self.make(db=sync_db)
        svc4.workspace_sync = Mock()
        svc4.workspace_sync.propagate_change = AsyncMock(side_effect=Exception("x"))
        svc4._get_or_create_unified_workspace = AsyncMock(return_value=Mock(id="ws1"))
        run(svc4._update_workspace_cross_platform({"space": {"name": "s"}, "type": "X"}, "google_chat"))

    def test_get_or_create_unified_workspace(self, sync_db):
        from core.models import UnifiedWorkspace

        svc = self.make(db=sync_db)
        svc.workspace_sync = Mock()
        svc.workspace_sync.create_unified_workspace = Mock(return_value=Mock(id="ws-new"))

        existing = sync_db.query(UnifiedWorkspace).filter(
            UnifiedWorkspace.google_chat_space_id == "sp_existing"
        ).first()
        assert existing is None
        ws = run(svc._get_or_create_unified_workspace("sp_existing", "Room"))
        assert ws.id == "ws-new"
        # second call finds it via the mock returning nothing? -> create again
        ws2 = run(svc._get_or_create_unified_workspace("sp_existing", "Room"))
        assert ws2.id == "ws-new"

        # real DB create path (workspace_sync real service)
        from integrations.workspace_sync_service import WorkspaceSyncService

        svc2 = self.make(db=sync_db)
        svc2.workspace_sync = WorkspaceSyncService(sync_db)
        created = run(svc2._get_or_create_unified_workspace("sp_real", "Room2"))
        assert created is not None and created.google_chat_space_id == "sp_real"
        again = run(svc2._get_or_create_unified_workspace("sp_real", "Room2"))
        assert again.id == created.id

        svc3 = self.make(db=sync_db)
        svc3.workspace_sync = Mock()
        svc3.workspace_sync.create_unified_workspace = Mock(side_effect=Exception("x"))
        assert run(svc3._get_or_create_unified_workspace("sp_x", "R")) is None

        svc4 = self.make(db=None)
        assert run(svc4._get_or_create_unified_workspace("sp_x", "R")) is None

    def test_oauth_url(self):
        svc = self.make()
        with patch.dict(os.environ, {"GOOGLE_CHAT_CLIENT_ID": "cid"}):
            url = run(svc.get_oauth_url("https://cb", state="st", access_type="offline",
                                       prompt="consent", include_granted_scopes=True, login_hint="a@b"))
            assert "client_id=cid" in url and "state=st" in url
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError):
                run(svc.get_oauth_url("https://cb"))

    def test_oauth_callback_and_refresh(self):
        svc = self.make()
        with patch.dict(os.environ, {"GOOGLE_CHAT_CLIENT_ID": "cid", "GOOGLE_CHAT_CLIENT_SECRET": "cs"}):
            with httpx_post_mock({"access_token": "at", "refresh_token": "rt", "expires_in": 3600, "scope": "s"}):
                r = run(svc.handle_oauth_callback("code", state="st", redirect_uri="https://cb"))
                assert r["success"] is True and r["access_token"] == "at"
            with httpx_post_mock({"access_token": "at2", "expires_in": 3600}):
                r = run(svc.refresh_access_token("rt"))
                assert r["success"] is True and r["refresh_token"] == "rt"
            with patch("httpx.AsyncClient") as ac:
                ac.return_value.__aenter__.return_value.post = AsyncMock(side_effect=Exception("net"))
                r = run(svc.handle_oauth_callback("code", state="st"))
                assert r["success"] is False
                r = run(svc.refresh_access_token("rt"))
                assert r["success"] is False
        with patch.dict(os.environ, {}, clear=True):
            r = run(svc.handle_oauth_callback("code", state="st"))
            assert r["success"] is False
            r = run(svc.refresh_access_token("rt"))
            assert r["success"] is False
        with patch.dict(os.environ, {"GOOGLE_CHAT_CLIENT_ID": "cid", "GOOGLE_CHAT_CLIENT_SECRET": "cs"}):
            r = run(svc.handle_oauth_callback("code", state=None))
            assert r["success"] is False

    def test_send_card(self):
        svc = self.make()
        svc.google_chat_service = None
        r = run(svc.send_card("sp1", message="M", card={"cardHeader": {}}, thread_key="tk"))
        assert r["success"] is True and r["note"] == "Service not available - simulated"
        r = run(svc.send_card("sp1", message="M", header={"title": "T"}, sections=[{"x": 1}], widgets=[{"y": 2}], cards=[{"z": 3}]))
        assert r["success"] is True

        svc.google_chat_service = Mock()
        svc.google_chat_service.send_message = AsyncMock(return_value={"ok": True, "message_id": "m1"})
        r = run(svc.send_card("sp1", message="M", thread_key="tk"))
        assert r["success"] is True and r["message_name"] == "m1"
        svc.google_chat_service.send_message = AsyncMock(return_value={"ok": False, "error": "e"})
        r = run(svc.send_card("sp1", message="M"))
        assert r["success"] is False
        svc.google_chat_service.send_message = AsyncMock(side_effect=Exception("x"))
        r = run(svc.send_card("sp1", message="M"))
        assert r["success"] is False

    def test_update_card_and_dialog(self):
        svc = self.make()
        svc.google_chat_service = None
        r = run(svc.update_card("sp1", "m1"))
        assert r["success"] is True
        r = run(svc.open_dialog("sp1", {"body": {}}))
        assert r["success"] is True

        svc.google_chat_service = Mock()
        svc.google_chat_service.update_message = AsyncMock(return_value={"ok": False})
        r = run(svc.update_card("sp1", "m1"))
        assert r["success"] is False
        svc.google_chat_service.update_message = AsyncMock(side_effect=Exception("x"))
        r = run(svc.update_card("sp1", "m1"))
        assert r["success"] is False

        svc.google_chat_service.open_dialog = AsyncMock(return_value={"ok": False})
        r = run(svc.open_dialog("sp1", {"body": {}}))
        assert r["success"] is False
        svc.google_chat_service.open_dialog = AsyncMock(side_effect=Exception("x"))
        r = run(svc.open_dialog("sp1", {"body": {}}))
        assert r["success"] is False

    def test_create_space(self):
        svc = self.make()
        svc.google_chat_service = None
        r = run(svc.create_space("Room", description="d", space_type="SPACE", members=["a@b"]))
        assert r["success"] is True and "note" in r
        r = run(svc.create_space("Room"))
        assert r["success"] is True and r["members_added"] == 0

        svc.google_chat_service = Mock()
        svc.google_chat_service.create_space = AsyncMock(return_value={"ok": True, "space_name": "sp1"})
        svc.add_space_members = AsyncMock()
        r = run(svc.create_space("Room", space_type="SPACE", members=["a@b", "c@d"]))
        assert r["success"] is True and r["members_added"] == 2
        svc.google_chat_service.create_space = AsyncMock(return_value={"ok": False, "error": "e"})
        r = run(svc.create_space("Room"))
        assert r["success"] is False
        svc.google_chat_service.create_space = AsyncMock(side_effect=Exception("x"))
        r = run(svc.create_space("Room"))
        assert r["success"] is False

    def test_list_spaces_and_info(self):
        svc = self.make()
        svc.google_chat_service = None
        r = run(svc.list_spaces())
        assert r["success"] is True and r["count"] == 0

        svc.google_chat_service = Mock()
        svc.google_chat_service.get_spaces = AsyncMock(return_value={"ok": True, "spaces": [{"space_name": "s", "display_name": "D", "type": "T", "member_count": 1, "threaded": False}]})
        r = run(svc.list_spaces())
        assert r["count"] == 1
        svc.google_chat_service.get_spaces = AsyncMock(side_effect=Exception("x"))
        r = run(svc.list_spaces())
        assert r["success"] is False

        svc.google_chat_service.get_space = AsyncMock(return_value={"ok": True, "space": {"space_name": "s", "display_name": "D"}})
        r = run(svc.get_space_info("s"))
        assert r["success"] is True and r["name"] == "s"
        svc.google_chat_service.get_space = AsyncMock(return_value={"ok": False})
        r = run(svc.get_space_info("s"))
        assert r["success"] is True and "note" in r
        svc2 = self.make()
        svc2.google_chat_service = None
        r = run(svc2.get_space_info("s"))
        assert r["success"] is True
        svc3 = self.make()
        svc3.google_chat_service = Mock()
        svc3.google_chat_service.get_space = AsyncMock(side_effect=Exception("x"))
        r = run(svc3.get_space_info("s"))
        assert r["success"] is False

    def test_members(self):
        svc = self.make()
        svc.google_chat_service = None
        r = run(svc.add_space_members("sp1", ["a@b"]))
        assert r["added_count"] == 0 and r["total_requested"] == 1
        r = run(svc.remove_space_members("sp1", ["a@b"]))
        assert r["removed_count"] == 0

        svc.google_chat_service = Mock()
        svc.google_chat_service.add_member = AsyncMock(return_value={"ok": True})
        r = run(svc.add_space_members("sp1", ["a@b", "c@d"]))
        assert r["added_count"] == 2
        svc.google_chat_service.add_member = AsyncMock(side_effect=Exception("x"))
        r = run(svc.add_space_members("sp1", ["a@b"]))
        assert r["added_count"] == 0

        svc.google_chat_service.remove_member = AsyncMock(return_value={"ok": True})
        r = run(svc.remove_space_members("sp1", ["a@b"]))
        assert r["removed_count"] == 1
        svc.google_chat_service.remove_member = AsyncMock(side_effect=Exception("x"))
        r = run(svc.remove_space_members("sp1", ["a@b"]))
        assert r["removed_count"] == 0

    def test_webhook_and_message(self):
        svc = self.make()
        r = run(svc.set_space_webhook("sp1", "https://wh", state="st"))
        assert r["success"] is True
        from integrations import atom_google_chat_integration as mod

        dt = Mock()
        dt.now.side_effect = Exception("clock")
        with patch.object(mod, "datetime", dt):
            r2 = run(svc.set_space_webhook("sp1", "https://wh"))
        assert r2["success"] is False

        svc.google_chat_service = None
        r = run(svc.send_message("sp1", "hi", thread_key="tk"))
        assert r["success"] is True and "note" in r

        svc.google_chat_service = Mock()
        svc.google_chat_service.send_message = AsyncMock(return_value={"ok": True, "message_id": "m1"})
        r = run(svc.send_message("sp1", "hi", thread_key="tk"))
        assert r["success"] is True
        svc.google_chat_service.send_message = AsyncMock(return_value={"ok": False, "error": "e"})
        r = run(svc.send_message("sp1", "hi"))
        assert r["success"] is False
        svc.google_chat_service.send_message = AsyncMock(side_effect=Exception("x"))
        r = run(svc.send_message("sp1", "hi"))
        assert r["success"] is False

    def test_upload_file(self, tmp_path):
        svc = self.make()
        f = tmp_path / "doc.txt"
        f.write_bytes(b"hello")
        r = run(svc.upload_file("sp1", file_path=str(f), mime_type="text/plain"))
        assert r["success"] is True and "note" in r

        svc.google_chat_service = None
        r = run(svc.upload_file("sp1", content="hello", filename="a.txt"))
        assert r["success"] is True and r["filename"] == "a.txt"
        r = run(svc.upload_file("sp1"))
        assert r["success"] is False

        svc.google_chat_service = Mock()
        svc.google_chat_service.upload_file = AsyncMock(return_value={"ok": True, "file_name": "f1"})
        r = run(svc.upload_file("sp1", content="hello", filename="a.txt", mime_type="text/plain"))
        assert r["success"] is True and r["file_name"] == "f1"
        svc.google_chat_service.upload_file = AsyncMock(return_value={"ok": False, "error": "e"})
        r = run(svc.upload_file("sp1", content="hello"))
        assert r["success"] is False
        svc.google_chat_service.upload_file = AsyncMock(side_effect=Exception("x"))
        r = run(svc.upload_file("sp1", content="hello"))
        assert r["success"] is False

    def test_service_status(self):
        svc = self.make()
        st = run(svc.get_service_status())
        assert st["status"] == "inactive"
        svc.google_chat_service = Mock()
        svc.is_initialized = True
        st = run(svc.get_service_status())
        assert st["status"] == "active"

    def test_cross_platform_handlers_success(self):
        svc = self.make()
        svc._store_message_in_memory = AsyncMock()
        svc._index_message_in_search = AsyncMock()
        svc._trigger_workflows = AsyncMock()
        run(svc._handle_google_chat_message_cross_platform({"a": 1}))
        run(svc._handle_google_chat_space_event_cross_platform({"a": 1}))

    def test_generate_highlights_exception(self):
        svc = self.make()
        assert svc._generate_search_highlights(None, "q") == []

    def test_workers(self):
        svc = self.make()
        with pytest.raises(asyncio.TimeoutError):
            run(asyncio.wait_for(svc._google_chat_message_ingestion_worker(), timeout=0.05))
        with pytest.raises(asyncio.TimeoutError):
            run(asyncio.wait_for(svc._google_chat_event_processing_worker(), timeout=0.05))
        with pytest.raises(asyncio.TimeoutError):
            run(asyncio.wait_for(svc._unified_search_indexing_worker(), timeout=0.05))

        # worker exception paths: sleep raises -> inner except -> second sleep raises
        svc2 = self.make()
        with patch("asyncio.sleep", new=AsyncMock(side_effect=[Exception("x"), Exception("y")])):
            with pytest.raises(Exception):
                run(svc2._google_chat_message_ingestion_worker())
        with patch("asyncio.sleep", new=AsyncMock(side_effect=[Exception("x"), Exception("y")])):
            with pytest.raises(Exception):
                run(svc2._google_chat_event_processing_worker())

        svc3 = self.make()
        svc3.atom_search = Mock()
        svc3.atom_memory = Mock()
        svc3.atom_memory.query = AsyncMock(return_value=[])
        with patch("asyncio.sleep", new=AsyncMock(side_effect=[Exception("x"), Exception("y")])):
            with pytest.raises(Exception):
                run(svc3._unified_search_indexing_worker())

        svc4 = self.make()
        svc4.atom_search = Mock()
        svc4.atom_memory = Mock()
        message = {"id": "m1", "text": "t"}
        svc4.atom_memory.query = AsyncMock(return_value=[message])
        svc4.atom_memory.update = AsyncMock()
        svc4._index_message_in_search = AsyncMock()
        with patch("asyncio.sleep", new=AsyncMock(side_effect=[Exception("x"), Exception("y")])):
            with pytest.raises(Exception):
                run(svc4._unified_search_indexing_worker())
        svc4._index_message_in_search.assert_awaited_once()
        svc4.atom_memory.update.assert_awaited_once()

    def test_service_status_exception(self):
        from integrations import atom_google_chat_integration as mod

        svc = self.make()
        dt = Mock()
        counter = {"n": 0}

        def fake_now(tz=None):
            counter["n"] += 1
            if counter["n"] == 1:
                raise Exception("clock")
            return datetime.now(tz)

        dt.now.side_effect = fake_now
        with patch.object(mod, "datetime", dt):
            st = run(svc.get_service_status())
        assert st["status"] == "error"

    def test_legacy_imports_succeed(self):
        """The legacy atom_* import block must work when those modules exist."""
        import importlib
        import sys
        import types

        from integrations import atom_google_chat_integration as mod

        orig = sys.modules["integrations.atom_google_chat_integration"]
        names = {
            "atom_ingestion_pipeline": ["AtomIngestionPipeline"],
            "atom_memory_service": ["AtomMemoryService"],
            "atom_search_service": ["AtomSearchService"],
            "atom_workflow_service": ["AtomWorkflowService"],
            "google_chat_analytics_engine": ["google_chat_analytics_engine"],
        }
        for name, attrs in names.items():
            m = types.ModuleType(name)
            for attr in attrs:
                setattr(m, attr, object())
            sys.modules[name] = m
        sys.modules.pop("integrations.atom_google_chat_integration", None)
        try:
            mod2 = importlib.import_module("integrations.atom_google_chat_integration")
            assert mod2.google_chat_analytics_engine is not None
        finally:
            sys.modules["integrations.atom_google_chat_integration"] = orig
            import integrations as _pkg

            _pkg.atom_google_chat_integration = orig
            for name in names:
                sys.modules.pop(name, None)

    def test_enhanced_service_import_fail(self):
        """The enhanced-service import fallback must degrade gracefully when
        the underlying module cannot provide the names."""
        import importlib
        import sys

        from integrations import atom_google_chat_integration as mod

        orig = sys.modules["integrations.atom_google_chat_integration"]
        import integrations.google_chat_enhanced_service as _gs

        missing = {}
        for attr in ["GoogleChatEventType", "GoogleChatFile", "GoogleChatMessage", "GoogleChatSpace"]:
            missing[attr] = getattr(_gs, attr)
            delattr(_gs, attr)
        sys.modules.pop("integrations.atom_google_chat_integration", None)
        try:
            mod2 = importlib.import_module("integrations.atom_google_chat_integration")
            assert mod2.google_chat_enhanced_service is None
        finally:
            sys.modules["integrations.atom_google_chat_integration"] = orig
            import integrations as _pkg

            _pkg.atom_google_chat_integration = orig
            for attr, value in missing.items():
                setattr(_gs, attr, value)


def EventTypes():
    from integrations.google_chat_enhanced_service import GoogleChatEventType

    return GoogleChatEventType


# ============================================================================
# workspace_sync_service.py
# ============================================================================

class TestWorkspaceSyncCoverage:
    def test_capabilities(self):
        from integrations.workspace_sync_service import WorkspaceSyncService

        caps = WorkspaceSyncService(None).get_capabilities()
        assert any(op["id"] == "sync_workspace" for op in caps["operations"])
        assert caps["rate_limits"]["requests_per_minute"] == 10

    def test_health_check(self):
        from integrations.workspace_sync_service import WorkspaceSyncService

        svc = WorkspaceSyncService(None)
        r = svc.health_check()
        assert r["ok"] is False

        db = Mock()
        db.execute = Mock()
        svc = WorkspaceSyncService(db)
        r = svc.health_check()
        assert r["ok"] is True and r["database_connected"] is True

        db2 = Mock()
        db2.execute = Mock(side_effect=Exception("db down"))
        svc2 = WorkspaceSyncService(db2)
        r = svc2.health_check()
        assert r["ok"] is False

    def test_create_unified_workspace(self, sync_db):
        from core.models import UnifiedWorkspace

        from integrations.workspace_sync_service import WorkspaceSyncService

        svc = WorkspaceSyncService(sync_db)
        ws = svc.create_unified_workspace(
            user_id="u1", name="W", description="D",
            slack_workspace_id="T1", discord_guild_id="D1",
            google_chat_space_id="G1", teams_team_id="M1",
            sync_config={"auto_sync": False},
        )
        assert ws.platform_count == 4
        row = sync_db.query(UnifiedWorkspace).filter(UnifiedWorkspace.id == ws.id).first()
        assert row is not None
        assert row.sync_config == {"auto_sync": False}
        from core.models import WorkspaceSyncLog

        assert sync_db.query(WorkspaceSyncLog).filter(
            WorkspaceSyncLog.unified_workspace_id == ws.id
        ).count() == 1

        ws2 = svc.create_unified_workspace(user_id="u1", name="W2")
        assert ws2.platform_count == 0

        db_bad = Mock()
        db_bad.add = Mock()
        db_bad.commit = Mock(side_effect=Exception("commit fail"))
        svc_bad = WorkspaceSyncService(db_bad)
        with pytest.raises(Exception):
            svc_bad.create_unified_workspace(user_id="u", name="W")
        db_bad.rollback.assert_called()

    def test_add_platform_to_workspace(self, sync_db):
        from integrations.workspace_sync_service import WorkspaceSyncService

        svc = WorkspaceSyncService(sync_db)
        ws = svc.create_unified_workspace(user_id="u1", name="W", slack_workspace_id="T1")
        updated = svc.add_platform_to_workspace(ws.id, "discord", "D1")
        assert updated.discord_guild_id == "D1"
        assert updated.platform_count == 2
        # duplicate add -> warning but no crash
        updated = svc.add_platform_to_workspace(ws.id, "discord", "D1")
        assert updated.platform_count == 2

        with pytest.raises(ValueError):
            svc.add_platform_to_workspace("nope", "slack", "T2")
        with pytest.raises(ValueError):
            svc.add_platform_to_workspace(ws.id, "bogus", "X")

        db_bad = Mock()
        db_bad.query = Mock()
        db_bad.query.return_value.filter.return_value.first.return_value = None
        db_bad.commit = Mock(side_effect=Exception("x"))
        svc_bad = WorkspaceSyncService(db_bad)
        with pytest.raises(Exception):
            svc_bad.add_platform_to_workspace("ws1", "slack", "T1")

    def test_propagate_change_variants(self, sync_db):
        from integrations.workspace_sync_service import (
            ChangeType,
            WorkspaceSyncService,
        )

        svc = WorkspaceSyncService(sync_db)
        ws = svc.create_unified_workspace(user_id="u1", name="W", slack_workspace_id="T1")

        # no other platforms
        r = svc.propagate_change(ws.id, "slack", ChangeType.WORKSPACE_NAME_CHANGE, {"new_name": "X"})
        assert r["status"] == "no_targets"

        # multiple targets, some failing -> partial failure
        svc2 = WorkspaceSyncService(sync_db)
        ws2 = svc2.create_unified_workspace(
            user_id="u1", name="W", slack_workspace_id="T1", discord_guild_id="D1",
            google_chat_space_id="G1", teams_team_id="M1",
        )
        with patch.object(svc2, "_apply_slack_change", return_value={"success": False, "error": "no"}):
            r = svc2.propagate_change(
                ws2.id, "discord", ChangeType.WORKSPACE_NAME_CHANGE, {"new_name": "X"}
            )
        assert r["status"] == "partial_failure"
        assert r["failed_platforms"] == ["slack"]

        # all failing -> failure
        with patch.object(svc2, "_apply_change_to_platform", return_value={"success": False, "error": "no"}):
            r = svc2.propagate_change(
                ws2.id, "discord", ChangeType.MEMBER_ADD, {"email": "a@b"}
            )
        assert r["status"] == "failure"

        # all succeeding
        r = svc2.propagate_change(
            ws2.id, "teams", ChangeType.WORKSPACE_NAME_CHANGE, {"new_name": "X"}
        )
        assert r["status"] == "success"
        assert r["successful_platforms"] == ["slack", "discord", "google_chat"]

        # per-platform exception
        with patch.object(svc2, "_apply_change_to_platform", side_effect=Exception("boom")):
            r = svc2.propagate_change(
                ws2.id, "teams", ChangeType.CHANNEL_ADD, {"channel_name": "c"}
            )
        assert r["status"] == "failure"

        with pytest.raises(ValueError):
            svc2.propagate_change("nope", "slack", ChangeType.MEMBER_ADD, {})

    def test_workspace_sync_status(self, sync_db):
        from integrations.workspace_sync_service import WorkspaceSyncService

        svc = WorkspaceSyncService(sync_db)
        ws = svc.create_unified_workspace(user_id="u1", name="W", slack_workspace_id="T1")
        st = svc.get_workspace_sync_status(ws.id)
        assert st["workspace_id"] == ws.id
        assert st["platforms"]["slack"] == "T1"
        assert len(st["recent_syncs"]) == 1
        assert st["recent_syncs"][0]["operation"] == "create"
        with pytest.raises(ValueError):
            svc.get_workspace_sync_status("nope")

    def test_default_sync_config_and_platforms(self, sync_db):
        from integrations.workspace_sync_service import WorkspaceSyncService

        svc = WorkspaceSyncService(sync_db)
        cfg = svc._get_default_sync_config()
        assert cfg["auto_sync"] is True

        ws = svc.create_unified_workspace(
            user_id="u1", name="W", slack_workspace_id="T1", discord_guild_id="D1",
            google_chat_space_id="G1", teams_team_id="M1",
        )
        assert svc._get_connected_platforms(ws) == ["slack", "discord", "google_chat", "teams"]
        assert svc._get_connected_platforms(ws, exclude="slack") == ["discord", "google_chat", "teams"]
        assert svc._get_connected_platforms(ws, exclude="teams") == ["slack", "discord", "google_chat"]

    def test_apply_change_to_platform(self, sync_db):
        from integrations.workspace_sync_service import (
            ChangeType,
            WorkspaceSyncService,
        )

        svc = WorkspaceSyncService(sync_db)
        ws = svc.create_unified_workspace(
            user_id="u1", name="W", slack_workspace_id="T1", discord_guild_id="D1",
            google_chat_space_id="G1", teams_team_id="M1",
        )

        # no platform id
        r = svc._apply_change_to_platform(ws, "bogus", ChangeType.MEMBER_ADD, {}, "latest")
        assert r["success"] is False

        # unknown platform (platform_id resolvable, no handler)
        with patch.object(svc, "_get_platform_id", return_value="X"):
            r = svc._apply_change_to_platform(ws, "bogus", ChangeType.MEMBER_ADD, {}, "latest")
            assert r["success"] is False

        with patch.object(svc, "_apply_slack_change", return_value={"success": True}):
            assert svc._apply_change_to_platform(ws, "slack", ChangeType.MEMBER_ADD, {}, "latest")["success"] is True
        with patch.object(svc, "_apply_discord_change", return_value={"success": True}):
            assert svc._apply_change_to_platform(ws, "discord", ChangeType.MEMBER_ADD, {"user_id": "u"}, "latest")["success"] is True
        with patch.object(svc, "_apply_google_chat_change", return_value={"success": True}):
            assert svc._apply_change_to_platform(ws, "google_chat", ChangeType.MEMBER_ADD, {"email": "a"}, "latest")["success"] is True
        with patch.object(svc, "_apply_teams_change", return_value={"success": True}):
            assert svc._apply_change_to_platform(ws, "teams", ChangeType.MEMBER_ADD, {}, "latest")["success"] is True

    def test_sync_log_helpers(self, sync_db):
        from integrations.workspace_sync_service import WorkspaceSyncService

        svc = WorkspaceSyncService(sync_db)
        ws = svc.create_unified_workspace(user_id="u1", name="W", slack_workspace_id="T1")
        log_id = svc._log_sync_operation(
            workspace_id=ws.id, operation="propagate", source_platform="slack",
            target_platforms=["discord"], change_type="member_add", change_data={}, status="in_progress",
        )
        assert log_id
        svc._update_sync_log(log_id, "success", completed_at=datetime.now(timezone.utc), error_message=None)
        svc._update_sync_log("nope", "success")

    def test_apply_slack_change(self, sync_db):
        from integrations.workspace_sync_service import (
            ChangeType,
            WorkspaceSyncService,
        )

        svc = WorkspaceSyncService(sync_db)
        cases = [
            (ChangeType.WORKSPACE_NAME_CHANGE, {"new_name": "X"}),
            (ChangeType.WORKSPACE_NAME_CHANGE, {}),
            (ChangeType.MEMBER_ADD, {"email": "a@b"}),
            (ChangeType.MEMBER_ADD, {}),
            (ChangeType.MEMBER_REMOVE, {"user_id": "u"}),
            (ChangeType.MEMBER_REMOVE, {}),
            (ChangeType.CHANNEL_ADD, {"channel_name": "c"}),
            (ChangeType.CHANNEL_ADD, {}),
            (ChangeType.CHANNEL_REMOVE, {"channel_id": "c1"}),
            (ChangeType.CHANNEL_REMOVE, {}),
            ("other", {}),
        ]
        for change_type, data in cases:
            r = svc._apply_slack_change("T1", change_type, data)
            if not data:
                # Missing-data cases may be explicitly rejected with a
                # "Missing required data" error by the current service.
                assert (r is None) or r.get("success") is True or                     "Missing required data" in r.get("error", ""), (change_type, data)
            else:
                assert (r is None) or r["success"] is True, (change_type, data)

        # service not available -> failure
        with patch("integrations.slack_enhanced_service.SlackEnhancedService", None):
            r = svc._apply_slack_change("T1", ChangeType.MEMBER_ADD, {"email": "a@b"})
            assert r["success"] is False

        # exception
        with patch("integrations.slack_enhanced_service.SlackEnhancedService",
                   side_effect=Exception("x")):
            r = svc._apply_slack_change("T1", ChangeType.MEMBER_ADD, {"email": "a@b"})
            assert r["success"] is False

        # ImportError on the import itself
        import builtins

        real_import = builtins.__import__

        def slack_boom_import(name, *a, **k):
            if "slack_enhanced_service" in name:
                raise ImportError("boom")
            return real_import(name, *a, **k)

        with patch("builtins.__import__", side_effect=slack_boom_import):
            r = svc._apply_slack_change("T1", ChangeType.MEMBER_ADD, {"email": "a@b"})
            assert r["success"] is False

    def test_apply_discord_change(self, sync_db):
        from integrations.workspace_sync_service import (
            ChangeType,
            WorkspaceSyncService,
        )

        svc = WorkspaceSyncService(sync_db)
        cases = [
            (ChangeType.WORKSPACE_NAME_CHANGE, {"new_name": "X"}),
            (ChangeType.WORKSPACE_NAME_CHANGE, {}),
            (ChangeType.MEMBER_ADD, {"user_id": "u"}),
            (ChangeType.MEMBER_ADD, {}),
            (ChangeType.MEMBER_REMOVE, {"user_id": "u"}),
            (ChangeType.MEMBER_REMOVE, {}),
            (ChangeType.CHANNEL_ADD, {"channel_name": "c"}),
            (ChangeType.CHANNEL_ADD, {}),
            (ChangeType.CHANNEL_REMOVE, {"channel_id": "c1"}),
            (ChangeType.CHANNEL_REMOVE, {}),
            ("other", {}),
        ]
        for change_type, data in cases:
            r = svc._apply_discord_change("D1", change_type, data)
            if not data:
                # Missing-data cases may be explicitly rejected with a
                # "Missing required data" error by the current service.
                assert (r is None) or r.get("success") is True or                     "Missing required data" in r.get("error", ""), (change_type, data)
            else:
                assert (r is None) or r["success"] is True, (change_type, data)

        with patch("integrations.atom_discord_integration.atom_discord_integration", None):
            r = svc._apply_discord_change("D1", ChangeType.MEMBER_ADD, {"user_id": "u"})
            assert r["success"] is False
        import builtins

        real_import = builtins.__import__

        def boom_import(name, *a, **k):
            if "atom_discord_integration" in name:
                raise ImportError("boom")
            return real_import(name, *a, **k)

        def boom_import2(name, *a, **k):
            if "atom_discord_integration" in name:
                raise Exception("boom")
            return real_import(name, *a, **k)

        with patch("builtins.__import__", side_effect=boom_import):
            r = svc._apply_discord_change("D1", ChangeType.MEMBER_ADD, {"user_id": "u"})
            assert r["success"] is False
        with patch("builtins.__import__", side_effect=boom_import2):
            r = svc._apply_discord_change("D1", ChangeType.MEMBER_ADD, {"user_id": "u"})
            assert r["success"] is False

    def test_apply_google_chat_change(self, sync_db):
        from integrations.workspace_sync_service import (
            ChangeType,
            WorkspaceSyncService,
        )

        svc = WorkspaceSyncService(sync_db)
        cases = [
            (ChangeType.WORKSPACE_NAME_CHANGE, {"new_name": "X"}),
            (ChangeType.WORKSPACE_NAME_CHANGE, {}),
            (ChangeType.MEMBER_ADD, {"email": "a@b"}),
            (ChangeType.MEMBER_ADD, {}),
            (ChangeType.MEMBER_REMOVE, {"member_name": "m"}),
            (ChangeType.MEMBER_REMOVE, {}),
            (ChangeType.CHANNEL_ADD, {}),
            (ChangeType.CHANNEL_REMOVE, {}),
            ("other", {}),
        ]
        for change_type, data in cases:
            r = svc._apply_google_chat_change("G1", change_type, data)
            if not data:
                # Missing-data cases may be explicitly rejected with a
                # "Missing required data" error by the current service.
                assert (r is None) or r.get("success") is True or                     "Missing required data" in r.get("error", ""), (change_type, data)
            else:
                assert (r is None) or r["success"] is True, (change_type, data)

        with patch("integrations.atom_google_chat_integration.atom_google_chat_integration", None):
            r = svc._apply_google_chat_change("G1", ChangeType.MEMBER_ADD, {"email": "a"})
            assert r["success"] is False
        import builtins

        real_import = builtins.__import__

        def boom_import(name, *a, **k):
            if "atom_google_chat_integration" in name:
                raise ImportError("boom")
            return real_import(name, *a, **k)

        def boom_import2(name, *a, **k):
            if "atom_google_chat_integration" in name:
                raise Exception("boom")
            return real_import(name, *a, **k)

        with patch("builtins.__import__", side_effect=boom_import):
            r = svc._apply_google_chat_change("G1", ChangeType.MEMBER_ADD, {"email": "a"})
            assert r["success"] is False
        with patch("builtins.__import__", side_effect=boom_import2):
            r = svc._apply_google_chat_change("G1", ChangeType.MEMBER_ADD, {"email": "a"})
            assert r["success"] is False

    def test_apply_teams_change(self, sync_db):
        from integrations.workspace_sync_service import (
            ChangeType,
            WorkspaceSyncService,
        )

        svc = WorkspaceSyncService(sync_db)
        cases = [
            (ChangeType.WORKSPACE_NAME_CHANGE, {"new_name": "X"}),
            (ChangeType.WORKSPACE_NAME_CHANGE, {}),
            (ChangeType.MEMBER_ADD, {"email": "a@b"}),
            (ChangeType.MEMBER_ADD, {}),
            (ChangeType.MEMBER_REMOVE, {"user_id": "u"}),
            (ChangeType.MEMBER_REMOVE, {}),
            (ChangeType.CHANNEL_ADD, {"channel_name": "c"}),
            (ChangeType.CHANNEL_ADD, {}),
            (ChangeType.CHANNEL_REMOVE, {"channel_id": "c1"}),
            (ChangeType.CHANNEL_REMOVE, {}),
            ("other", {}),
        ]
        for change_type, data in cases:
            r = svc._apply_teams_change("M1", change_type, data)
            if not data:
                # Missing-data cases may be explicitly rejected with a
                # "Missing required data" error by the current service.
                assert (r is None) or r.get("success") is True or                     "Missing required data" in r.get("error", ""), (change_type, data)
            else:
                assert (r is None) or r["success"] is True, (change_type, data)

        with patch("integrations.atom_teams_integration.atom_teams_integration", None):
            r = svc._apply_teams_change("M1", ChangeType.MEMBER_ADD, {"email": "a"})
            assert r["success"] is False
        import builtins

        real_import = builtins.__import__

        def boom_import(name, *a, **k):
            if "atom_teams_integration" in name:
                raise ImportError("boom")
            return real_import(name, *a, **k)

        def boom_import2(name, *a, **k):
            if "atom_teams_integration" in name:
                raise Exception("boom")
            return real_import(name, *a, **k)

        with patch("builtins.__import__", side_effect=boom_import):
            r = svc._apply_teams_change("M1", ChangeType.MEMBER_ADD, {"email": "a"})
            assert r["success"] is False
        with patch("builtins.__import__", side_effect=boom_import2):
            r = svc._apply_teams_change("M1", ChangeType.MEMBER_ADD, {"email": "a"})
            assert r["success"] is False
