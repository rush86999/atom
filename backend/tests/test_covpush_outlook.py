"""Coverage-push tests for integrations.outlook_service + outlook_service_enhanced.

TDD bug hunts (red-green) covered here:
  R1  reply_to_email reports success when the Graph call failed (result ignored)
  R2  query params built by naive "&".join -> unencoded values break $filter/$search
  R3  execute_operation / sync_to_postgres_cache leak str(e) to callers
  R4  fetch_recent_messages calls async pipeline.ingest_message WITHOUT await
  R5  create_task_enhanced posts to nonexistent /users/{id}/tasks endpoint
  R6  enhanced _handle_response crashes on non-numeric Retry-After header
  R7  OutlookService.__init__ docstring is dead code (placed after statements)
  R8  _refresh_access_token is a stub: expired tokens are never refreshed
"""

import asyncio
import base64
import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from integrations.outlook_service import OutlookService
from integrations.outlook_service_enhanced import (
    OutlookAttachment,
    OutlookCalendarEvent,
    OutlookContact,
    OutlookEmail,
    OutlookEnhancedService,
    OutlookFolder,
    OutlookTask,
    OutlookUser,
)

UTC = timezone.utc


def dt(offset_minutes: float = 60) -> datetime:
    return datetime.now(UTC) + timedelta(minutes=offset_minutes)


def make_token(
    access: str = "access-1",
    refresh: Optional[str] = "refresh-1",
    expires_at: Optional[datetime] = None,
    user_id: str = "u-1",
):
    token = MagicMock()
    token.user_id = user_id
    token.access_token = access
    token.refresh_token = refresh
    token.expires_at = expires_at
    return token


class FakeResponse:
    def __init__(
        self,
        status: int = 200,
        payload: Any = None,
        text: str = "",
        headers: Optional[Dict[str, str]] = None,
        raise_on_json: bool = False,
    ):
        self.status = status
        self._payload = payload
        self._text = text
        self.headers = headers or {}
        self.raise_on_json = raise_on_json

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            raise aiohttp.ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=self.status,
                message=f"HTTP {self.status}",
            )

    async def json(self):
        if self.raise_on_json:
            raise aiohttp.ContentTypeError(
                request_info=MagicMock(), history=(), message="not json"
            )
        return self._payload

    async def text(self):
        return self._text


class FakeSession:
    """Records requests; serves responses per-method from FIFO stacks.

    Request methods are SYNCHRONOUS (returning FakeResponse directly) so they
    work inside ``async with session.get(...)`` in both service modules.
    """

    def __init__(self, default: Optional[FakeResponse] = None, responses: Optional[Dict[str, List]] = None):
        self.requests: List[Dict[str, Any]] = []
        self._default = default
        self._responses: Dict[str, List] = responses or {}
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def _next(self, method: str) -> Any:
        stack = self._responses.get(method)
        if stack:
            return stack.pop(0)
        if self._default is not None:
            return self._default
        return FakeResponse(200, {})

    def _record(self, method: str, url: str, **kw) -> FakeResponse:
        self.requests.append({"method": method, "url": url, **kw})
        resp = self._next(method)
        if isinstance(resp, Exception):
            raise resp
        return resp

    def get(self, url, **kw):
        return self._record("GET", url, **kw)

    def post(self, url, **kw):
        return self._record("POST", url, **kw)

    def patch(self, url, **kw):
        return self._record("PATCH", url, **kw)

    def put(self, url, **kw):
        return self._record("PUT", url, **kw)

    def delete(self, url, **kw):
        return self._record("DELETE", url, **kw)

    async def close(self):
        self.closed = True


def patch_client_session(module: str, fake: FakeSession):
    return patch(f"{module}.aiohttp.ClientSession", lambda *a, **k: fake)


@contextmanager
def token_env(token=None):
    """Start the core.database.get_db_session patch; yield the mocked db."""
    db = MagicMock()
    q = MagicMock()
    q.filter.return_value.first.return_value = token
    # Refresh fans out to both provider rows via .all() — serve the same
    # token there so the update loop exercises the caller's record.
    q.filter.return_value.all.return_value = [token] if token is not None else []
    db.query.return_value = q
    m = patch("core.database.get_db_session")
    m.start().return_value.__enter__.return_value = db
    try:
        yield db
    finally:
        m.stop()


@contextmanager
def decrypt_env():
    with patch(
        "core.privsec.token_encryption.decrypt_token",
        side_effect=lambda ciphertext, **kw: ciphertext or "",
    ):
        yield


def patch_encrypt():
    return patch(
        "core.privsec.token_encryption.encrypt_token",
        side_effect=lambda plaintext, **kw: plaintext,
    )


EMAIL_PAYLOAD = {
    "id": "m-1",
    "subject": "Hello",
    "bodyPreview": "preview",
    "body": {"contentType": "text", "content": "hello"},
    "sender": {"emailAddress": {"address": "a@b.c"}},
    "from": {"emailAddress": {"address": "a@b.c"}},
    "toRecipients": [{"emailAddress": {"address": "to@b.c"}}],
    "ccRecipients": [],
    "bccRecipients": [],
    "receivedDateTime": "2026-01-01T00:00:00Z",
    "sentDateTime": "2026-01-01T00:00:00Z",
    "hasAttachments": True,
    "importance": "high",
    "isRead": False,
    "webLink": "https://outlook.example/m-1",
    "conversationId": "c-1",
    "parentFolderId": "f-1",
    "attachments": [{"id": "a-1", "name": "x.pdf"}],
}

EVENT_PAYLOAD = {
    "id": "e-1",
    "subject": "Meeting",
    "body": {"contentType": "text", "content": "agenda"},
    "start": {"dateTime": "2026-01-01T10:00:00Z", "timeZone": "UTC"},
    "end": {"dateTime": "2026-01-01T11:00:00Z", "timeZone": "UTC"},
    "location": {"displayName": "Room 1"},
    "attendees": [
        {"emailAddress": {"address": "x@b.c", "name": "X"}, "type": "required"}
    ],
    "organizer": {"emailAddress": {"address": "org@b.c"}},
    "isAllDay": False,
    "showAs": "tentative",
    "sensitivity": "private",
    "webLink": "https://outlook.example/e-1",
    "createdDateTime": "2025-12-01T00:00:00Z",
    "lastModifiedDateTime": "2025-12-02T00:00:00Z",
}

CONTACT_PAYLOAD = {
    "id": "ct-1",
    "displayName": "Jane Doe",
    "givenName": "Jane",
    "surname": "Doe",
    "emailAddresses": [{"address": "jane@b.c"}],
    "businessPhones": ["+1-555"],
    "mobilePhone": "+1-666",
    "homePhones": ["+1-777"],
    "companyName": "ACME",
    "jobTitle": "Engineer",
    "officeLocation": "HQ",
    "createdDateTime": "2025-12-01T00:00:00Z",
    "lastModifiedDateTime": "2025-12-02T00:00:00Z",
}

TASK_PAYLOAD = {
    "id": "t-1",
    "subject": "Ship it",
    "body": {"contentType": "text", "content": "do it"},
    "importance": "high",
    "status": "inProgress",
    "createdDateTime": "2025-12-01T00:00:00Z",
    "lastModifiedDateTime": "2025-12-02T00:00:00Z",
    "dueDateTime": {"dateTime": "2026-02-01T00:00:00Z", "timeZone": "UTC"},
    "completedDateTime": None,
    "categories": ["work"],
}

USER_PAYLOAD = {
    "id": "u-1",
    "displayName": "Jane",
    "mail": "jane@b.c",
    "userPrincipalName": "jane@b.c",
    "jobTitle": "Engineer",
    "officeLocation": "HQ",
    "businessPhones": ["+1-555"],
    "mobilePhone": "+1-666",
}


def make_service(**kw) -> OutlookService:
    config = {"client_id": "cid", "client_secret": "csec", "tenant_id": "t-1", "redirect_uri": "http://cb"}
    config.update(kw)
    return OutlookService(tenant_id="t-1", config=config)


def make_enhanced(**kw) -> OutlookEnhancedService:
    return OutlookEnhancedService(
        client_id=kw.get("client_id", "cid"),
        client_secret=kw.get("client_secret", "csec"),
        tenant_id=kw.get("tenant_id", "t-1"),
    )


# ============================================================================
# R7: __init__ docstring is dead code (placed after statements)
# ============================================================================


