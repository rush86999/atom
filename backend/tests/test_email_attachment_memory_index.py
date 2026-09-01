"""Binary email-attachment memory indexing (Phase 2 of the attachment plan).

- core.email_attachment_ingestion.ingest_email_attachment_bytes — the shared
  bytes→documents-table entry point (status mapping, caps, provenance).
- CommunicationIngestionPipeline._ingest_binary_attachments — the live-poller
  hook: decodes raw payloads, enforces budgets, stamps ingestion status onto
  the normalized attachment records.
"""

import os

os.environ.setdefault("TESTING", "1")

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from core.email_attachment_ingestion import (
    attachment_ingestible,
    ingest_email_attachment_bytes,
)


# ─── heuristics ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("report.pdf", True),
        ("deck.pptx", True),
        ("book.xlsx", True),
        ("photo.PNG", True),
        ("notes.txt", False),  # text-like: already indexed by the comms pipeline
        ("data.csv", False),
        ("noext", False),
        ("", False),
    ],
)
def test_attachment_ingestible_extension_gate(filename, expected):
    assert attachment_ingestible(filename) is expected


# ─── shared ingestion entry point ────────────────────────────────────────────


def _ingest_patch(return_value):
    return patch(
        "core.auto_document_ingestion.AutoDocumentIngestionService.process_file_bytes",
        new=AsyncMock(return_value=return_value),
    )


@pytest.mark.asyncio
async def test_ingest_maps_processed_to_indexed():
    with _ingest_patch({"status": "ingested", "doc_id": "ext_abc", "chars_ingested": 420}) as mock:
        result = await ingest_email_attachment_bytes(
            provider="outlook",
            message_id="m1",
            attachment_id="a1",
            filename="report.pdf",
            content=b"%PDF fake",
            user_id="u-1",
            email_subject="Q3 numbers",
            email_from="boss@corp.test",
        )

    assert result == {"status": "indexed", "doc_id": "ext_abc", "chars": 420}
    kwargs = mock.await_args.kwargs
    assert kwargs["external_id"] == "m1:a1"  # stable, source-scoped identity
    assert kwargs["source"] == "outlook"
    assert kwargs["extra_metadata"]["source_type"] == "email_attachment"
    assert kwargs["extra_metadata"]["email_subject"] == "Q3 numbers"


@pytest.mark.asyncio
async def test_ingest_reports_unchanged_as_cached_hit():
    with _ingest_patch(
        {"status": "skipped", "reason": "unchanged", "doc_id": "ext_abc", "chars_ingested": 0}
    ):
        result = await ingest_email_attachment_bytes(
            provider="gmail", message_id="m1", attachment_id="a1",
            filename="report.pdf", content=b"%PDF fake",
        )
    assert result["status"] == "indexed"
    assert result["cached"] is True


@pytest.mark.asyncio
async def test_ingest_maps_skipped_and_error_statuses():
    with _ingest_patch({"status": "skipped", "reason": "no_text"}):
        assert (
            await ingest_email_attachment_bytes(
                provider="outlook", message_id="m", attachment_id="a",
                filename="scan.pdf", content=b"x",
            )
        )["status"] == "skipped"
    with _ingest_patch({"status": "error", "reason": "parse_failed"}):
        assert (
            await ingest_email_attachment_bytes(
                provider="outlook", message_id="m", attachment_id="a",
                filename="scan.pdf", content=b"x",
            )
        )["status"] == "error"


@pytest.mark.asyncio
async def test_ingest_rejects_unsupported_extension_without_parsing():
    with _ingest_patch({"status": "ingested", "doc_id": "x", "chars_ingested": 1}) as mock:
        result = await ingest_email_attachment_bytes(
            provider="outlook", message_id="m", attachment_id="a",
            filename="archive.zip", content=b"PK",
        )
    assert result["status"] == "unsupported"
    mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_ingest_enforces_size_cap(monkeypatch):
    monkeypatch.setenv("MAX_EMAIL_ATTACHMENT_INGEST_MB", "1")
    with _ingest_patch({"status": "ingested", "doc_id": "x", "chars_ingested": 1}) as mock:
        result = await ingest_email_attachment_bytes(
            provider="outlook", message_id="m", attachment_id="a",
            filename="big.pdf", content=b"x" * (1024 * 1024 + 1),
        )
    assert result["status"] == "skipped"
    assert result["reason"] == "too_large"
    mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_ingest_never_raises():
    with patch(
        "core.auto_document_ingestion.AutoDocumentIngestionService.process_file_bytes",
        side_effect=RuntimeError("boom"),
    ):
        result = await ingest_email_attachment_bytes(
            provider="outlook", message_id="m", attachment_id="a",
            filename="report.pdf", content=b"x",
        )
    assert result["status"] == "error"


# ─── live-pipeline hook ──────────────────────────────────────────────────────


def _normalized_for(attachments):
    return {
        "id": "msg-1",
        "subject": "Q3 report",
        "sender": "boss@corp.test",
        "timestamp": datetime(2026, 9, 1, 12, 0, 0),
        "attachments": attachments,
        "metadata": {"user_id": "u-9"},
    }


def _pdf_b64(content: str = "%PDF-1.4 fake") -> str:
    import base64

    return base64.b64encode(content.encode()).decode()


