"""
Gmail webhook A-path — route through CommunicationIngestionPipeline.ingest_message.

RED: `IngestionPipelineService.process_webhook_payload` writes Gmail webhook
records to `atom_communications` via a raw `LanceDBHandler.add_document`
call — no normalization, no FTS hybrid, no graph trigger. Outlook's poller
and backfill both flow through `ingest_message`; Gmail's own poller does
too (`_fetch_gmail_messages` -> `ingest_message`). Only the Gmail WEBHOOK
path bypasses it (P0.4 audit follow-up #4).

Why it matters: raw vector dumps are not structured memory — normalized
`ingest_message` records are what `search_communications`, the conversations
hybrid leg, and the agent's role/work memory read from.

Contracts pinned here:
  - integration_id="gmail": every transformed record is bridged to
    `CommunicationIngestionPipeline.ingest_message("gmail", record)`; the
    raw LanceDB write is NOT used.
  - bridge failure degrades gracefully: falls back to the legacy raw
    `atom_communications` write so ingestion never loses the record.
  - outlook/slack behavior unchanged: still the legacy raw write (the audit
    marks their webhook paths working; this fix must not disturb them).
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.ingestion_pipeline import IngestionPipelineService


def _service():
    svc = IngestionPipelineService.__new__(IngestionPipelineService)
    svc.tenant_id = "t-1"
    svc.workspace_id = "w-1"
    svc.graphrag = MagicMock()
    svc.usage_tracker = MagicMock()
    return svc


def _gmail_record():
    # Shape emitted by _transform_gmail_payload after an API fetch.
    return {
        "type": "gmail_message",
        "id": "gm_1",
        "thread_id": "th_1",
        "message_id": "gm_1",
        "subject": "Q3 numbers",
        "content": "Need the Q3 numbers by EOD",
        "from": "client@acme.com",
        "to": "me@atom.dev",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "message_received",
    }


async def _fake_transform(records):
    async def _transform(integration_id, webhook_data):
        return list(records)

    return _transform


@pytest.fixture()
def raw_lancedb():
    """The comm block constructs its own LanceDBHandler in-function; patch
    the class so the legacy raw write is observable."""
    with patch("core.lancedb_handler.LanceDBHandler") as cls:
        yield cls


@pytest.fixture()
def comm_bridge():
    """Patch get_ingestion_pipeline where process_webhook_payload imports it."""
    with patch(
        "integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline"
    ) as factory:
        pipe = MagicMock()
        pipe.ingest_message = AsyncMock(return_value={"success": True})
        factory.return_value = pipe
        yield pipe


class TestGmailWebhookBridgesToIngestMessage:
    @pytest.mark.asyncio
    async def test_gmail_records_route_through_ingest_message(self, comm_bridge):
        svc = _service()
        record = _gmail_record()
        with patch.object(svc, "_transform_webhook_payload",
                          side_effect=(await _fake_transform([record]))):
            result = await svc.process_webhook_payload("gmail", {"historyId": "1"})

        assert comm_bridge.ingest_message.await_count == 1
        args = comm_bridge.ingest_message.await_args.args
        assert args[0] == "gmail"
        assert args[1]["id"] == "gm_1"
        # records_processed counted by the bridge branch
        assert result["records_processed"] >= 1

    @pytest.mark.asyncio
    async def test_gmail_skips_raw_lancedb_write(self, comm_bridge, raw_lancedb):
        svc = _service()
        with patch.object(svc, "_transform_webhook_payload",
                          side_effect=(await _fake_transform([_gmail_record()]))):
            await svc.process_webhook_payload("gmail", {"historyId": "1"})
        raw_lancedb.return_value.add_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_bridge_failure_falls_back_to_raw_write(self, comm_bridge, raw_lancedb):
        comm_bridge.ingest_message = AsyncMock(
            side_effect=RuntimeError("comm store down")
        )
        svc = _service()
        with patch.object(svc, "_transform_webhook_payload",
                          side_effect=(await _fake_transform([_gmail_record()]))):
            result = await svc.process_webhook_payload("gmail", {"historyId": "1"})
        # fallback: legacy raw write preserved the record
        assert raw_lancedb.return_value.add_document.called
        table = raw_lancedb.return_value.add_document.call_args.kwargs.get(
            "table_name"
        ) or raw_lancedb.return_value.add_document.call_args.args[0]
        assert table == "atom_communications"
        assert result["records_processed"] >= 1


class TestOutlookSlackUnchanged:
    @pytest.mark.asyncio
    async def test_outlook_still_uses_raw_write(self, raw_lancedb):
        svc = _service()
        record = dict(_gmail_record(), type="email", id="ol_1")
        with patch.object(svc, "_transform_webhook_payload",
                          side_effect=(await _fake_transform([record]))):
            with patch(
                "integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline"
            ) as factory:
                pipe = MagicMock()
                pipe.ingest_message = AsyncMock()
                factory.return_value = pipe
                await svc.process_webhook_payload("outlook", {})
                pipe.ingest_message.assert_not_awaited()
        raw_lancedb.return_value.add_document.assert_called()

    @pytest.mark.asyncio
    async def test_slack_still_uses_raw_write(self, raw_lancedb):
        svc = _service()
        record = {
            "id": "sl_1",
            "text": "deploy is green",
            "sender_id": "U1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with patch.object(svc, "_transform_webhook_payload",
                          side_effect=(await _fake_transform([record]))):
            with patch(
                "integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline"
            ) as factory:
                pipe = MagicMock()
                pipe.ingest_message = AsyncMock()
                factory.return_value = pipe
                await svc.process_webhook_payload("slack", {})
                pipe.ingest_message.assert_not_awaited()
        raw_lancedb.return_value.add_document.assert_called()

class TestTeamsDiscordQueueBridge:
    """Same contract as Gmail, for the other queue-routed comm apps whose
    `/webhooks/communication/*` paths were B-only (P0.4 audit: Teams/Discord
    rows). Outlook/slack stay excluded."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("integration_id,record", [
        ("teams", {
            "type": "teams_message",
            "id": "tm_1",
            "text": "standup notes in channel",
            "from": "Ops Bot",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "message_created",
        }),
        ("discord", {
            "type": "discord_message",
            "id": "dc_1",
            "content": "deploy is green",
            "author": "devops",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "message_created",
        }),
    ])
    async def test_queue_records_bridge_to_ingest_message(
        self, comm_bridge, raw_lancedb, integration_id, record,
    ):
        svc = _service()
        with patch.object(svc, "_transform_webhook_payload",
                          side_effect=(await _fake_transform([record]))):
            result = await svc.process_webhook_payload(integration_id, {})
        assert comm_bridge.ingest_message.await_count == 1
        args = comm_bridge.ingest_message.await_args.args
        assert args[0] == integration_id
        assert args[1]["id"] == record["id"]
        assert result["records_processed"] >= 1
        raw_lancedb.return_value.add_document.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("integration_id,record", [
        ("teams", {
            "type": "teams_message", "id": "tm_2",
            "text": "standup moved to ten-thirty today",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }),
        ("discord", {
            "type": "discord_message", "id": "dc_2",
            "content": "deploy window shifted to friday evening",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }),
    ])
    async def test_bridge_failure_falls_back_per_record(
        self, comm_bridge, raw_lancedb, integration_id, record,
    ):
        comm_bridge.ingest_message = AsyncMock(
            side_effect=RuntimeError("comm store down")
        )
        svc = _service()
        with patch.object(svc, "_transform_webhook_payload",
                          side_effect=(await _fake_transform([record]))):
            result = await svc.process_webhook_payload(integration_id, {})
        assert raw_lancedb.return_value.add_document.called
        assert result["records_processed"] >= 1

    @pytest.mark.asyncio
    async def test_mixed_bridge_outcome_writes_only_failures_raw(self, comm_bridge, raw_lancedb):
        """Two records: first bridges fine, second fails -> only the second
        continues to the legacy raw write (no double-writes). NOTE: the
        per-record prep loop rewrites record["content"] into a formatted
        summary before both paths, so identity is asserted via doc_id."""
        record_ok = {"type": "discord_message", "id": "ok_1",
                     "content": "release checklist is all green",
                     "timestamp": datetime.now(timezone.utc).isoformat()}
        record_bad = {"type": "discord_message", "id": "bad_1",
                      "content": "rollback triggered boom scenario",
                      "timestamp": datetime.now(timezone.utc).isoformat()}
        comm_bridge.ingest_message = AsyncMock(
            side_effect=[{"success": True}, RuntimeError("down")]
        )
        svc = _service()
        with patch.object(svc, "_transform_webhook_payload",
                          side_effect=(await _fake_transform([record_ok, record_bad]))):
            await svc.process_webhook_payload("discord", {})
        assert comm_bridge.ingest_message.await_count == 2
        assert raw_lancedb.return_value.add_document.call_count == 1
        doc_id = raw_lancedb.return_value.add_document.call_args.kwargs.get(
            "doc_id"
        ) or raw_lancedb.return_value.add_document.call_args.args[0]
        assert doc_id == "bad_1"
