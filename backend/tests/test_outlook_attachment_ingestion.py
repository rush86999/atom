"""Tests for attachment ingestion in the communication pipeline.

Pins the behavior that closes the "attachments never ingested" gap:

- Outlook polling expands the attachments collection for every message
  flagged hasAttachments (Graph list responses never include it), budgeted
  per page, and never fails the fetch on Graph errors.
- The email normalizer indexes attachment names for every attachment and
  the extracted text layer for text-like ones into the record content, so
  FTS/embeddings can find them.
- Raw contentBytes never reaches storage; the attachment metadata keeps
  only an `extracted_text` flag.
- Ingestion can be turned off per app via IngestionConfig.ingest_attachments.
"""

import base64
from types import SimpleNamespace

import pytest

import integrations.atom_communication_ingestion_pipeline as pipeline_module
from integrations.atom_communication_ingestion_pipeline import (
    _extract_attachment_text,
    ingestion_pipeline,
)


def _csv_b64(content: str = "name,amount\nacme,120\n") -> str:
    return base64.b64encode(content.encode()).decode()


# ---------------------------------------------------------------------------
# _extract_attachment_text
# ---------------------------------------------------------------------------


def test_extracts_text_from_csv_attachment():
    att = {
        "name": "invoice.csv",
        "contentType": "text/csv",
        "contentBytes": _csv_b64(),
    }
    assert _extract_attachment_text(att) == "name,amount\nacme,120\n"


def test_extracts_text_by_extension_without_mime():
    att = {"name": "notes.md", "contentBytes": _csv_b64("# hello")}
    assert _extract_attachment_text(att) == "# hello"


def test_binary_attachment_returns_none():
    att = {
        "name": "report.pdf",
        "contentType": "application/pdf",
        "contentBytes": base64.b64encode(b"%PDF-1.4 ...").decode(),
    }
    assert _extract_attachment_text(att) is None


def test_inline_attachment_returns_none():
    att = {
        "name": "sig.png",
        "isInline": True,
        "contentBytes": _csv_b64("text-ish but inline"),
    }
    assert _extract_attachment_text(att) is None


def test_invalid_base64_returns_none():
    att = {"name": "a.txt", "contentBytes": "!!!not-base64!!!"}
    assert _extract_attachment_text(att) is None


def test_oversized_attachment_returns_none():
    att = {
        "name": "big.csv",
        "contentBytes": base64.b64encode(b"x" * (600 * 1024)).decode(),
    }
    assert _extract_attachment_text(att) is None


def test_truncates_long_text():
    att = {"name": "log.txt", "contentBytes": _csv_b64("x" * 30_000)}
    text = _extract_attachment_text(att)
    assert text is not None and text.endswith("…[truncated]")


def test_accepts_snake_case_keys_from_fetch_normalizer():
    # The outlook fetch normalizer emits content_type/is_inline, not the
    # Graph camelCase — extraction must still work.
    att = {
        "name": "data.csv",
        "content_type": "text/csv",
        "is_inline": False,
        "contentBytes": _csv_b64(),
    }
    assert _extract_attachment_text(att) == "name,amount\nacme,120\n"


# ---------------------------------------------------------------------------
# Other platforms' payload shapes
# ---------------------------------------------------------------------------


def _b64url(content: str) -> str:
    return base64.urlsafe_b64encode(content.encode()).decode().rstrip("=")


def test_extracts_gmail_base64url_data():
    att = {
        "filename": "export.csv",
        "contentType": "text/csv",
        "data": _b64url("col1,col2\na,b\n"),
    }
    assert _extract_attachment_text(att) == "col1,col2\na,b\n"


def test_extracts_teams_inline_content_and_skips_reference():
    inline = {
        "name": "snippet.json",
        "contentType": "application/json",
        "content": base64.b64encode(b'{"ok": true}').decode(),
    }
    assert _extract_attachment_text(inline) == '{"ok": true}'

    reference = {
        "name": "sheet.xlsx",
        "contentType": "reference",
        "content": "https://sharepoint.example.com/sheet.xlsx",
    }
    assert _extract_attachment_text(reference) is None