class TestInit:
    def test_init_docstring_is_documented(self):
        assert OutlookService.__init__.__doc__ is not None
        assert "tenant" in OutlookService.__init__.__doc__.lower()

    def test_init_config_used(self):
        svc = make_service()
        assert svc.client_id == "cid"
        assert svc.client_secret == "csec"
        assert svc.tenant_id_config == "t-1"
        assert svc.redirect_uri == "http://cb"
        assert svc.base_url == "https://graph.microsoft.com/v1.0"

    def test_init_env_fallback(self, monkeypatch):
        monkeypatch.setenv("MICROSOFT_CLIENT_ID", "env-cid")
        monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "env-csec")
        monkeypatch.setenv("MICROSOFT_TENANT_ID", "env-tid")
        monkeypatch.setenv("OUTLOOK_REDIRECT_URI", "http://env-cb")
        svc = OutlookService(tenant_id="t-1", config={})
        assert svc.client_id == "env-cid"
        assert svc.client_secret == "env-csec"
        assert svc.tenant_id_config == "env-tid"
        assert svc.redirect_uri == "http://env-cb"

    def test_init_none_config(self):
        svc = OutlookService(tenant_id="t-1", config=None)
        assert svc.config == {}
        assert svc.tenant_id == "t-1"


# ============================================================================
# Token lifecycle (_is_token_expired / _get_access_token / _refresh_access_token)
# ============================================================================


class TestTokenLifecycle:
    def test_is_token_expired_no_expiry(self):
        assert make_service()._is_token_expired({}) is True

    def test_is_token_expired_int_past(self):
        assert make_service()._is_token_expired({"expires_at": dt(-5).timestamp()}) is True

    def test_is_token_expired_int_future(self):
        assert make_service()._is_token_expired({"expires_at": dt(30).timestamp()}) is False

    def test_is_token_expired_iso_past(self):
        assert make_service()._is_token_expired({"expires_at": "2020-01-01T00:00:00Z"}) is True

    def test_is_token_expired_iso_future(self):
        assert make_service()._is_token_expired({"expires_at": "2999-01-01T00:00:00Z"}) is False

    def test_is_token_expired_corrupt(self):
        assert make_service()._is_token_expired({"expires_at": "garbage"}) is True

    async def test_get_access_token_no_record(self):
        with token_env(token=None), decrypt_env():
            assert await make_service()._get_access_token("u-1") is None

    async def test_get_access_token_no_access(self):
        with token_env(token=make_token(access=None)), decrypt_env():
            assert await make_service()._get_access_token("u-1") is None

    async def test_get_access_token_valid_returns_decrypted(self):
        with token_env(token=make_token(expires_at=dt(30))), decrypt_env():
            result = await make_service()._get_access_token("u-1")
        assert result == "access-1"

    async def test_get_access_token_expired_refreshes(self):
        fake = FakeSession(
            responses={
                "POST": [
                    FakeResponse(
                        200,
                        {
                            "access_token": "new-token",
                            "refresh_token": "new-refresh",
                            "expires_in": 3600,
                        },
                    )
                ]
            }
        )
        with token_env(token=make_token(access="old-token", expires_at=dt(-5))), decrypt_env(), patch_encrypt(), patch_client_session(
            "integrations.outlook_service", fake
        ):
            svc = make_service()
            result = await svc._get_access_token("u-1")
        assert result == "new-token"
        assert fake.requests[0]["method"] == "POST"
        assert "login.microsoftonline.com" in fake.requests[0]["url"]
        assert "t-1" in fake.requests[0]["url"]

    async def test_get_access_token_expired_refresh_failure_returns_none(self):
        with token_env(token=make_token(access="old-token", refresh=None, expires_at=dt(-5))), decrypt_env():
            assert await make_service()._get_access_token("u-1") is None

    async def test_get_access_token_db_exception_returns_none(self):
        with patch("core.database.get_db_session") as gds:
            gds.return_value.__enter__.side_effect = RuntimeError("db down")
            assert await make_service()._get_access_token("u-1") is None

    async def test_refresh_persists_encrypted_tokens(self):
        fake = FakeSession(
            responses={
                "POST": [
                    FakeResponse(
                        200,
                        {"access_token": "new-token", "expires_in": 7200},
                    )
                ]
            }
        )
        with token_env(token=make_token(expires_at=dt(-5))) as db, decrypt_env(), patch_encrypt(), patch_client_session(
            "integrations.outlook_service", fake
        ):
            result = await make_service()._refresh_access_token(
                "u-1", {"refresh_token": "refresh-1", "access_token": "old"}
            )
        assert result == "new-token"
        record = db.query.return_value.filter.return_value.first.return_value
        assert record.access_token == "new-token"
        assert record.refresh_token == "refresh-1"
        assert record.expires_at is not None
        db.commit.assert_called_once()

    async def test_refresh_missing_refresh_token(self):
        assert await make_service()._refresh_access_token("u-1", {}) is None

    async def test_refresh_missing_config(self):
        svc = OutlookService(tenant_id="t-1", config={})
        assert await svc._refresh_access_token("u-1", {"refresh_token": "r"}) is None

    async def test_refresh_http_error(self):
        fake = FakeSession(responses={"POST": [FakeResponse(400, text="bad")]})
        with patch_client_session("integrations.outlook_service", fake):
            result = await make_service()._refresh_access_token("u-1", {"refresh_token": "r"})
        assert result is None

    async def test_refresh_exception(self):
        fake = FakeSession(responses={"POST": [aiohttp.ClientError("boom")]})
        with patch_client_session("integrations.outlook_service", fake):
            result = await make_service()._refresh_access_token("u-1", {"refresh_token": "r"})
        assert result is None

    async def test_refresh_response_missing_access_token(self):
        fake = FakeSession(responses={"POST": [FakeResponse(200, {"expires_in": 3600})]})
        with token_env(token=make_token(expires_at=dt(-5))), patch_client_session(
            "integrations.outlook_service", fake
        ):
            result = await make_service()._refresh_access_token("u-1", {"refresh_token": "r"})
        assert result is None


# ============================================================================
# _make_graph_request / _handle_response
# ============================================================================


class TestGraphRequest:
    @pytest.mark.parametrize(
        "method,kw",
        [
            ("GET", {}),
            ("POST", {"data": {"a": 1}}),
            ("PATCH", {"data": {"a": 1}}),
            ("DELETE", {}),
        ],
    )
    async def test_methods(self, method, kw):
        fake = FakeSession(default=FakeResponse(200, {"ok": True}))
        with patch_client_session("integrations.outlook_service", fake):
            result = await make_service()._make_graph_request(
                "u-1", "/me", method=method, access_token="tok", **kw
            )
        assert result == {"ok": True}
        req = fake.requests[0]
        assert req["method"] == method
        assert req["url"] == "https://graph.microsoft.com/v1.0/me"
        assert req["headers"]["Authorization"] == "Bearer tok"

    async def test_unsupported_method(self):
        with patch_client_session("integrations.outlook_service", FakeSession()):
            result = await make_service()._make_graph_request(
                "u-1", "/me", method="OPTIONS", access_token="tok"
            )
        assert result is None

    async def test_no_token(self):
        with token_env(token=None), decrypt_env():
            result = await make_service()._make_graph_request("u-1", "/me")
        assert result is None

    async def test_network_exception(self):
        fake = FakeSession(responses={"GET": [aiohttp.ClientError("conn refused")]})
        with patch_client_session("integrations.outlook_service", fake):
            result = await make_service()._make_graph_request("u-1", "/me", access_token="tok")
        assert result is None

    async def test_handle_response_202(self):
        assert await make_service()._handle_response(FakeResponse(202)) == {"success": True}

    async def test_handle_response_204(self):
        assert await make_service()._handle_response(FakeResponse(204)) == {"success": True}

    async def test_handle_response_error(self):
        resp = FakeResponse(500, text="oops")
        assert await make_service()._handle_response(resp) is None

    async def test_handle_response_json_error(self):
        assert await make_service()._handle_response(FakeResponse(200, raise_on_json=True)) is None


# ============================================================================
# Email operations
# ============================================================================


