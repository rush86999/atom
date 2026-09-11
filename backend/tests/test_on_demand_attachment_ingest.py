"""On-demand "ingest from the integration" attachment path.

Covers ``core.email_attachment_ingestion.ingest_message_attachments_on_demand``
— the leg that fetches a mailbox message's attachment(s) from the connected
provider and indexes their text into memory when the background poller never
did (or the content predates the pipeline).

Contract under test:
  - provider resolution: explicit, alias, inferred from connected mailboxes;
  - idempotency: an attachment already in memory is reported without a
    provider download (the "if not already in memory" short-circuit);
  - truthful per-attachment statuses (indexed / already_ingested / unsupported
    / error) — never a fabricated success;
  - the extracted text rides back spotlight-wrapped so a product photo or
    scanned quote becomes usable in the same turn.
"""

import os

os.environ.setdefault("TESTING", "1")

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def provider(monkeypatch):
    """Stub the provider I/O so no Graph/Gmail call leaves the process."""
    import core.email_attachment_ingestion as mod

    monkeypatch.setattr(
        mod,
        "_provider_attachment_metadata",
        AsyncMock(
            return_value=[
                {
                    "id": "att-1",
                    "name": "machine-photo.png",
                    "size": 2048,
                    "contentType": "image/png",
                }
            ]
        ),
    )
    monkeypatch.setattr(
        mod, "_provider_download_attachment", AsyncMock(return_value=b"PNG-BYTES")
    )
    monkeypatch.setattr(mod, "_active_mail_providers", lambda user_id: ["outlook"])
    return mod


@pytest.fixture
def ingest_indexed(monkeypatch):
    """The shared ingestion write reports an indexed doc with a text preview."""
    import core.email_attachment_ingestion as mod

    mock = AsyncMock(
        return_value={
            "status": "indexed",
            "doc_id": "ext_deadbeef",
            "chars": 42,
            "text_preview": "Bandsaw BS-460GB, 460mm capacity",
        }
    )
    monkeypatch.setattr(mod, "ingest_email_attachment_bytes", mock)
    return mock


@pytest.fixture
def not_in_memory(monkeypatch):
    from core.auto_document_ingestion import AutoDocumentIngestionService

    mock = AsyncMock(return_value=[])
    monkeypatch.setattr(AutoDocumentIngestionService, "ingested_external_ids", mock)
    return mock


@pytest.fixture
def in_memory(monkeypatch):
    from core.auto_document_ingestion import AutoDocumentIngestionService

    mock = AsyncMock(return_value=["msg-1:att-1"])
    monkeypatch.setattr(AutoDocumentIngestionService, "ingested_external_ids", mock)
    return mock


@pytest.mark.asyncio
async def test_fetches_and_indexes_attachment_from_provider(
    provider, ingest_indexed, not_in_memory
):
    result = await provider.ingest_message_attachments_on_demand(
        user_id="u-1", message_id="msg-1", platform="outlook"
    )

    assert result["success"] is True
    assert result["ingested"] == 1
    assert result["already_ingested"] == 0
    entry = result["attachments"][0]
    assert entry["status"] == "indexed"
    assert entry["doc_id"] == "ext_deadbeef"
    # Text rides back spotlight-wrapped (untrusted email content as DATA).
    assert "Bandsaw BS-460GB" in entry["text"]
    assert "untrusted" in entry["text"].lower() or "UNTRUSTED" in entry["text"]

    # The provider fetch used the caller's id and the message/attachment pair.
    provider._provider_download_attachment.assert_awaited_once_with(
        "outlook", "u-1", "msg-1", "att-1"
    )
    ingest_indexed.assert_awaited_once()
    kwargs = ingest_indexed.await_args.kwargs
    assert kwargs["provider"] == "outlook"
    assert kwargs["message_id"] == "msg-1"
    assert kwargs["attachment_id"] == "att-1"
    assert kwargs["content"] == b"PNG-BYTES"
    # Explicit pull: textless images (product photos) get a description so they
    # still land in memory instead of dying as no_text.
    assert kwargs["describe_images"] is True


@pytest.mark.asyncio
async def test_already_in_memory_skips_provider_download(
    provider, ingest_indexed, in_memory
):
    result = await provider.ingest_message_attachments_on_demand(
        user_id="u-1", message_id="msg-1", platform="outlook"
    )

    assert result["success"] is True
    assert result["ingested"] == 0
    assert result["already_ingested"] == 1
    entry = result["attachments"][0]
    assert entry["status"] == "already_ingested"
    assert entry["doc_id"]  # names the row already in memory
    provider._provider_download_attachment.assert_not_awaited()
    ingest_indexed.assert_not_awaited()