def test_extracts_slack_files_by_mimetype():
    att = {
        "name": "debug.log",
        "mimetype": "text/plain",
        "contentBytes": _csv_b64("line one"),
    }
    assert _extract_attachment_text(att) == "line one"


def test_generic_app_normalizer_indexes_attachments():
    # Slack/Discord/Teams records flow through the generic branch — the
    # attachment indexing must apply there too, not just email.
    pipeline_module.ingestion_pipeline.ingestion_configs["slack"] = {
        "ingest_attachments": True
    }
    message = {
        "id": "s1",
        "content": "see file",
        "attachments": [
            {
                "name": "prices.csv",
                "mimetype": "text/csv",
                "size": 18,
                "contentBytes": _csv_b64("sku,price\nA1,9\n"),
            },
            {
                "name": "mockup.png",
                "mimetype": "image/png",
                "size": 2048,
            },
        ],
    }
    normalized = ingestion_pipeline._normalize_message("slack", message)

    assert "--- Attachments ---" in normalized["content"]
    assert "- prices.csv (text/csv / 18 bytes)" in normalized["content"]
    assert "sku,price" in normalized["content"]
    assert "- mockup.png (image/png / 2048 bytes)" in normalized["content"]
    stored = {a["name"]: a for a in normalized["attachments"]}
    assert stored["prices.csv"]["extracted_text"] is True
    assert stored["mockup.png"]["extracted_text"] is False
    assert "contentBytes" not in stored["prices.csv"]


# ---------------------------------------------------------------------------
# email-branch normalization: content indexing + contentBytes stripping
# ---------------------------------------------------------------------------


def _message_with_attachments():
    return {
        "id": "msg-1",
        "app_type": "outlook",
        "timestamp": __import__("datetime").datetime(2026, 8, 29, 12, 0, 0),
        "direction": "inbound",
        "sender_email": "acme@example.com",
        "sender": "Acme",
        "recipient": "me@example.com",
        "subject": "Invoice",
        "content": "<p>See attached</p>",
        "content_type": "html",
        "attachments": [
            {
                "id": "att-1",
                "name": "invoice.csv",
                "size": 20,
                "content_type": "text/csv",
                "is_inline": False,
                "contentBytes": _csv_b64(),
            },
            {
                "id": "att-2",
                "name": "logo.pdf",
                "size": 4000,
                "content_type": "application/pdf",
                "is_inline": False,
            },
        ],
        "metadata": {},
    }


def test_email_normalizer_indexes_attachment_text():
    pipeline_module.ingestion_pipeline.ingestion_configs["outlook"] = {
        "ingest_attachments": True
    }
    normalized = ingestion_pipeline._normalize_message(
        "outlook", _message_with_attachments()
    )

    content = normalized["content"]
    assert "--- Attachments ---" in content
    assert "- invoice.csv (text/csv / 20 bytes)" in content
    assert "name,amount" in content  # extracted text is searchable
    assert "- logo.pdf (application/pdf / 4000 bytes)" in content

    stored = normalized["attachments"]
    assert all("contentBytes" not in a for a in stored)
    by_name = {a["name"]: a for a in stored}
    assert by_name["invoice.csv"]["extracted_text"] is True
    assert by_name["logo.pdf"]["extracted_text"] is False


def test_email_normalizer_gate_turns_off_attachment_indexing():
    pipeline_module.ingestion_pipeline.ingestion_configs["outlook"] = {
        "ingest_attachments": False
    }
    try:
        normalized = ingestion_pipeline._normalize_message(
            "outlook", _message_with_attachments()
        )
        assert "--- Attachments ---" not in normalized["content"]
    finally:
        pipeline_module.ingestion_pipeline.ingestion_configs["outlook"] = {
            "ingest_attachments": True
        }