class TestEmailOperations:
    @pytest.fixture(autouse=True)
    def fake_access_token(self, monkeypatch):
        monkeypatch.setattr(OutlookService, "_get_access_token", AsyncMock(return_value="tok"))
    async def test_get_user_emails_inbox(self):
        fake = FakeSession(default=FakeResponse(200, {"value": [EMAIL_PAYLOAD]}))
        with patch_client_session("integrations.outlook_service", fake):
            emails = await make_service().get_user_emails("u-1", max_results=5)
        assert len(emails) == 1
        assert emails[0]["id"] == "m-1"
        assert emails[0]["subject"] == "Hello"
        assert emails[0]["has_attachments"] is True
        assert "/mailFolders/inbox/messages" in fake.requests[0]["url"]
        assert "%24top=5" in fake.requests[0]["url"]

    @pytest.mark.parametrize(
        "folder,endpoint_frag",
        [
            ("inbox", "/mailFolders/inbox/messages"),
            ("sent", "/mailFolders/sentitems/messages"),
            ("drafts", "/mailFolders/drafts/messages"),
            ("archive", "/me/messages"),
        ],
    )
    async def test_get_user_emails_folder_variants(self, folder, endpoint_frag):
        fake = FakeSession(default=FakeResponse(200, {"value": []}))
        with patch_client_session("integrations.outlook_service", fake):
            await make_service().get_user_emails("u-1", folder=folder)
        assert endpoint_frag in fake.requests[0]["url"]

    async def test_get_user_emails_no_value(self):
        fake = FakeSession(default=FakeResponse(200, {"other": 1}))
        with patch_client_session("integrations.outlook_service", fake):
            assert await make_service().get_user_emails("u-1") == []

    async def test_get_user_emails_error(self):
        with patch(
            "integrations.outlook_service.OutlookService._make_graph_request",
            new=AsyncMock(side_effect=RuntimeError("graph down")),
        ):
            assert await make_service().get_user_emails("u-1") == []

    async def test_get_user_emails_encodes_query_params(self):
        fake = FakeSession(default=FakeResponse(200, {"value": []}))
        with patch_client_session("integrations.outlook_service", fake):
            await make_service().get_user_emails("u-1", query="urgent & critical")
        url = fake.requests[0]["url"]
        assert "%24filter" in url
        assert "%26" in url
        assert "urgent & critical" not in url

    async def test_get_user_emails_with_attachments(self):
        fake = FakeSession(default=FakeResponse(200, {"value": []}))
        with patch_client_session("integrations.outlook_service", fake):
            await make_service().get_user_emails("u-1", include_attachments=True)
        assert "%24expand" in fake.requests[0]["url"]

    async def test_send_email(self):
        fake = FakeSession(default=FakeResponse(202))
        with patch_client_session("integrations.outlook_service", fake):
            result = await make_service().send_email(
                "u-1", ["a@b.c"], "Subj", "Body", cc_recipients=["c@b.c"], bcc_recipients=["d@b.c"]
            )
        assert result == {"success": True}
        assert fake.requests[0]["method"] == "POST"
        body = fake.requests[0]["json"]["message"]
        assert body["subject"] == "Subj"
        assert body["toRecipients"] == [{"emailAddress": {"address": "a@b.c"}}]
        assert body["ccRecipients"] == [{"emailAddress": {"address": "c@b.c"}}]
        assert body["bccRecipients"] == [{"emailAddress": {"address": "d@b.c"}}]

    async def test_send_email_error(self):
        with patch(
            "integrations.outlook_service.OutlookService._make_graph_request",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            assert await make_service().send_email("u-1", ["a@b.c"], "S", "B") is None

    async def test_reply_to_email_success(self):
        # The mixed-thread leak guard fires its own Graph reads before the
        # reply, so assert the REPLY call happened with the right payload
        # instead of asserting the exact total await count.
        with patch(
            "integrations.outlook_service.OutlookService._make_graph_request",
            new=AsyncMock(return_value={"success": True}),
        ) as mock_req:
            assert await make_service().reply_to_email("u-1", "m-1", "nice") is True
        reply_calls = [
            c for c in mock_req.await_args_list
            if c.args[1:3] == ("/me/messages/m-1/reply", "POST")
        ]
        assert reply_calls, "legacy /reply call missing"
        assert reply_calls[0].args[3] == {"comment": "nice"}

    async def test_reply_to_email_graph_failure_reports_false(self):
        with patch(
            "integrations.outlook_service.OutlookService._make_graph_request",
            new=AsyncMock(return_value=None),
        ):
            assert await make_service().reply_to_email("u-1", "m-1", "nice") is False

    async def test_reply_to_email_error(self):
        with patch(
            "integrations.outlook_service.OutlookService._make_graph_request",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            assert await make_service().reply_to_email("u-1", "m-1", "nice") is False

    async def test_create_draft_email(self):
        fake = FakeSession(default=FakeResponse(201, {"id": "d-1"}))
        with patch_client_session("integrations.outlook_service", fake):
            result = await make_service().create_draft_email("u-1", ["a@b.c"], "Draft", "Body", cc_recipients=["c@b.c"])
        assert result == {"id": "d-1"}
        assert fake.requests[0]["url"].endswith("/me/messages")
        assert fake.requests[0]["json"]["subject"] == "Draft"

    async def test_create_draft_email_error(self):
        with patch(
            "integrations.outlook_service.OutlookService._make_graph_request",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            assert await make_service().create_draft_email("u-1", ["a@b.c"], "D", "B") is None

    async def test_get_email_by_id(self):
        fake = FakeSession(default=FakeResponse(200, EMAIL_PAYLOAD))
        with patch_client_session("integrations.outlook_service", fake):
            email = await make_service().get_email_by_id("u-1", "m-1")
        assert email["id"] == "m-1"
        assert "/me/messages/m-1" in fake.requests[0]["url"]

    async def test_get_email_by_id_none(self):
        fake = FakeSession(default=FakeResponse(200, None))
        with patch_client_session("integrations.outlook_service", fake):
            assert await make_service().get_email_by_id("u-1", "m-1") is None

    async def test_get_email_by_id_error(self):
        with patch(
            "integrations.outlook_service.OutlookService._make_graph_request",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            assert await make_service().get_email_by_id("u-1", "m-1") is None

    async def test_delete_email_success(self):
        fake = FakeSession(default=FakeResponse(204))
        with patch_client_session("integrations.outlook_service", fake):
            assert await make_service().delete_email("u-1", "m-1") is True

    async def test_delete_email_failure(self):
        with patch(
            "integrations.outlook_service.OutlookService._make_graph_request",
            new=AsyncMock(return_value=None),
        ):
            assert await make_service().delete_email("u-1", "m-1") is False

    async def test_delete_email_error(self):
        with patch(
            "integrations.outlook_service.OutlookService._make_graph_request",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            assert await make_service().delete_email("u-1", "m-1") is False

    async def test_get_attachment_content(self):
        fake = FakeSession(default=FakeResponse(200, {"contentBytes": base64.b64encode(b"pdf").decode()}))
        with patch_client_session("integrations.outlook_service", fake):
            content = await make_service().get_attachment_content("u-1", "m-1", "a-1")
        assert content == b"pdf"
        assert "/attachments/a-1" in fake.requests[0]["url"]

    async def test_get_attachment_content_missing(self):
        fake = FakeSession(default=FakeResponse(200, {"id": "a-1"}))
        with patch_client_session("integrations.outlook_service", fake):
            assert await make_service().get_attachment_content("u-1", "m-1", "a-1") is None

    async def test_get_attachment_content_error(self):
        with patch(
            "integrations.outlook_service.OutlookService._make_graph_request",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            assert await make_service().get_attachment_content("u-1", "m-1", "a-1") is None

    async def test_get_unread_emails(self):
        fake = FakeSession(default=FakeResponse(200, {"value": [EMAIL_PAYLOAD]}))
        with patch_client_session("integrations.outlook_service", fake):
            emails = await make_service().get_unread_emails("u-1")
        assert len(emails) == 1
        assert "isRead+eq+false" in fake.requests[0]["url"]

    async def test_get_unread_emails_error(self):
        with patch(
            "integrations.outlook_service.OutlookService._make_graph_request",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            assert await make_service().get_unread_emails("u-1") == []

    async def test_get_unread_emails_no_value(self):
        fake = FakeSession(default=FakeResponse(200, {"other": 1}))
        with patch_client_session("integrations.outlook_service", fake):
            assert await make_service().get_unread_emails("u-1") == []

    async def test_search_emails(self):
        fake = FakeSession(default=FakeResponse(200, {"value": [EMAIL_PAYLOAD]}))
        with patch_client_session("integrations.outlook_service", fake):
            emails = await make_service().search_emails("u-1", "hello world")
        assert len(emails) == 1
        assert "hello world" not in fake.requests[0]["url"]

    async def test_search_emails_error(self):
        with patch(
            "integrations.outlook_service.OutlookService._make_graph_request",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            assert await make_service().search_emails("u-1", "q") == []

    async def test_search_emails_no_value(self):
        fake = FakeSession(default=FakeResponse(200, {"other": 1}))
        with patch_client_session("integrations.outlook_service", fake):
            assert await make_service().search_emails("u-1", "q") == []


# ============================================================================
# Calendar operations
# ============================================================================


class TestCalendarOperations:
    @pytest.fixture(autouse=True)
    def fake_access_token(self, monkeypatch):
        monkeypatch.setattr(OutlookService, "_get_access_token", AsyncMock(return_value="tok"))
    async def test_get_calendar_events_both_bounds(self):
        fake = FakeSession(default=FakeResponse(200, {"value": [EVENT_PAYLOAD]}))
        with patch_client_session("integrations.outlook_service", fake):
            events = await make_service().get_calendar_events("u-1", time_min="2026-01-01", time_max="2026-01-02")
        assert events[0]["id"] == "e-1"
        assert events[0]["subject"] == "Meeting"
        url = fake.requests[0]["url"]
        assert "start%2FdateTime" in url
        assert "end%2FdateTime" in url

    async def test_get_calendar_events_min_only(self):
        fake = FakeSession(default=FakeResponse(200, {"value": []}))
        with patch_client_session("integrations.outlook_service", fake):
            await make_service().get_calendar_events("u-1", time_min="2026-01-01")
        assert "start%2FdateTime" in fake.requests[0]["url"]

    async def test_get_calendar_events_max_only(self):
        fake = FakeSession(default=FakeResponse(200, {"value": []}))
        with patch_client_session("integrations.outlook_service", fake):
            await make_service().get_calendar_events("u-1", time_max="2026-01-02")
        assert "end%2FdateTime" in fake.requests[0]["url"]

    async def test_get_calendar_events_error(self):
        with patch(
            "integrations.outlook_service.OutlookService._make_graph_request",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            assert await make_service().get_calendar_events("u-1") == []

    async def test_create_calendar_event_full(self):
        fake = FakeSession(default=FakeResponse(201, {"id": "e-2"}))
        with patch_client_session("integrations.outlook_service", fake):
            result = await make_service().create_calendar_event(
                "u-1",
                "Standup",
                body="notes",
                start={"dateTime": "2026-01-01T09:00:00Z"},
                end={"dateTime": "2026-01-01T09:30:00Z"},
                location={"displayName": "Room 2"},
                attendees=["a@b.c", "c@b.c"],
            )
        assert result == {"id": "e-2"}
        body = fake.requests[0]["json"]
        assert body["location"] == {"displayName": "Room 2"}
        assert len(body["attendees"]) == 2

    async def test_create_calendar_event_defaults(self):
        fake = FakeSession(default=FakeResponse(201, {"id": "e-3"}))
        with patch_client_session("integrations.outlook_service", fake):
            await make_service().create_calendar_event("u-1", "Standup")
        body = fake.requests[0]["json"]
        assert body["start"]["timeZone"] == "UTC"
        assert body["end"]["timeZone"] == "UTC"

    async def test_create_calendar_event_error(self):
        with patch(
            "integrations.outlook_service.OutlookService._make_graph_request",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            assert await make_service().create_calendar_event("u-1", "S") is None

    async def test_update_calendar_event(self):
        fake = FakeSession(default=FakeResponse(200, {"id": "e-1"}))
        with patch_client_session("integrations.outlook_service", fake):
            result = await make_service().update_calendar_event("u-1", "e-1", {"subject": "New"})
        assert result == {"id": "e-1"}
        assert fake.requests[0]["method"] == "PATCH"
        assert fake.requests[0]["json"] == {"subject": "New"}

    async def test_update_calendar_event_error(self):
        with patch(
            "integrations.outlook_service.OutlookService._make_graph_request",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            assert await make_service().update_calendar_event("u-1", "e-1", {}) is None


# ============================================================================
# Contacts / tasks / profile
# ============================================================================


class TestContactsTasksProfile:
    @pytest.fixture(autouse=True)
    def fake_access_token(self, monkeypatch):
        monkeypatch.setattr(OutlookService, "_get_access_token", AsyncMock(return_value="tok"))
    async def test_get_user_contacts(self):
        fake = FakeSession(default=FakeResponse(200, {"value": [CONTACT_PAYLOAD]}))
        with patch_client_session("integrations.outlook_service", fake):
            contacts = await make_service().get_user_contacts("u-1", query="Jane")
        assert contacts[0]["id"] == "ct-1"
        assert contacts[0]["display_name"] == "Jane Doe"
        assert "contains%28displayName" in fake.requests[0]["url"]

    async def test_get_user_contacts_no_value(self):
        fake = FakeSession(default=FakeResponse(200, {"other": 1}))
        with patch_client_session("integrations.outlook_service", fake):
            assert await make_service().get_user_contacts("u-1") == []

    async def test_get_user_contacts_error(self):
        with patch(
            "integrations.outlook_service.OutlookService._make_graph_request",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            assert await make_service().get_user_contacts("u-1") == []

    async def test_create_contact_full(self):
        fake = FakeSession(default=FakeResponse(201, {"id": "ct-2"}))
        with patch_client_session("integrations.outlook_service", fake):
            result = await make_service().create_contact(
                "u-1",
                "John",
                given_name="John",
                surname="Smith",
                email_addresses=[{"address": "j@b.c"}],
                business_phones=["+1"],
                company_name="ACME",
            )
        assert result == {"id": "ct-2"}
        body = fake.requests[0]["json"]
        assert body["givenName"] == "John"
        assert body["businessPhones"] == ["+1"]

    async def test_create_contact_minimal(self):
        fake = FakeSession(default=FakeResponse(201, {"id": "ct-3"}))
        with patch_client_session("integrations.outlook_service", fake):
            await make_service().create_contact("u-1", "John")
        assert fake.requests[0]["json"] == {"displayName": "John"}

    async def test_create_contact_error(self):
        with patch(
            "integrations.outlook_service.OutlookService._make_graph_request",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            assert await make_service().create_contact("u-1", "John") is None

    async def test_get_user_tasks(self):
        fake = FakeSession(default=FakeResponse(200, {"value": [TASK_PAYLOAD]}))
        with patch_client_session("integrations.outlook_service", fake):
            tasks = await make_service().get_user_tasks("u-1", status="inProgress")
        assert tasks[0]["id"] == "t-1"
        assert "inProgress" in fake.requests[0]["url"]

    async def test_get_user_tasks_no_status(self):
        fake = FakeSession(default=FakeResponse(200, {"value": []}))
        with patch_client_session("integrations.outlook_service", fake):
            await make_service().get_user_tasks("u-1")
        assert "status+eq" not in fake.requests[0]["url"]

    async def test_get_user_tasks_no_value(self):
        fake = FakeSession(default=FakeResponse(200, {"other": 1}))
        with patch_client_session("integrations.outlook_service", fake):
            assert await make_service().get_user_tasks("u-1") == []

    async def test_get_user_tasks_error(self):
        with patch(
            "integrations.outlook_service.OutlookService._make_graph_request",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            assert await make_service().get_user_tasks("u-1") == []

    async def test_create_task_full(self):
        fake = FakeSession(default=FakeResponse(201, {"id": "t-2"}))
        with patch_client_session("integrations.outlook_service", fake):
            result = await make_service().create_task(
                "u-1",
                "Task",
                body="desc",
                importance="high",
                due_date_time={"dateTime": "2026-01-01T00:00:00Z"},
                categories=["work"],
            )
        assert result == {"id": "t-2"}
        body = fake.requests[0]["json"]
        assert body["body"] == {"contentType": "text", "content": "desc"}
        assert body["categories"] == ["work"]

    async def test_create_task_error(self):
        with patch(
            "integrations.outlook_service.OutlookService._make_graph_request",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            assert await make_service().create_task("u-1", "Task") is None

    async def test_get_user_profile(self):
        fake = FakeSession(default=FakeResponse(200, USER_PAYLOAD))
        with patch_client_session("integrations.outlook_service", fake):
            profile = await make_service().get_user_profile("u-1")
        assert profile["display_name"] == "Jane"
        assert profile["mail"] == "jane@b.c"

    async def test_get_user_profile_none(self):
        fake = FakeSession(default=FakeResponse(200, None))
        with patch_client_session("integrations.outlook_service", fake):
            assert await make_service().get_user_profile("u-1") is None

    async def test_get_user_profile_error(self):
        with patch(
            "integrations.outlook_service.OutlookService._make_graph_request",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            assert await make_service().get_user_profile("u-1") is None


# ============================================================================
# Capabilities / health / execute_operation
# ============================================================================


class TestServiceMeta:
    def test_get_capabilities(self):
        caps = make_service().get_capabilities()
        assert caps["supports_webhooks"] is True
        assert "send_email" in [op["id"] for op in caps["operations"]]

    def test_health_check_configured(self):
        health = make_service().health_check()
        assert health["healthy"] is True
        assert "last_check" in health

    def test_health_check_missing_client_id(self):
        # Env-coupled: a dev .env may export client ids; the service must
        # report unhealthy only when none is resolvable, so clear them.
        with patch.dict(
            "os.environ",
            {k: "" for k in ("MICROSOFT_CLIENT_ID", "AZURE_CLIENT_ID", "OUTLOOK_CLIENT_ID")},
        ):
            health = OutlookService(tenant_id="t-1", config={}).health_check()
        assert health["healthy"] is False
        assert "Missing client_id" in health["message"]

    async def test_execute_send_email(self):
        with patch(
            "integrations.outlook_service.OutlookService.send_email",
            new=AsyncMock(return_value={"success": True}),
        ):
            result = await make_service().execute_operation(
                "send_email",
                {"user_id": "u-1", "to_recipients": ["a@b.c"], "subject": "S", "body": "B"},
                context={"tenant_id": "t-1"},
            )
        assert result["success"] is True

    async def test_execute_read_emails(self):
        with patch(
            "integrations.outlook_service.OutlookService.get_user_emails",
            new=AsyncMock(return_value=[{"id": "m-1"}]),
        ):
            result = await make_service().execute_operation("read_emails", {"user_id": "u-1"})
        assert result["success"] is True
        assert result["result"] == [{"id": "m-1"}]

    async def test_execute_create_calendar_event(self):
        with patch(
            "integrations.outlook_service.OutlookService.create_calendar_event",
            new=AsyncMock(return_value={"id": "e-1"}),
        ):
            result = await make_service().execute_operation(
                "create_calendar_event", {"user_id": "u-1", "subject": "S"}
            )
        assert result["success"] is True

    async def test_execute_unknown_operation(self):
        result = await make_service().execute_operation("nope", {})
        assert result["success"] is False
        assert "Unknown operation" in result["error"]

    async def test_execute_tenant_mismatch(self):
        with pytest.raises(ValueError):
            await make_service().execute_operation(
                "read_emails", {}, context={"tenant_id": "other"}
            )

    async def test_execute_operation_error_no_str_leak(self):
        result = await make_service().execute_operation(
            "send_email", {"user_id": "u-1"}
        )
        assert result["success"] is False
        assert "to_recipients" not in result["error"]
        assert result["error"] != ""


# ============================================================================
# Sync / hub pipeline
# ============================================================================


class TestSync:
    def _metric_db(self, existing: bool):
        db = MagicMock()
        if existing:
            existing_metric = MagicMock()
            q = MagicMock()
            q.filter_by.return_value.first.return_value = existing_metric
            db.query.return_value = q
            return db, existing_metric
        q = MagicMock()
        q.filter_by.return_value.first.return_value = None
        db.query.return_value = q
        return db, None

    async def _sync_env(self, db):
        """Patch token lookup (valid token), graph session, and SessionLocal."""
        token = make_token(expires_at=dt(30))
        fake = FakeSession(
            default=FakeResponse(200, {"totalItemCount": 10, "unreadItemCount": 2})
        )
        patch_session = patch_client_session("integrations.outlook_service", fake)
        m2 = patch("core.database.SessionLocal", return_value=db)
        return token_env(token=token), patch_session, m2, decrypt_env()

    async def test_sync_to_postgres_cache_success_new(self):
        db, _ = self._metric_db(existing=False)
        tenv, patch_session, m2, decrypt = await self._sync_env(db)
        with tenv, patch_session, m2, decrypt:
            result = await make_service().sync_to_postgres_cache("u-1")
        assert result["success"] is True
        assert result["metrics_synced"] == 3
        assert db.add.call_count == 3
        db.commit.assert_called_once()

    async def test_sync_to_postgres_cache_success_existing(self):
        db, existing_metric = self._metric_db(existing=True)
        tenv, patch_session, m2, decrypt = await self._sync_env(db)
        with tenv, patch_session, m2, decrypt:
            result = await make_service().sync_to_postgres_cache("u-1")
        assert result["success"] is True
        assert db.add.call_count == 0
        assert existing_metric.last_synced_at is not None

    async def test_sync_to_postgres_cache_inbox_failure(self):
        with patch(
            "integrations.outlook_service.OutlookService._make_graph_request",
            new=AsyncMock(return_value=None),
        ):
            result = await make_service().sync_to_postgres_cache("u-1")
        assert result["success"] is False
        assert "Inbox stats" in result["error"]

    async def test_sync_to_postgres_cache_commit_error_no_str_leak(self):
        db, _ = self._metric_db(existing=False)
        db.commit.side_effect = RuntimeError("db exploded")
        tenv, patch_session, m2, decrypt = await self._sync_env(db)
        with tenv, patch_session, m2, decrypt:
            result = await make_service().sync_to_postgres_cache("u-1")
        assert result["success"] is False
        assert "db exploded" not in result["error"]
        db.rollback.assert_called_once()
        db.close.assert_called_once()

    async def test_sync_to_postgres_cache_outer_error(self):
        patch_session = patch_client_session(
            "integrations.outlook_service",
            FakeSession(default=FakeResponse(200, {"totalItemCount": 1, "unreadItemCount": 0})),
        )
        with token_env(token=make_token(expires_at=dt(30))), decrypt_env(), patch_session, patch(
            "core.database.SessionLocal", side_effect=RuntimeError("outer boom")
        ):
            result = await make_service().sync_to_postgres_cache("u-1")
        assert result["success"] is False
        assert "outer boom" not in result["error"]

    async def test_full_sync(self):
        with patch(
            "integrations.outlook_service.OutlookService.sync_to_postgres_cache",
            new=AsyncMock(return_value={"success": True, "metrics_synced": 3}),
        ):
            result = await make_service().full_sync("u-1")
        assert result["success"] is True
        assert result["user_id"] == "u-1"
        assert result["postgres_cache"]["metrics_synced"] == 3

    async def test_fetch_recent_messages_empty(self):
        with patch(
            "integrations.outlook_service.OutlookService.get_user_emails",
            new=AsyncMock(return_value=[]),
        ):
            assert await make_service().fetch_recent_messages("u-1") == []

    async def test_fetch_recent_messages_ingests(self):
        pipeline = MagicMock()
        pipeline.ingest_message = AsyncMock(return_value=True)
        with patch(
            "integrations.outlook_service.OutlookService.get_user_emails",
            new=AsyncMock(return_value=[{"id": "m-1"}]),
        ), patch(
            "integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline",
            return_value=pipeline,
        ):
            result = await make_service().fetch_recent_messages("u-1")
        assert result == [{"id": "m-1"}]
        pipeline.ingest_message.assert_awaited_once()
        assert pipeline.ingest_message.await_args.args[0] == "outlook"

    async def test_fetch_recent_messages_error(self):
        with patch(
            "integrations.outlook_service.OutlookService.get_user_emails",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            assert await make_service().fetch_recent_messages("u-1") == []

    async def test_sync_calendar_events_empty(self):
        with patch(
            "integrations.outlook_service.OutlookService.get_calendar_events",
            new=AsyncMock(return_value=[]),
        ):
            assert await make_service().sync_calendar_events("u-1") == []

    async def test_sync_calendar_events_normalizes(self):
        pipeline = MagicMock()
        pipeline.ingest_message = AsyncMock(return_value=True)
        with patch(
            "integrations.outlook_service.OutlookService.get_calendar_events",
            new=AsyncMock(return_value=[EVENT_PAYLOAD]),
        ), patch(
            "integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline",
            return_value=pipeline,
        ):
            result = await make_service().sync_calendar_events("u-1")
        assert len(result) == 1
        pipeline.ingest_message.assert_awaited_once()
        normalized = pipeline.ingest_message.await_args.args[1]
        assert normalized["title"] == "Meeting"
        assert normalized["metadata"]["organizer"] == "org@b.c"
        assert normalized["metadata"]["attendees"] == [
            {"email": "x@b.c", "name": "X"}
        ]

    async def test_sync_calendar_events_error(self):
        with patch(
            "integrations.outlook_service.OutlookService.get_calendar_events",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            assert await make_service().sync_calendar_events("u-1") == []


# ============================================================================
# ENHANCED SERVICE
# ============================================================================


class TestEnhancedInit:
    def test_init(self):
        svc = make_enhanced()
        assert svc.client_id == "cid"
        assert svc.session is None
        assert svc.users_cache == {}
        assert svc.emails_cache == {}

    async def test_get_session_creates(self):
        svc = make_enhanced()
        session = await svc._get_session()
        assert session is not None
        await svc._close_session()

    async def test_get_session_reuses(self):
        svc = make_enhanced()
        fake = FakeSession()
        svc.session = fake
        assert await svc._get_session() is fake
        fake.closed = True
        assert await svc._get_session() is not fake

    async def test_close_session(self):
        svc = make_enhanced()
        fake = FakeSession()
        svc.session = fake
        await svc._close_session()
        assert fake.closed is True

    async def test_get_access_token_valid(self):
        svc = make_enhanced()
        svc.access_token = "tok"
        svc.token_expiry = dt(5)
        assert await svc._get_access_token("u-1") == "tok"

    async def test_get_access_token_expired_raises(self):
        svc = make_enhanced()
        svc.access_token = "tok"
        svc.token_expiry = dt(-5)
        with pytest.raises(Exception):
            await svc._get_access_token("u-1")


class TestEnhancedRefresh:
    async def test_refresh_success(self):
        svc = make_enhanced()
        svc.refresh_token = "refresh-1"
        fake = FakeSession(
            responses={
                "POST": [
                    FakeResponse(
                        200,
                        {"access_token": "new", "refresh_token": "new-refresh", "expires_in": 3600},
                    )
                ]
            }
        )
        svc.session = fake
        assert await svc._refresh_access_token() is True
        assert svc.access_token == "new"
        assert svc.refresh_token == "new-refresh"
        assert "login.microsoftonline.com/t-1" in fake.requests[0]["url"]

    async def test_refresh_missing_refresh_token(self):
        svc = make_enhanced()
        assert await svc._refresh_access_token() is False

    async def test_refresh_http_error(self):
        svc = make_enhanced()
        svc.refresh_token = "refresh-1"
        fake = FakeSession(responses={"POST": [FakeResponse(400, text="bad")]})
        svc.session = fake
        assert await svc._refresh_access_token() is False

    async def test_refresh_exception(self):
        svc = make_enhanced()
        svc.refresh_token = "refresh-1"
        fake = FakeSession(responses={"POST": [aiohttp.ClientError("down")]})
        svc.session = fake
        assert await svc._refresh_access_token() is False


class TestEnhancedGraphRequest:
    def _svc(self, fake: FakeSession) -> OutlookEnhancedService:
        svc = make_enhanced()
        svc.access_token = "tok"
        svc.token_expiry = dt(5)
        svc.session = fake
        return svc

    @pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def test_methods(self, method):
        fake = FakeSession(default=FakeResponse(200, {"ok": True}))
        svc = self._svc(fake)
        result = await svc._make_graph_request(method, "me", "u-1", data={"a": 1})
        assert result == {"ok": True}
        assert fake.requests[0]["method"] == method
        assert fake.requests[0]["url"] == "https://graph.microsoft.com/v1.0/me"
        assert fake.requests[0]["headers"]["Authorization"] == "Bearer tok"

    async def test_unsupported_method(self):
        svc = self._svc(FakeSession())
        with pytest.raises(ValueError):
            await svc._make_graph_request("OPTIONS", "me", "u-1")

    async def test_client_error_raises(self):
        fake = FakeSession(responses={"GET": [aiohttp.ClientError("conn refused")]})
        svc = self._svc(fake)
        with pytest.raises(Exception, match="HTTP client error"):
            await svc._make_graph_request("GET", "me", "u-1")

    async def test_401_retry_refreshes_and_succeeds(self):
        fake = FakeSession(
            responses={
                "GET": [FakeResponse(401), FakeResponse(200, {"ok": True})],
                "POST": [
                    FakeResponse(
                        200,
                        {"access_token": "new", "expires_in": 3600},
                    )
                ],
            }
        )
        svc = self._svc(fake)
        svc.refresh_token = "refresh-1"
        result = await svc._make_graph_request("GET", "me", "u-1")
        assert result == {"ok": True}
        assert svc.access_token == "new"
        assert [r["method"] for r in fake.requests] == ["GET", "POST", "GET"]

    async def test_401_refresh_failure_raises(self):
        svc = self._svc(FakeSession(responses={"GET": [FakeResponse(401)]}))
        with pytest.raises(Exception, match="Authentication failed"):
            await svc._make_graph_request("GET", "me", "u-1")

    async def test_429_retry_backs_off(self):
        fake = FakeSession(
            responses={
                "GET": [
                    FakeResponse(429, headers={"Retry-After": "0"}),
                    FakeResponse(200, {"ok": True}),
                ]
            }
        )
        svc = self._svc(fake)
        with patch("integrations.outlook_service_enhanced.asyncio.sleep", new=AsyncMock()) as sleep:
            result = await svc._make_graph_request("GET", "me", "u-1")
        assert result == {"ok": True}
        sleep.assert_awaited_once_with(0)

    async def test_429_invalid_retry_after_falls_back(self):
        fake = FakeSession(
            responses={
                "GET": [
                    FakeResponse(429, headers={"Retry-After": "abc"}),
                    FakeResponse(200, {"ok": True}),
                ]
            }
        )
        svc = self._svc(fake)
        with patch("integrations.outlook_service_enhanced.asyncio.sleep", new=AsyncMock()) as sleep:
            result = await svc._make_graph_request("GET", "me", "u-1")
        assert result == {"ok": True}
        sleep.assert_awaited_once_with(5)

    async def test_handle_response_202(self):
        fake = FakeSession()
        svc = self._svc(fake)
        assert await svc._handle_response(FakeResponse(202), "POST", "me", "u-1", None, None, False) == {"success": True}

    async def test_handle_response_204(self):
        fake = FakeSession()
        svc = self._svc(fake)
        assert await svc._handle_response(FakeResponse(204), "POST", "me", "u-1", None, None, False) == {"success": True}

    async def test_handle_response_error_status(self):
        svc = self._svc(FakeSession())
        with pytest.raises(Exception, match="Graph API error: 500"):
            await svc._handle_response(FakeResponse(500), "GET", "me", "u-1", None, None, False)


class TestEnhancedEmails:
    async def test_get_user_emails_enhanced(self):
        fake = FakeSession(default=FakeResponse(200, {"value": [EMAIL_PAYLOAD]}))
        svc = make_enhanced()
        svc.access_token = "tok"
        svc.token_expiry = dt(5)
        svc.session = fake
        emails = await svc.get_user_emails_enhanced("u-1", folder="inbox", query="Q", include_attachments=True)
        assert len(emails) == 1
        assert emails[0].id == "m-1"
        assert fake.requests[0]["url"] == "https://graph.microsoft.com/v1.0/users/u-1/mailFolders/inbox/messages"

    async def test_get_user_emails_enhanced_cache(self):
        svc = make_enhanced()
        svc.access_token = "tok"
        svc.token_expiry = dt(5)
        svc.session = FakeSession(default=FakeResponse(200, {"value": []}))
        await svc.get_user_emails_enhanced("u-1")
        cached = svc.emails_cache["u-1:inbox:None:50:0"]
        await svc.get_user_emails_enhanced("u-1")
        assert svc.emails_cache["u-1:inbox:None:50:0"] is cached

    async def test_get_user_emails_enhanced_error(self):
        svc = make_enhanced()
        svc.access_token = "tok"
        svc.token_expiry = dt(5)
        svc.session = FakeSession(responses={"GET": [aiohttp.ClientError("x")]})
        assert await svc.get_user_emails_enhanced("u-1") == []

    async def test_send_email_enhanced(self):
        fake = FakeSession(default=FakeResponse(202))
        svc = make_enhanced()
        svc.access_token = "tok"
        svc.token_expiry = dt(5)
        svc.session = fake
        ok = await svc.send_email_enhanced(
            "u-1",
            ["a@b.c"],
            "Subj",
            "Body",
            cc_recipients=["c@b.c"],
            bcc_recipients=["d@b.c"],
            attachments=[{"name": "f.pdf", "contentBytes": "xx", "contentType": "application/pdf"}],
        )
        assert ok is True
        body = fake.requests[0]["json"]
        assert body["message"]["ccRecipients"] == [{"emailAddress": {"address": "c@b.c"}}]
        assert body["message"]["attachments"][0]["name"] == "f.pdf"

    async def test_send_email_enhanced_error(self):
        svc = make_enhanced()
        svc.access_token = "tok"
        svc.token_expiry = dt(5)
        svc.session = FakeSession(responses={"POST": [aiohttp.ClientError("x")]})
        assert await svc.send_email_enhanced("u-1", ["a@b.c"], "S", "B") is False


class TestEnhancedCalendarContactsTasks:
    async def test_create_calendar_event_enhanced(self):
        fake = FakeSession(default=FakeResponse(201, EVENT_PAYLOAD))
        svc = make_enhanced()
        svc.access_token = "tok"
        svc.token_expiry = dt(5)
        svc.session = fake
        event = await svc.create_calendar_event_enhanced(
            "u-1",
            "Meeting",
            "2026-01-01T10:00:00Z",
            "2026-01-01T11:00:00Z",
            location="Room 1",
            body="agenda",
            attendees=["x@b.c"],
            is_all_day=False,
            sensitivity="private",
            show_as="free",
            reminder_minutes=5,
        )
        assert event.id == "e-1"
        assert event.sensitivity == "private"
        assert fake.requests[0]["json"]["reminderMinutesBeforeStart"] == 5

    async def test_create_calendar_event_enhanced_no_result(self):
        fake = FakeSession(default=FakeResponse(200, None))
        svc = make_enhanced()
        svc.access_token = "tok"
        svc.token_expiry = dt(5)
        svc.session = fake
        assert await svc.create_calendar_event_enhanced("u-1", "M", "S", "E") is None

    async def test_create_calendar_event_enhanced_error(self):
        svc = make_enhanced()
        svc.access_token = "tok"
        svc.token_expiry = dt(5)
        svc.session = FakeSession(responses={"POST": [aiohttp.ClientError("x")]})
        assert await svc.create_calendar_event_enhanced("u-1", "M", "S", "E") is None

    async def test_create_contact_enhanced(self):
        fake = FakeSession(default=FakeResponse(201, CONTACT_PAYLOAD))
        svc = make_enhanced()
        svc.access_token = "tok"
        svc.token_expiry = dt(5)
        svc.session = fake
        contact = await svc.create_contact_enhanced(
            "u-1", "Jane Doe", given_name="Jane", surname="Doe",
            email_addresses=["jane@b.c"], business_phones=["+1"], mobile_phone="+2",
            job_title="Eng", company_name="ACME",
        )
        assert contact.id == "ct-1"
        assert fake.requests[0]["json"]["emailAddresses"] == [{"address": "jane@b.c", "name": "Jane Doe"}]

    async def test_create_contact_enhanced_error(self):
        svc = make_enhanced()
        svc.access_token = "tok"
        svc.token_expiry = dt(5)
        svc.session = FakeSession(responses={"POST": [aiohttp.ClientError("x")]})
        assert await svc.create_contact_enhanced("u-1", "Jane") is None

    async def test_create_contact_enhanced_no_result(self):
        svc = make_enhanced()
        svc.access_token = "tok"
        svc.token_expiry = dt(5)
        svc.session = FakeSession(default=FakeResponse(200, None))
        assert await svc.create_contact_enhanced("u-1", "Jane") is None

    async def test_create_task_enhanced_uses_todo_endpoint(self):
        fake = FakeSession(default=FakeResponse(201, TASK_PAYLOAD))
        svc = make_enhanced()
        svc.access_token = "tok"
        svc.token_expiry = dt(5)
        svc.session = fake
        task = await svc.create_task_enhanced(
            "u-1", "Ship", body="b", due_date="2026-01-01", start_date="2025-12-01",
            reminder_date="2025-12-31", categories=["work"],
        )
        assert task.id == "t-1"
        assert "/todo/lists/tasks/tasks" in fake.requests[0]["url"]
        assert fake.requests[0]["json"]["isReminderOn"] is True

    async def test_create_task_enhanced_error(self):
        svc = make_enhanced()
        svc.access_token = "tok"
        svc.token_expiry = dt(5)
        svc.session = FakeSession(responses={"POST": [aiohttp.ClientError("x")]})
        assert await svc.create_task_enhanced("u-1", "Ship") is None

    async def test_create_task_enhanced_no_result(self):
        svc = make_enhanced()
        svc.access_token = "tok"
        svc.token_expiry = dt(5)
        svc.session = FakeSession(default=FakeResponse(200, None))
        assert await svc.create_task_enhanced("u-1", "Ship") is None


class TestEnhancedReads:
    def _svc(self, fake: FakeSession) -> OutlookEnhancedService:
        svc = make_enhanced()
        svc.access_token = "tok"
        svc.token_expiry = dt(5)
        svc.session = fake
        return svc

    async def test_get_user_folders(self):
        fake = FakeSession(
            default=FakeResponse(
                200,
                {"value": [{"id": "f-1", "displayName": "Inbox", "totalItemCount": 5, "unreadItemCount": 1}]},
            )
        )
        svc = self._svc(fake)
        folders = await svc.get_user_folders("u-1", folder_type="Inbox")
        assert folders[0].id == "f-1"
        assert folders[0].display_name == "Inbox"
        assert "displayName eq 'Inbox'" in fake.requests[0]["params"]["$filter"]

    async def test_get_user_folders_cache(self):
        svc = self._svc(FakeSession(default=FakeResponse(200, {"value": []})))
        await svc.get_user_folders("u-1")
        assert "u-1:all" in svc.folders_cache
        assert await svc.get_user_folders("u-1") == []

    async def test_get_user_folders_error(self):
        svc = self._svc(FakeSession(responses={"GET": [aiohttp.ClientError("x")]}))
        assert await svc.get_user_folders("u-1") == []

    async def test_search_entities_enhanced(self):
        fake = FakeSession(
            default=FakeResponse(
                200,
                {
                    "value": [
                        {
                            "hitsContainers": [
                                {
                                    "hits": [
                                        {
                                            "id": "h-1",
                                            "resource": {"@odata.type": "#microsoft.graph.message", "subject": "Sub", "webLink": "w"},
                                            "summary": {"score": 0.9},
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                },
            )
        )
        svc = self._svc(fake)
        results = await svc.search_entities_enhanced("u-1", "Sub")
        assert results[0]["entityType"] == "message"
        assert results[0]["score"] == 0.9

    async def test_search_entities_enhanced_error(self):
        svc = self._svc(FakeSession(responses={"POST": [aiohttp.ClientError("x")]}))
        assert await svc.search_entities_enhanced("u-1", "q") == []

    async def test_get_user_profile_enhanced(self):
        fake = FakeSession(default=FakeResponse(200, USER_PAYLOAD))
        svc = self._svc(fake)
        profile = await svc.get_user_profile_enhanced("u-1")
        assert profile.display_name == "Jane"
        assert "profile:u-1" in svc.users_cache

    async def test_get_user_profile_enhanced_cache(self):
        svc = self._svc(FakeSession(default=FakeResponse(200, USER_PAYLOAD)))
        first = await svc.get_user_profile_enhanced("u-1")
        second = await svc.get_user_profile_enhanced("u-1")
        assert first is second

    async def test_get_user_profile_enhanced_none(self):
        svc = self._svc(FakeSession(default=FakeResponse(200, None)))
        assert await svc.get_user_profile_enhanced("u-1") is None

    async def test_get_user_profile_enhanced_error(self):
        svc = self._svc(FakeSession(responses={"GET": [aiohttp.ClientError("x")]}))
        assert await svc.get_user_profile_enhanced("u-1") is None

    async def test_get_upcoming_events(self):
        fake = FakeSession(default=FakeResponse(200, {"value": [EVENT_PAYLOAD]}))
        svc = self._svc(fake)
        events = await svc.get_upcoming_events("u-1", days=3)
        assert events[0].id == "e-1"
        assert "calendarView" in fake.requests[0]["url"]
        assert fake.requests[0]["params"]["startDateTime"] is not None

    async def test_get_upcoming_events_cache(self):
        svc = self._svc(FakeSession(default=FakeResponse(200, {"value": []})))
        await svc.get_upcoming_events("u-1")
        assert "u-1:upcoming:7" in svc.events_cache
        assert await svc.get_upcoming_events("u-1") == []

    async def test_get_upcoming_events_error(self):
        svc = self._svc(FakeSession(responses={"GET": [aiohttp.ClientError("x")]}))
        assert await svc.get_upcoming_events("u-1") == []

    async def test_get_unread_email_count(self):
        fake = FakeSession(default=FakeResponse(200, {"unreadItemCount": 7}))
        svc = self._svc(fake)
        assert await svc.get_unread_email_count("u-1") == 7

    async def test_get_unread_email_count_error(self):
        svc = self._svc(FakeSession(responses={"GET": [aiohttp.ClientError("x")]}))
        assert await svc.get_unread_email_count("u-1") == 0

    async def test_mark_emails_read(self):
        fake = FakeSession(default=FakeResponse(200, {"id": "m-1", "isRead": True}))
        svc = self._svc(fake)
        assert await svc.mark_emails_read("u-1", ["m-1", "m-2"]) is True
        assert len(fake.requests) == 2

    async def test_mark_emails_read_failure_stops(self):
        fake = FakeSession(
            responses={
                "PATCH": [
                    FakeResponse(200, {"id": "m-1"}),
                    FakeResponse(500),
                ]
            }
        )
        svc = self._svc(fake)
        assert await svc.mark_emails_read("u-1", ["m-1", "m-2"]) is False

    async def test_mark_emails_read_error(self):
        svc = self._svc(FakeSession(responses={"PATCH": [aiohttp.ClientError("x")]}))
        assert await svc.mark_emails_read("u-1", ["m-1"]) is False

    async def test_mark_emails_read_empty_result(self):
        svc = self._svc(FakeSession())
        with patch(
            "integrations.outlook_service_enhanced.OutlookEnhancedService._make_graph_request",
            new=AsyncMock(return_value=None),
        ):
            assert await svc.mark_emails_read("u-1", ["m-1"]) is False


class TestEnhancedCacheAndInfo:
    def test_clear_cache(self):
        svc = make_enhanced()
        svc.users_cache["k"] = 1
        svc.emails_cache["k"] = 1
        svc.events_cache["k"] = 1
        svc.contacts_cache["k"] = 1
        svc.tasks_cache["k"] = 1
        svc.folders_cache["k"] = 1
        svc._clear_cache()
        assert svc.users_cache == {} and svc.folders_cache == {}

    def test_clear_email_cache(self):
        svc = make_enhanced()
        svc.emails_cache["k"] = 1
        svc._clear_email_cache()
        assert svc.emails_cache == {}

    def test_clear_events_cache(self):
        svc = make_enhanced()
        svc.events_cache["k"] = 1
        svc._clear_events_cache()
        assert svc.events_cache == {}

    def test_clear_contacts_cache(self):
        svc = make_enhanced()
        svc.contacts_cache["k"] = 1
        svc._clear_contacts_cache()
        assert svc.contacts_cache == {}

    def test_clear_tasks_cache(self):
        svc = make_enhanced()
        svc.tasks_cache["k"] = 1
        svc._clear_tasks_cache()
        assert svc.tasks_cache == {}

    def test_clear_folders_cache(self):
        svc = make_enhanced()
        svc.folders_cache["k"] = 1
        svc._clear_folders_cache()
        assert svc.folders_cache == {}

    async def test_get_service_info(self):
        info = await make_enhanced().get_service_info()
        assert info["service"] == "outlook"
        assert info["version"] == "2.0.0"
        assert "email_management" in info["capabilities"]

    def test_dataclass_to_dict(self):
        user = OutlookUser(
            id="1", display_name="n", email="e@b.c", job_title="", department="",
            office_location="", mobile_phone="", business_phones=[], user_principal_name="",
            mail="", account_enabled=True, user_type="", preferred_language="", timezone="",
            usage_location="", metadata={},
        )
        assert user.to_dict()["display_name"] == "n"
        email = OutlookEmail(
            id="1", conversation_id="", subject="s", body_preview="", body={},
            importance="normal", has_attachments=False, is_read=True, is_draft=False,
            web_link="", created_datetime="", last_modified_datetime="",
            received_datetime="", sent_datetime="", from_address={}, to_recipients=[],
            cc_recipients=[], bcc_recipients=[], reply_to=[], categories=[], flag={},
            internet_message_headers=[], attachments=[], metadata={},
        )
        assert email.to_dict()["subject"] == "s"
        event = OutlookCalendarEvent(
            id="1", subject="s", body_preview="", body={}, start={}, end={}, location={},
            locations=[], attendees=[], organizer={}, is_all_day=False, is_cancelled=False,
            is_organizer=True, response_requested=True, response_status={}, sensitivity="normal",
            show_as="busy", type="singleInstance", web_link="", online_meeting={},
            recurrence={}, reminder_minutes_before_start=15, categories=[], extensions=[], metadata={},
        )
        assert event.to_dict()["subject"] == "s"
        contact = OutlookContact(
            id="1", display_name="n", given_name="", surname="", job_title="", department="",
            company_name="", business_phones=[], mobile_phone="", home_phones=[],
            email_addresses=[], im_addresses=[], home_address={}, business_address={},
            other_address={}, personal_notes="", birthday="", anniversary="", spouse_name="",
            children=[], manager="", assistant_name="", profession="", categories=[],
            created_date_time="", last_modified_date_time="", metadata={},
        )
        assert contact.to_dict()["display_name"] == "n"
        task = OutlookTask(
            id="1", subject="s", body={}, importance="normal", status="notStarted",
            completed_date_time={}, due_date_time={}, start_date_time={}, created_date_time="",
            last_modified_date_time="", is_reminder_on=False, reminder_date_time={},
            categories=[], assigned_to="", parent_folder_id="", conversation_id="",
            conversation_index="", flag={}, metadata={},
        )
        assert task.to_dict()["subject"] == "s"
        folder = OutlookFolder(
            id="1", display_name="n", parent_folder_id="", child_folder_count=0,
            unread_item_count=0, total_item_count=0, folder_type="", is_hidden=False,
            well_known_name="", metadata={},
        )
        assert folder.to_dict()["display_name"] == "n"
        attachment = OutlookAttachment(
            id="1", name="n", content_type="", size=0, is_inline=False, content_id="",
            content_bytes="", last_modified_date_time="", metadata={},
        )
        assert attachment.to_dict()["name"] == "n"


# ───────── Mail.Send consent precheck (Aug 31 canvas-send 403) ─────────
# Tokens minted before Mail.Send joined the OAuth scope request carry
# Mail.ReadWrite but not Mail.Send; refreshes never expand scopes, so every
# /me/sendMail died with a bare Graph 403. The send path must fail fast with
# an actionable "reconnect" error instead.

class TestMailSendScopePrecheck:
    def test_scope_grants_matches_bare_and_qualified_entries(self):
        assert OutlookService._scope_grants("mail.send mail.read", "Mail.Send")
        assert OutlookService._scope_grants(
            "https://graph.microsoft.com/Mail.Send offline_access", "Mail.Send")
        assert not OutlookService._scope_grants(
            "https://graph.microsoft.com/Mail.ReadWrite Contacts.Read", "Mail.Send")
        assert not OutlookService._scope_grants("", "Mail.Send")

    @pytest.mark.asyncio
    async def test_send_email_fails_fast_when_scope_missing(self):
        svc = OutlookService()
        stale = MagicMock(scope="https://graph.microsoft.com/Mail.ReadWrite User.Read")
        with token_env(token=stale), patch.object(
            svc, "_get_connection_scope", new=AsyncMock(
                return_value="https://graph.microsoft.com/Mail.ReadWrite User.Read")
        ):
            result = await svc.send_email("u-1", ["a@b.c"], "s", "body")

        assert result is None
        assert svc.last_send_error["needs_reconnect"] is True
        assert svc.last_send_error["missing_scope"] == "Mail.Send"

    @pytest.mark.asyncio
    async def test_send_email_proceeds_when_scope_granted(self):
        svc = OutlookService()
        ok_response = {"success": True}
        with patch.object(svc, "_get_connection_scope", new=AsyncMock(
            return_value="https://graph.microsoft.com/Mail.Send offline_access"
        )), patch.object(svc, "_make_graph_request", new=AsyncMock(
            return_value=ok_response
        )) as mk:
            result = await svc.send_email("u-1", ["a@b.c"], "s", "body")

        assert result == ok_response
        assert svc.last_send_error is None
        mk.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_email_skips_scope_check_for_explicit_token(self):
        svc = OutlookService()
        with patch.object(svc, "_get_connection_scope", new=AsyncMock()) as scope_q, patch.object(
            svc, "_make_graph_request", new=AsyncMock(return_value={"success": True})
        ):
            result = await svc.send_email("u-1", ["a@b.c"], "s", "body", token="tok")

        assert result == {"success": True}
        scope_q.assert_not_awaited()  # explicit token → scope unknown, let Graph decide
