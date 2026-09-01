"""Email attachment provider plumbing (Phase 1 of the attachment CRUD plan).

Covers:
- OutlookService.get_attachment_metadata / download_attachment — the normalized
  interface core.ingestion_pipeline dispatches on (Outlook previously lacked
  them, so binary-attachment ingestion silently fell back to body-only).
- Outlook send_email(attachments=...) — draft → attachment → send flow, with
  the >3 MB upload-session branch and the draft-cleanup failure path.
- GmailService.send_message(attachments=...) — MIME multipart attachments.
"""

import base64
import email as email_lib
import os

os.environ.setdefault("TESTING", "1")

from unittest.mock import MagicMock, patch

import pytest

from integrations.outlook_service import OutlookService


# ─── Outlook helpers ─────────────────────────────────────────────────────────


def _capture_calls():
    """Record every Graph call in order; serve canned draft/upload-session
    responses so attachment sends walk the real multi-call flow."""
    calls = []

    async def fake_graph(self, user_id, endpoint, method="GET", payload=None, **kw):
        calls.append({"endpoint": endpoint, "method": method, "payload": payload})
        if endpoint == "/me/messages" and method == "POST":
            return {"id": "draft-1"}
        if endpoint.endswith("/attachments/createUploadSession"):
            return {"uploadUrl": "https://outlook.office.com/upload-1"}
        return {"success": True}

    async def fake_token(self, user_id):
        return "tok"

    async def fake_scope(self, user_id):
        return "https://graph.microsoft.com/Mail.Send https://graph.microsoft.com/Mail.ReadWrite"

    return calls, (
        patch("integrations.outlook_service.OutlookService._make_graph_request", new=fake_graph),
        patch("integrations.outlook_service.OutlookService._get_access_token", new=fake_token),
        patch("integrations.outlook_service.OutlookService._get_connection_scope", new=fake_scope),
    )


class _FakeChunkResponse:
    def __init__(self, status):
        self.status = status
        self._text = "{}"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def text(self):
        return self._text


def _test_attachment(name="report.pdf", data=b"%PDF-1.4 fake", content_type="application/pdf"):
    return {
        "filename": name,
        "content_bytes": data,
        "content_type": content_type,
    }


# ─── Outlook: normalized metadata/download interface ────────────────────────


@pytest.mark.asyncio
async def test_outlook_get_attachment_metadata_normalizes_graph_values():
    calls = []

    async def fake_graph(self, user_id, endpoint, method="GET", payload=None, **kw):
        calls.append(endpoint)
        assert "$select=id,name,size,contentType,isInline" in endpoint
        return {
            "value": [
                {"id": "att-1", "name": "q3.pdf", "size": 10, "contentType": "application/pdf", "isInline": False},
                {"id": "att-2", "name": "inline.png", "size": 5, "contentType": "image/png", "isInline": True},
            ]
        }

    with patch("integrations.outlook_service.OutlookService._make_graph_request", new=fake_graph):
        meta = await OutlookService().get_attachment_metadata("u-1", "msg-1")

    assert [m["id"] for m in meta] == ["att-1", "att-2"]
    assert meta[0] == {
        "id": "att-1", "name": "q3.pdf", "size": 10,
        "contentType": "application/pdf", "isInline": False,
    }


@pytest.mark.asyncio
async def test_outlook_get_attachment_metadata_graph_failure_returns_empty():
    calls, patches = _capture_calls()
    with patches[0], patches[1], patches[2]:
        assert await OutlookService().get_attachment_metadata("u-1", "msg-1") == []


@pytest.mark.asyncio
async def test_outlook_download_attachment_delegates_to_content():
    async def fake_content(self, user_id, message_id, attachment_id, token=None):
        assert (user_id, message_id, attachment_id) == ("u-1", "msg-1", "att-1")
        return b"file-bytes"

    with patch("integrations.outlook_service.OutlookService.get_attachment_content", new=fake_content):
        assert await OutlookService().download_attachment("u-1", "msg-1", "att-1") == b"file-bytes"