# ---------------------------------------------------------------------------
# _expand_outlook_attachments
# ---------------------------------------------------------------------------


class _FakeGraphResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload or {"value": []}
        self.headers = headers or {}

    def json(self):
        return self._payload


class _FakeGraphClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, headers=None, params=None):
        self.calls.append(url)
        return self._responses.pop(0)


@pytest.mark.asyncio
async def test_expand_fetches_attachments_for_flagged_messages(monkeypatch):
    messages = [
        {"id": "m1", "hasAttachments": True},
        {"id": "m2"},
        {"id": "m3", "hasAttachments": True},
    ]
    client = _FakeGraphClient(
        [
            _FakeGraphResponse(payload={"value": [{"id": "a1", "name": "f.csv"}]}),
            _FakeGraphResponse(payload={"value": [{"id": "a2", "name": "g.pdf"}]}),
        ]
    )
    await ingestion_pipeline._expand_outlook_attachments(client, {}, messages)

    assert len(client.calls) == 2
    assert "me/messages/m1/attachments" in client.calls[0]
    assert messages[0]["attachments"][0]["name"] == "f.csv"
    assert messages[1].get("attachments") is None  # untouched


@pytest.mark.asyncio
async def test_expand_respects_page_budget(monkeypatch):
    monkeypatch.setattr(
        ingestion_pipeline, "ATTACHMENT_EXPAND_BUDGET_PER_PAGE", 1
    )
    messages = [
        {"id": "m1", "hasAttachments": True},
        {"id": "m2", "hasAttachments": True},
    ]
    client = _FakeGraphClient(
        [_FakeGraphResponse(payload={"value": [{"id": "a1"}]})]
    )
    await ingestion_pipeline._expand_outlook_attachments(client, {}, messages)

    # Budget of 1: only the first flagged message is expanded.
    assert len(client.calls) == 1
    assert messages[0]["attachments"][0]["id"] == "a1"
    assert messages[1].get("attachments") is None


@pytest.mark.asyncio
async def test_expand_survives_graph_errors(monkeypatch):
    messages = [{"id": "m1", "hasAttachments": True}]

    class _BoomClient(_FakeGraphClient):
        async def get(self, url, headers=None, params=None):
            raise RuntimeError("network down")

    client = _BoomClient([])
    # Must not raise.
    await ingestion_pipeline._expand_outlook_attachments(client, {}, messages)
    assert messages[0].get("attachments") is None


# ---------------------------------------------------------------------------
# Gmail + Slack/Discord download expansions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gmail_expansion_fetches_text_first_then_binary(monkeypatch):
    """Text-like attachments keep priority on the shared page budget; binary
    ones are fetched in a second pass (they feed the documents memory index
    now), and only while budget remains. With the memory-index flag off the
    old text-only contract applies."""

    class _FakeGmailService:
        def __init__(self):
            self.requested = []

        def get_attachment_content(self, message_id, attachment_id):
            self.requested.append((message_id, attachment_id))
            return b"payload"

    import base64 as _b64

    # Flag on (default): text fetched first, binary second with leftover budget.
    svc = _FakeGmailService()
    messages = [
        {
            "id": "gm1",
            "attachments": [
                {"attachmentId": "a1", "filename": "export.csv", "contentType": "text/csv"},
                {"attachmentId": "a2", "filename": "scan.pdf", "contentType": "application/pdf"},
            ],
        },
    ]
    await ingestion_pipeline._expand_gmail_attachments(svc, messages)
    assert svc.requested == [("gm1", "a1"), ("gm1", "a2")]
    assert _b64.b64decode(messages[0]["attachments"][0]["data"]) == b"payload"
    assert _b64.b64decode(messages[0]["attachments"][1]["data"]) == b"payload"

    # Flag off: binary is never fetched (budget left unspent).
    monkeypatch.setenv("ENABLE_EMAIL_ATTACHMENT_MEMORY_INDEX", "false")
    svc = _FakeGmailService()
    messages = [
        {
            "id": "gm1",
            "attachments": [
                {"attachmentId": "a1", "filename": "export.csv", "contentType": "text/csv"},
                {"attachmentId": "a2", "filename": "scan.pdf", "contentType": "application/pdf"},
            ],
        },
    ]
    await ingestion_pipeline._expand_gmail_attachments(svc, messages)
    assert svc.requested == [("gm1", "a1")]
    assert "data" not in messages[0]["attachments"][1]