@pytest.mark.asyncio
async def test_provider_inferred_from_connected_mailbox(provider, ingest_indexed, not_in_memory):
    result = await provider.ingest_message_attachments_on_demand(
        user_id="u-1", message_id="msg-1"
    )
    assert result["platform"] == "outlook"
    assert result["success"] is True


@pytest.mark.asyncio
async def test_no_connected_mailbox_reports_honestly(provider, ingest_indexed, not_in_memory, monkeypatch):
    monkeypatch.setattr(provider, "_active_mail_providers", lambda user_id: [])
    result = await provider.ingest_message_attachments_on_demand(
        user_id="u-1", message_id="msg-1"
    )
    assert result["success"] is False
    assert "No connected mailbox" in result["error"]
    provider._provider_download_attachment.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_message_id_rejected(provider):
    result = await provider.ingest_message_attachments_on_demand(
        user_id="u-1", message_id=""
    )
    assert result["success"] is False
    assert "message_id" in result["error"]


@pytest.mark.asyncio
async def test_unsupported_format_is_reported_not_silently_skipped(provider, ingest_indexed, not_in_memory):
    provider._provider_attachment_metadata.return_value = [
        {"id": "att-9", "name": "archive.zip", "size": 10, "contentType": "application/zip"}
    ]
    result = await provider.ingest_message_attachments_on_demand(
        user_id="u-1", message_id="msg-1", platform="outlook"
    )
    assert result["attachments"][0]["status"] == "unsupported"
    assert result["attachments"][0]["reason"] == "unsupported_format"
    assert result["success"] is False
    ingest_indexed.assert_not_awaited()


@pytest.mark.asyncio
async def test_explicit_attachment_id_filters_selection(provider, ingest_indexed, not_in_memory):
    provider._provider_attachment_metadata.return_value = [
        {"id": "att-1", "name": "a.pdf", "size": 1, "contentType": "application/pdf"},
        {"id": "att-2", "name": "b.png", "size": 1, "contentType": "image/png"},
    ]
    result = await provider.ingest_message_attachments_on_demand(
        user_id="u-1", message_id="msg-1", platform="outlook", attachment_id="att-2"
    )
    assert [a["attachment_id"] for a in result["attachments"]] == ["att-2"]
    provider._provider_download_attachment.assert_awaited_once_with(
        "outlook", "u-1", "msg-1", "att-2"
    )


@pytest.mark.asyncio
async def test_explicit_id_absent_from_metadata_still_downloads(provider, ingest_indexed, not_in_memory):
    # Graph occasionally omits reference attachments from the listing; the id
    # is authoritative and the direct download can still resolve it.
    provider._provider_attachment_metadata.return_value = []
    result = await provider.ingest_message_attachments_on_demand(
        user_id="u-1",
        message_id="msg-1",
        platform="outlook",
        attachment_id="att-ref",
        filename_hint="notes.png",
    )
    assert result["attachments"][0]["attachment_id"] == "att-ref"
    assert result["attachments"][0]["status"] == "indexed"
    provider._provider_download_attachment.assert_awaited_once_with(
        "outlook", "u-1", "msg-1", "att-ref"
    )


@pytest.mark.asyncio
async def test_download_failure_is_reported(provider, ingest_indexed, not_in_memory):
    provider._provider_download_attachment.return_value = None
    result = await provider.ingest_message_attachments_on_demand(
        user_id="u-1", message_id="msg-1", platform="outlook"
    )
    assert result["attachments"][0]["status"] == "error"
    assert result["attachments"][0]["reason"] == "download_failed"
    assert result["success"] is False
    ingest_indexed.assert_not_awaited()


@pytest.mark.asyncio
async def test_message_without_attachments_reports_honestly(provider, ingest_indexed, not_in_memory):
    provider._provider_attachment_metadata.return_value = []
    result = await provider.ingest_message_attachments_on_demand(
        user_id="u-1", message_id="msg-1", platform="outlook"
    )
    assert result["success"] is False
    assert result["error"] in ("message_not_found_or_has_no_attachments", "no_attachments_on_message")