# ─── Outlook: send with attachments ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_outlook_attachment_send_walks_draft_attach_send():
    calls, patches = _capture_calls()
    with patches[0], patches[1], patches[2]:
        result = await OutlookService().send_email(
            "u-1", ["a@b.com"], "Quarterly report", "See attached.",
            attachments=[_test_attachment()],
        )

    assert result == {"success": True}
    assert [c["endpoint"] for c in calls] == [
        "/me/messages",
        "/me/messages/draft-1/attachments",
        "/me/messages/draft-1/send",
    ]
    att = calls[1]["payload"]
    assert att["@odata.type"] == "#microsoft.graph.fileAttachment"
    assert att["name"] == "report.pdf"
    assert att["contentType"] == "application/pdf"
    assert base64.b64decode(att["contentBytes"]) == b"%PDF-1.4 fake"
    # draft body goes through the same HTML conversion as the direct send
    assert calls[0]["payload"]["body"]["contentType"] == "HTML"


@pytest.mark.asyncio
async def test_outlook_b64_attachment_input_is_accepted():
    calls, patches = _capture_calls()
    att = _test_attachment()
    att.pop("content_bytes")
    att["content_bytes_b64"] = base64.b64encode(b"%PDF-1.4 fake").decode()
    with patches[0], patches[1], patches[2]:
        await OutlookService().send_email(
            "u-1", ["a@b.com"], "S", "B", attachments=[att],
        )
    assert base64.b64decode(calls[1]["payload"]["contentBytes"]) == b"%PDF-1.4 fake"


@pytest.mark.asyncio
async def test_outlook_send_without_attachments_keeps_sendmail_path():
    calls, patches = _capture_calls()
    with patches[0], patches[1], patches[2]:
        await OutlookService().send_email("u-1", ["a@b.com"], "S", "B")
    assert calls[0]["endpoint"] == "/me/sendMail"


@pytest.mark.asyncio
async def test_outlook_attachment_missing_content_fails_before_any_call():
    calls, patches = _capture_calls()
    svc = OutlookService()
    with patches[0], patches[1], patches[2]:
        result = await svc.send_email(
            "u-1", ["a@b.com"], "S", "B",
            attachments=[{"filename": "x.pdf"}],
        )
    assert result is None
    assert calls == []  # nothing hit the wire
    assert svc.last_send_error is not None


@pytest.mark.asyncio
async def test_outlook_attachment_send_uses_upload_session_above_3mb():
    calls, patches = _capture_calls()
    big = b"x" * (OutlookService.GRAPH_INLINE_ATTACHMENT_LIMIT + 1)
    puts = []

    class _FakeSession:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def put(self, url, data=None, headers=None):
            puts.append({"url": url, "size": len(data), "headers": headers})
            return _FakeChunkResponse(201)

    with patches[0], patches[1], patches[2], patch(
        "integrations.outlook_service.aiohttp.ClientSession", _FakeSession
    ):
        result = await OutlookService().send_email(
            "u-1", ["a@b.com"], "S", "B",
            attachments=[_test_attachment(data=big)],
        )

    assert result == {"success": True}
    assert calls[1]["endpoint"] == "/me/messages/draft-1/attachments/createUploadSession"
    assert calls[1]["payload"]["AttachmentItem"]["size"] == len(big)
    # one 5 MiB-chunk PUT carrying the whole 3MB+1 payload, pre-authenticated URL
    assert len(puts) == 1
    assert puts[0]["url"] == "https://outlook.office.com/upload-1"
    assert puts[0]["headers"]["Content-Range"] == f"bytes 0-{len(big) - 1}/{len(big)}"
    assert calls[2]["endpoint"] == "/me/messages/draft-1/send"


@pytest.mark.asyncio
async def test_outlook_upload_session_chunks_large_files():
    calls, patches = _capture_calls()
    big = b"y" * (OutlookService.GRAPH_UPLOAD_CHUNK_SIZE + 1024)
    puts = []

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def put(self, url, data=None, headers=None):
            puts.append(len(data))
            return _FakeChunkResponse(201)

    with patches[0], patches[1], patches[2], patch(
        "integrations.outlook_service.aiohttp.ClientSession", _Session
    ):
        await OutlookService()._upload_large_attachment(
            "u-1", "draft-1", "big.bin", "application/octet-stream", big, "tok"
        )

    assert puts == [OutlookService.GRAPH_UPLOAD_CHUNK_SIZE, 1024]