@pytest.mark.asyncio
async def test_gmail_expansion_binary_never_starves_text(monkeypatch):
    """One page budget: text-like attachments consume it first; if none
    remain, binary fetches are skipped rather than displacing text."""

    class _FakeGmailService:
        def __init__(self):
            self.requested = []

        def get_attachment_content(self, message_id, attachment_id):
            self.requested.append((message_id, attachment_id))
            return b"payload"

    monkeypatch.setattr(
        ingestion_pipeline, "ATTACHMENT_EXPAND_BUDGET_PER_PAGE", 1
    )
    svc = _FakeGmailService()
    messages = [
        {
            "id": "gm1",
            "attachments": [
                {"attachmentId": "a1", "filename": "export.csv", "contentType": "text/csv"},
                {"attachmentId": "a2", "filename": "scan.pdf", "contentType": "application/pdf"},
            ],
        },
    ]
    await ingestion_pipeline._expand_gmail_attachments(svc, messages)
    assert svc.requested == [("gm1", "a1")]


@pytest.mark.asyncio
async def test_slack_discord_downloads_set_content_bytes(monkeypatch):
    class _FakeDownloadResponse:
        def __init__(self, status_code, content):
            self.status_code = status_code
            self.content = content

    class _FakeDownloadClient:
        instances: list = []

        def __init__(self, *args, **kwargs):
            self._calls = []
            self.instances.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            self._calls.append((url, headers))
            if "slack.com" in url:
                return _FakeDownloadResponse(200, b"row1,row2\n")
            return _FakeDownloadResponse(200, b"discord,file\n")

    import integrations.atom_communication_ingestion_pipeline as mod

    def _fake_async_client(*args, **kwargs):
        return _FakeDownloadClient(*args, **kwargs)

    monkeypatch.setattr(mod.httpx, "AsyncClient", _fake_async_client)

    slack_messages = [
        {
            "attachments": [
                {
                    "name": "rows.csv",
                    "mimetype": "text/csv",
                    "url_private_download": "https://files.slack.com/files-pri/rows.csv",
                },
                {"name": "pic.png", "mimetype": "image/png"},
            ]
        }
    ]
    await ingestion_pipeline._expand_slack_attachments("xoxb-token", slack_messages)
    assert (
        slack_messages[0]["attachments"][0]["contentBytes"] == _csv_b64("row1,row2\n")
    )
    assert "contentBytes" not in slack_messages[0]["attachments"][1]
    # Slack downloads are token-authenticated (per-request header).
    slack_call_headers = _FakeDownloadClient.instances[0]._calls[0][1]
    assert slack_call_headers == {"Authorization": "Bearer xoxb-token"}

    discord_messages = [
        {
            "attachments": [
                {
                    "filename": "notes.txt",
                    "content_type": "text/plain",
                    "url": "https://cdn.discordapp.com/attachments/notes.txt",
                }
            ]
        }
    ]
    await ingestion_pipeline._expand_discord_attachments(discord_messages)
    assert (
        discord_messages[0]["attachments"][0]["contentBytes"] == _csv_b64("discord,file\n")
    )
    # Discord CDN downloads are unauthenticated.
    discord_call_headers = _FakeDownloadClient.instances[-1]._calls[0][1]
    assert discord_call_headers is None