@pytest.mark.asyncio
async def test_ingest_reports_unchanged_content_as_already_indexed(provider, not_in_memory, monkeypatch):
    """The shared write dedups identical bytes — the on-demand leg must map
    that to a truthful cached result, not a fresh ingest claim."""
    import core.email_attachment_ingestion as mod

    monkeypatch.setattr(
        mod,
        "ingest_email_attachment_bytes",
        AsyncMock(
            return_value={"status": "indexed", "doc_id": "ext_x", "chars": 0, "cached": True}
        ),
    )
    result = await provider.ingest_message_attachments_on_demand(
        user_id="u-1", message_id="msg-1", platform="outlook"
    )
    assert result["attachments"][0]["status"] == "indexed"
    assert result["attachments"][0]["chars"] == 0


@pytest.mark.asyncio
async def test_mcp_dispatch_routes_to_real_ingestion(monkeypatch):
    """The MCP action must reach the real fetch+ingest leg (it used to be a
    placeholder that returned a fabricated success string)."""
    from unittest.mock import patch

    import tools.email_attachment_tool as attachment_tool_mod
    from integrations.mcp_service import MCPService

    sentinel = {"success": True, "ingested": 1, "already_ingested": 0, "attachments": []}
    mock = AsyncMock(return_value=sentinel)
    with patch(
        "core.email_attachment_ingestion.ingest_message_attachments_on_demand", mock
    ), patch.object(attachment_tool_mod, "gate_for_topic") as fake_gate:
        fake_gate.return_value = {"outcome": "execute", "reason": "test gate"}
        result = await MCPService().execute_tool(
            "local-tools",
            "ingest_message_attachment",
            {"message_id": "m1", "attachment_id": "a1", "platform": "outlook"},
            {"user_id": "u-1", "workspace_id": "default"},
        )

    assert result is sentinel
    mock.assert_awaited_once()
    assert mock.await_args.kwargs["user_id"] == "u-1"
    assert mock.await_args.kwargs["message_id"] == "m1"
    assert mock.await_args.kwargs["attachment_id"] == "a1"
    assert mock.await_args.kwargs["platform"] == "outlook"


@pytest.mark.asyncio
async def test_mcp_dispatch_honors_pinned_approval(monkeypatch):
    """An owner who pinned the email_attachment topic to approval still gets a
    proposal instead of an autonomous memory write."""
    from unittest.mock import patch

    import tools.email_attachment_tool as attachment_tool_mod
    from integrations.mcp_service import MCPService

    mock = AsyncMock(return_value={"success": True})
    with patch(
        "core.email_attachment_ingestion.ingest_message_attachments_on_demand", mock
    ), patch.object(attachment_tool_mod, "gate_for_topic") as fake_gate:
        fake_gate.return_value = {
            "outcome": "propose",
            "reason": "owner pinned this topic",
        }
        result = await MCPService().execute_tool(
            "local-tools",
            "ingest_message_attachment",
            {"message_id": "m1"},
            {"user_id": "u-1"},
        )

    assert result.get("needs_approval") is True
    mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_explicit_pipeline_ingest_requests_image_description(monkeypatch):
    """``ingest_email_on_demand`` is explicit: textless images (product photos)
    get a vision description. The bulk poll/webhook path keeps the default
    (OCR only) so a mailbox sync never pays a vision call per image."""
    import base64

    import integrations.atom_communication_ingestion_pipeline as pipe_mod

    calls = []

    async def fake_ingest(**kwargs):
        calls.append(kwargs)
        return {"status": "indexed", "doc_id": "ext_1", "chars": 10}

    monkeypatch.setattr(pipe_mod, "ingest_email_attachment_bytes", fake_ingest)
    monkeypatch.setattr(pipe_mod, "max_attachments_per_message", lambda: 5)

    class _Stub:
        ingestion_configs: dict = {}

        def _binary_memory_ingest_enabled(self) -> bool:
            return True

    raw = [
        {
            "id": "a1",
            "name": "photo.png",
            "contentType": "image/png",
            "contentBytes": base64.b64encode(b"PNG").decode(),
            "isInline": False,
        }
    ]
    normalized = {"id": "m1", "metadata": {"user_id": "u-1"}, "attachments": []}

    await pipe_mod.CommunicationIngestionPipeline._ingest_binary_attachments(
        _Stub(), "outlook", raw, normalized, describe_images=True
    )
    assert calls and calls[0]["describe_images"] is True

    calls.clear()
    await pipe_mod.CommunicationIngestionPipeline._ingest_binary_attachments(
        _Stub(), "outlook", raw, normalized
    )
    assert calls and calls[0]["describe_images"] is False