@pytest.mark.asyncio
async def test_outlook_attachment_failure_deletes_draft_and_reports():
    calls = []

    async def failing_graph(self, user_id, endpoint, method="GET", payload=None, **kw):
        calls.append({"endpoint": endpoint, "method": method})
        if endpoint == "/me/messages" and method == "POST":
            return {"id": "draft-1"}
        if endpoint.endswith("/attachments"):
            return None  # Graph rejects the attachment
        return {"success": True}

    async def fake_token(self, user_id):
        return "tok"

    async def fake_scope(self, user_id):
        return "https://graph.microsoft.com/Mail.Send https://graph.microsoft.com/Mail.ReadWrite"

    svc = OutlookService()
    with patch("integrations.outlook_service.OutlookService._make_graph_request", new=failing_graph), \
         patch("integrations.outlook_service.OutlookService._get_access_token", new=fake_token), \
         patch("integrations.outlook_service.OutlookService._get_connection_scope", new=fake_scope):
        result = await svc.send_email(
            "u-1", ["a@b.com"], "S", "B", attachments=[_test_attachment()],
        )

    assert result is None
    assert calls[-1]["endpoint"] == "/me/messages/draft-1"  # draft cleaned up
    assert calls[-1]["method"] == "DELETE"
    assert "report.pdf" in svc.last_send_error["error"]


# ─── Gmail: multipart send with attachments ─────────────────────────────────


def _gmail_service_with_captured_raw():
    from integrations.gmail_service import GmailService

    svc = GmailService()
    sent = {}
    fake = MagicMock()
    fake.users.return_value.messages.return_value.send.return_value.execute.return_value = {
        "id": "msg-1"
    }

    def capture_send(userId, body):
        sent["kwargs"] = body
        return fake.users.return_value.messages.return_value.send.return_value

    fake.users.return_value.messages.return_value.send.side_effect = capture_send

    def fake_service(self, token=None):
        return fake

    return svc, sent, patch(
        "integrations.gmail_service.GmailService._get_service_with_token", new=fake_service
    )


def test_gmail_send_with_attachments_builds_mime_parts():
    svc, sent, ptch = _gmail_service_with_captured_raw()
    with ptch:
        result = svc.send_message(
            "a@b.com", "Report", "See attached.",
            attachments=[_test_attachment(), _test_attachment(name="data.csv",
                                                              data=b"a,b\n1,2",
                                                              content_type="text/csv")],
        )

    assert result == {"id": "msg-1"}
    parsed = email_lib.message_from_bytes(base64.urlsafe_b64decode(sent["kwargs"]["raw"]))
    by_name = {p.get_filename(): p for p in parsed.walk() if p.get_filename()}
    assert set(by_name) == {"report.pdf", "data.csv"}
    pdf_part = by_name["report.pdf"]
    assert pdf_part.get_content_type() == "application/pdf"
    assert pdf_part.get_payload(decode=True) == b"%PDF-1.4 fake"
    body_part = next(p for p in parsed.walk() if p.get_content_type() == "text/plain")
    assert "See attached." in body_part.get_payload(decode=True).decode()


def test_gmail_send_without_attachments_unchanged():
    svc, sent, ptch = _gmail_service_with_captured_raw()
    with ptch:
        svc.send_message("a@b.com", "S", "B")
    parsed = email_lib.message_from_bytes(base64.urlsafe_b64decode(sent["kwargs"]["raw"]))
    assert not [p for p in parsed.walk() if p.get_filename()]


def test_gmail_invalid_attachment_fails_the_send():
    svc, sent, ptch = _gmail_service_with_captured_raw()
    with ptch:
        result = svc.send_message(
            "a@b.com", "S", "B", attachments=[{"filename": "x.pdf"}],
        )
    assert result is None  # loud failure, not a silently dropped file
    assert "raw" not in sent
    with pytest.raises(ValueError):
        svc._attachment_payloads([{"filename": "x.pdf"}])