@pytest.mark.asyncio
async def test_pipeline_hook_indexes_binary_and_stamps_status():
    import integrations.atom_communication_ingestion_pipeline as mod

    normalized = _normalized_for(
        [{"id": "att-1", "name": "report.pdf", "contentType": "application/pdf", "size": 11}]
    )
    raw = [
        {"id": "att-1", "name": "report.pdf", "contentType": "application/pdf",
         "size": 11, "contentBytes": _pdf_b64()},
    ]
    with patch.object(
        mod, "ingest_email_attachment_bytes", new=AsyncMock(
            return_value={"status": "indexed", "doc_id": "ext_abc", "chars": 420}
        )
    ) as fake_ingest:
        await mod.ingestion_pipeline._ingest_binary_attachments("outlook", raw, normalized)

    kwargs = fake_ingest.await_args.kwargs
    assert kwargs["provider"] == "outlook"
    assert kwargs["message_id"] == "msg-1"
    assert kwargs["attachment_id"] == "att-1"
    assert kwargs["user_id"] == "u-9"
    assert kwargs["email_subject"] == "Q3 report"
    assert kwargs["content"].startswith(b"%PDF")
    assert normalized["attachments"][0]["ingestion"] == {
        "status": "indexed", "doc_id": "ext_abc",
    }


@pytest.mark.asyncio
async def test_pipeline_hook_skips_textlike_inline_and_byteless():
    import integrations.atom_communication_ingestion_pipeline as mod

    normalized = _normalized_for(
        [
            {"id": "att-t", "name": "notes.txt", "contentType": "text/plain"},
            {"id": "att-i", "name": "logo.png", "contentType": "image/png", "isInline": True},
            {"id": "att-n", "name": "nofetch.pdf", "contentType": "application/pdf"},
            {"id": "att-y", "name": "yes.pdf", "contentType": "application/pdf",
             "contentBytes": _pdf_b64()},
        ]
    )
    raw = [
        {"id": "att-t", "name": "notes.txt", "contentType": "text/plain",
         "contentBytes": _pdf_b64()},
        {"id": "att-i", "name": "logo.png", "contentType": "image/png", "isInline": True,
         "contentBytes": _pdf_b64()},
        {"id": "att-n", "name": "nofetch.pdf", "contentType": "application/pdf"},
        {"id": "att-y", "name": "yes.pdf", "contentType": "application/pdf",
         "contentBytes": _pdf_b64()},
    ]
    with patch.object(
        mod, "ingest_email_attachment_bytes", new=AsyncMock(
            return_value={"status": "indexed", "doc_id": "d", "chars": 1}
        )
    ) as fake_ingest:
        await mod.ingestion_pipeline._ingest_binary_attachments("outlook", raw, normalized)

    fake_ingest.assert_awaited_once()
    assert fake_ingest.await_args.kwargs["attachment_id"] == "att-y"
    assert "ingestion" not in normalized["attachments"][0]
    assert "ingestion" not in normalized["attachments"][2]
    assert normalized["attachments"][3]["ingestion"]["doc_id"] == "d"


@pytest.mark.asyncio
async def test_pipeline_hook_respects_per_message_cap(monkeypatch):
    import integrations.atom_communication_ingestion_pipeline as mod

    monkeypatch.setenv("MAX_BINARY_ATTACHMENTS_INDEXED_PER_MESSAGE", "1")
    atts = [
        {"id": f"att-{i}", "name": f"f{i}.pdf", "contentType": "application/pdf",
         "contentBytes": _pdf_b64()}
        for i in range(3)
    ]
    normalized = _normalized_for([dict(a) for a in atts])
    with patch.object(
        mod, "ingest_email_attachment_bytes", new=AsyncMock(
            return_value={"status": "indexed", "doc_id": "d", "chars": 1}
        )
    ) as fake_ingest:
        await mod.ingestion_pipeline._ingest_binary_attachments("outlook", atts, normalized)
    assert fake_ingest.await_count == 1


@pytest.mark.asyncio
async def test_pipeline_hook_disabled_by_flag(monkeypatch):
    import integrations.atom_communication_ingestion_pipeline as mod

    monkeypatch.setenv("ENABLE_EMAIL_ATTACHMENT_MEMORY_INDEX", "false")
    normalized = _normalized_for(
        [{"id": "att-1", "name": "r.pdf", "contentType": "application/pdf"}]
    )
    raw = [
        {"id": "att-1", "name": "r.pdf", "contentType": "application/pdf",
         "contentBytes": _pdf_b64()},
    ]
    with patch.object(
        mod, "ingest_email_attachment_bytes", new=AsyncMock()
    ) as fake_ingest:
        await mod.ingestion_pipeline._ingest_binary_attachments("outlook", raw, normalized)
    fake_ingest.assert_not_awaited()
    assert "ingestion" not in normalized["attachments"][0]


@pytest.mark.asyncio
async def test_pipeline_hook_survives_ingestion_failure():
    import integrations.atom_communication_ingestion_pipeline as mod

    normalized = _normalized_for(
        [{"id": "att-1", "name": "r.pdf", "contentType": "application/pdf"}]
    )
    raw = [
        {"id": "att-1", "name": "r.pdf", "contentType": "application/pdf",
         "contentBytes": _pdf_b64()},
    ]
    with patch.object(
        mod, "ingest_email_attachment_bytes", new=AsyncMock(
            return_value={"status": "error", "doc_id": None, "chars": 0}
        )
    ):
        # must not raise — the message still ingests, attachment stays metadata-only
        await mod.ingestion_pipeline._ingest_binary_attachments("outlook", raw, normalized)
    assert normalized["attachments"][0]["ingestion"]["status"] == "error"
